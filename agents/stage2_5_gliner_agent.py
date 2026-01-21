# """
# Stage 2.5 — GLiNER AI Agent (FINAL DROP-IN FIX)
# ==============================================
# • Gap filler for secondary fields only
# • NEVER creates or overrides policy_number
# • Handles orchestrator ↔ GLiNER field mismatch
# • Safe, strict, but actually functional
# """

# from typing import List, Dict
# import re

# # ============================================================
# # FORBIDDEN FIELDS (ABSOLUTE)
# # ============================================================

# FORBIDDEN_FIELDS = {
#     "policy_number",  # NEVER allowed here
# }

# # ============================================================
# # FIELD ALIASES (CRITICAL FIX)
# # Orchestrator → GLiNER schema
# # ============================================================

# FIELD_ALIASES = {
#     "carrier": "carrier_name",
#     "mortgage": "mortgage_company",
# }

# REVERSE_FIELD_ALIASES = {v: k for k, v in FIELD_ALIASES.items()}

# # ============================================================
# # SINGLETON MODEL (PERFORMANCE SAFE)
# # ============================================================

# _GLINER_MODEL = None


# def _get_model(model_name: str = "urchade/gliner_medium-v2.1"):
#     global _GLINER_MODEL
#     if _GLINER_MODEL is None:
#         from gliner import GLiNER
#         print("[INFO] Loading GLiNER model...")
#         _GLINER_MODEL = GLiNER.from_pretrained(model_name)
#         print("[INFO] GLiNER model loaded")
#     return _GLINER_MODEL


# # ============================================================
# # MAIN ENTRY
# # ============================================================

# def extract_with_gliner(
#     text: str,
#     missing_fields: List[str],
#     confidence_threshold: float = 0.65,
# ) -> Dict[str, Dict]:
#     """
#     GLiNER extraction for missing secondary fields only
#     """

#     if not text or not missing_fields:
#         return {}

#     # ----------------------------
#     # Normalize + filter fields
#     # ----------------------------
#     normalized_fields = []
#     for f in missing_fields:
#         if f in FORBIDDEN_FIELDS:
#             continue
#         normalized_fields.append(FIELD_ALIASES.get(f, f))

#     if not normalized_fields:
#         return {}

#     print(f"[DEBUG] GLiNER extracting: {normalized_fields}")

#     labels = _field_to_label(normalized_fields)
#     if not labels:
#         return {}

#     model = _get_model()
#     entities = model.predict_entities(
#         text,
#         labels,
#         threshold=confidence_threshold,
#     )

#     results = _post_process(
#         entities,
#         normalized_fields,
#         confidence_threshold,
#     )

#     print(f"[DEBUG] GLiNER extracted {len(results)} fields: {list(results.keys())}")
#     return results


# # ============================================================
# # LABEL MAPPING (STRICT + COMPLETE)
# # ============================================================

# def _field_to_label(fields: List[str]) -> List[str]:
#     mapping = {
#         "carrier_name": "insurance carrier name",
#         "mortgage_company": "mortgage company name",
#         "loan_number": "loan number",
#         "total_premium": "total premium amount",
#         "deductible": "deductible amount",
#         "effective_date": "policy effective date",
#         "expiration_date": "policy expiration date",
#         "agent_name": "insurance agent name",
#         "agent_phone": "agent phone number",
#     }

#     labels = []
#     for f in fields:
#         if f in mapping:
#             labels.append(mapping[f])
#         else:
#             print(f"[WARNING] No label mapping for field: {f}")

#     return labels


# def _label_to_field(label: str) -> str:
#     reverse = {
#         "insurance carrier name": "carrier_name",
#         "mortgage company name": "mortgage_company",
#         "loan number": "loan_number",
#         "total premium amount": "total_premium",
#         "deductible amount": "deductible",
#         "policy effective date": "effective_date",
#         "policy expiration date": "expiration_date",
#         "insurance agent name": "agent_name",
#         "agent phone number": "agent_phone",
#     }
#     return reverse.get(label.lower())


# # ============================================================
# # POST-PROCESSING (STRICT BUT REALISTIC)
# # ============================================================

# def _post_process(
#     entities: List[Dict],
#     allowed_fields: List[str],
#     confidence_threshold: float,
# ) -> Dict[str, Dict]:

#     results: Dict[str, Dict] = {}

#     NOISE = (
#         "policy", "coverage", "endorsement", "notice",
#         "conditions", "summary", "page", "copy",
#         "continued", "information",
#     )

#     for ent in entities:
#         raw_field = _label_to_field(ent["label"])
#         if not raw_field or raw_field not in allowed_fields:
#             continue

#         # Map back to orchestrator field if needed
#         field = REVERSE_FIELD_ALIASES.get(raw_field, raw_field)

#         value = ent["text"].strip()
#         score = ent["score"]

#         if score < confidence_threshold:
#             continue

#         ll = value.lower()
#         if any(n in ll for n in NOISE):
#             continue

#         if len(value) < 3:
#             continue

#         # Keep best candidate only
#         if field not in results or results[field]["confidence"] < score:
#             results[field] = {
#                 "value": _clean(value),
#                 "confidence": round(score * 0.82, 3),  # AI penalty
#                 "source": "stage2_5_gliner",
#             }

#     return results


# # ============================================================
# # CLEANUP
# # ============================================================

# def _clean(v: str) -> str:
#     v = re.sub(r"\s+", " ", v)
#     return v.strip(" ,.;:")


"""
Stage 2.5 – GLiNER AI Agent (SPEED OPTIMIZED)
==============================================
• Only runs if CRITICAL fields are missing
• Skips for common fields
• Uses smaller/faster model option
"""

