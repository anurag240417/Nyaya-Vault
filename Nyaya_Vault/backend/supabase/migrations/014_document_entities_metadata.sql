-- Adds a nullable metadata column to document_entities for structured data
-- that doesn't fit the existing NER-shaped columns (start_offset/end_offset
-- are character positions in text; a detected object in an image needs a
-- bounding box, and a detected object in a video needs a frame timestamp,
-- neither of which is a text offset). Follows the same jsonb-metadata
-- pattern already used by audit_logs.metadata elsewhere in this schema.
-- Nullable and additive - existing NER entity rows are unaffected.

alter table public.document_entities
  add column if not exists metadata jsonb;