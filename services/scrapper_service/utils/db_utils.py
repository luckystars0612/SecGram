import sqlite3
import json
import os
import logging
from pathlib import Path
from typing import List
import datetime

logger = logging.getLogger(__name__)

def init_db(db_path: str, accounts_file: str) -> sqlite3.Connection:
    """Initialize the SQLite database and create tables if they don't exist, returning a shared connection."""
    try:
        # Check if database exists, create it if not
        if not os.path.exists(db_path):
            logger.info(f"Database {db_path} does not exist. Creating it...")
            Path(db_path).touch()
        
        db_conn = sqlite3.connect(db_path)
        cursor = db_conn.cursor()

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

        db_conn.commit()
        cursor.close()

        # Load accounts from JSON if file exists and not already in DB
        if os.path.exists(accounts_file):
            cursor = db_conn.cursor()
            with open(accounts_file, 'r') as f:
                accounts_data = json.load(f)
            for account in accounts_data['accounts']:
                phone = account['session'].split('.')[0]
                cursor.execute("SELECT COUNT(*) FROM accounts WHERE phone = ?", (phone,))
                if cursor.fetchone()[0] == 0:  # Only insert if not already present
                    cursor.execute("INSERT OR REPLACE INTO accounts (phone, api_id, api_hash, status) VALUES (?, ?, ?, 'active')",
                                  (phone, account['api_id'], account['api_hash']))
            db_conn.commit()
            cursor.close()
            logger.info("Accounts loaded from accounts.json into database")
        else:
            logger.error(f"Accounts file {accounts_file} does not exist")

        return db_conn
    except sqlite3.Error as e:
        logger.error(f"SQLite error initializing database: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON error loading accounts: {e}")
        raise
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_account_status(db_conn: sqlite3.Connection, phone: str) -> str:
    """Get the status of an account from the database using the shared connection."""
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT status FROM accounts WHERE phone = ?", (phone,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else 'active'
    except sqlite3.Error as e:
        logger.error(f"SQLite error getting status for {phone}: {e}")
        return 'active'
    except Exception as e:
        logger.error(f"Error getting status for {phone}: {e}")
        return 'active'

def update_account_status(db_conn: sqlite3.Connection, phone: str, status: str) -> None:
    """Update the status of an account in the database using the shared connection."""
    if status not in ['active', 'banned']:
        raise ValueError("Status must be 'active' or 'banned'")
    try:
        cursor = db_conn.cursor()
        cursor.execute("UPDATE accounts SET status = ? WHERE phone = ?", (status, phone))
        db_conn.commit()
        cursor.close()
        logger.debug(f"Updated status for {phone} to {status}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error updating status for {phone}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error updating status for {phone}: {e}")
        raise

def add_channel(db_conn: sqlite3.Connection, phone: str, channel: str) -> None:
    """Add a channel for an account to the database with date_joined using the shared connection."""
    try:
        cursor = db_conn.cursor()
        date_joined = datetime.datetime.now(datetime.timezone.utc)
        cursor.execute("INSERT OR REPLACE INTO channels (phone, channel, date_joined) VALUES (?, ?, ?)",
                      (phone, channel, date_joined))
        db_conn.commit()
        cursor.close()
        logger.debug(f"Added channel {channel} with date_joined {date_joined} for {phone} to database")
    except sqlite3.Error as e:
        logger.error(f"SQLite error adding channel {channel} for {phone}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error adding channel {channel} for {phone} to database: {e}")
        raise

def get_joined_channels(db_conn: sqlite3.Connection, phone: str) -> List[str]:
    """Get the list of joined channels for an account from the database using the shared connection."""
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT channel FROM channels WHERE phone = ?", (phone,))
        channels = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return channels
    except sqlite3.Error as e:
        logger.error(f"SQLite error getting joined channels for {phone}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting joined channels for {phone}: {e}")
        return []

def get_new_channels(db_conn: sqlite3.Connection, phone: str, required_channels: List[str]) -> List[str]:
    """Get channels that the account hasn't joined yet, based on the database using the shared connection."""
    try:
        joined = set(get_joined_channels(db_conn, phone))
        return [channel for channel in required_channels if channel not in joined]
    except Exception as e:
        logger.error(f"Error getting new channels for {phone}: {e}")
        return required_channels  # Fallback to all channels if error occurs