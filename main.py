import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("8733489007:AAH_So9kjUljYsbgXDjcwty81IcoebKelwg")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает")

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN не найден")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
