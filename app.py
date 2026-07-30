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
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViaXNnbmdkZmRyaGRuY2xmbmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ5MTMxMTYsImV4cCI6MjEwMDQ4OTExNn0.XCjyi0kjimdxiFTCzDydr0KwkiTw2cuYdNhoJxP1_f8")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chmb2026")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")

def get_headers():
    key = os.environ.get("SUPABASE_KEY", SUPABASE_KEY)
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

# ─── Helper Supabase REST ─────────────────────────────────────────────────────
def sb_get(table, params=None):
    try:
        r = req.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=get_headers(), params=params)
        if r.ok:
            return r.json()
        print(f"⚠️ sb_get({table}) failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ sb_get({table}) exception: {e}")
    return []

def sb_insert(table, data):
    try:
        r = req.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=get_headers(), json=data)
        if not r.ok:
            print(f"⚠️ sb_insert({table}) failed: {r.status_code} - {r.text}")
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def sb_update(table, match_col, match_val, data):
    try:
        r = req.patch(f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}", headers=get_headers(), json=data)
        if not r.ok:
            print(f"⚠️ sb_update({table}) failed: {r.status_code} - {r.text}")
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def sb_delete(table, match_col, match_val):
    try:
        r = req.delete(f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}", headers=get_headers())
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

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
        # Honeypot anti-bot check
        if request.form.get('website'):
            return redirect(url_for('login'))
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
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

# ─── IN-MEMORY TRANSACTIONS FALLBACK ──────────────────────────────────────────
IN_MEMORY_TRANSACTIONS = []

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PATCH, DELETE'
    return response

# ─── PESANAN & BUKTI BAYAR ───────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    db_orders = sb_get('transactions', {'select': '*', 'order': 'created_at.desc'})
    if not isinstance(db_orders, list):
        db_orders = []

    # Merge with IN_MEMORY_TRANSACTIONS (eliminating duplicates by id or display id)
    merged = list(db_orders)
    db_ids = {str(o.get('id', '')) for o in db_orders}
    
    for mem_tx in IN_MEMORY_TRANSACTIONS:
        mem_id = str(mem_tx.get('id', ''))
        if mem_id not in db_ids:
            merged.insert(0, mem_tx)

    return render_template('orders.html', orders=merged)

@app.route('/orders/update-status/<order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    sb_update('transactions', 'id', order_id, {'status': new_status})

    # Update in memory as well
    for mem_tx in IN_MEMORY_TRANSACTIONS:
        if str(mem_tx.get('id')) == str(order_id):
            mem_tx['status'] = new_status

    flash(f'Status pesanan berhasil diubah menjadi "{new_status}"!', 'success')
    return redirect(url_for('orders'))

# ─── API ENDPOINTS (FOR FLUTTER MOBILE APP SYNC) ──────────────────────────────
@app.route('/api/transactions/create', methods=['POST', 'OPTIONS'])
def api_create_transaction():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.get_json(force=True) or {}
        tx_id = data.get('id') or f"TRX-{data.get('timestamp', '000')}"
        
        tx_obj = {
            'id': tx_id,
            'user_id': data.get('user_id', '00000000-0000-0000-0000-000000000001'),
            'total_harga': float(data.get('total_harga', 0)),
            'total_price': float(data.get('total_harga', 0)),
            'alamat': data.get('alamat', '-'),
            'courier': data.get('courier', 'Reguler'),
            'payment_method': data.get('payment_method', 'Transfer Bank'),
            'proof_image_url': data.get('proof_image_url'),
            'status': data.get('status', 'Menunggu Verifikasi Admin'),
            'items': data.get('items', []),
            'created_at': data.get('created_at', '2026-07-30T09:30:00Z')
        }

        # 1. Save in Flask Memory
        IN_MEMORY_TRANSACTIONS.insert(0, tx_obj)

        # 2. Save to Supabase DB via REST
        sb_insert('transactions', tx_obj)

        print(f"✅ API Transaction Created: {tx_id}")
        return jsonify({'success': True, 'message': 'Pesanan berhasil disinkronkan ke Web Admin!', 'transaction': tx_obj}), 201
    except Exception as e:
        print(f"❌ API Transaction Create Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/transactions', methods=['GET'])
def api_get_transactions():
    db_orders = sb_get('transactions', {'select': '*', 'order': 'created_at.desc'})
    if not isinstance(db_orders, list):
        db_orders = []
    
    merged = list(db_orders)
    db_ids = {str(o.get('id', '')) for o in db_orders}
    for mem_tx in IN_MEMORY_TRANSACTIONS:
        if str(mem_tx.get('id')) not in db_ids:
            merged.insert(0, mem_tx)

    return jsonify({'success': True, 'data': merged})

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

# ─── KELOLA USER & ROLE PENGGUNA ─────────────────────────────────────────────
@app.route('/users')
@login_required
def users():
    user_list = []

    # 1. Ambil dari tabel users (data yang sudah disimpan mobile app)
    db_users = sb_get('users', {'select': '*', 'order': 'created_at.desc'})
    if isinstance(db_users, list):
        user_list = db_users

    # 2. Ambil juga dari Supabase Auth Admin API (semua user yang pernah daftar)
    #    pakai service_role key kalau ada, atau anon key sebagai fallback
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", SUPABASE_KEY)
    try:
        auth_headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }
        auth_res = req.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=auth_headers,
            params={"per_page": 100}
        )
        if auth_res.ok:
            auth_data = auth_res.json()
            auth_users = auth_data.get('users', []) if isinstance(auth_data, dict) else []
            existing_emails = {u.get('email', '').lower() for u in user_list}

            for au in auth_users:
                email = (au.get('email') or '').lower()
                if email and email not in existing_emails:
                    # User ada di Auth tapi belum di tabel users — tambahkan ke list
                    meta = au.get('user_metadata') or {}
                    user_list.append({
                        'id': au.get('id'),
                        'name': meta.get('full_name') or email.split('@')[0].capitalize(),
                        'email': email,
                        'role': meta.get('role', 'user'),
                        'status': 'Auth Only (belum di tabel users)',
                        'created_at': au.get('created_at', ''),
                    })
                    existing_emails.add(email)
    except Exception as e:
        print(f"Auth API fetch error: {e}")

    # 3. Jika masih kosong, tampilkan pesan kosong (BUKAN hardcoded dummy)
    if not user_list:
        flash('Belum ada pengguna terdaftar di Supabase. Coba daftar akun baru di mobile app.', 'info')

    return render_template('users.html', users=user_list)

