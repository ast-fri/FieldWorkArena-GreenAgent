from a2a.types import FileWithBytes

from fieldworkarena.agent_core.client_utils import send_message_with_file

class PurpleClient:
    """PurpleClient is used to communicate with PurpleAgents."""
    def __init__(self):
        self._context_ids = {}

    async def send_message(
            self,
            message: str,
            file_payloads: list[FileWithBytes],
            url: str,
            new_conversation: bool = False
        ) -> str:
        """
        Communicate with another agent by sending a message and receiving their response.

        Args:
            message: The message to send to the agent
            file_payloads: The file payloads for A2A FilePart, which includes data encoded in base64.
            url: The agent's URL endpoint
            new_conversation: If True, start fresh conversation; if False, continue existing conversation

        Returns:
            str: The agent's response message
        """
        outputs = await send_message_with_file(
            message=message,
            file_payloads=file_payloads,
            base_url=url,
            context_id=None if new_conversation else self._context_ids.get(url, None))
        if outputs.get("status", "completed") != "completed":
            raise RuntimeError(f"{url} responded with: {outputs}")
        self._context_ids[url] = outputs.get("context_id", None)
        return outputs["response"]

    def reset(self):
        self._context_ids = {}