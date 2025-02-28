import asyncio
import os
import random
import json
from typing import List, Dict, Optional
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Account:
    """Represents a Telegram account with session management and channel tracking using Telethon."""
    def __init__(self, session_file: str, name: str, api_id: str, api_hash: str, db_path: str, proxy: Optional[Dict] = None):
        """
        Initialize an Account instance.

        :param session_file: Path to session file (Telethon .session)
        :param name: Phone number
        :param api_id: Telegram API ID
        :param api_hash: Telegram API hash
        :param db_path: Path to SQLite database
        :param proxy: Optional proxy settings (e.g., {'type': 'http', 'host': '10.65.47.23', 'port': 8080})
        """
        # Use absolute path for session file
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.session_file = os.path.join(project_root, 'resources', 'sessions', session_file)
        self.name = name  # This is the phone number, e.g., "84896869942"
        self.api_id = api_id
        self.api_hash = api_hash
        self.db_path = db_path
        self.proxy = proxy  # Store as dict: {'type': 'http', 'host': '10.65.47.23', 'port': 8080}
        self.client = None
        self.is_banned = self._get_account_status() == 'banned'

    def _get_account_status(self) -> str:
        """Get the status of an account from the database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM accounts WHERE phone = ?", (self.name,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result[0] if result else 'active'
        except sqlite3.Error as e:
            logger.error(f"SQLite error getting account status for {self.name}: {e}")
            return 'active'
        except Exception as e:
            logger.error(f"Error getting account status for {self.name}: {e}")
            return 'active'

    def _update_account_status(self, status: str) -> None:
        """Update the status of the account in the database."""
        if status not in ['active', 'banned']:
            raise ValueError("Status must be 'active' or 'banned'")
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET status = ? WHERE phone = ?", (status, self.name))
            conn.commit()
            cursor.close()
            conn.close()
            logger.debug(f"Updated status for {self.name} to {status}")
        except sqlite3.Error as e:
            logger.error(f"SQLite error updating status for {self.name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating status for {self.name}: {e}")
            raise

    def _add_channel_to_db(self, channel: str) -> None:
        """Add a channel for the account to the database with date_joined."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            date_joined = datetime.utcnow()
            cursor.execute("INSERT OR REPLACE INTO channels (phone, channel, date_joined) VALUES (?, ?, ?)",
                          (self.name, channel, date_joined))
            conn.commit()
            cursor.close()
            conn.close()
            logger.debug(f"Added channel {channel} with date_joined {date_joined} for {self.name} to database")
        except sqlite3.Error as e:
            logger.error(f"SQLite error adding channel {channel} for {self.name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error adding channel {channel} to database for {self.name}: {e}")
            raise

    def get_joined_channels_from_db(self) -> List[str]:
        """Get the list of joined channels for an account from the database, including date_joined."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT channel FROM channels WHERE phone = ?", (self.name,))
            channels = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return channels
        except sqlite3.Error as e:
            logger.error(f"SQLite error getting joined channels from database for {self.name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting joined channels from database for {self.name}: {e}")
            return []

    async def connect(self) -> bool:
        """Connect to Telegram using Telethon with optional proxy, with retry logic for connection issues."""
        logger.debug(f"Attempting Telethon login for {self.name} with session file {self.session_file}")
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Verify session file existence and permissions
                if not os.path.exists(self.session_file):
                    logger.error(f"Session file {self.session_file} does not exist")
                    return False
                if not os.access(self.session_file, os.R_OK | os.W_OK):
                    logger.error(f"No read/write permissions for {self.session_file}")
                    return False

                # Configure proxy if provided
                proxy_settings = None
                if self.proxy:
                    proxy_type = self.proxy.get('type', 'http').lower()
                    if proxy_type == 'http':
                        proxy_settings = ('http', self.proxy['host'], self.proxy['port'])
                    elif proxy_type == 'socks5':
                        proxy_settings = ('socks5', self.proxy['host'], self.proxy['port'])
                    logger.debug(f"Using proxy for {self.name}: {proxy_settings}")

                # Initialize Telethon client with session file and proxy
                self.client = TelegramClient(self.session_file, self.api_id, self.api_hash, proxy=proxy_settings)
                await self.client.start()
                logger.info(f"Connected account: {self.name} using Telethon session")
                return True
            except Exception as e:
                logger.error(f"Failed to connect {self.name} (attempt {retry_count + 1}/{max_retries}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying connection in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    self.client = None  # Ensure client is None on failure
                    return False

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()
            logger.debug(f"Disconnected account: {self.name}")
            logger.info(f"Disconnected account: {self.name}")
            self.client = None  # Clear client after disconnection

    async def process_channels(self, required_channels: List[str]) -> None:
        """Process channels: check join status against DB, join if needed, update DB with date_joined, and scrape messages, using a single connection."""
        if not await self.connect():
            logger.error(f"Failed to connect account {self.name}. Skipping channel processing.")
            return

        try:
            # Get joined channels from database (more efficient than Telegram API)
            joined_channels_db = set(self.get_joined_channels_from_db())
            logger.info(f"Required channels: {required_channels}")
            logger.info(f"Joined channels (Database): {joined_channels_db}")

            # Check if database is up-to-date with required channels
            missing_channels = [channel for channel in required_channels if channel not in joined_channels_db]

            if not missing_channels:
                logger.debug(f"Database is up-to-date with required channels. Skipping Telegram fetch and joining.")
                # Directly scrape 5 latest messages from each required channel
                for channel in required_channels:
                    messages = await self.scrape_messages(channel, limit=5)
                    logger.debug(f"5 latest messages from {channel} for {self.name}: {messages}")
            else:
                logger.debug(f"Database lacks {len(missing_channels)} channels. Fetching from Telegram and joining missing channels.")
                # Fetch joined channels from Telegram to verify and update database
                joined_channels_telegram = await self.get_joined_channels()
                logger.info(f"Joined channels (Telegram): {joined_channels_telegram}")

                # Update database with any channels joined in Telegram but not in DB
                for channel in joined_channels_telegram:
                    if channel not in joined_channels_db:
                        self._add_channel_to_db(channel)
                        joined_channels_db.add(channel)
                        logger.debug(f"Verified and added {channel} to database for {self.name}")

                # Join missing channels and update database with date_joined
                for channel in missing_channels:
                    try:
                        await self.join_channel(channel)
                        logger.info(f"Joined {channel} for account {self.name}")
                    except Exception as e:
                        logger.error(f"Failed to join {channel} for {self.name}: {e}")
                        continue

                # Scrape 5 latest messages from all required channels after updates
                for channel in required_channels:
                    messages = await self.scrape_messages(channel, limit=5)
                    logger.debug(f"5 latest messages from {channel} for {self.name}: {messages}")
        finally:
            await self.disconnect()

    async def join_channel(self, channel: str) -> None:
        """Join a Telegram channel and update the database using Telethon with date_joined."""
        logger.debug(f"Calling join_channel for {self.name} on channel {channel} using Telethon")
        await self.client(JoinChannelRequest(channel))
        self._add_channel_to_db(channel)
        await asyncio.sleep(random.uniform(3, 7))  # Random delay

    async def get_joined_channels(self) -> List[str]:
        """Retrieve joined channels from Telegram using Telethon."""
        logger.debug(f"Fetching joined channels for {self.name} using Telethon")
        joined_channels = []
        async for dialog in self.client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                entity = await self.client.get_entity(dialog.id)
                if hasattr(entity, 'username') and entity.username:
                    joined_channels.append(entity.username)
        logger.debug(f"Joined channels for {self.name}: {joined_channels}")
        return joined_channels

    async def scrape_messages(self, channel: str, limit: int = 5) -> List[dict]:
        """Scrape the 5 latest messages from a channel using Telethon."""
        logger.debug(f"Attempting to scrape {limit} latest messages from {channel} with account {self.name} using Telethon")
        if self.is_banned:
            logger.warning(f"Account {self.name} is banned, skipping scrape for {channel}")
            return []

        try:
            # Fetch the 5 latest messages
            messages = await self.client(GetHistoryRequest(
                peer=channel,
                limit=limit,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))
            logger.debug(f"Scraped {len(messages.messages)} messages from {channel} for {self.name} using Telethon: {messages.messages}")
            return [{'id': msg.id, 'text': msg.message, 'date': msg.date} for msg in messages.messages if msg.message]
        except Exception as e:
            error_msg = str(e)
            if 'FloodWait' in error_msg or 'UserBannedInChannel' in error_msg:
                logger.error(f"{self.name} banned or flood limited: {error_msg}")
                self.is_banned = True
                self._update_account_status('banned')
            else:
                logger.error(f"{self.name} failed to scrape {channel}: {e}")
            return []

    def get_status(self) -> str:
        """Get account status from the database."""
        return self._get_account_status()

    def __str__(self) -> str:
        """String representation of the account."""
        return (f"{'Session':<10}: {self.session_file}\n"
                f"{'API ID':<10}: {self.api_id}\n"
                f"{'API HASH':<10}: {self.api_hash}\n"
                f"{'Status':<10}: {self.get_status()}")

class AccountManager:
    """Manages multiple Telegram accounts with queue-based usage and real-time channel updates."""
    def __init__(self, session_dir: str, accounts_file: str, db_path: str, proxy_pool: List[Dict] = None, email_config: Dict = None):
        """
        Initialize the AccountManager.

        :param session_dir: Directory for session files
        :param accounts_file: Path to accounts JSON file
        :param db_path: Path to SQLite database
        :param proxy_pool: Optional list of proxies (e.g., [{'type': 'http', 'host': '10.65.47.23', 'port': 8080}])
        :param email_config: Optional email settings
        """
        logger.debug(f"Initializing AccountManager with session_dir={session_dir}, db_path={db_path}, accounts_file={accounts_file}")
        self.session_dir = session_dir
        self.db_path = db_path
        self.accounts = self._load_accounts(accounts_file, proxy_pool or [])
        self.required_channels = self._load_channels()
        self.proxy_pool = proxy_pool or []
        self.email_config = email_config
        self.account_queue = asyncio.Queue()
        for account in self.accounts:
            self.account_queue.put_nowait(account)
        logger.debug(f"Loaded accounts: {[acc.name for acc in self.accounts]}")
        # Initialize database only if it doesn’t exist
        self._initialize_database_once(accounts_file)
        self._setup_channel_watcher()

    def _initialize_database_once(self, accounts_file: str) -> None:
        """Initialize the database only if it doesn’t exist, importing accounts from JSON if needed."""
        try:
            if not os.path.exists(self.db_path):
                logger.info(f"Database {self.db_path} does not exist. Creating it...")
                Path(self.db_path).touch()
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS accounts (
                        phone TEXT PRIMARY KEY,
                        api_id TEXT NOT NULL,
                        api_hash TEXT NOT NULL,
                        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'banned'))
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS channels (
                        phone TEXT,
                        channel TEXT,
                        date_joined DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (phone, channel),
                        FOREIGN KEY (phone) REFERENCES accounts(phone)
                    )
                """)
                conn.commit()
                cursor.close()
                conn.close()

                # Load accounts from JSON if file exists
                if os.path.exists(accounts_file):
                    with open(accounts_file, 'r') as f:
                        accounts_data = json.load(f)
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    for account in accounts_data['accounts']:
                        phone = account['session'].split('.')[0]
                        cursor.execute("INSERT OR REPLACE INTO accounts (phone, api_id, api_hash, status) VALUES (?, ?, ?, 'active')",
                                      (phone, account['api_id'], account['api_hash']))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    logger.info("Accounts loaded from accounts.json into database")
                else:
                    logger.error(f"Accounts file {accounts_file} does not exist")
            else:
                logger.debug(f"Database {self.db_path} already exists, skipping initialization")
        except sqlite3.Error as e:
            logger.error(f"SQLite error initializing database: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON error loading accounts: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _load_accounts(self, accounts_file: str, proxy_pool: List[Dict]) -> List[Account]:
        """Load accounts from JSON file, optionally assigning proxies."""
        logger.debug(f"Loading accounts from {accounts_file}")
        accounts = []
        try:
            # Use absolute path to /home/kali/Desktop/SecGram/resources/accounts.json
            accounts_path = '/home/kali/Desktop/SecGram/resources/accounts.json'
            if not os.path.exists(accounts_path):
                logger.error(f"Accounts file {accounts_path} does not exist")
                return accounts

            with open(accounts_path, 'r') as f:
                data = json.load(f)
            for i, acc in enumerate(data['accounts']):
                proxy = proxy_pool[i % len(proxy_pool)] if proxy_pool else None
                logger.debug(f"Creating account for {acc['session']} with proxy={proxy}")
                accounts.append(Account(
                    session_file=acc['session'],  # Use relative path within resources/sessions/
                    name=acc['session'].split('.')[0],
                    api_id=acc['api_id'],
                    api_hash=acc['api_hash'],
                    db_path=self.db_path,
                    proxy=proxy
                ))
            return accounts
        except json.JSONDecodeError as e:
            logger.error(f"JSON error loading accounts: {e}")
            return accounts
        except Exception as e:
            logger.error(f"Error loading accounts: {e}")
            return accounts

    def _load_channels(self) -> List[str]:
        """Load required channels from /resources/channels.json."""
        logger.debug("Loading channels from /resources/channels.json")
        try:
            # Use absolute path to /home/kali/Desktop/SecGram/resources/channels.json
            channels_path = '/home/kali/Desktop/SecGram/resources/channels.json'
            if not os.path.exists(channels_path):
                logger.error(f"Channels file {channels_path} does not exist")
                return []

            with open(channels_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON error loading channels: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading channels: {e}")
            return []

    def _setup_channel_watcher(self) -> None:
        """Monitor /resources/channels.json for real-time updates."""
        logger.debug("Setting up channel file watcher for /resources/channels.json")
        class ChannelHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager

            def on_modified(self, event):
                if event.src_path.endswith('/resources/channels.json'):
                    logger.info("Channels file updated, reloading...")
                    self.manager.required_channels = self.manager._load_channels()
                    asyncio.run(self.manager._test_channels())

        # Use absolute path to /home/kali/Desktop/SecGram/resources/
        resources_path = '/home/kali/Desktop/SecGram/resources'
        observer = Observer()
        observer.schedule(ChannelHandler(self), path=resources_path, recursive=False)
        observer.start()

    async def _test_channels(self) -> None:
        """Test connecting to the account, checking joined channels against DB, joining unjoined channels, and crawling 5 latest messages."""
        logger.debug(f"Testing channels for accounts: {[acc.name for acc in self.accounts]}")
        account = await self.get_active_account()
        await account.process_channels(self.required_channels)

    async def get_active_account(self) -> 'Account':
        """Get the next active account from the queue."""
        logger.debug("Getting active account from queue")
        while not self.account_queue.empty():
            account = await self.account_queue.get()
            logger.debug(f"Checking account {account.name} from queue")
            if account.get_status() != 'banned':
                await self.account_queue.put(account)  # Return to queue
                logger.debug(f"Returning active account: {account.name}")
                return account
            else:
                logger.warning(f"Account {account.name} is banned")
                if self.email_config:
                    from utils.email_utils import send_ban_notification
                    send_ban_notification(self.email_config, account.name)
        if self.email_config:
            from utils.email_utils import send_ban_notification
            send_ban_notification(self.email_config, "All accounts")
        logger.error("All accounts banned!")
        raise RuntimeError("No available accounts")