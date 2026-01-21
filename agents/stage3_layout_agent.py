# """
# Stage 3 – Layout & Spatial Reasoning (NON-AUTHORITATIVE)
# ======================================================

# Purpose:
# - Recover remaining missing fields using spatial relationships
# - Weakest signal in the pipeline
# - NEVER overrides Stage 1 or Stage 2
# - Stateless
# """

# from typing import List, Dict, Tuple, Optional
# import math
# import re


# # ============================================================
# # MAIN ENTRYPOINT
# # ============================================================

# def extract_with_layoutxlm(
#     ambiguous_regions: List[Dict],
#     relations: List[Tuple],
#     missing_fields: List[str],
# ) -> Dict[str, Dict]:
#     """
#     Spatial extraction for missing fields only.
#     """

#     if not ambiguous_regions or not missing_fields:
#         return {}

#     extracted: Dict[str, Dict] = {}

#     # Strategy 1 — relations (strongest spatial signal)
#     extracted.update(
#         _extract_from_relations(relations, missing_fields)
#     )

#     # Strategy 2 — tables
#     extracted.update(
#         _extract_from_tables(ambiguous_regions, missing_fields)
#     )

#     # Strategy 3 — proximity (weakest)
#     extracted.update(
#         _extract_from_proximity(ambiguous_regions, missing_fields)
#     )

#     return extracted


# # ============================================================
# # STRATEGY 1 — RELATION-BASED
# # ============================================================

# def _extract_from_relations(
#     relations: List[Tuple],
#     missing_fields: List[str],
# ) -> Dict[str, Dict]:

#     extracted = {}

#     LABEL_MAP = {
#         "policy number": "policy_number",
#         "policy no": "policy_number",
#         "insured name": "insured_name",
#         "named insured": "insured_name",
#         "effective date": "effective_date",
#         "expiration date": "expiration_date",
#         "mailing address": "mailing_address",
#         "property address": "property_address",
#         "total premium": "total_premium",
#         "deductible": "deductible",
#     }

#     for rel in relations:
#         if len(rel) != 4:
#             continue

#         label, rel_type, value, confidence = rel

#         if rel_type != "HAS_VALUE":
#             continue

#         field = LABEL_MAP.get(label.lower().strip(":"))
#         if not field or field not in missing_fields:
#             continue

#         if not _basic_sanity(field, value):
#             continue

#         extracted[field] = {
#             "value": value.strip(),
#             "confidence": round(confidence * 0.80, 3),
#             "source": "layout",
#             "method": "relation",
#         }

#     return extracted


# # ============================================================
# # STRATEGY 2 — TABLE PARSING
# # ============================================================

# def _extract_from_tables(
#     regions: List[Dict],
#     missing_fields: List[str],
# ) -> Dict[str, Dict]:

#     extracted = {}

#     tables = _detect_tables(regions)
#     for table in tables:
#         headers = table[0]
#         rows = table[1:]

#         header_map = {}
#         for idx, h in enumerate(headers):
#             t = h["text"].lower()
#             if "premium" in t:
#                 header_map[idx] = "total_premium"
#             elif "deductible" in t:
#                 header_map[idx] = "deductible"

#         for row in rows:
#             for idx, cell in enumerate(row):
#                 field = header_map.get(idx)
#                 if field and field in missing_fields:
#                     if _basic_sanity(field, cell["text"]):
#                         extracted[field] = {
#                             "value": cell["text"].strip(),
#                             "confidence": round(cell.get("confidence", 0.8) * 0.78, 3),
#                             "source": "layout",
#                             "method": "table",
#                         }

#     return extracted


# def _detect_tables(elements: List[Dict]) -> List[List[List[Dict]]]:
#     if len(elements) < 6:
#         return []

#     sorted_elems = sorted(elements, key=lambda e: e["box"][1])
#     rows = []
#     current = [sorted_elems[0]]
#     current_y = sorted_elems[0]["box"][1]

#     for el in sorted_elems[1:]:
#         y = el["box"][1]
#         if abs(y - current_y) < 30:
#             current.append(el)
#         else:
#             if len(current) >= 2:
#                 rows.append(current)
#             current = [el]
#             current_y = y

#     if len(current) >= 2:
#         rows.append(current)

#     return [rows] if len(rows) >= 2 else []


# # ============================================================
# # STRATEGY 3 — PROXIMITY
# # ============================================================

# def _extract_from_proximity(
#     regions: List[Dict],
#     missing_fields: List[str],
# ) -> Dict[str, Dict]:

#     extracted = {}

#     labels = [r for r in regions if r.get("role") == "label"]
#     values = [r for r in regions if r.get("role") == "value"]

#     FIELD_LABELS = {
#         "policy_number": ["policy"],
#         "insured_name": ["insured", "policyholder"],
#         "effective_date": ["effective"],
#         "expiration_date": ["expiration"],
#         "total_premium": ["premium"],
#         "deductible": ["deductible"],
#     }

#     for field, keywords in FIELD_LABELS.items():
#         if field not in missing_fields:
#             continue

#         label = _find_label(labels, keywords)
#         if not label:
#             continue

#         value = _nearest_value(label, values)
#         if not value:
#             continue

#         if not _basic_sanity(field, value["text"]):
#             continue

#         extracted[field] = {
#             "value": value["text"].strip(),
#             "confidence": round(value.get("confidence", 0.8) * 0.75, 3),
#             "source": "layout",
#             "method": "proximity",
#         }

#     return extracted


# def _find_label(labels: List[Dict], keywords: List[str]) -> Optional[Dict]:
#     for l in labels:
#         t = l["text"].lower()
#         if any(k in t for k in keywords):
#             return l
#     return None


# def _nearest_value(label: Dict, values: List[Dict]) -> Optional[Dict]:
#     lx1, ly1, lx2, ly2 = label["box"]
#     lc_x = (lx1 + lx2) / 2
#     lc_y = (ly1 + ly2) / 2

#     best = None
#     best_dist = float("inf")

#     for v in values:
#         vx1, vy1, vx2, vy2 = v["box"]
#         vc_x = (vx1 + vx2) / 2
#         vc_y = (vy1 + vy2) / 2

#         dist = math.hypot(vc_x - lc_x, vc_y - lc_y)
#         if dist < best_dist and dist < 200:
#             best = v
#             best_dist = dist

#     return best


# # ============================================================
# # BASIC SANITY CHECKS (NOT VALIDATION)
# # ============================================================

# def _basic_sanity(field: str, value: str) -> bool:
#     if not value or len(value.strip()) < 2:
#         return False

#     if field in {"policy_number", "loan_number"}:
#         return sum(c.isdigit() for c in value) >= 3

#     if field == "insured_name":
#         return not any(c.isdigit() for c in value)

#     if field in {"total_premium", "deductible"}:
#         return any(c.isdigit() for c in value)

#     return True


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
