"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Manual QR
Version: 11.0.11 - Fixed JSON wrapping + long message splitting
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
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
requests = _require_package("requests", "requests")
import time
import re
from datetime import datetime, timedelta, timezone
import threading
import signal
import uuid
import json
from flask import Flask

# ==================== SECURE CONFIGURATION ====================
def get_env_var(var_name, required=True, default=None):
    """Safely get environment variable with optional fallback"""
    value = os.getenv(var_name)
    if required and not value:
        print(f"❌ Missing required environment variable: {var_name}")
        if default is not None:
            return default
        sys.exit(1)
    return value or default

BOT_TOKEN = get_env_var("BOT_TOKEN")
ADMIN_ID = int(get_env_var("ADMIN_ID", default="7850023357"))
ADMIN_CHANNEL_ID = int(get_env_var("ADMIN_CHANNEL_ID", default="-1003743686626"))
ADMIN_USERNAME = get_env_var("ADMIN_USERNAME", default="gaurav_beniwal_0001")

SUPABASE_URL = get_env_var("SUPABASE_URL")
SUPABASE_ANON_KEY = get_env_var("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = get_env_var("SUPABASE_SERVICE_ROLE_KEY", required=False)

# ==================== LOOKUP API CONFIGURATION ====================
LOOKUP_API_BASE = "https://gauravbeniwal.online/lookupportal/lookups/manual-api-plans/unlimited_api.php"
LOOKUP_API_KEY = "telegram-bot-osint"

LOOKUP_SERVICES = {
    "numberinfo": {
        "name": "Mobile Number Info",
        "emoji": "📱",
        "cost": 3,
        "query_type": "mobile",
        "placeholder": "9876543210",
        "description": "Mobile number details"
    },
    "tg2num": {
        "name": "Telegram To Number",
        "emoji": "💬",
        "cost": 5,
        "query_type": "username",
        "placeholder": "@username",
        "description": "Get phone from Telegram"
    },
    "aadhaar": {
        "name": "Aadhaar Lookup",
        "emoji": "🆔",
        "cost": 15,
        "query_type": "aadhaar",
        "placeholder": "123456789012",
        "description": "Aadhaar card details"
    },
    "vehicle": {
        "name": "Vehicle Lookup",
        "emoji": "🚗",
        "cost": 10,
        "query_type": "vehicle",
        "placeholder": "BR06PE8167",
        "description": "Vehicle registration info"
    },
    "instagram": {
        "name": "Instagram Lookup",
        "emoji": "📷",
        "cost": 10,
        "query_type": "username",
        "placeholder": "therock",
        "description": "Instagram profile details"
    },
    "truecaller": {
        "name": "Truecaller Lookup",
        "emoji": "📞",
        "cost": 10,
        "query_type": "mobile",
        "placeholder": "9876543210",
        "description": "Truecaller name & details"
    },
    "rc": {
        "name": "Vehicle RC Lookup",
        "emoji": "📋",
        "cost": 10,
        "query_type": "vehicle",
        "placeholder": "BR06PE8167",
        "description": "RC owner details"
    },
    "ifsc": {
        "name": "Bank IFSC Details",
        "emoji": "🏦",
        "cost": 5,
        "query_type": "ifsc",
        "placeholder": "SBIN0001234",
        "description": "Bank branch details"
    },
    "gst": {
        "name": "GST Info",
        "emoji": "🧾",
        "cost": 20,
        "query_type": "gst",
        "placeholder": "22AAAAA0000A1Z5",
        "description": "GST number details"
    },
    "imei": {
        "name": "IMEI Lookup",
        "emoji": "📲",
        "cost": 10,
        "query_type": "imei",
        "placeholder": "353010111111110",
        "description": "IMEI device info"
    },
    "pan": {
        "name": "PAN Card Lookup",
        "emoji": "💳",
        "cost": 20,
        "query_type": "pan",
        "placeholder": "AAYFK4129N",
        "description": "PAN name & DOB"
    },
    "challan": {
        "name": "Vehicle Challan",
        "emoji": "⚠️",
        "cost": 10,
        "query_type": "vehicle",
        "placeholder": "BR06PE8167",
        "description": "Traffic challan details"
    }
}

PAYMENT_QR_IMAGE = get_env_var("PAYMENT_QR_IMAGE", required=False, default="payment_qr.png")
WEBSITE_URL = get_env_var("WEBSITE_URL", required=False, default="https://tracexdata.online")
WEBSITE_REGISTRATION_URL = get_env_var("WEBSITE_REGISTRATION_URL", required=False, default="https://tracexdata.online/register")
GROUP_LINK = get_env_var("GROUP_LINK", required=False, default="https://t.me/Gaurav_beni_0001")

BOT_VERSION = "11.0.11"
MINIMUM_RECHARGE = int(get_env_var("MINIMUM_RECHARGE", required=False, default="30"))

MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900
COOLDOWN_SECONDS = 3
PAYMENT_SESSION_COOLDOWN_SECONDS = 60
REMINDER_INTERVAL_HOURS = 4

REFERRAL_GOALS = {
    3: {"plan": "u1h", "label": "1 Hour Unlimited"},
    15: {"plan": "u1d", "label": "1 Day Unlimited"},
    70: {"plan": "u1w", "label": "7 Days Unlimited"},
    200: {"plan": "u1m", "label": "30 Days Unlimited"},
    1000: {"plan": "lifetime", "label": "Lifetime Free"}
}

channels_str = get_env_var("REQUIRED_CHANNELS", required=False, default="Beniwal Mods|beniwalmods|https://t.me/beniwalmods,Gaurav Beniwal|Gaurav_beni_0001|https://t.me/Gaurav_beni_0001")
REQUIRED_CHANNELS = []
for channel in channels_str.split(','):
    parts = channel.split('|')
    if len(parts) == 3:
        REQUIRED_CHANNELS.append({
            "name": parts[0].strip(),
            "username": "@" + parts[1].strip() if not parts[1].strip().startswith('@') else parts[1].strip(),
            "link": parts[2].strip()
        })

PLAN_CONFIG = {
    "c50": {"amount": 30, "credits": 50, "unlimited_minutes": 0, "payment_for": "credits", "label": "50 Credits - ₹30"},
    "c100": {"amount": 60, "credits": 105, "unlimited_minutes": 0, "payment_for": "credits", "label": "105 Credits - ₹60"},
    "c200": {"amount": 120, "credits": 220, "unlimited_minutes": 0, "payment_for": "credits", "label": "220 Credits - ₹120"},
    "c500": {"amount": 300, "credits": 550, "unlimited_minutes": 0, "payment_for": "credits", "label": "550 Credits - ₹300"},
    "c1000": {"amount": 600, "credits": 1150, "unlimited_minutes": 0, "payment_for": "credits", "label": "1150 Credits - ₹600"},
    "u1h": {"amount": 29, "credits": 0, "unlimited_minutes": 60, "payment_for": "unlimited", "label": "1 Hour Unlimited - ₹29"},
    "u1d": {"amount": 60, "credits": 0, "unlimited_minutes": 1440, "payment_for": "unlimited", "label": "1 Day Unlimited - ₹60"},
    "u1w": {"amount": 240, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited - ₹240"},
    "u1m": {"amount": 720, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited - ₹720"},
    "protect_number": {"amount": 59, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection - ₹59"},
    "protect_telegram": {"amount": 59, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Protection - ₹59"},
    "lifetime": {"amount": 0, "credits": 0, "unlimited_minutes": 525600, "payment_for": "unlimited", "label": "Lifetime Free"},
}

def validate_startup_config():
    required_vars = ["BOT_TOKEN", "SUPABASE_URL", "SUPABASE_ANON_KEY"]
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print("❌ Missing required environment variables: " + ", ".join(missing))
        sys.exit(1)
    print("✅ All required environment variables are set")
    print(f"📱 Bot Version: {BOT_VERSION}")
    print(f"👑 Admin ID: {ADMIN_ID}")

validate_startup_config()

# ==================== SUPABASE CLIENT ====================
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

    def delete(self):
        self.method = "DELETE"
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

    def range(self, start, end):
        self.params["offset"] = str(int(start))
        self.params["limit"] = str(int(end) - int(start) + 1)
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

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True)
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_states = {}
user_cooldown = {}
temp_data = {}
payment_session_cooldown = {}
active_sessions = set()
active_sessions_lock = threading.Lock()
proof_forwarded_txs = set()
daily_search_stats = {}
daily_stats_lock = threading.Lock()
IST = timezone(timedelta(hours=5, minutes=30))
MAINTENANCE_MODE = False
last_reminder_sent = {}

# ==================== BRANDING REMOVAL ====================
def remove_branding(data):
    if not isinstance(data, dict):
        return data
    if "branding" in data:
        del data["branding"]
    for key, value in data.items():
        if isinstance(value, dict):
            data[key] = remove_branding(value)
        elif isinstance(value, list):
            data[key] = [remove_branding(item) if isinstance(item, dict) else item for item in value]
    return data

# ==================== UI COMPONENTS ====================
def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 {WEBSITE_URL}\n👨‍💻 @{ADMIN_USERNAME}\n👥 [Community]({GROUP_LINK})"

def header(title, emoji="🚀"):
    return f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━"

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    keyboard.add(
        KeyboardButton("📱 NUMBER INFO"),
        KeyboardButton("💬 TG TO NUM"),
        KeyboardButton("🆔 AADHAAR")
    )
    keyboard.add(
        KeyboardButton("🚗 VEHICLE"),
        KeyboardButton("📷 INSTAGRAM"),
        KeyboardButton("📞 TRUECALLER")
    )
    keyboard.add(
        KeyboardButton("📋 RC LOOKUP"),
        KeyboardButton("🏦 IFSC"),
        KeyboardButton("🧾 GST")
    )
    keyboard.add(
        KeyboardButton("📲 IMEI"),
        KeyboardButton("💳 PAN"),
        KeyboardButton("⚠️ CHALLAN")
    )
    keyboard.add(
        KeyboardButton("💎 MY CREDITS"),
        KeyboardButton("🛒 BUY CREDITS"),
        KeyboardButton("🛡️ PROTECTION")
    )
    keyboard.add(
        KeyboardButton("📢 SUPPORT"),
        KeyboardButton("🎯 REFER & EARN")
    )
    return keyboard

def get_main_keyboard_for_user(user_id):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    keyboard.add(
        KeyboardButton("📱 NUMBER INFO"),
        KeyboardButton("💬 TG TO NUM"),
        KeyboardButton("🆔 AADHAAR")
    )
    keyboard.add(
        KeyboardButton("🚗 VEHICLE"),
        KeyboardButton("📷 INSTAGRAM"),
        KeyboardButton("📞 TRUECALLER")
    )
    keyboard.add(
        KeyboardButton("📋 RC LOOKUP"),
        KeyboardButton("🏦 IFSC"),
        KeyboardButton("🧾 GST")
    )
    keyboard.add(
        KeyboardButton("📲 IMEI"),
        KeyboardButton("💳 PAN"),
        KeyboardButton("⚠️ CHALLAN")
    )
    keyboard.add(
        KeyboardButton("💎 MY CREDITS"),
        KeyboardButton("🛒 BUY CREDITS"),
        KeyboardButton("🛡️ PROTECTION")
    )
    keyboard.add(
        KeyboardButton("📢 SUPPORT"),
        KeyboardButton("🎯 REFER & EARN")
    )
    if str(user_id) == str(ADMIN_ID):
        keyboard.add(KeyboardButton("🛠 ADMIN PANEL"))
    return keyboard

def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton("❌ CANCEL"))
    return keyboard

def get_channel_join_markup_for_missing(missing_channels):
    markup = InlineKeyboardMarkup(row_width=1)
    for channel in missing_channels:
        markup.add(InlineKeyboardButton(f"📢 Join {channel['name']}", url=channel['link']))
    markup.add(InlineKeyboardButton("✅ I HAVE JOINED ALL", callback_data="check_all_join"))
    return markup

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    return markup

def credit_packs_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 50 CR - ₹30", callback_data="plan_c50"),
        InlineKeyboardButton("💰 105 CR - ₹60", callback_data="plan_c100"),
        InlineKeyboardButton("💰 220 CR - ₹120", callback_data="plan_c200"),
        InlineKeyboardButton("💰 550 CR - ₹300", callback_data="plan_c500"),
        InlineKeyboardButton("💰 1150 CR - ₹600", callback_data="plan_c1000")
    )
    markup.add(
        InlineKeyboardButton("🚀 1H - ₹29", callback_data="plan_u1h"),
        InlineKeyboardButton("🚀 1D - ₹60", callback_data="plan_u1d"),
        InlineKeyboardButton("🚀 7D - ₹240", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30D - ₹720", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protect - ₹59", callback_data="plan_protect_number"),
        InlineKeyboardButton("💬 TG Protect - ₹59", callback_data="plan_protect_telegram")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    return markup

def telegram_lookup_protection_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛡️ PROTECT MY TG ID", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔍 NEW LOOKUP", callback_data="back_to_lookup")
    )
    markup.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    return markup

def lookup_result_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW SEARCH", callback_data="back_to_lookup"),
        InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
    )
    markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
    return markup

