# import re
# from datetime import datetime
# from typing import Dict, Tuple, Set, List, Optional

# # ============================================================
# # CONFIGURATION
# # ============================================================
# CONFIDENCE_FLOORS = {
#     "carrier_name": 0.80, "policy_number": 0.80, "loan_number": 0.80, "insured_name": 0.75,
#     "property_address": 0.75, "mailing_address": 0.70, "mortgage_company": 0.75, "total_premium": 0.70,
#     "deductible": 0.70, "effective_date": 0.75, "expiration_date": 0.75, "agent_phone": 0.75, "agent_name": 0.70
# }
# DEFAULT_FLOOR = 0.65

# # Field Groups
# _INV_FIELDS = ["carrier_name", "insured_name", "policy_number", "balance_due", "issue_date", "remit_info", "effective_date", "expiration_date", "property_address", "loan_number", "mortgage_company", "total_premium"]
# _CAN_FIELDS = ["carrier_name", "policy_number", "insured_name", "effective_date", "expiration_date", "cancellation_date", "cancellation_reason", "property_address", "mortgage_company", "loan_number", "cancellation_effective_date"]
# _RNW_FIELDS = ["carrier_name", "policy_number", "insured_name", "effective_date", "expiration_date", "property_address", "mailing_address", "mortgage_company", "loan_number", "total_premium"]
# _DOI_FIELDS = ["policy_number", "mortgage_company", "loan_number", "carrier_name", "insured_name", "property_address", "third_party_removed", "third_party_cancellation_date"]

# # Allowed Fields Map
# ALLOWED_FIELDS_BY_DOC_POLICY = {}
# for pt in ["HAZ", "HO", "HO3", "HO6", "FIR", "FLD", "WND", "DP3", "AUTO", "LL", "UO", "ERQ", "UNK", "BREQ", "NPAY", "NRNW", "UNWR", "CEL"]:
#     ALLOWED_FIELDS_BY_DOC_POLICY[("INV", pt)] = _INV_FIELDS
# for pt in ["HO", "HO3", "HO6", "HAZ", "FIR", "FLD", "WND", "DP3", "AUTO", "LL", "UO", "ERQ", "UNK", "NRNW", "UNWR", "CEL", "BREQ", "NPAY", "OTH"]:
#     ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("CAN", pt), _CAN_FIELDS)
#     ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("RNW", pt), _RNW_FIELDS)
#     ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("DOI", pt), _DOI_FIELDS)

# # Smart Hints for Missing Logic
# FIELD_LABEL_HINTS = {
#     "policy_number": ["policy number", "policy #", "policy no", "pol num", "policy id"],
#     "loan_number": ["loan number", "loan #", "mortgage number", "loan no", "account number"],
#     "insured_name": ["insured", "named insured", "policyholder", "customer name"],
#     "carrier_name": ["insurance company", "carrier", "insurer", "company name", "underwriter"],
#     "property_address": ["property address", "location", "risk address", "insured location", "premises"],
#     "mailing_address": ["mailing address", "mail to", "billing address"],
#     "effective_date": ["effective date", "policy period", "period begins", "eff date", "from"],
#     "expiration_date": ["expiration date", "period ends", "valid until", "exp date", "to"],
#     "total_premium": ["total premium", "premium", "policy total", "annual premium"],
#     "balance_due": ["balance due", "amount due", "pay this amount", "total due", "min due"],
#     "mortgage_company": ["mortgagee", "mortgage company", "lender", "lienholder", "interested party"],
#     "cancellation_date": ["cancellation date", "cancel date", "effective date of cancellation"],
#     "cancellation_reason": ["reason", "reason for cancellation", "reason for non-renewal"],
#     "deductible": ["deductible", "all perils", "wind/hail"],
# }

# # Block Lists & Regex
# SECTION_TITLES = {"summary", "home protection", "coverage", "coverages", "limits", "policy mortgage declarations summary", "declarations", "declarations summary", "mortgage/other interested parties", "applicable deductible(s)", "premiums", "forms and endorsements", "policy period", "policyholder since", "billing information", "payment plan", "discount information", "for your information", "important notice", "thank you", "office use space", "message(s)", "mortgagee(s)", "endorsements", "schedule", "notice", "rating information", "additional coverages", "discounts"}
# JUNK_VALUES = {"type", "interest", "policy", "coverage", "summary", "n/a", "none", "see attached", "continued", "page", "na", "tbd", "pending", "unknown", "included", "see policy"}
# MARKETING_SLOGANS = {"you're in good hands", "you're in good hands.", "youre in good hands", "on your side", "like a good neighbor", "we're all in this together", "nationwide is on your side", "for all that matters", "the promise", "keep the promise"}
# BAD_NAME_PHRASES = {"policy payment", "quickly & easily", "quickly and easily", "online", "pocket expenses", "out of pocket", "out-of-pocket", "and policy information", "policy information", "page 1 of", "page 2 of", "page 3 of", "mortgagee copy", "declarations page", "your policy", "our policy", "this policy", "policy conditions", "policy type", "policy period", "coverage detail", "coverage info", "premium info", "building type", "single family", "construction type", "roof-wall connection", "roof connection", "roof deck", "additional insured", "first named insured", "named insured:", "location id", "location of", "described location", "effective date", "expiration date", "endorsement", "deductible", "important notice", "special provisions"}
# PRODUCT_NAMES = {"homesaver polcy", "homesaver policy", "homeowners policy", "dwelling policy", "mobilehome policy", "mobilehomeowners", "special form policy", "wind only policy", "condominium policy", "condominium owners", "rental unit owners", "ultrapack plus", "encompassone", "encompass one"}
# BAD_INSURED_COMPANY_NAMES = {"allied trust", "aegis", "aegis security", "aegis security insurance", "a egis", "properiy insurance", "property insurance", "insurance corporation", "insurance company", "insurance exchange", "mortgage company", "mortgage corp", "financial inc", "lending llc", "bank na"}
# BAD_CARRIER_PATTERNS = {"properiy insurance", "property insurance corporaion", "property insurance corporaiion", "insurance exchange*", "insurance company*", "insurance agency", "insurance services", "insurance center", "everett financial", "broker solutions", "nancy bond insurance", "geico ins agency", "allstate mortgage"}
# MORTGAGE_PO_BOX_PATTERNS = [r"p\.?o\.?\s*box\s*\d+.*troy.*mi", r"p\.?o\.?\s*box\s*\d+.*48007", r"p\.?o\.?\s*box\s*\d+.*miami.*fl.*33197", r"p\.?o\.?\s*box\s*\d+.*dallas.*tx.*75266"]
# PREFIX_STRIP = ["coverage detail for", "policy effective date is", "effective date is", "your policy effective date is", "your policy effective date:", "location:", "address:", "name:", "insured:", "named insured:", "property:", "mailing:", "first named insured:", "policyholder(s)", "policyholder:"]
# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'); DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'); ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b'); PO_BOX_RE = re.compile(r'p\.?o\.?\s*box', re.I)
# STREET_TYPES = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd', 'lane', 'ln', 'drive', 'dr', 'court', 'ct', 'circle', 'cir', 'way', 'place', 'pl', 'terrace', 'ter', 'highway', 'hwy', 'parkway', 'pkwy', 'ridge']

