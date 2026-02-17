# """
# Orchestrator – Intelligent Cascading Hybrid (ENHANCED VERSION)
# ================================================================================
# This orchestrator enforces a strict multi-layer extraction pipeline:

# Stage 0 → OCR conditioning
# Stage 1 → Deterministic stateful extraction (SOLE AUTHORITY)
# Stage 2 → Semantic gap filling (penalized, missing-only)
# Stage 3 → Layout gap filling (weakest signal)
# Stage 4 → Validation & arbitration (FINAL AUTHORITY)

# ENHANCEMENTS:
# 1. Smarter Stage 2/3 execution logic
# 2. Better missing field detection
# 3. Optimized for mortgage / loan extraction
# """

# from typing import Dict, List

# from preprocessing import preprocess
# from utils.text_utils import merge_broken_lines
# from agents.vision_agent import VisionAgent
# from agents.correction_agent import correct_lines

# # ================= EXTRACTION STAGES =================
# from agents.stage1_deterministic_agent import extract_fields
# from agents.stage2_semantic_agent import extract_with_ner
# from agents.stage3_layout_agent import extract_with_layoutxlm
# from agents.relation_extraction_agent import RelationExtractionAgent
# from agents.validation_agent import validate_and_arbitrate

# # ================= CLASSIFICATION =================
# try:
#     from agents.document_classifier import classify_document
#     from agents.policy_classifier import classify_policy
#     CLASSIFICATION_AVAILABLE = True
# except Exception:
#     CLASSIFICATION_AVAILABLE = False

# # ============================================================
# # FIELD GROUPS (ENHANCED)
# # ============================================================

# CRITICAL_FIELDS = [
#     "carrier_name",
#     "policy_number",
#     "insured_name",
#     "effective_date",
#     "expiration_date",
# ]

# IMPORTANT_FIELDS = [
#     "property_address",
#     "loan_number",
#     "mortgage_company",
#     "total_premium",
# ]

# OPTIONAL_FIELDS = [
#     "mailing_address",
#     "agent_name",
#     "agent_phone",
# ]

# REQUIRED_FIELDS = CRITICAL_FIELDS + IMPORTANT_FIELDS

# # Core fields enabling fast-path
# CORE_FIELDS = ["insured_name", "policy_number", "property_address"]

# # ============================================================
# # PIPELINE STATE
# # ============================================================

# _vision_agent = None

# # ============================================================
# # MAIN PIPELINE
# # ============================================================

# def run_pipeline(image, max_retries=1, debug=False, use_cache=True) -> Dict:
#     try:
#         # ---------------- PREPROCESS ----------------
#         processed = preprocess(image)

#         global _vision_agent
#         if _vision_agent is None:
#             _vision_agent = VisionAgent(use_layoutxlm=True)

#         vision = _vision_agent

#         # ---------------- OCR ----------------
#         ocr = vision.ocr_engine.run_with_boxes(processed)

#         if not ocr or not ocr.get("text"):
#             return _empty_result("No OCR text")

#         # ---------------- OCR → LINES (FIXED, CONTRACT SAFE) ----------------
#         tokens = ocr.get("text", [])

#         if not isinstance(tokens, list) or not tokens:
#             return _empty_result("No OCR tokens")

#         lines: List[str] = []
#         current: List[str] = []

#         for t in tokens:
#             t = str(t).strip()
#             if not t:
#                 continue

#             current.append(t)

#             # conservative heuristic line break
#             if len(" ".join(current)) >= 80:
#                 lines.append(" ".join(current))
#                 current = []

#         if current:
#             lines.append(" ".join(current))

#         lines = merge_broken_lines(lines)
#         lines = correct_lines(lines, debug=debug)

#         if not lines:
#             return _empty_result("OCR produced no usable lines")

#         # ================= STAGE 1 (AUTHORITATIVE) =================
#         stage1 = extract_fields(lines)

#         missing1 = _identify_missing_fields(stage1)

#         if debug:
#             print(f"\n[STAGE 1] Extracted {len(stage1)} fields: {list(stage1.keys())}")
#             print(f"[STAGE 1] Missing {len(missing1)} fields: {missing1}")

#         # ---------------- FAST PATH ----------------
#         has_core_fields = all(f in stage1 for f in CORE_FIELDS)

#         if has_core_fields and len(missing1) <= 2:
#             if debug:
#                 print("[PIPELINE] Fast path activated")

