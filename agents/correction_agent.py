# # agents/correction_agent.py
# # Enhanced OCR correction with careful noise removal
# # Preserves valid insurance terminology

# import re
# from utils.dictionary import OCR_FIXES

# # Logging for debugging
# CORRECTION_LOG = []
# ENABLE_LOGGING = True


# def correct_lines(lines, debug=False):
#     """
#     Correction with CAREFUL NOISE REMOVAL.
#     Removes garbled text while preserving valid insurance terms.
#     """
#     global ENABLE_LOGGING
#     ENABLE_LOGGING = debug
#     CORRECTION_LOG.clear()
    
#     if not lines:
#         return []
    
#     corrected = []
    
#     for idx, line in enumerate(lines):
#         if not line or not line.strip():
#             continue
        
#         original = line
        
#         # Stage 1: Remove obvious garbled text
#         line = remove_garbled_text(line)
        
#         # Stage 2: Dictionary fixes
#         line = apply_dictionary_fixes(line)
        
#         # Stage 3: Character corrections
#         line = fix_obvious_chars(line)
        
#         # Stage 4: Spacing cleanup
#         line = re.sub(r'\s+', ' ', line).strip()
        
#         # Stage 5: Validate line quality
#         if is_valid_line(line):
#             corrected.append(line)
#             if ENABLE_LOGGING and line != original:
#                 CORRECTION_LOG.append({
#                     "line": idx,
#                     "original": original,
#                     "corrected": line,
#                     "action": "corrected"
#                 })
#         else:
#             if ENABLE_LOGGING:
#                 CORRECTION_LOG.append({
#                     "line": idx,
#                     "original": original,
#                     "corrected": line,
#                     "action": "removed_as_noise"
#                 })
    
#     return corrected


# def remove_garbled_text(text):
#     """
#     Remove garbled OCR noise while preserving valid terms.
#     CAREFUL approach - only remove obvious noise.
#     """
#     if not text:
#         return ""
    
#     # Pattern 1: Repeating nonsense patterns (e.g., "aen aen aen")
#     text = re.sub(r'[-\s]*\b([a-z]{2,3})\s+\1\s+\1\b', '', text, flags=re.IGNORECASE)
    
#     # Pattern 2: Lines with excessive consonant clusters
#     # BUT: Be more careful - use 15% threshold instead of 20%
#     words = text.split()
#     cleaned_words = []
    
#     for word in words:
#         # Skip short words (likely valid)
#         if len(word) <= 4:
#             cleaned_words.append(word)
#             continue
        
#         # Check vowel ratio for longer words
#         if len(word) > 5:
#             vowel_count = sum(1 for c in word.lower() if c in 'aeiou')
#             vowel_ratio = vowel_count / len(word) if len(word) > 0 else 0
            
#             # RELAXED: If < 15% vowels, likely garbled (was 20%)
#             if vowel_ratio < 0.15:
#                 if ENABLE_LOGGING:
#                     CORRECTION_LOG.append({
#                         "word": word,
#                         "action": "removed_low_vowels",
#                         "vowel_ratio": f"{vowel_ratio:.2f}"
#                     })
#                 continue  # Skip this word
        
#         cleaned_words.append(word)
    
#     text = ' '.join(cleaned_words)
    
#     # Pattern 3: Remove repeating character clusters (e.g., "aaaa", "----")
#     text = re.sub(r'\b([a-z])\1{4,}\b', '', text, flags=re.IGNORECASE)
    
#     # Pattern 4: Remove standalone dash/hyphen clusters
#     text = re.sub(r'\s[-]{2,}\s', ' ', text)
    
#     # Pattern 5: Remove obvious OCR artifacts
#     text = re.sub(r'[|]{2,}', '', text)  # Multiple pipes
#     text = re.sub(r'_{3,}', '', text)    # Multiple underscores
    
#     return text


# def apply_dictionary_fixes(text):
#     """
#     Apply dictionary corrections for common OCR errors.
#     Enhanced with insurance-specific terms.
#     """
    
