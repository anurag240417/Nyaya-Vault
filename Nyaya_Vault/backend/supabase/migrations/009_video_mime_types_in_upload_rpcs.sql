-- Fix: video upload support (added to app/services/casevault.py earlier)
-- was never propagated to these RPC functions. They enforce their own
-- independent mime-type whitelist and, until this migration, only allowed
-- 'application/pdf','image/jpeg','image/png','image/tiff' - meaning any
-- video upload would pass Python's validation, upload successfully to
-- Storage, and then fail here with "Unsupported file type." against a
-- real Postgres database. Exactly the same failure class as the
-- audit_action enum gap (008): invisible to the fake-gateway test suite,
-- real against Postgres, only discoverable by actually running this SQL.
--
-- Same signature as the current 004_backend_api_rpcs.sql definitions - no
-- drop required, only the mime whitelist line changes in each body.

begin;

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
  p_mime_type text
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

  insert into public.documents(id,case_id,title,document_type,clearance_level,current_version_number,created_by)
  values(p_document_id,p_case_id,btrim(p_title),nullif(btrim(p_document_type),''),p_clearance,1,p_actor_user_id);

  insert into public.document_versions(
    document_id,version_number,storage_key,sha256,size_bytes,mime_type,created_by
  ) values (
    p_document_id,1,p_storage_key,lower(p_sha256),p_size_bytes,p_mime_type,p_actor_user_id
  ) returning id into v_version_id;

  perform public.append_audit_entry(
    p_actor_user_id,p_case_id,p_document_id,'DOCUMENT_UPLOADED','SUCCESS',null,
    jsonb_build_object('version',1,'version_id',v_version_id,'sha256',lower(p_sha256),'size_bytes',p_size_bytes)
  );
  return jsonb_build_object('ok',true,'document_id',p_document_id,'version_id',v_version_id,'version_number',1);
exception when unique_violation then
  return jsonb_build_object('ok',false,'error','Document id, storage object, or version already exists.');
end;
$$;

create or replace function public.backend_register_document_version(
  p_actor_user_id uuid,
  p_document_id uuid,
  p_storage_key text,
  p_sha256 text,
  p_size_bytes bigint,
  p_mime_type text,
  p_change_summary text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, storage, pg_temp
as $$
declare
  v_document public.documents;
  v_next integer;
  v_version_id uuid;
begin
  if not exists(select 1 from public.profiles p where p.id=p_actor_user_id and p.is_active=true) then
    return jsonb_build_object('ok',false,'error','Actor profile is missing or inactive.');
  end if;
  select * into v_document from public.documents where id=p_document_id for update;
  if not found then return jsonb_build_object('ok',false,'error','Document not found.'); end if;
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff','video/mp4','video/quicktime','video/webm') then
    return jsonb_build_object('ok',false,'error','Unsupported file type.');
  end if;
  if p_size_bytes <= 0 or p_size_bytes > 26214400 then
    return jsonb_build_object('ok',false,'error','File size must be between 1 byte and 25 MB.');
  end if;
  if p_sha256 !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok',false,'error','Invalid SHA-256 hash.');
  end if;
  if split_part(p_storage_key,'/',1) <> v_document.case_id::text
     or split_part(p_storage_key,'/',2) <> p_document_id::text then
    return jsonb_build_object('ok',false,'error','Storage key does not match case/document scope.');
  end if;
  if not exists(select 1 from storage.objects o where o.bucket_id='case-documents' and o.name=p_storage_key) then
    return jsonb_build_object('ok',false,'error','Uploaded storage object was not found.');
  end if;

  v_next := v_document.current_version_number + 1;
  insert into public.document_versions(
    document_id,version_number,storage_key,sha256,size_bytes,mime_type,change_summary,created_by
  ) values (
    p_document_id,v_next,p_storage_key,lower(p_sha256),p_size_bytes,p_mime_type,
    nullif(btrim(p_change_summary),''),p_actor_user_id
  ) returning id into v_version_id;

  update public.documents set current_version_number=v_next where id=p_document_id;

  perform public.append_audit_entry(
    p_actor_user_id,v_document.case_id,p_document_id,'DOCUMENT_VERSION_CREATED','SUCCESS',null,
    jsonb_build_object('version',v_next,'version_id',v_version_id,'sha256',lower(p_sha256),'size_bytes',p_size_bytes)
  );
  return jsonb_build_object('ok',true,'version_id',v_version_id,'version_number',v_next);
end;
$$;

commit;