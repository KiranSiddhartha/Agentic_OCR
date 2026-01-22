# """
# Stage 4 – Validation & Arbitration Agent (ENHANCED)
# =======================================================
# Comprehensive validation with strict filtering
# ENHANCED: Better phone number blocking for policy numbers
# """

# import re
# from datetime import datetime
# from typing import Dict, Tuple


# # ============================================================
# # CONFIDENCE FLOORS
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier_name": 0.85,
#     "policy_number": 0.85,
#     "loan_number": 0.85,
#     "insured_name": 0.80,
#     "property_address": 0.80,
#     "mailing_address": 0.75,
#     "mortgage_company": 0.80,
#     "total_premium": 0.75,
#     "deductible": 0.75,
#     "effective_date": 0.80,
#     "expiration_date": 0.80,
#     "agent_phone": 0.80,
#     "agent_name": 0.75,
# }

# DEFAULT_FLOOR = 0.70


# # ============================================================
# # BLOCK LISTS
# # ============================================================

# SECTION_TITLES = {
#     "summary",
#     "home protection",
#     "coverage",
#     "coverages",
#     "limits",
#     "policy mortgage declarations summary",
#     "declarations",
#     "declarations summary",
#     "mortgage/other interested parties",
#     "applicable deductible(s)",
#     "premiums",
#     "forms and endorsements",
#     "policy period",
#     "policyholder since",
#     "billing information",
#     "payment plan",
#     "discount information",
#     "for your information",
#     "important notice",
#     "thank you",
#     "office use space",
#     "message(s)",
#     "mortgagee(s)",
# }

# JUNK_VALUES = {
#     "type",
#     "interest",
#     "policy",
#     "coverage",
#     "summary",
#     "n/a",
#     "none",
#     "see attached",
#     "continued",
#     "page",
# }

# PREFIX_STRIP = [
#     "coverage detail for",
#     "policy effective date is",
#     "effective date is",
#     "your policy effective date is",
#     "your policy effective date:",
#     "location:",
#     "address:",
#     "name:",
#     "insured:",
#     "named insured:",
#     "property:",
#     "mailing:",
# ]


# # ============================================================
# # HELPERS
# # ============================================================

# def _is_section_header_value(value: str) -> bool:
#     if not value:
#         return False

#     l = value.lower().strip()

#     if l in SECTION_TITLES:
#         return True

#     for title in SECTION_TITLES:
#         if l.startswith(title) or title in l:
#             return True

#     if l.endswith(":") and len(l.split()) <= 5:
#         return True
    
#     if value.isupper() and len(value.split()) >= 3:
#         return True

#     return False


# def _strip_prefixes(value: str) -> str:
#     v = value.strip()
#     vl = v.lower()
    
#     for p in PREFIX_STRIP:
#         if vl.startswith(p):
#             v = v[len(p):].strip(" :.-")
    
#     return v


# def _normalize_whitespace(value: str) -> str:
#     return re.sub(r'\s+', ' ', value).strip()


# def _normalize_address(value: str) -> str:
#     v = _normalize_whitespace(value)
    
#     replacements = {
#         r'\bSt\b': 'Street',
#         r'\bAve\b': 'Avenue',
#         r'\bRd\b': 'Road',
#         r'\bBlvd\b': 'Boulevard',
#         r'\bDr\b': 'Drive',
#         r'\bLn\b': 'Lane',
#         r'\bCt\b': 'Court',
#         r'\bCir\b': 'Circle',
#     }
    
#     for pattern, replacement in replacements.items():
#         v = re.sub(pattern, replacement, v, flags=re.I)
    
#     return v


# def _normalize_phone(value: str) -> str:
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
#     elif len(digits) == 11 and digits[0] == '1':
#         return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
#     return value


# # ============================================================
# # VALIDATORS (ENHANCED)
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
# ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')


# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(value)
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     if len(v) < 3:
#         return False, v, 0.0
    
#     return True, v.upper(), 0.95


# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     """Validate policy number with STRICT filtering - ENHANCED"""
#     v = value.strip()

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     # CRITICAL: Block phone numbers (most common false positive)
#     if PHONE_RE.fullmatch(v.replace(" ", "")):
#         return False, v, 0.0
    
#     # Block partial phone numbers (last 7 digits)
#     if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
#         return False, v, 0.0
    
#     # NEW: Block 10-digit sequences (likely phone)
#     digits_only = ''.join(c for c in v if c.isdigit())
#     if len(digits_only) == 10:
#         return False, v, 0.0
    
#     # Block short numeric sequences (barcodes, reference codes)
#     if re.fullmatch(r"\d{1,7}", v):
#         return False, v, 0.0

#     # Can't be just ZIP
#     if ZIP_RE.fullmatch(v):
#         return False, v, 0.0
    
#     # Block date-like patterns
#     if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', v, re.I):
#         return False, v, 0.0
#     if re.match(r'^[A-Za-z]+\d{1,2},?\d{4}$', v):
#         return False, v, 0.0

#     digits = sum(c.isdigit() for c in v)
#     letters = sum(c.isalpha() for c in v)
    
#     # Must have substantial digits
#     if digits < 5:
#         return False, v, 0.0
    
#     # Can't be mostly letters with few digits
#     if letters > digits:
#         return False, v, 0.0
    
#     # Length check
#     if not (7 <= len(v) <= 35):
#         return False, v, 0.0

#     return True, v, 0.95


# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     v = value.strip()
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     digits = sum(c.isdigit() for c in v)
#     if digits < 6:
#         return False, v, 0.0
    
#     return True, v, 0.95


# def validate_name(value: str) -> Tuple[bool, str, float]:
#     """Validate person/company name with comprehensive filtering"""
#     v = _normalize_whitespace(value)

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if ":" in v:
#         return False, v, 0.0

#     # Block structural keywords - COMPREHENSIVE
#     bad_keywords = (
#         "named insured",
#         "insured name",
#         "mailing address",
#         "property address",
#         "policy type",
#         "coverage",
#         "deductible",
#         "premium",
#         "billing",
#         "mortgagee",
#         "mortgage",
#         "lender",
#         "loan",
#         "copy",
#         "page",
#         "interest",
#         "section",
#         "premises",
#         "office use",
#         "office use space",
#         "message",
#         "declarations",
#         "effective date",
#         "expiration date",
#     )
#     if any(w in v.lower() for w in bad_keywords):
#         return False, v, 0.0

#     # Allow digits if has entity suffix
#     has_entity = any(w in v.lower() for w in ["llc", "inc", "corp", "company", "trust", "ltd"])
#     if any(c.isdigit() for c in v) and not has_entity:
#         return False, v, 0.0

#     words = [w for w in v.split() if w]
    
#     if has_entity:
#         if not (2 <= len(words) <= 10):
#             return False, v, 0.0
#     else:
#         if not (2 <= len(words) <= 6):
#             return False, v, 0.0

#     return True, v, 0.95


# def validate_address(value: str) -> Tuple[bool, str, float]:
#     """Validate address with strict filtering"""
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     # Block if contains period/date keywords
#     v_lower = v.lower()
#     if any(kw in v_lower for kw in [
#         "policy period", "beginning", "through", "standard time",
#         "coverage", "summary", "declarations", "effective date",
#         "office use", "message", "mortgagee"
#     ]):
#         return False, v, 0.0

#     # PO Box
#     if re.search(r'p\.?o\.?\s*box', v, re.I):
#         return True, _normalize_address(v), 0.95

