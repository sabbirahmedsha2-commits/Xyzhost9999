# ════════════════════════════════════════════════════════════
#  🚀 STREAMLY BOT HOSTING — PREMIUM EDITION v4.2
#  Fixed: Env isolation (No token hijack), Token duplication check
# ════════════════════════════════════════════════════════════
import asyncio, os, sys, json, re, time, shutil, zipfile, sqlite3
import subprocess, signal, logging, random, string, html
import importlib.util
from datetime import datetime
from pathlib import Path
import aiohttp
import psutil
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery

# ────────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "YOUR_ADMIN_ID_HERE"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")
# ────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("streamly")

BASE_DIR = Path(__file__).parent.absolute()
BOTS_DIR = BASE_DIR / "hosted_bots"
DB_PATH  = BASE_DIR / "streamly.db"
BOTS_DIR.mkdir(exist_ok=True)
BOT_START = time.time()

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ════════════════════════════════════════════════════════════
#  🌐 HTTP & TELEGRAM API
# ════════════════════════════════════════════════════════════
_session: aiohttp.ClientSession | None = None

async def _sess():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=20))
    return _session

async def api(method, payload, timeout=60):
    s = await _sess()
    try:
        async with s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                          json=payload,
                          timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            return await r.json()
    except: return {"ok": False}

async def send(chat_id, text, kb=None, parse_mode="HTML", **extra):
    p = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, **extra}
    if kb is not None: p["reply_markup"] = kb if isinstance(kb, str) else json.dumps(kb, ensure_ascii=False)
    return await api("sendMessage", p)

async def edit(chat_id, mid, text, kb=None, parse_mode="HTML"):
    if not mid: return {"ok": False}
    p = {"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": parse_mode}
    if kb is not None: p["reply_markup"] = kb if isinstance(kb, str) else json.dumps(kb, ensure_ascii=False)
    return await api("editMessageText", p)

async def safe_edit(chat_id, mid, text, kb=None):
    if mid:
        r = await edit(chat_id, mid, text, kb)
        if r.get("ok"): return r
    return await send(chat_id, text, kb)

async def answer_cb(cb_id, text=None, alert=False):
    p = {"callback_query_id": cb_id}
    if text: p["text"] = text; p["show_alert"] = alert
    return await api("answerCallbackQuery", p)

async def delete_msg(chat_id, mid): return await api("deleteMessage", {"chat_id": chat_id, "message_id": mid})
def _mid(resp): return (resp.get("result") or {}).get("message_id") if isinstance(resp, dict) and resp.get("ok") else None

# ════════════════════════════════════════════════════════════
#  🎨 KEYBOARDS & TRANSLATIONS
# ════════════════════════════════════════════════════════════
def btn(text, style="primary"): return {"text": text, "style": style}
def rkb(rows, persistent=True): return json.dumps({"keyboard": rows, "resize_keyboard": True, "is_persistent": persistent}, ensure_ascii=False)
def ikb(rows): return json.dumps({"inline_keyboard": rows}, ensure_ascii=False)
def ibtn(text, **kw): return {"text": text, **kw}
def esc(v): return html.escape(str(v), quote=False)

