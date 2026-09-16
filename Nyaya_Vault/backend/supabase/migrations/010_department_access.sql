begin;

do $$ begin
  create type public.department as enum (
    'POLICE',
    'FORENSICS',
    'PROSECUTION',
    'JUDICIARY',
    'GENERAL'
  );
exception when duplicate_object then null; end $$;

-- Users: nullable, defaults to unassigned. A NULL department cannot see any
-- department-tagged document until an admin sets one - deliberately not
-- defaulted to GENERAL, mirroring how role/clearance default safely closed.
alter table public.profiles
  add column if not exists department public.department;

-- Documents: NOT NULL, defaults to GENERAL so every document created before
-- this migration (and every document uploaded without picking a department)
-- stays visible to everyone who already had clearance + case access. Only
-- documents explicitly tagged POLICE/FORENSICS/PROSECUTION/JUDICIARY become
-- department-restricted.
alter table public.documents
  add column if not exists department public.department not null default 'GENERAL';

create index if not exists profiles_department_idx on public.profiles(department);
create index if not exists documents_department_idx on public.documents(department);

-- backend_register_document_upload needs a department parameter. Postgres
-- can't add a parameter to an existing function signature in place, so the
-- old 9-arg version is dropped and replaced by this 10-arg version; FastAPI
-- (app/services/casevault.py) is updated in the same change to always pass
-- p_department.
drop function if exists public.backend_register_document_upload(
  uuid, uuid, uuid, text, text, public.clearance_level, text, text, bigint, text
);

create or replace function public.backend_register_document_upload(
  p_actor_user_id uuid,
  p_document_id uuid,
  p_case_id uuid,
  p_title text,
  p_document_type text,
  p_clearance public.clearance_level,
  p_storage_key text,
  p_sha256 text,
  p_size_bytes bigint,
  p_mime_type text,
  p_department public.department default 'GENERAL'
)
returns jsonb
language plpgsql
security definer
set search_path = public, storage, pg_temp
as $$
declare
  v_version_id uuid;
begin
  if not exists(select 1 from public.profiles p where p.id=p_actor_user_id and p.is_active=true) then
    return jsonb_build_object('ok',false,'error','Actor profile is missing or inactive.');
  end if;
  if not exists(select 1 from public.cases c where c.id=p_case_id) then
    return jsonb_build_object('ok',false,'error','Case not found.');
  end if;
  if nullif(btrim(p_title),'') is null or char_length(p_title) > 300 then
    return jsonb_build_object('ok',false,'error','Document title is required and must be at most 300 characters.');
  end if;
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff','video/mp4','video/quicktime','video/webm') then
    return jsonb_build_object('ok',false,'error','Unsupported file type.');
  end if;
  if p_size_bytes <= 0 or p_size_bytes > 26214400 then
    return jsonb_build_object('ok',false,'error','File size must be between 1 byte and 25 MB.');
  end if;
  if p_sha256 !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok',false,'error','Invalid SHA-256 hash.');
  end if;
  if split_part(p_storage_key,'/',1) <> p_case_id::text
     or split_part(p_storage_key,'/',2) <> p_document_id::text then
    return jsonb_build_object('ok',false,'error','Storage key does not match case/document scope.');
  end if;
  if not exists(select 1 from storage.objects o where o.bucket_id='case-documents' and o.name=p_storage_key) then
    return jsonb_build_object('ok',false,'error','Uploaded storage object was not found.');
  end if;

  insert into public.documents(id,case_id,title,document_type,clearance_level,department,current_version_number,created_by)
  values(p_document_id,p_case_id,btrim(p_title),nullif(btrim(p_document_type),''),p_clearance,p_department,1,p_actor_user_id);

  insert into public.document_versions(
    document_id,version_number,storage_key,sha256,size_bytes,mime_type,created_by
  ) values (
    p_document_id,1,p_storage_key,lower(p_sha256),p_size_bytes,p_mime_type,p_actor_user_id
  ) returning id into v_version_id;

  perform public.append_audit_entry(
    p_actor_user_id,p_case_id,p_document_id,'DOCUMENT_UPLOADED','SUCCESS',null,
    jsonb_build_object('version',1,'version_id',v_version_id,'sha256',lower(p_sha256),'size_bytes',p_size_bytes,'department',p_department)
  );
  return jsonb_build_object('ok',true,'document_id',p_document_id,'version_id',v_version_id,'version_number',1);
exception when unique_violation then
  return jsonb_build_object('ok',false,'error','Document id, storage object, or version already exists.');
end;
$$;

revoke all on function public.backend_register_document_upload(
  uuid, uuid, uuid, text, text, public.clearance_level, text, text, bigint, text, public.department
) from public, anon, authenticated;
grant execute on function public.backend_register_document_upload(
  uuid, uuid, uuid, text, text, public.clearance_level, text, text, bigint, text, public.department
) to service_role;

commit;