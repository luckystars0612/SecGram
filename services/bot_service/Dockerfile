# services/bot_service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed, e.g., for telethon)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .
# Copy shared config and resources
COPY ../../config/ ./config/
COPY ../../resources/ ./resources/

# Command to run the bot
CMD ["python", "main.py"]