# # ============================================================
# # HELPERS & LOGIC
# # ============================================================
# def _normalize_whitespace(v: str) -> str: return re.sub(r'\s+', ' ', v).strip()
# def _strip_prefixes(v: str) -> str:
#     v = v.strip(); vl = v.lower()
#     for p in PREFIX_STRIP:
#         if vl.startswith(p): v = v[len(p):].strip(" :.-"); vl = v.lower()
#     return v
# def _normalize_address(v: str) -> str:
#     v = _normalize_whitespace(v); replacements = {r'\bSt\b': 'Street', r'\bAve\b': 'Avenue', r'\bRd\b': 'Road', r'\bBlvd\b': 'Boulevard', r'\bDr\b': 'Drive', r'\bLn\b': 'Lane', r'\bCt\b': 'Court', r'\bCir\b': 'Circle'}
#     for p, r in replacements.items(): v = re.sub(p, r, v, flags=re.I)
#     return v
# def _normalize_phone(v: str) -> str:
#     d = ''.join(c for c in v if c.isdigit())
#     if len(d) == 10: return f"({d[:3]}) {d[3:6]}-{d[6:]}"
#     elif len(d) == 11 and d[0] == '1': return f"({d[1:4]}) {d[4:7]}-{d[7:]}"
#     return v
# def _is_phone_number(v: str) -> bool: d = ''.join(c for c in v if c.isdigit()); return len(d) == 10 or (len(d) == 11 and d.startswith('1')) or len(d) == 7 or bool(PHONE_RE.search(v))
# def _is_document_reference(v: str) -> bool: v = v.lower().strip(); return bool(re.match(r'^\d+_\d+_\d+$', v)) or bool(re.match(r'^page\s*\d+', v, re.I)) or ('_' in v and sum(c.isdigit() for c in v) > len(v) * 0.6)
# def _is_mortgage_company_address(v: str) -> bool: v = v.lower(); return any(re.search(p, v, re.I) for p in MORTGAGE_PO_BOX_PATTERNS) or (('troy' in v and 'mi' in v and 'box' in v) or '48007' in v)

# def _is_section_header_value(v: str) -> bool:
#     if not v: return False
#     v_lower = v.lower().strip()
#     if v_lower in SECTION_TITLES: return True
#     for t in SECTION_TITLES:
#         if v_lower.startswith(t) or t in v_lower: return True
#     if v_lower.endswith(":") and len(v_lower.split()) <= 5: return True
#     if v.isupper() and len(v.split()) >= 3:
#         words = v.split()
#         if any(i in v_lower for i in {'insurance', 'ins', 'company', 'co', 'corporation', 'corp', 'exchange', 'mutual', 'group', 'inc', 'llc', 'ltd'}): return False
#         header_words = {'PAGE', 'SECTION', 'COVERAGE', 'DECLARATIONS', 'NOTICE', 'INFORMATION', 'SUMMARY', 'DETAILS', 'SCHEDULE', 'ENDORSEMENT', 'CONDITIONS', 'PROVISIONS', 'LIMITS', 'POLICY', 'PREMIUM', 'TOTAL', 'SUBTOTAL', 'AMOUNT', 'DATE', 'NUMBER', 'TYPE'}
#         if any(w.upper() in header_words for w in words): return True
#         if len(words) <= 4: return False
#         if not any(c.isdigit() for c in v): return True
#     return False

# def get_missing_field_reason(field_name: str, raw_text: str) -> str:
#     hints = FIELD_LABEL_HINTS.get(field_name, [field_name.replace("_", " ")])
#     if any(h in raw_text for h in hints): return "Field value not available in the document"
#     return "Field label not found in document"

# def attach_missing_reasons(validated_fields: Dict, required_fields: List[str], raw_text: str) -> Dict:
#     if not required_fields: return validated_fields
#     for field in required_fields:
#         if field not in validated_fields:
#             validated_fields[field] = {"reason": get_missing_field_reason(field, raw_text)}
#     return validated_fields

# # ============================================================
# # VALIDATORS
# # ============================================================
# def validate_carrier(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*', '', value, flags=re.I).strip())
#     if _is_section_header_value(v) or v.lower() in JUNK_VALUES or len(v) < 5 or len(v) > 60: return False, v, 0.0
#     if re.match(r'(?i)^(the |this |in |we |you |if |any |all |for |it )', v) and not re.match(r'(?i)^the\s+\w+\s+(insurance|indemnity|casualty|mutual)', v): return False, v, 0.0
#     v_clean = v.replace('*', '').replace('/', '').strip(); vl_clean = v_clean.lower()
#     if any(b in vl_clean for b in BAD_CARRIER_PATTERNS) or any(w in vl_clean for w in ('agency', 'agent', 'services', 'producer')): return False, v, 0.0
#     has_ins = ('insurance' in vl_clean or ' ins ' in vl_clean or vl_clean.endswith(' ins') or ' ins.' in vl_clean or 'indemnity' in vl_clean or 'casualty' in vl_clean or 'assurance' in vl_clean or 'trust' in vl_clean or ('fire' in vl_clean and any(w in vl_clean for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual'))))
#     if not has_ins: return False, v, 0.0
#     if not any(w in vl_clean for w in ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')) and len(v_clean.split()) < 2: return False, v, 0.0
#     return True, v_clean.upper(), 0.95

# def validate_policy_number(value: str) -> Tuple[bool, str, float]:
#     v = re.sub(r'^[.\s:;,]+', '', value.strip()).strip()
#     if _is_section_header_value(v) or _is_document_reference(v) or DATE_RE.search(v) or '$' in v: return False, v, 0.0
#     if re.search(r'(date|time|page|due|liability|coverage|endorsement|premium|deductible|dwelling|personal|medical)', v, re.I): return False, v, 0.0
#     if (re.search(r'\.\d{2,}', v) and not re.search(r'^[A-Z]', v)) or re.match(r'^[A-Z]{2}\d{5,}$', v): return False, v, 0.0
#     if re.search(r'\d{5}_\d+', v) or len(''.join(c for c in v if c.isdigit())) > 18 or re.fullmatch(r"\d{3}[-.\s]?\d{4}", v): return False, v, 0.0
#     v_clean = v.replace(" ", "").replace("-", "")
#     if len(v_clean) < 6 or ZIP_RE.fullmatch(v) or sum(c.isdigit() for c in v) < 5 or not (6 <= len(v_clean) <= 30): return False, v, 0.0
#     if v_clean.isdigit() and len(v_clean) < 6: return False, v, 0.0
#     if ':' in v:
#         parts = v.split(':', 1)
#         if 'policy' in parts[0].lower() and 'number' in parts[0].lower(): v = parts[1].strip()
#     return True, v, 0.95

