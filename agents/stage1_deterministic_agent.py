# ##1st
# # stage1_deterministic_agent.py
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


# # ============================================================
# # REGEX
# # ============================================================

# POLICY_RE = re.compile(r"[A-Z0-9][A-Z0-9\-]{4,20}")
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# LOAN_RE = re.compile(r"\b\d{8,15}\b")

# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy"
#     r")\b",
#     re.I,
# )

# BAD_NAME_PHRASES = {
#     "our duties",
#     "policy conditions",
#     "building owner",
#     "coverage",
#     "mortgagee",
#     "loss payment",
#     "appraisal",
# }

# # ============================================================
# # HELPERS
# # ============================================================

# def _clean(v: str) -> str:
#     return re.sub(r"\s+", " ", v).strip(" ,.;:")


# def _normalize_name(v: str) -> str:
#     v = v.strip()
#     if "," in v:
#         parts = [p.strip() for p in v.split(",") if p.strip()]
#         if len(parts) == 2:
#             return f"{parts[1]} {parts[0]}"
#     return v


# def _looks_like_name(text: str) -> bool:
#     t = text.strip()
#     ll = t.lower()

#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False

#     if any(c.isdigit() for c in t):
#         return False

#     words = t.replace(",", "").split()
#     if not (1 <= len(words) <= 6):
#         return False

#     caps = sum(1 for w in words if w[0].isupper())
#     return caps >= 2


# def _looks_like_policy(v: str) -> bool:
#     v = v.replace(" ", "")
#     if DATE_RE.search(v):
#         return False
#     if v.startswith(("19", "20")):
#         return False
#     return bool(POLICY_RE.fullmatch(v))


# def _looks_like_carrier(line: str) -> bool:
#     t = line.upper()
#     return (
#         "INSURANCE" in t
#         and any(x in t for x in ("COMPANY", "CORPORATION", "EXCHANGE"))
#         and len(t.split()) >= 2
#     )


# def _looks_like_address(line: str) -> bool:
#     if "po box" in line.lower():
#         return False
#     return bool(STREET_RE.search(line))


# # ============================================================
# # EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.prev_line = ""
#         self.fields: Dict[str, Dict] = {}

#     def update_role(self, line: str):
#         ll = line.lower()
#         if "policy number" in ll:
#             self.role = Role.POLICY_HEADER
#             self.window = 5
#         elif ll.strip() in ("insured", "insured name and address", "policyholder/named insured"):
#             self.role = Role.INSURED_BLOCK
#             self.window = 4
#         elif "named insured" in ll:
#             self.role = Role.INSURED_BLOCK
#             self.window = 4
#         elif "property" in ll or "location" in ll:
#             self.role = Role.PROPERTY_BLOCK
#             self.window = 4

#     def extract(self, line: str):
#         if not line:
#             self.prev_line = line
#             return

#         self._inline(line)

#         if self.window <= 0:
#             self.role = Role.NONE
#             self.prev_line = line
#             return

#         if self.role == Role.POLICY_HEADER:
#             self._policy(line)
#         elif self.role == Role.INSURED_BLOCK:
#             self._insured(line)
#         elif self.role == Role.PROPERTY_BLOCK:
#             self._property(line)

#         self.window -= 1
#         self.prev_line = line

#     # ---------------- INLINE ----------------

#     def _inline(self, line: str):
#         ll = line.lower()

#         # Carrier
#         if "carrier_name" not in self.fields and _looks_like_carrier(line):
#             self.fields["carrier_name"] = {
#                 "value": line.strip(),
#                 "confidence": 0.99,
#                 "source": "stage1_carrier",
#             }

#         # Policy Number (inline)
#         if "policy_number" not in self.fields and "policy number" in ll:
#             _, _, v = line.partition(":")
#             v = _clean(v)
#             v = v.replace(" ", "")
#             if _looks_like_policy(v):
#                 self.fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.99,
#                     "source": "stage1_policy",
#                 }

