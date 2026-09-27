from app.core.catalog import detect_scheme, detect_topic, find_scheme_in_text
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
    assert detect_scheme("What is the ELSS lock-in period?") == "Parag Parikh ELSS Tax Saver Fund"
    assert detect_scheme("exit load of the liquid fund") == "Parag Parikh Liquid Fund"
    assert detect_scheme("benchmark of the large cap fund") == "Parag Parikh Large Cap Fund"
    assert detect_scheme("riskometer of the conservative hybrid fund") == "Parag Parikh Conservative Hybrid Fund"
    assert detect_scheme("What is the expense ratio?") is None


def test_topic_detection():
    assert detect_topic("What is the expense ratio?").name == "expense ratio"
    assert detect_topic("What is the minimum SIP?").name == "minimum SIP"
    assert detect_topic("How do I download my capital-gains statement?").name == "capital gains statement"
    assert detect_topic("Does the ELSS fund have a lock-in?").name == "lock-in"
    assert detect_topic("What is CAS?").name == "CAS"
    assert detect_topic("Who is the CEO of Tesla?") is None


def test_page_scheme_detection_skips_out_of_scope():
    assert find_scheme_in_text("Parag Parikh Arbitrage Fund Type of Scheme") == "OUT_OF_SCOPE"
    assert find_scheme_in_text("Parag Parikh Liquid Fund Type of Scheme") == "Parag Parikh Liquid Fund"
