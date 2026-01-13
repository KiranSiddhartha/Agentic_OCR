# # agents/stage1_deterministic_agent.py
# # Stage 1: Deterministic Extraction - HARDENED
# # Optimized for insurance document field extraction
# # NOTE: No functionality removed. Only defensive validation added.

# import re
# from typing import List, Dict, Optional
# from datetime import datetime

# # ============================================================
# # MAIN ENTRY
# # ============================================================

# def extract_with_regex(lines: List[str], layout_elements: List[Dict] = None) -> Dict[str, Dict]:
#     """
#     Stage 1: Extract fields using deterministic regex patterns.
#     Hardened to block form IDs, endorsements, and section noise.
#     """

#     text = "\n".join(lines)
#     fields = {}

#     # ============================================================
#     # POLICY NUMBER
#     # ============================================================

#     policy_patterns = [
#         (r'Policy\s+number[:\s]+([A-Z0-9\-]{5,30})', 'policy_number_lowercase', 0.98),
#         (r'Policy\s+Number[:\s]+([A-Z0-9\-]{5,30})', 'policy_number_colon', 0.98),
#         (r'Policy\s+No\.?[:\s]+([A-Z0-9\-]{5,30})', 'policy_no_colon', 0.97),
#         (r'Policy\s*#[:\s]+([A-Z0-9\-]{5,30})', 'policy_hash', 0.96),
#         (r'Certificate\s+Number[:\s]+([A-Z0-9\-]{5,30})', 'certificate_number', 0.96),
#     ]

#     for pattern, name, conf in policy_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             val = m.group(1).strip()
#             if _validate_policy_number(val):
#                 fields["policy_number"] = {
#                     "value": val,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # EFFECTIVE / EXPIRATION DATES
#     # ============================================================

#     date_patterns = [
#         (r'Effective\s+Date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', "effective_word", "effective_date", 0.97),
#         (r'Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', "effective_numeric", "effective_date", 0.97),
#         (r'Expiration\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', "expiration_numeric", "expiration_date", 0.97),
#     ]

#     for pattern, name, field, conf in date_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             norm = _normalize_date(m.group(1))
#             if norm:
#                 fields[field] = {
#                     "value": norm,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }

#     # ============================================================
#     # INSURED NAME
#     # ============================================================

#     name_patterns = [
#         (r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s\.,-]{2,60})', "named_insured", 0.97),
#         (r'Insured\s+Name[:\s]+([A-Z][A-Za-z\s\.,-]{2,60})', "insured_name", 0.96),
#     ]

#     for pattern, name, conf in name_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             val = m.group(1).strip().rstrip(".,")
#             if _validate_name(val):
#                 fields["insured_name"] = {
#                     "value": val,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # PROPERTY ADDRESS (HARDENED)
#     # ============================================================

#     property_patterns = [
#         (r'Location\s+of\s+Insured\s+Property[:\s]+([^\n]+)', "location_of_property", 0.96),
#         (r'Property\s+Address[:\s]+([^\n]+)', "property_address", 0.95),
#     ]

#     for pattern, name, conf in property_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             val = re.sub(r'\s+', ' ', m.group(1)).strip()
#             if _validate_property_address(val):
#                 fields["property_address"] = {
#                     "value": val,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # MAILING ADDRESS
#     # ============================================================

#     mailing_patterns = [
#         (r'Mailing\s+Address[:\s]+([^\n]+)', "mailing_address", 0.95),
#         (r'P\.?\s*O\.?\s*Box\s+\d+[^,\n]*,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5}', "po_box", 0.94),
#     ]

#     for pattern, name, conf in mailing_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             val = re.sub(r'\s+', ' ', m.group(0)).strip()
#             if _validate_address(val):
#                 fields["mailing_address"] = {
#                     "value": val,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # LOAN NUMBER
#     # ============================================================

#     loan_patterns = [
#         (r'Loan\s+Number[:\s]+([A-Z0-9\-]{5,30})', "loan_number", 0.97),
#     ]

#     for pattern, name, conf in loan_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             val = m.group(1).strip()
#             if _validate_loan_number(val):
#                 fields["loan_number"] = {
#                     "value": val,
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # TOTAL PREMIUM (HARDENED)
#     # ============================================================

#     premium_patterns = [
#         (r'Total\s+Premium[:\s]+\$\s*([\d,]+)', "total_premium", 0.97),
#     ]

#     for pattern, name, conf in premium_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             amt = m.group(1)
#             if _validate_currency(amt):
#                 fields["total_premium"] = {
#                     "value": f"${amt}",
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     # ============================================================
#     # DWELLING COVERAGE (HARDENED)
#     # ============================================================

