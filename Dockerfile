# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for any Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project structure
COPY config/ ./config/
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create log and state directories
RUN mkdir -p /app/logs /app/state

# Make scripts executable
RUN chmod +x /app/scripts/*.py

# Set environment to use /app as module root
ENV PYTHONPATH=/app

# Add healthcheck
HEALTHCHECK --interval=2m --timeout=10s --start-period=2m --retries=2 \
    CMD python3 /app/scripts/healthcheck.py

# Run scheduler as main process
CMD ["python3", "/app/scripts/scheduler.py"]
