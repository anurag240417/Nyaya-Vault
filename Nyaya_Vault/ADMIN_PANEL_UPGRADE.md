# Admin Panel Upgrade

## New Administration structure

```text
Administration
├── Users
│   ├── Role
│   ├── Clearance
│   └── Active / Disabled
│
└── Case Management
    ├── Create & assign case
    ├── Select primary investigating officer
    ├── Select multiple collaborators
    ├── View assigned users
    ├── Reassign primary investigator / collaborators
    └── Remove additional collaborators
```

## Existing database

If you already ran migrations 001 through 004, run only this new migration in Supabase SQL Editor:

```text
backend/supabase/migrations/005_admin_case_management.sql
```

Then restart FastAPI and the Vite frontend. No existing case, document, audit, or user data is removed.

## Authorization

All endpoints under `/api/v1/admin/*` require an active `ADMIN`. The frontend never receives the Supabase secret/service-role key. Assignment writes are transactional backend-only Supabase RPCs called by FastAPI.

The case creator is kept in `case_assignments` for provenance. The primary investigating officer and additional collaborators can be reassigned by an admin.
