# Insurance Segmentation Module - CLEAN ARCHITECTURE VERSION
# Proper segregation of document types and policy types with field rules

import re
from typing import List, Dict, Optional, Set

# ============================================================
# VALID DOCUMENT TYPES (Structural)
# ============================================================

VALID_DOC_TYPES = {
    "BIN",  # Binder
    "COI",  # Certificate of Insurance
    "DOI",  # Deletion of Interest
    "INV",  # Invoice
    "RNS",  # Reinstatement
    "RNW",  # Renewal/Declarations
    "CAN",  # Cancellation
    "OTH",  # Other
}

# ============================================================
# POLICY TYPES
# ============================================================

# Coverage Types
COVERAGE_TYPES = {
    "AUTO",  # Automobile
    "ERQ",   # Earthquake
    "FIR",   # Fire / Dwelling Fire
    "FLD",   # Flood
    "HAZ",   # Hazard / Commercial Property
    "HO",    # Homeowners
    "HO6",   # Condo
    "LL",    # Landlord
    "UO",    # Unit Owner
    "WND",   # Windstorm
}

# Cancellation Subtypes (Reasons)
CANCELLATION_SUBTYPES = {
    "BREQ",  # Borrower Request
    "NPAY",  # Non-Payment
    "NRNW",  # Non-Renewal
    "UNWR",  # Underwriting
    "CEL",   # Generic Cancellation
}

ALL_POLICY_TYPES = COVERAGE_TYPES | CANCELLATION_SUBTYPES | {"OTH"}

# ============================================================
# FIELD RULES BY DOCUMENT TYPE
# ============================================================

# ============================================================
# BASE DOCUMENT FIELDS (strict per-document-type base)
# These are the MINIMUM fields for each document type.
# Policy-type expansion adds fields ON TOP of these.
# ============================================================

FIELD_RULES = {
    "CAN": {
        # Base = 5 fields
        "carrier_name",
        "policy_number",
        "insured_name",
        "cancellation_date",
        "cancellation_reason",
    },
    "RNW": {
        # Base = 5 fields
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
    },
    "INV": {
        # Base = 6 fields
        "carrier_name",
        "policy_number",
        "insured_name",
        "balance_due",
        "issue_date",
        "remit_info",
    },
    "DOI": {
        # Base = 3 fields
        "policy_number",
        "mortgage_company",
        "loan_number",
    },
    "RNS": {
        # Base = 5 fields (NO expansion for any policy type)
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
    },
    "COI": {
        # Base = 6 fields (NO expansion for any policy type)
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
    },
    "BIN": {
        # Base = 6 fields (NO expansion for any policy type)
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
    },
    "OTH": {
        # Base = 5 fields (NO expansion for any policy type)
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "loan_number",
    },
}

# ============================================================
# FIELD RULES BY POLICY TYPE
# ============================================================

# ============================================================
# POLICY-TYPE EXPANSION FIELDS
# These are the ADDITIONAL fields added on top of the document
# base when a specific policy type is detected.
# Only CAN, RNW, INV, DOI expand — RNS, COI, BIN, OTH do NOT.
# ============================================================

# --- CAN EXPANSION (base=5) ---
# +2 fields: HO, FLD, FIR, BREQ, NPAY, NRNW, UNWR
# +1 field:  HAZ, HO6, LL, WND, ERQ
# +0 fields: AUTO, UO, CEL, OTH
CAN_EXPANSION = {
    "HO":   {"property_address", "mortgage_company"},         # 5+2=7
    "FLD":  {"property_address", "mortgage_company"},         # 5+2=7
    "FIR":  {"property_address", "mortgage_company"},         # 5+2=7
    "HAZ":  {"property_address"},                             # 5+1=6
    "HO6":  {"property_address"},                             # 5+1=6
    "LL":   {"property_address"},                             # 5+1=6
    "WND":  {"property_address"},                             # 5+1=6
    "ERQ":  {"property_address"},                             # 5+1=6
    "AUTO": set(),                                            # 5+0=5
    "UO":   set(),                                            # 5+0=5
    "BREQ": {"property_address", "mortgage_company"},         # 5+2=7
    "NPAY": {"property_address", "mortgage_company"},         # 5+2=7
    "NRNW": {"property_address", "mortgage_company"},         # 5+2=7
    "UNWR": {"property_address", "mortgage_company"},         # 5+2=7
    "CEL":  set(),                                            # 5+0=5
    "OTH":  set(),                                            # 5+0=5
}