#     # Apply standard OCR fixes
#     for error, fix in OCR_FIXES.items():
#         # Whole word replacement (case-insensitive)
#         pattern = r'\b' + re.escape(error) + r'\b'
#         text = re.sub(pattern, fix, text, flags=re.IGNORECASE)
    
#     # Additional insurance-specific fixes
#     insurance_fixes = {
#         # Common OCR errors in insurance docs
#         "po1icy": "policy",
#         "po|icy": "policy",
#         "pollcy": "policy",
#         "insuranee": "insurance",
#         "insuronce": "insurance",
#         "eoverage": "coverage",
#         "covergae": "coverage",
#         "premíum": "premium",
#         "premiurn": "premium",
#         "dwe11ing": "dwelling",
#         "dweliing": "dwelling",
#         "mortgagee": "mortgage",
#         "mortage": "mortgage",
#         "efective": "effective",
#         "eflective": "effective",
#         "expiration": "expiration",
#         "expriration": "expiration",
#         "borrower": "borrower",
#         "borrover": "borrower",
#         "certifícate": "certificate",
#         "certificat": "certificate",
#         "deductib1e": "deductible",
#         "deductibie": "deductible",
#     }
    
#     for error, fix in insurance_fixes.items():
#         pattern = r'\b' + re.escape(error) + r'\b'
#         text = re.sub(pattern, fix, text, flags=re.IGNORECASE)
    
#     return text


# def fix_obvious_chars(text):
#     """
#     Fix obvious character confusions.
#     CAREFUL: Only fix when context is clear.
#     """
    
#     # Numbers: O→0, l→1 (only when surrounded by digits)
#     text = re.sub(r'(?<=\d)O(?=\d)', '0', text)
#     text = re.sub(r'(?<=\d)l(?=\d)', '1', text)
#     text = re.sub(r'(?<=\d)I(?=\d)', '1', text)
    
#     # Words: 0→o, 1→I (only when surrounded by letters)
#     text = re.sub(r'(?<=[a-z])0(?=[a-z])', 'o', text, flags=re.IGNORECASE)
#     text = re.sub(r'(?<=[a-z])1(?=[a-z])', 'l', text, flags=re.IGNORECASE)
    
#     # Common punctuation fixes
#     text = re.sub(r',,+', ',', text)  # Multiple commas
#     text = re.sub(r'\.\.+', '.', text)  # Multiple periods
    
#     # Fix common character substitutions
#     text = text.replace('|', 'I')  # Pipe to capital I in words
#     text = re.sub(r'\b([A-Z])0([a-z])', r'\1o\2', text)  # Capital letter + 0 + lowercase = o
    
#     return text


# def is_valid_line(text):
#     """
#     Validate if line should be kept.
#     RELAXED validation - keep most lines.
#     """
#     if not text or len(text.strip()) < 2:
#         return False
    
#     # Check character composition
#     alphanumeric = sum(c.isalnum() for c in text)
#     total = len(text)
    
#     # RELAXED: Must be at least 25% alphanumeric (was 30%)
#     if total > 0 and alphanumeric < total * 0.25:
#         return False
    
#     # Check for excessive punctuation (noise)
#     punct_count = sum(1 for c in text if c in '.,;:-_|/')
#     # RELAXED: Allow up to 60% punctuation (was 50%)
#     if total > 0 and punct_count > len(text) * 0.60:
#         return False
    
#     # Check for repeating noise patterns (same substring 4+ times)
#     if re.search(r'(.{2,})\1{3,}', text):
#         return False
    
#     # PRESERVE lines with insurance keywords
#     insurance_keywords = [
#         'policy', 'insurance', 'coverage', 'premium', 'deductible',
#         'dwelling', 'mortgage', 'insured', 'borrower', 'loan',
#         'effective', 'expiration', 'certificate', 'carrier',
#         'property', 'address', 'date', 'number', 'amount'
#     ]
    
