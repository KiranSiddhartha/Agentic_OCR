# # agents/value_normalizer.py
# import re
# from utils.dictionary import apply_dictionary_fixes


# def normalize_extracted_fields(fields: dict) -> dict:
#     """
#     Post-extraction normalization.
#     Applies dictionary fixes and formatting ONLY to extracted values.
#     """
#     normalized = {}

#     for key, payload in fields.items():
#         # Handle both dict and string values
#         val = payload.get("value") if isinstance(payload, dict) else payload

#         if not val:
#             normalized[key] = payload
#             continue

#         # Apply dictionary fixes to this value only
#         val = apply_dictionary_fixes(str(val))

#         # Field-specific normalization
#         if "date" in key.lower():
#             val = normalize_date(val)
#         elif key in ["coverage_amount", "deductible", "balance_due", "total_premium"]:
#             val = normalize_currency(val)
#         elif "phone" in key.lower():
#             val = normalize_phone(val)
#         elif "policy_number" in key.lower():
#             val = normalize_policy_number(val)

#         # Preserve structure
#         if isinstance(payload, dict):
#             normalized[key] = {**payload, "value": val}
#         else:
#             normalized[key] = val

#     return normalized


# def normalize_date(text):
#     """Normalize date format to MM/DD/YYYY"""
#     if not text:
#         return text
    
#     # Fix single-digit months/days
#     text = re.sub(r'\b(\d{1})/(\d{1,2})/(\d{4})\b', r'0\1/\2/\3', text)
#     text = re.sub(r'\b(\d{1,2})/(\d{1})/(\d{4})\b', r'\1/0\2/\3', text)
    
#     return text


# def normalize_currency(text):
#     """Normalize currency to $X,XXX.XX format"""
#     if not text:
#         return text
    
#     # Extract digits only
#     digits = re.findall(r'\d+', str(text))
#     if digits:
#         try:
#             amount = int(''.join(digits))
#             return f"${amount:,}"
#         except:
#             pass
    
#     return text


# def normalize_phone(text):
#     """Normalize phone to (XXX) XXX-XXXX"""
#     if not text:
#         return text
    
#     digits = re.sub(r'\D', '', text)
    
#     if len(digits) == 10:
#         return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
#     elif len(digits) == 11 and digits[0] == '1':
#         return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
#     return text


# def normalize_policy_number(text):
#     """Clean policy number (remove spaces, normalize dashes)"""
#     if not text:
#         return text
    
#     # Remove internal spaces
#     text = re.sub(r'\s+', '', text)
    
#     # Standardize separators to dash
#     text = text.replace('_', '-').replace('/', '-')
    
#     return text.upper()


# agents/value_normalizer.py
from utils.dictionary import apply_dictionary_fixes

def normalize_extracted_fields(fields):
    normalized = {}

    for key, payload in fields.items():
        val = payload.get("value") if isinstance(payload, dict) else payload
        if not val:
            normalized[key] = payload
            continue

        val = apply_dictionary_fixes(val)

        normalized[key] = {
            **payload,
            "value": val
        }

    return normalized
