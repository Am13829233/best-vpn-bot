import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ADMIN_ID = 5312248314
CARD_NUMBER = "5859-8311-8151-0099"
CARD_OWNER = "امیرمحمد صلواتی"

# قیمت پایه: هر گیگ ۱۰،۰۰۰ تومان در ماه
# به ازای هر ماه اضافه‌تر از ماه اول، ۱۵،۰۰۰ تومان اضافه می‌شه
PRICE_PER_GB = 10_000
EXTRA_PER_MONTH = 15_000

PLANS = {
    "10":  {"gb": 10,  "price": 100_000},
    "20":  {"gb": 20,  "price": 200_000},
    "50":  {"gb": 50,  "price": 500_000},
    "100": {"gb": 100, "price": 1_000_000},
}

def calc_price(gb: int, months: int) -> int:
    base = gb * PRICE_PER_GB
    return base + (months - 1) * EXTRA_PER_MONTH

def payment_text(gb, months, price):
    return (
        f"✅ پلن انتخابی: {gb} گیگ — {months} ماهه\n"
        f"💰 قیمت کل: {price:,} تومان\n\n"
        f"💳 شماره کارت (برای کپی روش بزن):\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_OWNER}\n\n"
        f"بعد از پرداخت، لطفاً عکس رسید رو ارسال کنید."
    )

# ─── منوی اصلی ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🛒 خرید سرور", callback_data="buy_server")],
        [InlineKeyboardButton("💬 پشتیبانی", callback_data="support")],
        [InlineKeyboardButton("ℹ️ درباره ما", callback_data="about")],
    ]
    text = "به ربات 💎 Best VPN خوش اومدی!\nلطفاً یکی از گزینه‌ها رو انتخاب کن:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ─── دکمه‌ها ─────────────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # منوی انتخاب پلن
    if data == "buy_server":
        keyboard = [
            [InlineKeyboardButton("🔹 10 گیگ — 100,000 تومان", callback_data="plan_10")],
            [InlineKeyboardButton("🔹 20 گیگ — 200,000 تومان", callback_data="plan_20")],
            [InlineKeyboardButton("🔹 50 گیگ — 500,000 تومان", callback_data="plan_50")],
            [InlineKeyboardButton("🔹 100 گیگ — 1,000,000 تومان", callback_data="plan_100")],
            [InlineKeyboardButton("⚙️ پلن سفارشی", callback_data="plan_custom")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="back_main")],
        ]
        await query.edit_message_text(
            "💳 لطفاً یکی از تعرفه‌ها رو انتخاب کن:\n(همه پلن‌ها یک‌ماهه هستن — برای چند ماهه از «پلن سفارشی» استفاده کن)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # پلن‌های آماده
    elif data.startswith("plan_") and data != "plan_custom":
        key = data.replace("plan_", "")
        plan = PLANS.get(key)
        if plan:
            context.user_data["buying"] = True
            await query.edit_message_text(
                payment_text(plan["gb"], 1, plan["price"]),
                parse_mode="Markdown"
            )

    # پلن سفارشی — مرحله اول
    elif data == "plan_custom":
        context.user_data["custom"] = True
        context.user_data["custom_step"] = "gb"
        await query.edit_message_text(
            "⚙️ پلن سفارشی\n\nچند گیگ می‌خوای؟ (عدد بنویس، مثلاً: 30)"
        )

    # پشتیبانی
    elif data == "support":
        context.user_data["support"] = True
        await query.edit_message_text("💬 لطفاً پیام خود را ارسال کنید تا به مدیر منتقل شود.")

    # درباره ما
    elif data == "about":
        keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="back_main")]]
        await query.edit_message_text(
            "💎 Best VPN\nارائه‌دهنده‌ی سرورهای پرسرعت و امن برای تمام دستگاه‌ها.\nپشتیبانی ۲۴ ساعته و تحویل فوری سرویس.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # بازگشت به منوی اصلی
    elif data == "back_main":
        await start(update, context)

# ─── پردازش پیام‌های متنی و عکس ─────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text or ""

    # پلن سفارشی — مرحله گیگ
    if context.user_data.get("custom") and context.user_data.get("custom_step") == "gb":
        if text.isdigit() and int(text) > 0:
            context.user_data["custom_gb"] = int(text)
            context.user_data["custom_step"] = "months"
            await update.message.reply_text(
                f"✅ {text} گیگ انتخاب شد.\n\nچند ماهه می‌خوای؟ (عدد بنویس، مثلاً: 3)"
            )
        else:
            await update.message.reply_text("❌ لطفاً یک عدد صحیح وارد کن (مثلاً: 30)")

    # پلن سفارشی — مرحله ماه
    elif context.user_data.get("custom") and context.user_data.get("custom_step") == "months":
        if text.isdigit() and int(text) > 0:
            gb = context.user_data["custom_gb"]
            months = int(text)
            price = calc_price(gb, months)
            context.user_data.clear()
            context.user_data["buying"] = True
            await update.message.reply_text(
                payment_text(gb, months, price),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ لطفاً یک عدد صحیح وارد کن (مثلاً: 3)")

    # دریافت رسید
    elif context.user_data.get("buying"):
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=file_id,
                caption=f"📥 رسید پرداخت جدید از کاربر: {user.username or user.id}"
            )
            await update.message.reply_text("✅ رسید شما ثبت شد. بعد از بررسی، سرویس برایتان ارسال می‌شود.")
            context.user_data.clear()
        else:
            await update.message.reply_text("❌ لطفاً عکس رسید پرداخت را ارسال کنید.")

    # پیام پشتیبانی
    elif context.user_data.get("support"):
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 پیام پشتیبانی از کاربر {user.username or user.id}:\n{text}"
        )
        await update.message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.")
        context.user_data.clear()

    else:
        await update.message.reply_text("⚠️ ابتدا دستور /start را بزنید و گزینه مورد نظر را انتخاب کنید.")

# ─── اجرا ────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

print("Bot is running...")
app.run_polling()
