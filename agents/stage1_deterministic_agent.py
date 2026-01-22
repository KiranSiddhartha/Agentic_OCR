# # stage1_deterministic_agent.py
# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
# Authoritative extraction layer with multi-line carrier support
# ENHANCED VERSION with mortgage, loan, and better validation
# """
# import re
# from typing import Dict, List
# from enum import Enum, auto

# # ============================================================
# # ROLES
# # ============================================================

# class Role(Enum):
#     NONE = auto()
#     POLICY_HEADER = auto()
#     INSURED_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()  # NEW

# # ============================================================
# # REGEX PATTERNS (ENHANCED)
# # ============================================================

# POLICY_RE = re.compile(r'\b[A-Z0-9]{2}[A-Z0-9\-]{5,28}\b')  # More strict
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# LOAN_RE = re.compile(r"\b\d{8,15}\b")
# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')  # NEW

# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge"
#     r")\b",
#     re.I,
# )

# # ============================================================
# # BLOCKLISTS
# # ============================================================

# BAD_NAME_PHRASES = {
#     "our duties", "policy conditions", "building owner", "coverage",
#     "mortgagee", "loss payment", "appraisal", "endorsement",
#     "conditions", "deductible", "liability", "policy type",
# }
# BAD_NAME_PHRASES.update({
#     "property protection",
#     "coverage",
#     "form number",
#     "endorsement",
#     "policy conditions",
#     "deductible",
# })

# # ============================================================
# # HELPER FUNCTIONS (ENHANCED)
# # ============================================================

# def _clean(v: str) -> str:
#     return re.sub(r"\s+", " ", v).strip(" ,.;:")

# def _normalize_name(v: str) -> str:
#     v = v.replace("0", "O")  # OCR fix
#     v = v.strip()
#     if "," in v:
#         parts = [p.strip() for p in v.split(",") if p.strip()]
#         if len(parts) == 2:
#             return f"{parts[1]} {parts[0]}"
#     return v

# def _is_phone_number(v: str) -> bool:
#     """Check if value is a phone number - CRITICAL NEW FUNCTION"""
#     digits_only = ''.join(c for c in v if c.isdigit())
    
#     # Exactly 10 digits = phone number
#     if len(digits_only) == 10:
#         return True
    
#     # Exactly 7 digits = phone number (last 7)
#     if len(digits_only) == 7:
#         return True
    
#     # Has phone formatting
#     if PHONE_RE.search(v):
#         return True
    
#     return False

# def _looks_like_name(text: str) -> bool:
#     if not text:
#         return False
    
#     t = text.strip()
#     ll = t.lower()
    
#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False
    
#     # Allow entities with digits (LLC, Corp)
#     has_entity = any(w in ll for w in ["llc", "inc", "corp", "company", "trust", "ltd"])
#     if not has_entity and any(c.isdigit() for c in t):
#         return False
    
#     words = t.replace(",", "").split()
#     if has_entity:
#         if not (2 <= len(words) <= 10):
#             return False
#     else:
#         if not (2 <= len(words) <= 8):
#             return False
    
#     caps = sum(1 for w in words if w and w[0].isupper())
#     if caps < 2:
#         return False
    
#     return True

# def _looks_like_policy(v: str) -> bool:
#     """Enhanced policy number validation - COMPLETELY REWRITTEN"""
#     v_clean = v.replace(" ", "").replace("-", "")
    
#     # CRITICAL: BLOCK phone numbers FIRST
#     if _is_phone_number(v):
#         return False
    
#     # BLOCK dates
#     if DATE_RE.search(v):
#         return False
    
#     # BLOCK pure year references
#     if v_clean.isdigit() and len(v_clean) == 4 and v_clean.startswith(('19', '20')):
#         return False
    
#     # BLOCK ZIP codes
#     if v_clean.isdigit() and len(v_clean) == 5:
#         return False
    
#     # Allow pure numeric if 8-12 digits (common format)
#     if v_clean.isdigit() and 8 <= len(v_clean) <= 12:
#         return True
    
#     # Must have mix of letters and numbers
#     has_letters = any(c.isalpha() for c in v_clean)
#     has_digits = any(c.isdigit() for c in v_clean)
    
#     if not (has_letters and has_digits):
#         return False
    
#     # Length check
#     if not (7 <= len(v_clean) <= 30):
#         return False
    
#     # Must have substantial digits (at least 5)
#     digit_count = sum(c.isdigit() for c in v_clean)
#     if digit_count < 5:
#         return False
    
#     return bool(POLICY_RE.fullmatch(v_clean))

# def _looks_like_carrier_part(line: str) -> bool:
#     """Check if line could be part of carrier name"""
#     t = line.upper().replace("*", "").strip()
    
#     if not t or len(t) < 4:
#         return False
    
#     # Block agencies FIRST
#     if any(w in t for w in ("AGENCY", "AGENT", "CENTER", "LLC", "INC", "SERVICES")):
#         return False
    
#     # Direct insurance keywords
#     if any(w in t for w in ("INSURANCE", "EXCHANGE", "COMPANY", "CORPORATION", "GROUP", "MUTUAL")):
#         return True
    
#     # All-caps word (like ADIRONDACK)
#     if t.isupper() and not any(c.isdigit() for c in t):
#         noise = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", "NOTICE", "LOCATED", "DESCRIPTION"}
#         if not any(w in t for w in noise):
#             words = t.split()
#             if 1 <= len(words) <= 3 and all(len(w) >= 3 for w in words):
#                 return True
    
#     return False

# def _looks_like_carrier(line: str) -> bool:
#     """Check if complete line is a carrier name"""
#     t = line.upper()
    
#     if "INSURANCE" not in t:
#         return False
    
#     if not any(w in t for w in ("COMPANY", "EXCHANGE", "GROUP", "CORPORATION", "MUTUAL")):
#         return False
    
#     # Block agencies
#     if any(w in t for w in ("AGENCY", "AGENT", "CENTER", "LLC", "INC")):
#         return False
    
#     return 2 <= len(t.split()) <= 10

# def _is_skippable_line_for_carrier(line: str) -> bool:
#     """Lines to skip during carrier accumulation (PO Box, addresses)"""
#     ll = line.lower().strip()
    
#     if "po box" in ll or "p.o. box" in ll:
#         return True
    
#     # City/state/zip pattern
#     if re.match(r"^[a-zA-Z\s,]+,?\s*[A-Z]{2}\s*\d{5}(-\d{4})?$", line.strip()):
#         return True
    
#     return False

# def _looks_like_address(line: str) -> bool:
#     if "po box" in line.lower():
#         return False
#     return bool(STREET_RE.search(line))

# # ============================================================
# # STATEFUL EXTRACTOR (ENHANCED)
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}
#         self.carrier_parts: List[str] = []

#     def update_role(self, line: str):
#         ll = line.lower().strip()

#         # Policy header
#         if any(k in ll for k in (
#                 "policy number",
#                 "policy no",
#                 "dwelling policy number",
#             )):
#             self.role = Role.POLICY_HEADER
#             self.window = 6
#             return

#         # Insured block
#         if any(k in ll for k in (
#             "insured",
#             "named insured",
#             "policyholder/named insured",
#             "insured mailing",
#             "insured mailing name",
#             "insured mailing name and address",
#             "policyholder/insured",
#         )):
#             self.role = Role.INSURED_BLOCK
#             self.window = 10
#             return


