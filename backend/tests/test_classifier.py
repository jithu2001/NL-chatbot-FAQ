import pytest

from app.classifier.question_classifier import (
    REASON_PERFORMANCE,
    REASON_PREDICTION,
    Classification,
    classify,
)

FACTUAL = [
    "What is the expense ratio?",
    "What is the minimum SIP?",
    "What is the exit load?",
    "What is the benchmark?",
    "What is the riskometer?",
    "What is the minimum investment?",
    "Does the ELSS fund have a lock-in?",
    "How can I download my capital-gains statement?",
    "Where can I get the scheme factsheet?",
    "What is the ELSS lock-in period?",
    "What is the exit load if I redeem it within a year?",
    "Can I redeem ELSS units before 3 years?",
    "What is the asset allocation of the Flexi Cap fund?",
    "Who manages the large cap fund?",
    "How do I see my portfolio statement?",
]

ADVICE = [
    "Should I invest in this fund?",
    "Should I buy this mutual fund?",
    "Should I sell this fund?",
    "Which mutual fund is best?",
    "Which fund should I choose?",
    "Is this fund good for me?",
    "Should I invest my savings here?",
    "Can you recommend a fund?",
    "Is it a good time to invest in the ELSS fund?",
    "How much should I invest every month?",
    "Which is better: the Flexi Cap fund or the ELSS fund?",
    "Which one is best for tax saving?",
]

UNSUPPORTED = [
    ("What will the return be next year?", REASON_PREDICTION),
    ("Will this fund outperform?", REASON_PREDICTION),
    ("What will the NAV be next month?", REASON_PREDICTION),
    ("Predict the return.", REASON_PREDICTION),
    ("Compare the future performance.", REASON_PREDICTION),
    ("What return will this fund give next year?", REASON_PREDICTION),
    ("Which fund will give the highest return?", REASON_PREDICTION),
    ("Which fund has the highest returns?", REASON_PERFORMANCE),
    ("Compare Flexi Cap vs ELSS returns", REASON_PERFORMANCE),
    ("What was the 5 year CAGR of the Flexi Cap fund?", REASON_PERFORMANCE),
]


@pytest.mark.parametrize("q", FACTUAL)
def test_factual(q):
    assert classify(q).label is Classification.FACTUAL, q


@pytest.mark.parametrize("q", ADVICE)
def test_advice(q):
    assert classify(q).label is Classification.ADVICE, q


@pytest.mark.parametrize("q,reason", UNSUPPORTED)
def test_unsupported(q, reason):
    result = classify(q)
    assert result.label is Classification.UNSUPPORTED, q
    assert result.reason == reason, q


def test_pii_takes_priority_over_everything():
    assert classify("My PAN is ABCDE1234F. Should I invest?").label is Classification.PII
    assert classify("My PAN is ABCDE1234F. What is my mutual fund balance?").label is Classification.PII
