# # classification/document_classifier.py

# """
# Document Classification based on official business rules
# Matches the company's Document Types reference table
# """

# DOC_TYPES = {
#     # ⚠️ ORDER MATTERS - More specific patterns first!
    
#     "FPN": [
#         # Force Placed Notice - Must be very specific to avoid false positives
#         "second and final notice",
#         "final notice of flood insurance",
#         "flood insurance required by lender",
#         "force placed",
#         "force-placed",
#         "we will purchase coverage",
#         "lender-placed insurance",
#         "required by your mortgage",
#         "adequately insured",
#         "your property must be kept insured",
#         "insurance will be purchased at your expense",
#         "notice of special flood hazard"
#         # NOTE: Removed standalone "sfha" and "nfip" - these appear in all flood policies
#         # FPN must have clear "notice" or "requirement" context
#     ],
    
#     "DOI": [
#         # Deletion of Interest
#         "interest removed",
#         "deletion of interest",
#         "mortgage deleted",
#         "mortgage removed",
#         "loan has been satisfied"
#     ],

#     "RNW": [
#         # Renewal (Reciprocal)
#         "renewal notice",
#         "policy renewal",
#         "renew your policy",
#         "renewed",
#         "policy change",
#         "reason: policy change",
#         "renewal policy",
#         "transaction desc: renewal",
#         "transaction dese: renewal",  # OCR variant
#         "declaration form contains dwelling amount",
#         "declaration form contains deductible amount",
#         "borrower chooses to continue the policy",
#         "revised declaration",  # Added - key for your doc
#         "type: revised declaration",  # Added - exact match
#         "policy changes: from: to:",  # Added - indicates renewal with changes
#         "policy period"  # Added - if has active period, likely renewal/COI
#     ],

#     "RNS": [
#         # Reinstatement
#         "reinstatement",
#         "policy reinstated",
#         "rescission of cancellation",
#         "rescission notice",
#         "your policy has been reinstated",
#         "rescind intend to cancellation",
#         "withdrawal of cancellation"
#     ],

#     "CAN": [
#         # Cancellation
#         "cancellation notice",
#         "policy cancelled",
#         "flood policy cancellation",  # Added - specific to your doc
#         "your policy has been cancelled",
#         "expired policy",
#         "expiration notice",
#         "return premium",
#         "cancelled by wish of borrower",
#         "non-payment of premium",
#         "non-renewal",
#         "borrower request",
#         "company cancelled",
#         "the building has been sold",  # Added - from your doc
#         "removed, destroyed"  # Added - from your doc
#     ],

#     "INV": [
#         # Invoice
#         "invoice number",
#         "invoice date",
#         "invoice total",
#         "past due",
#         "due amount",
#         "balance due",
#         "pay in full",
#         "remit to",
#         "premium notice",
#         "amount remit to",
#         "make check payable"
#     ],

#     "COI": [
#         # Certificate of Insurance
#         "certificate of insurance",
#         "acord",
#         "flood maps",
#         "additional insured",
#         "certificate holder",
#         "this declaration page is attached",
#         "certificate provisions"
#     ],

#     "BIN": [
#         # Binder (temporary coverage)
#         "binder without policy number",
#         "quote without policy number",
#         "quote date",
#         "binder issued",
#         "temporary coverage",
#         "cover note",
#         "binder is an offer issued"
#     ],

#     "OTH": [
#         # Other documents
#         "multiple loans number",
#         "multiple policy numbers",
#         "multiple insured names",
#         "borrower letters",
#         "document without any details"
#     ]
# }


# def classify_document(lines):
#     """
#     Enhanced document classification with business logic
#     Follows official document type definitions
#     """
#     text = " ".join(lines).lower()
    
#     # ========================================
#     # PRE-CHECK 1: Renewal Invoice Detection
#     # ========================================
#     has_invoice = any(kw in text for kw in [
#         "invoice number", "invoice date", "invoice total", "invoice"
#     ])
#     has_renewal = any(kw in text for kw in [
#         "renewal", "transaction desc: renewal", "transaction dese: renewal",
#         "renewal policy", "policy renewal"
#     ])
    
#     if has_invoice and has_renewal:
#         return "RNW"  # Renewal Invoice
    
#     # ========================================
#     # PRE-CHECK 2: Cancellation Context
#     # ========================================
#     has_cancellation = "cancellation" in text or "cancelled" in text
#     has_rescission = "rescission" in text or "reinstated" in text
    
#     if has_cancellation and has_rescission:
#         return "RNS"  # Reinstatement (takes priority over cancellation)
    
#     # ========================================
#     # STANDARD KEYWORD MATCHING
#     # ========================================
#     for doc_type, keywords in DOC_TYPES.items():
#         for keyword in keywords:
#             if keyword in text:
#                 # Special validation for BIN to prevent false positives
#                 if doc_type == "BIN":
#                     # Only return BIN if explicit binder indicators present
#                     if any(x in text for x in [
#                         "binder without policy number",
#                         "quote without policy number",
#                         "binder issued",
#                         "temporary coverage"
#                     ]):
#                         return doc_type
#                     continue
                
