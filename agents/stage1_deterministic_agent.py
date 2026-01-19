# """
# Stage 1 – Stateful, Role-Anchored Deterministic Extraction (FINAL LOCKED)
# ========================================================================
# Authoritative extraction layer.
# No guessing. No fallback. No semantic inference.
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
#     MAILING_BLOCK = auto()
#     PROPERTY_BLOCK = auto()
#     MORTGAGE_BLOCK = auto()


# # ============================================================
# # REGEX (HARD CONSTRAINTS)
# # ============================================================

# # Requires at least 6 digits inside the token
# POLICY_RE = re.compile(
#     r"\b[A-Z0-9][A-Z0-9\- ]{5,20}\b(?=(?:.*\d){6,})"
# )

# PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
# DATE_RE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
# CURRENCY_RE = re.compile(r"\$\s?\d")
# ZIP_RE = re.compile(r"\b\d{5}(-\d{4})?\b")
# STATE_ZIP_INLINE_RE = re.compile(r"\b[A-Z]{2}\s*\d{5}(-\d{4})?\b")

# STREET_RE = re.compile(
#     r"\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court)\b",
#     re.I,
# )


# # ============================================================
# # SECTION HEADERS (GUARD)
# # ============================================================

# SECTION_TITLES = {
#     "policy type",
#     "policy period",
#     "named insured",
#     "named insured and mailing address",
#     "insured and mailing address",
#     "mailing address",
#     "coverage",
#     "coverages",
#     "summary",
#     "forms and endorsements",
#     "deductible",
#     "payment plan",
#     "agent",
#     "mortgagee",
#     "important notice",
# }


# def is_section_header(line: str) -> bool:
#     l = line.lower().strip()
#     if not l:
#         return False

#     if l in SECTION_TITLES:
#         return True

#     if l.endswith(":") and len(l.split()) <= 6:
#         return True

#     return False


# # ============================================================
# # ANCHORS
# # ============================================================

# POLICY_ANCHORS = {
#     "policy number",
#     "policy no",
#     "policy #",
#     "policy:",
#     "dwelling fire policy number",
# }

# INSURED_ANCHORS = {
#     "named insured",
#     "insured",
#     "insured name",
#     "insured and mailing address",
#     "policyholder",
#     "policyholder(s)",
# }

# MAILING_ANCHORS = {
#     "mailing address",
#     "insured mailing address",
# }

# PROPERTY_ANCHORS = {
#     "location of insured property",
#     "property address",
#     "property insured",
#     "described location",
# }

# MORTGAGE_ANCHORS = {
#     "mortgagee",
#     "loss payee",
#     "other interest",
# }

# SECTION_BREAKERS = {
#     "coverage",
#     "endorsement",
#     "deductible",
#     "conditions",
#     "forms",
#     "liability",
#     "schedule",
#     "important notice",
# }


# # ============================================================
# # VALIDATORS
# # ============================================================

# def valid_policy(v: str) -> bool:
#     v = v.strip()

#     if PHONE_RE.search(v):
#         return False
#     if DATE_RE.search(v) or CURRENCY_RE.search(v):
#         return False
#     if ZIP_RE.fullmatch(v) or STATE_ZIP_INLINE_RE.search(v):
#         return False

#     if re.match(r"^(NW-|HO-|DP-|HS-|IN-|CL-|AP-)", v):
#         return False

#     digits = sum(c.isdigit() for c in v)

#     return (
#         7 <= len(v) <= 20
#         and digits >= 6
#     )


# def valid_name(line: str) -> bool:
#     if ":" in line:
#         return False
#     if any(c.isdigit() for c in line):
#         return False

#     l = line.lower()
#     for bad in (
#         "policy type",
#         "coverage",
#         "deductible",
#         "endorsement",
#         "mortgagee",
#         "important notice",
#         "thank you",
#         "summary",
#     ):
#         if bad in l:
#             return False

#     words = line.split()
#     return 2 <= len(words) <= 6


# def valid_address(line: str) -> bool:
#     return bool(
#         STREET_RE.search(line)
#         or STATE_ZIP_INLINE_RE.search(line)
#         or "po box" in line.lower()
#     )


# # ============================================================
# # EXTRACTOR
# # ============================================================

# class StatefulExtractor:
#     def __init__(self):
#         self.role = Role.NONE
#         self.fields: Dict[str, Dict] = {}

#     # ----------------------------
#     # ROLE UPDATE
#     # ----------------------------

#     def update_role(self, line: str):
#         ll = line.lower().strip()

#         if any(b in ll for b in SECTION_BREAKERS):
#             self.role = Role.NONE
#             return

#         if any(a in ll for a in INSURED_ANCHORS):
#             self.role = Role.INSURED_BLOCK
#         elif any(a in ll for a in MAILING_ANCHORS):
#             self.role = Role.MAILING_BLOCK
#         elif any(a in ll for a in PROPERTY_ANCHORS):
#             self.role = Role.PROPERTY_BLOCK
#         elif any(a in ll for a in MORTGAGE_ANCHORS):
#             self.role = Role.MORTGAGE_BLOCK

