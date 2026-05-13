import os
import json
import logging
from io import BytesIO
from datetime import datetime, timedelta

import matplotlib.pyplot as plt

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

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# CONFIG
# ==========================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден")

ADMIN_ID = 6604090880

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

GOOGLE_CREDS = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

SCOPES = ["https://www.googleapis.com/auth/calendar"]

credentials = service_account.Credentials.from_service_account_info(
    GOOGLE_CREDS,
    scopes=SCOPES
)

calendar_service = build("calendar", "v3", credentials=credentials)

logging.basicConfig(level=logging.INFO)

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
# GOOGLE CALENDAR
# ==========================================

def create_calendar_event(student_name, date_str, time_str, topic):
    try:
        start = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
    except:
        return

    end = start + timedelta(hours=1)

    event = {
        "summary": f"📚 Урок: {student_name}",
        "description": topic,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Europe/Amsterdam",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Europe/Amsterdam",
        },
    }

    calendar_service.events().insert(
        calendarId=GOOGLE_CALENDAR_ID,
        body=event
    ).execute()

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
        text += f"\n📅 Следующий урок:\n{last['дата']} {last['время']}\n📘 {last['тема']}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Добавить оплату", callback_data=f"payment_{name}")],
        [InlineKeyboardButton("📅 Назначить урок", callback_data=f"lesson_{name}")],
        [InlineKeyboardButton("📈 График", callback_data=f"chart_{name}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{name}")]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)

# ==========================================
# HANDLE TEXT
# ==========================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not has_access(user_id):
        return

    text = update.message.text
    step = context.user_data.get("step")

    if text == "➕ Добавить студента":
        context.user_data["step"] = "student_name"
        await update.message.reply_text("👤 Введи имя:")
        return

    if text == "📚 Студенты":
        for name in students:
            await send_student_card(update, name)
        return

    if text == "📅 Расписание":
        msg = "📅 Расписание:\n\n"
        for name, s in students.items():
            for l in s.get("уроки_список", []):
                msg += f"{name}\n{l['дата']} {l['время']}\n{l['тема']}\n\n"
        await update.message.reply_text(msg)
        return

    if text == "📊 Статистика":
        total_money = sum(s.get("оплата", 0) for s in students.values())
        total_lessons = sum(s.get("уроки", 0) for s in students.values())

        await update.message.reply_text(
            f"📊 Статистика\n\n"
            f"👥 Студентов: {len(students)}\n"
            f"💰 Доход: {total_money}\n"
            f"📖 Уроков: {total_lessons}"
        )
        return

    # ===== STUDENT FLOW =====

    if step == "student_name":
        context.user_data["name"] = text
        context.user_data["step"] = "student_class"
        await update.message.reply_text("📚 Класс:")
        return

    if step == "student_class":
        context.user_data["class"] = text
        context.user_data["step"] = "student_goal"
        await update.message.reply_text("🎯 Цель:")
        return

    if step == "student_goal":
        context.user_data["goal"] = text
        context.user_data["step"] = "student_note"
        await update.message.reply_text("📝 Заметка:")
        return

    if step == "student_note":
        name = context.user_data["name"]

        students[name] = {
            "класс": context.user_data["class"],
            "цель": context.user_data["goal"],
            "заметка": text,
            "оплата": 0,
            "уроки": 0,
            "уроки_список": [],
        }

        save_students()
        context.user_data.clear()

        await update.message.reply_text(f"✅ Студент {name} добавлен")
        return

    # ===== LESSON FLOW =====

    if step == "lesson_date":
        context.user_data["lesson_date"] = text
        context.user_data["step"] = "lesson_time"
        await update.message.reply_text("⏰ Время:")
        return

    if step == "lesson_time":
        context.user_data["lesson_time"] = text
        context.user_data["step"] = "lesson_topic"
        await update.message.reply_text("📘 Тема:")
        return

    if step == "lesson_topic":
        name = context.user_data["lesson_student"]

        students[name]["уроки_список"].append({
            "дата": context.user_data["lesson_date"],
            "время": context.user_data["lesson_time"],
            "тема": text,
        })

        # 👉 GOOGLE CALENDAR INTEGRATION
        create_calendar_event(
            name,
            context.user_data["lesson_date"],
            context.user_data["lesson_time"],
            text
        )

        save_students()
        context.user_data.clear()

        await update.message.reply_text("✅ Урок добавлен + Google Calendar")
        return

# ==========================================
# CALLBACKS
# ==========================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("lesson_"):
        name = data.replace("lesson_", "")
        context.user_data["lesson_student"] = name
        context.user_data["step"] = "lesson_date"
        await query.message.reply_text("📅 Дата:")
        return

    if data.startswith("payment_"):
        name = data.replace("payment_", "")
        context.user_data["step"] = "payment_input"
        context.user_data["student_payment"] = name
        await query.message.reply_text("💰 Сумма:")
        return

    if data.startswith("delete_"):
        name = data.replace("delete_", "")
        students.pop(name, None)
        save_students()
        await query.edit_message_text("🗑 удалено")
        return

# ==========================================
# MAIN
# ==========================================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(callback))

    print("CRM BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
