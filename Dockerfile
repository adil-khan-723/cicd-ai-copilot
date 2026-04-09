FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Webhook server default
EXPOSE 8000
CMD ["uvicorn", "webhook.server:app", "--host", "0.0.0.0", "--port", "8000"]
