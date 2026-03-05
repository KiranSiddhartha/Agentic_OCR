"""
Stage 2 — Semantic Gap Filler  (SC + TE)
=========================================
Comprehensive rule-based extraction covering ALL carrier layouts:
  Allstate, AAA/CSAA, Erie, Nationwide/Allied, Encompass,
  Safeco, Farmers/NFIP, Wind/Specialty, Aegis, and more.

Supported fields (15):
  carrier_name, policy_number, insured_name, effective_date,
  expiration_date, property_address, mailing_address,
  mortgage_company, loan_number, total_premium,
  balance_due, issue_date, remit_info,
  cancellation_date, cancellation_reason
"""

from typing import List, Dict, Optional
import re


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def extract_with_ner(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    if not lines or not missing_fields:
        return {}
    rule_based = _extract_with_rules(lines, missing_fields)
    if len(rule_based) >= len(missing_fields):
        return rule_based
    still_missing = [f for f in missing_fields if f not in rule_based]
    if still_missing:
        ai_results = _extract_with_gliner_safe("\n".join(lines), still_missing)
        for field, data in ai_results.items():
            if field not in rule_based:
                rule_based[field] = data
    return rule_based


# ============================================================
# LABEL PATTERNS — all known OCR variations per field
# ============================================================

# Each entry: (regex, mode)
# Modes: inline, next, inline_or_next, date_inline, dollar_inline, address_block

_POLICY_NUMBER_LABELS = [
    (r"(?i)(?:dwelling\s+(?:fire\s+)?)?policy\s*(?:number|no\.?|#|num)\.?\s*:?", "inline_or_next"),
    (r"(?i)^policy\s*:", "inline"),
    (r"(?i)nfip\s+policy\s*(?:number|no\.?|#)\.?\s*:", "inline"),
    # Nationwide: "DWELLING FIRE POLICY NUMBER" followed by "DPC 0076173896-1"
    (r"(?i)dwelling\s+fire\s+policy\s+number\s*:?", "inline_or_next"),
    # Nationwide/AMCO: "POLICY NO.:" (period after NO before colon)
    (r"(?i)policy\s+no\.\s*:", "inline_or_next"),
]
_POLICY_NUMBER_SKIP = re.compile(
    r"(?i)(?:write|please|include|allow|change\s+request|refer\s+to|"
    r"contact|do\s+not|five\s+days)")

_INSURED_NAME_LABELS = [
    (r"(?i)(?:named\s+)?insured\s*(?:name)?\s*:", "inline_or_next"),
    (r"(?i)insured\s+(?:name\s+and\s+)?mailing\s+(?:name\s+and\s+)?address\s*:", "next"),
    (r"(?i)policyholder(?:\s*/\s*named\s+insured)?(?:\(s\))?\s*:?", "inline_or_next"),
    (r"(?i)^INSURED$", "next"),
    (r"(?i)name\s+of\s+insured\s*:?\s+", "inline_or_next"),
    # DOI-specific: "Name and address of Insured:" → next line is name
    (r"(?i)name\s+and\s+address\s+of\s+(?:the\s+)?insured\s*:", "next"),
    # DOI: "Primary Name:" (EDI format)
    (r"(?i)primary\s+name\s*:", "inline_or_next"),
    # DOI: "Customer Name:" (various formats)
    (r"(?i)customer\s+name\s*:", "inline_or_next"),
]
_INSURED_NAME_SKIP = re.compile(r"(?i)property\s+insured|payor\s*[:\.]")

_CARRIER_WORDS = ("insurance", "indemnity", "casualty", "underwriters",
                  "surety", "assurance", "ins")
_CARRIER_ENTITY = ("company", "co", "co.", "exchange", "group", "mutual",
                   "corp", "corporation")
_CARRIER_SKIP = ("agency", "agent", "services", "broker", "producer",
                 "processing", "center", "relations", "mortgage")

_EFF_DATE_LABELS = [
    (r"(?i)policy\s+effective\s+date\s*:", "date"),
    (r"(?i)eff(?:ective)?\.?\s*date\s*:", "date"),
    (r"(?i)effective\s+(?=\w)", "date"),
    (r"(?i)policy\s+(?:period|term)\s*:", "date"),
    (r"(?i)pol\.?\s*from\s*:", "date"),
    (r"(?i)^from\s*:", "date"),
    (r"(?i)inception\s+date\s*:", "date"),
    (r"(?i)coverage\s+effective\s*:", "date"),
    # Date range line: "NOV 09 2021 to NOV 09 2022" — pick first date
    (r"(?i)(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\s+to\s+", "date_range_start"),
    # Encompass: "Beginning July 1, 2020"
    (r"(?i)beginning\s+", "date"),
    # AAA: "Effective September 09, 2020"
    (r"(?i)effective\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)", "date"),
]

_EXP_DATE_LABELS = [
    (r"(?i)policy\s+expiration\s+date\s*:", "date"),
    (r"(?i)expir(?:ation|es|ing)?\s*(?:date)?\s*:", "date"),
    (r"(?i)pol\.?\s*to\s*:", "date"),
    (r"(?i)^to\s*:", "date"),
    # Nationwide/Allied: "From: MM/DD/YYYY To: MM/DD/YYYY" — extract after "To:"
    (r"(?i)\bTo\s*:\s*", "date"),
    (r"(?i)through\s+", "date"),
    # Date range line: pick the second date after "to"
    (r"(?i)\bto\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b", "date_range_end"),
    # Encompass: "through July 1, 2021"
    (r"(?i)through\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)", "date"),
]

_PROP_ADDR_LABELS = [
    (r"(?i)property\s+address\s*:", "addr"),
    (r"(?i)property\s+location\s*:", "addr"),
    (r"(?i)location\s+of\s+insured\s+property", "addr"),
    (r"(?i)prop\.?\s*loc(?:ation)?\.?\s*:", "inline"),
    (r"(?i)covered\s+property\s*:?", "addr"),
    (r"(?i)^address\s*:", "addr"),
    (r"(?i)risk\s+location\s*:", "addr"),
    (r"(?i)location\s+of\s+property\s*:?", "addr"),
    (r"(?i)^location\s*:", "inline"),  # State Farm: "Location: 2971 GA HIGHWAY 93 S"
    # Encompass: "Coverage Detail for 136 Old Altamont Ridge Rd,Greenville,SC 29609"
    (r"(?i)coverage\s+detail\s+for\s+", "inline"),
    # Nationwide: "DESCRIPTION OF PROPERTY:"
    (r"(?i)description\s+of\s+property\s*:", "addr"),
    # Generic: "Location of Insured Property"
    (r"(?i)location\s+of\s+insured\s+property\s*:", "addr"),
    # AAA: "Location of Insured Property"
    (r"(?i)location\s+of\s+insured\s+property", "addr"),
    # Nationwide: "Described Location:" 
    (r"(?i)described\s+location\s*:", "addr"),
    # Adirondack: "LOCATED AT:"
    (r"(?i)located\s+at\s*:", "addr"),
]

_MAIL_ADDR_LABELS = [
    (r"(?i)insured\s+mailing\s+address\s*:", "addr"),
    (r"(?i)mailing\s+address\s*:", "addr"),
    (r"(?i)named\s+insured\s+and\s+mailing\s+address", "addr"),
    (r"(?i)insured\s+(?:mailing\s+)?name\s+and\s+(?:mailing\s+)?address\s*:", "addr"),
]

_MORTGAGE_LABELS = [
    (r"(?i)(?:first|1st)\s*(?:mortgage|mortgagee)\s*:", "inline_or_next"),
    (r"(?i)mortgagee\s+(?:full\s+)?name\s*:", "inline_or_next"),
    (r"(?i)first\s+mortgage\s*:", "inline_or_next"),
    (r"(?i)mortgage(?:e)?(?:\s*/\s*add\.?\s*party)?\s*:", "inline"),
    (r"(?i)(?:^|\b)loss\s+payee\s*:", "next"),
    (r"(?i)mortgagee\s+(?:wailing|mailing)\s+name\s+and\s+address\s*:", "next"),
    (r"(?i)^holder\s*:", "inline_or_next"),  # State Farm: "holder: CAPITAL CITY BANK"
    # --- INS observation batch additions (Section 4) ---
    (r"(?i)mortgage\s*\(s\)\s*:", "inline_or_next"),
    (r"(?i)mortgage\s+holder\s*:", "inline_or_next"),
    (r"(?i)additional\s+interest\s*\(s?\)\s*:", "inline_or_next"),
    (r"(?i)other\s+interests?\s*:", "inline_or_next"),
    (r"(?i)mortgage\s+servicing\s+agency\s*:", "inline_or_next"),
    (r"(?i)lien\s*holder\s*:", "inline_or_next"),
    (r"(?i)unit\s+owner\s+mortgagee\s*:", "inline_or_next"),
    (r"(?i)second\s+mortgage\s*:", "inline_or_next"),
    (r"(?i)(?:2nd)\s+mortgage\s*:", "inline_or_next"),
    (r"(?i)mortgage\s+or\s+interested\s+party\s*:", "inline_or_next"),
    (r"(?i)additional\s+interest/mortgage/trust\s*:", "inline_or_next"),
    (r"(?i)mortgagee/loss\s+payee\s*:", "inline_or_next"),
    (r"(?i)mortgage\s+clause\s*:", "inline_or_next"),
]

_LOAN_LABELS = [
    (r"(?i)loan\s*(?:number|no|#|num|id)\s*:?", "inline_or_next"),
    (r"(?i)loan#\s*:?", "inline"),
    # --- INS observation batch additions (Section 3) ---
    (r"(?i)loan/contract\s*(?:number|#)\s*:?", "inline_or_next"),
    (r"(?i)mortgage\s+loan\s*no\.?\s*:?", "inline_or_next"),
    (r"(?i)loan\s+no\.\s*:?", "inline_or_next"),
    (r"(?i)^loan\s*:", "inline"),
]

_PREMIUM_LABELS = [
    (r"(?i)annual\s+premium\s*:", "dollar"),
    (r"(?i)total\s+(?:policy\s+)?premium\s*:?", "dollar"),
    (r"(?i)total\s+premium\s+paid\s*:", "dollar"),
    (r"(?i)base\s+policy\s+premium\s*:", "dollar"),
    (r"(?i)premium\s+balance\s*:?", "dollar"),
    # Encompass: "Total Residence Premium"
    (r"(?i)total\s+residence\s+premium\s*:?", "dollar"),
    # Adirondack mortgagee certificate: "Mortgagee Premium"
    (r"(?i)mortgagee\s+premium\s*:?", "dollar"),
    # AAA: "Total Premium:"
    (r"(?i)total\s+premium\s*:", "dollar"),
    # Invoice/Declaration: "TOTAL DUE $ 5,421.05"
    (r"(?i)total\s+due\s*:?", "dollar"),
]

_BALANCE_LABELS = [
    (r"(?i)balance\s*\(?\s*(?:to\s+pay|due)", "dollar"),
    (r"(?i)to\s+pay\s+in\s+full(?:\s+amount\s+due)?", "dollar"),
    (r"(?i)(?:amount|balance)\s+due\s*:", "dollar"),
    (r"(?i)full\s+payment\s*", "dollar"),
    (r"(?i)current\s+balance\s+due\s*:?", "dollar"),
    (r"(?i)total\s+balance\s*:?", "dollar"),
    (r"(?i)(?:amount|balance)\s+due\s+(?:no\s+later|by)", "dollar"),
    (r"(?i)minimum\s+(?:amount\s+)?due\s+no\s+later", "dollar"),
    (r"(?i)total\s+amount\s+due\s*:?", "dollar"),
]
_BALANCE_SKIP = re.compile(r"(?i)(?:includes|past\s+due\s+amount)")

_ISSUE_DATE_LABELS = [
    (r"(?i)bill\s*date\s*:", "date"),
    (r"(?i)(?:issue|invoice|statement)\s*date\s*:", "date"),
    (r"(?i)information\s+as\s+of", "date"),
    (r"(?i)document\s+produced\s*:", "date"),
    (r"(?i)processed\s+on\s*:", "date"),
    (r"(?i)statement\s+date\s*:", "date"),
    (r"(?i)billing\s+date\s*:", "date"),
    (r"(?i)due\s+date\s*:", "date"),
]

_REMIT_LABELS = [
    (r"(?i)(?:mail|remit|send\s+payment)\s+to\s*:", "inline"),
    (r"(?i)payable\s+to\s+", "inline"),
    (r"(?i)make\s+checks?\s+payable\s+to\s*:?", "inline"),
    (r"(?i)return\s+payment\s+to\s*:", "inline"),
]

_CANCEL_DATE_LABELS = [
    (r"(?i)cancellation\s*date\s*:", "date"),
    (r"(?i)cancel(?:led)?\s+(?:effective\s+)?date\s*:", "date"),
    (r"(?i)date\s+of\s+cancellation\s*:", "date"),
    (r"(?i)termination\s+date\s*:", "date"),
    (r"(?i)policy\s+cancellation\s+date\s+is\s*:", "date"),
    (r"(?i)cancellation\s+effective\s*:?", "date"),
    (r"(?i)non-?renewal\s+date\s*(?:and\s+time)?\s*:", "date"),
    (r"(?i)terminate\s+this\s+policy\s+effective\s*:", "date"),
]

_CANCEL_REASON_LABELS = [
    (r"(?i)(?:reason\s+for\s+)?cancellation\s+reason\s*:", "inline"),
    (r"(?i)reason\s+for\s+(?:cancellation|termination)\s*:", "inline"),
    (r"(?i)cancel\s+reason\s*:", "inline"),
    (r"(?i)reason\s*:", "inline"),
    (r"(?i)REASON\s+", "inline"),
]


# ============================================================
# SC — MAIN EXTRACTION LOOP
# ============================================================

def _extract_with_rules(
    lines: List[str],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}

    for idx, line in enumerate(lines):
        if len(out) >= len(missing_fields):
            break
        ll = line.lower().strip()
        if not ll:
            continue
        nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
        nxt2 = lines[idx + 2].strip() if idx + 2 < len(lines) else ""

        # --- POLICY NUMBER ---
        if "policy_number" in missing_fields and "policy_number" not in out:
            if not _POLICY_NUMBER_SKIP.search(line):
                val = _try_labels(line, nxt, _POLICY_NUMBER_LABELS, nxt2)
                if val:
                    # Take policy number portion (stop at REASON, text labels, etc.)
                    first = re.match(r'^([A-Z0-9\-]+(?:\s+\d+)*)', val.strip(), re.I)
                    if first:
                        clean = _clean_policy(first.group(1))
                    else:
                        clean = _clean_policy(val)
                    if _valid_policy_number(clean):
                        out["policy_number"] = _r(clean, "sc_policy", 0.85)

        # --- INSURED NAME ---
        if "insured_name" in missing_fields and "insured_name" not in out:
            if not _INSURED_NAME_SKIP.search(line):
                val = _try_labels(line, nxt, _INSURED_NAME_LABELS, nxt2)
                if val:
                    # CRITICAL FIX: Handle split-line names like "Named Insured: YOKO\nMATSUMOTO"
                    # When inline value is a single word (partial name), combine with next line
                    val_stripped = val.strip()
                    val_words = val_stripped.split()
                    if len(val_words) == 1 and val_stripped.replace(",", "").isalpha():
                        # Single word name — likely split across lines
                        # Check if next line is a continuation (also a single uppercase name word)
                        if nxt and nxt.strip():
                            nxt_stripped = nxt.strip()
                            nxt_words = nxt_stripped.split()
                            # Combine if next line looks like a name part (1-3 words, alphabetic, not a label)
                            if (1 <= len(nxt_words) <= 3
                                and all(w.replace(",", "").replace(".", "").isalpha() for w in nxt_words)
                                and not any(b in nxt_stripped.lower() for b in (
                                    "policy", "number", "period", "effective", "date",
                                    "address", "coverage", "premium", "mortgage",
                                    "page", "continued", "section"))):
                                val = val_stripped + " " + nxt_stripped
                    # Truncate at address patterns (digit + street name)
                    addr_m = re.search(r'\s+\d+\s+\w+\s+(?:st|street|ave|'
                                       r'avenue|rd|road|blvd|dr|drive|ln|'
                                       r'lane|ct|cir|way|loop)\b', val, re.I)
                    if addr_m:
                        val = val[:addr_m.start()].strip()
                    # Truncate at standalone digit blocks (address start)
                    addr_m2 = re.search(r'\s+\d{2,}\s+[A-Z]', val)
                    if addr_m2 and len(val[:addr_m2.start()].split()) >= 2:
                        val = val[:addr_m2.start()].strip()
                    # Normalize OCR mixed-case corruption: "GIlLIS, DaVId" → "GILLIS, DAVID"
                    if re.search(r'[A-Z][a-z][A-Z]', val) or re.search(r'[a-z][A-Z]', val):
                        val = val.upper()
                    # CRITICAL: Strip garbled label prefixes from name values
                    # E.g., "NANEAND ADDRESO OCTHEINSURED Dashiell Lopez" → strip prefix
                    garbled_pats = [
                        r"(?i)^.*?(?:NAMEAND|NANEAND|ADDRESO|OCTHE|OFTHE)(?:INSURED|INSUREO|LNSURED)?\s*",
                        r"(?i)^.*?(?:INSUREDNAME|INSUREONAME|INSUREDMAILING)\s*",
                    ]
                    for gpat in garbled_pats:
                        gm = re.match(gpat, val)
                        if gm and gm.end() < len(val):
                            remainder = val[gm.end():].strip()
                            if remainder and len(remainder) > 3:
                                val = remainder
                                break
                    if _valid_name(val):
                        out["insured_name"] = _r(
                            _clean_isaoa(val), "sc_insured", 0.82)

        # --- CARRIER NAME (labeled: "Carrier: XXX", "policy provided by\nXXX") ---
        if "carrier_name" in missing_fields and "carrier_name" not in out:
            m = re.search(r'(?i)carrier\s*:', line)
            if m:
                val = line[m.end():].strip()
                if val and len(val) > 3:
                    out["carrier_name"] = _r(val, "sc_carrier_label", 0.85)
            elif re.search(r'(?i)(?:policy|insurance)\s+provided\s+by', ll):
                if nxt and len(nxt) > 3 and len(nxt) < 80:
                    # Try to merge multi-line carrier name
                    carrier_val = nxt.strip()
                    if nxt2 and len(nxt2) < 60 and any(
                        w in nxt2.lower() for w in (
                            "insurance", "company", "co.", "corp",
                            "indemnity", "casualty", "mutual",
                        )):
                        carrier_val = carrier_val + " " + nxt2.strip()
                    out["carrier_name"] = _r(carrier_val, "sc_carrier_provided", 0.82)
            # DOI: "Carrier Cd-Name:" (EDI format)
            elif re.search(r'(?i)carrier\s+cd[\-\s]*name\s*:', ll):
                val = re.split(r'(?i)carrier\s+cd[\-\s]*name\s*:', line, maxsplit=1)
                if len(val) > 1 and val[1].strip():
                    out["carrier_name"] = _r(val[1].strip(), "sc_carrier_edi", 0.82)

        # --- EFFECTIVE DATE ---
        if "effective_date" in missing_fields and "effective_date" not in out:
            val = _try_date_labels(line, _EFF_DATE_LABELS)
            if val:
                out["effective_date"] = _r(val, "sc_eff_date", 0.85)

        # --- EXPIRATION DATE ---
        if "expiration_date" in missing_fields and "expiration_date" not in out:
            val = _try_date_labels(line, _EXP_DATE_LABELS)
            if val:
                out["expiration_date"] = _r(val, "sc_exp_date", 0.85)

        # --- PROPERTY ADDRESS ---
        if "property_address" in missing_fields and "property_address" not in out:
            val = _try_addr_labels(line, nxt, nxt2, lines, idx,
                                   _PROP_ADDR_LABELS)
            if val:
                out["property_address"] = _r(val, "sc_prop_addr", 0.78)

        # --- MAILING ADDRESS ---
        if "mailing_address" in missing_fields and "mailing_address" not in out:
            val = _try_addr_labels(line, nxt, nxt2, lines, idx,
                                   _MAIL_ADDR_LABELS)
            if val:
                out["mailing_address"] = _r(val, "sc_mail_addr", 0.78)

        # --- MORTGAGE COMPANY ---
        if "mortgage_company" in missing_fields and "mortgage_company" not in out:
            val = _try_labels(line, nxt, _MORTGAGE_LABELS, nxt2)
            if val and len(val) > 3:
                out["mortgage_company"] = _r(
                    _clean_isaoa(val), "sc_mortgage", 0.80)

        # --- LOAN NUMBER ---
        if "loan_number" in missing_fields and "loan_number" not in out:
            val = _try_labels(line, nxt, _LOAN_LABELS, nxt2)
            if val:
                # CRITICAL: If the value came from the next line (no digits on label line),
                # verify it actually looks like a loan number candidate (must have digits)
                val_digits = sum(c.isdigit() for c in val)
                if val_digits < 3:
                    val = None  # Reject non-numeric next-line values like "Type of Interest"
            if val:
                clean = re.sub(r'[^0-9A-Za-z]', '', val)
                if _valid_loan_number(clean):
                    out["loan_number"] = _r(clean, "sc_loan", 0.82)

        # --- TOTAL PREMIUM ---
        if "total_premium" in missing_fields and "total_premium" not in out:
            val = _try_dollar_labels(line, _PREMIUM_LABELS)
            if val:
                out["total_premium"] = _r(val, "sc_premium", 0.83)

        # --- BALANCE DUE ---
        if "balance_due" in missing_fields and "balance_due" not in out:
            if not _BALANCE_SKIP.search(line):
                val = _try_dollar_labels(line, _BALANCE_LABELS)
                if val:
                    out["balance_due"] = _r(val, "sc_balance", 0.83)

        # --- ISSUE DATE ---
        if "issue_date" in missing_fields and "issue_date" not in out:
            val = _try_date_labels(line, _ISSUE_DATE_LABELS)
            if val:
                out["issue_date"] = _r(val, "sc_issue_date", 0.83)

        # --- REMIT INFO ---
        if "remit_info" in missing_fields and "remit_info" not in out:
            val = _try_remit(line)
            if val:
                out["remit_info"] = _r(val, "sc_remit", 0.80)

        # --- CANCELLATION DATE ---
        if "cancellation_date" in missing_fields and "cancellation_date" not in out:
            val = _try_date_labels(line, _CANCEL_DATE_LABELS)
            if val:
                out["cancellation_date"] = _r(val, "sc_cancel_date", 0.85)

        # --- CANCELLATION REASON ---
        if "cancellation_reason" in missing_fields and "cancellation_reason" not in out:
            val = _try_labels(line, nxt, _CANCEL_REASON_LABELS)
            if val and len(val) > 3:
                out["cancellation_reason"] = _r(val, "sc_cancel_reason", 0.82)

    # ---- POST-LOOP: Custom handlers for complex patterns ----

    if "carrier_name" in missing_fields and "carrier_name" not in out:
        val = _extract_carrier_keyword(lines)
        if val:
            out["carrier_name"] = val

    if "expiration_date" in missing_fields and "expiration_date" not in out:
        val = _extract_exp_from_period(lines)
        if val:
            out["expiration_date"] = val

    if "mortgage_company" in missing_fields and "mortgage_company" not in out:
        val = _extract_mortgage_isaoa(lines)
        if val:
            out["mortgage_company"] = val

    if "cancellation_reason" in missing_fields and "cancellation_reason" not in out:
        val = _extract_cancel_reason_kw(lines)
        if val:
            out["cancellation_reason"] = val

    if "remit_info" in missing_fields and "remit_info" not in out:
        val = _extract_remit_fuzzy(lines)
        if val:
            out["remit_info"] = val

    # ---- Total Premium: table format (label on one line, dollar on next) ----
    if "total_premium" in missing_fields and "total_premium" not in out:
        val = _extract_total_premium_table(lines)
        if val:
            out["total_premium"] = val

    # ---- Mortgage Company from "Other Interests" table (AAA format) ----
    if "mortgage_company" in missing_fields and "mortgage_company" not in out:
        val = _extract_mortgage_from_interests_table(lines)
        if val:
            out["mortgage_company"] = val

    # ---- Loan Number from "Other Interests" table (AAA format) ----
    if "loan_number" in missing_fields and "loan_number" not in out:
        val = _extract_loan_from_interests_table(lines)
        if val:
            out["loan_number"] = val

    # ---- Property address from "Coverage Detail for XXX" inline (Encompass) ----
    if "property_address" in missing_fields and "property_address" not in out:
        val = _extract_property_from_coverage_detail(lines)
        if val:
            out["property_address"] = val

    # ---- Property address from "LOCATED AT:" or "DESCRIPTION OF PROPERTY:" (Adirondack/Nationwide) ----
    if "property_address" in missing_fields and "property_address" not in out:
        val = _extract_property_from_located_at(lines)
        if val:
            out["property_address"] = val

    # ---- DOI-specific: extract insured name + address from "Name and address of Insured:" ----
    if ("insured_name" in missing_fields and "insured_name" not in out) or \
       ("property_address" in missing_fields and "property_address" not in out):
        _extract_doi_name_address(lines, missing_fields, out)
    # Also try if property_address still missing (insured_name may have been found by main loop)
    if "property_address" in missing_fields and "property_address" not in out:
        _extract_doi_name_address(lines, ["property_address"], out)

    # ---- DOI/Policy Change: property address from insured header block ----
    # For Policy Change docs the insured address appears in a header block:
    #   Bradley R Hanson          (name)
    #   42 Equestrian Way         (street)
    #   Hawthorn Woods IL 60047   (city/state/zip)
    # We detect it by finding a name-looking line followed by address lines,
    # appearing BEFORE "Policy Information" / "Policy number" section headers.
    if "property_address" in missing_fields and "property_address" not in out:
        _extract_property_from_insured_header(lines, out)

    # ---- Column-header format: "Policy number" header + values 2 lines below ----
    if "policy_number" in missing_fields and "policy_number" not in out:
        _extract_column_policy_number(lines, out)

    # ---- Orphaned value scanner: two-column OCR splits label from value ----
    # When OCR outputs left-column lines then right-column lines, a label like
    # "POLICY NO.:" may appear alone (no value) and the value "ADP 0038122530 7"
    # appears later as a standalone line.  Scan for the classic Nationwide/AMCO
    # format: "ADP    XXXXXXXXXX    N" on its own line after a policy label.
    if "policy_number" in missing_fields and "policy_number" not in out:
        _extract_orphaned_policy_value(lines, out)

    if "loan_number" in missing_fields and "loan_number" not in out:
        _extract_orphaned_loan_value(lines, out)

    # ---- "Named insured" column header ----
    if "insured_name" in missing_fields and "insured_name" not in out:
        _extract_column_named_insured(lines, out)

    # ---- "Loan number" column/labeled pattern ----
    if "loan_number" in missing_fields and "loan_number" not in out:
        _extract_doi_loan_number(lines, out)

    return out


# ============================================================
# PATTERN MATCHING HELPERS
# ============================================================

def _r(value: str, source: str, conf: float) -> Dict:
    return {"value": value, "confidence": conf, "source": source}


def _try_labels(line: str, nxt: str, labels: list, nxt2: str = "") -> Optional[str]:
    """Try label patterns, return value or None."""
    for pat, mode in labels:
        m = re.search(pat, line)
        if not m:
            continue
        if mode == "inline":
            val = _after_match(line, m)
            if val:
                return val
        elif mode == "next":
            return nxt if nxt else None
        elif mode == "inline_or_next":
            val = _after_match(line, m)
            if val and len(val.strip()) >= 3:
                return val
            # Also try next line if inline value is empty or too short
            if nxt and len(nxt.strip()) >= 2:
                return nxt
            # Also try nxt2 — handles two-column OCR where values are
            # separated from labels by one blank or interleaved line
            if nxt2 and len(nxt2.strip()) >= 2:
                return nxt2
    return None


def _try_date_labels(line: str, labels: list) -> Optional[str]:
    """Try label patterns for date extraction."""
    for pat, _ in labels:
        m = re.search(pat, line)
        if not m:
            continue
        # Search for date after the match position
        d = _extract_date(line[m.start():])
        if d:
            return d
        d = _extract_date(line)
        if d:
            return d
    return None


def _try_dollar_labels(line: str, labels: list) -> Optional[str]:
    """Try label patterns for dollar amount extraction."""
    for pat, _ in labels:
        m = re.search(pat, line)
        if not m:
            continue
        after = line[m.end():]
        # First: look for explicit $ sign
        dm = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', after)
        if dm:
            return "$" + dm.group(1).replace(",", "")
        # Fallback: look for $ anywhere on line
        dm = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', line)
        if dm:
            return "$" + dm.group(1).replace(",", "")
        # Last resort: bare number directly after label (no date-like patterns)
        dm = re.search(r'(?<!\w)([\d,]+\.\d{2})(?!\s*[/-]\d)', after)
        if dm:
            raw = dm.group(1).replace(",", "")
            if float(raw) > 0:
                return "$" + raw
    return None


def _try_addr_labels(line, nxt, nxt2, lines, idx, labels) -> Optional[str]:
    """Try label patterns for address extraction."""
    for pat, mode in labels:
        m = re.search(pat, line)
        if not m:
            continue
        if mode == "inline":
            val = _after_match(line, m)
            if val and len(val) > 5:
                return val.rstrip(".,")
        # Address block: collect lines until state+zip or blank
        inline_val = _after_match(line, m)
        if inline_val and _valid_address(inline_val):
            return inline_val.rstrip(".,")
        parts = []
        for offset in range(1, 4):
            if idx + offset >= len(lines):
                break
            al = lines[idx + offset].strip()
            if not al or _is_header(al):
                break
            parts.append(al)
            if re.search(r'\b[A-Z]{2}\s*\d{5}', al):
                break
        if parts:
            return ", ".join(parts).rstrip(".,")
    return None


def _try_remit(line: str) -> Optional[str]:
    """Extract remit info from labeled patterns."""
    ll = line.lower()
    # "payable to XXX" / "make checks payable to XXX"
    m = re.search(r'(?i)(?:make\s+checks?\s+)?payable\s+to\s*:?\s*(.+)', line)
    if m:
        entity = m.group(1).strip()
        entity = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                         entity, flags=re.I).strip()
        entity = entity.rstrip(".,;: ")
        if entity and len(entity) > 3:
            return entity
    # "Mail to:" / "Remit to:" / "Send payment to:"
    for kw in ("mail to:", "remit to:", "send payment to:",
               "return payment to:"):
        if kw in ll:
            _, _, val = line.lower().partition(kw)
            original = line[line.lower().index(kw) + len(kw):].strip()
            if original:
                return original.rstrip(".,;: ")
    return None


