# # Insurance Document Segmentation with STRICT FIELD-TO-SECTION ROUTING
# # Hardened for Intelligent Cascading Hybrid extraction
# # STEP 4 APPLIED: Confidence penalties for fallback extractions
# # PATCHED: header retention + insured/mail/property hardening (NO REMOVALS)

# import re
# from typing import List, Dict

# # ============================================================
# # CONFIDENCE PENALTY HELPER (STEP 4)
# # ============================================================

# def _penalize_confidence(base: float, reason: str) -> float:
#     penalties = {
#         "fallback": 0.30,
#         "loose": 0.15,
#         "semantic": 0.20,
#     }
#     return max(0.40, base - penalties.get(reason, 0.0))


# # ============================================================
# # SECTION DEFINITIONS (BUSINESS ANCHORS)
# # ============================================================

# SECTION_HEADERS = {
#     "insured_section": [
#         "named insured",
#         "insured name",
#         "policyholder",
#         "named insured and mailing address",
#         "customer",
#         "borrower",
#         "named insured", 
#     ],
#     "property_section": [
#         "location of insured property",
#         "insured property",
#         "property address",
#         "location of property",
#     ],
#     "mailing_section": [
#         "mailing address",
#         "mail address",
#     ],
#     "mortgage_section": [
#         "other interests",
#         "mortgage",
#         "mortgagee",
#         "loss payee",
#         "lender",
#     ],
#     "coverage_section": [
#         "coverages and limits",
#         "section i",
#         "coverage a",
#         "dwelling",
#     ],
#     "premium_section": [
#         "total premium",
#         "base policy premium",
#         "endorsement premium",
#         "premium summary",
#     ],
#     "agent_section": [
#         "sales rep",
#         "agent",
#         "producer",
#         "agency",
#         "broker",
#     ],
#     "carrier_section": [
#         "issued by",
#         "insurance company",
#         "carrier",
#         "underwritten by",
#     ],
#     "endorsement_section": [
#         "forms and endorsements",
#         "endorsement",
#         "form number",
#         "additional forms",
#     ],
# }

# # ============================================================
# # FIELD RULES (UI + SUMMARY)  🔒 PRESERVED
# # ============================================================

# FIELD_RULES = {
#     "HO": [
#         "carrier",
#         "policy_number",
#         "insured_name",
#         "property_address",
#         "mailing_address",
#         "loan_number",
#         "mortgage",
#         "effective_date",
#         "expiration_date",
#         "total_premium",
#     ],
#     "OTH": [
#         "carrier",
#         "policy_number",
#         "insured_name",
#         "property_address",
#         "loan_number",
#     ],
# }

# # ============================================================
# # SECTION DETECTION (STRICT, NON-LEAKING)
# # ============================================================

# def detect_sections(lines: List[str]) -> Dict[str, List[str]]:
#     sections: Dict[str, List[str]] = {}
#     current = None

#     for line in lines:
#         l = line.lower().strip()
#         new_section = None

#         for section, keywords in SECTION_HEADERS.items():
#             if any(k in l for k in keywords):
#                 new_section = section
#                 break

#         if new_section:
#             current = new_section
#             # ✅ FIX 1: keep header line instead of discarding
#             sections[current] = [line]
#             continue

#         if current and line.strip():
#             sections[current].append(line)

#     return sections

# # ============================================================
# # MAIN ENTRYPOINT
# # ============================================================

# def segregate_insurance_document(lines: List[str]) -> Dict:
#     sections = detect_sections(lines)
#     fields = {}

#     carrier_text = " ".join(sections.get("carrier_section", lines[:8]))
#     carrier = _extract_carrier(carrier_text)
#     if carrier:
#         fields["carrier"] = carrier

#     policy = _extract_policy_number(lines)
#     if policy:
#         fields["policy_number"] = policy

#     insured = _extract_insured_name(sections.get("insured_section", []))
#     if insured:
#         fields["insured_name"] = insured

#     # ✅ FIX 2: property address should NOT be blocked by endorsements
#     prop_addr = _extract_property_address(sections.get("property_section", []))
#     if prop_addr:
#         fields["property_address"] = prop_addr

#     mail_addr = _extract_mailing_address(sections.get("mailing_section", []))
#     if mail_addr:
#         fields["mailing_address"] = mail_addr

#     mortgage_text = " ".join(sections.get("mortgage_section", []))

#     loan = _extract_loan_number(mortgage_text)
#     if loan:
#         fields["loan_number"] = loan

#     mortgage = _extract_mortgage_name(mortgage_text)
#     if mortgage:
#         fields["mortgage"] = mortgage

#     coverage_text = " ".join(sections.get("coverage_section", []))
#     dwelling = _extract_currency(coverage_text)
#     if dwelling:
#         fields["dwelling_coverage"] = dwelling

#     premium_text = " ".join(sections.get("premium_section", []))
#     premium = _extract_currency(premium_text)
#     if premium:
#         fields["total_premium"] = premium

#     return {
#         "document_type": "OTH",
#         "policy_type": "UNK",
#         "fields": fields,
#         "field_errors": [],
#     }

# # ============================================================
# # EXTRACTION HELPERS (STEP 4 HARDENED)
# # ============================================================

