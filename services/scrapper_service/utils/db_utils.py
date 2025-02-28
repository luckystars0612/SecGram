import sqlite3
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def init_db(db_path: str, accounts_file: str) -> None:
    """Initialize the SQLite database and create tables if they don't exist."""
    try:
        # Check if database exists, create it if not
        if not os.path.exists(db_path):
            logger.info(f"Database {db_path} does not exist. Creating it...")
            Path(db_path).touch()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                phone TEXT PRIMARY KEY,
                api_id TEXT NOT NULL,
                api_hash TEXT NOT NULL,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'banned'))
            )
        """)

        # Create channels table with date_joined
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

        # Load accounts from JSON if not already in DB
        if os.path.exists(accounts_file):
            with open(accounts_file, 'r') as f:
                accounts_data = json.load(f)
            conn = sqlite3.connect(db_path)
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
    except sqlite3.Error as e:
        logger.error(f"SQLite error initializing database: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON error loading accounts: {e}")
        raise
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def add_account(db_path: str, phone: str, api_id: str, api_hash: str) -> None:
    """Add an account to the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO accounts (phone, api_id, api_hash, status) VALUES (?, ?, ?, 'active')",
                      (phone, api_id, api_hash))
        conn.commit()
        cursor.close()
        conn.close()
        logger.debug(f"Added account {phone} to database")
    except sqlite3.Error as e:
        logger.error(f"SQLite error adding account {phone}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error adding account {phone} to database: {e}")
        raise

def get_account_status(db_path: str, phone: str) -> str:
    """Get the status of an account from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM accounts WHERE phone = ?", (phone,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else 'active'
    except sqlite3.Error as e:
        logger.error(f"SQLite error getting status for {phone}: {e}")
        return 'active'
    except Exception as e:
        logger.error(f"Error getting status for {phone}: {e}")
        return 'active'

def update_account_status(db_path: str, phone: str, status: str) -> None:
    """Update the status of an account in the database."""
    if status not in ['active', 'banned']:
        raise ValueError("Status must be 'active' or 'banned'")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET status = ? WHERE phone = ?", (status, phone))
        conn.commit()
        cursor.close()
        conn.close()
        logger.debug(f"Updated status for {phone} to {status}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error updating status for {phone}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error updating status for {phone}: {e}")
        raise

def add_channel(db_path: str, phone: str, channel: str) -> None:
    """Add a channel for an account to the database with date_joined."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        date_joined = datetime.utcnow()
        cursor.execute("INSERT OR REPLACE INTO channels (phone, channel, date_joined) VALUES (?, ?, ?)",
                      (phone, channel, date_joined))
        conn.commit()
        cursor.close()
        conn.close()
        logger.debug(f"Added channel {channel} with date_joined {date_joined} for {phone} to database")
    except sqlite3.Error as e:
        logger.error(f"SQLite error adding channel {channel} for {phone}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error adding channel {channel} for {phone} to database: {e}")
        raise

def get_joined_channels(db_path: str, phone: str) -> List[str]:
    """Get the list of joined channels for an account from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT channel FROM channels WHERE phone = ?", (phone,))
        channels = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return channels
    except sqlite3.Error as e:
        logger.error(f"SQLite error getting joined channels for {phone}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting joined channels for {phone}: {e}")
        return []

def get_new_channels(db_path: str, phone: str, required_channels: List[str]) -> List[str]:
    """Get channels that the account hasn't joined yet, based on the database."""
    try:
        joined = set(get_joined_channels(db_path, phone))
        return [channel for channel in required_channels if channel not in joined]
    except Exception as e:
        logger.error(f"Error getting new channels for {phone}: {e}")
        return required_channels  # Fallback to all channels if error occurs

def check_account_exists(db_path: str, phone: str) -> bool:
    """Check if an account exists in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE phone = ?", (phone,))
        exists = cursor.fetchone()[0] > 0
        cursor.close()
        conn.close()
        return exists
    except sqlite3.Error as e:
        logger.error(f"SQLite error checking existence of account {phone}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking existence of account {phone}: {e}")
        return False