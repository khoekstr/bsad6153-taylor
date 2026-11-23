# Milestone 4 code tour

AI source review of the November 23 working copy. ✔ means the cited code supports the claim. ✘ flags an earlier explanation that needed correction. Live Google sign-in, deployed database permissions, and the student's independent review are separate checks.

## From a click to a query

✔ [streamlit_app.py](../app/streamlit_app.py) renders Discover, Explore, and the owner's notebook (lines 355, 408, 313, with view selection in `main` starting at 451). [library_access.py](../app/library_access.py) checks the owner identity (17–26), opens database connections (30–54), reads notes (57–67), and saves entries (75–99).

| Verified operation | SQL definition | Where it runs |
|---|---|---|
| ✔ Check the database identity on every new application connection | `library_access.py` 49 selects both the current role and session login. | Line 49 executes it immediately after opening the connection at 44. Lines 50–51 require both names to match. |
| ✔ Show the last successful discovery | `streamlit_app.py` 92–97 takes the latest finish time for a matching non-dry run. | The banner supplies success, discovery mode, and completed outcome at 148–150. Line 108 executes the query on a cache miss. |
| ✔ Count public papers, papers published in the date window, and papers missing an interest score | `streamlit_app.py` 46–54 | Line 490 requests all three counts together. Line 108 executes the query on a cache miss. |
| ✔ Populate Explore's topic selector | `streamlit_app.py` 56–67 combines source topics and AI categories and counts distinct papers per topic. | Line 358 requests the options. Line 108 executes the query on a cache miss. |
| ✔ Find papers for Discover and Explore | `streamlit_app.py` 69–88 defines one shared query. Lines 118–127 bind the search, filters, limit, and offset. | Discover requests up to five scored papers in 30 calendar days at 411. Explore passes its filter and page values at 389–392. Both reach 127, then 108 on a cache miss. |
| ✔ Read private notebook entries | `library_access.py` 59–67 joins notes to papers. A supplied work ID limits results to that paper. | `streamlit_app.py` 328 calls the reader. `library_access.py` 58 requests the private connection and 59 executes the SELECT directly. |
| ✔ Save a note, quotation, reference, or progress entry | `library_access.py` 86–91 inserts into `reading_notes` using bound values. | `streamlit_app.py` 299–300 calls the saver. `library_access.py` 85 requests the private connection and 86 executes the INSERT. The save path contains no assessment update. |
| ✔ Check a repeated save | `library_access.py` 92–99 looks up the existing submission by its unique import key when the INSERT returned no row. | Line 93 executes the SELECT only on that branch. A matching entry completes the retry. A missing or different entry raises `EarlierSave` at 98. |

✔ The shared public-library definition at `streamlit_app.py` 29–44 selects eligible works and their latest AI assessments. It forms part of the counts, topics, and papers queries. The cache decorator at 104 uses the 900-second TTL at 23. On a cache hit, the function body at 107–108 is skipped.

## Connections, secrets, and error handling

| File and responsibility | Verified locations |
|---|---|
| ✔ `streamlit_app.py` loads local settings and requests public connections. | Line 452 loads `app/.env` while preserving existing environment values. Lines 112–115 read `APP_DATABASE_URL`, raise a friendly error if missing, and hash the URL for the cache key. Lines 100–101 and 107 delegate connection creation. |
| ✔ `library_access.py` chooses credentials and opens the connection. | Lines 31–38 select `NOTEBOOK_DATABASE_URL` for an authorized notebook request or `APP_DATABASE_URL` for public reads. Lines 39–43 reject missing settings or an unexpected username. `psycopg.connect` is at **44**. Line 48 sets public transactions to read-only. Lines 53–54 translate driver errors into a user-safe message. |
| ✔ Google verifies identity and the app decides who may use the notebook. | `streamlit_app.py` 259–273 initiates login at 262, handles login errors at 263–264, checks the owner setting during setup at 268, and invokes logout at 273. Streamlit's secret-file locations are configured in `.streamlit/config.toml` 1–2. `library_access.py` 18–26 reads the configured owner ID and checks login state, Google issuer, subject ID, and expiry. Lines 31–33 enforce that check before opening a private connection. |
| ✔ The public screens distinguish stale data, unavailable data, and empty searches. | `streamlit_app.py` 130–143 checks missing, invalid, future, and overdue timestamps. Lines 152–155 show a warning if the history query fails. Lines 384–398 handle incomplete dates, an out-of-range page, and zero matches. Lines 412–417 explain an empty shortlist. Lines 500–503 handle expected and unexpected public-view errors. Link parsing handles invalid values at 163–182. |
| ✔ The notebook validates input and reports unsuccessful saves. | `library_access.py` 80–84 rejects an empty entry or invalid progress. `streamlit_app.py` 301–305 handles conflicting retries and safe save errors. Lines 306–310 reset the form after success. Line 330 explains an empty notebook. Lines 483–486 handle errors loading the private view. |

## Tests and supporting files

| App file | Verified purpose and locations |
|---|---|
| ✔ [test_streamlit_app.py](../app/test_streamlit_app.py) | Offline checks cover freshness (31–60), parameter binding, connection identity and errors (62–97), caching (99–123), and public screens (139 onward). The connection tests substitute credentials and mock the connector at 74–95. The count queries at 108–112 and 122 use a mocked connection or simulated failure. Lines 140–157 replace public query results for UI tests. Failure assertions include 91–97 and 214 onward. |
| ✔ [test_notebook.py](../app/test_notebook.py) | Lines 19–46 simulate owner identities, credential settings, and denied private operations. Lines 48–74 exercise repeated saves, conflicting contents, and invalid input with database operations mocked. Lines 93–97 replace identity, reads, and saves for the UI test. Lines 107–115 exercise a failed save and retry. These tests use simulated credentials and connections. |
| ✔ [test_notebook_database.py](../app/test_notebook_database.py) | Line 14 checks the opt-in flag. Line 18 loads website settings. Lines 25 and 36 request connections through the production helper. Line 29 executes the counts query. The two private SELECT probes and the INSERT probe at 30–32, and the UPDATE and DELETE probes at 37–38, all execute at **22** under the expected permission error at **21**. Lines 39 and 51 execute the work-ID and note-ID lookups. Lines 49–53 exercise the production insert, retry lookup, and note reader on the same connection. Line 35 substitutes a successful owner check and line 36 requests rollback of the test transaction. |
| ✔ [google.example.toml](../app/google.example.toml) | Lines 1–7 provide a Google login configuration template with placeholder credentials. It contains no executable connection, query, secret read, or error handler. |
| ✔ [README.md](../app/README.md) | Lines 11–29 describe the views, cache, and notebook. Setup begins at 31 and verification at 42. These are instructions. The file executes no connections, queries, secret reads, or error handlers. |
| ✔ `app/.env` | Local, Git-ignored settings file. Its runtime read is at `streamlit_app.py` 452 and its integration-test read at `test_notebook_database.py` 18. The file executes no code. Credential values were excluded from this review. |

## Correction found during review

✘ **Earlier description:** the current website connects only as `app_reader` and never writes.

✔ **Corrected:** public browsing expects `library_web_reader`. An owner-authorized notebook request expects `library_notebook`. Both use the connection call in `library_access.py` 44, with role selection at 31–38 and verification at 49–51. The notebook writes at 86. Google sign-in itself starts at `streamlit_app.py` 262 and does not open a database connection.
