FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Install ALL dependencies explicitly (don't rely solely on requirements.txt)
RUN pip install \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.6" \
    httpx==0.27.2 \
    python-dotenv==1.0.1 \
    jinja2==3.1.4 \
    python-multipart==0.0.9 \
    aiofiles==24.1.0 \
    spacy==3.7.6

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Verify uvicorn is installed
RUN uvicorn --version

# Copy application code
COPY . .

# Remove any stale bytecode that could shadow updated source files
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find /app -name "*.pyc" -delete 2>/dev/null || true

# Create outputs directory
RUN mkdir -p outputs

# Expose port
EXPOSE 8000

# Start the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]