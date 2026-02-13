"""
Document Type Classifier - CLEAN ARCHITECTURE VERSION
Returns ONLY valid document types (structural classification).
Policy types and cancellation subtypes are handled by policy_classifier.

Valid document types: BIN, COI, DOI, INV, RNS, RNW, CAN, OTH, UNK
NOT returned: FPN, NRNW, BREQ/BRQ (these are policy subtypes)
"""
from typing import List
import re
 
VALID_DOC_TYPES = {
    "BIN",  # Binder
    "COI",  # Certificate of Insurance
    "DOI",  # Deletion of Interest
    "INV",  # Invoice
    "RNS",  # Reinstatement
    "RNW",  # Renewal/Declarations
    "CAN",  # Cancellation (includes non-renewal structurally)
    "OTH",  # Other
    "UNK",  # Unknown
}

# REMOVED FROM VALID DOCUMENT TYPES:
# - FPN: Force Placed Notice (no longer a valid doc type per business rules)
# - NRNW: Non-Renewal (this is a cancellation REASON, returned by policy_classifier)
# - BREQ/BRQ: Borrower Request (this is a cancellation REASON, returned by policy_classifier)
# - TPN: Third Party Notice (structural detection maps to CAN or DOI)
# - EDI: Electronic Data Interchange (format indicator, not a document type)

