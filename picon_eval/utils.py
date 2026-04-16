from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable, List, Sequence, Set


STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "are", "i", "my", "to", "of",
    "in", "on", "at", "for", "with", "it", "this", "that", "입니다", "그리고",
    "저는", "제가", "있습니다", "하는", "하고", "현재", "가장", "최근", "입니다."
}


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def harmonic_mean(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return 2 * a * b / (a + b)


def tokenize(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[A-Za-z0-9가-힣]+", text.lower()) if tok not in STOPWORDS]


def semantic_similarity(a: str, b: str) -> float:
    set_a = set(tokenize(a))
    set_b = set(tokenize(b))
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    jaccard = inter / union
    len_bias = min(len(set_a), len(set_b)) / max(len(set_a), len(set_b))
    return round(0.7 * jaccard + 0.3 * len_bias, 4)


def contains_any(text: str, keywords: Sequence[str]) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in keywords)