#         # Property block
#         if any(k in ll for k in (
#             "property address",
#             "property insured",
#             "location of insured property",
#             "description of property",
#             "coverage detail for",
#         )):
#             self.role = Role.PROPERTY_BLOCK
#             self.window = 6
#             return

        
#         # Mortgage block (NEW)
#         if any(k in ll for k in ("mortgagee", "loss payee", "lender", 
#                                  "mortgage company", "other interested parties")):
#             self.role = Role.MORTGAGE_BLOCK
#             self.window = 8
#             return

#     def extract(self, line: str):
#         if not line:
#             return

#         # ALWAYS check for carrier parts (multi-line support)
#         self._capture_carrier_part(line)

#         # Inline extraction (high priority)
#         self._inline(line)

#         # Role-based extraction
#         if self.window > 0:
#             if self.role == Role.POLICY_HEADER:
#                 self._policy(line)
#             elif self.role == Role.INSURED_BLOCK:
#                 self._insured(line)
#             elif self.role == Role.PROPERTY_BLOCK:
#                 self._property(line)
#             elif self.role == Role.MORTGAGE_BLOCK:  # NEW
#                 self._mortgage(line)

#             self.window -= 1
#             if self.window == 0:
#                 self.role = Role.NONE

#     def _capture_carrier_part(self, line: str):
#         """Accumulate carrier name parts across lines"""
#         if "carrier_name" in self.fields:
#             return

#         clean = line.replace("*", "").strip()
        
#         if _looks_like_carrier_part(clean):
#             self.carrier_parts.append(clean)
            
#             # Check if we have complete carrier
#             combined = " ".join(self.carrier_parts)
#             if _looks_like_carrier(combined):
#                 self.fields["carrier_name"] = {
#                     "value": combined.upper(),
#                     "confidence": 0.99,
#                     "source": "stage1_carrier_multiline",
#                 }
#                 self.carrier_parts = []
#         else:
#             # Skip PO Box lines without resetting
#             if _is_skippable_line_for_carrier(clean):
#                 return
#             # Reset if we hit non-carrier, non-skippable line
#             if self.carrier_parts and not _looks_like_carrier_part(clean):
#                 self._finalize_carrier()

#     def _finalize_carrier(self):
#         """Finalize accumulated carrier parts"""
#         if self.carrier_parts and "carrier_name" not in self.fields:
#             combined = " ".join(self.carrier_parts)
#             if "INSURANCE" in combined.upper():
#                 self.fields["carrier_name"] = {
#                     "value": combined.upper(),
#                     "confidence": 0.95,
#                     "source": "stage1_carrier_accumulated",
#                 }
#         self.carrier_parts = []

#     def _inline(self, line: str):
#         """Extract from inline patterns (Label: Value) - ENHANCED"""
#         ll = line.lower()

#         # Policy Underwritten By: ADIRONDACK INSURANCE EXCHANGE
#         if "carrier_name" not in self.fields and "underwritten by" in ll and ":" in line:
#             _, _, v = line.partition(":")
#             v = v.strip()
#             if v and "INSURANCE" in v.upper():
#                 self.fields["carrier_name"] = {
#                     "value": v.upper(),
#                     "confidence": 0.99,
#                     "source": "stage1_carrier_underwritten_by",
#                 }

#         # Policy Number: 2004939477
#         if "policy_number" not in self.fields and any(k in ll for k in ("policy number", "policy no")): 
#             _, _, v = line.partition(":")
#             # v = _clean(v).replace(" ", "")
#             v = _clean(v)
#             v = re.sub(r"\s+(\d)$", r"-\1", v)  # Fix split suffix
#             v = v.replace(" ", "")

#             if _looks_like_policy(v):
#                 self.fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.99,
#                     "source": "stage1_policy_inline",
#                 }

#         # Named insured: Heather A Babcock
#         if "insured_name" not in self.fields and ":" in line:
#             label, _, value = line.partition(":")
#             label_lower = label.lower().strip()
#             if label_lower in ("insured", "named insured"):
#                 v = _normalize_name(value)
#                 if _looks_like_name(v):
#                     self.fields["insured_name"] = {
#                         "value": v,
#                         "confidence": 0.99,
#                         "source": "stage1_insured_inline",
#                     }

#         # Loan Number (CRITICAL - NEW)
#         if "loan_number" not in self.fields:
#             # Pattern 1: "Loan Number: 12345678"
#             if "loan" in ll and "number" in ll and ":" in line:
#                 _, _, v = line.partition(":")
#                 v_clean = ''.join(c for c in v if c.isdigit())
#                 if LOAN_RE.fullmatch(v_clean):
#                     self.fields["loan_number"] = {
#                         "value": v_clean,
#                         "confidence": 0.96,
#                         "source": "stage1_loan_inline",
#                     }
            
#             # Pattern 2: Scan for 8-15 digit sequences in loan context
#             # elif "loan" in ll:
#             #     for token in line.split():
#             #         digits = ''.join(c for c in token if c.isdigit())
#             #         if LOAN_RE.fullmatch(digits) and not _is_phone_number(token):
#             #             self.fields["loan_number"] = {
#             #                 "value": digits,
#             #                 "confidence": 0.93,
#             #                 "source": "stage1_loan_context",
#             #             }
#             #             break

#     def _policy(self, line: str):
#         if "policy_number" in self.fields:
#             return
        
#         for token in line.split():
#             if _looks_like_policy(token):
#                 self.fields["policy_number"] = {
#                     "value": token,
#                     "confidence": 0.96,
#                     "source": "stage1_policy_block",
#                 }
#                 return

#     def _insured(self, line: str):
#         """Extract insured name from INSURED block"""
#         ll = line.lower().strip()

#         # Skip obvious non-name lines
#         if any(x in ll for x in ("po box", "policy period", "loan number", 
#                                   "policy type", "description", "coverage")):
#             return

#         # Try to extract name
#         if "insured_name" not in self.fields:
#             candidate = _normalize_name(line)
#             if _looks_like_name(candidate):
#                 self.fields["insured_name"] = {
#                     "value": candidate,
#                     "confidence": 0.98,
#                     "source": "stage1_insured_block",
#                 }
#                 return

#         # Also capture property address if found
#         if "property_address" not in self.fields and _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.97,
#                 "source": "stage1_property_from_insured",
#             }

#     def _property(self, line: str):
#         if "property_address" in self.fields:
#             return
        
#         if _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.98,
#                 "source": "stage1_property_block",
#             }
    
#     def _mortgage(self, line: str):
#         """Extract mortgage company and loan number in MORTGAGE block"""
#         ll = line.lower().strip()

#         # Skip junk / structural lines
#         if any(k in ll for k in (
#             "type of interest",
#             "interest:",
#             "mortgagee certificate",
#             "this is not a bill",
#             "policy conditions",
#             "coverage",
#         )):
#             return

#         # =========================
#         # Mortgage Company
#         # =========================
#         if "mortgage_company" not in self.fields:
#             clean = line.strip()

#             # Strip common prefixes
#             for prefix in (
#                 "1.", "2.", "first mortgage:", "second mortgage:",
#                 "mortgagee:", "mortgagee full name:"
#             ):
#                 if clean.lower().startswith(prefix.lower()):
#                     clean = clean[len(prefix):].strip()

#             cl = clean.lower()

#             # HARD BLOCK insurers & noise
#             if any(w in cl for w in (
#                 "insurance", "exchange", "group", "policy", "endorsement",
#                 "isaoa", "atima", "loan number", "p.o. box", "po box"
#             )):
#                 pass
#             elif _looks_like_name(clean):
#                 self.fields["mortgage_company"] = {
#                     "value": clean,
#                     "confidence": 0.92,
#                     "source": "stage1_mortgage_block",
#                 }

