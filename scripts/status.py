"""Report sync freshness and seven-day changes using app_reader only."""
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / '.env')
    url = os.getenv('APP_DATABASE_URL')
    if not url:
        print('APP_DATABASE_URL is required; there is no owner fallback.')
        return 1
    try:
        with psycopg.connect(url, connect_timeout=15) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            if conn.execute('SELECT current_user').fetchone()[0] != 'app_reader':
                raise ValueError('Expected app_reader')
            result = conn.execute((ROOT / 'db/sync_status.sql').read_text(encoding='utf-8')).fetchone()[0]
        print(json.dumps(result, indent=2))
        if result['last_successful_discovery_at'] is None:
            print('No completed successful live discovery is recorded yet.')
        if result['last_committed_work_change_at'] is None:
            print('No committed work changes are recorded by this run history yet; earlier imports are not included.')
        return 0
    except Exception:
        print('Status unavailable; check the reader connection and migration 006. Details withheld to protect credentials.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
