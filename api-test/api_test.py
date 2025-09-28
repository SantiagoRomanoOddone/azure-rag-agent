
import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel
from openai import AzureOpenAI


# FastAPI app
app = FastAPI()


load_dotenv("../rag-app/.env")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

class WhatsAppMessage(BaseModel):
    from_number: str
    text: str


@app.post("/send-message")
async def send_message(to_number: str, text: str):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": text}
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
    return resp.json()