"""
Policy Type Classification - FINAL FIX
FIR guard added to prevent HO override
"""
import re
from typing import List

def classify_policy(lines: List[str]) -> str:
    """
    Classify insurance policy type.
    Returns: BREQ, NPAY, NRNW, UNWR, CEL,
             AUTO, ERQ, FIR, FLD, HAZ, HO6, LL, HO, UO, WND, UNK

    For CAN/DOI docs, the cancellation REASON (BREQ/NPAY/NRNW/UNWR/CEL)
    takes priority over coverage type (FLD/HO/etc).
    """

    text = " ".join(lines).lower()

    # ==========================================================
    # 0. CANCELLATION SUB-TYPES — checked FIRST
    # For CAN docs, the reason WHY it was cancelled is more
    # important than WHAT was insured (flood/home/etc).
    # Priority: BREQ > NPAY > NRNW > UNWR > CEL
    # ==========================================================

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
    if any(k in text for k in (
        "underwriting",
        "underwriting guidelines",
        "building has been sold",
        "building has been sold, removed",
        "property has been sold",
        "no longer meets the definition",
        "company request",
        "company decision",
        "does not meet underwriting",
        "risk does not meet",
    )):
        return "UNWR"

    # CEL — Generic Cancellation (CAN doc without specific reason)
    # Guard: skip if DOI signals present (cancellation date in DOI = interest end date)
    is_doi_context = any(k in text for k in (
        "no longer have an interest",
        "loan has been satisfied",
        "interest removed",
        "interest has been removed",
        "deletion of interest",
    ))
    if not is_doi_context and any(k in text for k in (
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
        )):
            return "FLD"

    # ==========================================================
    # 2. FIRE / DWELLING FIRE (DOMINANT — check BEFORE HO)
    # "dwelling fire", "dp3", "dp-3" are STRONG FIR signals.
    # HO docs say "coverage a dwelling" but NOT "dwelling fire".
    # ==========================================================
    fir_signals = any(k in text for k in (
        "dwelling fire",
        "dp-1",
        "dp-3",
        "dp3",
        "dp 3",
        "fire policy",
        "fire dwelling",
        "insured under peril fire",
        "insured under perils fire",
        "coverage type: dwelling fire",
        "dwelling fire policy",
        # EDI format patterns
        "dfire",
        "dfire-s11",
        "cov type - dwelling fire",
        "cov type dwelling fire",
        "covtype dwelling fire",
        "coverage type dwelling fire",
    )) or bool(re.search(r"dfire[\s\-]*s11", text)) or bool(
        re.search(r"cov\s*type.*dwelling\s*fire", text)
    )
    if fir_signals:
        # FIR ALWAYS wins when explicit dwelling fire keywords present.
        # "coverage a" in a dwelling fire doc does NOT make it HO.
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
        r"geico|hartford|erie|travelers|american family|auto.owners)"
        r".*\bvehicle\b.*\b(property|insurance|company)\b", text))

    auto_match = any(re.search(p, text) for p in auto_patterns)
    if not auto_match and has_vehicle and not vehicle_in_carrier:
        auto_match = True

    if auto_match and not any(
        k in text for k in (
            "coverage a",
            "dwelling",
            "home protection",
            "residence premises",
            "homeowners",
            "house & home",
            "house and home",
        )
    ):
        return "AUTO"

    # ==========================================================
    # 4. EARTHQUAKE (STANDALONE)
    # ==========================================================
    if any(k in text for k in (
        "california earthquake authority",
        "earthquake policy",
        "earthquake",
    )) and not any(
        k in text for k in (
            "coverage a",
            "home protection",
            "dwelling",
        )
    ):
        return "ERQ"

    # ==========================================================
    # 5. WIND (STANDALONE ONLY — not wind deductible in HO)
    # ==========================================================
    if any(w in text for w in (
        "wind only",
        "wind-only policy",
        "windstorm policy",
        "hurricane only",
        "wind and hail only",
    )) and not any(h in text for h in (
        "coverage a",
        "coverage b",
        "home protection",
        "policy declarations",
        "residence premises",
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
        "lessor",
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
    ]
    ho_score = sum(1 for m in ho_markers if m in text)
    if ho_score >= 3:
        return "HO"

    # If only 1-2 HO markers but "dwelling" present → still could be HO
    if ho_score >= 1 and "dwelling" in text and "dwelling fire" not in text:
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