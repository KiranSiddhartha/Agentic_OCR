# import re

# def extract_fields(lines):
#     """
#     FAST field extraction using regex only.
#     Removed LLM (slow, adds errors, reduces accuracy).
#     """
#     text = "\n".join(lines)
#     structured = {}
    
#     # Remove common OCR artifacts
#     text_clean = text.replace('|', 'l').replace('0O', 'O')
    
#     # Special handling for confidence calculation
#     confidence_scores = {}

#     # -----------------------------
#     # POLICY NUMBER - Multiple patterns for reliability
#     # -----------------------------
#     policy_patterns = [
#         r'(?:Policy|Polic|POLICY)\s*(?:Number|No\.?|NUM|\#)[:\s]*([A-Z0-9\-]{8,30})',
#         r'(?:Policy|Polic|POLICY)(?:\s*Number)?(?:\s*No)?[:\s#-]*([A-Z0-9\-]{8,30})',
#         r'(?:POLICY\s+(?:NO|#|NUM)[.:]?\s*)([A-Z0-9\-]{8,30})',
#         r'P(?:o|0|O)l(?:i|1|l)c(?:y|i)\s*(?:Number|No)[:\s]*([A-Z0-9\-]{8,30})',  # Common blurred confusions
#     ]
    
#     for pattern in policy_patterns:
#         m = re.search(pattern, text_clean, re.IGNORECASE)
#         if m:
#             policy_num = m.group(1).strip()
#             if len(policy_num) >= 8:
#                 structured["policy_number"] = {"value": policy_num}
#                 confidence_scores["policy_number"] = 0.95
#                 break

#     # Fallback: Look for any significant alphanumeric string after "Policy"
#     if "policy_number" not in structured:
#         m = re.search(r'(?:Policy|Polic)[^A-Z0-9]*([A-Z0-9\-]{8,30})', text_clean, re.IGNORECASE)
#         if m:
#             policy_num = m.group(1).strip()
#             if len(policy_num) >= 8 and not policy_num.isalpha():
#                 structured["policy_number"] = {"value": policy_num}
#                 confidence_scores["policy_number"] = 0.85

#     # -----------------------------
#     # DATES - Multiple formats and patterns
#     # -----------------------------
#     date_patterns = [
#         r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',  # MM/DD/YYYY or M/D/YYYY
#         r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',  # YYYY/MM/DD
#         r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',  # Month DD, YYYY
#     ]
    
#     dates = []
#     for pattern in date_patterns:
#         found_dates = re.findall(pattern, text_clean, re.IGNORECASE)
#         for date_match in found_dates:
#             if isinstance(date_match, tuple):
#                 dates.append('/'.join(date_match))
#             else:
#                 dates.append(date_match)
    
#     # Remove duplicates while preserving order
#     dates = list(dict.fromkeys(dates))

#     if len(dates) >= 1:
#         structured["effective_date"] = {"value": dates[0]}
#         confidence_scores["effective_date"] = 0.90

#     if len(dates) >= 2:
#         structured["expiration_date"] = {"value": dates[1]}
#         confidence_scores["expiration_date"] = 0.90

#     # Fallback: Look for dates after "effective" and "expiration" keywords
#     if "effective_date" not in structured:
#         m = re.search(r'(?:Effective|Eff|EFF)[^\d]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', text_clean, re.IGNORECASE)
#         if m:
#             structured["effective_date"] = {"value": m.group(1)}
#             confidence_scores["effective_date"] = 0.85

#     if "expiration_date" not in structured:
#         m = re.search(r'(?:Expiration|Expir|Exp)[^\d]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', text_clean, re.IGNORECASE)
#         if m:
#             structured["expiration_date"] = {"value": m.group(1)}
#             confidence_scores["expiration_date"] = 0.85

#     # -----------------------------
#     # INSURED NAME - Multiple patterns for robustness
#     # -----------------------------
#     name_patterns = [
#         r'(?:Named|Name)[\s:]\s*Insured[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#         r'(?:INSURED|INSURED\s+NAME)[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#         r'(?:Insured|INSURED)\s+(?:Name|NAME)[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#         r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#         r'Insured[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#         # For blurred images with common confusions
#         r'(?:1nsured|lnsured|Insure)[:\s]+([A-Z][A-Za-z\s]{5,60}?)(?:\n|$)',
#     ]

#     for pattern in name_patterns:
#         m = re.search(pattern, text_clean, re.MULTILINE)
#         if m:
#             insured_name = m.group(1).strip()
#             # Clean up common OCR artifacts in names
#             insured_name = re.sub(r'[|]', 'l', insured_name)
#             if len(insured_name) > 5:  # Valid name should be longer than 5 chars
#                 structured["insured_name"] = {"value": insured_name}
#                 confidence_scores["insured_name"] = 0.90
#                 break

#     # Fallback: Extract first significant capitalized phrase
#     if "insured_name" not in structured:
#         m = re.search(r'(?:Named\s+)?Insured[^A-Z]([A-Z][A-Za-z\s]{8,60})', text_clean)
#         if m:
#             insured_name = m.group(1).strip()
#             if len(insured_name) > 5:
#                 structured["insured_name"] = {"value": insured_name}
#                 confidence_scores["insured_name"] = 0.80

#     # Add confidence scores to extracted fields
#     for field_name, score in confidence_scores.items():
#         if field_name in structured:
#             structured[field_name]["confidence"] = score

#     return structured


# agents/field_extraction_agent.py
# Enhanced field extraction with relation support
import re
from typing import List, Dict, Optional, Tuple