# def validate_loan_number(value: str) -> Tuple[bool, str, float]:
#     v = value.strip()
#     if _is_section_header_value(v): return False, v, 0.0
#     if re.match(r'^n/?a$', v, re.I): return True, "N/A", 0.90
#     if v.lower() in JUNK_VALUES or _is_document_reference(v) or DATE_RE.search(v): return False, v, 0.0
#     digits = ''.join(c for c in v if c.isdigit())
#     if not (7 <= len(digits) <= 12) or len(digits) >= 13 or re.match(r'^\d{5}_\d+', v) or '000000' in digits: return False, v, 0.0
#     if len(digits) > 0 and digits.count('0') > len(digits) * 0.6: return False, v, 0.0
#     # Reject barcode-style numbers: long all-digit strings that are likely
#     # page footers (e.g., "044091120000442", "1965565232" from print barcodes).
#     # Heuristic: 13+ digit pure numbers starting with "0" are typically barcodes.
#     # NOTE: 10-digit loan numbers starting with "0" are legitimate (e.g., "0400004466")
#     if len(digits) >= 13 and digits.startswith('0'): return False, v, 0.0
#     return True, digits, 0.95

# def validate_name(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))
#     if not v or len(v) < 2: return False, v, 0.0
#     # CRITICAL: Normalize "LASTNAME,FIRSTNAME" → "LASTNAME, FIRSTNAME"
#     # OCR often produces names without space after comma
#     v = re.sub(r'([A-Za-z]),([A-Za-z])', r'\1, \2', v)
#     # Also normalize "LASTNAME.FIRSTNAME" → "LASTNAME, FIRSTNAME"
#     if re.match(r'^[A-Za-z]+\.[A-Za-z]+$', v):
#         v = v.replace('.', ', ')
#     words = v.split()
#     if len(words) >= 3 and len(words[0]) == 1 and words[0].isalpha() and len(words[1]) >= 2: v = " ".join(words[1:])
#     if _is_section_header_value(v) or v.count(":") > 0: return False, v, 0.0
#     vl = v.lower()
#     if any(s in vl for s in MARKETING_SLOGANS) or any(p in vl for p in PRODUCT_NAMES) or any(c in vl for c in BAD_INSURED_COMPANY_NAMES): return False, v, 0.0
#     CARRIER_INDICATORS = {"aegis", "allstate", "state farm", "geico", "progressive", "travelers", "liberty mutual", "farmers", "citizens", "universal", "federated", "nationwide", "american family", "usaa", "auto-owners", "erie", "encompass", "safeco", "hanover", "hartford", "insurance company", "insurance co", "insurance exchange", "assurance company", "property insurance", "casualty insurance"}
#     if any(i in vl for i in CARRIER_INDICATORS):
#         if len(words) <= 2 or words[0] in CARRIER_INDICATORS or words[-1] in CARRIER_INDICATORS: return False, v, 0.0
#     if any(p in vl for p in BAD_NAME_PHRASES) or re.search(r'[$%*#@!]', v) or _is_document_reference(v) or _is_phone_number(v): return False, v, 0.0
#     bad_starts = ("policy", "coverage", "premium", "billing", "copy", "page", "section", "office", "message", "declarations", "effective", "expiration", "total", "subtotal", "the ", "this ", "our ", "your ", "and ", "or ", "for ")
#     if any(vl.startswith(w) for w in bad_starts): return False, v, 0.0
#     bad_ends = (" copy", " page", " info", " information", " type", " period", " date", " number", " account")
#     if any(vl.endswith(w) for w in bad_ends): return False, v, 0.0
#     has_entity = any(w in vl for w in ["llc", "inc", "corp", "company", "trust", "ltd", "dba"])
#     if any(c.isdigit() for c in v) and not has_entity: return False, v, 0.0
#     words = [w for w in v.split() if w]; limit = 12 if has_entity else 8
#     if not (2 <= len(words) <= limit): return False, v, 0.0
#     if sum(1 for w in words if w and (w[0].isupper() or w.isupper())) < 1: return False, v, 0.0
#     return True, v, 0.95

# def validate_mortgage_company(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))
#     if not v or len(v) < 3: return False, v, 0.0
#     vl = v.lower()
#     noise = ("copy named insured", "boss payee", "payee mortgagee listed", "page ", "section ", "coverage ", "premium ", "deductible", "declarations", "notification", "notice of")
#     if any(n in vl for n in noise): return False, v, 0.0
#     if not (1 <= len(v.split()) <= 12) or re.search(r'[$%*#@!]', v) or _is_phone_number(v): return False, v, 0.0
#     if not any(c.isupper() for c in v): return False, v, 0.0
#     return True, v, 0.95

# def validate_address(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))
#     if _is_section_header_value(v) or v.lower() in JUNK_VALUES or not v or len(v) < 5 or v.endswith(":"): return False, v, 0.0
#     vl = v.lower()
#     bad_patterns = ["policy period", "beginning", "through", "standard time", "coverage", "summary", "declarations", "effective date", "office use", "message", "mortgagee", "endorsement", "premium", "deductible", "page ", " of ", "building type", "construction", "roof", "single family", "owner occupied", "ph 87", "_8s$", "$$", "##", "exclusion", "poisoning", "liability", "inflation", "protection", "provisions", "amendment", "special form", "fungi", "ordinance", "personal property", "loss payee"]
#     if any(k in vl for k in bad_patterns) or re.search(r'\b\d{2}/\d{2}\b', v) and not re.search(r'\b\d{2}/\d{2}/\d{2,4}\b', v): return False, v, 0.0
#     if _is_document_reference(v) or _is_mortgage_company_address(v): return False, v, 0.0
#     if PO_BOX_RE.search(v):
#         if len(v.split()) <= 4 and not re.search(r'\b[A-Z]{2}\s*\d{5}', v): return False, v, 0.0
#         return True, _normalize_address(v), 0.90
#     if re.search(r'\d+\s+.+?\b(' + '|'.join(STREET_TYPES) + r')\b', v, re.I): return True, _normalize_address(v), 0.95
#     if re.search(r'\b[A-Z]{2}\s*\d{5}(-\d{4})?\b', v): return True, _normalize_address(v), 0.92
#     if re.match(r'^\d+\s+\w', v) and len(v.split()) >= 3: return True, _normalize_address(v), 0.88
#     if bool(re.search(r'\d+', v)) and len(v.split()) >= 4: return True, _normalize_address(v), 0.80
#     return False, v, 0.0

# def validate_date(value: str) -> Tuple[bool, str, float]:
#     v = _normalize_whitespace(_strip_prefixes(value))
#     if _is_section_header_value(v): return False, v, 0.0
#     m = re.match(r'^([A-Z]{3})\s+(\d{1,2}),?\s+(\d{4})$', v)
#     if m: v = f"{m.group(1).capitalize()} {m.group(2)} {m.group(3)}"
#     formats = ["%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"]
#     for fmt in formats:
#         try:
#             if 1990 <= datetime.strptime(v, fmt).year <= 2050: return True, v, 0.95
#         except: continue
#     m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', v) or re.search(r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', v)
#     if m: return True, m.group(1), 0.90
#     return False, v, 0.0

# def validate_money(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value): return False, value, 0.0
#     try:
#         amt = float(value.replace('$', '').replace(',', '').strip())
#         if 1 <= amt <= 10_000_000: return True, f"${amt:,.2f}".replace('.00', ''), 0.92
#     except: pass
#     return False, value, 0.0