#     # Street address - MUST have street number
#     street_pattern = re.compile(
#         r'\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court|cir|circle)\b',
#         re.I
#     )
#     if street_pattern.search(v):
#         return True, _normalize_address(v), 0.93

#     # Has state + ZIP
#     if re.search(r'\b[A-Z]{2}\s*\d{5}', v):
#         return True, _normalize_address(v), 0.92

#     # Has number and reasonable length
#     has_number = bool(re.search(r'\d+', v))
#     word_count = len(v.split())
#     if has_number and word_count >= 3:
#         return True, _normalize_address(v), 0.85

#     return False, v, 0.0


# def validate_date(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     date_formats = [
#         "%B %d, %Y",
#         "%b %d, %Y",
#         "%m/%d/%Y",
#         "%m-%d-%Y",
#         "%m/%d/%y",
#         "%Y-%m-%d",
#     ]

#     for fmt in date_formats:
#         try:
#             dt = datetime.strptime(v, fmt)
#             if 1990 <= dt.year <= 2050:
#                 return True, v, 0.95
#         except ValueError:
#             continue

#     return False, v, 0.0


# def validate_money(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     try:
#         clean = value.replace('$', '').replace(',', '').strip()
#         amt = float(clean)
        
#         if 10 <= amt <= 1_000_000:
#             formatted = f"${amt:,.2f}".replace('.00', '')
#             return True, formatted, 0.92
#     except Exception:
#         pass
    
#     return False, value, 0.0


# def validate_phone(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         normalized = _normalize_phone(value)
#         return True, normalized, 0.95
    
#     return False, value, 0.0


# # ============================================================
# # CROSS-VALIDATION
# # ============================================================

# def _cross_validate(validated: Dict) -> Dict:
#     if ("mailing_address" in validated and 
#         "property_address" in validated):
        
#         mailing = validated["mailing_address"]["value"]
#         property_addr = validated["property_address"]["value"]
        
#         mailing_norm = mailing.lower().replace(',', '').replace('.', '')
#         property_norm = property_addr.lower().replace(',', '').replace('.', '')
        
#         if mailing_norm == property_norm:
#             validated["mailing_address"]["confidence"] *= 1.1
#             validated["property_address"]["confidence"] *= 1.1
#             validated["mailing_address"]["note"] = "Same as property address"
    
#     if ("effective_date" in validated and 
#         "expiration_date" in validated):
        
#         try:
#             eff = validated["effective_date"]["value"]
#             exp = validated["expiration_date"]["value"]
            
#             for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y"]:
#                 try:
#                     eff_dt = datetime.strptime(eff, fmt)
#                     exp_dt = datetime.strptime(exp, fmt)
                    
#                     if eff_dt < exp_dt:
#                         validated["effective_date"]["confidence"] *= 1.05
#                         validated["expiration_date"]["confidence"] *= 1.05
#                     break
#                 except:
#                     continue
#         except:
#             pass
    
#     return validated


# # ============================================================
# # MAIN VALIDATION
# # ============================================================

# def validate_and_arbitrate(
#     merged_fields: Dict,
#     ocr_confidence: float,
#     stage_breakdown: Dict,
# ) -> Tuple[Dict, float]:
#     validated = {}
#     scores = []

#     validators = {
#         "carrier_name": validate_carrier,
#         "policy_number": validate_policy_number,
#         "loan_number": validate_loan_number,
#         "insured_name": validate_name,
#         "agent_name": validate_name,
#         "mortgage_company": validate_name,
#         "property_address": validate_address,
#         "mailing_address": validate_address,
#         "effective_date": validate_date,
#         "expiration_date": validate_date,
#         "total_premium": validate_money,
#         "deductible": validate_money,
#         "agent_phone": validate_phone,
#     }

#     for field, data in merged_fields.items():
#         if not isinstance(data, dict):
#             continue

#         value = data.get("value")
#         confidence = data.get("confidence", 0.0)

#         floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor or not value:
#             continue

#         if field in validators:
#             ok, norm_value, score = validators[field](value)
#             if not ok:
#                 continue
            
#             data["value"] = norm_value
#             data["validation_score"] = score
#             scores.append(score)
#         else:
#             scores.append(0.80)

#         validated[field] = data

#     validated = _cross_validate(validated)

#     if scores:
#         avg_validation_score = sum(scores) / len(scores)
#         final_confidence = round(
#             avg_validation_score * 0.6 + ocr_confidence * 0.4,
#             3,
#         )
#     else:
#         final_confidence = round(ocr_confidence * 0.4, 3)

#     return validated, final_confidence


# def validate_output(structured: Dict, confidence: float):
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})




# """
# Stage 4 – Validation & Arbitration Agent (FIXED VERSION)
# =========================================================
# FIXES APPLIED:
# 1. Policy Number - Relaxed digit requirements, better phone blocking
# 2. Insured Name - Allow single uppercase word, relaxed word count
# 3. Address - Better PO Box support, relaxed validation
# 4. Lowered confidence floors to not reject valid extractions

# Key Changes:
# - validate_policy_number: Allow 8+ digit pure numeric, fix phone blocking
# - validate_name: Allow names with 1+ capitalized words, longer company names
# - validate_address: Support PO Box, city/state/zip patterns
# - Reduced confidence floors to prevent over-filtering
# """

# import re
# from datetime import datetime
# from typing import Dict, Tuple


# # ============================================================
# # CONFIDENCE FLOORS (RELAXED)
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier_name": 0.75,      # Was 0.85
#     "policy_number": 0.75,     # Was 0.85
#     "loan_number": 0.75,       # Was 0.85
#     "insured_name": 0.70,      # Was 0.80
#     "property_address": 0.70,  # Was 0.80
#     "mailing_address": 0.65,   # Was 0.75
#     "mortgage_company": 0.70,  # Was 0.80
#     "total_premium": 0.70,     # Was 0.75
#     "deductible": 0.70,        # Was 0.75
#     "effective_date": 0.70,    # Was 0.80
#     "expiration_date": 0.70,   # Was 0.80
#     "agent_phone": 0.70,       # Was 0.80
#     "agent_name": 0.65,        # Was 0.75
# }

# DEFAULT_FLOOR = 0.60  # Was 0.70


# # ============================================================
# # BLOCK LISTS
# # ============================================================

# SECTION_TITLES = {
#     "summary", "home protection", "coverage", "coverages", "limits",
#     "policy mortgage declarations summary", "declarations",
#     "declarations summary", "mortgage/other interested parties",
#     "applicable deductible(s)", "premiums", "forms and endorsements",
#     "policy period", "policyholder since", "billing information",
#     "payment plan", "discount information", "for your information",
#     "important notice", "thank you", "office use space", "message(s)",
#     "mortgagee(s)", "endorsements", "schedule", "notice",
# }

# JUNK_VALUES = {
#     "type", "interest", "policy", "coverage", "summary",
#     "n/a", "none", "see attached", "continued", "page",
#     "na", "tbd", "pending", "unknown",
# }

# PREFIX_STRIP = [
#     "coverage detail for", "policy effective date is",
#     "effective date is", "your policy effective date is",
#     "your policy effective date:", "location:", "address:",
#     "name:", "insured:", "named insured:", "property:",
#     "mailing:", "policy number:", "policy no:",
# ]


# # ============================================================
# # REGEX PATTERNS
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
# ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')
# PO_BOX_RE = re.compile(r'p\.?o\.?\s*box\s+\d+', re.I)