#         # =========================
#         # Loan Number (STRICT)
#         # =========================
#         if "loan_number" not in self.fields:
#             for token in line.split():
#                 digits = ''.join(c for c in token if c.isdigit())
#                 if (
#                     LOAN_RE.fullmatch(digits)
#                     and not _is_phone_number(token)
#                     and len(digits) >= 8
#                 ):
#                     self.fields["loan_number"] = {
#                         "value": digits,
#                         "confidence": 0.94,
#                         "source": "stage1_loan_mortgage_block",
#                     }
#                     break


# # ============================================================
# # SAFE SWEEP (Fallback extraction) - ENHANCED
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     """Final pass to catch missed fields"""
#     REQUIRED_FIELDS = {"policy_number", "insured_name", "property_address"}

#     if REQUIRED_FIELDS.issubset(fields.keys()):
#         return
#     for i, line in enumerate(lines):
#         ll = line.lower().strip()

#         # =========================================================
#         # Carrier name (multi-line)
#         # =========================================================
#         if "carrier_name" not in fields:
#             clean = line.replace("*", "").strip()
#             if _looks_like_carrier_part(clean):
#                 parts = [clean]
#                 for j in range(i + 1, min(i + 6, len(lines))):
#                     next_clean = lines[j].replace("*", "").strip()
#                     if _looks_like_carrier_part(next_clean):
#                         parts.append(next_clean)
#                         combined = " ".join(parts)
#                         if _looks_like_carrier(combined):
#                             fields["carrier_name"] = {
#                                 "value": combined.upper(),
#                                 "confidence": 0.93,
#                                 "source": "stage1_sweep_carrier",
#                             }
#                             break
#                     elif _is_skippable_line_for_carrier(next_clean):
#                         continue
#                     else:
#                         break

#         # =========================================================
#         # Insured name (label → next line)
#         # =========================================================
#         if "insured_name" not in fields:
#             if ll in (
#                 "insured",
#                 "named insured",
#                 "insured name",
#                 "insured mailing",
#                 "insured mailing name",
#                 "insured name and address",
#                 "policyholder/named insured",
#             ):
#                 if i + 1 < len(lines):
#                     v = _normalize_name(lines[i + 1])
#                     if _looks_like_name(v):
#                         fields["insured_name"] = {
#                             "value": v,
#                             "confidence": 0.88,
#                             "source": "stage1_sweep_insured",
#                         }

#         # =========================================================
#         # Policy number
#         # =========================================================
#         if "policy_number" not in fields and "policy number" in ll and ":" in line:
#             _, _, v = line.partition(":")
#             v = v.replace(" ", "").strip()
#             if _looks_like_policy(v):
#                 fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.88,
#                     "source": "stage1_sweep_policy",
#                 }

#         # =========================================================
#         # Property address (triggered block-based)
#         # =========================================================
#         if "property_address" not in fields:
#             if any(k in ll for k in (
#                 "coverage detail for",
#                 "location",
#                 "described location",
#                 "residence premises",
#             )):
#                 for j in range(i + 1, min(i + 4, len(lines))):
#                     if _looks_like_address(lines[j]):
#                         fields["property_address"] = {
#                             "value": lines[j].strip(),
#                             "confidence": 0.83,
#                             "source": "stage1_sweep_property_block",
#                         }
#                         break

# # ============================================================
# # MAIN ENTRY POINT
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """
#     Main extraction entry point
    
#     Args:
#         lines: List of text lines from OCR
#         layout_elements: Optional layout information (unused)
    
#     Returns:
#         Dictionary of extracted fields with confidence scores
#     """
#     if not lines:
#         return {}
    
#     extractor = StatefulExtractor()

#     # Process each line
#     for raw in lines:
#         line = raw.strip()
#         if line:
#             extractor.update_role(line)
#             extractor.extract(line)

#     # Finalize any accumulated carrier parts
#     extractor._finalize_carrier()
    
#     # Final sweep for missed fields
#     _safe_sweep(lines, extractor.fields)
    
#     return extractor.fields

# # Backward compatibility
# def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     """Legacy function name for backward compatibility"""
#     return extract_fields(lines, layout_elements)

#2nd
# # stage1_deterministic_agent.py
# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
# Authoritative extraction layer with multi-line carrier support
# ENHANCED VERSION with mortgage, loan, and better validation
# """
# import re
# from typing import Dict, List
# from enum import Enum, auto

# # ============================================================
# # ROLES
# # ============================================================

# class Role(Enum):
#     NONE = auto()
#     POLICY_HEADER = auto()
#     INSURED_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()

# # ============================================================
# # REGEX PATTERNS
# # ============================================================

# POLICY_RE = re.compile(r'\b[A-Z0-9]{2}[A-Z0-9\-]{5,28}\b')
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# LOAN_RE = re.compile(r"\b\d{8,15}\b")
# PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge"
#     r")\b",
#     re.I,
# )

# # ============================================================
# # BLOCKLISTS
# # ============================================================

# BAD_NAME_PHRASES = {
#     "our duties", "policy conditions", "building owner", "coverage",
#     "mortgagee", "loss payment", "appraisal", "endorsement",
#     "conditions", "deductible", "liability", "policy type",
#     "property protection", "form number",
# }

# BAD_MORTGAGE_PRODUCTS = {
#     "ultrapack", "package", "homeowners", "dwelling", "policy"
# }

# # ============================================================
# # HELPERS
# # ============================================================

# def _clean(v: str) -> str:
#     return re.sub(r"\s+", " ", v).strip(" ,.;:")

# def _normalize_name(v: str) -> str:
#     v = v.replace("0", "O").strip()
#     if "," in v:
#         parts = [p.strip() for p in v.split(",") if p.strip()]
#         if len(parts) == 2:
#             return f"{parts[1]} {parts[0]}"
#     return v

# def _is_phone_number(v: str) -> bool:
#     digits = ''.join(c for c in v if c.isdigit())
#     return len(digits) in (7, 10) or bool(PHONE_RE.search(v))

# def _looks_like_name(text: str) -> bool:
#     if not text:
#         return False
#     t = text.strip()
#     ll = t.lower()
#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False
#     has_entity = any(w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
#     if not has_entity and any(c.isdigit() for c in t):
#         return False
#     words = t.replace(",", "").split()
#     caps = sum(1 for w in words if w and w[0].isupper())
#     return 2 <= len(words) <= 10 and caps >= 2

# def _looks_like_policy(v: str) -> bool:
#     v = v.replace(" ", "").replace("-", "")
#     if _is_phone_number(v):
#         return False
#     if DATE_RE.search(v):
#         return False
#     if v.isdigit() and len(v) in (4, 5):
#         return False
#     if v.isdigit() and 8 <= len(v) <= 12:
#         return True
#     return bool(POLICY_RE.fullmatch(v))

# def _looks_like_carrier_part(line: str) -> bool:
#     t = line.upper().strip("* ").strip()
#     if len(t) < 4:
#         return False
#     if any(w in t for w in ("AGENCY", "AGENT", "CENTER", "LLC", "INC", "SERVICES")):
#         return False
#     return any(w in t for w in ("INSURANCE", "EXCHANGE", "COMPANY", "GROUP", "MUTUAL")) or t.isupper()

