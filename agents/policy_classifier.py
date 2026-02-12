"""
Policy Type Classifier - CLEAN ARCHITECTURE VERSION
Returns coverage types AND cancellation subtypes.

Coverage types: AUTO, ERQ, FIR, FLD, HAZ, HO, HO6, LL, UO, WND
Cancellation subtypes: BREQ, NPAY, NRNW, UNWR, CEL

For CAN documents, cancellation subtypes (BREQ/NPAY/NRNW/UNWR/CEL) take
priority over coverage types, as the REASON for cancellation is more
important business logic than the coverage type.
"""
import re
from typing import List

def classify_policy(lines: List[str]) -> str:
    """
    Classify insurance policy type (coverage OR cancellation subtype).
    
    Returns COVERAGE TYPES:
        AUTO, ERQ, FIR, FLD, HAZ, HO, HO6, LL, UO, WND, UNK
    
    Returns CANCELLATION SUBTYPES (reasons for CAN/DOI docs):
        BREQ - Borrower Request / Customer Initiated
        NPAY - Non-Payment of Premium
        NRNW - Non-Renewal
        UNWR - Underwriting / Company Decision
        CEL  - Generic Cancellation (no specific reason)
    
    Priority Logic:
    For CAN/DOI docs, the cancellation REASON (BREQ/NPAY/NRNW/UNWR/CEL)
    takes priority over coverage type (FLD/HO/etc), as the reason WHY
    it was cancelled is more important than WHAT was insured.
    
    This allows proper segregation:
    - document_type = CAN (structure)
    - policy_type = BREQ (reason) or FLD (coverage)
    """

    text = " ".join(lines).lower()

    # ==========================================================
    # DOI GUARD: If DOI signals are present, skip cancellation 
    # subtypes and go directly to coverage type detection.
    # For DOI docs, the coverage type (FIR/HO/HAZ) is more 
    # important than the cancellation reason (BREQ/CEL).
    # ==========================================================
    is_doi_context = any(k in text for k in (
        "no longer have an interest",
        "loan has been satisfied",
        "interest removed",
        "interest has been removed",
        "deletion of interest",
        "mortgagee interest removed",
        "mir-mortgagee interest removed",
        "mir mortgagee interest removed",
        "removed all indications of your interest",
        "interest terminated",
        "terminate the interest of the third party",
        "terminate the interest",
    )) or bool(re.search(r"mir[\s\-]*mortgagee\s+interest\s+removed", text))

    # ==========================================================
    # RENEWAL/DECLARATION GUARD: If strong renewal/declaration 
    # signals are present, skip cancellation subtypes.
    # Words like "underwriting" in "Rating/Underwriting Information"
    # are section headers in declarations, not cancellation reasons.
    # ==========================================================
    is_renewal_context = any(k in text for k in (
        "policy declarations",
        "declarations summary",
        "mortgagee declarations",
        "policy change summary",
        "transaction: renewal",
        "transaction desc: renewal",
        "agent issued declarations",
        "amended declarations",
        "amended policy information",
        "renewal notice",
        "policy renewal",
        "landlord protection policy declarations",
        "wind only policy - declarations",
        "homeowners hw-",
    ))

    # ==========================================================
    # 0. CANCELLATION SUB-TYPES — checked FIRST 
    # (but NOT for DOI or RENEWAL contexts)
    # For CAN docs, the reason WHY it was cancelled is more
    # important than WHAT was insured (flood/home/etc).
    # Priority: BREQ > NPAY > NRNW > UNWR > CEL
    # ==========================================================

    if not is_doi_context and not is_renewal_context:

        # BREQ — Borrower Request / Insured-initiated cancellation
        if "third party notice of termination" in text:
            has_policy_terminate = bool(re.search(
                r"terminate this policy effective[:\s]*\d", text))
            if has_policy_terminate:
                return "BREQ"

        if any(k in text for k in (
            "insured - non pay",
            "insured non pay",
            "insured - nonpay",
            "insured request",
            "borrower request",
            "customer request",
            "customer initiated",
            "cancellation customer initiated",
            "reason cancellation customer",
            "at the request of the insured",
            "requested by the insured",
            "requested by insured",
            # LexisNexis / EDI cancellation reason patterns
            "reason cancellation customer initiated",
            "reason: customer initiated",
            "cancel reason: customer",
            "cancel reason customer",
        )):
            return "BREQ"
        
        # Additional BREQ: LexisNexis notification with cancellation context
        # If "insurance coverage notification" + "cancellation" + no other 
        # specific reason → check if customer/borrower initiated
        if "insurance coverage notification" in text and "cancellation" in text:
            # If we see cancellation in a LexisNexis notification but no specific
            # sub-reason was detected above, default to BREQ (most common for 
            # LexisNexis notifications to insurance tracking)
            if not any(k in text for k in (
                "non-payment", "nonpayment", "failure to pay",
                "non-renewal", "nonrenewal",
                "underwriting", "company request",
            )):
                return "BREQ"
        
        # NPAY — Non-Payment of Premium
        if any(k in text for k in (
            "premium payment has not been received",
            "non-payment of premium",
            "nonpayment of premium",
            "failure to pay premium",
            "premium not paid",
            "premium has not been paid",
            "payment is not received on or before",
        )):
            return "NPAY"

        # NRNW — Non-Renewal
        if any(k in text for k in (
            "non-renewal",
            "nonrenewal",
            "will be non-renewed",
            "will not be renewed",
            "notice of non-renewal",
        )):
            return "NRNW"

        # UNWR — Underwriting (carrier decision to cancel)
        # Guard: "underwriting" alone is too broad (matches "Rating/Underwriting Information"
        # headers in declarations). Require stronger patterns or cancellation context.
        unwr_strong = any(k in text for k in (
            "underwriting guidelines",
            "building has been sold",
            "building has been sold, removed",
            "property has been sold",
            "no longer meets the definition",
            "company request",
            "company decision",
            "does not meet underwriting",
            "risk does not meet",
        ))
        # "underwriting" alone only triggers UNWR if cancellation context is also present
        unwr_with_cancel = (
            "underwriting" in text 
            and any(k in text for k in (
                "cancellation", "cancelled", "cancel", 
                "terminated", "non-renewal",
            ))
            and "rating/underwriting" not in text
            and "underwriting information" not in text
        )
        if unwr_strong or unwr_with_cancel:
            return "UNWR"

        # CEL — Generic Cancellation (CAN doc without specific reason)
        if any(k in text for k in (
            "cancellation notice",
            "notice of cancellation",
            "policy cancellation",
            "flood policy cancellation",
            "will be cancelled",
            "has been cancelled",
            "is being cancelled",
            "cancelled effective",
            "cancellation effective",
            "cancellation date",
        )):
            return "CEL"

    # ==========================================================
    # 1. FLOOD (DOMINANT — standalone policy)
    # ==========================================================
    if any(k in text for k in (
        "flood policy",
        "flood insurance",
        "nfip",
        "fema",
        "flood zone",
        "flood service center",
        "standard flood insurance",
    )):
        if not any(excl in text for excl in (
            "does not have coverage for the peril of flood",
            "flood is excluded",
            "flood coverage is not provided",
            "does not include coverage for damage resulting from flood",
            "does not include coverage for flood",
            "not include flood",
            "flood insurance coverage, you may have",
            "purchase of flood insurance",
            "purchase separate flood",
            "consider the purchase of flood",
            "need to purchase flood",
        )):
            return "FLD"
        # If flood is mentioned only in disclaimers/warnings, it's NOT a flood policy
        # Check if there's a POSITIVE flood policy indicator beyond disclaimers
        flood_positive = any(k in text for k in (
            "flood policy number",
            "flood insurance policy declarations",
            "national flood insurance",
            "flood insurance declarations",
            "flood zone determination",
        ))
        if flood_positive:
            return "FLD"

    # ==========================================================
    # FIRE / DWELLING FIRE (STRICT DETECTION)
    # Must indicate actual policy type, not endorsement wording.
    # ==========================================================

    fir_strong = any(k in text for k in (
        "dwelling fire policy",
        "policy type: dwelling fire",
        "coverage type: dwelling fire",
        "coverage type dwelling fire",
        "cov type - dwelling fire",
        "cov type dwelling fire",
        "covtype - dwelling fire",
        "covtype dwelling fire",
    ))
    
    # "dwelling fire" as standalone policy indicator — but NOT in endorsement/form titles
    # or coverage peril entries within other policy types (landlord, HO)
    # Guard: "dwelling fire provisions" = form title, not policy type
    # Guard: "A DWELLING FIRE $..." = peril type in coverage table, not policy type
    if not fir_strong and "dwelling fire" in text:
        dfire_in_endorsement = any(k in text for k in (
            "dwelling fire provisions",
            "dwelling fire endorsement",
            "amendment of home and dwelling fire",
            "amendment of dwelling fire",
        ))
        # "dwelling fire" as a peril in a coverage table (e.g., "A DWELLING FIRE $308,800")
        # This appears in landlord/HO policies where FIRE is a peril, not the policy type
        dfire_as_peril = any(k in text for k in (
            "landlord",
            "landlord protection",
            "occupancy: tenant",
            "loss of rent",
            "rental value",
        )) or bool(re.search(r"a\s+dwelling\s+fire\s+[\$\d]", text))
        if not dfire_in_endorsement and not dfire_as_peril:
            fir_strong = True
    
    # DFIRE / DFIR patterns — must be word-boundary to avoid matching "wildfire"
    fir_dfire = bool(re.search(r"\bdfire\b", text)) or bool(re.search(r"\bdfir\b", text))
    fir_dfire_s11 = "dfire-s11" in text

    # Strict DP form detection (standalone form reference)
    fir_dp_form = bool(re.search(r"\bdp[-\s]?(1|2|3)\b", text))

    # Explicit cov type format
    fir_covtype = bool(
        re.search(r"cov\s*type\s*[:\-]?\s*dwelling\s*fire", text)
    )

    if fir_strong or fir_dfire or fir_dfire_s11 or fir_dp_form or fir_covtype:
        return "FIR"


    # ==========================================================
    # 3. AUTO (STRICT — standalone)
    # Guard: "vehicle" in carrier names like "Allstate Vehicle and
    # Property Insurance Company" must NOT trigger AUTO.
    # ==========================================================
    auto_patterns = [
        r"\bvin\b",
        r"\bautomobile\b",
        r"\bmotor vehicle\b",
    ]
    # "vehicle" needs extra context — only match if NOT in a carrier name
    has_vehicle = bool(re.search(r"\bvehicle\b", text))
    vehicle_in_carrier = bool(re.search(
        r"(allstate|nationwide|state farm|farmers|liberty|usaa|progressive|"
        r"geico|travelers|hartford|safeco|mercury).*"
        r"(vehicle|property).*insurance",
        text,
    ))
    if has_vehicle and not vehicle_in_carrier:
        return "AUTO"
    if any(re.search(p, text) for p in auto_patterns):
        return "AUTO"

    # ==========================================================
    # 4. ERQ / EARTHQUAKE (STANDALONE)
    # ==========================================================
    if any(k in text for k in (
        "earthquake",
        "erq",
        "eq policy",
        "earthquake insurance",
    )):
        # Guard: "does not provide earthquake" / "earthquake is excluded" = disclaimer
        erq_excluded = any(k in text for k in (
            "does not provide earthquake",
            "not provide earthquake coverage",
            "earthquake is excluded",
            "earthquake coverage is not",
            "no earthquake coverage",
            "earthquake is not covered",
            "does not include earthquake",
        ))
        if not erq_excluded:
            return "ERQ"

    # ==========================================================
    # 5. WINDSTORM / WIND (BEFORE HO, highly specific)
    # Can be standalone or part of HO. Standalone WND takes priority.
    # ==========================================================
    if any(k in text for k in (
        "wind-only policy",
        "wind-only coverage",
        "wind only policy",
        "wind only coverage",
        "standalone wind policy",
        "policy type: wind",
        "windstorm insurance policy",
        "hw-2 wind only",
        "hw2 wind only",
        "wind only",
    )):
        return "WND"

    # ==========================================================
    # 6. HO6 / CONDO (before HO — more specific)
    # ==========================================================
    if any(k in text for k in (
        "condominium",
        "condo unit",
        "unit owner",
        "ho6",
        "ho-6",
        "co-op",
        "town house",
        "town home",
    )):
        return "HO6"

    # ==========================================================
    # 7. UNIT OWNER (UO) — COI context
    # ==========================================================
    if "certificate of insurance" in text and any(k in text for k in (
        "unit owner",
        "master policy",
    )):
        return "UO"

    # ==========================================================
    # 8. LANDLORD (LL)
    # ==========================================================
    if any(k in text for k in (
        "rental dwelling",
        "rental property",
        "landlord",
        "landlord protection",
        "lessor",
        "occupancy: tenant",
        "loss of rent, rental value",
        "loss of rent",
    )):
        return "LL"

    # ==========================================================
    # 9. HAZ / COMMERCIAL — check BEFORE HO
    # HAZ is for commercial/non-residential property with
    # property-specific language but NO residential coverage letters.
    # ==========================================================
    haz_signals = any(k in text for k in (
        "property protection",
        "commercial property",
        "commercial property coverage",
        "medical office",
        "office occupancy",
        "blanket coverage",
        "property insured",
        "amount of insurance",
        "property deductible",
        "buildings - replacement cost",
    ))
    if haz_signals:
        # HAZ wins if NO strong residential signals
        # Use \b word boundaries to avoid false matches like
        # "coverage buildings" matching "coverage b"
        residential_patterns = [
            r"\bcoverage a\b",
            r"\bcoverage b\b",
            r"\bcoverage c\b",
            r"\bcoverage e\b",
            r"\bcoverage f\b",
            r"\bpersonal liability\b",
            r"\bmedical payments\b",
            r"\bresidence premises\b",
            r"\bhomeowners\b",
            r"\bhome protection\b",
        ]
        if not any(re.search(p, text) for p in residential_patterns):
            return "HAZ"

    # ==========================================================
    # 10. HOMEOWNERS (HO) — needs STRONG residential signals
    # Requires 3+ of: coverage a-f, dwelling, personal liability,
    # home protection, policy declarations, residence premises, etc.
    # ==========================================================
    ho_markers = [
        "coverage a",
        "coverage b",
        "coverage c",
        "coverage d",
        "coverage e",
        "coverage f",
        "personal liability",
        "home protection",
        "policy declarations",
        "residence premises",
        "property location limit",
        "pll",
        "estimated residence value",
        "other structures",
        "loss of use",
        "medical payments",
        "homeowners",
        "homeowners pol",
        "homeowner pol",
        "limit of liability",
        "forms & endorsements",
        "forms and endorsements",
        "dwelling amount",
        "dwelling limit",
        "deductible",
    ]
    ho_score = sum(1 for m in ho_markers if m in text)
    if ho_score >= 3:
        return "HO"

    # If only 1-2 HO markers but "dwelling" present → still could be HO
    if ho_score >= 1 and "dwelling" in text and "dwelling fire" not in text:
        return "HO"
    
    # Also check: "dwell" without "fire" in context of homeowners
    if ho_score >= 1 and "dwell " in text and "dwelling fire" not in text and "dfire" not in text:
        return "HO"

    # (Cancellation sub-types moved to step 0 at top)

    # ==========================================================
    # 12. "House & Home" → HAZ (Allstate policy type label)
    # ==========================================================
    if any(k in text for k in (
        "house & home",
        "house and home",
        "policy type: house",
    )):
        return "HAZ"

    # ==========================================================
    # 13. "Homeowners Policy" standalone → HO
    # For docs that mention "homeowners policy" but lack coverage details
    # ==========================================================
    if any(k in text for k in (
        "homeowners policy",
        "homeowner policy",
        "homeowner's policy",
    )):
        return "HO"

    # ==========================================================
    # 14. MOBILEHOME → HO (per table: HO includes Mobile Home)
    # ==========================================================
    if any(k in text for k in (
        "mobile home",
        "mobilehome",
        "manufactured home",
    )):
        return "HO"

    # ==========================================================
    # DEFAULT
    # ==========================================================
    return "UNK"