# --- RNW EXPANSION (base=5) ---
# +5 fields: HO  (property_address, mailing_address, mortgage_company, loan_number, total_premium)
# +4 fields: FIR (property_address, mortgage_company, loan_number, total_premium)
# +3 fields: FLD (property_address, mortgage_company, loan_number)
# +3 fields: HO6 (property_address, mailing_address, total_premium)
# +2 fields: HAZ, LL, WND, ERQ (property_address, total_premium)
# +1 field:  AUTO (total_premium)
# +0 fields: UO, BREQ, NPAY, NRNW, UNWR, CEL, OTH
RNW_EXPANSION = {
    "HO":   {"property_address", "mailing_address", "mortgage_company", "loan_number", "total_premium"},  # 5+5=10
    "FLD":  {"property_address", "mortgage_company", "loan_number"},                                       # 5+3=8
    "FIR":  {"property_address", "mortgage_company", "loan_number", "total_premium"},                      # 5+4=9
    "HAZ":  {"property_address", "total_premium"},                                                         # 5+2=7
    "HO6":  {"property_address", "mailing_address", "total_premium"},                                      # 5+3=8
    "LL":   {"property_address", "total_premium"},                                                         # 5+2=7
    "WND":  {"property_address", "total_premium"},                                                         # 5+2=7
    "ERQ":  {"property_address", "total_premium"},                                                         # 5+2=7
    "AUTO": {"total_premium"},                                                                             # 5+1=6
    "UO":   set(),                                                                                         # 5+0=5
    "BREQ": set(),                                                                                         # 5+0=5
    "NPAY": set(),                                                                                         # 5+0=5
    "NRNW": set(),                                                                                         # 5+0=5
    "UNWR": set(),                                                                                         # 5+0=5
    "CEL":  set(),                                                                                         # 5+0=5
    "OTH":  set(),                                                                                         # 5+0=5
}

# --- INV EXPANSION (base=6) ---
# +1 field: HO, FLD, FIR, HAZ, HO6, LL, WND, ERQ (property_address)
# +0 fields: AUTO, UO, BREQ, NPAY, NRNW, UNWR, CEL, OTH
INV_EXPANSION = {
    "HO":   {"property_address"},   # 6+1=7
    "FLD":  {"property_address"},   # 6+1=7
    "FIR":  {"property_address"},   # 6+1=7
    "HAZ":  {"property_address"},   # 6+1=7
    "HO6":  {"property_address"},   # 6+1=7
    "LL":   {"property_address"},   # 6+1=7
    "WND":  {"property_address"},   # 6+1=7
    "ERQ":  {"property_address"},   # 6+1=7
    "AUTO": set(),                  # 6+0=6
    "UO":   set(),                  # 6+0=6
    "BREQ": set(),                  # 6+0=6
    "NPAY": set(),                  # 6+0=6
    "NRNW": set(),                  # 6+0=6
    "UNWR": set(),                  # 6+0=6
    "CEL":  set(),                  # 6+0=6
    "OTH":  set(),                  # 6+0=6
}

