# ✅ MASTER KEYWORD CONSTANTS (AUTHORITATIVE)
# 1️⃣ Policy Number — Labels + Patterns
# Policy Number Labels
# POLICY_NUMBER_LABELS = {
#     "policy number",
#     "policy no",
#     "policy #",
#     "policy id",
#     "policy reference",
#     "policy:",
#     "policy no:",
#     "dwelling policy number",
#     "dwelling fire policy number",
#     "homeowners policy number",
#     "ultrapack plus policy number",
#     "renewal policy number",
#     "amended policy number",
#     "previous policy number",
# }

# Policy Number Context Anchors

# (used when no colon exists)

# POLICY_NUMBER_CONTEXT = {
#     "policy period",
#     "policy info",
#     "policy indicators",
#     "declarations",
#     "policy declarations",
# }

# Policy Number Regex Patterns
# POLICY_NUMBER_REGEX = [
#     r"\b[A-Z]{1,4}[-\s]?\d{6,12}\b",              # OKH3-109194373
#     r"\b[A-Z]{2,5}\s?\d{7,12}[-]?\d?\b",          # DPC 0076173896-1
#     r"\b\d{8,12}\b",                              # Pure numeric
#     r"\b[A-Z0-9]{2}[A-Z0-9\-]{5,28}\b",            # Generic strict
# ]

# 2️⃣ Insured Name — ALL Variants
# Inline / Block Labels
# INSURED_NAME_LABELS = {
#     "insured",
#     "named insured",
#     "insured name",
#     "insured name and address",
#     "insured mailing",
#     "insured mailing name",
#     "insured mailing name and address",
#     "insured & mailing address",
#     "policyholder",
#     "policyholder/insured",
#     "policyholder/named insured",
# }

# Standalone Block Headers
# INSURED_BLOCK_HEADERS = {
#     "insured",
#     "named insured",
#     "insured mailing name and address",
#     "insured name and address",
# }

# 3️⃣ Property Address — Highest-Variance Field
# Primary Triggers
# PROPERTY_ADDRESS_TRIGGERS = {
#     "property address",
#     "property insured",
#     "location of insured property",
#     "coverage detail for",
#     "coverage applies to",
#     "described location",
#     "residence premises",
#     "location id described location",
#     "location:",
#     "address:",
#     "located at",
# }

# Weak / Secondary Triggers

# (used only if nothing else found)

# PROPERTY_ADDRESS_SECONDARY = {
#     "description of property",
#     "homeowners coverage on the dwelling at the above address",
#     "the described residence premises",
# }

# 4️⃣ Mortgage Company — Clean vs Noise
# Mortgage Section Triggers (Role Detection)
# MORTGAGE_BLOCK_TRIGGERS = {
#     "mortgagee",
#     "mortgagee full name",
#     "mortgagee mailing name and address",
#     "mortgage company",
#     "lender",
#     "loss payee",
#     "loss payee, mortgagee or other interest",
#     "other interest",
#     "other interested parties",
#     "mortgagee copy",
# }

# Mortgage Name Suffixes (Allowed)
# MORTGAGE_ALLOWED_SUFFIXES = {
#     "isaoa",
#     "atima",
#     "isaoa atima",
# }

# Hard Block — NOT Mortgage Companies
# BAD_MORTGAGE_PRODUCTS = {
#     "ultrapack",
#     "special package",
#     "homeowners",
#     "dwelling",
#     "policy",
#     "endorsement",
#     "coverage",
#     "insurance",
#     "exchange",
# }

# 5️⃣ Loan Number — Explicit + Implicit
# Loan Labels
# LOAN_NUMBER_LABELS = {
#     "loan number",
#     "loan no",
#     "loan #",
#     "loan id",
#     "mortgage loan number",
#     "account number",
# }

# Loan Context Anchors
# LOAN_CONTEXT = {
#     "mortgagee",
#     "billing information to be paid by mortgagee",
#     "loss payee",
# }

# 6️⃣ Carrier / Insurance Company
# Carrier Keywords
# CARRIER_KEYWORDS = {
#     "insurance",
#     "insurance company",
#     "insurance exchange",
#     "insurance group",
#     "mutual insurance",
#     "indemnity company",
#     "underwritten by",
#     "insurance provided by",
# }

# Carrier Blockers (Never Carrier)
# CARRIER_BLOCKLIST = {
#     "agency",
#     "agent",
#     "services",
#     "producer",
#     "sales rep",
# }

# 7️⃣ Document / Template Type Indicators

# (used for confidence + routing)

# TEMPLATE_KEYWORDS = {
#     # Renewal
#     "rnw", "renewal", "renewal certificate",

#     # Cancellation
#     "can", "cancellation", "non payment", "npay", "unwritten", "unwr",

#     # Involuntary
#     "inv", "involuntary",

#     # DOI
#     "doi", "department of insurance",

#     # Policy types
#     "ho", "ho6", "haz", "fire", "fir", "fld", "flood",
#     "wind", "wnd", "ll", "landlord", "uo",

#     # Pre-quote / pending
#     "pq", "pre-quote",
# }

# 8️⃣ Universal Noise / Exclusion Keywords
# GLOBAL_NOISE_KEYWORDS = {
#     "coverage",
#     "limits",
#     "endorsements",
#     "forms",
#     "deductible",
#     "premium",
#     "conditions",
#     "our duties",
#     "appraisal",
#     "loss payment",
#     "building owner",
#     "property protection",
# }

# 🔧 HOW TO USE THESE (Mapping)
# update_role
# if any(k in ll for k in POLICY_NUMBER_LABELS):
#     role = POLICY_HEADER

# elif any(k in ll for k in INSURED_BLOCK_HEADERS):
#     role = INSURED_BLOCK

# elif any(k in ll for k in PROPERTY_ADDRESS_TRIGGERS):
#     role = PROPERTY_BLOCK

# elif any(k in ll for k in MORTGAGE_BLOCK_TRIGGERS):
#     role = MORTGAGE_BLOCK

# _inline
# if any(k in ll for k in POLICY_NUMBER_LABELS):
#     ...

# if label in INSURED_NAME_LABELS:
#     ...

# if any(k in ll for k in LOAN_NUMBER_LABELS):
#     ...

# _safe_sweep
# if any(k in ll for k in PROPERTY_ADDRESS_TRIGGERS):
#     look_ahead_for_address()

# if any(k in ll for k in INSURED_NAME_LABELS):
#     next_line_name()