# def validate_phone(value: str) -> Tuple[bool, str, float]:
#     if _is_section_header_value(value): return False, value, 0.0
#     d = ''.join(c for c in value if c.isdigit())
#     if len(d) == 10 or (len(d) == 11 and d[0] == '1'): return True, _normalize_phone(value), 0.95
#     return False, value, 0.0

# def _cross_validate(val: Dict) -> Dict:
#     if "mailing_address" in val and "property_address" in val:
#         if val["mailing_address"]["value"].lower().replace(',', '').replace('.', '') == val["property_address"]["value"].lower().replace(',', '').replace('.', ''):
#             val["mailing_address"]["confidence"] = min(1.0, val["mailing_address"]["confidence"] * 1.1)
#             val["property_address"]["confidence"] = min(1.0, val["property_address"]["confidence"] * 1.1)
#             val["mailing_address"]["note"] = "Same as property address"
#     if "effective_date" in val and "expiration_date" in val:
#         try:
#             eff = val["effective_date"]["value"]; exp = val["expiration_date"]["value"]
#             for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]:
#                 try:
#                     if datetime.strptime(eff, fmt) < datetime.strptime(exp, fmt):
#                         val["effective_date"]["confidence"] = min(1.0, val["effective_date"]["confidence"] * 1.05)
#                         val["expiration_date"]["confidence"] = min(1.0, val["expiration_date"]["confidence"] * 1.05)
#                     break
#                 except: continue
#         except: pass
#     return val

# # ============================================================
# # MAIN ENTRY POINT
# # ============================================================
# def validate_and_arbitrate(merged_fields: Dict, ocr_confidence: float, stage_breakdown: Dict, doc_type: str = "UNK", policy_type: str = "UNK", lines: List[str] = []) -> Tuple[Dict, float]:
#     validated = {}; scores = []
#     validators = {
#         "carrier_name": validate_carrier, "policy_number": validate_policy_number, "loan_number": validate_loan_number,
#         "insured_name": validate_name, "agent_name": validate_name, "mortgage_company": validate_mortgage_company,
#         "property_address": validate_address, "mailing_address": validate_address, "effective_date": validate_date,
#         "expiration_date": validate_date, "cancellation_date": validate_date, "total_premium": validate_money,
#         "balance_due": validate_money, "issue_date": validate_date, "deductible": validate_money, "agent_phone": validate_phone
#     }
    
#     for field, data in merged_fields.items():
#         if not isinstance(data, dict): continue
#         value = data.get("value"); confidence = data.get("confidence", 0.0); source = data.get("source", "")
#         floor = 0.40 if source == "stage2_5_gliner" else CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
#         if confidence < floor or not value: continue
#         if field in validators:
#             ok, norm_value, score = validators[field](value)
#             if not ok: continue
#             data["value"] = norm_value; data["validation_score"] = score; scores.append(score)
#         else: scores.append(0.80)
#         validated[field] = data

#     validated = _cross_validate(validated)
    
#     # Defaults and Filtering
#     default_fields = list(validators.keys()) + ["remit_info", "third_party_removed", "third_party_cancellation_date", "cancellation_reason", "cancellation_effective_date"]
#     allowed = ALLOWED_FIELDS_BY_DOC_POLICY.get((doc_type, policy_type), default_fields)
#     validated = {f: d for f, d in validated.items() if f in allowed}
    
#     # Missing Reasons
#     raw_text = " ".join(lines).lower() if lines else ""
#     validated = attach_missing_reasons(validated, allowed, raw_text)

#     final_conf = round(sum(scores)/len(scores)*0.6 + ocr_confidence*0.4, 3) if scores else round(ocr_confidence*0.4, 3)
#     return validated, final_conf

# def validate_output(structured: Dict, confidence: float):
#     return validate_and_arbitrate(structured, confidence, {"stage1": structured})

import re
from datetime import datetime
from typing import Dict, Tuple, Set, List, Optional

# ============================================================
# CONFIGURATION
# ============================================================
CONFIDENCE_FLOORS = {
    "carrier_name": 0.80, "policy_number": 0.80, "loan_number": 0.80, "insured_name": 0.75,
    "property_address": 0.75, "mailing_address": 0.70, "mortgage_company": 0.75, "total_premium": 0.70,
    "deductible": 0.70, "effective_date": 0.75, "expiration_date": 0.75, "agent_phone": 0.75, "agent_name": 0.70
}
DEFAULT_FLOOR = 0.65

# Field Groups
_INV_FIELDS = ["carrier_name", "insured_name", "policy_number", "balance_due", "issue_date", "remit_info", "effective_date", "expiration_date", "property_address", "loan_number", "mortgage_company", "total_premium"]
_CAN_FIELDS = ["carrier_name", "policy_number", "insured_name", "effective_date", "expiration_date", "cancellation_date", "cancellation_reason", "property_address", "mortgage_company", "loan_number", "cancellation_effective_date"]
_RNW_FIELDS = ["carrier_name", "policy_number", "insured_name", "effective_date", "expiration_date", "property_address", "mailing_address", "mortgage_company", "loan_number", "total_premium"]
_DOI_FIELDS = ["policy_number", "mortgage_company", "loan_number", "carrier_name", "insured_name", "property_address", "third_party_removed", "third_party_cancellation_date"]

# Allowed Fields Map
ALLOWED_FIELDS_BY_DOC_POLICY = {}
for pt in ["HAZ", "HO", "HO3", "HO6", "FIR", "FLD", "WND", "DP3", "AUTO", "LL", "UO", "ERQ", "UNK", "BREQ", "NPAY", "NRNW", "UNWR", "CEL"]:
    ALLOWED_FIELDS_BY_DOC_POLICY[("INV", pt)] = _INV_FIELDS
for pt in ["HO", "HO3", "HO6", "HAZ", "FIR", "FLD", "WND", "DP3", "AUTO", "LL", "UO", "ERQ", "UNK", "NRNW", "UNWR", "CEL", "BREQ", "NPAY", "OTH"]:
    ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("CAN", pt), _CAN_FIELDS)
    ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("RNW", pt), _RNW_FIELDS)
    ALLOWED_FIELDS_BY_DOC_POLICY.setdefault(("DOI", pt), _DOI_FIELDS)

# Smart Hints for Missing Logic
FIELD_LABEL_HINTS = {
    "policy_number": ["policy number", "policy #", "policy no", "pol num", "policy id"],
    "loan_number": ["loan number", "loan #", "mortgage number", "loan no", "account number"],
    "insured_name": ["insured", "named insured", "policyholder", "customer name"],
    "carrier_name": ["insurance company", "carrier", "insurer", "company name", "underwriter"],
    "property_address": ["property address", "location", "risk address", "insured location", "premises"],
    "mailing_address": ["mailing address", "mail to", "billing address"],
    "effective_date": ["effective date", "policy period", "period begins", "eff date", "from"],
    "expiration_date": ["expiration date", "period ends", "valid until", "exp date", "to"],
    "total_premium": ["total premium", "premium", "policy total", "annual premium"],
    "balance_due": ["balance due", "amount due", "pay this amount", "total due", "min due"],
    "mortgage_company": ["mortgagee", "mortgage company", "lender", "lienholder", "interested party"],
    "cancellation_date": ["cancellation date", "cancel date", "effective date of cancellation"],
    "cancellation_reason": ["reason", "reason for cancellation", "reason for non-renewal"],
    "deductible": ["deductible", "all perils", "wind/hail"],
}

