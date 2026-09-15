from __future__ import annotations

import re
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_MIGRATIONS_DIR = _BACKEND_ROOT / "supabase" / "migrations"
_CASEVAULT_PY = _BACKEND_ROOT / "app" / "services" / "casevault.py"

_MIME_RE = re.compile(r"'([a-z]+/[a-z0-9.+-]+)'")


def _python_allowed_mimes() -> set[str]:
    text = _CASEVAULT_PY.read_text()
    match = re.search(r"_ALLOWED_MIME\s*=\s*\{([^}]*)\}", text, re.DOTALL)
    assert match, "Could not find _ALLOWED_MIME in casevault.py - has it been renamed?"
    return set(re.findall(r'"([a-z]+/[a-z0-9.+-]+)"', match.group(1)))


def _document_versions_column_check_mimes() -> set[str] | None:
    """The document_versions.mime_type CHECK constraint's own allowed list -
    a FOURTH independent gate, sitting at the actual table insert, after
    Python, the RPC functions, and Storage have all already let a request
    through. Scans for the original inline column check (migration 001) and
    any later `add constraint ... check (mime_type in (...))` that replaces
    it, taking whichever was declared last in migration order.
    """
    last_seen: set[str] | None = None
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        text = sql_file.read_text()
        for stmt_match in re.finditer(
            r"mime_type\s+text\s+not\s+null\s+check\s*\(mime_type\s+in\s*\(([^)]*)\)\)|"
            r"check\s*\(mime_type\s+in\s*\(([^)]*)\)\)",
            text, re.IGNORECASE,
        ):
            group = stmt_match.group(1) or stmt_match.group(2)
            if group:
                last_seen = set(_MIME_RE.findall(group))
    return last_seen


def test_document_versions_check_constraint_covers_every_python_allowed_type():
    """Regression test for a real, reported bug: video upload failed with
    'new row for relation "document_versions" violates check constraint
    "document_versions_mime_type_check"' - a fourth independent gate, this
    one a table-level CHECK constraint, found only after the other three
    (Python, the RPC functions, the Storage bucket) were already fixed and
    confirmed working, because this one sits last in the chain.
    """
    python_mimes = _python_allowed_mimes()
    constraint_mimes = _document_versions_column_check_mimes()
    assert constraint_mimes is not None, (
        "Could not find the document_versions.mime_type CHECK constraint in any "
        "migration - the parser may be broken, or the constraint definition moved."
    )
    missing = python_mimes - constraint_mimes
    assert not missing, (
        f"The document_versions.mime_type CHECK constraint is narrower than "
        f"Python's _ALLOWED_MIME - an insert would be rejected at the database "
        f"level even after passing every other check: {sorted(missing)}. Add a "
        f"migration that drops and recreates document_versions_mime_type_check "
        f"with the full current list."
    )


def _rpc_whitelisted_mimes_per_function() -> dict[str, set[str]]:
    """Every 'p_mime_type not in (...)' whitelist, keyed by the name of the
    function it appears in, across every migration file - scoped to
    backend_-prefixed functions only, since those are the ones actually
    invoked by casevault.py. The legacy register_document_upload/_version
    (no prefix, from migration 001) are dead code - locked down by
    migration 003's blanket `revoke execute ... from authenticated` and
    never called from Python - so they're deliberately excluded here
    rather than flagged as a false-positive "bug" every test run."""
    results: dict[str, set[str]] = {}
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        text = sql_file.read_text()
        current_function = None
        for line in text.splitlines():
            fn_match = re.match(r"create (?:or replace )?function public\.(backend_\w+)", line.strip(), re.IGNORECASE)
            if fn_match:
                current_function = fn_match.group(1)
            elif re.match(r"create (?:or replace )?function public\.\w+", line.strip(), re.IGNORECASE):
                current_function = None  # a different (non-backend_) function started
            if "p_mime_type not in" in line and current_function:
                # Later migrations redefining the same function name replace
                # its whitelist entirely - this reflects the real deployed
                # state after all migrations run in order.
                results[current_function] = set(_MIME_RE.findall(line))
    return results


def _storage_bucket_allowed_mimes() -> set[str] | None:
    """The case-documents Storage bucket's own allowed_mime_types array -
    a THIRD independent gate, enforced by Supabase Storage's API itself,
    separate from both Python's _ALLOWED_MIME and the RPC functions'
    whitelists. Scans every migration for either the original bucket
    creation (insert into storage.buckets(...)) or a later update to it,
    and returns whichever was declared last in migration order - that's
    the state a real deployment ends up in after all migrations run.
    Returns None if no bucket declaration is found at all (parser problem,
    not "no restriction").
    """
    last_seen: set[str] | None = None
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        text = sql_file.read_text()
        for stmt_match in re.finditer(
            r"(?:insert into storage\.buckets[^;]*?case-documents[^;]*?|"
            r"update storage\.buckets\s+set\s+allowed_mime_types\s*=\s*array\[[^\]]*\][^;]*?case-documents[^;]*?);",
            text, re.IGNORECASE | re.DOTALL,
        ):
            stmt = stmt_match.group(0)
            array_match = re.search(r"array\[([^\]]*)\]", stmt, re.IGNORECASE)
            if array_match:
                last_seen = set(_MIME_RE.findall(array_match.group(1)))
    return last_seen


def test_storage_bucket_mime_whitelist_covers_every_python_allowed_type():
    """Regression test for a real, reported bug: a video upload rejected
    with 'mime type video/mp4 is not supported' even after both the Python
    check and the RPC functions' checks were already fixed to allow it.
    Root cause: the case-documents Storage bucket itself was created with
    its own allowed_mime_types array (migration 001), enforced by Supabase
    Storage's API before any backend code runs at all - a third,
    independent gate neither of the other two fixes touched.
    """
    python_mimes = _python_allowed_mimes()
    bucket_mimes = _storage_bucket_allowed_mimes()
    assert bucket_mimes is not None, (
        "Could not find the case-documents bucket's allowed_mime_types declaration "
        "in any migration - the parser may be broken, or the bucket setup itself moved."
    )
    missing = python_mimes - bucket_mimes
    assert not missing, (
        f"The case-documents Storage bucket's allowed_mime_types is narrower than "
        f"Python's _ALLOWED_MIME - Supabase Storage itself will reject these before "
        f"any application code runs: {sorted(missing)}. Add a migration with "
        f"`update storage.buckets set allowed_mime_types = array[...] where id = "
        f"'case-documents';` including the full current list."
    )


def test_rpc_mime_whitelists_cover_every_python_allowed_type():
    """Regression test for: video upload passing Python validation, then
    failing at backend_register_document_upload/_version with 'Unsupported
    file type' against real Postgres - because those RPCs enforce their
    OWN independent whitelist that Python's _ALLOWED_MIME doesn't touch.
    The fake-gateway test suite can't catch this (it doesn't model these
    RPC bodies at all), so this checks the SQL text statically instead.
    """
    python_mimes = _python_allowed_mimes()
    per_function = _rpc_whitelisted_mimes_per_function()
    assert per_function, "Could not find any RPC mime-type whitelist at all - the parser may be broken."

    problems = []
    for function_name, rpc_mimes in per_function.items():
        missing = python_mimes - rpc_mimes
        if missing:
            problems.append(f"{function_name}: missing {sorted(missing)}")

    assert not problems, (
        "These RPC functions have a mime-type whitelist narrower than Python's "
        "_ALLOWED_MIME - a file type Python accepts would be uploaded to Storage "
        "and then rejected at the RPC step against real Postgres:\n"
        + "\n".join(problems)
    )