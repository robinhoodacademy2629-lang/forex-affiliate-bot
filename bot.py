import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BASE_URL = os.environ.get("BASE_URL", "")  # Railway URL жнь: https://forex-bot.railway.app
XM_LINK = os.environ.get("XM_LINK", "")   # Таны XM affiliate link
PORT = int(os.environ.get("PORT", 8080))

# ─── Data Storage (JSON файл) ──────────────────────────────────
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "clicks": [],
        "messages": {
            "0": None,  # Welcome
            "1": None,  # 1 хоног
            "2": None,  # 3 хоног
            "3": None,  # 7 хоног
        },
        "stats": {"total": 0, "clicks": 0, "conversions": 0}
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Default Messages ──────────────────────────────────────────
def get_messages():
    data = load_data()
    redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK

    defaults = [
        f"""👋 Сайн байна уу! Forex арилжааны дэлхийд тавтай морил!

Би танд:
✅ Өдөр бүрийн market шинжилгээ
✅ EUR/USD, Gold сигнал
✅ Эхлэгчдэд гарын авлага

...хүргэх болно!

🚀 Эхлэхийн тулд XM-д ҮНЭГҮЙ бүртгүүлнэ үү:
👉 {redirect}

Асуулт байвал хэзээ ч бичээрэй! 💬""",

        f"""📊 Forex-д амжилттай трейдерүүдийн нийтлэг 3 алдаа:

❌ Хэт их leverage ашиглах
❌ Stop loss тавихгүй арилжаалах
❌ Мэдрэмжээр шийдвэр гаргах

Эдгээрээс зайлсхийхийн тулд XM-ийн ҮНЭГҮЙ demo account-аас эхэл:
👉 {redirect}

Demo дээр дадлага → бодит мөнгөөр итгэлтэй! 💪""",

        f"""🔥 Энэ долоо хоногийн шинжилгээ:

EUR/USD чухал support level-д байна.

📈 Чиглэл: BUY
🎯 Entry: 1.0840
🛡️ Stop Loss: 1.0790
✅ Target: 1.0930

⚠️ Боловсролын зорилготой.

XM дээр арилжаалахын тулд:
👉 {redirect}""",

        f"""💎 7 хоногийн дараа та манай community-д байгаа!

Одоог хүртэл бүртгүүлээгүй бол яарна уу:

🎁 Welcome bonus
📚 Үнэгүй Forex course

Зөвхөн энэ холбоосоор:
👉 {redirect}

Санал хязгаарлагдмал! ⏰"""
    ]

    result = []
    for i, default in enumerate(defaults):
        custom = data["messages"].get(str(i))
        result.append(custom if custom else default)
    return result

# ─── Schedule helpers ──────────────────────────────────────────
SCHEDULE_DAYS = [0, 1, 3, 7]  # Өдрүүд

async def schedule_messages(app, chat_id: int):
    """Хэрэглэгчид хойшлогдсон мессеж явуулах"""
    msgs = get_messages()
    delays_seconds = [
        0,           # Шууд
        86400,       # 1 өдөр
        259200,      # 3 өдөр
        604800,      # 7 өдөр
    ]
    for i, delay in enumerate(delays_seconds):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            await app.bot.send_message(chat_id=chat_id, text=msgs[i])
            logger.info(f"Мессеж {i+1} → {chat_id} илгээгдлээ")
            # Update step
            data = load_data()
            if str(chat_id) in data["users"]:
                data["users"][str(chat_id)]["step"] = i + 1
                save_data(data)
        except Exception as e:
            logger.error(f"Мессеж илгээхэд алдаа: {e}")

