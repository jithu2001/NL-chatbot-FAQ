"""Retrieval: scheme/topic-aware vector search + hybrid re-ranking.

1. Detect scheme and topic in the question.
2. Embed an expanded query (fastembed or Ollama, per EMBEDDING_PROVIDER).
3. Query ChromaDB with a metadata filter on scheme (plus general documents).
4. Re-rank a wider candidate pool with a hybrid relevance score:
       relevance = 0.5 * semantic cosine similarity
                 + 0.5 * lexical coverage of the question's key terms
   Raw cosine similarity alone does not separate "relevant" from "unrelated"
   well for short FAQ questions, so the relevance threshold
   (RELEVANCE_THRESHOLD) is applied to this hybrid score.
5. Return the top-K chunks with their relevance; the caller decides whether
   the best one clears the threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.catalog import Topic, detect_scheme, detect_topic
from app.core.config import get_settings
from app.rag import vector_store
from app.rag.embeddings import embed_query
from app.rag.vector_store import RetrievedChunk

SEMANTIC_WEIGHT = 0.5
LEXICAL_WEIGHT = 0.5
CANDIDATE_POOL = 25
PREFERRED_SOURCE_BOOST = 0.06
SCHEME_MATCH_BOOST = 0.03

_STOPWORDS = set(
    ["a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "for", "to", "in", "on", "at", "by", "with", "from", "and", "or", "not", "no", "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "do", "does", "did", "can", "could", "should", "would", "will", "i", "me", "my", "mine", "we", "our", "you", "your", "it", "its", "this", "that", "these", "those", "there", "here", "any", "some", "about", "tell", "please", "much", "many", "get", "give", "show", "find", "know", "need", "want", "fund", "funds", "scheme", "schemes", "mutual", "parag", "parikh", "ppfas", "mf", "plan"]
)

# Small synonym map so paraphrases still count as lexical matches.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "ter": ("expense", "ter"),
    "expense": ("expense", "ter"),
    "lockin": ("lock", "lockin"),
    "lock": ("lock", "lockin"),
    "sip": ("sip", "systematic"),
    "cas": ("cas", "consolidated"),
    "riskometer": ("riskometer", "risk"),
    "minimum": ("minimum", "min"),
    "gains": ("gain", "gains"),
    "gain": ("gain", "gains"),
    "download": ("download", "request"),
    "period": ("period", "years", "year"),
}


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("lock-in", "lockin").replace("lock in", "lockin")
    text = text.replace("risk-o-meter", "riskometer")
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text)


def key_terms(question: str) -> list[str]:
    terms = []
    for tok in _tokens(question):
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        if tok.endswith("s") and len(tok) > 4 and tok not in ("gains", "sas"):
            tok = tok[:-1]
        if tok not in terms:
            terms.append(tok)
    return terms


def lexical_coverage(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    words = set(_tokens(text))
    lowered = text.lower()
    hits = 0
    for term in terms:
        variants = _SYNONYMS.get(term, (term,))
        if any(v in words or (len(v) > 4 and v in lowered) for v in variants):
            hits += 1
    return hits / len(terms)


@dataclass
class ScoredChunk:
    chunk: RetrievedChunk
    semantic: float
    lexical: float
    relevance: float
    rank_score: float

    @property
    def metadata(self) -> dict:
        return self.chunk.metadata

    @property
    def text(self) -> str:
        return self.chunk.text


@dataclass
class RetrievalResult:
    question: str
    scheme: str | None
    scheme_was_defaulted: bool
    topic: Topic | None
    chunks: list[ScoredChunk] = field(default_factory=list)

    @property
    def best(self) -> ScoredChunk | None:
        return self.chunks[0] if self.chunks else None

    def is_relevant(self, threshold: float | None = None) -> bool:
        threshold = get_settings().relevance_threshold if threshold is None else threshold
        return self.best is not None and self.best.relevance >= threshold


def resolve_scope(question: str, scheme_hint: str | None = None) -> tuple[str | None, bool, Topic | None]:
    """Work out (scheme, scheme_was_defaulted, topic) for a question."""
    topic = detect_topic(question)
    scheme = detect_scheme(question) or scheme_hint
    defaulted = False
    if scheme is None and topic is not None and not topic.general:
        # Scheme-specific fact without a named scheme: use the configured default
        # scheme and say so explicitly in the answer/UI.
        scheme = get_settings().default_scheme
        defaulted = True
    return scheme, defaulted, topic


def recency_key(meta: dict) -> str:
    """ISO last-updated date for sorting; undated sources sort oldest."""
    value = meta.get("last_updated", "")
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else "0000-00-00"


async def retrieve(question: str, scheme_hint: str | None = None, top_k: int | None = None) -> RetrievalResult:
    settings = get_settings()
    top_k = top_k or settings.top_k
    scheme, defaulted, topic = resolve_scope(question, scheme_hint)

    query_text = question
    if scheme and scheme.lower() not in question.lower():
        query_text += f" ({scheme})"
    if topic and topic.expansion:
        query_text += f" {topic.expansion}"

    embedding = await embed_query(query_text)
    if scheme:
        where = {"scheme": {"$in": [scheme, "General"]}}
    elif topic and topic.general:
        where = {"scheme": "General"}  # investor-service topics live in general documents
    else:
        where = None
    candidates = vector_store.query(embedding, max(CANDIDATE_POOL, top_k * 4), where)

    if topic and topic.preferred_source_types:
        # Metadata-filtered second pass over the topic's authoritative
        # document types, so the right factsheet page is always a candidate.
        type_filter = {"source_type": {"$in": list(topic.preferred_source_types)}}
        scoped = {"$and": [where, type_filter]} if where else type_filter
        seen = {c.id for c in candidates}
        candidates += [c for c in vector_store.query(embedding, CANDIDATE_POOL, scoped) if c.id not in seen]

    terms = key_terms(question)
    if scheme:
        # Named scheme words are matched by the metadata filter, not lexically.
        scheme_words = set(key_terms(scheme))
        terms = [t for t in terms if t not in scheme_words] or terms

    scored: list[ScoredChunk] = []
    for c in candidates:
        lexical = lexical_coverage(terms, c.text)
        relevance = SEMANTIC_WEIGHT * c.similarity + LEXICAL_WEIGHT * lexical
        rank = relevance
        if topic and c.metadata.get("source_type") in topic.preferred_source_types:
            rank += PREFERRED_SOURCE_BOOST
        if scheme and c.metadata.get("scheme") == scheme:
            rank += SCHEME_MATCH_BOOST
        scored.append(ScoredChunk(c, c.similarity, lexical, relevance, rank))

    # Highest rank first; ties broken by the most recently updated document.
    scored.sort(key=lambda s: (round(s.rank_score, 3), recency_key(s.metadata)), reverse=True)
    return RetrievalResult(question, scheme, defaulted, topic, scored[:top_k])
