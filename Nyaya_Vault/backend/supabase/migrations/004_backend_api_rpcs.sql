-- Atomic operations used only by the trusted FastAPI service_role.
-- Authorization decisions have already been made in Python. These functions
-- enforce transactionality/data integrity, not user authorization.

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
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff') then
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
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff') then
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

create or replace function public.backend_search_casevault(
  p_query text,
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
  rank real
)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  v_query text := nullif(btrim(p_query),'');
begin
  if v_query is null then return; end if;
  return query
  with latest as (
    select d.id as document_id, d.case_id, d.title, d.current_version_number
    from public.documents d
    where (p_case_ids is null or d.case_id = any(p_case_ids))
      and public.clearance_rank(d.clearance_level) <= public.clearance_rank(p_clearance)
  ), chunk_matches as (
    select l.document_id, l.case_id, c.case_number, l.title, ch.page_number,
           left(regexp_replace(ch.chunk_text, E'[\\n\\r\\t]+', ' ', 'g'),320) as snippet,
           ts_rank_cd(
             to_tsvector('english',coalesce(ch.chunk_text,'')),
             websearch_to_tsquery('english',v_query)
           )::real as rank
    from latest l
    join public.cases c on c.id=l.case_id
    join public.document_versions dv
      on dv.document_id=l.document_id and dv.version_number=l.current_version_number
    join public.document_chunks ch on ch.document_version_id=dv.id
    where to_tsvector('english',coalesce(ch.chunk_text,'')) @@ websearch_to_tsquery('english',v_query)
  ), title_matches as (
    select l.document_id,l.case_id,c.case_number,l.title,null::integer,
           'Document title or case metadata match'::text,0.20::real
    from latest l
    join public.cases c on c.id=l.case_id
    where l.title ilike '%'||v_query||'%'
       or c.case_number ilike '%'||v_query||'%'
       or c.title ilike '%'||v_query||'%'
  )
  select * from (
    select * from chunk_matches
    union all
    select * from title_matches
  ) x
  order by x.rank desc,x.title
  limit greatest(1,least(coalesce(p_limit,50),100));
end;
$$;

create or replace function public.backend_recent_activity(
  p_actor_user_id uuid,
  p_case_ids uuid[] default null,
  p_limit integer default 12
)
returns table(
  sequence bigint,
  case_id uuid,
  case_number text,
  document_id uuid,
  action public.audit_action,
  actor_username text,
  result public.audit_result,
  "timestamp" timestamptz
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select al.sequence,al.case_id,c.case_number,al.document_id,al.action,
         coalesce(p.username,'system') as actor_username,al.result,al."timestamp"
  from public.audit_logs al
  left join public.cases c on c.id=al.case_id
  left join public.profiles p on p.id=al.actor_user_id
  where p_case_ids is null
     or al.actor_user_id=p_actor_user_id
     or (al.case_id is not null and al.case_id=any(p_case_ids))
  order by al.sequence desc
  limit greatest(1,least(coalesce(p_limit,12),100));
$$;

create or replace function public.backend_verify_audit_chain()
returns table(valid boolean,total_entries bigint,first_invalid_sequence bigint,detail text)
language plpgsql
stable
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  r public.audit_logs;
  v_expected_prev text := repeat('0',64);
  v_payload text;
  v_expected_hash text;
  v_total bigint := 0;
begin
  for r in select * from public.audit_logs order by sequence loop
    v_total := v_total + 1;
    if r.prev_hash <> v_expected_prev then
      return query select false,v_total,r.sequence,'Previous-hash link mismatch.'::text;
      return;
    end if;
    v_payload := jsonb_build_object(
      'sequence',r.sequence,
      'actor_user_id',r.actor_user_id,
      'case_id',r.case_id,
      'document_id',r.document_id,
      'action',r.action,
      'result',r.result,
      'reason',r.reason,
      'metadata',coalesce(r.metadata,'{}'::jsonb),
      'timestamp',to_char(r."timestamp" at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    )::text;
    v_expected_hash := encode(extensions.digest(convert_to(v_payload||r.prev_hash,'UTF8'),'sha256'),'hex');
    if r.entry_hash <> v_expected_hash then
      return query select false,v_total,r.sequence,'Entry hash mismatch.'::text;
      return;
    end if;
    v_expected_prev := r.entry_hash;
  end loop;
  return query select true,v_total,null::bigint,'Audit chain verified.'::text;
end;
$$;

revoke all on function public.backend_register_document_upload(uuid,uuid,uuid,text,text,public.clearance_level,text,text,bigint,text) from public,anon,authenticated;
revoke all on function public.backend_register_document_version(uuid,uuid,text,text,bigint,text,text) from public,anon,authenticated;
revoke all on function public.backend_search_casevault(text,uuid[],public.clearance_level,integer) from public,anon,authenticated;
revoke all on function public.backend_recent_activity(uuid,uuid[],integer) from public,anon,authenticated;
revoke all on function public.backend_verify_audit_chain() from public,anon,authenticated;

grant execute on function public.backend_register_document_upload(uuid,uuid,uuid,text,text,public.clearance_level,text,text,bigint,text) to service_role;
grant execute on function public.backend_register_document_version(uuid,uuid,text,text,bigint,text,text) to service_role;
grant execute on function public.backend_search_casevault(text,uuid[],public.clearance_level,integer) to service_role;
grant execute on function public.backend_recent_activity(uuid,uuid[],integer) to service_role;
grant execute on function public.backend_verify_audit_chain() to service_role;

commit;
