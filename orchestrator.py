# # orchestrator.py
# # INTELLIGENT CASCADING HYBRID ARCHITECTURE - ENHANCED
# # Optimized for insurance document field extraction

# from preprocessing import preprocess
# from agents.vision_agent import VisionAgent
# from utils.text_utils import merge_broken_lines
# import hashlib
# import time

# # ============================================================
# # STAGE IMPORTS
# # ============================================================

# from agents.stage1_deterministic_agent import extract_with_regex

# # Stage 2
# try:
#     from agents.stage2_semantic_agent import extract_with_ner
#     STAGE2_AVAILABLE = True
# except ImportError:
#     STAGE2_AVAILABLE = False
#     print("[WARN] Stage 2 (Semantic NER) not available")

# # Stage 3
# try:
#     from agents.stage3_layout_agent import extract_with_layoutxlm
#     from agents.relation_extraction_agent import RelationExtractionAgent
#     STAGE3_AVAILABLE = True
# except ImportError:
#     STAGE3_AVAILABLE = False
#     print("[WARN] Stage 3 (Layout) not available")

# from agents.validation_agent import validate_and_arbitrate

# # Classification
# try:
#     from agents.document_classifier import classify_document
#     from agents.policy_classifier import classify_policy
#     CLASSIFICATION_AVAILABLE = True
# except ImportError:
#     CLASSIFICATION_AVAILABLE = False

# # ============================================================
# # REQUIRED FIELDS
# # ============================================================

# CRITICAL_FIELDS = [
#     "carrier",
#     "policy_number",
#     "insured_name",
#     "effective_date",
#     "expiration_date",
# ]

# IMPORTANT_FIELDS = [
#     "property_address",
#     "loan_number",
#     "mortgage",
#     "total_premium",
#     "dwelling_coverage",
# ]

# OPTIONAL_FIELDS = [
#     "mailing_address",
#     "agent",
#     "agent_phone",
# ]

# ALL_FIELDS = CRITICAL_FIELDS + IMPORTANT_FIELDS + OPTIONAL_FIELDS

# # ============================================================
# # GLOBAL STATE
# # ============================================================

# _PIPELINE_CACHE = {}
# _CACHE_ENABLED = False
# _vision_agent = None

# # ============================================================
# # MAIN PIPELINE
# # ============================================================

# def run_pipeline(image, max_retries=1, debug=False, use_cache=True):

#     cache_key = None  # cache disabled 
#     try:
#         processed = preprocess(image)

#         global _vision_agent
#         if _vision_agent is None:
#             _vision_agent = VisionAgent(use_layoutxlm=STAGE3_AVAILABLE)

#         vision = _vision_agent
#         ocr_results = vision.ocr_engine.run_with_boxes(processed)

#         if not ocr_results or not ocr_results.get("text"):
#             return _create_empty_result("No text detected")

#         lines = ocr_results.get("lines", [])
#         if not lines:
#             lines = [" ".join(ocr_results.get("text", []))]

#         lines = merge_broken_lines([l.strip() for l in lines if l.strip()])

#         layout = []
#         if STAGE3_AVAILABLE:
#             try:
#                 layout = vision.analyze_layout(processed, ocr_results)
#             except Exception:
#                 layout = []

#         # ---------------- STAGE 1 ----------------
#         stage1 = extract_with_regex(lines, layout)
#         missing1 = _identify_missing_fields(stage1)
#         conf1 = _calculate_stage_confidence(stage1)

#         # ---------------- STAGE 2 (STRICT FILL ONLY) ----------------
#         stage2 = {}
#         if STAGE2_AVAILABLE and _should_run_stage2(stage1, missing1, conf1):
#             raw_stage2 = extract_with_ner(lines, missing1)
#             for f, d in raw_stage2.items():
#                 if f not in stage1:
#                     d["confidence"] = max(0.55, d.get("confidence", 0.7) - 0.20)
#                     d["source"] = "semantic_ner"
#                     stage2[f] = d

#         # ---------------- STAGE 3 ----------------
#         combined = {**stage1, **stage2}
#         missing2 = _identify_missing_fields(combined)
#         conf2 = _calculate_stage_confidence(combined)

#         stage3 = {}
#         if STAGE3_AVAILABLE and _should_run_stage3(combined, missing2, conf2, layout):
#             re_agent = RelationExtractionAgent()
#             relations = re_agent.extract_relations(layout, combined)
#             ambiguous = _identify_ambiguous_regions(layout, combined)
#             stage3 = extract_with_layoutxlm(ambiguous, relations, missing2)

