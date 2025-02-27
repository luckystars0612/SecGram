from typing import List, Optional
import json
import random
import os
import sys
from utils import logger
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest 
from telethon.tl.types import Channel
import asyncio
from dbstate import (
    init_db,
    add_account, 
    get_channels, 
    check_account_exists, 
    add_channel, 
    get_account_status,
    update_account_status,
    get_available_accounts
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)


class Account:
    '''
    Represents a Telegram account with session management, authentication details, 
    and tracking of joined channels. 
    '''
    def __init__(self, session_file: str, name: str, api_id: str, api_hash: str, db_path: str):
        '''
        Initializes an Account instance with authentication credentials and session details.
        
        :param session_file: Path to session file name ('e.g., 84123456789.session')
        :param name: Number phone associated with account ('e.g., 84123456789')
        :param api_id: API ID for Telegram authentication
        :param api_hash: API HASH associated with the API ID
        :param db_paht: Path to database file 
        :param client: TelegramClient instance
        '''
        self.session_file = session_file
        self.name = name
        self.api_id = api_id
        self.api_hash = api_hash
        self.db_path = db_path
        self.client = None
                
    async def connect(self) -> bool:
        '''Connect to Telegram using the provided cred.'''
        try: 
            self.client = TelegramClient(
                session=self.session_file,
                api_id=self.api_id,
                api_hash=self.api_hash
            )
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.info(f"Session {self.name} not authorized yet.")
                return False
            logger.info(f'Connected account: {self.name}')
            return True
        except Exception as e: 
            logger.error(f'Failed to connect: {e}')
            return False
            
    async def disconnect(self) -> None:
        '''Disconnect from Tele.'''
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info(f'Disconnected account: {self.name}')
    
    async def initialize(self) -> None:
        """Initialize the account by ensuring it's in the database and fetching joined channels."""     
        if not check_account_exists(self.db_path, self.name):
            add_account(self.db_path, self.name, self.api_id, self.api_hash)
        
        if not get_channels(self.db_path, self.name):
            logger.info(f"No channels found in DB for {self.name}.session. Fetching from Telegram...")        
            if await self.connect():
                channels = await self.get_joined_channels()
                for channel in channels:
                    add_channel(self.db_path, self.name, channel)
                await self.disconnect()

    async def get_joined_channels(self) -> List[str]:
        """Retrieve a list of channels the account has joined from Telegram."""
        joined_channels = []
        try:
            if not self.client or not self.client.is_connected():
                await self.connect()
            async for dialog in self.client.iter_dialogs():
                if isinstance(dialog.entity, Channel):
                    username = getattr(dialog.entity, 'username', None)
                    if username:
                        joined_channels.append(username)
        except Exception as e:
            logger.error(f"Error fetching joined channels for {self.session_file}: {e}")
        return joined_channels
        
    async def join_channel(self, channel: str) -> bool:
        """Join a Telegram channel and update database."""
        try: 
            if not self.client or not self.client.is_connected():
                await self.connect()
                
            await self.client(JoinChannelRequest(channel))
            add_channel(self.db_path, self.name, channel)
            # Random time sleep
            await asyncio.sleep(random.uniform(5, 15))  
            logger.info(f"{self.name} joined {channel}")
            return True
        except errors.FloodWaitError as e:
            logger.error(f"{self.name} hit flood limit: wait {e.seconds} seconds")
            self.update_status('banned')
            return False
        except errors.ChannelInvalidError:
            logger.error(f"{self.name} cannot join {channel}: invalid channel")
            return False
        except Exception as e: 
            logger.error(f"{self.name} failed to join {channel}: {e}")
            return False
    
    def get_status(self) -> str: 
        """Get the current status of the account from the database."""
        return get_account_status(self.db_path, self.name)
    
    def update_status(self, status: str) -> None:
        """Update status of the account from the DB."""
        update_account_status(self.db_path, self.name, status)
        
    async def scrape_messages(self, channel: str, limit: int = 10) -> List[dict]:
        if self.is_banned or not self.client or not self.client.is_connected():
            if not self.client or not self.client.is_connected():
                await self.connect()
            if self.is_banned:
                return []
        try:
            # update code later
            pass
        except errors.FloodWaitError as e:
            logger.error(f"{self.name} hit flood limit: wait {e.seconds} seconds")
            self.is_banned = True  
            return []
        except errors.UserBannedInChannelError:
            logger.error(f"{self.name} is banned in {channel}")
            self.is_banned = True
            return []
        except Exception as e:
            logger.error(f"{self.name} failed to scrape {channel}: {e}")
            return []
        
    def __str__(self):
        '''
        Returns a string representation of the Account instance.
        
        :return: A formated string containing account details
        '''
        return (
           f"{'Session':<{10}}: {self.session_file}\n"
           f"{'API ID':<{10}}: {self.api_id}\n"
           f"{'API HASH':<{10}}: {self.api_hash}\n"
           f"{'Status':<{10}}: {self.get_status()}"
        )
        
        
