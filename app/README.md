# AI Research Discovery app

Run from the repository root with the existing `requirements.txt` dependencies installed.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

The public site and the private notebook use separate server-side connections. Setup is below.

## Public views

- Discover shows up to five papers published today or in the previous 29 UTC calendar dates, ranked by latest saved AI interest, publication date, and work ID. Unknown and future publication dates are excluded.
- Explore provides literal keyword search over titles, abstracts, and AI summaries, topic selection, optional inclusive date bounds, minimum AI interest, and ten-paper pages. Unknown dates and scores remain accessible when their filters are unset.
- Topics include OpenAlex topics and AI-assigned categories. Their counts overlap because papers can belong to several topics.
- Only OpenAlex records and manually added references with web source links enter the public collection. Raw source JSON, file paths, private notes, user assessments, and internal assessment context are not queried. Review the source permissions and public AI summaries/explanations before deployment to confirm that the displayed material contains no private information and is permitted for public use.
- The latest AI assessment is selected by creation time and assessment ID, matching the existing SQL queries. An absent score means unknown. Assessments are explicitly labeled by their basis. The app makes no model calls. The owner can explicitly save private reading progress.

## Freshness and caching

The banner follows `db/sync_status.sql`: only completed, non-preview, successful live discovery counts. Successful previews, same-day skips, and targeted maintenance cannot advance discovery freshness. The age is calculated at render time from the cached timestamp. A warning appears after 96 hours, when no qualifying success exists, when the timestamp is invalid, or when history cannot be read.

The ongoing workflow is configured for Monday/Thursday at 08:15 America/Chicago, including daylight saving time. It takes effect after the workflow changes reach `main`. Initially, the workflow contained an expired November trial. The app reads actual history. A successful discovery does not establish that all stored source metadata and AI assessments are current.

Public SELECT results use `st.cache_data` with a **900-second (15-minute) TTL**, much shorter than the planned three/four-day sync gaps. This avoids repeated database work on every interaction while letting new papers and assistant-updated assessments appear within about 15 minutes on the next render. A longer TTL would delay those changes. A very short TTL would increase database load. Date-sensitive queries include the current UTC date in their cache inputs. A connection fingerprint separates configurations without putting the connection string in cache arguments. Database failures raise safe exceptions and are not cached as empty results.

## Owner notebook

The instructor approved authenticated writes for this milestone. Visitors see the same Discover and Explore views. Kara signs in with Google, opens **My notes** on a paper, and can open the source in a second tab. Thoughts, exact passages, and page or section references have separate fields. Reading progress is optional. Saving appends one private entry. It does not update the paper's AI score, explanation, or recommendation order. Kara can explicitly request reassessment separately. The notebook includes older imported entries, including notes on private references. Private results bypass the shared cache.

### Local and Render setup

1. Install the project dependencies with `python -m pip install -r requirements.txt`. The Streamlit authentication extra supplies Authlib.
2. From a machine with access to the existing Supabase database, run `python scripts/setup_web_database.py` from the repository root. It reads the local administrator URL, applies migration 009 after the existing schema/migrations, and creates two logins with generated passwords. Their connection URLs are saved in ignored `app/.env`. The original root `.env` and its course evaluator login stay in place. The script preserves existing roles/passwords. If an administrator already applied migration 009 manually, supply the two existing role URLs in `app/.env` or the process environment.
3. Create a Google OAuth **Web application** client with the OpenID, email and profile scopes. Register the exact callback for each environment: `http://localhost:8501/oauth2callback` locally and `https://YOUR-RENDER-DOMAIN/oauth2callback` on Render. For a Google consent screen in testing mode, add Kara's Google account as a test user. [Google sign-in with Streamlit](https://docs.streamlit.io/develop/tutorials/authentication/google)
4. Copy `app/google.example.toml` to ignored `.streamlit/secrets.toml` locally. Fill in the client ID, client secret, matching callback, and a random cookie secret. Generate a separate cookie secret for each environment, for example with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. On Render, use a **secret file** named `secrets.toml` with the production callback. The app configuration looks for that file in `/etc/secrets`. Set `APP_DATABASE_URL` to the generated **library_web_reader** URL and `NOTEBOOK_DATABASE_URL` to the generated **library_notebook** URL. Keep the local administrator and course reader credentials off the web service. [Render environment and secret files](https://render.com/docs/configure-environment-variables)
5. Start the app and sign in with Kara's Google account. With the owner setting empty, **Set up owner access** shows the signed-in account's own Google subject ID. Copy that ID into `NOTEBOOK_GOOGLE_SUB` in ignored `app/.env` locally or Render's environment settings. Restart. The server requires the configured Google subject, Google issuer, an authenticated session, and a current identity token before each private database operation. An expired session can sign out and back in. Enrollment requires changing server settings.
6. In Discover or Explore, open **My notes** on a paper. Save an entry, sign out, then sign back in and reopen **My notes** to verify persistence. Check that a signed-out browser and a different Google account can browse public papers and cannot access notes.

Only the notebook role can append notebook entries from the app. Its grants exclude edits, deletes, and writes to works or assessments. The dedicated public reader has column-level grants and row policies. The older `app_reader` login has wider read access for the Milestone 2 and 3 course checks and is rejected by the website.

## Verification and deployment

### Kara's favorite reads

Apply `db/migrations/012_public_favorites.sql` in the Supabase SQL Editor after
migrations 010 and 011. The public favorites view exposes the article ID and
display order for eligible, AI-summarized articles starred by Kara. Visitors
can browse five per page. New stars appear first. Older stars with unknown
dates follow in descending publication order.

To add or restore a favorite, sign in, open the article notebook, check
**★ Favorite**, and save the assessment. Under **My library → Favorites**, use
**Remove from favorites** to take an article off the list.

Run the focused offline tests from the repository root.

```powershell
.\.venv\Scripts\python.exe -m unittest app.test_streamlit_app app.test_notebook -v
```

Before submission, compare the displayed public-collection total, 30-day publication count, and unknown-interest count with direct SQL using the same public-source rules and UTC dates. After provisioning, set `TEST_WEB_DATABASE=1` and run `python -m unittest app.test_notebook_database -v` with the website credentials. The tests exercise public access denials and an owner insert/retry inside a rolled-back transaction. Offline tests supplement the student's live verification evidence.

Render uses the existing repository start command and the server settings above. A free service can take about a minute to wake after inactivity. Record the actual deployed URL and domain in the root README during the deployment step.
