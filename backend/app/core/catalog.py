"""Static catalogue of the selected AMCs, their schemes and the FAQ topics.

Scheme and topic detection are deliberately rule-based: they are
deterministic, fast, easy to test and never need to send the user's
question anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PPFAS = "PPFAS Mutual Fund"
HDFC = "HDFC Mutual Fund"
AMCS: tuple[str, ...] = (PPFAS, HDFC)

# Words that identify a fund house in a question.
AMC_KEYWORDS: dict[str, tuple[str, ...]] = {
    PPFAS: ("parag parikh", "ppfas", "parag"),
    HDFC: ("hdfc",),
}

# Official website hosts per AMC (used to tag general pages with their AMC).
AMC_HOSTS: dict[str, tuple[str, ...]] = {
    PPFAS: ("amc.ppfas.com",),
    HDFC: ("www.hdfcfund.com", "hdfcfund.com", "files.hdfcfund.com"),
}


@dataclass(frozen=True)
class Scheme:
    name: str
    amc: str
    category: str
    # Category phrases that identify the scheme within its AMC.
    category_aliases: tuple[str, ...]
    # Codes / former names that identify this exact scheme on their own.
    unique_aliases: tuple[str, ...] = ()


SCHEMES: tuple[Scheme, ...] = (
    Scheme("Parag Parikh Flexi Cap Fund", PPFAS, "Flexi Cap (Equity)",
           ("flexi cap", "flexicap", "flexi-cap"), ("ppfcf", "long term equity fund")),
    Scheme("Parag Parikh Large Cap Fund", PPFAS, "Large Cap (Equity)",
           ("large cap", "largecap", "large-cap"), ("pplcf",)),
    Scheme("Parag Parikh ELSS Tax Saver Fund", PPFAS, "ELSS (Equity Linked Savings Scheme)",
           ("elss", "tax saver", "tax-saver", "tax saving"), ("pptsf",)),
    Scheme("Parag Parikh Liquid Fund", PPFAS, "Liquid (Debt)",
           ("liquid",), ("pplf",)),
    Scheme("Parag Parikh Conservative Hybrid Fund", PPFAS, "Conservative Hybrid",
           ("conservative hybrid", "hybrid"), ("ppchf",)),
    Scheme("HDFC Flexi Cap Fund", HDFC, "Flexi Cap (Equity)",
           ("flexi cap", "flexicap", "flexi-cap"), ("hdfc equity fund",)),
    Scheme("HDFC Large Cap Fund", HDFC, "Large Cap (Equity)",
           ("large cap", "largecap", "large-cap"), ("hdfc top 100",)),
    Scheme("HDFC Mid Cap Fund", HDFC, "Mid Cap (Equity)",
           ("mid cap", "midcap", "mid-cap"), ("hdfc mid-cap opportunities", "hdfc mid cap opportunities")),
    Scheme("HDFC ELSS Tax Saver Fund", HDFC, "ELSS (Equity Linked Savings Scheme)",
           ("elss", "tax saver", "tax-saver", "tax saving"), ("hdfc taxsaver",)),
    Scheme("HDFC Liquid Fund", HDFC, "Liquid (Debt)",
           ("liquid",)),
)

SCHEME_NAMES: tuple[str, ...] = tuple(s.name for s in SCHEMES)
_SCHEME_BY_NAME = {s.name: s for s in SCHEMES}

# Default scheme per AMC when a scheme-specific question names only the AMC.
AMC_DEFAULT_SCHEME: dict[str, str] = {PPFAS: "Parag Parikh Flexi Cap Fund", HDFC: "HDFC Flexi Cap Fund"}

# Any "<AMC> ... Fund" heading that is not an in-scope scheme is skipped during
# ingestion (multi-scheme factsheets cover dozens of other schemes).
_OTHER_SCHEME_HEADING = re.compile(r"\b(parag parikh|hdfc)\b.{0,60}\b(fund|fof|etf|plan|index)\b", re.I)


def get_scheme(name: str | None) -> Scheme | None:
    return _SCHEME_BY_NAME.get(name) if name else None


def amc_of_scheme(name: str | None) -> str | None:
    scheme = get_scheme(name)
    return scheme.amc if scheme else None


def amc_for_host(host: str) -> str | None:
    for amc, hosts in AMC_HOSTS.items():
        if host in hosts:
            return amc
    return None


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

_TOPIC_BY_NAME = {t.name: t for t in TOPICS}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def detect_amc(question: str) -> str | None:
    q = _norm(question)
    found = [amc for amc, words in AMC_KEYWORDS.items() if any(re.search(rf"\b{re.escape(w)}\b", q) for w in words)]
    return found[0] if len(found) == 1 else None


def scheme_candidates(question: str) -> list[str]:
    """All in-scope schemes the question could refer to (empty if none).

    A full scheme name or unique alias wins outright. Otherwise category words
    ("flexi cap", "ELSS", "liquid") match every AMC's scheme of that category,
    narrowed to one AMC when the question names the fund house.
    """
    q = _norm(question)
    squashed = _squash(question)
    exact = [s.name for s in SCHEMES
             if _squash(s.name) in squashed or any(re.search(rf"\b{re.escape(a)}\b", q) for a in s.unique_aliases)]
    if exact:
        return exact[:1]
    amc = detect_amc(question)
    matches = [s.name for s in SCHEMES
               if any(re.search(rf"\b{re.escape(a)}\b", q) for a in s.category_aliases)
               and (amc is None or s.amc == amc)]
    # "large and mid cap" should not also count as "large cap" + "mid cap".
    return list(dict.fromkeys(matches))


def detect_scheme(question: str) -> str | None:
    """The single scheme the question refers to, or None (none or ambiguous)."""
    candidates = scheme_candidates(question)
    return candidates[0] if len(candidates) == 1 else None


def detect_topic(question: str) -> Topic | None:
    q = _norm(question)
    for topic in TOPICS:
        if any(re.search(p, q) for p in topic.patterns):
            return topic
    return None


def get_topic(name: str | None) -> Topic | None:
    return _TOPIC_BY_NAME.get(name) if name else None


def find_scheme_in_text(text: str, head_chars: int = 400) -> str | None:
    """Detect which scheme a document page is about from its heading text.

    Returns the in-scope scheme name, "OUT_OF_SCOPE" for any other scheme of
    the AMCs, or None when the heading names no scheme.
    """
    head = text[:head_chars]
    squashed = _squash(head)
    best: tuple[int, str] | None = None
    for name in SCHEME_NAMES:
        idx = squashed.find(_squash(name))
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, name)
    if best is not None:
        return best[1]
    if _OTHER_SCHEME_HEADING.search(head):
        return "OUT_OF_SCOPE"
    return None