#         # Insured inline (Aegis fix)
#         if "insured_name" not in self.fields and ll.startswith("insured:"):
#             _, _, v = line.partition(":")
#             v = _normalize_name(v)
#             if _looks_like_name(v):
#                 self.fields["insured_name"] = {
#                     "value": v,
#                     "confidence": 0.99,
#                     "source": "stage1_insured_inline",
#                 }

#         # Loan Number
#         if "loan_number" not in self.fields and "loan number" in ll:
#             _, _, v = line.partition(":")
#             v = v.strip()
#             if LOAN_RE.fullmatch(v):
#                 self.fields["loan_number"] = {
#                     "value": v,
#                     "confidence": 0.96,
#                     "source": "stage1_loan",
#                 }

#     # ---------------- ROLE ----------------

#     def _policy(self, line: str):
#         if "policy_number" in self.fields:
#             return
#         for p in line.split():
#             if _looks_like_policy(p):
#                 self.fields["policy_number"] = {
#                     "value": p,
#                     "confidence": 0.96,
#                     "source": "stage1_policy",
#                 }
#                 return

#     def _insured(self, line: str):
#         if "insured_name" in self.fields:
#             return

#         v = _normalize_name(line)
#         if _looks_like_name(v):
#             self.fields["insured_name"] = {
#                 "value": v,
#                 "confidence": 0.98,
#                 "source": "stage1_insured_block",
#             }

#     def _property(self, line: str):
#         if "property_address" in self.fields:
#             return
#         if _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.98,
#                 "source": "stage1_property",
#             }


# # ============================================================
# # SAFE FINAL SWEEP
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     for i, line in enumerate(lines):
#         ll = line.lower()

#         if "insured_name" not in fields and ll.strip() == "insured":
#             if i + 1 < len(lines):
#                 v = _normalize_name(lines[i + 1])
#                 if _looks_like_name(v):
#                     fields["insured_name"] = {
#                         "value": v,
#                         "confidence": 0.90,
#                         "source": "stage1_sweep",
#                     }

#         if "policy_number" not in fields and "policy number" in ll:
#             _, _, v = line.partition(":")
#             v = v.replace(" ", "")
#             if _looks_like_policy(v):
#                 fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.90,
#                     "source": "stage1_sweep",
#                 }


# # ============================================================
# # ENTRY
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     extractor = StatefulExtractor()

#     for raw in lines:
#         line = raw.strip()
#         extractor.update_role(line)
#         extractor.extract(line)

#     _safe_sweep(lines, extractor.fields)
#     return extractor.fields

# ## stage1_deterministic_agent.py
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

# # ============================================================
# # REGEX
# # ============================================================

# POLICY_RE = re.compile(r"[A-Z0-9][A-Z0-9\-]{4,25}")
# DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
# LOAN_RE = re.compile(r"\b\d{8,15}\b")

# STREET_RE = re.compile(
#     r"\b\d{1,6}\s+.+?\b("
#     r"st|street|ave|avenue|rd|road|blvd|boulevard|"
#     r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy"
#     r")\b",
#     re.I,
# )

# # ============================================================
# # HARD NEGATIVES (critical)
# # ============================================================

# BAD_NAME_PHRASES = {
#     "our duties",
#     "policy conditions",
#     "building owner",
#     "coverage",
#     "mortgagee",
#     "loss payment",
#     "appraisal",
#     "endorsement",
#     "conditions",
#     "deductible",
#     "liability",
# }

# # ============================================================
# # HELPERS
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

# def _looks_like_name(text: str) -> bool:
#     if not text:
#         return False

#     t = text.strip()
#     ll = t.lower()

#     if any(b in ll for b in BAD_NAME_PHRASES):
#         return False

#     if any(c.isdigit() for c in t):
#         return False

#     words = t.replace(",", "").split()
#     if not (2 <= len(words) <= 8):
#         return False

#     caps = sum(1 for w in words if w and w[0].isupper())
#     return caps >= 2

# def _looks_like_policy(v: str) -> bool:
#     v = v.replace(" ", "")
#     if DATE_RE.search(v):
#         return False
#     if v.startswith(("19", "20")):
#         return False
#     return bool(POLICY_RE.fullmatch(v))

