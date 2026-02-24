from typing import List
import re

VALID_DOC_TYPES = {"BIN", "COI", "DOI", "INV", "RNS", "RNW", "CAN", "OTH"}

DOC_TYPES = {
    "DOI": [
        "deletion of interest", "interest removed", "mortgage deleted", "mortgage deleted/removed", "mortgage removed", "loan has been satisfied",
        "mortgagee interest removed", "mir - mortgagee interest removed", "mir-mortgagee interest removed", "cancel reason: mir", "cancel reason mir",
        "deleted as loss payee", "removed as loss payee", "loss payee deleted", "loss payee removed", "loss payee has been deleted", "loss payee has been removed"
    ],
    "RNS": [
        "reinstatement", "rescission of cancellation", "rescission notice", "rescind the policy", "policy reinstated", "your policy has been reinstated",
        "withdrawal of cancellation", "rescind intend to cancellation"
    ],
    "CAN": [
        "cancellation notice", "policy cancelled", "your policy has been cancelled", "cancelled", "expired policy", "expiration notice", "return premium",
        "non-payment of premium", "non-renewal", "borrower request", "company cancelled", "the building has been sold", "property sold", "removed, destroyed",
        "cancelled by wish of borrower", "flood policy cancellation", "expiration", "total premium amount is -", "negative example total premium",
        "underwriting guidelines", "company request", "no longer required by lender", "insurance coverage notification", "coverage notification"
    ],
    "RNW": [
        "renewal notice", "policy renewal", "renew your policy", "policy change", "reason: policy change", "renewal policy", "transaction desc: renewal",
        "transaction dese: renewal", "declaration form contains dwelling amount", "declaration form contains deductible amount",
        "borrower chooses to continue the policy", "revised declaration", "type: revised declaration", "renewed", "policy changes: from: to:", "policy period"
    ],
    "INV": [
        "invoice number", "invoice date", "invoice total", "invoice amount", "past due", "due amount", "balance due", "pay in full", "paid in full", "remit to",
        "premium notice", "amount remit to", "make check payable", "minimum due", "policy bill", "premium bill", "premium statement", "renewal premium bill",
        "homeowners policy bill", "landlords policy bill", "condominium policy bill", "the document only contains premium amount and due date without the balance due"
    ],
    "COI": ["certificate of insurance", "acord", "flood maps", "additional insured", "certificate holder", "this declaration page is attached", "certificate provisions"],
    "BIN": ["binder without policy number", "quote without policy number", "quote date", "binder issued", "temporary coverage", "cover note", "binder is an offer issued"],
    "OTH": ["multiple loans number", "multiple policy numbers", "multiple insured names", "multiple insured names\\address", "borrower letters", "document without any details"]
}

