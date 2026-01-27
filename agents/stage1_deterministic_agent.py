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
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
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
    re.compile(r"^\d{9,12}$"),  # 2004939477
    re.compile(r"^\d{9}\s*\d{3}\s*\d{1}$"),  # 602732135 664 1
    re.compile(r"^[A-Z]{2,4}\d{1,2}[-]?\d{9,12}$", re.I),  # OKH3-109194373
    re.compile(r"^\d{8,12}[-\s]?\d{1,2}$"),  # 04038598 - 1
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
    "account number", "your account number",
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
}

# CRITICAL: Terms that should NOT be captured as insured names
BAD_INSURED_TERMS = {
    # Mortgagee-related (most common error)
    "mortgagee", "first mortgagee", "second mortgagee", "third mortgagee",
    "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
    "loss payee", "lienholder", "lender",
    "isaoa", "atima", "isaoa atima", "isaoa/atima",
    "lien holder", "1st mortgagee copy",
    
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
}

# Property labels for inline extraction (Label: Value format)
PROPERTY_INLINE_LABELS = {
    "property address", "risk location",
    "location of insured property",
    "premises address", "property location",
    "property insured",  # ADDED for "Property Insured: 4616 HERITAGE RD"
}

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
    # Note: Removed "lender" as it can trigger on "Lender Relations Center"
}

# Patterns that look like mortgage triggers but are actually service centers
MORTGAGE_FALSE_POSITIVES = {
    "lender relations center",
    "mortgagee relations center",
    "mortgage relations center",
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
}

DATE_LABELS_EFFECTIVE = {
    "effective date", "policy effective date",
    "coverage begins", "term start date",
    "change effective date",
}

