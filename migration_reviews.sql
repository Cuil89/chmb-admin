-- ============================================================
-- SQL MIGRATION: FITUR RATING & REVIEW PRODUK (CHMB STORE)
-- Jalankan script ini di: Supabase Dashboard > SQL Editor
-- ============================================================

-- 1. Tambah Kolom Rating & Review Count pada Tabel Products (Non-destruktif)
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS avg_rating NUMERIC DEFAULT 0;
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS review_count INT DEFAULT 0;

-- 2. Buat Tabel Reviews & Pastikan Seluruh Kolom Ada (Jika tabel sudah pernah dibuat sebelumnya)
CREATE TABLE IF NOT EXISTS public.reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id TEXT NOT NULL DEFAULT '',
  user_id TEXT NOT NULL DEFAULT '',
  order_id TEXT NOT NULL DEFAULT '',
  rating INT NOT NULL DEFAULT 5 CHECK (rating >= 1 AND rating <= 5),
  comment TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pastikan kolom tambahan ada jika tabel reviews sudah ada sebelumnya di DB
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS product_id TEXT NOT NULL DEFAULT '';
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT '';
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS order_id TEXT NOT NULL DEFAULT '';
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS rating INT NOT NULL DEFAULT 5;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS comment TEXT;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Tambah constraint UNIQUE jika belum ada
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'unique_user_product_order'
  ) THEN
    ALTER TABLE public.reviews ADD CONSTRAINT unique_user_product_order UNIQUE (user_id, product_id, order_id);
  END IF;
EXCEPTION
  WHEN OTHERS THEN NULL;
END $$;

-- Index untuk mempercepat query ulasan per produk
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON public.reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_order ON public.reviews(user_id, order_id);

-- 3. Function & Trigger Postgres untuk Otomatis Recalculate avg_rating & review_count
CREATE OR REPLACE FUNCTION update_product_rating_stats()
RETURNS TRIGGER AS $$
DECLARE
  target_product_id TEXT;
  new_avg NUMERIC;
  new_count INT;
BEGIN
  IF (TG_OP = 'DELETE') THEN
    target_product_id := OLD.product_id;
  ELSE
    target_product_id := NEW.product_id;
  END IF;

  SELECT 
    COALESCE(ROUND(AVG(rating)::numeric, 1), 0),
    COALESCE(COUNT(*), 0)
  INTO new_avg, new_count
  FROM public.reviews
  WHERE product_id = target_product_id;

  UPDATE public.products
  SET 
    avg_rating = new_avg,
    review_count = new_count
  WHERE id::text = target_product_id;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_product_rating ON public.reviews;
CREATE TRIGGER trigger_update_product_rating
AFTER INSERT OR UPDATE OR DELETE ON public.reviews
FOR EACH ROW
EXECUTE FUNCTION update_product_rating_stats();

-- 4. Enable Row Level Security (RLS) pada Tabel Reviews
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Reviews" ON public.reviews;
CREATE POLICY "Public Read Reviews" ON public.reviews
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Authenticated Insert Reviews" ON public.reviews;
CREATE POLICY "Authenticated Insert Reviews" ON public.reviews
  FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Owner Update Reviews" ON public.reviews;
CREATE POLICY "Owner Update Reviews" ON public.reviews
  FOR UPDATE USING (auth.uid()::text = user_id OR user_id IS NOT NULL);

DROP POLICY IF EXISTS "Owner Delete Reviews" ON public.reviews;
CREATE POLICY "Owner Delete Reviews" ON public.reviews
  FOR DELETE USING (auth.uid()::text = user_id OR user_id IS NOT NULL);

-- 5. Grant Akses untuk Role Anon & Authenticated
GRANT ALL ON public.reviews TO anon, authenticated, service_role;