DOC_TYPES = {
    # ORDER MATTERS - More specific patterns first
    # NOTE: This dictionary is kept for backwards compatibility with keyword matching
    # but classify_document() only returns values from VALID_DOC_TYPES above
    
    "DOI": [
        # Deletion of Interest
        "deletion of interest",
        "interest removed",
        "mortgage deleted",
        "mortgage deleted/removed",
        "mortgage removed",
        "loan has been satisfied",
        "mortgagee interest removed",
        "mir - mortgagee interest removed",
        "mir-mortgagee interest removed",
        "cancel reason: mir",
        "cancel reason mir",
        # Loss payee deletion - CRITICAL FIX FOR "DELETED AS LOSS PAYEE"
        "deleted as loss payee",
        "removed as loss payee",
        "loss payee deleted",
        "loss payee removed",
        "loss payee has been deleted",
        "loss payee has been removed",
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
        "no longer required by lender",
        "insurance coverage notification",
        "coverage notification",
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
    Classify insurance document type based on STRUCTURE only.
    Returns: BIN, COI, DOI, INV, RNS, RNW, CAN, OTH, UNK

    Valid doc types per business rules:
      BIN, COI, DOI, INV, RNS, RNW, OTH, CAN, UNK
    
    Does NOT return (these are policy subtypes handled by policy_classifier):
      FPN   - Force Placed Notice (removed from valid types)
      BREQ  - Borrower Request (cancellation reason)
      TPN   - Third Party Notice (maps to CAN or DOI based on content)
      NRNW  - Non-Renewal (cancellation reason)
      EDI   - Electronic Data Interchange (format, not type)

    NRNW is NOT a doc type — non-renewal is a CAN with reason=NRNW.
    The policy classifier separately returns NRNW as a policy_type.
    BREQ is NOT a doc type — borrower request is a CAN with reason=BREQ.
    The policy classifier separately returns BREQ as a policy_type.
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
        has_interest_terminate = (
            bool(re.search(
                r"terminate the interest.*?(hereon|third party|interested party)", text))
            or "terminate the interest of the third party" in text
            or "terminate the interest" in text
        )

        if has_interest_terminate and not has_policy_terminate:
            # Only interest termination → DOI
            return "DOI"
        # Policy termination (borrower request) → CAN
        return "CAN"

    # ==========================================================
    # PRIORITY 2: DELETION OF INTEREST (DOI) — check BEFORE CAN
    # because some DOI docs also contain cancellation language
    # (e.g., "policy change/cancellation notice" with "no longer have an interest")
    # ==========================================================
    doi_signals = any(k in text for k in (
        "deletion of interest",
        "interest removed",
        "third party interest removed",
        "mortgage deleted",
        "mortgage removed",
        "terminate the interest of the third party",
        "interest is hereby removed",
        "interest has been removed",
        "loan has been satisfied",
        "you no longer have an interest",
        "no longer have an interest in the",
        "removed all indications of your interest",
        "mortgagee interest removed",
        "mir-mortgagee interest removed",
        # EDI format patterns
        "mir - mortgagee interest removed",
        "mir mortgagee interest removed",
        "cancel reason mir",
        # Additional OCR-robust patterns
        "interest removal",
        "interest deleted",
        "remove interest",
        "interest termination",
        "interest terminated",
        # Loss payee deletion patterns
        "deleted as loss payee",
        "removed as loss payee",
        "loss payee deleted",
        "loss payee removed",
        "loss payee has been deleted",
        "loss payee has been removed",
    )) or bool(re.search(
        r"mir[\s\-]*mortgagee\s+interest\s+removed", text
    )) or bool(re.search(
        r"cancel\s*reason[:\s]*mir", text
    ))
    if doi_signals:
        # 🔒 GUARD: mortgagee declarations / full policy docs ≠ DOI
        # Use regex for "coverage a" to avoid false match on "coverage amt"
        doi_guard = any(r in text for r in (
            "policy declarations",
            "mortgagee declarations summary",
        )) or bool(re.search(r"\bcoverage a\b", text))
        if not doi_guard:
            return "DOI"

    # ==========================================================
    # PRIORITY 3: CANCELLATION (CAN) — includes non-renewal
    # Non-renewal IS a form of cancellation per business rules.
    # ==========================================================
    if any(k in text for k in (
        "notice of cancellation",
        "cancellation notice",
        "policy cancellation",
        "flood policy cancellation",
        "is cancelled",
        "is being cancelled",
        "has been cancelled",
        "will be cancelled",
        "cancelled effective",
        "cancellation effective",
        "policy is cancelled",
        "policy cancelled",
        "void date",
        "cease date",
        "cancellation date",
        # Non-renewal keywords → still CAN doc type
        "notice of non-renewal",
        "non-renewal date",
        "non-renewal notice",
        "will be non-renewed",
        "will not be renewed",
        "nonrenewal notice",
        "notice of nonrenewal",
        # Policy change/cancellation notice (AmFam format)
        "policy change/cancellation notice",
        # LexisNexis / EDI formats
        "reason cancellation",
        "doc type - cancellation",
        "reason: cancellation",
        # Additional: LexisNexis insurance coverage notification with cancellation
        "reason cancellation customer",
        "cancellation customer initiated",
        "reason: cancellation customer initiated",
        "xlc-s11 doc type - cancellation",
        "doc type cancellation",
        "nlc-s11 doc type - cancellation",
        # EDI-style cancellation
        "cancel reason",
        "for all cancellation",
    )) or (
        # LexisNexis notification + "cancellation" anywhere = CAN
        "insurance coverage notification" in text and "cancellation" in text
    ):
        # 🔒 GUARD: Declarations / Renewals must NOT be CAN
        # Use \b to avoid false matches like "coverage afforded" matching "coverage a"
        # EXCEPTION: LexisNexis notifications with explicit cancellation reason
        # should ALWAYS be CAN regardless of guard
        is_lexisnexis_can = (
            "insurance coverage notification" in text 
            and "cancellation" in text
        )
        can_guard_patterns = [
            r"\bdeclarations?\b",
            r"\bpolicy declarations\b",
            r"\bmortgagee declarations\b",
            r"\bpolicy change declarations\b",
            r"\bcoverage a\b",
            r"\bcoverage b\b",
            r"\bcoverage c\b",
            r"\bcoverage d\b",
            r"\bcoverage e\b",
            r"\bcoverage f\b",
        ]
        # Additional guard: declarations with coverage/premium tables
        has_declaration_with_coverage = (
            any(re.search(r"\bdeclarations?\b", text) for _ in [1])
            and any(k in text for k in (
                "section i", "section ii",
                "property coverages", "liability coverages",
                "total premium", "policy forms and endorsements",
                "homesaver policy",
            ))
        )
        # Additional guard: mortgagee certificates or docs with strong 
        # coverage structure (A-F) + boilerplate cancellation language
        has_mortgagee_cert_context = "mortgagee certificate" in text
        has_coverage_with_boilerplate = (
            sum(1 for cov in ("a.dwelling", "b.other structures",
                              "c.personal property", "d.loss of use",
                              "e.personal liability", "f.medical payments")
                if cov in text) >= 3
            and any(k in text for k in (
                "if the policy is cancelled or not renewed",
                "advance notice of cancellation",
                "notice of cancellation we give our insured",
            ))
        )
        # 🔒 GUARD: "Cancellation notice for non-payment" documents that function
        # as invoices/billing notices should be INV, not CAN, when they contain
        # strong payment/invoice signals (payment stub, amount due, remittance).
        # These are conditional cancellation warnings requesting payment.
        is_payment_notice = (
            ("non-payment of premium" in text or "non-payment" in text 
             or "nonpayment of premium" in text)
        ) and (
            # Strong payment stub signals — these indicate an invoice, not a final cancellation
            sum(1 for k in (
                "return this portion with your payment",
                "amount enclosed",
                "make check or money order",
                "make check payable",
                "make checks payable",
                "minimum amount due",
                "minimum premium amount due",
                "remit to",
                "payment by check",
                "pay by phone",
                "check-by-phone",
            ) if k in text) >= 2
        )
        if is_payment_notice:
            pass  # Let it fall through to INV detection below
        elif not is_lexisnexis_can and (any(re.search(p, text) for p in can_guard_patterns) or has_declaration_with_coverage or has_mortgagee_cert_context or has_coverage_with_boilerplate):
            pass
        else:
            return "CAN"

    # ==========================================================
    # PRIORITY 4: REINSTATEMENT (RNS)
    # ==========================================================
    rns_signals = any(k in text for k in (
        "reinstatement",
        "rescission of cancellation",
        "policy reinstated",
        "rescind cancellation",
        "withdrawal of cancellation",
    ))
    if rns_signals:
        # 🔒 GUARD: "reinstatement date: n/a" or "reinstatement date:" 
        # appearing in declaration forms does NOT mean RNS.
        # Only trigger RNS if there's actual reinstatement context.
        rns_is_just_field_label = (
            "reinstatement date" in text
            and not any(k in text for k in (
                "policy reinstated",
                "rescission of cancellation",
                "rescind cancellation",
                "withdrawal of cancellation",
                "your policy has been reinstated",
                "hereby reinstated",
            ))
        )
        # Also guard: if strong renewal/declaration signals present,
        # "reinstatement" is just a field label in the dec page
        rns_in_declaration = any(k in text for k in (
            "renewal flood insurance",
            "flood insurance policy declarations",
            "policy declarations",
            "renewal notice",
            "declarations page",
            "agent issued declarations",
        ))
        if rns_is_just_field_label or rns_in_declaration:
            pass  # Skip RNS — it's just a field label in a declaration
        else:
            return "RNS"

    # (DOI moved to Priority 2 above)

    # PRIORITY 6: EDI WRAPPER (format only — never a doc type)
    if any(k in text for k in (
        "edi image",
        "electronic data interchange",
        "electronic image generated for edi",
        "electronic image generated",
        "generated for edi",
        "edi data",
    )):
        # If DOI signals exist → treat as DOI
        if any(k in text for k in (
            "interest removed",
            "mortgagee interest removed",
            "mir-mortgagee",
            "mir mortgagee",
        )) or bool(re.search(r"mir[\s\-]*mortgagee", text)):
            return "DOI"

        # If cancellation context → treat as CAN
        if any(k in text for k in (
            "cancellation",
            "cancel reason",
            "cancelled",
        )):
            return "CAN"

        # Otherwise do NOT classify as EDI
        return "OTH"
    
    # LexisNexis "insurance coverage notification" — classify based on content
    if "insurance coverage notification" in text or "lexisnexis" in text:
        # Check for cancellation context
        if any(k in text for k in (
            "reason cancellation", "cancellation customer",
            "doc type - cancellation", "doc type cancellation",
            "cancellation", "cancelled", "cancel date",
            "cancel reason",
        )):
            # Don't return CAN here if the CAN check above already failed
            # due to its guard. Instead, just skip EDI and let it fall 
            # through to RNW or other checks.
            pass
        # Check for DOI context
        elif any(k in text for k in (
            "interest removed", "mir-mortgagee", "mir mortgagee",
        )):
            pass  # Already handled above
        else:
            return "OTH"

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
        "make check or money order",
        "amount enclosed",
        "to pay in full amount due",
        "balance (to pay in full)",
        "return this portion with your payment",
    ))
    if inv_signals:
        # 🔒 GUARD: declarations with coverage tables are RNW, not INV
        # Also guard: "this is not an invoice/bill" (LexisNexis format)
        inv_guard = any(g in text for g in (
            "policy declarations",
            "declaration page",
            "declarations page",
            "mortgagee declarations",
            "agent issued declarations",
            "coverage a dwelling",
            "coverage b other",
            "coverage c personal",
            "coverage d loss",
            "this is not an invoice",
            "not an invoice/bill",
            "insurance coverage notification",
            # Additional guards for declaration documents
            "premium notice state farm",
            "homeowners policy",
            "homeowner policy",
            "dwelling (coverage a)",
            "dwelling coverage a",
            "limit of liability",
            "forms & endorsements",
            "forms and endorsements",
            "policy type",
            "location of premises",
            "mortgagee copy",
        )) or (
            "declarations" in text and re.search(r"\bcoverage a\b", text)
        ) or (
            "declarations" in text and "premium" in text and "policy" in text
        ) or (
            "premium notice" in text and "declarations" in text
        )
        if inv_guard:
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
        
        # Flood renewal specific
        "renewal flood insurance",
        "flood insurance policy declarations",
        "renewal billing payor",
        
        # Agent-issued declarations
        "agent issued declarations",
        "premium notice state farm",
        
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
    # PRIORITY 10: FORCE PLACED NOTICE (FPN) - REMOVED
    # FPN is no longer a valid document type per clean architecture.
    # Force placed notices should be classified as OTH if detected.
    # ==========================================================
    # Original FPN detection logic removed - FPN not in VALID_DOC_TYPES
    
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
    }
    
    return explanations.get(doc_type, "Unknown document type")