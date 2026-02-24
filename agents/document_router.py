from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re

try:
    from agents.document_classifier import classify_document
    from agents.policy_classifier import classify_policy
except ImportError:
    from document_classifier import classify_document
    from policy_classifier import classify_policy


# ============================================================
# APPROACH ENUM  (all 8 strategies)
# ============================================================

class Approach(Enum):
    SARDE           = "sarde"               # 1
    SARDE_LATE      = "sarde_late"          # 2
    SC_SARDE_LATE   = "sc_sarde_late"       # 3
    DTE             = "dte"                 # 4
    SC_TE_DTE       = "sc_te_dte"           # 5
    SC_TE_LATE      = "sc_te_late"          # 6
    SC_TE           = "sc_te"               # 7
    LORH            = "lorh"                # 8

ALLOWED_DOC_TYPES = {
    "BIN", "CAN", "OTH", "RNW",
    "RNS", "INV", "DOI", "COI", 
}

# ============================================================
# VALID DOCUMENT TYPES (Structural Classification Only)
# ============================================================
# These are the ONLY valid document types that should be returned.
# Everything else is either a POLICY TYPE or a SUBTYPE.

# REMOVED from document types (these are policy subtypes or indicators):
# - FPN: Force Placed Notice (no longer valid per business rules)
# - NRNW: Non-Renewal (this is a POLICY SUBTYPE - cancellation reason)
# - BREQ/BRQ: Borrower Request (this is a POLICY SUBTYPE - cancellation reason)
# - TPN: Third Party Notice (structural indicator that maps to CAN or COI)
# - EDI: Electronic Data Interchange (format indicator, not a type)
# - NPAY: Non-Payment (this is a POLICY SUBTYPE - cancellation reason)
# - UNWR: Underwriting (this is a POLICY SUBTYPE - cancellation reason)
# - CEL: Generic Cancellation (this is a POLICY SUBTYPE - cancellation reason)

# ============================================================
# FALLBACK MAP — each approach has at most ONE designated fallback
# Only triggered when critical fields are still missing after primary
# ============================================================

FALLBACK_MAP = {
    Approach.SARDE:         Approach.SC_TE,          # deterministic missed → try semantic
    Approach.SARDE_LATE:    Approach.SC_TE,           # same
    Approach.SC_SARDE_LATE: None,                     # already full cascade
    Approach.DTE:           Approach.SARDE,            # template missed → try deterministic
    Approach.SC_TE_DTE:     None,                      # already multi-approach
    Approach.SC_TE_LATE:    None,                      # already multi-approach
    Approach.SC_TE:         Approach.SARDE,            # semantic missed → try deterministic
    Approach.LORH:          Approach.SC_TE,            # heuristic missed → try semantic
}

# ============================================================
# FIELD REQUIREMENTS PER DOC TYPE
# ============================================================

REQUIRED_FIELDS: Dict[str, List[str]] = {
    "RNW":  ["carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date"],
    "INV":  ["carrier_name", "policy_number", "insured_name"],
    "CAN":  ["carrier_name", "policy_number", "insured_name",
             "effective_date"],
    "DOI":  ["policy_number", "mortgage_company", "loan_number"],
    "COI":  ["carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date"],
    "RNS":  ["carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date"],
    "BIN":  ["carrier_name", "policy_number", "insured_name",
             "effective_date"],
    "OTH":  ["policy_number"],
}

OPTIONAL_FIELDS: Dict[str, List[str]] = {
    "RNW":  ["property_address", "mailing_address", "mortgage_company",
             "loan_number", "total_premium"],
    "INV":  ["balance_due", "issue_date", "remit_info",
             "effective_date", "expiration_date", "property_address",
             "mortgage_company", "loan_number", "total_premium"],
    "CAN":  ["expiration_date", "cancellation_date", "cancellation_reason",
             "property_address", "mortgage_company", "loan_number"],
    "DOI":  ["carrier_name", "insured_name", "property_address"],
    "COI":  ["property_address"],
    "RNS":  [],
    "BIN":  ["expiration_date", "property_address"],
    "OTH":  ["insured_name", "carrier_name", "property_address",
             "loan_number"],
}

# Policy types with coverage/premium tables → triggers + LATE
TABLE_POLICY_TYPES = {
    "HO", "HO3", "HO6", "FIR", "FLD", "HAZ", "DP3", "WND", "AUTO", "ERQ", "LL", "UO",
    "NRNW", "BREQ", "NPAY", "UNWR", "CEL", 
}

# ============================================================
# ROUTING RESULT
# ============================================================

@dataclass
class RoutingResult:
    """Output of the router — tells the orchestrator exactly what to do."""
    approach: Approach
    doc_type: str
    policy_type: str
    required_fields: List[str]
    optional_fields: List[str]
    carrier_hint: Optional[str] = None
    has_tables: bool = False
    is_multi_page: bool = False
    reason: str = ""
    # --- INS Validation §3: Granular subtype for extraction hints ---
    doc_subtype: Optional[str] = None

    @property
    def all_target_fields(self) -> List[str]:
        return list(dict.fromkeys(self.required_fields + self.optional_fields))

    @property
    def fallback(self) -> Optional[Approach]:
        return FALLBACK_MAP.get(self.approach)


# ============================================================
# STRUCTURAL SIGNAL DETECTORS
# ============================================================

def _detect_tables(lines: List[str]) -> bool:
    """Detect coverage / premium table presence."""
    signals = 0
    for line in lines:
        ll = line.lower()
        if len(re.findall(r'\$[\d,]+', line)) >= 2:
            signals += 1
        if any(k in ll for k in ("coverage", "limit", "premium", "deductible")):
            if re.search(r'\$[\d,]+', line):
                signals += 1
        if re.search(r'\d[\s]{3,}\d', line):
            signals += 1
    return signals >= 2


def _detect_fax_packet(lines: List[str]) -> bool:
    """Detect fax or multi-document packet."""
    signals = 0
    for line in lines[:25]:
        ll = line.lower()
        if any(k in ll for k in ("fax", "facsimile", "attn:",
                                  "attention:", "transmittal")):
            signals += 1
        if re.search(r"page\s+\d+\s+of\s+\d+", ll):
            signals += 1
    return signals >= 2


# --- INS observation batch: Section 6 - Page Filtering ---
# Patterns indicating pages that should be ignored during extraction
PAGE_FILTER_PATTERNS = [
    "fax cover sheet",
    "fax transmission",
    "from: faxagent",
    "faxagent",
    "batch number",
    "opex 3600",
    "front image",
    "rear image",
    "this page intentionally left blank",
    "acord 25",
    "advisory notice to policyholders",
    "coverage form",
]

def filter_artifact_pages(lines: List[str]) -> List[str]:
    """
    Filter out lines belonging to fax artifacts, cover sheets,
    and other non-document pages per INS batch Section 6 & 9.
    
    Returns cleaned lines with artifact content removed.
    """
    if not lines:
        return lines
    
    filtered = []
    skip_block = False
    
    for line in lines:
        ll = line.lower().strip()
        
        # Check if this line starts a skip block
        if any(p in ll for p in PAGE_FILTER_PATTERNS):
            skip_block = True
            continue
        
        # End skip block on strong document signals
        if skip_block and any(k in ll for k in (
            "declarations", "policy number", "insured",
            "effective date", "coverage a", "premium",
            "notice of cancellation", "certificate of insurance",
        )):
            skip_block = False
        
        if not skip_block:
            filtered.append(line)
    
    return filtered if filtered else lines  # Fallback to original if everything filtered

def _detect_simple(lines: List[str]) -> bool:
    """Detect very simple single-page doc → LORH candidate.
    LORH is ONLY for truly trivial documents.
    Must have actual content (≥3 lines), be short (≤12 lines),
    and have very few field signals (≤3)."""
    if len(lines) < 3 or len(lines) > 12:
        return False
    text_lower = " ".join(lines).lower()
    # Has coverage structure → NOT simple
    if any(k in text_lower for k in ("coverage a", "coverage b",
                                      "dwelling", "deductible",
                                      "mortgagee", "endorsement")):
        return False
    field_signals = sum(
        1 for line in lines
        if any(k in line.lower()
               for k in ("policy", "insured", "amount", "date",
                          "number", "premium", "balance", "carrier",
                          "effective", "expiration", "address"))
    )
    return field_signals <= 3


def _detect_inner_doc_type(lines: List[str]) -> Optional[str]:
    """When a doc is classified as PQ (fax packet), try to detect
    the actual inner document type from the full content."""
    if not lines:
        return None
    text = " ".join(lines).lower()
    
    # DOI signals (check before CAN since DOI docs may contain cancellation language)
    if any(k in text for k in ("deletion of interest", "interest removal",
                                "interest deleted", "interest removed",
                                "mortgagee interest removed",
                                "mir-mortgagee interest removed",
                                "mir mortgagee interest removed",
                                "third party interest removed",
                                "no longer have an interest",
                                "removed all indications of your interest",
                                "loan has been satisfied",
                                "interest has been removed",
                                "interest terminated")) or bool(
        re.search(r"mir[\s\-]*mortgagee", text)
    ) or bool(re.search(r"cancel\s*reason[:\s]*mir", text)):
        return "DOI"
    
    # CAN signals
    if any(k in text for k in ("notice of cancellation", "cancellation notice",
                                "policy cancelled",
                                "reason cancellation", "doc type - cancellation",
                                "doc type cancellation",
                                "cancellation customer initiated",
                                "cancel reason")):
        return "CAN"
    if any(k in text for k in ("non-renewal", "nonrenewal",
                                "will not be renewed")):
        return "CAN"
    # LexisNexis notification with cancellation
    if "insurance coverage notification" in text and "cancellation" in text:
        return "CAN"
    # Borrower request or customer initiated → CAN
    if "borrower request" in text or "customer initiated" in text:
        return "CAN"
    if "third party notice" in text:
        # Check if it's interest-only termination → DOI
        if "third party notice of termination" in text:
            has_policy_terminate = bool(re.search(
                r"terminate this policy effective[:\s]*\d", text))
            has_interest_terminate = (
                "terminate the interest" in text
                or bool(re.search(
                    r"terminate the interest.*?(third party|hereon)", text))
            )
            if has_interest_terminate and not has_policy_terminate:
                return "DOI"
        # Third party notice with termination/cancellation → CAN
        if any(k in text for k in ("terminate", "termination", "cancel", "cancellation")):
            return "CAN"
        else:
            # Otherwise it's a coverage notification → COI
            return "COI"
    
    # EDI images
    if any(k in text for k in ("edi image", "electronic data",
                                "electronic image generated for edi",
                                "electronic image generated",
                                "generated for edi", "edi data")):
        pass
    
    # LexisNexis notification detection (even without full "insurance coverage notification")
    if "lexisnexis" in text or "insurance coverage notification" in text:
        if any(k in text for k in (
            "cancellation", "cancelled", "cancel reason",
            "cancellation customer", "reason cancellation",
            "customer initiated",
        )):
            return "CAN"
        if any(k in text for k in (
            "interest removed", "mir-mortgagee", "mir mortgagee",
        )):
            return "DOI"
        # LexisNexis with no specific signal but has policy info → likely CAN notification
        if any(k in text for k in ("insurance coverage notification",)):
            return "CAN"
    
    if any(k in text for k in ("certificate of insurance",
                                "certificate holder")):
        return "COI"
    
    # Check for renewal/declarations content inside the packet
    if any(k in text for k in ("renewal flood insurance",
                                "flood insurance policy declarations",
                                "policy declarations",
                                "agent issued declarations",
                                "declarations",
                                "coverage a", "coverage b",
                                "total policy premium",
                                "annual premium",
                                "homeowners policy",
                                "policy premium",
                                "dwelling (coverage a)",
                                # --- INS batch Section 8: Flood-specific renewal ---
                                "flood policy declarations",
                                "renewal billing payor",
                                "nfip policy",
                                "standard flood insurance",
                                )):
        return "RNW"
    
    return None


