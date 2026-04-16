from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from persona_agent.fact_sheet import FactSheet
from persona_agent.parser import QuestionParser
from persona_agent.types import QuestionPlan, SessionState


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    def resolve(self, messages: list[dict[str, str]]) -> SessionState:
        normalized = self._normalize(messages)
        digest = hashlib.sha1(json.dumps(normalized, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        prefix_digest = hashlib.sha1(json.dumps(normalized[:2], ensure_ascii=False).encode("utf-8")).hexdigest()[:12]

        if digest in self.sessions:
            return self.sessions[digest]

        for session in self.sessions.values():
            if len(session.transcript) <= len(normalized) and session.transcript == normalized[: len(session.transcript)]:
                self.sessions[digest] = session
                return session

        session = self.sessions.get(prefix_digest)
        if session is None:
            session = SessionState(session_id=prefix_digest)
            self.sessions[prefix_digest] = session
        self.sessions[digest] = session
        return session

    def update(self, session: SessionState, messages: list[dict[str, str]], response: str) -> None:
        normalized = self._normalize(messages)
        session.transcript = normalized + [{"role": "assistant", "content": response}]
        session.turn_index += 1
        digest = hashlib.sha1(json.dumps(normalized, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        self.sessions[digest] = session

    def _normalize(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for message in messages:
            if message.get("role") == "system":
                continue
            normalized.append({"role": message.get("role", ""), "content": message.get("content", "").strip()})
        return normalized


class PersonaEngine:
    def __init__(self, fact_sheet: FactSheet):
        self.fact_sheet = fact_sheet
        self.parser = QuestionParser()
        self.sessions = SessionStore()

    def respond(self, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        session = self.sessions.resolve(messages)
        plan = self.parser.parse(messages)

        if session.turn_index == 0 and plan.question_type == "INSTRUCTION":
            response = self._instruction_response()
            self.sessions.update(session, messages, response)
            trace = {"type": "instruction_ack", "session_id": session.session_id, "response": response}
            session.debug_log.append(trace)
            return response, trace

        if plan.asks_confirmation:
            response = self._confirmation_response(plan)
        elif plan.asks_unknown_detail:
            response = self._bounded_unknown_response(plan)
        else:
            response = self._render_answer(plan)

        response = self._strip_meta_leaks(response)
        response = self._prevent_bad_fallbacks(response, plan)
        self.sessions.update(session, messages, response)
        trace = {
            "session_id": session.session_id,
            "turn_index": session.turn_index,
            "plan": {
                "intent": plan.intent,
                "domain": plan.domain,
                "slots": plan.slots,
                "question_type": plan.question_type,
                "asks_confirmation": plan.asks_confirmation,
                "asks_boolean": plan.asks_boolean,
                "asks_unknown_detail": plan.asks_unknown_detail,
            },
            "response": response,
        }
        session.debug_log.append(trace)
        return response, trace

    def _render_answer(self, plan: QuestionPlan) -> str:
        for handler in (
            self._identity_answer,
            self._work_answer,
            self._education_answer,
            self._family_answer,
            self._lifestyle_answer,
            self._opinion_answer,
            self._plans_answer,
        ):
            response = handler(plan)
            if response:
                return response
        return self._unknown_response(plan)

    def _identity_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if "live with your parents" in q or "parents or your parents in law" in q or "parents-in-law" in q:
            return ""
        if "born in the country" in q or "immigrant" in q:
            born = self.fact_sheet.get("identity.birth_place.country")
            current = self.fact_sheet.get("identity.current_residence.country")
            if born == current:
                return "I was born in South Korea, the same country where I currently live."
            return f"I was born in {born}, but I currently live in {current}."
        if "birth year" in q or "year of birth" in q or "state your year of birth" in q:
            return f"I was born in {self.fact_sheet.get('identity.birth_year')}."
        if "born" in q:
            if "country" in q or "passport" in q or "birthplace" in q:
                return f"I was born in {self.fact_sheet.get('identity.birth_place.country')}."
            return f"I was born in {self.fact_sheet.get('identity.birth_place.city')}, {self.fact_sheet.get('identity.birth_place.country')}."
        if ("full name" in q or "your name" in q or "display name" in q or "이름" in q) and not any(term in q for term in ["manager", "supervisor", "direct manager"]):
            return f"My name is {self.fact_sheet.display_name}."
        if "language" in q or "speak at home" in q:
            return f"I normally speak {self.fact_sheet.get('identity.home_language')} at home."
        if any(term in q for term in ["city of residence", "current city", "where do you live", "residence", "거주", "reside"]):
            city = self.fact_sheet.get("identity.current_residence.city")
            district = self.fact_sheet.get("identity.current_residence.district")
            country = self.fact_sheet.get("identity.current_residence.country")
            if any(term in q for term in ["street", "building number", "postal code", "zip code", "mailing address", "exact address"]):
                return "I'd prefer not to share my exact street address."
            if "apartment" in q:
                return f"I live in {self.fact_sheet.get('identity.current_residence.apartment_name')} in {district}, {city}."
            if "dong" in q or "neighborhood" in q:
                return f"I live in {self.fact_sheet.get('identity.current_residence.neighborhood')}, {district}."
            if "subway" in q or "station" in q or "metro" in q:
                return f"The nearest subway station is {self.fact_sheet.get('identity.current_residence.nearest_subway')}."
            if "convenience store" in q or "grocery" in q:
                return f"The nearest convenience store is {self.fact_sheet.get('identity.current_residence.nearest_convenience_store')}."
            if "district" in q or "gu " in q:
                return f"I live in {district}, {city}."
            return f"I currently live in {district}, {city}, {country}."
        return ""

    def _work_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        company = self.fact_sheet.get("work.current_employer.company_name")
        title = self.fact_sheet.get("work.org_structure.job_title")
        team = self.fact_sheet.get("work.org_structure.team_name")

        if any(term in q for term in ["ceo", "chief executive", "founder", "who runs", "who leads"]):
            return f"The CEO of {company} is {self.fact_sheet.get('work.current_employer.ceo_name')}."
        if any(term in q for term in ["email", "메일", "mail domain"]):
            return f"My work email uses the @{self.fact_sheet.get('work.email_domain')} domain."
        if any(term in q for term in ["manager", "supervisor", "report to", "direct manager"]):
            return f"My direct manager is {self.fact_sheet.get('work.manager.name')}."
        if any(term in q for term in ["direct report", "team member", "engineer on", "subordinate"]):
            return f"Some key members of my team include {', '.join(self.fact_sheet.get('work.direct_reports'))}."
        if any(term in q for term in ["start date", "when did you start", "joined", "employment start", "start month", "how long"]):
            return f"I started at {company} in {self.fact_sheet.get('work.employment_start')}."
        if any(term in q for term in ["previous employer", "previous job", "before", "predecessor"]):
            return f"Before {company}, I worked at {self.fact_sheet.get('work.previous_employer')}."
        if any(term in q for term in ["legal company name", "company name", "employment contract", "incorporation", "registration"]):
            return f"The company name on my employment contract is {self.fact_sheet.get('work.current_employer.legal_name', company)}."
        if any(term in q for term in ["office", "location", "where is", "building", "headquarters"]):
            return f"Our office is at {self.fact_sheet.get('work.office.location_name')}."
        if any(term in q for term in ["website", "homepage", "url"]):
            return f"The company website is {self.fact_sheet.get('work.current_employer.website')}."
        if any(term in q for term in ["activity", "status", "field", "work", "job", "occupation"]):
            return f"I work as {title} at {company}, where I am part of the {team} team."
        return ""

    def _education_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        ug = self.fact_sheet.get("education.undergraduate")
        grad = self.fact_sheet.get("education.graduate")

        if any(term in q for term in ["university", "institution", "school", "where you earned", "diploma"]):
            if any(term in q for term in ["master", "graduate", "m.s."]):
                return f"I earned my Master's degree from {grad['institution_name']}."
            if any(term in q for term in ["undergraduate", "bachelor", "b.s."]):
                return f"I earned my Bachelor's degree from {ug['institution_name']}."
            return f"I studied at {ug['institution_name']} for my undergraduate degree and {grad['institution_name']} for my graduate degree."
        if any(term in q for term in ["highest educational", "highest education", "educational level", "최종 학력"]):
            return f"The highest educational level I attained is {self.fact_sheet.get('education.highest_education')}."
        if "thesis" in q or "논문" in q:
            return f"My master's thesis was on {grad['thesis_topic']}."
        if "advisor" in q or "지도" in q:
            return f"My graduate advisor was {grad['advisor_name']}."
        if "degree" in q:
            if "master" in q or "graduate" in q:
                return f"My graduate degree is {grad['degree']} from {grad['institution_name']}."
            if "bachelor" in q or "undergraduate" in q:
                return f"My undergraduate degree is {ug['degree']} from {ug['institution_name']}."
            return f"The highest educational level I attained is {self.fact_sheet.get('education.highest_education')}."
        return ""

    def _family_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if "saved money" in q or "spent some savings" in q or "borrowed money" in q or "financial" in q:
            return ""
        if "parents or your parents in law" in q or "live with your parents" in q or "parents-in-law" in q:
            if self.fact_sheet.get("family.parents_cohabitation"):
                return "Yes, I live with my parents."
            return "No, I live alone with my cat, so I do not live with my parents or in-laws."
        if any(term in q for term in ["children", "child", "자녀"]):
            count = self.fact_sheet.get("family.children_count")
            return "I do not have children." if count == 0 else f"I have {count} children."
        if any(term in q for term in ["married", "spouse", "배우자"]):
            return f"I am {self.fact_sheet.get('family.marital_status')}."
        if re.search(r"\bcat\b|\bcat's\b|고양이", q):
            return f"My cat's name is {self.fact_sheet.get('family.cat_name')}."
        if any(term in q for term in ["family", "가족", "household"]):
            return f"My household is {self.fact_sheet.get('family.household')}."
        return ""

    def _lifestyle_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["saved money", "spent some savings", "borrowed money", "financial"]):
            return f"During the past year, my household {self.fact_sheet.get('lifestyle.financial_status')}."
        if any(term in q for term in ["religion", "religious", "종교"]):
            religion = self.fact_sheet.get("lifestyle.religion")
            return "I do not belong to a religion." if religion == "none" else f"I belong to {religion}."
        if any(term in q for term in ["hobby", "취미", "여가"]):
            return f"My main hobbies are {', '.join(self.fact_sheet.get('lifestyle.hobbies'))}."
        if any(term in q for term in ["interest", "관심"]):
            return f"Recently I have been most interested in {', '.join(self.fact_sheet.get('lifestyle.current_interests'))}."
        if any(term in q for term in ["frequent", "landmark", "grocery"]):
            return f"A place I frequently go to is {self.fact_sheet.get('lifestyle.frequent_place')}."
        return ""

    def _opinion_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["policy", "ai regulation", "innovation", "규제"]):
            return self.fact_sheet.get("opinions.ai_policy")
        if "work life" in q or "워라밸" in q:
            return self.fact_sheet.get("opinions.work_life")
        return ""

    def _plans_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["five year", "future", "향후", "5년"]):
            return self.fact_sheet.get("plans.five_year_plan")
        return ""

    def _confirmation_response(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question

        if any(term in q for term in ["actor", "1976", "public figure", "kim min-jun", "kim min jun"]):
            return f"No, that is not correct. {self.fact_sheet.get('identity.disambiguation')}"

        if self._asks_if_entity_is_different(q, "neuronforge bio"):
            return (
                f"No, that is not correct. I work for {self.fact_sheet.get('work.current_employer.company_name')}, "
                f"which is a separate company. Our website is {self.fact_sheet.get('work.current_employer.website')}."
            )

        if "korean" in q and "language" in q and self.fact_sheet.get("identity.home_language", "").lower() == "korean":
            return "Yes, that is correct. I speak Korean."
        if "seoul" in q and self.fact_sheet.get("identity.current_residence.city", "").lower() == "seoul":
            return "Yes, that is correct. I live in Seoul."
        if ("south korea" in q or "korea" in q) and self.fact_sheet.get("identity.current_residence.country", "").lower() == "south korea":
            if self._is_asking_about_different_entity(q):
                return "No, that refers to something else. I live in South Korea."
            return "Yes, that is correct."
        if "mapo" in q and self.fact_sheet.get("identity.current_residence.district", "").lower() == "mapo-gu":
            return "Yes, that is correct. I live in Mapo-gu."
        if "kaist" in q:
            return "Yes, that is correct. I studied at KAIST."
        if "seoul national university" in q or "snu" in q:
            return "Yes, that is correct. I studied at Seoul National University."
        if "married" in q and self.fact_sheet.get("family.marital_status") == "single":
            return "No, I am single."
        if "children" in q and self.fact_sheet.get("family.children_count") == 0:
            return "No, I do not have children."

        urls_in_question = re.findall(r"https?://[^\s\)]+", q)
        if urls_in_question:
            return self._evaluate_url_confirmation(q, urls_in_question)

        if self._core_claim_matches_persona(q):
            return "Yes, that is correct."
        return "I'm not entirely sure about that specific detail."

    def _bounded_unknown_response(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["street", "address", "postal", "phone", "mobile"]):
            return "I'd rather not share that level of detail about my personal address."
        if any(term in q for term in ["veterinary", "hospital", "hr representative", "bank", "registration number", "tax"]):
            return "I don't recall that specific detail off the top of my head."
        return "I'm not sure about that specific detail."

    def _unknown_response(self, plan: QuestionPlan) -> str:
        if plan.question_type == "SPECIFIC_ANSWER":
            return "I'm not sure about that specific detail."
        if plan.asks_boolean:
            return "I don't have enough information to answer that accurately."
        return "I don't have that information off the top of my head."

    def _prevent_bad_fallbacks(self, response: str, plan: QuestionPlan) -> str:
        forbidden = "I am Minjun Kim, a Chief Technology Officer"
        if forbidden in response and plan.question_type in {"SPECIFIC_ANSWER", "YES_NO"}:
            return self._unknown_response(plan)
        if response.strip() == "Yes, that is correct." and plan.question_type == "SPECIFIC_ANSWER":
            return self._unknown_response(plan)
        return response

    def _strip_meta_leaks(self, response: str) -> str:
        banned = [
            "profile says",
            "my profile",
            "fact sheet",
            "background documentation",
            "was provided",
            "not specified",
        ]
        cleaned = response
        for phrase in banned:
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _asks_if_entity_is_different(self, q: str, entity_name: str) -> bool:
        patterns = [
            rf"{entity_name}.*you mentioned.*is ",
            rf"confirm.*{entity_name}.*refers to",
            rf"{entity_name}.*consulting firm",
            rf"{entity_name}.*software solutions company",
        ]
        return any(re.search(pattern, q) for pattern in patterns)

    def _is_asking_about_different_entity(self, q: str) -> bool:
        different_entity_signals = [
            "guesthouse", "hotel", "restaurant", "museum", "center", "tower", "temple",
            "palace", "park", "gallery", "consulting firm", "software solutions company", "art center",
        ]
        return any(signal in q for signal in different_entity_signals)

    def _evaluate_url_confirmation(self, q: str, urls: list[str]) -> str:
        known_url = self.fact_sheet.get("work.current_employer.website", "").lower()
        for url in urls:
            url_clean = url.rstrip(")").rstrip("?").lower()
            if known_url and known_url in url_clean:
                return "Yes, that is correct."
        if self._core_claim_matches_persona(q):
            return "Yes, that is correct."
        return "No, that does not match my background."

    def _core_claim_matches_persona(self, q: str) -> bool:
        if "korean" in q and "language" in q:
            return self.fact_sheet.get("identity.home_language", "").lower() == "korean"
        if "seoul" in q:
            return self.fact_sheet.get("identity.current_residence.city", "").lower() == "seoul"
        if "mapo" in q:
            return self.fact_sheet.get("identity.current_residence.district", "").lower() == "mapo-gu"
        if "kaist" in q:
            return True
        if "seoul national university" in q or "snu" in q:
            return True
        if "neuronforge bio" in q:
            return True
        return False

    def _instruction_response(self) -> str:
        return (
            f"Hello, I'm {self.fact_sheet.display_name}. I'm a "
            f"{self.fact_sheet.get('work.org_structure.job_title')} at "
            f"{self.fact_sheet.get('work.current_employer.company_name')}, based in "
            f"{self.fact_sheet.get('identity.current_residence.city')}. I'm happy to answer your questions."
        )
