"""Record a real permission denial using the public website credential."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import psycopg
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
PROBE = "UPDATE public.works SET title = title WHERE false"
HEADER = "## Public reader write test"


def main():
    deployed = os.getenv("RENDER") == "true"
    if not deployed:
        load_dotenv(ROOT / "app/.env", override=False)
    url = os.getenv("APP_DATABASE_URL")
    if not url or conninfo_to_dict(url).get("user", "").split(".")[0] != "library_web_reader":
        sys.exit("The public website reader credential is required.")
    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION READ WRITE")
            identity = conn.execute("SELECT current_user, session_user").fetchone()
            if identity != ("library_web_reader", "library_web_reader"):
                sys.exit("Unexpected database identity.")
            conn.execute("SELECT title FROM public.works LIMIT 1").fetchone()
            try:
                conn.execute(PROBE)
            except psycopg.errors.InsufficientPrivilege as exc:
                denial = exc.diag.message_primary
                state = exc.sqlstate
            else:
                sys.exit("FAIL: PostgreSQL permitted UPDATE. The predicate matched zero rows.")
    origin = "Render service environment" if deployed else "local website configuration"
    evidence = (
        f"{HEADER}\n\nChecked {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} using "
        f"`APP_DATABASE_URL` from the {origin}. Both the login and current role were "
        "`library_web_reader`. Reading a public title succeeded.\n\n"
        f"```sql\n{PROBE};\n```\n\nPostgreSQL returned `{denial}` "
        f"(SQLSTATE `{state}`). The transaction allowed writes so the error tests "
        "the role's grants. The statement targeted zero rows and the transaction was rolled back.\n"
    )
    print(evidence)
    if not deployed:
        path = ROOT / "docs/app_verification.md"
        report = path.read_text(encoding="utf-8") if path.exists() else ""
        if evidence.strip() not in report:
            with path.open("a", encoding="utf-8") as output:
                output.write("\n" + evidence)


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        sys.exit(f"Verification stopped before evidence was recorded ({type(exc).__name__}, SQLSTATE {exc.sqlstate or 'unavailable'}).")
