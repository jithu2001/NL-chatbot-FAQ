"""The end-to-end answer pipeline.

Question -> PII check -> classification -> retrieval -> relevance check
-> context construction -> LLM (Groq or Ollama) -> answer validation -> citation
attachment -> response.

The LLM only ever produces answer text. The source shown to the user is
always chosen by this module from ChromaDB metadata / the source registry.
"""

from __future__ import annotations

import logging
import re

from app.classifier.question_classifier import REASON_PREDICTION, Classification, classify
from app.core.catalog import detect_scheme
from app.core.config import get_settings
from app.core.sources import Source, find_source, registry
from app.llm import provider
from app.models.schemas import ChatResponse, SourceInfo
from app.prompts.system_prompt import NOT_VERIFIED_MESSAGE, build_system_prompt
from app.rag import vector_store
from app.rag.retriever import RetrievalResult, ScoredChunk, key_terms, lexical_coverage, retrieve
from app.safety.answer_validator import Verdict, numbers_in, validate_answer
from app.safety.pii_detector import PII_REFUSAL

# Never log question text: only classifications and verdicts.
log = logging.getLogger("powerup.pipeline")


ADVICE_MESSAGE = (
    "I can provide factual information about {subject}, but I can't recommend whether you should "
    "buy, sell, or invest. You can review the official scheme documents for factual information."
)
PREDICTION_MESSAGE = (
    "I can't predict future returns. I can provide factual information about the scheme, such as its "
    "expense ratio, benchmark, riskometer, and published official documents."
)
PERFORMANCE_MESSAGE = (
    "I can't provide, rank, or compare return figures or fund performance. I can provide factual "
    "information about the scheme, such as its expense ratio, benchmark, riskometer, and published "
    "official documents."
)
ADVICE_BLOCKED_MESSAGE = (
    "I can only share factual information from official scheme documents and can't offer investment advice."
)


class KnowledgeBaseEmptyError(RuntimeError):
    pass


def _source_from_meta(meta: dict) -> SourceInfo:
    # Re-resolve through the registry so the URL always comes from sources.csv.
    src = registry().get(meta.get("source_id", ""))
    if src is None:
        raise RuntimeError("chunk references an unknown source")
    page = meta.get("page")
    return SourceInfo(
        title=src.title, url=src.url, source_type=src.source_type, authority=src.authority,
        last_updated=src.last_updated, retrieved_date=src.retrieved_date,
        page=int(page) if isinstance(page, (int, float)) and page > 0 else None,
    )


def _source_from_registry(src: Source) -> SourceInfo:
    return SourceInfo(
        title=src.title, url=src.url, source_type=src.source_type, authority=src.authority,
        last_updated=src.last_updated, retrieved_date=src.retrieved_date,
    )


def _response(answer: str, classification: Classification, source: SourceInfo | None = None,
              scheme: str | None = None, defaulted: bool = False) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        classification=classification.value,
        source=source,
        last_updated=source.last_updated if source else None,
        retrieved_date=source.retrieved_date if source else None,
        scheme=scheme,
        scheme_defaulted=defaulted,
    )


def _strip_chunk_header(text: str) -> str:
    # Chunks are stored as "Document: ...\nScheme: ...\nPage: N\n\n<body>".
    head, sep, body = text.partition("\n\n")
    return body if sep and head.startswith("Document:") else text


EXPAND_TOP_N = 3  # top hits that get their neighbouring chunks added ("small-to-big")


def expand_with_neighbors(chunks: list[ScoredChunk]) -> dict[str, str]:
    """Return chunk id -> body text, where the top hits include the adjacent
    chunks from the same page. Small chunks retrieve precisely; the neighbours
    restore facts split across a chunk boundary (e.g. a list of fund managers).
    Chunks swallowed into a neighbour's window are dropped."""
    bodies: dict[str, str] = {}
    covered: set[str] = set()
    for rank, c in enumerate(chunks):
        if c.chunk.id in covered:
            continue
        body = _strip_chunk_header(c.text)
        if rank < EXPAND_TOP_N:
            neighbors = vector_store.get_neighbors(c.metadata)
            if neighbors:
                index = c.metadata["chunk_index"]
                pieces = {**{i: _strip_chunk_header(t) for i, t in neighbors.items()}, index: body}
                body = "\n".join(pieces[i] for i in sorted(pieces))
                source_id = c.metadata["source_id"]
                covered.update(f"{source_id}-chunk-{i:04d}" for i in pieces)
        covered.add(c.chunk.id)
        bodies[c.chunk.id] = body
    return bodies


def build_context(chunks: list[ScoredChunk], bodies: dict[str, str] | None = None) -> str:
    parts = []
    for c in chunks:
        if bodies is not None and c.chunk.id not in bodies:
            continue
        m = c.metadata
        label = f"[{len(parts) + 1}] {m.get('title')} | Scheme: {m.get('scheme')}"
        if m.get("page"):
            label += f" | Page {m['page']}"
        label += f" | Last updated: {m.get('last_updated', 'Not specified')}"
        body = bodies[c.chunk.id] if bodies is not None else _strip_chunk_header(c.text)
        parts.append(f"{label}\n{body}")
    return "\n\n---\n\n".join(parts)