def escape_html(text):
    """Escape HTML special characters for safe embedding in HTML messages."""
    if text is None:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))

def format_json_for_telegram(data):
    """
    Format JSON data for Telegram using HTML <pre> block.
    <pre> gives a monospace block with tap-to-copy support.
    Returns an HTML-safe string.
    """
    try:
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
        elif isinstance(data, str):
            try:
                parsed = json.loads(data)
                json_str = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                json_str = data
        else:
            json_str = str(data)

        # Escape HTML chars so <pre> content is safe
        json_str = json_str.replace("&", "&amp;")
        json_str = json_str.replace("<", "&lt;")
        json_str = json_str.replace(">", "&gt;")

        return f"<pre>{json_str}</pre>"
    except Exception as e:
        print(f"JSON format error: {e}")
        return f"<pre>{escape_html(str(data))}</pre>"

# ==================== LOOKUP API FUNCTIONS ====================
def call_lookup_api(service, query):
    """
    Call the unified lookup API.
    Returns result dict only (no tuple).
    """
    try:
        url = f"{LOOKUP_API_BASE}?api_key={LOOKUP_API_KEY}&service={service}&query={query}"
        print(f"[LOOKUP API] Service: {service}, Query: {query}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/11.0.11",
            "Accept": "application/json,text/html,text/plain,*/*",
            "Connection": "close",
        }
        response = requests.get(url, headers=headers, timeout=(10, 25))
        print(f"[LOOKUP API] Status: {response.status_code}")
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "raw": response.text[:500]}
        content = response.text
        if not content or len(content.strip()) < 5:
            return {"error": "empty_response"}
        try:
            data = response.json()
            data = remove_branding(data)
            return data
        except Exception:
            return {"raw_response": content}
    except requests.exceptions.Timeout:
        print("[LOOKUP API] Timeout!")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError as ce:
        print(f"[LOOKUP API] Connection error: {ce}")
        return {"error": "connection_error"}
    except Exception as e:
        print(f"[LOOKUP API] Exception: {e}")
        return {"error": f"exception_{e}"}

def has_valid_results(result):
    """Check if API returned valid data"""
    if not isinstance(result, dict):
        return False
    if result.get('error'):
        return False
    no_data_phrases = ['no data found', 'no result', 'not found', 'no query found',
                       'no data', 'no information', 'unable to find', 'not available',
                       'invalid', 'error', 'failed']
    raw = result.get('raw_response')
    if isinstance(raw, str):
        raw_lower = raw.lower()
        for phrase in no_data_phrases:
            if phrase in raw_lower:
                return False
    msg = result.get('message')
    if isinstance(msg, str):
        msg_lower = msg.lower()
        for phrase in no_data_phrases:
            if phrase in msg_lower:
                return False
    if 'results' in result:
        api_results = result.get('results')
        if isinstance(api_results, dict):
            for key, value in api_results.items():
                if isinstance(value, dict) and value:
                    for v in value.values():
                        if v and str(v).strip() and str(v).strip().lower() not in ['none', 'null', 'n/a', '']:
                            return True
                elif value and str(value).strip() and str(value).strip().lower() not in ['none', 'null', 'n/a', '']:
                    return True
        if isinstance(api_results, list):
            for item in api_results:
                if isinstance(item, dict) and item:
                    for v in item.values():
                        if v and str(v).strip() and str(v).strip().lower() not in ['none', 'null', 'n/a', '']:
                            return True
    valid_fields = ['name', 'mobile', 'phone', 'email', 'address', 'city', 'state', 'country',
                    'telegram_id', 'user_id', 'id', 'username', 'first_name', 'last_name',
                    'aadhaar', 'vehicle', 'rc', 'ifsc', 'gst', 'imei', 'pan', 'challan',
                    'owner', 'father_name', 'dob', 'bank', 'branch']
    for field in valid_fields:
        value = result.get(field)
        if value:
            str_value = str(value).strip()
            if str_value and str_value.lower() not in ['none', 'null', 'n/a', '', 'no data', 'not found', 'no result']:
                return True
    for key, value in result.items():
        if key in ['results', 'data', 'response', 'raw_response']:
            continue
        if isinstance(value, dict) and value:
            if has_valid_results(value):
                return True
        elif isinstance(value, list) and value:
            for item in value:
                if isinstance(item, dict) and item:
                    if has_valid_results(item):
                        return True
    return False

def is_no_data_response(result):
    """Check if response indicates no data found"""
    if not isinstance(result, dict):
        return False
    no_data_phrases = ['no data found', 'no result', 'not found', 'no query found',
                       'no data', 'no information', 'unable to find', 'not available']
    raw = result.get('raw_response')
    if isinstance(raw, str):
        raw_lower = raw.lower()
        for phrase in no_data_phrases:
            if phrase in raw_lower:
                return True
    msg = result.get('message')
    if isinstance(msg, str):
        msg_lower = msg.lower()
        for phrase in no_data_phrases:
            if phrase in msg_lower:
                return True
    if 'results' in result:
        api_results = result.get('results')
        if isinstance(api_results, dict):
            has_data = False
            for value in api_results.values():
                if isinstance(value, dict):
                    for v in value.values():
                        if v and str(v).strip() and str(v).strip().lower() not in ['none', 'null', 'n/a', '']:
                            has_data = True
                            break
                elif value and str(value).strip() and str(value).strip().lower() not in ['none', 'null', 'n/a', '']:
                    has_data = True
                    break
            if not has_data:
                return True
        elif isinstance(api_results, list) and not api_results:
            return True
    return False

# ==================== SMART SPLITTING (PRE-BLOCK AWARE) ====================
def split_long_text(text, limit=TELEGRAM_SAFE_LIMIT):
    """
    Split text safely without breaking <pre> blocks.

    If the message wraps a big JSON inside a single <pre>...</pre>,
    we split *inside* the pre block and close/reopen tags per chunk
    so every chunk is a valid HTML fragment. This keeps each part
    copy-friendly (each chunk has its own complete <pre> block).
    """
    text = str(text or "")
    if len(text) <= limit:
        return [text]

    # Detect a single outer <pre> block
    pre_start = text.find("<pre>")
    pre_end = text.rfind("</pre>")

    if pre_start != -1 and pre_end != -1 and pre_start < pre_end:
        before = text[:pre_start]
        inner = text[pre_start + len("<pre>"):pre_end]
        after = text[pre_end + len("</pre>"):]

        overhead = len("<pre></pre>")
        # Reserve enough room for header added later
        chunk_budget = max(500, limit - overhead - 400)

        chunks = []
        lines = inner.split("\n")
        current = ""
        first_chunk = True

        for line in lines:
            candidate = (current + "\n" + line) if current else line
            if len(candidate) > chunk_budget and current:
                # Close this chunk
                prefix = before if first_chunk else ""
                suffix = ""
                body = f"{prefix}<pre>{current}</pre>{suffix}"
                chunks.append(body)
                first_chunk = False
                current = line
            else:
                current = candidate

        if current or first_chunk:
            prefix = before if first_chunk else ""
            body = f"{prefix}<pre>{current}</pre>"
            chunks.append(body)

        # Attach trailing content to the last chunk
        if after and chunks:
            chunks[-1] = chunks[-1] + after

        return chunks if chunks else [text]

    # No <pre> block: standard line-based split
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


def send_or_edit_long_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    """
    Send or edit a long HTML message safely.
    - Each chunk is a complete valid HTML fragment.
    - A "Part X/N" header is prepended when there are multiple chunks.
    """
    chunks = split_long_text(text)
    sent_messages = []
    total = len(chunks)

    for idx, chunk in enumerate(chunks):
        is_first = idx == 0
        is_last = idx == total - 1
        markup = reply_markup if is_last else None

        if total > 1:
            body = f"<b>📄 Part {idx + 1}/{total}</b>\n{chunk}"
        else:
            body = chunk

        # Telegram hard limit is 4096; add safety net
        if len(body) > 4096:
            body = body[:4090] + "…"

        try:
            if is_first:
                sent_messages.append(bot.edit_message_text(
                    body, chat_id, message_id,
                    reply_markup=markup, parse_mode=parse_mode,
                    disable_web_page_preview=True
                ))
            else:
                sent_messages.append(bot.send_message(
                    chat_id, body,
                    reply_markup=markup, parse_mode=parse_mode,
                    disable_web_page_preview=True
                ))
        except Exception as send_error:
            print(f"Long message send error: {send_error}")
            # Fallback: strip HTML tags and send as plain text
            try:
                plain = re.sub(r"<[^>]+>", "", body)
                if len(plain) > 4090:
                    plain = plain[:4090] + "…"
                if is_first:
                    sent_messages.append(bot.edit_message_text(
                        plain, chat_id, message_id,
                        reply_markup=markup, disable_web_page_preview=True
                    ))
                else:
                    sent_messages.append(bot.send_message(
                        chat_id, plain,
                        reply_markup=markup, disable_web_page_preview=True
                    ))
            except Exception as e2:
                print(f"Fallback send failed: {e2}")
    return sent_messages


