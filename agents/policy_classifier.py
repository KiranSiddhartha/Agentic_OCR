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
    # DOI context detection — but NOT if there's also a policy termination signal.
    # A Third Party Notice of Termination that terminates BOTH the policy AND
    # the third party interest is a BREQ (borrower request), not a DOI.
    _has_policy_termination = bool(re.search(
        r"terminate this policy effective[:\s]*\d", text
    )) or any(k in text for k in (
        "policy cancelled",
        "policy has been cancelled",
        "policy is cancelled",
        "policy will be cancelled",
    ))

    is_doi_context = (
        any(k in text for k in (
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
    ) and not _has_policy_termination  # Policy termination overrides DOI context

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
        "policy change declarations",
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
        "homesaver policy",
        # Mortgagee certificates with coverage details are declarations, not cancellations
        "mortgagee certificate",
    ))

    # Additional renewal context: documents with strong coverage structure
    # (Coverage A-F with dollar amounts) that also contain boilerplate
    # cancellation/non-renewal language in mortgagee clauses.
    # The boilerplate phrases like "if the policy is cancelled or not renewed"
    # and "notice of cancellation we give our insured" are standard mortgagee 
    # clause language and do NOT indicate actual cancellation.
    if not is_renewal_context:
        has_coverage_structure = (
            sum(1 for cov in ("coverage a", "coverage b", "coverage c", 
                              "coverage d", "coverage e", "coverage f",
                              "a.dwelling", "b.other structures", 
                              "c.personal property", "d.loss of use",
                              "e.personal liability", "f.medical payments")
                if cov in text) >= 3
        )
        # Boilerplate cancellation: appears in mortgagee clauses, not as actual notice
        has_boilerplate_cancel = any(k in text for k in (
            "if the policy is cancelled or not renewed",
            "notice of cancellation we give our insured",
            "advance notice of cancellation",
            "same advance notice of cancellation",
            "the mortgagee will be notified at least",
            "if this policy is cancelled or not renewed by us, the party",
        ))
        if has_coverage_structure and has_boilerplate_cancel:
            is_renewal_context = True

    # ==========================================================
    # INVOICE/PAYMENT NOTICE CONTEXT: Documents that are billing
    # notices for non-payment (with payment stubs, "amount enclosed",
    # "return this portion with your payment") should return coverage
    # type (HAZ/HO), not cancellation subtype (NPAY).
    # ==========================================================
    is_payment_notice_context = (
        any(k in text for k in (
            "non-payment of premium", "non-payment", "nonpayment",
        ))
        and (
            sum(1 for k in (
                "return this portion with your payment",
                "amount enclosed",
                "make check or money order",
                "make check payable",
                "minimum amount due",
                "minimum premium amount due",
                "payment by check",
                "check-by-phone",
            ) if k in text) >= 2
        )
    )

    # ==========================================================
    # 0. CANCELLATION SUB-TYPES — checked FIRST 
    # (but NOT for DOI or RENEWAL or PAYMENT NOTICE contexts)
    # For CAN docs, the reason WHY it was cancelled is more
    # important than WHAT was insured (flood/home/etc).
    # Priority: BREQ > NPAY > NRNW > UNWR > CEL
    # ==========================================================

    if not is_doi_context and not is_renewal_context and not is_payment_notice_context:

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
            "flood insurance declarations",
            "flood zone determination",
        ))
        # "national flood insurance" is positive ONLY if NOT preceded by 
        # "purchase of" or "consider" — those are disclaimer contexts
        if not flood_positive and "national flood insurance" in text:
            nfi_disclaimer = any(k in text for k in (
                "purchase of flood insurance from the national flood",
                "consider the purchase of flood insurance",
                "need to purchase flood insurance",
                "purchase flood insurance from the national",
                "flood coverage is not provided",
                "flood coverage is not part of this policy",
                "is not part of this policy",
            ))
            if not nfi_disclaimer:
                flood_positive = True
        if flood_positive:
            return "FLD"

    # ==========================================================
    # FIRE / DWELLING FIRE (STRICT DETECTION)
    # Must indicate actual policy type, not endorsement wording.
    # ==========================================================

    # --- INS observation batch: Section 1 - Additional subtypes ---
    # DB (Dwelling Basic) - distinct from FIR
    if any(k in text for k in (
        "dwelling basic",
        "policy type: dwelling basic",
        "dwelling basic policy",
        "dwelling basic renewal",
    )):
        return "FIR"  # Map DB → FIR per extraction taxonomy

    # DS (Dwelling Special) - distinct from HAZ
    if any(k in text for k in (
        "dwelling special",
        "policy type: dwelling special",
        "dwelling special policy",
    )):
        return "HAZ"  # Map DS → HAZ per extraction taxonomy

    # MH (Manufactured Home) - check before HO
    if any(k in text for k in (
        "manufactured home",
        "mobile home",
        "mobilehome",
        "policy type: manufactured home",
        "manufactured housing",
    )):
        return "HO"  # Map MH → HO per extraction taxonomy

    # COMMERCIAL_BOP (Businessowners Policy)
    if any(k in text for k in (
        "businessowners policy",
        "business owners policy",
        "commercial property coverage part",
        "common declarations",
        "compak",
    )):
        return "HAZ"  # Map COMMERCIAL_BOP → HAZ per extraction taxonomy

    # FARM
    if any(k in text for k in (
        "farm ranch",
        "farm policy",
        "farm and ranch",
        "farmowners",
        "farm owners",
    )):
        return "HAZ"  # Map FARM → HAZ per extraction taxonomy

    fir_strong = any(k in text for k in (
        "dwelling fire policy",
        "policy type: dwelling fire",
        "coverage type: dwelling fire",
        "coverage type dwelling fire",
        "cov type - dwelling fire",
        "cov type dwelling fire",
        "covtype - dwelling fire",
        "covtype dwelling fire",
        # American Modern / Nationwide formats
        "policy type: dwelling basic",
        "dwelling basic policy",
        "dwelling basic renewal",
        "dwelling basic policy declaration",
        # Nationwide Allied format
        "dwelling fire policy number",
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
    # Guard: "vehicle" in endorsement/exclusion names like
    # "Recreational Or Service Vehicle Exclusion" must NOT trigger AUTO.
    # ==========================================================
    auto_patterns = [
        r"\bvin\b",
        r"\bautomobile\b",
        r"\bmotor vehicle\b",
    ]
    # "vehicle" needs extra context — only match if NOT in a carrier name
    # and NOT in an endorsement/exclusion/form name
    has_vehicle = bool(re.search(r"\bvehicle\b", text))
    if has_vehicle:
        # Check if "vehicle" is in a carrier name
        vehicle_in_carrier = bool(re.search(
            r"(allstate|nationwide|state farm|farmers|liberty|usaa|progressive|"
            r"geico|travelers|hartford|safeco|mercury).*"
            r"(vehicle|property).*(insurance|ins\b)",
            text,
        ))
        # Check if "vehicle" is in an endorsement/exclusion/form name
        vehicle_in_endorsement = any(k in text for k in (
            "vehicle exclusion",
            "service vehicle",
            "recreational or service vehicle",
            "recreational vehicle exclusion",
            "vehicle storage",
            "vehicle endorsement",
        ))
        # Check if strong homeowners/property signals are present —
        # a homeowners declarations page mentioning "vehicle" in an
        # endorsement schedule is NOT an auto policy
        has_strong_ho_signals = (
            sum(1 for c in ("coverage a", "coverage b", "coverage c",
                            "coverage d", "coverage e", "coverage f")
                if c in text) >= 3
            or any(k in text for k in (
                "homeowners", "declarations page", "dwelling",
                "residence premises", "house & home",
            ))
        )
        if not vehicle_in_carrier and not vehicle_in_endorsement and not has_strong_ho_signals:
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
            # American Modern format: "does not have coverage for the peril of earthquake"
            "peril of earthquake",
            "coverage for earthquake",
            "not have coverage for",
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
        # Wind/specialty formats
        "pol. type: wind",
        "pol type: wind",
        "pol.type: wind",
        "aop & hurricane",
        # "hurricane deductible",
    )):
        return "WND"

    # ==========================================================
    # 6a. UNIT OWNER (UO) — BEFORE HO6, more specific
    # Unit owner = condo certificate with master policy + unit context
    # ==========================================================
    if any(k in text for k in (
        "unit owner",
        "master policy",
    )) and any(k in text for k in (
        "certificate of insurance",
        "condominium unit number",
        "unit owner mortgagee",
        "master policy number",
    )):
        return "UO"

    # ==========================================================
    # 6. HO6 / CONDO (before HO — more specific)
    # Guard: "Condominium Unit Form" is a form NAME used by carriers
    # like Travelers for various policy types — it does NOT mean the 
    # policy is HO6. Only match when "condominium" appears in policy
    # type context, NOT inside form titles or endorsement names.
    # ==========================================================
    ho6_strong = any(k in text for k in (
        "ho6",
        "ho-6",
        "condo unit owner",
        "condo unit-owner",
        # Policy type labels
        "policy type: condominium",
        "condominium owners",
        "condominium policy declaration",
        "condominium policy",
        # American Modern format
        "condominium new business",
        "condominium renewal",
        "condominium policy change",
        # QBE / multi-peril with condo
        "e&s multi-peril",
    ))
    
    if not ho6_strong:
        # "condominium" needs a guard — exclude when it's part of a form name
        has_condo = any(k in text for k in (
            "condominium",
            "condo unit",
            "unit owner",
            "co-op",
            "town house",
            "town home",
        ))
        if has_condo:
            # Guard: "condominium unit form" or "condominium unit coverage form"
            # or "rental condominium unit form" = form title, NOT policy type
            condo_in_form_name = bool(re.search(
                r"(rental\s+)?condominium\s+unit\s+(form|coverage\s+form)", text
            ))
            # Guard: if strong HO/homeowners signals present alongside,
            # "condominium" is likely a form reference, not the policy type
            strong_ho_signal = any(k in text for k in (
                "homeowners policy",
                "homeowner policy",
                "homesaver policy",
                "home protection policy",
                "homeowners coverage",
            ))
            if not condo_in_form_name and not strong_ho_signal:
                ho6_strong = True
    
    if ho6_strong:
        return "HO6"

    # (UO detection moved to step 6a above HO6)

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
    # 9a. DWELLING SPECIAL → HAZ (American Modern format)
    # "Dwelling Special" is a commercial/non-residential dwelling policy
    # ==========================================================
    if any(k in text for k in (
        "dwelling special",
        "policy type: dwelling special",
        "dwelling special policy",
    )):
        return "HAZ"

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
        # EDI format HAZ indicators
        "cov type - home owners",
        "cov type home owners",
        "home-811",
        "home-s11",
        "coverage amt opt a",
        "premium amt opt a",
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
    # Guard: Third Party Notice of Termination should be BREQ,
    # not HAZ, even when "House & Home" policy type label is present.
    # ==========================================================
    if any(k in text for k in (
        "house & home",
        "house and home",
        "policy type: house",
    )):
        # Guard: if this is a Third Party Notice of Termination with 
        # policy termination, it should have been caught as BREQ above.
        # If we reach here, it's a genuine HAZ coverage type.
        if "third party notice of termination" not in text:
            return "HAZ"
        # For TPN docs, we want the cancellation subtype (BREQ/CEL) 
        # to take priority, but if we reached here, fall through to 
        # check other coverage types or return HAZ as last resort
        return "HAZ"

    # ==========================================================
    # 13. "Homeowners Policy" standalone → HO
    # For docs that mention "homeowners policy" but lack coverage details
    # ==========================================================
    if any(k in text for k in (
        "homeowners policy",
        "homeowner policy",
        "homeowner's policy",
        "homesaver policy",
    )):
        return "HO"

    # ==========================================================
    # 14. MOBILEHOME → HO (per table: HO includes Mobile Home)
    # ==========================================================
    if any(k in text for k in (
        "mobile home",
        "mobilehome",
        "manufactured home",
        "policy type: manufactured home",
    )):
        return "HO"

    # ==========================================================
    # DEFAULT
    # ==========================================================
    return "OTH"

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
    return "other"


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
        "OTH": "If policy-related information is not available in the document it will be considered as Unknown."
    }
    return explanations.get(policy_type, "Unknown policy type")