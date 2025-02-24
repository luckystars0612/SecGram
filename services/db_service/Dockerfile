# services/db_service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (e.g., for SQLite)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .
# Copy shared config
COPY ../../config/ ./config/

# Command to run the database service
CMD ["python", "database.py"]