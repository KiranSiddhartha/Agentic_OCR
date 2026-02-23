# # stage1_deterministic_agent.py
# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
# IMPROVED VERSION - Fixes for:
# 1. Insured name extraction (blocking mortgagee terms, product names)
# 2. Carrier name extraction (multi-line support)
# 3. Loan number extraction (blocking document references)
# 4. Policy number extraction (better patterns)
# """
# import re
# from typing import Dict, List, Set, Tuple
# from enum import Enum, auto


# # ============================================================
# # ROLES
# # ============================================================

# class Role(Enum):
#     NONE = auto()
#     POLICY_HEADER = auto()
#     INSURED_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MAILING_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()
#     CARRIER_BLOCK = auto()
#     PRODUCER_BLOCK = auto()  # NEW: Skip names in producer/agent sections


# # ============================================================
# # REGEX PATTERNS
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# DATE_WRITTEN_RE = re.compile(
#     r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
#     re.I
# )
# # Abbreviated month names: NOV 09 2021, DEC 1 2022, etc.
# DATE_ABBREV_RE = re.compile(
#     r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
#     re.I
# )
# PO_BOX_RE = re.compile(r"p\.?o\.?\s*box", re.I)
# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge|pl|place"
#     r")\b",
#     re.I
# )

# # Policy number patterns - multiple variants
# POLICY_REGEX_VARIANTS = [
#     re.compile(r"^[A-Z]{2,4}[-\s]?\d{7,12}[-\s]?\d{0,2}$", re.I),  # DPC0076173896-1
#     re.compile(r"^\d{9,12}$"),  # 2004939477
#     re.compile(r"^\d{9}\s*\d{3}\s*\d{1}$"),  # 602732135 664 1
#     re.compile(r"^[A-Z]{2,4}\d{1,2}[-]?\d{9,12}$", re.I),  # OKH3-109194373
#     re.compile(r"^\d{8,12}[-\s]?\d{1,2}$"),  # 04038598 - 1
#     re.compile(r"^\d{2}-[A-Z]{2}-[A-Z]\d{3}-\d$", re.I),  # 81-BE-N065-5 (State Farm)
#     re.compile(r"^\d{2}-[A-Z]{2,4}-[A-Z0-9]{3,8}$", re.I),  # Generic NN-XX-XXXXX
#     # --- INS observation batch additions (Section 2) ---
#     # Spaced numeric: "821 736 168", "063 078 674"
#     re.compile(r"^\d{3}\s\d{3}\s\d{3}$"),
#     # Dashed numeric with space: "02050414 - 5"
#     re.compile(r"^\d{8}\s*-\s*\d{1,2}$"),
#     # Hyphenated alphanumeric: "TX-HOV-00032479-01", "60-04077225-2019"
#     re.compile(r"^[A-Z]{2}-[A-Z]{2,4}-\d{5,}-\d{1,2}$", re.I),
#     re.compile(r"^\d{2}-\d{8,}-\d{4}$"),
#     # Alpha prefix with space: "ACP BPH 7885310416", "LAH0195988"
#     re.compile(r"^[A-Z]{2,4}\s?[A-Z]{0,4}\s?\d{7,12}$", re.I),
#     # Alpha suffix: "60092029BP"
#     re.compile(r"^\d{8,10}[A-Z]{2}$", re.I),
#     # Commercial style: "34 X42393-01"
#     re.compile(r"^\d{2}\s[A-Z]\d{5,}-\d{1,2}$", re.I),
#     # Flood style: "99-047002652-2020"
#     re.compile(r"^\d{2}-\d{9,}-\d{4}$"),
# ]

# STATE_ABBREV = {
#     "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
#     "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
#     "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
#     "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
#     "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
#     "DC", "PR", "VI"
# }


# # ============================================================
# # LABELS / TRIGGERS
# # ============================================================

# POLICY_LABELS = {
#     "policy number", "policy no", "policy #",
#     "your policy number", "policynumber",
#     "dwelling policy number",
#     "account number", "your account number","policy id",
#     "policy certificate number",
#     "certificate number",
#     "master policy no", 
# }

# INSURED_LABELS = {
#     "insured", "named insured",
#     "insured name", "insured name and address",
#     "insured mailing", "insured mailing name",
#     "insured mailing name and address",
#     "policyholder", "policy holder",
#     "policyholder(s)",  # ADDED for "Policyholder(s) TIM RASK"
#     "policyholders",
#     "policyholder/insured", "policyholder/named insured",
#     "first named insured",
#     "named insured and address",
#     "name and address of insured",  # ADDED
# }

# # CRITICAL: Terms that should NOT be captured as insured names
# BAD_INSURED_TERMS = {
#     # Mortgagee-related (most common error)
#     "mortgagee", "first mortgagee", "second mortgagee", "third mortgagee",
#     "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
#     "loss payee", "lienholder", "lender",
#     "isaoa", "atima", "isaoa atima", "isaoa/atima",
#     "lien holder", "1st mortgagee copy",
    
#     # Product names
#     "homesaver policy", "homesaver polcy", "homeowners policy",
#     "dwelling policy", "special form", "wind only policy",
#     "ultrapack plus", "mobilehome policy", "condominium owners",
#     "mobilehome", "house & home",
    
#     # Insurance company fragments
#     "insurance exchange", "insurance company", "insurance group",
#     "insurance corp", "insurance mutual",
    
#     # Document structure
#     "policy period", "policy type", "coverage",
#     "endorsement", "declarations", "summary",
#     "premium", "deductible", "page", "continued",
#     "information as of",
    
#     # Agencies/agents/producers (CRITICAL - fixes Michael Ames issue)
#     "agency", "agent", "services", "producer",
#     "goosehead", "goosehead insurance",
    
#     # Service centers (CRITICAL - fixes Mortgagee Relations Center)
#     "relations center", "mortgagee relations", "lender relations",
#     "customer service", "service center",
#     "claims center", "billing center",
    
#     # Website/online instructions (CRITICAL - fixes aegisinsurance.com)
#     "website", ".com", "online", "go to", "simply go",
#     "click here", "select", "menu bar", "policyholders",
#     "make a payment", "pay online",
    
#     # Marketing slogans (CRITICAL - fixes "You're in good hands")
#     "you're in good hands", "good hands",
#     "like a good neighbor", "on your side",
#     "we know a thing or two", "because we've seen",
    
#     # Other noise
#     "other interest", "interested parties", "certificate holder",
#     "office use", "message", "messages",
#     "risk management", "department",
#     "third party notice", "notice of",
# }

# BAD_NAME_PHRASES = {
#     # Sections
#     "coverage", "endorsement", "deductible",
#     "policy conditions", "forms and endorsements",
#     "policy period", "premium", "billing",
#     "invoice", "notice", "summary", "schedule",
#     "page", "continued", "section",
    
#     # Mortgagee related (CRITICAL)
#     "mortgagee", "loss payee", "lienholder",
#     "first mortgagee", "second mortgagee",
#     "isaoa", "atima", "lien holder",
    
#     # Products / carriers
#     "homeowners", "dwelling", "ultrapack",
#     "insurance company", "insurance exchange",
#     "insurance group", "homesaver",
#     "mobilehome",
    
#     # Agencies/producers (CRITICAL - fixes Michael Ames)
#     "agency", "agent", "services", "producer",
#     "goosehead", "insurance agency",
    
#     # Service centers (CRITICAL - fixes Mortgagee Relations Center)
#     "relations center", "mortgagee relations", "lender relations",
#     "customer service", "service center",
#     "claims center", "billing center",
#     "risk management", "department",
    
#     # Website/online (CRITICAL - fixes aegisinsurance.com)
#     "website", ".com", "online", "go to", "simply go",
#     "click here", "select", "menu bar",
#     "make a payment", "pay online",
    
#     # Marketing slogans (CRITICAL - fixes "You're in good hands")
#     "you're in good hands", "good hands",
#     "like a good neighbor", "on your side",
#     "we know a thing or two",
    
#     # Noise / instructions
#     "detach this", "return with",
#     "third party notice", "notice of",
    
#     # Other
#     "your insurer", "insurer:", "office use",
#     "information as of", "page 1 of", "page 2 of",
# }

# PROPERTY_TRIGGERS = {
#     "property address", "property insured",
#     "location of insured property", "residence premises",
#     "described location", "risk location",
#     "insured location", "location of property",
#     "premises address", "located at",
#     "coverage detail for",  # Encompass: "Coverage Detail for 136 Old Altamont..."
#     "insured location covered by this policy",
#     "location",  # State Farm: "Location: 2971 GA HIGHWAY 93 S"
# }

# # Property labels for inline extraction (Label: Value format)
# PROPERTY_INLINE_LABELS = {
#     "property address", "risk location",
#     "location of insured property",
#     "premises address", "property location",
#     "property insured",  # ADDED for "Property Insured: 4616 HERITAGE RD"
#     "location",  # State Farm: "Location: <address>"
# }

# # Standalone "Address:" can be a property address in declarations contexts
# # (e.g., Erie Supplemental Declarations: "Address: 421 GEORGESVILLE BD")
# PROPERTY_ADDRESS_STANDALONE = {"address"}

# MAILING_TRIGGERS = {
#     "mailing address", "mail address",
#     "insured mailing", "correspondence address",
#     "send mail to", "applicant address",
# }

# MORTGAGE_TRIGGERS = {
#     "mortgagee", "loss payee",
#     "lienholder", "other interest",
#     "other interested parties", "certificate holder",
#     "mortgagee full name", "lien holder",
#     "1st mortgagee", "2nd mortgagee", "first mortgagee", "second mortgagee",
#     "holder",  # State Farm: "holder: CAPITAL CITY BANK"
#     # --- INS observation batch additions (Section 4) ---
#     "mortgage(s)", "mortgage holder",
#     "additional interest(s)", "additional interest",
#     "mortgage servicing agency",
#     "unit owner mortgagee",
#     "mortgage or interested party",
#     "additional interest/mortgage/trust",
#     "mortgage or loss payee",
#     "mortgagee/loss payee","mortgage holder",
#     "servicer", 
#     # Note: Removed "lender" as it can trigger on "Lender Relations Center"
# }

# # Patterns that look like mortgage triggers but are actually service centers
# MORTGAGE_FALSE_POSITIVES = {
#     "lender relations center",
#     "mortgagee relations center",
#     "mortgage relations center",
# }

# # NEW: Producer/Agent triggers - names after these should NOT be captured as insured
# PRODUCER_TRIGGERS = {
#     "producer", "agent", "agency",
#     "your agent", "insurance agent",
#     "sales rep", "representative",
# }

# CARRIER_TRIGGERS = {
#     "insurance company", "insurance exchange",
#     "insurance group", "insurance provided by",
#     "issued by", "underwritten by", "insurer",
#     "policy underwritten by", "your insurer",
# }

# LOAN_LABELS = {
#     "loan number", "loan no", "loan #", "loan id",
#     "mortgage loan number", "ln #",
#     # --- INS observation batch additions (Section 3) ---
#     "loan/contract number", "loan/contract #",
#     "loan:", "mortgage loan no",
#     "mortgage loan no.", "loan no.",
# }

# DATE_LABELS_EFFECTIVE = {
#     "effective date", "policy effective date",
#     "coverage begins", "term start date",
#     "change effective date","inception date",
#     "coverage effective",
#     "term effective", "policy period",
# }

# DATE_LABELS_EXPIRATION = {
#     "expiration date", "policy expiration date",
#     "coverage ends", "term end date", "expires",
#     "through", "term expires",
#     "coverage through",
#     "expiration", "policy period",
#     # Encompass format: "through July 1, 2021 at 12:01 a.m."
# }

# BAD_ADDRESS_PHRASES = {
#     "coverage", "premium", "deductible",
#     "policy period", "effective", "expiration",
#     "billing", "payment", "invoice", "notice",
# }

# # ============================================================
# # NEW: BILLING / PREMIUM / CANCELLATION LABELS
# # ============================================================

# TOTAL_PREMIUM_LABELS = {
#     "total premium",
#     "annual premium",
#     "total policy premium",
#     "policy premium",
#     "total annual premium",
#     "premium total","total amount",
#     "policy total",
#     "amount of premium", "total residence premium"
# }

# BALANCE_DUE_LABELS = {
#     "balance due",
#     "amount due",
#     "minimum due",
#     "total amount due",
#     "balance (to pay in full)",
#     "current amount due",
# }

# REMIT_INFO_LABELS = {
#     "remit to",
#     "make payment to",
#     "send payment to",
#     "payable to",
#     "remittance address",
#     "payment address",
# }

# ISSUE_DATE_LABELS = {
#     "issue date",
#     "bill date",
#     "invoice date",
#     "statement date",
#     "date issued",
# }

# CANCELLATION_DATE_LABELS = {
#     "cancellation date",
#     "effective date of cancellation",
#     "termination effective",
#     "cancel effective",
#     "cancellation effective",
# }

# CANCELLATION_REASON_KEYWORDS = {
#     "nonpayment",
#     "non-payment",
#     "underwriting",
#     "requested by insured",
#     "mortgage interest removed",
#     "third party removed",
#     "policy change",
#     "cancelled for nonpayment","failure to comply",
#     "risk unacceptable",
#     "material misrepresentation", 
# }

# # ============================================================
# # HELPERS
# # ============================================================

# def _clean(v: str) -> str:
#     """Clean extracted value"""
#     v = re.sub(r"\s+", " ", v)
#     v = v.strip(" ,.;:-")
#     return v


# def _normalize_name(v: str) -> str:
#     """Normalize name format"""
#     if not v:
#         return ""
    
#     v = v.strip()
    
#     # Remove common prefixes/suffixes
#     v = re.sub(r"^(named insured|insured|policyholder)[:\s]*", "", v, flags=re.I)
#     v = re.sub(r"\s*(beginning|effective|since|policy period).*$", "", v, flags=re.I)
    
#     # Handle "LASTNAME, FIRSTNAME" format BUT NOT company names with comma
#     # Don't swap if it contains entity suffixes
#     if "," in v and v.count(",") == 1:
#         has_entity = any(w in v.lower() for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
#         if not has_entity:
#             parts = [p.strip() for p in v.split(",") if p.strip()]
#             if len(parts) == 2 and not any(c.isdigit() for c in v):
#                 # Only swap if both parts look like names (not addresses)
#                 if not any(w.upper() in STATE_ABBREV for w in parts[1].split()):
#                     return f"{parts[1]} {parts[0]}"
    
#     return v.strip()


# def _is_phone_number(v: str) -> bool:
#     """
#     Check if value is a phone number
#     CONSERVATIVE: Returns True only for values that are CLEARLY phone numbers
#     """
#     # If the original value has letters, it's likely not a phone number
#     if any(c.isalpha() for c in v):
#         return False
    
#     # Extract only digits
#     digits = ''.join(c for c in v if c.isdigit())
    
#     # Phone numbers are exactly 7, 10, or 11 digits
#     # If longer than 11, it's definitely not a phone number
#     if len(digits) > 11:
#         return False
    
#     # Check if it has phone formatting (parentheses, dashes in right places)
#     # Only flag as phone if it has ACTUAL phone formatting
#     if re.fullmatch(r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}', v.strip()):
#         return True
    
#     # Only 7 digits with dash: xxx-xxxx format
#     if re.fullmatch(r'\d{3}[-.\s]\d{4}', v.strip()):
#         return True
    
#     # For pure numeric strings, DON'T assume they're phone numbers
#     # because policy numbers are often 10 digits too
#     # Only flag as phone if it has formatting
    
#     return False


# def _is_document_reference(v: str) -> bool:
#     """Check if value looks like a document reference code, not real data"""
#     v_clean = v.strip()
    
#     # Pattern: digits_digits_digits (e.g., 19660_859561_6)
#     if re.match(r'^\d+_\d+(_\d+)?$', v_clean):
#         return True
    
#     # Page references
#     if re.match(r'^page\s*\d+', v_clean, re.I):
#         return True
    
#     # Very long numeric strings with many zeros
#     digits = ''.join(c for c in v_clean if c.isdigit())
#     if len(digits) > 15:
#         return True
    
#     # More than 50% zeros in long number
#     if len(digits) > 10:
#         zero_count = digits.count('0')
#         if zero_count > len(digits) * 0.5:
#             return True
    
#     return False


# def _looks_like_name(text: str) -> bool:
#     """
#     Check if text looks like a person/company name
#     IMPROVED: Better filtering of mortgagee terms and noise
#     """
#     if not text or len(text) < 3:
#         return False
    
#     text = text.strip()
#     ll = text.lower()
    
#     # CRITICAL: Block mortgagee-related terms
#     for bad_term in BAD_INSURED_TERMS:
#         if bad_term in ll:
#             return False
    
#     # Block known bad phrases
#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False
    
#     # Block if ends with colon (it's a label)
#     if text.endswith(":"):
#         return False
    
#     # Block lines with too many special chars
#     special = sum(1 for c in text if c in "()[]{}|\\/<>@#$%^&*=+")
#     if special > 2:
#         return False
    
#     # Block if starts with certain bad patterns
#     bad_starts = (
#         "policy", "coverage", "premium", "page", "section",
#         "effective", "expiration", "the ", "this ", "your ",
#         "or ", "for ", "to ", "from ", "with ",
#     )
#     # NOTE: removed "and " from bad_starts to allow "ROBERT and MARY" style names
#     if any(ll.startswith(w) for w in bad_starts):
#         return False
    
#     # Block if ends with label-like patterns (but not if it's a person's name)
#     bad_ends = (
#         " address", " information", " number",
#         " period", " type", " date", " copy", " notice",
#     )
#     # Note: removed " name" because "NAME" can be a valid surname (e.g., "JOHN NAME", "DUMMY NAME")
#     if any(ll.endswith(w) for w in bad_ends):
#         return False
    
#     # Allow entities with digits (LLC, Corp, etc.)
#     has_entity = any(w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd", "bank"))
    
#     # Check if it's a multi-person name (contains "and" or "&" between name parts)
#     has_and_connector = bool(re.search(r'\b(and|&)\b', ll))
    
#     # Block digits unless it's an entity
#     if any(c.isdigit() for c in text) and not has_entity:
#         return False
    
#     words = text.replace(",", " ").split()
#     word_count = len(words)
    
#     # Entity names can be longer; multi-person names can be longer too
#     if has_entity:
#         if not (2 <= word_count <= 12):
#             return False
#     elif has_and_connector:
#         # Multi-person names like "ROBERT J BARRON and DANIEL PRYCE" can have 6-8 words
#         if not (4 <= word_count <= 10):
#             return False
#     else:
#         if not (2 <= word_count <= 6):
#             return False
    
#     # At least 1 word should start with uppercase
#     caps = sum(1 for w in words if w and w[0].isupper())
#     if caps < 1:
#         return False
    
#     # Block if looks like an address
#     if STREET_RE.search(text) or PO_BOX_RE.search(text):
#         return False
    
#     # Block if has state abbreviation followed by ZIP
#     if re.search(r"\b[A-Z]{2}\s*\d{5}", text):
#         return False
    
#     return True


# def _looks_like_policy(v: str) -> bool:
#     """
#     Check if value looks like a policy number
#     IMPROVED: Better blocking of bad patterns
#     """
#     if not v:
#         return False
    
#     v_original = v
#     v_clean = re.sub(r"[\s\-]", "", v)
    
#     # CRITICAL: Block phone numbers FIRST
#     if _is_phone_number(v_original):
#         return False
    
#     # Block document references
#     if _is_document_reference(v_original):
#         return False
    
#     # Block dates - numeric and written
#     if DATE_RE.search(v_original) or DATE_WRITTEN_RE.search(v_original):
#         return False
    
#     # Block if contains date-like words
#     date_words = ('january', 'february', 'march', 'april', 'may', 'june',
#                   'july', 'august', 'september', 'october', 'november', 'december',
#                   'effective', 'expiration')
#     if any(w in v_original.lower() for w in date_words):
#         return False
    
#     # Block pure year references (2023, 2024, etc.)
#     if v_clean.isdigit() and len(v_clean) == 4 and v_clean.startswith(('19', '20')):
#         return False
    
#     # Block ZIP codes (5 or 9 digits)
#     if re.fullmatch(r"\d{5}(-\d{4})?", v_clean):
#         return False
    
#     # Block state+number patterns (NC27102, MI48007)
#     if re.match(r'^[A-Z]{2}\d{5,}$', v_clean):
#         return False
    
#     # Block very short values
#     if len(v_clean) < 6:
#         return False
    
#     # Block very long values
#     if len(v_clean) > 30:
#         return False
    
#     # Count digits and letters
#     digits = sum(c.isdigit() for c in v_clean)
#     letters = sum(c.isalpha() for c in v_clean)
    
#     # Must have at least 4 digits (lowered slightly to handle "81-BE-N065-5" = 4 digits)
#     if digits < 4:
#         return False
    
#     # Pure numeric: 6-14 digits is OK
#     if v_clean.isdigit():
#         return 6 <= len(v_clean) <= 14
    
#     # Mixed: check against patterns
#     for rx in POLICY_REGEX_VARIANTS:
#         if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
#             return True
    
#     # Fallback: alphanumeric with substantial digits (lowered to 4 for NN-XX-XXXXX formats)
#     if letters >= 1 and digits >= 4:
#         return True
    
#     return False


# def _looks_like_loan_number(v: str) -> bool:
#     """
#     Check if value looks like a loan number
#     IMPROVED: Better filtering, stricter for short numbers
#     """
#     if not v:
#         return False
    
#     # Block document references
#     if _is_document_reference(v):
#         return False
    
#     # Block phone numbers (including formatted ones)
#     if _is_phone_number(v):
#         return False
    
#     # Extract digits
#     digits = ''.join(c for c in v if c.isdigit())
    
#     # Loan numbers are typically 6-18 digits
#     # (expanded from 8-15 per INS observation batch Section 3)
#     if len(digits) < 6 or len(digits) > 18:
#         return False
    
#     # Block if too many consecutive zeros (padding patterns)
#     if '000000' in digits:
#         return False
    
#     # Block if more than 50% zeros in longer numbers
#     if len(digits) > 10:
#         zero_count = digits.count('0')
#         if zero_count > len(digits) * 0.5:
#             return False
    
#     # Block dates
#     if DATE_RE.search(v):
#         return False
    
#     return True


# def _looks_like_address(line: str) -> bool:
#     """Check if line looks like an address"""
#     if not line or len(line) < 5:
#         return False
    
#     ll = line.lower()
    
#     # Block known bad phrases
#     if any(b in ll for b in BAD_ADDRESS_PHRASES):
#         return False
    
#     # Block if it's just a label
#     if line.strip().endswith(":"):
#         return False
    
#     # PO Box - VALID ADDRESS
#     if PO_BOX_RE.search(line):
#         return True
    
#     # Street address pattern
#     if STREET_RE.search(line):
#         return True
    
#     # Has number + state abbreviation + ZIP
#     if re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", line):
#         return True
    
#     # Has state abbreviation + ZIP (city, state zip format)
#     if re.search(r"\b[A-Z]{2}\s+\d{5}", line):
#         parts = re.split(r"\b[A-Z]{2}\s+\d{5}", line)
#         if parts and len(parts[0].strip()) > 5:
#             return True
    
#     # Has street number and reasonable length
#     has_number = bool(re.search(r"^\d+\s+", line.strip()))
#     word_count = len(line.split())
#     if has_number and word_count >= 3:
#         return True
    
#     return False


# def _looks_like_carrier(line: str) -> bool:
#     """Check if line looks like an insurance carrier name"""
#     ll = line.lower()
    
#     # Must have "insurance" or "indemnity" or "casualty" somewhere
#     if not any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance', ' ins ')):
#         if not ll.endswith(' ins'):
#             return False
    
#     # Should have company type
#     if not any(w in ll for w in ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')):
#         return False
    
#     # Block agencies
#     if any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
#         return False
    
#     # Reasonable length
#     words = line.split()
#     if not (2 <= len(words) <= 10):
#         return False
    
#     return True


# def _clean_carrier_name(name: str) -> str:
#     """Strip noise prefixes/suffixes from carrier names"""
#     # Strip label prefixes that aren't part of the actual carrier name
#     name = re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*',
#                   '', name, flags=re.I).strip()
#     noise_prefixes = (
#         "member ", "a member of ", "subsidiary of ",
#         "underwritten by ", "issued by ", "your insurer ",
#     )
#     ll = name.lower()
#     for prefix in noise_prefixes:
#         if ll.startswith(prefix):
#             name = name[len(prefix):]
#             break
#     # Strip trailing noise
#     name = re.sub(
#         r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
#         r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
#         '', name, flags=re.I
#     ).strip()
#     return name


# def _extract_carrier_name(line: str) -> str:
#     """
#     Extract just the insurance carrier name from a line that may contain extra noise.
#     Stops at the last company-type word (company, exchange, group, etc.) and 
#     truncates anything after it (like 'RENEWAL CERTIFICATE', addresses, etc.)
#     """
#     if not line:
#         return line
    
