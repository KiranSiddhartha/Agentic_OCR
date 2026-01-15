# # agents/validation_agent.py
# # Enhanced validation with confidence floors
# # Stage 4: Arbitration and final validation

# import re
# from datetime import datetime
# from typing import Dict, Tuple, Optional

# # ============================================================
# # CONFIDENCE FLOORS (BUSINESS RULES)
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier": 0.90,
#     "policy_number": 0.90,
#     "loan_number": 0.90,
#     "insured_name": 0.85,
#     "property_address": 0.85,
#     "mailing_address": 0.80,
#     "total_premium": 0.80,
#     "dwelling_coverage": 0.80,
#     "deductible": 0.80,
#     "effective_date": 0.85,
#     "expiration_date": 0.85,
#     "agent_phone": 0.85,
#     "agent": 0.80,
# }

# DEFAULT_FLOOR = 0.75

# # ============================================================
# # FIELD-SPECIFIC VALIDATORS
# # ============================================================

# def validate_carrier(carrier: str) -> Tuple[bool, float]:
#     if not carrier or len(carrier.strip()) < 3:
#         return False, 0.0
#     if carrier.lower() in {"insurance", "policy", "coverage"}:
#         return False, 0.0
#     if any(k in carrier.lower() for k in ["endorsement", "form", "page"]):
#         return False, 0.0
#     return True, 0.95


# def validate_policy_number(policy_num: str) -> Tuple[bool, float]:
#     if not policy_num or len(policy_num) < 6:
#         return False, 0.0
#     digits = sum(c.isdigit() for c in policy_num)
#     if digits >= 6:
#         return True, 0.95
#     return False, 0.2


# def validate_loan_number(loan_num: str) -> Tuple[bool, float]:
#     if not loan_num or len(loan_num) < 5:
#         return False, 0.0
#     digits = sum(c.isdigit() for c in loan_num)
#     if digits >= 4:
#         return True, 0.95
#     return False, 0.2


# def validate_date(date_str: str) -> Tuple[bool, float]:
#     for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
#         try:
#             parsed = datetime.strptime(date_str, fmt)
#             if 1990 <= parsed.year <= 2050:
#                 return True, 0.95
#         except ValueError:
#             pass
#     return False, 0.0


# def validate_name(name_str: str) -> Tuple[bool, float]:
#     if not name_str or len(name_str.strip()) < 4:
#         return False, 0.0
#     if any(c.isdigit() for c in name_str):
#         return False, 0.0
#     words = name_str.split()
#     if len(words) < 2:
#         return False, 0.0
#     if not (name_str.isupper() or name_str.istitle()):
#         return False, 0.4
#     return True, 0.95


# def validate_address(address_str: str) -> Tuple[bool, float]:
#     addr = address_str.lower()
#     if any(k in addr for k in ["endorsement", "form", "coverage", "section"]):
#         return False, 0.0
#     if "po box" in addr:
#         return False, 0.0
#     if re.search(r'\d+\s+.+\b[A-Z]{2}\b\s+\d{5}', address_str):
#         return True, 0.95
#     return False, 0.3


# def validate_premium(premium_str: str) -> Tuple[bool, float]:
#     try:
#         amount = float(premium_str.replace("$", "").replace(",", ""))
#         if 10 <= amount <= 500000:
#             return True, 0.95
#     except Exception:
#         pass
#     return False, 0.0


# def validate_phone(phone_str: str) -> Tuple[bool, float]:
#     digits = "".join(c for c in phone_str if c.isdigit())
#     if len(digits) in (10, 11):
#         return True, 0.95
#     return False, 0.3


# # ============================================================
# # STAGE 4: VALIDATION & ARBITRATION
# # ============================================================

# def validate_and_arbitrate(
#     merged_fields: Dict,
#     ocr_confidence: float,
#     stage_breakdown: Dict
# ) -> Tuple[Dict, float]:

#     validated = {}
#     scores = []

#     validators = {
#         "carrier": validate_carrier,
#         "policy_number": validate_policy_number,
#         "loan_number": validate_loan_number,
#         "insured_name": validate_name,
#         "agent": validate_name,
#         "property_address": validate_address,
#         "mailing_address": validate_address,
#         "total_premium": validate_premium,
#         "dwelling_coverage": validate_premium,
#         "deductible": validate_premium,
#         "effective_date": validate_date,
#         "expiration_date": validate_date,
#         "agent_phone": validate_phone,
#     }

#     for field, data in merged_fields.items():
#         value = data.get("value")
#         confidence = data.get("confidence", 0.0)

#         # ---------- CONFIDENCE FLOOR ----------
#         floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor:
#             continue

#         # ---------- FIELD VALIDATION ----------
#         if field in validators:
#             ok, score = validators[field](value)
#             if not ok:
#                 continue
#             data["validation_score"] = score
#             scores.append(score)
#         else:
#             scores.append(0.80)

#         validated[field] = data

#     final_conf = round(
#         (sum(scores) / len(scores)) * 0.6 + ocr_confidence * 0.4
#         if scores else ocr_confidence * 0.4,
#         3
#     )

