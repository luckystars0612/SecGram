# services/scraper_service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (e.g., for torpy or telethon)
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .
# Copy shared config and resources
COPY ../../config/ ./config/
COPY ../../resources/ ./resources/

# Command to run the scraper
CMD ["python", "telegram_scraper.py"]  # Adjust based on your main scraper file