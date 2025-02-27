import sqlite3
import time
from typing import List

def init_db(db_path: str):
    '''Initialize the database with the necessary tables.'''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # accounts table
    # account name e.g 84896380623
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_name TEXT PRIMARY KEY, 
            api_id INTEGER,
            api_hash TEXT,
            status TEXT CHECK(status IN ('available', 'crawling', 'banned')) DEFAULT 'available'
        )
    """)
    
    # account_channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_channels (
            account_name TEXT,
            channel_id TEXT,
            joined_at INTEGER,
            last_crawled INTEGER DEFAULT 0,
            PRIMARY KEY (account_name, channel_id),
            FOREIGN KEY (account_name) REFERENCES accounts(account_name)
        )
    """)
    
    # crawl_locks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_locks (
            channel_id TEXT PRIMARY KEY,
            locked_by_session TEXT,
            locked_at INTEGER,
            FOREIGN KEY (locked_by_session) REFERENCES accounts(account_name)
        )
    """)
    
    conn.commit()
    conn.close()

def add_account(db_path: str, account_name: str, api_id: str, api_hash: str):
    '''
    '''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO accounts (account_name, api_id, api_hash, status)
        VALUES (?, ?, ?, 'available')
    """, (account_name, api_id, api_hash))
    conn.commit()
    conn.close()
    
def check_account_exists(db_path: str, account_name):
    """Check if the account exists in the SQLite table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = f"SELECT 1 FROM accounts WHERE account_name = ? LIMIT 1"
        cursor.execute(query, (account_name,))
        result = cursor.fetchone()

        conn.close()
        return result is not None  
    
    except sqlite3.Error as e:
        return False

def get_available_accounts(db_path: str) -> List:
    ''''''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT account_name FROM accounts WHERE status = 'available'")
    accounts = [row[0] for row in cursor.fetchall()]
    conn.close()
    return accounts

def get_account_status(db_path: str, account_name: str) -> str:
    '''Get the current status of the account from the db'''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM accounts WHERE account_name = ?", (account_name,))
    status = cursor.fetchone()
    conn.close()
    return status[0] if status else 'available'
    
def update_account_status(db_path: str, account_name: str, status: str):
    """Update the status of an account (available, crawling, banned)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET status = ? WHERE account_name = ?", (status, account_name))
    conn.commit()
    conn.close()

def remove_account(db_path: str, account_name: str):
    """Delete an account from the accounts table and related tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE account_name = ?", (account_name,))
    cursor.execute("DELETE FROM account_channels WHERE account_name = ?", (account_name,))
    cursor.execute("DELETE FROM crawl_locks WHERE locked_by_session = ?", (account_name,))
    conn.commit()
    conn.close()

def add_channel(db_path: str, account_name: str, channel_id: str):
    """Add a channel that the account has joined to the account_channels table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO account_channels (account_name, channel_id, joined_at, last_crawled)
        VALUES (?, ?, ?, 0)
    """, (account_name, channel_id, int(time.time())))
    conn.commit()
    conn.close()

def remove_channel(db_path: str, account_name: str, channel_id: str):
    '''Delete a channel from the account_channels table for specific account.'''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM account_channels 
        WHERE account_name = ? AND channel_id = ?
    """, (account_name, channel_id))
    conn.commit()
    conn.close()
    
def get_channels(db_path: str, account_name: str) -> list:
    """Get a list of channels an account has joined."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM account_channels WHERE account_name = ?", (account_name,))
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    return channels

def update_channel_crawl(db_path: str, account_name: str, channel_id: str, last_crawled: int):
    """Updates the last crawl time of a channel"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE account_channels SET last_crawled = ? 
        WHERE account_name = ? AND channel_id = ?
    """, (last_crawled, account_name, channel_id))
    conn.commit()
    conn.close()

def has_been_crawled_recently(db_path: str, channel_id: str, threshold: int = 3600) -> bool:
    """Check if the channel has been crawled recently (within threshold seconds)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(last_crawled) FROM account_channels WHERE channel_id = ?
    """, (channel_id,))
    last_crawled = cursor.fetchone()[0] or 0
    conn.close()
    return (int(time.time()) - last_crawled) < threshold

def reset_all_crawled(db_path: str):
    """Reset all last_crawled to 0 to start a new crawl iteration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE account_channels SET last_crawled = 0")
    conn.commit()
    conn.close()

