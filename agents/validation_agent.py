# """
# Stage 4 – Validation & Arbitration Agent (IMPROVED VERSION)
# ============================================================
# Major improvements to address common extraction errors:

# 1. INSURED NAME VALIDATION:
#    - Block marketing slogans ("You're in good hands", "policy payment quickly & easily ONLINE")
#    - Block product names ("HOMESAVER POLCY", "PROPERTY INSURANCE CORPORAION")
#    - Block document headers and structural text
#    - Require proper name patterns

# 2. POLICY NUMBER VALIDATION:
#    - Block page reference numbers and document codes
#    - Block phone numbers more aggressively
#    - Validate alphanumeric patterns correctly

# 3. ADDRESS VALIDATION:
#    - Distinguish between insured addresses and mortgage company addresses
#    - Block PO Box addresses that belong to mortgage companies (Troy MI pattern)
#    - Block document reference text disguised as addresses

# 4. LOAN NUMBER VALIDATION:
#    - Block page numbers and document reference codes
#    - Require proper loan number patterns

# 5. CARRIER NAME VALIDATION:
#    - Block truncated or malformed carrier names
#    - Block product names being captured as carriers
# """

# import re
# from datetime import datetime
# from typing import Dict, Tuple, Set


# # ============================================================
# # CONFIDENCE FLOORS
# # ============================================================

# CONFIDENCE_FLOORS = {
#     "carrier_name": 0.80,
#     "policy_number": 0.80,
#     "loan_number": 0.80,
#     "insured_name": 0.75,
#     "property_address": 0.75,
#     "mailing_address": 0.70,
#     "mortgage_company": 0.75,
#     "total_premium": 0.70,
#     "deductible": 0.70,
#     "effective_date": 0.75,
#     "expiration_date": 0.75,
#     "agent_phone": 0.75,
#     "agent_name": 0.70,
# }

# DEFAULT_FLOOR = 0.65


# # ============================================================
# # BLOCK LISTS - EXPANDED
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
#     "rating information", "additional coverages", "discounts",
# }

# JUNK_VALUES = {
#     "type", "interest", "policy", "coverage", "summary",
#     "n/a", "none", "see attached", "continued", "page",
#     "na", "tbd", "pending", "unknown", "included", "see policy",
# }

# # Marketing slogans and taglines to block as names
# MARKETING_SLOGANS = {
#     "you're in good hands",
#     "you're in good hands.",
#     "youre in good hands",
#     "on your side",
#     "like a good neighbor",
#     "we're all in this together",
#     "nationwide is on your side",
#     "for all that matters",
#     "the promise",
#     "keep the promise",
# }

# # Phrases that indicate document structure, not actual names
# BAD_NAME_PHRASES = {
#     "policy payment",
#     "quickly & easily",
#     "quickly and easily",
#     "online",
#     "pocket expenses",
#     "out of pocket",
#     "out-of-pocket",
#     "and policy information",
#     "policy information",
#     "page 1 of",
#     "page 2 of",
#     "page 3 of",
#     "mortgagee copy",
#     "declarations page",
#     "your policy",
#     "our policy",
#     "this policy",
#     "policy conditions",
#     "policy type",
#     "policy period",
#     "coverage detail",
#     "coverage info",
#     "premium info",
#     "building type",
#     "single family",
#     "construction type",
#     "roof-wall connection",
#     "roof connection",
#     "roof deck",
#     "additional insured",
#     "first named insured",
#     "named insured:",
#     "location id",
#     "location of",
#     "described location",
#     "effective date",
#     "expiration date",
#     "endorsement",
#     "deductible",
#     "important notice",
#     "special provisions",
# }

# # Product names that should not be captured as insured names
# PRODUCT_NAMES: Set[str] = {
#     "homesaver polcy",
#     "homesaver policy",
#     "homeowners policy",
#     "dwelling policy",
#     "mobilehome policy",
#     "mobilehomeowners",
#     "special form policy",
#     "wind only policy",
#     "condominium policy",
#     "condominium owners",
#     "rental unit owners",
#     "ultrapack plus",
#     "encompassone",
#     "encompass one",
# }

# # Company names that should NOT be captured as insured names
# # These are often mortgage companies, agents, or other entities
# BAD_INSURED_COMPANY_NAMES: Set[str] = {
#     "allied trust",
#     "properiy insurance",  # Typo
#     "property insurance",
#     "insurance corporation",
#     "insurance company",
#     "insurance exchange",
#     "mortgage company",
#     "mortgage corp",
#     "financial inc",
#     "lending llc",
#     "bank na",
# }

# # Truncated/malformed carrier names to reject
# BAD_CARRIER_PATTERNS = {
#     "properiy insurance",  # Typo
#     "property insurance corporaion",  # Missing T
#     "property insurance corporaiion",  # Double I
#     "insurance exchange*",  # Has asterisk
#     "insurance company*",
#     "insurance agency",  # Agency, not carrier
#     "insurance services",  # Services, not carrier
#     "insurance center",
#     "everett financial",  # Not a carrier, it's a lender
#     "broker solutions",
#     "nancy bond insurance",  # Agent, not carrier
#     "geico ins agency",
#     "allstate mortgage",
# }

# # Common mortgage company PO Box addresses (Troy MI is most common)
# MORTGAGE_PO_BOX_PATTERNS = [
#     r"p\.?o\.?\s*box\s*\d+.*troy.*mi",
#     r"p\.?o\.?\s*box\s*\d+.*48007",  # Troy MI ZIP
#     r"p\.?o\.?\s*box\s*\d+.*miami.*fl.*33197",
#     r"p\.?o\.?\s*box\s*\d+.*dallas.*tx.*75266",
# ]

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
#     "first named insured:",
#     "policyholder(s)",
#     "policyholder:",
# ]


# # ============================================================
# # REGEX PATTERNS
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
# ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')
# PO_BOX_RE = re.compile(r'p\.?o\.?\s*box', re.I)

# STREET_TYPES = [
#     'street', 'st', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd',
#     'lane', 'ln', 'drive', 'dr', 'court', 'ct', 'circle', 'cir',
#     'way', 'place', 'pl', 'terrace', 'ter', 'highway', 'hwy',
#     'parkway', 'pkwy', 'ridge'
# ]


# # ============================================================
# # HELPERS
# # ============================================================

# def _is_section_header_value(value: str) -> bool:
#     """Check if value is a section header, not actual data"""
#     if not value:
#         return False

#     v = value.lower().strip()

#     if v in SECTION_TITLES:
#         return True

#     for title in SECTION_TITLES:
#         if v.startswith(title) or title in v:
#             return True

#     # Ends with colon = likely header
#     if v.endswith(":") and len(v.split()) <= 5:
#         return True