def safe_edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    """Safely edit a message; falls back to plain text if HTML fails."""
    try:
        return bot.edit_message_text(
            text, chat_id, message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return None
        # Try plain text fallback once
        try:
            plain = re.sub(r"<[^>]+>", "", str(text))
            return bot.edit_message_text(
                plain, chat_id, message_id,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e2:
            print(f"safe_edit_message failed: {e} / fallback: {e2}")
            return None

def is_active_session(user_id):
    with active_sessions_lock:
        return user_id in active_sessions

def add_active_session(user_id):
    with active_sessions_lock:
        active_sessions.add(user_id)

def remove_active_session(user_id):
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== REFERRAL FUNCTIONS ====================
def get_user_referral_data(user_id):
    try:
        response = supabase.table("botrefer").select("*").eq("user_id", str(user_id)).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Get referral data error: {e}")
        return None

def create_referral_data(user_id):
    try:
        existing = get_user_referral_data(user_id)
        if existing:
            return existing
        user = get_user(user_id)
        if not user:
            return None
        new_data = {
            "user_id": str(user_id),
            "referral_code": str(user_id),
            "referral_count": 0,
            "referred_users": [],
            "total_referrals": 0,
            "last_reset": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "claimed_rewards": []
        }
        result = supabase.table("botrefer").insert(new_data).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Create referral data error: {e}")
        return None

def get_user_referral_count(user_id):
    try:
        data = get_user_referral_data(user_id)
        if data:
            return data.get("referral_count", 0)
        return 0
    except Exception as e:
        print(f"Get referral count error: {e}")
        return 0

def is_existing_user(user_id):
    try:
        user = get_user(user_id)
        if user:
            created_at = user.get("created_at")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                    if (datetime.now(timezone.utc) - created_dt).total_seconds() > 300:
                        return True
                except:
                    pass
            return True
        return False
    except Exception as e:
        print(f"Check existing user error: {e}")
        return False

def is_already_referred(user_id):
    try:
        response = supabase.table("botrefer").select("user_id, referred_users").execute()
        for row in response.data:
            referred_users = row.get("referred_users", [])
            if str(user_id) in referred_users:
                return True
        return False
    except Exception as e:
        print(f"Check already referred error: {e}")
        return False

def add_referral(referrer_id, new_user_id):
    try:
        if str(referrer_id) == str(new_user_id):
            return False, "Cannot refer yourself"
        if is_existing_user(new_user_id):
            return False, "User already exists"
        if is_already_referred(new_user_id):
            return False, "User already referred"
        referrer_data = get_user_referral_data(referrer_id)
        if not referrer_data:
            referrer_data = create_referral_data(referrer_id)
            if not referrer_data:
                return False, "Referrer not found"
        referred_users = referrer_data.get("referred_users", [])
        if str(new_user_id) in referred_users:
            return False, "Already referred this user"
        referred_users.append(str(new_user_id))
        new_count = len(referred_users)
        update_data = {
            "referral_count": new_count,
            "referred_users": referred_users,
            "total_referrals": referrer_data.get("total_referrals", 0) + 1,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("botrefer").update(update_data).eq("user_id", str(referrer_id)).execute()
        check_and_award_referral_rewards(referrer_id, new_count)
        try:
            bot.send_message(
                int(referrer_id),
                f"🎉 *New Referral!*\n\n"
                f"📊 Total: `{new_count}`\n\n"
                f"Keep sharing to earn rewards!",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Referral notification error: {e}")
        create_referral_data(new_user_id)
        return True, f"Referral added! Total: {new_count}"
    except Exception as e:
        print(f"Add referral error: {e}")
        return False, str(e)

def check_and_award_referral_rewards(user_id, referral_count):
    try:
        user_data = get_user_referral_data(user_id)
        if not user_data:
            return
        claimed_rewards = user_data.get("claimed_rewards", [])
        sorted_goals = sorted(REFERRAL_GOALS.items())
        for threshold, reward in sorted_goals:
            threshold = int(threshold)
            if referral_count >= threshold and str(threshold) not in claimed_rewards:
                plan_id = reward.get("plan")
                plan_label = reward.get("label")
                if plan_id == "lifetime":
                    ok, new_expiry = activate_unlimited_plan_for_user(user_id, "u1m")
                else:
                    ok, new_expiry = activate_unlimited_plan_for_user(user_id, plan_id)
                if ok:
                    claimed_rewards.append(str(threshold))
                    supabase.table("botrefer").update({
                        "claimed_rewards": claimed_rewards,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("user_id", str(user_id)).execute()
                    try:
                        bot.send_message(
                            int(user_id),
                            f"🏆 *Milestone Unlocked!*\n\n"
                            f"🎁 Reward: *{plan_label}*\n"
                            f"📊 Referrals: `{threshold}`\n\n"
                            f"Keep referring to unlock more!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"Reward notification error: {e}")
                    try:
                        bot.send_message(
                            ADMIN_CHANNEL_ID,
                            f"🏆 *Referral Reward*\n\n"
                            f"👤 `{user_id}`\n"
                            f"📊 Referrals: `{threshold}`\n"
                            f"🎁 *{plan_label}*\n"
                            f"📅 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"Admin notification error: {e}")
    except Exception as e:
        print(f"Check referral rewards error: {e}")

def reset_referral_counts():
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            sleep_seconds = max(60, int((target - now).total_seconds()))
            time.sleep(sleep_seconds)
            if datetime.now(IST).day == 1:
                print("🔄 Resetting referral counts...")
                response = supabase.table("botrefer").select("user_id").execute()
                for row in response.data:
                    supabase.table("botrefer").update({
                        "referral_count": 0,
                        "referred_users": [],
                        "claimed_rewards": [],
                        "last_reset": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("user_id", row.get("user_id")).execute()
                print("✅ Referral counts reset")
                try:
                    bot.send_message(
                        ADMIN_CHANNEL_ID,
                        f"🔄 *Referral Reset*\n\nMonthly reset completed.\n📅 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"Admin notification error: {e}")
        except Exception as e:
            print(f"Reset referral counts error: {e}")
            time.sleep(300)

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

def add_credits(telegram_user_id, amount):
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

def is_value_protected(table_name, column_name, value):
    try:
        response = supabase.table(table_name).select(column_name).eq(column_name, value).limit(1).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Protection check error {table_name}: {e}")
        return False

def is_telegram_protected(telegram_id):
    return is_value_protected("protected_telegrams", "telegram_id", str(telegram_id))

def add_protected_telegram(telegram_id, telegram_user_id=None):
    return add_protected_value("protected_telegrams", "telegram_id", str(telegram_id))

def add_protected_value(table_name, column_name, value):
    try:
        supabase.table(table_name).insert({
            column_name: value,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Add protection error {table_name}: {e}")
        return False

def is_valid_telegram_id(value):
    return bool(re.match(r'^\d{4,15}$', str(value or '').strip()))

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
        protected_resp = supabase.table("protected_numbers").select("*", count="exact").execute()
        protected_count = protected_resp.count
        referrals_resp = supabase.table("botrefer").select("*", count="exact").execute()
        total_referrals = referrals_resp.count if referrals_resp else 0
        return {
            'total_users': total_users,
            'total_searches': total_searches,
            'total_credits': total_credits,
            'banned_users': banned_users,
            'pending_payments': pending_payments_count,
            'total_revenue': total_revenue,
            'protected_count': protected_count,
            'total_referrals': total_referrals
        }
    except Exception as e:
        print(f"Get stats error: {e}")
        return {
            'total_users': 0,
            'total_searches': 0,
            'total_credits': 0,
            'banned_users': 0,
            'pending_payments': 0,
            'total_revenue': 0,
            'protected_count': 0,
            'total_referrals': 0
        }

def get_all_users_batch(limit=1000, offset=0):
    try:
        response = supabase.table("telegram_users").select("telegram_user_id").eq("is_banned", False).range(offset, offset + limit - 1).execute()
        return [row['telegram_user_id'] for row in response.data]
    except Exception as e:
        print(f"Get users batch error: {e}")
        return []

def get_total_users_count():
    try:
        response = supabase.table("telegram_users").select("*", count="exact").eq("is_banned", False).execute()
        return response.count or 0
    except Exception as e:
        print(f"Get total users error: {e}")
        return 0

def add_giveaway_credits(credits):
    try:
        users = []
        offset = 0
        batch_size = 1000
        while True:
            batch = get_all_users_batch(batch_size, offset)
            if not batch:
                break
            users.extend(batch)
            offset += batch_size
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

# ==================== MANUAL QR PAYMENT FUNCTIONS ====================
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
            "credits": plan["credits"],
            "payment_source": "manual_qr",
            "payment_for": plan["payment_for"],
            "protected_number": protected_number,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "raw_response": {
                "mode": "manual_static_qr",
                "note": "Admin must verify this payment manually."
            }
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
            return True, f"Unlimited until {new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC"
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
            except Exception as e:
                print(f"Manual verify lookup skipped {field}: {e}")
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
            "raw_response": {
                "mode": "manual_static_qr",
                "verified_by": str(admin_id or ADMIN_ID),
                "verified_at": now,
                "detail": detail
            }
        }).eq("id", claim.get("id")).execute()
        telegram_user_id = int(claim.get("telegram_user_id"))
        try:
            bot.send_message(
                telegram_user_id,
                f"✅ *Payment Verified!*\n\n{detail}\n\n🧾 `{tx_code}`\n\nUse /start to refresh.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"User payment verified message failed: {e}")
        try:
            bot.send_message(
                ADMIN_CHANNEL_ID,
                f"✅ *Payment Verified*\n\n"
                f"👤 `{telegram_user_id}`\n"
                f"📦 `{claim.get('plan_id')}`\n"
                f"💰 ₹{claim.get('amount')}\n"
                f"🧾 `{tx_code}`\n"
                f"🛠 By: `{admin_id or ADMIN_ID}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Admin channel verify log failed: {e}")
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
            except Exception as e:
                print(f"Manual reject lookup skipped {field}: {e}")
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
            "raw_response": {
                "mode": "manual_static_qr",
                "rejected_by": str(admin_id or ADMIN_ID),
                "rejected_at": now,
                "reason": reason
            }
        }).eq("id", claim.get("id")).execute()
        telegram_user_id = int(claim.get("telegram_user_id"))
        try:
            bot.send_message(
                telegram_user_id,
                f"❌ *Payment Rejected*\n\n"
                f"🧾 `{tx_code}`\n"
                f"Reason: `{reason}`\n\n"
                f"Contact admin: @{ADMIN_USERNAME}",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"User reject message failed: {e}")
        try:
            bot.send_message(
                ADMIN_CHANNEL_ID,
                f"❌ *Payment Rejected*\n\n"
                f"👤 `{telegram_user_id}`\n"
                f"📦 `{claim.get('plan_id')}`\n"
                f"💰 ₹{claim.get('amount')}\n"
                f"🧾 `{tx_code}`\n"
                f"🛠 By: `{admin_id or ADMIN_ID}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Admin channel reject log failed: {e}")
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
            except Exception as e:
                print(f"Payment status lookup skipped {field}: {e}")
        return None
    except Exception as e:
        print(f"Get payment status error: {e}")
        return None

def payment_session_reminder_worker(chat_id, user_id, tx_code, plan_label):
    try:
        time.sleep(60)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"⏰ *Payment Reminder*\n\n"
                f"🧾 `{tx_code}`\n"
                f"📦 `{plan_label}`\n\n"
                f"Share payment screenshot for admin verification.",
                parse_mode="Markdown"
            )
        time.sleep(60)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"✅ *Your payment is safe!*\n\n"
                f"🧾 `{tx_code}`\n\n"
                f"Share screenshot to complete verification.\n"
                f"No auto-rejection.",
                parse_mode="Markdown"
            )
        time.sleep(60)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"📌 *Reminder*\n\n"
                f"🧾 `{tx_code}`\n\n"
                f"Payment session still pending.\n"
                f"Share screenshot for verification.",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Payment reminder worker error for {tx_code}: {e}")

def send_manual_qr_payment(chat_id, user_id, username, plan_id, protected_number=None):
    plan = get_plan_config(plan_id)
    if not plan:
        bot.send_message(chat_id, "❌ Invalid plan.", reply_markup=get_main_keyboard_for_user(user_id))
        return
    now_ts = time.time()
    last_ts = payment_session_cooldown.get(user_id, 0)
    remaining = int(PAYMENT_SESSION_COOLDOWN_SECONDS - (now_ts - last_ts))
    if remaining > 0:
        bot.send_message(chat_id, f"⏳ *Wait {remaining}s* for new QR session.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode="Markdown")
        return
    payment_session_cooldown[user_id] = now_ts
    tx_code = create_manual_payment_claim(plan_id, user_id, username, protected_number)
    if not tx_code:
        bot.send_message(chat_id, f"❌ Failed. Contact @{ADMIN_USERNAME}.", parse_mode="Markdown")
        return
    extra = f"\n📱 `{protected_number}`" if protected_number else ""
    caption = f"""
💳 *Scan & Pay*
━━━━━━━━━━━━━━━━━━
💰 ₹{plan['amount']}
📦 `{plan['label']}`{extra}
🧾 `{tx_code}`

Send payment screenshot for verification.

━━━━━━━━━━━━━━━━━━
📞 @{ADMIN_USERNAME}
"""
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
            bot.send_message(
                chat_id,
                caption + "\n⚠️ QR file missing. Add `payment_qr.png`.",
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Send QR failed: {e}")
        bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )
    send_admin_alert(
        f"💳 *New QR Payment*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 `{user_id}`\n"
        f"📦 `{plan_id}`\n"
        f"💰 ₹{plan['amount']}\n"
        f"🧾 `{tx_code}`\n"
        f"📱 `{protected_number if protected_number else 'N/A'}`\n\n"
        f"Verify after checking screenshot.",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )
    threading.Thread(
        target=payment_session_reminder_worker,
        args=(chat_id, user_id, tx_code, plan.get("label", plan_id)),
        daemon=True
    ).start()

# ==================== DAILY SEARCH REPORT ====================
def record_search_for_daily_report(user_id, username, first_name, query_value, found=True, lookup_type="numberinfo", credits_used=0):
    try:
        key = str(user_id)
        with daily_stats_lock:
            row = daily_search_stats.setdefault(key, {
                "user_id": user_id,
                "username": username or "no_username",
                "first_name": first_name or "User",
                "searches": 0,
                "numberinfo_searches": 0,
                "telegram_searches": 0,
                "credits_used": 0,
                "found": 0,
                "not_found": 0,
                "last_query": ""
            })
            row["searches"] += 1
            row["last_query"] = query_value
            row["credits_used"] += int(credits_used or 0)
            if lookup_type == "tg2num":
                row["telegram_searches"] = row.get("telegram_searches", 0) + 1
            else:
                row["numberinfo_searches"] = row.get("numberinfo_searches", 0) + 1
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
    credits_used = sum(v.get("credits_used", 0) for v in stats_snapshot.values())
    top = sorted(stats_snapshot.values(), key=lambda x: x.get("searches", 0), reverse=True)[:10]
    lines = [
        "📊 *TRACEX 24H REPORT*",
        "━━━━━━━━━━━━━━━━",
        f"🕕 `{datetime.now(IST).strftime('%Y-%m-%d 06:00 IST')}`",
        f"👥 Users: `{total_users}`",
        f"🔍 Lookups: `{total_searches}`",
        f"💎 Credits: `{credits_used}`",
        f"✅ Found: `{found}`",
        f"❌ No Data: `{not_found}`",
        "",
        "🏆 *TOP SEARCHERS*"
    ]
    if not top:
        lines.append("No searches in last 24h.")
    else:
        for i, row in enumerate(top, 1):
            uname = row.get("username") or "no_username"
            display = f"@{uname}" if uname != "no_username" else row.get("first_name", "User")
            lines.append(f"{i}. {display} | `{row.get('searches', 0)}` lookups | 💎 `{row.get('credits_used', 0)}`")
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

# ==================== WEBSITE REGISTRATION REMINDER ====================
def send_website_registration_reminder(user_id):
    try:
        user = get_user(user_id)
        if not user:
            return
        reminder_msg = f"""
🌐 *REGISTER ON WEBSITE*
━━━━━━━━━━━━━━━━━━

✅ Better lookup results
✅ Instant payment success
✅ Lower rates
✅ API access

━━━━━━━━━━━━━━━━━━

👉 [Register Now]({WEBSITE_REGISTRATION_URL})

💎 *Benefits:*
• 10 Free Credits
• Instant Verification
• Lower Rates

━━━━━━━━━━━━━━━━━━
📞 @{ADMIN_USERNAME}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🌐 REGISTER", url=WEBSITE_REGISTRATION_URL))
        markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
        bot.send_message(user_id, reminder_msg, reply_markup=markup, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        print(f"Failed to send reminder to {user_id}: {e}")

def send_bulk_reminders():
    while True:
        try:
            users = []
            offset = 0
            batch_size = 1000
            while True:
                batch = get_all_users_batch(batch_size, offset)
                if not batch:
                    break
                users.extend(batch)
                offset += batch_size
            print(f"📢 Sending reminders to {len(users)} users...")
            for user_id in users:
                last_time = last_reminder_sent.get(user_id, 0)
                if time.time() - last_time >= REMINDER_INTERVAL_HOURS * 3600:
                    send_website_registration_reminder(user_id)
                    last_reminder_sent[user_id] = time.time()
                    time.sleep(0.5)
            print(f"✅ Reminders sent for this cycle")
            time.sleep(REMINDER_INTERVAL_HOURS * 3600)
        except Exception as e:
            print(f"Reminder loop error: {e}")
            time.sleep(300)

# ==================== ADMIN ALERTS ====================
def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    sent = False
    try:
        bot.send_message(ADMIN_CHANNEL_ID, text, reply_markup=reply_markup, parse_mode=parse_mode)
        sent = True
    except Exception as e:
        print(f"Admin channel alert failed: {e}")
    if not sent:
        try:
            bot.send_message(ADMIN_ID, "⚠️ Fallback:\n\n" + text, reply_markup=reply_markup, parse_mode=parse_mode)
            sent = True
        except Exception as e:
            print(f"Admin DM fallback failed: {e}")
    return sent

# ==================== CHANNEL MEMBERSHIP CHECK ====================
def is_channel_member(user_id, channel_username):
    if str(user_id) == str(ADMIN_ID):
        return True
    try:
        member = bot.get_chat_member(channel_username, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Channel membership check error for {user_id} on {channel_username}: {e}")
        return False

def check_all_channels(user_id):
    if str(user_id) == str(ADMIN_ID):
        return True, []
    missing = []
    for channel in REQUIRED_CHANNELS:
        if not is_channel_member(user_id, channel['username']):
            missing.append(channel)
    return len(missing) == 0, missing

def send_join_required(chat_id, missing_channels=None):
    if missing_channels is None:
        all_joined, missing_channels = check_all_channels(chat_id)
        if all_joined:
            return True
    if missing_channels:
        channel_list = "\n".join([f"• {ch['name']}: {ch['link']}" for ch in missing_channels])
        message = f"""
🔒 *JOIN REQUIRED*
━━━━━━━━━━━━━━━━━━

Join these channels to use the bot:

{channel_list}

⚠️ If you left after joining, rejoin.

After joining, tap ✅ button below.

━━━━━━━━━━━━━━━━━━
📢 *Benefits:*
• Latest updates
• Support access
• Exclusive features
"""
        bot.send_message(
            chat_id,
            message,
            reply_markup=get_channel_join_markup_for_missing(missing_channels),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return False
    return True

# ==================== FORMATTING FUNCTIONS ====================
def format_lookup_result(result, service_key, query_value, user_id, unlimited_active=False, unlimited_expiry=None):
    """
    Build the lookup result message as HTML.
    JSON is rendered inside a <pre> block for clean wrapping + tap-to-copy.
    """
    service = LOOKUP_SERVICES.get(service_key, {})
    service_name = service.get("name", service_key)
    emoji = service.get("emoji", "🔍")
    cost = service.get("cost", 3)

    if not isinstance(result, dict):
        result = {"response": str(result)}

    json_output = format_json_for_telegram(result)
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    total_searches = user.get('total_searches', 0) if user else 0
    safe_query = escape_html(query_value)

    output = f"""<b>{emoji} {service_name.upper()}</b>
━━━━━━━━━━━━━━━━━━

🔎 Query: <code>{safe_query}</code>

📄 <b>Result:</b>
{json_output}
"""

    if unlimited_active:
        exp = escape_html(unlimited_expiry[:16] if unlimited_expiry else "N/A")
        output += f"""

━━━━━━━━━━━━━━━━━━
🚀 <b>UNLIMITED ACTIVE</b>
No credits deducted.
Expires: <code>{exp}</code>
"""
    else:
        output += f"""

━━━━━━━━━━━━━━━━━━
💎 Used: <code>{cost}</code>
💎 Left: <code>{updated_total}</code>
🔎 Total: <code>{total_searches}</code>"""

    output += f"""
{footer()}
"""
    return output

# ==================== PROTECTION MENU ====================
def show_protection_menu(message):
    user_id = message.from_user.id
    text = f"""
🛡️ *PROTECTION SERVICES*
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹59
💬 Telegram Protection → ₹59

Protected data hidden from lookup results.
"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📱 PROTECT NUMBER - ₹59", callback_data="plan_protect_number"))
    markup.add(InlineKeyboardButton("💬 PROTECT TELEGRAM - ₹59", callback_data="plan_protect_telegram"))
    markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def process_protection_payment_input(message, plan_id):
    user_id = message.from_user.id
    if message.text == "❌ CANCEL" or message.text == "/cancel":
        user_states.pop(user_id, None)
        remove_active_session(user_id)
        bot.reply_to(message, "❌ Cancelled.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_protection_input" and state.get("plan_id") == plan_id):
        return
    user_states.pop(user_id, None)
    value = str(message.text or "").strip()
    if plan_id == "protect_number":
        if not re.match(r'^[6-9]\d{9}$', value):
            bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            remove_active_session(user_id)
            return
        if is_number_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            remove_active_session(user_id)
            return
    elif plan_id == "protect_telegram":
        if not is_valid_telegram_id(value):
            bot.reply_to(message, "❌ *Invalid Telegram ID!*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            remove_active_session(user_id)
            return
        if is_telegram_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            remove_active_session(user_id)
            return
    else:
        bot.reply_to(message, "❌ Invalid plan.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        remove_active_session(user_id)
        return
    send_manual_qr_payment(message.chat.id, user_id, message.from_user.username or "no_username", plan_id, protected_number=value)

# ==================== PAYMENT HANDLERS ====================
def show_credit_packs(message, user_id):
    packs_msg = f"""
💎 *CREDIT STORE*
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS (1 Credit = ₹1)*
• 50 CR → ₹30
• 105 CR → ₹60
• 220 CR → ₹120
• 550 CR → ₹300
• 1150 CR → ₹600

🚀 *UNLIMITED PLANS*
• 1 Hour → ₹29
• 1 Day → ₹60
• 7 Days → ₹240
• 30 Days → ₹720

🛡️ *PROTECTION*
• Number Protect → ₹59
• Telegram Protect → ₹59

━━━━━━━━━━━━━━━━━━
✅ Credits Never Expire
✅ Manual Verification
✅ Website: {WEBSITE_URL}

👇 Select a plan
{footer()}
"""
    bot.send_message(message.chat.id, packs_msg, reply_markup=credit_packs_markup(), parse_mode='Markdown')

def handle_plan_selection(call):
    plan_id = call.data.replace("plan_", "")
    user_id = call.from_user.id
    username = call.from_user.username or "no_username"
    plan = PLAN_CONFIG.get(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Invalid plan.", show_alert=True)
        return
    if plan_id in ["protect_number", "protect_telegram"]:
        labels = {
            "protect_number": ("📱 *NUMBER PROTECTION*", "Enter 10-digit mobile number:", "`Example: 9876543210`"),
            "protect_telegram": ("💬 *TELEGRAM PROTECTION*", "Enter numeric Telegram user ID:", "`Example: 7850023357`")
        }
        title, prompt, example = labels[plan_id]
        user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
        msg = bot.send_message(
            call.message.chat.id,
            f"""{title}

{prompt}

{example}

💰 Price: `₹59`

QR will be created after this.

Type /cancel to abort""",
            reply_markup=cancel_button(),
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_protection_payment_input, plan_id)
        bot.answer_callback_query(call.id)
        return
    bot.answer_callback_query(call.id, "Sending QR...")
    send_manual_qr_payment(call.message.chat.id, user_id, username, plan_id)

# ==================== REFERRAL HANDLERS ====================
def show_referral_menu(message):
    user_id = message.from_user.id
    referral_data = create_referral_data(user_id)
    if not referral_data:
        bot.reply_to(message, "❌ Failed to load referral data.", reply_markup=get_main_keyboard_for_user(user_id))
        return
    referral_count = referral_data.get("referral_count", 0)
    referred_users = referral_data.get("referred_users", [])
    claimed_rewards = referral_data.get("claimed_rewards", [])
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    next_goal = None
    for threshold in sorted(REFERRAL_GOALS.keys()):
        if referral_count < threshold and str(threshold) not in claimed_rewards:
            next_goal = {"threshold": threshold, "label": REFERRAL_GOALS[threshold]["label"]}
            break
    progress_msg = f"""
🎯 *REFER & EARN*
━━━━━━━━━━━━━━━━━━

📊 *Your Stats:*
• Referrals: `{referral_count}`
• Rewards Claimed: `{len(claimed_rewards)}`

🔗 *Your Link:*
`{referral_link}`

━━━━━━━━━━━━━━━━━━
🏆 *REWARDS:*

3 → 🚀 1 Hour Unlimited
15 → 🚀 1 Day Unlimited
70 → 🚀 7 Days Unlimited
200 → 🚀 30 Days Unlimited
1000 → 👑 Lifetime Free

━━━━━━━━━━━━━━━━━━
"""
    if next_goal:
        progress_msg += f"""
🎯 *Next Goal:*
`{next_goal['threshold'] - referral_count}` more referrals for:
*{next_goal['label']}*

━━━━━━━━━━━━━━━━━━
"""
    else:
        progress_msg += """
🎉 *All Rewards Claimed!*
Keep referring!

━━━━━━━━━━━━━━━━━━
"""
    if referred_users:
        progress_msg += f"""
📋 *Recent Referrals:*
"""
        for i, ref_user in enumerate(referred_users[-10:], 1):
            try:
                user_info = get_user(int(ref_user))
                if user_info:
                    name = user_info.get("telegram_name", "User")
                    progress_msg += f"{i}. {name} (`{ref_user}`)\n"
                else:
                    progress_msg += f"{i}. User `{ref_user}`\n"
            except:
                progress_msg += f"{i}. User `{ref_user}`\n"
    else:
        progress_msg += "\n📋 *No referrals yet*\nShare your link!"
    progress_msg += f"""
{footer()}
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 COPY LINK", callback_data=f"copy_referral_{user_id}"))
    markup.add(InlineKeyboardButton("📤 SHARE", callback_data=f"share_referral_{user_id}"))
    markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
    bot.send_message(message.chat.id, progress_msg, reply_markup=markup, parse_mode='Markdown', disable_web_page_preview=True)

# ==================== ANIMATED LOADING ====================
def update_loading_animation(chat_id, message_id, stage, emoji="🔍"):
    dots = ["", ".", "..", "..."]
    dot = dots[stage % 4]
    try:
        bot.edit_message_text(f"{emoji} *Searching{dot}*", chat_id, message_id, parse_mode='Markdown')
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        elif "message to edit not found" in err or "message can't be edited" in err or "message identifier is not specified" in err:
            return False
        else:
            print(f"Animation update error: {e}")
            return True

def animated_loading(chat_id, message_id, stop_event, emoji="🔍"):
    stage = 0
    while not stop_event.is_set():
        try:
            should_continue = update_loading_animation(chat_id, message_id, stage, emoji)
            if not should_continue:
                return
            stage += 1
            for _ in range(5):
                if stop_event.is_set():
                    return
                time.sleep(0.1)
        except Exception as e:
            print(f"Animation thread stopping: {e}")
            return

def stop_animation_safely(stop_event, thread):
    try:
        stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=3)
    except Exception as e:
        print(f"Stop animation error: {e}")

# ==================== FIXED: PROCESS LOOKUP FUNCTION ====================
def process_lookup(message):
    """
    Unified lookup handler for all 12 services.
    Handles validation, credit deduction, API call, and result display.
    Uses HTML parse mode for JSON-safe results.
    """
    user_id = message.from_user.id
    query_input = str(message.text or "").strip()

    if query_input == "❌ CANCEL" or query_input == "/cancel":
        user_states.pop(user_id, None)
        remove_active_session(user_id)
        bot.reply_to(message, "❌ Cancelled.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_lookup_query"):
        return

    service_key = state.get("service")
    user_states.pop(user_id, None)

    service = LOOKUP_SERVICES.get(service_key)
    if not service:
        bot.reply_to(message, "❌ Invalid service.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    # Validate query based on service type
    query_clean = query_input
    query_type = service.get("query_type")

    if query_type == "mobile":
        phone = normalize_indian_mobile(query_input)
        if not phone:
            bot.reply_to(message, f"❌ *Invalid mobile number!*\n\nEnter 10-digit Indian number.\nExample: `{service.get('placeholder', '9876543210')}`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        query_clean = phone
    elif query_type == "username":
        if not query_input.startswith('@'):
            query_clean = '@' + query_input
        else:
            query_clean = query_input
    elif query_type == "aadhaar":
        if not re.match(r'^\d{12}$', query_input):
            bot.reply_to(message, "❌ *Invalid Aadhaar!*\n\nEnter 12-digit Aadhaar number.\nExample: `123456789012`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    elif query_type == "vehicle":
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$', query_input.upper()):
            bot.reply_to(message, "❌ *Invalid vehicle number!*\n\nEnter valid format.\nExample: `BR06PE8167`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        query_clean = query_input.upper()
    elif query_type == "ifsc":
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', query_input.upper()):
            bot.reply_to(message, "❌ *Invalid IFSC code!*\n\nEnter valid 11-character IFSC.\nExample: `SBIN0001234`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        query_clean = query_input.upper()
    elif query_type == "gst":
        if not re.match(r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$', query_input.upper()):
            bot.reply_to(message, "❌ *Invalid GST number!*\n\nEnter valid 15-character GST.\nExample: `22AAAAA0000A1Z5`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        query_clean = query_input.upper()
    elif query_type == "imei":
        if not re.match(r'^\d{15}$', query_input):
            bot.reply_to(message, "❌ *Invalid IMEI!*\n\nEnter 15-digit IMEI number.\nExample: `353010111111110`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    elif query_type == "pan":
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', query_input.upper()):
            bot.reply_to(message, "❌ *Invalid PAN!*\n\nEnter valid 10-character PAN.\nExample: `AAYFK4129N`",
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        query_clean = query_input.upper()

    if is_active_session(user_id):
        bot.reply_to(message, "⏳ *Search already running!*\n\nWait for current search.",
                     reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Wait {wait_time}s*",
                         reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return

    add_active_session(user_id)

    loading_msg = None
    stop_animation = threading.Event()
    animation_thread = None

    try:
        user = get_user(user_id)
        total_credits = get_total_credits(user_id)
        unlimited_active, unlimited_expiry = get_active_unlimited(user)
        cost = service.get("cost", 3)

        if total_credits < cost and not unlimited_active:
            bot.reply_to(message, f"❌ *Insufficient credits!*\n\n{service.get('name')} costs `{cost}` credits.\nYou have `{total_credits}`.\n\nBuy more credits or get unlimited plan.\n\n🌐 {WEBSITE_URL}",
                         reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown', disable_web_page_preview=True)
            return

        # Check protection for number lookup
        if service_key == "numberinfo" and is_number_protected(query_clean):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🛡️ PROTECT MY NUMBER", callback_data="protect"))
            markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
            bot.reply_to(message, f"""
🛡️ *PROTECTED NUMBER*

📱 `{query_clean}`

This number is protected.

Details hidden.

Protect your number for ₹59!
""", reply_markup=markup, parse_mode='Markdown')
            return

        user_cooldown[user_id] = time.time()
        loading_msg = bot.reply_to(message, f"{service.get('emoji', '🔍')} *Searching...*", parse_mode='Markdown')

        animation_thread = threading.Thread(
            target=animated_loading,
            args=(message.chat.id, loading_msg.message_id, stop_animation, service.get('emoji', '🔍')),
            daemon=True
        )
        animation_thread.start()

        time.sleep(0.8)

        try:
            result = call_lookup_api(service_key, query_clean)
        except Exception as api_err:
            print(f"Lookup API exception: {api_err}")
            result = {"error": f"api_exception_{api_err}"}

        stop_animation_safely(stop_animation, animation_thread)

        if is_no_data_response(result):
            output = f"""<b>❌ NO DATA FOUND</b>
━━━━━━━━━━━━━━━━━━

{service.get('emoji', '🔍')} Query: <code>{escape_html(query_clean)}</code>

No information found.
Please verify the query and try again.

💎 Credits NOT deducted
{footer()}
"""
            safe_edit_message(message.chat.id, loading_msg.message_id, output, parse_mode='HTML')
            record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query_clean, found=False, lookup_type=service_key, credits_used=0)
            return

        if not result or result.get('error'):
            output = f"""<b>❌ API RESPONSE</b>
━━━━━━━━━━━━━━━━━━

{service.get('emoji', '🔍')} Query: <code>{escape_html(query_clean)}</code>

📄 <b>Response:</b>
{format_json_for_telegram(result or {"error": "No response"})}

💎 Credits NOT deducted
{footer()}
"""
            safe_edit_message(message.chat.id, loading_msg.message_id, output, parse_mode='HTML')
            record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query_clean, found=False, lookup_type=service_key, credits_used=0)
            return

        if not isinstance(result, dict):
            result = {"response": str(result)}

        if has_valid_results(result):
            if not unlimited_active:
                if not deduct_credits(user_id, cost):
                    safe_edit_message(message.chat.id, loading_msg.message_id, "❌ <b>Failed to deduct credit. Please try again.</b>", parse_mode='HTML')
                    return
            increment_total_searches(user_id)
            output = format_lookup_result(result, service_key, query_clean, user_id, unlimited_active, unlimited_expiry)
            send_or_edit_long_message(
                message.chat.id,
                loading_msg.message_id,
                output,
                reply_markup=lookup_result_markup(),
                parse_mode='HTML'
            )
            record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query_clean, found=True, lookup_type=service_key, credits_used=cost if not unlimited_active else 0)
        else:
            if not unlimited_active:
                if not deduct_credits(user_id, cost):
                    safe_edit_message(message.chat.id, loading_msg.message_id, "❌ <b>Failed to deduct credit. Please try again.</b>", parse_mode='HTML')
                    return
            increment_total_searches(user_id)
            updated_total = get_total_credits(user_id)
            output = f"""<b>{service.get('emoji', '🔍')} {service.get('name', service_key).upper()}</b>
━━━━━━━━━━━━━━━━━━

Query: <code>{escape_html(query_clean)}</code>

📄 <b>API Response:</b>
{format_json_for_telegram(result)}

━━━━━━━━━━━━━━━━━━
💎 Used: <code>{0 if unlimited_active else cost}</code>
💎 Left: <code>{updated_total}</code>
{footer()}
"""
            send_or_edit_long_message(
                message.chat.id,
                loading_msg.message_id,
                output,
                parse_mode='HTML'
            )
            record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query_clean, found=False, lookup_type=service_key, credits_used=cost if not unlimited_active else 0)

    except Exception as e:
        print(f"process_lookup critical error: {e}")
        try:
            if loading_msg:
                safe_edit_message(
                    message.chat.id,
                    loading_msg.message_id,
                    f"❌ <b>Search failed!</b>\n\nError: <code>{escape_html(str(e)[:100])}</code>\n\nCredits NOT deducted.\nPlease try again.",
                    parse_mode='HTML'
                )
            else:
                bot.reply_to(message, "❌ *Search failed!* Please try again.",
                             parse_mode='Markdown')
        except Exception as inner:
            print(f"Error notifying user: {inner}")

    finally:
        stop_animation_safely(stop_animation, animation_thread)
        remove_active_session(user_id)

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    args = message.text.split()
    referrer_id = None
    is_referral = False
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == user_id:
                referrer_id = None
            else:
                is_referral = True
        except:
            pass
    existing_user = get_user(user_id)
    is_new_user = existing_user is None
    if is_new_user:
        user = get_user(user_id)
    else:
        user = existing_user
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 *BANNED*\n\nContact: @{ADMIN_USERNAME}", parse_mode='Markdown')
        return
    if is_referral and referrer_id and is_new_user:
        if not is_already_referred(user_id):
            ok, msg = add_referral(referrer_id, user_id)
            if ok:
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 *Welcome!*\n\nYou were referred!\nUse /start to explore.\n\n💎 10 free credits!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"Welcome message error: {e}")
    all_joined, missing = check_all_channels(user_id)
    if not all_joined and str(user_id) != str(ADMIN_ID):
        send_join_required(message.chat.id, missing)
        return
    total_credits = get_total_credits(user_id)
    unlimited_expiry = user.get('unlimited_expiry') if user else None
    unlimited_text = ""
    if unlimited_expiry:
        try:
            if isinstance(unlimited_expiry, str):
                expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
            else:
                expiry_date = unlimited_expiry
            if expiry_date > datetime.now(timezone.utc):
                unlimited_text = f"\n🚀 Unlimited: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
        except:
            pass
    referral_count = get_user_referral_count(user_id)
    referral_text = f"\n🎯 Referrals: `{referral_count}`" if referral_count > 0 else ""
    welcome_msg = f"""
{header("TRACEX LOOKUP", "🚀")}

👋 *{first_name}*

💎 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Searches:* `{user.get('total_searches', 0) if user else 0}`{referral_text}

━━━━━━━━━━━━━━━━
📋 *LOOKUP SERVICES:*

📱 Mobile Info — ₹3
💬 TG to Number — ₹5
🆔 Aadhaar — ₹15
🚗 Vehicle — ₹10
📷 Instagram — ₹10
📞 Truecaller — ₹10
📋 RC — ₹10
🏦 IFSC — ₹5
🧾 GST — ₹20
📲 IMEI — ₹10
💳 PAN — ₹20
⚠️ Challan — ₹10

━━━━━━━━━━━━━━━━
🎁 *Refer & Earn:*
3→1H | 15→1D | 70→7D | 200→30D | 1000→Lifetime

🌐 *Website:* {WEBSITE_URL}

👇 Choose a service
{footer()}
"""
    bot.send_message(message.chat.id, welcome_msg, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown', disable_web_page_preview=True)

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    remove_active_session(user_id)
    bot.reply_to(message, "❌ Cancelled.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

@bot.message_handler(commands=['resetcooldown'])
def reset_cooldown(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    user_cooldown.clear()
    with active_sessions_lock:
        active_sessions.clear()
    bot.reply_to(message, "✅ Cooldowns cleared!")

@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(message):
    global MAINTENANCE_MODE
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage:\n/maintenance on\n/maintenance off")
        return
    mode = parts[1].lower()
    if mode == "on":
        MAINTENANCE_MODE = True
        bot.reply_to(message, "🛠 Maintenance ENABLED")
    elif mode == "off":
        MAINTENANCE_MODE = False
        bot.reply_to(message, "✅ Maintenance DISABLED")
    else:
        bot.reply_to(message, "Invalid! Use on/off")

@bot.message_handler(commands=['verify'])
def verify_command(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /verify TXCODE")
            return
        tx_code = parts[1].strip()
        ok, msg = manual_verify_payment(tx_code, message.from_user.id)
        if ok:
            bot.reply_to(message, f"✅ {msg}")
        else:
            bot.reply_to(message, f"❌ {msg}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['reject'])
def reject_command(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /reject TXCODE reason")
            return
        tx_code = parts[1].strip()
        reason = parts[2].strip() if len(parts) > 2 else "Payment not confirmed"
        ok, msg = manual_reject_payment(tx_code, message.from_user.id, reason)
        bot.reply_to(message, f"{'✅' if ok else '❌'} {msg}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['apitest'])
def admin_api_test(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    parts = str(message.text or "").split()
    service = parts[1] if len(parts) > 1 else "numberinfo"
    query = parts[2] if len(parts) > 2 else "9876543210"
    bot.reply_to(message, f"🧪 Testing {service}...")
    result = call_lookup_api(service, query)
    if result and not result.get('error'):
        bot.reply_to(message, f"✅ OK\n<pre>{escape_html(str(result)[:200])}</pre>", parse_mode="HTML")
    else:
        bot.reply_to(message, f"❌ Failed\n<pre>{escape_html(str(result)[:200])}</pre>", parse_mode="HTML")

@bot.message_handler(content_types=['photo', 'document'])
def payment_screenshot_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_payment_screenshot"):
        return
    tx_code = state.get("tx_code")
    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, f"✅ Already sent for `{tx_code}`.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
        return
    proof_forwarded_txs.add(tx_code)
    plan_name = "Unknown"
    try:
        for field in ["session_id", "payment_id", "cashfree_order_id"]:
            try:
                claim_resp = supabase.table("payment_claims").select("plan_id").eq(field, tx_code).limit(1).execute()
                if claim_resp.data:
                    plan_data = claim_resp.data[0]
                    plan_id = plan_data.get("plan_id", "")
                    if plan_id:
                        plan_config = PLAN_CONFIG.get(plan_id, {})
                        plan_name = plan_config.get("label", plan_id)
                    break
            except Exception:
                pass
    except Exception:
        pass
    caption = f"""📸 *Screenshot Received*
━━━━━━━━━━━━━━━━━━
👤 `{user_id}` @{message.from_user.username if message.from_user.username else 'no_username'}
📦 `{plan_name}`
🧾 `{tx_code}`
━━━━━━━━━━━━━━━━━━
⚠️ Verify after checking payment"""
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )
    try:
        try:
            bot.forward_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        except Exception as forward_error:
            print(f"Admin group forward failed: {forward_error}")
            try:
                bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            except Exception as dm_forward_error:
                print(f"Admin DM forward failed: {dm_forward_error}")
        send_admin_alert(caption, reply_markup=admin_markup, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Sent to admin.\n\n🧾 `{tx_code}`\n📦 `{plan_name}`\n⏳ Wait for verification.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        print(f"Payment screenshot forward error: {e}")
        bot.reply_to(message, f"❌ Failed. Contact @{ADMIN_USERNAME}", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

# ==================== TEXT MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def text_handler(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 *BANNED*\n\nContact: @{ADMIN_USERNAME}", parse_mode='Markdown')
        return
    all_joined, missing = check_all_channels(user_id)
    if not all_joined and str(user_id) != str(ADMIN_ID):
        send_join_required(message.chat.id, missing)
        return
    text = message.text.strip()
    
    # Check for dict state with "awaiting_lookup_query"
    state = user_states.get(user_id)
    if isinstance(state, dict) and state.get("state") == "awaiting_lookup_query":
        process_lookup(message)
        return
    elif isinstance(state, dict) and state.get("state") == "awaiting_protection_input":
        plan_id = state.get("plan_id")
        if plan_id:
            process_protection_payment_input(message, plan_id)
        return
    
    # Map button text to service keys
    service_buttons = {
        "📱 NUMBER INFO": "numberinfo",
        "💬 TG TO NUM": "tg2num",
        "🆔 AADHAAR": "aadhaar",
        "🚗 VEHICLE": "vehicle",
        "📷 INSTAGRAM": "instagram",
        "📞 TRUECALLER": "truecaller",
        "📋 RC LOOKUP": "rc",
        "🏦 IFSC": "ifsc",
        "🧾 GST": "gst",
        "📲 IMEI": "imei",
        "💳 PAN": "pan",
        "⚠️ CHALLAN": "challan"
    }
    
    if text in service_buttons:
        service_key = service_buttons[text]
        service = LOOKUP_SERVICES.get(service_key, {})
        user_states[user_id] = {"state": "awaiting_lookup_query", "service": service_key}
        bot.reply_to(message, f"{service.get('emoji', '🔍')} *{service.get('name', service_key)}*\n\nEnter {service.get('query_type', 'query')}:\n`{service.get('placeholder', '')}`\n\n💎 Cost: `{service.get('cost', 3)} credits`\n\nType ❌ CANCEL to abort",
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    elif text == "💎 MY CREDITS":
        total_credits = get_total_credits(user_id)
        unlimited_expiry = user.get('unlimited_expiry') if user else None
        unlimited_text = ""
        if unlimited_expiry:
            try:
                if isinstance(unlimited_expiry, str):
                    expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
                else:
                    expiry_date = unlimited_expiry
                if expiry_date > datetime.now(timezone.utc):
                    unlimited_text = f"\n🚀 Unlimited: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        credits_msg = f"""
💎 *MY CREDITS*
━━━━━━━━━━━━━━━━━━
💰 Credits: `{total_credits}`{unlimited_text}
🔎 Used: `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
📦 *PACKS*
• 50 CR → ₹30
• 105 CR → ₹60
• 220 CR → ₹120
• 550 CR → ₹300
• 1150 CR → ₹600

🚀 *UNLIMITED*
• 1H → ₹29
• 1D → ₹60
• 7D → ₹240
• 30D → ₹720

🛡️ *PROTECTION*
• Number → ₹59
• Telegram → ₹59

🌐 {WEBSITE_URL}
"""
        bot.reply_to(message, credits_msg, parse_mode='Markdown')
    elif text == "🛒 BUY CREDITS":
        show_credit_packs(message, user_id)
    elif text == "🛡️ PROTECTION":
        show_protection_menu(message)
    elif text == "🎯 REFER & EARN":
        show_referral_menu(message)
    elif text == "📢 SUPPORT":
        support_msg = f"""
📢 *SUPPORT*
━━━━━━━━━━━━━━━━━━
👨‍💻 @{ADMIN_USERNAME}
👥 [Community]({GROUP_LINK})
🌐 {WEBSITE_URL}

For issues, contact admin.

━━━━━━━━━━━━━━━━━━
🌐 *Register on Website:*
👉 {WEBSITE_URL}
✅ Better rates
✅ Auto payment success
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👥 JOIN GROUP", url=GROUP_LINK))
        markup.add(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url=f"https://t.me/{ADMIN_USERNAME}"))
        markup.add(InlineKeyboardButton("🌐 WEBSITE", url=WEBSITE_URL))
        bot.reply_to(message, support_msg, reply_markup=markup, parse_mode='Markdown')
    elif text == "🛠 ADMIN PANEL":
        if str(user_id) != str(ADMIN_ID):
            bot.reply_to(message, "❌ Unauthorized!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        show_admin_panel(message)
    elif text == "❌ CANCEL":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        remove_active_session(user_id)
        bot.reply_to(message, "❌ Cancelled.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ *Unknown command!*\n\nUse /start to see menu.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if user and user.get('is_banned'):
        bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
        return
    if call.data == "check_all_join":
        all_joined, missing = check_all_channels(user_id)
        if all_joined or str(user_id) == str(ADMIN_ID):
            bot.answer_callback_query(call.id, "✅ All channels joined!", show_alert=True)
            try:
                bot.edit_message_text("✅ *All channels joined!*\n\nUse /start to open menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode="Markdown")
            except Exception:
                bot.send_message(call.message.chat.id, "✅ All channels joined! Use /start")
        else:
            if missing:
                channel_list = "\n".join([f"• {ch['name']}: {ch['link']}" for ch in missing])
                bot.answer_callback_query(call.id, f"Missing: {', '.join([ch['name'] for ch in missing])}", show_alert=True)
                send_join_required(call.message.chat.id, missing)
        return
    all_joined, missing = check_all_channels(user_id)
    if not all_joined and str(user_id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "Join all channels first!", show_alert=True)
        send_join_required(call.message.chat.id, missing)
        return
    if call.data == "main_menu":
        try:
            bot.edit_message_text("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        except Exception:
            try:
                bot.edit_message_caption("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            except Exception:
                bot.send_message(call.message.chat.id, "🏠 *MAIN MENU*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "cancel":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        remove_active_session(user_id)
        try:
            bot.edit_message_text("❌ Cancelled. Use /start for menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        except Exception:
            try:
                bot.edit_message_caption("❌ Cancelled. Use /start for menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            except Exception:
                bot.send_message(call.message.chat.id, "❌ Cancelled.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Cancelled")
    elif call.data == "back_to_lookup":
        bot.send_message(call.message.chat.id, "👇 Choose a service from the menu below.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "telegram_lookup":
        user_states[user_id] = {"state": "awaiting_lookup_query", "service": "tg2num"}
        bot.send_message(call.message.chat.id, "💬 *Telegram to Number*\n\nEnter username:\n`@username` or `username`\n\n💎 Cost: `5 credits`\n\nType ❌ CANCEL to abort", reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data in ["protect", "protection_menu"]:
        show_protection_menu(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "credits":
        total_credits = get_total_credits(user_id)
        unlimited_expiry = user.get('unlimited_expiry') if user else None
        unlimited_text = ""
        if unlimited_expiry:
            try:
                if isinstance(unlimited_expiry, str):
                    expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
                else:
                    expiry_date = unlimited_expiry
                if expiry_date > datetime.now(timezone.utc):
                    unlimited_text = f"\n🚀 Unlimited: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        credits_msg = f"""
💎 *MY CREDITS*
━━━━━━━━━━━━━━━━━━
💰 Credits: `{total_credits}`{unlimited_text}
🔎 Used: `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
📦 *PACKS*
• 50 CR → ₹30
• 105 CR → ₹60
• 220 CR → ₹120
• 550 CR → ₹300
• 1150 CR → ₹600

🚀 *UNLIMITED*
• 1H → ₹29
• 1D → ₹60
• 7D → ₹240
• 30D → ₹720

🛡️ *PROTECTION*
• Number → ₹59
• Telegram → ₹59

🌐 {WEBSITE_URL}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 BUY", callback_data="buy"))
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(credits_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "buy":
        show_credit_packs(call.message, user_id)
        bot.answer_callback_query(call.id)
    elif call.data.startswith("submitproof_"):
        tx_code = call.data.replace("submitproof_", "", 1)
        user_states[user_id] = {"state": "awaiting_payment_screenshot", "tx_code": tx_code}
        bot.send_message(call.message.chat.id, f"📸 *Send payment screenshot*\n\n🧾 `{tx_code}`\n\nForwarded to admin for verification.", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Send screenshot now")
    elif call.data.startswith("adminverify_"):
        if str(user_id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        tx_code = call.data.replace("adminverify_", "", 1)
        ok, msg = manual_verify_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Verified" if ok else msg, show_alert=not ok)
        try:
            bot.send_message(call.message.chat.id, f"{'✅' if ok else '❌'} {msg}")
        except Exception:
            pass
    elif call.data.startswith("adminreject_"):
        if str(user_id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        tx_code = call.data.replace("adminreject_", "", 1)
        ok, msg = manual_reject_payment(tx_code, user_id)
        bot.answer_callback_query(call.id, "Rejected" if ok else msg, show_alert=not ok)
        try:
            bot.send_message(call.message.chat.id, f"{'❌' if ok else '⚠️'} {msg}")
        except Exception:
            pass
    elif call.data.startswith("plan_"):
        handle_plan_selection(call)
    elif call.data.startswith("copy_referral_"):
        ref_user_id = call.data.replace("copy_referral_", "")
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start={ref_user_id}"
        bot.answer_callback_query(call.id, "📋 Copied!")
        bot.send_message(
            call.message.chat.id,
            f"🔗 *Your Link:*\n\n`{referral_link}`\n\n📋 Tap & hold to copy.",
            parse_mode='Markdown'
        )
    elif call.data.startswith("share_referral_"):
        ref_user_id = call.data.replace("share_referral_", "")
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start={ref_user_id}"
        bot.answer_callback_query(call.id, "📤 Share!")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📤 SHARE", url=f"https://t.me/share/url?url={referral_link}&text=Join%20TraceX%20Lookup%20Bot%20and%20get%2010%20free%20credits!%20Use%20my%20link%3A"))
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.send_message(
            call.message.chat.id,
            f"📤 *Share Link*\n\n🔗 `{referral_link}`\n\nTap below to share!",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    elif call.data == "profile":
        total_credits = get_total_credits(user_id)
        unlimited_expiry = user.get('unlimited_expiry') if user else None
        unlimited_text = ""
        if unlimited_expiry:
            try:
                if isinstance(unlimited_expiry, str):
                    expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
                else:
                    expiry_date = unlimited_expiry
                if expiry_date > datetime.now(timezone.utc):
                    unlimited_text = f"\n🚀 Unlimited: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        referral_count = get_user_referral_count(user_id)
        profile_msg = f"""
👤 *PROFILE*
━━━━━━━━━━━━━━━━━━
🆔 `{user_id}`
👤 `{call.from_user.first_name}`
💎 Credits: `{total_credits}`{unlimited_text}
🔎 Searches: `{user.get('total_searches', 0) if user else 0}`
🎯 Referrals: `{referral_count}`
🛡️ Status: `{'ACTIVE ✅' if not (user and user.get('is_banned')) else 'BANNED ❌'}`
━━━━━━━━━━━━━━━━━━
🚀 Thanks for using TraceX
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
        bot.edit_message_text(profile_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "help":
        help_msg = f"""
📖 *HOW TO USE*
━━━━━━━━━━━━━━━━━━
1️⃣ Choose a service from menu
2️⃣ Enter query
3️⃣ Get instant results

📋 *SERVICES:*
📱 Mobile Info — ₹3
💬 TG to Number — ₹5
🆔 Aadhaar — ₹15
🚗 Vehicle — ₹10
📷 Instagram — ₹10
📞 Truecaller — ₹10
📋 RC — ₹10
🏦 IFSC — ₹5
🧾 GST — ₹20
📲 IMEI — ₹10
💳 PAN — ₹20
⚠️ Challan — ₹10

━━━━━━━━━━━━━━━━━━
💎 *CREDITS*
• New User: 10 free
• Credits never expire
• Unlimited plans available
• Protection plans ₹59

━━━━━━━━━━━━━━━━━━
🏆 *REFERRAL REWARDS*
3→1H | 15→1D | 70→7D | 200→30D | 1000→Lifetime

━━━━━━━━━━━━━━━━━━
🌐 {WEBSITE_URL}
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 MENU", callback_data="main_menu"))
        markup.add(InlineKeyboardButton("🌐 WEBSITE", url=WEBSITE_URL))
        bot.edit_message_text(help_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "admin":
        if str(user_id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        show_admin_panel(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "broadcast_confirm":
        if str(user_id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        confirm_broadcast(call)
    elif call.data == "giveaway_confirm":
        if str(user_id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        confirm_giveaway(call)
    elif call.data in ["admin_add", "admin_remove", "admin_ban", "admin_unban", "admin_broadcast", "admin_stats", "admin_transactions", "admin_back", "admin_giveaway"]:
        if str(user_id) != str(ADMIN_ID):
            return
        if call.data == "admin_add":
            user_states[user_id] = "admin_add"
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS / UNLIMITED*\n\nCredits:\n`user_id credits`\nExample: `123456789 50`\n\nUnlimited:\n`user_id u1h/u1d/u1w/u1m`\nExample: `123456789 u1d`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE*\n\nCredits:\n`user_id/@username credits`\nExample: `@gaurav 10`\n\nDeactivate unlimited:\n`user_id/@username unlimited`\nExample: `@gaurav unlimited`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_remove)
        elif call.data == "admin_ban":
            user_states[user_id] = "admin_ban"
            msg = bot.send_message(call.message.chat.id, "🚫 *BAN USER*\n\nEnter user ID:\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_ban)
        elif call.data == "admin_unban":
            user_states[user_id] = "admin_unban"
            msg = bot.send_message(call.message.chat.id, "✅ *UNBAN USER*\n\nEnter user ID:\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_unban)
        elif call.data == "admin_broadcast":
            user_states[user_id] = "admin_broadcast"
            msg = bot.send_message(call.message.chat.id, "📢 *BROADCAST*\n\nSend your message:\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_broadcast)
        elif call.data == "admin_giveaway":
            user_states[user_id] = "admin_giveaway"
            msg = bot.send_message(call.message.chat.id, "🎁 *GIVEAWAY*\n\nEnter credits for ALL users:\n\nExample: `50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
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
    admin_msg = f"""
*🛠 ADMIN PANEL*
*📊 STATS*
👥 Users: `{stats['total_users']}`
🔍 Searches: `{stats['total_searches']}`
🛡️ Protected: `{stats['protected_count']}`
🎯 Referrals: `{stats['total_referrals']}`
*💎 CREDITS*
💰 Total: `{stats['total_credits']}`
*💰 FINANCIAL*
💵 Revenue: ₹{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
🚫 Banned: `{stats['banned_users']}`
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
    """
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ ADD", callback_data="admin_add"),
        InlineKeyboardButton("➖ REMOVE", callback_data="admin_remove")
    )
    markup.add(
        InlineKeyboardButton("🚫 BAN", callback_data="admin_ban"),
        InlineKeyboardButton("✅ UNBAN", callback_data="admin_unban")
    )
    markup.add(
        InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"),
        InlineKeyboardButton("🎁 GIVEAWAY", callback_data="admin_giveaway")
    )
    markup.add(
        InlineKeyboardButton("📊 STATS", callback_data="admin_stats"),
        InlineKeyboardButton("📋 TRANSACTIONS", callback_data="admin_transactions")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    bot.send_message(message.chat.id, admin_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_stats(message):
    stats = get_stats()
    stats_msg = f"""
*📊 DETAILED STATS*
━━━━━━━━━━━━━━━━━━
👥 *USERS*
Total: `{stats['total_users']}`
Banned: `{stats['banned_users']}`
Active: `{stats['total_users'] - stats['banned_users']}`
━━━━━━━━━━━━━━━━━━
💎 *CREDITS*
Total: `{stats['total_credits']}`
━━━━━━━━━━━━━━━━━━
📊 *USAGE*
Searches: `{stats['total_searches']}`
Protected: `{stats['protected_count']}`
Referrals: `{stats['total_referrals']}`
━━━━━━━━━━━━━━━━━━
💰 *FINANCIAL*
Revenue: ₹{stats['total_revenue']}
Pending: `{stats['pending_payments']}`
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
    """
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, stats_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_transactions(message):
    transactions = get_recent_transactions()
    if not transactions:
        trans_msg = "📋 *No transactions found.*"
    else:
        trans_msg = "*📋 RECENT TRANSACTIONS*\n\n"
        for trans in transactions:
            status_emoji = "✅" if trans.get('status') == "success" else "⏳" if trans.get('status') == "pending" else "❌"
            trans_msg += f"{status_emoji} `{trans.get('payment_id', '')[:20]}` | `{trans.get('telegram_user_id', '')}` | ₹{trans.get('amount', 0)} | {trans.get('plan_id', '')}\n"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, trans_msg, reply_markup=markup, parse_mode='Markdown')

def process_admin_add(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
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
        if value in ["u1h", "u1d", "u1w", "u1m"]:
            ok, new_expiry = activate_unlimited_plan_for_user(target_user, value)
            if not ok:
                bot.reply_to(message, "❌ Invalid plan.", parse_mode='Markdown')
                return
            label = PLAN_CONFIG.get(value, {}).get("label", value)
            bot.reply_to(message, f"✅ Added `{label}` to `{target_user}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🚀 *Unlimited Added!*\nPlan: `{label}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                pass
            return
        credits = int(value)
        new_total = add_credits(target_user, credits)
        bot.reply_to(message, f"✅ Added {credits} credits to `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, f"✅ *{credits} credits added!*\nNew total: `{new_total}`\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Invalid format!\nCredits: `user_id/@username credits`\nUnlimited: `user_id/@username u1h/u1d/u1w/u1m`", parse_mode='Markdown')

def process_admin_remove(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
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
            bot.reply_to(message, f"✅ Unlimited deactivated for `{target_user}`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🧨 *Unlimited Deactivated*\n\nRemoved by admin.\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                pass
            return
        credits = int(action)
        current_credits = int(user.get('credits', 0) or 0)
        new_credits = max(0, current_credits - credits)
        supabase.table("telegram_users").update({"credits": new_credits, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("telegram_user_id", target_user).execute()
        bot.reply_to(message, f"✅ Removed {credits} credits from `{target_user}`\nNew total: `{new_credits}`", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "❌ Invalid format!\nCredits: `user_id/@username credits`\nDeactivate: `user_id/@username unlimited`", parse_mode='Markdown')

def process_admin_ban(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    try:
        target_user = int(message.text.strip())
        ban_user(target_user)
        bot.reply_to(message, f"✅ Banned `{target_user}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, "🚫 *You are banned.* Contact support.", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_unban(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    try:
        target_user = int(message.text.strip())
        unban_user(target_user)
        bot.reply_to(message, f"✅ Unbanned `{target_user}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, "✅ *You are unbanned!* Use /start", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_broadcast(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    broadcast_text = (message.text or message.caption or "").strip()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ SEND", callback_data="broadcast_confirm"), InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    temp_data[user_id] = {'broadcast_text': broadcast_text}
    bot.reply_to(message, f"📢 *Confirm Broadcast*\n\n📝 `{broadcast_text}`\n\nSend to all active users?", reply_markup=markup, parse_mode='Markdown')

def process_admin_giveaway(message):
    user_id = message.from_user.id
    if str(user_id) != str(ADMIN_ID):
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    try:
        credits = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ GIVE", callback_data="giveaway_confirm"), InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
        temp_data[user_id] = {'giveaway_credits': credits}
        bot.reply_to(message, f"🎁 *Confirm Giveaway*\n\nGive `{credits}` credits to ALL active users?", reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number! Enter a valid amount.", parse_mode='Markdown')

def confirm_broadcast(call):
    user_id = call.from_user.id
    if str(user_id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Broadcast cancelled.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id))
        return
    broadcast_text = temp_data[user_id]['broadcast_text']
    total_users = get_total_users_count()
    bot.edit_message_text(f"📡 *Broadcasting to {total_users} users...*\n\nPlease wait...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    success = 0
    failed = 0
    offset = 0
    batch_size = 100
    while True:
        users = get_all_users_batch(batch_size, offset)
        if not users:
            break
        for target_user_id in users:
            try:
                broadcast_msg = f"""
*📢 TRACEX*
{broadcast_text}
━━━━━━━━━━━━━━━━
📞 @{ADMIN_USERNAME}
👥 [Community]({GROUP_LINK})
🌐 {WEBSITE_URL}
"""
                bot.send_message(target_user_id, broadcast_msg, parse_mode='Markdown', disable_web_page_preview=True)
                success += 1
            except Exception as e:
                failed += 1
                print(f"Broadcast failed to {target_user_id}: {e}")
            time.sleep(0.05)
        offset += batch_size
        progress_msg = f"📡 *Broadcasting...*\n\n✅ Sent: `{success}`\n❌ Failed: `{failed}`\n📝 Total: `{total_users}`\n⏳ `{min(offset, total_users)}/{total_users}`"
        try:
            bot.edit_message_text(progress_msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except:
            pass
    result_msg = f"""
✅ *Broadcast Complete!*
📊 *Stats:*
• ✅ Sent: `{success}`
• ❌ Failed: `{failed}`
• 📝 Total: `{total_users}`
⏱️ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    del temp_data[user_id]

def confirm_giveaway(call):
    user_id = call.from_user.id
    if str(user_id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Giveaway cancelled.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id))
        return
    credits = temp_data[user_id]['giveaway_credits']
    total_users = get_total_users_count()
    bot.edit_message_text(f"🎁 *Processing...*\n\nGiving `{credits}` credits to `{total_users}` users...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    success, failed = add_giveaway_credits(credits)
    result_msg = f"""
🎉 *Giveaway Complete!*
✨ `{credits}` credits given to each user!
📊 *Stats:*
• ✅ Successful: `{success}`
• ❌ Failed: `{failed}`
💎 Total: `{success * credits}`
⏱️ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    del temp_data[user_id]

# ==================== FLASK WEBHOOK ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "TraceX Bot v11.0.11 - 12 Lookup Services - Running!"

def keep_alive():
    def run():
        port = int(os.getenv("PORT", "8080"))
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ==================== START BOT ====================
if __name__ == "__main__":
    print("=" * 60)
    print(f"TraceX Lookup v{BOT_VERSION} starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Admin: @{ADMIN_USERNAME}")
    print("=" * 60)
    print("📋 12 LOOKUP SERVICES:")
    for key, svc in LOOKUP_SERVICES.items():
        print(f"   • {svc['emoji']} {svc['name']} — ₹{svc['cost']}")
    print("=" * 60)
    print("🔍 FIXES IN v11.0.11:")
    print("   • JSON rendered as HTML <pre> block (copy-friendly)")
    print("   • Smart splitter keeps <pre> blocks intact per chunk")
    print("   • Part indicators on multi-message results")
    print("   • Plain-text fallback if HTML parse fails")
    print("   • HTML special chars escaped safely")
    print("=" * 60)

    keep_alive()
    print("✅ Flask server started")
    threading.Thread(target=send_daily_search_report_loop, daemon=True).start()
    print("✅ Daily report scheduler started")
    threading.Thread(target=send_bulk_reminders, daemon=True).start()
    print("✅ Reminder scheduler started")
    threading.Thread(target=reset_referral_counts, daemon=True).start()
    print("✅ Referral reset scheduler started")
    print("✅ Bot is running!")
    print("=" * 60)

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
            bot.infinity_polling(timeout=30, skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}")
            if "409" in str(e) or "getUpdates" in str(e):
                print("⚠️ 409 conflict: stop other bot instances using same BOT_TOKEN.")
            time.sleep(5)