def select_source(chunks: list[ScoredChunk], answer: str, bodies: dict[str, str] | None = None) -> ScoredChunk:
    """Pick the single chunk that best supports the generated answer.

    Criteria: retrieval rank (relevance + authority/scheme preference), how
    many of the answer's numbers the chunk contains, and word overlap with
    the answer; ties go to the most recently updated document.
    """
    answer_numbers = numbers_in(answer)
    answer_terms = key_terms(answer)

    candidates = [c for c in chunks if bodies is None or c.chunk.id in bodies]

    def score(c: ScoredChunk) -> tuple[float, str]:
        body = bodies[c.chunk.id] if bodies is not None else _strip_chunk_header(c.text)
        num_support = (len(answer_numbers & numbers_in(body)) / len(answer_numbers)) if answer_numbers else 0.0
        overlap = lexical_coverage(answer_terms, body) if answer_terms else 0.0
        recency = c.metadata.get("last_updated", "")
        recency = recency if re.fullmatch(r"\d{4}-\d{2}-\d{2}", recency) else "0000-00-00"
        return (c.rank_score + 0.35 * num_support + 0.35 * overlap, recency)

    return max(candidates or chunks, key=score)


def _advice_source(scheme: str | None) -> SourceInfo | None:
    """One official educational source: the scheme's KIM, else AMFI investor education."""
    src = find_source(scheme=scheme, source_type="Key Information Memorandum") if scheme else None
    src = src or find_source(title_contains="Risks in Mutual Funds")
    return _source_from_registry(src) if src else None


def _unsupported_source() -> SourceInfo | None:
    """The official factsheet - where the AMC publishes its mandated disclosures."""
    src = find_source(source_type="AMC Factsheet")
    return _source_from_registry(src) if src else None


def _question_for_llm(result: RetrievalResult) -> str:
    q = result.question
    if result.scheme and result.scheme.lower() not in q.lower():
        q += f" (This question is about {result.scheme}.)"
    if result.topic and result.topic.answer_hint:
        q += f"\nAnswer guidance: {result.topic.answer_hint}"
    return q


async def answer_question(question: str, scheme_hint: str | None = None) -> ChatResponse:
    settings = get_settings()
    cls = classify(question)
    log.info("classified question as %s", cls.label.value)

    if cls.label is Classification.PII:
        # Stop immediately: nothing is embedded, sent to Ollama, or logged.
        return _response(PII_REFUSAL, Classification.PII)

    scheme_named = detect_scheme(question) or scheme_hint

    if cls.label is Classification.ADVICE:
        subject = scheme_named or "these schemes"
        return _response(ADVICE_MESSAGE.format(subject=subject), Classification.ADVICE,
                         _advice_source(scheme_named), scheme=scheme_named)

    if cls.label is Classification.UNSUPPORTED:
        message = PREDICTION_MESSAGE if cls.reason == REASON_PREDICTION else PERFORMANCE_MESSAGE
        return _response(message, Classification.UNSUPPORTED, _unsupported_source(), scheme=scheme_named)

    # ---- FACTUAL: retrieval-augmented generation -------------------------
    if vector_store.count() == 0:
        raise KnowledgeBaseEmptyError("the vector store is empty")

    result = await retrieve(question, scheme_hint=scheme_hint)
    if not result.is_relevant():
        # Retrieval failed the relevance check: do NOT call Ollama.
        log.info("retrieval below relevance threshold")
        return _response(NOT_VERIFIED_MESSAGE, Classification.FACTUAL, scheme=result.scheme,
                         defaulted=result.scheme_was_defaulted)

    # Only chunks that individually pass the relevance check become context.
    context_chunks = [c for c in result.chunks if c.relevance >= settings.relevance_threshold]
    topic = result.topic
    if topic and topic.prefer_latest:
        # Monthly-changing facts: use only the latest authoritative document
        # when it has relevant passages (avoids stale KIM/SID values).
        latest = [c for c in context_chunks if c.metadata.get("source_type") in topic.preferred_source_types]
        context_chunks = latest or context_chunks
    bodies = expand_with_neighbors(context_chunks)
    context = build_context(context_chunks, bodies)

    llm_question = _question_for_llm(result)
    raw = await provider.chat(system=build_system_prompt(llm_question, context), user=llm_question)
    validation = validate_answer(raw, context, question)
    log.info("answer validation verdict: %s", validation.verdict.value)

    if validation.verdict is Verdict.OK:
        best = select_source(context_chunks, validation.answer, bodies)
        return _response(validation.answer, Classification.FACTUAL, _source_from_meta(best.metadata),
                         scheme=result.scheme, defaulted=result.scheme_was_defaulted)

    if validation.verdict is Verdict.ADVICE_BLOCKED:
        return _response(ADVICE_BLOCKED_MESSAGE, Classification.FACTUAL,
                         _source_from_meta(result.best.metadata), scheme=result.scheme,
                         defaulted=result.scheme_was_defaulted)

    # NOT_VERIFIED / UNGROUNDED / EMPTY: never show an unsupported answer.
    return _response(NOT_VERIFIED_MESSAGE, Classification.FACTUAL, _source_from_meta(result.best.metadata),
                     scheme=result.scheme, defaulted=result.scheme_was_defaulted)
