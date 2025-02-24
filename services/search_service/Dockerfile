# services/search_service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .
# Copy shared config and resources
COPY ../../config/ ./config/
COPY ../../resources/ ./resources/

# Command to run the search service
CMD ["python", "scheduled_search.py"]  # Adjust for AI bot later