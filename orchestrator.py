"""
Orchestrator – Intelligent Cascading Hybrid (ENHANCED VERSION)
================================================================================

This orchestrator enforces a strict 4-layer extraction pipeline:

Stage 0 → OCR conditioning
Stage 1 → Deterministic stateful extraction (SOLE AUTHORITY)
Stage 2 → Semantic gap filling (penalized, missing-only)
Stage 3 → Layout gap filling (weakest signal)
Stage 4 → Validation & arbitration (FINAL AUTHORITY)

ENHANCEMENTS:
1. Smarter Stage 2/3 execution logic
2. Better missing field detection
3. Optimized for mortgage/loan extraction
"""

from typing import Dict, List

from preprocessing import preprocess
from utils.text_utils import merge_broken_lines
from agents.vision_agent import VisionAgent
from agents.correction_agent import correct_lines

# ================= EXTRACTION STAGES =================

from agents.stage1_deterministic_agent import extract_fields
from agents.stage2_semantic_agent import extract_with_ner
from agents.stage3_layout_agent import extract_with_layoutxlm
from agents.relation_extraction_agent import RelationExtractionAgent
from agents.validation_agent import validate_and_arbitrate

# ================= CLASSIFICATION =================

try:
    from agents.document_classifier import classify_document
    from agents.policy_classifier import classify_policy
    CLASSIFICATION_AVAILABLE = True
except Exception:
    CLASSIFICATION_AVAILABLE = False


# ============================================================
# FIELD GROUPS (ENHANCED)
# ============================================================

CRITICAL_FIELDS = [
    "carrier_name",
    "policy_number",
    "insured_name",
    "effective_date",
    "expiration_date",
]

IMPORTANT_FIELDS = [
    "property_address",
    "loan_number",
    "mortgage_company",
    "total_premium",
]

OPTIONAL_FIELDS = [
    "mailing_address",
    "agent_name",
    "agent_phone",
]

REQUIRED_FIELDS = CRITICAL_FIELDS + IMPORTANT_FIELDS

# Core fields that enable fast path
CORE_FIELDS = ["insured_name", "policy_number", "property_address"]


# ============================================================
# PIPELINE STATE
# ============================================================

_vision_agent = None


# ============================================================
# MAIN PIPELINE (ENHANCED)
# ============================================================