#             ocr_conf = ocr.get("avg_confidence", 0.85)

#             final_fields, confidence = validate_and_arbitrate(
#                 stage1,
#                 ocr_conf,
#                 {"stage1": stage1, "stage2": {}, "stage3": {}},
#             )

#             return {
#                 "fields": final_fields,
#                 "raw_lines": lines,
#                 "confidence": confidence,
#                 "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#                 "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#             }

#         # ================= STAGE 2 (SEMANTIC GAP FILL) =================
#         stage2 = {}

#         should_run_stage2 = (
#             any(f in missing1 for f in ["carrier_name", "policy_number", "insured_name"])
#             or any(f in missing1 for f in ["mortgage_company", "loan_number"])
#             or len(missing1) > 4
#         )

#         if missing1 and should_run_stage2:
#             if debug:
#                 print(f"\n[STAGE 2] Running semantic extraction for: {missing1}")

#             raw_stage2 = extract_with_ner(lines, missing1)

#             for f, d in raw_stage2.items():
#                 if f not in stage1:
#                     d["confidence"] = max(0.55, d.get("confidence", 0.7))
#                     d["source"] = "semantic_ner"
#                     stage2[f] = d

#             if debug:
#                 print(f"[STAGE 2] Extracted {len(stage2)} fields: {list(stage2.keys())}")

#         elif debug:
#             print("[PIPELINE] Skipping Stage 2")

#         # ================= STAGE 3 (LAYOUT GAP FILL) =================
#         combined = {**stage1, **stage2}
#         stage3 = {}

#         missing2 = _identify_missing_fields(combined)
#         should_run_stage3 = any(f in missing2 for f in CRITICAL_FIELDS)

#         if missing2 and should_run_stage3:
#             if debug:
#                 print(f"\n[STAGE 3] Running layout extraction for: {missing2}")

#             try:
#                 layout = vision.analyze_layout(processed, ocr)
#             except Exception as e:
#                 if debug:
#                     print(f"[STAGE 3] Layout analysis failed: {e}")
#                 layout = []

#             if layout:
#                 re_agent = RelationExtractionAgent()
#                 relations = re_agent.extract_relations(layout, combined)
#                 ambiguous = _identify_ambiguous_regions(layout, combined)

#                 stage3 = extract_with_layoutxlm(
#                     ambiguous,
#                     relations,
#                     missing2,
#                 )

#                 if debug:
#                     print(f"[STAGE 3] Extracted {len(stage3)} fields: {list(stage3.keys())}")

#         elif debug:
#             print("[PIPELINE] Skipping Stage 3")

#         # ================= STAGE 4 (FINAL AUTHORITY) =================
#         merged = _merge_stage_results(stage1, stage2, stage3)

#         if debug:
#             print(f"\n[MERGE] Total fields after merge: {len(merged)}")

#         ocr_conf = ocr.get("avg_confidence", 0.85)

#         final_fields, confidence = validate_and_arbitrate(
#             merged,
#             ocr_conf,
#             {"stage1": stage1, "stage2": stage2, "stage3": stage3},
#         )

#         return {
#             "fields": final_fields,
#             "raw_lines": lines,
#             "confidence": confidence,
#             "document_type": classify_document(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#             "policy_type": classify_policy(lines) if CLASSIFICATION_AVAILABLE else "UNK",
#         }

#     except Exception as e:
#         if debug:
#             import traceback
#             print(f"[ERROR] Pipeline failed: {e}")
#             traceback.print_exc()
#         return _empty_result(str(e))


# # ============================================================
# # BATCH WRAPPER (UI CONTRACT)
# # ============================================================

# def run_pipeline_batch(images, max_retries=1, debug=False, use_cache=True):
#     return [
#         run_pipeline(
#             img,
#             max_retries=max_retries,
#             debug=debug,
#             use_cache=use_cache,
#         )
#         for img in images
#     ]


# # ============================================================
# # HELPERS
# # ============================================================

# def _identify_missing_fields(fields: Dict) -> List[str]:
#     return [f for f in REQUIRED_FIELDS if f not in fields]


# def _merge_stage_results(s1, s2, s3):
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
#     extracted_vals = {
#         v.get("value", "").lower()
#         for v in extracted.values()
#         if isinstance(v, dict)
#     }
#     return [e for e in layout if e.get("text", "").lower() not in extracted_vals]


