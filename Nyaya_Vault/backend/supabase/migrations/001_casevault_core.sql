-- CaseVault: fresh Supabase schema
-- Run this once in a new Supabase project (SQL editor or supabase db push).
-- Browser clients use the anon key + Supabase Auth; privileged writes are exposed only through SECURITY DEFINER RPCs.

begin;

create extension if not exists pgcrypto with schema extensions;

-- ---------- enums ----------
do $$ begin
  create type public.user_role as enum (
    'ADMIN',
    'INVESTIGATING_OFFICER',
    'PROSECUTOR',
    'JUDGE',
    'CLERK'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.clearance_level as enum (
    'PUBLIC',
    'RESTRICTED',
    'CONFIDENTIAL',
    'SECRET'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.processing_status as enum (
    'UPLOADED',
    'EXTRACTING_TEXT',
    'ANALYZING_ENTITIES',
    'GENERATING_SEARCH_INDEX',
    'READY',
    'FAILED'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.audit_action as enum (
    'LOGIN',
    'CASE_CREATED',
    'CASE_UPDATED',
    'CASE_ASSIGNED',
    'CASE_UNASSIGNED',
    'DOCUMENT_UPLOADED',
    'DOCUMENT_VIEWED',
    'DOCUMENT_DOWNLOADED',
    'DOCUMENT_VERSION_CREATED',
    'METADATA_CONFIRMED',
    'SEARCH_PERFORMED',
    'ACCESS_DENIED',
    'REDACTION_CREATED',
    'REDACTION_APPROVED',
    'REPORT_EXPORTED',
    'PROFILE_UPDATED'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.audit_result as enum ('SUCCESS', 'DENIED', 'FAILED');
exception when duplicate_object then null; end $$;

-- ---------- tables ----------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null unique check (char_length(username) between 2 and 80),
  email text not null unique,
  role public.user_role not null default 'CLERK',
  clearance_level public.clearance_level not null default 'PUBLIC',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cases (
  id uuid primary key default gen_random_uuid(),
  case_number text not null unique check (char_length(btrim(case_number)) between 2 and 120),
  title text not null check (char_length(btrim(title)) between 2 and 300),
  description text check (description is null or char_length(description) <= 5000),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.case_assignments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  assigned_by uuid not null references public.profiles(id) on delete restrict,
  assigned_at timestamptz not null default now(),
  unique (case_id, user_id)
);
create index if not exists case_assignments_user_case_idx on public.case_assignments(user_id, case_id);
create index if not exists case_assignments_case_idx on public.case_assignments(case_id);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 1 and 300),
  document_type text check (document_type is null or char_length(document_type) <= 120),
  clearance_level public.clearance_level not null default 'RESTRICTED',
  current_version_number integer not null default 1 check (current_version_number >= 1),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now()
);
create index if not exists documents_case_created_idx on public.documents(case_id, created_at desc);
create index if not exists documents_clearance_idx on public.documents(clearance_level);

create table if not exists public.document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  version_number integer not null check (version_number >= 1),
  storage_key text not null unique,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 26214400),
  mime_type text not null check (mime_type in ('application/pdf','image/jpeg','image/png','image/tiff')),
  change_summary text check (change_summary is null or char_length(change_summary) <= 1000),
  processing_status public.processing_status not null default 'UPLOADED',
  processing_error text,
  extracted_text text,
  ocr_used boolean,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (document_id, version_number)
);
create index if not exists document_versions_document_idx on public.document_versions(document_id, version_number desc);
create index if not exists document_versions_processing_idx on public.document_versions(processing_status);

create table if not exists public.document_entities (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  entity_type text not null check (char_length(entity_type) between 1 and 80),
  value text not null check (char_length(value) between 1 and 2000),
  confidence double precision check (confidence is null or (confidence >= 0 and confidence <= 1)),
  page_number integer check (page_number is null or page_number >= 1),
  start_offset integer check (start_offset is null or start_offset >= 0),
  end_offset integer check (end_offset is null or end_offset >= 0),
  confirmed boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists document_entities_version_idx on public.document_entities(document_version_id);

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  page_number integer check (page_number is null or page_number >= 1),
  chunk_text text not null check (char_length(chunk_text) > 0),
  created_at timestamptz not null default now(),
  unique (document_version_id, chunk_index)
);
create index if not exists document_chunks_version_idx on public.document_chunks(document_version_id);
create index if not exists document_chunks_fts_idx
  on public.document_chunks using gin (to_tsvector('english', coalesce(chunk_text, '')));

-- JSON fallback keeps the core migration independent of pgvector.
-- Run 002_optional_pgvector.sql when you are ready to store vectors natively.
create table if not exists public.document_embeddings (
  id uuid primary key default gen_random_uuid(),
  document_chunk_id uuid not null unique references public.document_chunks(id) on delete cascade,
  model_name text not null,
  embedding_json jsonb not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(embedding_json) = 'array')
);

