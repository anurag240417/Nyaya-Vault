-- Fix: a THIRD, independent mime-type gate that video support never
-- reached. Two others were already found and fixed (casevault.py's
-- Python-side _ALLOWED_MIME, and the backend_register_document_upload/
-- _version RPC functions' own whitelist in migration 009) - but the
-- Supabase Storage bucket itself was also created in 001_casevault_core.sql
-- with its own allowed_mime_types array, enforced by Storage's API before
-- any of the backend's own code ever runs. This is why the exact error
-- wording ("mime type X is not supported") never matched anything in the
-- Python or SQL RPC error strings - it's Supabase Storage's own message
-- format, not this application's.

update storage.buckets
set allowed_mime_types = array[
  'application/pdf','image/jpeg','image/png','image/tiff',
  'video/mp4','video/quicktime','video/webm'
]
where id = 'case-documents';