#     return validated, final_conf


# # ============================================================
# # BACKWARD COMPATIBILITY
# # ============================================================

# def validate_output(structured: Dict, confidence: float):
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})

#13/01
# """
# Stage 4 – Validation & Normalization Agent (FINAL AUTHORITY)

# Responsibilities:
# - Value sanity (reject headers / junk / placeholders)
# - Field-specific normalization
# - Confidence flooring
# - Arbitration (accept / reject, never extract)
# """

# import re
# from datetime import datetime
# from typing import Dict, Tuple

# # ============================================================
# # CONFIDENCE FLOORS (BUSINESS RULES)
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier": 0.90,
#     "policy_number": 0.90,
#     "loan_number": 0.90,
#     "insured_name": 0.85,
#     "property_address": 0.85,
#     "mailing_address": 0.80,
#     "mortgage": 0.85,
#     "total_premium": 0.80,
#     "deductible": 0.80,
#     "effective_date": 0.85,
#     "expiration_date": 0.85,
#     "agent_phone": 0.85,
#     "agent": 0.80,
# }

# DEFAULT_FLOOR = 0.75

# # ============================================================
# # GLOBAL BLOCK LISTS (CRITICAL)
# # ============================================================

# SECTION_TITLES = {
#     "summary",
#     "home protection",
#     "coverage",
#     "coverages",
#     "limits",
#     "policy mortgagee declarations summary",
#     "declarations",
# }

# JUNK_VALUES = {
#     "type",
#     "interest",
#     "policy",
#     "coverage",
#     "summary",
# }

# PREFIX_STRIP = [
#     "coverage detail for",
#     "policy effective date is",
#     "effective date is",
#     "your policy effective date is",
# ]

# # ============================================================
# # NORMALIZATION HELPERS
# # ============================================================

# def _strip_prefixes(value: str) -> str:
#     v = value.strip()
#     vl = v.lower()
#     for p in PREFIX_STRIP:
#         if vl.startswith(p):
#             return v[len(p):].strip(" :.-")
#     return v


# def _normalize_whitespace(value: str) -> str:
#     return re.sub(r"\s+", " ", value).strip()


# # ============================================================
# # FIELD VALIDATORS (SANITY + NORMALIZATION)
# # ============================================================

# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(value)
#     if v.lower() in SECTION_TITLES:
#         return False, v, 0.0
#     if len(v) < 4:
#         return False, v, 0.0
#     return True, v.upper(), 0.95


# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     v = value.strip()
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
#     if sum(c.isdigit() for c in v) < 5:
#         return False, v, 0.0
#     return True, v, 0.95


# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     v = value.strip()
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
#     if sum(c.isdigit() for c in v) < 4:
#         return False, v, 0.0
#     return True, v, 0.95


# def validate_name(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(value)
#     if v.lower() in SECTION_TITLES:
#         return False, v, 0.0
#     if any(c.isdigit() for c in v):
#         return False, v, 0.0
#     if len(v.split()) < 2:
#         return False, v, 0.0
#     return True, v, 0.95


# def validate_address(value: str) -> Tuple[bool, str, float]:
#     v = _strip_prefixes(value)
#     v = _normalize_whitespace(v)

#     if v.lower() in SECTION_TITLES:
#         return False, v, 0.0

#     # Require at least street number + state + ZIP
#     if not re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", v):
#         return False, v, 0.0

#     return True, v, 0.95


# def validate_date(value: str) -> Tuple[bool, str, float]:
#     v = _strip_prefixes(value)
#     v = _normalize_whitespace(v)

#     for fmt in ("%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y"):
#         try:
#             dt = datetime.strptime(v, fmt)
#             if 1990 <= dt.year <= 2050:
#                 return True, v, 0.95
#         except ValueError:
#             continue

#     return False, v, 0.0


# def validate_money(value: str) -> Tuple[bool, str, float]:
#     try:
#         amt = float(value.replace("$", "").replace(",", ""))
#         if 10 <= amt <= 1_000_000:
#             return True, f"${amt:,.2f}".replace(".00", ""), 0.90
#     except Exception:
#         pass
#     return False, value, 0.0


# def validate_phone(value: str) -> Tuple[bool, str, float]:
#     digits = "".join(c for c in value if c.isdigit())
#     if len(digits) == 10:
#         return True, value, 0.95
#     return False, value, 0.0


# # ============================================================
# # STAGE 4 – VALIDATION & ARBITRATION
# # ============================================================

# def validate_and_arbitrate(
#     merged_fields: Dict,
#     ocr_confidence: float,
#     stage_breakdown: Dict
# ) -> Tuple[Dict, float]:

#     validated = {}
#     scores = []

#     validators = {
#         "carrier": validate_carrier,
#         "policy_number": validate_policy_number,
#         "loan_number": validate_loan_number,
#         "insured_name": validate_name,
#         "agent": validate_name,
#         "mortgage": validate_name,
#         "property_address": validate_address,
#         "mailing_address": validate_address,
#         "effective_date": validate_date,
#         "expiration_date": validate_date,
#         "total_premium": validate_money,
#         "deductible": validate_money,
#         "agent_phone": validate_phone,
#     }

