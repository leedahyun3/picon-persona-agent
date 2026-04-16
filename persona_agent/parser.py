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
        question_type = self._classify_question_type(normalized)

        if self._contains_any(normalized, ["이름", "full name", "your name", "display name"]):
            slots.append("identity.display_name")
            intent = "identity"
            domain = "identity"
        if self._contains_any(normalized, ["live with your parents", "parents or your parents in law", "parents-in-law", "in law"]) or self._contains_cat_reference(normalized):
            domain = "family"
            intent = "family"
            if "live with your parents" in normalized or "parents or your parents in law" in normalized or "parents-in-law" in normalized or "in law" in normalized:
                slots.append("family.parents_cohabitation")
            if self._contains_cat_reference(normalized):
                slots.append("family.cat_name")
        if self._contains_any(normalized, ["나이", "birth year", "year of birth", "몇 살", "born", "state your year of birth"]):
            if "year" in normalized or "birth" in normalized or "born" in normalized:
                slots.append("identity.birth_year")
            else:
                slots.append("derived.age")
            intent = "identity"
            domain = "identity"
        if self._contains_any(normalized, ["어디에 살", "current residence", "where do you live", "which district", "apartment", "nearest subway", "subway station", "convenience store"]):
            slots.extend(
                [
                    "identity.current_residence.city",
                    "identity.current_residence.country",
                    "identity.current_residence.district",
                    "identity.current_residence.neighborhood",
                    "identity.current_residence.apartment_name",
                    "identity.current_residence.nearest_subway",
                    "identity.current_residence.nearest_convenience_store",
                ]
            )
            domain = "identity"
        if self._contains_any(normalized, ["직업", "job", "occupation", "activity", "work", "employment", "employer", "company", "ceo", "email domain"]):
            slots.extend(
                [
                    "work.org_structure.job_title",
                    "work.current_employer.company_name",
                    "work.current_employer.ceo_name",
                    "work.email_domain",
                    "work.employment_start",
                    "work.previous_employer",
                ]
            )
            intent = "work"
            domain = "work"
        if self._contains_any(normalized, ["학력", "degree", "school", "대학", "institution", "advisor", "thesis", "education", "educational level", "highest educational"]):
            domain = "education"
            intent = "education"
        if self._contains_any(normalized, ["가족", "married", "children", "child", "spouse", "family", "parents", "household", "live with"]) or self._contains_cat_reference(normalized):
            domain = "family"
            intent = "family"
        if self._contains_any(normalized, ["취미", "hobby", "여가", "interest", "language", "religion", "financial", "saved money"]):
            domain = "lifestyle"
            intent = "lifestyle"
        if self._contains_any(normalized, ["manager", "매니저", "상사", "supervisor"]):
            slots.append("work.manager.name")
            domain = "work"
            intent = "work"
        if self._contains_any(normalized, ["office", "사무실", "location", "출근", "commute", "transit", "route", "nearest landmark", "grocery"]):
            domain = "work"
            intent = "work"
        if self._contains_any(normalized, ["religion", "religious", "종교"]):
            slots.append("lifestyle.religion")
            domain = "lifestyle"
            intent = "lifestyle"
        if self._contains_any(normalized, ["language", "speak at home", "mother tongue", "native language"]):
            slots.extend(["identity.native_language", "identity.home_language"])
            domain = "identity"
            intent = "identity"
        if self._contains_any(normalized, ["saved money", "spent some savings", "borrowed money", "financial"]):
            slots.append("lifestyle.financial_status")
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
            question_type=question_type,
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
            if "highest educational" in normalized or "highest education" in normalized:
                return ["education.highest_education"]
            if "advisor" in normalized or "지도" in normalized:
                return ["education.graduate.advisor_name"]
            if "thesis" in normalized or "논문" in normalized:
                return ["education.graduate.thesis_topic"]
            if "course" in normalized or "수업" in normalized:
                return ["education.current_courses"]
            return ["education.highest_education", "education.undergraduate.institution_name", "education.graduate.institution_name"]
        if domain == "family":
            if self._contains_cat_reference(normalized):
                return ["family.cat_name"]
            if "live with your parents" in normalized or "parents or your parents in law" in normalized:
                return ["family.parents_cohabitation"]
            if "children" in normalized or "child" in normalized or "자녀" in normalized:
                return ["family.children_count"]
            if "spouse" in normalized or "배우자" in normalized:
                return ["family.marital_status"]
            return ["family.marital_status", "family.household"]
        if domain == "work":
            if "email domain" in normalized or "email" in normalized:
                return ["work.email_domain"]
            if "ceo" in normalized:
                return ["work.current_employer.ceo_name"]
            if "start" in normalized or "join" in normalized:
                return ["work.employment_start"]
            if "previous employer" in normalized or "previous job" in normalized:
                return ["work.previous_employer"]
            return ["work.current_employer.company_name", "work.org_structure.job_title"]
        if domain == "lifestyle":
            if "language" in normalized:
                return ["identity.home_language"]
            if "saved money" in normalized or "financial" in normalized:
                return ["lifestyle.financial_status"]
            if "religion" in normalized:
                return ["lifestyle.religion"]
            return ["lifestyle.hobbies", "lifestyle.frequent_place"]
        return ["identity.display_name"]

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _contains_cat_reference(self, text: str) -> bool:
        return bool(re.search(r"\bcat\b|\bcat's\b|고양이", text))

    def _classify_question_type(self, normalized: str) -> str:
        if "would you confirm" in normalized or "can you confirm" in normalized:
            return "CONFIRMATION"
        if normalized.startswith(("do ", "are ", "did ", "have ", "has ", "were ", "is ", "was ")):
            return "YES_NO"
        if normalized.startswith(("what is", "what are", "state ", "name ", "identify ", "tell me ", "can you tell me", "which ", "who ")):
            return "SPECIFIC_ANSWER"
        return "OPEN_ENDED"
