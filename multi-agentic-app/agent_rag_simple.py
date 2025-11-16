import os
from dotenv import load_dotenv
from pathlib import Path
import yaml

# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder, MessageRole, FunctionTool, ToolSet
from functions.agents_functions import user_functions


def main():
    # Clear the console
    os.system('cls' if os.name == 'nt' else 'clear')

    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    print("Initializing Customer Support Agent with RAG capabilities...")

    # Connect to the Agent client
    agent_client = AgentsClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True
        )
    )

    with agent_client:
        # Register our RAG function via ToolSet and enable auto function calls
        functions = FunctionTool(user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        agent_client.enable_auto_function_calls(toolset)

        # Load instructions from YAML
        instr_path = Path(__file__).parent / "instructions" / "customer_support_assistant.yml"
        with open(instr_path, "r", encoding="utf-8") as f:
            instr_cfg = yaml.safe_load(f) or {}
        agent_name = instr_cfg.get("name") or "customer-support-agent"
        instructions_text = (
            (instr_cfg.get("messages") or {}).get("system")
            or "You are an automated customer support assistant."
        )

        # Define an agent that can use the toolset
        agent = agent_client.create_agent(
            model=model_deployment,
            name=agent_name,
            instructions=instructions_text,
            toolset=toolset,
            temperature=0.2,
        )
        print(f"Created agent: {agent.name}")

        # Create a thread for the conversation
        thread = agent_client.threads.create()
        print("Started conversation thread")

        # Loop until the user types 'quit'
        while True:
            # Get input text
            user_prompt = input("\nEnter your support question (or type 'quit' to exit): ")
            if user_prompt.lower() == "quit":
                break
            if len(user_prompt) == 0:
                print("Please enter a question.")
                continue

            print("Processing your request...")

            # Send the user's prompt directly; the agent can call rag_search as needed
            agent_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_prompt,
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
                print(f"\nSimplePilot Assistant: {last_msg.text.value}")

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
