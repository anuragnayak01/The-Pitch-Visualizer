FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Install spaCy explicitly BEFORE requirements.txt
RUN pip install spacy==3.7.6

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create outputs directory
RUN mkdir -p outputs

# Expose port
EXPOSE 8000

# Start the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]