from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class QuestionPlan:
    question_text: str
    normalized_question: str
    intent: str
    domain: str
    slots: list[str]
    question_type: str = "OPEN_ENDED"
    asks_confirmation: bool = False
    asks_boolean: bool = False
    asks_unknown_detail: bool = False


@dataclass(slots=True)
class SessionState:
    session_id: str
    turn_index: int = 0
    transcript: list[dict[str, str]] = field(default_factory=list)
    canonical_answers: dict[str, str] = field(default_factory=dict)
    approved_memory: dict[str, Any] = field(default_factory=dict)
    debug_log: list[dict[str, Any]] = field(default_factory=list)
