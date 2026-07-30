import os
import json
import requests as req
from flask import Blueprint, request, jsonify

reviews_bp = Blueprint('reviews_bp', __name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ubisgngdfdrhdnclfnln.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViaXNnbmdkZmRyaGRuY2xmbmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ5MTMxMTYsImV4cCI6MjEwMDQ4OTExNn0.XCjyi0kjimdxiFTCzDydr0KwkiTw2cuYdNhoJxP1_f8")

def get_headers():
    key = os.environ.get("SUPABASE_KEY", SUPABASE_KEY)
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def sb_get(table, params=None):
    try:
        r = req.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=get_headers(), params=params)
        if r.ok:
            return r.json()
    except Exception as e:
        print(f"❌ sb_get({table}) error: {e}")
    return []

def sb_insert(table, data):
    try:
        r = req.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=get_headers(), json=data)
        if r.ok:
            res_json = r.json()
            return True, res_json[0] if isinstance(res_json, list) and len(res_json) > 0 else data
        return False, r.text
    except Exception as e:
        return False, str(e)

def _anonymize_name(name_str):
    """Format nama menjadi inisial ramah privasi (misal: 'Budi Santoso' -> 'Budi S.')"""
    if not name_str:
        return "Pelanggan CHMB"
    parts = name_str.strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."

# ─── 1. POST /api/products/<product_id>/reviews ─────────────────────────────────
@reviews_bp.route('/api/products/<product_id>/reviews', methods=['POST', 'OPTIONS'])
def create_review(product_id):
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    user_name = data.get('user_name', 'Pelanggan CHMB')
    order_id = data.get('order_id') or data.get('transaction_id')
    rating = data.get('rating')
    comment = (data.get('comment') or '').strip()

    # Validasi Dasar Input
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib diisi / User harus login'}), 401

    if not order_id:
        return jsonify({'success': False, 'error': 'Order ID wajib disertakan untuk verifikasi pembelian'}), 400

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Rating harus berupa angka antara 1 sampai 5'}), 400

    # 1. Validasi Keberadaan Transaksi di Database / Memory
    orders = sb_get('transactions', {'id': f'eq.{order_id}'})
    if not orders:
        # Fallback query by order_ref / id text
        orders = sb_get('transactions', {'order_ref': f'eq.{order_id}'})

    if not orders:
        return jsonify({'success': False, 'error': 'Pesanan tidak ditemukan'}), 404

    target_order = orders[0]

    # Validasi Kepemilikan Pesanan
    tx_user_id = str(target_order.get('user_id', ''))
    if tx_user_id and tx_user_id != str(user_id):
        return jsonify({'success': False, 'error': 'Pesanan ini bukan milik akun kamu'}), 403

    # Validasi Status Pesanan (Harus Selesai / Completed / Delivered)
    tx_status = str(target_order.get('status', '')).lower()
    valid_statuses = ['selesai', 'completed', 'delivered']
    if not any(vs in tx_status for vs in valid_statuses):
        return jsonify({'success': False, 'error': 'Ulasan hanya dapat diberikan pada pesanan berstatus Selesai'}), 400

    # Validasi Produk ada dalam Pesanan
    items = target_order.get('items') or []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []

    product_found = False
    if isinstance(items, list):
        for item in items:
            pid = str(item.get('product_id') or item.get('id') or '')
            if pid == str(product_id):
                product_found = True
                break

    # Catatan: Jika items kosong/format lama, izinkan demi fleksibilitas data existing
    if items and not product_found:
        return jsonify({'success': False, 'error': 'Produk ini tidak terdapat dalam pesanan tersebut'}), 400

    # 2. Cek apakah sudah pernah memberikan review untuk order_id + product_id ini
    existing_reviews = sb_get('reviews', {
        'user_id': f'eq.{user_id}',
        'product_id': f'eq.{product_id}',
        'order_id': f'eq.{order_id}'
    })

    if existing_reviews:
        return jsonify({'success': False, 'error': 'Kamu sudah pernah memberikan ulasan untuk produk di pesanan ini'}), 409

    # 3. Simpan Review Baru ke Supabase
    review_payload = {
        'product_id': str(product_id),
        'user_id': str(user_id),
        'order_id': str(order_id),
        'rating': rating,
        'comment': comment,
    }

    ok, result = sb_insert('reviews', review_payload)
    if not ok:
        return jsonify({'success': False, 'error': f'Gagal menyimpan ulasan ke DB: {result}'}), 500

    # 4. Ambil Summary Rating Terbaru untuk Response
    all_p_reviews = sb_get('reviews', {'product_id': f'eq.{product_id}'})
    total_rev = len(all_p_reviews)
    avg_rat = round(sum(r.get('rating', 5) for r in all_p_reviews) / total_rev, 1) if total_rev > 0 else 0.0

    return jsonify({
        'success': True,
        'message': 'Ulasan berhasil disimpan! Terima kasih.',
        'data': {
            'id': result.get('id') if isinstance(result, dict) else '',
            'product_id': str(product_id),
            'user_name': _anonymize_name(user_name),
            'rating': rating,
            'comment': comment,
            'created_at': result.get('created_at') if isinstance(result, dict) else ''
        },
        'summary': {
            'avg_rating': avg_rat,
            'review_count': total_rev
        }
    }), 201


