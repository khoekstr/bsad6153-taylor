"""Private article workspace; all persistence uses the authenticated owner role."""
import json
import streamlit as st
if __package__:
    from . import library_access as access
else:
    import library_access as access


def reading_details(work_id, current):
    st.subheader("Reading details")
    key = f"notebook_later_{work_id}"
    saved = bool(current.get("come_back_to_it"))

    def update_saved():
        selected = st.session_state[key]
        try:
            access.set_saved_for_later(work_id, selected)
        except access.LibraryUnavailable as error:
            st.session_state[key] = saved
            st.error(str(error))
        else:
            st.success("Saved for later." if selected else "Removed from Saved for later.")

    st.checkbox("Save for later", value=saved, key=key, on_change=update_saved,
                help="Changes save immediately in My reading → Saved for later.")
    with st.form(f"assessment_{work_id}"):
        statuses = [None, *access.PROGRESS]
        progress = st.selectbox(
            "Reading status", statuses, index=statuses.index(current.get("reading_status")),
            format_func=lambda value: access.PROGRESS.get(value, "Choose a status"),
        )
        ratings = [None, 1, 2, 3, 4, 5]
        rating = st.selectbox("My interest rating", ratings, index=ratings.index(current.get("value_rating")),
                             format_func=lambda value: f"{value}/5" if value else "Not rated",
                             help="Your private rating of how interesting you found this article.")
        reason = st.text_area("Why this interests me (optional)", value=current.get("value_reason") or "")
        if st.form_submit_button("Save reading details"):
            access.save_assessment(work_id, rating, reason, None, None, progress)
            st.success("Reading details saved.")


def edit_note(row):
    with st.expander('Edit, history and recovery'):
        with st.form(f"edit_{row['note_id']}"):
            note=st.text_area('Note',value=row['notes'] or '')
            quote=st.text_area('Quote',value=row['quoted_passage'] or '')
            location=st.text_input('Reference',value=row['key_references'] or '')
            save=st.form_submit_button('Save edited note')
            delete=st.form_submit_button('Move to trash')
            if save or delete:
                access.revise_note(row['note_id'],row['last_updated_at'],note,quote,location,delete)
                st.rerun()
        for i,revision in enumerate(access.note_history(row['note_id'])):
            old=revision['snapshot']
            st.caption(str(revision['changed_at']))
            st.text(old.get('notes') or old.get('quoted_passage') or 'Progress entry')
            if st.button('Restore this version',key=f"restore_{row['note_id']}_{i}"):
                access.revise_note(row['note_id'],row['last_updated_at'],old.get('notes') or '',
                                   old.get('quoted_passage') or '',old.get('key_references') or '')
                st.rerun()


def show_note(row):
    with st.container(border=True):
        st.caption(row["noted_at"].strftime("%b %d, %Y"))
        if row["notes"]:
            st.text(row["notes"])
        if row["quoted_passage"]:
            st.markdown("**Saved quote**")
            st.text(row["quoted_passage"])
        if row["key_references"]:
            st.caption(row["key_references"])
        if row["reading_status"]:
            st.caption(access.PROGRESS[row["reading_status"]])
        if row.get("stopped_reason"):
            st.text(row["stopped_reason"])
        if row["deleted_at"]:
            if st.button("Restore note", key=f"undelete_{row['note_id']}"):
                access.revise_note(row["note_id"], row["last_updated_at"], row["notes"] or "",
                                   row["quoted_passage"] or "", row["key_references"] or "")
                st.rerun()
        else:
            edit_note(row)


def article_page(library, paper, owner):
    st.button("Back to my reading" if st.session_state.get("library_view") == "My reading"
              else "Back to articles", on_click=st.session_state.pop, args=("notebook_paper", None))
    work_id = paper["work_id"]
    details = library.select_rows(library.ARTICLE_SQL, (work_id,))
    if not details and (not owner or "title" not in paper):
        st.info("This article is unavailable.")
        return

    article = details[0] if details else paper
    st.header(library.markdown_text(article["title"]))
    current = next((row for row in access.read_assessments() if row["work_id"] == work_id), {}) if owner else {}
    starred = current.get("is_favorite")
    if starred:
        st.caption("\u2605 Starred")
    if article.get("is_retracted"):
        st.warning("Source metadata marks this article as retracted.")
    original = library.paper_link(article)
    catalog = library.external_url(article["openalex_id"])
    if original:
        st.link_button("Read original", original)
    elif catalog:
        st.link_button("View OpenAlex record", catalog)
    else:
        st.caption("An accessible source link is unavailable.")
    if article.get("summary"):
        st.subheader("AI summary")
        st.markdown(library.markdown_text(article["summary"]))
        basis = library.REVIEW_BASIS_LABELS.get(article["review_basis"])
        if basis:
            st.caption(f"Based on {basis}.")
    if not owner:
        source_details(article, catalog if original else None)
        return

    st.subheader("Your notes")
    if st.session_state.pop("notebook_saved", False):
        st.success("Note saved.")
    library.note_form(work_id, favorite=bool(starred) if details or starred else None)
    for row in access.read_notes(work_id):
        if row["work_id"] == work_id and not row["deleted_at"]:
            show_note(row)

    reading_details(work_id, current)
    source_details(article, catalog if original else None)

    with st.expander("Related articles"):
        linked = access.connections(work_id)
        if not linked:
            st.caption("No saved connections yet.")
        for item in linked:
            st.markdown("**" + library.markdown_text(item["title"]) + "**")
            st.caption(f"{item['connection_type']} · {item['review_status']}")
            st.text(item["explanation"])
            if item["evidence"]:
                st.text(item["evidence"])
            st.caption("Connection based on " + item["review_basis"])
            st.button("Open article", key=f"connected_{item['work_id']}_{item['connection_type']}",
                      on_click=library.open_paper_notebook, args=(item,))


