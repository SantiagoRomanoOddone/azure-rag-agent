import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel
from openai import AzureOpenAI


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


class WhatsAppMessage(BaseModel):
    from_number: str
    text: str


    
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



@app.post("/test-whatsapp")
async def test_whatsapp(message: WhatsAppMessage):
    print("Message received from WhatsApp:", message.dict())
    return {"status": "ok", "received": message.dict()}

# Endpoint to simulate sending a test message
@app.get("/send-test")
async def send_test():
    test_message = WhatsAppMessage(
        from_number="+15556370138",
        text="Hello, this is a test message"
    )
    print("Simulating sending message:", test_message.dict())
    # Directly call the endpoint
    response = await test_whatsapp(test_message)
    return response