# BSAD 6153 Project: &lt;your project name&gt;

**Student:** Kara Taylor
**My decision:** What AI material should I read or watch next, given my available time, learning interests, and what I have already consumed?
**Website:** &lt;your domain, from Week 4&gt;

This repository is one complete AI system, built over eight weeks: a real API, synced on a schedule into a
PostgreSQL database, shown on a public website, with a chatbot and an agent that answer and act from your
own data. You build it with an AI coding agent, and you read and verify everything it writes.

---

## Setting up your computer (Week 1 Setup)

You need a **Windows 10/11 or macOS computer where you can install software**, Git, Python 3.12, and your AI
coding agent (Claude Code, Codex, Antigravity, or Copilot). Let your agent help with the installs, but read
every command before you approve it, and keep auto-approve off.

1. **Clone this repository** into a short folder path that isn't synced by OneDrive or Dropbox, for example
   `C:\dev\bsad6153` on Windows or `~/dev/bsad6153` on macOS.
2. **Create and activate a virtual environment** from the project folder:

   | | Windows (PowerShell) | macOS (Terminal) |
   |---|---|---|
   | Create | `py -3.12 -m venv .venv` | `python3.12 -m venv .venv` |
   | Activate | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |

   You'll see `(.venv)` at the start of your prompt when it's active. Activate it every time you open a new terminal.
3. **Install the packages:** `pip install -r requirements.txt`
4. **Create your secrets file:** copy `.env.example` to `.env`, and put a fake value on the `TEST_SECRET=` line.
5. **Check everything:** `python scripts/check_setup.py` should end with `Setup OK`.
6. **Try the website:** `streamlit run app/streamlit_app.py` opens it in your browser. Press Ctrl+C to stop it.

### Working with your AI agent

- **You approve every command.** Read it first, and if you don't understand it, ask the agent what it does.
- **Ask for a plan before code:** "Before writing anything, tell me your plan."
- **Never paste a real key into the chat,** and never ask the agent to print your `.env` file.
- **The agent never gets the owner database password or deploy tokens.** That's how agents delete databases.
- **Record what you directed, read, verified, and decided** in each pull request's AI review log.

---

## Project layout

| Folder | What goes there | When |
|---|---|---|
| `ingest/` | Fetch, load, and sync code | Weeks 1&ndash;3 |
| `db/` | `schema.sql`, `roles.sql`, `queries.sql` | Weeks 2&ndash;6 |
| `docs/` | Data dictionary, logs, reports (see `docs/README.md`) | Every week |
| `evals/` | Golden questions and evaluation runs | Weeks 3&ndash;7 |
| `app/` | Your website (Streamlit) | Weeks 4&ndash;6 |
| `examples/` | A reference tool-using chatbot loop | Week 5 |
| `scripts/` | Setup and database checks | Weeks 0&ndash;2 |
| `data/sample/` | A small sample of raw API data (large downloads go in `data/raw/`, which Git ignores) | Week 1 |

## Secrets: where each one lives

| Secret | On your computer | On Render (website) | In GitHub Actions (sync) |
|---|---|---|---|
| `DATABASE_URL` (owner) | `.env` | **never** | Actions secret |
| `APP_DATABASE_URL` (read-only) | `.env` | environment setting | if your checks need it |
| `AGENT_DATABASE_URL` | `.env` | environment setting | no |
| LLM key, `APP_PASSWORD` | `.env` | environment setting | no |
| Data API key | `.env` | no | Actions secret |

`.env.example` lists the names only. If a secret ever leaks, revoke or rotate it first, then tell the instructor.

---

## Deploying on Render (Week 4)

1. Claim your free domain through the GitHub Student Developer Pack.
2. In Render, choose **New &gt; Blueprint**, pick this repository, and enter each secret when asked.
   (`render.yaml` describes the service.) Or create a **Web Service** by hand with:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
   - Environment variables: `PYTHON_VERSION=3.12.4`, `APP_DATABASE_URL`, and later your LLM key and `APP_PASSWORD`
3. Under **Settings &gt; Custom Domains**, add your domain, then add the DNS records Render shows you at your
   registrar. Ask your agent to explain each record before you add it. HTTPS turns on automatically.
4. Free services sleep when idle and take about a minute to wake. Say so on your site.

---

## Troubleshooting

- **`pip install` fails with "No such file or directory" on Windows:** the folder path is too long. Move the
  project to a short path such as `C:\dev\bsad6153` and recreate `.venv`.
- **PowerShell says running scripts is disabled when you activate:** use Command Prompt instead and run
  `.venv\Scripts\activate.bat`, or ask the instructor. Don't change system security settings without asking.
- **`python` opens the Microsoft Store or isn't found:** use `py -3.12` on Windows or `python3.12` on macOS.
- **The database check can't connect:** use Supabase's Session pooler string, check the password, and check
  that your Supabase project isn't paused.

---

## Project Proposal (Week 1)

**Data source and backup.** My primary source is the [OpenAlex API](https://help.openalex.org/api/),
which supplies scholarly works and related authors. The first successful run collected
500 unique works and 1,451 author records. My backup is the
[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/),
using works and related journal records. Switching would require a different importer;
Crossref does not replace OpenAlex's author profiles directly, and abstract coverage varies.

**Decision and workflow.** My decision is what AI material to read or watch next,
given my available time, interests, and prior reading. My [baseline log](docs/baseline_log.md)
documents browsing YouTube, LinkedIn, The Rundown AI, and OpenAlex. I struggle to judge
unfamiliar sources, see beyond headlines, and recognize repeated information. The log
also revealed an interest in retaining ideas and connecting readings for future research.
The system should combine a broad AI reading library with private notes, reading status,
and personal ratings. It should offer understandable summaries and distinguish newly
published material from material that is new to me. I will assess improvement through
selection time, abandoned or repetitive selections, and my usefulness ratings.

**Agent idea, first draft.** By Week 6, I want an agent within my personal AI reading website that helps me choose what to read and connect my own thinking across readings. The database would hold source information alongside my private notes, questions, quotations, reading status, and personal ratings. Through a chatbot, I could ask “What should I read in 15 minutes?” or “How does this relate to questions I raised earlier?” The agent would create a proposed reading list, explain relevance and novelty, and identify connections between sources and thoughts I have recorded. It could bring back an earlier question when a new article offers supporting evidence, a conflicting finding, or another perspective. My ideas would remain clearly distinguished from AI suggestions, and I would decide which connections are useful. The first agent action would be to save a proposed reading-and-connections brief for my review, linking recommendations to my notes and the original sources. Over time, these reviewed connections could help me organize references and develop my own research questions or proposal.

**Risks.** Rate limits, exhausted allowances, and expired or revoked keys could interrupt
collection; bounded retries, clear errors, and private key replacement address these.
Repeated downloads increase storage, so raw files stay outside Git. Missing metadata,
version duplicates, and search bias can weaken recommendations. OpenAlex's CC0 metadata
statement and broader service terms need reconciliation before public display; metadata
access does not authorize redistributing articles. Personal notes must remain private.
These limitations are documented in the [data dictionary](docs/data_dictionary.md).

## How to run this project

<!-- Keep this current: how to run the sync, the website, and the evaluations. -->

## Credits

<!-- Your data API's required attribution, plus any open-source code or samples you used. -->
