"""
Stage 3 – Layout & Spatial Reasoning (NON-AUTHORITATIVE)
======================================================

Purpose:
- Recover remaining missing fields using spatial relationships
- Weakest signal in the pipeline
- NEVER overrides Stage 1 or Stage 2
- Stateless
"""

from typing import List, Dict, Tuple, Optional
import math
import re


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def extract_with_layoutxlm(
    ambiguous_regions: List[Dict],
    relations: List[Tuple],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Spatial extraction for missing fields only.
    """

    if not ambiguous_regions or not missing_fields:
        return {}

    extracted: Dict[str, Dict] = {}

    # Strategy 1 — relations (strongest spatial signal)
    extracted.update(
        _extract_from_relations(relations, missing_fields)
    )

    # Strategy 2 — tables
    extracted.update(
        _extract_from_tables(ambiguous_regions, missing_fields)
    )

    # Strategy 3 — proximity (weakest)
    extracted.update(
        _extract_from_proximity(ambiguous_regions, missing_fields)
    )

    return extracted


# ============================================================
# STRATEGY 1 — RELATION-BASED
# ============================================================

def _extract_from_relations(
    relations: List[Tuple],
    missing_fields: List[str],
) -> Dict[str, Dict]:

    extracted = {}

    LABEL_MAP = {
        "policy number": "policy_number",
        "policy no": "policy_number",
        "insured name": "insured_name",
        "named insured": "insured_name",
        "effective date": "effective_date",
        "expiration date": "expiration_date",
        "mailing address": "mailing_address",
        "property address": "property_address",
        "total premium": "total_premium",
        "deductible": "deductible",
    }

    for rel in relations:
        if len(rel) != 4:
            continue

        label, rel_type, value, confidence = rel

        if rel_type != "HAS_VALUE":
            continue

        field = LABEL_MAP.get(label.lower().strip(":"))
        if not field or field not in missing_fields:
            continue

        if not _basic_sanity(field, value):
            continue

        extracted[field] = {
            "value": value.strip(),
            "confidence": round(confidence * 0.80, 3),
            "source": "layout",
            "method": "relation",
        }

    return extracted


# ============================================================
# STRATEGY 2 — TABLE PARSING
# ============================================================

def _extract_from_tables(
    regions: List[Dict],
    missing_fields: List[str],
) -> Dict[str, Dict]:

    extracted = {}

    tables = _detect_tables(regions)
    for table in tables:
        headers = table[0]
        rows = table[1:]

        header_map = {}
        for idx, h in enumerate(headers):
            t = h["text"].lower()
            if "premium" in t:
                header_map[idx] = "total_premium"
            elif "deductible" in t:
                header_map[idx] = "deductible"

        for row in rows:
            for idx, cell in enumerate(row):
                field = header_map.get(idx)
                if field and field in missing_fields:
                    if _basic_sanity(field, cell["text"]):
                        extracted[field] = {
                            "value": cell["text"].strip(),
                            "confidence": round(cell.get("confidence", 0.8) * 0.78, 3),
                            "source": "layout",
                            "method": "table",
                        }

    return extracted


def _detect_tables(elements: List[Dict]) -> List[List[List[Dict]]]:
    if len(elements) < 6:
        return []

    sorted_elems = sorted(elements, key=lambda e: e["box"][1])
    rows = []
    current = [sorted_elems[0]]
    current_y = sorted_elems[0]["box"][1]

    for el in sorted_elems[1:]:
        y = el["box"][1]
        if abs(y - current_y) < 30:
            current.append(el)
        else:
            if len(current) >= 2:
                rows.append(current)
            current = [el]
            current_y = y

    if len(current) >= 2:
        rows.append(current)

    return [rows] if len(rows) >= 2 else []


# ============================================================
# STRATEGY 3 — PROXIMITY
# ============================================================

def _extract_from_proximity(
    regions: List[Dict],
    missing_fields: List[str],
) -> Dict[str, Dict]:

    extracted = {}

    labels = [r for r in regions if r.get("role") == "label"]
    values = [r for r in regions if r.get("role") == "value"]

    FIELD_LABELS = {
        "policy_number": ["policy"],
        "insured_name": ["insured", "policyholder"],
        "effective_date": ["effective"],
        "expiration_date": ["expiration"],
        "total_premium": ["premium"],
        "deductible": ["deductible"],
    }

    for field, keywords in FIELD_LABELS.items():
        if field not in missing_fields:
            continue

        label = _find_label(labels, keywords)
        if not label:
            continue

        value = _nearest_value(label, values)
        if not value:
            continue

        if not _basic_sanity(field, value["text"]):
            continue

        extracted[field] = {
            "value": value["text"].strip(),
            "confidence": round(value.get("confidence", 0.8) * 0.75, 3),
            "source": "layout",
            "method": "proximity",
        }

    return extracted


def _find_label(labels: List[Dict], keywords: List[str]) -> Optional[Dict]:
    for l in labels:
        t = l["text"].lower()
        if any(k in t for k in keywords):
            return l
    return None


def _nearest_value(label: Dict, values: List[Dict]) -> Optional[Dict]:
    lx1, ly1, lx2, ly2 = label["box"]
    lc_x = (lx1 + lx2) / 2
    lc_y = (ly1 + ly2) / 2

    best = None
    best_dist = float("inf")

    for v in values:
        vx1, vy1, vx2, vy2 = v["box"]
        vc_x = (vx1 + vx2) / 2
        vc_y = (vy1 + vy2) / 2

        dist = math.hypot(vc_x - lc_x, vc_y - lc_y)
        if dist < best_dist and dist < 200:
            best = v
            best_dist = dist

    return best


# ============================================================
# BASIC SANITY CHECKS (NOT VALIDATION)
# ============================================================

def _basic_sanity(field: str, value: str) -> bool:
    if not value or len(value.strip()) < 2:
        return False

    if field in {"policy_number", "loan_number"}:
        return sum(c.isdigit() for c in value) >= 3

    if field == "insured_name":
        return not any(c.isdigit() for c in value)

    if field in {"total_premium", "deductible"}:
        return any(c.isdigit() for c in value)

    return True