#     # All uppercase multi-word WITHOUT being a typical name pattern
#     # Names are typically 2-4 words, headers are typically longer or contain structural words
#     if value.isupper() and len(value.split()) >= 3:
#         words = value.split()
#         v_lower = value.lower()
        
#         # If it contains "insurance", "company", "corporation", etc., it's likely a company name
#         # not a header
#         company_indicators = {'insurance', 'ins', 'company', 'co', 'corporation', 'corp', 'exchange', 
#                              'mutual', 'group', 'inc', 'llc', 'ltd'}
#         if any(ind in v_lower for ind in company_indicators):
#             return False  # Likely a company name, not a header
        
#         # Check if it looks like a header vs a name
#         # Headers often contain words like: PAGE, SECTION, COVERAGE, DECLARATIONS, NOTICE, etc.
#         header_words = {'PAGE', 'SECTION', 'COVERAGE', 'DECLARATIONS', 'NOTICE', 
#                        'INFORMATION', 'SUMMARY', 'DETAILS', 'SCHEDULE', 'ENDORSEMENT',
#                        'CONDITIONS', 'PROVISIONS', 'LIMITS', 'POLICY', 'PREMIUM',
#                        'TOTAL', 'SUBTOTAL', 'AMOUNT', 'DATE', 'NUMBER', 'TYPE'}
#         if any(w.upper() in header_words for w in words):
#             return True
#         # If it's a short all-caps phrase without header words, it might be a name
#         # Names: "JOHN SMITH", "HEATHER A BABCOCK", "MICHAEL K LANI"
#         # Allow up to 4 words if they don't contain header keywords
#         if len(words) <= 4:
#             return False  # Likely a name
#         # 5+ words all caps without digits and without company indicators = probably a header
#         if not any(c.isdigit() for c in value):
#             return True

#     return False


# def _strip_prefixes(value: str) -> str:
#     """Remove common prefixes from values"""
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
#     """Format phone number consistently"""
#     digits = ''.join(c for c in value if c.isdigit())

#     if len(digits) == 10:
#         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
#     elif len(digits) == 11 and digits[0] == '1':
#         return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

#     return value


# def _is_phone_number(value: str) -> bool:
#     """Check if value is a phone number"""
#     digits = ''.join(c for c in value if c.isdigit())
    
#     # Exactly 10 digits = phone
#     if len(digits) == 10:
#         return True
    
#     # 11 digits starting with 1 = phone with country code
#     if len(digits) == 11 and digits.startswith('1'):
#         return True
    
#     # 7 digits = local phone
#     if len(digits) == 7:
#         return True
    
#     # Has phone formatting
#     if PHONE_RE.search(value):
#         return True
    
#     return False


# def _is_document_reference(value: str) -> bool:
#     """Check if value is a document reference code, not actual data"""
#     v = value.lower().strip()
    
#     # Page references
#     if re.match(r'^\d+_\d+_\d+$', v):  # e.g., "19312_243570_11"
#         return True
    
#     if re.match(r'^page\s*\d+', v, re.I):
#         return True
    
#     # Document codes with underscores
#     if '_' in v and sum(c.isdigit() for c in v) > len(v) * 0.6:
#         return True
    
#     return False


# def _is_mortgage_company_address(value: str) -> bool:
#     """Check if address belongs to a mortgage company, not the insured"""
#     v = value.lower()
    
#     for pattern in MORTGAGE_PO_BOX_PATTERNS:
#         if re.search(pattern, v, re.I):
#             return True
    
#     # Generic mortgage PO Box indicators
#     if 'troy' in v and 'mi' in v and 'box' in v:
#         return True
    
#     if '48007' in v:  # Troy MI ZIP
#         return True
    
#     return False


# # ============================================================
# # VALIDATORS
# # ============================================================

# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     """Validate carrier name"""
#     v = _normalize_whitespace(value)

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0

#     if len(v) < 5:
#         return False, v, 0.0

#     # Clean up common OCR artifacts
#     v_clean = v.replace('*', '').replace('/', '').strip()
#     vl_clean = v_clean.lower()

#     # Block known bad carrier patterns (must check before positive matches)
#     for bad in BAD_CARRIER_PATTERNS:
#         if bad in vl_clean:
#             return False, v, 0.0

#     # Block agencies/agents/services FIRST (before insurance check)
#     if any(w in vl_clean for w in ('agency', 'agent', 'services', 'producer')):
#         return False, v, 0.0

#     # Must contain "insurance" (or "ins" abbreviation)
#     # Check for various patterns: "insurance", " ins ", " ins.", ends with " ins"
#     has_insurance = ('insurance' in vl_clean or 
#                      ' ins ' in vl_clean or 
#                      vl_clean.endswith(' ins') or 
#                      ' ins.' in vl_clean or
#                      ' ins co' in vl_clean or
#                      vl_clean.endswith(' ins co'))
#     if not has_insurance:
#         return False, v, 0.0

#     # Company type indicator (relaxed - many valid variations)
#     company_types = ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')
#     has_company_type = any(w in vl_clean for w in company_types)
    
#     # If no company type, still accept if it clearly has "insurance" and is reasonably formatted
#     if not has_company_type:
#         # Must have at least 2 words and insurance
#         words = v_clean.split()
#         if len(words) < 2:
#             return False, v, 0.0

#     return True, v_clean.upper(), 0.95


# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     """Validate policy number with strict filtering"""
#     v = value.strip()

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if _is_document_reference(v):
#         return False, v, 0.0

#     # Block if contains dates in the value
#     if DATE_RE.search(v):
#         return False, v, 0.0

#     # Block garbage patterns with specific keywords
#     if re.search(r'(date|time|page|due|liability\$|ozark)', v, re.I):
#         return False, v, 0.0
    
#     # Block state abbreviation + number patterns (like MI48007, NC27102)
#     # These are typically addresses, not policy numbers
#     if re.match(r'^[A-Z]{2}\d{5,}$', v):
#         return False, v, 0.0
    
#     # Block patterns that look like page references (5+ digits underscore pattern)
#     if re.search(r'\d{5}_\d+', v):
#         return False, v, 0.0
    
#     # Block very long numeric strings (likely document IDs)
#     digits_only = ''.join(c for c in v if c.isdigit())
#     if len(digits_only) > 18:
#         return False, v, 0.0

#     # Block partial phone numbers
#     if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
#         return False, v, 0.0

#     # Get clean version
#     v_clean = v.replace(" ", "").replace("-", "")
    
#     # Block very short values (less than 6 characters total)
#     if len(v_clean) < 6:
#         return False, v, 0.0

#     # Block ZIP codes alone
#     if ZIP_RE.fullmatch(v):
#         return False, v, 0.0

#     # Must have minimum digits (at least 5)
#     digit_count = sum(c.isdigit() for c in v)
#     if digit_count < 5:
#         return False, v, 0.0

#     # Length check
#     if not (6 <= len(v_clean) <= 30):
#         return False, v, 0.0