#     # ----------------------------
#     # EXTRACTION
#     # ----------------------------

#     def extract(self, line: str):
#         self._extract_policy(line)

#         if self.role == Role.INSURED_BLOCK:
#             self._extract_insured(line)
#         elif self.role == Role.MAILING_BLOCK:
#             self._extract_mailing(line)
#         elif self.role == Role.PROPERTY_BLOCK:
#             self._extract_property(line)

#     # ----------------------------
#     # FIELD EXTRACTORS
#     # ----------------------------

#     def _extract_policy(self, line: str):
#         if "policy_number" in self.fields:
#             return

#         ll = line.lower()
#         if not any(a in ll for a in POLICY_ANCHORS):
#             return

#         tokens = re.findall(POLICY_RE, line)
#         for t in tokens:
#             v = t.replace(" ", "").strip()
#             if valid_policy(v):
#                 self.fields["policy_number"] = {
#                     "value": v,
#                     "confidence": 0.99,
#                     "source": "stage1_policy_anchor",
#                 }
#                 return

#     def _extract_insured(self, line: str):
#         if "insured_name" in self.fields:
#             return
#         if is_section_header(line):
#             return
#         if valid_name(line):
#             self.fields["insured_name"] = {
#                 "value": line.strip(),
#                 "confidence": 0.95,
#                 "source": "stage1_insured_block",
#             }

#     def _extract_mailing(self, line: str):
#         if "mailing_address" in self.fields:
#             return
#         if is_section_header(line):
#             return
#         if valid_address(line):
#             self.fields["mailing_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.93,
#                 "source": "stage1_mailing_block",
#             }

#     def _extract_property(self, line: str):
#         if "property_address" in self.fields:
#             return
#         if is_section_header(line):
#             return
#         if valid_address(line):
#             self.fields["property_address"] = {
#                 "value": line.strip(),
#                 "confidence": 0.96,
#                 "source": "stage1_property_block",
#             }


# # ============================================================
# # PUBLIC ENTRY POINT
# # ============================================================

# def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
#     extractor = StatefulExtractor()

#     for raw in lines:
#         line = raw.strip()
#         if not line:
#             continue

#         extractor.update_role(line)
#         extractor.extract(line)

#     return extractor.fields
 

"""
Stage 1 – Stateful, Role-Anchored Deterministic Extraction (FINAL LOCKED)
========================================================================
Authoritative extraction layer.
No guessing. No fallback. No semantic inference.
"""

import re
from typing import Dict, List
from enum import Enum, auto

from pyparsing import line


# ============================================================
# ROLES
# ============================================================

class Role(Enum):
    NONE = auto()
    POLICY_HEADER = auto()
    INSURED_BLOCK = auto()
    MAILING_BLOCK = auto()
    PROPERTY_BLOCK = auto()


# ============================================================
# REGEX (HARD CONSTRAINTS)
# ============================================================

POLICY_RE = re.compile(r"\b[A-Z0-9][A-Z0-9\- ]{5,25}\b")

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
DATE_RE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
CURRENCY_RE = re.compile(r"\$\s?\d")
ZIP_RE = re.compile(r"\b\d{5}(-\d{4})?\b")
STATE_ZIP_INLINE_RE = re.compile(r"\b[A-Z]{2}\s*\d{5}(-\d{4})?\b")

STREET_RE = re.compile(
    r"\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court|cir)\b",
    re.I,
)


# ============================================================
# SECTION GUARD
# ============================================================

SECTION_TITLES = {
    "policy type",
    "policy period",
    "coverage",
    "summary",
    "forms and endorsements",
    "deductible",
    "agent",
    "mortgagee",
    "important notice",
    "for your information",
    "continued",
}


def is_section_header(line: str) -> bool:
    l = line.lower().strip()
    if not l:
        return False
    if l in SECTION_TITLES:
        return True
    if l.endswith(":") and len(l.split()) <= 6:
        return True
    return False


# ============================================================
# ANCHORS
# ============================================================

POLICY_ANCHORS = {
    "policy number",
    "policy no",
    "policy #",
    "dwelling fire policy number",
}

INSURED_ANCHORS = {
    "named insured",
    "insured name",
    "insured",
    "policyholder",
}

MAILING_ANCHORS = {
    "mailing address",
    "insured mailing address",
}

PROPERTY_ANCHORS = {
    "location of insured property",
    "location of residence premises",
    "property address",
}


# ============================================================
# VALIDATORS
# ============================================================

def valid_policy(v: str) -> bool:
    if PHONE_RE.search(v):
        return False
    if DATE_RE.search(v) or CURRENCY_RE.search(v):
        return False
    if ZIP_RE.fullmatch(v) or STATE_ZIP_INLINE_RE.search(v):
        return False

    digits = sum(c.isdigit() for c in v)
    return 7 <= len(v) <= 25 and digits >= 6


