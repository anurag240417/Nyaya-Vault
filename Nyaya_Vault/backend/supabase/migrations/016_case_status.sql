-- Case status: UNDER_INVESTIGATION (default - every case starts here),
-- SOLVED, UNSOLVED, CLOSED. A separate axis from case_assignments/
-- clearance/department - this tracks the case's own lifecycle, not who
-- can see it or what evidence it contains.

do $$ begin
  create type public.case_status as enum (
    'UNDER_INVESTIGATION', 'SOLVED', 'UNSOLVED', 'CLOSED'
  );
exception when duplicate_object then null; end $$;

alter table public.cases
  add column if not exists status public.case_status not null default 'UNDER_INVESTIGATION';

alter type public.audit_action add value if not exists 'CASE_STATUS_CHANGED';