from typing import List, Dict
import re

# ============================================================
# CONFIGURATION
# ============================================================

# Only run GLiNER if these CRITICAL fields are missing
CRITICAL_FIELDS_FOR_GLINER = {
    "mortgage_company",
    "agent_name",
}

# NEVER run GLiNER for these (Stage1 handles them well)
SKIP_FIELDS = {
    "policy_number",
    "insured_name",
    "property_address",
    "loan_number",
}

# ============================================================
# FIELD ALIASES
# ============================================================

FIELD_ALIASES = {
    "carrier": "carrier_name",
    "mortgage": "mortgage_company",
}

REVERSE_FIELD_ALIASES = {v: k for k, v in FIELD_ALIASES.items()}

# ============================================================
# SINGLETON MODEL (LAZY LOAD)
# ============================================================

_GLINER_MODEL = None


def _get_model(model_name: str = "urchade/gliner_small-v2.1"):  # ← SMALLER MODEL
    global _GLINER_MODEL
    if _GLINER_MODEL is None:
        try:
            from gliner import GLiNER
            print("[INFO] Loading GLiNER model (one-time)...")
            _GLINER_MODEL = GLiNER.from_pretrained(model_name)
            print("[INFO] GLiNER model ready")
        except Exception as e:
            print(f"[ERROR] Failed to load GLiNER: {e}")
            _GLINER_MODEL = None
    return _GLINER_MODEL


# ============================================================
# MAIN ENTRY (WITH SMART SKIP LOGIC)
# ============================================================

def extract_with_gliner(
    text: str,
    missing_fields: List[str],
    confidence_threshold: float = 0.65,
) -> Dict[str, Dict]:
    """
    GLiNER extraction - ONLY runs when critical fields missing
    """

    if not text or not missing_fields:
        return {}

    # ----------------------------
    # SPEED OPTIMIZATION 1: Skip if no critical fields missing
    # ----------------------------
    critical_missing = [f for f in missing_fields if f in CRITICAL_FIELDS_FOR_GLINER]
    
    if not critical_missing:
        print("[INFO] GLiNER skipped - no critical fields missing")
        return {}

    # ----------------------------
    # SPEED OPTIMIZATION 2: Remove fields Stage1 handles
    # ----------------------------
    normalized_fields = []
    for f in missing_fields:
        if f in SKIP_FIELDS:
            continue
        normalized_fields.append(FIELD_ALIASES.get(f, f))

    if not normalized_fields:
        print("[INFO] GLiNER skipped - all fields handled by Stage1")
        return {}

    print(f"[INFO] GLiNER extracting: {normalized_fields}")

    labels = _field_to_label(normalized_fields)
    if not labels:
        return {}

    model = _get_model()
    if model is None:
        print("[WARNING] GLiNER model not available")
        return {}

    # ----------------------------
    # SPEED OPTIMIZATION 3: Limit text length
    # ----------------------------
    max_chars = 5000  # Only analyze first 5000 chars
    text_sample = text[:max_chars]

    try:
        entities = model.predict_entities(
            text_sample,
            labels,
            threshold=confidence_threshold,
        )
    except Exception as e:
        print(f"[ERROR] GLiNER prediction failed: {e}")
        return {}

    results = _post_process(
        entities,
        normalized_fields,
        confidence_threshold,
    )

    print(f"[INFO] GLiNER extracted {len(results)} fields: {list(results.keys())}")
    return results


# ============================================================
# LABEL MAPPING
# ============================================================

def _field_to_label(fields: List[str]) -> List[str]:
    mapping = {
        "carrier_name": "insurance carrier name",
        "mortgage_company": "mortgage company name",
        "loan_number": "loan number",
        "total_premium": "total premium amount",
        "deductible": "deductible amount",
        "effective_date": "policy effective date",
        "expiration_date": "policy expiration date",
        "agent_name": "insurance agent name",
        "agent_phone": "agent phone number",
    }

    labels = []
    for f in fields:
        if f in mapping:
            labels.append(mapping[f])

    return labels


def _label_to_field(label: str) -> str:
    reverse = {
        "insurance carrier name": "carrier_name",
        "mortgage company name": "mortgage_company",
        "loan number": "loan_number",
        "total premium amount": "total_premium",
        "deductible amount": "deductible",
        "policy effective date": "effective_date",
        "policy expiration date": "expiration_date",
        "insurance agent name": "agent_name",
        "agent phone number": "agent_phone",
    }
    return reverse.get(label.lower())


# ============================================================
# POST-PROCESSING
# ============================================================

def _post_process(
    entities: List[Dict],
    allowed_fields: List[str],
    confidence_threshold: float,
) -> Dict[str, Dict]:

    results: Dict[str, Dict] = {}

    NOISE = (
        "policy", "coverage", "endorsement", "notice",
        "conditions", "summary", "page", "copy",
        "continued", "information",
    )

    for ent in entities:
        raw_field = _label_to_field(ent["label"])
        if not raw_field or raw_field not in allowed_fields:
            continue

        field = REVERSE_FIELD_ALIASES.get(raw_field, raw_field)

        value = ent["text"].strip()
        score = ent["score"]

        if score < confidence_threshold:
            continue

        ll = value.lower()
        if any(n in ll for n in NOISE):
            continue

        if len(value) < 3:
            continue

        # Keep best candidate only
        if field not in results or results[field]["confidence"] < score:
            results[field] = {
                "value": _clean(value),
                "confidence": round(score * 0.82, 3),
                "source": "stage2_5_gliner",
            }

    return results

# ============================================================
# CLEANUP
# ============================================================

def _clean(v: str) -> str:
    v = re.sub(r"\s+", " ", v)
    return v.strip(" ,.;:")