# def _empty_result(reason):
#     return {
#         "fields": {},
#         "raw_lines": [],
#         "confidence": 0.0,
#         "document_type": "UNK",
#         "policy_type": "UNK",
#         "metadata": {"error": reason},
#     }

"""
Orchestrator — Approach-Based Extraction Engine
================================================================================

Pipeline:
  1. OCR preprocessing → lines
  2. Classify doc type + policy type
  3. Route to ONE primary approach
  4. Execute approach (calls appropriate agents)
  5. Check for missing critical fields
  6. If missing → run ONE controlled fallback (never more)
  7. Validate + arbitrate → final output

Approaches (8 total):
  1. SARDE             — stage1 deterministic only
  2. SARDE + LATE      — stage1 + stage3 layout for tables
  3. SC → SARDE → LATE — semantic first, then stage1, then layout
  4. DTE               — direct template extraction
  5. SC+TE → DTE       — semantic + GLiNER, then template fallback
  6. SC+TE + LATE      — semantic + GLiNER + layout tables
  7. SC+TE             — semantic + GLiNER only
  8. LORH              — lightweight heuristic

Rules:
  • Only ONE primary approach per document
  • Fallback is conditional, not automatic
  • Fallback only runs if CRITICAL fields are still missing
  • Never run more than primary + 1 fallback
  • LATE only runs when tables are detected
  • Stage 1 output ALWAYS takes priority when present
"""

from typing import Dict, List, Optional

# ================= INFRASTRUCTURE =================
from preprocessing import preprocess
from utils.text_utils import merge_broken_lines
from agents.vision_agent import VisionAgent
from agents.correction_agent import correct_lines

# ================= EXTRACTION AGENTS =================
from agents.stage1_deterministic_agent import extract_fields as sarde_extract
from agents.stage2_semantic_agent import extract_with_ner as sc_te_extract
from agents.stage3_layout_agent import extract_with_layoutxlm as late_extract
from agents.relation_extraction_agent import RelationExtractionAgent
from agents.validation_agent import validate_and_arbitrate

# ================= ROUTER + DTE/LORH =================
from agents.document_router import (
    route,
    Approach,
    RoutingResult,
    extract_dte,
    extract_lorh,
    classify_doc_type,
    classify_policy_type,
    REQUIRED_FIELDS,
)

# ================= CLASSIFICATION (optional, may not be installed) =======
try:
    from agents.document_classifier import classify_document
    from agents.policy_classifier import classify_policy
    CLASSIFICATION_AVAILABLE = True
except Exception:
    CLASSIFICATION_AVAILABLE = False


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

ALL_KNOWN_FIELDS = [
    "carrier_name", "policy_number", "insured_name",
    "effective_date", "expiration_date",
    "property_address", "mailing_address",
    "mortgage_company", "loan_number",
    "total_premium", "deductible",
    "agent_name", "agent_phone",
    "cancellation_reason",
]


# ============================================================
# SINGLETON STATE
# ============================================================

