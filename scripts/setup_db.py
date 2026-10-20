"""Create the SkillSync database and app user on an existing MySQL 8 or SQL Server, then
run the Alembic migrations as that user.

    backend/.venv/Scripts/python scripts/setup_db.py mysql --admin-user root
    backend/.venv/Scripts/python scripts/setup_db.py mssql --host localhost --admin-user sa
    backend/.venv/Scripts/python scripts/setup_db.py mysql --dry-run      (print the SQL only)

Passwords are never stored or logged. The admin password is read with getpass (or from
SKILLSYNC_DB_ADMIN_PASSWORD for unattended use) and used only for this run. The app user's
password comes from SKILLSYNC_DB_APP_PASSWORD, or a random one is generated and printed once,
inside the DATABASE_URL line you paste into .env.

Drivers (both MIT): pip install -r backend/requirements-mysql.txt  (PyMySQL)
                    pip install pyodbc   (+ Microsoft ODBC Driver 18 for SQL Server)
Status: the generated DDL is compile-tested for both dialects (backend/tests/test_migrations_ddl.py),
but this script has not been run against a live MySQL or SQL Server (see docs/DECISIONS.md).
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
DEFAULT_PORT = {"mysql": 3306, "mssql": 1433}
MSSQL_DRIVER = "ODBC Driver 18 for SQL Server"


def ident(value: str, what: str) -> str:
    if not IDENT.match(value):
        raise SystemExit(f"{what} must match {IDENT.pattern}: {value!r}")
    return value


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def plan_sql(dialect: str, db: str, app_user: str, app_password: str, app_host: str = "%") -> list[str]:
    """The admin statements, in order. Identifiers are validated, the password is a quoted literal."""
    db, app_user = ident(db, "database"), ident(app_user, "app user")
    pwd = sql_literal(app_password)
    if dialect == "mysql":
        host = sql_literal(app_host)
        return [
            f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            f"CREATE USER IF NOT EXISTS '{app_user}'@{host} IDENTIFIED BY {pwd}",
            f"ALTER USER '{app_user}'@{host} IDENTIFIED BY {pwd}",
            f"GRANT ALL PRIVILEGES ON `{db}`.* TO '{app_user}'@{host}",
            "FLUSH PRIVILEGES",
        ]
    if dialect == "mssql":
        return [
            f"IF DB_ID(N'{db}') IS NULL CREATE DATABASE [{db}]",
            f"IF SUSER_ID(N'{app_user}') IS NULL CREATE LOGIN [{app_user}] WITH PASSWORD = {pwd}, "
            "CHECK_POLICY = ON",
            f"ALTER LOGIN [{app_user}] WITH PASSWORD = {pwd}",
            f"USE [{db}]",
            f"IF USER_ID(N'{app_user}') IS NULL CREATE USER [{app_user}] FOR LOGIN [{app_user}]",
            f"ALTER ROLE db_owner ADD MEMBER [{app_user}]",
        ]
    raise SystemExit(f"unsupported dialect {dialect!r} (use mysql or mssql)")


def url_for(dialect: str, user: str, password: str, host: str, port: int, db: str | None) -> str:
    auth = f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}"
    if dialect == "mysql":
        return f"mysql+pymysql://{auth}/{db or ''}?charset=utf8mb4"
    query = f"driver={quote_plus(MSSQL_DRIVER)}&TrustServerCertificate=yes"
    return f"mssql+pyodbc://{auth}/{db or 'master'}?{query}"


def masked(statements: list[str], password: str) -> list[str]:
    return [s.replace(sql_literal(password), "'********'") for s in statements]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dialect", choices=("mysql", "mssql"))
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int)
    ap.add_argument("--admin-user", default="root")
    ap.add_argument("--db", default="skillsync")
    ap.add_argument("--app-user", default="skillsync")
    ap.add_argument("--app-host", default="localhost", help="MySQL only: host part of the app account")
    ap.add_argument("--dry-run", action="store_true", help="print the SQL (password masked) and exit")
    args = ap.parse_args(argv)
    port = args.port or DEFAULT_PORT[args.dialect]

    app_password = os.environ.get("SKILLSYNC_DB_APP_PASSWORD") or secrets.token_urlsafe(18)
    statements = plan_sql(args.dialect, args.db, args.app_user, app_password, args.app_host)
    if args.dry_run:
        print("\n".join(s + ";" for s in masked(statements, app_password)))
        return 0

    admin_password = os.environ.get("SKILLSYNC_DB_ADMIN_PASSWORD") or getpass.getpass(
        f"{args.dialect} password for {args.admin_user}@{args.host} (not stored): "
    )
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlalchemy import create_engine, text

    from app.core.db import run_migrations

    admin = create_engine(
        url_for(args.dialect, args.admin_user, admin_password, args.host, port, None),
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    admin.dispose()
    del admin_password
    print(f"[setup_db] database {args.db!r} and user {args.app_user!r} ready on {args.host}:{port}")

    app_url = url_for(args.dialect, args.app_user, app_password, args.host, port, args.db)
    run_migrations(app_url)
    print("[setup_db] migrations applied (alembic upgrade head)")
    print("\nAdd this line to .env (it contains the app password, so keep .env out of git):\n")
    print(f"DATABASE_URL={app_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
