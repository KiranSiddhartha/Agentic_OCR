"""
Stage 1 – Stateful, Role-Anchored Deterministic Extraction (LOCKED)
=================================================================

Covers:
- Declarations
- Mortgagee summaries
- Billing notices
- Renewal notices

Fully deterministic. Carrier-agnostic.
"""

import re
from typing import List, Dict
from enum import Enum, auto


# ============================================================
# ROLES
# ============================================================

class Role(Enum):
    NONE = auto()
    POLICY_HEADER = auto()
    INSURED_BLOCK = auto()
    MAILING_BLOCK = auto()
    PROPERTY_BLOCK = auto()
    MORTGAGE_BLOCK = auto()


# ============================================================
# REGEX
# ============================================================

POLICY_RE = re.compile(r"\b[A-Z0-9\- ]{6,25}\b")

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
SHORT_PHONE_RE = re.compile(r"\b\d{3}-\d{4}\b")

ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
STATE_ZIP_INLINE_RE = re.compile(r"\b[A-Z]{2}\d{5}(-\d{4})?\b")

DATE_RE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
CURRENCY_RE = re.compile(r"\$\d")

STATE_ZIP_RE = re.compile(r"\b[A-Z]{2}\s*\d{5}(-\d{4})?\b")
STREET_RE = re.compile(
    r"\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|lane|ln|drive|dr|ct|court|trl)\b",
    re.I,
)

SECTION_BREAKERS = {
    "coverage", "coverages", "limits", "endorsement",
    "deductible", "premium", "forms", "conditions",
    "policy conditions", "liability", "schedule"
}


# ============================================================
# VALIDATORS
# ============================================================

def valid_policy(val: str) -> bool:
    v = val.strip()

    if ZIP_RE.match(v):
        return False
    if STATE_ZIP_INLINE_RE.search(v):
        return False
    if re.search(r"\b[A-Z]{2}\s+\d{5}\b", v):
        return False
    if PHONE_RE.search(v) or SHORT_PHONE_RE.search(v):
        return False
    if DATE_RE.search(v):
        return False
    if CURRENCY_RE.search(v):
        return False

    if "-" in v and len(v.replace("-", "").replace(" ", "")) < 7:
        return False

    digits = sum(c.isdigit() for c in v)
    return digits >= 5 and 6 <= len(v.replace(" ", "")) <= 25


def valid_name(line: str) -> bool:
    if not line:
        return False

    l = line.lower()

    if len(line) > 80:
        return False

    if any(bad in l for bad in [
        "named insured",
        "insured and policy",
        "policyholder since",
        "coverage",
        "deductible",
        "conditions",
        "endorsement",
        "mortgagee",
        "policy number",
        "liability",
        "thank you for choosing",
        "a new & efficient way",
        "offers the option",
        "policy payment",
        "please contact",
    ]):
        return False

    if any(c.isdigit() for c in line):
        return False

    words = line.replace(",", "").split()
    return 2 <= len(words) <= 10


def valid_address(line: str) -> bool:
    return bool(
        STREET_RE.search(line)
        or STATE_ZIP_RE.search(line)
        or "po box" in line.lower()
    )


# ============================================================
# ANCHORS
# ============================================================

POLICY_ANCHORS = {
    "policy number",
    "policy no",
    "policy #",
    "dwelling fire policy number",
    "dwelling policy number",
    "fire policy number",
    "homeowners policy number",
}

INSURED_ANCHORS = {
    "named insured",
    "insured name",
    "insured:",
    "insured",
    "policyholder",
    "primary insured",
}

GROUP_INFO_ANCHORS = {
    "insured and policy information",
    "policyholder/named insured",
}

MAILING_ANCHORS = {
    "mailing address",
    "insured mailing address",
}

PROPERTY_ANCHORS = {
    "property address",
    "property insured",
    "location of insured property",
}

MORTGAGE_ANCHORS = {
    "mortgagee",
    "loss payee",
    "lender",
    "other interest",
}


# ============================================================
# STATEFUL EXTRACTOR
# ============================================================

class StatefulExtractor:
    def __init__(self):
        self.role = Role.NONE
        self.fields: Dict[str, Dict] = {}

    def update_role(self, line: str):
        ll = line.lower().strip()

        if any(b in ll for b in SECTION_BREAKERS):
            self.role = Role.NONE
            return

        if any(a in ll for a in GROUP_INFO_ANCHORS):
            self.role = Role.INSURED_BLOCK
            return

        if any(a in ll for a in POLICY_ANCHORS):
            self.role = Role.POLICY_HEADER
            return

        if any(a in ll for a in INSURED_ANCHORS):
            self.role = Role.INSURED_BLOCK
            return

        if any(a in ll for a in MAILING_ANCHORS):
            self.role = Role.MAILING_BLOCK
            return

        if any(a in ll for a in PROPERTY_ANCHORS):
            self.role = Role.PROPERTY_BLOCK
            return

    def extract(self, line: str):
        if ":" in line:
            label, value = line.split(":", 1)
            label_l = label.lower()
            value = value.strip()

            if "policy number" in label_l:
                self._extract_policy(value)
                return
            if "insured" in label_l:
                self._extract_insured(value)
                return
            if "property" in label_l:
                self._extract_property(value)
                return

        if self.role == Role.POLICY_HEADER:
            self._extract_policy(line)
        elif self.role == Role.INSURED_BLOCK:
            self._extract_insured(line)
        elif self.role == Role.MAILING_BLOCK:
            self._extract_mailing(line)
        elif self.role == Role.PROPERTY_BLOCK:
            self._extract_property(line)

    def _extract_policy(self, line: str):
        if "policy_number" in self.fields:
            return

        if any(k in line.lower() for k in ["agent", "producer", "phone", "fax"]):
            return

        for t in re.findall(POLICY_RE, line):
            if valid_policy(t):
                self.fields["policy_number"] = {
                    "value": t.replace(" ", ""),
                    "confidence": 0.99,
                    "source": "policy_header",
                }
                return

    def _extract_insured(self, line: str):
        if "insured_name" in self.fields:
            return
        if valid_name(line):
            self.fields["insured_name"] = {
                "value": line,
                "confidence": 0.95,
                "source": "insured_block",
            }

    def _extract_mailing(self, line: str):
        if "mailing_address" in self.fields:
            return
        if valid_address(line):
            self.fields["mailing_address"] = {
                "value": line,
                "confidence": 0.93,
                "source": "mailing_block",
            }

    def _extract_property(self, line: str):
        if "property_address" in self.fields:
            return
        if valid_address(line):
            self.fields["property_address"] = {
                "value": line,
                "confidence": 0.96,
                "source": "property_block",
            }


def extract_fields(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    extractor = StatefulExtractor()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        extractor.update_role(line)
        extractor.extract(line)
    return extractor.fields
