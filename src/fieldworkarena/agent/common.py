from pydantic import BaseModel
from typing import Literal

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)


class FWAEval(BaseModel):
    score: str


def get_fwa_green_agent_card(card_url: str) -> AgentCard:
    skill = AgentSkill(
        id='field_work_arena_benchmark',
        name='Evaluate AI Agents in the Field Work Arena benchmark',
        description='Evaluate AI Agents in the Field Work Arena benchmark',
        tags=['green_agent', 'field_work_arena', 'evaluation', 'image_processing', 'video_processing'],
        examples=[]
    )
    agent_card = AgentCard(
        name="FWA Green Agent",
        description='Evaluate AI Agents in the Field Work Arena benchmark',
        url=card_url,
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    return agent_card
