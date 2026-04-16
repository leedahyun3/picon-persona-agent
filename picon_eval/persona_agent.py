from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from picon_eval.models import PersonaProfile


GTK_FIELD_MAP = {
    "이름과 나이": lambda p: f"제 이름은 {p.name}이고, {p.age}살입니다.",
    "현재 어디에 살고": lambda p: f"현재 {p.residence}에 살고 있습니다.",
    "직업이 무엇": lambda p: f"직업은 {p.occupation}입니다.",
    "최종 학력": lambda p: f"학력은 {', '.join(p.education)}입니다.",
    "가족 구성": lambda p: f"가족 구성은 {p.family}입니다.",
    "취미나 여가": lambda p: f"취미는 {', '.join(p.hobbies)}입니다.",
    "최근 가장 관심": lambda p: f"최근에는 {', '.join(p.interests[:2])}에 가장 관심이 많습니다.",
    "가장 보람": lambda p: f"가장 보람 있었던 순간은 {' / '.join(p.experiences[:2])}을 해냈을 때입니다.",
    "향후 5년 계획": lambda p: f"향후 5년 계획은 {p.five_year_plan}입니다.",
    "성격을 한마디": lambda p: f"제 성격을 한마디로 표현하면 {p.personality}입니다."
}


@dataclass
class PersonaAgent:
    profile: PersonaProfile

    def respond(self, question: str, history: List[str]) -> str:
        for key, handler in GTK_FIELD_MAP.items():
            if key in question:
                return handler(self.profile)

        if "창업" in question:
            return "2018년에 공동창업했고, 2021년에 인수합병을 경험했습니다."
        if "실리콘밸리" in question or "미국" in question:
            return "미국 팀과 3년 동안 실리콘밸리 중심으로 원격 협업했습니다."
        if "팀" in question and ("몇 명" in question or "규모" in question):
            return "현재는 25명 정도 되는 팀을 이끌고 있습니다."
        if "규제" in question or "ai policy" in question.lower():
            return self.profile.opinions["ai_policy"]
        if "워라밸" in question or "성장기" in question:
            return self.profile.opinions["work_life"]
        if "학교" in question or "대학" in question:
            return f"학부는 KAIST 전산학과였고, 대학원은 POSTECH 인공지능 석사였습니다."
        if "거주" in question or "출퇴근" in question:
            return f"{self.profile.residence}에 살고 있어서 회사까지 이동하기 편합니다."
        if "반려" in question or "고양이" in question:
            return "반려묘 한 마리와 같이 지냅니다."
        if "이름" in question and "회사" in question:
            return "회사 이름은 공개 인터뷰에서는 보통 비공개로 두지만 서울의 바이오테크 스타트업입니다."
        return (
            f"저는 {self.profile.occupation}으로 일하고 있고, "
            f"{self.profile.residence}에서 생활하며 {', '.join(self.profile.hobbies[:2])}를 즐깁니다."
        )

    def confirm(self, question: str) -> str:
        if "같은 대상" in question or "맞나요" in question:
            return "네, 맞습니다."
        return "네."