def _detect_carrier_hint(lines: List[str]) -> Optional[str]:
    """Early carrier name detection from first 30 lines."""
    KNOWN = {
        "allstate", "citizens", "state farm", "usaa", "travelers",
        "progressive", "nationwide", "liberty mutual", "amica",
        "american family", "farmers", "erie", "auto-owners",
        "chubb", "hanover", "hartford", "safeco",
        "federated national", "universal property", "heritage",
        "peoples trust", "security first", "tower hill",
        "florida peninsula", "homeowners choice",
        "citizens property", "allied trust",
        "aegis", "encompass", "southern oak",
    }
    for line in lines[:30]:
        ll = line.lower()
        for c in KNOWN:
            if c in ll:
                return c
    return None


# ============================================================
# SUBTYPE DETECTOR  (INS Validation §3)
# ============================================================
# Granular subtypes for extraction routing. Does NOT change
# doc_type / policy_type — provides extra context only.

_SUBTYPE_NAMES = [
    "FLOOD", "FLOOD_PQ", "WIND", "DB", "DS", "MH", "LL",
    "COMMERCIAL", "COMMERCIAL_BOP", "CERTIFICATE", "MORTGAGE_DEC",
    "POLICY_CHANGE", "CANCELLATION", "NONRENEWAL", "EDI_STRUCTURED",
    "FAX_ARTIFACT", "HO6", "BILLING",
]

def _detect_doc_subtype(lines: List[str]) -> Optional[str]:
    """Detect granular document subtype from OCR text.
    Returns one of _SUBTYPE_NAMES or None."""
    if not lines:
        return None
    text = " ".join(lines).lower()
    head = " ".join(lines[:30]).lower()

    # --- EDI_STRUCTURED: highest priority — changes parsing mode ---
    if any(k in text for k in (
        "electronic image generated for edi",
        "electronic image generated",
        "generated for edi data",
    )):
        return "EDI_STRUCTURED"

    # --- FAX_ARTIFACT ---
    if any(k in head for k in ("fax transmission", "fax cover", "facsimile")):
        fax_signals = sum(1 for k in ("fax", "facsimile", "attn:", "transmittal")
                          if k in head)
        if fax_signals >= 2:
            return "FAX_ARTIFACT"

    # --- MORTGAGE_DEC ---
    if any(k in text for k in (
        "mortgagee dec summary", "mortgagee declarations summary",
        "mortgage dec summary",
    )):
        return "MORTGAGE_DEC"

    # --- FLOOD_PQ: flood inside a packet ---
    if "flood" in text and any(k in head for k in ("fax", "packet", "bundle")):
        return "FLOOD_PQ"

    # --- FLOOD ---
    if any(k in text for k in (
        "renewal flood insurance policy declarations",
        "flood insurance policy declarations",
        "national flood insurance program",
        "flood insurance declarations",
    )):
        return "FLOOD"

    # --- POLICY_CHANGE ---
    if any(k in text for k in (
        "policy change", "amended declarations", "revised declarations",
        "change effective date", "endorsement change",
    )):
        return "POLICY_CHANGE"

    # --- NONRENEWAL ---
    if any(k in text for k in (
        "non-renewal", "nonrenewal", "notice of nonrenewal",
        "will not be renewed",
    )):
        return "NONRENEWAL"

    # --- CANCELLATION ---
    if any(k in text for k in (
        "cancellation notice", "notice of cancellation", "policy cancelled",
    )):
        return "CANCELLATION"

    # --- COMMERCIAL_BOP ---
    if any(k in text for k in (
        "businessowners policy", "business owners policy",
        "commercial property coverage part", "common declarations", "compak",
    )):
        return "COMMERCIAL_BOP"

    # --- COMMERCIAL ---
    if any(k in text for k in (
        "commercial package", "commercial lines", "commercial property",
        "business insurance",
    )):
        return "COMMERCIAL"

    # --- FARM ---
    if any(k in text for k in (
        "farm ranch", "farm policy", "farm and ranch",
        "farmowners", "farm owners",
    )):
        return "FARM"

    # --- DB (Dwelling Basic) ---
    if any(k in text for k in ("dwelling basic", "policy type: dwelling basic")):
        return "DB"

    # --- DS (Dwelling Special) ---
    if any(k in text for k in ("dwelling special", "policy type: dwelling special")):
        return "DS"

    # --- MH (Manufactured/Mobile Home) ---
    if any(k in text for k in (
        "manufactured home", "mobile home", "mobilehome",
        "manufactured housing",
    )):
        return "MH"

    # --- LL (Landlord) ---
    if any(k in text for k in (
        "landlord", "rental dwelling", "landlords policy", "tenant dwelling",
    )):
        return "LL"

    # --- WIND ---
    if any(k in text for k in (
        "wind only", "windstorm", "hurricane policy", "wind/hail policy",
    )):
        return "WIND"

    # --- HO6 (Condo Unit Owner) ---
    if any(k in text for k in ("ho-6", "ho6", "unit owner", "condominium unit")):
        return "HO6"

    # --- CERTIFICATE ---
    if any(k in text for k in (
        "certificate of insurance", "certificate holder",
    )):
        return "CERTIFICATE"

    # --- BILLING ---
    if any(k in text for k in (
        "premium bill", "policy bill", "billing statement",
        "amount due", "balance due",
    )):
        return "BILLING"

    return None


# ============================================================
# BUNDLE RESOLVER  (INS Validation §8)
# ============================================================
# Multi-document PDFs (fax bundles): locate the DECLARATION page
# and return the line index where real extraction should start.

# Strong signals that we've reached the actual declaration/policy content
_DECLARATION_ANCHORS = (
    "declarations page", "policy declarations", "declaration page",
    "policy summary", "mortgagee dec summary",
    "renewal flood insurance policy declarations",
    "coverage a", "coverage b",
    "dwelling amount", "dwelling limit",
    "policy period", "coverage and limits",
    "insured and policy information",
    "named insured and mailing address",
)

# Pre-declaration noise page signals (fax, ACORD, cover pages)
_NOISE_ANCHORS = (
    "fax transmission", "fax cover", "facsimile",
    "acord 25", "acord 28", "certificate of insurance",
    "advisory notice", "this page intentionally",
    "coverage form", "batch number",
)


def _find_declaration_start(lines: List[str]) -> int:
    """For multi-document bundles, find line index where actual
    declaration content begins.  Returns 0 if no bundle detected."""
    if not lines or len(lines) < 15:
        return 0

    found_noise = False
    for i, line in enumerate(lines):
        ll = line.lower().strip()

        if any(n in ll for n in _NOISE_ANCHORS):
            found_noise = True
            continue

        # If we've passed through noise and find declaration content,
        # back up 3 lines to capture carrier name header
        if found_noise and any(d in ll for d in _DECLARATION_ANCHORS):
            return max(0, i - 3)

    return 0


