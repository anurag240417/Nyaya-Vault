# Nyaya Vault

A tamper-evident legal case management system built for **Smart India Hackathon 2026, Problem Statement 190** (secure document management for investigative case work).

Every piece of evidence is content-hashed and versioned immutably, every state-changing action is recorded in a hash-chained audit log, and access is gated by three independent axes — case membership, clearance level, and department — enforced in the backend, never trusted to the client.

---

## What it does

**Core case management**
- Case creation, collaborator assignment, and a case status lifecycle (`Under Investigation` → `Solved` / `Unsolved` / `Closed`), changeable only by an admin or the case's assigned Investigating Officer
- Evidence upload with SHA-256 hashing, immutable version history, and a hash-chained, append-only audit trail
- Three independent access axes: **role** (Admin / Investigating Officer / Prosecutor / Judge / Clerk), **clearance level** (Public → Restricted → Confidential → Secret), and **department** (Police / Forensics / Prosecution / Judiciary / General) — a case collaborator with sufficient clearance can still be blocked from a document tagged for a department they aren't in
- Evidence is organized into folders by type (FIR / Witness Statement / Evidence / Forensic Report / Charge Sheet), with only one *primary* FIR and one primary chargesheet per case — further uploads of either become new versions, not duplicates
- The same physical evidence file cannot be uploaded to two different cases (detected by content hash, not filename)
- Video (`.mp4`/`.mov`/`.webm`), PDF, and image evidence, all previewable inline in the browser — no download required

**OCR / NLP pipeline**
- Text extraction (native + OCR fallback) and named-entity recognition (people, locations, dates, FIR/case numbers, legal sections, phone numbers, vehicles) on every document
- Nothing extracted is trusted automatically — a human reviews and confirms or rejects every entity before it's used for anything else

**Contradiction detection ("Conflicts" tab)**
- A Google OR-Tools CP-SAT solver checks whether a person's reported locations and times can be jointly satisfied given travel time between locations — proving impossibility, not guessing at it
- Candidate statements are suggested automatically the moment entities are confirmed on a document (no manual "scan" step) by pairing confirmed PERSON + LOCATION + DATE facts within the same document
- A suggestion never counts as evidence until a human explicitly confirms it — confirmed statements are what the solver actually checks

**AI case assistant**
- Ask questions, generate an investigative summary, or get preliminary (BNS-referenced, explicitly non-authoritative) legal section suggestions — all grounded strictly in that case's own confirmed evidence, with citations, and a refusal to guess beyond what's actually in the case
- A separate, deterministic gap-checker (missing FIR/chargesheet, unresolved conflicts, pending reviews) runs with **zero AI calls** — these are exact, computable facts, not something to risk hallucinating
- Works with Anthropic, OpenAI, or any OpenAI-compatible endpoint (Groq, OpenRouter, a local model) — configurable, not hardcoded to one provider

**Document generation**
- **Section 63 certificates** (Bharatiya Sakshya Adhiniyam, 2023) for electronic evidence admissibility, with the required two-part device-operator/expert structure
- **16 legal notice types** (cheque bounce, eviction, defamation, consumer protection, trademark/copyright infringement, and more), each with the correct real statute cited where one genuinely applies — the system assembles verified case facts and structure; the substantive legal content is always written by the issuing officer, never fabricated by the system
- Both carry a visual issuance stamp (name, designation, department, timestamp) — explicitly labeled as **not** a cryptographic signature or a licensed Digital Signature Certificate under the IT Act, so nobody mistakes it for more legal weight than it has

