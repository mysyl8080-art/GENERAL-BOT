FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_PATH=/data/bot.sqlite3 \
    TEMP_DIR=/tmp/telegram-superbot

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice libreoffice-writer libreoffice-calc libreoffice-impress \
    ffmpeg tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    poppler-utils p7zip-full unrar-free fonts-liberation \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .
RUN mkdir -p /data /tmp/telegram-superbot
CMD ["python", "main.py"]
