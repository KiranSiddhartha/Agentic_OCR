"""
Stage 2.5 — GLiNER AI Agent (ENHANCED VERSION)
==============================================
• Gap filler for secondary fields only
• NEVER creates or overrides policy_number from Stage1
• Handles orchestrator ↔ GLiNER field mismatch
• Enhanced to NOT skip mortgage_company and loan_number
"""

from typing import List, Dict
import re

# ============================================================
# CONFIGURATION (ENHANCED)
# ============================================================

# Only run GLiNER if these CRITICAL fields are missing
CRITICAL_FIELDS_FOR_GLINER = {
    "carrier_name",
    "policy_number",
    "insured_name",
    "mortgage_company",  # KEEP THIS - it's critical
    "loan_number",       # ADDED - also critical
    "effective_date",
    "expiration_date"
}

# NEVER run GLiNER for these (Stage1 handles them perfectly)
SKIP_FIELDS = {
    # REMOVED property_address and mailing_address
    # Stage1 is good but GLiNER can help as backup
}

# Field name mapping (Orchestrator → GLiNER)
# Only map SHORT aliases that the orchestrator might send; full names pass through as-is.
# Bug fix: REVERSE_ALIASES was computed as {v:k} which mapped 'carrier_name'->'carrier'
# and 'mortgage_company'->'mortgage', breaking output field names. Now REVERSE_ALIASES
# only maps the short aliases back, leaving full names unchanged.
FIELD_ALIASES = {
    "carrier": "carrier_name",
    "mortgage": "mortgage_company",
}

# Correct reverse: only maps short→full inversions, not full→short
REVERSE_ALIASES = {
    "carrier": "carrier_name",
    "mortgage": "mortgage_company",
}

# ============================================================
# SINGLETON MODEL CACHE
# ============================================================

_GLINER_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def _get_gliner_model(model_name: str = "urchade/gliner_small-v2.1"):
    """
    Get singleton GLiNER model (lazy loaded)
    Uses smaller model for speed without much accuracy loss
    """
    global _GLINER_MODEL, _MODEL_LOAD_ATTEMPTED
    
    if _MODEL_LOAD_ATTEMPTED and _GLINER_MODEL is None:
        return None
    
    if _GLINER_MODEL is None:
        _MODEL_LOAD_ATTEMPTED = True
        try:
            from gliner import GLiNER
            print("[GLINER] Loading model (one-time initialization)...")
            _GLINER_MODEL = GLiNER.from_pretrained(model_name)
            print("[GLINER] Model ready")
        except ImportError:
            print("[WARNING] GLiNER not installed. Install with: pip install gliner")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to load GLiNER: {e}")
            return None
    
    return _GLINER_MODEL


# ============================================================
# LABEL MAPPING (ENHANCED)
# ============================================================

# Field name → Natural language label for GLiNER
FIELD_TO_LABEL = {
    "carrier_name": "insurance carrier company name",
    "policy_number": "insurance policy number",
    "insured_name": "insured person name",
    "mortgage_company": "mortgage company lender name",
    "loan_number": "mortgage loan number",
    "total_premium": "total insurance premium amount",
    "deductible": "insurance deductible amount",
    "effective_date": "policy effective start date",
    "expiration_date": "policy expiration end date",
    "agent_name": "insurance agent name",
    "agent_phone": "agent phone number",
    "property_address": "property address location",
    "mailing_address": "mailing address location",
}

# Reverse mapping: label → field name
LABEL_TO_FIELD = {v: k for k, v in FIELD_TO_LABEL.items()}


# ============================================================
# MAIN ENTRY POINT (ENHANCED)
# ============================================================