def _after_match(line: str, m) -> Optional[str]:
    """Get text after a regex match, handling colon separators."""
    rest = line[m.end():].strip()
    # If there's a colon in the matched portion, use text after the last colon
    matched = line[m.start():m.end()]
    if ":" in matched:
        _, _, val = line[m.start():].partition(":")
        return val.strip()
    # If colon immediately follows
    if rest.startswith(":"):
        return rest[1:].strip()
    # Handle period-as-colon OCR artifact: "Policy Number. 000000"
    if rest.startswith("."):
        return rest[1:].strip()
    return rest if rest else None


# ============================================================
# CUSTOM EXTRACTORS (post-loop)
# ============================================================

def _extract_carrier_keyword(lines: List[str]) -> Optional[Dict]:
    """Detect carrier name by keyword matching (no label)."""
    # KNOWN CARRIERS for fuzzy matching against OCR-garbled text
    _KNOWN_CARRIERS = [
        "QBE SPECIALTY INSURANCE COMPANY",
        "ALLSTATE INDEMNITY COMPANY",
        "ALLSTATE VEHICLE AND PROPERTY INSURANCE COMPANY",
        "STATE FARM FIRE AND CASUALTY COMPANY",
        "NATIONWIDE MUTUAL INSURANCE COMPANY",
        "TRAVELERS HOME AND MARINE INSURANCE COMPANY",
        "LIBERTY MUTUAL FIRE INSURANCE COMPANY",
        "SAFECO INSURANCE COMPANY OF AMERICA",
        "ERIE INSURANCE EXCHANGE",
        "AMERICAN FAMILY INSURANCE COMPANY",
        "CITIZENS PROPERTY INSURANCE CORPORATION",
        "UNIVERSAL PROPERTY AND CASUALTY INSURANCE COMPANY",
        "FEDERATED NATIONAL INSURANCE COMPANY",
        "AEGIS SECURITY INSURANCE COMPANY",
        "HARTFORD FIRE INSURANCE COMPANY",
        "TEXAS FARMERS INSURANCE COMPANY",
        "ENCOMPASS INDEMNITY COMPANY",
        "ANCHOR SPECIALTY INSURANCE COMPANY",
    ]
    
    for line in lines[:40]:
        ll = line.lower().strip()
        if not ll or len(ll) > 120:
            continue
        # Use word boundary matching to avoid false positives
        # e.g., "ins" in "collins" or "co" in "colorado"
        has_carrier = bool(re.search(
            r'\b(?:insurance|indemnity|casualty|underwriters|surety|assurance)\b', ll))
        has_entity = bool(re.search(
            r'\b(?:company|exchange|group|mutual|corp|corporation)\b', ll))
        has_skip = any(w in ll for w in _CARRIER_SKIP)
        # Also match abbreviated: "ALLIED PROP AND CAS INS CO"
        # Use word boundary for abbreviations too
        has_abbrev_ins = bool(re.search(r'\bins\b', ll))
        has_abbrev_entity = bool(re.search(r'\b(?:co|prop|cas)\b', ll))
        # For abbreviated match, require BOTH ins + co/prop/cas (not just one)
        has_abbrev = has_abbrev_ins and has_abbrev_entity
        if (has_carrier or has_abbrev_ins) and (has_entity or has_abbrev) and not has_skip:
            val = line.strip()
            # Skip if it looks like an address (has zip code)
            if re.search(r'\b\d{5}(-\d{4})?\b', val) and re.search(r'\b[A-Z]{2}\s+\d{5}', val):
                continue
            # Strip common label prefixes: "Company:", "Carrier:", "Insurer:", etc.
            val = re.sub(r'^(?:Company|Carrier|Insurer|Underwriter|Provider)\s*:\s*',
                         '', val, flags=re.I).strip()
            # Strip common trailing suffixes
            val = re.sub(r'\s+(?:Mortgagee|Dec\s*Summary|Declarations?|'
                         r'Summary|Page\s*\d).*$', '', val, flags=re.I).strip()
            if val and len(val) > 5:
                return _r(val, "sc_carrier_kw", 0.80)
    
    # Fuzzy matching fallback: try to match OCR-garbled carrier names
    # E.g., "BOWARE QSE SPECATY INSURANCE COMPANY" → "QBE SPECIALTY INSURANCE COMPANY"
    try:
        from difflib import SequenceMatcher
        for line in lines[:40]:
            ll = line.lower().strip()
            if not ll or len(ll) > 120 or len(ll) < 10:
                continue
            # Must contain something resembling "insurance" or similar
            has_ins_hint = any(w in ll for w in ('insuran', 'indemn', 'casualt', 'assuran',
                                                  'company', 'exchang', 'mutual', 'corp'))
            if not has_ins_hint:
                continue
            val = line.strip()
            val_upper = val.upper()
            best_match, best_score = None, 0
            for known in _KNOWN_CARRIERS:
                score = SequenceMatcher(None, val_upper, known).ratio()
                if score > best_score:
                    best_match, best_score = known, score
            if best_score > 0.55 and best_match:  # 55% similarity threshold
                return _r(best_match, "sc_carrier_fuzzy", 0.78)
    except ImportError:
        pass
    
    return None