#     # First apply standard cleaning
#     line = _clean_carrier_name(line)
    
#     # Strip leading OCR garbage (apostrophes, weird chars)
#     line = re.sub(r"^[^A-Za-z0-9]+", "", line).strip()
    
#     # Find where the company name likely ends by looking for company-type words
#     # Use the LAST occurrence (for "State Farm Fire and Casualty Company")
#     company_type_words = ['company', 'exchange', 'group', 'mutual', 
#                           'corp', 'corporation', 'indemnity', 'casualty']
    
#     ll = line.lower()
#     best_end = -1
    
#     for ct in company_type_words:
#         idx = ll.rfind(ct)  # rightmost occurrence
#         if idx >= 0:
#             end = idx + len(ct)
#             if end > best_end:
#                 best_end = end
    
#     if best_end > 0:
#         result = line[:best_end].strip()
#     else:
#         result = line
    
#     # Must still contain 'insurance', 'indemnity', or 'casualty'
#     if not any(w in result.lower() for w in ('insurance', 'indemnity', 'casualty', 'assurance', 'fire')):
#         return ""
    
#     # Reasonable length check
#     words = result.split()
#     if len(words) > 10:
#         # Too long — probably a merged line; find the carrier within it
#         # Look for a window ending at a company type
#         for i in range(len(words) - 1, -1, -1):
#             if any(ct in words[i].lower() for ct in company_type_words):
#                 # Find reasonable start (up to 8 words back)
#                 start = max(0, i - 7)
#                 candidate = " ".join(words[start:i+1])
#                 if any(w in candidate.lower() for w in ('insurance', 'indemnity', 'casualty')):
#                     result = candidate
#                     break
    
#     # Strip leading OCR artifact words (words that don't belong to a carrier name)
#     # Look for known carrier name patterns — find where the "real" name starts
#     words = result.split()
#     if len(words) >= 2:
#         for i in range(1, len(words)):  # Start at 1: need at least one prefix word
#             rest = " ".join(words[i:])
#             rest_ll = rest.lower()
#             if any(x in rest_ll for x in ('insurance', 'indemnity', 'casualty', 'fire')):
#                 if any(x in rest_ll for x in company_type_words):
#                     # Check if the prefix looks like OCR noise (all lowercase)
#                     prefix = " ".join(words[:i])
#                     if all(not c.isupper() for c in prefix if c.isalpha()):
#                         result = rest
#                     break
    
#     return result.strip()

# def _extract_date(line: str, label_set: set) -> str:
#     """Extract date from line if it matches label pattern"""
#     ll = line.lower()
    
#     if not any(k in ll for k in label_set):
#         return None
    
#     # Try written format first: January 15, 2024
#     m = DATE_WRITTEN_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try abbreviated month format: NOV 09 2021
#     m = DATE_ABBREV_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try numeric format: 01/15/2024
#     m = DATE_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try extracting after colon
#     if ":" in line:
#         _, _, val = line.partition(":")
#         val = val.strip()
#         m = (DATE_WRITTEN_RE.search(val) or DATE_ABBREV_RE.search(val)
#              or DATE_RE.search(val))
#         if m:
#             return m.group(0)
    
#     return None


# # ============================================================
# # STATEFUL EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}
#         self.carrier_accumulator: List[str] = []  # For multi-line carrier names
#         self.address_accumulator: List[str] = []
#         self._partial_insured: str = ""  # For multi-line insured names
#         self._pending_premium: bool = False  # For multi-line premium extraction
#         self._pending_policy_period: bool = False  # For Policy Period: on its own line
    
#     def update_role(self, line: str):
#         """Update current parsing role based on section headers"""
#         ll = line.lower().strip()
        
#         # Check for role triggers (order matters - more specific first)
#         if any(k in ll for k in POLICY_LABELS):
#             self._flush_accumulators()
#             self.role, self.window = Role.POLICY_HEADER, 8
#         # "Insured Mailing Name and Address" = INSURED block (captures both name + address)
#         elif "insured" in ll and "mailing" in ll:
#             self._flush_accumulators()
#             self.role, self.window = Role.INSURED_BLOCK, 12
#         elif any(k in ll for k in MAILING_TRIGGERS):
#             self._flush_accumulators()
#             self.role, self.window = Role.MAILING_BLOCK, 8
#         elif any(k in ll for k in INSURED_LABELS) and "payor" not in ll:
#             self._flush_accumulators()
#             self.role, self.window = Role.INSURED_BLOCK, 12
#         elif any(k in ll for k in PROPERTY_TRIGGERS):
#             self._flush_accumulators()
#             self.role, self.window = Role.PROPERTY_BLOCK, 8
#         # Standalone "Address:" line can indicate property in declarations context
#         elif re.match(r'^address\s*[:.]', ll) and "property_address" not in self.fields:
#             self._flush_accumulators()
#             self.role, self.window = Role.PROPERTY_BLOCK, 5
#         elif any(k in ll for k in MORTGAGE_TRIGGERS):
#             # Check if it's a false positive (service center header)
#             if not any(fp in ll for fp in MORTGAGE_FALSE_POSITIVES):
#                 self._flush_accumulators()
#                 self.role, self.window = Role.MORTGAGE_BLOCK, 10
#         elif any(k in ll for k in PRODUCER_TRIGGERS):
#             # Producer/agent section - skip names here
#             self._flush_accumulators()
#             self.role, self.window = Role.PRODUCER_BLOCK, 6
#         elif any(k in ll for k in CARRIER_TRIGGERS):
#             # DON'T flush carrier accumulator - we might need to combine
#             self._flush_accumulators(entering_carrier_block=True)
#             self.role, self.window = Role.CARRIER_BLOCK, 6
    
#     def _flush_accumulators(self, entering_carrier_block=False):
#         """Save accumulated multi-line values before role change"""
#         # DON'T flush carrier accumulator if entering carrier block
#         # because we might need to combine it with the incoming line
#         if not entering_carrier_block:
#             if self.carrier_accumulator and "carrier_name" not in self.fields:
#                 combined = " ".join(self.carrier_accumulator)
#                 if _looks_like_carrier(combined):
#                     self.fields["carrier_name"] = {
#                         "value": combined.upper(),
#                         "confidence": 0.96,
#                         "source": "accumulated",
#                     }
#                 self.carrier_accumulator = []
        
#         # Flush address accumulator
#         if self.address_accumulator:
#             addr = " ".join(self.address_accumulator)
#             if "property_address" not in self.fields:
#                 self.fields["property_address"] = {
#                     "value": addr,
#                     "confidence": 0.94,
#                     "source": "accumulated",
#                 }
#             self.address_accumulator = []
    
#     def extract(self, line: str):
#         """Main extraction logic for each line"""
#         # Always try inline extraction first
#         self._inline(line)
        
#         # Try carrier extraction from any line (multi-line support)
#         self._try_carrier_accumulation(line)
        
#         # Role-based extraction
#         if self.window > 0:
#             if self.role == Role.POLICY_HEADER:
#                 self._policy(line)
#             elif self.role == Role.INSURED_BLOCK:
#                 self._insured(line)
#             elif self.role == Role.PROPERTY_BLOCK:
#                 self._property(line)
#             elif self.role == Role.MAILING_BLOCK:
#                 self._mailing(line)
#             elif self.role == Role.MORTGAGE_BLOCK:
#                 self._mortgage(line)
#             elif self.role == Role.CARRIER_BLOCK:
#                 self._carrier(line)
            
#             self.window -= 1
#             if self.window == 0:
#                 self._flush_accumulators()
#                 self.role = Role.NONE
    
#     def _try_carrier_accumulation(self, line: str):
#         """Try to accumulate carrier name across lines"""
#         if "carrier_name" in self.fields:
#             return
        
#         ll = line.lower()
#         clean = line.strip().replace("*", "")
        
#         # Skip label lines (ending with ":" or ":.") — these aren't carrier name parts
#         stripped = clean.rstrip(".")
#         if stripped.endswith(":"):
#             return
        
#         # Check if this line contains 'insurance'
#         if 'insurance' in ll:
#             # If we have accumulated a prefix, ALWAYS try to combine
#             if self.carrier_accumulator:
#                 combined = " ".join(self.carrier_accumulator) + " " + clean
#                 combined_lower = combined.lower()
#                 # If combined has insurance + company type, use it
#                 if 'insurance' in combined_lower and any(w in combined_lower for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual')):
#                     if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
#                         carrier_val = _extract_carrier_name(combined)
#                         self.fields["carrier_name"] = {
#                             "value": carrier_val.upper(),
#                             "confidence": 0.97,
#                             "source": "multi_line_combined",
#                         }
#                         self.carrier_accumulator = []
#                         return
            
#             # No accumulator - check if this line alone is a complete carrier
#             carrier_candidate = _extract_carrier_name(clean)
#             if carrier_candidate and _looks_like_carrier(carrier_candidate):
#                 self.fields["carrier_name"] = {
#                     "value": carrier_candidate.upper(),
#                     "confidence": 0.95,
#                     "source": "direct",
#                 }
#                 self.carrier_accumulator = []
#                 return
            
#             # Start accumulating (e.g., "Erie INSURANCE" without company type)
#             if not self.carrier_accumulator:
#                 if not any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
#                     self.carrier_accumulator = [clean]
#                     return
        
#         # If accumulator has 'insurance' and current line is a company-type word
#         # e.g., accumulator = ["Erie INSURANCE"], current line = "Exchange"
#         elif self.carrier_accumulator and any('insurance' in a.lower() for a in self.carrier_accumulator):
#             company_types = ('exchange', 'company', 'group', 'mutual', 'corp', 'corporation')
#             if any(w in ll for w in company_types):
#                 combined = " ".join(self.carrier_accumulator) + " " + clean
#                 combined_lower = combined.lower()
#                 if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
#                     carrier_val = _extract_carrier_name(_clean_carrier_name(combined))
#                     self.fields["carrier_name"] = {
#                         "value": carrier_val.upper(),
#                         "confidence": 0.97,
#                         "source": "multi_line_combined",
#                     }
#                     self.carrier_accumulator = []
#                     return
        
#         # Check if this might be first part of multi-line carrier
#         elif clean.isupper() and len(clean.split()) <= 2 and not any(c.isdigit() for c in clean):
#             # Might be company name prefix like "ADIRONDACK"
#             noise_words = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", "NOTICE", "PO", "BOX"}
#             words = clean.split()
#             if words and not any(w in noise_words for w in words):
#                 if all(len(w) >= 3 for w in words):  # Each word should be substantial
#                     self.carrier_accumulator = [clean]
    
#     def _inline(self, line: str):
#         """Extract from inline patterns (Label: Value)"""
#         ll = line.lower()

#         # ============================================================
#         # POLICY NUMBER
#         # ============================================================
#         if "policy_number" not in self.fields:
#             if ":" in line and any(k in ll for k in POLICY_LABELS):
#                 _, _, v = line.partition(":")
#                 v = _clean(v)

#                 if re.match(r'^\d{9}\s+\d{3}\s+\d$', v):
#                     v_no_space = v.replace(" ", "")
#                     if _looks_like_policy(v_no_space):
#                         self.fields["policy_number"] = {
#                             "value": v,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }
#                 else:
#                     v = re.sub(r"\s+(\d)$", r"-\1", v)
#                     v_no_space = v.replace(" ", "")
#                     if _looks_like_policy(v_no_space):
#                         self.fields["policy_number"] = {
#                             "value": v_no_space,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }

#             elif any(k in ll for k in POLICY_LABELS):
#                 for label in sorted(POLICY_LABELS, key=len, reverse=True):
#                     idx = ll.find(label)
#                     if idx >= 0:
#                         after = line[idx + len(label):].strip().lstrip(":").strip()
#                         for token in after.split():
#                             candidate = _clean(token)
#                             if _looks_like_policy(candidate.replace(" ", "")):
#                                 self.fields["policy_number"] = {
#                                     "value": candidate,
#                                     "confidence": 0.95,
#                                     "source": "inline_no_colon",
#                                 }
#                                 break
#                         if "policy_number" in self.fields:
#                             break

#         # ============================================================
#         # PROPERTY ADDRESS
#         # ============================================================
#         if "property_address" not in self.fields and ":" in line:
#             if any(k in ll for k in PROPERTY_INLINE_LABELS):
#                 _, _, v = line.partition(":")
#                 v = v.strip()
#                 if v and _looks_like_address(v):
#                     self.fields["property_address"] = {
#                         "value": v,
#                         "confidence": 0.98,
#                         "source": "inline",
#                     }

#         if "property_address" not in self.fields and "coverage detail for" in ll:
#             m = re.search(r'coverage\s+detail\s+for\s+(.+)', line, re.I)
#             if m:
#                 addr = re.sub(r'\s*\(continued\).*$', '', m.group(1), flags=re.I).strip()
#                 if _looks_like_address(addr):
#                     self.fields["property_address"] = {
#                         "value": addr,
#                         "confidence": 0.97,
#                         "source": "inline_coverage_detail",
#                     }

#         # ============================================================
#         # INSURED NAME
#         # ============================================================
#         if "insured_name" not in self.fields and ":" in line:
#             label, _, val = line.partition(":")
#             label_lower = label.lower().strip()

#             if any(k in label_lower for k in ("insured", "policyholder")):
#                 if not any(b in label_lower for b in (
#                     "mortgagee", "loss payee", "lender",
#                     "interest of", "interest in",
#                     "additional insured",
#                 )):
#                     v = _normalize_name(val)
#                     if v and _looks_like_name(v):
#                         self.fields["insured_name"] = {
#                             "value": v,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }
#                     elif v and len(v.strip()) > 3:
#                         self._partial_insured = v.strip()

#         # ============================================================
#         # LOAN NUMBER
#         # ============================================================
#         has_loan_label = any(k in ll for k in LOAN_LABELS)
#         existing = self.fields.get("loan_number", {})
#         existing_unlabeled = existing.get("source") in ("mortgage_block", "sweep") if existing else False

#         if has_loan_label and ("loan_number" not in self.fields or existing_unlabeled):
#             if ":" in line:
#                 _, _, v = line.partition(":")
#                 digits = ''.join(c for c in v if c.isdigit())
#             else:
#                 digits = ''
#                 for token in line.split():
#                     d = ''.join(c for c in token if c.isdigit())
#                     if len(d) >= 7:
#                         digits = d
#                         break

#             if _looks_like_loan_number(digits):
#                 self.fields["loan_number"] = {
#                     "value": digits,
#                     "confidence": 0.96,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # EFFECTIVE / EXPIRATION DATES (HARDENED)
#         # ============================================================

#         # 1️⃣ Handle date range FIRST
#         if "effective_date" not in self.fields or "expiration_date" not in self.fields:
#             date_range = re.search(
#                 r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-|thru|through)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
#                 line,
#                 re.I
#             )
#             if date_range:
#                 if "effective_date" not in self.fields:
#                     self.fields["effective_date"] = {
#                         "value": date_range.group(1),
#                         "confidence": 0.96,
#                         "source": "inline_date_range",
#                     }
#                 if "expiration_date" not in self.fields:
#                     self.fields["expiration_date"] = {
#                         "value": date_range.group(2),
#                         "confidence": 0.96,
#                         "source": "inline_date_range",
#                     }
#                 return  # stop further date extraction for this line

#         # 2️⃣ Fallback to label-based extraction
#         if "effective_date" not in self.fields:
#             date = _extract_date(line, DATE_LABELS_EFFECTIVE)
#             if date:
#                 self.fields["effective_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline_label",
#                 }

#         if "expiration_date" not in self.fields:
#             date = _extract_date(line, DATE_LABELS_EXPIRATION)
#             if date:
#                 self.fields["expiration_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline_label",
#                 }


#         # ============================================================
#         # TOTAL PREMIUM
#         # ============================================================
#         if "total_premium" not in self.fields:
#             if any(k in ll for k in TOTAL_PREMIUM_LABELS):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.96,
#                         "source": "inline_premium",
#                     }
#                 else:
#                     self._pending_premium = True
#             elif getattr(self, '_pending_premium', False):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.93,
#                         "source": "inline_premium_lookahead",
#                     }
#                     self._pending_premium = False
#                 elif ll.strip():
#                     self._pending_premium = False

#         # ============================================================
#         # BALANCE DUE
#         # ============================================================
#         if "balance_due" not in self.fields:
#             if any(k in ll for k in BALANCE_DUE_LABELS):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["balance_due"] = {
#                         "value": money[-1],
#                         "confidence": 0.95,
#                         "source": "inline_balance_due",
#                     }

#         # ============================================================
#         # ISSUE DATE
#         # ============================================================
#         if "issue_date" not in self.fields:
#             date = _extract_date(line, ISSUE_DATE_LABELS)
#             if date:
#                 self.fields["issue_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # CANCELLATION DATE
#         # ============================================================
#         if "cancellation_date" not in self.fields:
#             date = _extract_date(line, CANCELLATION_DATE_LABELS)
#             if date:
#                 self.fields["cancellation_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # CANCELLATION REASON
#         # ============================================================
#         if "cancellation_reason" not in self.fields:
#             for keyword in CANCELLATION_REASON_KEYWORDS:
#                 if keyword in ll:
#                     self.fields["cancellation_reason"] = {
#                         "value": keyword.title(),
#                         "confidence": 0.90,
#                         "source": "keyword_match",
#                     }
#                     break

#         # ============================================================
#         # REMIT INFO
#         # ============================================================
#         if any(k in ll for k in REMIT_INFO_LABELS):
#             self.role = Role.MAILING_BLOCK
#             self.window = 6


#     def _policy(self, line: str):
#         """Extract policy number from POLICY block"""
#         if "policy_number" in self.fields:
#             return
        
#         # Try each token
#         for token in line.split():
#             clean_token = _clean(token)
#             if _looks_like_policy(clean_token):
#                 self.fields["policy_number"] = {
#                     "value": clean_token,
#                     "confidence": 0.96,
#                     "source": "block",
#                 }
#                 return
        
#         # Try the whole line (handles spaces in policy numbers)
#         clean_line = _clean(line)
#         no_spaces = clean_line.replace(" ", "")
#         if _looks_like_policy(no_spaces):
#             self.fields["policy_number"] = {
#                 "value": no_spaces,
#                 "confidence": 0.94,
#                 "source": "block_combined",
#             }
    
#     def _insured(self, line: str):
#         """Extract insured name from INSURED block - IMPROVED"""
#         ll = line.lower().strip()
        
#         # Skip obvious non-name lines
#         skip_patterns = [
#             "po box", "policy period", "loan number", "policy type",
#             "description", "coverage", "premium", "effective", "expiration",
#             "page", "continued", "summary", "mortgagee", "loss payee",
#             "mailing address",
#         ]
#         if any(p in ll for p in skip_patterns):
#             return
        
#         # Skip if line is just a header
#         if line.strip().endswith(":"):
#             return
#         if ll in [l.lower() for l in INSURED_LABELS]:
#             return
        
#         # CRITICAL: Skip if line looks like a label fragment
#         if ll.startswith("and ") or ll.startswith("or "):
#             return
        
#         clean_line = _normalize_name(line)
        
#         # Strip trailing date patterns (e.g., "Dummy Name July 2020" -> "Dummy Name")
#         clean_line = re.sub(
#             r'\s+(January|February|March|April|May|June|July|August|September|'
#             r'October|November|December)\s+\d{4}\s*$',
#             '', clean_line, flags=re.I
#         ).strip()
        
#         # CRITICAL: Additional check - block mortgagee-related values
#         if any(bad in ll for bad in BAD_INSURED_TERMS):
#             return
        
#         # Skip generic section headers that look like names but aren't
#         section_headers = {
#             "home protection", "personal liability", "medical expenses",
#             "personal property", "dwelling coverage", "loss settlement",
#             "hurricane premium", "building ordinance", "property protection",
#             "coverage", "property protection", "renewal certificate",
#             "supplemental declarations", "medical office",
#         }
#         if clean_line.lower().strip() in section_headers:
#             return
        
#         # Check for multi-line name combination (e.g., "DUMMY NAME" + "PROPERTIES, LLC")
#         if self._partial_insured and "insured_name" not in self.fields:
#             # Try combining with previous partial
#             combined = self._partial_insured + " " + clean_line
#             if _looks_like_name(combined):
#                 self.fields["insured_name"] = {
#                     "value": combined,
#                     "confidence": 0.96,
#                     "source": "block_combined",
#                 }
#                 self._partial_insured = ""
#                 return
        
#         # Check if it's a name
#         if _looks_like_name(clean_line):
#             if "insured_name" not in self.fields:
#                 self.fields["insured_name"] = {
#                     "value": clean_line,
#                     "confidence": 0.97,
#                     "source": "block",
#                 }
#                 # Don't clear _partial — set it so next line can extend
#                 self._partial_insured = clean_line
#             elif self._partial_insured:
#                 # Already have a name — check if this extends it
#                 # (e.g., "PROPERTIES, LLC" extending "DUMMY NAME")
#                 combined = self._partial_insured + " " + clean_line
#                 if _looks_like_name(combined):
#                     self.fields["insured_name"] = {
#                         "value": combined,
#                         "confidence": 0.97,
#                         "source": "block_extended",
#                     }
#                 self._partial_insured = ""
#             return
        
#         # Check if current line is a business suffix that extends the existing name
#         if "insured_name" in self.fields and self._partial_insured:
#             business_suffixes = ("llc", "inc", "corp", "ltd", "co", "properties",
#                                  "enterprises", "holdings", "investments", "group",
#                                  "associates", "partners", "trust", "estate")
#             clean_lower = clean_line.lower().strip().rstrip(".,")
#             if any(clean_lower.startswith(s) or clean_lower.endswith(s) for s in business_suffixes):
#                 combined = self._partial_insured + " " + clean_line
#                 self.fields["insured_name"] = {
#                     "value": combined,
#                     "confidence": 0.97,
#                     "source": "block_extended",
#                 }
#             self._partial_insured = ""
#             return
        
#         # If it might be first part of multi-line name (single word, uppercase)
#         if clean_line.isupper() and len(clean_line.split()) <= 2 and "insured_name" not in self.fields:
#             # Check if it looks like a name part (not a header)
#             if not any(w in clean_line.lower() for w in ("page", "policy", "coverage")):
#                 self._partial_insured = clean_line
#                 return
        
#         # Check if it's an address (capture for mailing)
#         if _looks_like_address(line):
#             if "mailing_address" not in self.fields:
#                 # Check if line has "Label: Value" format
#                 address_value = line.strip()
#                 if ":" in line:
#                     _, _, val = line.partition(":")
#                     val = val.strip()
#                     if val and _looks_like_address(val):
#                         address_value = val
                
#                 self.fields["mailing_address"] = {
#                     "value": address_value,
#                     "confidence": 0.92,
#                     "source": "insured_block",
#                 }
    
#     def _property(self, line: str):
#         """Extract property address from PROPERTY block"""
#         ll = line.lower().strip()
        
#         # Skip headers and labels
#         if line.strip().endswith(":"):
#             return
#         if ll in [t.lower() for t in PROPERTY_TRIGGERS]:
#             return
        
#         # Check if line has "Label: Value" format
#         address_value = line.strip()
#         if ":" in line:
#             label, _, val = line.partition(":")
#             val = val.strip()
#             # If value part looks like an address, use just the value
#             if val and _looks_like_address(val):
#                 address_value = val
        
#         if _looks_like_address(address_value):
#             if "property_address" not in self.fields:
#                 self.fields["property_address"] = {
#                     "value": address_value,
#                     "confidence": 0.98,
#                     "source": "block",
#                 }
#             else:
#                 current = self.fields["property_address"]["value"]
#                 has_street_number = bool(re.match(r'^\d+\s+', current.strip()))
#                 new_has_street = bool(re.match(r'^\d+\s+', address_value.strip()))
                
#                 # Check if this looks like a city/state/zip continuation
#                 # (no street number, follows a street line)
#                 is_city_continuation = (
#                     has_street_number and not new_has_street
#                     and re.search(r'[A-Z]{2}\s+\d{5}', address_value)  # Has state + zip
#                     and "," not in current  # Current doesn't already have city
#                 )
                
#                 if is_city_continuation:
#                     self.fields["property_address"]["value"] = current + ", " + address_value
#                 elif new_has_street and not has_street_number:
#                     self.fields["property_address"]["value"] = address_value
#                 elif len(address_value) > len(current) and (new_has_street or not has_street_number):
#                     self.fields["property_address"]["value"] = address_value
    
#     def _mailing(self, line: str):
#         """Extract mailing address from MAILING block"""
#         if line.strip().endswith(":"):
#             return
        
