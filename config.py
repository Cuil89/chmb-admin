import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ubisgngdfdrhdnclfnln.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_4Hz3bB3u3Kw1kkzboMDhmA_OKL6shMi")

# Admin credentials (ganti sesuai keinginan)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "chmb2026")

SECRET_KEY = os.getenv("SECRET_KEY", "chmb-secret-flask-key-2026")
