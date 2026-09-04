-- CaseVault trusted-backend support.
-- Run after 001_casevault_core.sql. Safe to re-run.

begin;

-- A short DB lease prevents two API replicas from OCR-processing the same
-- immutable version concurrently. Browser clients receive no grants here.
create table if not exists public.document_processing_jobs (
  version_id uuid primary key references public.document_versions(id) on delete cascade,
  worker_id text,
  status text not null default 'IDLE' check (status in ('IDLE','RUNNING','SUCCEEDED','FAILED')),
  lease_expires_at timestamptz,
  attempts integer not null default 0 check (attempts >= 0),
  last_error text,
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.document_processing_jobs enable row level security;
revoke all on table public.document_processing_jobs from public, anon, authenticated;
grant select, insert, update, delete on table public.document_processing_jobs to service_role;

create or replace function public.claim_document_processing(
  p_version_id uuid,
  p_worker_id text,
  p_lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_claimed boolean := false;
begin
  if p_version_id is null or nullif(btrim(p_worker_id),'') is null then
    return false;
  end if;

  insert into public.document_processing_jobs(
    version_id, worker_id, status, lease_expires_at, attempts, started_at, finished_at, last_error, updated_at
  ) values (
    p_version_id, p_worker_id, 'RUNNING', now() + make_interval(secs => greatest(30, least(p_lease_seconds, 3600))),
    1, now(), null, null, now()
  )
  on conflict (version_id) do update
  set worker_id = excluded.worker_id,
      status = 'RUNNING',
      lease_expires_at = excluded.lease_expires_at,
      attempts = public.document_processing_jobs.attempts + 1,
      started_at = now(),
      finished_at = null,
      last_error = null,
      updated_at = now()
  where public.document_processing_jobs.status <> 'RUNNING'
     or public.document_processing_jobs.lease_expires_at is null
     or public.document_processing_jobs.lease_expires_at < now()
  returning true into v_claimed;

  return coalesce(v_claimed, false);
end;
$$;

create or replace function public.finish_document_processing(
  p_version_id uuid,
  p_worker_id text,
  p_succeeded boolean,
  p_error text default null
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_count integer;
begin
  update public.document_processing_jobs
  set status = case when p_succeeded then 'SUCCEEDED' else 'FAILED' end,
      lease_expires_at = null,
      last_error = case when p_succeeded then null else left(coalesce(p_error,'Processing failed.'), 1000) end,
      finished_at = now(),
      updated_at = now()
  where version_id = p_version_id and worker_id = p_worker_id;
  get diagnostics v_count = row_count;
  return v_count = 1;
end;
$$;

revoke all on function public.claim_document_processing(uuid,text,integer) from public, anon, authenticated;
revoke all on function public.finish_document_processing(uuid,text,boolean,text) from public, anon, authenticated;
grant execute on function public.claim_document_processing(uuid,text,integer) to service_role;
grant execute on function public.finish_document_processing(uuid,text,boolean,text) to service_role;

-- The processor needs tightly-scoped direct mutation rights. These grants do
-- not apply to browser JWTs; service_role must never be shipped to React.
grant select on table public.profiles, public.cases, public.documents, public.document_versions to service_role;
grant select, insert, update, delete on table public.document_entities to service_role;
grant select, insert, update, delete on table public.document_chunks to service_role;
grant select, insert, update, delete on table public.document_embeddings to service_role;
grant select, insert, update, delete on table public.redaction_suggestions to service_role;
grant update on table public.document_versions to service_role;
grant execute on function public.append_audit_entry(uuid,uuid,uuid,public.audit_action,public.audit_result,text,jsonb) to service_role;

-- User-scoped semantic candidate RPC. It never returns an embedding for a
-- document that the caller cannot access. The Python service performs cosine
-- ranking; install 002_optional_pgvector.sql later for a native ANN index.
create or replace function public.semantic_search_candidates(
  p_case_id uuid default null,
  p_limit integer default 1000
)
returns table(
  document_id uuid,
  document_version_id uuid,
  document_title text,
  case_id uuid,
  case_number text,
  chunk_index integer,
  chunk_text text,
  embedding_json jsonb,
  model_name text
)
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select
    d.id,
    dv.id,
    d.title,
    c.id,
    c.case_number,
    dc.chunk_index,
    dc.chunk_text,
    de.embedding_json,
    de.model_name
  from public.document_embeddings de
  join public.document_chunks dc on dc.id = de.document_chunk_id
  join public.document_versions dv on dv.id = dc.document_version_id
  join public.documents d on d.id = dv.document_id
  join public.cases c on c.id = d.case_id
  where public.can_access_document(d.id)
    and (p_case_id is null or d.case_id = p_case_id)
  order by dv.created_at desc, dc.chunk_index asc
  limit greatest(1, least(coalesce(p_limit,1000),5000));
$$;

revoke all on function public.semantic_search_candidates(uuid,integer) from public, anon;
grant execute on function public.semantic_search_candidates(uuid,integer) to authenticated;

commit;