def valid_name(line: str) -> bool:
    line = line.strip()

    # Hard rejects
    if not line:
        return False
    if ":" in line:
        return False
    if any(c.isdigit() for c in line):
        return False

    ll = line.lower()

    # Block structural / narrative phrases
    bad_phrases = (
        "policy",
        "coverage",
        "information",
        "notice",
        "summary",
        "conditions",
        "endorsement",
        "mortgagee",
        "additional interest",
        "additional insured",
        "for your information",
        "general conditions",
        "policy change",
        "declarations",
        "forms",
        "limits",
    )
    if any(bad in ll for bad in bad_phrases):
        return False

    # Reject slash-heavy lines (headers, forms)
    if "/" in line:
        return False

    # Normalize words
    words = [w for w in line.replace(",", "").split() if w]

    # Entity support
    entity_terms = {"llc", "inc", "corp", "company", "trust", "ltd", "pllc"}
    if any(w.lower() in entity_terms for w in words):
        return 2 <= len(words) <= 8

    # Comma-separated multiple people
    if "," in line:
        return 3 <= len(words) <= 8

    # Human names
    if not (2 <= len(words) <= 5):
        return False

    # Capitalization signal
    caps = sum(w[0].isupper() for w in words if w)
    if caps < 2:
        return False

    return True
 
def valid_address(line: str) -> bool:
    return bool(
        STREET_RE.search(line)
        or STATE_ZIP_INLINE_RE.search(line)
        or "po box" in line.lower()
    )


# ============================================================
# EXTRACTOR
# ============================================================

class StatefulExtractor:
    def __init__(self):
        self.role = Role.NONE
        self.window = 0
        self.expect_policy = False
        self.fields: Dict[str, Dict] = {}

    # ----------------------------
    # ROLE UPDATE
    # ----------------------------

    def update_role(self, line: str):
        ll = line.lower().strip()

        if any(a in ll for a in POLICY_ANCHORS):
            self.role = Role.POLICY_HEADER
            self.window = 3          # 👈 allow next lines
            self.expect_policy = True
            return

        if self.expect_policy:
            return  # 🔒 do NOT break policy window

        if any(a in ll for a in INSURED_ANCHORS):
            self.role = Role.INSURED_BLOCK
            self.window = 3
        elif any(a in ll for a in MAILING_ANCHORS):
            self.role = Role.MAILING_BLOCK
            self.window = 3
        elif any(a in ll for a in PROPERTY_ANCHORS):
            self.role = Role.PROPERTY_BLOCK
            self.window = 3

    # ----------------------------
    # EXTRACTION
    # ----------------------------

    def extract(self, line: str):
        if self.window <= 0:
            return
        if is_section_header(line):
            self.window -= 1
            return

        extracted = False

        if self.role == Role.POLICY_HEADER:
            extracted = self._extract_policy(line)
        elif self.role == Role.INSURED_BLOCK:
            extracted = self._extract_insured(line)
        elif self.role == Role.MAILING_BLOCK:
            extracted = self._extract_mailing(line)
        elif self.role == Role.PROPERTY_BLOCK:
            extracted = self._extract_property(line)

        if not extracted:
            self.window -= 1

    # ----------------------------
    # FIELD EXTRACTORS
    # ----------------------------

    def _extract_policy(self, line: str) -> bool:
        if "policy_number" in self.fields or not self.expect_policy:
            return False

        for t in POLICY_RE.findall(line):
            v = t.replace(" ", "")
            if valid_policy(v):
                self.fields["policy_number"] = {
                    "value": v,
                    "confidence": 0.99,
                    "source": "stage1_policy",
                }
                self.expect_policy = False
                self.window = 0
                self.role = Role.NONE
                return True
        return False

    def _extract_insured(self, line: str) -> bool:
        if "insured_name" in self.fields:
            return False

        line = line.strip()
        if not line:
            return False

        # If we have a pending first-half name, try to merge
        if self._pending_name:
            combined = f"{self._pending_name} {line}".strip()
            if valid_name(combined):
                self.fields["insured_name"] = {
                    "value": combined,
                    "confidence": 0.96,
                    "source": "stage1_insured_multiline",
                }
                self._pending_name = None
                return True
            else:
                # Drop pending if merge fails
                self._pending_name = None

        # Normal single-line name
        if valid_name(line):
            self.fields["insured_name"] = {
                "value": line,
                "confidence": 0.96,
                "source": "stage1_insured",
            }
            return True

        # Capture possible first half of a split name (ALL CAPS, 1–2 words)
        if line.isupper() and 1 <= len(line.split()) <= 2:
            self._pending_name = line

        return False


    def _extract_mailing(self, line: str) -> bool:
        if "mailing_address" in self.fields:
            return False
        if valid_address(line):
            self.fields["mailing_address"] = {
                "value": line.strip(),
                "confidence": 0.93,
                "source": "stage1_mailing",
            }
            return True
        return False

    def _extract_property(self, line: str) -> bool:
        if "property_address" in self.fields:
            return False
        if valid_address(line):
            self.fields["property_address"] = {
                "value": line.strip(),
                "confidence": 0.96,
                "source": "stage1_property",
            }
            return True
        return False


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    extractor = StatefulExtractor()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        extractor.update_role(line)
        extractor.extract(line)
    return extractor.fields