TR = {
 "en": {
  "welcome": "✨ <b>WELCOME TO STREAMLY</b> ✨", "features": "🔥 <b>BOT FEATURES</b>",
  "feat_list": "├ 🚀 Unlimited bot hosting\n├ 🎨 Beautiful premium UI\n├ 💳 Credit & VIP system\n├ 🔒 Secure sandbox\n└ ⚡ Blazing fast servers",
  "btn_upload":"📤 UPLOAD BOT", "btn_profile":"👤 PROFILE", "btn_mybot":"🤖 MY BOT", "btn_speed":"⚡ BOT SPEED",
  "btn_status":"📊 BOT STATUS", "btn_channel":"📢 UPDATE CHANNEL", "btn_refer":"🎁 REFER", "btn_redeem":"🎟️ REDEEM CODE",
  "btn_lang":"🌐 LANGUAGE", "btn_vip":"💎 VIP FEATURE", "btn_dev":"👨‍💻 DEVELOPER", "btn_back":"🔙 BACK",
  "upload_title":"📤 <b>UPLOAD FILES</b> 📤", "credits":"💳 <b>Credits:</b> <code>{credits}</code>",
  "formats": "📝 <b>Supported Formats</b>\n🐍 Python (.py)\n🟨 JavaScript (.js)\n📦 ZIP Archives (.zip)",
  "how_upload": "💡 <b>How to Upload</b>\n\n1️⃣ Send your file to the bot\n2️⃣ Wait for security scan\n3️⃣ Add packages (optional)\n4️⃣ Upload DB (if needed)\n5️⃣ Admin approves → bot runs",
  "scan_step1": "🔍 <b>SCAN</b>\n\n<code>▓▓▓░░░░░░░</code> 25%\n\n<i>Reading file info...</i>",
  "scan_step2": "🔍 <b>SCAN</b>\n\n<code>▓▓▓▓▓░░░░░</code> 50%\n\n<i>Downloading file...</i>",
  "scan_step3": "🔍 <b>SCAN</b>\n\n<code>▓▓▓▓▓▓▓░░░</code> 75%\n\n<i>Auto-installing packages...</i>",
  "scan_done": "✅ <b>SECURITY PASSED</b>\n\n<code>▓▓▓▓▓▓▓▓▓▓</code> 100%",
  "scan_fail": "🚫 <b>MALICIOUS FILE</b>\n\n<b>Reason:</b> {reason}",
  "auto_installed": "📦 <b>Auto-installed packages:</b>\n{items}",
  "ask_pkg": "📦 <b>PACKAGE INSTALLATION</b>\n\nDo you want to install additional packages manually?\n\n📝 Send package names separated by space\n<i>Example:</i> <code>pyrogram telethon</code>\n\nOr tap <b>SKIP</b> below.",
  "ask_db": "💾 <b>DATABASE</b>\n\nDoes your bot need a database file?\n\nIf yes, upload <code>.db</code>, <code>.sqlite</code>, or <code>.zip</code>.\n\nOr tap <b>SKIP</b>.",
  "upload_cancelled": "❌ <b>UPLOAD CANCELLED</b>",
  "submitted": "🎉 <b>SUBMITTED FOR APPROVAL</b>",
  "approved": "✅ <b>BOT APPROVED!</b>\n\nYour bot <b>{name}</b> is now live!",
  "rejected": "❌ <b>BOT REJECTED</b>\n\n<b>Reason:</b> {reason}",
  "no_credits": "❌ <b>NOT ENOUGH CREDITS</b>\n\nYou need <b>10 credits</b> to host a bot.\nYou have: <b>{credits}</b>",
  "profile_t": "👤 <b>MY PROFILE</b>",
  "profile": "📛 <b>Name:</b> {name}\n🔗 <b>Username:</b> {uname}\n🆔 <b>User ID:</b> <code>{uid}</code>\n💳 <b>Credits:</b> {credits}\n💎 <b>Account:</b> {vip}\n📅 <b>Joined:</b> {joined}\n\n━━━━━━━━━━━━━━━━━━━\n🤖 <b>Bots:</b> {bots} total ({running} running)\n📤 <b>Uploads:</b> {uploads}\n💾 <b>Storage:</b> {storage}\n🖥️ <b>CPU:</b> {cpu}  •  💾 <b>RAM:</b> {ram}",
  "mybot_empty": "📭 <b>NO BOTS YET</b>",
  "mybot_list": "🤖 <b>MY BOTS ({count})</b>",
  "bot_panel": "🤖 <b>{name}</b>\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>Bot:</b> {bot_uname}\n🚦 <b>Status:</b> {status}\n📅 <b>Created:</b> {created}\n💾 <b>Size:</b> {size}\n🖥️ <b>CPU:</b> {cpu}  •  💾 <b>RAM:</b> {ram}",
  "speed_t": "⚡ <b>BOT SPEED</b>",
  "speed": "🚀 <b>Response:</b> {ms} ms\n🟢 <b>Hosting service:</b> ONLINE\n⚙️ <b>System:</b> PYTHON {py}\n💻 <b>CPU:</b> {cpu}%\n💾 <b>RAM:</b> {ram}%\n🖥️ <b>Your online bots:</b> {online}",
  "status_t": "📊 <b>BOT STATUS</b>",
  "status": "🟢 <b>Service:</b> ONLINE\n🤖 <b>Your bots:</b> {bots}\n▶️ <b>Running:</b> {running}\n👥 <b>Total users:</b> {users}\n💾 <b>Storage used:</b> {storage}\n💻 <b>CPU:</b> {cpu}%\n🧠 <b>RAM:</b> {ram}%\n⏱ <b>Uptime:</b> {uptime}",
  "refer_t": "🎁 <b>REFER & EARN</b>",
  "refer": "💰 <b>EARN CREDITS FOR FREE</b>\n\n🎯 <b>Per Refer:</b> 5 credits\n🎯 <b>Bot Hosting:</b> 10 credits\n\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>Your Refer Link:</b>\n<code>https://t.me/{bot}?start=ref_{uid}</code>\n\n📊 <b>Total Referrals:</b> {count}",
  "redeem_t": "🎟️ <b>REDEEM CODE</b>", "redeem_ask": "Enter your redeem code below 👇",
  "redeem_ok": "🎉 <b>CODE REDEEMED!</b>\n\nYou received <b>{credits} credits</b>!",
  "redeem_bad": "❌ <b>INVALID CODE</b>", "lang_t": "🌐 <b>CHOOSE LANGUAGE</b>", "lang_ok": "✅ <b>Language updated</b>",
  "vip_t": "💎 <b>VIP FEATURES</b>", "vip_body": "🔥 <b>UNLOCK UNLIMITED POWER</b>\n\n✅ Unlimited bot hosting\n✅ No admin approval needed\n✅ Priority servers\n✅ Free package installs\n✅ Unlimited credits\n\n💳 <b>Contact admin to get VIP!</b>",
  "admin_t": "👑 <b>ADMIN PANEL</b>", "a_users":"👥 ALL USERS", "a_stats":"📊 STATISTICS", "a_bcast":"📢 BROADCAST", "a_thisdb":"💾 THIS BOT DB", "a_redeem":"🎟️ REDEEM MAKER", "a_bots":"🤖 ALL HOSTED BOTS", "a_pending":"⏳ PENDING BOTS", "a_settings":"⚙️ SETTINGS", "a_maint":"🔧 MAINTENANCE", "a_sendall":"📦 SEND ALL BOT DB",
  "maint_on": "🔧 <b>MAINTENANCE ON</b>\n\nReason: {reason}", "maint_off": "✅ <b>MAINTENANCE OFF</b>", "maint_notice": "🔧 <b>BOT UNDER MAINTENANCE</b>\n\n{reason}",
 },
 "bn": {
  "welcome": "✨ <b>STREAMLY-তে স্বাগতম</b> ✨", "features": "🔥 <b>বটের ফিচার</b>",
  "feat_list": "├ 🚀 আনলিমিটেড বট হোস্টিং\n├ 🎨 প্রিমিয়াম ডিজাইন\n├ 💳 ক্রেডিট ও VIP\n├ 🔒 সুরক্ষিত সিস্টেম\n└ ⚡ সুপার ফাস্ট সার্ভার",
  "btn_upload":"📤 বট আপলোড", "btn_profile":"👤 প্রোফাইল", "btn_mybot":"🤖 আমার বট", "btn_speed":"⚡ স্পিড", "btn_status":"📊 স্ট্যাটাস", "btn_channel":"📢 আপডেট চ্যানেল", "btn_refer":"🎁 রেফার", "btn_redeem":"🎟️ রিডিম কোড", "btn_lang":"🌐 ভাষা", "btn_vip":"💎 ভিআইপি", "btn_dev":"👨‍💻 ডেভেলপার", "btn_back":"🔙 পিছনে",
  "upload_title":"📤 <b>ফাইল আপলোড</b> 📤", "credits":"💳 <b>ক্রেডিট:</b> <code>{credits}</code>",
  "formats": "📝 <b>সাপোর্টেড ফরম্যাট</b>\n🐍 Python (.py)\n🟨 JavaScript (.js)\n📦 ZIP (.zip)",
  "how_upload": "💡 <b>কিভাবে আপলোড করবেন</b>\n\n1️⃣ ফাইল পাঠান\n2️⃣ সিকিউরিটি স্ক্যান\n3️⃣ প্যাকেজ যোগ (অপশনাল)\n4️⃣ ডাটাবেস আপলোড\n5️⃣ এডমিন এপ্রুভ করলে বট চলে",
  "scan_step1": "🔍 <b>সিকিউরিটি স্ক্যান</b>\n\n<code>▓▓▓░░░░░░░</code> 25%\n\n<i>ফাইল ইনফো আসছে...</i>",
  "scan_step2": "🔍 <b>সিকিউরিটি স্ক্যান</b>\n\n<code>▓▓▓▓▓░░░░░</code> 50%\n\n<i>ডাউনলোড হচ্ছে...</i>",
  "scan_step3": "🔍 <b>সিকিউরিটি স্ক্যান</b>\n\n<code>▓▓▓▓▓▓▓░░░</code> 75%\n\n<i>প্যাকেজ ইনস্টল হচ্ছে...</i>",
  "scan_done": "✅ <b>সিকিউরিটি পাস</b>\n\n<code>▓▓▓▓▓▓▓▓▓▓</code> 100%",
  "scan_fail": "🚫 <b>ক্ষতিকর ফাইল</b>\n\n<b>কারণ:</b> {reason}",
  "auto_installed": "📦 <b>অটো-ইনস্টলড প্যাকেজ:</b>\n{items}",
  "ask_pkg": "📦 <b>প্যাকেজ ইনস্টল</b>\n\nআপনি কি ম্যানুয়ালি কোনো প্যাকেজ ইনস্টল করতে চান?\n\n📝 স্পেস দিয়ে লিখুন\n<i>উদাহরণ:</i> <code>pyrogram telethon</code>\n\nঅথবা <b>SKIP</b> চাপুন।",
  "ask_db": "💾 <b>ডাটাবেস</b>\n\nডাটাবেস ফাইল লাগবে?\n\n<code>.db</code>, <code>.sqlite</code>, বা <code>.zip</code> আপলোড করুন।\n\nঅথবা <b>SKIP</b> চাপুন।",
  "upload_cancelled": "❌ <b>আপলোড বাতিল হয়েছে</b>",
  "submitted": "🎉 <b>এপ্রুভালের জন্য পাঠানো হয়েছে</b>",
  "approved": "✅ <b>বট এপ্রুভড!</b>\n\n<b>{name}</b> এখন লাইভ!",
  "rejected": "❌ <b>বট রিজেক্টেড</b>\n\n<b>কারণ:</b> {reason}",
  "no_credits": "❌ <b>পর্যাপ্ত ক্রেডিট নেই</b>\n\nবট হোস্টে <b>১০ ক্রেডিট</b> লাগবে।\nআপনার আছে: <b>{credits}</b>",
  "profile_t": "👤 <b>আমার প্রোফাইল</b>",
  "profile": "📛 <b>নাম:</b> {name}\n🔗 <b>ইউজারনেম:</b> {uname}\n🆔 <b>আইডি:</b> <code>{uid}</code>\n💳 <b>ক্রেডিট:</b> {credits}\n💎 <b>একাউন্ট:</b> {vip}\n📅 <b>জয়েন:</b> {joined}\n\n━━━━━━━━━━━━━━━━━━━\n🤖 <b>বট:</b> {bots} ({running} চলছে)\n📤 <b>আপলোড:</b> {uploads}\n💾 <b>স্টোরেজ:</b> {storage}\n🖥️ <b>CPU:</b> {cpu}  •  💾 <b>RAM:</b> {ram}",
  "mybot_empty": "📭 <b>কোনো বট নেই</b>",
  "mybot_list": "🤖 <b>আমার বট ({count})</b>",
  "bot_panel": "🤖 <b>{name}</b>\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>বট:</b> {bot_uname}\n🚦 <b>স্ট্যাটাস:</b> {status}\n📅 <b>তৈরি:</b> {created}\n💾 <b>সাইজ:</b> {size}\n🖥️ <b>CPU:</b> {cpu}  •  💾 <b>RAM:</b> {ram}",
  "speed_t": "⚡ <b>বট স্পিড</b>",
  "speed": "🚀 <b>রেসপন্স:</b> {ms} ms\n🟢 <b>হোস্টিং সার্ভিস:</b> ONLINE\n⚙️ <b>সিস্টেম:</b> PYTHON {py}\n💻 <b>CPU:</b> {cpu}%\n💾 <b>RAM:</b> {ram}%\n🖥️ <b>আপনার অনলাইন বট:</b> {online}",
  "status_t": "📊 <b>বট স্ট্যাটাস</b>",
  "status": "🟢 <b>সার্ভিস:</b> ONLINE\n🤖 <b>আপনার বট:</b> {bots}\n▶️ <b>চলছে:</b> {running}\n👥 <b>মোট ইউজার:</b> {users}\n💾 <b>স্টোরেজ:</b> {storage}\n💻 <b>CPU:</b> {cpu}%\n🧠 <b>RAM:</b> {ram}%\n⏱ <b>আপটাইম:</b> {uptime}",
  "refer_t": "🎁 <b>রেফার ও আর্ন</b>",
  "refer": "💰 <b>ফ্রি ক্রেডিট কামান</b>\n\n🎯 <b>প্রতি রেফার:</b> ৫ ক্রেডিট\n🎯 <b>বট হোস্টিং:</b> ১০ ক্রেডিট\n\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>আপনার রেফার লিংক:</b>\n<code>https://t.me/{bot}?start=ref_{uid}</code>\n\n📊 <b>মোট রেফার:</b> {count}",
  "redeem_t": "🎟️ <b>রিডিম কোড</b>", "redeem_ask": "নিচে রিডিম কোড পাঠান 👇",
  "redeem_ok": "🎉 <b>কোড রিডিমড!</b>\n\nপেয়েছেন <b>{credits} ক্রেডিট</b>!",
  "redeem_bad": "❌ <b>ভুল কোড</b>", "lang_t": "🌐 <b>ভাষা বেছে নিন</b>", "lang_ok": "✅ <b>ভাষা আপডেট হয়েছে</b>",
  "vip_t": "💎 <b>ভিআইপি ফিচার</b>", "vip_body": "🔥 <b>আনলিমিটেড পাওয়ার আনলক</b>\n\n✅ আনলিমিটেড বট হোস্ট\n✅ এডমিন এপ্রুভাল লাগবে না\n✅ প্রায়োরিটি সার্ভার\n✅ ফ্রি প্যাকেজ ইনস্টল\n✅ আনলিমিটেড ক্রেডিট\n\n💳 <b>VIP পেতে এডমিনে যোগাযোগ করুন!</b>",
  "admin_t": "👑 <b>এডমিন প্যানেল</b>", "a_users":"👥 সব ইউজার", "a_stats":"📊 স্ট্যাটস", "a_bcast":"📢 ব্রডকাস্ট", "a_thisdb":"💾 এই বটের DB", "a_redeem":"🎟️ রিডিম মেকার", "a_bots":"🤖 সব হোস্টেড বট", "a_pending":"⏳ পেন্ডিং বট", "a_settings":"⚙️ সেটিংস", "a_maint":"🔧 মেইনটেনেন্স", "a_sendall":"📦 সব বট DB পাঠান",
  "maint_on": "🔧 <b>মেইনটেনেন্স চালু</b>\n\nকারণ: {reason}", "maint_off": "✅ <b>মেইনটেনেন্স বন্ধ</b>", "maint_notice": "🔧 <b>বট মেইনটেনেন্সে</b>\n\n{reason}",
 },
}

USER_LANG: dict[int, str] = {}
STATE:     dict[int, dict] = {}
BOT_PROCS: dict[int, dict] = {}
SETTINGS:  dict[str, str] = {}

def t(_uid, key, **kw):
    lang = USER_LANG.get(_uid, "en")
    s = TR[lang].get(key) or TR["en"].get(key, key)
    return s.format(**kw) if kw else s

def _norm(s): return ''.join(c for c in s if c.isalnum()).lower()
_BTN_KEYS = ["btn_upload", "btn_profile", "btn_mybot", "btn_speed", "btn_status", "btn_channel", "btn_refer", "btn_redeem", "btn_lang", "btn_vip", "btn_dev", "btn_back", "a_users", "a_stats", "a_bcast", "a_thisdb", "a_redeem", "a_bots", "a_pending", "a_settings", "a_maint", "a_sendall"]

def find_btn(text, uid):
    tnorm = _norm(text)
    if not tnorm: return None
    for lang in {USER_LANG.get(uid, "en"), "en", "bn"}:
        for key in _BTN_KEYS:
            btn_text = TR[lang].get(key, "")
            if btn_text and _norm(btn_text) == tnorm: return key
    return None

def is_back(text, uid): return find_btn(text, uid) == "btn_back" or _norm(text) in (_norm("🔙 BACK"), _norm("🔙 পিছনে"))