#     text_lower = text.lower()
#     if any(keyword in text_lower for keyword in insurance_keywords):
#         return True  # Always keep lines with insurance terms
    
#     return True


# def get_correction_log():
#     """Return correction log for debugging"""
#     return CORRECTION_LOG.copy()


# def clear_correction_log():
#     """Clear correction log"""
#     CORRECTION_LOG.clear()


# # ============================================================
# # ADDITIONAL UTILITIES
# # ============================================================

# def clean_field_value(value: str) -> str:
#     """
#     Clean extracted field value.
#     Remove trailing punctuation, normalize spacing.
#     """
#     if not value:
#         return ""
    
#     # Remove leading/trailing whitespace
#     value = value.strip()
    
#     # Remove trailing punctuation (but keep internal punctuation)
#     value = value.rstrip('.,;:')
    
#     # Normalize internal spacing
#     value = re.sub(r'\s+', ' ', value)
    
#     # Remove common OCR artifacts at edges
#     value = value.strip('|_-')
    
#     return value


# def validate_extracted_value(field_name: str, value: str) -> bool:
#     """
#     Quick validation for extracted values.
#     Returns True if value looks reasonable for the field type.
#     """
#     if not value or len(value) < 2:
#         return False
    
#     value_lower = value.lower()
    
#     # Policy number: should have some digits
#     if field_name == "policy_number":
#         return sum(c.isdigit() for c in value) >= 3
    
#     # Names: should not have numbers
#     if field_name in ["insured_name", "agent", "carrier"]:
#         return not any(c.isdigit() for c in value)
    
#     # Dates: should match date pattern
#     if "date" in field_name:
#         return bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', value))
    
#     # Addresses: should have some numbers
#     if "address" in field_name:
#         return any(c.isdigit() for c in value)
    
#     # Amounts: should have digits and possibly $
#     if field_name in ["total_premium", "balance_due", "dwelling_coverage", "deductible"]:
#         return sum(c.isdigit() for c in value) >= 1
    
#     return True

"""
OCR Correction Agent – MAXIMUM RECALL MODE
========================================

Purpose:
- Improve OCR quality BEFORE deterministic extraction
- Preserve ALL keyword anchors required by Stage 1
- Preserve line order
- Remove only extreme garbage
- Never infer, normalize meaning, or extract fields

This agent MUST run before stage1_deterministic_agent.
"""

import re
from typing import List, Dict

try:
    from utils.dictionary import OCR_FIXES
except Exception:
    OCR_FIXES = {}

# ============================================================
# DEBUG LOGGING
# ============================================================

_CORRECTION_LOG: List[Dict] = []
_ENABLE_LOGGING = False


# ============================================================
# PUBLIC ENTRYPOINT
# ============================================================

def correct_lines(lines: List[str], debug: bool = False) -> List[str]:
    """
    Main OCR correction entrypoint – Stage-1 SAFE.
    """
    global _ENABLE_LOGGING
    _ENABLE_LOGGING = debug
    _CORRECTION_LOG.clear()

    if not lines:
        return []

    corrected: List[str] = []

    for idx, raw in enumerate(lines):
        if not raw or not raw.strip():
            continue

        original = raw.rstrip()
        text = original

        # --- Stage 1: extreme garbage removal only ---
        text = _remove_garbled_text(text)

        # --- Stage 2: dictionary OCR fixes (insurance-safe) ---
        text = _apply_dictionary_fixes(text)

        # --- Stage 3: character confusions ---
        text = _fix_char_confusions(text)

        # --- Stage 4: spacing (DO NOT REMOVE COLONS) ---
        text = re.sub(r"[ \t]+", " ", text).strip()

        # --- Stage 5: line retention decision ---
        final = _choose_best(original, text)

        if _is_valid_line(final):
            corrected.append(final)
            _log(idx, original, final, "kept")
        else:
            _log(idx, original, final, "removed_noise")

    return corrected


