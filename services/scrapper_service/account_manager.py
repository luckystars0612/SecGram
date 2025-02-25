from typing import List, Optional, Tuple
import json
import random
import os
import sys
from utils import logger
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest 
from telethon.tl.types import Channel
import asyncio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

class Account: 
    '''
    Represents a Telegram account with session management, authentication details, 
    and tracking of joined channels. 
    '''
    def __init__(self, session_file: str, name: str, api_id: str, api_hash: str):
        '''
        Initializes an Account instance with authentication credentials and session details.
        
        :param session_file: Session file name ('e.g., 84123456789.session')
        :param name: Number phone associated with account ('e.g., 84123456789')
        :param api_id: API ID for Telegram authentication
        :param api_hash: API HASH associated with the API ID
        :param is_banned: Indicates if the acc is banned
        :param is_crawling: Tracks whether the acc is currently performing data crawling
        :param joined_channels: List of channels the account has joined
        '''
        self.session_file = session_file
        self.name = name
        self.api_id = api_id
        self.api_hash = api_hash    
        self.is_banned: bool = False
        self.is_crawling: bool = False
        self.joined_channels: List[str] = []

    def __str__(self) -> str:
        '''
        Returns a string representation of the Account instance..
        
        :return: A formated string containing account details
        '''
        return f"Account(name={self.name}, api_id={self.api_id}, session={self.session_file})"
    
class AccountManager: 
    '''
    Manages multiple Telegram accounts, 
    '''
    def __init__(self, session_dir: str, accounts_file: str, required_channels: List[str]):
        '''
        Initializes the AccountManager with account details and required channels.
        
        :param session_dir: Directory path where session files are stored
        :param accounts_file: Path to the JSON file containing account details such as 'session file', 'name', 'api id', 'api hash'
        :param required_channels: List of Telegram channels that accounts must join.
        '''
        self.session_dir = session_dir
        self.accounts: List[Account] = self.load_account(accounts_file=accounts_file)
        self.required_channels = required_channels
        
    def load_account(self, accounts_file: str) -> List[Account]: 
        '''
        Loads account details from the given file (e.g., accounts.json) and returns a list of Account instances.
        
        :param accounts_file: Path to the file containing account details
        :return: A list of Account objects
        '''
        try: 
            with open (accounts_file, 'r') as f: 
                data = json.load(f)
            return [
               Account(
                    session_file=os.path.join(self.session_dir, acc['session']),
                    name=acc["session"].split(".")[0], 
                    api_id=acc['api_id'],
                    api_hash=acc['api_hash']
                )
                for acc in data['accounts']
            ]
        except FileNotFoundError:
            logger.error(f"Accounts file not found: {accounts_file}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {accounts_file}")
            return []
        except Exception as e:
            logger.error(f"Error loading accounts: {e}", exc_info=True)
            return []

    def get_accounts(self) -> List[Account]:
        return self.accounts
    
    @staticmethod
    async def get_joined_channel(client: TelegramClient) -> List[str]:
        '''
        Retrieves a list of channels that the Telegram account has joined.
        
        :param client: An instance of TelegramClient that is already logged in
        :return: A list of usernames of the channels the account has joined.
        '''
        joined_channels = []
        try: 
            if not client.is_connected():
                await client.connect()
                
            async for dialog in client.iter_dialogs(): 
                if isinstance(dialog.entity, Channel):
                    username: Optional[str] = getattr(dialog.entity, 'username', None)
                    if username: 
                        joined_channels.append(username)
        except Exception as e: 
            logger.error(f"Error checking joined channels: {e}", exc_info=True)
        return joined_channels
        
    async def get_random_client(self) -> Optional[Tuple[TelegramClient, Account]]: 
        '''
        Selects a random account, ensures it joins required channels, and returns its client.
        
        :return: TelegramClient instance or None if failed
        '''
        if not self.accounts: 
            logger.error('No accounts available')
            return None
        
        # Make sure just choice from available accounts
        available_accounts = [acc for acc in self.accounts if not acc.is_crawling]
        if not available_accounts:
            logger.error('No available accounts (all are crawling)')
            return None
        
        random_acc = random.choice(available_accounts)
        logger.info(f"Selected account: {random_acc.name}")
        print (random_acc)
        # Make a TelegramClient instance
        try:
            client = TelegramClient(
                session=random_acc.session_file,
                api_id=random_acc.api_id,
                api_hash=random_acc.api_hash
            )
            await client.start()
            logger.info(f"Client started for {random_acc.name}")
            if not random_acc.joined_channels:
                random_acc.joined_channels = await self.get_joined_channel(client)
            
            missing_channels = [ch for ch in self.required_channels if ch not in random_acc.joined_channels]
            if missing_channels:
                logger.info(f"Account {random_acc.name} is missing channels: {missing_channels}")
                for channel in missing_channels: 
                    success = await self.join_channel(client, channel)
                    if success: 
                        random_acc.joined_channels.append(channel)
                    else:
                        logger.warning(f"Failed to join {channel}. Skipping account.")
                        await client.disconnect()
                        return None
            random_acc.is_crawling = True
            logger.info(f"Set is_crawling = True for {random_acc.name}")
            return client, random_acc
        except Exception as e:
            logger.error(f"Error processing account {random_acc.name}: {e}", exc_info=True)
            await client.disconnect()
            return None

    
    def update_accounts(self):
        pass
    
    @staticmethod
    async def join_channel(client: TelegramClient, channel: str) -> bool: 
        '''
        Join a Telegram channel using the provided client.
        :param client: TelegramClient instance
        :param channel: Channel username of link (e.g., '@baseleak')
        :return: True if successful, False otherwise
        '''
        try: 
            if not client.is_connected(): 
                await client.connect()
            account_name = client.session.filename
            await client(JoinChannelRequest(channel))
            logger.info(f"Successfully joined channel {channel} with {account_name}")
            return True
        except errors.RPCError as e:
            logger.error(f"Failed to join {channel} wiht {account_name}: {e}")
            return False
        
        
async def main() -> None: 
    session_dir = os.path.join(BASE_DIR, "Resources/sessions/")
    accounts_file = os.path.join(BASE_DIR, "Resources/accounts.json")
    print(session_dir)
    
    required_channels = ['Osintcorp_chat', 'peass']
    account_mgr = AccountManager(session_dir, accounts_file, required_channels)
    client, account = await account_mgr.get_random_client()
  
    if client:
        me = await client.get_me()
        logger.info(f"Logged in as: {me.username}")
        await client.disconnect()
    else:
        logger.error("Failed to get a client")
    
if __name__ == '__main__':
    asyncio.run(main())