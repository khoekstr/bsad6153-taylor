"""Privately configure the reader's Session pooler URL after setting its password."""
import getpass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
import warnings

import psycopg
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def connection_failure(error):
    """Classify locally; never print the original error or connection details."""
    message = str(error).lower()
    if 'password authentication failed' in message or 'wrong password' in message:
        return 'The server rejected the password. Use the latest password set for app_reader.'
    if 'tenant or user not found' in message:
        return 'The pooler could not find this project or role.'
    if 'circuit breaker' in message or 'too many authentication' in message:
        return 'The pooler temporarily blocked authentication after failed attempts. Wait a few minutes before retrying.'
    if 'timeout' in message or 'timed out' in message:
        return 'The connection timed out before login completed.'
    if any(x in message for x in ('getaddrinfo', 'could not translate host', 'name resolution')):
        return 'The computer could not resolve the pooler hostname.'
    if 'ssl' in message or 'certificate' in message:
        return 'The secure connection could not be established.'
    if 'permission denied' in message:
        return 'The server denied connection permission.'
    return 'Unclassified connection failure; credentials and server message remain hidden.'


def reader_url(owner_url, password):
    parts = urlsplit(owner_url)
    username = unquote(parts.username or '')
    if parts.scheme not in ('postgresql', 'postgres') or not username.startswith('postgres.'):
        raise ValueError('DATABASE_URL must use the postgres.<project-ref> pooler username.')
    if not parts.hostname or not parts.hostname.endswith('.pooler.supabase.com') or parts.port != 5432:
        raise ValueError('DATABASE_URL must use the Supabase Session pooler on port 5432.')
    if not password:
        raise ValueError('Password cannot be empty.')
    username = 'app_reader.' + username.split('.', 1)[1]
    authority = quote(username, safe='.') + ':' + quote(password, safe='') + '@' + parts.hostname + ':5432'
    return urlunsplit((parts.scheme, authority, parts.path, parts.query, parts.fragment))


def main():
    try:
        values = dotenv_values(ROOT / '.env', interpolate=False)
        owner = values.get('DATABASE_URL')
        if not owner:
            print('[FAIL] DATABASE_URL is missing from local .env.')
            return 1
        # Never fall back to a visible password prompt in a redirected terminal.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('New app_reader password (hidden): ')
        url = reader_url(owner, password)
        with psycopg.connect(url, connect_timeout=20) as conn:
            if conn.execute('SELECT current_user').fetchone()[0] != 'app_reader':
                print('[FAIL] Unexpected database user; nothing saved.')
                return 1
        set_key(str(ROOT / '.env'), 'APP_DATABASE_URL', url, quote_mode='always')
        print('[ok] Connected as app_reader and saved APP_DATABASE_URL in local .env.')
        print('No password or connection string displayed.')
        return 0
    except psycopg.OperationalError as error:
        print('[FAIL] ' + connection_failure(error))
        print('Nothing saved. No password or connection string displayed.')
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled; nothing saved.')
        return 1
    except Exception as error:
        print('[FAIL] ' + type(error).__name__ + '; nothing saved. Check the password and Session pooler connection.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