_vision_agent: Optional[VisionAgent] = None


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(image, max_retries=1, debug=False, use_cache=True,
                 prior_fields=None) -> Dict:
    """
    Main entry point.  Processes one document image through the
    full approach-based extraction pipeline.

    Args:
        prior_fields: Fields already found on earlier pages (multi-page opt).
                      If provided, these are pre-merged into results and
                      used to reduce the set of missing fields, avoiding
                      expensive fallback/LATE runs.
    """
    try:
        # ============================
        # STAGE 0 — OCR PREPROCESSING
        # ============================
        processed = preprocess(image)

        global _vision_agent
        if _vision_agent is None:
            _vision_agent = VisionAgent(use_layoutxlm=True)
        vision = _vision_agent

        ocr = vision.ocr_engine.run_with_boxes(processed)
        if not ocr or not ocr.get("text"):
            return _empty_result("No OCR text")

        tokens = ocr.get("text", [])
        if not isinstance(tokens, list) or not tokens:
            return _empty_result("No OCR tokens")

        # --- Build lines: prefer layout-aware lines from OCR engine ---
        # The OCR engine's _build_lines() uses Y-coordinate clustering
        # to group tokens into real visual lines.  This preserves the
        # document's spatial structure (columns, label:value pairs, etc.)
        # 
        # Fallback: if "lines" key is missing/empty, reconstruct from
        # individual tokens (legacy path).
        ocr_lines = ocr.get("lines", [])

        if ocr_lines and isinstance(ocr_lines, list) and any(
            isinstance(l, str) and l.strip() for l in ocr_lines
        ):
            # Use layout-aware lines from OCR engine
            lines = [str(l).strip() for l in ocr_lines if str(l).strip()]
        else:
            # Fallback: reconstruct from word tokens
            lines: List[str] = []
            current: List[str] = []
            for t in tokens:
                t = str(t).strip()
                if not t:
                    continue
                current.append(t)
                if len(" ".join(current)) >= 80:
                    lines.append(" ".join(current))
                    current = []
            if current:
                lines.append(" ".join(current))

        lines = merge_broken_lines(lines)
        lines = correct_lines(lines, debug=debug)

        if not lines:
            return _empty_result("OCR produced no usable lines")

        # ============================
        # STAGE 1 — CLASSIFY
        # ============================
        doc_type = "UNK"
        policy_type = "UNK"

        if CLASSIFICATION_AVAILABLE:
            try:
                doc_type = classify_document(lines)
            except Exception:
                pass
            try:
                policy_type = classify_policy(lines)
            except Exception:
                pass

        # If classify_document returned OTH, treat it as OTH so the
        # router's classify_doc_type gets a second chance.  OTH is the
        # default/"I don't know" bucket — the router's classifier uses
        # different heuristics and may succeed where document_classifier
        # did not (e.g. for fax packets, EDI images, etc.).
        if doc_type == "OTH":
            doc_type = "OTH"

        # ============================
        # STAGE 2 — ROUTE
        # ============================
        routing: RoutingResult = route(
            lines,
            doc_type=doc_type,
            policy_type=policy_type,
        )

        if debug:
            print(f"\n[ROUTER] doc_type={routing.doc_type} "
                  f"policy_type={routing.policy_type}")
            print(f"[ROUTER] approach={routing.approach.value} "
                  f"reason={routing.reason}")
            print(f"[ROUTER] required={routing.required_fields}")
            print(f"[ROUTER] has_tables={routing.has_tables} "
                  f"fallback={routing.fallback}")

        # ============================
        # STAGE 3 — EXECUTE PRIMARY APPROACH
        # ============================
        # MULTI-PAGE OPTIMIZATION: If prior pages already found fields,
        # reduce the target field set so we don't run expensive agents
        # for fields we already have.
        target_fields = routing.all_target_fields
        if prior_fields:
            target_fields = [
                f for f in target_fields
                if f not in prior_fields
            ]
            if debug:
                print(f"[MULTI-PAGE] {len(prior_fields)} fields from prior pages, "
                      f"{len(target_fields)} still needed")

        # If prior pages already found everything, skip heavy extraction
        if prior_fields and not target_fields:
            if debug:
                print("[MULTI-PAGE] All fields found on prior pages — light scan only")
            primary_result = extract_lorh(lines)  # lightweight scan for any new info
        else:
            primary_result = _execute_approach(
                routing.approach,
                lines=lines,
                doc_type=routing.doc_type,
                missing_fields=target_fields if target_fields else routing.all_target_fields,
                vision=vision,
                processed=processed,
                ocr=ocr,
                has_tables=routing.has_tables,
                debug=debug,
            )

        if debug:
            print(f"\n[PRIMARY] {routing.approach.value} → "
                  f"{len(primary_result)} fields: "
                  f"{list(primary_result.keys())}")

        # ============================
        # STAGE 4 — CONDITIONAL FALLBACK
        # ============================
        # OPTIMIZATION: Only trigger fallback for CRITICAL required fields
        # that are truly missing (not just optional gaps)
        missing_critical = missing_required_fields(
            primary_result,
            routing.required_fields
        )
        # Filter to only truly critical fields worth a fallback run
        worth_fallback = [
            f for f in missing_critical
            if f in CRITICAL_FIELDS
        ]

        fallback_result: Dict[str, Dict] = {}

        if worth_fallback and routing.fallback:
            if debug:
                print(f"\n[FALLBACK] Missing critical: {worth_fallback}")
                print(f"[FALLBACK] Running {routing.fallback.value}")

            fallback_result = _execute_approach(
                routing.fallback,
                lines=lines,
                doc_type=routing.doc_type,
                missing_fields=worth_fallback,
                vision=vision,
                processed=processed,
                ocr=ocr,
                has_tables=routing.has_tables,
                debug=debug,
            )

            if debug:
                print(f"[FALLBACK] {routing.fallback.value} → "
                      f"{len(fallback_result)} fields: "
                      f"{list(fallback_result.keys())}")
        elif debug:
            if not missing_critical:
                print("[FALLBACK] Skipped — no required fields missing")
            elif not worth_fallback:
                print(f"[FALLBACK] Skipped — only non-critical missing: {missing_critical}")
            else:
                print("[FALLBACK] Skipped — no fallback defined "
                      f"for {routing.approach.value}")

        # ============================
        # STAGE 5 — MERGE
        # ============================
        merged = _merge_results(primary_result, fallback_result)

        # Merge in prior page fields (they fill gaps, don't override)
        if prior_fields:
            for k, v in prior_fields.items():
                if k not in merged:
                    merged[k] = v

        if debug:
            print(f"\n[MERGE] Total after merge: {len(merged)} fields")

        # ============================
        # STAGE 6 — VALIDATE & ARBITRATE
        # ============================
        ocr_conf = ocr.get("avg_confidence", 0.85)

        final_fields, confidence = validate_and_arbitrate(
            merged,
            ocr_conf,
            {
                "primary": primary_result,
                "fallback": fallback_result,
            },
            doc_type=routing.doc_type,
            policy_type=routing.policy_type,
        )

        if debug:
            print(f"[FINAL] {len(final_fields)} validated fields, "
                  f"confidence={confidence:.3f}")

        return {
            "fields": final_fields,
            "raw_lines": lines,
            "confidence": confidence,
            "document_type": routing.doc_type,
            "policy_type": routing.policy_type,
            "approach": routing.approach.value,
            "routing_reason": routing.reason,
            "fallback_used": routing.fallback.value if (
                worth_fallback and routing.fallback) else None,
        }

    except Exception as e:
        if debug:
            import traceback
            print(f"[ERROR] Pipeline failed: {e}")
            traceback.print_exc()
        return _empty_result(str(e))