#         # ---------------- VALIDATION ----------------
#         merged = _merge_stage_results_hybrid(stage1, stage2, stage3)

#         ocr_conf = ocr_results.get("avg_confidence")
#         if ocr_conf is None:
#             ocr_conf = 0.85

#         final_fields, confidence = validate_and_arbitrate(
#             merged,
#             ocr_conf,
#             {
#                 "stage1": stage1,
#                 "stage2": stage2,
#                 "stage3": stage3,
#             },
#         ) 
        
#         result = {
#             "fields": final_fields,
#             "raw_lines": lines,
#             "confidence": confidence,
#             "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#             "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#         }

#         if use_cache and cache_key:
#             _PIPELINE_CACHE[cache_key] = result

#         return result

#     except Exception as e:
#         return _create_empty_result(str(e))


# # ============================================================
# # ✅ RESTORED: BATCH WRAPPER (REQUIRED BY app.py)
# # ============================================================

# def run_pipeline_batch(images, max_retries=1, debug=False, use_cache=True):
#     """
#     UI-required batch wrapper.
#     SAFE: calls run_pipeline sequentially.
#     """
#     results = []
#     for img in images:
#         results.append(
#             run_pipeline(
#                 img,
#                 max_retries=max_retries,
#                 debug=debug,
#                 use_cache=use_cache,
#             )
#         )
#     return results


# # ============================================================
# # HELPERS
# # ============================================================

# def _identify_missing_fields(fields):
#     required = CRITICAL_FIELDS + IMPORTANT_FIELDS
#     return [f for f in required if f not in fields]

# def _calculate_stage_confidence(fields):
#     if not fields:
#         return 0.0
#     return sum(v.get("confidence", 0.5) for v in fields.values()) / len(fields)

# def _should_run_stage2(stage1, missing, conf):
#     if not missing:
#         return False
#     if conf < 0.95:
#         return True
#     return any(f in missing for f in CRITICAL_FIELDS)

# def _should_run_stage3(fields, missing, conf, layout):
#     if not STAGE3_AVAILABLE or not layout or not missing:
#         return False
#     if conf < 0.85:
#         return True
#     return any(f in missing for f in CRITICAL_FIELDS)

# def _merge_stage_results_hybrid(s1, s2, s3):
#     merged = {}
#     for f in set(s1) | set(s2) | set(s3):
#         candidates = []
#         if f in s1:
#             candidates.append({**s1[f], "priority": 3})
#         if f in s2:
#             candidates.append({**s2[f], "priority": 2})
#         if f in s3:
#             candidates.append({**s3[f], "priority": 1})
#         merged[f] = max(
#             candidates,
#             key=lambda c: c.get("confidence", 0) * 0.7 + c["priority"] * 0.3,
#         )
#     return merged

# def _identify_ambiguous_regions(layout, extracted):
#     extracted_vals = {v.get("value", "").lower() for v in extracted.values()}
#     return [e for e in layout if e.get("text", "").lower() not in extracted_vals]

# def _get_image_hash(image):
#     try:
#         import numpy as np
#         if isinstance(image, np.ndarray):
#             return hashlib.md5(image.tobytes()).hexdigest()
#     except Exception:
#         pass
#     return None

# def _create_empty_result(reason):
#     return {
#         "fields": {},
#         "raw_lines": [],
#         "confidence": 0.0,
#         "document_type": "UNK",
#         "policy_type": "UNK",
#         "metadata": {"error": reason},
#     }


"""
Orchestrator – Intelligent Cascading Hybrid (FLOW CONTROL ONLY)

Responsibilities:
- Run stages in strict order
- Control cascading (missing fields only)
- Merge results safely
- Never extract, normalize, or interpret values
"""

from typing import Dict, List

from preprocessing import preprocess
from utils.text_utils import merge_broken_lines
from agents.vision_agent import VisionAgent
from agents.correction_agent import correct_lines

# ---------------- STAGES ----------------

from agents.stage1_deterministic_agent import extract_with_regex
from agents.stage2_semantic_agent import semantic_fill_missing_fields
from agents.stage3_layout_agent import extract_with_layoutxlm
from agents.relation_extraction_agent import RelationExtractionAgent
from agents.validation_agent import validate_and_arbitrate

# ---------------- CLASSIFICATION ----------------

