import os
import json
import logging

print("CALENDAR_ID RAW:", repr(os.getenv("CALENDAR_ID")))
print("GOOGLE_CREDS LOADED:", bool(os.getenv("GOOGLE_CREDENTIALS")))

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
# GOOGLE CALENDAR
# ==========================================

GOOGLE_CREDS = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

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

CALENDAR_ID = os.getenv("CALENDAR_ID")

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

# ==========================================
# ACCESS SYSTEM
# ==========================================

def has_access(user_id):
    return user_id in approved_users


# ==========================================
# START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "👨‍🏫 Панель преподавателя",
            reply_markup=main_menu
        )
        return

    if has_access(user.id):
        await update.message.reply_text(
            "✅ Доступ разрешён",
            reply_markup=main_menu
        )
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Принять",
                callback_data=f"accept_{user.id}"
            ),
            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data=f"reject_{user.id}"
            ),
        ]
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📩 Новая заявка\n\n"
                f"👤 {user.full_name}\n"
                f"🆔 {user.id}"
            ),
            reply_markup=keyboard
        )
    except:
        pass

    await update.message.reply_text(
        "⏳ Заявка отправлена администратору"
    )


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
        next_lesson = lessons[-1]

        text += (
            f"\n📅 Следующий урок:\n"
            f"{next_lesson['дата']} {next_lesson['время']}\n"
            f"📘 {next_lesson['тема']}"
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💰 Добавить оплату",
                callback_data=f"payment_{name}"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 Назначить урок",
                callback_data=f"lesson_{name}"
            )
        ],
        [
            InlineKeyboardButton(
                "📈 График",
                callback_data=f"chart_{name}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить",
                callback_data=f"delete_{name}"
            )
        ]
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# GRAPH
# ==========================================

async def send_chart(update, name):
    student = students.get(name)

    if not student:
        return

    lessons = student.get("уроки", 0)

    if lessons == 0:
        await update.callback_query.message.reply_text(
            "Нет уроков для графика"
        )
        return

    x = list(range(1, lessons + 1))
    y = []

    total = 0

    for i in range(lessons):
        total += 1
        y.append(total)

    plt.figure(figsize=(6, 4))
    plt.plot(x, y, marker="o")
    plt.title(f"Прогресс: {name}")
    plt.xlabel("Урок")
    plt.ylabel("Количество уроков")

    buf = BytesIO()

    plt.savefig(buf, format="png")

    buf.seek(0)

    await update.callback_query.message.reply_photo(photo=buf)

    plt.close()


