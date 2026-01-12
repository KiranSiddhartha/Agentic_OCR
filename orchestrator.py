# orchestrator.py
# INTELLIGENT CASCADING HYBRID ARCHITECTURE
# Stage 1 → Stage 2 → Stage 3 → Stage 4 (with smart skipping)

from preprocessing import preprocess
from agents.vision_agent import VisionAgent
from utils.text_utils import merge_broken_lines
import hashlib
import time

# ============================================================
# STAGE IMPORTS
# ============================================================

from agents.stage1_deterministic_agent import extract_with_regex

# Stage 2
try:
    from agents.stage2_semantic_agent import extract_with_ner
    STAGE2_AVAILABLE = True
except ImportError:
    STAGE2_AVAILABLE = False
    print("[WARN] Stage 2 (Semantic NER) not available")

# Stage 3
try:
    from agents.stage3_layout_agent import extract_with_layoutxlm
    from agents.relation_extraction_agent import RelationExtractionAgent
    STAGE3_AVAILABLE = True
except ImportError:
    STAGE3_AVAILABLE = False
    print("[WARN] Stage 3 (Layout) not available")

from agents.validation_agent import validate_and_arbitrate

# ============================================================
# GLOBAL CACHE & PERFORMANCE TRACKING
# ============================================================

_PIPELINE_CACHE = {}
_CACHE_ENABLED = True
_vision_agent = None  # Singleton

_PERFORMANCE_STATS = {
    "stage1_hits": 0,
    "stage2_hits": 0,
    "stage3_hits": 0,
    "cache_hits": 0,
    "avg_stage1_time": 0,
    "avg_stage2_time": 0,
    "avg_stage3_time": 0,
}

# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(image, max_retries=1, debug=False, use_cache=True):
    """
    INTELLIGENT CASCADING HYBRID PIPELINE
    """

    cache_key = _get_image_hash(image)
    if use_cache and _CACHE_ENABLED and cache_key in _PIPELINE_CACHE:
        _PERFORMANCE_STATS["cache_hits"] += 1
        return _PIPELINE_CACHE[cache_key]

    stage_times = {}
    total_start = time.time()

    try:
        # ---------------- PREPROCESS ----------------
        processed = preprocess(image)

        # ---------------- OCR ----------------
        global _vision_agent
        if _vision_agent is None:
            _vision_agent = VisionAgent(use_layoutxlm=STAGE3_AVAILABLE)

        vision = _vision_agent

        ocr_start = time.time()
        ocr_results = vision.ocr_engine.run_with_boxes(processed)

        if not ocr_results or not ocr_results.get("text"):
            return _create_empty_result("No text detected by OCR")

        lines = ocr_results.get("lines", [])
        if not lines and ocr_results.get("text"):
            lines = [" ".join(ocr_results["text"])]

        lines = merge_broken_lines([l.strip() for l in lines if l.strip()])

        layout_elements = []
        if STAGE3_AVAILABLE:
            try:
                layout_elements = vision.analyze_layout(processed, ocr_results)
            except Exception:
                layout_elements = []

        stage_times["ocr"] = time.time() - ocr_start

        # ---------------- STAGE 1 ----------------
        stage1_start = time.time()
        stage1_fields = extract_with_regex(lines, layout_elements)
        stage_times["stage1"] = time.time() - stage1_start
        _PERFORMANCE_STATS["stage1_hits"] += 1

        missing_after_stage1 = _identify_missing_fields(stage1_fields)
        stage1_conf = _calculate_stage_confidence(stage1_fields)

        # ---------------- STAGE 2 ----------------
        stage2_fields = {}
        if STAGE2_AVAILABLE and _should_run_stage2(stage1_fields, missing_after_stage1, stage1_conf):
            stage2_start = time.time()
            stage2_fields = extract_with_ner(lines, missing_after_stage1)
            stage_times["stage2"] = time.time() - stage2_start
            _PERFORMANCE_STATS["stage2_hits"] += 1

        # ---------------- STAGE 3 ----------------
        combined_fields = {**stage1_fields, **stage2_fields}
        missing_after_stage2 = _identify_missing_fields(combined_fields)
        combined_conf = _calculate_stage_confidence(combined_fields)

        stage3_fields = {}
        if (
            STAGE3_AVAILABLE
            and _should_run_stage3(combined_fields, missing_after_stage2, combined_conf, layout_elements)
        ):
            stage3_start = time.time()
            re_agent = RelationExtractionAgent()
            relations = re_agent.extract_relations(layout_elements, combined_fields)
            ambiguous = _identify_ambiguous_regions(layout_elements, combined_fields)
            stage3_fields = extract_with_layoutxlm(ambiguous, relations, missing_after_stage2)
            stage_times["stage3"] = time.time() - stage3_start
            _PERFORMANCE_STATS["stage3_hits"] += 1

        # ---------------- STAGE 4 ----------------
        stage4_start = time.time()
        merged = _merge_stage_results_hybrid(stage1_fields, stage2_fields, stage3_fields)
        final_fields, confidence = validate_and_arbitrate(
            merged,
            ocr_results.get("avg_confidence", 0.8),
            stage_breakdown={
                "stage1": stage1_fields,
                "stage2": stage2_fields,
                "stage3": stage3_fields,
            },
        )
        stage_times["stage4"] = time.time() - stage4_start

        # ---------------- DOCUMENT CLASSIFICATION ----------------
        from agents.insurance_segmentation import segregate_insurance_document
        seg = segregate_insurance_document(lines)

        total_time = time.time() - total_start

        result = {
            "fields": final_fields,
            "raw_lines": lines,
            "confidence": confidence,
            "ocr_confidence": ocr_results.get("avg_confidence", 0.8),
            "document_type": seg.get("document_type", "INS"),
            "policy_type": seg.get("policy_type", _infer_policy_type(final_fields)),
            "metadata": {
                "pipeline": "intelligent_cascading_hybrid",
                "stage_times": stage_times,
                "total_time": total_time,
                "fields_per_stage": {
                    "stage1": len(stage1_fields),
                    "stage2": len(stage2_fields),
                    "stage3": len(stage3_fields),
                    "final": len(final_fields),
                },
            },
        }

        if use_cache and cache_key:
            _PIPELINE_CACHE[cache_key] = result

        return result

    except Exception as e:
        return _create_empty_result(str(e))

