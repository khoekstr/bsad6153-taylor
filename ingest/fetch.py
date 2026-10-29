"""Collect OpenAlex candidate works and linked authors; no database or LLM calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import os
from pathlib import Path
import re
import time
import uuid

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("fetch")


class FetchError(Exception):
    """Safe error message: never include request headers, key, or response body."""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def retry_delay(value, fallback):
    seconds = number(value)
    if seconds is not None:
        return max(0, seconds)
    try:
        return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return fallback


class Client:
    def __init__(self, key, folder, delay=2, max_requests=150):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}", "User-Agent": "BSAD6153-reading-library/0.1"})
        self.folder = folder
        self.delay = delay
        self.max_requests = max_requests
        self.stats = Counter()
        self.exhausted = False

    def get(self, endpoint, params=None):
        for attempt in range(5):
            if self.exhausted:
                raise FetchError("Daily allowance exhausted; wait until reset.")
            if self.stats["requests"] >= self.max_requests:
                raise FetchError("Local request cap reached; review summary before another run.")
            if self.stats["requests"]:
                time.sleep(self.delay)
            self.stats["requests"] += 1
            fallback = 2 ** (attempt + 1)
            try:
                response = self.session.get("https://api.openalex.org/" + endpoint, params=params, timeout=(10, 45), allow_redirects=False)
            except (requests.Timeout, requests.ConnectionError):
                LOG.warning("Temporary network failure (%s), attempt %d/5", endpoint, attempt + 1)
                self.stats["retries"] += 1
                time.sleep(fallback)
                continue
            remaining = number(response.headers.get("X-RateLimit-Remaining"))
            if remaining is not None and remaining <= 0:
                self.exhausted = True
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if self.exhausted:
                    raise FetchError("Daily allowance exhausted; wait until reset.")
                pause = retry_delay(response.headers.get("Retry-After"), fallback)
                if pause > 60:
                    raise FetchError("Server requests a wait longer than 60 seconds; retry later.")
                LOG.warning("HTTP %d (%s); retry in %.1fs", response.status_code, endpoint, pause)
                self.stats["retries"] += 1
                time.sleep(pause)
                continue
            if response.status_code != 200:
                raise FetchError(f"HTTP {response.status_code} from {endpoint}; check authentication or query documentation.")
            try:
                payload = response.json()
            except ValueError:
                LOG.warning("Invalid JSON (%s); retrying", endpoint)
                self.stats["retries"] += 1
                time.sleep(fallback)
                continue
            # Save the response before validating/transforming any records.
            filename = f"{self.stats['requests']:04d}_{endpoint}.json"
            write_json(self.folder / filename, payload)
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise FetchError(f"Unexpected {endpoint} response shape; raw response retained.")
            return payload, filename
        raise FetchError(f"Retries exhausted for {endpoint}; partial results retained.")


def normalized(title):
    return re.sub(r"[^\w]+", " ", title.casefold()).strip()


def valid_record(record, prefix):
    return (isinstance(record, dict)
            and isinstance(record.get("id"), str)
            and re.fullmatch(r"https://openalex.org/" + prefix + r"\d+", record["id"])
            and isinstance(record.get("display_name"), str)
            and bool(record["display_name"].strip()))


def collect(client, plan, target, max_pages=10):
    works, authors = {}, {}
    report = {"selected": {}, "required": {}, "manual_additions": plan["manual_additions"], "warnings": [], "groups": {}}

    def accept(record, label, filename):
        if not valid_record(record, "W"):
            client.stats["invalid_works"] += 1
            LOG.warning("Skipping work missing valid ID/title in %s", filename)
            return False
        if record["id"] in works:
            client.stats["duplicate_works"] += 1
            return False
        for field in ("publication_date", "abstract_inverted_index", "authorships"):
            if not record.get(field):
                client.stats["missing_" + field] += 1
        works[record["id"]] = record
        report["selected"][record["id"]] = {"group": label, "raw_file": filename}
        return True

    try:
        # Exact normalized title matches only; abbreviated titles need human review.
        for title in plan["required_titles"]:
            resolved_id = plan.get("required_ids", {}).get(title)
            params = {"filter": "openalex_id:" + resolved_id, "per_page": 1} if resolved_id else {"search": title, "per_page": 5}
            payload, filename = client.get("works", params)
            matches = [r for r in payload["results"] if valid_record(r, "W") and
                       (r["id"] == resolved_id if resolved_id else normalized(r["display_name"]) == normalized(title))]
            if len(matches) == 1:
                accept(matches[0], "required", filename)
                report["required"][title] = matches[0]["id"]
            else:
                report["required"][title] = "needs manual match"
                report["warnings"].append("Unresolved required title: " + title)

        for group in plan["groups"]:
            count = 0
            # Round-robin queries prevents the first search from filling a category.
            cursors = {query: "*" for query in group["queries"]}
            seen = {query: set() for query in cursors}
            quota = group["target"]
            for _ in range(max_pages):
                for query in group["queries"]:
                    cursor = cursors[query]
                    if cursor is None or count >= quota or len(works) >= target:
                        continue
                    seen[query].add(cursor)
                    payload, filename = client.get("works", {
                        "search": query, "filter": "type:article,language:en,is_oa:true",
                        "per_page": min(25, quota - count, target - len(works)), "cursor": cursor,
                    })
                    for record in payload["results"]:
                        if count < quota and len(works) < target and accept(record, group["name"], filename):
                            count += 1
                    meta = payload.get("meta") or {}
                    next_cursor = meta.get("next_cursor") if isinstance(meta, dict) else None
                    if not payload["results"] or next_cursor in seen[query]:
                        next_cursor = None
                    cursors[query] = next_cursor
                if count >= quota or len(works) >= target or not any(cursors.values()):
                    break
            report["groups"][group["name"]] = count
            LOG.info("%s: %d selected; %d unique works total", group["name"], count, len(works))

        # Fetch distinct author resources, not just the authorship stubs in works.
        ids = set()
        for work in works.values():
            for entry in work.get("authorships") or []:
                author = entry.get("author") if isinstance(entry, dict) else None
                identifier = author.get("id") if isinstance(author, dict) else None
                if isinstance(identifier, str) and re.fullmatch(r"https://openalex.org/A\d+", identifier):
                    ids.add(identifier)
        ordered = sorted(ids)
        for start in range(0, len(ordered), 100):
            batch = ordered[start:start + 100]
            payload, _ = client.get("authors", {"filter": "openalex_id:" + "|".join(batch), "per_page": 100})
            for author in payload["results"]:
                if valid_record(author, "A") and author["id"] in ids:
                    authors[author["id"]] = author
                else:
                    client.stats["invalid_authors"] += 1
            missing = set(batch) - authors.keys()
            if missing:
                report["warnings"].append(f"{len(missing)} linked authors absent from batch response")
        report["linked_author_ids"] = ordered
    except (FetchError, requests.RequestException) as error:
        # requests exception strings can contain credentials: never log them.
        report["error"] = str(error) if isinstance(error, FetchError) else "Request failed; details suppressed to protect credentials."
        LOG.error("%s", report["error"])
    report.update({"unique_works": len(works), "unique_authors": len(authors), "author_ids": sorted(authors), "stats": dict(client.stats)})
    report["complete"] = len(works) >= target and bool(authors) and "error" not in report
    if len(works) < target:
        report["warnings"].append("Below target; refine queries or increase page cap after review.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=150)
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum pages per search")
    parser.add_argument("--write-sample", action="store_true", help="Save one real work and author in data/sample/ for review")
    args = parser.parse_args()
    if args.max_requests < 1 or args.max_pages < 1:
        parser.error("Limits must be positive")
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        print("Set OPENALEX_API_KEY in the local .env file. Its value will not be printed.")
        return 1
    folder = ROOT / "data/raw" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(folder / "fetch.log", encoding="utf-8")])
    plan = json.loads((Path(__file__).with_name("selection.json")).read_text(encoding="utf-8"))
    write_json(folder / "selection.json", plan)
    report = collect(Client(key, folder, max_requests=args.max_requests), plan, 500, args.max_pages)
    write_json(folder / "summary.json", report)
    if args.write_sample and report["complete"]:
        # A clearly labeled excerpt, not a fabricated full API response.
        samples = {}
        for resource, selected in (("works", report["selected"]), ("authors", report["author_ids"])):
            for path in sorted(folder.glob(f"*_{resource}.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                match = next((r for r in payload["results"] if isinstance(r, dict) and r.get("id") in selected), None)
                if match:
                    samples[resource] = match
                    break
        write_json(ROOT / "data/sample/openalex_sample.json", {"description": "Unmodified record excerpts from OpenAlex responses; not a complete API response.", "records": samples})
    LOG.info("Finished: %d works, %d authors. Complete: %s. Report: %s", report["unique_works"], report["unique_authors"], report["complete"], folder / "summary.json")
    for warning in report["warnings"]:
        LOG.warning("%s", warning)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