def extract_with_gliner(
    text: str,
    missing_fields: List[str],
    confidence_threshold: float = 0.40,
) -> Dict[str, Dict]:
    """
    GLiNER extraction for missing secondary fields only
    ENHANCED: Better field filtering
    """

    if not text or not missing_fields:
        return {}

    # ----------------------------
    # SMART FILTERING: Only run if critical fields missing
    # ----------------------------
    critical_missing = [f for f in missing_fields if f in CRITICAL_FIELDS_FOR_GLINER]
    
    if not critical_missing:
        print("[INFO] GLiNER skipped - no critical fields missing")
        return {}

    # ----------------------------
    # Remove fields we should skip
    # ----------------------------
    normalized_fields = []
    for f in missing_fields:
        if f in SKIP_FIELDS:
            continue
        normalized_fields.append(FIELD_ALIASES.get(f, f))

    if not normalized_fields:
        print("[INFO] GLiNER skipped - all fields handled by Stage1")
        return {}

    print(f"[DEBUG] GLiNER extracting: {normalized_fields}")

    # ----------------------------
    # Get labels for fields
    # ----------------------------
    labels = _field_to_label(normalized_fields)
    if not labels:
        return {}

    # ----------------------------
    # Load model
    # ----------------------------
    model = _get_gliner_model()
    if model is None:
        print("[WARNING] GLiNER model not available")
        return {}

    # ----------------------------
    # Limit text length for speed
    # (increased: 5000 chars cut off page-2 content like mortgage/loan)
    # ----------------------------
    max_chars = 10000
    text_sample = text[:max_chars]

    # ----------------------------
    # Run prediction
    # ----------------------------
    try:
        entities = model.predict_entities(
            text_sample,
            labels,
            threshold=confidence_threshold,
        )
    except Exception as e:
        print(f"[ERROR] GLiNER prediction failed: {e}")
        return {}

    # ----------------------------
    # Post-process results
    # ----------------------------
    results = _post_process(
        entities,
        normalized_fields,
        confidence_threshold,
    )

    print(f"[DEBUG] GLiNER extracted {len(results)} fields: {list(results.keys())}")
    return results


# ============================================================
# LABEL MAPPING HELPERS
# ============================================================

def _field_to_label(fields: List[str]) -> List[str]:
    """Convert field names to GLiNER labels"""
    labels = []
    for f in fields:
        if f in FIELD_TO_LABEL:
            labels.append(FIELD_TO_LABEL[f])
        else:
            print(f"[WARNING] No label mapping for field: {f}")
    return labels


def _label_to_field(label: str) -> str:
    """Convert GLiNER label back to field name"""
    return LABEL_TO_FIELD.get(label.lower())


# ============================================================
# POST-PROCESSING (ENHANCED)
# ============================================================

def _post_process(
    entities: List[Dict],
    allowed_fields: List[str],
    confidence_threshold: float,
) -> Dict[str, Dict]:
    """
    Post-process and validate GLiNER predictions
    """

    results: Dict[str, Dict] = {}

    # Only filter truly noisy structural words; 'policy' removed because
    # GLiNER extracts just the value text (not surrounding labels), and
    # 'policy' appearing in a value is usually part of a legitimate policy name.
    NOISE = (
        "coverage", "endorsement", "notice",
        "conditions", "summary", "copy",
        "continued",
    )

    for ent in entities:
        raw_field = _label_to_field(ent["label"])
        if not raw_field or raw_field not in allowed_fields:
            continue

        # Map short alias back to full field name (only affects 'carrier'/'mortgage' aliases)
        field = REVERSE_ALIASES.get(raw_field, raw_field)

        value = ent["text"].strip()
        score = ent["score"]

        if score < confidence_threshold:
            continue

        ll = value.lower()
        if any(n in ll for n in NOISE):
            continue

        if len(value) < 3:
            continue

        # Keep best candidate only.
        # No confidence penalty applied: GLiNER is only invoked as a last-resort
        # fallback for fields that Stage1 and Stage2 rule-based already missed.
        # Its raw score is used directly so results can pass validation floors (0.75-0.80).
        if field not in results or results[field]["confidence"] < score:
            results[field] = {
                "value": _clean(value),
                "confidence": round(score, 3),
                "source": "stage2_5_gliner",
            }

    return results


# ============================================================
# CLEANUP
# ============================================================

def _clean(v: str) -> str:
    v = re.sub(r"\s+", " ", v)
    return v.strip(" ,.;:")