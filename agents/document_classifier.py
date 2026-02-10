"""
Document Classification - FIXED VERSION
Added underwriting keywords, no deletions
"""
from typing import List
import re
 
DOC_TYPES = {
    # ORDER MATTERS - More specific patterns first
    
    "FPN": [
        # Force Placed Notice
        "force placed notice",
        "force-placed notice", 
        "second and final notice",
        "final notice of flood insurance",
        "flood insurance required by lender",
        "force placed",
        "force-placed",
        "we will purchase coverage",
        "lender-placed insurance",
        "required by your mortgage",
        "adequately insured",
        "your property must be kept insured",
        "insurance will be purchased at your expense",
        "notice of special flood hazard"
    ],
    
    "DOI": [
        # Deletion of Interest
        "deletion of interest",
        "interest removed",
        "mortgage deleted",
        "mortgage deleted/removed",
        "mortgage removed",
        "loan has been satisfied"
    ],

    "RNS": [
        # Reinstatement
        "reinstatement",
        "rescission of cancellation",
        "rescission notice",
        "rescind the policy",
        "policy reinstated",
        "your policy has been reinstated",
        "withdrawal of cancellation",
        "rescind intend to cancellation"
    ],

    "CAN": [
        # Cancellation
        "cancellation notice",
        "policy cancelled",
        "your policy has been cancelled",
        "cancelled",
        "expired policy",
        "expiration notice",
        "return premium",
        "non-payment of premium",
        "non-renewal",
        "borrower request",
        "company cancelled",
        "the building has been sold",
        "property sold",
        "removed, destroyed",
        "cancelled by wish of borrower",
        "flood policy cancellation",
        "expiration",
        "total premium amount is -",
        "negative example total premium",
        # Added per instructions - underwriting reasons
        "underwriting guidelines",
        "company request",
        "no longer required by lender"
    ],

    "RNW": [
        # Renewal (Reciprocal)
        "renewal notice",
        "policy renewal",
        "renew your policy",
        "policy change",
        "reason: policy change",
        "renewal policy",
        "transaction desc: renewal",
        "transaction dese: renewal",
        "declaration form contains dwelling amount",
        "declaration form contains deductible amount",
        "borrower chooses to continue the policy",
        "revised declaration",
        "type: revised declaration",
        "renewed",
        "policy changes: from: to:",
        "policy period"
    ],

    "INV": [
        # Invoice
        "invoice number",
        "invoice date",
        "invoice total",
        "invoice amount",
        "past due",
        "due amount",
        "balance due",
        "pay in full",
        "paid in full",
        "remit to",
        "premium notice",
        "amount remit to",
        "make check payable",
        "minimum due",
        "the document only contains premium amount and due date without the balance due"
    ],

    "COI": [
        # Certificate of Insurance
        "certificate of insurance",
        "acord",
        "flood maps",
        "additional insured",
        "certificate holder",
        "this declaration page is attached",
        "certificate provisions"
    ],

    "BIN": [
        # Binder
        "binder without policy number",
        "quote without policy number",
        "quote date",
        "binder issued",
        "temporary coverage",
        "cover note",
        "binder is an offer issued"
    ],

    "OTH": [
        # Other
        "multiple loans number",
        "multiple policy numbers",
        "multiple insured names",
        "multiple insured names\\address",
        "borrower letters",
        "document without any details"
    ]
}

