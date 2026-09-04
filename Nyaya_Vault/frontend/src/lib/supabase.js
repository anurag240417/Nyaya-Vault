import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.warn('Missing Supabase Auth environment variables. Copy .env.example to .env.');
}

// Supabase is used by the browser for Auth only. All CaseVault business
// reads/writes go through FastAPI (src/lib/api.js).
export const supabase = createClient(
  url || 'https://placeholder.invalid',
  key || 'placeholder',
  { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } },
);
