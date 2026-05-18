"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System with Supabase & Cashfree
Version: 4.2 - Production Ready with Secure Webhook
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
BOT_VERSION = "4.2"

# Lookup API Configuration
LOOKUP_API_URL = os.getenv("LOOKUP_API_URL", "https://techvishalboss.com/apibuy/public/lookup.php")
LOOKUP_API_KEY = os.getenv("LOOKUP_API_KEY", "TVB_Y9T032")
LOOKUP_API_SERVICE = os.getenv("LOOKUP_API_SERVICE", "number")

COOLDOWN_SECONDS = 3
AUTO_DELETE_SECONDS = 120
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/Gaurav_beni_0001")

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
    return f"\n\n━━━━━━━━━━━━━━━━\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def header(title, emoji="🚀"):
    return f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━\n"

def main_menu_markup(current_user_id=None):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📱 NUMBER LOOKUP", callback_data="lookup"),
        InlineKeyboardButton("💎 MY CREDITS", callback_data="credits")
    )
    markup.add(
        InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"),
        InlineKeyboardButton("🛡️ PROTECT NUMBER", callback_data="protect")
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
        InlineKeyboardButton("🚀 1 Hour Unlimited - ₹9", callback_data="plan_u1h"),
        InlineKeyboardButton("🚀 1 Day Unlimited - ₹29", callback_data="plan_u1d")
    )
    markup.add(
        InlineKeyboardButton("🚀 7 Days Unlimited - ₹149", callback_data="plan_u1w"),
        InlineKeyboardButton("🚀 30 Days Unlimited - ₹399", callback_data="plan_u1m")
    )
    markup.add(
        InlineKeyboardButton("🛡️ Protect Number - ₹49", callback_data="plan_protect49")
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

def deduct_credit(telegram_user_id):
    try:
        user = get_user(telegram_user_id)
        if not user:
            return False
        
        unlimited_expiry = user.get('unlimited_expiry')
        if unlimited_expiry:
            if isinstance(unlimited_expiry, str):
                expiry_date = datetime.fromisoformat(unlimited_expiry.replace('Z', '+00:00'))
            else:
                expiry_date = unlimited_expiry
            if expiry_date > datetime.now(timezone.utc):
                return True
        
        credits = user.get('credits', 0)
        if credits > 0:
            supabase.table("telegram_users").update({
                "credits": credits - 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("telegram_user_id", telegram_user_id).execute()
            return True
        return False
    except Exception as e:
        print(f"Deduct credit error: {e}")
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

def add_protected_number(phone_number, telegram_user_id):
    try:
        supabase.table("protected_numbers").insert({
            "phone_number": phone_number,
            "telegram_user_id": telegram_user_id,
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
        existing = supabase.table("search_results").select("id,mobile_number").eq("mobile_number", phone_number).limit(1).execute()
        if existing.data and len(existing.data) > 0:
            row_id = existing.data[0].get("id")
            # Do not use updated_at here because the current table may not have that column.
            supabase.table("search_results").update({
                "raw_data": raw_data
            }).eq("id", row_id).execute()
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

# ==================== RESULT FORMATTING ====================
def format_lookup_result(result, phone, user_id, unlimited_active=False, unlimited_expiry=None):
    """Format API/cache result. Supports API format with results -> Result 1..16 and old cache direct Result keys."""
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
    
    output = f"""
🔍 *NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

📊 Total Results Found: `{len(parsed_results)}`
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
💎 *Credits Used:* `1`
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
    phone = message.text.strip()
    
    if user_id in user_states:
        del user_states[user_id]
    
    if phone == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    if not re.match(r'^[6-9]\d{9}$', phone):
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.\nExample: `9876543210`", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
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
    
    if total_credits <= 0 and not unlimited_active:
        markup = universal_markup(buy=True, join=True, admin=True)
        bot.reply_to(message, "❌ *No credits!* Buy more credits or get an unlimited plan.", reply_markup=markup, parse_mode='Markdown')
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

You can also protect your number for just ₹49!
""", reply_markup=markup, parse_mode='Markdown')
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
            if not deduct_credit(user_id):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
                return
        
        increment_total_searches(user_id)
        
        output, first_name = format_lookup_result(cached_result, phone, user_id, unlimited_active, unlimited_expiry)
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
        
        sent_msg = bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode='Markdown')
        
        log_message = f"""
🔍 *SEARCH LOG (Cached)*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
👤 Name Found: `{first_name}`
🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass
        
        def auto_delete():
            time.sleep(AUTO_DELETE_SECONDS)
            try:
                bot.delete_message(message.chat.id, sent_msg.message_id)
            except:
                pass
        
        threading.Thread(target=auto_delete, daemon=True).start()
        return
    
    try:
        url = f"{LOOKUP_API_URL}?key={LOOKUP_API_KEY}&service={LOOKUP_API_SERVICE}&query={phone}"
        r = requests.get(url, timeout=10)
        result = r.json()
    except Exception as e:
        bot.edit_message_text(f"❌ *API Error*\n\n{str(e)}", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        return

    if result and result.get('results'):
        if not unlimited_active:
            if not deduct_credit(user_id):
                bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                    message.chat.id, loading_msg.message_id, parse_mode='Markdown')
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
        
        sent_msg = bot.edit_message_text(output, message.chat.id, loading_msg.message_id, reply_markup=markup, parse_mode='Markdown')
        
        log_message = f"""
🔍 *SEARCH LOG*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
👤 Name Found: `{first_name}`
🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass
        
        def auto_delete():
            time.sleep(AUTO_DELETE_SECONDS)
            try:
                bot.delete_message(message.chat.id, sent_msg.message_id)
            except:
                pass
        
        threading.Thread(target=auto_delete, daemon=True).start()
        
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
        
        log_message = f"""
🔍 *SEARCH LOG (No Data)*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass

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
• 1 Hour Unlimited → ₹9
• 1 Day Unlimited → ₹29
• 7 Days Unlimited → ₹149
• 30 Days Unlimited → ₹399

🛡️ *PROTECTION*
• Protect Number → ₹49

━━━━━━━━━━━━━━━━━━
✅ Permanent Credits NEVER EXPIRE
✅ Unlimited Plans for heavy users
✅ Secure Payments via Cashfree

👇 Select your plan below
{footer()}
"""
    bot.send_message(message.chat.id, packs_msg, reply_markup=credit_packs_markup(), parse_mode='Markdown')

def handle_plan_selection(call):
    plan_id = call.data.replace("plan_", "")
    user_id = call.from_user.id
    username = call.from_user.username or "no_username"
    
    plan_prices = {"c10": 20, "c50": 70, "c100": 100, "u1h": 9, "u1d": 29, "u1w": 149, "u1m": 399, "protect49": 49}
    amount = plan_prices.get(plan_id, 0)
    
    print(f"Plan selected: {plan_id}, Amount: ₹{amount}, User: {user_id}")
    
    if plan_id == "protect49":
        user_states[user_id] = "awaiting_protect_number"
        msg = bot.send_message(
            call.message.chat.id,
            "🛡️ *PROTECT NUMBER*\n\nEnter the 10-digit mobile number you want to protect:\n\n`Example: 9876543210`\n\n⚠️ Once protected, no one can lookup details for this number!\n\nType /cancel to abort",
            reply_markup=cancel_button(),
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_protect_number, plan_id, amount)
        bot.answer_callback_query(call.id)
        return
    
    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
        bot.answer_callback_query(call.id, "Payment system not configured. Contact admin.", show_alert=True)
        print("ERROR: Cannot create payment - Cashfree credentials missing")
        return
    
    bot.answer_callback_query(call.id, "Creating payment link... ⏳")
    
    order_id, payment_link = create_cashfree_order(plan_id, amount, user_id, username)
    
    if order_id and payment_link:
        bot.answer_callback_query(call.id, f"Payment link created! ₹{amount}")
        
        payment_msg = f"""
💳 *PAYMENT REQUEST*
━━━━━━━━━━━━━━━━━━

💰 *Amount:* ₹{amount}
💎 *Plan:* `{plan_id}`

🔗 *Click below to pay:*
[💳 PAY NOW]({payment_link})

━━━━━━━━━━━━━━━━━━
⚠️ After payment, you'll receive credits automatically.
⏳ Verification takes 1-2 minutes.

📞 For issues: {ADMIN_USERNAME}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 PAY NOW", url=payment_link))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        
        bot.send_message(call.message.chat.id, payment_msg, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "Payment link creation failed. Please try again later.", show_alert=True)
        print(f"❌ Payment link creation failed for user {user_id}, plan {plan_id}")
        
        error_msg = f"""
❌ *Payment Error*

Sorry, we couldn't create a payment link at this moment.

Possible reasons:
• Payment gateway is temporarily unavailable
• Technical issue with our payment processor

Please try again in a few minutes or contact support.

📞 Support: {ADMIN_USERNAME}
"""
        bot.send_message(call.message.chat.id, error_msg, parse_mode='Markdown')

def process_protect_number(message, plan_id, amount):
    user_id = message.from_user.id
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    phone = message.text.strip()
    
    if not re.match(r'^[6-9]\d{9}$', phone):
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.\nExample: `9876543210`", 
                    reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
        return
    
    if is_number_protected(phone):
        bot.reply_to(message, f"❌ *Number already protected!*\n\n📱 `{phone}`\n\nThis number is already in the protection list.", parse_mode='Markdown')
        return
    
    temp_data[user_id] = {'protected_number': phone}
    
    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
        bot.reply_to(message, "❌ Payment system not configured. Contact admin.", parse_mode='Markdown')
        return
    
    order_id, payment_link = create_cashfree_order(plan_id, amount, user_id, message.from_user.username or "no_username", "protect_number", phone)
    
    if order_id and payment_link:
        payment_msg = f"""
🛡️ *PROTECT NUMBER - PAYMENT*
━━━━━━━━━━━━━━━━━━

📱 *Number to protect:* `{phone}`
💰 *Amount:* ₹{amount}
💎 *Plan:* Number Protection

🔗 *Click below to pay:*
[💳 PAY NOW]({payment_link})

━━━━━━━━━━━━━━━━━━
✅ After payment, your number will be protected instantly!
🔒 No one can lookup details for this number.

📞 For issues: {ADMIN_USERNAME}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 PAY NOW", url=payment_link))
        markup.add(InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu"))
        
        bot.send_message(message.chat.id, payment_msg, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Payment system error! Please try again later.", reply_markup=main_menu_markup(user_id))

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
    
    if call.data == "main_menu":
        bot.edit_message_text("🏠 *MAIN MENU*", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(user_id), parse_mode='Markdown')
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
        msg = bot.send_message(call.message.chat.id, "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)
    elif call.data == "protect":
        user_states[user_id] = "awaiting_protect_number"
        msg = bot.send_message(call.message.chat.id, "🛡️ *PROTECT NUMBER*\n\nEnter the 10-digit mobile number you want to protect:\n\n`Example: 9876543210`\n\n⚠️ Once protected, no one can lookup details for this number!\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_protect_number, "protect49", 49)
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
• 1 Hour → ₹9
• 1 Day → ₹29
• 7 Days → ₹149
• 30 Days → ₹399
*🛡️ PROTECTION*
• Protect Number → ₹49
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"))
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(credits_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    elif call.data == "buy":
        show_credit_packs(call.message, user_id)
        bot.answer_callback_query(call.id)
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
• Each lookup costs 1 credit
• Unlimited plans available
• Protected numbers cost ₹49
━━━━━━━━━━━━━━━━━━
🛒 BUYING
• Select plan
• Make payment via Cashfree
• Automatic activation
━━━━━━━━━━━━━━━━━━
⚡ FEATURES
✅ Fast Lookup
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
            msg = bot.send_message(call.message.chat.id, "➕ *ADD CREDITS*\n\nFormat: `user_id credits`\nExample: `123456789 50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE CREDITS*\n\nFormat: `user_id credits`\nExample: `123456789 10`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
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
        InlineKeyboardButton("➕ ADD CREDITS", callback_data="admin_add"),
        InlineKeyboardButton("➖ REMOVE CREDITS", callback_data="admin_remove")
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
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        parts = message.text.split()
        target_user = int(parts[0])
        credits = int(parts[1])
        new_total = add_credits(target_user, credits)
        bot.reply_to(message, f"✅ Added {credits} credits to `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        try:
            bot.send_message(target_user, f"✅ *{credits} credits added!*\nNew total: `{new_total}`", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid format! Use: `user_id credits`", parse_mode='Markdown')

def process_admin_remove(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if user_id in user_states:
        del user_states[user_id]
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup(user_id))
        return
    try:
        parts = message.text.split()
        target_user = int(parts[0])
        credits = int(parts[1])
        user = get_user(target_user)
        if user:
            current_credits = user.get('credits', 0)
            new_credits = max(0, current_credits - credits)
            supabase.table("telegram_users").update({"credits": new_credits, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("telegram_user_id", target_user).execute()
            bot.reply_to(message, f"✅ Removed {credits} credits from `{target_user}`\nNew total: `{new_credits}`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ User `{target_user}` not found!", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid format! Use: `user_id credits`", parse_mode='Markdown')

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