#         if _looks_like_address(line):
#             addr_val = line.strip()
#             # Strip trailing date/time patterns
#             addr_val = re.sub(
#                 r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+'
#                 r'(January|February|March|April|May|June|July|August|September|'
#                 r'October|November|December)\s+\d{1,2},?\s+\d{4}.*$',
#                 '', addr_val, flags=re.I
#             ).strip()
#             addr_val = re.sub(
#                 r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+\d{1,2}/\d{1,2}/\d{4}.*$',
#                 '', addr_val, flags=re.I
#             ).strip()
#             if addr_val:
#                 if "mailing_address" not in self.fields:
#                     self.fields["mailing_address"] = {
#                         "value": addr_val,
#                         "confidence": 0.96,
#                         "source": "mailing_block",
#                     }
#                 else:
#                     # Append city/state/zip to existing PO Box or street
#                     existing = self.fields["mailing_address"]["value"]
#                     # Only append if it looks like a continuation (city/state/zip)
#                     if addr_val and not addr_val.lower().startswith("po box"):
#                         self.fields["mailing_address"]["value"] = existing + ", " + addr_val
#         elif _looks_like_name(line) and "insured_name" not in self.fields:
#             self.fields["insured_name"] = {
#                 "value": _normalize_name(line),
#                 "confidence": 0.90,
#                 "source": "mailing_block",
#             }
#         elif "insured_name" in self.fields and self.fields["insured_name"].get("source") == "mailing_block":
#             # Check if this is a continuation of the name (e.g., "PROPERTIES, LLC")
#             clean = _normalize_name(line)
#             if clean and _looks_like_name(clean) and not _looks_like_address(line):
#                 existing = self.fields["insured_name"]["value"]
#                 # Only append if it looks like a continuation (LLC, Inc, Corp, etc.)
#                 # or if the combined result still looks like a name
#                 combined = existing + " " + clean
#                 if _looks_like_name(combined):
#                     self.fields["insured_name"]["value"] = combined
    
#     def _mortgage(self, line: str):
#         """Extract mortgage company and loan number from MORTGAGE block"""
#         ll = line.lower()
        
#         # Skip headers (including ":." variant from OCR)
#         stripped = line.strip().rstrip(".")
#         if stripped.endswith(":"):
#             return
        
#         # Skip bad patterns (EXPANDED)
#         bad_patterns = [
#             "policy", "coverage", "endorsement", "homeowners", "premium",
#             "first mortgagee", "second mortgagee", "third mortgagee",
#             "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
#             "mortgagee copy", "mortgagee certificate",
#             "other interest", "type of interest",
#         ]
#         if any(p in ll for p in bad_patterns):
#             return
        
#         # Loan number — also capture "N/A" style loan indicators
#         if "loan_number" not in self.fields:
#             has_loan_label = any(k in ll for k in ("loan no", "loan number", "loan #", "loan id", "ln #", "mortgage loan"))
#             if has_loan_label:
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     if re.match(r'^n/?a\b', v, re.I):
#                         self.fields["loan_number"] = {
#                             "value": "N/A",
#                             "confidence": 0.90,
#                             "source": "mortgage_block",
#                         }
#                     else:
#                         digits = ''.join(c for c in v if c.isdigit())
#                         if _looks_like_loan_number(digits):
#                             self.fields["loan_number"] = {
#                                 "value": digits,
#                                 "confidence": 0.94,
#                                 "source": "mortgage_block",
#                             }
#             elif not _looks_like_address(line):
#                 # Only scan tokens for loan number if line is NOT an address
#                 for token in line.split():
#                     digits = ''.join(c for c in token if c.isdigit())
#                     if _looks_like_loan_number(digits):
#                         self.fields["loan_number"] = {
#                             "value": digits,
#                             "confidence": 0.90,
#                             "source": "mortgage_block",
#                         }
#                         break
        
#         # Mortgage company
#         if "mortgage_company" not in self.fields:
#             # Look for company-like patterns
#             if any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "federal", "financial")):
#                 # CRITICAL: Skip if it's just a label like "First Mortgagee"
#                 if re.match(r'^(first|second|third|1st|2nd|3rd)\s+(mortgagee|lender)', ll):
#                     return
                
#                 clean = line.strip()
#                 # Remove label prefixes like "holder:", "mortgagee:", etc.
#                 clean = re.sub(r'^(holder|mortgagee|loss\s+payee|lienholder|lien\s+holder)\s*:\s*', '', clean, flags=re.I)
#                 # Remove ISAOA/ATIMA/SUCC suffixes
#                 clean = re.sub(r'\s+(ITS\s+SUCC(\s+AND/OR\s+ASSIGNS)?\s+)?(ISAOA|ATIMA|ISAOA/ATIMA).*$', '', clean, flags=re.I)
#                 clean = re.sub(r'\s+ITS\s+SUCC\s+AND/OR\s+ASSIGNS.*$', '', clean, flags=re.I)
#                 # Remove numbering prefixes
#                 clean = re.sub(r'^(\d+\.?\s*|first\s+|second\s+|third\s+)', '', clean, flags=re.I)
                
#                 if len(clean) > 5:
#                     self.fields["mortgage_company"] = {
#                         "value": clean,
#                         "confidence": 0.94,
#                         "source": "mortgage_block",
#                     }
    
#     def _carrier(self, line: str):
#         """Extract carrier name from CARRIER block"""
#         if "carrier_name" in self.fields:
#             return
        
#         ll = line.lower()
        
#         # Skip headers
#         if line.strip().endswith(":"):
#             return
        
#         # Look for insurance company patterns
#         # Include "indemnity", "casualty" as alternatives to "insurance"
#         has_insurer_word = any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance'))
#         has_company_type = any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp'))
#         is_agent_line = any(w in ll for w in ('agency', 'agent', 'services', 'producer'))
        
#         if has_insurer_word and has_company_type and not is_agent_line:
#             # Strip trailing noise like "Customer assistance number:" 
#             carrier_val = line.strip()
#             carrier_val = re.sub(
#                 r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
#                 r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
#                 '', carrier_val, flags=re.I
#             ).strip()
#             self.fields["carrier_name"] = {
#                 "value": carrier_val.upper(),
#                 "confidence": 0.96,
#                 "source": "carrier_block",
#             }
    
#     def finalize(self):
#         """Final cleanup and flush"""
#         self._flush_accumulators()


# # ============================================================
# # SAFE SWEEP (FALLBACK)
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     """Final pass to catch missed fields"""
    
#     # --- Policy Number fallback ---
#     if "policy_number" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in POLICY_LABELS):
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = _clean(v).replace(" ", "")
#                     if _looks_like_policy(v):
#                         fields["policy_number"] = {
#                             "value": v,
#                             "confidence": 0.88,
#                             "source": "sweep",
#                         }
#                         break
                
#                 # Check next few lines
#                 for j in range(i + 1, min(i + 3, len(lines))):
#                     candidate = _clean(lines[j]).replace(" ", "")
#                     if _looks_like_policy(candidate):
#                         fields["policy_number"] = {
#                             "value": candidate,
#                             "confidence": 0.85,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "policy_number" in fields:
#                     break
    
#     # --- Insured Name fallback (IMPROVED) ---
#     if "insured_name" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in INSURED_LABELS):
#                 # CRITICAL: Skip if it's a mortgagee section
#                 if any(bad in ll for bad in ("mortgagee", "loss payee")):
#                     continue
                
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = _normalize_name(v)
#                     if _looks_like_name(v):
#                         fields["insured_name"] = {
#                             "value": v,
#                             "confidence": 0.88,
#                             "source": "sweep",
#                         }
#                         break
                
#                 # Check next few lines
#                 for j in range(i + 1, min(i + 4, len(lines))):
#                     candidate = _normalize_name(lines[j])
#                     if _looks_like_name(candidate):
#                         fields["insured_name"] = {
#                             "value": candidate,
#                             "confidence": 0.85,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "insured_name" in fields:
#                     break
    
#     # --- Property Address fallback ---
#     if "property_address" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in PROPERTY_TRIGGERS):
#                 for j in range(i + 1, min(i + 5, len(lines))):
#                     if _looks_like_address(lines[j]):
#                         fields["property_address"] = {
#                             "value": lines[j].strip(),
#                             "confidence": 0.84,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "property_address" in fields:
#                     break
    
#     # --- Carrier Name fallback (scan first 20 lines) ---
#     if "carrier_name" not in fields:
#         # First, look for "underwritten by" or "your insurer" patterns
#         for line in lines[:30]:
#             ll = line.lower()
#             if "underwritten by" in ll or "your insurer" in ll:
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     if 'insurance' in v.lower():
#                         fields["carrier_name"] = {
#                             "value": v.upper(),
#                             "confidence": 0.90,
#                             "source": "sweep_underwritten",
#                         }
#                         break
        
#         # Then try direct insurance company pattern
#         if "carrier_name" not in fields:
#             for line in lines[:20]:
#                 ll = line.lower()
#                 if any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance')):
#                     if any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
#                         if not any(w in ll for w in ('agency', 'agent', 'services')):
#                             carrier_val = _extract_carrier_name(line.strip())
#                             if carrier_val and _looks_like_carrier(carrier_val):
#                                 fields["carrier_name"] = {
#                                     "value": carrier_val.upper(),
#                                     "confidence": 0.85,
#                                     "source": "sweep_header",
#                                 }
#                                 break
    
#     # --- Loan Number fallback ---
#     if "loan_number" not in fields:
#         for line in lines:
#             ll = line.lower()
#             if any(k in ll for k in LOAN_LABELS):
#                 # Try to extract number from line
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     # Handle N/A loan numbers (with or without slash)
#                     if re.match(r'^n/?a\b', v, re.I):
#                         fields["loan_number"] = {
#                             "value": "N/A",
#                             "confidence": 0.85,
#                             "source": "sweep",
#                         }
#                         break
#                     digits = ''.join(c for c in v if c.isdigit())
#                 else:
#                     digits = ''.join(c for c in line if c.isdigit())
                
#                 if _looks_like_loan_number(digits):
#                     fields["loan_number"] = {
#                         "value": digits,
#                         "confidence": 0.85,
#                         "source": "sweep",
#                     }
#                     break
    
#     # --- Total Premium fallback ---
#     if "total_premium" not in fields:
#         premium_labels = (
#             "total annual policy premium", "total annual premium",
#             "total policy premium", "total premium",
#             "total residence premium", "annual premium",
#             "total annual policy cost", "full term premium",
#         )
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in premium_labels):
#                 # Check same line for dollar amount
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.85,
#                         "source": "sweep_premium",
#                     }
#                     break
#                 # Check next lines — take the LAST dollar amount found
#                 # (in two-column layouts, the total is the last amount)
#                 last_money = None
#                 for j in range(i + 1, min(i + 20, len(lines))):
#                     money_j = re.findall(r'\$[\d,]+\.?\d*', lines[j])
#                     if money_j:
#                         last_money = money_j[-1]
#                 if last_money:
#                     fields["total_premium"] = {
#                         "value": last_money,
#                         "confidence": 0.82,
#                         "source": "sweep_premium_lookahead",
#                     }
#                     break


# # ============================================================
# # ENTRY POINTS
# # ============================================================

# # ---- CAN-specific field patterns ----
# _CAN_DATE_PATTERNS = re.compile(
#     r"(?i)(?:cancellation|cancel(?:led)?|termination|void|cease|non-?renewal)"
#     r"(?:\s+effective|\s+date)?\s*[:\-]?\s*"
#     r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
# )
# _CAN_REASON_LABELS = re.compile(
#     r"(?i)(?:reason\s+for\s+(?:cancellation|termination)|cancel(?:lation)?\s+reason"
#     r"|reason\s*:)\s*(.{4,80})"
# )
# _BALANCE_DUE_PATTERNS = re.compile(
#     r"(?i)(?:balance\s+(?:to\s+pay|due)|amount\s+due|total\s+(?:amount\s+)?due"
#     r"|minimum\s+(?:amount\s+)?due|to\s+pay\s+in\s+full)\s*[:\$]?\s*\$?([\d,]+\.?\d*)"
# )
# _ISSUE_DATE_PATTERNS = re.compile(
#     r"(?i)(?:bill\s+date|invoice\s+date|statement\s+date|issue\s+date"
#     r"|billing\s+date|due\s+date|information\s+as\s+of|processed\s+on)\s*[:\-]?\s*"
#     r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
# )
# _REMIT_PATTERNS = re.compile(
#     r"(?i)(?:mail\s+to|remit\s+to|payable\s+to|make\s+check[s]?\s+payable\s+to"
#     r"|send\s+payment\s+to|payment\s+to)\s*[:\-]?\s*(.{4,80})"
# )


# def _extract_can_inv_fields(lines: List[str], fields: Dict[str, Dict]) -> None:
#     """
#     Doc-type-aware sweep for CAN and INV specific fields.
#     Stage1 normally doesn't extract these — this function fills the gap.
#     Called after _safe_sweep() so it only adds fields that Stage1 missed.
#     """
#     text = "\n".join(lines)

#     # --- CANCELLATION DATE ---
#     if "cancellation_date" not in fields:
#         m = _CAN_DATE_PATTERNS.search(text)
#         if m:
#             fields["cancellation_date"] = {
#                 "value": m.group(1).strip(),
#                 "confidence": 0.82,
#                 "source": "stage1_can_date",
#             }

#     # --- CANCELLATION REASON ---
#     if "cancellation_reason" not in fields:
#         m = _CAN_REASON_LABELS.search(text)
#         if m:
#             reason = m.group(1).strip().rstrip(".")
#             # Filter out dates and garbage
#             if len(reason) > 3 and not re.match(r"^\d", reason):
#                 fields["cancellation_reason"] = {
#                     "value": reason,
#                     "confidence": 0.78,
#                     "source": "stage1_can_reason",
#                 }

#     # --- BALANCE DUE ---
#     if "balance_due" not in fields:
#         m = _BALANCE_DUE_PATTERNS.search(text)
#         if m:
#             fields["balance_due"] = {
#                 "value": "$" + m.group(1).strip(),
#                 "confidence": 0.83,
#                 "source": "stage1_inv_balance",
#             }

#     # --- ISSUE DATE ---
#     if "issue_date" not in fields:
#         m = _ISSUE_DATE_PATTERNS.search(text)
#         if m:
#             fields["issue_date"] = {
#                 "value": m.group(1).strip(),
#                 "confidence": 0.82,
#                 "source": "stage1_inv_issue_date",
#             }

#     # --- REMIT INFO ---
#     if "remit_info" not in fields:
#         m = _REMIT_PATTERNS.search(text)
#         if m:
#             remit = m.group(1).strip()
#             if len(remit) > 3:
#                 fields["remit_info"] = {
#                     "value": remit,
#                     "confidence": 0.78,
#                     "source": "stage1_inv_remit",
#                 }


# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """Main entry point for Stage 1 extraction"""
#     if not lines:
#         return {}
    
#     extractor = StatefulExtractor()
    
#     for raw in lines:
#         line = raw.strip()
#         if line:
#             extractor.update_role(line)
#             extractor.extract(line)
    
#     extractor.finalize()
#     _safe_sweep(lines, extractor.fields)
#     _extract_can_inv_fields(lines, extractor.fields)   # ← NEW: CAN + INV fields
    
#     return extractor.fields


# def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """Alias for backward compatibility"""
#     return extract_fields(lines, layout_elements)

# # stage1_deterministic_agent.py
# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
# IMPROVED VERSION - Fixes for:
# 1. Insured name extraction (blocking mortgagee terms, product names)
# 2. Carrier name extraction (multi-line support)
# 3. Loan number extraction (blocking document references)
# 4. Policy number extraction (better patterns)
# """
# import re
# from typing import Dict, List, Set, Tuple
# from enum import Enum, auto


# # ============================================================
# # ROLES
# # ============================================================

# class Role(Enum):
#     NONE = auto()
#     POLICY_HEADER = auto()
#     INSURED_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MAILING_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()
#     CARRIER_BLOCK = auto()
#     PRODUCER_BLOCK = auto()  # NEW: Skip names in producer/agent sections


# # ============================================================
# # REGEX PATTERNS
# # ============================================================

# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# DATE_WRITTEN_RE = re.compile(
#     r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
#     re.I
# )
# # Abbreviated month names: NOV 09 2021, DEC 1 2022, etc.
# DATE_ABBREV_RE = re.compile(
#     r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
#     re.I
# )
# PO_BOX_RE = re.compile(r"p\.?o\.?\s*box", re.I)
# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge|pl|place"
#     r")\b",
#     re.I
# )

# # Policy number patterns - multiple variants
# POLICY_REGEX_VARIANTS = [
#     re.compile(r"^[A-Z]{2,4}[-\s]?\d{7,12}[-\s]?\d{0,2}$", re.I),  # DPC0076173896-1
#     re.compile(r"^\d{9,12}$"),  # 2004939477
#     re.compile(r"^\d{9}\s*\d{3}\s*\d{1}$"),  # 602732135 664 1
#     re.compile(r"^[A-Z]{2,4}\d{1,2}[-]?\d{9,12}$", re.I),  # OKH3-109194373
#     re.compile(r"^\d{8,12}[-\s]?\d{1,2}$"),  # 04038598 - 1
#     re.compile(r"^\d{2}-[A-Z]{2}-[A-Z]\d{3}-\d$", re.I),  # 81-BE-N065-5 (State Farm)
#     re.compile(r"^\d{2}-[A-Z]{2,4}-[A-Z0-9]{3,8}$", re.I),  # Generic NN-XX-XXXXX
#     # --- INS observation batch additions (Section 2) ---
#     # Spaced numeric: "821 736 168", "063 078 674"
#     re.compile(r"^\d{3}\s\d{3}\s\d{3}$"),
#     # Dashed numeric with space: "02050414 - 5"
#     re.compile(r"^\d{8}\s*-\s*\d{1,2}$"),
#     # Hyphenated alphanumeric: "TX-HOV-00032479-01", "60-04077225-2019"
#     re.compile(r"^[A-Z]{2}-[A-Z]{2,4}-\d{5,}-\d{1,2}$", re.I),
#     re.compile(r"^\d{2}-\d{8,}-\d{4}$"),
#     # Alpha prefix with space: "ACP BPH 7885310416", "LAH0195988"
#     re.compile(r"^[A-Z]{2,4}\s?[A-Z]{0,4}\s?\d{7,12}$", re.I),
#     # Alpha suffix: "60092029BP"
#     re.compile(r"^\d{8,10}[A-Z]{2}$", re.I),
#     # Commercial style: "34 X42393-01"
#     re.compile(r"^\d{2}\s[A-Z]\d{5,}-\d{1,2}$", re.I),
#     # Flood style: "99-047002652-2020"
#     re.compile(r"^\d{2}-\d{9,}-\d{4}$"),
# ]

# STATE_ABBREV = {
#     "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
#     "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
#     "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
#     "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
#     "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
#     "DC", "PR", "VI"
# }


# # ============================================================
# # LABELS / TRIGGERS
# # ============================================================

# POLICY_LABELS = {
#     "policy number", "policy no", "policy #",
#     "your policy number", "policynumber",
#     "dwelling policy number",
#     "account number", "your account number","policy id",
#     "policy certificate number",
#     "certificate number",
#     "master policy no", 
# }

# INSURED_LABELS = {
#     "insured", "named insured",
#     "insured name", "insured name and address",
#     "insured mailing", "insured mailing name",
#     "insured mailing name and address",
#     "policyholder", "policy holder",
#     "policyholder(s)",  # ADDED for "Policyholder(s) TIM RASK"
#     "policyholders",
#     "policyholder/insured", "policyholder/named insured",
#     "first named insured",
#     "named insured and address",
#     "name and address of insured",  # ADDED
# }

# # CRITICAL: Terms that should NOT be captured as insured names
# BAD_INSURED_TERMS = {
#     # Mortgagee-related (most common error)
#     "mortgagee", "first mortgagee", "second mortgagee", "third mortgagee",
#     "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
#     "loss payee", "lienholder", "lender",
#     "isaoa", "atima", "isaoa atima", "isaoa/atima",
#     "lien holder", "1st mortgagee copy",
    
#     # Product names
#     "homesaver policy", "homesaver polcy", "homeowners policy",
#     "dwelling policy", "special form", "wind only policy",
#     "ultrapack plus", "mobilehome policy", "condominium owners",
#     "mobilehome", "house & home",
    
#     # Insurance company fragments
#     "insurance exchange", "insurance company", "insurance group",
#     "insurance corp", "insurance mutual",
    
#     # Document structure
#     "policy period", "policy type", "coverage",
#     "endorsement", "declarations", "summary",
#     "premium", "deductible", "page", "continued",
#     "information as of",
    
#     # Agencies/agents/producers (CRITICAL - fixes Michael Ames issue)
#     "agency", "agent", "services", "producer",
#     "goosehead", "goosehead insurance",
    
#     # Service centers (CRITICAL - fixes Mortgagee Relations Center)
#     "relations center", "mortgagee relations", "lender relations",
#     "customer service", "service center",
#     "claims center", "billing center",
    
#     # Website/online instructions (CRITICAL - fixes aegisinsurance.com)
#     "website", ".com", "online", "go to", "simply go",
#     "click here", "select", "menu bar", "policyholders",
#     "make a payment", "pay online",
    
#     # Marketing slogans (CRITICAL - fixes "You're in good hands")
#     "you're in good hands", "good hands",
#     "like a good neighbor", "on your side",
#     "we know a thing or two", "because we've seen",
    
#     # Other noise
#     "other interest", "interested parties", "certificate holder",
#     "office use", "message", "messages",
#     "risk management", "department",
#     "third party notice", "notice of",
# }

# BAD_NAME_PHRASES = {
#     # Sections
#     "coverage", "endorsement", "deductible",
#     "policy conditions", "forms and endorsements",
#     "policy period", "premium", "billing",
#     "invoice", "notice", "summary", "schedule",
#     "page", "continued", "section",
    
#     # Mortgagee related (CRITICAL)
#     "mortgagee", "loss payee", "lienholder",
#     "first mortgagee", "second mortgagee",
#     "isaoa", "atima", "lien holder",
    
#     # Products / carriers
#     "homeowners", "dwelling", "ultrapack",
#     "insurance company", "insurance exchange",
#     "insurance group", "homesaver",
#     "mobilehome",
    
#     # Agencies/producers (CRITICAL - fixes Michael Ames)
#     "agency", "agent", "services", "producer",
#     "goosehead", "insurance agency",
    
#     # Service centers (CRITICAL - fixes Mortgagee Relations Center)
#     "relations center", "mortgagee relations", "lender relations",
#     "customer service", "service center",
#     "claims center", "billing center",
#     "risk management", "department",
    
#     # Website/online (CRITICAL - fixes aegisinsurance.com)
#     "website", ".com", "online", "go to", "simply go",
#     "click here", "select", "menu bar",
#     "make a payment", "pay online",
    
#     # Marketing slogans (CRITICAL - fixes "You're in good hands")
#     "you're in good hands", "good hands",
#     "like a good neighbor", "on your side",
#     "we know a thing or two",
    
#     # Noise / instructions
#     "detach this", "return with",
#     "third party notice", "notice of",
    
#     # Other
#     "your insurer", "insurer:", "office use",
#     "information as of", "page 1 of", "page 2 of",
# }

# PROPERTY_TRIGGERS = {
#     "property address", "property insured",
#     "location of insured property", "residence premises",
#     "described location", "risk location",
#     "insured location", "location of property",
#     "premises address", "located at",
#     "coverage detail for",  # Encompass: "Coverage Detail for 136 Old Altamont..."
#     "insured location covered by this policy",
#     "location",  # State Farm: "Location: 2971 GA HIGHWAY 93 S"
# }

# # Property labels for inline extraction (Label: Value format)
# PROPERTY_INLINE_LABELS = {
#     "property address", "risk location",
#     "location of insured property",
#     "premises address", "property location",
#     "property insured",  # ADDED for "Property Insured: 4616 HERITAGE RD"
#     "location",  # State Farm: "Location: <address>"
# }

# # Standalone "Address:" can be a property address in declarations contexts
# # (e.g., Erie Supplemental Declarations: "Address: 421 GEORGESVILLE BD")
# PROPERTY_ADDRESS_STANDALONE = {"address"}

# MAILING_TRIGGERS = {
#     "mailing address", "mail address",
#     "insured mailing", "correspondence address",
#     "send mail to", "applicant address",
# }

# MORTGAGE_TRIGGERS = {
#     "mortgagee", "loss payee",
#     "lienholder", "other interest",
#     "other interested parties", "certificate holder",
#     "mortgagee full name", "lien holder",
#     "1st mortgagee", "2nd mortgagee", "first mortgagee", "second mortgagee",
#     "holder",  # State Farm: "holder: CAPITAL CITY BANK"
#     # --- INS observation batch additions (Section 4) ---
#     "mortgage(s)", "mortgage holder",
#     "additional interest(s)", "additional interest",
#     "mortgage servicing agency",
#     "unit owner mortgagee",
#     "mortgage or interested party",
#     "additional interest/mortgage/trust",
#     "mortgage or loss payee",
#     "mortgagee/loss payee","mortgage holder",
#     "servicer", 
#     # Note: Removed "lender" as it can trigger on "Lender Relations Center"
# }

