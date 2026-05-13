import os
import logging
import json

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ===== TOKEN =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден")

# ===== LOGGING =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ===== DATA =====
DATA_FILE = "students.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        students = json.load(f)
else:
    students = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=4)

# ===== UI =====
keyboard = ReplyKeyboardMarkup(
    [
        ["➕ Add Student", "📋 Students"],
        ["💰 Finance"]
    ],
    resize_keyboard=True
)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен ✅", reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "➕ Add Student":
        context.user_data["add"] = True
        await update.message.reply_text("Введите имя студента:")
        return

    if text == "📋 Students":
        if not students:
            await update.message.reply_text("Список пуст")
            return

        msg = "\n".join([f"• {s}" for s in students])
        await update.message.reply_text(msg)
        return

    if text == "💰 Finance":
        total = sum([v.get("paid", 0) for v in students.values()])
        await update.message.reply_text(f"💰 Общая сумма: {total}")
        return

    if context.user_data.get("add"):
        name = text
        students[name] = {"paid": 0}
        save_data()
        context.user_data["add"] = False

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 +100", callback_data=f"pay_{name}")]
        ])

        await update.message.reply_text(f"Добавлен {name}", reply_markup=keyboard)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("pay_"):
        name = data.replace("pay_", "")
        students[name]["paid"] += 100
        save_data()

        await query.edit_message_text(f"{name}: {students[name]['paid']}")

# ===== MAIN =====
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))

    print("Бот запущен ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
