-- Scheduled (system-initiated) anchoring: there is no logged-in user, so the
-- actor may now be null, and the audit entry records whether an anchor was
-- created manually by an admin or by the scheduler. Replaces the 017
-- signature (dropped first - leaving both would make named-argument RPC
-- calls ambiguous between the two overloads).

drop function if exists public.backend_record_integrity_anchor(uuid,bigint,text,text,text,integer,text,text);

create or replace function public.backend_record_integrity_anchor(
  p_actor_user_id uuid,
  p_audit_sequence bigint,
  p_audit_entry_hash text,
  p_anchor_provider text,
  p_anchor_reference text,
  p_chain_id integer,
  p_tx_status text,
  p_explorer_url text default null,
  p_source text default 'manual'
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_actual_hash text;
  v_anchor_id uuid;
begin
  if p_actor_user_id is not null
     and not exists(select 1 from public.profiles p where p.id = p_actor_user_id and p.is_active = true) then
    return jsonb_build_object('ok', false, 'error', 'Actor profile is missing or inactive.');
  end if;
  if p_audit_entry_hash !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'error', 'Invalid entry hash.');
  end if;

  select entry_hash into v_actual_hash from public.audit_logs where sequence = p_audit_sequence;
  if v_actual_hash is null then
    return jsonb_build_object('ok', false, 'error', 'No audit entry exists at that sequence.');
  end if;
  if v_actual_hash <> lower(p_audit_entry_hash) then
    return jsonb_build_object('ok', false, 'error', 'Entry hash does not match the audit log at that sequence.');
  end if;

  insert into public.integrity_anchors(
    case_id, audit_sequence, audit_entry_hash, anchor_provider, anchor_reference,
    chain_id, tx_status, explorer_url, created_by
  ) values (
    null, p_audit_sequence, lower(p_audit_entry_hash), p_anchor_provider, p_anchor_reference,
    p_chain_id, coalesce(p_tx_status, 'PENDING'), p_explorer_url, p_actor_user_id
  ) returning id into v_anchor_id;

  perform public.append_audit_entry(
    p_actor_user_id, null, null,
    (case when p_tx_status = 'FAILED' then 'AUDIT_CHAIN_ANCHOR_FAILED' else 'AUDIT_CHAIN_ANCHORED' end)::public.audit_action,
    (case when p_tx_status = 'FAILED' then 'FAILED' else 'SUCCESS' end)::public.audit_result,
    null,
    jsonb_build_object(
      'anchor_id', v_anchor_id, 'audit_sequence', p_audit_sequence,
      'anchor_provider', p_anchor_provider, 'anchor_reference', p_anchor_reference,
      'chain_id', p_chain_id, 'tx_status', p_tx_status, 'source', coalesce(p_source, 'manual')
    )
  );

  return jsonb_build_object('ok', true, 'anchor_id', v_anchor_id);
end;
$$;

revoke all on function public.backend_record_integrity_anchor(uuid,bigint,text,text,text,integer,text,text,text) from public, anon, authenticated;
grant execute on function public.backend_record_integrity_anchor(uuid,bigint,text,text,text,integer,text,text,text) to service_role;
