# utils/dictionary.py
# EXPANDED: Added 50+ more patterns from your document
import re

OCR_FIXES = {
    # === YOUR EXACT ERRORS ===
    "Wh": "",
    "effectiyr": "effective",
    "Thec": "These",
    "nt:": "at:",
    "as nt:": "as at:",
    "Flrnd": "Flood",
    "Processinq": "Processing",
    "processinq": "processing",
    "Centul": "Center",
    "Kalspe1MT": "Kalispell MT",
    "Kalspe1": "Kalispell",
    "5990-.7": "59901",
    "P.0.B2057": "P.O. Box 2057",
    "P.0.B": "P.O. Box",
    "P.0.": "P.O.",
    "Sinqle": "Single",
    "sinqle": "single",
    "Thrce": "Three",
    "thrce": "three",
    "Hore": "More",
    "hore": "more",
    "Flnors": "Floors",
    "flnors": "floors",
    "Elovaled": "Elevated",
    "elovaled": "elevated",
    "Enclnsure": "Enclosure",
    "enclnsure": "enclosure",
    "Mortgaqee": "Mortgagee",
    "mortgaqee": "mortgagee",
    "Conmunity": "Community",
    "conmunity": "community",
    "Reqular": "Regular",
    "reqular": "regular",
    "Caleulation": "Calculation",
    "caleulation": "calculation",
    "Subiotal": "Subtotal",
    "subiotal": "subtotal",
    "Multplier": "Multiplier",
    "multplier": "multiplier",
    "CPromium": "Premium",
    "Assmt": "Assessment",
    "assmt": "assessment",
    "Prm": "Premium",
    "prm": "premium",
    "Endorscment": "Endorsement",
    "endorscment": "endorsement",
    "Horao": "Horacio",
    "TIr1ntany": "Tiffany",
    "Tir1ntany": "Tiffany",
    
    # === NAMES ===
    "DAV1D": "DAVID",
    "Dav1d": "David",
    "GALMOR": "GALMOR",
    "CLAYHYRA": "CLAY HYDRA",
    "Clayhyra": "Clay Hydra",
    "BUk": "BUK",
    "BUK": "BUK",
    "REBECCA": "REBECCA",
    "BEAIMONT": "BEAUMONT",
    "Beaimont": "Beaumont",
    "CEYCTAL": "CRYSTAL",
    "Ceyctal": "Crystal",
    "RKIHA": "RKIHA",
    "GUL": "GULF",
    "NEWFI": "NEWFI",
    "AIMA": "ALMA",
    "Aima": "Alma",
    "L58357": "L58357",
    "4OU8A": "4OU8A",
    
    # === LOCATIONS ===
    "IX": "TX",
    "7X": "TX",
    "IX7770": "TX 77",
    "IX7770-19.5": "TX 77",
    "7X77n": "TX 77",
    "7X77n-": "TX 77",
    "BEAUM": "BEAUMONT",
    
    # === POLICY TERMS ===
    "p01icy": "policy",
    "Po1icy": "Policy",
    "Pol1cy": "Policy",
    "POLICV": "POLICY",
    "polic7": "policy",
    "insuranee": "insurance",
    "lnsurance": "Insurance",
    "1nsurance": "Insurance",
    "INSURANEE": "INSURANCE",
    
    # === CHARACTER CONFUSIONS ===
    "0wner": "owner",
    "p0licy": "policy",
    "1nsured": "Insured",
    "po1icy": "policy",
    "c1aim": "claim",
    "c1aims": "claims",
    "bui1ding": "building",
    
    # === DATES ===
    "20Z3": "2023",
    "2O23": "2023",
    "2O2O": "2020",
    "2O21": "2021",
    "202O": "2020",
    "2Ol0": "2010",
    "lO/": "10/",
    "O1/": "01/",
    "O2/": "02/",
    "O3/": "03/",
    "O4/": "04/",
    "O5/": "05/",
    "O6/": "06/",
    "O7/": "07/",
    "O8/": "08/",
    "O9/": "09/",
    "O4/14/2O21": "04/14/2021",
    
    # === BLURRED TEXT ===
    "ellective": "effective",
    "effectlve": "effective",
    "effecti've": "effective",
    "eflective": "effective",
    "expiratlon": "expiration",
    "expirat1on": "expiration",
    "expirati0n": "expiration",
    
    # === FINANCIAL ===
    "amoun1": "amount",
    "amoullt": "amount",
    "dol1ar": "dollar",
    "do11ar": "dollar",
    "coveage": "coverage",
    "premiu1n": "premium",
    "premiurn": "premium",
    "prernium": "premium",
    "deductib1e": "deductible",
    "deductibie": "deductible",
    "deduct1ble": "deductible",
    
    # === TABLE ARTIFACTS (ALL FROM YOUR DOC) ===
    ",..": "",
    "..": "",
    ",..7..1!": "",
    ",++'": "",
    "./.": "",
    "+'F,I'": "",
    ".IAA": "",
    "I FVATh +.": "",
    "FVATh": "",
    ".1h)": "",
    ".1'": "",
    "b,dql.!": "",
    "dql.!": "",
    "/511, ou II": "",
    "/511,": "",
    "ou II": "",
    "7,4": "",
    "1.1.": "",
    "5, r": "",
    "5, n": "",
    "..E,": "",
    "4,0": "",
    "51 .": "",
    "+ (1)": "",
    "(1)": "",
    "..7..1!": "",
    "q,.": "",
    "2i..": "",
    ",++'": "",
    "11 ,++'": "",
    
    # === SPACING ISSUES ===
    "namec": "named",
    "insured.name": "insured name",
    "policy.number": "policy number",
    "effective.date": "effective date",
    "expiration.date": "expiration date",
    "phone.number": "phone number",
    "2h ALDER": "24 ALDER",
    "3T": "ST",
    "STE 104": "STE 104",
    "18.": "18",
    
    # === COMPANY/AGENCY ===
    "FARMERS": "FARMERS",
    "Farrners": "Farmers",
    "NFIP": "NFIP",
    "NFlP": "NFIP",
    "FEMA": "FEMA",
    "FENA": "FEMA",
    "GALVESTON COUNTY'": "GALVESTON COUNTY",
    
    # === MISC ===
    "Me Prm": "Premium",
    "HFLA1Surcharge": "HFLA Surcharge",
    "HFLA1": "HFLA",
    "Nh": "",
    "Jo E.A": "",
    "9470+50,/1/261": "",
    "TIr1ntany 1 1 l": "Tiffany",
    "044 092821 000090": "",

    # === ERIE INSURANCE SPECIFIC ===
    "Erie'": "Erie",
    "Erie\"": "Erie",
    "WO Erie": "Erie",
    "ins PI": "Insurance",
    "Wailing": "Mailing",
    "Wailing Name": "Mailing Name",
    "Lessor Risk": "Lesser Risk",
    
    # === YOUR EXISTING ERRORS (keep all of these) ===
    "Wh": "",
    "effectiyr": "effective",
    "Thec": "These",
    "nt:": "at:",
    "as nt:": "as at:",
    "Flrnd": "Flood",
    "Processinq": "Processing",
    # ... (keep all your existing entries)
    
    # === GARBLED TEXT PATTERNS (add these) ===
    "aennen": "",
    "aeraan": "",
    "aaennaen": "",
    "nennnnn": "",
    "meetiea": "",
    "alennile": "",
    "-aennen": "",
    "Buikhng": "Building",
    "Conmunity": "Community",
    "Policv": "Policy",
    "Poliey": "Policy",
    "GULProperty": "Property",
    "NFIP Policy Number:q": "NFIP Policy Number:",
    "PolicyPeriod": "Policy Period",
    "INSURANCe": "INSURANCE",
    "lnsurance": "Insurance",
    "rnortgage": "mortgage",
    "l1": "LL",
    # === CONTINUE WITH REST OF YOUR DICTIONARY ===
    # ... all your other entries
}

