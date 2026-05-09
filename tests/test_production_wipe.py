"""
tests/test_production_wipe.py — coverage for the destructive wipe script.

Tests run against the SQLite shared in-memory DB set up by conftest.
We exercise:
  - APP_ENV guard refuses when not production and --allow-non-prod absent
  - Missing required env vars cause non-zero exit
  - Password length < 12 causes non-zero exit
  - --yes-really gate
  - End-to-end: legacy data wiped, CEO created, skill catalog preserved
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Guard tests — these must NOT touch the database. They exit early.
# ---------------------------------------------------------------------------

def test_refuses_when_not_production_without_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "ceo@ufitonline.net")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "x" * 12)
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "Ada")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "Lovelace")
    from scripts.production_wipe import main
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["--yes-really"])
    assert exc_info.value.code == 2


def test_missing_required_env_vars(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    for k in (
        "SUPER_ADMIN_EMAIL",
        "SUPER_ADMIN_PASSWORD",
        "SUPER_ADMIN_FIRST",
        "SUPER_ADMIN_LAST",
    ):
        monkeypatch.delenv(k, raising=False)
    from scripts.production_wipe import main
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["--allow-non-prod", "--yes-really"])
    assert exc_info.value.code == 3


def test_password_too_short(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "tooshort")
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "A")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "B")
    from scripts.production_wipe import main
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["--allow-non-prod", "--yes-really"])
    assert exc_info.value.code == 4


def test_yes_really_required(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "x" * 12)
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "A")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "B")
    from scripts.production_wipe import main
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["--allow-non-prod"])
    assert exc_info.value.code == 5


# ---------------------------------------------------------------------------
# End-to-end test — exercises the actual TRUNCATE + INSERT against the
# shared SQLite in-memory DB created by conftest.
# ---------------------------------------------------------------------------

def test_wipes_operational_data_and_creates_ceo(app, monkeypatch):
    """
    Insert a legacy organization + user, run the wipe, and confirm:
      - operational tables are empty
      - CEO row was atomically inserted
      - skill catalog is preserved
    """
    from app.database import get_db
    from app.routes._helpers import now_utc

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "ceo@ufitonline.net")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "Sup3r$ecret!Pwd")
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "Boss")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "Lady")

    # Pre-state: insert a row so we can assert it gets wiped.
    with app.app_context():
        db = get_db()
        ts = now_utc()
        db.execute(
            """INSERT INTO organizations
               (organization_name, organization_type, contract_status, created_at)
               VALUES ('LegacyOrg', 'school_district', 'active', ?)""",
            (ts,),
        )
        db.commit()
        org_count_before = db.execute(
            "SELECT COUNT(*) AS c FROM organizations"
        ).fetchone()["c"]
        skills_before = db.execute(
            "SELECT COUNT(*) AS c FROM skills"
        ).fetchone()["c"]

    assert org_count_before >= 1
    assert skills_before > 0  # init_db seeded the skill catalog

    # Run the wipe.
    from scripts.production_wipe import main
    rc = main(argv=["--allow-non-prod", "--yes-really"])
    assert rc == 0

    # Post-state: legacy data gone, CEO created, skills intact.
    with app.app_context():
        db = get_db()
        org_count = db.execute(
            "SELECT COUNT(*) AS c FROM organizations"
        ).fetchone()["c"]
        skills_after = db.execute(
            "SELECT COUNT(*) AS c FROM skills"
        ).fetchone()["c"]
        ceo_row = db.execute(
            "SELECT email, role, active_status FROM users WHERE email = ?",
            ("ceo@ufitonline.net",),
        ).fetchone()
        # The wipe nukes audit_log too; confirm.
        audit_count = db.execute(
            "SELECT COUNT(*) AS c FROM audit_log"
        ).fetchone()["c"]

    assert org_count == 0
    assert skills_after == skills_before  # preserved
    assert ceo_row is not None
    assert ceo_row["role"] == "ceo"
    # active_status may be returned as 1 (SQLite) or True (Postgres) — both truthy.
    assert ceo_row["active_status"]
    assert audit_count == 0
