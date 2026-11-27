"""Compare the public Streamlit caption with independent read-only Supabase SQL."""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SQL = """
SELECT count(*) AS total,
       count(*) FILTER (WHERE w.publication_date BETWEEN
           (now() AT TIME ZONE 'UTC')::date - 29 AND
           (now() AT TIME ZONE 'UTC')::date) AS recent,
       count(*) FILTER (WHERE latest.value_rating IS NULL) AS awaiting
FROM public.works w
JOIN LATERAL (
    SELECT a.summary, a.value_rating FROM public.work_assessments a
    WHERE a.work_id = w.work_id AND a.assessed_by = 'ai'
    ORDER BY a.first_seen_at DESC, a.assessment_id DESC LIMIT 1
) latest ON true
WHERE (w.source = 'openalex' OR (w.source = 'upload' AND w.source_url ~* '^https?://'))
  AND latest.summary ~ '[^[:space:]]'
""".strip()


def main():
    load_dotenv(ROOT / "app/.env", override=False)
    url = os.environ.get("APP_DATABASE_URL")
    if not url or conninfo_to_dict(url).get("user", "").split(".")[0] != "library_web_reader":
        sys.exit("Check the public reader setting in app/.env.")
    with psycopg.connect(url, connect_timeout=8) as conn:
        conn.read_only = True
        role = conn.execute("SELECT current_user").fetchone()[0]
        if role != "library_web_reader":
            sys.exit("Unexpected database role.")
        direct = conn.execute(SQL).fetchone()
    app = AppTest.from_file(str(ROOT / "app/streamlit_app.py")).run(timeout=90)
    for caption in app.caption:
        match = re.search(r"([\d,]+) papers in the public collection.*?([\d,]+) published in 30 days.*?([\d,]+) awaiting an AI interest score", caption.value)
        if match:
            displayed = tuple(int(value.replace(",", "")) for value in match.groups())
            break
    else:
        sys.exit("Direct SQL succeeded. The app did not render its three counts.")
    rows = []
    for label, ui, db in zip(("Public papers", "Published in 30 days", "Awaiting an AI interest score"), displayed, direct):
        rows.append(f"| {label} | {ui} | {db} | {'Match' if ui == db else 'Mismatch'} |")
    report = [
        "# Public library count verification", "",
        f"Checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} as `{role}`. "
        "Read the signed-out Discover caption with Streamlit AppTest and ran the SQL below directly against Supabase in a separate read-only connection.", "",
        "| Number | App | Direct SQL | Result |", "|---|---:|---:|---|", *rows, "",
        "The recent window includes today and the preceding 29 UTC dates. "
        "The assessment check reads the newest AI assessment for each eligible paper.", "",
        "```sql", SQL + ";", "```", "",
    ]
    path = ROOT / "docs/app_verification.md"
    path.write_text("\n".join(report), encoding="utf-8")
    print(*rows, sep="\n")
    print("Evidence saved in", path)
    return int(displayed != direct)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except psycopg.Error as error:
        reason = next((word for word in ("getaddrinfo failed", "timeout", "password authentication failed", "tenant or user not found", "connection refused") if word in str(error).lower()), type(error).__name__)
        sys.exit(f"Database check stopped ({reason}).")
