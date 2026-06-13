"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 5.9.1 - Telegram Lookup API Updated
"""

import os
import sys

# Friendly dependency check for Render/Termux. No features are removed; this only shows a clear error.
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

# Lightweight Supabase REST client for Termux/Python 3.13.
# Avoids official supabase package because it pulls pydantic-core/Rust builds on Android.
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
BOT_VERSION = "5.9.1"

# Lookup API Configuration
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/api/v1/lookup.php").strip()
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "TVB_SGL_053B3AA6").strip()
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number").strip()

# Telegram Lookup API (Updated - New endpoint)
TELEGRAM_LOOKUP_API_URL = "https://exploitsindia.site//hdhddhjdjddjdjdjdndnddnnccndndhejdmdnnd//telegram.php"

NUMBER_LOOKUP_COST = 10
TELEGRAM_LOOKUP_COST = 15  # Updated to 15 credits
VEHICLE_LOOKUP_COST = 10
MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900
PROTECT_NUMBER_PRICE = 99
PROTECT_TELEGRAM_PRICE = 99
PROTECT_VEHICLE_PRICE = 99

# Hardcoded extra lookup APIs requested
TELEGRAM_LOOKUP_API_KEY = "TVB_SGL_D500F1C5"
TELEGRAM_LOOKUP_SERVICE = "tg_to_number"
VEHICLE_LOOKUP_API_KEY = "TVB_SGL_0435DADE"
VEHICLE_LOOKUP_SERVICE = "vehicle_owner_number"

COOLDOWN_SECONDS = 3
AUTO_DELETE_SECONDS = 120
GROUP_LINK = "https://t.me/Gaurav_beni_0001"
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Gaurav_beni_0001")
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")

# Generic API error shown to users. Never expose provider/API raw errors in Telegram.
GENERIC_API_ERROR_MESSAGE = "❌ *API Error*\n\n💎 Credits NOT deducted"

def show_api_error(chat_id, message_id, lookup_type="api"):
    """Show only a clean API error to users; keep provider/raw errors out of Telegram replies."""
    try:
        bot.edit_message_text(GENERIC_API_ERROR_MESSAGE, chat_id, message_id, parse_mode="Markdown")
    except Exception as edit_error:
        print(f"Failed to show generic API error for {lookup_type}: {edit_error}")

def safe_json_response(response):
    """Parse JSON safely and raise a generic exception if upstream response is invalid."""
    try:
        return response.json()
    except Exception:
        raise ValueError("Invalid API JSON response")

def has_valid_number_results(result):
    """True only when API/cache has at least one usable number result."""
    if not isinstance(result, dict):
        return False
    api_results = result.get("results")
    if isinstance(api_results, dict):
        return any(isinstance(v, dict) for v in api_results.values())
    if isinstance(api_results, list):
        return any(isinstance(v, dict) for v in api_results)
    return any(str(k).lower().startswith("result") and isinstance(v, dict) for k, v in result.items()) or ("name" in result or "mobile" in result)

def call_unstable_json_api(params, lookup_type="number", max_retries=5, timeout=30):
    """
    Smart API caller for Cloudflare/unstable APIs.
    Fixes random 502 HTML responses by retrying before showing API Error.
    Returns: (data, error_reason)
    """
    base_url = str(LOOKUP_API_URL or "").strip()
    clean_params = {str(k): str(v).strip() for k, v in (params or {}).items() if v is not None}

    headers_attempts = [
        {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/5.9",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        },
        {
            "User-Agent": "python-requests TraceXBot/5.9",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        },
    ]

    last_error = "unknown"
    for attempt in range(1, int(max_retries or 5) + 1):
        headers = headers_attempts[(attempt - 1) % len(headers_attempts)]
        try:
            response = requests.get(base_url, params=clean_params, headers=headers, timeout=timeout)
            content_type = str(response.headers.get("content-type", "")).lower()
            raw_preview = (response.text or "")[:500].replace("\n", " ")

            print(f"[{lookup_type.upper()} API] Try {attempt}/{max_retries} | HTTP {response.status_code} | CT={content_type}")
            print(f"[{lookup_type.upper()} API] URL: {response.url}")
            print(f"[{lookup_type.upper()} API] RAW: {raw_preview}")

            # Cloudflare/provider sometimes returns 502 HTML. Retry these.
            if response.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                last_error = f"temporary_http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue

            if response.status_code != 200:
                last_error = f"http_{response.status_code}"
                time.sleep(min(2 * attempt, 8))
                continue

            # Try JSON even if content-type is wrong, but reject HTML/block pages.
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
            print(f"[{lookup_type.upper()} API] Connection error on try {attempt}: {conn_error}")
            time.sleep(min(2 * attempt, 8))
        except Exception as api_error:
            last_error = f"exception_{api_error}"
            print(f"[{lookup_type.upper()} API] Error on try {attempt}: {api_error}")
            time.sleep(min(2 * attempt, 8))

    print(f"[{lookup_type.upper()} API] FINAL FAILED after {max_retries} tries: {last_error}")
    return None, last_error

def notify_admin_api_issue(lookup_type, query, error_reason):
    """Send compact admin-only debug alert without exposing raw provider errors to users."""
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ *API TEMP ISSUE*\n\nType: `{lookup_type}`\nQuery: `{query}`\nReason: `{str(error_reason)[:500]}`\n\nUser credits were not deducted.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Admin API issue notify failed: {e}")

def split_long_text(text, limit=TELEGRAM_SAFE_LIMIT):
    """Split long Telegram text safely by lines to avoid the 4096 character limit."""
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
    """Edit the loading message for short output; split and send extra messages for large output."""
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

# Manual QR Plan Configuration - Updated: Removed unlimited plans except 1 week and 1 month, minimum credits 50
PLAN_CONFIG = {
    "c50": {"amount": 70, "credits": 50, "unlimited_minutes": 0, "payment_for": "credits", "label": "50 Credits"},
    "c100": {"amount": 100, "credits": 100, "unlimited_minutes": 0, "payment_for": "credits", "label": "100 Credits"},
    "u1w": {"amount": 358, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited"},
    "u1m": {"amount": 898, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited"},
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Number Protection"},
    "bot_booking": {"amount": 399, "credits": 0, "unlimited_minutes": 0, "payment_for": "bot_booking", "label": "Custom Bot Booking Add-on"},
}

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

# Cashfree API URLs - will be set dynamically
CASHFREE_API_BASE = "https://sandbox.cashfree.com/pg" if CASHFREE_ENV == "TEST" else "https://api.cashfree.com/pg"
CASHFREE_API_VERSION = "2023-08-01"

# Initialize Bot
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

# Initialize Supabase Client
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
active_number_sessions = set()
active_number_sessions_lock = threading.Lock()
active_telegram_sessions = set()
active_telegram_sessions_lock = threading.Lock()
proof_forwarded_txs = set()

# 24-hour search summary storage
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

@bot.callback_query_handler(func=lambda call: MAINTENANCE_MODE and call.from_user.id != ADMIN_ID)
def maintenance_callback(call):
    bot.answer_callback_query(call.id, "Bot under maintenance 🛠️", show_alert=True)

# ==================== UI COMPONENTS ====================
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
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 Website: {WEBSITE_URL}\n⚡ Instant credits add • Lower credit cost • More accurate search\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    """Send important admin alerts to group, with DM fallback to admin to avoid missed payment sessions."""
    sent = False
    try:
        bot.send_message(ADMIN_CHANNEL_ID, text, reply_markup=reply_markup, parse_mode=parse_mode)
        sent = True
    except Exception as e:
        print(f"Admin channel alert failed: {e}")
    if not sent:
        try:
            bot.send_message(ADMIN_ID, "⚠️ Admin group delivery failed, fallback DM:\n\n" + text, reply_markup=reply_markup, parse_mode=parse_mode)
            sent = True
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
    """Return True only if user has joined the required channel. Admin bypasses this check."""
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

def main_menu_markup(current_user_id=None):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📱 NUMBER LOOKUP", callback_data="lookup"),
        InlineKeyboardButton("💬 TELEGRAM LOOKUP", callback_data="telegram_lookup")
    )
    markup.add(
        InlineKeyboardButton("💎 MY CREDITS", callback_data="credits"),
        InlineKeyboardButton("🤖 BOOK A BOT", callback_data="book_bot")
    )
    markup.add(
        InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"),
        InlineKeyboardButton("🛡️ PROTECTION", callback_data="protection_menu")
    )
    if current_user_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("🛠 ADMIN", callback_data="admin"))
    return markup

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    return markup

def credit_packs_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 50 Credits - ₹70", callback_data="plan_c50"),
        InlineKeyboardButton("💰 100 Credits - ₹100", callback_data="plan_c100")
    )
    markup.add(
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹358", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹898", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number")
    )
    markup.add(
        InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    return markup

def telegram_lookup_protection_markup():
    """Show protection option after Telegram lookup"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛡️ PROTECT MY TELEGRAM ID", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔍 NEW TELEGRAM LOOKUP", callback_data="telegram_lookup")
    )
    markup.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    return markup

