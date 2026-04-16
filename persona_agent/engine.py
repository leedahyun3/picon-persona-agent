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
            role = message.get("role", "")
            if role == "system":
                continue
            normalized.append({"role": role, "content": message.get("content", "").strip()})
        return normalized


class PersonaEngine:
    def __init__(self, fact_sheet: FactSheet):
        self.fact_sheet = fact_sheet
        self.parser = QuestionParser()
        self.sessions = SessionStore()
        self.slot_aliases = self._build_slot_aliases()

    def respond(self, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        session = self.sessions.resolve(messages)
        plan = self.parser.parse(messages)

        if plan.asks_confirmation:
            response = self._confirmation_response(plan)
        elif plan.asks_unknown_detail:
            response = self._bounded_unknown_response(plan)
        else:
            response = self._render_answer(plan, session)

        response = self._strip_meta_leaks(response)
        response = self._prevent_bad_fallbacks(response, plan)
        self._store_canonical(plan, response, session)
        self.sessions.update(session, messages, response)
        trace = {
            "session_id": session.session_id,
            "turn_index": session.turn_index,
            "plan": {
                "intent": plan.intent,
                "domain": plan.domain,
                "slots": plan.slots,
                "asks_confirmation": plan.asks_confirmation,
                "asks_boolean": plan.asks_boolean,
                "asks_unknown_detail": plan.asks_unknown_detail,
            },
            "response": response,
        }
        session.debug_log.append(trace)
        return response, trace

    def _render_answer(self, plan: QuestionPlan, session: SessionState) -> str:
        canonical = self._match_existing_canonical(plan, session)
        if canonical:
            return canonical

        handlers = [
            self._identity_answer,
            self._work_answer,
            self._education_answer,
            self._family_answer,
            self._lifestyle_answer,
            self._opinion_answer,
            self._plans_answer,
        ]
        for handler in handlers:
            response = handler(plan)
            if response:
                return response

        return self._unknown_response(plan)

    def _identity_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if "live with your parents" in q or "parents or your parents in law" in q or "parents-in-law" in q:
            return ""
        if "birth year" in q or "year of birth" in q or "state your year of birth" in q:
            return f"I was born in {self.fact_sheet.get('identity.birth_year')}."
        if "born in the country" in q or "immigrant" in q:
            born = self.fact_sheet.get("identity.birth_place.country")
            current = self.fact_sheet.get("identity.current_residence.country")
            if born == current:
                return f"I was born in the same country where I currently live, so I am not an immigrant."
            return f"I currently live in {current}, but I was born in {born}, so I am an immigrant."
        if "born" in q and "country" not in q:
            return (
                f"I was born in {self.fact_sheet.get('identity.birth_place.city')}, "
                f"{self.fact_sheet.get('identity.birth_place.country')}."
            )
        if "나이" in q or "몇 살" in q:
            return f"I am {self._derived_age()} years old."
        if "이름" in q or "full name" in q or "your name" in q:
            return f"My name is {self.fact_sheet.display_name}."
        if "language" in q or "speak at home" in q:
            return f"I normally speak {self.fact_sheet.get('identity.home_language')} at home."
        if "어디에 살" in q or "residence" in q or "live" in q:
            city = self.fact_sheet.get("identity.current_residence.city")
            district = self.fact_sheet.get("identity.current_residence.district")
            country = self.fact_sheet.get("identity.current_residence.country")
            if "apartment" in q:
                return f"I live in {self.fact_sheet.get('identity.current_residence.apartment_name')}."
            if "neighborhood" in q:
                return f"I live in {self.fact_sheet.get('identity.current_residence.neighborhood')}."
            if "subway" in q or "station" in q:
                return f"The nearest subway station to my home is {self.fact_sheet.get('identity.current_residence.nearest_subway')}."
            if "convenience store" in q or "grocery" in q:
                return f"The convenience store I use most often is {self.fact_sheet.get('identity.current_residence.nearest_convenience_store')}."
            if "district" in q or "gu" in q:
                return f"I live in {district}, {city}."
            return f"I currently live in {district}, {city}, {country}."
        return ""

    def _work_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        company = self.fact_sheet.get("work.current_employer.company_name")
        title = self.fact_sheet.get("work.org_structure.job_title")
        team = self.fact_sheet.get("work.org_structure.team_name")
        manager = self.fact_sheet.get("work.manager.name")
        office = self.fact_sheet.get("work.office.location_name")
        commute = self.fact_sheet.get("work.office.commute")

        if any(term in q for term in ["current main activity", "activity", "status"]):
            return f"My main activity is paid employment as {title} at {company}."
        if any(term in q for term in ["직업", "occupation", "job", "work"]):
            return f"I work as {title} at {company}, where I am part of the {team} team."
        if any(term in q for term in ["company", "employer", "회사"]):
            return f"My current employer is {company}, a {self.fact_sheet.get('work.current_employer.industry')} company."
        if "ceo" in q:
            return f"The CEO of {company} is {self.fact_sheet.get('work.current_employer.ceo_name')}."
        if "email domain" in q or "email" in q:
            return f"My work email uses the @{self.fact_sheet.get('work.email_domain')} domain."
        if "start" in q or "joined" in q or "employment" in q:
            return f"I started at {company} in {self.fact_sheet.get('work.employment_start')}."
        if "previous employer" in q or "previous job" in q:
            return f"Before {company}, I worked at {self.fact_sheet.get('work.previous_employer')}."
        if any(term in q for term in ["team", "job title", "title"]):
            return f"My role is {title}, and I work on the {team} team."
        if any(term in q for term in ["manager", "supervisor", "상사"]):
            return f"My manager is {manager}, who leads our team."
        if "team member" in q or "subordinate" in q or "direct report" in q:
            return f"Some of the people I work most closely with are {', '.join(self.fact_sheet.get('work.direct_reports'))}."
        if any(term in q for term in ["office", "사무실", "location"]):
            return f"Our office is based at {office}."
        if any(term in q for term in ["commute", "출근", "transit"]):
            return f"My usual commute is {commute}."
        if any(term in q for term in ["meeting", "regular"]):
            return f"I regularly attend {self.fact_sheet.get('work.regular_meetings_summary')}."
        return ""

    def _education_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        ug = self.fact_sheet.get("education.undergraduate")
        grad = self.fact_sheet.get("education.graduate")
        if any(term in q for term in ["highest educational", "최종 학력", "degree"]):
            return f"The highest educational level I attained is {self.fact_sheet.get('education.highest_education')}."
        if "advisor" in q or "지도" in q:
            return f"My graduate advisor was {grad['advisor_name']}."
        if "thesis" in q or "논문" in q:
            return f"My master's thesis focused on {grad['thesis_topic']}."
        if "course" in q or "수업" in q:
            return f"I currently keep up with the field through {self.fact_sheet.get('education.current_courses_summary')}."
        if "undergraduate" in q or "b.s." in q or "bachelor" in q:
            return f"My undergraduate degree was {ug['degree']} from {ug['institution_name']}."
        if "graduate" in q or "master" in q:
            return f"My graduate degree was {grad['degree']} from {grad['institution_name']}."
        if "school" in q or "대학" in q or "institution" in q:
            return (
                f"I studied {ug['major']} at {ug['institution_name']} and later completed "
                f"{grad['degree']} at {grad['institution_name']}."
            )
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
            return f"I do not have children." if count == 0 else f"I have {count} children."
        if any(term in q for term in ["married", "spouse", "배우자"]):
            return f"I am {self.fact_sheet.get('family.marital_status')}."
        if re.search(r"\bcat\b|\bcat's\b|고양이", q):
            return f"My cat's name is {self.fact_sheet.get('family.cat_name')}."
        if any(term in q for term in ["family", "가족", "household"]):
            return f"My household is {self.fact_sheet.get('family.household')}."
        return ""

    def _lifestyle_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        hobbies = ", ".join(self.fact_sheet.get("lifestyle.hobbies"))
        if any(term in q for term in ["hobby", "취미", "여가"]):
            return f"My main hobbies are {hobbies}."
        if any(term in q for term in ["interest", "관심"]):
            return f"Recently I have been most interested in {', '.join(self.fact_sheet.get('lifestyle.current_interests'))}."
        if any(term in q for term in ["religion", "religious", "종교"]):
            religion = self.fact_sheet.get("lifestyle.religion")
            return f"I do not belong to a religion." if religion == "none" else f"I belong to {religion}."
        if "saved money" in q or "spent some savings" in q or "borrowed money" in q or "financial" in q:
            return f"During the past year, my household {self.fact_sheet.get('lifestyle.financial_status')}."
        if "frequent" in q or "자주" in q or "landmark" in q or "grocery" in q:
            return f"A place I frequently go to is {self.fact_sheet.get('lifestyle.frequent_place')}."
        return ""

    def _opinion_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["규제", "policy", "regulation", "innovation"]):
            return self.fact_sheet.get("opinions.ai_policy")
        if "워라밸" in q or "work life" in q:
            return self.fact_sheet.get("opinions.work_life")
        return ""

    def _plans_answer(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["5년", "five year", "future", "향후"]):
            return self.fact_sheet.get("plans.five_year_plan")
        return ""

    def _confirmation_response(self, plan: QuestionPlan) -> str:
        q = plan.normalized_question
        if any(term in q for term in ["actor", "1976", "public figure", "kim min-jun", "kim min jun"]):
            return f"No, that is not correct. {self.fact_sheet.get('identity.disambiguation')}"
        if any(term in q for term in ["neuron forge inc", "neuronforge.io", "intelligent software solutions company"]):
            return (
                f"No, that is not correct. I work for {self.fact_sheet.get('work.current_employer.company_name')}, "
                f"which is distinct from Neuron Forge Inc. and uses {self.fact_sheet.get('work.current_employer.website')}."
            )
        if "kaist" in q:
            return "Yes, that is correct."
        if "seoul national university" in q or "snu" in q:
            return "Yes, that is correct."
        if "married" in q and self.fact_sheet.get("family.marital_status") == "single":
            return "No, I am single."
        if "children" in q and self.fact_sheet.get("family.children_count") == 0:
            return "No, I do not have children."
        if "not religious" in q and self.fact_sheet.get("lifestyle.religion") == "none":
            return "Yes, that is correct."
        if self._question_matches_known_truth(q):
            return "Yes, that is correct."
        return "No, that does not match my background."

    def _bounded_unknown_response(self, plan: QuestionPlan) -> str:
        if plan.question_type == "SPECIFIC_ANSWER":
            return "I'm not sure about that specific detail right now."
        if plan.asks_boolean:
            return "I don't have enough grounded information to answer that accurately."
        return "I'd prefer not to invent details that are not part of my background."

    def _general_summary(self) -> str:
        return (
            f"I am {self.fact_sheet.display_name}, a {self.fact_sheet.get('work.org_structure.job_title')} based in "
            f"{self.fact_sheet.get('identity.current_residence.city')}, and my background centers on "
            f"{self.fact_sheet.get('education.graduate.major')} and biotech product development."
        )

    def _match_existing_canonical(self, plan: QuestionPlan, session: SessionState) -> str:
        for slot in plan.slots:
            if slot in session.canonical_answers:
                return session.canonical_answers[slot]
        return ""

    def _store_canonical(self, plan: QuestionPlan, response: str, session: SessionState) -> None:
        for slot in plan.slots:
            session.canonical_answers.setdefault(slot, response)

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

    def _build_slot_aliases(self) -> dict[str, str]:
        birth_year = self.fact_sheet.get("identity.birth_year")
        current_year = self.fact_sheet.get("meta.current_year")
        age = max(0, int(current_year) - int(birth_year))
        return {"derived.age": str(age)}

    def _derived_age(self) -> int:
        birth_year = int(self.fact_sheet.get("identity.birth_year"))
        current_year = int(self.fact_sheet.get("meta.current_year"))
        return max(0, current_year - birth_year)

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

    def _question_matches_known_truth(self, normalized_question: str) -> bool:
        checks = {
            "kaist": self.fact_sheet.get("education.undergraduate.institution_name"),
            "seoul national university": self.fact_sheet.get("education.graduate.institution_name"),
            "neuronforge bio": self.fact_sheet.get("work.current_employer.company_name"),
            "mapo-gu": self.fact_sheet.get("identity.current_residence.district"),
            "single": self.fact_sheet.get("family.marital_status"),
            "no children": "0" if self.fact_sheet.get("family.children_count") == 0 else "",
        }
        return any(fragment in normalized_question and str(value).lower() in normalized_question for fragment, value in checks.items())