def _extract_exp_from_period(lines: List[str]) -> Optional[Dict]:
    """Extract expiration as second date from policy period."""
    for line in lines:
        ll = line.lower()
        if any(k in ll for k in ("policy period", "policy term",
                                  "pol. from", "pol.from")):
            dates = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', line)
            if len(dates) >= 2:
                return _r(dates[1], "sc_exp_period", 0.85)
            written = re.findall(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*'
                r'\s+\d{1,2},?\s+\d{4})', line, re.I)
            if len(written) >= 2:
                return _r(written[1], "sc_exp_period", 0.85)
        if "through" in ll:
            d = _extract_date(line)
            if d:
                return _r(d, "sc_exp_through", 0.83)
    return None


def _extract_mortgage_isaoa(lines: List[str]) -> Optional[Dict]:
    """Extract mortgage company from ISAOA/ATIMA context."""

    # --- FIRST PASS: Pattern A (highest priority) ---
    # "Third party interest added: Mortgagee, COMPANY NAME ... ATIMA, loannum"
    for line in lines:
        m = re.search(
            r'(?i)third\s+party\s+interest\s+added\s*:\s*mortgagee\s*,\s*(.+)',
            line)
        if m:
            raw = m.group(1).strip()
            name = re.sub(r'\s+(?:ITS\s+SUCCESSORS\s+AND/OR\s+ASSIGNS\s+)?(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA).*$',
                          '', raw, flags=re.I).strip()
            name = re.sub(r',?\s*\d{6,}$', '', name).strip()
            if name and len(name) > 3 and not _is_header(name):
                return _r(name, "sc_mortgage_third_party", 0.85)

    # --- SECOND PASS: Pattern C (ISAOA/ATIMA on next line → name is current line) ---
    # Also handles: "STATEBRIDGE COMPANY LLC" followed by "ITS SUCCESSORS AND/OR ASSIGNS ATIMA"
    for idx, line in enumerate(lines):
        if idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            nxt_is_isaoa_line = (
                re.search(r'(?i)^ISAOA', nxt) or nxt.upper().startswith('ISAOA')
                or re.match(r'(?i)^ITS\s+SUCCESSORS?\s+AND[/\s]+OR\s+ASSIGNS', nxt)
            )
            if nxt_is_isaoa_line:
                candidate = line.strip()
                if (candidate and len(candidate) > 3
                        and not re.search(r'(?i)^(?:to|from|dear|date|insured|named|policy|loan|attention)', candidate)
                        and not re.search(r'\b\d{5}\b', candidate)
                        and not _is_header(candidate)):
                    name = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$',
                                  '', candidate, flags=re.I).strip()
                    if name and len(name) > 3:
                        return _r(name, "sc_mortgage_isaoa_prevline", 0.82)

    # --- THIRD PASS: Pattern B (ISAOA on same line as company name) ---
    for idx, line in enumerate(lines):
        if re.search(r'\b(?:ISAOA|ATIMA)\b', line, re.I):
            name = re.sub(r'\s+(?:ITS\s+SUCCESSORS[\s\w/]*)?(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA).*$',
                          '', line, flags=re.I).strip()
            # Also strip standalone "ITS SUCCESSORS AND/OR ASSIGNS" if that's all that remains
            name = re.sub(r'^(?:ITS\s+)?SUCCESSORS?\s+AND[/\s]+OR\s+ASSIGNS\s*$', '',
                          name, flags=re.I).strip()
            name = re.sub(r'^\d+\w*\s+', '', name).strip()
            name = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                          name, flags=re.I).strip()
            name = re.sub(r'(?i)^(?:third\s+party\s+interest\s+\w+\s*:\s*)?(?:mortgagee|loss\s+payee)\s*,?\s*', '', name).strip()
            if name and len(name) > 3 and not _is_header(name):
                if idx > 0 and re.search(r'(?i)insured', lines[idx - 1]):
                    continue
                # CRITICAL: If name is short (single word, <15 chars) and previous line
                # looks like it could be the start of a multi-line company name, combine them
                # e.g., "BROKER SOLUTIONS INC DBA NEW AMERICAN" + "FUNDG" → full company name
                if (len(name.split()) <= 2 and len(name) < 15 and idx > 0):
                    prev = lines[idx - 1].strip()
                    # Previous line should look like a company name beginning
                    if (prev and len(prev) > 5
                            and not re.search(r'(?i)^(?:to|from|dear|date|insured|named|policy|loan|attention)', prev)
                            and not re.search(r'\b\d{5}\b', prev)
                            and not _is_header(prev)
                            and not re.match(r'^\d+$', prev)):
                        combined_name = prev.strip() + " " + name
                        # Clean ISAOA/ATIMA from combined just in case
                        combined_name = re.sub(r'\s+(?:ITS\s+SUCCESSORS[\s\w/]*)?(?:ISAOA|ATIMA).*$',
                                               '', combined_name, flags=re.I).strip()
                        if combined_name and len(combined_name) > 5:
                            return _r(combined_name, "sc_mortgage_isaoa_combined", 0.80)
                return _r(name, "sc_mortgage_isaoa", 0.78)
            # If name is empty/short after stripping, the company name is on the PREVIOUS line
            if (not name or len(name) <= 3) and idx > 0:
                prev = lines[idx - 1].strip()
                # Previous line should look like a company name (not a label, not a barcode)
                if (prev and len(prev) > 3
                        and not re.search(r'(?i)^(?:to|from|dear|date|insured|named|policy|loan|attention|\d{5,})', prev)
                        and not re.search(r'\b\d{5}\b', prev)
                        and not _is_header(prev)):
                    prev_clean = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$',
                                        '', prev, flags=re.I).strip()
                    # Strip leading barcodes/reference numbers like "000061EI310CCL1002480300 050030 001"
                    prev_clean = re.sub(r'^\d+\w*\d+\w*\s+', '', prev_clean).strip()
                    if prev_clean and len(prev_clean) > 3:
                        return _r(prev_clean, "sc_mortgage_isaoa_prevline_fallback", 0.80)

        # "First:" line under Mortgagee section
        if re.match(r'(?i)first\s*:', line.strip()):
            val = line.split(":", 1)[1].strip() if ":" in line else ""
            nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            candidate = val if val and len(val) > 3 else nxt
            if candidate:
                candidate = _clean_isaoa(candidate)
                if len(candidate) > 3:
                    return _r(candidate, "sc_mortgage_first", 0.78)
    return None


