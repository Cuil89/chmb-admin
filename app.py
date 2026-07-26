from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY
from functools import wraps

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Inisialisasi Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        products = supabase.table('products').select('*').execute()
        transactions = supabase.table('transactions').select('*').order('created_at', desc=True).execute()

        total_products = len(products.data)
        total_orders = len(transactions.data)
        total_revenue = sum(t.get('total_harga', 0) for t in transactions.data)
        pending_orders = [t for t in transactions.data if t.get('status') == 'Pending']
        recent_orders = transactions.data[:5]
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
    try:
        res = supabase.table('products').select('*').order('name').execute()
        product_list = res.data
    except Exception as e:
        flash(f'Error: {e}', 'danger')
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
        try:
            supabase.table('products').insert(data).execute()
            flash(f'Produk "{data["name"]}" berhasil ditambahkan!', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            flash(f'Gagal menambahkan produk: {e}', 'danger')

    return render_template('product_form.html', product=None, action='Tambah')

@app.route('/products/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    try:
        res = supabase.table('products').select('*').eq('id', product_id).single().execute()
        product = res.data
    except Exception as e:
        flash(f'Produk tidak ditemukan: {e}', 'danger')
        return redirect(url_for('products'))

    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'price': float(request.form.get('price', 0)),
            'image_url': request.form.get('image_url'),
            'category': request.form.get('category'),
        }
        try:
            supabase.table('products').update(data).eq('id', product_id).execute()
            flash(f'Produk "{data["name"]}" berhasil diupdate!', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            flash(f'Gagal mengupdate produk: {e}', 'danger')

    return render_template('product_form.html', product=product, action='Edit')

@app.route('/products/delete/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    try:
        supabase.table('products').delete().eq('id', product_id).execute()
        flash('Produk berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus produk: {e}', 'danger')
    return redirect(url_for('products'))

# ─── PESANAN ──────────────────────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    try:
        res = supabase.table('transactions').select('*').order('created_at', desc=True).execute()
        order_list = res.data
    except Exception as e:
        flash(f'Error: {e}', 'danger')
        order_list = []
    return render_template('orders.html', orders=order_list)

@app.route('/orders/update-status/<order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    try:
        supabase.table('transactions').update({'status': new_status}).eq('id', order_id).execute()
        flash(f'Status pesanan berhasil diubah menjadi "{new_status}"!', 'success')
    except Exception as e:
        flash(f'Gagal update status: {e}', 'danger')
    return redirect(url_for('orders'))

# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
