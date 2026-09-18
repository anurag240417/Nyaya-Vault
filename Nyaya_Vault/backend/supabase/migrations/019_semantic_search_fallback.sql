-- Lets the backend do semantic search without requiring the optional
-- pgvector extension: returns the same access-scoped chunk+embedding rows
-- that supabase/optional/pgvector.sql's native version would search over,
-- so app/services/embeddings.py's cosine_similarity() can rank them in
-- Python. Fine at small/medium scale; enable pgvector for anything larger
-- (see that file for the indexed version of this same query).
create or replace function public.backend_list_chunk_embeddings(
  p_case_ids uuid[] default null,
  p_clearance public.clearance_level default 'PUBLIC',
  p_limit integer default 2000
)
returns table(
  document_chunk_id uuid,
  document_id uuid,
  case_id uuid,
  case_number text,
  title text,
  page_number integer,
  chunk_text text,
  embedding_json jsonb
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  with latest as (
    select d.id as document_id, d.case_id, d.title, d.current_version_number
    from public.documents d
    where (p_case_ids is null or d.case_id = any(p_case_ids))
      and public.clearance_rank(d.clearance_level) <= public.clearance_rank(p_clearance)
  )
  select ch.id, l.document_id, l.case_id, c.case_number, l.title, ch.page_number, ch.chunk_text, de.embedding_json
  from latest l
  join public.cases c on c.id = l.case_id
  join public.document_versions dv on dv.document_id = l.document_id and dv.version_number = l.current_version_number
  join public.document_chunks ch on ch.document_version_id = dv.id
  join public.document_embeddings de on de.document_chunk_id = ch.id
  limit greatest(1, least(coalesce(p_limit, 2000), 5000));
$$;

revoke all on function public.backend_list_chunk_embeddings(uuid[],public.clearance_level,integer) from public, anon, authenticated;
grant execute on function public.backend_list_chunk_embeddings(uuid[],public.clearance_level,integer) to service_role;
