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
from streamlit.errors import StreamlitMissingAuthlibError
from dotenv import load_dotenv


if __package__:
    from . import library_access as access, owner_workspace
else:  # streamlit run app/streamlit_app.py
    import library_access as access
    import owner_workspace

LibraryUnavailable = access.LibraryUnavailable
ROOT = Path(__file__).resolve().parents[1]

CACHE_TTL_SECONDS = 900
FRESHNESS_LIMIT = timedelta(days=4)
PAGE_SIZE = 10
RECOMMENDATION_MINIMUM = 3
REVIEW_BASIS_LABELS = {
    "metadata": "metadata only", "abstract": "abstract only",
    "excerpt": "excerpt only", "full_text": "full text",
}

# Select public-facing fields explicitly. Private notes, user assessments,
# import paths, raw JSON, and internal assessment context stay out. The
# database's public reader policy excludes works outside the curated AI scope.
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
           source, source_url, doi, openalex_id, abstract, publication_name, is_retracted
    FROM public.works
    JOIN latest_ai USING (work_id)
    WHERE (source = 'openalex' OR (source = 'upload' AND source_url ~* '^https?://'))
      AND latest_ai.summary ~ '[^[:space:]]'
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
SELECT topic, count(*) AS paper_count
FROM (
    SELECT work_id, nullif(btrim(openalex_topic), '') AS topic FROM public_works
) AS topics
WHERE topic IS NOT NULL
GROUP BY topic
ORDER BY lower(topic), topic
"""

ARTICLE_ROWS = PUBLIC_LIBRARY + """
SELECT w.work_id, w.title, w.publication_date, w.first_seen_at,
       w.openalex_topic, w.source, w.source_url, w.doi, w.openalex_id, w.publication_name, w.is_retracted,
       a.value_rating, a.summary, a.value_reason,
       a.relevance_reason, a.review_basis, a.categories,
       count(*) OVER () AS matching_papers
