from abc import abstractmethod
from typing import Literal
from pydantic import ValidationError

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Part,
    InvalidParamsError,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
    InternalError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from fieldworkarena.agent_core.models import EvalRequest, EvalResult

from fieldworkarena.log.fwa_logger import getLogger
logger = getLogger(__name__)


class GreenAgent():

    @abstractmethod
    async def run_eval(self, request: EvalRequest, updater: TaskUpdater) -> None:
        pass

    @abstractmethod
    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        pass


class GreenExecutor(AgentExecutor):

    def __init__(self, green_agent: GreenAgent):
        self.agent = green_agent
        
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # task query
        task_query = context.get_user_input()
        
        # create EvalRequest from task query
        try:
            req: EvalRequest = EvalRequest.model_validate_json(task_query)
            ok, msg = self.agent.validate_request(req)
            if not ok:
                raise ServerError(error=InvalidParamsError(message=msg))
        except ValidationError as e:
            raise ServerError(error=InvalidParamsError(message=e.json()))

        # Create or get existing task
        if context.current_task:
            task = context.current_task
        elif context.message:
            task = new_task(context.message)
        else:
            raise ServerError(error=InvalidParamsError(message="No message provided"))
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"Starting assessment.\n{req.model_dump_json()}", context_id=task.context_id, task_id=task.id),
        )

        try:
            await self.agent.run_eval(req, updater)
            await updater.add_artifact(
                [Part(root=TextPart(text=f"{task.id} :Assessment completed successfully."))]
            )
            await updater.complete()
        except Exception as e:
            logger.error(f"Agent error: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(f"Agent error: {e}", task.context_id, task.id),
                final=True,
            )
            raise ServerError(error=InternalError(message=str(e)))

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
