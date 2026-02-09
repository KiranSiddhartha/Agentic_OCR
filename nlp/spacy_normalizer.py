# import spacy
# import re

# # Load minimal pipeline (fast, deterministic)
# _nlp = spacy.load(
#     "en_core_web_sm",
#     disable=["ner", "lemmatizer", "textcat"]
# )

# def normalize_lines(lines: list[str]) -> list[str]:
#     """
#     Normalize OCR lines using spaCy:
#     - Sentence segmentation
#     - Token normalization
#     - Whitespace cleanup
#     """
#     if not lines:
#         return []

#     text = "\n".join(lines)

#     # Fix common OCR junk before NLP
#     text = re.sub(r"[|•·]", " ", text)
#     text = re.sub(r"\s+", " ", text)

#     doc = _nlp(text)

#     normalized = []
#     for sent in doc.sents:
#         sent_text = " ".join(tok.text for tok in sent if not tok.is_space)
#         sent_text = sent_text.strip()
#         if sent_text:
#             normalized.append(sent_text)

#     return normalized

"""
spaCy Normalizer - TYPE-AWARE VERSION (SESSION 3)
=================================================
Improvements:
1. Document-type-specific normalization
2. Preserves type-specific keywords
3. Better sentence segmentation
4. Smart OCR artifact removal
5. Context-aware cleaning

Uses minimal spaCy pipeline for speed
"""

import spacy
import re
from typing import List, Set, Optional

# Load minimal pipeline (fast, deterministic)
_nlp = None  # Lazy loading

# ============================================================
# TYPE-SPECIFIC PRESERVATION KEYWORDS
# ============================================================

TYPE_PRESERVE_KEYWORDS = {
    "RNW": {
        # Renewal/Declaration specific
        "policy", "declarations", "coverage", "premium", "dwelling",
        "deductible", "limit", "endorsement", "mortgagee",
        "effective", "expiration", "inception",
    },
    "INV": {
        # Invoice specific
        "invoice", "bill", "balance", "due", "amount",
        "payment", "remit", "minimum", "processed", "billing",
    },
    "CAN": {
        # Cancellation specific
        "cancellation", "cancelled", "notice", "terminate",
        "non-payment", "non-renewal", "lapse", "reason",
    },
    "DOI": {
        # Deletion specific
        "deletion", "interest", "removed", "mortgage",
        "terminate", "third party",
    },
    "RNS": {
        # Reinstatement specific
        "reinstatement", "rescission", "reinstated",
        "reactivated", "restore",
    },
    "COI": {
        # Certificate specific
        "certificate", "acord", "holder", "insured",
        "limits", "coverage",
    },
}

# Universal keywords (always preserve)
UNIVERSAL_KEYWORDS = {
    "policy", "number", "insured", "name", "address",
    "date", "premium", "coverage", "carrier", "company",
    "loan", "mortgage", "property",
}


# ============================================================
# LAZY LOADING
# ============================================================

def _get_nlp():
    """Get or initialize spaCy model (lazy loading)"""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(
            "en_core_web_sm",
            disable=["ner", "lemmatizer", "textcat"]
        )
    return _nlp


# ============================================================
# TYPE-AWARE NORMALIZATION
# ============================================================

def normalize_lines(
    lines: List[str],
    document_type: str = "UNK",
    preserve_structure: bool = True
) -> List[str]:
    """
    Normalize OCR lines with type awareness.
    
    Args:
        lines: Raw OCR lines
        document_type: Document type (RNW, INV, CAN, etc.)
        preserve_structure: Whether to preserve line structure
        
    Returns:
        Normalized lines
    """
    if not lines:
        return []
    
    # Get type-specific keywords
    type_keywords = TYPE_PRESERVE_KEYWORDS.get(document_type, set())
    preserve_keywords = UNIVERSAL_KEYWORDS | type_keywords
    
    # Pre-process text
    text = "\n".join(lines) if preserve_structure else " ".join(lines)
    
    # Fix common OCR artifacts BEFORE spaCy
    text = _fix_ocr_artifacts(text, preserve_keywords)
    
    # Run spaCy normalization
    nlp = _get_nlp()
    doc = nlp(text)
    
    # Extract normalized sentences
    normalized = []
    
    if preserve_structure:
        # Preserve line structure as much as possible
        for sent in doc.sents:
            sent_text = _normalize_sentence(sent, preserve_keywords)
            if sent_text:
                normalized.append(sent_text)
    else:
        # Merge into continuous text
        for sent in doc.sents:
            sent_text = _normalize_sentence(sent, preserve_keywords)
            if sent_text:
                normalized.append(sent_text)
    
    return normalized


