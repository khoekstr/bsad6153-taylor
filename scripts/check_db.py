"""Week 2 database check. Run it from the project folder:

    python scripts/check_db.py          # connects as the owner (DATABASE_URL)
    python scripts/check_db.py --app    # connects as the read-only role (APP_DATABASE_URL)

It confirms that your connection string works and shows which database user you
are connected as. It never prints the connection string, which contains your password.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

variable = "APP_DATABASE_URL" if "--app" in sys.argv else "DATABASE_URL"
url = os.environ.get(variable)

if not url:
    print(f"[FAIL] {variable} is not set. Add it to your .env file (see .env.example).")
    sys.exit(1)

try:
    # connect_timeout keeps a wrong address from hanging forever.
    with psycopg.connect(url, connect_timeout=10) as conn:
        version, user = conn.execute("select version(), current_user").fetchone()
except psycopg.OperationalError as error:
    print(f"[FAIL] Could not connect using {variable}.")
    print(f"       {type(error).__name__}; connection details omitted for privacy.")
    print("       Check: Supabase Session pooler string? Correct password? Project paused?")
    sys.exit(1)

print(f"[ok] Connected using {variable}")
print(f"     Database user: {user}")
print(f"     Server: {version.split(',')[0]}")
if '--app' in sys.argv and user != 'app_reader':
    print('[FAIL] APP_DATABASE_URL must connect as app_reader.')
    sys.exit(1)
