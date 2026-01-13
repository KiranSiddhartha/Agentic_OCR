# # agents/field_extraction_agent.py
# # Enhanced comprehensive field extraction
# # Combines regex patterns with relation-based extraction

# import re
# from typing import List, Dict, Optional, Tuple


# def extract_fields(lines: List[str]) -> Dict[str, Dict]:
#     """
#     Comprehensive regex-based field extraction.
#     Works with text lines from OCR.
#     Enhanced with multiple fallback patterns.
#     """
#     text = "\n".join(lines)
#     structured = {}
    
#     # Clean text for better matching
#     text_clean = text.replace('|', 'I').replace('0O', 'O')
    
#     # ============================================================
#     # CARRIER / INSURANCE COMPANY
#     # ============================================================
#     carrier_patterns = [
#         r'(?:Insurance\s+Co(?:mpany)?\s+Name|Carrier(?:\s+Name)?|Issued\s+By)[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|Policy|Insured)',
#         r'(?:Policy\s+)?(?:Coverage\s+)?Provided\s+By[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#         r'Insurance\s+Company[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#     ]
    
#     for pattern in carrier_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE | re.MULTILINE)
#         if m:
#             carrier = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(carrier) >= 3 and not carrier.isdigit():
#                 structured["carrier"] = {
#                     "value": carrier,
#                     "confidence": 0.94,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # POLICY NUMBER - Comprehensive patterns
#     # ============================================================
#     policy_patterns = [
#         r'Policy\s+Number[:\s]+([A-Z0-9\-]{5,30})',
#         r'Policy\s+No\.?[:\s]+([A-Z0-9\-]{5,30})',
#         r'Policy\s*#[:\s]+([A-Z0-9\-]{5,30})',
#         r'Certificate\s+Number[:\s]+([A-Z0-9\-]{5,30})',
#         r'Risk\s+ID[:\s]+([A-Z0-9\-]{5,30})',
#         r'Pol\.?\s+No\.?[:\s]+([A-Z0-9\-]{5,30})',
#         # OCR variants
#         r'P(?:o|0)l(?:i|1)c(?:y|i)\s*(?:Number|No)[:\s]+([A-Z0-9\-]{5,30})',
#         # Fallback: Policy followed by alphanumeric
#         r'Policy[:\s]+([A-Z0-9\-]{6,30})(?:\s|$)',
#     ]
    
#     for pattern in policy_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             policy_num = m.group(1).strip()
#             # Validate: must have at least 5 chars and some digits
#             if len(policy_num) >= 5 and sum(c.isdigit() for c in policy_num) >= 2:
#                 structured["policy_number"] = {
#                     "value": policy_num,
#                     "confidence": 0.95,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # INSURED NAME
#     # ============================================================
#     name_patterns = [
#         r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s\.,-]{2,60}?)(?:\n|Mailing|Property|$)',
#         r'Insured\s+Name[:\s]+([A-Z][A-Za-z\s\.,-]{2,60}?)(?:\n|$)',
#         r'Policyholder[:\s]+([A-Z][A-Za-z\s\.,-]{2,60}?)(?:\n|$)',
#         r'(?:Insured|Customer|Borrower)[:\s]+([A-Z][A-Za-z\s\.,-]{2,60}?)(?:\n|$)',
#         r'Policy\s+holder[:\s]+([A-Z][A-Za-z\s\.,-]{2,60}?)(?:\n|$)',
#     ]
    
#     for pattern in name_patterns:
#         m = re.search(pattern, text_clean, re.MULTILINE | re.IGNORECASE)
#         if m:
#             name = re.sub(r'\s+', ' ', m.group(1).strip()).rstrip('.,')
#             # Validate: should not contain document keywords
#             if (len(name) >= 2 and 
#                 not any(c.isdigit() for c in name) and
#                 not any(word in name.lower() for word in ['policy', 'insurance', 'number', 'date'])):
#                 structured["insured_name"] = {
#                     "value": name,
#                     "confidence": 0.92,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # PROPERTY ADDRESS
#     # ============================================================
#     property_patterns = [
#         r'Property\s+Address[:\s]+([^\n]+(?:\n[^\n]{5,})?)',
#         r'(?:Location|Insured\s+address|Premises|Prescribed\s+location|Residential\s+address)[:\s]+([^\n]+)',
#         r'Covered\s+Location[:\s]+([^\n]+)',
#     ]
    
