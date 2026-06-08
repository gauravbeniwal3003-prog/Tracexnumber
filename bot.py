"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 6.0.0 - Refactored with Vehicle Removal & Updated Pricing
"""

import os
import sys
import time
import re
import uuid
import hmac
import hashlib
import json
import threading
import signal
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

# Environment variables - MUST be set before importing dependencies
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "TEST")
RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "https://your-app.onrender.com")

# Friendly dependency check
def _require_package(import_name, pip_name=None):
    try:
        return __import__(import_name)
    except ImportError:
        name = pip_name or import_name
        print(f"❌ Missing dependency: {name}")
        print(f"Install with: pip install {name}")
        raise

telebot = _require_package("telebot", "pyTelegramBotAPI")
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
requests = _require_package("requests", "requests")
from flask import Flask, request, jsonify

# ==================== CONFIGURATION ====================
ADMIN_ID = int(os.getenv("ADMIN_ID", "7850023357"))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1003743686626"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@gaurav_beniwal_0001")
BOT_VERSION = "6.0.0"

# Lookup API Configuration
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/api/v1/lookup.php").strip()
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "TVB_SGL_053B3AA6").strip()
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number").strip()

# Telegram Lookup API
TELEGRAM_LOOKUP_API_URL = "https://exploitsindia.site/lookup/telegram.php"

# Updated pricing
NUMBER_LOOKUP_COST = 6
TELEGRAM_LOOKUP_COST = 11
MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900

# Updated protection pricing
PROTECT_NUMBER_PRICE = 99
PROTECT_TELEGRAM_PRICE = 99

COOLDOWN_SECONDS = 3
AUTO_DELETE_SECONDS = 120
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/Gaurav_beni_0001")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Gaurav_beni_0001")
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")

# Generic API error message
GENERIC_API_ERROR_MESSAGE = "❌ *API Error*\n\n💎 Credits NOT deducted"

# Updated plan configuration - NEW PRICING
PLAN_CONFIG = {
    "c10": {"amount": 20, "credits": 10, "unlimited_minutes": 0, "payment_for": "credits", "label": "10 Credits"},
    "c50": {"amount": 70, "credits": 50, "unlimited_minutes": 0, "payment_for": "credits", "label": "50 Credits"},
    "c100": {"amount": 100, "credits": 100, "unlimited_minutes": 0, "payment_for": "credits", "label": "100 Credits"},
    "u1w": {"amount": 200, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited"},  # UPDATED: 358 → 200
    "u1m": {"amount": 500, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited"},  # UPDATED: 898 → 500
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Protection"},
    "bot_booking": {"amount": 399, "credits": 0, "unlimited_minutes": 0, "payment_for": "bot_booking", "label": "Custom Bot Booking"},
}

# Supabase Client
class _SupabaseResult:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count

class _SupabaseTableQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.method = "GET"
        self.payload = None
        self.params = {}
        self.headers = {}

    def select(self, columns="*", count=None):
        self.method = "GET"
        self.params["select"] = columns or "*"
        if count == "exact":
            self.headers["Prefer"] = "count=exact"
        return self

    def insert(self, payload):
        self.method = "POST"
        self.payload = payload
        self.headers["Prefer"] = "return=representation"
        return self

    def update(self, payload):
        self.method = "PATCH"
        self.payload = payload
        self.headers["Prefer"] = "return=representation"
        return self

    def eq(self, column, value):
        self.params[str(column)] = "eq." + str(value)
        return self

    def ilike(self, column, value):
        self.params[str(column)] = "ilike." + str(value)
        return self

    def limit(self, n):
        self.params["limit"] = str(int(n))
        return self

    def order(self, column, desc=False):
        direction = "desc" if desc else "asc"
        self.params["order"] = f"{column}.{direction}"
        return self

    def execute(self):
        if not self.client.url or not self.client.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        url = f"{self.client.url}/rest/v1/{self.table}"
        headers = dict(self.client.headers)
        headers.update(self.headers)
        response = requests.request(
            self.method, url, params=self.params,
            json=self.payload, headers=headers, timeout=30
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase error {response.status_code}: {response.text[:500]}")
        try:
            data = response.json() if response.text else []
        except Exception:
            data = []
        count = None
        content_range = response.headers.get("content-range") or response.headers.get("Content-Range")
        if content_range and "/" in content_range:
            try:
                total = content_range.split("/")[-1]
                count = None if total == "*" else int(total)
            except Exception:
                pass
        if count is None and isinstance(data, list):
            count = len(data)
        return _SupabaseResult(data=data, count=count)

class _SupabaseLiteClient:
    def __init__(self, url, key):
        self.url = str(url or "").rstrip("/")
        self.key = str(key or "")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def table(self, name):
        return _SupabaseTableQuery(self, name)

def create_client(url, key):
    return _SupabaseLiteClient(url, key)

# Initialize bot
def validate_startup_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY):
        missing.append("SUPABASE_KEY")
    if missing:
        print("❌ Missing: " + ", ".join(missing))
        sys.exit(1)

validate_startup_config()
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True)

SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# State management
user_states = {}
user_cooldown = {}
temp_data = {}
payment_session_cooldown = {}
PAYMENT_SESSION_COOLDOWN_SECONDS = 60
active_number_sessions = set()
active_number_sessions_lock = threading.Lock()
active_telegram_sessions = set()
active_telegram_sessions_lock = threading.Lock()
proof_forwarded_txs = set()

# Daily stats
daily_search_stats = {}
daily_stats_lock = threading.Lock()
IST = timezone(timedelta(hours=5, minutes=30))

MAINTENANCE_MODE = False

# Flask app for webhooks
app = Flask(__name__)

# ==================== HELPER FUNCTIONS ====================

def show_api_error(chat_id, message_id, lookup_type="api"):
    """Show clean API error without deducting credits"""
    try:
        bot.edit_message_text(GENERIC_API_ERROR_MESSAGE, chat_id, message_id, parse_mode="Markdown")
    except Exception as e:
        print(f"API error display failed: {e}")

def safe_json_response(response):
    try:
        return response.json()
    except Exception:
        raise ValueError("Invalid API JSON response")

def has_valid_number_results(result):
    """Check if API result contains valid data"""
    if not isinstance(result, dict):
        return False
    api_results = result.get("results")
    if isinstance(api_results, dict):
        return any(isinstance(v, dict) for v in api_results.values())
    if isinstance(api_results, list):
        return any(isinstance(v, dict) for v in api_results)
    return any(str(k).lower().startswith("result") and isinstance(v, dict) for k, v in result.items()) or ("name" in result or "mobile" in result)

def call_unstable_json_api(params, lookup_type="number", max_retries=5, timeout=30):
    """Smart API caller with retry logic"""
    base_url = str(LOOKUP_API_URL or "").strip()
    clean_params = {str(k): str(v).strip() for k, v in (params or {}).items() if v is not None}

    headers_attempts = [
        {"User-Agent": "Mozilla/5.0 (Linux; Android) TraceXBot/6.0", "Accept": "application/json,text/plain,*/*", "Connection": "close"},
        {"User-Agent": "python-requests TraceXBot/6.0", "Accept": "application/json,text/plain,*/*", "Connection": "close"},
    ]

    last_error = "unknown"
    for attempt in range(1, max_retries + 1):
        headers = headers_attempts[(attempt - 1) % len(headers_attempts)]
        try:
            response = requests.get(base_url, params=clean_params, headers=headers, timeout=timeout)
            raw_preview = (response.text or "")[:500].replace("\n", " ")

            if response.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                last_error = f"http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue

            if response.status_code != 200:
                last_error = f"http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue

            if raw_preview.lstrip().lower().startswith("<!doctype") or "<html" in raw_preview.lower():
                last_error = "html_response"
                time.sleep(min(2 * attempt, 8))
                continue

            try:
                data = response.json()
            except Exception:
                last_error = "json_parse_failed"
                time.sleep(min(2 * attempt, 8))
                continue

            if not isinstance(data, dict):
                last_error = "invalid_json"
                time.sleep(min(2 * attempt, 8))
                continue

            return data, None

        except requests.exceptions.Timeout:
            last_error = "timeout"
            time.sleep(min(2 * attempt, 8))
        except requests.exceptions.ConnectionError:
            last_error = "connection_error"
            time.sleep(min(2 * attempt, 8))
        except Exception as e:
            last_error = f"exception_{e}"
            time.sleep(min(2 * attempt, 8))

    return None, last_error

def split_long_text(text, limit=TELEGRAM_SAFE_LIMIT):
    """Split long text for Telegram"""
    text = str(text or "")
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit and current:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current.rstrip())
    return chunks or [""]

def send_or_edit_long_message(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send or edit long message with splitting"""
    chunks = split_long_text(text)
    sent_messages = []
    for idx, chunk in enumerate(chunks):
        is_first = idx == 0
        is_last = idx == len(chunks) - 1
        markup = reply_markup if is_last else None
        try:
            if is_first:
                sent_messages.append(bot.edit_message_text(chunk, chat_id, message_id, reply_markup=markup, parse_mode=parse_mode))
            else:
                sent_messages.append(bot.send_message(chat_id, chunk, reply_markup=markup, parse_mode=parse_mode, disable_web_page_preview=True))
        except Exception:
            if is_first:
                sent_messages.append(bot.edit_message_text(chunk, chat_id, message_id, reply_markup=markup))
            else:
                sent_messages.append(bot.send_message(chat_id, chunk, reply_markup=markup, disable_web_page_preview=True))
    return sent_messages

