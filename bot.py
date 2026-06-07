"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 6.0.0 - Clean UI, Updated Pricing, Vehicle Lookup Removed
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
from flask import Flask, request, jsonify

# ==================== DEPENDENCY CHECK ====================
def _require_package(import_name, pip_name=None):
    try:
        return __import__(import_name)
    except ImportError:
        name = pip_name or import_name
        print(f"❌ Missing dependency: {name}")
        print(f"Install it with: pip install {name}")
        raise

telebot = _require_package("telebot", "pyTelegramBotAPI")
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
requests = _require_package("requests", "requests")

# ==================== ENVIRONMENT VARIABLES (SECURITY FIX) ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "TEST")
RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "https://your-app.onrender.com")
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/api/v1/lookup.php").strip()
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "").strip()
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number").strip()
TELEGRAM_LOOKUP_API_URL = os.getenv("TELEGRAM_LOOKUP_API_URL", "https://exploitsindia.site/lookup/telegram.php")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Gaurav_beni_0001")
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")

# Validate required config
if not BOT_TOKEN:
    print("❌ BOT_TOKEN environment variable is required")
    sys.exit(1)
if not SUPABASE_URL or not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY):
    print("❌ SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY are required")
    sys.exit(1)

# ==================== CONSTANTS ====================
ADMIN_ID = int(os.getenv("ADMIN_ID", "7850023357"))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1003743686626"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@gaurav_beniwal_0001")
BOT_VERSION = "6.0.0"

# Updated pricing
NUMBER_LOOKUP_COST = 5
TELEGRAM_LOOKUP_COST = 10

# Updated unlimited plan pricing
UNLIMITED_PLANS = {
    "u1w": {"amount": 200, "minutes": 10080, "label": "7 Days Unlimited", "days": 7},
    "u1m": {"amount": 500, "minutes": 43200, "label": "30 Days Unlimited", "days": 30}
}

CREDIT_PLANS = {
    "c10": {"amount": 20, "credits": 10, "label": "10 Credits"},
    "c50": {"amount": 70, "credits": 50, "label": "50 Credits"},
    "c100": {"amount": 100, "credits": 100, "label": "100 Credits"}
}

