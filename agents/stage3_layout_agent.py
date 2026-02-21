"""
Stage 3 – Layout / Spatial Fallback Extractor (LOCKED)
=====================================================
Purpose:
- LAST RESORT extraction
- Uses layout / positional hints only
- NEVER overrides Stage 1 / 2 / 2.5
- NEVER creates policy_number
"""

from typing import Dict, List


# ============================================================
# PUBLIC API (EXPECTED BY ORCHESTRATOR)
# ============================================================

def extract_with_layoutxlm(
    layout_elements: List[Dict],
    relations: List[Dict],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Compatibility wrapper expected by orchestrator.

    Stage-3 is intentionally weak and conservative.
    """

    if not missing_fields:
        return {}

    out: Dict[str, Dict] = {}

    # Very defensive: only attempt name / address recovery
    for el in layout_elements or []:
        text = (el.get("text") or "").strip()
        if not text:
            continue

        # -----------------------------
        # INSURED NAME (layout guess)
        # -----------------------------
        if (
            "insured_name" in missing_fields
            and "insured_name" not in out
            and _looks_like_name(text)
        ):
            out["insured_name"] = _candidate(
                text,
                source="stage3_layout_name",
                confidence=0.65,
            )
            continue

        # -----------------------------
        # PROPERTY / MAILING ADDRESS
        # -----------------------------
        if (
            "property_address" in missing_fields
            and "property_address" not in out
            and _looks_like_address(text)
        ):
            out["property_address"] = _candidate(
                text,
                source="stage3_layout_address",
                confidence=0.62,
            )
            continue

        if (
            "mailing_address" in missing_fields
            and "mailing_address" not in out
            and _looks_like_address(text)
        ):
            out["mailing_address"] = _candidate(
                text,
                source="stage3_layout_address",
                confidence=0.62,
            )
            continue

    return out


# ============================================================
# HEURISTICS (VERY WEAK BY DESIGN)
# ============================================================

def _looks_like_name(text: str) -> bool:
    if ":" in text or any(c.isdigit() for c in text):
        return False

    words = text.replace(",", "").split()
    if not (2 <= len(words) <= 5):
        return False

    caps = sum(w[:1].isupper() for w in words if w)
    return caps >= 2


def _looks_like_address(text: str) -> bool:
    t = text.lower()

    if "po box" in t:
        return True

    return any(
        k in t
        for k in (
            " street",
            " st ",
            " avenue",
            " ave",
            " road",
            " rd",
            " blvd",
            " lane",
            " drive",
            " ct",
        )
    )


# ============================================================
# OUTPUT FORMAT
# ============================================================

def _candidate(value: str, source: str, confidence: float) -> Dict:
    return {
        "value": value.strip(),
        "confidence": min(confidence, 0.70),
        "source": source,
        "method": "layout",
    }
