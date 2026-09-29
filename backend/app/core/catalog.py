"""Static catalogue of the selected AMC, its schemes and the FAQ topics.

Scheme and topic detection are deliberately rule-based: they are
deterministic, fast, easy to test and never need to send the user's
question anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scheme:
    name: str
    category: str
    aliases: tuple[str, ...]


SCHEMES: tuple[Scheme, ...] = (
    Scheme(
        "Parag Parikh Flexi Cap Fund",
        "Flexi Cap (Equity)",
        ("flexi cap", "flexicap", "flexi-cap", "ppfcf", "long term equity"),
    ),
    Scheme(
        "Parag Parikh Large Cap Fund",
        "Large Cap (Equity)",
        ("large cap fund", "largecap", "large-cap fund", "pplcf", "large cap scheme"),
    ),
    Scheme(
        "Parag Parikh ELSS Tax Saver Fund",
        "ELSS (Equity Linked Savings Scheme)",
        ("elss", "tax saver", "tax-saver", "tax saving fund", "pptsf"),
    ),
    Scheme(
        "Parag Parikh Liquid Fund",
        "Liquid (Debt)",
        ("liquid fund", "liquid scheme", "pplf"),
    ),
    Scheme(
        "Parag Parikh Conservative Hybrid Fund",
        "Conservative Hybrid",
        ("conservative hybrid", "hybrid fund", "ppchf"),
    ),
)

SCHEME_NAMES: tuple[str, ...] = tuple(s.name for s in SCHEMES)

# Schemes that appear in multi-scheme documents but are NOT part of this
# assistant's scope. Pages about them are skipped during ingestion.
OUT_OF_SCOPE_SCHEMES: tuple[str, ...] = (
    "Parag Parikh Arbitrage Fund",
    "Parag Parikh Dynamic Asset Allocation Fund",
)


@dataclass(frozen=True)
class Topic:
    name: str
    patterns: tuple[str, ...]
    # Extra words appended to the retrieval query to pull the right section.
    expansion: str = ""
    # General topics (statements, CAS...) are not tied to a scheme.
    general: bool = False
    # Source types that are most authoritative for this topic (for ranking).
    preferred_source_types: tuple[str, ...] = field(default_factory=tuple)
    # Values that change monthly: when the preferred (latest) source has
    # relevant passages, only those passages are used as context.
    prefer_latest: bool = False
    # Short topic-specific guidance added to the generation prompt.
    answer_hint: str = ""


# Order matters: more specific topics first.
TOPICS: tuple[Topic, ...] = (
    Topic(
        "capital gains statement",
        (r"capital[\s-]*gains?", r"\bcg statement"),
        "Capital Gain/Loss Statement request statements account statement",
        general=True,
        preferred_source_types=("AMC Investor Services",),
    ),
    Topic(
        "CAS",
        (r"\bcas\b", r"consolidated account statement", r"e-?cas"),
        "Consolidated Account Statement CAS CAMS KFintech",
        general=True,
        preferred_source_types=("AMFI Investor Education", "AMFI Investor Services"),
    ),
    Topic(
        "tax document",
        (r"tax (document|statement|proof|certificate)", r"form 16", r"\b80c\b"),
        "tax statement account statement tax benefits",
        general=True,
        preferred_source_types=("AMC Investor Services", "AMC Scheme Page"),
    ),
    Topic(
        "statement",
        (r"\bstatements?\b",),
        "Account Statement request statements",
        general=True,
        preferred_source_types=("AMC Investor Services",),
    ),
    Topic(
        "expense ratio",
        (r"expense ratio", r"\bter\b", r"total expense", r"\bexpenses?\b", r"\bfees?\b"),
        "Expense Ratio Regular Plan Direct Plan Base Expense Ratio TER",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="Report the scheme's current Total Expense Ratio (base expense ratio) for the Regular Plan and the Direct Plan exactly as stated, in one sentence such as: 'The expense ratio of <scheme> is <x>% for the Regular Plan and <y>% for the Direct Plan.' Do not list the regulatory maximum expense slabs.",
    ),
    Topic(
        "exit load",
        (r"exit[\s-]*load", r"\bload\b", r"redemption (charge|fee)", r"exit (fee|charge)"),
        "Exit Load Load Structure redeemed from the date of allotment",
        preferred_source_types=("AMC Factsheet", "Key Information Memorandum"),
        answer_hint="Summarise the exit load structure in at most 3 short sentences, keeping every percentage and day/period exactly as stated.",
    ),
    Topic(
        "lock-in",
        (r"lock[\s-]*in", r"\blocked\b", r"lockin"),
        "lock-in period three years 3 years from the date of allotment ELSS",
        preferred_source_types=("Key Information Memorandum", "Scheme Information Document"),
        answer_hint="State the lock-in period exactly as stated in the context.",
    ),
    Topic(
        "minimum SIP",
        (r"\bsip\b", r"systematic investment"),
        "Minimum Investment SIP Amount Monthly SIP Quarterly SIP",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="State the minimum SIP amounts (monthly and quarterly, if given) exactly as stated, in one sentence such as: 'The minimum SIP for <scheme> is <amount> per month (monthly SIP) and <amount> per quarter (quarterly SIP).'",
    ),
    Topic(
        "minimum investment",
        (
            r"minimum (investment|amount|application|purchase|lump ?sum)",
            r"min(\.|imum)? invest",
            r"lump ?sum",
            r"how much .*(invest|start)",
        ),
        "Minimum Investment Lump Sum Amount New Purchase Minimum Application Amount",
        preferred_source_types=("AMC Factsheet", "Key Information Memorandum"),
        prefer_latest=True,
        answer_hint="State the minimum lump-sum (new purchase) amount exactly as stated; add the minimum SIP only if it is given.",
    ),
    Topic(
        "riskometer",
        (r"risk[\s-]*o?[\s-]*meter", r"risk (level|category|profile|grade)", r"how risky", r"\brisk\b"),
        "Riskometer The risk of the scheme is",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="State the scheme's riskometer level exactly as stated (for example: 'The risk of the scheme is ...').",
    ),
    Topic(
        "benchmark",
        (r"bench[\s-]*mark", r"\bindex\b"),
        "Benchmark Name TRI Index",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="State the benchmark index name exactly as stated.",
    ),
    Topic(
        "scheme objective",
        (r"objective", r"\baim\b", r"what does .* invest", r"type of scheme", r"what kind of (fund|scheme)"),
        "Investment Objective Type of Scheme",
        preferred_source_types=("AMC Factsheet", "Key Information Memorandum"),
    ),
    Topic(
        "fund manager",
        (r"fund managers?", r"who manages", r"managed by"),
        "Name of the Fund Managers Managing Since",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="List the fund managers' names as stated in the most recent document.",
    ),
    Topic(
        "NAV",
        (r"\bnav\b", r"net asset value"),
        "NAV as on Direct Plan Growth Regular Plan Growth",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="Give the NAV values with their plan/option names and the 'as on' date exactly as stated.",
    ),
    Topic(
        "AUM",
        (r"\baum\b", r"assets under management", r"fund size", r"corpus size"),
        "AUM as on Crores",
        preferred_source_types=("AMC Factsheet",),
        prefer_latest=True,
        answer_hint="Give the AUM figure with its 'as on' date exactly as stated.",
    ),
    Topic(
        "factsheet",
        (r"fact[\s-]*sheets?",),
        "Factsheet downloads monthly factsheet",
        general=True,
        preferred_source_types=("AMC Downloads Page",),
    ),
    Topic(
        "scheme documents",
        (r"\bsid\b", r"\bkim\b", r"\bsai\b", r"scheme information document", r"key information memorandum", r"offer document"),
        "KIM SID SAI Scheme Information Document Key Information Memorandum",
        general=True,
        preferred_source_types=("AMC Downloads Page",),
    ),
)



def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def detect_scheme(question: str) -> str | None:
    """Return the canonical scheme name mentioned in the question, if any."""
    q = _norm(question)
    for scheme in SCHEMES:
        if scheme.name.lower() in q:
            return scheme.name
    for scheme in SCHEMES:
        if any(alias in q for alias in scheme.aliases):
            return scheme.name
    # Bare category words ("the large cap", "hybrid", "liquid") as a fallback.
    fallbacks = {
        "large cap": "Parag Parikh Large Cap Fund",
        "liquid": "Parag Parikh Liquid Fund",
        "hybrid": "Parag Parikh Conservative Hybrid Fund",
    }
    for word, name in fallbacks.items():
        if re.search(rf"\b{word}\b", q):
            return name
    return None


def detect_topic(question: str) -> Topic | None:
    q = _norm(question)
    for topic in TOPICS:
        if any(re.search(p, q) for p in topic.patterns):
            return topic
    return None


def find_scheme_in_text(text: str, head_chars: int = 400) -> str | None:
    """Detect which scheme a document page is about by looking at its heading area.

    Returns the in-scope scheme name, "OUT_OF_SCOPE" for other schemes of the
    AMC, or None when no scheme heading is found.
    """
    head = _norm(text[:head_chars])
    best: tuple[int, str] | None = None
    for name in SCHEME_NAMES + OUT_OF_SCOPE_SCHEMES:
        idx = head.find(name.lower())
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, name)
    if best is None:
        return None
    return best[1] if best[1] in SCHEME_NAMES else "OUT_OF_SCOPE"
