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

# ─── PRODUK ───────────────────────────────────────────────────────────────────
@app.route('/products')
@login_required
def products():
    product_list = sb_get('products', {'select': '*', 'order': 'name.asc'})
    if not isinstance(product_list, list):
        flash('Error mengambil data produk.', 'danger')
        product_list = []
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

# ─── PESANAN ──────────────────────────────────────────────────────────────────
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

# ─── AI AUTO-GENERATE (Gemini) ───────────────────────────────────────────────
@app.route('/api/ai-generate', methods=['POST'])
@login_required
def ai_generate():
    if not GEMINI_KEY:
        return jsonify({'error': 'GEMINI_KEY belum diset di environment variables.'}), 500

    keyword = request.json.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': 'Keyword tidak boleh kosong.'}), 400

    prompt = f"""Kamu adalah copywriter untuk brand fashion streetwear Indonesia bernama CHMB.
Buat data produk lengkap berdasarkan keyword berikut: "{keyword}".

Balas HANYA dengan JSON valid (tidak ada teks lain), format:
{{
  "name": "nama produk CHMB yang catchy dan lengkap",
  "description": "deskripsi produk 1-2 kalimat, bahasa Indonesia, sebutkan bahan/keunggulan",
  "category": "pilih salah satu: T-Shirt, Hoodie, atau Pants",
  "price": angka harga dalam rupiah (tanpa titik/koma, contoh: 189000)
}}"""

    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = req.post(gemini_url, json=payload, timeout=15)
        r.raise_for_status()

        raw = r.json()['candidates'][0]['content']['parts'][0]['text']
        # Bersihkan markdown code block kalau ada
        clean = re.sub(r'```(?:json)?|```', '', raw).strip()
        result = json.loads(clean)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({'error': 'AI mengembalikan format tidak valid, coba lagi.'}), 500
    except Exception as e:
        return jsonify({'error': f'Gagal generate: {str(e)}'}), 500


# ─── SCRAPE TOKOPEDIA URL ─────────────────────────────────────────────────────
@app.route('/api/scrape-url', methods=['POST'])
@login_required
def scrape_url():
    url = request.json.get('url', '').strip()
    if not url or 'tokopedia.com' not in url:
        return jsonify({'error': 'Masukkan URL produk Tokopedia yang valid.'}), 400

    headers_scrape = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
    }

    try:
        r = req.get(url, headers=headers_scrape, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        result = {}

        # Nama produk
        name_tag = (soup.find('h1') or
                    soup.find('meta', {'property': 'og:title'}) or
                    soup.find('title'))
        if name_tag:
            result['name'] = (name_tag.get('content') or name_tag.get_text()).strip()[:120]

        # Gambar produk
        img_tag = soup.find('meta', {'property': 'og:image'})
        if img_tag:
            result['image_url'] = img_tag.get('content', '')

        # Deskripsi
        desc_tag = soup.find('meta', {'property': 'og:description'}) or \
                   soup.find('meta', {'name': 'description'})
        if desc_tag:
            result['description'] = (desc_tag.get('content') or '').strip()[:300]

        # Harga — cari pattern angka setelah "Rp"
        price_match = re.search(r'Rp[\s.]*(\d[\d.]+)', r.text)
        if price_match:
            raw_price = price_match.group(1).replace('.', '')
            result['price'] = int(raw_price)

        # Tebak kategori dari nama
        name_lower = result.get('name', '').lower()
        if any(k in name_lower for k in ['hoodie', 'zipper', 'sweater', 'crewneck']):
            result['category'] = 'Hoodie'
        elif any(k in name_lower for k in ['pants', 'celana', 'cargo', 'sweatpants', 'jogger']):
            result['category'] = 'Pants'
        else:
            result['category'] = 'T-Shirt'

        if not result.get('name'):
            return jsonify({'error': 'Tidak bisa membaca data dari halaman ini. Coba URL lain.'}), 422

        return jsonify(result)
    except req.exceptions.Timeout:
        return jsonify({'error': 'Timeout. Halaman terlalu lama merespons.'}), 504
    except Exception as e:
        return jsonify({'error': f'Gagal scrape: {str(e)}'}), 500


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