# ============================================================
# APPROACH EXECUTOR
# ============================================================

def _execute_approach(
    approach: Approach,
    *,
    lines: List[str],
    doc_type: str,
    missing_fields: List[str],
    vision,
    processed,
    ocr,
    has_tables: bool,
    debug: bool,
) -> Dict[str, Dict]:

    if approach == Approach.SARDE:
        return sarde_extract(lines)

    if approach == Approach.SARDE_LATE:
        result = sarde_extract(lines)
        # OPTIMIZATION: Only run LATE if CRITICAL fields are missing
        # Don't burn LayoutLMv3 inference for optional fields
        missing = missing_required_fields(result, missing_fields)
        critical_missing = [f for f in missing if f in CRITICAL_FIELDS]
        if critical_missing and has_tables:
            layout_result = _run_late(
                vision, processed, ocr, result, missing, debug
            )
            result = _merge_results(result, layout_result)
        elif debug and missing:
            print(f"[SARDE_LATE] Skipping LATE — only optional fields missing: {missing}")
        return result

    if approach == Approach.SC_SARDE_LATE:
        sc_result = sc_te_extract(lines, missing_fields)
        sarde_result = sarde_extract(lines)

        combined = _merge_results(sc_result, sarde_result)

        missing = missing_required_fields(combined, missing_fields)
        critical_missing = [f for f in missing if f in CRITICAL_FIELDS]
        if critical_missing and has_tables:
            layout_result = _run_late(
                vision, processed, ocr, combined, missing, debug
            )
            combined = _merge_results(combined, layout_result)

        return combined

    if approach == Approach.DTE:
        return extract_dte(lines, doc_type)

    if approach == Approach.SC_TE_DTE:
        sc_result = sc_te_extract(lines, missing_fields)

        missing = missing_required_fields(sc_result, missing_fields)
        if missing:
            dte_result = extract_dte(lines, doc_type)
            sc_result = _merge_results(dte_result, sc_result)

        return sc_result

    if approach == Approach.SC_TE_LATE:
        sc_result = sc_te_extract(lines, missing_fields)

        missing = missing_required_fields(sc_result, missing_fields)
        critical_missing = [f for f in missing if f in CRITICAL_FIELDS]
        if critical_missing and has_tables:
            layout_result = _run_late(
                vision, processed, ocr, sc_result, missing, debug
            )
            sc_result = _merge_results(sc_result, layout_result)

        return sc_result

    if approach == Approach.SC_TE:
        return sc_te_extract(lines, missing_fields)

    if approach == Approach.LORH:
        return extract_lorh(lines)

    if debug:
        print(f"[WARNING] Unknown approach: {approach}")

    return sarde_extract(lines)

