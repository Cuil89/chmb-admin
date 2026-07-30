-- ============================================================
-- SQL MIGRATION: FITUR EDIT PROFIL USER & ALAMAT (CHMB STORE)
-- Jalankan script ini di: Supabase Dashboard > SQL Editor
-- ============================================================

-- 1. Tambah Kolom Profil Tambahan pada Tabel public.users (Non-destruktif)
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS phone_number TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. Buat Tabel Alamat Pengguna (user_addresses)
CREATE TABLE IF NOT EXISTS public.user_addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  label TEXT DEFAULT 'Rumah',
  recipient_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  full_address TEXT NOT NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index untuk mempercepat query alamat per user
CREATE INDEX IF NOT EXISTS idx_user_addresses_user_id ON public.user_addresses(user_id);

-- 3. Enable Row Level Security (RLS) pada Tabel user_addresses
ALTER TABLE public.user_addresses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Addresses" ON public.user_addresses;
CREATE POLICY "Public Read Addresses" ON public.user_addresses
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow Insert Addresses" ON public.user_addresses;
CREATE POLICY "Allow Insert Addresses" ON public.user_addresses
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow Update Addresses" ON public.user_addresses;
CREATE POLICY "Allow Update Addresses" ON public.user_addresses
  FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Allow Delete Addresses" ON public.user_addresses;
CREATE POLICY "Allow Delete Addresses" ON public.user_addresses
  FOR DELETE USING (true);

-- Grant Akses untuk Role Anon, Authenticated, & Service Role
GRANT ALL ON public.user_addresses TO anon, authenticated, service_role;

-- 4. Setup Supabase Storage Bucket 'avatars'
INSERT INTO storage.buckets (id, name, public) 
VALUES ('avatars', 'avatars', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Policy Storage Bucket avatars
DROP POLICY IF EXISTS "Public Read Avatars" ON storage.objects;
CREATE POLICY "Public Read Avatars" ON storage.objects
  FOR SELECT USING (bucket_id = 'avatars');

DROP POLICY IF EXISTS "Public Upload Avatars" ON storage.objects;
CREATE POLICY "Public Upload Avatars" ON storage.objects
  FOR ALL USING (bucket_id = 'avatars') WITH CHECK (bucket_id = 'avatars');
