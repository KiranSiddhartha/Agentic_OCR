# Stage 1 – Stateful, Role-Anchored Deterministic Extraction
  
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
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{1,2},?\s*\d{4}",
    re.I
)
# Abbreviated month names: NOV 09 2021, DEC 1 2022, OCT-05-2021, etc.
DATE_ABBREV_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-]+\d{1,2}[\s,\-]+\d{4}\b",
    re.I
)
# Also match "OCT-05-2021 to OCT-05-2022" style date ranges
DATE_ABBREV_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-]+\d{1,2}[\s,\-]+\d{4})"
    r"\s+to\s+"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-]+\d{1,2}[\s,\-]+\d{4})",
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
    re.compile(r"^\d{9,16}$"),  # 2004939477, 99047002652020 (NFIP flood 14-digit)
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
    "cert. #", "cert #", "cert. no",  # QBE: "CERT. #: QSN4481303"
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
    "customer name",  # QBE invoice: "Customer Name: Dashiell Lopez"
}

# CRITICAL: Terms that should NOT be captured as insured names
BAD_INSURED_TERMS = {
    # Mortgagee-related (most common error)
    "mortgagee", "first mortgagee", "second mortgagee", "third mortgagee",
    "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
    "loss payee", "lienholder", "lender",
    "isaoa", "atima", "isaoa atima", "isaoa/atima",
    "lien holder", "1st mortgagee copy",
    
    # Financial institutions / Banks (CRITICAL - not insured names)
    "first horizon bank", "first horizon",
    "wells fargo", "chase bank", "bank of america",
    "us bank", "pnc bank", "citizens bank",
    "huntington bank", "regions bank",
    "orchid underwriters", "attn:",  # Invoice headers
    "attn", "attention",
    
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
    # Flood packet headings / OCR variants
    "direct rating information",
    "drect ratng informaton",
    "nfip direct rating information",
    "nfip drect ratng informaton",
    "additional interest information",
    "mortgagees additional interest information",
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
    "description of property",  # Adirondack: "DESCRIPTION OF PROPERTY:"
    "location of residence premises",  # Travelers Homesaver
}

