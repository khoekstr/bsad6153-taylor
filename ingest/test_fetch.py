"""Offline behavior tests. No .env access and no live API requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from ingest.fetch import Client, FetchError, collect


def response(status=200, payload=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload if payload is not None else {"results": []}
    return result


def work(identifier, title="Example"):
    return {"id": f"https://openalex.org/W{identifier}", "display_name": title,
            "authorships": [{"author": {"id": "https://openalex.org/A1"}}]}


class FetchTests(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parent / "__pycache__"
        cache.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=cache)
        assert Path(self.temp.name).resolve().is_relative_to(cache.resolve())
        self.addCleanup(self.temp.cleanup)
        self.client = Client("fake-test-key", Path(self.temp.name), delay=0)
        self.client.session = Mock()
        sleeper = patch("ingest.fetch.time.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_rate_limit_then_success_and_raw_preserved(self):
        payload = {"results": [work(1)], "meta": {"next_cursor": "abc"}}
        self.client.session.get.side_effect = [response(429, headers={"Retry-After": "3"}), response(payload=payload)]
        actual, filename = self.client.get("works")
        self.assertEqual(payload, actual)
        self.assertEqual(json.loads((Path(self.temp.name) / filename).read_text()), payload)
        self.sleep.assert_any_call(3)

    def test_timeout_and_server_error_retry(self):
        self.client.session.get.side_effect = [requests.Timeout(), response(503), response()]
        self.client.get("works")
        self.assertEqual(self.client.stats["retries"], 2)

    def test_daily_exhaustion_stops(self):
        self.client.session.get.return_value = response(429, headers={"X-RateLimit-Remaining": "0"})
        with self.assertRaisesRegex(FetchError, "allowance exhausted"):
            self.client.get("works")
        self.assertEqual(self.client.session.get.call_count, 1)

    def test_failure_is_bounded(self):
        self.client.session.get.return_value = response(503)
        with self.assertRaisesRegex(FetchError, "Retries exhausted"):
            self.client.get("works")
        self.assertEqual(self.client.session.get.call_count, 5)

    def test_invalid_json_retry(self):
        bad = response()
        bad.json.side_effect = ValueError("bad")
        self.client.session.get.side_effect = [bad, response()]
        self.client.get("works")
        self.assertEqual(self.client.stats["retries"], 1)

    def test_pagination_dedup_missing_fields_and_related_authors(self):
        self.client.session.get.side_effect = [
            response(payload={"results": [work(1), {}], "meta": {"next_cursor": "next"}}),
            response(payload={"results": [work(1), work(2)], "meta": {"next_cursor": None}}),
            response(payload={"results": [{"id": "https://openalex.org/A1", "display_name": "Author"}]})]
        plan = {"required_titles": [], "manual_additions": [], "groups": [{"name": "test", "target": 2, "queries": ["AI"]}]}
        report = collect(self.client, plan, 2)
        self.assertTrue(report["complete"])
        self.assertEqual(report["unique_works"], 2)
        self.assertEqual(report["unique_authors"], 1)
        self.assertEqual(self.client.session.get.call_args_list[1].kwargs["params"]["cursor"], "next")
        self.assertEqual(report["stats"]["invalid_works"], 1)
        self.assertEqual(report["stats"]["duplicate_works"], 1)

    def test_unresolved_seed_and_shortfall_reported(self):
        self.client.session.get.return_value = response()
        plan = {"required_titles": ["Missing title"], "manual_additions": [], "groups": []}
        report = collect(self.client, plan, 500)
        self.assertFalse(report["complete"])
        self.assertEqual(report["required"]["Missing title"], "needs manual match")

    def test_local_request_cap(self):
        self.client.max_requests = 1
        self.client.session.get.return_value = response()
        self.client.get("works")
        with self.assertRaisesRegex(FetchError, "request cap"):
            self.client.get("works")

    def test_resolved_id_handles_abbreviated_title(self):
        self.client.session.get.side_effect = [
            response(payload={"results": [work(1, "Full title with subtitle")]}),
            response(payload={"results": [{"id": "https://openalex.org/A1", "display_name": "Author"}]})]
        plan = {"required_titles": ["Short title"], "required_ids": {"Short title": "https://openalex.org/W1"}, "manual_additions": [], "groups": []}
        report = collect(self.client, plan, 1)
        self.assertTrue(report["complete"])
        self.assertEqual(report["required"]["Short title"], "https://openalex.org/W1")
        self.assertEqual(self.client.session.get.call_args_list[0].kwargs["params"]["filter"], "openalex_id:https://openalex.org/W1")


if __name__ == "__main__":
    unittest.main()