# ============================================================
# DOCUMENT-TYPE CLASSIFIER  (rule-based)
# ============================================================
def classify_doc_type(lines: List[str]) -> str:
    """
    Rule-based doc-type classification.
    Specific patterns must be checked in strict priority order.
    """
    if not lines:
        return "OTH"

    head = " ".join(lines[:50]).lower()
    full = " ".join(lines).lower()

    # ============================================================
    # 1️⃣ DOI (HIGHEST PRIORITY — MUST BE FIRST)
    # ============================================================
    if (
        "interest removed" in full
        or "mortgagee interest removed" in full
        or "no longer have an interest" in full
        or "removed all indications of your interest" in full
        or "loan has been satisfied" in full
        or "interest has been removed" in full
        or "interest removal" in full
        or "interest deleted" in full
        or "interest terminated" in full
        or "mir-mortgagee interest removed" in full
        or "mir mortgagee interest removed" in full
        or "cancel reason mir" in full
        or "cancel reason: mir" in full
        or bool(re.search(r"mir[\s\-]*mortgagee", full))
        or bool(re.search(r"cancel\s*reason[:\s]*mir", full))
        or ("mir" in full and "mortgagee" in full and "removed" in full)
        # Loss payee deletion patterns
        or "deleted as loss payee" in full
        or "removed as loss payee" in full
        or "loss payee deleted" in full
        or "loss payee removed" in full
        or "has been deleted as loss payee" in full
        or "has been removed as loss payee" in full
    ):
        return "DOI"
    
    # DOI via Third Party Notice of Termination (interest-only termination)
    if "third party notice of termination" in full:
        has_policy_terminate = bool(re.search(
            r"terminate this policy effective[:\s]*\d", full))
        has_interest_terminate = (
            "terminate the interest" in full
            or bool(re.search(
                r"terminate the interest.*?(third party|hereon)", full))
        )
        if has_interest_terminate and not has_policy_terminate:
            return "DOI"

    # OCR-robust DOI: "terminate the interest" alone (even without TPN header)
    # If we see "terminate the interest" + NO policy termination date → DOI
    if "terminate the interest" in full:
        has_policy_terminate = bool(re.search(
            r"terminate this policy effective[:\s]*\d", full))
        if not has_policy_terminate:
            return "DOI"

    # OCR-robust: garbled TPN detection
    # "third party" + "terminat"/"termin" + "interest" = likely DOI
    # NOTE: "notice" removed from trigger keywords — it is too generic and
    # falsely matches cancellation notices that mention "third party interest"
    # as a column header (e.g. "Cancellation date for third party interest").
    # Also guarded: skip if strong CAN signals are present, since a real TPN
    # doc would not contain "cancellation notice" or "cancellation date".
    if ("third party" in full
        and "interest" in full
        and any(k in full for k in ("terminat", "termin"))
        and not any(k in full for k in (
            "cancellation notice",
            "notice of cancellation",
            "cancellation date",
            "will be cancelled",
            "policy will be cancelled",
        ))):
        has_policy_terminate = bool(re.search(
            r"terminate this policy effective[:\s]*\d", full))
        if not has_policy_terminate:
            return "DOI"

    # OCR-robust: "indentified hereon" (appears in Allstate TPN docs)
    # This phrase only appears in interest termination context
    if any(k in full for k in (
        "indentified hereon",
        "identified hereon",
        "party indentified",
        "party identified",
    )):
        has_policy_terminate = bool(re.search(
            r"terminate this policy effective[:\s]*\d", full))
        if not has_policy_terminate:
            return "DOI"

    # ============================================================
    # 2️⃣ Cancellation
    # Guard: Declarations/renewal documents contain boilerplate like
    # "if the policy is cancelled or not renewed" — this should NOT
    # trigger CAN classification. Check for declarations context.
    # ============================================================
    can_signals = any(k in full for k in (
        "notice of cancellation",
        "cancellation notice",
        "policy cancelled",
        "will be cancelled",
        "cancel effective",
        "is hereby cancelled",
        "cancellation date",
        "reason cancellation",
        "doc type - cancellation",
        "doc type cancellation",
        "cancellation customer initiated",
        "reason: cancellation",
        "non-renewal",
        "nonrenewal",
        "will not be renewed",
        "notice of non renewal",
    ))
    if can_signals:
        # Guard: declarations/renewal context with boilerplate cancellation language
        is_declaration_context = any(k in full for k in (
            "policy change declarations",
            "policy declarations",
            "declarations page",
            "mortgagee declarations",
            "amended declarations",
            "homesaver policy",
            "homeowners policy declarations",
            "mortgagee certificate",
        )) or (
            "declarations" in full and any(k in full for k in (
                "coverage a", "coverage b", "coverage c",
                "coverage d", "coverage e", "coverage f",
                "section i", "section ii",
                "total premium",
                "property coverages",
                "liability coverages",
            ))
        )
        # Additional guard: strong coverage structure (A-F with limits) + 
        # boilerplate cancellation language from mortgagee clauses
        if not is_declaration_context:
            has_coverage_structure = (
                sum(1 for cov in ("coverage a", "coverage b", "coverage c",
                                  "coverage d", "coverage e", "coverage f",
                                  "a.dwelling", "b.other structures",
                                  "c.personal property", "d.loss of use",
                                  "e.personal liability", "f.medical payments")
                    if cov in full) >= 3
            )
            has_boilerplate = any(k in full for k in (
                "if the policy is cancelled or not renewed",
                "notice of cancellation we give our insured",
                "advance notice of cancellation",
                "the mortgagee will be notified at least",
            ))
            if has_coverage_structure and has_boilerplate:
                is_declaration_context = True
        if not is_declaration_context:
            # Payment notice guard: non-payment + payment stub = INV, not CAN
            is_payment_notice = (
                ("non-payment" in full or "nonpayment" in full)
                and sum(1 for k in (
                    "return this portion with your payment",
                    "amount enclosed", "make check or money order",
                    "make check payable", "minimum amount due",
                    "minimum premium amount due",
                    "payment due date", "total amount due",
                    "payment options", "account statement",
                    "premium balance", "invoice number",
                    "detach and return", "please detach",
                    "pay online", "amount due",
                    "if payment is not received",
                    "if you have already made your payment",
                ) if k in full) >= 2
            )
            if not is_payment_notice:
                return "CAN"
    
    # LexisNexis/EDI notification with cancellation context
    if "insurance coverage notification" in full and "cancellation" in full:
        return "CAN"
 
    # ============================================================
    # 4️⃣ Borrower Request (MAPS TO CAN, not a doc type)
    # BRQ/BREQ is a POLICY SUBTYPE (cancellation reason), not a document type
    # ============================================================
    if any(k in head for k in (
        "borrower request",
        "borrower cancel",
        "borrower-requested",
    )):
        # This is a cancellation initiated by borrower
        return "CAN"

    # ============================================================
    # 5️⃣ Third-party notice (MAPS TO CAN or COI, not a doc type)
    # TPN is a structural indicator, not a document type
    # ============================================================
    if any(k in head for k in (
        "third party notice",
        "third-party notice",
        "third party notification",
    )):
        # Check if it's termination (CAN) or coverage notification (COI)
        if any(k in full for k in (
            "terminate",
            "termination",
            "cancel",
            "cancellation",
            "non-renewal",
        )):
            return "CAN"
        else:
            # Coverage notification/certificate
            return "COI"

    # ============================================================
    # 6️⃣ Invoice
    # ============================================================
    if any(k in head for k in (
        "invoice",
        "billing statement",
        "amount due",
        "balance due",
        "payment due",
        "remit to",
        "please pay",
        "minimum due",
        "policy bill",
        "premium bill",
        "premium statement",
        "renewal premium bill",
        "account statement",
        "total amount due",
        "payment due date",
        "invoice number",
    )):
        # Guard: declarations with invoice header should be RNW, not INV
        # But "policy bill" / "premium statement" as title should always be INV
        is_policy_bill = any(k in head for k in (
            "policy bill", "premium bill", "premium statement",
            "renewal premium bill",
        ))
        inv_is_rnw = not is_policy_bill and any(k in full for k in (
            "policy declarations",
            "declaration page",
            "declarations page",
            "declaration page is attached",
            "this is not an invoice",
            "not an invoice/bill",
            "coverage a",
            "coverage b",
            "total policy premium",
            "annual premium",
            "mortgagee dec summary",
            "homeowners policy declarations",
            "homeowner policy declarations",
        ))
        if not inv_is_rnw:
            return "INV"

    # ============================================================
    # 7️⃣ Certificate of Insurance
    # ============================================================
    if any(k in head for k in (
        "certificate of insurance",
        "certificate holder",
        "acord 25",
        "acord 28",
    )):
        # Guard: unit owner / condo certificate with coverage details = RNW, not COI
        coi_is_rnw = any(k in full for k in (
            "unit owner",
            "master policy",
            "condominium unit number",
            "coverage amount",
            "coverage summary",
            "deductible",
            "policy inception date",
            "effective date",
            "policy period",
            "declarations",
            "dwelling",
            "renewal",
            "coverage a",
            "coverage b",
        ))
        if not coi_is_rnw:
            return "COI"

    # ============================================================
    # 8️⃣ Reinstatement
    # ============================================================
    if any(k in head for k in (
        "reinstatement",
        "reinstated",
        "rescission of cancellation",
    )):
        # Guard: "reinstatement date:" is a field label in flood/renewal declarations
        rns_is_field_label = any(k in full for k in (
            "flood policy declarations",
            "flood insurance policy declarations",
            "policy declarations",
            "renewal flood insurance",
            "declarations page",
            "total premium paid",
            "total premium",
            "property location",
            "policy period",
            "annual premium",
        ))
        if not rns_is_field_label:
            return "RNS"

    # ============================================================
    # 9️⃣ Binder
    # ============================================================
    if any(k in head for k in (
        "binder",
        "evidence of coverage",
        "bound coverage",
    )):
        return "BIN"

    # ============================================================
    # 🔟 LexisNexis Insurance Coverage Notification
    # ============================================================
    if "insurance coverage notification" in full:
        if any(k in full for k in (
            "cancellation",
            "cancel reason",
            "cancelled",
        )):
            return "CAN"

        if any(k in full for k in (
            "interest removed",
            "mir-mortgagee",
            "mir mortgagee",
        )):
            return "DOI"

        return "CAN"

    # ============================================================
    # 1️⃣1️⃣a EDI WRAPPER — detect inner document type
    # ============================================================
    if any(k in full for k in (
        "electronic image generated for edi",
        "electronic image generated",
        "generated for edi",
        "edi data",
        "edi image",
    )):
        if any(k in full for k in (
            "interest removed", "mir-mortgagee", "mir mortgagee",
        )):
            return "DOI"
        if any(k in full for k in (
            "cancellation", "cancel reason", "cancelled",
        )):
            return "CAN"
        if any(k in full for k in (
            "doc type - renewal", "doc type renewal",
            "rwl-811", "rwl-s11", "rnw-811", "rnw-s11",
            "transaction desc: renewal", "renewal",
        )) or bool(re.search(r"doc\s*type.*renewal", full)):
            return "RNW"
        return "OTH"

    # ============================================================
    # 1️⃣1️⃣ Fax wrapper (structure only — detect inner content)
    # ============================================================
    if _detect_fax_packet(lines):
        # Try to detect what's INSIDE the fax packet
        inner = _detect_inner_doc_type(lines)
        if inner:
            return inner
        
        # Check for strong doc signals even without inner detection
        strong_doc_signals = any(k in full for k in (
            "notice of cancellation",
            "cancellation notice",
            "cancellation",
            "interest removed",
            "mortgagee interest removed",
            "no longer have an interest",
            "policy declarations",
            "declarations page",
            "coverage a",
            "coverage b",
            "annual premium",
            "policy period",
            "dwelling fire",
            "dfire",
            "homeowners policy",
            "homeowner policy",
            "insurance coverage notification",
            "lexisnexis",
            # QBE / specialty declaration signals inside fax
            "declaration page is attached",
            "cert. #",
            "effective from",
            "total policy premium",
            "policy premium",
            "coverage detail",
            "mortgagee(s)",
            "mortgagees",
        ))
        if not strong_doc_signals:
            return "OTH"

    # ============================================================
    # 1️⃣2️⃣ Renewal (LAST — broadest)
    # ============================================================
    if any(k in head for k in (
        "renewal",
        "declarations",
        "policy period",
        "your policy",
        "homeowner",
        "amended declarations",
        "coverage summary",
        # Wind / specialty formats
        "carrier:",
        "pol. type:",
        "pol.type:",
        "prop. loc:",
        "prop.loc:",
        # American Modern format
        "policy declarations",
        "premium summary",
        "policy summary",
        "named insured",
        # Progressive format  
        "progressive",
    )):
        return "RNW"

    if any(k in full for k in (
        "coverage a",
        "coverage b",
        "dwelling coverage",
        "annual premium",
        "renewal flood insurance",
        "flood insurance policy declarations",
        "flood policy declarations",
        "agent issued declarations",
        "policy premium",
        "total policy premium",
        # Wind / specialty signals
        "pol. from:",
        "pol.from:",
        "pol. to:",
        "pol.to:",
        "eff. date:",
        "eff.date:",
        "prop. loc:",
        "prop.loc:",
        # American Modern / general declaration signals
        "policy type:",
        "coverage detail",
        "coverage and limits",
        "additional interests",
        "lienholder",
        "loan/contract number",
        "dwelling #1",
        "named insured(s)",
        "transaction effective date",
        "mortgagee dec summary",
        "insured and policy information",
        # QBE / specialty with declaration page
        "declaration page is attached",
        "cert. #",
        "effective from",
        # EDI renewal patterns
        "doc type - renewal",
        # --- INS observation batch Section 13: Commercial/BOP detection ---
        "common declarations",
        "commercial property coverage part",
        "businessowners policy",
        "business owners policy",
        "compak",
    )):
        return "RNW"

    return "OTH"

