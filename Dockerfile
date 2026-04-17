FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Create directories
RUN mkdir -p /app/downloads /app/data && chmod -R 755 /app

# Expose port
EXPOSE 8000

# FIXED: Simple CMD (no complex shell)
CMD python main.py