# STREET_TYPES = (
#     "st", "street", "ave", "avenue", "rd", "road", "blvd", "boulevard",
#     "ln", "lane", "dr", "drive", "ct", "court", "cir", "circle",
#     "way", "pkwy", "parkway", "place", "pl", "terrace", "ter",
#     "trail", "trl", "highway", "hwy", "ridge"
# )


# # ============================================================
# # HELPERS
# # ============================================================

# def _is_section_header_value(value: str) -> bool:
#     """Check if value is actually a section header, not real data"""
#     if not value:
#         return False
    
#     v = value.lower().strip()
    
#     # Exact match
#     if v in SECTION_TITLES:
#         return True
    
#     # Contains section title
#     for title in SECTION_TITLES:
#         if v == title or (title in v and len(v) < len(title) + 15):
#             return True
    
#     # Ends with colon and short
#     if v.endswith(":") and len(v.split()) <= 4:
#         return True
    
#     # All caps and 3+ words (likely header)
#     if value.isupper() and len(value.split()) >= 4:
#         return True
    
#     return False


# def _strip_prefixes(value: str) -> str:
#     """Remove common label prefixes from values"""
#     v = value.strip()
#     vl = v.lower()
    
#     for p in PREFIX_STRIP:
#         if vl.startswith(p):
#             v = v[len(p):].strip(" :.-")
#             vl = v.lower()
    
#     return v


# def _normalize_whitespace(value: str) -> str:
#     """Normalize whitespace in value"""
#     return re.sub(r'\s+', ' ', value).strip()


# def _normalize_address(value: str) -> str:
#     """Normalize address formatting"""
#     v = _normalize_whitespace(value)
    
#     # Expand common abbreviations
#     replacements = {
#         r'\bSt\b(?!\.)': 'Street',
#         r'\bAve\b(?!\.)': 'Avenue',
#         r'\bRd\b(?!\.)': 'Road',
#         r'\bBlvd\b(?!\.)': 'Boulevard',
#         r'\bDr\b(?!\.)': 'Drive',
#         r'\bLn\b(?!\.)': 'Lane',
#         r'\bCt\b(?!\.)': 'Court',
#         r'\bCir\b(?!\.)': 'Circle',
#         r'\bPkwy\b(?!\.)': 'Parkway',
#         r'\bHwy\b(?!\.)': 'Highway',
#     }
    
#     for pattern, replacement in replacements.items():
#         v = re.sub(pattern, replacement, v, flags=re.I)
    
#     return v


# def _normalize_phone(value: str) -> str:
#     """Normalize phone number formatting"""
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
#     elif len(digits) == 11 and digits[0] == '1':
#         return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
#     return value


# # ============================================================
# # VALIDATORS (FIXED)
# # ============================================================

# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     """Validate carrier name"""
#     v = _normalize_whitespace(value)
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     if len(v) < 3:
#         return False, v, 0.0
    
#     # Should have "insurance" or similar
#     ll = v.lower()
#     if not any(w in ll for w in ("insurance", "exchange", "mutual", "indemnity", "company", "group", "corp")):
#         # Still allow if it's a known carrier pattern
#         if len(v.split()) < 2:
#             return False, v, 0.0
    
#     return True, v.upper(), 0.95


# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     """
#     Validate policy number - FIXED VERSION
#     More flexible, but still blocks phone numbers
#     """
#     v = value.strip()
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     # Remove common prefixes
#     v = _strip_prefixes(v)
    
#     # CRITICAL: Block phone numbers
#     v_no_format = re.sub(r'[\s\-\(\)\.]', '', v)
    
#     # 10-digit number with phone-like patterns
#     if PHONE_RE.fullmatch(v):
#         return False, v, 0.0
    
#     # Partial phone (7 digits with formatting)
#     if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
#         return False, v, 0.0
    
#     # Pure 10-digit might be phone - check formatting
#     digits_only = ''.join(c for c in v if c.isdigit())
#     if len(digits_only) == 10:
#         # If formatted like phone, reject
#         if re.match(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', v):
#             return False, v, 0.0
#         # If no formatting and just 10 digits, might be phone
#         if v == digits_only:
#             return False, v, 0.0
    
#     # Block ZIP codes
#     if ZIP_RE.fullmatch(v):
#         return False, v, 0.0
    
#     # Block dates
#     if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', v, re.I):
#         return False, v, 0.0
#     if DATE_RE.fullmatch(v):
#         return False, v, 0.0
    
#     # Block 4-digit years
#     if re.fullmatch(r'(19|20)\d{2}', v):
#         return False, v, 0.0
    
#     # Count characters
#     digits = sum(c.isdigit() for c in v)
#     letters = sum(c.isalpha() for c in v)
    
#     # Must have substantial length
#     if len(v) < 6:
#         return False, v, 0.0
    
#     if len(v) > 35:
#         return False, v, 0.0
    
#     # Must have at least 5 digits (RELAXED from original)
#     if digits < 5:
#         return False, v, 0.0
    
#     # Pure numeric: 8-14 digits is valid
#     if v_no_format.isdigit():
#         if 8 <= len(v_no_format) <= 14:
#             return True, v, 0.95
#         else:
#             return False, v, 0.0
    
#     # Mixed alphanumeric
#     if letters > 0 and digits >= 5:
#         return True, v, 0.95
    
#     return False, v, 0.0


# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     """Validate loan number"""
#     v = value.strip()
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     digits = sum(c.isdigit() for c in v)
    
#     # Must have at least 6 digits
#     if digits < 6:
#         return False, v, 0.0
    
#     # Block phone numbers
#     if PHONE_RE.fullmatch(v):
#         return False, v, 0.0
    
#     return True, v, 0.95


# def validate_name(value: str) -> Tuple[bool, str, float]:
#     """
#     Validate person/company name - FIXED VERSION
#     More flexible for real-world name formats
#     """
#     v = _normalize_whitespace(value)
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     # Remove prefix labels
#     v = _strip_prefixes(v)
    
#     if not v or len(v) < 2:
#         return False, v, 0.0
    
#     # Block if contains colon (likely a label)
#     if ":" in v:
#         return False, v, 0.0
    
#     # Block structural keywords
#     bad_keywords = (
#         "named insured", "insured name", "mailing address",
#         "property address", "policy type", "coverage",
#         "deductible", "premium", "billing", "mortgagee",
#         "mortgage", "lender", "loan", "copy", "page",
#         "interest", "section", "premises", "office use",
#         "office use space", "message", "declarations",
#         "effective date", "expiration date", "policy period",
#         "endorsement", "summary", "schedule", "notice",
#     )
#     if any(w in v.lower() for w in bad_keywords):
#         return False, v, 0.0
    
#     # Check for entity indicators
#     has_entity = any(w in v.lower() for w in (
#         "llc", "inc", "corp", "company", "trust", "ltd",
#         "bank", "mortgage", "lending", "credit", "services"
#     ))
    
#     # Allow digits only if has entity suffix
#     if any(c.isdigit() for c in v) and not has_entity:
#         return False, v, 0.0
    
#     # Word count validation
#     words = [w for w in v.split() if w]
    
#     if has_entity:
#         # Entity names can be longer
#         if not (1 <= len(words) <= 12):
#             return False, v, 0.0
#     else:
#         # Person names: 2-6 words typical
#         if not (2 <= len(words) <= 7):
#             return False, v, 0.0
    
#     # At least one word should be capitalized (RELAXED)
#     caps = sum(1 for w in words if w and w[0].isupper())
#     if caps < 1:
#         return False, v, 0.0
    
