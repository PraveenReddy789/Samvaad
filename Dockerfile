FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir qdrant-client edge-tts pypdf prometheus-client psycopg2-binary

# Copy application source code
COPY . .

# Expose API port
EXPOSE 8000

# Run entrypoint
CMD ["python", "main.py", "--port", "8000"]