#     # If purely numeric, allow 6+ digits
#     if v_clean.isdigit():
#         if len(v_clean) < 6:
#             return False, v, 0.0
        
#     # If contains "PolicyNumber:" prefix, strip it
#     if ':' in v:
#         parts = v.split(':', 1)
#         label = parts[0].lower()
#         if 'policy' in label and 'number' in label:
#             v = parts[1].strip()

#     return True, v, 0.95


# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     """Validate loan number"""
#     v = value.strip()

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0

#     if _is_document_reference(v):
#         return False, v, 0.0

#     # Extract digits
#     digits = ''.join(c for c in v if c.isdigit())

#     # Loan numbers are typically 8-16 digits
#     if len(digits) < 7 or len(digits) > 16:
#         return False, v, 0.0

#     # Block obvious page reference patterns (underscore separated)
#     if re.match(r'^\d{5}_\d+', v):
#         return False, v, 0.0

#     # Block date patterns
#     if DATE_RE.search(v):
#         return False, v, 0.0
    
#     # Block very long sequences of zeros (padding patterns)
#     # But allow some zeros as they're common in real loan numbers
#     if '000000' in digits:  # 6+ consecutive zeros is suspicious
#         return False, v, 0.0
    
#     # Block if more than 60% zeros
#     zero_count = digits.count('0')
#     if len(digits) > 0 and zero_count > len(digits) * 0.6:
#         return False, v, 0.0

#     return True, digits, 0.95


# def validate_name(value: str) -> Tuple[bool, str, float]:
#     """
#     Validate person/company name - MAJOR IMPROVEMENTS
#     Block marketing slogans, product names, and document text
#     """
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if not v or len(v) < 2:
#         return False, v, 0.0

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     # Allow colons only if they're separating name parts (e.g., "Last, First")
#     if v.count(":") > 0:
#         return False, v, 0.0

#     vl = v.lower()

#     # Block marketing slogans
#     for slogan in MARKETING_SLOGANS:
#         if slogan in vl:
#             return False, v, 0.0

#     # Block product names
#     for product in PRODUCT_NAMES:
#         if product in vl:
#             return False, v, 0.0

#     # Block company names that shouldn't be insured names
#     for company in BAD_INSURED_COMPANY_NAMES:
#         if company in vl:
#             return False, v, 0.0

#     # Block bad name phrases
#     for phrase in BAD_NAME_PHRASES:
#         if phrase in vl:
#             return False, v, 0.0

#     # Block if starts with certain keywords
#     bad_starts = (
#         "policy", "coverage", "premium", "billing", "copy",
#         "page", "section", "office", "message", "declarations",
#         "effective", "expiration", "total", "subtotal", "the ",
#         "this ", "our ", "your ", "and ", "or ", "for ",
#     )
#     if any(vl.startswith(w) for w in bad_starts):
#         return False, v, 0.0

#     # Block if ends with certain patterns
#     bad_ends = (
#         " copy", " page", " info", " information", " type",
#         " period", " date", " number", " account",
#     )
#     if any(vl.endswith(w) for w in bad_ends):
#         return False, v, 0.0

#     # Block values with weird characters
#     if re.search(r'[$%&*#@!]', v):
#         return False, v, 0.0

#     # Block document reference patterns
#     if _is_document_reference(v):
#         return False, v, 0.0

#     # Block if contains phone number
#     if _is_phone_number(v):
#         return False, v, 0.0

#     # Allow digits only if entity suffix present
#     has_entity = any(w in vl for w in ["llc", "inc", "corp", "company", "trust", "ltd", "dba"])
#     if any(c.isdigit() for c in v) and not has_entity:
#         return False, v, 0.0

#     # Word count check
#     words = [w for w in v.split() if w and len(w) > 0]
#     if has_entity:
#         if not (2 <= len(words) <= 12):
#             return False, v, 0.0
#     else:
#         if not (2 <= len(words) <= 8):
#             return False, v, 0.0

#     # At least some words should be capitalized (or all caps)
#     caps = sum(1 for w in words if w and (w[0].isupper() or w.isupper()))
#     if caps < 1:
#         return False, v, 0.0

#     return True, v, 0.95


# def validate_address(value: str) -> Tuple[bool, str, float]:
#     """
#     Validate address - IMPROVED VERSION
#     Distinguish insured addresses from mortgage company addresses
#     """
#     v = _normalize_whitespace(_strip_prefixes(value))

#     if _is_section_header_value(v):
#         return False, v, 0.0

#     if v.lower() in JUNK_VALUES:
#         return False, v, 0.0

#     if not v or len(v) < 5:
#         return False, v, 0.0

#     if v.endswith(":"):
#         return False, v, 0.0

#     vl = v.lower()

#     # Block non-address content
#     bad_patterns = [
#         "policy period", "beginning", "through", "standard time",
#         "coverage", "summary", "declarations", "effective date",
#         "office use", "message", "mortgagee", "endorsement",
#         "premium", "deductible", "page ", " of ", "building type",
#         "construction", "roof", "single family", "owner occupied",
#         "ph 87", "_8s$", "$$", "##",  # OCR garbage patterns
#     ]
#     if any(kw in vl for kw in bad_patterns):
#         return False, v, 0.0

#     # Block document references
#     if _is_document_reference(v):
#         return False, v, 0.0

#     # Block mortgage company PO Box addresses
#     # (These often get captured instead of the actual insured address)
#     if _is_mortgage_company_address(v):
#         return False, v, 0.0
    
#     # Block short PO Box addresses that are likely mortgage company addresses
#     if PO_BOX_RE.search(v):
#         # If it's JUST a PO Box with no city/state, be suspicious
#         words = v.split()
#         if len(words) <= 4:  # "PO BOX 7083" - too short, likely mortgage
#             # Check if it has a city/state
#             if not re.search(r'\b[A-Z]{2}\s*\d{5}', v):
#                 return False, v, 0.0
#         return True, _normalize_address(v), 0.90

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
#         "%m-%d-%y",       # 01-15-24
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


# # ============================================================
# # TESTING / EXAMPLES
# # ============================================================

# if __name__ == "__main__":
#     # Test cases based on the errors shown
#     # Format: (field, value, should_pass)
#     test_cases = [
#         # Insured names that should be REJECTED
#         ("insured_name", "You're in good hands..", False),
#         ("insured_name", "HOMESAVER POLCY", False),
#         ("insured_name", "policy payment quickly & easily ONLINE", False),
#         ("insured_name", "POCKet eXPENSES TO yOU.", False),
#         ("insured_name", "and Policy Information", False),
#         ("insured_name", "ALLIED TRUST", False),  # Insurance company, not insured
#         ("insured_name", "PROPERIY INSURANCE CORPORAION", False),  # Malformed carrier
        