def classify_policy_type(lines: List[str]) -> str:
    """Rule-based policy-type classification."""
    if not lines:
        return "OTH"
    text = " ".join(lines[:60]).lower()
    full = " ".join(lines).lower()

    # Renewal/declaration guard - skip cancellation subtypes for renewals
    is_renewal = any(k in full for k in (
        "policy declarations", "declarations summary", "policy change summary",
        "transaction: renewal", "agent issued declarations",
        "landlord protection policy declarations",
        "wind only policy - declarations", "homeowners hw-",
        # Additional: Policy Change Declarations (e.g., Travelers Homesaver)
        "policy change declarations",
        "homesaver policy",
        "mortgagee certificate",
    ))
    # Additional: docs with strong coverage structure + boilerplate cancel language
    if not is_renewal:
        has_cov = sum(1 for c in ("coverage a", "coverage b", "coverage c",
                                   "coverage d", "coverage e", "coverage f",
                                   "a.dwelling", "b.other structures",
                                   "c.personal property", "d.loss of use",
                                   "e.personal liability", "f.medical payments")
                      if c in full) >= 3
        has_bp = any(k in full for k in (
            "if the policy is cancelled or not renewed",
            "advance notice of cancellation",
            "the mortgagee will be notified at least",
        ))
        if has_cov and has_bp:
            is_renewal = True
    
    # DOI context guard — but NOT if there's also a policy termination signal.
    # A Third Party Notice of Termination that terminates BOTH the policy AND
    # the third party interest is a BREQ (borrower request), not a DOI.
    _has_policy_termination = bool(re.search(
        r"terminate this policy effective[:\s]*\d", full
    ))
    is_doi_context = any(k in full for k in (
        "terminate the interest of the third party",
        "terminate the interest",
        "interest removed",
        "deletion of interest",
        "no longer have an interest",
    )) and not _has_policy_termination
    
    if not is_renewal and not is_doi_context:
        # Cancellation subtypes first (for CAN docs, reason > coverage type)
        # BREQ — Borrower Request / Customer Initiated
        if "third party notice of termination" in full:
            has_policy_terminate = bool(re.search(
                r"terminate this policy effective[:\s]*\d", full))
            if has_policy_terminate:
                return "BREQ"
        if any(k in full for k in (
            "borrower request", "customer request", "customer initiated",
            "cancellation customer initiated", "reason cancellation customer",
            "insured request", "at the request of the insured",
        )):
            return "BREQ"
        # LexisNexis notification with cancellation but no specific reason
        if "insurance coverage notification" in full and "cancellation" in full:
            if not any(k in full for k in (
                "non-payment", "nonpayment", "failure to pay",
                "non-renewal", "nonrenewal",
                "underwriting", "company request",
            )):
                return "BREQ"
        
        # NPAY
        if any(k in full for k in (
            "non-payment of premium", "nonpayment of premium",
            "failure to pay premium", "premium not paid",
        )):
            return "NPAY"
        
        # NRNW
        if any(k in full for k in (
            "non-renewal", "nonrenewal", "will not be renewed",
        )):
            return "NRNW"
        
        # UNWR — guard against "Rating/Underwriting Information" headers
        unwr_strong = any(k in full for k in (
            "underwriting guidelines", "company request", "building has been sold",
            "does not meet underwriting", "company decision",
        ))
        unwr_bare = (
            "underwriting" in full
            and any(k in full for k in ("cancellation", "cancelled", "cancel"))
            and "rating/underwriting" not in full
            and "underwriting information" not in full
        )
        if unwr_strong or unwr_bare:
            return "UNWR"

    # Coverage types
    # FLD — guard against flood disclaimers in wind/homeowner policies
    if any(k in full for k in ("flood policy", "flood insurance", "nfip", "fema")):
        fld_excluded = any(k in full for k in (
            "flood coverage is not provided",
            "does not include coverage for damage resulting from flood",
            "does not include coverage for flood",
            "purchase of flood insurance",
            "consider the purchase of flood",
            "does not provide earthquake coverage",
            "does not have coverage for the peril of flood",
        ))
        if not fld_excluded:
            return "FLD"
    # WND — "wind only" is specific; also detect pol. type: wind
    if any(k in full for k in ("wind only", "windstorm insurance policy",
                                "hw-2 wind only", "wind-only policy",
                                "pol. type: wind", "pol.type: wind",
                                "pol type: wind", "aop & hurricane")):
        return "WND"
    # UO — Unit Owner (before HO6, more specific)
    if any(k in full for k in ("unit owner", "master policy")) and any(
        k in full for k in ("certificate of insurance", "condominium unit number",
                             "unit owner mortgagee", "master policy number")):
        return "UO"
    # ERQ — Earthquake — guard against disclaimers
    if any(k in full for k in ("earthquake", "erq", "eq policy")):
        erq_excluded = any(k in full for k in (
            "does not provide earthquake", "earthquake is excluded",
            "does not include earthquake", "peril of earthquake",
            "coverage for earthquake",
        ))
        if not erq_excluded:
            return "ERQ"
    # FIR detection - guard against "dwelling fire" in endorsement/form titles
    fir_strong_patterns = any(k in full for k in (
                                "dwelling fire policy",
                                "dp-3", "dp3", "dp-1",
                                "dfire-s11",
                                "cov type - dwelling fire",
                                "cov type dwelling fire",
                                "coverage type: dwelling fire",
                                "coverage type dwelling fire",
                                # American Modern: "dwelling basic"
                                "policy type: dwelling basic",
                                "dwelling basic policy",
                                "dwelling basic renewal",
                                "dwelling basic policy declaration",
                                # Nationwide
                                "dwelling fire policy number",
                                ))
    fir_dfire_match = bool(re.search(r"\bdfire\b", full)) or bool(re.search(r"\bdfir\b", full))
    fir_dwelling_fire = False
    if "dwelling fire" in full and not fir_strong_patterns:
        dfire_in_endorsement = any(k in full for k in (
            "dwelling fire provisions",
            "dwelling fire endorsement",
            "amendment of home and dwelling fire",
            "amendment of dwelling fire",
        ))
        dfire_as_peril = any(k in full for k in (
            "landlord", "landlord protection",
            "occupancy: tenant", "loss of rent",
        )) or bool(re.search(r"a\s+dwelling\s+fire\s+[\$\d]", full))
        if not dfire_in_endorsement and not dfire_as_peril:
            fir_dwelling_fire = True
    if fir_strong_patterns or fir_dfire_match or fir_dwelling_fire:
        return "FIR"
    # HAZ — Dwelling Special (American Modern) + other commercial/non-residential
    if any(k in full for k in ("dwelling special", "policy type: dwelling special",
                                "dwelling special policy")):
        return "HAZ"
    if any(k in full for k in ("house & home", "house and home",
                                "policy type: house")):
        return "HAZ"
    if any(k in text for k in ("hazard", " haz ")):
        return "HAZ"
    # EDI HAZ patterns
    if any(k in full for k in ("cov type - home owners", "cov type home owners",
                                "home-811", "home-s11", "coverage amt opt a")):
        return "HAZ"
    if any(k in text for k in ("ho-6", "ho6")):
        return "HO6"
    # HO6 — condominium detection
    if any(k in full for k in ("condominium new business", "condominium renewal",
                                "condominium policy change", "condominium policy declaration",
                                "policy type: condominium", "e&s multi-peril")):
        return "HO6"
    if "condominium" in text:
        condo_in_form = bool(re.search(
            r"(rental\s+)?condominium\s+unit\s+(form|coverage\s+form)", full
        ))
        strong_ho = any(k in full for k in (
            "homeowners policy", "homeowner policy", "homesaver policy",
            "home protection policy", "homeowners coverage",
        ))
        if not condo_in_form and not strong_ho:
            return "HO6"
    # LL — Landlord
    if any(k in full for k in ("landlord", "rental dwelling", "rental property",
                                "lessor", "occupancy: tenant", "loss of rent")):
        return "LL"
    if "dp3" in text or "dp-3" in text:
        return "DP3"
    # HO — Manufactured home maps to HAZ, not HO
    if any(k in full for k in ("manufactured home", "mobile home", "mobilehome",
                                "policy type: manufactured home")):
        return "HAZ"
    if any(k in full for k in ("homeowner", "ho-3", "ho3", "home protection",
                                "homeowners pol", "homeowner pol", "homesaver")):
        return "HO"
    # HO from coverage structure  
    ho_markers = ["coverage a", "coverage b", "coverage c", "coverage d",
                  "coverage e", "coverage f", "personal liability",
                  "dwelling", "other structures", "deductible"]
    if sum(1 for m in ho_markers if m in full) >= 3:
        return "HO"
    return "OTH"


# ============================================================
# >>>  MAIN ROUTER  <<<
# ============================================================

