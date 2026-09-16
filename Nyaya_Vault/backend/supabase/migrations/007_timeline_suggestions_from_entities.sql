alter table public.case_timeline_statements
  add column if not exists status text not null default 'CONFIRMED'
    check (status in ('SUGGESTED', 'CONFIRMED')),
  add column if not exists page_number integer check (page_number is null or page_number >= 1);

create index if not exists case_timeline_statements_case_status_idx
  on public.case_timeline_statements(case_id, status);

-- Existing rows (all manually entered before this migration) are already
-- CONFIRMED by the column default above - no backfill needed.