#     for pattern in property_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             addr = re.sub(r'\s+', ' ', m.group(1).strip())
#             # Exclude PO BOX and mailing addresses
#             if (len(addr) >= 8 and 
#                 any(c.isdigit() for c in addr) and
#                 'po box' not in addr.lower() and 
#                 'p.o. box' not in addr.lower()):
#                 structured["property_address"] = {
#                     "value": addr,
#                     "confidence": 0.93,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # MAILING ADDRESS
#     # ============================================================
#     mailing_patterns = [
#         r'Mailing\s+Address[:\s]+([^\n]+(?:\n[^\n]{5,})?)',
#         r'PO\s+BOX[:\s]+([^\n]+)',
#         r'P\.O\.\s+BOX[:\s]+([^\n]+)',
#     ]
    
#     for pattern in mailing_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             addr = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(addr) >= 5:
#                 structured["mailing_address"] = {
#                     "value": addr,
#                     "confidence": 0.91,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # LOAN NUMBER
#     # ============================================================
#     loan_patterns = [
#         r'Loan\s+Number[:\s]+([A-Z0-9\-]{5,30})',
#         r'LN#[:\s]+([A-Z0-9\-]{5,30})',
#         r'Loan\s+No\.?[:\s]+([A-Z0-9\-]{5,30})',
#         r'Reference\s+[Nn]umber[:\s]+([A-Z0-9\-]{5,30})',
#         r'Account\s+[Nn]umber[:\s]+([A-Z0-9\-]{5,30})',
#     ]
    
#     for pattern in loan_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             loan_num = m.group(1).strip()
#             if len(loan_num) >= 5 and sum(c.isdigit() for c in loan_num) >= 3:
#                 structured["loan_number"] = {
#                     "value": loan_num,
#                     "confidence": 0.93,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # MORTGAGE / LIEN HOLDER
#     # ============================================================
#     mortgage_patterns = [
#         r'(?:Mortgage|Lien\s+holder|Loss\s+Payee|Lender|Certificate\s+Holder)[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#         r'Other\s+Interest[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#         r'Mortgagee[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#     ]
    
#     for pattern in mortgage_patterns:
#         m = re.search(pattern, text_clean, re.MULTILINE | re.IGNORECASE)
#         if m:
#             mortgage = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(mortgage) >= 3:
#                 structured["mortgage"] = {
#                     "value": mortgage,
#                     "confidence": 0.90,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # DATES - Multiple formats and contexts
#     # ============================================================
    
#     # Notice Effective Date
#     notice_eff_patterns = [
#         r'Notice\s+Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Endorsement\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Change\s+Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Declaration\s+Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#     ]
    
#     for pattern in notice_eff_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["notice_effective_date"] = {
#                 "value": m.group(1),
#                 "confidence": 0.94,
#                 "source": "regex"
#             }
#             break
    
#     # Effective Date
#     effective_patterns = [
#         r'Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Policy\s+Effective(?:\s+Date)?[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Inception\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Term\s+Start\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Beginning[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#     ]
    
#     for pattern in effective_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["effective_date"] = {
#                 "value": m.group(1),
#                 "confidence": 0.94,
#                 "source": "regex"
#             }
#             break
    
#     # Expiration Date
#     expiration_patterns = [
#         r'Expiration\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Policy\s+Expires?[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Through[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Term\s+End\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Ending[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#     ]
    
#     for pattern in expiration_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["expiration_date"] = {
#                 "value": m.group(1),
#                 "confidence": 0.94,
#                 "source": "regex"
#             }
#             break
    
#     # Cancellation Date
#     cancel_patterns = [
#         r'Cancellation\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Expire\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Void\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Cease\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#     ]
    
#     for pattern in cancel_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["cancellation_date"] = {
#                 "value": m.group(1),
#                 "confidence": 0.92,
#                 "source": "regex"
#             }
#             break
    
#     # Issue Date
#     issue_patterns = [
#         r'Issue\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Printed\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#         r'Mailed\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
#     ]
    
#     for pattern in issue_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["issue_date"] = {
#                 "value": m.group(1),
#                 "confidence": 0.90,
#                 "source": "regex"
#             }
#             break
    
#     # Fallback: Extract all dates if specific ones not found
#     if "effective_date" not in structured or "expiration_date" not in structured:
#         all_dates = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b', text_clean)
#         if all_dates and "effective_date" not in structured:
#             structured["effective_date"] = {
#                 "value": all_dates[0],
#                 "confidence": 0.75,
#                 "source": "regex_fallback"
#             }
#         if len(all_dates) > 1 and "expiration_date" not in structured:
#             structured["expiration_date"] = {
#                 "value": all_dates[1],
#                 "confidence": 0.75,
#                 "source": "regex_fallback"
#             }
    