def run_pipeline(image, max_retries=1, debug=False, use_cache=True) -> Dict:
    try:
        # ---------------- PREPROCESS ----------------
        processed = preprocess(image)

        global _vision_agent
        if _vision_agent is None:
            _vision_agent = VisionAgent(use_layoutxlm=True)

        vision = _vision_agent
        ocr = vision.ocr_engine.run_with_boxes(processed)

        if not ocr or not ocr.get("text"):
            return _empty_result("No OCR text")

        # ---------------- OCR → LINES ----------------
        lines = ocr.get("lines") or ocr.get("text", [])
        lines = [l.strip() for l in lines if l and l.strip()]
        lines = merge_broken_lines(lines)
        lines = correct_lines(lines, debug=debug)

        # ================= STAGE 1 (AUTHORITATIVE) =================
        stage1 = extract_fields(lines)
        
        # Check what's missing
        missing1 = _identify_missing_fields(stage1)
        
        if debug:
            print(f"\n[STAGE1] Extracted {len(stage1)} fields: {list(stage1.keys())}")
            print(f"[STAGE1] Missing {len(missing1)} fields: {missing1}")
        
        # OPTIMIZATION: Early exit if we have all core fields and only minor fields missing
        has_core_fields = all(f in stage1 for f in CORE_FIELDS)
        if has_core_fields and len(missing1) <= 2:
            if debug:
                print(f"[PIPELINE] Fast path: Core fields found, skipping expensive stages")
                print(f"[PIPELINE] Only missing: {missing1}")
            
            # Skip to validation
            ocr_conf = ocr.get("avg_confidence", 0.85)
            
            final_fields, confidence = validate_and_arbitrate(
                stage1,
                ocr_conf,
                {"stage1": stage1, "stage2": {}, "stage3": {}},
            )
            
            return {
                "fields": final_fields,
                "raw_lines": lines,
                "confidence": confidence,
                "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
                "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
            }

        # ================= STAGE 2 (SEMANTIC GAP FILL) =================
        stage2 = {}
        
        # ENHANCED: Smarter Stage 2 execution
        # Run if:
        # 1. ANY critical field is missing (carrier, policy#, insured, dates)
        # 2. OR mortgage/loan info is missing (common)
        # 3. OR many fields missing
        should_run_stage2 = (
            any(f in missing1 for f in ['carrier_name', 'policy_number', 'insured_name']) or
            any(f in missing1 for f in ['mortgage_company', 'loan_number']) or
            len(missing1) > 4
        )
        
        if missing1 and should_run_stage2:
            if debug:
                print(f"\n[STAGE2] Running semantic extraction for: {missing1}")
            
            raw_stage2 = extract_with_ner(lines, missing1)
            for f, d in raw_stage2.items():
                if f not in stage1:
                    d["confidence"] = max(0.55, d.get("confidence", 0.7))
                    d["source"] = "semantic_ner"
                    stage2[f] = d
            
            if debug:
                print(f"[STAGE2] Extracted {len(stage2)} additional fields: {list(stage2.keys())}")
        else:
            if debug:
                print(f"\n[PIPELINE] Skipping Stage 2")
                print(f"  Reason: Missing={len(missing1)}, Critical missing={any(f in missing1 for f in CRITICAL_FIELDS)}")

        # ================= STAGE 3 (LAYOUT GAP FILL) =================
        combined = {**stage1, **stage2}
        stage3 = {}
        missing2 = _identify_missing_fields(combined)

        # Only run layout analysis if still missing critical fields
        should_run_stage3 = any(f in missing2 for f in CRITICAL_FIELDS)
        
        if missing2 and should_run_stage3:
            if debug:
                print(f"\n[STAGE3] Running layout extraction for: {missing2}")
            
            # Lazy layout analysis (only when needed)
            try:
                layout = vision.analyze_layout(processed, ocr)
            except Exception as e:
                if debug:
                    print(f"[STAGE3] Layout analysis failed: {e}")
                layout = []
            
            if layout:
                re_agent = RelationExtractionAgent()
                relations = re_agent.extract_relations(layout, combined)
                ambiguous = _identify_ambiguous_regions(layout, combined)
                stage3 = extract_with_layoutxlm(ambiguous, relations, missing2)
                
                if debug:
                    print(f"[STAGE3] Extracted {len(stage3)} additional fields: {list(stage3.keys())}")
            else:
                if debug:
                    print(f"[STAGE3] No layout data available")
        else:
            if debug:
                print(f"\n[PIPELINE] Skipping Stage 3 - all critical fields found")

        # ================= STAGE 4 (FINAL AUTHORITY) =================
        merged = _merge_stage_results(stage1, stage2, stage3)
        
        if debug:
            print(f"\n[MERGE] Total fields after merge: {len(merged)}")
            print(f"[MERGE] Fields: {list(merged.keys())}")

        ocr_conf = ocr.get("avg_confidence", 0.85)

        final_fields, confidence = validate_and_arbitrate(
            merged,
            ocr_conf,
            {"stage1": stage1, "stage2": stage2, "stage3": stage3},
        )
        
        if debug:
            print(f"\n[FINAL] Validated fields: {len(final_fields)}")
            print(f"[FINAL] Overall confidence: {confidence:.1%}")

        return {
            "fields": final_fields,
            "raw_lines": lines,
            "confidence": confidence,
            "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
            "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
        }

    except Exception as e:
        if debug:
            import traceback
            print(f"[ERROR] Pipeline failed: {e}")
            traceback.print_exc()
        return _empty_result(str(e))


# ============================================================
# BATCH WRAPPER (REQUIRED BY UI)
# ============================================================

def run_pipeline_batch(images, max_retries=1, debug=False, use_cache=True):
    return [
        run_pipeline(
            img,
            max_retries=max_retries,
            debug=debug,
            use_cache=use_cache,
        )
        for img in images
    ]


# ============================================================
# HELPERS
# ============================================================

def _identify_missing_fields(fields: Dict) -> List[str]:
    return [f for f in REQUIRED_FIELDS if f not in fields]


def _merge_stage_results(s1, s2, s3):
    merged = {}
    for f in set(s1) | set(s2) | set(s3):
        candidates = []
        if f in s1:
            candidates.append({**s1[f], "priority": 3})
        if f in s2:
            candidates.append({**s2[f], "priority": 2})
        if f in s3:
            candidates.append({**s3[f], "priority": 1})
        merged[f] = max(
            candidates,
            key=lambda c: c.get("confidence", 0) * 0.7 + c["priority"] * 0.3,
        )
    return merged


def _identify_ambiguous_regions(layout, extracted):
    extracted_vals = {v.get("value", "").lower() for v in extracted.values()}
    return [e for e in layout if e.get("text", "").lower() not in extracted_vals]


def _empty_result(reason):
    return {
        "fields": {},
        "raw_lines": [],
        "confidence": 0.0,
        "document_type": "UNK",
        "policy_type": "UNK",
        "metadata": {"error": reason},
    }