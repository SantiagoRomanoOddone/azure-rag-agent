import os
from dotenv import load_dotenv
from typing import Any, List, Dict
from pathlib import Path

# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder, MessageRole
import httpx
from openai import AzureOpenAI

# ------------------ Vector RAG function (replicates original rag-app logic) ------------------ #
def run_vector_rag(user_query: str, chat_history: List[Dict[str, str]]) -> str:
    """Replicate original rag-app vector RAG using Azure OpenAI + Azure AI Search.

    Args:
        user_query: Current user question.
        chat_history: List of prior messages (dicts with role/content) including system and previous turns.

    Returns:
        Assistant completion string (grounded via vector search) or error string prefixed with [RAG].
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

        # Build prompt (append current user message)
        temp_prompt = list(chat_history) + [{"role": "user", "content": user_query}]

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
            messages=temp_prompt,
            extra_body=rag_params,
        )
        completion = response.choices[0].message.content
        return completion
    except Exception as ex:
        return f"[RAG] Error: {ex}"


def get_rag_enhanced_response(user_query: str) -> str:
    """
    Search Azure AI Search and return concise context only.
    The agent (Foundry model) will generate the final answer.
    """
    try:
        load_dotenv()
        search_url = os.getenv("SEARCH_ENDPOINT")
        search_key = os.getenv("SEARCH_KEY")
        index_name = os.getenv("INDEX_NAME")

        if not (search_url and search_key and index_name):
            return "[RAG] Missing search configuration. Please set SEARCH_ENDPOINT, SEARCH_KEY, INDEX_NAME."

        print(f"  🔍 Searching index '{index_name}' for: {user_query}")

        api_version = "2023-11-01"
        search_endpoint = f"{search_url.rstrip('/')}/indexes/{index_name}/docs/search?api-version={api_version}"

        payload = {
            "search": user_query,
            "top": 5,
            "queryType": "simple",
            "select": "*"
        }
        headers = {
            "Content-Type": "application/json",
            "api-key": search_key,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(search_endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        hits = data.get("value", [])
        if not hits:
            return "[RAG] No relevant documents found in the index."

        context_lines = [
            "[RAG] Retrieved context from Margie's Travel knowledge base:",
        ]
        for i, doc in enumerate(hits, start=1):
            title = doc.get("title") or doc.get("hotel_name") or doc.get("name") or f"Document {i}"
            snippet = doc.get("content") or doc.get("text") or doc.get("description") or ""
            snippet = (snippet or "").strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "…"
            source = doc.get("source") or doc.get("url") or doc.get("path") or ""
            line = f"- {title}: {snippet}"
            if source:
                line += f" (source: {source})"
            context_lines.append(line)

        return "\n".join(context_lines)

    except Exception as ex:
        return f"[RAG] Error querying search index: {str(ex)}"


def main():
    # Clear the console
    os.system('cls' if os.name == 'nt' else 'clear')

    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    print("Initializing Simple Azure AI Agent with RAG capabilities...")

    # Connect to the Agent client
    agent_client = AgentsClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True
        )
    )

    # Maintain separate chat history for vector RAG (system + prior turns)
    rag_chat_history: List[Dict[str, str]] = [
        {"role": "system", "content": "You are a travel assistant that provides information on travel services available from Margie's Travel."}
    ]

    with agent_client:
        # Define a simple agent without function calling
        agent = agent_client.create_agent(
            model=model_deployment,
            name="travel-assistant",
            instructions="""You are a helpful travel assistant for Margie's Travel. 
            
You help customers with information about travel services, destinations, hotels, flights, and related services.
Be friendly, professional, and helpful in all your responses.
If you need to search for specific information, let the user know that you're checking the database.""",
        )
        print(f"Created agent: {agent.name}")

        # Create a thread for the conversation
        thread = agent_client.threads.create()
        print("Started conversation thread")

        # Loop until the user types 'quit'
        while True:
            # Get input text
            user_prompt = input("\nEnter your travel question (or type 'quit' to exit): ")
            if user_prompt.lower() == "quit":
                break
            if len(user_prompt) == 0:
                print("Please enter a question.")
                continue

            print("Processing your request...")

            # Run vector RAG (original logic) to get grounded answer text
            vector_rag_answer = run_vector_rag(user_prompt, rag_chat_history)
            # Also get fallback simple search context (optional)
            simple_context = get_rag_enhanced_response(user_prompt)
            # Update chat history with user + assistant answer from vector RAG for continuity
            rag_chat_history.append({"role": "user", "content": user_prompt})
            rag_chat_history.append({"role": "assistant", "content": vector_rag_answer})
            
            # Create an enhanced prompt that includes the vector answer + raw context lines for transparency
            enhanced_prompt = f"""User question: {user_prompt}

Vector-grounded answer candidate (from Azure OpenAI + vector search):
{vector_rag_answer}

Raw search context (simple keyword search, may be less precise):
{simple_context}

Please refine the vector-grounded answer. If context is insufficient, state limitations and ask for clarification."""

            # Send the enhanced prompt to the agent
            message = agent_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=enhanced_prompt,
            )

            # Create and process the run
            run = agent_client.runs.create_and_process(
                thread_id=thread.id, 
                agent_id=agent.id
            )

            # Check the run status for failures
            if run.status == "failed":
                print(f"Run failed: {run.last_error}")
                continue

            # Show the latest response from the agent
            last_msg = agent_client.messages.get_last_message_text_by_role(
                thread_id=thread.id,
                role=MessageRole.AGENT,
            )
            if last_msg:
                print(f"\n🤖 Travel Assistant: {last_msg.text.value}")

        print("\n--- Conversation Summary ---")
        # Get the full conversation history
        messages = agent_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        for message in messages:
            role_icon = "👤" if message.role == MessageRole.USER else "🤖"
            if message.text_messages:
                last_msg = message.text_messages[-1]
                # Only show the original user questions, not the enhanced prompts
                if message.role == MessageRole.USER:
                    # Extract just the user question from enhanced prompts
                    content = last_msg.text.value
                    if "User question:" in content:
                        user_question = content.split("User question:")[1].split("\n")[0].strip()
                        print(f"{role_icon} {message.role}: {user_question}\n")
                    else:
                        print(f"{role_icon} {message.role}: {content}\n")
                else:
                    print(f"{role_icon} {message.role}: {last_msg.text.value}\n")

        # Clean up
        print("Cleaning up resources...")
        agent_client.delete_agent(agent.id)
        print("Agent deleted successfully")


if __name__ == '__main__':
    main()