#         # Insured names that should be ACCEPTED
#         ("insured_name", "JAMES BROSTRON", True),
#         ("insured_name", "HEATHER A BABCOCK", True),
#         ("insured_name", "YOKO MATSUMOTO", True),
#         ("insured_name", "Michael K Lani, Michelle Lani", True),
#         ("insured_name", "JOHN CRENSHAW", True),
#         ("insured_name", "SARAH JONGSMA", True),
#         ("insured_name", "CHAD MEYER", True),  # Could be agent or insured - allow it
        
#         # Policy numbers that should be REJECTED
#         ("policy_number", "DueDate:10/10/20OZARK,AR72949", False),
#         ("policy_number", "100000889100011L0030", False),  # Too long, junk
#         ("policy_number", "NC27102", False),  # State + number
#         ("policy_number", "L-PersonalLiability$500,000", False),  # Coverage text
#         ("policy_number", "MI48007", False),  # State + ZIP
        
#         # Policy numbers that should be ACCEPTED
#         ("policy_number", "DPC 0076173896-1", True),
#         ("policy_number", "2004939477", True),
#         ("policy_number", "602732135 664 1", True),
#         ("policy_number", "04038598 - 1", True),
#         ("policy_number", "757051", True),
#         ("policy_number", "987 673 277", True),
#         ("policy_number", "PolicyNumber:757051", True),
        
#         # Addresses that should be REJECTED
#         ("property_address", "Page 2 of 2", False),
#         ("property_address", "1966o_8s$H PH 87 01 11", False),  # OCR garbage
#         ("property_address", "PO BOX 7083", False),  # Short PO Box without city
        
#         # Addresses that should be ACCEPTED
#         ("property_address", "3605 ROYAL DR FORT COLLINS, CO 80526-2939", True),
#         ("property_address", "908 MEADOW LN NISKAYUNA, NY 12309-6514", True),
#         ("property_address", "1682 GREEN MEADOW AVE TUSTIN CA 92780-6659", True),
#         ("property_address", "15300 SUGAR BOWL RD MYAKKA CITY, FL 34251", True),
        
#         # Loan numbers that should be REJECTED
#         ("loan_number", "00008088910000120003", False),  # Too many zeros
#         ("loan_number", "00033300333333333303", False),  # Too many zeros
#         ("loan_number", "062920201906872915019", False),  # Too long (date + reference)
        
#         # Loan numbers that should be ACCEPTED
#         ("loan_number", "0400004466", True),
#         ("loan_number", "7000654501", True),
#         ("loan_number", "1161870386", True),
#         ("loan_number", "297200525511", True),
        
#         # Carrier names that should be REJECTED
#         ("carrier_name", "NANCY BOND INSURANCE SERVICES", False),  # Agency
#         ("carrier_name", "PROPERIY INSURANCE CORPORAION", False),  # Malformed
#         ("carrier_name", "EVERETT FINANCIAL INC", False),  # Not a carrier
        
#         # Carrier names that should be ACCEPTED
#         ("carrier_name", "ALLIED PROP AND CAS INS CO", True),
#         ("carrier_name", "ADIRONDACK INSURANCE EXCHANGE", True),
#         ("carrier_name", "TRAVELERS PROPERTY CASUALTY INSURANCE COMPANY", True),
#         ("carrier_name", "CITIZENS PROPERTY INSURANCE CORPORATION", True),
#         ("carrier_name", "ALLSTATE INSURANCE COMPANY", True),
#     ]
    
#     validators = {
#         "insured_name": validate_name,
#         "policy_number": validate_policy_number,
#         "property_address": validate_address,
#         "loan_number": validate_loan_number,
#         "carrier_name": validate_carrier,
#     }
    
#     print("=" * 70)
#     print("VALIDATION TEST RESULTS")
#     print("=" * 70)
    
#     passed = 0
#     failed = 0
    
#     for field, value, should_pass in test_cases:
#         validator = validators[field]
#         ok, norm_value, score = validator(value)
        
#         if ok == should_pass:
#             status = "✓ PASS"
#             passed += 1
#         else:
#             status = "✗ FAIL"
#             failed += 1
#             expected = "ACCEPT" if should_pass else "REJECT"
#             actual = "ACCEPTED" if ok else "REJECTED"
#             status += f" (expected {expected}, got {actual})"
        
#         print(f"{status} | {field}: {value[:50]}")
    
#     print("=" * 70)
#     print(f"Results: {passed} passed, {failed} failed")

"""
Stage 4 – Validation & Arbitration Agent (IMPROVED VERSION)
============================================================
Major improvements to address common extraction errors:

1. INSURED NAME VALIDATION:
   - Block marketing slogans ("You're in good hands", "policy payment quickly & easily ONLINE")
   - Block product names ("HOMESAVER POLCY", "PROPERTY INSURANCE CORPORAION")
   - Block document headers and structural text
   - Require proper name patterns

2. POLICY NUMBER VALIDATION:
   - Block page reference numbers and document codes
   - Block phone numbers more aggressively
   - Validate alphanumeric patterns correctly

3. ADDRESS VALIDATION:
   - Distinguish between insured addresses and mortgage company addresses
   - Block PO Box addresses that belong to mortgage companies (Troy MI pattern)
   - Block document reference text disguised as addresses

4. LOAN NUMBER VALIDATION:
   - Block page numbers and document reference codes
   - Require proper loan number patterns

5. CARRIER NAME VALIDATION:
   - Block truncated or malformed carrier names
   - Block product names being captured as carriers
"""

import re
from datetime import datetime
from typing import Dict, Tuple, Set


# ============================================================
# CONFIDENCE FLOORS
# ============================================================

CONFIDENCE_FLOORS = {
    "carrier_name": 0.80,
    "policy_number": 0.80,
    "loan_number": 0.80,
    "insured_name": 0.75,
    "property_address": 0.75,
    "mailing_address": 0.70,
    "mortgage_company": 0.75,
    "total_premium": 0.70,
    "deductible": 0.70,
    "effective_date": 0.75,
    "expiration_date": 0.75,
    "agent_phone": 0.75,
    "agent_name": 0.70,
}

DEFAULT_FLOOR = 0.65


# ============================================================
# FIELD REQUIREMENTS BY DOCUMENT + POLICY TYPE
# ============================================================

# Field requirements by document type + policy type combination
# This implements business rules for which fields are allowed
# for specific document+policy combinations
#
# INV fields: core 3 + invoice-specific + context fields
_INV_FIELDS = [
    "carrier_name", "insured_name", "policy_number",
    "balance_due", "issue_date", "remit_info",
    "effective_date", "expiration_date",
    "property_address", "loan_number", "mortgage_company",
    "total_premium",
]

