from __future__ import annotations

import re
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_MIGRATIONS_DIR = _BACKEND_ROOT / "supabase" / "migrations"
_APP_DIR = _BACKEND_ROOT / "app"

_ENUM_VALUE_RE = re.compile(r"'([A-Z_]+)'")


def _declared_audit_actions() -> set[str]:
    """Every value the audit_action enum actually has, across the original
    CREATE TYPE list and every later ALTER TYPE ... ADD VALUE migration."""
    declared: set[str] = set()
    for sql_file in _MIGRATIONS_DIR.glob("*.sql"):
        text = sql_file.read_text()
        for block in re.finditer(r"audit_action[^;]*?\([^)]*\)", text, re.IGNORECASE | re.DOTALL):
            declared.update(_ENUM_VALUE_RE.findall(block.group(0)))
        for line in text.splitlines():
            if "add value" in line.lower() and "audit_action" in line.lower():
                declared.update(_ENUM_VALUE_RE.findall(line))
    return declared


def _actions_used_in_code() -> set[str]:
    """Every action="X" literal actually passed to append_audit_service /
    append_audit_entry anywhere in the app - the exact set that must be a
    subset of what the real Postgres enum accepts, or a live deployment
    500s the moment that code path runs (this is precisely what happened:
    passing tests against the fake gateway never enforce this, since it
    doesn't model Postgres enum constraints at all)."""
    used: set[str] = set()
    action_re = re.compile(r'action\s*=\s*"([A-Z_]+)"')
    for py_file in _APP_DIR.rglob("*.py"):
        used.update(action_re.findall(py_file.read_text()))
    return used


def test_every_audit_action_used_in_code_is_declared_in_migrations():
    """Regression test for: 'invalid input value for enum audit_action:
    ...' - a real-Postgres-only error the fake-gateway suite structurally
    cannot catch on its own. This closes the gap by comparing the SQL
    migrations' declared values against actual code usage statically, with
    no database connection required."""
    declared = _declared_audit_actions()
    used = _actions_used_in_code()
    assert declared, "Sanity check failed - couldn't find any declared audit_action values at all; the parser itself may be broken."
    missing = used - declared
    assert not missing, (
        f"These audit_action values are used in app code but never declared in any "
        f"migration - add `alter type public.audit_action add value if not exists '...'` "
        f"for each in a new migration: {sorted(missing)}"
    )