def classify_document(lines: List[str]) -> str:
    """
    Classify insurance document type.
    Returns: BIN, COI, DOI, INV, RNS, RNW, CAN, BRQ, TPN, FPN, EDI, OTH

    Valid doc types per business rules:
      BIN, COI, DOI, INV, RNS, RNW, OTH, CAN, FPN
    Additional extraction-only types (used for routing, not displayed):
      BRQ, TPN, EDI

    NRNW is NOT a doc type — non-renewal is a CAN with reason=non-renewal.
    The policy classifier separately returns NRNW as a policy_type.
    """

    text = " ".join(lines).lower()

    # ==========================================================
    # PRIORITY 1: THIRD PARTY NOTICE OF TERMINATION
    # Always doc_type=CAN (or DOI for interest-only).
    # The cancellation reason (BREQ) is handled by policy_classifier.
    # ==========================================================
    if "third party notice of termination" in text:
        has_policy_terminate = bool(re.search(
            r"terminate this policy effective[:\s]*\d", text))
        has_interest_terminate = bool(re.search(
            r"terminate the interest.*?hereon[:\s]*\d", text))

        if has_interest_terminate and not has_policy_terminate:
            # Only interest termination → DOI
            return "DOI"
        # Policy termination (borrower request) → CAN
        return "CAN"

    # ==========================================================
    # PRIORITY 2: CANCELLATION (CAN) — includes non-renewal
    # Non-renewal IS a form of cancellation per business rules.
    # ==========================================================
    if any(k in text for k in (
        "notice of cancellation",
        "policy cancellation",
        "is cancelled",
        "cancelled effective",
        "policy is cancelled",
        "void date",
        "cease date",
        # Non-renewal keywords → still CAN doc type
        "notice of non-renewal",
        "non-renewal date",
        "non-renewal notice",
        "will be non-renewed",
        "will not be renewed",
        "nonrenewal notice",
        "notice of nonrenewal",
    )):
        # 🔒 GUARD: Declarations / Renewals must NOT be CAN
        if any(rnw in text for rnw in (
            "declaration",
            "policy declarations",
            "mortgagee declarations",
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
        )):
            pass
        else:
            return "CAN"

    # ==========================================================
    # PRIORITY 4: REINSTATEMENT (RNS)
    # ==========================================================
    if any(k in text for k in (
        "reinstatement",
        "rescission of cancellation",
        "policy reinstated",
        "rescind cancellation",
        "withdrawal of cancellation",
    )):
        return "RNS"

    # ==========================================================
    # PRIORITY 5: DELETION OF INTEREST (DOI) — broader patterns
    # ==========================================================
    if any(k in text for k in (
        "deletion of interest",
        "interest removed",
        "mortgage deleted",
        "mortgage removed",
        "terminate the interest of the third party",
        "interest is hereby removed",
        "interest has been removed",
        "loan has been satisfied",
    )):
        # 🔒 GUARD: mortgagee declarations ≠ DOI
        if any(r in text for r in (
            "policy declarations",
            "mortgagee declarations summary",
            "coverage a",
        )):
            pass
        else:
            return "DOI"

    # ==========================================================
    # PRIORITY 6: EDI (Electronic Data Interchange image)
    # ==========================================================
    if any(k in text for k in (
        "edi image",
        "electronic data interchange",
    )):
        return "EDI"

    # ==========================================================
    # PRIORITY 7: INVOICE (INV) — check BEFORE RNW to catch
    # "policy bill" documents that also contain "effective date"
    # ==========================================================
    inv_signals = any(k in text for k in (
        "policy bill",
        "homeowners policy bill",
        "renewal premium bill",
        "invoice",
        "amount due",
        "balance due",
        "minimum due",
        "pay in full",
        "premium notice",
        "remit to",
        "make check payable",
        "make checks payable",
        "to pay in full amount due",
        "balance (to pay in full)",
        "return this portion with your payment",
    ))
    if inv_signals:
        # 🔒 GUARD: declarations with coverage tables are RNW, not INV
        if any(g in text for g in (
            "policy declarations",
            "declaration page",
            "mortgagee declarations",
            "coverage a dwelling",
            "coverage b other",
            "coverage c personal",
            "coverage d loss",
        )):
            pass
        else:
            return "INV"

    # ==========================================================
    # PRIORITY 8: STRONG RENEWAL / DECLARATION (RNW)
    # ==========================================================
    if (
        "declaration" in text
        and any(cov in text for cov in (
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
        ))
    ):
        return "RNW"

    if any(k in text for k in (
        # Declaration language
        "policy declarations",
        "declarations page",
        "policy declaration",
        "declaration page",
        "mortgagee declarations summary",
        "policy summary",

        # Coverage indicators
        "coverage a dwelling",
        "coverage b other structures",
        "coverage c personal property",
        "coverage d loss of use",
        "coverage e personal liability",
        "coverage f medical payments",
        "coverage and limits of liability",

        # Dwelling fire / dwelling policy indicators
        "dwelling policy",
        "dwelling fire policy",
        "dwelling fire policy number",
        "loss payee, mortgagee or other interest",
        "a. dwelling",

        # Deductible / dwelling indicators
        "dwelling amount",
        "dwelling limit",
        "all other peril deductible",
        "wind and hail deductible",
        "deductible",

        # Premium summary
        "total policy premium",
        "annual premium",
        "premium summary",
        "total premium this location",
        "total premium all locations",

        # Term / effective language
        "policy period",
        "effective date",
        "expiration date",
        "term start",
        "term end",

        # Change / amended declarations
        "policy change",
        "amended declarations",
        "revised declarations",
        "transaction effective date",

        # Renewal language
        "renewal notice",
        "this is your renewal",
    )):
        return "RNW"

    # ==========================================================
    # PRIORITY 9: CERTIFICATE OF INSURANCE (COI)
    # ==========================================================
    if any(k in text for k in (
        "certificate of insurance",
        "this certifies that",
        "acord",
        "certificate holder",
    )):
        # 🔒 Guard: RNW / DOI must beat COI
        if any(r in text for r in (
            "policy declarations",
            "declarations page",
            "policy declaration",
            "declaration page",
            "mortgagee declarations summary",
            "policy summary",
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "dwelling",
            "policy period",
            "effective date",
            "expiration date",
            "renewal",
            "renewed",
            "interest removed",
            "deletion of interest",
            "mortgage deleted",
            "mortgage removed",
        )):
            pass
        else:
            return "COI"

    # ==========================================================
    # PRIORITY 10: FORCE PLACED NOTICE (FPN)
    # ==========================================================
    if any(k in text for k in (
        "force placed notice",
        "force-placed notice",
        "second and final notice",
        "final notice of flood insurance",
        "lender-placed insurance",
    )):
        return "FPN"

    # ==========================================================
    # PRIORITY 11: BINDER (BIN)
    # ==========================================================
    if any(k in text for k in (
        "binder without policy number",
        "quote without policy number",
        "binder issued",
        "temporary coverage",
    )):
        return "BIN"

    # ==========================================================
    # DEFAULT
    # ==========================================================
    return "OTH"


def get_document_explanation(doc_type: str) -> str:
    """Business explanation for document type"""
    explanations = {
        "BIN": "A binder is an offer issued to the customer by the insurance company. It's an insurance contract used temporarily until the policy is issued.",
        
        "COI": "A COI is a statement of coverage issued by the company that insures your individual and business also which provides a summary of the coverage.",
        
        "DOI": "Once the loan has been satisfied or required change in Mortgage by the borrower then a notice of DOI will be raised.",
        
        "INV": "Invoice is a bill raised to the borrower with the details of due date and due amount which provides a summary of the pending balances.",
        
        "RNS": "Any Cancellation/Pending policy which can be renewed/reactivated after a lapse is known as reinstatement.",
        
        "RNW": "Once the borrower chooses to continue the policy with the same insurance company before the policy period expires would be considered as renewal.",
        
        "OTH": "Information with multiple policies listed in one document and document which is not related to insurance would be considered as other.",
        
        "CAN": "The Policy might get cancelled by wish of Borrower/Insurance company due to various reasons.",
        
        "FPN": "Force placed notice for required insurance coverage."
    }
    
    return explanations.get(doc_type, "Unknown document type")