# def _looks_like_carrier(line: str) -> bool:
#     t = line.upper()
#     return "INSURANCE" in t and not any(w in t for w in ("AGENCY", "AGENT", "CENTER"))

# def _is_skippable_line_for_carrier(line: str) -> bool:
#     ll = line.lower()
#     return "po box" in ll or bool(re.match(r".+,\s*[A-Z]{2}\s*\d{5}", line))

# def _looks_like_address(line: str) -> bool:
#     return "po box" not in line.lower() and bool(STREET_RE.search(line))

# # ============================================================
# # STATEFUL EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}
#         self.carrier_parts: List[str] = []

#     def update_role(self, line: str):
#         ll = line.lower()
#         if "policy number" in ll:
#             self.role, self.window = Role.POLICY_HEADER, 6
#         elif "insured" in ll:
#             self.role, self.window = Role.INSURED_BLOCK, 10
#         elif "coverage detail for" in ll or "location" in ll:
#             self.role, self.window = Role.PROPERTY_BLOCK, 6
#         elif any(k in ll for k in ("mortgagee", "loss payee", "lender")):
#             self.role, self.window = Role.MORTGAGE_BLOCK, 8

#     def extract(self, line: str):
#         self._capture_carrier_part(line)
#         self._inline(line)
#         if self.window > 0:
#             if self.role == Role.POLICY_HEADER:
#                 self._policy(line)
#             elif self.role == Role.INSURED_BLOCK:
#                 self._insured(line)
#             elif self.role == Role.PROPERTY_BLOCK:
#                 self._property(line)
#             elif self.role == Role.MORTGAGE_BLOCK:
#                 self._mortgage(line)
#             self.window -= 1

#     def _capture_carrier_part(self, line: str):
#         if "carrier_name" in self.fields:
#             return
#         clean = line.strip("* ").strip()
#         if _looks_like_carrier_part(clean):
#             self.carrier_parts.append(clean)
#             combined = " ".join(self.carrier_parts)
#             if _looks_like_carrier(combined):
#                 self.fields["carrier_name"] = {
#                     "value": combined.upper(),
#                     "confidence": 0.99,
#                     "source": "stage1_carrier_multiline",
#                 }
#                 self.carrier_parts.clear()
#         elif self.carrier_parts and not _is_skippable_line_for_carrier(clean):
#             self.carrier_parts.clear()

#     def _inline(self, line: str):
#         ll = line.lower()

#         if "policy number" in ll and ":" in line and "policy_number" not in self.fields:
#             v = _clean(line.split(":", 1)[1])
#             if _looks_like_policy(v):
#                 self.fields["policy_number"] = {"value": v, "confidence": 0.99, "source": "inline"}

#         if "insured" in ll and ":" in line and "insured_name" not in self.fields:
#             v = _normalize_name(line.split(":", 1)[1])
#             if _looks_like_name(v):
#                 self.fields["insured_name"] = {"value": v, "confidence": 0.99, "source": "inline"}

#         if "loan number" in ll and ":" in line and "loan_number" not in self.fields:
#             digits = ''.join(c for c in line if c.isdigit())
#             if LOAN_RE.fullmatch(digits):
#                 self.fields["loan_number"] = {"value": digits, "confidence": 0.96, "source": "inline"}

#     def _policy(self, line: str):
#         for t in line.split():
#             if _looks_like_policy(t):
#                 self.fields.setdefault("policy_number", {
#                     "value": t, "confidence": 0.96, "source": "block"
#                 })

#     def _insured(self, line: str):
#         if "insured_name" not in self.fields:
#             v = _normalize_name(line)
#             if _looks_like_name(v):
#                 self.fields["insured_name"] = {"value": v, "confidence": 0.98, "source": "block"}

#     def _property(self, line: str):
#         if "property_address" not in self.fields and _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.98,
#                 "source": "block",
#             }

#     def _mortgage(self, line: str):
#         cl = line.lower()

#         if any(x in cl for x in BAD_MORTGAGE_PRODUCTS):
#             return

#         if "mortgage_company" not in self.fields and _looks_like_name(line):
#             self.fields["mortgage_company"] = {
#                 "value": line.strip(),
#                 "confidence": 0.92,
#                 "source": "block",
#             }

#         if "loan_number" not in self.fields:
#             for t in line.split():
#                 d = ''.join(c for c in t if c.isdigit())
#                 if LOAN_RE.fullmatch(d) and not _is_phone_number(t):
#                     self.fields["loan_number"] = {
#                         "value": d,
#                         "confidence": 0.94,
#                         "source": "block",
#                     }

# # ============================================================
# # SAFE SWEEP
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     for i, line in enumerate(lines):
#         ll = line.lower()

#         if "insured_name" not in fields and ":" in line and "insured" in ll:
#             v = _normalize_name(line.split(":", 1)[1])
#             if _looks_like_name(v):
#                 fields["insured_name"] = {"value": v, "confidence": 0.88, "source": "sweep"}

#         if "property_address" not in fields and any(k in ll for k in (
#             "coverage detail for", "location", "described location"
#         )):
#             tail = ll.split("for", 1)[-1]
#             if _looks_like_address(tail):
#                 fields["property_address"] = {
#                     "value": tail.strip(),
#                     "confidence": 0.86,
#                     "source": "sweep",
#                 }

# # ============================================================
# # ENTRY POINT
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     extractor = StatefulExtractor()
#     for line in lines:
#         line = line.strip()
#         if line:
#             extractor.update_role(line)
#             extractor.extract(line)
#     _safe_sweep(lines, extractor.fields)
#     return extractor.fields

# def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     return extract_fields(lines, layout_elements)

# #3rd
# # stage1_deterministic_agent.py
# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
# Supports RNW / CAN / INV / DOI / PQ / COI / HO / HO6 / HAZ / FIR / FLD / LL / WIND
# """

# import re
# from typing import Dict, List
# from enum import Enum, auto

# # ============================================================
# # ROLES
# # ============================================================

# class Role(Enum):
#     NONE = auto()
#     POLICY_HEADER = auto()
#     INSURED_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()

# # ============================================================
# # REGEX
# # ============================================================

# POLICY_RE = re.compile(r"\b[A-Z0-9]{2}[A-Z0-9\-]{5,28}\b")
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# LOAN_RE = re.compile(r"\b\d{8,15}\b")
# PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# POLICY_REGEX_VARIANTS = [
#     re.compile(r"\b[A-Z]{1,4}[-\s]?\d{6,12}\b"),
#     re.compile(r"\b[A-Z]{2,6}\s?\d{7,12}[-]?\d?\b"),
#     re.compile(r"\b\d{8,12}\b"),
#     POLICY_RE,
# ]

# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge"
#     r")\b",
#     re.I,
# )

# # ============================================================
# # MASTER KEYWORD LISTS (ALL TEMPLATES)
# # ============================================================

# POLICY_LABELS = {
#     "policy number", "policy no", "policy #", "policy id",
#     "dwelling policy number", "dwelling fire policy number",
#     "homeowners policy number", "amended policy number",
#     "renewal policy number", "previous policy number",
#     "policy declarations",
# }

# INSURED_LABELS = {
#     "insured", "named insured", "insured name",
#     "insured name and address",
#     "insured mailing", "insured mailing name",
#     "insured mailing name and address",
#     "policyholder", "policyholder/insured",
#     "policyholder/named insured",
# }

# PROPERTY_TRIGGERS = {
#     "property address",
#     "property insured",
#     "location of insured property",
#     "coverage detail for",
#     "described location",
#     "location id described location",
#     "residence premises",
#     "located at",
#     "address:",
# }

