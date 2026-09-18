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
2. In SQL Editor, run every file in `supabase/migrations/` **in numeric order** (currently `001_casevault_core.sql` through `019_semantic_search_fallback.sql`). Every file is written to be safe to re-run (`if not exists` / `create or replace` throughout), so re-running the whole set on an already-migrated database is harmless.
3. Optional indexed semantic search: run `supabase/optional/pgvector.sql` and install `requirements-ml.txt` — see "Semantic search" below. Without it, semantic search still works via a pure-Python fallback once `ENABLE_SEMANTIC_EMBEDDINGS=true`, just not index-accelerated.
4. Optional blockchain anchoring of the audit chain: see "Blockchain-anchored audit integrity" below — off by default, no setup required unless you want it.
5. Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and the server-only `SUPABASE_SECRET_KEY`. Legacy anon/service-role keys are also supported.
6. Install and run:

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
- `/api/v1/search` – backend-authorized full-text search, blended with semantic search when enabled (see "Semantic search" below)
- `/api/v1/activity` – ACL-filtered recent activity
- `/api/v1/integrity/verify` – audit-chain verification
- `/api/v1/integrity/anchors` – list existing blockchain anchors (`GET`) / create a new one (`POST`, ADMIN only)
- `/api/v1/integrity/anchors/{id}/verify` – re-fetch one anchor's transaction from the chain and confirm the live database still matches it
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

## Blockchain-anchored audit integrity

The audit log (`audit_logs`) is already a hash-chained, append-only ledger inside Postgres — each row's hash depends on the previous row's hash, so altering any past row breaks every hash after it, and DB triggers block `UPDATE`/`DELETE` on the table outright. `GET /api/v1/integrity/verify` walks that chain and reports whether it's still internally consistent.

That check has one honest gap: it only proves the chain is *internally* consistent, using the same database that a `service_role`-level compromise could rewrite in one coordinated edit. **Blockchain anchoring** closes that gap by periodically recording the chain's current head (`sequence` + `entry_hash`) in a transaction on a public blockchain (Polygon Amoy testnet by default) — no smart contract, the transaction's plain-text `data` field is the permanent, publicly-readable record (`NYAYAVAULT-ANCHOR-V1:{sequence}:{entry_hash}`). Anyone can later re-fetch that exact transaction straight from the chain (not from this database) and compare it against the live `audit_logs` row at that sequence — a mismatch means the database was altered after the anchor was made.

See `app/services/blockchain_anchor.py` for the implementation and its documented limits (this anchors and lets tampering be *detected*; it is one backend writing to a chain it doesn't otherwise control, not a decentralized consensus ledger).

**Off by default** (`ENABLE_BLOCKCHAIN_ANCHOR=false`) — creating anchors needs a funded testnet wallet. To enable it:

1. Get a free RPC endpoint for Polygon Amoy. The public `https://polygon-amoy.drpc.org` works with no signup (alternatives: `https://polygon-amoy-bor-rpc.publicnode.com`, `https://polygon-amoy.gateway.tenderly.co`); a paid provider (Alchemy/Infura) is more reliable under load but not required.
2. Create a **throwaway** wallet (e.g. a new account in the MetaMask browser extension) — never reuse one holding anything of real value, since its private key lives in a plaintext `.env` file.
3. Fund that wallet's address with free testnet MATIC/POL from `https://faucet.polygon.technology` (select the Amoy network).
4. Export that account's private key (MetaMask: account menu → Account details → Show private key) and set, in `.env`:
   ```
   ENABLE_BLOCKCHAIN_ANCHOR=true
   BLOCKCHAIN_RPC_URL=https://polygon-amoy.drpc.org
   BLOCKCHAIN_PRIVATE_KEY=0xyour_private_key
   ```
   (`BLOCKCHAIN_CHAIN_ID`, `BLOCKCHAIN_NETWORK_NAME`, and `BLOCKCHAIN_EXPLORER_TX_BASE_URL` already default correctly for Amoy — only override them for a different network.)
5. Restart the backend. On the frontend's Integrity page, an ADMIN will now see an "Anchor now" button instead of a "not configured" notice; anyone can list anchors and verify one against the live chain.

Migration `017_blockchain_anchor_support.sql` adds the columns/RPC this needs on top of the `integrity_anchors` table that already existed. `web3` and `eth-account` (installed transitively) are the only new dependencies, both in `requirements.txt`.

## Semantic search

`/api/v1/search` runs keyword (PostgreSQL full-text) and semantic (embedding similarity) search side by side and blends the two result lists by **reciprocal rank fusion** — each result's final score is based on where it *placed* in each list, not a raw comparison of a text-relevance score against a cosine similarity (which aren't on comparable scales). A result near the top of both lists outranks one that only appears in one. With semantic search off (the default), this reduces to exactly the previous keyword-only ordering.

Each result carries a `matched_by` field (`keyword`, `semantic`, or `both`) so the frontend can show which kind of match it was — the Search page renders a "Semantic match" / "Keyword + semantic" badge whenever semantic search contributed.

**Off by default.** Turning it on:

1. `ENABLE_SEMANTIC_EMBEDDINGS=true` and install `requirements-ml.txt` — computes and stores an embedding for every chunk as it's processed. Without this there's nothing for semantic search to search.
2. Choose how the *query itself* gets matched against those stored embeddings:
   - **Pure-Python fallback** (`ENABLE_PGVECTOR_SEARCH=false`, the default once embeddings are on): `app/services/embeddings.py`'s `cosine_similarity()` ranks a bounded candidate set (`SEMANTIC_SEARCH_CANDIDATE_LIMIT`, default 2000 chunks) in the backend process. No extra setup, genuinely does semantic ranking, but doesn't scale past small/medium document volume.
   - **pgvector** (`ENABLE_PGVECTOR_SEARCH=true`): run `supabase/optional/pgvector.sql` first — it adds a native `vector(384)` column with an HNSW index and a `backend_semantic_search_casevault` RPC that does the same ranking as an indexed SQL query instead of in Python. Once this is on, newly-processed documents also get that native column populated (`app/services/processor.py`); documents processed *before* it was enabled won't have it until reprocessed, and the indexed query correctly skips them rather than erroring.
3. Matches below `SEMANTIC_SIMILARITY_THRESHOLD` (default `0.35`) are dropped from the semantic side entirely — an unrelated sentence scoring near zero isn't a "match," it's noise that would otherwise get merged in as one.
