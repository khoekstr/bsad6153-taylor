"""Provision the two website logins locally with the existing database administrator."""
import os
from pathlib import Path
import secrets
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import psycopg
from psycopg import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"APP_DATABASE_URL": "library_web_reader", "NOTEBOOK_DATABASE_URL": "library_notebook"}


def role_url(admin, role, password):
    parts = urlsplit(admin)
    username = unquote(parts.username or "")
    if parts.scheme not in ("postgres", "postgresql") or username.split(".")[0] != "postgres":
        raise ValueError("Use the postgres administrator URL for setup.")
    if parts.query and any(key in parts.query.lower() for key in ("user=", "password=", "options=", "service=")):
        raise ValueError("Use a standard PostgreSQL connection URL for setup.")
    suffix = username.partition(".")[2]
    login = role + ("." + suffix if suffix else "")
    endpoint = parts.netloc.rsplit("@", 1)[-1]
    credentials = quote(login, safe=".") + ":" + quote(password, safe="")
    return urlunsplit(parts._replace(netloc=credentials + "@" + endpoint))


def main():
    admin = os.getenv("DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if not admin:
        raise ValueError("The local administrator connection is missing.")
    role_url(admin, "library_web_reader", "unused")
    env_path = ROOT / "app" / ".env"
    migration = (ROOT / "db/migrations/009_web_notebook.sql").read_text().strip()
    if not migration.endswith("COMMIT;"):
        raise ValueError("The notebook migration must end with COMMIT.")
    with psycopg.connect(admin, autocommit=True, connect_timeout=6) as db:
        # Keep role creation and password provisioning in one transaction.
        # The migration starts BEGIN; hold its final COMMIT until both roles are ready.
        db.execute("BEGIN")
        db.execute("SELECT pg_advisory_xact_lock(6153, 9)")
        count = db.execute("SELECT count(*) FROM pg_roles WHERE rolname = ANY(%s)",
                           (list(ROLES.values()),)).fetchone()[0]
        if count == 1:
            raise ValueError("Only one website role exists. Review migration 009 before continuing.")
        if count == 2:
            print("Website role names already exist. Existing roles and passwords were preserved.")
            return
        if env_path.exists():
            settings = dotenv_values(env_path, interpolate=False)
            passwords = {}
            for key, role in ROLES.items():
                value = settings.get(key) or ""
                password = unquote(urlsplit(value).password or "")
                if not password or value != role_url(admin, role, password):
                    raise ValueError("The existing app/.env needs review. It was preserved.")
                passwords[role] = password
        else:
            passwords = {role: secrets.token_urlsafe(36) for role in ROLES.values()}
            # Persist the credentials first. A failed transaction can reuse them on retry.
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            with os.fdopen(os.open(env_path, flags, 0o600), "w", encoding="utf-8") as private_file:
                for key, role in ROLES.items():
                    private_file.write(f"{key}={role_url(admin, role, passwords[role])}\n")
        _, boundary, body = migration.partition("\nBEGIN;")
        if not boundary:
            raise ValueError("The notebook migration must contain BEGIN.")
        db.execute(body.removesuffix("COMMIT;"))
        for role, password in passwords.items():
            verifier = db.pgconn.encrypt_password(password.encode(), role.encode(), b"scram-sha-256")
            db.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(verifier.decode("ascii"))))
        db.execute("COMMIT")
    print("Website database roles are provisioned. Local website credentials are in ignored app/.env.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, psycopg.Error):
        raise SystemExit("Website database setup could not finish. Check the local connection, "
                         "existing app settings, and migration prerequisites. No credentials displayed.")