#     return True, v, 0.95


# def validate_address(value: str) -> Tuple[bool, str, float]:
#     """
#     Validate address - FIXED VERSION
#     Better support for PO Box and various formats
#     """
#     v = _normalize_whitespace(_strip_prefixes(value))
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     if not v or len(v) < 5:
#         return False, v, 0.0
    
#     # Block if ends with colon
#     if v.endswith(":"):
#         return False, v, 0.0
    
#     v_lower = v.lower()
    
#     # Block non-address content
#     bad_patterns = [
#         "policy period", "beginning", "through", "standard time",
#         "coverage", "summary", "declarations", "effective date",
#         "office use", "message", "mortgagee", "endorsement",
#         "premium", "deductible",
#     ]
#     if any(kw in v_lower for kw in bad_patterns):
#         return False, v, 0.0
    
#     # PO Box - VALID
#     if PO_BOX_RE.search(v):
#         return True, _normalize_address(v), 0.95
    
#     # Street address with number and street type
#     street_pattern = re.compile(
#         r'\d+\s+.+?\b(' + '|'.join(STREET_TYPES) + r')\b',
#         re.I
#     )
#     if street_pattern.search(v):
#         return True, _normalize_address(v), 0.95
    
#     # Has state abbreviation + ZIP
#     if re.search(r'\b[A-Z]{2}\s*\d{5}(-\d{4})?\b', v):
#         return True, _normalize_address(v), 0.92
    
#     # Has street number at start
#     if re.match(r'^\d+\s+\w', v):
#         word_count = len(v.split())
#         if word_count >= 3:
#             return True, _normalize_address(v), 0.88
    
#     # Fallback: has numbers and reasonable length
#     has_number = bool(re.search(r'\d+', v))
#     word_count = len(v.split())
#     if has_number and word_count >= 4:
#         return True, _normalize_address(v), 0.80
    
#     return False, v, 0.0


# def validate_date(value: str) -> Tuple[bool, str, float]:
#     """Validate date value"""
#     v = _normalize_whitespace(_strip_prefixes(value))
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     # Try various date formats
#     date_formats = [
#         "%B %d, %Y",      # January 15, 2024
#         "%b %d, %Y",      # Jan 15, 2024
#         "%B %d %Y",       # January 15 2024
#         "%m/%d/%Y",       # 01/15/2024
#         "%m-%d-%Y",       # 01-15-2024
#         "%m/%d/%y",       # 01/15/24
#         "%Y-%m-%d",       # 2024-01-15
#         "%d %B %Y",       # 15 January 2024
#     ]
    
#     for fmt in date_formats:
#         try:
#             dt = datetime.strptime(v, fmt)
#             if 1990 <= dt.year <= 2050:
#                 return True, v, 0.95
#         except ValueError:
#             continue
    
#     # Try partial match
#     m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', v)
#     if m:
#         return True, m.group(1), 0.90
    
#     m = re.search(r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', v)
#     if m:
#         return True, m.group(1), 0.90
    
#     return False, v, 0.0


# def validate_money(value: str) -> Tuple[bool, str, float]:
#     """Validate monetary value"""
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     try:
#         clean = value.replace('$', '').replace(',', '').strip()
#         amt = float(clean)
        
#         if 1 <= amt <= 10_000_000:
#             formatted = f"${amt:,.2f}".replace('.00', '')
#             return True, formatted, 0.92
#     except Exception:
#         pass
    
#     return False, value, 0.0


# def validate_phone(value: str) -> Tuple[bool, str, float]:
#     """Validate phone number"""
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         normalized = _normalize_phone(value)
#         return True, normalized, 0.95
#     elif len(digits) == 11 and digits[0] == '1':
#         normalized = _normalize_phone(value)
#         return True, normalized, 0.95
    
#     return False, value, 0.0


# # ============================================================
# # CROSS-VALIDATION
# # ============================================================

# def _cross_validate(validated: Dict) -> Dict:
#     """Cross-validate related fields for consistency"""
    
#     # Boost confidence if mailing == property
#     if "mailing_address" in validated and "property_address" in validated:
#         mailing = validated["mailing_address"]["value"]
#         property_addr = validated["property_address"]["value"]
        
#         mailing_norm = mailing.lower().replace(',', '').replace('.', '')
#         property_norm = property_addr.lower().replace(',', '').replace('.', '')
        
#         if mailing_norm == property_norm:
#             validated["mailing_address"]["confidence"] = min(1.0, validated["mailing_address"]["confidence"] * 1.1)
#             validated["property_address"]["confidence"] = min(1.0, validated["property_address"]["confidence"] * 1.1)
#             validated["mailing_address"]["note"] = "Same as property address"
    
#     # Boost confidence if effective < expiration
#     if "effective_date" in validated and "expiration_date" in validated:
#         try:
#             eff = validated["effective_date"]["value"]
#             exp = validated["expiration_date"]["value"]
            
#             for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]:
#                 try:
#                     eff_dt = datetime.strptime(eff, fmt)
#                     exp_dt = datetime.strptime(exp, fmt)
                    
#                     if eff_dt < exp_dt:
#                         validated["effective_date"]["confidence"] = min(1.0, validated["effective_date"]["confidence"] * 1.05)
#                         validated["expiration_date"]["confidence"] = min(1.0, validated["expiration_date"]["confidence"] * 1.05)
#                     break
#                 except:
#                     continue
#         except:
#             pass
    
#     return validated


# # ============================================================
# # MAIN VALIDATION
# # ============================================================

# def validate_and_arbitrate(
#     merged_fields: Dict,
#     ocr_confidence: float,
#     stage_breakdown: Dict,
# ) -> Tuple[Dict, float]:
#     """
#     Main validation entry point
#     Validates and filters extracted fields
#     """
#     validated = {}
#     scores = []
    
#     validators = {
#         "carrier_name": validate_carrier,
#         "policy_number": validate_policy_number,
#         "loan_number": validate_loan_number,
#         "insured_name": validate_name,
#         "agent_name": validate_name,
#         "mortgage_company": validate_name,
#         "property_address": validate_address,
#         "mailing_address": validate_address,
#         "effective_date": validate_date,
#         "expiration_date": validate_date,
#         "total_premium": validate_money,
#         "deductible": validate_money,
#         "agent_phone": validate_phone,
#     }
    
#     for field, data in merged_fields.items():
#         if not isinstance(data, dict):
#             continue
        
#         value = data.get("value")
#         confidence = data.get("confidence", 0.0)
        
#         # Check confidence floor
#         floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor or not value:
#             continue
        
#         # Apply field-specific validation
#         if field in validators:
#             ok, norm_value, score = validators[field](value)
#             if not ok:
#                 continue
            
#             data["value"] = norm_value
#             data["validation_score"] = score
#             scores.append(score)
#         else:
#             # Pass through unknown fields
#             scores.append(0.80)
        
#         validated[field] = data
    
#     # Cross-validate related fields
#     validated = _cross_validate(validated)
    
#     # Calculate final confidence
#     if scores:
#         avg_validation_score = sum(scores) / len(scores)
#         final_confidence = round(
#             avg_validation_score * 0.6 + ocr_confidence * 0.4,
#             3,
#         )
#     else:
#         final_confidence = round(ocr_confidence * 0.4, 3)
    
#     return validated, final_confidence


# def validate_output(structured: Dict, confidence: float):
#     """Backward compatible wrapper"""
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})


