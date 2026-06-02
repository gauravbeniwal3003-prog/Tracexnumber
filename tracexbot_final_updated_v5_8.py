"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 5.5.1 - Manual Static QR Payment Flow
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import re
from datetime import datetime, timedelta, timezone
import os
import threading
import signal
import sys
import uuid
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
from supabase import create_client, Client

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7850023357"))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1003743686626"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@gaurav_beniwal_0001")
BOT_VERSION = "5.8.0"

# Lookup API Configuration
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/api/v1/lookup.php")
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "TVB_SGL_053B3AA6")
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number")


NUMBER_LOOKUP_COST = 10
TELEGRAM_LOOKUP_COST = 10
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

# Manual QR Plan Configuration
PLAN_CONFIG = {
    "c10": {"amount": 20, "credits": 10, "unlimited_minutes": 0, "payment_for": "credits", "label": "10 Credits"},
    "c50": {"amount": 70, "credits": 50, "unlimited_minutes": 0, "payment_for": "credits", "label": "50 Credits"},
    "c100": {"amount": 100, "credits": 100, "unlimited_minutes": 0, "payment_for": "credits", "label": "100 Credits"},
    "u1h": {"amount": 34, "credits": 0, "unlimited_minutes": 60, "payment_for": "unlimited", "label": "1 Hour Unlimited"},
    "u1d": {"amount": 88, "credits": 0, "unlimited_minutes": 1440, "payment_for": "unlimited", "label": "1 Day Unlimited"},
    "u1w": {"amount": 358, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited"},
    "u1m": {"amount": 898, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited"},
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram Number Protection"},
    "protect_vehicle": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_vehicle", "label": "Vehicle Number Protection"},
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
CASHFREE_API_BASE = None
CASHFREE_API_VERSION = "2023-08-01"

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Supabase Client
# Backend writes need service role key because RLS can block inserts/updates from anon key.
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
proof_forwarded_txs = set()

# 24-hour search summary storage. No per-search spam is sent to admin channel.
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
    markup.add(InlineKeyboardButton("📱 NUMBER LOOKUP", callback_data="lookup"))
    markup.add(
        InlineKeyboardButton("💎 MY CREDITS", callback_data="credits"),
        InlineKeyboardButton("🤖 BOOK A BOT", callback_data="book_bot")
    )
    markup.add(
        InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"),
        InlineKeyboardButton("🛡️ PROTECTION", callback_data="protection_menu")
    )
    markup.add(
        InlineKeyboardButton("👤 PROFILE", callback_data="profile"),
        InlineKeyboardButton("ℹ️ HELP", callback_data="help")
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
        InlineKeyboardButton("💰 10 Credits - ₹20", callback_data="plan_c10"),
        InlineKeyboardButton("💰 50 Credits - ₹70", callback_data="plan_c50"),
        InlineKeyboardButton("💰 100 Credits - ₹100", callback_data="plan_c100")
    )
    markup.add(
        InlineKeyboardButton("🚀 1 Hour Unlimited - ₹34", callback_data="plan_u1h"),
        InlineKeyboardButton("🚀 1 Day Unlimited - ₹88", callback_data="plan_u1d")
    )
    markup.add(
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹358", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹898", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Number Protection - ₹99", callback_data="plan_protect_number")
    )
    markup.add(
        InlineKeyboardButton("💬 Telegram Protection - ₹99", callback_data="plan_protect_telegram"),
        InlineKeyboardButton("🚘 Vehicle Protection - ₹99", callback_data="plan_protect_vehicle")
    )
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
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
                "credits": 3,
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
        # First check if user exists
        response = supabase.table("telegram_users").select("credits, telegram_user_id, telegram_name").eq("telegram_user_id", telegram_user_id).execute()
        
        if not response.data or len(response.data) == 0:
            print(f"User {telegram_user_id} not found, creating new user...")
            new_user = {
                "telegram_user_id": telegram_user_id,
                "credits": amount,
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

def update_user_credits(telegram_user_id, new_credits):
    """Update user credits and return updated credits. Returns None on failure."""
    try:
        print(f"Updating user {telegram_user_id} credits to {new_credits}")
        
        update_result = supabase.table("telegram_users").update({
            "credits": new_credits,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", telegram_user_id).execute()
        
        if update_result.data and len(update_result.data) > 0:
            updated_credits = update_result.data[0].get('credits', new_credits)
            print(f"Update successful. New credits: {updated_credits}")
            return updated_credits
        else:
            verify = supabase.table("telegram_users").select("credits").eq("telegram_user_id", telegram_user_id).execute()
            if verify.data and len(verify.data) > 0:
                verified_credits = verify.data[0].get('credits', 0)
                print(f"Verified credits after update: {verified_credits}")
                return verified_credits
            else:
                print(f"Update failed - user {telegram_user_id} not found")
                return None
                
    except Exception as e:
        print(f"Update user credits error: {e}")
        import traceback
        traceback.print_exc()
        return None

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

def deduct_credit(telegram_user_id):
    # Backward compatibility for any old code path.
    return deduct_credits(telegram_user_id, 1)

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
        # Compatible with updated SQL: protected_numbers has phone_number + optional owner_id.
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
    """Save lookup result to cache without requiring optional columns."""
    try:
        existing = supabase.table("search_results").select("mobile_number").eq("mobile_number", phone_number).limit(1).execute()
        if existing.data and len(existing.data) > 0:
            # Do not use updated_at here because the current table may not have that column.
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


# ==================== TELEGRAM / VEHICLE SUPABASE HELPERS ====================
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
        # New SQL protection tables use only the protected value + created_at for bot-side protection.
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

def is_vehicle_protected(vehicle_number):
    return is_value_protected("protected_vehicles", "vehicle_number", normalize_vehicle_number(vehicle_number))

def add_protected_telegram(telegram_id, telegram_user_id=None):
    return add_protected_value("protected_telegrams", "telegram_id", str(telegram_id))

def add_protected_vehicle(vehicle_number, telegram_user_id=None):
    return add_protected_value("protected_vehicles", "vehicle_number", normalize_vehicle_number(vehicle_number))

def get_cached_generic(table_name, column_name, value):
    try:
        response = supabase.table(table_name).select("raw_data").eq(column_name, value).limit(1).execute()
        if response.data:
            return response.data[0].get("raw_data")
    except Exception as e:
        print(f"Get cache error {table_name}: {e}")
    return None

def save_cached_generic(table_name, column_name, value, raw_data):
    try:
        existing = supabase.table(table_name).select(column_name).eq(column_name, value).limit(1).execute()
        payload = {"raw_data": raw_data, "created_at": datetime.now(timezone.utc).isoformat()}
        if existing.data:
            supabase.table(table_name).update({"raw_data": raw_data}).eq(column_name, value).execute()
        else:
            payload[column_name] = value
            supabase.table(table_name).insert(payload).execute()
        return True
    except Exception as e:
        print(f"Save cache error {table_name}: {e}")
        return False

def normalize_vehicle_number(value):
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())

def is_valid_vehicle_number(value):
    return bool(re.match(r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}$', normalize_vehicle_number(value)))

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

# ==================== CASHFREE PAYMENT FUNCTIONS ====================
def verify_cashfree_signature(raw_body, signature):
    """Verify Cashfree webhook signature using webhook secret"""
    if not CASHFREE_WEBHOOK_SECRET:
        print("CASHFREE_WEBHOOK_SECRET not set")
        return False
    
    if not signature:
        print("No signature provided in webhook")
        return False
    
    try:
        expected_signature = hmac.new(
            CASHFREE_WEBHOOK_SECRET.encode('utf-8'),
            raw_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature.lower(), signature.lower())
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def get_cashfree_order_status(order_id):
    """Get order status from Cashfree API"""
    try:
        # Determine API URL based on environment
        env_upper = CASHFREE_ENV.upper()
        if env_upper in ["PROD", "PRODUCTION"]:
            api_base = "https://api.cashfree.com/pg"
        else:
            api_base = "https://sandbox.cashfree.com/pg"
        
        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{api_base}/orders/{order_id}", headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Cashfree status API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Get order status error: {e}")
        return None

def create_cashfree_order(plan_id, amount, telegram_user_id, telegram_username, payment_for=None, protected_number=None):
    """Create a real Cashfree order and return payment link"""
    try:
        # Validate Cashfree credentials
        if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
            print("ERROR: Cashfree credentials missing! CASHFREE_APP_ID and CASHFREE_SECRET_KEY must be set in environment variables.")
            return None, None
        
        if not RENDER_BASE_URL or RENDER_BASE_URL == "https://your-app.onrender.com":
            print("WARNING: RENDER_BASE_URL not set properly. Using placeholder.")
        
        # Determine API URL based on environment
        env_upper = CASHFREE_ENV.upper()
        if env_upper in ["PROD", "PRODUCTION"]:
            CASHFREE_API_BASE = "https://api.cashfree.com/pg"
            print(f"Using PRODUCTION Cashfree API: {CASHFREE_API_BASE}")
        else:
            CASHFREE_API_BASE = "https://sandbox.cashfree.com/pg"
            print(f"Using SANDBOX Cashfree API: {CASHFREE_API_BASE}")
        
        order_id = f"TX_{telegram_user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        print(f"Creating order: {order_id} for user {telegram_user_id}, amount: ₹{amount}, plan: {plan_id}")
        
        # Store pending payment in Supabase
        payment_data = {
            "payment_id": order_id,
            "cashfree_order_id": order_id,
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "plan_id": plan_id,
            "amount": amount,
            "status": "pending",
            "payment_for": payment_for,
            "protected_number": protected_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Add credits if applicable
        if plan_id == "c10":
            payment_data["credits"] = 10
        elif plan_id == "c50":
            payment_data["credits"] = 50
        elif plan_id == "c100":
            payment_data["credits"] = 100
        
        # Insert into Supabase
        supabase.table("payment_claims").insert(payment_data).execute()
        print(f"Payment claim stored in Supabase with ID: {order_id}")
        
        # Prepare customer details
        customer_name = telegram_username if telegram_username and telegram_username != "no_username" else f"User_{telegram_user_id}"
        customer_name = customer_name[:100]
        
        # Prepare payload for Cashfree
        payload = {
            "order_id": order_id,
            "order_amount": amount,
            "order_currency": "INR",
            "customer_details": {
                "customer_id": str(telegram_user_id),
                "customer_name": customer_name,
                "customer_phone": "9999999999",
                "customer_email": f"user_{telegram_user_id}@example.com"
            },
            "order_meta": {
                "return_url": f"{RENDER_BASE_URL}/payment/success?order_id={order_id}",
                "notify_url": f"{RENDER_BASE_URL}/cashfree/webhook"
            }
        }
        
        # Headers for Cashfree API
        headers = {
            "x-client-id": CASHFREE_APP_ID,
            "x-client-secret": CASHFREE_SECRET_KEY,
            "x-api-version": CASHFREE_API_VERSION,
            "Content-Type": "application/json"
        }
        
        # Make API call to Cashfree
        api_url = f"{CASHFREE_API_BASE}/orders"
        print(f"Calling Cashfree API: {api_url}")
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        # Log response details
        print(f"Cashfree Response Status Code: {response.status_code}")
        print(f"Cashfree Response Body (first 1000 chars): {response.text[:1000]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Cashfree order created successfully: {result.get('order_id')}")
            
            # Extract payment link from response
            payment_link = None
            
            if result.get("payment_link"):
                payment_link = result.get("payment_link")
                print(f"Found payment_link: {payment_link}")
            
            elif result.get("payments") and isinstance(result.get("payments"), dict):
                payment_link = result.get("payments", {}).get("url")
                if payment_link:
                    print(f"Found payments.url: {payment_link}")
            
            elif result.get("order_meta") and isinstance(result.get("order_meta"), dict):
                payment_methods = result.get("order_meta", {}).get("payment_methods")
                if isinstance(payment_methods, dict) and payment_methods.get("payment_url"):
                    payment_link = payment_methods.get("payment_url")
                    if payment_link:
                        print(f"Found payment_methods.payment_url: {payment_link}")
            
            elif result.get("payment_session_id"):
                payment_session_id = result.get("payment_session_id")
                # Use our Render-hosted checkout launcher. Direct session URLs are not reliable.
                payment_link = f"{RENDER_BASE_URL}/pay/{order_id}?session_id={payment_session_id}"
                print(f"Constructed Render checkout URL from payment_session_id: {payment_link}")
                # Save session_id if the column exists; ignore if it does not.
                try:
                    supabase.table("payment_claims").update({"session_id": payment_session_id}).eq("cashfree_order_id", order_id).execute()
                except Exception as e:
                    print(f"Could not save session_id (optional column may be missing): {e}")
            
            elif result.get("order_meta") and result.get("order_meta", {}).get("payment_url"):
                payment_link = result.get("order_meta", {}).get("payment_url")
                print(f"Found order_meta.payment_url: {payment_link}")
            
            if payment_link:
                print(f"✅ Payment link created successfully: {payment_link}")
                return order_id, payment_link
            else:
                print(f"❌ No payment link found in response. Full response: {json.dumps(result, indent=2)}")
                return None, None
                
        elif response.status_code == 401:
            print("❌ Cashfree authentication failed. Check CASHFREE_APP_ID and CASHFREE_SECRET_KEY.")
            print("Make sure you're using correct credentials for the environment:", CASHFREE_ENV)
            return None, None
        elif response.status_code == 422:
            print(f"❌ Cashfree validation error: {response.text}")
            return None, None
        else:
            print(f"❌ Cashfree API error {response.status_code}: {response.text}")
            return None, None
            
    except requests.exceptions.Timeout:
        print("❌ Cashfree API timeout after 30 seconds")
        return None, None
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Cashfree API. Check internet connection.")
        return None, None
    except Exception as e:
        print(f"❌ Create order error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def process_payment_success(order_id, cashfree_payment_id, raw_response):
    """Process successful payment with idempotency check"""
    try:
        # Get payment claim - check if already processed
        response = supabase.table("payment_claims").select("*").eq("cashfree_order_id", order_id).execute()
        
        if not response.data:
            print(f"Payment claim not found for order: {order_id}")
            return False
        
        claim = response.data[0]
        
        # Idempotency check - if already success, return
        if claim.get('status') == "success":
            print(f"Payment {order_id} already processed")
            return True
        
        telegram_user_id = claim['telegram_user_id']
        plan_id = claim['plan_id']
        payment_for = claim.get('payment_for')
        
        # Update payment claim
        supabase.table("payment_claims").update({
            "status": "success",
            "cashfree_payment_id": cashfree_payment_id,
            "raw_response": raw_response,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("cashfree_order_id", order_id).execute()
        
        # Process based on plan
        if plan_id in ["c10", "c50", "c100"]:
            credits_to_add = claim.get('credits', 0)
            if credits_to_add > 0:
                add_credits(telegram_user_id, credits_to_add)
                bot.send_message(telegram_user_id, f"""
✅ *PAYMENT SUCCESSFUL!*

💎 `{credits_to_add}` credits added to your account!

📊 *Total Credits:* `{get_total_credits(telegram_user_id)}`

Use /start to continue!
""", parse_mode='Markdown')
        
        elif plan_id in ["u1h", "u1d", "u1w", "u1m"]:
            durations = {"u1h": 1/24, "u1d": 1, "u1w": 7, "u1m": 30}
            days = durations.get(plan_id, 0)
            
            user = get_user(telegram_user_id)
            current_expiry = user.get('unlimited_expiry')
            
            if current_expiry:
                if isinstance(current_expiry, str):
                    expiry_date = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
                else:
                    expiry_date = current_expiry
                if expiry_date > datetime.now(timezone.utc):
                    new_expiry = expiry_date + timedelta(days=days)
                else:
                    new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
            else:
                new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
            
            supabase.table("telegram_users").update({
                "unlimited_expiry": new_expiry.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            
            duration_text = {"u1h": "1 Hour", "u1d": "1 Day", "u1w": "7 Days", "u1m": "30 Days"}.get(plan_id, "Limited")
            
            bot.send_message(telegram_user_id, f"""
✅ *PAYMENT SUCCESSFUL!*

🚀 *Unlimited Plan Activated!*
📅 Duration: `{duration_text}`
⏰ Expires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')}`

Use /start to continue!
""", parse_mode='Markdown')
        
        elif plan_id == "protect49" and payment_for == "protect_number":
            protected_number = claim.get('protected_number')
            if protected_number:
                add_protected_number(protected_number, telegram_user_id)
                bot.send_message(telegram_user_id, f"""
✅ *PAYMENT SUCCESSFUL!*

🛡️ *Number Protected!*
📱 Number: `{protected_number}`

Your number is now protected. No one can lookup details for this number!

Use /start to continue!
""", parse_mode='Markdown')
        
        # Send admin log
        bot.send_message(ADMIN_ID, f"""
✅ *PAYMENT SUCCESS*

👤 User: `{telegram_user_id}`
💎 Plan: `{plan_id}`
💰 Amount: ₹{claim['amount']}
🆔 Order: `{order_id}`

Status: COMPLETED
""", parse_mode='Markdown')
        
        return True
    except Exception as e:
        print(f"Process payment success error: {e}")
        return False


# ==================== MANUAL STATIC QR PAYMENT FUNCTIONS ====================
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

        if plan["payment_for"] == "protect_vehicle":
            vehicle_number = normalize_vehicle_number(claim.get("protected_number"))
            if not vehicle_number:
                return False, "Vehicle number missing"
            if not is_vehicle_protected(vehicle_number):
                add_protected_vehicle(vehicle_number, int(telegram_user_id))
            return True, f"Protected vehicle number {vehicle_number}"

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

def send_manual_qr_payment(chat_id, user_id, username, plan_id, protected_number=None):
    """Send static QR image + fixed amount details. Admin verifies manually."""
    plan = get_plan_config(plan_id)
    if not plan:
        bot.send_message(chat_id, "❌ Invalid plan selected.", reply_markup=main_menu_markup(user_id))
        return

    now_ts = time.time()
    last_ts = payment_session_cooldown.get(user_id, 0)
    remaining = int(PAYMENT_SESSION_COOLDOWN_SECONDS - (now_ts - last_ts))
    if remaining > 0:
        bot.send_message(chat_id, f"⏳ *QR already generated recently!*\n\nPlease wait `{remaining}` seconds before creating another payment session.", reply_markup=main_menu_markup(user_id), parse_mode="Markdown")
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
    admin_markup.add(InlineKeyboardButton("✅ VERIFY PAYMENT", callback_data=f"adminverify_{tx_code}"), InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}"))
    send_admin_alert(
        f"💳 *MANUAL QR PAYMENT CREATED*\n━━━━━━━━━━━━━━━━\n👤 User: `{user_id}`\n@ Username: @{username}\n📦 Plan: `{plan_id}`\n💰 Amount: ₹{plan['amount']}\n🧾 TX: `{tx_code}`\n\nVerify after checking screenshot/payment:\n`/verify {tx_code}`",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )




# ==================== DAILY SEARCH REPORT ====================
def record_search_for_daily_report(user_id, username, first_name, query_value, found=True, lookup_type="number", credits_used=0):
    """Store only aggregate lookup stats for the 6 AM report. No instant search log spam."""
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
                "credits_used": 0,
                "found": 0,
                "not_found": 0,
                "last_query": ""
            })
            row["searches"] += 1
            row["last_query"] = query_value
            row["credits_used"] += int(credits_used or 0)
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
    credits_used = sum(v.get("credits_used", 0) for v in stats_snapshot.values())
    top = sorted(stats_snapshot.values(), key=lambda x: x.get("searches", 0), reverse=True)[:10]

    lines = [
        "📊 *TRACEX 24H SEARCH REPORT*",
        "━━━━━━━━━━━━━━━━",
        f"🕕 Report Time: `{datetime.now(IST).strftime('%Y-%m-%d 06:00 IST')}`",
        f"👥 Users Searched: `{total_users}`",
        f"🔍 Total Lookups: `{total_searches}`",
        f"📱 Number Lookups: `{number_searches}`",
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
            lines.append(f"{i}. {display} | ID `{row.get('user_id')}` | `{row.get('searches', 0)}` lookups | 📱 `{row.get('number_searches', 0)}` | 💎 `{row.get('credits_used', 0)}`")
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

# ==================== RESULT FORMATTING ====================
def format_lookup_result(result, phone, user_id, unlimited_active=False, unlimited_expiry=None):
    """Format API/cache result. Supports API format with results -> Result 1..20 and old cache direct Result keys."""
    if not isinstance(result, dict):
        result = {}

    parsed_results = []

    api_results = result.get('results')
    if isinstance(api_results, dict):
        # Sort Result 1, Result 2... naturally, supports up to 16+ results.
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

    # Some existing Supabase rows may store direct keys: {"Result 1": {...}, "Result 2": {...}}
    if not parsed_results:
        direct_result_items = [(k, v) for k, v in result.items() if str(k).lower().startswith('result') and isinstance(v, dict)]
        def sort_key2(item):
            m = re.search(r'\d+', str(item[0]))
            return int(m.group()) if m else 9999
        for key, value in sorted(direct_result_items, key=sort_key2):
            parsed_results.append(value)

    # Some APIs return one direct object.
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
    
    first_name = "Unknown"
    
    for idx, data in enumerate(parsed_results, 1):
        name = data.get('name') or data.get('Name') or data.get('full_name') or 'N/A'
        if idx == 1 and name != 'N/A':
            first_name = name
            
        alt_mobile = data.get('alt_mobile') or data.get('alternate_mobile') or data.get('Alt_Mobile') or 'N/A'
        if alt_mobile == 'NA' or alt_mobile == 'n/a':
            alt_mobile = 'N/A'
        
        father_name = data.get('father_name') or data.get('Father_Name') or data.get('father') or 'N/A'
        email = data.get('email') or data.get('Email') or 'N/A'
        if email == 'n/a':
            email = 'N/A'
            
        aadhar = data.get('aadhar_number') or data.get('aadhar') or data.get('Aadhar') or 'N/A'
        if aadhar == 'n/a':
            aadhar = 'N/A'
            
        operator = data.get('operator') or data.get('Operator') or data.get('carrier') or 'N/A'
        circle = data.get('state_circle') or data.get('circle') or data.get('Circle') or data.get('state') or 'N/A'
        address = data.get('address') or data.get('Address') or data.get('full_address') or 'N/A'
        if address == 'NA':
            address = 'N/A'
        
        mobile = data.get('mobile') or data.get('Mobile') or data.get('phone') or phone
        
        output += f"""

━━━━━━━━━━━━━━━━━━
📄 *RESULT {idx}*

📱 Mobile: `{mobile}`
📞 Alternate: `{alt_mobile}`
👤 Name: `{name}`
👨 Father: `{father_name}`
📧 Email: `{email}`
🪪 Aadhaar: `{aadhar}`
📡 Operator: `{operator}`
📍 Circle: `{circle}`
🏠 Address: `{address}`"""
    
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
    
    return output, first_name


# ==================== LOOKUP PROCESS ====================
def process_lookup(message):
    user_id = message.from_user.id
    raw_phone = str(message.text or "").strip()
    phone = normalize_indian_mobile(raw_phone)
    
    if user_id in user_states:
        del user_states[user_id]
    
    if raw_phone == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    if not phone:
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter Indian mobile number.\nExamples: `9876543210` or `+919876543210`", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    with active_number_sessions_lock:
        if user_id in active_number_sessions:
            bot.reply_to(message, "⏳ *One number search already running!*\n\nPlease wait for current search result before starting another.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        active_number_sessions.add(user_id)
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            active_number_sessions.discard(user_id)
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
        markup = universal_markup(buy=True, join=True, admin=True)
        bot.reply_to(message, f"❌ *Not enough credits!* Number Lookup costs `{NUMBER_LOOKUP_COST}` credits. Buy more credits or get an unlimited plan.", reply_markup=markup, parse_mode='Markdown')
        active_number_sessions.discard(user_id)
        return
    
    if is_number_protected(phone):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECT MY NUMBER", callback_data="protect"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.reply_to(message, f"""
🛡️ *PROTECTED NUMBER*

📱 `{phone}`

This number is protected by the Number Protection Plan.

The owner has purchased privacy protection. Details are hidden.

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
    
    if cached_result:
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_number_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        
        output, first_name = format_lookup_result(cached_result, phone, user_id, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        
        threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
        active_number_sessions.discard(user_id)
        return
    
    try:
        url = f"{LOOKUP_API_URL}?key={LOOKUP_API_KEY}&service={LOOKUP_API_SERVICE}&number={phone}"
        r = requests.get(url, timeout=10)
        result = safe_json_response(r)
    except Exception as e:
        print(f"Number lookup API error: {e}")
        show_api_error(message.chat.id, loading_msg.message_id, lookup_type="number")
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=False, lookup_type="number", credits_used=0)
        active_number_sessions.discard(user_id)
        return

    if result and result.get('results'):
        if not unlimited_active:
            if not deduct_credits(user_id, NUMBER_LOOKUP_COST):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                active_number_sessions.discard(user_id)
                return
        
        increment_total_searches(user_id)
        save_cached_result(phone, result)
        output, first_name = format_lookup_result(result, phone, user_id, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
        
        sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
        
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=True, lookup_type="number", credits_used=NUMBER_LOOKUP_COST if not unlimited_active else 0)
        
        threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()
        active_number_sessions.discard(user_id)
        
    else:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number
`{phone}`

🚫 No records available in database

💡 Tips:
• Check number again
• Try another number
• Ensure Indian mobile number

━━━━━━━━━━━━━━━━━━
💎 Credits NOT deducted
{footer()}
"""
        
        bot.edit_message_text(output, message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, phone, found=False, lookup_type="number", credits_used=0)
        active_number_sessions.discard(user_id)


def format_telegram_lookup_result(result, telegram_id, user_id, unlimited_active=False, unlimited_expiry=None):
    data = result.get("Data") if isinstance(result, dict) else {}
    contacts = data.get("Contact") if isinstance(data, dict) else []
    if isinstance(contacts, str):
        contacts = [contacts]
    contacts = [str(x) for x in contacts if str(x).strip()]
    total = len(contacts)
    output = f"""
💬 *TELEGRAM NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

🆔 Telegram User ID: `{telegram_id}`
📊 Total Numbers Found: `{total}`
"""
    for idx, mobile in enumerate(contacts, 1):
        output += f"""
━━━━━━━━━━━━━━━━━━
📄 *RESULT {idx}*

📱 Mobile Number: `{mobile}`"""
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    if unlimited_active:
        output += f"""
━━━━━━━━━━━━━━━━━━
🚀 *UNLIMITED PLAN ACTIVE*
No credits deducted!
Expires: `{str(unlimited_expiry)[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""
━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{TELEGRAM_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{user.get('total_searches', 0) if user else 0}`"""
    output += f"""

⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec
{footer()}
"""
    return output

def format_vehicle_lookup_result(result, vehicle_number, user_id, unlimited_active=False, unlimited_expiry=None):
    data = result.get("data") if isinstance(result, dict) else {}
    mobile = data.get("mobile") if isinstance(data, dict) else None
    vehicle = data.get("vehicle") if isinstance(data, dict) else vehicle_number
    output = f"""
🚘 *VEHICLE NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

🚘 Vehicle Number: `{vehicle}`
📱 Owner Mobile: `{mobile or 'N/A'}`
"""
    user = get_user(user_id)
    updated_total = get_total_credits(user_id)
    if unlimited_active:
        output += f"""
━━━━━━━━━━━━━━━━━━
🚀 *UNLIMITED PLAN ACTIVE*
No credits deducted!
Expires: `{str(unlimited_expiry)[:16] if unlimited_expiry else 'N/A'}`
"""
    else:
        output += f"""
━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `{VEHICLE_LOOKUP_COST}`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{user.get('total_searches', 0) if user else 0}`"""
    output += f"""

⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec
{footer()}
"""
    return output

def process_telegram_lookup(message):
    process_extra_lookup(message, "telegram")

def process_vehicle_lookup(message):
    process_extra_lookup(message, "vehicle")

def process_extra_lookup(message, lookup_type):
    user_id = message.from_user.id
    query = str(message.text or "").strip()
    user_states.pop(user_id, None)

    if query == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    if lookup_type == "telegram":
        if not is_valid_telegram_id(query):
            bot.reply_to(message, "❌ *Invalid Telegram ID!*\n\nEnter numeric Telegram user ID.\nExample: `7850023357`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        cost = TELEGRAM_LOOKUP_COST
        protected = is_telegram_protected(query)
        protected_title = "Telegram Number Protection Plan"
        cache_table, cache_col = "telegram_search_results", "telegram_id"
    else:
        query = normalize_vehicle_number(query)
        if not is_valid_vehicle_number(query):
            bot.reply_to(message, "❌ *Invalid vehicle number!*\n\nEnter valid RC number.\nExample: `HR60E3838`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        cost = VEHICLE_LOOKUP_COST
        protected = is_vehicle_protected(query)
        protected_title = "Vehicle Number Protection Plan"
        cache_table, cache_col = "vehicle_search_results", "vehicle_number"

    if user_id in user_cooldown and time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
        wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
        bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return

    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    unlimited_active, unlimited_expiry = get_active_unlimited(user)
    if total_credits < cost and not unlimited_active:
        bot.reply_to(message, f"❌ *Not enough credits!* This lookup costs `{cost}` credits. Buy more credits or get an unlimited plan.", reply_markup=universal_markup(buy=True, join=True, admin=True), parse_mode='Markdown')
        return

    if protected:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛡️ PROTECTION", callback_data="protection_menu"))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        bot.reply_to(message, f"""
🛡️ *PROTECTED DATA*

🔎 Query: `{query}`

This data is protected by the {protected_title}.
Details are hidden.

You can also protect yours for ₹99.
""", reply_markup=markup, parse_mode='Markdown')
        return

    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching...*", parse_mode='Markdown')

    cached_result = get_cached_generic(cache_table, cache_col, query)
    if cached_result:
        found = True
        result = cached_result
    else:
        try:
            if lookup_type == "telegram":
                url = f"{LOOKUP_API_URL}?key={TELEGRAM_LOOKUP_API_KEY}&service={TELEGRAM_LOOKUP_SERVICE}&telegram={query}"
            else:
                url = f"{LOOKUP_API_URL}?key={VEHICLE_LOOKUP_API_KEY}&service={VEHICLE_LOOKUP_SERVICE}&rc={query}"
            r = requests.get(url, timeout=15)
            result = safe_json_response(r)
        except Exception as e:
            print(f"{lookup_type} lookup API error: {e}")
            show_api_error(message.chat.id, loading_msg.message_id, lookup_type=lookup_type)
            record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query, found=False, lookup_type=lookup_type, credits_used=0)
            return
        if lookup_type == "telegram":
            data = result.get("Data") if isinstance(result, dict) else {}
            contacts = data.get("Contact") if isinstance(data, dict) else []
            found = bool(result.get("Status") is True and contacts)
        else:
            data = result.get("data") if isinstance(result, dict) else {}
            found = bool(isinstance(data, dict) and data.get("success") is True and data.get("mobile"))
        if found:
            save_cached_generic(cache_table, cache_col, query, result)

    if not found:
        text = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

🔎 Query: `{query}`

🚫 No records available in database

💎 Credits NOT deducted
{footer()}
"""
        bot.edit_message_text(text, message.chat.id, loading_msg.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query, found=False, lookup_type=lookup_type, credits_used=0)
        return

    if not unlimited_active and not deduct_credits(user_id, cost):
        bot.edit_message_text("❌ *Failed to deduct credits. Please try again.*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        return

    increment_total_searches(user_id)
    if lookup_type == "telegram":
        output = format_telegram_lookup_result(result, query, user_id, unlimited_active, unlimited_expiry)
        new_cb = "telegram_lookup"
    else:
        output = format_vehicle_lookup_result(result, query, user_id, unlimited_active, unlimited_expiry)
        new_cb = "vehicle_lookup"

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔍 NEW SEARCH", callback_data=new_cb), InlineKeyboardButton("🏠 MENU", callback_data="main_menu"))
    markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
    sent_messages = send_or_edit_long_message(message.chat.id, loading_msg.message_id, output, reply_markup=markup, parse_mode='Markdown')
    record_search_for_daily_report(user_id, message.from_user.username, message.from_user.first_name, query, found=True, lookup_type=lookup_type, credits_used=cost if not unlimited_active else 0)
    threading.Thread(target=auto_delete_sent_messages, args=(message.chat.id, sent_messages), daemon=True).start()

def show_protection_menu(message):
    text = f"""
🛡️ *PROTECTION SERVICES*
━━━━━━━━━━━━━━━━━━

📱 Number Protection → ₹99
💬 Telegram Number Protection → ₹99
🚘 Vehicle Number Protection → ₹99

Protected data will not be shown in lookup results.
"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📱 PROTECT NUMBER - ₹99", callback_data="plan_protect_number"))
    markup.add(InlineKeyboardButton("💬 PROTECT TELEGRAM - ₹99", callback_data="plan_protect_telegram"))
    markup.add(InlineKeyboardButton("🚘 PROTECT VEHICLE - ₹99", callback_data="plan_protect_vehicle"))
    markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def process_protection_payment_input(message, plan_id):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    value = str(message.text or "").strip()
    if plan_id == "protect_number":
        if not re.match(r'^[6-9]\d{9}$', value):
            bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        if is_number_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    elif plan_id == "protect_telegram":
        if not is_valid_telegram_id(value):
            bot.reply_to(message, "❌ *Invalid Telegram ID!*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        if is_telegram_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    elif plan_id == "protect_vehicle":
        value = normalize_vehicle_number(value)
        if not is_valid_vehicle_number(value):
            bot.reply_to(message, "❌ *Invalid vehicle number!*\nExample: `HR60E3838`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
        if is_vehicle_protected(value):
            bot.reply_to(message, f"❌ Already protected: `{value}`", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            return
    else:
        bot.reply_to(message, "❌ Invalid protection plan.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    send_manual_qr_payment(message.chat.id, user_id, message.from_user.username or "no_username", plan_id, protected_number=value)

# ==================== FLASK WEBHOOK ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "TraceX Bot Running"

@app.route('/cashfree/webhook', methods=['POST'])
def cashfree_webhook():
    """Handle Cashfree payment webhook.
    Security flow: signature check if possible + final verification from Cashfree Order Status API.
    This avoids false 401 issues while still preventing fake credit addition.
    """
    try:
        signature = (
            request.headers.get('x-webhook-signature') or
            request.headers.get('X-Cashfree-Signature') or
            request.headers.get('x-cashfree-signature') or
            request.headers.get('X-Webhook-Signature') or
            ''
        )
        raw_body = request.get_data(as_text=True)
        data = request.get_json(silent=True) or {}

        print(f"Webhook received headers signature-present={bool(signature)}")
        print(f"Webhook body preview: {raw_body[:1000]}")

        # Extract order_id from common Cashfree webhook formats.
        order_id = None
        payment_id = None
        if isinstance(data, dict):
            order_id = data.get('order_id')
            payment_id = data.get('payment_id')

            if not order_id and isinstance(data.get('order'), dict):
                order_id = data['order'].get('order_id')
            if not payment_id and isinstance(data.get('payment'), dict):
                payment_id = data['payment'].get('cf_payment_id') or data['payment'].get('payment_id')

            nested = data.get('data')
            if isinstance(nested, dict):
                if not order_id:
                    order_id = nested.get('order_id')
                if not payment_id:
                    payment_id = nested.get('payment_id')
                if isinstance(nested.get('order'), dict) and not order_id:
                    order_id = nested['order'].get('order_id')
                if isinstance(nested.get('payment'), dict) and not payment_id:
                    payment_id = nested['payment'].get('cf_payment_id') or nested['payment'].get('payment_id')

        if not order_id:
            print("Could not extract order_id from webhook data")
            return jsonify({"error": "No order_id found"}), 400

        # Signature verification is attempted, but final trust is based on Cashfree Order Status API.
        if CASHFREE_WEBHOOK_SECRET:
            if verify_cashfree_signature(raw_body, signature):
                print("✅ Cashfree webhook signature verified")
            else:
                print("⚠️ Cashfree webhook signature mismatch. Continuing with Order Status API verification.")
        else:
            print("⚠️ CASHFREE_WEBHOOK_SECRET not set. Using Order Status API verification only.")

        # Idempotency early check.
        try:
            claim_check = supabase.table("payment_claims").select("status").eq("cashfree_order_id", order_id).limit(1).execute()
            if claim_check.data and claim_check.data[0].get("status") == "success":
                print(f"Payment {order_id} already success, ignoring duplicate webhook")
                return jsonify({"status": "already_processed"}), 200
        except Exception as e:
            print(f"Payment claim precheck error: {e}")

        # Final verification from Cashfree API.
        order_data = get_cashfree_order_status(order_id)
        if not order_data:
            print(f"Could not verify order {order_id} status via Cashfree API")
            return jsonify({"error": "Verification failed"}), 400

        order_status = str(order_data.get('order_status', '')).upper()
        print(f"Cashfree verified order status for {order_id}: {order_status}")

        if order_status in ['PAID', 'SUCCESS', 'COMPLETED']:
            process_payment_success(order_id, payment_id or order_data.get('payment_id') or order_data.get('cf_payment_id'), order_data)
        else:
            print(f"Order {order_id} status is {order_status}, not processing")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/pay/<order_id>', methods=['GET'])
def cashfree_pay_page(order_id):
    """Hosted checkout launcher for Cashfree payment_session_id."""
    payment_session_id = request.args.get('session_id', '')
    mode = 'production' if CASHFREE_ENV.upper() in ['PROD', 'PRODUCTION'] else 'sandbox'
    if not payment_session_id:
        return "Payment session missing. Please return to Telegram and try again.", 400
    return f"""
    <html>
        <head>
            <title>TraceX Payment</title>
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
            <script src=\"https://sdk.cashfree.com/js/v3/cashfree.js\"></script>
        </head>
        <body style=\"font-family: Arial, sans-serif; text-align:center; padding:30px; background:#0b0f17; color:white;\">
            <h2>Redirecting to secure payment...</h2>
            <p>Please wait.</p>
            <script>
                const cashfree = Cashfree({{ mode: \"{mode}\" }});
                cashfree.checkout({{
                    paymentSessionId: \"{payment_session_id}\",
                    redirectTarget: \"_self\"
                }});
            </script>
        </body>
    </html>
    """

@app.route('/payment/success', methods=['GET'])
def payment_success():
    """Payment success redirect page"""
    order_id = request.args.get('order_id', '')
    
    order_data = get_cashfree_order_status(order_id)
    
    if order_data and order_data.get('order_status') in ['PAID', 'SUCCESS', 'COMPLETED']:
        return """
        <html>
            <head><title>Payment Successful - TraceX</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: green;">✅ Payment Successful!</h1>
                <p>Your order has been processed successfully.</p>
                <p>You will receive a confirmation in Telegram shortly.</p>
                <p>You can now close this window and return to Telegram.</p>
                <script>
                    setTimeout(function() {
                        window.close();
                    }, 5000);
                </script>
            </body>
        </html>
        """
    else:
        return """
        <html>
            <head><title>Payment Processing - TraceX</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: orange;">⏳ Payment Processing</h1>
                <p>Your payment is being processed.</p>
                <p>You will receive a confirmation in Telegram shortly.</p>
                <p>You can close this window and wait for Telegram notification.</p>
            </body>
        </html>
        """

def keep_alive():
    """Run Flask app in a separate thread"""
    def run():
        app.run(host='0.0.0.0', port=8080)
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ==================== PAYMENT HANDLERS ====================
def show_credit_packs(message, user_id):
    packs_msg = f"""
💎 *PREMIUM CREDIT STORE*
━━━━━━━━━━━━━━━━━━

💰 *CREDIT PACKS*
• 10 Credits → ₹20
• 50 Credits → ₹70  
• 100 Credits → ₹100

🚀 *UNLIMITED PLANS*
• 1 Hour Unlimited → ₹34
• 1 Day Unlimited → ₹88
• 7 Days Unlimited → ₹358
• 30 Days Unlimited → ₹898

🛡️ *PROTECTION*
• Number Protection → ₹99
• Telegram Number Protection → ₹99
• Vehicle Number Protection → ₹99

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

    if plan_id in ["protect_number", "protect_telegram", "protect_vehicle"]:
        labels = {
            "protect_number": ("📱 *NUMBER PROTECTION*", "Enter the 10-digit mobile number you want to protect:", "`Example: 9876543210`"),
            "protect_telegram": ("💬 *TELEGRAM NUMBER PROTECTION*", "Enter numeric Telegram user ID:", "`Example: 7850023357`"),
            "protect_vehicle": ("🚘 *VEHICLE NUMBER PROTECTION*", "Enter vehicle RC number:", "`Example: HR60E3838`")
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

def process_protect_number(message, plan_id="protect_number", amount=None):
    """Legacy compatibility wrapper. Number protection is now ₹99 manual QR, not credits."""
    return process_protection_payment_input(message, "protect_number")



def show_bot_booking(message):
    booking_msg = f"""
🤖 *CUSTOM BOT BOOKING*
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
🎯 *FEATURES*
• Instant Number Lookup
• Fast Response
• Secure Credits System
• Unlimited Plans Available
• Number Protection Service

━━━━━━━━━━━━━━━━
🎁 New users get 3 free credits!

👇 Choose an option below
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


@bot.message_handler(content_types=['photo', 'document'])
def payment_screenshot_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_payment_screenshot"):
        return

    tx_code = state.get("tx_code")
    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, f"✅ Screenshot already sent to admin for TX `{tx_code}`.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
        return
    proof_forwarded_txs.add(tx_code)
    caption = f"📸 *PAYMENT SCREENSHOT RECEIVED*\n━━━━━━━━━━━━━━━━\n👤 User: `{user_id}`\n@ Username: @{message.from_user.username or 'no_username'}\n🧾 TX: `{tx_code}`\n\nVerify only after checking payment:\n`/verify {tx_code}`"
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(InlineKeyboardButton("✅ VERIFY PAYMENT", callback_data=f"adminverify_{tx_code}"), InlineKeyboardButton("❌ REJECT", callback_data=f"adminreject_{tx_code}"))

    try:
        try:
            bot.copy_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        except Exception as forward_error:
            print(f"Admin group screenshot copy failed: {forward_error}")
            try:
                bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
            except Exception as dm_forward_error:
                print(f"Admin DM screenshot copy failed: {dm_forward_error}")
        send_admin_alert(caption, reply_markup=admin_markup, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Screenshot sent to admin.\n\n🧾 TX: `{tx_code}`\n⏳ Wait for manual verification.", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        print(f"Payment screenshot forward error: {e}")
        bot.reply_to(message, f"❌ Could not forward screenshot. Contact {ADMIN_USERNAME}", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')

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
            bot.edit_message_text("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        except Exception:
            try:
                bot.edit_message_caption("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
            except Exception:
                bot.send_message(call.message.chat.id, "🏠 *MAIN MENU*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "cancel":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in temp_data:
            del temp_data[user_id]
        bot.edit_message_text("❌ Cancelled. Use /start for main menu.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "lookup":
        user_states[user_id] = "awaiting_number"
        msg = bot.send_message(call.message.chat.id, "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\n💎 Cost: `10 credits` per successful search\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)
    elif call.data == "telegram_lookup":
        user_states[user_id] = "awaiting_telegram_id"
        msg = bot.send_message(call.message.chat.id, "💬 *Enter Telegram User ID:*\n\n`Example: 7850023357`\n\n💎 Cost: `10 credits` per successful search\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_telegram_lookup)
        bot.answer_callback_query(call.id)
    elif call.data == "vehicle_lookup":
        user_states[user_id] = "awaiting_vehicle_number"
        msg = bot.send_message(call.message.chat.id, "🚘 *Enter Vehicle Number:*\n\n`Example: HR60E3838`\n\n💎 Cost: `10 credits` per successful search\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_vehicle_lookup)
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
*💎 MY CREDITS*
━━━━━━━━━━━━━━━━━━
💰 *Credits:* `{total_credits}`{unlimited_text}
🔎 *Used:* `{user.get('total_searches', 0) if user else 0}`
━━━━━━━━━━━━━━━━━━
*📦 CREDIT PACKS*
• 10 Credits → ₹20
• 50 Credits → ₹70  
• 100 Credits → ₹100
*🚀 UNLIMITED PLANS*
• 1 Hour → ₹34
• 1 Day → ₹88
• 7 Days → ₹358
• 30 Days → ₹898
*🛡️ PROTECTION*
• Number Protection → ₹99
• Telegram Number Protection → ₹99
• Vehicle Number Protection → ₹99
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
👤 *USER PROFILE*
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
        markup = universal_markup(back=True, join=True, admin=(user_id == ADMIN_ID))
        bot.edit_message_text(profile_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "help":
        help_msg = f"""
📖 *HOW TO USE TRACEX*
━━━━━━━━━━━━━━━━━━
1️⃣ Click NUMBER LOOKUP
2️⃣ Enter mobile number
3️⃣ Get instant results
━━━━━━━━━━━━━━━━━━
💎 *CREDIT SYSTEM*
• New User: `3` free credits
• Credits never expire
• Number Lookup: 10 credits
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
✅ Unlimited Plans
✅ Number Protection
✅ Secure Payments
{footer()}
"""
        markup = universal_markup(back=True, join=True, admin=(user_id == ADMIN_ID))
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
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS / UNLIMITED*\n\nCredits format:\n`user_id credits`\nExample: `123456789 50`\n\nUnlimited format:\n`user_id u1h` / `user_id u1d` / `user_id u1w` / `user_id u1m`\nExample: `123456789 u1d`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE CREDITS / DEACTIVATE UNLIMITED*\n\nRemove credits:\n`user_id_or_username credits`\n`@username credits`\nExample: `@gaurav 10`\n\nDeactivate unlimited:\n`user_id_or_username unlimited`\n`@username off`\nExample: `@gaurav unlimited`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
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
        bot.answer_callback_query(call.id)

# ==================== ADMIN FUNCTIONS ====================
def show_admin_panel(message):
    stats = get_stats()
    admin_msg = f"""
*🛠 ADMIN PANEL*
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
*📊 DETAILED STATS*
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
        trans_msg = "*📋 RECENT TRANSACTIONS*\n\n"
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
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
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
                bot.send_message(target_user, f"🚀 *Unlimited Plan Added!*\nPlan: `{label}`\nExpires: `{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n{footer()}", parse_mode='Markdown', disable_web_page_preview=True)
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
    if user_id in user_states:
        del user_states[user_id]
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

def process_admin_deactivate_unlimited(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    user_states.pop(user_id, None)
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        target_user = int(message.text.strip().split()[0])
        supabase.table("telegram_users").update({
            "unlimited_expiry": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_user_id", target_user).execute()
        bot.reply_to(message, f"✅ Unlimited plan deactivated for `{target_user}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, "🧨 *Unlimited Plan Deactivated*\n\nYour unlimited access has been removed by admin.", parse_mode='Markdown')
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Invalid format! Use: `user_id`", parse_mode='Markdown')

def process_admin_broadcast(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    broadcast_text = message.text.strip()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ YES, SEND", callback_data="broadcast_confirm"), InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel"))
    temp_data[user_id] = {'broadcast_text': broadcast_text}
    bot.reply_to(message, f"📢 *Confirm Broadcast*\n\n📝 Message:\n`{broadcast_text}`\n\nSend to all active users?", reply_markup=markup, parse_mode='Markdown')

def process_admin_giveaway(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        credits = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ YES, GIVE AWAY", callback_data="giveaway_confirm"), InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel"))
        temp_data[user_id] = {'giveaway_credits': credits}
        bot.reply_to(message, f"🎁 *Confirm Giveaway*\n\nGive `{credits}` credits to ALL active users?\n\nThis will be sent to all users immediately!", reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number! Enter a valid credit amount.", parse_mode='Markdown')

def confirm_broadcast(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Broadcast cancelled. No data found.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
        return
    broadcast_text = temp_data[user_id]['broadcast_text']
    users = get_all_users()
    success = 0
    failed = 0
    bot.edit_message_text(f"📡 *Broadcasting to {len(users)} users...*\n\nPlease wait...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    for target_user_id in users:
        try:
            broadcast_msg = f"""
*📢 TRACEX BROADCAST*
{broadcast_text}
━━━━━━━━━━━━━━━━
📞 *Support:* {ADMIN_USERNAME}
👥 *Group:* [Join Community]({GROUP_LINK})
"""
            bot.send_message(target_user_id, broadcast_msg, parse_mode='Markdown', disable_web_page_preview=True)
            success += 1
        except Exception as e:
            failed += 1
        time.sleep(0.05)
    result_msg = f"""
✅ *Broadcast Complete!*
📊 *Statistics:*
• ✅ Sent: `{success}` users
• ❌ Failed: `{failed}` users
• 📝 Total: `{len(users)}` users
⏱️ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
    del temp_data[user_id]

def confirm_giveaway(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if user_id not in temp_data:
        bot.edit_message_text("❌ Giveaway cancelled. No data found.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id))
        return
    credits = temp_data[user_id]['giveaway_credits']
    bot.edit_message_text(f"🎁 *Processing Giveaway...*\n\nGiving `{credits}` credits to all users...", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
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
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
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



# ==================== DAILY USER MOTIVATION BROADCAST ====================
def build_daily_user_motivation_text():
    return f"""
🚀 *TraceX Daily Reminder*
━━━━━━━━━━━━━━━━━━

Keep using TraceX for fast number lookup and fresh features.

🌐 *Try Website:* {WEBSITE_URL}

✅ Instant credits add
✅ Less credits cost
✅ More accurate search
✅ Smooth website experience

Open website now and continue your searches faster.
{footer()}
"""

def send_daily_user_motivation_loop():
    """Send one scheduled promotional message to all non-banned users daily at 11 AM IST."""
    while True:
        try:
            now = datetime.now(IST)
            target = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            time.sleep(max(60, int((target - now).total_seconds())))
            users = get_all_users()
            text = build_daily_user_motivation_text()
            sent = 0
            for uid in users:
                try:
                    bot.send_message(uid, text, parse_mode="Markdown", disable_web_page_preview=True)
                    sent += 1
                    time.sleep(0.05)
                except Exception as e:
                    print(f"Daily user promo failed for {uid}: {e}")
            try:
                bot.send_message(ADMIN_ID, f"✅ Daily website promo sent to `{sent}` users.", parse_mode="Markdown")
            except Exception:
                pass
        except Exception as e:
            print(f"Daily motivation loop error: {e}")
            time.sleep(300)

# ==================== START BOT ====================
if __name__ == "__main__":
    print("=" * 50)
    print(f"TraceX Lookup v{BOT_VERSION} is starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Admin: {ADMIN_USERNAME}")
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
            # Telegram 409 means another instance is still running with the same bot token.
            if "409" in str(e) or "getUpdates" in str(e):
                print("⚠️ Telegram 409 conflict: stop old Render/Termux/other bot instance using same BOT_TOKEN.")
            time.sleep(10)