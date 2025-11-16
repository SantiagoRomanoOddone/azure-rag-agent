import os
import json
from typing import List, Dict, Any, Optional, Set, Callable
from dotenv import load_dotenv
from openai import AzureOpenAI

"""
Function tool: rag_search
- Purpose: replicate rag-app vector RAG using Azure OpenAI + Azure AI Search
- Inputs:
  - query: str (user question)
  - history_json: Optional[str] JSON-serialized list of {role, content} for context
- Output:
  - str: grounded assistant answer text
Notes:
- Mirrors rag-app: same rag_params with data_sources -> azure_search + query_type=vector + embedding_dependency deployment_name.
- Keeps output plain text to fit common tool call patterns.
"""

def rag_search(query: str, history_json: Optional[str] = None) -> str:
    try:
        load_dotenv()
        open_ai_endpoint = os.getenv("OPEN_AI_ENDPOINT")
        open_ai_key = os.getenv("OPEN_AI_KEY")
        chat_model = os.getenv("CHAT_MODEL")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        search_url = os.getenv("SEARCH_ENDPOINT")
        search_key = os.getenv("SEARCH_KEY")
        index_name = os.getenv("INDEX_NAME")

        missing = [name for name, val in [
            ("OPEN_AI_ENDPOINT", open_ai_endpoint),
            ("OPEN_AI_KEY", open_ai_key),
            ("CHAT_MODEL", chat_model),
            ("EMBEDDING_MODEL", embedding_model),
            ("SEARCH_ENDPOINT", search_url),
            ("SEARCH_KEY", search_key),
            ("INDEX_NAME", index_name),
        ] if not val]
        if missing:
            return f"[RAG] Missing env vars: {', '.join(missing)}"

        # Build prompt history from JSON if provided
        history: List[Dict[str, str]] = []
        if history_json:
            try:
                parsed = json.loads(history_json)
                if isinstance(parsed, list):
                    history = [m for m in parsed if isinstance(m, dict) and 'role' in m and 'content' in m]
            except Exception:
                pass

        # Ensure we have a system prompt similar to rag-app
        if not any(m.get('role') == 'system' for m in history):
            history.insert(0, {"role": "system", "content": "You are a travel assistant that provides information on travel services available from Margie's Travel."})

        # Append current user query
        messages = history + [{"role": "user", "content": query}]

        rag_params = {
            "data_sources": [
                {
                    "type": "azure_search",
                    "parameters": {
                        "endpoint": search_url,
                        "index_name": index_name,
                        "authentication": {
                            "type": "api_key",
                            "key": search_key,
                        },
                        "query_type": "vector",
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": embedding_model,
                        },
                    }
                }
            ],
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
        completion = response.choices[0].message.content
        return completion
    except Exception as ex:
        return f"[RAG] Error: {ex}"

# Export as a set of callable functions for Agents ToolSet pattern
user_functions: Set[Callable[..., Any]] = {
    rag_search,
}
