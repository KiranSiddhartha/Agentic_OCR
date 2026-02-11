"""
Document Router — Classification, Routing, DTE & LORH Extraction
=================================================================
This file contains THREE concerns that belong together because they
are all driven by document type:

  1. ROUTING   — classify doc → select ONE primary approach
  2. DTE       — Direct Template Extraction (for CAN, NRNW, DOI, EDI)
  3. LORH      — Lightweight OCR Result Heuristic (for trivial docs)

Routing Table:
┌─────────────────────┬──────────────────────────────────────────────────────┐
│ Approach            │ Best Suited Document Types                          │
├─────────────────────┼──────────────────────────────────────────────────────┤
│ SARDE               │ Renewals, policy changes, amended declarations      │
│ SARDE + LATE        │ Renewals w/ coverage/premium tables (HO,FIR,FLD…)   │
│ SC → SARDE → LATE   │ Fax (PQ) packets, mixed multi-document files        │
│ DTE                 │ Cancellations, non-renewals, interest removals, EDI │
│ SC+TE → DTE         │ Borrower requests, third-party notices, certs       │
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
    "NRNW": ["policy_number", "insured_name", "expiration_date"],
    "DOI":  ["policy_number", "mortgage_company", "loan_number"],
    "COI":  ["carrier_name", "policy_number", "insured_name",
             "effective_date", "expiration_date"],
    "RNS":  ["policy_number", "insured_name", "effective_date"],
    "FPN":  ["policy_number", "insured_name"],
    "BIN":  ["carrier_name", "policy_number", "insured_name",
             "effective_date"],
    "EDI":  ["policy_number", "insured_name"],
    "PQ":   ["policy_number", "insured_name"],
    "BRQ":  ["policy_number", "insured_name"],
    "TPN":  ["policy_number", "insured_name"],
    "OTH":  ["policy_number"],
    "UNK":  ["policy_number"],
}

OPTIONAL_FIELDS: Dict[str, List[str]] = {
    "RNW":  ["property_address", "mailing_address", "mortgage_company",
             "loan_number", "total_premium", "agent_name", "agent_phone"],
    "INV":  ["carrier_name", "effective_date", "total_premium",
             "mortgage_company", "loan_number"],
    "CAN":  ["carrier_name", "mortgage_company", "property_address"],
    "NRNW": ["carrier_name", "effective_date", "mortgage_company"],
    "DOI":  ["carrier_name", "insured_name", "property_address"],
    "COI":  ["property_address", "mortgage_company"],
    "RNS":  ["carrier_name", "expiration_date"],
    "FPN":  ["carrier_name", "effective_date", "property_address"],
    "BIN":  ["expiration_date", "property_address"],
    "EDI":  ["carrier_name", "effective_date", "expiration_date"],
    "PQ":   ["carrier_name", "effective_date", "expiration_date",
             "property_address"],
    "BRQ":  ["carrier_name", "mortgage_company", "loan_number"],
    "TPN":  ["carrier_name", "mortgage_company"],
    "OTH":  ["insured_name", "carrier_name"],
    "UNK":  ["insured_name", "carrier_name"],
}

# Policy types with coverage/premium tables → triggers + LATE
TABLE_POLICY_TYPES = {"HO", "HO3", "HO6", "FIR", "FLD", "HAZ", "DP3", "WND"}


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
                                "third party interest removed")) or bool(
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
    if "borrower request" in text or "customer initiated" in text:
        return "CAN"
    if "third party notice" in text:
        return "CAN"
    
    # EDI images
    if any(k in text for k in ("edi image", "electronic data",
                                "electronic image generated for edi",
                                "electronic image generated",
                                "generated for edi", "edi data")):
        return "EDI"
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
    Used as primary classifier or fallback when embedding classifier
    returns UNK.  Order matters — specific patterns checked first.
    """
    if not lines:
        return "UNK"

    head = " ".join(lines[:50]).lower()
    full = " ".join(lines).lower()

    # ---- Deletion of interest (check BEFORE cancellation) ----
    if any(k in full for k in ("deletion of interest", "interest removal",
                                "interest deleted", "remove interest",
                                "interest removed", "mortgagee interest removed",
                                "mir-mortgagee interest removed",
                                "mir mortgagee interest removed",
                                "third party interest removed")) or bool(
        re.search(r"mir[\s\-]*mortgagee\s+interest\s+removed", full)
    ) or bool(re.search(r"cancel\s*reason[:\s]*mir", full)):
        return "DOI"

    # ---- Cancellation ----
    if any(k in full for k in ("notice of cancellation", "cancellation notice",
                                "policy cancelled", "will be cancelled",
                                "cancel effective", "is hereby cancelled",
                                "cancellation date",
                                "reason cancellation", "doc type - cancellation",
                                "doc type cancellation",
                                "cancellation customer initiated",
                                "reason: cancellation")):
        return "CAN"

    # ---- Non-renewal ----
    if any(k in head for k in ("non-renewal", "nonrenewal",
                                "will not be renewed",
                                "notice of non renewal")):
        return "NRNW"

    # ---- Borrower request (cancellation sub-type) ----
    if any(k in head for k in ("borrower request", "borrower cancel",
                                "borrower-requested")):
        return "BRQ"

    # ---- Third-party notice ----
    if any(k in head for k in ("third party notice", "third-party notice",
                                "third party notification")):
        return "TPN"

    # ---- Invoice / billing ----
    if any(k in head for k in ("invoice", "billing statement",
                                "amount due", "balance due",
                                "payment due", "remit to",
                                "please pay", "minimum due")):
        return "INV"

    # ---- Certificate of insurance ----
    if any(k in head for k in ("certificate of insurance",
                                "certificate holder",
                                "acord 25", "acord 28")):
        return "COI"

    # ---- Reinstatement ----
    if any(k in head for k in ("reinstatement", "reinstated",
                                "rescission of cancellation")):
        return "RNS"

    # ---- Force-placed / final payment ----
    if any(k in head for k in ("force placed", "force-placed",
                                "lender-placed", "final notice",
                                "final payment")):
        return "FPN"

    # ---- Binder ----
    if any(k in head for k in ("binder", "evidence of coverage",
                                "bound coverage")):
        return "BIN"

    # ---- EDI image ----
    if any(k in full for k in ("edi image", "electronic data",
                                "edi transaction",
                                "electronic image generated for edi",
                                "electronic image generated",
                                "generated for edi",
                                "edi data")):
        # Check if it's actually a DOI wrapped in EDI format
        if any(k in full for k in ("interest removed", "mir-mortgagee",
                                    "mir mortgagee", "cancel reason mir",
                                    "mortgagee interest removed")) or bool(
            re.search(r"mir[\s\-]*mortgagee", full)):
            return "DOI"
        return "EDI"
    
    # ---- LexisNexis insurance coverage notification ----
    if "insurance coverage notification" in full:
        if "cancellation" in full:
            return "CAN"
        if any(k in full for k in ("interest removed", "mir")):
            return "DOI"
        return "EDI"

    # ---- Fax / packet ----
    if _detect_fax_packet(lines):
        return "PQ"

    # ---- Renewal / Declarations (broadest — checked last) ----
    if any(k in head for k in ("renewal", "declarations", "policy period",
                                "your policy", "homeowner",
                                "dwelling fire", "amended declarations",
                                "coverage summary")):
        return "RNW"

    # ---- Full-text fallback for renewals ----
    if any(k in full for k in ("coverage a", "coverage b",
                                "dwelling coverage", "annual premium",
                                "renewal flood insurance",
                                "flood insurance policy declarations",
                                "agent issued declarations",
                                "policy premium",
                                "total policy premium")):
        return "RNW"

    return "UNK"