# ─── Handlers ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name or "Хэрэглэгч"

    data = load_data()

    if str(chat_id) not in data["users"]:
        data["users"][str(chat_id)] = {
            "name": name,
            "chat_id": chat_id,
            "joined": datetime.now().isoformat(),
            "step": 0,
            "clicked": False,
            "converted": False,
        }
        data["stats"]["total"] += 1
        save_data(data)
        logger.info(f"Шинэ хэрэглэгч: {name} ({chat_id})")

        # Admin-д мэдэгдэл
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🆕 Шинэ хэрэглэгч!\n👤 {name}\n🆔 {chat_id}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            except:
                pass

        # Мессеж дараалал эхлүүлэх
        asyncio.create_task(schedule_messages(context.application, chat_id))
    else:
        msgs = get_messages()
        await update.message.reply_text(msgs[0])

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /stats"""
    if update.effective_chat.id != ADMIN_ID:
        return
    data = load_data()
    s = data["stats"]
    total = s.get("total", 0)
    clicks = s.get("clicks", 0)
    convs = s.get("conversions", 0)
    ctr = round((clicks / total * 100), 1) if total > 0 else 0
    cvr = round((convs / clicks * 100), 1) if clicks > 0 else 0
    revenue = convs * 30

    text = f"""📊 СТАТИСТИК
{'─'*25}
👥 Нийт хэрэглэгч: {total}
🔗 Link дарсан: {clicks} ({ctr}%)
✅ Бүртгүүлсэн: {convs} ({cvr}%)
💰 Орлого (est): ${revenue}
{'─'*25}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
    await update.message.reply_text(text)

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /broadcast текст"""
    if update.effective_chat.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /broadcast Энд мессежээ бичнэ үү")
        return

    text = " ".join(context.args)
    data = load_data()
    users = data["users"]

    if not users:
        await update.message.reply_text("⚠️ Хэрэглэгч байхгүй байна")
        return

    sent = 0
    failed = 0
    for uid, u in users.items():
        try:
            await context.bot.send_message(chat_id=u["chat_id"], text=text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1

    await update.message.reply_text(f"✅ Broadcast дууслаа\n📤 Илгээгдсэн: {sent}\n❌ Амжилтгүй: {failed}")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /signal EURUSD BUY 1.0850 1.0790 1.0930"""
    if update.effective_chat.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "⚠️ Хэрэглээ:\n/signal EURUSD BUY 1.0850 1.0790 1.0930\n\n"
            "Дараалал: Хос Чиглэл Entry StopLoss TakeProfit"
        )
        return

    pair, direction, entry, sl, tp = args[0], args[1], args[2], args[3], args[4]
    redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK
    emoji = "📈" if direction.upper() == "BUY" else "📉"

    signal_text = f"""📊 FOREX СИГНАЛ
{'─'*22}
💱 Хос: {pair.upper()}
📌 Чиглэл: {direction.upper()} {emoji}
🎯 Entry: {entry}
🛡️ Stop Loss: {sl}
✅ Take Profit: {tp}
{'─'*22}
⚠️ Боловсролын зорилготой.

🚀 XM дээр арилжаалах:
👉 {redirect}"""

    # Preview admin-д
    keyboard = [[
        InlineKeyboardButton("✅ Бүгдэд илгээх", callback_data="confirm_signal"),
        InlineKeyboardButton("❌ Цуцлах", callback_data="cancel_signal")
    ]]
    context.user_data["pending_signal"] = signal_text
    await update.message.reply_text(
        f"📋 Preview:\n\n{signal_text}\n\n{'─'*22}\nИлгээх үү?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /edit1 /edit2 /edit3 /edit4"""
    if update.effective_chat.id != ADMIN_ID:
        return
    cmd = update.message.text.strip()
    idx_map = {"/edit1": 0, "/edit2": 1, "/edit3": 2, "/edit4": 3}
    labels = ["Welcome (Шууд)", "1 өдрийн дараа", "3 өдрийн дараа", "7 өдрийн дараа"]

    idx = idx_map.get(cmd.split()[0])
    if idx is None:
        return

    if len(cmd.split()) == 1:
        msgs = get_messages()
        await update.message.reply_text(
            f"✏️ {labels[idx]} мессежийг засварлах:\n\n"
            f"Одоогийн текст:\n{'─'*20}\n{msgs[idx]}\n{'─'*20}\n\n"
            f"Шинэ текст илгээнэ үү (дараагийн мессежийг):"
        )
        context.user_data["editing"] = idx
    else:
        new_text = " ".join(cmd.split()[1:])
        data = load_data()
        data["messages"][str(idx)] = new_text
        save_data(data)
        await update.message.reply_text(f"✅ {labels[idx]} мессеж хадгалагдлаа!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ерөнхий мессеж боловсруулах"""
    chat_id = update.effective_chat.id

    # Admin editing mode
    if chat_id == ADMIN_ID and "editing" in context.user_data:
        idx = context.user_data.pop("editing")
        labels = ["Welcome (Шууд)", "1 өдрийн дараа", "3 өдрийн дараа", "7 өдрийн дараа"]
        new_text = update.message.text
        data = load_data()
        data["messages"][str(idx)] = new_text
        save_data(data)
        await update.message.reply_text(f"✅ {labels[idx]} мессеж хадгалагдлаа!\n\nПревью:\n{new_text}")
        return

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button callbacks"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_signal":
        signal_text = context.user_data.get("pending_signal")
        if not signal_text:
            await query.edit_message_text("⚠️ Сигнал олдсонгүй")
            return
        data = load_data()
        users = data["users"]
        sent = 0
        for uid, u in users.items():
            try:
                await context.bot.send_message(chat_id=u["chat_id"], text=signal_text)
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await query.edit_message_text(f"✅ Сигнал {sent} хүнд илгээгдлээ!")

    elif query.data == "cancel_signal":
        await query.edit_message_text("❌ Сигнал цуцлагдлаа")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /help"""
    if update.effective_chat.id != ADMIN_ID:
        return
    text = """🤖 ADMIN КОМАНДУУД
{'─'*25}
📊 /stats — Статистик харах

📢 /broadcast текст — Бүгдэд мессеж
   Жнь: /broadcast Шинэ сигнал гарлаа!

📈 /signal хос чиглэл entry sl tp
   Жнь: /signal EURUSD BUY 1.0850 1.0790 1.0930

✏️ Мессеж засварлах:
   /edit1 — Welcome мессеж
   /edit2 — 1 өдрийн мессеж
   /edit3 — 3 өдрийн мессеж
   /edit4 — 7 өдрийн мессеж

   Жнь: /edit1 (мессеж тохируулах горимд орно)
   Дараа нь шинэ текстийг бичнэ"""
    await update.message.reply_text(text)

# ─── Click tracking web server ────────────────────────────────
async def handle_click(request):
    """Link дарсан үед бүртгэх + redirect"""
    campaign = request.match_info.get("campaign", "xm")
    user_id = request.rel_url.query.get("uid", "unknown")

    data = load_data()
    data["stats"]["clicks"] = data["stats"].get("clicks", 0) + 1
    data["clicks"].append({
        "time": datetime.now().isoformat(),
        "user_id": user_id,
        "campaign": campaign
    })

    # Хэрэглэгч дарсан гэж тэмдэглэх
    if user_id in data["users"]:
        data["users"][user_id]["clicked"] = True

    save_data(data)
    logger.info(f"Click: {campaign} from {user_id}")

    # XM руу redirect
    raise web.HTTPFound(XM_LINK or "https://www.xm.com")

async def handle_converted(request):
    """Бүртгүүлсэн үед бүртгэх"""
    user_id = request.rel_url.query.get("uid", "unknown")
    data = load_data()
    data["stats"]["conversions"] = data["stats"].get("conversions", 0) + 1
    if user_id in data["users"]:
        data["users"][user_id]["converted"] = True
    save_data(data)
    return web.Response(text="✅ Амжилттай бүртгэгдлээ!")

async def handle_health(request):
    return web.Response(text="OK")

# ─── Main ─────────────────────────────────────────────────────
async def main():
    # Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("edit1", edit_cmd))
    app.add_handler(CommandHandler("edit2", edit_cmd))
    app.add_handler(CommandHandler("edit3", edit_cmd))
    app.add_handler(CommandHandler("edit4", edit_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Web server (click tracking)
    web_app = web.Application()
    web_app.router.add_get("/click/{campaign}", handle_click)
    web_app.router.add_get("/converted", handle_converted)
    web_app.router.add_get("/health", handle_health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

    # Bot polling эхлүүлэх
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot started!")

    # Байнга ажиллах
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
