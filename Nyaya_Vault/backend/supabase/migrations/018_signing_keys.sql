-- Real cryptographic signing keys, one per user, for certificates and legal
-- notices (ECDSA P-256). Replaces the plain "typed name" issuer stamp with
-- an actual signature over the exact record being certified. The private
-- key column holds ciphertext only (encrypted in application code before
-- it ever reaches this table) - Postgres never sees a raw private key.

create table if not exists public.user_signing_keys (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  public_key_pem text not null,
  private_key_encrypted text not null,
  algorithm text not null default 'ECDSA-P256-SHA256',
  created_at timestamptz not null default now()
);

alter table public.user_signing_keys enable row level security;
-- Same boundary as every other business table: Python decides who may see
-- what (and here, ONLY ever the public_key_pem column - the encrypted
-- private key is never selected by any endpoint), not Postgres RLS.
revoke all on table public.user_signing_keys from anon, authenticated;
grant select, insert on table public.user_signing_keys to service_role;

alter type public.audit_action add value if not exists 'SIGNING_KEY_GENERATED';

-- Atomically "insert if missing, then read back whichever row actually
-- exists" - handles two concurrent first-uses for the same user without a
-- race where both generate a key but only one gets used going forward.
create or replace function public.backend_store_signing_key(
  p_user_id uuid,
  p_public_key_pem text,
  p_private_key_encrypted text,
  p_algorithm text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_row public.user_signing_keys;
begin
  if not exists(select 1 from public.profiles p where p.id = p_user_id and p.is_active = true) then
    return jsonb_build_object('ok', false, 'error', 'Actor profile is missing or inactive.');
  end if;

  insert into public.user_signing_keys(user_id, public_key_pem, private_key_encrypted, algorithm)
  values (p_user_id, p_public_key_pem, p_private_key_encrypted, coalesce(p_algorithm, 'ECDSA-P256-SHA256'))
  on conflict (user_id) do nothing;

  select * into v_row from public.user_signing_keys where user_id = p_user_id;

  if v_row.user_id is null then
    return jsonb_build_object('ok', false, 'error', 'Failed to store or read back the signing key.');
  end if;

  if v_row.public_key_pem = p_public_key_pem then
    perform public.append_audit_entry(
      p_user_id, null, null, 'SIGNING_KEY_GENERATED'::public.audit_action, 'SUCCESS'::public.audit_result,
      null, jsonb_build_object('algorithm', v_row.algorithm)
    );
  end if;

  return jsonb_build_object(
    'ok', true, 'public_key_pem', v_row.public_key_pem,
    'private_key_encrypted', v_row.private_key_encrypted, 'algorithm', v_row.algorithm,
    'created_at', v_row.created_at
  );
end;
$$;

revoke all on function public.backend_store_signing_key(uuid,text,text,text) from public, anon, authenticated;
grant execute on function public.backend_store_signing_key(uuid,text,text,text) to service_role;
