import os
import json
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BASE_URL = os.environ.get("BASE_URL", "")
XM_LINK = os.environ.get("XM_LINK", "")
EBC_LINK = os.environ.get("EBC_LINK", "https://client.ebc.com/signup?linkCode=B4355638-a01")
SIGNAL_GROUP_ID = int(os.environ.get("SIGNAL_GROUP_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

XM_VIDEO = "https://www.youtube.com/watch?v=aXsYay_OTgA"
EBC_VIDEO = "https://www.youtube.com/watch?v=C5yP2n5xMBw"

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "pending": {},
        "approved": {},
        "clicks": [],
        "messages": {"0": None, "1": None, "2": None, "3": None},
        "stats": {"total": 0, "clicks": 0, "conversions": 0, "xm": 0, "ebc": 0}
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_messages(broker="xm"):
    data = load_data()
    link = EBC_LINK if broker == "ebc" else (XM_LINK or "")
    broker_name = "EBC" if broker == "ebc" else "XM"
    video = EBC_VIDEO if broker == "ebc" else XM_VIDEO

    defaults = [
        # 1-р мессеж — брокер сонгосны дараа явна
        f"""👋 Сайн байна уу! Robinhood trading academy-д тавтай морил!

Би танд:
✅ Өдөр бүрийн market шинжилгээ
✅ EUR/USD, USDJPY, AUDUSD, NAS100, Gold сигнал болон IDEA
✅ Хаалттай сигнал Channel-д үнэгүй нэвтрэх эрх санал болгож байна

🚀 XM/EBC-д доорхи линкээр ҮНЭГҮЙ бүртгүүлснээр орох боломжтой.
👉 {link}

📹 Данс нээх заавар видео:
▶️ {video}""",

        # 2-р мессеж — 1 өдрийн дараа
        f"""📊 Forex-д трейдерүүдийн гаргадаг нийтлэг 4 алдаа:

❌ Хэт их leverage ашиглах
❌ Stop loss тавихгүй арилжаалах
❌ Мэдрэмжээр шийдвэр гаргах
❌ Хангалттай туршлага, мэдлэггүй байх

Та эдгээр алдаагаа засаж нэмэлт орлогыг бүрдүүлээрэй!

📹 {broker_name} данс нээх заавар:
▶️ {video}

👉 {link}""",

        # 3-р мессеж — 3 өдрийн дараа
        f"""🔥 Энэ долоо хоногийн шинжилгээний үр дүн:

GOLD: +600 pips ✅
EURUSD: +200 pips ✅
USDJPY: -150 pips ❌
━━━━━━━━━━━━━━
📈 Total: +650 pips

🔐 Бүрэн сигнал авахын тулд {broker_name}-д бүртгүүлнэ үү:
👉 {link}

📹 Данс нээх заавар:
▶️ {video}""",

        # 4-р мессеж — 7 өдрийн дараа
        f"""💎 Та энэ 7 хоногийн үр дүнгээ алдлаа!

Одоог хүртэл бүртгүүлээгүй бол яарна уу:

🎁 Broker-ийн Welcome bonus
📚 Нэмэлт орлого
🔐 Хаалттай сигнал Channel-д нэвтрэх эрх

📹 {broker_name} данс нээх заавар:
▶️ {video}

👉 {link}

Хугацаа хязгаарлагдмал! ⏰"""
    ]

    result = []
    for i, default in enumerate(defaults):
        custom = data["messages"].get(str(i))
        result.append(custom if custom else default)
    return result

def broker_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("1️⃣ XM Broker", callback_data="broker_xm"),
        InlineKeyboardButton("2️⃣ EBC Broker", callback_data="broker_ebc"),
    ]])

async def schedule_messages(app, chat_id, broker="xm"):
    msgs = get_messages(broker)
    delays = [86400, 259200, 604800]
    for i, delay in enumerate(delays):
        await asyncio.sleep(delay)
        try:
            await app.bot.send_message(chat_id=chat_id, text=msgs[i+1])
            data = load_data()
            if str(chat_id) in data["users"]:
                data["users"][str(chat_id)]["step"] = i + 2
                save_data(data)
        except Exception as e:
            logger.error(f"Мессеж алдаа: {e}")

