import asyncio
import logging
from account_manager import AccountManager, Account
from telethon import events
from utils.db_utils import get_joined_channels

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def handle_new_messages(account: 'Account', channel: str) -> None:
    """Handle new messages from a specific channel, printing them to the console for debugging."""
    @account.client.on(events.NewMessage(chats=[channel]))
    async def new_message_handler(event):
        message = event.message
        if message and message.text:
            logger.debug(f"New message in {channel} for account {account.name}: "
                         f"ID={message.id}, Text='{message.text}', Date={message.date}")

async def main():
    """Main function to initialize AccountManager, join channels, and listen for new messages from joined channels."""
    try:
        # Initialize AccountManager with paths and proxy
        manager = AccountManager(
            resources_dir="/home/kali/Desktop/SecGram/resources",
            db_path="/home/kali/Desktop/SecGram/telegram.db",
            proxy_pool=[{'type': 'http', 'host': '10.65.47.23', 'port': 8080}]  # Your specified proxy
        )

        # Get the active account
        account = await manager.get_active_account()

        # Join all required channels and set up message listeners
        await account.process_channels(manager.required_channels)

        # Get joined channels from the database
        joined_channels = set(get_joined_channels(account.db_conn, account.name))
        logger.info(f"Joined channels for {account.name}: {joined_channels}")

        # Set up listeners for new messages in each joined channel
        for channel in joined_channels:
            await handle_new_messages(account, channel)
            logger.debug(f"Listening for new messages in channel {channel} for account {account.name}")

        # Keep the script running to listen for updates (you can interrupt with Ctrl+C)
        try:
            while True:
                await asyncio.sleep(1)  # Keep the event loop running
        except KeyboardInterrupt:
            logger.info("Stopping Telegram scraper service...")
            await account.disconnect()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())