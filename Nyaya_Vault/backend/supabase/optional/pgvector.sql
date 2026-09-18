-- Optional: native pgvector column for semantic search.
-- The core app works without this migration using PostgreSQL full-text search.
-- The supplied processor contract expects 384-dimensional embeddings if you enable it.

begin;
create extension if not exists vector with schema extensions;

alter table public.document_embeddings
  add column if not exists embedding extensions.vector(384);

create index if not exists document_embeddings_hnsw_idx
  on public.document_embeddings
  using hnsw (embedding extensions.vector_cosine_ops);

-- Indexed semantic search: same access scoping (case membership + clearance)
-- as backend_search_casevault's full-text search, ranked by cosine distance
-- instead of text relevance. app/services/casevault.py calls this one when
-- ENABLE_PGVECTOR_SEARCH=true, and blends its results with the full-text
-- ones (reciprocal rank fusion) rather than using either alone.
create or replace function public.backend_semantic_search_casevault(
  p_query_embedding extensions.vector(384),
  p_case_ids uuid[] default null,
  p_clearance public.clearance_level default 'PUBLIC',
  p_limit integer default 50
)
returns table(
  document_id uuid,
  case_id uuid,
  case_number text,
  title text,
  page_number integer,
  snippet text,
  similarity real
)
language plpgsql
stable
security definer
set search_path = public, extensions, pg_temp
as $$
begin
  return query
  with latest as (
    select d.id as document_id, d.case_id, d.title, d.current_version_number
    from public.documents d
    where (p_case_ids is null or d.case_id = any(p_case_ids))
      and public.clearance_rank(d.clearance_level) <= public.clearance_rank(p_clearance)
  )
  select l.document_id, l.case_id, c.case_number, l.title, ch.page_number,
         left(regexp_replace(ch.chunk_text, E'[\\n\\r\\t]+', ' ', 'g'), 320) as snippet,
         (1 - (de.embedding <=> p_query_embedding))::real as similarity
  from latest l
  join public.cases c on c.id = l.case_id
  join public.document_versions dv on dv.document_id = l.document_id and dv.version_number = l.current_version_number
  join public.document_chunks ch on ch.document_version_id = dv.id
  join public.document_embeddings de on de.document_chunk_id = ch.id
  where de.embedding is not null
  order by de.embedding <=> p_query_embedding
  limit greatest(1, least(coalesce(p_limit, 50), 100));
end;
$$;

revoke all on function public.backend_semantic_search_casevault(extensions.vector,uuid[],public.clearance_level,integer) from public, anon, authenticated;
grant execute on function public.backend_semantic_search_casevault(extensions.vector,uuid[],public.clearance_level,integer) to service_role;

commit;