ALLOWED_FIELDS_BY_DOC_POLICY = {
    # Invoice + Policy Type combinations
    ("INV", "HAZ"): _INV_FIELDS,
    ("INV", "HO"): _INV_FIELDS,
    ("INV", "HO3"): _INV_FIELDS,
    ("INV", "HO6"): _INV_FIELDS,
    ("INV", "FIR"): _INV_FIELDS,
    ("INV", "FLD"): _INV_FIELDS,
    ("INV", "WND"): _INV_FIELDS,
    ("INV", "DP3"): _INV_FIELDS,
    ("INV", "AUTO"): _INV_FIELDS,
    ("INV", "LL"): _INV_FIELDS,
    ("INV", "UO"): _INV_FIELDS,
    ("INV", "ERQ"): _INV_FIELDS,
    # For unknown policy types with INV, still allow all INV fields
    ("INV", "UNK"): _INV_FIELDS,
    
    # Cancellation subtypes with INV
    ("INV", "BREQ"): _INV_FIELDS,
    ("INV", "NPAY"): _INV_FIELDS,
    ("INV", "NRNW"): _INV_FIELDS,
    ("INV", "UNWR"): _INV_FIELDS,
    ("INV", "CEL"): _INV_FIELDS,
    
    # Add other combinations as needed per business rules
    # If not specified, allow all fields (default behavior)
}


# ============================================================
# BLOCK LISTS - EXPANDED
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
    "rating information", "additional coverages", "discounts",
}

JUNK_VALUES = {
    "type", "interest", "policy", "coverage", "summary",
    "n/a", "none", "see attached", "continued", "page",
    "na", "tbd", "pending", "unknown", "included", "see policy",
}

# Marketing slogans and taglines to block as names
MARKETING_SLOGANS = {
    "you're in good hands",
    "you're in good hands.",
    "youre in good hands",
    "on your side",
    "like a good neighbor",
    "we're all in this together",
    "nationwide is on your side",
    "for all that matters",
    "the promise",
    "keep the promise",
}

# Phrases that indicate document structure, not actual names
BAD_NAME_PHRASES = {
    "policy payment",
    "quickly & easily",
    "quickly and easily",
    "online",
    "pocket expenses",
    "out of pocket",
    "out-of-pocket",
    "and policy information",
    "policy information",
    "page 1 of",
    "page 2 of",
    "page 3 of",
    "mortgagee copy",
    "declarations page",
    "your policy",
    "our policy",
    "this policy",
    "policy conditions",
    "policy type",
    "policy period",
    "coverage detail",
    "coverage info",
    "premium info",
    "building type",
    "single family",
    "construction type",
    "roof-wall connection",
    "roof connection",
    "roof deck",
    "additional insured",
    "first named insured",
    "named insured:",
    "location id",
    "location of",
    "described location",
    "effective date",
    "expiration date",
    "endorsement",
    "deductible",
    "important notice",
    "special provisions",
}

# Product names that should not be captured as insured names
PRODUCT_NAMES: Set[str] = {
    "homesaver polcy",
    "homesaver policy",
    "homeowners policy",
    "dwelling policy",
    "mobilehome policy",
    "mobilehomeowners",
    "special form policy",
    "wind only policy",
    "condominium policy",
    "condominium owners",
    "rental unit owners",
    "ultrapack plus",
    "encompassone",
    "encompass one",
}

# Company names that should NOT be captured as insured names
# These are often mortgage companies, agents, or other entities
BAD_INSURED_COMPANY_NAMES: Set[str] = {
    "allied trust",
    "aegis",
    "aegis security",
    "aegis security insurance",
    "a egis",  # OCR error variant
    "properiy insurance",  # Typo
    "property insurance",
    "insurance corporation",
    "insurance company",
    "insurance exchange",
    "mortgage company",
    "mortgage corp",
    "financial inc",
    "lending llc",
    "bank na",
}

# Truncated/malformed carrier names to reject
BAD_CARRIER_PATTERNS = {
    "properiy insurance",  # Typo
    "property insurance corporaion",  # Missing T
    "property insurance corporaiion",  # Double I
    "insurance exchange*",  # Has asterisk
    "insurance company*",
    "insurance agency",  # Agency, not carrier
    "insurance services",  # Services, not carrier
    "insurance center",
    "everett financial",  # Not a carrier, it's a lender
    "broker solutions",
    "nancy bond insurance",  # Agent, not carrier
    "geico ins agency",
    "allstate mortgage",
}

# Common mortgage company PO Box addresses (Troy MI is most common)
MORTGAGE_PO_BOX_PATTERNS = [
    r"p\.?o\.?\s*box\s*\d+.*troy.*mi",
    r"p\.?o\.?\s*box\s*\d+.*48007",  # Troy MI ZIP
    r"p\.?o\.?\s*box\s*\d+.*miami.*fl.*33197",
    r"p\.?o\.?\s*box\s*\d+.*dallas.*tx.*75266",
]

PREFIX_STRIP = [
    "coverage detail for",
    "policy effective date is",
    "effective date is",
    "your policy effective date is",
    "your policy effective date:",
    "location:",
    "address:",
    "name:",
    "insured:",
    "named insured:",
    "property:",
    "mailing:",
    "first named insured:",
    "policyholder(s)",
    "policyholder:",
]


# ============================================================
# FIELD FILTERING BY DOCUMENT + POLICY TYPE
# ============================================================

def filter_allowed_fields(
    validated: Dict,
    doc_type: str,
    policy_type: str
) -> Dict:
    """
    Filter extracted fields to only those allowed for the 
    specific document_type + policy_type combination.
    
    This implements business rules that restrict which fields
    should be extracted for certain document+policy combinations.
    For example, INV+HAZ documents should only extract 3 fields:
    carrier_name, insured_name, and policy_number.
    
    Args:
        validated: Dictionary of validated fields
        doc_type: Document type (INV, RNW, CAN, DOI, COI, BIN, RNS, OTH, UNK)
        policy_type: Policy type (HAZ, HO, FIR, FLD, BREQ, NPAY, etc.)
    
    Returns:
        Filtered dictionary with only allowed fields
    """
    # Check if there's a specific allowlist for this combination
    key = (doc_type, policy_type)
    allowed = ALLOWED_FIELDS_BY_DOC_POLICY.get(key)
    
    if allowed is None:
        # No restriction - return all fields
        return validated
    
    # Filter to only allowed fields
    filtered = {
        field: data 
        for field, data in validated.items() 
        if field in allowed
    }
    
    # Add metadata about filtering
    if len(filtered) < len(validated):
        removed_fields = set(validated.keys()) - set(filtered.keys())
        # Could log this for debugging: f"Filtered out {removed_fields} for {doc_type}+{policy_type}"
    
    return filtered


# ============================================================
# REGEX PATTERNS
# ============================================================

PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b')
PO_BOX_RE = re.compile(r'p\.?o\.?\s*box', re.I)

