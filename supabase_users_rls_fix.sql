-- ============================================================
-- JALANKAN SCRIPT INI DI: Supabase Dashboard > SQL Editor
-- Tujuan: Setup Tabel Users, Transactions & Storage Bucket Bukti Bayar
-- ============================================================

-- 1. Tabel Users
CREATE TABLE IF NOT EXISTS public.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  email text UNIQUE,
  role text DEFAULT 'user',
  status text DEFAULT 'Terverifikasi',
  avatar text,
  created_at timestamptz DEFAULT now()
);

-- 2. Tabel Transactions (Lengkap Kolom Alamat & Resi)
CREATE TABLE IF NOT EXISTS public.transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text,
  total_harga numeric DEFAULT 0,
  alamat text,
  courier text,
  payment_method text,
  proof_image_url text,
  resi_number text,
  status text DEFAULT 'Menunggu Pembayaran',
  items jsonb,
  created_at timestamptz DEFAULT now()
);

-- Tambah kolom jika tabel transaksi sudah ada tapi belum lengkap
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS user_id text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS order_ref text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS total_harga numeric DEFAULT 0;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS alamat text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS courier text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS payment_method text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS proof_image_url text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS resi_number text;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS status text DEFAULT 'Menunggu Pembayaran';
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS items jsonb;
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

-- 3. Kebijakan RLS (Row Level Security) untuk Tabel Users & Transactions
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for users" ON public.users;
CREATE POLICY "Allow all for users" ON public.users FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for transactions" ON public.transactions;
CREATE POLICY "Allow all for transactions" ON public.transactions FOR ALL USING (true) WITH CHECK (true);

-- 4. Grant Akses Anon & Authenticated
GRANT ALL ON public.users TO anon, authenticated;
GRANT ALL ON public.transactions TO anon, authenticated;

-- 5. Setup Storage Bucket payment_proofs
INSERT INTO storage.buckets (id, name, public) 
VALUES ('payment_proofs', 'payment_proofs', true)
ON CONFLICT (id) DO UPDATE SET public = true;

DROP POLICY IF EXISTS "Public Upload Payment Proofs" ON storage.objects;
CREATE POLICY "Public Upload Payment Proofs" ON storage.objects
  FOR ALL USING (bucket_id = 'payment_proofs') WITH CHECK (bucket_id = 'payment_proofs');
