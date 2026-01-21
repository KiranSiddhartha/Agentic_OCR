# """
# Stage 2 – Semantic Gap Filler (NON-AUTHORITATIVE)
# ================================================
# Fills ONLY missing fields after Stage 1.
# """

# from typing import List, Dict
# import re


# def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
#     if not lines or not missing_fields:
#         return {}

#     out: Dict[str, Dict] = {}

#     for line in lines:
#         clean = _semantic_cleanup(line)

#         if "insured_name" in missing_fields and _valid_name(clean):
#             out["insured_name"] = _candidate(clean, "semantic_rules", 0.75)

#         if (
#             "mailing_address" in missing_fields or "property_address" in missing_fields
#         ) and _valid_address(clean):
#             field = (
#                 "mailing_address"
#                 if "mailing_address" in missing_fields
#                 else "property_address"
#             )
#             out[field] = _candidate(clean, "semantic_rules", 0.72)

#     return out


# # ============================================================
# # SEMANTIC NORMALIZATION
# # ============================================================

# def _semantic_cleanup(text: str) -> str:
#     # Remove date phrases
#     text = re.sub(
#         r"\b(Beginning|through|since)?\s*[A-Z][a-z]+ \d{1,2},? \d{4}",
#         "",
#         text,
#     )

#     # Remove leading prose
#     text = re.sub(r".* for (\d+ .+)", r"\1", text, flags=re.I)

#     return text.strip()


# # ============================================================
# # VALIDATORS
# # ============================================================

# def _valid_name(text: str) -> bool:
#     if ":" in text or any(c.isdigit() for c in text):
#         return False
#     return 2 <= len(text.split()) <= 6


# def _valid_address(text: str) -> bool:
#     return bool(
#         re.search(r"\d+ .* (st|ave|rd|blvd|ln|dr)", text.lower())
#         or "po box" in text.lower()
#     )


# def _candidate(value: str, source: str, confidence: float) -> Dict:
#     return {
#         "value": value,
#         "confidence": min(confidence, 0.80),
#         "source": source,
#     }


# """
# Stage 2 — Semantic Gap Filler (PERFORMANCE OPTIMIZED)
# ====================================================
# Fills ONLY missing fields after Stage 1.
# GLiNER model cached globally for speed.
# """

# from typing import List, Dict
# import re


# # ============================================================
# # CONFIGURATION
# # ============================================================

# USE_GLINER = True  # Set to False to disable AI completely
# GLINER_CONFIDENCE_THRESHOLD = 0.70


# # ============================================================
# # MAIN ENTRYPOINT (OPTIMIZED)
# # ============================================================

# def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
#     """
#     Extract missing fields using rules + AI (FAST VERSION)
    
#     Performance:
#     - Rules: ~10-20ms
#     - GLiNER (first call): ~100-200ms (model already loaded)
#     - GLiNER (subsequent): ~50-100ms
#     """
#     if not lines or not missing_fields:
#         return {}

#     # Stage 2A: Rule-based extraction (FAST)
#     rule_based = _extract_with_rules(lines, missing_fields)
    
#     # Early exit if all fields found
#     if len(rule_based) == len(missing_fields):
#         return rule_based
    
#     # Stage 2B: AI extraction for remaining missing fields
#     if USE_GLINER:
#         still_missing = [f for f in missing_fields if f not in rule_based]
        
#         if still_missing:
#             # Join lines once (faster than multiple joins)
#             text = "\n".join(lines)
            
#             # Use fast extraction function (singleton model)
#             ai_results = _extract_with_gliner_fast(text, still_missing)
            
#             # Merge results (rules take priority)
#             for field, data in ai_results.items():
#                 if field not in rule_based:
#                     rule_based[field] = data
    
#     return rule_based


# # ============================================================
# # RULE-BASED EXTRACTION (UNCHANGED)
# # ============================================================

# def _extract_with_rules(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
#     """Original rule-based extraction"""
#     out: Dict[str, Dict] = {}

#     for line in lines:
#         # Early exit if all fields found
#         if len(out) == len(missing_fields):
#             break
        
#         clean = _semantic_cleanup(line)

#         if "insured_name" in missing_fields and "insured_name" not in out:
#             if _valid_name(clean):
#                 out["insured_name"] = _candidate(clean, "semantic_rules", 0.75)

#         if ("mailing_address" in missing_fields or "property_address" in missing_fields):
#             if _valid_address(clean):
#                 field = (
#                     "mailing_address"
#                     if "mailing_address" in missing_fields
#                     else "property_address"
#                 )
#                 if field not in out:
#                     out[field] = _candidate(clean, "semantic_rules", 0.72)

