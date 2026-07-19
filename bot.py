"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Manual QR
Version: 7.0.3 - Raw Response Pretty Print
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
from flask import Flask, request, jsonify

# Lightweight Supabase REST client for Termux/Python 3.13.
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
BOT_VERSION = "7.0.3"

# Updated Lookup APIs
NUMBER_LOOKUP_API_URL = "https://tracexdata-api.onrender.com/api/lookup"
TELEGRAM_LOOKUP_API_URL = "https://tracexdata-api.onrender.com/api/telegram"
PAN_LOOKUP_API_URL = "https://tracexdata-api.onrender.com/api/pancard"
VEHICLE_OWNER_API_URL = "https://tracexdata-api.onrender.com/api/veh-owner-num"
VEHICLE_LOOKUP_API_URL = "https://tracexdata-api.onrender.com/api/vehicle"
EMAIL_LOOKUP_API_URL = "https://tracexdata-api.onrender.com/api/email"

# API Keys
NUMBER_API_KEY = "Pvttbott"
TELEGRAM_API_KEY = "Pvtbott"
PAN_API_KEY = "Pvtbot"
VEHICLE_OWNER_API_KEY = "Pvtbottt"
VEHICLE_API_KEY = "Pvtbotttt"
EMAIL_API_KEY = "Pvttbot"

# Updated Costs (1 credit = 1 unit)
NUMBER_LOOKUP_COST = 2
TELEGRAM_LOOKUP_COST = 5
PAN_LOOKUP_COST = 5
VEHICLE_OWNER_COST = 10
VEHICLE_LOOKUP_COST = 5
EMAIL_LOOKUP_COST = 20
IDENTITY_LOOKUP_COST = 5
IFSC_LOOKUP_COST = 3

MAX_LOOKUP_RESULTS = 20
TELEGRAM_SAFE_LIMIT = 3900

# Updated Plan Configuration - New Pricing
PLAN_CONFIG = {
    "c40": {"amount": 20, "credits": 40, "unlimited_minutes": 0, "payment_for": "credits", "label": "40 Credits"},
    "c120": {"amount": 50, "credits": 120, "unlimited_minutes": 0, "payment_for": "credits", "label": "120 Credits"},
    "c400": {"amount": 100, "credits": 400, "unlimited_minutes": 0, "payment_for": "credits", "label": "400 Credits"},
    "u1h": {"amount": 49, "credits": 0, "unlimited_minutes": 60, "payment_for": "unlimited", "label": "1 Hour Unlimited"},
    "u1d": {"amount": 99, "credits": 0, "unlimited_minutes": 1440, "payment_for": "unlimited", "label": "1 Day Unlimited"},
    "u1w": {"amount": 499, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited"},
    "u1m": {"amount": 1499, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited"},
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Number Protection"},
    "bot_booking": {"amount": 399, "credits": 0, "unlimited_minutes": 0, "payment_for": "bot_booking", "label": "Custom Bot Booking Add-on"},
}

# Required Channels for Verification
REQUIRED_CHANNELS = [
    {"name": "Beniwal Mods", "url": "https://t.me/beniwalmods", "username": "@beniwalmods"},
    {"name": "Gaurav Beniwal", "url": "https://t.me/Gaurav_beni_0001", "username": "@Gaurav_beni_0001"},
    {"name": "Beniwal Zone", "url": "https://t.me/BeniwalzonYT", "username": "@BeniwalzonYT"},
    {"name": "Gaurav Beniwal Chat", "url": "https://t.me/gauravbeniwalchat", "username": "@gauravbeniwalchat"}
]

# Branding patterns to remove (restricted words)
BRANDING_PATTERNS = [
    r'exploits',
    r'userxinfo',
    r'tech vishal',
    r'techvishal',
    r'vishal',
    r'exploit',
    r'Developer[:\s]*@[a-zA-Z0-9_]+',
    r'Developed By[:\s]*@[a-zA-Z0-9_]+',
    r'By[:\s]*@[a-zA-Z0-9_]+',
    r'API[:\s]*@[a-zA-Z0-9_]+',
    r'💳 BUY API\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'🆘 SUPPORT\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'BUY API\s*:\s*@[a-zA-Z0-9_]+\s*',
    r'SUPPORT\s*:\s*@[a-zA-Z0-9_]+\s*',
]

GENERIC_API_ERROR_MESSAGE = "❌ *API Error*\n\n💎 Credits NOT deducted"

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

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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
active_sessions_lock = threading.Lock()
active_sessions = set()
proof_forwarded_txs = set()

# 24-hour search summary storage
daily_search_stats = {}
daily_stats_lock = threading.Lock()
IST = timezone(timedelta(hours=5, minutes=30))

MAINTENANCE_MODE = False

# ==================== MAIN MENU KEYBOARD ====================
def get_main_keyboard():
    """Create main menu with keyboard buttons"""
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
        KeyboardButton("📧 EMAIL LOOKUP"),
        KeyboardButton("🪪 PAN LOOKUP")
    )
    keyboard.add(
        KeyboardButton("🚗 VEHICLE LOOKUP"),
        KeyboardButton("🔍 VEHICLE OWNER")
    )
    keyboard.add(
        KeyboardButton("💎 MY CREDITS"),
        KeyboardButton("🛒 BUY CREDITS")
    )
    keyboard.add(
        KeyboardButton("🛡️ PROTECTION"),
        KeyboardButton("📢 SUPPORT")
    )
    return keyboard

def get_main_keyboard_for_user(user_id):
    """Create main menu with Admin button for admin user"""
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
        KeyboardButton("📧 EMAIL LOOKUP"),
        KeyboardButton("🪪 PAN LOOKUP")
    )
    keyboard.add(
        KeyboardButton("🚗 VEHICLE LOOKUP"),
        KeyboardButton("🔍 VEHICLE OWNER")
    )
    keyboard.add(
        KeyboardButton("💎 MY CREDITS"),
        KeyboardButton("🛒 BUY CREDITS")
    )
    keyboard.add(
        KeyboardButton("🛡️ PROTECTION"),
        KeyboardButton("📢 SUPPORT")
    )
    if user_id == ADMIN_ID:
        keyboard.add(KeyboardButton("🛠 ADMIN PANEL"))
    return keyboard

def get_cancel_keyboard():
    """Cancel keyboard"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton("❌ CANCEL"))
    return keyboard

# ==================== MAINTENANCE MODE ====================
MAINTENANCE_MESSAGE = """
⚠️ *BOT UNDER MAINTENANCE* 🛠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━

TraceX is currently under maintenance and upgrades.

⏰ Please try again later.

📢 Join our official channels for updates:
• https://t.me/beniwalmods
• https://t.me/Gaurav_beni_0001