# ============================================================
# SAFETY: KEEP BEST VERSION
# ============================================================

def _choose_best(original: str, cleaned: str) -> str:
    """
    Preserve anchors: if cleaning removed digits, colons,
    or insurance keywords, keep original.
    """
    if ":" in original and ":" not in cleaned:
        return original

    if sum(c.isdigit() for c in cleaned) < sum(c.isdigit() for c in original):
        return original

    KEYWORDS = (
        "policy", "insured", "property", "mailing", "address",
        "mortgage", "premium", "coverage", "effective", "expiration"
    )

    ol = original.lower()
    cl = cleaned.lower()

    if any(k in ol and k not in cl for k in KEYWORDS):
        return original

    return cleaned


# ============================================================
# NOISE REMOVAL (EXTREME ONLY)
# ============================================================

def _remove_garbled_text(text: str) -> str:
    if not text:
        return ""

    # repeated nonsense tokens (aen aen aen)
    text = re.sub(r'\b([a-z]{2,3})\s+\1\s+\1\b', '', text, flags=re.I)

    words = text.split()
    kept = []

    for w in words:
        # ALWAYS preserve anything with digits
        if any(c.isdigit() for c in w):
            kept.append(w)
            continue

        # ALWAYS preserve short words
        if len(w) <= 4:
            kept.append(w)
            continue

        # Long nonsense words only
        if len(w) > 7:
            vowels = sum(1 for c in w.lower() if c in "aeiou")
            if vowels / len(w) < 0.10:
                _log_word(w)
                continue

        kept.append(w)

    text = " ".join(kept)

    # Extreme spam only
    text = re.sub(r'\b([a-z])\1{5,}\b', '', text, flags=re.I)
    text = re.sub(r'[|]{3,}', '', text)
    text = re.sub(r'_{4,}', '', text)

    return text


# ============================================================
# OCR FIXES
# ============================================================

def _apply_dictionary_fixes(text: str) -> str:
    for err, fix in OCR_FIXES.items():
        text = re.sub(rf"\b{re.escape(err)}\b", fix, text, flags=re.I)

    INSURANCE_FIXES = {
        "po1icy": "policy",
        "pollcy": "policy",
        "insuranee": "insurance",
        "covergae": "coverage",
        "premiurn": "premium",
        "mortage": "mortgage",
        "efective": "effective",
        "expriration": "expiration",
        "deductib1e": "deductible",
    }

    for err, fix in INSURANCE_FIXES.items():
        text = re.sub(rf"\b{re.escape(err)}\b", fix, text, flags=re.I)

    return text


def _fix_char_confusions(text: str) -> str:
    text = re.sub(r'(?<=\d)[Oo](?=\d)', '0', text)
    text = re.sub(r'(?<=\d)[Il](?=\d)', '1', text)
    text = re.sub(r'(?<=[A-Za-z])0(?=[A-Za-z])', 'o', text)
    text = re.sub(r'(?<=[A-Za-z])1(?=[A-Za-z])', 'l', text)
    return text


# ============================================================
# LINE QUALITY (STAGE-1 SAFE)
# ============================================================

def _is_valid_line(text: str) -> bool:
    if not text or len(text) < 2:
        return False

    # ALWAYS keep headers
    if text.endswith(":") or text.isupper():
        return True

    total = len(text)
    alnum = sum(c.isalnum() for c in text)

    if alnum < total * 0.15:
        return False

    return True


# ============================================================
# LOGGING
# ============================================================

def _log(idx, original, corrected, action):
    if _ENABLE_LOGGING:
        _CORRECTION_LOG.append({
            "line": idx,
            "original": original,
            "corrected": corrected,
            "action": action,
        })


def _log_word(word):
    if _ENABLE_LOGGING:
        _CORRECTION_LOG.append({
            "word": word,
            "action": "removed_noise",
        })


def get_correction_log() -> List[Dict]:
    return list(_CORRECTION_LOG)


def clear_correction_log():
    _CORRECTION_LOG.clear()