def classify_document(lines: List[str]) -> str:
    """Classify insurance document type based on STRUCTURE only. Returns: BIN, COI, DOI, INV, RNS, RNW, CAN, OTH """
    text = " ".join(lines).lower()

    # ==========================================================
    # PRIORITY 1: THIRD PARTY NOTICE (TPN) -> CAN or DOI
    # ==========================================================
    if "third party notice of termination" in text:
        has_pol_term = bool(re.search(r"terminate this policy effective[:\s]*\d", text))
        has_int_term = (bool(re.search(r"terminate the interest.*?(hereon|third party|interested party)", text)) or 
                        "terminate the interest of the third party" in text or "terminate the interest" in text)
        return "DOI" if (has_int_term and not has_pol_term) else "CAN"

    # ==========================================================
    # PRIORITY 2: DELETION OF INTEREST (DOI)
    # ==========================================================
    doi_keywords = (
        "deletion of interest", "interest removed", "third party interest removed", "mortgage deleted", "mortgage removed", "terminate the interest of the third party",
        "interest is hereby removed", "interest has been removed", "loan has been satisfied", "you no longer have an interest", "no longer have an interest in the",
        "removed all indications of your interest", "mortgagee interest removed", "mir-mortgagee interest removed", "mir - mortgagee interest removed",
        "mir mortgagee interest removed", "cancel reason mir", "interest removal", "interest deleted", "remove interest", "interest termination", "interest terminated",
        "deleted as loss payee", "removed as loss payee", "loss payee deleted", "loss payee removed", "loss payee has been deleted", "loss payee has been removed"
    )
    doi_signals = any(k in text for k in doi_keywords) or bool(re.search(r"mir[\s\-]*mortgagee\s+interest\s+removed", text)) or bool(re.search(r"cancel\s*reason[:\s]*mir", text))
    
    if doi_signals:
        doi_guard = any(r in text for r in ("policy declarations", "mortgagee declarations summary")) or bool(re.search(r"\bcoverage a\b", text))
        if not doi_guard: return "DOI"

    # ==========================================================
    # PRIORITY 3: CANCELLATION (CAN)
    # ==========================================================
    can_keywords = (
        "notice of cancellation", "cancellation notice", "policy cancellation", "flood policy cancellation", "is cancelled", "is being cancelled",
        "has been cancelled", "will be cancelled", "cancelled effective", "cancellation effective", "policy is cancelled", "policy cancelled",
        "void date", "cease date", "cancellation date", "notice of non-renewal", "non-renewal date", "non-renewal notice", "will be non-renewed",
        "will not be renewed", "nonrenewal notice", "notice of nonrenewal", "policy change/cancellation notice", "reason cancellation",
        "doc type - cancellation", "reason: cancellation", "reason cancellation customer", "cancellation customer initiated",
        "reason: cancellation customer initiated", "xlc-s11 doc type - cancellation", "doc type cancellation", "nlc-s11 doc type - cancellation",
        "cancel reason", "for all cancellation"
    )
    if any(k in text for k in can_keywords) or ("insurance coverage notification" in text and "cancellation" in text):
        is_lexisnexis_can = "insurance coverage notification" in text and "cancellation" in text
        
        # Payment Notice Guard (treat as INV)
        payment_stubs = (
            "return this portion with your payment", "amount enclosed", "make check or money order", "make check payable", "make checks payable",
            "minimum amount due", "minimum premium amount due", "remit to", "payment by check", "pay by phone", "check-by-phone", "payment due date",
            "total amount due", "payment options", "account statement", "premium balance", "invoice number", "detach and return", "please detach",
            "amount due", "pay online", "if payment is not received", "if you have already made your payment"
        )
        is_pay_notice = (any(x in text for x in ("non-payment of premium", "non-payment", "nonpayment of premium", "nonpayment")) and 
                         sum(1 for k in payment_stubs if k in text) >= 2)

        # Declarations/Certificates Guard
        dec_guard_patterns = (r"\bdeclarations?\b", r"\bpolicy declarations\b", r"\bmortgagee declarations\b", r"\bpolicy change declarations\b", 
                              r"\bcoverage a\b", r"\bcoverage b\b", r"\bcoverage c\b", r"\bcoverage d\b", r"\bcoverage e\b", r"\bcoverage f\b")
        has_dec_w_cov = any(re.search(r"\bdeclarations?\b", text) for _ in [1]) and any(k in text for k in ("section i", "section ii", "property coverages", "liability coverages", "total premium", "policy forms and endorsements", "homesaver policy"))
        has_cov_boilerplate = (sum(1 for cov in ("a.dwelling", "b.other structures", "c.personal property", "d.loss of use", "e.personal liability", "f.medical payments") if cov in text) >= 3 
                               and any(k in text for k in ("if the policy is cancelled or not renewed", "advance notice of cancellation", "notice of cancellation we give our insured")))
        
        if is_pay_notice: pass # Fallthrough to INV
        elif not is_lexisnexis_can and (any(re.search(p, text) for p in dec_guard_patterns) or has_dec_w_cov or "mortgagee certificate" in text or has_cov_boilerplate): pass
        else: return "CAN"

    # ==========================================================
    # PRIORITY 4: REINSTATEMENT (RNS)
    # ==========================================================
    if any(k in text for k in ("reinstatement", "rescission of cancellation", "policy reinstated", "rescind cancellation", "withdrawal of cancellation")):
        rns_is_label = "reinstatement date" in text and not any(k in text for k in ("policy reinstated", "rescission of cancellation", "rescind cancellation", "withdrawal of cancellation", "your policy has been reinstated", "hereby reinstated"))
        rns_in_dec = any(k in text for k in ("renewal flood insurance", "flood insurance policy declarations", "policy declarations", "renewal notice", "declarations page", "agent issued declarations", "flood policy declarations", "total premium paid", "property location:", "premium summary", "coverage detail"))
        if not rns_is_label and not rns_in_dec: return "RNS"

    # ==========================================================
    # PRIORITY 6: EDI / LEXISNEXIS LOGIC
    # ==========================================================
    if any(k in text for k in ("edi image", "electronic data interchange", "electronic image generated for edi", "electronic image generated", "generated for edi", "edi data")):
        if any(k in text for k in ("interest removed", "mortgagee interest removed", "mir-mortgagee", "mir mortgagee")) or bool(re.search(r"mir[\s\-]*mortgagee", text)): return "DOI"
        if any(k in text for k in ("cancellation", "cancel reason", "cancelled")): return "CAN"
        if any(k in text for k in ("doc type - renewal", "doc type renewal", "transaction desc: renewal", "transaction dese: renewal", "renewal policy", "rnw-s11", "rnw-811", "rwl-s11", "rwl-811")) or bool(re.search(r"doc\s*type.*renewal", text)): return "RNW"
        return "OTH"
    
    if "insurance coverage notification" in text or "lexisnexis" in text:
        if any(k in text for k in ("reason cancellation", "cancellation customer", "doc type - cancellation", "doc type cancellation", "cancellation", "cancelled", "cancel date", "cancel reason")): pass
        elif any(k in text for k in ("interest removed", "mir-mortgagee", "mir mortgagee")): pass # Handled above
        else: return "OTH"

    # ==========================================================
    # PRIORITY 7a: MORTGAGE DEC SUMMARY -> RNW
    # ==========================================================
    if any(k in text for k in ("mortgagee dec summary", "mortgagee declarations summary", "mortgage dec summary")): return "RNW"

    # ==========================================================
    # PRIORITY 7: INVOICE (INV)
    # ==========================================================
    inv_signals = any(k in text for k in (
        "policy bill", "homeowners policy bill", "renewal premium bill", "invoice", "amount due", "balance due", "minimum due", "pay in full", "premium notice",
        "remit to", "make check payable", "make checks payable", "make check or money order", "amount enclosed", "to pay in full amount due", "balance (to pay in full)",
        "return this portion with your payment", "account statement", "payment due date", "total amount due", "invoice number", "billing statement", "premium statement"
    ))
    if inv_signals:
        is_policy_bill = any(k in text for k in ("policy bill", "premium bill", "premium statement"))
        inv_guard_keys = (
            "policy declarations", "declaration page", "declarations page", "mortgagee declarations", "agent issued declarations", "coverage a dwelling",
            "coverage b other", "coverage c personal", "coverage d loss", "this is not an invoice", "not an invoice/bill", "insurance coverage notification",
            "premium notice state farm", "homeowners policy declarations", "homeowner policy declarations", "dwelling (coverage a)", "dwelling coverage a",
            "limit of liability", "forms & endorsements", "forms and endorsements", "location of premises", "mortgagee copy", "declaration page is attached",
            "cert. #", "coverage forms", "total due", "premium must be received by"
        )
        inv_guard = not is_policy_bill and (any(g in text for g in inv_guard_keys) or 
                    ("declarations" in text and re.search(r"\bcoverage a\b", text)) or 
                    ("declarations" in text and "premium" in text and "policy" in text and "bill" not in text and "statement" not in text) or 
                    ("premium notice" in text and "declarations" in text))
        if not inv_guard: return "INV"

    # ==========================================================
    # PRIORITY 8: RENEWAL / DECLARATIONS (RNW)
    # ==========================================================
    if "declaration" in text and any(cov in text for cov in ("coverage a", "coverage b", "coverage c", "coverage d", "coverage e", "coverage f")): return "RNW"

    rnw_keywords = (
        "policy declarations", "declarations page", "policy declaration", "declaration page", "mortgagee declarations summary", "policy summary",
        "coverage a dwelling", "coverage b other structures", "coverage c personal property", "coverage d loss of use", "coverage e personal liability",
        "coverage f medical payments", "coverage and limits of liability", "dwelling policy", "dwelling fire policy", "dwelling fire policy number",
        "loss payee, mortgagee or other interest", "a. dwelling", "dwelling amount", "dwelling limit", "all other peril deductible", "wind and hail deductible",
        "deductible", "total policy premium", "annual premium", "premium summary", "total premium this location", "total premium all locations",
        "policy period", "effective date", "expiration date", "term start", "term end", "policy change", "amended declarations", "revised declarations",
        "transaction effective date", "renewal notice", "this is your renewal", "renewal flood insurance", "flood insurance policy declarations",
        "renewal billing payor", "agent issued declarations", "premium notice state farm", "pol. from:", "pol. to:", "prop. loc:", "prop. loc", "carrier:",
        "eff. date:", "policy coverages", "coverage detail", "dwelling #1", "dwelling #1:", "named insured(s)", "named insured(s):", "lienholder",
        "loan/contract number", "additional interests", "additional named insureds", "declaration page is attached", "cert. #", "coverages - insurance is effective with",
        "effective from", "mortgagee(s)", "progressive", "policy type:", "insured and policy information", "mortgagee dec summary"
    )
    if any(k in text for k in rnw_keywords): return "RNW"

    # ==========================================================
    # PRIORITY 9: CERTIFICATE OF INSURANCE (COI)
    # ==========================================================
    if any(k in text for k in ("certificate of insurance", "this certifies that", "acord", "certificate holder")):
        coi_override = any(r in text for r in (
            "policy declarations", "declarations page", "policy declaration", "declaration page", "mortgagee declarations summary", "policy summary",
            "coverage a", "coverage b", "coverage c", "coverage d", "coverage e", "coverage f", "dwelling", "policy period", "effective date", "expiration date",
            "renewal", "renewed", "interest removed", "deletion of interest", "mortgage deleted", "mortgage removed", "master policy", "unit owner",
            "condominium unit", "coverage amount", "certificate period", "policy inception date", "coverage summary", "general liability insurance",
            "property insurance", "deductible"
        ))
        if not coi_override: return "COI"

    # ==========================================================
    # PRIORITY 11: BINDER (BIN) & DEFAULT
    # ==========================================================
    if any(k in text for k in ("binder without policy number", "quote without policy number", "binder issued", "temporary coverage")): return "BIN"
    
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