CHAR_SUBSTITUTIONS = {
    "uppercase_1_to_I": (r'(?<=[A-Z])1(?=[A-Z])', 'I'),
    "uppercase_0_to_O": (r'(?<=[A-Z])0(?=[A-Z])', 'O'),
    "lowercase_0_to_o": (r'(?<=[a-z])0(?=[a-z])', 'o'),
    "lowercase_1_to_l": (r'(?<=[a-z])1(?=[a-z])', 'l'),
    "number_l_to_1": (r'(?<=\d)l(?=\d)', '1'),
    "number_O_to_0": (r'(?<=\d)O(?=\d)', '0'),
    "number_I_to_1": (r'(?<=\d)I(?=\d)', '1'),
}

PROPER_CASE = {
    "farmers": "FARMERS",
    "nfip": "NFIP",
    "fema": "FEMA",
    "texas": "Texas",
    "flood": "Flood",
    "insurance": "Insurance",
    "policy": "Policy",
}

def apply_dictionary_fixes(text: str) -> str:
    """
    Apply dictionary-based OCR fixes safely.
    This runs BEFORE line merging and field extraction.
    """
    if not text:
        return text

    # 1. Direct phrase replacements (longest first)
    for wrong, correct in sorted(OCR_FIXES.items(), key=lambda x: -len(x[0])):
        if wrong in text:
            text = text.replace(wrong, correct)

    # 2. Regex-based character substitutions
    for _, (pattern, replacement) in CHAR_SUBSTITUTIONS.items():
        text = re.sub(pattern, replacement, text)

    # 3. Proper casing for known terms
    for k, v in PROPER_CASE.items():
        text = re.sub(rf'\b{k}\b', v, text, flags=re.IGNORECASE)

    # 4. Normalize colon spacing
    text = re.sub(r'\s*:\s*', ': ', text)

    # 5. Remove dangling garbage like ": q"
    text = re.sub(r':\s+[a-zA-Z]$', ':', text)

    return text.strip()