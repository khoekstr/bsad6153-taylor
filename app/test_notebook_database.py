"""Opt-in checks against provisioned web roles; the test entry is rolled back."""
from contextlib import contextmanager
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv
import psycopg

from app import library_access as access, streamlit_app as library


@unittest.skipUnless(os.getenv("TEST_WEB_DATABASE") == "1", "requires the two provisioned web roles")
class WebRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv(library.ROOT / "app" / ".env", override=False)

    def assert_denied(self, conn, statement):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(statement)

    def test_public_reader_grants(self):
        with access.database_connection() as conn:
            # Make the database grants themselves responsible for denying writes.
            conn.rollback()
            conn.read_only = False
            conn.execute(library.STATS_SQL, ("2000-01-01", "2000-01-30")).fetchone()
            self.assert_denied(conn, "SELECT notes FROM public.reading_notes LIMIT 0")
            self.assert_denied(conn, "SELECT assessment_context FROM public.work_assessments LIMIT 0")
            self.assert_denied(conn, "INSERT INTO public.reading_notes (notes) SELECT 'test' WHERE false")

    def test_owner_append_and_retry_without_committing_data(self):
        with patch.object(access, "owner_signed_in", return_value=True):
            with access.database_connection(notebook=True) as conn, conn.transaction(force_rollback=True):
                self.assert_denied(conn, "UPDATE public.work_assessments SET value_rating = 1 WHERE false")
                self.assert_denied(conn, "DELETE FROM public.reading_notes WHERE false")
                work = conn.execute("SELECT work_id FROM public.works ORDER BY work_id LIMIT 1").fetchone()
                self.assertIsNotNone(work, "At least one paper is needed for this test.")
                entry_key = "notebook:" + uuid4().hex

                @contextmanager
                def existing_transaction(*, notebook):
                    self.assertTrue(notebook)
                    yield conn

                with patch.object(access, "database_connection", existing_transaction):
                    for _ in range(2):
                        access.save_note(work["work_id"], entry_key, " test ", "passage", "p. 1", "partial")
                    note_id = conn.execute("SELECT note_id FROM public.reading_notes WHERE import_key = %s",
                                           (entry_key,)).fetchone()["note_id"]
                    entries = access.read_notes(work["work_id"])
                    self.assertTrue(any(n["note_id"] == note_id and n["notes"] == " test " for n in entries))


if __name__ == "__main__":
    unittest.main()
