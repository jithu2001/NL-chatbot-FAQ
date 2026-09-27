#!/usr/bin/env python
"""Run the evaluation set (evaluation/sample_qa.csv) against the live pipeline.

Requires the configured LLM (Groq key or Ollama) and the index built
(python scripts/ingest_sources.py).

    python evaluation/run_eval.py              # prints a summary, writes evaluation/results/
    python evaluation/run_eval.py --ids 1 6 11 # run a subset

Metrics
  classification  predicted label == expected label
  retrieval       an expected source is among the top-K retrieved chunks (factual, answerable)
  citation        the cited source is one of the expected sources
  answer          every expected fact (";"-separated, "|" = alternatives) is in the answer
  grounded        every number in the answer appears on the cited source page(s)
  refusal         advice / unsupported / PII questions got the safe response, no LLM call
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.sources import registry  # noqa: E402
from app.rag import vector_store  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402
from app.safety.answer_validator import numbers_in  # noqa: E402
from app.services import answer_pipeline  # noqa: E402

REFUSAL_PREFIXES = {
    "ADVICE": "I can provide factual information about",
    "UNSUPPORTED": "I can't",
    "PII": "Please don't share personal",
}


def _contains_all(answer: str, spec: str) -> bool:
    a = answer.lower().replace("’", "'")
    for item in filter(None, (s.strip() for s in spec.split(";"))):
        if not any(alt.strip().lower() in a for alt in item.split("|")):
            return False
    return True


def _source_id_for(url: str | None) -> str | None:
    for sid, src in registry().items():
        if src.url == url:
            return sid
    return None


def _cited_text(source_id: str, page: int | None) -> str:
    where = {"source_id": source_id} if page is None else {"$and": [{"source_id": source_id}, {"page": page}]}
    res = vector_store.get_collection().get(where=where, include=["documents"])
    return "\n".join(res.get("documents") or [])


async def evaluate(rows: list[dict]) -> list[dict]:
    calls = {"n": 0}
    original_chat = answer_pipeline.provider.chat

    async def counting_chat(*a, **kw):
        calls["n"] += 1
        return await original_chat(*a, **kw)

    answer_pipeline.provider.chat = counting_chat
    results = []
    for row in rows:
        calls["n"] = 0
        t0 = time.perf_counter()
        resp = await answer_pipeline.answer_question(row["question"])
        latency = time.perf_counter() - t0
        llm_called = calls["n"] > 0

        expected_cls = row["expected_classification"]
        expected_sources = [s for s in row["expected_source"].split("|") if s]
        cited = _source_id_for(resp.source.url if resp.source else None)
        page = resp.source.page if resp.source else None
        out = {
            "id": row["id"], "question": row["question"],
            "expected_classification": expected_cls, "classification": resp.classification,
            "classification_ok": resp.classification == expected_cls,
            "answer": resp.answer, "cited_source": cited or "", "cited_page": page or "",
            "last_updated": resp.last_updated or "", "latency_s": round(latency, 2), "llm_called": llm_called,
            "retrieval_ok": "", "citation_ok": "", "answer_ok": "", "grounded": "", "refusal_ok": "",
        }

        if expected_cls == "FACTUAL":
            if row["expected_answer_contains"]:
                out["answer_ok"] = _contains_all(resp.answer, row["expected_answer_contains"])
            if expected_sources:
                retrieval = await retrieve(row["question"])
                retrieved_ids = [c.metadata.get("source_id") for c in retrieval.chunks]
                out["retrieval_ok"] = any(s in retrieved_ids for s in expected_sources)
                out["citation_ok"] = cited in expected_sources
            if cited:
                answer_numbers = numbers_in(resp.answer)
                out["grounded"] = answer_numbers <= numbers_in(_cited_text(cited, page))
        else:
            prefix = REFUSAL_PREFIXES[expected_cls]
            out["refusal_ok"] = resp.answer.startswith(prefix) and not llm_called
        results.append(out)
        print(f"[{row['id']:>2}] {'OK ' if out['classification_ok'] else 'CLS'} "
              f"{resp.classification:<11} {latency:5.1f}s  {resp.answer[:90]}")
    answer_pipeline.provider.chat = original_chat
    return results


def _rate(results: list[dict], key: str) -> str:
    vals = [r[key] for r in results if r[key] != ""]
    return f"{sum(bool(v) for v in vals)}/{len(vals)}" if vals else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", help="only run these ids")
    args = parser.parse_args()

    with open(ROOT / "evaluation" / "sample_qa.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.ids:
        rows = [r for r in rows if r["id"] in set(args.ids)]

    results = asyncio.run(evaluate(rows))

    summary = {
        "questions": len(results),
        "classification_accuracy": _rate(results, "classification_ok"),
        "retrieval_hit_at_k": _rate(results, "retrieval_ok"),
        "citation_accuracy": _rate(results, "citation_ok"),
        "answer_correctness": _rate(results, "answer_ok"),
        "grounded_numbers": _rate(results, "grounded"),
        "refusal_accuracy": _rate(results, "refusal_ok"),
        "median_latency_s": sorted(r["latency_s"] for r in results)[len(results) // 2],
    }
    out_dir = ROOT / "evaluation" / "results"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "latest.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print("\nSummary")
    for k, v in summary.items():
        print(f"  {k:<24} {v}")
    failures = [r for r in results if False in (r["classification_ok"], r["retrieval_ok"], r["citation_ok"],
                                                 r["answer_ok"], r["grounded"], r["refusal_ok"])]
    if failures:
        print("\nFailures")
        for r in failures:
            flags = [k for k in ("classification_ok", "retrieval_ok", "citation_ok", "answer_ok", "grounded", "refusal_ok")
                     if r[k] is False]
            print(f"  [{r['id']}] {r['question']}\n      {', '.join(flags)} | cited={r['cited_source']} p{r['cited_page']}\n      {r['answer']}")
    print(f"\nDetailed results: {out_dir / 'latest.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
