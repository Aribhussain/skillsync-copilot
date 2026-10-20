"""Offline DDL for the non-SQLite backends (no server needed).

Alembic's offline mode compiles every migration to SQL for a dialect. This catches
migrations that only work on SQLite, e.g. an audit_ledger.seq without an identity
column, which SQLite hides because INTEGER PRIMARY KEY is always its rowid.
Postgres is also exercised live by the Docker smoke test; MySQL and SQL Server are
only compiled here (see docs/DECISIONS.md).
"""

from __future__ import annotations

import contextlib
import io
import re

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR

DIALECT_URLS = {
    "postgresql": "postgresql+pg8000://u:p@localhost/skillsync",
    "mysql": "mysql+pymysql://u:p@localhost/skillsync",
    "mssql": "mssql+pyodbc://u:p@localhost/skillsync",
}

# How each dialect spells "the database assigns this integer key".
IDENTITY = {
    "postgresql": r"seq SERIAL",
    "mysql": r"seq INTEGER NOT NULL AUTO_INCREMENT",
    "mssql": r"seq INTEGER NOT NULL IDENTITY",
}


def offline_sql(url: str) -> str:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    out = io.StringIO()
    cfg.stdout = out
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)
    return buf.getvalue() + out.getvalue()


@pytest.mark.parametrize("dialect", sorted(DIALECT_URLS))
def test_migrations_compile_offline(dialect):
    sql = offline_sql(DIALECT_URLS[dialect])
    assert "CREATE TABLE audit_ledger" in sql
    assert "CREATE TABLE credentials" in sql
    ledger = re.search(r"CREATE TABLE audit_ledger \((.*?)\n\);", sql, re.S)
    assert ledger, "audit_ledger DDL not found"
    assert re.search(IDENTITY[dialect], ledger.group(1)), ledger.group(1)
    # No server-side defaults on JSON columns (unsupported on MySQL).
    assert not re.search(r"JSON[^,\n]*DEFAULT", sql)