# """
# Stage 4 – Validation & Arbitration Agent (ENHANCED)
# =======================================================
# Comprehensive validation with strict filtering
# ENHANCED: Better phone number blocking for policy numbers
# """

# import re
# from datetime import datetime
# from typing import Dict, Tuple


# # ============================================================
# # CONFIDENCE FLOORS
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier_name": 0.85,
#     "policy_number": 0.85,
#     "loan_number": 0.85,
#     "insured_name": 0.80,
#     "property_address": 0.80,
#     "mailing_address": 0.75,
#     "mortgage_company": 0.80,
#     "total_premium": 0.75,
#     "deductible": 0.75,
#     "effective_date": 0.80,
#     "expiration_date": 0.80,
#     "agent_phone": 0.80,
#     "agent_name": 0.75,
# }

# DEFAULT_FLOOR = 0.70


# # ============================================================
# # BLOCK LISTS
# # ============================================================

# SECTION_TITLES = {
#     "summary",
#     "home protection",
#     "coverage",
#     "coverages",
#     "limits",
#     "policy mortgage declarations summary",
#     "declarations",
#     "declarations summary",
#     "mortgage/other interested parties",
#     "applicable deductible(s)",
#     "premiums",
#     "forms and endorsements",
#     "policy period",
#     "policyholder since",
#     "billing information",
#     "payment plan",
#     "discount information",
#     "for your information",
#     "important notice",
#     "thank you",
#     "office use space",
#     "message(s)",
#     "mortgagee(s)",
# }

# JUNK_VALUES = {
#     "type",
#     "interest",
#     "policy",
#     "coverage",
#     "summary",
#     "n/a",
#     "none",
#     "see attached",
#     "continued",
#     "page",
# }

# PREFIX_STRIP = [
#     "coverage detail for",
#     "policy effective date is",
#     "effective date is",
#     "your policy effective date is",
#     "your policy effective date:",
#     "location:",
#     "address:",
#     "name:",
#     "insured:",
#     "named insured:",
#     "property:",
#     "mailing:",
# ]


# # ============================================================
# # HELPERS
# # ============================================================

# def _is_section_header_value(value: str) -> bool:
#     if not value:
#         return False

#     l = value.lower().strip()

#     if l in SECTION_TITLES:
#         return True

#     for title in SECTION_TITLES:
#         if l.startswith(title) or title in l:
#             return True

#     if l.endswith(":") and len(l.split()) <= 5:
#         return True
    
#     if value.isupper() and len(value.split()) >= 3:
#         return True

#     return False


# def _strip_prefixes(value: str) -> str:
#     v = value.strip()
#     vl = v.lower()
    
#     for p in PREFIX_STRIP:
#         if vl.startswith(p):
#             v = v[len(p):].strip(" :.-")
    
#     return v


# def _normalize_whitespace(value: str) -> str:
#     return re.sub(r'\s+', ' ', value).strip()


# def _normalize_address(value: str) -> str:
#     v = _normalize_whitespace(value)
    
#     replacements = {
#         r'\bSt\b': 'Street',
#         r'\bAve\b': 'Avenue',
#         r'\bRd\b': 'Road',
#         r'\bBlvd\b': 'Boulevard',
#         r'\bDr\b': 'Drive',
#         r'\bLn\b': 'Lane',
#         r'\bCt\b': 'Court',
#         r'\bCir\b': 'Circle',
#     }
    
#     for pattern, replacement in replacements.items():
#         v = re.sub(pattern, replacement, v, flags=re.I)
    
#     return v


# def _normalize_phone(value: str) -> str:
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
#     elif len(digits) == 11 and digits[0] == '1':
#         return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
#     return value


# # ============================================================
# # VALIDATORS (ENHANCED)
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
# ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')


# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(value)
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     if len(v) < 3:
#         return False, v, 0.0
    
#     return True, v.upper(), 0.95


# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     """Validate policy number with STRICT filtering - ENHANCED"""
#     v = value.strip()

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     # CRITICAL: Block phone numbers (most common false positive)
#     if PHONE_RE.fullmatch(v.replace(" ", "")):
#         return False, v, 0.0
    
#     # Block partial phone numbers (last 7 digits)
#     if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
#         return False, v, 0.0
    
#     # NEW: Block 10-digit sequences (likely phone)
#     digits_only = ''.join(c for c in v if c.isdigit())
#     if len(digits_only) == 10:
#         return False, v, 0.0
    
#     # Block short numeric sequences (barcodes, reference codes)
#     if re.fullmatch(r"\d{1,7}", v):
#         return False, v, 0.0

#     # Can't be just ZIP
#     if ZIP_RE.fullmatch(v):
#         return False, v, 0.0
    
#     # Block date-like patterns
#     if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', v, re.I):
#         return False, v, 0.0
#     if re.match(r'^[A-Za-z]+\d{1,2},?\d{4}$', v):
#         return False, v, 0.0

#     digits = sum(c.isdigit() for c in v)
#     letters = sum(c.isalpha() for c in v)
    
#     # Must have substantial digits
#     if digits < 5:
#         return False, v, 0.0
    
#     # Can't be mostly letters with few digits
#     if letters > digits:
#         return False, v, 0.0
    
#     # Length check
#     if not (7 <= len(v) <= 35):
#         return False, v, 0.0

#     return True, v, 0.95


# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     v = value.strip()
    
#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     digits = sum(c.isdigit() for c in v)
#     if digits < 6:
#         return False, v, 0.0
    
#     return True, v, 0.95


# def validate_name(value: str) -> Tuple[bool, str, float]:
#     """Validate person/company name with comprehensive filtering"""
#     v = _normalize_whitespace(value)

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if ":" in v:
#         return False, v, 0.0

#     # Block structural keywords - COMPREHENSIVE
#     bad_keywords = (
#         "named insured",
#         "insured name",
#         "mailing address",
#         "property address",
#         "policy type",
#         "coverage",
#         "deductible",
#         "premium",
#         "billing",
#         "mortgagee",
#         "mortgage",
#         "lender",
#         "loan",
#         "copy",
#         "page",
#         "interest",
#         "section",
#         "premises",
#         "office use",
#         "office use space",
#         "message",
#         "declarations",
#         "effective date",
#         "expiration date",
#     )
#     if any(w in v.lower() for w in bad_keywords):
#         return False, v, 0.0

#     # Allow digits if has entity suffix
#     has_entity = any(w in v.lower() for w in ["llc", "inc", "corp", "company", "trust", "ltd"])
#     if any(c.isdigit() for c in v) and not has_entity:
#         return False, v, 0.0

#     words = [w for w in v.split() if w]
    
#     if has_entity:
#         if not (2 <= len(words) <= 10):
#             return False, v, 0.0
#     else:
#         if not (2 <= len(words) <= 6):
#             return False, v, 0.0

#     return True, v, 0.95


# def validate_address(value: str) -> Tuple[bool, str, float]:
#     """Validate address with strict filtering"""
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if _is_section_header_value(v):
#         return False, v, 0.0
    
#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0
    
#     # Block if contains period/date keywords
#     v_lower = v.lower()
#     if any(kw in v_lower for kw in [
#         "policy period", "beginning", "through", "standard time",
#         "coverage", "summary", "declarations", "effective date",
#         "office use", "message", "mortgagee"
#     ]):
#         return False, v, 0.0

#     # PO Box
#     if re.search(r'p\.?o\.?\s*box', v, re.I):
#         return True, _normalize_address(v), 0.95

