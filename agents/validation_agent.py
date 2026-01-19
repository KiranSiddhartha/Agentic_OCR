"""
Stage 4 – Validation & Arbitration Agent (FINAL AUTHORITY)
=========================================================
Responsibilities:
- Value sanity (reject headers / junk / placeholders)
- Field-specific normalization
- Confidence flooring
- Arbitration (accept / reject, never extract)
"""

import re
from datetime import datetime
from typing import Dict, Tuple


# ============================================================
# CONFIDENCE FLOORS (BUSINESS RULES)
# ============================================================

CONFIDENCE_FLOORS = {
    "carrier": 0.90,
    "policy_number": 0.90,
    "loan_number": 0.90,
    "insured_name": 0.85,
    "property_address": 0.85,
    "mailing_address": 0.80,
    "mortgage": 0.85,
    "total_premium": 0.80,
    "deductible": 0.80,
    "effective_date": 0.85,
    "expiration_date": 0.85,
    "agent_phone": 0.85,
    "agent": 0.80,
}

DEFAULT_FLOOR = 0.75


# ============================================================
# GLOBAL BLOCK LISTS
# ============================================================

SECTION_TITLES = {
    "summary",
    "home protection",
    "coverage",
    "coverages",
    "limits",
    "policy mortgage declarations summary",
    "declarations",
    "declarations summary",
    "mortgage/other interested parties",
    "applicable deductible(s)",
    "premiums",
    "forms and endorsements",
    "policy period",
    "policyholder since",
}

JUNK_VALUES = {
    "type",
    "interest",
    "policy",
    "coverage",
    "summary",
    "n/a",
    "none",
    "see attached",
}

PREFIX_STRIP = [
    "coverage detail for",
    "policy effective date is",
    "effective date is",
    "your policy effective date is",
    "your policy effective date:",
    "location:",
    "address:",
    "name:",
]


# ============================================================
# HEADER / LABEL DETECTION
# ============================================================

def _is_section_header_value(value: str) -> bool:
    if not value:
        return False

    l = value.lower().strip()

    if l in SECTION_TITLES:
        return True

    for title in SECTION_TITLES:
        if l.startswith(title):
            return True

    if l.endswith(":") and len(l.split()) <= 5:
        return True

    return False


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _strip_prefixes(value: str) -> str:
    v = value.strip()
    vl = v.lower()
    for p in PREFIX_STRIP:
        if vl.startswith(p):
            return v[len(p):].strip(" :.-")
    return v


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# ============================================================
# FIELD VALIDATORS
# ============================================================

def validate_carrier(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(value)
    if _is_section_header_value(v) or v.lower() in JUNK_VALUES or len(v) < 4:
        return False, v, 0.0
    return True, v.upper(), 0.95

POLICY_RE = re.compile(r"\b[A-Z0-9][A-Z0-9\- ]{5,20}\b")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
DATE_RE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
CURRENCY_RE = re.compile(r"\$\s?\d")
ZIP_RE = re.compile(r"\b\d{5}(-\d{4})?\b")

def validate_policy_number(value: str):
    v = value.strip()

    if _is_section_header_value(v):
        return False, v, 0.0

    if PHONE_RE.search(v):
        return False, v, 0.0

    if ZIP_RE.search(v):
        return False, v, 0.0

    if sum(c.isdigit() for c in v) < 6:
        return False, v, 0.0

    return True, v, 0.95  

def validate_loan_number(value: str) -> Tuple[bool, str, float]:
    v = value.strip()
    if _is_section_header_value(v) or v.lower() in JUNK_VALUES:
        return False, v, 0.0
    if sum(c.isdigit() for c in v) < 4:
        return False, v, 0.0
    return True, v, 0.95


def validate_name(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(value)

    if _is_section_header_value(v):
        return False, v, 0.0

    if ":" in v:
        return False, v, 0.0

    if any(w in v.lower() for w in (
        "named insured",
        "insured name",
        "mailing address",
        "policy type",
        "coverage",
        "deductible",
    )):
        return False, v, 0.0

    if any(c.isdigit() for c in v) or len(v.split()) < 2:
        return False, v, 0.0

    return True, v, 0.95


def validate_address(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))

    if _is_section_header_value(v) or v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if not re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", v):
        return False, v, 0.0

    return True, v, 0.95


def validate_date(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))

    if _is_section_header_value(v):
        return False, v, 0.0

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            dt = datetime.strptime(v, fmt)
            if 1990 <= dt.year <= 2050:
                return True, v, 0.95
        except ValueError:
            continue

    return False, v, 0.0


def validate_money(value: str) -> Tuple[bool, str, float]:
    if _is_section_header_value(value):
        return False, value, 0.0
    try:
        amt = float(value.replace("$", "").replace(",", ""))
        if 10 <= amt <= 1_000_000:
            return True, f"${amt:,.2f}".replace(".00", ""), 0.90
    except Exception:
        pass
    return False, value, 0.0


def validate_phone(value: str) -> Tuple[bool, str, float]:
    if _is_section_header_value(value):
        return False, value, 0.0
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) == 10:
        return True, value, 0.95
    return False, value, 0.0


# ============================================================
# FINAL ARBITRATION
# ============================================================

def validate_and_arbitrate(
    merged_fields: Dict,
    ocr_confidence: float,
    stage_breakdown: Dict,
) -> Tuple[Dict, float]:

    validated = {}
    scores = []

    validators = {
        "carrier": validate_carrier,
        "policy_number": validate_policy_number,
        "loan_number": validate_loan_number,
        "insured_name": validate_name,
        "agent": validate_name,
        "mortgage": validate_name,
        "property_address": validate_address,
        "mailing_address": validate_address,
        "effective_date": validate_date,
        "expiration_date": validate_date,
        "total_premium": validate_money,
        "deductible": validate_money,
        "agent_phone": validate_phone,
    }

    for field, data in merged_fields.items():
        if not isinstance(data, dict):
            continue

        value = data.get("value")
        confidence = data.get("confidence", 0.0)

        floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
        if confidence < floor or not value:
            continue

        if field in validators:
            ok, norm_value, score = validators[field](value)
            if not ok:
                continue
            data["value"] = norm_value
            data["validation_score"] = score
            scores.append(score)
        else:
            scores.append(0.80)

        validated[field] = data

    final_confidence = round(
        (sum(scores) / len(scores)) * 0.6 + ocr_confidence * 0.4
        if scores else ocr_confidence * 0.4,
        3,
    )

    return validated, final_confidence

# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def validate_output(structured: Dict, confidence: float):
    return validate_and_arbitrate(structured, confidence, {"stage1": structured})