create table if not exists public.redaction_suggestions (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  entity_type text not null check (char_length(entity_type) between 1 and 80),
  entity_value text,
  page_number integer check (page_number is null or page_number >= 1),
  region_json jsonb not null default '{}'::jsonb,
  confidence double precision check (confidence is null or (confidence >= 0 and confidence <= 1)),
  approved boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists redaction_suggestions_version_idx on public.redaction_suggestions(document_version_id);

create sequence if not exists public.audit_sequence_seq as bigint;

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  sequence bigint not null unique default nextval('public.audit_sequence_seq'),
  -- Deliberately no FKs here: deleting/renaming source records must never rewrite a hashed audit row.
  actor_user_id uuid,
  case_id uuid,
  document_id uuid,
  action public.audit_action not null,
  result public.audit_result not null,
  reason text,
  metadata jsonb not null default '{}'::jsonb,
  prev_hash text not null check (prev_hash ~ '^[0-9a-f]{64}$'),
  entry_hash text not null unique check (entry_hash ~ '^[0-9a-f]{64}$'),
  "timestamp" timestamptz not null default now()
);
create index if not exists audit_logs_case_sequence_idx on public.audit_logs(case_id, sequence desc);
create index if not exists audit_logs_actor_sequence_idx on public.audit_logs(actor_user_id, sequence desc);
create index if not exists audit_logs_document_sequence_idx on public.audit_logs(document_id, sequence desc);

create table if not exists public.integrity_anchors (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.cases(id) on delete cascade,
  audit_sequence bigint not null,
  audit_entry_hash text not null check (audit_entry_hash ~ '^[0-9a-f]{64}$'),
  anchor_provider text not null,
  anchor_reference text not null,
  anchored_at timestamptz not null default now(),
  created_by uuid references public.profiles(id) on delete set null
);
create index if not exists integrity_anchors_case_idx on public.integrity_anchors(case_id, anchored_at desc);

-- ---------- generic helpers ----------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
before update on public.profiles
for each row execute function public.touch_updated_at();

drop trigger if exists cases_touch_updated_at on public.cases;
create trigger cases_touch_updated_at
before update on public.cases
for each row execute function public.touch_updated_at();

create or replace function public.protect_document_version_identity()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if new.document_id <> old.document_id
     or new.version_number <> old.version_number
     or new.storage_key <> old.storage_key
     or new.sha256 <> old.sha256
     or new.size_bytes <> old.size_bytes
     or new.mime_type <> old.mime_type
     or new.created_by <> old.created_by
     or new.created_at <> old.created_at then
    raise exception 'Immutable document version identity/bytes metadata cannot be changed';
  end if;
  return new;
end;
$$;

drop trigger if exists document_versions_protect_identity on public.document_versions;
create trigger document_versions_protect_identity
before update on public.document_versions
for each row execute function public.protect_document_version_identity();

create or replace function public.block_audit_mutation()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  raise exception 'Audit ledger rows are append-only';
end;
$$;

drop trigger if exists audit_logs_no_update on public.audit_logs;
create trigger audit_logs_no_update
before update on public.audit_logs
for each row execute function public.block_audit_mutation();

drop trigger if exists audit_logs_no_delete on public.audit_logs;
create trigger audit_logs_no_delete
before delete on public.audit_logs
for each row execute function public.block_audit_mutation();

create or replace function public.clearance_rank(p_level public.clearance_level)
returns integer
language sql
immutable
strict
set search_path = public, pg_temp
as $$
  select case p_level
    when 'PUBLIC' then 1
    when 'RESTRICTED' then 2
    when 'CONFIDENTIAL' then 3
    when 'SECRET' then 4
  end;
$$;

create or replace function public.is_active_user()
returns boolean
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select exists(
    select 1 from public.profiles p
    where p.id = auth.uid() and p.is_active = true
  );
$$;

create or replace function public.current_user_role()
returns public.user_role
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select p.role from public.profiles p
  where p.id = auth.uid() and p.is_active = true;
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select exists(
    select 1 from public.profiles p
    where p.id = auth.uid() and p.is_active = true and p.role = 'ADMIN'
  );
$$;

