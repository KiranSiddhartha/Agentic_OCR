"""
Stage 2 – Semantic Gap Filler (NON-AUTHORITATIVE)
================================================
Fills ONLY missing fields after Stage 1.
"""

from typing import List, Dict
import re


def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
    if not lines or not missing_fields:
        return {}

    out: Dict[str, Dict] = {}

    for line in lines:
        clean = _semantic_cleanup(line)

        if "insured_name" in missing_fields and _valid_name(clean):
            out["insured_name"] = _candidate(clean, "semantic_rules", 0.75)

        if (
            "mailing_address" in missing_fields or "property_address" in missing_fields
        ) and _valid_address(clean):
            field = (
                "mailing_address"
                if "mailing_address" in missing_fields
                else "property_address"
            )
            out[field] = _candidate(clean, "semantic_rules", 0.72)

    return out


# ============================================================
# SEMANTIC NORMALIZATION
# ============================================================

def _semantic_cleanup(text: str) -> str:
    # Remove date phrases
    text = re.sub(
        r"\b(Beginning|through|since)?\s*[A-Z][a-z]+ \d{1,2},? \d{4}",
        "",
        text,
    )

    # Remove leading prose
    text = re.sub(r".* for (\d+ .+)", r"\1", text, flags=re.I)

    return text.strip()


# ============================================================
# VALIDATORS
# ============================================================

def _valid_name(text: str) -> bool:
    if ":" in text or any(c.isdigit() for c in text):
        return False
    return 2 <= len(text.split()) <= 6


def _valid_address(text: str) -> bool:
    return bool(
        re.search(r"\d+ .* (st|ave|rd|blvd|ln|dr)", text.lower())
        or "po box" in text.lower()
    )


def _candidate(value: str, source: str, confidence: float) -> Dict:
    return {
        "value": value,
        "confidence": min(confidence, 0.80),
        "source": source,
    }
