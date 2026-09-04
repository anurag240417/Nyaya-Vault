# Assignment visibility fix

This build fixes stale collaborator case visibility in the React UI.

- Dashboard and Cases refetch when the tab/window becomes active again.
- Cases has an explicit Refresh button.
- No background polling is used.
- Backend regression coverage now proves that newly assigned users can list the case immediately, and removed users lose it immediately.
- No new Supabase migration is required for this fix. Migration 005 remains the latest schema migration.
