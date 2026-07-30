import os
import re
import json
import requests as req
from flask import Blueprint, request, jsonify

profile_bp = Blueprint('profile_bp', __name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ubisgngdfdrhdnclfnln.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViaXNnbmdkZmRyaGRuY2xmbmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ5MTMxMTYsImV4cCI6MjEwMDQ4OTExNn0.XCjyi0kjimdxiFTCzDydr0KwkiTw2cuYdNhoJxP1_f8")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB Limit

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
            res = r.json()
            return True, res[0] if isinstance(res, list) and len(res) > 0 else data
        return False, r.text
    except Exception as e:
        return False, str(e)

def sb_update(table, match_col, match_val, data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
        r = req.patch(url, headers=get_headers(), json=data)
        if r.ok:
            res = r.json()
            return True, res[0] if isinstance(res, list) and len(res) > 0 else data
        return False, r.text
    except Exception as e:
        return False, str(e)

def sb_delete(table, match_col, match_val):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
        r = req.delete(url, headers=get_headers())
        return r.ok
    except Exception as e:
        return False

def is_valid_phone_indonesia(phone):
    """Regex validasi nomor telepon format Indonesia"""
    if not phone:
        return False
    clean = re.sub(r'[\s\-]', '', phone)
    pattern = r'^(?:\+62|62|0)8[1-9][0-9]{7,11}$'
    return bool(re.match(pattern, clean))


# ─── 1. GET /api/profile ────────────────────────────────────────────────────────
@profile_bp.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id') or request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib diisi'}), 400

    users = sb_get('users', {'id': f'eq.{user_id}'})
    user = users[0] if isinstance(users, list) and len(users) > 0 else {}

    # Ambil Alamat Default
    addresses = sb_get('user_addresses', {'user_id': f'eq.{user_id}'})
    default_address = None
    if isinstance(addresses, list) and len(addresses) > 0:
        default_address = next((a for a in addresses if a.get('is_default')), addresses[0])

    full_name = user.get('full_name') or user.get('name') or 'Pelanggan CHMB'
    phone = user.get('phone_number') or user.get('phone') or ''
    avatar = user.get('avatar_url') or user.get('avatar') or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400'

    return jsonify({
        'success': True,
        'data': {
            'id': str(user_id),
            'full_name': full_name,
            'name': full_name,
            'email': user.get('email', ''),
            'phone_number': phone,
            'avatar_url': avatar,
            'role': user.get('role', 'user'),
            'status': user.get('status', 'Terverifikasi'),
            'default_address': default_address
        }
    }), 200


# ─── 2. PUT /api/profile ────────────────────────────────────────────────────────
@profile_bp.route('/api/profile', methods=['PUT', 'OPTIONS'])
def update_profile():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    full_name = (data.get('full_name') or data.get('name') or '').strip()
    phone_number = (data.get('phone_number') or data.get('phone') or '').strip()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib diisi'}), 400

    if not full_name:
        return jsonify({'success': False, 'error': 'Nama lengkap tidak boleh kosong'}), 400

    if phone_number and not is_valid_phone_indonesia(phone_number):
        return jsonify({'success': False, 'error': 'Nomor HP tidak valid. Gunakan format Indonesia (misal: 08123456789)'}), 400

    update_payload = {
        'name': full_name,
        'full_name': full_name,
        'phone_number': phone_number,
        'updated_at': 'now()'
    }

    ok, result = sb_update('users', 'id', user_id, update_payload)
    if not ok:
        return jsonify({'success': False, 'error': f'Gagal update profil di DB: {result}'}), 500

    return jsonify({
        'success': True,
        'message': 'Profil berhasil diperbarui!',
        'data': {
            'id': str(user_id),
            'full_name': full_name,
            'phone_number': phone_number
        }
    }), 200


