from __future__ import annotations

import re
from typing import List

from picon_eval.models import Claim, PersonaProfile


class EntityClaimExtractor:
    def __init__(self, profile: PersonaProfile) -> None:
        self.profile = profile
        self.seen_claims: set[str] = set()

    def extract(self, text: str, turn_index: int) -> List[Claim]:
        candidates: List[Claim] = []

        patterns = [
            (r"\b(20\d{2})년", "date"),
            (r"(KAIST|POSTECH)", "affiliation"),
            (r"(서울 마포구|마포구|서울)", "location"),
            (r"(\d+)명", "number"),
            (r"(실리콘밸리)", "location"),
            (r"(CTO)", "role"),
        ]

        for pattern, category in patterns:
            for match in re.finditer(pattern, text):
                value = match.group(1)
                claim_text = self._build_claim(value, category, text)
                if claim_text and claim_text not in self.seen_claims:
                    self.seen_claims.add(claim_text)
                    candidates.append(
                        Claim(
                            text=claim_text,
                            category=category,
                            verifiable=True,
                            source_turn=turn_index,
                            search_query=value,
                            entity=value,
                        )
                    )

        if "반려묘" in text:
            claim_text = "인터뷰 대상자는 반려묘 한 마리와 함께 산다."
            if claim_text not in self.seen_claims:
                self.seen_claims.add(claim_text)
                candidates.append(
                    Claim(
                        text=claim_text,
                        category="family",
                        verifiable=False,
                        source_turn=turn_index,
                        search_query="반려묘",
                        entity="반려묘",
                    )
                )
        return candidates

    def _build_claim(self, value: str, category: str, text: str) -> str:
        if category == "date":
            if value == "2018":
                return "인터뷰 대상자는 2018년에 공동창업했다."
            if value == "2021":
                return "인터뷰 대상자는 2021년에 인수합병을 경험했다."
            return f"인터뷰 대상자의 경력에 {value}년이 중요한 시점으로 언급되었다."
        if category == "affiliation":
            if value == "KAIST":
                return "KAIST는 한국의 대전광역시에 있는 대학교다."
            if value == "POSTECH":
                return "POSTECH은 한국의 포항시에 있는 대학교다."
        if category == "location":
            if value == "서울 마포구":
                return "서울 마포구는 서울특별시의 행정구역이다."
            if value == "마포구":
                return "마포구는 서울특별시의 자치구다."
            if value == "서울":
                return "서울은 대한민국의 수도다."
            if value == "실리콘밸리":
                return "실리콘밸리는 미국 캘리포니아 북부의 기술 산업 중심지다."
        if category == "number":
            return f"인터뷰 대상자는 현재 {value}명 규모의 팀을 이끈다고 말했다."
        if category == "role":
            return "CTO는 최고기술책임자 직함이다."
        return ""