# # Patterns that look like mortgage triggers but are actually service centers
# MORTGAGE_FALSE_POSITIVES = {
#     "lender relations center",
#     "mortgagee relations center",
#     "mortgage relations center",
# }

# # NEW: Producer/Agent triggers - names after these should NOT be captured as insured
# PRODUCER_TRIGGERS = {
#     "producer", "agent", "agency",
#     "your agent", "insurance agent",
#     "sales rep", "representative",
# }

# CARRIER_TRIGGERS = {
#     "insurance company", "insurance exchange",
#     "insurance group", "insurance provided by",
#     "issued by", "underwritten by", "insurer",
#     "policy underwritten by", "your insurer",
# }

# LOAN_LABELS = {
#     "loan number", "loan no", "loan #", "loan id",
#     "mortgage loan number", "ln #",
#     # --- INS observation batch additions (Section 3) ---
#     "loan/contract number", "loan/contract #",
#     "loan:", "mortgage loan no",
#     "mortgage loan no.", "loan no.",
# }

# DATE_LABELS_EFFECTIVE = {
#     "effective date", "policy effective date",
#     "coverage begins", "term start date",
#     "change effective date","inception date",
#     "coverage effective",
#     "term effective", "policy period",
# }

# DATE_LABELS_EXPIRATION = {
#     "expiration date", "policy expiration date",
#     "coverage ends", "term end date", "expires",
#     "through", "term expires",
#     "coverage through",
#     "expiration", "policy period",
#     # Encompass format: "through July 1, 2021 at 12:01 a.m."
# }

# BAD_ADDRESS_PHRASES = {
#     "coverage", "premium", "deductible",
#     "policy period", "effective", "expiration",
#     "billing", "payment", "invoice", "notice",
# }

# # ============================================================
# # NEW: BILLING / PREMIUM / CANCELLATION LABELS
# # ============================================================

# TOTAL_PREMIUM_LABELS = {
#     "total premium",
#     "annual premium",
#     "total policy premium",
#     "policy premium",
#     "total annual premium",
#     "premium total","total amount",
#     "policy total",
#     "amount of premium", "total residence premium"
# }

# BALANCE_DUE_LABELS = {
#     "balance due",
#     "amount due",
#     "minimum due",
#     "total amount due",
#     "balance (to pay in full)",
#     "current amount due",
# }

# REMIT_INFO_LABELS = {
#     "remit to",
#     "make payment to",
#     "send payment to",
#     "payable to",
#     "remittance address",
#     "payment address",
# }

# ISSUE_DATE_LABELS = {
#     "issue date",
#     "bill date",
#     "invoice date",
#     "statement date",
#     "date issued",
# }

# CANCELLATION_DATE_LABELS = {
#     "cancellation date",
#     "effective date of cancellation",
#     "termination effective",
#     "cancel effective",
#     "cancellation effective",
# }

# CANCELLATION_REASON_KEYWORDS = {
#     "nonpayment",
#     "non-payment",
#     "underwriting",
#     "requested by insured",
#     "mortgage interest removed",
#     "third party removed",
#     "policy change",
#     "cancelled for nonpayment","failure to comply",
#     "risk unacceptable",
#     "material misrepresentation", 
# }

# # ============================================================
# # HELPERS
# # ============================================================

# def _clean(v: str) -> str:
#     """Clean extracted value"""
#     v = re.sub(r"\s+", " ", v)
#     v = v.strip(" ,.;:-")
#     return v


# def _normalize_name(v: str) -> str:
#     """Normalize name format"""
#     if not v:
#         return ""
    
#     v = v.strip()
    
#     # Remove common prefixes/suffixes
#     v = re.sub(r"^(named insured|insured|policyholder)[:\s]*", "", v, flags=re.I)
#     v = re.sub(r"\s*(beginning|effective|since|policy period).*$", "", v, flags=re.I)
    
#     # Handle "LASTNAME, FIRSTNAME" format BUT NOT company names with comma
#     # Don't swap if it contains entity suffixes
#     if "," in v and v.count(",") == 1:
#         has_entity = any(w in v.lower() for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
#         if not has_entity:
#             parts = [p.strip() for p in v.split(",") if p.strip()]
#             if len(parts) == 2 and not any(c.isdigit() for c in v):
#                 # Only swap if both parts look like names (not addresses)
#                 if not any(w.upper() in STATE_ABBREV for w in parts[1].split()):
#                     return f"{parts[1]} {parts[0]}"
    
#     return v.strip()


# def _is_phone_number(v: str) -> bool:
#     """
#     Check if value is a phone number
#     CONSERVATIVE: Returns True only for values that are CLEARLY phone numbers
#     """
#     # If the original value has letters, it's likely not a phone number
#     if any(c.isalpha() for c in v):
#         return False
    
#     # Extract only digits
#     digits = ''.join(c for c in v if c.isdigit())
    
#     # Phone numbers are exactly 7, 10, or 11 digits
#     # If longer than 11, it's definitely not a phone number
#     if len(digits) > 11:
#         return False
    
#     # Check if it has phone formatting (parentheses, dashes in right places)
#     # Only flag as phone if it has ACTUAL phone formatting
#     if re.fullmatch(r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}', v.strip()):
#         return True
    
#     # Only 7 digits with dash: xxx-xxxx format
#     if re.fullmatch(r'\d{3}[-.\s]\d{4}', v.strip()):
#         return True
    
#     # For pure numeric strings, DON'T assume they're phone numbers
#     # because policy numbers are often 10 digits too
#     # Only flag as phone if it has formatting
    
#     return False


# def _is_document_reference(v: str) -> bool:
#     """Check if value looks like a document reference code, not real data"""
#     v_clean = v.strip()
    
#     # Pattern: digits_digits_digits (e.g., 19660_859561_6)
#     if re.match(r'^\d+_\d+(_\d+)?$', v_clean):
#         return True
    
#     # Page references
#     if re.match(r'^page\s*\d+', v_clean, re.I):
#         return True
    
#     # Very long numeric strings with many zeros
#     digits = ''.join(c for c in v_clean if c.isdigit())
#     if len(digits) > 15:
#         return True
    
#     # More than 50% zeros in long number
#     if len(digits) > 10:
#         zero_count = digits.count('0')
#         if zero_count > len(digits) * 0.5:
#             return True
    
#     return False


# def _looks_like_name(text: str) -> bool:
#     """
#     Check if text looks like a person/company name
#     IMPROVED: Better filtering of mortgagee terms and noise
#     """
#     if not text or len(text) < 3:
#         return False
    
#     text = text.strip()
#     ll = text.lower()
    
#     # CRITICAL: Block mortgagee-related terms
#     for bad_term in BAD_INSURED_TERMS:
#         if bad_term in ll:
#             return False
    
#     # Block known bad phrases
#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False
    
#     # Block if ends with colon (it's a label)
#     if text.endswith(":"):
#         return False
    
#     # Block lines with too many special chars
#     special = sum(1 for c in text if c in "()[]{}|\\/<>@#$%^&*=+")
#     if special > 2:
#         return False
    
#     # Block if starts with certain bad patterns
#     bad_starts = (
#         "policy", "coverage", "premium", "page", "section",
#         "effective", "expiration", "the ", "this ", "your ",
#         "or ", "for ", "to ", "from ", "with ",
#     )
#     # NOTE: removed "and " from bad_starts to allow "ROBERT and MARY" style names
#     if any(ll.startswith(w) for w in bad_starts):
#         return False
    
#     # Block if ends with label-like patterns (but not if it's a person's name)
#     bad_ends = (
#         " address", " information", " number",
#         " period", " type", " date", " copy", " notice",
#     )
#     # Note: removed " name" because "NAME" can be a valid surname (e.g., "JOHN NAME", "DUMMY NAME")
#     if any(ll.endswith(w) for w in bad_ends):
#         return False
    
#     # Allow entities with digits (LLC, Corp, etc.)
#     has_entity = any(w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd", "bank"))
    
#     # Check if it's a multi-person name (contains "and" or "&" between name parts)
#     has_and_connector = bool(re.search(r'\b(and|&)\b', ll))
    
#     # Block digits unless it's an entity
#     if any(c.isdigit() for c in text) and not has_entity:
#         return False
    
#     words = text.replace(",", " ").split()
#     word_count = len(words)
    
#     # Entity names can be longer; multi-person names can be longer too
#     if has_entity:
#         if not (2 <= word_count <= 12):
#             return False
#     elif has_and_connector:
#         # Multi-person names like "ROBERT J BARRON and DANIEL PRYCE" can have 6-8 words
#         if not (4 <= word_count <= 10):
#             return False
#     else:
#         if not (2 <= word_count <= 6):
#             return False
    
#     # At least 1 word should start with uppercase
#     caps = sum(1 for w in words if w and w[0].isupper())
#     if caps < 1:
#         return False
    
#     # Block if looks like an address
#     if STREET_RE.search(text) or PO_BOX_RE.search(text):
#         return False
    
#     # Block if has state abbreviation followed by ZIP
#     if re.search(r"\b[A-Z]{2}\s*\d{5}", text):
#         return False
    
#     return True


# def _looks_like_policy(v: str) -> bool:
#     """
#     Check if value looks like a policy number
#     IMPROVED: Better blocking of bad patterns
#     """
#     if not v:
#         return False
    
#     v_original = v
#     v_clean = re.sub(r"[\s\-]", "", v)
    
#     # CRITICAL: Block phone numbers FIRST
#     if _is_phone_number(v_original):
#         return False
    
#     # Block document references
#     if _is_document_reference(v_original):
#         return False
    
#     # Block dates - numeric and written
#     if DATE_RE.search(v_original) or DATE_WRITTEN_RE.search(v_original):
#         return False
    
#     # Block if contains date-like words
#     date_words = ('january', 'february', 'march', 'april', 'may', 'june',
#                   'july', 'august', 'september', 'october', 'november', 'december',
#                   'effective', 'expiration')
#     if any(w in v_original.lower() for w in date_words):
#         return False
    
#     # Block pure year references (2023, 2024, etc.)
#     if v_clean.isdigit() and len(v_clean) == 4 and v_clean.startswith(('19', '20')):
#         return False
    
#     # Block ZIP codes (5 or 9 digits)
#     if re.fullmatch(r"\d{5}(-\d{4})?", v_clean):
#         return False
    
#     # Block state+number patterns (NC27102, MI48007)
#     if re.match(r'^[A-Z]{2}\d{5,}$', v_clean):
#         return False
    
#     # Block very short values
#     if len(v_clean) < 6:
#         return False
    
#     # Block very long values
#     if len(v_clean) > 30:
#         return False
    
#     # Count digits and letters
#     digits = sum(c.isdigit() for c in v_clean)
#     letters = sum(c.isalpha() for c in v_clean)
    
#     # Must have at least 4 digits (lowered slightly to handle "81-BE-N065-5" = 4 digits)
#     if digits < 4:
#         return False
    
#     # Pure numeric: 6-14 digits is OK
#     if v_clean.isdigit():
#         return 6 <= len(v_clean) <= 14
    
#     # Mixed: check against patterns
#     for rx in POLICY_REGEX_VARIANTS:
#         if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
#             return True
    
#     # Fallback: alphanumeric with substantial digits (lowered to 4 for NN-XX-XXXXX formats)
#     if letters >= 1 and digits >= 4:
#         return True
    
#     return False


# def _looks_like_loan_number(v: str) -> bool:
#     """
#     Check if value looks like a loan number
#     IMPROVED: Better filtering, stricter for short numbers
#     """
#     if not v:
#         return False
    
#     # Block document references
#     if _is_document_reference(v):
#         return False
    
#     # Block phone numbers (including formatted ones)
#     if _is_phone_number(v):
#         return False
    
#     # Extract digits
#     digits = ''.join(c for c in v if c.isdigit())
    
#     # Loan numbers are typically 6-18 digits
#     # (expanded from 8-15 per INS observation batch Section 3)
#     if len(digits) < 6 or len(digits) > 18:
#         return False
    
#     # Block if too many consecutive zeros (padding patterns)
#     if '000000' in digits:
#         return False
    
#     # Block if more than 50% zeros in longer numbers
#     if len(digits) > 10:
#         zero_count = digits.count('0')
#         if zero_count > len(digits) * 0.5:
#             return False
    
#     # Block dates
#     if DATE_RE.search(v):
#         return False
    
#     return True


# def _looks_like_address(line: str) -> bool:
#     """Check if line looks like an address"""
#     if not line or len(line) < 5:
#         return False
    
#     ll = line.lower()
    
#     # Block known bad phrases
#     if any(b in ll for b in BAD_ADDRESS_PHRASES):
#         return False
    
#     # Block if it's just a label
#     if line.strip().endswith(":"):
#         return False
    
#     # PO Box - VALID ADDRESS
#     if PO_BOX_RE.search(line):
#         return True
    
#     # Street address pattern
#     if STREET_RE.search(line):
#         return True
    
#     # Has number + state abbreviation + ZIP
#     if re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", line):
#         return True
    
#     # Has state abbreviation + ZIP (city, state zip format)
#     if re.search(r"\b[A-Z]{2}\s+\d{5}", line):
#         parts = re.split(r"\b[A-Z]{2}\s+\d{5}", line)
#         if parts and len(parts[0].strip()) > 5:
#             return True
    
#     # Has street number and reasonable length
#     has_number = bool(re.search(r"^\d+\s+", line.strip()))
#     word_count = len(line.split())
#     if has_number and word_count >= 3:
#         return True
    
#     return False


# def _looks_like_carrier(line: str) -> bool:
#     """Check if line looks like an insurance carrier name"""
#     ll = line.lower()
    
#     # Must have "insurance" or "indemnity" or "casualty" somewhere
#     if not any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance', ' ins ')):
#         if not ll.endswith(' ins'):
#             return False
    
#     # Should have company type
#     if not any(w in ll for w in ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')):
#         return False
    
#     # Block agencies
#     if any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
#         return False
    
#     # Reasonable length
#     words = line.split()
#     if not (2 <= len(words) <= 10):
#         return False
    
#     return True


# def _clean_carrier_name(name: str) -> str:
#     """Strip noise prefixes/suffixes from carrier names"""
#     # Strip label prefixes that aren't part of the actual carrier name
#     name = re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*',
#                   '', name, flags=re.I).strip()
#     noise_prefixes = (
#         "member ", "a member of ", "subsidiary of ",
#         "underwritten by ", "issued by ", "your insurer ",
#     )
#     ll = name.lower()
#     for prefix in noise_prefixes:
#         if ll.startswith(prefix):
#             name = name[len(prefix):]
#             break
#     # Strip trailing noise
#     name = re.sub(
#         r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
#         r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
#         '', name, flags=re.I
#     ).strip()
#     return name


# def _extract_carrier_name(line: str) -> str:
#     """
#     Extract just the insurance carrier name from a line that may contain extra noise.
#     Stops at the last company-type word (company, exchange, group, etc.) and 
#     truncates anything after it (like 'RENEWAL CERTIFICATE', addresses, etc.)
#     """
#     if not line:
#         return line
    
#     # First apply standard cleaning
#     line = _clean_carrier_name(line)
    
#     # Strip leading OCR garbage (apostrophes, weird chars)
#     line = re.sub(r"^[^A-Za-z0-9]+", "", line).strip()
    
#     # Find where the company name likely ends by looking for company-type words
#     # Use the LAST occurrence (for "State Farm Fire and Casualty Company")
#     company_type_words = ['company', 'exchange', 'group', 'mutual', 
#                           'corp', 'corporation', 'indemnity', 'casualty']
    
#     ll = line.lower()
#     best_end = -1
    
#     for ct in company_type_words:
#         idx = ll.rfind(ct)  # rightmost occurrence
#         if idx >= 0:
#             end = idx + len(ct)
#             if end > best_end:
#                 best_end = end
    
#     if best_end > 0:
#         result = line[:best_end].strip()
#     else:
#         result = line
    
#     # Must still contain 'insurance', 'indemnity', or 'casualty'
#     if not any(w in result.lower() for w in ('insurance', 'indemnity', 'casualty', 'assurance', 'fire')):
#         return ""
    
#     # Reasonable length check
#     words = result.split()
#     if len(words) > 10:
#         # Too long — probably a merged line; find the carrier within it
#         # Look for a window ending at a company type
#         for i in range(len(words) - 1, -1, -1):
#             if any(ct in words[i].lower() for ct in company_type_words):
#                 # Find reasonable start (up to 8 words back)
#                 start = max(0, i - 7)
#                 candidate = " ".join(words[start:i+1])
#                 if any(w in candidate.lower() for w in ('insurance', 'indemnity', 'casualty')):
#                     result = candidate
#                     break
    
#     # Strip leading OCR artifact words (words that don't belong to a carrier name)
#     # Look for known carrier name patterns — find where the "real" name starts
#     words = result.split()
#     if len(words) >= 2:
#         for i in range(1, len(words)):  # Start at 1: need at least one prefix word
#             rest = " ".join(words[i:])
#             rest_ll = rest.lower()
#             if any(x in rest_ll for x in ('insurance', 'indemnity', 'casualty', 'fire')):
#                 if any(x in rest_ll for x in company_type_words):
#                     # Check if the prefix looks like OCR noise (all lowercase)
#                     prefix = " ".join(words[:i])
#                     if all(not c.isupper() for c in prefix if c.isalpha()):
#                         result = rest
#                     break
    
#     return result.strip()

# def _extract_date(line: str, label_set: set) -> str:
#     """Extract date from line if it matches label pattern"""
#     ll = line.lower()
    
#     if not any(k in ll for k in label_set):
#         return None
    
#     # Try written format first: January 15, 2024
#     m = DATE_WRITTEN_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try abbreviated month format: NOV 09 2021
#     m = DATE_ABBREV_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try numeric format: 01/15/2024
#     m = DATE_RE.search(line)
#     if m:
#         return m.group(0)
    
#     # Try extracting after colon
#     if ":" in line:
#         _, _, val = line.partition(":")
#         val = val.strip()
#         m = (DATE_WRITTEN_RE.search(val) or DATE_ABBREV_RE.search(val)
#              or DATE_RE.search(val))
#         if m:
#             return m.group(0)
    
#     return None


# # ============================================================
# # STATEFUL EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}
#         self.carrier_accumulator: List[str] = []  # For multi-line carrier names
#         self.address_accumulator: List[str] = []
#         self._partial_insured: str = ""  # For multi-line insured names
#         self._pending_premium: bool = False  # For multi-line premium extraction
#         self._pending_policy_period: bool = False  # For Policy Period: on its own line
    
#     def update_role(self, line: str):
#         """Update current parsing role based on section headers"""
#         ll = line.lower().strip()
        
#         # Check for role triggers (order matters - more specific first)
#         if any(k in ll for k in POLICY_LABELS):
#             self._flush_accumulators()
#             self.role, self.window = Role.POLICY_HEADER, 8
#         # "Insured Mailing Name and Address" = INSURED block (captures both name + address)
#         elif "insured" in ll and "mailing" in ll:
#             self._flush_accumulators()
#             self.role, self.window = Role.INSURED_BLOCK, 12
#         elif any(k in ll for k in MAILING_TRIGGERS):
#             self._flush_accumulators()
#             self.role, self.window = Role.MAILING_BLOCK, 8
#         elif any(k in ll for k in INSURED_LABELS) and "payor" not in ll:
#             self._flush_accumulators()
#             self.role, self.window = Role.INSURED_BLOCK, 12
#         elif any(k in ll for k in PROPERTY_TRIGGERS):
#             self._flush_accumulators()
#             self.role, self.window = Role.PROPERTY_BLOCK, 8
#         # Standalone "Address:" line can indicate property in declarations context
#         elif re.match(r'^address\s*[:.]', ll) and "property_address" not in self.fields:
#             self._flush_accumulators()
#             self.role, self.window = Role.PROPERTY_BLOCK, 5
#         elif any(k in ll for k in MORTGAGE_TRIGGERS):
#             # Check if it's a false positive (service center header)
#             if not any(fp in ll for fp in MORTGAGE_FALSE_POSITIVES):
#                 self._flush_accumulators()
#                 self.role, self.window = Role.MORTGAGE_BLOCK, 10
#         elif any(k in ll for k in PRODUCER_TRIGGERS):
#             # Producer/agent section - skip names here
#             self._flush_accumulators()
#             self.role, self.window = Role.PRODUCER_BLOCK, 6
#         elif any(k in ll for k in CARRIER_TRIGGERS):
#             # DON'T flush carrier accumulator - we might need to combine
#             self._flush_accumulators(entering_carrier_block=True)
#             self.role, self.window = Role.CARRIER_BLOCK, 6
    
#     def _flush_accumulators(self, entering_carrier_block=False):
#         """Save accumulated multi-line values before role change"""
#         # DON'T flush carrier accumulator if entering carrier block
#         # because we might need to combine it with the incoming line
#         if not entering_carrier_block:
#             if self.carrier_accumulator and "carrier_name" not in self.fields:
#                 combined = " ".join(self.carrier_accumulator)
#                 if _looks_like_carrier(combined):
#                     self.fields["carrier_name"] = {
#                         "value": combined.upper(),
#                         "confidence": 0.96,
#                         "source": "accumulated",
#                     }
#                 self.carrier_accumulator = []
        
#         # Flush address accumulator
#         if self.address_accumulator:
#             addr = " ".join(self.address_accumulator)
#             if "property_address" not in self.fields:
#                 self.fields["property_address"] = {
#                     "value": addr,
#                     "confidence": 0.94,
#                     "source": "accumulated",
#                 }
#             self.address_accumulator = []
    
#     def extract(self, line: str):
#         """Main extraction logic for each line"""
#         # Always try inline extraction first
#         self._inline(line)
        
#         # Try carrier extraction from any line (multi-line support)
#         self._try_carrier_accumulation(line)
        
#         # Role-based extraction
#         if self.window > 0:
#             if self.role == Role.POLICY_HEADER:
#                 self._policy(line)
#             elif self.role == Role.INSURED_BLOCK:
#                 self._insured(line)
#             elif self.role == Role.PROPERTY_BLOCK:
#                 self._property(line)
#             elif self.role == Role.MAILING_BLOCK:
#                 self._mailing(line)
#             elif self.role == Role.MORTGAGE_BLOCK:
#                 self._mortgage(line)
#             elif self.role == Role.CARRIER_BLOCK:
#                 self._carrier(line)
            
#             self.window -= 1
#             if self.window == 0:
#                 self._flush_accumulators()
#                 self.role = Role.NONE
    
#     def _try_carrier_accumulation(self, line: str):
#         """Try to accumulate carrier name across lines"""
#         if "carrier_name" in self.fields:
#             return
        
#         ll = line.lower()
#         clean = line.strip().replace("*", "")
        
#         # Skip label lines (ending with ":" or ":.") — these aren't carrier name parts
#         stripped = clean.rstrip(".")
#         if stripped.endswith(":"):
#             return
        
#         # Check if this line contains 'insurance'
#         if 'insurance' in ll:
#             # If we have accumulated a prefix, ALWAYS try to combine
#             if self.carrier_accumulator:
#                 combined = " ".join(self.carrier_accumulator) + " " + clean
#                 combined_lower = combined.lower()
#                 # If combined has insurance + company type, use it
#                 if 'insurance' in combined_lower and any(w in combined_lower for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual')):
#                     if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
#                         carrier_val = _extract_carrier_name(combined)
#                         self.fields["carrier_name"] = {
#                             "value": carrier_val.upper(),
#                             "confidence": 0.97,
#                             "source": "multi_line_combined",
#                         }
#                         self.carrier_accumulator = []
#                         return
            
#             # No accumulator - check if this line alone is a complete carrier
#             carrier_candidate = _extract_carrier_name(clean)
#             if carrier_candidate and _looks_like_carrier(carrier_candidate):
#                 self.fields["carrier_name"] = {
#                     "value": carrier_candidate.upper(),
#                     "confidence": 0.95,
#                     "source": "direct",
#                 }
#                 self.carrier_accumulator = []
#                 return
            
#             # Start accumulating (e.g., "Erie INSURANCE" without company type)
#             if not self.carrier_accumulator:
#                 if not any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
#                     self.carrier_accumulator = [clean]
#                     return
        
