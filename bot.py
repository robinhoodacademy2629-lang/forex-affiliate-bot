import os
import json
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
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
BASE_URL = os.environ.get("BASE_URL", "")
XM_LINK = os.environ.get("XM_LINK", "")
SIGNAL_GROUP_ID = int(os.environ.get("SIGNAL_GROUP_ID", "0"))  # Хаалттай группын ID
PORT = int(os.environ.get("PORT", 8080))

# ─── Data ─────────────────────────────────────────────────────
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "pending": {},   # XM ID шалгагдаж байгаа хүмүүс
        "approved": {},  # Баталгаажсан хүмүүс
        "clicks": [],
        "messages": {"0": None, "1": None, "2": None, "3": None},
        "stats": {"total": 0, "clicks": 0, "conversions": 0}
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Messages ─────────────────────────────────────────────────
def get_messages():
    data = load_data()
    redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK

    defaults = [
        f"""👋 Сайн байна уу! Forex арилжааны дэлхийд тавтай морил!

Би танд:
✅ Өдөр бүрийн market шинжилгээ
✅ EUR/USD, Gold сигнал
✅ Хаалттай сигнал группэд нэвтрэх эрх

🚀 Эхлэхийн тулд XM-д ҮНЭГҮЙ бүртгүүлнэ үү:
👉 {redirect}

⭐ Бүртгүүлсний дараа XM ID-гаа илгээвэл хаалттай сигнал группэд нэмэгдэнэ!

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

🔐 Бүрэн сигнал авахын тулд хаалттай группэд нэр бүртгүүлээрэй:
👉 {redirect}""",

        f"""💎 7 хоногийн дараа та манай community-д байгаа!

Одоог хүртэл бүртгүүлээгүй бол яарна уу:
🎁 Welcome bonus
📚 Үнэгүй Forex course
🔐 Хаалттай сигнал группэд нэвтрэх эрх

👉 {redirect}

Санал хязгаарлагдмал! ⏰"""
    ]

    result = []
    for i, default in enumerate(defaults):
        custom = data["messages"].get(str(i))
        result.append(custom if custom else default)
    return result

# ─── Schedule ─────────────────────────────────────────────────
async def schedule_messages(app, chat_id: int):
    msgs = get_messages()
    delays = [0, 86400, 259200, 604800]
    for i, delay in enumerate(delays):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            await app.bot.send_message(chat_id=chat_id, text=msgs[i])
            data = load_data()
            if str(chat_id) in data["users"]:
                data["users"][str(chat_id)]["step"] = i + 1
                save_data(data)
        except Exception as e:
            logger.error(f"Мессеж алдаа: {e}")

# ─── /start ───────────────────────────────────────────────────
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
            "xm_id": None,
            "approved": False,
        }
        data["stats"]["total"] += 1
        save_data(data)

        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🆕 Шинэ хэрэглэгч!\n👤 {name}\n🆔 {chat_id}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            except:
                pass

        asyncio.create_task(schedule_messages(context.application, chat_id))
    else:
        msgs = get_messages()
        await update.message.reply_text(msgs[0])

# ─── /stats ───────────────────────────────────────────────────
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    data = load_data()
    s = data["stats"]
    total = s.get("total", 0)
    clicks = s.get("clicks", 0)
    convs = s.get("conversions", 0)
    pending = len(data.get("pending", {}))
    approved = len(data.get("approved", {}))
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
⏳ Шалгагдаж байгаа: {pending}
🔐 Группэд нэмэгдсэн: {approved}
{'─'*25}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
    await update.message.reply_text(text)

