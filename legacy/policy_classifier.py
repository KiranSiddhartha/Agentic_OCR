# classification/policy_classifier.py

"""
Policy Type Classification based on official business rules
Matches the company's Policy Types reference table
"""

POLICY_MAP = {
    "AUTO": [
        # Auto/Vehicle insurance
        "auto policy",
        "motor insurance",
        "vehicle insurance",
        "vin number",
        "vin vehicle",
        "vehicle number",
        "auto mobile",
        "hatch",
        "motor vehicle",
        "boat owners",
        "airplane",
        "comprehensive",
        "collision"
    ],

    "ERQ": [
        # Earthquake
        "earthquake",
        "california earthquake authority",
        "earth and land movement",
        "earth rotation",
        "seismic"
    ],

    "FIR": [
        # Fire
        "dwelling fire",
        "dp3",
        "dp-3",
        "insured under perils fire",
        "fire policy"
    ],

    "FLD": [
        # Flood
        "flood",
        "fema",
        "flood zone",
        "flood insurance",
        "special flood hazard",
        "sfha",
        "nfip"
    ],

    "HAZ": [
        # Hazard (general property)
        "home guard",
        "farm owner with dwelling",
        "farm house with dwelling",
        "dwelling protector",
        "road and residence",
        "farm and ranch with dwelling",
        "home owner special form",
        "deluxe package with dwelling",
        "elite package",
        "insured property address",
        "covered location only"
    ],

    "HO6": [
        # Condo/Unit Owner
        "condominium",
        "unit owners",
        "town house",
        "town homes",
        "apartments",
        "condo unit owners",
        "rental unit owners",
        "co-op",
        "cooperative",
        "form ho6"
    ],

    "LL": [
        # Landlord
        "landlords",
        "rental dwelling",
        "rental",
        "rental owners"
    ],

    "HO": [
        # Homeowners (general)
        "homeowners",
        "homeowner",
        "mobile home",
        "form 3",
        "manufacture home",
        "ho3",
        "ho-3",
        "mobile home protector",
        "multi-peril",
        "multiperil",
        "multi peril",
        "e&s multi-peril",
        "e&s multiperil",
        "coverage a dwelling",
        "coverage a. dwelling",
        "coverage b",
        "coverage c",
        "coverage d",
        "coverage e",
        "coverage f",
        "personal property",
        "loss of use",
        "personal liability",
        "medical payments"
    ],

    "UO": [
        # Unit Owner (specific doc type)
        "associated with doc type coi",
        "unit owner policy",
        "master policy"
    ],

    "WND": [
        # Wind/Windstorm
        "windstorm",
        "wind and hail",
        "tropical cyclone",
        "insured under perils",
        "homeowners and wind only",
        "hurricane"
    ]
}

# Cancellation reasons (sub-classification)
CANCELLATION_REASONS = {
    "borrower_request": [
        "customer request",
        "borrower request",
        "insured request",
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
        "non-payment of premium"
    ],
    
    "non_renewal": [
        "cancellation of non-renewal",
        "non-renewal the policy"
    ],
    
    "underwriting": [
        "underwriting guidelines",
        "insured",
        "borrower moved to the different city",
        "company request",
        "no longer required by lender",
        "property sold"
    ]
}


def classify_policy(lines):
    """
    Enhanced policy classification with multi-pass detection
    Follows official policy type definitions
    """
    text = " ".join(lines).lower()

    # ========================================
    # PASS 1: Direct Keyword Matching
    # ========================================
    for policy_code, keywords in POLICY_MAP.items():
        for keyword in keywords:
            if keyword in text:
                return policy_code
    
    # ========================================
    # PASS 2: Structural Detection for HO
    # ========================================
    
    # Check for standard HO coverages (A through F)
    ho_coverages = [
        "coverage a",
        "coverage b", 
        "coverage c",
        "coverage d",
        "coverage e",
        "coverage f"
    ]
    
    coverage_count = sum(1 for cov in ho_coverages if cov in text)
    
    if coverage_count >= 3:  # 3+ standard coverages = HO policy
        return "HO"
    
    # ========================================
    # PASS 3: Carrier-Specific Patterns
    # ========================================
    
    # QBE Specialty typically writes HO policies
    if "qbe specialty" in text or "qbe specialty insurance" in text:
        if any(ind in text for ind in ["dwelling", "property", "coverage"]):
            return "HO"
    
    # ========================================
    # PASS 4: Combined Indicators
    # ========================================
    
    # Property + liability combo = HO
    has_dwelling = "dwelling" in text
    has_liability = "liability" in text or "personal liability" in text
    has_property = "personal property" in text or "coverage c" in text
    
    if has_dwelling and has_liability:
        return "HO"
    
    if has_dwelling and has_property:
        return "HO"
    
    # ========================================
    # PASS 5: Policy Number Patterns
    # ========================================
    
    # Some carriers use specific policy number formats
    import re
    
    # HO6 pattern (common for condos)
    if re.search(r'\bho6\b|\bho-6\b', text, re.I):
        return "HO6"
    
    # HO3 pattern
    if re.search(r'\bho3\b|\bho-3\b', text, re.I):
        return "HO"

    return "UNK"


def classify_cancellation_reason(lines):
    """
    Classify the reason for cancellation (sub-type)
    """
    text = " ".join(lines).lower()
    
    for reason_type, keywords in CANCELLATION_REASONS.items():
        for keyword in keywords:
            if keyword in text:
                return reason_type
    
    return "unknown"


def get_policy_explanation(policy_type: str) -> str:
    """
    Returns business explanation for policy type
    """
    explanations = {
        "AUTO": "Auto policy provides financial protection for losses related to a vehicle, including damage, injuries, theft, and accidents.",
        
        "ERQ": "Earthquake insurance pays the policyholder in the event of an earthquake that causes damage to the property.",
        
        "FIR": "Fire policy provides financial protection against losses and damages caused by fire.",
        
        "FLD": "Flood insurance denotes the specific insurance coverage against property loss from flooding.",
        
        "HAZ": "Hazard policy offers property owners protection against explosions, vandalism and some weather related occurrences.",
        
        "HO6": "HO6 condo insurance protects your unit and everything it contains and provides liability coverage.",
        
        "LL": "Landlord policy is designed to protect landlords from financial losses related to their rental properties.",
        
        "HO": "Homeowners insurance covers the home's structure, fixtures and contents from risks such as hail, wind, storm or fire.",
        
        "UO": "Unit owner policy covers the individual unit owner's responsibilities and belongings within their unit.",
        
        "WND": "Wind insurance covers damages caused by high winds, hurricane-force winds, tornadoes, and hail."
    }
    
    return explanations.get(policy_type, "Unknown policy type")