def source_details(article, catalog):
    with st.expander("Source details"):
        if article.get("publication_name"):
            st.text(article["publication_name"])
        if article.get("doi"):
            st.caption("DOI")
            st.text(article["doi"])
        if catalog:
            st.link_button("View OpenAlex record", catalog)


def workspace(library):
    st.header("My reading")
    notes = access.read_notes()
    assessments = access.read_assessments()
    active_notes = {}
    for row in notes:
        if row["work_id"] is not None and not row["deleted_at"]:
            active_notes.setdefault(row["work_id"], []).append(row)
    articles = {row["work_id"]: row for row in assessments}
    for work_id, entries in active_notes.items():
        articles.setdefault(work_id, entries[0])

    search = st.text_input("Find something in my reading", placeholder="Search titles, notes, and quotes", key="notebook_search").strip().casefold()
    view = st.selectbox("Show", ["All my articles", "Continue reading", "Saved for later", "Starred", "Finished"],
                        key="notebook_filter")
    ordered = sorted(
        articles.values(),
        key=lambda item: max(
            [item["last_updated_at"]] +
            [entry["last_updated_at"] for entry in active_notes.get(item["work_id"], [])]
        ),
        reverse=True,
    )
    shown = 0
    for item in ordered:
        work_id = item["work_id"]
        entries = active_notes.get(work_id, [])
        progress = item.get("reading_status")
        progress_note = next((entry for entry in entries if entry["reading_status"]), None)
        if progress_note and (not progress or progress_note["noted_at"] > item["last_updated_at"]):
            progress = progress_note["reading_status"]
        if view == "Continue reading" and progress not in ("abstract_only", "partial"):
            continue
        if view == "Starred" and not item.get("is_favorite"):
            continue
        if view == "Saved for later" and not item.get("come_back_to_it"):
            continue
        if view == "Finished" and progress != "complete":
            continue
        snippets = [entry[field] for entry in entries for field in ("notes", "quoted_passage") if entry[field]]
        if search and not any(search in text.casefold() for text in [item["title"], *snippets]):
            continue

        shown += 1
        with st.container(border=True):
            st.subheader(library.markdown_text(item["title"]))
            labels = []
            if item.get("is_favorite"):
                labels.append("\u2605 Starred")
            if item.get("come_back_to_it"):
                labels.append("Saved for later")
            if progress:
                labels.append(access.PROGRESS[progress])
            if labels:
                st.caption(" · ".join(labels))
            if snippets:
                snippet = snippets[0].strip()
                st.text(snippet[:240].rstrip() + ("…" if len(snippet) > 240 else ""))
            st.button("Open article", key=f"library_open_{work_id}",
                      on_click=library.open_paper_notebook, args=(item,))
            if view == "Starred" and st.button("Remove star", key=f"unstar_{work_id}"):
                access.remove_favorite(work_id)
                st.rerun()
    if not shown:
        if view == "Starred" and not search:
            st.info("No starred articles yet. Use ☆ Star as a favorite on any article you want to share.")
        else:
            st.info("No articles match these filters." if articles
                    else "Articles appear here when you add a note or save them for later.")
        st.button("Find an article to read", on_click=st.session_state.update,
                  args=({"library_view": "Discover"},))

    with st.expander("Notebook tools"):
        st.download_button(
            "Export my notes and reading details",
            json.dumps({"notes": notes, "assessments": assessments}, default=str, ensure_ascii=False, indent=2),
            file_name="research-library.json", mime="application/json",
        )
        tool = st.selectbox("Manage notes", ["Choose an option", "General notes", "Deleted notes"])
        if tool == "General notes":
            if st.session_state.pop("notebook_saved", False):
                st.success("Note saved.")
            library.note_form(None)
            for row in notes:
                if row["work_id"] is None and not row["deleted_at"]:
                    show_note(row)
        elif tool == "Deleted notes":
            st.caption("Restore a note here if you deleted it by mistake.")
            for row in notes:
                if row["deleted_at"]:
                    show_note(row)