# Block Lists & Regex
SECTION_TITLES = {"summary", "home protection", "coverage", "coverages", "limits", "policy mortgage declarations summary", "declarations", "declarations summary", "mortgage/other interested parties", "applicable deductible(s)", "premiums", "forms and endorsements", "policy period", "policyholder since", "billing information", "payment plan", "discount information", "for your information", "important notice", "thank you", "office use space", "message(s)", "mortgagee(s)", "endorsements", "schedule", "notice", "rating information", "additional coverages", "discounts"}
JUNK_VALUES = {"type", "interest", "policy", "coverage", "summary", "n/a", "none", "see attached", "continued", "page", "na", "tbd", "pending", "unknown", "included", "see policy"}
MARKETING_SLOGANS = {"you're in good hands", "you're in good hands.", "youre in good hands", "on your side", "like a good neighbor", "we're all in this together", "nationwide is on your side", "for all that matters", "the promise", "keep the promise"}
BAD_NAME_PHRASES = {"policy payment", "quickly & easily", "quickly and easily", "online", "pocket expenses", "out of pocket", "out-of-pocket", "and policy information", "policy information", "page 1 of", "page 2 of", "page 3 of", "mortgagee copy", "declarations page", "your policy", "our policy", "this policy", "policy conditions", "policy type", "policy period", "coverage detail", "coverage info", "premium info", "building type", "single family", "construction type", "roof-wall connection", "roof connection", "roof deck", "additional insured", "first named insured", "named insured:", "location id", "location of", "described location", "effective date", "expiration date", "endorsement", "deductible", "important notice", "special provisions"}
PRODUCT_NAMES = {"homesaver polcy", "homesaver policy", "homeowners policy", "dwelling policy", "mobilehome policy", "mobilehomeowners", "special form policy", "wind only policy", "condominium policy", "condominium owners", "rental unit owners", "ultrapack plus", "encompassone", "encompass one"}
BAD_INSURED_COMPANY_NAMES = {"allied trust", "aegis", "aegis security", "aegis security insurance", "a egis", "properiy insurance", "property insurance", "insurance corporation", "insurance company", "insurance exchange", "mortgage company", "mortgage corp", "financial inc", "lending llc", "bank na"}
BAD_CARRIER_PATTERNS = {"properiy insurance", "property insurance corporaion", "property insurance corporaiion", "insurance exchange*", "insurance company*", "insurance agency", "insurance services", "insurance center", "everett financial", "broker solutions", "nancy bond insurance", "geico ins agency", "allstate mortgage"}
MORTGAGE_PO_BOX_PATTERNS = [r"p\.?o\.?\s*box\s*\d+.*troy.*mi", r"p\.?o\.?\s*box\s*\d+.*48007", r"p\.?o\.?\s*box\s*\d+.*miami.*fl.*33197", r"p\.?o\.?\s*box\s*\d+.*dallas.*tx.*75266"]
PREFIX_STRIP = ["coverage detail for", "policy effective date is", "effective date is", "your policy effective date is", "your policy effective date:", "location:", "address:", "name:", "insured:", "named insured:", "property:", "mailing:", "first named insured:", "policyholder(s)", "policyholder:"]
PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'); DATE_RE = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'); ZIP_RE = re.compile(r'\b\d{5}(-\d{4})?\b'); PO_BOX_RE = re.compile(r'p\.?o\.?\s*box', re.I)
STREET_TYPES = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd', 'lane', 'ln', 'drive', 'dr', 'court', 'ct', 'circle', 'cir', 'way', 'place', 'pl', 'terrace', 'ter', 'highway', 'hwy', 'parkway', 'pkwy', 'ridge']

# ============================================================
# HELPERS & LOGIC
# ============================================================
def _normalize_whitespace(v: str) -> str: return re.sub(r'\s+', ' ', v).strip()
def _strip_prefixes(v: str) -> str:
    v = v.strip(); vl = v.lower()
    for p in PREFIX_STRIP:
        if vl.startswith(p): v = v[len(p):].strip(" :.-"); vl = v.lower()
    return v
def _normalize_address(v: str) -> str:
    v = _normalize_whitespace(v); replacements = {r'\bSt\b': 'Street', r'\bAve\b': 'Avenue', r'\bRd\b': 'Road', r'\bBlvd\b': 'Boulevard', r'\bDr\b': 'Drive', r'\bLn\b': 'Lane', r'\bCt\b': 'Court', r'\bCir\b': 'Circle'}
    for p, r in replacements.items(): v = re.sub(p, r, v, flags=re.I)
    return v
def _normalize_phone(v: str) -> str:
    d = ''.join(c for c in v if c.isdigit())
    if len(d) == 10: return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    elif len(d) == 11 and d[0] == '1': return f"({d[1:4]}) {d[4:7]}-{d[7:]}"
    return v
def _is_phone_number(v: str) -> bool: d = ''.join(c for c in v if c.isdigit()); return len(d) == 10 or (len(d) == 11 and d.startswith('1')) or len(d) == 7 or bool(PHONE_RE.search(v))
def _is_document_reference(v: str) -> bool: v = v.lower().strip(); return bool(re.match(r'^\d+_\d+_\d+$', v)) or bool(re.match(r'^page\s*\d+', v, re.I)) or ('_' in v and sum(c.isdigit() for c in v) > len(v) * 0.6)
def _is_mortgage_company_address(v: str) -> bool: v = v.lower(); return any(re.search(p, v, re.I) for p in MORTGAGE_PO_BOX_PATTERNS) or (('troy' in v and 'mi' in v and 'box' in v) or '48007' in v)

def _is_section_header_value(v: str) -> bool:
    if not v: return False
    v_lower = v.lower().strip()
    if v_lower in SECTION_TITLES: return True
    for t in SECTION_TITLES:
        if v_lower.startswith(t) or t in v_lower: return True
    if v_lower.endswith(":") and len(v_lower.split()) <= 5: return True
    if v.isupper() and len(v.split()) >= 3:
        words = v.split()
        if any(i in v_lower for i in {'insurance', 'ins', 'company', 'co', 'corporation', 'corp', 'exchange', 'mutual', 'group', 'inc', 'llc', 'ltd'}): return False
        header_words = {'PAGE', 'SECTION', 'COVERAGE', 'DECLARATIONS', 'NOTICE', 'INFORMATION', 'SUMMARY', 'DETAILS', 'SCHEDULE', 'ENDORSEMENT', 'CONDITIONS', 'PROVISIONS', 'LIMITS', 'POLICY', 'PREMIUM', 'TOTAL', 'SUBTOTAL', 'AMOUNT', 'DATE', 'NUMBER', 'TYPE'}
        if any(w.upper() in header_words for w in words): return True
        if len(words) <= 4: return False
        if not any(c.isdigit() for c in v): return True
    return False

def get_missing_field_reason(field_name: str, raw_text: str) -> str:
    hints = FIELD_LABEL_HINTS.get(field_name, [field_name.replace("_", " ")])
    if any(h in raw_text for h in hints): return "Field value not available in the document"
    return "Field label not found in document"

