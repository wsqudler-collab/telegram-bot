import os
import json
import asyncio
import logging
from datetime import datetime

import matplotlib.pyplot as plt
from io import BytesIO

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ======================
# TOKEN
# ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден")

logging.basicConfig(level=logging.INFO)

# ======================
# ACCESS
# ======================
ALLOWED_USERS = {6604090880} # сюда вставь свой ID: {123456789}
PENDING_USERS = set()

def is_allowed(user_id):
    return not ALLOWED_USERS or user_id in ALLOWED_USERS

# ======================
# DATA
# ======================
DATA_FILE = "students.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        students = json.load(f)
else:
    students = {}

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=4)

# ======================
# UI MENU
# ======================
menu = ReplyKeyboardMarkup([
    ["🎓 Students", "📊 Dashboard"],
    ["➕ Add Student", "📅 Schedule"]
], resize_keyboard=True)

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        PENDING_USERS.add(user_id)
        await update.message.reply_text("⏳ Заявка отправлена, ожидай одобрения.")
        return

    await update.message.reply_text("🎓 CRM бот запущен", reply_markup=menu)

# ======================
# HANDLE TEXT
# ======================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        return

    # ADD STUDENT
    if text == "➕ Add Student":
        context.user_data["step"] = "name"
        await update.message.reply_text("Имя студента:")
        return

    # LIST
    if text == "🎓 Students":
        if not students:
            await update.message.reply_text("Нет студентов")
            return

        msg = "📋 Students:\n\n"
        for name, s in students.items():
            msg += (
                f"👤 {name}\n"
                f"📚 Class: {s.get('class','-')}\n"
                f"🎯 Goal: {s.get('goal','-')}\n"
                f"💰 Paid: {s.get('paid',0)}\n"
                f"📅 Lessons: {len(s.get('lessons',[]))}\n\n"
            )

        await update.message.reply_text(msg)
        return

    # DASHBOARD
    if text == "📊 Dashboard":
        total = sum(s.get("paid", 0) for s in students.values())
        lessons = sum(len(s.get("lessons", [])) for s in students.values())

        await update.message.reply_text(
            f"📊 Dashboard\n\n💰 Total: {total}\n📚 Lessons: {lessons}"
        )
        return

    # SCHEDULE
    if text == "📅 Schedule":
        msg = "📅 Lessons:\n\n"

        for name, s in students.items():
            for l in s.get("lessons", []):
                msg += f"{name} → {l['datetime']} ({l['topic']})\n"

        await update.message.reply_text(msg)
        return

    # STEP FLOW
    step = context.user_data.get("step")

    if step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "class"
        await update.message.reply_text("Class:")
        return

    if step == "class":
        context.user_data["class"] = text
        context.user_data["step"] = "goal"
        await update.message.reply_text("Goal:")
        return

    if step == "goal":
        name = context.user_data["name"]

        students[name] = {
            "class": context.user_data["class"],
            "goal": text,
            "paid": 0,
            "lessons": []
        }

        save()
        context.user_data.clear()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Lesson", callback_data=f"addlesson_{name}")],
            [InlineKeyboardButton("💰 +100", callback_data=f"pay_{name}")],
            [InlineKeyboardButton("📈 Progress", callback_data=f"chart_{name}")],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"del_{name}")]
        ])

        await update.message.reply_text(f"✅ Student {name} added", reply_markup=keyboard)
        return

# ======================
# GRAPH
# ======================
async def send_chart(update, name):
    student = students.get(name)

    if not student:
        await update.callback_query.message.reply_text("Student not found")
        return

    lessons = student.get("lessons", [])

    if not lessons:
        await update.callback_query.message.reply_text("No lessons yet")
        return

    x = list(range(1, len(lessons) + 1))
    y = list(range(1, len(lessons) + 1))

    plt.figure()
    plt.plot(x, y, marker="o")
    plt.title(f"Progress: {name}")
    plt.xlabel("Lessons")
    plt.ylabel("Progress")

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)

    await update.callback_query.message.reply_photo(photo=buf)
    plt.close()

# ======================
# CALLBACKS
# ======================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # payment
    if data.startswith("pay_"):
        name = data[4:]
        students[name]["paid"] += 100

    # delete
    elif data.startswith("del_"):
        name = data[4:]
        students.pop(name, None)

    # add lesson
    elif data.startswith("addlesson_"):
        name = data[11:]
        students[name].setdefault("lessons", []).append({
            "datetime": "2026-05-13 18:00",
            "topic": "Lesson",
            "reminded_2h": False,
            "reminded_30m": False
        })

    # chart
    elif data.startswith("chart_"):
        name = data.replace("chart_", "")
        await send_chart(update, name)
        return

    save()
    await query.edit_message_text("✅ Updated")

# ======================
# MAIN
# ======================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(callback))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
