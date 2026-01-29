"""
Document Classification - FIXED VERSION
Added underwriting keywords, no deletions
"""
from typing import List
 
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
    Returns: BIN, COI, DOI, INV, RNS, RNW, CAN, FPN, OTH
    """

    text = " ".join(lines).lower()

    # -----------------------
    # CANCELLATION (CAN)
    # -----------------------
    if any(k in text for k in (
        "notice of cancellation",
        "policy cancellation",
        "is cancelled",
        "cancelled effective",
        "expiration notice",
        "return premium",
        "expired policy",
        "void date",
        "cease date",
    )):
        # 🔒 GUARD: Declarations / Renewals must NOT be CAN
        if any(rnw in text for rnw in (
            "declaration",
            "policy declarations",
            "mortgagee declarations",
            "renewal",
            "policy period",
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
        )):
            pass
        # 🔒 GUARD: underwriting / borrower wording alone ≠ CAN
        elif any(k in text for k in (
            "underwriting guidelines",
            "company request",
            "borrower request",
        )) and not any(c in text for c in (
            "notice of cancellation",
            "policy cancelled",
            "cancelled effective",
        )):
            pass
        else:
            return "CAN"

    # -----------------------
    # REINSTATEMENT (RNS)
    # -----------------------
    if any(k in text for k in (
        "reinstatement",
        "rescission of cancellation",
        "policy reinstated",
        "rescind cancellation",
        "withdrawal of cancellation",
    )):
        return "RNS"

    # -----------------------
    # INVOICE (INV)
    # -----------------------
    if any(k in text for k in (
        "invoice",
        "amount due",
        "balance due",
        "minimum due",
        "pay in full",
        "premium notice",
        "remit to",
        "make check payable",
    )):
        # 🔒 GUARD: declarations / renewals are NOT invoices
        if any(g in text for g in (
            "policy declarations",
            "declaration page",
            "mortgagee declarations",
            "coverage a",
            "coverage b",
            "coverage c",
            "coverage d",
            "coverage e",
            "coverage f",
            "policy period",
            "renewal",
        )):
            pass
        else:
            return "INV"

    # -----------------------
    # STRONG RENEWAL / DECLARATION (RNW)
    # -----------------------
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
    )):
        return "RNW"

    # -----------------------
    # CERTIFICATE OF INSURANCE (COI)
    # -----------------------
    if any(k in text for k in (
        "certificate of insurance",
        "this certifies that",
        "acord",
        "certificate holder",
    )):
        # 🔒 Guard: RNW / DOI must beat COI
        if any(r in text for r in (
            # RNW guards
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
            # DOI guards
            "interest removed",
            "deletion of interest",
            "mortgage deleted",
            "mortgage removed",
        )):
            pass
        else:
            return "COI"

    # -----------------------
    # DELETE OF INTEREST (DOI)
    # -----------------------
    if any(k in text for k in (
        "interest removed",
        "deletion of interest",
        "mortgage deleted",
        "mortgage removed",
    )):
        # 🔒 GUARD: mortgagee declarations ≠ DOI
        if any(r in text for r in (
            "policy declarations",
            "mortgagee declarations summary",
            "coverage a",
            "policy period",
        )):
            pass
        else:
            return "DOI"

    # -----------------------
    # FORCE PLACED NOTICE (FPN)
    # -----------------------
    if any(k in text for k in (
        "force placed notice",
        "force-placed notice",
        "second and final notice",
        "final notice of flood insurance",
        "lender-placed insurance",
    )):
        return "FPN"

    # -----------------------
    # BINDER (BIN)
    # -----------------------
    if any(k in text for k in (
        "binder without policy number",
        "quote without policy number",
        "binder issued",
        "temporary coverage",
    )):
        return "BIN"

    # -----------------------
    # DEFAULT
    # -----------------------
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