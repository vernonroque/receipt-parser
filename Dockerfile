FROM python:3.12-slim

# Install system dependencies (poppler for pdf2image)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Start the app
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT