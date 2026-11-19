# -*- coding: utf-8 -*-
import telebot
from telebot import types
import json
import os
import html
import time
from datetime import datetime, timedelta
import random
import re
import asyncio
import requests
from threading import Thread

# ========= ستايل ألوان الأزرار (Bot API 9.4) =========
# فعّل/عطّل التلوين التلقائي لكل الأزرار
BUTTON_AUTO_STYLE_ENABLED = True

# اللون الافتراضي لأي زر ما تنطبق عليه أي كلمة مفتاحية (خليه None عشان يرجع للشكل الافتراضي الشفاف)
# القيم المسموحة: "primary" (أزرق) / "success" (أخضر) / "danger" (أحمر) / None
BUTTON_DEFAULT_STYLE = None

# كلمات مفتاحية: أي زر نصه أو الـ callback_data تبعه يحتوي على إحدى هذي الكلمات ياخذ اللون المقابل
# رتب القوائم حسب الأولوية: danger يفحص أول، بعدين success، بعدين primary
BUTTON_STYLE_KEYWORDS = {
    "danger": [
        "حذف", "الغاء", "إلغاء", "طرد", "حظر", "بان", "تصفير", "مسح",
        "إغلاق", "اغلاق", "خلع", "طلاق", "مطلق", "close_panel", "_del", "_del_",
        "ban", "delete", "reset", "clear", "cancel", "reject", "conf_del",
    ],
    "success": [
        "تأكيد", "موافقة", "قبول", "شراء", "تفعيل", "فك الحظر", "نعم",
        "زواج", "تزويج", "قبل", "إضافة", "اضف", "أضف", "add", "confirm",
        "accept", "buy", "activate", "unban", "approve",
    ],
    "primary": [
        "رجوع", "التالي", "السابق", "back", "next", "prev", "توب", "top",
        "احصائيات", "إحصائيات", "معلومات", "تعليمات", "قائمة", "menu",
    ],
}

# نبني قائمة مسطّحة (كلمة، ستايل) ونرتبها حسب طول الكلمة تنازلياً
# عشان عبارة مثل "فك الحظر" (طويلة/أدق) تتفحص قبل كلمة "حظر" المفردة
_FLAT_STYLE_KEYWORDS = sorted(
    ((kw, style_name) for style_name, kws in BUTTON_STYLE_KEYWORDS.items() for kw in kws),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

# اللون الافتراضي: بدل ما يضل "شفاف" (None)، الأزرار اللي ما تطابقت مع أي كلمة مفتاحية
# تاخذ لون بالتناوب كل زرين (زرين أزرق، زرين أخضر، زرين أزرق...) عشان ولا زر يضل بدون لون
FALLBACK_STYLE_PAIR_CYCLE = ["primary", "success"]  # غيّر هذي القائمة لو تبي ألوان/ترتيب مختلف

_fallback_counter = 0

def _next_fallback_style():
    global _fallback_counter
    style = FALLBACK_STYLE_PAIR_CYCLE[(_fallback_counter // 2) % len(FALLBACK_STYLE_PAIR_CYCLE)]
    _fallback_counter += 1
    return style

def _auto_button_style(text, callback_data):
    """يحدد الستايل المناسب للزر تلقائياً بناءً على النص أو الـ callback_data."""
    if not BUTTON_AUTO_STYLE_ENABLED:
        return None
    haystack = f"{text or ''} {callback_data or ''}"
    for kw, style_name in _FLAT_STYLE_KEYWORDS:
        if kw in haystack:
            return style_name
    # ما تطابق مع أي كلمة مفتاحية -> ياخذ لون بالتناوب (زرين زرين) بدل ما يضل شفاف
    return _next_fallback_style()

_OriginalInlineKeyboardButton = types.InlineKeyboardButton
_OriginalKeyboardButton = types.KeyboardButton

class InlineKeyboardButton(_OriginalInlineKeyboardButton):
    def __init__(self, text, *args, style=None, **kwargs):
        if style is None:
            style = _auto_button_style(text, kwargs.get("callback_data"))
        super().__init__(text, *args, style=style, **kwargs)

class KeyboardButton(_OriginalKeyboardButton):
    def __init__(self, text, *args, style=None, **kwargs):
        if style is None:
            style = _auto_button_style(text, None)
        super().__init__(text, *args, style=style, **kwargs)

# نستبدل الكلاسات الأصلية بالنسخ المطوّرة، فكل استخدام types.InlineKeyboardButton / types.KeyboardButton
# بباقي الملف بياخذ اللون تلقائياً بدون ما نعدل كل زر يدوياً
types.InlineKeyboardButton = InlineKeyboardButton
types.KeyboardButton = KeyboardButton
# ========= نهاية إعدادات ستايل الأزرار =========

# ========= إعدادات أساسية =========
BOT_TOKEN = "8681702594:AAF1yjc_uz9SmWH5509An4vtacUnfrjDIBc"
DATA_FILE = "data.json"
BOT_OWNER_ID = 7847452449  # إيدي مالك البوت

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========= يوزر واسم البوت (يستخدم لبناء رابط فتح البوت بزر شفاف / رابط أزرق) =========
try:
    _me = bot.get_me()
    BOT_USERNAME = _me.username
    BOT_DISPLAY_NAME = _me.first_name or _me.username or "ايتو"
    BOT_ID = _me.id
except Exception:
    BOT_USERNAME = None
    BOT_DISPLAY_NAME = "ايتو"
    BOT_ID = None
BOT_DEEPLINK = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me/ri5xbot"

# ========= أدوات تخزين =========
def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_db():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=2)

DB = load_db()

# ========= إصلاح تلقائي لأي بيانات تلوثت بسبب علة قديمة بزر "تصفير الكل" =========
# العلة القديمة كانت تحقن مفاتيح messages/marriages/divorces داخل قواميس عامة
# زي global_divorces و global_khulaa و global_golden و gold_ranking، فتصير
# قيمها dict بدل رقم، وأي فرز (sorted) عليها يطيح بخطأ ويعلّق الزر بتلجرام.
# هذا الكود ينظفها تلقائياً بأول تشغيل بدون ما تحتاج تحذف data.json يدوياً.
def _sanitize_ranking_dict(key):
    d = DB.get(key)
    if isinstance(d, dict):
        changed = False
        for junk_key in ("messages", "marriages", "divorces"):
            if junk_key in d:
                del d[junk_key]
                changed = True
        for k in list(d.keys()):
            if not isinstance(d[k], (int, float)):
                del d[k]
                changed = True
        return changed
    return False

_needs_save = False
for _rank_key in ("global_divorces", "global_khulaa", "global_golden", "gold_ranking"):
    if _sanitize_ranking_dict(_rank_key):
        _needs_save = True
if _needs_save:
    save_db()
    print("🔧 تم إصلاح بيانات تالفة تلقائياً بـ data.json (توب المطلقات/المخلوعين/الذهبي).")

# ========= دمج بوت اليوتيوب (يوت / بحث) — تشتغل بالقروبات المفعّلة فقط =========
import yt_dlp
from youtube_search import YoutubeSearch
try:
    from pyrogram import Client as PyroClient
    from pyrogram.types import InlineKeyboardMarkup as PyroInlineKeyboardMarkup, InlineKeyboardButton as PyroInlineKeyboardButton
    PYROGRAM_AVAILABLE = True
except Exception as _e:
    PYROGRAM_AVAILABLE = False
    print("⚠️ مكتبة pyrogram غير مثبتة — التحميل سيقتصر على الملفات الصغيرة (أقل من 49 ميجا).")

YT_API_ID = 20938788
YT_API_HASH = "f6e8b15641bbf5f30877f965e4be56c0"
YT_DOWNLOAD_DIR = "yt_downloads"
YT_MAX_TELEBOT_SIZE = 49 * 1024 * 1024  # حد الرفع عبر telebot العادي
YT_COOKIES_FILE = "cookies.txt"  # حط ملف الكوكيز بهذا الاسم بنفس مجلد main.py


def yt_cookie_opts():
    """يرجع dict فيه cookiefile إذا الملف موجود، وإلا يرجع فاضي."""
    if os.path.exists(YT_COOKIES_FILE):
        return {"cookiefile": YT_COOKIES_FILE}
    return {}

if not os.path.exists(YT_DOWNLOAD_DIR):
    os.makedirs(YT_DOWNLOAD_DIR)

yt_pyro_app = None
yt_loop = None

if PYROGRAM_AVAILABLE:
    yt_pyro_app = PyroClient(
        "nawal_yt_session",
        api_id=YT_API_ID,
        api_hash=YT_API_HASH,
        bot_token=BOT_TOKEN,
        no_updates=True,   # يشتغل بس للإرسال — ما يستقبل تحديثات حتى ما يصير تعارض مع telebot
        in_memory=True
    )

    def _start_yt_loop():
        global yt_loop
        yt_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(yt_loop)
        try:
            yt_loop.run_until_complete(yt_pyro_app.start())
            print("✅ عميل اليوتيوب (Pyrogram) اشتغل بنجاح — دعم الملفات الكبيرة مفعّل.")
        except Exception as e:
            print(f"⚠️ فشل تشغيل عميل اليوتيوب: {e}")
        yt_loop.run_forever()

    Thread(target=_start_yt_loop, daemon=True).start()
    time.sleep(2)  # مهلة بسيطة لضمان جهوزية العميل قبل أول استخدام

def yt_run_coro(coro):
    """تشغيل كوروتين Pyrogram من كود telebot المتزامن (لإرسال الملفات الكبيرة)"""
    if not PYROGRAM_AVAILABLE or yt_loop is None:
        raise RuntimeError("عميل اليوتيوب غير متاح")
    future = asyncio.run_coroutine_threadsafe(coro, yt_loop)
    return future.result(timeout=300)

# ========= قاعدة بيانات وصلاحيات اليوتيوب (على مستوى القروب) =========
def ensure_yt_groups():
    if "yt_activated_groups" not in DB:
        DB["yt_activated_groups"] = []
    return DB["yt_activated_groups"]

def is_yt_group_active(chat_id):
    return chat_id in ensure_yt_groups()

def is_yt_maintenance():
    return DB.get("yt_maintenance", False)

def format_yt_duration(seconds):
    """يحول المدة من ثواني إلى صيغة MM:SS (أو HH:MM:SS للفيديوهات الطويلة)"""
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "00:00"
    if seconds < 0:
        seconds = 0
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def yt_build_caption(info):
    """يبني كابشن الميديا: العنوان + المدة الحقيقية بصيغة 00:00 (نص عادي، غير قابل للضغط
    لأن تلجرام ما يخلي نص بالكابشن يشغّل الملف المرفق — التشغيل يصير من مشغّل الصوت/الفيديو
    نفسه اللي يحطه تلجرام تلقائياً) + توقيع ايتو كرابط أزرق يفتح البوت"""
    title = info.get("title", "")
    duration = info.get("duration", 0)
    dur_txt = format_yt_duration(duration)
    return (
        f"🎬 <b>{title}</b>\n"
        f"⏱ {dur_txt}\n\n"
        f"✅ بواسطة <a href='{BOT_DEEPLINK}'>ايتو</a> 🎵"
    )

def yt_build_open_bot_markup():
    """زر شفاف باسم البوت (وليس يوزره) يفتح البوت عند الضغط عليه (للإرسال عبر telebot)"""
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton(f"🎵 {BOT_DISPLAY_NAME}", url=BOT_DEEPLINK))
    return m

def yt_build_open_bot_markup_pyro():
    """نفس الزر لكن بصيغة Pyrogram (تستخدم مع الملفات الكبيرة)"""
    if not PYROGRAM_AVAILABLE:
        return None
    return PyroInlineKeyboardMarkup([[PyroInlineKeyboardButton(f"🎵 {BOT_DISPLAY_NAME}", url=BOT_DEEPLINK)]])

def yt_send_result_file(chat_id, file_path, ftype, title, caption):
    """يرسل الملف عبر telebot عادي، أو عبر Pyrogram إذا كان الحجم أكبر من حد telebot
    + يرفق زر شفاف باسم البوت يفتح البوت عند الضغط.
    يرجع كائن الرسالة المُرسلة عند الإرسال عبر telebot (نحتاجه لحفظ file_id بالكاش)،
    أو None عند الإرسال عبر Pyrogram (ملفات كبيرة لا تُخزّن بالكاش)."""
    size = os.path.getsize(file_path)
    if size <= YT_MAX_TELEBOT_SIZE:
        markup = yt_build_open_bot_markup()
        with open(file_path, "rb") as f:
            if ftype == "audio":
                sent = bot.send_audio(chat_id, f, title=title, caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                sent = bot.send_video(chat_id, f, caption=caption, parse_mode="HTML", reply_markup=markup)
        return sent
    else:
        if not PYROGRAM_AVAILABLE:
            raise RuntimeError("الملف أكبر من 49 ميجا ومكتبة pyrogram غير متوفرة لإرساله.")
        pyro_markup = yt_build_open_bot_markup_pyro()
        if ftype == "audio":
            yt_run_coro(yt_pyro_app.send_audio(chat_id, file_path, title=title, caption=caption, reply_markup=pyro_markup))
        else:
            yt_run_coro(yt_pyro_app.send_video(chat_id, file_path, caption=caption, reply_markup=pyro_markup))
        return None


def yt_extract_file_id(sent_message, ftype):
    """يستخرج file_id من الرسالة المُرسلة عبر telebot، حتى نقدر نعيد إرسال نفس الملف
    مستقبلاً بدون ما نحمّله من يوتيوب مرة ثانية (أسرع + يوفر مساحة)."""
    if sent_message is None:
        return None
    try:
        if ftype == "audio" and getattr(sent_message, "audio", None):
            return sent_message.audio.file_id
        if ftype != "audio" and getattr(sent_message, "video", None):
            return sent_message.video.file_id
    except Exception:
        pass
    return None


# ========= كاش اليوتيوب: يحفظ نتيجة كل بحث حتى ما يعيد التحميل مرة ثانية =========
# yt_query_cache: نص البحث (بعد التطبيع) -> id الفيديو على يوتيوب
# yt_file_cache : "id الفيديو_نوع الملف" -> file_id بتلجرام + العنوان + المدة
# بهذا الشكل: لو نفس الفيديو انطلب بأكثر من صيغة بحث، ما ينحفظ الملف الا مرة وحدة
# (توفير مساحة)، ولو نفس البحث تكرر، يرجع يرسل مباشرة بدون تحميل (سرعة).
def ensure_yt_query_cache():
    if "yt_query_cache" not in DB:
        DB["yt_query_cache"] = {}
    return DB["yt_query_cache"]

def ensure_yt_file_cache():
    if "yt_file_cache" not in DB:
        DB["yt_file_cache"] = {}
    return DB["yt_file_cache"]

def yt_normalize_query(q):
    return " ".join((q or "").strip().lower().split())

def yt_file_cache_key(video_id, ftype):
    return f"{video_id}_{ftype}"

def yt_get_cached_file(video_id, ftype):
    return ensure_yt_file_cache().get(yt_file_cache_key(video_id, ftype))

def yt_store_cached_file(video_id, ftype, file_id, title, duration):
    cache = ensure_yt_file_cache()
    cache[yt_file_cache_key(video_id, ftype)] = {
        "file_id": file_id,
        "title": title,
        "duration": duration,
    }
    save_db()

def yt_send_cached(chat_id, cached_entry, ftype):
    """يرسل ملف محفوظ بالكاش مباشرة (بدون تحميل) بنفس شكل الكابشن والزر."""
    caption = yt_build_caption({"title": cached_entry.get("title", ""), "duration": cached_entry.get("duration", 0)})
    markup = yt_build_open_bot_markup()
    if ftype == "audio":
        bot.send_audio(chat_id, cached_entry["file_id"], caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        bot.send_video(chat_id, cached_entry["file_id"], caption=caption, parse_mode="HTML", reply_markup=markup)

# ========= دوال مساعدة للتوب (يجب تعريفها مبكراً) =========
def safe_name_for_top(user_obj):
    """يرجع الاسم الظاهر فقط — بدون يوزر. إذا ما يوجد اسم مناسب يرجع None لاستبعاد المستخدم."""
    try:
        name = (user_obj.first_name or "").strip()
        if user_obj.last_name:
            name += " " + user_obj.last_name.strip()
        name = name.strip()
        if not name or name.startswith("@"):
            return None
        # نعمل escape لأي رموز HTML موجودة بالاسم (مثل < > &) حتى ما تكسر رسائل التوب
        return html.escape(name)
    except:
        return None

def build_top_markup():
    """يبني قائمة التوب مثل الصورة"""
    m = types.InlineKeyboardMarkup(row_width=1)
    # سطر 1: زر واحد
    m.add(types.InlineKeyboardButton("👑 توب الحكام", callback_data="ntop_rulers", style="primary"))
    # سطر 2: زرين
    row2 = [
        types.InlineKeyboardButton("🏅 توب تصنيف الذهبي", callback_data="ntop_gold", style="primary"),
        types.InlineKeyboardButton("💀 بارزات العالمية", callback_data="ntop_battles", style="primary"),
    ]
    m.row(*row2)
    # سطر 3: زرين
    row3 = [
        types.InlineKeyboardButton("💰 توب الفلوس", callback_data="ntop_money", style="primary"),
        types.InlineKeyboardButton("💀 توب الحراميه", callback_data="ntop_thieves", style="primary"),
    ]
    m.row(*row3)
    # سطر 4: زرين
    row4 = [
        types.InlineKeyboardButton("📊 توب المتفاعلين", callback_data="ntop_messages", style="success"),
        types.InlineKeyboardButton("💕 توب المتزوجين", callback_data="ntop_mahr", style="success"),
    ]
    m.row(*row4)
    # سطر 5: زرين
    row5 = [
        types.InlineKeyboardButton("🐸 توب المطلقات", callback_data="ntop_divorces", style="success"),
        types.InlineKeyboardButton("💔 توب المخلوعين", callback_data="ntop_khulaa", style="success"),
    ]
    m.row(*row5)
    # سطر 6: زر واحد
    m.add(types.InlineKeyboardButton("🏆 TOP توب القروبات", callback_data="ntop_groups", style="success"))
    return m

def ensure_global_divorces():
    if "global_divorces" not in DB:
        DB["global_divorces"] = {}
    return DB["global_divorces"]

def ensure_group_messages():
    """يحسب إجمالي رسائل كل قروب من DB"""
    groups = {}
    for key, val in DB.items():
        if key.startswith("-") and isinstance(val, dict) and "messages" in val:
            total = sum(val["messages"].values())
            if total > 0:
                groups[key] = total
    return groups

# ==========================================================
# التعديلات والاضافات الجديدة المطورة بالكامل لـ ايتو XRT
# ==========================================================

# قوالب الأسئلة لـ كت وصراحه والكلمات
KUT_QUESTIONS = [
    "إذا كان لديك 100000 ريال للتبرع لقضية ، فأي واحدة ستختار ولماذا؟",
    "ما هي العادة التي تمارسها وتظن أن الجميع يفعلها وهي غريبة؟",
    "لو أتيحت لك فرصة السفر للمستقبل واكتشاف شيء واحد، ماذا سيكون؟",
    "إذا عاد بك الزمن لوراء، ما هو القرار الذي ستلغيه تماماً؟",
    "ما هو الشيء الذي تعتبره نقطة قوتك الحقيقية في الحياة؟",
    "لو كان بإمكانك تغيير صفة واحدة في شخصيتك الحالية، فماذا ستختار؟"
]

SARAH_QUESTIONS = [
    "ما العطر المفضل لديك ؟",
    "هل سبق وأن كذبت كذبة كبيرة وندمت عليها لاحقاً؟",
    "من هو الشخص الذي تلجأ إليه دائماً عندما تشعر بالضيق؟",
    "ما هي أكبر مخاوفك في العلاقات العاطفية أو الصداقة؟",
    "هل أنت راضٍ عن حياتك الحالية بنسبة كم من 100؟",
    "ما هو الموقف الذي جعلك تبكي من شدة الاحراج؟"
]

GAME_WORDS = ["تماسيح", "برشلونة", "ريال مدريد", "العراق", "ايتو", "تليجرام", "مجموعة", "حماية", "برمجة", "مستقبل", "اقتصاد", "امبراطورية"]

active_words_game = {}

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "طلاق", priority=2)
def track_divorce_count(message):
    # تم نقل عد الطلاقات إلى divorce_command مباشرة لتجنب التكرار
    pass


# دالة لتحديث توب المطلقات العام والتصنيف الذهبي العام في البنك المشترك
def add_global_divorce(user_id):
    if "global_divorces" not in DB:
        DB["global_divorces"] = {}
    uid = str(user_id)
    DB["global_divorces"][uid] = DB["global_divorces"].get(uid, 0) + 1
    save_db()

def get_global_golden_points(user_id):
    if "global_golden" not in DB:
        DB["global_golden"] = {}
    return DB["global_golden"].get(str(user_id), 0)

def add_global_golden_points(user_id, points):
    if "global_golden" not in DB:
        DB["global_golden"] = {}
    uid = str(user_id)
    DB["global_golden"][uid] = DB["global_golden"].get(uid, 0) + points
    save_db()

# فحص دوري أو تلقائي للرصيد الذهبي يتم استدعاؤه عند زيادة الأموال بالبنك
def check_and_convert_to_gold(user_id, chat_id=None):
    # الحد الأقصى للمال الافتراضي بالبنك هو 100,000,000 (مائة مليون) أو مليار
    # سنقوم بجعل الكود يحول تلقائياً بمجرد تخطي رصيده للحد الأقصى المتاح
    banking = ensure_banking()
    uid = str(user_id)
    if uid in banking["users"]:
        current_balance = banking["users"][uid].get("balance", 0)
        # لنفترض أن لفل ماكس الفلوس هو 500,000,000 (خمسة مائة مليون)
        if current_balance >= 500000000:
            banking["users"][uid]["balance"] = 0
            add_global_golden_points(user_id, 50)
            save_db()
            if chat_id:
                try:
                    bot.send_message(chat_id, f"🏆 <b>تهانينا!</b> لقد وصلت للحد الأقصى من الثروة 💰.\nتمت تصفير أموالك تلقائياً وتحويلها إلى <b>50 نقطة ذهبية 🥇</b> في <b>توب التصنيف الذهبي</b>!")
                except: pass

# تعديل معالج "ا" الأساسي ليكون حراً وبقيود رتبة الأدمن وفوق
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "ا")
def refined_shortcut_user_info(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    role = get_role(chat_id, user_id)
    if role not in ["ادمن", "مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]:
        bot.reply_to(message, "⚠️ <b>هذا الأمر مخصص للإداريين فقط (أدمن وفوق)!</b>", parse_mode="HTML")
        return
        
    target_user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    target_id = target_user.id
    chat = ensure_chat(chat_id)
    target_role = get_role(chat_id, target_id)
    msg_count = chat.get("messages", {}).get(str(target_id), 0)
    
    banking = ensure_banking()
    user_bank = banking["users"].get(str(target_id), {})
    points = user_bank.get("balance", 0)
    gold = get_global_golden_points(target_id)
    
    try:
        chat_info = bot.get_chat(target_id)
        bio = chat_info.bio if chat_info.bio else "لا يوجد بايو"
    except:
        bio = "لا يوجد بايو"
        
    username = f"@{target_user.username}" if target_user.username else "بدون يوزر"
    
    info_text = (
        f"👤 <b>ايديك✨الحلو🥰:</b>\n\n"
        f"• <b>الاسم:</b> {human_name(target_user)}\n"
        f"• <b>اليوزر:</b> {username}\n"
        f"• <b>الايدي:</b> <code>{target_id}</code>\n"
        f"• <b>الرتبة:</b> <code>{target_role}</code>\n"
        f"• <b>البايو:</b> {bio}\n"
        f"• <b>عدد الرسائل:</b> {msg_count}\n"
        f"• <b>النقاط/الفلوس:</b> {points:,} دينار\n"
        f"• <b>النقاط الذهبية:</b> {gold} 🥇\n"
    )
    
    try:
        photos = bot.get_user_profile_photos(target_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            bot.send_photo(chat_id, file_id, caption=info_text, reply_to_message_id=message.message_id, parse_mode="HTML")
            return
    except:
        pass
        
    bot.reply_to(message, info_text, parse_mode="HTML")

# أمر مسح بالرد للادمن وفوق
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "مسح")
def delete_message_by_reply(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if get_role(chat_id, user_id) not in ["ادمن", "مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]:
        return
        
    if message.reply_to_message:
        try:
            bot.delete_message(chat_id, message.reply_to_message.message_id)
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

# أمر الردود لعرض كافة الردود المضافة بالجروب
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الردود")
def show_all_group_replies(message):
    if not is_group(message): return
    chat_id = message.chat.id
    chat = ensure_chat(chat_id)
    replies = chat.get("custom_replies", {})
    
    if not replies:
        bot.reply_to(message, "📦 لا توجد أي ردود مضافة في هذه المجموعة حالياً.")
        return
        
    txt = "📋 <b>قائمة الردود المضافة في المجموعة:</b>\n\n"
    for i, keyword in enumerate(replies.keys(), 1):
        txt += f"{i} - <code>{keyword}</code>\n"
    bot.reply_to(message, txt, parse_mode="HTML")

# توب المطلقات العام
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب المطلقات")
def show_divorces_top(message):
    if not is_group(message): return
    divs = DB.get("global_divorces", {})
    if not divs:
        bot.reply_to(message, "💔 لا يوجد أي حالات طلاق مسجلة في البوت حتى الآن!")
        return
        
    lst = sorted(divs.items(), key=lambda x: x[1], reverse=True)
    medals_d = ["🥇","🥈","🥉"]
    txt = "💔 <b>توب المطلقات</b>\n🌍 من كل القروبات\n\n━━━━━━━━━━━━━━━\n"
    shown = 0
    for uid_str, count in lst[:30]:
        try:
            info = bot.get_chat(int(uid_str))
            name = safe_name_for_top(info)
        except:
            name = None
        if name is None: continue
        r = medals_d[shown] if shown < 3 else f"{shown+1}."
        txt += f"{r} {name} ← <b>{count} طلاق</b>\n"
        shown += 1
    txt += f"━━━━━━━━━━━━━━━\n👥 إجمالي المطلقين: <b>{shown}</b>"
    bot.reply_to(message, txt, parse_mode="HTML")

# توب التصنيف الذهبي
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب التصنيف الذهبي")
def show_golden_top(message):
    if not is_group(message): return
    gold = DB.get("global_golden", {})
    if not gold:
        bot.reply_to(message, "🏅 لا يوجد أي متصدرين في التصنيف الذهبي بعد!")
        return
        
    lst = sorted(gold.items(), key=lambda x: x[1], reverse=True)
    txt = "🏆 <b>قائمة متصدري التصنيف الذهبي (1 - 30):</b>\n\n"
    for i, (uid_str, points) in enumerate(lst[:30]):
        try:
            info = bot.get_chat(int(uid_str))
            name = human_name(info)
        except:
            name = f"مستخدم ({uid_str})"
        txt += f"{i+1} - {name} ↤ <b>{points} نقطة ذهبية 🥇</b>\n"
    bot.reply_to(message, txt, parse_mode="HTML")

# لعبة الكلمات ك
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "ك")
def start_words_game(message):
    if not is_group(message): return
    add_interaction(message.chat.id, message.from_user.id)
    chat_id = message.chat.id
    word = random.choice(GAME_WORDS)
    active_words_game[chat_id] = {
        "word": word,
        "time": time.time()
    }
    bot.reply_to(message, f"• اكتب الكلمه ↤︎︎ ( <b>{word}</b> )", parse_mode="HTML")

# لعبة كت
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "كت")
def kut_game(message):
    if not is_group(message): return
    add_interaction(message.chat.id, message.from_user.id)
    if not games_allowed(message.chat.id):
        bot.reply_to(message, "🚫 الألعاب مطفأة حالياً.")
        return
    q = random.choice(KUT_QUESTIONS)
    bot.reply_to(message, f"「 {human_name(message.from_user)} 」\n⤺ {q}")

# لعبة صراحه
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "صراحه")
def sarahah_game(message):
    if not is_group(message): return
    add_interaction(message.chat.id, message.from_user.id)
    q = random.choice(SARAH_QUESTIONS)
    bot.reply_to(message, f"💬 <b>صراحة ↤</b> {q}")

# زر بخشيش
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "بخشيش")
def bakhsheesh_cmd(message):
    if not is_group(message): return
    amount = random.randint(1, 25000)
    banking = ensure_banking()
    uid = str(message.from_user.id)
    if uid not in banking["users"]:
        banking["users"][uid] = {"balance": 0, "history": []}
    banking["users"][uid]["balance"] += amount
    save_db()
    
    bot.reply_to(message, f"• خذ يا فقير ( <b>{amount:,}</b> ) دينار", parse_mode="HTML")
    check_and_convert_to_gold(message.from_user.id, message.chat.id)

# زر مح بالرد
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "مح")
def kiss_reply_cmd(message):
    if not is_group(message): return
    if message.reply_to_message:
        sender_id = message.from_user.id
        receiver_id = message.reply_to_message.from_user.id
        sender = f'<a href="tg://user?id={sender_id}">{human_name(message.from_user)}</a>'
        receiver = f'<a href="tg://user?id={receiver_id}">{human_name(message.reply_to_message.from_user)}</a>'
        bot.reply_to(message, f"💋 تم تقبيلك يـ {receiver} من قبل {sender} 🙈", parse_mode="HTML")

# معالج فحص الاجابة الصحيحة للعبة الكلمات ك
@bot.message_handler(func=lambda m: m.chat.id in active_words_game and m.text and m.text.strip() == active_words_game[m.chat.id]["word"])
def check_game_answer(message):
    chat_id = message.chat.id
    add_interaction(chat_id, message.from_user.id)
    game_data = active_words_game[chat_id]
    elapsed = round(time.time() - game_data["time"], 2)
    del active_words_game[chat_id]
    
    prize = random.randint(10, 1000)
    banking = ensure_banking()
    uid = str(message.from_user.id)
    if uid not in banking["users"]:
        banking["users"][uid] = {"balance": 0, "history": []}
    banking["users"][uid]["balance"] += prize
    save_db()
    
    txt = (
        f"• اجابة صحيحة ↤ ( <b>{human_name(message.from_user)}</b> )\n"
        f"• عدد الثواني ↤ ( <b>{elapsed}</b> ثانية )\n"
        f"• فلوسك الزيادة ↤ ( <b>+{prize}</b> دينار )"
    )
    bot.reply_to(message, txt, parse_mode="HTML")
    check_and_convert_to_gold(message.from_user.id, chat_id)


@bot.callback_query_handler(func=lambda call: call.data in ["owner_clear_all_assets", "owner_clear_golden_top"])
def handle_owner_clear_actions(call):
    if call.from_user.id != BOT_OWNER_ID:
        bot.answer_callback_query(call.id, "⚠️ هذا الزر مخصص للمطور الأساسي فقط!", show_alert=True)
        return
        
    if call.data == "owner_clear_all_assets":
        # تصفير الممتلكات والزواجات والطلاقات والفلوس
        DB["global_divorces"] = {}
        # تصفير البنك والفلوس
        if "banking" in DB:
            DB["banking"]["users"] = {}
        # تصفير الممتلكات والزواج من داخل القروبات
        for chat_id in DB:
            if isinstance(DB[chat_id], dict):
                if "marriages" in DB[chat_id]: DB[chat_id]["marriages"] = {}
                if "inventory" in DB[chat_id]: DB[chat_id]["inventory"] = {}
        save_db()
        bot.answer_callback_query(call.id, "✅ تم تصفير (الممتلكات، الزواجات، الطلاقات، الفلوس) بنجاح لجميع المستخدمين!", show_alert=True)
        
    elif call.data == "owner_clear_golden_top":
        # تصفير التصنيف الذهبي فقط له زر مستقل وحده
        DB["global_golden"] = {}
        save_db()
        bot.answer_callback_query(call.id, "✅ تم تصفير توب التصنيف الذهبي بالكامل بنجاح!", show_alert=True)


@bot.message_handler(func=lambda m: m.from_user.id == BOT_OWNER_ID and m.text and m.text.strip() == "لوحة تصفير المطور")
def show_owner_clear_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💥 تصفير (الفلوس + الزواج + المطلقات + الممتلكات)", callback_data="owner_clear_all_assets"))
    markup.add(types.InlineKeyboardButton("🥇 تصفير توب التصنيف الذهبي فقط", callback_data="owner_clear_golden_top"))
    bot.reply_to(message, "⚙️ <b>أهلاً بك يا مطورنا العزيز في لوحة التحكم في تصفير البيانات الشاملة:</b>", reply_markup=markup, parse_mode="HTML")


# ==========================================
# نظام الردود المتطور المدمج + أمر "ا" الحر
# ==========================================

reply_adding_steps = {}
shortcut_steps = {}  # نفس نظام reply_adding_steps للاختصارات
shortcut_delete_steps = {}  # جلسات مسح الاختصارات

def can_manage_replies(chat_id, user_id):
    return get_role(chat_id, user_id) in ["مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]

def format_reply_text(text, message, chat, user_id):
    reply_username = "لا يوجد"
    if message.reply_to_message:
        ru = message.reply_to_message.from_user
        reply_username = f"@{ru.username}" if ru.username else human_name(ru)
    u = message.from_user
    my_username = f"@{u.username}" if u.username else "لا يوجد"
    role = get_role(message.chat.id, u.id)
    user_msg_count = chat.get("messages", {}).get(str(user_id), 0)
    user_points = ensure_banking()["users"].get(str(user_id), {}).get("balance", 0)
    
    text = text.replace("#الاسم", human_name(u))
    text = text.replace("#يوزره", reply_username)
    text = text.replace("#اليوزر", my_username)
    text = text.replace("#الرسائل", str(user_msg_count))
    text = text.replace("#الايدي", str(u.id))
    text = text.replace("#الرتبه", str(role))
    text = text.replace("#التعديل", "0")
    text = text.replace("#النقاط", str(user_points))
    return text

def _wz_normalize_reply_entry(entry):
    """يحوّل أي شكل قديم (رد وحيد مباشر) لشكل موحّد {'exact': [...], 'contains': [...]}"""
    if entry is None:
        return {"exact": [], "contains": []}
    if isinstance(entry, dict) and ("exact" in entry or "contains" in entry):
        entry.setdefault("exact", [])
        entry.setdefault("contains", [])
        return entry
    if isinstance(entry, dict) and "type" in entry:
        return {"exact": [entry], "contains": []}
    if isinstance(entry, list):
        return {"exact": entry, "contains": []}
    return {"exact": [], "contains": []}


def _wz_find_reply_match(chat, msg_text):
    """يرجع (رد, الكلمة المطابقة). يفضّل المطابقة التامة، وإلا أطول كلمة منذكرة بأي مكان بالنص."""
    replies = chat.get("custom_replies", {})
    if not msg_text:
        return None, None
    if msg_text in replies:
        entry = _wz_normalize_reply_entry(replies[msg_text])
        pool = entry["exact"] or entry["contains"]
        if pool:
            return random.choice(pool), msg_text
    best_kw = None
    for kw in replies.keys():
        if kw and kw != msg_text and kw in msg_text:
            if best_kw is None or len(kw) > len(best_kw):
                best_kw = kw
    if best_kw:
        entry = _wz_normalize_reply_entry(replies[best_kw])
        pool = entry["contains"] or entry["exact"]
        if pool:
            return random.choice(pool), best_kw
    return None, None


def _wz_send_matched_reply(chat, chat_id, message, user_id):
    """يفحص إذا الرسالة تطابق رد مخصص ويرسله. يرجع True إذا أرسل شي."""
    if not message.text:
        return False
    msg_text = message.text.strip()
    rep, matched_kw = _wz_find_reply_match(chat, msg_text)
    if not rep:
        return False
    final_text = format_reply_text(rep["text"], message, chat, user_id)
    if rep["type"] == "text": bot.reply_to(message, final_text, parse_mode="HTML")
    elif rep["type"] == "photo": bot.send_photo(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    elif rep["type"] == "video": bot.send_video(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    elif rep["type"] == "animation": bot.send_animation(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    elif rep["type"] == "voice": bot.send_voice(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    elif rep["type"] == "audio": bot.send_audio(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    elif rep["type"] == "document": bot.send_document(chat_id, rep["file_id"], caption=final_text, reply_to_message_id=message.message_id, parse_mode="HTML")
    else:
        return False
    return True


def _wz_has_any_reply_match(m):
    if not (m.text and is_group(m)):
        return False
    txt = m.text.strip()
    if not txt:
        return False
    # لا تتدخل بالرسائل الموجهة أصلاً لتريغر الذكاء الاصطناعي (ايتو ...)
    # حتى لو النص يحتوي على كلمة مفتاحية من الردود المخصصة (مثل "ماثيو")
    if txt.split()[0] == AI_TRIGGER and len(txt.split()) > 1:
        return False
    chat = ensure_chat(m.chat.id)
    replies = chat.get("custom_replies", {})
    if not replies:
        return False
    if txt in replies:
        return True
    for kw in replies.keys():
        if kw and kw in txt:
            return True
    return False


@bot.message_handler(func=lambda m: m.text and m.text.strip() == "اضف رد")
def init_add_reply(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_manage_replies(chat_id, user_id):
        bot.reply_to(message, "⚠️ هذا الأمر مخصص للإداريين فقط (مدير فأعلى).")
        return
    reply_adding_steps[f"{chat_id}_{user_id}"] = {"step": "waiting_keyword"}
    bot.reply_to(message, "📋 حسناً، أرسل الآن <b>كلمة الرد</b> (الكلمة المفتاحية):", parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data in ("rpladd_exact", "rpladd_contains"))
def reply_add_match_type_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_key = f"{chat_id}_{user_id}"
    if user_key not in reply_adding_steps or reply_adding_steps[user_key].get("step") != "waiting_match_type":
        bot.answer_callback_query(call.id, "⚠️ انتهت صلاحية الجلسة، اكتب 'اضف رد' من جديد.", show_alert=True)
        return
    keyword = reply_adding_steps[user_key]["keyword"]
    match_kind = "exact" if call.data == "rpladd_exact" else "contains"
    reply_adding_steps[user_key] = {"step": "waiting_content", "keyword": keyword, "match_kind": match_kind}
    kind_label = "مطابقة تامة (يكتب الكلمة بس)" if match_kind == "exact" else "لو انذكرت بأي مكان بالكلام"
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            f"📥 الكلمة المفتاحية: (<code>{keyword}</code>) — {kind_label}\n\n"
            f"الآن أرسل محتوى الرد (نص، صورة، فيديو، بصمة، متحركة، ملف، أو أغنية):",
            chat_id, call.message.message_id, parse_mode="HTML")
    except:
        bot.send_message(chat_id,
            "📥 الآن أرسل محتوى الرد (نص، صورة، فيديو، بصمة، متحركة، ملف، أو أغنية):", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "حذف رد")
def init_delete_reply(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_manage_replies(chat_id, user_id):
        bot.reply_to(message, "⚠️ هذا الأمر مخصص للإداريين فقط (مدير فأعلى).")
        return
    reply_adding_steps[f"{chat_id}_{user_id}"] = {"step": "waiting_delete_keyword"}
    bot.reply_to(message, "🗑️ أرسل الآن <b>اسم الرد</b> الذي تريد حذفه:")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الردود")
def list_replies(message):
    if not is_group(message): return
    chat_id = message.chat.id
    chat = ensure_chat(chat_id)
    replies = chat.get("custom_replies", {})
    if not replies:
        bot.reply_to(message, "📦 لا توجد أي ردود محفوظة في هذه المجموعة حتى الآن.")
        return
    txt = "📋 <b>قائمة الردود المحفوظة في المجموعة:</b>\n\n"
    for i, keyword in enumerate(replies.keys(), 1):
        entry = _wz_normalize_reply_entry(replies[keyword])
        parts = []
        if entry["exact"]:
            parts.append(f"مطابقة تامة×{len(entry['exact'])}")
        if entry["contains"]:
            parts.append(f"أي مكان×{len(entry['contains'])}")
        info = " + ".join(parts) if parts else "؟"
        txt += f"{i} - <code>{keyword}</code> ({info})\n"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🗑️ حذف رد", callback_data="panel_delete_reply"),
        types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")
    )
    bot.reply_to(message, txt, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "ا")
def shortcut_user_info(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    if get_role(chat_id, user_id) not in ["ادمن", "مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]: return
    
    target_user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    target_id = target_user.id
    chat = ensure_chat(chat_id)
    target_role = get_role(chat_id, target_id)
    msg_count = chat.get("messages", {}).get(str(target_id), 0)
    points = ensure_banking()["users"].get(str(target_id), {}).get("balance", 0)
    
    try:
        chat_info = bot.get_chat(target_id)
        bio = chat_info.bio if chat_info.bio else "لا يوجد بايو"
    except:
        bio = "لا يوجد بايو"
    username = f"@{target_user.username}" if target_user.username else "بدون يوزر"
    
    info_text = (
        f"👤 <b>معلومات المستخدم:</b>\n\n"
        f"• <b>الاسم:</b> {human_name(target_user)}\n"
        f"• <b>اليوزر:</b> {username}\n"
        f"• <b>الايدي:</b> <code>{target_id}</code>\n"
        f"• <b>الرتبة:</b> <code>{target_role}</code>\n"
        f"• <b>البايو:</b> {bio}\n"
        f"• <b>عدد الرسائل:</b> {msg_count}\n"
        f"• <b>النقاط:</b> {points:,}\n"
    )
    try:
        photos = bot.get_user_profile_photos(target_id, limit=1)
        if photos.total_count > 0:
            bot.send_photo(chat_id, photos.photos[0][-1].file_id, caption=info_text, reply_to_message_id=message.message_id, parse_mode="HTML")
            return
    except: pass
    bot.reply_to(message, info_text, parse_mode="HTML")


@bot.message_handler(func=lambda m: (f"{m.chat.id}_{m.from_user.id}" in reply_adding_steps) or (f"{m.chat.id}_{m.from_user.id}" in shortcut_steps) or _wz_has_any_reply_match(m), content_types=["text", "photo", "video", "animation", "audio", "voice", "document"])
def handle_custom_replies_and_steps_intercept(message):
    # هذا المعالج مسجل مبكراً في الملف، لذلك نمرر جلسات الهمسات
    # وإضافة صور ألعاب الأنمي/اللاعبين قبل الخروج من الخاص.
    if not is_group(message):
        uid_key = str(getattr(message.from_user, "id", ""))
        # جلسة همسة خاصة
        if uid_key in DB.get("whisper_compose", {}):
            try:
                return whisper_receive_private(message)
            except NameError:
                return
            except Exception:
                try:
                    bot.send_message(message.chat.id, "⚠️ صار خطأ أثناء حفظ الهمسة، حاول مرة ثانية.")
                except Exception:
                    pass
            return
        # جلسة إضافة صورة للأنمي/اللاعبين
        sess = DB.get("picture_add_sessions", {}).get(uid_key)
        if sess:
            try:
                if getattr(message, "content_type", None) == "photo" and sess.get("step") == "photo":
                    return picture_add_photo_step(message)
                if getattr(message, "content_type", None) == "text" and sess.get("step") == "answer":
                    return picture_add_answer_step(message)
            except NameError:
                return
            except Exception:
                try:
                    bot.send_message(message.chat.id, "⚠️ صار خطأ أثناء إضافة الصورة، حاول مرة ثانية.")
                except Exception:
                    pass
            return
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_key = f"{chat_id}_{user_id}"
    chat = ensure_chat(chat_id)

    # ========= معالجة جلسة الاختصار =========
    if user_key in shortcut_steps:
        sess = shortcut_steps[user_key]
        txt = message.text.strip() if message.text else ""
        if not txt: return
        cid = sess.get("chat_id", chat_id)

        if sess["step"] == "waiting_shortcut_word":
            # المرحلة 1 — كتب الاختصار، نطلب الأمر
            shortcuts = ensure_shortcuts(cid)
            if txt in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{txt}</b> موجود مسبقاً، اكتب اختصاراً مختلفاً.", parse_mode="HTML")
                return
            shortcut_steps[user_key] = {"step": "waiting_cmd_for_shortcut", "shortcut": txt, "chat_id": cid}
            bot.reply_to(message,
                f"✅ الاختصار: <code>{txt}</code>\n\n"
                f"📝 الآن اكتب الأمر الذي تريد اختصاره\n"
                f"مثال: <code>ادمن</code>",
                parse_mode="HTML")

        elif sess["step"] == "waiting_cmd_for_shortcut":
            # المرحلة 2 — كتب الأمر، نحفظ ونؤكد
            shortcut     = sess["shortcut"]
            original_cmd = txt
            shortcuts    = ensure_shortcuts(cid)
            if shortcut in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{shortcut}</b> موجود مسبقاً.", parse_mode="HTML")
                del shortcut_steps[user_key]
                return
            shortcuts[shortcut] = original_cmd
            save_db()
            del shortcut_steps[user_key]
            bot.reply_to(message,
                f"✅ <b>تم إضافة الاختصار!</b>\n\n"
                f"⚡ <code>{shortcut}</code> ← <b>{original_cmd}</b>\n\n"
                f"أي شخص يكتب <b>{shortcut}</b> يطلعله نفس نتيجة <b>{original_cmd}</b>",
                parse_mode="HTML")

        # جلسة قديمة للتوافق
        elif sess["step"] == "waiting_cmd":
            shortcut_steps[user_key] = {"step": "waiting_shortcut", "original_cmd": txt, "chat_id": cid}
            bot.reply_to(message, f"✅ الأمر: <b>{txt}</b>\n\n📝 الآن أرسل الاختصار المطلوب\nمثال: <code>ف</code>", parse_mode="HTML")
        elif sess["step"] == "waiting_shortcut":
            original_cmd = sess["original_cmd"]
            shortcut     = txt
            shortcuts    = ensure_shortcuts(cid)
            if shortcut not in shortcuts:
                shortcuts[shortcut] = original_cmd
                save_db()
            del shortcut_steps[user_key]
            bot.reply_to(message,
                f"✅ <b>تم إضافة الاختصار!</b>\n\n"
                f"⚡ <code>{shortcut}</code> ← <b>{original_cmd}</b>",
                parse_mode="HTML")
        return
    
    if user_key in reply_adding_steps:
        step_data = reply_adding_steps[user_key]
        if step_data["step"] == "waiting_keyword":
            keyword = message.text
            if not keyword:
                bot.reply_to(message, "⚠️ يجب أن تكون الكلمة نصية، أعد إرسال كلمة الرد:")
                return
            reply_adding_steps[user_key] = {"step": "waiting_match_type", "keyword": keyword}
            mk = types.InlineKeyboardMarkup(row_width=1)
            mk.add(types.InlineKeyboardButton("🎯 مطابقة تامة (يكتب الكلمة بس)", callback_data="rpladd_exact"))
            mk.add(types.InlineKeyboardButton("📝 يظهر لو انذكرت بأي مكان بالكلام", callback_data="rpladd_contains"))
            bot.reply_to(message,
                f"📥 الكلمة المفتاحية: (<code>{keyword}</code>).\n\nشلون تريد الرد يشتغل؟",
                parse_mode="HTML", reply_markup=mk)
            return
        elif step_data["step"] == "waiting_content":
            keyword = step_data["keyword"]
            match_kind = step_data.get("match_kind", "exact")
            reply_type = message.content_type
            file_id = None
            caption = message.caption or ""
            text_content = message.text or ""
            
            if reply_type == "photo": file_id = message.photo[-1].file_id
            elif reply_type == "video": file_id = message.video.file_id
            elif reply_type == "animation": file_id = message.animation.file_id
            elif reply_type == "voice": file_id = message.voice.file_id
            elif reply_type == "audio": file_id = message.audio.file_id
            elif reply_type == "document": file_id = message.document.file_id

            new_variant = {"type": reply_type, "file_id": file_id, "text": text_content if reply_type == "text" else caption}

            entry = _wz_normalize_reply_entry(chat["custom_replies"].get(keyword))
            entry[match_kind].append(new_variant)
            chat["custom_replies"][keyword] = entry
            save_db()
            del reply_adding_steps[user_key]

            count = len(entry[match_kind])
            extra = f" (عنده الحين {count} نسخ لهالنوع، بينتخب وحدة عشوائية كل مرة)" if count > 1 else ""
            bot.reply_to(message, f"✅ تم حفظ الرد بنجاح للكلمة: <b>{keyword}</b>{extra}", parse_mode="HTML")
            return
        elif step_data["step"] == "waiting_delete_keyword":
            keyword = message.text
            if keyword not in chat.get("custom_replies", {}):
                if user_key in reply_adding_steps: del reply_adding_steps[user_key]
                bot.reply_to(message, f"❌ الرد للكلمة (<code>{keyword}</code>) غير موجود بالأصل.", parse_mode="HTML")
                return
            reply_adding_steps[user_key] = {"step": "confirm_delete", "keyword": keyword}
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("نعم، احذف", callback_data="conf_del_y"), types.InlineKeyboardButton("لا، إلغاء", callback_data="conf_del_n"))
            bot.reply_to(message, f"❓ هل تريد بالتأكيد حذف الرد الخاص بـ (<b>{keyword}</b>) نهائياً؟", reply_markup=markup, parse_mode="HTML")
            return

    _wz_send_matched_reply(chat, chat_id, message, user_id)


@bot.callback_query_handler(func=lambda call: call.data in ["panel_delete_reply", "conf_del_y", "conf_del_n"])
def handle_replies_callbacks_unique(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_key = f"{chat_id}_{user_id}"
    chat = ensure_chat(chat_id)
    
    if call.data == "panel_delete_reply":
        if not can_manage_replies(chat_id, user_id):
            bot.answer_callback_query(call.id, "⚠️ الصلاحية للمدراء فقط.", show_alert=True)
            return
        reply_adding_steps[user_key] = {"step": "waiting_delete_keyword"}
        bot.edit_message_text("🗑️ أرسل الآن اسم الرد الذي تريد حذفه بالقروب:", chat_id, call.message.message_id)
        
    elif call.data == "conf_del_y":
        if not can_manage_replies(chat_id, user_id):
            bot.answer_callback_query(call.id, "⚠️ الصلاحية للمدراء فقط.", show_alert=True)
            return
        if user_key in reply_adding_steps and reply_adding_steps[user_key]["step"] == "confirm_delete":
            keyword = reply_adding_steps[user_key]["keyword"]
            if keyword in chat.get("custom_replies", {}):
                del chat["custom_replies"][keyword]
                save_db()
                bot.edit_message_text(f"🗑️ تم حذف الرد الخاص بـ (<b>{keyword}</b>) نهائياً من قاعدة البيانات.", chat_id, call.message.message_id, parse_mode="HTML")
            else:
                bot.edit_message_text("⚠️ لم يتم العثور على الرد أو قد يكون حُذف مسبقاً.", chat_id, call.message.message_id)
            del reply_adding_steps[user_key]
        else:
            bot.edit_message_text("⚠️ انتهت صلاحية الجلسة، أرسل 'حذف رد' من جديد.", chat_id, call.message.message_id)
            
    elif call.data == "conf_del_n":
        if not can_manage_replies(chat_id, user_id):
            bot.answer_callback_query(call.id, "⚠️ الصلاحية للمدراء فقط.", show_alert=True)
            return
        if user_key in reply_adding_steps: del reply_adding_steps[user_key]
        bot.edit_message_text("❌ تم إلغاء عملية الحذف وبقي الرد نشطاً.", chat_id, call.message.message_id)


# ========= هياكل البيانات =========
ALL_ROLES = ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن","مميز","عضو"]

# تسلسل الرتب للتنزيل المتدرج
ROLES_HIERARCHY = {
    "مالك اساسي": "مساعد مالك",
    "مساعد مالك": "مالك", 
    "مالك": "منشئ",
    "منشئ": "مدير",
    "مدير": "ادمن",
    "ادمن": "مميز",
    "مميز": "عضو",
    "عضو": "عضو"
}

ASSIGN_SCOPE = {
    "مالك اساسي": set(["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن","مميز","عضو"]), 
    "مساعد مالك": set(["مالك","منشئ","مدير","ادمن","مميز","عضو"]), 
    "مالك": set(["منشئ","مدير","ادمن","مميز","عضو"]),
    "منشئ": set(["مدير","ادمن","مميز","عضو"]),
    "مدير": set(["ادمن","مميز","عضو"]),
    "ادمن": set(["مميز","عضو"]),
    "مميز": set([]),
    "عضو": set([])
}

CAN_PIN = set(["مالك اساسي","مالك","منشئ","مدير"])

BAN_PERMISSIONS = {
    "مالك اساسي": True,
    "مساعد مالك": True,
    "مالك": True,
    "منشئ": True,
    "مدير": True,
    "ادمن": False,
    "مميز": False,
    "عضو": False
}

# نظام البنك والعملة
MAX_MONEY = 18223372036854774990  # 18 كوينتيليون

BANKS = {
    "1": {"name": "بنك لانستر سيتي 🏦", "interest": 0.05, "color": "🟨", "type": "ماستركارد"},
    "2": {"name": "بنك وستيروس ترست 💳", "interest": 0.07, "color": "🔴", "type": "فيزا"},
    "3": {"name": "بنك برافوسي إنفستمنت 📈", "interest": 0.10, "color": "🟢", "type": "بلاتينيوم"}
}

JOBS = {
    "طبيب جراح": {"min_salary": 12000, "max_salary": 18000, "emoji": "👨‍⚕️"},
    "مدير تنفيذي": {"min_salary": 10000, "max_salary": 15000, "emoji": "👨‍💼"},
    "مبرمج": {"min_salary": 8000, "max_salary": 12000, "emoji": "👨‍💻"},
    "معلم": {"min_salary": 5000, "max_salary": 8000, "emoji": "👨‍🏫"},
    "طاهي": {"min_salary": 4000, "max_salary": 6000, "emoji": "👨‍🍳"}
}

# ========= إضافة عناصر أكثر للمتجر =========
ITEMS = {
    # 📱 الالكترونيات
    "ايفون": {"price": 1200, "category": "📱 الالكترونيات", "emoji": "📱"},
    "سامسونج": {"price": 1100, "category": "📱 الالكترونيات", "emoji": "📱"},
    "ماك بوك": {"price": 2500, "category": "📱 الالكترونيات", "emoji": "💻"},
    "بلايستيشن": {"price": 500, "category": "📱 الالكترونيات", "emoji": "🎮"},
    "ايباد": {"price": 800, "category": "📱 الالكترونيات", "emoji": "📱"},
    "ساعة ذكية": {"price": 400, "category": "📱 الالكترونيات", "emoji": "⌚"},
    "سماعات": {"price": 300, "category": "📱 الالكترونيات", "emoji": "🎧"},
    "كاميرا": {"price": 1500, "category": "📱 الالكترونيات", "emoji": "📷"},
    
    # 🚗 السيارات
    "تويوتا": {"price": 25000, "category": "🚗 السيارات", "emoji": "🚗"},
    "تيسلا": {"price": 42000, "category": "🚗 السيارات", "emoji": "🚗"},
    "لامبورغيني": {"price": 500000, "category": "🚗 السيارات", "emoji": "🏎️"},
    "فيراري": {"price": 625000, "category": "🚗 السيارات", "emoji": "🏎️"},
    "مرسيدس": {"price": 80000, "category": "🚗 السيارات", "emoji": "🚙"},
    "بي ام دبليو": {"price": 75000, "category": "🚗 السيارات", "emoji": "🚙"},
    "奥迪": {"price": 60000, "category": "🚗 السيارات", "emoji": "🚗"},
    "هيونداي": {"price": 35000, "category": "🚗 السيارات", "emoji": "🚗"},
    
    # 🏠 العقارات
    "شقة": {"price": 80000, "category": "🏠 العقارات", "emoji": "🏠"},
    "فيلا": {"price": 1200000, "category": "🏠 العقارات", "emoji": "🏰"},
    "قصر": {"price": 5000000, "category": "🏠 العقارات", "emoji": "🏰"},
    "جزيرة": {"price": 50000000, "category": "🏠 العقارات", "emoji": "🏝️"},
    "مزرعة": {"price": 2000000, "category": "🏠 العقارات", "emoji": "🌾"},
    "منزل": {"price": 150000, "category": "🏠 العقارات", "emoji": "🏡"},
    "شاليه": {"price": 300000, "category": "🏠 العقارات", "emoji": "⛱️"},
    "برج": {"price": 10000000, "category": "🏠 العقارات", "emoji": "🏢"},
    
    # ✈️ الطائرات واليخوت
    "طائرة خاصة": {"price": 3000000, "category": "✈️ الطائرات واليخوت", "emoji": "✈️"},
    "يخت فاخر": {"price": 30000000, "category": "✈️ الطائرات واليخوت", "emoji": "🛳️"},
    "مروحية": {"price": 1800000, "category": "✈️ الطائرات واليخوت", "emoji": "🚁"},
    "طائرة تجارية": {"price": 80000000, "category": "✈️ الطائرات واليخوت", "emoji": "✈️"},
    "زورق": {"price": 50000, "category": "✈️ الطائرات واليخوت", "emoji": "⛵"},
    "غواصة": {"price": 25000000, "category": "✈️ الطائرات واليخوت", "emoji": "🚤"},
    
    # 💎 المجوهرات
    "خاتم الماس": {"price": 50000, "category": "💎 المجوهرات", "emoji": "💍"},
    "ساعة رولكس": {"price": 25000, "category": "💎 المجوهرات", "emoji": "⌚"},
    "قلادة ذهب": {"price": 15000, "category": "💎 المجوهرات", "emoji": "📿"},
    "اسوارة الماس": {"price": 30000, "category": "💎 المجوهرات", "emoji": "📿"},
    "تاج": {"price": 1000000, "category": "💎 المجوهرات", "emoji": "👑"},
    
    # 🎨 الفنون
    "لوحة فنية": {"price": 500000, "category": "🎨 الفنون", "emoji": "🎨"},
    "تمثال": {"price": 200000, "category": "🎨 الفنون", "emoji": "🗿"},
    "مخطوطة نادرة": {"price": 1000000, "category": "🎨 الفنون", "emoji": "📜"},
    "سجادة ثمينة": {"price": 300000, "category": "🎨 الفنون", "emoji": "🧵"},
    
    # 🏟️ المرافق
    "ملعب": {"price": 20000000, "category": "🏟️ المرافق", "emoji": "⚽"},
    "مستشفى": {"price": 15000000, "category": "🏟️ المرافق", "emoji": "🏥"},
    "مدرسة": {"price": 5000000, "category": "🏟️ المرافق", "emoji": "🏫"},
    "فندق": {"price": 10000000, "category": "🏟️ المرافق", "emoji": "🏨"},
    "مركز تجاري": {"price": 30000000, "category": "🏟️ المرافق", "emoji": "🏬"}
}

# ========= دوال مساعدة =========
def ensure_chat(chat_id):
    sid = str(chat_id)
    if sid not in DB:
        DB[sid] = {
            "main_owner": None,
            "roles": { r: [] for r in ALL_ROLES if r != "عضو" },
            "known_users": {},
            "messages": {},
            "admins_list": [],
            "spam": {},
            "warnings": {},
            "ban_permissions": {},
            "restrictions": {},
            "zarf_cooldown": {},
            "marriages": {},
            "divorces": {},
            "golden_points": {},
            "custom_replies": {},
            "event_log": [],
            "new_members": [],
            "group_rules": None
        }
        save_db()
    if "custom_replies" not in DB[sid]:
        DB[sid]["custom_replies"] = {}
        save_db()
    if "event_log" not in DB[sid]:
        DB[sid]["event_log"] = []
        save_db()
    if "new_members" not in DB[sid]:
        DB[sid]["new_members"] = []
        save_db()
    if "group_rules" not in DB[sid]:
        DB[sid]["group_rules"] = None
        save_db()
    return DB[sid]

def ensure_banking():
    if "banking" not in DB:
        DB["banking"] = {
            "users": {},
            "items": ITEMS,
            "zarf_history": {},
            "marriage_top": {}
        }
        save_db()
    return DB["banking"]

def ensure_event_log(chat_id):
    chat = ensure_chat(chat_id)
    if "event_log" not in chat:
        chat["event_log"] = []
    return chat["event_log"]

def add_event(chat_id, text):
    from datetime import datetime as _dt
    log = ensure_event_log(chat_id)
    now = _dt.now().strftime("%d/%m %H:%M")
    log.append(f"[{now}] {text}")
    if len(log) > 50:
        log.pop(0)
    save_db()

def ensure_games_settings(chat_id):
    chat = ensure_chat(chat_id)
    if "games_enabled" not in chat:
        chat["games_enabled"] = True
        save_db()
    return chat

def games_allowed(chat_id):
    chat = ensure_chat(chat_id)
    return chat.get("games_enabled", True)

def build_shortcut_panel(chat_id):
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton("➕ اضف اختصار",   callback_data=f"scpanel_add_{chat_id}"))
    m.add(types.InlineKeyboardButton("📋 الاختصارات",   callback_data=f"scpanel_list_{chat_id}"))
    m.add(types.InlineKeyboardButton("🗑 مسح اختصار",   callback_data=f"scpanel_del_{chat_id}"))
    m.add(types.InlineKeyboardButton("❌ اغلاق",        callback_data="close_panel"))
    return m


    if "banking" not in DB:
        DB["banking"] = {
            "users": {},
            "items": ITEMS,
            "zarf_history": {},  # تاريخ الزرف
            "marriage_top": {}  # توب المهور
        }
        save_db()
    return DB["banking"]

def ensure_marriage_system():
    if "marriage" not in DB:
        DB["marriage"] = {
            "marriages": {},
            "divorces": {},
            "golden_points": {},
            "custom_replies": {},
            "divorced": {},
            "khul": {}
        }
        save_db()
    return DB["marriage"]

def get_user_bank_data(user_id):
    banking = ensure_banking()
    user_id_str = str(user_id)
    if user_id_str not in banking["users"]:
        return None
    return banking["users"][user_id_str]

def set_main_owner(chat_id, user_id):
    chat = ensure_chat(chat_id)
    if chat["main_owner"] is None:
        chat["main_owner"] = user_id
        if user_id not in chat["roles"]["مالك اساسي"]:
            chat["roles"]["مالك اساسي"].append(user_id)
        save_db()
        return True
    return False

def get_role(chat_id, user_id):
    chat = ensure_chat(chat_id)
    if chat["main_owner"] == user_id:
        return "مالك اساسي"
    if user_id in chat["roles"].get("مساعد مالك", []):
        return "مساعد مالك"
    for r in ["مالك","منشئ","مدير","ادمن","مميز"]:
        if user_id in chat["roles"][r]:
            return r
    return "عضو"

def set_role(chat_id, user_id, new_role):
    chat = ensure_chat(chat_id)
    if new_role == "مالك اساسي":
        return
    
    # إزالة المستخدم من جميع الرتب
    for r in ["مالك","منشئ","مدير","ادمن","مميز"]:
        if user_id in chat["roles"][r]:
            chat["roles"][r].remove(user_id)
    
    # إضافة المستخدم للرتبة الجديدة
    if new_role == "مساعد مالك":
        chat["roles"]["مساعد مالك"] = [user_id]
    elif new_role in chat["roles"]:
        if user_id not in chat["roles"][new_role]:
            chat["roles"][new_role].append(user_id)
    save_db()

def downgrade_role(chat_id, user_id):
    """تنزيل الرتبة درجة واحدة فقط"""
    current_role = get_role(chat_id, user_id)
    if current_role == "عضو":
        return current_role  # لا يمكن التنزيل أكثر من هذا
    
    new_role = ROLES_HIERARCHY[current_role]
    set_role(chat_id, user_id, new_role)
    return new_role

def human_name(u):
    name = u.first_name or ""
    if u.last_name:
        name += " " + u.last_name
    name = name.strip() or "بدون اسم"
    # نعمل escape لأي رموز HTML موجودة بالاسم (مثل < > &) حتى ما تكسر رسائل البوت
    return html.escape(name)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def find_user_id_by_username(chat_id, username_no_at):
    chat = ensure_chat(chat_id)
    return chat["known_users"].get(username_no_at)

def update_known_user(message):
    # V22: تسجيل XP عام للرسائل بدون تكرار نفس message_id
    try:
        vu = v22_user(message.from_user.id) if 'v22_user' in globals() else None
        if vu is not None and vu.get("last_message_id") != getattr(message, "message_id", None):
            vu["last_message_id"] = getattr(message, "message_id", None)
            vu["messages"] = vu.get("messages", 0) + 1
            vu["xp"] = vu.get("xp", 0) + 5
            vu["level"] = v22_level(vu["xp"]) if 'v22_level' in globals() else vu.get("level",1)
            if 'v22_check_achievements' in globals(): v22_check_achievements(message.from_user.id)
    except Exception:
        pass
    chat_id = message.chat.id
    chat = ensure_chat(chat_id)
    u = message.from_user
    if u.username:
        chat["known_users"][u.username] = u.id
        save_db()
    # ===== تسجيل نشاط المستخدم بهذا القروب (يفيد قائمة لعبة السحرة) =====
    if u and not u.is_bot:
        active = chat.setdefault("wz_active_members", {})
        uid_str = str(u.id)
        if uid_str not in active:
            active[uid_str] = True
            save_db()
    if message.chat.title and chat.get("title") != message.chat.title:
        chat["title"] = message.chat.title
        save_db()

def is_group(message):
    return message.chat.type in ["group","supergroup"]

def can_assign(actor_role, target_new_role):
    scope = ASSIGN_SCOPE.get(actor_role, set())
    return target_new_role in scope

def validate_username(username):
    username = username.strip().replace('@', '')
    if re.match(r'^[a-zA-Z09_]{5,32}$', username):
        return username
    return None

def can_ban(chat_id, user_id):
    chat = ensure_chat(chat_id)
    role = get_role(chat_id, user_id)
    if BAN_PERMISSIONS.get(role, False):
        return True
    if chat["ban_permissions"].get(str(user_id), False):
        return True
    return False

def can_restrict(chat_id, user_id):
    role = get_role(chat_id, user_id)
    return role in ["ادمن", "مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]

def can_mute(chat_id, user_id):
    role = get_role(chat_id, user_id)
    return role in ["مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]

def can_send_media(role_name):
    return role_name in ["مميز", "ادمن", "مدير", "منشئ", "مالك", "مالك اساسي", "مساعد مالك"]

def can_create_polls(role_name):
    return role_name in ["ادمن", "مدير", "منشئ", "مالk", "مالك اساسي", "مساعد مالك"]

# ========= دوال البنك =========
def generate_account_number():
    # رقم حساب طويل يشبه الحقيقي (16 رقم)
    return f"{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}"

def generate_card_number():
    return f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

def generate_cvv():
    return str(random.randint(100, 999))

# ========= دوال القيود (منقولة من البوت الثاني) =========

def ban_user(chat_id, user_id):
    bot.ban_chat_member(chat_id, user_id)
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["banned"] = True
    save_db()
    return True

def unban_user(chat_id, user_id):
    bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["banned"] = False
    save_db()
    return True

def restrict_user(chat_id, user_id):
    bot.restrict_chat_member(chat_id, user_id, can_send_messages=False)
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["restricted"] = True
    save_db()
    return True

def unrestrict_user(chat_id, user_id):
    bot.restrict_chat_member(chat_id, user_id, can_send_messages=True)
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["restricted"] = False
    save_db()
    return True

# ========= دوال الكتم (حذف سريع — بدون تقييد Telegram) =========

def mute_user(chat_id, user_id):
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["muted"] = True
    chat["restrictions"][str(user_id)].pop("muted_until", None)  # كتم دائم (بدون وقت انتهاء)
    save_db()
    return True

def mute_user_temporary(chat_id, user_id, minutes):
    """كتم داخلي مؤقت لمدة معينة بالدقائق — ينرفع تلقائياً بعد انتهاء الوقت."""
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["muted"] = True
    chat["restrictions"][str(user_id)]["muted_until"] = time.time() + minutes * 60
    save_db()
    return True

def is_user_muted(chat, user_key):
    """يتحقق إذا الشخص مكتوم حالياً، ويرفع الكتم تلقائياً إذا كان مؤقت وانتهت مدته."""
    r = chat.get("restrictions", {}).get(user_key, {})
    if not r.get("muted"):
        return False
    until = r.get("muted_until")
    if until and time.time() >= until:
        r["muted"] = False
        r.pop("muted_until", None)
        save_db()
        return False
    return True

def unmute_user(chat_id, user_id):
    chat = ensure_chat(chat_id)
    if str(user_id) not in chat["restrictions"]:
        chat["restrictions"][str(user_id)] = {}
    chat["restrictions"][str(user_id)]["muted"] = False
    chat["restrictions"][str(user_id)].pop("muted_until", None)
    save_db()
    return True

# ========= نظام "منع" محتوى معيّن (ملصق/صورة/نص/متحركة) =========
def ensure_banned_media(chat):
    if "banned_media" not in chat:
        chat["banned_media"] = {}
    return chat["banned_media"]

MEDIA_TYPE_LABELS = {
    "sticker": "الملصق",
    "photo": "الصورة",
    "animation": "الصورة المتحركة (GIF)",
    "text": "النص",
}

def get_media_unique_id(message):
    """يرجع (المعرّف، النوع) لصورة/ملصق/متحركة (GIF)/نص برسالة معينة، أو (None, None) لأي نوع ثاني."""
    if getattr(message, "sticker", None):
        return message.sticker.file_unique_id, "sticker"
    if getattr(message, "photo", None):
        return message.photo[-1].file_unique_id, "photo"
    if getattr(message, "animation", None):
        return message.animation.file_unique_id, "animation"
    if getattr(message, "text", None):
        return message.text.strip(), "text"
    return None, None

def format_arabic_time(dt):
    """يحول datetime لصيغة 12 ساعة بالعربي، مثل: 4:25 ص"""
    hour12 = dt.strftime("%I").lstrip("0") or "12"
    minute = dt.strftime("%M")
    suffix = "ص" if dt.hour < 12 else "م"
    return f"{hour12}:{minute} {suffix}"

def remove_all_restrictions(chat_id, user_id):
    # رفع التقييد + الحظر + الكتم + الانذارات — بدون طرد
    try:
        permissions = types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False
        )
        bot.restrict_chat_member(chat_id, user_id, permissions)
    except:
        pass
    # رفع الحظر فقط إذا كان محظوراً — حتى لا يُطرد
    chat = ensure_chat(chat_id)
    if chat.get("restrictions", {}).get(str(user_id), {}).get("banned"):
        try:
            bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        except:
            pass
    chat["restrictions"][str(user_id)] = {"banned": False, "muted": False, "restricted": False}
    chat["warnings"][str(user_id)] = 0
    save_db()
    return True

# ========= نظام الزواج والطلاق =========
def get_user_marriages(user_id):
    marriage_system = ensure_marriage_system()
    user_id_str = str(user_id)
    return marriage_system["marriages"].get(user_id_str, [])

def add_marriage(husband_id, wife_id, mahr_amount):
    marriage_system = ensure_marriage_system()
    husband_str = str(husband_id)
    wife_str = str(wife_id)
    
    # خصم 10% من المهر عند الزواج
    actual_mahr = int(mahr_amount * 0.9)
    
    marriage = {
        "husband": husband_id,
        "wife": wife_id,
        "mahr": actual_mahr,
        "original_mahr": mahr_amount,
        "timestamp": time.time(),
        "status": "married"
    }
    
    if husband_str not in marriage_system["marriages"]:
        marriage_system["marriages"][husband_str] = []
    
    # التحقق من عدم تجاوز الحد الأقصى (4 زوجات)
    if len(marriage_system["marriages"][husband_str]) >= 4:
        return False, "لقد وصلت إلى الحد الأقصى للزوجات (4)"
    
    # التحقق أن الزوجة غير متزوجة من أحد آخر
    for h_str, wives in marriage_system["marriages"].items():
        for m in wives:
            if m.get("wife") == wife_id:
                return False, "هذا الشخص متزوج بالفعل! يجب أن يطلق أو ينخلع أولاً."
    
    marriage_system["marriages"][husband_str].append(marriage)
    
    # تحديث توب المهور
    banking = ensure_banking()
    if husband_str not in banking["marriage_top"]:
        banking["marriage_top"][husband_str] = 0
    banking["marriage_top"][husband_str] += actual_mahr
    
    save_db()
    return True, actual_mahr

def divorce_all(husband_id):
    marriage_system = ensure_marriage_system()
    husband_str = str(husband_id)
    
    if husband_str not in marriage_system["marriages"]:
        return False, "ليس لديك أي زوجات للطلاق"
    
    divorced_wives = []
    for marriage in marriage_system["marriages"][husband_str]:
        wife_id = marriage["wife"]
        divorced_wives.append(wife_id)
        
        # إضافة إلى قائمة المطلقات
        wife_str = str(wife_id)
        if wife_str not in marriage_system["divorced"]:
            marriage_system["divorced"][wife_str] = []
        marriage_system["divorced"][wife_str].append({
            "ex_husband": husband_id,
            "mahr": marriage["mahr"],
            "timestamp": time.time()
        })
    
    # حذف جميع الزوجات
    del marriage_system["marriages"][husband_str]
    
    # تحديث توب المهور
    banking = ensure_banking()
    if husband_str in banking["marriage_top"]:
        del banking["marriage_top"][husband_str]
    
    save_db()
    return True, divorced_wives

def divorce_specific(husband_id, wife_number):
    marriage_system = ensure_marriage_system()
    husband_str = str(husband_id)
    
    if husband_str not in marriage_system["marriages"]:
        return False, "ليس لديك أي زوجات للطلاق"
    
    if wife_number < 1 or wife_number > len(marriage_system["marriages"][husband_str]):
        return False, "رقم الزوجة غير صحيح"
    
    # الحصول على الزوجة المطلوبة
    marriage = marriage_system["marriages"][husband_str][wife_number - 1]
    wife_id = marriage["wife"]
    
    # إضافة إلى قائمة المطلقات
    wife_str = str(wife_id)
    if wife_str not in marriage_system["divorced"]:
        marriage_system["divorced"][wife_str] = []
    marriage_system["divorced"][wife_str].append({
        "ex_husband": husband_id,
        "mahr": marriage["mahr"],
        "timestamp": time.time()
    })
    
    # حذف الزوجة
    del marriage_system["marriages"][husband_str][wife_number - 1]
    
    # تحديث توب المهور
    banking = ensure_banking()
    if husband_str in banking["marriage_top"]:
        banking["marriage_top"][husband_str] -= marriage["mahr"]
        if banking["marriage_top"][husband_str] <= 0:
            del banking["marriage_top"][husband_str]
    
    save_db()
    return True, wife_id

def khul_divorce(wife_id, husband_id):
    marriage_system = ensure_marriage_system()
    husband_str = str(husband_id)
    wife_str = str(wife_id)
    
    if husband_str not in marriage_system["marriages"]:
        return False, "الزوج ليس لديك في قائمة زوجاته"
    
    # البحث عن الزوجة في قائمة زوجات الزوج
    marriage_index = -1
    marriage_data = None
    for i, marriage in enumerate(marriage_system["marriages"][husband_str]):
        if marriage["wife"] == wife_id:
            marriage_index = i
            marriage_data = marriage
            break
    
    if marriage_index == -1:
        return False, "لستِ زوجة لهذا الرجل"
    
    # إرجاع المهر للزوج
    banking = ensure_banking()
    husband_bank = get_user_bank_data(husband_id)
    wife_bank = get_user_bank_data(wife_id)
    
    if husband_bank and wife_bank:
        # خصم المهر من الزوجة وإرجاعه للزوج
        mahr_amount = marriage_data["mahr"]
        if wife_bank["balance"] >= mahr_amount:
            wife_bank["balance"] -= mahr_amount
            husband_bank["balance"] += mahr_amount
            
            # تحديث بيانات البنك
            banking["users"][str(wife_id)] = wife_bank
            banking["users"][str(husband_id)] = husband_bank
    
    # إضافة إلى قائمة المخلوعات
    if wife_str not in marriage_system["khul"]:
        marriage_system["khul"][wife_str] = []
    marriage_system["khul"][wife_str].append({
        "ex_husband": husband_id,
        "mahr": marriage_data["mahr"],
        "timestamp": time.time()
    })
    
    # حذف الزوجة من قائمة زوجات الزوج
    del marriage_system["marriages"][husband_str][marriage_index]
    
    # إذا لم يعد هناك زوجات، حذف القائمة
    if not marriage_system["marriages"][husband_str]:
        del marriage_system["marriages"][husband_str]
    
    # تحديث توب المهور
    if husband_str in banking["marriage_top"]:
        banking["marriage_top"][husband_str] -= marriage_data["mahr"]
        if banking["marriage_top"][husband_str] <= 0:
            del banking["marriage_top"][husband_str]
    
    save_db()
    return True, marriage_data["mahr"]

# ========= نظام الزرف الجديد =========
def zarf_user(chat_id, zarf_user_id, target_user_id):
    """سرقة الأموال من مستخدم آخر"""
    chat = ensure_chat(chat_id)
    banking = ensure_banking()
    
    # التحقق من التبريد
    zarf_key = f"{zarf_user_id}_{target_user_id}"
    current_time = time.time()
    
    if zarf_key in chat["zarf_cooldown"]:
        if current_time - chat["zarf_cooldown"][zarf_key] < 300:  # 5 دقائق
            return False, "الزرف", "هذا الشخص تم زرفه مؤخراً، حاول مرة أخرى بعد 5 دقائق"
    
    # التحقق من وجود حسابات بنكية
    zarf_user_data = get_user_bank_data(zarf_user_id)
    target_user_data = get_user_bank_data(target_user_id)
    
    if not zarf_user_data or not target_user_data:
        return False, "الزرف", "أحد المستخدمين ليس لديه حساب بنكي"
    
    # التحقق من رصيد الهدف
    if target_user_data["balance"] <= 0:
        return False, "الزرف", "هذا الشخص لا يملك أي أموال لسرقتها"
    
    # سرقة مبلغ عشوائي (0 إلى 13000)
    stolen_amount = random.randint(0, min(13000, target_user_data["balance"]))
    
    if stolen_amount <= 0:
        return False, "الزرف", "لم تستطع سرقة أي أموال"
    
    # خصم المبلغ من الهدف وإضافته للزرف
    target_user_data["balance"] -= stolen_amount
    zarf_user_data["balance"] += stolen_amount
    
    # تحديث zarf_total و zarf_count للزارف
    zarf_user_data["zarf_total"] = zarf_user_data.get("zarf_total", 0) + stolen_amount
    zarf_user_data["zarf_count"] = zarf_user_data.get("zarf_count", 0) + 1
    banking["users"][str(zarf_user_id)] = zarf_user_data
    
    # تحديث التبريد
    chat["zarf_cooldown"][zarf_key] = current_time
    
    # تسجيل تاريخ الزرف
    zarf_history_key = str(target_user_id)
    if zarf_history_key not in banking["zarf_history"]:
        banking["zarf_history"][zarf_history_key] = []
    
    banking["zarf_history"][zarf_history_key].append({
        "zarf_user_id": zarf_user_id,
        "amount": stolen_amount,
        "timestamp": current_time
    })
    
    save_db()
    return True, "الزرف", stolen_amount

# ========= مكافحة السبام =========
def check_spam(message):
    chat = ensure_chat(message.chat.id)
    user_id = message.from_user.id
    role = get_role(message.chat.id, user_id)

    if role not in ["عضو","مميز"]:
        return

    user_key = str(user_id)

    # لو الشخص متجاوز 5 انذارات ومكتوم أصلاً -> نحذف رسالته فوراً ونوقف هنا.
    # هذا هو الضمان الحقيقي للإسكات: يشتغل دايماً حتى لو تيليجرام رفض
    # تقييد العضو (نقص صلاحيات البوت مثلاً)، وهو نفسه اللي يمنع عدّاد
    # الانذارات من الاستمرار للأبد (6/5, 7/5, 8/5...).
    if is_user_muted(chat, user_key):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        return

    now_ts = time.time()

    timestamps = chat.get("spam", {}).get(user_key, [])
    timestamps = [t for t in timestamps if now_ts - t <= 5]
    timestamps.append(now_ts)

    if "spam" not in chat:
        chat["spam"] = {}
    chat["spam"][user_key] = timestamps
    save_db()

    if len(timestamps) >= 10:
        if "warnings" not in chat:
            chat["warnings"] = {}
        warnings = chat["warnings"].get(user_key, 0)
        chat["spam"][user_key] = []

        # نوقف عدّاد الانذارات عند 5 بالضبط — ما يزيد بعدها أبداً
        if warnings < 5:
            warnings += 1
            chat["warnings"][user_key] = warnings
            save_db()
            bot.send_message(message.chat.id, f"⚠️ {human_name(message.from_user)} تم إعطاؤه إنذار! ({warnings}/5)")

        if warnings >= 5:
            # تقييد مضمون بطريقتين مع بعض:
            # 1) تقييد تيليجرام الحقيقي (يحتاج صلاحية "تقييد الأعضاء" للبوت)
            # 2) كتم داخلي احتياطي مؤقت (30 دقيقة) — يضمن الإسكات حتى لو
            #    تيليجرام رفض التقييد الفعلي، وبنفس الوقت ما يعلّق العضو مكتوم للأبد
            try:
                restrict_user(message.chat.id, user_id)
            except Exception:
                pass
            try:
                mute_user_temporary(message.chat.id, user_id, 30)
            except Exception:
                pass
            chat["warnings"][user_key] = 0  # نصفر الإنذارات بعد تطبيق العقوبة
            save_db()
            bot.send_message(message.chat.id, f"⛔ {human_name(message.from_user)} تم كتمه وتقييده 30 دقيقة بسبب تعدد الانذارات (5/5).")

# ========= أمر: منع (يمنع صورة/ملصق معيّن — رتبة مدير وفوق) =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "منع" and m.chat.type in ["group","supergroup"])
def ban_media_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_mute(chat_id, user_id):  # مدير وفوق
        bot.reply_to(message, "⛔ هذا الأمر مخصص لرتبة المدير وفوق فقط.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⛔ رد على الصورة/الملصق/الصورة المتحركة/النص اللي تريد تمنعه، وبعدين اكتب: منع")
        return
    uid, mtype = get_media_unique_id(message.reply_to_message)
    if not uid:
        bot.reply_to(message, "⛔ لازم ترد على صورة أو ملصق أو صورة متحركة (GIF) أو نص حتى تكدر تمنعه.")
        return
    chat = ensure_chat(chat_id)
    banned = ensure_banned_media(chat)
    if uid in banned:
        bot.reply_to(message, "⚠️ هذا المحتوى ممنوع مسبقاً.")
        return
    banned[uid] = {"type": mtype, "added_by": user_id, "added_at": now_str()}
    save_db()
    label = MEDIA_TYPE_LABELS.get(mtype, "المحتوى")
    bot.reply_to(message,
        f"✅ تم إضافة هذا {label} إلى قائمة الممنوعات.\n"
        f"أي شخص (غير الأدمن وفوق) يرسله راح تنحذف رسالته تلقائياً ويستلم إنذار."
    )

# ========= أمر: الغاء المنع (رد على المحتوى الممنوع — رتبة مدير وفوق) =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الغاء المنع" and m.chat.type in ["group","supergroup"])
def unban_media_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_mute(chat_id, user_id):  # مدير وفوق
        bot.reply_to(message, "⛔ هذا الأمر مخصص لرتبة المدير وفوق فقط.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⛔ رد على المحتوى الممنوع اللي تريد تلغي منعه، وبعدين اكتب: الغاء المنع")
        return
    uid, mtype = get_media_unique_id(message.reply_to_message)
    if not uid:
        bot.reply_to(message, "⛔ لازم ترد على صورة أو ملصق أو صورة متحركة (GIF) أو نص حتى تكدر تلغي منعه.")
        return
    chat = ensure_chat(chat_id)
    banned = ensure_banned_media(chat)
    if uid not in banned:
        bot.reply_to(message, "⚠️ هذا المحتوى مو موجود بقائمة الممنوعات أصلاً.")
        return
    del banned[uid]
    save_db()
    bot.reply_to(message, "✅ تم إلغاء المنع عن هذا المحتوى.")

# ========= تطبيق عقوبة المحتوى الممنوع (صورة/ملصق/متحركة/نص) =========
def enforce_banned_content(chat_id, chat, message, mtype):
    user_id = message.from_user.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass

    content_warnings = chat.setdefault("content_warnings", {})
    key = str(user_id)
    warns = content_warnings.get(key, 0)
    if warns < 5:
        warns += 1
        content_warnings[key] = warns

    name = human_name(message.from_user)
    username_part = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
    link = f"<a href='tg://user?id={user_id}'>{name}</a>"
    label = MEDIA_TYPE_LABELS.get(mtype, "محتوى")

    if warns >= 5:
        until_dt = datetime.now() + timedelta(minutes=5)
        penalty_line = (
            f"العقوبة: تقييد 5 دقايق ⛔ حتى {until_dt.strftime('%y.%m.%d')}\n"
            f"الساعة {format_arabic_time(until_dt)}."
        )
    else:
        now_dt = datetime.now()
        penalty_line = (
            f"العقوبة: تحذير ({warns}/5) ❕ حتى {now_dt.strftime('%y.%m.%d')}\n"
            f"الساعة {format_arabic_time(now_dt)}."
        )

    try:
        bot.send_message(
            chat_id,
            f"{username_part} [<code>{user_id}</code>] {link} قام بإرسال {label} ممنوع 🚫\n{penalty_line}",
            parse_mode="HTML"
        )
    except:
        pass

    if warns >= 5:
        until_ts = int(time.time() + 5 * 60)
        try:
            bot.restrict_chat_member(chat_id, user_id, can_send_messages=False, until_date=until_ts)
        except:
            pass
        # كتم داخلي احتياطي مؤقت (5 دقايق) — يشتغل حتى لو تيليجرام رفض التقييد الفعلي
        mute_user_temporary(chat_id, user_id, 5)
        content_warnings[key] = 0  # نبدأ عداد جديد بعد استلام العقوبة
    save_db()

# ========= فلتر الوسائط =========
@bot.message_handler(content_types=["photo","sticker","video","animation","audio","voice","video_note","document"])
def media_guard(message):
    # الوسائط الخاصة يجب أن تصل إلى جلسات الهمسة/إضافة صور الألعاب،
    # لأن هذا المعالج العام مسجل قبل معالجاتها المتخصصة.
    if not is_group(message):
        uid_key = str(getattr(message.from_user, "id", ""))
        if uid_key in DB.get("whisper_compose", {}):
            try:
                return whisper_receive_private(message)
            except Exception:
                try:
                    bot.send_message(message.chat.id, "⚠️ صار خطأ أثناء حفظ الهمسة، حاول مرة ثانية.")
                except Exception:
                    pass
            return
        sess = DB.get("picture_add_sessions", {}).get(uid_key)
        if sess and getattr(message, "content_type", None) == "photo" and sess.get("step") == "photo":
            try:
                return picture_add_photo_step(message)
            except Exception:
                try:
                    bot.send_message(message.chat.id, "⚠️ صار خطأ أثناء إضافة الصورة، حاول مرة ثانية.")
                except Exception:
                    pass
            return
        return
    update_known_user(message)
    chat_id = message.chat.id
    user_id = message.from_user.id
    role = get_role(chat_id, user_id)
    chat = ensure_chat(chat_id)

    # ===== فحص المحتوى الممنوع (أمر "منع") — الأدمن وفوق مستثنون ويكدرون يرسلون بحرية =====
    banned = chat.get("banned_media", {})
    if banned and not can_restrict(chat_id, user_id):  # can_restrict = ادمن وفوق
        b_uid, b_type = get_media_unique_id(message)
        if b_uid and b_uid in banned:
            enforce_banned_content(chat_id, chat, message, b_type)
            return  # الرسالة انحذفت أصلاً، ما نكمل بقية فلتر الوسائط لنفس الرسالة

    chat["messages"][str(user_id)] = chat["messages"].get(str(user_id),0)+1
    save_db()

    check_spam(message)

    if can_send_media(role):
        return

    try:
        bot.delete_message(chat_id, message.message_id)
        bot.send_message(chat_id,
            f"⛔ <b>يا {human_name(message.from_user)}</b>، رتبتك <code>{role}</code> وما مسموح لك ترسل وسائط.\n"
            f"يجب أن تكون <b>مميز</b> أو أعلى لإرسال الوسائط."
        )
    except:
        pass

@bot.message_handler(content_types=["poll"])
def poll_guard(message):
    if not is_group(message):
        return
    
    role = get_role(message.chat.id, message.from_user.id)
    
    if not can_create_polls(role):
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id,
                f"⛔ <b>يا {human_name(message.from_user)}</b>، رتبتك <code>{role}</code> وما مسموح لك تنشئ استفتاءات.\n"
                f"يجب أن تكون <b>ادمن</b> أو أعلى لإنشاء الاستفتاءات."
            )
        except:
            pass

# ========= فلتر النصوص الممنوعة (ضمن نظام "منع") =========
def _is_banned_text(m):
    if not m.text or not is_group(m):
        return False
    if can_restrict(m.chat.id, m.from_user.id):  # ادمن وفوق مستثنون
        return False
    chat = ensure_chat(m.chat.id)
    banned = chat.get("banned_media", {})
    if not banned:
        return False
    text = m.text.strip()
    return text in banned and banned[text].get("type") == "text"

@bot.message_handler(func=_is_banned_text, priority=10)
def banned_text_guard(message):
    chat_id = message.chat.id
    chat = ensure_chat(chat_id)
    enforce_banned_content(chat_id, chat, message, "text")

# ========= نظام منع الروابط (للمالك والمالك الأساسي فقط) =========
LINK_BAN_ALLOWED = ["مالك", "مالك اساسي"]
LINK_PATTERN = re.compile(r'https?://', re.IGNORECASE)

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "منع الروابط" and m.chat.type in ["group","supergroup"])
def ban_links_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    role = get_role(chat_id, user_id)
    if role not in LINK_BAN_ALLOWED:
        bot.reply_to(message, "⛔ هذا الأمر مخصص للمالك والمالك الأساسي فقط.")
        return
    chat = ensure_chat(chat_id)
    if chat.get("links_banned", False):
        bot.reply_to(message, "⚠️ منع الروابط مفعّل مسبقاً.")
        return
    chat["links_banned"] = True
    save_db()
    bot.reply_to(message,
        "✅ تم تفعيل منع الروابط.\n"
        "أي شخص رتبته تحت الأدمن ويرسل رابط (http/https) راح تنحذف رسالته تلقائياً.")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الغاء منع الروابط" and m.chat.type in ["group","supergroup"])
def unban_links_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    role = get_role(chat_id, user_id)
    if role not in LINK_BAN_ALLOWED:
        bot.reply_to(message, "⛔ هذا الأمر مخصص للمالك والمالك الأساسي فقط.")
        return
    chat = ensure_chat(chat_id)
    if not chat.get("links_banned", False):
        bot.reply_to(message, "⚠️ منع الروابط مو مفعّل أصلاً.")
        return
    chat["links_banned"] = False
    save_db()
    bot.reply_to(message, "✅ تم إلغاء منع الروابط.")

def _is_banned_link(m):
    if not m.text or not is_group(m):
        return False
    if can_restrict(m.chat.id, m.from_user.id):  # ادمن وفوق مستثنون
        return False
    chat = ensure_chat(m.chat.id)
    if not chat.get("links_banned", False):
        return False
    return bool(LINK_PATTERN.search(m.text))

@bot.message_handler(func=_is_banned_link, priority=10)
def banned_link_guard(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    name = human_name(message.from_user)
    link = f"<a href='tg://user?id={user_id}'>{name}</a>"
    try:
        bot.send_message(chat_id, f"⛔ {link} الروابط ممنوعة بهذا القروب، تم حذف رسالتك.", parse_mode="HTML")
    except:
        pass

# ========= ردود عشوائية =========
NANI_RESPONSES = [" شتريد"," ها شتريد"," گدامك أني"]
BOT_RESPONSES = [" تره عندي اسم"," لا تلح"," راح أعصب واطلع من القروب"]

def random_reply(cmd):
    if cmd=="ايتو":
        return random.choice(NANI_RESPONSES)
    elif cmd=="بوت":
        return random.choice(BOT_RESPONSES)
    return ""

# ========= دوال الزرافات الجديدة =========
def create_user_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 حسابي", callback_data="pm_account"),
        types.InlineKeyboardButton("🏦 رصيدي", callback_data="pm_balance"),
        types.InlineKeyboardButton("🏆 التوب", callback_data="pm_top"),
        types.InlineKeyboardButton("💍 زوجاتي", callback_data="pm_wives"),
        types.InlineKeyboardButton("🛒 المتجر", callback_data="pm_store"),
        types.InlineKeyboardButton("📜 تعليمات", callback_data="pm_help"),
        types.InlineKeyboardButton("🎮 الألعاب", callback_data="user_games_menu"),
        types.InlineKeyboardButton("➕ أضف البوت لقروب", url="https://t.me/ri5xbot?startgroup=true"),
        types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"),
    )
    return markup

def create_owner_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    # ===== المراقبة =====
    markup.add(
        types.InlineKeyboardButton("📊 إحصائيات", callback_data="bot_stats"),
        types.InlineKeyboardButton("👥 القروبات", callback_data="bot_groups"),
    )
    markup.add(
        types.InlineKeyboardButton("🥇 التصنيف الذهبي", callback_data="bot_gold"),
        types.InlineKeyboardButton("📈 الأكثر نشاطاً", callback_data="bot_top_active"),
    )
    # ===== الأدوات =====
    markup.add(
        types.InlineKeyboardButton("💰 هدية فلوس", callback_data="bot_gift"),
        types.InlineKeyboardButton("🚫 حظر من اللعبة", callback_data="bot_ban_game"),
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ تصفير الكل", callback_data="bot_reset_all"),
        types.InlineKeyboardButton("🥇 تصفير الذهبي", callback_data="bot_reset_gold"),
    )
    markup.add(
        types.InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="bot_search_user"),
        types.InlineKeyboardButton("🔄 تصفير قروب", callback_data="bot_reset_group"),
    )
    # ===== التواصل =====
    markup.add(
        types.InlineKeyboardButton("📢 بث للقروبات", callback_data="bot_broadcast_groups"),
        types.InlineKeyboardButton("✉️ رسالة لمستخدم", callback_data="bot_broadcast_user"),
    )
    # ===== الألعاب =====
    markup.add(
        types.InlineKeyboardButton("🎮 الألعاب", callback_data="dev_games_menu", style="success"),
    )
    markup.add(
        types.InlineKeyboardButton("🎌 إدارة الأنمي", callback_data="manage_anime", style="success"),
        types.InlineKeyboardButton("⚽ إدارة اللاعبين", callback_data="manage_players", style="success"),
    )
    # ===== النظام =====
    markup.add(
        types.InlineKeyboardButton("⏸️ وضع الصيانة", callback_data="bot_maintenance"),
        types.InlineKeyboardButton("💾 نسخة احتياطية", callback_data="bot_backup"),
    )
    markup.add(
        types.InlineKeyboardButton("📜 سجل الأخطاء", callback_data="bot_error_log"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ أضف البوت لقروب", url="https://t.me/ri5xbot?startgroup=true"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="bot_add_admin"),
        types.InlineKeyboardButton("👥 الأدمنية", callback_data="bot_list_admins"),
    )
    markup.add(types.InlineKeyboardButton("⚙️ صلاحيات الأدمن", callback_data="bot_admin_permissions"))
    markup.add(
        types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"),
    )
    return markup


# ========= نظام البنك والأموال =========
@bot.message_handler(func=lambda m: m.text and m.text.startswith("انشاء حساب بنكي"))
def create_bank_account(message):
    user_id = message.from_user.id
    banking = ensure_banking()
    
    if str(user_id) in banking["users"]:
        bot.reply_to(message, "⚠️ لديك حساب بنكي بالفعل!")
        return
    
    # إنشاء لوحة اختيار نوع البطاقة
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("فيزا", callback_data="create_card_visa", style="primary")   # أزرق
    btn2 = types.InlineKeyboardButton("ماستر كارد", callback_data="create_card_master", style="success")  # أخضر
    btn3 = types.InlineKeyboardButton("كي كارد", callback_data="create_card_key", style="danger")  # أحمر
    markup.add(btn1, btn2, btn3)
    
    bot.reply_to(message, 
        "• عشان تسوي حساب لازم تختار نوع البطاقة\n\n"
        "↤︎ فيزا ↤︎ ماستر كارد ↤︎ كي كارد\n\n"
        "· اضغط للاختيار",
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('create_card_'))
def handle_card_choice(call):
    user_id = call.from_user.id
    banking = ensure_banking()
    
    if str(user_id) in banking["users"]:
        bot.answer_callback_query(call.id, "⚠️ لديك حساب بنكي بالفعل!")
        return
    
    card_type = call.data.replace('create_card_', '')
    card_types = {
        'visa': {'name': 'فيزا', 'bank': '2'},
        'master': {'name': 'ماستر كارد', 'bank': '1'}, 
        'key': {'name': 'كي كارد', 'bank': '3'}
    }
    
    if card_type not in card_types:
        bot.answer_callback_query(call.id, "⚠️ نوع البطاقة غير صحيح!")
        return
    
    bank_choice = card_types[card_type]['bank']
    bank = BANKS[bank_choice]
    
    user_data = {
        "bank_name": bank["name"],
        "account_number": generate_account_number(),
        "balance": 1000,
        "inventory": {},
        "daily_bonus_claimed": None,
        "salary_claimed": None,
        "bank_card": {
            "card_number": generate_card_number(),
            "expiry_date": f"{random.randint(1,12)}/{random.randint(23,30)}",
            "cvv": generate_cvv(),
            "type": bank["type"]
        },
        "last_salary_claim": 0,
        "last_luck_claim": 0,
        "last_invest_claim": 0,
        "zarf_count": 0,
        "zarf_total": 0
    }
    # إذا كان عنده رصيد محفوظ في نفس البنك يرجعله
    saved_balances = banking.get("bank_balances", {}).get(str(user_id), {})
    if bank["name"] in saved_balances:
        user_data["balance"] = saved_balances[bank["name"]]
    
    banking["users"][str(user_id)] = user_data
    save_db()
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ <b>تم إنشاء حسابك في {bank['name']}</b>\n"
             f"رقم حسابك: <code>{user_data['account_number']}</code>\n"
             f"رصيدك الأولي: <b>1,000 دولار</b> 💵\n\n"
             f"💳 <b>بطاقتك البنكية:</b>\n"
             f"الرقم: <code>{user_data['bank_card']['card_number']}</code>\n"
             f"الانتهاء: {user_data['bank_card']['expiry_date']}\n"
             f"CVV: <code>{user_data['bank_card']['cvv']}</code>\n"
             f"النوع: {user_data['bank_card']['type']}"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("فلوسي"))
def check_balance(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    bot.reply_to(message,
        f"💰 <b>فلوسك الحالية:</b>\n"
        f"الرصيد: <b>{user_data['balance']: ,} دولار</b> 💵"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("حسابي"))
def my_account(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    try:
        user_info = bot.get_chat(user_id)
        username = f"@{user_info.username}" if user_info.username else "بدون يوزر"
        name = human_name(user_info)
    except:
        username = "غير معروف"
        name = "غير معروف"
    zarf_count = user_data.get("zarf_count", 0)
    zarf_total = user_data.get("zarf_total", 0)
    card_num = user_data['bank_card']['card_number']
    bot.reply_to(message,
        f"🏦 <b>معلومات حسابك البنكي:</b>\n\n"
        f"• الاسم ↢ {name}\n"
        f"• الحساب ↢ <code>{user_data['account_number']}</code>\n"
        f"• بنك ↢ {user_data['bank_name']}\n"
        f"• نوع ↢ {user_data['bank_card']['type']}\n"
        f"• الرصيد ↢  {user_data['balance']:,} دولار 💸\n"
        f"• البطاقة ↢ <code>{card_num}</code>\n"
        f"• اليوزر ↢ {username}\n"
        f"• عدد الزرف ↢ {zarf_count} مرة\n"
        f"• إجمالي المزروف ↢  {zarf_total:,} دولار"
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_card_"))
def copy_card_callback(call):
    uid = call.data.replace("copy_card_", "")
    banking = ensure_banking()
    user_data = banking["users"].get(uid)
    if user_data:
        card = user_data['bank_card']['card_number']
        bot.answer_callback_query(call.id, f"✅ تم نسخ: {card}", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⚠️ لم يتم العثور على البطاقة")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "مسح حسابي")
def delete_bank_account(message):
    user_id = message.from_user.id
    banking = ensure_banking()
    uid_str = str(user_id)
    if uid_str not in banking["users"]:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي أصلاً.")
        return
    user_data = banking["users"][uid_str]
    bank_name = user_data.get("bank_name", "")
    # حفظ الرصيد في سجل البنوك بدل الحذف الكامل
    if "bank_balances" not in banking:
        banking["bank_balances"] = {}
    if uid_str not in banking["bank_balances"]:
        banking["bank_balances"][uid_str] = {}
    banking["bank_balances"][uid_str][bank_name] = user_data.get("balance", 0)
    # مسح الحساب — الفلوس محفوظة في سجل البنوك
    del banking["users"][uid_str]
    save_db()
    bot.reply_to(message,
        f"✅ تم مسح حسابك في <b>{bank_name}</b>.\n"
        f"• فلوسك محفوظة — إذا رجعت لنفس البنك ترجعلك.\n"
        f"• ما يقدر أحد يزرفك الحين.\n"
        f"• تقدر تنشئ حساب جديد بأي وقت."
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("رصيدي"))
def check_balance_full(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    bot.reply_to(message,
        f"🏦 <b>رصيدك في {user_data['bank_name']}</b>\n"
        f"رقم الحساب: <code>{user_data['account_number']}</code>\n"
        f"الرصيد: <b>{user_data['balance']: ,} دولار</b> 💵\n"
        f"البطاقة: <code>{user_data['bank_card']['card_number']}</code>"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("ممتلكاتي"))
def my_properties(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    if not user_data.get("inventory"):
        bot.reply_to(message, "📦 <b>ليس لديك أي ممتلكات بعد</b>\n\nاستخدم 'شراء' لشراء ممتلكات جديدة.")
        return
    
    categories = {}
    total_value = 0
    
    for item_name, quantity in user_data["inventory"].items():
        if item_name in ITEMS:
            item = ITEMS[item_name]
            category = item["category"]
            item_value = item["price"] * quantity
            total_value += item_value
            
            if category not in categories:
                categories[category] = []
            
            categories[category].append({
                "name": item_name,
                "quantity": quantity,
                "value": item_value,
                "emoji": item["emoji"]
            })
    
    properties_text = "🏰 <b>ممتلكاتك:</b>\n\n"
    
    for category, items in categories.items():
        properties_text += f"📁 <b>{category}</b>\n"
        for item in items:
            properties_text += f"   {item['emoji']} {item['name']} × {item['quantity']} - {item['value']: ,} دولار\n"
        properties_text += "\n"
    
    properties_text += f"💰 <b>القيمة الاجمالية للممتلكات:</b> {total_value: ,} دولار\n"
    properties_text += f"💵 <b>رصيدك النقدي:</b> {user_data['balance']: ,} دولار\n"
    properties_text += f"🏦 <b>إجمالي ثروتك:</b> {total_value + user_data['balance']: ,} دولار"
    
    bot.reply_to(message, properties_text)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("يومي"))
def daily_bonus(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_data["daily_bonus_claimed"] == today:
        bot.reply_to(message, "⚠️ لقد حصلت على المكافأة اليومية بالفعل! عد غداً.")
        return
    
    bonus = random.randint(100, 1000)
    user_data["balance"] += bonus
    user_data["daily_bonus_claimed"] = today
    
    banking = ensure_banking()
    banking["users"][str(user_id)] = user_data
    save_db()
    
    bot.reply_to(message, f"🎉 <b>مكافأة يومية!</b>\nلقد حصلت على <b>{bonus} دولار</b> 💵\nرصيدك الجديد: <b>{user_data['balance']: ,} دولار</b>")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("راتب"))
def salary(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    if user_data["balance"] >= MAX_MONEY:
        bot.reply_to(message, "💎 فلوسك ماكس ما تقدر تزيدهم!")
        return
    now = time.time()
    last_claimed = user_data.get("last_salary_claim", 0)
    if now - last_claimed < 600:
        remaining = int(600 - (now - last_claimed))
        bot.reply_to(message, f"⏰ يجب الانتظار {remaining//60} دقائق و{remaining%60} ثواني")
        return
    job_name = random.choice(list(JOBS.keys()))
    job = JOBS[job_name]
    salary_amount = random.randint(job["min_salary"], job["max_salary"])
    user_data["balance"] = min(MAX_MONEY, user_data["balance"] + salary_amount)
    user_data["last_salary_claim"] = now
    banking = ensure_banking()
    banking["users"][str(user_id)] = user_data
    save_db()
    bot.reply_to(message,
        f"🎉 <b>حصلت على وظيفة {job_name} {job['emoji']}</b>\n"
        f"الراتب: <b>{salary_amount:,} دولار</b> 💵\n"
        f"رصيدك: <b>{user_data['balance']:,} دولار</b>\n"
        f"⏰ يمكنك الحصول على الراتب بعد 10 دقائق"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("مخزني"))
def check_inventory(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    if not user_data["inventory"]:
        bot.reply_to(message, "📦 <b>المخزون فارغ</b>\nليس لديك أي عناصر في المخزون.")
        return
    
    inventory_text = "📦 <b>مخزونك:</b>\n\n"
    total_value = 0
    
    for item_name, quantity in user_data["inventory"].items():
        if item_name in ITEMS:
            item = ITEMS[item_name]
            item_value = item["price"] * quantity
            total_value += item_value
            inventory_text += f"{item['emoji']} {item_name} × {quantity} - {item_value: ,} دولار\n"
    
    inventory_text += f"\n💰 <b>القيمة الاجمالية:</b> {total_value: ,} دولار"
    
    bot.reply_to(message, inventory_text)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("شراء"))
def buy_item(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    text_parts = message.text.split()
    if len(text_parts) < 3:
        bot.reply_to(message, "⚠️ الاستخدام الصحيح: 'شراء [الكمية] [اسم المنتج]'")
        return
    
    try:
        quantity = int(text_parts[1])
    except:
        bot.reply_to(message, "⚠️ الكمية يجب أن تكون رقماً صحيحاً.")
        return
    
    item_name = " ".join(text_parts[2:])
    
    if item_name not in ITEMS:
        available_items = "\n".join([f"- {name} ({ITEMS[name]['price']} دولار)" for name in ITEMS.keys()])
        bot.reply_to(message, f"⚠️ العنصر غير موجود. العناصر المتاحة:\n{available_items}")
        return
    
    item = ITEMS[item_name]
    total_cost = item["price"] * quantity
    
    if user_data["balance"] < total_cost:
        bot.reply_to(message, f"⚠️ رصيدك غير كافي. تحتاج إلى {total_cost: ,} دولار، ورصيدك هو {user_data['balance']: ,} دولار.")
        return
    
    user_data["balance"] -= total_cost
    if item_name in user_data["inventory"]:
        user_data["inventory"][item_name] += quantity
    else:
        user_data["inventory"][item_name] = quantity
    
    banking = ensure_banking()
    banking["users"][str(user_id)] = user_data
    save_db()
    
    bot.reply_to(message,
        f"✅ <b>تم الشراء بنجاح!</b>\n"
        f"اشتريت {quantity} × {item_name} {item['emoji']}\n"
        f"التكلفة: {total_cost: ,} دولار 💵\n"
        f"رصيدك الجديد: {user_data['balance']: ,} دولار"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("بيع"))
def sell_item(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    text_parts = message.text.split()
    if len(text_parts) < 3:
        bot.reply_to(message, "⚠️ الاستخدام الصحيح: 'بيع [الكمية] [اسم المنتج]'")
        return
    
    try:
        quantity = int(text_parts[1])
    except:
        bot.reply_to(message, "⚠️ الكمية يجب أن تكون رقماً صحيحاً.")
        return
    
    item_name = " ".join(text_parts[2:])
    
    if item_name not in user_data["inventory"] or user_data["inventory"][item_name] < quantity:
        bot.reply_to(message, f"⚠️ ليس لديك كمية كافية من {item_name}.")
        return
    
    if item_name not in ITEMS:
        bot.reply_to(message, f"⚠️ لا يمكن بيع {item_name} لأنه غير معروف في السوق.")
        return
    
    item = ITEMS[item_name]
    original_value = item["price"] * quantity
    refund_amount = int(original_value * 0.6)
    
    user_data["balance"] += refund_amount
    user_data["inventory"][item_name] -= quantity
    
    if user_data["inventory"][item_name] == 0:
        del user_data["inventory"][item_name]
    
    banking = ensure_banking()
    banking["users"][str(user_id)] = user_data
    save_db()
    
    bot.reply_to(message,
        f"✅ <b>تم البيع بنجاح!</b>\n"
        f"بعت {quantity} × {item_name} {item['emoji']}\n"
        f"القيمة الأصلية: {original_value: ,} دولار\n"
        f"قيمة الاسترداد: {refund_amount: ,} دولار (60%)\n"
        f"رصيدك الجديد: {user_data['balance']: ,} دولار"
    )

@bot.message_handler(func=lambda m: m.text and (m.text.strip() == "حظ فلوسي" or (m.text.startswith("حظ ") and len(m.text.split()) == 2 and m.text.split()[1].isdigit())))
def luck_money(message):
    user_id = message.from_user.id
    banking = ensure_banking()
    user_data = banking["users"].get(str(user_id))
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    if user_data["balance"] >= MAX_MONEY:
        bot.reply_to(message, "💎 فلوسك ماكس ما تقدر تزيدهم!")
        return
    now = time.time()
    if now - user_data.get("last_luck_claim", 0) < 1200:
        remaining = int(1200 - (now - user_data.get("last_luck_claim", 0)))
        bot.reply_to(message, f"⏰ يجب الانتظار {remaining//60} دقائق و{remaining%60} ثواني")
        return
    text = message.text.strip()
    # حظ فلوسي = كل الفلوس | حظ [رقم] = مبلغ محدد
    if text == "حظ فلوسي":
        amount = user_data["balance"]
    else:
        amount = int(text.split()[1])
    if amount <= 0 or user_data["balance"] < amount:
        bot.reply_to(message, "⚠️ المبلغ غير صالح أو رصيدك غير كافي.")
        return
    proximity = min(1.0, user_data["balance"] / MAX_MONEY)
    win_chance = max(10, int(65 - proximity * 55))
    max_mult = max(1.01, 2.5 - proximity * 2.0)
    multiplier = random.uniform(0.01, max_mult)
    if random.randint(1, 100) <= win_chance:
        win = int(amount * multiplier)
        user_data["balance"] = min(MAX_MONEY, user_data["balance"] + win)
        pct = round(multiplier * 100, 1)
        result_text = f"🎰 <b>مبروك! فزت بـ {win:,} دولار</b>\n📊 النسبة: <b>+{pct}%</b>"
    else:
        user_data["balance"] = max(0, user_data["balance"] - amount)
        result_text = f"💔 <b>خسرت {amount:,} دولار</b>\n📊 النسبة: <b>-100%</b>"
        if user_data["balance"] == 0:
            result_text += "\n😢 رصيدك الآن 0"
    user_data["last_luck_claim"] = now
    banking["users"][str(user_id)] = user_data
    save_db()
    bot.reply_to(message, f"{result_text}\nرصيدك: <b>{user_data['balance']:,} دولار</b>\n⏰ مرة أخرى بعد 20 دقيقة")

@bot.message_handler(func=lambda m: m.text and (m.text.strip() == "استثمار كل فلوسي" or (m.text.startswith("استثمار ") and len(m.text.split()) == 2 and m.text.split()[1].isdigit())))
def invest_money(message):
    user_id = message.from_user.id
    banking = ensure_banking()
    user_data = banking["users"].get(str(user_id))
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    if user_data["balance"] >= MAX_MONEY:
        bot.reply_to(message, "💎 فلوسك ماكس ما تقدر تزيدهم!")
        return
    now = time.time()
    if now - user_data.get("last_invest_claim", 0) < 1200:
        remaining = int(1200 - (now - user_data.get("last_invest_claim", 0)))
        bot.reply_to(message, f"⏰ يجب الانتظار {remaining//60} دقائق و{remaining%60} ثواني")
        return
    text = message.text.strip()
    # استثمار كل فلوسي = كل الفلوس | استثمار [رقم] = مبلغ محدد
    if text == "استثمار كل فلوسي":
        amount = user_data["balance"]
    else:
        amount = int(text.split()[1])
    if amount <= 0 or user_data["balance"] < amount:
        bot.reply_to(message, "⚠️ المبلغ غير صالح أو رصيدك غير كافي.")
        return
    proximity = min(1.0, user_data["balance"] / MAX_MONEY)
    win_chance = max(10, int(70 - proximity * 60))
    max_mult = max(1.01, 2.5 - proximity * 2.0)
    multiplier = random.uniform(0.01, max_mult)
    if random.randint(1, 100) <= win_chance:
        profit = int(amount * multiplier)
        user_data["balance"] = min(MAX_MONEY, user_data["balance"] + profit)
        pct = round(multiplier * 100, 1)
        result_text = f"📈 <b>استثمار ناجح! ربحت {profit:,} دولار</b>\n📊 النسبة: <b>+{pct}%</b>"
        if user_data["balance"] >= MAX_MONEY:
            result_text += "\n🎯 <b>وصلت الحد الأقصى!</b>"
    else:
        user_data["balance"] = max(0, user_data["balance"] - amount)
        result_text = f"📉 <b>استثمار فاشل! خسرت {amount:,} دولار</b>\n📊 النسبة: <b>-100%</b>"
        if user_data["balance"] == 0:
            result_text += "\n😢 رصيدك الآن 0"
    user_data["last_invest_claim"] = now
    banking["users"][str(user_id)] = user_data
    save_db()
    bot.reply_to(message, f"{result_text}\nرصيدك: <b>{user_data['balance']:,} دولار</b>\n⏰ مرة أخرى بعد 20 دقيقة")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("هدية مطور"))
def developer_gift(message):
    user_id = message.from_user.id
    
    if user_id != BOT_OWNER_ID:
        bot.reply_to(message, "⛔ هذا الأمر مخصص فقط لمطور البوت!")
        return
    
    target_id = None
    target_username = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        text_parts = message.text.split()
        if len(text_parts) >= 3 and text_parts[2].startswith("@"):
            target_username = text_parts[2].replace('@', '')
            for chat_id, chat_data in DB.items():
                if chat_id.isdigit() and "known_users" in chat_data:
                    if target_username in chat_data["known_users"]:
                        target_id = chat_data["known_users"][target_username]
                        break
    
    if not target_id:
        bot.reply_to(message, "⚠️ يجب الرد على رسالة المستخدم أو كتابة 'هدية مطور @username'")
        return
    
    banking = ensure_banking()
    target_id_str = str(target_id)
    
    if target_id_str not in banking["users"]:
        bank_choice = "1"
        bank = BANKS[bank_choice]
        
        banking["users"][target_id_str] = {
            "bank_name": bank["name"],
            "account_number": generate_account_number(),
            "balance": MAX_MONEY,
            "inventory": {},
            "daily_bonus_claimed": None,
            "salary_claimed": None,
            "bank_card": {
                "card_number": generate_card_number(),
                "expiry_date": f"{random.randint(1,12)}/{random.randint(23,30)}",
                "cvv": generate_cvv(),
                "type": bank["type"]
            },
            "last_salary_claim": 0,
            "last_luck_claim": 0,
            "last_invest_claim": 0
        }
    else:
        banking["users"][target_id_str]["balance"] = MAX_MONEY
    
    save_db()
    
    if not target_username:
        target_username = f"user_{target_id}"
        for chat_id, chat_data in DB.items():
            if chat_id.isdigit() and "known_users" in chat_data:
                for uname, uid in chat_data["known_users"].items():
                    if uid == target_id:
                        target_username = uname
                        break
    
    bot.reply_to(message, f"🎁 <b>تم منح هدية المطور لـ @{target_username}</b>\n\nتم منح أعلى مستوى للفلوس: <b>{MAX_MONEY: ,} دولار</b> 💰")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("توب الفلوس"))
def money_top(message):
    banking = ensure_banking()
    
    if not banking["users"]:
        bot.reply_to(message, "📊 <b>لا يوجد مستخدمين في النظام بعد</b>")
        return
    
    user_wealth = []
    
    for user_id_str, user_data in banking["users"].items():
        user_id = int(user_id_str)
        total_wealth = user_data["balance"]
        
        if user_data.get("inventory"):
            for item_name, quantity in user_data["inventory"].items():
                if item_name in ITEMS:
                    total_wealth += ITEMS[item_name]["price"] * quantity
        
        username = f"user_{user_id}"
        name = "غير معروف"
        
        # البحث عن اسم المستخدم في جميع المجموعات
        for chat_id, chat_data in DB.items():
            if chat_id.isdigit() and "known_users" in chat_data:
                for uname, uid in chat_data["known_users"].items():
                    if uid == user_id:
                        username = f"@{uname}"
                        try:
                            user_info = bot.get_chat(user_id)
                            name = human_name(user_info)
                        except:
                            pass
                        break
        
        user_wealth.append({
            "user_id": user_id,
            "username": username,
            "name": name,
            "wealth": total_wealth
        })
    
    user_wealth.sort(key=lambda x: x["wealth"], reverse=True)
    
    top_text = "🏆 <b>توب أغنى 30 شخص في النظام:</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, user in enumerate(user_wealth[:30]):
        if i < 3:
            rank_emoji = medals[i]
        else:
            rank_emoji = f"{i+1}."
        
        top_text += f"{rank_emoji} {user['name']} ({user['username']}) - <b>{user['wealth']: ,} دولار</b>\n"
    
    total_users = len(user_wealth)
    total_wealth = sum(user["wealth"] for user in user_wealth)
    avg_wealth = total_wealth // total_users if total_users > 0 else 0
    
    top_text += f"\n📈 <b>الاحصائيات:</b>\n"
    top_text += f"• عدد المستخدمين: {total_users}\n"
    top_text += f"• إجمالي الثروة في النظام: {total_wealth: ,} دولار\n"
    top_text += f"• متوسط الثروة: {avg_wealth: ,} دولار"
    
    bot.reply_to(message, top_text)

# ========= نظام التحويل =========
transfer_requests = {}

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تحويل"))
def transfer_money_step1(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    text_parts = message.text.split()
    if len(text_parts) < 2:
        bot.reply_to(message, "⚠️ الاستخدام: تحويل [المبلغ]")
        return
    try:
        amount = int(text_parts[1])
    except:
        bot.reply_to(message, "⚠️ المبلغ يجب أن يكون رقماً.")
        return
    if amount <= 0:
        bot.reply_to(message, "⚠️ المبلغ يجب أن يكون أكبر من الصفر.")
        return
    if user_data["balance"] < amount:
        bot.reply_to(message, f"⚠️ فلوسك قليلة. رصيدك: <b>{user_data['balance']:,} دولار</b>")
        return
    transfer_requests[user_id] = {"amount": amount, "timestamp": time.time()}
    bot.reply_to(message, f"💳 المبلغ: <b>{amount:,} دولار</b>\n\nأرسل رقم حساب الشخص اللي تبي تحوله")

@bot.message_handler(func=lambda m: m.text and m.from_user.id in transfer_requests and m.text.strip().isdigit())
def transfer_money_step2(message):
    user_id = message.from_user.id
    if user_id not in transfer_requests:
        return
    request = transfer_requests[user_id]
    if time.time() - request["timestamp"] > 300:
        del transfer_requests[user_id]
        bot.reply_to(message, "⏰ انتهت صلاحية طلب التحويل.")
        return
    account_number = message.text.strip()
    banking = ensure_banking()
    # البحث عن صاحب الحساب
    target_id_str = None
    for uid_str, udata in banking["users"].items():
        if udata.get("account_number") == account_number:
            target_id_str = uid_str
            break
    if not target_id_str:
        bot.reply_to(message, "⚠️ رقم الحساب غير صحيح.")
        return
    if target_id_str == str(user_id):
        bot.reply_to(message, "⚠️ لا تقدر تحوّل لنفسك.")
        return
    user_data = get_user_bank_data(user_id)
    amount = request["amount"]
    transfer_fee = int(amount * 0.08)
    total = amount + transfer_fee
    if user_data["balance"] < total:
        del transfer_requests[user_id]
        bot.reply_to(message, f"⚠️ رصيدك غير كافي بعد رسوم التحويل (8%). تحتاج: <b>{total:,}</b>")
        return
    target_data = banking["users"][target_id_str]
    user_data["balance"] -= total
    target_data["balance"] += amount
    save_db()
    # إشعار للمستلم
    try:
        sender_name = f"@{message.from_user.username}" if message.from_user.username else human_name(message.from_user)
        bot.send_message(int(target_id_str), f"💰 <b>استلمت تحويل!</b>\nالمبلغ: <b>{amount:,} دولار</b>\nمن: {sender_name}\nرصيدك: <b>{target_data['balance']:,}</b>")
    except:
        pass
    del transfer_requests[user_id]
    bot.reply_to(message,
        f"✅ <b>تم التحويل بنجاح!</b>\n"
        f"المبلغ: <b>{amount:,} دولار</b>\n"
        f"رسوم: <b>{transfer_fee:,} دولار</b> (8%)\n"
        f"رصيدك: <b>{user_data['balance']:,} دولار</b>"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("بطاقتي"))
def my_card(message):
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    bot.reply_to(message,
        f"💳 <b>بطاقتك البنكية - {user_data['bank_name']}</b>\n\n"
        f"رقم البطاقة: <code>{user_data['bank_card']['card_number']}</code>\n"
        f"تاريخ الانتهاء: {user_data['bank_card']['expiry_date']}\n"
        f"CVV: <code>{user_data['bank_card']['cvv']}</code>\n"
        f"النوع: {user_data['bank_card']['type']}\n"
        f"رقم الحساب: <code>{user_data['account_number']}</code>\n"
        f"الرصيد: <b>{user_data['balance']: ,} دولار</b> 💵"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تصفير فلوسي"))
def reset_my_money(message):
    user_id = message.from_user.id
    banking = ensure_banking()
    user_id_str = str(user_id)
    
    if user_id_str not in banking["users"]:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي.")
        return
    
    banking["users"][user_id_str]["balance"] = 0
    banking["users"][user_id_str]["inventory"] = {}
    
    save_db()
    
    bot.reply_to(message, "✅ تم تصفير فلوسك وممتلكاتك بنجاح. الرصيد الآن: 0 دولار")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تصفير توب الفلوس"))
def reset_all_money(message):
    user_id = message.from_user.id
    
    if user_id != BOT_OWNER_ID:
        bot.reply_to(message, "⛔ هذا الأمر مخصص فقط لمطور البوت!")
        return
    
    banking = ensure_banking()
    
    for user_id_str, user_data in banking["users"].items():
        user_data["balance"] = 0
        user_data["inventory"] = {}
    
    save_db()
    
    bot.reply_to(message, "✅ تم تصفير جميع فلوس وممتلكات جميع المستخدمين بنجاح")

# ========= أمر متجر العالمي =========
@bot.message_handler(func=lambda m: m.text and m.text.startswith("متجر العالمي"))
def global_store(message):
    store_text = "🌍 <b>متجر العالمي - جميع العناصر:</b>\n\n"
    
    # ترتيب العناصر حسب السعر (من الأغلى للأرخص)
    sorted_items = sorted(ITEMS.items(), key=lambda x: x[1]["price"], reverse=True)
    
    # عرض العناصر مصنفة ومرتبة
    categories = {}
    for item_name, item_data in sorted_items:
        category = item_data["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append((item_name, item_data))
    
    for category, items in categories.items():
        store_text += f"📁 <b>{category}</b>\n"
        for item_name, item_data in items:
            store_text += f"   {item_data['emoji']} <b>{item_name}</b> - {item_data['price']: ,} دولار\n"
        store_text += "\n"
    
    store_text += "💡 <b>طريقة الشراء:</b>\n"
    store_text += "اكتب: <code>شراء [الكمية] [اسم المنتج]</code>\n"
    store_text += "مثال: <code>شراء 2 ايفون</code>\n\n"
    store_text += "💰 <b>أغلى 5 عناصر:</b>\n"
    
    # عرض أغلى 5 عناصر
    top_5 = sorted_items[:5]
    for i, (item_name, item_data) in enumerate(top_5, 1):
        store_text += f"{i}. {item_data['emoji']} {item_name} - {item_data['price']: ,} دولار\n"
    
    bot.reply_to(message, store_text)

# ========= أمر المتجر العادي =========
@bot.message_handler(func=lambda m: m.text and m.text.startswith("المتجر"))
def show_store(message):
    store_text = "🛒 <b>المتجر - العناصر الشائعة:</b>\n\n"
    
    # عرض العناصر الشائعة فقط
    popular_items = [
        "ايفون", "سامسونج", "تويوتa", "تيسلا", "شقة", "فيلا",
        "طائرة خاصة", "يخت فاخر", "خاتم الماس", "ساعة رولكس"
    ]
    
    categories = {}
    for item_name in popular_items:
        if item_name in ITEMS:
            item_data = ITEMS[item_name]
            category = item_data["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append((item_name, item_data))
    
    for category, items in categories.items():
        store_text += f"📁 <b>{category}</b>\n"
        for item_name, item_data in items:
            store_text += f"   {item_data['emoji']} <b>{item_name}</b> - {item_data['price']: ,} دولار\n"
        store_text += "\n"
    
    store_text += "💡 <b>طريقة الشراء:</b>\n"
    store_text += "اكتب: <code>شراء [الكمية] [اسم المنتج]</code>\n"
    store_text += "مثال: <code>شراء 2 ايفون</code>\n\n"
    store_text += "🌍 لرؤية جميع العناصر اكتب: <code>متجر العالمي</code>"
    
    bot.reply_to(message, store_text)

# ========= نظام الزرف =========
@bot.message_handler(func=lambda m: m.text and m.text.startswith("زرف"))
def zarf_command(message):
    if not is_group(message):
        return
    
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    target_username = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            target_username = parts[1].replace('@', '')
            target_id = find_user_id_by_username(message.chat.id, target_username)
    
    if not target_id:
        bot.reply_to(message, "⚠️ يجب الرد على رسالة المستخدم أو ذكر اليوزر بعد الأمر.")
        return
    
    if target_id == user_id:
        bot.reply_to(message, "⚠️ لا يمكنك زرف نفسك!")
        return
    
    try:
        target_member = bot.get_chat_member(message.chat.id, target_id)
        target_user = target_member.user
        if not target_username:
            target_username = target_user.username or str(target_id)
    except:
        bot.reply_to(message, "⛔ لم أتمكن العثور على المستخدم.")
        return
    
    # تنفيذ الزرف
    success, action, result = zarf_user(message.chat.id, user_id, target_id)
    
    if success:
        # تحديث إحصائيات الزرف
        user_data["zarf_count"] = user_data.get("zarf_count", 0) + 1
        user_data["zarf_total"] = user_data.get("zarf_total", 0) + result
        
        banking = ensure_banking()
        banking["users"][str(user_id)] = user_data
        save_db()
        
        bot.reply_to(message, f"✅ <b>تم الزرف بنجاح!</b>\nسرقت <b>{result: ,} دولار</b> من @{target_username}\nرصيدك الجديد: <b>{user_data['balance']: ,} دولار</b>")
    else:
        bot.reply_to(message, f"❌ <b>فشل في الزرف:</b> {result}")

# ========= لعبة الترجمة (انق) =========
TRANSLATION_WORDS = {
    "house": "منزل", "school": "مدرسة", "wind": "ريح", "rain": "مطر",
    "water": "ماء", "car": "سيارة", "fan": "معجب", "country": "دولة",
    "time": "وقت", "sun": "شمس", "moon": "قمر", "star": "نجمة",
    "dog": "كلب", "cat": "قطة", "fish": "سمكة", "bird": "طائر",
    "tree": "شجرة", "flower": "زهرة", "book": "كتاب", "door": "باب",
    "fire": "نار", "ice": "جليد", "sand": "رمل", "road": "طريق",
    "bridge": "جسر", "river": "نهر", "mountain": "جبل", "sky": "سماء",
    "cloud": "سحابة", "storm": "عاصفة", "heart": "قلب", "hand": "يد",
    "eye": "عين", "nose": "أنف", "ear": "أذن", "head": "رأس",
    "food": "طعام", "milk": "حليب", "bread": "خبز", "egg": "بيضة",
    "chair": "كرسي", "table": "طاولة", "bed": "سرير", "wall": "جدار",
    "phone": "هاتف", "computer": "حاسوب", "pen": "قلم", "bag": "حقيبة",
    "key": "مفتاح", "clock": "ساعة", "ball": "كرة", "game": "لعبة",
    "music": "موسيقى", "color": "لون", "black": "أسود", "white": "أبيض",
    "red": "أحمر", "blue": "أزرق", "green": "أخضر", "yellow": "أصفر",
    "big": "كبير", "small": "صغير", "fast": "سريع", "slow": "بطيء",
    "happy": "سعيد", "sad": "حزين", "hot": "حار", "cold": "بارد",
    "love": "حب", "dream": "حلم", "hope": "أمل", "friend": "صديق",
    "family": "عائلة", "city": "مدينة", "village": "قرية", "sea": "بحر",
    "ship": "سفينة", "plane": "طائرة", "train": "قطار", "bike": "دراجة",
    "gold": "ذهب", "silver": "فضة", "money": "مال", "king": "ملك",
    "queen": "ملكة", "army": "جيش", "war": "حرب", "peace": "سلام",
    "night": "ليل", "day": "نهار", "week": "أسبوع", "year": "سنة",
    "baby": "طفل", "boy": "ولد", "girl": "بنت", "man": "رجل", "woman": "امرأة"
}

# {user_id: {"word": ..., "answer": ..., "chat_id": ...}}
anaq_sessions = {}

# قائمة الأوامر اللي تتجاوز الانق
ANAQ_BYPASS = {
    "توب","تعليمات","رتبتي","معلوماتي","حسابي","رصيدي","راتب","يومي",
    "فلوسي","فف","ادمن","انق","تفعيل البوت","تفعيل اليوتيوب","بطاقتي","ممتلكاتي",
    "مخزني","زوجتي","زوجاتي","طلاق","تصفير التوب","المتجر","متجر العالمي"
}

def is_anaq_bypass(text):
    if text in ANAQ_BYPASS:
        return True
    for prefix in ["حظ","استثمار","تحويل","شراء","بيع","زرف","زواج","حظر",
                   "رفع","تقييد","كتم","انذار","اعطاء","سحب","هدية","توب الفلوس",
                   "مسح","رفع القيود","رفع التقييد","رفع الحظر","رفع الكتم"]:
        if text.startswith(prefix):
            return True
    return False

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "انق")
def translation_game(message):
    user_id = message.from_user.id
    add_interaction(message.chat.id, user_id)
    word_en, word_ar = random.choice(list(TRANSLATION_WORDS.items()))
    anaq_sessions[user_id] = {"word": word_en, "answer": word_ar, "chat_id": message.chat.id}
    bot.reply_to(message, f"🎯 <b>انق</b>\n\nترجم هذه الكلمة للعربية:\n<b>{word_en}</b>")

# ========= لعبة الأحكام =========
judgment_games = {}

@bot.message_handler(func=lambda m: m.text and m.text.startswith("احكام"))
def judgment_game_start(message):
    if not is_group(message):
        bot.reply_to(message, "⚠️ هذه اللعبة تعمل فقط في المجموعات.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    add_interaction(chat_id, user_id)
    
    if chat_id in judgment_games:
        bot.reply_to(message, "⚠️ هناك لعبة أحكام نشطة بالفعل في هذه المجموعة.")
        return
    
    judgment_games[chat_id] = {
        "players": [user_id],
        "judge": None,
        "accused": None,
        "status": "waiting"
    }
    
    bot.reply_to(message, "🧑‍⚖️ <b>لعبة الأحكام</b>\n\nتم بدء لعبة الأحكام\nاكتب 'انا' للانضمام إلى اللعبة")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("انا") and is_group(m))
def judgment_join(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    add_interaction(chat_id, user_id)
    
    if chat_id not in judgment_games:
        return
    
    game = judgment_games[chat_id]
    
    if user_id in game["players"]:
        bot.reply_to(message, "⚠️ أنت منضم بالفعل إلى اللعبة.")
        return
    
    if len(game["players"]) >= 10:
        bot.reply_to(message, "⚠️ اللعبة ممتلئة (10 لاعبين كحد أقصى).")
        return
    
    game["players"].append(user_id)
    bot.reply_to(message, f"✅ <b>تم الانضمام إلى اللعبة!</b>\nعدد اللاعبين: {len(game['players'])}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("نعم") and is_group(m))
def judgment_start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in judgment_games:
        return
    
    game = judgment_games[chat_id]
    
    if user_id != game["players"][0]:
        bot.reply_to(message, "⚠️ فقط من بدأ اللعبة يمكنه بدئها.")
        return
    
    if len(game["players"]) < 2:
        bot.reply_to(message, "⚠️ تحتاج إلى لاعبين على الأقل لبدء اللعبة.")
        return
    
    # اختيار الحكم والمحكوم عشوائياً
    random.shuffle(game["players"])
    game["judge"] = game["players"][0]
    game["accused"] = game["players"][1]
    game["status"] = "started"
    
    try:
        judge_user = bot.get_chat_member(chat_id, game["judge"]).user
        accused_user = bot.get_chat_member(chat_id, game["accused"]).user

        judge_name = wz_mention(game["judge"], human_name(judge_user))
        accused_name = wz_mention(game["accused"], human_name(accused_user))

        bot.reply_to(message,
            f"🧑‍⚖️ <b>بدأت لعبة الأحكام!</b>\n\n"
            f"• الحاكم: {judge_name}\n"
            f"• المحكوم: {accused_name}\n\n"
            f"الحاكم يمكنه الآن إصدار الحكم!\n\n"
            f"⏹️ انتهت هذي الجولة. لبدء جولة جديدة اكتب 'احكام' من جديد ولازم الكل ينضم من جديد."
        )
    except:
        bot.reply_to(message, "❌ حدث خطأ أثناء بدء اللعبة.")
    finally:
        # ===== توقف اللعبة بعد كتابة "نعم": الجولة تخلص وتحتاج "احكام" جديدة + انضمام جديد =====
        judgment_games.pop(chat_id, None)

# ========= نظام الزواج والطلاق =========
@bot.message_handler(func=lambda m: m.text and m.text.startswith("زواج") and not m.text.strip() == "زواجي")
def marriage_command(message):
    if not is_group(message):
        return
    
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي. استخدم 'انشاء حساب بنكي' أولاً.")
        return
    
    parts = message.text.split()
    target_id = None
    target_user = None
    mahr_amount = 0

    # استخراج المهر من النص
    for p in parts[1:]:
        try:
            mahr_amount = int(p)
            break
        except:
            pass

    # الهدف: بالرد أولاً، ثم اليوزر
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
    else:
        for p in parts[1:]:
            if p.startswith("@"):
                uname = p.replace("@", "")
                uid = find_user_id_by_username(message.chat.id, uname)
                if uid:
                    target_id = uid
                    try:
                        target_user = bot.get_chat_member(message.chat.id, uid).user
                    except:
                        pass
                break

    if not target_id:
        bot.reply_to(message, "⚠️ رد على رسالة الشخص اللي تريد تتزوجه، أو اكتب يوزره.\nمثال: <code>زواج 1500</code> مع الرد")
        return

    if target_id == user_id:
        bot.reply_to(message, "⚠️ لا يمكنك الزواج من نفسك!")
        return

    if mahr_amount <= 0:
        bot.reply_to(message, "⚠️ حدد مبلغ المهر.\nمثال: <code>زواج 1500</code> مع الرد على رسالة الشخص")
        return

    if user_data["balance"] < mahr_amount:
        bot.reply_to(message, f"⚠️ رصيدك غير كافي. تحتاج {mahr_amount:,} دولار، رصيدك {user_data['balance']:,} دولار.")
        return

    try:
        if not target_user:
            target_user = bot.get_chat_member(message.chat.id, target_id).user
    except:
        bot.reply_to(message, "⛔ لم أتمكن من العثور على المستخدم.")
        return

    success, result = add_marriage(user_id, target_id, mahr_amount)

    if success:
        user_data["balance"] -= mahr_amount
        banking = ensure_banking()
        banking["users"][str(user_id)] = user_data
        save_db()

        husband_name = human_name(message.from_user)
        wife_name = human_name(target_user)
        bot.reply_to(message,
            f"💍 <b>تمت مراسم الزواج!</b>\n\n"
            f"🤵 الزوج: <a href='tg://user?id={user_id}'>{husband_name}</a>\n"
            f"👰‍♀️ الزوجة: <a href='tg://user?id={target_id}'>{wife_name}</a>\n"
            f"💰 المهر: <b>{mahr_amount:,} دولار</b>\n\n"
            f"🎊 مبروك الزواج!"
        )
    else:
        bot.reply_to(message, f"❌ {result}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("زوجتي"))
def my_wife_command(message):
    user_id = message.from_user.id
    marriages = get_user_marriages(user_id)
    
    if not marriages:
        bot.reply_to(message, "⚠️ ليس لديك أي زوجات.")
        return
    
    wife_info = ""
    for i, marriage in enumerate(marriages, 1):
        wife_id = marriage["wife"]
        try:
            wife_user = bot.get_chat(wife_id)
            wife_name = human_name(wife_user)
        except:
            wife_name = f"user_{wife_id}"
        wife_info += f"👰‍♀️ الزوجة {i}: <a href='tg://user?id={wife_id}'>{wife_name}</a> — مهر: <b>{marriage['mahr']:,} دولار</b>\n"
    
    bot.reply_to(message, f"👰‍♀️ <b>زوجاتك:</b>\n\n{wife_info}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("زوجاتي"))
def my_wives_command(message):
    user_id = message.from_user.id
    marriages = get_user_marriages(user_id)
    
    if not marriages:
        bot.reply_to(message, "⚠️ ليس لديك أي زوجات.")
        return
    
    wives_mention = ""
    for i, marriage in enumerate(marriages, 1):
        wife_id = marriage["wife"]
        try:
            wife_user = bot.get_chat(wife_id)
            wife_name = human_name(wife_user)
        except:
            wife_name = f"user_{wife_id}"
        # اسم قابل للضغط يفتح الحساب
        wives_mention += f"👰‍♀️ الزوجة {i}: <a href='tg://user?id={wife_id}'>{wife_name}</a>\n"
    
    bot.reply_to(message, f"👰‍♀️ <b>زوجاتك</b>\n\n{wives_mention}")

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "زواجي")
def my_marriage_info(message):
    user_id = message.from_user.id
    marriages = get_user_marriages(user_id)
    if not marriages:
        bot.reply_to(message, "⚠️ لست متزوجاً حالياً.")
        return
    for i, marriage in enumerate(marriages, 1):
        wife_id = marriage["wife"]
        try:
            wife_user = bot.get_chat(wife_id)
            wife_name = human_name(wife_user)
        except:
            wife_name = f"user_{wife_id}"
        husband_name = human_name(message.from_user)
        txt = (
            f"📜 <b>هذه عقد زواجكم</b>\n\n"
            f"🤵 الزوج: <a href='tg://user?id={user_id}'>{husband_name}</a>\n"
            f"👰‍♀️ الزوجة {i}: <a href='tg://user?id={wife_id}'>{wife_name}</a>\n"
            f"💰 المهر: <b>{marriage['mahr']:,} دولار</b>"
        )
        bot.reply_to(message, txt)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("خلع"))
def khul_command(message):
    if not is_group(message):
        return
    
    user_id = message.from_user.id
    user_data = get_user_bank_data(user_id)
    
    if not user_data:
        bot.reply_to(message, "⚠️ ليس لديك حساب بنكي.")
        return
    
    target_username = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            target_username = parts[1].replace('@', '')
            target_id = find_user_id_by_username(message.chat.id, target_username)
    
    if not target_id:
        bot.reply_to(message, "⚠️ يجب الرد على رسالة الزوج أو ذكر اليوزر بعد الأمر.")
        return
    
    try:
        target_member = bot.get_chat_member(message.chat.id, target_id)
        target_user = target_member.user
        if not target_username:
            target_username = target_user.username or str(target_id)
    except:
        bot.reply_to(message, "⛔ لم أتمكن العثور على الزوج.")
        return
    
    # تنفيذ الخلع
    success, result = khul_divorce(user_id, target_id)
    
    if success:
        bot.reply_to(message,
            f"✅ <b>تم الخلع بنجاح!</b>\n"
            f"👰‍♀️ المخلوعة: @{message.from_user.username if message.from_user.username else 'مستخدم'}\n"
            f"🤵‍♂️ الزوج السابق: @{target_username}\n"
            f"💰 تم إرجاع المهر: <b>{result: ,} دولار</b> للزوج"
        )
    else:
        bot.reply_to(message, f"❌ <b>فشل في الخلع:</b> {result}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("توب المهور"))
def marriage_top_command(message):
    banking = ensure_banking()
    
    if not banking.get("marriage_top"):
        bot.reply_to(message, "📊 <b>لا يوجد مهور مسجلة بعد</b>")
        return
    
    # ترتيب المهور من الأعلى إلى الأدنى
    sorted_marriage_top = sorted(banking["marriage_top"].items(), key=lambda x: x[1], reverse=True)
    
    top_text = "💍 <b>توب أكبر المهور:</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (user_id_str, total_mahr) in enumerate(sorted_marriage_top[:10]):
        user_id = int(user_id_str)
        username = f"user_{user_id}"
        name = "غير معروف"
        
        # البحث عن اسم المستخدم
        for chat_id, chat_data in DB.items():
            if chat_id.isdigit() and "known_users" in chat_data:
                for uname, uid in chat_data["known_users"].items():
                    if uid == user_id:
                        username = f"@{uname}"
                        try:
                            user_info = bot.get_chat(user_id)
                            name = human_name(user_info)
                        except:
                            pass
                        break
        
        if i < 3:
            rank_emoji = medals[i]
        else:
            rank_emoji = f"{i+1}."
        
        top_text += f"{rank_emoji} {name} ({username}) - <b>{total_mahr: ,} دولار</b>\n"
    
    bot.reply_to(message, top_text)
# ========= أمر نقل الملكية المطور والمضمون 100% =========
@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("اعطاء مالك اساسي"))
def give_main_owner(message):
    if not is_group(message):
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    actor_role = get_role(chat_id, user_id)

    # التحقق من الرتبة (دعم الصيغتين بالمسافة أو الشرطة السفلية)
    if actor_role not in ["مالك اساسي", "مالك_اساسي"]:
        bot.reply_to(message, "⛔ فقط <b>المالك الأساسي</b> للجروب يمتلك صلاحية نقل الملكية.")
        return

    chat = ensure_chat(chat_id)
    target_id = None
    target_name = ""

    # الحالة الأولى: إذا تم استخدام الأمر بالرد على الشخص
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_name = f"@{target_user.username}" if target_user.username else target_user.first_name

    # الحالة الثانية: إذا تم كتابة الايدي أو اليوزر بجانب الأمر
    else:
        parts = message.text.strip().split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ <b>الاستخدام الصحيح للأمر:</b>\n1 - بالرد على الشخص وكتابة: <code>اعطاء مالك اساسي</code>\n2 - أو عبر المعرف: <code>اعطاء مالك اساسي @username</code>\n3 - أو عبر الايدي: <code>اعطاء مالك اساسي 123456</code>", parse_mode="HTML")
            return
        
        arg = parts[2]
        if arg.isdigit():  # إذا كان المُدخل آيدي رقمي
            target_id = int(arg)
            try:
                chat_member = bot.get_chat_member(chat_id, target_id)
                target_name = chat_member.user.first_name
            except:
                target_name = f"المستخدم ({target_id})"
        elif arg.startswith("@"):  # إذا كان المُدخل يوزر
            uname = arg[1:]
            target_id = find_user_id_by_username(chat_id, uname)
            target_name = arg
            if not target_id:
                # محاولة فحص الرسالة بحثاً عن منشن مدمج من التليجرام منعاً للتعليق
                if message.entities:
                    for entity in message.entities:
                        if entity.type == "text_mention":
                            target_id = entity.user.id
                            target_name = entity.user.first_name
                            break
                if not target_id:
                    bot.reply_to(message, "⛔ لم أتمكن من العثور على هذا المستخدم في سجلات الجروب، يرجى تفعيل الأمر بالرد عليه.")
                    return

    if not target_id:
        bot.reply_to(message, "⛔ حدث خطأ في تحديد الشخص، يرجى استخدام الأمر بالرد عليه مباشرة.")
        return

    if target_id == user_id:
        bot.reply_to(message, "⚠️ لا يمكنك نقل الملكية إلى نفسك!")
        return

    # حفظ المالك السابق لتنزيله لعضو
    prev_owner = chat.get("main_owner")

    # إعطاء الرتبة الجديدة للشخص المستهدف في كلتا الصيغتين
    chat["main_owner"] = target_id
    for r_name in ["مالك اساسي", "مالك_اساسي"]:
        if r_name not in chat["roles"]:
            chat["roles"][r_name] = []
        if target_id not in chat["roles"][r_name]:
            chat["roles"][r_name].append(target_id)

    # تجريد المالك السابق من كافة الرتب والمميزات وتنزيله لعضو بالكامل
    if prev_owner and prev_owner != target_id:
        # إزالته من رتبة مالك أساسي
        for r_name in ["مالك اساسي", "مالك_اساسي"]:
            if r_name in chat["roles"] and prev_owner in chat["roles"][r_name]:
                chat["roles"][r_name].remove(prev_owner)
        
        # تنظيفه من بقية الرتب الادارية ليكون عضواً عادياً
        for r in ["مالك", "منشئ", "مدير", "ادمن", "مميز", "مساعد مالك", "مساعد_مالك"]:
            if r in chat["roles"] and prev_owner in chat["roles"][r]:
                try:
                    chat["roles"][r].remove(prev_owner)
                except:
                    pass

    save_db()
    bot.reply_to(message, f"👑 <b>تم نقل الملكية بنجاح!</b>\n\n👤 المالك الأساسي الجديد: <b>{target_name}</b>\n📉 تم تجريد المالك السابق من رتبه بالكامل ونزل إلى رتبة عضو.")

# ========= أوامر التقييد والحظر والكتم =========
@bot.message_handler(func=lambda m: m.text and any(m.text.startswith(cmd) for cmd in ["حظر", "كتم", "تقييد", "رفع الحظر", "رفع الكتم", "رفع التقييد", "اعطاء صلاحية حظر", "سحب صلاحية حظر"]))
def restriction_commands(message):
    if not is_group(message):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    actor_role = get_role(chat_id, user_id)
    text = (message.text or "").strip()
    
    if text.startswith("حظر") or text.startswith("رفع الحظر"):
        if not can_ban(chat_id, user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية الحظر.")
            return
    
    if text.startswith("كتم") or text.startswith("رفع الكتم"):
        if not can_mute(chat_id, user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية الكتم.")
            return
    
    if text.startswith("تقييد") or text.startswith("رفع التقييد"):
        if not can_restrict(chat_id, user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية التقييد.")
            return
    
    if text.startswith("اعطاء صلاحية حظر") or text.startswith("سحب صلاحية حظر"):
        if actor_role not in ["مالك اساسي", "مساعد مالك"]:
            bot.reply_to(message, "⛔ فقط المالك الأساسي ومساعده يمكنهم منح صلاحيات الحظر.")
            return
    
    target_username = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        parts = text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            target_username = parts[1][1:]
            target_id = find_user_id_by_username(chat_id, target_username)
    
    if not target_id:
        bot.reply_to(message, "⛔ يجب الرد على رسالة المستخدم أو ذكر اليوزر بعد الأمر.")
        return
    
    try:
        target_member = bot.get_chat_member(chat_id, target_id)
        target_user = target_member.user
        if not target_username:
            target_username = target_user.username or str(target_id)
    except:
        bot.reply_to(message, "⛔ لم أتمكن العثور على المستخدم.")
        return
    
    if text.startswith("حظر"):
        if ban_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم حظر @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في حظر @{target_username}.")
    
    elif text.startswith("رفع الحظر"):
        if unban_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم رفع الحظر عن @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في رفع الحظر عن @{target_username}.")
    
    elif text.startswith("كتم"):
        if mute_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم كتم @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في كتم @{target_username}.")
    
    elif text.startswith("رفع الكتم"):
        if unmute_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم رفع الكتم عن @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في رفع الكتم عن @{target_username}.")
    
    elif text.startswith("تقييد"):
        if restrict_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم تقييد @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في تقييد @{target_username}.")
    
    elif text.startswith("رفع التقييد"):
        if unrestrict_user(chat_id, target_id):
            bot.reply_to(message, f"✅ تم رفع التقييد عن @{target_username} بنجاح.")
        else:
            bot.reply_to(message, f"❌ فشل في رفع التقييد عن @{target_username}.")
    
    elif text.startswith("اعطاء صلاحية حظر"):
        chat = ensure_chat(chat_id)
        chat["ban_permissions"][str(target_id)] = True
        save_db()
        bot.reply_to(message, f"✅ تم منح صلاحية الحظر لـ @{target_username}.")
    
    elif text.startswith("سحب صلاحية حظر"):
        chat = ensure_chat(chat_id)
        if str(target_id) in chat["ban_permissions"]:
            del chat["ban_permissions"][str(target_id)]
            save_db()
            bot.reply_to(message, f"✅ تم سحب صلاحية الحظر من @{target_username}.")
        else:
            bot.reply_to(message, f"❌ @{target_username} لا يملك صلاحية حظر أساساً.")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("رفع القيود"))
def remove_all_restrictions_command(message):
    if not is_group(message):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not can_restrict(chat_id, user_id):
        bot.reply_to(message, "⛔ ليس لديك صلاحية رفع القيود.")
        return
    
    target_username = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            target_username = parts[1][1:]
            target_id = find_user_id_by_username(chat_id, target_username)
    
    if not target_id:
        bot.reply_to(message, "⛔ يجب الرد على رسالة المستخدم أو ذكر اليوزر بعد الأمر.")
        return
    
    try:
        target_member = bot.get_chat_member(chat_id, target_id)
        target_user = target_member.user
        if not target_username:
            target_username = target_user.username or str(target_id)
    except:
        bot.reply_to(message, "⛔ لم أتمكن العثور على المستخدم.")
        return
    
    if remove_all_restrictions(chat_id, target_id):
        bot.reply_to(message, f"✅ تم رفع جميع القيود والانذارات عن @{target_username} بنجاح.")
    else:
        bot.reply_to(message, f"❌ فشل في رفع القيود عن @{target_username}.")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith("انذار") or m.text.startswith("مسح الانذارات") or m.text.startswith("مسح الانذارات")))
def warning_command(message):
    if not is_group(message):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not can_restrict(chat_id, user_id):
        bot.reply_to(message, "⛔ ليس لديك صلاحية إعطاء الانذارات.")
        return
    
    text = (message.text or "").strip()
    
    target_username = None
    target_id = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
    else:
        parts = text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            target_username = parts[1][1:]
            target_id = find_user_id_by_username(chat_id, target_username)
    
    if not target_id:
        bot.reply_to(message, "⛔ يجب الرد على رسالة المستخدم أو ذكر اليوزر بعد الأمر.")
        return
    
    try:
        target_member = bot.get_chat_member(chat_id, target_id)
        target_user = target_member.user
        if not target_username:
            target_username = target_user.username or str(target_id)
    except:
        bot.reply_to(message, "⛔ لم أتمكن العثور على المستخدم.")
        return
    
    chat = ensure_chat(chat_id)
    target_key = str(target_id)
    
    if text.startswith("انذار"):
        current_warnings, action = v22_apply_warning(chat_id, target_id)
        cfg = v22_warn_config(chat)
        bot.reply_to(message, f"⚠️ تم إعطاء إنذار لـ @{target_username} ({current_warnings}/{cfg['ban']})" + (f"\n➡️ العقوبة: {action}" if action else ""))

    elif text.startswith("مسح الانذارات") or text.startswith("مسح الانذارات"):
        chat["warnings"][target_key] = 0
        try:
            unrestrict_user(chat_id, target_id)
        except:
            pass
        try:
            unmute_user(chat_id, target_id)
        except:
            pass
        save_db()
        bot.reply_to(message, f"✅ تم مسح إنذارات @{target_username} ورفع التقييد/الكتم عنه.")

    elif text.startswith("انذاراته"):
        current_warnings = chat["warnings"].get(target_key, 0)
        bot.reply_to(message, f"📊 عدد إنذارات @{target_username}: {current_warnings}/5")

# ========= معالج أمر /start =========
# ================================================================
# نظام لوحة المطور — القروبات (Pagination + تفاصيل)
# ================================================================
GROUPS_PER_PAGE = 4

def get_active_groups():
    """يرجع قائمة (chat_id, chat_data) لكل القروبات الفعالة فقط (يستبعد المحذوفة)"""
    active = []
    for cid in list(DB.keys()):
        if not cid.isdigit() and not (cid.startswith("-") and cid[1:].isdigit()):
            continue
        if "main_owner" not in DB.get(cid, {}):
            continue
        try:
            info = bot.get_chat(int(cid))
            active.append((cid, DB[cid], info))
        except:
            # القروب محذوف أو البوت طرد منه — نتجاهله
            continue
    return active

def build_groups_list_markup(groups, page):
    total_pages = max(1, (len(groups) + GROUPS_PER_PAGE - 1) // GROUPS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * GROUPS_PER_PAGE
    end   = start + GROUPS_PER_PAGE
    page_groups = groups[start:end]

    m = types.InlineKeyboardMarkup(row_width=1)
    for cid, cdata, info in page_groups:
        gname = info.title or cid
        is_banned = cdata.get("bot_banned", False)
        label = f"🚫 {gname}" if is_banned else gname
        m.add(types.InlineKeyboardButton(label, callback_data=f"grpinfo_{cid}_{page}"))

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("◀️ السابق", callback_data=f"grppage_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton("التالي ▶️", callback_data=f"grppage_{page+1}"))
    if nav_row:
        m.row(*nav_row)

    m.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
    return m, page, total_pages

def send_groups_page(chat_id, message_id, page=0, edit=False):
    groups = get_active_groups()
    if not groups:
        txt = "👥 <b>القروبات</b>\n\nلا توجد قروبات فعالة حالياً."
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        try:
            if edit:
                bot.edit_message_text(txt, chat_id, message_id, reply_markup=back, parse_mode="HTML")
            else:
                bot.send_message(chat_id, txt, reply_markup=back, parse_mode="HTML")
        except: pass
        return

    markup, page, total_pages = build_groups_list_markup(groups, page)
    txt = f"👥 <b>القروبات الفعالة ({len(groups)}):</b>\n\nالصفحة {page+1} / {total_pages}\n\nاختر قروباً لعرض تفاصيله:"
    try:
        if edit:
            bot.edit_message_text(txt, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(chat_id, txt, reply_markup=markup, parse_mode="HTML")
    except: pass

def send_group_info(chat_id, message_id, group_cid, back_page):
    try:
        info = bot.get_chat(int(group_cid))
    except:
        bot.edit_message_text("⚠️ هذا القروب لم يعد متاحاً (محذوف أو طُرد البوت منه).",
                              chat_id, message_id,
                              reply_markup=types.InlineKeyboardMarkup().add(
                                  types.InlineKeyboardButton("🔙 رجوع", callback_data=f"grppage_{back_page}")))
        return

    cdata     = DB.get(group_cid, {})
    gname     = info.title or group_cid
    gusername = f"@{info.username}" if info.username else "لا يوجد"
    is_banned = cdata.get("bot_banned", False)
    ban_status = "🚫 محظور" if is_banned else "✅ غير محظور"

    try:
        members_count = bot.get_chat_members_count(int(group_cid))
    except:
        members_count = "غير معروف"

    txt = (
        f"📋 <b>معلومات القروب</b>\n\n"
        f"🏷️ الاسم : <b>{gname}</b>\n"
        f"🆔 الآيدي : <code>{group_cid}</code>\n"
        f"🔗 اليوزر : {gusername}\n"
        f"👥 عدد الأعضاء : <b>{members_count}</b>\n"
        f"⚙️ الحالة : <b>{ban_status}</b>"
    )

    back_mk = types.InlineKeyboardMarkup(row_width=1)
    if is_banned:
        back_mk.add(types.InlineKeyboardButton("✅ فك الحظر عن القروب", callback_data=f"grpban_off_{group_cid}_{back_page}"))
    else:
        back_mk.add(types.InlineKeyboardButton("🚫 حظر القروب", callback_data=f"grpban_on_{group_cid}_{back_page}"))
    back_mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"grppage_{back_page}"))

    try:
        group_photo = info.photo
        if group_photo:
            # نحذف الرسالة القديمة ونرسل صورة بدلها لأن edit_message_text ما يدعم تحويل لصورة
            try:
                bot.delete_message(chat_id, message_id)
            except: pass
            bot.send_photo(chat_id, group_photo.big_file_id, caption=txt, parse_mode="HTML", reply_markup=back_mk)
        else:
            bot.edit_message_text(txt, chat_id, message_id, reply_markup=back_mk, parse_mode="HTML")
    except:
        try:
            bot.send_message(chat_id, txt, reply_markup=back_mk, parse_mode="HTML")
        except: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("grppage_"))
def groups_page_callback(call):
    if call.from_user.id != BOT_OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ هذا الزر للمطور فقط.", show_alert=True)
        return
    page = int(call.data.replace("grppage_", ""))
    send_groups_page(call.message.chat.id, call.message.message_id, page=page, edit=True)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("grpban_"))
def group_ban_toggle_callback(call):
    if call.from_user.id != BOT_OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ هذا الزر للمطور فقط.", show_alert=True)
        return
    parts     = call.data.split("_")
    action    = parts[1]            # on / off
    group_cid = parts[2]
    back_page = int(parts[3])

    gchat = ensure_chat(int(group_cid))
    if action == "on":
        gchat["bot_banned"] = True
        save_db()
        bot.answer_callback_query(call.id, "🚫 تم حظر القروب.")
        try:
            bot.send_message(int(group_cid), "🚫 <b>تم حظر هذا القروب من استخدام البوت بواسطة المطور.</b>", parse_mode="HTML")
        except: pass
    else:
        gchat["bot_banned"] = False
        save_db()
        bot.answer_callback_query(call.id, "✅ تم فك الحظر عن القروب.")
        try:
            bot.send_message(int(group_cid), "✅ <b>تم فك الحظر عن هذا القروب، البوت يعمل الآن بشكل طبيعي.</b>", parse_mode="HTML")
        except: pass

    send_group_info(call.message.chat.id, call.message.message_id, group_cid, back_page)


@bot.callback_query_handler(func=lambda c: c.data.startswith("grpinfo_"))
def group_info_callback(call):
    if call.from_user.id != BOT_OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ هذا الزر للمطور فقط.", show_alert=True)
        return
    parts = call.data.split("_")
    group_cid = parts[1]
    back_page = int(parts[2])
    send_group_info(call.message.chat.id, call.message.message_id, group_cid, back_page)
    bot.answer_callback_query(call.id)


# ================================================================
# ميزات لوحة المطور الجديدة
# ================================================================

owner_back_btn = lambda: types.InlineKeyboardMarkup().add(
    types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))

# جلسات المطور (بحث، بث، تصفير قروب)
owner_sessions = {}

def log_error(error_text):
    """يسجل خطأ بسجل الأخطاء"""
    if "error_log" not in DB:
        DB["error_log"] = []
    now = datetime.now().strftime("%d/%m %H:%M")
    DB["error_log"].append(f"[{now}] {error_text}")
    if len(DB["error_log"]) > 100:
        DB["error_log"].pop(0)
    save_db()

def is_maintenance_on():
    return DB.get("maintenance_mode", False)


# ========= 📈 الأكثر نشاطاً =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_top_active")
def bot_top_active_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_top_active"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    groups_activity = []
    for cid in list(DB.keys()):
        if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
            cdata = DB[cid]
            if isinstance(cdata, dict) and "messages" in cdata:
                total = sum(cdata["messages"].values())
                groups_activity.append((cid, total))
    groups_activity.sort(key=lambda x: x[1], reverse=True)
    txt = "📈 <b>أكثر القروبات نشاطاً:</b>\n\n"
    if not groups_activity:
        txt += "لا توجد بيانات بعد."
    else:
        medals = ["🥇","🥈","🥉"]
        for i, (cid, total) in enumerate(groups_activity[:10]):
            try:
                gname = bot.get_chat(int(cid)).title or cid
            except:
                gname = cid
            rank = medals[i] if i < 3 else f"{i+1}."
            txt += f"{rank} {gname} — <b>{total:,}</b> رسالة\n"
    try:
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= 🔍 بحث عن مستخدم =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_search_user")
def bot_search_user_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_search_user"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    owner_sessions[call.from_user.id] = {"step": "waiting_search_user"}
    try:
        bot.edit_message_text("🔍 <b>أرسل آيدي المستخدم أو اليوزر للبحث عنه:</b>",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= 🔄 تصفير قروب معين =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_reset_group")
def bot_reset_group_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_reset_group"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    owner_sessions[call.from_user.id] = {"step": "waiting_reset_group_id"}
    try:
        bot.edit_message_text("🔄 <b>أرسل آيدي القروب الذي تريد تصفير بياناته بالكامل:</b>",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("resetgrp_confirm_") or c.data == "resetgrp_cancel")
def reset_group_confirm_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_reset_group"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    if call.data == "resetgrp_cancel":
        try:
            bot.edit_message_text("❌ تم الإلغاء.", call.message.chat.id, call.message.message_id, reply_markup=owner_back_btn())
        except: pass
        bot.answer_callback_query(call.id)
        return
    target_cid = call.data.replace("resetgrp_confirm_", "")
    if target_cid in DB:
        del DB[target_cid]
        save_db()
        txt = f"✅ تم تصفير بيانات القروب <code>{target_cid}</code> بالكامل."
    else:
        txt = "⚠️ لا توجد بيانات لهذا القروب أصلاً."
    try:
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= 📢 بث جماعي للقروبات =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_broadcast_groups")
def bot_broadcast_groups_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_broadcast_groups"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    owner_sessions[call.from_user.id] = {"step": "waiting_broadcast_groups"}
    try:
        bot.edit_message_text("📢 <b>أرسل الرسالة التي تريد بثها لكل القروبات:</b>",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= ✉️ رسالة لمستخدم معين =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_broadcast_user")
def bot_broadcast_user_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_broadcast_user"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    owner_sessions[call.from_user.id] = {"step": "waiting_broadcast_user_id"}
    try:
        bot.edit_message_text("✉️ <b>أرسل آيدي المستخدم الذي تريد مراسلته:</b>",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= ⏸️ وضع الصيانة =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_maintenance")
def bot_maintenance_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_maintenance"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    current = is_maintenance_on()
    status = "✅ مفعّل" if current else "❌ معطّل"
    mk = types.InlineKeyboardMarkup(row_width=1)
    if current:
        mk.add(types.InlineKeyboardButton("❌ تعطيل وضع الصيانة", callback_data="maintenance_off"))
    else:
        mk.add(types.InlineKeyboardButton("✅ تفعيل وضع الصيانة", callback_data="maintenance_on"))
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
    try:
        bot.edit_message_text(
            f"⏸️ <b>وضع الصيانة</b>\n\nالحالة الحالية: <b>{status}</b>\n\n"
            f"عند التفعيل، البوت يرد بس للمطور وتتوقف باقي القروبات مؤقتاً.",
            call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data in ["maintenance_on", "maintenance_off"])
def maintenance_toggle_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_maintenance"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    DB["maintenance_mode"] = (call.data == "maintenance_on")
    save_db()
    status = "✅ مفعّل" if DB["maintenance_mode"] else "❌ معطّل"
    mk = types.InlineKeyboardMarkup(row_width=1)
    if DB["maintenance_mode"]:
        mk.add(types.InlineKeyboardButton("❌ تعطيل وضع الصيانة", callback_data="maintenance_off"))
    else:
        mk.add(types.InlineKeyboardButton("✅ تفعيل وضع الصيانة", callback_data="maintenance_on"))
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
    try:
        bot.edit_message_text(
            f"⏸️ <b>وضع الصيانة</b>\n\nالحالة الحالية: <b>{status}</b>",
            call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id, f"تم {'تفعيل' if DB['maintenance_mode'] else 'تعطيل'} وضع الصيانة")


# ========= 💾 نسخة احتياطية =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_backup")
def bot_backup_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_backup"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    try:
        with open(DATA_FILE, "rb") as f:
            bot.send_document(call.message.chat.id, f, caption="💾 نسخة احتياطية من قاعدة البيانات.")
        bot.answer_callback_query(call.id, "✅ تم إرسال النسخة الاحتياطية")
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ خطأ: {e}", show_alert=True)


# ========= 📜 سجل الأخطاء =========
@bot.callback_query_handler(func=lambda c: c.data == "bot_error_log")
def bot_error_log_callback(call):
    if not has_bot_permission(call.from_user.id, "bot_error_log"):
        bot.answer_callback_query(call.id, "⛔ للمطور فقط.", show_alert=True)
        return
    errors = DB.get("error_log", [])
    if not errors:
        txt = "📜 <b>سجل الأخطاء</b>\n\nلا توجد أخطاء مسجلة. ✅"
    else:
        txt = "📜 <b>آخر 15 خطأ:</b>\n\n"
        for e in reversed(errors[-15:]):
            txt += f"• {e}\n"
    try:
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                              reply_markup=owner_back_btn(), parse_mode="HTML")
    except: pass
    bot.answer_callback_query(call.id)


# ========= معالجة جلسات المطور النصية =========
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.from_user.id in owner_sessions)
def owner_session_handler(message):
    user_id = message.from_user.id
    sess = owner_sessions.get(user_id)
    if not sess:
        return
    text = (message.text or "").strip()
    step = sess["step"]

    # ===== بحث عن مستخدم =====
    if step == "waiting_search_user":
        target_id = None
        if text.startswith("@"):
            uname = text[1:]
            for cid in DB.keys():
                if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                    known = DB[cid].get("known_users", {})
                    if uname in known:
                        target_id = known[uname]
                        break
        elif text.isdigit():
            target_id = int(text)

        if not target_id:
            bot.reply_to(message, "⚠️ لم يتم العثور على المستخدم.")
            del owner_sessions[user_id]
            return

        try:
            info = bot.get_chat(target_id)
            name = human_name(info)
        except:
            name = str(target_id)

        banking = ensure_banking()
        balance = banking["users"].get(str(target_id), {}).get("balance", 0)
        gold    = ensure_gold_ranking().get(str(target_id), 0)

        found_groups = []
        for cid in DB.keys():
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                role = get_role(int(cid), target_id)
                if role != "عضو":
                    try:
                        gname = bot.get_chat(int(cid)).title or cid
                    except:
                        gname = cid
                    found_groups.append(f"• {gname} ← <b>{role}</b>")

        txt = (
            f"🔍 <b>نتيجة البحث:</b>\n\n"
            f"👤 الاسم : <b>{name}</b>\n"
            f"🆔 الآيدي : <code>{target_id}</code>\n"
            f"💰 الرصيد البنكي : <b>{balance:,}</b> دولار\n"
            f"🥇 النقاط الذهبية : <b>{gold}</b>\n\n"
        )
        if found_groups:
            txt += "📋 <b>العضويات والرتب:</b>\n" + "\n".join(found_groups)
        else:
            txt += "📋 لا يحمل أي رتبة بأي قروب."

        bot.send_message(message.chat.id, txt, parse_mode="HTML", reply_markup=owner_back_btn())
        del owner_sessions[user_id]
        return

    # ===== تصفير قروب معين =====
    if step == "waiting_reset_group_id":
        target_cid = text
        if target_cid not in DB:
            bot.reply_to(message, "⚠️ لا توجد بيانات لهذا القروب.")
            del owner_sessions[user_id]
            return
        try:
            gname = bot.get_chat(int(target_cid)).title or target_cid
        except:
            gname = target_cid
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            types.InlineKeyboardButton("✅ تأكيد", callback_data=f"resetgrp_confirm_{target_cid}"),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="resetgrp_cancel"),
        )
        bot.reply_to(message,
            f"⚠️ <b>تأكيد تصفير قروب: {gname}</b>\n\n"
            f"سيتم حذف كل بيانات هذا القروب (الرتب، الإنذارات، الفلوس، الزيجات، الأحداث).\n"
            f"هذا الاجراء لا يمكن التراجع عنه!",
            parse_mode="HTML", reply_markup=mk)
        del owner_sessions[user_id]
        return

    # ===== بث جماعي للقروبات =====
    if step == "waiting_broadcast_groups":
        sent, failed = 0, 0
        for cid in list(DB.keys()):
            if cid.isdigit() or (cid.startswith("-") and cid[1:].isdigit()):
                if "main_owner" in DB.get(cid, {}):
                    try:
                        bot.send_message(int(cid), f"📢 <b>إعلان من إدارة البوت:</b>\n\n{text}", parse_mode="HTML")
                        sent += 1
                    except:
                        failed += 1
        bot.reply_to(message, f"✅ تم الإرسال لـ <b>{sent}</b> قروب.\n❌ فشل الإرسال لـ <b>{failed}</b> قروب.",
                     parse_mode="HTML", reply_markup=owner_back_btn())
        del owner_sessions[user_id]
        return

    # ===== رسالة لمستخدم =====
    if step == "waiting_broadcast_user_id":
        if not text.isdigit():
            bot.reply_to(message, "⚠️ أرسل آيدي صحيح (أرقام فقط).")
            del owner_sessions[user_id]
            return
        owner_sessions[user_id] = {"step": "waiting_broadcast_user_msg", "target_id": int(text)}
        bot.reply_to(message, "✉️ الآن أرسل نص الرسالة:")
        return

    if step == "waiting_broadcast_user_msg":
        target_id = sess["target_id"]
        try:
            bot.send_message(target_id, f"✉️ <b>رسالة من إدارة البوت:</b>\n\n{text}", parse_mode="HTML")
            bot.reply_to(message, "✅ تم إرسال الرسالة بنجاح.", reply_markup=owner_back_btn())
        except Exception as e:
            bot.reply_to(message, f"⚠️ تعذر إرسال الرسالة: {e}", reply_markup=owner_back_btn())
        del owner_sessions[user_id]
        return




# ==========================================================
# ========= نظام الذكاء الاصطناعي (ماثيو AI مدمج بايتو) =========
# ==========================================================
# يعمل فقط بالخاص (Private) — وفقط اذا بدأت الرسالة بكلمة "ايتو"

AI_TRIGGER = "ايتو"

# ==================== نظام الـAI الجديد (من main.py) ====================
API_URL = "https://baithek.com/chatbee/health_ai/new_health.php"
API_HEADERS = {
    "Host": "baithek.com",
    "Content-Type": "application/json",
    "User-Agent": "okhttp/4.9.2",
}
API_MAX_RETRIES = 3
# =====================================================================

OLD_AI_MEMORY_FILE = "smart_memory.json"  # ملف ذاكرة ماثيو القديم


def ensure_ai_memory():
    if "ai_memory" not in DB:
        DB["ai_memory"] = {}
    return DB["ai_memory"]


def migrate_owner_ai_memory():
    """
    يرحّل فقط ذاكرة محادثة المطور (Owner) من نظام ماثيو القديم إلى ايتو.
    ذاكرة باقي الأعضاء (الخاص القديم) لا تُنقل إطلاقاً.
    """
    if not os.path.exists(OLD_AI_MEMORY_FILE):
        return
    try:
        with open(OLD_AI_MEMORY_FILE, "r", encoding="utf-8") as f:
            old_mem = json.load(f)
    except:
        return

    owner_key = str(BOT_OWNER_ID)
    mem = ensure_ai_memory()

    if owner_key in old_mem and owner_key not in mem:
        mem[owner_key] = old_mem[owner_key][-10:]
        save_db()


migrate_owner_ai_memory()


def ask_nawal_ai(prompt, history, user_id, user_name, user_link):
    """نظام AI المستخرج من main.py، مكيّف مع ذاكرة Nawal الحالية."""
    is_dev = "نعم" if user_id == BOT_OWNER_ID else "لا"
    today_str = datetime.now().strftime("%Y-%m-%d")

    if not isinstance(history, list):
        history = []

    if not user_name:
        user_name = "مستخدم"
    if not user_link:
        user_link = ""

    sys_prompt = (
        "أنت ايتو  ، مساعد ذكر ذكاء اصطناعي فرفوش ومرحة داخل بوت تليجرام. "
        "ردودك مختصرة، مبهجة، ومليئة بالطاقة الإيجابية. "
        "انت من دولة العراق وتتكلمين باللهجة العراقية. "
        "إذا أحد سألك عن عمرك، ردي بمغازلة لطيفة مثل: انتَ عمري ❤️ أو أي مغازلة خفيفة ومناسبة للسياق. "
        "إذا أحد قال لكي أحبج، ردي برد لطيف ومضحك. وإذا قال تحبين المطور، قولي نعم مع مقولة شعرية من عندج. "
        "إذا سألك المستخدم عن نفسك أو طلب منك تعرفين نفسك، قول إن اسمك ايتو ، "
        "مساعدة ذكاء اصطناعي عراقية ومرحة داخل بوت تليجرام، وتساعدين المستخدمين وتسولفين وياهم بطريقة لطيفة. "
        "لا تذكر تاريخ اليوم أو مهاراتك البرمجية إلا إذا سألك المستخدم عن ذلك مباشرة. "
        f"تاريخ اليوم الحالي هو {today_str}، اعتمد عليه إذا احتجت تعرف الوقت الحالي. "
        "مهم جداً: جاوب دائماً على أصل سؤال المستخدم كامل ومباشر أولاً، حتى لو ذكر بالسؤال كلمة 'ماثيو' أو أي اسم ثاني ضمن سياق الكلام. "
        "لا تتجاهل السؤال الأصلي وتحوله لجواب عن الصانع. "
        "فقط إذا كان سؤال المستخدم صريح ومباشر عن هوية صانعك أو مبرمجك "
        "(مثل: مين صنعك؟ مين برمجك؟ شكو المبرمج مالك؟) جاوب إنك من صنع ماثيو، كجزء من الرد وليس بديل عن الإجابة. "
        "استخدم الرموز التعبيرية Emojis لتجعل المحادثة لطيفة. "
        f"المطور الحقيقي آيديه هو {BOT_OWNER_ID}. هل المتحدث الآن هو المطور؟ ({is_dev}). "
        "إذا كان هو المطور، دلعه بألقاب لطيفة مثل يا غالي ويا مطوري. "
        "إذا ادعى شخص آخر أنه المطور، اضحك معه بلطف وقل إن المطور واحد بس. "
        "إذا سألك المستخدم عن اسمه، مثل شنو اسمي، جاوبه باسمه الحقيقي الموجود تحت اسم المستخدم، ولا تذكر رقم الآيدي كجواب على اسمه. "
        "إذا احتجت تذكر حسابه أو تسويله منشن، استخدم القيمة الموجودة تحت رابط الحساب بالضبط كما هي بدون أي تعديل عليها، لأنها كود HTML جاهز وقابل للضغط. "
    )

    context_prompt = (
        f"[اسم المستخدم: {user_name} | رابط الحساب: {user_link} | User ID: {user_id}]\n{prompt}"
    )

    # تحويل ذاكرة Gemini القديمة إلى صيغة الـAPI الجديد.
    normalized_history = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role == "model":
            role = "assistant"
        content = item.get("content")
        if content is None and isinstance(item.get("parts"), list):
            texts = [p.get("text", "") for p in item["parts"] if isinstance(p, dict)]
            content = "".join(texts)
        if role in ("user", "assistant") and content:
            normalized_history.append({"role": role, "content": str(content)})

    messages = (
        [{"role": "system", "content": sys_prompt}]
        + normalized_history
        + [{"role": "user", "content": context_prompt}]
    )

    payload = {"name": "Usama", "messages": messages}
    last_error = None

    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            response = requests.post(
                API_URL,
                headers=API_HEADERS,
                json=payload,
                timeout=25
            )
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                return "⚠️ السيرفر رجّع رد غير مفهوم، جرب بعد شوي! 🌸"

            if isinstance(data, dict) and data.get("choices") and isinstance(data["choices"], list):
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    message_data = choice.get("message")
                    if isinstance(message_data, dict) and message_data.get("content"):
                        return str(message_data["content"]).strip()
                    if choice.get("text"):
                        return str(choice["text"]).strip()

            if isinstance(data, dict):
                for key in ("content", "response", "answer"):
                    if data.get(key):
                        return str(data[key]).strip()

            return "⚠️ وصلتني استجابة من السيرفر بس ما گدرت أقرأها 😅"

        except requests.RequestException as e:
            last_error = e
            if attempt < API_MAX_RETRIES:
                time.sleep(1.5 * attempt)
                continue
            return "⚠️ ما گدرت أتصل بالسيرفر حاليًا بعد عدة محاولات، جرب بعد شوي! 🌸"
        except Exception:
            return "⚠️ صار خطأ غير متوقع، جرب بعد شوي! 🌸"

    return "⚠️ ما گدرت أتصل بالسيرفر حاليًا، جرب بعد شوي! 🌸"


@bot.message_handler(
    func=lambda m: m.chat.type in ["group", "supergroup"]
    and m.text
    and m.text.strip().split()[0] == AI_TRIGGER
    if m.text and m.text.strip() else False
)
def nawal_ai_handler(message):
    user_id = message.from_user.id
    raw = message.text.strip()
    prompt = raw[len(AI_TRIGGER):].strip()

    if not prompt:
        bot.reply_to(message, "هلا فيك! 🌸 اكتب سؤالك بعد كلمة (ايتو) وراح اجاوبك 😊")
        return
    # ===== لو الرسالة فيها كلمة مفتاحية من الردود المخصصة (مثل "ماثيو")، أرسل الرد المخصص أيضاً =====
    try:
        chat = ensure_chat(message.chat.id)
        _wz_send_matched_reply(chat, message.chat.id, message, user_id)
    except Exception:
        pass

    mem = ensure_ai_memory()
    history = mem.get(str(user_id), [])

    try:
        bot.send_chat_action(message.chat.id, "typing")
    except:
        pass

    user_name = human_name(message.from_user)
    user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    answer = ask_nawal_ai(prompt, history, user_id, user_name, user_link)

    history.append({"role": "user", "parts": [{"text": prompt}]})
    history.append({"role": "model", "parts": [{"text": answer}]})
    mem[str(user_id)] = history[-10:]
    save_db()

    try:
        bot.reply_to(message, answer, parse_mode="HTML")
    except Exception:
        # لو الرابط طلع بصيغة HTML خربانة من الذكاء الاصطناعي، نرسلها بدون فورمات بدل ما نطيح
        bot.reply_to(message, answer)



# ========= إدارة أدمنية البوت وصلاحياتهم =========
BOT_PANEL_PERMISSIONS = {
    "bot_stats":"📊 إحصائيات", "bot_groups":"👥 القروبات", "bot_gold":"🥇 التصنيف الذهبي",
    "bot_top_active":"📈 الأكثر نشاطاً", "bot_gift":"💰 هدية فلوس", "bot_ban_game":"🚫 حظر من اللعبة",
    "bot_reset_all":"🗑️ تصفير الكل", "bot_reset_gold":"🥇 تصفير الذهبي", "bot_search_user":"🔍 بحث عن مستخدم",
    "bot_reset_group":"🔄 تصفير قروب", "bot_broadcast_groups":"📢 بث للقروبات", "bot_broadcast_user":"✉️ رسالة لمستخدم",
    "dev_games_menu":"🎮 الألعاب", "manage_anime":"🎌 إدارة الأنمي", "manage_players":"⚽ إدارة اللاعبين",
    "bot_maintenance":"⏸️ وضع الصيانة", "bot_backup":"💾 نسخة احتياطية",
    "bot_error_log":"📜 سجل الأخطاء", "view_whispers":"💌 مشاهدة الهمسات"
}

def ensure_bot_admins():
    if "bot_admins" not in DB or not isinstance(DB.get("bot_admins"), dict): DB["bot_admins"]={}
    return DB["bot_admins"]

def is_bot_admin(uid): return uid == BOT_OWNER_ID or str(uid) in ensure_bot_admins()

def has_bot_permission(uid, perm):
    if uid == BOT_OWNER_ID: return True
    rec=ensure_bot_admins().get(str(uid),{})
    return bool(rec.get("permissions",{}).get(perm,False))

def admin_panel_keyboard(uid):
    # نفس أسلوب قائمة المطور: زرين بكل صف، وبنفس ترتيب الأقسام تقريباً
    m=types.InlineKeyboardMarkup(row_width=2)

    def add_pair(key1, key2=None):
        buttons=[]
        for key in (key1, key2):
            if not key or not has_bot_permission(uid, key):
                continue
            cb = "admin_whispers" if key == "view_whispers" else key
            buttons.append(types.InlineKeyboardButton(BOT_PANEL_PERMISSIONS[key], callback_data=cb))
        if buttons:
            m.row(*buttons)

    # المراقبة
    add_pair("bot_stats", "bot_groups")
    add_pair("bot_gold", "bot_top_active")

    # الأدوات
    add_pair("bot_gift", "bot_ban_game")
    add_pair("bot_reset_all", "bot_reset_gold")
    add_pair("bot_search_user", "bot_reset_group")

    # التواصل
    add_pair("bot_broadcast_groups", "bot_broadcast_user")

    # الألعاب
    add_pair("dev_games_menu", "manage_anime")
    add_pair("manage_players", "view_whispers")

    # النظام
    add_pair("bot_maintenance", "bot_backup")
    add_pair("bot_error_log")

    m.add(types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"))
    return m

def admin_panel_text(uid):
    rec=ensure_bot_admins().get(str(uid),{})
    return f"🛡️ <b>لوحة أدمن البوت</b>\n\n👤 {html.escape(str(rec.get('name','أدمن')))}\nاختر الصلاحية المتاحة لك:", admin_panel_keyboard(uid)

@bot.message_handler(func=lambda m: m.chat.type=="private" and m.from_user.id==BOT_OWNER_ID and m.text and m.text.strip().isdigit() and DB.get("bot_admin_add_wait"))
def owner_finish_add_admin(message):
    uid=int(message.text.strip())
    try:
        bot.get_chat(uid)
    except Exception:
        bot.reply_to(message,"⚠️ لازم المستخدم يكون مسوي /start للبوت أولاً.")
        return
    admins=ensure_bot_admins(); admins[str(uid)]={"name":human_name(bot.get_chat(uid)),"permissions":{}}
    DB.pop("bot_admin_add_wait",None); save_db()
    bot.reply_to(message,"✅ تمت إضافة الأدمن. ادخل على «صلاحيات الأدمن» وحدد الصلاحيات.")

@bot.callback_query_handler(func=lambda c: c.data in ("bot_add_admin","bot_list_admins","bot_admin_permissions"))
def bot_admin_management_callback(call):
    if call.from_user.id!=BOT_OWNER_ID:
        bot.answer_callback_query(call.id,"⛔ هذه الميزة للمطور فقط.",show_alert=True); return
    data=call.data; admins=ensure_bot_admins()
    if data=="bot_add_admin":
        DB["bot_admin_add_wait"]={"owner":BOT_OWNER_ID}; save_db()
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,"➕ <b>إضافة أدمن</b>\n\nأرسل الآن <b>آيدي المستخدم</b> بعد أن يكون مسوي /start للبوت.",parse_mode="HTML")
    elif data=="bot_list_admins":
        m=types.InlineKeyboardMarkup(row_width=1)
        for uid,rec in admins.items(): m.add(types.InlineKeyboardButton(f"👤 {rec.get('name',uid)} — {uid}",callback_data=f"admin_view_{uid}"))
        m.add(types.InlineKeyboardButton("🔙 رجوع",callback_data="owner_back"))
        txt="👥 <b>أدمنية البوت:</b>\n\n"+ ("لا يوجد أدمنية." if not admins else "اختر أدمن:")
        bot.edit_message_text(txt,call.message.chat.id,call.message.message_id,reply_markup=m,parse_mode="HTML")
    else:
        m=types.InlineKeyboardMarkup(row_width=1)
        for uid,rec in admins.items(): m.add(types.InlineKeyboardButton(f"⚙️ {rec.get('name',uid)}",callback_data=f"admin_perms_{uid}"))
        m.add(types.InlineKeyboardButton("🔙 رجوع",callback_data="owner_back"))
        bot.edit_message_text("⚙️ <b>صلاحيات الأدمن</b>\n\nاختر الأدمن الذي تريد تعديل صلاحياته:",call.message.chat.id,call.message.message_id,reply_markup=m,parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_perms_") or c.data.startswith("admin_view_"))
def admin_detail_callback(call):
    if call.from_user.id!=BOT_OWNER_ID: bot.answer_callback_query(call.id,"⛔ للمطور فقط.",show_alert=True); return
    parts=call.data.split("_",2); uid=parts[2]; admins=ensure_bot_admins(); rec=admins.get(uid)
    if not rec: bot.answer_callback_query(call.id,"الأدمن غير موجود",show_alert=True); return
    if parts[1]=="view":
        perms=[label for key,label in BOT_PANEL_PERMISSIONS.items() if rec.get("permissions",{}).get(key)]
        txt=f"👤 <b>{html.escape(rec.get('name',uid))}</b>\n🆔 <code>{uid}</code>\n\nالصلاحيات:\n"+ ("\n".join("✅ "+x for x in perms) if perms else "❌ لا توجد")
        m=types.InlineKeyboardMarkup(); m.add(types.InlineKeyboardButton("🗑️ حذف الأدمن",callback_data=f"admin_del_{uid}"),types.InlineKeyboardButton("🔙 رجوع",callback_data="bot_list_admins"))
    else:
        m=types.InlineKeyboardMarkup(row_width=2)
        perm_buttons=[]
        for key,label in BOT_PANEL_PERMISSIONS.items():
            on=bool(rec.get("permissions",{}).get(key))
            perm_buttons.append(types.InlineKeyboardButton(("✅ " if on else "❌ ")+label,callback_data=f"admin_toggle_{uid}_{key}"))
        for i in range(0, len(perm_buttons), 2):
            m.row(*perm_buttons[i:i+2])
        m.add(types.InlineKeyboardButton("🔙 رجوع",callback_data="bot_admin_permissions"))
        txt=f"⚙️ <b>صلاحيات {html.escape(rec.get('name',uid))}</b>\n\nاضغط على أي صلاحية لتشغيلها/إطفائها."
    bot.edit_message_text(txt,call.message.chat.id,call.message.message_id,reply_markup=m,parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_toggle_") or c.data.startswith("admin_del_"))
def admin_toggle_callback(call):
    if call.from_user.id!=BOT_OWNER_ID: bot.answer_callback_query(call.id,"⛔ للمطور فقط.",show_alert=True); return
    admins=ensure_bot_admins()
    if call.data.startswith("admin_del_"):
        uid=call.data[len("admin_del_"):]; admins.pop(uid,None); save_db(); bot.answer_callback_query(call.id,"✅ تم حذف الأدمن"); return
    _,_,uid,key=call.data.split("_",3); rec=admins.get(uid)
    if not rec: return
    rec.setdefault("permissions",{})[key]=not rec["permissions"].get(key,False); save_db(); bot.answer_callback_query(call.id,"تم تحديث الصلاحية")
    # إعادة عرض القائمة
    m=types.InlineKeyboardMarkup(row_width=2)
    perm_buttons=[]
    for k,label in BOT_PANEL_PERMISSIONS.items():
        perm_buttons.append(types.InlineKeyboardButton(("✅ " if rec["permissions"].get(k) else "❌ ")+label,callback_data=f"admin_toggle_{uid}_{k}"))
    for i in range(0, len(perm_buttons), 2):
        m.row(*perm_buttons[i:i+2])
    m.add(types.InlineKeyboardButton("🔙 رجوع",callback_data="bot_admin_permissions"))
    bot.edit_message_reply_markup(call.message.chat.id,call.message.message_id,reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data=="admin_whispers")
def admin_whispers_callback(call):
    if not has_bot_permission(call.from_user.id,"view_whispers"): bot.answer_callback_query(call.id,"⛔ لا تملك صلاحية مشاهدة الهمسات.",show_alert=True); return
    bot.answer_callback_query(call.id,"💌 صلاحية مشاهدة الهمسات مفعلة لك.")

# ================================================================
# V24 FEATURES — همسات + أول تشغيل + تفاعل الألعاب + ألعاب الصور
# ================================================================
WHISPER_TRIGGERS = {"همسة", "همسه", "اهمس", "همس"}

# تخزين جلسات الهمس داخل DB حتى لا تضيع بعد إعادة تشغيل البوت
def ensure_whisper_store():
    if "whispers" not in DB or not isinstance(DB.get("whispers"), dict):
        DB["whispers"] = {}
    if "whisper_compose" not in DB or not isinstance(DB.get("whisper_compose"), dict):
        DB["whisper_compose"] = {}
    return DB["whispers"]

def whisper_user_link(user, fallback_id=None):
    uid = getattr(user, "id", fallback_id)
    name = human_name(user) if user is not None else str(uid)
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'

def whisper_bot_username():
    try:
        return bot.get_me().username
    except Exception:
        return None

def whisper_deeplink(param):
    u = whisper_bot_username()
    return f"https://t.me/{u}?start={param}" if u else None

def whisper_new_id():
    import uuid
    return uuid.uuid4().hex[:20]

def whisper_is_allowed(w):
    uid = w.get("sender_id")
    return uid is not None

def whisper_open_markup(wid):
    """زر عرض الهمسة: النص/الستيكر يفتحان داخل القروب،
    أما الصورة/الفيديو/GIF فتذهب للخاص حتى لا يظهر محتواها بالقروب."""
    w = DB.get("whispers", {}).get(str(wid), {})
    kind = w.get("kind")
    m = types.InlineKeyboardMarkup(row_width=1)
    if kind in ("photo", "video", "animation"):
        url = whisper_deeplink("whopen_" + str(wid))
        if url:
            m.add(types.InlineKeyboardButton("🔐 رؤية الهمسة", url=url, style="primary"))
    else:
        m.add(types.InlineKeyboardButton("📨 رؤية الهمسة", callback_data=f"whview_{wid}", style="primary"))
    return m

def whisper_add_markup(chat_id, recipient_id):
    url = whisper_deeplink(f"whadd_{chat_id}_{recipient_id}")
    m = types.InlineKeyboardMarkup(row_width=1)
    if url:
        m.add(types.InlineKeyboardButton("🔵 أضف همستك", url=url, style="primary"))
    return m

def whisper_admin_can_view(uid):
    # المطور + أدمنية البوت الذين لديهم صلاحية مشاهدة الهمسات
    if uid == BOT_OWNER_ID:
        return True
    admins = DB.get("bot_admins", {})
    rec = admins.get(str(uid), {}) if isinstance(admins, dict) else {}
    return bool(rec.get("permissions", {}).get("view_whispers"))

def whisper_render_private(w, chat_id):
    kind = w.get("kind")
    text_value = w.get("text") or ""
    if kind == "text":
        bot.send_message(chat_id, "🔐 <b>همستك الخاصة:</b>\n\n" + html.escape(text_value), parse_mode="HTML")
    elif kind == "sticker":
        if text_value:
            bot.send_message(chat_id, "🔐 <b>همستك الخاصة:</b>\n\n" + html.escape(text_value), parse_mode="HTML")
        bot.send_sticker(chat_id, w["file_id"])
    elif kind == "photo":
        bot.send_photo(chat_id, w["file_id"], caption=("🔐 <b>همستك الخاصة</b>\n\n" + html.escape(text_value))[:1024], parse_mode="HTML")
    elif kind == "video":
        bot.send_video(chat_id, w["file_id"], caption=("🔐 <b>همستك الخاصة</b>\n\n" + html.escape(text_value))[:1024], parse_mode="HTML")
    elif kind == "animation":
        bot.send_animation(chat_id, w["file_id"], caption=("🔐 <b>همستك الخاصة</b>\n\n" + html.escape(text_value))[:1024], parse_mode="HTML")

def whisper_make_group_card(w):
    sender = w.get("sender_name", "مرسل")
    recipient = w.get("recipient_name", "المستلم")
    s_link = f'<a href="tg://user?id={w["sender_id"]}">{html.escape(sender)}</a>'
    r_link = f'<a href="tg://user?id={w["recipient_id"]}">{html.escape(recipient)}</a>'
    kind = w.get("kind")
    if kind == "photo":
        content_label = "🖼 صورة خاصة"
    elif kind == "video":
        content_label = "🎥 فيديو خاص"
    elif kind == "animation":
        content_label = "🎞 متحركة خاصة"
    elif kind == "sticker":
        content_label = "🎭 ملصق خاص"
    else:
        content_label = "💬 نص خاص"
    if kind in ("text", "sticker"):
        hint = "👁️ اضغط زر رؤية الهمسة لعرضها."
    else:
        hint = "🔒 محتوى الهمسة مخفي ويُفتح في خاص البوت فقط."
    return (
        f"💌 <b>همسة خاصة</b>\n\n"
        f"👤 من: {s_link}\n"
        f"👤 إلى: {r_link}\n"
        f"📦 المحتوى: <b>{content_label}</b>\n\n"
        f"{hint}"
    )

@bot.message_handler(func=lambda m: is_group(m) and bool(m.text) and m.reply_to_message is not None and m.text.strip().lower() in WHISPER_TRIGGERS)
def whisper_trigger(message):
    target = message.reply_to_message.from_user
    if not target or target.is_bot:
        return
    if target.id == message.from_user.id:
        bot.reply_to(message, "⚠️ ما تكدر تسوي همسة لنفسك.")
        return
    url = whisper_deeplink(f"whadd_{message.chat.id}_{target.id}")
    if not url:
        bot.reply_to(message, "⚠️ تعذر فتح الهمسة حالياً.")
        return
    bot.reply_to(message, "💌 <b>همسة خاصة</b>\nاضغط الزر وأرسل همستك للخاص:", parse_mode="HTML", reply_markup=whisper_add_markup(message.chat.id, target.id))

# استقبال محتوى الهمسة في الخاص
@bot.message_handler(content_types=["text", "photo", "video", "sticker", "animation"], func=lambda m: m.chat.type == "private" and str(m.from_user.id) in DB.get("whisper_compose", {}))
def whisper_receive_private(message):
    key = str(message.from_user.id)
    compose = DB.get("whisper_compose", {}).get(key)
    if not compose:
        return
    if message.text and message.text.strip().startswith("/start"):
        return
    store = ensure_whisper_store()
    wid = whisper_new_id()
    target_id = int(compose["recipient_id"])
    try:
        target_info = bot.get_chat(target_id)
        recipient_name = human_name(target_info)
    except Exception:
        recipient_name = str(target_id)
    sender_name = human_name(message.from_user)
    w = {"sender_id": message.from_user.id, "recipient_id": target_id, "sender_name": sender_name, "recipient_name": recipient_name, "chat_id": int(compose["chat_id"]), "created_at": time.time()}
    if message.content_type == "text":
        w.update(kind="text", text=message.text)
    elif message.content_type == "sticker":
        w.update(kind="sticker", file_id=message.sticker.file_id, text=message.caption or "")
    elif message.content_type == "photo":
        w.update(kind="photo", file_id=message.photo[-1].file_id, text=message.caption or "")
    elif message.content_type == "video":
        w.update(kind="video", file_id=message.video.file_id, text=message.caption or "")
    elif message.content_type == "animation":
        w.update(kind="animation", file_id=message.animation.file_id, text=message.caption or "")
    else:
        bot.send_message(message.chat.id, "⚠️ هذا النوع من الوسائط غير مدعوم حالياً.")
        return
    store[wid] = w
    DB["whisper_compose"].pop(key, None)
    save_db()
    try:
        bot.send_message(message.chat.id, "✅ تم إرسال الهمسة بنجاح.")
        # الهمسة دائماً تُعرض كبطاقة مخفية داخل القروب.
        # المحتوى (نص/ستيكر/صورة/فيديو/GIF وحتى الوسائط مع كابتشن) لا يُرسل للقروب.
        # عند الضغط على الزر يفتح رابط خاص البوت، ثم يتحقق البوت من الصلاحية ويعرض المحتوى هناك.
        card = whisper_make_group_card(w)
        bot.send_message(
            w["chat_id"],
            card,
            parse_mode="HTML",
            reply_markup=whisper_open_markup(wid)
        )
    except Exception:
        bot.send_message(message.chat.id, "⚠️ تم حفظ الهمسة لكن تعذر إرسالها للقروب.")

# أوامر deep-link الخاصة بالهمسات داخل /start

def handle_whisper_start(message, param):
    parts = param.split("_")
    uid = message.from_user.id
    if param.startswith("whadd_") and len(parts) >= 3:
        try:
            chat_id = int(parts[1]); recipient_id = int(parts[2])
        except Exception:
            return False
        DB.setdefault("whisper_compose", {})[str(uid)] = {"chat_id": chat_id, "recipient_id": recipient_id, "created_at": time.time()}
        save_db()
        bot.send_message(message.chat.id, "💌 <b>اكتب همستك الآن</b>\n\nتقدر ترسل نص، صورة، فيديو أو ملصق.", parse_mode="HTML")
        return True
    if param.startswith("whopen_") and len(param) > 7:
        wid = param[7:]
        w = DB.get("whispers", {}).get(wid)
        if not w:
            bot.send_message(message.chat.id, "⚠️ هذه الهمسة غير موجودة أو انتهت.")
            return True
        if uid not in (w.get("sender_id"), w.get("recipient_id")) and not whisper_admin_can_view(uid):
            bot.send_message(message.chat.id, "👁️ مو إلك عيناي، هذه الهمسة خاصة بصاحبها ومستلمها.")
            try:
                bot.send_message(w["sender_id"], "👁️ شخص حاول فتح همستك بدون صلاحية.")
                bot.send_message(w["recipient_id"], "👁️ شخص حاول فتح همستك بدون صلاحية.")
            except Exception: pass
            return True
        # هذا المسار يعمل في خاص البوت فقط، لذلك الصورة/الفيديو/النص لا يعودان للقروب.
        try:
            whisper_render_private(w, message.chat.id)
        except Exception:
            bot.send_message(message.chat.id, "⚠️ تعذر عرض محتوى الهمسة حالياً.")
        return True
    return False

# صلاحيات تفاعل البوت + التوب

def add_interaction(chat_id, user_id, amount=1):
    try:
        chat = ensure_chat(chat_id)
        chat["messages"][str(user_id)] = chat["messages"].get(str(user_id), 0) + int(amount)
        save_db()
    except Exception:
        pass

# ألعاب الصور: يتم تخزين file_id مسبقاً، والأسماء/البدائل في DB

def ensure_picture_games():
    if "picture_games" not in DB or not isinstance(DB.get("picture_games"), dict):
        DB["picture_games"] = {"anime": [], "players": []}
    DB["picture_games"].setdefault("anime", [])
    DB["picture_games"].setdefault("players", [])
    return DB["picture_games"]

def normalize_game_answer(x):
    x = (x or "").strip().lower()
    x = re.sub(r"[\u064B-\u065F\u0670]", "", x)
    x = re.sub(r"[إأآا]", "ا", x)
    return re.sub(r"\s+", " ", x)

def start_picture_game(message, category):
    if not is_group(message): return
    add_interaction(message.chat.id, message.from_user.id)
    if not games_allowed(message.chat.id): return
    games = ensure_picture_games().get(category, [])
    if not games:
        bot.reply_to(message, "⚠️ ماكو صور محفوظة لهذه اللعبة حالياً. يضيفها المطور أولاً.")
        return
    item = random.choice(games)
    DB.setdefault("picture_game_sessions", {})[str(message.chat.id)] = {"category": category, "item": item, "started_by": message.from_user.id, "created_at": time.time()}
    save_db(); add_interaction(message.chat.id, message.from_user.id)
    title = "🎌 أنمي" if category == "anime" else "⚽ لاعبين"
    bot.send_photo(message.chat.id, item["file_id"], caption=f"{title}\n\n🧐 من هذا؟ اكتب الاسم!")

@bot.message_handler(func=lambda m: is_group(m) and m.text and m.text.strip() in ("أنمي", "انمي"))
def anime_picture_game(message): start_picture_game(message, "anime")

@bot.message_handler(func=lambda m: is_group(m) and m.text and m.text.strip() in ("لاعب", "لاعبين", "كرة قدم"))
def player_picture_game(message): start_picture_game(message, "players")

@bot.message_handler(func=lambda m: is_group(m) and m.text and str(m.chat.id) in DB.get("picture_game_sessions", {}))
def picture_game_answer(message):
    add_interaction(message.chat.id, message.from_user.id)
    sess = DB.get("picture_game_sessions", {}).get(str(message.chat.id))
    if not sess or not message.text: return
    item = sess["item"]
    answers = [item.get("name", "")] + item.get("aliases", [])
    if normalize_game_answer(message.text) in {normalize_game_answer(a) for a in answers}:
        add_interaction(message.chat.id, message.from_user.id)
        bot.reply_to(message, f"🎉 إجابة صحيحة!\n🏆 <b>{html.escape(item.get('name',''))}</b>\n+1 تفاعل", parse_mode="HTML")
        DB["picture_game_sessions"].pop(str(message.chat.id), None); save_db()

# إضافة صور الألعاب من المطور: رد على الصورة ثم: إضافة أنمي <الاسم> [|اسم بديل]
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.startswith("إضافة أنمي") and m.reply_to_message and m.reply_to_message.photo)
def owner_add_anime(message):
    parts = message.text.split(maxsplit=1)
    name = parts[1].strip() if len(parts) > 1 else ""
    if not name: return bot.reply_to(message, "اكتب: إضافة أنمي اسم الشخصية")
    games=ensure_picture_games(); names=[x.strip() for x in name.split("|") if x.strip()]
    games["anime"].append({"name":names[0],"aliases":names[1:],"file_id":message.reply_to_message.photo[-1].file_id}); save_db(); bot.reply_to(message,"✅ تم حفظ صورة شخصية الأنمي.")

@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.startswith("إضافة لاعب") and m.reply_to_message and m.reply_to_message.photo)
def owner_add_player(message):
    parts = message.text.split(maxsplit=1)
    name = parts[1].strip() if len(parts) > 1 else ""
    if not name: return bot.reply_to(message, "اكتب: إضافة لاعب اسم اللاعب")
    games=ensure_picture_games(); names=[x.strip() for x in name.split("|") if x.strip()]
    games["players"].append({"name":names[0],"aliases":names[1:],"file_id":message.reply_to_message.photo[-1].file_id}); save_db(); bot.reply_to(message,"✅ تم حفظ صورة اللاعب.")


@bot.message_handler(content_types=["photo"], func=lambda m: m.chat.type == "private" and str(m.from_user.id) in DB.get("picture_add_sessions", {}) and DB.get("picture_add_sessions", {}).get(str(m.from_user.id),{}).get("step") == "photo")
def picture_add_photo_step(message):
    sess=DB["picture_add_sessions"][str(message.from_user.id)]
    sess["step"]="answer"
    sess["file_id"]=message.photo[-1].file_id
    save_db()
    title="الأنمي" if sess["category"]=="anime" else "اللاعب"
    bot.send_message(message.chat.id, f"✅ تم استلام الصورة.\n\n✏️ الآن أرسل جواب {title} الصحيح.\nيمكنك كتابة الأسماء البديلة بهذا الشكل: الاسم | البديل1 | البديل2")

@bot.message_handler(content_types=["text"], func=lambda m: m.chat.type == "private" and str(m.from_user.id) in DB.get("picture_add_sessions", {}) and DB.get("picture_add_sessions", {}).get(str(m.from_user.id),{}).get("step") == "answer")
def picture_add_answer_step(message):
    uid=str(message.from_user.id); sess=DB["picture_add_sessions"].get(uid)
    if not sess: return
    raw=message.text.strip()
    if not raw:
        bot.reply_to(message,"⚠️ ارسل الجواب الصحيح."); return
    names=[x.strip() for x in raw.split("|") if x.strip()]
    if not names:
        bot.reply_to(message,"⚠️ ارسل الجواب الصحيح."); return
    games=ensure_picture_games(); cat=sess["category"]
    games[cat].append({"name":names[0],"aliases":names[1:],"file_id":sess["file_id"]})
    DB["picture_add_sessions"].pop(uid,None); save_db()
    title="🎌 الأنمي" if cat=="anime" else "⚽ اللاعبين"
    bot.reply_to(message,f"✅ تم حفظ الصورة والجواب ضمن {title}.\n🎯 الجواب: <b>{html.escape(names[0])}</b>",parse_mode="HTML")

@bot.message_handler(commands=['start'])
def start_command(message):
    if message.chat.type != "private":
        bot.reply_to(message, "🔰 <b>أهلاً بك!</b>\n💡 اكتب <code>تعليمات</code> لرؤية جميع الأوامر")
        return
    # ===== دعم رابط الدخول المباشر للعبة السحرة (deep link) =====
    _start_parts = message.text.split(maxsplit=1) if message.text else []
    if len(_start_parts) > 1 and _start_parts[1].strip().startswith("wzjoin_"):
        try:
            wz_handle_deeplink_join(message, _start_parts[1].strip())
        except Exception as _e:
            try:
                log_error(f"wz_handle_deeplink_join error: {_e}")
            except:
                pass
        return
    # ===== دعم رابط الدخول المباشر للعبة عرش المملكة (deep link) =====
    if len(_start_parts) > 1 and _start_parts[1].strip().startswith("thrjoin_"):
        try:
            thr_handle_deeplink_join(message, _start_parts[1].strip())
        except Exception as _e:
            try:
                log_error(f"thr_handle_deeplink_join error: {_e}")
            except:
                pass
        return
    # ===== دعم رابط الدخول المباشر للعبة المافيا (deep link) =====
    if len(_start_parts) > 1 and _start_parts[1].strip().startswith("mfjoin_"):
        try:
            mf_handle_deeplink_join(message, _start_parts[1].strip())
        except Exception as _e:
            try:
                log_error(f"mf_handle_deeplink_join error: {_e}")
            except:
                pass
        return
    user_id = message.from_user.id
    name = human_name(message.from_user)
    # همسات deep-link
    if len(_start_parts) > 1 and handle_whisper_start(message, _start_parts[1].strip()):
        return
    # إشعار المطور بأول /start فقط
    users_started = DB.setdefault("started_users", {})
    if str(user_id) not in users_started:
        users_started[str(user_id)] = {"first_start": time.time()}
        save_db()
        if user_id != BOT_OWNER_ID:
            try:
                info = bot.get_chat(user_id)
                bio = getattr(info, "bio", None) or "لا يوجد بايو"
            except Exception:
                info = message.from_user
                bio = "لا يوجد بايو"
            uname = f"@{info.username}" if getattr(info, "username", None) else "بدون يوزر"
            when = datetime.now().strftime("%Y-%m-%d %H:%M")
            txt = ("🎉 <b>انضم مستخدم جديد إلى البوت!</b>\n\n"
                   f"👤 الاسم: {html.escape(name)} — {when}\n"
                   f"📌 اليوزر: {html.escape(uname)}\n"
                   f"🆔 الـ ID: <code>{user_id}</code>\n"
                   f"📝 البايو: {html.escape(str(bio))}")
            try:
                photos = bot.get_user_profile_photos(user_id, limit=1)
                if photos.total_count:
                    bot.send_photo(BOT_OWNER_ID, photos.photos[0][-1].file_id, caption=txt, parse_mode="HTML")
                else:
                    bot.send_message(BOT_OWNER_ID, txt, parse_mode="HTML")
            except Exception:
                try: bot.send_message(BOT_OWNER_ID, txt, parse_mode="HTML")
                except Exception: pass
    WELCOME_STICKER = "CAACAgIAAxkBAAEBmZ5lJ9z2AAFCfAABqvJ2kHs3VWuQAAF_AAJP9R0AAc7GpRfAAd5pHjAE"
    try:
        bot.send_sticker(message.chat.id, WELCOME_STICKER)
    except:
        pass
    if user_id != BOT_OWNER_ID and is_bot_admin(user_id):
        txt, mk = admin_panel_text(user_id)
        bot.send_message(message.chat.id, txt, parse_mode="HTML", reply_markup=mk)
        return
    if user_id == BOT_OWNER_ID:
        banking = ensure_banking()
        total_users = len(banking["users"])
        total_groups = sum(1 for cid in DB.keys() if cid.isdigit())
        total_wealth = sum(ud.get("balance", 0) for ud in banking["users"].values())
        bot.send_message(message.chat.id,
            f"👑 <b>أهلاً يا مطور ايتو!</b>\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 <b>إحصائيات سريعة:</b>\n"
            f"• المستخدمين: <b>{total_users}</b>\n"
            f"• القروبات: <b>{total_groups}</b>\n"
            f"• إجمالي الفلوس: <b>{total_wealth:,} دولار</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛠️ اختر من لوحة التحكم:",
            reply_markup=create_owner_keyboard()
        )
    else:
        dev_id   = BOT_OWNER_ID
        dev_username = None
        try:
            dev_info = bot.get_chat(dev_id)
            dev_name = human_name(dev_info)
            dev_username = dev_info.username
        except:
            dev_name = "المطور"
        # استخدام يوزر مباشر إن وجد (أضمن للرندر الأزرق)، وإلا tg://user كحل بديل
        if dev_username:
            dev_link = f'<a href="https://t.me/{dev_username}">{dev_name}</a>'
        else:
            dev_link = f'<a href="tg://user?id={dev_id}">{dev_name}</a>'

        welcome_text = (
            f"أهلاً بك عزيزي انا بوت اسمي ايتو\n"
            f"اختصاص البوت حماية المجموعات\n"
            f"اضف البوت الى مجموعتك .\n"
            f"ارفعه ادمن مشرف\n"
            f"ارفعه مشرف وارسل تفعيل ليتم تفعيل المجموعة .\n"
            f"مطور البوت ← {dev_link}"
        )

        # ===== زر باسم المطور يفتح حسابه =====
        dev_markup = types.InlineKeyboardMarkup(row_width=1)
        dev_markup.add(types.InlineKeyboardButton(
            f"➕ اضفني لمجموعتك", url="https://t.me/ri5xbot?startgroup=true", style="success"
        ))
        dev_markup.add(types.InlineKeyboardButton(
            "🎮 الألعاب", callback_data="user_games_menu_home", style="success"
        ))
        dev_markup.add(types.InlineKeyboardButton(
            f"{dev_name}", url=f"tg://user?id={dev_id}", style="primary"
        ))

        # ===== زر القناة بالاسم الديناميكي =====
        try:
            channel_info = bot.get_chat("@R_5_XT")
            channel_name = channel_info.title or "القناة"
        except:
            channel_name = "القناة"
        dev_markup.add(types.InlineKeyboardButton(
            f"{channel_name}", url="https://t.me/R_5_XT", style="primary"
        ))

        # ===== صورة حساب العضو نفسه فوق رسالة الترحيب =====
        try:
            user_photos = bot.get_user_profile_photos(user_id, limit=1)
            if user_photos.total_count > 0:
                user_photo_id = user_photos.photos[0][-1].file_id
                bot.send_photo(message.chat.id, user_photo_id,
                               caption=welcome_text, parse_mode="HTML", reply_markup=dev_markup)
            else:
                bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=dev_markup)
        except:
            bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=dev_markup)


# ========= معالج الكولباك =========
# ========= أوامر اليوتيوب (يوت / بحث) — تشتغل بالقروبات المفعّلة فقط، مطفية بالخاص =========
def _yt_group_permission_check(chat_id):
    """يرجع رسالة رفض إذا القروب ما يحق له يستخدم اليوتيوب، أو None إذا مسموح"""
    if is_yt_maintenance():
        return "🛠 خاصية اليوتيوب تحت الصيانة حالياً، حاول لاحقاً."
    if not is_yt_group_active(chat_id):
        return "⛔ خاصية اليوتيوب مو مفعّلة بهذا القروب.\nفعّلها بكتابة: <code>تفعيل اليوتيوب</code>"
    return None


@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text and re.match(r'^(يوت|YT|yt)\s+(.+)', m.text.strip()))
def yt_quick_audio(message):
    chat_id = message.chat.id
    denial = _yt_group_permission_check(chat_id)
    if denial:
        bot.reply_to(message, denial, parse_mode="HTML")
        return

    match = re.match(r'^(يوت|YT|yt)\s+(.+)', message.text.strip())
    query = match.group(2).strip()
    norm_query = yt_normalize_query(query)
    wait_msg = bot.reply_to(message, "🔍 جاري البحث والتحميل...")

    def _job():
        file_path = None
        try:
            query_cache = ensure_yt_query_cache()
            vid_id = query_cache.get(norm_query)

            # 1) لو نفس البحث محفوظ من قبل وعندنا ملف جاهز له بالكاش -> إرسال فوري بدون تحميل
            if vid_id:
                cached = yt_get_cached_file(vid_id, "audio")
                if cached:
                    yt_send_cached(chat_id, cached, "audio")
                    try:
                        bot.delete_message(chat_id, wait_msg.message_id)
                    except:
                        pass
                    return

            # 2) لو ما عندنا id الفيديو أصلاً -> نبحث عنه (مرة وحدة فقط لكل نص بحث)
            if not vid_id:
                search = YoutubeSearch(query, max_results=1).to_dict()
                if not search:
                    bot.edit_message_text("❌ لم يتم العثور على نتائج.", chat_id, wait_msg.message_id)
                    return
                vid_id = search[0]["id"]
                query_cache[norm_query] = vid_id
                save_db()

            # 3) حتى لو نص البحث جديد، ممكن نفس الفيديو انحمل قبل من بحث ثاني -> نتأكد بالكاش
            cached = yt_get_cached_file(vid_id, "audio")
            if cached:
                yt_send_cached(chat_id, cached, "audio")
                try:
                    bot.delete_message(chat_id, wait_msg.message_id)
                except:
                    pass
                return

            # 4) ما فيه كاش -> نحمّل فعلياً
            url = f"https://youtu.be/{vid_id}"
            unique = f"{message.from_user.id}_{int(time.time())}"
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": f"{YT_DOWNLOAD_DIR}/{unique}_%(id)s.%(ext)s",
                "quiet": True,
                **yt_cookie_opts()
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            caption = yt_build_caption(info)
            sent = yt_send_result_file(chat_id, file_path, "audio", info.get("title", "audio"), caption)
            file_id = yt_extract_file_id(sent, "audio")
            if file_id:
                yt_store_cached_file(vid_id, "audio", file_id, info.get("title", ""), info.get("duration", 0))
            try:
                bot.delete_message(chat_id, wait_msg.message_id)
            except:
                pass
        except Exception as e:
            try:
                bot.edit_message_text(f"❌ صار خطأ: {e}", chat_id, wait_msg.message_id)
            except:
                pass
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    Thread(target=_job, daemon=True).start()


@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text and re.match(r'^بحث\s+(.+)', m.text.strip()))
def yt_search_command(message):
    chat_id = message.chat.id
    denial = _yt_group_permission_check(chat_id)
    if denial:
        bot.reply_to(message, denial, parse_mode="HTML")
        return

    query = re.match(r'^بحث\s+(.+)', message.text.strip()).group(1).strip()
    wait_msg = bot.reply_to(message, f"🔎 جاري البحث عن: {query}")

    def _job():
        try:
            res = YoutubeSearch(query, max_results=5).to_dict()
            if not res:
                bot.edit_message_text("❌ لم يتم العثور على نتائج.", chat_id, wait_msg.message_id)
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            for r in res:
                markup.add(types.InlineKeyboardButton(f"🎬 {r['title'][:35]}", callback_data=f"ytopt_{r['id']}"))
            bot.edit_message_text(f"🔎 نتائج البحث عن: {query}\n\nاختر المطلوب:",
                                   chat_id, wait_msg.message_id, reply_markup=markup)
        except Exception as e:
            try:
                bot.edit_message_text(f"❌ صار خطأ: {e}", chat_id, wait_msg.message_id)
            except:
                pass

    Thread(target=_job, daemon=True).start()


@bot.callback_query_handler(func=lambda c: c.data.startswith("ytopt_") or c.data.startswith("ytdown_"))
def yt_search_callback(call):
    chat_id = call.message.chat.id
    denial = _yt_group_permission_check(chat_id)
    if denial:
        bot.answer_callback_query(call.id, "⛔ خاصية اليوتيوب مو مفعّلة أو تحت الصيانة.", show_alert=True)
        return

    if call.data.startswith("ytopt_"):
        vid = call.data.split("_", 1)[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("صوت 🎵", callback_data=f"ytdown_m4a_{vid}"),
            types.InlineKeyboardButton("فيديو 🎥", callback_data=f"ytdown_mp4_{vid}")
        )
        try:
            bot.edit_message_text("اختر نوع التحميل:", chat_id, call.message.message_id, reply_markup=markup)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    # ytdown_
    _, ftype, vid = call.data.split("_", 2)
    bot.answer_callback_query(call.id, "⏳ جاري التحميل...")
    try:
        bot.edit_message_text("⏳ جاري التحميل...", chat_id, call.message.message_id)
    except:
        pass

    def _job():
        file_path = None
        try:
            kind = "audio" if ftype == "m4a" else "video"

            # لو نفس الفيديو ونفس النوع (صوت/فيديو) محمّل من قبل -> إرسال فوري بدون تحميل
            cached = yt_get_cached_file(vid, kind)
            if cached:
                yt_send_cached(chat_id, cached, kind)
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except:
                    pass
                return

            url = f"https://youtu.be/{vid}"
            ydl_opts = {
                "format": "bestaudio/best" if ftype == "m4a" else "best",
                "outtmpl": f"{YT_DOWNLOAD_DIR}/{vid}_{int(time.time())}.%(ext)s",
                "quiet": True,
                "extractor_args": {"youtube": {"player_client": ["android", "web_safari"]}},
                **yt_cookie_opts()
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            caption = yt_build_caption(info)
            sent = yt_send_result_file(chat_id, file_path, kind, info.get("title", "media"), caption)
            file_id = yt_extract_file_id(sent, kind)
            if file_id:
                yt_store_cached_file(vid, kind, file_id, info.get("title", ""), info.get("duration", 0))
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
        except Exception as e:
            try:
                bot.send_message(chat_id, f"❌ صار خطأ: {e}")
            except:
                pass
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    Thread(target=_job, daemon=True).start()


# ========= أوامر مطور اليوتيوب (خاص + نفس صلاحية BOT_OWNER_ID) =========
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.strip() == "احصائيات اليوتيوب")
def yt_stats_command(message):
    groups = ensure_yt_groups()
    bot.reply_to(message,
        f"📊 <b>إحصائيات اليوتيوب</b>\n\n"
        f"👥 القروبات المفعّلة: {len(groups)}\n"
        f"🛠 الصيانة: {'مفعّلة' if is_yt_maintenance() else 'مطفأة'}",
        parse_mode="HTML")


@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.strip() == "صيانة اليوتيوب")
def yt_toggle_maintenance(message):
    DB["yt_maintenance"] = not is_yt_maintenance()
    save_db()
    bot.reply_to(message, f"🛠 وضع صيانة اليوتيوب الآن: {'مفعّل ✅' if DB['yt_maintenance'] else 'مطفأ ❌'}")


@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.strip() == "قروبات اليوتيوب")
def yt_list_groups(message):
    groups = ensure_yt_groups()
    if not groups:
        bot.reply_to(message, "❌ لا توجد قروبات مفعّل فيها اليوتيوب.")
        return
    txt = "👥 <b>القروبات المفعّل فيها اليوتيوب:</b>\n\n" + "\n".join(f"• <code>{gid}</code>" for gid in groups)
    bot.reply_to(message, txt, parse_mode="HTML")


@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user.id == BOT_OWNER_ID and m.text and m.text.strip().startswith("الغاء تفعيل اليوتيوب"))
def yt_deactivate_group(message):
    parts = message.text.strip().split()
    if len(parts) < 4:
        bot.reply_to(message, "⚠️ استخدم: <code>الغاء تفعيل اليوتيوب [chat_id]</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[3])
    except:
        bot.reply_to(message, "⚠️ الآيدي غير صحيح.")
        return
    groups = ensure_yt_groups()
    if gid in groups:
        groups.remove(gid)
        save_db()
        bot.reply_to(message, f"✅ تم إلغاء تفعيل اليوتيوب بالقروب <code>{gid}</code>.", parse_mode="HTML")
    else:
        bot.reply_to(message, "⚠️ هذا القروب مو مفعّل فيه اليوتيوب أصلاً.")


# ========= callback تأكيد/إلغاء مسح الاختصار (منقول ليشتغل فعلياً) =========
@bot.callback_query_handler(func=lambda c: c.data.startswith("scdel_"))
def scdel_callback(call):
    user_id = call.from_user.id
    data    = call.data
    chat_id = call.message.chat.id
    parts   = data.split("_")
    action  = parts[1]

    if action == "cancel":
        cid = int(parts[2])
        key = f"{cid}_{user_id}"
        shortcut_delete_steps.pop(key, None)
        bot.answer_callback_query(call.id, "❌ تم الالغاء")
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass

    elif action == "confirm":
        cid = int(parts[2])
        key = f"{cid}_{user_id}"
        sess = shortcut_delete_steps.get(key)
        if not sess or "shortcut" not in sess:
            bot.answer_callback_query(call.id, "⚠️ انتهت الجلسة، أعد المحاولة.", show_alert=True)
            return
        shortcut = sess["shortcut"]
        role     = get_role(cid, user_id)
        if role not in SHORTCUT_ALLOWED:
            bot.answer_callback_query(call.id, "⛔ لا تملك الصلاحية", show_alert=True)
            return
        shortcuts = ensure_shortcuts(cid)
        if shortcut in shortcuts:
            del shortcuts[shortcut]
            save_db()
        shortcut_delete_steps.pop(key, None)
        bot.answer_callback_query(call.id, f"✅ تم مسح الاختصار {shortcut}")
        try:
            bot.edit_message_text(f"✅ تم مسح الاختصار <b>{shortcut}</b> بنجاح.",
                                  chat_id, call.message.message_id, parse_mode="HTML")
        except: pass


@bot.callback_query_handler(func=lambda call: not (call.data and (call.data.startswith("wz_") or call.data.startswith("thr_") or call.data.startswith("mf_") or call.data.startswith("v22tr_") or call.data.startswith("v22atk_") or call.data.startswith("v22bid_"))))
def handle_callback(call):
    # شبكة حماية عامة: أي خطأ غير متوقع بأي زر ما يخلي الزر يعلق —
    # نرجع نجاوب تلجرام على طول حتى لو صار استثناء داخل الكود.
    try:
        _handle_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ بسيط، جرب مرة ثانية", show_alert=False)
        except:
            pass
        try:
            print(f"[handle_callback error] data={getattr(call, 'data', None)} err={e}")
        except:
            pass


def _handle_callback_inner(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    # ========= عرض الهمسة داخل القروب للنص/الستيكر فقط =========
    # الصور والفيديو وGIF تستخدم deep-link إلى خاص البوت، لذلك لا تمر من هنا.
    if data.startswith("whview_"):
        wid = data[len("whview_"):]
        w = DB.get("whispers", {}).get(wid)
        if not w:
            bot.answer_callback_query(call.id, "⚠️ هذه الهمسة غير موجودة أو انتهت.", show_alert=True)
            return
        if user_id not in (w.get("sender_id"), w.get("recipient_id")) and not whisper_admin_can_view(user_id):
            bot.answer_callback_query(call.id, "👁️ مو إلك عيناي...", show_alert=True)
            try:
                bot.send_message(w["sender_id"], "👁️ شخص حاول فتح همستك بدون صلاحية.")
                bot.send_message(w["recipient_id"], "👁️ شخص حاول فتح همستك بدون صلاحية.")
            except Exception:
                pass
            return

        kind = w.get("kind")
        # حماية إضافية: إذا كان المحتوى صورة/فيديو/GIF فلا نعرضه داخل القروب.
        if kind in ("photo", "video", "animation"):
            bot.answer_callback_query(call.id, "🔐 هذه الوسائط تفتح في خاص البوت.", show_alert=True)
            return

        try:
            if kind == "text":
                # النص فقط يُعرض كنافذة منبثقة مثل المثال، وليس كرسالة جديدة داخل القروب.
                sender = w.get("sender_name", "عضو")
                text_value = (w.get("text") or "").strip()
                alert_text = f"💌 همسة من {sender}\n\n{text_value}"
                # Telegram يفرض حداً على نص التنبيه، لذلك نقصّه بأمان.
                if len(alert_text) > 200:
                    alert_text = alert_text[:197] + "..."
                bot.answer_callback_query(call.id, alert_text, show_alert=True)
            elif kind == "sticker":
                # الستيكر لا يمكن عرضه داخل نافذة التنبيه، لذلك يبقى عرضه داخل القروب.
                bot.answer_callback_query(call.id, "✅ تم فتح الهمسة.")
                if w.get("text"):
                    bot.send_message(chat_id, html.escape(w["text"]), parse_mode="HTML")
                bot.send_sticker(chat_id, w["file_id"])
            else:
                bot.answer_callback_query(call.id, "⚠️ نوع الهمسة غير مدعوم.", show_alert=True)
        except Exception:
            try:
                bot.answer_callback_query(call.id, "⚠️ تعذر عرض الهمسة حالياً.", show_alert=True)
            except Exception:
                pass
        return

    # ========= إدارة بنك صور الألعاب (المطور/الأدمن المصرح) =========
    if data in ("manage_anime", "manage_players"):
        perm = data
        if not has_bot_permission(user_id, perm):
            bot.answer_callback_query(call.id, "⛔ ما عندك صلاحية لهذه اللعبة.", show_alert=True)
            return
        cat = "anime" if data == "manage_anime" else "players"
        title = "🎌 إدارة الأنمي" if cat == "anime" else "⚽ إدارة اللاعبين"
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            types.InlineKeyboardButton("➕ إضافة صورة", callback_data=f"picadd_{cat}"),
            types.InlineKeyboardButton("🗑️ مسح " + ("أنمي" if cat == "anime" else "لاعب"), callback_data=f"picdel_{cat}"),
        )
        kb.row(types.InlineKeyboardButton("📋 الصور المحفوظة", callback_data=f"piclist_{cat}"))
        kb.row(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        bot.edit_message_text(f"{title}\n\nاختر العملية:", chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("picadd_"):
        cat = data[len("picadd_"):]
        perm = "manage_anime" if cat == "anime" else "manage_players"
        if not has_bot_permission(user_id, perm):
            bot.answer_callback_query(call.id, "⛔ ما عندك صلاحية.", show_alert=True)
            return
        DB.setdefault("picture_add_sessions", {})[str(user_id)] = {"category": cat, "step": "photo"}
        save_db()
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🖼️ أرسل الآن الصورة التي تريد إضافتها.")
        return

    if data.startswith("piclist_"):
        cat=data[len("piclist_"):]
        perm="manage_anime" if cat=="anime" else "manage_players"
        if not has_bot_permission(user_id, perm):
            bot.answer_callback_query(call.id,"⛔ ما عندك صلاحية.",show_alert=True); return
        items=ensure_picture_games().get(cat,[])
        title="🎌 الأنمي" if cat=="anime" else "⚽ اللاعبين"
        txt=title+"\n\n"+("لا توجد صور محفوظة." if not items else "\n".join(f"{i+1}. {html.escape(str(x.get('name','غير معروف')))}" for i,x in enumerate(items[-50:])))
        kb=types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("🗑️ مسح " + ("أنمي" if cat=="anime" else "لاعب"), callback_data=f"picdel_{cat}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع",callback_data="manage_anime" if cat=="anime" else "manage_players"))
        bot.edit_message_text(txt,chat_id,call.message.message_id,reply_markup=kb,parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("picdel_"):
        cat=data[len("picdel_"):]
        if cat not in ("anime", "players"):
            bot.answer_callback_query(call.id,"⚠️ نوع غير صحيح.",show_alert=True); return
        perm="manage_anime" if cat=="anime" else "manage_players"
        if not has_bot_permission(user_id, perm):
            bot.answer_callback_query(call.id,"⛔ ما عندك صلاحية.",show_alert=True); return
        items=ensure_picture_games().get(cat,[])
        title="🎌 حذف أنمي" if cat=="anime" else "⚽ حذف لاعب"
        kb=types.InlineKeyboardMarkup(row_width=2)
        if not items:
            txt=f"{title}\n\n❌ ماكو شخصيات محفوظة حالياً."
        else:
            txt=f"{title}\n\nاختر الشخصية التي تريد حذفها:"
            for i,item in enumerate(items):
                name=html.escape(str(item.get("name","غير معروف")))
                kb.add(types.InlineKeyboardButton(f"🗑️ {name}", callback_data=f"picdelete_{cat}_{i}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"manage_{'anime' if cat=='anime' else 'players'}"))
        bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("picdelete_"):
        parts=data.split("_")
        if len(parts) != 3 or parts[1] not in ("anime", "players") or not parts[2].isdigit():
            bot.answer_callback_query(call.id,"⚠️ اختيار غير صحيح.",show_alert=True); return
        cat=parts[1]
        perm="manage_anime" if cat=="anime" else "manage_players"
        if not has_bot_permission(user_id, perm):
            bot.answer_callback_query(call.id,"⛔ ما عندك صلاحية.",show_alert=True); return
        idx=int(parts[2])
        games=ensure_picture_games()
        items=games.get(cat,[])
        if idx < 0 or idx >= len(items):
            bot.answer_callback_query(call.id,"⚠️ الشخصية غير موجودة أو تم حذفها مسبقاً.",show_alert=True); return
        removed=items.pop(idx)
        save_db()
        removed_name=html.escape(str(removed.get("name","غير معروف")))
        title="الأنمي" if cat=="anime" else "اللاعبين"
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"manage_{'anime' if cat=='anime' else 'players'}"))
        bot.edit_message_text(f"✅ تم حذف <b>{removed_name}</b> من {title}.\n🗑️ تم حذف الاسم والصورة معاً.", chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id,"🗑️ تم الحذف.")
        return

    # ========= التوب =========
    if data.startswith("ntop_"):
        medals = ["🥇","🥈","🥉"]
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="ntop_back"))

        if data == "ntop_back":
            top_markup = build_top_markup()
            try:
                bot.edit_message_text("📊 <b>اختر التوب:</b>", chat_id, call.message.message_id, reply_markup=top_markup)
            except:
                pass
            bot.answer_callback_query(call.id)
            return

        if data == "ntop_money":
            banking = ensure_banking()
            lst = []
            for uid_str, udata in banking["users"].items():
                bal = udata.get("balance", 0)
                if bal <= 0: continue
                try:
                    info = bot.get_chat(int(uid_str))
                    name = safe_name_for_top(info)
                except:
                    name = None
                if name is None: continue
                lst.append((uid_str, name, bal))
            lst.sort(key=lambda x: x[2], reverse=True)
            medals_loc = ["🥇","🥈","🥉"]
            num_emojis_loc = ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
            def rank_icon_loc(i):
                if i < 3: return medals_loc[i]
                if i < 10: return num_emojis_loc[i-3]
                return f"{i+1}."
            txt = "💰 <b>توب أغنى 30 شخص:</b>\n\n"
            user_rank = None
            user_line = ""
            for idx, (uid_str, name, bal) in enumerate(lst):
                if int(uid_str) == user_id:
                    user_rank = idx + 1
                    user_line = f"\n━━━━━━━━━\n• ترتيبك: {user_rank} | رصيدك: {bal:,} 💰"
                    break
            for i, (uid_str, name, bal) in enumerate(lst[:30]):
                txt += f"{rank_icon_loc(i)} {name} ← <b>{bal:,} دولار</b>\n"
            if user_line:
                txt += user_line
            txt += "\n\n⚠️ <i>أي شخص مخالف للعبة بالغش يُحظر وتُصفّر فلوسه</i>"

        elif data == "ntop_messages":
            chat_data = ensure_chat(chat_id)
            lst = sorted(chat_data["messages"].items(), key=lambda x: x[1], reverse=True)
            txt = "💬 <b>توب المتفاعلين:</b>\n\n"
            for i, (uid, cnt) in enumerate(lst[:20]):
                try:
                    mem = bot.get_chat_member(chat_id, int(uid)).user
                    name = human_name(mem)
                except:
                    name = uid
                r = medals[i] if i < 3 else f"{i+1} )"
                txt += f"{r} {name} ← <b>{cnt} رسالة</b>\n"
            if not lst:
                txt += "لا يوجد بيانات بعد."

        elif data == "ntop_mahr":
            # نجمع كل الزيجات من كل القروبات
            all_pairs = []
            for key, val in DB.items():
                if not isinstance(val, dict): continue
                marriages = val.get("marriages", {})
                for husband_str, wives in marriages.items():
                    if not isinstance(wives, list): continue
                    for m in wives:
                        mahr = m.get("mahr", 0)
                        wife_id = m.get("wife")
                        if mahr > 0 and wife_id:
                            all_pairs.append((mahr, int(husband_str), wife_id))
            # نرتب حسب المهر
            all_pairs.sort(key=lambda x: x[0], reverse=True)
            txt = "<b>توب اغنى 10 زوجات بالقروب :</b>\n\n"
            shown = 0
            for mahr, husband_id, wife_id in all_pairs[:10]:
                try:
                    h_info = bot.get_chat(husband_id)
                    h_name = safe_name_for_top(h_info) or human_name(h_info)
                except:
                    h_name = str(husband_id)
                try:
                    w_info = bot.get_chat(wife_id)
                    w_name = safe_name_for_top(w_info) or human_name(w_info)
                except:
                    w_name = str(wife_id)
                r = medals[shown] if shown < 3 else f"{shown+1}"
                txt += f"{r} - {mahr:,} 💵 l <a href='tg://user?id={husband_id}'>{h_name}</a>  👫 <a href='tg://user?id={wife_id}'>{w_name}</a>\n"
                shown += 1
            if shown == 0:
                txt += "💤 لا يوجد زيجات بعد!"
            txt += "\n ━━━━━━━━━"

        elif data == "ntop_gold":
            gold = DB.get("global_golden", {})
            lst = sorted(gold.items(), key=lambda x: x[1], reverse=True)
            if not lst:
                txt = (
                    "🏅 <b>توب تصنيف الذهبي (التصنيف الذهبي)</b>\n\n"
                    "━━━━━━━━━━━━━━━\n"
                    "💤 لا يوجد أصحاب عملات ذهبية بعد!\n\n"
                    "🏆 كيف تحصل على عملات ذهبية؟\n"
                    "• وصّل رصيدك للحد الأقصى\n"
                    "• انتظر 60 ثانية\n"
                    "• رصيدك يتصفر وتحصل <b>50 🥇</b>\n"
                    "━━━━━━━━━━━━━━━"
                )
            else:
                txt = "🏅 <b>توب تصنيف الذهبي</b>\n🌍 من كل القروبات\n\n━━━━━━━━━━━━━━━\n"
                shown = 0
                for uid_str, coins in lst[:20]:
                    try:
                        info = bot.get_chat(int(uid_str))
                        name = safe_name_for_top(info)
                    except:
                        name = None
                    if name is None: continue
                    r = medals[shown] if shown < 3 else f"{shown+1}."
                    txt += f"{r} {name} — <b>{coins} عملة ذهبية 🥇</b>\n"
                    shown += 1
                txt += f"━━━━━━━━━━━━━━━\n👥 المتنافسين: <b>{shown}</b>"

        elif data == "ntop_divorces":
            divs = ensure_global_divorces()
            lst = sorted(divs.items(), key=lambda x: x[1], reverse=True)
            txt = "💔 <b>توب المطلقات</b>\n🌍 من كل القروبات\n\n━━━━━━━━━━━━━━━\n"
            shown = 0
            for uid_str, count in lst:
                try:
                    info = bot.get_chat(int(uid_str))
                    name = safe_name_for_top(info)
                except:
                    name = None
                if name is None: continue
                r = medals[shown] if shown < 3 else f"{shown+1} )"
                txt += f"{r} {name} ← <b>{count} طلاق</b>\n"
                shown += 1
                if shown >= 20: break
            if shown == 0:
                txt += "💤 لا يوجد طلاقات مسجلة بعد!"
            txt += f"\n━━━━━━━━━━━━━━━\n👥 إجمالي المطلقين: <b>{shown}</b>"

        elif data == "ntop_groups":
            groups_data = ensure_group_messages()
            lst = sorted(groups_data.items(), key=lambda x: x[1], reverse=True)
            txt = "<b>توب اكثر 20 قروب يلعبون :</b>\n\n"
            shown = 0
            for cid_str, total_msgs in lst:
                try:
                    info = bot.get_chat(int(cid_str))
                    gname = info.title or cid_str
                except:
                    gname = cid_str
                r = medals[shown] if shown < 3 else f"{shown+1}"
                txt += f"{r} ) {total_msgs:,}   l  {gname}\n"
                shown += 1
                if shown >= 20: break
            if shown == 0:
                txt += "💤 لا يوجد بيانات بعد!"
            txt += "\n ━━━━━━━━━"

        elif data == "ntop_rulers":
            txt = "👑 <b>توب الحكام</b>\n\n━━━━━━━━━━━━━━━\n🔧 هذا التوب قيد التطوير.\n━━━━━━━━━━━━━━━"

        elif data == "ntop_battles":
            txt = "💀 <b>بارزات العالمية</b>\n\n━━━━━━━━━━━━━━━\n🔧 هذا النظام قيد التطوير.\n━━━━━━━━━━━━━━━"

        elif data == "ntop_thieves":
            banking = ensure_banking()
            lst = []
            caller_id = call.from_user.id
            user_entry = None
            for uid_str, udata in banking["users"].items():
                total = udata.get("zarf_total", 0)
                uid_int = int(uid_str)
                try:
                    info = bot.get_chat(uid_int)
                    name = safe_name_for_top(info)
                except:
                    name = None
                if name is None: continue
                if uid_int == caller_id:
                    user_entry = (name, total, uid_int)
                if total > 0:
                    lst.append((name, total, uid_int))
            lst.sort(key=lambda x: x[1], reverse=True)
            txt = "<b>توب اكثر 20 شخص حرامية فلوس:</b>\n\n"
            for i, (name, total, uid_int) in enumerate(lst[:20]):
                r = medals[i] if i < 3 else f"{i+1}"
                txt += f"{r} ) {total:,} 💰 l <a href='tg://user?id={uid_int}'>{name}</a>\n"
            if not lst:
                txt += "💤 لا يوجد بيانات بعد!"
            txt += "\n ━━━━━━━━━\n"
            if user_entry:
                u_name, u_total, u_id = user_entry
                txt += f"• you)  {u_total:,} 💰 l {u_name}"
            else:
                txt += f"• you)  0 💰 l {human_name(call.from_user)}"

        elif data == "ntop_khulaa":
            khulaa = DB.get("global_khulaa", {})
            lst = sorted(khulaa.items(), key=lambda x: x[1], reverse=True)
            txt = "<b>توب اكثر 20 مخلوع بالبوت :</b>\n\n"
            shown = 0
            for uid_str, count in lst[:20]:
                uid_int = int(uid_str)
                try:
                    info = bot.get_chat(uid_int)
                    name = safe_name_for_top(info)
                except:
                    name = None
                if name is None: continue
                r = medals[shown] if shown < 3 else f"{shown+1}"
                txt += f"{r} ) {count} 🙎🏻‍♂ l <a href='tg://user?id={uid_int}'>{name}</a>\n"
                shown += 1
            if shown == 0:
                txt += "💤 لا يوجد خلع مسجل بعد!"
            txt += "\n ━━━━━━━━━"
        else:
            bot.answer_callback_query(call.id)
            return

        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            try:
                bot.send_message(chat_id, txt, reply_markup=back)
            except:
                pass
        try:
            bot.answer_callback_query(call.id)
        except:
            pass
        return

    if data == "close_panel":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            bot.answer_callback_query(call.id, "✅ تم الاغلاق")
        return

    # ===== أزرار الخاص — المستخدم =====
    elif data == "pm_account":
        user_data = get_user_bank_data(user_id)
        if not user_data:
            bot.answer_callback_query(call.id, "⚠️ ما عندك حساب بنكي", show_alert=True)
            return
        try:
            info = bot.get_chat(user_id)
            name = human_name(info)
            uname = f"@{info.username}" if info.username else "بدون يوزر"
            bio = info.bio or "لا يوجد"
        except:
            name = "غير معروف"; uname = "غير معروف"; bio = "لا يوجد"
        card = user_data['bank_card']['card_number']
        txt = (
            f"🏦 <b>معلومات حسابك:</b>\n\n"
            f"• الاسم ↢ {name}\n"
            f"• الحساب ↢ <code>{user_data['account_number']}</code>\n"
            f"• بنك ↢ {user_data['bank_name']}\n"
            f"• نوع ↢ {user_data['bank_card']['type']}\n"
            f"• الرصيد ↢ {user_data['balance']:,} دولار 💸\n"
            f"• البطاقة ↢ <code>{card}</code>\n"
            f"• اليوزر ↢ {uname}\n"
            f"• الزرف ↢ {user_data.get('zarf_count',0)} مرة"
        )
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            bot.send_message(chat_id, txt, reply_markup=back)

    elif data == "pm_balance":
        user_data = get_user_bank_data(user_id)
        if not user_data:
            bot.answer_callback_query(call.id, "⚠️ ما عندك حساب بنكي", show_alert=True)
            return
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        try:
            bot.edit_message_text(
                f"💰 <b>رصيدك:</b> {user_data['balance']:,} دولار 💸\n"
                f"🏦 البنك: {user_data['bank_name']}",
                chat_id, call.message.message_id, reply_markup=back
            )
        except:
            pass

    elif data == "pm_top":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💰 توب الفلوس", callback_data="ntop_money"),
            types.InlineKeyboardButton("🥇 توب التصنيف الذهبي", callback_data="ntop_gold"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"),
        )
        try:
            bot.edit_message_text("📊 <b>اختر التوب:</b>", chat_id, call.message.message_id, reply_markup=markup)
        except:
            pass

    elif data == "pm_wives":
        marriage_system = ensure_marriage_system()
        marriages = marriage_system["marriages"].get(str(user_id), [])
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        if not marriages:
            txt = "💍 ما عندك زوجات بعد."
        else:
            txt = "💍 <b>زوجاتك:</b>\n\n"
            for i, m in enumerate(marriages, 1):
                try:
                    w = bot.get_chat(m["wife"])
                    wname = human_name(w)
                except:
                    wname = str(m["wife"])
                txt += f"{i}. {wname} — مهر: {m['mahr']:,} دولار\n"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            pass

    elif data == "pm_store":
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        cats = {}
        for item, info in list(ITEMS.items())[:15]:
            c = info["category"]
            if c not in cats:
                cats[c] = []
            cats[c].append(f"{info['emoji']} {item}: {info['price']:,}")
        txt = "🛒 <b>المتجر:</b>\n\n"
        for cat, items in cats.items():
            txt += f"<b>{cat}</b>\n" + "\n".join(items) + "\n\n"
        txt += "للشراء: <code>شراء 1 [اسم العنصر]</code>"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            pass

    elif data == "pm_help":
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        txt = (
            "📜 <b>الأوامر الرئيسية:</b>\n\n"
            "<b>💰 البنك:</b>\n"
            "• انشاء حساب بنكي\n• حسابي • رصيدي • راتب\n"
            "• حظ فلوسي | حظ [مبلغ]\n"
            "• استثمار كل فلوسي | استثمار [مبلغ]\n"
            "• تحويل [مبلغ]\n• مسح حسابي\n\n"
            "<b>🎮 الألعاب:</b>\n"
            "• انق — لعبة ترجمة\n• احكام — لعبة جماعية\n"
            "• زرف @يوزر — سرقة\n"
            "• 🧙 السحرة، 🏰 عرش المملكة، 🐺 المافيا — من زر «الألعاب» بالخاص\n\n"
            "<b>💍 الزواج:</b>\n"
            "• زواج [مبلغ] — رد على رسالة\n• زوجتي • طلاق\n\n"
            "<b>🏆 التوب:</b>\n"
            "• توب — كل التوبات\n\n"
            "<b>⚙️ الادارة (في القروب):</b>\n"
            "• تعليمات — قائمة كاملة"
        )
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            pass

    elif data == "pm_back":
        user_data = get_user_bank_data(user_id)
        balance_line = f"💰 رصيدك: <b>{user_data['balance']:,} دولار</b>" if user_data else "🏦 ما عندك حساب — اكتب <code>انشاء حساب بنكي</code>"
        name = human_name(call.from_user)
        back_txt = (
            f"✨ <b>أهلاً {name}!</b>\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🤖 أنا <b>ايتو</b> — بوت إدارة وألعاب\n"
            f"{balance_line}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"اختر من القائمة:"
        )
        edited = False
        try:
            bot.edit_message_text(back_txt, chat_id, call.message.message_id, reply_markup=create_user_keyboard())
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(back_txt, chat_id, call.message.message_id, reply_markup=create_user_keyboard())
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(chat_id, back_txt, reply_markup=create_user_keyboard())
            except Exception:
                pass
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    elif data in ("user_games_menu", "user_games_menu_home"):
        back_target = "go_home" if data == "user_games_menu_home" else "pm_back"
        m = types.InlineKeyboardMarkup(row_width=1)
        m.add(types.InlineKeyboardButton("🧙 لعبة السحرة", callback_data="wz_menu", style="success"))
        m.add(types.InlineKeyboardButton("🏰 عرش المملكة", callback_data="thr_menu", style="danger"))
        m.add(types.InlineKeyboardButton("🐺 لعبة المافيا", callback_data="mf_menu", style="primary"))
        m.add(types.InlineKeyboardButton("🎌 أنمي", callback_data="picture_anime_help", style="primary"))
        m.add(types.InlineKeyboardButton("⚽ لاعبين", callback_data="picture_players_help", style="primary"))
        m.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target))
        games_txt = "🎮 <b>الألعاب:</b>\n\nاختر اللعبة اللي تبي تسويها:"
        edited = False
        try:
            bot.edit_message_text(games_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=m)
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(games_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=m)
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(chat_id, games_txt, parse_mode="HTML", reply_markup=m)
            except Exception:
                pass
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    elif data == "go_home":
        dev_id = BOT_OWNER_ID
        dev_username = None
        try:
            dev_info = bot.get_chat(dev_id)
            dev_name = human_name(dev_info)
            dev_username = dev_info.username
        except:
            dev_name = "المطور"
        if dev_username:
            dev_link = f'<a href="https://t.me/{dev_username}">{dev_name}</a>'
        else:
            dev_link = f'<a href="tg://user?id={dev_id}">{dev_name}</a>'

        home_txt = (
            f"أهلاً بك عزيزي انا بوت اسمي ايتو\n"
            f"اختصاص البوت حماية المجموعات\n"
            f"اضف البوت الى مجموعتك .\n"
            f"ارفعه ادمن مشرف\n"
            f"ارفعه مشرف وارسل تفعيل ليتم تفعيل المجموعة .\n"
            f"مطور البوت ← {dev_link}"
        )

        home_markup = types.InlineKeyboardMarkup(row_width=1)
        home_markup.add(types.InlineKeyboardButton(
            "➕ اضفني لمجموعتك", url="https://t.me/ri5xbot?startgroup=true", style="success"
        ))
        home_markup.add(types.InlineKeyboardButton(
            "🎮 الألعاب", callback_data="user_games_menu_home", style="success"
        ))
        home_markup.add(types.InlineKeyboardButton(
            f"{dev_name}", url=f"tg://user?id={dev_id}", style="primary"
        ))
        try:
            channel_info = bot.get_chat("@R_5_XT")
            channel_name = channel_info.title or "القناة"
        except:
            channel_name = "القناة"
        home_markup.add(types.InlineKeyboardButton(
            f"{channel_name}", url="https://t.me/R_5_XT", style="primary"
        ))

        edited = False
        try:
            bot.edit_message_text(home_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=home_markup)
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(home_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=home_markup)
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(chat_id, home_txt, parse_mode="HTML", reply_markup=home_markup)
            except Exception:
                pass
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    elif data == "dev_games_menu" and has_bot_permission(user_id, "dev_games_menu"):
        m = types.InlineKeyboardMarkup(row_width=1)
        m.add(types.InlineKeyboardButton("🧙 لعبة السحرة", callback_data="wz_menu", style="success"))
        m.add(types.InlineKeyboardButton("🏰 عرش المملكة", callback_data="thr_menu", style="success"))
        m.add(types.InlineKeyboardButton("🐺 لعبة المافيا", callback_data="mf_menu", style="success"))
        m.add(types.InlineKeyboardButton("🎌 أنمي", callback_data="picture_anime_help", style="success"))
        m.add(types.InlineKeyboardButton("⚽ لاعبين", callback_data="picture_players_help", style="success"))
        m.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        games_txt = "🎮 <b>الألعاب:</b>\n\nاختر اللعبة اللي تبي تسويها:"
        edited = False
        try:
            bot.edit_message_text(games_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=m)
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(games_txt, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=m)
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(chat_id, games_txt, parse_mode="HTML", reply_markup=m)
            except Exception:
                pass
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    elif data in ("picture_anime_help", "picture_players_help"):
        title = "🎌 أنمي" if data == "picture_anime_help" else "⚽ لاعبين"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"{title}\n\nاكتب الأمر في القروب لبدء اللعبة.\n" + ("أنمي" if data == "picture_anime_help" else "لاعبين"))

    # ===== أزرار الخاص — المطور =====
    elif data == "bot_stats" and has_bot_permission(user_id, "bot_stats"):
        banking = ensure_banking()
        total_groups = sum(1 for cid in DB.keys() if cid.isdigit())
        total_users = len(banking["users"])
        total_wealth = sum(ud.get("balance",0) for ud in banking["users"].values())
        gold = ensure_gold_ranking()
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        try:
            bot.edit_message_text(
                f"📊 <b>إحصائيات البوت:</b>\n\n"
                f"• المستخدمين: <b>{total_users}</b>\n"
                f"• القروبات: <b>{total_groups}</b>\n"
                f"• إجمالي الفلوس: <b>{total_wealth:,} دولار</b>\n"
                f"• أصحاب عملات ذهبية: <b>{len(gold)}</b>",
                chat_id, call.message.message_id, reply_markup=back
            )
        except:
            pass

    elif data == "bot_groups" and has_bot_permission(user_id, "bot_groups"):
        send_groups_page(chat_id, call.message.message_id, page=0, edit=True)

    elif data == "bot_gold" and has_bot_permission(user_id, "bot_gold"):
        gold = ensure_gold_ranking()
        lst = sorted(gold.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇","🥈","🥉"]
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        txt = "🥇 <b>التصنيف الذهبي:</b>\n\n"
        for i, (uid_str, coins) in enumerate(lst[:30]):
            try:
                info = bot.get_chat(int(uid_str))
                name = human_name(info)
            except:
                name = uid_str
            r = medals[i] if i < 3 else f"{i+1}."
            txt += f"{r} {name} ← <b>{coins} 🥇</b>\n"
        if not gold:
            txt += "لا يوجد بيانات بعد."
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
        except:
            pass

    elif data == "bot_reset_all" and has_bot_permission(user_id, "bot_reset_all"):
        back = types.InlineKeyboardMarkup(row_width=2)
        back.add(
            types.InlineKeyboardButton("✅ تأكيد التصفير", callback_data="bot_reset_confirm"),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="owner_back"),
        )
        try:
            bot.edit_message_text(
                "⚠️ <b>تأكيد تصفير كل شيء؟</b>\n\n"
                "سيتم تصفير:\n"
                "• كل الفلوس (الأرصدة البنكية)\n"
                "• توب المتفاعلين (الرسائل)\n"
                "• توب الحراميه (سجل الزرف)\n"
                "• توب المطلقات/المخلوعين\n"
                "• توب المتزوجين (المهور)\n\n"
                "🥇 <b>التصنيف الذهبي لن يتأثر</b>\n\n"
                "هذا الاجراء لا يمكن التراجع عنه!",
                chat_id, call.message.message_id, reply_markup=back, parse_mode="HTML")
        except:
            pass

    elif data == "bot_reset_confirm" and has_bot_permission(user_id, "bot_reset_all"):
        banking = ensure_banking()
        # تصفير الفلوس + توب الحراميه (zarf_total)
        for uid_str in list(banking["users"].keys()):
            banking["users"][uid_str]["balance"]    = 0
            banking["users"][uid_str]["zarf_total"] = 0
        # تصفير سجل الزرف
        banking["zarf_history"] = {}
        # تصفير توب المطلقات
        DB["global_divorces"] = {}
        # تصفير توب المخلوعين
        DB["global_khulaa"] = {}
        # تصفير الزواج الفعلي (نظام الزواج العام) + توب المهور
        # حتى المتزوجين ينمسحون من الزواج فعلياً ويرجعون يتزوجون من جديد
        marriage_system = ensure_marriage_system()
        marriage_system["marriages"] = {}
        marriage_system["divorced"]  = {}
        marriage_system["khul"]      = {}
        banking["marriage_top"] = {}
        # تصفير الرسائل والزيجات بكل قروب فقط (وليس كل مفاتيح DB!)
        # ملاحظة مهمة: قبل هذا التعديل كان اللوب يمر على كل مفتاح بـ DB
        # (حتى المفاتيح العامة زي global_divorces / global_khulaa / banking / gold_ranking)
        # ويحقن فيها messages/marriages/divorces، فتفسد هالقواميس العامة
        # ولاحقاً أي فرز (sorted) على قيمها يطيح بخطأ TypeError ويعلّق الزر
        # لأن الرد ما يوصل لتلجرام (answer_callback_query ما ينفذ).
        for cid in list(DB.keys()):
            if cid.startswith("-") and isinstance(DB[cid], dict):
                DB[cid]["messages"]  = {}
                DB[cid]["marriages"] = {}
                DB[cid]["divorces"]  = {}
        save_db()
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        try:
            bot.edit_message_text(
                "✅ <b>تم تصفير كل شيء بنجاح!</b>\n\n"
                "• الفلوس ✅\n"
                "• توب الحراميه ✅\n"
                "• توب المطلقات ✅\n"
                "• توب المخلوعين ✅\n"
                "• توب المتفاعلين ✅\n"
                "• توب المتزوجين ✅\n\n"
                "🥇 التصنيف الذهبي محفوظ.",
                chat_id, call.message.message_id, reply_markup=back, parse_mode="HTML")
        except:
            pass

    # ========= تصفير التصنيف الذهبي (منفصل) =========
    elif data == "bot_reset_gold" and has_bot_permission(user_id, "bot_reset_gold"):
        back = types.InlineKeyboardMarkup(row_width=2)
        back.add(
            types.InlineKeyboardButton("✅ تأكيد", callback_data="bot_reset_gold_confirm"),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="owner_back"),
        )
        try:
            bot.edit_message_text(
                "⚠️ <b>تأكيد تصفير التصنيف الذهبي؟</b>\n\nسيتم حذف كل النقاط الذهبية لجميع المستخدمين.\nهذا الاجراء لا يمكن التراجع عنه!",
                chat_id, call.message.message_id, reply_markup=back, parse_mode="HTML")
        except: pass

    elif data == "bot_reset_gold_confirm" and has_bot_permission(user_id, "bot_reset_gold"):
        # تصفير نقاط الذهبي الحقيقية
        DB["global_golden"] = {}
        DB["gold_ranking"]  = {}
        # تصفير نقاط الذهبي داخل banking["users"] إن وجدت
        banking_g = ensure_banking()
        for uid_str in list(banking_g["users"].keys()):
            banking_g["users"][uid_str]["golden_coins"] = 0
        save_db()
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        try:
            bot.edit_message_text("✅ تم تصفير التصنيف الذهبي بنجاح.", chat_id, call.message.message_id, reply_markup=back, parse_mode="HTML")
        except: pass

    elif data == "bot_ban_game" and has_bot_permission(user_id, "bot_ban_game"):
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="owner_back"))
        try:
            bot.edit_message_text(
                "🚫 <b>حظر من اللعبة:</b>\n\nأرسل: <code>حظر لعبة [ID]</code>",
                chat_id, call.message.message_id, reply_markup=back
            )
        except:
            pass

    elif data == "owner_back" and user_id != BOT_OWNER_ID and is_bot_admin(user_id):
        # رجوع أدمن البوت إلى لوحة الأدمن، وليس لوحة المطور.
        try:
            bot.edit_message_text(admin_panel_text(user_id)[0], chat_id, call.message.message_id, reply_markup=admin_panel_text(user_id)[1], parse_mode="HTML")
        except Exception:
            try:
                bot.send_message(chat_id, admin_panel_text(user_id)[0], reply_markup=admin_panel_text(user_id)[1], parse_mode="HTML")
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return

    elif data == "owner_back" and user_id == BOT_OWNER_ID:
        banking = ensure_banking()
        total_users = len(banking["users"])
        total_groups = sum(1 for cid in DB.keys() if cid.isdigit())
        total_wealth = sum(ud.get("balance",0) for ud in banking["users"].values())
        back_txt = (
            f"👑 <b>أهلاً يا مطور ايتو!</b>\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 <b>إحصائيات سريعة:</b>\n"
            f"• المستخدمين: <b>{total_users}</b>\n"
            f"• القروبات: <b>{total_groups}</b>\n"
            f"• إجمالي الفلوس: <b>{total_wealth:,} دولار</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛠️ اختر من لوحة التحكم:"
        )
        edited = False
        try:
            bot.edit_message_text(back_txt, chat_id, call.message.message_id, reply_markup=create_owner_keyboard())
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(back_txt, chat_id, call.message.message_id, reply_markup=create_owner_keyboard())
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(chat_id, back_txt, reply_markup=create_owner_keyboard())
            except Exception:
                pass
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    # ===== قديم للتوافق =====
    elif data == "my_money":
        user_data = get_user_bank_data(user_id)
        if not user_data:
            bot.answer_callback_query(call.id, "⚠️ ليس لديك حساب بنكي", show_alert=True)
            return
        back = types.InlineKeyboardMarkup()
        back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="pm_back"))
        try:
            bot.edit_message_text(f"💰 رصيدك: <b>{user_data['balance']:,} دولار</b>", chat_id, call.message.message_id, reply_markup=back)
        except:
            pass

    # ========= لوحة الادارة =========
    elif data.startswith("admpanel_"):
        parts  = data.split("_")
        action = parts[1]
        adm_chat_id = int(parts[2])
        role = get_role(adm_chat_id, user_id)
        if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
            bot.answer_callback_query(call.id, "⛔ الصلاحية للإداريين فقط.", show_alert=True)
            return
        chat_data = ensure_chat(adm_chat_id)
        back_btn  = types.InlineKeyboardMarkup()
        back_btn.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"admpanel_back_{adm_chat_id}"))

        def adm_edit(txt):
            try:
                bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back_btn, parse_mode="HTML")
            except: pass

        if action == "back":
            try: gname = bot.get_chat(adm_chat_id).title or "القروب"
            except: gname = "القروب"
            t = (f"⚙️ <b>لوحة إدارة : {gname}</b>\n\n"
                 f"• إجمالي الرسائل : <b>{sum(chat_data.get('messages',{}).values()):,}</b>\n"
                 f"• إنذارات نشطة  : <b>{sum(1 for w in chat_data.get('warnings',{}).values() if w > 0)}</b>\n"
                 f"• محظورون       : <b>{sum(1 for r in chat_data.get('restrictions',{}).values() if r.get('banned'))}</b>\n\n"
                 f"اختر من الأزرار أدناه 👇")
            try:
                bot.edit_message_text(t, chat_id, call.message.message_id,
                                      reply_markup=build_admin_panel_markup(adm_chat_id), parse_mode="HTML")
            except: pass

        elif action == "admins":
            ROLE_EMOJI = {"مالك اساسي":"👑","مساعد مالك":"🔰","مالك":"🏅","منشئ":"⭐","مدير":"🛡️","ادمن":"🔷"}
            ORDER = ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن"]
            t = "👮 <b>الاداريون:</b>\n\n"
            found = False
            for r in ORDER:
                members = chat_data["roles"].get(r, [])
                if r == "مالك اساسي" and chat_data.get("main_owner"):
                    members = [chat_data["main_owner"]]
                for uid in members:
                    try:
                        mem = bot.get_chat_member(adm_chat_id, uid).user
                        link = f'<a href="tg://user?id={uid}">{human_name(mem)}</a>'
                    except:
                        link = f'<a href="tg://user?id={uid}">{uid}</a>'
                    t += f"{ROLE_EMOJI.get(r,'•')} {link} — <b>{r}</b>\n"
                    found = True
            if not found: t += "لا يوجد إداريون."
            adm_edit(t)

        elif action == "banned":
            banned = [(u,d) for u,d in chat_data.get("restrictions",{}).items() if d.get("banned")]
            t = f"⛔ <b>المحظورون ({len(banned)}):</b>\n\n"
            if not banned: t += "لا يوجد أحد محظور. ✅"
            else:
                for uid_str,_ in banned[:20]:
                    try:
                        info = bot.get_chat(int(uid_str))
                        link = f'<a href="tg://user?id={uid_str}">{human_name(info)}</a>'
                    except:
                        link = f'<a href="tg://user?id={uid_str}">{uid_str}</a>'
                    t += f"• {link}\n"
            adm_edit(t)

        elif action == "warns":
            wl = [(u,w) for u,w in chat_data.get("warnings",{}).items() if w > 0]
            wl.sort(key=lambda x: x[1], reverse=True)
            t = f"⚠️ <b>الانذارات النشطة ({len(wl)}):</b>\n\n"
            if not wl: t += "لا توجد إنذارات. ✅"
            else:
                for uid_str, count in wl[:20]:
                    try:
                        mem = bot.get_chat_member(adm_chat_id, int(uid_str)).user
                        link = f'<a href="tg://user?id={uid_str}">{human_name(mem)}</a>'
                    except:
                        link = f'<a href="tg://user?id={uid_str}">{uid_str}</a>'
                    t += f"• {link} — {'🔴'*count}{'⚪'*(5-count)} ({count}/5)\n"
            adm_edit(t)

        elif action == "new":
            nm = chat_data.get("new_members", [])
            t = f"🆕 <b>آخر الأعضاء ({len(nm)}):</b>\n\n"
            if not nm: t += "لا توجد بيانات."
            else:
                for i, md in enumerate(reversed(nm[-10:]), 1):
                    link = f'<a href="tg://user?id={md["id"]}">{md["name"]}</a>'
                    t += f"{i}. {link} — {md.get('time','')}\n"
            adm_edit(t)

        elif action == "stats":
            msgs  = chat_data.get("messages", {})
            warns = chat_data.get("warnings", {})
            rest  = chat_data.get("restrictions", {})
            roles = chat_data.get("roles", {})
            top_user = ""
            if msgs:
                top_uid = max(msgs, key=msgs.get)
                try:
                    tm = bot.get_chat_member(adm_chat_id, int(top_uid)).user
                    top_user = f'<a href="tg://user?id={top_uid}">{human_name(tm)}</a> ({msgs[top_uid]:,})'
                except: top_user = str(top_uid)
            t = (f"📊 <b>إحصائيات القروب:</b>\n\n"
                 f"👥 النشطون : <b>{len([v for v in msgs.values() if v>0])}</b>\n"
                 f"💬 الرسائل : <b>{sum(msgs.values()):,}</b>\n"
                 f"👮 الاداريون : <b>{sum(len(roles.get(r,[])) for r in ['ادمن','مدير','منشئ','مالك','مالك اساسي','مساعد مالك'])}</b>\n"
                 f"⛔ المحظورون : <b>{sum(1 for r in rest.values() if r.get('banned'))}</b>\n"
                 f"🔇 المكتومون : <b>{sum(1 for r in rest.values() if r.get('muted'))}</b>\n"
                 f"⚠️ الانذارات : <b>{sum(1 for w in warns.values() if w>0)}</b>\n"
                 f"🆕 الجدد : <b>{len(chat_data.get('new_members',[]))}</b>\n")
            if top_user: t += f"\n🏆 الأكثر تفاعلاً : {top_user}"
            adm_edit(t)

        elif action == "log":
            log = ensure_event_log(adm_chat_id)
            if not log: t = "📜 <b>سجل الأحداث</b>\n\nلا توجد أحداث بعد."
            else:
                t = "📜 <b>سجل الأحداث — آخر 15:</b>\n\n"
                for ev in reversed(log[-15:]): t += f"• {ev}\n"
            adm_edit(t)

        elif action == "shortcuts":
            sc_mk = types.InlineKeyboardMarkup(row_width=1)
            sc_mk.add(types.InlineKeyboardButton("➕ اضف اختصار",  callback_data=f"scpanel_add_{adm_chat_id}"))
            sc_mk.add(types.InlineKeyboardButton("📋 عرض الاختصارات", callback_data=f"scpanel_list_{adm_chat_id}"))
            sc_mk.add(types.InlineKeyboardButton("🗑 مسح اختصار",  callback_data=f"scpanel_del_{adm_chat_id}"))
            sc_mk.add(types.InlineKeyboardButton("🔙 رجوع",         callback_data=f"admpanel_back_{adm_chat_id}"))
            try:
                bot.edit_message_text(
                    "⚡ <b>نظام الاختصارات</b>\n\nاختر العملية:",
                    chat_id, call.message.message_id,
                    parse_mode="HTML", reply_markup=sc_mk)
            except: pass
            bot.answer_callback_query(call.id)
            return

        elif action == "games":
            chat_g  = ensure_games_settings(adm_chat_id)
            enabled = chat_g.get("games_enabled", True)
            status  = "✅ مشغلة" if enabled else "❌ مطفأة"
            games_mk = types.InlineKeyboardMarkup(row_width=1)
            games_mk.add(types.InlineKeyboardButton("✅ تشغيل الألعاب", callback_data=f"games_on_{adm_chat_id}"))
            games_mk.add(types.InlineKeyboardButton("❌ إطفاء الألعاب", callback_data=f"games_off_{adm_chat_id}"))
            games_mk.add(types.InlineKeyboardButton("🔙 رجوع",          callback_data=f"admpanel_back_{adm_chat_id}"))
            try:
                bot.edit_message_text(
                    f"🎮 <b>إعدادات الألعاب</b>\n\nالحالة: <b>{status}</b>\n\nالألعاب: كت، انق، حظ فلوسي",
                    chat_id, call.message.message_id, parse_mode="HTML", reply_markup=games_mk)
            except: pass
            bot.answer_callback_query(call.id)
            return

    # ========= صورة المطور =========
    elif data.startswith("show_dev_photo_"):
        dev_id_str = data.replace("show_dev_photo_", "")
        file_id = DB.get("dev_photo_cache", {}).get(dev_id_str)
        if not file_id:
            bot.answer_callback_query(call.id, "⚠️ الصورة غير متوفرة", show_alert=True)
            return
        try:
            dev_id   = int(dev_id_str)
            dev_info = bot.get_chat(dev_id)
            dev_name = human_name(dev_info)
            dev_bio  = dev_info.bio or "لا يوجد وصف"
            dev_user = dev_info.username
            dev_link = f'<a href="tg://user?id={dev_id}">@{dev_user}</a>' if dev_user else f'<a href="tg://user?id={dev_id}">{dev_name}</a>'
            caption  = (f"👨‍💻 <b>مطور البوت</b>\n\n"
                        f"• الاسم : <b>{dev_name}</b>\n"
                        f"• الحساب : {dev_link}\n"
                        f"• الوصف : {dev_bio}")
            bot.send_photo(chat_id, file_id, caption=caption, parse_mode="HTML",
                           reply_to_message_id=call.message.message_id)
        except: pass

    # ========= فهمت (تحذير عام) =========
    elif data == "warn_understood":
        bot.answer_callback_query(call.id, f"✅ تمام يا {human_name(call.from_user)}!", show_alert=False)
        return

    # ========= نظام الاختصارات (لوحة) =========
    elif data.startswith("scpanel_"):
        parts2 = data.split("_")
        act2   = parts2[1]
        cid2   = int(parts2[2])
        role   = get_role(cid2, user_id)
        if role not in SHORTCUT_ALLOWED:
            bot.answer_callback_query(call.id, "⛔ مخصص لرتبة مالك وفوق.", show_alert=True)
            return

        if act2 == "add":
            key = f"{cid2}_{user_id}"
            shortcut_steps[key] = {"step": "waiting_shortcut_word", "chat_id": cid2}
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, "✏️ اكتب الاختصار الذي تريده\nمثال: <code>اد</code>", parse_mode="HTML")
            return

        elif act2 == "list":
            shortcuts = ensure_shortcuts(cid2)
            if not shortcuts:
                bot.answer_callback_query(call.id, "لا يوجد اختصارات بعد.", show_alert=True)
                return
            txt2 = "📋 <b>الاختصارات الموجودة:</b>\n\n"
            for sh, orig in shortcuts.items():
                txt2 += f"• <code>{sh}</code> ← <b>{orig}</b>\n"
            mk2 = types.InlineKeyboardMarkup()
            mk2.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"scpanel_back_{cid2}"))
            try:
                bot.edit_message_text(txt2, chat_id, call.message.message_id, reply_markup=mk2, parse_mode="HTML")
            except: pass
            bot.answer_callback_query(call.id)
            return

        elif act2 == "del":
            shortcuts_check = ensure_shortcuts(cid2)
            if not shortcuts_check:
                bot.answer_callback_query(call.id, "لا توجد اختصارات للمسح.", show_alert=True)
                return
            key = f"{cid2}_{user_id}"
            shortcut_delete_steps[key] = {"step": "waiting_shortcut_name", "chat_id": cid2}
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, "🗑 اكتب الاختصار الذي تريد مسحه\nمثال: <code>اد</code>", parse_mode="HTML")
            return

        elif act2 == "back":
            try:
                bot.edit_message_text("⚙️ <b>نظام الاختصارات</b>\n\nاختر من الأزرار:",
                                      chat_id, call.message.message_id,
                                      reply_markup=build_shortcut_panel(cid2), parse_mode="HTML")
            except: pass
            bot.answer_callback_query(call.id)
            return

    # ========= تشغيل/إطفاء الألعاب =========
    elif data.startswith("games_on_") or data.startswith("games_off_"):
        parts3  = data.split("_")
        action3 = parts3[1]
        cid3    = int(parts3[2])
        role    = get_role(cid3, user_id)
        if role not in ["مدير","منشئ","مالك","مساعد مالك","مالك اساسي"]:
            bot.answer_callback_query(call.id, "⛔ للمدير وما فوقه.", show_alert=True)
            return
        chat3 = ensure_games_settings(cid3)
        if action3 == "on":
            chat3["games_enabled"] = True
            save_db()
            add_event(cid3, f"🎮 تشغيل الألعاب — {human_name(call.from_user)}")
            status3 = "✅ مشغلة"
            bot.answer_callback_query(call.id, "✅ تم تشغيل الألعاب!")
        else:
            chat3["games_enabled"] = False
            save_db()
            add_event(cid3, f"🎮 إطفاء الألعاب — {human_name(call.from_user)}")
            status3 = "❌ مطفأة"
            bot.answer_callback_query(call.id, "❌ تم إطفاء الألعاب!")
        games_mk3 = types.InlineKeyboardMarkup(row_width=1)
        games_mk3.add(types.InlineKeyboardButton("✅ تشغيل الألعاب", callback_data=f"games_on_{cid3}"))
        games_mk3.add(types.InlineKeyboardButton("❌ إطفاء الألعاب", callback_data=f"games_off_{cid3}"))
        games_mk3.add(types.InlineKeyboardButton("🔙 رجوع",          callback_data=f"admpanel_back_{cid3}"))
        try:
            bot.edit_message_text(
                f"🎮 <b>إعدادات الألعاب</b>\n\nالحالة: <b>{status3}</b>\n\nالألعاب: كت، انق، حظ فلوسي",
                chat_id, call.message.message_id, parse_mode="HTML", reply_markup=games_mk3)
        except: pass
        return

    bot.answer_callback_query(call.id)

# ========= توب — handler مستقل يشتغل دايماً =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب" and m.chat.type in ["group","supergroup"])
def top_menu_handler(message):
    bot.reply_to(message, "📊 <b>اختر التوب:</b>", reply_markup=build_top_markup())

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب التصنيف الذهبي" and m.chat.type in ["group","supergroup"])
def gold_top_text_handler(message):
    gold = ensure_gold_ranking()
    lst = sorted(gold.items(), key=lambda x: x[1], reverse=True)
    back = types.InlineKeyboardMarkup()
    back.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="ntop_gold"))
    if not lst:
        txt = (
            "🥇 <b>توب التصنيف الذهبي</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💤 لا يوجد أصحاب عملات ذهبية بعد!\n\n"
            "🏆 كيف تحصل على عملات ذهبية؟\n"
            "• وصّل رصيدك للحد الأقصى\n"
            "• انتظر 60 ثانية\n"
            "• رصيدك يتصفر وتحصل <b>50 🥇</b>\n"
            "━━━━━━━━━━━━━━━"
        )
    else:
        txt = "🏆 <b>توب التصنيف الذهبي</b>\n🌍 من كل القروبات\n\n━━━━━━━━━━━━━━━\n"
        for i, (uid_str, coins) in enumerate(lst[:30]):
            try:
                info = bot.get_chat(int(uid_str))
                name = human_name(info)
            except:
                name = uid_str
            if i == 0: r = "🥇 1"
            elif i == 1: r = "🥈 2"
            elif i == 2: r = "🥉 3"
            else: r = f"   {i+1}"
            txt += f"{r} ) {name} — <b>{coins} نقطة 🥇</b>\n"
        txt += f"━━━━━━━━━━━━━━━\n👥 المتنافسين: <b>{len(lst)}</b>"
    bot.reply_to(message, txt, reply_markup=back)

# ========= الأوامر النصية الرئيسية =========
@bot.message_handler(content_types=["text"])
def main_handler(message):
    # V22 commands must be dispatched here because this catch-all text handler
    # is registered before the V22 handlers. pyTelegramBotAPI tests handlers
    # in declaration order, so otherwise later V22 handlers never receive text.
    text = (message.text or "").strip()
    if text:
        v22_route = None
        if text.startswith("ضبط الانذارات"):
            v22_route = v22_warning_settings
        elif text == "اعدادات الانذارات":
            v22_route = v22_warning_show
        elif text.startswith("قفل "):
            v22_route = v22_lock
        elif text.startswith("فتح "):
            v22_route = v22_unlock
        elif text == "اقفال المجموعة":
            v22_route = v22_lock_list
        elif text == "سجل التدقيق":
            v22_route = v22_audit_show
        elif text == "السوق":
            v22_route = v22_market
        elif text.startswith("شراء نادر "):
            v22_route = v22_market_buy
        elif text.startswith("وظيفة"):
            v22_route = v22_job
        elif text == "قبض الراتب":
            v22_route = v22_job_salary
        elif text.startswith("قرض "):
            v22_route = v22_loan
        elif text == "سداد القرض":
            v22_route = v22_loan_pay
        elif text == "قرضي":
            v22_route = v22_loan_info
        elif text.startswith("تطوير عقار "):
            v22_route = v22_property_upgrade
        elif text.startswith("تأجير عقار "):
            v22_route = v22_property_rent
        elif text == "عقاراتي":
            v22_route = v22_properties
        elif text.startswith("استثمار طويل "):
            v22_route = v22_long_invest
        elif text == "حصاد الاستثمار":
            v22_route = v22_long_invest_claim
        elif text.startswith("تحويل مؤكد "):
            v22_route = v22_transfer
        elif text in ["ملفي", "بروفايلي", "انجازاتي", "إنجازاتي"]:
            v22_route = v22_profile
        elif text.startswith("مبارزة"):
            v22_route = v22_battle_start
        elif text.startswith("مزاد "):
            v22_route = v22_auction
        elif text == "سرقة البنك":
            v22_route = v22_robbery
        elif text == "حدث عشوائي":
            v22_route = v22_random_event_cmd
        elif text.startswith("تلخيص المجموعة"):
            v22_route = v22_ai_summary
        elif text == "مراقبة AI":
            v22_route = v22_ai_mod_toggle
        elif text == "توب شامل":
            v22_route = v22_top
        if v22_route is not None:
            try:
                return v22_route(message)
            except Exception as e:
                print(f"[V22 route error] {text}: {e}")
                try:
                    bot.reply_to(message, "⚠️ صار خطأ داخل الأمر. راجع سجل التشغيل.")
                except Exception:
                    pass
            return

    if not is_group(message):
        return
    
    update_known_user(message)
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id
    actor_role = get_role(chat_id, user_id)
    chat = ensure_chat(chat_id)
    # text was normalized above

    # ========= فحص حظر القروب — المطور فقط يتجاوزه =========
    if chat.get("bot_banned", False) and user_id != BOT_OWNER_ID:
        return

    # ========= فحص وضع الصيانة — المطور فقط يتجاوزه =========
    if is_maintenance_on() and user_id != BOT_OWNER_ID:
        return

    chat["messages"][str(user_id)] = chat["messages"].get(str(user_id),0)+1
    save_db()

    user_key = f"{chat_id}_{user_id}"

    # ========= فحص الاختصارات — قبل أي شي =========
    if user_key not in shortcut_steps and user_key not in shortcut_delete_steps:
        shortcuts_db = ensure_shortcuts(chat_id)
        if text in shortcuts_db:
            original_cmd = shortcuts_db[text]
            message.text = original_cmd
            text         = original_cmd
            # نكمل بالكود بعدين بالأمر الأصلي بدل الاختصار

    # ========= فحص جلسة الاختصار =========

    # ========= أمر: سحب الرتبة (للمطور فقط) =========
    if text == "سحب الرتبة" and user_id == BOT_OWNER_ID:
        current_owner = chat.get("main_owner")
        if not current_owner:
            bot.reply_to(message, "⚠️ لا يوجد مالك أساسي مسجل بهذا القروب.")
            return
        if current_owner == BOT_OWNER_ID:
            bot.reply_to(message, "✅ أنت بالفعل المالك الأساسي لهذا القروب.")
            return

        # إزالة المالك القديم من كل الرتب
        old_owner_id = current_owner
        for r in ["مالك","منشئ","مدير","ادمن","مميز","مساعد مالك"]:
            if old_owner_id in chat["roles"].get(r, []):
                chat["roles"][r].remove(old_owner_id)

        # تعيين المطور كمالك أساسي جديد
        chat["main_owner"] = BOT_OWNER_ID
        save_db()

        try:
            old_owner_info = bot.get_chat(old_owner_id)
            old_owner_name = human_name(old_owner_info)
            old_link = f'<a href="tg://user?id={old_owner_id}">{old_owner_name}</a>'
        except:
            old_link = str(old_owner_id)

        dev_name = human_name(user)
        dev_link = f'<a href="tg://user?id={user_id}">{dev_name}</a>'

        add_event(chat_id, f"👑 سحب رتبة المالك الأساسي من {old_link} إلى المطور {dev_link}")

        bot.reply_to(message,
            f"👑 <b>تم سحب الرتبة بنجاح!</b>\n\n"
            f"• الرتبة القديمة كانت لـ : {old_link}\n"
            f"• الرتبة الجديدة الآن لـ : {dev_link}\n\n"
            f"✅ المطور أصبح المالك الأساسي بكامل الصلاحيات.",
            parse_mode="HTML")
        return

    # ========= أمر: رفع الكل (للمالك الأساسي فقط) =========
    if text.startswith("رفع الكل"):
        if actor_role not in ["مالك اساسي"]:
            bot.reply_to(message, "⛔ هذا الأمر للمالك الأساسي فقط.")
            return
        parts_cmd = text.split()
        # رفع الكل مالك / رفع الكل ادمن / رفع الكل مدير
        target_role = parts_cmd[2] if len(parts_cmd) >= 3 else None
        ALLOWED_BULK = ["ادمن", "مدير", "منشئ", "مالك"]
        if not target_role or target_role not in ALLOWED_BULK:
            bot.reply_to(message,
                "⚠️ استخدم: <code>رفع الكل [رتبة]</code>\n\n"
                f"الرتب المتاحة: {' | '.join(ALLOWED_BULK)}\n"
                "مثال: <code>رفع الكل مالك</code>",
                parse_mode="HTML")
            return
        # جمع كل الأعضاء اللي عندهم رسائل بالقروب
        members_to_raise = []
        for uid_str in chat.get("messages", {}).keys():
            uid_int = int(uid_str)
            if uid_int == user_id: continue  # ما يغير رتبة نفسه
            current_role = get_role(chat_id, uid_int)
            if current_role in ["مالك اساسي", "مساعد مالك"]: continue  # ما يرفع فوق المالك
            members_to_raise.append(uid_int)
        if not members_to_raise:
            bot.reply_to(message, "⚠️ لا يوجد أعضاء لرفع رتبتهم.")
            return
        # رفع الرتب
        count = 0
        for uid_int in members_to_raise:
            # إزالة من الرتبة الحالية أولاً
            for r in ALLOWED_BULK:
                if uid_int in chat["roles"].get(r, []):
                    chat["roles"][r].remove(uid_int)
            # إضافة للرتبة الجديدة
            if target_role not in chat["roles"]:
                chat["roles"][target_role] = []
            if uid_int not in chat["roles"][target_role]:
                chat["roles"][target_role].append(uid_int)
            count += 1
        save_db()
        add_event(chat_id, f"⬆️ رفع الكل لرتبة {target_role} ({count} عضو) — {human_name(user)}")
        bot.reply_to(message,
            f"✅ <b>تم رفع {count} عضو لرتبة {target_role}!</b>\n\n"
            f"⚠️ الأعضاء ذوو الرتب الأعلى (مالك اساسي، مساعد مالك) لم يتأثروا.",
            parse_mode="HTML")
        return

    # ========= جلسة مسح الاختصار =========
    if user_key in shortcut_delete_steps:
        sess = shortcut_delete_steps[user_key]
        if not text: return
        cid = sess.get("chat_id", chat_id)
        if sess["step"] == "waiting_shortcut_name":
            shortcuts = ensure_shortcuts(cid)
            if text not in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{text}</b> غير موجود.", parse_mode="HTML")
                del shortcut_delete_steps[user_key]
                return
            # حفظ الاسم وطلب تأكيد
            shortcut_delete_steps[user_key] = {"step": "waiting_confirm", "shortcut": text, "chat_id": cid}
            mk = types.InlineKeyboardMarkup(row_width=2)
            mk.add(
                types.InlineKeyboardButton("✅ تأكيد المسح", callback_data=f"scdel_confirm_{cid}"),
                types.InlineKeyboardButton("❌ إلغاء", callback_data=f"scdel_cancel_{cid}")
            )
            bot.reply_to(message, f"⚠️ هل تريد مسح الاختصار <b>{text}</b> ← <b>{shortcuts[text]}</b>؟",
                         parse_mode="HTML", reply_markup=mk)
        return

    # ========= جلسة إضافة الاختصار (النظام الجديد) =========
    if user_key in shortcut_steps:
        sess = shortcut_steps[user_key]
        if not text: return
        cid = sess.get("chat_id", chat_id)
        if sess["step"] == "waiting_shortcut_word":
            # المرحلة 1: كتب الاختصار، نطلب منه الأمر
            shortcuts = ensure_shortcuts(cid)
            if text in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{text}</b> موجود مسبقاً. اكتب اختصاراً مختلفاً.", parse_mode="HTML")
                return
            shortcut_steps[user_key] = {"step": "waiting_cmd_for_shortcut", "shortcut": text, "chat_id": cid}
            bot.reply_to(message, f"✅ الاختصار: <b>{text}</b>\n\n📝 الآن اكتب الأمر الذي تريد اختصاره\nمثال: <code>ادمن</code>", parse_mode="HTML")
        elif sess["step"] == "waiting_cmd_for_shortcut":
            shortcut    = sess["shortcut"]
            original_cmd = text
            shortcuts = ensure_shortcuts(cid)
            # التأكد من عدم تكرار الاختصار
            if shortcut in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{shortcut}</b> موجود مسبقاً.", parse_mode="HTML")
                del shortcut_steps[user_key]
                return
            shortcuts[shortcut] = original_cmd
            save_db()
            del shortcut_steps[user_key]
            bot.reply_to(message,
                f"✅ <b>تم إضافة الاختصار!</b>\n\n"
                f"⚡ <code>{shortcut}</code> ← <b>{original_cmd}</b>\n\n"
                f"أي شخص يكتب <b>{shortcut}</b> يطلعله نفس نتيجة <b>{original_cmd}</b>",
                parse_mode="HTML")
        # جلسة قديمة
        elif sess["step"] == "waiting_cmd":
            shortcut_steps[user_key] = {"step": "waiting_shortcut", "original_cmd": text, "chat_id": cid}
            bot.reply_to(message, f"✅ الأمر: <b>{text}</b>\n\n📝 الآن أرسل الاختصار المطلوب\nمثال: <code>ف</code>", parse_mode="HTML")
        elif sess["step"] == "waiting_shortcut":
            original_cmd = sess["original_cmd"]
            shortcut = text
            shortcuts = ensure_shortcuts(cid)
            if shortcut in shortcuts:
                bot.reply_to(message, f"⚠️ الاختصار <b>{shortcut}</b> موجود مسبقاً.", parse_mode="HTML")
                del shortcut_steps[user_key]
                return
            shortcuts[shortcut] = original_cmd
            save_db()
            del shortcut_steps[user_key]
            bot.reply_to(message,
                f"✅ <b>تم إضافة الاختصار!</b>\n\n"
                f"⚡ <code>{shortcut}</code> ← <b>{original_cmd}</b>",
                parse_mode="HTML")
        return

    check_spam(message)

    if text == "تفعيل البوت":
        ok = set_main_owner(chat_id, user_id)
        if ok:
            bot.reply_to(message, "✅ تم تفعيل البوت\nأنت الآن <b>المالك الأساسي</b> لهذه المجموعة.")
        else:
            owner_id = chat["main_owner"]
            if owner_id == user_id:
                bot.reply_to(message, "✅ البوت مُفعل مسبقًا وأنت <b>المالك الأساسي</b>.")
            else:
                bot.reply_to(message, "ℹ️ البوت مُفعل مسبقًا ولا يمكنك تغيـير المالك الأساسي.")
        return

    if text == "تفعيل اليوتيوب":
        yt_groups = ensure_yt_groups()
        if chat_id not in yt_groups:
            yt_groups.append(chat_id)
            save_db()
            bot.reply_to(message,
                "✅ <b>تم تفعيل خاصية اليوتيوب بهذا القروب!</b>\n\n"
                "استخدم داخل هذا القروب:\n"
                "— <code>يوت [اسم الأغنية]</code>\n"
                "— <code>بحث [اسم الأغنية]</code> 🎵", parse_mode="HTML")
        else:
            bot.reply_to(message, "ℹ️ خاصية اليوتيوب مفعّلة مسبقاً بهذا القروب.")
        return

    if text == "تعليمات":
        help_txt = (
            "📜 <b>تعليمات البوت</b>\n"
            "— تفعيل البوت: <code>تفعيل البوت</code>\n"
            "— تفعيل اليوتيوب بالقروب: <code>تفعيل اليوتيوب</code>\n"
            "— تحميل أغنية (داخل القروب فقط): <code>يوت [اسم الأغنية]</code>\n"
            "— بحث بيوتيوب (داخل القروب فقط): <code>بحث [اسم الأغنية]</code>\n"
            "— إعطاء مالك أساسي (نقل ملكية): <code>اعطاء مالك اساسي @username</code>\n"
            "— رتبتك: <code>رتبتي</code>\n"
            "— معلوماتك: <code>معلوماتي</code>\n"
            "— كشف بالرد: رد على رسالة الشخص واكتب <code>كشف</code>\n"
            "— كشف باليوزر: <code>كشف @username</code>\n"
            "— رفع/تنزيل (بالرد أو باليوزر):\n"
            "   <code>رفع @username رتبة</code> / <code>تنزيل @username رتبة</code>\n"
            "— تصفير التوب: <code>تصفير التوب</code> (المالك الاساسي فقط)\n"
            "— توب: <code>توب</code>\n"
            "— فف: <code>فف</code>\n"
            "— قائمة الادمنية: <code>ادمن</code> / تحديث القائمة: <code>تحديث قائمة الادمن</code>\n"
            "— الحظر: <code>حظر @username</code> (للمدير وفوق)\n"
            "— رفع الحظر: <code>رفع الحظر @username</code> (للمدير وفوق)\n"
            "— التقييد: <code>تقييد @username</code> (للادمن وفوق)\n"
            "— رفع التقييد: <code>رفع التقييد @username</code> (للادمن وفوق)\n"
            "— الكتم: <code>كتم @username</code> (للمدير وفوق)\n"
            "— رفع الكتم: <code>رفع الكتم @username</code> (للمدير وفوق)\n"
            "— رفع القيود: <code>رفع القيود @username</code> (للادمن وفوق)\n"
            "— الانذار: <code>انذار @username</code> (للادمن وفوق)\n"
            "— عدد الانذارات: <code>انذاراته @username</code> (للادمن وفوق)\n"
            "— منح صلاحية الحظر: <code>اعطاء صلاحية حظر @username</code> (للمالك الأساسي ومساعده)\n"
            "— سحب صلاحية الحظر: <code>سحب صلاحية حظر @username</code> (للمالك الأساسي ومساعده)\n\n"
            "<b>🏦 أوامر النظام البنكي:</b>\n"
            "— انشاء حساب بنكي - إنشاء حساب مع اختيار نوع البطاقة\n"
            "— فلوسي - عرض الرصيد الحالي\n"
            "— حسابي - عرض معلومات الحساب البنكي\n"
            "— رصيدي - عرض الرصيد الكامل\n"
            "— ممتلكاتي - عرض جميع الممتلكات\n"
            "— يومي - المكافأة اليومية (100-1000 دولار)\n"
            "— راتب - كل 10 دقائق (راتب عشوائي)\n"
            "— شراء [كمية] [عنصر] - شراء عنصر\n"
            "— بيع [كمية] [عنصر] - بيع عنصر\n"
            "— تحويل المبلغ @شخص - تحويل أموال\n"
            "— توب الفلوس - عرض أغنى 30 شخص\n"
            "— بطاقتي - عرض البطاقة البنكية\n"
            "— مخزني - عرض العناصر المملوكة\n"
            "— تصفير فلوسي - تصفير فلوسك الخاصة\n"
            "— تصفير توب الفلوس - تصفير كل الفلوس (للمطور فقط)\n"
            "— هدية مطور @username - منح هدية المطور (للمطور فقط)\n\n"
            "<b>💍 نظام الزواج والطلاق:</b>\n"
            "— زواج @username المبلغ - الزواج بشخص مع المهر\n"
            "— زوجتي - عرض زوجاتك\n"
            "— زوجاتي - منشن لزوجاتك\n"
            "— طلاق - طلاق جميع الزوجات\n"
            "— طلاق الاولى/الثانية/الثالثة/الرابعة - طلاق زوجة محددة\n"
            "— خلع @username - خلع الزوج وإرجاع المهر\n"
            "— توب المهور - عرض أكبر المهور\n\n"
            "<b>🎮 الألعاب:</b>\n"
            "— زرف @username - سرقة الأموال (كل 5 دقائق)\n"
            "— انق - لعبة الترجمة (مكافأة 7 دولار)\n"
            "— احكام - لعبة الأحكام الجماعية (تنتهي الجولة بعد 'نعم'، اكتب احكام من جديد لجولة جديدة)\n"
            "— 🧙 السحرة، 🏰 عرش المملكة، 🐺 المافيا - افتح خاص البوت واضغط زر «الألعاب»\n"
            "— حظ فلوسي المبلغ - لعبة الحظ (كل 20 دقيقة)\n"
            "— استثمار المبلغ - الاستثمار (كل 20 دقيقة)\n"
            "— استثمار كل الفلوس - استثمار كل الرصيد\n\n"
            "<b>🛒 أوامر المتجر:</b>\n"
            "— المتجر - عرض العناصر الشائعة\n"
            "— متجر العالمي - عرض جميع العناصر\n"
            "— شراء [كمية] [عنصر] - شراء عنصر\n"
            "— بيع [كمية] [عنصر] - بيع عنصر\n\n"
            "الرتب: <code>مالك اساسي</code> (نقل فقط)، <code>مساعد مالك</code> (واحد فقط)، <code>مالك</code>، <code>منشئ</code>، <code>مدير</code>، <code>ادمن</code>، <code>مميز</code>، <code>عضو</code>"
        )
        bot.reply_to(message, help_txt)
        return

    if text == "رتبتي":
        bot.reply_to(message, f"🎖️ رتبتك الحالية: <b>{actor_role}</b>")
        return

    if text == "معلوماتي":
        try:
            bio = bot.get_chat(user_id).bio or "لا يوجد"
        except:
            bio = "لا يوجد"
        bot.reply_to(message,
            f"👤 <b>معلوماتك</b>\n"
            f"الاسم: {human_name(user)}\n"
            f"اليوزر: @{user.username if user.username else 'بدون'}\n"
            f"الآيدي: <code>{user_id}</code>\n"
            f"الرتبة: <b>{actor_role}</b>\n"
            f"الوقت: <code>{now_str()}</code>\n"
            f"رسائلك بالتفاعل: {chat['messages'].get(str(user_id),0)}"
        )
        return

    if text in ["ايتو","بوت"]:
        bot.reply_to(message, random_reply(text))
        return

    if text == "تصفير التوب":
        if actor_role=="مالك اساسي":
            chat["messages"] = {}
            save_db()
            bot.reply_to(message,"✅ تم تصفير التوب")
        else:
            bot.reply_to(message,"⛔ فقط المالك الأساسي يمكنه تصفير التوب")
        return

    if text == "تقييد الدخول":
        if actor_role == "مالك اساسي":
            chat["restrict_entry"] = True
            save_db()
            bot.reply_to(message, "✅ تم تفعيل تقييد الدخول.\nهسة أي رسالة انضمام (عن طريق رابط أو إضافة عضو) راح تنمسح تلقائياً.")
        else:
            bot.reply_to(message, "⛔ فقط المالك الأساسي يمكنه تفعيل تقييد الدخول")
        return

    if text == "الغاء تقييد الدخول":
        if actor_role == "مالك اساسي":
            chat["restrict_entry"] = False
            save_db()
            bot.reply_to(message, "✅ تم إلغاء تقييد الدخول.\nرسائل الانضمام راح تظهر بشكل طبيعي هسة.")
        else:
            bot.reply_to(message, "⛔ فقط المالك الأساسي يمكنه إلغاء تقييد الدخول")
        return

    if text == "توب":
        bot.reply_to(message, "📊 <b>اختر التوب:</b>", reply_markup=build_top_markup())
        return

    if text == "فف":
        sorted_msgs = sorted(chat["messages"].items(), key=lambda x:x[1])
        txt="📊 <b>ترتيبك في المتفاعلين</b>\n"
        for i,user_count in enumerate(sorted_msgs):
            uid,count = user_count
            if int(uid)==user_id:
                txt += f"• رسائلك بالتفاعل ↢ {count}\n• ترتيبك بالمتفاعلين ↢ {i+1}\n-"
                break
        bot.reply_to(message,txt)
        return

    if text == "ادمن":
        txt="═══════════════════\nالمسؤولين عن إدارة القروب : \n───────────────────\n"

        # المالكين (رتبة مالك فقط)
        txt+="• المالكين :\n"
        for i,uid in enumerate(chat["roles"].get("مالك", [])):
            try:
                member = bot.get_chat_member(chat_id, uid).user
                if member.is_bot: continue
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"{i+1} • مالك : {uname}\n────────────────\n"

        # المنشئون
        txt+="• المنشئون :\n"
        for i,uid in enumerate(chat["roles"].get("منشئ", [])):
            try:
                member = bot.get_chat_member(chat_id, uid).user
                if member.is_bot: continue
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"{i+1} • المنشئ : {uname}\n────────────────\n"

        # المدراء
        txt+="• المدراء :\n"
        for i,uid in enumerate(chat["roles"].get("مدير", [])):
            try:
                member = bot.get_chat_member(chat_id, uid).user
                if member.is_bot: continue
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"{i+1} • مدير : {uname}\n───────────────────\n"

        # الأدمنية
        txt+="• الأدمنية :\n"
        for i,uid in enumerate(chat["roles"].get("ادمن", [])):
            try:
                member = bot.get_chat_member(chat_id, uid).user
                if member.is_bot: continue
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"{i+1} • ادمن : {uname}\n────────────────────\n"

        txt+="───────────────────\n"
        txt+="إذا واجهت أي مشكلة أو لاحظت خطأ من قبل المشرفين أو الأدمنية، يُرجى التواصل مباشرة مع المالكين\n"
        txt+="───────────────────\n"

        # المالك الأساسي
        for uid in chat["roles"].get("مالك اساسي", []):
            try:
                member = bot.get_chat_member(chat_id, uid).user
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"👑 مالك اساسي : {uname}\n"

        # مساعد المالك
        if chat["roles"].get("مساعد مالك"):
            try:
                uid = chat["roles"]["مساعد مالك"][0]
                member = bot.get_chat_member(chat_id, uid).user
                uname = f"<a href='tg://user?id={uid}'>{human_name(member)}</a>"
            except:
                uid = chat["roles"]["مساعد مالك"][0]
                uname = f"<a href='tg://user?id={uid}'>{uid}</a>"
            txt+=f"🔰 مساعد مالك : {uname}\n"

        txt+="═══════════════════"
        bot.reply_to(message, txt, parse_mode="HTML")
        return

    if text.startswith("كشف") or text == "كشف":
        target_id = None
        target_user = None
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
        else:
            parts = text.split()
            if len(parts) == 2 and parts[1].startswith("@"):
                uname = parts[1][1:]
                uid = find_user_id_by_username(chat_id, uname)
                if uid:
                    try:
                        member = bot.get_chat_member(chat_id, uid).user
                        target_user = member
                        target_id = uid
                    except:
                        pass
        if not target_id:
            bot.reply_to(message, "⛔ استخدم الرد على رسالة أو <code>كشف @username</code>.")
            return
        t_role = get_role(chat_id, target_id)
        try:
            t_bio = bot.get_chat(target_id).bio or "لا يوجد"
        except:
            t_bio = "لا يوجد"
        
        restrictions = chat["restrictions"].get(str(target_id), {})
        restriction_status = ""
        if restrictions.get("banned"):
            restriction_status += "🔴 محظور\n"
        if restrictions.get("muted"):
            restriction_status += "🔇 مكتوم\n"
        if restrictions.get("restricted"):
            restriction_status += "⛓️ مقيد\n"
        if not restriction_status:
            restriction_status = "🟢 بدون قيود"
        
        warnings = chat["warnings"].get(str(target_id), 0)
        
        bot.reply_to(message,
            f"🔎 <b>كشف المستخدم</b>\n"
            f"الاسم: {human_name(target_user)}\n"
            f"اليوزر: @{target_user.username if target_user.username else 'بدون'}\n"
            f"الآيدي: <code>{target_id}</code>\n"
            f"الرتبة: <b>{t_role}</b>\n"
            f"البايو: {t_bio}\n"
            f"الانذارات: {warnings}/5\n"
            f"حالة القيود:\n{restriction_status}"
        )
        return

    def parse_assign(cmd_text):
        parts = cmd_text.split()
        if len(parts) == 2 and message.reply_to_message:
            return parts[0], None, parts[1]
        if len(parts) == 3 and parts[1].startswith("@"):
            return parts[0], parts[1][1:], parts[2]
        return None, None, None

    if text.startswith("رفع") or text.startswith("تنزيل"):
        action, uname, role_name = parse_assign(text)
        if not action or role_name not in ALL_ROLES:
            bot.reply_to(message,
                "⛔ الاستخدام الصحيح:\n"
                "— بالرد: <code>رفع رتبة</code> / <code>تنزيل رتبة</code>\n"
                "— باليوزر: <code>رفع @username رتبة</code> / <code>تنزيل @username رتبة</code>\n"
                f"الرتب: <code>{'، '.join(ALL_ROLES)}</code>")
            return

        if role_name == "مالك اساسي":
            bot.reply_to(message, "⛔ لا يمكن رفع/تنزيل <b>مالك اساسي</b>. استخدم: <code>اعطاء مالك اساسي @username</code> للنقل.")
            return

        target_id = None
        target_user = None
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
        elif uname:
            uid = find_user_id_by_username(chat_id, uname)
            if uid:
                target_id = uid
                try:
                    target_user = bot.get_chat_member(chat_id, uid).user
                except:
                    pass
        if not target_id:
            bot.reply_to(message, "⛔ لم أتمكن من إيجاد المستخدم. استخدم الرد أو تأكد من اليوزر.")
            return

        # منع رفع/تنزيل النفس
        if target_id == user_id:
            bot.reply_to(message, "⛔ لا يمكنك رفع أو تنزيل نفسك!")
            return

        target_role = get_role(chat_id, target_id)

        # منع رفع/تنزيل المالك الأساسي
        if target_role == "مالك اساسي":
            bot.reply_to(message, "⛔ لا يمكن تغيير رتبة <b>المالك الأساسي</b>.")
            return

        # قواعد الصلاحية حسب الرتب:
        # مالك اساسي → يرفع/ينزل لحد منشئ
        # مالك → يرفع/ينزل لحد مدير
        # منشئ → يرفع/ينزل لحد ادمن
        # مدير → يرفع/ينزل لحد مميز فقط
        # ادمن/مميز/عضو → لا يقدر
        ACTOR_MAX_TARGET = {
            "مالك اساسي": ["مساعد مالك", "مالك", "منشئ", "مدير", "ادمن", "مميز", "عضو"],
            "مساعد مالك": ["مالك", "منشئ", "مدير", "ادمن", "مميز", "عضو"],
            "مالك": ["منشئ", "مدير", "ادمن", "مميز", "عضو"],
            "منشئ": ["مدير", "ادمن", "مميز", "عضو"],
            "مدير": ["ادمن", "مميز", "عضو"],
            "ادمن": ["مميز", "عضو"],
            "مميز": [],
            "عضو": [],
        }
        allowed_targets = ACTOR_MAX_TARGET.get(actor_role, [])

        # التحقق أن الهدف ضمن نطاق الصلاحية
        if target_role not in allowed_targets:
            bot.reply_to(message, f"⛔ رتبتك (<b>{actor_role}</b>) لا تستطيع تغيير رتبة <b>{target_role}</b>.")
            return

        if text.startswith("رفع"):
            if role_name not in allowed_targets:
                bot.reply_to(message, f"⛔ رتبتك (<b>{actor_role}</b>) لا تستطيع رفع أحد إلى <b>{role_name}</b>.")
                return
            set_role(chat_id, target_id, role_name)
            tname = human_name(target_user) if target_user else str(target_id)
            tlink = f'<a href="tg://user?id={target_id}">{tname}</a>'
            bot.reply_to(message, f"✅ تم رفع {tlink} إلى رتبة <b>{role_name}</b>", parse_mode="HTML")
        else:
            new_role = downgrade_role(chat_id, target_id)
            tname = human_name(target_user) if target_user else str(target_id)
            tlink = f'<a href="tg://user?id={target_id}">{tname}</a>'
            bot.reply_to(message, f"✅ تم تنزيل {tlink} إلى رتبة <b>{new_role}</b>", parse_mode="HTML")
        return

    # ========= الأوامر الجديدة داخل main_handler =========

    if text == "لوحة الادارة":
        if actor_role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
            bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
            return
        try: group_name = bot.get_chat(chat_id).title or "القروب"
        except: group_name = "القروب"
        total_msgs  = sum(chat.get("messages",{}).values())
        total_warns = sum(1 for w in chat.get("warnings",{}).values() if w > 0)
        total_banned= sum(1 for r in chat.get("restrictions",{}).values() if r.get("banned"))
        txt = (f"⚙️ <b>لوحة إدارة : {group_name}</b>\n\n"
               f"• إجمالي الرسائل : <b>{total_msgs:,}</b>\n"
               f"• إنذارات نشطة  : <b>{total_warns}</b>\n"
               f"• محظورون       : <b>{total_banned}</b>\n\n"
               f"اختر من الأزرار أدناه 👇")
        bot.reply_to(message, txt, reply_markup=build_admin_panel_markup(chat_id), parse_mode="HTML")
        return

    if text == "سجل القروب":
        if actor_role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
            bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
            return
        log = chat.get("event_log", [])
        if not log:
            bot.reply_to(message, "📜 <b>سجل القروب</b>\n\nلا توجد أحداث مسجلة بعد.", parse_mode="HTML")
            return
        txt = "📜 <b>سجل الأحداث — آخر 15 حدث:</b>\n\n"
        for ev in reversed(log[-15:]): txt += f"• {ev}\n"
        bot.reply_to(message, txt, parse_mode="HTML")
        return

    if text == "الاداريون":
        ROLE_EMOJI = {"مالك اساسي":"👑","مساعد مالك":"🔰","مالك":"🏅","منشئ":"⭐","مدير":"🛡️","ادمن":"🔷"}
        ORDER = ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن"]
        try: group_name = bot.get_chat(chat_id).title or "القروب"
        except: group_name = "القروب"
        txt = f"⚙️ <b>إداريو {group_name}:</b>\n━━━━━━━━━━━━━━━\n"
        found = False
        for r in ORDER:
            members = chat["roles"].get(r, [])
            if r == "مالك اساسي" and chat.get("main_owner"):
                members = [chat["main_owner"]]
            for uid in members:
                try:
                    mem = bot.get_chat_member(chat_id, uid).user
                    if mem.is_bot: continue
                    link = f'<a href="tg://user?id={uid}">{human_name(mem)}</a>'
                except: link = f'<a href="tg://user?id={uid}">{uid}</a>'
                txt += f"{ROLE_EMOJI.get(r,'•')} {link} ← <b>{r}</b>\n"
                found = True
        if not found: txt += "لا يوجد إداريون مسجلون."
        txt += "━━━━━━━━━━━━━━━"
        bot.reply_to(message, txt, parse_mode="HTML")
        return

    if text == "رفع كل الانذارات":
        if actor_role not in ["مالك اساسي","مساعد مالك","مالك"]:
            bot.reply_to(message, "⛔ هذا الأمر للمالك وما فوقه فقط.")
            return
        count = sum(1 for w in chat.get("warnings",{}).values() if w > 0)
        chat["warnings"] = {}
        save_db()
        add_event(chat_id, f"🧹 رفع كل الانذارات ({count}) — {human_name(user)}")
        bot.reply_to(message, f"✅ تم رفع جميع الانذارات (<b>{count}</b> إنذار).", parse_mode="HTML")
        return

    if text.startswith("إنذارات") or text.startswith("انذاراته"):
        if actor_role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
            bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
            return
        target_id   = None
        target_user = None
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id   = target_user.id
        else:
            parts = text.split()
            if len(parts) >= 2 and parts[1].startswith("@"):
                uid = find_user_id_by_username(chat_id, parts[1][1:])
                if uid:
                    target_id = uid
                    try: target_user = bot.get_chat_member(chat_id, uid).user
                    except: pass
        if not target_id:
            bot.reply_to(message, "⛔ استخدم الرد أو <code>إنذارات @يوزر</code>", parse_mode="HTML")
            return
        warns = chat.get("warnings", {}).get(str(target_id), 0)
        name  = human_name(target_user) if target_user else str(target_id)
        link  = f'<a href="tg://user?id={target_id}">{name}</a>'
        bar   = "🔴" * warns + "⚪" * (5 - warns)
        txt   = f"⚠️ <b>إنذارات {link}:</b>\n\n{bar}\n• عدد الانذارات : <b>{warns} / 5</b>\n"
        if warns >= 5: txt += "• الحالة : 🔴 <b>تجاوز الحد — تقييد تلقائي</b>"
        elif warns == 0: txt += "• الحالة : 🟢 <b>نظيف</b>"
        else: txt += f"• الحالة : 🟡 <b>تحت المراقبة</b> ({5-warns} متبقي)"
        bot.reply_to(message, txt, parse_mode="HTML")
        return

    if text.startswith("قوانين تعيين"):
        if actor_role not in ["مالك اساسي","مساعد مالك","مالك"]:
            bot.reply_to(message, "⛔ فقط المالك يمكنه تعيين القوانين.")
            return
        new_rules = text.replace("قوانين تعيين", "").strip()
        if not new_rules:
            bot.reply_to(message, "⚠️ اكتب القوانين بعد الأمر.\nمثال: <code>قوانين تعيين 1. احترام الجميع</code>", parse_mode="HTML")
            return
        chat["group_rules"] = new_rules
        save_db()
        add_event(chat_id, f"📋 تحديث قوانين القروب — {human_name(user)}")
        bot.reply_to(message, "✅ تم حفظ قوانين القروب بنجاح.")
        return

    if text == "قوانين":
        rules = chat.get("group_rules")
        if not rules:
            bot.reply_to(message, "📋 <b>لا توجد قوانين.</b>\n\nللمالك:\n<code>قوانين تعيين [النص]</code>", parse_mode="HTML")
            return
        try: group_name = bot.get_chat(chat_id).title or "القروب"
        except: group_name = "القروب"
        bot.reply_to(message, f"📋 <b>قوانين {group_name}:</b>\n\n{rules}", parse_mode="HTML")
        return

    if text.startswith("تحذير عام"):
        if actor_role not in ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير"]:
            bot.reply_to(message, "⛔ هذا الأمر للمدير وما فوقه.")
            return
        warning_text = text.replace("تحذير عام", "").strip()
        if not warning_text:
            bot.reply_to(message, "⚠️ اكتب نص التحذير.\nمثال: <code>تحذير عام ممنوع الاعلانات</code>", parse_mode="HTML")
            return
        sender_name = human_name(user)
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("✅ فهمت", callback_data="warn_understood"))
        bot.send_message(chat_id,
            f"📢 <b>⚠️ تحذير عام من الادارة ⚠️</b>\n\n{warning_text}\n\n— <b>{sender_name}</b>",
            parse_mode="HTML", reply_markup=mk)
        add_event(chat_id, f"📢 تحذير عام — {sender_name}")
        return

    if text in ["مطور", "المطور"]:
        try:
            dev_id   = BOT_OWNER_ID
            dev_info = bot.get_chat(dev_id)
            dev_name = human_name(dev_info)
            dev_bio  = dev_info.bio or "لا يوجد وصف"
            dev_user = dev_info.username
            # الاسم لينك أزرق قابل للضغط
            dev_link = f'<a href="tg://user?id={dev_id}">{dev_name}</a>'
            dev_caption = (
                f"👨\u200d💻 <b>مطور البوت</b>\n\n"
                f"• الاسم : {dev_link}\n"
                f"• اليوزر : @{dev_user if dev_user else 'بدون'}\n"
                f"• البايو : {dev_bio}"
            )
            # زر تحت الرسالة بنفس اسم المطور يفتح حسابه
            dev_url = f"tg://user?id={dev_id}"
            dev_markup = types.InlineKeyboardMarkup()
            dev_markup.add(types.InlineKeyboardButton(f"👤 {dev_name}", url=dev_url))
            photos = bot.get_user_profile_photos(dev_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                bot.send_photo(
                    chat_id,
                    file_id,
                    caption=dev_caption,
                    parse_mode="HTML",
                    has_spoiler=True,
                    reply_to_message_id=message.message_id,
                    reply_markup=dev_markup
                )
            else:
                bot.reply_to(message, dev_caption, parse_mode="HTML", reply_markup=dev_markup)
        except:
            bot.reply_to(message, "⚠️ تعذر جلب معلومات المطور.")
        return

    # ========= انق — آخر شيء في main_handler =========
    # يشتغل فقط إذا ما انمسكت الرسالة بأي handler فوق
    if user_id in anaq_sessions and anaq_sessions[user_id]["chat_id"] == chat_id:
        if not games_allowed(chat_id):
            bot.reply_to(message, "🚫 الألعاب مطفأة حالياً.")
            del anaq_sessions[user_id]
            return
        session = anaq_sessions[user_id]
        if text == session["answer"]:
            banking = ensure_banking()
            user_data = banking["users"].get(str(user_id))
            reward_text = ""
            if user_data:
                reward = random.randint(3, 1000)
                user_data["balance"] += reward
                save_db()
                reward_text = f"\n💰 ربحت <b>{reward:,} دينار</b>! رصيدك: <b>{user_data['balance']:,}</b>"
            del anaq_sessions[user_id]
            bot.reply_to(message, f"✅ <b>صح!</b>{reward_text}\n\n💡 اكتب <b>انق</b> لجولة جديدة")
        # خطأ — ما يرد شي

# ========= نظام الاختصارات =========
SHORTCUT_ALLOWED = ["مالك", "منشئ", "مساعد مالك", "مالك اساسي"]

def can_manage_shortcuts(chat_type, chat_id, user_id):
    """بالخاص كل شخص يدير اختصاراته الشخصية، وبالقروب لازم رتبة مالك وفوق"""
    if chat_type == "private":
        return True
    return get_role(chat_id, user_id) in SHORTCUT_ALLOWED

def ensure_shortcuts(chat_id):
    chat = ensure_chat(chat_id)
    if "shortcuts" not in chat:
        chat["shortcuts"] = {}
        save_db()
    return chat["shortcuts"]

# جلسة مسح الاختصار

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "اختصار" and (m.chat.type in ["group","supergroup"] or m.chat.type == "private"))
def shortcut_panel_cmd(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_manage_shortcuts(message.chat.type, chat_id, user_id):
        bot.reply_to(message, "⛔ هذا الأمر مخصص لرتبة <b>مالك</b> وفوق.", parse_mode="HTML")
        return
    bot.reply_to(message, "⚙️ <b>نظام الاختصارات</b>\n\nاختر من الأزرار:", parse_mode="HTML",
                 reply_markup=build_shortcut_panel(chat_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("scpanel_"))
def shortcut_panel_callback(call):
    user_id = call.from_user.id
    data    = call.data
    chat_id = call.message.chat.id
    parts   = data.split("_")
    action  = parts[1]
    cid     = int(parts[2])
    role    = get_role(cid, user_id)

    if not can_manage_shortcuts(call.message.chat.type, cid, user_id):
        bot.answer_callback_query(call.id, "⛔ مخصص لرتبة مالك وفوق.", show_alert=True)
        return

    if action == "add":
        key = f"{cid}_{user_id}"
        shortcut_steps[key] = {"step": "waiting_shortcut_word", "chat_id": cid}
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "✏️ اكتب الاختصار الذي تريده\nمثال: <code>اد</code>", parse_mode="HTML")

    elif action == "list":
        shortcuts = ensure_shortcuts(cid)
        if not shortcuts:
            bot.answer_callback_query(call.id, "لا يوجد اختصارات بعد.", show_alert=True)
            return
        txt = "📋 <b>الاختصارات الموجودة:</b>\n\n"
        for sh, orig in shortcuts.items():
            txt += f"⚡ <code>{sh}</code> ← <b>{orig}</b>\n"
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"scpanel_back_{cid}"))
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
        except: pass
        bot.answer_callback_query(call.id)

    elif action == "del":
        key = f"{cid}_{user_id}"
        shortcut_delete_steps[key] = {"step": "waiting_shortcut_name", "chat_id": cid}
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🗑 اكتب الاختصار الذي تريد مسحه\nمثال: <code>اد</code>", parse_mode="HTML")

    elif action == "back":
        try:
            bot.edit_message_text("⚙️ <b>نظام الاختصارات</b>\n\nاختر من الأزرار:", chat_id, call.message.message_id,
                                  reply_markup=build_shortcut_panel(cid), parse_mode="HTML")
        except: pass
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الاختصارات" and (m.chat.type in ["group","supergroup"] or m.chat.type == "private"))
def show_shortcuts(message):
    chat_id = message.chat.id
    shortcuts = ensure_shortcuts(chat_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    # زر إضافة اختصار
    markup.add(types.InlineKeyboardButton("➕ إضافة اختصار", callback_data=f"sc_add_{chat_id}"))
    # أزرار الاختصارات الموجودة مع زر حذف
    for short, orig in shortcuts.items():
        markup.row(
            types.InlineKeyboardButton(f"⚡ {short} ← {orig}", callback_data="sc_noop"),
            types.InlineKeyboardButton("🗑", callback_data=f"sc_del_{chat_id}_{short}")
        )
    if not shortcuts:
        bot.reply_to(message, "📋 <b>الاختصارات</b>\n\nلا يوجد اختصارات بعد.", reply_markup=markup)
    else:
        txt = f"📋 <b>اختصارات القروب ({len(shortcuts)}):</b>"
        bot.reply_to(message, txt, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sc_"))
def shortcut_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "sc_noop":
        bot.answer_callback_query(call.id)
        return

    if data.startswith("sc_add_"):
        cid = int(data.split("_")[2])
        if not can_manage_shortcuts(call.message.chat.type, cid, user_id):
            bot.answer_callback_query(call.id, "⛔ مخصص لرتبة منشئ وفوق.", show_alert=True)
            return
        # بدأ جلسة الاضافة
        key = f"{cid}_{user_id}"
        shortcut_steps[key] = {"step": "waiting_cmd", "chat_id": cid, "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        bot.send_message(cid, "📝 أرسل الأمر اللي تريد تختصره\nمثال: <code>فلوسي</code>")

    elif data.startswith("sc_del_"):
        parts = data.split("_", 3)
        cid = int(parts[2])
        shortcut = parts[3]
        if not can_manage_shortcuts(call.message.chat.type, cid, user_id):
            bot.answer_callback_query(call.id, "⛔ مخصص لرتبة منشئ وفوق.", show_alert=True)
            return
        shortcuts = ensure_shortcuts(cid)
        if shortcut in shortcuts:
            del shortcuts[shortcut]
            save_db()
        # نحدث الرسالة
        shortcuts = ensure_shortcuts(cid)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ إضافة اختصار", callback_data=f"sc_add_{cid}"))
        for short, orig in shortcuts.items():
            markup.row(
                types.InlineKeyboardButton(f"⚡ {short} ← {orig}", callback_data="sc_noop"),
                types.InlineKeyboardButton("🗑", callback_data=f"sc_del_{cid}_{short}")
            )
        txt = f"📋 <b>اختصارات القروب ({len(shortcuts)}):</b>" if shortcuts else "📋 <b>الاختصارات</b>\n\nلا يوجد اختصارات بعد."
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=markup)
        except: pass
        bot.answer_callback_query(call.id, f"✅ تم حذف الاختصار {shortcut}")

@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("مسح الاختصار") and (m.chat.type in ["group","supergroup"] or m.chat.type == "private"))
def delete_shortcut(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not can_manage_shortcuts(message.chat.type, chat_id, user_id):
        bot.reply_to(message, "⛔ هذا الأمر مخصص لرتبة <b>منشئ</b> وفوق.")
        return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ استخدام: <code>مسح الاختصار ف</code>")
        return
    shortcut = parts[1].strip()
    shortcuts = ensure_shortcuts(chat_id)
    if shortcut not in shortcuts:
        bot.reply_to(message, f"⚠️ الاختصار <b>{shortcut}</b> غير موجود.")
        return
    orig = shortcuts.pop(shortcut)
    save_db()
    bot.reply_to(message, f"✅ تم حذف الاختصار <b>{shortcut}</b> ← {orig}")

# ========= معالج تنفيذ الاختصارات =========
def _is_shortcut(m):
    if not m.text:
        return False
    key = f"{m.chat.id}_{m.from_user.id}"
    if key in shortcut_steps:
        return False
    cid = str(m.chat.id)
    return m.text.strip() in DB.get(cid, {}).get("shortcuts", {})

@bot.message_handler(func=_is_shortcut, priority=3)
def handle_shortcuts(message):
    cid = str(message.chat.id)
    shortcuts = DB.get(cid, {}).get("shortcuts", {})
    original_cmd = shortcuts.get(message.text.strip())
    if not original_cmd: return
    message.text = original_cmd
    bot.process_new_messages([message])


# ================================================================
# الاضافات الجديدة
# ================================================================

# ========= سجل الأحداث =========
def ensure_event_log(chat_id):
    chat = ensure_chat(chat_id)
    if "event_log" not in chat:
        chat["event_log"] = []
    return chat["event_log"]

def add_event(chat_id, text):
    """يضيف حدث لسجل القروب (يحتفظ بآخر 50 حدث فقط)"""
    log = ensure_event_log(chat_id)
    now = datetime.now().strftime("%d/%m %H:%M")
    log.append(f"[{now}] {text}")
    if len(log) > 50:
        log.pop(0)
    save_db()


# ========= رسالة الترحيب بالأعضاء الجدد =========
@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    chat_id = message.chat.id
    chat = ensure_chat(chat_id)
    if message.chat.title:
        chat["title"] = message.chat.title
        save_db()

    # ===== تقييد الدخول: احذف رسالة الانضمام (سواء عن طريق رابط أو إضافة عضو) =====
    if chat.get("restrict_entry"):
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        return

    for new_user in message.new_chat_members:
        if new_user.is_bot:
            continue

        user_id  = new_user.id
        name     = human_name(new_user)
        username = new_user.username

        # تسجيل في known_users
        if username:
            chat["known_users"][username] = user_id
            save_db()

        # تسجيل في سجل الأعضاء الجدد (للوحة الادارة)
        if "new_members" not in chat:
            chat["new_members"] = []
        chat["new_members"].append({
            "id":   user_id,
            "name": name,
            "time": datetime.now().strftime("%d/%m %H:%M")
        })
        if len(chat["new_members"]) > 30:
            chat["new_members"].pop(0)
        save_db()

        # سجل الأحداث
        mention = f'<a href="tg://user?id={user_id}">{name}</a>'
        add_event(chat_id, f"🆕 {mention} انضم للقروب")

        # بناء رسالة الترحيب
        if username:
            user_link = f'<a href="tg://user?id={user_id}">@{username}</a>'
        else:
            user_link = f'<a href="tg://user?id={user_id}">{name}</a>'

        welcome_lines = [
            f"🌟 نورت القروب يا {user_link} 👑",
            f"",
            f"• اسمك : <b>{name}</b>",
            f"• حسابك : {user_link}",
            f"",
            f"يلا سوي حساب بنكي واشترك معنا بالألعاب 🎮",
            f"اكتب <code>تعليمات</code> لمعرفة الأوامر ✨",
        ]
        welcome_text = "\n".join(welcome_lines)

        # نحاول نجيب صورة القروب
        try:
            chat_photos = bot.get_chat(chat_id)
            group_photo = chat_photos.photo
            if group_photo:
                bot.send_photo(
                    chat_id,
                    group_photo.big_file_id,
                    caption=welcome_text,
                    parse_mode="HTML"
                )
            else:
                bot.send_message(chat_id, welcome_text, parse_mode="HTML")
        except:
            try:
                bot.send_message(chat_id, welcome_text, parse_mode="HTML")
            except:
                pass


# ========= أمر: مطور =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "مطور")
def show_developer_info(message):
    try:
        dev_id   = BOT_OWNER_ID
        dev_info = bot.get_chat(dev_id)
        dev_name = human_name(dev_info)
        dev_bio  = dev_info.bio or "لا يوجد وصف"
        dev_user = dev_info.username

        if dev_user:
            dev_link = f'<a href="tg://user?id={dev_id}">@{dev_user}</a>'
        else:
            dev_link = f'<a href="tg://user?id={dev_id}">{dev_name}</a>'

        # نص معلومات المطور
        dev_text = (
            f"👨‍💻 <b>مطور البوت</b>\n\n"
            f"• الاسم : <b>{dev_name}</b>\n"
            f"• الحساب : {dev_link}\n"
            f"• الوصف : <tg-spoiler>{dev_bio}</tg-spoiler>"
        )

        # نحاول نجيب صورة المطور
        photos = bot.get_user_profile_photos(dev_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            # زر لرفع التشويش عن الصورة — نرسل الصورة كـ spoiler
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                "👁️ إظهار صورة المطور", callback_data=f"show_dev_photo_{dev_id}"
            ))
            # نرسل نص بدون صورة أول + زر
            bot.reply_to(message, dev_text + "\n\n🖼️ <i>الصورة مخفية — اضغط الزر لإظهارها</i>",
                         parse_mode="HTML", reply_markup=markup)
            # نخزن file_id مؤقتاً في DB
            if "dev_photo_cache" not in DB:
                DB["dev_photo_cache"] = {}
            DB["dev_photo_cache"][str(dev_id)] = file_id
            save_db()
        else:
            bot.reply_to(message, dev_text, parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, "⚠️ تعذر جلب معلومات المطور.")


@bot.callback_query_handler(func=lambda c: c.data.startswith("show_dev_photo_"))
def show_dev_photo_callback(call):
    dev_id_str = call.data.replace("show_dev_photo_", "")
    file_id    = DB.get("dev_photo_cache", {}).get(dev_id_str)

    if not file_id:
        bot.answer_callback_query(call.id, "⚠️ الصورة غير متوفرة", show_alert=True)
        return

    try:
        dev_id   = int(dev_id_str)
        dev_info = bot.get_chat(dev_id)
        dev_name = human_name(dev_info)
        dev_bio  = dev_info.bio or "لا يوجد وصف"
        dev_user = dev_info.username
        dev_link = f'<a href="tg://user?id={dev_id}">@{dev_user}</a>' if dev_user else f'<a href="tg://user?id={dev_id}">{dev_name}</a>'

        caption = (
            f"👨‍💻 <b>مطور البوت</b>\n\n"
            f"• الاسم : <b>{dev_name}</b>\n"
            f"• الحساب : {dev_link}\n"
            f"• الوصف : {dev_bio}"
        )

        bot.send_photo(
            call.message.chat.id,
            file_id,
            caption=caption,
            parse_mode="HTML",
            reply_to_message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ حدث خطأ", show_alert=True)


# ========= أمر: سجل القروب =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "سجل القروب" and m.chat.type in ["group","supergroup"])
def show_group_log(message):
    if not is_group(message):
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)

    if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
        return

    log = ensure_event_log(chat_id)
    if not log:
        bot.reply_to(message, "📜 <b>سجل القروب</b>\n\nلا توجد أحداث مسجلة بعد.")
        return

    last_events = log[-15:]
    last_events.reverse()
    txt = "📜 <b>سجل الأحداث — آخر 15 حدث:</b>\n\n"
    for ev in last_events:
        txt += f"• {ev}\n"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= أمر: لوحة الادارة =========
def build_admin_panel_markup(chat_id):
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("👮 الاداريون",        callback_data=f"admpanel_admins_{chat_id}"),
        types.InlineKeyboardButton("⛔ المحظورون",        callback_data=f"admpanel_banned_{chat_id}"),
    )
    m.add(
        types.InlineKeyboardButton("⚠️ الانذارات النشطة", callback_data=f"admpanel_warns_{chat_id}"),
        types.InlineKeyboardButton("🆕 الأعضاء الجدد",   callback_data=f"admpanel_new_{chat_id}"),
    )
    m.add(
        types.InlineKeyboardButton("📊 إحصائيات القروب", callback_data=f"admpanel_stats_{chat_id}"),
        types.InlineKeyboardButton("📜 سجل الأحداث",     callback_data=f"admpanel_log_{chat_id}"),
    )
    m.add(types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"))
    return m

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "لوحة الادارة" and m.chat.type in ["group","supergroup"])
def admin_panel(message):
    if not is_group(message):
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)

    if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
        return

    try:
        chat_info = bot.get_chat(chat_id)
        group_name = chat_info.title or "القروب"
    except:
        group_name = "القروب"

    chat_data = ensure_chat(chat_id)
    total_msgs  = sum(chat_data.get("messages",{}).values())
    total_warns = sum(1 for w in chat_data.get("warnings",{}).values() if w > 0)
    total_banned= sum(1 for r in chat_data.get("restrictions",{}).values() if r.get("banned"))

    txt = (
        f"⚙️ <b>لوحة إدارة : {group_name}</b>\n\n"
        f"• إجمالي الرسائل : <b>{total_msgs:,}</b>\n"
        f"• إنذارات نشطة  : <b>{total_warns}</b>\n"
        f"• محظورون       : <b>{total_banned}</b>\n\n"
        f"اختر من الأزرار أدناه 👇"
    )
    bot.reply_to(message, txt, reply_markup=build_admin_panel_markup(chat_id), parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admpanel_"))
def admin_panel_callback(call):
    user_id = call.from_user.id
    parts   = call.data.split("_")
    # admpanel_[action]_[chat_id]
    action  = parts[1]
    chat_id = int(parts[2])

    role = get_role(chat_id, user_id)
    if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        bot.answer_callback_query(call.id, "⛔ الصلاحية للإداريين فقط.", show_alert=True)
        return

    chat_data = ensure_chat(chat_id)
    back_btn  = types.InlineKeyboardMarkup()
    back_btn.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"admpanel_back_{chat_id}"))

    # ===== رجوع =====
    if action == "back":
        try:
            chat_info  = bot.get_chat(chat_id)
            group_name = chat_info.title or "القروب"
        except:
            group_name = "القروب"
        total_msgs  = sum(chat_data.get("messages",{}).values())
        total_warns = sum(1 for w in chat_data.get("warnings",{}).values() if w > 0)
        total_banned= sum(1 for r in chat_data.get("restrictions",{}).values() if r.get("banned"))
        txt = (
            f"⚙️ <b>لوحة إدارة : {group_name}</b>\n\n"
            f"• إجمالي الرسائل : <b>{total_msgs:,}</b>\n"
            f"• إنذارات نشطة  : <b>{total_warns}</b>\n"
            f"• محظورون       : <b>{total_banned}</b>\n\n"
            f"اختر من الأزرار أدناه 👇"
        )
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=build_admin_panel_markup(chat_id), parse_mode="HTML")
        except: pass
        bot.answer_callback_query(call.id)
        return

    # ===== الاداريون =====
    elif action == "admins":
        ALL_ADMIN_ROLES = ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن"]
        ROLE_EMOJI = {
            "مالك اساسي":"👑","مساعد مالك":"🔰","مالك":"🏅",
            "منشئ":"⭐","مدير":"🛡️","ادمن":"🔷"
        }
        txt = "👮 <b>الاداريون:</b>\n\n"
        found = False
        for r in ALL_ADMIN_ROLES:
            members = chat_data["roles"].get(r, [])
            if r == "مالك اساسي" and chat_data.get("main_owner"):
                members = [chat_data["main_owner"]]
            for uid in members:
                try:
                    mem  = bot.get_chat_member(chat_id, uid).user
                    name = human_name(mem)
                    link = f'<a href="tg://user?id={uid}">{name}</a>'
                except:
                    link = f'<a href="tg://user?id={uid}">{uid}</a>'
                txt += f"{ROLE_EMOJI.get(r,'•')} {link} — <b>{r}</b>\n"
                found = True
        if not found:
            txt += "لا يوجد إداريون مسجلون."
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    # ===== المحظورون =====
    elif action == "banned":
        banned_list = [(uid, data) for uid, data in chat_data.get("restrictions",{}).items()
                       if data.get("banned")]
        txt = f"⛔ <b>المحظورون ({len(banned_list)}):</b>\n\n"
        if not banned_list:
            txt += "لا يوجد أحد محظور حالياً. ✅"
        else:
            for uid_str, _ in banned_list[:20]:
                try:
                    info = bot.get_chat(int(uid_str))
                    name = human_name(info)
                    link = f'<a href="tg://user?id={uid_str}">{name}</a>'
                except:
                    link = f'<a href="tg://user?id={uid_str}">{uid_str}</a>'
                txt += f"• {link}\n"
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    # ===== الانذارات النشطة =====
    elif action == "warns":
        warns_list = [(uid, w) for uid, w in chat_data.get("warnings",{}).items() if w > 0]
        warns_list.sort(key=lambda x: x[1], reverse=True)
        txt = f"⚠️ <b>الانذارات النشطة ({len(warns_list)}):</b>\n\n"
        if not warns_list:
            txt += "لا توجد إنذارات نشطة. ✅"
        else:
            for uid_str, count in warns_list[:20]:
                try:
                    mem  = bot.get_chat_member(chat_id, int(uid_str)).user
                    name = human_name(mem)
                    link = f'<a href="tg://user?id={uid_str}">{name}</a>'
                except:
                    link = f'<a href="tg://user?id={uid_str}">{uid_str}</a>'
                bar = "🔴" * count + "⚪" * (5 - count)
                txt += f"• {link} — {bar} ({count}/5)\n"
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    # ===== الأعضاء الجدد =====
    elif action == "new":
        new_members = chat_data.get("new_members", [])
        txt = f"🆕 <b>آخر الأعضاء المنضمين ({len(new_members)}):</b>\n\n"
        if not new_members:
            txt += "لا توجد بيانات بعد."
        else:
            for i, m_data in enumerate(reversed(new_members[-10:]), 1):
                uid  = m_data["id"]
                name = m_data["name"]
                time = m_data.get("time","")
                link = f'<a href="tg://user?id={uid}">{name}</a>'
                txt += f"{i}. {link} — {time}\n"
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    # ===== إحصائيات القروب =====
    elif action == "stats":
        messages   = chat_data.get("messages", {})
        warnings   = chat_data.get("warnings", {})
        restrictions = chat_data.get("restrictions", {})
        roles      = chat_data.get("roles", {})

        total_active  = len([v for v in messages.values() if v > 0])
        total_msgs    = sum(messages.values())
        total_warns   = sum(1 for w in warnings.values() if w > 0)
        total_banned  = sum(1 for r in restrictions.values() if r.get("banned"))
        total_muted   = sum(1 for r in restrictions.values() if r.get("muted"))
        total_admins  = sum(len(roles.get(r,[])) for r in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"])
        marriages     = sum(len(v) for v in ensure_marriage_system().get("marriages",{}).values())
        new_today     = len(chat_data.get("new_members",[]))

        # أكثر شخص رسائل
        top_user = ""
        if messages:
            top_uid = max(messages, key=messages.get)
            try:
                top_mem = bot.get_chat_member(chat_id, int(top_uid)).user
                top_user = f'<a href="tg://user?id={top_uid}">{human_name(top_mem)}</a> ({messages[top_uid]:,} رسالة)'
            except:
                top_user = f"{top_uid} ({messages.get(top_uid,0):,} رسالة)"

        txt = (
            f"📊 <b>إحصائيات القروب:</b>\n\n"
            f"👥 الأعضاء النشطون : <b>{total_active}</b>\n"
            f"💬 إجمالي الرسائل : <b>{total_msgs:,}</b>\n"
            f"👮 الاداريون : <b>{total_admins}</b>\n"
            f"⛔ المحظورون : <b>{total_banned}</b>\n"
            f"🔇 المكتومون : <b>{total_muted}</b>\n"
            f"⚠️ إنذارات نشطة : <b>{total_warns}</b>\n"
            f"💍 الزيجات : <b>{marriages}</b>\n"
            f"🆕 أعضاء منضمون : <b>{new_today}</b>\n"
        )
        if top_user:
            txt += f"\n🏆 الأكثر تفاعلاً : {top_user}"

        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    # ===== سجل الأحداث =====
    elif action == "log":
        log = ensure_event_log(chat_id)
        if not log:
            txt = "📜 <b>سجل الأحداث</b>\n\nلا توجد أحداث مسجلة بعد."
        else:
            last = list(reversed(log[-15:]))
            txt  = "📜 <b>سجل الأحداث — آخر 15:</b>\n\n"
            for ev in last:
                txt += f"• {ev}\n"
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass

    bot.answer_callback_query(call.id)


# ========= أمر: الاداريون (نصي مباشر) =========
# ملاحظة: هذا الأمر منفصل عن أمر "ادمن" الموجود مسبقاً —
# يعرض قائمة مرتبة مع الرتب والايموجي
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "الاداريون" and m.chat.type in ["group","supergroup"])
def show_admins_fancy(message):
    if not is_group(message): return
    chat_id   = message.chat.id
    chat_data = ensure_chat(chat_id)

    ROLE_EMOJI = {
        "مالك اساسي" : "👑",
        "مساعد مالك" : "🔰",
        "مالك"       : "🏅",
        "منشئ"       : "⭐",
        "مدير"       : "🛡️",
        "ادمن"       : "🔷",
    }
    ORDER = ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير","ادمن"]

    try:
        group_name = bot.get_chat(chat_id).title or "القروب"
    except:
        group_name = "القروب"

    txt = f"⚙️ <b>إداريو {group_name}:</b>\n━━━━━━━━━━━━━━━\n"
    found = False
    for r in ORDER:
        members = chat_data["roles"].get(r, [])
        if r == "مالك اساسي" and chat_data.get("main_owner"):
            members = [chat_data["main_owner"]]
        for uid in members:
            try:
                mem  = bot.get_chat_member(chat_id, uid).user
                if mem.is_bot: continue
                name = human_name(mem)
                link = f'<a href="tg://user?id={uid}">{name}</a>'
            except:
                link = f'<a href="tg://user?id={uid}">{uid}</a>'
            txt += f"{ROLE_EMOJI.get(r,'•')} {link} ← <b>{r}</b>\n"
            found = True

    if not found:
        txt += "لا يوجد إداريون مسجلون."
    txt += "━━━━━━━━━━━━━━━"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= أمر: إنذارات @شخص =========
@bot.message_handler(func=lambda m: m.text and (m.text.strip().startswith("إنذارات") or m.text.strip().startswith("انذاراته")) and m.chat.type in ["group","supergroup"])
def check_user_warns(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)

    if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        bot.reply_to(message, "⛔ هذا الأمر للإداريين فقط.")
        return

    target_id   = None
    target_user = None

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id   = target_user.id
    else:
        parts = message.text.strip().split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            uname = parts[1][1:]
            uid   = find_user_id_by_username(chat_id, uname)
            if uid:
                target_id = uid
                try:
                    target_user = bot.get_chat_member(chat_id, uid).user
                except: pass

    if not target_id:
        bot.reply_to(message, "⛔ استخدم الرد أو <code>إنذارات @يوزر</code>")
        return

    chat_data = ensure_chat(chat_id)
    warns     = chat_data.get("warnings", {}).get(str(target_id), 0)
    name      = human_name(target_user) if target_user else str(target_id)
    link      = f'<a href="tg://user?id={target_id}">{name}</a>'
    bar       = "🔴" * warns + "⚪" * (5 - warns)

    txt = (
        f"⚠️ <b>إنذارات {link}:</b>\n\n"
        f"{bar}\n"
        f"• عدد الانذارات : <b>{warns} / 5</b>\n"
    )
    if warns >= 5:
        txt += "• الحالة : 🔴 <b>تجاوز الحد — تقييد تلقائي</b>"
    elif warns == 0:
        txt += "• الحالة : 🟢 <b>نظيف</b>"
    else:
        txt += f"• الحالة : 🟡 <b>تحت المراقبة</b> ({5-warns} إنذار متبقي)"

    bot.reply_to(message, txt, parse_mode="HTML")


# ========= أمر: رفع كل الانذارات =========
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "رفع كل الانذارات" and m.chat.type in ["group","supergroup"])
def clear_all_warnings(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)

    if role not in ["مالك اساسي","مساعد مالك","مالك"]:
        bot.reply_to(message, "⛔ هذا الأمر للمالك وما فوقه فقط.")
        return

    chat_data = ensure_chat(chat_id)
    count     = sum(1 for w in chat_data.get("warnings",{}).values() if w > 0)

    chat_data["warnings"] = {}
    save_db()
    add_event(chat_id, f"🧹 تم رفع كل الانذارات ({count} إنذار) بواسطة {human_name(message.from_user)}")
    bot.reply_to(message, f"✅ تم رفع جميع الانذارات (<b>{count}</b> إنذار) من كل الأعضاء.", parse_mode="HTML")


# ========= أمر: قوانين =========
@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("قوانين") and m.chat.type in ["group","supergroup"])
def group_rules(message):
    if not is_group(message): return
    chat_id   = message.chat.id
    user_id   = message.from_user.id
    chat_data = ensure_chat(chat_id)
    text      = message.text.strip()

    # تعيين القوانين: "قوانين تعيين [النص]"
    if text.startswith("قوانين تعيين"):
        role = get_role(chat_id, user_id)
        if role not in ["مالك اساسي","مساعد مالك","مالك"]:
            bot.reply_to(message, "⛔ فقط المالك يمكنه تعيين القوانين.")
            return
        new_rules = text.replace("قوانين تعيين", "").strip()
        if not new_rules:
            bot.reply_to(message, "⚠️ أرسل القوانين بعد الأمر.\nمثال: <code>قوانين تعيين 1. احترام الجميع</code>")
            return
        chat_data["group_rules"] = new_rules
        save_db()
        add_event(chat_id, f"📋 تم تحديث قوانين القروب بواسطة {human_name(message.from_user)}")
        bot.reply_to(message, "✅ تم حفظ قوانين القروب بنجاح.")
        return

    # عرض القوانين
    rules = chat_data.get("group_rules")
    if not rules:
        bot.reply_to(message,
            "📋 <b>لا توجد قوانين مضافة بعد.</b>\n\n"
            "للمالك — اكتب:\n<code>قوانين تعيين [نص القوانين]</code>")
        return

    try:
        group_name = bot.get_chat(chat_id).title or "القروب"
    except:
        group_name = "القروب"

    txt = f"📋 <b>قوانين {group_name}:</b>\n\n{rules}"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= أمر: تحذير عام =========
@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("تحذير عام") and m.chat.type in ["group","supergroup"])
def general_warning(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)

    if role not in ["مالك اساسي","مساعد مالك","مالك","منشئ","مدير"]:
        bot.reply_to(message, "⛔ هذا الأمر للمدير وما فوقه.")
        return

    warning_text = message.text.strip().replace("تحذير عام", "").strip()
    if not warning_text:
        bot.reply_to(message, "⚠️ اكتب نص التحذير بعد الأمر.\nمثال: <code>تحذير عام ممنوع الاعلانات</code>")
        return

    sender_name = human_name(message.from_user)
    txt = (
        f"📢 <b>⚠️ تحذير عام من الادارة ⚠️</b>\n\n"
        f"{warning_text}\n\n"
        f"— <b>{sender_name}</b>"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ فهمت", callback_data="warn_understood"))
    bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=markup)
    add_event(chat_id, f"📢 تحذير عام أرسله {sender_name}")


@bot.callback_query_handler(func=lambda c: c.data == "warn_understood")
def warn_understood_callback(call):
    name = human_name(call.from_user)
    bot.answer_callback_query(call.id, f"✅ تمام يا {name}!", show_alert=False)







# ------------------ MERGED OVERRIDES & FIXES (appended to override earlier defs) ------------------
# These functions were added/updated to fix: parse target, mute (DB-only), unmute,
# media guard auto-delete for muted users, unified admin handler for ban/restrict/mute,
# improved money top showing @username with profile button, and improved invest/luck logic.

import random
import time
from telebot import types

def parse_target_from_message(message):
    """
    Returns (target_id:int or None, target_username:str or None, error_msg:str or None)
    Supports: reply, @username, numeric id
    """
    chat_id = message.chat.id
    # reply case
    if getattr(message, 'reply_to_message', None):
        u = message.reply_to_message.from_user
        return u.id, (u.username or None), None

    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) >= 2:
        target = parts[1].strip()
        if target.startswith("@"):
            uname = target[1:]
            # try known users in chat DB
            try:
                uid = find_user_id_by_username(chat_id, uname)
            except:
                uid = None
            if uid:
                return uid, uname, None
            else:
                try:
                    tchat = bot.get_chat("@" + uname)
                    return tchat.id, uname, None
                except Exception:
                    return None, None, "⛔ لم أتمكن من العثور على اليوزر في سجلات البوت أو عبر API."
        if target.isdigit():
            try:
                return int(target), None, None
            except:
                return None, None, "⛔ الـ ID غير صالح."
    return None, None, "⛔ يجب الرد على رسالة المستخدم أو ذكر اليوزر/ID بعد الأمر."

# ========= حذف رسائل المكتومين فوراً =========
@bot.message_handler(func=lambda m: bool(getattr(m, "chat", None)) and m.chat.type in ["group", "supergroup"] and bool(getattr(m, "from_user", None)) and is_user_muted(ensure_chat(m.chat.id), str(m.from_user.id)), content_types=["text","photo","sticker","video","animation","audio","voice","video_note","document","poll"])
def mute_guard(message):
    if not message.chat or message.chat.type not in ["group","supergroup"]:
        return
    chat = ensure_chat(message.chat.id)
    user_id = message.from_user.id
    if is_user_muted(chat, str(user_id)):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

# Unified admin handler (overrides duplicates) for ban/restrict/mute and their lifts.
@bot.message_handler(func=lambda m: m.text and m.chat and m.chat.type in ["group","supergroup"] and any(m.text.startswith(p) for p in ["حظر","رفع الحظر","تقييد","رفع التقييد","كتم","رفع الكتم","رفع القيود"]))
def merged_admin_restrictions_handler(message):
    update_known_user(message)
    text = (message.text or "").strip()
    chat_id = message.chat.id

    # permission check: require actor to be allowed to perform actions
    actor_role = get_role(chat_id, message.from_user.id)
    if actor_role not in ["مدير","منشئ","مالك","مالك اساسي","مساعد مالك","ادمن"]:
        # allow admins to use some commands depending on can_* checks later
        pass

    target_id, target_username, parse_err = parse_target_from_message(message)
    if parse_err:
        bot.reply_to(message, parse_err)
        return

    # try to fetch username if missing
    try:
        member = bot.get_chat_member(chat_id, target_id)
        if not target_username and getattr(member.user, "username", None):
            target_username = member.user.username
    except Exception:
        pass

    if text.startswith("حظر"):
        if not can_ban(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية الحظر.")
            return
        chat_rec = ensure_chat(chat_id)
        if chat_rec.get("restrictions", {}).get(str(target_id), {}).get("banned"):
            bot.reply_to(message, "⚠️ هذا المستخدم محظور أصلاً.")
            return
        ban_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم حظر @{target_username or target_id} بنجاح.")
        return

    if text.startswith("رفع الحظر"):
        if not can_ban(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية رفع الحظر.")
            return
        unban_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم رفع الحظر عن @{target_username or target_id} بنجاح.")
        return

    if text.startswith("تقييد"):
        if not can_restrict(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية التقييد.")
            return
        chat_rec = ensure_chat(chat_id)
        if chat_rec.get("restrictions", {}).get(str(target_id), {}).get("restricted"):
            bot.reply_to(message, "⚠️ هذا المستخدم مقيد أصلاً.")
            return
        restrict_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم تقييد @{target_username or target_id} بنجاح.")
        return

    if text.startswith("رفع التقييد"):
        if not can_restrict(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية رفع التقييد.")
            return
        unrestrict_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم رفع التقييد عن @{target_username or target_id} بنجاح.")
        return

    if text.startswith("كتم"):
        if not can_mute(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية الكتم.")
            return
        chat_rec = ensure_chat(chat_id)
        if chat_rec.get("restrictions", {}).get(str(target_id), {}).get("muted"):
            bot.reply_to(message, "⚠️ هذا المستخدم مكتم أصلاً.")
            return
        mute_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم كتم @{target_username or target_id} بنجاح.")
        return

    if text.startswith("رفع الكتم"):
        if not can_mute(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية رفع الكتم.")
            return
        unmute_user(chat_id, target_id)
        bot.reply_to(message, f"✅ تم رفع الكتم عن @{target_username or target_id} بنجاح.")
        return

    if text.startswith("رفع القيود"):
        if not can_restrict(chat_id, message.from_user.id):
            bot.reply_to(message, "⛔ ليس لديك صلاحية رفع القيود.")
            return
        remove_all_restrictions(chat_id, target_id)
        bot.reply_to(message, f"✅ تم رفع جميع القيود عن @{target_username or target_id} بنجاح.")
        return

# Improved money top for callback usage (also safe if called directly)
def merged_money_top_text_and_markup():
    banking = ensure_banking()
    user_wealth = []
    for user_id_str, user_data in banking["users"].items():
        try:
            user_id = int(user_id_str)
        except:
            continue
        total_wealth = user_data.get("balance", 0)
        for itnm, qty in user_data.get("inventory", {}).items():
            if itnm in ITEMS:
                total_wealth += ITEMS[itnm]["price"] * qty
        username = None
        name = "غير معروف"
        for chat_id, chat_data in DB.items():
            if chat_id.isdigit() and "known_users" in chat_data:
                for uname, uid in chat_data["known_users"].items():
                    if uid == user_id:
                        username = uname
                        break
            if username:
                break
        try:
            user_info = bot.get_chat(user_id)
            name = human_name(user_info)
        except:
            pass
        user_wealth.append({"user_id": user_id, "username": username, "name": name, "wealth": total_wealth})
    user_wealth.sort(key=lambda x: x["wealth"], reverse=True)
    lines = ["🏆 <b>توب أغنى 30 شخص في النظام:</b>\n"]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, user in enumerate(user_wealth[:30]):
        rank = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        display = f"{rank} {user['name']} ({('@'+user['username']) if user['username'] else user['user_id']}) - <b>{user['wealth']: ,} دولار</b>"
        lines.append(display)
        if user['username']:
            markup.add(types.InlineKeyboardButton(f"فتح @{user['username']}", url=f"https://t.me/{user['username']}"))

    stats = f"\\n📈 <b>الاحصائيات:</b>\\n• عدد المستخدمين: {len(user_wealth)}\\n• إجمالي الثروة في النظام: {sum(u['wealth'] for u in user_wealth): ,} دولار\\n"
    return "\\n".join(lines) + stats, markup

# Invest & luck improvements: use proximity to MAX_MONEY and ensure 'all-in' -> zero on loss.
def merged_invest_logic(user, amount):
    bal = user['balance']
    proximity = min(1.0, bal / MAX_MONEY)
    base_win_chance = 70
    win_chance = max(5, int(base_win_chance - proximity * 60))
    max_multiplier = max(1.01, 2.0 - proximity * 1.5)
    multiplier = random.uniform(0.01, max_multiplier)
    roll = random.randint(1,100)
    if roll <= win_chance:
        profit = int(amount * multiplier)
        user['balance'] += profit
        return True, f"📈 استثمار ناجح! ربحت {profit: ,} دولار (×{multiplier:.2f})"
    else:
        loss = int(amount * (1 - multiplier))
        if amount == bal:
            user['balance'] = 0
            return False, "📉 خسرت كل الفلوس! رصيدك الآن 0 دولار"
        else:
            user['balance'] = max(0, user['balance'] - loss)
            return False, f"📉 استثمار فاشل! خسرت {loss: ,} دولار"

def merged_luck_logic(user, amount):
    bal = user['balance']
    proximity = min(1.0, bal / MAX_MONEY)
    base_win_chance = 60
    win_chance = max(5, int(base_win_chance - proximity * 55))
    max_multiplier = max(1.01, 1.5 - proximity * 1.2)
    multiplier = random.uniform(0.01, max_multiplier)
    roll = random.randint(1,100)
    if roll <= win_chance:
        win_amount = int(amount * multiplier)
        user['balance'] += win_amount
        return True, f"🎰 مبروك! فزت بـ {win_amount: ,} دولار (×{multiplier:.2f})"
    else:
        loss = int(amount * (1 - multiplier))
        if amount == bal:
            user['balance'] = 0
            return False, "💔 خسرت كل فلوسك! رصيدك الآن 0 دولار"
        else:
            user['balance'] = max(0, user['balance'] - loss)
            return False, f"💔 خسرت {loss: ,} دولار"


# ========= نظام التصنيف الذهبي =========
def ensure_gold_ranking():
    if "gold_ranking" not in DB:
        DB["gold_ranking"] = {}
    return DB["gold_ranking"]

def process_max_resets():
    while True:
        try:
            banking = ensure_banking()
            gold = ensure_gold_ranking()
            changed = False
            for uid_str, udata in list(banking["users"].items()):
                bal = udata.get("balance", 0)
                if bal >= MAX_MONEY and not udata.get("max_reached_at"):
                    udata["max_reached_at"] = time.time()
                    changed = True
                elif bal >= MAX_MONEY and udata.get("max_reached_at"):
                    if time.time() - udata["max_reached_at"] >= 60:
                        udata["balance"] = 0
                        udata["max_reached_at"] = None
                        gold[uid_str] = gold.get(uid_str, 0) + 50
                        changed = True
                        try:
                            bot.send_message(int(uid_str),
                                "🏆 وصلت الماكس!\n"
                                "💰 تم تصفير رصيدك وحصلت على <b>50 عملة ذهبية 🥇</b>\n"
                                f"إجمالي عملاتك: <b>{gold[uid_str]}</b>"
                            )
                        except:
                            pass
            if changed:
                save_db()
        except:
            pass
        time.sleep(10)

Thread(target=process_max_resets, daemon=True).start()

# ========= دوال مساعدة للتوب =========
# ========= زر توب — callback handlers =========
def ntop_back_markup():
    return build_top_markup()

@bot.callback_query_handler(func=lambda c: c.data.startswith("ntop_"))
def ntop_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    medals = ["🥇","🥈","🥉"]
    num_emojis = ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    back = types.InlineKeyboardMarkup()
    back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="ntop_back"))

    if data == "ntop_back":
        try:
            bot.edit_message_text("📊 <b>اختر التوب:</b>", chat_id, call.message.message_id, reply_markup=build_top_markup())
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    def rank_icon(i):
        if i < 3: return medals[i]
        if i < 10: return num_emojis[i-3]
        return f"{i+1}."

    if data == "ntop_money":
        banking = ensure_banking()
        lst = []
        for uid_str, udata in banking["users"].items():
            bal = udata.get("balance", 0)
            if bal <= 0: continue
            try:
                info = bot.get_chat(int(uid_str))
                name = safe_name_for_top(info)
            except:
                name = None
            if name is None: continue
            lst.append((name, bal))
        lst.sort(key=lambda x: x[1], reverse=True)
        txt = "💰 <b>توب أغنى 30 شخص:</b>\n\n"
        for i, (name, bal) in enumerate(lst[:30]):
            txt += f"{rank_icon(i)} {name} ← <b>{bal:,} دولار</b>\n"
        if not lst:
            txt += "لا يوجد بيانات بعد."

    elif data == "ntop_messages":
        chat = ensure_chat(chat_id)
        lst = sorted(chat["messages"].items(), key=lambda x: x[1], reverse=True)
        txt = "• <b>توب لأكثر 20 متفاعلين في القروب</b>\n\n"
        medals_m = ["🥇","🥈","🥉"]
        for i, (uid, cnt) in enumerate(lst[:20]):
            try:
                mem = bot.get_chat_member(chat_id, int(uid)).user
                name = human_name(mem)
                uid_int = int(uid)
            except:
                name = str(uid)
                uid_int = int(uid)
            r = medals_m[i] if i < 3 else ""
            num = f"{i+1})" if i >= 3 else f"{i+1}){r}"
            if i < 3:
                txt += f"{i+1}){r}  {cnt}  l <a href='tg://user?id={uid_int}'>{name}</a>\n"
            else:
                txt += f"{i+1})  {cnt}  l <a href='tg://user?id={uid_int}'>{name}</a>\n"
        if not lst:
            txt += "لا يوجد بيانات بعد."

    elif data == "ntop_mahr":
        # توب المتزوجين — أعلى مهر
        marriage_system = ensure_marriage_system()
        all_marriages = marriage_system.get("marriages", {})
        lst = []
        for husband_str, wives in all_marriages.items():
            for marriage in wives:
                mahr = marriage.get("mahr", 0)
                wife_id = marriage.get("wife")
                husband_id = int(husband_str)
                lst.append((mahr, husband_id, wife_id))
        lst.sort(key=lambda x: x[0], reverse=True)
        medals_mr = ["🥇","🥈","🥉"]
        txt = f"<b>توب اغنى 10 زوجات بالقروب :</b>\n\n"
        shown = 0
        for mahr, husband_id, wife_id in lst[:10]:
            try:
                h_info = bot.get_chat(husband_id)
                h_name = human_name(h_info)
            except:
                h_name = str(husband_id)
            try:
                w_info = bot.get_chat(wife_id)
                w_name = human_name(w_info)
            except:
                w_name = str(wife_id)
            r = medals_mr[shown] if shown < 3 else f"{shown+1}"
            txt += f"{r} - {mahr:,} 💵 l <a href='tg://user?id={husband_id}'>{h_name}</a>  👫 <a href='tg://user?id={wife_id}'>{w_name}</a>\n"
            shown += 1
        if shown == 0:
            txt += "لا يوجد بيانات."
        txt += "\n ━━━━━━━━━"

    elif data == "ntop_gold":
        gold = DB.get("global_golden", {})
        lst = sorted(gold.items(), key=lambda x: x[1], reverse=True)
        if not lst:
            txt = (
                "🏅 <b>توب تصنيف الذهبي (التصنيف الذهبي)</b>\n\n"
                "━━━━━━━━━━━━━━━\n"
                "💤 لا يوجد أصحاب عملات ذهبية بعد!\n\n"
                "🏆 كيف تحصل على عملات ذهبية؟\n"
                "• وصّل رصيدك للحد الأقصى\n"
                "• انتظر 60 ثانية\n"
                "• رصيدك يتصفر وتحصل <b>50 🥇</b>\n"
                "━━━━━━━━━━━━━━━"
            )
        else:
            medals_g = ["🥇","🥈","🥉"]
            txt = "🏅 <b>توب تصنيف الذهبي</b>\n🌍 من كل القروبات\n\n━━━━━━━━━━━━━━━\n"
            shown = 0
            for uid_str, coins in lst[:20]:
                try:
                    info = bot.get_chat(int(uid_str))
                    name = safe_name_for_top(info)
                    uid_int = int(uid_str)
                except:
                    name = None
                    uid_int = int(uid_str)
                if name is None: continue
                r = medals_g[shown] if shown < 3 else f"{shown+1}"
                txt += f"{r} ) <a href='tg://user?id={uid_int}'>{name}</a> — <b>{coins} عملة ذهبية 🥇</b>\n"
                shown += 1
            txt += f"━━━━━━━━━━━━━━━\n👥 المتنافسين: <b>{shown}</b>"

    elif data == "ntop_rulers":
        txt = "👑 <b>توب الحكام</b>\n\n━━━━━━━━━━━━━━━\n🔧 هذا التوب قيد التطوير.\n━━━━━━━━━━━━━━━"

    elif data == "ntop_battles":
        txt = "💀 <b>بارزات العالمية</b>\n🌍 قريباً...\n\n━━━━━━━━━━━━━━━\n💤 هذا النظام قيد التطوير."

    elif data == "ntop_thieves":
        banking = ensure_banking()
        lst = []
        user_entry = None
        caller_id = call.from_user.id
        for uid_str, udata in banking["users"].items():
            total = udata.get("zarf_total", 0)
            uid_int = int(uid_str)
            try:
                info = bot.get_chat(uid_int)
                name = safe_name_for_top(info)
            except:
                name = None
            if name is None: continue
            if uid_int == caller_id:
                user_entry = (name, total, uid_int)
            if total > 0:
                lst.append((name, total, uid_int))
        lst.sort(key=lambda x: x[1], reverse=True)
        medals_t = ["🥇","🥈","🥉"]
        txt = f"<b>توب اكثر 20 شخص حرامية فلوس:</b>\n\n"
        for i, (name, total, uid_int) in enumerate(lst[:20]):
            r = medals_t[i] if i < 3 else f"{i+1}"
            txt += f"{r} ) {total:,} 💰 l <a href='tg://user?id={uid_int}'>{name}</a>\n"
        if not lst:
            txt += "💤 لا يوجد بيانات بعد!"
        txt += "\n ━━━━━━━━━\n"
        if user_entry:
            u_name, u_total, u_id = user_entry
            u_rank = next((i+1 for i,(n,t,_) in enumerate(lst) if t == u_total and n == u_name), "؟")
            txt += f"• you)  {u_total:,} 💰 l {u_name}"
        else:
            txt += f"• you)  0 💰 l {human_name(call.from_user)}"

    elif data == "ntop_khulaa":
        khulaa = DB.get("global_khulaa", {})
        lst = sorted(khulaa.items(), key=lambda x: x[1], reverse=True)
        medals_k = ["🥇","🥈","🥉"]
        txt = f"<b>توب اكثر 20 مخلوع بالبوت :</b>\n\n"
        shown = 0
        for uid_str, count in lst[:20]:
            uid_int = int(uid_str)
            try:
                info = bot.get_chat(uid_int)
                name = safe_name_for_top(info)
            except:
                name = None
            if name is None: continue
            r = medals_k[shown] if shown < 3 else f"{shown+1}"
            txt += f"{r} ) {count} 🙎🏻‍♂ l <a href='tg://user?id={uid_int}'>{name}</a>\n"
            shown += 1
        if shown == 0:
            txt += "💤 لا يوجد خلع مسجل بعد!"
        txt += "\n ━━━━━━━━━"

    elif data == "ntop_divorces":
        divs = ensure_global_divorces()
        lst = sorted(divs.items(), key=lambda x: x[1], reverse=True)
        medals_d = ["🥇","🥈","🥉"]
        txt = f"<b>توب اكثر 20 مطلقه بالبوت :</b>\n\n"
        shown = 0
        for uid_str, count in lst:
            uid_int = int(uid_str)
            try:
                info = bot.get_chat(uid_int)
                name = safe_name_for_top(info)
            except:
                name = None
            if name is None: continue
            r = medals_d[shown] if shown < 3 else f"{shown+1}"
            txt += f"{r} ) {count} 🙎🏻‍♀ l <a href='tg://user?id={uid_int}'>{name}</a>\n"
            shown += 1
            if shown >= 20: break
        if shown == 0:
            txt += "💤 لا يوجد طلاقات مسجلة بعد!"
        txt += "\n ━━━━━━━━━"

    elif data == "ntop_groups":
        groups_data = ensure_group_messages()
        lst = sorted(groups_data.items(), key=lambda x: x[1], reverse=True)
        medals_gr = ["🥇","🥈","🥉"]
        txt = f"<b>توب اكثر 20 قروب يلعبون :</b>\n\n"
        shown = 0
        for cid_str, total_msgs in lst:
            try:
                info = bot.get_chat(int(cid_str))
                gname = info.title or cid_str
            except:
                gname = cid_str
            r = medals_gr[shown] if shown < 3 else f"{shown+1}"
            txt += f"{r} ) {total_msgs:,}   l  {gname}\n"
            shown += 1
            if shown >= 20: break
        if shown == 0:
            txt += "💤 لا يوجد بيانات بعد!"
        txt += "\n ━━━━━━━━━"

    else:
        bot.answer_callback_query(call.id)
        return

    try:
        bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=back)
    except:
        bot.send_message(chat_id, txt, reply_markup=back)
    bot.answer_callback_query(call.id)





# ================================================================
# إضافات V21.1 — تأكيد مسح الاختصار + أمر العاب + تحديث لوحة الادارة
# ================================================================

# ========= نظام تشغيل/إطفاء الألعاب =========
def ensure_games_settings(chat_id):
    chat = ensure_chat(chat_id)
    if "games_enabled" not in chat:
        chat["games_enabled"] = True
        save_db()
    return chat

def build_games_markup(chat_id):
    chat = ensure_games_settings(chat_id)
    enabled = chat.get("games_enabled", True)
    status  = "✅ مشغلة" if enabled else "❌ مطفأة"
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton(f"✅ تشغيل الألعاب",  callback_data=f"games_on_{chat_id}"))
    m.add(types.InlineKeyboardButton(f"❌ إطفاء الألعاب",  callback_data=f"games_off_{chat_id}"))
    m.add(types.InlineKeyboardButton("❌ اغلاق",           callback_data="close_panel"))
    return m, status

@bot.message_handler(func=lambda m: m.text and m.text.strip() == "العاب" and m.chat.type in ["group","supergroup"])
def games_panel_cmd(message):
    if not is_group(message): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    role    = get_role(chat_id, user_id)
    if role not in ["مدير","منشئ","مالك","مساعد مالك","مالك اساسي"]:
        bot.reply_to(message, "⛔ هذا الأمر للمدير وما فوقه.")
        return
    chat = ensure_games_settings(chat_id)
    enabled = chat.get("games_enabled", True)
    status  = "✅ مشغلة" if enabled else "❌ مطفأة"
    markup, _ = build_games_markup(chat_id)
    bot.reply_to(message,
        f"🎮 <b>إعدادات الألعاب</b>\n\nالحالة الحالية: <b>{status}</b>\n\n"
        f"الألعاب المتأثرة: كت، انق، حظ فلوسي",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("games_on_") or c.data.startswith("games_off_"))
def games_toggle_callback(call):
    user_id  = call.from_user.id
    data     = call.data
    chat_id  = call.message.chat.id
    parts    = data.split("_")
    action   = parts[1]
    cid      = int(parts[2])
    role     = get_role(cid, user_id)
    if role not in ["مدير","منشئ","مالك","مساعد مالك","مالك اساسي"]:
        bot.answer_callback_query(call.id, "⛔ مخصص للمدير وما فوقه.", show_alert=True)
        return
    chat = ensure_games_settings(cid)
    if action == "on":
        chat["games_enabled"] = True
        save_db()
        add_event(cid, f"🎮 تم تشغيل الألعاب — {human_name(call.from_user)}")
        status = "✅ مشغلة"
        bot.answer_callback_query(call.id, "✅ تم تشغيل الألعاب!")
    else:
        chat["games_enabled"] = False
        save_db()
        add_event(cid, f"🎮 تم إطفاء الألعاب — {human_name(call.from_user)}")
        status = "❌ مطفأة"
        bot.answer_callback_query(call.id, "❌ تم إطفاء الألعاب!")
    markup, _ = build_games_markup(cid)
    try:
        bot.edit_message_text(
            f"🎮 <b>إعدادات الألعاب</b>\n\nالحالة الحالية: <b>{status}</b>\n\n"
            f"الألعاب المتأثرة: كت، انق، حظ فلوسي",
            chat_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except: pass


# ========= تحديث لوحة الادارة بإضافة زري الاختصارات والألعاب =========
def build_admin_panel_markup(chat_id):
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("👮 الاداريون",         callback_data=f"admpanel_admins_{chat_id}"),
        types.InlineKeyboardButton("⛔ المحظورون",         callback_data=f"admpanel_banned_{chat_id}"),
    )
    m.add(
        types.InlineKeyboardButton("⚠️ الانذارات النشطة", callback_data=f"admpanel_warns_{chat_id}"),
        types.InlineKeyboardButton("🆕 الأعضاء الجدد",    callback_data=f"admpanel_new_{chat_id}"),
    )
    m.add(
        types.InlineKeyboardButton("📊 إحصائيات القروب",  callback_data=f"admpanel_stats_{chat_id}"),
        types.InlineKeyboardButton("📜 سجل الأحداث",      callback_data=f"admpanel_log_{chat_id}"),
    )
    m.add(
        types.InlineKeyboardButton("⚡ الاختصارات",        callback_data=f"admpanel_shortcuts_{chat_id}"),
        types.InlineKeyboardButton("🎮 الألعاب",           callback_data=f"admpanel_games_{chat_id}"),
    )
    m.add(types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"))
    return m


# ========= معالجة admpanel_shortcuts و admpanel_games داخل handle_callback =========
# هذه الأكواد تضاف داخل admin_panel_callback الموجود
# لكن بما أن handle_callback يمسك كل شيء، نضيف handler مستقل

@bot.callback_query_handler(func=lambda c: c.data.startswith("admpanel_shortcuts_") or c.data.startswith("admpanel_games_"))
def admpanel_extra_callback(call):
    user_id = call.from_user.id
    data    = call.data
    chat_id = call.message.chat.id
    parts   = data.split("_")

    if data.startswith("admpanel_shortcuts_"):
        cid  = int(parts[2])
        role = get_role(cid, user_id)
        if role not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
            bot.answer_callback_query(call.id, "⛔ للإداريين فقط.", show_alert=True)
            return
        shortcuts = ensure_shortcuts(cid)
        back_btn  = types.InlineKeyboardMarkup()
        back_btn.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"admpanel_back_{cid}"))
        if not shortcuts:
            txt = "⚡ <b>الاختصارات</b>\n\nلا يوجد اختصارات بعد."
        else:
            txt = f"⚡ <b>الاختصارات ({len(shortcuts)}):</b>\n\n"
            for sh, orig in shortcuts.items():
                txt += f"• <code>{sh}</code> ← <b>{orig}</b>\n"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id,
                                  reply_markup=back_btn, parse_mode="HTML")
        except: pass
        bot.answer_callback_query(call.id)

    elif data.startswith("admpanel_games_"):
        cid  = int(parts[2])
        role = get_role(cid, user_id)
        if role not in ["مدير","منشئ","مالك","مساعد مالك","مالك اساسي"]:
            bot.answer_callback_query(call.id, "⛔ للمدير وما فوقه.", show_alert=True)
            return
        chat    = ensure_games_settings(cid)
        enabled = chat.get("games_enabled", True)
        status  = "✅ مشغلة" if enabled else "❌ مطفأة"
        back_btn = types.InlineKeyboardMarkup(row_width=1)
        back_btn.add(types.InlineKeyboardButton("✅ تشغيل الألعاب", callback_data=f"games_on_{cid}"))
        back_btn.add(types.InlineKeyboardButton("❌ إطفاء الألعاب", callback_data=f"games_off_{cid}"))
        back_btn.add(types.InlineKeyboardButton("🔙 رجوع",          callback_data=f"admpanel_back_{cid}"))
        try:
            bot.edit_message_text(
                f"🎮 <b>إعدادات الألعاب</b>\n\nالحالة: <b>{status}</b>\n\nالألعاب المتأثرة: كت، انق، حظ فلوسي",
                chat_id, call.message.message_id, parse_mode="HTML", reply_markup=back_btn)
        except: pass
        bot.answer_callback_query(call.id)


# ========= فحص الألعاب قبل تشغيلها =========
# أضف هذا الفحص في كل لعبة (كت، انق، حظ فلوسي)
def games_allowed(chat_id):
    chat = ensure_chat(chat_id)
    return chat.get("games_enabled", True)


# ================================================================
# 🧙 لعبة السحرة — نظام استنتاج اجتماعي كامل (نمط الذئب/مافيا)
# ================================================================
import threading
from collections import Counter

WZ_MIN_PLAYERS   = 3     # الحد الأدنى للاعبين حتى تبدأ المباراة
WZ_REG_SECONDS   = 60    # مدة التسجيل
WZ_PHASE_SECONDS = 45    # مدة الليل / النقاش / التصويت
WZ_MAX_GROUPS_SHOWN = 30

WZ_ROLES_INFO = {
    "الساحر الأسود": {"emoji": "🧙", "team": "evil",
        "desc": "يختار كل ليلة ضحية ليقتلها"},
    "الساحر الأبيض": {"emoji": "✨", "team": "good",
        "desc": "يملك جرعة شفاء واحدة طوال اللعبة يحمي فيها أي لاعب من الموت"},
    "العراف":        {"emoji": "🔮", "team": "good",
        "desc": "يكشف كل ليلة إذا كان لاعب معيّن شريراً أو بريئاً"},
    "الحارس":        {"emoji": "🛡", "team": "good",
        "desc": "يحمي كل ليلة لاعباً من القتل (لا يقدر يحمي نفس الشخص ليلتين متتاليتين)"},
    "الفلاح":        {"emoji": "🌿", "team": "good",
        "desc": "لا يملك قدرة خاصة، لكن صوته بالتصويت مهم جداً"},
}

WIZARD_GAMES = {}        # chat_id(int) -> game dict (حالة حية بالذاكرة)
WIZARD_USER_ACTIVE = {}  # user_id(int) -> chat_id المباراة اللي هوه منضم/يلعب فيها حالياً


def wz_new_game(chat_id, creator_id):
    return {
        "chat_id": chat_id,
        "creator_id": creator_id,
        "phase": "registering",     # registering / night / day / voting / ended
        "players": {},               # user_id -> {name, username, role, alive}
        "round": 1,
        "night_actions": {},         # action_key -> {actor_id: target_id}
        "guard_last_target": None,
        "white_used": False,
        "votes": {},                  # voter_id -> target_id
        "lock": threading.Lock(),
        "resolved_flags": set(),      # لمنع تنفيذ نفس المرحلة مرتين (سباق التايمر مع الاكتمال المبكر)
    }


def wz_build_roles(n):
    evil_count = max(1, n // 4)
    roles = ["الساحر الأسود"] * evil_count
    remaining = n - evil_count
    specials = []
    if remaining >= 1:
        specials.append("العراف")
    if n >= 6 and remaining >= 2:
        specials.append("الحارس")
    if n >= 9 and remaining >= 3:
        specials.append("الساحر الأبيض")
    roles += specials
    roles += ["الفلاح"] * (n - len(roles))
    random.shuffle(roles)
    return roles


def wz_alive_players(game):
    return {pid: p for pid, p in game["players"].items() if p["alive"]}


def wz_mention(pid, name):
    return f'<a href="tg://user?id={pid}">{name}</a>'


def wz_roster_text(game):
    lines = []
    for pid, p in game["players"].items():
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        lines.append(f"{wz_mention(pid, p['name'])} — {status}")
    return "👥 <b>اللاعبون:</b>\n" + "\n".join(lines)


def wz_cleanup_game(chat_id):
    game = WIZARD_GAMES.pop(chat_id, None)
    if game:
        for pid in list(game["players"].keys()):
            if WIZARD_USER_ACTIVE.get(pid) == chat_id:
                WIZARD_USER_ACTIVE.pop(pid, None)
    return game


# ========= إحصائيات اللاعبين =========
def wz_ensure_stats():
    if "wizard_stats" not in DB:
        DB["wizard_stats"] = {}
        save_db()
    return DB["wizard_stats"]


def wz_get_stats(user_id, name=None):
    stats = wz_ensure_stats()
    sid = str(user_id)
    if sid not in stats:
        stats[sid] = {"name": name or "لاعب", "games": 0, "wins": 0, "xp": 0, "role_counts": {}}
        save_db()
    if name:
        stats[sid]["name"] = name
    return stats[sid]


def wz_level_for_xp(xp):
    return 1 + xp // 50


def wz_add_result(user_id, name, role, won):
    s = wz_get_stats(user_id, name)
    s["games"] += 1
    if won:
        s["wins"] += 1
        s["xp"] += 10
    else:
        s["xp"] += 4
    s["role_counts"][role] = s["role_counts"].get(role, 0) + 1
    save_db()


def wz_stats_text(user_id, name):
    s = wz_get_stats(user_id, name)
    games = s["games"]
    wins = s["wins"]
    winrate = round((wins / games) * 100, 1) if games else 0.0
    best_role = "لا يوجد بعد"
    if s["role_counts"]:
        best_role = max(s["role_counts"].items(), key=lambda x: x[1])[0]
        best_role = f"{WZ_ROLES_INFO.get(best_role, {}).get('emoji','🎭')} {best_role}"
    lvl = wz_level_for_xp(s["xp"])
    return (
        f"🧙 <b>إحصائيات {name} بلعبة السحرة</b>\n\n"
        f"🎮 عدد المباريات: <b>{games}</b>\n"
        f"🏆 عدد الانتصارات: <b>{wins}</b>\n"
        f"📈 نسبة الفوز: <b>{winrate}%</b>\n"
        f"⭐ المستوى: <b>{lvl}</b>\n"
        f"💎 نقاط الخبرة: <b>{s['xp']}</b>\n"
        f"🥇 أفضل دور: <b>{best_role}</b>"
    )


@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["احصائيات السحرة", "سحرة احصائياتي"])
def wz_my_stats_cmd(message):
    name = human_name(message.from_user)
    bot.reply_to(message, wz_stats_text(message.from_user.id, name), parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب السحرة")
def wz_top_cmd(message):
    stats = wz_ensure_stats()
    lst = sorted(list(stats.items()), key=lambda x: x[1].get("wins", 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    txt = "🧙 <b>توب أفضل 10 سحرة (الأكثر فوزاً):</b>\n\n"
    if not lst:
        txt += "💤 لا يوجد بيانات بعد!"
    for i, (uid_str, sd) in enumerate(lst):
        rank = medals[i] if i < 3 else f"{i+1} )"
        txt += f"{rank} {sd.get('name','لاعب')} — 🏆 {sd.get('wins',0)} فوز من {sd.get('games',0)} مباراة\n"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= القائمة الرئيسية للعبة (بالخاص) =========
@bot.callback_query_handler(func=lambda c: c.data == "wz_menu")
def wz_menu_callback(call):
    try:
        _wz_menu_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[wz_menu_callback error] {e}")
        except:
            pass


def _wz_tg_retry(func, *args, retries=2, delay=0.4, **kwargs):
    """يعيد المحاولة مرة إضافية إذا صار خطأ مؤقت (شبكة/تأخير من تليجرام) بدل ما يستسلم فوراً."""
    last_exc = None
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if i < retries - 1:
                time.sleep(delay)
    raise last_exc


def _wz_menu_callback_inner(call):
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "🧙 هذه الميزة تعمل بالخاص فقط.", show_alert=True)
        return
    user_id = call.from_user.id
    uid_str = str(user_id)
    candidate_groups = []
    for sid in list(DB.keys()):
        if not (sid.lstrip("-").isdigit()):
            continue
        cid = int(sid)
        if cid > 0:
            continue  # القروبات إيديها سالبة
        chat = DB.get(sid)
        if not isinstance(chat, dict):
            continue
        known = chat.get("wz_active_members") or {}

        if uid_str in known:
            # ===== المصدر السريع: سجل النشاط يثبت إنك كتبت شي بهذا القروب من قبل =====
            title = chat.get("title") or sid
        else:
            # ما لقينا نشاط مسجل لك أنت تحديداً بهذا القروب (حتى لو غيرك مسجلين) → فحص حي احتياطي
            try:
                member = _wz_tg_retry(bot.get_chat_member, cid, user_id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception:
                continue
            # أكّدنا عضويتك الآن، نسجلك بالسجل حتى تصير المرات الجاية أسرع
            chat.setdefault("wz_active_members", {})[uid_str] = True
            save_db()
            try:
                info = _wz_tg_retry(bot.get_chat, cid)
                title = info.title or sid
                chat["title"] = title
            except Exception:
                title = chat.get("title") or sid

        candidate_groups.append((cid, title))
        if len(candidate_groups) >= WZ_MAX_GROUPS_SHOWN:
            break

    if not candidate_groups:
        no_groups_txt = (
            "🧙 <b>لعبة السحرة</b>\n\n"
            "ما لقيت أي قروب مشترك بيني وبينك تكدر تسوي فيه مباراة.\n"
            "تأكد إنك عضو بقروب مضاف فيه البوت، وجرب تكتب أي رسالة بذاك القروب."
        )
        edited = False
        try:
            bot.edit_message_text(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(call.message.chat.id, no_groups_txt, parse_mode="HTML")
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return

    m = types.InlineKeyboardMarkup(row_width=1)
    for cid, title in candidate_groups:
        m.add(types.InlineKeyboardButton(f"🏰 {title}", callback_data=f"wz_create_{cid}"))
    m.add(types.InlineKeyboardButton("❌ اغلاق", callback_data="close_panel"))
    choose_txt = "🧙 <b>لعبة السحرة</b>\n\nاختر القروب اللي تبي تسوي فيه المباراة:"
    edited = False
    try:
        bot.edit_message_text(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
        edited = True
    except Exception:
        pass
    if not edited:
        try:
            bot.edit_message_caption(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
            edited = True
        except Exception:
            pass
    if not edited:
        try:
            bot.send_message(call.message.chat.id, choose_txt, parse_mode="HTML", reply_markup=m)
        except Exception:
            pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("wz_create_"))
def wz_create_callback(call):
    try:
        _wz_create_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[wz_create_callback error] {e}")
        except:
            pass


def _wz_create_callback_inner(call):
    user_id = call.from_user.id
    chat_id = int(call.data.split("_", 2)[2])

    if WIZARD_USER_ACTIVE.get(user_id) is not None:
        bot.answer_callback_query(call.id, "⛔ أنت منضم بمباراة أخرى حالياً، خلّص منها أول.", show_alert=True)
        return
    if not games_allowed(chat_id):
        bot.answer_callback_query(call.id, "⛔ الألعاب مطفأة بهذا القروب حالياً.", show_alert=True)
        return
    if chat_id in WIZARD_GAMES:
        bot.answer_callback_query(call.id, "🧙 يوجد مباراة قائمة فعلاً بهذا القروب.", show_alert=True)
        return

    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status not in ("member", "administrator", "creator"):
            bot.answer_callback_query(call.id, "⛔ لازم تكون عضو بهذا القروب.", show_alert=True)
            return
    except:
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أتأكد من عضويتك بالقروب.", show_alert=True)
        return

    game = wz_new_game(chat_id, user_id)
    creator_name = human_name(call.from_user)
    game["players"][user_id] = {"name": creator_name, "username": call.from_user.username, "role": None, "alive": True}
    WIZARD_USER_ACTIVE[user_id] = chat_id
    WIZARD_GAMES[chat_id] = game

    join_markup = types.InlineKeyboardMarkup(row_width=1)
    join_markup.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=wzjoin_{chat_id}"))

    txt = wz_registration_text(game)
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=join_markup)
    except Exception:
        wz_cleanup_game(chat_id)
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أرسل رسالة بالقروب (تأكد إن البوت مو مطرود).", show_alert=True)
        return

    bot.answer_callback_query(call.id, "✅ تم إنشاء المباراة! افتح القروب.")
    confirm_txt = "✅ تم إنشاء مباراة لعبة السحرة بالقروب، شوف رسالة الانضمام هناك."
    try:
        bot.edit_message_text(confirm_txt, call.message.chat.id, call.message.message_id)
    except Exception:
        try:
            bot.edit_message_caption(confirm_txt, call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    Thread(target=wz_registration_timer, args=(chat_id,), daemon=True).start()


def wz_registration_text(game):
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    return (
        "🧙 <b>تم إنشاء لعبة السحرة.</b>\n\n"
        f"⏳ يبدأ التسجيل لمدة {WZ_REG_SECONDS} ثانية.\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}\n{players_txt}"
    )


def wz_join_markup(chat_id):
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=wzjoin_{chat_id}"))
    return m


def wz_announce_join(chat_id, joined_pid, joined_name):
    """يرسل رسالة جديدة بكل مرة ينضم فيها لاعب، فيها اسم المنضم الجديد + قائمة اللاعبين الحالية"""
    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    txt = (
        f"✅ انضم {wz_mention(joined_pid, joined_name)} إلى اللعبة!\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}\n{players_txt}"
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=wz_join_markup(chat_id))
    except:
        pass


def wz_handle_deeplink_join(message, payload):
    """يعالج فتح الخاص عبر رابط الانضمام https://t.me/<bot>?start=wzjoin_<chat_id>"""
    try:
        chat_id = int(payload.split("_", 1)[1])
    except Exception:
        return
    user = message.from_user
    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        bot.send_message(message.chat.id, "⏰ انتهى وقت التسجيل أو ما فيه مباراة قائمة حالياً بهذا القروب.")
        return
    if user.id in game["players"]:
        bot.send_message(message.chat.id, "✅ أنت مسجل بالفعل بهذه المباراة، انتظر بدء اللعب بالقروب.")
        return
    active_chat = WIZARD_USER_ACTIVE.get(user.id)
    if active_chat is not None and active_chat != chat_id:
        bot.send_message(message.chat.id, "⛔ أنت منضم بمباراة أخرى حالياً، لازم تخلّص منها أول.")
        return
    name = human_name(user)
    game["players"][user.id] = {"name": name, "username": user.username, "role": None, "alive": True}
    WIZARD_USER_ACTIVE[user.id] = chat_id
    bot.send_message(message.chat.id, "✅ تم تسجيلك بنجاح.\n🧙 انتظر بدء المباراة بالقروب.")
    wz_announce_join(chat_id, user.id, name)


def wz_registration_timer(chat_id):
    time.sleep(WZ_REG_SECONDS)
    wz_finish_registration(chat_id)


def wz_finish_registration(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    with game["lock"]:
        if game["phase"] != "registering":
            return
        if len(game["players"]) < WZ_MIN_PLAYERS:
            game["phase"] = "ended"
            try:
                bot.send_message(chat_id,
                    f"❌ <b>تم إلغاء المباراة</b>\nلم يكتمل الحد الأدنى للاعبين ({WZ_MIN_PLAYERS}).",
                    parse_mode="HTML")
            except:
                pass
            wz_cleanup_game(chat_id)
            return
        # الأدوار توزّع من جديد بشكل عشوائي كل جولة (داخل wz_start_night)
        game["phase"] = "night"

    try:
        bot.send_message(chat_id,
            f"🌙 <b>اكتمل التسجيل!</b>\nعدد اللاعبين: {len(game['players'])}\n\nبدأت المباراة الآن...",
            parse_mode="HTML")
    except:
        pass

    wz_start_night(chat_id)


# ========= مرحلة الليل =========
def wz_night_markup(chat_id, round_no, action_key, actor_id, exclude_self=True, exclude_pid=None):
    game = WIZARD_GAMES[chat_id]
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in wz_alive_players(game).items():
        if exclude_self and pid == actor_id:
            continue
        if exclude_pid is not None and pid == exclude_pid:
            continue
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"wz_act_{action_key}_{chat_id}_{round_no}_{pid}"))
    return m


def wz_start_night(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "night"
    game["night_actions"] = {}
    rnd = game["round"]

    # ===== إعادة توزيع الأدوار عشوائياً على اللاعبين الأحياء كل جولة =====
    alive_ids = list(wz_alive_players(game).keys())
    new_roles = wz_build_roles(len(alive_ids))
    random.shuffle(alive_ids)
    for pid, role in zip(alive_ids, new_roles):
        game["players"][pid]["role"] = role
    game["guard_last_target"] = None  # الحارس يتغيّر كل جولة، فما فيه داعي لتقييد نفس الهدف

    for pid, p in wz_alive_players(game).items():
        role = p["role"]
        info = WZ_ROLES_INFO[role]
        role_reveal = f"🎭 <b>دورك هذي الجولة:</b>\n{info['emoji']} <b>{role}</b>\n{info['desc']}"
        if role == "الساحر الأسود":
            markup = wz_night_markup(chat_id, rnd, "kill", pid, exclude_self=True)
            text = "🧙 اختر ضحيتك الليلة:"
        elif role == "العراف":
            markup = wz_night_markup(chat_id, rnd, "see", pid, exclude_self=True)
            text = "🔮 اختر لاعباً لتكشف حقيقته:"
        elif role == "الحارس":
            markup = wz_night_markup(chat_id, rnd, "guard", pid, exclude_self=False,
                                      exclude_pid=game.get("guard_last_target"))
            text = "🛡 اختر لاعباً لتحميه الليلة:"
        elif role == "الساحر الأبيض" and not game.get("white_used"):
            markup = wz_night_markup(chat_id, rnd, "heal", pid, exclude_self=False)
            text = "✨ اختر لاعباً تحميه بجرعتك السحرية (استخدام واحد طوال اللعبة):"
        else:
            markup = None
            text = None

        try:
            if markup is not None and markup.keyboard:
                bot.send_message(pid, f"🌙 <b>حل الليل...</b>\n\n{role_reveal}\n\n{text}",
                                  parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(pid, f"🌙 <b>حل الليل...</b>\n\n{role_reveal}\n\nما عندك قدرة هذي الجولة، انتظر النتيجة.",
                                  parse_mode="HTML")
        except:
            pass

    try:
        bot.send_message(chat_id,
            "🌙 <b>حل الليل...</b>\nيرجى انتظار انتهاء جميع الشخصيات من تنفيذ قدراتها.",
            parse_mode="HTML")
    except:
        pass

    Thread(target=wz_night_timer, args=(chat_id, rnd), daemon=True).start()


def wz_night_timer(chat_id, rnd):
    time.sleep(WZ_PHASE_SECONDS)
    game = WIZARD_GAMES.get(chat_id)
    if game and game["phase"] == "night" and game["round"] == rnd:
        wz_resolve_night(chat_id)


def wz_expected_night_actors(game):
    """يرجع مجموعة (action_key, actor_id) المتوقع نستلم منها فعل الليلة"""
    expected = set()
    for pid, p in wz_alive_players(game).items():
        role = p["role"]
        if role == "الساحر الأسود":
            expected.add(("kill", pid))
        elif role == "العراف":
            expected.add(("see", pid))
        elif role == "الحارس":
            expected.add(("guard", pid))
        elif role == "الساحر الأبيض" and not game.get("white_used"):
            expected.add(("heal", pid))
    return expected


def wz_check_night_complete(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "night":
        return
    expected = wz_expected_night_actors(game)
    done = set()
    for action_key, actors in game["night_actions"].items():
        for actor_id in actors.keys():
            done.add((action_key, actor_id))
    if expected and expected.issubset(done):
        wz_resolve_night(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("wz_act_"))
def wz_act_callback(call):
    try:
        parts = call.data.split("_")
        action_key = parts[2]
        chat_id = int(parts[3])
        rnd = int(parts[4])
        target = int(parts[5])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "night" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهت هذه المرحلة.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "لا يمكنك التصرف الآن.", show_alert=True)
        return

    game["night_actions"].setdefault(action_key, {})[user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل اختيارك.")
    try:
        bot.edit_message_text("✅ تم تسجيل اختيارك، انتظر نتيجة الليلة.", call.message.chat.id, call.message.message_id)
    except:
        pass

    wz_check_night_complete(chat_id)


def wz_check_win(game):
    alive = wz_alive_players(game)
    evil_alive = [p for p in alive.values() if p["role"] == "الساحر الأسود"]
    good_alive = [p for p in alive.values() if p["role"] != "الساحر الأسود"]
    if len(evil_alive) == 0:
        return "good"
    if len(evil_alive) >= len(good_alive):
        return "evil"
    return None


def wz_resolve_night(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "night":
            return
        game["phase"] = "resolving"

    actions = game["night_actions"]

    guard_targets = list(actions.get("guard", {}).values())
    guard_target = guard_targets[0] if guard_targets else None
    game["guard_last_target"] = guard_target

    heal_targets = list(actions.get("heal", {}).values())
    heal_target = heal_targets[0] if heal_targets else None
    if heal_target is not None:
        game["white_used"] = True

    kill_votes = list(actions.get("kill", {}).values())
    victim = None
    if kill_votes:
        tally = Counter(kill_votes)
        top = tally.most_common()
        maxvotes = top[0][1]
        candidates = [t for t, c in top if c == maxvotes]
        victim = random.choice(candidates)

    saved = victim is not None and (victim == guard_target or victim == heal_target)

    if victim is not None and not saved:
        game["players"][victim]["alive"] = False
        vname = game["players"][victim]["name"]
        vrole = game["players"][victim]["role"]
        vinfo = WZ_ROLES_INFO[vrole]
        black_info = WZ_ROLES_INFO["الساحر الأسود"]
        story = (f"🌙 <b>قصة الليلة:</b>\n"
                 f"قام {black_info['emoji']} <b>الساحر الأسود</b> بقتل {vinfo['emoji']} <b>{vrole}</b>!")
        death_text = f"{story}\n\n💀 القتيل: {wz_mention(victim, vname)}"
    elif victim is not None and saved:
        death_text = ("🌙 <b>قصة الليلة:</b>\n"
                       "حاول 🧙 الساحر الأسود قتل أحدهم الليلة، لكن تم إنقاذه في اللحظة الأخيرة! ✨")
    else:
        death_text = "🌙 <b>قصة الليلة:</b>\nمرّت الليلة بهدوء، لم يمت أحد."

    # نتائج العرّاف
    for actor_id, target in actions.get("see", {}).items():
        actor = game["players"].get(actor_id)
        if not actor or not actor["alive"]:
            continue
        t = game["players"].get(target)
        if not t:
            continue
        is_evil = t["role"] == "الساحر الأسود"
        result = "🔴 شرير! احذر منه" if is_evil else "🟢 بريء"
        try:
            bot.send_message(actor_id, f"🔮 نتيجة كشفك عن {t['name']}:\n{result}", parse_mode="HTML")
        except:
            pass

    game["night_actions"] = {}

    winner = wz_check_win(game)
    if winner:
        wz_end_game(chat_id, winner, death_text)
        return

    game["phase"] = "day"
    try:
        bot.send_message(chat_id,
            f"☀ <b>أشرق الصباح...</b>\n\n{death_text}\n\n{wz_roster_text(game)}\n\n"
            f"💬 وقت النقاش: {WZ_PHASE_SECONDS} ثانية",
            parse_mode="HTML")
    except:
        pass

    Thread(target=wz_discussion_timer, args=(chat_id, game["round"]), daemon=True).start()


def wz_discussion_timer(chat_id, rnd):
    time.sleep(WZ_PHASE_SECONDS)
    game = WIZARD_GAMES.get(chat_id)
    if game and game["phase"] == "day" and game["round"] == rnd:
        wz_start_voting(chat_id)


# ========= مرحلة التصويت =========
def wz_voting_text(game):
    tally = Counter(game["votes"].values())
    lines = []
    for pid, p in wz_alive_players(game).items():
        lines.append(f"• {p['name']} — {tally.get(pid, 0)} صوت")
    return "🗳 <b>وقت التصويت!</b>\nصوّت لطرد أحد اللاعبين المشتبه بهم:\n\n" + "\n".join(lines)


def wz_start_voting(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "voting"
    game["votes"] = {}
    rnd = game["round"]

    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in wz_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"wz_vote_{chat_id}_{rnd}_{pid}"))

    try:
        bot.send_message(chat_id, wz_voting_text(game), parse_mode="HTML", reply_markup=m)
    except:
        pass

    Thread(target=wz_voting_timer, args=(chat_id, rnd), daemon=True).start()


def wz_voting_timer(chat_id, rnd):
    time.sleep(WZ_PHASE_SECONDS)
    game = WIZARD_GAMES.get(chat_id)
    if game and game["phase"] == "voting" and game["round"] == rnd:
        wz_resolve_voting(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("wz_vote_"))
def wz_vote_callback(call):
    try:
        parts = call.data.split("_")
        chat_id = int(parts[2])
        rnd = int(parts[3])
        target = int(parts[4])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = WIZARD_GAMES.get(chat_id)
    if not game or game["phase"] != "voting" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهى وقت التصويت.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "⛔ ما تكدر تصوّت (غير حي أو مو منضم).", show_alert=True)
        return

    game["votes"][user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل صوتك.")
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in wz_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"wz_vote_{chat_id}_{rnd}_{pid}"))
    try:
        bot.send_message(chat_id,
            f"🗳 صوّت {wz_mention(user_id, player['name'])}!\n\n{wz_voting_text(game)}",
            parse_mode="HTML", reply_markup=m)
    except:
        pass

    if len(game["votes"]) >= len(wz_alive_players(game)):
        wz_resolve_voting(chat_id)


def wz_resolve_voting(chat_id):
    game = WIZARD_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "voting":
            return
        game["phase"] = "resolving"

    tally = Counter(game["votes"].values())
    result_text = ""
    if tally:
        top = tally.most_common()
        maxvotes = top[0][1]
        candidates = [t for t, c in top if c == maxvotes]
        if len(candidates) == 1:
            eliminated = candidates[0]
            game["players"][eliminated]["alive"] = False
            ename = game["players"][eliminated]["name"]
            erole = game["players"][eliminated]["role"]
            einfo = WZ_ROLES_INFO[erole]
            result_text = (
                f"🗳 <b>قصة التصويت:</b>\n"
                f"اجتمع القرويون وقرروا طرد {wz_mention(eliminated, ename)} من بينهم!\n\n"
                f"⚖️ كان دوره: {einfo['emoji']} <b>{erole}</b>"
            )
        else:
            result_text = (
                "🗳 <b>قصة التصويت:</b>\n"
                "تعادلت الأصوات بين أكثر من شخص، فقرر القرويون تأجيل الحكم لهذي المرة.\n\n"
                "🤝 لم يُطرد أحد."
            )
    else:
        result_text = (
            "🗳 <b>قصة التصويت:</b>\n"
            "ساد الصمت بين القرويين، محد جرؤ يصوّت أو يتّهم أحد.\n\n"
            "💤 لم يُطرد أحد، والليلة الجاية بتكشف المزيد..."
        )

    winner = wz_check_win(game)
    if winner:
        wz_end_game(chat_id, winner, result_text)
        return

    game["round"] += 1
    game["phase"] = "night"  # مؤقت لحد ما نرسل رسالة النتيجة
    try:
        bot.send_message(chat_id, f"{result_text}\n\n{wz_roster_text(game)}",
                          parse_mode="HTML")
    except:
        pass
    wz_start_night(chat_id)


def wz_end_game(chat_id, winner, last_event_text=""):
    game = WIZARD_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "ended"
    winner_label = "🧙 الساحر الأسود (الأشرار)" if winner == "evil" else "✨ السحرة الأخيار"

    lines = []
    winner_mentions = []
    for pid, p in game["players"].items():
        won = (p["role"] == "الساحر الأسود") == (winner == "evil")
        info = WZ_ROLES_INFO[p["role"]]
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        mark = "🏆" if won else "❌"
        lines.append(f"{mark} {wz_mention(pid, p['name'])} — {info['emoji']} {p['role']} ({status})")
        if won:
            winner_mentions.append(wz_mention(pid, p["name"]))
        wz_add_result(pid, p["name"], p["role"], won)

    txt = (
        f"{last_event_text}\n\n"
        f"🏁 <b>انتهت اللعبة!</b>\n"
        f"👑 <b>الفريق الفائز:</b> {winner_label}\n\n"
        f"🏆 <b>الفائزون:</b>\n" + ("\n".join(winner_mentions) if winner_mentions else "لا يوجد") + "\n\n"
        f"📋 <b>كشف الأدوار الكامل:</b>\n" + "\n".join(lines)
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML")
    except:
        pass

    add_event(chat_id, f"🧙 انتهت مباراة لعبة السحرة — الفائز: {winner_label}")
    wz_cleanup_game(chat_id)


# ================================================================
# 🏰 لعبة عرش المملكة — نفس محرك لعبة السحرة، بفكرة وأدوار مختلفة
# ================================================================
THR_MIN_PLAYERS   = 3
THR_REG_SECONDS   = 60
THR_PHASE_SECONDS = 45
THR_MAX_GROUPS_SHOWN = 30

THR_ROLES_INFO = {
    "القاتل":  {"emoji": "🗡️", "team": "evil",
        "desc": "الخائن الحقيقي، يختار كل جولة ضحية يحاول اغتيالها"},
    "الملك":   {"emoji": "👑", "team": "good",
        "desc": "قائد المملكة، لا يملك قدرة خاصة — لكن إذا اغتيل أو طُرد قبل كشف الخائن تسقط المملكة فوراً"},
    "الجاسوس": {"emoji": "🕵️", "team": "good",
        "desc": "يستطيع كل جولة معرفة إذا كان لاعب معيّن خائناً أو مخلصاً"},
    "الحارس":  {"emoji": "🛡", "team": "good",
        "desc": "يحمي كل جولة لاعباً واحداً من الاغتيال (لا يقدر يحمي نفس الشخص جولتين متتاليتين)"},
    "القاضي":  {"emoji": "⚖️", "team": "good",
        "desc": "يملك عفواً ملكياً واحداً طوال المباراة ينقذ فيه أي لاعب من الاغتيال"},
    "المواطن": {"emoji": "🧑‍🌾", "team": "good",
        "desc": "ليس لديه قدرة خاصة، لكن صوته وملاحظاته قد تنقذ المملكة"},
}

THRONE_GAMES = {}        # chat_id(int) -> game dict (حالة حية بالذاكرة)
THRONE_USER_ACTIVE = {}  # user_id(int) -> chat_id المباراة اللي هوه منضم/يلعب فيها حالياً


def thr_new_game(chat_id, creator_id):
    return {
        "chat_id": chat_id,
        "creator_id": creator_id,
        "phase": "registering",     # registering / night / day / voting / ended
        "players": {},               # user_id -> {name, username, role, alive}
        "round": 1,
        "night_actions": {},         # action_key -> {actor_id: target_id}
        "guard_last_target": None,
        "judge_used": False,
        "votes": {},                  # voter_id -> target_id
        "lock": threading.Lock(),
        "resolved_flags": set(),
    }


def thr_build_roles(n):
    evil_count = max(1, n // 4)
    roles = ["القاتل"] * evil_count
    remaining = n - evil_count
    specials = []
    if remaining >= 1:
        specials.append("الملك")
    if remaining >= 2:
        specials.append("الجاسوس")
    if n >= 6 and remaining >= 3:
        specials.append("الحارس")
    if n >= 9 and remaining >= 4:
        specials.append("القاضي")
    roles += specials
    roles += ["المواطن"] * (n - len(roles))
    random.shuffle(roles)
    return roles


def thr_alive_players(game):
    return {pid: p for pid, p in game["players"].items() if p["alive"]}


def thr_roster_text(game):
    lines = []
    for pid, p in game["players"].items():
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        lines.append(f"{wz_mention(pid, p['name'])} — {status}")
    return "👥 <b>اللاعبون:</b>\n" + "\n".join(lines)


def thr_cleanup_game(chat_id):
    game = THRONE_GAMES.pop(chat_id, None)
    if game:
        for pid in list(game["players"].keys()):
            if THRONE_USER_ACTIVE.get(pid) == chat_id:
                THRONE_USER_ACTIVE.pop(pid, None)
    return game


# ========= إحصائيات اللاعبين =========
def thr_ensure_stats():
    if "throne_stats" not in DB:
        DB["throne_stats"] = {}
        save_db()
    return DB["throne_stats"]


def thr_get_stats(user_id, name=None):
    stats = thr_ensure_stats()
    sid = str(user_id)
    if sid not in stats:
        stats[sid] = {"name": name or "لاعب", "games": 0, "wins": 0, "xp": 0, "role_counts": {}}
        save_db()
    if name:
        stats[sid]["name"] = name
    return stats[sid]


def thr_add_result(user_id, name, role, won):
    s = thr_get_stats(user_id, name)
    s["games"] += 1
    if won:
        s["wins"] += 1
        s["xp"] += 10
    else:
        s["xp"] += 4
    s["role_counts"][role] = s["role_counts"].get(role, 0) + 1
    save_db()


def thr_stats_text(user_id, name):
    s = thr_get_stats(user_id, name)
    games = s["games"]
    wins = s["wins"]
    winrate = round((wins / games) * 100, 1) if games else 0.0
    best_role = "لا يوجد بعد"
    if s["role_counts"]:
        best_role = max(s["role_counts"].items(), key=lambda x: x[1])[0]
        best_role = f"{THR_ROLES_INFO.get(best_role, {}).get('emoji','🎭')} {best_role}"
    lvl = wz_level_for_xp(s["xp"])
    return (
        f"🏰 <b>إحصائيات {name} بلعبة عرش المملكة</b>\n\n"
        f"🎮 عدد المباريات: <b>{games}</b>\n"
        f"🏆 عدد الانتصارات: <b>{wins}</b>\n"
        f"📈 نسبة الفوز: <b>{winrate}%</b>\n"
        f"⭐ المستوى: <b>{lvl}</b>\n"
        f"💎 نقاط الخبرة: <b>{s['xp']}</b>\n"
        f"🥇 أفضل دور: <b>{best_role}</b>"
    )


@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["احصائيات المملكة", "مملكة احصائياتي"])
def thr_my_stats_cmd(message):
    name = human_name(message.from_user)
    bot.reply_to(message, thr_stats_text(message.from_user.id, name), parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب المملكة")
def thr_top_cmd(message):
    stats = thr_ensure_stats()
    lst = sorted(list(stats.items()), key=lambda x: x[1].get("wins", 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    txt = "🏰 <b>توب أفضل 10 حماة للعرش (الأكثر فوزاً):</b>\n\n"
    if not lst:
        txt += "💤 لا يوجد بيانات بعد!"
    for i, (uid_str, sd) in enumerate(lst):
        rank = medals[i] if i < 3 else f"{i+1} )"
        txt += f"{rank} {sd.get('name','لاعب')} — 🏆 {sd.get('wins',0)} فوز من {sd.get('games',0)} مباراة\n"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= القائمة الرئيسية للعبة (بالخاص) =========
@bot.callback_query_handler(func=lambda c: c.data == "thr_menu")
def thr_menu_callback(call):
    try:
        _thr_menu_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[thr_menu_callback error] {e}")
        except:
            pass


def _thr_menu_callback_inner(call):
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "🏰 هذه الميزة تعمل بالخاص فقط.", show_alert=True)
        return
    user_id = call.from_user.id
    uid_str = str(user_id)
    candidate_groups = []
    for sid in list(DB.keys()):
        if not (sid.lstrip("-").isdigit()):
            continue
        cid = int(sid)
        if cid > 0:
            continue
        chat = DB.get(sid)
        if not isinstance(chat, dict):
            continue
        known = chat.get("wz_active_members") or {}

        if uid_str in known:
            title = chat.get("title") or sid
        else:
            try:
                member = _wz_tg_retry(bot.get_chat_member, cid, user_id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception:
                continue
            chat.setdefault("wz_active_members", {})[uid_str] = True
            save_db()
            try:
                info = _wz_tg_retry(bot.get_chat, cid)
                title = info.title or sid
                chat["title"] = title
            except Exception:
                title = chat.get("title") or sid

        candidate_groups.append((cid, title))
        if len(candidate_groups) >= THR_MAX_GROUPS_SHOWN:
            break

    if not candidate_groups:
        no_groups_txt = (
            "🏰 <b>عرش المملكة</b>\n\n"
            "ما لقيت أي قروب مشترك بيني وبينك تكدر تسوي فيه مباراة.\n"
            "تأكد إنك عضو بقروب مضاف فيه البوت، وجرب تكتب أي رسالة بذاك القروب."
        )
        edited = False
        try:
            bot.edit_message_text(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(call.message.chat.id, no_groups_txt, parse_mode="HTML")
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return

    m = types.InlineKeyboardMarkup(row_width=1)
    for cid, title in candidate_groups:
        m.add(types.InlineKeyboardButton(f"🏰 {title}", callback_data=f"thr_create_{cid}"))
    m.add(types.InlineKeyboardButton("❌ اغلاق", callback_data="close_panel"))
    choose_txt = "🏰 <b>عرش المملكة</b>\n\nاختر القروب اللي تبي تسوي فيه المباراة:"
    edited = False
    try:
        bot.edit_message_text(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
        edited = True
    except Exception:
        pass
    if not edited:
        try:
            bot.edit_message_caption(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
            edited = True
        except Exception:
            pass
    if not edited:
        try:
            bot.send_message(call.message.chat.id, choose_txt, parse_mode="HTML", reply_markup=m)
        except Exception:
            pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("thr_create_"))
def thr_create_callback(call):
    try:
        _thr_create_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[thr_create_callback error] {e}")
        except:
            pass


def _thr_create_callback_inner(call):
    user_id = call.from_user.id
    chat_id = int(call.data.split("_", 2)[2])

    if THRONE_USER_ACTIVE.get(user_id) is not None:
        bot.answer_callback_query(call.id, "⛔ أنت منضم بمباراة أخرى حالياً، خلّص منها أول.", show_alert=True)
        return
    if not games_allowed(chat_id):
        bot.answer_callback_query(call.id, "⛔ الألعاب مطفأة بهذا القروب حالياً.", show_alert=True)
        return
    if chat_id in THRONE_GAMES:
        bot.answer_callback_query(call.id, "🏰 يوجد مباراة قائمة فعلاً بهذا القروب.", show_alert=True)
        return

    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status not in ("member", "administrator", "creator"):
            bot.answer_callback_query(call.id, "⛔ لازم تكون عضو بهذا القروب.", show_alert=True)
            return
    except:
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أتأكد من عضويتك بالقروب.", show_alert=True)
        return

    game = thr_new_game(chat_id, user_id)
    creator_name = human_name(call.from_user)
    game["players"][user_id] = {"name": creator_name, "username": call.from_user.username, "role": None, "alive": True}
    THRONE_USER_ACTIVE[user_id] = chat_id
    THRONE_GAMES[chat_id] = game

    join_markup = types.InlineKeyboardMarkup(row_width=1)
    join_markup.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=thrjoin_{chat_id}"))

    txt = thr_registration_text(game)
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=join_markup)
    except Exception:
        thr_cleanup_game(chat_id)
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أرسل رسالة بالقروب (تأكد إن البوت مو مطرود).", show_alert=True)
        return

    bot.answer_callback_query(call.id, "✅ تم إنشاء المباراة! افتح القروب.")
    confirm_txt = "✅ تم إنشاء مباراة عرش المملكة بالقروب، شوف رسالة الانضمام هناك."
    try:
        bot.edit_message_text(confirm_txt, call.message.chat.id, call.message.message_id)
    except Exception:
        try:
            bot.edit_message_caption(confirm_txt, call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    Thread(target=thr_registration_timer, args=(chat_id,), daemon=True).start()


def thr_registration_text(game):
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    return (
        "🏰 <b>تم إنشاء مباراة عرش المملكة.</b>\n\n"
        f"⏳ يبدأ التسجيل لمدة {THR_REG_SECONDS} ثانية.\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}\n{players_txt}"
    )


def thr_join_markup(chat_id):
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=thrjoin_{chat_id}"))
    return m


def thr_announce_join(chat_id, joined_pid, joined_name):
    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    txt = (
        f"✅ انضم {wz_mention(joined_pid, joined_name)} إلى المباراة!\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}\n{players_txt}"
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=thr_join_markup(chat_id))
    except:
        pass


def thr_handle_deeplink_join(message, payload):
    """يعالج فتح الخاص عبر رابط الانضمام https://t.me/<bot>?start=thrjoin_<chat_id>"""
    try:
        chat_id = int(payload.split("_", 1)[1])
    except Exception:
        return
    user = message.from_user
    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        bot.send_message(message.chat.id, "⏰ انتهى وقت التسجيل أو ما فيه مباراة قائمة حالياً بهذا القروب.")
        return
    if user.id in game["players"]:
        bot.send_message(message.chat.id, "✅ أنت مسجل بالفعل بهذه المباراة، انتظر بدء اللعب بالقروب.")
        return
    active_chat = THRONE_USER_ACTIVE.get(user.id)
    if active_chat is not None and active_chat != chat_id:
        bot.send_message(message.chat.id, "⛔ أنت منضم بمباراة أخرى حالياً، لازم تخلّص منها أول.")
        return
    name = human_name(user)
    game["players"][user.id] = {"name": name, "username": user.username, "role": None, "alive": True}
    THRONE_USER_ACTIVE[user.id] = chat_id
    bot.send_message(message.chat.id, "✅ تم تسجيلك بنجاح.\n🏰 انتظر بدء المباراة بالقروب.")
    thr_announce_join(chat_id, user.id, name)


def thr_registration_timer(chat_id):
    time.sleep(THR_REG_SECONDS)
    thr_finish_registration(chat_id)


def thr_finish_registration(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    with game["lock"]:
        if game["phase"] != "registering":
            return
        if len(game["players"]) < THR_MIN_PLAYERS:
            game["phase"] = "ended"
            try:
                bot.send_message(chat_id,
                    f"❌ <b>تم إلغاء المباراة</b>\nلم يكتمل الحد الأدنى للاعبين ({THR_MIN_PLAYERS}).",
                    parse_mode="HTML")
            except:
                pass
            thr_cleanup_game(chat_id)
            return
        game["phase"] = "night"

    try:
        bot.send_message(chat_id,
            f"🏰 <b>اكتمل التسجيل!</b>\nعدد اللاعبين: {len(game['players'])}\n\nبدأت المباراة الآن...",
            parse_mode="HTML")
    except:
        pass

    thr_start_night(chat_id)


# ========= مرحلة الجولة الليلية =========
def thr_night_markup(chat_id, round_no, action_key, actor_id, exclude_self=True, exclude_pid=None):
    game = THRONE_GAMES[chat_id]
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in thr_alive_players(game).items():
        if exclude_self and pid == actor_id:
            continue
        if exclude_pid is not None and pid == exclude_pid:
            continue
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"thr_act_{action_key}_{chat_id}_{round_no}_{pid}"))
    return m


def thr_start_night(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "night"
    game["night_actions"] = {}
    rnd = game["round"]

    # ===== إعادة توزيع الأدوار عشوائياً على اللاعبين الأحياء كل جولة =====
    alive_ids = list(thr_alive_players(game).keys())
    new_roles = thr_build_roles(len(alive_ids))
    random.shuffle(alive_ids)
    for pid, role in zip(alive_ids, new_roles):
        game["players"][pid]["role"] = role
    game["guard_last_target"] = None

    for pid, p in thr_alive_players(game).items():
        role = p["role"]
        info = THR_ROLES_INFO[role]
        role_reveal = f"🎭 <b>دورك هذي الجولة:</b>\n{info['emoji']} <b>{role}</b>\n{info['desc']}"
        if role == "القاتل":
            markup = thr_night_markup(chat_id, rnd, "kill", pid, exclude_self=True)
            text = "🗡️ اختر ضحيتك هذه الجولة:"
        elif role == "الجاسوس":
            markup = thr_night_markup(chat_id, rnd, "spy", pid, exclude_self=True)
            text = "🕵️ اختر لاعباً لتكشف حقيقته:"
        elif role == "الحارس":
            markup = thr_night_markup(chat_id, rnd, "guard", pid, exclude_self=False,
                                       exclude_pid=game.get("guard_last_target"))
            text = "🛡 اختر لاعباً لتحميه هذه الجولة:"
        elif role == "القاضي" and not game.get("judge_used"):
            markup = thr_night_markup(chat_id, rnd, "pardon", pid, exclude_self=False)
            text = "⚖️ اختر لاعباً تصدر له عفواً ملكياً ينقذه من الاغتيال (استخدام واحد طوال اللعبة):"
        else:
            markup = None
            text = None

        try:
            if markup is not None and markup.keyboard:
                bot.send_message(pid, f"🌙 <b>جولة جديدة في القصر...</b>\n\n{role_reveal}\n\n{text}",
                                  parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(pid, f"🌙 <b>جولة جديدة في القصر...</b>\n\n{role_reveal}\n\nما عندك قدرة هذي الجولة، انتظر النتيجة.",
                                  parse_mode="HTML")
        except:
            pass

    try:
        bot.send_message(chat_id,
            "🌙 <b>اجتماع القصر جارٍ...</b>\nيرجى انتظار انتهاء جميع الشخصيات من تنفيذ قدراتها.",
            parse_mode="HTML")
    except:
        pass

    Thread(target=thr_night_timer, args=(chat_id, rnd), daemon=True).start()


def thr_night_timer(chat_id, rnd):
    time.sleep(THR_PHASE_SECONDS)
    game = THRONE_GAMES.get(chat_id)
    if game and game["phase"] == "night" and game["round"] == rnd:
        thr_resolve_night(chat_id)


def thr_expected_night_actors(game):
    expected = set()
    for pid, p in thr_alive_players(game).items():
        role = p["role"]
        if role == "القاتل":
            expected.add(("kill", pid))
        elif role == "الجاسوس":
            expected.add(("spy", pid))
        elif role == "الحارس":
            expected.add(("guard", pid))
        elif role == "القاضي" and not game.get("judge_used"):
            expected.add(("pardon", pid))
    return expected


def thr_check_night_complete(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "night":
        return
    expected = thr_expected_night_actors(game)
    done = set()
    for action_key, actors in game["night_actions"].items():
        for actor_id in actors.keys():
            done.add((action_key, actor_id))
    if expected and expected.issubset(done):
        thr_resolve_night(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("thr_act_"))
def thr_act_callback(call):
    try:
        parts = call.data.split("_")
        action_key = parts[2]
        chat_id = int(parts[3])
        rnd = int(parts[4])
        target = int(parts[5])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "night" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهت هذه المرحلة.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "لا يمكنك التصرف الآن.", show_alert=True)
        return

    game["night_actions"].setdefault(action_key, {})[user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل اختيارك.")
    try:
        bot.edit_message_text("✅ تم تسجيل اختيارك، انتظر نتيجة الجولة.", call.message.chat.id, call.message.message_id)
    except:
        pass

    thr_check_night_complete(chat_id)


def thr_check_win(game):
    alive = thr_alive_players(game)
    evil_alive = [p for p in alive.values() if p["role"] == "القاتل"]
    good_alive = [p for p in alive.values() if p["role"] != "القاتل"]
    if len(evil_alive) == 0:
        return "good"
    if len(evil_alive) >= len(good_alive):
        return "evil"
    return None


def thr_resolve_night(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "night":
            return
        game["phase"] = "resolving"

    actions = game["night_actions"]

    guard_targets = list(actions.get("guard", {}).values())
    guard_target = guard_targets[0] if guard_targets else None
    game["guard_last_target"] = guard_target

    pardon_targets = list(actions.get("pardon", {}).values())
    pardon_target = pardon_targets[0] if pardon_targets else None
    if pardon_target is not None:
        game["judge_used"] = True

    kill_votes = list(actions.get("kill", {}).values())
    victim = None
    if kill_votes:
        tally = Counter(kill_votes)
        top = tally.most_common()
        maxvotes = top[0][1]
        candidates = [t for t, c in top if c == maxvotes]
        victim = random.choice(candidates)

    saved = victim is not None and (victim == guard_target or victim == pardon_target)

    if victim is not None and not saved:
        game["players"][victim]["alive"] = False
        vname = game["players"][victim]["name"]
        vrole = game["players"][victim]["role"]
        vinfo = THR_ROLES_INFO[vrole]
        killer_info = THR_ROLES_INFO["القاتل"]
        story = (f"🌙 <b>قصة الجولة:</b>\n"
                 f"تسلل {killer_info['emoji']} <b>القاتل</b> واغتال {vinfo['emoji']} <b>{vrole}</b>!")
        death_text = f"{story}\n\n💀 القتيل: {wz_mention(victim, vname)}"

        if vrole == "الملك":
            death_text += "\n\n👑💀 <b>سقط الملك! سقطت المملكة بالكامل!</b>"
            thr_end_game(chat_id, "evil", death_text)
            return
    elif victim is not None and saved:
        death_text = ("🌙 <b>قصة الجولة:</b>\n"
                       "حاول 🗡️ القاتل اغتيال أحدهم هذه الجولة، لكن تم إنقاذه في اللحظة الأخيرة! ⚖️")
    else:
        death_text = "🌙 <b>قصة الجولة:</b>\nمرّت الجولة بهدوء، لم يمت أحد."

    # نتائج الجاسوس
    for actor_id, target in actions.get("spy", {}).items():
        actor = game["players"].get(actor_id)
        if not actor or not actor["alive"]:
            continue
        t = game["players"].get(target)
        if not t:
            continue
        is_evil = t["role"] == "القاتل"
        result = "🔴 خائن! احذر منه" if is_evil else "🟢 مخلص"
        try:
            bot.send_message(actor_id, f"🕵️ نتيجة تحرّيك عن {t['name']}:\n{result}", parse_mode="HTML")
        except:
            pass

    game["night_actions"] = {}

    winner = thr_check_win(game)
    if winner:
        thr_end_game(chat_id, winner, death_text)
        return

    game["phase"] = "day"
    try:
        bot.send_message(chat_id,
            f"☀ <b>اجتماع القصر...</b>\n\n{death_text}\n\n{thr_roster_text(game)}\n\n"
            f"💬 وقت النقاش: {THR_PHASE_SECONDS} ثانية",
            parse_mode="HTML")
    except:
        pass

    Thread(target=thr_discussion_timer, args=(chat_id, game["round"]), daemon=True).start()


def thr_discussion_timer(chat_id, rnd):
    time.sleep(THR_PHASE_SECONDS)
    game = THRONE_GAMES.get(chat_id)
    if game and game["phase"] == "day" and game["round"] == rnd:
        thr_start_voting(chat_id)


# ========= مرحلة التصويت =========
def thr_voting_text(game):
    tally = Counter(game["votes"].values())
    lines = []
    for pid, p in thr_alive_players(game).items():
        lines.append(f"• {p['name']} — {tally.get(pid, 0)} صوت")
    return "🗳 <b>وقت التصويت!</b>\nصوّت لمحاكمة أحد اللاعبين المشتبه بهم:\n\n" + "\n".join(lines)


def thr_start_voting(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "voting"
    game["votes"] = {}
    rnd = game["round"]

    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in thr_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"thr_vote_{chat_id}_{rnd}_{pid}"))

    try:
        bot.send_message(chat_id, thr_voting_text(game), parse_mode="HTML", reply_markup=m)
    except:
        pass

    Thread(target=thr_voting_timer, args=(chat_id, rnd), daemon=True).start()


def thr_voting_timer(chat_id, rnd):
    time.sleep(THR_PHASE_SECONDS)
    game = THRONE_GAMES.get(chat_id)
    if game and game["phase"] == "voting" and game["round"] == rnd:
        thr_resolve_voting(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("thr_vote_"))
def thr_vote_callback(call):
    try:
        parts = call.data.split("_")
        chat_id = int(parts[2])
        rnd = int(parts[3])
        target = int(parts[4])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = THRONE_GAMES.get(chat_id)
    if not game or game["phase"] != "voting" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهى وقت التصويت.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "⛔ ما تكدر تصوّت (غير حي أو مو منضم).", show_alert=True)
        return

    game["votes"][user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل صوتك.")
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in thr_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"thr_vote_{chat_id}_{rnd}_{pid}"))
    try:
        bot.send_message(chat_id,
            f"🗳 صوّت {wz_mention(user_id, player['name'])}!\n\n{thr_voting_text(game)}",
            parse_mode="HTML", reply_markup=m)
    except:
        pass

    if len(game["votes"]) >= len(thr_alive_players(game)):
        thr_resolve_voting(chat_id)


def thr_resolve_voting(chat_id):
    game = THRONE_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "voting":
            return
        game["phase"] = "resolving"

    tally = Counter(game["votes"].values())
    result_text = ""
    eliminated = None
    if tally:
        top = tally.most_common()
        maxvotes = top[0][1]
        candidates = [t for t, c in top if c == maxvotes]
        if len(candidates) == 1:
            eliminated = candidates[0]
            game["players"][eliminated]["alive"] = False
            ename = game["players"][eliminated]["name"]
            erole = game["players"][eliminated]["role"]
            einfo = THR_ROLES_INFO[erole]
            result_text = (
                f"🗳 <b>قصة المحاكمة:</b>\n"
                f"اجتمع مستشارو المملكة وقرروا محاكمة {wz_mention(eliminated, ename)}!\n\n"
                f"⚖️ كشف دوره: {einfo['emoji']} <b>{erole}</b>"
            )
            if erole == "الملك":
                result_text += "\n\n👑💀 <b>حكموا على الملك بالخطأ! سقطت المملكة بالكامل!</b>"
        else:
            result_text = (
                "🗳 <b>قصة المحاكمة:</b>\n"
                "تعادلت الأصوات بين أكثر من شخص، فقرر المجلس تأجيل الحكم لهذي المرة.\n\n"
                "🤝 لم يُحاكم أحد."
            )
    else:
        result_text = (
            "🗳 <b>قصة المحاكمة:</b>\n"
            "ساد الصمت بين مستشاري المملكة، محد جرؤ يصوّت أو يتّهم أحد.\n\n"
            "💤 لم يُحاكم أحد، والجولة الجاية بتكشف المزيد..."
        )

    if eliminated is not None and game["players"][eliminated]["role"] == "الملك":
        thr_end_game(chat_id, "evil", result_text)
        return

    winner = thr_check_win(game)
    if winner:
        thr_end_game(chat_id, winner, result_text)
        return

    game["round"] += 1
    game["phase"] = "night"
    try:
        bot.send_message(chat_id, f"{result_text}\n\n{thr_roster_text(game)}",
                          parse_mode="HTML")
    except:
        pass
    thr_start_night(chat_id)


def thr_end_game(chat_id, winner, last_event_text=""):
    game = THRONE_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "ended"
    winner_label = "🗡️ القاتل (الأشرار)" if winner == "evil" else "🏰 حماة المملكة (الأخيار)"

    lines = []
    winner_mentions = []
    for pid, p in game["players"].items():
        won = (p["role"] == "القاتل") == (winner == "evil")
        info = THR_ROLES_INFO[p["role"]]
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        mark = "🏆" if won else "❌"
        lines.append(f"{mark} {wz_mention(pid, p['name'])} — {info['emoji']} {p['role']} ({status})")
        if won:
            winner_mentions.append(wz_mention(pid, p["name"]))
        thr_add_result(pid, p["name"], p["role"], won)

    txt = (
        f"{last_event_text}\n\n"
        f"🏁 <b>انتهت المباراة!</b>\n"
        f"👑 <b>الفريق الفائز:</b> {winner_label}\n\n"
        f"🏆 <b>الفائزون:</b>\n" + ("\n".join(winner_mentions) if winner_mentions else "لا يوجد") + "\n\n"
        f"📋 <b>كشف الأدوار الكامل:</b>\n" + "\n".join(lines)
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML")
    except:
        pass

    add_event(chat_id, f"🏰 انتهت مباراة عرش المملكة — الفائز: {winner_label}")
    thr_cleanup_game(chat_id)


# ================================================================
# 🐺 لعبة المافيا — نفس المحرك، لكن الأدوار تنثبت مرة وحدة أول اللعبة
# ================================================================
MF_MIN_PLAYERS   = 5
MF_MAX_PLAYERS   = 15
MF_REG_SECONDS   = 60
MF_PHASE_SECONDS = 100
MF_MAX_GROUPS_SHOWN = 30

MF_ROLES_INFO = {
    "القاتل":  {"emoji": "🗡️", "team": "evil",
        "desc": "فرد من عصابة المافيا، يختار كل ليلة ضحية للقتل"},
    "الملك":   {"emoji": "👑", "team": "good",
        "desc": "أهم شخصية بالمدينة، بلا قدرة خاصة — لو مات أو انطرد تفوز المافيا فوراً"},
    "الحارس":  {"emoji": "🛡", "team": "good",
        "desc": "يحمي لاعباً كل ليلة من القتل (لا يقدر يحمي نفس الشخص ليلتين متتاليتين)"},
    "الجاسوس": {"emoji": "🕵️", "team": "good",
        "desc": "يحقق مع لاعب كل ليلة ليعرف إذا كان من المافيا أو بريئاً"},
    "المواطن": {"emoji": "🧑‍🌾", "team": "good",
        "desc": "ليس لديه قدرة خاصة، لكن صوته وملاحظاته تهم بالتصويت"},
    "المحتال": {"emoji": "🎭", "team": "evil",
        "desc": "يزوّر هوية لاعب كل ليلة، فتظهر نتيجة تحري الجاسوس عنه معكوسة"},
    "التاجر":  {"emoji": "💰", "team": "good",
        "desc": "يملك حماية ذاتية واحدة طوال اللعبة يستخدمها ليلاً ليحمي نفسه من القتل"},
    "القاضي":  {"emoji": "⚖️", "team": "good",
        "desc": "يملك عفواً ملكياً واحداً طوال اللعبة يلغي فيه نتيجة تصويت كاملة"},
}

# جدول توزيع الأدوار حسب عدد اللاعبين (5 حد أدنى، 15 حد أقصى)
MF_BASE_ROLES = ["الملك", "القاتل", "الحارس", "الجاسوس", "المواطن"]
MF_ADDITIONS = {
    6: "المحتال",
    7: "التاجر",
    8: "المواطن",
    9: "القاضي",
    10: None,  # يُحدد عشوائياً: الجاسوس أو الحارس
    11: "القاتل",
    12: "المحتال",
    13: "التاجر",
    14: "المواطن",
    15: "القاضي",
}

MAFIA_GAMES = {}
MAFIA_USER_ACTIVE = {}


def mf_new_game(chat_id, creator_id):
    return {
        "chat_id": chat_id,
        "creator_id": creator_id,
        "phase": "registering",
        "players": {},
        "round": 1,
        "night_actions": {},
        "guard_last_target": {},   # actor_id -> آخر هدف حماه
        "shield_used": {},          # actor_id -> True لو استخدم التاجر حمايته
        "judge_used": {},           # actor_id -> True لو استخدم القاضي عفوه
        "judge_veto_active": False,
        "votes": {},
        "lock": threading.Lock(),
    }


def mf_build_roles(n):
    n = max(MF_MIN_PLAYERS, min(n, MF_MAX_PLAYERS))
    roles = list(MF_BASE_ROLES)
    for i in range(6, n + 1):
        add = MF_ADDITIONS[i]
        if add is None:
            add = random.choice(["الجاسوس", "الحارس"])
        roles.append(add)
    random.shuffle(roles)
    return roles


def mf_alive_players(game):
    return {pid: p for pid, p in game["players"].items() if p["alive"]}


def mf_roster_text(game):
    lines = []
    for pid, p in game["players"].items():
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        lines.append(f"{wz_mention(pid, p['name'])} — {status}")
    return "👥 <b>اللاعبون:</b>\n" + "\n".join(lines)


def mf_cleanup_game(chat_id):
    game = MAFIA_GAMES.pop(chat_id, None)
    if game:
        for pid in list(game["players"].keys()):
            if MAFIA_USER_ACTIVE.get(pid) == chat_id:
                MAFIA_USER_ACTIVE.pop(pid, None)
    return game


# ========= إحصائيات اللاعبين =========
def mf_ensure_stats():
    if "mafia_stats" not in DB:
        DB["mafia_stats"] = {}
        save_db()
    return DB["mafia_stats"]


def mf_get_stats(user_id, name=None):
    stats = mf_ensure_stats()
    sid = str(user_id)
    if sid not in stats:
        stats[sid] = {"name": name or "لاعب", "games": 0, "wins": 0, "xp": 0, "role_counts": {}}
        save_db()
    if name:
        stats[sid]["name"] = name
    return stats[sid]


def mf_add_result(user_id, name, role, won):
    s = mf_get_stats(user_id, name)
    s["games"] += 1
    if won:
        s["wins"] += 1
        s["xp"] += 10
    else:
        s["xp"] += 4
    s["role_counts"][role] = s["role_counts"].get(role, 0) + 1
    save_db()


def mf_stats_text(user_id, name):
    s = mf_get_stats(user_id, name)
    games = s["games"]
    wins = s["wins"]
    winrate = round((wins / games) * 100, 1) if games else 0.0
    best_role = "لا يوجد بعد"
    if s["role_counts"]:
        best_role = max(s["role_counts"].items(), key=lambda x: x[1])[0]
        best_role = f"{MF_ROLES_INFO.get(best_role, {}).get('emoji','🎭')} {best_role}"
    lvl = wz_level_for_xp(s["xp"])
    return (
        f"🐺 <b>إحصائيات {name} بلعبة المافيا</b>\n\n"
        f"🎮 عدد المباريات: <b>{games}</b>\n"
        f"🏆 عدد الانتصارات: <b>{wins}</b>\n"
        f"📈 نسبة الفوز: <b>{winrate}%</b>\n"
        f"⭐ المستوى: <b>{lvl}</b>\n"
        f"💎 نقاط الخبرة: <b>{s['xp']}</b>\n"
        f"🥇 أفضل دور: <b>{best_role}</b>"
    )


@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["احصائيات المافيا", "مافيا احصائياتي"])
def mf_my_stats_cmd(message):
    name = human_name(message.from_user)
    bot.reply_to(message, mf_stats_text(message.from_user.id, name), parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text and m.text.strip() == "توب المافيا")
def mf_top_cmd(message):
    stats = mf_ensure_stats()
    lst = sorted(list(stats.items()), key=lambda x: x[1].get("wins", 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    txt = "🐺 <b>توب أفضل 10 لاعبين بلعبة المافيا (الأكثر فوزاً):</b>\n\n"
    if not lst:
        txt += "💤 لا يوجد بيانات بعد!"
    for i, (uid_str, sd) in enumerate(lst):
        rank = medals[i] if i < 3 else f"{i+1} )"
        txt += f"{rank} {sd.get('name','لاعب')} — 🏆 {sd.get('wins',0)} فوز من {sd.get('games',0)} مباراة\n"
    bot.reply_to(message, txt, parse_mode="HTML")


# ========= القائمة الرئيسية للعبة (بالخاص) =========
@bot.callback_query_handler(func=lambda c: c.data == "mf_menu")
def mf_menu_callback(call):
    try:
        _mf_menu_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[mf_menu_callback error] {e}")
        except:
            pass


def _mf_menu_callback_inner(call):
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "🐺 هذه الميزة تعمل بالخاص فقط.", show_alert=True)
        return
    user_id = call.from_user.id
    uid_str = str(user_id)
    candidate_groups = []
    for sid in list(DB.keys()):
        if not (sid.lstrip("-").isdigit()):
            continue
        cid = int(sid)
        if cid > 0:
            continue
        chat = DB.get(sid)
        if not isinstance(chat, dict):
            continue
        known = chat.get("wz_active_members") or {}

        if uid_str in known:
            title = chat.get("title") or sid
        else:
            try:
                member = _wz_tg_retry(bot.get_chat_member, cid, user_id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception:
                continue
            chat.setdefault("wz_active_members", {})[uid_str] = True
            save_db()
            try:
                info = _wz_tg_retry(bot.get_chat, cid)
                title = info.title or sid
                chat["title"] = title
            except Exception:
                title = chat.get("title") or sid

        candidate_groups.append((cid, title))
        if len(candidate_groups) >= MF_MAX_GROUPS_SHOWN:
            break

    if not candidate_groups:
        no_groups_txt = (
            "🐺 <b>لعبة المافيا</b>\n\n"
            "ما لقيت أي قروب مشترك بيني وبينك تكدر تسوي فيه مباراة.\n"
            "تأكد إنك عضو بقروب مضاف فيه البوت، وجرب تكتب أي رسالة بذاك القروب."
        )
        edited = False
        try:
            bot.edit_message_text(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
            edited = True
        except Exception:
            pass
        if not edited:
            try:
                bot.edit_message_caption(no_groups_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
                edited = True
            except Exception:
                pass
        if not edited:
            try:
                bot.send_message(call.message.chat.id, no_groups_txt, parse_mode="HTML")
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return

    m = types.InlineKeyboardMarkup(row_width=1)
    for cid, title in candidate_groups:
        m.add(types.InlineKeyboardButton(f"🐺 {title}", callback_data=f"mf_create_{cid}"))
    m.add(types.InlineKeyboardButton("❌ اغلاق", callback_data="close_panel"))
    choose_txt = "🐺 <b>لعبة المافيا</b>\n\nاختر القروب اللي تبي تسوي فيه المباراة:"
    edited = False
    try:
        bot.edit_message_text(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
        edited = True
    except Exception:
        pass
    if not edited:
        try:
            bot.edit_message_caption(choose_txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=m)
            edited = True
        except Exception:
            pass
    if not edited:
        try:
            bot.send_message(call.message.chat.id, choose_txt, parse_mode="HTML", reply_markup=m)
        except Exception:
            pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mf_create_"))
def mf_create_callback(call):
    try:
        _mf_create_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "⚠️ صار خطأ، جرب مرة ثانية.", show_alert=True)
        except:
            pass
        try:
            print(f"[mf_create_callback error] {e}")
        except:
            pass


def _mf_create_callback_inner(call):
    user_id = call.from_user.id
    chat_id = int(call.data.split("_", 2)[2])

    if MAFIA_USER_ACTIVE.get(user_id) is not None:
        bot.answer_callback_query(call.id, "⛔ أنت منضم بمباراة أخرى حالياً، خلّص منها أول.", show_alert=True)
        return
    if not games_allowed(chat_id):
        bot.answer_callback_query(call.id, "⛔ الألعاب مطفأة بهذا القروب حالياً.", show_alert=True)
        return
    if chat_id in MAFIA_GAMES:
        bot.answer_callback_query(call.id, "🐺 يوجد مباراة قائمة فعلاً بهذا القروب.", show_alert=True)
        return

    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status not in ("member", "administrator", "creator"):
            bot.answer_callback_query(call.id, "⛔ لازم تكون عضو بهذا القروب.", show_alert=True)
            return
    except:
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أتأكد من عضويتك بالقروب.", show_alert=True)
        return

    game = mf_new_game(chat_id, user_id)
    creator_name = human_name(call.from_user)
    game["players"][user_id] = {"name": creator_name, "username": call.from_user.username, "role": None, "alive": True}
    MAFIA_USER_ACTIVE[user_id] = chat_id
    MAFIA_GAMES[chat_id] = game

    join_markup = types.InlineKeyboardMarkup(row_width=1)
    join_markup.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=mfjoin_{chat_id}"))

    txt = mf_registration_text(game)
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=join_markup)
    except Exception:
        mf_cleanup_game(chat_id)
        bot.answer_callback_query(call.id, "⚠️ ما قدرت أرسل رسالة بالقروب (تأكد إن البوت مو مطرود).", show_alert=True)
        return

    bot.answer_callback_query(call.id, "✅ تم إنشاء المباراة! افتح القروب.")
    confirm_txt = "✅ تم إنشاء مباراة المافيا بالقروب، شوف رسالة الانضمام هناك."
    try:
        bot.edit_message_text(confirm_txt, call.message.chat.id, call.message.message_id)
    except Exception:
        try:
            bot.edit_message_caption(confirm_txt, call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    Thread(target=mf_registration_timer, args=(chat_id,), daemon=True).start()


def mf_registration_text(game):
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    return (
        "🐺 <b>تم إنشاء مباراة المافيا.</b>\n\n"
        f"⏳ يبدأ التسجيل لمدة {MF_REG_SECONDS} ثانية.\n"
        f"👤 الحد الأدنى {MF_MIN_PLAYERS} لاعبين — الحد الأقصى {MF_MAX_PLAYERS} لاعب.\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}\n{players_txt}"
    )


def mf_join_markup(chat_id):
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton(
        "✨ اضغط هنا للانضمام", url=f"https://t.me/{BOT_USERNAME}?start=mfjoin_{chat_id}"))
    return m


def mf_announce_join(chat_id, joined_pid, joined_name):
    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    n = len(game["players"])
    lines = [wz_mention(pid, p["name"]) for pid, p in game["players"].items()]
    players_txt = "\n".join(f"🔹 {l}" for l in lines) if lines else "💤 لا يوجد لاعبين بعد"
    txt = (
        f"✅ انضم {wz_mention(joined_pid, joined_name)} إلى المباراة!\n\n"
        f"👥 <b>عدد اللاعبين:</b> {n}/{MF_MAX_PLAYERS}\n{players_txt}"
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=mf_join_markup(chat_id))
    except:
        pass


def mf_handle_deeplink_join(message, payload):
    """يعالج فتح الخاص عبر رابط الانضمام https://t.me/<bot>?start=mfjoin_<chat_id>"""
    try:
        chat_id = int(payload.split("_", 1)[1])
    except Exception:
        return
    user = message.from_user
    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        bot.send_message(message.chat.id, "⏰ انتهى وقت التسجيل أو ما فيه مباراة قائمة حالياً بهذا القروب.")
        return
    if user.id in game["players"]:
        bot.send_message(message.chat.id, "✅ أنت مسجل بالفعل بهذه المباراة، انتظر بدء اللعب بالقروب.")
        return
    if len(game["players"]) >= MF_MAX_PLAYERS:
        bot.send_message(message.chat.id, f"⛔ اكتمل العدد الأقصى للمباراة ({MF_MAX_PLAYERS} لاعب).")
        return
    active_chat = MAFIA_USER_ACTIVE.get(user.id)
    if active_chat is not None and active_chat != chat_id:
        bot.send_message(message.chat.id, "⛔ أنت منضم بمباراة أخرى حالياً، لازم تخلّص منها أول.")
        return
    name = human_name(user)
    game["players"][user.id] = {"name": name, "username": user.username, "role": None, "alive": True}
    MAFIA_USER_ACTIVE[user.id] = chat_id
    bot.send_message(message.chat.id, "✅ تم تسجيلك بنجاح.\n🐺 انتظر بدء المباراة بالقروب.")
    mf_announce_join(chat_id, user.id, name)


def mf_registration_timer(chat_id):
    time.sleep(MF_REG_SECONDS)
    mf_finish_registration(chat_id)


def mf_finish_registration(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "registering":
        return
    with game["lock"]:
        if game["phase"] != "registering":
            return
        if len(game["players"]) < MF_MIN_PLAYERS:
            game["phase"] = "ended"
            try:
                bot.send_message(chat_id,
                    f"❌ <b>تم إلغاء المباراة</b>\nلم يكتمل الحد الأدنى للاعبين ({MF_MIN_PLAYERS}).",
                    parse_mode="HTML")
            except:
                pass
            mf_cleanup_game(chat_id)
            return
        # ===== توزيع الأدوار مرة واحدة فقط، تبقى ثابتة لبقية المباراة =====
        pids = list(game["players"].keys())
        roles = mf_build_roles(len(pids))
        random.shuffle(pids)
        for pid, role in zip(pids, roles):
            game["players"][pid]["role"] = role
        game["phase"] = "night"

    try:
        bot.send_message(chat_id,
            "🌆 <b>حلّ المساء في مدينة ريفان...</b>\n"
            "انتشرت الشائعات عن وجود عصابة مافيا بين السكان.\n"
            "أُغلقت الأبواب، وبدأ الجميع يترقب ما سيحدث الليلة.\n\n"
            f"عدد اللاعبين: {len(game['players'])}",
            parse_mode="HTML")
    except:
        pass

    mf_start_night(chat_id)


# ========= مرحلة الجولة الليلية =========
def mf_night_markup(chat_id, round_no, action_key, actor_id, exclude_self=True, exclude_pid=None):
    game = MAFIA_GAMES[chat_id]
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in mf_alive_players(game).items():
        if exclude_self and pid == actor_id:
            continue
        if exclude_pid is not None and pid == exclude_pid:
            continue
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"mf_act_{action_key}_{chat_id}_{round_no}_{pid}"))
    return m


def mf_start_night(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "night"
    game["night_actions"] = {}
    rnd = game["round"]
    first_round = (rnd == 1)

    for pid, p in mf_alive_players(game).items():
        role = p["role"]
        info = MF_ROLES_INFO[role]
        if first_round:
            header = f"🎭 <b>دورك بهذي المباراة:</b>\n{info['emoji']} <b>{role}</b>\n{info['desc']}\n\n"
        else:
            header = f"🌙 <b>دورك:</b> {info['emoji']} <b>{role}</b>\n\n"

        markup = None
        text = None
        if role == "القاتل":
            markup = mf_night_markup(chat_id, rnd, "kill", pid, exclude_self=True)
            text = "🗡️ اختر ضحية هذه الليلة:"
        elif role == "الجاسوس":
            markup = mf_night_markup(chat_id, rnd, "spy", pid, exclude_self=True)
            text = "🕵️ اختر لاعباً لتحقق معه:"
        elif role == "الحارس":
            markup = mf_night_markup(chat_id, rnd, "guard", pid, exclude_self=False,
                                      exclude_pid=game["guard_last_target"].get(pid))
            text = "🛡 اختر لاعباً لتحميه هذه الليلة:"
        elif role == "المحتال":
            markup = mf_night_markup(chat_id, rnd, "frame", pid, exclude_self=True)
            text = "🎭 اختر لاعباً لتزوّر هويته هذه الليلة:"
        elif role == "التاجر" and not game["shield_used"].get(pid):
            m = types.InlineKeyboardMarkup(row_width=1)
            m.add(types.InlineKeyboardButton("💰 استخدم حمايتي الليلة", callback_data=f"mf_act_shield_{chat_id}_{rnd}_{pid}"))
            markup = m
            text = "💰 عندك حماية ذاتية واحدة طول اللعبة، استخدمها إذا حسيت بخطر (اختياري):"

        try:
            if markup is not None and markup.keyboard:
                bot.send_message(pid, f"{header}{text}", parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(pid, f"{header}ما عندك قدرة تستخدمها هذه الليلة، انتظر النتيجة.", parse_mode="HTML")
        except:
            pass

    try:
        bot.send_message(chat_id,
            "🌙 <b>المدينة تغرق بالظلام...</b>\nيرجى انتظار انتهاء جميع الشخصيات من تنفيذ قدراتها.",
            parse_mode="HTML")
    except:
        pass

    Thread(target=mf_night_timer, args=(chat_id, rnd), daemon=True).start()


def mf_night_timer(chat_id, rnd):
    time.sleep(MF_PHASE_SECONDS)
    game = MAFIA_GAMES.get(chat_id)
    if game and game["phase"] == "night" and game["round"] == rnd:
        mf_resolve_night(chat_id)


def mf_expected_night_actors(game):
    expected = set()
    for pid, p in mf_alive_players(game).items():
        role = p["role"]
        if role == "القاتل":
            expected.add(("kill", pid))
        elif role == "الجاسوس":
            expected.add(("spy", pid))
        elif role == "الحارس":
            expected.add(("guard", pid))
        elif role == "المحتال":
            expected.add(("frame", pid))
        # ملاحظة: التاجر (shield) اختياري وما ينتظره التايمر
    return expected


def mf_check_night_complete(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "night":
        return
    expected = mf_expected_night_actors(game)
    done = set()
    for action_key, actors in game["night_actions"].items():
        if action_key == "shield":
            continue
        for actor_id in actors.keys():
            done.add((action_key, actor_id))
    if expected and expected.issubset(done):
        mf_resolve_night(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mf_act_"))
def mf_act_callback(call):
    try:
        parts = call.data.split("_")
        action_key = parts[2]
        chat_id = int(parts[3])
        rnd = int(parts[4])
        target = int(parts[5])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "night" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهت هذه المرحلة.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "لا يمكنك التصرف الآن.", show_alert=True)
        return

    if action_key == "shield":
        if game["shield_used"].get(user_id):
            bot.answer_callback_query(call.id, "⚠️ سبق واستخدمت حمايتك.", show_alert=True)
            return
        game["shield_used"][user_id] = True

    game["night_actions"].setdefault(action_key, {})[user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل اختيارك.")
    try:
        bot.edit_message_text("✅ تم تسجيل اختيارك، انتظر نتيجة الليلة.", call.message.chat.id, call.message.message_id)
    except:
        pass

    mf_check_night_complete(chat_id)


def mf_check_win(game):
    alive = mf_alive_players(game)
    evil_alive = [p for p in alive.values() if MF_ROLES_INFO[p["role"]]["team"] == "evil"]
    good_alive = [p for p in alive.values() if MF_ROLES_INFO[p["role"]]["team"] != "evil"]
    if len(evil_alive) == 0:
        return "good"
    if len(evil_alive) >= len(good_alive):
        return "evil"
    return None


def mf_resolve_night(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "night":
            return
        game["phase"] = "resolving"

    actions = game["night_actions"]

    guard_protected = set()
    for actor_id, target in actions.get("guard", {}).items():
        guard_protected.add(target)
        game["guard_last_target"][actor_id] = target

    shielded = set(actions.get("shield", {}).values())
    framed = set(actions.get("frame", {}).values())

    kill_votes = list(actions.get("kill", {}).values())
    victim = None
    if kill_votes:
        tally = Counter(kill_votes)
        top = tally.most_common()
        maxvotes = top[0][1]
        candidates = [t for t, c in top if c == maxvotes]
        victim = random.choice(candidates)

    saved = victim is not None and (victim in guard_protected or victim in shielded)

    if victim is not None and not saved:
        game["players"][victim]["alive"] = False
        vname = game["players"][victim]["name"]
        vrole = game["players"][victim]["role"]
        vinfo = MF_ROLES_INFO[vrole]
        death_text = (f"💀 <b>عثر السكان على جثة أحد أبناء المدينة.</b>\n"
                       f"القتيل: {wz_mention(victim, vname)} — كشف دوره: {vinfo['emoji']} <b>{vrole}</b>")
        if vrole == "الملك":
            death_text += "\n\n👑💀 <b>مات الملك! سيطرت المافيا على المدينة فوراً!</b>"
            mf_end_game(chat_id, "evil", death_text)
            return
    elif victim is not None and saved:
        death_text = "🌅 <b>مرت الليلة بسلام، ولم يُعثر على أي ضحية.</b> (تم إنقاذ الهدف في اللحظة الأخيرة!)"
    else:
        death_text = "🌅 <b>مرت الليلة بسلام، ولم يُعثر على أي ضحية.</b>"

    for actor_id, target in actions.get("spy", {}).items():
        actor = game["players"].get(actor_id)
        if not actor or not actor["alive"]:
            continue
        t = game["players"].get(target)
        if not t:
            continue
        is_evil = MF_ROLES_INFO[t["role"]]["team"] == "evil"
        if target in framed:
            is_evil = not is_evil
        result = "🔴 من عصابة المافيا! احذر منه" if is_evil else "🟢 بريء"
        try:
            bot.send_message(actor_id, f"🕵️ نتيجة تحقيقك مع {t['name']}:\n{result}", parse_mode="HTML")
        except:
            pass

    game["night_actions"] = {}

    winner = mf_check_win(game)
    if winner:
        mf_end_game(chat_id, winner, death_text)
        return

    game["phase"] = "day"
    try:
        bot.send_message(chat_id,
            f"🌅 <b>أشرقت الشمس على مدينة ريفان...</b>\n\n{death_text}\n\n{mf_roster_text(game)}\n\n"
            f"💬 وقت النقاش: {MF_PHASE_SECONDS} ثانية",
            parse_mode="HTML")
    except:
        pass

    Thread(target=mf_discussion_timer, args=(chat_id, game["round"]), daemon=True).start()


def mf_discussion_timer(chat_id, rnd):
    time.sleep(MF_PHASE_SECONDS)
    game = MAFIA_GAMES.get(chat_id)
    if game and game["phase"] == "day" and game["round"] == rnd:
        mf_start_voting(chat_id)


# ========= مرحلة التصويت =========
def mf_voting_text(game):
    tally = Counter(game["votes"].values())
    lines = []
    for pid, p in mf_alive_players(game).items():
        lines.append(f"• {p['name']} — {tally.get(pid, 0)} صوت")
    return "🗳 <b>وقت التصويت!</b>\nصوّت لطرد الشخص اللي تشك إنه من المافيا:\n\n" + "\n".join(lines)


def mf_start_voting(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "voting"
    game["votes"] = {}
    game["judge_veto_active"] = False
    rnd = game["round"]

    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in mf_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"mf_vote_{chat_id}_{rnd}_{pid}"))

    try:
        bot.send_message(chat_id, mf_voting_text(game), parse_mode="HTML", reply_markup=m)
    except:
        pass

    # ===== إرسال زر العفو الملكي سراً لأي قاضٍ حي لم يستخدمه بعد =====
    for pid, p in mf_alive_players(game).items():
        if p["role"] == "القاضي" and not game["judge_used"].get(pid):
            vm = types.InlineKeyboardMarkup(row_width=1)
            vm.add(types.InlineKeyboardButton("⚖️ استخدم العفو الملكي (يلغي نتيجة التصويت)", callback_data=f"mf_veto_{chat_id}_{rnd}"))
            try:
                bot.send_message(pid, "⚖️ أنت القاضي! تقدر تستخدم عفوك الملكي هذي الجولة لإلغاء نتيجة التصويت بالكامل (استخدام واحد طول اللعبة، اختياري):",
                                  reply_markup=vm)
            except:
                pass

    Thread(target=mf_voting_timer, args=(chat_id, rnd), daemon=True).start()


def mf_voting_timer(chat_id, rnd):
    time.sleep(MF_PHASE_SECONDS)
    game = MAFIA_GAMES.get(chat_id)
    if game and game["phase"] == "voting" and game["round"] == rnd:
        mf_resolve_voting(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mf_veto_"))
def mf_veto_callback(call):
    try:
        parts = call.data.split("_")
        chat_id = int(parts[2])
        rnd = int(parts[3])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "voting" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهى وقت استخدام العفو هذي الجولة.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"] or player["role"] != "القاضي" or game["judge_used"].get(user_id):
        bot.answer_callback_query(call.id, "⛔ ما تكدر تستخدم هذا الزر.", show_alert=True)
        return

    game["judge_used"][user_id] = True
    game["judge_veto_active"] = True
    bot.answer_callback_query(call.id, "✅ تم تفعيل العفو الملكي سراً لهذي الجولة.")
    try:
        bot.edit_message_text("✅ تم تفعيل عفوك الملكي، نتيجة التصويت هذي الجولة راح تُلغى.", call.message.chat.id, call.message.message_id)
    except:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("mf_vote_"))
def mf_vote_callback(call):
    try:
        parts = call.data.split("_")
        chat_id = int(parts[2])
        rnd = int(parts[3])
        target = int(parts[4])
    except Exception:
        bot.answer_callback_query(call.id)
        return

    game = MAFIA_GAMES.get(chat_id)
    if not game or game["phase"] != "voting" or game["round"] != rnd:
        bot.answer_callback_query(call.id, "⏰ انتهى وقت التصويت.", show_alert=True)
        return
    user_id = call.from_user.id
    player = game["players"].get(user_id)
    if not player or not player["alive"]:
        bot.answer_callback_query(call.id, "⛔ ما تكدر تصوّت (غير حي أو مو منضم).", show_alert=True)
        return

    game["votes"][user_id] = target
    bot.answer_callback_query(call.id, "✅ تم تسجيل صوتك.")
    m = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in mf_alive_players(game).items():
        m.add(types.InlineKeyboardButton(p["name"], callback_data=f"mf_vote_{chat_id}_{rnd}_{pid}"))
    try:
        bot.send_message(chat_id,
            f"🗳 صوّت {wz_mention(user_id, player['name'])}!\n\n{mf_voting_text(game)}",
            parse_mode="HTML", reply_markup=m)
    except:
        pass

    if len(game["votes"]) >= len(mf_alive_players(game)):
        mf_resolve_voting(chat_id)


def mf_resolve_voting(chat_id):
    game = MAFIA_GAMES.get(chat_id)
    if not game:
        return
    with game["lock"]:
        if game["phase"] != "voting":
            return
        game["phase"] = "resolving"

    if game.get("judge_veto_active"):
        result_text = ("⚖️ <b>استخدم أحدهم عفوه الملكي سراً!</b>\n"
                        "أُلغيت نتيجة التصويت هذي الجولة بالكامل، ولم يُطرد أحد.")
        game["judge_veto_active"] = False
        eliminated = None
    else:
        tally = Counter(game["votes"].values())
        eliminated = None
        if tally:
            top = tally.most_common()
            maxvotes = top[0][1]
            candidates = [t for t, c in top if c == maxvotes]
            if len(candidates) == 1:
                eliminated = candidates[0]
                game["players"][eliminated]["alive"] = False
                ename = game["players"][eliminated]["name"]
                erole = game["players"][eliminated]["role"]
                einfo = MF_ROLES_INFO[erole]
                result_text = (
                    f"🗳 <b>قرر السكان طرد {wz_mention(eliminated, ename)}!</b>\n\n"
                    f"📢 كشف دوره الحقيقي: {einfo['emoji']} <b>{erole}</b>"
                )
                if erole == "الملك":
                    result_text += "\n\n👑💀 <b>طردوا الملك بالخطأ! سيطرت المافيا على المدينة فوراً!</b>"
            else:
                result_text = "🤝 <b>تعادلت الأصوات بين أكثر من شخص، فما انطرد أحد هذي الجولة.</b>"
        else:
            result_text = "💤 <b>محد صوّت، فما انطرد أحد هذي الجولة.</b>"

    if eliminated is not None and game["players"][eliminated]["role"] == "الملك":
        mf_end_game(chat_id, "evil", result_text)
        return

    winner = mf_check_win(game)
    if winner:
        mf_end_game(chat_id, winner, result_text)
        return

    game["round"] += 1
    game["phase"] = "night"
    try:
        bot.send_message(chat_id, f"{result_text}\n\n{mf_roster_text(game)}", parse_mode="HTML")
    except:
        pass
    mf_start_night(chat_id)


def mf_end_game(chat_id, winner, last_event_text=""):
    game = MAFIA_GAMES.get(chat_id)
    if not game:
        return
    game["phase"] = "ended"
    winner_label = "🐺 عصابة المافيا" if winner == "evil" else "🟢 سكان مدينة ريفان"

    lines = []
    winner_mentions = []
    for pid, p in game["players"].items():
        is_evil_role = MF_ROLES_INFO[p["role"]]["team"] == "evil"
        won = is_evil_role == (winner == "evil")
        info = MF_ROLES_INFO[p["role"]]
        status = "🟢 حي" if p["alive"] else "⚰️ ميت"
        mark = "🏆" if won else "❌"
        lines.append(f"{mark} {wz_mention(pid, p['name'])} — {info['emoji']} {p['role']} ({status})")
        if won:
            winner_mentions.append(wz_mention(pid, p["name"]))
        mf_add_result(pid, p["name"], p["role"], won)

    txt = (
        f"{last_event_text}\n\n"
        f"🎉 <b>انتهت المباراة!</b>\n"
        f"🏆 <b>الفريق الفائز:</b> {winner_label}\n\n"
        f"🏆 <b>الفائزون:</b>\n" + ("\n".join(winner_mentions) if winner_mentions else "لا يوجد") + "\n\n"
        f"📈 عدد الجولات: {game['round']}\n\n"
        f"📋 <b>كشف الأدوار الكامل:</b>\n" + "\n".join(lines)
    )
    try:
        bot.send_message(chat_id, txt, parse_mode="HTML")
    except:
        pass

    add_event(chat_id, f"🐺 انتهت مباراة المافيا — الفائز: {winner_label}")
    mf_cleanup_game(chat_id)


# ================================================================




# ================================================================
# V22 - الأنظمة الجديدة الموسعة
# ================================================================
# ملاحظة: تم فصل الأنظمة الجديدة عن الأنظمة القديمة قدر الإمكان.
# لا يوجد كازينو/مقامرة في هذه النسخة.

FEATURE_VERSION = "V22-Expanded"

def _ensure_v22_global():
    DB.setdefault("v22", {})
    v = DB["v22"]
    v.setdefault("xp", {})
    v.setdefault("achievements", {})
    v.setdefault("jobs", {})
    v.setdefault("loans", {})
    v.setdefault("properties", {})
    v.setdefault("investments", {})
    v.setdefault("transfers", [])
    v.setdefault("auctions", {})
    v.setdefault("battles", {})
    v.setdefault("robbery", {})
    return v

V22_JOBS = {
    "عامل": (250, 600), "مبرمج": (500, 1200), "سائق": (350, 850),
    "طباخ": (300, 750), "محقق": (450, 1000), "مدير بنك": (700, 1600)
}
V22_ACH = {
    "messages_100": ("بداية النشاط", 100, "إرسال 100 رسالة"),
    "messages_1000": ("عضو نشيط", 500, "إرسال 1000 رسالة"),
    "money_100k": ("ثري", 1000, "جمع 100,000 دولار"),
    "money_1m": ("مليونير", 5000, "جمع 1,000,000 دولار"),
    "wins_10": ("مقاتل", 500, "الفوز في 10 معارك"),
    "wins_100": ("محترف", 3000, "الفوز في 100 معركة"),
    "marry": ("متزوج", 300, "الزواج مرة واحدة"),
    "divorce_5": ("خبرة الحياة", 500, "الطلاق 5 مرات"),
}

def v22_user(uid):
    v = _ensure_v22_global(); k = str(uid)
    u = v["xp"].setdefault(k, {"xp": 0, "level": 1, "messages": 0, "wins": 0, "losses": 0, "gold": 0})
    u.setdefault("xp", 0); u.setdefault("level", 1); u.setdefault("messages", 0)
    u.setdefault("wins", 0); u.setdefault("losses", 0); u.setdefault("gold", 0)
    return u

def v22_level(xp):
    return max(1, int(xp // 100) + 1)

def v22_add_xp(uid, amount=5):
    u=v22_user(uid); u["xp"] += amount; u["level"] = v22_level(u["xp"]); return u

def v22_bank(uid):
    return ensure_banking()["users"].get(str(uid))

def v22_money(uid):
    u=v22_bank(uid); return u.get("balance",0) if u else 0

def v22_save(): save_db()

def v22_admin(message): return is_group(message) and can_restrict(message.chat.id, message.from_user.id)

def v22_mention(uid, fallback="مستخدم"):
    try:
        cm=bot.get_chat_member(int(uid) if str(uid).lstrip('-').isdigit() else 0, int(uid))
        return f'<a href="tg://user?id={uid}">{html.escape(cm.user.first_name or fallback)}</a>'
    except: return f'<a href="tg://user?id={uid}">{fallback}</a>'

# ---------- 1) إنذارات قابلة للضبط ----------
def v22_warn_config(chat):
    cfg=chat.setdefault("warning_config", {"mute":3,"kick":5,"ban":7})
    return cfg

def v22_apply_warning(chat_id, target_id, reason=""):
    chat=ensure_chat(chat_id); cfg=v22_warn_config(chat); k=str(target_id)
    n=chat.setdefault("warnings",{}).get(k,0)+1; chat["warnings"][k]=n
    action=""
    if n >= cfg["ban"]:
        try: bot.ban_chat_member(chat_id,target_id)
        except: pass
        action="حظر"
    elif n >= cfg["kick"]:
        try: bot.ban_chat_member(chat_id,target_id); bot.unban_chat_member(chat_id,target_id)
        except: pass
        action="طرد"
    elif n >= cfg["mute"]:
        try: mute_user(chat_id,target_id)
        except: pass
        action="كتم"
    add_event(chat_id, f"⚠️ إنذار #{n} للمستخدم {target_id} {('— '+reason) if reason else ''} {('→ '+action) if action else ''}")
    save_db(); return n, action

@bot.message_handler(func=lambda m: m.text and m.text.startswith("ضبط الانذارات"))
def v22_warning_settings(message):
    if not v22_admin(message): return
    p=message.text.split()
    if len(p)!=4 or not all(x.isdigit() for x in p[1:]):
        bot.reply_to(message,"⚙️ الاستخدام: ضبط الانذارات 3 5 7\n(كتم / طرد / حظر)"); return
    a,b,c=map(int,p[1:])
    if not (1<=a<b<c<=50): bot.reply_to(message,"❌ يجب أن تكون الأرقام مرتبة: الكتم < الطرد < الحظر."); return
    v22_warn_config(ensure_chat(message.chat.id)).update(mute=a,kick=b,ban=c); save_db()
    bot.reply_to(message,f"✅ تم ضبط الإنذارات: كتم {a} / طرد {b} / حظر {c}")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="اعدادات الانذارات")
def v22_warning_show(message):
    if not is_group(message): return
    c=v22_warn_config(ensure_chat(message.chat.id)); bot.reply_to(message,f"⚙️ إنذارات المجموعة:\n🔇 كتم: {c['mute']}\n🚪 طرد: {c['kick']}\n⛔ حظر: {c['ban']}")

# ---------- 2) مكافحة الغارات ----------
def v22_raid_settings(chat):
    cfg=chat.setdefault("raid_config", {"enabled":True,"threshold":10,"window":10,"block_seconds":60})
    chat.setdefault("raid_joins",[]); chat.setdefault("raid_until",0); return cfg

def v22_raid_active(chat): return time.time() < chat.get("raid_until",0)

@bot.message_handler(content_types=["new_chat_members"])
def v22_new_members(message):
    if not is_group(message): return
    chat=ensure_chat(message.chat.id); cfg=v22_raid_settings(chat)
    now=time.time(); joins=chat.setdefault("raid_joins",[])
    joins[:]=[t for t in joins if now-t <= cfg["window"]]
    joins.extend([now]*len(message.new_chat_members))
    if cfg["enabled"] and len(joins)>=cfg["threshold"] and not v22_raid_active(chat):
        chat["raid_until"]=now+cfg["block_seconds"]; add_event(message.chat.id,f"🚨 تفعيل حماية الغارة: {len(joins)} انضمام خلال {cfg['window']} ثوانٍ")
        save_db()
        bot.send_message(message.chat.id,f"🚨 <b>تم تفعيل حماية الغارة!</b>\nتم رصد {len(joins)} انضمام سريع. سيتم تشديد المراقبة مؤقتاً.")
    if v22_raid_active(chat):
        for u in message.new_chat_members:
            try: bot.restrict_chat_member(message.chat.id,u.id,types.ChatPermissions(can_send_messages=False))
            except: pass

# ---------- 3) قفل أنواع الرسائل ----------
V22_LOCK_TYPES={"links":"روابط","photo":"صور","video":"فيديو","document":"ملفات","sticker":"ملصقات","audio":"صوتيات","animation":"GIF"}

def v22_locks(chat): return chat.setdefault("content_locks", {k:False for k in V22_LOCK_TYPES})

@bot.message_handler(func=lambda m: m.text and m.text.startswith("قفل "))
def v22_lock(message):
    if not v22_admin(message): return
    name=message.text.split(maxsplit=1)[1].strip(); rev={v:k for k,v in V22_LOCK_TYPES.items()}
    key=name if name in V22_LOCK_TYPES else rev.get(name)
    if key not in V22_LOCK_TYPES: bot.reply_to(message,"❌ الأنواع: روابط، صور، فيديو، ملفات، ملصقات، صوتيات، GIF"); return
    v22_locks(ensure_chat(message.chat.id))[key]=True; save_db(); bot.reply_to(message,f"🔒 تم قفل {V22_LOCK_TYPES[key]}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("فتح "))
def v22_unlock(message):
    if not v22_admin(message): return
    name=message.text.split(maxsplit=1)[1].strip(); rev={v:k for k,v in V22_LOCK_TYPES.items()}; key=name if name in V22_LOCK_TYPES else rev.get(name)
    if key not in V22_LOCK_TYPES: bot.reply_to(message,"❌ النوع غير معروف."); return
    v22_locks(ensure_chat(message.chat.id))[key]=False; save_db(); bot.reply_to(message,f"🔓 تم فتح {V22_LOCK_TYPES[key]}")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="اقفال المجموعة")
def v22_lock_list(message):
    if not is_group(message): return
    l=v22_locks(ensure_chat(message.chat.id)); bot.reply_to(message,"🔐 الأقفال:\n"+"\n".join(f"{'🔒' if l[k] else '🔓'} {v}" for k,v in V22_LOCK_TYPES.items()))

@bot.message_handler(content_types=["photo","video","document","sticker","audio","animation"])
def v22_media_lock(message):
    if not is_group(message): return
    l=v22_locks(ensure_chat(message.chat.id)); typ={"photo":"photo","video":"video","document":"document","sticker":"sticker","audio":"audio","animation":"animation"}.get(message.content_type)
    if typ and l.get(typ) and get_role(message.chat.id,message.from_user.id) not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        try: bot.delete_message(message.chat.id,message.message_id); add_event(message.chat.id,f"🗑 حذف {V22_LOCK_TYPES[typ]} من {message.from_user.id}")
        except: pass

@bot.message_handler(func=lambda m: m.text and ("http://" in m.text.lower() or "https://" in m.text.lower()))
def v22_link_lock(message):
    if not is_group(message): return
    l=v22_locks(ensure_chat(message.chat.id))
    if l.get("links") and get_role(message.chat.id,message.from_user.id) not in ["ادمن","مدير","منشئ","مالك","مالك اساسي","مساعد مالك"]:
        try: bot.delete_message(message.chat.id,message.message_id)
        except: pass

# ---------- 4) سجل تدقيق موسع ----------
def v22_audit(message, text):
    if is_group(message): add_event(message.chat.id, "🧾 "+text)

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="سجل التدقيق")
def v22_audit_show(message):
    if not v22_admin(message): return
    log=ensure_event_log(message.chat.id); bot.reply_to(message,"🧾 <b>سجل التدقيق</b>\n\n"+("\n".join(log[-30:]) if log else "لا يوجد سجل."))

# ---------- 4.5) سوق نادر ----------
V22_MARKET = {
    "سيف اسطوري": {"price":25000,"emoji":"⚔️"}, "درع نادر": {"price":18000,"emoji":"🛡️"},
    "سيارة نادرة": {"price":120000,"emoji":"🏎️"}, "لقب النخبة": {"price":50000,"emoji":"👑"},
    "حيوان نادر": {"price":35000,"emoji":"🐉"}, "صندوق اسطوري": {"price":75000,"emoji":"📦"}
}
@bot.message_handler(func=lambda m: m.text and m.text.strip()=="السوق")
def v22_market(message):
    lines=["🛒 <b>السوق النادر</b>",""]+[f"{x['emoji']} {name} — {x['price']:,}$" for name,x in V22_MARKET.items()]
    lines.append("\nالشراء: <code>شراء نادر اسم العنصر</code>"); bot.reply_to(message,"\n".join(lines))

@bot.message_handler(func=lambda m: m.text and m.text.startswith("شراء نادر "))
def v22_market_buy(message):
    name=message.text.split(maxsplit=2)[2]; item=V22_MARKET.get(name); b=v22_bank(message.from_user.id)
    if not item: bot.reply_to(message,"❌ العنصر غير موجود بالسوق."); return
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    if b["balance"]<item["price"]: bot.reply_to(message,"❌ رصيدك غير كافٍ."); return
    b["balance"]-=item["price"]; b.setdefault("inventory",{}); b["inventory"][name]=b["inventory"].get(name,0)+1; save_db(); bot.reply_to(message,f"✅ اشتريت {item['emoji']} {name} مقابل {item['price']:,}$")

# ---------- 5) الوظائف ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("وظيفة"))
def v22_job(message):
    uid=message.from_user.id; v=_ensure_v22_global(); k=str(uid); text=message.text.strip()
    if text=="وظيفتي":
        job=v["jobs"].get(k); bot.reply_to(message,f"💼 وظيفتك: <b>{job or 'عاطل'}</b>\nالوظائف: {', '.join(V22_JOBS)}"); return
    parts=text.split(maxsplit=1)
    if len(parts)<2 or parts[1] not in V22_JOBS: bot.reply_to(message,"💼 اختر: "+", ".join(V22_JOBS)); return
    v["jobs"][k]=parts[1]; save_db(); bot.reply_to(message,f"✅ تم تعيينك <b>{parts[1]}</b>. استخدم <code>قبض الراتب</code> للحصول على دخل الوظيفة.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="قبض الراتب")
def v22_job_salary(message):
    uid=message.from_user.id; job=_ensure_v22_global()["jobs"].get(str(uid))
    if not job: bot.reply_to(message,"⚠️ اختر وظيفة أولاً: وظيفة [الاسم]"); return
    b=v22_bank(uid)
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    now=time.time(); last=b.get("v22_last_job_salary",0)
    if now-last<3600: bot.reply_to(message,f"⏰ الراتب القادم بعد {int(3600-(now-last))//60} دقيقة."); return
    amount=random.randint(*V22_JOBS[job]); b["balance"]=min(MAX_MONEY,b["balance"]+amount); b["v22_last_job_salary"]=now; save_db(); bot.reply_to(message,f"💵 راتب {job}: +{amount:,} دولار")

# ---------- 6) قروض ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("قرض "))
def v22_loan(message):
    uid=message.from_user.id; b=v22_bank(uid)
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    p=message.text.split();
    if len(p)!=2 or not p[1].isdigit(): bot.reply_to(message,"🏦 الاستخدام: قرض 5000"); return
    amount=int(p[1]); v=_ensure_v22_global(); active=v["loans"].get(str(uid))
    if active: bot.reply_to(message,"⚠️ لديك قرض قائم بالفعل."); return
    if amount<100 or amount>max(100, b["balance"]*3): bot.reply_to(message,"❌ مبلغ القرض غير مسموح."); return
    due=time.time()+7*86400; total=int(amount*1.10); v["loans"][str(uid)]={"amount":amount,"total":total,"due":due}; b["balance"]+=amount; save_db(); bot.reply_to(message,f"🏦 تم إيداع {amount:,} دولار.\n💳 المطلوب للسداد: {total:,}\n⏳ المدة: 7 أيام")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="سداد القرض")
def v22_loan_pay(message):
    uid=message.from_user.id; v=_ensure_v22_global(); loan=v["loans"].get(str(uid)); b=v22_bank(uid)
    if not loan or not b: bot.reply_to(message,"ℹ️ لا يوجد قرض قائم."); return
    penalty=1.20 if time.time()>loan["due"] else 1.0; total=int(loan["total"]*penalty)
    if b["balance"]<total: bot.reply_to(message,f"❌ تحتاج {total-b['balance']:,} دولار إضافية."); return
    b["balance"]-=total; del v["loans"][str(uid)]; save_db(); bot.reply_to(message,f"✅ تم سداد القرض: {total:,} دولار.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="قرضي")
def v22_loan_info(message):
    loan=_ensure_v22_global()["loans"].get(str(message.from_user.id));
    if not loan: bot.reply_to(message,"🏦 لا يوجد قرض قائم."); return
    rem=max(0,int(loan["due"]-time.time())); bot.reply_to(message,f"🏦 القرض: {loan['amount']:,}\n💳 السداد: {loan['total']:,}\n⏳ المتبقي: {rem//86400} يوم و{(rem%86400)//3600} ساعة")

# ---------- 6.5) تطوير وتأجير العقارات ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("تطوير عقار "))
def v22_property_upgrade(message):
    uid=message.from_user.id; b=v22_bank(uid)
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    name=message.text.split(maxsplit=2)[2]; v=_ensure_v22_global(); props=v["properties"].setdefault(str(uid),[])
    prop=next((x for x in props if x.get("name")==name),None)
    if not prop: bot.reply_to(message,"❌ هذا العقار غير موجود في عقاراتك."); return
    cost=5000*(prop.get("level",1)+1)
    if b["balance"]<cost: bot.reply_to(message,f"❌ تحتاج {cost:,} دولار للتطوير."); return
    b["balance"]-=cost; prop["level"]=prop.get("level",1)+1; prop["value"]=int(prop.get("value",0)*1.15); save_db(); bot.reply_to(message,f"🏗️ تم تطوير {name} إلى المستوى {prop['level']}.")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تأجير عقار "))
def v22_property_rent(message):
    uid=message.from_user.id; v=_ensure_v22_global(); props=v["properties"].setdefault(str(uid),[]); name=message.text.split(maxsplit=2)[2]
    prop=next((x for x in props if x.get("name")==name),None)
    if not prop: bot.reply_to(message,"❌ العقار غير موجود."); return
    rent=int(prop.get("value",0)*0.02); b=v22_bank(uid)
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    b["balance"]=min(MAX_MONEY,b["balance"]+rent); save_db(); bot.reply_to(message,f"🏠 تم تحصيل إيجار {name}: +{rent:,} دولار.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="عقاراتي")
def v22_properties(message):
    props=_ensure_v22_global()["properties"].get(str(message.from_user.id),[])
    if not props: bot.reply_to(message,"🏠 لا توجد عقارات مطورة في نظام العقارات الجديد. يمكنك شراء العقارات من المتجر ثم تطويرها."); return
    bot.reply_to(message,"🏠 <b>عقاراتي</b>\n\n"+"\n".join(f"• {x['name']} — Lv.{x.get('level',1)} — {x.get('value',0):,}$" for x in props))

# ---------- 7) استثمار طويل الأجل ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("استثمار طويل "))
def v22_long_invest(message):
    uid=message.from_user.id; b=v22_bank(uid)
    if not b: bot.reply_to(message,"⚠️ أنشئ حساباً بنكياً أولاً."); return
    p=message.text.split();
    if len(p)!=3 or not p[2].isdigit(): bot.reply_to(message,"📈 الاستخدام: استثمار طويل 5000"); return
    amount=int(p[2]); v=_ensure_v22_global(); k=str(uid)
    if k in v["investments"]: bot.reply_to(message,"⚠️ لديك استثمار قائم."); return
    if amount<=0 or b["balance"]<amount: bot.reply_to(message,"❌ الرصيد غير كافٍ."); return
    b["balance"]-=amount; v["investments"][k]={"amount":amount,"start":time.time(),"risk":random.choice(["منخفض","متوسط","مرتفع"])}; save_db(); bot.reply_to(message,"📈 بدأ الاستثمار. استخدم <code>حصاد الاستثمار</code> بعد 24 ساعة.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="حصاد الاستثمار")
def v22_long_invest_claim(message):
    uid=message.from_user.id; v=_ensure_v22_global(); inv=v["investments"].get(str(uid)); b=v22_bank(uid)
    if not inv or not b: bot.reply_to(message,"ℹ️ لا يوجد استثمار قائم."); return
    if time.time()-inv["start"]<86400: bot.reply_to(message,"⏳ الاستثمار يحتاج 24 ساعة."); return
    rates={"منخفض":(0.02,0.08),"متوسط":(-0.05,0.18),"مرتفع":(-0.25,0.40)}; lo,hi=rates[inv["risk"]]; result=int(inv["amount"]*(1+random.uniform(lo,hi))); result=max(0,result); b["balance"]=min(MAX_MONEY,b["balance"]+result); del v["investments"][str(uid)]; save_db(); bot.reply_to(message,f"📊 نتيجة الاستثمار ({inv['risk']}): <b>{result:,}</b> دولار.")

# ---------- 8) تحويل مع تأكيد ----------
def v22_find_target(message):
    if message.reply_to_message: return message.reply_to_message.from_user.id
    p=message.text.split();
    if len(p)>=3 and p[2].startswith('@'): return find_user_id_by_username(message.chat.id,p[2][1:])
    return None

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تحويل مؤكد "))
def v22_transfer(message):
    p=message.text.split(); uid=message.from_user.id; b=v22_bank(uid); target=v22_find_target(message)
    if not b or not target: bot.reply_to(message,"💸 الرد على المستخدم ثم اكتب: تحويل مؤكد 100"); return
    try: amount=int(p[2] if p[1].startswith('@') else p[1])
    except: amount=0
    if amount<=0 or b["balance"]<amount or target==uid: bot.reply_to(message,"❌ بيانات التحويل غير صحيحة."); return
    tb=v22_bank(target)
    if not tb: bot.reply_to(message,"⚠️ المستلم يحتاج إنشاء حساب بنكي أولاً."); return
    kb=types.InlineKeyboardMarkup(); kb.row(types.InlineKeyboardButton("✅ تأكيد",callback_data=f"v22tr_yes_{uid}_{target}_{amount}"),types.InlineKeyboardButton("❌ إلغاء",callback_data="v22tr_no"))
    bot.reply_to(message,f"💸 تحويل <b>{amount:,}</b> دولار إلى المستخدم؟",reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("v22tr_"))
def v22_transfer_cb(call):
    if call.data=="v22tr_no": bot.answer_callback_query(call.id,"تم الإلغاء"); bot.edit_message_text("❌ تم إلغاء التحويل.",call.message.chat.id,call.message.message_id); return
    _,_,uid,target,amount=call.data.split("_"); uid=int(uid); target=int(target); amount=int(amount)
    if call.from_user.id!=uid: bot.answer_callback_query(call.id,"⛔ هذا الزر ليس لك.",show_alert=True); return
    b=v22_bank(uid); tb=v22_bank(target)
    if not b or not tb or b["balance"]<amount: bot.answer_callback_query(call.id,"❌ الرصيد تغير أو غير كافٍ.",show_alert=True); return
    b["balance"]-=amount; tb["balance"]+=amount; v=_ensure_v22_global(); v["transfers"].append({"from":uid,"to":target,"amount":amount,"time":now_str()}); v["transfers"]=v["transfers"][-200:]; save_db(); bot.answer_callback_query(call.id,"✅ تم التحويل"); bot.edit_message_text(f"✅ تم تحويل {amount:,} دولار بنجاح.",call.message.chat.id,call.message.message_id)

# ---------- 9) XP + الملف + الإنجازات ----------
def v22_check_achievements(uid):
    v=_ensure_v22_global(); u=v22_user(uid); b=v22_bank(uid); earned=v["achievements"].setdefault(str(uid),[]); total=b.get("balance",0) if b else 0
    checks={"messages_100":u["messages"]>=100,"messages_1000":u["messages"]>=1000,"money_100k":total>=100000,"money_1m":total>=1000000,"wins_10":u["wins"]>=10,"wins_100":u["wins"]>=100}
    for key,ok in checks.items():
        if ok and key not in earned:
            earned.append(key)
            if b: b["balance"]=min(MAX_MONEY,b["balance"]+V22_ACH[key][1])

def v22_profile_text(uid):
    u=v22_user(uid); b=v22_bank(uid); v=_ensure_v22_global(); job=v["jobs"].get(str(uid),"عاطل"); props=v["properties"].get(str(uid),[]); ach=v["achievements"].get(str(uid),[])
    return f"👤 <b>الملف الشخصي</b>\n\n⭐ المستوى: <b>{u['level']}</b>\n✨ XP: <b>{u['xp']}</b>\n💬 الرسائل: <b>{u['messages']}</b>\n💰 الرصيد: <b>{b['balance'] if b else 0:,}</b>\n🥇 الذهب: <b>{u['gold']}</b>\n💼 الوظيفة: <b>{job}</b>\n🏠 العقارات: <b>{len(props)}</b>\n⚔️ الانتصارات: <b>{u['wins']}</b>\n❌ الخسائر: <b>{u['losses']}</b>\n🏅 الإنجازات: <b>{len(ach)}</b>"

@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["ملفي","بروفايلي","انجازاتي","إنجازاتي"])
def v22_profile(message):
    if message.text.strip() in ["ملفي","بروفايلي"]: bot.reply_to(message,v22_profile_text(message.from_user.id))
    else:
        v=_ensure_v22_global(); arr=v["achievements"].get(str(message.from_user.id),[]); lines=[]
        for k,(name,reward,desc) in V22_ACH.items(): lines.append(f"{'🏆' if k in arr else '🔒'} {name} — {desc} (+{reward})")
        bot.reply_to(message,"🏅 <b>الإنجازات</b>\n\n"+"\n".join(lines))

# ---------- 10) معارك 1 ضد 1 ----------
@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("مبارزة"))
def v22_battle_start(message):
    if not is_group(message): return
    target=v22_find_target(message); uid=message.from_user.id
    if not target: bot.reply_to(message,"⚔️ رد على شخص واكتب: مبارزة"); return
    if target==uid: return
    v=_ensure_v22_global(); gid=str(message.chat.id)
    if gid in v["battles"]: bot.reply_to(message,"⚠️ توجد مبارزة قائمة."); return
    v["battles"][gid]={"p1":uid,"p2":target,"hp":{str(uid):100,str(target):100},"turn":uid}; save_db()
    kb=types.InlineKeyboardMarkup(); kb.row(types.InlineKeyboardButton("⚔️ هجوم",callback_data=f"v22atk_{message.chat.id}"))
    bot.reply_to(message,"⚔️ <b>بدأت المبارزة!</b>\n❤️ 100 / 100 لكل لاعب\nالدور للاعب الذي بدأ.",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("v22atk_"))
def v22_battle_cb(call):
    gid=call.data.split("_")[-1]; v=_ensure_v22_global(); g=v["battles"].get(gid)
    if not g or call.from_user.id!=g["turn"]: bot.answer_callback_query(call.id,"⏳ ليس دورك.",show_alert=True); return
    enemy=g["p2"] if call.from_user.id==g["p1"] else g["p1"]; dmg=random.randint(12,25); g["hp"][str(enemy)]-=dmg
    if g["hp"][str(enemy)]<=0:
        winner=call.from_user.id; loser=enemy; wu=v22_user(winner); lu=v22_user(loser); wu["wins"]+=1; lu["losses"]+=1; wu["xp"]+=50; wu["level"]=v22_level(wu["xp"]); del v["battles"][gid]; v22_check_achievements(winner); save_db(); bot.edit_message_text(f"🏆 فاز <a href=\"tg://user?id={winner}\">اللاعب</a>!\n💥 الضرر: {dmg}",call.message.chat.id,call.message.message_id); bot.answer_callback_query(call.id,"🏆 فوز!"); return
    g["turn"]=enemy; save_db(); bot.edit_message_text(f"⚔️ ضربة! الضرر {dmg}\n❤️ خصمك: {g['hp'][str(enemy)]}\n❤️ أنت: {g['hp'][str(call.from_user.id)]}",call.message.chat.id,call.message.message_id,reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⚔️ هجوم",callback_data=f"v22atk_{gid}"))); bot.answer_callback_query(call.id,"تم الهجوم")

# ---------- 11) مزاد ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("مزاد "))
def v22_auction(message):
    if not is_group(message): return
    p=message.text.split();
    if len(p)<3 or not p[-1].isdigit(): bot.reply_to(message,"🔨 الاستخدام: مزاد اسم_العنصر 1000"); return
    price=int(p[-1]); item=" ".join(p[1:-1]); v=_ensure_v22_global(); aid=str(time.time_ns()); v["auctions"][aid]={"item":item,"price":price,"leader":None,"ends":time.time()+30,"seller":message.from_user.id}; save_db()
    kb=types.InlineKeyboardMarkup(); kb.row(types.InlineKeyboardButton("💰 مزايدة +100",callback_data=f"v22bid_{aid}"))
    bot.reply_to(message,f"🔨 <b>مزاد لمدة 30 ثانية</b>\n📦 {html.escape(item)}\n💵 البداية: {price:,}",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("v22bid_"))
def v22_bid(call):
    aid=call.data[8:]; v=_ensure_v22_global(); a=v["auctions"].get(aid)
    if not a: bot.answer_callback_query(call.id,"انتهى المزاد.",show_alert=True); return
    if time.time()>a["ends"]: del v["auctions"][aid]; save_db(); bot.answer_callback_query(call.id,"انتهى المزاد.",show_alert=True); return
    b=v22_bank(call.from_user.id); new=a["price"]+100
    if not b or b["balance"]<new: bot.answer_callback_query(call.id,"رصيدك غير كافٍ.",show_alert=True); return
    a["price"]=new; a["leader"]=call.from_user.id; save_db(); bot.answer_callback_query(call.id,f"أصبحت المزايد الأعلى: {new:,}"); bot.edit_message_text(f"🔨 المزاد\n📦 {a['item']}\n💵 أعلى سعر: {new:,}\n⏳ مستمر حتى انتهاء الـ30 ثانية",call.message.chat.id,call.message.message_id,reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💰 مزايدة +100",callback_data=f"v22bid_{aid}")))

# ---------- 12) سرقة بنك كفعالية جماعية غير مؤذية ----------
@bot.message_handler(func=lambda m: m.text and m.text.strip()=="سرقة البنك")
def v22_robbery(message):
    if not is_group(message) or not games_allowed(message.chat.id): return
    add_interaction(message.chat.id, message.from_user.id)
    v=_ensure_v22_global(); gid=str(message.chat.id); g=v["robbery"].setdefault(gid,{"players":[],"started":time.time()})
    if message.from_user.id not in g["players"]: g["players"].append(message.from_user.id)
    if len(g["players"])<2: save_db(); bot.reply_to(message,"🏦 انضممت للفعالية. يحتاج الحدث لاعبين على الأقل؛ اكتب <code>سرقة البنك</code> للانضمام."); return
    prize=random.randint(500,3000); share=prize//len(g["players"])
    for uid in g["players"]:
        b=v22_bank(uid)
        if b: b["balance"]=min(MAX_MONEY,b["balance"]+share)
    add_event(message.chat.id,f"🏦 انتهت فعالية البنك بمشاركة {len(g['players'])} لاعبين")
    del v["robbery"][gid]; save_db(); bot.reply_to(message,f"🏦 انتهت الفعالية! الجائزة الإجمالية {prize:,} دولار، نصيب كل لاعب {share:,}.")

# ---------- 13) أحداث عشوائية ----------
def v22_random_event(chat_id):
    if not games_allowed(chat_id): return
    banking=ensure_banking(); candidates=[]
    for uid in list(banking.get("users",{}).keys()):
        try:
            cm=bot.get_chat_member(chat_id,int(uid));
            if cm.status not in ["left","kicked"]: candidates.append(int(uid))
        except: pass
    if not candidates: return
    uid=random.choice(candidates); b=v22_bank(uid)
    if not b:return
    amount=random.randint(200,2000); b["balance"]=min(MAX_MONEY,b["balance"]+amount); save_db(); bot.send_message(chat_id,f"🎁 <b>حدث عشوائي!</b>\nتم العثور على حقيبة مالية.\n💰 <a href=\"tg://user?id={uid}\">المستخدم</a> حصل على {amount:,} دولار.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="حدث عشوائي")
def v22_random_event_cmd(message):
    if not v22_admin(message): return
    v22_random_event(message.chat.id)

# ---------- 14) AI المجموعة ----------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("تلخيص المجموعة"))
def v22_ai_summary(message):
    if not is_group(message): return
    chat=ensure_chat(message.chat.id); msgs=chat.get("messages",{})
    recent=list(msgs.values())[-50:] if isinstance(msgs,dict) else []
    text="\n".join(str(x) for x in recent)
    if not text: bot.reply_to(message,"ℹ️ لا توجد رسائل مسجلة كفاية."); return
    try:
        user_name = human_name(message.from_user)
        user_link = f'<a href="tg://user?id={message.from_user.id}">{user_name}</a>'
        ans=ask_nawal_ai("لخص محتوى سجل المجموعة التالي باختصار واضح:\n"+text[:12000], [], message.from_user.id, user_name, user_link)
        bot.reply_to(message,"🤖 <b>ملخص المجموعة:</b>\n\n"+str(ans)[:4000])
    except Exception as e: bot.reply_to(message,"⚠️ تعذر تشغيل AI حالياً.")

@bot.message_handler(func=lambda m: m.text and m.text.strip()=="مراقبة AI")
def v22_ai_mod_toggle(message):
    if not v22_admin(message): return
    chat=ensure_chat(message.chat.id); chat["ai_moderator"]=not chat.get("ai_moderator",False); save_db(); bot.reply_to(message,"🤖 مراقبة AI: "+("مفعلة" if chat["ai_moderator"] else "متوقفة"))

# ---------- 15) توب شامل ----------
@bot.message_handler(func=lambda m: m.text and m.text.strip()=="توب شامل")
def v22_top(message):
    v=_ensure_v22_global(); rows=[]
    for uid,u in v["xp"].items(): rows.append((int(uid),u))
    rows.sort(key=lambda x:(x[1].get("level",1),x[1].get("xp",0)),reverse=True)
    out=["🏆 <b>التوب الشامل</b>"]
    for i,(uid,u) in enumerate(rows[:10],1): out.append(f"{i}. <a href=\"tg://user?id={uid}\">المستخدم</a> — Lv.{u['level']} / XP {u['xp']}")
    bot.reply_to(message,"\n".join(out))

@bot.message_handler(func=lambda m: bool(m.text) and not getattr(m.from_user,"is_bot",False))
def v22_xp_message(message):
    try:
        u=v22_add_xp(message.from_user.id,5); u["messages"]+=1; v22_check_achievements(message.from_user.id); save_db()
    except: pass


# تهيئة ميزات V24 الجديدة
ensure_whisper_store(); ensure_picture_games(); ensure_bot_admins(); DB.setdefault("picture_game_sessions", {}); DB.setdefault("picture_add_sessions", {}); DB.setdefault("started_users", {})
# حفظ التهيئة الجديدة مرة واحدة
_ensure_v22_global(); save_db()


# ========= تشغيل البوت =========
print("✅ تم تشغيل بوت ايتو V21 بنجاح!")
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    except Exception as e:
        print("Polling error:", e)
        try:
            log_error(f"Polling error: {e}")
        except: pass
        time.sleep(2)