#         # If accumulator has 'insurance' and current line is a company-type word
#         # e.g., accumulator = ["Erie INSURANCE"], current line = "Exchange"
#         elif self.carrier_accumulator and any('insurance' in a.lower() for a in self.carrier_accumulator):
#             company_types = ('exchange', 'company', 'group', 'mutual', 'corp', 'corporation')
#             if any(w in ll for w in company_types):
#                 combined = " ".join(self.carrier_accumulator) + " " + clean
#                 combined_lower = combined.lower()
#                 if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
#                     carrier_val = _extract_carrier_name(_clean_carrier_name(combined))
#                     self.fields["carrier_name"] = {
#                         "value": carrier_val.upper(),
#                         "confidence": 0.97,
#                         "source": "multi_line_combined",
#                     }
#                     self.carrier_accumulator = []
#                     return
        
#         # Check if this might be first part of multi-line carrier
#         elif clean.isupper() and len(clean.split()) <= 2 and not any(c.isdigit() for c in clean):
#             # Might be company name prefix like "ADIRONDACK"
#             noise_words = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", "NOTICE", "PO", "BOX"}
#             words = clean.split()
#             if words and not any(w in noise_words for w in words):
#                 if all(len(w) >= 3 for w in words):  # Each word should be substantial
#                     self.carrier_accumulator = [clean]
    
#     def _inline(self, line: str):
#         """Extract from inline patterns (Label: Value)"""
#         ll = line.lower()

#         # ============================================================
#         # POLICY NUMBER
#         # ============================================================
#         if "policy_number" not in self.fields:
#             if ":" in line and any(k in ll for k in POLICY_LABELS):
#                 _, _, v = line.partition(":")
#                 v = _clean(v)

#                 if re.match(r'^\d{9}\s+\d{3}\s+\d$', v):
#                     v_no_space = v.replace(" ", "")
#                     if _looks_like_policy(v_no_space):
#                         self.fields["policy_number"] = {
#                             "value": v,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }
#                 else:
#                     v = re.sub(r"\s+(\d)$", r"-\1", v)
#                     v_no_space = v.replace(" ", "")
#                     if _looks_like_policy(v_no_space):
#                         self.fields["policy_number"] = {
#                             "value": v_no_space,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }

#             elif any(k in ll for k in POLICY_LABELS):
#                 for label in sorted(POLICY_LABELS, key=len, reverse=True):
#                     idx = ll.find(label)
#                     if idx >= 0:
#                         after = line[idx + len(label):].strip().lstrip(":").strip()
#                         for token in after.split():
#                             candidate = _clean(token)
#                             if _looks_like_policy(candidate.replace(" ", "")):
#                                 self.fields["policy_number"] = {
#                                     "value": candidate,
#                                     "confidence": 0.95,
#                                     "source": "inline_no_colon",
#                                 }
#                                 break
#                         if "policy_number" in self.fields:
#                             break

#         # ============================================================
#         # PROPERTY ADDRESS
#         # ============================================================
#         if "property_address" not in self.fields and ":" in line:
#             if any(k in ll for k in PROPERTY_INLINE_LABELS):
#                 _, _, v = line.partition(":")
#                 v = v.strip()
#                 if v and _looks_like_address(v):
#                     self.fields["property_address"] = {
#                         "value": v,
#                         "confidence": 0.98,
#                         "source": "inline",
#                     }

#         if "property_address" not in self.fields and "coverage detail for" in ll:
#             m = re.search(r'coverage\s+detail\s+for\s+(.+)', line, re.I)
#             if m:
#                 addr = re.sub(r'\s*\(continued\).*$', '', m.group(1), flags=re.I).strip()
#                 if _looks_like_address(addr):
#                     self.fields["property_address"] = {
#                         "value": addr,
#                         "confidence": 0.97,
#                         "source": "inline_coverage_detail",
#                     }

#         # ============================================================
#         # INSURED NAME
#         # ============================================================
#         if "insured_name" not in self.fields and ":" in line:
#             label, _, val = line.partition(":")
#             label_lower = label.lower().strip()

#             if any(k in label_lower for k in ("insured", "policyholder")):
#                 if not any(b in label_lower for b in (
#                     "mortgagee", "loss payee", "lender",
#                     "interest of", "interest in",
#                     "additional insured",
#                 )):
#                     v = _normalize_name(val)
#                     if v and _looks_like_name(v):
#                         self.fields["insured_name"] = {
#                             "value": v,
#                             "confidence": 0.99,
#                             "source": "inline",
#                         }
#                     elif v and len(v.strip()) > 3:
#                         self._partial_insured = v.strip()

#         # ============================================================
#         # LOAN NUMBER
#         # ============================================================
#         has_loan_label = any(k in ll for k in LOAN_LABELS)
#         existing = self.fields.get("loan_number", {})
#         existing_unlabeled = existing.get("source") in ("mortgage_block", "sweep") if existing else False

#         if has_loan_label and ("loan_number" not in self.fields or existing_unlabeled):
#             if ":" in line:
#                 _, _, v = line.partition(":")
#                 digits = ''.join(c for c in v if c.isdigit())
#             else:
#                 digits = ''
#                 for token in line.split():
#                     d = ''.join(c for c in token if c.isdigit())
#                     if len(d) >= 7:
#                         digits = d
#                         break

#             if _looks_like_loan_number(digits):
#                 self.fields["loan_number"] = {
#                     "value": digits,
#                     "confidence": 0.96,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # EFFECTIVE / EXPIRATION DATES (HARDENED)
#         # ============================================================

#         # 1️⃣ Handle date range FIRST
#         if "effective_date" not in self.fields or "expiration_date" not in self.fields:
#             date_range = re.search(
#                 r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-|thru|through)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
#                 line,
#                 re.I
#             )
#             if date_range:
#                 if "effective_date" not in self.fields:
#                     self.fields["effective_date"] = {
#                         "value": date_range.group(1),
#                         "confidence": 0.96,
#                         "source": "inline_date_range",
#                     }
#                 if "expiration_date" not in self.fields:
#                     self.fields["expiration_date"] = {
#                         "value": date_range.group(2),
#                         "confidence": 0.96,
#                         "source": "inline_date_range",
#                     }
#                 return  # stop further date extraction for this line

#         # 2️⃣ Fallback to label-based extraction
#         if "effective_date" not in self.fields:
#             date = _extract_date(line, DATE_LABELS_EFFECTIVE)
#             if date:
#                 self.fields["effective_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline_label",
#                 }

#         if "expiration_date" not in self.fields:
#             date = _extract_date(line, DATE_LABELS_EXPIRATION)
#             if date:
#                 self.fields["expiration_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline_label",
#                 }


#         # ============================================================
#         # TOTAL PREMIUM
#         # ============================================================
#         if "total_premium" not in self.fields:
#             if any(k in ll for k in TOTAL_PREMIUM_LABELS):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.96,
#                         "source": "inline_premium",
#                     }
#                 else:
#                     self._pending_premium = True
#             elif getattr(self, '_pending_premium', False):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.93,
#                         "source": "inline_premium_lookahead",
#                     }
#                     self._pending_premium = False
#                 elif ll.strip():
#                     self._pending_premium = False

#         # ============================================================
#         # BALANCE DUE
#         # ============================================================
#         if "balance_due" not in self.fields:
#             if any(k in ll for k in BALANCE_DUE_LABELS):
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     self.fields["balance_due"] = {
#                         "value": money[-1],
#                         "confidence": 0.95,
#                         "source": "inline_balance_due",
#                     }

#         # ============================================================
#         # ISSUE DATE
#         # ============================================================
#         if "issue_date" not in self.fields:
#             date = _extract_date(line, ISSUE_DATE_LABELS)
#             if date:
#                 self.fields["issue_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # CANCELLATION DATE
#         # ============================================================
#         if "cancellation_date" not in self.fields:
#             date = _extract_date(line, CANCELLATION_DATE_LABELS)
#             if date:
#                 self.fields["cancellation_date"] = {
#                     "value": date,
#                     "confidence": 0.95,
#                     "source": "inline",
#                 }

#         # ============================================================
#         # CANCELLATION REASON
#         # ============================================================
#         if "cancellation_reason" not in self.fields:
#             for keyword in CANCELLATION_REASON_KEYWORDS:
#                 if keyword in ll:
#                     self.fields["cancellation_reason"] = {
#                         "value": keyword.title(),
#                         "confidence": 0.90,
#                         "source": "keyword_match",
#                     }
#                     break

#         # ============================================================
#         # REMIT INFO
#         # ============================================================
#         if any(k in ll for k in REMIT_INFO_LABELS):
#             self.role = Role.MAILING_BLOCK
#             self.window = 6


#     def _policy(self, line: str):
#         """Extract policy number from POLICY block"""
#         if "policy_number" in self.fields:
#             return
        
#         # Try each token
#         for token in line.split():
#             clean_token = _clean(token)
#             if _looks_like_policy(clean_token):
#                 self.fields["policy_number"] = {
#                     "value": clean_token,
#                     "confidence": 0.96,
#                     "source": "block",
#                 }
#                 return
        
#         # Try the whole line (handles spaces in policy numbers)
#         clean_line = _clean(line)
#         no_spaces = clean_line.replace(" ", "")
#         if _looks_like_policy(no_spaces):
#             self.fields["policy_number"] = {
#                 "value": no_spaces,
#                 "confidence": 0.94,
#                 "source": "block_combined",
#             }
    
#     def _insured(self, line: str):
#         """Extract insured name from INSURED block - IMPROVED"""
#         ll = line.lower().strip()
        
#         # Skip obvious non-name lines
#         skip_patterns = [
#             "po box", "policy period", "loan number", "policy type",
#             "description", "coverage", "premium", "effective", "expiration",
#             "page", "continued", "summary", "mortgagee", "loss payee",
#             "mailing address",
#         ]
#         if any(p in ll for p in skip_patterns):
#             return
        
#         # Skip if line is just a header
#         if line.strip().endswith(":"):
#             return
#         if ll in [l.lower() for l in INSURED_LABELS]:
#             return
        
#         # CRITICAL: Skip if line looks like a label fragment
#         if ll.startswith("and ") or ll.startswith("or "):
#             return
        
#         clean_line = _normalize_name(line)
        
#         # Strip trailing date patterns (e.g., "Dummy Name July 2020" -> "Dummy Name")
#         clean_line = re.sub(
#             r'\s+(January|February|March|April|May|June|July|August|September|'
#             r'October|November|December)\s+\d{4}\s*$',
#             '', clean_line, flags=re.I
#         ).strip()
        
#         # CRITICAL: Additional check - block mortgagee-related values
#         if any(bad in ll for bad in BAD_INSURED_TERMS):
#             return
        
#         # Skip generic section headers that look like names but aren't
#         section_headers = {
#             "home protection", "personal liability", "medical expenses",
#             "personal property", "dwelling coverage", "loss settlement",
#             "hurricane premium", "building ordinance", "property protection",
#             "coverage", "property protection", "renewal certificate",
#             "supplemental declarations", "medical office",
#         }
#         if clean_line.lower().strip() in section_headers:
#             return
        
#         # Check for multi-line name combination (e.g., "DUMMY NAME" + "PROPERTIES, LLC")
#         if self._partial_insured and "insured_name" not in self.fields:
#             # Try combining with previous partial
#             combined = self._partial_insured + " " + clean_line
#             if _looks_like_name(combined):
#                 self.fields["insured_name"] = {
#                     "value": combined,
#                     "confidence": 0.96,
#                     "source": "block_combined",
#                 }
#                 self._partial_insured = ""
#                 return
        
#         # Check if it's a name
#         if _looks_like_name(clean_line):
#             if "insured_name" not in self.fields:
#                 self.fields["insured_name"] = {
#                     "value": clean_line,
#                     "confidence": 0.97,
#                     "source": "block",
#                 }
#                 # Don't clear _partial — set it so next line can extend
#                 self._partial_insured = clean_line
#             elif self._partial_insured:
#                 # Already have a name — check if this extends it
#                 # (e.g., "PROPERTIES, LLC" extending "DUMMY NAME")
#                 combined = self._partial_insured + " " + clean_line
#                 if _looks_like_name(combined):
#                     self.fields["insured_name"] = {
#                         "value": combined,
#                         "confidence": 0.97,
#                         "source": "block_extended",
#                     }
#                 self._partial_insured = ""
#             return
        
#         # Check if current line is a business suffix that extends the existing name
#         if "insured_name" in self.fields and self._partial_insured:
#             business_suffixes = ("llc", "inc", "corp", "ltd", "co", "properties",
#                                  "enterprises", "holdings", "investments", "group",
#                                  "associates", "partners", "trust", "estate")
#             clean_lower = clean_line.lower().strip().rstrip(".,")
#             if any(clean_lower.startswith(s) or clean_lower.endswith(s) for s in business_suffixes):
#                 combined = self._partial_insured + " " + clean_line
#                 self.fields["insured_name"] = {
#                     "value": combined,
#                     "confidence": 0.97,
#                     "source": "block_extended",
#                 }
#             self._partial_insured = ""
#             return
        
#         # If it might be first part of multi-line name (single word, uppercase)
#         if clean_line.isupper() and len(clean_line.split()) <= 2 and "insured_name" not in self.fields:
#             # Check if it looks like a name part (not a header)
#             if not any(w in clean_line.lower() for w in ("page", "policy", "coverage")):
#                 self._partial_insured = clean_line
#                 return
        
#         # Check if it's an address (capture for mailing)
#         if _looks_like_address(line):
#             if "mailing_address" not in self.fields:
#                 # Check if line has "Label: Value" format
#                 address_value = line.strip()
#                 if ":" in line:
#                     _, _, val = line.partition(":")
#                     val = val.strip()
#                     if val and _looks_like_address(val):
#                         address_value = val
                
#                 self.fields["mailing_address"] = {
#                     "value": address_value,
#                     "confidence": 0.92,
#                     "source": "insured_block",
#                 }
    
#     def _property(self, line: str):
#         """Extract property address from PROPERTY block"""
#         ll = line.lower().strip()
        
#         # Skip headers and labels
#         if line.strip().endswith(":"):
#             return
#         if ll in [t.lower() for t in PROPERTY_TRIGGERS]:
#             return
        
#         # Check if line has "Label: Value" format
#         address_value = line.strip()
#         if ":" in line:
#             label, _, val = line.partition(":")
#             val = val.strip()
#             # If value part looks like an address, use just the value
#             if val and _looks_like_address(val):
#                 address_value = val
        
#         if _looks_like_address(address_value):
#             if "property_address" not in self.fields:
#                 self.fields["property_address"] = {
#                     "value": address_value,
#                     "confidence": 0.98,
#                     "source": "block",
#                 }
#             else:
#                 current = self.fields["property_address"]["value"]
#                 has_street_number = bool(re.match(r'^\d+\s+', current.strip()))
#                 new_has_street = bool(re.match(r'^\d+\s+', address_value.strip()))
                
#                 # Check if this looks like a city/state/zip continuation
#                 # (no street number, follows a street line)
#                 is_city_continuation = (
#                     has_street_number and not new_has_street
#                     and re.search(r'[A-Z]{2}\s+\d{5}', address_value)  # Has state + zip
#                     and "," not in current  # Current doesn't already have city
#                 )
                
#                 if is_city_continuation:
#                     self.fields["property_address"]["value"] = current + ", " + address_value
#                 elif new_has_street and not has_street_number:
#                     self.fields["property_address"]["value"] = address_value
#                 elif len(address_value) > len(current) and (new_has_street or not has_street_number):
#                     self.fields["property_address"]["value"] = address_value
    
#     def _mailing(self, line: str):
#         """Extract mailing address from MAILING block"""
#         if line.strip().endswith(":"):
#             return
        
#         if _looks_like_address(line):
#             addr_val = line.strip()
#             # Strip trailing date/time patterns
#             addr_val = re.sub(
#                 r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+'
#                 r'(January|February|March|April|May|June|July|August|September|'
#                 r'October|November|December)\s+\d{1,2},?\s+\d{4}.*$',
#                 '', addr_val, flags=re.I
#             ).strip()
#             addr_val = re.sub(
#                 r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+\d{1,2}/\d{1,2}/\d{4}.*$',
#                 '', addr_val, flags=re.I
#             ).strip()
#             if addr_val:
#                 if "mailing_address" not in self.fields:
#                     self.fields["mailing_address"] = {
#                         "value": addr_val,
#                         "confidence": 0.96,
#                         "source": "mailing_block",
#                     }
#                 else:
#                     # Append city/state/zip to existing PO Box or street
#                     existing = self.fields["mailing_address"]["value"]
#                     # Only append if it looks like a continuation (city/state/zip)
#                     if addr_val and not addr_val.lower().startswith("po box"):
#                         self.fields["mailing_address"]["value"] = existing + ", " + addr_val
#         elif _looks_like_name(line) and "insured_name" not in self.fields:
#             self.fields["insured_name"] = {
#                 "value": _normalize_name(line),
#                 "confidence": 0.90,
#                 "source": "mailing_block",
#             }
#         elif "insured_name" in self.fields and self.fields["insured_name"].get("source") == "mailing_block":
#             # Check if this is a continuation of the name (e.g., "PROPERTIES, LLC")
#             clean = _normalize_name(line)
#             if clean and _looks_like_name(clean) and not _looks_like_address(line):
#                 existing = self.fields["insured_name"]["value"]
#                 # Only append if it looks like a continuation (LLC, Inc, Corp, etc.)
#                 # or if the combined result still looks like a name
#                 combined = existing + " " + clean
#                 if _looks_like_name(combined):
#                     self.fields["insured_name"]["value"] = combined
    
#     def _mortgage(self, line: str):
#         """Extract mortgage company and loan number from MORTGAGE block"""
#         ll = line.lower()
        
#         # Skip headers (including ":." variant from OCR)
#         stripped = line.strip().rstrip(".")
#         if stripped.endswith(":"):
#             return
        
#         # Skip bad patterns (EXPANDED)
#         bad_patterns = [
#             "policy", "coverage", "endorsement", "homeowners", "premium",
#             "first mortgagee", "second mortgagee", "third mortgagee",
#             "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
#             "mortgagee copy", "mortgagee certificate",
#             "other interest", "type of interest",
#         ]
#         if any(p in ll for p in bad_patterns):
#             return
        
#         # Loan number — also capture "N/A" style loan indicators
#         if "loan_number" not in self.fields:
#             has_loan_label = any(k in ll for k in ("loan no", "loan number", "loan #", "loan id", "ln #", "mortgage loan"))
#             if has_loan_label:
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     if re.match(r'^n/?a\b', v, re.I):
#                         self.fields["loan_number"] = {
#                             "value": "N/A",
#                             "confidence": 0.90,
#                             "source": "mortgage_block",
#                         }
#                     else:
#                         digits = ''.join(c for c in v if c.isdigit())
#                         if _looks_like_loan_number(digits):
#                             self.fields["loan_number"] = {
#                                 "value": digits,
#                                 "confidence": 0.94,
#                                 "source": "mortgage_block",
#                             }
#             elif not _looks_like_address(line):
#                 # Only scan tokens for loan number if line is NOT an address
#                 for token in line.split():
#                     digits = ''.join(c for c in token if c.isdigit())
#                     if _looks_like_loan_number(digits):
#                         self.fields["loan_number"] = {
#                             "value": digits,
#                             "confidence": 0.90,
#                             "source": "mortgage_block",
#                         }
#                         break
        
#         # Mortgage company
#         if "mortgage_company" not in self.fields:
#             # Look for company-like patterns
#             if any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "federal", "financial")):
#                 # CRITICAL: Skip if it's just a label like "First Mortgagee"
#                 if re.match(r'^(first|second|third|1st|2nd|3rd)\s+(mortgagee|lender)', ll):
#                     return
                
#                 clean = line.strip()
#                 # Remove label prefixes like "holder:", "mortgagee:", etc.
#                 clean = re.sub(r'^(holder|mortgagee|loss\s+payee|lienholder|lien\s+holder)\s*:\s*', '', clean, flags=re.I)
#                 # Remove ISAOA/ATIMA/SUCC suffixes
#                 clean = re.sub(r'\s+(ITS\s+SUCC(\s+AND/OR\s+ASSIGNS)?\s+)?(ISAOA|ATIMA|ISAOA/ATIMA).*$', '', clean, flags=re.I)
#                 clean = re.sub(r'\s+ITS\s+SUCC\s+AND/OR\s+ASSIGNS.*$', '', clean, flags=re.I)
#                 # Remove numbering prefixes
#                 clean = re.sub(r'^(\d+\.?\s*|first\s+|second\s+|third\s+)', '', clean, flags=re.I)
                
#                 if len(clean) > 5:
#                     self.fields["mortgage_company"] = {
#                         "value": clean,
#                         "confidence": 0.94,
#                         "source": "mortgage_block",
#                     }
    
#     def _carrier(self, line: str):
#         """Extract carrier name from CARRIER block"""
#         if "carrier_name" in self.fields:
#             return
        
#         ll = line.lower()
        
#         # Skip headers
#         if line.strip().endswith(":"):
#             return
        
#         # Look for insurance company patterns
#         # Include "indemnity", "casualty" as alternatives to "insurance"
#         has_insurer_word = any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance'))
#         has_company_type = any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp'))
#         is_agent_line = any(w in ll for w in ('agency', 'agent', 'services', 'producer'))
        
#         if has_insurer_word and has_company_type and not is_agent_line:
#             # Strip trailing noise like "Customer assistance number:" 
#             carrier_val = line.strip()
#             carrier_val = re.sub(
#                 r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
#                 r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
#                 '', carrier_val, flags=re.I
#             ).strip()
#             self.fields["carrier_name"] = {
#                 "value": carrier_val.upper(),
#                 "confidence": 0.96,
#                 "source": "carrier_block",
#             }
    
#     def finalize(self):
#         """Final cleanup and flush"""
#         self._flush_accumulators()


# # ============================================================
# # SAFE SWEEP (FALLBACK)
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     """Final pass to catch missed fields"""
    
#     # --- Policy Number fallback ---
#     if "policy_number" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in POLICY_LABELS):
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = _clean(v).replace(" ", "")
#                     if _looks_like_policy(v):
#                         fields["policy_number"] = {
#                             "value": v,
#                             "confidence": 0.88,
#                             "source": "sweep",
#                         }
#                         break
                
#                 # Check next few lines
#                 for j in range(i + 1, min(i + 3, len(lines))):
#                     candidate = _clean(lines[j]).replace(" ", "")
#                     if _looks_like_policy(candidate):
#                         fields["policy_number"] = {
#                             "value": candidate,
#                             "confidence": 0.85,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "policy_number" in fields:
#                     break
    
#     # --- Insured Name fallback (IMPROVED) ---
#     if "insured_name" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in INSURED_LABELS):
#                 # CRITICAL: Skip if it's a mortgagee section
#                 if any(bad in ll for bad in ("mortgagee", "loss payee")):
#                     continue
                
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = _normalize_name(v)
#                     if _looks_like_name(v):
#                         fields["insured_name"] = {
#                             "value": v,
#                             "confidence": 0.88,
#                             "source": "sweep",
#                         }
#                         break
                
#                 # Check next few lines
#                 for j in range(i + 1, min(i + 4, len(lines))):
#                     candidate = _normalize_name(lines[j])
#                     if _looks_like_name(candidate):
#                         fields["insured_name"] = {
#                             "value": candidate,
#                             "confidence": 0.85,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "insured_name" in fields:
#                     break
    
#     # --- Property Address fallback ---
#     if "property_address" not in fields:
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in PROPERTY_TRIGGERS):
#                 for j in range(i + 1, min(i + 5, len(lines))):
#                     if _looks_like_address(lines[j]):
#                         fields["property_address"] = {
#                             "value": lines[j].strip(),
#                             "confidence": 0.84,
#                             "source": "sweep_lookahead",
#                         }
#                         break
#                 if "property_address" in fields:
#                     break
    
#     # --- Carrier Name fallback (scan first 20 lines) ---
#     if "carrier_name" not in fields:
#         # First, look for "underwritten by" or "your insurer" patterns
#         for line in lines[:30]:
#             ll = line.lower()
#             if "underwritten by" in ll or "your insurer" in ll:
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     if 'insurance' in v.lower():
#                         fields["carrier_name"] = {
#                             "value": v.upper(),
#                             "confidence": 0.90,
#                             "source": "sweep_underwritten",
#                         }
#                         break
        
#         # Then try direct insurance company pattern
#         if "carrier_name" not in fields:
#             for line in lines[:20]:
#                 ll = line.lower()
#                 if any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance')):
#                     if any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
#                         if not any(w in ll for w in ('agency', 'agent', 'services')):
#                             carrier_val = _extract_carrier_name(line.strip())
#                             if carrier_val and _looks_like_carrier(carrier_val):
#                                 fields["carrier_name"] = {
#                                     "value": carrier_val.upper(),
#                                     "confidence": 0.85,
#                                     "source": "sweep_header",
#                                 }
#                                 break
    