# def _looks_like_carrier(line: str) -> bool:
#     t = line.upper()
#     return (
#         "INSURANCE" in t
#         and any(x in t for x in ("COMPANY", "CORPORATION", "EXCHANGE"))
#         and not any(x in t for x in ("AGENCY", "AGENT", "CENTER", "LLC", "INC"))
#         and 2 <= len(t.split()) <= 10
#     )

# def _looks_like_address(line: str) -> bool:
#     if "po box" in line.lower():
#         return False
#     return bool(STREET_RE.search(line))

# # ============================================================
# # EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.window = 0
#         self.fields: Dict[str, Dict] = {}

#     # ---------------- ROLE UPDATE ----------------

#     def update_role(self, line: str):
#         ll = line.lower()

#         if "policy number" in ll:
#             self.role = Role.POLICY_HEADER
#             self.window = 6

#         elif any(k in ll for k in (
#             "named insured",
#             "insured name and address",
#             "insured mailing",
#             "insured mailing name and address",
#             "policyholder/named insured",
#         )):
#             self.role = Role.INSURED_BLOCK
#             self.window = 8

#         elif any(k in ll for k in (
#             "property address",
#             "property insured",
#             "location of insured property",
#             "location of residence premises",
#         )):
#             self.role = Role.PROPERTY_BLOCK
#             self.window = 6

#     # ---------------- MAIN ----------------

#     def extract(self, line: str):
#         if not line:
#             return

#         self._inline(line)

#         if self.window <= 0:
#             self.role = Role.NONE
#             return

#         if self.role == Role.POLICY_HEADER:
#             self._policy(line)
#         elif self.role == Role.INSURED_BLOCK:
#             self._insured(line)
#         elif self.role == Role.PROPERTY_BLOCK:
#             self._property(line)

#         self.window -= 1

#     # ---------------- INLINE ----------------

#     def _inline(self, line: str):
#         ll = line.lower()

#         # Carrier
#         if "carrier_name" not in self.fields and _looks_like_carrier(line):
#             self.fields["carrier_name"] = {
#                 "value": line.strip(),
#                 "confidence": 0.99,
#                 "source": "stage1_carrier",
#             }

#         # Policy Number (inline)
#         if "policy_number" not in self.fields and "policy number" in ll:
#             _, _, v = line.partition(":")
#             v = _clean(v).replace(" ", "")
#             if _looks_like_policy(v):
#                 self.fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.99,
#                     "source": "stage1_policy",
#                 }

#         # Insured inline (Encompass / Aegis / Travelers)
#         if "insured_name" not in self.fields:
#             if ll.startswith("insured:") or "policyholder/named insured" in ll:
#                 _, _, v = line.partition(":")
#                 v = _normalize_name(v)
#                 if _looks_like_name(v):
#                     self.fields["insured_name"] = {
#                         "value": v,
#                         "confidence": 0.99,
#                         "source": "stage1_insured_inline",
#                     }

#         # Loan Number
#         if "loan_number" not in self.fields and "loan number" in ll:
#             _, _, v = line.partition(":")
#             v = v.strip()
#             if LOAN_RE.fullmatch(v):
#                 self.fields["loan_number"] = {
#                     "value": v,
#                     "confidence": 0.96,
#                     "source": "stage1_loan",
#                 }

#     # ---------------- ROLE EXTRACTORS ----------------

#     def _policy(self, line: str):
#         if "policy_number" in self.fields:
#             return
#         for p in line.split():
#             if _looks_like_policy(p):
#                 self.fields["policy_number"] = {
#                     "value": p,
#                     "confidence": 0.96,
#                     "source": "stage1_policy",
#                 }
#                 return

#     def _insured(self, line: str):
#         if "insured_name" in self.fields:
#             return

#         ll = line.lower()

#         if any(x in ll for x in (
#             "po box",
#             "policy period",
#             "address",
#             "county",
#             "property",
#         )):
#             return

