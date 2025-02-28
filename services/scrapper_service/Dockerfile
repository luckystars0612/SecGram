FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source files and utilities
COPY main.py .
COPY account_manager.py .
COPY utils/ utils/

# Create directories for sessions, resources, and database
RUN mkdir -p /app/sessions /app/resources /app

# Set up volume mounts for persistent data (mounted in docker-compose.yml)
VOLUME /app/sessions
VOLUME /app/resources
VOLUME /app/telegram.db

# Use host networking for direct access to host services
CMD ["python", "main.py"]