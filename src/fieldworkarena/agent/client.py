import sys
import json
import asyncio
from pathlib import Path
from typing import Any
from pydantic import HttpUrl

import tomllib

from fieldworkarena.agent_core.client_utils import send_message
from fieldworkarena.agent_core.models import EvalRequest
from a2a.types import (
    AgentCard,
    Message,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskState,
    Part,
    TextPart,
    DataPart,
)
from fieldworkarena.log.fwa_logger import getLogger, set_logger

set_logger()
logger = getLogger(__name__)


def parse_toml(cfg: dict[str, Any]) -> tuple[EvalRequest, str]:
    """"""
    green = cfg.get("green_agent")
    if not isinstance(green, dict) or "endpoint" not in green:
        raise ValueError("green.endpoint is required in TOML")

    green_endpoint: str = green["endpoint"]

    # collect participants
    parts: dict[str, HttpUrl] = {}
    for p in cfg.get("participants", []):
        if isinstance(p, dict):
            role = p.get("role")
            endpoint = p.get("endpoint")
            if role and endpoint:
                parts[role] = endpoint

    # create Request for GreenAgent
    eval_req = EvalRequest(
        participants=parts,
        config=cfg.get("config", {}) or {}
    )
    return eval_req, green_endpoint

def print_parts(parts, task_state: str | None = None):
    text_parts = []
    data_parts = []

    for part in parts:
        if isinstance(part.root, TextPart):
            try:
                data_item = json.loads(part.root.text)
                data_parts.append(data_item)
            except Exception:
                text_parts.append(part.root.text.strip())
        elif isinstance(part.root, DataPart):
            data_parts.append(part.root.data)

    output = []
    if task_state:
        output.append(f"[Status: {task_state}]")
    if text_parts:
        output.append("\n".join(text_parts))
    if data_parts:
        output.extend(json.dumps(item, indent=2) for item in data_parts)

    message_to_log = "\n".join(output)
    logger.info(message_to_log)

async def event_consumer(event, card: AgentCard):
    match event:
        case Message() as msg:
            print_parts(msg.parts)

        case (task, TaskStatusUpdateEvent() as status_event):
            status = status_event.status
            parts = status.message.parts if status.message else []
            print_parts(parts, status.state.value)
            if status.state.value == "completed":
                logger.info(task.artifacts)

        case (task, TaskArtifactUpdateEvent() as artifact_event):
            print_parts(artifact_event.artifact.parts, "Artifact update")

        case task, None:
            status = task.status
            parts = status.message.parts if status.message else []
            print_parts(parts, task.status.state.value)

        case _:
            logger.info("Unhandled event")

async def main():
    if len(sys.argv) < 2:
        logger.info("Usage: python client.py <scenario.toml>")
        sys.exit(1)

    scenario_path = Path(sys.argv[1])
    if not scenario_path.exists():
        logger.info(f"File not found: {scenario_path}")
        sys.exit(1)

    toml_data = scenario_path.read_text()
    data = tomllib.loads(toml_data)

    req, green_url = parse_toml(data)

    msg = req.model_dump_json()
    
    # send eval request to GreenAgent
    await send_message(msg, green_url, streaming=True, consumer=event_consumer)


if __name__ == "__main__":
    asyncio.run(main())
