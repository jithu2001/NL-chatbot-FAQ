"""Post-generation validation of LLM answers.

Checks, in order:
  1. Strip anything citation-like the model produced (URLs, markdown links,
     "Source:" lines) - citations are attached by the backend only.
  2. Detect "could not verify" answers.
  3. Forbidden content (advice, recommendations, predictions, guarantees).
  4. Numeric grounding - every number in the answer must appear in the
     retrieved context (or the question); otherwise the answer is rejected
     as a possible hallucination.
  5. Maximum length - at most 3 sentences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

MAX_SENTENCES = 3


class Verdict(str, Enum):
    OK = "OK"
    NOT_VERIFIED = "NOT_VERIFIED"
    ADVICE_BLOCKED = "ADVICE_BLOCKED"
    UNGROUNDED = "UNGROUNDED"
    EMPTY = "EMPTY"


@dataclass
class ValidationResult:
    verdict: Verdict
    answer: str
    detail: str = ""


_URL_RE = re.compile(r"(https?://[^\s)\]]+|www\.[^\s)\]]+|\b[a-z0-9-]+\.(com|in|org|gov\.in)(/[^\s)\]]*)?)", re.I)
# Sentences where the model narrates its own source ("This information is from the KIM...").
_SELF_CITATION_RE = re.compile(
    r"^(this|the above|the|that)?\s*(information|data|answer|detail|fact)s?\s+(is|are|was|were|comes?|has been)\s+"
    r"(from|based on|taken from|sourced from|provided in|mentioned in|stated in|as per)\b"
    r"|^(source|reference)s?\b|^(as per|according to) the [^,]{0,80}(last updated|dated)\b",
    re.I,
)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_SOURCE_LINE_RE = re.compile(r"^\s*(sources?|citations?|references?|last updated)\s*[:\-].*$", re.I | re.M)

_NOT_VERIFIED_RE = re.compile(
    r"(could ?n[o']t|cannot|can ?not|unable to|was not able to|not able to)\s+(be\s+)?(verify|verified|find|found|confirm|locate)"
    r"|not (mentioned|stated|specified|available|provided|found|present|included) in the (provided |supplied |retrieved )?(context|documents?|sources?)"
    r"|(context|documents?|sources?) (does|do) not (contain|mention|state|specify|provide|include)"
    r"|no information (is |was )?(available|provided|found)",
    re.I,
)

_FORBIDDEN_PATTERNS = [
    r"\byou (should|must|could|may want to|might want to|can consider|may consider|ought to)\b.{0,40}\b(invest|buy|sell|hold|redeem|consider|choose|switch|opt|go for)",
    r"\b(i|we) (would )?(strongly )?(recommend|suggest|advise|advice)",
    r"\b(is|are|makes it) (a )?(good|great|excellent|wise|smart|safe|ideal) (investment|choice|option|fund|bet)",
    r"\bbest (fund|scheme|option|choice|investment|performing)",
    r"\bguaranteed? (returns?|income|profit)",
    r"\bexpected (returns?|gains?|profit)",
    r"\bfuture (returns?|performance|gains?)",
    r"\b(will|is likely to|is expected to|should) (outperform|beat|deliver|generate|give|earn|grow|double|rise)",
    r"\b(buy|sell|redeem) (it|this fund|this scheme|now|today)",
    r"\bworth investing\b",
    r"\bsuitable for you\b",
]
_FORBIDDEN_RE = [re.compile(p, re.I) for p in _FORBIDDEN_PATTERNS]
_NEGATION_RE = re.compile(r"\b(not|no|nor|never|cannot|can't|doesn't|does not|without)\b[^.]{0,25}$", re.I)

_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
}
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:,\d+)*(?:\.\d+)?")

# Abbreviations that end with a period but do not end a sentence.
_ABBREVIATIONS = ("Rs.", "Mr.", "Ms.", "Mrs.", "Dr.", "No.", "Ltd.", "Pvt.", "e.g.", "i.e.",
                  "approx.", "p.a.", "viz.", "etc.", "vs.", "Sr.", "Co.", "Inc.", "u/s.", "Re.")


def _normalise_number(token: str) -> str:
    n = token.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".") or "0"
    return n.lstrip("0") or "0"


def numbers_in(text: str) -> set[str]:
    found = {_normalise_number(m.group(0)) for m in _NUMBER_RE.finditer(text)}
    lowered = text.lower()
    for word, digit in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            found.add(digit)
    return found


def split_sentences(text: str) -> list[str]:
    protected = text
    for i, abbr in enumerate(_ABBREVIATIONS):
        protected = re.sub(r"(?<![A-Za-z])" + re.escape(abbr), f"§{i}§", protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9₹\"'(§])", protected.strip())
    restored = []
    for part in parts:
        for i, abbr in enumerate(_ABBREVIATIONS):
            part = part.replace(f"§{i}§", abbr)
        if part.strip():
            restored.append(part.strip())
    return restored


def _flatten_lines(text: str) -> str:
    """Turn a multi-line answer into prose: drop source-narration lines and
    join bullet items with semicolons so they stay one readable sentence."""
    out: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if bullets:
            joined = "; ".join(b.rstrip(".;,") for b in bullets) + "."
            if out and out[-1].endswith(":"):
                out[-1] = out[-1] + " " + joined
            else:
                out.append(joined)
            bullets.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _SELF_CITATION_RE.search(line) and not re.search(r"\d+(\.\d+)?%|₹", line):
            continue
        m = re.match(r"^([-•*]|\d+[.)])\s+(.*)$", line)
        if m:
            bullets.append(m.group(2).strip())
            continue
        flush()
        out.append(line)
    flush()
    return " ".join(out)


def strip_citations(text: str) -> str:
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _SOURCE_LINE_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = re.sub(r"\(\s*(and|or|,)?\s*\)", "", text)
    text = re.sub(r"\[\d+(,\s*\d+)*\]", "", text)  # "[1]" style passage references
    text = re.sub(r"[*_#`>]+(?=\S)|(?<=\S)[*_#`]+", "", text)  # markdown emphasis / headings
    # Echoed context labels, e.g. "(Context - Page 4, Last updated: 2026-08-31)".
    text = re.sub(r"\((?=[^)]*\b(page|last updated|context|passage|document)\b)[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"\[(?=[^\]]*\b(page|last updated|context|passage|document)\b)[^\]]*\]", "", text, flags=re.I)
    text = _flatten_lines(text)
    text = text.replace(":;", ":").replace(";;", ";")
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_forbidden(text: str) -> str | None:
    for rx in _FORBIDDEN_RE:
        for m in rx.finditer(text):
            before = text[max(0, m.start() - 40) : m.start()]
            if _NEGATION_RE.search(before):
                continue  # e.g. "does not guarantee returns" is a factual disclaimer
            return m.group(0)
    return None


def validate_answer(answer: str, context: str, question: str = "") -> ValidationResult:
    cleaned = strip_citations(answer or "")
    # Drop sentences where the model narrates its own source; citations are
    # attached by the backend.
    sentences = [s for s in split_sentences(cleaned) if not _SELF_CITATION_RE.search(s)]
    cleaned = " ".join(sentences)
    if not cleaned:
        return ValidationResult(Verdict.EMPTY, "", "empty answer")

    if _NOT_VERIFIED_RE.search(cleaned):
        return ValidationResult(Verdict.NOT_VERIFIED, cleaned, "model could not verify the fact")

    bad = find_forbidden(cleaned)
    if bad:
        return ValidationResult(Verdict.ADVICE_BLOCKED, cleaned, f"forbidden phrase: {bad!r}")

    allowed = numbers_in(context) | numbers_in(question)
    unsupported = sorted(n for n in numbers_in(cleaned) - allowed)
    if unsupported:
        return ValidationResult(Verdict.UNGROUNDED, cleaned, f"numbers not in context: {unsupported}")

    if len(sentences) > MAX_SENTENCES:
        cleaned = " ".join(sentences[:MAX_SENTENCES])
    return ValidationResult(Verdict.OK, cleaned)
