"""
Stage 2 — Semantic Gap Filler  (SC + TE)
=========================================
This is the SC+TE agent in the routing table.

  SC  = Rule-based semantic extraction (this file)
  TE  = GLiNER token-entity extraction (stage2_5_gliner_agent)

Called by the orchestrator for approaches:
  SC+TE, SC+TE→DTE, SC+TE+LATE, SC→SARDE→LATE

Contract:
  • Only fills MISSING fields (never overrides Stage 1)
  • Penalized confidence (max 0.85)
  • Calls GLiNER internally for AI-assisted gap fill
"""

from typing import List, Dict, Optional
import re


# ============================================================
# MAIN ENTRYPOINT — called by orchestrator
# ============================================================

def extract_with_ner(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Extract missing fields using rules (SC) + AI (TE).

    Args:
        lines: OCR text lines
        missing_fields: field names that are still missing

    Returns:
        Dict of field_name → {value, confidence, source}
    """
    if not lines or not missing_fields:
        return {}

    # --- SC: Rule-based semantic extraction (fast) ---
    rule_based = _extract_with_rules(lines, missing_fields)

    # Early exit if all fields found
    if len(rule_based) >= len(missing_fields):
        return rule_based

    # --- TE: GLiNER AI extraction for remaining gaps ---
    still_missing = [f for f in missing_fields if f not in rule_based]
    if still_missing:
        ai_results = _extract_with_gliner_safe(
            "\n".join(lines), still_missing)
        for field, data in ai_results.items():
            if field not in rule_based:
                rule_based[field] = data

    return rule_based


# ============================================================
# SC — RULE-BASED SEMANTIC EXTRACTION
# ============================================================

def _extract_with_rules(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Enhanced rule-based extraction.
    Scans lines for label:value patterns and contextual hints.
    """
    out: Dict[str, Dict] = {}

    for idx, line in enumerate(lines):
        if len(out) >= len(missing_fields):
            break

        clean = _semantic_cleanup(line)
        ll = line.lower()

        # --- Policy Number ---
        if "policy_number" in missing_fields and "policy_number" not in out:
            policy = _extract_policy_number(line)
            if policy:
                out["policy_number"] = {
                    "value": policy,
                    "confidence": 0.85,
                    "source": "sc_policy",
                }

        # --- Insured Name ---
        if "insured_name" in missing_fields and "insured_name" not in out:
            if ":" in line and any(
                k in ll for k in ("insured", "name", "policyholder")
            ):
                _, _, value = line.partition(":")
                value = value.strip()
                if _valid_name(value):
                    out["insured_name"] = {
                        "value": value,
                        "confidence": 0.82,
                        "source": "sc_inline_name",
                    }
            elif _valid_name(clean):
                out["insured_name"] = {
                    "value": clean,
                    "confidence": 0.75,
                    "source": "sc_contextual_name",
                }

        # --- Carrier Name ---
        if "carrier_name" in missing_fields and "carrier_name" not in out:
            if "insurance" in ll:
                if any(w in ll for w in ("company", "co", "exchange",
                                          "group", "mutual", "corp")):
                    if not any(w in ll for w in ("agency", "agent",
                                                  "services")):
                        out["carrier_name"] = {
                            "value": line.strip().upper(),
                            "confidence": 0.82,
                            "source": "sc_carrier",
                        }

        # --- Address ---
        if ("mailing_address" in missing_fields
                or "property_address" in missing_fields):
            if _valid_address(clean):
                field = (
                    "property_address"
                    if "property_address" in missing_fields
                    else "mailing_address"
                )
                if field not in out:
                    out[field] = {
                        "value": clean,
                        "confidence": 0.72,
                        "source": "sc_address",
                    }

        # --- Loan Number ---
        if "loan_number" in missing_fields and "loan_number" not in out:
            loan = _extract_loan_number(line)
            if loan:
                out["loan_number"] = {
                    "value": loan,
                    "confidence": 0.82,
                    "source": "sc_loan",
                }

        # --- Mortgage Company ---
        if "mortgage_company" in missing_fields and "mortgage_company" not in out:
            if any(k in ll for k in ("mortgagee", "lender", "loss payee")):
                if ":" in line:
                    _, _, value = line.partition(":")
                    value = value.strip()
                    if value and len(value) > 5:
                        # Clean ISAOA/ATIMA suffixes
                        value = re.sub(
                            r'\s+(ISAOA|ATIMA|ISAOA/ATIMA).*$', '',
                            value, flags=re.I)
                        out["mortgage_company"] = {
                            "value": value,
                            "confidence": 0.80,
                            "source": "sc_mortgage",
                        }

        # --- Dates ---
        if "effective_date" in missing_fields and "effective_date" not in out:
            if any(k in ll for k in ("effective", "start", "begin")):
                d = _extract_date(line)
                if d:
                    out["effective_date"] = {
                        "value": d,
                        "confidence": 0.85,
                        "source": "sc_date",
                    }

        if "expiration_date" in missing_fields and "expiration_date" not in out:
            if any(k in ll for k in ("expir", "end", "term")):
                d = _extract_date(line)
                if d:
                    out["expiration_date"] = {
                        "value": d,
                        "confidence": 0.85,
                        "source": "sc_date",
                    }

        # --- Total Premium ---
        if "total_premium" in missing_fields and "total_premium" not in out:
            if any(k in ll for k in ("total premium", "annual premium",
                                      "total amount")):
                m = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', line)
                if m:
                    out["total_premium"] = {
                        "value": "$" + m.group(1),
                        "confidence": 0.83,
                        "source": "sc_premium",
                    }

    return out


# ============================================================
# TE — GLINER WRAPPER (safe import)
# ============================================================

def _extract_with_gliner_safe(
    text: str,
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Safe wrapper for GLiNER (Token Entity) extraction.
    Returns empty dict if GLiNER is not installed.
    """
    try:
        from agents.stage2_5_gliner_agent import extract_with_gliner
        return extract_with_gliner(
            text, missing_fields, confidence_threshold=0.65)
    except ImportError:
        return {}
    except Exception as e:
        print(f"[SC+TE] GLiNER failed: {e}")
        return {}


# ============================================================
# EXTRACTORS
# ============================================================

def _extract_policy_number(line: str) -> Optional[str]:
    """Extract policy number from line."""
    ll = line.lower()
    if ":" in line and any(
        k in ll for k in ("policy number", "policy no", "policy #")
    ):
        _, _, value = line.partition(":")
        value = value.strip().replace(" ", "")
        if _valid_policy_number(value):
            return value

    # Fallback: scan for alphanumeric policy-like tokens
    pattern = re.compile(r'\b[A-Z0-9]{2,}[-\s]?[A-Z0-9]{4,}\b')
    for match in pattern.findall(line):
        v = match.replace(" ", "")
        if _valid_policy_number(v):
            return v
    return None


def _extract_loan_number(line: str) -> Optional[str]:
    """Extract loan number from line."""
    ll = line.lower()
    if any(k in ll for k in ("loan number", "loan #", "loan no",
                               "loan id")):
        if ":" in line:
            _, _, value = line.partition(":")
            value = value.strip()
            if _valid_loan_number(value):
                return value
        # Scan for digit sequences
        for token in line.split():
            digits = "".join(c for c in token if c.isdigit())
            if len(digits) >= 7 and _valid_loan_number(digits):
                return digits
    return None


def _extract_date(line: str) -> Optional[str]:
    """Extract first date from line."""
    # Written format: January 15, 2024
    m = re.search(
        r"((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        line, re.I)
    if m:
        return m.group(1)
    # Numeric format: 01/15/2024
    m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", line)
    if m:
        return m.group(1)
    return None


# ============================================================
# CLEANUP
# ============================================================

def _semantic_cleanup(text: str) -> str:
    """Remove dates, dollar amounts, and normalize whitespace."""
    text = re.sub(r"\b[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}", "", text)
    text = re.sub(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "", text)
    text = re.sub(r"\$[\d,]+(\.\d{2})?", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# VALIDATORS
# ============================================================

def _valid_policy_number(text: str) -> bool:
    if not text or len(text) < 5:
        return False
    if re.search(r"\(\d{3}\)", text):
        return False
    if re.fullmatch(r"\d{5}(-\d{4})?", text):
        return False
    digits = sum(c.isdigit() for c in text)
    return digits >= 4 and 5 <= len(text) <= 30


def _valid_loan_number(text: str) -> bool:
    if not text:
        return False
    digits = sum(c.isdigit() for c in text)
    return digits >= 6 and 6 <= len(text) <= 25


def _valid_name(text: str) -> bool:
    if not text or ":" in text:
        return False
    has_entity = any(
        w in text.lower()
        for w in ("llc", "inc", "corp", "company", "trust")
    )
    if any(c.isdigit() for c in text) and not has_entity:
        return False
    ll = text.lower()
    bad = ("policy", "coverage", "notice", "summary", "premium",
           "billing", "endorsement", "declarations", "page",
           "mortgagee", "agency", "agent", "services")
    if any(b in ll for b in bad):
        return False
    words = text.split()
    if has_entity:
        return 2 <= len(words) <= 10
    return 2 <= len(words) <= 6


def _valid_address(text: str) -> bool:
    if not text:
        return False
    ll = text.lower()
    if "po box" in ll or "p.o. box" in ll:
        return True
    if re.search(
        r"\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|"
        r"lane|ln|drive|dr|ct|court)\b", text, re.I
    ):
        return True
    if re.search(r"\b[A-Z]{2}\s*\d{5}", text):
        return True
    has_number = bool(re.search(r"\d+", text))
    return has_number and len(text.split()) >= 3