# Use a slim Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY multi_agentic_app/ ./multi_agentic_app
COPY multi_agentic_app/.env .env

EXPOSE 80

CMD ["uvicorn", "multi_agentic_app.app:app", "--host", "0.0.0.0", "--port", "80"]
