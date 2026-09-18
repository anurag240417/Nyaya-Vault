# CaseVault Full Stack

Two replacement-ready folders:

- `frontend/` — React + JavaScript + Vite, GitHub-inspired UI
- `backend/` — FastAPI trusted API, Supabase Auth/Postgres/Storage integration

## Request flow

```text
React
  │ Supabase sign-in only
  │ receives user access token
  ▼
FastAPI
  ├─ validates token with Supabase Auth
  ├─ loads profile using the server-only Supabase secret/service-role capability
  ├─ enforces role + case assignment + document clearance
  ├─ OCR / NER / redaction / hashing
  └─ trusted DB & private Storage calls
        ▼
     Supabase
     Auth + PostgreSQL + Storage
```

The migration `backend/supabase/migrations/003_backend_only_access.sql` explicitly revokes browser access to CaseVault business tables/RPCs/Storage, so authorization cannot be bypassed by calling Supabase directly with the frontend publishable key.

Start with `backend/README.md`, then `frontend/README.md`.


## Administration → Case Management

The ADMIN console now contains two tabs:

- **Users** — role, clearance, active/disabled state
- **Case Management** — create + assign cases, select a primary investigating officer, select multiple collaborators, view current assignments, reassign the primary/collaborators, and remove additional collaborators

For an existing database that already has migrations 001–004, run `backend/supabase/migrations/005_admin_case_management.sql` before using the new Case Management tab.

## Integrity → Blockchain-anchored audit proof

The Integrity page's audit-chain hash is a database-resident, tamper-evident log on its own, but a `service_role`-level compromise of the database alone could still rewrite it undetected. To close that gap, an ADMIN can periodically **anchor** the chain's current hash to a public blockchain (Polygon Amoy testnet by default) — no smart contract, just the hash embedded in a real transaction's data field. Anyone can later independently re-fetch that transaction from the chain and confirm the live database still matches it.

This is off by default (`ENABLE_BLOCKCHAIN_ANCHOR=false`) and needs a funded testnet wallet to enable — see `backend/README.md` → "Blockchain-anchored audit integrity" for the full setup walkthrough.
