from __future__ import annotations

from typing import List

from picon_eval.models import Claim, Evidence, PersonaProfile


class ReferenceSearchBackend:
    def __init__(self, profile: PersonaProfile) -> None:
        self.profile = profile

    def verify(self, claim: Claim) -> Evidence:
        for fact in self.profile.public_facts:
            if fact["claim"] == claim.text:
                return Evidence(
                    claim=claim.text,
                    label=fact["label"],
                    evidence=fact["evidence"],
                )

        if claim.category in {"location", "affiliation", "role"}:
            return Evidence(
                claim=claim.text,
                label="SUPPORTED",
                evidence=f"Reference KB inferred support for '{claim.entity}'.",
            )

        if claim.category == "number":
            return Evidence(
                claim=claim.text,
                label="UNVERIFIABLE",
                evidence="Public evidence is insufficient for a private team-size statement.",
            )

        return Evidence(
            claim=claim.text,
            label="UNVERIFIABLE",
            evidence="No matching evidence found in the reference knowledge base.",
        )
