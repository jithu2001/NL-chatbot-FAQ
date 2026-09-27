from app.core.catalog import detect_amc, detect_scheme, detect_topic, find_scheme_in_text, scheme_candidates
from app.rag.chunker import chunk_text


def test_chunk_keeps_label_and_value_together():
    rows = "\n".join(f"Row {i} label: value {i}" for i in range(2000))
    text = "Expense Ratio\nRegular Plan: 1.05%*\n\n" + rows
    for chunk in chunk_text(text, chunk_size_tokens=200, overlap_tokens=30):
        for line in chunk.splitlines():
            if line.startswith("Row "):
                assert ": value " in line  # a line is never split


def test_chunk_overlap_and_size():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 30 for i in range(40))
    chunks = chunk_text(text, chunk_size_tokens=300, overlap_tokens=60)
    assert len(chunks) > 1
    assert all(len(c) <= 300 * 4 + 10 for c in chunks)
    assert chunks[0].split("\n\n")[-1] in chunks[1]  # overlap carried forward


def test_overlap_carries_tail_lines_of_large_blocks():
    block = "\n".join(f"Label {i}: {i}.00%" for i in range(300))
    chunks = chunk_text(block + "\n\n" + block, chunk_size_tokens=400, overlap_tokens=50)
    assert len(chunks) >= 2
    last_line = chunks[0].splitlines()[-1]
    assert last_line in chunks[1]


def test_scheme_detection():
    assert detect_scheme("What is the exit load of Parag Parikh Flexi Cap Fund?") == "Parag Parikh Flexi Cap Fund"
    assert detect_scheme("HDFC flexi cap expense ratio") == "HDFC Flexi Cap Fund"
    assert detect_scheme("Parag Parikh ELSS lock-in") == "Parag Parikh ELSS Tax Saver Fund"
    assert detect_scheme("benchmark of HDFC Top 100") == "HDFC Large Cap Fund"
    assert detect_scheme("HDFC ELSS - Tax Saver Fund exit load") == "HDFC ELSS Tax Saver Fund"
    assert detect_scheme("benchmark of the mid cap fund") == "HDFC Mid Cap Fund"  # only HDFC has one
    assert detect_scheme("riskometer of the conservative hybrid fund") == "Parag Parikh Conservative Hybrid Fund"
    assert detect_scheme("What is the expense ratio?") is None


def test_ambiguous_category_lists_both_amcs():
    assert scheme_candidates("What is the ELSS lock-in period?") == [
        "Parag Parikh ELSS Tax Saver Fund", "HDFC ELSS Tax Saver Fund"]
    assert detect_scheme("exit load of the liquid fund") is None
    assert detect_amc("expense ratio of HDFC") == "HDFC Mutual Fund"
    assert detect_amc("Parag Parikh and HDFC") is None


def test_resolve_scope_defaults():
    from app.rag.retriever import resolve_scope

    scope = resolve_scope("What is the ELSS lock-in period?")
    assert scope.scheme == "Parag Parikh ELSS Tax Saver Fund" and scope.defaulted
    assert scope.other_schemes == ["HDFC ELSS Tax Saver Fund"]
    scope = resolve_scope("What is the expense ratio of HDFC?")
    assert scope.scheme == "HDFC Flexi Cap Fund" and scope.defaulted and scope.amc == "HDFC Mutual Fund"
    scope = resolve_scope("What is the exit load?", scheme_hint="HDFC Liquid Fund")
    assert scope.scheme == "HDFC Liquid Fund" and not scope.defaulted
    assert resolve_scope("How do I download my HDFC capital gains statement?").amc == "HDFC Mutual Fund"


def test_topic_detection():
    assert detect_topic("What is the expense ratio?").name == "expense ratio"
    assert detect_topic("What is the minimum SIP?").name == "minimum SIP"
    assert detect_topic("How do I download my capital-gains statement?").name == "capital gains statement"
    assert detect_topic("Does the ELSS fund have a lock-in?").name == "lock-in"
    assert detect_topic("What is CAS?").name == "CAS"
    assert detect_topic("Who is the CEO of Tesla?") is None


def test_page_scheme_detection_skips_out_of_scope():
    assert find_scheme_in_text("Parag Parikh Arbitrage Fund Type of Scheme") == "OUT_OF_SCOPE"
    assert find_scheme_in_text("HDFC Large & Mid Cap Fund") == "OUT_OF_SCOPE"
    assert find_scheme_in_text("HDFC ELSS - Tax Saver Fund") == "HDFC ELSS Tax Saver Fund"
    assert find_scheme_in_text("BENCHMARK AND SCHEME RISKOMETERS") is None
    assert find_scheme_in_text("Parag Parikh Liquid Fund Type of Scheme") == "Parag Parikh Liquid Fund"