def auto_delete_sent_messages(chat_id, sent_messages):
    time.sleep(AUTO_DELETE_SECONDS)
    for msg in sent_messages:
        try:
            bot.delete_message(chat_id, msg.message_id)
        except Exception:
            pass

def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    """Send alerts to admin channel with fallback"""
    try:
        bot.send_message(ADMIN_CHANNEL_ID, text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Admin alert failed: {e}")
        try:
            bot.send_message(ADMIN_ID, "⚠️ " + text[:500], reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except Exception:
            return False

def notify_admin_api_issue(lookup_type, query, error_reason):
    """Notify admin about API issues"""
    try:
        bot.send_message(ADMIN_ID, f"⚠️ *API Issue*\nType: `{lookup_type}`\nQuery: `{query}`\nReason: `{str(error_reason)[:200]}`\nNo credits deducted.", parse_mode="Markdown")
    except Exception:
        pass

def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 {WEBSITE_URL}\n👨‍💻 Admin: {ADMIN_USERNAME}"

# ==================== SUPABASE FUNCTIONS ====================

def get_user(telegram_user_id):
    try:
        response = supabase.table("telegram_users").select("*").eq("telegram_user_id", telegram_user_id).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            supabase.table("telegram_users").update({
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            return user
        else:
            new_user = {
                "telegram_user_id": telegram_user_id,
                "credits": 10,
                "total_searches": 0,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "is_banned": False
            }
            result = supabase.table("telegram_users").insert(new_user).execute()
            return result.data[0] if result.data else None
    except Exception as e:
        print(f"Get user error: {e}")
        return None

def normalize_indian_mobile(value):
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits if re.match(r"^[6-9]\d{9}$", digits) else None

def add_credits(telegram_user_id, amount):
    try:
        response = supabase.table("telegram_users").select("credits").eq("telegram_user_id", telegram_user_id).execute()
        if not response.data:
            new_user = {
                "telegram_user_id": telegram_user_id,
                "credits": 10 + int(amount or 0),
                "total_searches": 0,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "is_banned": False
            }
            result = supabase.table("telegram_users").insert(new_user).execute()
            return result.data[0].get('credits', 0) if result.data else 0
        else:
            current = response.data[0].get('credits', 0)
            new_total = current + amount
            supabase.table("telegram_users").update({
                "credits": new_total,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            return new_total
    except Exception as e:
        print(f"Add credits error: {e}")
        return 0

def deduct_credits(telegram_user_id, amount=1):
    try:
        amount = int(amount or 1)
        user = get_user(telegram_user_id)
        if not user:
            return False

        # Check unlimited plan
        unlimited_expiry = user.get('unlimited_expiry')
        if unlimited_expiry:
            try:
                if isinstance(unlimited_expiry, str):
                    expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
                else:
                    expiry_date = unlimited_expiry
                if expiry_date > datetime.now(timezone.utc):
                    return True
            except Exception:
                pass

        credits = int(user.get('credits', 0) or 0)
        if credits >= amount:
            supabase.table("telegram_users").update({
                "credits": credits - amount,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            return True
        return False
    except Exception as e:
        print(f"Deduct credits error: {e}")
        return False

def increment_total_searches(telegram_user_id):
    try:
        user = get_user(telegram_user_id)
        if user:
            new_total = user.get('total_searches', 0) + 1
            supabase.table("telegram_users").update({
                "total_searches": new_total,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            return True
    except Exception as e:
        print(f"Increment searches error: {e}")
    return False

def get_total_credits(telegram_user_id):
    try:
        user = get_user(telegram_user_id)
        return user.get('credits', 0) if user else 0
    except Exception:
        return 0

def get_active_unlimited(user):
    unlimited_expiry_raw = user.get('unlimited_expiry') if user else None
    if not unlimited_expiry_raw:
        return False, None
    try:
        expiry_date = datetime.fromisoformat(str(unlimited_expiry_raw).replace('Z', '+00:00'))
        if expiry_date > datetime.now(timezone.utc):
            return True, str(unlimited_expiry_raw)
    except Exception:
        pass
    return False, None

def is_number_protected(phone_number):
    try:
        response = supabase.table("protected_numbers").select("*").eq("phone_number", phone_number).execute()
        return len(response.data) > 0
    except Exception:
        return False

def add_protected_number(phone_number, telegram_user_id=None):
    try:
        supabase.table("protected_numbers").insert({
            "phone_number": phone_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception:
        return False

def is_telegram_protected(telegram_id):
    try:
        response = supabase.table("protected_telegrams").select("*").eq("telegram_id", str(telegram_id)).execute()
        return len(response.data) > 0
    except Exception:
        return False

def add_protected_telegram(telegram_id, telegram_user_id=None):
    try:
        supabase.table("protected_telegrams").insert({
            "telegram_id": str(telegram_id),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception:
        return False

def get_cached_result(phone_number):
    try:
        response = supabase.table("search_results").select("*").eq("mobile_number", phone_number).execute()
        if response.data and len(response.data) > 0:
            return response.data[0].get('raw_data')
        return None
    except Exception:
        return None

def save_cached_result(phone_number, raw_data):
    try:
        existing = supabase.table("search_results").select("mobile_number").eq("mobile_number", phone_number).limit(1).execute()
        if existing.data:
            supabase.table("search_results").update({"raw_data": raw_data}).eq("mobile_number", phone_number).execute()
        else:
            supabase.table("search_results").insert({
                "mobile_number": phone_number,
                "raw_data": raw_data,
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        return True
    except Exception:
        return False

def resolve_user_identifier(identifier):
    token = str(identifier or "").strip()
    if not token:
        return None, None
    if token.startswith("@"):
        token = token[1:]
    if token.isdigit():
        uid = int(token)
        return uid, get_user(uid)
    try:
        resp = supabase.table("telegram_users").select("*").eq("telegram_username", token).limit(1).execute()
        if not resp.data:
            resp = supabase.table("telegram_users").select("*").ilike("telegram_username", token).limit(1).execute()
        if resp.data:
            user = resp.data[0]
            return int(user.get("telegram_user_id")), user
    except Exception:
        pass
    return None, None

def activate_unlimited_plan_for_user(target_user, plan_id):
    plan = PLAN_CONFIG.get(plan_id)
    if not plan or plan.get("payment_for") != "unlimited":
        return False, "Invalid unlimited plan"
    minutes = int(plan.get("unlimited_minutes") or 0)
    now_dt = datetime.now(timezone.utc)
    user = get_user(int(target_user))
    start_from = now_dt
    current_expiry = user.get("unlimited_expiry") if user else None
    if current_expiry:
        try:
            expiry_dt = datetime.fromisoformat(str(current_expiry).replace("Z", "+00:00"))
            if expiry_dt > now_dt:
                start_from = expiry_dt
        except Exception:
            pass
    new_expiry = start_from + timedelta(minutes=minutes)
    supabase.table("telegram_users").update({
        "unlimited_expiry": new_expiry.isoformat(),
        "updated_at": now_dt.isoformat()
    }).eq("telegram_user_id", int(target_user)).execute()
    return True, new_expiry

def get_all_users():
    try:
        response = supabase.table("telegram_users").select("telegram_user_id").eq("is_banned", False).execute()
        return [row['telegram_user_id'] for row in response.data]
    except Exception:
        return []

def add_giveaway_credits(credits):
    try:
        users = get_all_users()
        success = 0
        for user_id in users:
            add_credits(user_id, credits)
            success += 1
        return success, 0
    except Exception:
        return 0, 0

def ban_user(telegram_user_id):
    try:
        supabase.table("telegram_users").update({
            "is_banned": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        return True
    except Exception:
        return False

def unban_user(telegram_user_id):
    try:
        supabase.table("telegram_users").update({
            "is_banned": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        return True
    except Exception:
        return False

def get_stats():
    try:
        users_resp = supabase.table("telegram_users").select("*", count="exact").execute()
        total_users = users_resp.count
        searches_resp = supabase.table("telegram_users").select("total_searches").execute()
        total_searches = sum(u.get('total_searches', 0) for u in searches_resp.data)
        credits_resp = supabase.table("telegram_users").select("credits").execute()
        total_credits = sum(u.get('credits', 0) for u in credits_resp.data)
        banned_resp = supabase.table("telegram_users").select("*", count="exact").eq("is_banned", True).execute()
        banned_users = banned_resp.count
        pending_resp = supabase.table("payment_claims").select("*", count="exact").eq("status", "pending").execute()
        pending_payments = pending_resp.count
        revenue_resp = supabase.table("payment_claims").select("amount").eq("status", "success").execute()
        total_revenue = sum(p.get('amount', 0) for p in revenue_resp.data)
        cache_resp = supabase.table("search_results").select("*", count="exact").execute()
        cache_size = cache_resp.count
        protected_resp = supabase.table("protected_numbers").select("*", count="exact").execute()
        protected_count = protected_resp.count
        return {
            'total_users': total_users, 'total_searches': total_searches, 'total_credits': total_credits,
            'banned_users': banned_users, 'pending_payments': pending_payments, 'total_revenue': total_revenue,
            'cache_size': cache_size, 'protected_count': protected_count
        }
    except Exception:
        return {'total_users': 0, 'total_searches': 0, 'total_credits': 0, 'banned_users': 0,
                'pending_payments': 0, 'total_revenue': 0, 'cache_size': 0, 'protected_count': 0}

def get_recent_transactions(limit=20):
    try:
        response = supabase.table("payment_claims").select("*").order("created_at", desc=True).limit(limit).execute()
        return response.data
    except Exception:
        return []

# ==================== PAYMENT FUNCTIONS ====================

def get_plan_config(plan_id):
    return PLAN_CONFIG.get(str(plan_id or "").strip())

def create_manual_payment_claim(plan_id, telegram_user_id, telegram_username, protected_number=None):
    try:
        plan = get_plan_config(plan_id)
        if not plan:
            return None
        tx_code = "TX" + uuid.uuid4().hex[:16].upper()
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "payment_id": tx_code, "cashfree_order_id": tx_code, "session_id": tx_code,
            "telegram_user_id": str(telegram_user_id), "telegram_username": str(telegram_username or "no_username"),
            "plan_id": plan_id, "amount": plan["amount"], "credits": plan["credits"],
            "payment_source": "manual_qr", "payment_for": plan["payment_for"],
            "protected_number": protected_number, "status": "pending",
            "created_at": now, "updated_at": now,
            "raw_response": {"mode": "manual_static_qr", "note": "Manual verification required"}
        }
        supabase.table("payment_claims").insert(payload).execute()
        return tx_code
    except Exception as e:
        print(f"Create manual claim error: {e}")
        return None

def fulfill_manual_claim(claim):
    try:
        telegram_user_id = claim.get("telegram_user_id")
        plan_id = claim.get("plan_id")
        plan = get_plan_config(plan_id)
        if not telegram_user_id or not plan:
            return False, "Invalid claim data"

        if plan["payment_for"] == "credits":
            credits = int(claim.get("credits") or plan.get("credits") or 0)
            if credits <= 0:
                return False, "No credits in this plan"
            new_total = add_credits(int(telegram_user_id), credits)
            return True, f"Added {credits} credits. New total: {new_total}"

        if plan["payment_for"] == "unlimited":
            minutes = int(plan.get("unlimited_minutes") or 0)
            if minutes <= 0:
                return False, "Invalid unlimited duration"
            user = get_user(int(telegram_user_id))
            now_dt = datetime.now(timezone.utc)
            start_from = now_dt
            current_expiry = user.get("unlimited_expiry") if user else None
            if current_expiry:
                try:
                    expiry_dt = datetime.fromisoformat(str(current_expiry).replace("Z", "+00:00"))
                    if expiry_dt > now_dt:
                        start_from = expiry_dt
                except Exception:
                    pass
            new_expiry = start_from + timedelta(minutes=minutes)
            supabase.table("telegram_users").update({
                "unlimited_expiry": new_expiry.isoformat(),
                "updated_at": now_dt.isoformat()
            }).eq("telegram_user_id", int(telegram_user_id)).execute()
            return True, f"Unlimited activated until {new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC"

        if plan["payment_for"] == "protect_number":
            number = claim.get("protected_number")
            if not number:
                return False, "Protected number missing"
            if not is_number_protected(number):
                add_protected_number(number, int(telegram_user_id))
            return True, f"Protected number {number}"

        if plan["payment_for"] == "protect_telegram":
            telegram_id = claim.get("protected_number")
            if not telegram_id:
                return False, "Telegram ID missing"
            if not is_telegram_protected(telegram_id):
                add_protected_telegram(telegram_id, int(telegram_user_id))
            return True, f"Protected Telegram ID {telegram_id}"

        if plan["payment_for"] == "bot_booking":
            return True, "Bot booking confirmed. Delivery: 24-48 hours."

        return False, "Unknown payment type"
    except Exception as e:
        print(f"Fulfill manual claim error: {e}")
        return False, str(e)

def manual_verify_payment(tx_code, admin_id=None):
    try:
        tx_code = str(tx_code or "").strip()
        claim_resp = None
        for field in ["session_id", "payment_id", "cashfree_order_id"]:
            try:
                claim_resp = supabase.table("payment_claims").select("*").eq(field, tx_code).limit(1).execute()
                if claim_resp.data:
                    break
            except Exception:
                continue
        if not claim_resp or not claim_resp.data:
            return False, "Transaction not found"
        claim = claim_resp.data[0]
        if str(claim.get("status") or "").lower() == "success":
            return False, "Already verified"
        ok, detail = fulfill_manual_claim(claim)
        if not ok:
            return False, detail
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("payment_claims").update({
            "status": "success", "updated_at": now,
            "raw_response": {"mode": "manual_static_qr", "verified_by": str(admin_id or ADMIN_ID), "verified_at": now, "detail": detail}
        }).eq("id", claim.get("id")).execute()
        telegram_user_id = int(claim.get("telegram_user_id"))
        try:
            bot.send_message(telegram_user_id, f"✅ *Payment Verified!*\n\n{detail}\n\n🧾 TX: `{tx_code}`\n\nUse /start", parse_mode="Markdown")
        except Exception:
            pass
        return True, detail
    except Exception as e:
        print(f"Manual verify error: {e}")
        return False, str(e)

def manual_reject_payment(tx_code, admin_id=None, reason="Payment not confirmed"):
    try:
        tx_code = str(tx_code or "").strip()
        claim_resp = None
        for field in ["session_id", "payment_id", "cashfree_order_id"]:
            try:
                claim_resp = supabase.table("payment_claims").select("*").eq(field, tx_code).limit(1).execute()
                if claim_resp.data:
                    break
            except Exception:
                continue
        if not claim_resp or not claim_resp.data:
            return False, "Transaction not found"
        claim = claim_resp.data[0]
        status = str(claim.get("status") or "").lower()
        if status == "success":
            return False, "Already verified"
        if status == "rejected":
            return False, "Already rejected"
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("payment_claims").update({
            "status": "rejected", "updated_at": now,
            "raw_response": {"mode": "manual_static_qr", "rejected_by": str(admin_id or ADMIN_ID), "rejected_at": now, "reason": reason}
        }).eq("id", claim.get("id")).execute()
        telegram_user_id = int(claim.get("telegram_user_id"))
        try:
            bot.send_message(telegram_user_id, f"❌ *Payment Rejected*\n\n🧾 TX: `{tx_code}`\nReason: `{reason}`\n\nContact admin: {ADMIN_USERNAME}", parse_mode="Markdown")
        except Exception:
            pass
        return True, "Payment rejected"
    except Exception as e:
        print(f"Manual reject error: {e}")
        return False, str(e)

def get_manual_claim_status(tx_code):
    try:
        tx_code = str(tx_code or "").strip()
        for field in ["session_id", "payment_id", "cashfree_order_id"]:
            try:
                resp = supabase.table("payment_claims").select("status").eq(field, tx_code).limit(1).execute()
                if resp.data:
                    return str(resp.data[0].get("status") or "").lower()
            except Exception:
                continue
        return None
    except Exception:
        return None

def payment_session_reminder_worker(chat_id, user_id, tx_code, plan_label):
    """3-minute timer with auto-cancel"""
    try:
        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            bot.send_message(chat_id, f"⏰ *Payment Reminder - 2 minutes left!*\n\n🧾 TX: `{tx_code}`\n⏱️ 2 minutes remaining.\n\nSend screenshot when done.", parse_mode="Markdown")
        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            bot.send_message(chat_id, f"⚠️ *LAST CALL - 1 minute left!*\n\n🧾 TX: `{tx_code}`\nOnly 1 minute remaining!", parse_mode="Markdown")
        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            manual_reject_payment(tx_code, ADMIN_ID, reason="Payment session expired - 3 minutes timeout")
            bot.send_message(chat_id, f"❌ *Payment Session Expired*\n\n🧾 TX: `{tx_code}`\nReason: 3 minutes timeout.\n\nCreate a new payment session.", reply_markup=credit_packs_markup(), parse_mode="Markdown")
    except Exception as e:
        print(f"Payment reminder error: {e}")

def send_manual_qr_payment(chat_id, user_id, username, plan_id, protected_number=None):
    plan = get_plan_config(plan_id)
    if not plan:
        bot.send_message(chat_id, "❌ Invalid plan selected.", reply_markup=main_menu_markup(user_id))
        return

    now_ts = time.time()
    last_ts = payment_session_cooldown.get(user_id, 0)
    if now_ts - last_ts < PAYMENT_SESSION_COOLDOWN_SECONDS:
        remaining = int(PAYMENT_SESSION_COOLDOWN_SECONDS - (now_ts - last_ts))
        bot.send_message(chat_id, f"⏳ Wait `{remaining}` seconds before another session.", parse_mode="Markdown")
        return
    payment_session_cooldown[user_id] = now_ts

    tx_code = create_manual_payment_claim(plan_id, user_id, username, protected_number)
    if not tx_code:
        bot.send_message(chat_id, f"❌ Payment error. Contact {ADMIN_USERNAME}")
        return

    extra = f"\n📱 Number: `{protected_number}`" if protected_number else ""
    caption = f"""💳 *Scan & Pay*
━━━━━━━━━━━━━━━━━━
💰 Amount: ₹{plan['amount']}
📦 Plan: `{plan['label']}`{extra}
🧾 TX: `{tx_code}`

⏰ *You have 3 minutes!*

Send screenshot after payment.

━━━━━━━━━━━━━━━━━━
📞 Admin: {ADMIN_USERNAME}"""

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 SEND SCREENSHOT", callback_data=f"submitproof_{tx_code}"))
    markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))

    qr_path = PAYMENT_QR_IMAGE
    if not os.path.isabs(qr_path):
        qr_path = os.path.join(os.getcwd(), qr_path)

    try:
        if os.path.exists(qr_path):
            with open(qr_path, "rb") as img:
                bot.send_photo(chat_id, img, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, caption + "\n⚠️ QR missing", reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")

    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )
    send_admin_alert(
        f"💳 *PAYMENT CREATED*\n👤 User: `{user_id}`\n📦 Plan: `{plan_id}`\n💰 ₹{plan['amount']}\n🧾 TX: `{tx_code}`\n/verify {tx_code}",
        reply_markup=admin_markup
    )
    threading.Thread(target=payment_session_reminder_worker, args=(chat_id, user_id, tx_code, plan.get("label", plan_id)), daemon=True).start()

# ==================== TELEGRAM LOOKUP ====================

def call_telegram_lookup_api(username):
    try:
        if not username.startswith('@'):
            username = '@' + username
        from urllib.parse import urlencode
        url = f"{TELEGRAM_LOOKUP_API_URL}?{urlencode({'username': username})}"
        headers = {"User-Agent": "Mozilla/5.0 TraceXBot/6.0", "Accept": "text/html,*/*", "Connection": "close"}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None, f"http_{response.status_code}"
        html_content = response.text
        result = {}
        tg_id_match = re.search(r'🆔 Telegram ID:\s*<code>(\d+)</code>', html_content)
        if tg_id_match:
            result['telegram_id'] = tg_id_match.group(1)
        phone_match = re.search(r'📱 Phone Number:\s*<code>(\d+)</code>', html_content)
        if phone_match:
            result['phone_number'] = phone_match.group(1)
        username_match = re.search(r'👥 Username:\s*@([a-zA-Z0-9_]+)', html_content)
        if username_match:
            result['username'] = '@' + username_match.group(1)
        if result.get('telegram_id') or result.get('phone_number'):
            return result, None
        no_data_markers = ["no data found", "not found", "no records", "no result"]
        if any(m in html_content.lower() for m in no_data_markers):
            return {"error": "no_result"}, None
        return {"error": "no_result"}, None
    except Exception as e:
        return None, f"exception_{e}"

def format_telegram_lookup_result(result, username, user_id, unlimited_active=False, unlimited_expiry=None):
    output = f"""🔍 *TELEGRAM LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

Lookup for: `{username}`

👥 Username: `{result.get('username', username)}`
🆔 Telegram ID: `{result.get('telegram_id', 'N/A')}`
📱 Phone: `{result.get('phone_number', 'N/A')}`

━━━━━━━━━━━━━━━━━━"""
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    if unlimited_active:
        output += f"""
🚀 *UNLIMITED ACTIVE*
Expires: `{unlimited_expiry[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""
💎 Credits Used: `{TELEGRAM_LOOKUP_COST}`
💎 Credits Left: `{updated_total}`
🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`"""
    output += f"\n\n⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec{footer()}"
    return output

def process_telegram_lookup(message):
    user_id = message.from_user.id
    username_input = str(message.text or "").strip()

    if username_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id))
        return

    if user_states.get(user_id) != "awaiting_telegram_username":
        return
    user_states.pop(user_id, None)

    # Clean username
    username_clean = username_input if username_input.startswith('@') else '@' + username_input
    username_raw = username_input.lstrip('@')

    # Validate
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username_raw):
        bot.reply_to(message, "❌ *Invalid username!*\n\nUse 5-32 chars, letters/numbers/underscore.\nExample: `@username`\n\n💎 Cost: 11 credits", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        return

    # Cooldown
    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ Wait {wait} seconds", reply_markup=main_menu_markup(user_id))
        return

    with active_telegram_sessions_lock:
        if user_id in active_telegram_sessions:
            bot.reply_to(message, "⏳ Search already running!", reply_markup=main_menu_markup(user_id))
            return
        active_telegram_sessions.add(user_id)

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < TELEGRAM_LOOKUP_COST and not unlimited_active:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💎 BUY CREDITS", callback_data="buy"))
        bot.reply_to(message, f"❌ Need {TELEGRAM_LOOKUP_COST} credits. Buy more!", reply_markup=markup, parse_mode="Markdown")
        active_telegram_sessions.discard(user_id)
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 Searching Telegram...", parse_mode="Markdown")
    time.sleep(1)

    result, api_error = call_telegram_lookup_api(username_input)

    # API error - NO DEDUCTION
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, "telegram")
        notify_admin_api_issue("telegram", username_input, api_error)
        active_telegram_sessions.discard(user_id)
        return

    # No result - NO DEDUCTION
    if result.get("error") == "no_result" or not result.get("telegram_id"):
        increment_total_searches(user_id)
        updated_total = get_total_credits(user_id)
        output = f"""❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Username: `{username_clean}`

No records found.

━━━━━━━━━━━━━━━━━━
💎 Credits Used: `0` (No deduction)
💎 Credits Left: `{updated_total}`
{footer()}"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode="Markdown")
        active_telegram_sessions.discard(user_id)
        return

    # Check protection - NO DEDUCTION
    telegram_id = result.get('telegram_id')
    if telegram_id and is_telegram_protected(telegram_id):
        output = f"""🛡️ *PROTECTED TELEGRAM ID*

🔍 Username: `{username_clean}`
🆔 Telegram ID: `{telegram_id}`

This Telegram ID is protected.

Protect yours for ₹99!"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECT", callback_data="plan_protect_telegram"))
        markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode="Markdown")
        active_telegram_sessions.discard(user_id)
        return

    # Valid data - DEDUCT CREDITS
    if not unlimited_active:
        if not deduct_credits(user_id, TELEGRAM_LOOKUP_COST):
            bot.edit_message_text("❌ Failed to deduct credits!", message.chat.id, loading_msg.message_id)
            active_telegram_sessions.discard(user_id)
            return

    increment_total_searches(user_id)
    output = format_telegram_lookup_result(result, username_clean, user_id, unlimited_active, unlimited_expiry)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 NEW SEARCH", callback_data="telegram_lookup"))
    markup.add(InlineKeyboardButton("🏠 MENU", callback_data="main_menu"))

    sent = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode="Markdown")
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent), daemon=True).start()
    active_telegram_sessions.discard(user_id)

# ==================== NUMBER LOOKUP ====================

def format_lookup_result(result, phone, user_id, unlimited_active=False, unlimited_expiry=None):
    if not isinstance(result, dict):
        result = {}

    parsed_results = []
    api_results = result.get('results')
    if isinstance(api_results, dict):
        for key, value in sorted(api_results.items(), key=lambda x: int(re.search(r'\d+', str(x[0]))[0]) if re.search(r'\d+', str(x[0])) else 9999):
            if isinstance(value, dict):
                parsed_results.append(value)
    elif isinstance(api_results, list):
        parsed_results = [v for v in api_results if isinstance(v, dict)]

    if not parsed_results:
        direct = [(k, v) for k, v in result.items() if str(k).lower().startswith('result') and isinstance(v, dict)]
        for key, value in sorted(direct, key=lambda x: int(re.search(r'\d+', str(x[0]))[0]) if re.search(r'\d+', str(x[0])) else 9999):
            parsed_results.append(value)

    if not parsed_results and ('name' in result or 'mobile' in result):
        parsed_results = [result]

    total_found = len(parsed_results)
    parsed_results = parsed_results[:MAX_LOOKUP_RESULTS]
    showing = f"\n📌 Showing: {len(parsed_results)}/{total_found}" if total_found > MAX_LOOKUP_RESULTS else ""

    output = f"""🔍 *NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

📊 Total Results: `{total_found}`{showing}
"""

    for idx, data in enumerate(parsed_results, 1):
        name = data.get('name') or data.get('Name') or data.get('full_name') or 'N/A'
        mobile = data.get('mobile') or data.get('Mobile') or data.get('phone') or phone
        alt = data.get('alt_mobile') or data.get('alternate_mobile') or 'N/A'
        if alt == 'NA' or alt == 'n/a':
            alt = 'N/A'
        output += f"""
━━━━━━━━━━━━━━━━━━
📄 *RESULT {idx}*

📱 Mobile: `{mobile}`
📞 Alternate: `{alt}`
👤 Name: `{name}`
"""

    user = get_user(user_id)
    updated_total = get_total_credits(user_id)

    if unlimited_active:
        output += f"""
━━━━━━━━━━━━━━━━━━
🚀 *UNLIMITED ACTIVE*
Expires: `{unlimited_expiry[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""
━━━━━━━━━━━━━━━━━━
💎 Credits Used: `{NUMBER_LOOKUP_COST}`
💎 Credits Left: `{updated_total}`
🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`"""

    output += f"\n\n⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec{footer()}"
    return output

def process_lookup(message):
    user_id = message.from_user.id
    raw_phone = str(message.text or "").strip()

    if raw_phone == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id))
        return

    if user_states.get(user_id) != "awaiting_number":
        return
    user_states.pop(user_id, None)

    phone = normalize_indian_mobile(raw_phone)

    if not phone:
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian mobile.\nExample: `9876543210`\n\n💎 Cost: 6 credits", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        return

    with active_number_sessions_lock:
        if user_id in active_number_sessions:
            bot.reply_to(message, "⏳ Search already running!", reply_markup=main_menu_markup(user_id))
            return
        active_number_sessions.add(user_id)

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ Wait {wait} seconds", reply_markup=main_menu_markup(user_id))
        active_number_sessions.discard(user_id)
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < NUMBER_LOOKUP_COST and not unlimited_active:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💎 BUY CREDITS", callback_data="buy"))
        bot.reply_to(message, f"❌ Need {NUMBER_LOOKUP_COST} credits. Buy more!", reply_markup=markup, parse_mode="Markdown")
        active_number_sessions.discard(user_id)
        return

    # Check protected - NO DEDUCTION
    if is_number_protected(phone):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECT NUMBER", callback_data="plan_protect_number"))
        markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
        bot.reply_to(message, f"🛡️ *PROTECTED NUMBER*\n📱 `{phone}`\n\nThis number is protected.\n\nProtect yours for ₹99!", reply_markup=markup, parse_mode="Markdown")
        active_number_sessions.discard(user_id)
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 Searching...", parse_mode="Markdown")
    time.sleep(1)

    # Check cache
    cached = get_cached_result(phone)
    if cached:
        if has_valid_number_results(cached):
            if not unlimited_active:
                if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                    bot.edit_message_text("❌ Failed to deduct credits!", message.chat.id, loading_msg.message_id)
                    active_number_sessions.discard(user_id)
                    return
            increment_total_searches(user_id)
            output = format_lookup_result(cached, phone, user_id, unlimited_active, unlimited_expiry)
        else:
            increment_total_searches(user_id)
            updated_total = get_total_credits(user_id)
            output = f"""❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number: `{phone}`

No records found.

━━━━━━━━━━━━━━━━━━
💎 Credits Used: `0` (No deduction)
💎 Credits Left: `{updated_total}`
{footer()}"""
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"))
            markup.add(InlineKeyboardButton("🏠 MENU", callback_data="main_menu"))
            bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode="Markdown")
            active_number_sessions.discard(user_id)
            return
    else:
        # Call API
        result, api_error = call_unstable_json_api(
            {"key": LOOKUP_API_KEY, "service": LOOKUP_API_SERVICE, "number": phone},
            lookup_type="number", max_retries=5, timeout=30
        )

        if not result:
            show_api_error(message.chat.id, loading_msg.message_id)
            notify_admin_api_issue("number", phone, api_error)
            active_number_sessions.discard(user_id)
            return

        if has_valid_number_results(result):
            if not unlimited_active:
                if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                    bot.edit_message_text("❌ Failed to deduct credits!", message.chat.id, loading_msg.message_id)
                    active_number_sessions.discard(user_id)
                    return
            increment_total_searches(user_id)
            save_cached_result(phone, result)
            output = format_lookup_result(result, phone, user_id, unlimited_active, unlimited_expiry)
        else:
            increment_total_searches(user_id)
            updated_total = get_total_credits(user_id)
            output = f"""❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number: `{phone}`

No records found.

━━━━━━━━━━━━━━━━━━
💎 Credits Used: `0` (No deduction)
💎 Credits Left: `{updated_total}`
{footer()}"""
            bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode="Markdown")
            active_number_sessions.discard(user_id)
            return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"))
    markup.add(InlineKeyboardButton("🏠 MENU", callback_data="main_menu"))

    sent = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode="Markdown")
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent), daemon=True).start()
    active_number_sessions.discard(user_id)

# ==================== UI COMPONENTS ====================

def main_menu_markup(user_id=None):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 SEARCH NUMBER", callback_data="lookup"),
        InlineKeyboardButton("💬 SEARCH TELEGRAM", callback_data="telegram_lookup")
    )
    markup.add(
        InlineKeyboardButton("💎 MY CREDITS", callback_data="credits"),
        InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy")
    )
    markup.add(
        InlineKeyboardButton("🛡️ PROTECT DATA", callback_data="protection_menu"),
        InlineKeyboardButton("🤖 BOOK CUSTOM BOT", callback_data="book_bot")
    )
    if user_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("🛠 ADMIN", callback_data="admin"))
    return markup

