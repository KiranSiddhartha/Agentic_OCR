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
    Priority: DOI/Termination Logic -> Renewal/Payment Guards -> Cancel Subtypes -> Coverage Types.
    """
    text = " ".join(lines).lower()

    # ==========================================================
    # DOI GUARD
    # ==========================================================
    term_signals = ("policy cancelled", "policy has been cancelled", "policy is cancelled", "policy will be cancelled")
    _has_policy_termination = bool(re.search(r"terminate this policy effective[:\s]*\d", text)) or any(k in text for k in term_signals)

    doi_keywords = (
        "no longer have an interest", "loan has been satisfied", "interest removed", "interest has been removed",
        "deletion of interest", "mortgagee interest removed", "mir-mortgagee interest removed", "mir mortgagee interest removed",
        "removed all indications of your interest", "interest terminated", "terminate the interest of the third party", "terminate the interest"
    )
    is_doi_context = (any(k in text for k in doi_keywords) or bool(re.search(r"mir[\s\-]*mortgagee\s+interest\s+removed", text))) and not _has_policy_termination

    # ==========================================================
    # RENEWAL/DECLARATION GUARD
    # ==========================================================
    renewal_keywords = (
        "policy declarations", "declarations summary", "mortgagee declarations", "policy change summary", "policy change declarations",
        "transaction: renewal", "transaction desc: renewal", "agent issued declarations", "amended declarations", "amended policy information",
        "renewal notice", "policy renewal", "landlord protection policy declarations", "wind only policy - declarations",
        "homeowners hw-", "homesaver policy", "mortgagee certificate"
    )
    is_renewal_context = any(k in text for k in renewal_keywords)

    if not is_renewal_context:
        cov_structure = ("coverage a", "coverage b", "coverage c", "coverage d", "coverage e", "coverage f", 
                         "a.dwelling", "b.other structures", "c.personal property", "d.loss of use", "e.personal liability", "f.medical payments")
        has_coverage_structure = sum(1 for cov in cov_structure if cov in text) >= 3
        
        boilerplate_cancels = (
            "if the policy is cancelled or not renewed", "notice of cancellation we give our insured", "advance notice of cancellation",
            "same advance notice of cancellation", "the mortgagee will be notified at least", "if this policy is cancelled or not renewed by us, the party"
        )
        if has_coverage_structure and any(k in text for k in boilerplate_cancels):
            is_renewal_context = True

    # ==========================================================
    # INVOICE/PAYMENT NOTICE CONTEXT
    # ==========================================================
    pay_stubs = (
        "return this portion with your payment", "amount enclosed", "make check or money order", "make check payable",
        "minimum amount due", "minimum premium amount due", "payment by check", "check-by-phone"
    )
    is_payment_notice_context = (
        any(k in text for k in ("non-payment of premium", "non-payment", "nonpayment")) and sum(1 for k in pay_stubs if k in text) >= 2
    )

    # ==========================================================
    # 0. CANCELLATION SUB-TYPES
    # ==========================================================
    if not is_doi_context and not is_renewal_context and not is_payment_notice_context:
        # BREQ
        if "third party notice of termination" in text and bool(re.search(r"terminate this policy effective[:\s]*\d", text)):
            return "BREQ"

        breq_keywords = (
            "insured - non pay", "insured non pay", "insured - nonpay", "insured request", "borrower request", "customer request",
            "customer initiated", "cancellation customer initiated", "cancellation, customer initiated", "reason cancellation customer",
            "at the request of the insured", "requested by the insured", "requested by insured", "reason cancellation customer initiated",
            "reason: customer initiated", "cancel reason: customer", "cancel reason customer"
        )
        if any(k in text for k in breq_keywords): return "BREQ"
        
        # LexisNexis BREQ fallback
        if "insurance coverage notification" in text and "cancellation" in text:
            if not any(k in text for k in ("non-payment", "nonpayment", "failure to pay", "non-renewal", "nonrenewal", "underwriting", "company request")):
                return "BREQ"
        
        # NPAY
        npay_keywords = (
            "premium payment has not been received", "non-payment of premium", "nonpayment of premium",
            "nonpayment of the required premium", "nonpayment of required premium",
            "failure to pay premium", "premium not paid", "premium has not been paid",
            "payment is not received on or before", "for nonpayment of"
        )
        if any(k in text for k in npay_keywords): return "NPAY"
        if re.search(r"nonpayment.{0,25}premium", text): return "NPAY"

        # NRNW
        if any(k in text for k in ("non-renewal", "nonrenewal", "will be non-renewed", "will not be renewed", "notice of non-renewal")):
            return "NRNW"

        # UNWR
        unwr_strong = any(k in text for k in (
            "underwriting guidelines", "building has been sold", "building has been sold, removed", "property has been sold",
            "no longer meets the definition", "company request", "company decision", "does not meet underwriting", "risk does not meet"
        ))
        unwr_with_cancel = "underwriting" in text and any(k in text for k in ("cancellation", "cancelled", "cancel", "terminated", "non-renewal")) \
                           and "rating/underwriting" not in text and "underwriting information" not in text
        if unwr_strong or unwr_with_cancel: return "UNWR"

        # CEL
        cel_keywords = (
            "cancellation notice", "notice of cancellation", "policy cancellation", "flood policy cancellation", "will be cancelled",
            "has been cancelled", "is being cancelled", "cancelled effective", "cancellation effective", "cancellation date"
        )
        if any(k in text for k in cel_keywords): return "CEL"

    # ==========================================================
    # 1. FLOOD (DOMINANT)
    # ==========================================================
    if any(k in text for k in ("flood policy", "flood insurance", "nfip", "fema", "flood zone", "flood service center", "standard flood insurance")):
        fld_exclusions = (
            "does not have coverage for the peril of flood", "flood is excluded", "flood coverage is not provided",
            "does not include coverage for damage resulting from flood", "does not include coverage for flood", "not include flood",
            "flood insurance coverage, you may have", "purchase of flood insurance", "purchase separate flood",
            "consider the purchase of flood", "need to purchase flood"
        )
        if not any(excl in text for excl in fld_exclusions): return "FLD"
        
        flood_positive = any(k in text for k in ("flood policy number", "flood insurance policy declarations", "flood insurance declarations", "flood zone determination"))
        if not flood_positive and "national flood insurance" in text:
            nfi_disclaimer = any(k in text for k in ("purchase of", "consider the purchase", "need to purchase", "flood coverage is not provided", "not part of this policy"))
            if not nfi_disclaimer: flood_positive = True
        if flood_positive: return "FLD"

    # ==========================================================
    # FIRE / DWELLING FIRE
    # ==========================================================
    # Specific Mappings
    if any(k in text for k in ("dwelling basic", "policy type: dwelling basic", "dwelling basic policy", "dwelling basic renewal")): return "FIR"
    if any(k in text for k in ("dwelling special", "policy type: dwelling special", "dwelling special policy")): return "HAZ"
    if any(k in text for k in ("manufactured home", "mobile home", "mobilehome", "policy type: manufactured home", "manufactured housing")): return "HAZ"
    if any(k in text for k in ("businessowners policy", "business owners policy", "commercial property coverage part", "common declarations", "compak")): return "HAZ"
    if any(k in text for k in ("farm ranch", "farm policy", "farm and ranch", "farmowners", "farm owners")): return "HAZ"

    fir_strong = any(k in text for k in (
        "dwelling fire policy", "policy type: dwelling fire", "coverage type: dwelling fire", "coverage type dwelling fire",
        "cov type - dwelling fire", "cov type dwelling fire", "covtype - dwelling fire", "covtype dwelling fire", "dwelling basic policy",
        "dwelling basic renewal", "dwelling basic policy declaration", "dwelling fire policy number"
    ))
    
    if not fir_strong and "dwelling fire" in text:
        dfire_endorsements = ("dwelling fire provisions", "dwelling fire endorsement", "amendment of home and dwelling fire", "amendment of dwelling fire")
        dfire_as_peril = any(k in text for k in ("landlord", "landlord protection", "occupancy: tenant", "loss of rent", "rental value")) or bool(re.search(r"a\s+dwelling\s+fire\s+[\$\d]", text))
        if not any(k in text for k in dfire_endorsements) and not dfire_as_peril:
            fir_strong = True

    if fir_strong or bool(re.search(r"\bdfir(e)?\b", text)) or "dfire-s11" in text or bool(re.search(r"\bdp[-\s]?(1|2|3)\b", text)) or bool(re.search(r"cov\s*type\s*[:\-]?\s*dwelling\s*fire", text)):
        return "FIR"

    # ==========================================================
    # 3. AUTO
    # ==========================================================
    auto_patterns = (r"\bvin\b", r"\bautomobile\b", r"\bmotor vehicle\b")
    has_vehicle = bool(re.search(r"\bvehicle\b", text))
    if has_vehicle:
        vehicle_in_carrier = bool(re.search(r"(allstate|nationwide|state farm|farmers|liberty|usaa|progressive|geico|travelers|hartford|safeco|mercury).*(vehicle|property).*(insurance|ins\b)", text))
        vehicle_endorse = any(k in text for k in ("vehicle exclusion", "service vehicle", "recreational or service vehicle", "recreational vehicle exclusion", "vehicle storage", "vehicle endorsement"))
        has_strong_ho = (sum(1 for c in ("coverage a", "coverage b", "coverage c", "coverage d", "coverage e", "coverage f") if c in text) >= 3 or 
                         any(k in text for k in ("homeowners", "declarations page", "dwelling", "residence premises", "house & home")))
        if not vehicle_in_carrier and not vehicle_endorse and not has_strong_ho: return "AUTO"
    if any(re.search(p, text) for p in auto_patterns): return "AUTO"

    # ==========================================================
    # 4. ERQ
    # ==========================================================
    if any(k in text for k in ("earthquake", "erq", "eq policy", "earthquake insurance")):
        erq_excluded = any(k in text for k in (
            "does not provide earthquake", "not provide earthquake coverage", "earthquake is excluded", "earthquake coverage is not",
            "no earthquake coverage", "earthquake is not covered", "does not include earthquake", "peril of earthquake", "coverage for earthquake", "not have coverage for"
        ))
        if not erq_excluded: return "ERQ"

    # ==========================================================
    # 5. WIND
    # ==========================================================
    wnd_keys = (
        "wind-only policy", "wind-only coverage", "wind only policy", "wind only coverage", "standalone wind policy", "policy type: wind",
        "windstorm insurance policy", "hw-2 wind only", "hw2 wind only", "wind only", "pol. type: wind", "pol type: wind", "pol.type: wind", "aop & hurricane"
    )
    if any(k in text for k in wnd_keys): return "WND"

    # ==========================================================
    # 6a. UNIT OWNER (UO)
    # ==========================================================
    if any(k in text for k in ("unit owner", "master policy")) and any(k in text for k in ("certificate of insurance", "condominium unit number", "unit owner mortgagee", "master policy number")):
        return "UO"

    # ==========================================================
    # 6. HO6 / CONDO
    # ==========================================================
    ho6_strong = any(k in text for k in (
        "ho6", "ho-6", "condo unit owner", "condo unit-owner", "policy type: condominium", "condominium owners", "condominium policy declaration",
        "condominium policy", "condominium new business", "condominium renewal", "condominium policy change", "e&s multi-peril"
    ))
    if not ho6_strong:
        if any(k in text for k in ("condominium", "condo unit", "unit owner", "co-op", "town house", "town home")):
            condo_form = bool(re.search(r"(rental\s+)?condominium\s+unit\s+(form|coverage\s+form)", text))
            ho_signal = any(k in text for k in ("homeowners policy", "homeowner policy", "homesaver policy", "home protection policy", "homeowners coverage"))
            if not condo_form and not ho_signal: ho6_strong = True
    if ho6_strong: return "HO6"

    # ==========================================================
    # 8. LANDLORD (LL)
    # ==========================================================
    if any(k in text for k in ("rental dwelling", "rental property", "landlord", "landlord protection", "lessor", "occupancy: tenant", "loss of rent, rental value", "loss of rent")):
        return "LL"

    # ==========================================================
    # 9. HAZ / COMMERCIAL
    # ==========================================================
    haz_keys = (
        "property protection", "commercial property", "commercial property coverage", "medical office", "office occupancy", "blanket coverage",
        "property insured", "amount of insurance", "property deductible", "buildings - replacement cost", "cov type - home owners",
        "cov type home owners", "home-811", "home-s11", "coverage amt opt a", "premium amt opt a"
    )
    if any(k in text for k in haz_keys):
        res_patterns = (r"\bcoverage a\b", r"\bcoverage b\b", r"\bcoverage c\b", r"\bcoverage e\b", r"\bcoverage f\b", r"\bpersonal liability\b", r"\bmedical payments\b", r"\bresidence premises\b", r"\bhomeowners\b", r"\bhome protection\b")
        if not any(re.search(p, text) for p in res_patterns): return "HAZ"

    # ==========================================================
    # 10. HOMEOWNERS (HO)
    # ==========================================================
    ho_markers = (
        "coverage a", "coverage b", "coverage c", "coverage d", "coverage e", "coverage f", "personal liability", "home protection",
        "policy declarations", "residence premises", "property location limit", "pll", "estimated residence value", "other structures",
        "loss of use", "medical payments", "homeowners", "homeowners pol", "homeowner pol", "limit of liability", "forms & endorsements",
        "forms and endorsements", "dwelling amount", "dwelling limit", "deductible"
    )
    ho_score = sum(1 for m in ho_markers if m in text)
    if ho_score >= 3: return "HO"
    if ho_score >= 1 and "dwelling" in text and "dwelling fire" not in text: return "HO"
    if ho_score >= 1 and "dwell " in text and "dwelling fire" not in text and "dfire" not in text: return "HO"

    # ==========================================================
    # REMAINING
    # ==========================================================
    if any(k in text for k in ("house & home", "house and home", "policy type: house")):
        return "HAZ" if "third party notice of termination" not in text else "HAZ" 
    
    if any(k in text for k in ("homeowners policy", "homeowner policy", "homeowner's policy", "homesaver policy")): return "HO"
    
    if any(k in text for k in ("mobile home", "mobilehome", "manufactured home", "policy type: manufactured home")): return "HAZ"

    return "OTH"

# =========================================================
# CANCELLATION REASON
# =========================================================
CANCELLATION_REASONS = {
    "borrower_request": ["customer request", "borrower request", "insured request", "insured name request", "agent request", "property sold"],
    "cancellation": ["cancellation of interest", "reason not given for the cancellation"],
    "non_payment": ["insured amount not paid", "premium amount not paid", "non-payment of premium", "non-payment"],
    "non_renewal": ["cancellation of non-renewal", "non-renewal the policy", "non-renewal"],
    "underwriting": ["underwriting guidelines", "insured/borrower moved", "company request", "no longer required by lender", "property sold"]
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