"""Structure-aware chunking.

Text is split on semantic boundaries (blank-line separated blocks/columns,
then lines, then sentences) and packed into chunks of roughly
CHUNK_SIZE_TOKENS with CHUNK_OVERLAP_TOKENS of overlap. A single line is
never split unless it is longer than a whole chunk, so a label and its value
on the same row (e.g. "Regular Plan: 1.05%*") always stay together.
"""

from __future__ import annotations

import re

# Bump when the chunking algorithm changes so ingestion re-indexes everything.
CHUNKER_VERSION = "3"
CHUNK_SIZE_TOKENS = 900
CHUNK_OVERLAP_TOKENS = 150
CHARS_PER_TOKEN = 4  # conservative approximation for English + numbers


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _split_long(unit: str, max_chars: int) -> list[str]:
    """Split an over-long unit by lines, then sentences, then hard wraps."""
    if len(unit) <= max_chars:
        return [unit]
    lines = unit.split("\n")
    if len(lines) > 1:
        return [piece for ln in lines for piece in _split_long(ln, max_chars)]
    sentences = re.split(r"(?<=[.;:])\s+(?=[A-Z(])", unit)
    if len(sentences) > 1:
        return [piece for s in sentences for piece in _split_long(s, max_chars)]
    return [unit[i : i + max_chars] for i in range(0, len(unit), max_chars)]


def _units(text: str, max_chars: int) -> list[str]:
    units: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if len(block) <= max_chars:
            units.append(block)
        else:
            # Keep lines of a big block grouped, but allow breaks between lines.
            units.extend(_split_long(block, max_chars))
    return units


def chunk_text(text: str, chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
               overlap_tokens: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    max_chars = chunk_size_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN
    units = _units(text, max_chars)

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for unit in units:
        add = len(unit) + (2 if current else 0)
        if current and size + add > max_chars:
            chunks.append("\n\n".join(current))
            # Carry trailing units forward as overlap.
            carry: list[str] = []
            carried = 0
            for prev in reversed(current):
                if carried + len(prev) > overlap_chars:
                    if not carry:
                        # Last unit is bigger than the overlap: carry its
                        # trailing whole lines instead.
                        tail: list[str] = []
                        for line in reversed(prev.split("\n")):
                            if carried + len(line) > overlap_chars:
                                break
                            tail.insert(0, line)
                            carried += len(line) + 1
                        if tail:
                            carry.append("\n".join(tail))
                    break
                carry.insert(0, prev)
                carried += len(prev) + 2
            current, size = carry, carried
            add = len(unit) + (2 if current else 0)
        current.append(unit)
        size += add
    if current:
        chunk = "\n\n".join(current)
        # Avoid emitting a tail that is pure overlap of the previous chunk.
        if not chunks or not chunks[-1].endswith(chunk):
            chunks.append(chunk)
    return [c for c in chunks if c.strip()]