async def process_approve(context, target_id, data):
    user_info = data["pending"][str(target_id)]
    broker = user_info.get("broker", "xm")
    if SIGNAL_GROUP_ID:
        try:
            invite = await context.bot.create_chat_invite_link(
                chat_id=SIGNAL_GROUP_ID,
                member_limit=1,
                expire_date=int(datetime.now().timestamp()) + 86400
            )
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""🎉 Баяр хүргэе! Таны ID баталгаажлаа!

🔐 Хаалттай сигнал Channel-д нэвтрэх линк:
👉 {invite.invite_link}

⚠️ Линк 24 цагийн дотор хүчинтэй
⚠️ Зөвхөн нэг удаа ашиглагдана

Амжилттай арилжаа хийгээрэй! 💰"""
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 Таны ID баталгаажлаа! Admin тантай холбогдох болно."
            )
            logger.error(f"Invite алдаа: {e}")
    else:
        await context.bot.send_message(
            chat_id=target_id,
            text="🎉 Таны ID баталгаажлаа! Admin тантай холбогдох болно."
        )
    data["approved"][str(target_id)] = user_info
    data["approved"][str(target_id)]["approved_date"] = datetime.now().isoformat()
    del data["pending"][str(target_id)]
    data["stats"]["conversions"] = data["stats"].get("conversions", 0) + 1
    data["stats"][broker] = data["stats"].get(broker, 0) + 1
    if str(target_id) in data["users"]:
        data["users"][str(target_id)]["approved"] = True
        data["users"][str(target_id)]["converted"] = True
    save_data(data)

async def process_reject(context, target_id, data):
    user_info = data["pending"][str(target_id)]
    broker = user_info.get("broker", "xm")
    link = EBC_LINK if broker == "ebc" else XM_LINK
    video = EBC_VIDEO if broker == "ebc" else XM_VIDEO
    await context.bot.send_message(
        chat_id=target_id,
        text=f"""❌ Таны ID баталгаажаагүй байна.

Дахин манай линкээр бүртгүүлж ID-гаа илгээнэ үү:
👉 {link}

