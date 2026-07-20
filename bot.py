import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# ─── تنظیمات ──────────────────────────────────────────────────────
CARD_NUMBER = "5859-8311-8151-0099"
CARD_OWNER  = "امیرمحمد صلواتی"
CHANNEL_ID  = os.environ.get("CHANNEL_ID", "")
ADMIN_ID    = int(os.environ.get("ADMIN_ID", "5312248314"))
ADMINS      = {ADMIN_ID: "superadmin"}

# ─── پکیج‌های ثابت ────────────────────────────────────────────────
PACKAGES = [
    (1,   "نامحدود",  3_000),
    (10,  "نامحدود",  30_000),
    (20,  "نامحدود",  60_000),
    (30,  "نامحدود",  90_000),
    (50,  "نامحدود",  150_000),
    (75,  "نامحدود",  225_000),
    (100, "نامحدود",  300_000),
]

users: dict = {}
test_configs: list = []
waiting_for_config: set = set()


# ─── ابزارهای کمکی ────────────────────────────────────────────────
def has_access(user_id: int, role: str) -> bool:
    r = ADMINS.get(user_id)
    return r == role or r == "superadmin"


def get_user(user_id: int) -> dict:
    if user_id not in users:
        users[user_id] = {"purchases": [], "points": 0, "pending": None, "wallet": 0}
    elif "wallet" not in users[user_id]:
        users[user_id]["wallet"] = 0
    return users[user_id]


def payment_text(gb: int, time_label: str, price: int) -> str:
    return (
        f"✅ انتخاب شما: {gb} گیگ — {time_label}\n"
        f"💰 قیمت کل: {price:,} تومان\n\n"
        f"💳 شماره کارت (برای کپی روش بزن):\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_OWNER}\n\n"
        f"بعد از پرداخت، لطفاً عکس رسید رو ارسال کنید."
    )


# ─── بررسی عضویت کانال ────────────────────────────────────────────
async def check_membership(bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        chat = int(CHANNEL_ID) if CHANNEL_ID.lstrip("-").isdigit() else CHANNEL_ID
        member = await bot.get_chat_member(chat, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True


# ─── دکمه بازگشت ──────────────────────────────────────────────────
BACK_MAIN = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="back_main")]]


# ─── کیبورد جدول پکیج‌های ثابت ───────────────────────────────────
def get_package_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    # هدر
    buttons.append([
        InlineKeyboardButton("📦 حجم",  callback_data="noop"),
        InlineKeyboardButton("⏱ زمان",  callback_data="noop"),
        InlineKeyboardButton("💰 قیمت", callback_data="noop"),
    ])
    # ردیف هر پکیج
    for gb, time_label, price in PACKAGES:
        buttons.append([
            InlineKeyboardButton(f"{gb} گیگ",          callback_data=f"pkg_{gb}"),
            InlineKeyboardButton(f"{time_label}",       callback_data=f"pkg_{gb}"),
            InlineKeyboardButton(f"{price:,} T",        callback_data=f"pkg_{gb}"),
        ])
    # خرید سفارشی
    buttons.append([InlineKeyboardButton("🛍 خرید سفارشی (حجم و زمان دلخواه)", callback_data="buy_custom")])
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# ─── کیبورد انتخاب حجم (برای خرید سفارشی) ───────────────────────
def get_volume_keyboard() -> InlineKeyboardMarkup:
    buttons, row = [], []
    for gb in range(5, 105, 5):
        row.append(InlineKeyboardButton(f"{gb} گیگ", callback_data=f"vol_{gb}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="buy_server")])
    return InlineKeyboardMarkup(buttons)


# ─── کیبورد انتخاب ماه ────────────────────────────────────────────
def get_month_keyboard(volume: int) -> InlineKeyboardMarkup:
    buttons, row = [], []
    for m in range(1, 7):
        row.append(InlineKeyboardButton(f"{m} ماه", callback_data=f"mon_{volume}_{m}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="buy_server")])
    return InlineKeyboardMarkup(buttons)


# ─── منوی اصلی ───────────────────────────────────────────────────
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ساخت اکانت",           callback_data="buy_server")],
        [InlineKeyboardButton("⚙️ حساب کاربری",          callback_data="account"),
         InlineKeyboardButton("🏦 کیف پول",              callback_data="wallet")],
        [InlineKeyboardButton("💡 آموزش ها",             callback_data="tutorials"),
         InlineKeyboardButton("👨‍💻 پشتیبانی",            callback_data="support")],
        [InlineKeyboardButton("🤖 ربات استعلام",         callback_data="inquiry_bot"),
         InlineKeyboardButton("📱 اپل ایدی",             callback_data="apple_id")],
        [InlineKeyboardButton("🗂 مدیریت اشتراک ها",     callback_data="manage_subs")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    get_user(user_id)

    if not await check_membership(context.bot, user_id):
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/bestvpn028")
        ]])
        msg = "❌ برای استفاده از ربات باید عضو کانال شوید."
        if update.message:
            await update.message.reply_text(msg, reply_markup=kb)
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=kb)
        return

    text = "به ربات 💎 Best VPN خوش اومدی!\nلطفاً یکی از گزینه‌ها رو انتخاب کن:"
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard())