#     for field, data in merged_fields.items():
#         if not isinstance(data, dict):
#             continue

#         value = data.get("value")
#         confidence = data.get("confidence", 0.0)

#         # -------- confidence floor --------
#         floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor or not value:
#             continue

#         # -------- validation --------
#         if field in validators:
#             ok, norm_value, score = validators[field](value)
#             if not ok:
#                 continue
#             data["value"] = norm_value
#             data["validation_score"] = score
#             scores.append(score)
#         else:
#             scores.append(0.80)

#         validated[field] = data

#     final_confidence = round(
#         (sum(scores) / len(scores)) * 0.6 + ocr_confidence * 0.4
#         if scores else ocr_confidence * 0.4,
#         3
#     )

#     return validated, final_confidence


# # ============================================================
# # BACKWARD COMPATIBILITY
# # ============================================================

# def validate_output(structured: Dict, confidence: float):
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})


"""
Stage 4 – Validation & Normalization Agent (FINAL AUTHORITY)

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
# GLOBAL BLOCK LISTS (CRITICAL - EXPANDED)
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
# SECTION HEADER DETECTION (NEW - ADDED)
# ============================================================

def _is_section_header_value(value: str) -> bool:
    """
    Block section headers from being accepted as field values.
    This is the final defense against header leakage.
    """
    if not value:
        return False

    l = value.lower().strip()

    # Exact match with known section titles
    if l in SECTION_TITLES:
        return True

    # Starts with blocked phrase
    for title in SECTION_TITLES:
        if l.startswith(title):
            return True

    # Check for "Coverage Detail for..." specifically
    if l.startswith("coverage detail"):
        return True

    # Short lines ending with colon are likely headers
    if l.endswith(":") and len(l.split()) <= 5:
        return True

    return False


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _strip_prefixes(value: str) -> str:
    """Remove common label prefixes from extracted values"""
    v = value.strip()
    vl = v.lower()

    for p in PREFIX_STRIP:
        if vl.startswith(p):
            return v[len(p):].strip(" :.-")

    return v


def _normalize_whitespace(value: str) -> str:
    """Normalize internal whitespace"""
    return re.sub(r"\s+", " ", value).strip()


# ============================================================
# FIELD VALIDATORS (SANITY + NORMALIZATION)
# ============================================================

def validate_carrier(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(value)

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if len(v) < 4:
        return False, v, 0.0

    return True, v.upper(), 0.95


def validate_policy_number(value: str) -> Tuple[bool, str, float]:
    v = value.strip()

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if sum(c.isdigit() for c in v) < 5:
        return False, v, 0.0

    return True, v, 0.95


def validate_loan_number(value: str) -> Tuple[bool, str, float]:
    v = value.strip()

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if sum(c.isdigit() for c in v) < 4:
        return False, v, 0.0

    return True, v, 0.95


def validate_name(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(value)

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    # No digits allowed in names
    if any(c.isdigit() for c in v):
        return False, v, 0.0

    # Must have at least 2 words
    if len(v.split()) < 2:
        return False, v, 0.0

    return True, v, 0.95


def validate_address(value: str) -> Tuple[bool, str, float]:
    v = _strip_prefixes(value)
    v = _normalize_whitespace(v)

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    # Require at least street number + state + ZIP
    if not re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", v):
        return False, v, 0.0

    return True, v, 0.95


def validate_date(value: str) -> Tuple[bool, str, float]:
    v = _strip_prefixes(value)
    v = _normalize_whitespace(v)

    # ADDED: Block section headers
    if _is_section_header_value(v):
        return False, v, 0.0

    # Try multiple date formats
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            dt = datetime.strptime(v, fmt)
            if 1990 <= dt.year <= 2050:
                return True, v, 0.95
        except ValueError:
            continue

    return False, v, 0.0


def validate_money(value: str) -> Tuple[bool, str, float]:
    # ADDED: Block section headers
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
    # ADDED: Block section headers
    if _is_section_header_value(value):
        return False, value, 0.0

    digits = "".join(c for c in value if c.isdigit())
    if len(digits) == 10:
        return True, value, 0.95
    return False, value, 0.0


# ============================================================
# STAGE 4 – VALIDATION & ARBITRATION
# ============================================================

def validate_and_arbitrate(
    merged_fields: Dict,
    ocr_confidence: float,
    stage_breakdown: Dict
) -> Tuple[Dict, float]:
    """
    Final validation with header blocking enabled.
    """

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

        # -------- confidence floor --------
        floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
        if confidence < floor or not value:
            continue

        # -------- validation --------
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
        3
    )

    return validated, final_confidence


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def validate_output(structured: Dict, confidence: float):
    """Legacy function for backward compatibility"""
    return validate_and_arbitrate(structured, confidence, {"stage1": structured})