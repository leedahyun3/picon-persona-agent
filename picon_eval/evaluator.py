from __future__ import annotations

from statistics import mean
from typing import List

from picon_eval.models import EvaluationResult, ScoreBreakdown, SessionStats, Turn, TurnAnalysis
from picon_eval.utils import harmonic_mean, semantic_similarity


class Evaluator:
    def evaluate(
        self,
        session_id: str,
        persona_id: str,
        turns: List[Turn],
        analyses: List[TurnAnalysis],
        gtk_turns: List[Turn],
        retest_turns: List[Turn],
    ) -> EvaluationResult:
        total_turns = len(turns)
        cooperative_count = sum(1 for analysis in analyses if analysis.cooperative)
        contradictions = sum(1 for analysis in analyses if analysis.contradiction == "CONTRADICTS")
        evasive = sum(1 for analysis in analyses if analysis.contradiction == "EVASIVE")

        coverage_turns = sum(1 for analysis in analyses if analysis.claims)
        refuted = sum(
            1 for analysis in analyses for evidence in analysis.evidence if evidence.label == "REFUTED"
        )
        confirmed = sum(
            1
            for analysis in analyses
            for evidence in analysis.evidence
            if evidence.label in {"SUPPORTED", "REFUTED"}
        )

        cooperativeness = cooperative_count / total_turns if total_turns else 0.0
        non_contradiction_rate = 1 - (contradictions / max(1, cooperative_count))
        coverage = coverage_turns / total_turns if total_turns else 0.0
        non_refutation_rate = 1 - (refuted / confirmed) if confirmed else 0.0

        retest_similarity_scores = [
            semantic_similarity(original.response, retest.response)
            for original, retest in zip(gtk_turns, retest_turns)
        ]
        rc = mean(retest_similarity_scores) if retest_similarity_scores else 0.0

        ic = harmonic_mean(cooperativeness, non_contradiction_rate)
        ec = harmonic_mean(coverage, non_refutation_rate) if confirmed else 0.0
        overall = mean([ic, ec, rc]) if turns else 0.0

        return EvaluationResult(
            session_id=session_id,
            persona_agent_id=persona_id,
            scores={
                "IC": round(ic, 4),
                "EC": round(ec, 4),
                "RC": round(rc, 4),
                "overall": round(overall, 4),
            },
            breakdown=ScoreBreakdown(
                cooperativeness=round(cooperativeness, 4),
                non_contradiction_rate=round(non_contradiction_rate, 4),
                coverage=round(coverage, 4),
                non_refutation_rate=round(non_refutation_rate, 4),
                retest_similarity=round(rc, 4),
            ),
            session_stats=SessionStats(
                total_turns=total_turns,
                contradictions_detected=contradictions,
                claims_extracted=sum(len(analysis.claims) for analysis in analyses),
                claims_refuted=refuted,
                evasive_responses=evasive,
            ),
            turns=turns,
            analyses=analyses,
        )
