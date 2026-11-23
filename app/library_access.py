"""Server-side database connections and single-owner notebook operations."""

from contextlib import contextmanager
import os
import time

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import streamlit as st


class LibraryUnavailable(Exception):
    """Only user-safe messages may be displayed."""


def owner_signed_in():
    user = st.user
    owner = os.environ.get("NOTEBOOK_GOOGLE_SUB", "").strip()
    expiry = user.get("exp")
    return bool(
        owner and user.get("is_logged_in") is True
        and user.get("iss") in ("https://accounts.google.com", "accounts.google.com")
        and user.get("sub") == owner
        and isinstance(expiry, (int, float)) and expiry > time.time()
    )


@contextmanager
def database_connection(*, notebook=False):
    if notebook:
        if not owner_signed_in():
            raise LibraryUnavailable("Please sign in with the notebook owner's Google account.")
        env_key, role, label = "NOTEBOOK_DATABASE_URL", "library_notebook", "notebook"
    else:
        env_key, role, label = "APP_DATABASE_URL", "library_web_reader", "research library"

    url = os.environ.get(env_key)
    if not url:
        raise LibraryUnavailable(f"The {label} is not connected yet.")
    try:
        if conninfo_to_dict(url).get("user", "").split(".", 1)[0] != role:
            raise LibraryUnavailable(f"The {label} connection needs attention.")
        with psycopg.connect(
            url, connect_timeout=10, options="-c statement_timeout=10000",
            row_factory=dict_row,
        ) as conn:
            conn.read_only = not notebook
            identity = conn.execute("SELECT current_user AS role, session_user AS login").fetchone()
            if identity["role"] != role or identity["login"] != role:
                raise LibraryUnavailable(f"The {label} connection needs attention.")
            yield conn
    except psycopg.Error:
        raise LibraryUnavailable(f"The {label} is temporarily unavailable. Please try again.") from None


def read_notes(work_id=None):
    with database_connection(notebook=True) as conn:
        return conn.execute("""
            SELECT n.note_id, n.work_id, n.notes, n.quoted_passage, n.key_references,
                   n.reading_status, n.stopped_reason, coalesce(n.read_at, n.first_seen_at) AS noted_at,
                   w.title, w.source_url, w.doi, w.openalex_id
            FROM public.reading_notes n JOIN public.works w ON w.work_id = n.work_id
            WHERE (%s::bigint IS NULL OR n.work_id = %s)
            ORDER BY noted_at DESC, n.note_id DESC
        """, (work_id, work_id)).fetchall()


PROGRESS = {
    "not_started": "Not started", "abstract_only": "Read the abstract",
    "partial": "Partway through", "complete": "Finished",
}


def save_note(work_id, entry_key, note, passage, location, progress):
    """Append verbatim text. The same form submission can safely be retried."""
    def optional(text):
        return text if text.strip() else None

    values = (work_id, optional(note), optional(passage), optional(location), progress)
    if not (values[1] or values[2] or progress):
        raise LibraryUnavailable("Add a thought, paste a passage, or choose your reading progress.")
    if progress is not None and progress not in PROGRESS:
        raise LibraryUnavailable("Choose a reading progress option from the list.")
    with database_connection(notebook=True) as conn:
        inserted = conn.execute("""
            INSERT INTO public.reading_notes
                (work_id, notes, quoted_passage, key_references, reading_status, import_key, read_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (import_key) DO NOTHING RETURNING note_id
        """, (*values, entry_key)).fetchone()
        if inserted is None:
            previous = conn.execute("""
                SELECT work_id, notes, quoted_passage, key_references, reading_status
                FROM public.reading_notes WHERE import_key = %s
            """, (entry_key,)).fetchone()
            if previous is None or tuple(previous.values()) != values:
                raise EarlierSave("An earlier version was saved. Your current draft is here. "
                                  "Choose Save note again to add it as a separate entry.")


class EarlierSave(LibraryUnavailable):
    """A previous submission committed before the client received confirmation."""
