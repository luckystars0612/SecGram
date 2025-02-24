import os
from typing import List
from telethon import TelegramClient
import random
from utils import logger

class Account:
    def __init__(self, session_path: str, name: str):
        self.session_path = session_path
        self.name = name
        self.is_banned = False
        self.joined_all_channels = False

class AccountManager:
    def __init__(self, sessions_dir: str, api_id: str, api_hash: str):
        self.sessions_dir = sessions_dir
        self.api_id = api_id
        self.api_hash = api_hash
        self.accounts: List[Account] = self.load_accounts()

    def load_accounts(self) -> List[Account]:
        try:
            sessions = [f for f in os.listdir(self.sessions_dir) if f.endswith('.session')]
            return [Account(os.path.join(self.sessions_dir, s), s.split('.')[0]) for s in sessions]
        except Exception as e:
            logger.error(f"Error loading accounts: {e}", exc_info=True)
            return []

    def update_accounts(self):
        """Remove accounts whose session files are deleted."""
        current_sessions = {os.path.basename(acc.session_path) for acc in self.accounts}
        new_sessions = {f for f in os.listdir(self.sessions_dir) if f.endswith('.session')}
        
        # Remove deleted sessions
        self.accounts = [acc for acc in self.accounts if os.path.basename(acc.session_path) in new_sessions]
        if len(self.accounts) < len(current_sessions):
            logger.info(f"Removed {len(current_sessions) - len(self.accounts)} deleted session(s)")

    async def get_client(self, account: Account) -> TelegramClient:
        try:
            client = TelegramClient(account.session_path, self.api_id, self.api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError(f"Account {account.name} is not authorized.")
            return client
        except Exception as e:
            logger.error(f"Error creating client for {account.name}: {e}", exc_info=True)
            raise

    def get_random_available_account(self) -> Account:
        available = [acc for acc in self.accounts if not acc.is_banned]
        if not available:
            raise Exception("No available accounts.")
        return random.choice(available)

    def active_count(self) -> int:
        return sum(1 for acc in self.accounts if not acc.is_banned)

    def mark_banned(self, account_name: str):
        for acc in self.accounts:
            if acc.name == account_name:
                acc.is_banned = True
                logger.info(f"Account {account_name} marked as banned.")
                send_email("Account Banned", f"Account {account_name} has been banned.")
                break