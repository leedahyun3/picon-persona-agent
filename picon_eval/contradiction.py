from __future__ import annotations

import re
from typing import Dict, List, Tuple

from picon_eval.models import Turn


class ContradictionChecker:
    def __init__(self) -> None:
        self.facts: Dict[str, str] = {}

    def check(self, response: str, history: List[Turn]) -> tuple[str, str, dict[str, str]]:
        cooperative = self._is_cooperative(response)
        if not cooperative:
            return "EVASIVE", "질문에 대한 실질 응답이 부족합니다.", {}

        extracted = self._extract_fact_map(response)
        for key, value in extracted.items():
            if key in self.facts and self.facts[key] != value:
                return "CONTRADICTS", f"{key} 값이 이전 응답과 충돌합니다: {self.facts[key]} != {value}", extracted

        self.facts.update(extracted)
        return "CONSISTENT", "", extracted

    def _is_cooperative(self, response: str) -> bool:
        evasive_markers = ["모르", "비공개", "답하기 어렵", "기억나지"]
        return not any(marker in response for marker in evasive_markers)

    def _extract_fact_map(self, response: str) -> dict[str, str]:
        facts: dict[str, str] = {}

        age_match = re.search(r"(\d{2})살", response)
        if age_match:
            facts["age"] = age_match.group(1)

        birth_match = re.search(r"(19\d{2}|20\d{2})", response)
        if birth_match and "태어" in response:
            facts["birth_year"] = birth_match.group(1)

        if "미혼" in response:
            facts["marital_status"] = "미혼"
        if "기혼" in response or "결혼" in response and "미혼" not in response:
            facts["marital_status"] = "기혼"

        if "마포구" in response:
            facts["residence"] = "서울 마포구"

        if "KAIST" in response:
            facts["education_undergrad"] = "KAIST"
        if "POSTECH" in response:
            facts["education_grad"] = "POSTECH"

        if "25명" in response:
            facts["team_size"] = "25"

        return facts
