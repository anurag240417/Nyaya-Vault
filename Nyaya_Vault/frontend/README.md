# CaseVault React Frontend

GitHub-inspired React/Vite interface for the CaseVault FastAPI + Supabase stack.

## Important architecture

The frontend uses Supabase **only for Auth**. It does not query CaseVault tables, call business RPCs, or access the private evidence bucket. All business operations go through FastAPI, which owns authorization.

## Setup

```bash
cp .env.example .env
npm install
npm run dev
```

Set:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_ME
VITE_API_URL=http://localhost:8000
```

Never put the Supabase service-role key in this folder.

## Features

- Supabase email/password sign-up and sign-in
- GitHub-like private case workspaces
- case overview / documents / collaborators / audit tabs
- backend-controlled roles, assignment checks and clearance checks
- evidence upload and immutable versions
- SHA-256 metadata and secure downloads
- OCR/native text extraction + NER processing
- human entity confirmation
- redaction suggestions, human approval, true redacted PDF export
- backend-authorized search
- audit integrity verification
- admin user role/clearance/account controls
- Administration → Case Management: create + assign case, primary investigator, multiple collaborators, view assignments, reassign, and remove collaborators
