import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("8733489007:AAFYFiMbER9Cp00XTid5TjB3az6AftPpMNo")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я работаю на Railway")

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN не найден в переменных окружения Railway")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # Если раньше пробовала webhook, удаляем его и работаем через polling
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
