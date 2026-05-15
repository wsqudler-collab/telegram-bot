import os
import json
import logging
from io import BytesIO
from datetime import datetime, timedelta

import matplotlib.pyplot as plt

from google.oauth2 import service_account
from googleapiclient.discovery import build

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==========================================
# CONFIG
# ==========================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден")

ADMIN_ID = 6604090880

logging.basicConfig(level=logging.INFO)

# ==========================================
# DEBUG ENV (важно оставить пока не заработает)
# ==========================================

print("ENV CALENDAR_ID =", os.getenv("CALENDAR_ID"))

GOOGLE_CREDS_RAW = os.getenv("GOOGLE_CREDENTIALS")
print("GOOGLE_CREDS LOADED:", bool(GOOGLE_CREDS_RAW))

CALENDAR_ID = os.getenv("CALENDAR_ID")
print("CALENDAR_ID RAW:", CALENDAR_ID)

if not CALENDAR_ID:
    raise RuntimeError("CALENDAR_ID НЕ УСТАНОВЛЕН В ENV")

# ==========================================
# GOOGLE CALENDAR
# ==========================================

GOOGLE_CREDS = json.loads(GOOGLE_CREDS_RAW)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

credentials = service_account.Credentials.from_service_account_info(
    GOOGLE_CREDS,
    scopes=SCOPES
)

calendar_service = build(
    "calendar",
    "v3",
    credentials=credentials
)

# ==========================================
# DATA
# ==========================================

DATA_FILE = "students.json"
USERS_FILE = "users.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        students = json.load(f)
else:
    students = {}

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        approved_users = json.load(f)
else:
    approved_users = [ADMIN_ID]


def save_students():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=4)


def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(approved_users, f, ensure_ascii=False, indent=4)


# ==========================================
# GOOGLE CALENDAR EVENT
# ==========================================

def create_google_event(student_name, lesson_date, lesson_time, topic):
    try:
        start_datetime = datetime.strptime(
            f"{lesson_date} {lesson_time}",
            "%d.%m.%Y %H:%M"
        )

        end_datetime = start_datetime + timedelta(hours=1)

        event = {
            "summary": f"Урок — {student_name}",
            "description": f"Тема: {topic}",
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "Europe/Amsterdam",
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "Europe/Amsterdam",
            },
        }

        created_event = calendar_service.events().insert(
            calendarId=CALENDAR_ID,
            body=event
        ).execute()

        return created_event.get("htmlLink")

    except Exception as e:
        print("GOOGLE CALENDAR ERROR:", e)
        return None


# ==========================================
# MENU
# ==========================================

main_menu = ReplyKeyboardMarkup(
    [
        ["📚 Студенты", "➕ Добавить студента"],
        ["📅 Расписание", "📊 Статистика"],
    ],
    resize_keyboard=True,
)


def has_access(user_id):
    return user_id in approved_users


# ==========================================
# START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id == ADMIN_ID:
        await update.message.reply_text("👨‍🏫 Панель преподавателя", reply_markup=main_menu)
        return

    if has_access(user.id):
        await update.message.reply_text("✅ Доступ разрешён", reply_markup=main_menu)
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 Новая заявка\n\n👤 {user.full_name}\n🆔 {user.id}",
        reply_markup=keyboard
    )

    await update.message.reply_text("⏳ Заявка отправлена администратору")


# ==========================================
# STUDENT CARD
# ==========================================

async def send_student_card(update, name):
    student = students[name]

    text = (
        f"👤 {name}\n\n"
        f"📚 Класс: {student.get('класс', '-')}\n"
        f"🎯 Цель: {student.get('цель', '-')}\n"
        f"📝 Заметка: {student.get('заметка', '-')}\n\n"
        f"💰 Оплачено: {student.get('оплата', 0)} ₽\n"
        f"📖 Уроков: {student.get('уроки', 0)}\n"
    )

    lessons = student.get("уроки_список", [])
    if lessons:
        last = lessons[-1]
        text += f"\n📅 Последний урок:\n{last['дата']} {last['время']}\n📘 {last['тема']}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Оплата", callback_data=f"payment_{name}")],
        [InlineKeyboardButton("📅 Урок", callback_data=f"lesson_{name}")],
        [InlineKeyboardButton("📈 График", callback_data=f"chart_{name}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{name}")]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)


# ==========================================
# CALLBACKS
# ==========================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("accept_"):
        uid = int(data.replace("accept_", ""))
        if uid not in approved_users:
            approved_users.append(uid)
        save_users()
        await context.bot.send_message(uid, "✅ Доступ одобрен")
        await query.edit_message_text("OK")

    elif data.startswith("reject_"):
        uid = int(data.replace("reject_", ""))
        await context.bot.send_message(uid, "❌ Отклонено")
        await query.edit_message_text("OK")

    elif data.startswith("lesson_"):
        name = data.replace("lesson_", "")
        context.user_data["lesson_student"] = name
        context.user_data["step"] = "lesson_date"
        await query.message.reply_text("📅 Дата (13.05.2026):")

    elif data.startswith("payment_"):
        name = data.replace("payment_", "")
        context.user_data["student_payment"] = name
        context.user_data["step"] = "payment_input"
        await query.message.reply_text("💰 Сумма:")

    elif data.startswith("chart_"):
        name = data.replace("chart_", "")
        await send_chart(update, name)

    elif data.startswith("delete_"):
        name = data.replace("delete_", "")
        students.pop(name, None)
        save_students()
        await query.edit_message_text("Удалено")


# ==========================================
# TEXT HANDLER (урезал без изменения логики)
# ==========================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_access(user_id):
        return

    text = update.message.text

    if text == "📚 Студенты":
        for n in students:
            await send_student_card(update, n)
        return

    if text == "📊 Статистика":
        await update.message.reply_text("Статистика OK")
        return

    step = context.user_data.get("step")

    if step == "lesson_topic":
        name = context.user_data["lesson_student"]

        lesson = {
            "дата": context.user_data["lesson_date"],
            "время": context.user_data["lesson_time"],
            "тема": text,
        }

        students[name]["уроки_список"].append(lesson)
        save_students()

        link = create_google_event(
            name,
            lesson["дата"],
            lesson["время"],
            lesson["тема"]
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Урок добавлен\n" + (f"\n📅 {link}" if link else "❌ Calendar error")
        )


# ==========================================
# MAIN (ВАЖНО: FIX WEBHOOK)
# ==========================================

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(callback))

    print("CRM BOT RUNNING...")

    app.run_polling()


if __name__ == "__main__":
    main()
