"""
Policy Type Classification - FINAL FIX
FIR guard added to prevent HO override
"""
import re
from typing import List

def classify_policy(lines: List[str]) -> str:
    """
    Classify insurance policy type with dominance guards.
    Returns: AUTO, ERQ, FIR, FLD, HAZ, HO6, LL, HO, UO, WND, UNK
    """

    text = " ".join(lines).lower()

    # -----------------------
    # 🔒 1. FIRE (DOMINANT) - WITH HO GUARD
    # Key fix: Only return FIR if NO HO indicators present
    # -----------------------
    if any(k in text for k in (
        "dwelling fire",
        "dp-1",
        "dp-3",
        "dp3",
        "fire policy",
        "insured under peril fire",
        "insured under perils fire",
        "coverage type: dwelling fire",
    )):
        # 🔒 CRITICAL GUARD: HO beats FIR
        if not any(h in text for h in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "personal liability",
            "homeowners",
            "home protection",
            "policy declarations",
            "residence premises",
        )):
            return "FIR"

    # -----------------------
    # 🔒 2. FLOOD (DOMINANT)
    # -----------------------
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

    # -----------------------
    # AUTO (STRICT)
    # -----------------------
    auto_patterns = [
        r"\bvin\b",
        r"\bvehicle\b",
        r"\bautomobile\b",
        r"\bmotor vehicle\b",
    ]

    if any(re.search(p, text) for p in auto_patterns) and not any(
        k in text for k in (
            "coverage a",
            "dwelling",
            "home protection",
            "residence premises",
        )
    ):
        return "AUTO"

    # -----------------------
    # EARTHQUAKE (STANDALONE)
    # -----------------------
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

    # -----------------------
    # WIND (STANDALONE ONLY)
    # -----------------------
    wind_only_markers = (
        "wind only",
        "wind-only policy",
        "windstorm policy",
        "hurricane only",
        "wind and hail only",
    )

    ho_markers = (
        "coverage a",
        "coverage b",
        "coverage c",
        "coverage d",
        "coverage e",
        "coverage f",
        "dwelling",
        "home protection",
        "policy declarations",
        "residence premises",
    )

    if any(w in text for w in wind_only_markers) and not any(h in text for h in ho_markers):
        return "WND"

    # -----------------------
    # 🔒 UNIT OWNER (UO) — COI ONLY
    # -----------------------
    if "certificate of insurance" in text and any(k in text for k in (
        "unit owner",
        "master policy",
        "condominium",
        "ho6",
    )):
        if not any(h in text for h in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "dwelling",
            "home protection",
            "policy declarations",
        )):
            return "UO"

    # -----------------------
    # 🔒 HO6 (before HO)
    # -----------------------
    if any(k in text for k in (
        "condominium",
        "condo unit",
        "unit owner",
        "ho6",
        "co-op",
        "town house",
        "town home",
    )):
        if not any(h in text for h in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "dwelling",
            "home protection",
            "policy declarations",
            "residence premises",
        )):
            return "HO6"

    # -----------------------
    # LANDLORD (LL)
    # -----------------------
    if any(k in text for k in (
        "rental dwelling",
        "rental property",
        "landlord",
        "lessor",
    )):
        if not any(h in text for h in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "dwelling",
            "home protection",
            "policy declarations",
            "residence premises",
            "owner occupied",
            "primary residence",
        )):
            return "LL"

    # -----------------------
    # 🔒 HOMEOWNERS (HO) — DOMINANT
    # -----------------------
    haz_markers = [
        "policy declarations",
        "home protection",
        "dwelling",
        "residence premises",
        "property location limit",
        "pll",
        "estimated residence value",
        "other structures",
        "loss of use",
        "personal liability",
        "medical payments",
        "coverage a",
        "coverage b",
        "coverage c",
        "coverage d",
        "coverage e",
        "coverage f",
    ]

    if sum(1 for m in haz_markers if m in text) >= 3:
        return "HO"

    # -----------------------
    # 🔒 HAZARD / COMMERCIAL (GUARDED)
    # -----------------------
    if any(k in text for k in (
        "property protection",
        "buildings - replacement cost",
        "commercial property",
        "commercial property coverage part",
        "medical office",
        "office occupancy",
        "blanket coverage",
        "property insured",
        "replacement cost",
        "amount of insurance",
        "policy term",
        "policy expires",
        "property deductible",
    )):
        if not any(h in text for h in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "personal liability",
            "medical payments",
            "residence premises",
            "homeowners",
        )):
            return "HAZ"

    # -----------------------
    # DEFAULT
    # -----------------------
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
        "UNK": "If policy-related information is not available in the document it will be considered as Unknown."
    }
    return explanations.get(policy_type, "Unknown policy type")