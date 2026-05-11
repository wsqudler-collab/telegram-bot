import logging
import json
import os

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
    filters,
    ContextTypes,
    CallbackQueryHandler
)

TELEGRAM_TOKEN = os.getenv("8733489007:AAH_So9kjUljYsbgXDjcwty81IcoebKelwg")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DATA_FILE = "students.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        students = json.load(f)
else:
    students = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=4)

main_keyboard = ReplyKeyboardMarkup(
    [
        ["➕ Add Student", "📋 Students"],
        ["💰 Finance", "📝 Notes"]
    ],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот работает ✅",
        reply_markup=main_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "➕ Add Student":
        context.user_data["waiting_for_student_name"] = True
        await update.message.reply_text("Введите имя студента:")
        return

    if text == "📋 Students":

        if not students:
            await update.message.reply_text("Список студентов пуст.")
            return

        message = "📋 Студенты:\n\n"

        for student in students:
            message += f"• {student}\n"

        await update.message.reply_text(message)
        return

    if text == "💰 Finance":

        total = 0

        for student in students.values():
            total += student.get("paid", 0)

        await update.message.reply_text(
            f"💰 Общая сумма: {total}"
        )
        return

    if text == "📝 Notes":
        await update.message.reply_text(
            "Раздел заметок пока пуст."
        )
        return

    if context.user_data.get("waiting_for_student_name"):

        student_name = text

        students[student_name] = {
            "paid": 0
        }

        save_data()

        context.user_data["waiting_for_student_name"] = False

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "💵 Add Payment",
                    callback_data=f"pay_{student_name}"
                )
            ]
        ])

        await update.message.reply_text(
            f"✅ Студент {student_name} добавлен.",
            reply_markup=keyboard
        )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("pay_"):

        student_name = data.replace("pay_", "")

        students[student_name]["paid"] += 100

        save_data()

        await query.edit_message_text(
            f"💵 Оплата добавлена\n\n"
            f"{student_name}: {students[student_name]['paid']}"
        )

def main():

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_handler(CallbackQueryHandler(button_click))

    print("Бот запущен ✅")

    app.run_polling()

if __name__ == "__main__":
    main()