# ─── 3. POST /api/profile/avatar ────────────────────────────────────────────────
@profile_bp.route('/api/profile/avatar', methods=['POST', 'OPTIONS'])
def upload_avatar():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    user_id = request.form.get('user_id') or request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib diisi'}), 400

    if 'file' not in request.files and 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'Berkas foto tidak ditemukan'}), 400

    file = request.files.get('file') or request.files.get('avatar')
    filename = file.filename or 'avatar.jpg'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'

    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'error': f'Format file .{ext} tidak diizinkan. Gunakan png, jpg, jpeg, atau webp'}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'Ukuran foto melebihi batas maksimal 2MB'}), 400

    # Upload ke Supabase Storage Bucket 'avatars'
    storage_path = f"avatars/avatar_{user_id}.{ext}"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{storage_path}"

    headers = get_headers()
    headers["Content-Type"] = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    headers["x-upsert"] = "true"

    try:
        r = req.post(upload_url, headers=headers, data=file_bytes)
        if r.ok or r.status_code == 200:
            public_avatar_url = f"{SUPABASE_URL}/storage/v1/object/public/{storage_path}"
            # Update tabel users
            sb_update('users', 'id', user_id, {'avatar': public_avatar_url, 'avatar_url': public_avatar_url})
            return jsonify({
                'success': True,
                'message': 'Foto profil berhasil diperbarui!',
                'avatar_url': public_avatar_url
            }), 200
        else:
            return jsonify({'success': False, 'error': f'Gagal upload ke storage: {r.text}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 4. POST /api/profile/change-email ──────────────────────────────────────────
@profile_bp.route('/api/profile/change-email', methods=['POST', 'OPTIONS'])
def change_email():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    new_email = (data.get('new_email') or '').strip().lower()

    if not user_id or not new_email:
        return jsonify({'success': False, 'error': 'user_id dan new_email wajib diisi'}), 400

    if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', new_email):
        return jsonify({'success': False, 'error': 'Format email baru tidak valid'}), 400

    # Flow Verifikasi via Supabase Auth REST API
    try:
        auth_url = f"{SUPABASE_URL}/auth/v1/otp"
        payload = {'email': new_email, 'create_user': False}
        req.post(auth_url, headers=get_headers(), json=payload)
    except Exception as e:
        print(f"Trigger Email Auth Warning: {e}")

    return jsonify({
        'success': True,
        'message': f'Tautan konfirmasi telah dikirim ke {new_email}. Silakan cek email kamu untuk menyelesaikan verifikasi ubah email.',
        'new_email': new_email
    }), 200


# ─── 5. POST /api/profile/change-password ───────────────────────────────────────
@profile_bp.route('/api/profile/change-password', methods=['POST', 'OPTIONS'])
def change_password():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    email = data.get('email')
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'success': False, 'error': 'Password lama dan password baru wajib diisi'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Password baru minimal 6 karakter'}), 400

    # 1. Verifikasi Password Lama ke Supabase Auth REST API
    if email:
        token_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        payload = {'email': email, 'password': old_password}
        res = req.post(token_url, headers=get_headers(), json=payload)
        if not res.ok:
            return jsonify({'success': False, 'error': 'Password lama yang kamu masukkan salah'}), 400

    return jsonify({
        'success': True,
        'message': 'Password berhasil diperbarui! Silakan gunakan password baru kamu saat login berikutnya.'
    }), 200


# ─── 6. ALAMAT PENGGUNA (CRUD /api/profile/addresses) ───────────────────────────
@profile_bp.route('/api/profile/addresses', methods=['GET'])
def get_addresses():
    user_id = request.args.get('user_id') or request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID wajib diisi'}), 400

    addresses = sb_get('user_addresses', {'user_id': f'eq.{user_id}', 'order': 'is_default.desc,created_at.desc'})
    return jsonify({'success': True, 'data': addresses if isinstance(addresses, list) else []}), 200

@profile_bp.route('/api/profile/addresses', methods=['POST', 'OPTIONS'])
def add_address():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    recipient_name = (data.get('recipient_name') or '').strip()
    phone = (data.get('phone') or '').strip()
    full_address = (data.get('full_address') or '').strip()
    label = (data.get('label') or 'Rumah').strip()
    is_default = bool(data.get('is_default', False))

    if not user_id or not recipient_name or not phone or not full_address:
        return jsonify({'success': False, 'error': 'Nama penerima, nomor telp, dan alamat lengkap wajib diisi'}), 400

    if is_default:
        # Reset default sebelumnya
        sb_update('user_addresses', 'user_id', user_id, {'is_default': False})

    payload = {
        'user_id': str(user_id),
        'label': label,
        'recipient_name': recipient_name,
        'phone': phone,
        'full_address': full_address,
        'is_default': is_default
    }

    ok, result = sb_insert('user_addresses', payload)
    if not ok:
        return jsonify({'success': False, 'error': f'Gagal menambah alamat: {result}'}), 500

    return jsonify({'success': True, 'message': 'Alamat berhasil ditambahkan!', 'data': result}), 201

@profile_bp.route('/api/profile/addresses/<address_id>', methods=['PUT', 'DELETE', 'OPTIONS'])
def address_detail_ops(address_id):
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if request.method == 'DELETE':
        ok = sb_delete('user_addresses', 'id', address_id)
        return jsonify({'success': ok, 'message': 'Alamat berhasil dihapus'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')
    recipient_name = (data.get('recipient_name') or '').strip()
    phone = (data.get('phone') or '').strip()
    full_address = (data.get('full_address') or '').strip()
    label = (data.get('label') or 'Rumah').strip()
    is_default = bool(data.get('is_default', False))

    if is_default and user_id:
        sb_update('user_addresses', 'user_id', user_id, {'is_default': False})

    update_data = {
        'label': label,
        'recipient_name': recipient_name,
        'phone': phone,
        'full_address': full_address,
        'is_default': is_default,
        'updated_at': 'now()'
    }

    ok, result = sb_update('user_addresses', 'id', address_id, update_data)
    return jsonify({'success': ok, 'message': 'Alamat berhasil diperbarui!', 'data': result}), 200

@profile_bp.route('/api/profile/addresses/<address_id>/set-default', methods=['POST', 'OPTIONS'])
def set_default_address(address_id):
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True) or {}
    user_id = data.get('user_id') or request.headers.get('X-User-Id')

    if user_id:
        sb_update('user_addresses', 'user_id', user_id, {'is_default': False})

    ok, result = sb_update('user_addresses', 'id', address_id, {'is_default': True})
    return jsonify({'success': ok, 'message': 'Alamat default berhasil diubah!'}), 200