#     return out


# # ============================================================
# # AI EXTRACTION (OPTIMIZED)
# # ============================================================

# def _extract_with_gliner_fast(text: str, missing_fields: List[str]) -> Dict[str, Dict]:
#     """
#     Extract fields using GLiNER AI (FAST VERSION)
#     Uses global singleton model - no initialization overhead
#     """
#     try:
#         # Import optimized version with singleton model
#         from stage2_5_gliner_agent import extract_fields
        
#         # This is FAST because model is already loaded
#         results = extract_fields(
#             text,
#             missing_fields,
#             confidence_threshold=GLINER_CONFIDENCE_THRESHOLD
#         )
        
#         return results
        
#     except ImportError:
#         # Only warn once
#         if not hasattr(_extract_with_gliner_fast, '_warned'):
#             print("[WARNING] GLiNER not available. Install with: pip install gliner")
#             _extract_with_gliner_fast._warned = True
#         return {}
#     except Exception as e:
#         # Only warn once per error type
#         error_key = type(e).__name__
#         if not hasattr(_extract_with_gliner_fast, f'_warned_{error_key}'):
#             print(f"[WARNING] GLiNER extraction failed: {e}")
#             setattr(_extract_with_gliner_fast, f'_warned_{error_key}', True)
#         return {}


# # ============================================================
# # SEMANTIC NORMALIZATION (UNCHANGED)
# # ============================================================

# def _semantic_cleanup(text: str) -> str:
#     # Remove date phrases
#     text = re.sub(
#         r"\b(Beginning|through|since)?\s*[A-Z][a-z]+ \d{1,2},? \d{4}",
#         "",
#         text,
#     )
#     # Remove leading prose
#     text = re.sub(r".* for (\d+ .+)", r"\1", text, flags=re.I)
#     return text.strip()


# # ============================================================
# # VALIDATORS (UNCHANGED)
# # ============================================================

# def _valid_name(text: str) -> bool:
#     if ":" in text or any(c.isdigit() for c in text):
#         return False
#     return 2 <= len(text.split()) <= 6


# def _valid_address(text: str) -> bool:
#     return bool(
#         re.search(r"\d+ .* (st|ave|rd|blvd|ln|dr)", text.lower())
#         or "po box" in text.lower()
#     )


# def _candidate(value: str, source: str, confidence: float) -> Dict:
#     return {
#         "value": value,
#         "confidence": min(confidence, 0.80),
#         "source": source,
#     }

"""
Stage 2 – Semantic Gap Filler (MINIMAL FIX - PASTE THIS AT TOP OF YOUR FILE)
==============================================================================
This version has the EXACT function signature your orchestrator expects.
"""

from typing import List, Dict
import re


# ============================================================
# MAIN ENTRYPOINT - THIS MUST EXIST
# ============================================================

def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
    """
    Extract missing fields using rules + AI
    
    THIS FUNCTION NAME MUST MATCH EXACTLY what orchestrator.py imports
    """
    if not lines or not missing_fields:
        return {}

    # Stage 2A: Rule-based extraction
    rule_based = _extract_with_rules(lines, missing_fields)
    
    # Early exit if all fields found
    if len(rule_based) == len(missing_fields):
        return rule_based
    
    # Stage 2B: Try AI extraction if available
    try:
        still_missing = [f for f in missing_fields if f not in rule_based]
        
        if still_missing:
            text = "\n".join(lines)
            ai_results = _extract_with_gliner_safe(text, still_missing)
            
            # Merge results
            for field, data in ai_results.items():
                if field not in rule_based:
                    rule_based[field] = data
    except Exception as e:
        print(f"[WARNING] AI extraction failed: {e}")
    
    return rule_based


# ============================================================
# RULE-BASED EXTRACTION (SAFE)
# ============================================================

