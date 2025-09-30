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



# verify_token = os.getenv("VERIFY_TOKEN")

# # Webhook verification 
# @app.get("/webhook")
# async def verify_webhook(request: Request):
#     mode = request.query_params.get("hub.mode")
#     token = request.query_params.get("hub.verify_token")
#     challenge = request.query_params.get("hub.challenge")

#     if mode == "subscribe" and token == verify_token:
#         return PlainTextResponse(content=challenge)  # return exactly what Meta sends
#     return PlainTextResponse(content="Verification failed", status_code=403)
# @app.get("/webhook")
# async def verify_webhook(request: Request):
#     mode = request.query_params.get("hub.mode")
#     token = request.query_params.get("hub.verify_token")
#     challenge = request.query_params.get("hub.challenge")

#     content = f"mode: {mode}\ntoken: {token}\nchallenge: {challenge}"
#     return PlainTextResponse(content=content)

# from fastapi import FastAPI, Request
# from fastapi.responses import PlainTextResponse

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


# POST WhatsApp sends the messages here
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("Incoming message:", body)
    # later call your /chat logic here
    return {"status": "received"}
