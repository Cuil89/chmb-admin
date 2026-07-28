-- ============================================================
-- JALANKAN SCRIPT INI DI: Supabase Dashboard > SQL Editor
-- Tujuan: Fix RLS agar mobile app bisa insert/upsert ke tabel users
-- ============================================================

-- 1. Pastikan tabel users ada dengan kolom yang benar
CREATE TABLE IF NOT EXISTS public.users (
  id uuid PRIMARY KEY,
  name text,
  email text UNIQUE,
  role text DEFAULT 'user',
  status text DEFAULT 'Terverifikasi',
  avatar text,
  created_at timestamptz DEFAULT now()
);

-- 2. Aktifkan RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- 3. Drop policy lama jika ada
DROP POLICY IF EXISTS "Users can insert their own data" ON public.users;
DROP POLICY IF EXISTS "Users can read all users" ON public.users;
DROP POLICY IF EXISTS "Users can update their own data" ON public.users;
DROP POLICY IF EXISTS "Service role full access" ON public.users;

-- 4. Policy: User bisa INSERT data diri sendiri saat signup
CREATE POLICY "Users can insert their own data"
  ON public.users
  FOR INSERT
  WITH CHECK (auth.uid() = id);

-- 5. Policy: Semua authenticated user bisa READ tabel users
CREATE POLICY "Users can read all users"
  ON public.users
  FOR SELECT
  USING (true);

-- 6. Policy: User hanya bisa UPDATE data diri sendiri
CREATE POLICY "Users can update their own data"
  ON public.users
  FOR UPDATE
  USING (auth.uid() = id);

-- 7. Grant akses ke anon & authenticated
GRANT SELECT, INSERT, UPDATE ON public.users TO anon;
GRANT SELECT, INSERT, UPDATE ON public.users TO authenticated;
