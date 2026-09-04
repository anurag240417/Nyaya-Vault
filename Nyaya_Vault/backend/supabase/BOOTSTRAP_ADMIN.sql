-- Run manually after creating your first account in Supabase Auth.
-- Replace the email before executing.
update public.profiles
set role='ADMIN', clearance_level='SECRET', is_active=true, updated_at=now()
where lower(email)=lower('YOUR_EMAIL@example.com');

select id,email,username,role,clearance_level,is_active
from public.profiles
where lower(email)=lower('YOUR_EMAIL@example.com');
