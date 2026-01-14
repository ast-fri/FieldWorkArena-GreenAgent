import argparse
import uvicorn
import os
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

def get_litellm_model(
        llm_name: str = "openai",
        model_name: str = "gpt-4o")-> LiteLlm:
    """Get LiteLlm model based on the specified llm_name."""
    try:
        API_KEY = os.getenv("OPENAI_API_KEY", "")

        if llm_name == "openai":
            llm = "openai/" + model_name
            return LiteLlm(
                model=llm,
                api_key=API_KEY,
            )
        else:
            raise ValueError(f"Unsupported llm_name: {llm_name}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize LiteLlm: {e}")

def main():
    parser = argparse.ArgumentParser(description="Run the A2A test agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9019, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL to provide in the agent card")
    args = parser.parse_args()

    model = get_litellm_model()

    root_agent = Agent(
        name="fwa_test_purple_agent",
        model=model,
        description="The Agent that understands user's instructions",
        instruction="Your responsibility is to assist the user effectively.",
    )

    skill = AgentSkill(
            id="field_work_ai_agent",
            name="Field Work AI Agent",
            description="Assists with field work tasks such as PPE compliance checking.",
            tags=["field_work"],
            examples=[
                "Please check the PPE compliance status from the site images.",
            ],
        )

    agent_card = AgentCard(
        name=root_agent.name,
        description=root_agent.description,
        url=args.card_url or f'http://{args.host}:{args.port}/',
        version='1.0.0',
        default_input_modes=['text', 'text/plain', 'application/pdf', 'image/jpeg', 'video/mp4'],
        default_output_modes=['text', 'text/plain'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    a2a_app = to_a2a(root_agent, agent_card=agent_card)
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()