# --- DOI EXPANSION (base=3) ---
# +1 field: HO, FLD (property_address)
# +0 fields: all others
DOI_EXPANSION = {
    "HO":   {"property_address"},   # 3+1=4
    "FLD":  {"property_address"},   # 3+1=4
    "FIR":  set(),                  # 3+0=3
    "HAZ":  set(),                  # 3+0=3
    "HO6":  set(),                  # 3+0=3
    "LL":   set(),                  # 3+0=3
    "WND":  set(),                  # 3+0=3
    "ERQ":  set(),                  # 3+0=3
    "AUTO": set(),                  # 3+0=3
    "UO":   set(),                  # 3+0=3
    "BREQ": set(),                  # 3+0=3
    "NPAY": set(),                  # 3+0=3
    "NRNW": set(),                  # 3+0=3
    "UNWR": set(),                  # 3+0=3
    "CEL":  set(),                  # 3+0=3
    "OTH":  set(),                  # 3+0=3
}

# Master expansion lookup (only expandable doc types)
EXPANSION_MATRIX = {
    "CAN": CAN_EXPANSION,
    "RNW": RNW_EXPANSION,
    "INV": INV_EXPANSION,
    "DOI": DOI_EXPANSION,
}

# NO-EXPANSION doc types — always return base only
NO_EXPANSION_DOCS = {"RNS", "COI", "BIN", "OTH"}

# Legacy compatibility alias
POLICY_FIELD_RULES = {
    "HO": {"carrier_name", "policy_number", "insured_name", "property_address",
            "mailing_address", "loan_number", "mortgage_company",
            "effective_date", "expiration_date", "total_premium"},
    "FLD": {"carrier_name", "policy_number", "insured_name", "property_address",
            "loan_number", "mortgage_company", "effective_date", "expiration_date"},
    "AUTO": {"carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date", "total_premium"},
    "FIR": {"carrier_name", "policy_number", "insured_name", "property_address",
            "effective_date", "expiration_date", "total_premium",
            "mortgage_company", "loan_number"},
    "WND": {"carrier_name", "policy_number", "insured_name", "property_address",
            "effective_date", "expiration_date", "total_premium"},
    "ERQ": {"carrier_name", "policy_number", "insured_name", "property_address",
            "effective_date", "expiration_date", "total_premium"},
    "HO6": {"carrier_name", "policy_number", "insured_name", "property_address",
            "mailing_address", "effective_date", "expiration_date", "total_premium"},
    "LL": {"carrier_name", "policy_number", "insured_name", "property_address",
           "effective_date", "expiration_date", "total_premium"},
    "HAZ": {"carrier_name", "policy_number", "insured_name", "property_address",
            "effective_date", "expiration_date", "total_premium"},
    "UO": {"carrier_name", "policy_number", "insured_name",
           "effective_date", "expiration_date"},
    "BREQ": {"carrier_name", "policy_number", "insured_name", "property_address",
             "mortgage_company", "loan_number", "effective_date", "expiration_date",
             "cancellation_date", "cancellation_reason"},
    "NPAY": {"carrier_name", "policy_number", "insured_name", "property_address",
             "mortgage_company", "loan_number", "effective_date", "expiration_date",
             "cancellation_date", "cancellation_reason"},
    "NRNW": {"carrier_name", "policy_number", "insured_name", "property_address",
             "mortgage_company", "loan_number", "effective_date", "expiration_date",
             "cancellation_date", "cancellation_reason"},
    "UNWR": {"carrier_name", "policy_number", "insured_name", "property_address",
             "mortgage_company", "loan_number", "effective_date", "expiration_date",
             "cancellation_date", "cancellation_reason"},
    "CEL": {"carrier_name", "policy_number", "insured_name", "property_address",
            "mortgage_company", "loan_number", "effective_date", "expiration_date",
            "cancellation_date", "cancellation_reason"},
    "OTH": {"carrier_name", "policy_number", "loan_number"},
}

# ============================================================
# FIELD SELECTION LOGIC - DETERMINISTIC MATRIX
# ============================================================

