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
    def test_unchecking_saved_for_later_persists_immediately(self):
        article = {"come_back_to_it": True}
        script = "from app.owner_workspace import reading_details\nreading_details(42, article)"
        def save(work_id, selected):
            article["come_back_to_it"] = selected
        with patch.object(access, "set_saved_for_later", side_effect=save) as write:
            app = AppTest.from_string("import streamlit as st\narticle = st.session_state.article\n" + script)
            app.session_state.article = article
            app.run().checkbox[0].uncheck().run()
            write.assert_called_once_with(42, False)
            self.assertFalse(app.exception)
            self.assertEqual(app.success[0].value, "Removed from Saved for later.")
            self.assertFalse(app.checkbox[0].value)

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
            if statement == library.TOPICS_SQL:
                return []
            if statement == library.STATS_SQL:
                return [{"total_papers": 1, "recent_papers": 1, "awaiting_assessment": 0}]
            return [paper()]

        def store(work_id, key, note, passage, location, progress):
            saved.append(paper(note_id=1, work_id=work_id, notes=note, quoted_passage=passage,
                               key_references=location, reading_status=progress, stopped_reason=None,
                               noted_at=NOW, last_updated_at=NOW, deleted_at=None))
        script = "from app.streamlit_app import main\nmain()"
        with (patch.dict(os.environ, {"NOTEBOOK_GOOGLE_SUB": "owner-id"}),
              patch.object(library.st, "user", IDENTITY),
              patch.object(library, "select_rows", side_effect=public_sql),
              patch.object(access, "read_notes", side_effect=lambda work_id=None: saved) as read,
              patch.object(access, "read_assessments", return_value=[]),
              patch.object(access, "feedback_snapshot", return_value=[]),
              patch.object(access, "connections", return_value=[]),
              patch.object(access, "note_history", return_value=[]),
              patch.object(access, "save_note") as save):
            app = AppTest.from_string(script).run()
            app.button(key="notes_1").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.radio(key="library_view").value, "Discover")
            app.text_area[0].set_value("  private comment  ")
            app.text_area[1].set_value("exact passage")
            app.text_input[0].set_value("p. 7")
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
            new_session.radio(key="library_view").set_value("My reading").run()
            self.assertIn("private comment", [t.value for t in new_session.text])
            self.assertEqual(saved[0]["notes"], "  private comment  ")
            new_session.button(key="library_open_1").click().run()
            self.assertIn("AI and learning", [h.value for h in new_session.header])
            with patch.object(library.st, "user", IDENTITY | {"sub": "someone-else"}):
                read.reset_mock()
                app.run()
                self.assertFalse(app.exception)
                self.assertFalse(any(r.key == "library_view" for r in app.radio))
                self.assertFalse(app.text_area)
                read.assert_not_called()

    def test_star_from_article_and_remove_from_my_reading(self):
        item = paper(is_favorite=False, reading_status=None, last_updated_at=NOW)

        def public_sql(statement, parameters=()):
            if statement == library.FRESHNESS_SQL:
                return [{"finished_at": NOW}]
            if statement == library.TOPICS_SQL:
                return []
            if statement == library.STATS_SQL:
                return [{"total_papers": 1, "recent_papers": 1, "awaiting_assessment": 0}]
            return [paper()]

        script = "from app.streamlit_app import main\nmain()"
        with (patch.dict(os.environ, {"NOTEBOOK_GOOGLE_SUB": "owner-id"}),
              patch.object(library.st, "user", IDENTITY),
              patch.object(library, "select_rows", side_effect=public_sql),
              patch.object(access, "read_notes", return_value=[]),
              patch.object(access, "read_assessments", return_value=[item]),
              patch.object(access, "feedback_snapshot", return_value=[]),
              patch.object(access, "connections", return_value=[]),
              patch.object(access, "add_favorite", side_effect=lambda _: item.update(is_favorite=True)) as add,
              patch.object(access, "remove_favorite", side_effect=lambda _: item.update(is_favorite=False)) as remove):
            app = AppTest.from_string(script).run()
            app.button(key="notes_1").click().run()
            app.text_area[0].set_value("Unfinished note")
            app.button(key="article_star").click().run()
            self.assertEqual(app.text_area[0].value, "Unfinished note")
            add.assert_called_once_with(1)
            self.assertIn("★ Starred", [item.value for item in app.caption])
            app.radio(key="library_view").set_value("My reading").run()
            app.selectbox(key="notebook_filter").set_value("Starred").run()
            self.assertIn("★ Starred", [item.value for item in app.caption])
            app.button(key="unstar_1").click().run()
            remove.assert_called_once_with(1)
            self.assertTrue(app.info)
            self.assertFalse(app.error)


if __name__ == "__main__":
    unittest.main()