DATE_LABELS_EXPIRATION = {
    "expiration date", "policy expiration date",
    "coverage ends", "term end date", "expires",
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
    
    # Handle "LASTNAME, FIRSTNAME" format BUT NOT company names with comma
    # Don't swap if it contains entity suffixes
    if "," in v and v.count(",") == 1:
        has_entity = any(w in v.lower() for w in ("llc", "inc", "corp", "company", "trust", "ltd"))
        if not has_entity:
            parts = [p.strip() for p in v.split(",") if p.strip()]
            if len(parts) == 2 and not any(c.isdigit() for c in v):
                # Only swap if both parts look like names (not addresses)
                if not any(w.upper() in STATE_ABBREV for w in parts[1].split()):
                    return f"{parts[1]} {parts[0]}"
    
    return v.strip()


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


def _looks_like_name(text: str) -> bool:
    """
    Check if text looks like a person/company name
    IMPROVED: Better filtering of mortgagee terms and noise
    """
    if not text or len(text) < 3:
        return False
    
    text = text.strip()
    ll = text.lower()
    
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
    
    # Check if it's a multi-person name (contains "and" between name parts)
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
    
    # Must have at least 5 digits
    if digits < 5:
        return False
    
    # Pure numeric: 6-14 digits is OK
    if v_clean.isdigit():
        return 6 <= len(v_clean) <= 14
    
    # Mixed: check against patterns
    for rx in POLICY_REGEX_VARIANTS:
        if rx.fullmatch(v_clean) or rx.fullmatch(v_original):
            return True
    
    # Fallback: alphanumeric with substantial digits
    if letters >= 1 and digits >= 6:
        return True
    
    return False


def _looks_like_loan_number(v: str) -> bool:
    """
    Check if value looks like a loan number
    IMPROVED: Better filtering, stricter for short numbers
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
    
    # Loan numbers are typically 8-15 digits (raised minimum from 7)
    # 7-digit numbers are too likely to be phone number fragments
    if len(digits) < 8 or len(digits) > 15:
        return False
    
    # Block if too many consecutive zeros (padding patterns)
    if '000000' in digits:
        return False
    
    # Block if more than 50% zeros in longer numbers
    if len(digits) > 10:
        zero_count = digits.count('0')
        if zero_count > len(digits) * 0.5:
            return False
    
    # Block dates
    if DATE_RE.search(v):
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
    
    # Must have "insurance" somewhere
    if 'insurance' not in ll and ' ins ' not in ll and not ll.endswith(' ins'):
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
    
    def update_role(self, line: str):
        """Update current parsing role based on section headers"""
        ll = line.lower().strip()
        
        # Check for role triggers (order matters - more specific first)
        if any(k in ll for k in POLICY_LABELS):
            self._flush_accumulators()
            self.role, self.window = Role.POLICY_HEADER, 8
        elif any(k in ll for k in MAILING_TRIGGERS):
            self._flush_accumulators()
            self.role, self.window = Role.MAILING_BLOCK, 8
        elif any(k in ll for k in INSURED_LABELS):
            self._flush_accumulators()
            self.role, self.window = Role.INSURED_BLOCK, 12
        elif any(k in ll for k in PROPERTY_TRIGGERS):
            self._flush_accumulators()
            self.role, self.window = Role.PROPERTY_BLOCK, 8
        elif any(k in ll for k in MORTGAGE_TRIGGERS):
            # Check if it's a false positive (service center header)
            if not any(fp in ll for fp in MORTGAGE_FALSE_POSITIVES):
                self._flush_accumulators()
                self.role, self.window = Role.MORTGAGE_BLOCK, 10
        elif any(k in ll for k in PRODUCER_TRIGGERS):
            # Producer/agent section - skip names here
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
        
        # Check if this line contains 'insurance'
        if 'insurance' in ll:
            # If we have accumulated a prefix, ALWAYS try to combine
            if self.carrier_accumulator:
                combined = " ".join(self.carrier_accumulator) + " " + clean
                combined_lower = combined.lower()
                # If combined has insurance + company type, use it
                if 'insurance' in combined_lower and any(w in combined_lower for w in ('company', 'co', 'exchange', 'group', 'corp', 'mutual')):
                    if not any(w in combined_lower for w in ('agency', 'agent', 'services')):
                        self.fields["carrier_name"] = {
                            "value": combined.upper(),
                            "confidence": 0.97,
                            "source": "multi_line_combined",
                        }
                        self.carrier_accumulator = []
                        return
            
            # No accumulator - check if this line alone is a complete carrier
            if _looks_like_carrier(clean):
                self.fields["carrier_name"] = {
                    "value": clean.upper(),
                    "confidence": 0.95,
                    "source": "direct",
                }
                self.carrier_accumulator = []
                return
        
        # Check if this might be first part of multi-line carrier
        elif clean.isupper() and len(clean.split()) <= 2 and not any(c.isdigit() for c in clean):
            # Might be company name prefix like "ADIRONDACK"
            noise_words = {"PAGE", "DATE", "POLICY", "NUMBER", "INSURED", "ADDRESS", "NOTICE", "PO", "BOX"}
            words = clean.split()
            if words and not any(w in noise_words for w in words):
                if all(len(w) >= 3 for w in words):  # Each word should be substantial
                    self.carrier_accumulator = [clean]
    
    def _inline(self, line: str):
        """Extract from inline patterns (Label: Value)"""
        ll = line.lower()
        
        # Policy Number
        if "policy_number" not in self.fields:
            if ":" in line and any(k in ll for k in POLICY_LABELS):
                _, _, v = line.partition(":")
                v = _clean(v)
                
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
                else:
                    # Handle split values like "DPC 0076173896 -1"
                    v = re.sub(r"\s+(\d)$", r"-\1", v)
                    v_no_space = v.replace(" ", "")
                    
                    if _looks_like_policy(v_no_space):
                        self.fields["policy_number"] = {
                            "value": v_no_space,
                            "confidence": 0.99,
                            "source": "inline",
                        }
        
        # Property Address (NEW - for "Risk Location: 3004 NORFOLK DR" patterns)
        if "property_address" not in self.fields and ":" in line:
            if any(k in ll for k in PROPERTY_INLINE_LABELS):
                _, _, v = line.partition(":")
                v = v.strip()
                if v and _looks_like_address(v):
                    self.fields["property_address"] = {
                        "value": v,
                        "confidence": 0.98,
                        "source": "inline",
                    }
        
        # Insured Name (IMPROVED)
        if "insured_name" not in self.fields and ":" in line:
            label, _, val = line.partition(":")
            label_lower = label.lower().strip()
            
            # Check if this is an insured label
            if any(k in label_lower for k in ("insured", "policyholder")):
                # CRITICAL: Skip if label contains mortgagee terms
                if any(bad in label_lower for bad in ("mortgagee", "loss payee", "lender")):
                    pass  # Skip this
                else:
                    v = _normalize_name(val)
                    if v and _looks_like_name(v):
                        self.fields["insured_name"] = {
                            "value": v,
                            "confidence": 0.99,
                            "source": "inline",
                        }
                    elif v and len(v.strip()) > 3:
                        # Value on same line might be partial - check next line context
                        # Store as potential first part of multi-line name
                        self._partial_insured = v.strip()
        
        # Loan Number (IMPROVED)
        if "loan_number" not in self.fields and any(k in ll for k in LOAN_LABELS):
            if ":" in line:
                _, _, v = line.partition(":")
                digits = ''.join(c for c in v if c.isdigit())
            else:
                # Try to find number on line
                digits = ''
                for token in line.split():
                    d = ''.join(c for c in token if c.isdigit())
                    if len(d) >= 7:
                        digits = d
                        break
            
            if _looks_like_loan_number(digits):
                self.fields["loan_number"] = {
                    "value": digits,
                    "confidence": 0.96,
                    "source": "inline",
                }
        
        # Dates
        if "effective_date" not in self.fields:
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
        
        # Carrier from "underwritten by" or "your insurer"
        if "carrier_name" not in self.fields:
            if any(k in ll for k in ("underwritten by", "your insurer")):
                if ":" in line:
                    _, _, v = line.partition(":")
                    v = v.strip()
                    if 'insurance' in v.lower() and len(v) > 10:
                        self.fields["carrier_name"] = {
                            "value": v.upper(),
                            "confidence": 0.98,
                            "source": "inline_carrier",
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
                    "value": clean_token,
                    "confidence": 0.96,
                    "source": "block",
                }
                return
        
        # Try the whole line (handles spaces in policy numbers)
        clean_line = _clean(line)
        no_spaces = clean_line.replace(" ", "")
        if _looks_like_policy(no_spaces):
            self.fields["policy_number"] = {
                "value": no_spaces,
                "confidence": 0.94,
                "source": "block_combined",
            }
    
    def _insured(self, line: str):
        """Extract insured name from INSURED block - IMPROVED"""
        ll = line.lower().strip()
        
        # Skip obvious non-name lines
        skip_patterns = [
            "po box", "policy period", "loan number", "policy type",
            "description", "coverage", "premium", "effective", "expiration",
            "page", "continued", "summary", "mortgagee", "loss payee",
            "mailing address",
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
        
        # CRITICAL: Additional check - block mortgagee-related values
        if any(bad in ll for bad in BAD_INSURED_TERMS):
            return
        
        # Check for multi-line name combination (e.g., "DUMMY NAME" + "PROPERTIES, LLC")
        if self._partial_insured and "insured_name" not in self.fields:
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
            if "mailing_address" not in self.fields:
                # Check if line has "Label: Value" format
                address_value = line.strip()
                if ":" in line:
                    _, _, val = line.partition(":")
                    val = val.strip()
                    if val and _looks_like_address(val):
                        address_value = val
                
                self.fields["mailing_address"] = {
                    "value": address_value,
                    "confidence": 0.92,
                    "source": "insured_block",
                }
    
    def _property(self, line: str):
        """Extract property address from PROPERTY block"""
        ll = line.lower().strip()
        
        # Skip headers and labels
        if line.strip().endswith(":"):
            return
        if ll in [t.lower() for t in PROPERTY_TRIGGERS]:
            return
        
        # Check if line has "Label: Value" format
        address_value = line.strip()
        if ":" in line:
            label, _, val = line.partition(":")
            val = val.strip()
            # If value part looks like an address, use just the value
            if val and _looks_like_address(val):
                address_value = val
        
        if _looks_like_address(address_value):
            if "property_address" not in self.fields:
                self.fields["property_address"] = {
                    "value": address_value,
                    "confidence": 0.98,
                    "source": "block",
                }
            else:
                # Only overwrite if new address has street number (more complete)
                # Don't overwrite "3004 NORFOLK DR" with "AUSTIN, TX 78745"
                current = self.fields["property_address"]["value"]
                has_street_number = bool(re.match(r'^\d+\s+', current.strip()))
                new_has_street = bool(re.match(r'^\d+\s+', address_value.strip()))
                
                if new_has_street and not has_street_number:
                    # New address has street number, current doesn't - use new
                    self.fields["property_address"]["value"] = address_value
                elif len(address_value) > len(current) and (new_has_street or not has_street_number):
                    # Only update if new is longer AND either has street or current doesn't
                    self.fields["property_address"]["value"] = address_value
    
    def _mailing(self, line: str):
        """Extract mailing address from MAILING block"""
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
            self.fields["insured_name"] = {
                "value": _normalize_name(line),
                "confidence": 0.90,
                "source": "mailing_block",
            }
    
    def _mortgage(self, line: str):
        """Extract mortgage company and loan number from MORTGAGE block"""
        ll = line.lower()
        
        # Skip headers
        if line.strip().endswith(":"):
            return
        
        # Skip bad patterns (EXPANDED)
        bad_patterns = [
            "policy", "coverage", "endorsement", "homeowners", "premium",
            "first mortgagee", "second mortgagee", "third mortgagee",
            "1st mortgagee", "2nd mortgagee", "3rd mortgagee",
            "mortgagee copy", "mortgagee certificate",
            "other interest", "type of interest",
        ]
        if any(p in ll for p in bad_patterns):
            return
        
        # Loan number
        if "loan_number" not in self.fields:
            for token in line.split():
                digits = ''.join(c for c in token if c.isdigit())
                if _looks_like_loan_number(digits):
                    self.fields["loan_number"] = {
                        "value": digits,
                        "confidence": 0.94,
                        "source": "mortgage_block",
                    }
                    break
        
        # Mortgage company
        if "mortgage_company" not in self.fields:
            # Look for company-like patterns
            if any(w in ll for w in ("bank", "mortgage", "lending", "credit", "loan", "federal", "financial")):
                # CRITICAL: Skip if it's just a label like "First Mortgagee"
                if re.match(r'^(first|second|third|1st|2nd|3rd)\s+(mortgagee|lender)', ll):
                    return
                
                clean = line.strip()
                # Remove ISAOA/ATIMA suffixes
                clean = re.sub(r'\s+(ISAOA|ATIMA|ISAOA/ATIMA).*$', '', clean, flags=re.I)
                # Remove numbering prefixes
                clean = re.sub(r'^(\d+\.?\s*|first\s+|second\s+|third\s+)', '', clean, flags=re.I)
                
                if len(clean) > 5:
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
        if 'insurance' in ll and any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
            if not any(w in ll for w in ('agency', 'agent', 'services', 'producer')):
                self.fields["carrier_name"] = {
                    "value": line.strip().upper(),
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
                    v = _clean(v).replace(" ", "")
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
                    if _looks_like_address(lines[j]):
                        fields["property_address"] = {
                            "value": lines[j].strip(),
                            "confidence": 0.84,
                            "source": "sweep_lookahead",
                        }
                        break
                if "property_address" in fields:
                    break
    
    # --- Carrier Name fallback (scan first 20 lines) ---
    if "carrier_name" not in fields:
        # First, look for "underwritten by" or "your insurer" patterns
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
                if 'insurance' in ll:
                    if any(w in ll for w in ('company', 'exchange', 'group', 'mutual', 'corp')):
                        if not any(w in ll for w in ('agency', 'agent', 'services')):
                            fields["carrier_name"] = {
                                "value": line.strip().upper(),
                                "confidence": 0.85,
                                "source": "sweep_header",
                            }
                            break
    
    # --- Loan Number fallback ---
    if "loan_number" not in fields:
        for line in lines:
            ll = line.lower()
            if any(k in ll for k in LOAN_LABELS):
                # Try to extract number from line
                if ":" in line:
                    _, _, v = line.partition(":")
                    digits = ''.join(c for c in v if c.isdigit())
                else:
                    digits = ''.join(c for c in line if c.isdigit())
                
                if _looks_like_loan_number(digits):
                    fields["loan_number"] = {
                        "value": digits,
                        "confidence": 0.85,
                        "source": "sweep",
                    }
                    break


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