PROTECTION_PLANS = {
    "protect_number": {"amount": 99, "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "label": "Telegram Number Protection"}
}

BOT_BOOKING_PLAN = {"amount": 399, "label": "Custom Bot Booking"}

# All plans merged for config lookup
PLAN_CONFIG = {}
PLAN_CONFIG.update(CREDIT_PLANS)
PLAN_CONFIG.update(UNLIMITED_PLANS)
PLAN_CONFIG.update(PROTECTION_PLANS)
PLAN_CONFIG["bot_booking"] = BOT_BOOKING_PLAN

MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900
COOLDOWN_SECONDS = 3
AUTO_DELETE_SECONDS = 120
GROUP_LINK = "https://t.me/Gaurav_beni_0001"
PAYMENT_SESSION_COOLDOWN_SECONDS = 60
GENERIC_API_ERROR_MESSAGE = "❌ *API Error*\n\n💎 Credits NOT deducted"

# ==================== SUPABASE LITE CLIENT ====================
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
            raise RuntimeError("Supabase credentials required")
        url = f"{self.client.url}/rest/v1/{self.table}"
        headers = dict(self.client.headers)
        headers.update(self.headers)
        response = requests.request(
            self.method, url, params=self.params, json=self.payload,
            headers=headers, timeout=30
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase REST error {response.status_code}: {response.text[:500]}")
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

# ==================== INITIALIZATION ====================
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True)

# State Management
user_states = {}
user_cooldown = {}
temp_data = {}
payment_session_cooldown = {}
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

# ==================== HELPER FUNCTIONS ====================
def show_api_error(chat_id, message_id, lookup_type="api"):
    try:
        bot.edit_message_text(GENERIC_API_ERROR_MESSAGE, chat_id, message_id, parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to show API error: {e}")

def safe_json_response(response):
    try:
        return response.json()
    except Exception:
        raise ValueError("Invalid API JSON response")

def has_valid_number_results(result):
    if not isinstance(result, dict):
        return False
    api_results = result.get("results")
    if isinstance(api_results, dict):
        return any(isinstance(v, dict) for v in api_results.values())
    if isinstance(api_results, list):
        return any(isinstance(v, dict) for v in api_results)
    return any(str(k).lower().startswith("result") and isinstance(v, dict) for k, v in result.items()) or ("name" in result or "mobile" in result)

def call_unstable_json_api(params, lookup_type="number", max_retries=5, timeout=30):
    base_url = str(LOOKUP_API_URL or "").strip()
    clean_params = {str(k): str(v).strip() for k, v in (params or {}).items() if v is not None}
    
    headers_attempts = [
        {"User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/6.0", "Accept": "application/json,text/plain,*/*", "Connection": "close"},
        {"User-Agent": "python-requests TraceXBot/6.0", "Accept": "application/json,text/plain,*/*", "Connection": "close"},
    ]
    
    last_error = "unknown"
    for attempt in range(1, max_retries + 1):
        headers = headers_attempts[(attempt - 1) % len(headers_attempts)]
        try:
            response = requests.get(base_url, params=clean_params, headers=headers, timeout=timeout)
            raw_preview = (response.text or "")[:500].replace("\n", " ")
            
            if response.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                last_error = f"temporary_http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue
            
            if response.status_code != 200:
                last_error = f"http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue
            
            if raw_preview.lstrip().lower().startswith("<!doctype") or "<html" in raw_preview.lower():
                last_error = "html_non_json_response"
                time.sleep(min(2 * attempt, 8))
                continue
            
            try:
                data = response.json()
            except Exception:
                last_error = "json_parse_failed"
                time.sleep(min(2 * attempt, 8))
                continue
            
            if not isinstance(data, dict):
                last_error = "json_not_object"
                time.sleep(min(2 * attempt, 8))
                continue
            
            return data, None
            
        except requests.exceptions.Timeout:
            last_error = "timeout"
            time.sleep(min(2 * attempt, 8))
        except Exception as e:
            last_error = f"exception_{e}"
            time.sleep(min(2 * attempt, 8))
    
    return None, last_error

def notify_admin_api_issue(lookup_type, query, error_reason):
    try:
        bot.send_message(ADMIN_ID, f"⚠️ *API TEMP ISSUE*\n\nType: `{lookup_type}`\nQuery: `{query}`\nReason: `{str(error_reason)[:500]}`\n\nUser credits were not deducted.", parse_mode="Markdown")
    except Exception as e:
        print(f"Admin API issue notify failed: {e}")

def split_long_text(text, limit=TELEGRAM_SAFE_LIMIT):
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

def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 Website: {WEBSITE_URL}\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def header(title, emoji="🚀"):
    return f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━\n"

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return markup

# ==================== UI COMPONENTS ====================
def main_menu_markup(current_user_id=None):
    """Simplified beginner-friendly main menu"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Search Number", callback_data="lookup"),
        InlineKeyboardButton("💬 Search Telegram", callback_data="telegram_lookup")
    )
    markup.add(
        InlineKeyboardButton("💎 My Credits", callback_data="credits"),
        InlineKeyboardButton("🛒 Buy Credits", callback_data="buy")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Protect Data", callback_data="protection_menu"),
        InlineKeyboardButton("🤖 Book Custom Bot", callback_data="book_bot")
    )
    if current_user_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("🛠 Admin", callback_data="admin"))
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
    markup.add(InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number"))
    markup.add(InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    return markup

def protection_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Protect Number - ₹99", callback_data="plan_protect_number"),
        InlineKeyboardButton("💬 Protect Telegram ID - ₹99", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
    )
    return markup

def join_required_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📢 Join Channel", url=GROUP_LINK))
    markup.add(InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
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
    bot.send_message(
        chat_id,
        f"🔒 *Join Required*\n━━━━━━━━━━━━━━━━\n\nPlease join our official channel first.\n\n📢 Channel: {GROUP_LINK}\n\nThen tap `✅ I Have Joined`.",
        reply_markup=join_required_markup(),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

def telegram_lookup_protection_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛡️ Protect My Telegram ID", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔍 New Telegram Lookup", callback_data="telegram_lookup")
    )
    markup.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return markup

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
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
    except Exception as e:
        print(f"Supabase get_user error: {e}")
        return None

def normalize_indian_mobile(value):
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits if re.match(r"^[6-9]\d{9}$", digits) else None

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
    except Exception as e:
        print(f"Resolve username error: {e}")
    return None, None

def add_credits(telegram_user_id, amount):
    try:
        response = supabase.table("telegram_users").select("credits").eq("telegram_user_id", telegram_user_id).execute()
        
        if not response.data or len(response.data) == 0:
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
            if result.data and len(result.data) > 0:
                return result.data[0].get('credits', amount)
            return 0
        else:
            current_credits = response.data[0].get('credits', 0)
            new_credits = current_credits + amount
            
            supabase.table("telegram_users").update({
                "credits": new_credits,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            
            verify_response = supabase.table("telegram_users").select("credits").eq("telegram_user_id", telegram_user_id).execute()
            if verify_response.data:
                return verify_response.data[0].get('credits', new_credits)
            return new_credits
    except Exception as e:
        print(f"Add credits error: {e}")
        return 0

def deduct_credits(telegram_user_id, amount=1):
    try:
        amount = int(amount or 1)
        user = get_user(telegram_user_id)
        if not user:
            return False

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
    except Exception as e:
        print(f"Get total credits error: {e}")
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
    except Exception as e:
        print(f"Check protected number error: {e}")
        return False

def add_protected_number(phone_number, telegram_user_id=None):
    try:
        supabase.table("protected_numbers").insert({
            "phone_number": phone_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Add protected number error: {e}")
        return False

def is_telegram_protected(telegram_id):
    try:
        response = supabase.table("protected_telegrams").select("*").eq("telegram_id", str(telegram_id)).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Check protected telegram error: {e}")
        return False

def add_protected_telegram(telegram_id, telegram_user_id=None):
    try:
        supabase.table("protected_telegrams").insert({
            "telegram_id": str(telegram_id),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Add protected telegram error: {e}")
        return False

def get_cached_result(phone_number):
    try:
        response = supabase.table("search_results").select("*").eq("mobile_number", phone_number).execute()
        if response.data and len(response.data) > 0:
            return response.data[0].get('raw_data')
        return None
    except Exception as e:
        print(f"Get cached result error: {e}")
        return None

def save_cached_result(phone_number, raw_data):
    try:
        existing = supabase.table("search_results").select("mobile_number").eq("mobile_number", phone_number).limit(1).execute()
        if existing.data and len(existing.data) > 0:
            supabase.table("search_results").update({"raw_data": raw_data}).eq("mobile_number", phone_number).execute()
        else:
            supabase.table("search_results").insert({
                "mobile_number": phone_number,
                "raw_data": raw_data,
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        return True
    except Exception as e:
        print(f"Save cached result error: {e}")
        return False

def ban_user(telegram_user_id):
    try:
        supabase.table("telegram_users").update({
            "is_banned": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        return True
    except Exception as e:
        print(f"Ban user error: {e}")
        return False

def unban_user(telegram_user_id):
    try:
        supabase.table("telegram_users").update({
            "is_banned": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        return True
    except Exception as e:
        print(f"Unban user error: {e}")
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
        pending_payments_count = pending_resp.count
        
        revenue_resp = supabase.table("payment_claims").select("amount").eq("status", "success").execute()
        total_revenue = sum(p.get('amount', 0) for p in revenue_resp.data)
        
        cache_resp = supabase.table("search_results").select("*", count="exact").execute()
        cache_size = cache_resp.count
        
        protected_resp = supabase.table("protected_numbers").select("*", count="exact").execute()
        protected_count = protected_resp.count
        
        return {
            'total_users': total_users or 0,
            'total_searches': total_searches,
            'total_credits': total_credits,
            'banned_users': banned_users or 0,
            'pending_payments': pending_payments_count or 0,
            'total_revenue': total_revenue,
            'cache_size': cache_size or 0,
            'protected_count': protected_count or 0
        }
    except Exception as e:
        print(f"Get stats error: {e}")
        return {
            'total_users': 0, 'total_searches': 0, 'total_credits': 0,
            'banned_users': 0, 'pending_payments': 0, 'total_revenue': 0,
            'cache_size': 0, 'protected_count': 0
        }

def get_all_users():
    try:
        response = supabase.table("telegram_users").select("telegram_user_id").eq("is_banned", False).execute()
        return [row['telegram_user_id'] for row in response.data]
    except Exception as e:
        print(f"Get all users error: {e}")
        return []

def add_giveaway_credits(credits):
    try:
        users = get_all_users()
        success_count = 0
        for user_id in users:
            add_credits(user_id, credits)
            success_count += 1
        return success_count, 0
    except Exception as e:
        print(f"Giveaway error: {e}")
        return 0, 0

def get_recent_transactions(limit=20):
    try:
        response = supabase.table("payment_claims").select("*").order("created_at", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        print(f"Get transactions error: {e}")
        return []

def activate_unlimited_plan(user_id, plan_id):
    plan = UNLIMITED_PLANS.get(plan_id)
    if not plan:
        return False, "Invalid plan"
    
    now_dt = datetime.now(timezone.utc)
    user = get_user(user_id)
    current_expiry = user.get('unlimited_expiry') if user else None
    
    start_from = now_dt
    if current_expiry:
        try:
            expiry_dt = datetime.fromisoformat(str(current_expiry).replace("Z", "+00:00"))
            if expiry_dt > now_dt:
                start_from = expiry_dt
        except Exception:
            pass
    
    new_expiry = start_from + timedelta(days=plan["days"])
    supabase.table("telegram_users").update({
        "unlimited_expiry": new_expiry.isoformat(),
        "updated_at": now_dt.isoformat()
    }).eq("telegram_user_id", user_id).execute()
    
    return True, new_expiry

# ==================== TELEGRAM LOOKUP API ====================
def call_telegram_lookup_api(username):
    try:
        if not username.startswith('@'):
            username = '@' + username
        
        from urllib.parse import urlencode
        url = f"{TELEGRAM_LOOKUP_API_URL}?{urlencode({'username': username})}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/6.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        }
        
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
        
        country_match = re.search(r'🌍 Country:\s*([A-Za-z\s]+)', html_content)
        if country_match:
            result['country'] = country_match.group(1).strip()
        
        cc_match = re.search(r'📞 Country Code:\s*\+(\d+)', html_content)
        if cc_match:
            result['country_code'] = '+' + cc_match.group(1)
        
        if result.get('telegram_id') or result.get('phone_number'):
            return result, None
        else:
            no_data_markers = ["no data found", "not found", "no records", "no result", "data not found"]
            if any(marker in html_content.lower() for marker in no_data_markers):
                return {"error": "no_result"}, None
            if html_content.strip():
                return {"error": "no_result"}, None
            return None, "empty_api_response"
            
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, f"exception_{e}"

def format_telegram_lookup_result(result, username, user_id, unlimited_active=False, unlimited_expiry=None):
    output = f"""
🔍 *TELEGRAM LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lookup Result for: `{username}`
────────────────────────

👥 Username: `{result.get('username', username)}`
🆔 Telegram ID: `{result.get('telegram_id', 'N/A')}`
📱 Phone Number: `{result.get('phone_number', 'N/A')}`
🌍 Country: `{result.get('country', 'N/A')}`
📞 Country Code: `{result.get('country_code', 'N/A')}`

────────────────────────
"""
    
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    
    if unlimited_active:
        output += f"""
🚀 *UNLIMITED PLAN ACTIVE*
No credits deducted!
Expires: `{unlimited_expiry[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""
💎 *Credits Used:* `{TELEGRAM_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{user.get('total_searches', 0) if user else 0}`"""
    
    output += f"""

⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec
{footer()}
"""
    return output

# ==================== LOOKUP RESULT FORMATTING ====================
def format_lookup_result(result, phone, user_id, unlimited_active=False, unlimited_expiry=None):
    if not isinstance(result, dict):
        result = {}

    parsed_results = []
    api_results = result.get('results')
    
    if isinstance(api_results, dict):
        def sort_key(item):
            key = str(item[0])
            m = re.search(r'\d+', key)
            return int(m.group()) if m else 9999
        for key, value in sorted(api_results.items(), key=sort_key):
            if isinstance(value, dict):
                parsed_results.append(value)
            elif isinstance(value, list):
                parsed_results.extend([v for v in value if isinstance(v, dict)])
    elif isinstance(api_results, list):
        parsed_results = [v for v in api_results if isinstance(v, dict)]

    if not parsed_results:
        direct_result_items = [(k, v) for k, v in result.items() if str(k).lower().startswith('result') and isinstance(v, dict)]
        def sort_key2(item):
            m = re.search(r'\d+', str(item[0]))
            return int(m.group()) if m else 9999
        for key, value in sorted(direct_result_items, key=sort_key2):
            parsed_results.append(value)

    if not parsed_results and ('name' in result or 'mobile' in result):
        parsed_results = [result]

    total_results_found = len(parsed_results)
    parsed_results = parsed_results[:MAX_LOOKUP_RESULTS]
    showing_text = f"\n📌 Showing: `{len(parsed_results)}` / `{total_results_found}`" if total_results_found > MAX_LOOKUP_RESULTS else ""
    
    output = f"""
🔍 *NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

📊 Total Results Found: `{total_results_found}`{showing_text}
"""
    
    for idx, data in enumerate(parsed_results, 1):
        name = data.get('name') or data.get('Name') or data.get('full_name') or 'N/A'
        alt_mobile = data.get('alt_mobile') or data.get('alternate_mobile') or 'N/A'
        father_name = data.get('father_name') or data.get('Father_Name') or 'N/A'
        email = data.get('email') or data.get('Email') or 'N/A'
        operator = data.get('operator') or data.get('Operator') or 'N/A'
        circle = data.get('state_circle') or data.get('circle') or 'N/A'
        address = data.get('address') or data.get('Address') or 'N/A'
        mobile = data.get('mobile') or data.get('Mobile') or phone
        
        output += f"""

━━━━━━━━━━━━━━━━━━
📄 *RESULT {idx}*

📱 Mobile: `{mobile}`
📞 Alternate: `{alt_mobile if alt_mobile != 'NA' else 'N/A'}`
👤 Name: `{name}`
👨 Father: `{father_name if father_name != 'NA' else 'N/A'}`
📧 Email: `{email if email not in ['n/a', 'NA'] else 'N/A'}`
📡 Operator: `{operator if operator != 'NA' else 'N/A'}`
📍 Circle: `{circle if circle != 'NA' else 'N/A'}`
🏠 Address: `{address if address != 'NA' else 'N/A'}`"""
    
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    
    if unlimited_active:
        output += f"""

━━━━━━━━━━━━━━━━━━
🚀 *UNLIMITED PLAN ACTIVE*
No credits deducted!
Expires: `{unlimited_expiry[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{NUMBER_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{user.get('total_searches', 0) if user else 0}`"""
    
    output += f"""

⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec
{footer()}
"""
    return output

# ==================== LOOKUP PROCESSORS ====================
def process_lookup(message):
    user_id = message.from_user.id
    raw_phone = str(message.text or "").strip()

    if raw_phone == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_number":
        return

    user_states.pop(user_id, None)
    phone = normalize_indian_mobile(raw_phone)

    if not phone:
        bot.reply_to(message, "❌ *Invalid Number!*\n\nPlease enter a valid 10-digit mobile number.\nExample: `9876543210`", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    with active_number_sessions_lock:
        if user_id in active_number_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current result.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        active_number_sessions.add(user_id)
    
    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        active_number_sessions.discard(user_id)
        return
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < NUMBER_LOOKUP_COST and not unlimited_active:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 Buy Credits", callback_data="buy"))
        markup.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        bot.reply_to(message, f"❌ *Not enough credits!*\n\nNumber Lookup costs `{NUMBER_LOOKUP_COST}` credits.\n\nBuy more credits or get an unlimited plan.", 
                    reply_markup=markup, parse_mode='Markdown')
        active_number_sessions.discard(user_id)
        return
    
    if is_number_protected(phone):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ Protect My Number", callback_data="plan_protect_number"))
        markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        bot.reply_to(message, f"""
🛡️ *Protected Number*

📱 `{phone}`

This number is protected. Details are hidden.

You can also protect your number for ₹99!
""", reply_markup=markup, parse_mode='Markdown')
        active_number_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching...*", parse_mode='Markdown')
    
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching..*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    cached_result = get_cached_result(phone)
    
    if cached_result and has_valid_number_results(cached_result):
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_number_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        output = format_lookup_result(cached_result, phone, user_id, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 New Search", callback_data="lookup"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 Join Group", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
        active_number_sessions.discard(user_id)
        return
    
    result, api_error_reason = call_unstable_json_api(
        {"key": LOOKUP_API_KEY, "service": LOOKUP_API_SERVICE, "number": phone},
        lookup_type="number",
        max_retries=5,
        timeout=30
    )

    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="number")
        notify_admin_api_issue("number", phone, api_error_reason)
        active_number_sessions.discard(user_id)
        return

    if has_valid_number_results(result):
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_number_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        save_cached_result(phone, result)
        output = format_lookup_result(result, phone, user_id, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 New Search", callback_data="lookup"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 Join Group", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
        active_number_sessions.discard(user_id)
    else:
        increment_total_searches(user_id)
        updated_total = get_total_credits(user_id)
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number: `{phone}`

🚫 No records available in database

💡 Tips:
• Check the number again
• Try another number
• Ensure it's a valid Indian mobile number

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `0` (No deduction for no results)
💎 *Credits Left:* `{updated_total}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        active_number_sessions.discard(user_id)

def process_telegram_lookup(message):
    user_id = message.from_user.id
    username_input = str(message.text or "").strip()

    if username_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_telegram_username":
        return

    user_states.pop(user_id, None)
    
    username_input = username_input.lstrip('@')
    
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username_input):
        bot.reply_to(message, "❌ *Invalid Username!*\n\nEnter a valid Telegram username.\nExamples: `@username` or `username`\n\n💎 Cost: `5 credits` per search", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    with active_telegram_sessions_lock:
        if user_id in active_telegram_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        active_telegram_sessions.add(user_id)
    
    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < TELEGRAM_LOOKUP_COST and not unlimited_active:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 Buy Credits", callback_data="buy"))
        markup.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        bot.reply_to(message, f"❌ *Not enough credits!*\n\nTelegram Lookup costs `{TELEGRAM_LOOKUP_COST}` credits.\n\nBuy more credits or get an unlimited plan.", 
                    reply_markup=markup, parse_mode='Markdown')
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Telegram...*", parse_mode='Markdown')
    
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching Telegram..*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching Telegram...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, api_error_reason = call_telegram_lookup_api(username_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="telegram")
        notify_admin_api_issue("telegram_lookup", username_input, api_error_reason)
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    if result.get("error") == "no_result" or not result.get("telegram_id"):
        increment_total_searches(user_id)
        updated_total = get_total_credits(user_id)
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Username: `@{username_input}`

🚫 No records available in database

💡 Tips:
• Check the username again
• Try another username
• Ensure the username is correct

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `0` (No deduction for no results)
💎 *Credits Left:* `{updated_total}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    telegram_id = result.get('telegram_id')
    if telegram_id and is_telegram_protected(telegram_id):
        output = f"""
🛡️ *PROTECTED TELEGRAM ID*

🔍 Username: `@{username_input}`
🆔 Telegram ID: `{telegram_id}`

This Telegram ID is protected. Details are hidden.

You can also protect your Telegram ID for ₹99!
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ Protect My Telegram", callback_data="plan_protect_telegram"))
        markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode='Markdown')
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, TELEGRAM_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_telegram_sessions_lock:
                active_telegram_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    output = format_telegram_lookup_result(result, f"@{username_input}", user_id, unlimited_active, unlimited_expiry)
    
    markup = telegram_lookup_protection_markup()
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
    
    with active_telegram_sessions_lock:
        active_telegram_sessions.discard(user_id)

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
            "payment_id": tx_code,
            "cashfree_order_id": tx_code,
            "session_id": tx_code,
            "telegram_user_id": str(telegram_user_id),
            "telegram_username": str(telegram_username or "no_username"),
            "plan_id": plan_id,
            "amount": plan["amount"],
            "credits": plan.get("credits", 0),
            "payment_source": "manual_qr",
            "payment_for": "credits" if plan_id in CREDIT_PLANS else "unlimited" if plan_id in UNLIMITED_PLANS else "protect_number" if plan_id == "protect_number" else "protect_telegram" if plan_id == "protect_telegram" else "bot_booking",
            "protected_number": protected_number,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "raw_response": {"mode": "manual_static_qr", "note": "Admin must verify manually."}
        }

        supabase.table("payment_claims").insert(payload).execute()
        return tx_code
    except Exception as e:
        print(f"Create manual payment claim error: {e}")
        return None

def fulfill_manual_claim(claim):
    try:
        telegram_user_id = claim.get("telegram_user_id")
        plan_id = claim.get("plan_id")
        plan = get_plan_config(plan_id)

        if not telegram_user_id or not plan:
            return False, "Invalid claim data"

        if plan_id in CREDIT_PLANS:
            credits = int(claim.get("credits") or plan.get("credits") or 0)
            if credits <= 0:
                return False, "No credits in this plan"
            new_total = add_credits(int(telegram_user_id), credits)
            return True, f"Added {credits} credits. New total: {new_total}"

        if plan_id in UNLIMITED_PLANS:
            ok, expiry = activate_unlimited_plan(int(telegram_user_id), plan_id)
            if not ok:
                return False, "Failed to activate unlimited plan"
            return True, f"Unlimited plan activated until {expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC"

        if plan_id == "protect_number":
            number = claim.get("protected_number")
            if not number:
                return False, "Protected number missing"
            if not is_number_protected(number):
                add_protected_number(number, int(telegram_user_id))
            return True, f"Number {number} is now protected"

        if plan_id == "protect_telegram":
            telegram_id = claim.get("protected_number")
            if not telegram_id:
                return False, "Telegram ID missing"
            if not is_telegram_protected(telegram_id):
                add_protected_telegram(telegram_id, int(telegram_user_id))
            return True, f"Telegram ID {telegram_id} is now protected"

        if plan_id == "bot_booking":
            return True, "Bot booking confirmed. Delivery: 24-48 hours after requirements."

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
                pass

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
            "status": "success",
            "updated_at": now,
            "raw_response": {"mode": "manual_static_qr", "verified_by": str(admin_id or ADMIN_ID), "verified_at": now, "detail": detail}
        }).eq("id", claim.get("id")).execute()

        telegram_user_id = int(claim.get("telegram_user_id"))
        try:
            bot.send_message(telegram_user_id, f"✅ *Payment Verified!*\n\n{detail}\n\n🧾 TX: `{tx_code}`\n\nUse /start to continue.", parse_mode="Markdown")
        except Exception:
            pass

        try:
            bot.send_message(ADMIN_CHANNEL_ID, f"✅ *MANUAL PAYMENT VERIFIED*\n━━━━━━━━━━━━━━━━\n👤 User: `{telegram_user_id}`\n📦 Plan: `{claim.get('plan_id')}`\n💰 Amount: ₹{claim.get('amount')}\n🧾 TX: `{tx_code}`", parse_mode="Markdown")
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
                pass

        if not claim_resp or not claim_resp.data:
            return False, "Transaction not found"

        claim = claim_resp.data[0]
        status = str(claim.get("status") or "").lower()
        if status == "success":
            return False, "Already verified, cannot reject"
        if status == "rejected":
            return False, "Already rejected"

        now = datetime.now(timezone.utc).isoformat()
        supabase.table("payment_claims").update({
            "status": "rejected",
            "updated_at": now,
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
                pass
        return None
    except Exception:
        return None

def payment_session_reminder_worker(chat_id, user_id, tx_code, plan_label):
    try:
        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            bot.send_message(chat_id, f"⏰ *Payment Reminder - 2 minutes left!*\n\n🧾 TX: `{tx_code}`\n\nPlease complete payment within 2 minutes.", parse_mode="Markdown")

        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            bot.send_message(chat_id, f"⚠️ *LAST CALL - 1 minute remaining!*\n\n🧾 TX: `{tx_code}`\n\nTransaction will be cancelled automatically.", parse_mode="Markdown")

        time.sleep(60)
        if get_manual_claim_status(tx_code) == "pending":
            ok, msg = manual_reject_payment(tx_code, ADMIN_ID, reason="Payment session expired - 3 minutes timeout")
            if ok:
                bot.send_message(chat_id, f"❌ *Payment Session Expired*\n\n🧾 TX: `{tx_code}`\nReason: Transaction not completed within 3 minutes.\n\nYou can create a new session by selecting the plan again.", reply_markup=credit_packs_markup(), parse_mode="Markdown")
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
        bot.send_message(chat_id, f"⏳ *Please wait {remaining} seconds* before creating another payment session.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        return
    payment_session_cooldown[user_id] = now_ts

    tx_code = create_manual_payment_claim(plan_id, user_id, username, protected_number)
    if not tx_code:
        bot.send_message(chat_id, f"❌ Could not create payment record. Contact {ADMIN_USERNAME}.", parse_mode="Markdown")
        return

    extra = f"\n📱 Number: `{protected_number}`" if protected_number else ""
    caption = f"""
💳 *Scan & Pay*
━━━━━━━━━━━━━━━━━━
💰 Amount: ₹{plan['amount']}
📦 Plan: `{plan['label']}`{extra}
🧾 TX ID: `{tx_code}`

⏰ *You have 3 minutes to complete this transaction!*

✅ Pay exactly ₹{plan['amount']} on this QR.
📩 After payment, tap below and send screenshot here.

━━━━━━━━━━━━━━━━━━
📞 Admin: {ADMIN_USERNAME}
"""

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Send Payment Screenshot", callback_data=f"submitproof_{tx_code}"))
    markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))

    qr_path = PAYMENT_QR_IMAGE
    if not os.path.isabs(qr_path):
        qr_path = os.path.join(os.getcwd(), qr_path)

    try:
        if os.path.exists(qr_path):
            with open(qr_path, "rb") as img:
                bot.send_photo(chat_id, img, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, caption + "\n⚠️ QR image missing.", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Send QR failed: {e}")
        bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")

    threading.Thread(target=payment_session_reminder_worker, args=(chat_id, user_id, tx_code, plan.get("label", plan_id)), daemon=True).start()

# ==================== ADMIN FUNCTIONS ====================
def show_admin_panel(message):
    stats = get_stats()
    admin_msg = f"""
*🛠 ADMIN PANEL*
━━━━━━━━━━━━━━━━━━
👥 Users: `{stats['total_users']}`
🔍 Searches: `{stats['total_searches']}`
💎 Credits: `{stats['total_credits']}`
💰 Revenue: ₹{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
🚫 Banned: `{stats['banned_users']}`
💾 Cache: `{stats['cache_size']}`
🛡️ Protected: `{stats['protected_count']}`
━━━━━━━━━━━━━━━━━━
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Add Credits", callback_data="admin_add"),
        InlineKeyboardButton("➖ Remove Credits", callback_data="admin_remove")
    )
    markup.add(
        InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")
    )
    markup.add(
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("🎁 Giveaway", callback_data="admin_giveaway")
    )
    markup.add(
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton("📋 Transactions", callback_data="admin_transactions")
    )
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    bot.send_message(message.chat.id, admin_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_stats(message):
    stats = get_stats()
    stats_msg = f"""
*📊 DETAILED STATS*
━━━━━━━━━━━━━━━━━━
👥 Users: `{stats['total_users']}`
🚫 Banned: `{stats['banned_users']}`
✅ Active: `{stats['total_users'] - stats['banned_users']}`
━━━━━━━━━━━━━━━━━━
💎 Total Credits: `{stats['total_credits']}`
━━━━━━━━━━━━━━━━━━
🔍 Searches: `{stats['total_searches']}`
💾 Cache: `{stats['cache_size']}`
🛡️ Protected: `{stats['protected_count']}`
━━━━━━━━━━━━━━━━━━
💰 Revenue: ₹{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
━━━━━━━━━━━━━━━━━━
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, stats_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_transactions(message):
    transactions = get_recent_transactions()
    if not transactions:
        trans_msg = "📋 *No transactions found!*"
    else:
        trans_msg = "*📋 RECENT TRANSACTIONS*\n\n"
        for trans in transactions:
            status_emoji = "✅" if trans.get('status') == "success" else "⏳" if trans.get('status') == "pending" else "❌"
            trans_msg += f"{status_emoji} `{trans.get('payment_id', '')[:20]}` | User: `{trans.get('telegram_user_id', '')}` | ₹{trans.get('amount', 0)} | {trans.get('plan_id', '')}\n"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, trans_msg, reply_markup=markup, parse_mode='Markdown')

def process_admin_add(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError("Missing values")
        target_user, target_row = resolve_user_identifier(parts[0])
        if not target_user:
            bot.reply_to(message, "❌ User not found.", parse_mode='Markdown')
            return
        value = parts[1].strip().lower()

        if value in ["u1w", "u1m"]:
            ok, new_expiry = activate_unlimited_plan(target_user, value)
            if not ok:
                bot.reply_to(message, "❌ Invalid plan.", parse_mode='Markdown')
                return
            label = UNLIMITED_PLANS[value]["label"]
            bot.reply_to(message, f"✅ Added `{label}` to `{target_user}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🚀 *Unlimited Plan Added!*\nPlan: `{label}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`", parse_mode='Markdown')
            except Exception:
                pass
            return

        credits = int(value)
        new_total = add_credits(target_user, credits)
        bot.reply_to(message, f"✅ Added {credits} credits to `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, f"✅ *{credits} credits added!*\nNew total: `{new_total}`", parse_mode='Markdown')
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Invalid format!\nCredits: `user_id/@username credits`\nUnlimited: `user_id/@username u1w/u1m`", parse_mode='Markdown')

def process_admin_remove(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError("Missing values")
        target_user, user = resolve_user_identifier(parts[0])
        if not target_user or not user:
            bot.reply_to(message, "❌ User not found.", parse_mode='Markdown')
            return
        action = parts[1].strip().lower()
        if action in ["unlimited", "deactivate", "off", "u0", "remove_unlimited"]:
            supabase.table("telegram_users").update({
                "unlimited_expiry": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", target_user).execute()
            bot.reply_to(message, f"✅ Unlimited plan deactivated for `{target_user}`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🧨 *Unlimited Plan Deactivated*\n\nYour unlimited access has been removed.", parse_mode='Markdown')
            except Exception:
                pass
            return
        credits = int(action)
        current_credits = int(user.get('credits', 0) or 0)
        new_credits = max(0, current_credits - credits)
        supabase.table("telegram_users").update({"credits": new_credits, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("telegram_user_id", target_user).execute()
        bot.reply_to(message, f"✅ Removed {credits} credits from `{target_user}`\nNew total: `{new_credits}`", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "❌ Invalid format!", parse_mode='Markdown')

def process_admin_ban(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        target_user = int(message.text.strip())
        ban_user(target_user)
        bot.reply_to(message, f"✅ Banned user `{target_user}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, "🚫 *You have been banned.* Contact support.", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_unban(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        target_user = int(message.text.strip())
        unban_user(target_user)
        bot.reply_to(message, f"✅ Unbanned user `{target_user}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, "✅ *You have been unbanned!* Use /start", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_broadcast(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    broadcast_text = (message.text or message.caption or "").strip()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Send", callback_data="broadcast_confirm"), InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    temp_data[user_id] = {'broadcast_text': broadcast_text}
    bot.reply_to(message, f"📢 *Confirm Broadcast*\n\n📝 Message:\n`{broadcast_text}`\n\nSend to all active users?", reply_markup=markup, parse_mode='Markdown')

def process_admin_giveaway(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        credits = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Give Away", callback_data="giveaway_confirm"), InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        temp_data[user_id] = {'giveaway_credits': credits}
        bot.reply_to(message, f"🎁 *Confirm Giveaway*\n\nGive `{credits}` credits to ALL users?", reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number!", parse_mode='Markdown')

def confirm_broadcast(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Broadcast cancelled.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
        return
    broadcast_text = temp_data[user_id]['broadcast_text']
    users = get_all_users()
    success = 0
    failed = 0
    bot.edit_message_text(f"📡 *Broadcasting to {len(users)} users...*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    for target_user_id in users:
        try:
            broadcast_msg = f"*📢 TRACEX BROADCAST*\n{broadcast_text}\n━━━━━━━━━━━━━━━━\n📞 Support: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"
            bot.send_message(target_user_id, broadcast_msg, parse_mode='Markdown', disable_web_page_preview=True)
            success += 1
        except Exception:
            failed += 1
        time.sleep(0.05)
    result_msg = f"✅ *Broadcast Complete!*\n✅ Sent: `{success}`\n❌ Failed: `{failed}`\n📝 Total: `{len(users)}`"
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
    del temp_data[user_id]

def confirm_giveaway(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Giveaway cancelled.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
        return
    credits = temp_data[user_id]['giveaway_credits']
    bot.edit_message_text(f"🎁 *Processing Giveaway...*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    success, failed = add_giveaway_credits(credits)
    result_msg = f"🎉 *Giveaway Complete!*\n✨ `{credits}` credits to each user!\n✅ Successful: `{success}`\n❌ Failed: `{failed}`\n💎 Total Distributed: `{success * credits}`"
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
    del temp_data[user_id]

# ==================== PROTECTION FUNCTIONS ====================
def show_protection_menu(message):
    text = f"""
🛡️ *PROTECTION SERVICES*
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹99
💬 Telegram ID Protection → ₹99

Protected data will not be shown in lookup results.
"""
    bot.send_message(message.chat.id, text, reply_markup=protection_menu_markup(), parse_mode="Markdown")

def process_protection_payment_input(message, plan_id):
    user_id = message.from_user.id
    if message.text == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_protection_input" and state.get("plan_id") == plan_id):
        return

    user_states.pop(user_id, None)
    value = str(message.text or "").strip()
    
    if plan_id == "protect_number":
        if not re.match(r'^[6-9]\d{9}$', value):
            bot.reply_to(message, "❌ *Invalid number!*\n\nEnter a 10-digit Indian mobile number.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        if is_number_protected(value):
            bot.reply_to(message, f"❌ Number `{value}` is already protected.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    elif plan_id == "protect_telegram":
        if not re.match(r'^\d{4,15}$', value):
            bot.reply_to(message, "❌ *Invalid Telegram ID!*\n\nEnter a numeric Telegram ID.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        if is_telegram_protected(value):
            bot.reply_to(message, f"❌ Telegram ID `{value}` is already protected.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    
    send_manual_qr_payment(message.chat.id, user_id, message.from_user.username or "no_username", plan_id, protected_number=value)

def show_bot_booking(message):
    booking_msg = f"""
🤖 *CUSTOM BOT BOOKING*
━━━━━━━━━━━━━━━━━━

💰 *Bot setup:* ₹399
📆 *API charges:* Monthly (separate)
🔧 *Updates:* ₹399 per update
⏰ *Delivery:* 24-48 hours

👇 Tap below to create booking payment.
{footer()}
"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("💳 Book Bot - Pay ₹399", callback_data="booking_pay"))
    markup.add(InlineKeyboardButton("👨‍💻 Contact Admin", url="https://t.me/gaurav_beniwal_0001"))
    markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
    bot.send_message(message.chat.id, booking_msg, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)

# ==================== FLASK WEBHOOK ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "TraceX Bot Running"

@app.route('/payment/success', methods=['GET'])
def payment_success():
    return """
    <html>
        <head><title>Payment Successful - TraceX</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: green;">✅ Payment Successful!</h1>
            <p>You will receive confirmation in Telegram shortly.</p>
            <p>You can close this window now.</p>
        </body>
    </html>
    """

def keep_alive():
    def run():
        port = int(os.getenv("PORT", "8080"))
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user = get_user(user_id)
    
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 You are banned.\n\nContact: {ADMIN_USERNAME}")
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
    total_searches = user.get('total_searches', 0) if user else 0
    unlimited_expiry = user.get('unlimited_expiry') if user else None
    
    unlimited_text = ""
    if unlimited_expiry:
        try:
            expiry_date = datetime.fromisoformat(str(unlimited_expiry).replace('Z', '+00:00'))
            if expiry_date > datetime.now(timezone.utc):
                unlimited_text = f"\n🚀 Unlimited Active until: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
        except:
            pass
    
    welcome_msg = f"""
🚀 *TRACEX LOOKUP*

👋 Welcome, *{first_name}*

💎 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Searches:* `{total_searches}`

━━━━━━━━━━━━━━━━

📱 Number Search → 2 Credits
💬 Telegram Search → 5 Credits

🎁 New users receive free credits.

👇 Select an option below.
{footer()}
"""
    
    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    bot.reply_to(message, "❌ Cancelled. Use /start for main menu.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')

@bot.message_handler(commands=['verify'])
def verify_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /verify TXCODE")
            return
        tx_code = parts[1].strip()
        ok, msg = manual_verify_payment(tx_code, message.from_user.id)
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
            bot.reply_to(message, "Usage: /reject TXCODE [reason]")
            return
        tx_code = parts[1].strip()
        reason = parts[2].strip() if len(parts) > 2 else "Payment not confirmed"
        ok, msg = manual_reject_payment(tx_code, message.from_user.id, reason)
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
        bot.reply_to(message, "Usage:\n/maintenance on\n/maintenance off")
        return
    mode = parts[1].lower()
    if mode == "on":
        MAINTENANCE_MODE = True
        bot.reply_to(message, "🛠 Maintenance mode ENABLED")
    elif mode == "off":
        MAINTENANCE_MODE = False
        bot.reply_to(message, "✅ Maintenance mode DISABLED")

@bot.message_handler(content_types=['photo', 'document'])
def payment_screenshot_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_payment_screenshot"):
        return

    tx_code = state.get("tx_code")
    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, f"✅ Screenshot already sent for TX `{tx_code}`.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
        return
    
    proof_forwarded_txs.add(tx_code)
    caption = f"📸 *PAYMENT SCREENSHOT*\n━━━━━━━━━━━━━━━━\n👤 User: `{user_id}`\n@ Username: @{message.from_user.username or 'no_username'}\n🧾 TX: `{tx_code}`\n\nVerify: `/verify {tx_code}`"
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ Verify", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"adminreject_{tx_code}")
    )

    try:
        try:
            bot.copy_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        except Exception:
            try:
                bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
            except Exception:
                pass
        
        bot.send_message(ADMIN_CHANNEL_ID, caption, reply_markup=admin_markup, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Screenshot sent to admin.\n\n🧾 TX: `{tx_code}`\n⏳ Wait for verification.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        print(f"Payment screenshot error: {e}")
        bot.reply_to(message, f"❌ Could not forward screenshot. Contact {ADMIN_USERNAME}", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if user and user.get('is_banned'):
        bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
        return

    if call.data == "check_join":
        if is_channel_member(user_id):
            bot.answer_callback_query(call.id, "Joined verified ✅")
            try:
                bot.edit_message_text("✅ *Joined verified!*\n\nUse /start to open bot menu.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
            except Exception:
                bot.send_message(call.message.chat.id, "✅ Joined verified! Use /start")
        else:
            bot.answer_callback_query(call.id, "Please join channel first", show_alert=True)
        return

    if not is_channel_member(user_id):
        bot.answer_callback_query(call.id, "Join channel first", show_alert=True)
        send_join_required(call.message.chat.id)
        return
    
    if call.data == "main_menu":
        try:
            bot.edit_message_text("🏠 *Main Menu*", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        except Exception:
            bot.send_message(call.message.chat.id, "🏠 *Main Menu*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "cancel":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        with active_number_sessions_lock:
            active_number_sessions.discard(user_id)
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        try:
            bot.edit_message_text("❌ Cancelled. Use /start for main menu.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Cancelled. Use /start for main menu.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Cancelled")
    
    elif call.data == "lookup":
        user_states[user_id] = "awaiting_number"
        msg = bot.send_message(call.message.chat.id, "📱 *NUMBER SEARCH*\n\nEnter a 10-digit mobile number\n\nExample:\n9876543210\n\n💎 Cost: 2 Credits\n\n❌ Use Cancel button to exit.", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "telegram_lookup":
        user_states[user_id] = "awaiting_telegram_username"
        msg = bot.send_message(call.message.chat.id, "💬 *TELEGRAM SEARCH*\n\nEnter Telegram username\n\nExamples:\n@username\nusername\n\n💎 Cost: 5 Credits\n\n❌ Use Cancel button to exit.", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_telegram_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "protection_menu":
        show_protection_menu(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data == "credits":
        total_credits = get_total_credits(user_id)
        total_searches = user.get('total_searches', 0) if user else 0
        unlimited_expiry = user.get('unlimited_expiry') if user else None
        unlimited_text = ""
        if unlimited_expiry:
            try:
                expiry_date = datetime.fromisoformat(str(unlimited_expiry).replace('Z', '+00:00'))
                if expiry_date > datetime.now(timezone.utc):
                    unlimited_text = f"\n🚀 *Unlimited Active*\n   Expires: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        
        credits_msg = f"""
*💎 MY CREDITS*
━━━━━━━━━━━━━━━━━━
💰 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Used:* `{total_searches}`
━━━━━━━━━━━━━━━━━━
*📦 CREDIT PACKS*
• 10 Credits → ₹20  
• 50 Credits → ₹70  
• 100 Credits → ₹100
*🚀 UNLIMITED PLANS*
• 7 Days → ₹200
• 30 Days → ₹500
*🛡️ PROTECTION*
• Number Protection → ₹99
• Telegram ID Protection → ₹99
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 Buy Credits", callback_data="buy"))
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        bot.edit_message_text(credits_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "buy":
        packs_msg = f"""
💎 *BUY CREDITS & PLANS*
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
• Telegram ID Protection → ₹99

━━━━━━━━━━━━━━━━━━
✅ Permanent Credits NEVER EXPIRE
✅ Manual payment verification

👇 Select your plan below
{footer()}
"""
        bot.edit_message_text(packs_msg, call.message.chat.id, call.message.message_id, reply_markup=credit_packs_markup(), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "book_bot":
        show_bot_booking(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data == "booking_pay":
        bot.answer_callback_query(call.id, "Creating booking QR... ✅")
        send_manual_qr_payment(call.message.chat.id, user_id, call.from_user.username or "no_username", "bot_booking")
    
    elif call.data.startswith("submitproof_"):
        tx_code = call.data.replace("submitproof_", "", 1)
        user_states[user_id] = {"state": "awaiting_payment_screenshot", "tx_code": tx_code}
        bot.send_message(call.message.chat.id, f"📸 *Send payment screenshot now*\n\n🧾 TX: `{tx_code}`\n\nYour screenshot will be forwarded to admin for verification.", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Now send screenshot here")
    
    elif call.data.startswith("adminverify_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        tx_code = call.data.replace("adminverify_", "", 1)
        ok, msg = manual_verify_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Verified" if ok else msg, show_alert=not ok)
    
    elif call.data.startswith("adminreject_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        tx_code = call.data.replace("adminreject_", "", 1)
        ok, msg = manual_reject_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Rejected" if ok else msg, show_alert=not ok)
    
    elif call.data.startswith("plan_"):
        plan_id = call.data.replace("plan_", "")
        
        if plan_id in ["protect_number", "protect_telegram"]:
            labels = {
                "protect_number": ("📱 *NUMBER PROTECTION*", "Enter the 10-digit mobile number you want to protect:", "Example: 9876543210"),
                "protect_telegram": ("💬 *TELEGRAM ID PROTECTION*", "Enter your numeric Telegram user ID:", "Example: 123456789")
            }
            title, prompt, example = labels[plan_id]
            user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
            msg = bot.send_message(call.message.chat.id, f"{title}\n\n{prompt}\n\n{example}\n\n💰 Price: ₹99\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_protection_payment_input, plan_id)
            bot.answer_callback_query(call.id)
            return
        
        bot.answer_callback_query(call.id, "Sending QR... ✅")
        send_manual_qr_payment(call.message.chat.id, user_id, call.from_user.username or "no_username", plan_id)
    
    elif call.data in ["admin_add", "admin_remove", "admin_ban", "admin_unban", "admin_broadcast", "admin_stats", "admin_transactions", "admin_back", "admin_giveaway"]:
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        
        if call.data == "admin_add":
            user_states[user_id] = "admin_add"
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS / UNLIMITED*\n\nCredits format:\n`user_id credits`\nExample: `123456789 50`\n\nUnlimited format:\n`user_id u1w` / `user_id u1m`\nExample: `123456789 u1w`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE CREDITS / DEACTIVATE UNLIMITED*\n\nRemove credits:\n`user_id_or_username credits`\nExample: `@username 10`\n\nDeactivate unlimited:\n`user_id_or_username unlimited`\nExample: `@username unlimited`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_remove)
        elif call.data == "admin_ban":
            user_states[user_id] = "admin_ban"
            msg = bot.send_message(call.message.chat.id, "🚫 *BAN USER*\n\nEnter user ID to ban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_ban)
        elif call.data == "admin_unban":
            user_states[user_id] = "admin_unban"
            msg = bot.send_message(call.message.chat.id, "✅ *UNBAN USER*\n\nEnter user ID to unban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_unban)
        elif call.data == "admin_broadcast":
            user_states[user_id] = "admin_broadcast"
            msg = bot.send_message(call.message.chat.id, "📢 *BROADCAST*\n\nSend your broadcast message below:\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_broadcast)
        elif call.data == "admin_giveaway":
            user_states[user_id] = "admin_giveaway"
            msg = bot.send_message(call.message.chat.id, "🎁 *GIVEAWAY CREDITS*\n\nEnter number of credits to give to ALL users:\n\nExample: `50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_giveaway)
        elif call.data == "admin_stats":
            show_admin_stats(call.message)
        elif call.data == "admin_transactions":
            show_admin_transactions(call.message)
        elif call.data == "admin_back":
            show_admin_panel(call.message)
        elif call.data == "admin":
            show_admin_panel(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data in ["broadcast_confirm", "giveaway_confirm"]:
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        if call.data == "broadcast_confirm":
            confirm_broadcast(call)
        else:
            confirm_giveaway(call)

# ==================== DAILY TASKS ====================
def record_search_for_daily_report(user_id, username, first_name, query_value, found=True, lookup_type="number", credits_used=0):
    try:
        key = str(user_id)
        with daily_stats_lock:
            row = daily_search_stats.setdefault(key, {
                "user_id": user_id, "username": username or "no_username",
                "first_name": first_name or "User", "searches": 0,
                "number_searches": 0, "telegram_searches": 0, "credits_used": 0,
                "found": 0, "not_found": 0, "last_query": ""
            })
            row["searches"] += 1
            row["credits_used"] += int(credits_used or 0)
            if lookup_type == "telegram":
                row["telegram_searches"] = row.get("telegram_searches", 0) + 1
            else:
                row["number_searches"] += 1
            if found:
                row["found"] += 1
            else:
                row["not_found"] += 1
    except Exception as e:
        print(f"Daily report record error: {e}")

def build_daily_report_text(stats_snapshot):
    total_searches = sum(v.get("searches", 0) for v in stats_snapshot.values())
    total_users = len(stats_snapshot)
    found = sum(v.get("found", 0) for v in stats_snapshot.values())
    not_found = sum(v.get("not_found", 0) for v in stats_snapshot.values())
    number_searches = sum(v.get("number_searches", 0) for v in stats_snapshot.values())
    telegram_searches = sum(v.get("telegram_searches", 0) for v in stats_snapshot.values())
    credits_used = sum(v.get("credits_used", 0) for v in stats_snapshot.values())
    top = sorted(stats_snapshot.values(), key=lambda x: x.get("searches", 0), reverse=True)[:10]

    lines = [
        "📊 *TRACEX 24H SEARCH REPORT*",
        "━━━━━━━━━━━━━━━━",
        f"🕕 Report Time: `{datetime.now(IST).strftime('%Y-%m-%d 06:00 IST')}`",
        f"👥 Users Searched: `{total_users}`",
        f"🔍 Total Lookups: `{total_searches}`",
        f"📱 Number Lookups: `{number_searches}`",
        f"💬 Telegram Lookups: `{telegram_searches}`",
        f"💎 Credits Used: `{credits_used}`",
        f"✅ Found: `{found}`",
        f"❌ No Data: `{not_found}`",
        "", "🏆 *TOP SEARCHERS*"
    ]
    if not top:
        lines.append("No searches in last 24 hours.")
    else:
        for i, row in enumerate(top, 1):
            uname = row.get("username") or "no_username"
            display = f"@{uname}" if uname != "no_username" else row.get("first_name", "User")
            lines.append(f"{i}. {display} | ID `{row.get('user_id')}` | `{row.get('searches', 0)}` lookups")
    lines.append("━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def send_daily_search_report_loop():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_seconds = max(60, int((target - now).total_seconds()))
            time.sleep(sleep_seconds)
            with daily_stats_lock:
                snapshot = dict(daily_search_stats)
                daily_search_stats.clear()
            bot.send_message(ADMIN_CHANNEL_ID, build_daily_report_text(snapshot), parse_mode="Markdown")
        except Exception as e:
            print(f"Daily report loop error: {e}")
            time.sleep(300)

# ==================== START BOT ====================
if __name__ == "__main__":
    print("=" * 50)
    print(f"TraceX Lookup v{BOT_VERSION} is starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Updated Pricing: Number = {NUMBER_LOOKUP_COST} credits, Telegram = {TELEGRAM_LOOKUP_COST} credits")
    print(f"Unlimited Plans: 7 Days = ₹200, 30 Days = ₹500")
    print("=" * 50)
    
    keep_alive()
    print("✅ Flask server started")
    
    threading.Thread(target=send_daily_search_report_loop, daemon=True).start()
    print("✅ Daily report scheduler started")
    
    print("✅ Bot is running!")
    
    def signal_handler(sig, frame):
        print("\n🛑 Bot stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"remove_webhook warning: {e}")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)