try:
    from agents.document_classifier import classify_document
    from agents.policy_classifier import classify_policy
    CLASSIFICATION_AVAILABLE = True
except Exception:
    CLASSIFICATION_AVAILABLE = False

# ============================================================
# FIELD GROUPS (FLOW DECISIONS ONLY)
# ============================================================

CRITICAL_FIELDS = {
    "carrier",
    "policy_number",
    "insured_name",
    "effective_date",
}

IMPORTANT_FIELDS = {
    "property_address",
    "mortgage",
    "loan_number",
}

OPTIONAL_FIELDS = {
    "mailing_address",
    "agent",
    "agent_phone",
}

# ============================================================
# PIPELINE STATE
# ============================================================

_PIPELINE_CACHE = {}
_vision_agent = None

# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(image, debug: bool = False, use_cache: bool = True) -> Dict:
    """
    Execute the full Intelligent Cascading Hybrid pipeline.
    """
    try:
        processed = preprocess(image)

        global _vision_agent
        if _vision_agent is None:
            _vision_agent = VisionAgent(use_layoutxlm=True)

        vision = _vision_agent
        ocr = vision.ocr_engine.run_with_boxes(processed)

        if not ocr or not ocr.get("text"):
            return _empty_result("No OCR text")

        lines = ocr.get("lines") or [" ".join(ocr.get("text", []))]
        lines = merge_broken_lines([l.strip() for l in lines if l.strip()])

        # ✅ OCR CORRECTION (FIX ONLY)
        lines = correct_lines(lines, debug=debug)

        layout = []
        try:
            layout = vision.analyze_layout(processed, ocr)
        except Exception:
            layout = []

        # ================= STAGE 1 =================
        stage1 = extract_with_regex(lines, layout)

        # ================= STAGE 2 =================
        stage2 = semantic_fill_missing_fields(
            lines,
            existing_fields=stage1,
            sections=None,
        )

        # ================= STAGE 3 =================
        combined_12 = _merge_locked(stage1, stage2)
        missing_after_2 = _missing_fields(combined_12)

        stage3 = {}
        if missing_after_2 and layout:
            relation_agent = RelationExtractionAgent()
            relations = relation_agent.extract_relations(layout, combined_12)
            ambiguous_regions = _ambiguous_regions(layout, combined_12)

            stage3 = extract_with_layoutxlm(
                ambiguous_regions,
                relations,
                missing_after_2,
            )

        # ================= FINAL MERGE =================
        merged = _merge_by_priority(stage1, stage2, stage3)

        # ================= VALIDATION =================
        ocr_conf = ocr.get("avg_confidence", 0.85)

        final_fields, final_confidence = validate_and_arbitrate(
            merged,
            ocr_conf,
            {
                "stage1": stage1,
                "stage2": stage2,
                "stage3": stage3,
            },
        )

        return {
            "fields": final_fields,
            "raw_lines": lines,
            "confidence": final_confidence,
            "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
            "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
        }

    except Exception as e:
        return _empty_result(str(e))


# ============================================================
# BATCH WRAPPER
# ============================================================

def run_pipeline_batch(images, debug: bool = False, use_cache: bool = True):
    return [run_pipeline(img, debug=debug, use_cache=use_cache) for img in images]


# ============================================================
# HELPERS (FLOW ONLY)
# ============================================================

def _missing_fields(fields: Dict[str, Dict]) -> List[str]:
    required = CRITICAL_FIELDS | IMPORTANT_FIELDS
    return [f for f in required if f not in fields]


def _merge_locked(primary: Dict, secondary: Dict) -> Dict:
    merged = dict(primary)
    for k, v in secondary.items():
        if k not in merged and v is not None:
            merged[k] = v
    return merged


def _merge_by_priority(s1: Dict, s2: Dict, s3: Dict) -> Dict:
    merged = {}
    for field in set(s1) | set(s2) | set(s3):
        if field in s1:
            merged[field] = s1[field]
        elif field in s2:
            merged[field] = s2[field]
        elif field in s3:
            merged[field] = s3[field]
    return merged


def _ambiguous_regions(layout: List[Dict], extracted: Dict) -> List[Dict]:
    used = {v.get("value", "").lower() for v in extracted.values()}
    return [r for r in layout if r.get("text", "").lower() not in used]


def _empty_result(reason: str) -> Dict:
    return {
        "fields": {},
        "raw_lines": [],
        "confidence": 0.0,
        "document_type": "UNK",
        "policy_type": "UNK",
        "metadata": {"error": reason},
    }