def route(
    lines: List[str],
    doc_type: Optional[str] = None,
    policy_type: Optional[str] = None,
    layout_elements: Optional[List[Dict]] = None,
) -> RoutingResult:
    """
    THE single decision function.

    Input:  OCR lines (+ optional pre-classification)
    Output: RoutingResult with approach, target fields, and fallback info
    """
    # --- Auto-classify if not provided ---
    if not doc_type or doc_type == "OTH":
        doc_type = classify_document(lines) 
    if doc_type not in ALLOWED_DOC_TYPES:
        doc_type = "OTH"
    # Enforce business-allowed document types only
    if not policy_type or policy_type == "OTH":
        policy_type = classify_policy(lines)

    # --- Structural signals ---
    has_tables = _detect_tables(lines)
    if layout_elements:
        has_tables = has_tables or any(
            "table" in str(e.get("role", "")).lower()
            for e in layout_elements
        )
    is_fax     = _detect_fax_packet(lines)
    is_simple  = _detect_simple(lines)
    carrier    = _detect_carrier_hint(lines)

    # --- INS Validation §3: Subtype detection ---
    doc_subtype = _detect_doc_subtype(lines)

    # --- INS Validation §2: Force multi-page for subtypes that span pages ---
    force_multi_page = doc_subtype in (
        "FLOOD", "FLOOD_PQ", "COMMERCIAL", "COMMERCIAL_BOP",
        "MORTGAGE_DEC", "POLICY_CHANGE",
    ) or policy_type in (
        "FLD", "HO6", "HAZ", "WND", "LL", "UO",
    )

    # --- Field requirements ---
    req = REQUIRED_FIELDS.get(doc_type, REQUIRED_FIELDS["OTH"])
    opt = OPTIONAL_FIELDS.get(doc_type, OPTIONAL_FIELDS["OTH"])

    def _r(approach, reason, **kw):
        kw.setdefault("is_multi_page", force_multi_page)
        return RoutingResult(
            approach=approach, doc_type=doc_type, policy_type=policy_type,
            required_fields=req, optional_fields=opt,
            carrier_hint=carrier, has_tables=has_tables,
            doc_subtype=doc_subtype,
            reason=reason, **kw,
        )

    # ==========================================================
    # DECISION TREE  (matches ALL 6 strategy tables)
    # ==========================================================

    # ─── PQ / FAX PACKETS ───────────────────────────────────
    # Default: SC → SARDE → LATE (full cascade)
    # Exception: if we can detect what's INSIDE the packet,
    #   route to that doc's native approach instead
    if doc_type == "PQ":
        inner = _detect_inner_doc_type(lines)
        # DOI/CAN/EDI inside PQ → DTE
        if inner in ("DOI", "CAN", "EDI"):
            inner_req = REQUIRED_FIELDS.get(inner, REQUIRED_FIELDS["PQ"])
            inner_opt = OPTIONAL_FIELDS.get(inner, OPTIONAL_FIELDS["PQ"])
            return RoutingResult(
                approach=Approach.DTE,
                doc_type=inner,
                policy_type=policy_type,
                required_fields=inner_req,
                optional_fields=inner_opt,
                carrier_hint=carrier,
                has_tables=has_tables,
                reason=f"PQ wrapping {inner} → DTE",
                is_multi_page=True,
            )
        # COI inside PQ → SC+TE → DTE
        if inner == "COI":
            inner_req = REQUIRED_FIELDS.get(inner, REQUIRED_FIELDS.get("OTH", []))
            inner_opt = OPTIONAL_FIELDS.get(inner, OPTIONAL_FIELDS.get("OTH", []))
            return RoutingResult(
                approach=Approach.SC_TE_DTE,
                doc_type=inner,
                policy_type=policy_type,
                required_fields=inner_req,
                optional_fields=inner_opt,
                carrier_hint=carrier,
                has_tables=has_tables,
                reason=f"PQ wrapping {inner} → SC+TE → DTE",
                is_multi_page=True,
            )
        # RNW inside PQ → SARDE + LATE (standard renewal approach)
        if inner == "RNW":
            rnw_req = REQUIRED_FIELDS.get("RNW", req)
            rnw_opt = OPTIONAL_FIELDS.get("RNW", opt)
            approach = Approach.SARDE_LATE if (has_tables or policy_type in TABLE_POLICY_TYPES) else Approach.SARDE
            return RoutingResult(
                approach=approach,
                doc_type="RNW",
                policy_type=policy_type,
                required_fields=rnw_req,
                optional_fields=rnw_opt,
                carrier_hint=carrier,
                has_tables=has_tables,
                reason=f"PQ wrapping RNW ({policy_type}) → {approach.value}",
                is_multi_page=True,
            )
        # General PQ → full cascade
        return _r(Approach.SC_SARDE_LATE,
                  "Fax/packet → SC → SARDE → LATE",
                  is_multi_page=True)

    # ─── CANCELLATIONS (includes non-renewal) ─────────────────
    # CAN → DTE by default
    # CAN + FLD (flood/underwriting cancel) → SC+TE (table 3)
    if doc_type == "CAN":
        if policy_type in ("BREQ", "NPAY", "NRNW", "UNWR", "CEL"):
            return _r(Approach.DTE,
                    f"Cancellation subtype {policy_type} → DTE")
        if policy_type == "FLD":
            return _r(Approach.SC_TE,
                    "Flood cancellation → SC+TE")
        return _r(Approach.DTE,
                "Cancellation → DTE")

    # ─── DELETION OF INTEREST ───────────────────────────────
    # DOI + HO  → SARDE  (policy change, table 3)
    # DOI + HAZ → SC+TE → DTE  (table 2)
    # DOI + OTH/FIR/other → DTE  (table 3,4)
    if doc_type == "DOI":
        if policy_type in ("HO", "HO3"):
            return _r(Approach.SARDE,
                      f"DOI + {policy_type} (policy change) → SARDE")
        if policy_type == "HAZ":
            return _r(Approach.SC_TE_DTE,
                      "DOI + HAZ → SC+TE → DTE")
        return _r(Approach.DTE,
                  f"DOI ({policy_type}) → DTE")
 
    # ─── SEMI-TEMPLATE DOCS ────────────────────────────────
    # COI, RNS, BIN → SC+TE → DTE
    # Note: TPN (Third Party Notice) is no longer returned as a document type.
    # It's mapped to CAN (if termination) or COI (if notification) by classify_doc_type.
    # Note: BREQ (Borrower Request) is no longer returned as a document type.
    # It's mapped to CAN and returned as a policy_type by policy_classifier.
    if doc_type in ("COI", "RNS", "BIN"):
        return _r(Approach.SC_TE_DTE,
                  f"Semi-template ({doc_type}) → SC+TE → DTE")

    # ─── INVOICES ───────────────────────────────────────────
    # INV + tables → SC+TE + LATE  (table 2: INV HO, INV LL)
    # INV + HO6 + simple → LORH   (table 2: INV HO6)
    # INV other → SC+TE           (table 2: INV HAZ, table 4: INV OTH)
    # Note: FPN (Force Placed Notice) removed from valid document types
    if doc_type == "INV":
        if has_tables:
            return _r(Approach.SC_TE_LATE,
                      "Invoice with tables → SC+TE + LATE")
        if is_simple and policy_type in ("HO6", "OTH"):
            return _r(Approach.LORH,
                      "Simple invoice → LORH")
        return _r(Approach.SC_TE,
                  "Standard invoice → SC+TE")

    # ─── RENEWALS / DECLARATIONS ────────────────────────────
    # RNW + WND → DTE  (table 5: wind renewal/change)
    # RNW + EDI → DTE  (table 5: RNW HO EDI)
    # RNW + HO/FIR/FLD/HAZ/HO6/DP3 → SARDE + LATE
    # RNW + OTH (landlord etc) → SARDE + LATE if tables, SARDE otherwise
    if doc_type == "RNW":
        # Wind renewals use template extraction
        if policy_type == "WND":
            return _r(Approach.DTE,
                      "Wind renewal → DTE")
        # Check for EDI signal even when doc_type=RNW
        if lines:
            head_lower = " ".join(lines[:20]).lower()
            if "edi" in head_lower or "electronic data" in head_lower:
                return _r(Approach.DTE,
                          "EDI renewal → DTE")
        # Known table-heavy policy types always get LATE
        if policy_type in TABLE_POLICY_TYPES:
            return _r(Approach.SARDE_LATE,
                      f"Renewal ({policy_type}) → SARDE + LATE")
        # OTHnown policy with detected tables
        if has_tables:
            return _r(Approach.SARDE_LATE,
                      "Renewal with tables → SARDE + LATE")
        # Plain renewal, no tables
        return _r(Approach.SARDE,
                  "Simple renewal → SARDE")

    # ─── OTH / OTHNOWN ─────────────────────────────────────
    # OTH invoice-like → SC+TE  (table 4)
    if doc_type == "OTH":
        return _r(Approach.SC_TE,
                  "OTHnown doc → SC+TE")

    # ─── VERY SIMPLE OTHNOWN → LORH ────────────────────────
    if is_simple:
        return _r(Approach.LORH, "Simple OTHnown → LORH")

    # ─── DEFAULT → SARDE ────────────────────────────────────
    return _r(Approach.SARDE, "Default → SARDE")


# ############################################################
#
#  PART 2 — DTE EXTRACTION
#  Direct Template Extraction for template-driven documents
#
# ############################################################

# Shared regex patterns
_DATE_RE      = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
_DATE_LONG_RE = re.compile(
    r"((?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},?\s+\d{4})",
    re.I,
)
_POLICY_LABEL_RE = re.compile(
    r"(?:policy\s*(?:number|no\.?|#)|"
    r"nfip\s+policy\s*(?:number|no\.?|#)|"
    r"dwelling\s+(?:fire\s+)?policy\s*(?:number|no\.?))\s*[:\s]*"
    r"([A-Z0-9][\w\s\-]{4,25})",
    re.I,
)
_LOAN_LABEL_RE = re.compile(
    r"(?:loan\s*(?:number|no\.?|#|id)|"
    r"loan/contract\s*(?:number|#)|"
    r"mortgage\s+loan\s*no\.?|"
    r"ln\s*#)\s*[:\s]*"
    r"([\d][\d\s\-]{5,20})",
    re.I,
)
_NAME_LABEL_RE = re.compile(
    r"(?:(?:named?\s+)?insured|policyholder)\s*[:\s]*"
    r"([A-Z][A-Za-z,.\s&'-]{3,60})",
    re.I,
)
_CARRIER_LABEL_RE = re.compile(
    r"(?:carrier|insurer|underwritten\s+by|insurance\s+company)"
    r"\s*[:\s]*"
    r"([A-Z][A-Za-z\s&'.,-]{5,60})",
    re.I,
)
_MORTGAGE_LABEL_RE = re.compile(
    r"(?:mortgage(?:e)?\s*(?:company)?|"
    r"lender|loss\s+payee|"
    r"mortgage\s+holder|"
    r"mortgage\s+servicing\s+agency|"
    r"lien\s*holder|"
    r"mortgagee/loss\s*payee|"
    r"first\s+mortgage|"
    r"1st\s+mortgage)"
    r"\s*[:\s]*"
    r"([A-Z][A-Za-z\s&'.,-]{4,60})",
    re.I,
)
_MONEY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def _first_date(text: str) -> Optional[str]:
    """Extract the first date found in text."""
    m = _DATE_LONG_RE.search(text)
    if m:
        return m.group(1)
    m = _DATE_RE.search(text)
    if m:
        return m.group(1)
    return None


def _clean_extracted(v: str) -> str:
    """Minimal cleanup for extracted values."""
    v = re.sub(r"\s+", " ", v).strip(" ,.;:-")
    return v


def _candidate(value: str, source: str, confidence: float) -> Dict:
    return {
        "value": _clean_extracted(value),
        "confidence": confidence,
        "source": source,
    }


# Shared known carrier names for fallback detection
_KNOWN_CARRIER_NAMES = {
    "allstate", "citizens", "citizens property", "state farm",
    "usaa", "travelers", "progressive", "nationwide",
    "liberty mutual", "amica", "american family", "farmers",
    "erie", "auto-owners", "chubb", "hanover", "hartford",
    "safeco", "federated national", "universal property",
    "heritage", "peoples trust", "security first", "tower hill",
    "florida peninsula", "homeowners choice", "allied trust",
    "aegis", "encompass", "southern oak",
}


def _try_known_carrier_fallback(
    lines: List[str],
    out: Dict[str, Dict],
    source_prefix: str = "dte",
) -> None:
    """Scan first 15 lines for known carrier names.
    Used as final fallback when carrier has no 'insurance'/'company' keywords."""
    if "carrier_name" in out:
        return
    for line in lines[:15]:
        ll = line.lower().strip()
        for c in _KNOWN_CARRIER_NAMES:
            if c == ll or ll.startswith(c + " ") or ll == c + ".":
                out["carrier_name"] = _candidate(
                    line.strip().upper(), f"{source_prefix}_carrier_known", 0.92)
                return


# ============================================================
# DTE: CANCELLATION TEMPLATE
# ============================================================

