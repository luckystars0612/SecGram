from telegram.ext import Updater, CommandHandler
from config.settings import TELEGRAM_TOKEN, USE_DATABASE
from message_broker import publish_to_channel, receive_from_broker

def start(update, context):
    update.message.reply_text("Bot started!")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    updater.start_polling()

    # Listen for incoming data
    while True:
        data = receive_from_broker()  # Receive from Scraper or DB
        if data:
            if USE_DATABASE:
                # Fetch from DB (pseudocode)
                pass
            else:
                publish_to_channel(data)  # Post directly to channel

if __name__ == "__main__":
    main()