#     # Street address - MUST have street number
#     street_pattern = re.compile(
#         r'\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court|cir|circle)\b',
#         re.I
#     )
#     if street_pattern.search(v):
#         return True, _normalize_address(v), 0.93

#     # Has state + ZIP
#     if re.search(r'\b[A-Z]{2}\s*\d{5}', v):
#         return True, _normalize_address(v), 0.92

#     # Has number and reasonable length
#     has_number = bool(re.search(r'\d+', v))
#     word_count = len(v.split())
#     if has_number and word_count >= 3:
#         return True, _normalize_address(v), 0.85

#     return False, v, 0.0


# def validate_date(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     date_formats = [
#         "%B %d, %Y",
#         "%b %d, %Y",
#         "%m/%d/%Y",
#         "%m-%d-%Y",
#         "%m/%d/%y",
#         "%Y-%m-%d",
#     ]

#     for fmt in date_formats:
#         try:
#             dt = datetime.strptime(v, fmt)
#             if 1990 <= dt.year <= 2050:
#                 return True, v, 0.95
#         except ValueError:
#             continue

#     return False, v, 0.0


# def validate_money(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     try:
#         clean = value.replace('$', '').replace(',', '').strip()
#         amt = float(clean)
        
#         if 10 <= amt <= 1_000_000:
#             formatted = f"${amt:,.2f}".replace('.00', '')
#             return True, formatted, 0.92
#     except Exception:
#         pass
    
#     return False, value, 0.0


# def validate_phone(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value):
#         return False, value, 0.0
    
#     digits = ''.join(c for c in value if c.isdigit())
    
#     if len(digits) == 10:
#         normalized = _normalize_phone(value)
#         return True, normalized, 0.95
    
#     return False, value, 0.0


# # ============================================================
# # CROSS-VALIDATION
# # ============================================================

# def _cross_validate(validated: Dict) -> Dict:
#     if ("mailing_address" in validated and 
#         "property_address" in validated):
        
#         mailing = validated["mailing_address"]["value"]
#         property_addr = validated["property_address"]["value"]
        
#         mailing_norm = mailing.lower().replace(',', '').replace('.', '')
#         property_norm = property_addr.lower().replace(',', '').replace('.', '')
        
#         if mailing_norm == property_norm:
#             validated["mailing_address"]["confidence"] *= 1.1
#             validated["property_address"]["confidence"] *= 1.1
#             validated["mailing_address"]["note"] = "Same as property address"
    
#     if ("effective_date" in validated and 
#         "expiration_date" in validated):
        
#         try:
#             eff = validated["effective_date"]["value"]
#             exp = validated["expiration_date"]["value"]
            
#             for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y"]:
#                 try:
#                     eff_dt = datetime.strptime(eff, fmt)
#                     exp_dt = datetime.strptime(exp, fmt)
                    
#                     if eff_dt < exp_dt:
#                         validated["effective_date"]["confidence"] *= 1.05
#                         validated["expiration_date"]["confidence"] *= 1.05
#                     break
#                 except:
#                     continue
#         except:
#             pass
    
#     return validated


# # ============================================================
# # MAIN VALIDATION
# # ============================================================

# def validate_and_arbitrate(
#     merged_fields: Dict,
#     ocr_confidence: float,
#     stage_breakdown: Dict,
# ) -> Tuple[Dict, float]:
#     validated = {}
#     scores = []

#     validators = {
#         "carrier_name": validate_carrier,
#         "policy_number": validate_policy_number,
#         "loan_number": validate_loan_number,
#         "insured_name": validate_name,
#         "agent_name": validate_name,
#         "mortgage_company": validate_name,
#         "property_address": validate_address,
#         "mailing_address": validate_address,
#         "effective_date": validate_date,
#         "expiration_date": validate_date,
#         "total_premium": validate_money,
#         "deductible": validate_money,
#         "agent_phone": validate_phone,
#     }

#     for field, data in merged_fields.items():
#         if not isinstance(data, dict):
#             continue

#         value = data.get("value")
#         confidence = data.get("confidence", 0.0)

#         floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor or not value:
#             continue

#         if field in validators:
#             ok, norm_value, score = validators[field](value)
#             if not ok:
#                 continue
            
#             data["value"] = norm_value
#             data["validation_score"] = score
#             scores.append(score)
#         else:
#             scores.append(0.80)

#         validated[field] = data

#     validated = _cross_validate(validated)

#     if scores:
#         avg_validation_score = sum(scores) / len(scores)
#         final_confidence = round(
#             avg_validation_score * 0.6 + ocr_confidence * 0.4,
#             3,
#         )
#     else:
#         final_confidence = round(ocr_confidence * 0.4, 3)

#     return validated, final_confidence


# def validate_output(structured: Dict, confidence: float):
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})


"""
Stage 4 – Validation & Arbitration Agent (FIXED VERSION)
=========================================================
FIXES APPLIED:
1. Policy Number - Relaxed digit requirements, better phone blocking
2. Insured Name - Allow single uppercase word, relaxed word count
3. Address - Better PO Box support, relaxed validation
4. Lowered confidence floors to not reject valid extractions

Key Changes:
- validate_policy_number: Allow 8+ digit pure numeric, fix phone blocking
- validate_name: Allow names with 1+ capitalized words, longer company names
- validate_address: Support PO Box, city/state/zip patterns
- Reduced confidence floors to prevent over-filtering
"""

import re
from datetime import datetime
from typing import Dict, Tuple


# ============================================================
# CONFIDENCE FLOORS (RELAXED)
# ============================================================

CONFIDENCE_FLOORS = {
    "carrier_name": 0.75,      # Was 0.85
    "policy_number": 0.75,     # Was 0.85
    "loan_number": 0.75,       # Was 0.85
    "insured_name": 0.70,      # Was 0.80
    "property_address": 0.70,  # Was 0.80
    "mailing_address": 0.65,   # Was 0.75
    "mortgage_company": 0.70,  # Was 0.80
    "total_premium": 0.70,     # Was 0.75
    "deductible": 0.70,        # Was 0.75
    "effective_date": 0.70,    # Was 0.80
    "expiration_date": 0.70,   # Was 0.80
    "agent_phone": 0.70,       # Was 0.80
    "agent_name": 0.65,        # Was 0.75
}

DEFAULT_FLOOR = 0.60  # Was 0.70


# ============================================================
# BLOCK LISTS
# ============================================================

SECTION_TITLES = {
    "summary", "home protection", "coverage", "coverages", "limits",
    "policy mortgage declarations summary", "declarations",
    "declarations summary", "mortgage/other interested parties",
    "applicable deductible(s)", "premiums", "forms and endorsements",
    "policy period", "policyholder since", "billing information",
    "payment plan", "discount information", "for your information",
    "important notice", "thank you", "office use space", "message(s)",
    "mortgagee(s)", "endorsements", "schedule", "notice",
}

JUNK_VALUES = {
    "type", "interest", "policy", "coverage", "summary",
    "n/a", "none", "see attached", "continued", "page",
    "na", "tbd", "pending", "unknown",
}

PREFIX_STRIP = [
    "coverage detail for", "policy effective date is",
    "effective date is", "your policy effective date is",
    "your policy effective date:", "location:", "address:",
    "name:", "insured:", "named insured:", "property:",
    "mailing:", "policy number:", "policy no:",
]


# ============================================================
# REGEX PATTERNS
# ============================================================

PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')
PO_BOX_RE = re.compile(r'p\.?o\.?\s*box\s+\d+', re.I)