#     # ============================================================
#     # FINANCIAL FIELDS
#     # ============================================================
    
#     # Total Premium
#     premium_patterns = [
#         r'Total\s+Premium[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Premium\s+Amount[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Annual\s+Premium[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Premium[:\s]+\$\s*([\d,]+\.?\d*)',
#     ]
    
#     for pattern in premium_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["total_premium"] = {
#                 "value": f"${m.group(1)}",
#                 "confidence": 0.92,
#                 "source": "regex"
#             }
#             break
    
#     # Balance Due
#     balance_patterns = [
#         r'Balance\s+Due[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Amount\s+Due[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Minimum\s+Due[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'(?:Pay|Paid)\s+in\s+full[:\s]+\$\s*([\d,]+\.?\d*)',
#     ]
    
#     for pattern in balance_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["balance_due"] = {
#                 "value": f"${m.group(1)}",
#                 "confidence": 0.91,
#                 "source": "regex"
#             }
#             break
    
#     # Dwelling Coverage
#     dwelling_patterns = [
#         r'Dwelling\s+(?:Coverage|Limit|Amount)[:\s]+\$\s*([\d,]+)',
#         r'Coverage\s+A[:\s\.]*\s*Dwelling[:\s]+\$\s*([\d,]+)',
#         r'Coverage\s+A[:\s]+\$\s*([\d,]+)',
#     ]
    
#     for pattern in dwelling_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["dwelling_coverage"] = {
#                 "value": f"${m.group(1)}",
#                 "confidence": 0.91,
#                 "source": "regex"
#             }
#             break
    
#     # Deductible
#     deductible_patterns = [
#         r'Deductible\s+Amount[:\s]+\$\s*([\d,]+\.?\d*)',
#         r'Deductible[:\s]+\$\s*([\d,]+\.?\d*)',
#     ]
    
#     for pattern in deductible_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             structured["deductible"] = {
#                 "value": f"${m.group(1)}",
#                 "confidence": 0.89,
#                 "source": "regex"
#             }
#             break
    
#     # ============================================================
#     # AGENT INFORMATION
#     # ============================================================
    
#     # Agent Name
#     agent_patterns = [
#         r'Agent(?:\s+Name)?[:\s]+([A-Z][A-Za-z\s\.,-]{2,50}?)(?:\n|$)',
#         r'(?:Producer|Agency|Representative|Broker)[:\s]+([A-Z][A-Za-z\s\.,-]{2,50}?)(?:\n|$)',
#     ]
    
#     for pattern in agent_patterns:
#         m = re.search(pattern, text_clean, re.MULTILINE | re.IGNORECASE)
#         if m:
#             agent = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(agent) >= 2 and not any(c.isdigit() for c in agent):
#                 structured["agent"] = {
#                     "value": agent,
#                     "confidence": 0.88,
#                     "source": "regex"
#                 }
#                 break
    
#     # Agent Phone
#     phone_patterns = [
#         r'Agent\s+Phone(?:\s+Number)?[:\s]+([\d\-\(\)\s]{10,20})',
#         r'(?:Policy\s+service|Claim\s+service)[:\s]+([\d\-\(\)\s]{10,20})',
#     ]
    
#     for pattern in phone_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             phone = m.group(1).strip()
#             # Extract digits
#             digits = ''.join(c for c in phone if c.isdigit())
#             if len(digits) >= 10:
#                 structured["agent_phone"] = {
#                     "value": phone,
#                     "confidence": 0.87,
#                     "source": "regex"
#                 }
#                 break
    
#     # ============================================================
#     # PAYMENT INFORMATION
#     # ============================================================
    
#     # Payee Name
#     payee_patterns = [
#         r'(?:Payable\s+To|Check\s+Payable)[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#         r'Payee\s+Name[:\s]+([A-Z][A-Za-z\s&,\.]{3,60}?)(?:\n|$)',
#     ]
    
#     for pattern in payee_patterns:
#         m = re.search(pattern, text_clean, re.MULTILINE | re.IGNORECASE)
#         if m:
#             payee = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(payee) >= 3:
#                 structured["payee_name"] = {
#                     "value": payee,
#                     "confidence": 0.86,
#                     "source": "regex"
#                 }
#                 break
    