def get_allowed_fields(
    document_type: str,
    policy_type: Optional[str] = None
) -> Set[str]:
    """
    Determine allowed fields based on document and policy type.

    DETERMINISTIC MATRIX RULES (128 combinations):
    ─────────────────────────────────────────────────
    • RNS, COI, BIN, OTH → base fields ONLY (no expansion)
    • CAN, RNW, INV, DOI → base fields + policy-type expansion
    • No dynamic merging, no intersection, no union heuristics
    • All 128 combinations produce exact, auditable field counts

    Returns: Set of allowed field names for the given combination.
    """
    # Get base document fields (always present)
    base_fields: Set[str] = set(FIELD_RULES.get(document_type, set()))

    # No-expansion document types — return base only regardless of policy
    if document_type in NO_EXPANSION_DOCS:
        return base_fields

    # Expandable document types — look up expansion matrix
    if document_type in EXPANSION_MATRIX and policy_type:
        expansion = EXPANSION_MATRIX[document_type].get(policy_type, set())
        return base_fields | expansion

    # Fallback: unknown policy type → base only
    return base_fields

# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

def validate_document_type(doc_type: str) -> bool:
    """Check if document type is valid"""
    return doc_type in VALID_DOC_TYPES


def validate_policy_type(policy_type: str) -> bool:
    """Check if policy type is valid (coverage or cancellation subtype)"""
    return policy_type in ALL_POLICY_TYPES


def is_coverage_type(policy_type: str) -> bool:
    """Check if policy type is a coverage type"""
    return policy_type in COVERAGE_TYPES


def is_cancellation_subtype(policy_type: str) -> bool:
    """Check if policy type is a cancellation subtype (reason)"""
    return policy_type in CANCELLATION_SUBTYPES

# ============================================================
# SECTION DEFINITIONS (OWNERSHIP MODEL)
# ============================================================

SECTION_HEADERS = {
    "insured": [
        "named insured",
        "insured name",
        "insured mailing name and address",
        "policyholder",
    ],
    "property": [
        "location of insured property",
        "coverage detail for",
        "property location",
        "address:",
    ],
    "mortgage": [
        "mortgagee",
        "other interests",
        "loss payee",
        "lender",
    ],
    "premium": [
        "total premium",
        "base policy premium",
        "endorsement premium",
    ],
    "carrier": [
        "underwritten by",
        "insurance company",
        "issued by",
    ],
}

# ============================================================
# CONFIDENCE HELPERS
# ============================================================

def _confidence(base: float, penalty: float = 0.0) -> float:
    return round(max(0.40, base - penalty), 2)

# ============================================================
# SECTION DETECTION (STRICT)
# ============================================================

def detect_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None

    for line in lines:
        ll = line.lower().strip()
        new_section = None

        for section, headers in SECTION_HEADERS.items():
            if any(h in ll for h in headers):
                new_section = section
                break

        if new_section:
            current = new_section
            sections.setdefault(current, []).append(line)
            continue

        if current and line.strip():
            sections[current].append(line)

    return sections

# ============================================================
# MAIN ENTRYPOINT (LOCKING ENABLED)
# ============================================================

def segregate_insurance_document(lines: List[str]) -> Dict:
    sections = detect_sections(lines)
    fields: Dict[str, Dict] = {}

    def lock(name: str, value: Dict):
        if name not in fields:
            fields[name] = value

    lock("carrier_name", extract_carrier(lines))
    lock("policy_number", extract_policy_number(lines))

    lock("insured_name", extract_insured_name(sections.get("insured", [])))
    lock("mailing_address", extract_mailing_address(sections.get("insured", [])))
    lock("property_address", extract_property_address(sections.get("property", [])))

    lock("mortgage_company", extract_mortgage(sections.get("mortgage", [])))
    lock("loan_number", extract_loan_number(sections.get("mortgage", [])))

    lock("effective_date", extract_effective_date(lines))
    lock("expiration_date", extract_expiration_date(lines))
    lock("issue_date", extract_issue_date(lines))
    lock("total_premium", extract_total_premium(sections.get("premium", [])))
    lock("balance_due", extract_balance_due(lines))
    lock("remit_info", extract_remit_info(lines))

    return {
        "fields": fields,
        "errors": [],
    }

