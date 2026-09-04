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

commit;
