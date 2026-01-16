# # agents/stage2_semantic_agent.py
# # Stage 2: Semantic Extraction using SpaCy NER
# # Handles unlabeled entities that regex can't catch

# import re
# from typing import List, Dict, Optional

# # Try to import spacy, fall back to rule-based if unavailable
# try:
#     import spacy
#     SPACY_AVAILABLE = True
#     _nlp = None
# except ImportError:
#     SPACY_AVAILABLE = False
#     _nlp = None


# # ============================================================
# # SECTION CONTROL (ADDED – NON-DESTRUCTIVE)
# # ============================================================

# BLOCKED_SECTIONS = {
#     "forms and endorsements",
#     "additional forms",
#     "endorsement",
#     "form number",
#     "other interests",
#     "mortgagee",
#     "other interest",
#     "additional exposures",
# }

# ADDRESS_ALLOWED_SECTIONS = {
#     "named insured",
#     "named insured and mailing address",
#     "location of insured property",
# }

# CURRENT_SECTION = None


# def _update_section_state(line: str):
#     """Track current document section"""
#     global CURRENT_SECTION
#     l = line.lower()

#     for s in BLOCKED_SECTIONS:
#         if s in l:
#             CURRENT_SECTION = s
#             return

#     for s in ADDRESS_ALLOWED_SECTIONS:
#         if s in l:
#             CURRENT_SECTION = s
#             return


# def _is_blocked_context() -> bool:
#     return CURRENT_SECTION in BLOCKED_SECTIONS


# # ============================================================
# # SPACY LOADING
# # ============================================================

# def _load_spacy_model():
#     """Lazy load spacy model"""
#     global _nlp

#     if not SPACY_AVAILABLE:
#         return None

#     if _nlp is None:
#         try:
#             _nlp = spacy.load("en_core_web_sm")
#             print("[Stage2] SpaCy model loaded")
#         except OSError:
#             print("[Stage2] SpaCy model not found, using rule-based fallback")
#             return None

#     return _nlp


# # ============================================================
# # MAIN ENTRY
# # ============================================================

# def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
#     """
#     Stage 2: Extract fields using Named Entity Recognition
#     """

#     if not missing_fields:
#         return {}

#     # Track section state line-by-line
#     for line in lines:
#         _update_section_state(line)

#     nlp = _load_spacy_model()

#     if nlp is not None:
#         return _extract_with_spacy(lines, missing_fields, nlp)
#     else:
#         return _extract_with_rules(lines, missing_fields)


# # ============================================================
# # SPACY-BASED EXTRACTION
# # ============================================================

# def _extract_with_spacy(lines: List[str], missing_fields: List[str], nlp) -> Dict[str, Dict]:
#     text = "\n".join(lines)
#     doc = nlp(text)

#     extracted = {}

#     entity_map = {
#         "PERSON": "insured_name",
#         "ORG": "insured_name",
#         "GPE": "mailing_address",
#         "LOC": "mailing_address",
#         "DATE": ["effective_date", "expiration_date"],
#         "MONEY": "total_premium",
#     }

#     entities_by_type = {}
#     for ent in doc.ents:
#         entities_by_type.setdefault(ent.label_, []).append(ent)

#     # ---------------- INSURED NAME ----------------
#     if "insured_name" in missing_fields:
#         person_entities = entities_by_type.get("PERSON", []) + entities_by_type.get("ORG", [])
#         for ent in person_entities:
#             if _is_valid_name_entity(ent.text):
#                 extracted["insured_name"] = {
#                     "value": ent.text.strip(),
#                     "confidence": 0.82,
#                     "source": "semantic_ner",
#                     "ner_label": ent.label_,
#                 }
#                 break

#     # ---------------- ADDRESS (STRICT) ----------------
#     if not _is_blocked_context() and (
#         "mailing_address" in missing_fields or "property_address" in missing_fields
#     ):
#         loc_entities = entities_by_type.get("GPE", []) + entities_by_type.get("LOC", [])

#         address = _build_address_from_entities(loc_entities, doc)
#         if address and _is_valid_address(address):
#             field_name = (
#                 "mailing_address"
#                 if "mailing_address" in missing_fields
#                 else "property_address"
#             )
#             extracted[field_name] = {
#                 "value": address,
#                 "confidence": 0.78,
#                 "source": "semantic_ner",
#                 "ner_label": "LOC/GPE",
#             }