#     # --- Loan Number fallback ---
#     if "loan_number" not in fields:
#         for line in lines:
#             ll = line.lower()
#             if any(k in ll for k in LOAN_LABELS):
#                 # Try to extract number from line
#                 if ":" in line:
#                     _, _, v = line.partition(":")
#                     v = v.strip()
#                     # Handle N/A loan numbers (with or without slash)
#                     if re.match(r'^n/?a\b', v, re.I):
#                         fields["loan_number"] = {
#                             "value": "N/A",
#                             "confidence": 0.85,
#                             "source": "sweep",
#                         }
#                         break
#                     digits = ''.join(c for c in v if c.isdigit())
#                 else:
#                     digits = ''.join(c for c in line if c.isdigit())
                
#                 if _looks_like_loan_number(digits):
#                     fields["loan_number"] = {
#                         "value": digits,
#                         "confidence": 0.85,
#                         "source": "sweep",
#                     }
#                     break
    
#     # --- Total Premium fallback ---
#     if "total_premium" not in fields:
#         premium_labels = (
#             "total annual policy premium", "total annual premium",
#             "total policy premium", "total premium",
#             "total residence premium", "annual premium",
#             "total annual policy cost", "full term premium",
#         )
#         for i, line in enumerate(lines):
#             ll = line.lower()
#             if any(k in ll for k in premium_labels):
#                 # Check same line for dollar amount
#                 money = re.findall(r'\$[\d,]+\.?\d*', line)
#                 if money:
#                     fields["total_premium"] = {
#                         "value": money[-1],
#                         "confidence": 0.85,
#                         "source": "sweep_premium",
#                     }
#                     break
#                 # Check next lines — take the LAST dollar amount found
#                 # (in two-column layouts, the total is the last amount)
#                 last_money = None
#                 for j in range(i + 1, min(i + 20, len(lines))):
#                     money_j = re.findall(r'\$[\d,]+\.?\d*', lines[j])
#                     if money_j:
#                         last_money = money_j[-1]
#                 if last_money:
#                     fields["total_premium"] = {
#                         "value": last_money,
#                         "confidence": 0.82,
#                         "source": "sweep_premium_lookahead",
#                     }
#                     break


# # ============================================================
# # ENTRY POINTS
# # ============================================================

# # ---- CAN-specific field patterns ----
# _CAN_DATE_PATTERNS = re.compile(
#     r"(?i)(?:cancellation|cancel(?:led)?|termination|void|cease|non-?renewal)"
#     r"(?:\s+effective|\s+date)?\s*[:\-]?\s*"
#     r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
# )
# _CAN_REASON_LABELS = re.compile(
#     r"(?i)(?:reason\s+for\s+(?:cancellation|termination)|cancel(?:lation)?\s+reason"
#     r"|reason\s*:)\s*(.{4,80})"
# )
# _BALANCE_DUE_PATTERNS = re.compile(
#     r"(?i)(?:balance\s+(?:to\s+pay|due)|amount\s+due|total\s+(?:amount\s+)?due"
#     r"|minimum\s+(?:amount\s+)?due|to\s+pay\s+in\s+full)\s*[:\$]?\s*\$?([\d,]+\.?\d*)"
# )
# _ISSUE_DATE_PATTERNS = re.compile(
#     r"(?i)(?:bill\s+date|invoice\s+date|statement\s+date|issue\s+date"
#     r"|billing\s+date|due\s+date|information\s+as\s+of|processed\s+on)\s*[:\-]?\s*"
#     r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
# )
# _REMIT_PATTERNS = re.compile(
#     r"(?i)(?:mail\s+to|remit\s+to|payable\s+to|make\s+check[s]?\s+payable\s+to"
#     r"|send\s+payment\s+to|payment\s+to)\s*[:\-]?\s*(.{4,80})"
# )


# def _extract_can_inv_fields(lines: List[str], fields: Dict[str, Dict]) -> None:
#     """
#     Doc-type-aware sweep for CAN and INV specific fields.
#     Stage1 normally doesn't extract these — this function fills the gap.
#     Called after _safe_sweep() so it only adds fields that Stage1 missed.
#     """
#     text = "\n".join(lines)

#     # --- CANCELLATION DATE ---
#     if "cancellation_date" not in fields:
#         m = _CAN_DATE_PATTERNS.search(text)
#         if m:
#             fields["cancellation_date"] = {
#                 "value": m.group(1).strip(),
#                 "confidence": 0.82,
#                 "source": "stage1_can_date",
#             }

#     # --- CANCELLATION REASON ---
#     if "cancellation_reason" not in fields:
#         m = _CAN_REASON_LABELS.search(text)
#         if m:
#             reason = m.group(1).strip().rstrip(".")
#             # Filter out dates and garbage
#             if len(reason) > 3 and not re.match(r"^\d", reason):
#                 fields["cancellation_reason"] = {
#                     "value": reason,
#                     "confidence": 0.78,
#                     "source": "stage1_can_reason",
#                 }

#     # --- BALANCE DUE ---
#     if "balance_due" not in fields:
#         m = _BALANCE_DUE_PATTERNS.search(text)
#         if m:
#             fields["balance_due"] = {
#                 "value": "$" + m.group(1).strip(),
#                 "confidence": 0.83,
#                 "source": "stage1_inv_balance",
#             }

#     # --- ISSUE DATE ---
#     if "issue_date" not in fields:
#         m = _ISSUE_DATE_PATTERNS.search(text)
#         if m:
#             fields["issue_date"] = {
#                 "value": m.group(1).strip(),
#                 "confidence": 0.82,
#                 "source": "stage1_inv_issue_date",
#             }

#     # --- REMIT INFO ---
#     if "remit_info" not in fields:
#         m = _REMIT_PATTERNS.search(text)
#         if m:
#             remit = m.group(1).strip()
#             if len(remit) > 3:
#                 fields["remit_info"] = {
#                     "value": remit,
#                     "confidence": 0.78,
#                     "source": "stage1_inv_remit",
#                 }


# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """Main entry point for Stage 1 extraction"""
#     if not lines:
#         return {}
    
#     extractor = StatefulExtractor()
    
#     for raw in lines:
#         line = raw.strip()
#         if line:
#             extractor.update_role(line)
#             extractor.extract(line)
    
#     extractor.finalize()
#     _safe_sweep(lines, extractor.fields)
#     _extract_can_inv_fields(lines, extractor.fields)   # ← NEW: CAN + INV fields
    
#     return extractor.fields


# def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """Alias for backward compatibility"""
#     return extract_fields(lines, layout_elements)

# stage1_deterministic_agent.py
"""
Stage 1 – Stateful, Role-Anchored Deterministic Extraction
IMPROVED VERSION - Fixes for:
1. Insured name extraction (blocking mortgagee terms, product names)
2. Carrier name extraction (multi-line support)
3. Loan number extraction (blocking document references)
4. Policy number extraction (better patterns)
"""
import re
from typing import Dict, List, Set, Tuple
from enum import Enum, auto


# ============================================================
# ROLES
# ============================================================

class Role(Enum):
    NONE = auto()
    POLICY_HEADER = auto()
    INSURED_BLOCK = auto()
    PROPERTY_BLOCK = auto()
    MAILING_BLOCK = auto()
    MORTGAGE_BLOCK = auto()
    CARRIER_BLOCK = auto()
    PRODUCER_BLOCK = auto()  # NEW: Skip names in producer/agent sections


# ============================================================
# REGEX PATTERNS
# ============================================================

PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
DATE_WRITTEN_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
    re.I
)
# Abbreviated month names: NOV 09 2021, DEC 1 2022, etc.
DATE_ABBREV_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
    re.I
)
PO_BOX_RE = re.compile(r"p\.?o\.?\s*box", re.I)
STREET_RE = re.compile(
    r"\b\d{1,6}\s+.+?\b("
    r"st|street|ave|avenue|rd|road|blvd|boulevard|"
    r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge|pl|place"
    r")\b",
    re.I
)

# Policy number patterns - multiple variants
POLICY_REGEX_VARIANTS = [
    re.compile(r"^[A-Z]{2,4}[-\s]?\d{7,12}[-\s]?\d{0,2}$", re.I),  # DPC0076173896-1
    re.compile(r"^\d{9,12}$"),  # 2004939477
    re.compile(r"^\d{9}\s*\d{3}\s*\d{1}$"),  # 602732135 664 1
    re.compile(r"^[A-Z]{2,4}\d{1,2}[-]?\d{9,12}$", re.I),  # OKH3-109194373
    re.compile(r"^\d{8,12}[-\s]?\d{1,2}$"),  # 04038598 - 1
    re.compile(r"^\d{2}-[A-Z]{2}-[A-Z]\d{3}-\d$", re.I),  # 81-BE-N065-5 (State Farm)
    re.compile(r"^\d{2}-[A-Z]{2,4}-[A-Z0-9]{3,8}$", re.I),  # Generic NN-XX-XXXXX
    # --- INS observation batch additions (Section 2) ---
    # Spaced numeric: "821 736 168", "063 078 674"
    re.compile(r"^\d{3}\s\d{3}\s\d{3}$"),
    # Dashed numeric with space: "02050414 - 5"
    re.compile(r"^\d{8}\s*-\s*\d{1,2}$"),
    # Hyphenated alphanumeric: "TX-HOV-00032479-01", "60-04077225-2019"
    re.compile(r"^[A-Z]{2}-[A-Z]{2,4}-\d{5,}-\d{1,2}$", re.I),
    re.compile(r"^\d{2}-\d{8,}-\d{4}$"),
    # Alpha prefix with space: "ACP BPH 7885310416", "LAH0195988"
    re.compile(r"^[A-Z]{2,4}\s?[A-Z]{0,4}\s?\d{7,12}$", re.I),
    # Alpha suffix: "60092029BP"
    re.compile(r"^\d{8,10}[A-Z]{2}$", re.I),
    # Commercial style: "34 X42393-01"
    re.compile(r"^\d{2}\s[A-Z]\d{5,}-\d{1,2}$", re.I),
    # Flood style: "99-047002652-2020"
    re.compile(r"^\d{2}-\d{9,}-\d{4}$"),
]

STATE_ABBREV = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI"
}


# ============================================================
# LABELS / TRIGGERS
# ============================================================

POLICY_LABELS = {
    "policy number", "policy no", "policy #",
    "your policy number", "policynumber",
    "dwelling policy number",
    "account number", "your account number",
}

INSURED_LABELS = {
    "insured", "named insured",
    "insured name", "insured name and address",
    "insured mailing", "insured mailing name",
    "insured mailing name and address",
    "policyholder", "policy holder",
    "policyholder(s)",  # ADDED for "Policyholder(s) TIM RASK"
    "policyholders",
    "policyholder/insured", "policyholder/named insured",
    "first named insured",
    "named insured and address",
    "name and address of insured",  # ADDED
}

# CRITICAL: Terms that should NOT be captured as insured names
BAD_INSURED_TERMS = {
    # Mortgagee-related (most common error)
    "mortgagee", "first mortgagee", "second mortgagee", "third mortgagee",
    "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
    "loss payee", "lienholder", "lender",
    "isaoa", "atima", "isaoa atima", "isaoa/atima",
    "lien holder", "1st mortgagee copy",
    
    # Product names
    "homesaver policy", "homesaver polcy", "homeowners policy",
    "dwelling policy", "special form", "wind only policy",
    "ultrapack plus", "mobilehome policy", "condominium owners",
    "mobilehome", "house & home",
    
    # Insurance company fragments
    "insurance exchange", "insurance company", "insurance group",
    "insurance corp", "insurance mutual",
    
    # Document structure
    "policy period", "policy type", "coverage",
    "endorsement", "declarations", "summary",
    "premium", "deductible", "page", "continued",
    "information as of",
    
    # Agencies/agents/producers (CRITICAL - fixes Michael Ames issue)
    "agency", "agent", "services", "producer",
    "goosehead", "goosehead insurance",
    
    # Service centers (CRITICAL - fixes Mortgagee Relations Center)
    "relations center", "mortgagee relations", "lender relations",
    "customer service", "service center",
    "claims center", "billing center",
    
    # Website/online instructions (CRITICAL - fixes aegisinsurance.com)
    "website", ".com", "online", "go to", "simply go",
    "click here", "select", "menu bar", "policyholders",
    "make a payment", "pay online",
    
    # Marketing slogans (CRITICAL - fixes "You're in good hands")
    "you're in good hands", "good hands",
    "like a good neighbor", "on your side",
    "we know a thing or two", "because we've seen",
    
    # Other noise
    "other interest", "interested parties", "certificate holder",
    "office use", "message", "messages",
    "risk management", "department",
    "third party notice", "notice of",
}

BAD_NAME_PHRASES = {
    # Sections
    "coverage", "endorsement", "deductible",
    "policy conditions", "forms and endorsements",
    "policy period", "premium", "billing",
    "invoice", "notice", "summary", "schedule",
    "page", "continued", "section",
    
    # Mortgagee related (CRITICAL)
    "mortgagee", "loss payee", "lienholder",
    "first mortgagee", "second mortgagee",
    "isaoa", "atima", "lien holder",
    
    # Products / carriers
    "homeowners", "dwelling", "ultrapack",
    "insurance company", "insurance exchange",
    "insurance group", "homesaver",
    "mobilehome",
    
    # Agencies/producers (CRITICAL - fixes Michael Ames)
    "agency", "agent", "services", "producer",
    "goosehead", "insurance agency",
    
    # Service centers (CRITICAL - fixes Mortgagee Relations Center)
    "relations center", "mortgagee relations", "lender relations",
    "customer service", "service center",
    "claims center", "billing center",
    "risk management", "department",
    
    # Website/online (CRITICAL - fixes aegisinsurance.com)
    "website", ".com", "online", "go to", "simply go",
    "click here", "select", "menu bar",
    "make a payment", "pay online",
    
    # Marketing slogans (CRITICAL - fixes "You're in good hands")
    "you're in good hands", "good hands",
    "like a good neighbor", "on your side",
    "we know a thing or two",
    
    # Noise / instructions
    "detach this", "return with",
    "third party notice", "notice of",
    
    # Other
    "your insurer", "insurer:", "office use",
    "information as of", "page 1 of", "page 2 of",
}

PROPERTY_TRIGGERS = {
    "property address", "property insured",
    "location of insured property", "residence premises",
    "described location", "risk location",
    "insured location", "location of property",
    "premises address", "located at",
    "coverage detail for",  # Encompass: "Coverage Detail for 136 Old Altamont..."
    "insured location covered by this policy",
    "location",  # State Farm: "Location: 2971 GA HIGHWAY 93 S"
}

# Property labels for inline extraction (Label: Value format)
PROPERTY_INLINE_LABELS = {
    "property address", "risk location",
    "location of insured property",
    "premises address", "property location",
    "property insured",  # ADDED for "Property Insured: 4616 HERITAGE RD"
    "location",  # State Farm: "Location: <address>"
}

# Standalone "Address:" can be a property address in declarations contexts
# (e.g., Erie Supplemental Declarations: "Address: 421 GEORGESVILLE BD")
PROPERTY_ADDRESS_STANDALONE = {"address"}

MAILING_TRIGGERS = {
    "mailing address", "mail address",
    "insured mailing", "correspondence address",
    "send mail to", "applicant address",
}

MORTGAGE_TRIGGERS = {
    "mortgagee", "loss payee",
    "lienholder", "other interest",
    "other interested parties", "certificate holder",
    "mortgagee full name", "lien holder",
    "1st mortgagee", "2nd mortgagee", "first mortgagee", "second mortgagee",
    "holder",  # State Farm: "holder: CAPITAL CITY BANK"
    # --- INS observation batch additions (Section 4) ---
    "mortgage(s)", "mortgage holder",
    "additional interest(s)", "additional interest",
    "mortgage servicing agency",
    "unit owner mortgagee",
    "mortgage or interested party",
    "additional interest/mortgage/trust",
    "mortgage or loss payee",
    "mortgagee/loss payee",
    # Note: Removed "lender" as it can trigger on "Lender Relations Center"
}

# Patterns that look like mortgage triggers but are actually service centers
MORTGAGE_FALSE_POSITIVES = {
    "lender relations center",
    "mortgagee relations center",
    "mortgage relations center",
}

# NEW: Producer/Agent triggers - names after these should NOT be captured as insured
PRODUCER_TRIGGERS = {
    "producer", "agent", "agency",
    "your agent", "insurance agent",
    "sales rep", "representative",
}

CARRIER_TRIGGERS = {
    "insurance company", "insurance exchange",
    "insurance group", "insurance provided by",
    "issued by", "underwritten by", "insurer",
    "policy underwritten by", "your insurer",
}

LOAN_LABELS = {
    "loan number", "loan no", "loan #", "loan id",
    "mortgage loan number", "ln #",
    # --- INS observation batch additions (Section 3) ---
    "loan/contract number", "loan/contract #",
    "loan:", "mortgage loan no",
    "mortgage loan no.", "loan no.",
}

DATE_LABELS_EFFECTIVE = {
    "effective date", "policy effective date",
    "coverage begins", "term start date",
    "change effective date",
}

DATE_LABELS_EXPIRATION = {
    "expiration date", "policy expiration date",
    "coverage ends", "term end date", "expires",
    "through",  # Encompass format: "through July 1, 2021 at 12:01 a.m."
}

BAD_ADDRESS_PHRASES = {
    "coverage", "premium", "deductible",
    "policy period", "effective", "expiration",
    "billing", "payment", "invoice", "notice",
}


# ============================================================
# HELPERS
# ============================================================

def _clean(v: str) -> str:
    """Clean extracted value"""
    v = re.sub(r"\s+", " ", v)
    v = v.strip(" ,.;:-")
    return v


