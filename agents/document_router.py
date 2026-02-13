"""
Document Router - CLEAN ARCHITECTURE VERSION
Classification, Routing, DTE & LORH Extraction

CLEAN SEPARATION:
- document_type: Structural (CAN, DOI, RNW, INV, COI, BIN, RNS, OTH, UNK) from document_classifier
- policy_type: Coverage OR cancellation subtype (HO, FIR, BREQ, NRNW, NPAY, UNWR, CEL...) from policy_classifier
- Routing: Based on document_type only (policy_type used for field selection)

IMPORTANT: 
- TPN (Third Party Notice) is NOT a document type - it maps to CAN (if termination) or COI (if notification)
- BREQ/BRQ (Borrower Request) is NOT a document type - it's a policy subtype (cancellation reason)
- NRNW (Non-Renewal) is NOT a document type - it's a policy subtype (cancellation reason)

This file contains THREE concerns that belong together because they
are all driven by document type:

  1. ROUTING   — classify doc → select ONE primary approach
  2. DTE       — Direct Template Extraction (for CAN, DOI, EDI)
  3. LORH      — Lightweight OCR Result Heuristic (for trivial docs)

Routing Table:
┌─────────────────────┬──────────────────────────────────────────────────────┐
│ Approach            │ Best Suited Document Types                          │
├─────────────────────┼──────────────────────────────────────────────────────┤
│ SARDE               │ Renewals, policy changes, amended declarations      │
│ SARDE + LATE        │ Renewals w/ coverage/premium tables (HO,FIR,FLD…)   │
│ SC → SARDE → LATE   │ Fax (PQ) packets, mixed multi-document files        │
│ DTE                 │ Cancellations, interest removals, EDI               │
│ SC+TE → DTE         │ Certificates, third-party notices, binders          │
│ SC+TE + LATE        │ Invoices with transaction tables                    │
│ SC+TE               │ Simple invoices, flood cancellations                │
│ LORH                │ Very simple, single-page invoices/notices           │
└─────────────────────┴──────────────────────────────────────────────────────┘

Agent mapping:
  SARDE → stage1_deterministic_agent.extract_fields
  SC+TE → stage2_semantic_agent.extract_with_ner (calls GLiNER internally)
  LATE  → stage3_layout_agent.extract_with_layoutxlm
  DTE   → THIS FILE: extract_dte()
  LORH  → THIS FILE: extract_lorh()
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re
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
    "RNS", "INV", "DOI", "COI", "UNK"
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
    "INV":  ["policy_number", "insured_name"],
    "CAN":  ["policy_number", "insured_name", "effective_date"],
    "DOI":  ["policy_number", "mortgage_company", "loan_number"],
    "COI":  ["carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date"],
    "RNS":  ["policy_number", "insured_name", "effective_date"],
    "BIN":  ["carrier_name", "policy_number", "insured_name",
             "effective_date"],
    "OTH":  ["policy_number"],
    "UNK":  ["policy_number"],
}

OPTIONAL_FIELDS: Dict[str, List[str]] = {
    "RNW":  ["property_address", "mailing_address", "mortgage_company",
             "loan_number", "total_premium", "agent_name", "agent_phone"],
    "INV":  ["carrier_name", "effective_date", "total_premium",
             "mortgage_company", "loan_number"],
    "CAN":  ["carrier_name", "mortgage_company", "property_address"],
    "DOI":  ["carrier_name", "insured_name", "property_address"],
    "COI":  ["property_address", "mortgage_company"],
    "RNS":  ["carrier_name", "expiration_date"],
    "BIN":  ["expiration_date", "property_address"],
    "OTH":  ["insured_name", "carrier_name"],
    "UNK":  ["insured_name", "carrier_name"],
}

# Policy types with coverage/premium tables → triggers + LATE
TABLE_POLICY_TYPES = {
    "HO", "HO3", "HO6", "FIR", "FLD", "HAZ", "DP3", "WND", "AUTO", "ERQ", "LL", "UO",
    "NRNW", "BREQ", "NPAY", "UNWR", "CEL", "UNK"
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
    # Borrower request or third party notice → CAN
    if "borrower request" in text or "customer initiated" in text:
        return "CAN"
    if "third party notice" in text:
        # Third party notice is a CAN if it mentions termination/cancellation
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
                                "dwelling (coverage a)")):
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
# DOCUMENT-TYPE CLASSIFIER  (rule-based)
# ============================================================
def classify_doc_type(lines: List[str]) -> str:
    """
    Rule-based doc-type classification.
    Specific patterns must be checked in strict priority order.
    """
    if not lines:
        return "UNK"

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
    )):
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
        return "COI"

    # ============================================================
    # 8️⃣ Reinstatement
    # ============================================================
    if any(k in head for k in (
        "reinstatement",
        "reinstated",
        "rescission of cancellation",
    )):
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
        ))
        if not strong_doc_signals:
            return "UNK"

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
    )):
        return "RNW"

    if any(k in full for k in (
        "coverage a",
        "coverage b",
        "dwelling coverage",
        "annual premium",
        "renewal flood insurance",
        "flood insurance policy declarations",
        "agent issued declarations",
        "policy premium",
        "total policy premium",
    )):
        return "RNW"

    return "UNK"

def classify_policy_type(lines: List[str]) -> str:
    """Rule-based policy-type classification."""
    if not lines:
        return "UNK"
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
        ))
        if not fld_excluded:
            return "FLD"
    # WND — "wind only" is specific; "hurricane" alone is too broad
    if any(k in full for k in ("wind only", "windstorm insurance policy",
                                "hw-2 wind only", "wind-only policy")):
        return "WND"
    # FIR detection - guard against "dwelling fire" in endorsement/form titles
    fir_strong_patterns = any(k in full for k in (
                                "dwelling fire policy",
                                "dp-3", "dp3", "dp-1",
                                "dfire-s11",
                                "cov type - dwelling fire",
                                "cov type dwelling fire",
                                "coverage type: dwelling fire",
                                "coverage type dwelling fire"))
    fir_dfire_match = bool(re.search(r"\bdfire\b", full)) or bool(re.search(r"\bdfir\b", full))
    fir_dwelling_fire = False
    if "dwelling fire" in full and not fir_strong_patterns:
        # Guard: "dwelling fire provisions" or similar = endorsement, not policy type
        dfire_in_endorsement = any(k in full for k in (
            "dwelling fire provisions",
            "dwelling fire endorsement",
            "amendment of home and dwelling fire",
            "amendment of dwelling fire",
        ))
        # Guard: "A DWELLING FIRE $..." = peril in coverage table (landlord/HO)
        dfire_as_peril = any(k in full for k in (
            "landlord", "landlord protection",
            "occupancy: tenant", "loss of rent",
        )) or bool(re.search(r"a\s+dwelling\s+fire\s+[\$\d]", full))
        if not dfire_in_endorsement and not dfire_as_peril:
            fir_dwelling_fire = True
    if fir_strong_patterns or fir_dfire_match or fir_dwelling_fire:
        return "FIR"
    if any(k in full for k in ("house & home", "house and home",
                                "policy type: house")):
        return "HAZ"
    if any(k in text for k in ("hazard", " haz ")):
        return "HAZ"
    if any(k in text for k in ("ho-6", "ho6")):
        return "HO6"
    # Guard: "condominium" in form names (e.g., "Rental Condominium Unit Form 664")
    # should NOT trigger HO6. Only match in policy type context.
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
    if "dp3" in text or "dp-3" in text:
        return "DP3"
    if any(k in full for k in ("homeowner", "ho-3", "ho3", "home protection",
                                "homeowners pol", "homeowner pol", "homesaver")):
        return "HO"
    return "UNK"


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
    if not doc_type or doc_type == "UNK":
        doc_type = classify_document(lines) 
    if doc_type not in ALLOWED_DOC_TYPES:
        doc_type = "UNK"
    # Enforce business-allowed document types only
    if not policy_type or policy_type == "UNK":
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

    # --- Field requirements ---
    req = REQUIRED_FIELDS.get(doc_type, REQUIRED_FIELDS["UNK"])
    opt = OPTIONAL_FIELDS.get(doc_type, OPTIONAL_FIELDS["UNK"])

    def _r(approach, reason, **kw):
        return RoutingResult(
            approach=approach, doc_type=doc_type, policy_type=policy_type,
            required_fields=req, optional_fields=opt,
            carrier_hint=carrier, has_tables=has_tables,
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
            inner_req = REQUIRED_FIELDS.get(inner, REQUIRED_FIELDS.get("UNK", []))
            inner_opt = OPTIONAL_FIELDS.get(inner, OPTIONAL_FIELDS.get("UNK", []))
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
    # DOI + UNK/FIR/other → DTE  (table 3,4)
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
    # INV other → SC+TE           (table 2: INV HAZ, table 4: INV UNK)
    # Note: FPN (Force Placed Notice) removed from valid document types
    if doc_type == "INV":
        if has_tables:
            return _r(Approach.SC_TE_LATE,
                      "Invoice with tables → SC+TE + LATE")
        if is_simple and policy_type in ("HO6", "UNK"):
            return _r(Approach.LORH,
                      "Simple invoice → LORH")
        return _r(Approach.SC_TE,
                  "Standard invoice → SC+TE")

    # ─── RENEWALS / DECLARATIONS ────────────────────────────
    # RNW + WND → DTE  (table 5: wind renewal/change)
    # RNW + EDI → DTE  (table 5: RNW HO EDI)
    # RNW + HO/FIR/FLD/HAZ/HO6/DP3 → SARDE + LATE
    # RNW + UNK (landlord etc) → SARDE + LATE if tables, SARDE otherwise
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
        # Unknown policy with detected tables
        if has_tables:
            return _r(Approach.SARDE_LATE,
                      "Renewal with tables → SARDE + LATE")
        # Plain renewal, no tables
        return _r(Approach.SARDE,
                  "Simple renewal → SARDE")

    # ─── OTH / UNKNOWN ─────────────────────────────────────
    # OTH invoice-like → SC+TE  (table 4)
    if doc_type == "OTH":
        return _r(Approach.SC_TE,
                  "Unknown doc → SC+TE")

    # ─── VERY SIMPLE UNKNOWN → LORH ────────────────────────
    if is_simple:
        return _r(Approach.LORH, "Simple unknown → LORH")

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
    r"(?:policy\s*(?:number|no\.?|#))\s*[:\s]*"
    r"([A-Z0-9][\w\s\-]{4,25})",
    re.I,
)
_LOAN_LABEL_RE = re.compile(
    r"(?:loan\s*(?:number|no\.?|#|id))\s*[:\s]*"
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
    r"(?:mortgage(?:e)?\s*(?:company)?|lender|loss\s+payee)"
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

    # Insured name
    m = _NAME_LABEL_RE.search(text)
    if m:
        out["insured_name"] = _candidate(
            m.group(1).strip(), "dte_can_name", 0.93)

    # Cancellation / effective date — look for specific labels
    for line in lines:
        ll = line.lower()

        # Cancellation date
        if "effective_date" not in out:
            if any(k in ll for k in ("cancel effective", "cancellation date",
                                      "cancelled effective",
                                      "effective date of cancellation",
                                      "policy will be cancel")):
                d = _first_date(line)
                if d:
                    out["effective_date"] = _candidate(
                        d, "dte_can_cancel_date", 0.96)

        # Reason
        if "cancellation_reason" not in out:
            if any(k in ll for k in ("reason", "non-payment",
                                      "nonpayment", "borrower request",
                                      "insured request", "underwriting")):
                # Extract the reason text
                if ":" in line:
                    _, _, val = line.partition(":")
                    val = val.strip()
                    if val and len(val) > 3:
                        out["cancellation_reason"] = _candidate(
                            val, "dte_can_reason", 0.92)
                elif "non-payment" in ll or "nonpayment" in ll:
                    out["cancellation_reason"] = _candidate(
                        "Non-payment of premium", "dte_can_reason", 0.90)
                elif "borrower request" in ll:
                    out["cancellation_reason"] = _candidate(
                        "Borrower request", "dte_can_reason", 0.90)
                elif "insured request" in ll:
                    out["cancellation_reason"] = _candidate(
                        "Insured request", "dte_can_reason", 0.90)

    # Carrier
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_can_carrier", 0.90)

    # Mortgage company
    m = _MORTGAGE_LABEL_RE.search(text)
    if m:
        out["mortgage_company"] = _candidate(
            m.group(1).strip(), "dte_can_mortgage", 0.88)

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

    # Expiration date
    for line in lines:
        ll = line.lower()
        if "expiration_date" not in out:
            if any(k in ll for k in ("expiration", "expire", "will not renew",
                                      "policy end", "coverage end")):
                d = _first_date(line)
                if d:
                    out["expiration_date"] = _candidate(
                        d, "dte_nrnw_expiration", 0.95)

    # Effective date (sometimes present as "non-renewal effective")
    for line in lines:
        ll = line.lower()
        if "effective_date" not in out:
            if any(k in ll for k in ("effective date", "policy period")):
                d = _first_date(line)
                if d:
                    out["effective_date"] = _candidate(
                        d, "dte_nrnw_effective", 0.90)

    # Carrier
    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_nrnw_carrier", 0.90)

    return out


# ============================================================
# DTE: DELETION OF INTEREST TEMPLATE
# ============================================================

def _dte_doi(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for DOI documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)

    # Policy number
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), "dte_doi_policy", 0.95)

    # Mortgage company
    m = _MORTGAGE_LABEL_RE.search(text)
    if m:
        out["mortgage_company"] = _candidate(
            m.group(1).strip(), "dte_doi_mortgage", 0.93)

    # Loan number
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

    return out


# ============================================================
# DTE: EDI IMAGE TEMPLATE
# ============================================================

def _dte_edi(lines: List[str]) -> Dict[str, Dict]:
    """Template extraction for EDI image documents."""
    out: Dict[str, Dict] = {}
    text = "\n".join(lines)

    # EDI images are very structured — field labels are predictable
    m = _POLICY_LABEL_RE.search(text)
    if m:
        out["policy_number"] = _candidate(
            m.group(1).strip(), "dte_edi_policy", 0.94)

    m = _NAME_LABEL_RE.search(text)
    if m:
        out["insured_name"] = _candidate(
            m.group(1).strip(), "dte_edi_name", 0.92)

    # Dates — scan all lines
    dates_found = []
    for line in lines:
        ll = line.lower()
        d = _first_date(line)
        if d:
            if any(k in ll for k in ("effective", "begin", "start")):
                out["effective_date"] = _candidate(d, "dte_edi_eff", 0.93)
            elif any(k in ll for k in ("expir", "end", "term")):
                out["expiration_date"] = _candidate(d, "dte_edi_exp", 0.93)
            else:
                dates_found.append(d)

    # If we found exactly 2 unlabeled dates, assume effective then expiration
    if "effective_date" not in out and "expiration_date" not in out:
        if len(dates_found) >= 2:
            out["effective_date"] = _candidate(
                dates_found[0], "dte_edi_eff_infer", 0.85)
            out["expiration_date"] = _candidate(
                dates_found[1], "dte_edi_exp_infer", 0.85)

    m = _CARRIER_LABEL_RE.search(text)
    if m:
        out["carrier_name"] = _candidate(
            m.group(1).strip().upper(), "dte_edi_carrier", 0.90)

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
        # REMOVED: "EDI" - EDI is a format indicator, not a document type
    }

    extractor = dispatch.get(doc_type)
    if extractor:
        return extractor(lines)

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
                                         "policy #", "policy num")):
                v = value.replace(" ", "")
                if len(v) >= 6:
                    out["policy_number"] = _candidate(
                        v, "lorh_policy", 0.92)

    # --- Insured Name ---
    for label, value in kv_pairs:
        if "insured_name" not in out:
            if any(k in label for k in ("insured", "policyholder",
                                         "name")):
                if not any(k in label for k in ("mortgagee", "company",
                                                 "agent", "loss payee")):
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

    # --- Carrier (scan first 15 lines for "insurance" + company type) ---
    if "carrier_name" not in out:
        for line in lines[:15]:
            ll = line.lower()
            if "insurance" in ll and any(
                w in ll for w in ("company", "co", "exchange", "group",
                                   "mutual", "corp")):
                if not any(w in ll for w in ("agency", "agent", "services")):
                    out["carrier_name"] = _candidate(
                        line.strip().upper(), "lorh_carrier", 0.85)
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

    return out