# ════════════════════════════════════════════════════════════
#  💾 DATABASE
# ════════════════════════════════════════════════════════════
def db():
    c = sqlite3.connect(DB_PATH, timeout=30.0)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000"); c.execute("PRAGMA synchronous=NORMAL")
    except: pass
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, username TEXT DEFAULT '', first_name TEXT DEFAULT '', credits INTEGER DEFAULT 10, is_vip INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, ban_reason TEXT DEFAULT '', support_url TEXT DEFAULT '', referrer INTEGER DEFAULT 0, refer_count INTEGER DEFAULT 0, uploads INTEGER DEFAULT 0, joined_at TEXT);
    CREATE TABLE IF NOT EXISTS bots (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, name TEXT, path TEXT, db_path TEXT DEFAULT '', bot_username TEXT DEFAULT '', status TEXT DEFAULT 'pending', pid INTEGER DEFAULT 0, created_at TEXT, reject_reason TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS redeem (code TEXT PRIMARY KEY, credits INTEGER, used_by INTEGER DEFAULT 0, used_at TEXT DEFAULT '', created_at TEXT);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS pending (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, name TEXT, path TEXT, db_path TEXT DEFAULT '', bot_username TEXT DEFAULT '', packages TEXT DEFAULT '', created_at TEXT, approved INTEGER DEFAULT 0);
    """)
    for stmt in ["ALTER TABLE bots ADD COLUMN bot_username TEXT DEFAULT ''", "ALTER TABLE pending ADD COLUMN bot_username TEXT DEFAULT ''"]:
        try: c.execute(stmt)
        except: pass
    c.commit(); c.close()

def get_user(uid):
    c = db(); r = c.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone(); c.close()
    return dict(r) if r else None

def create_user(uid, username, first_name, referrer=0):
    c = db()
    c.execute("INSERT OR IGNORE INTO users (uid, username, first_name, joined_at, referrer) VALUES (?,?,?,?,?)", (uid, username or "", first_name or "", datetime.now().isoformat(), referrer))
    if referrer and referrer != uid:
        c.execute("UPDATE users SET credits = credits + 5 WHERE uid=?", (referrer,))
        c.execute("UPDATE users SET refer_count = refer_count + 1 WHERE uid=?", (referrer,))
    c.commit(); c.close()

def get_setting(k, d=""):
    if k in SETTINGS: return SETTINGS[k]
    c = db(); r = c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone(); c.close()
    return r["value"] if r else d

def save_setting(k, v):
    SETTINGS[k] = v
    c = db(); c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (k, v)); c.commit(); c.close()

# ════════════════════════════════════════════════════════════
#  🛡️ SECURITY & AUTO-INSTALL
# ════════════════════════════════════════════════════════════
MALICIOUS = [(r"stratum\+tcp|stratum\+ssl|xmrig|minerd|cpuminer", "Crypto miner"), (r"socket\.socket[\s\S]{0,200}connect\s*\(", "Reverse shell"), (r"subprocess.*['\"]nc['\"].*-e", "Reverse shell"), (r"bash\s+-i\s+>&\s*/dev/tcp", "Reverse shell"), (r"rm\s+-rf\s+/(?:\s|;|&)", "Destructive"), (r"base64\.b64decode.*exec", "Obfuscated"), (r"os\.system\s*\(\s*['\"]curl.*\|\s*sh", "Remote code"), (r"(?i)(?:https?://)?pastebin\.com/raw", "Pastebin")]
DANGEROUS = {"paramiko", "ftplib", "telnetlib", "pexpect"}

def scan_file(path):
    try: code = path.read_text(errors="ignore")
    except: return True, ""
    for pattern, reason in MALICIOUS:
        if re.search(pattern, code): return False, reason
    for imp in DANGEROUS:
        if re.search(rf"^\s*(?:import|from)\s+{imp}", code, re.MULTILINE): return False, f"Dangerous import: {imp}"
    return True, ""

def extract_imports(file_path):
    modules = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for match in re.finditer(r'^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE):
            modules.add(match.group(1).split('.')[0])
    except: pass
    return modules

def install_missing_py(file_path):
    imports = extract_imports(file_path)
    installed = []
    pip_map = {'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot', 'PIL': 'Pillow', 'cv2': 'opencv-python-headless', 'bs4': 'beautifulsoup4', 'dotenv': 'python-dotenv', 'Crypto': 'pycryptodome', 'yaml': 'PyYAML', 'requests': 'requests', 'aiohttp': 'aiohttp'}
    
    for mod in imports:
        if mod in sys.stdlib_module_names or mod == '__future__': continue
        if importlib.util.find_spec(mod) is None:
            pkg = pip_map.get(mod, mod)
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], timeout=120)
                installed.append(pkg)
            except: pass
    return installed

async def auto_install_from_zip(user_dir: Path, chat_id, uid) -> list:
    installed = []
    req_file = user_dir / "requirements.txt"
    if not req_file.exists():
        for f in user_dir.rglob("requirements.txt"): req_file = f; break

    if req_file.exists():
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"], capture_output=True, timeout=300)
            installed.append("✅ requirements.txt" if r.returncode == 0 else "⚠️ requirements.txt (partial)")
        except: installed.append("❌ requirements.txt")

    pkg_file = user_dir / "package.json"
    if not pkg_file.exists():
        for f in user_dir.rglob("package.json"): pkg_file = f; break

    if pkg_file.exists():
        try:
            r = subprocess.run(["npm", "install"], cwd=str(pkg_file.parent), capture_output=True, timeout=300)
            installed.append("✅ package.json" if r.returncode == 0 else "⚠️ package.json")
        except: installed.append("❌ package.json")
    return installed

def extract_bot_token(file_path):
    try: code = Path(file_path).read_text(errors="ignore")
    except: return None
    patterns = [
        r'(?:^|\s|;)(?:bot_token|BOT_TOKEN|TOKEN|token|api_token|API_TOKEN)\s*=\s*["\'](\d{8,10}:[A-Za-z0-9_-]{30,})["\']',
        r'["\'](\d{8,10}:[A-Za-z0-9_-]{30,})["\']',
    ]
    for pat in patterns:
        m = re.search(pat, code, re.MULTILINE | re.IGNORECASE)
        if m: return m.group(1)
    return None

async def detect_bot_username(file_path):
    token = extract_bot_token(file_path)
    if not token: return ""
    try:
        s = await _sess()
        async with s.get(f"https://api.telegram.org/bot{token}/getMe", timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = await r.json()
            if data.get("ok"): return data["result"].get("username", "")
    except: pass
    return ""

# ════════════════════════════════════════════════════════════
#  🤖 BOT PROCESS (Fixed Token Hijack)
# ════════════════════════════════════════════════════════════
def stop_bot(bot_id):
    info = BOT_PROCS.get(bot_id)
    if info:
        try:
            p = info["proc"]
            if p.poll() is None:
                parent = psutil.Process(p.pid)
                for child in parent.children(recursive=True):
                    try: child.kill()
                    except: pass
                parent.kill()
                p.wait(timeout=3)
        except: pass
        try: info["log"].close()
        except: pass
        BOT_PROCS.pop(bot_id, None)
    c = db(); c.execute("UPDATE bots SET status='stopped', pid=0 WHERE id=?", (bot_id,)); c.commit(); c.close()

async def start_bot_async(bot_id) -> tuple[bool, str]:
    stop_bot(bot_id)
    c = db(); row = c.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone(); c.close()
    if not row: return False, "Bot not found"
    path = Path(row["path"])
    if not path.exists(): return False, "Bot file missing"

    # 1. Delete Webhook
    token = extract_bot_token(path)
    if token:
        try:
            s = await _sess()
            await s.get(f"https://api.telegram.org/bot{token}/deleteWebhook")
        except: pass

    log_path = path.parent / "bot.log"
    log_f = open(log_path, "w", encoding="utf-8")
    log_f.write(f"[START {datetime.now().isoformat()}]\n")

    # 2. ENVIRONMENT ISOLATION (Prevent Hijacking Main Bot)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Remove main bot's TOKEN so child bot doesn't accidentally use it
    env.pop("TOKEN", None) 
    env.pop("ADMIN_ID", None)
    env.pop("BOT_USERNAME", None)

    try:
        if path.suffix == ".py":
            proc = subprocess.Popen([sys.executable, "-u", str(path)], cwd=str(path.parent), stdout=log_f, stderr=subprocess.STDOUT, env=env)
        elif path.suffix == ".js":
            proc = subprocess.Popen(["node", str(path)], cwd=str(path.parent), stdout=log_f, stderr=subprocess.STDOUT, env=env)
        else:
            log_f.close(); return False, "Unsupported file type"

        BOT_PROCS[bot_id] = {"proc": proc, "log": log_f, "log_path": log_path}
        await asyncio.sleep(2.0)
        
        if proc.poll() is not None:
            BOT_PROCS.pop(bot_id, None); log_f.close()
            err_log = log_path.read_text(errors="ignore")[-1000:]
            c = db(); c.execute("UPDATE bots SET status='error', pid=0 WHERE id=?", (bot_id,)); c.commit(); c.close()
            return False, err_log
        else:
            c = db(); c.execute("UPDATE bots SET status='running', pid=? WHERE id=?", (proc.pid, bot_id)); c.commit(); c.close()
            return True, ""
    except Exception as e:
        log_f.close(); c = db(); c.execute("UPDATE bots SET status='error', pid=0 WHERE id=?", (bot_id,)); c.commit(); c.close()
        return False, str(e)

def is_bot_running(bot_id):
    info = BOT_PROCS.get(bot_id)
    return bool(info and info["proc"].poll() is None)

# ════════════════════════════════════════════════════════════
#  🎯 STATE & KEYBOARDS
# ════════════════════════════════════════════════════════════
class S:
    MENU="menu"; AWAIT_FILE="await_file"; AWAIT_PKG="await_pkg"; AWAIT_DB="await_db"; AWAIT_REDEEM="await_redeem"; AWAIT_BCAST="await_bcast"; AWAIT_REDEEM_CREDITS="await_redeem_credits"; AWAIT_MAINT_REASON="await_maint_reason"; AWAIT_CHANNEL="await_channel"; AWAIT_DEV="await_dev"; AWAIT_SUPPORT="await_support"; AWAIT_REJECT_REASON="await_reject_reason"; AWAIT_BAN_REASON="await_ban_reason"; AWAIT_BAN_URL="await_ban_url"; AWAIT_ADD_CREDITS="await_add_credits"; ADMIN_PANEL="admin_panel"; ADMIN_STATS="admin_stats"; ADMIN_SETTINGS="admin_settings"; ADMIN_MAINT="admin_maint"; INSTALL_PKG="install_pkg"

def st(uid): return STATE.get(uid, {"state": S.MENU})
def set_st(uid, **kw): STATE[uid] = kw

def kb_main(uid):
    return rkb([[btn(t(uid, "btn_upload"), "success")], [btn(t(uid, "btn_profile"), "primary"), btn(t(uid, "btn_mybot"), "primary")], [btn(t(uid, "btn_speed"), "primary"), btn(t(uid, "btn_status"), "primary")], [btn(t(uid, "btn_channel"), "success")], [btn(t(uid, "btn_refer"), "primary"), btn(t(uid, "btn_redeem"), "success")], [btn(t(uid, "btn_lang"), "primary"), btn(t(uid, "btn_vip"), "danger")], [btn(t(uid, "btn_dev"), "danger")]])

def kb_back(uid): return rkb([[btn(t(uid, "btn_back"), "danger")]])
def kb_lang(uid): return rkb([[btn("🇧🇩 বাংলা", "primary"), btn("🇬🇧 ENGLISH", "primary")], [btn(t(uid, "btn_back"), "danger")]])
def kb_pkg(uid): return rkb([[btn("⏭️ SKIP", "success")], [btn(t(uid, "btn_back"), "danger")]])
def kb_admin(uid):
    return rkb([[btn(t(uid, "a_users"), "primary"), btn(t(uid, "a_stats"), "success")], [btn(t(uid, "a_bots"), "primary"), btn(t(uid, "a_pending"), "danger")], [btn(t(uid, "a_bcast"), "primary"), btn(t(uid, "a_redeem"), "success")], [btn(t(uid, "a_thisdb"), "primary"), btn(t(uid, "a_sendall"), "primary")], [btn(t(uid, "a_settings"), "success"), btn(t(uid, "a_maint"), "danger")], [btn(t(uid, "btn_back"), "danger")]])

def ikb_users_list(users):
    rows = [[ibtn(f"{'🚫' if u['banned'] else '💎' if u['is_vip'] else '👤'} {dict(u)['first_name'][:20] or 'User'} • {u['uid']}", callback_data=f"u:{u['uid']}", style="primary")] for u in users]
    rows.append([ibtn("🔙 BACK", callback_data="back:admin", style="danger")]); return ikb(rows)

def ikb_user_detail(u):
    row1 = [ibtn("✅ UNBAN" if u["banned"] else "🚫 BAN", callback_data=f"{'unban' if u['banned'] else 'ban'}:{u['uid']}", style="success" if u['banned'] else "danger")]
    if not u["is_vip"]: row1.append(ibtn("💎 VIP", callback_data=f"vip:{u['uid']}", style="success"))
    return ikb([row1, [ibtn("💳 ADD CREDITS", callback_data=f"cred:{u['uid']}", style="primary")], [ibtn("🔙 BACK", callback_data="back:users", style="danger")]])

def ikb_bots_list(bots):
    rows = []
    for b in bots:
        b = dict(b); icon = "🟢" if is_bot_running(b["id"]) else "🔴" if b["status"]=="stopped" else "⚠️"
        rows.append([ibtn(f"{icon} #{b['id']} {b['name'][:18]} @{b.get('bot_username','')}".strip(), callback_data=f"b:{b['id']}", style="primary")])
    rows.append([ibtn("🔙 BACK", callback_data="back:admin", style="danger")]); return ikb(rows)

def ikb_bot_detail_admin(bid, status):
    return ikb([[ibtn("▶️ ON", callback_data=f"on:{bid}", style="success"), ibtn("⏹ OFF", callback_data=f"off:{bid}", style="danger")], [ibtn("📜 LOG", callback_data=f"log:{bid}", style="primary"), ibtn("💾 DB", callback_data=f"db:{bid}", style="primary")], [ibtn("🔄 REBOOT", callback_data=f"on:{bid}", style="primary"), ibtn("🗑️ DELETE", callback_data=f"del:{bid}", style="danger")], [ibtn("🔙 BACK", callback_data="back:bots", style="danger")]])

def ikb_bot_detail_user(bid, status):
    return ikb([[ibtn("▶️ ON", callback_data=f"uon:{bid}", style="success"), ibtn("⏹ OFF", callback_data=f"uoff:{bid}", style="danger")], [ibtn("📜 LOG", callback_data=f"ulog:{bid}", style="primary"), ibtn("💾 DB", callback_data=f"udb:{bid}", style="primary")], [ibtn("🔄 REBOOT", callback_data=f"uon:{bid}", style="primary"), ibtn("🗑️ DELETE", callback_data=f"udel:{bid}", style="danger")], [ibtn("🔙 BACK", callback_data="back:mybots", style="danger")]])

def ikb_pending_list(pendings):
    rows = [[ibtn(f"⏳ #{dict(p)['id']} {p['name'][:25]}", callback_data=f"p:{p['id']}", style="primary")] for p in pendings]
    rows.append([ibtn("🔙 BACK", callback_data="back:admin", style="danger")]); return ikb(rows)

def ikb_pending_detail(pid): return ikb([[ibtn("✅ APPROVE", callback_data=f"ap:{pid}", style="success"), ibtn("❌ REJECT", callback_data=f"rp:{pid}", style="danger")], [ibtn("🔙 BACK", callback_data="back:pending", style="danger")]])

def ikb_my_bots(bots):
    rows = []
    for b in bots:
        b = dict(b); icon = "🟢" if is_bot_running(b["id"]) else "🔴" if b["status"]=="stopped" else "⚠️"
        rows.append([ibtn(f"{icon} {b['name'][:25]} @{b.get('bot_username','')}".strip(), callback_data=f"mb:{b['id']}", style="primary")])
    rows.append([ibtn("🔙 BACK", callback_data="back:main", style="danger")]); return ikb(rows)

# ════════════════════════════════════════════════════════════
#  🏠 MAIN MENU & UPLOAD FLOW
# ════════════════════════════════════════════════════════════
async def show_main_menu(uid, chat_id):
    u = get_user(uid) or {}
    text = f"╔═══════════════════════╗\n    {t(uid, 'welcome')}\n╚═══════════════════════╝\n\n👋 <b>Hello, {esc(u.get('first_name', 'User'))}!</b>\n\n🆔 <b>User ID:</b> <code>{uid}</code>\n💳 <b>Credits:</b> {u.get('credits', 10)}\n💎 <b>Account:</b> {'VIP 💎' if u.get('is_vip') else 'Regular 🆓'}\n\n━━━━━━━━━━━━━━━━━━━━\n{t(uid, 'features')}\n{t(uid, 'feat_list')}\n━━━━━━━━━━━━━━━━━━━━"
    await send(chat_id, text, kb_main(uid)); set_st(uid, state=S.MENU)

async def show_upload(uid, chat_id):
    u = get_user(uid) or {"credits": 0}
    text = f"╔═══════════════════════╗\n    {t(uid, 'upload_title')}\n╚═══════════════════════╝\n\n{t(uid, 'credits', credits=u.get('credits', 0))}\n\n{t(uid, 'formats')}\n\n━━━━━━━━━━━━━━━━━━━━\n{t(uid, 'how_upload')}"
    await send(chat_id, text, kb_back(uid)); set_st(uid, state=S.AWAIT_FILE)

async def process_uploaded_file(uid, chat_id, message: Message):
    doc = message.document
    if not doc: return
    fname = doc.file_name or "file.py"
    ext = Path(fname).suffix.lower()
    if ext not in {".py", ".js", ".zip"}: await send(chat_id, "❌ Only .py, .js, .zip allowed!", kb_back(uid)); return

    u = get_user(uid)
    if u["credits"] < 10 and not u["is_vip"]: await send(chat_id, t(uid, "no_credits", credits=u["credits"]), kb_back(uid)); set_st(uid, state=S.MENU); return

    scan = await send(chat_id, t(uid, "scan_step1")); mid = _mid(scan); await asyncio.sleep(0.8)
    user_dir = BOTS_DIR / str(uid) / Path(fname).stem

    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / fname
        resp = await api("getFile", {"file_id": doc.file_id}, timeout=30)
        if not resp.get("ok"): raise Exception("getFile failed")
        
        await safe_edit(chat_id, mid, t(uid, "scan_step2"), None)
        s = await _sess()
        async with s.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{resp['result']['file_path']}", timeout=aiohttp.ClientTimeout(total=180)) as r:
            file_path.write_bytes(await r.read())

        await safe_edit(chat_id, mid, t(uid, "scan_step3"), None)
        entry = file_path; auto_installed = []

        if ext == ".zip":
            with zipfile.ZipFile(file_path) as z: z.extractall(user_dir)
            file_path.unlink()
            cands = list(user_dir.rglob("*.py")) + list(user_dir.rglob("*.js"))
            if not cands: raise Exception("ZIP has no .py or .js")
            entry = cands[0]
            auto_installed = await auto_install_from_zip(user_dir, chat_id, uid)
        elif ext == ".py":
            auto_installed = install_missing_py(entry)

        ok, reason = scan_file(entry)
        if not ok:
            await safe_edit(chat_id, mid, t(uid, "scan_fail", reason=esc(reason)), kb_back(uid))
            shutil.rmtree(user_dir, ignore_errors=True); set_st(uid, state=S.MENU); return

        # Check if user is trying to host the main bot itself
        tkn = extract_bot_token(entry)
        if tkn == BOT_TOKEN:
            await safe_edit(chat_id, mid, "❌ <b>REJECTED</b>\n\nYou cannot host the main hosting bot inside itself.", kb_back(uid))
            shutil.rmtree(user_dir, ignore_errors=True); set_st(uid, state=S.MENU); return

        await safe_edit(chat_id, mid, t(uid, "scan_done"), None); await asyncio.sleep(1.3)
        try: await delete_msg(chat_id, mid)
        except: pass

        if auto_installed: await send(chat_id, t(uid, "auto_installed", items="\n".join(f"• {x}" for x in auto_installed)))

        await send(chat_id, t(uid, "ask_pkg"), kb_pkg(uid))
        set_st(uid, state=S.AWAIT_PKG, path=str(entry), bot_dir=str(user_dir), name=fname)
    except Exception as e:
        await safe_edit(chat_id, mid, f"❌ <b>Upload failed</b>\n\n<code>{esc(str(e))}</code>", kb_back(uid)); set_st(uid, state=S.MENU)

async def process_packages(uid, chat_id, text):
    cur = st(uid)
    if text.strip().lower() != "skip":
        msg = await send(chat_id, f"📦 Installing <b>{esc(text)}</b>...")
        ok, fail = [], []
        for n in text.strip().split():
            try: subprocess.run([sys.executable, "-m", "pip", "install", n, "--quiet"], capture_output=True, timeout=120); ok.append(n)
            except: fail.append(n)
        await safe_edit(chat_id, _mid(msg), f"✅ Installed: {', '.join(ok)}\n❌ Failed: {', '.join(fail)}", kb_pkg(uid))

    await send(chat_id, t(uid, "ask_db"), kb_pkg(uid))
    set_st(uid, state=S.AWAIT_DB, path=cur["path"], bot_dir=cur["bot_dir"], name=cur["name"])

async def process_db(uid, chat_id, msg_or_text):
    cur = st(uid); db_file = ""
    if isinstance(msg_or_text, Message) and msg_or_text.document:
        doc = msg_or_text.document
        try:
            resp = await api("getFile", {"file_id": doc.file_id}, timeout=30)
            if resp.get("ok"):
                s = await _sess()
                async with s.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{resp['result']['file_path']}", timeout=aiohttp.ClientTimeout(total=120)) as r:
                    if r.status == 200: db_file = str(Path(cur["bot_dir"]) / doc.file_name); Path(db_file).write_bytes(await r.read())
        except: pass

    bot_uname = await detect_bot_username(cur["path"])
    auto = get_setting("auto_approve", "0") == "1"
    u = get_user(uid)

    if auto:
        c = db()
        if not u["is_vip"]: c.execute("UPDATE users SET credits = credits - 10 WHERE uid=?", (uid,))
        c.execute("INSERT INTO bots (uid, name, path, db_path, bot_username, status, created_at) VALUES (?,?,?,?,?,?,?)", (uid, cur["name"], cur["path"], db_file, bot_uname, "stopped", datetime.now().isoformat()))
        bot_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE users SET uploads = uploads + 1 WHERE uid=?", (uid,)); c.commit(); c.close()
        
        success, err = await start_bot_async(bot_id)
        if success: await send(chat_id, t(uid, "approved", name=esc(cur["name"])))
        else: await send(chat_id, f"⚠️ Bot approved but failed to start!\nError:\n<code>{esc(err)}</code>")
        
        await asyncio.sleep(0.4); await show_bot_panel_user(uid, chat_id, bot_id); set_st(uid, state=S.MENU)
        return

    c = db()
    c.execute("INSERT INTO pending (uid, name, path, db_path, bot_username, created_at) VALUES (?,?,?,?,?,?)", (uid, cur["name"], cur["path"], db_file, bot_uname, datetime.now().isoformat()))
    pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]; c.commit(); c.close()

    await send(chat_id, t(uid, "submitted"), kb_main(uid)); set_st(uid, state=S.MENU)
    text = f"╔═══════════════════════╗\n    🆕 <b>NEW BOT PENDING</b>\n╚═══════════════════════╝\n\n👤 <b>Name:</b> {esc(u['first_name'])}\n🆔 <b>User ID:</b> <code>{uid}</code>\n📦 <b>Bot:</b> <code>{esc(cur['name'])}</code>\n🤖 <b>Bot Username:</b> @{bot_uname or '—'}"
    await send(ADMIN_ID, text, ikb([[ibtn("✅ APPROVE", callback_data=f"ap:{pid}", style="success"), ibtn("❌ REJECT", callback_data=f"rp:{pid}", style="danger")], [ibtn("👑 ADMIN PANEL", callback_data="back:admin", style="primary")]]))

# ════════════════════════════════════════════════════════════
#  🤖 MY BOTS
# ════════════════════════════════════════════════════════════
async def show_my_bots(uid, chat_id):
    c = db(); bots = c.execute("SELECT * FROM bots WHERE uid=? ORDER BY id DESC", (uid,)).fetchall(); c.close()
    if not bots: await send(chat_id, t(uid, "mybot_empty"), kb_back(uid)); set_st(uid, state=S.MENU); return
    await send(chat_id, t(uid, "mybot_list", count=len(bots)), ikb_my_bots(bots)); set_st(uid, state=S.MENU)

async def show_bot_panel_user(uid, chat_id, bot_id):
    c = db(); b = c.execute("SELECT * FROM bots WHERE id=? AND uid=?", (bot_id, uid)).fetchone(); c.close()
    if not b: await send(chat_id, "❌ Bot not found", kb_back(uid)); return
    b = dict(b); running = is_bot_running(bot_id)
    status_text = "🟢 Running" if running else ("🔴 Stopped" if b["status"]=="stopped" else "⚠️ Error/Crashed")
    cpu = ram = "0%"
    if running:
        try: p = psutil.Process(BOT_PROCS[bot_id]["proc"].pid); cpu = f"{p.cpu_percent()}%"; ram = f"{p.memory_percent():.1f}%"
        except: pass

    size = Path(b["path"]).stat().st_size if Path(b["path"]).exists() else 0
    body = t(uid, "bot_panel", name=esc(b["name"]), bot_uname=esc(f"@{b['bot_username']}" if b.get("bot_username") else "Not detected"), status=status_text, created=b["created_at"][:16], size=f"{size/1024:.1f} KB", cpu=cpu, ram=ram)
    
    if b["status"] == "error":
        logp = Path(b["path"]).parent / "bot.log"
        if logp.exists(): body += f"\n\n🚨 <b>ERROR LOG:</b>\n<pre>{esc(logp.read_text(errors='ignore')[-800:])}</pre>"
            
    await send(chat_id, f"╔═══════════════════════╗\n    🤖 <b>MY BOT</b>\n╚═══════════════════════╝\n\n{body}", ikb_bot_detail_user(bot_id, b["status"]))

# ════════════════════════════════════════════════════════════
#  👤 PROFILE / ⚡ SPEED / 📊 STATUS / 🎁 REFER / 🎟️ REDEEM / 💎 VIP
# ════════════════════════════════════════════════════════════
async def show_profile(uid, chat_id):
    u = get_user(uid); c = db(); bots = c.execute("SELECT * FROM bots WHERE uid=?", (uid,)).fetchall(); c.close()
    running = sum(1 for b in bots if is_bot_running(b["id"])); storage = sum(Path(b["path"]).stat().st_size for b in bots if Path(b["path"]).exists())
    try: cpu, ram = f"{psutil.cpu_percent():.1f}%", f"{psutil.virtual_memory().percent:.1f}%"
    except: cpu = ram = "N/A"
    body = t(uid, "profile", name=esc(u["first_name"]), uname="@"+u["username"] if u["username"] else "—", uid=uid, credits=u["credits"], vip="VIP 💎" if u["is_vip"] else "Regular 🆓", joined=u["joined_at"][:10], bots=len(bots), running=running, uploads=u["uploads"], storage=f"{storage/1024/1024:.2f} MB", cpu=cpu, ram=ram)
    await send(chat_id, f"╔═══════════════════════╗\n    {t(uid, 'profile_t')}\n╚═══════════════════════╝\n\n{body}", kb_back(uid)); set_st(uid, state=S.MENU)

async def show_speed(uid, chat_id):
    start = time.time(); msg = await send(chat_id, "⚡ <i>Testing...</i>"); ms = (time.time() - start) * 1000
    c = db(); running = sum(1 for b in c.execute("SELECT * FROM bots WHERE uid=?", (uid,)).fetchall() if is_bot_running(b["id"])); c.close()
    try: cpu, ram = f"{psutil.cpu_percent():.1f}", f"{psutil.virtual_memory().percent:.1f}"
    except: cpu = ram = "N/A"
    body = t(uid, "speed", ms=f"{ms:.2f}", py=f"{sys.version_info.major}.{sys.version_info.minor}", cpu=cpu, ram=ram, online=running)
    await safe_edit(chat_id, _mid(msg), f"╔═══════════════════════╗\n    {t(uid, 'speed_t')}\n╚═══════════════════════╝\n\n{body}", kb_back(uid)); set_st(uid, state=S.MENU)

async def show_status(uid, chat_id):
    c = db(); bots = c.execute("SELECT * FROM bots WHERE uid=?", (uid,)).fetchall(); users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; c.close()
    running = sum(1 for b in bots if is_bot_running(b["id"])); storage = sum(Path(b["path"]).stat().st_size for b in bots if Path(b["path"]).exists())
    try: cpu, ram = f"{psutil.cpu_percent():.1f}", f"{psutil.virtual_memory().percent:.1f}"
    except: cpu = ram = "N/A"
    up = int(time.time() - BOT_START)
    body = t(uid, "status", bots=len(bots), running=running, users=users, storage=f"{storage/1024/1024:.2f} MB", cpu=cpu, ram=ram, uptime=f"{up//3600}h {(up%3600)//60}m")
    await send(chat_id, f"╔═══════════════════════╗\n    {t(uid, 'status_t')}\n╚═══════════════════════╝\n\n{body}", kb_back(uid)); set_st(uid, state=S.MENU)

async def show_refer(uid, chat_id):
    u = get_user(uid) or {"refer_count": 0}; body = t(uid, "refer", bot=BOT_USERNAME, uid=uid, count=u.get("refer_count", 0))
    share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    await send(chat_id, f"╔═══════════════════════╗\n    {t(uid, 'refer_t')}\n╚═══════════════════════╝\n\n{body}", ikb([[ibtn("🔗 SHARE REFER LINK", url=share_url, style="success")], [ibtn("🔙 BACK", callback_data="back:main", style="danger")]])); set_st(uid, state=S.MENU)

async def show_redeem(uid, chat_id):
    await send(chat_id, f"╔═══════════════════════╗\n    {t(uid, 'redeem_t')}\n╚═══════════════════════╝\n\n{t(uid, 'redeem_ask')}", kb_back(uid)); set_st(uid, state=S.AWAIT_REDEEM)

async def process_redeem(uid, chat_id, code):
    c = db(); row = c.execute("SELECT * FROM redeem WHERE code=? AND used_by=0", (code.strip(),)).fetchone()
    if not row: c.close(); await send(chat_id, t(uid, "redeem_bad"), kb_back(uid)); set_st(uid, state=S.MENU); return
    c.execute("UPDATE redeem SET used_by=?, used_at=? WHERE code=?", (uid, datetime.now().isoformat(), code.strip()))
    c.execute("UPDATE users SET credits = credits + ? WHERE uid=?", (row["credits"], uid)); c.commit(); c.close()
    await send(chat_id, t(uid, "redeem_ok", credits=row["credits"]), kb_main(uid)); set_st(uid, state=S.MENU)

async def show_lang(uid, chat_id): await send(chat_id, f"╔═══════════════════════╗\n    {t(uid, 'lang_t')}\n╚═══════════════════════╝", kb_lang(uid)); set_st(uid, state=S.MENU)

async def show_vip(uid, chat_id):
    text = f"╔═══════════════════════╗\n    {t(uid, 'vip_t')}\n╚═══════════════════════╝\n\n{t(uid, 'vip_body')}"
    if get_setting("support_url"): text += f"\n\n📞 <b>Contact:</b> {esc(get_setting('support_url'))}"
    await send(chat_id, text, kb_back(uid)); set_st(uid, state=S.MENU)

async def show_dev(uid, chat_id):
    await send(chat_id, f"╔═══════════════════════╗\n    👨‍💻 <b>DEVELOPER</b>\n╚═══════════════════════╝\n\n🌟 <b>ARX ANAMUL</b>\n🛠 <b>Streamly Bot Hosting</b>\n📦 <b>Version:</b> 4.2\n⚡ <b>Bot:</b> @{BOT_USERNAME}", ikb([[ibtn("💬 CONTACT DEVELOPER", url=get_setting("dev_url", "https://t.me/ARX_ANAMUL"), style="success")], [ibtn("🔙 BACK", callback_data="back:main", style="danger")]])); set_st(uid, state=S.MENU)

# ════════════════════════════════════════════════════════════
#  👑 ADMIN PANEL
# ════════════════════════════════════════════════════════════
def _count(q): c = db(); n = c.execute(q).fetchone()[0]; c.close(); return n

async def show_admin(uid, chat_id):
    if uid != ADMIN_ID: await send(chat_id, "⛔ Admin only.", kb_main(uid)); return
    text = f"╔═══════════════════════╗\n    {t(uid, 'admin_t')}\n╚═══════════════════════╝\n\n📊 <b>Quick Stats:</b>\n👥 Users: {_count('SELECT COUNT(*) FROM users')}\n🤖 Bots: {_count('SELECT COUNT(*) FROM bots')}\n⏳ Pending: {_count('SELECT COUNT(*) FROM pending WHERE approved=0')}\n⚙️ Auto-Approve: {'✅ ON' if get_setting('auto_approve','0')=='1' else '❌ OFF'}"
    await send(chat_id, text, kb_admin(uid)); set_st(uid, state=S.ADMIN_PANEL)

async def admin_users(uid, chat_id):
    c = db(); users = c.execute("SELECT * FROM users ORDER BY uid DESC LIMIT 20").fetchall(); c.close()
    await send(chat_id, f"👥 <b>ALL USERS ({len(users)})</b>\n\nTap to view:", ikb_users_list(users))

async def admin_user_detail(uid, chat_id, target_uid):
    u = get_user(target_uid)
    if not u: await send(chat_id, "❌ Not found"); return
    c = db(); bots = c.execute("SELECT * FROM bots WHERE uid=?", (target_uid,)).fetchall(); c.close()
    running = sum(1 for b in bots if is_bot_running(b["id"]))
    text = f"╔═══════════════════════╗\n    👤 <b>USER DETAILS</b>\n╚═══════════════════════╝\n\n📛 <b>Name:</b> {esc(u['first_name'])}\n🔗 <b>Username:</b> @{u['username'] or '—'}\n🆔 <b>ID:</b> <code>{target_uid}</code>\n💳 <b>Credits:</b> {u['credits']}\n💎 <b>VIP:</b> {'Yes ✅' if u['is_vip'] else 'No'}\n🚫 <b>Banned:</b> {'Yes ❌' if u['banned'] else 'No'}\n📅 <b>Joined:</b> {u['joined_at'][:10]}\n🤖 <b>Bots:</b> {len(bots)} ({running} running)\n📤 <b>Uploads:</b> {u['uploads']}\n🎁 <b>Referrals:</b> {u['refer_count']}"
    await send(chat_id, text, ikb_user_detail(u))

async def admin_stats(uid, chat_id):
    c = db(); users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; bots = c.execute("SELECT * FROM bots").fetchall(); pending = c.execute("SELECT COUNT(*) n FROM pending WHERE approved=0").fetchone()["n"]; banned = c.execute("SELECT COUNT(*) n FROM users WHERE banned=1").fetchone()["n"]; vips = c.execute("SELECT COUNT(*) n FROM users WHERE is_vip=1").fetchone()["n"]; c.close()
    running = sum(1 for b in bots if is_bot_running(b["id"]))
    try: cpu, ram, disk = f"{psutil.cpu_percent()}%", f"{psutil.virtual_memory().percent}%", f"{psutil.disk_usage('/').percent}%"
    except: cpu = ram = disk = "N/A"
    up = int(time.time() - BOT_START)
    await send(chat_id, f"╔═══════════════════════╗\n    📊 <b>STATISTICS</b>\n╚═══════════════════════╝\n\n👥 <b>Users:</b> {users}\n✅ <b>VIP:</b> {vips}\n🚫 <b>Banned:</b> {banned}\n\n🤖 <b>Bots:</b> {len(bots)}\n▶️ <b>Running:</b> {running}\n⏳ <b>Pending:</b> {pending}\n\n🖥️ <b>CPU:</b> {cpu}\n💾 <b>RAM:</b> {ram}\n💽 <b>Disk:</b> {disk}\n⏱ <b>Uptime:</b> {up//3600}h {(up%3600)//60}m", ikb([[ibtn("🔙 BACK", callback_data="back:admin", style="danger")]])); set_st(uid, state=S.ADMIN_STATS)

async def admin_all_bots(uid, chat_id):
    c = db(); bots = c.execute("SELECT * FROM bots ORDER BY id DESC LIMIT 20").fetchall(); c.close()
    await send(chat_id, f"🤖 <b>ALL HOSTED BOTS ({len(bots)})</b>\n\nTap to manage:", ikb_bots_list(bots))

async def admin_bot_detail(uid, chat_id, bot_id):
    c = db(); b = c.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone(); c.close()
    if not b: await send(chat_id, "❌ Not found"); return
    b = dict(b); u = get_user(b["uid"]) or {}; running = is_bot_running(bot_id)
    status_text = "🟢 Running" if running else ("🔴 Stopped" if b["status"]=="stopped" else "⚠️ Error/Crashed")
    text = f"╔═══════════════════════╗\n    🤖 <b>BOT #{bot_id}</b>\n╚═══════════════════════╝\n\n📦 <b>Name:</b> <code>{esc(b['name'])}</code>\n🔗 <b>Bot Username:</b> @{b.get('bot_username','—')}\n🚦 <b>Status:</b> {status_text}\n📅 <b>Created:</b> {b['created_at'][:10]}\n\n━━━ OWNER ━━━\n👤 <b>Name:</b> {esc(u.get('first_name','—'))}\n🔗 <b>Username:</b> @{u.get('username','—')}\n🆔 <b>ID:</b> <code>{b['uid']}</code>\n💳 <b>Credits:</b> {u.get('credits',0)}"
    if b["status"] == "error":
        logp = Path(b["path"]).parent / "bot.log"
        if logp.exists(): text += f"\n\n🚨 <b>ERROR LOG:</b>\n<pre>{esc(logp.read_text(errors='ignore')[-800:])}</pre>"
    await send(chat_id, text, ikb_bot_detail_admin(bot_id, b["status"]))

async def admin_pending(uid, chat_id):
    c = db(); rows = c.execute("SELECT * FROM pending WHERE approved=0 ORDER BY id DESC LIMIT 20").fetchall(); c.close()
    if not rows: await send(chat_id, "✨ No pending bots.", ikb([[ibtn("🔙 BACK", callback_data="back:admin", style="danger")]])); return
    await send(chat_id, f"⏳ <b>PENDING BOTS ({len(rows)})</b>", ikb_pending_list(rows))

async def admin_pending_detail(uid, chat_id, pid):
    c = db(); p = c.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone(); c.close()
    if not p: await send(chat_id, "❌ Not found"); return
    p = dict(p); u = get_user(p["uid"]) or {}
    text = f"╔═══════════════════════╗\n    ⏳ <b>PENDING #{pid}</b>\n╚═══════════════════════╝\n\n📦 <b>Bot:</b> <code>{esc(p['name'])}</code>\n🔗 <b>Bot Username:</b> @{p.get('bot_username','—')}\n👤 <b>Owner:</b> {esc(u.get('first_name','—'))}\n🔗 <b>Owner Username:</b> @{u.get('username','—')}\n🆔 <b>UID:</b> <code>{p['uid']}</code>\n📅 <b>Submitted:</b> {p['created_at'][:16]}"
    await send(chat_id, text, ikb_pending_detail(pid))

async def admin_approve_pending(uid, chat_id, pid):
    c = db(); row = c.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
    if not row: c.close(); await send(chat_id, "❌ Not found"); return
    p = dict(row); u = c.execute("SELECT * FROM users WHERE uid=?", (p["uid"],)).fetchone()
    
    if u["credits"] < 10 and not u["is_vip"]: c.close(); await send(chat_id, "⚠️ Insufficient credits."); return
    if not u["is_vip"]: c.execute("UPDATE users SET credits = credits - 10 WHERE uid=?", (p["uid"],))
    
    bot_uname = p.get("bot_username") or ""
    if not bot_uname: c.close(); bot_uname = await detect_bot_username(p["path"]); c = db()
        
    c.execute("INSERT INTO bots (uid, name, path, db_path, bot_username, status, created_at) VALUES (?,?,?,?,?,?,?)", (p["uid"], p["name"], p["path"], p["db_path"], bot_uname, "stopped", datetime.now().isoformat()))
    bot_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("DELETE FROM pending WHERE id=?", (pid,)); c.execute("UPDATE users SET uploads = uploads + 1 WHERE uid=?", (p["uid"],)); c.commit(); c.close()

    success, err = await start_bot_async(bot_id)
    if success:
        await send(chat_id, f"✅ Bot #{bot_id} approved & started!")
        try: await send(p["uid"], t(p["uid"], "approved", name=esc(p["name"])))
        except: pass
    else:
        await send(chat_id, f"⚠️ Bot #{bot_id} approved but failed to start!\nError:\n<code>{esc(err)}</code>")
        try: await send(p["uid"], f"✅ Bot approved, but failed to start.\nError:\n<code>{esc(err)}</code>")
        except: pass

    try: await asyncio.sleep(0.4); await show_bot_panel_user(p["uid"], p["uid"], bot_id)
    except: pass

async def admin_reject_pending(uid, chat_id, pid, reason="Not specified"):
    c = db(); row = c.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
    if row:
        p = dict(row); c.execute("DELETE FROM pending WHERE id=?", (pid,)); c.commit()
        try: shutil.rmtree(Path(p["path"]).parent, ignore_errors=True)
        except: pass
        try: await send(p["uid"], t(p["uid"], "rejected", reason=esc(reason)), kb_main(p["uid"]))
        except: pass
    c.close(); await send(chat_id, "❌ Rejected.")

async def admin_settings(uid, chat_id):
    auto = get_setting("auto_approve", "0") == "1"
    await send(chat_id, f"⚙️ <b>SETTINGS</b>\n\n📢 <b>Channel:</b> {esc(get_setting('channel_url', 'not set'))}\n👨‍💻 <b>Developer:</b> {esc(get_setting('dev_url', 'not set'))}\n📞 <b>Support:</b> {esc(get_setting('support_url', 'not set'))}\n🤖 <b>Auto-Approve:</b> {'✅ ON' if auto else '❌ OFF'}", rkb([[btn("📢 SET CHANNEL", "primary")], [btn("👨‍💻 SET DEVELOPER", "primary")], [btn("📞 SET SUPPORT", "primary")], [btn(f"🤖 AUTO-APPROVE: {'ON' if auto else 'OFF'}", "success" if auto else "danger")], [btn(t(uid, "btn_back"), "danger")]])); set_st(uid, state=S.ADMIN_SETTINGS)

async def admin_maintenance(uid, chat_id):
    c = db(); row = c.execute("SELECT value FROM settings WHERE key='maint_active'").fetchone(); c.close()
    active = row["value"] == "1" if row else False
    await send(chat_id, f"🔧 <b>MAINTENANCE</b>\n\nStatus: {'🔴 ON' if active else '🟢 OFF'}\nReason: {esc(get_setting('maint_reason', '—'))}", rkb([[btn("🔴 TURN ON", "danger")], [btn("🟢 TURN OFF", "success")], [btn(t(uid, "btn_back"), "danger")]])); set_st(uid, state=S.ADMIN_MAINT)

async def admin_send_this_db(uid, chat_id):
    msg = await send(chat_id, "💾 <b>Preparing main DB...</b>"); mid = _mid(msg)
    try:
        c = db(); c.execute("PRAGMA wal_checkpoint(FULL)"); c.close()
        zp = BASE_DIR / f"streamly_main_db_{int(time.time())}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(DB_PATH, "streamly.db")
            for ext in ["-wal", "-shm"]:
                wf = Path(str(DB_PATH) + ext)
                if wf.exists(): z.write(wf, f"streamly.db{ext}")
        
        s = await _sess()
        with open(zp, "rb") as f:
            data = aiohttp.FormData(); data.add_field("chat_id", str(chat_id)); data.add_field("document", f, filename=zp.name)
            data.add_field("caption", f"💾 <b>MAIN DB</b>\n👥 Users: {_count('SELECT COUNT(*) FROM users')}\n🤖 Bots: {_count('SELECT COUNT(*) FROM bots')}")
            await s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data=data)
        zp.unlink(); await delete_msg(chat_id, mid)
    except Exception as e: await safe_edit(chat_id, mid, f"❌ Failed: {esc(str(e))}")

async def admin_send_all_db(uid, chat_id):
    await send(chat_id, "📦 Sending all bot DB files to owners...")
    c = db(); bots = c.execute("SELECT * FROM bots").fetchall(); c.close()
    sent = fail = 0
    for b in bots:
        try:
            bp = Path(b["path"])
            if not bp.exists(): continue
            zp = bp.parent / f"{b['name']}_db.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
                for f in bp.parent.iterdir():
                    if f.is_file() and f.suffix in {".db", ".sqlite", ".sqlite3", ".json"}: z.write(f, f.name)
            if zp.stat().st_size > 0:
                s = await _sess()
                with open(zp, "rb") as f:
                    data = aiohttp.FormData(); data.add_field("chat_id", str(b["uid"])); data.add_field("document", f, filename=zp.name); data.add_field("caption", f"💾 <b>DB Backup: {esc(b['name'])}</b>")
                    r = await s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data=data)
                    if r.status == 200: sent += 1
                    else: fail += 1
            zp.unlink()
        except: fail += 1
    await send(chat_id, f"✅ Sent: {sent}\n❌ Failed: {fail}", kb_admin(uid))

async def admin_broadcast_start(uid, chat_id): await send(chat_id, "📢 Send the message to broadcast:", kb_back(uid)); set_st(uid, state=S.AWAIT_BCAST)

async def do_broadcast(message: Message):
    c = db(); users = c.execute("SELECT uid FROM users WHERE banned=0").fetchall(); c.close()
    ok = fail = 0
    for row in users:
        try:
            r = await api("copyMessage", {"chat_id": row["uid"], "from_chat_id": message.chat.id, "message_id": message.message_id})
            if r.get("ok"): ok += 1
            else: fail += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await send(ADMIN_ID, f"✅ Broadcast done.\n✅ OK: {ok}\n❌ Failed: {fail}", kb_admin(ADMIN_ID)); set_st(ADMIN_ID, state=S.ADMIN_PANEL)

async def admin_redeem_start(uid, chat_id): await send(chat_id, "🎟️ Send credits amount for new code:\n\n<i>Example: 10</i>", kb_back(uid)); set_st(uid, state=S.AWAIT_REDEEM_CREDITS)

async def admin_create_redeem(uid, chat_id, credits_str):
    try: credits = int(credits_str)
    except: await send(uid, "❌ Invalid number", kb_admin(uid)); set_st(uid, state=S.ADMIN_PANEL); return
    code = "STREAM-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    c = db(); c.execute("INSERT INTO redeem (code, credits, created_at) VALUES (?,?,?)", (code, credits, datetime.now().isoformat())); c.commit(); c.close()
    await send(chat_id, f"✅ <b>CODE CREATED</b>\n\n🎟️ Code: <code>{code}</code>\n💳 Credits: {credits}", kb_admin(uid)); set_st(uid, state=S.ADMIN_PANEL)

async def _send_db_zip(chat_id, bot_row):
    bp = Path(bot_row["path"]).parent; zp = bp / f"{bot_row['name']}_db.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in bp.iterdir():
            if f.is_file() and f.suffix in {".db", ".sqlite", ".sqlite3", ".json"}: z.write(f, f.name)
    if zp.exists() and zp.stat().st_size > 0:
        s = await _sess()
        with open(zp, "rb") as f:
            data = aiohttp.FormData(); data.add_field("chat_id", str(chat_id)); data.add_field("document", f, filename=zp.name)
            await s.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data=data)
        zp.unlink(); await send(chat_id, "✅ DB sent.")
    else: await send(chat_id, "No DB files found.")

# ════════════════════════════════════════════════════════════
#  🎯 CALLBACKS
# ════════════════════════════════════════════════════════════
@dp.callback_query()
async def on_cb(cb: CallbackQuery):
    uid = cb.from_user.id; data = cb.data or ""; is_admin = uid == ADMIN_ID
    try: await answer_cb(cb.id)
    except: pass

    try:
        if data == "back:main": await show_main_menu(uid, uid); return
        if data == "back:admin":
            if not is_admin: return
            await show_admin(uid, uid); return
        if data == "back:users":
            if not is_admin: return
            await admin_users(uid, uid); return
        if data == "back:bots":
            if not is_admin: return
            await admin_all_bots(uid, uid); return
        if data == "back:pending":
            if not is_admin: return
            await admin_pending(uid, uid); return
        if data == "back:mybots": await show_my_bots(uid, uid); return

        if data.startswith("u:") and is_admin: await admin_user_detail(uid, uid, int(data[2:])); return
        if data.startswith("ban:") and is_admin:
            set_st(uid, state=S.AWAIT_BAN_REASON, target=int(data[4:])); await send(uid, f"📝 Send ban reason for <code>{data[4:]}</code>:", kb_back(uid)); return
        if data.startswith("unban:") and is_admin:
            target = int(data[6:]); c = db(); c.execute("UPDATE users SET banned=0 WHERE uid=?", (target,)); c.commit(); c.close()
            try: await send(target, "✅ You have been unbanned!", kb_main(target))
            except: pass
            await send(uid, "✅ User unbanned."); await admin_user_detail(uid, uid, target); return
        if data.startswith("vip:") and is_admin:
            target = int(data[4:]); c = db(); c.execute("UPDATE users SET is_vip=1 WHERE uid=?", (target,)); c.commit(); c.close()
            try: await send(target, "💎 You are now VIP!", kb_main(target))
            except: pass
            await send(uid, "✅ User is now VIP."); await admin_user_detail(uid, uid, target); return
        if data.startswith("cred:") and is_admin:
            set_st(uid, state=S.AWAIT_ADD_CREDITS, target=int(data[5:])); await send(uid, "💳 Send credits amount to add:", kb_back(uid)); return

        if data.startswith("b:") and is_admin: await admin_bot_detail(uid, uid, int(data[2:])); return
        if data.startswith("on:") and is_admin:
            bid = int(data[3:]); success, err = await start_bot_async(bid)
            if not success: await send(uid, f"⚠️ Failed to start:\n<code>{esc(err)}</code>")
            await admin_bot_detail(uid, uid, bid); return
        if data.startswith("off:") and is_admin:
            bid = int(data[4:]); stop_bot(bid); await send(uid, "⏹ Bot stopped."); await admin_bot_detail(uid, uid, bid); return
        if data.startswith("log:") and is_admin:
            bid = int(data[4:]); logp = Path(BOT_PROCS[bid]["log_path"]) if bid in BOT_PROCS else Path(".")
            if logp.exists(): await send(uid, f"📜 <b>LOG #{bid}</b>\n\n<pre>{esc(logp.read_text(errors='ignore')[-3000:])}</pre>", ikb([[ibtn("🔙 BACK", callback_data=f"b:{bid}", style="danger")]]))
            else: await send(uid, "No log available.")
            return
        if data.startswith("db:") and is_admin:
            bid = int(data[3:]); c = db(); b = c.execute("SELECT * FROM bots WHERE id=?", (bid,)).fetchone(); c.close()
            if b: await _send_db_zip(uid, dict(b))
            return
        if data.startswith("del:") and is_admin:
            bid = int(data[4:]); stop_bot(bid); c = db(); b = c.execute("SELECT * FROM bots WHERE id=?", (bid,)).fetchone()
            if b: shutil.rmtree(Path(b["path"]).parent, ignore_errors=True); c.execute("DELETE FROM bots WHERE id=?", (bid,)); c.commit()
            c.close(); await send(uid, "🗑️ Bot deleted."); await admin_all_bots(uid, uid); return

        if data.startswith("p:") and is_admin: await admin_pending_detail(uid, uid, int(data[2:])); return
        if data.startswith("ap:") and is_admin: await admin_approve_pending(uid, uid, int(data[3:])); await admin_pending(uid, uid); return
        if data.startswith("rp:") and is_admin:
            set_st(uid, state=S.AWAIT_REJECT_REASON, pending_id=int(data[3:])); await send(uid, "📝 Send rejection reason:", kb_back(uid)); return

        if data.startswith("mb:"): await show_bot_panel_user(uid, uid, int(data[3:])); return
        if data.startswith("uon:"):
            bid = int(data[4:]); success, err = await start_bot_async(bid)
            if not success: await send(uid, f"⚠️ Failed to start:\n<code>{esc(err)}</code>")
            await show_bot_panel_user(uid, uid, bid); return
        if data.startswith("uoff:"):
            bid = int(data[5:]); stop_bot(bid); await show_bot_panel_user(uid, uid, bid); return
        if data.startswith("ulog:"):
            bid = int(data[5:]); logp = Path(BOT_PROCS[bid]["log_path"]) if bid in BOT_PROCS else Path(".")
            if logp.exists(): await send(uid, f"📜 <b>LOG</b>\n\n<pre>{esc(logp.read_text(errors='ignore')[-3000:])}</pre>", ikb([[ibtn("🔙 BACK", callback_data=f"mb:{bid}", style="danger")]]))
            else: await send(uid, "No log available.")
            return
        if data.startswith("udb:"):
            bid = int(data[4:]); c = db(); b = c.execute("SELECT * FROM bots WHERE id=?", (bid,)).fetchone(); c.close()
            if b and b["uid"] == uid: await _send_db_zip(uid, dict(b))
            return
        if data.startswith("upkg:"):
            set_st(uid, state=S.INSTALL_PKG, bot_id=int(data[5:])); await send(uid, "📦 Send packages to install:", kb_back(uid)); return
        if data.startswith("udel:"):
            bid = int(data[5:]); c = db(); b = c.execute("SELECT * FROM bots WHERE id=? AND uid=?", (bid, uid)).fetchone()
            if b: stop_bot(bid); shutil.rmtree(Path(b["path"]).parent, ignore_errors=True); c.execute("DELETE FROM bots WHERE id=?", (bid,)); c.commit()
            c.close(); await send(uid, "🗑️ Bot deleted."); await show_my_bots(uid, uid); return
    except Exception as e: log.error(f"Callback error: {e}"); await send(uid, f"⚠️ Error: {esc(str(e))}")

# ════════════════════════════════════════════════════════════
#  🎯 MESSAGES
# ════════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def on_start(m: Message):
    uid = m.from_user.id
    if m.text and " " in m.text:
        arg = m.text.split(" ", 1)[1]
        if arg.startswith("ref_"):
            try:
                ref = int(arg[4:])
                if not get_user(uid): create_user(uid, m.from_user.username, m.from_user.first_name, ref)
            except: pass
    if not get_user(uid): create_user(uid, m.from_user.username, m.from_user.first_name)
    u = get_user(uid)
    if u and u["banned"]: await send(uid, f"🚫 You are banned.\n\nReason: {esc(u['ban_reason'])}"); return
    c = db(); row = c.execute("SELECT value FROM settings WHERE key='maint_active'").fetchone(); c.close()
    if row and row["value"] == "1" and uid != ADMIN_ID: await send(uid, t(uid, "maint_notice", reason=esc(get_setting("maint_reason", "—")))); return
    await show_main_menu(uid, uid)

@dp.message(Command("admin"))
async def on_admin(m: Message):
    if m.from_user.id != ADMIN_ID: return
    await show_admin(m.from_user.id, m.from_user.id)

@dp.message()
async def router(m: Message):
    try: await _router(m)
    except Exception as e: log.error(f"Router err: {e}"); await send(m.from_user.id, f"⚠️ <b>Error:</b> {esc(str(e))}", kb_main(m.from_user.id))

async def _router(m: Message):
    uid = m.from_user.id; text = (m.text or "").strip()
    if not text and not m.document: return
    if not get_user(uid): create_user(uid, m.from_user.username, m.from_user.first_name)

    c = db(); row = c.execute("SELECT value FROM settings WHERE key='maint_active'").fetchone(); c.close()
    if row and row["value"] == "1" and uid != ADMIN_ID: await send(uid, t(uid, "maint_notice", reason=esc(get_setting("maint_reason", "—")))); return

    cur = st(uid); state = cur.get("state", S.MENU)

    if state in (S.AWAIT_PKG, S.AWAIT_DB) and is_back(text, uid):
        cur_dir = cur.get("bot_dir"); set_st(uid, state=S.MENU)
        if cur_dir: shutil.rmtree(cur_dir, ignore_errors=True)
        await send(uid, t(uid, "upload_cancelled"), kb_main(uid)); return

    if state == S.AWAIT_FILE and m.document: await process_uploaded_file(uid, uid, m); return
    if state == S.AWAIT_PKG and text:
        if _norm(text) == "skip":
            c2 = st(uid); await send(uid, t(uid, "ask_db"), kb_pkg(uid)); set_st(uid, state=S.AWAIT_DB, path=c2["path"], bot_dir=c2["bot_dir"], name=c2["name"]); return
        await process_packages(uid, uid, text); return
    if state == S.AWAIT_DB:
        if _norm(text) == "skip": await process_db(uid, uid, ""); return
        if m.document: await process_db(uid, uid, m); return
        return
    if state == S.AWAIT_REDEEM and text: await process_redeem(uid, uid, text); return
    if state == S.INSTALL_PKG and text:
        names = text.split(); msg = await send(uid, f"📦 Installing {len(names)} packages...")
        ok, fail = [], []
        for n in names:
            try: subprocess.run([sys.executable, "-m", "pip", "install", n, "--quiet"], capture_output=True, timeout=120); ok.append(n)
            except: fail.append(n)
        await safe_edit(uid, _mid(msg), f"✅ OK: {', '.join(ok)}\n❌ Fail: {', '.join(fail)}", kb_main(uid)); set_st(uid, state=S.MENU); return

    if uid == ADMIN_ID:
        if state == S.AWAIT_BCAST: await do_broadcast(m); return
        if state == S.AWAIT_REDEEM_CREDITS and text: await admin_create_redeem(uid, uid, text); return
        if state == S.AWAIT_MAINT_REASON and text:
            save_setting("maint_active", "1"); save_setting("maint_reason", text)
            await send(uid, t(uid, "maint_on", reason=esc(text)), kb_admin(uid)); set_st(uid, state=S.ADMIN_PANEL); return
        if state == S.AWAIT_CHANNEL and text: save_setting("channel_url", text); await send(uid, "✅ Channel set.", kb_admin(uid)); set_st(uid, state=S.ADMIN_SETTINGS); return
        if state == S.AWAIT_DEV and text: save_setting("dev_url", text); await send(uid, "✅ Dev URL set.", kb_admin(uid)); set_st(uid, state=S.ADMIN_SETTINGS); return
        if state == S.AWAIT_SUPPORT and text: save_setting("support_url", text); await send(uid, "✅ Support URL set.", kb_admin(uid)); set_st(uid, state=S.ADMIN_SETTINGS); return
        if state == S.AWAIT_REJECT_REASON and text: await admin_reject_pending(uid, uid, cur.get("pending_id"), text); await admin_pending(uid, uid); return
        if state == S.AWAIT_BAN_REASON and text: set_st(uid, state=S.AWAIT_BAN_URL, target=cur.get("target"), reason=text); await send(uid, "🔗 Now send support URL:", kb_back(uid)); return
        if state == S.AWAIT_BAN_URL and text:
            target, reason = cur["target"], cur["reason"]; c = db(); c.execute("UPDATE users SET banned=1, ban_reason=?, support_url=? WHERE uid=?", (reason, text, target)); c.commit(); c.close()
            try: await send(target, f"🚫 <b>Banned</b>\n\nReason: {esc(reason)}\nSupport: {esc(text)}")
            except: pass
            await send(uid, "✅ User banned."); await admin_user_detail(uid, uid, target); return
        if state == S.AWAIT_ADD_CREDITS and text:
            try:
                amt = int(text); target = cur.get("target"); c = db(); c.execute("UPDATE users SET credits = credits + ? WHERE uid=?", (amt, target)); c.commit(); c.close()
                await send(uid, f"✅ Added {amt} credits."); await admin_user_detail(uid, uid, target); return
            except: await send(uid, "❌ Invalid number", kb_back(uid)); return

    if is_back(text, uid):
        if uid == ADMIN_ID and state and state.startswith("admin_") and state != S.ADMIN_PANEL: await show_admin(uid, uid); return
        await show_main_menu(uid, uid); return

    key = find_btn(text, uid)
    if key == "btn_upload": await show_upload(uid, uid); return
    if key == "btn_profile": await show_profile(uid, uid); return
    if key == "btn_mybot": await show_my_bots(uid, uid); return
    if key == "btn_speed": await show_speed(uid, uid); return
    if key == "btn_status": await show_status(uid, uid); return
    if key == "btn_channel":
        channel = get_setting("channel_url", "")
        if channel: await send(uid, "📢 <b>UPDATE CHANNEL</b>", ikb([[ibtn("📢 JOIN CHANNEL", url=channel, style="success")], [ibtn("🔙 BACK", callback_data="back:main", style="danger")]]))
        else: await send(uid, "⚠️ Channel not set yet.", kb_back(uid))
        set_st(uid, state=S.MENU); return
    if key == "btn_refer": await show_refer(uid, uid); return
    if key == "btn_redeem": await show_redeem(uid, uid); return
    if key == "btn_lang": await show_lang(uid, uid); return
    if key == "btn_vip": await show_vip(uid, uid); return
    if key == "btn_dev": await show_dev(uid, uid); return

    if _norm(text) == _norm("🇧🇩 বাংলা"): USER_LANG[uid] = "bn"; await send(uid, t(uid, "lang_ok"), kb_main(uid)); set_st(uid, state=S.MENU); return
    if _norm(text) == _norm("🇬🇧 ENGLISH"): USER_LANG[uid] = "en"; await send(uid, t(uid, "lang_ok"), kb_main(uid)); set_st(uid, state=S.MENU); return

    if uid == ADMIN_ID:
        if key == "a_users": await admin_users(uid, uid); return
        if key == "a_stats": await admin_stats(uid, uid); return
        if key == "a_bcast": await admin_broadcast_start(uid, uid); return
        if key == "a_thisdb": await admin_send_this_db(uid, uid); return
        if key == "a_redeem": await admin_redeem_start(uid, uid); return
        if key == "a_bots": await admin_all_bots(uid, uid); return
        if key == "a_pending": await admin_pending(uid, uid); return
        if key == "a_settings": await admin_settings(uid, uid); return
        if key == "a_maint": await admin_maintenance(uid, uid); return
        if key == "a_sendall": await admin_send_all_db(uid, uid); return

        if state == S.ADMIN_SETTINGS:
            if text == "📢 SET CHANNEL": set_st(uid, state=S.AWAIT_CHANNEL); await send(uid, "Send channel URL:", kb_back(uid)); return
            if text == "👨‍💻 SET DEVELOPER": set_st(uid, state=S.AWAIT_DEV); await send(uid, "Send developer URL:", kb_back(uid)); return
            if text == "📞 SET SUPPORT": set_st(uid, state=S.AWAIT_SUPPORT); await send(uid, "Send support URL:", kb_back(uid)); return
            if text.startswith("🤖 AUTO-APPROVE"):
                cur_val = get_setting("auto_approve", "0"); save_setting("auto_approve", "0" if cur_val == "1" else "1"); await admin_settings(uid, uid); return

        if state == S.ADMIN_MAINT:
            if text == "🔴 TURN ON": set_st(uid, state=S.AWAIT_MAINT_REASON); await send(uid, "Send reason:", kb_back(uid)); return
            if text == "🟢 TURN OFF": save_setting("maint_active", "0"); await send(uid, t(uid, "maint_off"), kb_admin(uid)); return

    await show_main_menu(uid, uid)

# ════════════════════════════════════════════════════════════
#  🌐 HEALTH SERVER (Render)
# ════════════════════════════════════════════════════════════
async def start_health_server():
    app = web.Application()
    async def health(request): return web.json_response({"ok": True, "uptime": int(time.time() - BOT_START)})
    app.router.add_get("/", health); app.router.add_get("/health", health)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start(); log.info("Health server running")

# ════════════════════════════════════════════════════════════
#  🚀 MAIN
# ════════════════════════════════════════════════════════════
async def main():
    log.info("Starting Streamly v4.2...")
    init_db()
    c = db()
    for row in c.execute("SELECT key, value FROM settings").fetchall(): SETTINGS[row["key"]] = row["value"]
    running = c.execute("SELECT * FROM bots WHERE status='running'").fetchall(); c.close()
    for b in running: await start_bot_async(b["id"])

    await start_health_server()
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Bot online.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down...")
        for bid in list(BOT_PROCS.keys()): stop_bot(bid)