# ============================================================
# LATE RUNNER  (layout agent wrapper)
# ============================================================

def _run_late(vision, processed, ocr, existing, missing, debug):
    """
    Run the Layout Agent (LATE) for spatial/table extraction.
    Returns dict of extracted fields.
    """
    try:
        layout = vision.analyze_layout(processed, ocr)
    except Exception as e:
        if debug:
            print(f"[LATE] Layout analysis failed: {e}")
        return {}

    if not layout:
        return {}

    try:
        re_agent = RelationExtractionAgent()
        relations = re_agent.extract_relations(layout, existing)
    except Exception as e:
        if debug:
            print(f"[LATE] Relation extraction failed: {e}")
        relations = []

    # Filter out already-extracted regions
    extracted_vals = {
        v.get("value", "").lower()
        for v in existing.values()
        if isinstance(v, dict)
    }
    ambiguous = [
        e for e in layout
        if e.get("text", "").lower() not in extracted_vals
    ]

    try:
        return late_extract(ambiguous, relations, missing)
    except Exception as e:
        if debug:
            print(f"[LATE] Extraction failed: {e}")
        return {}


# ============================================================
# MERGE LOGIC
# ============================================================

def _merge_results(
    base: Dict[str, Dict],
    overlay: Dict[str, Dict],
) -> Dict[str, Dict]:
    """
    Merge two extraction results.  Overlay wins for fields not
    in base; for fields in both, higher confidence wins.

    This is called in two contexts:
      1. Primary + fallback merge (primary is base, has priority)
      2. Within cascade approaches (earlier stage is base)
    """
    merged = dict(base)  # shallow copy

    for field, data in overlay.items():
        if field not in merged:
            merged[field] = data
        else:
            # Both have the field — keep the one with higher confidence
            existing_conf = merged[field].get("confidence", 0)
            new_conf = data.get("confidence", 0)
            if new_conf > existing_conf:
                merged[field] = data

    return merged


# ============================================================
# BATCH WRAPPER  (UI CONTRACT)
# ============================================================

def run_pipeline_batch(images, max_retries=1, debug=False, use_cache=True):
    """Process multiple images with cross-page optimization.
    Fields found on earlier pages are passed forward so later pages
    can skip expensive extraction for already-found fields."""
    results = []
    accumulated_fields: Dict[str, Dict] = {}

    for i, img in enumerate(images):
        result = run_pipeline(
            img,
            max_retries=max_retries,
            debug=debug,
            use_cache=use_cache,
            prior_fields=accumulated_fields if i > 0 else None,
        )
        results.append(result)
        # Accumulate fields for next page
        for k, v in result.get("fields", {}).items():
            if k not in accumulated_fields:
                accumulated_fields[k] = v

    return results


# ============================================================
# HELPERS
# ============================================================
def missing_required_fields(
    fields: Dict[str, Dict],
    required_fields: List[str],
    *,
    min_confidence: float = 0.65,
) -> List[str]:
    """
    A field is considered missing if:
      - not present
      - empty value
      - confidence below threshold
      - explicitly marked invalid
    """
    missing = []

    for f in required_fields:
        data = fields.get(f)

        if not data:
            missing.append(f)
            continue

        if isinstance(data, dict):
            value = data.get("value")
            conf = data.get("confidence", 0)
            status = data.get("validation")

            if value in ("", None, []):
                missing.append(f)
            elif conf < min_confidence:
                missing.append(f)
            elif status in ("failed", "invalid"):
                missing.append(f)
        else:
            if not str(data).strip():
                missing.append(f)

    return missing

def _empty_result(reason: str) -> Dict:
    return {
        "fields": {},
        "raw_lines": [],
        "confidence": 0.0,
        "document_type": "OTH",
        "policy_type": "OTH",
        "approach": None,
        "routing_reason": None,
        "fallback_used": None,
        "metadata": {"error": reason},
    }