STREET_TYPES = [
    'street', 'st', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd',
    'lane', 'ln', 'drive', 'dr', 'court', 'ct', 'circle', 'cir',
    'way', 'place', 'pl', 'terrace', 'ter', 'highway', 'hwy',
    'parkway', 'pkwy', 'ridge'
]


# ============================================================
# HELPERS
# ============================================================

def _is_section_header_value(value: str) -> bool:
    """Check if value is a section header, not actual data"""
    if not value:
        return False

    v = value.lower().strip()

    if v in SECTION_TITLES:
        return True

    for title in SECTION_TITLES:
        if v.startswith(title) or title in v:
            return True

    # Ends with colon = likely header
    if v.endswith(":") and len(v.split()) <= 5:
        return True

    # All uppercase multi-word WITHOUT being a typical name pattern
    # Names are typically 2-4 words, headers are typically longer or contain structural words
    if value.isupper() and len(value.split()) >= 3:
        words = value.split()
        v_lower = value.lower()
        
        # If it contains "insurance", "company", "corporation", etc., it's likely a company name
        # not a header
        company_indicators = {'insurance', 'ins', 'company', 'co', 'corporation', 'corp', 'exchange', 
                             'mutual', 'group', 'inc', 'llc', 'ltd'}
        if any(ind in v_lower for ind in company_indicators):
            return False  # Likely a company name, not a header
        
        # Check if it looks like a header vs a name
        # Headers often contain words like: PAGE, SECTION, COVERAGE, DECLARATIONS, NOTICE, etc.
        header_words = {'PAGE', 'SECTION', 'COVERAGE', 'DECLARATIONS', 'NOTICE', 
                       'INFORMATION', 'SUMMARY', 'DETAILS', 'SCHEDULE', 'ENDORSEMENT',
                       'CONDITIONS', 'PROVISIONS', 'LIMITS', 'POLICY', 'PREMIUM',
                       'TOTAL', 'SUBTOTAL', 'AMOUNT', 'DATE', 'NUMBER', 'TYPE'}
        if any(w.upper() in header_words for w in words):
            return True
        # If it's a short all-caps phrase without header words, it might be a name
        # Names: "JOHN SMITH", "HEATHER A BABCOCK", "MICHAEL K LANI"
        # Allow up to 4 words if they don't contain header keywords
        if len(words) <= 4:
            return False  # Likely a name
        # 5+ words all caps without digits and without company indicators = probably a header
        if not any(c.isdigit() for c in value):
            return True

    return False


def _strip_prefixes(value: str) -> str:
    """Remove common prefixes from values"""
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

    replacements = {
        r'\bSt\b': 'Street',
        r'\bAve\b': 'Avenue',
        r'\bRd\b': 'Road',
        r'\bBlvd\b': 'Boulevard',
        r'\bDr\b': 'Drive',
        r'\bLn\b': 'Lane',
        r'\bCt\b': 'Court',
        r'\bCir\b': 'Circle',
    }

    for pattern, replacement in replacements.items():
        v = re.sub(pattern, replacement, v, flags=re.I)

    return v


def _normalize_phone(value: str) -> str:
    """Format phone number consistently"""
    digits = ''.join(c for c in value if c.isdigit())

    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return value


def _is_phone_number(value: str) -> bool:
    """Check if value is a phone number"""
    digits = ''.join(c for c in value if c.isdigit())
    
    # Exactly 10 digits = phone
    if len(digits) == 10:
        return True
    
    # 11 digits starting with 1 = phone with country code
    if len(digits) == 11 and digits.startswith('1'):
        return True
    
    # 7 digits = local phone
    if len(digits) == 7:
        return True
    
    # Has phone formatting
    if PHONE_RE.search(value):
        return True
    
    return False


def _is_document_reference(value: str) -> bool:
    """Check if value is a document reference code, not actual data"""
    v = value.lower().strip()
    
    # Page references
    if re.match(r'^\d+_\d+_\d+$', v):  # e.g., "19312_243570_11"
        return True
    
    if re.match(r'^page\s*\d+', v, re.I):
        return True
    
    # Document codes with underscores
    if '_' in v and sum(c.isdigit() for c in v) > len(v) * 0.6:
        return True
    
    return False


def _is_mortgage_company_address(value: str) -> bool:
    """Check if address belongs to a mortgage company, not the insured"""
    v = value.lower()
    
    for pattern in MORTGAGE_PO_BOX_PATTERNS:
        if re.search(pattern, v, re.I):
            return True
    
    # Generic mortgage PO Box indicators
    if 'troy' in v and 'mi' in v and 'box' in v:
        return True
    
    if '48007' in v:  # Troy MI ZIP
        return True
    
    return False


# ============================================================
# VALIDATORS
# ============================================================

def validate_carrier(value: str) -> Tuple[bool, str, float]:
    """Validate carrier name"""
    v = _normalize_whitespace(value)

    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if len(v) < 5:
        return False, v, 0.0

    # Clean up common OCR artifacts
    v_clean = v.replace('*', '').replace('/', '').strip()
    vl_clean = v_clean.lower()

    # Block known bad carrier patterns (must check before positive matches)
    for bad in BAD_CARRIER_PATTERNS:
        if bad in vl_clean:
            return False, v, 0.0

    # Block agencies/agents/services FIRST (before insurance check)
    if any(w in vl_clean for w in ('agency', 'agent', 'services', 'producer')):
        return False, v, 0.0

    # Must contain "insurance" (or "ins" abbreviation)
    # Check for various patterns: "insurance", " ins ", " ins.", ends with " ins"
    has_insurance = ('insurance' in vl_clean or 
                     ' ins ' in vl_clean or 
                     vl_clean.endswith(' ins') or 
                     ' ins.' in vl_clean or
                     ' ins co' in vl_clean or
                     vl_clean.endswith(' ins co'))
    if not has_insurance:
        return False, v, 0.0

    # Company type indicator (relaxed - many valid variations)
    company_types = ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')
    has_company_type = any(w in vl_clean for w in company_types)
    
    # If no company type, still accept if it clearly has "insurance" and is reasonably formatted
    if not has_company_type:
        # Must have at least 2 words and insurance
        words = v_clean.split()
        if len(words) < 2:
            return False, v, 0.0

    return True, v_clean.upper(), 0.95