def credit_packs_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 10 Credits - ₹20", callback_data="plan_c10"),
        InlineKeyboardButton("💰 50 Credits - ₹70", callback_data="plan_c50"),
        InlineKeyboardButton("💰 100 Credits - ₹100", callback_data="plan_c100")
    )
    markup.add(
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹200", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹500", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number"),
        InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    return markup

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    return markup

def join_required_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📢 JOIN CHANNEL", url=GROUP_LINK))
    markup.add(InlineKeyboardButton("✅ I HAVE JOINED", callback_data="check_join"))
    return markup

def is_channel_member(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

def send_join_required(chat_id):
    bot.send_message(chat_id, "🔒 *Join Required*\n\nJoin official channel first.\n\n📢 " + GROUP_LINK, reply_markup=join_required_markup(), parse_mode="Markdown", disable_web_page_preview=True)

def show_credit_packs(message, user_id):
    packs_msg = f"""💎 *CREDIT STORE*
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS*
• 10 Credits → ₹20  
• 50 Credits → ₹70  
• 100 Credits → ₹100

🚀 *UNLIMITED PLANS*
• 7 Days Unlimited → ₹200
• 30 Days Unlimited → ₹500

🛡️ *PROTECTION*
• Number Protection → ₹99
• Telegram Protection → ₹99

━━━━━━━━━━━━━━━━━━
✅ Credits never expire
✅ Manual verification

{footer()}"""
    bot.send_message(message.chat.id, packs_msg, reply_markup=credit_packs_markup(), parse_mode="Markdown")

def show_protection_menu(message):
    text = f"""🛡️ *PROTECTION SERVICES*
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹99
💬 Telegram Protection → ₹99

Protected data will not appear in lookups."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 PROTECT NUMBER - ₹99", callback_data="plan_protect_number"),
        InlineKeyboardButton("💬 PROTECT TELEGRAM - ₹99", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def show_bot_booking(message):
    booking_msg = f"""🤖 *CUSTOM BOT BOOKING*
━━━━━━━━━━━━━━━━━━

💰 Setup: ₹399
📆 API charges: Monthly (separate)
⏰ Delivery: 24-48 hours

👇 Book now
{footer()}"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💳 BOOK BOT - ₹399", callback_data="booking_pay"),
        InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"),
        InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu")
    )
    bot.send_message(message.chat.id, booking_msg, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)