# MORTGAGE_TRIGGERS = {
#     "mortgagee",
#     "mortgagee full name",
#     "mortgagee mailing name and address",
#     "loss payee",
#     "loss payee, mortgagee or other interest",
#     "other interest",
#     "other interested parties",
#     "lender",
#     "mortgage company",
#     "mortgagee copy",
# }

# LOAN_LABELS = {
#     "loan number", "loan no", "loan #",
#     "mortgage loan number", "account number",
# }

# BAD_NAME_PHRASES = {
#     "our duties", "policy conditions", "coverage", "endorsement",
#     "deductible", "liability", "property protection",
#     "form number", "loss payment", "mortgagee certificate",
#     "policy period", "coverage limits", "forms and endorsements",
# }

# BAD_MORTGAGE_PRODUCTS = {
#     "ultrapack", "package", "homeowners", "dwelling",
#     "special package", "policy", "endorsement", "insurance",
# }

# # ============================================================
# # HELPERS
# # ============================================================

# def _clean(v: str) -> str:
#     return re.sub(r"\s+", " ", v).strip(" ,.;:")

# def _normalize_name(v: str) -> str:
#     v = v.replace("0", "O").strip()
#     if "," in v:
#         p = [x.strip() for x in v.split(",") if x.strip()]
#         if len(p) == 2:
#             return f"{p[1]} {p[0]}"
#     return v

# def _is_phone_number(v: str) -> bool:
#     digits = ''.join(c for c in v if c.isdigit())
#     return len(digits) in (7, 10) or bool(PHONE_RE.search(v))

# def _looks_like_name(text: str) -> bool:
#     if not text:
#         return False
#     ll = text.lower()
#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False
#     if any(c.isdigit() for c in text) and not any(
#         w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd")
#     ):
#         return False
#     words = text.replace(",", "").split()
#     caps = sum(1 for w in words if w and w[0].isupper())
#     return 2 <= len(words) <= 10 and caps >= 2

# def _looks_like_policy(v: str) -> bool:
#     v = v.replace(" ", "").replace("-", "")
#     if _is_phone_number(v) or DATE_RE.search(v):
#         return False
#     if v.isdigit() and len(v) in (4, 5):
#         return False
#     for rx in POLICY_REGEX_VARIANTS:
#         if rx.fullmatch(v):
#             return True
#     return False

# def _looks_like_address(line: str) -> bool:
#     return "po box" not in line.lower() and bool(STREET_RE.search(line))

# # ============================================================
# # STATEFUL EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}

#     def update_role(self, line: str):
#         ll = line.lower()

#         if any(k in ll for k in POLICY_LABELS):
#             self.role, self.window = Role.POLICY_HEADER, 6
#         elif any(k in ll for k in INSURED_LABELS):
#             self.role, self.window = Role.INSURED_BLOCK, 10
#         elif any(k in ll for k in PROPERTY_TRIGGERS):
#             self.role, self.window = Role.PROPERTY_BLOCK, 6
#         elif any(k in ll for k in MORTGAGE_TRIGGERS):
#             self.role, self.window = Role.MORTGAGE_BLOCK, 8

#     def extract(self, line: str):
#         self._inline(line)

#         if self.window > 0:
#             if self.role == Role.POLICY_HEADER:
#                 self._policy(line)
#             elif self.role == Role.INSURED_BLOCK:
#                 self._insured(line)
#             elif self.role == Role.PROPERTY_BLOCK:
#                 self._property(line)
#             elif self.role == Role.MORTGAGE_BLOCK:
#                 self._mortgage(line)

#             self.window -= 1
#             if self.window == 0:
#                 self.role = Role.NONE

#     # --------------------------------------------------------

#     def _inline(self, line: str):
#         ll = line.lower()

#         if "policy_number" not in self.fields and ":" in line and any(k in ll for k in POLICY_LABELS):
#             v = _clean(line.split(":", 1)[1])
#             if _looks_like_policy(v):
#                 self.fields["policy_number"] = {
#                     "value": v, "confidence": 0.99, "source": "inline"
#                 }

#         if "insured_name" not in self.fields and ":" in line:
#             label, _, val = line.partition(":")
#             if label.lower().strip() in INSURED_LABELS:
#                 v = _normalize_name(val)
#                 if _looks_like_name(v):
#                     self.fields["insured_name"] = {
#                         "value": v, "confidence": 0.99, "source": "inline"
#                     }

#         if "loan_number" not in self.fields and any(k in ll for k in LOAN_LABELS):
#             digits = ''.join(c for c in line if c.isdigit())
#             if LOAN_RE.fullmatch(digits) and not _is_phone_number(digits):
#                 self.fields["loan_number"] = {
#                     "value": digits, "confidence": 0.96, "source": "inline"
#                 }

#     # --------------------------------------------------------

#     def _policy(self, line: str):
#         for t in line.split():
#             if _looks_like_policy(t):
#                 self.fields.setdefault(
#                     "policy_number",
#                     {"value": t, "confidence": 0.96, "source": "block"},
#                 )

#     def _insured(self, line: str):
#         if "insured_name" not in self.fields:
#             v = _normalize_name(line)
#             if _looks_like_name(v):
#                 self.fields["insured_name"] = {
#                     "value": v, "confidence": 0.98, "source": "block"
#                 }

#     def _property(self, line: str):
#         if "property_address" not in self.fields and _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.98,
#                 "source": "block",
#             }

#     def _mortgage(self, line: str):
#         ll = line.lower()

#         if any(p in ll for p in BAD_MORTGAGE_PRODUCTS):
#             return

#         if "mortgage_company" not in self.fields and _looks_like_name(line):
#             self.fields["mortgage_company"] = {
#                 "value": line.strip(),
#                 "confidence": 0.92,
#                 "source": "block",
#             }

#         if "loan_number" not in self.fields:
#             for t in line.split():
#                 d = ''.join(c for c in t if c.isdigit())
#                 if LOAN_RE.fullmatch(d) and not _is_phone_number(t):
#                     self.fields["loan_number"] = {
#                         "value": d,
#                         "confidence": 0.94,
#                         "source": "block",
#                     }

# # ============================================================
# # SAFE SWEEP
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     for i, line in enumerate(lines):
#         ll = line.lower()

#         if "insured_name" not in fields and ":" in line and any(k in ll for k in INSURED_LABELS):
#             v = _normalize_name(line.split(":", 1)[1])
#             if _looks_like_name(v):
#                 fields["insured_name"] = {
#                     "value": v, "confidence": 0.88, "source": "sweep"
#                 }

#         if "property_address" not in fields and any(k in ll for k in PROPERTY_TRIGGERS):
#             for j in range(i + 1, min(i + 4, len(lines))):
#                 if _looks_like_address(lines[j]):
#                     fields["property_address"] = {
#                         "value": lines[j].strip(),
#                         "confidence": 0.86,
#                         "source": "sweep",
#                     }
#                     break

# # ============================================================
# # ENTRY
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     extractor = StatefulExtractor()
#     for raw in lines:
#         line = raw.strip()
#         if line:
#             extractor.update_role(line)
#             extractor.extract(line)
#     _safe_sweep(lines, extractor.fields)
#     return extractor.fields

# def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     return extract_fields(lines, layout_elements)