# ============================================================
# OCR ARTIFACT FIXING
# ============================================================

def _fix_ocr_artifacts(text: str, preserve_keywords: Set[str]) -> str:
    """
    Fix common OCR artifacts before spaCy processing.
    
    Args:
        text: Input text
        preserve_keywords: Keywords to preserve
        
    Returns:
        Cleaned text
    """
    # Fix common OCR character confusions
    
    # Remove excessive symbols (but keep important ones)
    text = re.sub(r"[|•·]{2,}", " ", text)  # Multiple bullets/pipes
    text = re.sub(r"_{3,}", " ", text)      # Multiple underscores
    
    # Fix spacing around punctuation (but preserve colons for labels)
    text = re.sub(r"\s+([,.])", r"\1", text)  # Remove space before comma/period
    
    # Normalize whitespace (but preserve newlines for structure)
    text = re.sub(r"[ \t]+", " ", text)
    
    # Fix broken words (common OCR issue)
    # Example: "insur ance" -> "insurance"
    text = _fix_broken_words(text, preserve_keywords)
    
    return text


def _fix_broken_words(text: str, preserve_keywords: Set[str]) -> str:
    """
    Fix words broken by OCR (e.g., "insur ance" -> "insurance").
    
    Args:
        text: Input text
        preserve_keywords: Keywords to check against
        
    Returns:
        Text with fixed words
    """
    # Check for broken versions of keywords
    for keyword in preserve_keywords:
        if " " in keyword:
            continue  # Skip multi-word keywords
        
        # Look for broken versions (e.g., "insur ance" for "insurance")
        for split_pos in range(3, len(keyword) - 2):
            broken = keyword[:split_pos] + " " + keyword[split_pos:]
            if broken in text.lower():
                # Replace with correct version
                text = re.sub(
                    re.escape(broken),
                    keyword,
                    text,
                    flags=re.IGNORECASE
                )
    
    return text


# ============================================================
# SENTENCE NORMALIZATION
# ============================================================

def _normalize_sentence(sent, preserve_keywords: Set[str]) -> str:
    """
    Normalize a single sentence.
    
    Args:
        sent: spaCy Span object
        preserve_keywords: Keywords to preserve
        
    Returns:
        Normalized sentence text
    """
    # Extract tokens
    tokens = []
    for tok in sent:
        # Skip pure whitespace
        if tok.is_space:
            continue
        
        # Get token text
        token_text = tok.text
        
        # Check if token contains a preserved keyword
        token_lower = token_text.lower()
        is_keyword = any(kw in token_lower for kw in preserve_keywords)
        
        if is_keyword:
            # Preserve exactly as is
            tokens.append(token_text)
        else:
            # Apply normalization
            # Remove excessive punctuation
            if token_text in (".", ",", ";") and tokens and tokens[-1] in (".", ",", ";"):
                continue  # Skip duplicate punctuation
            
            tokens.append(token_text)
    
    # Join tokens
    sent_text = " ".join(tokens)
    
    # Final cleanup
    sent_text = sent_text.strip()
    
    # Remove if too short or pure punctuation
    if len(sent_text) < 2 or all(c in ".,;:-_|/" for c in sent_text):
        return ""
    
    return sent_text


# ============================================================
# SPECIALIZED NORMALIZERS
# ============================================================