def _extract_cancel_reason_kw(lines: List[str]) -> Optional[Dict]:
    """Infer cancellation reason from keywords in text."""
    for line in lines:
        ll = line.lower()
        if "non-payment" in ll or "nonpayment" in ll or "non pay" in ll:
            return _r("Non-payment of premium", "sc_cancel_kw", 0.78)
        if "borrower request" in ll or "borrower-request" in ll:
            return _r("Borrower request", "sc_cancel_kw", 0.78)
        if "insured request" in ll or "insured named below has requested" in ll:
            return _r("Insured request", "sc_cancel_kw", 0.78)
        if "non-renewal" in ll or "nonrenewal" in ll or "non-renewed" in ll:
            return _r("Non-renewal", "sc_cancel_kw", 0.78)
        if "building has been sold" in ll or "property sold" in ll:
            return _r("Building sold/removed/destroyed", "sc_cancel_kw", 0.78)
        if "removed, destroyed" in ll or "removed or destroyed" in ll:
            return _r("Building sold/removed/destroyed", "sc_cancel_kw", 0.78)
        # OCR typo: "tiitated" = "initiated"
        if "customer initiated" in ll or "customer tiitated" in ll:
            return _r("Cancellation Customer Initiated", "sc_cancel_kw", 0.78)
        if "premium payment has not been received" in ll:
            return _r("Non-payment of premium", "sc_cancel_kw", 0.78)
        if "insured - non pay" in ll:
            return _r("Insured - Non Pay", "sc_cancel_kw", 0.78)
        if "no longer required by lender" in ll:
            return _r("No longer required by lender", "sc_cancel_kw", 0.78)
        # Flood CAN: "no longer meets the definition of an eligible building"
        if "no longer meets the definition" in ll:
            return _r("Building sold/removed/destroyed", "sc_cancel_kw", 0.78)
        # "cancelled at the time and date shown above" — generic, AmFam
        if "cancelled at the time and date shown above" in ll:
            return _r("Cancellation per notice", "sc_cancel_kw", 0.72)
    return None


