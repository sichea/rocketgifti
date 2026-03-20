# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# 1) Telegram
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# 관리자/슈퍼관리자 텔레그램 numeric id (쉼표로 여러 명 가능)
def _parse_ids(raw: str) -> set:
    ids = set()
    for s in raw.split(","):
        s = s.strip()
        if s.isdigit():
            ids.add(int(s))
    return ids

ADMIN_TELEGRAM_IDS = _parse_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))
SUPER_ADMIN_TELEGRAM_IDS = _parse_ids(os.getenv("SUPER_ADMIN_TELEGRAM_IDS", ""))

# =========================
# 2) Giftishow Biz API
# =========================
GIFTISHOW_API_BASE = os.getenv("GIFTISHOW_API_BASE", "https://bizapi.giftishow.com/bizApi")
GIFTISHOW_CUSTOM_AUTH_CODE = os.getenv("GIFTISHOW_CUSTOM_AUTH_CODE", "")
GIFTISHOW_CUSTOM_AUTH_TOKEN = os.getenv("GIFTISHOW_CUSTOM_AUTH_TOKEN", "")
GIFTISHOW_USER_ID = os.getenv("GIFTISHOW_USER_ID", "")
GIFTISHOW_CALLBACK_NO = os.getenv("GIFTISHOW_CALLBACK_NO", "")
GIFTISHOW_DEV_YN = os.getenv("GIFTISHOW_DEV_YN", "N")

# =========================
# 3) Payment 안내 (입금형)
# =========================
BANK_INFO = os.getenv("BANK_INFO", "국민은행 000-0000-0000 / 예금주: 홍길동")
PAYMENT_DEADLINE_MINUTES = int(os.getenv("PAYMENT_DEADLINE_MINUTES", "120"))

# =========================
# 4) Supabase DB
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")