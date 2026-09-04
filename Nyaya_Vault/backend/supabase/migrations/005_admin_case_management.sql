-- CaseVault admin-side case management.
-- Run after 004_backend_api_rpcs.sql.
-- Adds a persisted primary investigating officer and two service-role-only,
-- transactional RPCs used by FastAPI. Browser clients receive no access.

begin;

alter table public.cases
  add column if not exists primary_investigator_id uuid
  references public.profiles(id) on delete set null;

create index if not exists cases_primary_investigator_idx
  on public.cases(primary_investigator_id);

create or replace function public.backend_admin_create_case(
  p_actor_user_id uuid,
  p_case_number text,
  p_title text,
  p_description text default null,
  p_primary_investigator_id uuid default null,
  p_collaborator_ids uuid[] default '{}'::uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_case public.cases;
  v_target uuid;
  v_profile public.profiles;
  v_collaborators uuid[] := coalesce(p_collaborator_ids, '{}'::uuid[]);
begin
  if not exists (
    select 1 from public.profiles p
    where p.id = p_actor_user_id and p.is_active = true and p.role = 'ADMIN'
  ) then
    raise exception 'Only an active admin may create and assign cases.' using errcode = '42501';
  end if;

  if char_length(btrim(coalesce(p_case_number, ''))) < 2 then
    raise exception 'Case number is required.' using errcode = '22023';
  end if;
  if char_length(btrim(coalesce(p_title, ''))) < 2 then
    raise exception 'Case title is required.' using errcode = '22023';
  end if;

  if p_primary_investigator_id is not null then
    select * into v_profile from public.profiles p where p.id = p_primary_investigator_id;
    if not found or not v_profile.is_active or v_profile.role <> 'INVESTIGATING_OFFICER' then
      raise exception 'Primary investigator must be an active INVESTIGATING_OFFICER.' using errcode = '22023';
    end if;
  end if;

  foreach v_target in array v_collaborators loop
    select * into v_profile from public.profiles p where p.id = v_target;
    if not found or not v_profile.is_active then
      raise exception 'Every collaborator must be an active user.' using errcode = '22023';
    end if;
  end loop;

  insert into public.cases(
    case_number, title, description, created_by, primary_investigator_id
  ) values (
    btrim(p_case_number),
    btrim(p_title),
    nullif(btrim(coalesce(p_description, '')), ''),
    p_actor_user_id,
    p_primary_investigator_id
  ) returning * into v_case;

  -- after_case_created() already assigns the creator and writes CASE_CREATED.
  if p_primary_investigator_id is not null then
    insert into public.case_assignments(case_id, user_id, assigned_by)
    values (v_case.id, p_primary_investigator_id, p_actor_user_id)
    on conflict (case_id, user_id) do nothing;

    perform public.append_audit_entry(
      p_actor_user_id, v_case.id, null,
      'CASE_ASSIGNED', 'SUCCESS', null,
      jsonb_build_object('assigned_user_id', p_primary_investigator_id, 'primary_investigator', true, 'source', 'admin_case_management')
    );
  end if;

  foreach v_target in array v_collaborators loop
    insert into public.case_assignments(case_id, user_id, assigned_by)
    values (v_case.id, v_target, p_actor_user_id)
    on conflict (case_id, user_id) do nothing;

    if v_target <> p_actor_user_id and (p_primary_investigator_id is null or v_target <> p_primary_investigator_id) then
      perform public.append_audit_entry(
        p_actor_user_id, v_case.id, null,
        'CASE_ASSIGNED', 'SUCCESS', null,
        jsonb_build_object('assigned_user_id', v_target, 'source', 'admin_case_management')
      );
    end if;
  end loop;

  return jsonb_build_object('ok', true, 'case_id', v_case.id);
end;
$$;

create or replace function public.backend_admin_replace_case_assignments(
  p_actor_user_id uuid,
  p_case_id uuid,
  p_primary_investigator_id uuid default null,
  p_collaborator_ids uuid[] default '{}'::uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_case public.cases;
  v_profile public.profiles;
  v_target uuid;
  v_old_primary uuid;
  v_old_ids uuid[];
  v_new_ids uuid[];
  v_collaborators uuid[] := coalesce(p_collaborator_ids, '{}'::uuid[]);
begin
  if not exists (
    select 1 from public.profiles p
    where p.id = p_actor_user_id and p.is_active = true and p.role = 'ADMIN'
  ) then
    raise exception 'Only an active admin may reassign cases.' using errcode = '42501';
  end if;

  select * into v_case from public.cases c where c.id = p_case_id for update;
  if not found then
    raise exception 'Case not found.' using errcode = 'P0002';
  end if;
  v_old_primary := v_case.primary_investigator_id;

  if p_primary_investigator_id is not null then
    select * into v_profile from public.profiles p where p.id = p_primary_investigator_id;
    if not found or not v_profile.is_active or v_profile.role <> 'INVESTIGATING_OFFICER' then
      raise exception 'Primary investigator must be an active INVESTIGATING_OFFICER.' using errcode = '22023';
    end if;
  end if;

  foreach v_target in array v_collaborators loop
    select * into v_profile from public.profiles p where p.id = v_target;
    if not found or not v_profile.is_active then
      raise exception 'Every collaborator must be an active user.' using errcode = '22023';
    end if;
  end loop;

  select coalesce(array_agg(ca.user_id order by ca.user_id), '{}'::uuid[])
    into v_old_ids
  from public.case_assignments ca
  where ca.case_id = p_case_id;

  -- Keep the creator assigned, then include primary IO + requested collaborators.
  select coalesce(array_agg(distinct x order by x), '{}'::uuid[])
    into v_new_ids
  from unnest(
    array_append(
      array_append(v_collaborators, v_case.created_by),
      p_primary_investigator_id
    )
  ) as x
  where x is not null;

  -- Audit removals before deleting.
  foreach v_target in array v_old_ids loop
    if not (v_target = any(v_new_ids)) then
      perform public.append_audit_entry(
        p_actor_user_id, p_case_id, null,
        'CASE_UNASSIGNED', 'SUCCESS', null,
        jsonb_build_object('unassigned_user_id', v_target, 'source', 'admin_case_management')
      );
    end if;
  end loop;

  delete from public.case_assignments ca
  where ca.case_id = p_case_id
    and not (ca.user_id = any(v_new_ids));

  foreach v_target in array v_new_ids loop
    if not (v_target = any(v_old_ids)) then
      insert into public.case_assignments(case_id, user_id, assigned_by)
      values (p_case_id, v_target, p_actor_user_id)
      on conflict (case_id, user_id) do nothing;

      perform public.append_audit_entry(
        p_actor_user_id, p_case_id, null,
        'CASE_ASSIGNED', 'SUCCESS', null,
        jsonb_build_object(
          'assigned_user_id', v_target,
          'primary_investigator', v_target = p_primary_investigator_id,
          'source', 'admin_case_management'
        )
      );
    end if;
  end loop;

  update public.cases
  set primary_investigator_id = p_primary_investigator_id,
      updated_at = now()
  where id = p_case_id;

  if v_old_primary is distinct from p_primary_investigator_id then
    perform public.append_audit_entry(
      p_actor_user_id, p_case_id, null,
      'CASE_UPDATED', 'SUCCESS', null,
      jsonb_build_object(
        'field', 'primary_investigator_id',
        'previous_user_id', v_old_primary,
        'new_user_id', p_primary_investigator_id,
        'source', 'admin_case_management'
      )
    );
  end if;

  return jsonb_build_object('ok', true, 'case_id', p_case_id);
end;
$$;

revoke all on function public.backend_admin_create_case(uuid,text,text,text,uuid,uuid[]) from public, anon, authenticated;
revoke all on function public.backend_admin_replace_case_assignments(uuid,uuid,uuid,uuid[]) from public, anon, authenticated;
grant execute on function public.backend_admin_create_case(uuid,text,text,text,uuid,uuid[]) to service_role;
grant execute on function public.backend_admin_replace_case_assignments(uuid,uuid,uuid,uuid[]) to service_role;

commit;