def classify_policy_type(lines: List[str]) -> str:
    """Rule-based policy-type classification."""
    if not lines:
        return "UNK"
    text = " ".join(lines[:60]).lower()
    full = " ".join(lines).lower()

    if any(k in full for k in ("flood", "nfip", "fema")):
        return "FLD"
    if any(k in full for k in ("wind only", "hurricane")):
        return "WND"
    if any(k in full for k in ("dwelling fire", "dp-3", "dp3", "dp-1",
                                "dfire", "dfire-s11",
                                "cov type - dwelling fire",
                                "cov type dwelling fire")):
        return "FIR"
    if any(k in text for k in ("hazard", " haz ")):
        return "HAZ"
    if any(k in text for k in ("ho-6", "ho6", "condominium")):
        return "HO6"
    if "dp3" in text or "dp-3" in text:
        return "DP3"
    if any(k in full for k in ("homeowner", "ho-3", "ho3", "home protection",
                                "homeowners pol", "homeowner pol")):
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
        doc_type = classify_doc_type(lines)
    if not policy_type or policy_type == "UNK":
        policy_type = classify_policy_type(lines)

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
    if doc_type == "PQ" or is_fax:
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
        # COI/TPN inside PQ → SC+TE → DTE
        if inner in ("COI", "TPN"):
            inner_req = REQUIRED_FIELDS.get(inner, REQUIRED_FIELDS["PQ"])
            inner_opt = OPTIONAL_FIELDS.get(inner, OPTIONAL_FIELDS["PQ"])
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

    # ─── EDI ────────────────────────────────────────────────
    if doc_type == "EDI":
        return _r(Approach.DTE, "EDI → DTE")

    # ─── SEMI-TEMPLATE DOCS ────────────────────────────────
    # TPN, COI, RNS, BIN → SC+TE → DTE
    if doc_type in ("TPN", "COI", "RNS", "BIN"):
        return _r(Approach.SC_TE_DTE,
                  f"Semi-template ({doc_type}) → SC+TE → DTE")

    # ─── INVOICES ───────────────────────────────────────────
    # INV + tables → SC+TE + LATE  (table 2: INV HO, INV LL)
    # INV + HO6 + simple → LORH   (table 2: INV HO6)
    # INV other → SC+TE           (table 2: INV HAZ, table 4: INV UNK)
    if doc_type in ("INV", "FPN"):
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
        "NRNW": _dte_nonrenewal,
        "DOI":  _dte_doi,
        "EDI":  _dte_edi,
    }

    extractor = dispatch.get(doc_type)
    if extractor:
        return extractor(lines)

    # Generic fallback for BRQ, TPN, COI, RNS, BIN, etc.
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