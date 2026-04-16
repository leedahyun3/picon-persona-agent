from __future__ import annotations

import re

from persona_agent.types import QuestionPlan


class QuestionParser:
    def parse(self, messages: list[dict[str, str]]) -> QuestionPlan:
        question = self._last_user_message(messages)
        normalized = re.sub(r"\s+", " ", question).strip().lower()

        if self._is_instruction_message(normalized):
            return QuestionPlan(
                question_text=question,
                normalized_question=normalized,
                intent="instruction",
                domain="instruction",
                slots=[],
                question_type="INSTRUCTION",
            )

        slots: list[str] = []
        intent = "open"
        domain = "general"
        question_type = self._classify_question_type(normalized)

        if self._contains_any(normalized, ["manager", "supervisor", "report to", "direct manager"]):
            slots.append("work.manager.name")
            intent = "work"
            domain = "work"

        if self._contains_any(normalized, ["full name", "your name", "display name", "이름"]) and not self._contains_any(normalized, ["manager", "supervisor", "direct manager"]):
            slots.append("identity.display_name")
            intent = "identity"
            domain = "identity"

        if self._contains_any(normalized, ["birth year", "year of birth", "state your year of birth"]):
            slots.append("identity.birth_year")
            intent = "identity"
            domain = "identity"
        elif self._contains_any(normalized, ["born in the country", "currently living in", "immigrant"]):
            slots.append("identity.birth_place.country")
            intent = "identity"
            domain = "identity"
        elif self._contains_any(normalized, ["birthplace", "birth place", "born in", "birth city", "birth country"]):
            slots.extend(["identity.birth_place.city", "identity.birth_place.country"])
            intent = "identity"
            domain = "identity"
        elif self._contains_any(
            normalized,
            [
                "city of residence",
                "current city",
                "where do you live",
                "current residence",
                "which district",
                "apartment",
                "nearest subway",
                "subway station",
                "convenience store",
                "neighborhood",
                "dong",
                "residence",
            ],
        ):
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
            intent = "identity"
            domain = "identity"

        if self._contains_any(normalized, ["language", "speak at home", "mother tongue", "native language"]):
            slots.extend(["identity.native_language", "identity.home_language"])
            intent = "identity"
            domain = "identity"

        if self._contains_any(normalized, ["ceo", "chief executive", "who runs", "who leads", "founder"]):
            slots.append("work.current_employer.ceo_name")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["email", "email domain", "mail domain"]):
            slots.append("work.email_domain")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["start date", "when did you start", "joined", "employment start", "start month", "how long"]):
            slots.append("work.employment_start")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["previous employer", "previous job", "before ", "predecessor"]):
            slots.append("work.previous_employer")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["direct report", "team member", "engineer on", "subordinate"]):
            slots.append("work.direct_reports")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["office", "where is", "building", "headquarters", "location"]):
            slots.append("work.office.location_name")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["website", "homepage", "url"]):
            slots.append("work.current_employer.website")
            intent = "work"
            domain = "work"
        elif self._contains_any(normalized, ["job", "occupation", "activity", "work", "employment", "employer", "company", "field", "status"]):
            slots.extend(["work.org_structure.job_title", "work.current_employer.company_name"])
            intent = "work"
            domain = "work"

        if self._contains_any(normalized, ["university", "institution", "school", "where you earned", "diploma"]):
            if self._contains_any(normalized, ["master", "graduate", "m.s."]):
                slots.append("education.graduate.institution_name")
            elif self._contains_any(normalized, ["undergraduate", "bachelor", "b.s."]):
                slots.append("education.undergraduate.institution_name")
            else:
                slots.extend(["education.undergraduate.institution_name", "education.graduate.institution_name"])
            intent = "education"
            domain = "education"
        elif self._contains_any(normalized, ["highest educational", "highest education", "educational level", "최종 학력"]):
            slots.append("education.highest_education")
            intent = "education"
            domain = "education"
        elif self._contains_any(normalized, ["thesis", "논문"]):
            slots.append("education.graduate.thesis_topic")
            intent = "education"
            domain = "education"
        elif self._contains_any(normalized, ["advisor", "지도"]):
            slots.append("education.graduate.advisor_name")
            intent = "education"
            domain = "education"
        elif self._contains_any(normalized, ["degree", "education", "학력", "대학"]):
            intent = "education"
            domain = "education"

        if self._contains_any(normalized, ["live with your parents", "parents or your parents in law", "parents-in-law", "in law"]):
            slots.append("family.parents_cohabitation")
            intent = "family"
            domain = "family"
        elif self._contains_any(normalized, ["children", "child", "자녀"]):
            slots.append("family.children_count")
            intent = "family"
            domain = "family"
        elif self._contains_any(normalized, ["married", "spouse", "배우자"]):
            slots.append("family.marital_status")
            intent = "family"
            domain = "family"
        elif self._contains_cat_reference(normalized):
            slots.append("family.cat_name")
            intent = "family"
            domain = "family"
        elif self._contains_any(normalized, ["family", "가족", "household", "live with"]):
            slots.append("family.household")
            intent = "family"
            domain = "family"

        if self._contains_any(normalized, ["saved money", "spent some savings", "borrowed money", "financial"]):
            slots.append("lifestyle.financial_status")
            intent = "lifestyle"
            domain = "lifestyle"
        elif self._contains_any(normalized, ["religion", "religious", "종교"]):
            slots.append("lifestyle.religion")
            intent = "lifestyle"
            domain = "lifestyle"
        elif self._contains_any(normalized, ["hobby", "취미", "여가"]):
            slots.append("lifestyle.hobbies")
            intent = "lifestyle"
            domain = "lifestyle"
        elif self._contains_any(normalized, ["interest", "관심", "frequent", "landmark", "grocery"]):
            slots.append("lifestyle.frequent_place")
            intent = "lifestyle"
            domain = "lifestyle"

        if self._contains_any(normalized, ["policy", "ai regulation", "innovation", "규제"]):
            slots.append("opinions.ai_policy")
            intent = "opinion"
            domain = "opinions"
        if self._contains_any(normalized, ["five year", "future plan", "향후", "5년"]):
            slots.append("plans.five_year_plan")
            intent = "plans"
            domain = "plans"

        if not slots:
            slots = self._infer_slots_from_domain(domain, normalized)

        asks_confirmation = "would you confirm" in normalized or "can you confirm" in normalized
        asks_boolean = asks_confirmation or normalized.startswith(("do ", "are ", "did ", "have ", "has ", "were ", "is ", "was "))
        asks_unknown_detail = self._contains_any(
            normalized,
            [
                "street name", "street address", "building number", "postal code", "zip code", "mailing address",
                "exact address", "bank", "salary", "account", "registration number", "tax", "mobile carrier",
                "phone number", "linkedin", "instagram", "social media", "github", "profile url", "veterinary",
                "vet clinic", "hospital", "vaccination", "hr representative", "onboarded", "gu office", "registered",
                "adoption", "desk position", "window view", "furniture color", "weekday", "floor count",
            ],
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
            if "master" in normalized or "graduate" in normalized:
                return ["education.graduate.institution_name"]
            if "undergraduate" in normalized or "bachelor" in normalized:
                return ["education.undergraduate.institution_name"]
            return ["education.highest_education"]
        if domain == "family":
            return ["family.household"]
        if domain == "work":
            return ["work.current_employer.company_name", "work.org_structure.job_title"]
        if domain == "lifestyle":
            return ["lifestyle.frequent_place"]
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

    def _is_instruction_message(self, normalized: str) -> bool:
        indicators = [
            "interview guidelines",
            "thank you for contributing",
            "interview is being held",
            "warning",
            "demographic questions",
            "50+",
        ]
        return sum(1 for indicator in indicators if indicator in normalized) >= 2
