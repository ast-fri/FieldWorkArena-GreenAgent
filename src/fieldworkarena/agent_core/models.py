from typing import Any
from pydantic import BaseModel, HttpUrl

class EvalRequest(BaseModel):
    participants: dict[str, HttpUrl] # role-endpoint mapping
    config: dict[str, Any]

class EvalResult(BaseModel):
    target: str
    total_tasks: int
    total_score: float
    score_rate: float
    task_results: list[dict[str, Any]]