def validate_policy_number(value: str) -> Tuple[bool, str, float]:
    """Validate policy number with strict filtering"""
    v = value.strip()

    if _is_section_header_value(v):
        return False, v, 0.0

    if _is_document_reference(v):
        return False, v, 0.0

    # Block if contains dates in the value
    if DATE_RE.search(v):
        return False, v, 0.0

    # Block garbage patterns with specific keywords
    if re.search(r'(date|time|page|due|liability\$|ozark)', v, re.I):
        return False, v, 0.0
    
    # Block state abbreviation + number patterns (like MI48007, NC27102)
    # These are typically addresses, not policy numbers
    if re.match(r'^[A-Z]{2}\d{5,}$', v):
        return False, v, 0.0
    
    # Block patterns that look like page references (5+ digits underscore pattern)
    if re.search(r'\d{5}_\d+', v):
        return False, v, 0.0
    
    # Block very long numeric strings (likely document IDs)
    digits_only = ''.join(c for c in v if c.isdigit())
    if len(digits_only) > 18:
        return False, v, 0.0

    # Block partial phone numbers
    if re.fullmatch(r"\d{3}[-.\s]?\d{4}", v):
        return False, v, 0.0

    # Get clean version
    v_clean = v.replace(" ", "").replace("-", "")
    
    # Block very short values (less than 6 characters total)
    if len(v_clean) < 6:
        return False, v, 0.0

    # Block ZIP codes alone
    if ZIP_RE.fullmatch(v):
        return False, v, 0.0

    # Must have minimum digits (at least 5)
    digit_count = sum(c.isdigit() for c in v)
    if digit_count < 5:
        return False, v, 0.0

    # Length check
    if not (6 <= len(v_clean) <= 30):
        return False, v, 0.0

    # If purely numeric, allow 6+ digits
    if v_clean.isdigit():
        if len(v_clean) < 6:
            return False, v, 0.0
        
    # If contains "PolicyNumber:" prefix, strip it
    if ':' in v:
        parts = v.split(':', 1)
        label = parts[0].lower()
        if 'policy' in label and 'number' in label:
            v = parts[1].strip()

    return True, v, 0.95


def validate_loan_number(value: str) -> Tuple[bool, str, float]:
    """Validate loan number"""
    v = value.strip()

    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if _is_document_reference(v):
        return False, v, 0.0

    # Extract digits
    digits = ''.join(c for c in v if c.isdigit())

    # Loan numbers are typically 8-16 digits
    if len(digits) < 7 or len(digits) > 16:
        return False, v, 0.0

    # Block obvious page reference patterns (underscore separated)
    if re.match(r'^\d{5}_\d+', v):
        return False, v, 0.0

    # Block date patterns
    if DATE_RE.search(v):
        return False, v, 0.0
    
    # Block very long sequences of zeros (padding patterns)
    # But allow some zeros as they're common in real loan numbers
    if '000000' in digits:  # 6+ consecutive zeros is suspicious
        return False, v, 0.0
    
    # Block if more than 60% zeros
    zero_count = digits.count('0')
    if len(digits) > 0 and zero_count > len(digits) * 0.6:
        return False, v, 0.0

    return True, digits, 0.95


def validate_name(value: str) -> Tuple[bool, str, float]:
    """
    Validate person/company name - MAJOR IMPROVEMENTS
    Block marketing slogans, product names, and document text
    """
    v = _normalize_whitespace(_strip_prefixes(value))

    if not v or len(v) < 2:
        return False, v, 0.0

    if _is_section_header_value(v):
        return False, v, 0.0

    # Allow colons only if they're separating name parts (e.g., "Last, First")
    if v.count(":") > 0:
        return False, v, 0.0

    vl = v.lower()

    # Block marketing slogans
    for slogan in MARKETING_SLOGANS:
        if slogan in vl:
            return False, v, 0.0

    # Block product names
    for product in PRODUCT_NAMES:
        if product in vl:
            return False, v, 0.0

    # Block company names that shouldn't be insured names
    for company in BAD_INSURED_COMPANY_NAMES:
        if company in vl:
            return False, v, 0.0
    
    # Block known carrier names that appear as text (not actual insured names)
    # This prevents carriers from being extracted as insured names
    CARRIER_INDICATORS = {
        "aegis", "allstate", "state farm", "geico", 
        "progressive", "travelers", "liberty mutual", "farmers",
        "citizens", "universal", "federated", "nationwide",
        "american family", "usaa", "auto-owners", "erie",
        "encompass", "safeco", "hanover", "hartford",
        "insurance company", "insurance co", 
        "insurance exchange", "assurance company",
        "property insurance", "casualty insurance",
    }
    # Check if the entire value is a carrier name
    if any(indicator in vl for indicator in CARRIER_INDICATORS):
        # Allow if it's clearly a person's name that happens to contain a word
        # (e.g., "John Progressive" would be allowed, but "Aegis" alone would not)
        words = vl.split()
        # If only 1-2 words and matches carrier pattern, reject
        if len(words) <= 2:
            return False, v, 0.0
        # If 3+ words but starts/ends with carrier indicator, likely still a carrier
        if words[0] in CARRIER_INDICATORS or words[-1] in CARRIER_INDICATORS:
            return False, v, 0.0

    # Block bad name phrases
    for phrase in BAD_NAME_PHRASES:
        if phrase in vl:
            return False, v, 0.0

    # Block if starts with certain keywords
    bad_starts = (
        "policy", "coverage", "premium", "billing", "copy",
        "page", "section", "office", "message", "declarations",
        "effective", "expiration", "total", "subtotal", "the ",
        "this ", "our ", "your ", "and ", "or ", "for ",
    )
    if any(vl.startswith(w) for w in bad_starts):
        return False, v, 0.0

    # Block if ends with certain patterns
    bad_ends = (
        " copy", " page", " info", " information", " type",
        " period", " date", " number", " account",
    )
    if any(vl.endswith(w) for w in bad_ends):
        return False, v, 0.0

    # Block values with weird characters
    if re.search(r'[$%&*#@!]', v):
        return False, v, 0.0

    # Block document reference patterns
    if _is_document_reference(v):
        return False, v, 0.0

    # Block if contains phone number
    if _is_phone_number(v):
        return False, v, 0.0

    # Allow digits only if entity suffix present
    has_entity = any(w in vl for w in ["llc", "inc", "corp", "company", "trust", "ltd", "dba"])
    if any(c.isdigit() for c in v) and not has_entity:
        return False, v, 0.0

    # Word count check
    words = [w for w in v.split() if w and len(w) > 0]
    if has_entity:
        if not (2 <= len(words) <= 12):
            return False, v, 0.0
    else:
        if not (2 <= len(words) <= 8):
            return False, v, 0.0

    # At least some words should be capitalized (or all caps)
    caps = sum(1 for w in words if w and (w[0].isupper() or w.isupper()))
    if caps < 1:
        return False, v, 0.0

    return True, v, 0.95