STREET_TYPES = (
    "st", "street", "ave", "avenue", "rd", "road", "blvd", "boulevard",
    "ln", "lane", "dr", "drive", "ct", "court", "cir", "circle",
    "way", "pkwy", "parkway", "place", "pl", "terrace", "ter",
    "trail", "trl", "highway", "hwy", "ridge"
)


# ============================================================
# HELPERS
# ============================================================

def _is_section_header_value(value: str) -> bool:
    """Check if value is actually a section header, not real data"""
    if not value:
        return False
    
    v = value.lower().strip()
    
    # Exact match
    if v in SECTION_TITLES:
        return True
    
    # Contains section title
    for title in SECTION_TITLES:
        if v == title or (title in v and len(v) < len(title) + 15):
            return True
    
    # Ends with colon and short
    if v.endswith(":") and len(v.split()) <= 4:
        return True
    
    # All caps and 3+ words (likely header)
    if value.isupper() and len(value.split()) >= 4:
        return True
    
    return False


def _strip_prefixes(value: str) -> str:
    """Remove common label prefixes from values"""
    v = value.strip()
    vl = v.lower()
    
    for p in PREFIX_STRIP:
        if vl.startswith(p):
            v = v[len(p):].strip(" :.-")
            vl = v.lower()
    
    return v


def _normalize_whitespace(value: str) -> str:
    """Normalize whitespace in value"""
    return re.sub(r'\s+', ' ', value).strip()


def _normalize_address(value: str) -> str:
    """Normalize address formatting"""
    v = _normalize_whitespace(value)
    
    # Expand common abbreviations
    replacements = {
        r'\bSt\b(?!\.)': 'Street',
        r'\bAve\b(?!\.)': 'Avenue',
        r'\bRd\b(?!\.)': 'Road',
        r'\bBlvd\b(?!\.)': 'Boulevard',
        r'\bDr\b(?!\.)': 'Drive',
        r'\bLn\b(?!\.)': 'Lane',
        r'\bCt\b(?!\.)': 'Court',
        r'\bCir\b(?!\.)': 'Circle',
        r'\bPkwy\b(?!\.)': 'Parkway',
        r'\bHwy\b(?!\.)': 'Highway',
    }
    
    for pattern, replacement in replacements.items():
        v = re.sub(pattern, replacement, v, flags=re.I)
    
    return v


def _normalize_phone(value: str) -> str:
    """Normalize phone number formatting"""
    digits = ''.join(c for c in value if c.isdigit())
    
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    return value


# ============================================================
# VALIDATORS (FIXED)
# ============================================================

def validate_carrier(value: str) -> Tuple[bool, str, float]:
    """Validate carrier name"""
    v = _normalize_whitespace(value)
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    if v.lower() in JUNK_VALUES:
        return False, v, 0.0
    
    if len(v) < 3:
        return False, v, 0.0
    
    # Should have "insurance" or similar
    ll = v.lower()
    if not any(w in ll for w in ("insurance", "exchange", "mutual", "indemnity", "company", "group", "corp")):
        # Still allow if it's a known carrier pattern
        if len(v.split()) < 2:
            return False, v, 0.0
    
    return True, v.upper(), 0.95


