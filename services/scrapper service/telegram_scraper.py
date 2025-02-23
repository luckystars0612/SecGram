from telethon import TelegramClient
from config.settings import API_ID, API_HASH, USE_DATABASE
from message_broker import send_to_db_service, send_to_bot_service

client = TelegramClient('scraper', API_ID, API_HASH)

async def scrape_telegram():
    async with client:
        for channel in get_channels():
            async for message in client.iter_messages(channel):
                data = {"source": channel, "content": message.text}
                if USE_DATABASE:
                    send_to_db_service(data)  # Send to DB if enabled
                else:
                    send_to_bot_service(data)  # Send to bot directly

def get_channels():
    # Load from resources or DB
    with open("resources/telegram_channels.txt", "r") as f:
        return f.read().splitlines()

if __name__ == "__main__":
    client.loop.run_until_complete(scrape_telegram())