#Claude Version (1st)
"""
Stage 1 – Stateful, Role-Anchored Deterministic Extraction (FIXED VERSION)
==========================================================================
FIXES APPLIED:
1. Policy Number - More flexible regex, better inline extraction
2. Insured Name - Relaxed validation, multi-line support, better cleanup
3. Property Address - PO Box support, multi-line accumulation, state/ZIP detection

Key Changes:
- Added mailing_address extraction (was missing entirely)
- Fixed _looks_like_name() being too strict (caps requirement)
- Fixed _looks_like_policy() rejecting valid formats
- Fixed _looks_like_address() rejecting PO Boxes
- Added carrier extraction
- Added date extraction
- Increased role windows for better capture
- Added fallback patterns in _safe_sweep
"""

import re
from typing import Dict, List
from enum import Enum, auto


# ============================================================
# ROLES
# ============================================================

class Role(Enum):
    NONE = auto()
    POLICY_HEADER = auto()
    INSURED_BLOCK = auto()
    PROPERTY_BLOCK = auto()
    MAILING_BLOCK = auto()  # NEW
    MORTGAGE_BLOCK = auto()
    CARRIER_BLOCK = auto()  # NEW


# ============================================================
# REGEX PATTERNS (ENHANCED)
# ============================================================

# Policy number patterns - MORE FLEXIBLE
POLICY_REGEX_VARIANTS = [
    re.compile(r"[A-Z]{1,4}[-\s]?\d{6,12}"),           # OKH3-109194373
    re.compile(r"[A-Z]{2,6}\s?\d{7,12}[-]?\d?"),       # DPC 0076173896-1
    re.compile(r"\d{8,14}"),                            # Pure numeric (8-14 digits)
    re.compile(r"[A-Z0-9]{2}[A-Z0-9\-]{5,25}"),        # Generic alphanumeric
    re.compile(r"[A-Z]{2,3}\d{2}[A-Z]?\d{5,10}"),      # HO3A12345678
]

DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
DATE_WRITTEN_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    re.I
)
LOAN_RE = re.compile(r"\d{8,18}")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
ZIP_RE = re.compile(r"\b\d{5}(-\d{4})?\b")

# Address patterns - ENHANCED
STREET_RE = re.compile(
    r"\d{1,6}\s+.+?\b("
    r"st|street|ave|avenue|rd|road|blvd|boulevard|"
    r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|"
    r"ridge|place|pl|terrace|ter|trail|trl|highway|hwy"
    r")\b",
    re.I,
)

PO_BOX_RE = re.compile(r"p\.?o\.?\s*box\s+\d+", re.I)

STATE_ABBREV = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}


# ============================================================
# MASTER KEYWORD LISTS (COMPREHENSIVE)
# ============================================================

POLICY_LABELS = {
    "policy number", "policy no", "policy #", "policy id",
    "policy number:", "policy no:", "policy #:",
    "dwelling policy number", "dwelling fire policy number",
    "homeowners policy number", "amended policy number",
    "renewal policy number", "previous policy number",
    "policy declarations", "nfip policy number",
    "flood policy number", "policy num",
}

INSURED_LABELS = {
    "insured", "named insured", "insured name",
    "insured name and address", "name and address",
    "insured mailing", "insured mailing name",
    "insured mailing name and address",
    "policyholder", "policyholder/insured",
    "policyholder/named insured", "policy holder",
    "insured:", "named insured:",
}

PROPERTY_TRIGGERS = {
    "property address", "property insured",
    "location of insured property", "insured property",
    "coverage detail for", "described location",
    "location id described location", "residence premises",
    "located at", "property location", "risk location",
    "insured location", "premises address",
    "location of property", "property:",
}

MAILING_TRIGGERS = {
    "mailing address", "mail address", "mailing:",
    "insured mailing name and address",
    "send mail to", "correspondence address",
}

MORTGAGE_TRIGGERS = {
    "mortgagee", "mortgagee full name",
    "mortgagee mailing name and address",
    "loss payee", "loss payee, mortgagee or other interest",
    "other interest", "other interested parties",
    "lender", "mortgage company", "mortgagee copy",
    "lienholder", "additional interest",
}

CARRIER_TRIGGERS = {
    "underwritten by", "insurance company",
    "issued by", "carrier", "insurer",
    "this policy is issued by",
}

LOAN_LABELS = {
    "loan number", "loan no", "loan #",
    "mortgage loan number", "account number",
    "loan number:", "loan #:", "reference number",
}

DATE_LABELS_EFFECTIVE = {
    "effective date", "policy effective date",
    "effective", "coverage begins", "from",
    "policy period", "term",
}

DATE_LABELS_EXPIRATION = {
    "expiration date", "policy expiration date",
    "expiration", "expires", "coverage ends", "to",
}

# ============================================================
# BLOCKLISTS (ENHANCED)
# ============================================================

BAD_NAME_PHRASES = {
    "our duties", "policy conditions", "coverage", "endorsement",
    "deductible", "liability", "property protection",
    "form number", "loss payment", "mortgagee certificate",
    "policy period", "coverage limits", "forms and endorsements",
    "premium", "billing", "payment", "invoice", "notice",
    "important", "please", "thank you", "declaration",
    "summary", "schedule", "total", "amount",
}

BAD_ADDRESS_PHRASES = {
    "coverage", "premium", "deductible", "endorsement",
    "policy period", "effective", "expiration", "billing",
    "payment", "invoice", "notice", "important",
    "forms and endorsements", "summary", "schedule",
}

BAD_MORTGAGE_PRODUCTS = {
    "ultrapack", "package", "homeowners", "dwelling",
    "special package", "policy", "endorsement", "insurance",
    "coverage", "premium",
}


# ============================================================
# HELPERS (FIXED)
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
    
    # Handle "LASTNAME, FIRSTNAME" format
    if "," in v and v.count(",") == 1:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if len(parts) == 2 and not any(c.isdigit() for c in v):
            # Only swap if both parts look like names (not addresses)
            if not any(w in parts[1].lower() for w in STATE_ABBREV):
                return f"{parts[1]} {parts[0]}"
    
    return v.strip()


def _is_phone_number(v: str) -> bool:
    """Check if value is a phone number"""
    digits = ''.join(c for c in v if c.isdigit())
    
    # Exactly 10 or 7 digits = likely phone
    if len(digits) in (7, 10):
        return True
    
    # Has phone formatting
    if PHONE_RE.search(v):
        return True
    
    return False


