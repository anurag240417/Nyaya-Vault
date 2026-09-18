-- Blockchain anchoring for the audit chain. public.integrity_anchors already
-- existed (see 001_casevault_core.sql) but nothing ever populated it. This
-- adds the columns needed to record a *public-blockchain* anchor (not just
-- a generic "anchor_provider/anchor_reference" pair) and a backend RPC that
-- atomically validates + records one, so recording an anchor and logging it
-- to the audit chain can never happen only halfway.

alter table public.integrity_anchors
  add column if not exists chain_id integer,
  add column if not exists block_number bigint,
  add column if not exists tx_status text not null default 'PENDING',
  add column if not exists explorer_url text;

do $$ begin
  alter table public.integrity_anchors
    add constraint integrity_anchors_tx_status_check
    check (tx_status in ('PENDING', 'CONFIRMED', 'FAILED'));
exception when duplicate_object then null; end $$;

alter type public.audit_action add value if not exists 'AUDIT_CHAIN_ANCHORED';
alter type public.audit_action add value if not exists 'AUDIT_CHAIN_ANCHOR_FAILED';

-- Records one anchor row and its audit entry atomically. audit_sequence /
-- audit_entry_hash are re-validated against the real audit_logs row here
-- (not just trusted from the caller) so a bug upstream can never anchor a
-- hash that doesn't actually correspond to that sequence.
create or replace function public.backend_record_integrity_anchor(
  p_actor_user_id uuid,
  p_audit_sequence bigint,
  p_audit_entry_hash text,
  p_anchor_provider text,
  p_anchor_reference text,
  p_chain_id integer,
  p_tx_status text,
  p_explorer_url text default null
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
  if not exists(select 1 from public.profiles p where p.id = p_actor_user_id and p.is_active = true) then
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
      'chain_id', p_chain_id, 'tx_status', p_tx_status
    )
  );

  return jsonb_build_object('ok', true, 'anchor_id', v_anchor_id);
end;
$$;

revoke all on function public.backend_record_integrity_anchor(uuid,bigint,text,text,text,integer,text,text) from public, anon, authenticated;
grant execute on function public.backend_record_integrity_anchor(uuid,bigint,text,text,text,integer,text,text) to service_role;
