import os
import json
import logging
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

# ======================
# ACCESS (добавь свой ID сюда)
# ======================
ALLOWED_USERS = {6604090880}  # например: {123456789}

def allowed(user_id: int):
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
    ["➕ Add Student", "📋 Students"],
    ["💰 Stats", "📈 Analytics"]
], resize_keyboard=True)

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа")
        return

    await update.message.reply_text("🎓 CRM Bot запущен", reply_markup=menu)

# ======================
# GRAPH
# ======================
async def send_chart(update, name):
    data = students[name].get("progress", [])

    if not data:
        await update.message.reply_text("Нет данных прогресса")
        return

    plt.figure()
    plt.plot(data, marker="o")
    plt.title(f"Progress: {name}")
    plt.xlabel("Lessons")
    plt.ylabel("Score")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    await update.message.reply_photo(photo=buffer)

# ======================
# CALLBACK BUTTONS
# ======================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("pay_"):
        name = data[4:]
        students[name]["paid"] += 100

    elif data.startswith("lesson_"):
        name = data[7:]
        students[name]["lessons"] += 1
        students[name].setdefault("progress", []).append(students[name]["lessons"])

    elif data.startswith("del_"):
        name = data[4:]
        students.pop(name, None)

    save()
    await query.edit_message_text("✅ Updated")

# ======================
# MAIN HANDLER
# ======================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return

    text = update.message.text

    # MENU
    if text == "➕ Add Student":
        context.user_data["step"] = "name"
        await update.message.reply_text("Имя студента:")
        return

    if text == "📋 Students":
        if not students:
            await update.message.reply_text("Пусто")
            return

        msg = ""
        for name, s in students.items():
            msg += (
                f"\n👤 {name}\n"
                f"Class: {s.get('class','-')}\n"
                f"Goal: {s.get('goal','-')}\n"
                f"Paid: {s.get('paid',0)}\n"
                f"Lessons: {s.get('lessons',0)}\n"
                f"-----------------\n"
            )

        await update.message.reply_text(msg)
        return

    if text == "💰 Stats":
        total = sum(s.get("paid", 0) for s in students.values())
        lessons = sum(s.get("lessons", 0) for s in students.values())

        await update.message.reply_text(
            f"💰 Total: {total}\n📚 Lessons: {lessons}"
        )
        return

    if text == "📈 Analytics":
        context.user_data["chart"] = True
        await update.message.reply_text("Введи имя студента:")
        return

    # CHART
    if context.user_data.get("chart"):
        name = text

        if name not in students:
            await update.message.reply_text("Нет такого студента")
            return

        await send_chart(update, name)
        context.user_data["chart"] = False
        return

    # ADD FLOW
    step = context.user_data.get("step")

    if step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "class"
        await update.message.reply_text("Класс:")
        return

    if step == "class":
        context.user_data["class"] = text
        context.user_data["step"] = "goal"
        await update.message.reply_text("Цель:")
        return

    if step == "goal":
        name = context.user_data["name"]

        students[name] = {
            "class": context.user_data["class"],
            "goal": text,
            "paid": 0,
            "lessons": 0,
            "progress": []
        }

        save()
        context.user_data.clear()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 +100", callback_data=f"pay_{name}")],
            [InlineKeyboardButton("📚 +1 lesson", callback_data=f"lesson_{name}")],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"del_{name}")]
        ])

        await update.message.reply_text("✅ Student added", reply_markup=keyboard)

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
