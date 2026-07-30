-- ==============================================================================
-- MASTER DATABASE SCHEMA & SEED DATA (CHMB STORE E-COMMERCE)
-- Database Engine : Supabase PostgreSQL 15
-- Backend REST API: Flask (Vercel Serverless)
-- Mobile Client   : Flutter (GetX State Management)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TABEL PENGGUNA (users)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  full_name TEXT,
  email TEXT UNIQUE NOT NULL,
  phone_number TEXT,
  avatar TEXT,
  avatar_url TEXT,
  role TEXT DEFAULT 'user', -- 'user', 'admin', 'guest'
  status TEXT DEFAULT 'Terverifikasi',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Data Contoh Pengguna
INSERT INTO public.users (id, name, full_name, email, phone_number, role, status)
VALUES 
  ('00000000-0000-0000-0000-000000000001', 'Budi Santoso', 'Budi Santoso', 'budi.santoso@gmail.com', '081234567890', 'user', 'Terverifikasi'),
  ('00000000-0000-0000-0000-000000000002', 'Admin CHMB', 'Admin CHMB Store', 'admin@chmb.com', '081987654321', 'admin', 'Terverifikasi'),
  ('00000000-0000-0000-0000-000000000003', 'Siti Rahma', 'Siti Rahma', 'siti.rahma@gmail.com', '085712345678', 'user', 'Terverifikasi')
ON CONFLICT (email) DO NOTHING;


-- ------------------------------------------------------------------------------
-- 2. TABEL KATALOG PRODUK (products)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  price NUMERIC NOT NULL,
  category TEXT NOT NULL,
  stock INT DEFAULT 50,
  image_url TEXT,
  avg_rating NUMERIC DEFAULT 0,
  review_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Data Contoh Produk Pakaian
INSERT INTO public.products (id, name, description, price, category, stock, image_url, avg_rating, review_count)
VALUES 
  ('PROD-001', 'Kemeja Linen Premium White', 'Kemeja bahan linen halus dan adem cocok untuk santai maupun formal.', 189000, 'Kemeja', 25, 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=500', 4.8, 12),
  ('PROD-002', 'Kaos Over-sized Cotton 24s', 'Kaos oversize 100% katun combed 24s lembut dan menyerap keringat.', 99000, 'Kaos', 40, 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500', 4.7, 8),
  ('PROD-003', 'Jaket Denim Vintage Blue', 'Jaket denim gaya klasik vintage dengan jahitan kuat dan durable.', 299000, 'Jaket', 15, 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500', 4.9, 15),
  ('PROD-004', 'Celana Chino Slimfit Navy', 'Celana chino stretch slimfit bahan melar nyaman digunakan seharian.', 175000, 'Celana', 30, 'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500', 4.6, 6)
ON CONFLICT (id) DO NOTHING;


-- ------------------------------------------------------------------------------
-- 3. TABEL TRANSAKSI & PESANAN (transactions)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_ref TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  items JSONB NOT NULL,
  total_amount NUMERIC NOT NULL,
  payment_method TEXT DEFAULT 'BCA Transfer',
  payment_proof_url TEXT,
  status TEXT DEFAULT 'PENDING', -- 'PENDING', 'PAID', 'SHIPPED', 'CANCELLED'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ------------------------------------------------------------------------------
-- 4. TABEL ULASAN PRODUK (reviews)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  user_name TEXT NOT NULL,
  user_avatar TEXT,
  rating INT CHECK (rating >= 1 AND rating <= 5),
  comment TEXT NOT NULL,
  order_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON public.reviews(product_id);


-- ------------------------------------------------------------------------------
-- 5. TABEL WISHLIST / PRODUK FAVORIT (wishlists)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wishlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_user_product_wishlist UNIQUE (user_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_wishlists_user_id ON public.wishlists(user_id);


-- ------------------------------------------------------------------------------
-- 6. TABEL ALAMAT PENGGUNA (user_addresses)
-- ------------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_user_addresses_user_id ON public.user_addresses(user_id);


-- ------------------------------------------------------------------------------
-- 7. ROW LEVEL SECURITY (RLS) POLICIES & PERMISSIONS
-- ------------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wishlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_addresses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public Read Access" ON public.users FOR SELECT USING (true);
CREATE POLICY "Public Write Access" ON public.users FOR ALL USING (true);

CREATE POLICY "Public Read Access Products" ON public.products FOR SELECT USING (true);
CREATE POLICY "Public Write Access Products" ON public.products FOR ALL USING (true);

CREATE POLICY "Public Read Access Transactions" ON public.transactions FOR SELECT USING (true);
CREATE POLICY "Public Write Access Transactions" ON public.transactions FOR ALL USING (true);

CREATE POLICY "Public Read Access Reviews" ON public.reviews FOR SELECT USING (true);
CREATE POLICY "Public Write Access Reviews" ON public.reviews FOR ALL USING (true);

CREATE POLICY "Public Read Access Wishlists" ON public.wishlists FOR SELECT USING (true);
CREATE POLICY "Public Write Access Wishlists" ON public.wishlists FOR ALL USING (true);

CREATE POLICY "Public Read Access Addresses" ON public.user_addresses FOR SELECT USING (true);
CREATE POLICY "Public Write Access Addresses" ON public.user_addresses FOR ALL USING (true);

GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
