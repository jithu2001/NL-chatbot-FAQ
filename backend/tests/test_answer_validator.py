from app.safety.answer_validator import Verdict, split_sentences, strip_citations, validate_answer

CTX = "Expense Ratio Regular Plan: 1.05%* Direct Plan: 0.53%* Monthly SIP: ₹1,000 lock in of three years"


def test_ok_answer_passes():
    r = validate_answer("The expense ratio is 1.05% for the Regular Plan and 0.53% for the Direct Plan.", CTX)
    assert r.verdict is Verdict.OK


def test_urls_and_source_lines_removed():
    raw = "The minimum SIP is ₹1,000 (https://evil.example.com/x).\nSource: [Factsheet](https://x.y)"
    r = validate_answer(raw, CTX)
    assert r.verdict is Verdict.OK
    assert "http" not in r.answer and "Source" not in r.answer


def test_self_citation_sentence_removed():
    raw = "The minimum SIP is ₹1,000. This information is from the Key Information Memorandum, last updated on 2025-11-27."
    r = validate_answer(raw, CTX)
    assert r.verdict is Verdict.OK
    assert r.answer == "The minimum SIP is ₹1,000."


def test_hallucinated_number_rejected():
    r = validate_answer("The expense ratio is 0.75%.", CTX)
    assert r.verdict is Verdict.UNGROUNDED


def test_number_words_count_as_grounded():
    assert validate_answer("The lock-in period is 3 years.", CTX).verdict is Verdict.OK


def test_advice_blocked():
    assert validate_answer("You should invest in this fund for the long term.", CTX).verdict is Verdict.ADVICE_BLOCKED
    assert validate_answer("This is the best fund for tax saving.", CTX).verdict is Verdict.ADVICE_BLOCKED
    assert validate_answer("It is expected to deliver strong returns.", CTX).verdict is Verdict.ADVICE_BLOCKED


def test_negated_disclaimer_is_not_advice():
    r = validate_answer("The scheme does not guarantee returns.", CTX)
    assert r.verdict is Verdict.OK


def test_not_verified_detected():
    r = validate_answer("The fact could not be verified from the available official sources.", CTX)
    assert r.verdict is Verdict.NOT_VERIFIED


def test_max_three_sentences():
    raw = "The SIP is ₹1,000. The ratio is 1.05%. The Direct ratio is 0.53%. The lock-in is three years."
    r = validate_answer(raw, CTX)
    assert r.verdict is Verdict.OK
    assert len(split_sentences(r.answer)) == 3


def test_abbreviations_do_not_split_or_mangle():
    assert split_sentences("The minimum is Rs. 1,000 per month. Mr. Thakkar manages it.") == [
        "The minimum is Rs. 1,000 per month.", "Mr. Thakkar manages it."]
    assert "years." in strip_citations("The lock-in is 3 years.")


def test_bullets_flattened():
    raw = "The exit load is:\n- Day 1: 1.05%\n- Day 2: 0.53%"
    assert strip_citations(raw) == "The exit load is: Day 1: 1.05%; Day 2: 0.53%."
