-- ============================================================
-- SQL MIGRATION: FITUR WISHLIST / FAVORIT PRODUK (CHMB STORE)
-- Jalankan script ini di: Supabase Dashboard > SQL Editor
-- ============================================================

-- 1. Buat Tabel Wishlists
CREATE TABLE IF NOT EXISTS public.wishlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_user_product_wishlist UNIQUE (user_id, product_id)
);

-- Index untuk performa pencarian wishlist per user & per produk
CREATE INDEX IF NOT EXISTS idx_wishlists_user_id ON public.wishlists(user_id);
CREATE INDEX IF NOT EXISTS idx_wishlists_product_id ON public.wishlists(product_id);

-- 2. Enable Row Level Security (RLS)
ALTER TABLE public.wishlists ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Wishlists" ON public.wishlists;
CREATE POLICY "Public Read Wishlists" ON public.wishlists
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow Insert Wishlists" ON public.wishlists;
CREATE POLICY "Allow Insert Wishlists" ON public.wishlists
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow Delete Wishlists" ON public.wishlists;
CREATE POLICY "Allow Delete Wishlists" ON public.wishlists
  FOR DELETE USING (true);

-- 3. Grant Akses untuk Role Anon, Authenticated, & Service Role
GRANT ALL ON public.wishlists TO anon, authenticated, service_role;