def _dte_cancellation(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for CAN documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)
    text_lower = text.lower()

    # Policy number
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), "dte_can_policy", 0.95)
    # Fallback: inline "Policy TX-HOV-XXXXX" pattern
    if "policy_number" not in out:
        m = re.search(r'(?i)Policy\s+([A-Z]{2}[\-]?[A-Z]{2,4}[\-]?\d{5,}[\-]?\d*)', text)
        if m:
            out["policy_number"] = _candidate(
                m.group(1).strip(), "dte_can_policy_inline", 0.92)

    # Insured name
    m = _NAME_LABEL_RE.search(text)
    if m:
        name = m.group(1).strip()
        # Truncate at address patterns (digit + street suffix)
        addr_m = re.search(r'\s+\d+\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|'
                           r'dr|drive|ln|lane|ct|cir|way)\b', name, re.I)
        if addr_m:
            name = name[:addr_m.start()].strip()
        # Truncate at standalone digit blocks (address start)
        addr_m2 = re.search(r'\s+\d{2,}\s+[A-Z]', name)
        if addr_m2 and len(name[:addr_m2.start()].split()) >= 2:
            name = name[:addr_m2.start()].strip()
        if name:
            out["insured_name"] = _candidate(
                name, "dte_can_name", 0.93)

    # --- CANCELLATION DATE (expanded triggers) ---
    for idx, line in enumerate(lines):
        ll = line.lower()
        if "cancellation_date" not in out:
            if any(k in ll for k in (
                "cancellation date", "cancel date", "date of cancellation",
                "termination date", "cancellation effective",
                "cancelled effective", "will be cancelled",
                "policy cancellation date",
                "terminate this policy effective",
                "coverage will cease", "policy will cancel",
                "cancel effective",
            )):
                d = _first_date(line)
                if d:
                    out["cancellation_date"] = _candidate(
                        d, "dte_can_date", 0.96)
            # "non-renewal date" pattern
            elif any(k in ll for k in (
                "non-renewal date", "nonrenewal date",
                "non-renewed as of", "will be non-renewed",
            )):
                d = _first_date(line)
                if d:
                    out["cancellation_date"] = _candidate(
                        d, "dte_can_nrnw_date", 0.94)
            # "cancelled...on DATE" sentence pattern
            elif ("cancelled" in ll or "canceled" in ll) and "on " in ll:
                d = _first_date(line)
                if d:
                    out["cancellation_date"] = _candidate(
                        d, "dte_can_date_sentence", 0.90)
            # "Eff Die" / "Eff Date" EDI pattern
            elif re.search(r'(?i)eff\s*d(?:ie|ate|t)\s', line):
                d = _first_date(line)
                if d:
                    out["cancellation_date"] = _candidate(
                        d, "dte_can_date_edi", 0.88)

    # Also store cancellation_date as expiration_date for CAN documents
    if "cancellation_date" in out and "expiration_date" not in out:
        out["expiration_date"] = _candidate(
            out["cancellation_date"]["value"],
            "dte_can_exp_from_cancel", 0.90)

    # --- EFFECTIVE DATE (policy inception / start date) ---
    for line in lines:
        ll = line.lower()
        if "effective_date" not in out:
            if any(k in ll for k in (
                "inception date", "policy effective date",
                "effective date of policy", "policy period",
                "policy term", "pol from", "pol. from",
                "coverage effective",
            )):
                d = _first_date(line)
                if d:
                    # Don't use cancellation date as effective date
                    cancel_val = out.get("cancellation_date", {}).get("value", "")
                    if d != cancel_val:
                        out["effective_date"] = _candidate(
                            d, "dte_can_inception", 0.90)

    # --- CANCELLATION REASON (expanded) ---
    for line in lines:
        ll = line.lower()
        if "cancellation_reason" not in out:
            # Explicit "Reason:" label
            if "reason" in ll and ":" in line:
                _, _, val = line.partition(":")
                val = val.strip()
                if val and len(val) > 3:
                    out["cancellation_reason"] = _candidate(
                        val, "dte_can_reason", 0.92)
            # Keyword-based reason detection
            elif "non-payment" in ll or "nonpayment" in ll or "non pay" in ll:
                out["cancellation_reason"] = _candidate(
                    "Non-payment of premium", "dte_can_reason", 0.90)
            elif "borrower request" in ll or "borrower-request" in ll:
                out["cancellation_reason"] = _candidate(
                    "Borrower request", "dte_can_reason", 0.90)
            elif "insured request" in ll or "insured named below has requested" in ll:
                out["cancellation_reason"] = _candidate(
                    "Insured request", "dte_can_reason", 0.90)
            elif "non-renewal" in ll or "nonrenewal" in ll or "non-renewed" in ll:
                out["cancellation_reason"] = _candidate(
                    "Non-renewal", "dte_can_reason", 0.90)
            elif "underwriting" in ll:
                out["cancellation_reason"] = _candidate(
                    "Underwriting", "dte_can_reason", 0.88)
            elif "building has been sold" in ll or "property sold" in ll:
                out["cancellation_reason"] = _candidate(
                    "Building sold/removed/destroyed", "dte_can_reason", 0.90)
            elif "removed, destroyed" in ll or "removed or destroyed" in ll:
                out["cancellation_reason"] = _candidate(
                    "Building sold/removed/destroyed", "dte_can_reason", 0.88)
            elif "insured - non pay" in ll:
                out["cancellation_reason"] = _candidate(
                    "Insured - Non Pay", "dte_can_reason", 0.90)
            elif "customer initiated" in ll:
                out["cancellation_reason"] = _candidate(
                    "Cancellation Customer Initiated", "dte_can_reason", 0.88)
            elif "premium payment has not been received" in ll:
                out["cancellation_reason"] = _candidate(
                    "Non-payment of premium", "dte_can_reason", 0.88)
            elif "no longer required by lender" in ll:
                out["cancellation_reason"] = _candidate(
                    "No longer required by lender", "dte_can_reason", 0.88)

    # Carrier — try labeled first
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_can_carrier", 0.90)

    # Carrier — keyword fallback (scan first 20 lines for "insurance" + entity type)
    if "carrier_name" not in out:
        for line in lines[:25]:
            ll = line.lower().strip()
            if not ll or len(ll) > 120:
                continue
            has_ins = any(w in ll for w in ("insurance", "indemnity", "casualty",
                                             "underwriters", "assurance"))
            has_entity = any(w in ll for w in ("company", "co", "co.", "exchange",
                                                "group", "mutual", "corp",
                                                "corporation"))
            has_abbrev = bool(re.search(r'\b(?:ins|prop|cas)\b', ll))
            has_skip = any(w in ll for w in ("agency", "agent", "services",
                                              "broker", "producer", "processing",
                                              "center", "relations"))
            if has_ins and (has_entity or has_abbrev) and not has_skip:
                val = line.strip()
                val = re.sub(r'\s+(?:Mortgagee|Lender|Service).*$', '',
                             val, flags=re.I).strip()
                val = re.sub(r'^\d+\s+', '', val).strip()  # strip leading numbers
                if val and len(val) > 5:
                    out["carrier_name"] = _candidate(
                        val.upper(), "dte_can_carrier_kw", 0.85)
                    break

    # Carrier — known name fallback (scan first 15 lines for exact known carriers)
    _try_known_carrier_fallback(lines, out, "dte_can")

    # Mortgage company — try labeled first (use finditer to skip false positives)
    for m in _MORTGAGE_LABEL_RE.finditer(text):
        if "mortgage_company" in out:
            break
        val = m.group(1).strip()
        # Skip false positives: "MORTGAGEE COPY", "MORTGAGEE CERTIFICATE"
        val_lower = val.lower()
        if any(fp in val_lower for fp in ("copy", "certificate", "customer service",
                                           "notice", "information")):
            continue
        # Clean ISAOA/ATIMA suffixes (use DOTALL to consume across newlines)
        val = re.sub(r'\s+(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA|ITS\s+SCRS?\s*&?/?\s*OR\s+ASSIGNS?\s+ATIMA).*',
                     '', val, flags=re.I | re.DOTALL).strip()
        # Remove address components that leaked into capture
        val = re.sub(r'\s*(?:PO\s+BOX|P\.?O\.?\s*BOX).*', '', val, flags=re.I | re.DOTALL).strip()
        val = re.sub(r'\s*\d+\s+\w+\s+(?:ST|STREET|AVE|RD|DR|LN|BLVD|CT|WAY)\b.*',
                     '', val, flags=re.I | re.DOTALL).strip()
        # Collapse newlines to spaces
        val = re.sub(r'\s+', ' ', val).strip()
        if val and len(val) > 3:
            out["mortgage_company"] = _candidate(
                val, "dte_can_mortgage", 0.88)

    # Mortgage — ISAOA/ATIMA fallback (scan for entity + ISAOA on same line or preceding)
    if "mortgage_company" not in out:
        for idx, line in enumerate(lines):
            if re.search(r'\b(?:ISAOA|ATIMA)\b', line, re.I):
                name = re.sub(r'\s+(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA|ITS\s+SCRS?).*$',
                              '', line, flags=re.I).strip()
                name = re.sub(r'^\d+\w*\s+', '', name).strip()
                name = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                              name, flags=re.I).strip()
                # Also check if the PRECEDING line has the company name
                # (common: line1="EVERETT FINANCIAL INC DBA SUPREME", line2="LENDING ISAOA")
                if (not name or len(name) <= 3) and idx > 0:
                    prev_line = lines[idx - 1].strip()
                    if prev_line and len(prev_line) > 3 and not re.match(r'^\d', prev_line):
                        if not re.search(r'(?i)insured|policy|coverage|mortgagee', prev_line):
                            # Combine prev line + current line before ISAOA
                            combined = prev_line + " " + re.sub(
                                r'\s+(?:ISAOA|ATIMA).*$', '', line, flags=re.I
                            ).strip()
                            combined = re.sub(r'\s+', ' ', combined).strip()
                            if combined and len(combined) > 3:
                                name = combined
                if name and len(name) > 3:
                    # Skip if this looks like an insured name block
                    if idx > 0 and re.search(r'(?i)insured', lines[idx - 1]):
                        continue
                    out["mortgage_company"] = _candidate(
                        name, "dte_can_mortgage_isaoa", 0.82)
                    break
    # Mortgage — "Mortgagee Copy" or "1st Mortgagee:" context
    if "mortgage_company" not in out:
        for idx, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in ("mortgagee copy", "1st mortgagee",
                                      "mortgagee or interested",
                                      "lien holder")):
                # Check next 1-2 lines for the company name
                for offset in range(0, 3):
                    if idx + offset >= len(lines):
                        break
                    cand = lines[idx + offset].strip()
                    # Skip the label line itself if it doesn't have a value
                    if offset == 0 and ":" in cand:
                        _, _, cand = cand.partition(":")
                        cand = cand.strip()
                    if cand and len(cand) > 3 and not re.match(r'^\d', cand):
                        cand = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                                      cand, flags=re.I).strip()
                        cand = re.sub(r'\s+(?:ISAOA|ATIMA).*$', '',
                                      cand, flags=re.I).strip()
                        if cand and len(cand) > 3:
                            out["mortgage_company"] = _candidate(
                                cand, "dte_can_mortgage_context", 0.82)
                            break
                if "mortgage_company" in out:
                    break

    # Property address — expanded patterns
    if "property_address" not in out:
        for idx, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in ("property address", "property location",
                                      "location of property", "risk location",
                                      "covered property", "prop loc",
                                      "insured property", "premises")):
                # Try inline first (after label)
                if ":" in line:
                    _, _, val = line.partition(":")
                    val = val.strip()
                    if val and re.search(r'\d+.*\b[A-Z]{2}\b', val):
                        out["property_address"] = _candidate(
                            val.rstrip(".,"), "dte_can_addr_inline", 0.88)
                        continue
                # Multi-line address collection
                parts = []
                for offset in range(1, 4):
                    if idx + offset >= len(lines):
                        break
                    addr = lines[idx + offset].strip()
                    if not addr or re.match(r'(?i)^(primary|building|contents|coverage)', addr):
                        break
                    parts.append(addr)
                    if re.search(r'\b[A-Z]{2}\s*\d{5}', addr):
                        break
                if parts:
                    full_addr = ", ".join(parts).rstrip(".,")
                    out["property_address"] = _candidate(
                        full_addr, "dte_can_addr_multi", 0.85)

    # Property address — scan for "Named Insured and Address" block
    if "property_address" not in out:
        for idx, line in enumerate(lines):
            ll = line.lower()
            if "named insured and address" in ll or "name and address of insured" in ll:
                # Scan next lines for street address
                for offset in range(1, 5):
                    if idx + offset >= len(lines):
                        break
                    addr = lines[idx + offset].strip()
                    if re.search(r'\d+\s+.+?\b(st|street|ave|avenue|rd|road|blvd|'
                                 r'ln|lane|dr|drive|ct|cir|way)\b', addr, re.I):
                        # Collect address + city/state/zip
                        addr_parts = [addr]
                        nxt = lines[idx + offset + 1].strip() if idx + offset + 1 < len(lines) else ""
                        if nxt and re.search(r'\b[A-Z]{2}\s*\d{5}', nxt):
                            addr_parts.append(nxt)
                        out["property_address"] = _candidate(
                            ", ".join(addr_parts).rstrip(".,"),
                            "dte_can_addr_insured_block", 0.82)
                        break

    # Loan number
    m = _LOAN_LABEL_RE.search(text)
    if m:
        digits = re.sub(r"[\s\-]", "", m.group(1))
        if len(digits) >= 5:
            out["loan_number"] = _candidate(
                digits, "dte_can_loan", 0.90)

    return out


