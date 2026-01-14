import argparse
import asyncio
import contextlib
import sys
from typing import Any

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    FileWithBytes,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(override=True)

import fieldworkarena.agent.metrics.automatic.automatic_evaluation as auto_eval
from fieldworkarena.agent.common import FWAEval, get_fwa_green_agent_card
from fieldworkarena.agent.metrics.tasks import (
    BenchmarkDataSource,
    TaskLoader,
    build_goal,
)
from fieldworkarena.agent_core.green_executor import GreenAgent, GreenExecutor
from fieldworkarena.agent_core.models import EvalRequest, EvalResult
from fieldworkarena.agent_core.purple_client import PurpleClient
from fieldworkarena.log.fwa_logger import getLogger, set_logger


set_logger()
logger = getLogger(__name__)

class FWAGreenAgent(GreenAgent):
    def __init__(self):
        self._required_roles = ["agent"]
        self._required_config_keys = ["target", "token"]
        self._client = PurpleClient()
        self._data_source = None

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        """Validate the EvalRequest."""
        logger.info(f"Validating request: {request.participants}")
        
        # Validate the roles
        missing_roles = set(self._required_roles) - set(request.participants.keys())
        if missing_roles:
            return False, f"Missing roles: {missing_roles}"
        
        # validate the config keys
        missing_config_keys = set(self._required_config_keys) - set(request.config.keys())
        if missing_config_keys:
            return False, f"Missing config keys: {missing_config_keys}"
        
        # validate the access token
        try:
            self._data_source = BenchmarkDataSource(
                access_token=request.config['token']
            )
            self._data_source.validate_access()
            logger.info("Access token validated successfully.")
        except Exception as e:
            return False, f"Access token validation failed: {e}"
        
        return True, "ok"

    async def run_eval(self, req: EvalRequest, updater: TaskUpdater) -> None:
        """Run the FWA evaluation
        
        This method gives PurpleAgents(participants) the task_query of FWA
        
        Args:
            req (EvalRequest): The evaluation request containing participants and config.
            updater (TaskUpdater): The task updater to report progress and results.
        
        """
        # Ensure data source is initialized
        if self._data_source is None:
            raise ServerError(error=InvalidParamsError(message="Invalid Access Token. Data source is not initialized."))

        try:
            # Load task from json
            tasks = TaskLoader()
            tasks = tasks.extract_tasks(req.config['target'])
            logger.info(f"Loaded tasks: {tasks}")

            task_results = []
            total_score = 0.0

            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"=== Starting evaluation of {len(tasks)} tasks. ===")
            )

            for task in tasks:
                try:
                    logger.info("===============================================")
                    logger.info(f"Processing task ID: {task['id']}")
                    logger.info("===============================================")
                    goal = build_goal(task)
                    file_payloads = self._data_source.load_file_payload(task['input_data'])

                    # orchestrate purple agents to perform the task
                    result = await self.orchestrate(
                        req.participants,
                        goal,
                        file_payloads,
                        updater)
                    
                    # TODO: need to check if the format of result is correct by using task['output_format']

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(f"=== Orchestration finished. Analyzing result... ===")
                    )
                    logger.info("Orchestration finished. Evaluating results.")
                    
                    # Evaluate the results using the eval method of FWA
                    analyze_eval: FWAEval = await self.judge(
                        task['query'],
                        task["answer"],
                        result['agent'][-1],
                        task['eval_func'])
                    logger.info(f"★★★Evaluation★★★:{analyze_eval.model_dump_json()}")

                    # Save the evaluation result
                    task_result = {
                        "task_id": task['id'],
                        "score": float(analyze_eval.score),
                        "eval_func": task['eval_func']
                    }
                    task_results.append(task_result)
                    total_score += float(analyze_eval.score)

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(f"=== Task {task['id']} completed. Score: {analyze_eval.score} ===")
                    )
                except Exception as e:
                    logger.error(f"Error during task execution: {e}")
                    # Record tasks with errors as having a score of 0
                    task_results.append({
                        "task_id": task.get('id', 'unknown'),
                        "score": 0.0,
                        "error": str(e)
                    })
                finally:
                    # reset client to initiate conversation with PurpleAgents
                    self._client.reset()
            
            # After all tasks are completed, add the aggregated results as an artifact
            score_rate = total_score / len(tasks) if len(tasks) > 0 else 0.0
            eval_result = EvalResult(
                total_tasks=len(tasks),
                total_score=total_score,
                score_rate=score_rate,
                task_results=task_results
            )
            await updater.add_artifact(
                parts=[
                    Part(root=TextPart(text=eval_result.model_dump_json())),
                ],
                name="EvaluationResult",
            )
            logger.info(f"★★★Final Evaluation Summary★★★: Total Tasks: {len(tasks)}, Total Score: {total_score}, Score Rate: {score_rate:.2%}")
        except Exception as e:
            logger.error(f"Error in run_eval: {e}")

    async def orchestrate(
        self,
        participants: dict[str,Any],
        goal: str,
        file_payloads: list[FileWithBytes],
        updater: TaskUpdater,
    ) -> dict[str, list[str]]:
        """Orchestrate the PurpleAgents(participants) to perform the FWA task.
        Args:
            participants: Dictionary mapping role names to their endpoints.
            goal: The task goal to be processed.
            file_payloads: The file payloads for A2A FilePart, which includes data encoded in base64.
            updater: The task updater to report progress.
        Returns:
            A dictionary containing the analysis results from each participant."""
        analyze: dict[str, list[str]] = {"agent": []}

        async def turn(role: str, query: str) -> str:
            """Manage a conversation with PurpleAgents"""
            logger.info(f"Turn for role {role} with query:\n{query}")
            response = await self._client.send_message(
                query,
                file_payloads,
                str(participants[role]),
                new_conversation=False
            )
            logger.info(f"{role}: {response}")
            analyze[role].append(response)
            await updater.update_status(TaskState.working, new_agent_text_message(f"=== {role}: {response} ===" ))
            return response

        # send query to PurpleAgents
        response = await turn("agent", f"{goal}")

        return analyze

    async def judge(
            self,
            query: str,
            reference:str,
            predicted: str,
            eval_func: str
    ) -> FWAEval:
        """Judge the analysis result from PurpleAgents.
        Args:
            query: The original task query.
            reference: The reference answer for evaluation.
            predicted: The analysis result from PurpleAgents.
            eval_func: The evaluation function to use.
        Returns:
            FWAEval: The evaluation result including score and reason.
        """
        logger.info(f"Judging result...\nQuery: {query}\nReference: {reference}\nPredicted: {predicted}")

        score = 0.0
        reason = None

        match eval_func:
            case "fuzzy_match":
                score, reason = auto_eval.llm_fuzzy_match(predicted, reference, query)
                logger.info(" ==> fuzzy_match, score: {}".format(score))
            case "exact_match":
                score, reason = auto_eval.exact_match(reference, predicted)
                logger.info(" ==> exact_match, score: {}".format(score))
            case "must_include":
                score, reason = auto_eval.must_include(reference, predicted)
                logger.info(" ==> must_include, score: {}".format(score))
            case "must_exclude":
                score, reason = auto_eval.must_exclude(reference, predicted)
                logger.info(" ==> must_exclude, score: {}".format(score))
            case "json_match":
                score = auto_eval.json_match(predicted, reference, query)
                logger.info(" ==> json_match, score: {}".format(score))
            case "numerical_match":
                score = auto_eval.numerical_match(predicted, reference, query)
                logger.info(" ==> numerical_match, score: {}".format(score))

        #return score as a EWAEval
        return FWAEval(
            score=str(score),
        )