# ─── /pending ─────────────────────────────────────────────────
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: шалгагдаж байгаа XM ID жагсаалт"""
    if update.effective_chat.id != ADMIN_ID:
        return
    data = load_data()
    pending = data.get("pending", {})

    if not pending:
        await update.message.reply_text("⏳ Шалгагдаж байгаа хүн байхгүй байна")
        return

    text = "⏳ ШАЛГАГДАЖ БАЙГАА XM ID-УУД:\n" + "─"*25 + "\n"
    for chat_id, info in pending.items():
        text += f"👤 {info['name']}\n"
        text += f"🆔 XM ID: {info['xm_id']}\n"
        text += f"📱 Chat ID: {chat_id}\n"
        text += f"📅 {info['date']}\n"
        text += f"➡️ /approve {chat_id} — Зөвшөөрөх\n"
        text += f"➡️ /reject {chat_id} — Татгалзах\n"
        text += "─"*25 + "\n"

    await update.message.reply_text(text)

# ─── /approve ─────────────────────────────────────────────────
async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /approve chat_id — хэрэглэгчийг группэд нэмэх"""
    if update.effective_chat.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /approve 123456789")
        return

    target_id = int(context.args[0])
    data = load_data()

    if str(target_id) not in data.get("pending", {}):
        await update.message.reply_text("⚠️ Энэ хэрэглэгч pending жагсаалтад байхгүй байна")
        return

    user_info = data["pending"][str(target_id)]

    # Группэд нэмэх
    if SIGNAL_GROUP_ID:
        try:
            # Invite link үүсгэх
            invite = await context.bot.create_chat_invite_link(
                chat_id=SIGNAL_GROUP_ID,
                member_limit=1,
                expire_date=datetime.now().timestamp() + 86400  # 24 цаг
            )

            # Хэрэглэгчид мессеж явуулах
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""🎉 Баяр хүргэе! Таны XM ID баталгаажлаа!

🔐 Хаалттай сигнал группэд нэвтрэх линк:
👉 {invite.invite_link}

⚠️ Линк 24 цагийн дотор хүчинтэй
⚠️ Зөвхөн нэг удаа ашиглагдана

Амжилттай арилжаа хийгээрэй! 💰"""
            )

            # Approved болгох
            data["approved"][str(target_id)] = user_info
            data["approved"][str(target_id)]["approved_date"] = datetime.now().isoformat()
            del data["pending"][str(target_id)]

            # Stats нэмэх
            data["stats"]["conversions"] = data["stats"].get("conversions", 0) + 1
            if str(target_id) in data["users"]:
                data["users"][str(target_id)]["approved"] = True
                data["users"][str(target_id)]["converted"] = True

            save_data(data)

            await update.message.reply_text(
                f"✅ {user_info['name']}-д групп линк явуулагдлаа!\n"
                f"🆔 XM ID: {user_info['xm_id']}"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Алдаа гарлаа: {e}\n\nSIGNAL_GROUP_ID зөв эсэхийг шалгаарай")
    else:
        # SIGNAL_GROUP_ID байхгүй бол зөвхөн баталгаажуулах мессеж явуулна
        await context.bot.send_message(
            chat_id=target_id,
            text=f"""🎉 Баяр хүргэе! Таны XM ID баталгаажлаа!

Admin тантай холбогдож сигнал группэд нэмэх болно.
Түр хүлээнэ үү... ⏳"""
        )

        data["approved"][str(target_id)] = user_info
        del data["pending"][str(target_id)]
        save_data(data)
        await update.message.reply_text(f"✅ {user_info['name']} баталгаажлаа (группын ID тохируулаагүй байна)")

# ─── /reject ──────────────────────────────────────────────────
async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /reject chat_id — татгалзах"""
    if update.effective_chat.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /reject 123456789")
        return

    target_id = int(context.args[0])
    data = load_data()

    if str(target_id) not in data.get("pending", {}):
        await update.message.reply_text("⚠️ Энэ хэрэглэгч байхгүй байна")
        return

    user_info = data["pending"][str(target_id)]

    await context.bot.send_message(
        chat_id=target_id,
        text=f"""❌ Таны XM ID баталгаажаагүй байна.

Шалтгаан:
• XM ID буруу байж магадгүй
• Манай линкээр бүртгүүлээгүй байж магадгүй

Дахин манай линкээр бүртгүүлж XM ID-гаа илгээнэ үү:
👉 {XM_LINK}"""
    )

    del data["pending"][str(target_id)]
    save_data(data)
    await update.message.reply_text(f"❌ {user_info['name']}-д татгалзах мессеж явуулагдлаа")

