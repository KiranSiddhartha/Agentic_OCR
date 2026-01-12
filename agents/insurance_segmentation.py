# agents/insurance_segmentation.py

import re
from difflib import SequenceMatcher
from agents.document_classifier import classify_document
from agents.policy_classifier import classify_policy
from typing import List
from agents.field_extraction_agent import extract_fields
from agents.value_normalizer import normalize_extracted_fields

# --------------------------------------------------
# FIELD RULES (Based on official requirements)
# --------------------------------------------------
FIELD_RULES = {
    "BIN": [
        "policy_number",
        "insured_name",
        "effective_date",
        "property_address"
    ],
    
    "COI": [
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
        "insurance_company",
        "property_address"
    ],
    
    "DOI": [
        "policy_number",
        "loan_number",
        "insured_name"
    ],
    
    "INV": [
        "balance_due",
        "due_date",
        "policy_number",
        "insured_name"
    ],
    
    "RNS": [
        "policy_number",
        "insured_name",
        "effective_date"
    ],
    
    "RNW": [
        "policy_number",
        "insured_name",
        "effective_date",
        "expiration_date",
        "balance_due",
        "invoice_number",
        "invoice_total"
    ],
    
    "CAN": [
        "policy_number",
        "insured_name",
        "cancellation_date",
        "effective_date"
    ],
    
    "FPN": [
        "loan_number",
        "property_address",
        "insured_name"
    ],
    
    "OTH": [
        "policy_number",
        "insured_name"
    ]
}

# --------------------------------------------------
# OCR FIXES (Comprehensive)
# --------------------------------------------------
OCR_FIXES = {
    # Policy
    r"\bpol1cy\b": "policy",
    r"\bp0licy\b": "policy",
    r"\bpolicv\b": "policy",
    r"\bpo1icy\b": "policy",
    
    # Insurance
    r"\blnsurance\b": "insurance",
    r"\binsuranee\b": "insurance",
    r"\binsur\s*ance\b": "insurance",
    
    # Number variants
    r"\bnomoer\b": "number",
    r"\bnumher\b": "number",
    r"\bnunber\b": "number",
    r"\bnurnber\b": "number",
    
    # Loan
    r"\bfoan\b": "loan",
    r"\bf0an\b": "loan",
    r"\bloam\b": "loan",
    
    # Property
    r"\bpropenty\b": "property",
    r"\bpropeny\b": "property",
    r"\bpropertv\b": "property",
    
    # Address
    r"\baddres\b": "address",
    r"\baddrass\b": "address",
    r"\baddressS\b": "address",
    r"\baddressss\b": "address",  # Added - from your doc
    
    # Premium
    r"\bpremiurn\b": "premium",
    r"\bpremom\b": "premium",
    r"\bpremlum\b": "premium",
    
    # Name
    r"\bnane\b": "name",
    r"\bnarne\b": "name",
    
    # Description
    r"\bdese\b": "desc",
    r"\bdesce\b": "desc",
    
    # Company
    r"\bcompanv\b": "company",
    
    # Mortgage
    r"\bmortqaqee\b": "mortgagee",
    r"\bmortqaee\b": "mortgagee"
}

# --------------------------------------------------
# UTILS
# --------------------------------------------------
def normalize_text(text: str) -> str:
    """Aggressive OCR normalization"""
    text = text.lower()
    
    for wrong_pattern, right in OCR_FIXES.items():
        text = re.sub(wrong_pattern, right, text, flags=re.I)
    
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fuzzy_match(a: str, b: str, threshold=0.70) -> bool:
    """Fuzzy string matching for OCR tolerance"""
    return SequenceMatcher(None, a, b).ratio() >= threshold


# --------------------------------------------------
# ENHANCED FIELD EXTRACTORS
# --------------------------------------------------

