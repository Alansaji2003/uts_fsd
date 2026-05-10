"""Email and password format validators."""
import re

# Email: firstname.lastname@university.com
EMAIL_REGEX = re.compile(r"^[a-zA-Z]+\.[a-zA-Z]+@university\.com$")

# Password: starts with uppercase, then 5+ letters, then 3+ digits.
# Calibrated to sample I/O — "Hello123" must FAIL, "Helloworld123" must PASS.
PASSWORD_REGEX = re.compile(r"^[A-Z][a-zA-Z]{5,}[0-9]{3,}$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email or ""))


def is_valid_password(password: str) -> bool:
    return bool(PASSWORD_REGEX.match(password or ""))


def name_from_email(email: str) -> str:
    """alen.jones@university.com -> 'Alen Jones'"""
    local = email.split("@")[0]
    parts = local.split(".")
    return " ".join(p.capitalize() for p in parts)
