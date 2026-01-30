"""
Orchestrator – Intelligent Cascading Hybrid (ENHANCED VERSION)
================================================================================

Stage 0 → OCR conditioning
Stage 1 → Deterministic stateful extraction (SOLE AUTHORITY)
Stage 2 → Semantic gap filling (GLiNER, penalized, missing-only)
Stage 3 → Layout gap filling (weakest signal)
Stage 4 → Validation & arbitration (FINAL AUTHORITY)
Stage 5 → Document + Policy Type Field Enforcement (OUTPUT ONLY)
"""

from typing import Dict, List

from preprocessing import preprocess
from utils.text_utils import merge_broken_lines
from agents.vision_agent import VisionAgent
from agents.correction_agent import correct_lines

# ================= EXTRACTION STAGES =================

from agents.stage1_deterministic_agent import extract_fields
from agents.stage2_semantic_agent import extract_with_ner   # GLiNER
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

from agents.insurance_segmentation import FIELD_RULES, POLICY_FIELD_RULES


# ============================================================
# FIELD GROUPS
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

REQUIRED_FIELDS = CRITICAL_FIELDS + IMPORTANT_FIELDS
CORE_FIELDS = ["insured_name", "policy_number", "property_address"]

# ============================================================
# PIPELINE STATE
# ============================================================

_vision_agent = None


# ============================================================
# MAIN PIPELINE
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

        # ---------------- OCR → LINES (FIXED) ----------------
        raw_text = ocr.get("text")

        if isinstance(raw_text, str):
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        elif isinstance(raw_text, list):
            lines = [str(l).strip() for l in raw_text if l and str(l).strip()]
        else:
            lines = []

        if not lines:
            return _empty_result("No usable OCR lines")

        lines = merge_broken_lines(lines)
        lines = correct_lines(lines, debug=debug)

        # ---------------- CLASSIFICATION (ONCE) ----------------
        document_type = classify_document(lines) if CLASSIFICATION_AVAILABLE else "OTH"
        policy_type = classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK"

        if debug:
            print("[DOC TYPE]", document_type)
            print("[POLICY TYPE]", policy_type)

        # ================= STAGE 1 =================
        stage1 = extract_fields(lines)
        missing1 = _identify_missing_fields(stage1)

        # ---------------- FAST PATH ----------------
        if all(f in stage1 for f in CORE_FIELDS) and len(missing1) <= 2:
            ocr_conf = ocr.get("avg_confidence", 0.85)

            final_fields, confidence = validate_and_arbitrate(
                stage1,
                ocr_conf,
                {"stage1": stage1, "stage2": {}, "stage3": {}},
            )

            final_fields = _apply_doc_policy_gating(
                final_fields, document_type, policy_type
            )

            return {
                "fields": final_fields,
                "raw_lines": lines,
                "confidence": confidence,
                "document_type": document_type,
                "policy_type": policy_type,
            }

        # ================= STAGE 2 (GLiNER) =================
        stage2 = {}
        should_run_stage2 = (
            any(f in missing1 for f in CRITICAL_FIELDS)
            or any(f in missing1 for f in ["mortgage_company", "loan_number"])
            or len(missing1) > 4
        )

        if missing1 and should_run_stage2:
            raw_stage2 = extract_with_ner(lines, missing1)
            for f, d in raw_stage2.items():
                if f not in stage1:
                    d["confidence"] = max(0.55, d.get("confidence", 0.7))
                    d["source"] = "semantic_ner"
                    stage2[f] = d

        # ================= STAGE 3 (LAYOUT) =================
        combined = {**stage1, **stage2}
        stage3 = {}
        missing2 = _identify_missing_fields(combined)

        if any(f in missing2 for f in CRITICAL_FIELDS):
            try:
                layout = vision.analyze_layout(processed, ocr)
            except Exception:
                layout = []

            if layout:
                re_agent = RelationExtractionAgent()
                relations = re_agent.extract_relations(layout, combined)
                ambiguous = _identify_ambiguous_regions(layout, combined)
                stage3 = extract_with_layoutxlm(ambiguous, relations, missing2)

        # ================= STAGE 4 (VALIDATION) =================
        merged = _merge_stage_results(stage1, stage2, stage3)
        ocr_conf = ocr.get("avg_confidence", 0.85)

        final_fields, confidence = validate_and_arbitrate(
            merged,
            ocr_conf,
            {"stage1": stage1, "stage2": stage2, "stage3": stage3},
        )

        # ================= STAGE 5 (DOC + POLICY ENFORCEMENT) =================
        final_fields = _apply_doc_policy_gating(
            final_fields, document_type, policy_type
        )

        return {
            "fields": final_fields,
            "raw_lines": lines,
            "confidence": confidence,
            "document_type": document_type,
            "policy_type": policy_type,
            "extraction_reason": _build_extraction_reason(
                document_type, policy_type, final_fields
            ),
        } 
    
    except Exception as e:
        if debug:
            import traceback
            print("[ERROR]", e)
            traceback.print_exc()
        return _empty_result(str(e))


# ============================================================
# HELPERS
# ============================================================

def _apply_doc_policy_gating(fields, document_type, policy_type):
    doc_allowed = FIELD_RULES.get(document_type, FIELD_RULES["OTH"])
    policy_allowed = POLICY_FIELD_RULES.get(policy_type)

    def allowed(f):
        if policy_allowed:
            return f in doc_allowed and f in policy_allowed
        return f in doc_allowed

    return {k: v for k, v in fields.items() if allowed(k)}


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

def _build_extraction_reason(document_type, policy_type, final_fields):
    from agents.insurance_segmentation import FIELD_RULES, POLICY_FIELD_RULES

    doc_allowed = FIELD_RULES.get(document_type, [])
    policy_allowed = POLICY_FIELD_RULES.get(policy_type)

    if policy_allowed:
        allowed = set(doc_allowed) & set(policy_allowed)
        rule_scope = "Document + Policy rules"
    else:
        allowed = set(doc_allowed)
        rule_scope = "Document rules only"

    return {
        "document_type": document_type,
        "policy_type": policy_type,
        "rule_scope": rule_scope,
        "allowed_field_count": len(allowed),
        "extracted_field_count": len(final_fields),
        "allowed_fields": sorted(list(allowed)),
        "extracted_fields": sorted(list(final_fields.keys())),
        "message": (
            f"For document type '{document_type}'"
            + (f" and policy type '{policy_type}'" if policy_allowed else "")
            + f", only {len(allowed)} fields are allowed by segmentation rules."
        ),
    }