# ==========================================
# TEXT HANDLER
# ==========================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not has_access(user_id):
        return

    text = update.message.text

    # ======================================
    # ADD STUDENT
    # ======================================

    if text == "➕ Добавить студента":
        context.user_data["step"] = "student_name"

        await update.message.reply_text(
            "👤 Введи имя студента:"
        )

        return

    # ======================================
    # STUDENTS
    # ======================================

    if text == "📚 Студенты":
        if not students:
            await update.message.reply_text(
                "Список пуст"
            )

            return

        for name in students:
            await send_student_card(update, name)

        return

    # ======================================
    # SCHEDULE
    # ======================================

    if text == "📅 Расписание":
        msg = "📅 Расписание:\n\n"

        found = False

        for name, s in students.items():
            for lesson in s.get("уроки_список", []):
                found = True

                msg += (
                    f"👤 {name}\n"
                    f"📅 {lesson['дата']} {lesson['время']}\n"
                    f"📘 {lesson['тема']}\n\n"
                )

        if not found:
            msg += "Нет занятий"

        await update.message.reply_text(msg)

        return

    # ======================================
    # STATS
    # ======================================

    if text == "📊 Статистика":
        total_money = sum(
            s.get("оплата", 0)
            for s in students.values()
        )

        total_lessons = sum(
            s.get("уроки", 0)
            for s in students.values()
        )

        await update.message.reply_text(
            f"📊 Общая статистика\n\n"
            f"👥 Студентов: {len(students)}\n"
            f"💰 Заработано: {total_money} ₽\n"
            f"📖 Всего уроков: {total_lessons}"
        )

        return

    # ======================================
    # CREATE STUDENT FLOW
    # ======================================

    step = context.user_data.get("step")

    if step == "student_name":
        context.user_data["name"] = text
        context.user_data["step"] = "student_class"

        await update.message.reply_text(
            "📚 Введи класс:"
        )

        return

    if step == "student_class":
        context.user_data["class"] = text
        context.user_data["step"] = "student_goal"

        await update.message.reply_text(
            "🎯 Введи цель подготовки:"
        )

        return

    if step == "student_goal":
        context.user_data["goal"] = text
        context.user_data["step"] = "student_note"

        await update.message.reply_text(
            "📝 Введи заметку:"
        )

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

        await update.message.reply_text(
            f"✅ Студент {name} добавлен"
        )

        return

    # ======================================
    # PAYMENT INPUT
    # ======================================

    if step == "payment_input":
        name = context.user_data["student_payment"]

        try:
            amount = int(text)

        except:
            await update.message.reply_text(
                "Введите число"
            )

            return

        students[name]["оплата"] += amount
        students[name]["уроки"] += 1

        save_students()

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Добавлено {amount} ₽\n"
            f"📖 Уроков: {students[name]['уроки']}"
        )

        return

    # ======================================
    # LESSON FLOW
    # ======================================

    if step == "lesson_date":
        context.user_data["lesson_date"] = text
        context.user_data["step"] = "lesson_time"

        await update.message.reply_text(
            "⏰ Введи время (18:00):"
        )

        return

    if step == "lesson_time":
        context.user_data["lesson_time"] = text
        context.user_data["step"] = "lesson_topic"

        await update.message.reply_text(
            "📘 Введи тему урока:"
        )

        return

    if step == "lesson_topic":
        name = context.user_data["lesson_student"]

        lesson = {
            "дата": context.user_data["lesson_date"],
            "время": context.user_data["lesson_time"],
            "тема": text,
        }

        students[name]["уроки_список"].append(lesson)

        save_students()

        calendar_link = create_google_event(
            student_name=name,
            lesson_date=context.user_data["lesson_date"],
            lesson_time=context.user_data["lesson_time"],
            topic=text
        )

        context.user_data.clear()

        message = "✅ Урок добавлен"

        if calendar_link:
            message += (
                f"\n\n📅 Google Calendar:\n{calendar_link}"
            )
        else:
            message += (
                "\n\n⚠️ Не удалось добавить в Google Calendar"
            )

        await update.message.reply_text(message)

        return


# ==========================================
# CALLBACKS
# ==========================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()

    data = query.data

    # ======================================
    # ACCEPT
    # ======================================

    if data.startswith("accept_"):
        user_id = int(data.replace("accept_", ""))

        if user_id not in approved_users:
            approved_users.append(user_id)

        save_users()

        await context.bot.send_message(
            user_id,
            "✅ Доступ одобрен"
        )

        await query.edit_message_text(
            "✅ Пользователь одобрен"
        )

        return

    # ======================================
    # REJECT
    # ======================================

    if data.startswith("reject_"):
        user_id = int(data.replace("reject_", ""))

        await context.bot.send_message(
            user_id,
            "❌ Заявка отклонена"
        )

        await query.edit_message_text(
            "❌ Пользователь отклонён"
        )

        return

    # ======================================
    # PAYMENT
    # ======================================

    if data.startswith("payment_"):
        name = data.replace("payment_", "")

        context.user_data["step"] = "payment_input"
        context.user_data["student_payment"] = name

        await query.message.reply_text(
            f"💰 Введи сумму оплаты для {name}:"
        )

        return

    # ======================================
    # LESSON
    # ======================================

    if data.startswith("lesson_"):
        name = data.replace("lesson_", "")

        context.user_data["lesson_student"] = name
        context.user_data["step"] = "lesson_date"

        await query.message.reply_text(
            "📅 Введи дату урока (13.05.2026):"
        )

        return

    # ======================================
    # DELETE
    # ======================================

    if data.startswith("delete_"):
        name = data.replace("delete_", "")

        if name in students:
            del students[name]

        save_students()

        await query.edit_message_text(
            f"🗑 Студент {name} удалён"
        )

        return

    # ======================================
    # CHART
    # ======================================

    if data.startswith("chart_"):
        name = data.replace("chart_", "")

        await send_chart(update, name)

        return


# ==========================================
# MAIN
# ==========================================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle
        )
    )

    app.add_handler(
        CallbackQueryHandler(callback)
    )

    print("CRM BOT RUNNING...")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
