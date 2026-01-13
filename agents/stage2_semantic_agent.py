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

 
import re
from typing import Dict, List, Optional

#  """
# Stage 2 – Semantic Agent
# Purpose: Fill ONLY missing fields with low-confidence semantic hints.

# Rules:
# - Never override existing fields
# - Never act as authority
# - Never normalize values
# - Validation agent decides final acceptance
# """

# ============================================================
# ALLOWED FIELDS (STRICT)
# ============================================================

ALLOWED_FIELDS = {
    "insured_name",
    "mailing_address",
    "property_address",
    "mortgage",
    "loan_number",
    "effective_date",
    "expiration_date",
}

# ============================================================
# OPTIONAL SPACY SUPPORT
# ============================================================

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    _NLP = None
    SPACY_AVAILABLE = False


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def semantic_fill_missing_fields(
    lines: List[str],
    existing_fields: Dict[str, Dict],
    sections: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Dict]:
    """
    Fill missing fields using semantic heuristics.
    Never overrides existing_fields.
    """

    results: Dict[str, Dict] = {}

    missing = ALLOWED_FIELDS - set(existing_fields.keys())
    if not missing:
        return results

    # Prefer section-scoped lines when available
    insured_lines = (sections or {}).get("insured", lines)
    property_lines = (sections or {}).get("property", lines)
    mortgage_lines = (sections or {}).get("mortgage", lines)

    if "insured_name" in missing:
        val = _semantic_insured_name(insured_lines)
        if val:
            results["insured_name"] = val

    if "mailing_address" in missing:
        val = _semantic_address(insured_lines)
        if val:
            results["mailing_address"] = val

    if "property_address" in missing:
        val = _semantic_address(property_lines)
        if val:
            results["property_address"] = val

    if "mortgage" in missing:
        val = _semantic_mortgage(mortgage_lines)
        if val:
            results["mortgage"] = val

    if "loan_number" in missing:
        val = _semantic_loan_number(mortgage_lines)
        if val:
            results["loan_number"] = val

    if "effective_date" in missing:
        val = _semantic_date(lines, keyword="effective")
        if val:
            results["effective_date"] = val

    if "expiration_date" in missing:
        val = _semantic_date(lines, keyword="expiration")
        if val:
            results["expiration_date"] = val

    return results


# ============================================================
# SEMANTIC HELPERS (LOW CONFIDENCE)
# ============================================================

def _semantic_insured_name(lines: List[str]) -> Optional[Dict]:
    for l in lines:
        if ":" in l or l.endswith("."):
            continue
        if any(char.isdigit() for char in l):
            continue
        words = l.strip().split()
        if 2 <= len(words) <= 6:
            return {"value": l.strip(), "confidence": 0.72}
    return None


def _semantic_address(lines: List[str]) -> Optional[Dict]:
    for l in lines:
        ll = l.lower()
        if "po box" in ll:
            return {"value": l.strip(), "confidence": 0.70}
        if re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", l):
            return {"value": l.strip(), "confidence": 0.72}
    return None


def _semantic_mortgage(lines: List[str]) -> Optional[Dict]:
    for l in lines:
        ll = l.lower()
        if any(k in ll for k in ["mortgage", "lender", "bank", "isaoa", "atima"]):
            if len(l.split()) >= 2 and not l.endswith("."):
                return {"value": l.strip(), "confidence": 0.70}
    return None


def _semantic_loan_number(lines: List[str]) -> Optional[Dict]:
    for l in lines:
        m = re.search(r"\b\d{5,}\b", l)
        if m:
            return {"value": m.group(0), "confidence": 0.68}
    return None


def _semantic_date(lines: List[str], keyword: str) -> Optional[Dict]:
    for l in lines:
        ll = l.lower()
        if keyword in ll and "date" in ll:
            matches = re.findall(
                r"\b(?:\d{1,2}/\d{1,2}/\d{4}|[A-Z][a-z]+ \d{1,2}, \d{4})\b",
                l,
            )
            if matches:
                return {"value": matches[0], "confidence": 0.70}
    return None