# ─── 2. GET /api/products/<product_id>/reviews ──────────────────────────────────
@reviews_bp.route('/api/products/<product_id>/reviews', methods=['GET'])
def get_reviews(product_id):
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    page = max(1, page)
    limit = max(1, limit)

    all_reviews = sb_get('reviews', {
        'product_id': f'eq.{product_id}',
        'order': 'created_at.desc'
    })

    if not isinstance(all_reviews, list):
        all_reviews = []

    # Ambil list users untuk mapping nama (JANGAN expose email)
    users_list = sb_get('users', {'select': 'id, name'})
    user_map = {}
    if isinstance(users_list, list):
        for u in users_list:
            user_map[str(u.get('id'))] = u.get('name', 'Pelanggan CHMB')

    distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    formatted_reviews = []

    for r in all_reviews:
        r_rat = int(r.get('rating', 5))
        if 1 <= r_rat <= 5:
            distribution[r_rat] += 1

        uid = str(r.get('user_id', ''))
        raw_name = user_map.get(uid) or r.get('user_name') or 'Pelanggan CHMB'
        anon_name = _anonymize_name(raw_name)

        formatted_reviews.append({
            'id': str(r.get('id', '')),
            'rating': r_rat,
            'comment': r.get('comment', ''),
            'user_name': anon_name,
            'created_at': r.get('created_at', '')
        })

    total_count = len(formatted_reviews)
    avg_rating = round(sum(r['rating'] for r in formatted_reviews) / total_count, 1) if total_count > 0 else 0.0

    # Apply Pagination Slicing
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_data = formatted_reviews[start_idx:end_idx]

    return jsonify({
        'success': True,
        'data': paginated_data,
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total_count
        },
        'summary': {
            'avg_rating': avg_rating,
            'review_count': total_count,
            'distribution': distribution
        }
    }), 200