def is_channel_locked(db_path: str, channel_id: str, timeout: int = 300) -> bool:
    """Check if a channel is locked, also check timeout."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT locked_at FROM crawl_locks WHERE channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    if result and (int(time.time()) - result[0]) > timeout:
        cursor.execute("DELETE FROM crawl_locks WHERE channel_id = ?", (channel_id,))
        conn.commit()
        conn.close()
        return False
    conn.close()
    return result is not None

def lock_channel(db_path: str, channel_id: str, account_name: str) -> bool:
    """Lock a channel if the account has joined that channel. Returns True if the lock is successful."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the account has joined the channel
    cursor.execute("""
        SELECT channel_id FROM account_channels 
        WHERE account_name = ? AND channel_id = ?
    """, (account_name, channel_id))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False  
    
    # If joined, proceed to lock
    cursor.execute("""
        INSERT OR REPLACE INTO crawl_locks (channel_id, locked_by_session, locked_at)
        VALUES (?, ?, ?)
    """, (channel_id, account_name, int(time.time())))
    conn.commit()
    conn.close()
    return True
    
def unlock_channel(db_path: str, channel_id: str):
    """Release the lock of a channel after crawling is complete."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM crawl_locks WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_locked_channels(db_path: str) -> list:
    """Get a list of locked channels."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM crawl_locks")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    return channels

def main():
    init_db('database.db')
    add_account('database.db', '84896380623', '21746700', '5b0d128c17ca0df5e8903c0daa190ab7')
    add_account('database.db', '84928200282', '22441216', 'a032e0e87aa70a3acb983e4b87443cbd')
    add_account('database.db', '84928201234', '22441111', 'a032e0e87aa70a3acb983e4b8744bcde')
    
    '''
    84896380623|21746700|5b0d128c17ca0df5e8903c0daa190ab7|available
    84928200282|22441216|a032e0e87aa70a3acb983e4b87443cbd|available
    84928201234|22441111|a032e0e87aa70a3acb983e4b8744bcde|available
    '''
    available_accounts = get_available_accounts('database.db')
    print(available_accounts) # ['84896380623', '84928200282', '84928201234']
    
    update_account_status('database.db', '84896380623', 'crawling')
    '''
    84896380623|21746700|5b0d128c17ca0df5e8903c0daa190ab7|crawling
    84928200282|22441216|a032e0e87aa70a3acb983e4b87443cbd|available
    84928201234|22441111|a032e0e87aa70a3acb983e4b8744bcde|available
    '''
    remove_account('database.db', '84928201234')
    # add_account('database.db', '84928201234.session', '22441111', 'a032e0e87aa70a3acb983e4b8744bcde')
    
    # Handle channel
    add_channel('database.db', '84928201234', 'baseleak')
    add_channel('database.db', '84928201234', 'altenens')
    '''
    84928201234|baseleak|1740585791|0
    84928201234|altenens|1740585791|0   
    '''
    channels = get_channels('database.db', '84928201234')
    print(channels)
    
    # remove_channel('database.db', '84928201234.session', 'altenens')
    
    last_crawled = time.time()
    update_channel_crawl('database.db', '84928201234', 'baseleak', last_crawled)
    print (has_been_crawled_recently('database.db', 'baseleak'))
    # reset_all_crawled('database.db')
    
    # print(lock_channel('database.db', 'baseleak', '84928201234')) # True because this session has joined channel
    # print(lock_channel('database.db', 'baseleak', '84928200282')) # False
    
    # print(get_account_status('database.db', '84896380623.session'))
if __name__ == '__main__':
    main()