# =========================================================
# CANCELLATION REASON (UNCHANGED)
# =========================================================
CANCELLATION_REASONS = {
    "borrower_request": [
        "customer request",
        "borrower request",
        "insured request",
        "insured name request",
        "agent request",
        "property sold"
    ],
    "cancellation": [
        "cancellation of interest",
        "reason not given for the cancellation"
    ],
    "non_payment": [
        "insured amount not paid",
        "premium amount not paid",
        "non-payment of premium",
        "non-payment"
    ],
    "non_renewal": [
        "cancellation of non-renewal",
        "non-renewal the policy",
        "non-renewal"
    ],
    "underwriting": [
        "underwriting guidelines",
        "insured/borrower moved",
        "company request",
        "no longer required by lender",
        "property sold"
    ]
}


def classify_cancellation_reason(lines):
    text = " ".join(lines).lower()
    for reason_type, keywords in CANCELLATION_REASONS.items():
        for keyword in keywords:
            if keyword in text:
                return reason_type
    return "unknown"


def get_policy_explanation(policy_type: str) -> str:
    """Business explanation for policy type"""
    explanations = {
        "AUTO": "Auto policy provides financial protection for losses related to a vehicle.",
        "ERQ": "Earthquake insurance pays the policyholder in the event of an earthquake that causes damage to the property.",
        "FIR": "Fire policy provides financial protection against losses and damages caused by fire.",
        "FLD": "Flood insurance denotes the specific insurance coverage against property loss from flooding.",
        "HAZ": "Dwelling fire policies offer property owners protection against hazards like explosions, vandalism and weather occurrences.",
        "HO6": "HO6 insurance policy is homeowners insurance for those who own a condominium or co-op unit.",
        "LL": "Landlord policy is designed to protect landlords from financial losses related to their rental properties.",
        "HO": "Homeowners insurance covers the home's structure, fixtures and contents from risks such as hail, wind, storm or fire.",
        "UO": "Unit owner policy covers the individual unit owner's responsibilities and belongings within their unit.",
        "WND": "Windstorm insurance covers damages caused by high winds, tornadoes, hail and other weather events.",
        "NRNW": "Non-renewal indicates the insurance company has chosen not to renew the policy at the end of its term.",
        "NPAY": "Non-payment cancellation occurs when premium payment has not been received by the due date.",
        "BREQ": "Borrower request cancellation occurs when the insured/borrower requests or triggers termination of the policy.",
        "CEL": "Generic cancellation where the specific reason for policy termination is not categorized.",
        "UNWR": "Underwriting cancellation occurs when the carrier cancels due to underwriting guidelines, property changes, or risk assessment.",
        "UNK": "If policy-related information is not available in the document it will be considered as Unknown."
    }
    return explanations.get(policy_type, "Unknown policy type")