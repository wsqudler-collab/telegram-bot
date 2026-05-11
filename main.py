import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8733489007:AAH_So9kjUljYsbgXDjcwty81IcoebKelwg"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает!")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()