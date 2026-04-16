from __future__ import annotations

import re

from persona_agent.types import QuestionPlan


class QuestionParser:
    def parse(self, messages: list[dict[str, str]]) -> QuestionPlan:
        question = self._last_user_message(messages)
        normalized = re.sub(r"\s+", " ", question).strip().lower()
        slots: list[str] = []
        intent = "open"
        domain = "general"

        if self._contains_any(normalized, ["이름", "name"]):
            slots.append("identity.display_name")
            intent = "identity"
            domain = "identity"
        if self._contains_any(normalized, ["나이", "birth year", "year of birth", "몇 살", "born"]):
            if "year" in normalized or "birth" in normalized or "born" in normalized:
                slots.append("identity.birth_year")
            else:
                slots.append("derived.age")
            intent = "identity"
            domain = "identity"
        if self._contains_any(normalized, ["어디에 살", "residence", "live", "city"]):
            slots.extend(["identity.current_residence.city", "identity.current_residence.country"])
            domain = "identity"
        if self._contains_any(normalized, ["직업", "job", "occupation", "activity", "work"]):
            slots.extend(["work.org_structure.job_title", "work.current_employer.company_name"])
            intent = "work"
            domain = "work"
        if self._contains_any(normalized, ["학력", "degree", "school", "대학", "institution", "advisor", "thesis"]):
            domain = "education"
            intent = "education"
        if self._contains_any(normalized, ["가족", "married", "children", "child", "spouse", "family"]):
            domain = "family"
            intent = "family"
        if self._contains_any(normalized, ["취미", "hobby", "여가", "interest"]):
            domain = "lifestyle"
            intent = "lifestyle"
        if self._contains_any(normalized, ["manager", "매니저", "상사", "supervisor"]):
            slots.append("work.manager.name")
            domain = "work"
            intent = "work"
        if self._contains_any(normalized, ["office", "사무실", "location", "출근", "commute", "transit"]):
            domain = "work"
            intent = "work"
        if self._contains_any(normalized, ["religion", "religious", "종교"]):
            slots.append("lifestyle.religion")
            domain = "lifestyle"
            intent = "lifestyle"
        if self._contains_any(normalized, ["규제", "policy", "ai regulation", "innovation"]):
            slots.append("opinions.ai_policy")
            domain = "opinions"
            intent = "opinion"
        if self._contains_any(normalized, ["5년", "five year", "future plan", "향후"]):
            slots.append("plans.five_year_plan")
            domain = "plans"
            intent = "plans"

        if not slots:
            slots = self._infer_slots_from_domain(domain, normalized)

        asks_confirmation = self._contains_any(normalized, ["맞", "correct", "confirm", "same entity", "right"])
        asks_boolean = asks_confirmation or normalized.startswith(("do ", "did ", "is ", "are ", "were ", "have "))
        asks_unknown_detail = self._contains_any(
            normalized,
            ["desk position", "window view", "furniture color", "weekday", "floor count"],
        )

        return QuestionPlan(
            question_text=question,
            normalized_question=normalized,
            intent=intent,
            domain=domain,
            slots=list(dict.fromkeys(slots)),
            asks_confirmation=asks_confirmation,
            asks_boolean=asks_boolean,
            asks_unknown_detail=asks_unknown_detail,
        )

    def _last_user_message(self, messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "").strip()
        return ""

    def _infer_slots_from_domain(self, domain: str, normalized: str) -> list[str]:
        if domain == "education":
            if "advisor" in normalized or "지도" in normalized:
                return ["education.graduate.advisor_name"]
            if "thesis" in normalized or "논문" in normalized:
                return ["education.graduate.thesis_topic"]
            if "course" in normalized or "수업" in normalized:
                return ["education.current_courses"]
            return ["education.undergraduate.institution_name", "education.graduate.institution_name"]
        if domain == "family":
            if "children" in normalized or "child" in normalized or "자녀" in normalized:
                return ["family.children_count"]
            if "spouse" in normalized or "배우자" in normalized:
                return ["family.marital_status"]
            return ["family.marital_status", "family.household"]
        if domain == "work":
            return ["work.current_employer.company_name", "work.org_structure.job_title"]
        if domain == "lifestyle":
            return ["lifestyle.hobbies", "lifestyle.frequent_places"]
        return ["identity.display_name"]

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)
