import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from pydantic import BaseModel
from openai import AzureOpenAI
from fastapi.responses import PlainTextResponse


# Same logic but as a web service to be called from WhatsApp

# Load environment variables
load_dotenv()
open_ai_endpoint = os.getenv("OPEN_AI_ENDPOINT")
open_ai_key = os.getenv("OPEN_AI_KEY")
chat_model = os.getenv("CHAT_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")
search_url = os.getenv("SEARCH_ENDPOINT")
search_key = os.getenv("SEARCH_KEY")
index_name = os.getenv("INDEX_NAME")

# OpenAI client
chat_client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=open_ai_endpoint,
    api_key=open_ai_key
)

# FastAPI app
app = FastAPI()

# Model to receive messages
class Message(BaseModel):
    text: str
    chat_id: str  # optional, useful for maintaining context per user

    
# Endpoint that WhatsApp will call
@app.post("/chat")
async def chat(message: Message):
    prompt = [
        {"role": "system", "content": "You are a travel assistant that provides information on travel services available from Margie's Travel."},
        {"role": "user", "content": message.text}
    ]

    # RAG parameters
    rag_params = {
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    "endpoint": search_url,
                    "index_name": index_name,
                    "authentication": {"type": "api_key", "key": search_key},
                    "query_type": "vector",
                    "embedding_dependency": {"type": "deployment_name", "deployment_name": embedding_model},
                }
            }
        ]
    }

    response = chat_client.chat.completions.create(
        model=chat_model,
        messages=prompt,
        extra_body=rag_params
    )

    completion = response.choices[0].message.content
    return {"chat_id": message.chat_id, "reply": completion}



app = FastAPI()

VERIFY_TOKEN = "s3cret123"

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse(content="Forbidden", status_code=403)


import httpx
import os

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # from Meta

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("Incoming message:", body)

    # Extract the text and sender
    msg_text = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    sender_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

    # Call your /chat endpoint
    async with httpx.AsyncClient() as client:
        chat_resp = await client.post(
            "https://docker-fastapi-sp-bzccc0fbdzhgajgn.eastus2-01.azurewebsites.net/chat",  
            json={"text": msg_text, "chat_id": sender_id}
        )
        chat_data = chat_resp.json()
        reply_text = chat_data["reply"]

    # Send reply back via WhatsApp Cloud API
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "text",
        "text": {"body": reply_text},
    }

    await client.post(url, headers=headers, json=payload)

    return {"status": "ok"}
