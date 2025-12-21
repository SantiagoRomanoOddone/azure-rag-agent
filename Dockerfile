FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY multi_agentic_app/ ./multi_agentic_app
COPY multi_agentic_app/.env .env

EXPOSE 80

CMD ["uvicorn", "multi_agentic_app.app:app", "--host", "0.0.0.0", "--port", "80"]


