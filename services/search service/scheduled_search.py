import schedule
import time
from message_broker import update_scraper_targets

def search_new_sources():
    # Simple example: hardcoded new sources
    new_sources = ["https://new_channel.tg", "https://darkweb_link.onion"]
    update_scraper_targets(new_sources)

def main():
    schedule.every().day.at("02:00").do(search_new_sources)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()