def _looks_like_name(text: str) -> bool:
    """
    Check if text looks like a person/company name
    FIXED: More relaxed validation
    """
    if not text or len(text) < 3:
        return False
    
    text = text.strip()
    ll = text.lower()
    
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
    
    # Allow entities with digits (LLC, Corp, etc.)
    has_entity = any(w in ll for w in ("llc", "inc", "corp", "company", "trust", "ltd", "bank", "mortgage"))
    
    # Block digits unless it's an entity
    if any(c.isdigit() for c in text) and not has_entity:
        return False
    
    words = text.replace(",", " ").split()
    word_count = len(words)
    
    # Entity names can be longer
    if has_entity:
        if not (2 <= word_count <= 12):
            return False
    else:
        if not (2 <= word_count <= 6):
            return False
    
    # RELAXED: At least 1 word should start with uppercase (was 2)
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
    FIXED: More flexible patterns, better blocking
    """
    if not v:
        return False
    
    v_original = v
    v_clean = re.sub(r"[\s\-]", "", v)
    
    # CRITICAL: Block phone numbers FIRST
    if _is_phone_number(v_original):
        return False
    
    # Block dates
    if DATE_RE.search(v_original) or DATE_WRITTEN_RE.search(v_original):
        return False
    
    # Block pure year references (2023, 2024, etc.)
    if v_clean.isdigit() and len(v_clean) == 4 and v_clean.startswith(('19', '20')):
        return False
    
    # Block ZIP codes (5 or 9 digits)
    if re.fullmatch(r"\d{5}(-\d{4})?", v_clean):
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
    
    # Must have at least 5 digits
    if digits < 5:
        return False
    
    # Pure numeric: 8-14 digits is OK
    if v_clean.isdigit():
        return 8 <= len(v_clean) <= 14
    
    # Mixed: check against patterns
    for rx in POLICY_REGEX_VARIANTS:
        if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
            return True
    
    # Fallback: alphanumeric with substantial digits
    if letters >= 1 and digits >= 6:
        return True
    
    return False


def _looks_like_address(line: str) -> bool:
    """
    Check if line looks like an address
    FIXED: Support PO Box, state/ZIP patterns
    """
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
        # Make sure it has some address-like content before the state
        parts = re.split(r"\b[A-Z]{2}\s+\d{5}", line)
        if parts and len(parts[0].strip()) > 5:
            return True
    
    # Has street number and reasonable length
    has_number = bool(re.search(r"^\d+\s+", line.strip()))
    word_count = len(line.split())
    if has_number and word_count >= 3:
        return True
    
    return False


def _extract_date(line: str, label_set: set) -> str:
    """Extract date from line if it matches label pattern"""
    ll = line.lower()
    
    if not any(k in ll for k in label_set):
        return None
    
    # Try written format first: January 15, 2024
    m = DATE_WRITTEN_RE.search(line)
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
        m = DATE_WRITTEN_RE.search(val) or DATE_RE.search(val)
        if m:
            return m.group(0)
    
    return None


# ============================================================
# STATEFUL EXTRACTOR (ENHANCED)
# ============================================================

class StatefulExtractor:
    def __init__(self):
        self.role = Role.NONE
        self.window = 0
        self.fields: Dict[str, Dict] = {}
        self.address_accumulator: List[str] = []  # For multi-line addresses
        self.insured_accumulator: List[str] = []  # For multi-line names
    
    def update_role(self, line: str):
        """Update current parsing role based on section headers"""
        ll = line.lower().strip()
        
        # Check for role triggers (order matters - more specific first)
        if any(k in ll for k in POLICY_LABELS):
            self.role, self.window = Role.POLICY_HEADER, 8
            self._flush_accumulators()
        elif any(k in ll for k in MAILING_TRIGGERS):
            self.role, self.window = Role.MAILING_BLOCK, 8
            self._flush_accumulators()
        elif any(k in ll for k in INSURED_LABELS):
            self.role, self.window = Role.INSURED_BLOCK, 12
            self._flush_accumulators()
        elif any(k in ll for k in PROPERTY_TRIGGERS):
            self.role, self.window = Role.PROPERTY_BLOCK, 8
            self._flush_accumulators()
        elif any(k in ll for k in MORTGAGE_TRIGGERS):
            self.role, self.window = Role.MORTGAGE_BLOCK, 10
            self._flush_accumulators()
        elif any(k in ll for k in CARRIER_TRIGGERS):
            self.role, self.window = Role.CARRIER_BLOCK, 6
            self._flush_accumulators()
    
    def _flush_accumulators(self):
        """Save accumulated multi-line values before role change"""
        if self.address_accumulator:
            addr = " ".join(self.address_accumulator)
            if "property_address" not in self.fields:
                self.fields["property_address"] = {
                    "value": addr, "confidence": 0.94, "source": "block_accumulated"
                }
            self.address_accumulator = []
        
        if self.insured_accumulator:
            name = " ".join(self.insured_accumulator)
            if "insured_name" not in self.fields and _looks_like_name(name):
                self.fields["insured_name"] = {
                    "value": name, "confidence": 0.94, "source": "block_accumulated"
                }
            self.insured_accumulator = []
    
    def extract(self, line: str):
        """Main extraction logic for each line"""
        # Always try inline extraction
        self._inline(line)
        
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
    
    def _inline(self, line: str):
        """Extract from inline patterns (Label: Value)"""
        ll = line.lower()
        
        # Policy Number: XXXXXXXX
        if "policy_number" not in self.fields:
            if ":" in line and any(k in ll for k in POLICY_LABELS):
                _, _, v = line.partition(":")
                v = _clean(v)
                # Handle split values like "DPC 0076173896 -1"
                v = re.sub(r"\s+(\d)$", r"-\1", v)
                v = v.replace(" ", "")
                if _looks_like_policy(v):
                    self.fields["policy_number"] = {
                        "value": v, "confidence": 0.99, "source": "inline"
                    }
        
        # Insured: John Doe
        if "insured_name" not in self.fields and ":" in line:
            label, _, val = line.partition(":")
            if label.lower().strip() in INSURED_LABELS or any(k in label.lower() for k in ("insured", "policyholder")):
                v = _normalize_name(val)
                if v and _looks_like_name(v):
                    self.fields["insured_name"] = {
                        "value": v, "confidence": 0.99, "source": "inline"
                    }
        
        # Loan Number
        if "loan_number" not in self.fields and any(k in ll for k in LOAN_LABELS):
            if ":" in line:
                _, _, v = line.partition(":")
                digits = ''.join(c for c in v if c.isdigit())
            else:
                digits = ''.join(c for c in line if c.isdigit())
            
            if len(digits) >= 8 and not _is_phone_number(digits):
                self.fields["loan_number"] = {
                    "value": digits, "confidence": 0.96, "source": "inline"
                }
        
        # Effective Date
        if "effective_date" not in self.fields:
            date = _extract_date(line, DATE_LABELS_EFFECTIVE)
            if date:
                self.fields["effective_date"] = {
                    "value": date, "confidence": 0.95, "source": "inline"
                }
        
        # Expiration Date
        if "expiration_date" not in self.fields:
            date = _extract_date(line, DATE_LABELS_EXPIRATION)
            if date:
                self.fields["expiration_date"] = {
                    "value": date, "confidence": 0.95, "source": "inline"
                }
    
    def _policy(self, line: str):
        """Extract policy number from POLICY block"""
        if "policy_number" in self.fields:
            return
        
        # Try each token
        for token in line.split():
            clean_token = _clean(token)
            if _looks_like_policy(clean_token):
                self.fields["policy_number"] = {
                    "value": clean_token, "confidence": 0.96, "source": "block"
                }
                return
        
        # Try the whole line (handles spaces in policy numbers)
        clean_line = _clean(line)
        no_spaces = clean_line.replace(" ", "")
        if _looks_like_policy(no_spaces):
            self.fields["policy_number"] = {
                "value": no_spaces, "confidence": 0.94, "source": "block_combined"
            }
    
    def _insured(self, line: str):
        """Extract insured name from INSURED block"""
        ll = line.lower().strip()
        
        # Skip obvious non-name lines
        skip_patterns = [
            "po box", "policy period", "loan number", "policy type",
            "description", "coverage", "premium", "effective", "expiration",
            "page", "continued", "summary"
        ]
        if any(p in ll for p in skip_patterns):
            return
        
        # Skip if line is just a header
        if line.strip().endswith(":") or line.strip().lower() in INSURED_LABELS:
            return
        
        clean_line = _normalize_name(line)
        
        # Check if it's a name
        if _looks_like_name(clean_line):
            if "insured_name" not in self.fields:
                self.fields["insured_name"] = {
                    "value": clean_line, "confidence": 0.97, "source": "block"
                }
            return
        
        # Check if it's an address (capture for mailing)
        if _looks_like_address(line):
            if "mailing_address" not in self.fields:
                self.fields["mailing_address"] = {
                    "value": line.strip(), "confidence": 0.92, "source": "insured_block"
                }
    
    def _property(self, line: str):
        """Extract property address from PROPERTY block"""
        ll = line.lower().strip()
        
        # Skip headers and labels
        if line.strip().endswith(":") or ll in [t.lower() for t in PROPERTY_TRIGGERS]:
            return
        
        if _looks_like_address(line):
            if "property_address" not in self.fields:
                self.fields["property_address"] = {
                    "value": line.strip(),
                    "confidence": 0.98,
                    "source": "block",
                }
            elif len(line.strip()) > len(self.fields["property_address"]["value"]):
                # Update if we found a more complete address
                self.fields["property_address"]["value"] = line.strip()
    
    def _mailing(self, line: str):
        """Extract mailing address from MAILING block"""
        ll = line.lower().strip()
        
        # Skip headers
        if line.strip().endswith(":"):
            return
        
        if _looks_like_address(line):
            if "mailing_address" not in self.fields:
                self.fields["mailing_address"] = {
                    "value": line.strip(),
                    "confidence": 0.96,
                    "source": "mailing_block",
                }
        elif _looks_like_name(line) and "insured_name" not in self.fields:
            # Name might appear in mailing block too
            self.fields["insured_name"] = {
                "value": _normalize_name(line),
                "confidence": 0.90,
                "source": "mailing_block",
            }
    
    def _mortgage(self, line: str):
        """Extract mortgage company and loan number from MORTGAGE block"""
        ll = line.lower()
        
        # Skip product names and junk
        if any(p in ll for p in BAD_MORTGAGE_PRODUCTS):
            return
        
        # Skip headers
        if line.strip().endswith(":"):
            return
        
        # Mortgage company
        if "mortgage_company" not in self.fields and _looks_like_name(line):
            # Additional check: should have bank/mortgage-like words or be a company
            if any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "isaoa", "atima")):
                self.fields["mortgage_company"] = {
                    "value": line.strip(),
                    "confidence": 0.94,
                    "source": "block",
                }
            elif _looks_like_name(line):
                self.fields["mortgage_company"] = {
                    "value": line.strip(),
                    "confidence": 0.88,
                    "source": "block",
                }
        
        # Loan number
        if "loan_number" not in self.fields:
            for token in line.split():
                digits = ''.join(c for c in token if c.isdigit())
                if len(digits) >= 8 and not _is_phone_number(token):
                    self.fields["loan_number"] = {
                        "value": digits,
                        "confidence": 0.94,
                        "source": "block",
                    }
                    break
    
    def _carrier(self, line: str):
        """Extract carrier name from CARRIER block"""
        if "carrier_name" in self.fields:
            return
        
        ll = line.lower()
        
        # Skip headers
        if line.strip().endswith(":"):
            return
        
        # Look for insurance company patterns
        if "insurance" in ll and any(w in ll for w in ("company", "exchange", "group", "mutual", "corp")):
            # Block agencies
            if not any(w in ll for w in ("agency", "agent", "services", "producer")):
                self.fields["carrier_name"] = {
                    "value": line.strip().upper(),
                    "confidence": 0.96,
                    "source": "block",
                }
    
    def finalize(self):
        """Final cleanup and flush"""
        self._flush_accumulators()


# ============================================================
# SAFE SWEEP (ENHANCED FALLBACK)
# ============================================================

def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
    """
    Final pass to catch missed fields using lookahead patterns
    """
    text_block = "\n".join(lines)
    
    # --- Policy Number fallback ---
    if "policy_number" not in fields:
        # Look for "Policy Number" followed by value on same or next line
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in POLICY_LABELS):
                # Check same line after colon
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = _clean(v).replace(" ", "")
                    if _looks_like_policy(v):
                        fields["policy_number"] = {
                            "value": v, "confidence": 0.88, "source": "sweep"
                        }
                        break
                
                # Check next few lines
                for j in range(i + 1, min(i + 3, len(lines))):
                    candidate = _clean(lines[j]).replace(" ", "")
                    if _looks_like_policy(candidate):
                        fields["policy_number"] = {
                            "value": candidate, "confidence": 0.85, "source": "sweep_lookahead"
                        }
                        break
                if "policy_number" in fields:
                    break
    
    # --- Insured Name fallback ---
    if "insured_name" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in INSURED_LABELS):
                # Check same line after colon
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = _normalize_name(v)
                    if _looks_like_name(v):
                        fields["insured_name"] = {
                            "value": v, "confidence": 0.88, "source": "sweep"
                        }
                        break
                
                # Check next few lines
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = _normalize_name(lines[j])
                    if _looks_like_name(candidate):
                        fields["insured_name"] = {
                            "value": candidate, "confidence": 0.85, "source": "sweep_lookahead"
                        }
                        break
                if "insured_name" in fields:
                    break
    
    # --- Property Address fallback ---
    if "property_address" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in PROPERTY_TRIGGERS):
                # Check same line (might have address inline)
                if _looks_like_address(line) and ":" in line:
                    _, _, v = line.partition(":")
                    if _looks_like_address(v):
                        fields["property_address"] = {
                            "value": v.strip(), "confidence": 0.86, "source": "sweep"
                        }
                        break
                
                # Check next few lines
                for j in range(i + 1, min(i + 5, len(lines))):
                    if _looks_like_address(lines[j]):
                        fields["property_address"] = {
                            "value": lines[j].strip(), "confidence": 0.84, "source": "sweep_lookahead"
                        }
                        break
                if "property_address" in fields:
                    break
    
    # --- Mailing Address fallback ---
    if "mailing_address" not in fields:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in MAILING_TRIGGERS):
                for j in range(i + 1, min(i + 5, len(lines))):
                    if _looks_like_address(lines[j]):
                        fields["mailing_address"] = {
                            "value": lines[j].strip(), "confidence": 0.84, "source": "sweep_lookahead"
                        }
                        break
                if "mailing_address" in fields:
                    break
    
    # --- Carrier Name fallback (scan first 15 lines) ---
    if "carrier_name" not in fields:
        for line in lines[:15]:
            ll = line.lower()
            if "insurance" in ll:
                if any(w in ll for w in ("company", "exchange", "group", "mutual", "corp")):
                    if not any(w in ll for w in ("agency", "agent", "services")):
                        fields["carrier_name"] = {
                            "value": line.strip().upper(),
                            "confidence": 0.85,
                            "source": "sweep_header",
                        }
                        break
    
    # --- Date extraction fallback ---
    for line in lines:
        if "effective_date" not in fields:
            date = _extract_date(line, DATE_LABELS_EFFECTIVE)
            if date:
                fields["effective_date"] = {
                    "value": date, "confidence": 0.85, "source": "sweep"
                }
        
        if "expiration_date" not in fields:
            date = _extract_date(line, DATE_LABELS_EXPIRATION)
            if date:
                fields["expiration_date"] = {
                    "value": date, "confidence": 0.85, "source": "sweep"
                }


# ============================================================
# ENTRY POINTS
# ============================================================

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
    
    return extractor.fields


def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    """Alias for backward compatibility"""
    return extract_fields(lines, layout_elements)
 