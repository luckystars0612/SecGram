import smtplib
from email.mime.text import MIMEText
import logging
from typing import Dict

logger = logging.getLogger(__name__)

def send_ban_notification(email_config: Dict, account_name: str) -> None:
    """Send an email notification for banned accounts or all accounts banned."""
    msg = MIMEText(f"Account {account_name} has been banned or all accounts are banned.")
    msg['Subject'] = 'Telegram Account Ban Notification'
    msg['From'] = email_config['sender']
    msg['To'] = email_config['recipient']
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_config['sender'], email_config['password'])
            server.send_message(msg)
        logger.info(f"Email sent for {account_name}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")