def process_protection_payment_input(message, plan_id):
    user_id = message.from_user.id
    if message.text == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id))
        return

    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_protection_input" and state.get("plan_id") == plan_id):
        return

    user_states.pop(user_id, None)
    value = str(message.text or "").strip()

    if plan_id == "protect_number":
        if not re.match(r'^[6-9]\d{9}$', value):
            bot.reply_to(message, "❌ Invalid number! Enter 10-digit number.", reply_markup=main_menu_markup(user_id))
            return
        if is_number_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
            return
    elif plan_id == "protect_telegram":
        if not re.match(r'^\d{4,15}$', value):
            bot.reply_to(message, "❌ Invalid Telegram ID! Enter numeric ID.", reply_markup=main_menu_markup(user_id))
            return
        if is_telegram_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
            return
    else:
        bot.reply_to(message, "❌ Invalid plan.", reply_markup=main_menu_markup(user_id))
        return

    send_manual_qr_payment(message.chat.id, user_id, message.from_user.username or "no_username", plan_id, protected_number=value)

def handle_plan_selection(call):
    plan_id = call.data.replace("plan_", "")
    user_id = call.from_user.id
    username = call.from_user.username or "no_username"

    plan = PLAN_CONFIG.get(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Invalid plan")
        return

    if plan_id in ["protect_number", "protect_telegram"]:
        labels = {
            "protect_number": ("📱 *NUMBER PROTECTION*", "Enter 10-digit mobile number:", "Example: 9876543210"),
            "protect_telegram": ("💬 *TELEGRAM PROTECTION*", "Enter numeric Telegram ID:", "Example: 7850023357")
        }
        title, prompt, example = labels[plan_id]
        user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
        msg = bot.send_message(
            call.message.chat.id,
            f"""{title}

{prompt}
{example}

💰 Price: ₹{plan['amount']}

Type /cancel to abort""",
            reply_markup=cancel_button(),
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_protection_payment_input, plan_id)
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Creating payment... ✅")
    send_manual_qr_payment(call.message.chat.id, user_id, username, plan_id)

# ==================== BOT HANDLERS ====================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    user = get_user(user_id)
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 BANNED\n\nContact: {ADMIN_USERNAME}")
        return

    try:
        supabase.table("telegram_users").update({
            "telegram_username": username,
            "telegram_name": first_name,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", user_id).execute()
    except:
        pass

    total_credits = get_total_credits(user_id)
    searches = user.get('total_searches', 0) if user else 0

    welcome_msg = f"""🚀 *TRACEX LOOKUP*

👋 Welcome, *{first_name}*

💎 Credits: `{total_credits}`
🔎 Searches: `{searches}`

━━━━━━━━━━━━━━

📱 Number Search → 6 Credits
💬 Telegram Search → 11 Credits

🎁 New users receive free credits.

👇 Select an option below."""

    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_menu_markup(user_id), parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    bot.reply_to(message, "❌ Cancelled.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")

@bot.message_handler(commands=['verify'])
def verify_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /verify TXCODE")
            return
        ok, msg = manual_verify_payment(parts[1], message.from_user.id)
        bot.reply_to(message, f"{'✅' if ok else '❌'} {msg}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['reject'])
def reject_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /reject TXCODE reason")
            return
        reason = parts[2] if len(parts) > 2 else "Not confirmed"
        ok, msg = manual_reject_payment(parts[1], message.from_user.id, reason)
        bot.reply_to(message, f"{'✅' if ok else '❌'} {msg}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(message):
    global MAINTENANCE_MODE
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /maintenance on/off")
        return
    MAINTENANCE_MODE = parts[1].lower() == "on"
    bot.reply_to(message, f"Maintenance {'ON' if MAINTENANCE_MODE else 'OFF'}")

@bot.message_handler(content_types=['photo', 'document'])
def payment_screenshot_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_payment_screenshot"):
        return

    tx_code = state.get("tx_code")
    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, f"✅ Screenshot already sent for TX `{tx_code}`.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        user_states.pop(user_id, None)
        return

    proof_forwarded_txs.add(tx_code)
    caption = f"📸 *PAYMENT SCREENSHOT*\n👤 User: `{user_id}`\n🧾 TX: `{tx_code}`\n/verify {tx_code}"
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )

    try:
        try:
            bot.copy_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        except:
            bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
        send_admin_alert(caption, reply_markup=admin_markup)
        bot.reply_to(message, f"✅ Screenshot sent!\n\n🧾 TX: `{tx_code}`\nWait for verification.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        user_states.pop(user_id, None)
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        bot.reply_to(message, f"❌ Error. Contact {ADMIN_USERNAME}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)

    if user and user.get('is_banned'):
        bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
        return

    if call.data == "check_join":
        if is_channel_member(user_id):
            bot.answer_callback_query(call.id, "Joined ✅")
            try:
                bot.edit_message_text("✅ Joined verified!\n\nUse /start", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
            except:
                bot.send_message(call.message.chat.id, "✅ Joined! Use /start")
        else:
            bot.answer_callback_query(call.id, "Join first", show_alert=True)
        return

    if not is_channel_member(user_id):
        bot.answer_callback_query(call.id, "Join channel first", show_alert=True)
        send_join_required(call.message.chat.id)
        return

    # Main menu navigation
    if call.data == "main_menu":
        try:
            bot.edit_message_text("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        except:
            bot.send_message(call.message.chat.id, "🏠 *MAIN MENU*", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "cancel":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        active_number_sessions.discard(user_id)
        active_telegram_sessions.discard(user_id)
        try:
            bot.edit_message_text("❌ Cancelled.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
        except:
            bot.send_message(call.message.chat.id, "❌ Cancelled.", reply_markup=main_menu_markup(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "lookup":
        user_states[user_id] = "awaiting_number"
        msg = bot.send_message(call.message.chat.id, "📱 *NUMBER SEARCH*\n\nEnter 10-digit mobile number\n\nExample: `9876543210`\n\n💎 Cost: 6 Credits\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)

    elif call.data == "telegram_lookup":
        user_states[user_id] = "awaiting_telegram_username"
        msg = bot.send_message(call.message.chat.id, "💬 *TELEGRAM SEARCH*\n\nEnter Telegram username\n\nExamples:\n`@username`\n`username`\n\n💎 Cost: 11 Credits\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_telegram_lookup)
        bot.answer_callback_query(call.id)

    elif call.data == "credits":
        total = get_total_credits(user_id)
        unlimited_expiry = user.get('unlimited_expiry') if user else None
        unlimited_text = ""
        if unlimited_expiry:
            try:
                expiry = datetime.fromisoformat(str(unlimited_expiry).replace('Z', '+00:00'))
                if expiry > datetime.now(timezone.utc):
                    unlimited_text = f"\n🚀 Unlimited until: `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        msg = f"""💎 *MY CREDITS*
━━━━━━━━━━━━━━━━━━
💰 Credits: `{total}`{unlimited_text}
🔎 Used: `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
📦 Credit Packs: 10/50/100
🚀 Unlimited: 7d/30d
🛡️ Protection: ₹99 each"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 BUY", callback_data="buy"), InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "buy":
        show_credit_packs(call.message, user_id)
        bot.answer_callback_query(call.id)

    elif call.data == "protection_menu":
        show_protection_menu(call.message)
        bot.answer_callback_query(call.id)

    elif call.data == "book_bot":
        show_bot_booking(call.message)
        bot.answer_callback_query(call.id)

    elif call.data == "booking_pay":
        bot.answer_callback_query(call.id, "Creating booking...")
        send_manual_qr_payment(call.message.chat.id, user_id, call.from_user.username or "no_username", "bot_booking")

    elif call.data.startswith("plan_"):
        handle_plan_selection(call)

    elif call.data.startswith("submitproof_"):
        tx_code = call.data.replace("submitproof_", "")
        user_states[user_id] = {"state": "awaiting_payment_screenshot", "tx_code": tx_code}
        bot.send_message(call.message.chat.id, f"📸 *Send payment screenshot*\n\n🧾 TX: `{tx_code}`\n\n⏰ You have 3 minutes!", reply_markup=cancel_button(), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("adminverify_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        tx_code = call.data.replace("adminverify_", "")
        ok, msg = manual_verify_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Verified" if ok else msg, show_alert=not ok)

    elif call.data.startswith("adminreject_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        tx_code = call.data.replace("adminreject_", "")
        ok, msg = manual_reject_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Rejected" if ok else msg, show_alert=not ok)

    elif call.data == "admin":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        show_admin_panel(call.message)
        bot.answer_callback_query(call.id)

    elif call.data in ["admin_add", "admin_remove", "admin_ban", "admin_unban", "admin_broadcast", "admin_stats", "admin_transactions", "admin_back", "admin_giveaway"]:
        if user_id != ADMIN_ID:
            return
        if call.data == "admin_add":
            user_states[user_id] = "admin_add"
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS/UNLIMITED*\n\nCredits: `user_id credits`\nExample: `123456789 50`\n\nUnlimited: `user_id u1w` or `u1m`\nExample: `123456789 u1w`", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE*\n\nRemove credits: `user_id credits`\nDeactivate unlimited: `user_id unlimited`", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_remove)
        elif call.data == "admin_ban":
            user_states[user_id] = "admin_ban"
            msg = bot.send_message(call.message.chat.id, "🚫 *BAN USER*\n\nEnter user ID", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_ban)
        elif call.data == "admin_unban":
            user_states[user_id] = "admin_unban"
            msg = bot.send_message(call.message.chat.id, "✅ *UNBAN USER*\n\nEnter user ID", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_unban)
        elif call.data == "admin_broadcast":
            user_states[user_id] = "admin_broadcast"
            msg = bot.send_message(call.message.chat.id, "📢 *BROADCAST*\n\nSend your message", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_broadcast)
        elif call.data == "admin_giveaway":
            user_states[user_id] = "admin_giveaway"
            msg = bot.send_message(call.message.chat.id, "🎁 *GIVEAWAY*\n\nEnter credits for ALL users", reply_markup=cancel_button(), parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_admin_giveaway)
        elif call.data == "admin_stats":
            show_admin_stats(call.message)
        elif call.data == "admin_transactions":
            show_admin_transactions(call.message)
        elif call.data == "admin_back":
            show_admin_panel(call.message)
        bot.answer_callback_query(call.id)

# ==================== ADMIN FUNCTIONS ====================

def show_admin_panel(message):
    stats = get_stats()
    admin_msg = f"""*🛠 ADMIN PANEL*
━━━━━━━━━━━━━━━━
👥 Users: `{stats['total_users']}`
🔍 Searches: `{stats['total_searches']}`
💎 Total Credits: `{stats['total_credits']}`
💰 Revenue: ₹{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
🚫 Banned: `{stats['banned_users']}`
💾 Cache: `{stats['cache_size']}`
🛡️ Protected: `{stats['protected_count']}`
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ ADD", callback_data="admin_add"),
        InlineKeyboardButton("➖ REMOVE", callback_data="admin_remove"),
        InlineKeyboardButton("🚫 BAN", callback_data="admin_ban"),
        InlineKeyboardButton("✅ UNBAN", callback_data="admin_unban"),
        InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"),
        InlineKeyboardButton("🎁 GIVEAWAY", callback_data="admin_giveaway"),
        InlineKeyboardButton("📊 STATS", callback_data="admin_stats"),
        InlineKeyboardButton("📋 TRANSACTIONS", callback_data="admin_transactions"),
        InlineKeyboardButton("🔙 BACK", callback_data="main_menu")
    )
    bot.send_message(message.chat.id, admin_msg, reply_markup=markup, parse_mode="Markdown")

def show_admin_stats(message):
    stats = get_stats()
    msg = f"""📊 *DETAILED STATS*
━━━━━━━━━━━━━━━━━━
👥 Total Users: `{stats['total_users']}`
👤 Active: `{stats['total_users'] - stats['banned_users']}`
🚫 Banned: `{stats['banned_users']}`
🔍 Total Searches: `{stats['total_searches']}`
💎 Total Credits: `{stats['total_credits']}`
💰 Revenue: ₹{stats['total_revenue']}
⏳ Pending Payments: `{stats['pending_payments']}`
💾 Cache Size: `{stats['cache_size']}`
🛡️ Protected: `{stats['protected_count']}`
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

def show_admin_transactions(message):
    txs = get_recent_transactions()
    if not txs:
        msg = "📋 No transactions"
    else:
        msg = "📋 *RECENT TRANSACTIONS*\n\n"
        for tx in txs:
            status = "✅" if tx.get('status') == "success" else "⏳" if tx.get('status') == "pending" else "❌"
            msg += f"{status} `{tx.get('payment_id', '')[:20]}` | {tx.get('telegram_user_id')} | ₹{tx.get('amount', 0)} | {tx.get('plan_id')}\n"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

def process_admin_add(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(ADMIN_ID))
        return
    try:
        parts = message.text.split()
        target_user, _ = resolve_user_identifier(parts[0])
        if not target_user:
            bot.reply_to(message, "❌ User not found")
            return
        value = parts[1].strip().lower()
        if value in ["u1w", "u1m"]:
            ok, expiry = activate_unlimited_plan_for_user(target_user, value)
            if ok:
                label = PLAN_CONFIG.get(value, {}).get("label", value)
                bot.reply_to(message, f"✅ Added {label} to {target_user}")
        else:
            credits = int(value)
            new_total = add_credits(target_user, credits)
            bot.reply_to(message, f"✅ Added {credits} credits\nNew total: {new_total}")
    except:
        bot.reply_to(message, "❌ Invalid format")

def process_admin_remove(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled")
        return
    try:
        parts = message.text.split()
        target_user, user = resolve_user_identifier(parts[0])
        if not target_user:
            bot.reply_to(message, "❌ User not found")
            return
        action = parts[1].strip().lower()
        if action in ["unlimited", "deactivate", "off"]:
            supabase.table("telegram_users").update({"unlimited_expiry": None}).eq("telegram_user_id", target_user).execute()
            bot.reply_to(message, f"✅ Unlimited deactivated for {target_user}")
        else:
            credits = int(action)
            current = user.get('credits', 0)
            new_credits = max(0, current - credits)
            supabase.table("telegram_users").update({"credits": new_credits}).eq("telegram_user_id", target_user).execute()
            bot.reply_to(message, f"✅ Removed {credits} credits\nNew total: {new_credits}")
    except:
        bot.reply_to(message, "❌ Invalid format")

def process_admin_ban(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled")
        return
    try:
        target = int(message.text.strip())
        ban_user(target)
        bot.reply_to(message, f"✅ Banned {target}")
    except:
        bot.reply_to(message, "❌ Invalid ID")

def process_admin_unban(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled")
        return
    try:
        target = int(message.text.strip())
        unban_user(target)
        bot.reply_to(message, f"✅ Unbanned {target}")
    except:
        bot.reply_to(message, "❌ Invalid ID")

def process_admin_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled")
        return
    text = message.text.strip()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ SEND", callback_data="broadcast_confirm"), InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    temp_data[message.from_user.id] = {'broadcast_text': text}
    bot.reply_to(message, f"📢 Confirm broadcast to ALL users?\n\n{text[:200]}", reply_markup=markup, parse_mode="Markdown")

def process_admin_giveaway(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states.pop(message.from_user.id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled")
        return
    try:
        credits = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ GIVE", callback_data="giveaway_confirm"), InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
        temp_data[message.from_user.id] = {'giveaway_credits': credits}
        bot.reply_to(message, f"🎁 Give {credits} credits to ALL users?", reply_markup=markup)
    except:
        bot.reply_to(message, "❌ Invalid number")

# Callback for broadcast/giveaway confirmation
@bot.callback_query_handler(func=lambda call: call.data in ["broadcast_confirm", "giveaway_confirm"] and call.from_user.id == ADMIN_ID)
def confirm_admin_action(call):
    user_id = call.from_user.id
    if call.data == "broadcast_confirm":
        if user_id not in temp_data or 'broadcast_text' not in temp_data[user_id]:
            bot.answer_callback_query(call.id, "No broadcast data")
            return
        text = temp_data[user_id]['broadcast_text']
        users = get_all_users()
        sent = 0
        for uid in users:
            try:
                bot.send_message(uid, f"📢 *ANNOUNCEMENT*\n{text}", parse_mode="Markdown")
                sent += 1
                time.sleep(0.05)
            except:
                pass
        bot.edit_message_text(f"✅ Broadcast sent to {sent} users", call.message.chat.id, call.message.message_id)
        del temp_data[user_id]

    elif call.data == "giveaway_confirm":
        if user_id not in temp_data or 'giveaway_credits' not in temp_data[user_id]:
            bot.answer_callback_query(call.id, "No giveaway data")
            return
        credits = temp_data[user_id]['giveaway_credits']
        users = get_all_users()
        success = 0
        for uid in users:
            add_credits(uid, credits)
            success += 1
            time.sleep(0.05)
        bot.edit_message_text(f"🎁 Giveaway complete! {credits} credits to {success} users", call.message.chat.id, call.message.message_id)
        del temp_data[user_id]

    bot.answer_callback_query(call.id)

# ==================== FLASK WEBHOOK ====================

@app.route('/')
def home():
    return "TraceX Bot Running"

@app.route('/cashfree/webhook', methods=['POST'])
def cashfree_webhook():
    # Simplified webhook - production would need full Cashfree integration
    return jsonify({"status": "ok"}), 200

def keep_alive():
    def run():
        port = int(os.getenv("PORT", "8080"))
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ==================== START BOT ====================

if __name__ == "__main__":
    print("=" * 50)
    print(f"TraceX Lookup v{BOT_VERSION}")
    print(f"Pricing: Number={NUMBER_LOOKUP_COST} | Telegram={TELEGRAM_LOOKUP_COST}")
    print(f"Unlimited: 7d=₹200 | 30d=₹500")
    print("=" * 50)

    keep_alive()
    print("✅ Flask server started")

    # Clear webhook
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    while True:
        try:
            bot.infinity_polling(timeout=60, skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)