"""Text extraction for official HTML pages and PDFs.

PDF factsheets and KIMs are multi-column layouts full of label/value pairs
("Expense Ratio" ... "Regular Plan: 1.05%"). Naive text extraction scatters
labels far away from their values, so pages are rebuilt column by column
from word positions, keeping each visual row on one line.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class PageText:
    page: int | None  # 1-based page number for PDFs, None for HTML
    text: str
    heading: str = ""  # largest-font text on a PDF page (e.g. the scheme title)


# --------------------------------------------------------------------------
# Shared cleaning
# --------------------------------------------------------------------------

_RUPEE_BACKTICK = re.compile(r"`\s?(?=\d)")  # PPFAS PDFs render ₹ as a backtick glyph


def clean_text(text: str) -> str:
    text = text.replace(" ", " ").replace("​", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = _RUPEE_BACKTICK.sub("₹", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue
        if out and out[-1] == ln:  # consecutive duplicate
            continue
        out.append(ln)
    return "\n".join(out).strip()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

GUTTER_MAX_CROSSINGS = 2


def _pdf_page_columns(page) -> str:
    """Rebuild a PDF page as text, column by column, row by row."""
    width = page.rect.width
    items: list[tuple[float, float, float, float, str]] = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            _, dy = line["dir"]
            if abs(dy) > 0.1:  # rotated text, e.g. riskometer dial lettering
                continue
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            segment = [spans[0]]
            segments = []
            for span in spans[1:]:
                if span["bbox"][0] - segment[-1]["bbox"][2] > 25:
                    segments.append(segment)
                    segment = [span]
                else:
                    segment.append(span)
            segments.append(segment)
            for seg in segments:
                text = " ".join(s["text"].strip() for s in seg)
                if len(text) <= 2 and not any(c.isdigit() for c in text):
                    continue  # dial letters and stray glyphs
                items.append((
                    min(s["bbox"][0] for s in seg), min(s["bbox"][1] for s in seg),
                    max(s["bbox"][2] for s in seg), max(s["bbox"][3] for s in seg), text,
                ))
    if not items:
        return ""

    # Column gutters = vertical strips that (almost) no narrow text crosses.
    # A couple of crossings are tolerated: factsheets often have one caption or
    # footnote that bridges two columns.
    coverage = [0] * (int(width) + 2)
    for x0, _, x1, _, _ in items:
        if x1 - x0 > 0.45 * width:
            continue
        for x in range(max(0, int(x0)), min(int(width), int(x1)) + 1):
            coverage[x] += 1
    gutters: list[float] = []
    x = 0
    while x < len(coverage):
        if coverage[x] <= GUTTER_MAX_CROSSINGS:
            start = x
            while x < len(coverage) and coverage[x] <= GUTTER_MAX_CROSSINGS:
                x += 1
            if x - start >= 4 and start > 30 and x < width - 30:
                gutters.append((start + x) / 2)
        x += 1
    bounds = [0.0, *gutters, width + 1]

    columns: list[list] = [[] for _ in range(len(bounds) - 1)]
    wide_top, wide_rest = [], []
    for it in items:
        x0, y0, x1, _, _ = it
        if x1 - x0 > 0.45 * width:
            (wide_top if y0 < 130 else wide_rest).append(it)
            continue
        for i in range(len(bounds) - 1):
            if bounds[i] <= x0 + 1 < bounds[i + 1]:
                columns[i].append(it)
                break

    def rows(its) -> list[str]:
        its = sorted(its, key=lambda i: (i[1], i[0]))
        result, current, row_y = [], [], None
        for it in its:
            if row_y is not None and abs(it[1] - row_y) > 4:
                result.append("   ".join(c[4] for c in sorted(current)))
                current = []
            if not current:
                row_y = it[1]
            current.append(it)
        if current:
            result.append("   ".join(c[4] for c in sorted(current)))
        return result

    parts = rows(wide_top)
    for col in columns:
        if col:
            parts.extend(rows(col))
            parts.append("")
    parts.extend(rows(wide_rest))
    return "\n".join(parts)


def _page_heading(page) -> str:
    """Text set in the largest font on the page (factsheet pages carry the
    scheme name as their title)."""
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            if abs(line["dir"][1]) > 0.1:
                continue
            for s in line["spans"]:
                if len(s["text"].strip()) > 3:
                    spans.append((round(s["size"], 1), s["bbox"][1], s["text"].strip()))
    if not spans:
        return ""
    top = max(size for size, _, _ in spans)
    return " ".join(t for size, _, t in sorted(spans, key=lambda x: x[1]) if size >= top - 0.6)[:300]


def _remove_repeated_lines(pages: list[str]) -> list[str]:
    """Drop running headers/footers: short lines repeated on many pages."""
    if len(pages) < 4:
        return pages
    counts: Counter[str] = Counter()
    for text in pages:
        counts.update({ln.strip() for ln in text.splitlines() if ln.strip()})
    limit = max(3, int(0.4 * len(pages)))
    repeated = {ln for ln, n in counts.items() if n >= limit and len(ln) < 160}
    cleaned = []
    for text in pages:
        keep = [ln for ln in text.splitlines()
                if ln.strip() not in repeated and not re.fullmatch(r"\s*\d{1,3}\s*", ln)]
        cleaned.append("\n".join(keep))
    return cleaned


def extract_pdf(data: bytes) -> list[PageText]:
    try:
        import pymupdf  # PyMuPDF: position-aware extraction
    except ImportError:  # pragma: no cover - fallback path
        return _extract_pdf_pypdf(data)

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        raw = [_pdf_page_columns(page) for page in doc]
        headings = [_page_heading(page) for page in doc]
    raw = _remove_repeated_lines(raw)
    return [PageText(page=i + 1, text=clean_text(t), heading=headings[i])
            for i, t in enumerate(raw) if t.strip()]


def _extract_pdf_pypdf(data: bytes) -> list[PageText]:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    raw = [(p.extract_text(extraction_mode="layout") or "") for p in reader.pages]
    raw = [re.sub(r"[ \t]{3,}", "   ", t) for t in raw]
    raw = _remove_repeated_lines(raw)
    return [PageText(page=i + 1, text=clean_text(t)) for i, t in enumerate(raw) if t.strip()]


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

_DROP_TAGS = ("script", "style", "noscript", "svg", "nav", "header", "footer", "form",
              "iframe", "button", "select", "option", "template", "img")
_DROP_CLASS = re.compile(
    r"(navbar|nav-|menu|footer|offcanvas|breadcrumb|dropdown|modal|cookie|social|"
    r"skip-link|accessib|translate|mega|topbar|header-)", re.I)
_BOILERPLATE_TERMINATORS = {"Related Topics", "Related Tools", "Related Links"}
_BLOCK_TAGS = {"p", "div", "section", "article", "li", "ul", "ol", "br", "tr", "table",
               "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "blockquote"}


def _table_to_text(table: Tag) -> str:
    lines = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_html(data: bytes) -> list[PageText]:
    soup = BeautifulSoup(data, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    for tag in soup(_DROP_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        if getattr(tag, "decomposed", False):
            continue
        attrs = getattr(tag, "attrs", None)
        if not attrs:
            continue
        marker = " ".join(attrs.get("class", []) or []) + " " + (attrs.get("id") or "")
        if marker.strip() and _DROP_CLASS.search(marker) and tag.name not in ("body", "main", "html"):
            tag.decompose()

    root = soup.find("main") or soup.body or soup

    for table in root.find_all("table"):
        table.replace_with(NavigableString("\n" + _table_to_text(table) + "\n"))
    for h in root.find_all(re.compile(r"^h[1-6]$")):
        h.insert_before(NavigableString("\n\n## "))
        h.insert_after(NavigableString("\n"))
    for li in root.find_all("li"):
        if li.find(["ul", "ol"]) is None:  # simple item: keep it on one "- " line
            text = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
            li.replace_with(NavigableString(f"\n- {text}\n" if text else "\n"))
    for tag in root.find_all(_BLOCK_TAGS):
        tag.insert_after(NavigableString("\n"))

    text = root.get_text("")
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Drop menu-like lines that repeat many times (desktop + mobile menus).
    lines = [ln.strip() for ln in text.splitlines()]
    counts = Counter(ln for ln in lines if ln)
    lines = [ln for ln in lines if not ln or counts[ln] < 3 or len(ln) > 80]
    # Cut site boilerplate that follows the article body (e.g. AMFI's
    # "Related Topics" block and footer menus that are not in <footer>).
    for i, ln in enumerate(lines):
        if ln.lstrip("#- ").strip() in _BOILERPLATE_TERMINATORS:
            lines = lines[:i]
            break
    lines = [ln for ln in lines if ln not in ("-", "##", "- ##")]
    body = clean_text("\n".join(lines))
    if title and title not in body[:200]:
        body = f"{title}\n\n{body}"
    return [PageText(page=None, text=body)] if body else []
