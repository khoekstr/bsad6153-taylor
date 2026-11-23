"""Research discovery library with a Google-authenticated owner notebook. Run with Streamlit from the repository root."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from uuid import uuid4
import streamlit as st
from dotenv import load_dotenv


if __package__:
    from . import library_access as access
else:  # streamlit run app/streamlit_app.py
    import library_access as access

LibraryUnavailable = access.LibraryUnavailable
ROOT = Path(__file__).resolve().parents[1]
CACHE_TTL_SECONDS = 900
FRESHNESS_LIMIT = timedelta(days=4)
PAGE_SIZE = 10

# Select public-facing fields explicitly. Private notes, user assessments,
# import paths, raw JSON, and internal assessment context stay out.
PUBLIC_LIBRARY = """
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id)
        work_id, value_rating, summary, value_reason, relevance_reason,
        review_basis, categories
    FROM public.work_assessments
    WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
), public_works AS (
    SELECT work_id, title, publication_date, first_seen_at, openalex_topic,
           source, source_url, doi, openalex_id, abstract
    FROM public.works
    WHERE source = 'openalex'
       OR (source = 'upload' AND source_url ~* '^https?://')
)
"""

STATS_SQL = PUBLIC_LIBRARY + """
SELECT count(*) AS total_papers,
       count(*) FILTER (
           WHERE w.publication_date BETWEEN %s AND %s
       ) AS recent_papers,
       count(*) FILTER (WHERE a.value_rating IS NULL) AS awaiting_assessment
FROM public_works w
LEFT JOIN latest_ai a ON a.work_id = w.work_id
"""

TOPICS_SQL = PUBLIC_LIBRARY + """
SELECT topic, count(DISTINCT work_id) AS paper_count
FROM (
    SELECT work_id, nullif(btrim(openalex_topic), '') AS topic FROM public_works
    UNION
    SELECT w.work_id, unnest(a.categories) AS topic
    FROM public_works w JOIN latest_ai a ON a.work_id = w.work_id
) AS topics
WHERE topic IS NOT NULL
GROUP BY topic
ORDER BY lower(topic), topic
"""

PAPERS_SQL = PUBLIC_LIBRARY + """
SELECT w.work_id, w.title, w.publication_date, w.first_seen_at,
       w.openalex_topic, w.source, w.source_url, w.doi, w.openalex_id,
       a.value_rating, a.summary, a.value_reason,
       a.relevance_reason, a.review_basis, a.categories,
       count(*) OVER () AS matching_papers
FROM public_works w
LEFT JOIN latest_ai a ON a.work_id = w.work_id
WHERE (%s = '' OR strpos(
          lower(concat_ws(' ', w.title, w.abstract, a.summary)), lower(%s)
      ) > 0)
  AND (%s::text IS NULL OR w.openalex_topic = %s
       OR %s = ANY(coalesce(a.categories, ARRAY[]::text[])))
  AND (%s::date IS NULL OR w.publication_date >= %s)
  AND (%s::date IS NULL OR w.publication_date <= %s)
  AND (%s::integer IS NULL OR a.value_rating >= %s)
ORDER BY a.value_rating DESC NULLS LAST,
         w.publication_date DESC NULLS LAST, w.work_id
LIMIT %s OFFSET %s
"""

# Match db/sync_status.sql. Previews, skips, and targeted maintenance cannot
# make the last successful collection discovery look more recent.
FRESHNESS_SQL = """
SELECT max(finished_at) AS finished_at
FROM public.sync_runs
WHERE status = %s AND NOT dry_run AND mode = %s AND outcome = %s
  AND finished_at IS NOT NULL