def run_pipeline_batch(
    images,
    max_retries=1,
    debug=False,
    max_workers=4,
    use_cache=True,
):
    """
    Batch wrapper for run_pipeline.
    Preserves existing behavior expected by app.py.
    """

    if not images:
        return []

    results = []

    # Simple sequential execution (SAFE DEFAULT)
    # Can be parallelized later if needed
    for img in images:
        try:
            res = run_pipeline(
                img,
                max_retries=max_retries,
                debug=debug,
                use_cache=use_cache,
            )
            results.append(res)
        except Exception as e:
            results.append(_create_empty_result(str(e)))

    return results

# ============================================================
# DECISION HELPERS
# ============================================================

def _should_run_stage2(stage1_fields, missing_fields, stage1_confidence):
    if not missing_fields:
        return False  # ← Skip Stage 2 if Stage 1 got everything
    if stage1_confidence < 0.90:
        return True  # ← Run if low confidence
    if len(missing_fields) >= 3:
        return True  # ← Run if many fields missing
    return any(f in missing_fields for f in ["policy_number", "insured_name"])

def _should_run_stage3(fields, missing, conf, layout):
    return bool(STAGE3_AVAILABLE and layout and missing and conf < 0.85)
    # ← Only run expensive LayoutLM if needed


def _calculate_stage_confidence(fields):
    if not fields:
        return 0.0
    return sum(f.get("confidence", 0.5) for f in fields.values()) / len(fields)


def _merge_stage_results_hybrid(stage1, stage2, stage3):
    merged = {}
    all_fields = set(stage1) | set(stage2) | set(stage3)

    for f in all_fields:
        candidates = []
        if f in stage1:
            candidates.append({**stage1[f], "priority": 3})
        if f in stage2:
            candidates.append({**stage2[f], "priority": 2})
        if f in stage3:
            candidates.append({**stage3[f], "priority": 1})

        merged[f] = max(
            candidates,
            key=lambda c: c.get("confidence", 0) * 0.7 + c.get("priority", 0) * 0.3,
        )

    return merged

# ============================================================
# UTILITIES
# ============================================================

def _identify_missing_fields(fields):
    required = [
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
        "mailing_address",
        "total_premium",
    ]
    return [f for f in required if f not in fields]


def _identify_ambiguous_regions(layout_elements, extracted_fields):
    extracted = {v.get("value", "").lower() for v in extracted_fields.values()}
    return [e for e in layout_elements if e.get("text", "").lower() not in extracted]


def _infer_policy_type(fields):
    text = " ".join(v.get("value", "") for v in fields.values()).lower()
    if "home" in text:
        return "HO"
    if "auto" in text:
        return "AUTO"
    if "life" in text:
        return "LIFE"
    if "commercial" in text:
        return "CGL"
    return "UNK"


def _create_empty_result(reason):
    return {
        "fields": {},
        "raw_lines": [],
        "confidence": 0.0,
        "metadata": {"error": reason},
    }


def _get_image_hash(image):
    try:
        import numpy as np
        if isinstance(image, np.ndarray):
            return hashlib.md5(image.tobytes()).hexdigest()
    except Exception:
        pass
    return None


def get_performance_stats():
    return _PERFORMANCE_STATS.copy()


def clear_cache():
    _PIPELINE_CACHE.clear()