# ==================== TELEGRAM LOOKUP FUNCTION ====================
def call_telegram_lookup_api(username):
    """
    Call the Telegram lookup API at the new endpoint with exploits parameter
    Format: https://exploitsindia.site//hdhddhjdjddjdjdjdndnddnnccndndhejdmdnnd//telegram.php?exploits=@username
    Returns: (data, error_reason)
    """
    try:
        if not username.startswith('@'):
            username = '@' + username
        
        from urllib.parse import urlencode
        url = f"{TELEGRAM_LOOKUP_API_URL}?{urlencode({'exploits': username})}"
        print(f"[TELEGRAM LOOKUP API] Calling: {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/5.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"[TELEGRAM LOOKUP API] Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return None, f"http_{response.status_code}"
        
        html_content = response.text
        print(f"[TELEGRAM LOOKUP API] Response length: {len(html_content)}")
        
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
        
        result['raw_html'] = html_content
        
        buy_api_match = re.search(r'💳 BUY API\s*:\s*@([a-zA-Z0-9_]+)', html_content)
        support_match = re.search(r'🆘 SUPPORT\s*:\s*@([a-zA-Z0-9_]+)', html_content)
        
        result['buy_api'] = buy_api_match.group(1) if buy_api_match else None
        result['support'] = support_match.group(1) if support_match else None
        
        if result.get('telegram_id') or result.get('phone_number'):
            return result, None
        else:
            no_data_markers = [
                "no data found", "not found", "no records", "no record",
                "no result", "no results", "data not found", "record not found"
            ]
            lower_html = html_content.lower()
            if any(marker in lower_html for marker in no_data_markers):
                return {"error": "no_result"}, None

            if html_content.strip():
                return {"error": "no_result"}, None
            return None, "empty_api_response"
            
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except Exception as e:
        print(f"[TELEGRAM LOOKUP API] Exception: {e}")
        return None, f"exception_{e}"

def format_telegram_lookup_result(result, username, user_id, unlimited_active=False, unlimited_expiry=None):
    """Format the Telegram lookup result for display - filtered to remove BUY API/SUPPORT lines"""
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

def process_telegram_lookup(message):
    """Process Telegram username lookup"""
    user_id = message.from_user.id
    username_input = str(message.text or "").strip()

    if username_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_telegram_username":
        return

    user_states.pop(user_id, None)

    username_clean = username_input
    if not username_input.startswith('@'):
        username_clean = '@' + username_input
    
    if not re.match(r'^@?[a-zA-Z0-9_]{5,32}$', username_input):
        bot.reply_to(message, "❌ *Invalid Telegram Username!*\n\nEnter a valid Telegram username.\nExamples: `@username` or `username`\n\n💎 Cost: `15 credits` per search", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    
    with active_telegram_sessions_lock:
        if user_id in active_telegram_sessions:
            bot.reply_to(message, "⏳ *One Telegram search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        active_telegram_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < TELEGRAM_LOOKUP_COST and not unlimited_active:
        markup = universal_markup(buy=True, join=True, admin=True)
        bot.reply_to(message, f"❌ *Not enough credits!* Telegram Lookup costs `{TELEGRAM_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
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
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=0)
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    if result.get("error") == "no_result" or not result.get("telegram_id"):
        if not unlimited_active:
            if not deduct_credits(user_id, TELEGRAM_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*",
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                with active_telegram_sessions_lock:
                    active_telegram_sessions.discard(user_id)
                return

        increment_total_searches(user_id)
        updated_total = get_total_credits(user_id)
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Username: `{username_clean}`

🚫 No records available in database

💡 Tips:
• Check username again
• Try another username
• Ensure username is correct

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{0 if unlimited_active else TELEGRAM_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=TELEGRAM_LOOKUP_COST if not unlimited_active else 0)
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    telegram_id = result.get('telegram_id')
    if telegram_id and is_telegram_protected(telegram_id):
        output = f"""
🛡️ *PROTECTED TELEGRAM ID*

🔍 Username: `{username_clean}`
🆔 Telegram ID: `{telegram_id}`

This Telegram ID is protected by the Telegram Number Protection Plan.

The owner has purchased privacy protection. Details are hidden.

You can also protect your Telegram ID for ₹99!
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECT MY TELEGRAM", callback_data="plan_protect_telegram"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=0)
        with active_telegram_sessions_lock:
            active_telegram_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, TELEGRAM_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_telegram_sessions_lock:
                active_telegram_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_telegram_lookup_result(result, username_clean, user_id, unlimited_active, unlimited_expiry)
    markup = telegram_lookup_protection_markup()
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=True, lookup_type="telegram", credits_used=TELEGRAM_LOOKUP_COST if not unlimited_active else 0)
    
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
    
    with active_telegram_sessions_lock:
        active_telegram_sessions.discard(user_id)

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
    """Accept 10 digit Indian mobile, +91XXXXXXXXXX, 91XXXXXXXXXX, spaces/dashes."""
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits if re.match(r"^[6-9]\d{9}$", digits) else None

def resolve_user_identifier(identifier):
    """Resolve admin input: user_id, @username, or username to telegram_user_id."""
    token = str(identifier or "").strip()
    if not token:
        return None, None
    if token.startswith("@"): token = token[1:]
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

def activate_unlimited_plan_for_user(target_user, plan_id):
    plan = get_plan_config(plan_id)
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

def add_credits(telegram_user_id, amount):
    """Add credits to user and return new total. Creates user if not exists."""
    try:
        response = supabase.table("telegram_users").select("credits, telegram_user_id, telegram_name").eq("telegram_user_id", telegram_user_id).execute()
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
            update_result = supabase.table("telegram_users").update({
                "credits": new_credits,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            if update_result.data and len(update_result.data) > 0:
                return update_result.data[0].get('credits', new_credits)
            return new_credits
    except Exception as e:
        print(f"Add credits error for user {telegram_user_id}: {e}")
    return 0

def update_user_credits(telegram_user_id, new_credits):
    try:
        update_result = supabase.table("telegram_users").update({
            "credits": new_credits,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        if update_result.data and len(update_result.data) > 0:
            return update_result.data[0].get('credits', new_credits)
        return None
    except Exception as e:
        print(f"Update user credits error: {e}")
    return None

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
        res = update_user_credits(telegram_user_id, new_credits)
        return res is not None
    except Exception as e:
        print(f"Deduct credits runtime fault: {e}")
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
        print(f"Increment total searches error: {e}")

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

# ==================== DAILY SCHEDULERS & METRICS ====================
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

def generate_daily_search_report():
    with daily_stats_lock:
        report_date = datetime.now(IST).strftime("%Y-%m-%d")
        total_num = len(daily_search_stats.get("number", []))
        found_num = sum(1 for x in daily_search_stats.get("number", []) if x["found"])
        total_tg = len(daily_search_stats.get("telegram", []))
        found_tg = sum(1 for x in daily_search_stats.get("telegram", []) if x["found"])
        
        report = f"📊 *TraceX Daily Operations Report*\n📅 Date: `{report_date}`\n\n"
        report += f"📱 *Number Searches:* Total: `{total_num}` | Found: `{found_num}`\n"
        report += f"💬 *Telegram Searches:* Total: `{total_tg}` | Found: `{found_tg}`\n\n"
        
        report += "📝 *Recent Activity Log (Max 15):*\n"
        all_activities = []
        for t, items in daily_search_stats.items():
            for item in items:
                all_activities.append(item)
        all_activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        for act in all_activities[:15]:
            status = "✅" if act["found"] else "❌"
            report += f"• `{act['timestamp'][11:16]}` | {act['username']} | `{act['query']}` | {status} ({act['credits_used']}cr)\n"
            
        daily_search_stats.clear()
        return report

def send_daily_search_report_loop():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_secs = (target - now).total_seconds()
            print(f" Scheduler: Next daily operational report in {sleep_secs/3600:.2f} hours")
            time.sleep(sleep_secs)
            
            report_text = generate_daily_search_report()
            send_admin_alert(report_text, parse_mode="Markdown")
        except Exception as scheduler_err:
            print(f"Daily operational report scheduler fault: {scheduler_err}")
            time.sleep(60)

def send_daily_user_motivation_loop():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_secs = (target - now).total_seconds()
            print(f" Scheduler: Next daily marketing blast in {sleep_secs/3600:.2f} hours")
            time.sleep(sleep_secs)
            
            promo = f"""
🚀 *TraceX Premium Network Updates*

Get instant telecom lookup analytics directly inside Telegram!

💎 *Benefits of Web Upgrades:*
1. Super fast credit allocation
2. Advanced deep database queries
3. Fully integrated premium server lookups

🔗 Explore web tools: {WEBSITE_URL}
👨‍💻 Maintained by official admin: {ADMIN_USERNAME}
"""
            try:
                bot.send_message(ADMIN_CHANNEL_ID, promo, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                print(f"Marketing broadcast delivery failed: {e}")
        except Exception as e:
            print(f"Marketing Loop Fault: {e}")
            time.sleep(60)

# ==================== BOTCORE ROUTINES & SECTIONS ====================
@bot.message_handler(commands=['start', 'menu'])
def start_handler(message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        return
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    
    # Track username if available
    if message.from_user.username:
        try:
            supabase.table("telegram_users").update({
                "telegram_username": message.from_user.username,
                "telegram_name": message.from_user.first_name or "User"
            }).eq("telegram_user_id", user_id).execute()
        except Exception:
            pass

    if not is_channel_member(user_id):
        send_join_required(message.chat.id)
        return
        
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    welcome = header("TRACEX PLATFORM ENGINE", "🔥")
    welcome += f"Welcome back, *{message.from_user.first_name or 'User'}*!\n\n"
    welcome += f"💎 Available Credits: `{total_credits}`\n"
    if unlimited_active:
        welcome += f"🚀 Unlimited Access: `ACTIVE` until `{unlimited_expiry[:16]}`\n"
    welcome += f"🔎 Total Global Queries: `{user.get('total_searches', 0) if user else 0}`\n\n"
    welcome += "Select a lookup metric down below to scan numbers or verify identities."
    welcome += footer()
    
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu_markup(user_id), parse_mode='Markdown', disable_web_page_preview=True)

@bot.message_handler(commands=['help'])
def help_handler(message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        return
    help_text = f"""
💡 *TraceX Command Assistance*

• `/start` or `/menu` - Launch standard dashboard panel
• `/help` - View usage guide
• `/cancel` - Abort active operations

📱 *Lookup Instructions:*
Click *NUMBER LOOKUP* or *TELEGRAM LOOKUP* from the menu, then supply the target data.

💳 *Credits Pricing:*
• 50 Credits = ₹70
• 100 Credits = ₹100
• 7 Days Unlimited = ₹358
• 30 Days Unlimited = ₹898

🛡️ *Privacy Protection:*
Hide your information from data searches for ₹99.
"""
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_lookup_number")
def lookup_number_processor(message):
    user_id = message.from_user.id
    raw_val = str(message.text or "").strip()
    
    if raw_val == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Lookup cancelled.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        return

    user_states.pop(user_id, None)
    mobile = normalize_indian_mobile(raw_val)
    
    if not mobile:
        bot.reply_to(message, "❌ *Invalid Indian Phone Number!*\nPlease provide a standard 10 digit number.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
        return

    with active_number_sessions_lock:
        if user_id in active_number_sessions:
            bot.reply_to(message, "⏳ *Active request in progress. Please wait.*", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
            return
        active_number_sessions.add(user_id)

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, _ = get_active_unlimited(user)

    if total_credits < NUMBER_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Insufficient Credits!* (Requires {NUMBER_LOOKUP_COST} cr)", reply_markup=universal_markup(buy=True), parse_mode="Markdown")
        with active_number_sessions_lock:
            active_number_sessions.discard(user_id)
        return

    loading = bot.reply_to(message, "🔍 *Accessing Database Registries...*", parse_mode="Markdown")
    
    if is_number_protected(mobile):
        bot.edit_message_text("🛡️ *Privacy Shield Alert*\n\nThis subscriber node is protected under privacy guidelines. Identity assets are masked.", message.chat.id, loading.message_id, parse_mode="Markdown")
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, mobile, found=False, lookup_type="number", credits_used=0)
        with active_number_sessions_lock:
            active_number_sessions.discard(user_id)
        return

    params = {"key": LOOKUP_API_KEY, "service": LOOKUP_API_SERVICE, "number": mobile}
    data, api_err = call_unstable_json_api(params, lookup_type="number")

    if not data:
        show_api_error(message.chat.id, loading.message_id, lookup_type="number")
        notify_admin_api_issue("number_lookup", mobile, api_err)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, mobile, found=False, lookup_type="number", credits_used=0)
        with active_number_sessions_lock:
            active_number_sessions.discard(user_id)
        return

    if not has_valid_number_results(data):
        if not unlimited_active:
            deduct_credits(user_id, NUMBER_LOOKUP_COST)
        increment_total_searches(user_id)
        
        out = f"❌ *NO REGISTRY FOUND*\n\nQuery Target: `{mobile}`\n\nNo records verified on this cluster node.\n\n💎 Remaining Credits: `{get_total_credits(user_id)}`"
        bot.edit_message_text(out, message.chat.id, loading.message_id, parse_mode="Markdown")
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, mobile, found=False, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        with active_number_sessions_lock:
            active_number_sessions.discard(user_id)
        return

    if not unlimited_active:
        deduct_credits(user_id, NUMBER_LOOKUP_COST)
    increment_total_searches(user_id)

    res_str = f"🔍 *LOOKUP RESULTS ACQUIRED*\nTarget: `{mobile}`\n\n"
    # Basic structural format parsing logic
    if "results" in data:
        res_block = data["results"]
        if isinstance(res_block, dict):
            for k, v in res_block.items():
                if isinstance(v, dict):
                    res_str += f"👤 *Name:* `{v.get('name', 'N/A')}`\n📱 *Carrier:* `{v.get('carrier', 'N/A')}`\n📍 *Region:* `{v.get('circle', 'N/A')}`\n\n"
        elif isinstance(res_block, list):
            for entry in res_block[:MAX_LOOKUP_RESULTS]:
                if isinstance(entry, dict):
                    res_str += f"👤 *Name:* `{entry.get('name', 'N/A')}`\n📱 *Carrier:* `{entry.get('carrier', 'N/A')}`\n\n"
    else:
        res_str += f"👤 *Name:* `{data.get('name', 'N/A')}`\n📱 *Carrier:* `{data.get('mobile', 'N/A')}`\n\n"

    res_str += f"💎 Remaining Balance: `{get_total_credits(user_id)}`"
    res_str += footer()

    sent_msg = send_or_edit_long_message(message.chat.id, loading.message_id, res_str, parse_mode="Markdown")
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, mobile, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
    
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_msg), daemon=True).start()
    with active_number_sessions_lock:
        active_number_sessions.discard(user_id)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_telegram_username")
def lookup_telegram_processor(message):
    process_telegram_lookup(message)

# ==================== ACTIONS & INLINE CALLBACK REGISTRY ====================
@bot.callback_query_handler(func=lambda call: True)
def query_actions_router(call):
    if MAINTENANCE_MODE and call.from_user.id != ADMIN_ID:
        return
    user_id = call.from_user.id
    action = str(call.data)
    
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if action == "main_menu" or action == "cancel":
        user_states.pop(user_id, None)
        user = get_user(user_id)
        total_credits = get_total_credits(user_id)
        unlimited_active, unlimited_expiry = get_active_unlimited(user)
        
        welcome = header("TRACEX PLATFORM ENGINE", "🔥")
        welcome += f"Welcome back, *{call.from_user.first_name or 'User'}*!\n\n"
        welcome += f"💎 Available Credits: `{total_credits}`\n"
        if unlimited_active:
            welcome += f"🚀 Unlimited Access: `ACTIVE` until `{unlimited_expiry[:16]}`\n"
        welcome += f"🔎 Total Global Queries: `{user.get('total_searches', 0) if user else 0}`\n\n"
        welcome += "Select a lookup metric down below to scan numbers or verify identities."
        welcome += footer()
        
        try:
            bot.edit_message_text(welcome, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            bot.send_message(call.message.chat.id, welcome, reply_markup=main_menu_markup(user_id), parse_mode='Markdown', disable_web_page_preview=True)

    elif action == "check_join":
        if is_channel_member(user_id):
            bot.send_message(call.message.chat.id, "✅ Membership confirmed! Access unlocked. Run /menu to refresh.")
        else:
            bot.send_message(call.message.chat.id, "❌ Verification failed. Please ensure you join the tracking channel first.", reply_markup=join_required_markup())

    elif action == "lookup":
        if not is_channel_member(user_id):
            send_join_required(call.message.chat.id)
            return
        user_states[user_id] = "awaiting_lookup_number"
        bot.send_message(call.message.chat.id, "📱 *NUMBER LOOKUP ENGINE*\n━━━━━━━━━━━━━━━━\n\nPlease enter the 10-digit Indian target number to trace:\n\n💡 _Type /cancel to go back_", reply_markup=cancel_button(), parse_mode="Markdown")

    elif action == "telegram_lookup":
        if not is_channel_member(user_id):
            send_join_required(call.message.chat.id)
            return
        user_states[user_id] = "awaiting_telegram_username"
        bot.send_message(call.message.chat.id, "💬 *TELEGRAM ID LOOKUP ENGINE*\n━━━━━━━━━━━━━━━━\n\nEnter the exact target Telegram username (e.g. `@username` or `username`):\n\n💎 Cost: `15 credits` per search\n💡 _Type /cancel to go back_", reply_markup=cancel_button(), parse_mode="Markdown")

    elif action == "credits":
        user = get_user(user_id)
        total_credits = get_total_credits(user_id)
        unlimited_active, unlimited_expiry = get_active_unlimited(user)
        
        info = header("CREDITS INDEX SYSTEM", "💎")
        info += f"User Entity ID: `{user_id}`\n"
        info += f"Current Credit Units: `{total_credits}`\n"
        if unlimited_active:
            info += f"🚀 Unlimited Access: `ACTIVE` until `{unlimited_expiry[:16]}`\n"
        else:
            info += "🚀 Unlimited Access: `INACTIVE`\n"
        info += footer()
        bot.edit_message_text(info, call.message.chat.id, call.message.message_id, reply_markup=universal_markup(back=True, buy=True), parse_mode="Markdown", disable_web_page_preview=True)

    elif action == "buy":
        txt = header("CREDITS DEPOSIT TERMINAL", "🛒")
        txt += "Select your required bundle pack from the terminal registry options below:\n\n"
        txt += "⚡ *Credit Allocations:* Available instantly.\n"
        txt += "🚀 *Unlimited Allocation:* Query without restriction during active window."
        txt += footer()
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=credit_packs_markup(), parse_mode="Markdown", disable_web_page_preview=True)

    elif action == "book_bot":
        txt = header("CUSTOM STRUCT BOT BOOKING", "🤖")
        txt += "Want a professional custom tracking or management bot like TraceX?\n\n"
        txt += "💵 *Development Base Cost:* ₹399 setup.\n"
        txt += "🛠 Fully hosted runtime loops, dynamic database configurations, and admin dashboards.\n\n"
        txt += "Click Contact Admin to speak directly with development operations."
        txt += footer()
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=universal_markup(back=True, admin=True), parse_mode="Markdown", disable_web_page_preview=True)

    elif action == "protection_menu":
        txt = header("PRIVACY PROTECTION REGISTRY", "🛡️")
        txt += "Keep your public parameters from showing up in public lookup results:\n\n"
        txt += "• *Number Protection:* ₹99 (Removes cellular data parameters)\n"
        txt += "• *Telegram ID Protection:* ₹99 (Masks Telegram profile correlations)\n\n"
        txt += "Select Buy Credits below to pick a protection package plan."
        txt += footer()
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=universal_markup(back=True, buy=True), parse_mode="Markdown", disable_web_page_preview=True)

    elif action.startswith("plan_"):
        plan_id = action.replace("plan_", "")
        plan = get_plan_config(plan_id)
        if not plan:
            bot.send_message(call.message.chat.id, "❌ Selected structural plan layout no longer online.")
            return

        # Simple rate limiter for active payment initialization routines
        now = time.time()
        if user_id in payment_session_cooldown:
            if now - payment_session_cooldown[user_id] < PAYMENT_SESSION_COOLDOWN_SECONDS:
                left = int(PAYMENT_SESSION_COOLDOWN_SECONDS - (now - payment_session_cooldown[user_id]))
                bot.send_message(call.message.chat.id, f"⏳ *Payment throttling active.* Please wait {left}s before cycling order sessions.", parse_mode="Markdown")
                return
        payment_session_cooldown[user_id] = now

        order_id = f"TX_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        # Build Cashfree checkout structure session
        payload = {
            "order_id": order_id,
            "order_amount": float(plan["amount"]),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"CUST_{user_id}",
                "customer_phone": "9999999999",
                "customer_email": "tracex@payment.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment-status?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/webhook/cashfree",
                "payment_methods": "upi"
            },
            "order_note": f"Plan: {plan['label']} | User: {user_id}"
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
                
                # Create dynamic inline configuration
                mk = InlineKeyboardMarkup()
                mk.add(InlineKeyboardButton("💳 PAY NOW (UPI/CARDS)", url=pay_url))
                mk.add(InlineKeyboardButton("✅ VERIFY TRANSACTION", callback_data=f"chk_tx_{order_id}"))
                mk.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
                
                # Save transaction structural reference state context to database cache records
                try:
                    supabase.table("payment_orders").insert({
                        "order_id": order_id,
                        "telegram_user_id": user_id,
                        "plan_id": plan_id,
                        "amount": plan["amount"],
                        "status": "PENDING",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()
                except Exception as db_err:
                    print(f"Failed cache tracking state write: {db_err}")

                txt = header("GATEWAY LINK PREPARED", "⚡")
                txt += f"Bundle Package: *{plan['label']}*\n"
                txt += f"Invoice Amount: *₹{plan['amount']}*\n"
                txt += f"Internal Reference ID: `{order_id}`\n\n"
                txt += "Complete your payment inside the secure gateway window, then click Verify below."
                txt += footer()
                
                bot.send_message(call.message.chat.id, txt, reply_markup=mk, parse_mode="Markdown", disable_web_page_preview=True)
                
                # Alert tracking room channel
                send_admin_alert(f"💸 *Payment Session Initialized*\nUser: `{user_id}`\nPlan: `{plan['label']}`\nAmt: `₹{plan['amount']}`\nID: `{order_id}`")
            else:
                print(f"Cashfree processing payload error: {res_data}")
                bot.send_message(call.message.chat.id, "❌ *Gateway Session Failure.*\nConfiguration is pointing to structural validation test flags.", parse_mode="Markdown")
        except Exception as api_err:
            print(f"Cashfree execution failure: {api_err}")
            bot.send_message(call.message.chat.id, "❌ Gateway offline or connectivity structural runtime timeout.")

    elif action.startswith("chk_tx_"):
        oid = action.replace("chk_tx_", "")
        
        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION
        }
        
        try:
            v_url = f"{CASHFREE_API_BASE}/{oid}"
            resp = requests.get(v_url, headers=headers, timeout=20)
            v_data = resp.json()
            
            status = str(v_data.get("order_status", "PENDING")).upper()
            
            if status == "PAID":
                # Process structural fulfillment allocation routines
                success = execute_order_fulfillment(oid)
                if success:
                    bot.send_message(call.message.chat.id, "✅ *Transaction Verified Successfully!*\nYour premium benefits are applied. Run /menu to refresh status dashboards.", parse_mode="Markdown")
                else:
                    bot.send_message(call.message.chat.id, "⚠️ Transaction is paid but fulfillment loop was already closed or handled.", parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ *Order Status:* `{status}`\nPayment not confirmed yet. Complete transaction or try verification again shortly.", parse_mode="Markdown")
        except Exception as e:
            print(f"Manual check transaction loop failure: {e}")
            bot.send_message(call.message.chat.id, "❌ Verification execution routine tracking failure.")

    elif action == "admin":
        if user_id != ADMIN_ID:
            return
        adm_txt = "🛠 *TraceX Admin Control Matrix*\n━━━━━━━━━━━━━━━━━━━━\n"
        adm_txt += f"Current Software Version Core: `{BOT_VERSION}`\n"
        adm_txt += f"Active Maintenance Mode Flag: `{MAINTENANCE_MODE}`\n\n"
        adm_txt += "Manage parameters or change system variables manually via code flags."
        
        mk = InlineKeyboardMarkup()
        mk.add(InlineKeyboardButton("🏠 DASHBOARD", callback_data="main_menu"))
        bot.edit_message_text(adm_txt, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

# ==================== ORDER FULFILLMENT CORE ====================
def execute_order_fulfillment(order_id):
    """Atomic structural fulfillment allocation routine to guard against multiple credit injections."""
    try:
        res = supabase.table("payment_orders").select("*").eq("order_id", order_id).execute()
        if not res.data:
            print(f" Order record {order_id} not indexed in storage cache maps.")
            return False
            
        order = res.data[0]
        if order.get("status") == "SUCCESS":
            print(f" Order allocation route {order_id} already marked SUCCESS.")
            return False
            
        user_id = int(order["telegram_user_id"])
        plan_id = order["plan_id"]
        plan = get_plan_config(plan_id)
        
        if not plan:
            print(f" Context maps are missing plan definitions for configuration code: {plan_id}")
            return False
            
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Allocation Routing
        ptype = plan.get("payment_for")
        if ptype == "credits":
            credits_to_add = int(plan["credits"])
            add_credits(user_id, credits_to_add)
        elif ptype == "unlimited":
            activate_unlimited_plan_for_user(user_id, plan_id)
        elif ptype == "protect_number":
            add_protected_number(user_id, name=f"User_{user_id}")
        elif ptype == "protect_telegram":
            add_protected_telegram_id(user_id, username=f"TGUser_{user_id}")
            
        # Complete transaction record update pipeline
        supabase.table("payment_orders").update({
            "status": "SUCCESS",
            "updated_at": now_str
        }).eq("order_id", order_id).execute()
        
        # Broadcast configuration updates out to group notifications
        send_admin_alert(f"✅ *Fulfillment Finalized Successfully*\nUser: `{user_id}`\nPlan: `{plan['label']}`\nID: `{order_id}`")
        
        try:
            bot.send_message(user_id, f"🎉 *Payment Allocation Finalized!*\nYour bundle pack configuration (*{plan['label']}*) is applied and online.", parse_mode="Markdown")
        except Exception:
            pass
            
        return True
    except Exception as fulfillment_err:
        print(f"CRITICAL: Structural fulfillment breakdown tracking fault: {fulfillment_err}")
        return False

# ==================== EMBEDDED FLASK RUNTIME SERVER ====================
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index_ping_test():
    return jsonify({"status": "ONLINE", "engine": "TraceX Engine Pro Core", "version": BOT_VERSION}), 200

@app.route("/payment-status", methods=["GET"])
def payment_status_page():
    order_id = request.args.get("order_id")
    return f"<h3>TraceX Processing Terminal Invoice Check Frame</h3><p>Order Reference: {order_id}</p><p>You can return to Telegram and press Verify Transaction now.</p>", 200

@app.route("/webhook/cashfree", methods=["POST"])
def cashfree_webhook_endpoint():
    """
    Validates structural authenticity signatures via asymmetric hash check blocks
    before modifying billing ledgers.
    """
    try:
        raw_payload = request.data
        signature = request.headers.get("x-webhook-signature")
        timestamp = request.headers.get("x-webhook-timestamp")
        
        if not signature or not timestamp:
            return jsonify({"status": "REJECTED", "reason": "Missing verification tags"}), 400
            
        # Signature Verification
        data_to_sign = timestamp.encode('utf-8') + raw_payload
        secret = CASHFREE_WEBHOOK_SECRET.encode('utf-8')
        computed_sig = hmac.new(secret, data_to_sign, hashlib.sha256).digest()
        import base64
        computed_sig_b64 = base64.b64encode(computed_sig).decode('utf-8')
        
        # If signature verification environment matches, switch to execution
        if computed_sig_b64 != signature and CASHFREE_ENV != "TEST":
            print("⚠️ Unauthorized verification hash signatures ignored.")
            return jsonify({"status": "UNAUTHORIZED"}), 401
            
        payload = request.json
        event = payload.get("type")
        
        if event == "ORDER_PAID_SUCCESS":
            data_obj = payload.get("data", {}).get("order", {})
            order_id = data_obj.get("order_id")
            execute_order_fulfillment(order_id)
            
        return jsonify({"status": "PROCESSED"}), 200
    except Exception as webhook_fault:
        print(f"Webhook structural runtime logic crash: {webhook_fault}")
        return jsonify({"status": "INTERNAL_ERROR"}), 500

def keep_alive():
    def run():
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    threading.Thread(target=run, daemon=True).start()

# ==================== MAIN SYSTEM ENTRYPOINT LOOP ====================
if __name__ == "__main__":
    print("=" * 50)
    print(f"🚀 Initializing TraceX Engine Framework Runtime Core v{BOT_VERSION}")
    print(f"Cashfree Environment: {CASHFREE_ENV}")
    print(f"Webhook Secret Set: {'Yes' if CASHFREE_WEBHOOK_SECRET else 'No'}")
    print(f"Cashfree Credentials Set: {'Yes' if CASHFREE_APP_ID and CASHFREE_SECRET_KEY else 'No'}")
    print("=" * 50)
    
    # Start Flask keep_alive server
    keep_alive()
    print("✅ Flask server started on port 8080")

    threading.Thread(target=send_daily_search_report_loop, daemon=True).start()
    print("✅ Daily 6 AM IST report scheduler started")
    threading.Thread(target=send_daily_user_motivation_loop, daemon=True).start()
    print("✅ Daily 11 AM IST user website promo scheduler started")
    
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    
    def signal_handler(sig, frame):
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Clear any old webhook before long polling. Only ONE bot instance must be running.
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