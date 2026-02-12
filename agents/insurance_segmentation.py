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
    "UNK",  # Unknown
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

ALL_POLICY_TYPES = COVERAGE_TYPES | CANCELLATION_SUBTYPES | {"UNK"}

# ============================================================
# FIELD RULES BY DOCUMENT TYPE
# ============================================================

FIELD_RULES = {
    "RNW": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mailing_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "FLD": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
    },
    "INV": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "balance_due",
        "issue_date",
        "remit_info",
    },
    "CAN": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
        "property_address",  # ADDED - often needed
        "mortgage_company",  # ADDED - often needed
    },
    "DOI": {
        "carrier_name",
        "policy_number",
        "mortgage_company",
        "loan_number",
        "insured_name",  # ADDED - usually present
        "property_address",  # ADDED - usually present
    },
    "RNS": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
    },
    "COI": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
    },
    "BIN": {
        "carrier_name",
        "insured_name",
        "property_address",
        "effective_date",
    },
    "OTH": {
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

POLICY_FIELD_RULES = {
    # COVERAGE TYPES
    "HO": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mailing_address",
        "loan_number",
        "mortgage_company",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "FLD": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "loan_number",
        "mortgage_company",
        "effective_date",
        "expiration_date",
    },
    "AUTO": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "FIR": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
        "total_premium",
        "mortgage_company",  # ADDED - fire policies often have mortgagee
        "loan_number",  # ADDED
    },
    "WND": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "ERQ": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "HO6": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mailing_address",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "LL": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "HAZ": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "effective_date",
        "expiration_date",
        "total_premium",
    },
    "UO": {
        "carrier_name",
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
    },
    
    # CANCELLATION SUBTYPES (REASONS)
    "BREQ": {
        # Borrower Request cancellation
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
    },
    "NPAY": {
        # Non-Payment cancellation
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
    },
    "NRNW": {
        # Non-Renewal
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
    },
    "UNWR": {
        # Underwriting cancellation
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
    },
    "CEL": {
        # Generic cancellation
        "carrier_name",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage_company",
        "loan_number",
        "effective_date",
        "expiration_date",
        "cancellation_date",
        "cancellation_reason",
    },
    
    # UNKNOWN
    "UNK": {
        "carrier_name",
        "policy_number",
        "loan_number",
    },
}

# ============================================================
# FIELD SELECTION LOGIC - IMPROVED
# ============================================================

def get_allowed_fields(
    document_type: str,
    policy_type: Optional[str] = None
) -> Set[str]:
    """
    Determine allowed fields based on document and policy type.

    Improved Rules:
    - RNW / HO / HAZ → UNION of document + policy rules
    - CAN / DOI → UNION instead of intersection (more permissive)
    - Others → document rules only
    
    Rationale: Intersection was too restrictive and caused field loss.
    For CAN and DOI documents, we want ALL relevant fields from both
    document and policy perspectives.
    """
    doc_fields: Set[str] = FIELD_RULES.get(document_type, set())
    policy_fields: Set[str] = (
        POLICY_FIELD_RULES.get(policy_type, set())
        if policy_type
        else set()
    )

    if document_type in {"RNW", "HO", "HAZ"}:
        return doc_fields | policy_fields

    # Strict intersection for CAN/DOI, but with fallback
    if document_type in {"CAN", "DOI"}:
        if not policy_fields:
            # Policy type unknown or not in our list - use doc fields only
            return doc_fields
        
        intersection = doc_fields & policy_fields
        
        if len(intersection) < 3:
            # Intersection too small - likely a mismatch, use union instead
            print(f"WARNING: Small intersection for {document_type}-{policy_type}, using union")
            return doc_fields | policy_fields
        
        return intersection

    return doc_fields

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