def attach_missing_reasons(validated_fields: Dict, required_fields: List[str], raw_text: str) -> Dict:
    if not required_fields: return validated_fields
    for field in required_fields:
        if field not in validated_fields:
            validated_fields[field] = {"reason": get_missing_field_reason(field, raw_text)}
    return validated_fields

# ============================================================
# VALIDATORS
# ============================================================
def validate_carrier(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*', '', value, flags=re.I).strip())
    # CRITICAL: Accept known carrier brand names that don't contain "insurance"
    KNOWN_CARRIER_BRANDS = {
        "nationwide", "allstate", "state farm", "geico", "progressive",
        "travelers", "liberty mutual", "farmers", "usaa", "erie",
        "safeco", "hartford", "hanover", "encompass", "auto-owners",
        "american family", "citizens", "universal", "federated",
        "chubb", "amica", "kemper", "mercury", "shelter",
    }
    v_lower_check = v.lower().strip().rstrip("'\"")
    if v_lower_check in KNOWN_CARRIER_BRANDS:
        return True, v.strip().rstrip("'\""), 0.95
    # Strip common OCR tail-noise appended after carrier names.
    v = re.sub(
        r'(?i)\s+(?:policy\s+that\s+apply|policy\s+that\s+applies|policy\s+that\s+app|policy\s+that)\b.*$',
        '',
        v,
    ).strip(" ,.;:-")
    if _is_section_header_value(v) or v.lower() in JUNK_VALUES or len(v) < 5 or len(v) > 60: return False, v, 0.0
    if re.match(r'(?i)^(the |this |in |we |you |if |any |all |for |it )', v) and not re.match(r'(?i)^the\s+\w+\s+(insurance|indemnity|casualty|mutual)', v): return False, v, 0.0
    v_clean = v.replace('*', '').replace('/', '').strip(); vl_clean = v_clean.lower()
    if any(b in vl_clean for b in BAD_CARRIER_PATTERNS) or any(w in vl_clean for w in ('agency', 'agent', 'services', 'producer')): return False, v, 0.0
    has_ins = ('insurance' in vl_clean or ' ins ' in vl_clean or vl_clean.endswith(' ins') or ' ins.' in vl_clean or 'indemnity' in vl_clean or 'casualty' in vl_clean or 'assurance' in vl_clean or 'trust' in vl_clean or ('fire' in vl_clean and any(w in vl_clean for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual'))))
    if not has_ins: return False, v, 0.0
    if not any(w in vl_clean for w in ('company', 'co', 'exchange', 'group', 'corporation', 'corp', 'mutual')) and len(v_clean.split()) < 2: return False, v, 0.0
    # CRITICAL: Strip trailing single-char OCR noise (e.g., "ALLSTATE INDEMNITY COMPANYD" → "ALLSTATE INDEMNITY COMPANY")
    v_clean = re.sub(r'\b(COMPANY|CORPORATION|EXCHANGE|GROUP|MUTUAL|INDEMNITY)[A-Z]\b', r'\1', v_clean, flags=re.I)
    return True, v_clean.upper(), 0.95

def validate_policy_number(value: str) -> Tuple[bool, str, float]:
    v = re.sub(r'^[.\s:;,]+', '', value.strip()).strip()
    # Strip trailing OCR-merged label text: "063 078 674 Policy descrip" → "063 078 674"
    v = re.sub(
        r'\s+(?:policy\s*(?:description|descrip|desc|type|period|number|info)?'
        r'|description|descrip)\b.*$',
        '', v, flags=re.I
    ).strip()
    # Strip trailing Title-case label bleed: "063 078 674 Mobilehome" → "063 078 674"
    v = re.sub(r'\s+[A-Z][a-z]\w*(?:\s+[A-Z][a-z]\w*)*\s*$', '', v).strip()
    if _is_section_header_value(v) or _is_document_reference(v) or DATE_RE.search(v) or '$' in v: return False, v, 0.0
    if re.search(r'(date|time|page|due|liability|coverage|endorsement|premium|deductible|dwelling|personal|medical)', v, re.I): return False, v, 0.0
    if (re.search(r'\.\d{2,}', v) and not re.search(r'^[A-Z]', v)) or re.match(r'^[A-Z]{2}\d{5,}$', v): return False, v, 0.0
    if re.search(r'\d{5}_\d+', v) or len(''.join(c for c in v if c.isdigit())) > 18 or re.fullmatch(r"\d{3}[-.\s]?\d{4}", v): return False, v, 0.0
    # Join spaced digit groups: "063 078 674" → "063078674"
    parts_check = v.split()
    if all(p.isdigit() for p in parts_check) and 2 <= len(parts_check) <= 4:
        v = ''.join(parts_check)
    v_clean = v.replace(" ", "").replace("-", "")
    if len(v_clean) < 6 or ZIP_RE.fullmatch(v) or sum(c.isdigit() for c in v) < 5 or not (6 <= len(v_clean) <= 30): return False, v, 0.0
    if v_clean.isdigit() and len(v_clean) < 6: return False, v, 0.0
    if ':' in v:
        parts = v.split(':', 1)
        if 'policy' in parts[0].lower() and 'number' in parts[0].lower(): v = parts[1].strip()
    return True, v, 0.95

def validate_loan_number(value: str) -> Tuple[bool, str, float]:
    v = value.strip()
    if _is_section_header_value(v): return False, v, 0.0
    if re.match(r'^n/?a$', v, re.I): return True, "N/A", 0.90
    if v.lower() in JUNK_VALUES or _is_document_reference(v) or DATE_RE.search(v): return False, v, 0.0
    digits = ''.join(c for c in v if c.isdigit())
    if not (7 <= len(digits) <= 12) or len(digits) >= 13 or re.match(r'^\d{5}_\d+', v) or '000000' in digits: return False, v, 0.0
    if len(digits) > 0 and digits.count('0') > len(digits) * 0.6: return False, v, 0.0
    # Reject barcode-style numbers: long all-digit strings that are likely
    # page footers (e.g., "044091120000442", "1965565232" from print barcodes).
    # Heuristic: 13+ digit pure numbers starting with "0" are typically barcodes.
    # NOTE: 10-digit loan numbers starting with "0" are legitimate (e.g., "0400004466")
    if len(digits) >= 13 and digits.startswith('0'): return False, v, 0.0
    return True, digits, 0.95

def validate_name(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))
    if not v or len(v) < 2: return False, v, 0.0
    # CRITICAL: Normalize "LASTNAME,FIRSTNAME" → "LASTNAME, FIRSTNAME"
    # OCR often produces names without space after comma
    v = re.sub(r'([A-Za-z]),([A-Za-z])', r'\1, \2', v)
    # Also normalize "LASTNAME.FIRSTNAME" → "LASTNAME, FIRSTNAME"
    if re.match(r'^[A-Za-z]+\.[A-Za-z]+$', v):
        v = v.replace('.', ', ')
    words = v.split()
    if len(words) >= 3 and len(words[0]) == 1 and words[0].isalpha() and len(words[1]) >= 2: v = " ".join(words[1:])
    if _is_section_header_value(v) or v.count(":") > 0: return False, v, 0.0
    vl = v.lower()
    if any(s in vl for s in MARKETING_SLOGANS) or any(p in vl for p in PRODUCT_NAMES) or any(c in vl for c in BAD_INSURED_COMPANY_NAMES): return False, v, 0.0
    CARRIER_INDICATORS = {"aegis", "allstate", "state farm", "geico", "progressive", "travelers", "liberty mutual", "farmers", "citizens", "universal", "federated", "nationwide", "american family", "usaa", "auto-owners", "erie", "encompass", "safeco", "hanover", "hartford", "insurance company", "insurance co", "insurance exchange", "assurance company", "property insurance", "casualty insurance"}
    if any(i in vl for i in CARRIER_INDICATORS):
        if len(words) <= 2 or words[0] in CARRIER_INDICATORS or words[-1] in CARRIER_INDICATORS: return False, v, 0.0
    if any(p in vl for p in BAD_NAME_PHRASES) or re.search(r'[$%*#@!]', v) or _is_document_reference(v) or _is_phone_number(v): return False, v, 0.0
    bad_starts = ("policy", "coverage", "premium", "billing", "copy", "page", "section", "office", "message", "declarations", "effective", "expiration", "total", "subtotal", "the ", "this ", "our ", "your ", "and ", "or ", "for ")
    if any(vl.startswith(w) for w in bad_starts): return False, v, 0.0
    bad_ends = (" copy", " page", " info", " information", " type", " period", " date", " number", " account")
    if any(vl.endswith(w) for w in bad_ends): return False, v, 0.0
    has_entity = any(w in vl for w in ["llc", "inc", "corp", "company", "trust", "ltd", "dba"])
    if any(c.isdigit() for c in v) and not has_entity: return False, v, 0.0
    words = [w for w in v.split() if w]; limit = 12 if has_entity else 8
    if not (2 <= len(words) <= limit): return False, v, 0.0
    if sum(1 for w in words if w and (w[0].isupper() or w.isupper())) < 1: return False, v, 0.0
    return True, v, 0.95

def validate_mortgage_company(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))
    if not v or len(v) < 3: return False, v, 0.0
    vl = v.lower()
    noise = ("copy named insured", "boss payee", "payee mortgagee listed", "page ", "section ", "coverage ", "premium ", "deductible", "declarations", "notification", "notice of")
    if any(n in vl for n in noise): return False, v, 0.0
    if not (1 <= len(v.split()) <= 12) or re.search(r'[$%*#@!]', v) or _is_phone_number(v): return False, v, 0.0
    if not any(c.isupper() for c in v): return False, v, 0.0
    return True, v, 0.95

def validate_address(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))
    if _is_section_header_value(v) or v.lower() in JUNK_VALUES or not v or len(v) < 5 or v.endswith(":"): return False, v, 0.0
    vl = v.lower()
    bad_patterns = ["policy period", "beginning", "through", "standard time", "coverage", "summary", "declarations", "effective date", "office use", "message", "mortgagee", "endorsement", "premium", "deductible", "page ", " of ", "building type", "construction", "roof", "single family", "owner occupied", "ph 87", "_8s$", "$$", "##", "exclusion", "poisoning", "liability", "inflation", "protection", "provisions", "amendment", "special form", "fungi", "ordinance", "personal property", "loss payee"]
    if any(k in vl for k in bad_patterns) or re.search(r'\b\d{2}/\d{2}\b', v) and not re.search(r'\b\d{2}/\d{2}/\d{2,4}\b', v): return False, v, 0.0
    if _is_document_reference(v) or _is_mortgage_company_address(v): return False, v, 0.0
    if PO_BOX_RE.search(v):
        if len(v.split()) <= 4 and not re.search(r'\b[A-Z]{2}\s*\d{5}', v): return False, v, 0.0
        return True, _normalize_address(v), 0.90
    if re.search(r'\d+\s+.+?\b(' + '|'.join(STREET_TYPES) + r')\b', v, re.I): return True, _normalize_address(v), 0.95
    if re.search(r'\b[A-Z]{2}\s*\d{5}(-\d{4})?\b', v): return True, _normalize_address(v), 0.92
    if re.match(r'^\d+\s+\w', v) and len(v.split()) >= 3: return True, _normalize_address(v), 0.88
    if bool(re.search(r'\d+', v)) and len(v.split()) >= 4: return True, _normalize_address(v), 0.80
    return False, v, 0.0

def validate_date(value: str) -> Tuple[bool, str, float]:
    v = _normalize_whitespace(_strip_prefixes(value))
    if _is_section_header_value(v): return False, v, 0.0
    # CRITICAL: Normalize "July1,2020" → "July 1, 2020" (OCR missing space)
    v = re.sub(r'([A-Za-z])(\d)', r'\1 \2', v)
    # Also normalize "1,2020" → "1, 2020"
    v = re.sub(r'(\d),(\d{4})', r'\1, \2', v)
    m = re.match(r'^([A-Z]{3})\s+(\d{1,2}),?\s+(\d{4})$', v)
    if m: v = f"{m.group(1).capitalize()} {m.group(2)} {m.group(3)}"
    formats = ["%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"]
    for fmt in formats:
        try:
            if 1990 <= datetime.strptime(v, fmt).year <= 2050: return True, v, 0.95
        except: continue
    m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', v) or re.search(r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', v)
    if m: return True, m.group(1), 0.90
    return False, v, 0.0