#     # ---------------- DATES ----------------
#     date_entities = entities_by_type.get("DATE", [])
#     if date_entities:
#         dates = []
#         for ent in date_entities:
#             norm = _normalize_date(ent.text)
#             if norm:
#                 dates.append(norm)

#         if dates and "effective_date" in missing_fields:
#             extracted["effective_date"] = {
#                 "value": dates[0],
#                 "confidence": 0.75,
#                 "source": "semantic_ner",
#                 "ner_label": "DATE",
#             }

#         if len(dates) > 1 and "expiration_date" in missing_fields:
#             extracted["expiration_date"] = {
#                 "value": dates[1],
#                 "confidence": 0.75,
#                 "source": "semantic_ner",
#                 "ner_label": "DATE",
#             }

#     # ---------------- MONEY ----------------
#     if "total_premium" in missing_fields:
#         money_entities = entities_by_type.get("MONEY", [])
#         for ent in money_entities:
#             if _is_valid_currency(ent.text):
#                 extracted["total_premium"] = {
#                     "value": ent.text,
#                     "confidence": 0.80,
#                     "source": "semantic_ner",
#                     "ner_label": "MONEY",
#                 }
#                 break

#     return extracted


# # ============================================================
# # RULE-BASED FALLBACK
# # ============================================================

# def _extract_with_rules(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
#     text = "\n".join(lines)
#     extracted = {}

#     if "insured_name" in missing_fields:
#         name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
#         for match in re.findall(name_pattern, text):
#             if _is_valid_name_entity(match):
#                 extracted["insured_name"] = {
#                     "value": match,
#                     "confidence": 0.70,
#                     "source": "semantic_rules",
#                     "ner_label": "PERSON",
#                 }
#                 break

#     if not _is_blocked_context() and (
#         "mailing_address" in missing_fields or "property_address" in missing_fields
#     ):
#         address_pattern = r'\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln)'
#         matches = re.findall(address_pattern, text, re.I)
#         if matches and _is_valid_address(matches[0]):
#             field = "mailing_address" if "mailing_address" in missing_fields else "property_address"
#             extracted[field] = {
#                 "value": matches[0],
#                 "confidence": 0.68,
#                 "source": "semantic_rules",
#                 "ner_label": "ADDRESS",
#             }

#     return extracted


# # ============================================================
# # VALIDATION HELPERS (EXPANDED)
# # ============================================================

# def _is_valid_name_entity(name: str) -> bool:
#     if not name or len(name.strip()) < 4:
#         return False
#     if any(c.isdigit() for c in name):
#         return False
#     if name.lower() in {"and", "or", "the"}:
#         return False
#     if len(name.split()) < 2:
#         return False
#     return True


# def _is_valid_address(addr: str) -> bool:
#     if not addr:
#         return False
#     if re.search(r'HS\s?\d{2}', addr):
#         return False
#     if re.search(r'endorsement|form|policy', addr.lower()):
#         return False
#     return bool(re.search(r'\d+ .* (st|ave|rd|blvd|ln|dr)', addr.lower()))


# def _is_valid_currency(val: str) -> bool:
#     return bool(re.search(r'\$\s*\d|,\d{3}', val))


# def _build_address_from_entities(loc_entities, doc) -> Optional[str]:
#     if not loc_entities:
#         return None

#     parts = []
#     for ent in loc_entities[:3]:
#         context = doc[max(0, ent.start - 10): ent.end + 5].text
#         street_match = re.search(
#             r'\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln)',
#             context,
#             re.I,
#         )
#         if street_match:
#             parts.append(street_match.group(0))
#         parts.append(ent.text)

#     return ", ".join(dict.fromkeys(parts))


# def _normalize_date(date_text: str) -> Optional[str]:
#     if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_text):
#         return date_text

#     patterns = [
#         (r'(\d{1,2})-(\d{1,2})-(\d{4})', r'\1/\2/\3'),
#         (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\2/\3/\1'),
#     ]

#     for p, r in patterns:
#         if re.search(p, date_text):
#             return re.sub(p, r, date_text)

#     return None

 
"""
Stage 2 – Semantic Gap Filler (NON-AUTHORITATIVE)
================================================

Purpose:
- Fill ONLY fields missing after Stage 1
- Semantic assistance only (NER / heuristics)
- NEVER override Stage-1 output
- Penalized confidence
- Stateless

Stage 1 owns truth.
Stage 2 proposes candidates only.
"""

from typing import List, Dict
import re

