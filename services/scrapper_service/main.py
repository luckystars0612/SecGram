import asyncio
import logging
from account_manager import AccountManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the Telegram scraper service."""
    try:
        # Initialize AccountManager with paths and proxy
        manager = AccountManager(
            session_dir="/home/kali/Desktop/SecGram/resources/sessions",
            accounts_file="/home/kali/Desktop/SecGram/resources/accounts.json",
            db_path="/home/kali/Desktop/SecGram/telegram.db",
            proxy_pool=[{'type': 'http', 'host': '10.65.47.23', 'port': 8080}]  # Your specified proxy
        )

        # Test channels and fetch messages
        await manager._test_channels()

        logger.info("Telegram scraper service completed successfully")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())