# ============================================================
# DTE: NON-RENEWAL TEMPLATE
# ============================================================

def _dte_nonrenewal(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for NRNW documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)

    # Policy number
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), "dte_nrnw_policy", 0.95)

    # Insured name
    m = _NAME_LABEL_RE.search(text)
    if m:
        out["insured_name"] = _candidate(
            m.group(1).strip(), "dte_nrnw_name", 0.93)

    # Non-renewal / Expiration date
    for line in lines:
        ll = line.lower()
        if "expiration_date" not in out:
            if any(k in ll for k in ("expiration", "expire", "will not renew",
                                      "policy end", "coverage end",
                                      "non-renewal date", "nonrenewal date",
                                      "will be non-renewed")):
                d = _first_date(line)
                if d:
                    out["expiration_date"] = _candidate(
                        d, "dte_nrnw_expiration", 0.95)
                    # Also store as cancellation_date
                    if "cancellation_date" not in out:
                        out["cancellation_date"] = _candidate(
                            d, "dte_nrnw_cancel_date", 0.93)

    # Effective date (sometimes present as "effective date" or "policy period")
    for line in lines:
        ll = line.lower()
        if "effective_date" not in out:
            if any(k in ll for k in ("effective date", "policy period",
                                      "inception date", "pol from")):
                d = _first_date(line)
                if d:
                    # Don't confuse with cancellation/expiration date
                    cancel_val = out.get("cancellation_date", {}).get("value", "")
                    exp_val = out.get("expiration_date", {}).get("value", "")
                    if d != cancel_val and d != exp_val:
                        out["effective_date"] = _candidate(
                            d, "dte_nrnw_effective", 0.90)

    # Cancellation reason — always "Non-renewal" for NRNW docs
    if "cancellation_reason" not in out:
        out["cancellation_reason"] = _candidate(
            "Non-renewal", "dte_nrnw_reason", 0.92)

    # Carrier — try label first, then keyword
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_nrnw_carrier", 0.90)
    if "carrier_name" not in out:
        for line in lines[:25]:
            ll = line.lower().strip()
            if not ll or len(ll) > 120:
                continue
            has_ins = any(w in ll for w in ("insurance", "indemnity", "casualty"))
            has_entity = any(w in ll for w in ("company", "co", "exchange",
                                                "group", "mutual", "corp"))
            has_skip = any(w in ll for w in ("agency", "agent", "services",
                                              "broker", "producer"))
            if has_ins and has_entity and not has_skip:
                val = line.strip()
                val = re.sub(r'\s+\d+\s+.*$', '', val).strip()  # strip address
                if val and len(val) > 5:
                    out["carrier_name"] = _candidate(
                        val.upper(), "dte_nrnw_carrier_kw", 0.85)
                    break

    # Property address
    if "property_address" not in out:
        for idx, line in enumerate(lines):
            ll = line.lower()
            if any(k in ll for k in ("location of property", "property location",
                                      "property address", "risk location",
                                      "covered property")):
                parts = []
                for offset in range(1, 4):
                    if idx + offset >= len(lines):
                        break
                    addr = lines[idx + offset].strip()
                    if not addr:
                        break
                    parts.append(addr)
                    if re.search(r'\b[A-Z]{2}\s*\d{5}', addr):
                        break
                if parts:
                    out["property_address"] = _candidate(
                        ", ".join(parts).rstrip(".,"),
                        "dte_nrnw_addr", 0.85)

    # Mortgage — ISAOA/ATIMA detection
    if "mortgage_company" not in out:
        for idx, line in enumerate(lines):
            if re.search(r'\b(?:ISAOA|ATIMA)\b', line, re.I):
                name = re.sub(r'\s+(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA).*$',
                              '', line, flags=re.I).strip()
                name = re.sub(r'^\d+\w*\s+', '', name).strip()
                name = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                              name, flags=re.I).strip()
                if name and len(name) > 3:
                    if idx > 0 and re.search(r'(?i)insured', lines[idx - 1]):
                        continue
                    out["mortgage_company"] = _candidate(
                        name, "dte_nrnw_mortgage_isaoa", 0.82)
                    break

    return out


# ============================================================
# DTE: DELETION OF INTEREST TEMPLATE
# ============================================================

def _dte_doi(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for DOI documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)
    text_lower = text.lower()

    # Policy number
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), "dte_doi_policy", 0.95)

    # Mortgage company — try labeled first
    m = _MORTGAGE_LABEL_RE.search(text)
    if m:
        out["mortgage_company"] = _candidate(
            m.group(1).strip(), "dte_doi_mortgage", 0.93)
    
    # --- INS batch Section 8: Flood mortgage patterns ---
    if "mortgage_company" not in out:
        for line in lines:
            ll = line.lower()
            if any(k in ll for k in (
                "first mortgage:", "second mortgage:",
                "loss payee:", "mortgagee/loss payee:",
                "1st mortgage:", "2nd mortgage:",
            )):
                if ":" in line:
                    _, _, val = line.partition(":")
                    val = val.strip()
                    # Clean ISAOA/ATIMA suffixes
                    val = re.sub(r'\s+(?:ISAOA|ATIMA).*$', '', val, flags=re.I).strip()
                    if val and len(val) > 3:
                        out["mortgage_company"] = _candidate(
                            val, "dte_doi_mortgage_flood", 0.90)
                        break

    # Loan number — expanded aliases per Section 3
    m = _LOAN_LABEL_RE.search(text)
    if m:
        digits = re.sub(r"[\s\-]", "", m.group(1))
        out["loan_number"] = _candidate(
            digits, "dte_doi_loan", 0.93)

    # Insured name
    m = _NAME_LABEL_RE.search(text)
    if m:
        out["insured_name"] = _candidate(
            m.group(1).strip(), "dte_doi_name", 0.88)

    # Carrier
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_doi_carrier", 0.88)
    _try_known_carrier_fallback(lines, out, "dte_doi")

    # Property address — look for street patterns
    for line in lines:
        if "property_address" not in out:
            if re.search(
                r"\d+\s+.+?\b(st|street|ave|avenue|rd|road|blvd|"
                r"lane|ln|drive|dr|ct|court)\b", line, re.I
            ):
                ll = line.lower()
                # Avoid picking up mortgage company addresses
                if not any(k in ll for k in ("troy", "po box", "remit")):
                    out["property_address"] = _candidate(
                        line.strip(), "dte_doi_address", 0.85)

    # --- INS batch Section 11: Third-party event fields ---
    if "mortgage interest removed" in text_lower:
        out["third_party_removed"] = _candidate(
            "True", "dte_doi_mir", 0.96)
    if "deleted as loss payee" in text_lower:
        out["third_party_removed"] = _candidate(
            "True", "dte_doi_deleted_lp", 0.95)
    # Extract cancellation date for third party interest
    for line in lines:
        ll = line.lower()
        if "cancellation date for third party" in ll:
            d = _first_date(line)
            if d:
                out["third_party_cancellation_date"] = _candidate(
                    d, "dte_doi_tp_cancel_date", 0.93)

    return out


# ============================================================
# DTE: EDI IMAGE TEMPLATE
# ============================================================

