import argparse
import uvicorn
import sys

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Add purple_agent directory to Python path
purple_agent_root = Path(__file__).parent
sys.path.insert(0, str(purple_agent_root))

from google.adk.agents import Agent

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from purple_executor import PurpleExecutor
from utils.helpers import get_litellm_model, load_yaml_config

from fieldworkarena.log.fwa_logger import set_logger, getLogger
set_logger()
logger = getLogger(__name__)



def main():
    parser = argparse.ArgumentParser(description="Run the A2A test agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9019, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL to provide in the agent card")
    args = parser.parse_args()

    # Load agent configuration and model
    agent_config = load_yaml_config("test_purple")
    model = get_litellm_model()

    root_agent = Agent(
        name=agent_config["name"],
        model=model,
        description=agent_config["description"],
        instruction=agent_config["instructions"],
        tools=[],  # Add other tools as needed
    )

    skill = AgentSkill(
            id="field_work_ai_agent",
            name=root_agent.name,
            description=root_agent.description,
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
    request_handler = DefaultRequestHandler(
        agent_executor=PurpleExecutor(
            agent=root_agent
        ),
        task_store=InMemoryTaskStore()
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )

    logger.info("[Agent] Starting Test Purple Agent A2A server")
    uvicorn.run(server.build(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()