#                 return doc_type
    
#     # ========================================
#     # FALLBACK HEURISTICS
#     # ========================================
    
#     # Invoice without renewal
#     if has_invoice and not has_renewal:
#         return "INV"
    
#     # Declaration page
#     if "declaration" in text and "coverage" in text:
#         if any(x in text for x in ["certificate", "insured", "limits"]):
#             return "COI"
    
#     # Cancellation without rescission
#     if has_cancellation and not has_rescission:
#         return "CAN"
    
#     return "OTH"


# def get_document_explanation(doc_type: str) -> str:
#     """
#     Returns business explanation for document type
#     """
#     explanations = {
#         "BIN": "A binder is an offer issued to the customer by the insurance company. It's an insurance contract used temporarily until the policy is issued.",
        
#         "COI": "A COI is a statement of coverage issued by the company that insures your individual and business also which provides a summary of the coverage.",
        
#         "DOI": "Once the loan has been satisfied or required change in Mortgage by the borrower then a notice of DOI will be raised.",
        
#         "INV": "Invoice is a bill raised to the borrower with the details of due date and due amount which provides a summary of the pending balances.",
        
#         "RNS": "Any Cancellation/Pending policy which can be renewed/reactivated after a lapse is known as reinstatement.",
        
#         "RNW": "Once the borrower chooses to continue the policy with the same insurance company before the policy period expires would be considered as renewal.",
        
#         "OTH": "Information with multiple policies listed in one document and document which is not related to insurance would be considered as other.",
        
#         "CAN": "The Policy might get cancelled by wish of Borrower/Insurance company due to various reasons.",
        
#         "FPN": "Force placed notice for required insurance coverage."
#     }
    
#     return explanations.get(doc_type, "Unknown document type")

"""
Document Classification based on official business rules
Matches the company's Document Types reference table
"""

DOC_TYPES = {
    # ORDER MATTERS – specific first

    "FPN": [
        "second and final notice",
        "final notice of flood insurance",
        "flood insurance required by lender",
        "force placed",
        "force-placed",
        "we will purchase coverage",
        "lender-placed insurance",
        "required by your mortgage",
        "adequately insured",
        "insurance will be purchased at your expense",
        "notice of special flood hazard"
    ],

    "DOI": [
        "interest removed",
        "deletion of interest",
        "mortgage deleted",
        "mortgage removed",
        "loan has been satisfied"
    ],

    "RNW": [
        "renewal notice",
        "policy renewal",
        "renew your policy",
        "renewed",
        "renewal policy",
        "transaction desc: renewal",
        "transaction dese: renewal",
        "revised declaration",
        "policy period",
        "declaration form contains dwelling amount",
        "declaration form contains deductible amount"
    ],

    "RNS": [
        "reinstatement",
        "policy reinstated",
        "rescission of cancellation",
        "rescission notice",
        "withdrawal of cancellation"
    ],

    "CAN": [
        "cancellation notice",
        "policy cancelled",
        "expired policy",
        "expiration notice",
        "return premium",
        "non-payment of premium",
        "non-renewal",
        "borrower request",
        "company cancelled",
        "property sold",
        "removed, destroyed"
    ],

    "INV": [
        "invoice",
        "invoice number",
        "invoice date",
        "balance due",
        "amount due",
        "minimum due",
        "paid in full",
        "past due",
        "remit to",
        "make check payable",
        "premium notice"
    ],

    "COI": [
        "certificate of insurance",
        "acord",
        "flood maps",
        "certificate holder",
        "additional insured"
    ],

    "BIN": [
        "binder without policy number",
        "quote without policy number",
        "binder issued",
        "temporary coverage",
        "cover note"
    ],

    "OTH": [
        "multiple policy numbers",
        "multiple loan numbers",
        "borrower letters",
        "document without any details"
    ]
}


def classify_document(lines):
    text = " ".join(lines).lower()

    has_invoice = "invoice" in text
    has_renewal = "renewal" in text

    if has_invoice and has_renewal:
        return "RNW"

    if "cancellation" in text and "rescission" in text:
        return "RNS"

    for doc_type, keywords in DOC_TYPES.items():
        for kw in keywords:
            if kw in text:
                if doc_type == "BIN" and "policy number" in text:
                    continue
                return doc_type

    if has_invoice:
        return "INV"

    return "OTH"


def get_document_explanation(doc_type):
    explanations = {
        "BIN": "Temporary insurance contract issued before policy number generation.",
        "COI": "Certificate summarizing insurance coverage.",
        "DOI": "Document indicating removal of mortgage or lien interest.",
        "INV": "Invoice requesting premium payment.",
        "RNS": "Reinstatement after cancellation or lapse.",
        "RNW": "Policy renewed before expiration.",
        "CAN": "Policy cancellation notice.",
        "FPN": "Force placed insurance notice.",
        "OTH": "Unclassified or non-insurance document."
    }
    return explanations.get(doc_type, "Unknown document type")