def normalize_for_invoice(lines: List[str]) -> List[str]:
    """
    Specialized normalization for invoices.
    Preserves dollar amounts and dates.
    
    Args:
        lines: Raw lines
        
    Returns:
        Normalized lines
    """
    return normalize_lines(lines, document_type="INV", preserve_structure=True)


def normalize_for_cancellation(lines: List[str]) -> List[str]:
    """
    Specialized normalization for cancellations.
    Preserves dates and reason keywords.
    
    Args:
        lines: Raw lines
        
    Returns:
        Normalized lines
    """
    return normalize_lines(lines, document_type="CAN", preserve_structure=True)


def normalize_for_renewal(lines: List[str]) -> List[str]:
    """
    Specialized normalization for renewals/declarations.
    Preserves coverage and premium information.
    
    Args:
        lines: Raw lines
        
    Returns:
        Normalized lines
    """
    return normalize_lines(lines, document_type="RNW", preserve_structure=True)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_field_value(value: str, field_name: str = None) -> str:
    """
    Clean extracted field value.
    
    Args:
        value: Raw field value
        field_name: Name of field (for context)
        
    Returns:
        Cleaned value
    """
    if not value:
        return ""
    
    # Normalize whitespace
    value = re.sub(r"\s+", " ", value)
    
    # Remove trailing punctuation (but keep internal)
    value = value.strip(" .,;:")
    
    # Field-specific cleaning
    if field_name:
        if "date" in field_name.lower():
            # Normalize date format
            value = re.sub(r"\s*/\s*", "/", value)  # Fix "10 / 15 / 2024"
        
        elif "number" in field_name.lower():
            # Remove spaces from numbers
            value = value.replace(" ", "")
        
        elif "address" in field_name.lower():
            # Normalize address spacing
            value = re.sub(r"\s+,", ",", value)
            value = re.sub(r",\s*", ", ", value)
    
    return value.strip()


def remove_noise_lines(lines: List[str], preserve_keywords: Set[str] = None) -> List[str]:
    """
    Remove obvious noise lines.
    
    Args:
        lines: Input lines
        preserve_keywords: Keywords that indicate important lines
        
    Returns:
        Filtered lines
    """
    if preserve_keywords is None:
        preserve_keywords = UNIVERSAL_KEYWORDS
    
    filtered = []
    
    for line in lines:
        # Skip empty
        if not line or not line.strip():
            continue
        
        line_clean = line.strip()
        line_lower = line_clean.lower()
        
        # Always keep lines with keywords
        if any(kw in line_lower for kw in preserve_keywords):
            filtered.append(line_clean)
            continue
        
        # Skip obvious noise
        # Pure punctuation
        if all(c in ".,;:-_|/() " for c in line_clean):
            continue
        
        # Too short
        if len(line_clean) < 3:
            continue
        
        # Excessive non-alphanumeric
        alnum = sum(c.isalnum() for c in line_clean)
        if alnum < len(line_clean) * 0.3:
            continue
        
        filtered.append(line_clean)
    
    return filtered


# ============================================================
# DIAGNOSTICS
# ============================================================

def get_normalization_stats(lines: List[str], document_type: str = "UNK") -> dict:
    """
    Get statistics about normalization.
    
    Args:
        lines: Input lines
        document_type: Document type
        
    Returns:
        Dictionary with stats
    """
    if not lines:
        return {
            "original_lines": 0,
            "normalized_lines": 0,
            "removed_lines": 0,
        }
    
    normalized = normalize_lines(lines, document_type)
    
    return {
        "original_lines": len(lines),
        "normalized_lines": len(normalized),
        "removed_lines": len(lines) - len(normalized),
        "document_type": document_type,
        "avg_line_length_before": sum(len(l) for l in lines) / len(lines) if lines else 0,
        "avg_line_length_after": sum(len(l) for l in normalized) / len(normalized) if normalized else 0,
    }


# ============================================================
# BACKWARD COMPATIBILITY (without document_type)
# ============================================================

def normalize_lines_legacy(lines: List[str]) -> List[str]:
    """Legacy function for backward compatibility"""
    return normalize_lines(lines, document_type="UNK", preserve_structure=True)