def validate_money(value: str) -> Tuple[bool, str, float]:
    if _is_section_header_value(value): return False, value, 0.0
    try:
        amt = float(value.replace('$', '').replace(',', '').strip())
        if 1 <= amt <= 10_000_000: return True, f"${amt:,.2f}".replace('.00', ''), 0.92
    except: pass
    return False, value, 0.0

def validate_phone(value: str) -> Tuple[bool, str, float]:
    if _is_section_header_value(value): return False, value, 0.0
    d = ''.join(c for c in value if c.isdigit())
    if len(d) == 10 or (len(d) == 11 and d[0] == '1'): return True, _normalize_phone(value), 0.95
    return False, value, 0.0

def _cross_validate(val: Dict) -> Dict:
    if "mailing_address" in val and "property_address" in val:
        if val["mailing_address"]["value"].lower().replace(',', '').replace('.', '') == val["property_address"]["value"].lower().replace(',', '').replace('.', ''):
            val["mailing_address"]["confidence"] = min(1.0, val["mailing_address"]["confidence"] * 1.1)
            val["property_address"]["confidence"] = min(1.0, val["property_address"]["confidence"] * 1.1)
            val["mailing_address"]["note"] = "Same as property address"
    if "effective_date" in val and "expiration_date" in val:
        try:
            eff = val["effective_date"]["value"]; exp = val["expiration_date"]["value"]
            for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]:
                try:
                    if datetime.strptime(eff, fmt) < datetime.strptime(exp, fmt):
                        val["effective_date"]["confidence"] = min(1.0, val["effective_date"]["confidence"] * 1.05)
                        val["expiration_date"]["confidence"] = min(1.0, val["expiration_date"]["confidence"] * 1.05)
                    break
                except: continue
        except: pass
    return val


