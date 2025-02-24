# services/api_service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .
# Copy shared config
COPY ../../config/ ./config/

# Command to run the API service
CMD ["python", "chatgpt_api.py"]