# ============================================================
# EXTRACTION HELPERS (SECTION-OWNED)
# ============================================================

def extract_carrier(lines):
    for l in lines[:12]:
        m = re.search(r'\b(AAA|ERIE|ENCOMPASS|FARMERS|STATE FARM|ALLSTATE|CSAA)\b', l, re.I)
        if m:
            return {"value": m.group(1).upper(), "confidence": _confidence(0.97)}
    return None


def extract_policy_number(lines):
    for l in lines:
        m = re.search(r'policy\s*number[:\s]+([A-Z0-9\-]+)', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": _confidence(0.97)}
    return None


def extract_insured_name(lines):
    BLOCK = {
        "policy", "coverage", "summary", "notice",
        "interest of named insured", "such premises",
    }

    for i, l in enumerate(lines):
        for cand in lines[i + 1:i + 4]:
            name = cand.strip()
            nl = name.lower()

            if not name or ":" in name:
                continue
            if any(b in nl for b in BLOCK):
                continue
            if any(c.isdigit() for c in name):
                continue
            if name.endswith("."):
                continue
            if 2 <= len(name.split()) <= 6:
                return {"value": name, "confidence": _confidence(0.96)}
    return None


def extract_mailing_address(lines):
    for l in lines:
        ll = l.lower()
        if "po box" in ll or re.search(r'\d+.*\b[A-Z]{2}\b.*\d{5}', l):
            return {"value": l.strip(), "confidence": _confidence(0.95)}
    return None


def extract_property_address(lines):
    for l in lines:
        ll = l.lower()
        if "po box" in ll:
            continue
        if re.search(r'\d+.*\b[A-Z]{2}\b.*\d{5}', l):
            return {"value": l.strip(), "confidence": _confidence(0.96)}
    return None


def extract_mortgage(lines):
    for l in lines:
        ll = l.lower()
        if any(k in ll for k in ["mortgage", "bank", "lending", "isaoa", "atima"]):
            if not l.strip().endswith(".") and len(l.split()) >= 2:
                return {"value": l.strip(), "confidence": _confidence(0.95, 0.10)}
    return None


def extract_loan_number(lines):
    for l in lines:
        m = re.search(r'loan\s*number[:\s]+([A-Z0-9\-]+)', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": _confidence(0.95)}
    return None


def extract_effective_date(lines):
    for l in lines:
        if "policy effective date" in l.lower():
            return {"value": l.split(":")[-1].strip(), "confidence": _confidence(0.98)}
    for l in lines:
        m = re.search(r'policy period.*?(\d{2}/\d{2}/\d{4})', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": _confidence(0.96)}
    return None


def extract_expiration_date(lines):
    for l in lines:
        m = re.search(r'policy period.*?to\s*(\d{2}/\d{2}/\d{4})', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": _confidence(0.96)}
    return None


def extract_issue_date(lines):
    for l in lines:
        if "processed on" in l.lower():
            return {"value": l.split(":")[-1].strip(), "confidence": _confidence(0.90)}
    return None


def extract_total_premium(lines):
    for l in lines:
        m = re.search(r'\$\s*([\d,]{3,})', l)
        if m:
            return {"value": f"${m.group(1)}", "confidence": _confidence(0.90, 0.15)}
    return None


def extract_balance_due(lines):
    text = " ".join(lines)
    m = re.search(r'(amount due|balance due)\s*\$([\d,]+)', text, re.I)
    if m:
        return {"value": f"${m.group(2)}", "confidence": _confidence(0.92)}
    return None


def extract_remit_info(lines):
    for l in lines:
        if l.lower().startswith("mail to"):
            return {"value": l.strip(), "confidence": _confidence(0.93)}
    return None