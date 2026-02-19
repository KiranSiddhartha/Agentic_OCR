# """
# OCR Correction Agent – MAXIMUM RECALL MODE
# ========================================

# Purpose:
# - Improve OCR quality BEFORE deterministic extraction
# - Preserve ALL keyword anchors required by Stage 1
# - Preserve line order
# - Remove only extreme garbage
# - Never infer, normalize meaning, or extract fields

# This agent MUST run before stage1_deterministic_agent.
# """

# import re
# from typing import List, Dict

# try:
#     from utils.dictionary import OCR_FIXES
# except Exception:
#     OCR_FIXES = {}

# # ============================================================
# # DEBUG LOGGING
# # ============================================================

# _CORRECTION_LOG: List[Dict] = []
# _ENABLE_LOGGING = False


# # ============================================================
# # PUBLIC ENTRYPOINT
# # ============================================================

# def correct_lines(lines: List[str], debug: bool = False) -> List[str]:
#     """
#     Main OCR correction entrypoint – Stage-1 SAFE.
#     """
#     global _ENABLE_LOGGING
#     _ENABLE_LOGGING = debug
#     _CORRECTION_LOG.clear()

#     if not lines:
#         return []

#     corrected: List[str] = []

#     for idx, raw in enumerate(lines):
#         if not raw or not raw.strip():
#             continue

#         original = raw.rstrip()
#         text = original

#         # --- Stage 1: extreme garbage removal only ---
#         text = _remove_garbled_text(text)

#         # --- Stage 2: dictionary OCR fixes (insurance-safe) ---
#         text = _apply_dictionary_fixes(text)

#         # --- Stage 3: character confusions ---
#         text = _fix_char_confusions(text)

#         # --- Stage 4: spacing (DO NOT REMOVE COLONS) ---
#         text = re.sub(r"[ \t]+", " ", text).strip()

#         # --- Stage 5: line retention decision ---
#         final = _choose_best(original, text)

#         if _is_valid_line(final):
#             corrected.append(final)
#             _log(idx, original, final, "kept")
#         else:
#             _log(idx, original, final, "removed_noise")

#     return corrected


# # ============================================================
# # SAFETY: KEEP BEST VERSION
# # ============================================================

# def _choose_best(original: str, cleaned: str) -> str:
#     """
#     Preserve anchors: if cleaning removed digits, colons,
#     or insurance keywords, keep original.
#     """
#     if ":" in original and ":" not in cleaned:
#         return original

#     if sum(c.isdigit() for c in cleaned) < sum(c.isdigit() for c in original):
#         return original

#     KEYWORDS = (
#         "policy", "insured", "property", "mailing", "address",
#         "mortgage", "premium", "coverage", "effective", "expiration"
#     )

#     ol = original.lower()
#     cl = cleaned.lower()

#     if any(k in ol and k not in cl for k in KEYWORDS):
#         return original

#     return cleaned


# # ============================================================
# # NOISE REMOVAL (EXTREME ONLY)
# # ============================================================

# def _remove_garbled_text(text: str) -> str:
#     if not text:
#         return ""

#     # repeated nonsense tokens (aen aen aen)
#     text = re.sub(r'\b([a-z]{2,3})\s+\1\s+\1\b', '', text, flags=re.I)

#     words = text.split()
#     kept = []

#     for w in words:
#         # ALWAYS preserve anything with digits
#         if any(c.isdigit() for c in w):
#             kept.append(w)
#             continue

#         # ALWAYS preserve short words
#         if len(w) <= 4:
#             kept.append(w)
#             continue

#         # Long nonsense words only
#         if len(w) > 7:
#             vowels = sum(1 for c in w.lower() if c in "aeiou")
#             if vowels / len(w) < 0.10:
#                 _log_word(w)
#                 continue

#         kept.append(w)

#     text = " ".join(kept)

#     # Extreme spam only
#     text = re.sub(r'\b([a-z])\1{5,}\b', '', text, flags=re.I)
#     text = re.sub(r'[|]{3,}', '', text)
#     text = re.sub(r'_{4,}', '', text)

#     return text


# # ============================================================
# # OCR FIXES
# # ============================================================

# def _apply_dictionary_fixes(text: str) -> str:
#     for err, fix in OCR_FIXES.items():
#         text = re.sub(rf"\b{re.escape(err)}\b", fix, text, flags=re.I)

#     INSURANCE_FIXES = {
#         "po1icy": "policy",
#         "pollcy": "policy",
#         "insuranee": "insurance",
#         "covergae": "coverage",
#         "premiurn": "premium",
#         "mortage": "mortgage",
#         "efective": "effective",
#         "expriration": "expiration",
#         "deductib1e": "deductible",
#     }

#     for err, fix in INSURANCE_FIXES.items():
#         text = re.sub(rf"\b{re.escape(err)}\b", fix, text, flags=re.I)

#     return text


# def _fix_char_confusions(text: str) -> str:
#     text = re.sub(r'(?<=\d)[Oo](?=\d)', '0', text)
#     text = re.sub(r'(?<=\d)[Il](?=\d)', '1', text)
#     text = re.sub(r'(?<=[A-Za-z])0(?=[A-Za-z])', 'o', text)
#     text = re.sub(r'(?<=[A-Za-z])1(?=[A-Za-z])', 'l', text)
#     return text