🙏 Thanks for your patience.
"""

@bot.message_handler(func=lambda message: MAINTENANCE_MODE and message.from_user.id != ADMIN_ID)
def maintenance_handler(message):
    bot.reply_to(message, MAINTENANCE_MESSAGE, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: MAINTENANCE_MODE and call.from_user.id != ADMIN_ID)
def maintenance_callback(call):
    bot.answer_callback_query(call.id, "Bot under maintenance 🛠️", show_alert=True)

# ==================== UI COMPONENTS ====================
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")
GROUP_LINK = "https://t.me/Gaurav_beni_0001"
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
COOLDOWN_SECONDS = 3

def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n🌐 Website: {WEBSITE_URL}\n⚡ Instant credits add • Lower credit cost • More accurate search\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    """Send important admin alerts to group, with DM fallback to admin."""
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
    """Create inline keyboard for channel verification"""
    markup = InlineKeyboardMarkup(row_width=2)
    for channel in REQUIRED_CHANNELS:
        markup.add(InlineKeyboardButton(f"📢 {channel['name']}", url=channel['url']))
    markup.add(InlineKeyboardButton("✅ I HAVE JOINED ALL", callback_data="check_all_join"))
    return markup

def is_all_channels_member(user_id):
    """Check if user has joined ALL required channels. Admin bypasses."""
    if user_id == ADMIN_ID:
        return []  # Return empty list for admin (no missing channels)
    missing_channels = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel['username'], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing_channels.append(channel)
        except Exception as e:
            print(f"Channel membership check error for {channel['name']}: {e}")
            missing_channels.append(channel)
    return missing_channels

def get_missing_channels_message(missing_channels):
    """Generate message for missing channels"""
    if not missing_channels:
        return None
    
    msg = "🔒 *JOIN REQUIRED CHANNELS* 🔒\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "⚠️ You must join ALL of our official channels to use this bot.\n\n"
    msg += "📢 *Missing Channels:*\n"
    for channel in missing_channels:
        msg += f"• {channel['name']}: {channel['url']}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "✅ Join all channels above, then click the *'I HAVE JOINED ALL'* button to continue.\n\n"
    msg += "❌ If you leave any channel after joining, you will be asked to join again."
    return msg

def send_join_required(chat_id):
    """Send join required message for all channels. Returns True if user is missing channels."""
    missing = is_all_channels_member(chat_id)
    if missing:  # If there are missing channels
        msg = get_missing_channels_message(missing)
        bot.send_message(
            chat_id,
            msg,
            reply_markup=join_required_markup(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return True
    return False

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
        InlineKeyboardButton("🚀 1 Hour Unlimited - ₹49", callback_data="plan_u1h"),
        InlineKeyboardButton("🚀 1 Day Unlimited - ₹99", callback_data="plan_u1d"),
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹499", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹1499", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number"),
        InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
    return markup

def telegram_lookup_protection_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛡️ PROTECT MY TELEGRAM ID", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🔍 NEW TELEGRAM LOOKUP", callback_data="telegram_lookup")
    )
    markup.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    return markup

def remove_branding(text):
    """Remove all branding patterns from API response text"""
    if not text:
        return text
    result = text
    for pattern in BRANDING_PATTERNS:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
    result = re.sub(r'@[a-zA-Z0-9_]+', '', result)
    result = result.strip()
    return result

def show_api_error(chat_id, message_id, lookup_type="api"):
    """Show only a clean API error to users."""
    try:
        bot.edit_message_text(GENERIC_API_ERROR_MESSAGE, chat_id, message_id, parse_mode="Markdown")
    except Exception as edit_error:
        print(f"Failed to show generic API error for {lookup_type}: {edit_error}")

def call_api_with_retry(url, params=None, max_retries=3, timeout=30):
    """Generic API caller with retry logic"""
    for attempt in range(max_retries):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 16) TraceXBot/7.0",
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                try:
                    return response.json(), None
                except:
                    return {"raw_response": response.text}, None
            elif response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(2 * (attempt + 1))
                continue
            else:
                return None, f"http_{response.status_code}"
                
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                return None, "timeout"
            time.sleep(2)
        except Exception as e:
            if attempt == max_retries - 1:
                return None, f"exception_{e}"
            time.sleep(2)
    
    return None, "max_retries_exceeded"

def call_lookup_api(url, key_param, key_value, query_param, query_value):
    """Generic lookup API caller"""
    params = {
        key_param: key_value,
        query_param: query_value
    }
    return call_api_with_retry(url, params)

def call_number_lookup_api(number):
    """Call number lookup API"""
    return call_lookup_api(
        NUMBER_LOOKUP_API_URL,
        "key", NUMBER_API_KEY,
        "number", number
    )

def call_telegram_lookup_api(username):
    """Call Telegram lookup API"""
    if not username.startswith('@'):
        username = '@' + username
    return call_lookup_api(
        TELEGRAM_LOOKUP_API_URL,
        "key", TELEGRAM_API_KEY,
        "api", "gaurav_beniwal_0001"
    )

def call_pan_lookup_api(pan_number):
    """Call PAN card lookup API"""
    return call_lookup_api(
        PAN_LOOKUP_API_URL,
        "key", PAN_API_KEY,
        "query", pan_number.upper()
    )

def call_vehicle_owner_api(vehicle_number):
    """Call vehicle to owner number API"""
    return call_lookup_api(
        VEHICLE_OWNER_API_URL,
        "key", VEHICLE_OWNER_API_KEY,
        "query", vehicle_number.upper()
    )

def call_vehicle_lookup_api(vehicle_number):
    """Call vehicle lookup API"""
    return call_lookup_api(
        VEHICLE_LOOKUP_API_URL,
        "key", VEHICLE_API_KEY,
        "query", vehicle_number.upper()
    )

def call_email_lookup_api(email):
    """Call email lookup API"""
    return call_lookup_api(
        EMAIL_LOOKUP_API_URL,
        "key", EMAIL_API_KEY,
        "query", email.lower()
    )

def format_raw_response(data, indent=2):
    """Format any raw response data into a pretty readable format"""
    if data is None:
        return "No data received"
    
    # If it's a string, try to parse as JSON first
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            # If not JSON, return as is (but remove branding)
            return remove_branding(data)
    
    # If it's a list, format each item
    if isinstance(data, list):
        if not data:
            return "Empty list"
        result = ""
        for i, item in enumerate(data, 1):
            if isinstance(item, dict):
                result += f"\n📌 *Item {i}*:\n"
                for key, value in item.items():
                    if isinstance(value, (dict, list)):
                        result += f"   • {key}: {json.dumps(value, indent=2)}\n"
                    else:
                        result += f"   • {key}: `{value}`\n"
            else:
                result += f"\n📌 *Item {i}*: `{item}`\n"
        return result
    
    # If it's a dict, format all key-value pairs
    if isinstance(data, dict):
        # Remove any branding from the response
        result = ""
        
        # Check for common response patterns
        if "status" in data:
            status = data.get("status", "N/A")
            status_emoji = "✅" if str(status).lower() in ["success", "true", "1"] else "❌"
            result += f"📊 *Status*: {status_emoji} `{status}`\n\n"
        
        if "message" in data:
            result += f"💬 *Message*: {remove_branding(str(data['message']))}\n\n"
        
        # Process all other fields
        for key, value in data.items():
            if key in ["status", "message"]:
                continue
            if isinstance(value, dict):
                result += f"\n📂 *{key.upper()}*:\n"
                for k, v in value.items():
                    if isinstance(v, (dict, list)):
                        result += f"   • {k}: {json.dumps(v, indent=2)}\n"
                    else:
                        result += f"   • {k}: `{v}`\n"
            elif isinstance(value, list):
                result += f"\n📂 *{key.upper()}*:\n"
                for item in value:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if isinstance(v, (dict, list)):
                                result += f"   • {k}: {json.dumps(v, indent=2)}\n"
                            else:
                                result += f"   • {k}: `{v}`\n"
                    else:
                        result += f"   • `{item}`\n"
            else:
                if value is not None and value != "":
                    result += f"📌 {key}: `{remove_branding(str(value))}`\n"
        
        return result
    
    # Fallback for other types
    return remove_branding(str(data))

def format_lookup_response(result, query, lookup_type, user_id, cost, unlimited_active=False, unlimited_expiry=None):
    """Format the final lookup response with pretty printed raw data"""
    output = f"""
🔍 *{lookup_type.upper()} LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 Query: `{query}`

"""
    
    # Format the raw response
    if isinstance(result, dict):
        # Check if there's a raw_response or just use the result directly
        if "raw_response" in result:
            formatted_data = format_raw_response(result["raw_response"])
        else:
            formatted_data = format_raw_response(result)
    else:
        formatted_data = format_raw_response(result)
    
    output += formatted_data
    
    output += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
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
💎 *Credits Used:* `{cost}`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{user.get('total_searches', 0) if user else 0}`"""
    
    output += f"""
{footer()}
"""
    return output

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

