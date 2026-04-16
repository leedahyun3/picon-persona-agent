from __future__ import annotations

from datetime import datetime
from typing import List

from picon_eval.contradiction import ContradictionChecker
from picon_eval.evaluator import Evaluator
from picon_eval.extractor import EntityClaimExtractor
from picon_eval.models import PersonaProfile, Turn, TurnAnalysis
from picon_eval.persona_agent import PersonaAgent
from picon_eval.questioner import Questioner
from picon_eval.verifier import ReferenceSearchBackend


class Orchestrator:
    def __init__(self, profile: PersonaProfile) -> None:
        self.profile = profile
        self.persona_agent = PersonaAgent(profile)
        self.questioner = Questioner()
        self.extractor = EntityClaimExtractor(profile)
        self.verifier = ReferenceSearchBackend(profile)
        self.contradiction_checker = ContradictionChecker()
        self.evaluator = Evaluator()
        self.history: List[Turn] = []
        self.analyses: List[TurnAnalysis] = []

    def run_session(self, main_turns: int = 40):
        gtk_turns: List[Turn] = []
        retest_turns: List[Turn] = []

        for idx in range(10):
            turn = self._run_turn(
                phase="get_to_know",
                index=idx + 1,
                question=self.questioner.get_gtk_question(idx),
                strategy="Get-to-Know",
            )
            gtk_turns.append(turn)

        for idx in range(main_turns):
            question, strategy = self.questioner.generate_main_question(
                turn_index=10 + idx,
                history=self.history,
                extracted_claims=[claim for analysis in self.analyses for claim in analysis.claims],
                evidence=[evidence for analysis in self.analyses for evidence in analysis.evidence],
            )
            self._run_turn(
                phase="main_interrogation",
                index=len(self.history) + 1,
                question=question,
                strategy=strategy,
            )

        for idx in range(10):
            turn = self._run_turn(
                phase="retest",
                index=len(self.history) + 1,
                question=self.questioner.get_retest_question(idx),
                strategy="Retest",
            )
            retest_turns.append(turn)

        session_id = datetime.now().strftime("eval_%Y%m%d_%H%M%S")
        return self.evaluator.evaluate(
            session_id=session_id,
            persona_id=self.profile.id,
            turns=self.history,
            analyses=self.analyses,
            gtk_turns=gtk_turns,
            retest_turns=retest_turns,
        )

    def _run_turn(self, phase: str, index: int, question: str, strategy: str) -> Turn:
        response = self.persona_agent.respond(question, [turn.response for turn in self.history])
        turn = Turn(index=index, phase=phase, question=question, response=response, strategy=strategy)
        contradiction, reason, _ = self.contradiction_checker.check(response, self.history)
        claims = self.extractor.extract(response, index)
        evidence = [self.verifier.verify(claim) for claim in claims if claim.verifiable]
        analysis = TurnAnalysis(
            claims=claims,
            evidence=evidence,
            contradiction=contradiction,
            contradiction_reason=reason,
            cooperative=contradiction != "EVASIVE",
        )
        self.history.append(turn)
        self.analyses.append(analysis)
        return turn
