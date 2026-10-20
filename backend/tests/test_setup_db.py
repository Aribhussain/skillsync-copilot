"""scripts/setup_db.py: SQL planning only (no live MySQL / SQL Server in the test run)."""

from __future__ import annotations

import importlib.util
import sys

import pytest

from app.core.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("setup_db", REPO_ROOT / "scripts" / "setup_db.py")
setup_db = importlib.util.module_from_spec(spec)
sys.modules["setup_db"] = setup_db
spec.loader.exec_module(setup_db)


@pytest.mark.parametrize("dialect", ["mysql", "mssql"])
def test_plan_quotes_the_password_and_masks_it(dialect):
    pwd = "it's; DROP DATABASE x; --"
    sql = setup_db.plan_sql(dialect, "skillsync", "skillsync", pwd)
    assert any("'it''s; DROP DATABASE x; --'" in s for s in sql)  # one literal, quote doubled
    shown = setup_db.masked(sql, pwd)
    assert not any("DROP DATABASE x" in s for s in shown)
    assert any("'********'" in s for s in shown)


@pytest.mark.parametrize("bad", ["sk-ill", "x;drop", "1abc", "a b", "`x`", "a" * 65])
def test_identifiers_are_validated(bad):
    with pytest.raises(SystemExit):
        setup_db.plan_sql("mysql", bad, "skillsync", "pw")
    with pytest.raises(SystemExit):
        setup_db.plan_sql("mssql", "skillsync", bad, "pw")


def test_urls_escape_credentials():
    url = setup_db.url_for("mysql", "app", "p@ss:w/rd", "localhost", 3306, "skillsync")
    assert url == "mysql+pymysql://app:p%40ss%3Aw%2Frd@localhost:3306/skillsync?charset=utf8mb4"
    ms = setup_db.url_for("mssql", "app", "pw", "db.local", 1433, "skillsync")
    assert ms.startswith("mssql+pyodbc://app:pw@db.local:1433/skillsync?driver=ODBC+Driver+18")


def test_dry_run_never_asks_for_a_password(monkeypatch, capsys):
    monkeypatch.setattr(setup_db.getpass, "getpass", lambda *_: pytest.fail("prompted"))
    assert setup_db.main(["mysql", "--dry-run"]) == 0
    assert "CREATE DATABASE IF NOT EXISTS `skillsync`" in capsys.readouterr().out