#         v = _normalize_name(line)
#         if _looks_like_name(v):
#             self.fields["insured_name"] = {
#                 "value": v,
#                 "confidence": 0.98,
#                 "source": "stage1_insured_block",
#             }

#     def _property(self, line: str):
#         if "property_address" in self.fields:
#             return
#         if _looks_like_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.98,
#                 "source": "stage1_property",
#             }

# # ============================================================
# # FINAL SAFE SWEEP
# # ============================================================

# def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
#     for i, line in enumerate(lines):
#         ll = line.lower().strip()

#         if "insured_name" not in fields and ll in (
#             "insured",
#             "named insured",
#             "insured mailing name and address",
#         ):
#             if i + 1 < len(lines):
#                 v = _normalize_name(lines[i + 1])
#                 if _looks_like_name(v):
#                     fields["insured_name"] = {
#                         "value": v,
#                         "confidence": 0.90,
#                         "source": "stage1_sweep",
#                     }

# # ============================================================
# # ENTRY (UNCHANGED)
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     extractor = StatefulExtractor()

#     for raw in lines:
#         line = raw.strip()
#         extractor.update_role(line)
#         extractor.extract(line)

#     _safe_sweep(lines, extractor.fields)
#     return extractor.fields

# stage1_deterministic_agent.py
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

# ============================================================
# REGEX
# ============================================================

POLICY_RE = re.compile(r"[A-Z0-9][A-Z0-9\-]{4,25}")
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
LOAN_RE = re.compile(r"\b\d{8,15}\b")

STREET_RE = re.compile(
    r"\b\d{1,6}\s+.+?\b("
    r"st|street|ave|avenue|rd|road|blvd|boulevard|"
    r"ln|lane|dr|drive|ct|court|cir|circle|way|pkwy|ridge"
    r")\b",
    re.I,
)

# Patterns to clean from addresses
ADDRESS_CLEANUP_PATTERNS = [
    r"\s*\(continued\)",
    r"\s*\(see\s+.*?\)",
    r"\s*-\s*continued",
]

# ============================================================
# HARD NEGATIVES (critical)
# ============================================================

BAD_NAME_PHRASES = {
    "our duties",
    "policy conditions",
    "building owner",
    "coverage",
    "mortgagee",
    "loss payment",
    "appraisal",
    "endorsement",
    "conditions",
    "deductible",
    "liability",
}

# ============================================================
# HELPERS
# ============================================================