#     dwelling_patterns = [
#         (r'Dwelling[:\s]+\$\s*([\d,]+)', "dwelling_coverage", 0.96),
#         (r'Coverage\s+A[:\s]+\$\s*([\d,]+)', "coverage_a", 0.95),
#     ]

#     for pattern, name, conf in dwelling_patterns:
#         m = re.search(pattern, text, re.IGNORECASE)
#         if m:
#             amt = m.group(1)
#             if _validate_currency(amt):
#                 fields["dwelling_coverage"] = {
#                     "value": f"${amt}",
#                     "confidence": conf,
#                     "source": "deterministic_regex",
#                     "pattern_matched": name,
#                 }
#                 break

#     return fields


# # ============================================================
# # VALIDATION HELPERS (HARDENED)
# # ============================================================

# def _validate_policy_number(val: str) -> bool:
#     if not val or len(val) < 5:
#         return False
#     if re.match(r'[A-Z]{2}\s\d{2}\s\d{2}', val):
#         return False
#     return sum(c.isdigit() for c in val) >= 3


# def _validate_loan_number(val: str) -> bool:
#     return bool(val and sum(c.isdigit() for c in val) >= 4)


# def _validate_name(val: str) -> bool:
#     if not val or len(val.split()) < 2:
#         return False
#     if any(c.isdigit() for c in val):
#         return False
#     if val.lower() in {"and", "or", "the"}:
#         return False
#     return True


# def _validate_address(val: str) -> bool:
#     if not val or len(val) < 8:
#         return False
#     if any(k in val.lower() for k in ["endorsement", "form", "section"]):
#         return False
#     return True


# def _validate_property_address(val: str) -> bool:
#     if not _validate_address(val):
#         return False
#     return bool(re.search(r'\d+\s+.+(st|ave|rd|dr|ln|blvd)', val.lower()))


# def _validate_currency(val: str) -> bool:
#     try:
#         amt = float(val.replace(",", ""))
#         return 10 <= amt <= 500000
#     except Exception:
#         return False


# # ============================================================
# # NORMALIZATION
# # ============================================================

# def _normalize_date(date_str: str) -> Optional[str]:
#     date_str = date_str.strip()

#     word = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', date_str)
#     if word:
#         month_map = {
#             "january": "01", "february": "02", "march": "03", "april": "04",
#             "may": "05", "june": "06", "july": "07", "august": "08",
#             "september": "09", "october": "10", "november": "11", "december": "12",
#         }
#         m, d, y = word.groups()
#         mm = month_map.get(m.lower())
#         if mm:
#             return f"{mm}/{d.zfill(2)}/{y}"

#     num = date_str.replace("-", "/")
#     parts = num.split("/")
#     if len(parts) == 3 and all(p.isdigit() for p in parts):
#         return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"

#     return None


"""
Stage 1 – Deterministic Extraction (CRITICAL)

Design goals:
- MAXIMUM RECALL
- Minimal rejection
- OCR-tolerant
- No cross-field logic
- No arbitration
"""

import re
from typing import List, Dict, Optional

# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def extract_with_regex(
    lines: List[str],
    layout_elements: Optional[List[Dict]] = None,
) -> Dict[str, Dict]:
    """
    Deterministic extraction using regex + loose heuristics.
    """

    text = "\n".join(lines)
    fields: Dict[str, Dict] = {}

    # --------------------------------------------------------
    # CARRIER
    # --------------------------------------------------------

    carriers = [
        "STATE FARM", "ALLSTATE", "FARMERS", "AAA", "CSAA",
        "ENCOMPASS", "ERIE", "TRAVELERS", "NATIONWIDE",
        "LIBERTY MUTUAL", "USAA", "PROGRESSIVE",
    ]

    for l in lines[:15]:
        for c in carriers:
            if c in l.upper():
                fields["carrier"] = _field(l.strip(), 0.98, "carrier_match")
                break
        if "carrier" in fields:
            break

    # --------------------------------------------------------
    # POLICY NUMBER
    # --------------------------------------------------------

    _regex(
        fields,
        "policy_number",
        text,
        [
            r'policy\s*(number|no|#)\s*[:\-]?\s*([A-Z0-9\-]{5,30})',
            r'certificate\s*number\s*[:\-]?\s*([A-Z0-9\-]{5,30})',
        ],
        min_digits=3,
        confidence=0.98,
    )

    # --------------------------------------------------------
    # INSURED NAME
    # --------------------------------------------------------

    for i, l in enumerate(lines):
        ll = l.lower()

        if any(k in ll for k in ["insured", "named insured", "policyholder"]):
            val = _next_nonempty(lines, i)
            if val and _looks_like_name(val):
                fields["insured_name"] = _field(val, 0.96, "insured_context")
                break

    # --------------------------------------------------------
    # EFFECTIVE / EXPIRATION / ISSUE / NOTICE DATES
    # --------------------------------------------------------

    _date_field(fields, text, "effective_date", ["effective"])
    _date_field(fields, text, "expiration_date", ["expiration", "expires"])
    _date_field(fields, text, "issue_date", ["issue", "issued"])
    _date_field(fields, text, "notice_effective_date", ["notice effective"])
    _date_field(fields, text, "cancellation_date", ["cancellation", "cancelled"])

    # --------------------------------------------------------
    # PROPERTY ADDRESS
    # --------------------------------------------------------

    for i, l in enumerate(lines):
        if any(k in l.lower() for k in ["property location", "location of insured"]):
            val = _next_nonempty(lines, i)
            if _looks_like_address(val):
                fields["property_address"] = _field(val, 0.95, "property_context")
                break

    # --------------------------------------------------------
    # MAILING ADDRESS
    # --------------------------------------------------------

    for i, l in enumerate(lines):
        if any(k in l.lower() for k in ["mailing address", "insured mailing"]):
            val = _next_nonempty(lines, i)
            if _looks_like_address(val):
                fields["mailing_address"] = _field(val, 0.94, "mailing_context")
                break

    # --------------------------------------------------------
    # MORTGAGE / PAYEE
    # --------------------------------------------------------

    for i, l in enumerate(lines):
        if any(k in l.lower() for k in ["mortgagee", "loss payee", "lender"]):
            val = _next_nonempty(lines, i)
            if val:
                fields["mortgage"] = _field(val, 0.94, "mortgage_context")
                break

    # --------------------------------------------------------
    # LOAN NUMBER
    # --------------------------------------------------------

    _regex(
        fields,
        "loan_number",
        text,
        [r'loan\s*(number|#)\s*[:\-]?\s*([A-Z0-9\-]{5,30})'],
        min_digits=4,
        confidence=0.97,
    )

    # --------------------------------------------------------
    # PREMIUM / BALANCE DUE
    # --------------------------------------------------------

    _money_field(fields, text, "total_premium", ["total premium"])
    _money_field(fields, text, "balance_due", ["balance due", "amount due"])

    # --------------------------------------------------------
    # DWELLING COVERAGE
    # --------------------------------------------------------

    _money_field(fields, text, "dwelling_coverage", ["dwelling", "coverage a"])

    # --------------------------------------------------------
    # AGENT INFO
    # --------------------------------------------------------

    _regex(
        fields,
        "agent_phone",
        text,
        [r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'],
        confidence=0.93,
    )

    # --------------------------------------------------------
    # REMIT / PAYEE INFO
    # --------------------------------------------------------

    for l in lines:
        if any(k in l.lower() for k in ["remit to", "make payable", "payable to"]):
            fields["remit_info"] = _field(l.strip(), 0.92, "remit_context")
            break

    return fields


# ============================================================
# HELPERS
# ============================================================

def _field(value: str, confidence: float, source: str) -> Dict:
    return {
        "value": value.strip(),
        "confidence": confidence,
        "source": source,
    }


def _regex(
    fields: Dict,
    name: str,
    text: str,
    patterns: List[str],
    min_digits: int = 0,
    confidence: float = 0.95,
):
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            val = m.group(m.lastindex).strip()
            if min_digits and sum(c.isdigit() for c in val) < min_digits:
                continue
            fields[name] = _field(val, confidence, p)
            return


def _date_field(fields: Dict, text: str, name: str, keywords: List[str]):
    for k in keywords:
        m = re.search(
            rf'{k}.*?(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|[A-Z][a-z]+ \d{{1,2}}, \d{{4}})',
            text,
            re.I,
        )
        if m:
            fields[name] = _field(m.group(1), 0.95, k)
            return


def _money_field(fields: Dict, text: str, name: str, keywords: List[str]):
    for k in keywords:
        m = re.search(rf'{k}.*?\$([\d,]+)', text, re.I)
        if m:
            fields[name] = _field(f"${m.group(1)}", 0.95, k)
            return


def _next_nonempty(lines: List[str], idx: int) -> Optional[str]:
    for j in range(idx + 1, min(idx + 6, len(lines))):
        if lines[j].strip():
            return lines[j].strip()
    return None


def _looks_like_name(val: str) -> bool:
    if any(char.isdigit() for char in val):
        return False
    words = val.split()
    return 1 <= len(words) <= 6


def _looks_like_address(val: str) -> bool:
    if not val:
        return False
    if "po box" in val.lower():
        return True
    return bool(re.search(r'\d+.*\b[A-Z]{2}\b.*\d{5}', val))