def extract_fields(lines: List[str]) -> Dict[str, Dict]:
    """
    Standard regex-based field extraction
    Works with text lines from OCR
    """
    text = "\n".join(lines)
    structured = {}

    # === POLICY NUMBER ===
    policy_patterns = [
        r'Policy\s*(?:number|#|no\.?)[:\s]*(\d{6,})',
        r'Policy\s*(?:Number|No\.?)[:\s]*([A-Z0-9\-]{6,30})',
        r'Policy[:\s]+([A-Z0-9\-]{8,30})',
    ]

    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            structured["policy_number"] = {
                "value": match.group(1).strip(),
                "confidence": 0.90,
                "source": "regex"
            }
            break

    # === DATES ===
    effective_match = re.search(
        r'(?:effective|beginning|from)[^0-9]*(\d{1,2}/\d{1,2}/\d{4})',
        text,
        re.IGNORECASE
    )
    if effective_match:
        structured["effective_date"] = {
            "value": effective_match.group(1).strip(),
            "confidence": 0.92,
            "source": "regex"
        }

    expiration_match = re.search(
        r'(?:expiration|through|to|ending)[^0-9]*(\d{1,2}/\d{1,2}/\d{4})',
        text,
        re.IGNORECASE
    )
    if expiration_match:
        structured["expiration_date"] = {
            "value": expiration_match.group(1).strip(),
            "confidence": 0.92,
            "source": "regex"
        }

    # Fallback: Extract all dates
    if "effective_date" not in structured or "expiration_date" not in structured:
        all_dates = re.findall(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', text)
        if all_dates and "effective_date" not in structured:
            structured["effective_date"] = {
                "value": all_dates[0],
                "confidence": 0.75,
                "source": "regex_fallback"
            }
        if len(all_dates) > 1 and "expiration_date" not in structured:
            structured["expiration_date"] = {
                "value": all_dates[1],
                "confidence": 0.75,
                "source": "regex_fallback"
            }

    # === INSURED NAME ===
    name_patterns = [
        r'(?:Policyholder|Named\s+Insured|Insured)[:\s]+([A-Z][A-Za-z\s]{3,60}?)(?:\n|Mailing)',
        r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s]{5,60})',
        r'Insured[:\s]+([A-Z][A-Za-z\s]{5,60})',
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            name = re.sub(r'\s+', ' ', match.group(1).strip())
            if len(name) > 3 and not any(word in name.lower() for word in ['policy', 'number', 'date']):
                structured["insured_name"] = {
                    "value": name,
                    "confidence": 0.88,
                    "source": "regex"
                }
                break

    # === ADDRESS ===
    address_match = re.search(
        r'(?:Mailing\s+address|Address)[:\s]+([^\n]+(?:\n[^\n]{5,})?)',
        text,
        re.IGNORECASE
    )
    if address_match:
        address = re.sub(r'\s+', ' ', address_match.group(1).strip())
        structured["mailing_address"] = {
            "value": address,
            "confidence": 0.85,
            "source": "regex"
        }

    # === PREMIUM / COVERAGE ===
    premium_match = re.search(r'(?:Total|Premium)[^\$]*\$\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if premium_match:
        structured["total_premium"] = {
            "value": f"${premium_match.group(1)}",
            "confidence": 0.87,
            "source": "regex"
        }

    coverage_match = re.search(r'(?:Dwelling|Coverage)[^\$]*\$\s*([\d,]+)', text, re.IGNORECASE)
    if coverage_match:
        structured["dwelling_coverage"] = {
            "value": f"${coverage_match.group(1)}",
            "confidence": 0.86,
            "source": "regex"
        }

    return structured


def extract_fields_with_relations(
    lines: List[str],
    layout_elements: List[Dict],
    relations: List[Tuple]
) -> Dict[str, Dict]:
    """
    Enhanced extraction using layout + relations
    """
    fields = extract_fields(lines)

    for relation in relations:
        if len(relation) != 4:
            continue

        entity1, rel_type, entity2, rel_conf = relation

        if rel_type == 'HAS_VALUE':
            field_name = _normalize_field_name(entity1)

            if not field_name:
                continue

            if field_name not in fields:
                fields[field_name] = {
                    'value': entity2,
                    'confidence': rel_conf * 0.9,
                    'source': 'relation_extraction'
                }
            else:
                if fields[field_name].get('confidence', 0) < rel_conf:
                    fields[field_name]['confidence'] = min(
                        fields[field_name]['confidence'] + 0.05,
                        0.98
                    )

    if layout_elements:
        fields = _enhance_with_layout(fields, layout_elements)

    return fields


def _normalize_field_name(label: str) -> Optional[str]:
    if not label:
        return None

    label = label.lower().strip().rstrip(':')

    field_map = {
        'policy number': 'policy_number',
        'policy no': 'policy_number',
        'policy #': 'policy_number',
        'insured name': 'insured_name',
        'named insured': 'insured_name',
        'policyholder': 'insured_name',
        'effective date': 'effective_date',
        'expiration date': 'expiration_date',
        'mailing address': 'mailing_address',
        'property address': 'property_address',
        'total premium': 'total_premium',
        'dwelling coverage': 'dwelling_coverage',
        'agent': 'agent',
    }

    if label in field_map:
        return field_map[label]

    for key, value in field_map.items():
        if re.search(rf'\b{re.escape(key)}\b', label):
            return value

    return None


def _enhance_with_layout(fields: Dict, layout_elements: List[Dict]) -> Dict:
    for field_name, field_data in fields.items():
        value = field_data.get('value', '')

        for elem in layout_elements:
            if value.lower() in elem['text'].lower():
                if (
                    'bounding_box' not in field_data
                    or field_data.get('confidence', 0) < elem.get('confidence', 0)
                ):
                    field_data['bounding_box'] = {
                        'x_min': elem['box'][0],
                        'y_min': elem['box'][1],
                        'x_max': elem['box'][2],
                        'y_max': elem['box'][3]
                    }
                break

    return fields