def _salvage_from_lines(
    validated: Dict,
    allowed: List[str],
    lines: List[str],
    validators: Dict,
) -> Dict:
    """
    Last-mile recovery for fields that are commonly present in OCR text
    but missed upstream due noisy layout/label splits.
    """
    if not lines or not allowed:
        return validated

    missing = [f for f in allowed if f not in validated]
    if not missing:
        return validated

    text = "\n".join(lines)
    candidates: Dict[str, str] = {}

    # Carrier: allow abbreviated forms like "INS CO"
    if "carrier_name" in missing:
        for line in lines[:80]:
            ll = line.lower().strip()
            if not ll or len(ll) < 5:
                continue
            if any(x in ll for x in ("agency", "services", "producer", "agent", "mortgagee", "loss payee")):
                continue
            if re.search(r'\b(insurance|ins\.?\s+co|ins\s+co|mutual|casualty|indemnity|fire)\b', ll):
                candidates["carrier_name"] = line.strip()
                break

    # Effective/Expiration from policy period line
    if "effective_date" in missing or "expiration_date" in missing:
        # Pattern A: "Policy Period From: 01/01/2020 To: 01/01/2021"
        m = re.search(
            r'(?is)policy\s+period.*?from[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}).*?to[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            text,
        )
        if m:
            if "effective_date" in missing:
                candidates["effective_date"] = m.group(1)
            if "expiration_date" in missing:
                candidates["expiration_date"] = m.group(2)
        else:
            # Pattern B: split lines:
            # "Policy Period"
            # "From: 01/01/2020 To: 01/01/2021"
            # or plain "01/01/2020 ... 01/01/2021" near that label.
            for i, line in enumerate(lines):
                if "policy period" not in line.lower():
                    continue
                window = " ".join(lines[i:i + 4])
                d = re.findall(r'([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})', window)
                if len(d) >= 2:
                    if "effective_date" in missing:
                        candidates["effective_date"] = d[0]
                    if "expiration_date" in missing:
                        candidates["expiration_date"] = d[1]
                    break

    # Property address from "Location"/"Described Location" blocks
    if "property_address" in missing:
        for i, line in enumerate(lines):
            ll = line.lower().strip()
            if ll in ("location", "described location") or "described location:" in ll:
                chunk = " ".join(lines[i + 1:i + 4]).strip()
                street = re.search(
                    r'(\d{1,6}\s+[^,]+?\b(?:st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|parkway)\b)',
                    chunk,
                    re.I,
                )
                city_state_zip = re.search(r'([A-Za-z .\'-]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)', chunk)
                if street and city_state_zip:
                    candidates["property_address"] = f"{street.group(1)}, {city_state_zip.group(1)}"
                    break
                if street:
                    candidates["property_address"] = street.group(1)
                    break

        if "property_address" not in candidates:
            m = re.search(
                r'(?i)(?:property\s+address|property|location|described\s+location)\s*:\s*(.+)',
                text,
            )
            if m:
                candidates["property_address"] = m.group(1).split("\n")[0].strip()

    # Total premium from totals lines
    if "total_premium" in missing:
        m = re.search(
            r'(?is)total\s+premium(?:\s+(?:this\s+location|all\s+locations))?\s*[:$]?\s*\$?\s*([0-9][0-9,]*\.?[0-9]{0,2})',
            text,
        )
        if m:
            amt = m.group(1).strip().rstrip(".")
            candidates["total_premium"] = f"${amt}"

    for field in missing:
        if field not in candidates or field in validated:
            continue
        validator = validators.get(field)
        raw_value = candidates[field]
        if validator:
            ok, norm_value, score = validator(raw_value)
            if not ok:
                continue
            validated[field] = {
                "value": norm_value,
                "confidence": max(CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR), 0.76),
                "source": "validation_salvage",
                "validation_score": score,
            }
        else:
            validated[field] = {
                "value": raw_value,
                "confidence": 0.76,
                "source": "validation_salvage",
            }

    return validated


def _normalize_carrier_with_context(validated: Dict, lines: List[str]) -> Dict:
    """
    Resolve brand-vs-legal-entity carrier conflicts using document context.
    Example: RNW docs with "Nationwide is on your side" but legal line says
    "ALLIED PROP AND CAS INS CO".
    """
    carrier = validated.get("carrier_name")
    if not carrier or not isinstance(carrier, dict):
        return validated

    val = str(carrier.get("value", "")).strip()
    if not val:
        return validated

    text = " ".join(lines).lower() if lines else ""
    if "nationwide" in text and re.search(r'(?i)\ballied\s+prop(?:erty)?\s+and\s+cas', val):
        carrier["value"] = "NATIONWIDE"
        carrier["source"] = "validation_context_brand"
        carrier["confidence"] = max(carrier.get("confidence", 0.0), 0.96)

    return validated

# ============================================================
# MAIN ENTRY POINT
# ============================================================
def validate_and_arbitrate(merged_fields: Dict, ocr_confidence: float, stage_breakdown: Dict, doc_type: str = "UNK", policy_type: str = "UNK", lines: List[str] = []) -> Tuple[Dict, float]:
    validated = {}; scores = []
    validators = {
        "carrier_name": validate_carrier, "policy_number": validate_policy_number, "loan_number": validate_loan_number,
        "insured_name": validate_name, "agent_name": validate_name, "mortgage_company": validate_mortgage_company,
        "property_address": validate_address, "mailing_address": validate_address, "effective_date": validate_date,
        "expiration_date": validate_date, "cancellation_date": validate_date, "total_premium": validate_money,
        "balance_due": validate_money, "issue_date": validate_date, "deductible": validate_money, "agent_phone": validate_phone
    }
    
    for field, data in merged_fields.items():
        if not isinstance(data, dict): continue
        value = data.get("value"); confidence = data.get("confidence", 0.0); source = data.get("source", "")
        floor = 0.40 if source == "stage2_5_gliner" else CONFIDENCE_FLOORS.get(field, DEFAULT_FLOOR)
        if confidence < floor or not value: continue
        if field in validators:
            ok, norm_value, score = validators[field](value)
            if not ok: continue
            data["value"] = norm_value; data["validation_score"] = score; scores.append(score)
        else: scores.append(0.80)
        validated[field] = data

    validated = _cross_validate(validated)

    # Defaults and Filtering
    default_fields = list(validators.keys()) + ["remit_info", "third_party_removed", "third_party_cancellation_date", "cancellation_reason", "cancellation_effective_date"]
    allowed = ALLOWED_FIELDS_BY_DOC_POLICY.get((doc_type, policy_type), default_fields)

    # Last-mile salvage for still-missing allowed fields
    validated = _salvage_from_lines(validated, allowed, lines, validators)
    validated = _normalize_carrier_with_context(validated, lines)
    validated = {f: d for f, d in validated.items() if f in allowed}
    
    # Missing Reasons
    raw_text = " ".join(lines).lower() if lines else ""
    validated = attach_missing_reasons(validated, allowed, raw_text)

    final_conf = round(sum(scores)/len(scores)*0.6 + ocr_confidence*0.4, 3) if scores else round(ocr_confidence*0.4, 3)
    return validated, final_conf

def validate_output(structured: Dict, confidence: float):
    return validate_and_arbitrate(structured, confidence, {"stage1": structured})