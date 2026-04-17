FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install FFmpeg + dependencies
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy & install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==24.2 && \
    pip install --no-cache-dir -r requirements.txt

# Copy ALL files (including main.py)
COPY . .

# Create directories (✅ SAFE - no file check)
RUN mkdir -p /app/downloads /app/data && \
    chmod -R 755 /app/downloads /app/data /app

# Health check + Expose port
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

EXPOSE ${PORT}

# Run whatever main file exists (flexible)
CMD ["sh", "-c", "if [ -f main.py ]; then python main.py; elif [ -f app.py ]; then python app.py; else python3 -c 'print("No main file found"); exit(1)'; fi"]
