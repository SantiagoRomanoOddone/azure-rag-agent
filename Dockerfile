# Use a slim Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI app and the .env file
COPY rag-app ./rag-app
COPY rag-app/.env .env

# Expose the port
EXPOSE 8000

# Command to run the FastAPI app
CMD ["uvicorn", "rag-app.app:app", "--host", "0.0.0.0", "--port", "8000"]
