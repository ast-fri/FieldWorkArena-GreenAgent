from typing import Any
from uuid import uuid4

import httpx
from a2a.client import (
    A2ACardResolver,
    ClientConfig,
    ClientFactory,
    Consumer,
)
from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    DataPart,
    FilePart,
    FileWithBytes,
)

from fieldworkarena.log.fwa_logger import getLogger

logger = getLogger(__name__)


DEFAULT_TIMEOUT = 300


def create_message(*, role: Role = Role.user, text: str, context_id: str | None = None) -> Message:
    """Create a Message object with given text and role."""
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
        context_id=context_id
    )

def create_message_with_file(
        *,
        role: Role = Role.user,
        text: str,
        file_payloads: list[FileWithBytes],
        context_id: str | None = None
) -> Message:
    """Create a Message object with text and multiple file attachments.
    
    Args:
        role: The role of the message sender (default: user).
        text: The text content of the message.
        file_payloads: List of file payloads to attach to the message.
        context_id: Optional context ID for the conversation.
        
    Returns:
        Message object with text and all file attachments.
    """
    # Start with text part
    parts = [Part(TextPart(kind="text", text=text))]
    
    # Add all file parts
    for file_payload in file_payloads:
        parts.append(Part(FilePart(kind="file", file=file_payload)))
    
    return Message(
        kind="message",
        role=role,
        parts=parts,
        message_id=uuid4().hex,
        context_id=context_id
    )

def merge_parts(parts: list[Part]) -> str:
    """message.parts include text answerd by agent"""
    chunks = []
    for part in parts:
        if isinstance(part.root, TextPart):
            chunks.append(part.root.text)
        elif isinstance(part.root, DataPart):
            chunks.append(part.root.data)
        elif isinstance(part.root, FilePart):
            chunks.append(part.root.file)
    return "\n".join(chunks)

async def send_message(
        message: str,
        base_url: str,
        context_id: str | None = None,
        streaming=False,
        consumer: Consumer | None = None
    ) -> dict[str, Any]:
    """Client function to interact with PurpleAgent.
    Args:
        message: The query message to send to the agent.
        base_url: The base URL of the PurpleAgent.
        context_id: Optional context ID for the conversation.
        streaming: Whether to use streaming mode.
        consumer: Callback to process streaming events (ClientEvent or Message) from the agent.
    Notice:
        This Client way using CleintFactory is need for Google Auth,
        We can not find if it is necessary for this development, but we use this way for future compatibility.
    """
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=streaming,
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            if consumer:
                await client.add_event_consumer(consumer)

            outbound_msg = create_message(text=message, context_id=context_id)
            last_event = None
            outputs = {
                "response": "",
                "context_id": None
            }

            async for event in client.send_message(outbound_msg):
                last_event = event

            match last_event:
                case Message() as msg:
                    outputs["context_id"] = msg.context_id
                    outputs["response"] += merge_parts(msg.parts)

                case (task, update):
                    outputs["context_id"] = task.context_id
                    outputs["status"] = task.status.state.value
                    msg = task.status.message
                    if msg:
                        outputs["response"] += merge_parts(msg.parts)
                    if task.artifacts:
                        for artifact in task.artifacts:
                            outputs["response"] += merge_parts(artifact.parts)

                case _:
                    pass

            return outputs
    except Exception as e:
        logger.error(f"Error communicating with agent at {base_url}: {type(e).__name__}: {e}")
        raise RuntimeError(f"Error communicating with agent at {base_url}: {type(e).__name__}: {e}") from e

async def send_message_with_file(
        message: str,
        file_payloads: list[FileWithBytes],
        base_url: str,
        context_id: str | None = None,
        streaming=False,
        consumer: Consumer | None = None
    ) -> dict[str, Any]:
    """Client function to interact with PurpleAgent.
    Args:
        message: The query message to send to the agent.
        file_payloads: The file payloads for A2A FilePart, which includes data encoded in base64.
        base_url: The base URL of the PurpleAgent.
        context_id: Optional context ID for the conversation.
        streaming: Whether to use streaming mode.
        consumer: Callback to process streaming events (ClientEvent or Message) from the agent.
    Notice:
        This Client way using CleintFactory is need for Google Auth,
        We can not find if it is necessary for this development, but we use this way for future compatibility.
    """
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=streaming,
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            if consumer:
                await client.add_event_consumer(consumer)

            outbound_msg = create_message_with_file(text=message, file_payloads=file_payloads, context_id=context_id)
            last_event = None
            outputs = {
                "response": "",
                "context_id": None
            }

            # if streaming == False, only one event is generated
            async for event in client.send_message(outbound_msg):
                last_event = event

            match last_event:
                case Message() as msg:
                    outputs["context_id"] = msg.context_id
                    outputs["response"] += merge_parts(msg.parts)

                case (task, update):
                    outputs["context_id"] = task.context_id
                    outputs["status"] = task.status.state.value
                    msg = task.status.message
                    if msg:
                        outputs["response"] += merge_parts(msg.parts)
                    if task.artifacts:
                        for artifact in task.artifacts:
                            outputs["response"] += merge_parts(artifact.parts)

                case _:
                    pass

            return outputs
    except Exception as e:
        logger.error(f"Error communicating with agent at {base_url}: {type(e).__name__}: {e}")
        raise RuntimeError(f"Error communicating with agent at {base_url}: {type(e).__name__}: {e}") from e

