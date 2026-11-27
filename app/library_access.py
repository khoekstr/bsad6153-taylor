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


def owner_access_issue():
    user = st.user
    owner = os.environ.get("NOTEBOOK_GOOGLE_SUB", "").strip()
    expiry = user.get("exp")
    if user.get("is_logged_in") is not True:
        return "Sign in with the notebook owner's Google account."
    if not owner:
        return "The server needs a notebook owner account configured."
    if user.get("iss") not in ("https://accounts.google.com", "accounts.google.com") or not user.get("sub"):
        return "The app could not confirm a Google identity for this session. Sign out and sign in again."
    if user.get("sub") != owner:
        return "This Google account does not match the configured notebook owner. Sign out to choose another account."
    if not isinstance(expiry, (int, float)) or not expiry > time.time():
        return "Your Google session needs a fresh sign-in. Sign out and sign in again."
    return None


def owner_signed_in():
    return owner_access_issue() is None


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
            SELECT n.note_id, n.work_id, n.deleted_at, n.last_updated_at, n.notes, n.quoted_passage, n.key_references,
                   n.reading_status, n.stopped_reason, coalesce(n.read_at, n.first_seen_at) AS noted_at,
                   w.title, w.source_url, w.doi, w.openalex_id
            FROM public.reading_notes n LEFT JOIN public.works w ON w.work_id = n.work_id
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


def read_assessments():
    with database_connection(notebook=True) as conn:
        return conn.execute("""SELECT a.work_id,a.last_updated_at,a.value_rating,a.value_reason,a.is_favorite,
            a.come_back_to_it,a.reading_status,w.title,w.doi,w.source_url,w.openalex_id
            FROM public.work_assessments a JOIN public.works w USING(work_id)
            WHERE assessed_by='user' ORDER BY a.last_updated_at DESC""").fetchall()


def remove_favorite(work_id):
    with database_connection(notebook=True) as conn:
        conn.execute("""UPDATE public.work_assessments SET is_favorite = false
                        WHERE work_id = %s AND assessed_by = 'user' AND is_favorite""", (work_id,))


def add_favorite(work_id):
    with database_connection(notebook=True) as conn:
        conn.execute("""INSERT INTO public.work_assessments (work_id, assessed_by, is_favorite)
                        VALUES (%s, 'user', true)
                        ON CONFLICT (work_id) WHERE assessed_by = 'user'
                        DO UPDATE SET is_favorite = true
                        WHERE public.work_assessments.is_favorite IS DISTINCT FROM true""", (work_id,))


def set_saved_for_later(work_id, saved):
    with database_connection(notebook=True) as conn:
        conn.execute("""INSERT INTO public.work_assessments (work_id, assessed_by, come_back_to_it)
                        VALUES (%s, 'user', %s)
                        ON CONFLICT (work_id) WHERE assessed_by = 'user'
                        DO UPDATE SET come_back_to_it = EXCLUDED.come_back_to_it""", (work_id, saved))


def save_assessment(work_id, rating, reason, favorite, shortlist, progress):
    if rating is not None and (type(rating) is not int or not 1 <= rating <= 5):
        raise LibraryUnavailable("Choose a rating from 1 to 5.")
    if progress is not None and progress not in PROGRESS:
        raise LibraryUnavailable("Choose a reading status from the list.")
    with database_connection(notebook=True) as conn:
        conn.execute("""INSERT INTO public.work_assessments
            (work_id,assessed_by,value_rating,value_reason,is_favorite,come_back_to_it,reading_status)
            VALUES (%s,'user',%s,%s,%s,%s,%s)
            ON CONFLICT (work_id) WHERE assessed_by='user' DO UPDATE SET
            value_rating=EXCLUDED.value_rating,value_reason=EXCLUDED.value_reason,
            is_favorite=coalesce(EXCLUDED.is_favorite, work_assessments.is_favorite),
            come_back_to_it=coalesce(EXCLUDED.come_back_to_it, work_assessments.come_back_to_it),
            reading_status=EXCLUDED.reading_status""", (work_id,rating,reason,favorite,shortlist,progress))


def revise_note(note_id, expected, note, passage, location, deleted=False):
    with database_connection(notebook=True) as conn:
        result = conn.execute("""UPDATE public.reading_notes SET notes=%s,quoted_passage=%s,
            key_references=%s,deleted_at=CASE WHEN %s THEN now() ELSE NULL END
            WHERE note_id=%s AND last_updated_at=%s RETURNING note_id""",
            (note,passage,location,deleted,note_id,expected)).fetchone()
        if not result:
            raise LibraryUnavailable("This note changed in another session. Reload before editing.")


def note_history(note_id):
    with database_connection(notebook=True) as conn:
        return conn.execute("SELECT snapshot,changed_at FROM public.note_history WHERE note_id=%s ORDER BY revision_id DESC",
                            (note_id,)).fetchall()


def connections(work_id):
    with database_connection(notebook=True) as conn:
        return conn.execute("""SELECT c.connection_type,c.explanation,c.evidence,c.review_basis,
            c.review_status,w.work_id,w.title,w.doi,w.source_url,w.openalex_id
            FROM public.work_connections c JOIN public.works w ON w.work_id=
            CASE WHEN c.from_work_id=%s THEN c.to_work_id ELSE c.from_work_id END
            WHERE (c.from_work_id=%s OR c.to_work_id=%s) AND c.review_status <> 'rejected'
            ORDER BY c.connection_id""", (work_id,work_id,work_id)).fetchall()


def feedback_snapshot(refresh=False):
    from psycopg.types.json import Jsonb
    with database_connection(notebook=True) as conn:
        if refresh:
            feedback = conn.execute("""SELECT a.value_rating,a.value_reason,w.title,
                    (SELECT string_agg(n.notes,' ') FROM public.reading_notes n
                     WHERE n.work_id=a.work_id AND n.deleted_at IS NULL) AS notes
                FROM public.work_assessments a JOIN public.works w USING(work_id)
                WHERE assessed_by='user' AND value_rating IS NOT NULL""").fetchall()
            conn.execute("""INSERT INTO public.recommendation_feedback(singleton,feedback)
                VALUES(true,%s) ON CONFLICT(singleton) DO UPDATE SET
                feedback=EXCLUDED.feedback,updated_at=now()""",(Jsonb(feedback),))
        row=conn.execute('SELECT feedback FROM public.recommendation_feedback WHERE singleton=true').fetchone()
        return row['feedback'] if row else []
