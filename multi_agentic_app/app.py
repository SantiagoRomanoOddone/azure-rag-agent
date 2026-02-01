import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from openai import AzureOpenAI


from .functions.agents_functions import rag_search, get_pricing_info


# -----------------------
# ENV + OpenAI client
# -----------------------
load_dotenv()


OPEN_AI_ENDPOINT = os.getenv("OPEN_AI_ENDPOINT")
OPEN_AI_KEY = os.getenv("OPEN_AI_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL")


VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


if not OPEN_AI_ENDPOINT or not OPEN_AI_KEY or not CHAT_MODEL:
    raise RuntimeError("Missing OPEN_AI_ENDPOINT / OPEN_AI_KEY / CHAT_MODEL")


client = AzureOpenAI(
    azure_endpoint=OPEN_AI_ENDPOINT,
    api_key=OPEN_AI_KEY,
    api_version="2024-12-01-preview",
)


app = FastAPI()


# -----------------------
# Tools registry
# -----------------------
TOOL_IMPL = {
    "rag_search": rag_search,
    "get_pricing_info": get_pricing_info,
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the company knowledge base for information. Use this for questions about products, services, policies, contact info, hours, shipping, warranty, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The user's question."},
                    "history_json": {
                        "type": "string",
                        "description": "Optional JSON list of chat history messages [{role, content}].",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pricing_info",
            "description": "Get pricing information or link to the store. Use this when the customer asks about prices, costs, quotes, or how much something costs.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }
]


SYSTEM_PROMPT = (
    "You are a customer support assistant. "
    "Use tools when you need grounded information. "
    "If you call a tool, wait for its result and then answer the user clearly. "
    "If you cannot find the information, escalate to a human agent."
)


# -----------------------
# Meta webhook verify
# -----------------------
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse(content="Forbidden", status_code=403)


# -----------------------
# WhatsApp webhook
# -----------------------
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()


    # Ignore status messages (delivered, read, etc.)
    if body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
        return {"status": "ignored_status"}


    try:
        msg_text = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        sender_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except Exception:
        return {"status": "ignored"}


    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": msg_text},
    ]


    # 1) model call with tools enabled
    resp1 = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=history,
        tools=TOOLS,
        tool_choice="auto",
    )
    assistant_msg = resp1.choices[0].message
    tool_calls = getattr(assistant_msg, "tool_calls", None)


    reply_text = assistant_msg.content or ""


    # 2) if tool calls exist: execute tools and ask model again
    if tool_calls:
        history.append(assistant_msg)


        for call in tool_calls:
            fn_name = call.function.name
            args = json.loads(call.function.arguments or "{}")


            fn = TOOL_IMPL.get(fn_name)
            if not fn:
                tool_result = f"[tool_error] Unknown tool: {fn_name}"
            else:
                try:
                    tool_result = fn(**args)
                except Exception as e:
                    tool_result = f"[tool_error] {fn_name} failed: {e}"


            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(tool_result),
                }
            )


        resp2 = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=history,
        )
        reply_text = resp2.choices[0].message.content or "No response."


    # 3) send to WhatsApp
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "text",
        "text": {"body": reply_text},
    }


    async with httpx.AsyncClient() as http_client:
        resp = await http_client.post(url, headers=headers, json=payload)
        print("WA SEND:", resp.status_code, resp.text)


    return {"status": "ok", "bot_reply": reply_text}


