"""Every refusal must still carry exactly one official source from the registry.

These paths never reach retrieval or the LLM, so they run offline.
"""

import asyncio

import pytest

from app.core.sources import registry
from app.services.answer_pipeline import answer_question

REGISTRY_URLS = {s.url for s in registry().values()}


@pytest.mark.parametrize(
    "question,classification",
    [
        ("My PAN is ABCDE1234F. What is my balance?", "PII"),
        ("Should I buy the Flexi Cap fund?", "ADVICE"),
        ("Is Parag Parikh Flexi Cap good for my portfolio?", "ADVICE"),
        ("What was the 1-year return of the ELSS fund?", "UNSUPPORTED"),
        ("What will the NAV be next month?", "UNSUPPORTED"),
    ],
)
def test_refusals_cite_one_registry_source(question, classification):
    resp = asyncio.run(answer_question(question))
    assert resp.classification == classification
    assert resp.source is not None and resp.source.url in REGISTRY_URLS


def test_performance_refusal_points_to_factsheet():
    resp = asyncio.run(answer_question("Compare returns of Flexi Cap and ELSS"))
    assert resp.source.source_type == "AMC Factsheet"
    assert "factsheet" in resp.answer.lower()
