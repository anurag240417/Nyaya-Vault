-- Fix: a FOURTH, independent mime-type gate that video support never
-- reached. Three others were already found and fixed:
--   - Python's _ALLOWED_MIME (casevault.py)
--   - backend_register_document_upload/_version RPC whitelist (009)
--   - the case-documents Storage bucket's own allowed_mime_types (012)
-- This one is a table-level CHECK constraint directly on
-- document_versions.mime_type, defined in 001_casevault_core.sql. By the
-- time an insert reaches this constraint, it has already passed Python,
-- the RPC's own check, AND Storage's own upload - meaning every earlier
-- gate can be fixed and video upload still fails here last, which is
-- exactly what happened: reported as
--   new row for relation "document_versions" violates check constraint
--   "document_versions_mime_type_check"
-- Postgres auto-named the constraint <table>_<column>_check, which is why
-- it must be dropped by that exact name before adding the replacement -
-- CHECK constraints can't be altered in place, only replaced.

alter table public.document_versions
  drop constraint if exists document_versions_mime_type_check;

alter table public.document_versions
  add constraint document_versions_mime_type_check
  check (mime_type in (
    'application/pdf','image/jpeg','image/png','image/tiff',
    'video/mp4','video/quicktime','video/webm'
  ));