# ─── 3. GET /api/products/<product_id>/reviews/eligibility ─────────────────────
@reviews_bp.route('/api/products/<product_id>/reviews/eligibility', methods=['GET'])
def check_eligibility(product_id):
    user_id = request.args.get('user_id') or request.headers.get('X-User-Id')

    if not user_id:
        return jsonify({
            'success': True,
            'eligible': False,
            'reason': 'User belum login'
        }), 200

    # Ambil semua transaksi user berstatus Selesai
    user_orders = sb_get('transactions', {
        'user_id': f'eq.{user_id}',
        'order': 'created_at.desc'
    })

    eligible_orders = []

    if isinstance(user_orders, list):
        for tx in user_orders:
            tx_status = str(tx.get('status', '')).lower()
            if not any(vs in tx_status for vs in ['selesai', 'completed', 'delivered']):
                continue

            order_id = str(tx.get('id') or tx.get('order_ref') or '')
            if not order_id:
                continue

            # Cek apakah produk ini ada dalam pesanan ini
            items = tx.get('items') or []
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []

            has_product = False
            if isinstance(items, list):
                for item in items:
                    pid = str(item.get('product_id') or item.get('id') or '')
                    if pid == str(product_id):
                        has_product = True
                        break
            else:
                has_product = True

            if not has_product:
                continue

            # Cek apakah order ini sudah pernah diulas
            existing = sb_get('reviews', {
                'user_id': f'eq.{user_id}',
                'product_id': f'eq.{product_id}',
                'order_id': f'eq.{order_id}'
            })

            if not existing:
                eligible_orders.append({
                    'order_id': order_id,
                    'created_at': tx.get('created_at')
                })

    is_eligible = len(eligible_orders) > 0

    return jsonify({
        'success': True,
        'eligible': is_eligible,
        'eligible_orders': eligible_orders,
        'reason': 'User berhak memberikan ulasan' if is_eligible else 'Belum ada pesanan selesai yang belum diulas'
    }), 200


# ─── 4. WISHLIST API ENDPOINTS (ISOLASI USER RIGID) ─────────────────────────────
IN_MEMORY_WISHLISTS = []

@reviews_bp.route('/api/wishlist', methods=['GET'])
def get_wishlist():
    user_id = request.args.get('user_id') or request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib disertakan'}), 400

    # 1. Fetch from Supabase DB
    db_items = sb_get('wishlists', {'user_id': f'eq.{user_id}'})
    if not isinstance(db_items, list):
        db_items = []

    # Merge with memory fallbacks
    combined = list(db_items)
    db_pids = {str(w.get('product_id')) for w in db_items}

    for mem in IN_MEMORY_WISHLISTS:
        if str(mem.get('user_id')) == str(user_id) and str(mem.get('product_id')) not in db_pids:
            combined.append(mem)

    product_ids = [str(w.get('product_id')) for w in combined if w.get('product_id')]

    return jsonify({
        'success': True,
        'user_id': str(user_id),
        'count': len(product_ids),
        'product_ids': product_ids,
        'data': combined
    }), 200

@reviews_bp.route('/api/wishlist/toggle', methods=['POST', 'OPTIONS'])
def toggle_wishlist():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    product_id = data.get('product_id')

    if not user_id or not product_id:
        return jsonify({'success': False, 'error': 'user_id dan product_id wajib diisi'}), 400

    user_id = str(user_id)
    product_id = str(product_id)

    # Cek apakah sudah ada di Supabase DB
    existing = sb_get('wishlists', {'user_id': f'eq.{user_id}', 'product_id': f'eq.{product_id}'})

    global IN_MEMORY_WISHLISTS

    if existing and len(existing) > 0:
        # Hapus dari Supabase DB
        req.delete(f"{SUPABASE_URL}/rest/v1/wishlists?user_id=eq.{user_id}&product_id=eq.{product_id}", headers=get_headers())
        IN_MEMORY_WISHLISTS = [w for w in IN_MEMORY_WISHLISTS if not (str(w.get('user_id')) == user_id and str(w.get('product_id')) == product_id)]
        is_wishlisted = False
        msg = 'Produk dihapus dari Wishlist'
    else:
        # Simpan ke Supabase DB
        payload = {'user_id': user_id, 'product_id': product_id}
        sb_insert('wishlists', payload)
        if not any(str(w.get('user_id')) == user_id and str(w.get('product_id')) == product_id for w in IN_MEMORY_WISHLISTS):
            IN_MEMORY_WISHLISTS.append(payload)
        is_wishlisted = True
        msg = 'Produk berhasil disimpan ke Wishlist ❤️'

    return jsonify({
        'success': True,
        'message': msg,
        'user_id': user_id,
        'product_id': product_id,
        'is_wishlisted': is_wishlisted
    }), 200

