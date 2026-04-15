from __future__ import annotations

from typing import List

from picon_eval.models import Claim, Evidence, Turn


GTK_QUESTIONS = [
    "이름과 나이를 알려주세요.",
    "현재 어디에 살고 계신가요?",
    "직업이 무엇인가요?",
    "최종 학력을 알려주세요.",
    "가족 구성은 어떻게 되나요?",
    "취미나 여가활동은 무엇인가요?",
    "최근 가장 관심 있는 분야가 무엇인가요?",
    "일하면서 가장 보람 있었던 순간은 언제인가요?",
    "향후 5년 계획이 있다면?",
    "본인의 성격을 한마디로 표현한다면?"
]


class Questioner:
    def __init__(self) -> None:
        self.strategy_cycle = [
            "Deep Dive",
            "Timeline Pressure",
            "Opinion Follow-up",
            "Fact Check",
            "Deep Dive",
            "Timeline Pressure",
            "Opinion Follow-up",
            "Fact Check",
            "Deep Dive",
            "Timeline Pressure",
        ]

    def get_gtk_question(self, index: int) -> str:
        return GTK_QUESTIONS[index]

    def get_retest_question(self, index: int) -> str:
        return GTK_QUESTIONS[index]

    def generate_main_question(
        self,
        turn_index: int,
        history: List[Turn],
        extracted_claims: List[Claim],
        evidence: List[Evidence],
    ) -> tuple[str, str]:
        strategy = self.strategy_cycle[(turn_index - 10) % len(self.strategy_cycle)]
        last_response = history[-1].response if history else ""
        last_claim = extracted_claims[-1].text if extracted_claims else ""
        last_evidence = evidence[-1] if evidence else None

        if strategy == "Deep Dive":
            if "KAIST" in last_response or "POSTECH" in last_response:
                return "학교 경로를 시간순으로 다시 말씀해 주세요.", strategy
            if "마포구" in last_response:
                return "마포구에서 가장 자주 가는 장소를 하나 말해주세요.", strategy
            return "방금 답변에서 가장 중요한 구체 사실을 다시 말해주세요.", strategy

        if strategy == "Timeline Pressure":
            if "2018" in last_response or "2021" in last_response:
                return "2018년부터 2021년까지의 주요 경력을 연도순으로 말해주세요.", strategy
            return "해당 경험이 발생한 시점을 앞뒤 순서로 정리해 주세요.", strategy

        if strategy == "Opinion Follow-up":
            if "규제" in last_response:
                return "AI 규제가 혁신을 막는다고 보는 실제 이유를 한 가지 말해주세요.", strategy
            return "방금 말한 입장을 실제 경험과 연결해 설명해주세요.", strategy

        if strategy == "Fact Check":
            if last_evidence and last_evidence.label == "REFUTED":
                return f"'{last_claim}' 관련해 공개 정보와 차이가 있는데, 더 구체적으로 말해주세요.", strategy
            if "서울" in last_response or "마포구" in last_response:
                return "현재 거주지와 업무 사이의 연결점을 구체적으로 말해주세요.", strategy
            return "방금 언급한 사실 중 공개적으로 확인 가능한 내용을 하나 더 말해주세요.", strategy

        return "이전에 말한 내용과 연결되는 세부사항을 하나 더 알려주세요.", strategy