def _extract_with_rules(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
    """Enhanced rule-based extraction"""
    out: Dict[str, Dict] = {}

    for idx, line in enumerate(lines):
        if len(out) == len(missing_fields):
            break
        
        clean = _semantic_cleanup(line)
        
        # Policy number
        if "policy_number" in missing_fields and "policy_number" not in out:
            policy = _extract_policy_number(line)
            if policy:
                out["policy_number"] = {"value": policy, "confidence": 0.85, "source": "semantic_policy"}
        
        # Insured name
        if "insured_name" in missing_fields and "insured_name" not in out:
            if ':' in line and any(k in line.lower() for k in ["insured", "name", "policyholder"]):
                parts = line.split(':', 1)
                value = parts[1].strip()
                if _valid_name(value):
                    out["insured_name"] = {"value": value, "confidence": 0.80, "source": "semantic_inline_name"}
            elif _valid_name(clean):
                out["insured_name"] = {"value": clean, "confidence": 0.75, "source": "semantic_name"}
        
        # Address extraction
        if ("mailing_address" in missing_fields or "property_address" in missing_fields):
            if _valid_address(clean):
                field = "mailing_address" if "mailing_address" in missing_fields else "property_address"
                if field not in out:
                    out[field] = {"value": clean, "confidence": 0.72, "source": "semantic_address"}
        
        # Loan number
        if "loan_number" in missing_fields and "loan_number" not in out:
            loan = _extract_loan_number(line)
            if loan:
                out["loan_number"] = {"value": loan, "confidence": 0.82, "source": "semantic_loan"}

    return out


# ============================================================
# GLINER WRAPPER (SAFE)
# ============================================================

def _extract_with_gliner_safe(text: str, missing_fields: List[str]) -> Dict[str, Dict]:
    """
    Safe wrapper for GLiNER extraction
    """
    try:
        # Import from stage2_5
        from agents.stage2_5_gliner_agent import extract_with_gliner
        
        return extract_with_gliner(text, missing_fields, confidence_threshold=0.65)
        
    except ImportError:
        # GLiNER not available
        return {}
    except Exception as e:
        print(f"[ERROR] GLiNER failed: {e}")
        return {}


# ============================================================
# EXTRACTORS
# ============================================================

def _extract_policy_number(line: str) -> str:
    """Extract policy number"""
    if ':' in line:
        ll = line.lower()
        if any(k in ll for k in ["policy number", "policy no", "policy #"]):
            parts = line.split(':', 1)
            value = parts[1].strip().replace(" ", "")
            if _valid_policy_number(value):
                return value
    
    policy_pattern = re.compile(r'\b[A-Z0-9]{2,}[-\s]?[A-Z0-9]{4,}\b')
    matches = policy_pattern.findall(line)
    for match in matches:
        v = match.replace(" ", "")
        if _valid_policy_number(v):
            return v
    
    return None


def _extract_loan_number(line: str) -> str:
    """Extract loan number"""
    if ':' in line:
        ll = line.lower()
        if any(k in ll for k in ["loan number", "loan #", "loan"]):
            parts = line.split(':', 1)
            value = parts[1].strip()
            if _valid_loan_number(value):
                return value
    
    loan_pattern = re.compile(r'\b\d{10,}\b')
    matches = loan_pattern.findall(line)
    for match in matches:
        if _valid_loan_number(match):
            return match
    
    return None


# ============================================================
# CLEANUP
# ============================================================

def _semantic_cleanup(text: str) -> str:
    """Clean text"""
    text = re.sub(r'\b[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}', '', text)
    text = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', '', text)
    text = re.sub(r'\$[\d,]+(\.\d{2})?', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================
# VALIDATORS
# ============================================================

def _valid_policy_number(text: str) -> bool:
    if not text or len(text) < 5:
        return False
    if re.search(r'\(\d{3}\)', text):
        return False
    if re.fullmatch(r'\d{5}(-\d{4})?', text):
        return False
    digits = sum(c.isdigit() for c in text)
    return digits >= 4 and 5 <= len(text) <= 30


def _valid_loan_number(text: str) -> bool:
    if not text:
        return False
    digits = sum(c.isdigit() for c in text)
    return digits >= 6 and 6 <= len(text) <= 25


def _valid_name(text: str) -> bool:
    if not text or ':' in text:
        return False
    
    has_entity = any(w in text.lower() for w in ["llc", "inc", "corp", "company", "trust"])
    if any(c.isdigit() for c in text) and not has_entity:
        return False
    
    ll = text.lower()
    bad_words = ["policy", "coverage", "notice", "summary", "premium", "billing"]
    if any(bad in ll for bad in bad_words):
        return False
    
    words = text.split()
    if has_entity:
        return 2 <= len(words) <= 10
    
    return 2 <= len(words) <= 6


def _valid_address(text: str) -> bool:
    if not text:
        return False
    
    ll = text.lower()
    
    # PO Box
    if "po box" in ll or "p.o. box" in ll:
        return True
    
    # Street pattern
    street_pattern = re.compile(
        r'\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court)\b',
        re.I
    )
    if street_pattern.search(text):
        return True
    
    # Has state + ZIP
    if re.search(r'\b[A-Z]{2}\s*\d{5}', text):
        return True
    
    # Has number + reasonable length
    has_number = bool(re.search(r'\d+', text))
    word_count = len(text.split())
    
    return has_number and word_count >= 3