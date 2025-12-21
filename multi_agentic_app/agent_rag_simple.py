import os
import json
from typing import Callable, Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI

# Import your tool implementations (rag_search etc.)
from functions.agents_functions import rag_search

# -----------------------
# Tool registry
# -----------------------
TOOL_IMPL: Dict[str, Callable[..., Any]] = {
    "rag_search": rag_search,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Run vector RAG over Azure AI Search and return a grounded answer.",
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
]


def run_chat_loop(client: AzureOpenAI, model: str) -> None:
    print("Interactive console. Type 'quit' to exit.\n")

    history: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are a customer support assistant. "
                "Use tools when needed. If you call a tool, wait for its result and then answer."
            ),
        }
    ]

    while True:
        user_prompt = input("User: ").strip()
        if user_prompt.lower() == "quit":
            break
        if not user_prompt:
            continue

        # Add user message
        history.append({"role": "user", "content": user_prompt})

        # 1) Ask model (tool calling allowed)
        resp1 = client.chat.completions.create(
            model=model,
            messages=history,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_msg = resp1.choices[0].message
        tool_calls = getattr(assistant_msg, "tool_calls", None)

        # If no tool call, just print answer
        if not tool_calls:
            answer = assistant_msg.content or ""
            history.append({"role": "assistant", "content": answer})
            print(f"\nAssistant: {answer}\n")
            continue

        # 2) If tool calls exist: record tool-call message then execute tools
        history.append(
            {
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function.name, "arguments": c.function.arguments},
                    }
                    for c in tool_calls
                ],
            }
        )

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

        # 3) Ask model again to produce the final response using tool results
        resp2 = client.chat.completions.create(
            model=model,
            messages=history,
        )
        final_answer = resp2.choices[0].message.content or ""
        history.append({"role": "assistant", "content": final_answer})

        print(f"\nAssistant: {final_answer}\n")


def main() -> None:
    load_dotenv()

    endpoint = os.getenv("OPEN_AI_ENDPOINT")
    api_key = os.getenv("OPEN_AI_KEY")
    model = os.getenv("CHAT_MODEL")

    if not endpoint or not api_key or not model:
        raise RuntimeError("Missing OPEN_AI_ENDPOINT / OPEN_AI_KEY / CHAT_MODEL in environment.")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-12-01-preview",
    )

    run_chat_loop(client, model)


if __name__ == "__main__":
    main()



