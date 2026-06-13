"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 6.1.0 - Updated Pricing & Removed Auto-Delete
"""

import os
import sys

# Friendly dependency check for Render/Termux
def _require_package(import_name, pip_name=None):
    try:
        return __import__(import_name)
    except ImportError:
        name = pip_name or import_name
        print(f"❌ Missing dependency: {name}")
        print(f"Install it with: pip install {name}")
        raise

telebot = _require_package("telebot", "pyTelegramBotAPI")
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
requests = _require_package("requests", "requests")
import time
import re
from datetime import datetime, timedelta, timezone
import threading
import signal
import uuid
import hmac
import hashlib
import json
from flask import Flask, request, jsonify

# Lightweight Supabase REST client
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
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY are required")
        url = f"{self.client.url}/rest/v1/{self.table}"
        headers = dict(self.client.headers)
        headers.update(self.headers)
        response = requests.request(
            self.method,
            url,
            params=self.params,
            json=self.payload,
            headers=headers,
            timeout=30,
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
                count = None
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

Client = _SupabaseLiteClient

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8525568503:AAHjydzj4bXdjVcS9c5jiL3CghFDfBePXXw"
ADMIN_ID = 7850023357
ADMIN_CHANNEL_ID = -1003743686626
ADMIN_USERNAME = r"@gaurav\_beniwal\_0001"
BOT_VERSION = "6.1.0"

# Lookup API Configuration
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/api/v1/lookup.php").strip()
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "TVB_SGL_053B3AA6").strip()
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number").strip()

# API Endpoints (Hardcoded)
BASE_API_URL = "https://exploitsindia.site//hdhddhjdjddjdjdjdndnddnnccndndhejdmdnnd"
TELEGRAM_LOOKUP_API_URL = f"{BASE_API_URL}/telegram.php"
IDENTITY_LOOKUP_API_URL = f"{BASE_API_URL}/aadhar.php"
IFSC_LOOKUP_API_URL = f"{BASE_API_URL}/ifsc.php"

# Updated Costs (Same as before)
NUMBER_LOOKUP_COST = 5
TELEGRAM_LOOKUP_COST = 12
IDENTITY_LOOKUP_COST = 15
IFSC_LOOKUP_COST = 20

# Updated Plan Pricing
PLAN_CONFIG = {
    "c40": {"amount": 20, "credits": 40, "unlimited_minutes": 0, "payment_for": "credits", "label": "40 Credits - ₹20"},
    "c120": {"amount": 50, "credits": 120, "unlimited_minutes": 0, "payment_for": "credits", "label": "120 Credits - ₹50"},
    "c400": {"amount": 100, "credits": 400, "unlimited_minutes": 0, "payment_for": "credits", "label": "400 Credits - ₹100"},
    "u1d": {"amount": 50, "credits": 0, "unlimited_minutes": 1440, "payment_for": "unlimited", "label": "1 Day Unlimited - ₹50"},
    "u1w": {"amount": 250, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited - ₹250"},
    "u1m": {"amount": 800, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited - ₹800"},
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection - ₹99"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Number Protection - ₹99"},
    "bot_booking": {"amount": 999, "credits": 0, "unlimited_minutes": 0, "payment_for": "bot_booking", "label": "Custom Bot Booking - ₹999"},
}

MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900
PROTECT_NUMBER_PRICE = 99
PROTECT_TELEGRAM_PRICE = 99

COOLDOWN_SECONDS = 3
# AUTO_DELETE_SECONDS removed - messages will not auto-delete
GROUP_LINK = "https://t.me/Gaurav_beni_0001"
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Gaurav_beni_0001")
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")

GENERIC_API_ERROR_MESSAGE = "❌ *API Error*\n\n💎 Credits NOT deducted"

# Branding patterns to remove
BRANDING_PATTERNS = [
    r'💳 BUY API\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'🆘 SUPPORT\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'BUY API\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'SUPPORT\s*:\s*@[a-zA-Z0-9_]+\s*',
]

def remove_branding(text):
    """Remove branding lines from API response"""
    if not text:
        return text
    for pattern in BRANDING_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def show_api_error(chat_id, message_id, lookup_type="api"):
    """Show only a clean API error to users"""
    try:
        bot.edit_message_text(GENERIC_API_ERROR_MESSAGE, chat_id, message_id, parse_mode="Markdown")
    except Exception as edit_error:
        print(f"Failed to show generic API error for {lookup_type}: {edit_error}")

def call_generic_api(url, params, lookup_type="api"):
    """Generic API caller for all endpoints"""
    try:
        print(f"[{lookup_type.upper()} API] Calling: {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/6.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        print(f"[{lookup_type.upper()} API] Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return None, f"http_{response.status_code}"
        
        html_content = response.text
        print(f"[{lookup_type.upper()} API] Response length: {len(html_content)}")
        
        cleaned_content = remove_branding(html_content)
        
        no_data_markers = [
            "no data found", "not found", "no records", "no record",
            "no result", "no results", "data not found", "record not found",
            "invalid", "error"
        ]
        lower_content = cleaned_content.lower()
        if any(marker in lower_content for marker in no_data_markers):
            return {"error": "no_result"}, None
        
        if cleaned_content and len(cleaned_content) > 50:
            return {"html_content": cleaned_content, "raw_html": html_content}, None
        else:
            return {"error": "no_result"}, None
            
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except Exception as e:
        print(f"[{lookup_type.upper()} API] Exception: {e}")
        return None, f"exception_{e}"

def call_telegram_lookup_api(username):
    """Call Telegram lookup API"""
    if not username.startswith('@'):
        username = '@' + username
    url = TELEGRAM_LOOKUP_API_URL
    params = {'exploits': username}
    return call_generic_api(url, params, "telegram")

def call_identity_lookup_api(aadhar_number):
    """Call Identity/Aadhar lookup API"""
    url = IDENTITY_LOOKUP_API_URL
    params = {'exploits': aadhar_number}
    return call_generic_api(url, params, "identity")

def call_ifsc_lookup_api(ifsc_code):
    """Call IFSC lookup API"""
    url = IFSC_LOOKUP_API_URL
    params = {'exploits': ifsc_code}
    return call_generic_api(url, params, "ifsc")

def notify_admin_api_issue(lookup_type, query, error_reason):
    """Send compact admin-only debug alert"""
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ *API TEMP ISSUE*\n\nType: `{lookup_type}`\nQuery: `{query}`\nReason: `{str(error_reason)[:500]}`\n\nUser credits were not deducted.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Admin API issue notify failed: {e}")

def split_long_text(text, limit=TELEGRAM_SAFE_LIMIT):
    """Split long Telegram text safely"""
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
    """Edit or send long message - NO AUTO DELETE"""
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
        except Exception as send_error:
            print(f"Long message send error: {send_error}")
    return sent_messages

# ==================== KEYBOARD MARKUP ====================
def get_main_keyboard():
    """Create main menu keyboard buttons"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("📱 NUMBER LOOKUP"),
        KeyboardButton("💬 TELEGRAM LOOKUP")
    )
    keyboard.add(
        KeyboardButton("🆔 IDENTITY LOOKUP"),
        KeyboardButton("🏦 IFSC LOOKUP")
    )
    keyboard.add(
        KeyboardButton("💎 MY CREDITS"),
        KeyboardButton("🛒 BUY CREDITS")
    )
    keyboard.add(
        KeyboardButton("🛡️ PROTECTION"),
        KeyboardButton("🤖 BOOK A BOT")
    )
    return keyboard