# # ============================================================
# # LINE QUALITY (STAGE-1 SAFE)
# # ============================================================

# def _is_valid_line(text: str) -> bool:
#     if not text or len(text) < 2:
#         return False

#     # ALWAYS keep headers
#     if text.endswith(":") or text.isupper():
#         return True

#     total = len(text)
#     alnum = sum(c.isalnum() for c in text)

#     if alnum < total * 0.15:
#         return False

#     return True


# def _log(idx, original, corrected, action):
#     if _ENABLE_LOGGING:
#         _CORRECTION_LOG.append({
#             "line": idx,
#             "original": original,
#             "corrected": corrected,
#             "action": action,
#         })


# def _log_word(word):
#     if _ENABLE_LOGGING:
#         _CORRECTION_LOG.append({
#             "word": word,
#             "action": "removed_noise",
#         })


# def get_correction_log() -> List[Dict]:
#     return list(_CORRECTION_LOG)


# def clear_correction_log():
#     _CORRECTION_LOG.clear()


"""
OCR Correction Agent – DOMAIN AGNOSTIC MODE
===========================================

Purpose:
- Improve OCR quality BEFORE deterministic extraction
- Preserve line order
- Remove only extreme garbage
- Never infer or extract fields
- No domain assumptions

Safe for ANY document type.
"""

import re
from typing import List, Dict, Optional

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

def correct_lines(
    lines: List[str],
    debug: bool = False,
    custom_dictionary: Optional[Dict[str, str]] = None
) -> List[str]:
    """
    Main OCR correction entrypoint.
    Fully domain-agnostic.
    """

    global _ENABLE_LOGGING
    _ENABLE_LOGGING = debug
    _CORRECTION_LOG.clear()

    if not lines:
        return []

    dictionary = custom_dictionary or OCR_FIXES
    corrected: List[str] = []

    for idx, raw in enumerate(lines):
        if not raw or not raw.strip():
            continue

        original = raw.rstrip()
        text = original

        # Stage 1: extreme garbage removal only
        text = _remove_extreme_noise(text)

        # Stage 2: dictionary fixes (generic only)
        text = _apply_dictionary_fixes(text, dictionary)

        # Stage 3: character confusion corrections
        text = _fix_char_confusions(text)

        # Stage 4: spacing normalization
        text = re.sub(r"[ \t]+", " ", text).strip()

        # Preserve anchors if cleaning caused degradation
        final = _choose_best(original, text)

        if _is_valid_line(final):
            corrected.append(final)
            _log(idx, original, final, "kept")
        else:
            _log(idx, original, final, "removed_noise")

    return corrected


# ============================================================
# SAFETY – PRESERVE STRUCTURAL CONTENT
# ============================================================

def _choose_best(original: str, cleaned: str) -> str:
    """
    Preserve structural content like:
    - colons
    - digits
    - all-caps headers
    """

    if ":" in original and ":" not in cleaned:
        return original

    if sum(c.isdigit() for c in cleaned) < sum(c.isdigit() for c in original):
        return original

    if original.isupper():
        return original

    return cleaned


# ============================================================
# NOISE REMOVAL (EXTREME ONLY)
# ============================================================

def _remove_extreme_noise(text: str) -> str:
    if not text:
        return ""

    # Remove repeated nonsense tokens (e.g., aen aen aen)
    text = re.sub(r'\b([a-z]{2,3})\s+\1\s+\1\b', '', text, flags=re.I)

    words = text.split()
    kept = []

    for w in words:

        # Always preserve tokens with digits
        if any(c.isdigit() for c in w):
            kept.append(w)
            continue

        # Preserve short words
        if len(w) <= 4:
            kept.append(w)
            continue

        # Remove extreme consonant garbage
        if len(w) > 8:
            vowels = sum(1 for c in w.lower() if c in "aeiou")
            if vowels / len(w) < 0.08:
                _log_word(w)
                continue

        kept.append(w)

    text = " ".join(kept)

    # Remove extreme character spam
    text = re.sub(r'\b([a-z])\1{6,}\b', '', text, flags=re.I)
    text = re.sub(r'[|]{4,}', '', text)
    text = re.sub(r'_{5,}', '', text)

    return text


# ============================================================
# DICTIONARY FIXES
# ============================================================

def _apply_dictionary_fixes(text: str, dictionary: Dict[str, str]) -> str:
    for err, fix in dictionary.items():
        pattern = rf"\b{re.escape(err)}\b"
        text = re.sub(pattern, fix, text, flags=re.I)
    return text


# ============================================================
# CHARACTER CONFUSION FIXES
# ============================================================

def _fix_char_confusions(text: str) -> str:
    # Numeric context
    text = re.sub(r'(?<=\d)[Oo](?=\d)', '0', text)
    text = re.sub(r'(?<=\d)[Il](?=\d)', '1', text)

    # Alphabetic context
    text = re.sub(r'(?<=[A-Za-z])0(?=[A-Za-z])', 'o', text)
    text = re.sub(r'(?<=[A-Za-z])1(?=[A-Za-z])', 'l', text)

    return text


# ============================================================
# GENERIC LINE VALIDATION
# ============================================================

def _is_valid_line(text: str) -> bool:
    if not text or len(text) < 2:
        return False

    total = len(text)
    alnum = sum(c.isalnum() for c in text)

    if alnum < total * 0.10:
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