def _clean(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip(" ,.;:")

def _normalize_name(v: str) -> str:
    v = v.replace("0", "O")  # OCR fix
    v = v.strip()
    if "," in v:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
    return v

def _looks_like_name(text: str) -> bool:
    if not text:
        return False

    t = text.strip()
    ll = t.lower()

    # Hard blocklist
    if any(b in ll for b in BAD_NAME_PHRASES):
        return False

    # No digits allowed
    if any(c.isdigit() for c in t):
        return False

    words = t.replace(",", "").split()
    
    # Must have 2-8 words
    if not (2 <= len(words) <= 8):
        return False

    # At least 2 capitalized words (relaxed from strict requirement)
    caps = sum(1 for w in words if w and w[0].isupper())
    if caps < 2:
        return False
    
    # Additional check: avoid lines that are mostly lowercase
    # (indicates descriptive text, not a name)
    if sum(1 for c in t if c.islower()) > len(t) * 0.7:
        return False
    
    return True

def _looks_like_policy(v: str) -> bool:
    v = v.replace(" ", "")
    # Allow pure numeric sequences of 8-12 digits (Aegis: 2100375750)
    if v.isdigit() and 8 <= len(v) <= 12:
        return True
    if DATE_RE.search(v):
        return False
    if v.startswith(("19", "20")) and len(v) <= 6:
        return False
    return bool(POLICY_RE.fullmatch(v))

def _looks_like_carrier(line: str) -> bool:
    t = line.upper()
    
    # Must contain "INSURANCE"
    if "INSURANCE" not in t:
        return False
    
    # Must have one of these company indicators
    has_company_indicator = any(x in t for x in ("COMPANY", "CORPORATION", "EXCHANGE", "GROUP"))
    if not has_company_indicator:
        return False
    
    # Block agency/agent names
    if any(x in t for x in ("AGENCY", "AGENT", "CENTER")):
        return False
    
    # Block if it has LLC or INC (usually agencies)
    if "LLC" in t or "INC" in t:
        return False
    
    # Must have reasonable word count
    word_count = len(t.split())
    if not (2 <= word_count <= 10):
        return False
    
    return True

def _looks_like_address(line: str) -> bool:
    if "po box" in line.lower():
        return False
    
    # Clean up common address suffixes
    clean_line = line
    for pattern in ADDRESS_CLEANUP_PATTERNS:
        clean_line = re.sub(pattern, "", clean_line, flags=re.I)
    
    return bool(STREET_RE.search(clean_line))

# ============================================================
# EXTRACTOR
# ============================================================

class StatefulExtractor:
    def __init__(self):
        self.role = Role.NONE
        self.window = 0
        self.fields: Dict[str, Dict] = {}

    # ---------------- ROLE UPDATE ----------------

    def update_role(self, line: str):
        ll = line.lower()

        if "policy number" in ll:
            self.role = Role.POLICY_HEADER
            self.window = 6

        elif any(k in ll for k in (
            "named insured",
            "insured name and address",
            "insured mailing",
            "insured mailing name and address",
            "policyholder/named insured",
            "insured:",  # Erie specific
        )):
            self.role = Role.INSURED_BLOCK
            self.window = 8

        # FIX: Add more property address triggers
        elif any(k in ll for k in (
            "property address",
            "property insured",
            "location of insured property",
            "location of residence premises",
            "coverage detail for",  # Encompass specific
            "address:",  # Erie specific
        )):
            self.role = Role.PROPERTY_BLOCK
            self.window = 6

    # ---------------- MAIN ----------------

    def extract(self, line: str):
        if not line:
            return

        self._inline(line)

        if self.window <= 0:
            self.role = Role.NONE
            return

        if self.role == Role.POLICY_HEADER:
            self._policy(line)
        elif self.role == Role.INSURED_BLOCK:
            self._insured(line)
        elif self.role == Role.PROPERTY_BLOCK:
            self._property(line)

        self.window -= 1

    # ---------------- INLINE ----------------

    def _inline(self, line: str):
        ll = line.lower()

        # Carrier - ENHANCED
        if "carrier_name" not in self.fields:
            # Check for carrier name with asterisk (Adirondack case)
            clean_line = line.replace("*", "").strip()
            if _looks_like_carrier(clean_line):
                self.fields["carrier_name"] = {
                    "value": clean_line.upper(),
                    "confidence": 0.99,
                    "source": "stage1_carrier",
                }

        # Policy Number (inline) - ENHANCED
        if "policy_number" not in self.fields and "policy number" in ll:
            _, _, v = line.partition(":")
            v = _clean(v).replace(" ", "")
            if _looks_like_policy(v):
                self.fields["policy_number"] = {
                    "value": v,
                    "confidence": 0.99,
                    "source": "stage1_policy",
                }

        # Insured inline - EXPANDED triggers
        if "insured_name" not in self.fields:
            # Check multiple inline patterns
            if any(pattern in ll for pattern in [
                "insured:",
                "policyholder/named insured:",
                "named insured:",
                "insured mailing name and address:",  # Erie format
            ]):
                _, _, v = line.partition(":")
                v = _normalize_name(v)
                if _looks_like_name(v):
                    self.fields["insured_name"] = {
                        "value": v,
                        "confidence": 0.99,
                        "source": "stage1_insured_inline",
                    }

        # Loan Number
        if "loan_number" not in self.fields and "loan number" in ll:
            _, _, v = line.partition(":")
            v = v.strip()
            if LOAN_RE.fullmatch(v):
                self.fields["loan_number"] = {
                    "value": v,
                    "confidence": 0.96,
                    "source": "stage1_loan",
                }

        # Property address inline - EXPANDED
        if "property_address" not in self.fields:
            # Aegis format: "Property Insured: address"
            if "property insured:" in ll:
                _, _, v = line.partition(":")
                v = v.strip()
                if _looks_like_address(v):
                    self.fields["property_address"] = {
                        "value": v,
                        "confidence": 0.99,
                        "source": "stage1_property_inline",
                    }
            # Erie format: "Address: address"
            elif ll.startswith("address:"):
                _, _, v = line.partition(":")
                v = v.strip()
                if _looks_like_address(v):
                    self.fields["property_address"] = {
                        "value": v,
                        "confidence": 0.99,
                        "source": "stage1_property_inline",
                    }
            # AAA format: "Location of Insured Property"
            elif "location of insured property" in ll and len(line) > 40:
                # The address is on the same line after the label
                parts = line.split(maxsplit=4)
                if len(parts) > 4:
                    v = parts[4]
                    if _looks_like_address(v):
                        self.fields["property_address"] = {
                            "value": v,
                            "confidence": 0.98,
                            "source": "stage1_property_inline",
                        }

    # ---------------- ROLE EXTRACTORS ----------------

    def _policy(self, line: str):
        if "policy_number" in self.fields:
            return
        for p in line.split():
            if _looks_like_policy(p):
                self.fields["policy_number"] = {
                    "value": p,
                    "confidence": 0.96,
                    "source": "stage1_policy",
                }
                return

    def _insured(self, line: str):
        if "insured_name" in self.fields:
            return

        ll = line.lower()

        # Skip obvious non-name lines
        if any(x in ll for x in (
            "po box",
            "policy period",
            "county",
            "mailing address:",  # Skip the label itself
            "policy term:",
        )):
            return

        # Skip lines that are just "address" by itself
        if ll.strip() == "address":
            return

        v = _normalize_name(line)
        if _looks_like_name(v):
            self.fields["insured_name"] = {
                "value": v,
                "confidence": 0.98,
                "source": "stage1_insured_block",
            }

    def _property(self, line: str):
        if "property_address" in self.fields:
            return
        
        # Clean address before validation
        clean_line = line
        for pattern in ADDRESS_CLEANUP_PATTERNS:
            clean_line = re.sub(pattern, "", clean_line, flags=re.I)
        clean_line = clean_line.strip()
        
        if _looks_like_address(clean_line):
            self.fields["property_address"] = {
                "value": clean_line,
                "confidence": 0.98,
                "source": "stage1_property",
            }

# ============================================================
# FINAL SAFE SWEEP
# ============================================================

def _safe_sweep(lines: List[str], fields: Dict[str, Dict]) -> None:
    for i, line in enumerate(lines):
        ll = line.lower().strip()

        # Policy number sweep - ENHANCED
        if "policy_number" not in fields:
            # Standard "Policy Number:" format
            if "policy number" in ll and ":" in line:
                _, _, v = line.partition(":")
                v = v.replace(" ", "").strip()
                if _looks_like_policy(v):
                    fields["policy_number"] = {
                        "value": v,
                        "confidence": 0.90,
                        "source": "stage1_sweep_policy",
                    }
            # Aegis format: line starts with "Policy Number:" then value on same line
            elif ll.startswith("policy number:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    v = parts[1].split()[0] if parts[1].split() else ""
                    v = v.replace(" ", "").strip()
                    if _looks_like_policy(v):
                        fields["policy_number"] = {
                            "value": v,
                            "confidence": 0.90,
                            "source": "stage1_sweep_policy_aegis",
                        }

        # Insured name sweep - ENHANCED
        if "insured_name" not in fields:
            # Standard label formats
            if ll in ("insured", "named insured", "insured mailing name and address"):
                if i + 1 < len(lines):
                    v = _normalize_name(lines[i + 1])
                    if _looks_like_name(v):
                        fields["insured_name"] = {
                            "value": v,
                            "confidence": 0.90,
                            "source": "stage1_sweep",
                        }
            
            # Inline colon format: "Insured: NAME"
            elif "insured:" in ll and "insured_name" not in fields:
                _, _, v = line.partition(":")
                v = _normalize_name(v)
                if _looks_like_name(v):
                    fields["insured_name"] = {
                        "value": v,
                        "confidence": 0.88,
                        "source": "stage1_sweep_inline",
                    }
            
            # Encompass format: "Policyholder/Named Insured: Policyholder since:"
            # The name is on the NEXT line
            elif "policyholder/named insured:" in ll:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Name might be split by tabs/spaces from "Policyholder since:"
                    parts = next_line.split()
                    if len(parts) >= 2:
                        # Take first 2-4 words as name (before "July 2020" or "Policyholder")
                        name_parts = []
                        for word in parts:
                            if word.lower() in ("policyholder", "since:", "july", "january", "february", "march", "april", "may", "june", "august", "september", "october", "november", "december"):
                                break
                            if not any(c.isdigit() for c in word):
                                name_parts.append(word)
                        
                        if len(name_parts) >= 2:
                            v = " ".join(name_parts[:4])  # Max 4 words
                            if _looks_like_name(v):
                                fields["insured_name"] = {
                                    "value": v,
                                    "confidence": 0.87,
                                    "source": "stage1_sweep_encompass",
                                }
        
        # Carrier name sweep - ENHANCED
        if "carrier_name" not in fields:
            # Look for lines that look like carrier names
            clean_line = line.replace("*", "").strip()
            if _looks_like_carrier(clean_line):
                fields["carrier_name"] = {
                    "value": clean_line.upper(),
                    "confidence": 0.88,
                    "source": "stage1_sweep_carrier",
                }
        
        # Property address sweep - ENHANCED
        if "property_address" not in fields:
            # "Property Insured:" format
            if "property insured:" in ll:
                _, _, v = line.partition(":")
                v = v.strip()
                # Clean address
                for pattern in ADDRESS_CLEANUP_PATTERNS:
                    v = re.sub(pattern, "", v, flags=re.I)
                v = v.strip()
                if _looks_like_address(v):
                    fields["property_address"] = {
                        "value": v,
                        "confidence": 0.88,
                        "source": "stage1_sweep_property",
                    }
            
            # "Coverage Detail for 136 Old..." format (Encompass)
            elif "coverage detail for" in ll:
                _, _, v = line.partition("for")
                v = v.strip().rstrip(",")
                # Clean address
                for pattern in ADDRESS_CLEANUP_PATTERNS:
                    v = re.sub(pattern, "", v, flags=re.I)
                v = v.strip()
                if _looks_like_address(v):
                    fields["property_address"] = {
                        "value": v,
                        "confidence": 0.88,
                        "source": "stage1_sweep_coverage",
                    }
            
            # "Location of Insured Property" format
            elif ll.startswith("location of insured property"):
                if i + 1 < len(lines):
                    v = lines[i + 1].strip()
                    # Clean address
                    for pattern in ADDRESS_CLEANUP_PATTERNS:
                        v = re.sub(pattern, "", v, flags=re.I)
                    v = v.strip()
                    if _looks_like_address(v):
                        fields["property_address"] = {
                            "value": v,
                            "confidence": 0.88,
                            "source": "stage1_sweep_location",
                        }
            
            # "Address:" format (Erie)
            elif ll.startswith("address:"):
                _, _, v = line.partition(":")
                v = v.strip()
                # Clean address
                for pattern in ADDRESS_CLEANUP_PATTERNS:
                    v = re.sub(pattern, "", v, flags=re.I)
                v = v.strip()
                if _looks_like_address(v):
                    fields["property_address"] = {
                        "value": v,
                        "confidence": 0.88,
                        "source": "stage1_sweep_address",
                    }

# ============================================================
# ENTRY (UNCHANGED)
# ============================================================

def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    extractor = StatefulExtractor()

    for raw in lines:
        line = raw.strip()
        extractor.update_role(line)
        extractor.extract(line)

    _safe_sweep(lines, extractor.fields)
    return extractor.fields