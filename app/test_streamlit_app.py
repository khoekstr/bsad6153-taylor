"""Regression checks for freshness, parameter binding, and public UI failures."""

from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import MagicMock, patch

import psycopg
from streamlit.testing.v1 import AppTest

from app import streamlit_app as library


NOW = datetime(2026, 11, 23, 18, tzinfo=timezone.utc)


def paper(**changes):
    result = {
        "work_id": 1, "title": "AI and learning", "publication_date": NOW.date(),
        "first_seen_at": NOW, "openalex_topic": "Education", "source": "openalex",
        "source_url": "https://example.org/paper", "doi": "10.1234/example",
        "openalex_id": "https://openalex.org/W123", "abstract": "Original abstract.",
        "value_rating": 5, "summary": "A saved summary.", "value_reason": "Relevant to learning.",
        "relevance_reason": "Explores student motivation.", "review_basis": "abstract",
        "categories": ["Learning"], "matching_papers": 1,
    }
    result.update(changes)
    return result


class FreshnessTests(unittest.TestCase):
    def test_recent_and_exact_boundary(self):
        for age in (timedelta(hours=1), timedelta(days=4)):
            with self.subTest(age=age):
                self.assertEqual(library.freshness_state(NOW - age, NOW)[0], "success")

    def test_warning_after_four_days(self):
        level, message = library.freshness_state(NOW - timedelta(days=4, seconds=1), NOW)
        self.assertEqual(level, "warning")
        self.assertIn("overdue", message)

    def test_unknown_future_and_naive_times(self):
        for timestamp in (None, NOW + timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(library.freshness_state(timestamp, NOW)[0], "warning")

    def test_cached_timestamp_does_not_freeze_age(self):
        finished = NOW - timedelta(days=4)
        self.assertEqual(library.freshness_state(finished, NOW)[0], "success")
        self.assertEqual(library.freshness_state(finished, NOW + timedelta(seconds=1))[0], "warning")

    def test_banner_selects_completed_live_discovery(self):
        with patch.object(library, "select_rows", return_value=[{"finished_at": NOW}]) as query:
            with patch.object(library.st, "success"), patch.object(library.st, "warning"):
                library.freshness_banner()
        statement, parameters = query.call_args.args
        self.assertIn("NOT dry_run", statement)
        self.assertIn("finished_at IS NOT NULL", statement)
        self.assertEqual(parameters, ("success", "discovery_only", "completed"))


class AccessTests(unittest.TestCase):
    def test_filter_values_are_bound(self):
        keyword = "%' OR 1=1; DROP TABLE works; --"
        with patch.object(library, "select_rows", return_value=[]) as query:
            library.fetch_papers(search=keyword, topic="Learning", minimum=4)
        statement, values = query.call_args.args
        self.assertNotIn(keyword, statement)
        self.assertEqual(values[:5], (keyword, keyword, "Learning", "Learning", "Learning"))
        self.assertEqual(values[-4:], (4, 4, library.PAGE_SIZE, 0))
        self.assertEqual(statement.count("%s"), len(values))

    def test_owner_credentials_are_rejected_before_connecting(self):
        with patch.dict(os.environ, {"APP_DATABASE_URL": "postgresql://postgres:secret@example.org/db"}):
            with patch.object(library.access.psycopg, "connect") as connect:
                with self.assertRaises(library.LibraryUnavailable):
                    with library.reader_connection():
                        self.fail("Owner account was accepted")
                connect.assert_not_called()

    def test_reader_role_and_read_only_transaction(self):
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = {"role": "library_web_reader", "login": "library_web_reader"}
        connection.__enter__.return_value = connection
        with patch.dict(os.environ, {"APP_DATABASE_URL": "postgresql://library_web_reader.project:secret@example.org/db"}):
            with patch.object(library.access.psycopg, "connect", return_value=connection):
                with library.reader_connection() as actual:
                    self.assertIs(actual, connection)
                    self.assertTrue(connection.read_only)

    def test_connection_errors_have_safe_messages(self):
        with patch.dict(os.environ, {"APP_DATABASE_URL": "postgresql://library_web_reader:secret@example.org/db"}):
            with patch.object(library.access.psycopg, "connect", side_effect=psycopg.OperationalError("secret host details")):
                with self.assertRaises(library.LibraryUnavailable) as error:
                    with library.reader_connection():
                        pass
        self.assertNotIn("secret", str(error.exception))

    def test_cached_results_are_scoped_to_connection_settings(self):
        library.cached_select.clear()
        self.addCleanup(library.cached_select.clear)
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [{"count": 2}]
        context = MagicMock()
        context.__enter__.return_value = connection
        with patch.object(library, "reader_connection", return_value=context) as connect:
            with patch.dict(os.environ, {"APP_DATABASE_URL": "reader-configuration-one"}):
                self.assertEqual(library.select_rows("SELECT count(*) FROM works"), [{"count": 2}])
                library.select_rows("SELECT count(*) FROM works")
                self.assertEqual(connect.call_count, 1)
            with patch.dict(os.environ, {"APP_DATABASE_URL": "reader-configuration-two"}):
                library.select_rows("SELECT count(*) FROM works")
                self.assertEqual(connect.call_count, 2)

    def test_connection_failures_are_retried_instead_of_cached(self):
        library.cached_select.clear()
        self.addCleanup(library.cached_select.clear)
        with patch.object(library, "reader_connection", side_effect=library.LibraryUnavailable("Unavailable")) as connect:
            with patch.dict(os.environ, {"APP_DATABASE_URL": "reader-configuration"}):
                for attempt in range(2):
                    with self.subTest(attempt=attempt), self.assertRaises(library.LibraryUnavailable):
                        library.select_rows("SELECT count(*) FROM works")
        self.assertEqual(connect.call_count, 2)

    def test_public_queries_exclude_private_fields(self):
        for statement in (library.PAPERS_SQL, library.TOPICS_SQL, library.STATS_SQL):
            for private_name in ("reading_notes", "assessment_context", "file_path", "is_favorite", "reading_status"):
                with self.subTest(statement=statement[:30], field=private_name):
                    self.assertNotIn(private_name, statement)
            self.assertIn("assessed_by = 'ai'", statement)

    def test_external_links_reject_unsafe_targets(self):
        for value in ("javascript:alert(1)", "file:///private", "https://user:secret@example.org/", "http://127.0.0.1/", "https://localhost/", "https://example.org/\nprivate"):
            with self.subTest(value=value):
                self.assertIsNone(library.external_url(value))
        self.assertEqual(library.external_url("https://doi.org/10.1234/example"), "https://doi.org/10.1234/example")


class PublicViewTests(unittest.TestCase):
    def setUp(self):
        self.papers = [paper()]
        self.finished_at = datetime.now(timezone.utc) - timedelta(hours=2)
        self.query_patch = patch.object(library, "select_rows", side_effect=self.query)
        self.query_mock = self.query_patch.start()
        self.addCleanup(self.query_patch.stop)

    def query(self, statement, parameters=()):
        if statement == library.FRESHNESS_SQL:
            return [{"finished_at": self.finished_at}]
        if statement == library.STATS_SQL:
            return [{"total_papers": 12, "recent_papers": 2, "awaiting_assessment": 3}]
        if statement == library.TOPICS_SQL:
            return [{"topic": "Learning", "paper_count": 5}]
        return self.papers

    def app(self):
        return AppTest.from_string("from app.streamlit_app import main\nmain()", default_timeout=10).run()

    def test_discover_keeps_original_abstract_off_public_card(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.subheader[0].value, "AI and learning")
        self.assertNotIn("Read the original abstract", [item.label for item in app.expander])
        self.assertFalse(any("Original abstract" in item.value for item in app.markdown))
        self.assertTrue(app.success)

    def test_stale_and_missing_history_render_warning(self):
        for timestamp in (None, datetime.now(timezone.utc) - timedelta(days=5)):
            with self.subTest(timestamp=timestamp):
                self.finished_at = timestamp
                app = self.app()
                self.assertFalse(app.exception)
                self.assertTrue(app.warning)

    def test_explore_controls_change_query_parameters(self):
        app = self.app()
        app.radio(key="library_view").set_value("Explore").run()
        app.text_input(key="explore_search").set_value("motivation").run()
        app.selectbox(key="explore_topic").set_value("Learning").run()
        app.selectbox(key="explore_minimum").set_value(4).run()
        self.assertFalse(app.exception)
        calls = self.query_mock.call_args_list
        paper_calls = [call for call in calls if call.args[0] == library.PAPERS_SQL]
        values = paper_calls[-1].args[1]
        self.assertEqual(values[:5], ("motivation", "motivation", "Learning", "Learning", "Learning"))
        self.assertEqual(values[-4:-2], (4, 4))

    def test_empty_results_and_unknown_score(self):
        self.papers = []
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        self.papers = [paper(value_rating=None, summary=None, publication_date=None)]
        app.radio(key="library_view").set_value("Explore").run()
        self.assertFalse(app.exception)
        captions = " ".join(item.value for item in app.caption)
        self.assertIn("Interest is unknown", captions)
        self.assertIn("Published Unknown", captions)

    def test_date_bounds_and_filter_changes_reset_pagination(self):
        self.papers = [paper(matching_papers=25)]
        app = self.app()
        app.radio(key="library_view").set_value("Explore").run()
        app.number_input(key="explore_page").set_value(2).run()
        paper_calls = [call for call in self.query_mock.call_args_list if call.args[0] == library.PAPERS_SQL]
        self.assertEqual(paper_calls[-1].args[1][-1], library.PAGE_SIZE)
        start, end = NOW.date() - timedelta(days=10), NOW.date()
        app.date_input(key="explore_dates").set_value((start, end)).run()
        self.assertFalse(app.exception)
        paper_calls = [call for call in self.query_mock.call_args_list if call.args[0] == library.PAPERS_SQL]
        values = paper_calls[-1].args[1]
        self.assertEqual(values[5:9], (start, start, end, end))
        self.assertEqual(values[-1], 0)

    def test_failure_does_not_render_exception_or_details(self):
        self.query_mock.side_effect = RuntimeError("secret connection details")
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertTrue(app.warning)
        visible = " ".join(item.value for item in list(app.error) + list(app.warning))
        self.assertNotIn("secret", visible)


if __name__ == "__main__":
    unittest.main()