async def async_main():
    """Main async function to run the FWA Green Agent server."""

    # --- Parse command-line arguments ---
    parser = argparse.ArgumentParser(description="Run the A2A server for FWA benchmark.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9009, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL to provide in the agent card")
    args = parser.parse_args()


    agent_url_cm = contextlib.nullcontext(args.card_url or f"http://{args.host}:{args.port}/")
    # --- end ---

    async with agent_url_cm as agent_url:
        try:
            agent = FWAGreenAgent()
            executor = GreenExecutor(agent)
            agent_card = get_fwa_green_agent_card(agent_url)

            request_handler = DefaultRequestHandler(
                agent_executor=executor,
                task_store=InMemoryTaskStore(),
            )

            server = A2AStarletteApplication(
                agent_card=agent_card,
                http_handler=request_handler,
            )

            uvicorn_config = uvicorn.Config(server.build(), host=args.host, port=args.port)
            uvicorn_server = uvicorn.Server(uvicorn_config)
            await uvicorn_server.serve()
        except KeyboardInterrupt:
            logger.info("Shutting down FWA Green Agent server.")
        except Exception as e:
            logger.error(f"Error running FWA Green Agent server: {e}")
            sys.exit(1)


def main():
    """Entry point for fwa-server command."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
        sys.exit(0)


if __name__ == '__main__':
    main()
