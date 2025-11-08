# Discord Bot Dockerfile with Tesseract OCR
FROM python:3.11-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Optionally set Tesseract path for Linux
ENV TESSERACT_CMD=/usr/bin/tesseract

# Default command to run your bot
CMD ["python", "main.py"]