def _extract_remit_fuzzy(lines: List[str]) -> Optional[Dict]:
    """Fuzzy remit info extraction (OCR typos)."""
    for line in lines:
        ll = line.lower()
        if re.search(r'make\s+checks?\s+pa\w*\s+to', ll):
            m = re.search(r'pa\w*\s+to\s+(.+)', line, re.I)
            if m:
                entity = re.sub(r'\s+(?:PO\s+BOX).*$', '', m.group(1),
                                flags=re.I).strip()
                return _r(entity, "sc_remit_fuzzy", 0.75)
    return None



# ============================================================
# TABLE / LAYOUT HELPERS (added — were referenced but missing)
# ============================================================

def _extract_total_premium_table(lines: List[str]) -> Optional[Dict]:
    """
    Extract total premium from table layouts where the label is on one line
    and the dollar amount is on the next line, or from columnar formats.
    Handles: 'Total Premium' / '$1,088.00' style layouts.
    """
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        # Check for total premium labels
        if re.search(r'(?i)\b(?:total\s+(?:annual\s+)?premium|'
                     r'full\s+payment|total\s+policy\s+premium|'
                     r'annual\s+premium|premium\s+amount)\b', ll):
            # Try same line first
            m = re.search(r'\$\s*([\d,]+\.?\d*)', line)
            if m:
                return _r("$" + m.group(1).replace(" ", ""), "sc_premium_table", 0.80)
            # Try next 1-3 lines
            for offset in range(1, 4):
                if idx + offset >= len(lines):
                    break
                nxt = lines[idx + offset].strip()
                m = re.search(r'\$\s*([\d,]+\.?\d*)', nxt)
                if m:
                    return _r("$" + m.group(1).replace(" ", ""), "sc_premium_table", 0.78)
    return None


