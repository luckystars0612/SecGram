import asyncio
import random
import os
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserBannedInChannelError, RPCError
import pika
import json
from dotenv import load_dotenv
from account_manager import AccountManager
from utils import send_email, logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
USE_DATABASE = os.getenv("USE_DATABASE", "false").lower() == "true"
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Constants
NORMAL_INTERVAL = 3600  # 1 hour
FALLBACK_INTERVAL = 21600  # 6 hours
FALLBACK_CHANNEL_LIMIT = 5  # Max channels in fallback mode

# Channel file paths
CHANNELS_FILE = "/app/resources/telegram_channels.txt"
PRIORITY_CHANNELS_FILE = "/app/resources/priority_channels.txt"

# Channel loader with priority parsing
class ChannelLoader(FileSystemEventHandler):
    def __init__(self, file_path: str, is_priority: bool = False):
        self.file_path = file_path
        self.is_priority = is_priority
        self.channels = []
        self.load_channels()

    def load_channels(self):
        try:
            if not os.path.exists(self.file_path):
                self.channels = []
                return
            with open(self.file_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]
                if self.is_priority:
                    # Parse channel,priority (e.g., "channel,5")
                    self.channels = [(line.split(",")[0], int(line.split(",")[1])) if "," in line else (line, 1) for line in lines]
                    self.channels.sort(key=lambda x: x[1], reverse=True)  # Sort by priority descending
                    self.channels = [ch[0] for ch in self.channels]  # Keep only channel names
                else:
                    self.channels = lines
            logger.info(f"Loaded {len(self.channels)} channels from {self.file_path}")
        except Exception as e:
            logger.error(f"Error loading channels from {self.file_path}: {e}", exc_info=True)

    def on_modified(self, event):
        if not event.is_directory and event.src_path == self.file_path:
            self.load_channels()

    def get_channels(self) -> list[str]:
        return self.channels

# RabbitMQ publishing
def publish_to_queue(data, queue_name):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name)
        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(data))
        connection.close()
    except Exception as e:
        logger.error(f"Error publishing to RabbitMQ: {e}", exc_info=True)

async def join_channel(client: TelegramClient, channel: str):
    try:
        await client(functions.channels.JoinChannelRequest(channel))
        logger.info(f"Joined {channel}")
        await asyncio.sleep(random.uniform(5, 15))  # Random delay between joins
        return True
    except RPCError as e:
        logger.warning(f"Failed to join {channel}: {e}")
        return False

async def update_channel_joins(mgr: AccountManager, channels: list[str]):
    for account in mgr.accounts:
        if account.is_banned:
            continue
        try:
            client = await mgr.get_client(account)
            for channel in channels:
                if not account.joined_all_channels:
                    await join_channel(client, channel)
            account.joined_all_channels = True
            await client.disconnect()
        except Exception as e:
            logger.error(f"Error updating joins for {account.name}: {e}", exc_info=True)

async def scrape_channel(client: TelegramClient, channel: str, account: Account, mgr: AccountManager):
    try:
        async for message in client.iter_messages(channel, limit=100):
            if message.text:
                data = {"source": channel, "content": message.text, "timestamp": message.date.isoformat()}
                queue = "scraped_data" if not USE_DATABASE else "db_data"
                publish_to_queue(data, queue)
    except UserBannedInChannelError:
        mgr.mark_banned(account.name)
        if mgr.active_count() == 1:
            send_email("Fallback Mode Activated", "Only 1 account active. Reduced scraping frequency.")
        new_account = mgr.get_random_available_account()
        new_client = await mgr.get_client(new_account)
        if await join_channel(new_client, channel):
            await scrape_channel(new_client, channel, new_account, mgr)
    except FloodWaitError as e:
        logger.info(f"Flood wait: Waiting {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"Error scraping {channel}: {e}", exc_info=True)

async def main():
    mgr = AccountManager("/app/resources/sessions/", API_ID, API_HASH)
    if mgr.active_count() < 1:
        send_email("Critical: No Active Accounts", "No active accounts available. Scraping stopped.")
        logger.critical("No active accounts. Stopping.")
        return

    # Setup channel watchers
    all_channels_loader = ChannelLoader(CHANNELS_FILE)
    priority_channels_loader = ChannelLoader(PRIORITY_CHANNELS_FILE, is_priority=True)
    
    observer = Observer()
    observer.schedule(all_channels_loader, path="/app/resources/", recursive=False)
    observer.schedule(priority_channels_loader, path="/app/resources/", recursive=False)
    observer.start()

    try:
        while True:
            mgr.update_accounts()  # Check for deleted session files
            active_accounts = mgr.active_count()
            all_channels = all_channels_loader.get_channels()
            priority_channels = priority_channels_loader.get_channels()

            if active_accounts < 1:
                send_email("Critical: All Accounts Banned", "All accounts banned. Scraping stopped.")
                logger.critical("No active accounts remaining. Stopping.")
                break

            # Adjust mode based on active accounts
            if active_accounts == 1:
                interval = FALLBACK_INTERVAL
                scrape_channels = priority_channels[:FALLBACK_CHANNEL_LIMIT] if priority_channels else all_channels[:FALLBACK_CHANNEL_LIMIT]
                logger.info(f"Fallback mode: 1 account active, scraping {len(scrape_channels)} priority channels every {interval//3600} hours.")
            else:
                interval = NORMAL_INTERVAL
                scrape_channels = all_channels
                logger.info(f"Normal mode: {active_accounts} accounts active, scraping {len(scrape_channels)} channels every {interval//3600} hour(s).")

            await update_channel_joins(mgr, all_channels)

            for channel in scrape_channels:
                try:
                    account = mgr.get_random_available_account()
                    client = await mgr.get_client(account)
                    logger.info(f"Scraping {channel} with {account.name}")
                    await scrape_channel(client, channel, account, mgr)
                    await client.disconnect()

                    if random.random() > 0.5:  # 50% chance to reuse
                        sleep_time = random.uniform(5, 30)
                        logger.info(f"Sleeping {sleep_time:.2f} seconds before next crawl")
                        await asyncio.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Error in scrape loop for {channel}: {e}", exc_info=True)

            logger.info(f"Completed crawl cycle. Waiting {interval//3600} hour(s) for next cycle.")
            await asyncio.sleep(interval)

    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    asyncio.run(main())