import os
import json
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI


def rag_search(query: str, history_json: Optional[str] = None) -> str:
    """
    Tool: rag_search
    - Uses AzureOpenAI and Azure AI Search vector RAG
    - Returns a grounded answer as plain text.
    """
    try:
        load_dotenv()

        open_ai_endpoint = os.getenv("OPEN_AI_ENDPOINT")
        open_ai_key = os.getenv("OPEN_AI_KEY")
        chat_model = os.getenv("CHAT_MODEL")

        embedding_model = os.getenv("EMBEDDING_MODEL")
        search_url = os.getenv("SEARCH_ENDPOINT")
        search_key = os.getenv("SEARCH_KEY")
        index_name = os.getenv("INDEX_NAME")

        missing = [
            name
            for name, val in [
                ("OPEN_AI_ENDPOINT", open_ai_endpoint),
                ("OPEN_AI_KEY", open_ai_key),
                ("CHAT_MODEL", chat_model),
                ("EMBEDDING_MODEL", embedding_model),
                ("SEARCH_ENDPOINT", search_url),
                ("SEARCH_KEY", search_key),
                ("INDEX_NAME", index_name),
            ]
            if not val
        ]
        if missing:
            return f"[RAG] Missing env vars: {', '.join(missing)}"

        history: List[Dict[str, str]] = []
        if history_json:
            try:
                parsed = json.loads(history_json)
                if isinstance(parsed, list):
                    history = [
                        m for m in parsed
                        if isinstance(m, dict) and "role" in m and "content" in m
                    ]
            except Exception:
                pass

        if not any(m.get("role") == "system" for m in history):
            history.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "You are a knowledge base search assistant. "
                        "Your role is to find and return accurate information from the documents. "
                        "Rules: "
                        "1. Only respond with information found in the documents. "
                        "2. If no relevant information is found, respond exactly: 'NO_INFO_FOUND'. "
                        "3. Do not make up or assume any data. "
                        "4. Be concise and direct."
                    ),
                },
            )

        messages = history + [{"role": "user", "content": query}]

        rag_params = {
            "data_sources": [
                {
                    "type": "azure_search",
                    "parameters": {
                        "endpoint": search_url,
                        "index_name": index_name,
                        "authentication": {"type": "api_key", "key": search_key},
                        "query_type": "vector",
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": embedding_model,
                        },
                    },
                }
            ]
        }

        client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=open_ai_endpoint,
            api_key=open_ai_key,
        )

        response = client.chat.completions.create(
            model=chat_model,
            messages=messages,
            extra_body=rag_params,
        )

        return response.choices[0].message.content or ""

    except Exception as ex:
        return f"[RAG] Error: {ex}"


def get_pricing_info() -> str:
    """
    Returns pricing information or link to the store.
    """
    return (
        "Pricing information is available at our online store: "
        "https://example.com/store - "
        "Prices are subject to change without notice."
    )