FROM public_works w
LEFT JOIN latest_ai a ON a.work_id = w.work_id
"""

ARTICLE_SQL = ARTICLE_ROWS + "WHERE w.work_id = %s"

FAVORITES_SQL = ARTICLE_ROWS + """
JOIN library_display.favorite_reads f ON f.work_id = w.work_id
ORDER BY f.position
LIMIT 5 OFFSET %s
"""

PAPERS_SQL = ARTICLE_ROWS + """
WHERE (%s = '' OR strpos(
          lower(concat_ws(' ', w.title, w.abstract, a.summary)), lower(%s)
      ) > 0)
  AND (%s::text IS NULL OR btrim(w.openalex_topic) = %s)
  AND (%s::text IS NULL OR %s = ANY(a.categories))
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
    *, search="", topic=None, category=None, start=None, end=None, minimum=None,
    limit=PAGE_SIZE, offset=0,
):
    """Bind every input, including literal keyword searches."""
    parameters = (
        search, search, topic, topic, category, category,
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
        f"Last successful collection update  |  {finished_at:%b %d, %Y at %H:%M} UTC"
        f"  |  {age.total_seconds() / 3600:.1f} hours ago."
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
            except StreamlitMissingAuthlibError:
                st.warning("Owner sign-in needs the Streamlit authentication dependency. "
                           "Install the project's requirements in the app's Python environment and restart Streamlit.")
            except Exception:
                st.warning("Google sign-in is unavailable. You can still browse the collection.")
        return
    if not access.owner_signed_in():
        st.warning(access.owner_access_issue())
        if not os.environ.get("NOTEBOOK_GOOGLE_SUB") and st.user.get("sub"):
            with st.expander("Set up owner access"):
                st.caption("Your signed-in Google account ID for the server's owner setting")
                st.text(str(st.user["sub"]))
    if st.button("Sign out", key="google_logout"):
        st.logout()


def open_paper_notebook(paper):
    # A public visitor's selection contains only the public article ID.
    fields = ("work_id", "title", "doi", "source_url", "openalex_id") if access.owner_signed_in() else ("work_id",)
    st.session_state["notebook_paper"] = {field: paper[field] for field in fields}


def note_form(work_id, *, favorite=None):
    key = f"notebook_entry_{work_id}"
    if key not in st.session_state:
        st.session_state[key] = uuid4().hex
    entry_id = st.session_state[key]
    with st.form(f"notebook_form_{work_id}_{entry_id}"):
        note = st.text_area("Add a note", placeholder="What stood out to you?")
        with st.expander("Add a quote or reference (optional)"):
            passage = st.text_area("Quoted passage", placeholder="Paste the author's exact words.")
            location = st.text_input("Passage location or reference", placeholder="Page, section, or timestamp")
        submitted = st.form_submit_button("Save note", type="primary")
        if favorite is not None and st.form_submit_button(
            "\u2605 Remove favorite" if favorite else "\u2606 Add article to favorites",
            key="article_star", help="Eligible starred articles appear in Kara's favorite reads.",
        ):
            if favorite:
                access.remove_favorite(work_id)
            else:
                access.add_favorite(work_id)
            st.rerun()
    if submitted:
        retry_key = f"notebook_request_{entry_id}"
        try:
            access.save_note(work_id, st.session_state.get(retry_key, "notebook:" + entry_id),
                             note, passage, location, None)
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


def rank_with_feedback(papers, feedback):
    """Stable, explainable keyword matching; explicit saved feedback only."""
    stop = {'about','their','these','those','which','would','could','should','research','study','paper','article'}
    def words(text):
        return set(re.findall(r"[a-z]{4,}",text.lower())) - stop
    weights = {}
    for item in feedback:
        weight = (item.get('value_rating') or 3) - 3
        for word in words((item.get('title') or '')+' '+(item.get('value_reason') or '')+' '+(item.get('notes') or '')):
            weights[word] = weights.get(word,0) + weight
    def score(paper):
        tokens=words(paper['title']+' '+(paper.get('summary') or ''))
        return sum(weights.get(word,0) for word in tokens)
    return sorted(papers,key=score,reverse=True)


def reset_discover_page():
    st.session_state["discover_offset"] = 0
    st.session_state.pop("discover_recent_return", None)


def continue_with_older():
    st.session_state["discover_recent_return"] = st.session_state.get("discover_offset", 0)
    st.session_state["discover_scope"] = "Older than 30 days"
    st.session_state["discover_offset"] = 0


def return_to_recent():
    st.session_state["discover_scope"] = "Last 30 days"
    st.session_state["discover_offset"] = st.session_state.pop("discover_recent_return", 0)


def move_discover_page(amount):
    st.session_state["discover_offset"] = max(0, st.session_state.get("discover_offset", 0) + amount)


def favorite_reads():
    st.header("Kara's favorite reads")
    st.caption("Handpicked by Kara. Most recently starred first.")
    page = st.session_state.get("favorite_page", 1)
    # Read membership fresh so removing a star takes effect on the next visit.
    with reader_connection() as conn:
        papers = conn.execute(FAVORITES_SQL, ((page - 1) * 5,)).fetchall()
    if not papers:
        if page > 1:
            st.session_state["favorite_page"] = 1
            st.rerun()
        st.info("There are no public favorites yet.")
        return
    total = papers[0]["matching_papers"]
    st.caption(f"Showing {(page - 1) * 5 + 1}–{(page - 1) * 5 + len(papers)} of {total}")
    if total > 5:
        previous, following = st.columns(2)
        previous.button("Previous five", disabled=page == 1, key="previous_favorites",
                        on_click=st.session_state.update, args=({"favorite_page": page - 1},))
        following.button("Next five", disabled=page * 5 >= total, key="next_favorites",
                         on_click=st.session_state.update, args=({"favorite_page": page + 1},))
    for paper in papers:
        public_article_card(paper)


def discover_view(today):
    st.header("Worth reading next")
    scope = st.selectbox("Publication window", ["Last 30 days", "Older than 30 days", "Any publication date"],
                         key="discover_scope", on_change=reset_discover_page)
    recent = scope == "Last 30 days"
    owner = access.owner_signed_in()
    hide_finished = False
    feedback = []
    if owner:
        hide_finished = st.session_state.get("discover_hide_finished", True)
        feedback = access.feedback_snapshot()
        if st.session_state.pop("notebook_feedback_updated", False):
            st.success("Recommendations updated from your feedback.")
    offset = st.session_state.get("discover_offset", 0)
    st.button("Reset", key="reset_recommendations", disabled=offset == 0,
              help="Return to the first recommendations in the selected publication window.",
              on_click=st.session_state.update, args=({"discover_offset": 0},))
    start = today - timedelta(days=29) if recent else None
    end = today if recent else None
    if scope == "Older than 30 days":
        end = today - timedelta(days=30)
    if owner:
        candidates = []
        batch_offset = 0
        while True:
            batch = fetch_papers(start=start, end=end, minimum=RECOMMENDATION_MINIMUM,
                                 limit=100, offset=batch_offset)
            candidates.extend(batch)
            if len(batch) < 100: break
            batch_offset += 100
        assessments = access.read_assessments()
        assessment_times = {r["work_id"]: r["last_updated_at"] for r in assessments if r["reading_status"]}
        finished = {r["work_id"] for r in assessments if r["reading_status"] == "complete"}
        latest_progress = {}
        for note in access.read_notes():
            if (not note["deleted_at"] and note["reading_status"]
                    and (note["work_id"] not in assessment_times or note["noted_at"] > assessment_times[note["work_id"]])):
                latest_progress.setdefault(note["work_id"], note["reading_status"])
        finished.difference_update(latest_progress)
        finished.update(k for k,v in latest_progress.items() if v == "complete")
        if hide_finished: candidates = [p for p in candidates if p["work_id"] not in finished]
        candidates = rank_with_feedback(candidates, feedback)
        papers = candidates[offset:offset+5]
        for p in papers: p["matching_papers"] = len(candidates)
    else:
        papers = fetch_papers(start=start, end=end, minimum=RECOMMENDATION_MINIMUM,
                              limit=5, offset=offset)
    if papers:
        total = papers[0]["matching_papers"]
        st.caption(f"Showing {offset + 1}–{offset + len(papers)} of {total} recommendations")
        previous, following = st.columns(2)
        if offset == 0 and "discover_recent_return" in st.session_state:
            previous.button("Previous five", on_click=return_to_recent)
        else:
            previous.button("Previous five", disabled=offset == 0, on_click=move_discover_page, args=(-5,))
        at_end = offset + len(papers) >= total
        if recent and at_end:
            following.button("Five more recommendations", on_click=continue_with_older)
            st.caption("You've reached the last recent match. Five more recommendations will look for older articles.")
        else:
            following.button("Five more recommendations", disabled=at_end,
                             on_click=move_discover_page, args=(5,))
        for paper in papers:
            public_article_card(paper)
    elif offset:
        st.info("There are no more recommendations on this page.")
    else:
        message = ("No recommendations match your settings for the last 30 days. Try Any publication date."
                   if recent else "No recommendations match your settings.")
        st.info(message)
        if recent:
            st.button("Look for older recommendations", on_click=continue_with_older)
    if owner:
        with st.expander("Recommendation settings"):
            st.checkbox("Exclude finished articles", value=True, key="discover_hide_finished",
                        on_change=reset_discover_page)
            st.caption("Use your saved notes and ratings to change which articles appear first.")
            if st.button("Update recommendations from my feedback"):
                access.feedback_snapshot(refresh=True)
                reset_discover_page()
                st.session_state["notebook_feedback_updated"] = True
                st.rerun()


def public_article_card(paper):
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
            st.button("My notes and reading details", key=f"notes_{paper['work_id']}",
                      on_click=open_paper_notebook, args=(paper,))


def reset_public_page():
    st.session_state["public_explore_page"] = 1


def public_explore_view():
    st.header("Explore the collection")
    st.caption("Follow an interest, revisit older research, or try an unfamiliar topic.")
    topics = select_rows(TOPICS_SQL)
    topic_counts = {row["topic"]: row["paper_count"] for row in topics}
    with st.container(border=True):
        search = st.text_input(
            "Search papers", placeholder="Search titles, abstracts, and AI summaries",
            max_chars=200, key="public_explore_search", on_change=reset_public_page,
        ).strip()
        category = None
        if access.owner_signed_in():
            category = st.selectbox(
                "Main category", [None, "Learning", "Work", "Information", "Society", "Technology", "Discovery"],
                format_func=lambda value: value or "All categories",
                key="public_explore_category", on_change=reset_public_page,
                help="Filter by a broad category assigned in the AI assessment.",
            )
        topic_column, score_column = st.columns(2)
        with topic_column:
            topic = st.selectbox(
                "Topic", [None] + list(topic_counts),
                format_func=lambda value: "All topics" if value is None else f"{value} ({topic_counts[value]})",
                key="public_explore_topic", on_change=reset_public_page,
                help="Filter by the OpenAlex topic assigned to the paper.",
            )
        with score_column:
            minimum = st.selectbox(
                "Minimum AI interest", [None, 1, 2, 3, 4, 5],
                format_func=lambda value: "Any score, including unknown" if value is None else f"{value}/5",
                key="public_explore_minimum", on_change=reset_public_page,
            )
        dates = st.date_input(
            "Publication date range (optional)", value=(), format="MM/DD/YYYY",
            key="public_explore_dates", on_change=reset_public_page,
            help="Leave empty to include unknown dates. Select both start and end dates to filter.",
        )
    if len(dates) == 1:
        st.info("Choose an end date to apply the publication date range.")
        return
    start, end = dates if dates else (None, None)
    page = st.session_state.get("public_explore_page", 1)
    papers = fetch_papers(
        search=search, topic=topic, category=category, start=start, end=end, minimum=minimum,
        offset=(page - 1) * PAGE_SIZE,
    )
    if not papers and page > 1:
        st.session_state["public_explore_page"] = 1
        st.rerun()
    if not papers:
        st.info("No papers match these filters. Try a broader topic, date range, or interest score.")
        return
    total = papers[0]["matching_papers"]
    st.caption(f"{total:,} matching papers · Ranked by predicted interest, then publication date")
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages > 1:
        st.number_input("Page", min_value=1, max_value=total_pages, step=1, key="public_explore_page")
    for paper in papers:
        public_article_card(paper)


def public_discover_view(today):
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
        public_article_card(paper)


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
    st.set_page_config(page_title="AI Research Discovery", page_icon=":books:", layout="wide")
    owner = access.owner_signed_in()
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
    views = ["Discover", "Explore", "Kara's favorite reads"]
    if owner:
        views.append("My reading")
    else:
        for key in list(st.session_state):
            if key.startswith("notebook_") or key == "library_view":
                del st.session_state[key]
    view_key = "library_view" if owner else "public_view"
    if st.session_state.get(view_key) not in views:
        st.session_state[view_key] = "Discover"
    view = st.radio("Browse research", views, horizontal=True, key=view_key,
                    on_change=lambda: st.session_state.pop("notebook_paper", None))

    # Keep filters selected when the article page temporarily hides their widgets.
    for key in list(st.session_state):
        if key.startswith(("public_explore_", "discover_")) or key in ("notebook_filter", "notebook_search"):
            st.session_state[key] = st.session_state[key]
    paper = st.session_state.get("notebook_paper")
    if paper or view == "My reading":
        try:
            import sys
            library = sys.modules[__name__]
            if paper:
                owner_workspace.article_page(library, paper, owner)
            else:
                owner_workspace.workspace(library)
        except LibraryUnavailable as error:
            st.error(str(error))
        except Exception:
            st.error("This page could not be loaded. Please try again.")
        return
    today = datetime.now(timezone.utc).date()
    try:
        stats = select_rows(STATS_SQL, (today - timedelta(days=29), today))[0]
        st.caption(
            f"{stats['total_papers']:,} papers in the public collection  |  "
            f"{stats['recent_papers']:,} published in 30 days  |  "
            f"{stats['awaiting_assessment']:,} awaiting an AI interest score"
        )
        if view == "Explore":
            public_explore_view()
        elif view == "Kara's favorite reads":
            favorite_reads()
        elif owner:
            discover_view(today)
        else:
            public_discover_view(today)
    except LibraryUnavailable as error:
        st.error(str(error))
    except Exception:
        st.error("This research view could not be loaded. Please try again shortly.")
    about_section()


if __name__ == "__main__":
    main()
