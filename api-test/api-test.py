
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel
from openai import AzureOpenAI


# FastAPI app
app = FastAPI()

class WhatsAppMessage(BaseModel):
    from_number: str
    text: str



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