def validate_policy_number(value: str) -> Tuple[bool, str, float]:
    """
    Validate policy number - FIXED VERSION
    More flexible, but still blocks phone numbers
    """
    v = value.strip()
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    if v.lower() in JUNK_VALUES:
        return False, v, 0.0
    
    # Remove common prefixes
    v = _strip_prefixes(v)
    
    # CRITICAL: Block phone numbers
    v_no_format = re.sub(r'[\s\-\(\)\.]', '', v)
    
    # 10-digit number with phone-like patterns
    if PHONE_RE.fullmatch(v):
        return False, v, 0.0
    
    # Partial phone (7 digits with formatting)
    if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
        return False, v, 0.0
    
    # Pure 10-digit might be phone - check formatting
    digits_only = ''.join(c for c in v if c.isdigit())
    if len(digits_only) == 10:
        # If formatted like phone, reject
        if re.match(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', v):
            return False, v, 0.0
        # If no formatting and just 10 digits, might be phone
        if v == digits_only:
            return False, v, 0.0
    
    # Block ZIP codes
    if ZIP_RE.fullmatch(v):
        return False, v, 0.0
    
    # Block dates
    if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', v, re.I):
        return False, v, 0.0
    if DATE_RE.fullmatch(v):
        return False, v, 0.0
    
    # Block 4-digit years
    if re.fullmatch(r'(19|20)\d{2}', v):
        return False, v, 0.0
    
    # Count characters
    digits = sum(c.isdigit() for c in v)
    letters = sum(c.isalpha() for c in v)
    
    # Must have substantial length
    if len(v) < 6:
        return False, v, 0.0
    
    if len(v) > 35:
        return False, v, 0.0
    
    # Must have at least 5 digits (RELAXED from original)
    if digits < 5:
        return False, v, 0.0
    
    # Pure numeric: 8-14 digits is valid
    if v_no_format.isdigit():
        if 8 <= len(v_no_format) <= 14:
            return True, v, 0.95
        else:
            return False, v, 0.0
    
    # Mixed alphanumeric
    if letters > 0 and digits >= 5:
        return True, v, 0.95
    
    return False, v, 0.0


def validate_loan_number(value: str) -> Tuple[bool, str, float]:
    """Validate loan number"""
    v = value.strip()
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    if v.lower() in JUNK_VALUES:
        return False, v, 0.0
    
    digits = sum(c.isdigit() for c in v)
    
    # Must have at least 6 digits
    if digits < 6:
        return False, v, 0.0
    
    # Block phone numbers
    if PHONE_RE.fullmatch(v):
        return False, v, 0.0
    
    return True, v, 0.95


def validate_name(value: str) -> Tuple[bool, str, float]:
    """
    Validate person/company name - FIXED VERSION
    More flexible for real-world name formats
    """
    v = _normalize_whitespace(value)
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    if v.lower() in JUNK_VALUES:
        return False, v, 0.0
    
    # Remove prefix labels
    v = _strip_prefixes(v)
    
    if not v or len(v) < 2:
        return False, v, 0.0
    
    # Block if contains colon (likely a label)
    if ":" in v:
        return False, v, 0.0
    
    # Block structural keywords
    bad_keywords = (
        "named insured", "insured name", "mailing address",
        "property address", "policy type", "coverage",
        "deductible", "premium", "billing", "mortgagee",
        "mortgage", "lender", "loan", "copy", "page",
        "interest", "section", "premises", "office use",
        "office use space", "message", "declarations",
        "effective date", "expiration date", "policy period",
        "endorsement", "summary", "schedule", "notice",
    )
    if any(w in v.lower() for w in bad_keywords):
        return False, v, 0.0
    
    # Check for entity indicators
    has_entity = any(w in v.lower() for w in (
        "llc", "inc", "corp", "company", "trust", "ltd",
        "bank", "mortgage", "lending", "credit", "services"
    ))
    
    # Allow digits only if has entity suffix
    if any(c.isdigit() for c in v) and not has_entity:
        return False, v, 0.0
    
    # Word count validation
    words = [w for w in v.split() if w]
    
    if has_entity:
        # Entity names can be longer
        if not (1 <= len(words) <= 12):
            return False, v, 0.0
    else:
        # Person names: 2-6 words typical
        if not (2 <= len(words) <= 7):
            return False, v, 0.0
    
    # At least one word should be capitalized (RELAXED)
    caps = sum(1 for w in words if w and w[0].isupper())
    if caps < 1:
        return False, v, 0.0
    
    return True, v, 0.95


def validate_address(value: str) -> Tuple[bool, str, float]:
    """
    Validate address - FIXED VERSION
    Better support for PO Box and various formats
    """
    v = _normalize_whitespace(_strip_prefixes(value))
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    if v.lower() in JUNK_VALUES:
        return False, v, 0.0
    
    if not v or len(v) < 5:
        return False, v, 0.0
    
    # Block if ends with colon
    if v.endswith(":"):
        return False, v, 0.0
    
    v_lower = v.lower()
    
    # Block non-address content
    bad_patterns = [
        "policy period", "beginning", "through", "standard time",
        "coverage", "summary", "declarations", "effective date",
        "office use", "message", "mortgagee", "endorsement",
        "premium", "deductible",
    ]
    if any(kw in v_lower for kw in bad_patterns):
        return False, v, 0.0
    
    # PO Box - VALID
    if PO_BOX_RE.search(v):
        return True, _normalize_address(v), 0.95
    
    # Street address with number and street type
    street_pattern = re.compile(
        r'\d+\s+.+?\b(' + '|'.join(STREET_TYPES) + r')\b',
        re.I
    )
    if street_pattern.search(v):
        return True, _normalize_address(v), 0.95
    
    # Has state abbreviation + ZIP
    if re.search(r'\b[A-Z]{2}\s*\d{5}(-\d{4})?\b', v):
        return True, _normalize_address(v), 0.92
    
    # Has street number at start
    if re.match(r'^\d+\s+\w', v):
        word_count = len(v.split())
        if word_count >= 3:
            return True, _normalize_address(v), 0.88
    
    # Fallback: has numbers and reasonable length
    has_number = bool(re.search(r'\d+', v))
    word_count = len(v.split())
    if has_number and word_count >= 4:
        return True, _normalize_address(v), 0.80
    
    return False, v, 0.0


def validate_date(value: str) -> Tuple[bool, str, float]:
    """Validate date value"""
    v = _normalize_whitespace(_strip_prefixes(value))
    
    if _is_section_header_value(v):
        return False, v, 0.0
    
    # Try various date formats
    date_formats = [
        "%B %d, %Y",      # January 15, 2024
        "%b %d, %Y",      # Jan 15, 2024
        "%B %d %Y",       # January 15 2024
        "%m/%d/%Y",       # 01/15/2024
        "%m-%d-%Y",       # 01-15-2024
        "%m/%d/%y",       # 01/15/24
        "%Y-%m-%d",       # 2024-01-15
        "%d %B %Y",       # 15 January 2024
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(v, fmt)
            if 1990 <= dt.year <= 2050:
                return True, v, 0.95
        except ValueError:
            continue
    
    # Try partial match
    m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', v)
    if m:
        return True, m.group(1), 0.90
    
    m = re.search(r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', v)
    if m:
        return True, m.group(1), 0.90
    
    return False, v, 0.0


def validate_money(value: str) -> Tuple[bool, str, float]:
    """Validate monetary value"""
    if _is_section_header_value(value):
        return False, value, 0.0
    
    try:
        clean = value.replace('$', '').replace(',', '').strip()
        amt = float(clean)
        
        if 1 <= amt <= 10_000_000:
            formatted = f"${amt:,.2f}".replace('.00', '')
            return True, formatted, 0.92
    except Exception:
        pass
    
    return False, value, 0.0


def validate_phone(value: str) -> Tuple[bool, str, float]:
    """Validate phone number"""
    if _is_section_header_value(value):
        return False, value, 0.0
    
    digits = ''.join(c for c in value if c.isdigit())
    
    if len(digits) == 10:
        normalized = _normalize_phone(value)
        return True, normalized, 0.95
    elif len(digits) == 11 and digits[0] == '1':
        normalized = _normalize_phone(value)
        return True, normalized, 0.95
    
    return False, value, 0.0


# ============================================================
# CROSS-VALIDATION
# ============================================================

def _cross_validate(validated: Dict) -> Dict:
    """Cross-validate related fields for consistency"""
    
    # Boost confidence if mailing == property
    if "mailing_address" in validated and "property_address" in validated:
        mailing = validated["mailing_address"]["value"]
        property_addr = validated["property_address"]["value"]
        
        mailing_norm = mailing.lower().replace(',', '').replace('.', '')
        property_norm = property_addr.lower().replace(',', '').replace('.', '')
        
        if mailing_norm == property_norm:
            validated["mailing_address"]["confidence"] = min(1.0, validated["mailing_address"]["confidence"] * 1.1)
            validated["property_address"]["confidence"] = min(1.0, validated["property_address"]["confidence"] * 1.1)
            validated["mailing_address"]["note"] = "Same as property address"
    
    # Boost confidence if effective < expiration
    if "effective_date" in validated and "expiration_date" in validated:
        try:
            eff = validated["effective_date"]["value"]
            exp = validated["expiration_date"]["value"]
            
            for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]:
                try:
                    eff_dt = datetime.strptime(eff, fmt)
                    exp_dt = datetime.strptime(exp, fmt)
                    
                    if eff_dt < exp_dt:
                        validated["effective_date"]["confidence"] = min(1.0, validated["effective_date"]["confidence"] * 1.05)
                        validated["expiration_date"]["confidence"] = min(1.0, validated["expiration_date"]["confidence"] * 1.05)
                    break
                except:
                    continue
        except:
            pass
    
    return validated


# ============================================================
# MAIN VALIDATION
# ============================================================

def validate_and_arbitrate(
    merged_fields: Dict,
    ocr_confidence: float,
    stage_breakdown: Dict,
) -> Tuple[Dict, float]:
    """
    Main validation entry point
    Validates and filters extracted fields
    """
    validated = {}
    scores = []
    
    validators = {
        "carrier_name": validate_carrier,
        "policy_number": validate_policy_number,
        "loan_number": validate_loan_number,
        "insured_name": validate_name,
        "agent_name": validate_name,
        "mortgage_company": validate_name,
        "property_address": validate_address,
        "mailing_address": validate_address,
        "effective_date": validate_date,
        "expiration_date": validate_date,
        "total_premium": validate_money,
        "deductible": validate_money,
        "agent_phone": validate_phone,
    }
    
    for field, data in merged_fields.items():
        if not isinstance(data, dict):
            continue
        
        value = data.get("value")
        confidence = data.get("confidence", 0.0)
        
        # Check confidence floor
        floor = CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
        if confidence < floor or not value:
            continue
        
        # Apply field-specific validation
        if field in validators:
            ok, norm_value, score = validators[field](value)
            if not ok:
                continue
            
            data["value"] = norm_value
            data["validation_score"] = score
            scores.append(score)
        else:
            # Pass through unknown fields
            scores.append(0.80)
        
        validated[field] = data
    
    # Cross-validate related fields
    validated = _cross_validate(validated)
    
    # Calculate final confidence
    if scores:
        avg_validation_score = sum(scores) / len(scores)
        final_confidence = round(
            avg_validation_score * 0.6 + ocr_confidence * 0.4,
            3,
        )
    else:
        final_confidence = round(ocr_confidence * 0.4, 3)
    
    return validated, final_confidence


def validate_output(structured: Dict, confidence: float):
    """Backward compatible wrapper"""
    return validate_and_arbitrate(structured, confidence, {"stage1": structured})