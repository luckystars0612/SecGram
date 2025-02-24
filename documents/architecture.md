# Microservice Architecture
Each major functionality is separated into its own service, allowing for independent development, deployment, and scaling
- Bot Service: Manages Telegram bot interactions, such as responding to commands and posting updates to the channel.
- Scraper Service: Scrapes data from sources like Telegram channels or dark web links.
- API Service: Integrates with external APIs (e.g., ChatGPT) for advanced processing.
- File Handler Service: Processes large files, such as extracting ZIP archives.
- Database Service (Optional): Stores scraped data if enabled; otherwise, data bypasses storage and goes directly to the bot.
- Search Service (Future-Ready): Handles automatic searching with support for both scheduled tasks and an AI bot.

## Optional Database Integration
- Database is optional, users can decide whether to save data (e.g., queries, scraped content) or skip storage and send it directly to the bot channel. This is achieved with:
    + Configuration Flag: A setting like USE_DATABASE=True/False in a global configuration file. If True, data is stored in the database; if False, it’s processed and sent to the bot channel without persistence.
    + Database Service: When enabled, this service receives data from the Scraper Service, stores it (e.g., in SQLite or PostgreSQL), and forwards it to the Bot Service for posting.
    + Direct Flow: When disabled, the Scraper Service sends data straight to the Bot Service, bypassing storage.

## Automatic Searching with AI Bot Space
- For the automatic searching feature, Search Service that supports both scheduled searches and future AI bot integration:
    + Scheduled Search: Initially, this service runs periodic searches (e.g., daily) based on predefined rules or keywords, updating the Scraper Service with new targets.
    + AI Bot Space: The service uses an abstract interface for search logic, allowing you to plug in an AI bot later (e.g., using machine learning to discover sources intelligently). This ensures flexibility without disrupting the existing architecture.

# Full architecture
```bash
project/
├── services/
│   ├── bot_service/            # Handles Telegram bot interactions
│   │   ├── handlers.py         # Command and message handlers
│   │   ├── commands.py         # Bot-specific commands
│   │   └── main.py             # Bot entry point
│   ├── scraper_service/        # Scrapes data from sources
│   │   ├── base_scraper.py     # Abstract scraper class
│   │   ├── telegram_scraper.py # Scrapes Telegram channels
│   │   ├── darkweb_scraper.py  # Scrapes dark web links
│   │   └── config.py           # Scraper settings
│   ├── api_service/            # Manages external API calls
│   │   ├── chatgpt_api.py      # ChatGPT integration
│   │   └── config.py           # API credentials
│   ├── filehandler_service/    # Processes large files
│   │   ├── zip_extractor.py    # Extracts ZIP files
│   │   └── config.py           # File handling settings
│   ├── db_service/             # Optional database storage
│   │   ├── models.py           # Data models (e.g., SQLAlchemy)
│   │   ├── database.py         # Database connection and logic
│   │   └── config.py           # Database settings
│   ├── search_service/         # Handles automatic searching
│   │   ├── base_search.py      # Abstract search interface
│   │   ├── scheduled_search.py # Scheduled search logic
│   │   └── ai_search.py        # Placeholder for AI bot
│   └── message_broker/         # Facilitates service communication
├── config/                     # Global settings
│   ├── settings.py             # Configuration (e.g., USE_DATABASE)
│   └── logger.py               # Logging setup
├── resources/                  # Static resources
│   ├── telegram_channels.txt   # Initial Telegram channels
│   └── darkweb_links.txt       # Initial dark web links
├── docker-compose.yml          # Containerizes services
└── run.py                      # Orchestrates startup
```