**Object/scene detection** *(optional, off by default)*
- Self-hosted YOLO-based object detection for image and video evidence, behind an `ENABLE_VISION_ANALYSIS` flag — needs meaningfully more CPU/RAM than the base app, see [Deployment](#deployment) before enabling it anywhere but your own machine

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Database / Auth / Storage | Supabase (Postgres, Auth, Storage) — accessed only via the service-role key, never directly from the browser |
| OCR / NLP | pdfminer.six, PyMuPDF, pytesseract, spaCy |
| Contradiction detection | Google OR-Tools (CP-SAT) |
| AI assistant | Anthropic / OpenAI-compatible API (configurable) |
| Object detection *(optional)* | Ultralytics YOLO + OpenCV |
| Document generation | ReportLab |
| Frontend | React + Vite |
| Deployment | Render (backend), Vercel (frontend) |

---

## Architecture

```text
React (Vite)
  │ Supabase sign-in only — the browser never talks to Supabase's
  │ database or storage APIs directly
  │ receives a user access token
  ▼
FastAPI
  ├─ validates the token with Supabase Auth
  ├─ loads the profile using the server-only service-role key
  ├─ enforces role + case assignment + clearance + department
  ├─ OCR / NER / redaction / hashing / OR-Tools / AI assistant / PDF generation
  └─ trusted DB & private Storage calls only
        ▼
     Supabase
     Auth + PostgreSQL + Storage
```

`backend/supabase/migrations/003_backend_only_access.sql` explicitly revokes browser access to every business table, RPC, and Storage bucket — authorization cannot be bypassed by calling Supabase directly with the frontend's publishable key, even by someone reading the client-side code.

Every MIME-type restriction (e.g. for video support) is enforced independently in **four separate places** — Python's own validation, two Postgres RPC functions, the Storage bucket's configuration, and a table-level `CHECK` constraint — by design, not accident: this is defense in depth, but it means adding a new evidence type touches all four.

---

## Project structure

```
Nyaya_Vault/
├── backend/
│   ├── app/
│   │   ├── main.py                 — FastAPI app factory, router registration
│   │   ├── api/                    — routes/ (one file per resource) + deps.py
│   │   ├── core/                   — config.py (Settings), exceptions.py, models.py (enums)
│   │   ├── integrations/           — supabase.py (the only thing that talks to Supabase)
│   │   ├── schemas/                — pydantic request/response models
│   │   ├── security/                — JWT validation
│   │   └── services/                — business logic (casevault, authorization, timeline,
│   │                                  assistant, certificate_builder, notice_builder,
│   │                                  vision, processor, ocr, ner, ...)
│   ├── supabase/migrations/        — run in numeric order, 001 through 016
│   ├── supabase/BOOTSTRAP_ADMIN.sql — one-time: promote your first account to ADMIN
│   ├── requirements.txt            — core dependencies
│   ├── requirements-ml.txt          — optional: semantic embeddings
│   └── requirements-vision.txt      — optional: object/scene detection (heavy - see below)
└── frontend/
    └── src/
        ├── pages/                   — one file per route (CasePage.jsx and DocumentPage.jsx
        │                              are the largest)
        ├── components/               — shared UI (modals, badges, the case tab bar, ...)
        ├── lib/api.js                — every backend call lives here
        └── context/AuthContext.jsx   — session + profile
```

---

## Setup

1. **Create a Supabase project.** Create a **private** Storage bucket named `case-documents`.
2. **Run every migration in `backend/supabase/migrations/` in numeric order** (001 → 016) via the Supabase SQL editor or CLI. Re-run this after pulling any change that adds a new migration file.
3. **Backend** — Python **3.12** specifically (3.14 has no prebuilt wheels yet for some dependencies):
   ```bash
   cd backend
   python3.12 -m venv venv
   source venv/bin/activate   # venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
   Copy `backend/.env.example` → `backend/.env` and fill in your Supabase project URL/keys. Never commit `.env` — if a real key ever ends up in a shared file, rotate it immediately, don't just delete the file.
4. **Run the backend:**
   ```bash
   uvicorn app.main:app --reload
   ```
5. **Bootstrap your first admin.** Sign up once through the frontend (new accounts default to `CLERK` / `PUBLIC` clearance), then run `backend/supabase/BOOTSTRAP_ADMIN.sql` with that account's email filled in.
6. **Frontend:**
   ```bash
   cd frontend
   npm install
   ```
   Copy `frontend/.env.example` → `frontend/.env`, set `VITE_API_URL` to your backend's URL, then:
   ```bash
   npm run dev
   ```

### Optional features

| Feature | Env var | Extra install |
|---|---|---|
| AI assistant | `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`) | none — already in `requirements.txt` |
| Semantic search | `ENABLE_SEMANTIC_EMBEDDINGS=true` | `pip install -r requirements-ml.txt` |
| Object/scene detection | `ENABLE_VISION_ANALYSIS=true` | `pip install -r requirements-vision.txt` — **do not enable on a free-tier host**, needs real CPU/RAM (~1-2GB for `torch` alone); test locally first |

---

## Testing

```bash
cd backend
pytest tests/ -q
```

100 tests, all passing against an in-memory fake of the Supabase gateway. **This proves the application logic is correct — it does not prove your real Supabase project is configured correctly.** Several bugs in this project were only ever discoverable against a real Postgres database (a table-level `CHECK` constraint, a Storage bucket's own MIME whitelist, an enum missing a value) — passing tests here is necessary, not sufficient. After any schema change, verify against your actual Supabase project too.

A handful of tests (`test_mime_whitelist_consistency.py`, `test_audit_action_enum_consistency.py`) are purely static — they parse the migration files and the application code and fail if they ever disagree, closing exactly that gap without needing a database connection.

---

## Deployment

- **Backend (Render):** set every env var from `backend/.env.example` in the Render dashboard, plus `CORS_ORIGINS` including your exact Vercel domain(s). Render's free tier (512MB RAM) runs the base app fine but **cannot** run object detection — see the table above.
- **Frontend (Vercel):** set `VITE_API_URL` to your Render backend's public URL. `frontend/vercel.json` provides the SPA rewrite needed for client-side routing to survive a direct page refresh — without it, refreshing on any route other than `/` 404s.
- After deploying, re-run the migrations against your **production** Supabase project specifically — a local/dev Supabase project being up to date says nothing about production.

---

## Honest limitations

Stated plainly rather than discovered the hard way:

- **The "digital signature" on certificates and notices is a visual stamp, not cryptography.** It carries the same legal weight as a typed name — it is explicitly not a licensed Digital Signature Certificate under India's IT Act, 2000, and the document itself says so.
- **Object/scene detection uses stock COCO classes (80 general categories).** There is no firearm-specific class in the standard dataset — this is general object detection, not a weapons detector, and is never presented as one.
- **The AI assistant will not identify itself as more certain than its context supports.** It's grounded strictly in that case's own confirmed data and is explicitly told to say "I don't know" rather than guess — but it is still a language model, not a source of legal truth, and its legal-section suggestions are always framed as preliminary.
- **Legal notice content is never authored by the system.** The 16 notice templates assemble verified case data and, where genuinely applicable, the correct real statute name — the actual grounds, allegations, and demand are always written by the issuing officer.