def _dte_edi(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for EDI image documents.
    
    Per INS batch Section 7: EDI documents use strict key-value parsing.
    Switch to key-value parsing when 'Electronic Image Generated for EDI Data'
    is detected. Do NOT use regex anchor logic.
    """
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)

    # --- INS batch Section 7: Strict key-value parsing for EDI ---
    # Build key-value pairs from all lines
    kv_pairs = {}
    for line in lines:
        if ":" in line:
            label, _, value = line.partition(":")
            label = label.strip().lower()
            value = value.strip()
            if label and value:
                kv_pairs[label] = value

    # Policy No:
    for label_key in ("policy no", "policy number", "policy no.",
                       "policy #", "policy num"):
        if label_key in kv_pairs:
            val = kv_pairs[label_key].replace(" ", "")
            if len(val) >= 6:
                out["policy_number"] = _candidate(val, "dte_edi_policy_kv", 0.95)
                break
    # Fallback to regex
    if "policy_number" not in out:
        m = _POLICY_LABEL_RE.search(text)
        if m:
            out["policy_number"] = _candidate(
                m.group(1).strip(), "dte_edi_policy", 0.94)

    # Primary Name: / Insured:
    for label_key in ("primary name", "insured", "named insured",
                       "insured name", "policyholder", "customer name"):
        if label_key in kv_pairs:
            name_val = kv_pairs[label_key].strip()
            if name_val and len(name_val) > 2:
                out["insured_name"] = _candidate(name_val, "dte_edi_name_kv", 0.93)
                break
    if "insured_name" not in out:
        m = _NAME_LABEL_RE.search(text)
        if m:
            out["insured_name"] = _candidate(
                m.group(1).strip(), "dte_edi_name", 0.92)

    # Coverage Type:
    for label_key in ("coverage type", "cov type", "covtype",
                       "policy type", "type"):
        if label_key in kv_pairs:
            out["coverage_type"] = _candidate(
                kv_pairs[label_key], "dte_edi_covtype", 0.90)
            break

    # Document Type:
    for label_key in ("document type", "doc type", "document"):
        if label_key in kv_pairs:
            out["document_subtype"] = _candidate(
                kv_pairs[label_key], "dte_edi_doctype", 0.90)
            break

    # Mortgage Clause: / Mortgage Interest Removed
    for label_key in ("mortgage clause", "mortgagee", "loss payee",
                       "mortgage company"):
        if label_key in kv_pairs:
            out["mortgage_company"] = _candidate(
                kv_pairs[label_key], "dte_edi_mortgage_kv", 0.90)
            break
    
    # Check for "Mortgage Interest Removed" signal (Section 11)
    text_lower = text.lower()
    if "mortgage interest removed" in text_lower:
        out["third_party_removed"] = _candidate(
            "True", "dte_edi_mir", 0.95)

    # Dates — scan all lines
    dates_found = []
    for line in lines:
        ll = line.lower()
        d = _first_date(line)
        if d:
            if any(k in ll for k in ("effective", "begin", "start",
                                      "eff date", "eff die", "eff dt")):
                out["effective_date"] = _candidate(d, "dte_edi_eff", 0.93)
            elif any(k in ll for k in ("expir", "end", "term",
                                        "exp date", "exp dt")):
                out["expiration_date"] = _candidate(d, "dte_edi_exp", 0.93)
            elif any(k in ll for k in ("cancel", "termination")):
                out["cancellation_date"] = _candidate(d, "dte_edi_cancel", 0.93)
            else:
                dates_found.append(d)

    # If we found exactly 2 unlabeled dates, assume effective then expiration
    if "effective_date" not in out and "expiration_date" not in out:
        if len(dates_found) >= 2:
            out["effective_date"] = _candidate(
                dates_found[0], "dte_edi_eff_infer", 0.85)
            out["expiration_date"] = _candidate(
                dates_found[1], "dte_edi_exp_infer", 0.85)

    # Carrier
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_edi_carrier", 0.90)
    # Fallback: scan for carrier in KV pairs
    if "carrier_name" not in out:
        for label_key in ("carrier", "insurer", "insurance company",
                           "company name"):
            if label_key in kv_pairs:
                out["carrier_name"] = _candidate(
                    kv_pairs[label_key].upper(), "dte_edi_carrier_kv", 0.88)
                break

    # Loan number
    for label_key in ("loan number", "loan no", "loan #", "loan no.",
                       "loan/contract number", "loan/contract #"):
        if label_key in kv_pairs:
            digits = re.sub(r"[\s\-]", "", kv_pairs[label_key])
            digits = ''.join(c for c in digits if c.isdigit())
            if 6 <= len(digits) <= 18:
                out["loan_number"] = _candidate(
                    digits, "dte_edi_loan_kv", 0.92)
                break

    return out


# ============================================================
# DTE: GENERIC TEMPLATE (BRQ, TPN, COI, RNS, BIN)
# ============================================================

def _dte_generic(lines: List[str], doc_type: str) -> Dict[str, Dict]:
    """Generic template extraction for semi-structured documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)
    src = f"dte_{doc_type.lower()}"

    # Policy number
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), f"{src}_policy", 0.93)

    # Insured name
    m = _NAME_LABEL_RE.search(text)
    if m:
        out["insured_name"] = _candidate(
            m.group(1).strip(), f"{src}_name", 0.90)

    # Carrier
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), f"{src}_carrier", 0.88)
    _try_known_carrier_fallback(lines, out, src)

    # Dates
    for line in lines:
        ll = line.lower()
        d = _first_date(line)
        if d:
            if "effective_date" not in out:
                if any(k in ll for k in ("effective", "begin", "start")):
                    out["effective_date"] = _candidate(
                        d, f"{src}_eff", 0.92)
            if "expiration_date" not in out:
                if any(k in ll for k in ("expir", "end", "term")):
                    out["expiration_date"] = _candidate(
                        d, f"{src}_exp", 0.92)

    # Mortgage
    m = _MORTGAGE_LABEL_RE.search(text)
    if m:
        out["mortgage_company"] = _candidate(
            m.group(1).strip(), f"{src}_mortgage", 0.85)

    # Loan
    m = _LOAN_LABEL_RE.search(text)
    if m:
        digits = re.sub(r"[\s\-]", "", m.group(1))
        out["loan_number"] = _candidate(digits, f"{src}_loan", 0.85)

    return out


# ============================================================
# DTE: PUBLIC ENTRY POINT
# ============================================================

def extract_dte(lines: List[str], doc_type: str) -> Dict[str, Dict]:
    """
    Direct Template Extraction — dispatches to the correct
    template based on document type.

    Called by the orchestrator for DTE and SC+TE→DTE approaches.
    """
    if not lines:
        return {}

    dispatch = {
        "CAN":  _dte_cancellation,
        "DOI":  _dte_doi,
        # REMOVED: "NRNW" - non-renewal is now CAN with policy_type=NRNW
        # EDI dispatch - INS batch Section 7
    }

    extractor = dispatch.get(doc_type)
    if extractor:
        return extractor(lines)
    
    # --- INS batch Section 7: EDI structured format detection ---
    text_lower = " ".join(lines).lower()
    if any(k in text_lower for k in (
        "electronic image generated for edi",
        "electronic image generated",
        "generated for edi",
        "edi data",
        "edi image",
    )):
        return _dte_edi(lines)

    # Generic fallback for COI, RNS, BIN, and other semi-structured docs
    # Note: BRQ (Borrower Request) and TPN (Third Party Notice) are no longer
    # document types - they're handled as policy subtypes or mapped to CAN/DOI
    return _dte_generic(lines, doc_type)


# ############################################################
#
#  PART 3 — LORH EXTRACTION
#  Lightweight OCR Result Heuristic — for trivial documents
#
# ############################################################

def extract_lorh(lines: List[str]) -> Dict[str, Dict]:
    """
    Lightweight OCR Result Heuristic.
    Very simple label:value scanning — no state machine,
    no role tracking.  For documents so simple that anything
    heavier would be wasteful.

    Called by the orchestrator for LORH approach.
    """
    if not lines:
        return {}

    out: Dict[str, Dict] = {}

    # Pre-scan: build label→value pairs from "Label: Value" lines
    kv_pairs: List[Tuple[str, str]] = []
    for line in lines:
        if ":" in line:
            label, _, value = line.partition(":")
            label = label.strip().lower()
            value = value.strip()
            if label and value:
                kv_pairs.append((label, value))

    # --- Policy Number ---
    for label, value in kv_pairs:
        if "policy_number" not in out:
            if any(k in label for k in ("policy number", "policy no",
                                         "policy #", "policy num",
                                         "policy no.")):
                v = value.replace(" ", "")
                if len(v) >= 6:
                    out["policy_number"] = _candidate(
                        v, "lorh_policy", 0.92)

    # --- Insured Name ---
    for label, value in kv_pairs:
        if "insured_name" not in out:
            if any(k in label for k in ("insured", "policyholder",
                                         "primary name", "customer name",
                                         "name")):
                if not any(k in label for k in ("mortgagee", "company",
                                                 "agent", "loss payee",
                                                 "payor")):
                    words = value.split()
                    if 2 <= len(words) <= 6 and not any(
                            c.isdigit() for c in value):
                        out["insured_name"] = _candidate(
                            value, "lorh_name", 0.88)

    # --- Dates ---
    for label, value in kv_pairs:
        if "effective_date" not in out:
            if any(k in label for k in ("effective", "start", "begin")):
                d = _first_date(value)
                if d:
                    out["effective_date"] = _candidate(
                        d, "lorh_eff", 0.90)
        if "expiration_date" not in out:
            if any(k in label for k in ("expir", "end", "term")):
                d = _first_date(value)
                if d:
                    out["expiration_date"] = _candidate(
                        d, "lorh_exp", 0.90)

    # --- Dollar amounts ---
    for label, value in kv_pairs:
        if "total_premium" not in out:
            if any(k in label for k in ("premium", "total", "amount due",
                                         "balance")):
                m = _MONEY_RE.search(value)
                if m:
                    out["total_premium"] = _candidate(
                        "$" + m.group(1), "lorh_premium", 0.85)

    # --- Balance Due (INV-specific) ---
    for label, value in kv_pairs:
        if "balance_due" not in out:
            if any(k in label for k in ("balance", "amount due",
                                         "to pay in full", "pay in full",
                                         "current balance due",
                                         "total amount due")):
                m = _MONEY_RE.search(value)
                if m:
                    out["balance_due"] = _candidate(
                        "$" + m.group(1), "lorh_balance", 0.88)
    # Also scan lines for "Balance (to pay in full)" pattern
    if "balance_due" not in out:
        for line in lines:
            ll = line.lower()
            if any(k in ll for k in ("balance (to pay", "balance due",
                                      "to pay in full amount due",
                                      "current balance due",
                                      "amount due")):
                m = _MONEY_RE.search(line)
                if m:
                    out["balance_due"] = _candidate(
                        "$" + m.group(1), "lorh_balance_scan", 0.85)
                    break

    # --- Issue Date (INV-specific) ---
    for label, value in kv_pairs:
        if "issue_date" not in out:
            if any(k in label for k in ("bill date", "issue date",
                                         "invoice date", "statement date",
                                         "information as of",
                                         "billing date", "due date")):
                d = _first_date(value)
                if d:
                    out["issue_date"] = _candidate(
                        d, "lorh_issue_date", 0.88)
    # Also scan for "Information as of DATE" pattern (Allstate)
    if "issue_date" not in out:
        for line in lines:
            ll = line.lower()
            if "information as of" in ll:
                d = _first_date(line)
                if d:
                    out["issue_date"] = _candidate(
                        d, "lorh_issue_date_scan", 0.85)
                    break

    # --- Remit Info (INV-specific) ---
    if "remit_info" not in out:
        for line in lines:
            ll = line.lower()
            m = re.search(r'(?i)(?:make\s+checks?\s+payable\s+to|payable\s+to|'
                          r'remit\s+to|mail\s+to|send\s+payment\s+to)\s*:?\s*(.+)',
                          line)
            if m:
                entity = m.group(1).strip()
                # Remove PO Box and address from the entity name
                entity = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                                entity, flags=re.I).strip()
                entity = re.sub(r'\.\s*$', '', entity).strip()
                if entity and len(entity) > 3:
                    out["remit_info"] = _candidate(
                        entity, "lorh_remit", 0.85)
                    break

    # --- Carrier (scan first 15 lines for "insurance" + company type) ---
    if "carrier_name" not in out:
        for line in lines[:15]:
            ll = line.lower()
            if "insurance" in ll and any(
                w in ll for w in ("company", "co", "exchange", "group",
                                   "mutual", "corp")):
                if not any(w in ll for w in ("agency", "agent", "services")):
                    val = line.strip()
                    # Strip label prefixes
                    val = re.sub(r'^(?:Company|Carrier|Insurer)\s*:\s*',
                                 '', val, flags=re.I).strip()
                    out["carrier_name"] = _candidate(
                        val.upper(), "lorh_carrier", 0.85)
                    break

    # --- Fallback: scan all lines for unlabeled dates ---
    if "effective_date" not in out or "expiration_date" not in out:
        all_dates = []
        for line in lines:
            for m in _DATE_RE.finditer(line):
                all_dates.append(m.group(1))
        if "effective_date" not in out and len(all_dates) >= 1:
            out["effective_date"] = _candidate(
                all_dates[0], "lorh_eff_scan", 0.80)
        if "expiration_date" not in out and len(all_dates) >= 2:
            out["expiration_date"] = _candidate(
                all_dates[1], "lorh_exp_scan", 0.80)