# Property labels for inline extraction (Label: Value format)
PROPERTY_INLINE_LABELS = {
    "property address", "risk location",
    "location of insured property",
    "premises address", "property location",
    "property insured",  # ADDED for "Property Insured: 4616 HERITAGE RD"
    "location",  # State Farm: "Location: <address>"
    "located at",  # Adirondack: "LOCATED AT: 908 Meadow Ln"
    "description of property",  # Adirondack: "DESCRIPTION OF PROPERTY: LOCATED AT: addr"
    "location of residence premises",  # Travelers Homesaver
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

# Patterns that look like mortgage triggers but are actually service centers or footer text
MORTGAGE_FALSE_POSITIVES = {
    "lender relations center",
    "mortgagee relations center",
    "mortgage relations center",
    "mortgagee copy",       # Footer: "Mortgagee Copy Page 1 of 3"
    "continued on next",    # Footer: "Continued on next page Mortgagee Copy"
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
    "loan#",  # Common in flood policies: "LOAN# 1041640358" or "Loan#: 0580239576"
}

DATE_LABELS_EFFECTIVE = {
    "effective date", "policy effective date",
    "coverage begins", "term start date",
    "effective from",  # QBE: "EFFECTIVE FROM 10/05/2021 TO 10/05/2022"
    # NOTE: "change effective date" intentionally excluded — it captures endorsement
    # change dates (e.g., "Change Effective Date: 07-09-20") which are NOT the
    # policy effective date.  The real effective date comes from Policy Period.
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
    
    # CRITICAL: Strip OCR-garbled label prefixes from names
    # E.g., "NANEAND ADDRESO OCTHEINSURED Dashiell Lopez" → "Dashiell Lopez"
    # Look for the transition from garbled uppercase noise to actual name
    # Strategy: if the text contains a recognizable name pattern at the end,
    # strip the garbled prefix
    garbled_label_patterns = [
        # Garbled "NAME AND ADDRESS OF THE INSURED" variations
        r"(?i)^.*?(?:NAMEAND|NANEAND|NAMEANDADDRESS|NANDADDRES|ADDRESO|OCTHE|OFTHE)"
        r"(?:INSURED|INSUREO|LNSURED)?\s*",
        # Garbled "INSURED NAME AND ADDRESS" variations
        r"(?i)^.*?(?:INSUREDNAME|INSUREONAME|INSUREDMAILING)\s*",
        # Garbled "INSURED LOCATION" / "COVERED BY THIS POLICY"
        r"(?i)^.*?(?:INSUREDLOCATION|COVEREDBYTHIS)\s*(?:POLICY)?\s*",
    ]
    for pat in garbled_label_patterns:
        m = re.match(pat, v)
        if m and m.end() < len(v):
            remainder = v[m.end():].strip()
            if remainder and len(remainder) > 3:
                v = remainder
    
    # Handle "LASTNAME, FIRSTNAME" format BUT NOT company names with comma
    # Don't swap if it contains entity suffixes
    # NOTE: We preserve the original LASTNAME, FIRSTNAME order to match document format
    # (DOI/letter docs address mortgagee as "GILLIS, DAVID" not "DAVID GILLIS")
    if "," in v and v.count(",") == 1:
        has_entity = any(w in v.lower() for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
        if not has_entity:
            parts = [p.strip() for p in v.split(",") if p.strip()]
            if len(parts) == 2 and not any(c.isdigit() for c in v):
                # Keep as "LASTNAME, FIRSTNAME" — do not swap
                pass  # v is already in correct format
    
    # Normalize OCR mixed-case corruption: "GIlLIS" / "DaVId" → uppercase
    # OCR often produces garbled case mid-word; detect by looking for
    # lowercase letters appearing after uppercase within the same word
    words = v.split()
    normalized_words = []
    for word in words:
        # Strip trailing punctuation for detection
        core = word.rstrip('.,;')
        if re.search(r'[A-Z][a-z][A-Z]|[a-z][A-Z]', core):
            # Mixed-case corruption — uppercase the whole word
            normalized_words.append(word.upper())
        else:
            normalized_words.append(word)
    v = " ".join(normalized_words)

    return v.strip()


def _is_low_quality_name(v: str) -> bool:
    """
    Heuristic for OCR-damaged names that should be replaced if a better
    labeled candidate exists (e.g., "Daael Lome?").
    """
    if not v:
        return True
    s = v.strip()
    if not s:
        return True
    if "?" in s:
        return True
    if any(ch.isdigit() for ch in s):
        return True
    # Too little alphabetic signal for a real name.
    alpha = sum(ch.isalpha() for ch in s)
    if alpha < 4:
        return True
    return False


def _override_insured_from_customer_label(lines: List[str], fields: Dict) -> None:
    """
    For invoice-like docs, prefer explicit "Customer Name" labels when
    current insured_name is missing or clearly OCR-damaged.
    """
    current = fields.get("insured_name", {})
    current_val = current.get("value", "") if isinstance(current, dict) else ""
    if current_val and not _is_low_quality_name(current_val):
        return

    for i, line in enumerate(lines):
        ll = line.lower()
        if "customer name" not in ll:
            continue

        candidate = ""
        if ":" in line:
            _, _, right = line.partition(":")
            candidate = _normalize_name(right)
        elif i + 1 < len(lines):
            candidate = _normalize_name(lines[i + 1])

        if candidate and _looks_like_name(candidate):
            fields["insured_name"] = {
                "value": candidate,
                "confidence": 0.93,
                "source": "stage1_customer_name_label",
            }
            return


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


def _is_garbled_label(text: str) -> bool:
    """
    Detect OCR-garbled label text that should NOT be treated as a name or value.
    Fax/scanned documents produce garbled text like:
      "NANEAND ADDRESO OCTHEINSURED" = "NAME AND ADDRESS OF THE INSURED"
      "BOWARE QSE SPECATY" = garbled carrier header noise
    
    Strategy: Use fuzzy matching against known label fragments.
    If the text is mostly composed of garbled versions of known labels, reject it.
    """
    from difflib import SequenceMatcher
    
    ll = text.lower().strip()
    
    # Quick check: if it contains recognizable label fragments, it's probably garbled
    _GARBLED_LABEL_FRAGMENTS = [
        # Garbled versions of common labels (OCR errors on fax documents)
        "nameand", "naneand", "addreso", "octhe", "ofthe",
        "theinsured", "insuredname", "namedinsured",
        "policyno", "policynumber", "policynum",
        "addressof", "addressofthe", "nameandaddress",
        "coverageforms", "coverageform",
        "declarationpage", "declarationspage",
        # No-space merges of common label words
        "insuredlocation", "propertylocation", "propertyaddress",
        "policyperiod", "effectivedate", "expirationdate",
        "mortgagecompany", "loanumber", "loannumber",
        "directratinginformation",
        "mortgageesadditionalinterestinformation",
    ]
    ll_nospace = re.sub(r'\s+', '', ll)
    for frag in _GARBLED_LABEL_FRAGMENTS:
        if frag in ll_nospace:
            return True
    
    # Fuzzy match against known full labels (catches OCR character substitutions)
    _KNOWN_LABELS = [
        "name and address of the insured",
        "name and address of insured",
        "named insured and address",
        "insured name and address",
        "insured mailing name and address",
        "name of the insured",
        "policy number",
        "insured location",
        "property address",
        "coverage forms",
        "declaration page",
        "declarations page",
        "coverage and limits",
        "this declaration page is attached to and forms part of certificate provisions",
        "nfip direct rating information",
        "mortgagees additional interest information",
    ]
    for known in _KNOWN_LABELS:
        # Compare character similarity ratio
        ratio = SequenceMatcher(None, ll_nospace, known.replace(" ", "")).ratio()
        if ratio > 0.55:  # 55% character similarity = likely garbled label
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
    
    # CRITICAL: Reject OCR-garbled labels masquerading as names
    if _is_garbled_label(text):
        return False
    
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
    
    # CRITICAL: Reject postal barcode artifacts.
    # USPS barcodes OCR as strings with double-quote chars or non-ASCII chars.
    # Real person/company names never contain double-quote characters.
    if '"' in text:
        return False
    # Reject if >20% of characters are non-alphanumeric/space (barcode noise)
    _non_alnum = sum(1 for c in text if not c.isalnum() and c != ' ')
    if len(text) > 0 and _non_alnum / len(text) > 0.20:
        return False
    # Reject if any non-ASCII characters present (Cyrillic/box-drawing from barcodes)
    if any(ord(c) > 127 for c in text):
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
    
    # CRITICAL: Block currency/liability-limit values.
    # Policy numbers never use comma-thousands separators (e.g. "500,000", "S10,000").
    # Pattern: optional single letter prefix, then digits with commas (NNN,NNN).
    if re.match(r'^[A-Z]?\d{1,3}(,\d{3})+$', v_original, re.I):
        return False
    # Also block OCR-mangled dollar amounts: '$' read as 'S' prefix on currency values.
    if re.match(r'^[$S]\s*\d{1,3}(,\d{3})*(\\.\d{1,2})?$', v_original, re.I):
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
        return 6 <= len(v_clean) <= 16
    
    # Mixed: check against patterns
    for rx in POLICY_REGEX_VARIANTS:
        if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
            return True
    
    # Fallback: alphanumeric with substantial digits (lowered to 4 for NN-XX-XXXXX formats)
    if letters >= 1 and digits >= 4:
        return True
    
    return False


def _looks_like_loan_number(v: str, labeled: bool = False) -> bool:
    """
    Check if value looks like a loan number
    IMPROVED: Better filtering, stricter for short numbers
    Args:
        v: The value to check
        labeled: If True, the number came from an explicit loan label
                 (e.g., "Loan Number: 600003415") — use relaxed filtering
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
    
    # When the number comes from an explicit label, use relaxed validation
    # These are high-confidence: the label already confirms it's a loan number
    if labeled:
        # Only block obvious non-loan patterns
        if DATE_RE.search(v):
            return False
        if re.match(r'^(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(\d{4}|\d{2})$', digits):
            return False
        return True
    
    # Block 13+ pure digits — likely a barcode artifact
    if len(digits) >= 13 and v.replace(' ', '').replace('-', '').isdigit():
        return False
    
    # Block if too many consecutive zeros (padding patterns)
    if '000000' in digits:
        return False
    
    # Block numbers starting with '00' that are longer than 10 digits
    if digits.startswith('00') and len(digits) > 10:
        return False
    
    # Block if more than 50% zeros in longer numbers
    if len(digits) > 10:
        zero_count = digits.count('0')
        if zero_count > len(digits) * 0.5:
            return False
    
    # Block if more than 40% zeros in numbers with 9+ digits
    # (catches footer codes like 00172500217 with 45% zeros)
    if len(digits) >= 9:
        zero_count = digits.count('0')
        if zero_count > len(digits) * 0.4:
            return False
    
    # Block dates (with separators)
    if DATE_RE.search(v):
        return False

    # Block digit-only date sequences: MMDDYYYY (8) or MMDDYY (6)
    # e.g. "09152020" extracted from "09/15/2020" after stripping non-digits
    if re.match(r'^(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(\d{4}|\d{2})$', digits):
        return False

    # Block footer/form reference codes (print job IDs)
    # These appear at the bottom of pages as "19655_65232kR" or "044_091120_000442"
    # and OCR extracts them as digit strings like "1965565232" or "044091120000442"
    # Pattern: 10-digit number starting with common form-code prefixes
    if re.match(r'^(?:19\d{3}|044)\d{5,9}$', digits):
        return False
    # Block numbers that look like concatenated form reference + page codes
    # e.g. "1965565232" from "19655_65232" — two 5-digit groups
    if len(digits) == 10 and re.match(r'^\d{5}\d{5}$', digits):
        # Additional heuristic: check if first 5 and last 5 digits both start with
        # plausible form-code ranges (not typical for real loan numbers)
        first5 = int(digits[:5])
        if 19000 <= first5 <= 19999:
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
    
    # Must have "insurance" or "indemnity" or "casualty" or abbreviations INS/CAS
    # "ALLIED PROP AND CAS INS CO" uses abbreviations
    has_ins = any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance', ' ins '))
    if not has_ins:
        has_ins = ll.endswith(' ins') or bool(re.search(r'\bins\b', ll)) or bool(re.search(r'\bcas\b', ll))
    if not has_ins:
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
    # Short words that need word-boundary matching
    company_type_short = ['co']
    
    ll = line.lower()
    best_end = -1
    
    for ct in company_type_words:
        idx = ll.rfind(ct)  # rightmost occurrence
        if idx >= 0:
            end = idx + len(ct)
            if end > best_end:
                best_end = end
    
    # Word-boundary match for short words like "co" to avoid matching inside "company"/"coverage"
    for ct in company_type_short:
        for m in re.finditer(r'\b' + re.escape(ct) + r'\b', ll):
            end = m.end()
            if end > best_end:
                best_end = end
    
    if best_end > 0:
        result = line[:best_end].strip()
    else:
        result = line
    
    # Must still contain 'insurance', 'indemnity', 'casualty', or abbreviations INS/CAS
    result_lower = result.lower()
    has_ins_word = any(w in result_lower for w in ('insurance', 'indemnity', 'casualty', 'assurance', 'fire'))
    if not has_ins_word:
        has_ins_word = bool(re.search(r'\bins\b', result_lower)) or bool(re.search(r'\bcas\b', result_lower))
    if not has_ins_word:
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
        
        # Detect fax cover sheet pages — suppress extraction until real policy content starts
        if any(k in ll for k in ("fax cover sheet", "cover message", "fax number",
                                  "fax coversheet", "fax cover page")):
            self._in_fax_cover = True
        # Also detect fax cover by fuzzy/garbled patterns
        if not getattr(self, '_in_fax_cover', False):
            ll_nospace = re.sub(r'\s+', '', ll)
            if any(f in ll_nospace for f in ("faxcoversheet", "covermessage", "faxnumber",
                                              "faxcoverpage")):
                self._in_fax_cover = True
        # Exit fax cover when we see real policy content
        if getattr(self, '_in_fax_cover', False):
            if any(k in ll for k in ("policy declarations", "declaration page", "invoice",
                                       "policy information", "certificate", "renewal",
                                       "policy number", "policy no", "policy #",
                                       "declarations page", "cert.", "cert #",
                                       "prev. cert", "name and address of",
                                       "coverages", "effective from",
                                       "policy period")):
                self._in_fax_cover = False
        
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
            # CRITICAL: "INSURED NAME AND ADDRESS" is a stronger/more specific label
            # than standalone "INSURED". If we already have an insured_name from a
            # weaker source (e.g., block capture from a standalone "INSURED" label
            # that accidentally captured a mortgagee name), allow override.
            if "name" in ll and "address" in ll:
                # This is "INSURED NAME AND ADDRESS" - high confidence label
                # Allow override of existing insured_name if it came from a weak source
                existing = self.fields.get("insured_name", {})
                existing_src = existing.get("source", "")
                if existing_src in ("block", "block_combined", "block_extended",
                                     "insured_block_mortgage_redirect", "mailing_block"):
                    # Delete existing so it can be re-captured
                    if "insured_name" in self.fields:
                        del self.fields["insured_name"]
                    self._partial_insured = ""
            self.role, self.window = Role.INSURED_BLOCK, 12
        elif any(k in ll for k in PROPERTY_TRIGGERS):
            # CRITICAL: Don't trigger for endorsement/premium section headers
            _prop_skip = ("endorsement", "total premium", "total policy",
                          "total location", "rated", "coverage info",
                          "policy info", "pol indicator", "coverage and limits",
                          "policy period",     # "Policy Period Location of Residence Premises" is NOT a property trigger
                          "standard time",     # "STANDARD TIME AT THE RESIDENCE PREMISES" is boilerplate, not property
                          "12:01")             # Time stamp lines near policy period
            if not any(s in ll for s in _prop_skip):
                self._flush_accumulators()
                self.role, self.window = Role.PROPERTY_BLOCK, 8
        # Standalone "Address:" line can indicate property in declarations context
        elif re.match(r'^address\s*[:.]', ll) and "property_address" not in self.fields:
            self._flush_accumulators()
            self.role, self.window = Role.PROPERTY_BLOCK, 5
        elif any(k in ll for k in MORTGAGE_TRIGGERS):
            # Check if it's a false positive (service center header)
            if not any(fp in ll for fp in MORTGAGE_FALSE_POSITIVES):
                # CRITICAL: Skip "Reason for Change:" lines — these describe WHY a change
                # was made, not the mortgagee section itself.
                # e.g., "Reason for Change: Change to Mortgagee Information"
                if "reason for" in ll:
                    pass  # Do NOT enter MORTGAGE_BLOCK
                else:
                    self._flush_accumulators()
                    self.role, self.window = Role.MORTGAGE_BLOCK, 10
        elif any(k in ll for k in PRODUCER_TRIGGERS):
            # Producer/agent section - skip names here
            # CRITICAL: Don't override INSURED_BLOCK — two-column OCR merge can put
            # agency names on the same line as insured names (e.g., "YOKO MATSUMOTO GEICO INS AGENCY INC")
            if self.role != Role.INSURED_BLOCK:
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
        # Skip extraction during fax cover sheet pages
        # (fax cover sheets contain loan numbers, dates, and names that can
        # be misidentified as policy fields)
        if getattr(self, '_in_fax_cover', False):
            return
        
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
        
        # Check if this line contains 'insurance', 'indemnity', 'casualty' or abbreviation 'ins'/'cas'
        has_insurance_keyword = any(w in ll for w in ('insurance', 'indemnity', 'casualty'))
        if not has_insurance_keyword:
            has_insurance_keyword = bool(re.search(r'\bins\b', ll)) or bool(re.search(r'\bcas\b', ll))
        
        if has_insurance_keyword:
            # CRITICAL: Skip email addresses, URLs, and binding notices
            if '@' in clean or 'www.' in ll or 'http' in ll or '.com' in ll:
                self.carrier_accumulator = []  # Clear any pending accumulation
                return
            
            # If we have accumulated a prefix, ALWAYS try to combine
            if self.carrier_accumulator:
                combined = " ".join(self.carrier_accumulator) + " " + clean
                combined_lower = combined.lower()
                # If combined has insurance/ins/cas + company type, use it
                combined_has_ins = 'insurance' in combined_lower or bool(re.search(r'\bins\b', combined_lower)) or bool(re.search(r'\bcas\b', combined_lower))
                if combined_has_ins and any(w in combined_lower for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual')):
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
            # Strip common label prefixes: "Insurance Company:", "Carrier:", etc.
            carrier_candidate = re.sub(
                r'^(?:Insurance\s+Company|Carrier|Insurer|Underwriter|Company)\s*:\s*',
                '', carrier_candidate, flags=re.I).strip()
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
                    # CRITICAL: Only accumulate short lines that look like company names
                    # Don't accumulate full sentences containing "insurance"
                    # Don't accumulate email addresses or URLs
                    if (len(clean.split()) <= 6 and len(clean) <= 60
                        and '@' not in clean and 'www.' not in ll
                        and 'http' not in ll and '.com' not in ll):
                        self.carrier_accumulator = [clean]
                        return
        
        # If accumulator has 'insurance' and current line is a company-type word
        # e.g., accumulator = ["Erie INSURANCE"], current line = "Exchange"
        elif self.carrier_accumulator and any('insurance' in a.lower() for a in self.carrier_accumulator):
            company_types = ('exchange', 'company', 'group', 'mutual', 'corp', 'corporation')
            if any(w in ll for w in company_types):
                combined = " ".join(self.carrier_accumulator) + " " + clean
                combined_lower = combined.lower()
                # CRITICAL: Combined carrier name should be short (max ~8 words)
                if (not any(w in combined_lower for w in ('agency', 'agent', 'services'))
                    and len(combined.split()) <= 8):
                    carrier_val = _extract_carrier_name(_clean_carrier_name(combined))
                    self.fields["carrier_name"] = {
                        "value": carrier_val.upper(),
                        "confidence": 0.97,
                        "source": "multi_line_combined",
                    }
                    self.carrier_accumulator = []
                    return
        
        # Check if this might be first part of multi-line carrier
        # e.g., "ADIRONDACK" (uppercase) or "Anchor Specialty" (Title Case)
        elif len(clean.split()) <= 3 and not any(c.isdigit() for c in clean):
            # Might be company name prefix
            noise_words = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", 
                          "NOTICE", "PO", "BOX", "RENEWAL", "DECLARATIONS", "PREMIUM",
                          "COVERAGE", "SECTION", "DWELLING", "HOMEOWNERS", "HO3"}
            words = clean.split()
            upper_words = [w.upper() for w in words]
            if words and not any(w in noise_words for w in upper_words):
                if all(len(w) >= 3 for w in words):  # Each word should be substantial
                    # Accept if all uppercase OR all title case (first letter upper)
                    if clean.isupper() or all(w[0].isupper() for w in words if w):
                        self.carrier_accumulator = [clean]
    
    def _inline(self, line: str):
        """Extract from inline patterns (Label: Value)"""
        ll = line.lower()
        
        # Policy Number — also handle "POLICY NUMBER value" on same line (no colon)
        if "policy_number" not in self.fields:
            if ":" in line and any(k in ll for k in POLICY_LABELS):
                _, _, v = line.partition(":")
                v = _clean(v)
                # Strip trailing noise words that OCR column-merging can append
                # e.g. "886 700 444 Agency" → "886 700 444"
                # e.g. "063 078 674 Policy descrip" → "063 078 674"
                v = re.sub(
                    r'\s+(?:agency|agent|eff\.?|effective|date|page|continued|'
                    r'information|loan|your|the|this|inc\.?|co\.?|corp\.?|'
                    r'policy|description|type|period)\b.*$',
                    '', v, flags=re.I
                ).strip()
                # Hard-stop at any Title-case word following the number
                # (catches abbreviated labels not in the list above)
                v = re.sub(r'\s+[A-Z][a-z].*$', '', v).strip()

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
                # Handle "821 359 087" style (3 groups of 3 digits)
                elif re.match(r'^\d{3}\s+\d{3}\s+\d{3}$', v):
                    v_no_space = v.replace(" ", "")
                    self.fields["policy_number"] = {
                        "value": v_no_space,
                        "confidence": 0.99,
                        "source": "inline",
                    }
                else:
                    # Handle split values like "DPC 0076173896 -1" or "04038598 - 1"
                    # First normalize " - " to "-" to avoid double dash
                    v = re.sub(r'\s*-\s*', '-', v)
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
                        # Strip trailing OCR label bleed: "063 078 674 Policy description" → "063 078 674"
                        after_label = re.sub(
                            r'\s+(?:policy\s*(?:description|descrip|type|period|number)?'
                            r'|description|descrip)\b.*$',
                            '', after_label, flags=re.I
                        ).strip()
                        after_label = re.sub(r'\s+[A-Z][a-z].*$', '', after_label).strip()
                        tokens = after_label.split()
                        # Try each token individually first
                        found = False
                        for token in tokens:
                            candidate = _clean(token)
                            if _looks_like_policy(candidate.replace(" ", "")):
                                self.fields["policy_number"] = {
                                    "value": candidate,
                                    "confidence": 0.95,
                                    "source": "inline_no_colon",
                                }
                                found = True
                                break
                        # Combine all-digit token groups: "063 078 674" → "063078674"
                        if not found and tokens and all(t.isdigit() for t in tokens) and 2 <= len(tokens) <= 4:
                            combined = "".join(tokens)
                            if _looks_like_policy(combined):
                                self.fields["policy_number"] = {
                                    "value": combined,
                                    "confidence": 0.93,
                                    "source": "inline_no_colon_combined",
                                }
                        if "policy_number" in self.fields:
                            break
        
        # Property Address (NEW - for "Risk Location: 3004 NORFOLK DR" patterns)
        if "property_address" not in self.fields and ":" in line:
            if any(k in ll for k in PROPERTY_INLINE_LABELS):
                # CRITICAL: Skip date/policy lines that contain "location" incidentally
                # e.g., "Policy Expiration Date: 09/03/2021 12:01 A.M. at Insured Location"
                skip_property_line = any(skip_k in ll for skip_k in (
                    "expiration", "effective", "policy period", "process date",
                    "transaction", "policy number"))
                if skip_property_line:
                    pass  # Don't extract property from date/policy lines
                else:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    # Handle double-label patterns:
                    # "DESCRIPTION OF PROPERTY:  LOCATED AT:  908 Meadow Ln"
                    # After first ":", remainder may contain "LOCATED AT: <address>"
                    if ":" in v:
                        # Try extracting after the LAST colon
                        last_colon_idx = v.rfind(":")
                        after_last = v[last_colon_idx + 1:].strip()
                        if after_last and _looks_like_address(after_last):
                            v = after_last
                        elif "located at" in v.lower():
                            # Extract after "LOCATED AT:"
                            m_loc = re.search(r'(?i)located\s+at\s*:\s*(.*)', v)
                            if m_loc:
                                v = m_loc.group(1).strip()
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
            if any(k in label_lower for k in ("insured", "policyholder", "customer name")):
                # CRITICAL: Skip if label contains mortgagee terms or interest-type labels
                if any(bad in label_lower for bad in (
                    "mortgagee", "loss payee", "lender",
                    "interest of", "interest in",  # "Interest of Named Insured In Such Premises"
                    "additional insured",
                )):
                    pass  # Skip this
                else:
                    v = _normalize_name(val)
                    # CRITICAL: Reject OCR-garbled label text captured as name value
                    if v and _is_garbled_label(v):
                        v = ""  # Don't use garbled label text as a name
                    if v and _looks_like_name(v):
                        self.fields["insured_name"] = {
                            "value": v,
                            "confidence": 0.99,
                            "source": "inline",
                        }
                    elif v and len(v.strip()) > 3 and "insured_name" not in self.fields:
                        # Value on same line might be partial - check next line context
                        # Store as potential first part of multi-line name
                        # CRITICAL: Only set partial if we don't already have a good name
                        self._partial_insured = v.strip()
        
        # Loan Number (IMPROVED)
        # Labeled loan numbers (with "Loan Number:" prefix) override unlabeled ones
        has_loan_label = any(k in ll for k in LOAN_LABELS)
        existing_loan = self.fields.get("loan_number", {})
        existing_is_unlabeled = existing_loan.get("source") in ("mortgage_block", "sweep") if existing_loan else False
        
        if has_loan_label and ("loan_number" not in self.fields or existing_is_unlabeled):
            if ":" in line:
                _, _, v = line.partition(":")
                v = v.strip()
                # CRITICAL FIX: Extract only the first contiguous digit sequence
                # instead of ALL digits from the line. This prevents digit bleed
                # from adjacent OCR fields (e.g., "0580239576" + "4" from zip "48007")
                m_loan = re.search(r'(\d[\d\s\-]*\d)', v)
                if m_loan:
                    digits = re.sub(r'[\s\-]', '', m_loan.group(1))
                else:
                    digits = ''.join(c for c in v if c.isdigit())
            else:
                # Try to find number on line
                digits = ''
                for token in line.split():
                    d = ''.join(c for c in token if c.isdigit())
                    if len(d) >= 7:
                        digits = d
                        break
            
            if _looks_like_loan_number(digits, labeled=True):
                self.fields["loan_number"] = {
                    "value": digits,
                    "confidence": 0.96,
                    "source": "inline",
                }
        
        # Dates
        if "effective_date" not in self.fields:
            # CRITICAL: Skip "Original New Business Effective Date" — this is the
            # original inception date (e.g., 10/21/2010), NOT the current renewal date.
            if "original" in ll and "effective" in ll:
                pass  # Skip original effective dates entirely
            else:
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
        
        # Date range pattern: "MM/DD/YYYY to MM/DD/YYYY" or "From: MM/DD/YYYY To: MM/DD/YYYY"
        # Extracts both effective and expiration dates from a single line
        if "effective_date" not in self.fields or "expiration_date" not in self.fields:
            # Pattern 1: "DATE to DATE" (no colons) — case-insensitive for "To" vs "to"
            date_range = re.search(
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+to\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                line, re.I
            )
            # Pattern 2: "From: DATE To: DATE" (with colons) - Nationwide/Allied format
            if not date_range:
                date_range = re.search(
                    r'(?i)from\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+to\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    line
                )
            # Pattern 3: "DATE - DATE" (dash-separated) — Adirondack/other formats
            # e.g., "4/30/2020 - 4/30/2021" or "06-26-20 To: 06-26-21"
            if not date_range:
                date_range = re.search(
                    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*[-–]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
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
                line, re.I
            )
            # Also try dash-separated: "4/30/2020 - 4/30/2021"
            if not date_range:
                date_range = re.search(
                    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*[-–]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
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
                "total premium paid",  # Flood: "Total Premium Paid: 5,007.19"
                "invoice total",  # QBE: "Invoice Total: 5,421.05"
                "total due",  # QBE declaration: "TOTAL DUE"
            )
            if any(k in ll for k in premium_labels):
                # Try to find dollar amount on same line (handles "$ 150.00" with space)
                money = re.findall(r'\$\s*[\d,]+\.?\d*', line)
                if money:
                    self.fields["total_premium"] = {
                        "value": money[-1],  # Take last (usually the total)
                        "confidence": 0.96,
                        "source": "inline_premium",
                    }
                else:
                    # Try bare number after colon (e.g., "Invoice Total: 5,421.05")
                    if ":" in line:
                        _, _, after_colon = line.partition(":")
                        bare = re.search(r'([\d,]+\.\d{2})', after_colon.strip())
                        if bare:
                            val = bare.group(1).replace(",", "")
                            if float(val) > 0:
                                self.fields["total_premium"] = {
                                    "value": "$" + bare.group(1),
                                    "confidence": 0.94,
                                    "source": "inline_premium_bare",
                                }
                            else:
                                self._pending_premium = True
                        else:
                            self._pending_premium = True
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
        
        # CRITICAL: Try the whole line FIRST to preserve prefixes like "DPC 0076173896-1"
        # A prefix pattern is 2-4 uppercase letters followed by digits
        clean_line = _clean(line)
        # Strip trailing noise words that OCR column-merging can append
        _POLICY_NOISE_TRAIL = re.compile(
            r'\s+(?:agency|agent|eff\.?|effective|date|page|continued|'
            r'information|loan|your|the|this|inc\.?|co\.?|corp\.?|'
            r'policy|description|type|period)\b.*$',
            re.I
        )
        clean_line = _POLICY_NOISE_TRAIL.sub('', clean_line).strip()
        # Hard-stop at any Title-case word following the number
        clean_line = re.sub(r'\s+[A-Z][a-z].*$', '', clean_line).strip()
        
        # Check if the whole line (with spaces removed) matches a prefixed policy
        # e.g., "DPC 0076173896-1" → "DPC0076173896-1" or "DPC 0076173896 1" → "DPC0076173896-1"
        no_spaces = clean_line.replace(" ", "")
        # Handle "DPC  0076173896    1" → combine with dash before trailing digit
        # ONLY if the original line had whitespace before the trailing digit
        if re.match(r'^[A-Z]{2,4}', no_spaces) and re.search(r'\s+\d\s*$', clean_line):
            no_spaces = re.sub(r'(\d)(\d)$', r'\1-\2', no_spaces)
        
        if _looks_like_policy(no_spaces) and re.match(r'^[A-Z]{2,4}', no_spaces):
            # Has a letter prefix — keep it
            self.fields["policy_number"] = {
                "value": no_spaces,
                "confidence": 0.96,
                "source": "block",
            }
            return
        
        # CRITICAL: If line has multiple digit groups (e.g., "821 359 087" or "821359 087"),
        # combine them first before trying individual tokens
        tokens = clean_line.split()
        if len(tokens) >= 2 and all(t.isdigit() for t in tokens):
            combined = ''.join(tokens)
            if _looks_like_policy(combined):
                self.fields["policy_number"] = {
                    "value": combined,
                    "confidence": 0.97,
                    "source": "block",
                }
                return
        
        # Also try the full no_spaces version for any multi-token policy
        if _looks_like_policy(no_spaces) and len(tokens) >= 2:
            self.fields["policy_number"] = {
                "value": no_spaces,
                "confidence": 0.95,
                "source": "block_combined",
            }
            return
        
        # Fall back: try each token individually
        for token in line.split():
            clean_token = _clean(token)
            if _looks_like_policy(clean_token):
                self.fields["policy_number"] = {
                    "value": clean_token,
                    "confidence": 0.96,
                    "source": "block",
                }
                return
        
        # Final fallback: try the whole line combined
        if _looks_like_policy(no_spaces):
            self.fields["policy_number"] = {
                "value": no_spaces,
                "confidence": 0.94,
                "source": "block_combined",
            }
    
    def _insured(self, line: str):
        """Extract insured name from INSURED block - IMPROVED"""
        ll = line.lower().strip()
        
        # CRITICAL: Reject OCR-garbled labels masquerading as name values
        if _is_garbled_label(line):
            return
        
        # CRITICAL: Skip lines that are insured labels with colons.
        # _inline() already processes "Named Insured: YOKO" and sets _partial_insured = "YOKO".
        # If _insured() also processes this line, it will try to combine _partial with the
        # same line's content, producing "YOKO YOKO". Let _inline() handle label:value lines.
        if ":" in line and any(k in ll for k in ("insured", "policyholder")):
            # This is a label line like "Named Insured: YOKO" — already handled by _inline()
            return
        
        # Skip obvious non-name lines
        skip_patterns = [
            "po box", "policy period", "loan number", "policy type",
            "description", "coverage", "premium", "effective", "expiration",
            "page", "continued", "summary", "mortgagee", "loss payee",
            "mailing address",
            # Coverage table terms (two-column OCR bleed)
            "property value", "living expense", "fair rental",
            "other structures", "personal property", "additional living",
            "perils insured", "limits of liability", "coverage and limits",
            "amt incl", "at no chg", "endorsement",
            "billing information", "previous policy",
            # Endorsement table values
            "included", "excluded", "not included",
            "limit    premium", "total premium",
            # Footer/copyright lines
            "copyright", "copyrighted", "permission",
            "office, inc", "includes copyrighted",
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
        
        # CRITICAL: Handle two-column OCR merge where insured name + agency name
        # are on the same line. E.g., "YOKO MATSUMOTO GEICO INS AGENCY INC"
        # The insured name is the part BEFORE the agency/company keywords.
        if not _looks_like_name(clean_line) and "insured_name" not in self.fields:
            _agency_split_kw = ("geico", "agency", " ins ", "insurance", "allstate",
                                "state farm", "nationwide", "farmers", "progressive",
                                "liberty mutual", "usaa", "erie", "safeco")
            cl_lower = clean_line.lower()
            for kw in _agency_split_kw:
                idx = cl_lower.find(kw)
                if idx > 3:  # Must have at least a few chars before the keyword
                    candidate = clean_line[:idx].strip()
                    if candidate and _looks_like_name(candidate):
                        self.fields["insured_name"] = {
                            "value": candidate,
                            "confidence": 0.93,
                            "source": "block_column_split",
                        }
                        self._partial_insured = candidate
                        return
        
        # Strip trailing date patterns (e.g., "Dummy Name July 2020" -> "Dummy Name")
        clean_line = re.sub(
            r'\s+(January|February|March|April|May|June|July|August|September|'
            r'October|November|December)\s+\d{4}\s*$',
            '', clean_line, flags=re.I
        ).strip()
        
        # CRITICAL: Additional check - block mortgagee-related values
        if any(bad in ll for bad in BAD_INSURED_TERMS):
            return
        
        # CRITICAL: Strip leading agent/reference codes like "087DF"
        # These are short alphanumeric codes before a company name
        clean_line_stripped = re.sub(r'^\d{2,5}[A-Z]{1,3}\s+', '', clean_line).strip()
        
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
        
        # CRITICAL: If name looks like a mortgage company (contains lending/bank/mortgage + LLC/INC etc.)
        # then skip it - it's likely from a two-column layout where mortgagee is on left
        _mortgage_company_indicators = (
            "lending", "bank", "mortgage", "credit union", "financial",
            "servicing", "loan", "savings", "horizon bank", "underwriters",
            "orchid", "attn",  # "Attn: Orchid Underwriters"
        )
        _entity_suffixes = ("llc", "inc", "corp", "na", "n.a.", "fsb", "f.s.b.", "bank")
        name_lower = clean_line_stripped.lower() if clean_line_stripped else clean_line.lower()
        has_mortgage_indicator = any(w in name_lower for w in _mortgage_company_indicators)
        has_entity_suffix = any(w in name_lower for w in _entity_suffixes)
        if has_mortgage_indicator and has_entity_suffix:
            # This looks like a mortgage company, not an insured name
            # Capture it as mortgage_company instead if not set
            if "mortgage_company" not in self.fields:
                self.fields["mortgage_company"] = {
                    "value": clean_line_stripped if clean_line_stripped != clean_line else clean_line,
                    "confidence": 0.85,
                    "source": "insured_block_mortgage_redirect",
                }
            return
        
        # Check for multi-line name combination (e.g., "DUMMY NAME" + "PROPERTIES, LLC")
        if self._partial_insured and "insured_name" not in self.fields:
            # CRITICAL: Don't combine with coverage/table terms
            _table_stop = ("property", "value", "expense", "living", "rental",
                           "dwelling", "liability", "personal", "coverage",
                           "premium", "deductible", "additional", "structures",
                           "perils", "insured against", "endorsement", "limit",
                           "included", "excluded", "not included",
                           "billing information", "previous policy")
            if any(t in clean_line.lower() for t in _table_stop):
                self._partial_insured = ""
                return
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
                # CRITICAL: Stop extending if current line contains coverage/table terms
                _table_terms = ("property", "value", "expense", "living", "rental",
                                "dwelling", "liability", "personal", "coverage",
                                "premium", "deductible", "additional", "structures",
                                "perils", "insured against", "endorsement", "limit",
                                "included", "excluded", "not included",
                                "billing information", "previous policy")
                if any(t in clean_line.lower() for t in _table_terms):
                    self._partial_insured = ""
                    return
                # CRITICAL: Check if this line is a duplicate of the existing name
                # (e.g., "BROSTRON.JAMES" followed by "BROSTRON,JAMES" — same person, diff punctuation)
                existing = self._partial_insured.replace(".", ",").replace(" ", "").lower()
                new = clean_line.replace(".", ",").replace(" ", "").lower()
                if existing == new or existing.startswith(new) or new.startswith(existing):
                    # Duplicate — keep the better formatted version (with comma)
                    if "," in clean_line and "." in self._partial_insured and "," not in self._partial_insured:
                        self.fields["insured_name"]["value"] = clean_line
                    self._partial_insured = ""
                    return
                # CRITICAL FIX: If the new line looks like a SEPARATE person name
                # (e.g., "BORGESS, REBECCA" after "CLAY, MYRA"), do NOT combine.
                # Only combine if it looks like a business suffix/extension.
                _business_ext = ("llc", "inc", "corp", "ltd", "co", "properties",
                                 "enterprises", "holdings", "investments", "group",
                                 "associates", "partners", "trust", "estate",
                                 "dba", "company", "services")
                cl_lower = clean_line.lower().strip().rstrip(".,")
                is_business_extension = any(cl_lower.startswith(s) or cl_lower.endswith(s)
                                            or s in cl_lower for s in _business_ext)
                if not is_business_extension:
                    # This is a separate person/entity name (e.g., co-insured),
                    # NOT an extension of the primary insured. Keep the first name.
                    self._partial_insured = ""
                    return
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
            # Check if line has "Label: Value" format
            address_value = line.strip()
            if ":" in line:
                _, _, val = line.partition(":")
                val = val.strip()
                if val and _looks_like_address(val):
                    address_value = val
            
            # CRITICAL: Skip addresses that belong to the agency/insurer (two-column layout)
            # Agency addresses often contain "GEICO", "AGENCY", "BLVD" with company names
            _agency_indicators = ("geico", "agency", "insurance agency", "ins agency",
                                  "allstate", "state farm", "farmers", "nationwide")
            addr_lower = address_value.lower()
            is_agency_address = any(w in addr_lower for w in _agency_indicators)
            
            if "mailing_address" not in self.fields:
                if not is_agency_address:
                    self.fields["mailing_address"] = {
                        "value": address_value,
                        "confidence": 0.92,
                        "source": "insured_block",
                    }
                # If this IS an agency address, skip it — don't capture
            else:
                # Append city/state/zip continuation to existing street address
                existing = self.fields["mailing_address"]["value"]
                has_street_number = bool(re.match(r'^\d+\s+', existing.strip()))
                new_has_street = bool(re.match(r'^\d+\s+', address_value.strip()))
                is_city_continuation = (
                    has_street_number and not new_has_street
                    and re.search(r'[A-Z]{2}\s+\d{5}', address_value)
                    and "," not in existing
                )
                if is_city_continuation:
                    self.fields["mailing_address"]["value"] = existing + ", " + address_value
                elif new_has_street and not has_street_number:
                    # Replace partial address with one that has a street number
                    if not is_agency_address:
                        self.fields["mailing_address"]["value"] = address_value
    
    def _property(self, line: str):
        """Extract property address from PROPERTY block"""
        ll = line.lower().strip()
        
        # Skip headers and labels
        if line.strip().endswith(":"):
            return
        if ll in [t.lower() for t in PROPERTY_TRIGGERS]:
            return
        
        # CRITICAL: Skip endorsement-format lines (e.g., "13447 03/93 Lead Poisoning")
        # These are endorsement codes, not addresses
        if re.match(r'^\d{4,5}\s+\d{2}/\d{2}\s+', line.strip()):
            return
        # Skip lines with endorsement/coverage keywords
        _prop_skip_kw = ("endorsement", "exclusion", "amendment", "provision",
                         "protection", "replacement", "liability", "fungi",
                         "ordinance", "coverage", "included", "total",
                         "from:", "standard time", "12:01")  # Date/time lines near policy period
        if any(k in ll for k in _prop_skip_kw):
            return
        
        # Check if line has "Label: Value" format
        address_value = line.strip()
        if ":" in line:
            label, _, val = line.partition(":")
            val = val.strip()
            # If value part looks like an address, use just the value
            if val and _looks_like_address(val):
                address_value = val
        
        # CRITICAL: Strip leading location ID like "001" (Nationwide format)
        # "001 FORT COLLINS, CO 80525-2870" → "FORT COLLINS, CO 80525-2870"
        # Location IDs are typically 3 digits at the start, followed by a city/state/zip
        loc_id_match = re.match(r'^(\d{3})\s+([A-Z])', address_value)
        if loc_id_match:
            # Check if removing the 3-digit prefix leaves a city/state/zip pattern
            remainder = address_value[len(loc_id_match.group(1)):].strip()
            if re.search(r'[A-Z]{2}\s+\d{5}', remainder):
                # This is a location ID + city/state/zip, strip the ID
                address_value = remainder
        
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
        
        # SPECIAL: "0400004466 MORTGAGEE" = loan number + type indicator
        # Extract loan number from this pattern before skipping
        m_loan_type = re.match(r'^(\d{7,15})\s+(?:MORTGAGEE|LOSS\s+PAYEE|LIENHOLDER)\b', line.strip(), re.I)
        if m_loan_type:
            if "loan_number" not in self.fields:
                digits = m_loan_type.group(1)
                if _looks_like_loan_number(digits, labeled=True):
                    self.fields["loan_number"] = {
                        "value": digits,
                        "confidence": 0.94,
                        "source": "mortgage_block",
                    }
            return  # This line is a loan+type indicator, not a company name
        
        # Skip bad patterns (EXPANDED)
        bad_patterns = [
            "policy", "coverage", "endorsement", "homeowners", "premium",
            "first mortgagee", "second mortgagee", "third mortgagee",
            "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
            "mortgagee copy", "mortgagee certificate",
            "other interest", "type of interest",
            "third party interest",  # DOI: "Third party interest added/removed" lines
            "additional interest information",
            "mortgagees additional interest information",
            "direct rating information",
        ]
        # CRITICAL: Don't skip lines that just contain "mortgagee" as the ONLY matching word
        # "0400004466 MORTGAGEE" was handled above; "PLANET HOME LENDING LLC" should pass through
        if any(p in ll for p in bad_patterns):
            # Allow lines that are purely company names (no label words) to pass through
            # Check if the line has actual company name content beyond the bad pattern
            has_company_word = any(w in ll for w in ("bank", "lending", "credit", "financial", 
                                                       "mortgage servicing", "loan servicing",
                                                       "home loan", "savings"))
            has_entity = any(w in ll for w in ("llc", "inc", "corp", "ltd", "na", "n.a."))
            if not (has_company_word or has_entity):
                return
        
        # Loan number — also capture "N/A" style loan indicators
        if "loan_number" not in self.fields:
            has_loan_label = any(k in ll for k in ("loan no", "loan number", "loan #", "loan id", "ln #", "mortgage loan", "loan/contract"))
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
                        if _looks_like_loan_number(digits, labeled=True):
                            self.fields["loan_number"] = {
                                "value": digits,
                                "confidence": 0.94,
                                "source": "mortgage_block",
                            }
            elif not _looks_like_address(line):
                # Only scan tokens for loan number if line is NOT an address
                # If the entire line is just a number (common after MORTGAGEE block),
                # use labeled=True since the mortgage context is strong evidence
                line_is_pure_number = line.strip().replace('-', '').replace(' ', '').isdigit()
                for token in line.split():
                    digits = ''.join(c for c in token if c.isdigit())
                    if _looks_like_loan_number(digits, labeled=line_is_pure_number):
                        self.fields["loan_number"] = {
                            "value": digits,
                            "confidence": 0.90,
                            "source": "mortgage_block",
                        }
                        break
        
        # Mortgage company
        if "mortgage_company" not in self.fields:
            # CRITICAL: Skip loan-label lines — these contain loan numbers, not company names
            # e.g., "Loan/Contract Number: 600003415" should NOT be captured as mortgage_company
            has_loan_label = any(k in ll for k in ("loan no", "loan number", "loan #", "loan id",
                                                     "loan/contract", "contract number"))
            if has_loan_label:
                pass  # Skip — this is a loan line, not a company name
            # Look for company-like patterns
            elif any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "federal", "financial", " mtg ")):
                # CRITICAL: Skip if it's just a label like "First Mortgagee"
                if re.match(r'^(first|second|third|1st|2nd|3rd)\s+(mortgagee|lender)', ll):
                    return
                
                clean = line.strip()
                # Remove numbered section prefixes like "7." or "7. "
                clean = re.sub(r'^\d+\.\s*', '', clean).strip()
                # Remove label prefixes like "holder:", "mortgagee:", "MORTGAGEE(S)", etc.
                clean = re.sub(r'^(holder|mortgagee|loss\s+payee|lienholder|lien\s+holder)\s*[\(:]\s*[sS)]*\s*', '', clean, flags=re.I).strip()
                # Remove ISAOA/ATIMA/SUCC suffixes
                clean = re.sub(r'\s+(ITS\s+SUCC(\s+AND/OR\s+ASSIGNS)?\s+)?(ISAOA|ATIMA|ISAOA/ATIMA).*$', '', clean, flags=re.I)
                clean = re.sub(r'\s+ITS\s+SUCC\s+AND/OR\s+ASSIGNS.*$', '', clean, flags=re.I)
                # Remove numbering prefixes
                clean = re.sub(r'^(\d+\.?\s*|first\s+|second\s+|third\s+)', '', clean, flags=re.I)
                
                if len(clean) > 5 and not _is_mortgage_heading_noise(clean):
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
                    v = _clean(v)
                    # Check for known spaced policy number formats BEFORE removing spaces
                    # e.g., "602732135 664 1" (9+3+1 digit format)
                    if re.match(r'^\d{9}\s+\d{3}\s+\d$', v):
                        # This is a spaced policy number - keep as-is
                        v_check = v.replace(" ", "")
                        if _looks_like_policy(v_check):
                            fields["policy_number"] = {
                                "value": v,
                                "confidence": 0.88,
                                "source": "sweep",
                            }
                            break
                    elif re.match(r'^\d{3}\s+\d{3}\s+\d{3}$', v):
                        # "821 736 168" format — combine
                        v_combined = v.replace(" ", "")
                        if _looks_like_policy(v_combined):
                            fields["policy_number"] = {
                                "value": v_combined,
                                "confidence": 0.88,
                                "source": "sweep",
                            }
                            break
                    else:
                        v = v.replace(" ", "")
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
    if "policy_number" not in fields:
        _extract_policy_from_account_label(lines, fields)
    
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
                    # CRITICAL: Skip lines that look like mortgage company names
                    cand_lower = candidate.lower()
                    _mort_words = ("lending", "bank", "mortgage", "credit union",
                                   "financial", "servicing", "savings")
                    _ent_words = ("llc", "inc", "corp", "na", "n.a.", "fsb")
                    if (any(w in cand_lower for w in _mort_words) and
                        any(w in cand_lower for w in _ent_words)):
                        continue
                    # Skip lines with leading agent codes like "087DF"
                    if re.match(r'^\d{2,5}[A-Z]{1,3}\s+', candidate):
                        continue
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
                    candidate = lines[j].strip()
                    cand_lower = candidate.lower()
                    # Skip date/time lines that appear near policy period
                    if any(skip in cand_lower for skip in ("from:", "standard time", "12:01", "policy period")):
                        continue
                    if _looks_like_address(candidate):
                        # CRITICAL: Strip leading person name from address
                        # e.g., "Dashiell Lopez 19116 N Gardenia Ave" → "19116 N Gardenia Ave"
                        m_name_addr = re.match(
                            r'^([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(\d{1,6}\s+.+)$', candidate)
                        if m_name_addr and _looks_like_address(m_name_addr.group(2)):
                            candidate = m_name_addr.group(2)
                        fields["property_address"] = {
                            "value": candidate,
                            "confidence": 0.84,
                            "source": "sweep_lookahead",
                        }
                        break
                if "property_address" in fields:
                    break
    
    # --- Carrier Name fallback (scan first 20 lines) ---
    if "carrier_name" not in fields:
        # FIRST: check for explicit "Insurance provided by:" / "policy provided by:" label
        # This is the most reliable pattern — value is on the next line(s)
        for i, line in enumerate(lines[:40]):
            ll = line.lower()
            if re.search(r'(?:insurance|policy)\s+provided\s+by\s*:', ll):
                # Collect carrier name from subsequent lines
                parts = []
                for off in range(1, 4):
                    if i + off >= len(lines):
                        break
                    nxt_line = lines[i + off].strip()
                    if not nxt_line or len(nxt_line) < 3:
                        break
                    # Stop at boilerplate/next-section labels
                    if re.match(r'(?i)(you may|contact|visit|phone|www\.|http|all references)', nxt_line):
                        break
                    parts.append(nxt_line)
                    # Stop if we have a company-type word
                    nxt_lower = nxt_line.lower()
                    if any(w in nxt_lower for w in ("company", "exchange", "mutual", "group", "corp")):
                        break
                if parts:
                    carrier_raw = " ".join(parts).strip()
                    # Strip trailing noise like "Customer assistance number: ..."
                    carrier_raw = re.sub(
                        r'\s*(customer\s*(assistance|service)\s*(number|phone|tel)[:\s]?.*|'
                        r'phone[:\s].*|tel[:\s].*|fax[:\s].*|\(\d{3}\).*)',
                        '', carrier_raw, flags=re.I
                    ).strip()
                    # Also truncate at company-type word
                    carrier_clean = _extract_carrier_name(carrier_raw) if carrier_raw else ""
                    if not carrier_clean:
                        carrier_clean = carrier_raw
                    if carrier_clean and len(carrier_clean) > 5:
                        fields["carrier_name"] = {
                            "value": carrier_clean.upper(),
                            "confidence": 0.95,
                            "source": "sweep_provided_by",
                        }
                break  # Only process first "provided by" match
        
        # Then look for "underwritten by" or "your insurer" patterns
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
            # Tier 1: Multi-word carrier names (high confidence, commit immediately)
            _KNOWN_CARRIERS_SWEEP_MULTI = {
                "allied trust", "tower hill", "southern oak", "peoples trust",
                "security first", "homeowners choice", "heritage",
                "florida peninsula", "citizens property", "federated national",
                "universal property", "auto-owners",
                "state farm", "liberty mutual", "american family",
                "texas farmers",  # NFIP WYO carrier
                "encompass indemnity",  # Encompass Indemnity Company
            }
            # Tier 2: Single-word brand names (lower confidence — only use as fallback)
            # These often appear in logos and may NOT be the full carrier name.
            # E.g., "FARMERS" logo → actual carrier is "Texas Farmers Insurance Company"
            _KNOWN_CARRIERS_SWEEP_BRAND = {
                "nationwide", "allstate", "geico", "progressive",
                "travelers", "farmers", "usaa", "erie",
                "safeco", "hartford", "hanover", "encompass",
                "chubb", "amica", "kemper", "mercury", "shelter",
            }
            
            brand_fallback = None  # Store brand-only match as fallback
            
            for line in lines[:15]:
                ll = line.lower().strip().rstrip("'\"")
                # First try multi-word carriers (commit immediately)
                for c in _KNOWN_CARRIERS_SWEEP_MULTI:
                    if c == ll or ll.startswith(c):
                        carrier_val = line.strip().rstrip("'\".,;:").strip()
                        fields["carrier_name"] = {
                            "value": carrier_val,
                            "confidence": 0.88,
                            "source": "sweep_known_carrier",
                        }
                        break
                if "carrier_name" in fields:
                    break
                # Then check single-word brands (save as fallback only)
                if brand_fallback is None:
                    for c in _KNOWN_CARRIERS_SWEEP_BRAND:
                        if c == ll or ll.startswith(c):
                            brand_fallback = {
                                "value": line.strip().rstrip("'\".,;:").strip(),
                                "confidence": 0.70,
                                "source": "sweep_brand_fallback",
                            }
                            break
            
            # Before committing brand fallback, re-scan for full carrier name
            # with "insurance" keyword in the header area (may have been missed
            # by sweep_header due to line formatting or OCR issues)
            if "carrier_name" not in fields:
                for line in lines[:25]:
                    ll = line.lower()
                    if any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance')):
                        if any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
                            if not any(w in ll for w in ('agency', 'agent', 'services', 'processing', 'center')):
                                carrier_val = _extract_carrier_name(line.strip())
                                if carrier_val and _looks_like_carrier(carrier_val):
                                    fields["carrier_name"] = {
                                        "value": carrier_val.upper(),
                                        "confidence": 0.92,
                                        "source": "sweep_header_over_brand",
                                    }
                                    break
            
            # Only use brand fallback if nothing better was found
            if "carrier_name" not in fields and brand_fallback:
                fields["carrier_name"] = brand_fallback
    
    # --- Loan Number fallback ---
    if "loan_number" not in fields:
        for line in lines:
            ll = line.lower()
            if any(k in ll for k in LOAN_LABELS):
                # CRITICAL: Skip footer/reference lines that contain mixed alphanumeric codes
                # e.g., "001725/00217 F3115MMA 9695 07/21/20" or "19660_859561_6 PL-8653 1-97"
                if re.search(r'[A-Z]\d{3,}[A-Z]{2,}', line):
                    continue  # Skip lines with mixed alphanumeric reference codes
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
                    # CRITICAL FIX: Extract first contiguous digit group only
                    # Prevents digit bleed from adjacent OCR fields
                    m_loan = re.search(r'(\d[\d\s\-]*\d)', v)
                    if m_loan:
                        digits = re.sub(r'[\s\-]', '', m_loan.group(1))
                    else:
                        digits = ''.join(c for c in v if c.isdigit())
                else:
                    digits = ''.join(c for c in line if c.isdigit())
                
                if _looks_like_loan_number(digits, labeled=True):
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
            "mortgagee premium",  # Adirondack mortgagee certificate format
            "total premium paid",  # Flood policies: "Total Premium Paid: 5,007.19"
            "invoice total",  # QBE invoice: "Invoice Total: 5,421.05"
            "total due",  # QBE declaration: "TOTAL DUE"
        )
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in premium_labels):
                # Check same line for dollar amount (handles "$ 150.00" with space)
                money = re.findall(r'\$\s*[\d,]+\.?\d*', line)
                if money:
                    fields["total_premium"] = {
                        "value": money[-1],
                        "confidence": 0.85,
                        "source": "sweep_premium",
                    }
                    break
                # Fallback: bare number after colon (e.g., "Total Premium Paid: 5,007.19")
                if ":" in line:
                    _, _, after = line.partition(":")
                    bare = re.search(r'([\d,]+\.\d{2})', after.strip())
                    if bare:
                        val = bare.group(1).replace(",", "")
                        if float(val) > 0:
                            fields["total_premium"] = {
                                "value": "$" + bare.group(1),
                                "confidence": 0.83,
                                "source": "sweep_premium",
                            }
                            break
                # Check next lines — take the LAST dollar amount found
                # (in two-column layouts, the total is the last amount)
                last_money = None
                for j in range(i + 1, min(i + 20, len(lines))):
                    money_j = re.findall(r'\$\s*[\d,]+\.?\d*', lines[j])
                    if money_j:
                        last_money = money_j[-1]
                if last_money:
                    fields["total_premium"] = {
                        "value": last_money,
                        "confidence": 0.82,
                        "source": "sweep_premium_lookahead",
                    }
                    break
    
    # --- Total Premium: standalone "Total:" with bare number (QBE invoice format) ---
    # "Total:    5,421.05" — no $ sign, just "Total:" label
    if "total_premium" not in fields:
        for i, line in enumerate(lines):
            # Match "Total:" followed by a bare number (with or without $)
            m = re.match(r'(?i)^\s*(?:invoice\s+)?total\s*:\s*\$?\s*([\d,]+\.\d{2})\s*$', line.strip())
            if m:
                val = m.group(1).replace(",", "")
                if float(val) > 50:  # Reasonable premium threshold
                    fields["total_premium"] = {
                        "value": "$" + m.group(1),
                        "confidence": 0.88,
                        "source": "sweep_total_bare",
                    }
                    break


# ============================================================
# ENTRY POINTS
# ============================================================

# ---- CAN-specific field patterns ----
# ENHANCED: handles 'on MM-DD-YY' (Nationwide), 'CANCELLATION EFFECTIVE MM/DD/YYYY AT',
# 'POLICY CANCELLATION DATE IS:', and column-table 'Cancellation date for'
_CAN_DATE_PATTERNS = re.compile(
    r"(?i)(?:"
    # A: standard "cancellation/cancelled/non-renewal [effective/date] [is]: DATE"
    r"(?:cancellation|cancel(?:led)?|termination|void|cease|non-?renewal)"
    r"(?:\s+effective|\s+date(?:\s+and\s+time)?)?(?:\s+for[\w\s]*interest)?"
    r"(?:\s+(?:is|will\s+be|date\s+is))?\s*[:\-]?\s*"
    # B: "cancelled...as of 12:01 A.M. standard time\non MM-DD-YY"
    r"|cancel(?:led|ed)\s+(?:.*?(?:standard|local)\s+time\s+)?on\s+"
    # C: "POLICY CANCELLATION DATE IS:"
    r"|policy\s+cancellation\s+date\s+is\s*:\s*"
    r")"
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
    r"(?i)(?:mail\s+to|remit\s+to|payable\s+to|make\s+check[s]?\s+(?:or\s+money\s+order\s+)?payable\s+to"
    r"|send\s+payment\s+to|payment\s+to)\s*[:\-]?\s*(.{4,120})"
)


def _extract_can_inv_fields(lines: List[str], fields: Dict[str, Dict]) -> None:
    """
    Doc-type-aware sweep for CAN and INV specific fields.
    Stage1 normally doesn't extract these — this function fills the gap.
    Called after _safe_sweep() so it only adds fields that Stage1 missed.

    ENHANCED for real CAN batch: column-header tables (AmFam), truncated dates
    (flood CAN), non-renewal dates (Allstate), inception dates, recipient
    mortgagee inference, 'as follows:' reason look-ahead, insured-from-column,
    property address from named-insured block, and page-2 carrier recovery.
    """
    text = "\n".join(lines)

    # =================================================================
    # CANCELLATION DATE (multi-strategy)
    # =================================================================
    if "cancellation_date" not in fields:
        # Strategy A: regex on joined text (handles 'on 09-07-20', standard labels)
        m = _CAN_DATE_PATTERNS.search(text)
        if m:
            fields["cancellation_date"] = {
                "value": m.group(1).strip(),
                "confidence": 0.82,
                "source": "stage1_can_date",
            }

    if "cancellation_date" not in fields:
        # Strategy B: non-renewal date (Allstate: label line, date on next lines)
        for i, line in enumerate(lines):
            if re.search(r'(?i)non-?renewal\s+date', line):
                d = _scan_date_nearby(lines, i, 0, 4)
                if d:
                    fields["cancellation_date"] = {
                        "value": d, "confidence": 0.80,
                        "source": "stage1_can_nrnw_date",
                    }
                break

    if "cancellation_date" not in fields:
        # Strategy C: column-header table (AmFam: "Policy number  Cancellation date  Insured  Loan")
        for i, line in enumerate(lines):
            ll = line.lower()
            if "cancellation date" in ll and (
                "policy" in ll or "insured" in ll or "loan" in ll
            ):
                for off in range(1, 4):
                    if i + off >= len(lines):
                        break
                    row = lines[i + off]
                    if row.strip()[:1] in (":", ";"):
                        continue  # skip sub-header ": third party interest"
                    dates = re.findall(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b', row)
                    if dates:
                        fields["cancellation_date"] = {
                            "value": dates[0], "confidence": 0.80,
                            "source": "stage1_can_column_date",
                        }
                        # Also harvest insured + loan from same row
                        _harvest_can_column_row(row, fields, dates[0])
                        break
                break

    if "cancellation_date" not in fields:
        # Strategy D: truncated date (flood CAN: "Cancellation Date: 01/10/")
        for line in lines:
            m = re.search(
                r'(?i)cancellation\s+date\s*:\s*(\d{1,2}/\d{1,2}/)\s*$', line)
            if m:
                fields["cancellation_date"] = {
                    "value": m.group(1).rstrip("/"),
                    "confidence": 0.68,
                    "source": "stage1_can_date_truncated",
                }
                break

    # =================================================================
    # CANCELLATION REASON
    # =================================================================
    if "cancellation_reason" not in fields:
        m = _CAN_REASON_LABELS.search(text)
        if m:
            reason = m.group(1).strip().rstrip(".")
            reason = re.sub(r'^[:\s;°]+', '', reason).strip()
            # Reject label fragments captured instead of actual reason
            if re.match(r'(?i)^(as follows|for this action|for the cancellation is)',
                        reason):
                reason = ""
            if len(reason) > 3 and not re.match(r"^\d", reason):
                fields["cancellation_reason"] = {
                    "value": reason,
                    "confidence": 0.78,
                    "source": "stage1_can_reason",
                }

    if "cancellation_reason" not in fields:
        # "as follows:\n <actual reason on next line>"
        for i, line in enumerate(lines):
            if re.search(r'(?i)reason.{0,30}cancellation.{0,20}as\s+follows', line):
                for off in range(1, 4):
                    if i + off >= len(lines):
                        break
                    nxt = lines[i + off].strip()
                    # Skip generic noise / boilerplate
                    if (nxt and len(nxt) > 5
                        and not re.match(r'(?i)^(P |If |Thank|Please)', nxt)):
                        fields["cancellation_reason"] = {
                            "value": nxt,
                            "confidence": 0.75,
                            "source": "stage1_can_reason_follows",
                        }
                        break
                break

    # =================================================================
    # EFFECTIVE DATE (inception date fallback + terminate policy effective)
    # =================================================================
    if "effective_date" not in fields:
        for line in lines:
            m = re.search(
                r'(?i)inception\s+date\s*:\s*(\d{1,2}/\d{1,2}/?\d{0,4})', line)
            if m:
                val = m.group(1).strip().rstrip("/")
                if val and len(val) >= 4:
                    fields["effective_date"] = {
                        "value": val, "confidence": 0.75,
                        "source": "stage1_inception_date",
                    }
                    break

    # "Terminate this Policy Effective: 09/03/2020" → also effective_date
    if "effective_date" not in fields:
        for line in lines:
            m = re.search(
                r'(?i)terminate\s+this\s+policy\s+effective\s*:\s*'
                r'(\d{1,2}/\d{1,2}/\d{2,4})', line)
            if m:
                fields["effective_date"] = {
                    "value": m.group(1), "confidence": 0.82,
                    "source": "stage1_terminate_eff_date",
                }
                break

    # =================================================================
    # CARRIER NAME: "Your policy provided by\n<carrier name>"
    # =================================================================
    _extract_carrier_provided_by(lines, fields)

    # =================================================================
    # INSURED NAME: "Name and address of Insured:\n<name>"
    # =================================================================
    _extract_insured_from_label(lines, fields)
    _override_insured_from_customer_label(lines, fields)

    # =================================================================
    # POLICY NUMBER: prefer labeled values, then clean POBOX contamination
    # =================================================================
    _override_policy_from_label(lines, fields)
    _clean_policy_number(fields)

    # =================================================================
    # MORTGAGE COMPANY: clean ISAOA/ATIMA/SCRS suffixes
    # =================================================================
    _clean_mortgage_suffixes(fields)

    # =================================================================
    # LOAN NUMBER: labeled "Loan Number:\n<digits>" override
    # =================================================================
    _extract_loan_next_line(lines, fields)

    # =================================================================
    # INSURED NAME (column-row + "Named Insured and Address" block)
    # =================================================================

    # Strategy 0: Fix merged mortgagee+insured line
    # Pattern: "1st Mortgagee:  NAMED INSURED AND ADDRESS:"
    #          "EVERETT FINANCIAL INC DBA SUPREME  ROBERT J BARRON and DANIEL PRYCE"
    # The OCR merges two columns into one line. Split at the boundary.
    _fix_merged_mortgagee_insured(lines, fields)

    if "insured_name" not in fields:
        # Strategy A: column-header table row
        for i, line in enumerate(lines):
            ll = line.lower()
            if ("named insured" in ll
                and ("policy" in ll or "cancellation" in ll or "loan" in ll)):
                for off in range(1, 4):
                    if i + off >= len(lines):
                        break
                    row = lines[i + off]
                    if row.strip()[:1] in (":", ";"):
                        continue
                    segs = re.split(r'\s{2,}', row.strip())
                    segs = [s.strip(" _-") for s in segs if s.strip(" _-")]
                    for seg in segs:
                        words = seg.split()
                        if (2 <= len(words) <= 6
                            and not any(c.isdigit() for c in seg)
                            and not re.search(
                                r'(?i)policy|coverage|premium|notice|party|third',
                                seg)
                            and words[0][:1].isupper()):
                            fields["insured_name"] = {
                                "value": seg.strip(),
                                "confidence": 0.78,
                                "source": "stage1_can_column_insured",
                            }
                            break
                    break

    if "insured_name" not in fields:
        # Strategy B: "Policy Number  Named Insured\n_ ACP BPH 7885310416 SUSANA SILVA _"
        for i, line in enumerate(lines):
            ll = line.lower()
            if "policy number" in ll and "named insured" in ll:
                if i + 1 < len(lines):
                    row = lines[i + 1]
                    # Strip policy-number-like prefix, then extract name
                    # Pattern: "_ ACP BPH 7885310416 SUSANA SILVA - _"
                    cleaned = re.sub(r'^[_\s]*(?:[A-Z]{2,4}\s+){0,3}', '', row)
                    # Remove leading digits (policy number)
                    cleaned = re.sub(r'^\d[\d\s]*\d\s+', '', cleaned)
                    # Remove trailing noise
                    cleaned = re.sub(r'\s*[-_]+\s*$', '', cleaned).strip()
                    if cleaned and 2 <= len(cleaned.split()) <= 6:
                        fields["insured_name"] = {
                            "value": cleaned,
                            "confidence": 0.75,
                            "source": "stage1_can_polnum_insured",
                        }
                break

    # =================================================================
    # PROPERTY ADDRESS (from named-insured address block)
    # =================================================================
    if "property_address" not in fields:
        # After "NAMED INSURED AND ADDRESS:" or after insured name in
        # column-table, the next lines with digit+street are the address.
        for i, line in enumerate(lines):
            if re.search(r'(?i)named\s+insured\s+and\s+address', line):
                addr = _collect_address_below(lines, i + 1, skip_first_line=True)
                if addr:
                    fields["property_address"] = {
                        "value": addr, "confidence": 0.75,
                        "source": "stage1_can_named_addr",
                    }
                break

    if "property_address" not in fields:
        # After insured name in "Policy Number  Named Insured" table,
        # address is on the next 1-2 lines
        for i, line in enumerate(lines):
            ll = line.lower()
            if "policy number" in ll and "named insured" in ll:
                # Data row is i+1, address is i+2, i+3
                addr = _collect_address_below(lines, i + 2, skip_first_line=False)
                if addr:
                    fields["property_address"] = {
                        "value": addr, "confidence": 0.78,
                        "source": "stage1_can_column_addr",
                    }
                break

    # =================================================================
    # MORTGAGE COMPANY (recipient address block for flood CAN)
    # =================================================================
    if "mortgage_company" not in fields:
        _extract_recipient_mortgagee(lines, fields)

    # --- Clean mortgage_company: strip producer/agent name prefix ---
    # Pattern: "Michael Ames EVERETT FINANCIAL INC DBA SUPREME"
    # Producer names from "Producer:" section get merged with mortgage in OCR.
    if "mortgage_company" in fields:
        _clean_mortgage_value(lines, fields)

    # =================================================================
    # CARRIER NAME (page-2 recovery: company near "Policy Number:" on later page)
    # =================================================================
    if "carrier_name" not in fields:
        _extract_carrier_page2(lines, fields)

    # =================================================================
    # INV fields (unchanged)
    # =================================================================
    # --- BALANCE DUE ---
    if "balance_due" not in fields:
        # Find ALL matches and pick the largest amount (avoids grabbing
        # small "past due" sub-amounts before the real balance figure)
        all_balance_matches = _BALANCE_DUE_PATTERNS.findall(text)
        if all_balance_matches:
            def _to_float(s):
                try:
                    return float(s.replace(",", ""))
                except ValueError:
                    return 0.0
            best = max(all_balance_matches, key=_to_float)
            fields["balance_due"] = {
                "value": "$" + best.strip(),
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
        # Strategy A: inline match
        m = _REMIT_PATTERNS.search(text)
        if m:
            remit = m.group(1).strip()
            if len(remit) > 3:
                fields["remit_info"] = {
                    "value": remit,
                    "confidence": 0.78,
                    "source": "stage1_inv_remit",
                }

    if "remit_info" not in fields:
        # Strategy B: payee name on the line AFTER the trigger
        # e.g. "Make check or money order\npayable to Allstate Indemnity Company."
        for i, line in enumerate(lines):
            if re.search(r'(?i)(payable\s+to|make\s+check|remit\s+to|mail\s+payment)', line):
                if i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if (nxt and len(nxt) > 5
                            and re.search(r'[A-Z]{3}', nxt)
                            and not re.match(r'^\d', nxt)):
                        fields["remit_info"] = {
                            "value": nxt,
                            "confidence": 0.76,
                            "source": "stage1_inv_remit_nextline",
                        }
                        break


# ---- CAN HELPER FUNCTIONS ----

def _scan_date_nearby(lines: List[str], start: int,
                      lo: int = 0, hi: int = 4) -> str:
    """Scan lines[start+lo .. start+hi-1] for a date, return first found."""
    for off in range(lo, hi):
        idx = start + off
        if idx >= len(lines):
            break
        line = lines[idx]
        m = re.search(
            r'((?:January|February|March|April|May|June|July|August|September|'
            r'October|November|December)\s+\d{1,2},?\s+\d{4})', line, re.I)
        if m:
            return m.group(1)
        m = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', line)
        if m:
            return m.group(1)
    return ""


def _harvest_can_column_row(data_line: str, fields: Dict,
                            cancel_date: str) -> None:
    """Extract insured name and loan number from a column-header data row."""
    remainder = data_line.replace(cancel_date, "  ").strip()
    segs = re.split(r'\s{2,}', remainder)
    segs = [s.strip(" _-") for s in segs if s.strip(" _-")]
    for seg in segs:
        if "insured_name" not in fields:
            words = seg.split()
            if (2 <= len(words) <= 6
                and not any(c.isdigit() for c in seg)
                and words[0][:1].isupper()):
                fields["insured_name"] = {
                    "value": seg, "confidence": 0.78,
                    "source": "stage1_can_column_insured",
                }
                continue
        if "loan_number" not in fields:
            clean = re.sub(r'[^0-9A-Za-z]', '', seg)
            digits = sum(c.isdigit() for c in clean)
            if digits >= 4 and 4 <= len(clean) <= 20:
                fields["loan_number"] = {
                    "value": clean, "confidence": 0.75,
                    "source": "stage1_can_column_loan",
                }


def _collect_address_below(lines: List[str], start: int,
                           skip_first_line: bool = False) -> str:
    """
    Collect an address from lines starting at `start`.
    If skip_first_line, skip line that is the insured name (no digits).
    Returns combined "street, city ST ZIP" or empty string.
    """
    parts = []
    begin = start
    if skip_first_line:
        # First line after label may be the insured name (skip if no digits)
        for k in range(start, min(start + 3, len(lines))):
            if any(c.isdigit() for c in lines[k]):
                begin = k
                break
        else:
            return ""
    for k in range(begin, min(begin + 3, len(lines))):
        ln = lines[k].strip()
        if not ln or len(ln) < 3:
            break
        # Stop at labels / boilerplate
        if re.match(r'(?i)(Loan|Policy|Notice|Dear|Premium|Primary|Risk)', ln):
            break
        parts.append(ln)
        # If line has a ZIP code, address is complete
        if re.search(r'\b\d{5}(?:-\d{4})?\b', ln):
            break
    if not parts:
        return ""
    addr = ", ".join(parts)
    # Quick validity: must have digits (street number) and letters
    if any(c.isdigit() for c in addr) and any(c.isalpha() for c in addr):
        return addr
    return ""


def _extract_recipient_mortgagee(lines: List[str], fields: Dict) -> None:
    """
    For DOI / CAN / UNWR docs: the mortgagee is the letter recipient block
    at the top of the document (before the main body).
    Scan first 20 lines for BANK/CREDIT UNION/MORTGAGE/LENDING near PO BOX + city/state.

    FIX: PO BOX and city/state may be on SEPARATE lines, so check a 5-line window
    for PO BOX presence AND city/state presence independently.
    ISAOA/ATIMA immediately after company name is a definitive mortgagee signal.
    """
    bank_keywords = ("bank", "credit union", "mortgage", "lending",
                     "servicing", "financial", "funding")
    for i in range(min(30, len(lines))):
        line = lines[i].strip()
        ll = line.lower()
        if not any(w in ll for w in bank_keywords):
            continue

        # Build a 5-line lookahead window
        lookahead = [lines[j] for j in range(i + 1, min(i + 6, len(lines)))]
        lookahead_lower = [l.lower() for l in lookahead]

        has_po_box = any("po box" in l or "p.o. box" in l for l in lookahead_lower)
        has_city_state = any(
            re.search(r"\b[A-Z]{2}\s+\d{5}", l, re.I)
            for l in lookahead
        )
        # ISAOA/ATIMA on the very next line is a definitive mortgagee signal
        # Also handle OCR variant "ISOA" (missing letter)
        has_isaoa_next = bool(
            lookahead and re.search(r"(?i)^(ISAOA|ISOA|ATIMA)", lookahead[0].strip())
        )

        if (has_po_box and has_city_state) or has_isaoa_next:
            bank_name = line
            if i > 0:
                prev = lines[i - 1].strip()
                prev_l = prev.lower()
                if (len(prev) > 2 and prev[0].isupper()
                    and not any(c.isdigit() for c in prev)
                    and any(w in prev_l for w in
                            ("bank", "national", "huntington", "the",
                             "first", "wells", "chase", "us "))):
                    bank_name = prev + " " + bank_name
            bank_name = re.sub(
                r"\s+(?:ITS|ISAOA|ISOA|ATIMA|SUCCESSORS|AND/OR|ASSIGNS).*$",
                "", bank_name, flags=re.I).strip()
            bank_name = re.sub(r"^[\d\s\"\'°³ae;:]+", "", bank_name).strip()
            bank_name = re.sub(r"\s+", " ", bank_name).strip()
            if len(bank_name) > 3:
                fields["mortgage_company"] = {
                    "value": bank_name,
                    "confidence": 0.86,
                    "source": "stage1_recipient_mortgagee",
                }
            return

        # ISAOA/ATIMA on same line (also handle OCR variant ISOA)
        if "isaoa" in ll or "isoa" in ll or "atima" in ll:
            bank_name = re.sub(
                r"\s+(?:ISAOA|ISOA|ATIMA|ISAOA\s*/?\ s*ATIMA|ISOA\s*/?\s*ATIMA|ITS\s+SCRS).*$",
                "", line, flags=re.I).strip()
            bank_name = re.sub(r"^[\d\s\"\'°³ae;:]+", "", bank_name).strip()
            if len(bank_name) > 3:
                fields["mortgage_company"] = {
                    "value": bank_name, "confidence": 0.78,
                    "source": "stage1_recipient_mortgagee",
                }
            return

def _fix_merged_mortgagee_insured(lines: List[str], fields: Dict) -> None:
    """
    Fix OCR-merged mortgagee+insured name lines.
    
    Pattern in document (two columns):
      Left column:  "1st Mortgagee:"         Right column: "NAMED INSURED AND ADDRESS:"
      Left column:  "EVERETT FINANCIAL..."    Right column: "ROBERT J BARRON and DANIEL PRYCE"
    
    OCR merges these into one line:
      "EVERETT FINANCIAL INC DBA SUPREME ROBERT J BARRON and DANIEL PRYCE"
    
    Detection: Find "Mortgagee:" and "NAMED INSURED" on same line or adjacent,
    then look at the data line below. If the current insured_name contains
    company words (INC, DBA, LLC, LENDING, FINANCIAL) at the start, the real
    insured is the person name AFTER the company portion.
    """
    # Check if current insured_name looks like it has mortgagee merged in
    if "insured_name" in fields:
        val = fields["insured_name"].get("value", "")
        vl = val.lower()
        # Detect merged pattern: contains company words AND person-name words
        company_indicators = ("financial", " inc ", " dba ", " llc", "lending",
                              "mortgage", "servicing", "funding", " bank")
        has_company = any(w in vl for w in company_indicators)
        if not has_company:
            return
        # Try to split at the boundary: company portion ends, person name begins
        # Look for pattern: "COMPANY WORDS PERSON_NAME"
        # Person names typically start with uppercase first name after company suffix
        # Try splitting after DBA + company name, before the person name
        # Pattern: "XXX DBA YYY  FIRST LAST and FIRST LAST"
        m = re.search(
            r'(?:ISAOA|LENDING|SUPREME|BANK|LLC|INC|COMPANY|CO\.?|CORP)\s+'
            r'([A-Z][a-z]+\s+[A-Z][\w\s]+(?:\s+and\s+[A-Z][\w\s]+)?)',
            val)
        if m:
            person = m.group(1).strip()
            # Validate it looks like a person name
            words = person.split()
            if 2 <= len(words) <= 8 and not any(c.isdigit() for c in person):
                fields["insured_name"] = {
                    "value": person,
                    "confidence": 0.88,
                    "source": "stage1_merged_split_insured",
                }
                return
        # Fallback: try splitting after "DBA XXX" pattern
        m2 = re.search(r'DBA\s+\w+\s+(.+)', val)
        if m2:
            rest = m2.group(1).strip()
            # Check if rest starts with uppercase name
            words = rest.split()
            if (len(words) >= 2
                and words[0][0].isupper()
                and not any(w.lower() in ("isaoa", "inc", "llc", "dba", "lending",
                                           "po", "box") for w in words[:2])):
                fields["insured_name"] = {
                    "value": rest,
                    "confidence": 0.85,
                    "source": "stage1_merged_split_insured",
                }
                return
    
    # Also check: if insured_name not yet found, look for "NAMED INSURED AND ADDRESS:"
    # on a line that also has "Mortgagee:" — this means next line has merged columns
    if "insured_name" not in fields:
        for i, line in enumerate(lines):
            if re.search(r'(?i)mortgagee.*named\s+insured|named\s+insured.*mortgagee', line):
                # Next line should have merged data
                if i + 1 < len(lines):
                    data = lines[i + 1].strip()
                    # Try to extract person name from the right portion
                    # Split on 2+ spaces if present
                    segs = re.split(r'\s{2,}', data)
                    for seg in reversed(segs):
                        seg = seg.strip()
                        words = seg.split()
                        if (2 <= len(words) <= 6
                            and not any(c.isdigit() for c in seg)
                            and words[0][0:1].isupper()
                            and not any(w.lower() in ("inc", "llc", "dba", "lending",
                                                       "financial", "mortgage", "bank")
                                        for w in words)):
                            fields["insured_name"] = {
                                "value": seg,
                                "confidence": 0.82,
                                "source": "stage1_merged_split_insured",
                            }
                            return
                break


def _clean_mortgage_value(lines: List[str], fields: Dict) -> None:
    """
    Clean mortgage_company value by stripping producer/agent name prefixes.
    
    Problem: "Michael Ames EVERETT FINANCIAL INC DBA SUPREME"
    The "Producer:" section name gets merged with Lien Holder in OCR.
    
    Also strips: "Copy Named Insured:", noise phrases like "boss Payee Mortgagee listed"
    """
    val = fields["mortgage_company"].get("value", "")
    if not val:
        return
    
    vl = val.lower()
    
    # Block complete noise values
    noise_phrases = ("copy named insured", "boss payee", "payee mortgagee listed",
                     "successors and/or assigns", "ee successors")
    if any(p in vl for p in noise_phrases):
        del fields["mortgage_company"]
        return
    
    # Strip producer/agent name prefix
    # Pattern: "Michael Ames EVERETT FINANCIAL INC DBA SUPREME"
    # Agent names are typically "First Last" (2 words, title case) before the
    # company name (ALL CAPS with INC/DBA/LLC etc.)
    m = re.match(
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+)\s+([A-Z]{2,}[\s\S]+)$', val)
    if m:
        agent_part = m.group(1)  # "Michael Ames"
        company_part = m.group(2)  # "EVERETT FINANCIAL INC DBA SUPREME"
        # Verify company part has entity indicators
        cl = company_part.lower()
        if any(w in cl for w in ("inc", "llc", "dba", "bank", "financial",
                                  "mortgage", "lending", "corp", "company")):
            fields["mortgage_company"]["value"] = company_part.strip()
            return
    
    # Also strip "Mortgage:" label prefix
    val = re.sub(r'^(?:Mortgage|Mortgagee|First\s+Mortgagee|1st\s+Mortgagee)\s*:\s*',
                 '', val, flags=re.I).strip()
    if val != fields["mortgage_company"]["value"]:
        fields["mortgage_company"]["value"] = val


def _extract_carrier_provided_by(lines: List[str], fields: Dict) -> None:
    """
    Extract carrier from 'Your policy provided by\\n<carrier name>' pattern.
    Allstate format: 'Your policy provided by' then 'Allstate Vehicle and Property'
    then 'Insurance Company' on the next line(s).
    """
    if "carrier_name" in fields:
        existing = fields["carrier_name"].get("value", "").lower()
        # Only override if current value is incomplete (e.g., just "INSURANCE COMPANY")
        if len(existing) > 20 and "insurance" in existing:
            return  # Already have a good carrier name

    for i, line in enumerate(lines):
        if re.search(r'(?i)(?:your\s+policy\s+provided\s+by|insurance\s+provided\s+by)', line):
            # Collect next 1-3 lines as carrier name
            parts = []
            for off in range(1, 4):
                if i + off >= len(lines):
                    break
                nxt = lines[i + off].strip()
                if not nxt or len(nxt) < 3:
                    break
                # Stop at boilerplate
                if re.match(r'(?i)(you may|contact|visit|phone|www\.|http)', nxt):
                    break
                parts.append(nxt)
                # Stop if we have "Company" or "Exchange" etc.
                if any(w in nxt.lower() for w in ("company", "exchange", "mutual",
                                                    "group", "corp")):
                    break
            if parts:
                carrier = " ".join(parts).strip()
                if len(carrier) > 5:
                    fields["carrier_name"] = {
                        "value": carrier, "confidence": 0.90,
                        "source": "stage1_carrier_provided_by",
                    }
            return


def _extract_insured_from_label(lines: List[str], fields: Dict) -> None:
    """
    Extract insured name from 'Name and address of Insured:' label.
    This is the authoritative insured name in CAN docs — overrides
    any incorrect block-level extraction that merged mortgagee+insured.
    """
    for i, line in enumerate(lines):
        if re.search(r'(?i)name\s+and\s+address\s+of\s+insured', line):
            if i + 1 < len(lines):
                name = lines[i + 1].strip()
                # Validate: must be 2+ words, mostly letters, not a street address
                words = name.split()
                if (2 <= len(words) <= 8
                    and not re.match(r'^\d', name)  # Not an address (starts with digit)
                    and name[0].isupper()):
                    fields["insured_name"] = {
                        "value": name, "confidence": 0.92,
                        "source": "stage1_name_addr_insured",
                    }
            return


def _clean_policy_number(fields: Dict) -> None:
    """
    Clean policy_number: strip POBOX prefix, trailing noise labels.
    Problem: OCR merges 'PO BOX 5023' with '807 356 710' → 'POBOX5023807356710'
    """
    if "policy_number" not in fields:
        return
    val = fields["policy_number"].get("value", "")

    # Strip POBOX prefix: remove "POBOX" + up to 4-digit box number
    # Must be careful not to eat into the actual policy number
    m = re.match(r'^(?:PO\s*BOX)\s*(\d{1,5})(.*)', val, re.I)
    if m:
        box_digits = m.group(1)
        remainder = m.group(2).strip()
        if remainder and len(remainder) >= 5:
            val = remainder
            fields["policy_number"]["value"] = val

    # Strip trailing "Loan Number" text
    val = re.sub(r'\s*Loan\s*Number.*$', '', val, flags=re.I).strip()

    # Strip accidental trailing year bleed from policy numbers.
    # Example: "99047002652020" where "2020" comes from nearby date text.
    if val.isdigit() and len(val) >= 12:
        suffix_year = val[-4:]
        if re.fullmatch(r'(?:19|20)\d{2}', suffix_year):
            prefix = val[:-4]
            if 8 <= len(prefix) <= 12:
                eff = str(fields.get("effective_date", {}).get("value", ""))
                exp = str(fields.get("expiration_date", {}).get("value", ""))
                known_years = set(re.findall(r'(?:19|20)\d{2}', f"{eff} {exp}"))
                if suffix_year in known_years:
                    val = prefix

    if val != fields["policy_number"]["value"]:
        fields["policy_number"]["value"] = val


def _extract_policy_from_account_label(lines: List[str], fields: Dict[str, Dict]) -> None:
    """
    Fallback for renewal docs where the policy id is printed as "Account Number".
    Guarded to avoid overriding normal policy-number extraction behavior.
    """
    if "policy_number" in fields:
        return

    joined = " ".join(lines).lower()
    # If explicit policy-number labels are present, do not use account fallback.
    if re.search(r"\bpolicy\s*(?:number|no\.?|#)\b", joined):
        return

    noise_trail = re.compile(
        r"\s+(?:agency|agent|eff\.?|effective|date|page|continued|loan|"
        r"policy|description|type|period|info|information)\b.*$",
        re.I,
    )

    for i, line in enumerate(lines):
        if not re.search(r"(?i)\b(?:your\s+)?account\s+number\b", line):
            continue

        candidate = ""
        if ":" in line:
            _, _, v = line.partition(":")
            candidate = v.strip()
        else:
            m = re.search(r"(?i)\baccount\s+number\b\s*([A-Z0-9][A-Z0-9\-\s]{3,})", line)
            if m:
                candidate = m.group(1).strip()

        if not candidate and i + 1 < len(lines):
            candidate = lines[i + 1].strip()

        candidate = noise_trail.sub("", _clean(candidate)).strip()
        compact = candidate.replace(" ", "")
        if _looks_like_policy(compact):
            fields["policy_number"] = {
                "value": compact,
                "confidence": 0.83,
                "source": "stage1_account_policy_fallback",
            }
            return


def _clean_insured_name(fields: Dict) -> None:
    """
    Normalize duplicated mirrored names from OCR merge artifacts.
    Example: "REBECCA borgess BORGESS, REBECCA" -> "BORGESS, REBECCA"
    """
    if "insured_name" not in fields:
        return
    raw = str(fields["insured_name"].get("value", "")).strip()
    if not raw:
        return

    raw = re.sub(r"\s+", " ", raw).strip()

    # Exact mirrored pattern: "FIRST LAST LAST, FIRST"
    m = re.match(
        r'^\s*([A-Za-z][A-Za-z\'\-]+)\s+([A-Za-z][A-Za-z\'\-]+)\s+\2,\s*\1\s*$',
        raw,
        re.I,
    )
    if m:
        cleaned = f"{m.group(2).upper()}, {m.group(1).upper()}"
        fields["insured_name"]["value"] = cleaned
        return

    # Token-level fallback for similar mirrored duplicates.
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*", raw)
    if len(toks) >= 4:
        t0, t1, t2, t3 = toks[0].lower(), toks[1].lower(), toks[2].lower(), toks[3].lower()
        if t0 == t3 and t1 == t2:
            fields["insured_name"]["value"] = f"{toks[1].upper()}, {toks[0].upper()}"


def _recover_named_insured_from_block(lines: List[str], fields: Dict) -> None:
    """
    Prefer a clean person-name line from labeled insured blocks when the current
    insured value is OCR-damaged.
    """
    current = fields.get("insured_name", {})
    current_val = str(current.get("value", "")).strip()
    current_src = current.get("source", "")
    should_override = (
        not current_val
        or _is_low_quality_name(current_val)
        or any(ch in current_val for ch in "[]{}|")
        or current_src in ("insured_block", "mailing_block")
    )
    if not should_override:
        return

    stop_words = (
        "location of insured property", "property location", "policy number",
        "policy period", "sales rep", "producer", "processed by", "naic number",
        "additional named insured", "forms and endorsements", "coverage",
        "loan number", "mortgage", "other interests", "other interest",
    )

    def _candidate_score(name: str) -> int:
        score = 0
        if _looks_like_name(name):
            score += 5
        if not _is_low_quality_name(name):
            score += 3
        if re.fullmatch(r"[A-Z][A-Z'\-]+(?:,\s*[A-Z][A-Z'\-]+)?(?:\s+[A-Z][A-Z'\-]+)*", name):
            score += 3
        if re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", name):
            score += 4
        if any(ch in name for ch in "[]{}|"):
            score -= 4
        if any(ch.isdigit() for ch in name):
            score -= 4
        return score

    for i, line in enumerate(lines):
        ll = line.lower()
        if not (
            "named insured and mailing address" in ll
            or "insured name and mailing address" in ll
            or "insured mailing name and address" in ll
        ):
            continue

        best_name = ""
        best_score = -999
        for j in range(i + 1, min(i + 6, len(lines))):
            candidate = lines[j].strip()
            if not candidate:
                continue
            cand_lower = candidate.lower()
            if any(word in cand_lower for word in stop_words):
                break
            if _looks_like_address(candidate):
                break
            score = _candidate_score(candidate)
            if score > best_score:
                best_name = candidate
                best_score = score

        if best_name and best_score >= 6:
            fields["insured_name"] = {
                "value": _normalize_name(best_name),
                "confidence": 0.94,
                "source": "stage1_named_insured_block",
            }
            return


def _recover_property_from_location_block(lines: List[str], fields: Dict) -> None:
    """
    Rebuild property address from a labeled property/location block and stop
    before adjacent labels bleed into the address.
    """
    current_val = str(fields.get("property_address", {}).get("value", "")).strip()
    current_lower = current_val.lower()
    current_is_contaminated = any(
        bad in current_lower for bad in (
            "primary residence", "premium payor", "flood risk", "rated zone",
            "community number", "policy period", "coverage", "mortgage",
        )
    )
    if current_val and not current_is_contaminated:
        return

    triggers = (
        "property location", "location of insured property", "property address",
        "risk location",
    )
    stop_words = (
        "primary residence", "premium payor", "flood risk", "current zone",
        "community number", "community name", "grandfathered", "post-firm",
        "program type", "building description", "policy period", "coverage",
        "forms and endorsements", "loan number", "mortgage", "other interests",
    )

    for i, line in enumerate(lines):
        ll = line.lower()
        if not any(t in ll for t in triggers):
            continue

        parts = []
        inline_value = ""
        if ":" in line:
            _, _, inline_value = line.partition(":")
            inline_value = inline_value.strip()
            if inline_value and not any(w in inline_value.lower() for w in stop_words):
                parts.append(inline_value)

        for j in range(i + 1, min(i + 5, len(lines))):
            candidate = lines[j].strip()
            if not candidate:
                continue
            cand_lower = candidate.lower()
            if any(word in cand_lower for word in stop_words):
                break
            if candidate.endswith(":"):
                break
            parts.append(candidate)

        if not parts:
            continue

        candidate_addr = _clean(" ".join(parts))
        if candidate_addr:
            fields["property_address"] = {
                "value": candidate_addr,
                "confidence": 0.9 if _looks_like_address(candidate_addr) else 0.78,
                "source": "stage1_location_block",
            }
            return


def _override_total_premium_from_explicit_label(lines: List[str], fields: Dict) -> None:
    """Prefer an explicit 'Total Premium' amount over incidental premium deltas."""
    for line in lines:
        m = re.search(r'(?i)\btotal\s+premium\s*:\s*(\$[\d,]+(?:\.\d{2})?)', line)
        if m:
            fields["total_premium"] = {
                "value": m.group(1),
                "confidence": 0.97,
                "source": "stage1_total_premium_label",
            }
            return


def _recover_mortgage_from_interest_table(lines: List[str], fields: Dict) -> None:
    """
    Recover mortgage company from table rows like:
      '1. Mortgagee    GATEWAY MORTGAGE'
    """
    current_val = str(fields.get("mortgage_company", {}).get("value", "")).strip()
    current_lower = current_val.lower()
    suspect_current = (
        not current_val
        or "payment plan" in current_lower
        or "mortgagee bill" in current_lower
        or "interest type" in current_lower
    )
    if not suspect_current:
        return

    for i, line in enumerate(lines):
        m = re.search(r'(?i)\b\d+\.\s*mortgagee\b\s+(.+)$', line)
        if not m:
            m = re.search(r'(?i)\bmortgagee\b\s*:\s*(.+)$', line)
        if not m:
            continue

        candidate = m.group(1).strip(" .:-")
        if candidate and not _looks_like_address(candidate):
            fields["mortgage_company"] = {
                "value": candidate,
                "confidence": 0.95,
                "source": "stage1_mortgage_interest_table",
            }
            return

        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt and not _looks_like_address(nxt) and len(nxt) > 3:
                fields["mortgage_company"] = {
                    "value": nxt,
                    "confidence": 0.93,
                    "source": "stage1_mortgage_interest_table_nextline",
                }
                return


def _prefer_brand_carrier_header(lines: List[str], fields: Dict) -> None:
    """
    For branded declaration headers like 'AAA Insurance' followed by
    'underwritten by ...', prefer the explicit brand line over a fuzzy-matched
    unrelated carrier.
    """
    current = fields.get("carrier_name", {})
    current_src = current.get("source", "")
    if current and "fuzzy_corrected" not in current_src:
        return

    for i, line in enumerate(lines[:6]):
        candidate = line.strip()
        cl = candidate.lower()
        if re.fullmatch(r'[A-Z]{2,6}\s+Insurance', candidate, re.I):
            if i + 1 < len(lines) and "underwritten by" in lines[i + 1].lower():
                fields["carrier_name"] = {
                    "value": candidate.upper(),
                    "confidence": 0.95,
                    "source": "stage1_brand_header",
                }
                return


def _repair_flood_renewal_dates(lines: List[str], fields: Dict) -> None:
    """
    Flood renewals often repeat the original month/day each year. If the current
    expiration matches the original month/day but the extracted effective date
    does not, align the effective month/day to the expiration month/day and keep
    the prior year.
    """
    joined = " ".join(lines).lower()
    if "flood policy declarations" not in joined and "nfip" not in joined:
        return

    eff = fields.get("effective_date", {}).get("value")
    exp = fields.get("expiration_date", {}).get("value")
    if not eff or not exp:
        return

    m_orig = re.search(
        r'(?i)original\s+new\s+business\s+effective\s+date\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        " ".join(lines),
    )
    if not m_orig:
        return

    def _parse_mmddyyyy(value: str):
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
            try:
                from datetime import datetime
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    eff_dt = _parse_mmddyyyy(str(eff))
    exp_dt = _parse_mmddyyyy(str(exp))
    orig_dt = _parse_mmddyyyy(m_orig.group(1))
    if not eff_dt or not exp_dt or not orig_dt:
        return

    if (exp_dt.month, exp_dt.day) != (orig_dt.month, orig_dt.day):
        return
    if (eff_dt.month, eff_dt.day) == (exp_dt.month, exp_dt.day):
        return
    if exp_dt.year - eff_dt.year not in (0, 1):
        return

    repaired = f"{exp_dt.month:02d}/{exp_dt.day:02d}/{exp_dt.year - 1:04d}"
    fields["effective_date"] = {
        "value": repaired,
        "confidence": max(fields.get("effective_date", {}).get("confidence", 0.0), 0.9),
        "source": "stage1_flood_renewal_repaired",
    }


def _is_mortgage_heading_noise(text: str) -> bool:
    ll = (text or "").lower()
    noise_phrases = (
        "additional interest information",
        "mortgagees additional interest information",
        "mortgagees/additional interest information",
        "direct rating information",
    )
    return any(p in ll for p in noise_phrases)


def _extract_nfip_direct_carrier(lines: List[str], fields: Dict) -> None:
    """
    Flood direct-rating docs often include 'NFIP Direct Rating Information'
    without a standard insurer header. Use a deterministic carrier fallback.
    """
    if fields.get("carrier_name", {}).get("value"):
        return
    joined = " ".join(lines).lower()
    if "nfip" in joined and ("direct rating" in joined or "drect ratng" in joined):
        fields["carrier_name"] = {
            "value": "NATIONAL FLOOD INSURANCE PROGRAM",
            "confidence": 0.86,
            "source": "stage1_nfip_direct",
        }


def _extract_carrier_full_scan(lines: List[str], fields: Dict) -> None:
    """
    Whole-document carrier fallback for packets where insurer appears later pages.
    """
    existing = fields.get("carrier_name", {})
    existing_val = existing.get("value", "")
    existing_src = existing.get("source", "")
    # Skip if we already have a high-quality carrier name
    # But DO override low-confidence brand-only fallbacks
    if existing_val and existing_src not in ("sweep_brand_fallback",):
        return

    # Strategy A: explicit '<name> Insurance Company/Exchange/Group/...'
    rx = re.compile(
        r'(?i)\b([A-Z][A-Z&.,/\-\s]{3,100}?)\s+'
        r'(INSURANCE|INDEMNITY|CASUALTY|ASSURANCE|MUTUAL)\s+'
        r'(COMPANY|EXCHANGE|GROUP|CORPORATION|CORP|CO)\b'
    )
    for line in lines:
        ll = line.lower()
        if any(bad in ll for bad in ("agency", "agent", "services", "producer", "underwriter")):
            continue
        m = rx.search(line.upper())
        if not m:
            continue
        candidate = f"{m.group(1).strip()} {m.group(2)} {m.group(3)}"
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,.;:-")
        if candidate and _looks_like_carrier(candidate):
            fields["carrier_name"] = {
                "value": candidate,
                "confidence": 0.88,
                "source": "stage1_carrier_full_scan",
            }
            return

    # Strategy B: catch title-case lines missed by uppercase regex.
    for line in lines:
        ll = line.lower()
        has_ins = any(w in ll for w in ("insurance", "indemnity", "casualty", "assurance"))
        has_ent = any(w in ll for w in ("company", "exchange", "group", "mutual", "corp"))
        if has_ins and has_ent and not any(b in ll for b in ("agency", "agent", "services", "producer")):
            candidate = _extract_carrier_name(line.strip())
            if candidate and _looks_like_carrier(candidate):
                fields["carrier_name"] = {
                    "value": candidate.upper(),
                    "confidence": 0.86,
                    "source": "stage1_carrier_full_scan_relaxed",
                }
                return


def _override_policy_from_label(lines: List[str], fields: Dict) -> None:
    """
    If policy_number looks suspect (has POBOX contamination, too long, etc.),
    look for a clean labeled 'Policy Number: XXX' in the document and use that.
    Also handles 'Policy number\\n886 700 444' (label and value on separate lines).
    """
    current = fields.get("policy_number", {}).get("value", "")
    current_source = fields.get("policy_number", {}).get("source", "")
    # Check if current value looks suspect
    suspect = (
        len(current) > 15  # Too long for a typical policy number
        or re.search(r'(?i)po\s*box', current)  # Still has PO BOX
        or not re.search(r'\d', current)  # No digits at all
        or current_source == "block_combined"  # Block combined values are often noisy
        or re.search(r'(?i)(agency|agent|eff|effective|date|loan)', current)  # Trailing noise
    )
    if not suspect:
        return

    _NOISE_TRAIL = re.compile(
        r'\s+(?:agency|agent|eff\.?|effective|date|page|continued|loan|'
        r'policy|description|type|period|number|info|information)\b.*$', re.I
    )

    # Strategy A: "Policy number: 886 700 444" on same line
    for line in lines:
        m = re.search(r'(?i)policy\s+number\s*:\s*([A-Z0-9][\w\s\-]{3,25})', line)
        if m:
            val = _NOISE_TRAIL.sub('', m.group(1).strip()).strip()
            # Also hard-stop at the first sequence that looks like a new label
            # e.g. "063 078 674 Policy descrip" → stop before "Policy"
            val = re.sub(r'\s+[A-Z][a-z].*$', '', val).strip()
            parts = val.split()
            if all(p.isdigit() for p in parts):
                val = "".join(parts)
            else:
                val = re.sub(r'(?<=\d)\s+(?=\d)', '', val)
            if val and len(val) >= 4:
                fields["policy_number"] = {
                    "value": val, "confidence": 0.95,
                    "source": "stage1_labeled_policy",
                }
                return

    # Strategy B: Label on one line, value on the next
    # e.g. "Policy number\n886 700 444"
    for i, line in enumerate(lines):
        if re.search(r'(?i)^policy\s+number\s*:?\s*$', line.strip()):
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                nxt_clean = _NOISE_TRAIL.sub('', nxt).strip()
                parts = nxt_clean.split()
                if all(p.isdigit() for p in parts) and 2 <= len(parts) <= 4:
                    val = "".join(parts)
                else:
                    val = nxt_clean.replace(" ", "")
                if val and len(val) >= 4 and re.search(r'\d', val):
                    fields["policy_number"] = {
                        "value": val, "confidence": 0.95,
                        "source": "stage1_labeled_policy_nextline",
                    }
                    return

    # Strategy C: Two-column OCR — "Policy number:" label found but value is
    # on a DIFFERENT line (not adjacent) due to column extraction order.
    # E.g., OCR extracts left column first: "July 2020\n123456789\nMailing address:"
    # then right column: "Policy number:\n24-hour claim..."
    # The value "123456789" is an orphaned pure-digit line in the header area.
    # Also handles merged-column artifacts like "123456789 24-hour claim reporting"
    has_policy_label = any(re.search(r'(?i)policy\s+number\s*:', line) for line in lines)
    if has_policy_label:
        # Find orphaned numeric values in the first 40 lines (header area)
        for line in lines[:40]:
            candidate = line.strip()
            if not candidate:
                continue
            # Strategy C1: Pure numeric standalone line
            candidate_clean = candidate.replace(" ", "").replace("-", "")
            if candidate_clean.isdigit() and _looks_like_policy(candidate_clean):
                if not DATE_RE.search(candidate) and not _is_phone_number(candidate):
                    fields["policy_number"] = {
                        "value": candidate_clean,
                        "confidence": 0.82,
                        "source": "stage1_orphaned_policy_value",
                    }
                    return
            # Strategy C2: Line starts with digits followed by column-merge noise
            # e.g., "123456789 24-hour claim reporting" or "12345678924-hour..."
            m_leading = re.match(r'^(\d{6,16})\s*[-\s]?\s*\d{0,2}[-\s]?(?:hour|h\b)', candidate, re.I)
            if m_leading:
                pol_val = m_leading.group(1)
                if _looks_like_policy(pol_val):
                    fields["policy_number"] = {
                        "value": pol_val,
                        "confidence": 0.80,
                        "source": "stage1_orphaned_policy_merged",
                    }
                    return
            # Strategy C3: Leading digits before any alpha chars on the line
            m_digits = re.match(r'^(\d{6,16})(?:\s|[^0-9A-Za-z]|[A-Za-z])', candidate)
            if m_digits:
                pol_val = m_digits.group(1)
                if _looks_like_policy(pol_val) and not _is_phone_number(pol_val):
                    if not DATE_RE.search(candidate[:len(pol_val)+5]):
                        fields["policy_number"] = {
                            "value": pol_val,
                            "confidence": 0.78,
                            "source": "stage1_orphaned_policy_leading_digits",
                        }
                        return


def _clean_mortgage_suffixes(fields: Dict) -> None:
    """
    Clean mortgage_company: strip ITS SCRS/ISAOA/ISOA/ATIMA/ASSIGNS suffixes.
    These are legal designations, not part of the company name.
    """
    if "mortgage_company" not in fields:
        return
    val = fields["mortgage_company"].get("value", "")
    # Strip "ITS SCRS &/OR ASSIGNS ATIMA" and similar
    # Also handle OCR variant "ISOA" (missing letter from ISAOA)
    cleaned = re.sub(
        r'\s+(?:ITS\s+SCRS|ISAOA|ISOA|ATIMA|ITS\s+SUCCESSORS|'
        r'&/OR\s+ASSIGNS|AND/OR\s+ASSIGNS|SUCCESSORS\s+AND/OR\s+ASSIGNS)'
        r'[\s&/OR]*(?:ATIMA|ISAOA|ISOA|ASSIGNS)*\s*$',
        '', val, flags=re.I).strip()
    # Also strip ",  ISOA/ATIMA" or ", ISAOA/ATIMA" at end (with comma)
    cleaned = re.sub(
        r',?\s*(?:ISAOA|ISOA)\s*/?\s*(?:ATIMA)?\s*$',
        '', cleaned, flags=re.I).strip()
    if cleaned and cleaned != val:
        fields["mortgage_company"]["value"] = cleaned


def _extract_loan_next_line(lines: List[str], fields: Dict) -> None:
    """
    Handle 'Loan Number:\\n9102030422' where label and value are on separate lines.
    Overrides mortgage_block loan numbers which are often wrong.
    """
    existing = fields.get("loan_number", {})
    existing_source = existing.get("source", "")
    # Only override if current value is from a low-confidence source
    if existing_source in ("inline",) and existing.get("confidence", 0) >= 0.95:
        return  # Already have a good labeled loan number

    for i, line in enumerate(lines):
        if re.search(r'(?i)loan\s+number\s*:\s*$', line.rstrip()):
            # Value is on the next line
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                digits = re.sub(r'[^0-9]', '', nxt)
                if 7 <= len(digits) <= 20:
                    fields["loan_number"] = {
                        "value": digits, "confidence": 0.95,
                        "source": "stage1_loan_nextline",
                    }
                    return
        # Also handle: "Loan Number: 9102030422" on same line
        m = re.search(r'(?i)loan\s+number\s*:\s*(\d{7,20})', line)
        if m:
            if existing_source in ("mortgage_block", "sweep", ""):
                fields["loan_number"] = {
                    "value": m.group(1), "confidence": 0.96,
                    "source": "stage1_loan_labeled",
                }
                return

    # Strategy: Table-header loan number extraction (Adirondack format)
    # Table header: "Policy Type    Loan Number    Mortgagee Premium"
    # Data row:     "PACKAGE        7000654501     $1,151"
    # No colon — "Loan Number" is a column header, value is on the next line
    for i, line in enumerate(lines):
        ll = line.lower()
        # Check for table header containing "loan number" without colon
        if "loan number" in ll and ":" not in line:
            # Look at next 1-3 lines for the data row
            for j in range(i + 1, min(i + 4, len(lines))):
                row = lines[j].strip()
                if not row:
                    continue
                # Split row by multiple spaces (table columns) or extract tokens
                tokens = re.split(r'\s{2,}', row)
                for token in tokens:
                    token = token.strip()
                    d = ''.join(c for c in token if c.isdigit())
                    if d and _looks_like_loan_number(d) and len(d) >= 7:
                        # Verify this isn't a dollar amount
                        if not re.search(r'^\$', token.strip()):
                            fields["loan_number"] = {
                                "value": d, "confidence": 0.93,
                                "source": "stage1_loan_table_header",
                            }
                            return
                break  # Only process the first matching header


def _extract_carrier_page2(lines: List[str], fields: Dict) -> None:
    """
    Recover carrier name from page 2 — look for a company-style name
    within 3 lines before a 'Policy Number:' label on a later page.
    Example: "ALLIED TRUST\\nPolicy Number: 757051"
    """
    for i, line in enumerate(lines):
        # Only look in the second half of the document
        if i < len(lines) // 2:
            continue
        if re.search(r'(?i)policy\s+number\s*:', line):
            # Scan up to 3 lines before for a company name
            for back in range(1, 4):
                if i - back < 0:
                    break
                candidate = lines[i - back].strip()
                cl = candidate.lower()
                # Must look like a company name (2+ words, uppercase, no digits)
                if (len(candidate) > 3
                    and len(candidate.split()) >= 2
                    and candidate[0].isupper()
                    and not any(c.isdigit() for c in candidate)
                    and not re.search(r'(?i)po\s+box|please|see|following|important', cl)
                    and not re.search(r'(?i)^(dwelling\s+policy|homeowners?\s+policy|'
                                      r'amended\s+declarations|policy\s+change|'
                                      r'declarations?\s+page|additional\s+dwelling|'
                                      r'renewal\s+notice|cancellation\s+notice)', cl)):
                    fields["carrier_name"] = {
                        "value": candidate, "confidence": 0.85,
                        "source": "stage1_carrier_page2",
                    }
                    return
            break


def _clean_carrier_ocr_bleed(fields: Dict) -> None:
    """
    Clean carrier_name: strip trailing single OCR-bleed character.
    E.g. "ALLSTATE INDEMNITY COMPANYD" → "ALLSTATE INDEMNITY COMPANY"
    Also: fuzzy-match garbled OCR carrier names to known carriers.
    E.g. "BOWARE QSE SPECATY INSURANCE COMPANY" → "QBE SPECIALTY INSURANCE COMPANY"
    """
    if "carrier_name" not in fields:
        return
    val = fields["carrier_name"].get("value", "")
    # Strip trailing single uppercase letter appended without space
    cleaned = re.sub(
        r'(COMPANY|CORP|INC|CO|GROUP|MUTUAL|EXCHANGE|INDEMNITY|CASUALTY|FIRE|GENERAL)([A-Z])$',
        r'\1', val
    )
    # Also strip trailing " X" (single uppercase letter with leading space)
    cleaned = re.sub(r'\s+[A-Z]$', '', cleaned).strip()
    if cleaned and cleaned != val:
        fields["carrier_name"]["value"] = cleaned
        val = cleaned
    
    # Fuzzy-match against known carriers to fix OCR garbling
    # E.g., "BOWARE QSE SPECATY INSURANCE COMPANY" → "QBE SPECIALTY INSURANCE COMPANY"
    _KNOWN_CARRIERS_FUZZY = [
        "QBE SPECIALTY INSURANCE COMPANY",
        "ALLSTATE INDEMNITY COMPANY",
        "ALLSTATE INSURANCE COMPANY",
        "ALLSTATE VEHICLE AND PROPERTY INSURANCE COMPANY",
        "ALLSTATE FIRE AND CASUALTY INSURANCE COMPANY",
        "STATE FARM FIRE AND CASUALTY COMPANY",
        "NATIONWIDE MUTUAL INSURANCE COMPANY",
        "NATIONWIDE MUTUAL FIRE INSURANCE COMPANY",
        "ALLIED PROPERTY AND CASUALTY INSURANCE COMPANY",
        "TRAVELERS HOME AND MARINE INSURANCE COMPANY",
        "TRAVELERS INDEMNITY COMPANY",
        "LIBERTY MUTUAL FIRE INSURANCE COMPANY",
        "LIBERTY MUTUAL INSURANCE COMPANY",
        "FARMERS INSURANCE EXCHANGE",
        "TEXAS FARMERS INSURANCE COMPANY",
        "SAFECO INSURANCE COMPANY OF AMERICA",
        "SAFECO INSURANCE COMPANY OF ILLINOIS",
        "ERIE INSURANCE EXCHANGE",
        "ERIE INSURANCE COMPANY",
        "AMERICAN FAMILY INSURANCE COMPANY",
        "AMERICAN BANKERS INSURANCE COMPANY OF FLORIDA",
        "AMERICAN MODERN PROPERTY AND CASUALTY INSURANCE COMPANY",
        "AMCO INSURANCE COMPANY",
        "CITIZENS PROPERTY INSURANCE CORPORATION",
        "UNIVERSAL PROPERTY AND CASUALTY INSURANCE COMPANY",
        "FEDERATED NATIONAL INSURANCE COMPANY",
        "SOUTHERN OAK INSURANCE COMPANY",
        "TOWER HILL PRIME INSURANCE COMPANY",
        "TOWER HILL SIGNATURE INSURANCE COMPANY",
        "PEOPLES TRUST INSURANCE COMPANY",
        "HERITAGE PROPERTY AND CASUALTY INSURANCE COMPANY",
        "FLORIDA PENINSULA INSURANCE COMPANY",
        "SECURITY FIRST INSURANCE COMPANY",
        "HOMEOWNERS CHOICE INSURANCE COMPANY",
        "AEGIS SECURITY INSURANCE COMPANY",
        "ADIRONDACK INSURANCE EXCHANGE",
        "HARTFORD FIRE INSURANCE COMPANY",
        "THE HANOVER INSURANCE COMPANY",
        "CHUBB INDEMNITY INSURANCE COMPANY",
        "AMICA MUTUAL INSURANCE COMPANY",
        "KEMPER INDEPENDENCE INSURANCE COMPANY",
        "MERCURY INSURANCE COMPANY",
        "SHELTER MUTUAL INSURANCE COMPANY",
        "USAA CASUALTY INSURANCE COMPANY",
        "AUTO-OWNERS INSURANCE COMPANY",
        "CSAA INSURANCE EXCHANGE",
        "ENCOMPASS INSURANCE COMPANY",
        "ENCOMPASS INDEMNITY COMPANY",
        "AMERICAN STRATEGIC INSURANCE COMPANY",
        "ORCHID UNDERWRITERS AGENCY",
        "ANCHOR SPECIALTY INSURANCE COMPANY",
    ]
    try:
        from difflib import SequenceMatcher
        val_upper = val.upper()
        best_match, best_score = None, 0
        
        # Extract the brand/first word from the input for brand-preference scoring
        val_words = val_upper.split()
        val_brand = val_words[0] if val_words else ""
        
        for known in _KNOWN_CARRIERS_FUZZY:
            score = SequenceMatcher(None, val_upper, known).ratio()
            # CRITICAL: Boost score when the known carrier starts with the same brand
            # This prevents "ALLSTATE INSURANCE COMPANY" matching "ERIE INSURANCE COMPANY"
            # (which has higher raw similarity due to shorter name)
            known_brand = known.split()[0] if known.split() else ""
            if val_brand and val_brand == known_brand:
                score += 0.15  # Brand match bonus
            if score > best_score:
                best_match, best_score = known, score
        # Threshold: 60% similarity is strong enough for OCR correction
        # but only if the current value contains "insurance" or similar keywords
        val_lower = val.lower()
        has_ins_word = any(w in val_lower for w in ('insurance', 'indemnity', 'casualty', 'assurance', 'exchange', 'mutual'))
        has_ins_abbrev = bool(re.search(r'\bins\b', val_lower)) or bool(re.search(r'\bcas\b', val_lower))
        has_prop_abbrev = " prop " in f" {val_lower} "
        has_ins_signal = has_ins_word or has_ins_abbrev or has_prop_abbrev
        if best_score > 0.60 and has_ins_signal and best_match:
            fields["carrier_name"]["value"] = best_match
            fields["carrier_name"]["confidence"] = min(fields["carrier_name"].get("confidence", 0.90), 0.92)
            fields["carrier_name"]["source"] = fields["carrier_name"].get("source", "") + "_fuzzy_corrected"
    except ImportError:
        pass  # difflib should always be available, but just in case


def _extract_mortgage_from_third_party(lines: List[str], fields: Dict) -> None:
    """
    Extract mortgage company from 'Third party interest added' lines in DOI docs.
    Pattern: "Third party interest added: Mortgagee, NORTHPOINTE BANK ITS SUCCESSORS AND/OR ASSIGNS ATIMA, 3183000166"
    Extracts: "NORTHPOINTE BANK"
    
    Only overrides if no mortgage_company yet OR current value looks suspect.
    """
    for i, line in enumerate(lines):
        m = re.search(
            r'(?i)third\s+party\s+interest\s+added\s*:\s*'
            r'(?:mortgagee|loss\s+payee)\s*,\s*(.+)',
            line
        )
        if not m:
            continue
        
        raw = m.group(1).strip()
        # Strip ISAOA/ATIMA/SUCCESSORS/ASSIGNS suffixes and trailing loan number
        # Handle patterns like:
        #   "NORTHPOINTE BANK ITS SUCCESSORS AND/OR ASSIGNS ATIMA, 3183000166"
        #   "COMPANY ITS SUCCESSORS AND/OR ASSIGNS, 12345"
        #   "COMPANY ISAOA ATIMA, 12345"
        name = re.sub(
            r'\s+ITS\s+SUCCESSORS?\s+AND[/\s]+OR\s+ASSIGNS\b.*$',
            '', raw, flags=re.I
        ).strip()
        name = re.sub(
            r'\s+(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA).*$',
            '', name, flags=re.I
        ).strip()
        name = re.sub(r',?\s*\d{6,}$', '', name).strip()
        name = name.rstrip(",. ")
        
        if name and len(name) > 3:
            existing = fields.get("mortgage_company", {})
            existing_val = existing.get("value", "")
            # Override if no value yet, or current value contains noise
            if (not existing_val
                    or "third party" in existing_val.lower()
                    or "interest added" in existing_val.lower()
                    or len(existing_val) > 80):
                fields["mortgage_company"] = {
                    "value": name,
                    "confidence": 0.96,
                    "source": "stage1_third_party_mortgage",
                }
            return


def _extract_loan_from_third_party(lines: List[str], fields: Dict) -> None:
    """
    Extract loan number from 'Third party interest added/removed' lines.
    This is the MOST AUTHORITATIVE source for loan numbers in DOI documents
    because the loan number is explicitly stated next to the mortgagee name.
    
    Pattern (same line):
      "Third party interest added: Mortgagee, NORTHPOINTE BANK ... ATIMA, 3183000166"
    Pattern (next line):
      "Third party interest added: Mortgagee, NORTHPOINTE BANK ... ATIMA,"
      "3183000166"
    
    ALWAYS overrides existing loan_number if found (highest authority).
    """
    for i, line in enumerate(lines):
        # Match "third party interest added/removed: Mortgagee, ..."
        if not re.search(r'(?i)third\s+party\s+interest\s+(?:added|removed)\s*:', line):
            continue

        # Strategy A: loan number at end of same line after last comma
        m = re.search(
            r'(?i)third\s+party\s+interest\s+(?:added|removed)\s*:\s*'
            r'(?:mortgagee|loss\s+payee)\s*,\s*.+?,\s*(\d{7,15})\s*$',
            line
        )
        if m:
            loan = m.group(1).strip()
            fields["loan_number"] = {
                "value": loan,
                "confidence": 0.97,
                "source": "stage1_third_party_interest",
            }
            return

        # Strategy B: loan number on the NEXT line (OCR split)
        # Line ends with comma or ATIMA/ISAOA, loan digits on next line
        if re.search(r'(?i)(?:ATIMA|ISAOA|ASSIGNS)\s*,?\s*$', line):
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if re.match(r'^\d{7,15}$', nxt):
                    fields["loan_number"] = {
                        "value": nxt,
                        "confidence": 0.96,
                        "source": "stage1_third_party_interest_nextline",
                    }
                    return

        # Strategy C: loan number embedded in the line but not at the very end
        # e.g. "Third party interest added: Mortgagee, COMPANY ATIMA, 3183000166 "
        # (trailing whitespace or OCR artifacts)
        m2 = re.search(
            r'(?i)(?:ATIMA|ISAOA|ASSIGNS)\s*,\s*(\d{7,15})',
            line
        )
        if m2:
            fields["loan_number"] = {
                "value": m2.group(1).strip(),
                "confidence": 0.96,
                "source": "stage1_third_party_interest_embedded",
            }
            return

        # Strategy D: any trailing digit sequence after last comma on the line
        # Handles cases where ATIMA/ISAOA may not be present but loan number
        # is at the end: "Third party interest added: Mortgagee, COMPANY, 3183000166"
        m3 = re.search(r',\s*(\d{7,15})\s*$', line)
        if m3:
            fields["loan_number"] = {
                "value": m3.group(1).strip(),
                "confidence": 0.95,
                "source": "stage1_third_party_interest_trailing",
            }
            return


def _extract_mortgage_from_doi_address_block(lines: List[str], fields: Dict) -> None:
    """
    Extract mortgage company from DOI mailing address block at top of letter.
    Many DOI documents are mailed to the mortgagee in this format:
    
        <barcode/reference number>
        COMPANY NAME LLC
        ITS SUCCESSORS AND/OR ASSIGNS ATIMA
        PO BOX xxxx
        CITY ST ZIP
    
    Or:
        COMPANY NAME
        ISAOA/ATIMA
        PO BOX xxxx
        CITY ST ZIP
    
    Only sets mortgage_company if not already set or current value is suspect.
    """
    if "mortgage_company" in fields:
        existing_val = fields["mortgage_company"].get("value", "")
        # Don't override good values
        if existing_val and "successors" not in existing_val.lower() and "assigns" not in existing_val.lower():
            return

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Look for "ITS SUCCESSORS AND/OR ASSIGNS" or "ISAOA/ATIMA" line
        if re.match(r'(?i)^(?:ITS\s+)?SUCCESSORS?\s+AND[/\s]+OR\s+ASSIGNS', stripped):
            # Company name is on the previous non-empty line
            if i > 0:
                prev = lines[i - 1].strip()
                # Skip barcode/reference number lines (all digits/letters mixed)
                if prev and not re.match(r'^[\d\s]+$', prev):
                    # Strip leading reference numbers like "000061EI310CCL1002480300 050030 001"
                    # These are barcode reference strings - long alphanumeric sequences
                    if re.match(r'^[A-Z0-9]{15,}', prev):
                        # This line is a barcode/reference, try the line before
                        if i > 1:
                            prev = lines[i - 2].strip()
                        else:
                            continue
                    # Validate: looks like a company name
                    if (prev and len(prev) > 3
                            and not re.match(r'^[\d\s]+$', prev)
                            and not re.search(r'(?i)^(policy|loan|insured|date|page|dear)', prev)
                            and not re.search(r'(?i)insurance\s+(company|group|exchange)', prev)):
                        fields["mortgage_company"] = {
                            "value": prev,
                            "confidence": 0.92,
                            "source": "stage1_doi_address_block",
                        }
                        return
        
        # Also handle: "ISAOA/ATIMA" or "ISOA/ATIMA" alone on a line (without SUCCESSORS)
        if re.match(r'(?i)^(?:ISAOA|ISOA)\s*/?\s*ATIMA\s*$', stripped):
            if i > 0:
                prev = lines[i - 1].strip()
                if re.match(r'^[A-Z0-9]{15,}', prev) and i > 1:
                    prev = lines[i - 2].strip()
                if (prev and len(prev) > 3
                        and not re.match(r'^[\d\s]+$', prev)
                        and not re.search(r'(?i)^(policy|loan|insured|date|page|dear)', prev)):
                    # CRITICAL: Strip leading agent/reference codes like "087DF"
                    prev = re.sub(r'^\d{2,5}[A-Z]{1,3}\s+', '', prev).strip()
                    if prev and len(prev) > 3:
                        fields["mortgage_company"] = {
                            "value": prev,
                            "confidence": 0.90,
                            "source": "stage1_doi_address_block",
                        }
                    return


def _extract_policy_period_dates(lines: List[str], fields: Dict) -> None:
    """
    Recover effective/expiration dates from Policy Period blocks.
    Handles both same-line and split-line layouts, e.g.:

      Policy Period
      From: 01/01/2020 To: 01/01/2021
      12:01 A.M. Standard Time
    """
    # Keep strong existing values
    has_eff = "effective_date" in fields and fields["effective_date"].get("value")
    has_exp = "expiration_date" in fields and fields["expiration_date"].get("value")
    if has_eff and has_exp:
        return

    date_pat = re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})')

    # Strategy A: find a "Policy Period" anchor and parse nearby lines.
    for i, line in enumerate(lines):
        if "policy period" not in line.lower():
            continue
        window = " ".join(lines[i:i + 5])

        # Prefer explicit From/To mapping if present.
        m = re.search(
            r'(?is)from[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}).*?to[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            window,
        )
        if m:
            if not has_eff:
                fields["effective_date"] = {
                    "value": m.group(1),
                    "confidence": 0.95,
                    "source": "stage1_policy_period_block",
                }
                has_eff = True
            if not has_exp:
                fields["expiration_date"] = {
                    "value": m.group(2),
                    "confidence": 0.95,
                    "source": "stage1_policy_period_block",
                }
                has_exp = True
            if has_eff and has_exp:
                return

        # Try abbreviated month date range: "OCT-05-2021 to OCT-05-2022"
        if not (has_eff and has_exp):
            m_abbrev = re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-]+\d{1,2}[\s,\-]+\d{4})'
                r'\s+to\s+'
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-]+\d{1,2}[\s,\-]+\d{4})',
                window, re.I
            )
            if m_abbrev:
                if not has_eff:
                    fields["effective_date"] = {
                        "value": m_abbrev.group(1),
                        "confidence": 0.95,
                        "source": "stage1_policy_period_block",
                    }
                    has_eff = True
                if not has_exp:
                    fields["expiration_date"] = {
                        "value": m_abbrev.group(2),
                        "confidence": 0.95,
                        "source": "stage1_policy_period_block",
                    }
                    has_exp = True
                if has_eff and has_exp:
                    return

        # Try dash-separated date range: "4/30/2020 - 4/30/2021"
        if not (has_eff and has_exp):
            m_dash = re.search(
                r'([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\s*[-–]\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
                window,
            )
            if m_dash:
                if not has_eff:
                    fields["effective_date"] = {
                        "value": m_dash.group(1),
                        "confidence": 0.95,
                        "source": "stage1_policy_period_block",
                    }
                    has_eff = True
                if not has_exp:
                    fields["expiration_date"] = {
                        "value": m_dash.group(2),
                        "confidence": 0.95,
                        "source": "stage1_policy_period_block",
                    }
                    has_exp = True
                if has_eff and has_exp:
                    return

        # Fallback: first two dates in the nearby block.
        dates = date_pat.findall(window)
        if len(dates) >= 2:
            if not has_eff:
                fields["effective_date"] = {
                    "value": dates[0],
                    "confidence": 0.92,
                    "source": "stage1_policy_period_nearby",
                }
                has_eff = True
            if not has_exp:
                fields["expiration_date"] = {
                    "value": dates[1],
                    "confidence": 0.92,
                    "source": "stage1_policy_period_nearby",
                }
                has_exp = True
            if has_eff and has_exp:
                return

    # Strategy B: global fallback for "From ... To ..." anywhere in document.
    if not (has_eff and has_exp):
        all_text = " ".join(lines)
        m = re.search(
            r'(?is)\bfrom[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}).*?\bto[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            all_text,
        )
        if m:
            if not has_eff:
                fields["effective_date"] = {
                    "value": m.group(1),
                    "confidence": 0.90,
                    "source": "stage1_from_to_fallback",
                }
            if not has_exp:
                fields["expiration_date"] = {
                    "value": m.group(2),
                    "confidence": 0.90,
                    "source": "stage1_from_to_fallback",
                }


def _upgrade_brand_to_full_carrier(lines: List[str], fields: Dict) -> None:
    """
    Post-extraction: if carrier_name is a single-word brand (e.g., "ENCOMPASS",
    "FARMERS", "HARTFORD"), scan the document for the full carrier name
    (e.g., "Encompass Indemnity Company") and upgrade.
    """
    if "carrier_name" not in fields:
        return
    val = fields["carrier_name"].get("value", "").strip()
    # Only upgrade if carrier is 1-2 words (brand-only)
    if not val or len(val.split()) > 2:
        return
    brand = val.lower().rstrip(".,;:-")
    
    # Scan ALL lines for a full carrier name containing this brand
    for line in lines:
        ll = line.lower()
        if brand not in ll:
            continue
        # Must also have insurer keyword + company type
        has_ins = any(w in ll for w in ('insurance', 'indemnity', 'casualty', 'assurance'))
        has_ent = any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp'))
        has_bad = any(w in ll for w in ('agency', 'agent', 'services', 'producer'))
        if has_ins and has_ent and not has_bad:
            carrier_val = _extract_carrier_name(line.strip())
            if carrier_val and _looks_like_carrier(carrier_val):
                if brand in carrier_val.lower():
                    fields["carrier_name"] = {
                        "value": carrier_val.upper(),
                        "confidence": 0.93,
                        "source": "brand_upgrade",
                    }
                    return


def _clean_policy_column_merge(fields: Dict) -> None:
    """
    Post-extraction cleanup: remove column-merge noise from policy_number.
    Handles all OCR merge variants: digits+alpha, digits+hyphen+alpha, pure trailing digits.
    """
    if "policy_number" not in fields:
        return
    val = fields["policy_number"].get("value", "")
    if not val:
        return
    
    # Pattern 1: pure-digit prefix followed by alpha noise (with optional hyphen)
    # E.g., "12345678924-hourclaimreporting" or "12345678924hourclaimreporti"
    m_alpha = re.search(r'[a-zA-Z]{3,}', val)
    if m_alpha and m_alpha.start() > 0:
        prefix = val[:m_alpha.start()].rstrip('-').rstrip()
        if sum(c.isalpha() for c in prefix) == 0:  # only pure-digit prefixes
            digits_only = re.sub(r'[^0-9]', '', prefix)
            if len(digits_only) >= 8:
                for strip_len in (3, 2, 1, 0):
                    candidate = digits_only[:len(digits_only)-strip_len] if strip_len else digits_only
                    if len(candidate) >= 6 and _looks_like_policy(candidate):
                        if strip_len > 0:
                            stripped = digits_only[len(digits_only)-strip_len:]
                            alpha_start = val[m_alpha.start():m_alpha.start()+10].lower()
                            combined = stripped + alpha_start
                            if any(combined.startswith(p) for p in ("24hour", "24h", "24claim", "800", "12hour", "1201")):
                                fields["policy_number"]["value"] = candidate
                                fields["policy_number"]["source"] += "_cleaned"
                                return
                        else:
                            fields["policy_number"]["value"] = candidate
                            fields["policy_number"]["source"] += "_cleaned"
                            return

    # Pattern 2: digits + lowercase alpha (no separator)
    m = re.match(r'^(\d{6,16})(\d{0,2}[a-z]{3,})', val)
    if m:
        pol_part = m.group(1)
        noise_digits = re.match(r'^(\d+)', m.group(2))
        if noise_digits:
            if _looks_like_policy(pol_part):
                fields["policy_number"]["value"] = pol_part
                fields["policy_number"]["source"] += "_cleaned"
                return
        elif _looks_like_policy(pol_part):
            fields["policy_number"]["value"] = pol_part
            fields["policy_number"]["source"] += "_cleaned"
            return
    
    # Pattern 3: alphanumeric policy + Title-case noise
    m2 = re.match(r'^([A-Z0-9\-]{6,25}?)([A-Z][a-z]{2,}.*)', val)
    if m2:
        pol_part = m2.group(1)
        if _looks_like_policy(pol_part):
            fields["policy_number"]["value"] = pol_part
            fields["policy_number"]["source"] += "_cleaned"
            return
    
    # Pattern 4: pure digits with trailing "24"/"800"/"12" from adjacent column
    # E.g., "12345678924" = "123456789" + "24" from "24-hour claim reporting"
    if val.isdigit() and len(val) >= 10:
        for trail in ("24", "800", "12"):
            tl = len(trail)
            if val.endswith(trail) and len(val) - tl >= 6:
                shorter = val[:-tl]
                if _looks_like_policy(shorter):
                    fields["policy_number"]["value"] = shorter
                    fields["policy_number"]["source"] += "_trail_cleaned"
                    return


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
    _extract_mortgage_from_third_party(lines, extractor.fields)  # ← DOI: authoritative mortgage from "Third party interest"
    _extract_loan_from_third_party(lines, extractor.fields)  # ← DOI: authoritative loan from "Third party interest"
    _extract_mortgage_from_doi_address_block(lines, extractor.fields)  # ← DOI: mortgage from mailing address block
    _extract_policy_period_dates(lines, extractor.fields)  # ← RNW/FIR: robust policy-period date recovery
    _extract_can_inv_fields(lines, extractor.fields)   # ← NEW: CAN + INV fields
    _extract_carrier_full_scan(lines, extractor.fields)
    _extract_nfip_direct_carrier(lines, extractor.fields)
    _override_total_premium_from_explicit_label(lines, extractor.fields)
    _recover_mortgage_from_interest_table(lines, extractor.fields)
    _clean_policy_number(extractor.fields)
    _clean_insured_name(extractor.fields)
    _recover_named_insured_from_block(lines, extractor.fields)
    _recover_property_from_location_block(lines, extractor.fields)
    _clean_carrier_ocr_bleed(extractor.fields)         # ← Fix OCR bleed on carrier name
    _prefer_brand_carrier_header(lines, extractor.fields)
    _upgrade_brand_to_full_carrier(lines, extractor.fields)  # ← Upgrade single-word brand to full carrier
    _clean_policy_column_merge(extractor.fields)        # ← Strip column-merge alpha noise from policy number
    _repair_flood_renewal_dates(lines, extractor.fields)
    
    return extractor.fields


def extract_with_regex(lines: List[str], layout_elements=None) -> Dict[str, Dict]:
    """Alias for backward compatibility"""
    return extract_fields(lines, layout_elements)

# ============================================================
# DEBUG HELPER - Call this to see exact OCR lines + extraction trace
# ============================================================
def debug_extract(lines, print_lines=True):
    """
    Debug wrapper: prints OCR lines and extraction trace.
    Usage: from stage1_deterministic_agent import debug_extract; debug_extract(lines)
    """
    if print_lines:
        print("=" * 70)
        print(f"OCR LINES ({len(lines)} total)")
        print("=" * 70)
        for i, line in enumerate(lines):
            print(f"  {i:3d}: {repr(line)}")
    
    print("\n" + "=" * 70)
    print("EXTRACTION TRACE")
    print("=" * 70)
    
    ext = StatefulExtractor()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        old_fields = set(ext.fields.keys())
        old_role = ext.role
        ext.update_role(line)
        ext.extract(line)
        new_fields = set(ext.fields.keys()) - old_fields
        if new_fields or ext.role != old_role:
            print(f"\n  Line {i:3d}: {repr(line[:80])}")
            if ext.role != old_role:
                print(f"           Role: {old_role} -> {ext.role}")
            for f in new_fields:
                v = ext.fields[f]
                print(f"           +++ {f} = {repr(v.get('value', '?'))} (src={v.get('source', '?')})")
    
    ext.finalize()
    _safe_sweep(lines, ext.fields)
    _extract_mortgage_from_third_party(lines, ext.fields)
    _extract_loan_from_third_party(lines, ext.fields)
    _extract_mortgage_from_doi_address_block(lines, ext.fields)
    _extract_policy_period_dates(lines, ext.fields)
    _extract_can_inv_fields(lines, ext.fields)
    _extract_carrier_full_scan(lines, ext.fields)
    _extract_nfip_direct_carrier(lines, ext.fields)
    _clean_policy_number(ext.fields)
    _clean_insured_name(ext.fields)
    _clean_carrier_ocr_bleed(ext.fields)
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    # Show ALL extracted fields (not a hardcoded list)
    if ext.fields:
        for f in sorted(ext.fields.keys()):
            v = ext.fields[f]
            print(f"  ✅ {f}: {v.get('value', '?')} (src={v.get('source', '?')})")
    else:
        print("  No fields extracted")
    
    # Also show which common fields are missing
    common_fields = [
        "carrier_name", "policy_number", "insured_name",
        "effective_date", "expiration_date",
        "property_address", "mailing_address",
        "mortgage_company", "loan_number", "total_premium",
        "cancellation_date", "cancellation_reason",
        "balance_due", "issue_date", "remit_info",
    ]
    missing = [f for f in common_fields if f not in ext.fields]
    if missing:
        print(f"\n  Missing: {', '.join(missing)}")
    
    return ext.fields