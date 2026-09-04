# CaseVault FastAPI Backend

Trusted backend for the GitHub-inspired CaseVault React application. Supabase provides **Auth, PostgreSQL, and private Storage**. FastAPI is the application authorization boundary.

## Security boundary

The browser uses Supabase only to create/sign into an account and obtain an access token. Every business request is sent to FastAPI with that token. FastAPI validates the token with Supabase Auth, loads the server-side profile through the server-only Supabase secret/service-role capability, then enforces:

- active account
- role (`ADMIN`, `INVESTIGATING_OFFICER`, `PROSECUTOR`, `JUDGE`, `CLERK`)
- case assignment
- collaborator-management rules
- document clearance (`PUBLIC` → `SECRET`)
- immutable evidence versioning and SHA-256 verification

`SUPABASE_SECRET_KEY` is server-only (legacy `SUPABASE_SERVICE_ROLE_KEY` is also supported). The backend-only migration revokes browser access to CaseVault tables, business RPCs, and evidence Storage objects.

## Fresh setup

1. Create a Supabase project.
2. In SQL Editor, run these in order:
   - `supabase/migrations/001_casevault_core.sql`
   - `supabase/migrations/002_backend_support.sql`
   - `supabase/migrations/003_backend_only_access.sql`
   - `supabase/migrations/004_backend_api_rpcs.sql`
   - `supabase/migrations/005_admin_case_management.sql`
3. Optional semantic-vector storage: run `supabase/optional/pgvector.sql` and install `requirements-ml.txt`.
4. Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and the server-only `SUPABASE_SECRET_KEY`. Legacy anon/service-role keys are also supported.
5. Install and run:

```bash
# Python 3.12 is recommended (and required by the pinned Windows wheels)
py -3.12 -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload --port 8000
```

For scanned PDFs/images, Tesseract and Poppler are required. The Dockerfile installs them automatically.

## First admin

Create the first account from the frontend. Then run `supabase/BOOTSTRAP_ADMIN.sql` in Supabase SQL Editor after replacing the email placeholder. New users otherwise start as `CLERK / PUBLIC`.

## Main API groups

- `/api/v1/auth/*` – backend identity/profile context
- `/api/v1/cases/*` – cases, collaborators, case documents, case audit
- `/api/v1/users/*` – admin authorization management
- `/api/v1/admin/cases*` – admin case creation, primary investigator selection, and atomic reassignment
- `/api/v1/documents/*` – evidence, versions, processing, reviews, redacted export
- `/api/v1/search` – backend-authorized PostgreSQL full-text search
- `/api/v1/activity` – ACL-filtered recent activity
- `/api/v1/integrity/verify` – audit-chain verification
- `/health`, `/docs`

## Tests

```bash
pytest -q
```

The supplied end-to-end suite uses an in-memory Supabase gateway and exercises auth context, case ACLs, collaborator authorization, document clearance, immutable uploads/versions/downloads, native PDF extraction, deterministic NER, human confirmation, redaction generation/approval/export, admin controls, audit, and integrity.


## Existing installations: Admin Case Management upgrade

If migrations `001` through `004` are already applied, run only:

```text
supabase/migrations/005_admin_case_management.sql
```

This adds `cases.primary_investigator_id` plus backend-only transactional RPCs for creating a case with assignments and replacing a case's assignment set. The case creator is always retained as an assignment for provenance, while the primary investigator and additional collaborators can be changed by an active ADMIN.