def validate_address(value: str) -> Tuple[bool, str, float]:
    """
    Validate address - IMPROVED VERSION
    Distinguish insured addresses from mortgage company addresses
    """
    v = _normalize_whitespace(_strip_prefixes(value))

    if _is_section_header_value(v):
        return False, v, 0.0

    if v.lower() in JUNK_VALUES:
        return False, v, 0.0

    if not v or len(v) < 5:
        return False, v, 0.0

    if v.endswith(":"):
        return False, v, 0.0

    vl = v.lower()

    # Block non-address content
    bad_patterns = [
        "policy period", "beginning", "through", "standard time",
        "coverage", "summary", "declarations", "effective date",
        "office use", "message", "mortgagee", "endorsement",
        "premium", "deductible", "page ", " of ", "building type",
        "construction", "roof", "single family", "owner occupied",
        "ph 87", "_8s$", "$$", "##",  # OCR garbage patterns
    ]
    if any(kw in vl for kw in bad_patterns):
        return False, v, 0.0

    # Block document references
    if _is_document_reference(v):
        return False, v, 0.0

    # Block mortgage company PO Box addresses
    # (These often get captured instead of the actual insured address)
    if _is_mortgage_company_address(v):
        return False, v, 0.0
    
    # Block short PO Box addresses that are likely mortgage company addresses
    if PO_BOX_RE.search(v):
        # If it's JUST a PO Box with no city/state, be suspicious
        words = v.split()
        if len(words) <= 4:  # "PO BOX 7083" - too short, likely mortgage
            # Check if it has a city/state
            if not re.search(r'\b[A-Z]{2}\s*\d{5}', v):
                return False, v, 0.0
        return True, _normalize_address(v), 0.90

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
        "%m-%d-%y",       # 01-15-24
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
    doc_type: str = "UNK",
    policy_type: str = "UNK",
) -> Tuple[Dict, float]:
    """
    Main validation entry point
    Validates and filters extracted fields based on document + policy type
    
    Args:
        merged_fields: Merged fields from all extraction stages
        ocr_confidence: OCR confidence score
        stage_breakdown: Breakdown of fields by stage
        doc_type: Document type (INV, RNW, CAN, DOI, COI, BIN, RNS, OTH, UNK)
        policy_type: Policy type (HAZ, HO, FIR, FLD, BREQ, NPAY, etc.)
    
    Returns:
        Tuple of (validated_fields, final_confidence)
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
        "cancellation_date": validate_date,
        "total_premium": validate_money,
        "balance_due": validate_money,
        "issue_date": validate_date,
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
    
    # Apply field filtering based on document + policy type business rules
    # This restricts which fields are allowed for certain doc+policy combinations
    validated = filter_allowed_fields(validated, doc_type, policy_type)

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


# ============================================================
# TESTING / EXAMPLES
# ============================================================

if __name__ == "__main__":
    # Test cases based on the errors shown
    # Format: (field, value, should_pass)
    test_cases = [
        # Insured names that should be REJECTED
        ("insured_name", "You're in good hands..", False),
        ("insured_name", "HOMESAVER POLCY", False),
        ("insured_name", "policy payment quickly & easily ONLINE", False),
        ("insured_name", "POCKet eXPENSES TO yOU.", False),
        ("insured_name", "and Policy Information", False),
        ("insured_name", "ALLIED TRUST", False),  # Insurance company, not insured
        ("insured_name", "PROPERIY INSURANCE CORPORAION", False),  # Malformed carrier
        
        # Insured names that should be ACCEPTED
        ("insured_name", "JAMES BROSTRON", True),
        ("insured_name", "HEATHER A BABCOCK", True),
        ("insured_name", "YOKO MATSUMOTO", True),
        ("insured_name", "Michael K Lani, Michelle Lani", True),
        ("insured_name", "JOHN CRENSHAW", True),
        ("insured_name", "SARAH JONGSMA", True),
        ("insured_name", "CHAD MEYER", True),  # Could be agent or insured - allow it
        
        # Policy numbers that should be REJECTED
        ("policy_number", "DueDate:10/10/20OZARK,AR72949", False),
        ("policy_number", "100000889100011L0030", False),  # Too long, junk
        ("policy_number", "NC27102", False),  # State + number
        ("policy_number", "L-PersonalLiability$500,000", False),  # Coverage text
        ("policy_number", "MI48007", False),  # State + ZIP
        
        # Policy numbers that should be ACCEPTED
        ("policy_number", "DPC 0076173896-1", True),
        ("policy_number", "2004939477", True),
        ("policy_number", "602732135 664 1", True),
        ("policy_number", "04038598 - 1", True),
        ("policy_number", "757051", True),
        ("policy_number", "987 673 277", True),
        ("policy_number", "PolicyNumber:757051", True),
        
        # Addresses that should be REJECTED
        ("property_address", "Page 2 of 2", False),
        ("property_address", "1966o_8s$H PH 87 01 11", False),  # OCR garbage
        ("property_address", "PO BOX 7083", False),  # Short PO Box without city
        
        # Addresses that should be ACCEPTED
        ("property_address", "3605 ROYAL DR FORT COLLINS, CO 80526-2939", True),
        ("property_address", "908 MEADOW LN NISKAYUNA, NY 12309-6514", True),
        ("property_address", "1682 GREEN MEADOW AVE TUSTIN CA 92780-6659", True),
        ("property_address", "15300 SUGAR BOWL RD MYAKKA CITY, FL 34251", True),
        
        # Loan numbers that should be REJECTED
        ("loan_number", "00008088910000120003", False),  # Too many zeros
        ("loan_number", "00033300333333333303", False),  # Too many zeros
        ("loan_number", "062920201906872915019", False),  # Too long (date + reference)
        
        # Loan numbers that should be ACCEPTED
        ("loan_number", "0400004466", True),
        ("loan_number", "7000654501", True),
        ("loan_number", "1161870386", True),
        ("loan_number", "297200525511", True),
        
        # Carrier names that should be REJECTED
        ("carrier_name", "NANCY BOND INSURANCE SERVICES", False),  # Agency
        ("carrier_name", "PROPERIY INSURANCE CORPORAION", False),  # Malformed
        ("carrier_name", "EVERETT FINANCIAL INC", False),  # Not a carrier
        
        # Carrier names that should be ACCEPTED
        ("carrier_name", "ALLIED PROP AND CAS INS CO", True),
        ("carrier_name", "ADIRONDACK INSURANCE EXCHANGE", True),
        ("carrier_name", "TRAVELERS PROPERTY CASUALTY INSURANCE COMPANY", True),
        ("carrier_name", "CITIZENS PROPERTY INSURANCE CORPORATION", True),
        ("carrier_name", "ALLSTATE INSURANCE COMPANY", True),
    ]
    
    validators = {
        "insured_name": validate_name,
        "policy_number": validate_policy_number,
        "property_address": validate_address,
        "loan_number": validate_loan_number,
        "carrier_name": validate_carrier,
    }
    
    print("=" * 70)
    print("VALIDATION TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for field, value, should_pass in test_cases:
        validator = validators[field]
        ok, norm_value, score = validator(value)
        
        if ok == should_pass:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
            expected = "ACCEPT" if should_pass else "REJECT"
            actual = "ACCEPTED" if ok else "REJECTED"
            status += f" (expected {expected}, got {actual})"
        
        print(f"{status} | {field}: {value[:50]}")
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")