import os
import re
import json
import requests as req
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chmb-secret-flask-key-2026")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ubisgngdfdrhdnclfnln.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_4Hz3bB3u3Kw1kkzboMDhmA_OKL6shMi")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chmb2026")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ─── Helper Supabase REST ─────────────────────────────────────────────────────
def sb_get(table, params=None):
    r = req.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params)
    return r.json() if r.ok else []

def sb_insert(table, data):
    r = req.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    return r.ok, r.text

def sb_update(table, match_col, match_val, data):
    r = req.patch(f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}", headers=HEADERS, json=data)
    return r.ok, r.text

def sb_delete(table, match_col, match_val):
    r = req.delete(f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}", headers=HEADERS)
    return r.ok, r.text

# ─── Decorator: Wajib Login ───────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ─── AUTH ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login berhasil! Selamat datang di CHMB Admin.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Kamu sudah logout.', 'info')
    return redirect(url_for('login'))

# ─── DASHBOARD OVERVIEW ───────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        products = sb_get('products', {'select': '*'})
        transactions = sb_get('transactions', {'select': '*', 'order': 'created_at.desc'})

        total_products = len(products) if isinstance(products, list) else 0
        total_orders = len(transactions) if isinstance(transactions, list) else 0
        total_revenue = sum(t.get('total_harga', 0) for t in (transactions if isinstance(transactions, list) else []))
        pending_orders = [t for t in (transactions if isinstance(transactions, list) else []) if t.get('status') == 'Pending']
        recent_orders = (transactions if isinstance(transactions, list) else [])[:5]
    except Exception as e:
        flash(f'Error mengambil data: {e}', 'danger')
        total_products = total_orders = total_revenue = 0
        pending_orders = recent_orders = []

    return render_template('dashboard.html',
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,
        pending_count=len(pending_orders),
        recent_orders=recent_orders
    )

# ─── PRODUK & DYNAMIC RATING ───────────────────────────────────────────────
@app.route('/products')
@login_required
def products():
    product_list = sb_get('products', {'select': '*', 'order': 'name.asc'})
    reviews = sb_get('reviews', {'select': '*'})

    if not isinstance(product_list, list):
        flash('Error mengambil data produk.', 'danger')
        product_list = []
    
    # Calculate dynamic average ratings per product
    review_map = {}
    if isinstance(reviews, list):
        for r in reviews:
            pid = str(r.get('product_id', ''))
            if pid not in review_map:
                review_map[pid] = []
            if r.get('rating'):
                review_map[pid].append(float(r['rating']))

    for p in product_list:
        pid = str(p.get('id', ''))
        ratings = review_map.get(pid, [])
        if ratings:
            p['avg_rating'] = round(sum(ratings) / len(ratings), 1)
            p['review_count'] = len(ratings)
        else:
            p['avg_rating'] = None
            p['review_count'] = 0

    return render_template('products.html', products=product_list)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'price': float(request.form.get('price', 0)),
            'image_url': request.form.get('image_url'),
            'category': request.form.get('category'),
        }
        ok, msg = sb_insert('products', data)
        if ok:
            flash(f'Produk "{data["name"]}" berhasil ditambahkan!', 'success')
            return redirect(url_for('products'))
        else:
            flash(f'Gagal menambahkan produk: {msg}', 'danger')

    return render_template('product_form.html', product=None, action='Tambah')

@app.route('/products/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    result = sb_get('products', {'select': '*', 'id': f'eq.{product_id}'})
    if not result or not isinstance(result, list):
        flash('Produk tidak ditemukan.', 'danger')
        return redirect(url_for('products'))
    product = result[0]

    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'price': float(request.form.get('price', 0)),
            'image_url': request.form.get('image_url'),
            'category': request.form.get('category'),
        }
        ok, msg = sb_update('products', 'id', product_id, data)
        if ok:
            flash(f'Produk "{data["name"]}" berhasil diupdate!', 'success')
            return redirect(url_for('products'))
        else:
            flash(f'Gagal mengupdate produk: {msg}', 'danger')

    return render_template('product_form.html', product=product, action='Edit')

