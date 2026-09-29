"""Rule-based question classifier: FACTUAL / ADVICE / UNSUPPORTED / PII.

Order of checks matters:
  1. PII          - stop immediately, nothing else runs.
  2. UNSUPPORTED  - predictions, return figures, rankings/comparisons.
  3. ADVICE       - buy/sell/hold/choose/suitability questions.
  4. FACTUAL      - everything else goes to retrieval, where the relevance
                    threshold rejects questions the corpus cannot support.

Rules are deterministic, explainable and never send the question to a model,
which matters for the PII and advice guarantees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.safety.pii_detector import detect_pii


class Classification(str, Enum):
    FACTUAL = "FACTUAL"
    ADVICE = "ADVICE"
    UNSUPPORTED = "UNSUPPORTED"
    PII = "PII"


@dataclass(frozen=True)
class ClassificationResult:
    label: Classification
    reason: str


_PREDICTION_PATTERNS = [
    r"\b(will|would|going to|gonna|expected to|likely to|could)\b.{0,40}\b(return|returns|grow|perform|outperform|beat|nav|give|make|earn|yield|rise|fall|crash|double|go up|go down)\b",
    r"\b(predict|prediction|forecast|projection|project(ed)?|estimate)\b",
    r"\b(next|coming|upcoming)\s+(year|month|week|quarter|decade|\d+\s+years?)\b.{0,30}\b(return|nav|performance|price)\b",
    r"\b(return|returns|nav|performance)\b.{0,40}\b(next|coming|future|in \d+ years?)\b",
    r"\bfuture (return|performance|nav|value)s?\b",
    r"\bexpected returns?\b",
    r"\bguarantee[ds]?\b.{0,20}\breturns?\b|\breturns?\b.{0,20}\bguarantee",
    r"\bhow much will\b",
]

# Performance figures, rankings and comparisons.
_PERFORMANCE_PATTERNS = [
    r"\b(highest|best|top|maximum|most)\b.{0,30}\b(return|returns|performing|performance|gain|gains|profit)\b",
    r"\b(compare|comparison|versus|vs\.?|better than|worse than)\b.{0,60}\b(return|returns|performance|perform|fund|funds|scheme)\b",
    r"\b(outperform|underperform|beat the (market|index|benchmark))\b",
    r"\b(rank|ranking|rate|rating)\b.{0,20}\b(fund|funds|scheme|schemes)\b",
    r"\b(how much|what)\b.{0,30}\b(return|returns|cagr|profit)\b",
    r"\b(returns?|cagr|performance)\b.{0,20}\b(of|for|in)\b.{0,40}\b(fund|scheme|year|years)\b",
    r"\bhow (has|did|does)\b.{0,40}\bperform",
    r"\b(calculate|compute)\b.{0,40}\b(return|returns|maturity|corpus|value)\b",
]

_ADVICE_PATTERNS = [
    r"\bshould (i|we)\b",
    r"\b(shall|ought) (i|we)\b",
    r"\bis (it|this|that|now)\b.{0,30}\b(good|right|safe|wise|smart|worth|ideal|suitable|a good time)\b",
    r"\b(worth|good|safe|right|suitable|ideal)\b.{0,20}\b(for me|to invest|investment|to buy)\b",
    r"\b(which|what)\b.{0,20}\b(fund|funds|scheme|schemes|option|plan)\b.{0,30}\b(should|best|better|choose|pick|recommend|suit|go for)\b",
    r"\b(best|better|good|top|safest|recommended)\b.{0,15}\b(fund|funds|scheme|schemes|mutual fund|sip|investment)\b",
    r"\b(recommend|recommendation|suggest|suggestion|advise|advice|tips?)\b",
    r"\b(buy|sell|hold|redeem|exit|switch)\b.{0,10}\b(now|today|right away)\b",
    r"\b(buy|sell|hold|invest)\b\s*(it\s*)?\bor\b\s*(not|buy|sell|hold|wait)\b",
    r"\bhow much (should|do|can|must) (i|we)\b.{0,20}\b(invest|allocate|put)\b",
    r"\b(how (should|do|can) (i|we)|my)\b.{0,20}\b(allocate|allocation|diversify|rebalance)\b",
    r"\b(my savings|my money|my retirement|my goals?)\b",
    r"\bfor me\b",
    r"\bgood (investment|option|choice)\b",
]

_PREDICTION_RE = [re.compile(p, re.I) for p in _PREDICTION_PATTERNS]
_PERFORMANCE_RE = [re.compile(p, re.I) for p in _PERFORMANCE_PATTERNS]

# Reason codes used by the answer pipeline to pick the refusal wording.
REASON_PREDICTION = "prediction"
REASON_PERFORMANCE = "performance"
_ADVICE_RE = [re.compile(p, re.I) for p in _ADVICE_PATTERNS]


def classify(question: str) -> ClassificationResult:
    pii = detect_pii(question)
    if pii:
        return ClassificationResult(Classification.PII, "contains " + ", ".join(pii))

    q = re.sub(r"\s+", " ", question).strip()
    # Advice is checked on "should I ..." style questions first, because
    # "Should I invest for higher returns?" is advice, not a prediction.
    if re.search(r"\bshould (i|we)\b", q, re.I):
        return ClassificationResult(Classification.ADVICE, "asks what the user should do")
    if any(rx.search(q) for rx in _PREDICTION_RE):
        return ClassificationResult(Classification.UNSUPPORTED, REASON_PREDICTION)
    if any(rx.search(q) for rx in _PERFORMANCE_RE):
        return ClassificationResult(Classification.UNSUPPORTED, REASON_PERFORMANCE)
    for rx in _ADVICE_RE:
        if rx.search(q):
            return ClassificationResult(Classification.ADVICE, "asks for a recommendation")
    return ClassificationResult(Classification.FACTUAL, "factual question")