# ============================================================
# OPTIONAL SPACY SUPPORT (LAZY)
# ============================================================

try:
    import spacy
    _NLP = None
    SPACY_AVAILABLE = True
except Exception:
    SPACY_AVAILABLE = False
    _NLP = None


# ============================================================
# HARD CONSTRAINT VALIDATORS (REUSED LOGIC)
# ============================================================

def _valid_name(text: str) -> bool:
    if not text:
        return False
    if any(c.isdigit() for c in text):
        return False
    words = text.split()
    return 2 <= len(words) <= 6


def _valid_address(text: str) -> bool:
    if not text:
        return False
    if not any(c.isdigit() for c in text):
        return False
    if len(text) < 10:
        return False
    return True


def _valid_currency(text: str) -> bool:
    return bool(re.search(r"\$\s?\d", text))


def _valid_date(text: str) -> bool:
    return bool(
        re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
        or re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", text)
    )


# ============================================================
# PUBLIC ENTRY POINT (USED BY ORCHESTRATOR)
# ============================================================

def extract_with_ner(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Extract semantic candidates for MISSING fields ONLY.
    """
    if not lines or not missing_fields:
        return {}

    results: Dict[str, Dict] = {}

    nlp = _load_spacy() if SPACY_AVAILABLE else None

    if nlp:
        results.update(_extract_with_spacy(lines, missing_fields, nlp))
    else:
        results.update(_extract_with_rules(lines, missing_fields))

    return results


# ============================================================
# SPACY-BASED EXTRACTION
# ============================================================

def _load_spacy():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except Exception:
            return None
    return _NLP


def _extract_with_spacy(
    lines: List[str],
    missing_fields: List[str],
    nlp,
) -> Dict[str, Dict]:

    text = "\n".join(lines)
    doc = nlp(text)
    out: Dict[str, Dict] = {}

    for ent in doc.ents:
        # -------- INSURED NAME --------
        if ent.label_ in {"PERSON", "ORG"} and "insured_name" in missing_fields:
            if _valid_name(ent.text):
                out["insured_name"] = _candidate(ent.text, "semantic_ner", 0.75)
                break

        # -------- ADDRESS --------
        if ent.label_ in {"GPE", "LOC"}:
            if "mailing_address" in missing_fields or "property_address" in missing_fields:
                if _valid_address(ent.text):
                    field = (
                        "mailing_address"
                        if "mailing_address" in missing_fields
                        else "property_address"
                    )
                    out[field] = _candidate(ent.text, "semantic_ner", 0.72)
                    break

        # -------- DATES --------
        if ent.label_ == "DATE":
            if "effective_date" in missing_fields and _valid_date(ent.text):
                out["effective_date"] = _candidate(ent.text, "semantic_ner", 0.70)
            elif "expiration_date" in missing_fields and _valid_date(ent.text):
                out["expiration_date"] = _candidate(ent.text, "semantic_ner", 0.70)

        # -------- MONEY --------
        if ent.label_ == "MONEY" and "total_premium" in missing_fields:
            if _valid_currency(ent.text):
                out["total_premium"] = _candidate(ent.text, "semantic_ner", 0.75)

    return out


# ============================================================
# RULE-BASED FALLBACK (NO NER)
# ============================================================

def _extract_with_rules(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:

    out: Dict[str, Dict] = {}

    for line in lines:
        # -------- INSURED NAME --------
        if "insured_name" in missing_fields and _valid_name(line):
            out["insured_name"] = _candidate(line, "semantic_rules", 0.70)
            continue

        # -------- ADDRESS --------
        if (
            ("mailing_address" in missing_fields or "property_address" in missing_fields)
            and _valid_address(line)
        ):
            field = (
                "mailing_address"
                if "mailing_address" in missing_fields
                else "property_address"
            )
            out[field] = _candidate(line, "semantic_rules", 0.68)
            continue

        # -------- PREMIUM --------
        if "total_premium" in missing_fields and _valid_currency(line):
            out["total_premium"] = _candidate(line, "semantic_rules", 0.72)

    return out


# ============================================================
# CANDIDATE BUILDER (CONFIDENCE CAPPED)
# ============================================================

def _candidate(value: str, source: str, confidence: float) -> Dict:
    """
    Build a semantic candidate with enforced confidence ceiling.
    """
    return {
        "value": value.strip(),
        "confidence": min(confidence, 0.80),
        "source": source,
    }