def _extract_mortgage_from_interests_table(lines: List[str]) -> Optional[Dict]:
    """
    Extract mortgage company from 'Other Interests' or 'Additional Interests'
    table sections (AAA, Nationwide, etc.).
    """
    in_section = False
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        if re.search(r'(?i)\b(?:other\s+interests|additional\s+interests|'
                     r'mortgagee|lienholder|loss\s+payee)\b', ll):
            in_section = True
            # Check if the name is on the same line after a colon/separator
            m = re.search(r'(?:mortgagee|lienholder|loss\s+payee)\s*[:\-]?\s*(.+)',
                          line, re.I)
            if m:
                val = m.group(1).strip()
                if len(val) > 3 and not re.match(r'^[\d\s/\-]+$', val):
                    return _r(val, "sc_interests_table", 0.75)
            continue
        if in_section:
            # Look for a company name (all caps, or contains ISAOA/ATIMA/BANK/MORTGAGE)
            stripped = line.strip()
            if not stripped:
                in_section = False
                continue
            if re.search(r'(?i)\b(?:isaoa|atima|bank|mortgage|credit\s+union|'
                         r'lending|servicing|funding)\b', stripped):
                val = re.sub(r'\s+', ' ', stripped).strip()
                return _r(val, "sc_interests_table", 0.75)
            if re.match(r'^[A-Z\s&,\.]+$', stripped) and len(stripped) > 5:
                return _r(stripped, "sc_interests_table", 0.72)
    return None


def _extract_loan_from_interests_table(lines: List[str]) -> Optional[Dict]:
    """
    Extract loan number from 'Other Interests' or 'Additional Interests'
    table sections. Often near mortgage company info.
    """
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        # Direct loan number labels in interests sections
        m = re.search(r'(?i)(?:loan|acct|account|contract)\s*(?:#|no\.?|number)\s*'
                      r'[:\-]?\s*([\w\-]+)', line)
        if m:
            val = m.group(1).strip()
            if len(val) >= 4 and re.search(r'\d', val):
                return _r(val, "sc_interests_loan", 0.75)
        # "Loan: XXXXXXX" format
        m = re.search(r'(?i)\bloan\s*[:\-]\s*([\d\-]+)', line)
        if m:
            val = m.group(1).strip()
            if len(val) >= 4:
                return _r(val, "sc_interests_loan", 0.75)
    return None


def _extract_property_from_coverage_detail(lines: List[str]) -> Optional[Dict]:
    """
    Extract property address from 'Coverage Detail for [address]' inline format.
    Common in Encompass, Safeco, and similar carriers.
    """
    for line in lines:
        m = re.search(r'(?i)coverage\s+detail\s+for\s+(.+)', line)
        if m:
            addr = m.group(1).strip()
            addr = re.sub(r'\s*-\s*$', '', addr)
            if _looks_like_address(addr):
                return _r(addr, "sc_coverage_detail", 0.78)
    return None


def _extract_property_from_located_at(lines: List[str]) -> Optional[Dict]:
    """
    Extract property address from 'LOCATED AT:' or 'DESCRIPTION OF PROPERTY:'
    patterns (Adirondack, Nationwide, etc.).
    """
    for idx, line in enumerate(lines):
        m = re.search(r'(?i)(?:located\s+at|description\s+of\s+property|'
                      r'property\s+location|insured\s+property)\s*[:\-]?\s*(.*)',
                      line)
        if m:
            addr = m.group(1).strip()
            if addr and _looks_like_address(addr):
                return _r(addr, "sc_located_at", 0.78)
            # Try next line
            if idx + 1 < len(lines):
                nxt = lines[idx + 1].strip()
                if nxt and _looks_like_address(nxt):
                    return _r(nxt, "sc_located_at", 0.76)
    return None


def _extract_orphaned_policy_value(lines: List[str], out: Dict) -> None:
    """
    Two-column OCR layout: policy label appears alone on one line,
    value appears much later (up to 25 lines) as a standalone orphaned line.
    Handles Nationwide/AMCO format: "ADP    0038122530    7"
    where ADP is a plan code prefix, the number is the policy, and trailing digit is a suffix.

    In two-column OCR the right-column values appear after ALL left-column content,
    so the label (line 5) and value (line 17) may be 12+ lines apart — with all
    left-column prose (letters, addresses) appearing in between.
    KEY FIX: never STOP on prose — always SKIP it and keep scanning.
    """
    label_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if re.search(r'(?i)policy\s+no\.?[\s\.]*:\.?\s*$', stripped):
            label_idx = idx
            break

    if label_idx is None:
        return

    # Scan up to 25 lines forward — value appears after all left-column prose
    for offset in range(1, 26):
        i = label_idx + offset
        if i >= len(lines):
            break
        candidate = lines[i].strip()
        if not candidate:
            continue

        # SKIP: other label-only lines (end with ':' or '.:')
        if re.search(r'(?i)^\w[\w\s\.]+\s*\.?\s*:\s*\.?\s*$', candidate):
            continue

        # SKIP: obvious footer/noise lines — keep scanning
        if re.search(r'(?i)^(mortgagee copy|i9z9|nw cf|yours very)', candidate):
            continue
        if candidate in (')+1.', 'NW CF-1305 i', 'NW CF-1305'):
            continue

        # SKIP: barcode strings with embedded lowercase
        if re.match(r'^[0-9][0-9a-z][0-9A-Za-z]{8,}$', candidate) and re.search(r'[a-z]', candidate):
            continue

        # SKIP: OCR reference codes like "I9Z9  2020248"
        if re.match(r'^[A-Z]\d[A-Z]\d\b', candidate):
            continue

        # SKIP: long prose sentences — but do NOT stop scanning.
        # In two-column OCR, the entire left-column letter body appears before
        # the right-column values, so prose between label and value is expected.
        words = candidate.split()
        if len(words) > 7 and not any(c.isdigit() for c in candidate[:15]):
            continue  # skip prose, keep scanning for the real value

        # MATCH: Nationwide/AMCO plan-code format: "ADP    0038122530    7"
        # PREFIX (2-4 caps) + DIGITS (8-12) + SINGLE DIGIT suffix
        m = re.match(r'^([A-Z]{2,4})\s+([\d][\d\s]{6,}[\d])\s+(\d)\s*$', candidate)
        if m:
            raw = re.sub(r'\s+', '', m.group(2))  # "0038122530"
            clean = _clean_policy(raw)
            if _valid_policy_number(clean):
                out["policy_number"] = _r(clean, "sc_orphaned_policy", 0.86)
                return

        # MATCH: generic standalone policy-number-looking token (single token only)
        first_token = re.match(r'^([\w\-]{6,30})\s*$', candidate)
        if first_token:
            token = first_token.group(1)
            if re.search(r'[a-z]', token):
                continue  # lowercase → barcode/noise
            clean = _clean_policy(token)
            if _valid_policy_number(clean):
                out["policy_number"] = _r(clean, "sc_orphaned_policy", 0.78)
                return


def _extract_orphaned_loan_value(lines: List[str], out: Dict) -> None:
    """
    Two-column OCR layout: loan label appears alone on one line,
    value appears later as a standalone orphaned digit-only line.
    Handles Nationwide/AMCO format: "0579158471" on its own line.
    """
    label_idx = None
    for idx, line in enumerate(lines):
        if re.search(r'(?i)loan\s+no\.?[\s\.]*:\.?\s*$', line.strip()):
            label_idx = idx
            break

    if label_idx is None:
        return

    for offset in range(1, 21):
        i = label_idx + offset
        if i >= len(lines):
            break
        candidate = lines[i].strip()
        if not candidate:
            continue

        # Skip label-only lines
        if re.search(r'(?i)^\w[\w\s\.]+\s*\.?\s*:\s*\.?\s*$', candidate):
            continue

        # Skip barcodes and footers
        if re.search(r'(?i)^(mortgagee copy|i9z9|nw cf|yours very|amco ins)', candidate):
            continue
        if re.match(r'^[0-9a-z]{10,}[A-Z0-9]{3,}$', candidate):
            continue

        # Pure digit string — potential loan number
        if re.match(r'^\d{7,15}$', candidate):
            if _valid_loan_number(candidate):
                out["loan_number"] = _r(candidate, "sc_orphaned_loan", 0.84)
                return


def _extract_column_policy_number(lines: List[str], out: Dict) -> None:
    """
    Column-header layout: 'Policy number' as header, value 2 lines below.
    American Family format:
        Policy number        Policy period        Billing account number
        41044-67747-94       5/30/2020...         622-278-039-84
    Also: standalone 'Policy No:' or 'Policy No' with value on same or next line.
    """
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        # "Policy number" as standalone header (no value on same line)
        if re.match(r'(?i)^policy\s+number\s*$', line.strip()):
            # Look ahead 1-5 lines for a value that looks like a policy number
            for offset in range(1, 6):
                if idx + offset >= len(lines):
                    break
                candidate = lines[idx + offset].strip()
                # Skip other column headers and sub-headers
                if re.search(r'(?i)policy\s+period|billing|cancellation|named\s+insured|third party', candidate):
                    continue
                clean = _clean_policy(candidate.split()[0] if candidate.split() else "")
                # Also try full first token group (e.g., "48-K09368-01-0020")
                first_token = re.match(r'^([\w\-]+)', candidate)
                if first_token:
                    clean = _clean_policy(first_token.group(1))
                if clean and _valid_policy_number(clean):
                    out["policy_number"] = _r(clean, "sc_col_policy", 0.82)
                    return

        # "Policy No:" or "Policy No" on EDI format
        m = re.match(r'(?i)policy\s+no\.?\s*:\s*(.+)', line.strip())
        if m:
            val = m.group(1).strip()
            # Take first token (may have "Term Dates" etc. after)
            first = re.match(r'^([\w\-]+)', val)
            if first:
                clean = _clean_policy(first.group(1))
                if _valid_policy_number(clean):
                    out["policy_number"] = _r(clean, "sc_edi_policy", 0.85)
                    return


