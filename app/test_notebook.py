"""Notebook access, persistence requests, and the private Streamlit workflow."""
from contextlib import contextmanager
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from app import library_access as access, streamlit_app as library
from app.test_streamlit_app import NOW, paper


IDENTITY = {"is_logged_in": True, "iss": "https://accounts.google.com",
            "sub": "owner-id", "exp": time.time() + 3600}


class NotebookAccessTests(unittest.TestCase):
    def test_only_configured_google_identity_can_use_either_private_operation(self):
        with patch.dict(os.environ, {"NOTEBOOK_GOOGLE_SUB": "owner-id"}):
            for changes in ({"is_logged_in": False}, {"sub": "someone-else"},
                            {"iss": "different-provider"}, {"exp": 1}, {"exp": None}):
                with self.subTest(changes=changes), patch.object(access.st, "user", IDENTITY | changes):
                    with patch.object(access.psycopg, "connect") as connect:
                        with self.assertRaises(access.LibraryUnavailable):
                            access.read_notes()
                        with self.assertRaises(access.LibraryUnavailable):
                            access.save_note(3, "notebook:k", "my thoughts", "", "", None)
                        connect.assert_not_called()
            with patch.object(access.st, "user", IDENTITY):
                self.assertTrue(access.owner_signed_in())
                with patch.dict(os.environ, {"NOTEBOOK_GOOGLE_SUB": ""}):
                    self.assertFalse(access.owner_signed_in())

    def test_wrong_role_is_refused_at_both_checks(self):
        with patch.object(access, "owner_signed_in", return_value=True):
            for username in ("postgres", "app_reader", "library_web_reader", "library_notebook"):
                url = f"postgresql://{username}.project@example.org/db"
                with self.subTest(username=username), patch.dict(os.environ, {"NOTEBOOK_DATABASE_URL": url}):
                    with patch.object(access.psycopg, "connect") as connect:
                        connection = connect.return_value.__enter__.return_value
                        connection.execute.return_value.fetchone.return_value = {
                            "role": "library_notebook", "login": "postgres"}
                        with self.assertRaises(access.LibraryUnavailable):
                            access.read_notes()
                        self.assertEqual(connect.call_count, int(username == "library_notebook"))

    def test_retry_uses_same_key_and_preserves_exact_words(self):
        db = MagicMock()
        text = "  O'Brien\nmy *own* thought  "
        fields = {"work_id": 7, "notes": text, "quoted_passage": "  quote ",
                  "key_references": "p. 3", "reading_status": None}
        db.execute.return_value.fetchone.side_effect = [{"note_id": 1}, None, fields, None, fields]
        @contextmanager
        def database(*, notebook):
            self.assertTrue(notebook)
            yield db
        with patch.object(access, "database_connection", database):
            for _ in range(2):
                access.save_note(7, "notebook:abc", text, "  quote ", "p. 3", None)
            with self.assertRaises(access.EarlierSave):
                access.save_note(7, "notebook:abc", "edited", "  quote ", "p. 3", None)
        sql, params = db.execute.call_args_list[0].args
        self.assertIn("ON CONFLICT (import_key) DO NOTHING", sql)
        self.assertNotIn(text, sql)
        self.assertEqual(params, (*fields.values(), "notebook:abc"))
        self.assertEqual(db.execute.call_args_list[0], db.execute.call_args_list[1])
        for call in db.execute.call_args_list:
            self.assertNotIn("work_assessments", call.args[0])

    def test_empty_note_and_location_only_do_not_open_database(self):
        with patch.object(access, "database_connection") as db:
            with self.assertRaises(access.LibraryUnavailable):
                access.save_note(1, "notebook:k", " ", "", "p. 2", None)
            db.assert_not_called()


class NotebookViewTests(unittest.TestCase):
    def test_save_retry_revisit_and_public_session(self):
        saved = []
        def public_sql(statement, parameters=()):
            if statement == library.FRESHNESS_SQL:
                return [{"finished_at": NOW}]
            if statement == library.STATS_SQL:
                return [{"total_papers": 1, "recent_papers": 1, "awaiting_assessment": 0}]
            return [paper()]

        def store(work_id, key, note, passage, location, progress):
            saved.append(paper(note_id=1, work_id=work_id, notes=note, quoted_passage=passage,
                               key_references=location, reading_status=progress, stopped_reason=None,
                               noted_at=NOW))
        script = "from app.streamlit_app import main\nmain()"
        with (patch.dict(os.environ, {"NOTEBOOK_GOOGLE_SUB": "owner-id"}),
              patch.object(library.st, "user", IDENTITY),
              patch.object(library, "select_rows", side_effect=public_sql),
              patch.object(access, "read_notes", side_effect=lambda work_id=None: saved) as read,
              patch.object(access, "save_note") as save):
            app = AppTest.from_string(script).run()
            app.button(key="notes_1").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.radio(key="library_view").value, "My notes")
            app.text_area[0].set_value("  private comment  ")
            app.text_area[1].set_value("exact passage")
            app.text_input[0].set_value("p. 7")
            app.selectbox[0].set_value("partial")
            save.side_effect = access.LibraryUnavailable("Please try again.")
            next(b for b in app.button if b.label == "Save note").click().run()
            self.assertEqual(app.text_area[0].value, "  private comment  ")
            self.assertTrue(app.error)
            save.side_effect = store
            next(b for b in app.button if b.label == "Save note").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(save.call_args_list[0], save.call_args_list[1])
            self.assertEqual(len(saved), 1)
            self.assertEqual(app.text_area[0].value, "")
            self.assertIn("exact passage", [t.value for t in app.text])
            new_session = AppTest.from_string(script).run()
            new_session.radio(key="library_view").set_value("My notes").run()
            self.assertEqual(saved[0]["notes"], "  private comment  ")
            self.assertIn("private comment", [t.value for t in new_session.text])
            new_session.button(key="notebook_open_1").click().run()
            self.assertEqual(new_session.subheader[0].value, "AI and learning")
            with patch.object(library.st, "user", IDENTITY | {"sub": "someone-else"}):
                read.reset_mock()
                app.run()
                self.assertFalse(app.exception)
                self.assertNotIn("My notes", app.radio[0].options)
                self.assertFalse(app.text_area)
                read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
