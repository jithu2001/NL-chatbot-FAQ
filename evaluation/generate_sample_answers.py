#!/usr/bin/env python
"""Write evaluation/sample_answers.md: real assistant answers + source links.

    python evaluation/generate_sample_answers.py                       # in-process pipeline
    python evaluation/generate_sample_answers.py --api https://<app>/  # a deployed instance
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

QUESTIONS = [
    "What is the expense ratio of Parag Parikh Flexi Cap Fund?",
    "What is the minimum SIP?",
    "What is the ELSS lock-in period?",
    "What is the exit load of the liquid fund?",
    "What is the riskometer of the conservative hybrid fund?",
    "What is the benchmark of the large cap fund?",
    "How do I download my capital-gains statement?",
    "Should I buy the Flexi Cap fund?",
    "What was the 1-year return of the ELSS fund?",
    "My PAN is ABCDE1234F. What is my balance?",
]


async def _ask_local(question: str) -> dict:
    from app.services.answer_pipeline import answer_question

    return (await answer_question(question)).model_dump()


def _ask_api(base: str, question: str) -> dict:
    r = httpx.post(f"{base.rstrip('/')}/api/chat", json={"question": question}, timeout=120)
    r.raise_for_status()
    return r.json()


def _source_cell(resp: dict) -> str:
    src = resp.get("source")
    if not src:
        return "—"
    url = src["url"] + (f"#page={src['page']}" if src.get("page") and ".pdf" in src["url"] else "")
    page = f", p. {src['page']}" if src.get("page") else ""
    return f"[{src['title']}{page}]({url})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", help="base URL of a deployed instance instead of the in-process pipeline")
    args = parser.parse_args()

    if args.api:
        answers = [_ask_api(args.api, q) for q in QUESTIONS]
        origin = f"deployed instance {args.api}"
    else:
        from app.core.config import get_settings

        answers = [asyncio.run(_ask_local(q)) for q in QUESTIONS]
        s = get_settings()
        model = s.groq_model if s.llm_provider == "groq" else s.ollama_model
        origin = f"local pipeline ({s.llm_provider}: {model}, embeddings: {s.embedding_model_id})"

    lines = [
        "# Sample Q&A — PowerUp Money Mutual Fund FAQ Assistant",
        "",
        f"Generated on {date.today():%d %B %Y} from the {origin} by `evaluation/generate_sample_answers.py`.",
        "Answers are the assistant's actual output. The source link is attached by the backend from `data/sources.csv`, never written by the LLM.",
        "",
        "| # | Question | Type | Answer | Source | Last updated from sources |",
        "|---|---|---|---|---|---|",
    ]
    for i, (q, r) in enumerate(zip(QUESTIONS, answers, strict=True), 1):
        answer = r["answer"].replace("|", "\\|")
        lines.append(f"| {i} | {q} | {r['classification']} | {answer} | {_source_cell(r)} | {r.get('last_updated') or '—'} |")
    out = ROOT / "evaluation" / "sample_answers.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