def extract_carrier(text):
    """Extract insurance carrier/company name"""
    patterns = [
        r"insurance\s*company\s*name?\s*[:\-]?\s*(.+?)(?:\n|customer)",
        r"insurance\s*provided\s*by\s*[:\-]?\s*(.+?)(?:\n|customer)",
        r"issued\s*by\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"carrier\s*name?\s*[:\-]?\s*(.+?)(?:\n|$)"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            company = m.group(1).strip()
            # Clean up extra info
            company = re.split(r'\s{2,}|customer|phone', company, flags=re.I)[0].strip()
            return company
    
    return None


def extract_policy_number(text, lines):
    """
    Enhanced policy number extraction
    Handles table-based layouts where label and value are separated
    """
    
    # Pattern 1: Label on line, value nearby
    for i, line in enumerate(lines):
        if "policy number" in line.lower():
            # Check same line
            nums = re.findall(r"\b\d{6,15}\b", line)
            if nums:
                return nums[-1]
            
            # Check next 3 lines
            for j in range(i + 1, min(i + 4, len(lines))):
                nums = re.findall(r"\b\d{6,15}\b", lines[j])
                if nums:
                    # Verify not a date
                    for num in nums:
                        if not re.match(r"\d{1,2}/\d{1,2}/\d{4}", num):
                            return num
    
    # Pattern 2: Standard labeled format
    patterns = [
        r"policy\s*(?:number|no|nunber)\s*[:\-]?\s*([a-z0-9\-\/]{6,25})",
        r"cert(?:ificate)?\s*[#\.]?\s*[:\-]?\s*([a-z0-9\-\/]{6,25})",
        r"\b(QSN\d{7,})\b",
        r"\b(QBE\d{7,})\b",
        r"\b([A-Z]{2,4}\d{7,})\b"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    
    # Pattern 3: Standalone 9-digit number (common format)
    # Look for 9-digit numbers that aren't dates or phones
    for line in lines:
        if "policy" in line.lower() or "number" in line.lower():
            nums = re.findall(r"\b(\d{9})\b", line)
            if nums:
                return nums[0]
    
    return None


def extract_loan_number(text):
    """Extract loan/reference/account number"""
    patterns = [
        r"loan\s*(?:number|no|#)?\s*[:\-]?\s*(\d{6,})",
        r"ln#\s*[:\-]?\s*(\d{6,})",
        r"reference\s*number\s*[:\-]?\s*(\d{6,})",
        r"account\s*number\s*[:\-]?\s*(\d{6,})"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1)
    
    return None


def extract_dates(text, lines):
    """
    Enhanced date extraction with context awareness
    Handles table layouts and various date formats
    """
    dates = {}
    
    # Pattern 1: Look for date labels
    date_labels = {
        "effective_date": [
            r"effective\s*date\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"policy\s*effective\s*date\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"beginning\s+(.+?)(?:\n|through)"
        ],
        "expiration_date": [
            r"expiration\s*date\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"through\s+(.+?)(?:\n|at\s+\d|$)"
        ],
        "cancellation_date": [
            r"cancellation\s*date\s*[:\-]?\s*(.+?)(?:\n|$)"
        ]
    }
    
    for date_type, patterns in date_labels.items():
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if m:
                date_str = m.group(1).strip()
                # Extract actual date from the string
                date_match = re.search(
                    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
                    date_str,
                    re.I
                )
                if date_match:
                    dates[date_type] = date_match.group(1)
                    break
    
    return dates


def extract_balance_due(text):
    """Extract balance/amount due"""
    patterns = [
        r"balance\s*due\s*[:\-]?\s*\$?\s*([0-9,]+\.\d{2})",
        r"amount\s*due\s*[:\-]?\s*\$?\s*([0-9,]+\.\d{2})",
        r"minimum\s*due\s*[:\-]?\s*\$?\s*([0-9,]+\.\d{2})",
        r"total\s*due\s*[:\-]?\s*\$?\s*([0-9,]+\.\d{2})"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1)
    
    return None


def extract_total_premium(text, lines):
    """
    Extract total premium with priority
    For Encompass-style declarations, look for "Total Residence Premium"
    """
    
    # Priority 1: Total Residence Premium
    m = re.search(r"total\s*residence\s*premium\s*\$?\s*([0-9,]+\.\d{2})", text, re.I)
    if m:
        return m.group(1)
    
    # Priority 2: Total Premium
    m = re.search(r"total\s*premium\s*\$?\s*([0-9,]+\.\d{2})", text, re.I)
    if m:
        return m.group(1)
    
    # Priority 3: Annual Premium
    m = re.search(r"annual\s*premium\s*\$?\s*([0-9,]+\.\d{2})", text, re.I)
    if m:
        return m.group(1)
    
    return None


def extract_invoice_number(text):
    """Extract invoice number"""
    m = re.search(r"invoice\s*(?:number|no|nunber)\s*[:\-]?\s*(\d{5,})", text, re.I)
    return m.group(1) if m else None


def extract_invoice_total(text):
    """Extract invoice total"""
    m = re.search(r"invoice\s*total\s*[:\-]?\s*\$?\s*([0-9,]+\.\d{2})", text, re.I)
    return m.group(1) if m else None


def extract_property_address(lines):
    """
    Extract property address (NOT mailing address or PO BOX)
    Enhanced for table-based layouts
    """
    for i, line in enumerate(lines):
        l = line.lower()
        
        # Skip mailing addresses and PO boxes
        if "mailing" in l or "po box" in l or "p.o. box" in l or "p o box" in l:
            continue
        
        # Look for "Coverage Detail for" pattern (Encompass-style)
        if "coverage detail for" in l:
            # Extract address after "for"
            m = re.search(r"coverage\s*detail\s*for\s+(.+?)(?:,\s*[A-Z]{2}\s+\d{5})?$", line, re.I)
            if m:
                addr = m.group(1).strip()
                # Look for full address with state/zip on same or next line
                full_match = re.search(
                    r"(\d+\s+.+?,\s*[A-Z]{2}\s+\d{5})",
                    line + " " + (lines[i+1] if i+1 < len(lines) else ""),
                    re.I
                )
                if full_match:
                    return full_match.group(1)
                return addr
        
        # Look for property address label
        if "property" in l and ("address" in l or "location" in l):
            # Check next few lines
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()
                
                # Must contain digits (street number)
                if any(c.isdigit() for c in candidate):
                    # Should contain state abbreviation
                    if re.search(r'\b[A-Z]{2}\b', candidate):
                        return candidate
    
    # Fallback: look for address pattern
    for line in lines:
        if "mailing" not in line.lower() and "po box" not in line.lower():
            m = re.search(
                r"\b\d{2,5}\s+[a-z0-9\s\.]+(FL|TX|CA|NY|NJ|NC|SC|GA|AL|AZ|AR|CO|CT|DE|IL|IN|KS|KY|LA|MA|MD|MI|MN|MO|MS|MT|NE|NV|NH|NM|ND|OH|OK|OR|PA|RI|SD|TN|UT|VA|VT|WA|WI|WV|WY)\s*\d{5}",
                line,
                re.I
            )
            if m:
                return m.group(0)
    
    return None


def extract_insured_name(lines):
    """
    Enhanced insured name extraction
    Handles table layouts where label and value are in different positions
    """
    
    for i, line in enumerate(lines):
        l = line.lower()
        
        # Skip lines that are clearly not names
        if any(x in l for x in ["page", "policy", "claim", "phone", "fax", "email"]):
            continue
        
        # Pattern 1: "Policyholder/Named Insured:" label
        if "policyholder" in l or "named insured" in l:
            # Check if name is on same line after colon
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    # Get text after colon
                    candidate = parts[1].strip()
                    # Remove any trailing labels or data
                    candidate = re.split(r"\s{2,}|policyholder since|policy number", candidate, flags=re.I)[0].strip()
                    
                    if candidate and len(candidate) > 3 and len(candidate.split()) >= 2:
                        # Verify it looks like a name (not a label)
                        if not any(x in candidate.lower() for x in ["since", "number", "period", "date"]):
                            return candidate
            
            # Check next lines for name
            for j in range(i + 1, min(i + 5, len(lines))):
                candidate = lines[j].strip()
                
                # Skip non-name content
                if any(x in candidate.lower() for x in [
                    "address", "policy", "number", "date", "invoice", "coverage", 
                    "premium", "since", "period", "mailing"
                ]):
                    continue
                
                # Check if looks like a name
                if len(candidate.split()) >= 2 and len(candidate) <= 60:
                    # Should not be all caps unless it's a real name
                    if candidate.isupper() or candidate.istitle():
                        return candidate
        
        # Pattern 2: "Customer Name" or "Insured Name"
        if "customer name" in l or "insured name" in l:
            parts = re.split(r":", line, maxsplit=1)
            if len(parts) == 2:
                candidate = parts[1].strip()
                candidate = re.split(r"\s{2,}", candidate)[0].strip()
                if candidate and len(candidate.split()) >= 2:
                    return candidate
    
    # Fallback: Look for name-like patterns (2-3 words, title case or uppercase)
    for line in lines:
        # Skip obvious non-name lines
        if any(x in line.lower() for x in [
            "policy", "address", "number", "premium", "invoice", "coverage",
            "page", "claim", "phone", "fax", "email", "company", "agent"
        ]):
            continue
        
        # Look for 2-3 word sequences that could be names
        words = line.split()
        if 2 <= len(words) <= 3 and len(line) <= 60:
            if line.isupper() or line.istitle():
                # Additional validation
                if all(len(w) >= 2 for w in words):
                    return line.strip()
    
    return None


def extract_insurance_company(lines):
    """Extract insurance company name"""
    for i, line in enumerate(lines):
        l = line.lower()
        if "insurance provided by" in l or "insurance company" in l:
            # Check same line
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    company = parts[1].strip()
                    # Clean up extra info
                    company = re.split(r'\s{2,}|customer|phone', company, flags=re.I)[0].strip()
                    return company
            
            # Check next line
            if i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                # Clean up extra info
                candidate = re.split(r'\s{2,}|customer|phone', candidate, flags=re.I)[0].strip()
                if candidate and "company" in candidate.lower():
                    return candidate
    
    return None

# ============================================================
# DOCUMENT TYPE DETECTION (Layer 1 – Structural + Keyword)
# ============================================================

def detect_document_type(lines: List[str]) -> str:
    """
    Detect document type using dominant insurance keywords.
    Returns normalized document codes.
    """

    text = " ".join(lines).lower()

    # ---------------- Cancellation / DOI ----------------
    if any(k in text for k in [
        "cancellation notice",
        "policy cancelled",
        "policy change",
        "deleted as loss payee",
        "notice of cancellation"
    ]):
        return "DOI"

    # ---------------- Renewal ----------------
    if any(k in text for k in [
        "renewal",
        "policy renewal",
        "renewed policy",
        "renewal notice"
    ]):
        return "RNW"

    # ---------------- Declaration ----------------
    if any(k in text for k in [
        "declarations",
        "policy declarations",
        "declaration page",
        "coverage summary"
    ]):
        return "DECLARATION"

    # ---------------- Invoice ----------------
    if any(k in text for k in [
        "invoice",
        "amount due",
        "total premium",
        "billing statement"
    ]):
        return "INV"

    # ---------------- Certificate ----------------
    if any(k in text for k in [
        "certificate of insurance",
        "certificate holder"
    ]):
        return "COI"

    return "OTH"

# --------------------------------------------------
# MAIN SEGMENTATION
# --------------------------------------------------
def segregate_insurance_document(lines):
    """
    Main document segmentation with enhanced classification
    """
    raw_text = " ".join(lines)
    clean_text = normalize_text(raw_text)

    # Classify using updated classifiers
    document_type = classify_document(lines)
    policy_type = classify_policy(lines)

    # ========================================
    # DOCUMENT-SPECIFIC POLICY RULES
    # ========================================
    
    # Special handling for invoice + renewal
    if "invoice" in clean_text and "renewal" in clean_text:
        if document_type in ["INV", "OTH"]:
            document_type = "RNW"

    # 🔥 BUSINESS RULE: Cancellation/DOI/Reinstatement documents
    # Policy type should be UNK for these document types
    if document_type in ["CAN", "DOI", "RNS"]:
        policy_type = "UNK"
    
    # Policy inference for FPN (force placed = flood)
    if policy_type == "UNK" and document_type == "FPN":
        policy_type = "FLD"

    # Extract fields based on document type
    extracted = {}
    errors = []

    required_fields = FIELD_RULES.get(document_type, FIELD_RULES["OTH"])

    for field in required_fields:
        val = None
        
        if field == "carrier":
            val = extract_carrier(clean_text)
        elif field == "policy_number":
            val = extract_policy_number(clean_text, lines)
        elif field == "loan_number":
            val = extract_loan_number(clean_text)
        elif field == "insured_name":
            val = extract_insured_name(lines)
        elif field == "property_address":
            val = extract_property_address(lines)
        elif field == "insurance_company":
            val = extract_insurance_company(lines)
        elif field == "balance_due":
            val = extract_balance_due(clean_text)
        elif field == "invoice_number":
            val = extract_invoice_number(clean_text)
        elif field == "invoice_total":
            val = extract_invoice_total(clean_text)
        elif field == "total_premium":
            val = extract_total_premium(clean_text, lines)
        elif field in ["effective_date", "expiration_date", "cancellation_date", "due_date", "issue_date"]:
            dates = extract_dates(clean_text, lines)
            val = dates.get(field)
        
        extracted[field] = val
        if not val:
            errors.append(f"{field} missing")

    return {
        "policy_type": policy_type,
        "document_type": document_type,
        "fields": extracted,
        "field_errors": errors
    }