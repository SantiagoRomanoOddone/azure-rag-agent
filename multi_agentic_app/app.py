import os
import httpx
import yaml
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import MessageRole, FunctionTool, ToolSet

from functions.agents_functions import user_functions


# Load env
load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT_NAME")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
print("DEBUG ENV:", PROJECT_ENDPOINT, MODEL_DEPLOYMENT)
app = FastAPI()

# --- Agent bootstrap (created once) ---
agent_client = AgentsClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True,
    ),
)

toolset = ToolSet()
toolset.add(FunctionTool(user_functions))
agent_client.enable_auto_function_calls(toolset)

instr_path = Path(__file__).parent / "instructions" / "customer_support_assistant.yml"
with open(instr_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

agent = agent_client.create_agent(
    model=MODEL_DEPLOYMENT,
    name=cfg.get("name", "customer-support-agent"),
    instructions=(cfg.get("messages") or {}).get(
        "system", "You are an automated customer support assistant."
    ),
    toolset=toolset,
    temperature=0.2,
)


# --- Webhook verification ---
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse(content="Forbidden", status_code=403)


# --- WhatsApp webhook ---
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()

    try:
        msg_text = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        sender_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return {"status": "ignored"}

    thread = agent_client.threads.create()

    agent_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=msg_text,
    )

    run = agent_client.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id,
    )

    if run.status == "failed":
        reply_text = "Sorry, something went wrong."
    else:
        reply = agent_client.messages.get_last_message_text_by_role(
            thread_id=thread.id,
            role=MessageRole.AGENT,
        )
        reply_text = reply.text.value if reply else "No response."

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

    return {"status": "ok"}
