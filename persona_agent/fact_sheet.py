from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class FactSheetError(ValueError):
    pass


REQUIRED_PATHS = [
    "persona_id",
    "identity.legal_name",
    "identity.display_name",
    "identity.birth_year",
    "identity.birth_place.country",
    "identity.birth_place.city",
    "identity.current_residence.country",
    "identity.current_residence.city",
    "identity.native_language",
    "identity.home_language",
    "family.marital_status",
    "family.parents_cohabitation",
    "family.cat_name",
    "work.current_employer.company_name",
    "work.current_employer.industry",
    "work.current_employer.website",
    "work.current_employer.ceo_name",
    "work.org_structure.job_title",
    "work.org_structure.team_name",
    "work.manager.name",
    "work.office.location_name",
    "work.email_domain",
    "work.employment_start",
    "education.undergraduate.institution_name",
    "education.undergraduate.degree",
    "education.graduate.institution_name",
    "education.graduate.degree",
    "education.highest_education",
    "lifestyle.financial_status",
    "identity.disambiguation",
    "answer_policy.preferred_language",
]


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for token in path.split("."):
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


@dataclass(slots=True)
class FactSheet:
    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "FactSheet":
        file_path = Path(path)
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        sheet = cls(path=file_path, data=payload)
        sheet.validate()
        return sheet

    def validate(self) -> None:
        for path in REQUIRED_PATHS:
            value = self.get(path)
            if value is None or value == "" or value == []:
                raise FactSheetError(f"Missing required fact sheet field: {path}")

    def get(self, slot_path: str, default: Any = None) -> Any:
        value = _get_path(self.data, slot_path)
        return default if value is None else value

    @property
    def persona_id(self) -> str:
        return str(self.data["persona_id"])

    @property
    def display_name(self) -> str:
        return str(self.get("identity.display_name"))