create or replace function public.can_access_case(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select public.is_active_user()
    and (
      public.is_admin()
      or exists(
        select 1 from public.case_assignments ca
        where ca.case_id = p_case_id and ca.user_id = auth.uid()
      )
    );
$$;

create or replace function public.can_manage_collaborators(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select public.is_active_user()
    and (
      public.is_admin()
      or (
        public.current_user_role() = 'INVESTIGATING_OFFICER'
        and exists(
          select 1 from public.case_assignments ca
          where ca.case_id = p_case_id and ca.user_id = auth.uid()
        )
      )
    );
$$;

create or replace function public.can_access_document(p_document_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth, pg_temp
as $$
  select exists(
    select 1
    from public.documents d
    join public.profiles p on p.id = auth.uid()
    where d.id = p_document_id
      and p.is_active = true
      and (
        public.is_admin()
        or exists(
          select 1 from public.case_assignments ca
          where ca.case_id = d.case_id and ca.user_id = auth.uid()
        )
      )
      and public.clearance_rank(p.clearance_level) >= public.clearance_rank(d.clearance_level)
  );
$$;

-- ---------- immutable audit chain ----------
create or replace function public.append_audit_entry(
  p_actor_user_id uuid,
  p_case_id uuid,
  p_document_id uuid,
  p_action public.audit_action,
  p_result public.audit_result,
  p_reason text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns public.audit_logs
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_prev_hash text;
  v_sequence bigint;
  v_timestamp timestamptz := clock_timestamp();
  v_payload text;
  v_entry_hash text;
  v_row public.audit_logs;
begin
  -- Serializes the single global chain. Transaction-scoped, so no leaked lock.
  perform pg_advisory_xact_lock(hashtext('casevault-global-audit-chain'));

  select al.entry_hash
    into v_prev_hash
  from public.audit_logs al
  order by al.sequence desc
  limit 1;

  v_prev_hash := coalesce(v_prev_hash, repeat('0', 64));
  v_sequence := nextval('public.audit_sequence_seq');

  v_payload := jsonb_build_object(
    'sequence', v_sequence,
    'actor_user_id', p_actor_user_id,
    'case_id', p_case_id,
    'document_id', p_document_id,
    'action', p_action,
    'result', p_result,
    'reason', p_reason,
    'metadata', coalesce(p_metadata, '{}'::jsonb),
    'timestamp', to_char(v_timestamp at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
  )::text;

  v_entry_hash := encode(
    extensions.digest(convert_to(v_payload || v_prev_hash, 'UTF8'), 'sha256'),
    'hex'
  );

  insert into public.audit_logs(
    sequence, actor_user_id, case_id, document_id, action, result, reason,
    metadata, prev_hash, entry_hash, "timestamp"
  ) values (
    v_sequence, p_actor_user_id, p_case_id, p_document_id, p_action, p_result,
    p_reason, coalesce(p_metadata, '{}'::jsonb), v_prev_hash, v_entry_hash, v_timestamp
  ) returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.append_audit_entry(uuid,uuid,uuid,public.audit_action,public.audit_result,text,jsonb) from public, anon, authenticated;

-- ---------- Auth -> profile bootstrap ----------
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_base text;
  v_username text;
begin
  v_base := coalesce(
    nullif(btrim(new.raw_user_meta_data ->> 'username'), ''),
    split_part(coalesce(new.email, 'user'), '@', 1),
    'user'
  );
  v_base := lower(regexp_replace(v_base, '[^a-zA-Z0-9_.-]+', '-', 'g'));
  v_base := trim(both '-' from v_base);
  if char_length(v_base) < 2 then v_base := 'user'; end if;
  v_username := left(v_base, 80);
  if exists(select 1 from public.profiles p where p.username=v_username) then
    v_username := left(v_base, 60) || '-' || left(replace(new.id::text, '-', ''), 8);
  end if;

  insert into public.profiles(id, username, email)
  values (new.id, v_username, lower(coalesce(new.email, new.id::text || '@local.invalid')))
  on conflict (id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

-- ---------- case bootstrap ----------
create or replace function public.after_case_created()
returns trigger
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  insert into public.case_assignments(case_id, user_id, assigned_by)
  values (new.id, new.created_by, new.created_by)
  on conflict (case_id, user_id) do nothing;

  perform public.append_audit_entry(
    new.created_by, new.id, null,
    'CASE_CREATED', 'SUCCESS', null,
    jsonb_build_object('case_number', new.case_number, 'title', new.title)
  );
  return new;
end;
$$;

drop trigger if exists cases_after_insert on public.cases;
create trigger cases_after_insert
after insert on public.cases
for each row execute function public.after_case_created();

-- ---------- RPCs used by the React app ----------
create or replace function public.record_login_event()
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if not public.is_active_user() then
    return jsonb_build_object('ok', false, 'error', 'Account is inactive or profile is missing.');
  end if;

  perform public.append_audit_entry(auth.uid(), null, null, 'LOGIN', 'SUCCESS', null, '{}'::jsonb);
  return jsonb_build_object('ok', true);
end;
$$;

create or replace function public.list_collaborator_candidates()
returns table(
  id uuid,
  username text,
  role public.user_role,
  clearance_level public.clearance_level
)
language plpgsql
stable
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if public.current_user_role() is null
     or public.current_user_role() not in ('ADMIN','INVESTIGATING_OFFICER') then
    raise exception 'Not authorized to list collaborator candidates' using errcode = '42501';
  end if;

  return query
  select p.id, p.username, p.role, p.clearance_level
  from public.profiles p
  where p.is_active = true
  order by p.username;
end;
$$;

create or replace function public.get_case_collaborators(p_case_id uuid)
returns table(
  user_id uuid,
  username text,
  role public.user_role,
  clearance_level public.clearance_level,
  assigned_by uuid,
  assigned_by_username text,
  assigned_at timestamptz
)
language plpgsql
stable
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if not public.can_access_case(p_case_id) then
    raise exception 'Case not found or access denied' using errcode = '42501';
  end if;

  return query
  select ca.user_id,
         p.username,
         p.role,
         p.clearance_level,
         ca.assigned_by,
         assigner.username,
         ca.assigned_at
  from public.case_assignments ca
  join public.profiles p on p.id = ca.user_id
  join public.profiles assigner on assigner.id = ca.assigned_by
  where ca.case_id = p_case_id
  order by ca.assigned_at, p.username;
end;
$$;

create or replace function public.add_case_collaborator(p_case_id uuid, p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_reason text;
  v_target_active boolean;
begin
  if not public.can_manage_collaborators(p_case_id) then
    v_reason := 'Only an admin or an assigned investigating officer may manage collaborators.';
    perform public.append_audit_entry(auth.uid(), p_case_id, null, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','add_collaborator','target_user_id',p_user_id));
    return jsonb_build_object('ok', false, 'error', v_reason);
  end if;

  select p.is_active into v_target_active from public.profiles p where p.id = p_user_id;
  if coalesce(v_target_active, false) = false then
    v_reason := 'Target user does not exist or is inactive.';
    perform public.append_audit_entry(auth.uid(), p_case_id, null, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','add_collaborator','target_user_id',p_user_id));
    return jsonb_build_object('ok', false, 'error', v_reason);
  end if;

  if exists(select 1 from public.case_assignments ca where ca.case_id=p_case_id and ca.user_id=p_user_id) then
    return jsonb_build_object('ok', true, 'already_assigned', true);
  end if;

  insert into public.case_assignments(case_id,user_id,assigned_by)
  values(p_case_id,p_user_id,auth.uid());

  perform public.append_audit_entry(auth.uid(), p_case_id, null, 'CASE_ASSIGNED', 'SUCCESS', null,
    jsonb_build_object('assigned_user_id',p_user_id));
  return jsonb_build_object('ok', true);
end;
$$;

create or replace function public.remove_case_collaborator(p_case_id uuid, p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_reason text;
  v_count integer;
begin
  if not public.can_manage_collaborators(p_case_id) then
    v_reason := 'Only an admin or an assigned investigating officer may manage collaborators.';
    perform public.append_audit_entry(auth.uid(), p_case_id, null, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','remove_collaborator','target_user_id',p_user_id));
    return jsonb_build_object('ok', false, 'error', v_reason);
  end if;

  if not exists(select 1 from public.case_assignments ca where ca.case_id=p_case_id and ca.user_id=p_user_id) then
    return jsonb_build_object('ok', true, 'not_assigned', true);
  end if;

  select count(*) into v_count from public.case_assignments ca where ca.case_id=p_case_id;
  if v_count <= 1 then
    v_reason := 'The last collaborator cannot be removed from a case.';
    perform public.append_audit_entry(auth.uid(), p_case_id, null, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','remove_collaborator','target_user_id',p_user_id));
    return jsonb_build_object('ok', false, 'error', v_reason);
  end if;

  delete from public.case_assignments
  where case_id=p_case_id and user_id=p_user_id;

  perform public.append_audit_entry(auth.uid(), p_case_id, null, 'CASE_UNASSIGNED', 'SUCCESS', null,
    jsonb_build_object('unassigned_user_id',p_user_id));
  return jsonb_build_object('ok', true);
end;
$$;

create or replace function public.register_document_upload(
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
set search_path = public, auth, storage, pg_temp
as $$
declare
  v_version_id uuid;
  v_reason text;
begin
  if not public.can_access_case(p_case_id) then
    v_reason := 'Case not found or access denied.';
    perform public.append_audit_entry(auth.uid(), p_case_id, p_document_id, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','document_upload'));
    return jsonb_build_object('ok', false, 'error', v_reason);
  end if;

  if not exists(
    select 1 from public.profiles p
    where p.id=auth.uid() and p.is_active=true
      and public.clearance_rank(p.clearance_level) >= public.clearance_rank(p_clearance)
  ) then
    return jsonb_build_object('ok', false, 'error', 'You cannot create evidence above your own clearance level.');
  end if;

  if nullif(btrim(p_title),'') is null or char_length(p_title) > 300 then
    return jsonb_build_object('ok', false, 'error', 'Document title is required and must be at most 300 characters.');
  end if;
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff') then
    return jsonb_build_object('ok', false, 'error', 'Unsupported file type.');
  end if;
  if p_size_bytes <= 0 or p_size_bytes > 26214400 then
    return jsonb_build_object('ok', false, 'error', 'File size must be between 1 byte and 25 MB.');
  end if;
  if p_sha256 !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'error', 'Invalid SHA-256 hash.');
  end if;
  if split_part(p_storage_key,'/',1) <> p_case_id::text
     or split_part(p_storage_key,'/',2) <> p_document_id::text then
    return jsonb_build_object('ok', false, 'error', 'Storage key does not match case/document scope.');
  end if;
  if not exists(select 1 from storage.objects o where o.bucket_id='case-documents' and o.name=p_storage_key) then
    return jsonb_build_object('ok', false, 'error', 'Uploaded storage object was not found.');
  end if;

  insert into public.documents(id,case_id,title,document_type,clearance_level,current_version_number,created_by)
  values(p_document_id,p_case_id,btrim(p_title),nullif(btrim(p_document_type),''),p_clearance,1,auth.uid());

  insert into public.document_versions(
    document_id,version_number,storage_key,sha256,size_bytes,mime_type,created_by
  ) values (
    p_document_id,1,p_storage_key,lower(p_sha256),p_size_bytes,p_mime_type,auth.uid()
  ) returning id into v_version_id;

  perform public.append_audit_entry(auth.uid(), p_case_id, p_document_id, 'DOCUMENT_UPLOADED', 'SUCCESS', null,
    jsonb_build_object('version',1,'version_id',v_version_id,'sha256',lower(p_sha256),'size_bytes',p_size_bytes));

  return jsonb_build_object('ok',true,'document_id',p_document_id,'version_id',v_version_id,'version_number',1);
exception
  when unique_violation then
    return jsonb_build_object('ok',false,'error','Document id, storage object, or version already exists.');
end;
$$;

create or replace function public.register_document_version(
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
set search_path = public, auth, storage, pg_temp
as $$
declare
  v_document public.documents;
  v_next integer;
  v_version_id uuid;
  v_reason text;
begin
  select * into v_document from public.documents where id=p_document_id for update;
  if not found or not public.can_access_document(p_document_id) then
    v_reason := 'Document not found or clearance/access denied.';
    perform public.append_audit_entry(auth.uid(), v_document.case_id, p_document_id, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation','document_version_upload'));
    return jsonb_build_object('ok',false,'error',v_reason);
  end if;
  if p_mime_type not in ('application/pdf','image/jpeg','image/png','image/tiff') then
    return jsonb_build_object('ok', false, 'error', 'Unsupported file type.');
  end if;
  if p_size_bytes <= 0 or p_size_bytes > 26214400 then
    return jsonb_build_object('ok', false, 'error', 'File size must be between 1 byte and 25 MB.');
  end if;
  if p_sha256 !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'error', 'Invalid SHA-256 hash.');
  end if;
  if split_part(p_storage_key,'/',1) <> v_document.case_id::text
     or split_part(p_storage_key,'/',2) <> p_document_id::text then
    return jsonb_build_object('ok', false, 'error', 'Storage key does not match case/document scope.');
  end if;
  if not exists(select 1 from storage.objects o where o.bucket_id='case-documents' and o.name=p_storage_key) then
    return jsonb_build_object('ok', false, 'error', 'Uploaded storage object was not found.');
  end if;

  v_next := v_document.current_version_number + 1;
  insert into public.document_versions(
    document_id,version_number,storage_key,sha256,size_bytes,mime_type,change_summary,created_by
  ) values (
    p_document_id,v_next,p_storage_key,lower(p_sha256),p_size_bytes,p_mime_type,nullif(btrim(p_change_summary),''),auth.uid()
  ) returning id into v_version_id;

  update public.documents set current_version_number=v_next where id=p_document_id;

  perform public.append_audit_entry(auth.uid(), v_document.case_id, p_document_id, 'DOCUMENT_VERSION_CREATED', 'SUCCESS', null,
    jsonb_build_object('version',v_next,'version_id',v_version_id,'sha256',lower(p_sha256),'size_bytes',p_size_bytes));
  return jsonb_build_object('ok',true,'version_id',v_version_id,'version_number',v_next);
end;
$$;

create or replace function public.record_document_event(p_document_id uuid, p_action public.audit_action)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_case_id uuid;
  v_reason text;
begin
  if p_action not in ('DOCUMENT_VIEWED','DOCUMENT_DOWNLOADED') then
    return jsonb_build_object('ok',false,'error','Unsupported document event.');
  end if;
  select d.case_id into v_case_id from public.documents d where d.id=p_document_id;
  if not public.can_access_document(p_document_id) then
    v_reason := 'Document not found or clearance/access denied.';
    perform public.append_audit_entry(auth.uid(), v_case_id, p_document_id, 'ACCESS_DENIED', 'DENIED', v_reason,
      jsonb_build_object('operation',lower(p_action::text)));
    return jsonb_build_object('ok',false,'error',v_reason);
  end if;
  perform public.append_audit_entry(auth.uid(), v_case_id, p_document_id, p_action, 'SUCCESS', null, '{}'::jsonb);
  return jsonb_build_object('ok',true);
end;
$$;

create or replace function public.confirm_document_entities(
  p_document_id uuid,
  p_confirmed_ids uuid[] default '{}'::uuid[],
  p_rejected_ids uuid[] default '{}'::uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_case_id uuid;
  v_version_id uuid;
begin
  select d.case_id, dv.id into v_case_id, v_version_id
  from public.documents d
  join public.document_versions dv
    on dv.document_id=d.id and dv.version_number=d.current_version_number
  where d.id=p_document_id;

  if v_version_id is null or not public.can_access_document(p_document_id) then
    return jsonb_build_object('ok',false,'error','Document not found or access denied.');
  end if;

  update public.document_entities
  set confirmed=true
  where document_version_id=v_version_id and id=any(coalesce(p_confirmed_ids,'{}'::uuid[]));

  delete from public.document_entities
  where document_version_id=v_version_id and id=any(coalesce(p_rejected_ids,'{}'::uuid[]));

  perform public.append_audit_entry(auth.uid(), v_case_id, p_document_id, 'METADATA_CONFIRMED', 'SUCCESS', null,
    jsonb_build_object('confirmed_ids',coalesce(to_jsonb(p_confirmed_ids),'[]'::jsonb),'rejected_ids',coalesce(to_jsonb(p_rejected_ids),'[]'::jsonb)));
  return jsonb_build_object('ok',true);
end;
$$;

create or replace function public.confirm_document_redactions(
  p_document_id uuid,
  p_approved_ids uuid[] default '{}'::uuid[],
  p_rejected_ids uuid[] default '{}'::uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_case_id uuid;
  v_version_id uuid;
begin
  select d.case_id, dv.id into v_case_id, v_version_id
  from public.documents d
  join public.document_versions dv
    on dv.document_id=d.id and dv.version_number=d.current_version_number
  where d.id=p_document_id;

  if v_version_id is null or not public.can_access_document(p_document_id) then
    return jsonb_build_object('ok',false,'error','Document not found or access denied.');
  end if;

  update public.redaction_suggestions
  set approved=true
  where document_version_id=v_version_id and id=any(coalesce(p_approved_ids,'{}'::uuid[]));

  delete from public.redaction_suggestions
  where document_version_id=v_version_id and id=any(coalesce(p_rejected_ids,'{}'::uuid[]));

  perform public.append_audit_entry(auth.uid(), v_case_id, p_document_id, 'REDACTION_APPROVED', 'SUCCESS', null,
    jsonb_build_object('approved_ids',coalesce(to_jsonb(p_approved_ids),'[]'::jsonb),'rejected_ids',coalesce(to_jsonb(p_rejected_ids),'[]'::jsonb)));
  return jsonb_build_object('ok',true);
end;
$$;

create or replace function public.get_case_audit(p_case_id uuid)
returns table(
  sequence bigint,
  action public.audit_action,
  actor_user_id uuid,
  actor_username text,
  document_id uuid,
  result public.audit_result,
  reason text,
  metadata jsonb,
  prev_hash text,
  entry_hash text,
  "timestamp" timestamptz
)
language plpgsql
stable
security definer
set search_path = public, auth, pg_temp
as $$
begin
  if not public.can_access_case(p_case_id) then
    raise exception 'Case not found or access denied' using errcode='42501';
  end if;

  return query
  select al.sequence, al.action, al.actor_user_id, p.username, al.document_id,
         al.result, al.reason, al.metadata, al.prev_hash, al.entry_hash, al."timestamp"
  from public.audit_logs al
  left join public.profiles p on p.id=al.actor_user_id
  where al.case_id=p_case_id
  order by al.sequence desc;
end;
$$;

create or replace function public.get_recent_activity(p_limit integer default 12)
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
language plpgsql
stable
security definer
set search_path = public, auth, pg_temp
as $$
begin
  return query
  select al.sequence, al.case_id, c.case_number, al.document_id, al.action,
         p.username, al.result, al."timestamp"
  from public.audit_logs al
  left join public.cases c on c.id=al.case_id
  left join public.profiles p on p.id=al.actor_user_id
  where (
    al.actor_user_id=auth.uid()
    or public.is_admin()
    or (al.case_id is not null and public.can_access_case(al.case_id))
  )
  order by al.sequence desc
  limit greatest(1,least(coalesce(p_limit,12),100));
end;
$$;

create or replace function public.search_casevault(
  p_query text,
  p_case_id uuid default null,
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
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_query text := nullif(btrim(p_query),'');
begin
  if v_query is null then return; end if;
  if p_case_id is not null and not public.can_access_case(p_case_id) then
    perform public.append_audit_entry(auth.uid(), p_case_id, null, 'ACCESS_DENIED', 'DENIED', 'Search case scope denied.',
      jsonb_build_object('operation','search','query_length',char_length(v_query)));
    return;
  end if;

  return query
  with latest as (
    select d.id as document_id, d.case_id, d.title, d.current_version_number
    from public.documents d
    where (p_case_id is null or d.case_id=p_case_id)
      and public.can_access_document(d.id)
  ), chunk_matches as (
    select l.document_id, l.case_id, c.case_number, l.title, ch.page_number,
           left(regexp_replace(ch.chunk_text, E'[\\n\\r\\t]+', ' ', 'g'), 320) as snippet,
           ts_rank_cd(
             to_tsvector('english', coalesce(ch.chunk_text,'')),
             websearch_to_tsquery('english', v_query)
           )::real as rank
    from latest l
    join public.cases c on c.id=l.case_id
    join public.document_versions dv
      on dv.document_id=l.document_id and dv.version_number=l.current_version_number
    join public.document_chunks ch on ch.document_version_id=dv.id
    where to_tsvector('english', coalesce(ch.chunk_text,'')) @@ websearch_to_tsquery('english', v_query)
  ), title_matches as (
    select l.document_id, l.case_id, c.case_number, l.title, null::integer as page_number,
           'Document title or case metadata match'::text as snippet,
           0.20::real as rank
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
  order by x.rank desc, x.title
  limit greatest(1,least(coalesce(p_limit,50),100));

  perform public.append_audit_entry(auth.uid(), p_case_id, null, 'SEARCH_PERFORMED', 'SUCCESS', null,
    jsonb_build_object('query_length',char_length(v_query),'case_scoped',p_case_id is not null));
end;
$$;

create or replace function public.verify_audit_chain()
returns table(
  valid boolean,
  total_entries bigint,
  first_invalid_sequence bigint,
  detail text
)
language plpgsql
security definer
set search_path = public, extensions, auth, pg_temp
as $$
declare
  r public.audit_logs;
  v_expected_prev text := repeat('0',64);
  v_payload text;
  v_expected_hash text;
  v_total bigint := 0;
begin
  if not public.is_active_user() then
    raise exception 'Authentication required' using errcode='42501';
  end if;

  for r in select * from public.audit_logs order by sequence loop
    v_total := v_total + 1;
    if r.prev_hash <> v_expected_prev then
      return query select false, v_total, r.sequence, 'Previous-hash link mismatch.'::text;
      return;
    end if;

    v_payload := jsonb_build_object(
      'sequence', r.sequence,
      'actor_user_id', r.actor_user_id,
      'case_id', r.case_id,
      'document_id', r.document_id,
      'action', r.action,
      'result', r.result,
      'reason', r.reason,
      'metadata', coalesce(r.metadata,'{}'::jsonb),
      'timestamp', to_char(r."timestamp" at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    )::text;
    v_expected_hash := encode(
      extensions.digest(convert_to(v_payload || r.prev_hash,'UTF8'),'sha256'),
      'hex'
    );
    if r.entry_hash <> v_expected_hash then
      return query select false, v_total, r.sequence, 'Entry hash mismatch.'::text;
      return;
    end if;
    v_expected_prev := r.entry_hash;
  end loop;

  return query select true, v_total, null::bigint, 'Audit chain verified.'::text;
end;
$$;

create or replace function public.admin_update_profile(
  p_user_id uuid,
  p_role public.user_role,
  p_clearance public.clearance_level,
  p_is_active boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_old public.profiles;
  v_admins integer;
begin
  if not public.is_admin() then
    return jsonb_build_object('ok',false,'error','Admin role required.');
  end if;

  select * into v_old from public.profiles where id=p_user_id for update;
  if not found then return jsonb_build_object('ok',false,'error','User not found.'); end if;

  if v_old.role='ADMIN' and v_old.is_active=true and (p_role<>'ADMIN' or p_is_active=false) then
    select count(*) into v_admins from public.profiles where role='ADMIN' and is_active=true;
    if v_admins <= 1 then
      return jsonb_build_object('ok',false,'error','The last active admin cannot be demoted or disabled.');
    end if;
  end if;

  update public.profiles
  set role=p_role, clearance_level=p_clearance, is_active=p_is_active
  where id=p_user_id;

  perform public.append_audit_entry(auth.uid(), null, null, 'PROFILE_UPDATED', 'SUCCESS', null,
    jsonb_build_object('target_user_id',p_user_id,'role',p_role,'clearance',p_clearance,'active',p_is_active));
  return jsonb_build_object('ok',true);
end;
$$;

-- ---------- RLS ----------
alter table public.profiles enable row level security;
alter table public.cases enable row level security;
alter table public.case_assignments enable row level security;
alter table public.documents enable row level security;
alter table public.document_versions enable row level security;
alter table public.document_entities enable row level security;
alter table public.document_chunks enable row level security;
alter table public.document_embeddings enable row level security;
alter table public.redaction_suggestions enable row level security;
alter table public.audit_logs enable row level security;
alter table public.integrity_anchors enable row level security;

-- Remove any same-named policies so the migration remains easy to re-run while iterating.
drop policy if exists profiles_self_or_admin_select on public.profiles;
create policy profiles_self_or_admin_select on public.profiles
for select to authenticated
using (id=auth.uid() or public.is_admin());

drop policy if exists cases_access_select on public.cases;
create policy cases_access_select on public.cases
for select to authenticated using (public.can_access_case(id));

drop policy if exists cases_create on public.cases;
create policy cases_create on public.cases
for insert to authenticated
with check (
  created_by=auth.uid()
  and public.is_active_user()
  and public.current_user_role() in ('ADMIN','INVESTIGATING_OFFICER')
);

drop policy if exists assignments_case_select on public.case_assignments;
create policy assignments_case_select on public.case_assignments
for select to authenticated using (public.can_access_case(case_id));

drop policy if exists documents_access_select on public.documents;
create policy documents_access_select on public.documents
for select to authenticated using (public.can_access_document(id));

drop policy if exists versions_document_select on public.document_versions;
create policy versions_document_select on public.document_versions
for select to authenticated using (public.can_access_document(document_id));

drop policy if exists entities_document_select on public.document_entities;
create policy entities_document_select on public.document_entities
for select to authenticated using (
  exists(select 1 from public.document_versions dv where dv.id=document_version_id and public.can_access_document(dv.document_id))
);

drop policy if exists chunks_document_select on public.document_chunks;
create policy chunks_document_select on public.document_chunks
for select to authenticated using (
  exists(select 1 from public.document_versions dv where dv.id=document_version_id and public.can_access_document(dv.document_id))
);

drop policy if exists redactions_document_select on public.redaction_suggestions;
create policy redactions_document_select on public.redaction_suggestions
for select to authenticated using (
  exists(select 1 from public.document_versions dv where dv.id=document_version_id and public.can_access_document(dv.document_id))
);

drop policy if exists audit_visible_select on public.audit_logs;
create policy audit_visible_select on public.audit_logs
for select to authenticated using (
  public.is_admin()
  or actor_user_id=auth.uid()
  or (case_id is not null and public.can_access_case(case_id))
);

drop policy if exists anchors_case_select on public.integrity_anchors;
create policy anchors_case_select on public.integrity_anchors
for select to authenticated using (case_id is null or public.can_access_case(case_id));

-- ---------- least-privilege SQL grants ----------
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

-- Direct browser reads are still filtered by RLS. Direct browser mutation is intentionally tiny.
grant select on table public.profiles to authenticated;
grant select, insert on table public.cases to authenticated;
grant select on table public.case_assignments to authenticated;
grant select on table public.documents to authenticated;
grant select on table public.document_versions to authenticated;
grant select on table public.document_entities to authenticated;
grant select on table public.document_chunks to authenticated;
grant select on table public.redaction_suggestions to authenticated;
grant select on table public.audit_logs to authenticated;
grant select on table public.integrity_anchors to authenticated;

revoke execute on all functions in schema public from public, anon, authenticated;

-- RLS helper functions need EXECUTE for authenticated queries/policies.
grant execute on function public.is_active_user() to authenticated;
grant execute on function public.current_user_role() to authenticated;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.can_access_case(uuid) to authenticated;
grant execute on function public.can_manage_collaborators(uuid) to authenticated;
grant execute on function public.can_access_document(uuid) to authenticated;

grant execute on function public.record_login_event() to authenticated;
grant execute on function public.list_collaborator_candidates() to authenticated;
grant execute on function public.get_case_collaborators(uuid) to authenticated;
grant execute on function public.add_case_collaborator(uuid,uuid) to authenticated;
grant execute on function public.remove_case_collaborator(uuid,uuid) to authenticated;
grant execute on function public.register_document_upload(uuid,uuid,text,text,public.clearance_level,text,text,bigint,text) to authenticated;
grant execute on function public.register_document_version(uuid,text,text,bigint,text,text) to authenticated;
grant execute on function public.record_document_event(uuid,public.audit_action) to authenticated;
grant execute on function public.confirm_document_entities(uuid,uuid[],uuid[]) to authenticated;
grant execute on function public.confirm_document_redactions(uuid,uuid[],uuid[]) to authenticated;
grant execute on function public.get_case_audit(uuid) to authenticated;
grant execute on function public.get_recent_activity(integer) to authenticated;
grant execute on function public.search_casevault(text,uuid,integer) to authenticated;
grant execute on function public.verify_audit_chain() to authenticated;
grant execute on function public.admin_update_profile(uuid,public.user_role,public.clearance_level,boolean) to authenticated;

-- ---------- Storage ----------
create or replace function public.storage_key_is_registered(p_storage_key text)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists(select 1 from public.document_versions dv where dv.storage_key=p_storage_key);
$$;
revoke all on function public.storage_key_is_registered(text) from public, anon;
grant execute on function public.storage_key_is_registered(text) to authenticated;

-- Storage object names are: <case_uuid>/<document_uuid>/uploads/<random>-<safe_filename>
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values(
  'case-documents',
  'case-documents',
  false,
  26214400,
  array['application/pdf','image/jpeg','image/png','image/tiff']
)
on conflict(id) do update set
  public=false,
  file_size_limit=excluded.file_size_limit,
  allowed_mime_types=excluded.allowed_mime_types;

drop policy if exists case_documents_insert on storage.objects;
create policy case_documents_insert on storage.objects
for insert to authenticated
with check (
  bucket_id='case-documents'
  and (storage.foldername(name))[1] ~* '^[0-9a-f-]{36}$'
  and public.can_access_case(((storage.foldername(name))[1])::uuid)
);

drop policy if exists case_documents_select on storage.objects;
create policy case_documents_select on storage.objects
for select to authenticated
using (
  bucket_id='case-documents'
  and (storage.foldername(name))[2] ~* '^[0-9a-f-]{36}$'
  and public.can_access_document(((storage.foldername(name))[2])::uuid)
);

drop policy if exists case_documents_delete_orphan on storage.objects;
create policy case_documents_delete_orphan on storage.objects
for delete to authenticated
using (
  bucket_id='case-documents'
  and (storage.foldername(name))[1] ~* '^[0-9a-f-]{36}$'
  and public.can_access_case(((storage.foldername(name))[1])::uuid)
  and not public.storage_key_is_registered(name)
);

commit;