class AccountManager:
    ''''''
    def __init__(self, session_dir, accounts_file: str, db_path: str):
        self.session_dir = session_dir
        self.db_path = db_path
        self.accounts: List[Account] = self.load_account(accounts_file)
        self.required_channels: List[str] = []
        init_db(self.db_path)
        
    def load_account(self, accounts_file: str) -> List[Account]:
        '''
        Loads account details from the given file (e.g., accounts.json) and returns a list of Account instances.
        
        :param accounts_file: Path to the file containing account details
        :return: A list of Account objects
        '''
        try: 
            with open(accounts_file, 'r') as f: 
                data = json.load(f)
            return [
                Account(
                    session_file=os.path.join(self.session_dir, acc['session']),
                    name=acc["session"].split(".")[0], 
                    api_id=acc['api_id'],
                    api_hash=acc['api_hash'],
                    db_path=self.db_path
                )
                for acc in data['accounts']
            ]
        except FileNotFoundError:
            logger.error(f'Accounts file not found: {accounts_file}')
            return []
        except json.JSONDecodeError:
            logger.error(f'Invalid JSON format in {accounts_file}')
            return []
        except Exception as e: 
            logger.error(f'Error loading accounts: {e}', exc_info=True)
            return []
        
    def get_accounts(self) -> List[Account]:
        '''Return the list of all accounts.'''
        return self.accounts
    
    def set_required_channels(self, channels: List[str]) -> None:
        '''Set the list of target channels to crawl.'''
        self.required_channels = channels
        logger.info(f"Set {len(self.required_channels)} target channels")
        
    async def get_random_account(self) -> Optional[Account]:
        available_accounts = [acc for acc in self.accounts if get_account_status(self.db_path, acc.name)]
        if not available_accounts:
            logger.error('No available accounts')
            return None
        
        random_acc = random.choice(available_accounts)
        await random_acc.initialize()
        joined_channels = get_channels(self.db_path, random_acc.name)
        missing_channels = [ch for ch in self.required_channels if ch not in joined_channels]
        
        if missing_channels:
            for channel in missing_channels: 
                await random_acc.join_channel(channel)
                       
        return random_acc
    
        
async def main():
    session_dir = os.path.join(BASE_DIR, "resources/sessions/")
    accounts_file = os.path.join(BASE_DIR, "resources/accounts.json")

    # account = Account(
    #     session_file='/home/yzx/workspace/ThreatBot/resources/sessions/84896380623.session',
    #     name='84896380623',
    #     api_id='21746700',
    #     api_hash='5b0d128c17ca0df5e8903c0daa190ab7',
    #     db_path='database.db'
    # )
    # await account.initialize()
    
    account_manager = AccountManager(
        session_dir=session_dir,
        accounts_file=accounts_file,
        db_path='database.db'
    )
    required_channels = ['aidlock', 'Allhak_mv']
    account_manager.set_required_channels(required_channels)
    random_acc =await account_manager.get_random_account()
    print(random_acc)
    print(await random_acc.get_joined_channels())
    
    await random_acc.connect()
    await random_acc.client.send_message('me', 'Hello fen!')
    await random_acc.disconnect()
    
if __name__ == '__main__':
    asyncio.run(main())