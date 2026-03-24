# Whisper API Service Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with compatible versions
# openai-whisper requires pydantic<2.0, so we use older fastapi
RUN pip install --no-cache-dir \
    "fastapi<0.100.0" \
    "uvicorn<0.25.0" \
    "pydantic<2.0.0" \
    "python-multipart<0.0.6" \
    openai-whisper

# Download Whisper model (medium size for balance of speed and accuracy)
RUN python -c "import whisper; whisper.load_model('medium')"

# Copy application code
COPY main.py /app/main.py

# Expose port
EXPOSE 8003

# Run the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