def _extract_column_named_insured(lines: List[str], out: Dict) -> None:
    """
    Column-header format: 'Named insured' header with value below.
    American Family DOI:
        Policy number    Cancellation date/time    Named insured
        48-K09368-01-0020    9/17/2020             RIEMER, LINDA M
    """
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        if re.match(r'(?i)^named\s+insured\s*$', line.strip()):
            # Value is typically 2 lines below (after sub-header)
            for offset in range(1, 4):
                if idx + offset >= len(lines):
                    break
                candidate = lines[idx + offset].strip()
                # Skip other headers/labels
                if re.search(r'(?i)third party|we are|you no longer|policy number|cancellation', candidate):
                    continue
                # Try to find a name-like value (at least 2 words, no digits)
                # In column layout, values may be on same line separated by spaces
                # Look for name-like tokens at end of line
                parts = candidate.split()
                # Try last 2-4 words as name
                for start in range(max(0, len(parts)-4), len(parts)-1):
                    name_candidate = " ".join(parts[start:])
                    if _valid_name(name_candidate):
                        out["insured_name"] = _r(
                            _clean_isaoa(name_candidate), "sc_col_insured", 0.78)
                        return


def _extract_doi_loan_number(lines: List[str], out: Dict) -> None:
    """
    DOI-specific loan number patterns:
    - 'Third party interest added: Mortgagee, COMPANY, <loan_number>' (same line)
    - 'Third party interest added: Mortgagee, COMPANY ATIMA,\n<loan_number>' (next line)
    - 'Loan number (if available)' + value below
    - 'LOAN NO.:' inline
    - 'Loan No:' inline
    """
    for idx, line in enumerate(lines):
        ll = line.lower().strip()

        # Pattern A: "Third party interest added/removed: Mortgagee, COMPANY, LOANNUM" (same line)
        m = re.search(
            r'(?i)third\s+party\s+interest\s+(?:added|removed)\s*:\s*'
            r'(?:mortgagee|loss\s+payee)\s*,\s*.+?,\s*(\d{7,15})\s*$',
            line)
        if m and _valid_loan_number(m.group(1)):
            out["loan_number"] = _r(m.group(1).strip(), "sc_doi_loan_tp", 0.88)
            return

        # Pattern A2: loan number on NEXT line after "Third party interest added: ... ATIMA,"
        if re.search(r'(?i)third\s+party\s+interest\s+(?:added|removed)\s*:', line):
            # Check if line ends with ATIMA/ISAOA/ASSIGNS + optional comma (loan on next line)
            if re.search(r'(?i)(?:ATIMA|ISAOA|ASSIGNS)\s*,?\s*$', line):
                if idx + 1 < len(lines):
                    nxt = lines[idx + 1].strip()
                    if re.match(r'^\d{7,15}$', nxt) and _valid_loan_number(nxt):
                        out["loan_number"] = _r(nxt, "sc_doi_loan_tp_nextline", 0.86)
                        return
            # Also check: loan number embedded after ATIMA/ISAOA on the same line
            m2 = re.search(r'(?i)(?:ATIMA|ISAOA|ASSIGNS)\s*,\s*(\d{7,15})', line)
            if m2 and _valid_loan_number(m2.group(1)):
                out["loan_number"] = _r(m2.group(1).strip(), "sc_doi_loan_tp_embedded", 0.87)
                return

        # Pattern B: "Loan number" standalone or with "(if available)"
        if re.match(r'(?i)^loan\s+number', ll):
            # Check for inline value first
            m = re.search(r'(?i)loan\s+number[^:]*:\s*(\S+)', line)
            if m and _valid_loan_number(m.group(1)):
                out["loan_number"] = _r(m.group(1).strip(), "sc_doi_loan", 0.82)
                return
            # Look ahead for value (skip non-digit lines)
            for offset in range(1, 6):
                if idx + offset >= len(lines):
                    break
                candidate = lines[idx + offset].strip()
                if re.match(r'(?i)\(?if\s+available\)?', candidate):
                    continue
                # Pure digit string = loan number
                if candidate and re.match(r'^[\d]+$', candidate):
                    if _valid_loan_number(candidate):
                        out["loan_number"] = _r(candidate, "sc_doi_loan", 0.80)
                        return
                # Continue scanning (address lines, etc. may appear between header and value)


def _extract_property_from_insured_header(lines: List[str], out: Dict) -> None:
    """
    Policy Change / DOI: insured address appears in a free-form header block
    BEFORE the policy details table. Pattern:
        <Name line (2+ words, no digits, title-case or ALL CAPS)>
        <Street address line (starts with digit)>
        <City State ZIP line>
    This address is treated as property_address for DOI docs since the insured's
    address is the property address for mortgage tracking purposes.
    
    IMPORTANT: Must skip insurance company HQ addresses and mortgagee PO Box addresses
    that also appear in the header area.
    """
    # Known company HQ / mortgagee addresses to skip
    _SKIP_ADDRESS_PATTERNS = [
        # Insurance company headquarters
        r'(?i)american\s+parkway',
        r'(?i)madison\s+wi\s+53783',
        r'(?i)libertyville\s+il\s+60048',
        r'(?i)273\s+peterson\s+rd',
        r'(?i)scottsdale.*az\s+85258',
        r'(?i)gainey\s+center',
        # Common mortgagee PO Boxes (Troy MI, etc.)
        r'(?i)po\s+box\s+7\d{3}\s*.*troy\s+mi',
        r'(?i)48007',
        r'(?i)po\s+box\s+\d+.*miami.*fl.*33197',
        r'(?i)po\s+box\s+\d+.*dallas.*tx.*75266',
    ]

    # Names that indicate a company header block, not an insured header
    _COMPANY_NAME_INDICATORS = [
        r'(?i)\b(?:insurance|indemnity|casualty)\b.*\b(?:company|co|group|exchange|mutual|corp)\b',
        r'(?i)^american\s+family',
        r'(?i)^nationwide',
        r'(?i)^allstate',
        r'(?i)^state\s+farm',
        r'(?i)^amco\s+insurance',
    ]

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Stop scanning once we hit policy information section headers
        if re.search(r'(?i)^(policy\s+information|policy\s+number|policy\s+period'
                     r'|description\s+of\s+change|change\(s\)\s+made|named\s+insured'
                     r'|third\s+party\s+interest)', stripped):
            break
        # Candidate name line: 2-5 words, no digits, not all-caps noise headers
        words = stripped.split()
        if (2 <= len(words) <= 6
                and not any(c.isdigit() for c in stripped)
                and not re.search(r'(?i)^(dear|date|insured|mortgage|to|from|re:|subject'
                                  r'|attention|cc|the|your|this|we|you|if|for|and|or|in|of)', stripped)
                and not _is_header(stripped)):

            # SKIP: if name line looks like an insurance company name
            if any(re.search(pat, stripped) for pat in _COMPANY_NAME_INDICATORS):
                continue

            # Check if next non-empty line is a street address
            nxt_idx = idx + 1
            while nxt_idx < len(lines) and not lines[nxt_idx].strip():
                nxt_idx += 1
            if nxt_idx >= len(lines):
                continue
            nxt = lines[nxt_idx].strip()

            # SKIP: PO Box addresses (these are mortgagee/company mailing, not property)
            if re.search(r'(?i)^p\.?o\.?\s*box', nxt):
                continue

            # Street address: starts with digit
            if re.match(r'^\d+\s+\w', nxt) and not re.search(r'(?i)policy|loan|insured', nxt):
                # Collect city/state/zip if present
                city_idx = nxt_idx + 1
                while city_idx < len(lines) and not lines[city_idx].strip():
                    city_idx += 1
                city_line = lines[city_idx].strip() if city_idx < len(lines) else ""
                addr_parts = [nxt]
                if city_line and re.search(r'\b[A-Z]{2}\s*\d{5}', city_line):
                    addr_parts.append(city_line)
                addr = ", ".join(addr_parts)

                # SKIP: known company HQ / mortgagee addresses
                if any(re.search(pat, addr) for pat in _SKIP_ADDRESS_PATTERNS):
                    continue

                if _valid_address(addr):
                    out["property_address"] = _r(addr, "sc_doi_insured_header_addr", 0.76)
                    return