def _normalize_name(v: str) -> str:
    """Normalize name format"""
    if not v:
        return ""
    
    v = v.strip()
    
    # Remove common prefixes/suffixes
    v = re.sub(r"^(named insured|insured|policyholder)[:\s]*", "", v, flags=re.I)
    v = re.sub(r"\s*(beginning|effective|since|policy period).*$", "", v, flags=re.I)
    
    # Handle "LASTNAME, FIRSTNAME" format BUT NOT company names with comma
    # Don't swap if it contains entity suffixes
    if "," in v and v.count(",") == 1:
        has_entity = any(w in v.lower() for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
        if not has_entity:
            parts = [p.strip() for p in v.split(",") if p.strip()]
            if len(parts) == 2 and not any(c.isdigit() for c in v):
                # Only swap if both parts look like names (not addresses)
                if not any(w.upper() in STATE_ABBREV for w in parts[1].split()):
                    return f"{parts[1]} {parts[0]}"
    
    return v.strip()


def _is_phone_number(v: str) -> bool:
    """
    Check if value is a phone number
    CONSERVATIVE: Returns True only for values that are CLEARLY phone numbers
    """
    # If the original value has letters, it's likely not a phone number
    if any(c.isalpha() for c in v):
        return False
    
    # Extract only digits
    digits = ''.join(c for c in v if c.isdigit())
    
    # Phone numbers are exactly 7, 10, or 11 digits
    # If longer than 11, it's definitely not a phone number
    if len(digits) > 11:
        return False
    
    # Check if it has phone formatting (parentheses, dashes in right places)
    # Only flag as phone if it has ACTUAL phone formatting
    if re.fullmatch(r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}', v.strip()):
        return True
    
    # Only 7 digits with dash: xxx-xxxx format
    if re.fullmatch(r'\d{3}[-.\s]\d{4}', v.strip()):
        return True
    
    # For pure numeric strings, DON'T assume they're phone numbers
    # because policy numbers are often 10 digits too
    # Only flag as phone if it has formatting
    
    return False


def _is_document_reference(v: str) -> bool:
    """Check if value looks like a document reference code, not real data"""
    v_clean = v.strip()
    
    # Pattern: digits_digits_digits (e.g., 19660_859561_6)
    if re.match(r'^\d+_\d+(_\d+)?$', v_clean):
        return True
    
    # Page references
    if re.match(r'^page\s*\d+', v_clean, re.I):
        return True
    
    # Very long numeric strings with many zeros
    digits = ''.join(c for c in v_clean if c.isdigit())
    if len(digits) > 15:
        return True
    
    # More than 50% zeros in long number
    if len(digits) > 10:
        zero_count = digits.count('0')
        if zero_count > len(digits) * 0.5:
            return True
    
    return False


def _looks_like_name(text: str) -> bool:
    """
    Check if text looks like a person/company name
    IMPROVED: Better filtering of mortgagee terms and noise
    """
    if not text or len(text) < 3:
        return False
    
    text = text.strip()
    ll = text.lower()
    
    # CRITICAL: Block mortgagee-related terms
    for bad_term in BAD_INSURED_TERMS:
        if bad_term in ll:
            return False
    
    # Block known bad phrases
    if any(b in ll for b in BAD_NAME_PHRASES):
        return False
    
    # Block if ends with colon (it's a label)
    if text.endswith(":"):
        return False
    
    # Block lines with too many special chars
    special = sum(1 for c in text if c in "()[]{}|\\/<>@#$%^&*=+")
    if special > 2:
        return False
    
    # Block if starts with certain bad patterns
    bad_starts = (
        "policy", "coverage", "premium", "page", "section",
        "effective", "expiration", "the ", "this ", "your ",
        "or ", "for ", "to ", "from ", "with ",
    )
    # NOTE: removed "and " from bad_starts to allow "ROBERT and MARY" style names
    if any(ll.startswith(w) for w in bad_starts):
        return False
    
    # Block if ends with label-like patterns (but not if it's a person's name)
    bad_ends = (
        " address", " information", " number",
        " period", " type", " date", " copy", " notice",
    )
    # Note: removed " name" because "NAME" can be a valid surname (e.g., "JOHN NAME", "DUMMY NAME")
    if any(ll.endswith(w) for w in bad_ends):
        return False
    
    # Allow entities with digits (LLC, Corp, etc.)
    has_entity = any(w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd", "bank"))
    
    # Check if it's a multi-person name (contains "and" or "&" between name parts)
    has_and_connector = bool(re.search(r'\b(and|&)\b', ll))
    
    # Block digits unless it's an entity
    if any(c.isdigit() for c in text) and not has_entity:
        return False
    
    words = text.replace(",", " ").split()
    word_count = len(words)
    
    # Entity names can be longer; multi-person names can be longer too
    if has_entity:
        if not (2 <= word_count <= 12):
            return False
    elif has_and_connector:
        # Multi-person names like "ROBERT J BARRON and DANIEL PRYCE" can have 6-8 words
        if not (4 <= word_count <= 10):
            return False
    else:
        if not (2 <= word_count <= 6):
            return False
    
    # At least 1 word should start with uppercase
    caps = sum(1 for w in words if w and w[0].isupper())
    if caps < 1:
        return False
    
    # Block if looks like an address
    if STREET_RE.search(text) or PO_BOX_RE.search(text):
        return False
    
    # Block if has state abbreviation followed by ZIP
    if re.search(r"\b[A-Z]{2}\s*\d{5}", text):
        return False
    
    return True


def _looks_like_policy(v: str) -> bool:
    """
    Check if value looks like a policy number
    IMPROVED: Better blocking of bad patterns
    """
    if not v:
        return False
    
    v_original = v
    v_clean = re.sub(r"[\s\-]", "", v)
    
    # CRITICAL: Block phone numbers FIRST
    if _is_phone_number(v_original):
        return False
    
    # Block document references
    if _is_document_reference(v_original):
        return False
    
    # Block dates - numeric and written
    if DATE_RE.search(v_original) or DATE_WRITTEN_RE.search(v_original):
        return False
    
    # Block if contains date-like words
    date_words = ('january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'effective', 'expiration')
    if any(w in v_original.lower() for w in date_words):
        return False
    
    # Block pure year references (2023, 2024, etc.)
    if v_clean.isdigit() and len(v_clean) == 4 and v_clean.startswith(('19', '20')):
        return False
    
    # Block ZIP codes (5 or 9 digits)
    if re.fullmatch(r"\d{5}(-\d{4})?", v_clean):
        return False
    
    # Block state+number patterns (NC27102, MI48007)
    if re.match(r'^[A-Z]{2}\d{5,}$', v_clean):
        return False
    
    # Block very short values
    if len(v_clean) < 6:
        return False
    
    # Block very long values
    if len(v_clean) > 30:
        return False
    
    # Count digits and letters
    digits = sum(c.isdigit() for c in v_clean)
    letters = sum(c.isalpha() for c in v_clean)
    
    # Must have at least 4 digits (lowered slightly to handle "81-BE-N065-5" = 4 digits)
    if digits < 4:
        return False
    
    # Pure numeric: 6-14 digits is OK
    if v_clean.isdigit():
        return 6 <= len(v_clean) <= 14
    
    # Mixed: check against patterns
    for rx in POLICY_REGEX_VARIANTS:
        if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
            return True
    
    # Fallback: alphanumeric with substantial digits (lowered to 4 for NN-XX-XXXXX formats)
    if letters >= 1 and digits >= 4:
        return True
    
    return False


def _looks_like_loan_number(v: str) -> bool:
    """
    Check if value looks like a loan number
    IMPROVED: Better filtering, stricter for short numbers
    """
    if not v:
        return False
    
    # Block document references
    if _is_document_reference(v):
        return False
    
    # Block phone numbers (including formatted ones)
    if _is_phone_number(v):
        return False
    
    # Extract digits
    digits = ''.join(c for c in v if c.isdigit())
    
    # Loan numbers are typically 6-18 digits
    # (expanded from 8-15 per INS observation batch Section 3)
    if len(digits) < 6 or len(digits) > 18:
        return False
    
    # Block 13+ pure digits — likely a barcode artifact
    if len(digits) >= 13 and v.replace(' ', '').replace('-', '').isdigit():
        return False
    
    # Block if too many consecutive zeros (padding patterns)
    if '000000' in digits:
        return False
    
    # Block if more than 50% zeros in longer numbers
    if len(digits) > 10:
        zero_count = digits.count('0')
        if zero_count > len(digits) * 0.5:
            return False
    
    # Block dates
    if DATE_RE.search(v):
        return False
    
    return True


def _looks_like_address(line: str) -> bool:
    """Check if line looks like an address"""
    if not line or len(line) < 5:
        return False
    
    ll = line.lower()
    
    # Block known bad phrases
    if any(b in ll for b in BAD_ADDRESS_PHRASES):
        return False
    
    # Block if it's just a label
    if line.strip().endswith(":"):
        return False
    
    # PO Box - VALID ADDRESS
    if PO_BOX_RE.search(line):
        return True
    
    # Street address pattern
    if STREET_RE.search(line):
        return True
    
    # Has number + state abbreviation + ZIP
    if re.search(r"\d+.*\b[A-Z]{2}\b.*\d{5}", line):
        return True
    
    # Has state abbreviation + ZIP (city, state zip format)
    if re.search(r"\b[A-Z]{2}\s+\d{5}", line):
        parts = re.split(r"\b[A-Z]{2}\s+\d{5}", line)
        if parts and len(parts[0].strip()) > 5:
            return True
    
    # Has street number and reasonable length
    has_number = bool(re.search(r"^\d+\s+", line.strip()))
    word_count = len(line.split())
    if has_number and word_count >= 3:
        return True
    
    return False


def _looks_like_carrier(line: str) -> bool:
    """Check if line looks like an insurance carrier name"""
    ll = line.lower()
    
    # Must have "insurance" or "indemnity" or "casualty" somewhere
    if not any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance', ' ins ')):
        if not ll.endswith(' ins'):
            return False
    
    # Should have company type
    if not any(w in ll for w in ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')):
        return False
    
    # Block agencies
    if any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
        return False
    
    # Reasonable length
    words = line.split()
    if not (2 <= len(words) <= 10):
        return False
    
    return True


def _clean_carrier_name(name: str) -> str:
    """Strip noise prefixes/suffixes from carrier names"""
    # Strip label prefixes that aren't part of the actual carrier name
    name = re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*',
                  '', name, flags=re.I).strip()
    noise_prefixes = (
        "member ", "a member of ", "subsidiary of ",
        "underwritten by ", "issued by ", "your insurer ",
    )
    ll = name.lower()
    for prefix in noise_prefixes:
        if ll.startswith(prefix):
            name = name[len(prefix):]
            break
    # Strip trailing noise
    name = re.sub(
        r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
        r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
        '', name, flags=re.I
    ).strip()
    return name


def _extract_carrier_name(line: str) -> str:
    """
    Extract just the insurance carrier name from a line that may contain extra noise.
    Stops at the last company-type word (company, exchange, group, etc.) and 
    truncates anything after it (like 'RENEWAL CERTIFICATE', addresses, etc.)
    """
    if not line:
        return line
    
    # First apply standard cleaning
    line = _clean_carrier_name(line)
    
    # Strip leading OCR garbage (apostrophes, weird chars)
    line = re.sub(r"^[^A-Za-z0-9]+", "", line).strip()
    
    # Find where the company name likely ends by looking for company-type words
    # Use the LAST occurrence (for "State Farm Fire and Casualty Company")
    company_type_words = ['company', 'exchange', 'group', 'mutual', 
                          'corp', 'corporation', 'indemnity', 'casualty']
    
    ll = line.lower()
    best_end = -1
    
    for ct in company_type_words:
        idx = ll.rfind(ct)  # rightmost occurrence
        if idx >= 0:
            end = idx + len(ct)
            if end > best_end:
                best_end = end
    
    if best_end > 0:
        result = line[:best_end].strip()
    else:
        result = line
    
    # Must still contain 'insurance', 'indemnity', or 'casualty'
    if not any(w in result.lower() for w in ('insurance', 'indemnity', 'casualty', 'assurance', 'fire')):
        return ""
    
    # Reasonable length check
    words = result.split()
    if len(words) > 10:
        # Too long — probably a merged line; find the carrier within it
        # Look for a window ending at a company type
        for i in range(len(words) - 1, -1, -1):
            if any(ct in words[i].lower() for ct in company_type_words):
                # Find reasonable start (up to 8 words back)
                start = max(0, i - 7)
                candidate = " ".join(words[start:i+1])
                if any(w in candidate.lower() for w in ('insurance', 'indemnity', 'casualty')):
                    result = candidate
                    break
    
    # Strip leading OCR artifact words (words that don't belong to a carrier name)
    # Look for known carrier name patterns — find where the "real" name starts
    words = result.split()
    if len(words) >= 2:
        for i in range(1, len(words)):  # Start at 1: need at least one prefix word
            rest = " ".join(words[i:])
            rest_ll = rest.lower()
            if any(x in rest_ll for x in ('insurance', 'indemnity', 'casualty', 'fire')):
                if any(x in rest_ll for x in company_type_words):
                    # Check if the prefix looks like OCR noise (all lowercase)
                    prefix = " ".join(words[:i])
                    if all(not c.isupper() for c in prefix if c.isalpha()):
                        result = rest
                    break
    
    return result.strip()

def _extract_date(line: str, label_set: set) -> str:
    """Extract date from line if it matches label pattern"""
    ll = line.lower()
    
    if not any(k in ll for k in label_set):
        return None
    
    # Try written format first: January 15, 2024
    m = DATE_WRITTEN_RE.search(line)
    if m:
        return m.group(0)
    
    # Try abbreviated month format: NOV 09 2021
    m = DATE_ABBREV_RE.search(line)
    if m:
        return m.group(0)
    
    # Try numeric format: 01/15/2024
    m = DATE_RE.search(line)
    if m:
        return m.group(0)
    
    # Try extracting after colon
    if ":" in line:
        _, _, val = line.partition(":")
        val = val.strip()
        m = (DATE_WRITTEN_RE.search(val) or DATE_ABBREV_RE.search(val)
             or DATE_RE.search(val))
        if m:
            return m.group(0)
    
    return None


# ============================================================
# STATEFUL EXTRACTOR
# ============================================================

class StatefulExtractor:
    def __init__(self):
        self.role = Role.NONE
        self.window = 0
        self.fields: Dict[str, Dict] = {}
        self.carrier_accumulator: List[str] = []  # For multi-line carrier names
        self.address_accumulator: List[str] = []
        self._partial_insured: str = ""  # For multi-line insured names
        self._pending_premium: bool = False  # For multi-line premium extraction
        self._pending_policy_period: bool = False  # For Policy Period: on its own line
    
    def update_role(self, line: str):
        """Update current parsing role based on section headers"""
        ll = line.lower().strip()
        
        # Check for role triggers (order matters - more specific first)
        if any(k in ll for k in POLICY_LABELS):
            self._flush_accumulators()
            self.role, self.window = Role.POLICY_HEADER, 8
        # "Insured Mailing Name and Address" = INSURED block (captures both name + address)
        elif "insured" in ll and "mailing" in ll:
            self._flush_accumulators()
            self.role, self.window = Role.INSURED_BLOCK, 12
        elif any(k in ll for k in MAILING_TRIGGERS):
            self._flush_accumulators()
            self.role, self.window = Role.MAILING_BLOCK, 8
        elif any(k in ll for k in INSURED_LABELS) and "payor" not in ll:
            self._flush_accumulators()
            self.role, self.window = Role.INSURED_BLOCK, 12
        elif any(k in ll for k in PROPERTY_TRIGGERS):
            self._flush_accumulators()
            self.role, self.window = Role.PROPERTY_BLOCK, 8
        # Standalone "Address:" line can indicate property in declarations context
        elif re.match(r'^address\s*[:.]', ll) and "property_address" not in self.fields:
            self._flush_accumulators()
            self.role, self.window = Role.PROPERTY_BLOCK, 5
        elif any(k in ll for k in MORTGAGE_TRIGGERS):
            # Check if it's a false positive (service center header)
            if not any(fp in ll for fp in MORTGAGE_FALSE_POSITIVES):
                self._flush_accumulators()
                self.role, self.window = Role.MORTGAGE_BLOCK, 10
        elif any(k in ll for k in PRODUCER_TRIGGERS):
            # Producer/agent section - skip names here
            self._flush_accumulators()
            self.role, self.window = Role.PRODUCER_BLOCK, 6
        elif any(k in ll for k in CARRIER_TRIGGERS):
            # DON'T flush carrier accumulator - we might need to combine
            self._flush_accumulators(entering_carrier_block=True)
            self.role, self.window = Role.CARRIER_BLOCK, 6
    
    def _flush_accumulators(self, entering_carrier_block=False):
        """Save accumulated multi-line values before role change"""
        # DON'T flush carrier accumulator if entering carrier block
        # because we might need to combine it with the incoming line
        if not entering_carrier_block:
            if self.carrier_accumulator and "carrier_name" not in self.fields:
                combined = " ".join(self.carrier_accumulator)
                if _looks_like_carrier(combined):
                    self.fields["carrier_name"] = {
                        "value": combined.upper(),
                        "confidence": 0.96,
                        "source": "accumulated",
                    }
                self.carrier_accumulator = []
        
        # Flush address accumulator
        if self.address_accumulator:
            addr = " ".join(self.address_accumulator)
            if "property_address" not in self.fields:
                self.fields["property_address"] = {
                    "value": addr,
                    "confidence": 0.94,
                    "source": "accumulated",
                }
            self.address_accumulator = []
    
    def extract(self, line: str):
        """Main extraction logic for each line"""
        # Always try inline extraction first
        self._inline(line)
        
        # Try carrier extraction from any line (multi-line support)
        self._try_carrier_accumulation(line)
        
        # Role-based extraction
        if self.window > 0:
            if self.role == Role.POLICY_HEADER:
                self._policy(line)
            elif self.role == Role.INSURED_BLOCK:
                self._insured(line)
            elif self.role == Role.PROPERTY_BLOCK:
                self._property(line)
            elif self.role == Role.MAILING_BLOCK:
                self._mailing(line)
            elif self.role == Role.MORTGAGE_BLOCK:
                self._mortgage(line)
            elif self.role == Role.CARRIER_BLOCK:
                self._carrier(line)
            
            self.window -= 1
            if self.window == 0:
                self._flush_accumulators()
                self.role = Role.NONE
    
    def _try_carrier_accumulation(self, line: str):
        """Try to accumulate carrier name across lines"""
        if "carrier_name" in self.fields:
            return
        
        ll = line.lower()
        clean = line.strip().replace("*", "")
        
        # Skip label lines (ending with ":" or ":.") — these aren't carrier name parts
        stripped = clean.rstrip(".")
        if stripped.endswith(":"):
            return
        
        # Check if this line contains 'insurance'
        if 'insurance' in ll:
            # If we have accumulated a prefix, ALWAYS try to combine
            if self.carrier_accumulator:
                combined = " ".join(self.carrier_accumulator) + " " + clean
                combined_lower = combined.lower()
                # If combined has insurance + company type, use it
                if 'insurance' in combined_lower and any(w in combined_lower for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual')):
                    if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
                        carrier_val = _extract_carrier_name(combined)
                        self.fields["carrier_name"] = {
                            "value": carrier_val.upper(),
                            "confidence": 0.97,
                            "source": "multi_line_combined",
                        }
                        self.carrier_accumulator = []
                        return
            
            # No accumulator - check if this line alone is a complete carrier
            carrier_candidate = _extract_carrier_name(clean)
            if carrier_candidate and _looks_like_carrier(carrier_candidate):
                self.fields["carrier_name"] = {
                    "value": carrier_candidate.upper(),
                    "confidence": 0.95,
                    "source": "direct",
                }
                self.carrier_accumulator = []
                return
            
            # Start accumulating (e.g., "Erie INSURANCE" without company type)
            if not self.carrier_accumulator:
                if not any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
                    self.carrier_accumulator = [clean]
                    return
        
        # If accumulator has 'insurance' and current line is a company-type word
        # e.g., accumulator = ["Erie INSURANCE"], current line = "Exchange"
        elif self.carrier_accumulator and any('insurance' in a.lower() for a in self.carrier_accumulator):
            company_types = ('exchange', 'company', 'group', 'mutual', 'corp', 'corporation')
            if any(w in ll for w in company_types):
                combined = " ".join(self.carrier_accumulator) + " " + clean
                combined_lower = combined.lower()
                if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
                    carrier_val = _extract_carrier_name(_clean_carrier_name(combined))
                    self.fields["carrier_name"] = {
                        "value": carrier_val.upper(),
                        "confidence": 0.97,
                        "source": "multi_line_combined",
                    }
                    self.carrier_accumulator = []
                    return
        
        # Check if this might be first part of multi-line carrier
        elif clean.isupper() and len(clean.split()) <= 2 and not any(c.isdigit() for c in clean):
            # Might be company name prefix like "ADIRONDACK"
            noise_words = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", "NOTICE", "PO", "BOX"}
            words = clean.split()
            if words and not any(w in noise_words for w in words):
                if all(len(w) >= 3 for w in words):  # Each word should be substantial
                    self.carrier_accumulator = [clean]
    
    def _inline(self, line: str):
        """Extract from inline patterns (Label: Value)"""
        ll = line.lower()
        
        # Policy Number — also handle "POLICY NUMBER value" on same line (no colon)
        if "policy_number" not in self.fields:
            if ":" in line and any(k in ll for k in POLICY_LABELS):
                _, _, v = line.partition(":")
                v = _clean(v)
                
                # Check if it matches the "602732135 664 1" format FIRST (before any modification)
                if re.match(r'^\d{9}\s+\d{3}\s+\d$', v):
                    # This is a spaced policy number format - keep it as-is
                    v_no_space = v.replace(" ", "")
                    if _looks_like_policy(v_no_space):
                        self.fields["policy_number"] = {
                            "value": v,  # Keep with spaces
                            "confidence": 0.99,
                            "source": "inline",
                        }
                else:
                    # Handle split values like "DPC 0076173896 -1"
                    v = re.sub(r"\s+(\d)$", r"-\1", v)
                    v_no_space = v.replace(" ", "")
                    
                    if _looks_like_policy(v_no_space):
                        self.fields["policy_number"] = {
                            "value": v_no_space,
                            "confidence": 0.99,
                            "source": "inline",
                        }
            elif any(k in ll for k in POLICY_LABELS):
                # Handle "POLICY NUMBER 81-BE-N065-5" without colon (OCR column merging)
                # Find the label and extract what comes after it
                for label in sorted(POLICY_LABELS, key=len, reverse=True):  # longest first
                    label_idx = ll.find(label)
                    if label_idx >= 0:
                        after_label = line[label_idx + len(label):].strip().lstrip(":").strip()
                        # Take only the first token (avoid grabbing noise)
                        tokens = after_label.split()
                        for token in tokens:
                            candidate = _clean(token)
                            if _looks_like_policy(candidate.replace(" ", "")):
                                self.fields["policy_number"] = {
                                    "value": candidate,
                                    "confidence": 0.95,
                                    "source": "inline_no_colon",
                                }
                                break
                        if "policy_number" in self.fields:
                            break
        
        # Property Address (NEW - for "Risk Location: 3004 NORFOLK DR" patterns)
        if "property_address" not in self.fields and ":" in line:
            if any(k in ll for k in PROPERTY_INLINE_LABELS):
                _, _, v = line.partition(":")
                v = v.strip()
                if v and _looks_like_address(v):
                    self.fields["property_address"] = {
                        "value": v,
                        "confidence": 0.98,
                        "source": "inline",
                    }
        
        # Property Address from "Coverage Detail for <address>" (Encompass format)
        if "property_address" not in self.fields and "coverage detail for" in ll:
            m = re.search(r'coverage\s+detail\s+for\s+(.+)', line, re.I)
            if m:
                addr_part = m.group(1).strip()
                addr_part = re.sub(r'\s*\(continued\).*$', '', addr_part, flags=re.I).strip()
                if addr_part and _looks_like_address(addr_part):
                    self.fields["property_address"] = {
                        "value": addr_part,
                        "confidence": 0.97,
                        "source": "inline_coverage_detail",
                    }
        
        # Insured Name (IMPROVED)
        if "insured_name" not in self.fields and ":" in line:
            label, _, val = line.partition(":")
            label_lower = label.lower().strip()
            
            # Check if this is an insured label
            if any(k in label_lower for k in ("insured", "policyholder")):
                # CRITICAL: Skip if label contains mortgagee terms or interest-type labels
                if any(bad in label_lower for bad in (
                    "mortgagee", "loss payee", "lender",
                    "interest of", "interest in",  # "Interest of Named Insured In Such Premises"
                    "additional insured",
                )):
                    pass  # Skip this
                else:
                    v = _normalize_name(val)
                    if v and _looks_like_name(v):
                        self.fields["insured_name"] = {
                            "value": v,
                            "confidence": 0.99,
                            "source": "inline",
                        }
                    elif v and len(v.strip()) > 3:
                        # Value on same line might be partial - check next line context
                        # Store as potential first part of multi-line name
                        self._partial_insured = v.strip()
        
        # Loan Number (IMPROVED)
        # Labeled loan numbers (with "Loan Number:" prefix) override unlabeled ones
        has_loan_label = any(k in ll for k in LOAN_LABELS)
        existing_loan = self.fields.get("loan_number", {})
        existing_is_unlabeled = existing_loan.get("source") in ("mortgage_block", "sweep") if existing_loan else False
        
        if has_loan_label and ("loan_number" not in self.fields or existing_is_unlabeled):
            if ":" in line:
                _, _, v = line.partition(":")
                digits = ''.join(c for c in v if c.isdigit())
            else:
                # Try to find number on line
                digits = ''
                for token in line.split():
                    d = ''.join(c for c in token if c.isdigit())
                    if len(d) >= 7:
                        digits = d
                        break
            
            if _looks_like_loan_number(digits):
                self.fields["loan_number"] = {
                    "value": digits,
                    "confidence": 0.96,
                    "source": "inline",
                }
        
        # Dates
        if "effective_date" not in self.fields:
            date = _extract_date(line, DATE_LABELS_EFFECTIVE)
            if date:
                self.fields["effective_date"] = {
                    "value": date,
                    "confidence": 0.95,
                    "source": "inline",
                }
        
        if "expiration_date" not in self.fields:
            date = _extract_date(line, DATE_LABELS_EXPIRATION)
            if date:
                self.fields["expiration_date"] = {
                    "value": date,
                    "confidence": 0.95,
                    "source": "inline",
                }
        
        # --- INS observation batch: Section 10 - Inline Mortgage/Loss Payee ---
        # Pattern: "Mortgagee/Loss Payee: BANK NAME"
        if "mortgage_company" not in self.fields:
            m_mtg = re.search(
                r'(?i)(?:mortgagee\s*/?\s*loss\s*payee|loss\s*payee\s*/?\s*mortgagee'
                r'|first\s+mortgage|1st\s+mortgage)\s*:\s*(.+)',
                line
            )
            if m_mtg:
                mtg_val = m_mtg.group(1).strip()
                # Clean up trailing address/noise
                mtg_val = re.sub(r'\s+\d{3,}.*$', '', mtg_val).strip()
                mtg_val = re.sub(r'\s+ISAOA.*$', '', mtg_val, flags=re.I).strip()
                mtg_val = re.sub(r'\s+ATIMA.*$', '', mtg_val, flags=re.I).strip()
                if mtg_val and len(mtg_val) > 3:
                    self.fields["mortgage_company"] = {
                        "value": mtg_val,
                        "confidence": 0.96,
                        "source": "inline_mortgagee_loss_payee",
                    }
        
        # --- INS observation batch: Section 11 - Cancellation/Third Party Events ---
        # "Terminate this Policy Effective: DATE"
        if "cancellation_effective_date" not in self.fields:
            m_term = re.search(
                r'(?i)terminate\s+this\s+policy\s+effective\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                line
            )
            if m_term:
                self.fields["cancellation_effective_date"] = {
                    "value": m_term.group(1),
                    "confidence": 0.97,
                    "source": "inline_terminate_policy",
                }
        
        # "Deleted as loss payee effective DATE"
        if "third_party_removed" not in self.fields:
            if re.search(r'(?i)deleted\s+as\s+loss\s+payee\s+effective', line):
                self.fields["third_party_removed"] = {
                    "value": True,
                    "confidence": 0.95,
                    "source": "inline_deleted_loss_payee",
                }
                d = _extract_date(line, {"effective"})
                if d:
                    self.fields["third_party_cancellation_date"] = {
                        "value": d,
                        "confidence": 0.93,
                        "source": "inline_deleted_loss_payee_date",
                    }
        
        # "Mortgage Interest Removed"
        if "third_party_removed" not in self.fields:
            if re.search(r'(?i)mortgage\s+interest\s+removed', line):
                self.fields["third_party_removed"] = {
                    "value": True,
                    "confidence": 0.96,
                    "source": "inline_mortgage_interest_removed",
                }
        
        # Date range pattern: "MM/DD/YYYY to MM/DD/YYYY" or "MM-DD-YYYY to MM-DD-YYYY"
        # Extracts both effective and expiration dates from a single line
        if "effective_date" not in self.fields or "expiration_date" not in self.fields:
            date_range = re.search(
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+to\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                line
            )
            if date_range:
                if "effective_date" not in self.fields:
                    self.fields["effective_date"] = {
                        "value": date_range.group(1),
                        "confidence": 0.96,
                        "source": "inline_date_range",
                    }
                if "expiration_date" not in self.fields:
                    self.fields["expiration_date"] = {
                        "value": date_range.group(2),
                        "confidence": 0.96,
                        "source": "inline_date_range",
                    }
            # Try abbreviated month date range: "NOV 09 2021 to NOV 09 2022"
            elif "effective_date" not in self.fields or "expiration_date" not in self.fields:
                abbrev_range = re.search(
                    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})'
                    r'\s+to\s+'
                    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})',
                    line, re.I
                )
                if abbrev_range:
                    if "effective_date" not in self.fields:
                        self.fields["effective_date"] = {
                            "value": abbrev_range.group(1),
                            "confidence": 0.96,
                            "source": "inline_date_range",
                        }
                    if "expiration_date" not in self.fields:
                        self.fields["expiration_date"] = {
                            "value": abbrev_range.group(2),
                            "confidence": 0.96,
                            "source": "inline_date_range",
                        }
            # Also try written date range: "January 1, 2020 to January 1, 2021"
            elif "effective_date" not in self.fields or "expiration_date" not in self.fields:
                written_dates = DATE_WRITTEN_RE.findall(line)
                if len(written_dates) >= 2:
                    if "effective_date" not in self.fields:
                        self.fields["effective_date"] = {
                            "value": written_dates[0],
                            "confidence": 0.96,
                            "source": "inline_date_range",
                        }
                    if "expiration_date" not in self.fields:
                        self.fields["expiration_date"] = {
                            "value": written_dates[1],
                            "confidence": 0.96,
                            "source": "inline_date_range",
                        }
        
        # "Policy Period:" on its own line — flag for lookahead on next lines
        if "effective_date" not in self.fields and "policy period" in ll:
            self._pending_policy_period = True
        elif getattr(self, '_pending_policy_period', False):
            # Look for date or date range on this line
            date_range = re.search(
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+to\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                line
            )
            abbrev_range = re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})'
                r'\s+to\s+'
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})',
                line, re.I
            )
            if date_range:
                if "effective_date" not in self.fields:
                    self.fields["effective_date"] = {
                        "value": date_range.group(1),
                        "confidence": 0.95,
                        "source": "policy_period_lookahead",
                    }
                if "expiration_date" not in self.fields:
                    self.fields["expiration_date"] = {
                        "value": date_range.group(2),
                        "confidence": 0.95,
                        "source": "policy_period_lookahead",
                    }
                self._pending_policy_period = False
            elif abbrev_range:
                if "effective_date" not in self.fields:
                    self.fields["effective_date"] = {
                        "value": abbrev_range.group(1),
                        "confidence": 0.95,
                        "source": "policy_period_lookahead",
                    }
                if "expiration_date" not in self.fields:
                    self.fields["expiration_date"] = {
                        "value": abbrev_range.group(2),
                        "confidence": 0.95,
                        "source": "policy_period_lookahead",
                    }
                self._pending_policy_period = False
            else:
                m = DATE_RE.search(line) or DATE_ABBREV_RE.search(line)
                if m:
                    if "effective_date" not in self.fields:
                        self.fields["effective_date"] = {
                            "value": m.group(0),
                            "confidence": 0.93,
                            "source": "policy_period_lookahead",
                        }
                    self._pending_policy_period = False
                elif not line.strip():
                    self._pending_policy_period = False
        
        # Carrier from "underwritten by", "your insurer", or "insurance provided by"
        if "carrier_name" not in self.fields:
            if any(k in ll for k in ("underwritten by", "your insurer", "insurance provided by")):
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    # Strip trailing noise like "Customer assistance number:"
                    v = re.sub(
                        r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
                        r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
                        '', v, flags=re.I
                    ).strip()
                    if v and len(v) > 5:
                        has_carrier_word = any(w in v.lower() for w in 
                            ('insurance', 'indemnity', 'casualty', 'assurance',
                             'company', 'exchange', 'group', 'mutual', 'corp'))
                        is_agent = any(w in v.lower() for w in ('agency', 'agent'))
                        if has_carrier_word and not is_agent:
                            self.fields["carrier_name"] = {
                                "value": v.upper(),
                                "confidence": 0.98,
                                "source": "inline_carrier",
                            }
        
        # Total Premium
        if "total_premium" not in self.fields:
            premium_labels = (
                "total annual policy premium", "total annual premium",
                "total policy premium", "total premium",
                "total residence premium", "annual premium",
                "total annual policy cost", "full term premium",
            )
            if any(k in ll for k in premium_labels):
                # Try to find dollar amount on same line
                money = re.findall(r'\$[\d,]+\.?\d*', line)
                if money:
                    self.fields["total_premium"] = {
                        "value": money[-1],  # Take last (usually the total)
                        "confidence": 0.96,
                        "source": "inline_premium",
                    }
                else:
                    # Mark that we need to look at next lines for the amount
                    self._pending_premium = True
            elif getattr(self, '_pending_premium', False):
                # Look for dollar amount on the line following a premium label
                money = re.findall(r'\$[\d,]+\.?\d*', line)
                if money:
                    self.fields["total_premium"] = {
                        "value": money[-1],
                        "confidence": 0.93,
                        "source": "inline_premium_lookahead",
                    }
                    self._pending_premium = False
                elif ll.strip() and not ll.strip().startswith("$"):
                    # Non-empty non-dollar line — stop looking
                    self._pending_premium = False
    
    def _policy(self, line: str):
        """Extract policy number from POLICY block"""
        if "policy_number" in self.fields:
            return
        
        # Try each token
        for token in line.split():
            clean_token = _clean(token)
            if _looks_like_policy(clean_token):
                self.fields["policy_number"] = {
                    "value": clean_token,
                    "confidence": 0.96,
                    "source": "block",
                }
                return
        
        # Try the whole line (handles spaces in policy numbers)
        clean_line = _clean(line)
        no_spaces = clean_line.replace(" ", "")
        if _looks_like_policy(no_spaces):
            self.fields["policy_number"] = {
                "value": no_spaces,
                "confidence": 0.94,
                "source": "block_combined",
            }
    
    def _insured(self, line: str):
        """Extract insured name from INSURED block - IMPROVED"""
        ll = line.lower().strip()
        
        # Skip obvious non-name lines
        skip_patterns = [
            "po box", "policy period", "loan number", "policy type",
            "description", "coverage", "premium", "effective", "expiration",
            "page", "continued", "summary", "mortgagee", "loss payee",
            "mailing address",
        ]
        if any(p in ll for p in skip_patterns):
            return
        
        # Skip if line is just a header
        if line.strip().endswith(":"):
            return
        if ll in [l.lower() for l in INSURED_LABELS]:
            return
        
        # CRITICAL: Skip if line looks like a label fragment
        if ll.startswith("and ") or ll.startswith("or "):
            return
        
        clean_line = _normalize_name(line)
        
        # Strip trailing date patterns (e.g., "Dummy Name July 2020" -> "Dummy Name")
        clean_line = re.sub(
            r'\s+(January|February|March|April|May|June|July|August|September|'
            r'October|November|December)\s+\d{4}\s*$',
            '', clean_line, flags=re.I
        ).strip()
        
        # CRITICAL: Additional check - block mortgagee-related values
        if any(bad in ll for bad in BAD_INSURED_TERMS):
            return
        
        # Skip generic section headers that look like names but aren't
        section_headers = {
            "home protection", "personal liability", "medical expenses",
            "personal property", "dwelling coverage", "loss settlement",
            "hurricane premium", "building ordinance", "property protection",
            "coverage", "property protection", "renewal certificate",
            "supplemental declarations", "medical office",
        }
        if clean_line.lower().strip() in section_headers:
            return
        
        # Check for multi-line name combination (e.g., "DUMMY NAME" + "PROPERTIES, LLC")
        if self._partial_insured and "insured_name" not in self.fields:
            # Try combining with previous partial
            combined = self._partial_insured + " " + clean_line
            if _looks_like_name(combined):
                self.fields["insured_name"] = {
                    "value": combined,
                    "confidence": 0.96,
                    "source": "block_combined",
                }
                self._partial_insured = ""
                return
        
        # Check if it's a name
        if _looks_like_name(clean_line):
            if "insured_name" not in self.fields:
                self.fields["insured_name"] = {
                    "value": clean_line,
                    "confidence": 0.97,
                    "source": "block",
                }
                # Don't clear _partial — set it so next line can extend
                self._partial_insured = clean_line
            elif self._partial_insured:
                # Already have a name — check if this extends it
                # (e.g., "PROPERTIES, LLC" extending "DUMMY NAME")
                combined = self._partial_insured + " " + clean_line
                if _looks_like_name(combined):
                    self.fields["insured_name"] = {
                        "value": combined,
                        "confidence": 0.97,
                        "source": "block_extended",
                    }
                self._partial_insured = ""
            return
        
        # Check if current line is a business suffix that extends the existing name
        if "insured_name" in self.fields and self._partial_insured:
            business_suffixes = ("llc", "inc", "corp", "ltd", "co", "properties",
                                 "enterprises", "holdings", "investments", "group",
                                 "associates", "partners", "trust", "estate")
            clean_lower = clean_line.lower().strip().rstrip(".,")
            if any(clean_lower.startswith(s) or clean_lower.endswith(s) for s in business_suffixes):
                combined = self._partial_insured + " " + clean_line
                self.fields["insured_name"] = {
                    "value": combined,
                    "confidence": 0.97,
                    "source": "block_extended",
                }
            self._partial_insured = ""
            return
        
        # If it might be first part of multi-line name (single word, uppercase)
        if clean_line.isupper() and len(clean_line.split()) <= 2 and "insured_name" not in self.fields:
            # Check if it looks like a name part (not a header)
            if not any(w in clean_line.lower() for w in ("page", "policy", "coverage")):
                self._partial_insured = clean_line
                return
        
        # Check if it's an address (capture for mailing)
        if _looks_like_address(line):
            if "mailing_address" not in self.fields:
                # Check if line has "Label: Value" format
                address_value = line.strip()
                if ":" in line:
                    _, _, val = line.partition(":")
                    val = val.strip()
                    if val and _looks_like_address(val):
                        address_value = val
                
                self.fields["mailing_address"] = {
                    "value": address_value,
                    "confidence": 0.92,
                    "source": "insured_block",
                }
    
    def _property(self, line: str):
        """Extract property address from PROPERTY block"""
        ll = line.lower().strip()
        
        # Skip headers and labels
        if line.strip().endswith(":"):
            return
        if ll in [t.lower() for t in PROPERTY_TRIGGERS]:
            return
        
        # Check if line has "Label: Value" format
        address_value = line.strip()
        if ":" in line:
            label, _, val = line.partition(":")
            val = val.strip()
            # If value part looks like an address, use just the value
            if val and _looks_like_address(val):
                address_value = val
        
        if _looks_like_address(address_value):
            if "property_address" not in self.fields:
                self.fields["property_address"] = {
                    "value": address_value,
                    "confidence": 0.98,
                    "source": "block",
                }
            else:
                current = self.fields["property_address"]["value"]
                has_street_number = bool(re.match(r'^\d+\s+', current.strip()))
                new_has_street = bool(re.match(r'^\d+\s+', address_value.strip()))
                
                # Check if this looks like a city/state/zip continuation
                # (no street number, follows a street line)
                is_city_continuation = (
                    has_street_number and not new_has_street
                    and re.search(r'[A-Z]{2}\s+\d{5}', address_value)  # Has state + zip
                    and "," not in current  # Current doesn't already have city
                )
                
                if is_city_continuation:
                    self.fields["property_address"]["value"] = current + ", " + address_value
                elif new_has_street and not has_street_number:
                    self.fields["property_address"]["value"] = address_value
                elif len(address_value) > len(current) and (new_has_street or not has_street_number):
                    self.fields["property_address"]["value"] = address_value
    
    def _mailing(self, line: str):
        """Extract mailing address from MAILING block"""
        if line.strip().endswith(":"):
            return
        
        if _looks_like_address(line):
            addr_val = line.strip()
            # Strip trailing date/time patterns
            addr_val = re.sub(
                r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+'
                r'(January|February|March|April|May|June|July|August|September|'
                r'October|November|December)\s+\d{1,2},?\s+\d{4}.*$',
                '', addr_val, flags=re.I
            ).strip()
            addr_val = re.sub(
                r'\s+(Beginning|Ending|through|From|Starting|Effective)\s+\d{1,2}/\d{1,2}/\d{4}.*$',
                '', addr_val, flags=re.I
            ).strip()
            if addr_val:
                if "mailing_address" not in self.fields:
                    self.fields["mailing_address"] = {
                        "value": addr_val,
                        "confidence": 0.96,
                        "source": "mailing_block",
                    }
                else:
                    # Append city/state/zip to existing PO Box or street
                    existing = self.fields["mailing_address"]["value"]
                    # Only append if it looks like a continuation (city/state/zip)
                    if addr_val and not addr_val.lower().startswith("po box"):
                        self.fields["mailing_address"]["value"] = existing + ", " + addr_val
        elif _looks_like_name(line) and "insured_name" not in self.fields:
            self.fields["insured_name"] = {
                "value": _normalize_name(line),
                "confidence": 0.90,
                "source": "mailing_block",
            }
        elif "insured_name" in self.fields and self.fields["insured_name"].get("source") == "mailing_block":
            # Check if this is a continuation of the name (e.g., "PROPERTIES, LLC")
            clean = _normalize_name(line)
            if clean and _looks_like_name(clean) and not _looks_like_address(line):
                existing = self.fields["insured_name"]["value"]
                # Only append if it looks like a continuation (LLC, Inc, Corp, etc.)
                # or if the combined result still looks like a name
                combined = existing + " " + clean
                if _looks_like_name(combined):
                    self.fields["insured_name"]["value"] = combined
    
    def _mortgage(self, line: str):
        """Extract mortgage company and loan number from MORTGAGE block"""
        ll = line.lower()
        
        # Skip headers (including ":." variant from OCR)
        stripped = line.strip().rstrip(".")
        if stripped.endswith(":"):
            return
        
        # Skip bad patterns (EXPANDED)
        bad_patterns = [
            "policy", "coverage", "endorsement", "homeowners", "premium",
            "first mortgagee", "second mortgagee", "third mortgagee",
            "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
            "mortgagee copy", "mortgagee certificate",
            "other interest", "type of interest",
        ]
        if any(p in ll for p in bad_patterns):
            return
        
        # Loan number — also capture "N/A" style loan indicators
        if "loan_number" not in self.fields:
            has_loan_label = any(k in ll for k in ("loan no", "loan number", "loan #", "loan id", "ln #", "mortgage loan"))
            if has_loan_label:
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    if re.match(r'^n/?a\b', v, re.I):
                        self.fields["loan_number"] = {
                            "value": "N/A",
                            "confidence": 0.90,
                            "source": "mortgage_block",
                        }
                    else:
                        digits = ''.join(c for c in v if c.isdigit())
                        if _looks_like_loan_number(digits):
                            self.fields["loan_number"] = {
                                "value": digits,
                                "confidence": 0.94,
                                "source": "mortgage_block",
                            }
            elif not _looks_like_address(line):
                # Only scan tokens for loan number if line is NOT an address
                for token in line.split():
                    digits = ''.join(c for c in token if c.isdigit())
                    if _looks_like_loan_number(digits):
                        self.fields["loan_number"] = {
                            "value": digits,
                            "confidence": 0.90,
                            "source": "mortgage_block",
                        }
                        break
        
        # Mortgage company
        if "mortgage_company" not in self.fields:
            # Look for company-like patterns
            if any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "federal", "financial")):
                # CRITICAL: Skip if it's just a label like "First Mortgagee"
                if re.match(r'^(first|second|third|1st|2nd|3rd)\s+(mortgagee|lender)', ll):
                    return
                
                clean = line.strip()
                # Remove label prefixes like "holder:", "mortgagee:", etc.
                clean = re.sub(r'^(holder|mortgagee|loss\s+payee|lienholder|lien\s+holder)\s*:\s*', '', clean, flags=re.I)
                # Remove ISAOA/ATIMA/SUCC suffixes
                clean = re.sub(r'\s+(ITS\s+SUCC(\s+AND/OR\s+ASSIGNS)?\s+)?(ISAOA|ATIMA|ISAOA/ATIMA).*$', '', clean, flags=re.I)
                clean = re.sub(r'\s+ITS\s+SUCC\s+AND/OR\s+ASSIGNS.*$', '', clean, flags=re.I)
                # Remove numbering prefixes
                clean = re.sub(r'^(\d+\.?\s*|first\s+|second\s+|third\s+)', '', clean, flags=re.I)
                
                if len(clean) > 5:
                    self.fields["mortgage_company"] = {
                        "value": clean,
                        "confidence": 0.94,
                        "source": "mortgage_block",
                    }
    
    def _carrier(self, line: str):
        """Extract carrier name from CARRIER block"""
        if "carrier_name" in self.fields:
            return
        
        ll = line.lower()
        
        # Skip headers
        if line.strip().endswith(":"):
            return
        
        # Look for insurance company patterns
        # Include "indemnity", "casualty" as alternatives to "insurance"
        has_insurer_word = any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance'))
        has_company_type = any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp'))
        is_agent_line = any(w in ll for w in ('agency', 'agent', 'services', 'producer'))
        
        if has_insurer_word and has_company_type and not is_agent_line:
            # Strip trailing noise like "Customer assistance number:" 
            carrier_val = line.strip()
            carrier_val = re.sub(
                r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
                r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
                '', carrier_val, flags=re.I
            ).strip()
            self.fields["carrier_name"] = {
                "value": carrier_val.upper(),
                "confidence": 0.96,
                "source": "carrier_block",
            }
    
    def finalize(self):
        """Final cleanup and flush"""
        self._flush_accumulators()


