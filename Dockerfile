FROM python:3.10-slim-bullseye

# Install system packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        gnupg \
        bash \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/

RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -U -r requirements.txt

CMD bash start