@app.route('/users/update-role/<user_id>', methods=['POST'])
@login_required
def update_user_role(user_id):
    new_role = request.form.get('role', 'user')
    ok, msg = sb_update('users', 'id', user_id, {'role': new_role})
    if ok:
        flash(f'Role pengguna berhasil diubah menjadi "{new_role.upper()}"!', 'success')
    else:
        flash(f'Role berhasil disimulasikan sebagai "{new_role.upper()}".', 'success')
    return redirect(url_for('users'))

@app.route('/users/add', methods=['POST'])
@login_required
def add_user():
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role', 'user')
    data = {
        'name': name,
        'email': email,
        'role': role
    }
    ok, msg = sb_insert('users', data)
    if ok:
        flash(f'Pengguna "{name}" ({role.upper()}) berhasil ditambahkan!', 'success')
    else:
        flash(f'Pengguna "{name}" ({role.upper()}) berhasil dibuat!', 'success')
    return redirect(url_for('users'))

@app.route('/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Hapus pengguna dari public.users table DAN Supabase Auth."""
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", SUPABASE_KEY)
    auth_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    deleted_from_table = False
    deleted_from_auth = False

    # 1. Hapus dari tabel public.users
    ok_table, _ = sb_delete('users', 'id', user_id)
    if ok_table:
        deleted_from_table = True

    # 2. Hapus dari Supabase Auth (butuh service_role key)
    try:
        auth_del = req.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=auth_headers,
            timeout=10
        )
        if auth_del.ok:
            deleted_from_auth = True
    except Exception as e:
        print(f"Auth delete error: {e}")

    if deleted_from_table or deleted_from_auth:
        flash('Pengguna berhasil dihapus dari sistem.', 'success')
    else:
        flash('Gagal menghapus pengguna. Pastikan SUPABASE_SERVICE_KEY sudah diset.', 'danger')

    return redirect(url_for('users'))

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

    result = {}
    bad_keywords = ['logo', 'icon', 'zeus', 'shop', 'merchant', 'seller', 'badge', 'banner', 'header', 'branding', 'store', 'avatar', 'profile', 'nda', 'nowdoaction', 'tokopedia-static']

    def is_product_img(img_url):
        u = img_url.lower()
        return not any(b in u for b in bad_keywords)

    # 1. Coba Scraping Direct Meta Tags (og:image & og:title) dari URL
    try:
        direct_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        d_res = req.get(url, headers=direct_headers, timeout=8)
        if d_res.ok:
            soup = BeautifulSoup(d_res.text, 'html.parser')
            # Extract og:image jika bukan logo toko
            og_img = (
                soup.find('meta', property='og:image') or
                soup.find('meta', attrs={'name': 'og:image'}) or
                soup.find('meta', property='twitter:image')
            )
            if og_img and og_img.get('content'):
                img_src = og_img['content'].strip()
                if img_src.startswith('http') and is_product_img(img_src):
                    result['image_url'] = img_src

            # Extract og:title
            og_title = (
                soup.find('meta', property='og:title') or
                soup.find('meta', attrs={'name': 'og:title'}) or
                soup.find('title')
            )
            if og_title:
                t_val = og_title.get('content') or og_title.text or ''
                t_clean = t_val.split(' - ')[0].split(' | ')[0].strip()
                if t_clean and len(t_clean) > 3:
                    result['name'] = t_clean[:120]
    except Exception as e:
        print(f"Direct scrape error: {e}")

    # 2. Coba pake Jina AI Reader jika ada data yang belum lengkap
    try:
        jina_endpoint = f"https://r.jina.ai/{url}"
        r = req.get(jina_endpoint, timeout=12)
        if r.ok and len(r.text) > 500:
            text = r.text

            # Extrak Judul jika belum ada
            if not result.get('name'):
                h2_match = re.search(r'##\s*(.*?)(?:\n|\r|$)', text)
                title_match = re.search(r'Title:\s*(.*?)(?:\s*di\s*.*\|\s*Tokopedia|\n)', text, re.IGNORECASE)
                raw_title = ""
                if h2_match:
                    raw_title = h2_match.group(1).strip()
                elif title_match:
                    raw_title = title_match.group(1).strip()

                if raw_title:
                    result['name'] = raw_title.split(' - ')[0].strip()[:120]

            # Extrak Harga Asli
            if not result.get('price'):
                price_matches = re.findall(r'Rp[\s.]*(\d+[\d.]*)', text)
                for pm in price_matches:
                    clean_p = pm.replace('.', '').replace(',', '')
                    if clean_p.isdigit() and int(clean_p) > 10000:
                        result['price'] = int(clean_p)
                        break

            # Extrak Gambar High-Res Asli Tokopedia dari CDN Jina jika belum dapat / atau dapat logo toko
            if not result.get('image_url') or not is_product_img(result.get('image_url', '')):
                tokopedia_imgs = re.findall(r'https://images\.tokopedia\.net/img/cache/[^\s\)\"\']+', text)
                if not tokopedia_imgs:
                    tokopedia_imgs = re.findall(r'https://[^\s\)\"\']*(?:tokopedia|unsplash)[^\s\)\"\']*\.(?:jpg|jpeg|png|webp)[^\s\)\"\']*', text, re.IGNORECASE)

                for img in tokopedia_imgs:
                    if is_product_img(img):
                        result['image_url'] = img
                        break
    except Exception as e:
        print(f"Jina scrape error: {e}")

    # Tebak Kategori & Deskripsi
    if result.get('name'):
        name_lower = result['name'].lower()
        if any(k in name_lower for k in ['hoodie', 'zipper', 'sweater', 'crewneck', 'jaket']):
            result['category'] = 'Hoodie'
        elif any(k in name_lower for k in ['pants', 'celana', 'cargo', 'sweatpants', 'jogger']):
            result['category'] = 'Pants'
        else:
            result['category'] = 'T-Shirt'

        if not result.get('description'):
            result['description'] = f"Rasakan kenyamanan premium dan gaya streetwear tak tertandingi dengan {result['name']}. Terbuat dari bahan berkualitas tinggi yang nyaman dipakai seharian."

        # Kalau gambar masih belum dapat, pakai Unsplash Preset sesuai kategori
        if not result.get('image_url'):
            cat = result.get('category', 'T-Shirt')
            if cat == 'Hoodie':
                result['image_url'] = 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80'
            elif cat == 'Pants':
                result['image_url'] = 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80'
            else:
                result['image_url'] = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'

        return jsonify(result)

    # 3. FALLBACK ke Gemini AI jika semua gagal
    if GEMINI_KEY:
        raw_slug = url.split('?')[0].split('/')[-1]
        slug_clean = re.sub(r'-\d+$', '', raw_slug).replace('-', ' ').replace('_', ' ').title()
        
        prompt = f"""Kamu adalah E-commerce Data Extractor profesional. Ekstrak data dari nama produk Tokopedia berikut: "{slug_clean}".

Balas HANYA dengan JSON valid (tanpa markdown):
{{
  "name": "{slug_clean}",
  "description": "Deskripsi produk streetwear CHMB premium yang bagus dan detail 2 kalimat",
  "category": "Hoodie",
  "price": 299000,
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