📹 Данс нээх заавар:
▶️ {video}"""
    )
    del data["pending"][str(target_id)]
    save_data(data)

async def start(update, context):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name or "Хэрэглэгч"
    data = load_data()
    if str(chat_id) not in data["users"]:
        data["users"][str(chat_id)] = {
            "name": name, "chat_id": chat_id,
            "joined": datetime.now().isoformat(),
            "step": 0, "clicked": False, "converted": False,
            "xm_id": None, "approved": False, "broker": None
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

    # 1️⃣ Welcome мессеж
    await update.message.reply_text(
        f"👋 Сайн байна уу, {name}!\n\n"
        f"Robinhood Trading Academy-д тавтай морил! 🎓\n\n"
        f"Би танд:\n"
        f"✅ Өдөр бүрийн market шинжилгээ\n"
        f"✅ EUR/USD, USDJPY, AUDUSD, NAS100, Gold сигнал болон IDEA\n"
        f"✅ Хаалттай сигнал Channel-д үнэгүй нэвтрэх эрх санал болгож байна"
    )

    # 2️⃣ Брокер сонголт
    await update.message.reply_text(
        "🚀 XM/EBC-д доорхи линкээр ҮНЭГҮЙ бүртгүүлснээр орох боломжтой.\n\n"
        "Та аль брокерт бүртгүүлэхийг хүсэж байна вэ?\n\n"
        "1️⃣ XM — Дэлхийн топ broker, $5-аас эхэлнэ\n"
        "2️⃣ EBC — Олон улсын найдвартай broker",
        reply_markup=broker_keyboard()
    )

async def stats_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    data = load_data()
    s = data["stats"]
    total = s.get("total", 0)
    clicks = s.get("clicks", 0)
    convs = s.get("conversions", 0)
    xm_count = s.get("xm", 0)
    ebc_count = s.get("ebc", 0)
    pending = len(data.get("pending", {}))
    approved = len(data.get("approved", {}))
    ctr = round((clicks/total*100), 1) if total > 0 else 0
    cvr = round((convs/clicks*100), 1) if clicks > 0 else 0
    await update.message.reply_text(
        f"📊 СТАТИСТИК\n{'─'*25}\n"
        f"👥 Нийт: {total}\n"
        f"🔗 Click: {clicks} ({ctr}%)\n"
        f"✅ Бүртгэл: {convs} ({cvr}%)\n"
        f"💰 Орлого: ~${convs*30}\n"
        f"{'─'*25}\n"
        f"1️⃣ XM: {xm_count}\n"
        f"2️⃣ EBC: {ebc_count}\n"
        f"{'─'*25}\n"
        f"⏳ Шалгагдаж байгаа: {pending}\n"
        f"🔐 Channel-д нэмэгдсэн: {approved}\n"
        f"{'─'*25}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

async def pending_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    data = load_data()
    pending = data.get("pending", {})
    if not pending:
        await update.message.reply_text("⏳ Шалгагдаж байгаа хүн байхгүй байна")
        return
    text = "⏳ ШАЛГАГДАЖ БАЙГАА:\n" + "─"*25 + "\n"
    for chat_id, info in pending.items():
        broker = info.get('broker', 'xm').upper()
        text += f"👤 {info['name']}\n🏦 {broker}\n🆔 {info['xm_id']}\n📱 {chat_id}\n📅 {info['date']}\n/approve {chat_id} | /reject {chat_id}\n{'─'*25}\n"
    await update.message.reply_text(text)

async def approve_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /approve 123456789")
        return
    target_id = int(context.args[0])
    data = load_data()
    if str(target_id) not in data.get("pending", {}):
        await update.message.reply_text("⚠️ Хүн байхгүй байна")
        return
    await process_approve(context, target_id, data)
    await update.message.reply_text("✅ Баталгаажлаа!")

async def reject_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Хэрэглээ: /reject 123456789")
        return
    target_id = int(context.args[0])
    data = load_data()
    if str(target_id) not in data.get("pending", {}):
        await update.message.reply_text("⚠️ Хүн байхгүй байна")
        return
    await process_reject(context, target_id, data)
    await update.message.reply_text("❌ Татгалзагдлаа")

async def broadcast_cmd(update, context):
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
    await update.message.reply_text(f"✅ Broadcast дууслаа\n📤 {sent}\n❌ {failed}")

async def signal_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 5:
        await update.message.reply_text("⚠️ Хэрэглээ:\n/signal EURUSD BUY 1.0850 1.0790 1.0930")
        return
    pair, direction, entry, sl, tp = args[0], args[1], args[2], args[3], args[4]
    emoji = "📈" if direction.upper() == "BUY" else "📉"
    signal_text = (
        f"📊 FOREX СИГНАЛ\n{'─'*22}\n"
        f"💱 Хос: {pair.upper()}\n"
        f"📌 Чиглэл: {direction.upper()} {emoji}\n"
        f"🎯 Entry: {entry}\n"
        f"🛡️ Stop Loss: {sl}\n"
        f"✅ Take Profit: {tp}\n"
        f"{'─'*22}\n"
        f"⚠️ Боловсролын зорилготой."
    )
    keyboard = [[
        InlineKeyboardButton("✅ Бүгдэд илгээх", callback_data="confirm_signal"),
        InlineKeyboardButton("🔐 Зөвхөн Channel", callback_data="group_signal"),
        InlineKeyboardButton("❌ Цуцлах", callback_data="cancel_signal")
    ]]
    context.user_data["pending_signal"] = signal_text
    await update.message.reply_text(
        f"📋 Preview:\n\n{signal_text}\n\nХэнд илгээх вэ?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    cmd = update.message.text.strip().split()[0]
    idx_map = {"/edit1": 0, "/edit2": 1, "/edit3": 2, "/edit4": 3}
    labels = ["Welcome", "1 өдөр", "3 өдөр", "7 өдөр"]
    idx = idx_map.get(cmd)
    if idx is None:
        return
    msgs = get_messages()
    await update.message.reply_text(
        f"✏️ {labels[idx]} мессежийг засварлах:\n\n"
        f"Одоогийн:\n{'─'*20}\n{msgs[idx]}\n{'─'*20}\n\n"
        f"Шинэ текстийг илгээнэ үү:"
    )
    context.user_data["editing"] = idx

async def help_cmd(update, context):
    if update.effective_chat.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "🤖 ADMIN КОМАНДУУД\n─────────────────────────\n"
        "📊 /stats — Статистик\n"
        "📢 /broadcast текст — Бүгдэд\n"
        "📈 /signal хос чиглэл entry sl tp\n"
        "⏳ /pending — Шалгах жагсаалт\n"
        "✅ /approve ID — Зөвшөөрөх\n"
        "❌ /reject ID — Татгалзах\n"
        "✏️ /edit1 /edit2 /edit3 /edit4"
    )

async def handle_message(update, context):
    chat_id = update.effective_chat.id
    text = (update.message.text or '').strip()
    text_lower = text.lower()
    name = update.effective_user.first_name or "Хэрэглэгч"

    if chat_id == ADMIN_ID and "editing" in context.user_data:
        idx = context.user_data.pop("editing")
        labels = ["Welcome", "1 өдөр", "3 өдөр", "7 өдөр"]
        data = load_data()
        data["messages"][str(idx)] = text
        save_data(data)
        await update.message.reply_text(f"✅ {labels[idx]} хадгалагдлаа!")
        return

    if any(c.isdigit() for c in text) and 6 <= len(text) <= 12:
        data = load_data()
        if str(chat_id) in data.get("approved", {}):
            await update.message.reply_text("✅ Та аль хэдийн сигнал Channel-д нэмэгдсэн байна!")
            return
        broker = "xm"
        if str(chat_id) in data["users"]:
            broker = data["users"][str(chat_id)].get("broker", "xm") or "xm"
        broker_name = "EBC" if broker == "ebc" else "XM"
        data["pending"][str(chat_id)] = {
            "name": name, "chat_id": chat_id,
            "xm_id": text, "broker": broker,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        if str(chat_id) in data["users"]:
            data["users"][str(chat_id)]["xm_id"] = text
        save_data(data)
        await update.message.reply_text(
            f"✅ Таны {broker_name} ID хүлээн авлаа!\n\n"
            f"🆔 ID: {text}\n"
            f"⏳ Admin шалгасны дараа Channel-д нэмэгдэнэ.\n"
            f"⏰ Ихэвчлэн 1-24 цагийн дотор 🙏"
        )
        if ADMIN_ID:
            keyboard = [[
                InlineKeyboardButton("✅ Зөвшөөрөх", callback_data=f"approve_{chat_id}"),
                InlineKeyboardButton("❌ Татгалзах", callback_data=f"reject_{chat_id}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 ШИНЭ ID ИРЛЭЭ!\n\n👤 {name}\n🏦 {broker_name}\n🆔 {text}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    xm_redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK
    ebc_redirect = f"{BASE_URL}/click/ebc" if BASE_URL else EBC_LINK
    faq = {
        'бүртгэл': f"📝 Бүртгүүлэх заавар:\n\n1️⃣ XM: {xm_redirect}\n📹 {XM_VIDEO}\n\n2️⃣ EBC: {ebc_redirect}\n📹 {EBC_VIDEO}\n\nБүртгүүлсний дараа ID-гаа илгээгээрэй!",
        'xm': f"1️⃣ XM Broker:\n\n✅ Хамгийн бага: $5\n✅ Монголоос карт ашиглан болно\n✅ MT4/MT5\n\n👉 {xm_redirect}\n📹 {XM_VIDEO}",
        'ebc': f"2️⃣ EBC Broker:\n\n✅ FCA зөвшөөрөлтэй\n✅ Олон улсын найдвартай\n✅ Өндөр leverage\n\n👉 {ebc_redirect}\n📹 {EBC_VIDEO}",
        'видео': f"📹 Данс нээх заавар видеонууд:\n\n1️⃣ XM заавар:\n{XM_VIDEO}\n\n2️⃣ EBC заавар:\n{EBC_VIDEO}",
        'заавар': f"📹 Данс нээх заавар видеонууд:\n\n1️⃣ XM заавар:\n{XM_VIDEO}\n\n2️⃣ EBC заавар:\n{EBC_VIDEO}",
        'deposit': "💰 Deposit:\n\n1️⃣ XM — $5-аас\n2️⃣ EBC — $50-аас\n\n✅ Visa/Mastercard\n✅ Bank transfer",
        'сигнал': "📊 Сигнал:\n\n✅ Өдөрт 1-3 сигнал\n✅ EUR/USD, USDJPY, AUDUSD, NAS100, Gold\n⚠️ Боловсролын зорилготой\n\n🔐 Бүртгүүлж ID-гаа илгээгээрэй!",
        'яаж': f"🚀 Эхлэх заавар:\n\n1️⃣ Broker сонгоно\n2️⃣ Бүртгүүлнэ\n3️⃣ ID-гаа илгээнэ\n4️⃣ Channel-д орно 🔐\n5️⃣ Сигнал авна 💰\n\nXM: {xm_redirect}\nEBC: {ebc_redirect}",
    }
    for keyword, answer in faq.items():
        if keyword in text_lower:
            await update.message.reply_text(answer)
            return

async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id

    if query.data == "broker_xm":
        data = load_data()
        if str(chat_id) in data["users"]:
            data["users"][str(chat_id)]["broker"] = "xm"
            save_data(data)
        redirect = f"{BASE_URL}/click/xm" if BASE_URL else XM_LINK
        await query.edit_message_text(
            f"✅ XM Broker сонголоо!\n\n"
            f"📹 Данс нээх заавар видео:\n▶️ {XM_VIDEO}\n\n"
            f"🚀 Доорх линкээр бүртгүүлнэ үү:\n👉 {redirect}\n\n"
            f"⭐ Бүртгүүлсний дараа XM ID-гаа (8 оронтой тоо) энд илгээгээрэй!"
        )
        asyncio.create_task(schedule_messages(context.application, chat_id, "xm"))

    elif query.data == "broker_ebc":
        data = load_data()
        if str(chat_id) in data["users"]:
            data["users"][str(chat_id)]["broker"] = "ebc"
            save_data(data)
        redirect = f"{BASE_URL}/click/ebc" if BASE_URL else EBC_LINK
        await query.edit_message_text(
            f"✅ EBC Broker сонголоо!\n\n"
            f"📹 Данс нээх заавар видео:\n▶️ {EBC_VIDEO}\n\n"
            f"🚀 Доорх линкээр бүртгүүлнэ үү:\n👉 {redirect}\n\n"
            f"⭐ Бүртгүүлсний дараа EBC ID-гаа (6-8 оронтой тоо) энд илгээгээрэй!"
        )
        asyncio.create_task(schedule_messages(context.application, chat_id, "ebc"))

    elif query.data == "confirm_signal":
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

    elif query.data == "group_signal":
        signal_text = context.user_data.get("pending_signal")
        if not signal_text:
            await query.edit_message_text("⚠️ Сигнал олдсонгүй")
            return
        if SIGNAL_GROUP_ID:
            try:
                await context.bot.send_message(chat_id=SIGNAL_GROUP_ID, text=signal_text)
                await query.edit_message_text("✅ Сигнал Channel-д илгээгдлээ!")
            except Exception as e:
                await query.edit_message_text(f"❌ Алдаа: {e}")
        else:
            await query.edit_message_text("⚠️ SIGNAL_GROUP_ID тохируулаагүй байна")

    elif query.data == "cancel_signal":
        await query.edit_message_text("❌ Сигнал цуцлагдлаа")

    elif query.data.startswith("approve_"):
        target_id = int(query.data.split("_")[1])
        data = load_data()
        if str(target_id) not in data.get("pending", {}):
            await query.edit_message_text("⚠️ Хэрэглэгч байхгүй байна")
            return
        user_info = data["pending"][str(target_id)]
        await process_approve(context, target_id, data)
        await query.edit_message_text(
            f"✅ {user_info['name']} баталгаажлаа!\n"
            f"🏦 {user_info.get('broker','xm').upper()}\n"
            f"🆔 {user_info['xm_id']}"
        )

    elif query.data.startswith("reject_"):
        target_id = int(query.data.split("_")[1])
        data = load_data()
        if str(target_id) not in data.get("pending", {}):
            await query.edit_message_text("⚠️ Хэрэглэгч байхгүй байна")
            return
        user_info = data["pending"][str(target_id)]
        await process_reject(context, target_id, data)
        await query.edit_message_text(f"❌ {user_info['name']} татгалзагдлаа")

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
    target = EBC_LINK if campaign == "ebc" else (XM_LINK or "https://www.xm.com")
    raise web.HTTPFound(target)

async def handle_health(request):
    return web.Response(text="OK")

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