# ─── /broadcast ───────────────────────────────────────────────
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /broadcast текст")
        return

    text = " ".join(context.args)
    data = load_data()
    users = data["users"]

    if not users:
        await update.message.reply_text("⚠️ Хэрэглэгч байхгүй")
        return

    sent = 0
    failed = 0
    for uid, u in users.items():
        try:
            await context.bot.send_message(chat_id=u["chat_id"], text=text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await update.message.reply_text(f"✅ Broadcast дууслаа\n📤 Илгээгдсэн: {sent}\n❌ Амжилтгүй: {failed}")

# ─── /signal ──────────────────────────────────────────────────
async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    keyboard = [[
        InlineKeyboardButton("✅ Бүгдэд илгээх", callback_data="confirm_signal"),
        InlineKeyboardButton("🔐 Зөвхөн группэд", callback_data="group_signal"),
        InlineKeyboardButton("❌ Цуцлах", callback_data="cancel_signal")
    ]]
    context.user_data["pending_signal"] = signal_text
    await update.message.reply_text(
        f"📋 Preview:\n\n{signal_text}\n\n{'─'*22}\nХэнд илгээх вэ?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /edit ────────────────────────────────────────────────────
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    cmd = update.message.text.strip().split()[0]
    idx_map = {"/edit1": 0, "/edit2": 1, "/edit3": 2, "/edit4": 3}
    labels = ["Welcome (Шууд)", "1 өдрийн дараа", "3 өдрийн дараа", "7 өдрийн дараа"]

    idx = idx_map.get(cmd)
    if idx is None:
        return

    msgs = get_messages()
    await update.message.reply_text(
        f"✏️ {labels[idx]} мессежийг засварлах:\n\n"
        f"Одоогийн текст:\n{'─'*20}\n{msgs[idx]}\n{'─'*20}\n\n"
        f"Шинэ текстийг дараагийн мессежээр илгээнэ үү:"
    )
    context.user_data["editing"] = idx

# ─── /help ────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    text = """🤖 ADMIN КОМАНДУУД
─────────────────────────
📊 /stats — Статистик

📢 /broadcast текст — Бүгдэд мессеж

📈 /signal хос чиглэл entry sl tp
   Жнь: /signal EURUSD BUY 1.0850 1.0790 1.0930

⏳ /pending — XM ID шалгагдаж байгаа жагсаалт

✅ /approve 123456789 — Зөвшөөрч группэд нэмэх

❌ /reject 123456789 — Татгалзах

✏️ Мессеж засварлах:
   /edit1 — Welcome
   /edit2 — 1 өдрийн
   /edit3 — 3 өдрийн
   /edit4 — 7 өдрийн"""
    await update.message.reply_text(text)

# ─── Message handler ──────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or '').strip()
    text_lower = text.lower()
    name = update.effective_user.first_name or "Хэрэглэгч"

    # Admin editing mode
    if chat_id == ADMIN_ID and "editing" in context.user_data:
        idx = context.user_data.pop("editing")
        labels = ["Welcome (Шууд)", "1 өдрийн мессеж", "3 өдрийн мессеж", "7 өдрийн мессеж"]
        data = load_data()
        data["messages"][str(idx)] = text
        save_data(data)
        await update.message.reply_text(f"✅ {labels[idx]} хадгалагдлаа!")
        return

    # XM ID илгээсэн эсэх шалгах (тоон утга эсвэл XM гэсэн үг агуулсан)
    if any(c.isdigit() for c in text) and len(text) >= 6 and len(text) <= 12:
        data = load_data()

        # Аль хэдийн approved эсэх
        if str(chat_id) in data.get("approved", {}):
            await update.message.reply_text("✅ Та аль хэдийн сигнал группэд нэмэгдсэн байна!")
            return

        # Pending-д нэмэх
        data["pending"][str(chat_id)] = {
            "name": name,
            "chat_id": chat_id,
            "xm_id": text,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        if str(chat_id) in data["users"]:
            data["users"][str(chat_id)]["xm_id"] = text
        save_data(data)

        # Хэрэглэгчид хариулах
        await update.message.reply_text(
            f"""✅ Таны XM ID хүлээн авлаа!

🆔 ID: {text}
⏳ Admin шалгасны дараа сигнал группэд нэмэгдэнэ.
⏰ Ихэвчлэн 1-24 цагийн дотор

Хүлээж байгаад баярлалаа! 🙏"""
        )

        # Admin-д мэдэгдэл
        if ADMIN_ID:
            keyboard = [[
                InlineKeyboardButton("✅ Зөвшөөрөх", callback_data=f"approve_{chat_id}"),
                InlineKeyboardButton("❌ Татгалзах", callback_data=f"reject_{chat_id}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"""🔔 ШИНЭ XM ID ИРЛЭЭ!

👤 Нэр: {name}
📱 Chat ID: {chat_id}
🆔 XM ID: {text}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚡ Шууд шийдэх:""",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    # FAQ автомат хариулт
    redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK
    faq = {
        'бүртгэл': f"""📝 XM-д бүртгүүлэх заавар:

1️⃣ Доорх линкээр орно
2️⃣ "Бүртгүүлэх" дарна
3️⃣ Мэдээллээ бөглөнө
4️⃣ Имэйл баталгаажуулна
5️⃣ Deposit хийнэ

👉 {redirect}

⭐ Бүртгүүлсний дараа XM ID-гаа энд илгээгээрэй!""",

        'deposit': """💰 XM Deposit мэдээлэл:

✅ Хамгийн бага: $5
✅ Visa/Mastercard
✅ Bank transfer
✅ Криптовалют

Монголоос шууд карт ашиглан хийж болно!""",

        'сигнал': """📊 Сигналын тухай:

✅ Өдөрт 1-3 сигнал
✅ EUR/USD, GBP/USD, Gold
✅ Entry, SL, TP бүгд өгдөг
⚠️ Боловсролын зорилготой

🔐 Сигнал авахын тулд XM-д бүртгүүлж ID-гаа илгээгээрэй!""",

        'хэзээ': """⏰ Сигнал гарах цаг:

🌅 Өглөө 09:00-10:00
🌆 Орой 20:00-21:00

Улаанбаатарын цагаар""",

        'яаж': f"""🚀 Эхлэх заавар:

1️⃣ Бүртгүүлнэ 👉 {redirect}
2️⃣ XM ID-гаа энд илгээнэ
3️⃣ Admin баталгаажуулна
4️⃣ Хаалттай сигнал группэд нэвтэрнэ 🔐
5️⃣ Сигнал хүлээж авна 💰""",

        'xm id': """🆔 XM ID олох заавар:

1️⃣ XM-д нэвтэрнэ
2️⃣ Профайл дээр дарна
3️⃣ "MT4/MT5 Account" хэсэгт байна
4️⃣ Тоон дугаараа энд илгээнэ үү

Жнь: 12345678""",
    }

    for keyword, answer in faq.items():
        if keyword in text_lower:
            await update.message.reply_text(answer)
            return

# ─── Callbacks ────────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Сигнал бүгдэд илгээх
    if query.data == "confirm_signal":
        signal_text = context.user_data.get("pending_signal")
        if not signal_text:
            await query.edit_message_text("⚠️ Сигнал олдсонгүй")
            return
        data = load_data()
        sent = 0
        for uid, u in data["users"].items():
            try:
                await context.bot.send_message(chat_id=u["chat_id"], text=signal_text)
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await query.edit_message_text(f"✅ Сигнал {sent} хүнд илгээгдлээ!")

    # Сигнал зөвхөн группэд
    elif query.data == "group_signal":
        signal_text = context.user_data.get("pending_signal")
        if not signal_text:
            await query.edit_message_text("⚠️ Сигнал олдсонгүй")
            return
        if SIGNAL_GROUP_ID:
            try:
                await context.bot.send_message(chat_id=SIGNAL_GROUP_ID, text=signal_text)
                await query.edit_message_text("✅ Сигнал хаалттай группэд илгээгдлээ!")
            except Exception as e:
                await query.edit_message_text(f"❌ Алдаа: {e}")
        else:
            await query.edit_message_text("⚠️ SIGNAL_GROUP_ID тохируулаагүй байна")

    elif query.data == "cancel_signal":
        await query.edit_message_text("❌ Сигнал цуцлагдлаа")

    # Inline approve/reject
    elif query.data.startswith("approve_"):
        target_id = int(query.data.split("_")[1])
        data = load_data()

        if str(target_id) not in data.get("pending", {}):
            await query.edit_message_text("⚠️ Хэрэглэгч байхгүй байна")
            return

        user_info = data["pending"][str(target_id)]

        if SIGNAL_GROUP_ID:
            try:
                invite = await context.bot.create_chat_invite_link(
                    chat_id=SIGNAL_GROUP_ID,
                    member_limit=1,
                    expire_date=int(datetime.now().timestamp()) + 86400
                )
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"""🎉 Баяр хүргэе! Таны XM ID баталгаажлаа!

🔐 Хаалттай сигнал группэд нэвтрэх линк:
👉 {invite.invite_link}

⚠️ Линк 24 цагийн дотор хүчинтэй
⚠️ Зөвхөн нэг удаа ашиглагдана

Амжилттай арилжаа хийгээрэй! 💰"""
                )
                data["approved"][str(target_id)] = user_info
                data["approved"][str(target_id)]["approved_date"] = datetime.now().isoformat()
                del data["pending"][str(target_id)]
                data["stats"]["conversions"] = data["stats"].get("conversions", 0) + 1
                if str(target_id) in data["users"]:
                    data["users"][str(target_id)]["approved"] = True
                    data["users"][str(target_id)]["converted"] = True
                save_data(data)
                await query.edit_message_text(
                    f"✅ {user_info['name']} баталгаажлаа!\n🆔 XM ID: {user_info['xm_id']}\n📨 Групп линк явуулагдлаа!"
                )
            except Exception as e:
                await query.edit_message_text(f"❌ Алдаа: {e}")
        else:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 Таны XM ID баталгаажлаа! Admin тантай холбогдох болно."
            )
            data["approved"][str(target_id)] = user_info
            del data["pending"][str(target_id)]
            save_data(data)
            await query.edit_message_text(f"✅ {user_info['name']} баталгаажлаа!")

    elif query.data.startswith("reject_"):
        target_id = int(query.data.split("_")[1])
        data = load_data()

        if str(target_id) not in data.get("pending", {}):
            await query.edit_message_text("⚠️ Хэрэглэгч байхгүй байна")
            return

        user_info = data["pending"][str(target_id)]
        await context.bot.send_message(
            chat_id=target_id,
            text=f"❌ Таны XM ID баталгаажаагүй байна.\n\nДахин манай линкээр бүртгүүлж ID-гаа илгээнэ үү:\n👉 {XM_LINK}"
        )
        del data["pending"][str(target_id)]
        save_data(data)
        await query.edit_message_text(f"❌ {user_info['name']} татгалзагдлаа")

# ─── Click tracking ───────────────────────────────────────────
async def handle_click(request):
    campaign = request.match_info.get("campaign", "xm")
    user_id = request.rel_url.query.get("uid", "unknown")
    data = load_data()
    data["stats"]["clicks"] = data["stats"].get("clicks", 0) + 1
    data["clicks"].append({
        "time": datetime.now().isoformat(),
        "user_id": user_id,
        "campaign": campaign
    })
    if user_id in data["users"]:
        data["users"][user_id]["clicked"] = True
    save_data(data)
    raise web.HTTPFound(XM_LINK or "https://www.xm.com")

async def handle_health(request):
    return web.Response(text="OK")

# ─── Main ─────────────────────────────────────────────────────
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("edit1", edit_cmd))
    app.add_handler(CommandHandler("edit2", edit_cmd))
    app.add_handler(CommandHandler("edit3", edit_cmd))
    app.add_handler(CommandHandler("edit4", edit_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    web_app = web.Application()
    web_app.router.add_get("/click/{campaign}", handle_click)
    web_app.router.add_get("/health", handle_health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot started!")

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
