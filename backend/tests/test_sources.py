import csv

import pytest

from app.core.sources import REQUIRED_COLUMNS, RegistryError, load_sources

PROHIBITED = ("groww", "zerodha", "moneycontrol", "etmoney", "bankbazaar", "wikipedia", "reddit", "quora", "youtube")


def test_registry_is_valid_and_official():
    sources = load_sources()
    assert 15 <= len(sources) <= 40
    assert {s.authority for s in sources} <= {"AMC", "AMFI", "SEBI"}
    for s in sources:
        assert not any(p in s.url.lower() for p in PROHIBITED)
        for field in ("publication_date", "last_updated", "retrieved_date"):
            value = getattr(s, field)
            assert value == "Not specified" or (len(value) == 10 and value[4] == "-"), (s.source_id, field)


def _write(tmp_path, url, authority="AMC"):
    path = tmp_path / "sources.csv"
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(REQUIRED_COLUMNS)
        w.writerow(["SRC-1", "T", "General", "x", "Page", url, "Not specified", "Not specified", "2026-09-27", authority])
    return path


def test_third_party_url_rejected(tmp_path):
    with pytest.raises(RegistryError):
        load_sources(_write(tmp_path, "https://groww.in/mutual-funds/x"))


def test_authority_domain_mismatch_rejected(tmp_path):
    with pytest.raises(RegistryError):
        load_sources(_write(tmp_path, "https://www.amfiindia.com/x", authority="AMC"))