#     # Remit Info
#     remit_patterns = [
#         r'(?:Remit\s+To|Payment\s+To|Make\s+Check\s+Payable)[:\s]+([^\n]{10,100})',
#     ]
    
#     for pattern in remit_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             remit = re.sub(r'\s+', ' ', m.group(1).strip())
#             if len(remit) >= 5:
#                 structured["remit_info"] = {
#                     "value": remit,
#                     "confidence": 0.84,
#                     "source": "regex"
#                 }
#                 break
    
#     return structured


# def extract_fields_with_relations(
#     lines: List[str],
#     layout_elements: List[Dict],
#     relations: List[Tuple]
# ) -> Dict[str, Dict]:
#     """
#     Enhanced extraction using layout + relations.
#     Combines regex results with spatial analysis.
#     """
#     # Start with regex extraction
#     fields = extract_fields(lines)
    
#     # Enhance with relations
#     for relation in relations:
#         if len(relation) != 4:
#             continue
        
#         entity1, rel_type, entity2, rel_conf = relation
        
#         if rel_type == 'HAS_VALUE':
#             field_name = _normalize_field_name(entity1)
            
#             if not field_name:
#                 continue
            
#             # If field not found by regex, add from relation
#             if field_name not in fields:
#                 fields[field_name] = {
#                     'value': entity2,
#                     'confidence': rel_conf * 0.85,  # Slightly lower confidence
#                     'source': 'relation_extraction'
#                 }
#             else:
#                 # Boost confidence if both found
#                 if fields[field_name].get('confidence', 0) < rel_conf:
#                     fields[field_name]['confidence'] = min(
#                         fields[field_name]['confidence'] + 0.05,
#                         0.98
#                     )
    
#     # Enhance with layout bounding boxes
#     if layout_elements:
#         fields = _enhance_with_layout(fields, layout_elements)
    
#     return fields


# def _normalize_field_name(label: str) -> Optional[str]:
#     """Normalize field label to standard field name"""
#     if not label:
#         return None
    
#     label = label.lower().strip().rstrip(':')
    
#     field_map = {
#         'carrier': 'carrier',
#         'insurance company': 'carrier',
#         'insurance co name': 'carrier',
#         'issued by': 'carrier',
#         'policy number': 'policy_number',
#         'policy no': 'policy_number',
#         'policy #': 'policy_number',
#         'certificate number': 'policy_number',
#         'insured name': 'insured_name',
#         'named insured': 'insured_name',
#         'policyholder': 'insured_name',
#         'borrower': 'insured_name',
#         'customer': 'insured_name',
#         'property address': 'property_address',
#         'location': 'property_address',
#         'insured address': 'property_address',
#         'mailing address': 'mailing_address',
#         'loan number': 'loan_number',
#         'ln#': 'loan_number',
#         'mortgage': 'mortgage',
#         'lien holder': 'mortgage',
#         'loss payee': 'mortgage',
#         'lender': 'mortgage',
#         'effective date': 'effective_date',
#         'policy effective': 'effective_date',
#         'inception date': 'effective_date',
#         'expiration date': 'expiration_date',
#         'policy expires': 'expiration_date',
#         'notice effective date': 'notice_effective_date',
#         'cancellation date': 'cancellation_date',
#         'issue date': 'issue_date',
#         'total premium': 'total_premium',
#         'premium amount': 'total_premium',
#         'premium': 'total_premium',
#         'balance due': 'balance_due',
#         'amount due': 'balance_due',
#         'dwelling coverage': 'dwelling_coverage',
#         'dwelling': 'dwelling_coverage',
#         'coverage a': 'dwelling_coverage',
#         'deductible': 'deductible',
#         'agent': 'agent',
#         'agent name': 'agent',
#         'producer': 'agent',
#         'agent phone': 'agent_phone',
#         'payee name': 'payee_name',
#         'payable to': 'payee_name',
#         'remit info': 'remit_info',
#         'remit to': 'remit_info',
#     }
    
#     if label in field_map:
#         return field_map[label]
    
#     # Partial matching
#     for key, value in field_map.items():
#         if re.search(rf'\b{re.escape(key)}\b', label):
#             return value
    
#     return None


# def _enhance_with_layout(fields: Dict, layout_elements: List[Dict]) -> Dict:
#     """Add bounding box information from layout"""
#     for field_name, field_data in fields.items():
#         value = field_data.get('value', '')
        