def get_cancel_keyboard():
    """Cancel button keyboard"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton("❌ CANCEL"))
    return keyboard

def get_back_keyboard():
    """Back to main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton("🏠 MAIN MENU"))
    return keyboard

def universal_markup(back=False, buy=False, join=False, admin=False):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    if buy:
        buttons.append(InlineKeyboardButton("💎 BUY CREDITS", callback_data="buy"))
    if join:
        buttons.append(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
    if admin:
        buttons.append(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"))
    if back:
        buttons.append(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    for btn in buttons:
        markup.add(btn)
    return markup

def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 Website: {WEBSITE_URL}\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    """Send important admin alerts"""
    sent = False
    try:
        bot.send_message(ADMIN_CHANNEL_ID, text, reply_markup=reply_markup, parse_mode=parse_mode)
        sent = True
    except Exception as e:
        print(f"Admin channel alert failed: {e}")
    if not sent:
        try:
            bot.send_message(ADMIN_ID, "⚠️ Admin group delivery failed, fallback DM:\n\n" + text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            print(f"Admin DM fallback failed: {e}")
    return sent

def header(title, emoji="🚀"):
    return f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━\n"

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
    except Exception as e:
        print(f"Channel membership check error for {user_id}: {e}")
        return False

def send_join_required(chat_id):
    bot.send_message(
        chat_id,
        f"🔒 *Join Required*\n━━━━━━━━━━━━━━━━\n\nBot use karne ke liye pehle official channel join karo.\n\n📢 Channel: {GROUP_LINK}\n\nJoin karne ke baad `✅ I HAVE JOINED` dabao.",
        reply_markup=join_required_markup(),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    return markup

def credit_packs_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 40 Credits - ₹20", callback_data="plan_c40"),
        InlineKeyboardButton("💰 120 Credits - ₹50", callback_data="plan_c120"),
        InlineKeyboardButton("💰 400 Credits - ₹100", callback_data="plan_c400")
    )
    markup.add(
        InlineKeyboardButton("🚀 1 Day Unlimited - ₹50", callback_data="plan_u1d"),
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹250", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹800", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number")
    )
    markup.add(
        InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    return markup

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Cashfree Configuration
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY")
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "TEST")
RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "https://your-app.onrender.com")

CASHFREE_API_BASE = "https://sandbox.cashfree.com/pg" if CASHFREE_ENV == "TEST" else "https://api.cashfree.com/pg"
CASHFREE_API_VERSION = "2023-08-01"

def validate_startup_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY):
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
    if missing:
        print("❌ Missing required environment variables: " + ", ".join(missing))
        print("Set them in Render/Termux before running the bot.")
        sys.exit(1)

validate_startup_config()
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True)

SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
if not SUPABASE_SERVICE_ROLE_KEY:
    print("⚠️ SUPABASE_SERVICE_ROLE_KEY missing, RLS may block backend writes")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# State Management
user_states = {}
user_cooldown = {}
temp_data = {}
payment_session_cooldown = {}
PAYMENT_SESSION_COOLDOWN_SECONDS = 60
active_sessions = {}
active_sessions_lock = threading.Lock()
proof_forwarded_txs = set()

daily_search_stats = {}
daily_stats_lock = threading.Lock()
IST = timezone(timedelta(hours=5, minutes=30))

MAINTENANCE_MODE = False

# ==================== MAINTENANCE MODE ====================
MAINTENANCE_MESSAGE = """
⚠️ BOT UNDER MAINTENANCE
🛠️ TraceX is currently under maintenance and upgrades.
⏰ Please try again later.
📢 Till then, join our official channel for updates and announcements: https://t.me/Gaurav_beni_0001
🙏 Thanks for your patience.
"""

@bot.message_handler(func=lambda message: MAINTENANCE_MODE and message.from_user.id != ADMIN_ID)
def maintenance_handler(message):
    bot.reply_to(message, MAINTENANCE_MESSAGE, parse_mode='Markdown')

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

def normalize_aadhar(value):
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    return digits if re.match(r"^\d{12}$", digits) else None

def normalize_ifsc(value):
    raw = str(value or "").strip().upper()
    return raw if re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", raw) else None

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
            return result.data[0].get('credits', amount) if result.data else 0
        else:
            current_credits = response.data[0].get('credits', 0)
            new_credits = current_credits + amount
            supabase.table("telegram_users").update({
                "credits": new_credits,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
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
                expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
                if expiry_date > datetime.now(timezone.utc):
                    return True
            except Exception:
                pass
        current_credits = int(user.get('credits', 0))
        if current_credits < amount:
            return False
        new_credits = current_credits - amount
        supabase.table("telegram_users").update({
            "credits": new_credits,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        return True
    except Exception as e:
        print(f"Deduct credits error: {e}")
        return False

def get_total_credits(telegram_user_id):
    user = get_user(telegram_user_id)
    return int(user.get('credits', 0)) if user else 0

def increment_total_searches(telegram_user_id):
    try:
        user = get_user(telegram_user_id)
        current = int(user.get('total_searches', 0)) if user else 0
        supabase.table("telegram_users").update({
            "total_searches": current + 1,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
    except Exception as e:
        print(f"Increment searches error: {e}")

def get_active_unlimited(user):
    if not user:
        return False, None
    expiry = user.get("unlimited_expiry")
    if not expiry:
        return False, None
    try:
        dt = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
        if dt > datetime.now(timezone.utc):
            return True, dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass
    return False, None

def is_number_protected(mobile):
    try:
        res = supabase.table("protected_numbers").select("mobile").eq("mobile", str(mobile)).execute()
        return bool(res.data)
    except Exception:
        return False

def is_telegram_protected(tg_id):
    try:
        res = supabase.table("protected_telegram_ids").select("telegram_id").eq("telegram_id", str(tg_id)).execute()
        return bool(res.data)
    except Exception:
        return False

def add_protected_number(mobile, name="Protected"):
    try:
        supabase.table("protected_numbers").insert({"mobile": str(mobile), "name": name, "created_at": datetime.now(timezone.utc).isoformat()}).execute()
        return True
    except Exception:
        return False

def add_protected_telegram_id(tg_id, username="Protected"):
    try:
        supabase.table("protected_telegram_ids").insert({"telegram_id": str(tg_id), "username": username, "created_at": datetime.now(timezone.utc).isoformat()}).execute()
        return True
    except Exception:
        return False

def get_plan_config(plan_id):
    clean = str(plan_id or "").replace("plan_", "")
    return PLAN_CONFIG.get(clean)

def record_search_for_daily_report(user_id, username, first_name, query, found=False, lookup_type="number", credits_used=0):
    with daily_stats_lock:
        if lookup_type not in daily_search_stats:
            daily_search_stats[lookup_type] = []
        daily_search_stats[lookup_type].append({
            "timestamp": datetime.now(IST).isoformat(),
            "user_id": user_id,
            "username": f"@{username}" if username else str(first_name or "User"),
            "query": query,
            "found": found,
            "credits_used": credits_used
        })

# ==================== LOOKUP PROCESSORS ====================
def process_number_lookup(message):
    user_id = message.from_user.id
    raw_phone = str(message.text or "").strip()

    if raw_phone == "❌ CANCEL" or raw_phone == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_number":
        return

    user_states.pop(user_id, None)
    phone = normalize_indian_mobile(raw_phone)

    if not phone:
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter Indian mobile number.\nExamples: `9876543210` or `+919876543210`", 
                    reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < NUMBER_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Number Lookup costs `{NUMBER_LOOKUP_COST}` credits.", 
                    reply_markup=universal_markup(buy=True), parse_mode='Markdown')
        return

    if is_number_protected(phone):
        bot.reply_to(message, f"""
🛡️ *PROTECTED NUMBER*

📱 `{phone}`

This number is protected. Details are hidden.
""", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching...*", parse_mode='Markdown')

    params = {"key": LOOKUP_API_KEY, "service": LOOKUP_API_SERVICE, "number": phone}
    result, api_error = call_unstable_json_api(params, lookup_type="number")

    if not result or not has_valid_number_results(result):
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number: `{phone}`

🚫 No records available in database

💎 *Credits Used:* `0`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=False, lookup_type="number", credits_used=0)
        return

    if not unlimited_active:
        deduct_credits(user_id, NUMBER_LOOKUP_COST)
    increment_total_searches(user_id)

    output = f"""
🔍 *NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

📱 Number: `{phone}`
"""
    if "results" in result:
        res_block = result["results"]
        if isinstance(res_block, dict):
            for k, v in res_block.items():
                if isinstance(v, dict):
                    output += f"""
👤 Name: `{v.get('name', 'N/A')}`
📡 Operator: `{v.get('operator', v.get('carrier', 'N/A'))}`
📍 Circle: `{v.get('circle', v.get('state', 'N/A'))}`
"""
                    break

    output += f"""
━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{NUMBER_LOOKUP_COST if not unlimited_active else 0}`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
    bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)

def process_telegram_lookup(message):
    user_id = message.from_user.id
    username_input = str(message.text or "").strip()

    if username_input == "❌ CANCEL" or username_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_telegram_username":
        return

    user_states.pop(user_id, None)

    if not username_input.startswith('@'):
        username_input = '@' + username_input

    if not re.match(r'^@?[a-zA-Z0-9_]{5,32}$', username_input[1:]):
        bot.reply_to(message, "❌ *Invalid Telegram Username!*\n\nExamples: `@username` or `username`", 
                    reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < TELEGRAM_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Telegram Lookup costs `{TELEGRAM_LOOKUP_COST}` credits.", 
                    reply_markup=universal_markup(buy=True), parse_mode='Markdown')
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Telegram...*", parse_mode='Markdown')

    result, api_error = call_telegram_lookup_api(username_input)

    if not result or result.get("error") == "no_result":
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Username: `{username_input}`

🚫 No records available in database

💎 *Credits Used:* `0`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=0)
        return

    if not unlimited_active:
        deduct_credits(user_id, TELEGRAM_LOOKUP_COST)
    increment_total_searches(user_id)

    html_content = result.get("html_content", "")
    
    tg_id_match = re.search(r'🆔 Telegram ID:\s*<code>(\d+)</code>', html_content)
    phone_match = re.search(r'📱 Phone Number:\s*<code>(\d+)</code>', html_content)
    country_match = re.search(r'🌍 Country:\s*([A-Za-z\s]+)', html_content)
    cc_match = re.search(r'📞 Country Code:\s*\+(\d+)', html_content)

    output = f"""
🔍 *TELEGRAM LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lookup Result for: `{username_input}`
────────────────────────

👥 Username: `{username_input}`
🆔 Telegram ID: `{tg_id_match.group(1) if tg_id_match else 'N/A'}`
📱 Phone Number: `{phone_match.group(1) if phone_match else 'N/A'}`
🌍 Country: `{country_match.group(1).strip() if country_match else 'N/A'}`
📞 Country Code: `{'+' + cc_match.group(1) if cc_match else 'N/A'}`

────────────────────────
💎 *Credits Used:* `{TELEGRAM_LOOKUP_COST if not unlimited_active else 0}`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
    bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=True, lookup_type="telegram", credits_used=TELEGRAM_LOOKUP_COST if not unlimited_active else 0)

def process_identity_lookup(message):
    user_id = message.from_user.id
    aadhar_input = str(message.text or "").strip()

    if aadhar_input == "❌ CANCEL" or aadhar_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_identity":
        return

    user_states.pop(user_id, None)
    aadhar = normalize_aadhar(aadhar_input)

    if not aadhar:
        bot.reply_to(message, "❌ *Invalid Aadhar Number!*\n\nEnter 12-digit Aadhar number.\nExample: `962397300673`", 
                    reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < IDENTITY_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Identity Lookup costs `{IDENTITY_LOOKUP_COST}` credits.", 
                    reply_markup=universal_markup(buy=True), parse_mode='Markdown')
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Identity Records...*", parse_mode='Markdown')

    result, api_error = call_identity_lookup_api(aadhar)

    if not result or result.get("error") == "no_result":
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🆔 Aadhar: `{aadhar}`

🚫 No records available in database

💎 *Credits Used:* `0`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, aadhar, found=False, lookup_type="identity", credits_used=0)
        return

    if not unlimited_active:
        deduct_credits(user_id, IDENTITY_LOOKUP_COST)
    increment_total_searches(user_id)

    html_content = result.get("html_content", "")
    
    output = f"""
🆔 *IDENTITY LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

{html_content}

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{IDENTITY_LOOKUP_COST if not unlimited_active else 0}`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
    bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, aadhar, found=True, lookup_type="identity", credits_used=IDENTITY_LOOKUP_COST if not unlimited_active else 0)

def process_ifsc_lookup(message):
    user_id = message.from_user.id
    ifsc_input = str(message.text or "").strip().upper()

    if ifsc_input == "❌ CANCEL" or ifsc_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_ifsc":
        return

    user_states.pop(user_id, None)
    ifsc = normalize_ifsc(ifsc_input)

    if not ifsc:
        bot.reply_to(message, "❌ *Invalid IFSC Code!*\n\nEnter valid IFSC code.\nExample: `HDFC0001325`", 
                    reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    if total_credits < IFSC_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* IFSC Lookup costs `{IFSC_LOOKUP_COST}` credits.", 
                    reply_markup=universal_markup(buy=True), parse_mode='Markdown')
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Bank Details...*", parse_mode='Markdown')

    result, api_error = call_ifsc_lookup_api(ifsc)

    if not result or result.get("error") == "no_result":
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🏦 IFSC Code: `{ifsc}`

🚫 No records available in database

💎 *Credits Used:* `0`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, ifsc, found=False, lookup_type="ifsc", credits_used=0)
        return

    if not unlimited_active:
        deduct_credits(user_id, IFSC_LOOKUP_COST)
    increment_total_searches(user_id)

    html_content = result.get("html_content", "")
    
    output = f"""
🏦 *IFSC LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

{html_content}

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{IFSC_LOOKUP_COST if not unlimited_active else 0}`
💎 *Credits Left:* `{get_total_credits(user_id)}`
{footer()}
"""
    bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, ifsc, found=True, lookup_type="ifsc", credits_used=IFSC_LOOKUP_COST if not unlimited_active else 0)

# ==================== API CALLER FOR NUMBER LOOKUP ====================
def call_unstable_json_api(params, lookup_type="number", max_retries=5, timeout=30):
    base_url = str(LOOKUP_API_URL or "").strip()
    clean_params = {str(k): str(v).strip() for k, v in (params or {}).items() if v is not None}

    headers_attempts = [
        {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/6.1",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        },
        {
            "User-Agent": "python-requests TraceXBot/6.1",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        },
    ]

    last_error = "unknown"
    for attempt in range(1, int(max_retries or 5) + 1):
        headers = headers_attempts[(attempt - 1) % len(headers_attempts)]
        try:
            response = requests.get(base_url, params=clean_params, headers=headers, timeout=timeout)
            raw_preview = (response.text or "")[:500].replace("\n", " ")

            print(f"[{lookup_type.upper()} API] Try {attempt}/{max_retries} | HTTP {response.status_code}")

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
            except Exception as json_error:
                last_error = f"json_parse_failed_{json_error}"
                time.sleep(min(2 * attempt, 8))
                continue

            if not isinstance(data, dict):
                last_error = "json_not_object"
                time.sleep(min(2 * attempt, 8))
                continue

            return data, None

        except requests.exceptions.Timeout:
            last_error = "timeout"
            print(f"[{lookup_type.upper()} API] Timeout on try {attempt}")
            time.sleep(min(2 * attempt, 8))
        except requests.exceptions.ConnectionError as conn_error:
            last_error = f"connection_error_{conn_error}"
            print(f"[{lookup_type.upper()} API] Connection error on try {attempt}")
            time.sleep(min(2 * attempt, 8))
        except Exception as api_error:
            last_error = f"exception_{api_error}"
            print(f"[{lookup_type.upper()} API] Error on try {attempt}")
            time.sleep(min(2 * attempt, 8))

    print(f"[{lookup_type.upper()} API] FINAL FAILED after {max_retries} tries: {last_error}")
    return None, last_error

def has_valid_number_results(result):
    if not isinstance(result, dict):
        return False
    api_results = result.get("results")
    if isinstance(api_results, dict):
        return any(isinstance(v, dict) for v in api_results.values())
    if isinstance(api_results, list):
        return any(isinstance(v, dict) for v in api_results)
    return ("name" in result or "mobile" in result)

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start', 'menu'])
def start_handler(message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        return
    user_id = message.from_user.id
    user_states.pop(user_id, None)

    if not is_channel_member(user_id):
        send_join_required(message.chat.id)
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)

    welcome = header("TRACEX PLATFORM", "🔥")
    welcome += f"Welcome *{message.from_user.first_name or 'User'}*!\n\n"
    welcome += f"💎 Credits: `{total_credits}`\n"
    if unlimited_active:
        welcome += f"🚀 Unlimited Active until `{unlimited_expiry[:16]}`\n"
    welcome += f"🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`\n\n"
    welcome += "Select an option from the buttons below:"
    welcome += footer()

    bot.send_message(message.chat.id, welcome, reply_markup=get_main_keyboard(), parse_mode='Markdown', disable_web_page_preview=True)

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    bot.reply_to(message, "❌ Cancelled. Use /start for main menu.", reply_markup=get_main_keyboard(), parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()

    if MAINTENANCE_MODE and user_id != ADMIN_ID:
        bot.reply_to(message, MAINTENANCE_MESSAGE, parse_mode='Markdown')
        return

    if not is_channel_member(user_id) and user_id != ADMIN_ID:
        send_join_required(message.chat.id)
        return

    if user_states.get(user_id) == "awaiting_number":
        process_number_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_telegram_username":
        process_telegram_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_identity":
        process_identity_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_ifsc":
        process_ifsc_lookup(message)
        return

    if text == "📱 NUMBER LOOKUP":
        user_states[user_id] = "awaiting_number"
        bot.reply_to(message, "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\n💎 Cost: `5 credits`\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "💬 TELEGRAM LOOKUP":
        user_states[user_id] = "awaiting_telegram_username"
        bot.reply_to(message, "💬 *Enter Telegram Username:*\n\n`Example: @username`\n\n💎 Cost: `12 credits`\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🆔 IDENTITY LOOKUP":
        user_states[user_id] = "awaiting_identity"
        bot.reply_to(message, "🆔 *Enter 12-digit Aadhar Number:*\n\n`Example: 962397300673`\n\n💎 Cost: `15 credits`\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🏦 IFSC LOOKUP":
        user_states[user_id] = "awaiting_ifsc"
        bot.reply_to(message, "🏦 *Enter IFSC Code:*\n\n`Example: HDFC0001325`\n\n💎 Cost: `20 credits`\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "💎 MY CREDITS":
        user = get_user(user_id)
        total_credits = get_total_credits(user_id)
        unlimited_active, unlimited_expiry = get_active_unlimited(user)
        
        info = header("CREDITS", "💎")
        info += f"User ID: `{user_id}`\n"
        info += f"Credits: `{total_credits}`\n"
        if unlimited_active:
            info += f"🚀 Unlimited Active until `{unlimited_expiry[:16]}`\n"
        info += f"Total Searches: `{user.get('total_searches', 0) if user else 0}`\n"
        info += footer()
        bot.reply_to(message, info, reply_markup=get_back_keyboard(), parse_mode='Markdown')
    
    elif text == "🛒 BUY CREDITS":
        packs_msg = f"""
💎 *CREDIT STORE*
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS*
• 40 Credits → ₹20  
• 120 Credits → ₹50
• 400 Credits → ₹100

🚀 *UNLIMITED PLANS*
• 1 Day Unlimited → ₹50
• 7 Days Unlimited → ₹250
• 30 Days Unlimited → ₹800

🛡️ *PROTECTION*
• Number Protection → ₹99
• Telegram Protection → ₹99

{footer()}
"""
        bot.reply_to(message, packs_msg, reply_markup=credit_packs_markup(), parse_mode='Markdown')
    
    elif text == "🛡️ PROTECTION":
        prot_msg = f"""
🛡️ *PROTECTION SERVICES*
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹99
💬 Telegram Protection → ₹99

Protected data will not be shown in lookup results.

{footer()}
"""
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("📱 PROTECT NUMBER - ₹99", callback_data="plan_protect_number"))
        markup.add(InlineKeyboardButton("💬 PROTECT TELEGRAM - ₹99", callback_data="plan_protect_telegram"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.reply_to(message, prot_msg, reply_markup=markup, parse_mode='Markdown')
    
    elif text == "🤖 BOOK A BOT":
        booking_msg = f"""
🤖 *CUSTOM BOT BOOKING*
━━━━━━━━━━━━━━━━━━

💰 Setup: ₹999
📆 API charges separate
⏰ Delivery: 24-48 hours

👇 Tap below to create payment session.

{footer()}
"""
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("💳 BOOK BOT - ₹999", callback_data="booking_pay"))
        markup.add(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.reply_to(message, booking_msg, reply_markup=markup, parse_mode='Markdown')
    
    elif text == "🏠 MAIN MENU" or text == "/start":
        user_states.pop(user_id, None)
        start_handler(message)
    
    elif text == "❌ CANCEL":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    
    else:
        bot.reply_to(message, "❌ Invalid option! Use the buttons below:", reply_markup=get_main_keyboard(), parse_mode='Markdown')

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    action = str(call.data)

    if MAINTENANCE_MODE and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Bot under maintenance 🛠️", show_alert=True)
        return

    if not is_channel_member(user_id) and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Join channel first", show_alert=True)
        send_join_required(call.message.chat.id)
        return

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if action == "main_menu":
        user_states.pop(user_id, None)
        user = get_user(user_id)
        total_credits = get_total_credits(user_id)
        unlimited_active, unlimited_expiry = get_active_unlimited(user)

        welcome = header("TRACEX PLATFORM", "🔥")
        welcome += f"Welcome *{call.from_user.first_name or 'User'}*!\n\n"
        welcome += f"💎 Credits: `{total_credits}`\n"
        if unlimited_active:
            welcome += f"🚀 Unlimited Active until `{unlimited_expiry[:16]}`\n"
        welcome += f"🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`\n\n"
        welcome += "Select an option from the buttons below:"
        welcome += footer()

        try:
            bot.edit_message_text(welcome, call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
            bot.send_message(call.message.chat.id, "Use the buttons below:", reply_markup=get_main_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, welcome, reply_markup=get_main_keyboard(), parse_mode='Markdown')

    elif action == "cancel":
        user_states.pop(user_id, None)
        try:
            bot.edit_message_text("❌ Cancelled.", call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "Use /start for main menu.", reply_markup=get_main_keyboard())
        except Exception:
            pass

    elif action == "check_join":
        if is_channel_member(user_id):
            bot.send_message(call.message.chat.id, "✅ Membership confirmed! Use /start to open menu.", reply_markup=get_main_keyboard())
        else:
            bot.answer_callback_query(call.id, "Please join channel first", show_alert=True)

    elif action == "buy":
        packs_msg = f"""
💎 *CREDIT STORE*
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS*
• 40 Credits → ₹20  
• 120 Credits → ₹50
• 400 Credits → ₹100

🚀 *UNLIMITED PLANS*
• 1 Day Unlimited → ₹50
• 7 Days Unlimited → ₹250
• 30 Days Unlimited → ₹800

{footer()}
"""
        try:
            bot.edit_message_text(packs_msg, call.message.chat.id, call.message.message_id, reply_markup=credit_packs_markup(), parse_mode='Markdown')
        except Exception:
            bot.send_message(call.message.chat.id, packs_msg, reply_markup=credit_packs_markup(), parse_mode='Markdown')

    elif action.startswith("plan_"):
        plan_id = action.replace("plan_", "")
        plan = get_plan_config(plan_id)
        if not plan:
            bot.send_message(call.message.chat.id, "❌ Invalid plan.")
            return

        bot.answer_callback_query(call.id, f"Processing {plan['label']}...")
        
        if plan_id in ["protect_number", "protect_telegram"]:
            if plan_id == "protect_number":
                bot.send_message(call.message.chat.id, "📱 *Enter 10-digit number to protect:*\n\nType /cancel to abort", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
                user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
            else:
                bot.send_message(call.message.chat.id, "💬 *Enter Telegram ID to protect:*\n\nType /cancel to abort", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
                user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
            return

        order_id = f"TX_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        payload = {
            "order_id": order_id,
            "order_amount": float(plan["amount"]),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"CUST_{user_id}",
                "customer_phone": "9999999999",
                "customer_email": f"user_{user_id}@tracex.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment-status?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/webhook/cashfree",
            }
        }

        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(CASHFREE_API_BASE, headers=headers, json=payload, timeout=20)
            res_data = resp.json()
            
            if resp.status_code == 200 and "payment_session_id" in res_data:
                pay_url = f"https://payments.cashfree.com/order/#/{res_data['payment_session_id']}"
                mk = InlineKeyboardMarkup()
                mk.add(InlineKeyboardButton("💳 PAY NOW", url=pay_url))
                mk.add(InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_tx_{order_id}"))
                mk.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
                
                try:
                    supabase.table("payment_orders").insert({
                        "order_id": order_id,
                        "telegram_user_id": user_id,
                        "plan_id": plan_id,
                        "amount": plan["amount"],
                        "status": "PENDING",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()
                except Exception:
                    pass

                txt = f"⚡ *Payment Gateway*\n━━━━━━━━━━━━━━━━\n\nPlan: *{plan['label']}*\nAmount: *₹{plan['amount']}*\nOrder ID: `{order_id}`\n\nClick below to pay:"
                bot.send_message(call.message.chat.id, txt, reply_markup=mk, parse_mode='Markdown')
                send_admin_alert(f"💸 Payment initiated\nUser: `{user_id}`\nPlan: {plan['label']}\nAmount: ₹{plan['amount']}")
            else:
                bot.send_message(call.message.chat.id, "❌ Payment gateway error. Please try again later.", reply_markup=get_main_keyboard())
        except Exception as e:
            print(f"Payment error: {e}")
            bot.send_message(call.message.chat.id, "❌ Payment service unavailable. Contact admin.", reply_markup=get_main_keyboard())

    elif action.startswith("verify_tx_"):
        order_id = action.replace("verify_tx_", "")
        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION
        }
        try:
            v_url = f"{CASHFREE_API_BASE}/{order_id}"
            resp = requests.get(v_url, headers=headers, timeout=20)
            v_data = resp.json()
            status = str(v_data.get("order_status", "PENDING")).upper()
            
            if status == "PAID":
                res = supabase.table("payment_orders").select("*").eq("order_id", order_id).execute()
                if res.data and res.data[0].get("status") != "SUCCESS":
                    order = res.data[0]
                    plan = get_plan_config(order["plan_id"])
                    if plan:
                        ptype = plan.get("payment_for")
                        if ptype == "credits":
                            add_credits(user_id, plan["credits"])
                        elif ptype == "unlimited":
                            minutes = plan.get("unlimited_minutes", 0)
                            new_expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
                            supabase.table("telegram_users").update({
                                "unlimited_expiry": new_expiry.isoformat()
                            }).eq("telegram_user_id", user_id).execute()
                    supabase.table("payment_orders").update({"status": "SUCCESS"}).eq("order_id", order_id).execute()
                    bot.send_message(call.message.chat.id, f"✅ *Payment Successful!*\n\n{plan['label']} activated!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                else:
                    bot.send_message(call.message.chat.id, "✅ Payment already processed!", reply_markup=get_main_keyboard())
            else:
                bot.send_message(call.message.chat.id, f"⚠️ Payment status: {status}\nPlease complete payment first.", reply_markup=get_main_keyboard())
        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ Could not verify payment. Please wait or contact admin.", reply_markup=get_main_keyboard())

    elif action == "booking_pay":
        plan = get_plan_config("bot_booking")
        order_id = f"BK_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        payload = {
            "order_id": order_id,
            "order_amount": float(plan["amount"]),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"CUST_{user_id}",
                "customer_phone": "9999999999",
                "customer_email": f"user_{user_id}@tracex.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment-status?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/webhook/cashfree",
            }
        }

        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(CASHFREE_API_BASE, headers=headers, json=payload, timeout=20)
            res_data = resp.json()
            
            if resp.status_code == 200 and "payment_session_id" in res_data:
                pay_url = f"https://payments.cashfree.com/order/#/{res_data['payment_session_id']}"
                mk = InlineKeyboardMarkup()
                mk.add(InlineKeyboardButton("💳 PAY ₹999", url=pay_url))
                mk.add(InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_booking_{order_id}"))
                
                try:
                    supabase.table("payment_orders").insert({
                        "order_id": order_id,
                        "telegram_user_id": user_id,
                        "plan_id": "bot_booking",
                        "amount": 999,
                        "status": "PENDING",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()
                except Exception:
                    pass

                bot.send_message(call.message.chat.id, "🤖 *Bot Booking Payment*\n\nClick below to complete payment:", reply_markup=mk, parse_mode='Markdown')
            else:
                bot.send_message(call.message.chat.id, "❌ Payment error. Contact admin.", reply_markup=get_main_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Payment service unavailable.", reply_markup=get_main_keyboard())

    elif action.startswith("verify_booking_"):
        order_id = action.replace("verify_booking_", "")
        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION
        }
        try:
            v_url = f"{CASHFREE_API_BASE}/{order_id}"
            resp = requests.get(v_url, headers=headers, timeout=20)
            v_data = resp.json()
            status = str(v_data.get("order_status", "PENDING")).upper()
            
            if status == "PAID":
                supabase.table("payment_orders").update({"status": "SUCCESS"}).eq("order_id", order_id).execute()
                bot.send_message(call.message.chat.id, "✅ *Booking Confirmed!*\n\nAdmin will contact you within 24-48 hours.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                send_admin_alert(f"🤖 Bot Booking\nUser: `{user_id}`\nOrder: `{order_id}`\nContact user for requirements.")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ Payment status: {status}\nPlease complete payment.", reply_markup=get_main_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Could not verify. Contact admin.", reply_markup=get_main_keyboard())

    elif action == "admin" and user_id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "🛠 Admin panel - Use /commands", reply_markup=get_main_keyboard())

# ==================== PROTECTION INPUT HANDLER ====================
@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict) and user_states[m.from_user.id].get("state") == "awaiting_protection_input")
def protection_input_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state:
        return

    plan_id = state.get("plan_id")
    value = str(message.text or "").strip()

    if value == "❌ CANCEL" or value == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Protection cancelled.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        return

    if plan_id == "protect_number":
        phone = normalize_indian_mobile(value)
        if not phone:
            bot.reply_to(message, "❌ Invalid number! Enter 10-digit Indian number.", reply_markup=get_main_keyboard())
            return
        if is_number_protected(phone):
            bot.reply_to(message, f"❌ Number `{phone}` is already protected!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
            return
        
        plan = get_plan_config("protect_number")
        order_id = f"PR_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        payload = {
            "order_id": order_id,
            "order_amount": float(plan["amount"]),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"CUST_{user_id}",
                "customer_phone": phone,
                "customer_email": f"user_{user_id}@tracex.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment-status?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/webhook/cashfree",
            }
        }

        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(CASHFREE_API_BASE, headers=headers, json=payload, timeout=20)
            res_data = resp.json()
            
            if resp.status_code == 200 and "payment_session_id" in res_data:
                pay_url = f"https://payments.cashfree.com/order/#/{res_data['payment_session_id']}"
                mk = InlineKeyboardMarkup()
                mk.add(InlineKeyboardButton("💳 PAY ₹99", url=pay_url))
                mk.add(InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_protect_{order_id}"))
                
                try:
                    supabase.table("payment_orders").insert({
                        "order_id": order_id,
                        "telegram_user_id": user_id,
                        "plan_id": "protect_number",
                        "amount": 99,
                        "protected_value": phone,
                        "status": "PENDING",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()
                except Exception:
                    pass

                bot.send_message(message.chat.id, f"🛡️ *Number Protection*\n\nNumber: `{phone}`\nAmount: ₹99\n\nClick below to pay:", reply_markup=mk, parse_mode='Markdown')
                user_states.pop(user_id, None)
            else:
                bot.reply_to(message, "❌ Payment error. Try again later.", reply_markup=get_main_keyboard())
        except Exception:
            bot.reply_to(message, "❌ Payment service unavailable.", reply_markup=get_main_keyboard())

    elif plan_id == "protect_telegram":
        tg_id = str(value).strip()
        if not re.match(r'^\d{5,15}$', tg_id):
            bot.reply_to(message, "❌ Invalid Telegram ID! Enter numeric ID only.", reply_markup=get_main_keyboard())
            return
        if is_telegram_protected(tg_id):
            bot.reply_to(message, f"❌ Telegram ID `{tg_id}` is already protected!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
            return
        
        plan = get_plan_config("protect_telegram")
        order_id = f"PT_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        payload = {
            "order_id": order_id,
            "order_amount": float(plan["amount"]),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"CUST_{user_id}",
                "customer_phone": "9999999999",
                "customer_email": f"user_{user_id}@tracex.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment-status?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/webhook/cashfree",
            }
        }

        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(CASHFREE_API_BASE, headers=headers, json=payload, timeout=20)
            res_data = resp.json()
            
            if resp.status_code == 200 and "payment_session_id" in res_data:
                pay_url = f"https://payments.cashfree.com/order/#/{res_data['payment_session_id']}"
                mk = InlineKeyboardMarkup()
                mk.add(InlineKeyboardButton("💳 PAY ₹99", url=pay_url))
                mk.add(InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_protect_tg_{order_id}"))
                
                try:
                    supabase.table("payment_orders").insert({
                        "order_id": order_id,
                        "telegram_user_id": user_id,
                        "plan_id": "protect_telegram",
                        "amount": 99,
                        "protected_value": tg_id,
                        "status": "PENDING",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()
                except Exception:
                    pass

                bot.send_message(message.chat.id, f"🛡️ *Telegram Protection*\n\nTelegram ID: `{tg_id}`\nAmount: ₹99\n\nClick below to pay:", reply_markup=mk, parse_mode='Markdown')
                user_states.pop(user_id, None)
            else:
                bot.reply_to(message, "❌ Payment error. Try again later.", reply_markup=get_main_keyboard())
        except Exception:
            bot.reply_to(message, "❌ Payment service unavailable.", reply_markup=get_main_keyboard())

# ==================== VERIFICATION CALLBACKS FOR PROTECTION ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_protect_"))
def verify_protection_payment(call):
    user_id = call.from_user.id
    data = call.data
    order_id = data.replace("verify_protect_", "")
    
    headers = {
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": CASHFREE_API_VERSION
    }
    try:
        v_url = f"{CASHFREE_API_BASE}/{order_id}"
        resp = requests.get(v_url, headers=headers, timeout=20)
        v_data = resp.json()
        status = str(v_data.get("order_status", "PENDING")).upper()
        
        if status == "PAID":
            res = supabase.table("payment_orders").select("*").eq("order_id", order_id).execute()
            if res.data and res.data[0].get("status") != "SUCCESS":
                order = res.data[0]
                plan_id = order["plan_id"]
                protected_value = order.get("protected_value")
                
                if plan_id == "protect_number" and protected_value:
                    add_protected_number(protected_value, f"User_{user_id}")
                    bot.send_message(call.message.chat.id, f"✅ *Number Protected!*\n\nNumber: `{protected_value}`\n\nThis number will not appear in lookup results.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                elif plan_id == "protect_telegram" and protected_value:
                    add_protected_telegram_id(protected_value, f"User_{user_id}")
                    bot.send_message(call.message.chat.id, f"✅ *Telegram ID Protected!*\n\nID: `{protected_value}`\n\nThis Telegram ID will not appear in lookup results.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                
                supabase.table("payment_orders").update({"status": "SUCCESS"}).eq("order_id", order_id).execute()
                send_admin_alert(f"🛡️ Protection purchased\nUser: `{user_id}`\nPlan: {plan_id}\nValue: {protected_value}")
            else:
                bot.send_message(call.message.chat.id, "✅ Protection already activated!", reply_markup=get_main_keyboard())
        else:
            bot.send_message(call.message.chat.id, f"⚠️ Payment status: {status}\nPlease complete payment first.", reply_markup=get_main_keyboard())
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ Could not verify. Contact admin.", reply_markup=get_main_keyboard())

# ==================== FLASK WEBHOOK SERVER ====================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ONLINE", "version": BOT_VERSION}), 200

@app.route("/payment-status", methods=["GET"])
def payment_status():
    return "<h3>Payment Status</h3><p>Return to Telegram and click Verify button.</p>", 200

@app.route("/webhook/cashfree", methods=["POST"])
def cashfree_webhook():
    try:
        raw_payload = request.data
        signature = request.headers.get("x-webhook-signature")
        timestamp = request.headers.get("x-webhook-timestamp")
        
        if signature and timestamp and CASHFREE_WEBHOOK_SECRET:
            data_to_sign = timestamp.encode('utf-8') + raw_payload
            secret = CASHFREE_WEBHOOK_SECRET.encode('utf-8')
            computed_sig = hmac.new(secret, data_to_sign, hashlib.sha256).digest()
            import base64
            computed_sig_b64 = base64.b64encode(computed_sig).decode('utf-8')
            
            if computed_sig_b64 != signature and CASHFREE_ENV != "TEST":
                return jsonify({"status": "UNAUTHORIZED"}), 401
        
        payload = request.json
        event = payload.get("type")
        
        if event == "ORDER_PAID_SUCCESS":
            data_obj = payload.get("data", {}).get("order", {})
            order_id = data_obj.get("order_id")
            
            res = supabase.table("payment_orders").select("*").eq("order_id", order_id).execute()
            if res.data and res.data[0].get("status") != "SUCCESS":
                order = res.data[0]
                user_id = order["telegram_user_id"]
                plan_id = order["plan_id"]
                plan = get_plan_config(plan_id)
                
                if plan:
                    ptype = plan.get("payment_for")
                    if ptype == "credits":
                        add_credits(user_id, plan["credits"])
                    elif ptype == "unlimited":
                        minutes = plan.get("unlimited_minutes", 0)
                        new_expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
                        supabase.table("telegram_users").update({
                            "unlimited_expiry": new_expiry.isoformat()
                        }).eq("telegram_user_id", user_id).execute()
                    elif ptype == "protect_number":
                        protected_value = order.get("protected_value")
                        if protected_value:
                            add_protected_number(protected_value, f"User_{user_id}")
                    elif ptype == "protect_telegram":
                        protected_value = order.get("protected_value")
                        if protected_value:
                            add_protected_telegram_id(protected_value, f"User_{user_id}")
                
                supabase.table("payment_orders").update({"status": "SUCCESS"}).eq("order_id", order_id).execute()
                try:
                    bot.send_message(user_id, f"✅ *Payment Successful!*\n\n{plan['label']} activated!" if plan else "✅ Payment Successful!", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                except Exception:
                    pass
        
        return jsonify({"status": "PROCESSED"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "ERROR"}), 500

def keep_alive():
    def run():
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    threading.Thread(target=run, daemon=True).start()

# ==================== DAILY REPORT SCHEDULER ====================
def generate_daily_search_report():
    with daily_stats_lock:
        report_date = datetime.now(IST).strftime("%Y-%m-%d")
        total_num = len(daily_search_stats.get("number", []))
        found_num = sum(1 for x in daily_search_stats.get("number", []) if x["found"])
        total_tg = len(daily_search_stats.get("telegram", []))
        found_tg = sum(1 for x in daily_search_stats.get("telegram", []) if x["found"])
        total_id = len(daily_search_stats.get("identity", []))
        found_id = sum(1 for x in daily_search_stats.get("identity", []) if x["found"])
        total_ifsc = len(daily_search_stats.get("ifsc", []))
        found_ifsc = sum(1 for x in daily_search_stats.get("ifsc", []) if x["found"])
        
        report = f"📊 *TraceX Daily Report*\n📅 Date: `{report_date}`\n\n"
        report += f"📱 Number: Total `{total_num}` | Found `{found_num}`\n"
        report += f"💬 Telegram: Total `{total_tg}` | Found `{found_tg}`\n"
        report += f"🆔 Identity: Total `{total_id}` | Found `{found_id}`\n"
        report += f"🏦 IFSC: Total `{total_ifsc}` | Found `{found_ifsc}`\n\n"
        
        report += "📝 *Recent Activity (Last 15):*\n"
        all_activities = []
        for t, items in daily_search_stats.items():
            for item in items:
                all_activities.append(item)
        all_activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        for act in all_activities[:15]:
            status = "✅" if act["found"] else "❌"
            report += f"• `{act['timestamp'][11:16]}` | {act['username']} | {status} ({act['credits_used']}cr)\n"
        
        daily_search_stats.clear()
        return report

def send_daily_report_loop():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_secs = (target - now).total_seconds()
            time.sleep(sleep_secs)
            
            report_text = generate_daily_search_report()
            send_admin_alert(report_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Daily report error: {e}")
            time.sleep(60)

def send_daily_motivation_loop():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_secs = (target - now).total_seconds()
            time.sleep(sleep_secs)
            
            promo = f"""
🚀 *TraceX Updates*

• Number Lookup: 5 credits
• Telegram Lookup: 12 credits
• Identity Lookup: 15 credits
• IFSC Lookup: 20 credits

🔗 Web: {WEBSITE_URL}
👨‍💻 Admin: {ADMIN_USERNAME}
"""
            try:
                bot.send_message(ADMIN_CHANNEL_ID, promo, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception:
                pass
        except Exception as e:
            print(f"Motivation loop error: {e}")
            time.sleep(60)

# ==================== MAIN ENTRYPOINT ====================
if __name__ == "__main__":
    print("=" * 50)
    print(f"🚀 TraceX Engine v{BOT_VERSION}")
    print(f"Cashfree: {CASHFREE_ENV}")
    print("=" * 50)
    
    keep_alive()
    print("✅ Flask server started")
    
    threading.Thread(target=send_daily_report_loop, daemon=True).start()
    threading.Thread(target=send_daily_motivation_loop, daemon=True).start()
    
    print("✅ Bot running! Press Ctrl+C to stop.")
    
    def signal_handler(sig, frame):
        print("\n🛑 Stopping...")
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
            time.sleep(5)