"""


def reader_connection():
    return access.database_connection()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_select(statement, parameters, connection_identity):
    """Cache successful public results and separate connection configurations."""
    with reader_connection() as conn:
        return conn.execute(statement, parameters).fetchall()


def select_rows(statement, parameters=()):
    url = os.environ.get("APP_DATABASE_URL", "")
    if not url:
        raise LibraryUnavailable("The research library is not connected yet.")
    return cached_select(statement, parameters, sha256(url.encode()).hexdigest())


def fetch_papers(
    *, search="", topic=None, start=None, end=None, minimum=None,
    limit=PAGE_SIZE, offset=0,
):
    """Bind every input, including literal keyword searches."""
    parameters = (
        search, search, topic, topic, topic,
        start, start, end, end, minimum, minimum, limit, offset,
    )
    return select_rows(PAPERS_SQL, parameters)


def freshness_state(finished_at, now):
    """Recalculate age at render time so a cached timestamp cannot freeze warnings."""
    if finished_at is None:
        return "warning", "A successful collection update cannot be confirmed yet."
    if finished_at.tzinfo is None or finished_at > now:
        return "warning", "The update time could not be confirmed. Freshness is unknown."
    age = now - finished_at
    message = (
        f"Last successful collection update · {finished_at:%b %d, %Y at %H:%M} UTC"
        f" · {age.total_seconds() / 3600:.1f} hours ago."
    )
    if age > FRESHNESS_LIMIT:
        return "warning", "Collection updates are overdue. " + message
    return "success", message


def freshness_banner():
    try:
        finished_at = select_rows(
            FRESHNESS_SQL, ("success", "discovery_only", "completed")
        )[0]["finished_at"]
        level, message = freshness_state(finished_at, datetime.now(timezone.utc))
    except Exception:
        level = "warning"
        message = "Update history is unavailable. Freshness cannot be confirmed."
    getattr(st, level)(message)


def markdown_text(value):
    """Display source content literally, including Markdown-like source text."""
    return re.sub(r"([\\\x60*_{}\[\]()#+.!|<>~\-])", r"\\\1", str(value))


def external_url(value):
    """Allow web links without embedded credentials or local targets."""
    if not value or re.search(r"[\s\x00-\x1f\x7f]", value):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in ("https", "http") or not host:
            return None
        if parsed.username or parsed.password or host == "localhost" or host.endswith(".local"):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        return value
    except ValueError:
        return None


def article_card(paper):
    with st.container(border=True):
        st.subheader(markdown_text(paper["title"]))
        published = paper["publication_date"]
        added = paper["first_seen_at"]
        published_label = published.strftime("%b %d, %Y") if published else "Unknown"
        added_label = added.strftime("%b %d, %Y") if added else "Unknown"
        st.caption(f"Published {published_label} · Added to collection {added_label}")
        topic = paper["openalex_topic"] or ", ".join(paper["categories"] or [])
        st.caption(markdown_text(topic or "Topic unavailable"))

        rating = paper["value_rating"]
        basis_labels = {
            "metadata": "metadata only", "abstract": "abstract only",
            "excerpt": "excerpt only", "full_text": "full text",
        }
        basis = basis_labels.get(paper["review_basis"], "basis unavailable")
        if rating is None:
            st.caption("AI interest score unavailable · Interest is unknown")
        else:
            st.caption(f"AI-predicted interest for Kara · {rating}/5 · Based on {basis}")

        summary = paper["summary"]
        if summary:
            st.markdown("**AI summary**")
            st.markdown(markdown_text(summary))
            if rating is None:
                st.caption("Summary assessment basis · " + basis)
        else:
            st.caption("No AI summary yet. Follow the source link to read the original.")

        reason = paper["relevance_reason"] or paper["value_reason"]
        if reason:
            st.markdown("**Why it might interest me**")
            st.markdown(markdown_text(reason))
        elif rating is not None:
            st.caption("A recommendation explanation is unavailable.")

        with st.expander("Source details"):
            source_name = "OpenAlex" if paper["source"] == "openalex" else "Manually added reference"
            st.caption("Source · " + source_name)
            if paper["doi"]:
                st.markdown(markdown_text("DOI · " + paper["doi"]))
            if paper["openalex_id"]:
                st.markdown(markdown_text(paper["openalex_id"]))

        source_link = paper_link(paper)
        if source_link:
            st.link_button("Open original source", source_link, key=f"source_{paper['work_id']}")
        catalog_link = external_url(paper["openalex_id"])
        if catalog_link:
            st.link_button("View OpenAlex record", catalog_link, key=f"catalog_{paper['work_id']}")
        if not source_link and not catalog_link:
            st.caption("An accessible source link is unavailable.")
        if access.owner_signed_in():
            st.button("My notes", key=f"notes_{paper['work_id']}",
                      on_click=open_paper_notebook, args=(paper,))


def paper_link(paper):
    doi = paper["doi"]
    if doi and doi.lower().startswith("10."):
        doi = "https://doi.org/" + doi
    return external_url(doi) or external_url(paper["source_url"])


def account_controls():
    if not st.user.get("is_logged_in"):
        if st.button("Owner sign in", key="google_login", help="Kara uses Google to access her private notebook. Visitors can browse without signing in."):
            try:
                st.login()
            except Exception:
                st.warning("Google sign-in is unavailable. You can still browse the collection.")
        return
    if not access.owner_signed_in():
        st.caption("This session has public access. The notebook is reserved for its owner.")
        if not os.environ.get("NOTEBOOK_GOOGLE_SUB") and st.user.get("sub"):
            with st.expander("Set up owner access"):
                st.caption("Your signed-in Google account ID for the server's owner setting")
                st.text(str(st.user["sub"]))
    if st.button("Sign out", key="google_logout"):
        st.logout()


def open_paper_notebook(paper):
    if access.owner_signed_in():
        st.session_state["notebook_paper"] = {
            field: paper[field] for field in ("work_id", "title", "doi", "source_url", "openalex_id")
        }
        st.session_state["library_view"] = "My notes"


def note_form(work_id):
    key = f"notebook_entry_{work_id}"
    if key not in st.session_state:
        st.session_state[key] = uuid4().hex
    entry_id = st.session_state[key]
    with st.form(f"notebook_form_{work_id}_{entry_id}"):
        note = st.text_area("My thoughts", placeholder="What stood out to you?")
        passage = st.text_area("Quoted passage (optional)", placeholder="Paste the author's exact words.")
        location = st.text_input("Passage location or reference (optional)", placeholder="Page, section, or timestamp")
        progress = st.selectbox("Reading progress (optional)", [None, *access.PROGRESS],
                                format_func=lambda value: access.PROGRESS.get(value, "Choose if useful"))
        submitted = st.form_submit_button("Save note", type="primary")
    if submitted:
        retry_key = f"notebook_request_{entry_id}"
        try:
            access.save_note(work_id, st.session_state.get(retry_key, "notebook:" + entry_id),
                             note, passage, location, progress)
        except access.EarlierSave as error:
            st.session_state[retry_key] = "notebook:" + uuid4().hex
            st.warning(str(error))
        except LibraryUnavailable as error:
            st.error(str(error))
        else:
            st.session_state.pop(key)
            st.session_state.pop(retry_key, None)
            st.session_state["notebook_saved"] = True
            st.rerun()


def notebook_view():
    st.header("My notes")
    paper = st.session_state.get("notebook_paper")
    if st.session_state.pop("notebook_saved", False):
        st.success("Saved to your private notebook.")
    if paper:
        st.button("All notebook entries", on_click=st.session_state.pop, args=("notebook_paper",))
        st.subheader(markdown_text(paper["title"]))
        link = paper_link(paper) or external_url(paper["openalex_id"])
        if link:
            st.link_button("Read paper", link)
        note_form(paper["work_id"])
    else:
        st.caption("Open My notes on a paper in Discover or Explore to add an entry.")

    rows = access.read_notes(paper["work_id"] if paper else None)
    if not rows:
        st.info("Your notes for this paper will appear here." if paper else "Your notebook has no entries yet.")
    for row in rows:
        with st.container(border=True):
            if not paper:
                st.button(markdown_text(row["title"]), key=f"notebook_open_{row['note_id']}",
                          on_click=open_paper_notebook, args=(row,))
            st.caption(row["noted_at"].astimezone(timezone.utc).strftime("%b %d, %Y at %H:%M UTC"))
            if row["notes"]:
                st.text(row["notes"])
            if row["quoted_passage"]:
                st.markdown("**Quoted passage**")
                st.text(row["quoted_passage"])
            if row["key_references"]:
                st.caption("Location or reference")
                st.text(row["key_references"])
            if row["reading_status"]:
                st.caption(access.PROGRESS.get(row["reading_status"], row["reading_status"]))
            if row["stopped_reason"]:
                st.text(row["stopped_reason"])


def reset_explore_page():
    st.session_state["explore_page"] = 1


def explore_view():
    st.header("Explore the collection")
    st.caption("Follow an interest, revisit older research, or try an unfamiliar topic.")
    topics = select_rows(TOPICS_SQL)
    topic_counts = {row["topic"]: row["paper_count"] for row in topics}
    with st.container(border=True):
        search = st.text_input(
            "Search papers", placeholder="Search titles, abstracts, and AI summaries",
            max_chars=200, key="explore_search", on_change=reset_explore_page,
        ).strip()
        topic_column, score_column = st.columns(2)
        with topic_column:
            topic = st.selectbox(
                "Topic", [None] + list(topic_counts),
                format_func=lambda value: "All topics" if value is None else f"{value} ({topic_counts[value]})",
                key="explore_topic", on_change=reset_explore_page,
                help="Includes OpenAlex topics and AI-suggested categories. A paper can have several topics.",
            )
        with score_column:
            minimum = st.selectbox(
                "Minimum AI interest", [None, 1, 2, 3, 4, 5],
                format_func=lambda value: "Any score, including unknown" if value is None else f"{value}/5",
                key="explore_minimum", on_change=reset_explore_page,
            )
        dates = st.date_input(
            "Publication date range (optional)", value=(), format="MM/DD/YYYY",
            key="explore_dates", on_change=reset_explore_page,
            help="Leave empty to include unknown dates. Select both start and end dates to filter.",
        )
    if len(dates) == 1:
        st.info("Choose an end date to apply the publication date range.")
        return
    start, end = dates if dates else (None, None)
    page = st.session_state.get("explore_page", 1)
    papers = fetch_papers(
        search=search, topic=topic, start=start, end=end, minimum=minimum,
        offset=(page - 1) * PAGE_SIZE,
    )
    if not papers and page > 1:
        st.session_state["explore_page"] = 1
        st.rerun()
    if not papers:
        st.info("No papers match these filters. Try a broader topic, date range, or interest score.")
        return
    total = papers[0]["matching_papers"]
    st.caption(f"{total:,} matching papers · Ranked by predicted interest, then publication date")
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages > 1:
        st.number_input("Page", min_value=1, max_value=total_pages, step=1, key="explore_page")
    for paper in papers:
        article_card(paper)


def discover_view(today):
    st.header("Worth reading next")
    st.caption("Up to five recommendations · Published in the last 30 days · Tailored to Kara's interests")
    papers = fetch_papers(start=today - timedelta(days=29), end=today, minimum=1, limit=5)
    if not papers:
        st.info(
            "There are no assessed recommendations from the last 30 days yet. "
            "Explore includes older papers and new arrivals awaiting assessment."
        )
        return
    for paper in papers:
        article_card(paper)


def about_section():
    with st.expander("About this research library"):
        st.write(
            "AI Research Discovery is Kara Taylor's student project for BSAD 6153 at Newman University. "
            "It brings together research records from OpenAlex and references Kara collected separately."
        )
        st.link_button("Learn about OpenAlex", "https://openalex.org/")
        st.link_button("Privacy policy", "https://karataylor.live/?page=privacy")
        st.write(
            "AI summaries describe the material named on each card. Scores estimate how interesting "
            "a paper might be to Kara. Follow the source link to read the authors' own work."
        )
        st.write(
            "The collection checks for new papers on Mondays and Thursdays at 8:15 a.m. Central. "
            "The banner shows the last successful check and warns after four days. "
            "Individual records and AI assessments can be older."
        )
        st.caption(
            "Public data results are cached for up to 15 minutes. On Render's free tier, "
            "the first visit after inactivity can take about a minute to wake the site."
        )


def main():
    load_dotenv(ROOT / "app" / ".env", override=False)
    st.set_page_config(page_title="AI Research Discovery", page_icon="📖", layout="wide")
    st.html("""
        <style>
        .stApp { background: #faf9f6; color: #23332e; }
        .block-container { max-width: 1060px; padding-top: 2rem; }
        h1, h2, h3 { font-family: 'Source Sans 3', sans-serif; }
        h1 { letter-spacing: -.035em; }
        h3 { font-size: 1.3rem !important; line-height: 1.4 !important; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px; background: #ffffff;
        }
        [data-testid="stLinkButton"] a { border-color: #59766b; }
        </style>
    """)
    st.title("AI Research Discovery")
    if st.query_params.get("page") == "privacy":
        st.markdown((ROOT / "app" / "privacy.md").read_text(encoding="utf-8"))
        st.link_button("Back to research library", "https://karataylor.live/")
        return
    freshness_banner()
    account_controls()
    views = ["Discover", "Explore"]
    if access.owner_signed_in():
        views.append("My notes")
    else:
        for key in list(st.session_state):
            if key.startswith("notebook_"):
                del st.session_state[key]
        if st.session_state.get("library_view") == "My notes":
            st.session_state["library_view"] = "Discover"
    view = st.radio("Browse research", views, horizontal=True, key="library_view")
    if view == "My notes":
        try:
            notebook_view()
        except LibraryUnavailable as error:
            st.error(str(error))
        except Exception:
            st.error("Your notebook could not be loaded. Please try again.")
        return
    today = datetime.now(timezone.utc).date()
    try:
        stats = select_rows(STATS_SQL, (today - timedelta(days=29), today))[0]
        st.caption(
            f"{stats['total_papers']:,} papers in the public collection · "
            f"{stats['recent_papers']:,} published in 30 days · "
            f"{stats['awaiting_assessment']:,} awaiting an AI interest score"
        )
        if view == "Discover":
            discover_view(today)
        else:
            explore_view()
    except LibraryUnavailable as error:
        st.error(str(error))
    except Exception:
        st.error("This research view could not be loaded. Please try again shortly.")
    about_section()


if __name__ == "__main__":
    main()
