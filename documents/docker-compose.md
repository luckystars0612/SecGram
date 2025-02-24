# Services
- Each microservice is defined as a separate container:
+ **rabbitmq**: The message broker using RabbitMQ with the management plugin enabled. It exposes port 5672 for AMQP communication and 15672 for the management UI.
+ **bot_service**: Runs the Telegram bot, listening for commands and posting updates to the channel.
+ **scraper_service**: Scrapes data from Telegram channels and dark web links.
+ **api_service**: Integrates with external APIs like ChatGPT.
+ **filehandler_service**: Processes large files (e.g., ZIP extraction).
+ **db_service**: Stores data if USE_DATABASE is true; otherwise, it acts as a pass-through.
+ **search_service**: Handles automatic searching (scheduled or future AI-driven).

# Network Communication
- **Shared Network**: All services are connected to a custom bridge network (***app-network***), allowing them to communicate with each other using container names (e.g., ***rabbitmq*** as the hostname).
- **Message Broker**: ***RabbitMQ*** facilitates decoupled communication. Services publish and subscribe to queues (e.g., scraper sends data to ***scraped_data*** queue, bot listens to it).

# 3. Environment Variables
- **Sensitive data** (e.g., TELEGRAM_TOKEN, CHATGPT_API_KEY) is loaded from a **.env** file or set at runtime.
- ***USE_DATABASE*** defaults to false, making the database optional. If true, ***db_service*** stores data; if false, data bypasses it.

# Dependencies
- Each service depends on **rabbitmq** being healthy (checked via healthcheck), ensuring communication is ready before services start.

# Volumes
- **Configuration** (./config) and **resources** (./resources) are mounted into relevant services for runtime access.
- For **db_service**, a persistent volume (**db_data**) stores the SQLite database if used.

# Build Context
- Each service uses a **Dockerfile** in its respective directory (e.g., ***services/bot_service/Dockerfile***) to define how it’s built.

# Communication Flow
- **Scraper Service**: Scrapes data and publishes it to a RabbitMQ queue (e.g., ***scraped_data***).
- **Database Service**: If ***USE_DATABASE*** is true, subscribes to ***scraped_data***, stores it, and republishes to ***bot_data***. If false, it’s bypassed.
- **Bot Service**: Subscribes to ***bot_data*** (or directly to ***scraped_data*** if no DB) and posts to the Telegram channel.
- **Search Service**: Publishes new sources to a ***new_sources*** queue, which ***scraper_service*** subscribes to for updates.
- **API Service & File Handler Service**: Operate on demand, publishing processed data to relevant queues.

* Notes
RabbitMQ Setup: The management UI is accessible at **http://localhost:15672** (default credentials: guest/guest) for monitoring queues.
Scalability: Increase replicas with docker-compose.yml (e.g., deploy: replicas: 2) for load balancing.
Customization: Adjust ports, volumes, or environment variables as needed.