#         for elem in layout_elements:
#             elem_text = elem.get('text', '').lower()
#             value_lower = value.lower()
            
#             if value_lower in elem_text or elem_text in value_lower:
#                 if ('bounding_box' not in field_data or 
#                     field_data.get('confidence', 0) < elem.get('confidence', 0)):
#                     field_data['bounding_box'] = {
#                         'x_min': elem['box'][0],
#                         'y_min': elem['box'][1],
#                         'x_max': elem['box'][2],
#                         'y_max': elem['box'][3]
#                     }
#                 break
    
#     return fields

"""
Field Extraction Agent (SAFE FALLBACK MODE)

IMPORTANT:
- This agent MUST NOT override deterministic extraction
- It runs ONLY for missing fields
- It MUST NOT extract insured_name, mailing_address, property_address
- It is intentionally conservative
"""

import re
from typing import Dict, List

# ============================================================
# FIELDS THIS AGENT IS ALLOWED TO EXTRACT (STRICT)
# ============================================================

ALLOWED_FIELDS = {
    "policy_number",
    "loan_number",
    "total_premium",
    "balance_due",
    "deductible",
    "agent",
    "agent_phone",
}

# ============================================================
# MAIN ENTRY
# ============================================================

def extract_additional_fields(
    lines: List[str],
    existing_fields: Dict[str, Dict]
) -> Dict[str, Dict]:
    """
    Extract ONLY missing fields using generic regex.
    Never overrides existing fields.
    """

    results: Dict[str, Dict] = {}

    missing = ALLOWED_FIELDS - set(existing_fields.keys())
    if not missing:
        return results

    text = " ".join(lines)

    if "policy_number" in missing:
        val = _extract_policy_number(lines)
        if val:
            results["policy_number"] = val

    if "loan_number" in missing:
        val = _extract_loan_number(lines)
        if val:
            results["loan_number"] = val

    if "total_premium" in missing:
        val = _extract_total_premium(text)
        if val:
            results["total_premium"] = val

    if "balance_due" in missing:
        val = _extract_balance_due(text)
        if val:
            results["balance_due"] = val

    if "deductible" in missing:
        val = _extract_deductible(text)
        if val:
            results["deductible"] = val

    if "agent" in missing:
        val = _extract_agent(lines)
        if val:
            results["agent"] = val

    if "agent_phone" in missing:
        val = _extract_agent_phone(text)
        if val:
            results["agent_phone"] = val

    return results

# ============================================================
# SAFE REGEX HELPERS
# ============================================================

def _extract_policy_number(lines):
    for i, l in enumerate(lines):
        m = re.search(r'policy\s*number[:\s]+([A-Z0-9\-]{6,})', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": 0.85}

        # multiline policy number (Erie / Encompass style)
        if "policy number" in l.lower() and i + 1 < len(lines):
            nxt = lines[i + 1]
            m2 = re.search(r'\b[A-Z0-9]{6,}\b', nxt)
            if m2:
                return {"value": m2.group(0), "confidence": 0.83}

    return None


def _extract_loan_number(lines):
    for l in lines:
        m = re.search(r'loan\s*number[:\s]+([A-Z0-9\-]{5,})', l, re.I)
        if m:
            return {"value": m.group(1), "confidence": 0.85}
    return None


def _extract_total_premium(text):
    m = re.search(r'total\s+premium[:\s]*\$([\d,]+)', text, re.I)
    if m:
        return {"value": f"${m.group(1)}", "confidence": 0.80}
    return None


def _extract_balance_due(text):
    m = re.search(r'(balance\s+due|amount\s+due)\s*\$([\d,]+)', text, re.I)
    if m:
        return {"value": f"${m.group(2)}", "confidence": 0.80}
    return None


def _extract_deductible(text):
    m = re.search(r'deductible[:\s]*\$([\d,]+)', text, re.I)
    if m:
        return {"value": f"${m.group(1)}", "confidence": 0.78}
    return None


def _extract_agent(lines):
    for i, l in enumerate(lines):
        if "agent:" in l.lower() or "producer:" in l.lower():
            name = l.split(":", 1)[-1].strip()
            if name and not any(char.isdigit() for char in name):
                return {"value": name, "confidence": 0.80}
    return None


def _extract_agent_phone(text):
    m = re.search(r'\(?\d{3}\)?[-\s]\d{3}[-\s]\d{4}', text)
    if m:
        return {"value": m.group(0), "confidence": 0.85}
    return None
