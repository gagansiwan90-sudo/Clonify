FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy requirements first (cache optimization)
COPY requirements.txt .

# FIXED: Pip upgrade + install (step by step)
RUN pip install --no-cache-dir --upgrade pip==24.2 setuptools==70.1 wheel==0.43.0
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/downloads /app/data && \
    chmod -R 755 /app/downloads /app/data

# Fix permissions
RUN chmod +x main.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

EXPOSE ${PORT}

CMD ["python", "main.py"]