def _extract_doi_name_address(lines: List[str], missing_fields: List[str],
                               out: Dict) -> None:
    """
    DOI-specific: extract insured name + property address from
    'Name and address of Insured:' or 'Policyholder(s):' blocks.
    Prioritize 'Name and address of Insured:' since it has both name AND address.
    """
    # First pass: look for "Name and address of Insured:" (has both name + address)
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        if re.search(r'(?i)name\s+and\s+address\s+of\s+(?:the\s+)?insured', ll):
            _doi_extract_from_label(lines, idx, missing_fields, out)
            return

    # Second pass: look for "Policyholder(s)" (name only, address may follow)
    for idx, line in enumerate(lines):
        ll = line.lower().strip()
        if re.search(r'(?i)policyholder', ll):
            _doi_extract_from_label(lines, idx, missing_fields, out)
            return


def _doi_extract_from_label(lines: List[str], idx: int,
                             missing_fields: List[str], out: Dict) -> None:
    """Helper: extract name + address starting from label at idx."""
    # Name is on next non-empty line
    name_idx = idx + 1
    while name_idx < len(lines) and not lines[name_idx].strip():
        name_idx += 1
    if name_idx >= len(lines):
        return

    name_line = lines[name_idx].strip()

    # Skip if it's "Page X of Y" or other noise
    if re.search(r'(?i)^page\s+\d|^\d+$|^policy|^loan|^your', name_line):
        name_idx += 1
        while name_idx < len(lines) and not lines[name_idx].strip():
            name_idx += 1
        if name_idx >= len(lines):
            return
        name_line = lines[name_idx].strip()

    # Validate name: not starting with digit, not a label
    if name_line and not re.match(r'^\d', name_line):
        if not re.search(r'(?i)^page|^policy|^loan|^your|^information', name_line):
            if "insured_name" in missing_fields and "insured_name" not in out:
                clean_name = _clean_isaoa(name_line)
                if _valid_name(clean_name):
                    out["insured_name"] = _r(clean_name, "sc_doi_insured", 0.80)

    # Address lines after the name
    if "property_address" in missing_fields and "property_address" not in out:
        addr_start = name_idx + 1
        addr_lines = []
        for ai in range(addr_start, min(addr_start + 3, len(lines))):
            if ai >= len(lines):
                break
            aline = lines[ai].strip()
            if not aline:
                break
            # Address: starts with digit, PO BOX, state+zip, or city+state+zip
            is_addr = (
                re.match(r'^\d', aline)
                or re.search(r'[A-Z]{2}\s+\d{5}', aline)
                or re.search(r'(?i)^(po\s+box|p\.?o\.?\s*box)', aline)
                or re.search(r'^[A-Z][a-zA-Z\s]+[A-Z]{2}\s+\d{5}', aline)
            )
            # Stop at labels or section headers
            is_label = re.search(
                r'(?i)^(policy|terminate|mortgag|loan|the insured|name and)', aline)
            if is_addr and not is_label:
                addr_lines.append(aline)
            elif addr_lines:
                break
            else:
                break
        if addr_lines:
            addr = ", ".join(addr_lines)
            out["property_address"] = _r(addr, "sc_doi_addr", 0.78)


# ============================================================
# GLINER WRAPPER
# ============================================================

def _extract_with_gliner_safe(text, missing_fields):
    try:
        from agents.stage2_5_gliner_agent import extract_with_gliner
        return extract_with_gliner(text, missing_fields,
                                   confidence_threshold=0.65)
    except ImportError:
        return {}
    except Exception as e:
        print(f"[SC+TE] GLiNER failed: {e}")
        return {}


# ============================================================
# UTILITIES
# ============================================================

def _extract_date(text: str) -> Optional[str]:
    # Full month names: January 15, 2024
    m = re.search(
        r"((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        text, re.I)
    if m:
        return m.group(1)
    # Abbreviated month names: NOV 09 2021
    m = re.search(
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b",
        text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
    if m:
        return m.group(1)
    return None


def _clean_policy(val: str) -> str:
    if not val:
        return val
    val = val.strip().lstrip(":").strip().rstrip(".,;:")
    # Stop at common separators: REASON, Policy, AR, INS, Loan, Agency, etc.
    # These are often appended by OCR when columns merge
    val = re.split(
        r'\s+(?:REASON|Policy|AR\b|INS\b|Loan|Mortgag|Name|Address|Type|'
        r'Agency|Agent|Markham|Page|Covered|Your|Information|Account)',
        val, flags=re.I)[0].strip()
    # Remove leading type codes like "ADP", "HO" before actual policy number
    m = re.match(r'^[A-Z]{2,4}\s+(\d[\d\s\-]+\w*)$', val)
    if m:
        val = m.group(1)
    # Remove trailing single characters (artifact codes)
    val = re.sub(r'\s+[A-Za-z0-9]$', '', val).strip()
    # Remove spaces between digit groups: "826 139 329" → "826139329"
    # But keep spaces between alpha-numeric: "DPC 0076173896-1"
    parts = val.split()
    if all(p.isdigit() for p in parts):
        val = "".join(parts)
    else:
        val = re.sub(r'(?<=\d)\s+(?=\d)', '', val)
    return val


def _clean_isaoa(val: str) -> str:
    if not val:
        return val
    val = re.sub(r'\s+(?:ISAOA|ATIMA|ISAOA\s*/?\s*ATIMA)\s*$', '',
                  val, flags=re.I).strip()
    val = re.sub(r'\s+(?:PO\s+BOX|P\.?O\.?\s*BOX).*$', '',
                  val, flags=re.I).strip()
    return val.rstrip(".,;:")


def _is_header(text: str) -> bool:
    ll = text.lower().strip()
    return any(h in ll for h in (
        "coverage", "deductible", "endorsement", "forms", "discount",
        "section", "what you should", "policy documents", "general",
        "exclusions", "definitions", "limits of liability"))


def _valid_policy_number(text: str) -> bool:
    if not text or len(text) < 5:
        return False
    if re.search(r"\(\d{3}\)", text):
        return False
    if re.fullmatch(r"\d{5}(-\d{4})?", text):
        return False
    if re.fullmatch(r"[A-Z]{2}\d{5}(-\d{4})?", text, re.I):
        return False
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text):
        return False
    tl = text.lower()
    if any(k in tl for k in ("box", "page", "code", "type")):
        return False
    digits = sum(c.isdigit() for c in text)
    return digits >= 4 and 5 <= len(text) <= 30


def _valid_loan_number(text: str) -> bool:
    if not text:
        return False
    clean = re.sub(r'[^0-9A-Za-z]', '', text)
    digits = sum(c.isdigit() for c in clean)
    if not (digits >= 5 and 5 <= len(clean) <= 25):
        return False
    # Block footer/form reference codes (print job IDs)
    # e.g. "1965565232" from "19655_65232kR" at bottom of pages
    digit_str = re.sub(r'[^0-9]', '', clean)
    if digit_str and re.match(r'^(?:19\d{3}|044)\d{5,9}$', digit_str):
        return False
    # Block 10-digit numbers starting with 19xxx (form ref pattern)
    if len(digit_str) == 10 and digit_str[:2] == '19' and int(digit_str[:5]) >= 19000:
        return False
    return True


def _valid_name(text: str) -> bool:
    if not text or ":" in text:
        return False
    
    # CRITICAL: Reject OCR-garbled label text masquerading as names
    # E.g., "NANEAND ADDRESO OCTHEINSURED Daael Lome?" = garbled label + garbled name
    ll_nospace = re.sub(r'\s+', '', text.lower())
    _garbled_frags = ("nameand", "naneand", "addreso", "octhe", "ofthe",
                      "theinsured", "insuredname", "namedinsured",
                      "addressof", "nameandaddress", "coveredbythis",
                      "insuredlocation")
    if any(f in ll_nospace for f in _garbled_frags):
        return False
    
    has_entity = any(w in text.lower()
                     for w in ("llc", "inc", "corp", "company", "trust"))
    if any(c.isdigit() for c in text) and not has_entity:
        return False
    ll = text.lower()
    bad = ("policy", "coverage", "notice", "summary", "premium",
           "billing", "endorsement", "declarations", "page",
           "mortgagee", "agency", "agent", "services",
           "property", "mailing", "address", "number",
           "effective", "expiration", "document", "produced",
           "information", "renewal", "type",
           "copyright", "copyrighted", "includes copyrighted",
           "office, inc", "permission")
    if any(b in ll for b in bad):
        return False
    words = text.split()
    if has_entity:
        return 1 <= len(words) <= 10
    # Require at least 2 words for person names — single word is almost
    # always a partial name from OCR splitting across lines
    return 2 <= len(words) <= 8


def _valid_address(text: str) -> bool:
    if not text:
        return False
    ll = text.lower()
    if "po box" in ll or "p.o. box" in ll:
        return True
    if re.search(
        r"\d+\s+.+\b(st|street|ave|avenue|rd|road|blvd|"
        r"lane|ln|drive|dr|ct|court|cir|circle|way|pkwy|"
        r"ridge|pl|place|loop)\b", text, re.I):
        return True
    if re.search(r"\b[A-Z]{2}\s*\d{5}", text):
        return True
    return bool(re.search(r"\d+", text)) and len(text.split()) >= 3

# Alias used by table/layout helpers
_looks_like_address = _valid_address


def _semantic_cleanup(text: str) -> str:
    text = re.sub(r"\b[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}", "", text)
    text = re.sub(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "", text)
    text = re.sub(r"\$[\d,]+(\.\d{2})?", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()