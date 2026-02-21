"""
validate_doctype_batches.py
============================
Runs 5 synthetic test documents per doc type through Stage1 extraction.
Reports field-by-field hit rates and flags missing fields.

Doc types tested: RNW, INV, CAN, DOI
Expected fields per type based on business requirements:
  RNW: carrier_name, effective_date, expiration_date, insured_name, policy_number,
       property_address, mailing_address, mortgage_company, loan_number, total_premium
  INV: carrier_name, insured_name, policy_number,
       balance_due, issue_date, remit_info, effective_date, expiration_date, property_address
  CAN: carrier_name, effective_date, insured_name, policy_number,
       cancellation_date, cancellation_reason, expiration_date, property_address
  DOI: policy_number, mortgage_company, loan_number,
       carrier_name, insured_name, property_address

Usage:
    python validate_doctype_batches.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.stage1_deterministic_agent import extract_fields

# ============================================================
# EXPECTED FIELDS PER DOC TYPE
# ============================================================
EXPECTED_FIELDS = {
    "RNW": [
        "carrier_name", "policy_number", "insured_name",
        "effective_date", "expiration_date",
        "property_address", "mailing_address",
        "mortgage_company", "loan_number", "total_premium",
    ],
    "INV": [
        "carrier_name", "policy_number", "insured_name",
        "balance_due", "issue_date", "remit_info",
        "effective_date", "expiration_date", "property_address",
        "mortgage_company", "loan_number",
    ],
    "CAN": [
        "carrier_name", "policy_number", "insured_name",
        "effective_date", "expiration_date",
        "cancellation_date", "cancellation_reason",
        "property_address", "mortgage_company", "loan_number",
    ],
    "DOI": [
        "policy_number", "mortgage_company", "loan_number",
        "carrier_name", "insured_name", "property_address",
    ],
}

# ============================================================
# TEST DOCUMENTS (5 per doc type)
# Each is a list of OCR text lines as would come from the pipeline
# ============================================================

RNW_DOCS = [
    # RNW Doc 1 — Standard renewal declaration
    [
        "RENEWAL DECLARATIONS",
        "State Farm Fire and Casualty Company",
        "Policy Number: HO-29-3847-F29-23T",
        "Named Insured: JOHN A SMITH",
        "Insured Mailing Address: 123 Oak Street, Austin, TX 78701",
        "Property Address: 456 Elm Ave, Austin, TX 78702",
        "Policy Period: 03/15/2024 to 03/15/2025",
        "Annual Premium: $1,842.00",
        "Mortgagee: WELLS FARGO BANK NA ISAOA",
        "Loan Number: 8271039845",
    ],
    # RNW Doc 2 — Flood renewal
    [
        "RENEWAL FLOOD INSURANCE POLICY DECLARATIONS",
        "Carrier: Allstate Insurance Company",
        "Policy No: FLD-2024-0087654",
        "Insured: MARIA GONZALEZ",
        "Mailing Address: PO Box 4421, Miami, FL 33101",
        "Location of Risk: 789 Coral Way, Miami, FL 33102",
        "Effective Date: 07/01/2024",
        "Expiration Date: 07/01/2025",
        "Total Premium: $956.00",
        "Mortgagee: BANK OF AMERICA NA ISAOA ATIMA",
        "Loan#: 1234567890",
    ],
    # RNW Doc 3 — Homeowners policy bill
    [
        "HOMEOWNERS POLICY DECLARATIONS",
        "CITIZENS PROPERTY INSURANCE CORPORATION",
        "Policy Number: HEX-0192837465",
        "Named Insured and Address:",
        "ROBERT E JOHNSON",
        "321 Magnolia Drive, Orlando, FL 32801",
        "Policy Period: From 09/01/2024 To 09/01/2025",
        "Annual Premium: $2,100.00",
        "Property Location: 321 Magnolia Drive, Orlando, FL 32801",
        "First Mortgagee: QUICKEN LOANS ISAOA",
        "Loan Number: 9988776655",
    ],
    # RNW Doc 4 — Simple renewal notice
    [
        "POLICY RENEWAL NOTICE",
        "Nationwide Mutual Insurance Company",
        "Your Policy Number: NPD-67890123",
        "Insured Name: PATRICIA L DAVIS",
        "Insured Address: 555 Peachtree St, Atlanta, GA 30308",
        "Property: 555 Peachtree St, Atlanta, GA 30308",
        "Effective Date: 11/15/2024",
        "Expiration Date: 11/15/2025",
        "Total Policy Premium: $1,650.50",
        "Holder: SUNTRUST MORTGAGE ISAOA",
        "Loan/Contract Number: 55443322110",
    ],
    # RNW Doc 5 — LexisNexis style
    [
        "INSURANCE COVERAGE NOTIFICATION",
        "Transaction Desc: Renewal",
        "Carrier: TRAVELERS PROPERTY CASUALTY",
        "Policy Number: 680-3948201-632-1",
        "Named Insured(s): WILLIAM T BROWN",
        "Property Location: 1001 River Rd, Nashville, TN 37201",
        "Mailing Address: 1001 River Rd, Nashville, TN 37201",
        "Policy Period: 01/10/2025 to 01/10/2026",
        "Total Annual Premium: $1,321.00",
        "Mortgagee(s): ROCKET MORTGAGE ISAOA ATIMA",
        "Loan Number: 7766554433",
    ],
]

INV_DOCS = [
    # INV Doc 1 — Standard invoice/bill
    [
        "HOMEOWNERS POLICY BILL",
        "Allstate Insurance Company",
        "Policy Number: 067 354 871",
        "Named Insured: DIANE K MORRISON",
        "Property Address: 202 Willow Lane, Denver, CO 80201",
        "Bill Date: 02/01/2024",
        "Balance (to pay in full): $1,142.00",
        "Make Check Payable To: Allstate Insurance Company",
        "Remit To: PO Box 55001, Chicago, IL 60690",
        "Effective Date: 03/01/2024",
        "Expiration Date: 03/01/2025",
        "Mortgage: CHASE BANK USA NA ISAOA",
        "Loan Number: 44332211009",
    ],
    # INV Doc 2 — Premium notice
    [
        "PREMIUM NOTICE",
        "Citizens Property Insurance Corporation",
        "Your Policy: HEX-5544332211",
        "Insured Name: HAROLD J WALKER",
        "Invoice Date: 01/15/2024",
        "Amount Due: $832.00",
        "Due Date: 02/15/2024",
        "Return Payment To: Citizens Property Insurance",
        "PO Box 19030, Jacksonville, FL 32245",
        "Policy Effective: 03/15/2024",
        "Expiration Date: 03/15/2025",
        "Mortgagee: REGIONS BANK ISAOA",
        "Loan: 99887766554",
        "Property: 808 Gulfview Blvd, Tampa, FL 33601",
    ],
    # INV Doc 3 — Balance due notice
    [
        "RENEWAL PREMIUM BILL",
        "USAA GENERAL INDEMNITY COMPANY",
        "Policy No.: HO-00292837",
        "Named Insured: CARLOS R MENDEZ",
        "Statement Date: 12/10/2023",
        "Total Balance Due: $2,250.00",
        "Pay Online at usaa.com or",
        "Make Checks Payable To: USAA",
        "Payable To: USAA Federal Savings Bank",
        "Policy Period: 01/01/2024 - 01/01/2025",
        "Property: 75 Sunset Ave, San Antonio, TX 78201",
    ],
    # INV Doc 4 — Billing statement
    [
        "BILLING STATEMENT",
        "State Farm Fire and Casualty Company",
        "Account Number: 29-AA-1234-5",
        "Insured: ANGELA M FOSTER",
        "Information As Of: 11/01/2023",
        "Total Amount Due: $467.50",
        "Minimum Amount Due No Later Than 12/01/2023",
        "Mail To: State Farm Insurance",
        "PO Box 588002, North Metro, GA 30029",
        "Effective Date: 12/01/2023",
        "Expiration Date: 12/01/2024",
        "Lienholder: TRUIST BANK ISAOA",
        "Loan/Contract #: 12309876543",
        "Property Address: 312 Magnolia Court, Charlotte, NC 28201",
    ],
    # INV Doc 5 — Invoice with invoice number
    [
        "INVOICE",
        "Heritage Property & Casualty Insurance Company",
        "Invoice Number: INV-2024-0078234",
        "Insured Name: THOMAS W REED",
        "Invoice Date: 03/05/2024",
        "Balance Due: $1,875.00",
        "Remit To: Heritage Insurance",
        "3625 Queen Palm Drive, Tampa, FL 33619",
        "Policy Effective: 04/01/2024",
        "Expiration Date: 04/01/2025",
        "Property: 44 Ocean Blvd, Fort Lauderdale, FL 33301",
        "Loan Number: 33221100998",
        "Mortgage: PENNYMAC LOAN SERVICES ISAOA",
    ],
]

CAN_DOCS = [
    # CAN Doc 1 — Standard cancellation notice
    [
        "NOTICE OF CANCELLATION",
        "Liberty Mutual Insurance Company",
        "Policy Number: H32-291-483920-40 7",
        "Named Insured: KEVIN J HOLLOWAY",
        "Property Address: 17 Birchwood Ct, Columbus, OH 43201",
        "Effective Date: 05/01/2024",
        "Expiration Date: 05/01/2025",
        "Cancellation Date: 06/15/2024",
        "Reason for Cancellation: Non-Payment of Premium",
        "Mortgagee: FIFTH THIRD BANK NA ISAOA",
        "Loan Number: 66778899001",
    ],
    # CAN Doc 2 — Non-renewal notice
    [
        "NOTICE OF NON-RENEWAL",
        "Farmers Insurance Exchange",
        "Policy No: 0154-73-8821",
        "Insured: LINDA C PRESCOTT",
        "Insured Address: 890 Maple Drive, Phoenix, AZ 85001",
        "Property: 890 Maple Drive, Phoenix, AZ 85001",
        "Policy Effective Date: 08/15/2023",
        "Policy Expiration Date: 08/15/2024",
        "Non-Renewal Date: 08/15/2024",
        "Reason: Underwriting Guidelines",
        "Mortgage: US BANK NA ISAOA ATIMA",
        "Loan #: 55443322118",
    ],
    # CAN Doc 3 — Company initiated cancellation
    [
        "CANCELLATION NOTICE",
        "Safeco Insurance Company of America",
        "Your Policy Number: OA 3948201-04",
        "Named Insured: PATRICIA ANNE WELLS",
        "Property: 234 Elm Street, Portland, OR 97201",
        "Policy Period: 09/01/2023 to 09/01/2024",
        "Cancellation Effective: 10/01/2023",
        "Cancel Reason: Company Request",
        "Carrier: Safeco Insurance Company of America",
        "Mortgagee: GUILD MORTGAGE ISAOA",
        "Loan Number: 87654321098",
    ],
    # CAN Doc 4 — Borrower-initiated
    [
        "THIRD PARTY NOTICE OF TERMINATION",
        "GEICO General Insurance Company",
        "Policy No.: GPP 1029384756",
        "Insured Name: MARCUS D JOHNSON",
        "Effective Date: 07/01/2024",
        "Expiration Date: 07/01/2025",
        "This policy will be cancelled effective: 07/20/2024",
        "Cancellation Date: 07/20/2024",
        "Reason: Borrower Request",
        "Mortgagee: NAVY FEDERAL CREDIT UNION ISAOA",
        "Loan: 77665544332",
        "Property: 500 Military Ave, Virginia Beach, VA 23451",
    ],
    # CAN Doc 5 — EDI cancellation notification
    [
        "INSURANCE COVERAGE NOTIFICATION",
        "XLC-S11 Doc Type - Cancellation",
        "Carrier Name: AMERICAN FAMILY INSURANCE",
        "Policy Number: 26WA-T1234567-00",
        "Named Insured(s): SAMANTHA G TURNER",
        "Property Location: 610 Prairie Ave, Kansas City, MO 64101",
        "Policy Effective Date: 02/01/2024",
        "Policy Expiration: 02/01/2025",
        "Cancellation Date: 03/15/2024",
        "Cancel Reason: Non-Payment of Premium",
        "Mortgage Company: FREEDOM MORTGAGE CORP ISAOA",
        "Loan Number: 11223344556",
    ],
]

DOI_DOCS = [
    # DOI Doc 1 — Standard deletion of interest
    [
        "DELETION OF INTEREST NOTICE",
        "Nationwide Mutual Insurance Company",
        "Policy Number: ACP BPH 0039281746",
        "Insured: GEORGE F HILL",
        "Property: 8 Lakeview Dr, Madison, WI 53701",
        "The mortgagee interest has been removed effective 04/30/2024.",
        "Mortgagee: BANK MIDWEST ISAOA",
        "Loan Number: 99887766554",
        "Carrier: Nationwide Mutual Insurance Company",
    ],
    # DOI Doc 2 — MIR EDI format
    [
        "INSURANCE COVERAGE NOTIFICATION",
        "MIR - Mortgagee Interest Removed",
        "Cancel Reason MIR",
        "Policy Number: TX-HOV-00019283-01",
        "Named Insured: ROSA M DELGADO",
        "Carrier: Travelers Property Casualty Company",
        "Mortgage Holder: CALIBER HOME LOANS ISAOA",
        "Loan/Contract Number: 33445566778",
        "Property Address: 400 Longhorn Trail, Fort Worth, TX 76101",
    ],
    # DOI Doc 3 — Loan satisfied
    [
        "NOTICE OF REMOVAL OF INTEREST",
        "State Farm Fire and Casualty Company",
        "Policy No: 81-BE-N122-8",
        "Named Insured: BARBARA T OLSON",
        "The loan has been satisfied.",
        "You no longer have an interest in this policy.",
        "First Mortgage: JPMORGAN CHASE BANK NA ISAOA",
        "Loan Number: 22334455667",
        "Property: 1234 Pine Street, Seattle, WA 98101",
    ],
    # DOI Doc 4 — Loss payee removed
    [
        "POLICY CHANGE/CANCELLATION NOTICE",
        "ASI ASSURANCE CORP",
        "Policy Number: HOP-2938471-05",
        "Insured Name: FRANK D STANLEY",
        "Loss Payee Has Been Removed",
        "You no longer have an interest in the above policy.",
        "Mortgage: AMERIHOME MORTGAGE ISAOA ATIMA",
        "Loan Number: 88997766554",
        "Property Address: 2020 Bayshore Blvd, Tampa, FL 33606",
    ],
    # DOI Doc 5 — Third party interest termination
    [
        "THIRD PARTY NOTICE OF TERMINATION",
        "Progressive Casualty Insurance Company",
        "Policy Number: 60-04087225-2024",
        "Insured: HELEN R SANTOS",
        "Terminate the interest of the third party named hereon",
        "Interest removed effective: 05/01/2024",
        "Mortgagee: LAKEVIEW LOAN SERVICING ISAOA",
        "Loan No.: 67890123456",
        "Property Location: 99 Ocean Drive, Miami Beach, FL 33139",
        "Carrier: Progressive Casualty Insurance Company",
    ],
]

ALL_BATCHES = {
    "RNW": RNW_DOCS,
    "INV": INV_DOCS,
    "CAN": CAN_DOCS,
    "DOI": DOI_DOCS,
}

# ============================================================
# RUN VALIDATION
# ============================================================

def run_validation():
    print("=" * 70)
    print("DOCUMENT TYPE FIELD EXTRACTION VALIDATION")
    print("5 documents per doc type | Stage 1 extraction only")
    print("=" * 70)

    grand_total_fields = 0
    grand_hit_fields = 0
    all_gaps = []

    for doc_type, docs in ALL_BATCHES.items():
        expected = EXPECTED_FIELDS[doc_type]
        print(f"\n{'='*70}")
        print(f"  DOC TYPE: {doc_type}  |  Expected fields: {', '.join(expected)}")
        print(f"{'='*70}")

        type_hits = {f: 0 for f in expected}
        type_total = len(docs)

        for i, lines in enumerate(docs, 1):
            result = extract_fields(lines)
            extracted_keys = set(result.keys())

            hit = []
            miss = []
            for f in expected:
                if f in extracted_keys:
                    hit.append(f)
                    type_hits[f] += 1
                else:
                    miss.append(f)

            status = "✅" if not miss else "⚠️"
            print(f"\n  Doc {i} {status}  Hit: {len(hit)}/{len(expected)}")
            if hit:
                for f in hit:
                    val = result[f].get("value", "?")
                    src = result[f].get("source", "?")
                    conf = result[f].get("confidence", 0)
                    print(f"    ✓ {f:<25} = {repr(val)[:40]}  [{src}, {conf:.2f}]")
            if miss:
                print(f"    MISSING: {', '.join(miss)}")
                for f in miss:
                    all_gaps.append((doc_type, i, f))

        print(f"\n  --- {doc_type} SUMMARY (hit rate per field) ---")
        for f in expected:
            rate = type_hits[f] / type_total
            bar = "█" * int(rate * 10) + "░" * (10 - int(rate * 10))
            flag = "" if rate == 1.0 else "  ← NEEDS IMPROVEMENT" if rate < 0.6 else ""
            print(f"    {f:<28} {bar} {type_hits[f]}/{type_total} ({rate*100:.0f}%){flag}")
            grand_total_fields += type_total
            grand_hit_fields += type_hits[f]

    print(f"\n{'='*70}")
    print("OVERALL SUMMARY")
    print(f"{'='*70}")
    overall_rate = grand_hit_fields / grand_total_fields if grand_total_fields else 0
    print(f"  Total field extractions: {grand_hit_fields}/{grand_total_fields} ({overall_rate*100:.1f}%)")

    if all_gaps:
        print(f"\n  GAPS TO FIX ({len(all_gaps)} total):")
        seen = set()
        for doc_type, doc_num, field in all_gaps:
            key = (doc_type, field)
            if key not in seen:
                seen.add(key)
                count = sum(1 for g in all_gaps if g[0] == doc_type and g[2] == field)
                print(f"    [{doc_type}] {field}  — missed in {count}/{len(ALL_BATCHES[doc_type])} docs")
    else:
        print("\n ALL FIELDS EXTRACTED SUCCESSFULLY!")

    print(f"\n{'='*70}")
    return overall_rate


if __name__ == "__main__":
    rate = run_validation()
    # Exit non-zero if overall hit rate < 70%
    sys.exit(0 if rate >= 0.70 else 1)