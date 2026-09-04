-- CaseVault backend-only authorization boundary.
-- Run after 001 and 002. React retains Supabase Auth, but business tables,
-- Storage objects, and business RPCs are inaccessible to anon/authenticated.

begin;

-- The frontend must not query CaseVault business tables directly.
revoke all on all tables in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
revoke all on table public.profiles from anon, authenticated;
revoke all on table public.cases from anon, authenticated;
revoke all on table public.case_assignments from anon, authenticated;
revoke all on table public.documents from anon, authenticated;
revoke all on table public.document_versions from anon, authenticated;
revoke all on table public.document_entities from anon, authenticated;
revoke all on table public.document_chunks from anon, authenticated;
revoke all on table public.document_embeddings from anon, authenticated;
revoke all on table public.redaction_suggestions from anon, authenticated;
revoke all on table public.audit_logs from anon, authenticated;
revoke all on table public.integrity_anchors from anon, authenticated;
revoke all on table public.document_processing_jobs from anon, authenticated;

-- Revoke all app RPCs from browser roles. Auth helper functions may still
-- exist for legacy migrations/policies but are no longer an application API.
revoke execute on all functions in schema public from public, anon, authenticated;

-- Keep future backend-owned public-schema objects closed to browser roles by default.
alter default privileges in schema public revoke all on tables from public, anon, authenticated;
alter default privileges in schema public revoke all on sequences from public, anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;

-- Browser evidence access is disabled. The FastAPI service_role performs
-- storage upload/download only after Python authorization succeeds.
drop policy if exists case_documents_insert on storage.objects;
drop policy if exists case_documents_select on storage.objects;
drop policy if exists case_documents_delete_orphan on storage.objects;

-- service_role is the only trusted application principal for DB business data.
grant select, insert, update, delete on table public.profiles to service_role;
grant select, insert, update, delete on table public.cases to service_role;
grant select, insert, update, delete on table public.case_assignments to service_role;
grant select, insert, update, delete on table public.documents to service_role;
grant select, insert, update, delete on table public.document_versions to service_role;
grant select, insert, update, delete on table public.document_entities to service_role;
grant select, insert, update, delete on table public.document_chunks to service_role;
grant select, insert, update, delete on table public.document_embeddings to service_role;
grant select, insert, update, delete on table public.redaction_suggestions to service_role;
grant select on table public.audit_logs to service_role;
grant select, insert, update, delete on table public.integrity_anchors to service_role;
grant select, insert, update, delete on table public.document_processing_jobs to service_role;
grant usage, select on sequence public.audit_sequence_seq to service_role;

grant execute on function public.append_audit_entry(uuid,uuid,uuid,public.audit_action,public.audit_result,text,jsonb) to service_role;
grant execute on function public.claim_document_processing(uuid,text,integer) to service_role;
grant execute on function public.finish_document_processing(uuid,text,boolean,text) to service_role;

commit;