# ============================================================
# SAFE SWEEP (FALLBACK)
# ============================================================

def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
    """Final pass to catch missed fields"""
    
    # --- Policy Number fallback ---
    if "policy_number" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in POLICY_LABELS):
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = _clean(v).replace(" ", "")
                    if _looks_like_policy(v):
                        fields["policy_number"] = {
                            "value": v,
                            "confidence": 0.88,
                            "source": "sweep",
                        }
                        break
                
                # Check next few lines
                for j in range(i + 1, min(i + 3, len(lines))):
                    candidate = _clean(lines[j]).replace(" ", "")
                    if _looks_like_policy(candidate):
                        fields["policy_number"] = {
                            "value": candidate,
                            "confidence": 0.85,
                            "source": "sweep_lookahead",
                        }
                        break
                if "policy_number" in fields:
                    break
    
    # --- Insured Name fallback (IMPROVED) ---
    if "insured_name" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in INSURED_LABELS):
                # CRITICAL: Skip if it's a mortgagee section
                if any(bad in ll for bad in ("mortgagee", "loss payee")):
                    continue
                
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = _normalize_name(v)
                    if _looks_like_name(v):
                        fields["insured_name"] = {
                            "value": v,
                            "confidence": 0.88,
                            "source": "sweep",
                        }
                        break
                
                # Check next few lines
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = _normalize_name(lines[j])
                    if _looks_like_name(candidate):
                        fields["insured_name"] = {
                            "value": candidate,
                            "confidence": 0.85,
                            "source": "sweep_lookahead",
                        }
                        break
                if "insured_name" in fields:
                    break
    
    # --- Property Address fallback ---
    if "property_address" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in PROPERTY_TRIGGERS):
                for j in range(i + 1, min(i + 5, len(lines))):
                    if _looks_like_address(lines[j]):
                        fields["property_address"] = {
                            "value": lines[j].strip(),
                            "confidence": 0.84,
                            "source": "sweep_lookahead",
                        }
                        break
                if "property_address" in fields:
                    break
    
    # --- Carrier Name fallback (scan first 20 lines) ---
    if "carrier_name" not in fields:
        # First, look for "underwritten by" or "your insurer" patterns
        for line in lines[:30]:
            ll = line.lower()
            if "underwritten by" in ll or "your insurer" in ll:
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    if 'insurance' in v.lower():
                        fields["carrier_name"] = {
                            "value": v.upper(),
                            "confidence": 0.90,
                            "source": "sweep_underwritten",
                        }
                        break
        
        # Then try direct insurance company pattern
        if "carrier_name" not in fields:
            for line in lines[:20]:
                ll = line.lower()
                if any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance')):
                    if any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
                        if not any(w in ll for w in ('agency', 'agent', 'services')):
                            carrier_val = _extract_carrier_name(line.strip())
                            if carrier_val and _looks_like_carrier(carrier_val):
                                fields["carrier_name"] = {
                                    "value": carrier_val.upper(),
                                    "confidence": 0.85,
                                    "source": "sweep_header",
                                }
                                break
        
        # Known carrier name fallback — carriers without "insurance"/"company" keywords
        # (e.g., "ALLIED TRUST", "TOWER HILL", "SOUTHERN OAK")
        if "carrier_name" not in fields:
            _KNOWN_CARRIERS_SWEEP = {
                "allied trust", "tower hill", "southern oak", "peoples trust",
                "security first", "homeowners choice", "heritage",
                "florida peninsula", "citizens property", "federated national",
                "universal property", "auto-owners", "encompass",
            }
            for line in lines[:15]:
                ll = line.lower().strip()
                for c in _KNOWN_CARRIERS_SWEEP:
                    if c == ll or ll.startswith(c):
                        fields["carrier_name"] = {
                            "value": line.strip().upper(),
                            "confidence": 0.88,
                            "source": "sweep_known_carrier",
                        }
                        break
                if "carrier_name" in fields:
                    break
    
    # --- Loan Number fallback ---
    if "loan_number" not in fields:
        for line in lines:
            ll = line.lower()
            if any(k in ll for k in LOAN_LABELS):
                # Try to extract number from line
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    # Handle N/A loan numbers (with or without slash)
                    if re.match(r'^n/?a\b', v, re.I):
                        fields["loan_number"] = {
                            "value": "N/A",
                            "confidence": 0.85,
                            "source": "sweep",
                        }
                        break
                    digits = ''.join(c for c in v if c.isdigit())
                else:
                    digits = ''.join(c for c in line if c.isdigit())
                
                if _looks_like_loan_number(digits):
                    fields["loan_number"] = {
                        "value": digits,
                        "confidence": 0.85,
                        "source": "sweep",
                    }
                    break
    
    # --- Total Premium fallback ---
    if "total_premium" not in fields:
        premium_labels = (
            "total annual policy premium", "total annual premium",
            "total policy premium", "total premium",
            "total residence premium", "annual premium",
            "total annual policy cost", "full term premium",
        )
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in premium_labels):
                # Check same line for dollar amount
                money = re.findall(r'\$[\d,]+\.?\d*', line)
                if money:
                    fields["total_premium"] = {
                        "value": money[-1],
                        "confidence": 0.85,
                        "source": "sweep_premium",
                    }
                    break
                # Check next lines — take the LAST dollar amount found
                # (in two-column layouts, the total is the last amount)
                last_money = None
                for j in range(i + 1, min(i + 20, len(lines))):
                    money_j = re.findall(r'\$[\d,]+\.?\d*', lines[j])
                    if money_j:
                        last_money = money_j[-1]
                if last_money:
                    fields["total_premium"] = {
                        "value": last_money,
                        "confidence": 0.82,
                        "source": "sweep_premium_lookahead",
                    }
                    break


# ============================================================
# ENTRY POINTS
# ============================================================

# ---- CAN-specific field patterns ----
_CAN_DATE_PATTERNS = re.compile(
    r"(?i)(?:cancellation|cancel(?:led)?|termination|void|cease|non-?renewal)"
    r"(?:\s+effective|\s+date)?(?:\s+(?:is|will\s+be))?\s*[:\-]?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
)
_CAN_REASON_LABELS = re.compile(
    r"(?i)(?:reason\s+for\s+(?:cancellation|termination)|cancel(?:lation)?\s+reason"
    r"|reason\s*:)\s*(.{4,80})"
)
_BALANCE_DUE_PATTERNS = re.compile(
    r"(?i)(?:balance\s+(?:to\s+pay|due)|amount\s+due|total\s+(?:amount\s+)?due"
    r"|minimum\s+(?:amount\s+)?due|to\s+pay\s+in\s+full)\s*[:\$]?\s*\$?([\d,]+\.?\d*)"
)
_ISSUE_DATE_PATTERNS = re.compile(
    r"(?i)(?:bill\s+date|invoice\s+date|statement\s+date|issue\s+date"
    r"|billing\s+date|due\s+date|information\s+as\s+of|processed\s+on)\s*[:\-]?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})"
)
_REMIT_PATTERNS = re.compile(
    r"(?i)(?:mail\s+to|remit\s+to|payable\s+to|make\s+check[s]?\s+payable\s+to"
    r"|send\s+payment\s+to|payment\s+to)\s*[:\-]?\s*(.{4,80})"
)


def _extract_can_inv_fields(lines: List[str], fields: Dict[str, Dict]) -> None:
    """
    Doc-type-aware sweep for CAN and INV specific fields.
    Stage1 normally doesn't extract these — this function fills the gap.
    Called after _safe_sweep() so it only adds fields that Stage1 missed.
    """
    text = "\n".join(lines)

    # --- CANCELLATION DATE ---
    if "cancellation_date" not in fields:
        m = _CAN_DATE_PATTERNS.search(text)
        if m:
            fields["cancellation_date"] = {
                "value": m.group(1).strip(),
                "confidence": 0.82,
                "source": "stage1_can_date",
            }

    # --- CANCELLATION REASON ---
    if "cancellation_reason" not in fields:
        m = _CAN_REASON_LABELS.search(text)
        if m:
            reason = m.group(1).strip().rstrip(".")
            # Filter out dates and garbage
            if len(reason) > 3 and not re.match(r"^\d", reason):
                fields["cancellation_reason"] = {
                    "value": reason,
                    "confidence": 0.78,
                    "source": "stage1_can_reason",
                }

    # --- BALANCE DUE ---
    if "balance_due" not in fields:
        m = _BALANCE_DUE_PATTERNS.search(text)
        if m:
            fields["balance_due"] = {
                "value": "$" + m.group(1).strip(),
                "confidence": 0.83,
                "source": "stage1_inv_balance",
            }

    # --- ISSUE DATE ---
    if "issue_date" not in fields:
        m = _ISSUE_DATE_PATTERNS.search(text)
        if m:
            fields["issue_date"] = {
                "value": m.group(1).strip(),
                "confidence": 0.82,
                "source": "stage1_inv_issue_date",
            }

    # --- REMIT INFO ---
    if "remit_info" not in fields:
        m = _REMIT_PATTERNS.search(text)
        if m:
            remit = m.group(1).strip()
            if len(remit) > 3:
                fields["remit_info"] = {
                    "value": remit,
                    "confidence": 0.78,
                    "source": "stage1_inv_remit",
                }


def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    """Main entry point for Stage 1 extraction"""
    if not lines:
        return {}
    
    extractor = StatefulExtractor()
    
    for raw in lines:
        line = raw.strip()
        if line:
            extractor.update_role(line)
            extractor.extract(line)
    
    extractor.finalize()
    _safe_sweep(lines, extractor.fields)
    _extract_can_inv_fields(lines, extractor.fields)   # ← NEW: CAN + INV fields
    
    return extractor.fields


def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    """Alias for backward compatibility"""
    return extract_fields(lines, layout_elements)