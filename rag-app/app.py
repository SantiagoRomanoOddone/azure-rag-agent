import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from openai import AzureOpenAI

# Load env vars
load_dotenv()
open_ai_endpoint = os.getenv("OPEN_AI_ENDPOINT")
open_ai_key = os.getenv("OPEN_AI_KEY")
chat_model = os.getenv("CHAT_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")
search_url = os.getenv("SEARCH_ENDPOINT")
search_key = os.getenv("SEARCH_KEY")
index_name = os.getenv("INDEX_NAME")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# OpenAI client
chat_client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=open_ai_endpoint,
    api_key=open_ai_key
)

app = FastAPI()

# VERIFY WEBHOOK (Meta validation)
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse(content="Forbidden", status_code=403)

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("Incoming:", body)

    try:
        msg_text = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        sender_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return {"status": "ignored"}

    # Build prompt
    prompt = [
        {"role": "system", "content": "You are a travel assistant that provides information on travel services available from Margie's Travel."},
        {"role": "user", "content": msg_text}
    ]

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

    # Call OpenAI
    response = chat_client.chat.completions.create(
        model=chat_model,
        messages=prompt,
        extra_body=rag_params
    )
    reply_text = response.choices[0].message.content
    print("Bot reply:", reply_text)  

    # Send reply via WhatsApp API
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "text",
        "text": {"body": reply_text},
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload)

    # Return the bot reply for testing/inspection
    return {"status": "ok", "bot_reply": reply_text}