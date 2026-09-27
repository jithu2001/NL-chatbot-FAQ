import pytest

from app.safety.pii_detector import contains_pii, detect_pii

POSITIVE = [
    ("My PAN is ABCDE1234F", "PAN"),
    ("pan abcde1234f", "PAN"),
    ("Aadhaar 2345 6789 0123", "AADHAAR"),
    ("my aadhaar is 234567890123", "AADHAAR"),
    ("email me at someone@example.com", "EMAIL"),
    ("call +91 98765 43210", "PHONE"),
    ("my number is 9876543210", "PHONE"),
    ("the OTP is 482913", "OTP"),
    ("my password is hunter2", "PASSWORD"),
    ("folio no: 12345678/90", "FOLIO"),
    ("account number 123456789012", "BANK_ACCOUNT"),
    ("IFSC HDFC0001234", "IFSC"),
]

NEGATIVE = [
    "What is the expense ratio?",
    "What is the minimum SIP of Rs. 1,000?",
    "What is the exit load after 365 days?",
    "What is the NAV as on August 31, 2026?",
    "How do I get my PAN updated in my folio?",
    "What is the lock-in under section 80C?",
    "Is the AUM above 1,47,404.51 crores?",
    "What does OTP mean?",
]


@pytest.mark.parametrize("text,kind", POSITIVE)
def test_detects(text, kind):
    assert kind in detect_pii(text), text


@pytest.mark.parametrize("text", NEGATIVE)
def test_no_false_positive(text):
    assert not contains_pii(text), (text, detect_pii(text))
