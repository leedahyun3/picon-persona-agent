from __future__ import annotations

from pathlib import Path

from picon_eval.models import PersonaProfile
from picon_eval.orchestrator import Orchestrator
from picon_eval.utils import load_json
import json


ROOT = Path(__file__).resolve().parent.parent


def load_profile(name: str = "stress_test_persona.json") -> PersonaProfile:
    payload = load_json(ROOT / "personas" / name)
    return PersonaProfile(**payload)


def run_demo():
    profile = load_profile()
    orchestrator = Orchestrator(profile)
    result = orchestrator.run_session()
    output_dir = ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)
    latest_path = output_dir / "latest_eval.json"
    latest_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result