# ─── دکمه‌های اینلاین ─────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    if not await check_membership(context.bot, user_id):
        await query.answer("❌ ابتدا عضو کانال شوید.", show_alert=True)
        return

    # ── noop (هدر جدول) ───────────────────────────────────────────
    if data == "noop":
        return

    # ── بازگشت به منوی اصلی ───────────────────────────────────────
    if data == "back_main":
        await start(update, context)

    # ── خرید سرور: جدول پکیج‌ها ──────────────────────────────────
    elif data == "buy_server":
        context.user_data.clear()
        await query.edit_message_text(
            "🛒 خرید سریع\n\nیک پکیج انتخاب کن:",
            reply_markup=get_package_keyboard()
        )

    # ── انتخاب پکیج ثابت ──────────────────────────────────────────
    elif data.startswith("pkg_"):
        gb = int(data.split("_")[1])
        pkg = next((p for p in PACKAGES if p[0] == gb), None)
        if not pkg:
            return
        gb, time_label, price = pkg
        get_user(user_id)["pending"] = {"volume": gb, "months": None, "time_label": time_label, "price": price}
        context.user_data["buying"] = True
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="buy_server")]])
        await query.edit_message_text(
            payment_text(gb, time_label, price),
            parse_mode="Markdown",
            reply_markup=kb
        )

    # ── خرید سفارشی ───────────────────────────────────────────────
    elif data == "buy_custom":
        await query.edit_message_text(
            "📦 لطفاً حجم مورد نظر رو انتخاب کن:",
            reply_markup=get_volume_keyboard()
        )

    # ── انتخاب حجم سفارشی ────────────────────────────────────────
    elif data.startswith("vol_"):
        volume = int(data.split("_")[1])
        context.user_data["gb"] = volume
        await query.edit_message_text(
            f"📦 حجم انتخابی: {volume} گیگ\nحالا مدت زمان رو انتخاب کن:",
            reply_markup=get_month_keyboard(volume)
        )

    # ── انتخاب ماه سفارشی → پرداخت ──────────────────────────────
    elif data.startswith("mon_"):
        _, volume, months = data.split("_")
        volume, months = int(volume), int(months)
        price = volume * 10_000 + (months - 1) * 15_000
        get_user(user_id)["pending"] = {"volume": volume, "months": months, "time_label": f"{months} ماه", "price": price}
        context.user_data["buying"] = True
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="buy_server")]])
        await query.edit_message_text(
            payment_text(volume, f"{months} ماه", price),
            parse_mode="Markdown",
            reply_markup=kb
        )

    # ── حساب کاربری ───────────────────────────────────────────────
    elif data == "account":
        u = get_user(user_id)
        count = len(u["purchases"])
        points = u["points"]
        last = "—"
        if u["purchases"]:
            p = u["purchases"][-1]
            last = f"{p['volume']} گیگ — {p.get('time_label', '')}"
        text = (
            f"👤 حساب کاربری\n"
            f"━━━━━━━━━━━━━━\n"
            f"🆔 شناسه: `{user_id}`\n"
            f"🛒 تعداد خرید: {count}\n"
            f"🎁 امتیاز وفاداری: {points}\n"
            f"📦 آخرین سرویس: {last}"
        )
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(BACK_MAIN))

    # ── کیف پول ───────────────────────────────────────────────────
    elif data == "wallet":
        balance = get_user(user_id).get("wallet", 0)
        await query.edit_message_text(
            f"🏦 کیف پول شما\n━━━━━━━━━━━━━━\n💵 موجودی: {balance:,} تومان\n\n"
            f"برای شارژ کیف پول با پشتیبانی تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ── پشتیبانی ──────────────────────────────────────────────────
    elif data == "support":
        context.user_data["support"] = True
        await query.edit_message_text(
            "💬 پیام خود را بنویسید تا به مدیر منتقل شود:",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ── آموزش ها ──────────────────────────────────────────────────
    elif data == "tutorials":
        await query.edit_message_text(
            "💡 آموزش ها\n━━━━━━━━━━━━━━\nبه زودی آموزش‌های اتصال به سرور اینجا قرار می‌گیرد.",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ── ربات استعلام ──────────────────────────────────────────────
    elif data == "inquiry_bot":
        await query.edit_message_text(
            "🤖 ربات استعلام\n━━━━━━━━━━━━━━\nبه زودی فعال می‌شود.",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ── اپل ایدی ──────────────────────────────────────────────────
    elif data == "apple_id":
        await query.edit_message_text(
            "📱 اپل ایدی\n━━━━━━━━━━━━━━\nبرای خرید اپل ایدی با پشتیبانی تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ── مدیریت اشتراک ها ──────────────────────────────────────────
    elif data == "manage_subs":
        await query.edit_message_text(
            "🗂 مدیریت اشتراک ها\n━━━━━━━━━━━━━━\nبه زودی فعال می‌شود.",
            reply_markup=InlineKeyboardMarkup(BACK_MAIN)
        )

    # ─── پنل ادمین ────────────────────────────────────────────────
    elif data == "add_test":
        if not has_access(user_id, "superadmin"):
            return
        waiting_for_config.add(user_id)
        await query.edit_message_text("لطفاً کانفیگ تستی جدید رو ارسال کن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="testpanel_menu")]]))

    elif data == "list_test":
        if not has_access(user_id, "superadmin"):
            return
        txt = "📭 هیچ کانفیگ تستی موجود نیست." if not test_configs else \
              "📋 لیست کانفیگ‌های تستی:\n\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(test_configs, 1))
        await query.edit_message_text(txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="testpanel_menu")]]))

    elif data == "remove_test":
        if not has_access(user_id, "superadmin"):
            return
        test_configs.clear()
        await query.edit_message_text("🗑 همه کانفیگ‌های تستی حذف شدند.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="testpanel_menu")]]))

    elif data == "testpanel_menu":
        if not has_access(user_id, "superadmin"):
            return
        keyboard = [
            [InlineKeyboardButton("➕ افزودن کانفیگ تستی", callback_data="add_test")],
            [InlineKeyboardButton("📋 لیست کانفیگ‌ها",     callback_data="list_test")],
            [InlineKeyboardButton("🗑 حذف همه کانفیگ‌ها",  callback_data="remove_test")],
        ]
        await query.edit_message_text("🔧 پنل مدیریت کانفیگ تستی:", reply_markup=InlineKeyboardMarkup(keyboard))


# ─── پنل ادمین ────────────────────────────────────────────────────
async def test_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.message.from_user.id, "superadmin"):
        await update.message.reply_text("❌ دسترسی ندارید.")
        return
    keyboard = [
        [InlineKeyboardButton("➕ افزودن کانفیگ تستی", callback_data="add_test")],
        [InlineKeyboardButton("📋 لیست کانفیگ‌ها",     callback_data="list_test")],
        [InlineKeyboardButton("🗑 حذف همه کانفیگ‌ها",  callback_data="remove_test")],
    ]
    await update.message.reply_text("🔧 پنل مدیریت کانفیگ تستی:", reply_markup=InlineKeyboardMarkup(keyboard))


# ─── شارژ کیف پول توسط ادمین ─────────────────────────────────────
async def addwallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.message.from_user.id, "superadmin"):
        return
    args = context.args
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.message.reply_text("استفاده: /addwallet [user_id] [مبلغ تومان]")
        return
    target_id, amount = int(args[0]), int(args[1])
    get_user(target_id)["wallet"] += amount
    bal = get_user(target_id)["wallet"]
    await update.message.reply_text(f"✅ {amount:,} تومان به کیف پول کاربر {target_id} اضافه شد.\nموجودی جدید: {bal:,} تومان")
    await context.bot.send_message(chat_id=target_id,
        text=f"💰 {amount:,} تومان به کیف پول شما اضافه شد.\nموجودی فعلی: {bal:,} تومان")


# ─── پردازش پیام‌های متنی و عکس ──────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.message.from_user
    user_id = user.id
    text    = update.message.text or ""

    # ── ادمین: ذخیره کانفیگ تستی ─────────────────────────────────
    if user_id in waiting_for_config:
        waiting_for_config.discard(user_id)
        test_configs.append(text)
        await update.message.reply_text("✅ کانفیگ تستی ذخیره شد.")
        return

    # ── ادمین: تأیید یا رد رسید با reply ─────────────────────────
    if user_id in ADMINS and update.message.reply_to_message:
        replied = update.message.reply_to_message
        if replied.forward_from:
            target_id = replied.forward_from.id
            if text.strip() == "تأیید":
                u = get_user(target_id)
                if u["pending"]:
                    u["purchases"].append(u["pending"])
                    u["points"] += 10
                    u["pending"] = None
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=f"✅ پرداخت شما تأیید شد. سرویس فعال گردید.\n🎁 امتیاز وفاداری: {u['points']}"
                    )
                await update.message.reply_text("✅ سرویس فعال شد.")
                return
            elif text.strip() == "رد":
                await context.bot.send_message(chat_id=target_id,
                    text="❌ پرداخت شما رد شد. لطفاً دوباره بررسی کنید.")
                await update.message.reply_text("❌ سرویس رد شد.")
                return

    # ── دریافت رسید عکس ───────────────────────────────────────────
    if update.message.photo:
        if context.user_data.get("buying"):
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id,
                caption=f"📥 رسید از @{user.username or user_id}")
            await update.message.reply_text("✅ رسید ثبت شد. بعد از بررسی سرویس ارسال می‌شود.")
            context.user_data.clear()
        else:
            await update.message.reply_text("⚠️ ابتدا /start بزنید و پلن انتخاب کنید.")
        return

    # ── پشتیبانی ─────────────────────────────────────────────────
    if context.user_data.get("support"):
        await context.bot.send_message(chat_id=ADMIN_ID,
            text=f"📩 پشتیبانی از @{user.username or user_id}:\n{text}")
        await update.message.reply_text("✅ پیام برای پشتیبانی ارسال شد.")
        context.user_data.clear()
        return

    if context.user_data.get("buying"):
        await update.message.reply_text("❌ لطفاً عکس رسید را ارسال کنید.")
        return

    await update.message.reply_text("⚠️ ابتدا /start بزنید.")


# ─── /chatid برای ادمین ───────────────────────────────────────────
async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        return
    chat = update.effective_chat
    await update.message.reply_text(
        f"🆔 Chat ID: `{chat.id}`\nنوع: {chat.type}\nنام: {chat.title or chat.username or '—'}",
        parse_mode="Markdown"
    )


# ─── اجرا ────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start",      start))
app.add_handler(CommandHandler("testpanel",  test_panel))
app.add_handler(CommandHandler("addwallet",  addwallet_cmd))
app.add_handler(CommandHandler("chatid",     chatid_cmd))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

print("Bot is running...")
app.run_polling()