@app.route('/products/delete/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    ok, msg = sb_delete('products', 'id', product_id)
    if ok:
        flash('Produk berhasil dihapus.', 'success')
    else:
        flash(f'Gagal menghapus produk: {msg}', 'danger')
    return redirect(url_for('products'))

# ─── PESANAN & BUKTI BAYAR ───────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    order_list = sb_get('transactions', {'select': '*', 'order': 'created_at.desc'})
    if not isinstance(order_list, list):
        flash('Error mengambil data pesanan.', 'danger')
        order_list = []
    return render_template('orders.html', orders=order_list)

@app.route('/orders/update-status/<order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    ok, msg = sb_update('transactions', 'id', order_id, {'status': new_status})
    if ok:
        flash(f'Status pesanan berhasil diubah menjadi "{new_status}"!', 'success')
    else:
        flash(f'Gagal update status: {msg}', 'danger')
    return redirect(url_for('orders'))

# ─── ULASAN & RATING PEMBELI ────────────────────────────────────────────────
@app.route('/reviews')
@login_required
def reviews():
    review_list = sb_get('reviews', {'select': '*', 'order': 'created_at.desc'})
    products = sb_get('products', {'select': 'id, name, image_url'})

    prod_dict = {}
    if isinstance(products, list):
        for p in products:
            prod_dict[str(p['id'])] = p

    if isinstance(review_list, list):
        for r in review_list:
            pid = str(r.get('product_id', ''))
            r['product_info'] = prod_dict.get(pid, {'name': 'Produk dihapus', 'image_url': ''})
    else:
        review_list = []

    return render_template('reviews.html', reviews=review_list)

@app.route('/reviews/delete/<review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    ok, msg = sb_delete('reviews', 'id', review_id)
    if ok:
        flash('Ulasan berhasil dihapus.', 'success')
    else:
        flash(f'Gagal menghapus ulasan: {msg}', 'danger')
    return redirect(url_for('reviews'))

# ─── AI AUTO-GENERATE (Gemini) ───────────────────────────────────────────────
@app.route('/api/ai-generate', methods=['POST'])
@login_required
def ai_generate():
    if not GEMINI_KEY:
        return jsonify({'error': 'GEMINI_KEY belum diset di environment variables.'}), 500

    keyword = request.json.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': 'Keyword tidak boleh kosong.'}), 400

    prompt = f"""Kamu adalah copywriter dan E-commerce Specialist untuk brand fashion streetwear Indonesia bernama CHMB.
Buat data produk lengkap dan akurat berdasarkan keyword/nama berikut: "{keyword}".

Sediakan juga salah satu URL gambar streetwear berkualitas tinggi dari Unsplash yang paling cocok:
- T-Shirt: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80"
- Hoodie: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80"
- Pants: "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80"

Balas HANYA dengan JSON valid (tanpa markdown), format:
{{
  "name": "Nama produk CHMB yang catchy, keren, dan rapi",
  "description": "Deskripsi produk 2-3 kalimat menarik dalam Bahasa Indonesia, sebutkan bahan (seperti Cotton Combed 24s / Heavyweight Fleece), keunggulan, dan gaya fitting",
  "category": "T-Shirt" atau "Hoodie" atau "Pants",
  "price": estimasi harga realistis (angka saja, contoh: 179000 untuk T-Shirt, 329000 untuk Hoodie, 289000 untuk Pants),
  "image_url": "pilih salah satu URL gambar di atas yang paling sesuai dengan kategori"
}}"""

    try:
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
        r = None
        for m in models_to_try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
            gemini_headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = req.post(gemini_url, headers=gemini_headers, json=payload, timeout=15)
            if res.status_code == 200:
                r = res
                break
            elif res.status_code != 404:
                r = res

        if not r:
            return jsonify({'error': 'Model Gemini tidak ditemukan.'}), 404

        if r.status_code == 429:
            return jsonify({'error': 'Quota API Gemini sedang penuh / terlampaui (Rate Limit / Quota Exceeded). Silakan coba beberapa saat lagi atau ganti API Key di AI Studio.'}), 429
        elif not r.ok:
            err_msg = r.json().get('error', {}).get('message', r.text)
            return jsonify({'error': f'Gemini API Error ({r.status_code}): {err_msg}'}), r.status_code

        raw = r.json()['candidates'][0]['content']['parts'][0]['text']
        # Bersihkan markdown code block kalau ada
        clean = re.sub(r'```(?:json)?|```', '', raw).strip()
        result = json.loads(clean)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({'error': 'AI mengembalikan format tidak valid, coba lagi.'}), 500
    except Exception as e:
        return jsonify({'error': f'Gagal generate: {str(e)}'}), 500


# ─── SCRAPE TOKOPEDIA / URL IMPORT (EXACT DATA) ──────────────────────────────
@app.route('/api/scrape-url', methods=['POST'])
@login_required
def scrape_url():
    url = request.json.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Masukkan URL produk yang valid.'}), 400

    # 1. Coba pake Jina AI Reader (rendering headless browser Tokopedia)
    try:
        jina_endpoint = f"https://r.jina.ai/{url}"
        r = req.get(jina_endpoint, timeout=12)
        if r.ok and len(r.text) > 500:
            text = r.text
            result = {}

            # Extrak Judul Asli Lengkap
            h2_match = re.search(r'##\s*(.*?)(?:\n|\r|$)', text)
            title_match = re.search(r'Title:\s*(.*?)(?:\s*di\s*.*\|\s*Tokopedia|\n)', text, re.IGNORECASE)
            
            raw_title = ""
            if h2_match:
                raw_title = h2_match.group(1).strip()
            elif title_match:
                raw_title = title_match.group(1).strip()

            if raw_title:
                # Ambil judul lengkap sebelum varian "- Hitam, S" jika ada
                full_name = raw_title.split(' - ')[0].strip()
                result['name'] = full_name[:120]

            # Extrak Harga Asli (misal Rp842.200 atau Rp882.200)
            price_matches = re.findall(r'Rp[\s.]*(\d+[\d.]*)', text)
            for pm in price_matches:
                clean_p = pm.replace('.', '').replace(',', '')
                if clean_p.isdigit() and int(clean_p) > 10000:
                    result['price'] = int(clean_p)
                    break

            # Extrak Gambar High-Res Asli dari Tokopedia CDN
            img_matches = re.findall(r'https://[^\s\)\"\']+(?:tokopedia-static|tokopedia\.net|aphluv)[^\s\)\"\']*(?:1600|800|700|jpeg|jpg|png|webp)', text, re.IGNORECASE)
            for img in img_matches:
                if 'logo' not in img and 'icon' not in img and 'zeus' not in img:
                    result['image_url'] = img
                    break

            # Tebak Kategori
            name_lower = (result.get('name') or '').lower()
            if any(k in name_lower for k in ['hoodie', 'zipper', 'sweater', 'crewneck', 'jaket']):
                result['category'] = 'Hoodie'
            elif any(k in name_lower for k in ['pants', 'celana', 'cargo', 'sweatpants', 'jogger']):
                result['category'] = 'Pants'
            else:
                result['category'] = 'T-Shirt'

            # Extrak Deskripsi atau buat deskripsi berbasis nama asli
            if result.get('name'):
                result['description'] = f"Produk pilihan {result['name']} original Tokopedia dengan kualitas bahan premium dan jahitan rapi, nyaman dipakai untuk aktivitas sehari-hari."
                return jsonify(result)
    except Exception as e:
        print(f"Jina scrape error: {e}")

    # 2. FALLBACK ke Gemini AI jika Jina tidak memberikan data
    if GEMINI_KEY:
        raw_slug = url.split('?')[0].split('/')[-1]
        slug_clean = re.sub(r'-\d+$', '', raw_slug).replace('-', ' ').replace('_', ' ').title()
        
        prompt = f"""Kamu adalah E-commerce Data Extractor profesional. Ekstrak data dari nama produk Tokopedia berikut: "{slug_clean}".

Balas HANYA dengan JSON valid (tanpa markdown):
{{
  "name": "{slug_clean}",
  "description": "Deskripsi produk streetwear CHMB premium yang bagus dan detail 2 kalimat",
  "category": "Hoodie",
  "price": 842000,
  "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80"
}}"""
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
            gemini_headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            g_res = req.post(gemini_url, headers=gemini_headers, json=payload, timeout=10)
            if g_res.ok:
                raw = g_res.json()['candidates'][0]['content']['parts'][0]['text']
                clean = re.sub(r'```(?:json)?|```', '', raw).strip()
                ai_data = json.loads(clean)
                return jsonify(ai_data)
        except Exception:
            pass

    return jsonify({'error': 'Tidak bisa membaca data dari URL ini.'}), 422


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