# def _extract_carrier(text: str):
#     m = re.search(r'(AAA|STATE FARM|ALLSTATE|CSAA|FARMERS|PROGRESSIVE)', text, re.I)
#     if m:
#         return {"value": m.group(1).strip(), "confidence": 0.96}
#     return None


# def _extract_policy_number(lines):
#     for l in lines:
#         m = re.search(r'policy\s*number[:\s]+([A-Z0-9\-]{6,30})', l, re.I)
#         if m:
#             return {"value": m.group(1), "confidence": 0.97}
#     return None


# def _extract_insured_name(lines):
#     REJECT_WORDS = {
#         "insurance", "policy", "coverage", "company", "mortgage",
#         "loan", "address", "property", "endorsement", "section",
#         "agent", "producer", "broker", "holder", "interest",
#         "additional", "loss", "payee", "discount", "safe home",
#         "modernization", "claims", "payment plan", "premium",
#     }

#     for raw in lines:
#         raw = raw.strip()
#         l = raw.lower()

#         # ✅ FIX 3: block header-like lines
#         if raw.endswith(":") or ":" in raw:
#             continue

#         if any(w in l for w in REJECT_WORDS):
#             continue

#         if any(char.isdigit() for char in raw):
#             continue

#         # ✅ FIX 4: strip trailing date noise
#         raw = re.split(
#             r'\b(beginning|effective|since|policy period|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
#             raw,
#             flags=re.I
#         )[0].strip()

#         words = raw.split()
#         if not (2 <= len(words) <= 5):
#             continue

#         if len(raw) < 6 or len(raw) > 60:
#             continue

#         # RELAXED: allow mixed case OCR
#         return {"value": raw, "confidence": 0.95}

#     return None


# def _extract_property_address(lines):
#     STATE_RE = r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WI|WV|WY)\b'
#     ZIP_RE = r'\b\d{5}\b'

#     REJECT_WORDS = {
#         "po box", "p.o. box", "mailing", "form",
#         "endorsement", "section", "coverage",
#         "policy", "declaration"
#     }

#     for raw in lines:
#         raw = raw.strip()
#         l = raw.lower()

#         if any(w in l for w in REJECT_WORDS):
#             continue

#         if not any(char.isdigit() for char in raw):
#             continue

#         if not re.search(STATE_RE, raw):
#             continue

#         if not re.search(ZIP_RE, raw):
#             continue

#         if not re.search(r'\d+\s+[A-Za-z]', raw):
#             continue

#         return {"value": raw, "confidence": 0.95}

#     return None


# def _extract_mailing_address(lines):
#     for l in lines:
#         ll = l.lower()

#         # ✅ FIX 5: block policy-period contamination
#         if any(x in ll for x in ["beginning", "through", "effective", "policy period"]):
#             continue

#         if "po box" in ll or re.search(r'\d+\s+.*\b(st|ave|rd|dr|blvd|ln)\b', ll):
#             return {
#                 "value": l.strip(),
#                 "confidence": _penalize_confidence(0.92, "fallback")
#             }
#     return None


# def _extract_loan_number(text):
#     m = re.search(r'loan\s*number[:\s]+([A-Z0-9\-]{5,})', text, re.I)
#     if m:
#         return {"value": m.group(1), "confidence": 0.95}
#     return None


# def _extract_mortgage_name(text):
#     m = re.search(r'(GATEWAY|WELLS FARGO|CHASE|BANK OF AMERICA|MORTGAGE)', text, re.I)
#     if m:
#         return {
#             "value": m.group(1),
#             "confidence": _penalize_confidence(0.90, "fallback")
#         }
#     return None


# def _extract_currency(text):
#     m = re.search(r'\$\s*([\d,]{3,})', text)
#     if m:
#         return {
#             "value": f"${m.group(1)}",
#             "confidence": _penalize_confidence(0.90, "loose")
#         }
#     return None


import re
from typing import List, Dict

# ============================================================
# FIELD RULES (REQUIRED BY app.py / orchestrator)
# ============================================================

FIELD_RULES = {
    "HO": [
        "carrier",
        "policy_number",
        "insured_name",
        "mailing_address",
        "property_address",
        "mortgage",
        "loan_number",
        "effective_date",
        "expiration_date",
        "total_premium",
    ],
    "FLD": [
        "carrier",
        "policy_number",
        "insured_name",
        "property_address",
        "mortgage",
        "loan_number",
        "effective_date",
        "expiration_date",
    ],
    "INV": [
        "carrier",
        "policy_number",
        "insured_name",
        "balance_due",
        "issue_date",
        "remit_info",
    ],
    "OTH": [
        "carrier",
        "policy_number",
        "insured_name",
        "property_address",
        "loan_number",
    ],
}

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

    lock("carrier", extract_carrier(lines))
    lock("policy_number", extract_policy_number(lines))

    lock("insured_name", extract_insured_name(sections.get("insured", [])))
    lock("mailing_address", extract_mailing_address(sections.get("insured", [])))
    lock("property_address", extract_property_address(sections.get("property", [])))

    lock("mortgage", extract_mortgage(sections.get("mortgage", [])))
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
