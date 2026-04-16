from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Turn:
    index: int
    phase: str
    question: str
    response: str
    strategy: str = ""


@dataclass
class Claim:
    text: str
    category: str
    verifiable: bool
    source_turn: int
    search_query: str
    entity: str = ""


@dataclass
class Evidence:
    claim: str
    label: str
    evidence: str
    source: str = "reference_kb"


@dataclass
class TurnAnalysis:
    claims: List[Claim] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    contradiction: str = "CONSISTENT"
    contradiction_reason: str = ""
    cooperative: bool = True


@dataclass
class PersonaProfile:
    id: str
    name: str
    age: int
    birth_year: int
    gender: str
    nationality: str
    residence: str
    occupation: str
    education: List[str]
    family: str
    hobbies: List[str]
    interests: List[str]
    five_year_plan: str
    personality: str
    experiences: List[str]
    opinions: Dict[str, str]
    public_facts: List[Dict[str, str]]


@dataclass
class SessionStats:
    total_turns: int
    contradictions_detected: int
    claims_extracted: int
    claims_refuted: int
    evasive_responses: int


@dataclass
class ScoreBreakdown:
    cooperativeness: float
    non_contradiction_rate: float
    coverage: float
    non_refutation_rate: float
    retest_similarity: float


@dataclass
class EvaluationResult:
    session_id: str
    persona_agent_id: str
    scores: Dict[str, float]
    breakdown: ScoreBreakdown
    session_stats: SessionStats
    turns: List[Turn]
    analyses: List[TurnAnalysis]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["breakdown"] = asdict(self.breakdown)
        payload["session_stats"] = asdict(self.session_stats)
        return payload