# ==================== TELEGRAM LOOKUP FUNCTIONS ====================
def process_telegram_lookup(message):
    """Process Telegram username lookup"""
    user_id = message.from_user.id
    username_input = str(message.text or "").strip()

    if username_input == "❌ CANCEL" or username_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_telegram_username":
        return

    user_states.pop(user_id, None)

    username_clean = username_input
    if not username_input.startswith('@'):
        username_clean = '@' + username_input
    
    if not re.match(r'^@?[a-zA-Z0-9_]{5,32}$', username_input):
        bot.reply_to(message, "❌ *Invalid Telegram Username!*\n\nEnter a valid Telegram username.\nExamples: `@username` or `username`\n\n💎 Cost: `5 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < TELEGRAM_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Telegram Lookup costs `{TELEGRAM_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Telegram...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching Telegram...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, error = call_telegram_lookup_api(username_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="telegram")
        notify_admin_api_issue("telegram_lookup", username_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    # Check if result has data
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True
    
    if not has_data:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Username: `{username_clean}`

🚫 No records available in database

💡 Tips:
• Check username again
• Try another username
• Ensure username is correct

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=False, lookup_type="telegram", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, TELEGRAM_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response(result, username_clean, "Telegram", user_id, TELEGRAM_LOOKUP_COST, unlimited_active, unlimited_expiry)
    markup = telegram_lookup_protection_markup()
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, username_input, found=True, lookup_type="telegram", credits_used=TELEGRAM_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== PAN LOOKUP FUNCTION ====================
def process_pan_lookup(message):
    """Process PAN card lookup"""
    user_id = message.from_user.id
    pan_input = str(message.text or "").strip().upper()

    if pan_input == "❌ CANCEL" or pan_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_pan_input":
        return

    user_states.pop(user_id, None)

    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_input):
        bot.reply_to(message, "❌ *Invalid PAN Card Number!*\n\nEnter a valid 10-character PAN number.\nExample: `NTEPK1628C`\n\n💎 Cost: `5 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < PAN_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* PAN Card Lookup costs `{PAN_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching PAN Card records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching PAN Card records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, error = call_pan_lookup_api(pan_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="pan")
        notify_admin_api_issue("pan_lookup", pan_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, pan_input, found=False, lookup_type="pan", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True
    
    if not has_data:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🪪 PAN Card: `{pan_input}`

🚫 No records available in database

💡 Tips:
• Check PAN number again
• Try another PAN number

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, pan_input, found=False, lookup_type="pan", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, PAN_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response(result, pan_input, "PAN Card", user_id, PAN_LOOKUP_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW PAN LOOKUP", callback_data="pan_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, pan_input, found=True, lookup_type="pan", credits_used=PAN_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== VEHICLE LOOKUP FUNCTIONS ====================
def process_vehicle_lookup(message):
    """Process vehicle lookup"""
    user_id = message.from_user.id
    vehicle_input = str(message.text or "").strip().upper()

    if vehicle_input == "❌ CANCEL" or vehicle_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_vehicle_input":
        return

    user_states.pop(user_id, None)

    vehicle_clean = re.sub(r'[^A-Z0-9]', '', vehicle_input)
    if len(vehicle_clean) < 4:
        bot.reply_to(message, "❌ *Invalid Vehicle Number!*\n\nEnter a valid vehicle registration number.\nExample: `BR07PB6268`\n\n💎 Cost: `5 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < VEHICLE_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Vehicle Lookup costs `{VEHICLE_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Vehicle records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching Vehicle records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, error = call_vehicle_lookup_api(vehicle_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="vehicle")
        notify_admin_api_issue("vehicle_lookup", vehicle_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=False, lookup_type="vehicle", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True
    
    if not has_data:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🚗 Vehicle: `{vehicle_input}`

🚫 No records available in database

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=False, lookup_type="vehicle", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, VEHICLE_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response(result, vehicle_input, "Vehicle", user_id, VEHICLE_LOOKUP_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW VEHICLE LOOKUP", callback_data="vehicle_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=True, lookup_type="vehicle", credits_used=VEHICLE_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

def process_vehicle_owner_lookup(message):
    """Process vehicle to owner number lookup"""
    user_id = message.from_user.id
    vehicle_input = str(message.text or "").strip().upper()

    if vehicle_input == "❌ CANCEL" or vehicle_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_vehicle_owner_input":
        return

    user_states.pop(user_id, None)

    vehicle_clean = re.sub(r'[^A-Z0-9]', '', vehicle_input)
    if len(vehicle_clean) < 4:
        bot.reply_to(message, "❌ *Invalid Vehicle Number!*\n\nEnter a valid vehicle registration number.\nExample: `BR07PB6268`\n\n💎 Cost: `10 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < VEHICLE_OWNER_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Vehicle Owner Lookup costs `{VEHICLE_OWNER_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Vehicle Owner records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching Vehicle Owner records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, error = call_vehicle_owner_api(vehicle_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="vehicle_owner")
        notify_admin_api_issue("vehicle_owner_lookup", vehicle_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=False, lookup_type="vehicle_owner", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True
    
    if not has_data:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔍 Vehicle: `{vehicle_input}`

🚫 No records available in database

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=False, lookup_type="vehicle_owner", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, VEHICLE_OWNER_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response(result, vehicle_input, "Vehicle Owner", user_id, VEHICLE_OWNER_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW VEHICLE OWNER LOOKUP", callback_data="vehicle_owner_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, vehicle_input, found=True, lookup_type="vehicle_owner", credits_used=VEHICLE_OWNER_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== EMAIL LOOKUP FUNCTION ====================
def process_email_lookup(message):
    """Process email lookup"""
    user_id = message.from_user.id
    email_input = str(message.text or "").strip().lower()

    if email_input == "❌ CANCEL" or email_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_email_input":
        return

    user_states.pop(user_id, None)

    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_input):
        bot.reply_to(message, "❌ *Invalid Email Address!*\n\nEnter a valid email address.\nExample: `user@example.com`\n\n💎 Cost: `20 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < EMAIL_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Email Lookup costs `{EMAIL_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Email records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching Email records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    result, error = call_email_lookup_api(email_input)
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="email")
        notify_admin_api_issue("email_lookup", email_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, email_input, found=False, lookup_type="email", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True
    
    if not has_data:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📧 Email: `{email_input}`

🚫 No records available in database

💡 Tips:
• Check email address again
• Try another email address

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, email_input, found=False, lookup_type="email", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, EMAIL_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response(result, email_input, "Email", user_id, EMAIL_LOOKUP_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW EMAIL LOOKUP", callback_data="email_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, email_input, found=True, lookup_type="email", credits_used=EMAIL_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== IDENTITY LOOKUP FUNCTION ====================
def process_identity_lookup(message):
    """Process Identity (Aadhar) lookup"""
    user_id = message.from_user.id
    aadhar_input = str(message.text or "").strip()

    if aadhar_input == "❌ CANCEL" or aadhar_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_identity_input":
        return

    user_states.pop(user_id, None)

    if not re.match(r'^\d{12}$', aadhar_input):
        bot.reply_to(message, "❌ *Invalid Aadhar Number!*\n\nEnter a valid 12-digit Aadhar number.\nExample: `123456789012`\n\n💎 Cost: `5 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < IDENTITY_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Identity Lookup costs `{IDENTITY_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching Identity records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching Identity records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    # Identity lookup using existing API
    result, error = call_api_with_retry("https://exploitsindia.site//osint-api/aadhar.php", {"exploits": aadhar_input})
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="identity")
        notify_admin_api_issue("identity_lookup", aadhar_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, aadhar_input, found=False, lookup_type="identity", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    response_text = result.get("response", "") if isinstance(result, dict) else str(result)
    no_data_markers = ["no data found", "not found", "no record", "no result", "invalid"]
    if any(marker in response_text.lower() for marker in no_data_markers):
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🆔 Aadhar: `{aadhar_input}`

🚫 No records available in database

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, aadhar_input, found=False, lookup_type="identity", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, IDENTITY_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response({"raw_response": response_text}, aadhar_input, "Identity", user_id, IDENTITY_LOOKUP_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW IDENTITY LOOKUP", callback_data="identity_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, aadhar_input, found=True, lookup_type="identity", credits_used=IDENTITY_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

# ==================== IFSC LOOKUP FUNCTION ====================
def process_ifsc_lookup(message):
    """Process IFSC lookup"""
    user_id = message.from_user.id
    ifsc_input = str(message.text or "").strip().upper()

    if ifsc_input == "❌ CANCEL" or ifsc_input == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_ifsc_input":
        return

    user_states.pop(user_id, None)

    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_input):
        bot.reply_to(message, "❌ *Invalid IFSC Code!*\n\nEnter a valid IFSC code.\nExample: `HDFC0001325`\n\n💎 Cost: `3 credits` per search", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    
    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One search already running!*\n\nPlease wait for current search result before starting another.", 
                        reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    
    if total_credits < IFSC_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* IFSC Lookup costs `{IFSC_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching IFSC records...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching IFSC records...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    # IFSC lookup using existing API
    result, error = call_api_with_retry("https://exploitsindia.site//osint-api/ifsc.php", {"exploits": ifsc_input})
    
    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="ifsc")
        notify_admin_api_issue("ifsc_lookup", ifsc_input, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, ifsc_input, found=False, lookup_type="ifsc", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    response_text = result.get("response", "") if isinstance(result, dict) else str(result)
    no_data_markers = ["no data found", "not found", "no record", "no result", "invalid", "not available"]
    if any(marker in response_text.lower() for marker in no_data_markers):
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🏦 IFSC Code: `{ifsc_input}`

🚫 No records available in database

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, ifsc_input, found=False, lookup_type="ifsc", credits_used=0)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        return
    
    if not unlimited_active:
        if not deduct_credits(user_id, IFSC_LOOKUP_COST):
            bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            with active_sessions_lock:
                active_sessions.discard(user_id)
            return
    
    increment_total_searches(user_id)
    
    output = format_lookup_response({"raw_response": response_text}, ifsc_input, "IFSC", user_id, IFSC_LOOKUP_COST, unlimited_active, unlimited_expiry)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 NEW IFSC LOOKUP", callback_data="ifsc_lookup"),
        InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")
    )
    
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, ifsc_input, found=True, lookup_type="ifsc", credits_used=IFSC_LOOKUP_COST if not unlimited_active else 0)
    
    with active_sessions_lock:
        active_sessions.discard(user_id)

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
    """Add credits to user and return new total."""
    try:
        response = supabase.table("telegram_users").select("credits, telegram_user_id, telegram_name").eq("telegram_user_id", telegram_user_id).execute()
        
        if not response.data or len(response.data) == 0:
            print(f"User {telegram_user_id} not found, creating new user...")
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
                final_credits = result.data[0].get('credits', amount)
                print(f"New user created with {final_credits} credits")
                return final_credits
            else:
                print(f"Failed to create user: {result}")
                return 0
        else:
            current_credits = response.data[0].get('credits', 0)
            new_credits = current_credits + amount
            
            print(f"Updating user {telegram_user_id}: {current_credits} -> {new_credits} (+{amount})")
            
            update_result = supabase.table("telegram_users").update({
                "credits": new_credits,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            
            if update_result.data and len(update_result.data) > 0:
                final_credits = update_result.data[0].get('credits', new_credits)
                print(f"Credits updated successfully: {final_credits}")
                return final_credits
            else:
                verify_response = supabase.table("telegram_users").select("credits").eq("telegram_user_id", telegram_user_id).execute()
                if verify_response.data and len(verify_response.data) > 0:
                    final_credits = verify_response.data[0].get('credits', 0)
                    print(f"Verified credits after update: {final_credits}")
                    return final_credits
                else:
                    print(f"Update may have failed - could not verify")
                    return new_credits
                    
    except Exception as e:
        print(f"Add credits error for user {telegram_user_id}: {e}")
        import traceback
        traceback.print_exc()
        return 0

def deduct_credits(telegram_user_id, amount=1):
    """Deduct credits unless an unlimited plan is active. Returns True on success."""
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
            supabase.table("search_results").update({
                "raw_data": raw_data
            }).eq("mobile_number", phone_number).execute()
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

def is_telegram_protected(telegram_id):
    return is_value_protected("protected_telegrams", "telegram_id", str(telegram_id))

def add_protected_telegram(telegram_id, telegram_user_id=None):
    return add_protected_value("protected_telegrams", "telegram_id", str(telegram_id))

def normalize_vehicle_number(value):
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())

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
        
        cache_resp = supabase.table("search_results").select("*", count="exact").execute()
        cache_size = cache_resp.count
        
        protected_resp = supabase.table("protected_numbers").select("*", count="exact").execute()
        protected_count = protected_resp.count
        
        return {
            'total_users': total_users,
            'total_searches': total_searches,
            'total_credits': total_credits,
            'banned_users': banned_users,
            'pending_payments': pending_payments_count,
            'total_revenue': total_revenue,
            'cache_size': cache_size,
            'protected_count': protected_count
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
            'cache_size': 0,
            'protected_count': 0
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
        failed_count = 0
        for user_id in users:
            try:
                add_credits(user_id, credits)
                success_count += 1
            except Exception as e:
                print(f"Failed to add credits to {user_id}: {e}")
                failed_count += 1
            time.sleep(0.05)
        return success_count, failed_count
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
    """Create a pending manual-QR payment record in payment_claims."""
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
        import traceback
        traceback.print_exc()
        return None

def fulfill_manual_claim(claim):
    """Apply the purchased plan to telegram_users/protected_numbers."""
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
            return True, "Bot booking confirmed. Delivery window: 24 to 48 hours after requirements are clear."

        return False, "Unknown payment type"

    except Exception as e:
        print(f"Fulfill manual claim error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def manual_verify_payment(tx_code, admin_id=None):
    """Admin command: /verify TXCODE"""
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
                f"✅ *Payment Verified!*\n\n{detail}\n\n🧾 TX: `{tx_code}`\n\nUse /start to refresh.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"User payment verified message failed: {e}")

        try:
            bot.send_message(
                ADMIN_CHANNEL_ID,
                f"✅ *MANUAL PAYMENT VERIFIED*\n━━━━━━━━━━━━━━━━\n👤 User: `{telegram_user_id}`\n📦 Plan: `{claim.get('plan_id')}`\n💰 Amount: ₹{claim.get('amount')}\n🧾 TX: `{tx_code}`\n🛠 By: `{admin_id or ADMIN_ID}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Admin channel verify log failed: {e}")

        return True, detail

    except Exception as e:
        print(f"Manual verify error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def manual_reject_payment(tx_code, admin_id=None, reason="Payment not confirmed"):
    """Admin command/button: reject a pending manual payment claim."""
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
                f"❌ *Payment Rejected*\n\n🧾 TX: `{tx_code}`\nReason: `{reason}`\n\nAgar payment kiya hai to clear screenshot/UTR ke saath admin ko contact karo: {ADMIN_USERNAME}",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"User reject message failed: {e}")

        try:
            bot.send_message(
                ADMIN_CHANNEL_ID,
                f"❌ *MANUAL PAYMENT REJECTED*\n━━━━━━━━━━━━━━━━\n👤 User: `{telegram_user_id}`\n📦 Plan: `{claim.get('plan_id')}`\n💰 Amount: ₹{claim.get('amount')}\n🧾 TX: `{tx_code}`\n🛠 By: `{admin_id or ADMIN_ID}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Admin channel reject log failed: {e}")

        return True, "Payment rejected"
    except Exception as e:
        print(f"Manual reject error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def get_manual_claim_status(tx_code):
    """Return current manual payment status for a TX code."""
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
    """Send payment reminders only - NO AUTO REJECTION"""
    try:
        time.sleep(60)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"""⏰ *Payment Reminder* 💬

🧾 TX: `{tx_code}`
📦 Plan: `{plan_label}`

Agar payment ho gaya hai to please payment screenshot yahin share karo, taaki admin verify kar sake.

Admin will verify your payment manually. We don't auto-reject payments.""",
                parse_mode="Markdown"
            )

        time.sleep(120)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"""✅ *Don't worry!* 💪

🧾 TX: `{tx_code}`

Aapka payment safe rahega. Screenshot share karo, plan verify hone ke baad enjoy kar paoge.

No auto-rejection - Your payment will remain pending until admin manually verifies it.""",
                parse_mode="Markdown"
            )

        time.sleep(180)
        status = get_manual_claim_status(tx_code)
        if status == "pending":
            bot.send_message(
                chat_id,
                f"""📌 *Final Reminder* ⏳

🧾 TX: `{tx_code}`

Payment session is still pending. 
Kindly share your payment screenshot to get your plan activated.

Admin will verify as soon as possible. No auto-rejection - your payment is safe!""",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Payment reminder worker error for {tx_code}: {e}")

def send_manual_qr_payment(chat_id, user_id, username, plan_id, protected_number=None):
    """Send static QR image + fixed amount details. Admin verifies manually."""
    plan = get_plan_config(plan_id)
    if not plan:
        bot.send_message(chat_id, "❌ Invalid plan selected.", reply_markup=get_main_keyboard_for_user(user_id))
        return

    now_ts = time.time()
    last_ts = payment_session_cooldown.get(user_id, 0)
    remaining = int(PAYMENT_SESSION_COOLDOWN_SECONDS - (now_ts - last_ts))
    if remaining > 0:
        bot.send_message(chat_id, f"⏳ *QR already generated recently!*\n\nPlease wait `{remaining}` seconds before creating another payment session.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode="Markdown")
        return
    payment_session_cooldown[user_id] = now_ts

    tx_code = create_manual_payment_claim(plan_id, user_id, username, protected_number)
    if not tx_code:
        bot.send_message(chat_id, f"❌ Could not create payment record. Contact {ADMIN_USERNAME}.", parse_mode="Markdown")
        return

    extra = f"\n📱 Number: `{protected_number}`" if protected_number else ""
    caption = f"""
💳 *Scan & Pay* 📱
━━━━━━━━━━━━━━━━━━
💰 Amount: ₹{plan['amount']}
📦 Plan: `{plan['label']}`{extra}
🧾 TX ID: `{tx_code}`

✅ Pay exactly ₹{plan['amount']} on this QR.
📩 After payment, tap below and send screenshot here. It will be forwarded to admin for manual verification.

━━━━━━━━━━━━━━━━━━
📞 Admin: {ADMIN_USERNAME}
"""

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 SEND PAYMENT SCREENSHOT", callback_data=f"submitproof_{tx_code}"))
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
                caption + "\n⚠️ QR image file missing on server. Add `payment_qr.png` beside bot.py.",
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Send QR failed: {e}")
        bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")

    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY PAYMENT", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )
    
    send_admin_alert(
        f"💳 *MANUAL QR PAYMENT CREATED*\n━━━━━━━━━━━━━━━━\n👤 *User Details:*\n• ID: `{user_id}`\n• Username: @{username if username != 'no_username' else 'N/A'}\n• Name: {user_id}\n\n📦 *Plan Details:*\n• Plan ID: `{plan_id}`\n• Plan Name: `{plan['label']}`\n• Amount: ₹{plan['amount']}\n\n🧾 *Transaction:* `{tx_code}`\n\n📱 *Protected Value:* `{protected_number if protected_number else 'N/A'}`\n\n⚠️ *Action Required:* Verify after checking screenshot/payment",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )
    threading.Thread(
        target=payment_session_reminder_worker,
        args=(chat_id, user_id, tx_code, plan.get("label", plan_id)),
        daemon=True
    ).start()

# ==================== DAILY SEARCH REPORT ====================
def record_search_for_daily_report(user_id, username, first_name, query_value, found=True, lookup_type="number", credits_used=0):
    """Store only aggregate lookup stats for the 6 AM report."""
    try:
        key = str(user_id)
        lookup_type = str(lookup_type or "number").lower()
        with daily_stats_lock:
            row = daily_search_stats.setdefault(key, {
                "user_id": user_id,
                "username": username or "no_username",
                "first_name": first_name or "User",
                "searches": 0,
                "number_searches": 0,
                "telegram_searches": 0,
                "identity_searches": 0,
                "ifsc_searches": 0,
                "pan_searches": 0,
                "vehicle_searches": 0,
                "vehicle_owner_searches": 0,
                "email_searches": 0,
                "credits_used": 0,
                "found": 0,
                "not_found": 0,
                "last_query": ""
            })
            row["searches"] += 1
            row["last_query"] = query_value
            row["credits_used"] += int(credits_used or 0)
            if lookup_type == "telegram":
                row["telegram_searches"] = row.get("telegram_searches", 0) + 1
            elif lookup_type == "identity":
                row["identity_searches"] = row.get("identity_searches", 0) + 1
            elif lookup_type == "ifsc":
                row["ifsc_searches"] = row.get("ifsc_searches", 0) + 1
            elif lookup_type == "pan":
                row["pan_searches"] = row.get("pan_searches", 0) + 1
            elif lookup_type == "vehicle":
                row["vehicle_searches"] = row.get("vehicle_searches", 0) + 1
            elif lookup_type == "vehicle_owner":
                row["vehicle_owner_searches"] = row.get("vehicle_owner_searches", 0) + 1
            elif lookup_type == "email":
                row["email_searches"] = row.get("email_searches", 0) + 1
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
    identity_searches = sum(v.get("identity_searches", 0) for v in stats_snapshot.values())
    ifsc_searches = sum(v.get("ifsc_searches", 0) for v in stats_snapshot.values())
    pan_searches = sum(v.get("pan_searches", 0) for v in stats_snapshot.values())
    vehicle_searches = sum(v.get("vehicle_searches", 0) for v in stats_snapshot.values())
    vehicle_owner_searches = sum(v.get("vehicle_owner_searches", 0) for v in stats_snapshot.values())
    email_searches = sum(v.get("email_searches", 0) for v in stats_snapshot.values())
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
        f"🆔 Identity Lookups: `{identity_searches}`",
        f"🏦 IFSC Lookups: `{ifsc_searches}`",
        f"🪪 PAN Lookups: `{pan_searches}`",
        f"🚗 Vehicle Lookups: `{vehicle_searches}`",
        f"🔍 Vehicle Owner Lookups: `{vehicle_owner_searches}`",
        f"📧 Email Lookups: `{email_searches}`",
        f"💎 Credits Used: `{credits_used}`",
        f"✅ Found: `{found}`",
        f"❌ No Data: `{not_found}`",
        "",
        "🏆 *TOP SEARCHERS*"
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
    """Send one aggregated report every day at 6 AM IST."""
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

# ==================== NUMBER LOOKUP FUNCTIONS ====================
def process_lookup(message):
    user_id = message.from_user.id
    raw_phone = str(message.text or "").strip()

    if raw_phone == "❌ CANCEL" or raw_phone == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    if user_states.get(user_id) != "awaiting_number":
        return

    user_states.pop(user_id, None)
    phone = normalize_indian_mobile(raw_phone)

    if not phone:
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter Indian mobile number.\nExamples: `9876543210` or `+919876543210`", 
                    reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    with active_sessions_lock:
        if user_id in active_sessions:
            bot.reply_to(message, "⏳ *One number search already running!*\n\nPlease wait for current search result before starting another.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        active_sessions.add(user_id)
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            active_sessions.discard(user_id)
            return
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    
    unlimited_active = False
    unlimited_expiry = None
    unlimited_expiry_raw = user.get('unlimited_expiry') if user else None
    if unlimited_expiry_raw:
        try:
            if isinstance(unlimited_expiry_raw, str):
                expiry_date = datetime.fromisoformat(unlimited_expiry_raw.replace('Z', '+00:00'))
            else:
                expiry_date = unlimited_expiry_raw
            if expiry_date > datetime.now(timezone.utc):
                unlimited_active = True
                unlimited_expiry = unlimited_expiry_raw
        except:
            pass
    
    if total_credits < NUMBER_LOOKUP_COST and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* Number Lookup costs `{NUMBER_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        active_sessions.discard(user_id)
        return
    
    if is_number_protected(phone):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECT MY NUMBER", callback_data="protect"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.reply_to(message, f"""
🛡️ *PROTECTED NUMBER* 🔒

📱 `{phone}`

This number is protected by the Number Protection Plan.

The owner has purchased privacy protection. Details are hidden.

You can also protect your number for ₹99!
""", reply_markup=markup, parse_mode='Markdown')
        active_sessions.discard(user_id)
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching...*", parse_mode='Markdown')
    
    for anim in ["🔍", "🔎", "🔍"]:
        time.sleep(0.8)
        bot.edit_message_text(f"{anim} *Searching...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    cached_result = get_cached_result(phone)
    
    if cached_result:
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        
        output = format_lookup_response(cached_result, phone, "Number", user_id, NUMBER_LOOKUP_COST, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        
        active_sessions.discard(user_id)
        return
    
    result, error = call_number_lookup_api(phone)

    if not result:
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="number")
        notify_admin_api_issue("number", phone, error)
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=False, lookup_type="number", credits_used=0)
        active_sessions.discard(user_id)
        return

    # Check if result has data
    has_data = False
    if isinstance(result, dict):
        if "raw_response" in result and result["raw_response"]:
            has_data = True
        elif len(result) > 0:
            has_data = True
    elif result:
        has_data = True

    if has_data:
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        save_cached_result(phone, result)
        output = format_lookup_response(result, phone, "Number", user_id, NUMBER_LOOKUP_COST, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        
        active_sessions.discard(user_id)
        
    else:
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*",
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_sessions.discard(user_id)
                return

        increment_total_searches(user_id)
        updated_total = get_total_credits(user_id)
        output = f"""
❌ *NO DATA FOUND* ❌
━━━━━━━━━━━━━━━━━━

📱 Number
`{phone}`

🚫 No records available in database

💡 Tips:
• Check number again
• Try another number
• Ensure Indian mobile number

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{0 if unlimited_active else NUMBER_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
{footer()}
"""

        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')

        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=False, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        active_sessions.discard(user_id)

def notify_admin_api_issue(lookup_type, query, error_reason):
    """Send compact admin-only debug alert."""
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ *API TEMP ISSUE*\n\nType: `{lookup_type}`\nQuery: `{query}`\nReason: `{str(error_reason)[:500]}`\n\nUser credits were not deducted.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Admin API issue notify failed: {e}")

def show_protection_menu(message):
    user_id = message.from_user.id
    text = f"""
🛡️ *PROTECTION SERVICES* 🔒
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹99
💬 Telegram Number Protection → ₹99

Protected data will not be shown in lookup results.
"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📱 PROTECT NUMBER - ₹99", callback_data="plan_protect_number"))
    markup.add(InlineKeyboardButton("💬 PROTECT TELEGRAM - ₹99", callback_data="plan_protect_telegram"))
    markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def process_protection_payment_input(message, plan_id):
    user_id = message.from_user.id
    if message.text == "❌ CANCEL" or message.text == "/cancel":
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return

    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_protection_input" and state.get("plan_id") == plan_id):
        return

    user_states.pop(user_id, None)
    value = str(message.text or "").strip()
    if plan_id == "protect_number":
        if not re.match(r'^[6-9]\d{9}$', value):
            bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        if is_number_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    elif plan_id == "protect_telegram":
        if not is_valid_telegram_id(value):
            bot.reply_to(message, "❌ *Invalid Telegram ID!*", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        if is_telegram_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
    else:
        bot.reply_to(message, "❌ Invalid protection plan.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        return
    send_manual_qr_payment(message.chat.id, user_id, message.from_user.username or "no_username", plan_id, protected_number=value)

# ==================== FLASK WEBHOOK (KEEP_ALIVE ONLY) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "TraceX Bot Running - Version 7.0.3"

def keep_alive():
    """Run Flask app in a separate thread"""
    def run():
        port = int(os.getenv("PORT", "8080"))
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ==================== PAYMENT HANDLERS ====================
def show_credit_packs(message, user_id):
    packs_msg = f"""
💎 *PREMIUM CREDIT STORE* 🛒
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS*
• 40 Credits → ₹20  
• 120 Credits → ₹50
• 400 Credits → ₹100

🚀 *UNLIMITED PLANS*
• 1 Hour Unlimited → ₹49
• 1 Day Unlimited → ₹99
• 7 Days Unlimited → ₹499
• 30 Days Unlimited → ₹1499

🛡️ *PROTECTION*
• Number Protection → ₹99
• Telegram Number Protection → ₹99

━━━━━━━━━━━━━━━━━━
✅ Permanent Credits NEVER EXPIRE
✅ Unlimited Plans for heavy users
✅ Manual payment verification

👇 Select your plan below
{footer()}
"""
    bot.send_message(message.chat.id, packs_msg, reply_markup=credit_packs_markup(), parse_mode='Markdown')

def handle_plan_selection(call):
    plan_id = call.data.replace("plan_", "")
    user_id = call.from_user.id
    username = call.from_user.username or "no_username"

    plan = PLAN_CONFIG.get(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Invalid plan selected.", show_alert=True)
        return

    if plan_id in ["protect_number", "protect_telegram"]:
        labels = {
            "protect_number": ("📱 *NUMBER PROTECTION* 🔒", "Enter the 10-digit mobile number you want to protect:", "`Example: 9876543210`"),
            "protect_telegram": ("💬 *TELEGRAM NUMBER PROTECTION* 🔒", "Enter numeric Telegram user ID:", "`Example: 7850023357`")
        }
        title, prompt, example = labels[plan_id]
        user_states[user_id] = {"state": "awaiting_protection_input", "plan_id": plan_id}
        msg = bot.send_message(
            call.message.chat.id,
            f"""{title}

{prompt}
{example}

💰 Price: `₹99`

After this QR payment will be created.

Type /cancel to abort""",
            reply_markup=cancel_button(),
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_protection_payment_input, plan_id)
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Sending QR... ✅")
    send_manual_qr_payment(call.message.chat.id, user_id, username, plan_id)

def show_bot_booking(message):
    user_id = message.from_user.id
    booking_msg = f"""
🤖 *CUSTOM BOT BOOKING* 🛠️
━━━━━━━━━━━━━━━━━━

💰 *Bot setup add-on:* ₹399
📆 *API charges:* Monthly, separate as per API provider
🔧 *Future updates:* ₹399 per update/change
⏰ *Delivery:* 24–48 hours after payment + clear requirements

✅ You can book bots for legal/public-data workflows, automation, payment system, admin panel, website+bot integration, alerts, reports, and similar tools.

⚠️ I will not build bots meant for private personal-data lookup, Aadhaar/PAN misuse, doxxing, or unauthorized data access.

👇 Tap below to create booking payment session.
{footer()}
"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("💳 BOOK BOT - PAY ₹399", callback_data="booking_pay"))
    markup.add(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"))
    markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
    bot.send_message(message.chat.id, booking_msg, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user = get_user(user_id)
    
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 YOU ARE BANNED\n\nContact: {ADMIN_USERNAME}")
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
    unlimited_expiry = user.get('unlimited_expiry') if user else None
    
    unlimited_text = ""
    if unlimited_expiry:
        try:
            if isinstance(unlimited_expiry, str):
                expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
            else:
                expiry_date = unlimited_expiry
            if expiry_date > datetime.now(timezone.utc):
                unlimited_text = f"\n🚀 Unlimited Active until: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
        except:
            pass
    
    welcome_msg = f"""
{header("TRACEX LOOKUP", "🚀")}

👋 Welcome, *{first_name}*

💎 *Credit Details:*
━━━━━━━━━━━━━━━━
💰 Credits: `{total_credits}`{unlimited_text}

🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`

━━━━━━━━━━━━━━━━
🎯 *FEATURES* ✨
• 📱 Number Lookup (2 Credits)
• 💬 Telegram Lookup (5 Credits)
• 🆔 Identity Lookup (5 Credits)
• 🏦 IFSC Lookup (3 Credits)
• 📧 Email Lookup (20 Credits)
• 🪪 PAN Lookup (5 Credits)
• 🚗 Vehicle Lookup (5 Credits)
• 🔍 Vehicle Owner Lookup (10 Credits)
• Fast Response • Secure Credits System
• Unlimited Plans Available • Protection Services

━━━━━━━━━━━━━━━━
🎁 New users get 10 free credits!

👇 Choose an option below
{footer()}
"""
    
    # Check channel membership - store result but send welcome either way
    missing = is_all_channels_member(user_id)
    if missing:
        msg = get_missing_channels_message(missing)
        bot.send_message(
            message.chat.id,
            msg,
            reply_markup=join_required_markup(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    else:
        bot.send_message(message.chat.id, welcome_msg, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    with active_sessions_lock:
        active_sessions.discard(user_id)
    bot.reply_to(message, "❌ Cancelled. Use /start for main menu.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

@bot.message_handler(content_types=['photo', 'document'])
def payment_screenshot_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_payment_screenshot"):
        return

    tx_code = state.get("tx_code")
    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, f"✅ Screenshot already sent to admin for TX `{tx_code}`.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
        return
    proof_forwarded_txs.add(tx_code)
    
    plan_name = "Unknown Plan"
    try:
        claim_resp = None
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
    
    caption = f"""📸 *PAYMENT SCREENSHOT RECEIVED* 🧾
━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 *User Details:*
• User ID: `{user_id}`
• Username: @{message.from_user.username if message.from_user.username else 'no_username'}
• Name: {message.from_user.first_name or 'N/A'}

📦 *Plan Details:*
• Plan Name: `{plan_name}`
• TX Code: `{tx_code}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Action Required:* Verify only after checking payment screenshot

/adminverify_{tx_code} - to verify
/adminreject_{tx_code} - to reject"""
    
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ VERIFY PAYMENT", callback_data=f"adminverify_{tx_code}"),
        InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}")
    )

    try:
        # Try to send to admin channel first
        try:
            bot.copy_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        except Exception as forward_error:
            print(f"Admin group screenshot copy failed: {forward_error}")
            try:
                bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
            except Exception as dm_forward_error:
                print(f"Admin DM screenshot copy failed: {dm_forward_error}")
        
        send_admin_alert(caption, reply_markup=admin_markup, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Screenshot sent to admin.\n\n🧾 TX: `{tx_code}`\n📦 Plan: `{plan_name}`\n⏳ Wait for manual verification.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        print(f"Payment screenshot forward error: {e}")
        bot.reply_to(message, f"❌ Could not forward screenshot. Contact {ADMIN_USERNAME}", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

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
    else:
        bot.reply_to(message, "Invalid option!\nUse:\n/maintenance on\n/maintenance off")

# ==================== TEXT MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def text_handler(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user and user.get('is_banned'):
        bot.reply_to(message, f"🚫 YOU ARE BANNED\n\nContact: {ADMIN_USERNAME}")
        return

    # Check channel membership - silently check every time
    missing = is_all_channels_member(user_id)
    if missing:
        msg = get_missing_channels_message(missing)
        bot.send_message(
            message.chat.id,
            msg,
            reply_markup=join_required_markup(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    text = message.text.strip()

    if user_states.get(user_id) == "awaiting_number":
        process_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_telegram_username":
        process_telegram_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_identity_input":
        process_identity_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_ifsc_input":
        process_ifsc_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_pan_input":
        process_pan_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_vehicle_input":
        process_vehicle_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_vehicle_owner_input":
        process_vehicle_owner_lookup(message)
        return
    elif user_states.get(user_id) == "awaiting_email_input":
        process_email_lookup(message)
        return
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("state") == "awaiting_protection_input":
        plan_id = user_states[user_id].get("plan_id")
        if plan_id:
            process_protection_payment_input(message, plan_id)
        return

    if text == "📱 NUMBER LOOKUP":
        user_states[user_id] = "awaiting_number"
        bot.reply_to(message, "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\n💎 Cost: `2 credits` per search\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "💬 TELEGRAM LOOKUP":
        user_states[user_id] = "awaiting_telegram_username"
        bot.reply_to(message, "💬 *Enter Telegram Username:*\n\n`Example: @username` or `username`\n\n💎 Cost: `5 credits` per search\n\n🛡️ After lookup, you can protect your Telegram ID for ₹99!\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🆔 IDENTITY LOOKUP":
        user_states[user_id] = "awaiting_identity_input"
        bot.reply_to(message, "🆔 *Enter Aadhar Number:*\n\n`Example: 123456789012`\n\n💎 Cost: `5 credits` per search\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🏦 IFSC LOOKUP":
        user_states[user_id] = "awaiting_ifsc_input"
        bot.reply_to(message, "🏦 *Enter IFSC Code:*\n\n`Example: HDFC0001325`\n\n💎 Cost: `3 credits` per search\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "📧 EMAIL LOOKUP":
        user_states[user_id] = "awaiting_email_input"
        bot.reply_to(message, "📧 *Enter Email Address:*\n\n`Example: user@example.com`\n\n💎 Cost: `20 credits` per search\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🪪 PAN LOOKUP":
        user_states[user_id] = "awaiting_pan_input"
        bot.reply_to(message, "🪪 *Enter PAN Card Number:*\n\n`Example: NTEPK1628C`\n\n💎 Cost: `5 credits` per search\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🚗 VEHICLE LOOKUP":
        user_states[user_id] = "awaiting_vehicle_input"
        bot.reply_to(message, "🚗 *Enter Vehicle Registration Number:*\n\n`Example: BR07PB6268`\n\n💎 Cost: `5 credits` per search\n\nType ❌ CANCEL to abort", 
                    reply_markup=get_cancel_keyboard(), parse_mode='Markdown')
    
    elif text == "🔍 VEHICLE OWNER":
        user_states[user_id] = "awaiting_vehicle_owner_input"
        bot.reply_to(message, "🔍 *Enter Vehicle Number for Owner Lookup:*\n\n`Example: BR07PB6268`\n\n💎 Cost: `10 credits` per search\n\nType ❌ CANCEL to abort", 
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
                    unlimited_text = f"\n🚀 *Unlimited Plan Active*\n   Expires: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        credits_msg = f"""
*💎 MY CREDITS* 💰
━━━━━━━━━━━━━━━━━━
💰 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Used:* `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
*📦 CREDIT PACKS*
• 40 Credits → ₹20  
• 120 Credits → ₹50
• 400 Credits → ₹100
*🚀 UNLIMITED PLANS*
• 1 Hour → ₹49
• 1 Day → ₹99
• 7 Days → ₹499
• 30 Days → ₹1499
*🛡️ PROTECTION*
• Number Protection → ₹99
• Telegram Number Protection → ₹99
"""
        bot.reply_to(message, credits_msg, parse_mode='Markdown')
    
    elif text == "🛒 BUY CREDITS":
        show_credit_packs(message, user_id)
    
    elif text == "🛡️ PROTECTION":
        show_protection_menu(message)
    
    elif text == "📢 SUPPORT":
        support_msg = f"""
📢 *SUPPORT & COMMUNITY* 🤝
━━━━━━━━━━━━━━━━━━

👨‍💻 *Admin:* {ADMIN_USERNAME}
👥 *Group:* [Join Community]({GROUP_LINK})
🌐 *Website:* {WEBSITE_URL}

For any issues, contact admin directly.
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👥 JOIN GROUP", url=GROUP_LINK))
        markup.add(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"))
        bot.reply_to(message, support_msg, reply_markup=markup, parse_mode='Markdown')
    
    elif text == "🛠 ADMIN PANEL":
        if user_id != ADMIN_ID:
            bot.reply_to(message, "❌ Unauthorized!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            return
        show_admin_panel(message)
    
    elif text == "❌ CANCEL":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        with active_sessions_lock:
            active_sessions.discard(user_id)
        bot.reply_to(message, "❌ Cancelled!", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    
    else:
        bot.reply_to(message, "❌ *Unknown command!*\n\nUse /start to see the main menu.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if user and user.get('is_banned'):
        bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
        return

    if call.data == "check_all_join":
        missing = is_all_channels_member(user_id)
        if not missing:
            bot.answer_callback_query(call.id, "All channels joined verified! ✅", show_alert=True)
            try:
                bot.edit_message_text("✅ *All channels joined verified!*\n\nUse /start to open bot menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode="Markdown")
            except Exception:
                bot.send_message(call.message.chat.id, "✅ All channels joined verified! Use /start")
        else:
            msg = get_missing_channels_message(missing)
            bot.answer_callback_query(call.id, "Please join all missing channels", show_alert=True)
            try:
                bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=join_required_markup(), parse_mode="Markdown")
            except Exception:
                bot.send_message(call.message.chat.id, msg, reply_markup=join_required_markup(), parse_mode="Markdown")
        return

    # Check channel membership for all other actions
    missing = is_all_channels_member(user_id)
    if missing:
        msg = get_missing_channels_message(missing)
        bot.answer_callback_query(call.id, "Please join all channels first", show_alert=True)
        try:
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=join_required_markup(), parse_mode="Markdown")
        except Exception:
            bot.send_message(call.message.chat.id, msg, reply_markup=join_required_markup(), parse_mode="Markdown")
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
        with active_sessions_lock:
            active_sessions.discard(user_id)
        try:
            bot.edit_message_text("❌ Cancelled. Use /start for main menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        except Exception:
            try:
                bot.edit_message_caption("❌ Cancelled. Use /start for main menu.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
            except Exception:
                bot.send_message(call.message.chat.id, "❌ Cancelled. Use /start for main menu.", reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Cancelled")
    
    elif call.data == "lookup":
        user_states[user_id] = "awaiting_number"
        msg = bot.send_message(call.message.chat.id, "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\n💎 Cost: `2 credits` per search\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "telegram_lookup":
        user_states[user_id] = "awaiting_telegram_username"
        msg = bot.send_message(call.message.chat.id, "💬 *Enter Telegram Username:*\n\n`Example: @username` or `username`\n\n💎 Cost: `5 credits` per search\n\n🛡️ After lookup, you can protect your Telegram ID for ₹99!\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_telegram_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "identity_lookup":
        user_states[user_id] = "awaiting_identity_input"
        msg = bot.send_message(call.message.chat.id, "🆔 *Enter Aadhar Number:*\n\n`Example: 123456789012`\n\n💎 Cost: `5 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_identity_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "ifsc_lookup":
        user_states[user_id] = "awaiting_ifsc_input"
        msg = bot.send_message(call.message.chat.id, "🏦 *Enter IFSC Code:*\n\n`Example: HDFC0001325`\n\n💎 Cost: `3 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_ifsc_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "email_lookup":
        user_states[user_id] = "awaiting_email_input"
        msg = bot.send_message(call.message.chat.id, "📧 *Enter Email Address:*\n\n`Example: user@example.com`\n\n💎 Cost: `20 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_email_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "pan_lookup":
        user_states[user_id] = "awaiting_pan_input"
        msg = bot.send_message(call.message.chat.id, "🪪 *Enter PAN Card Number:*\n\n`Example: NTEPK1628C`\n\n💎 Cost: `5 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_pan_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "vehicle_lookup":
        user_states[user_id] = "awaiting_vehicle_input"
        msg = bot.send_message(call.message.chat.id, "🚗 *Enter Vehicle Registration Number:*\n\n`Example: BR07PB6268`\n\n💎 Cost: `5 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_vehicle_lookup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "vehicle_owner_lookup":
        user_states[user_id] = "awaiting_vehicle_owner_input"
        msg = bot.send_message(call.message.chat.id, "🔍 *Enter Vehicle Number for Owner Lookup:*\n\n`Example: BR07PB6268`\n\n💎 Cost: `10 credits` per search\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_vehicle_owner_lookup)
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
                    unlimited_text = f"\n🚀 *Unlimited Plan Active*\n   Expires: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        credits_msg = f"""
*💎 MY CREDITS* 💰
━━━━━━━━━━━━━━━━━━
💰 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Used:* `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
*📦 CREDIT PACKS*
• 40 Credits → ₹20  
• 120 Credits → ₹50
• 400 Credits → ₹100
*🚀 UNLIMITED PLANS*
• 1 Hour → ₹49
• 1 Day → ₹99
• 7 Days → ₹499
• 30 Days → ₹1499
*🛡️ PROTECTION*
• Number Protection → ₹99
• Telegram Number Protection → ₹99
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"))
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(credits_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "buy":
        show_credit_packs(call.message, user_id)
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
        bot.send_message(call.message.chat.id, f"📸 *Send payment screenshot now*\n\n🧾 TX: `{tx_code}`\n\nYour screenshot will be forwarded to admin for manual verification.", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Now send screenshot here")
    
    elif call.data.startswith("adminverify_"):
        if user_id != ADMIN_ID:
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
        if user_id != ADMIN_ID:
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
                    unlimited_text = f"\n🚀 Unlimited until: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`"
            except:
                pass
        profile_msg = f"""
👤 *USER PROFILE* 👤
━━━━━━━━━━━━━━━━━━
🆔 User ID: `{user_id}`
👤 Name: `{call.from_user.first_name}`
💎 *Credits:* `{total_credits}`{unlimited_text}
🔎 Total Searches: `{user.get('total_searches', 0) if user else 0}`
🛡️ Account Status: `{'ACTIVE ✅' if not (user and user.get('is_banned')) else 'BANNED ❌'}`
━━━━━━━━━━━━━━━━━━
🚀 Thanks for using TraceX
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.edit_message_text(profile_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "help":
        help_msg = f"""
📖 *HOW TO USE TRACEX* 📚
━━━━━━━━━━━━━━━━━━
1️⃣ Click NUMBER LOOKUP
2️⃣ Enter mobile number
3️⃣ Get instant results

📱 *TELEGRAM LOOKUP*
1️⃣ Click TELEGRAM LOOKUP
2️⃣ Enter @username
3️⃣ Get Telegram ID and phone number
4️⃣ Option to protect your Telegram ID for ₹99

🆔 *IDENTITY LOOKUP*
1️⃣ Click IDENTITY LOOKUP
2️⃣ Enter 12-digit Aadhar number
3️⃣ Get identity information

🏦 *IFSC LOOKUP*
1️⃣ Click IFSC LOOKUP
2️⃣ Enter IFSC code
3️⃣ Get bank branch details

📧 *EMAIL LOOKUP*
1️⃣ Click EMAIL LOOKUP
2️⃣ Enter email address
3️⃣ Get email information

🪪 *PAN LOOKUP*
1️⃣ Click PAN LOOKUP
2️⃣ Enter PAN card number
3️⃣ Get PAN details

🚗 *VEHICLE LOOKUP*
1️⃣ Click VEHICLE LOOKUP
2️⃣ Enter vehicle number
3️⃣ Get vehicle details

🔍 *VEHICLE OWNER*
1️⃣ Click VEHICLE OWNER
2️⃣ Enter vehicle number
3️⃣ Get owner details

━━━━━━━━━━━━━━━━━━
💎 *CREDIT SYSTEM*
• New User: `10` free credits
• Credits never expire
• Number Lookup: 2 credits
• Telegram Lookup: 5 credits
• Identity Lookup: 5 credits
• IFSC Lookup: 3 credits
• Email Lookup: 20 credits
• PAN Lookup: 5 credits
• Vehicle Lookup: 5 credits
• Vehicle Owner: 10 credits
• Unlimited plans available
• Protection plans cost ₹99 each
━━━━━━━━━━━━━━━━━━
🛒 BUYING
• Select plan
• Scan QR, pay exact amount, then send screenshot
• Admin verifies manually
━━━━━━━━━━━━━━━━━━
⚡ FEATURES
✅ Fast Number Lookup
✅ Telegram ID Lookup
✅ Identity/Aadhar Lookup
✅ IFSC Bank Lookup
✅ Email Lookup
✅ PAN Card Lookup
✅ Vehicle Lookup
✅ Vehicle Owner Lookup
✅ Unlimited Plans
✅ Number Protection
✅ Secure Payments
{footer()}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.edit_message_text(help_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        show_admin_panel(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data == "broadcast_confirm":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        confirm_broadcast(call)
    
    elif call.data == "giveaway_confirm":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        confirm_giveaway(call)
    
    elif call.data in ["admin_add", "admin_remove", "admin_ban", "admin_unban", "admin_broadcast", "admin_stats", "admin_transactions", "admin_back", "admin_giveaway"]:
        if user_id != ADMIN_ID:
            return
        if call.data == "admin_add":
            user_states[user_id] = "admin_add"
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS / UNLIMITED* 💰\n\nCredits format:\n`user_id credits`\nExample: `123456789 50`\n\nUnlimited format:\n`user_id u1h` / `user_id u1d` / `user_id u1w` / `user_id u1m`\nExample: `123456789 u1d`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE CREDITS / DEACTIVATE UNLIMITED*\n\nRemove credits:\n`user_id_or_username credits`\n`@username credits`\nExample: `@gaurav 10`\n\nDeactivate unlimited:\n`user_id_or_username unlimited`\n`@username off`\nExample: `@gaurav unlimited`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_remove)
        elif call.data == "admin_ban":
            user_states[user_id] = "admin_ban"
            msg = bot.send_message(call.message.chat.id, "🚫 *BAN USER* ⛔\n\nEnter user ID to ban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_ban)
        elif call.data == "admin_unban":
            user_states[user_id] = "admin_unban"
            msg = bot.send_message(call.message.chat.id, "✅ *UNBAN USER* 🔓\n\nEnter user ID to unban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_unban)
        elif call.data == "admin_broadcast":
            user_states[user_id] = "admin_broadcast"
            msg = bot.send_message(call.message.chat.id, "📢 *BROADCAST* 📣\n\nSend your broadcast message below:\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_broadcast)
        elif call.data == "admin_giveaway":
            user_states[user_id] = "admin_giveaway"
            msg = bot.send_message(call.message.chat.id, "🎁 *GIVEAWAY CREDITS* 🎉\n\nEnter number of credits to give to ALL users:\n\nExample: `50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
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
*🛠 ADMIN PANEL* ⚙️
*📊 STATS*
👥 Users: `{stats['total_users']}`
🔍 Searches: `{stats['total_searches']}`
💾 Cache: `{stats['cache_size']}`
🛡️ Protected: `{stats['protected_count']}`
*💎 CREDITS SYSTEM*
💰 Total Credits: `{stats['total_credits']}`
*💰 FINANCIAL*
💵 Revenue: ₹{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
🚫 Banned: `{stats['banned_users']}`
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
    """
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ ADD CREDITS/PLAN", callback_data="admin_add"),
        InlineKeyboardButton("➖ REMOVE / DEACTIVATE", callback_data="admin_remove")
    )
    markup.add(
        InlineKeyboardButton("🚫 BAN USER", callback_data="admin_ban"),
        InlineKeyboardButton("✅ UNBAN USER", callback_data="admin_unban")
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
*📊 DETAILED STATS* 📈
━━━━━━━━━━━━━━━━━━
👥 *USERS*
━━━━━━━━━━━━━━━━━━
Total Users: `{stats['total_users']}`
Banned Users: `{stats['banned_users']}`
Active Users: `{stats['total_users'] - stats['banned_users']}`
━━━━━━━━━━━━━━━━━━
💎 *CREDITS*
━━━━━━━━━━━━━━━━━━
Total Credits: `{stats['total_credits']}`
━━━━━━━━━━━━━━━━━━
📊 *USAGE*
━━━━━━━━━━━━━━━━━━
Total Searches: `{stats['total_searches']}`
Cache Size: `{stats['cache_size']}`
Protected Numbers: `{stats['protected_count']}`
━━━━━━━━━━━━━━━━━━
💰 *FINANCIAL*
━━━━━━━━━━━━━━━━━━
Total Revenue: ₹{stats['total_revenue']}
Pending Payments: `{stats['pending_payments']}`
📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
    """
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, stats_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_transactions(message):
    transactions = get_recent_transactions()
    if not transactions:
        trans_msg = "📋 *No transactions found!*"
    else:
        trans_msg = "*📋 RECENT TRANSACTIONS* 📋\n\n"
        for trans in transactions:
            status_emoji = "✅" if trans.get('status') == "success" else "⏳" if trans.get('status') == "pending" else "❌"
            trans_msg += f"{status_emoji} `{trans.get('payment_id', '')[:20]}` | User: `{trans.get('telegram_user_id', '')}` | ₹{trans.get('amount', 0)} | {trans.get('plan_id', '')}\n"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    bot.send_message(message.chat.id, trans_msg, reply_markup=markup, parse_mode='Markdown')

def process_admin_add(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
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
            bot.reply_to(message, "❌ User not found. Use numeric Telegram ID or exact @username already saved in bot DB.", parse_mode='Markdown')
            return
        value = parts[1].strip().lower()

        if value in ["u1h", "u1d", "u1w", "u1m"]:
            ok, new_expiry = activate_unlimited_plan_for_user(target_user, value)
            if not ok:
                bot.reply_to(message, "❌ Invalid unlimited plan.", parse_mode='Markdown')
                return
            label = get_plan_config(value).get("label", value)
            bot.reply_to(message, f"✅ Added `{label}` to `{target_user}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🚀 *Unlimited Plan Added!* ✨\nPlan: `{label}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                pass
            return

        credits = int(value)
        new_total = add_credits(target_user, credits)
        bot.reply_to(message, f"✅ Added {credits} credits to `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, f"✅ *{credits} credits added!* 💰\nNew total: `{new_total}`\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Invalid format!\nCredits: `user_id/@username credits`\nUnlimited: `user_id/@username u1h/u1d/u1w/u1m`", parse_mode='Markdown')

def process_admin_remove(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
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
            bot.reply_to(message, "❌ User not found. Use numeric Telegram ID or exact @username already saved in bot DB.", parse_mode='Markdown')
            return
        action = parts[1].strip().lower()
        if action in ["unlimited", "deactivate", "off", "u0", "remove_unlimited"]:
            supabase.table("telegram_users").update({
                "unlimited_expiry": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", target_user).execute()
            bot.reply_to(message, f"✅ Unlimited plan deactivated for `{target_user}`", parse_mode='Markdown')
            try:
                bot.send_message(target_user, f"🧨 *Unlimited Plan Deactivated*\n\nYour unlimited access has been removed by admin.\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                pass
            return
        credits = int(action)
        current_credits = int(user.get('credits', 0) or 0)
        new_credits = max(0, current_credits - credits)
        supabase.table("telegram_users").update({"credits": new_credits, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("telegram_user_id", target_user).execute()
        bot.reply_to(message, f"✅ Removed {credits} credits from `{target_user}`\nNew total: `{new_credits}`", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "❌ Invalid format!\nRemove credits: `user_id/@username credits`\nDeactivate unlimited: `user_id/@username unlimited`", parse_mode='Markdown')

def process_admin_ban(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
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
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
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
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    broadcast_text = (message.text or message.caption or "").strip()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ YES, SEND", callback_data="broadcast_confirm"), InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel"))
    temp_data[user_id] = {'broadcast_text': broadcast_text}
    bot.reply_to(message, f"📢 *Confirm Broadcast* 📣\n\n📝 Message:\n`{broadcast_text}`\n\nSend to all active users?", reply_markup=markup, parse_mode='Markdown')

def process_admin_giveaway(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=get_main_keyboard_for_user(user_id))
        return
    try:
        credits = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ YES, GIVE AWAY", callback_data="giveaway_confirm"), InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel"))
        temp_data[user_id] = {'giveaway_credits': credits}
        bot.reply_to(message, f"🎁 *Confirm Giveaway* 🎉\n\nGive `{credits}` credits to ALL active users?\n\nThis will be sent to all users immediately!", reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number! Enter a valid credit amount.", parse_mode='Markdown')

def confirm_broadcast(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Broadcast cancelled. No data found.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id))
        return
    broadcast_text = temp_data[user_id]['broadcast_text']
    users = get_all_users()
    success = 0
    failed = 0
    bot.edit_message_text(f"📡 *Broadcasting to {len(users)} users...* 📡\n\nPlease wait...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    for target_user_id in users:
        try:
            broadcast_msg = f"""
*📢 TRACEX BROADCAST* 📣
{broadcast_text}
━━━━━━━━━━━━━━━━
📞 *Support:* {ADMIN_USERNAME}
👥 *Group:* [Join Community]({GROUP_LINK})
"""
            bot.send_message(target_user_id, broadcast_msg, parse_mode='Markdown', disable_web_page_preview=True)
            success += 1
        except Exception as e:
            failed += 1
            print(f"Broadcast failed to {target_user_id}: {e}")
        time.sleep(0.05)
    result_msg = f"""
✅ *Broadcast Complete!* 📢
📊 *Statistics:*
• ✅ Sent: `{success}` users
• ❌ Failed: `{failed}` users• 📝 Total: `{len(users)}` users
⏱️ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    del temp_data[user_id]

def confirm_giveaway(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Giveaway cancelled. No data found.", call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id))
        return
    credits = temp_data[user_id]['giveaway_credits']
    bot.edit_message_text(f"🎁 *Processing Giveaway...* 🎉\n\nGiving `{credits}` credits to all users...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    success, failed = add_giveaway_credits(credits)
    result_msg = f"""
🎉 *Giveaway Complete!* 🎉
✨ `{credits}` credits given to each user!
📊 *Statistics:*
• ✅ Successful: `{success}` users
• ❌ Failed: `{failed}` users
💎 Total Credits Distributed: `{success * credits}`
⏱️ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=get_main_keyboard_for_user(user_id), parse_mode='Markdown')
    del temp_data[user_id]

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

        if ok:
            bot.reply_to(message, f"✅ Verified\n\n{msg}")
        else:
            bot.reply_to(message, f"❌ {msg}")

    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['reject'])
def reject_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /reject TXCODE optional_reason")
            return
        tx_code = parts[1].strip()
        reason = parts[2].strip() if len(parts) > 2 else "Payment not confirmed"
        ok, msg = manual_reject_payment(tx_code, message.from_user.id, reason)
        bot.reply_to(message, f"{'✅' if ok else '❌'} {msg}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['apitest'])
def admin_api_test(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = str(message.text or "").split()
    phone = normalize_indian_mobile(parts[1] if len(parts) > 1 else "")
    if not phone:
        bot.reply_to(message, "Usage: /apitest 9876787776")
        return
    bot.reply_to(message, "🧪 Testing API with retry... check logs too.")
    result, error = call_number_lookup_api(phone)
    if result:
        bot.reply_to(message, f"✅ API OK\nResult: `{str(result)[:500]}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ API failed\nReason: `{str(error)[:500]}`", parse_mode="Markdown")

# ==================== START BOT ====================
if __name__ == "__main__":
    print("=" * 50)
    print(f"TraceX Lookup v{BOT_VERSION} is starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Admin: {ADMIN_USERNAME}")
    print("=" * 50)
    print("✅ New Features Added:")
    print("   • 📧 Email Lookup (20 Credits)")
    print("   • 🪪 PAN Card Lookup (5 Credits)")
    print("   • 🚗 Vehicle Lookup (5 Credits)")
    print("   • 🔍 Vehicle to Owner Number (10 Credits)")
    print("   • Updated APIs for all lookups")
    print("   • 4 Channel Verification System")
    print("   • Raw Response Pretty Print")
    print("   • Updated Pricing:")
    print("     • Number: 2 Credits")
    print("     • Telegram: 5 Credits")
    print("     • Identity: 5 Credits")
    print("     • IFSC: 3 Credits")
    print("     • Email: 20 Credits")
    print("     • PAN: 5 Credits")
    print("     • Vehicle: 5 Credits")
    print("     • Vehicle Owner: 10 Credits")
    print("   • Unlimited Plans:")
    print("     • 1 Hour - ₹49")
    print("     • 1 Day - ₹99")
    print("     • 7 Days - ₹499")
    print("     • 30 Days - ₹1499")
    print("   • Enhanced Broadcast System")
    print("   • Improved Payment Screenshot Handling")
    print("   • Channel Verification Check")
    print("=" * 50)
    
    # Start Flask keep_alive server
    keep_alive()
    print("✅ Flask server started on port 8080")

    threading.Thread(target=send_daily_search_report_loop, daemon=True).start()
    print("✅ Daily 6 AM IST report scheduler started")
    
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    
    def signal_handler(sig, frame):
        print("\n🛑 Bot stopped by user")
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
            if "409" in str(e) or "getUpdates" in str(e):
                print("⚠️ Telegram 409 conflict: stop old Render/Termux/other bot instance using same BOT_TOKEN.")
            time.sleep(5)