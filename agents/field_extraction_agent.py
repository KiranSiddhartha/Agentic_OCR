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
# LAYOUT-AWARE: Extracts from properly aligned text
import re


def extract_fields(lines):
    """
    LAYOUT-AWARE field extraction.
    Works with properly aligned text from layout-aware OCR.
    """
    text = "\n".join(lines)
    structured = {}
    
    # === POLICY NUMBER ===
    policy_patterns = [
        r'Policy\s*(?:number|#)[:\s]*(\d{6,})',
        r'Policy\s*(?:Number|No\.?)[:\s]*([A-Z0-9\-]{6,30})',
        r'Policy[:\s]+([A-Z0-9\-]{8,30})',
    ]
    
    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            structured["policy_number"] = {"value": match.group(1).strip()}
            break
    
    # === DATES ===
    # Look for specific date patterns with context
    effective_match = re.search(
        r'(?:effective|beginning|from)[^0-9]*(\d{1,2}/\d{1,2}/\d{4}|\w+\s+\d{1,2},?\s+\d{4})',
        text,
        re.IGNORECASE
    )
    if effective_match:
        structured["effective_date"] = {"value": effective_match.group(1).strip()}
    
    expiration_match = re.search(
        r'(?:expiration|through|to|ending)[^0-9]*(\d{1,2}/\d{1,2}/\d{4}|\w+\s+\d{1,2},?\s+\d{4})',
        text,
        re.IGNORECASE
    )
    if expiration_match:
        structured["expiration_date"] = {"value": expiration_match.group(1).strip()}
    
    # Fallback: Extract all dates
    if "effective_date" not in structured or "expiration_date" not in structured:
        all_dates = re.findall(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', text)
        if all_dates and "effective_date" not in structured:
            structured["effective_date"] = {"value": all_dates[0]}
        if len(all_dates) > 1 and "expiration_date" not in structured:
            structured["expiration_date"] = {"value": all_dates[1]}
    
    # === INSURED NAME ===
    name_patterns = [
        r'(?:Policyholder|Named\s+Insured|Insured)[:\s]+([A-Z][A-Za-z\s]{3,60}?)(?:\n|Mailing)',
        r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s]{5,60})',
        r'Insured[:\s]+([A-Z][A-Za-z\s]{5,60})',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up
            name = re.sub(r'\s+', ' ', name)
            if len(name) > 3 and not any(word in name.lower() for word in ['policy', 'number', 'date']):
                structured["insured_name"] = {"value": name}
                break
    
    # === ADDRESS ===
    # Look for mailing address
    address_match = re.search(
        r'(?:Mailing\s+address|Address)[:\s]+([^\n]+(?:\n[^\n]{5,})?)',
        text,
        re.IGNORECASE
    )
    if address_match:
        address = address_match.group(1).strip()
        address = re.sub(r'\s+', ' ', address)
        structured["mailing_address"] = {"value": address}
    
    # === PREMIUM/COVERAGE AMOUNTS ===
    # Extract from aligned columns (look for $ amounts)
    premium_match = re.search(r'(?:Total|Premium)[^\$]*\$\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if premium_match:
        structured["total_premium"] = {"value": f"${premium_match.group(1)}"}
    
    coverage_match = re.search(r'(?:Dwelling|Coverage)[^\$]*\$\s*([\d,]+)', text, re.IGNORECASE)
    if coverage_match:
        structured["dwelling_coverage"] = {"value": f"${coverage_match.group(1)}"}
    
    # === PROPERTY ADDRESS ===
    property_match = re.search(
        r'(?:Coverage\s+Detail\s+for|Property)[:\s]+([0-9]+\s+[A-Za-z\s,]+\d{5})',
        text,
        re.IGNORECASE
    )
    if property_match:
        structured["property_address"] = {"value": property_match.group(1).strip()}
    
    # === AGENT ===
    agent_match = re.search(
        r'(?:Agent|Agency)[:\s]+([A-Z][A-Za-z\s&]{5,60}?)(?:\n|\d)',
        text,
        re.IGNORECASE
    )
    if agent_match:
        agent = agent_match.group(1).strip()
        structured["agent"] = {"value": agent}
    
    # === PHONE NUMBERS ===
    phones = re.findall(r'\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}', text)
    if phones:
        structured["phone_numbers"] = {"value": ", ".join(phones[:2])}  # First 2 phones
    
    return structured


# # agents/field_extraction_agent.py
# # HYBRID: Fast regex + context validation for accuracy
# import re
# from typing import List, Dict, Optional


# def extract_fields(lines: List[str]) -> Dict[str, Dict]:
#     """
#     Hybrid extraction: Fast regex + context validation.
    
#     Strategy:
#     1. Try fast regex patterns first
#     2. If confidence is low, use context-aware extraction
#     3. Return best result with confidence score
#     """
    
#     # Quick extraction first (fast)
#     quick_fields = extract_fields_quick(lines)
    
#     # Context-aware extraction for low-confidence fields (accurate)
#     final_fields = {}
    
#     for field_name in ["policy_number", "effective_date", "expiration_date", 
#                        "insured_name", "property_address"]:
        
#         # Check if quick extraction succeeded with high confidence
#         if field_name in quick_fields:
#             conf = quick_fields[field_name].get("confidence", 0.0)
            
#             if conf >= 0.85:
#                 # High confidence - use quick result
#                 final_fields[field_name] = quick_fields[field_name]
#             else:
#                 # Low confidence - use context-aware extraction
#                 context_result = extract_with_context(lines, field_name)
#                 if context_result:
#                     final_fields[field_name] = context_result
#                 else:
#                     # Fallback to quick result
#                     final_fields[field_name] = quick_fields[field_name]
#         else:
#             # Field not found - try context-aware extraction
#             context_result = extract_with_context(lines, field_name)
#             if context_result:
#                 final_fields[field_name] = context_result
    
#     return final_fields


# def extract_fields_quick(lines: List[str]) -> Dict[str, Dict]:
#     """
#     Fast regex-based extraction (your current approach).
#     Returns fields with estimated confidence.
#     """
#     text = "\n".join(lines)
#     structured = {}
    
#     # === POLICY NUMBER ===
#     policy_patterns = [
#         (r'Policy\s*(?:Number|#)[:\s]*([A-Z]?\d{8,})', 0.9),
#         (r'Policy[:\s]+([A-Z0-9\-]{8,30})', 0.8),
#         (r'\b([A-Z]{1,3}\d{7,15})\b', 0.7),  # Lower confidence for standalone
#     ]
    
#     for pattern, base_conf in policy_patterns:
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             policy_num = match.group(1).strip()
#             if len(policy_num) >= 8:
#                 structured["policy_number"] = {
#                     "value": policy_num,
#                     "confidence": base_conf
#                 }
#                 break
    
#     # === DATES ===
#     date_matches = re.findall(r'(\d{2}/\d{2}/\d{4})', text)
    
#     # Try labeled dates first
#     effective_match = re.search(
#         r'(?:effective|beginning)[^0-9]*(\d{1,2}/\d{1,2}/\d{4})',
#         text,
#         re.IGNORECASE
#     )
#     if effective_match:
#         structured["effective_date"] = {
#             "value": effective_match.group(1),
#             "confidence": 0.9
#         }
#     elif date_matches:
#         structured["effective_date"] = {
#             "value": date_matches[0],
#             "confidence": 0.6  # Low confidence - no label
#         }
    
#     expiration_match = re.search(
#         r'(?:expiration|through)[^0-9]*(\d{1,2}/\d{1,2}/\d{4})',
#         text,
#         re.IGNORECASE
#     )
#     if expiration_match:
#         structured["expiration_date"] = {
#             "value": expiration_match.group(1),
#             "confidence": 0.9
#         }
#     elif len(date_matches) > 1:
#         structured["expiration_date"] = {
#             "value": date_matches[1],
#             "confidence": 0.6  # Low confidence - no label
#         }
    
#     # === INSURED NAME ===
#     name_patterns = [
#         (r'(?:Insured|Named\s+Insured)[^:]*:[^\n]*\n\s*([A-Z][A-Z\s,&]{3,60}?)\n', 0.9),
#         (r'(?:Policyholder)[^:]*:[^\n]*\n\s*([A-Z][A-Z\s,&]{3,60}?)\n', 0.85),
#     ]
    
#     for pattern, base_conf in name_patterns:
#         match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
#         if match:
#             name = match.group(1).strip()
#             name = re.sub(r'\s+', ' ', name)
#             if len(name) > 3:
#                 structured["insured_name"] = {
#                     "value": name,
#                     "confidence": base_conf
#                 }
#                 break
    
#     # === PROPERTY ADDRESS ===
#     address_patterns = [
#         (r'(?:Coverage\s+Detail\s+for)[:\s]+([^\n]+)', 0.9),
#         (r'(?:Property\s+Address)[:\s]+([^\n]+)', 0.85),
#     ]
    
#     for pattern, base_conf in address_patterns:
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             addr = match.group(1).strip()
#             if len(addr) > 10 and any(c.isdigit() for c in addr):
#                 structured["property_address"] = {
#                     "value": addr,
#                     "confidence": base_conf
#                 }
#                 break
    
#     return structured


# def extract_with_context(lines: List[str], field_name: str) -> Optional[Dict]:
#     """
#     Context-aware extraction for specific field.
#     Uses surrounding lines to validate extraction.
#     """
    
#     if field_name == "policy_number":
#         return extract_policy_number_with_context(lines)
#     elif field_name == "insured_name":
#         return extract_name_with_context(lines)
#     elif field_name == "property_address":
#         return extract_property_address_with_context(lines)
#     elif field_name in ["effective_date", "expiration_date"]:
#         dates = extract_dates_with_context(lines)
#         if field_name in dates:
#             value, conf = dates[field_name]
#             return {"value": value, "confidence": conf}
    
#     return None


# def get_context_window(lines: List[str], target_idx: int, window_size: int = 3) -> Dict:
#     """Get surrounding lines for context"""
#     before = lines[max(0, target_idx - window_size):target_idx]
#     after = lines[target_idx + 1:min(len(lines), target_idx + window_size + 1)]
    
#     return {
#         "before": before,
#         "target": lines[target_idx],
#         "after": after,
#         "all": before + [lines[target_idx]] + after
#     }


# def extract_policy_number_with_context(lines: List[str]) -> Optional[Dict]:
#     """Extract policy number using context validation"""
#     candidates = []
    
#     for i, line in enumerate(lines):
#         line_lower = line.lower()
        
#         if any(kw in line_lower for kw in ["policy number", "policy no", "policy#"]):
#             context = get_context_window(lines, i, window_size=3)
            
#             # Check same line
#             nums = re.findall(r'\b[A-Z0-9\-]{8,25}\b', line)
#             for num in nums:
#                 if not is_date_like(num):
#                     conf = 0.9
#                     candidates.append((num, conf))
            
#             # Check next 2 lines
#             for next_line in context["after"][:2]:
#                 nums = re.findall(r'\b[A-Z0-9\-]{8,25}\b', next_line)
#                 for num in nums:
#                     if not is_date_like(num) and not is_phone_like(num):
#                         # Verify not a loan number
#                         context_text = ' '.join(context["all"]).lower()
#                         if "loan" not in context_text or "policy" in context_text:
#                             conf = 0.85
#                             candidates.append((num, conf))
    
#     if candidates:
#         candidates.sort(key=lambda x: x[1], reverse=True)
#         return {"value": candidates[0][0], "confidence": candidates[0][1]}
    
#     return None


# def extract_dates_with_context(lines: List[str]) -> Dict[str, tuple]:
#     """Extract dates using context to determine type"""
#     dates = {}
    
#     for i, line in enumerate(lines):
#         date_matches = re.findall(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', line)
        
#         if date_matches:
#             context = get_context_window(lines, i)
#             context_text = ' '.join(context["before"] + [line]).lower()
            
#             for date_str in date_matches:
#                 if any(kw in context_text for kw in ["effective", "beginning", "from"]):
#                     if "effective_date" not in dates:
#                         dates["effective_date"] = (date_str, 0.9)
                
#                 elif any(kw in context_text for kw in ["expiration", "through", "to"]):
#                     if "expiration_date" not in dates:
#                         dates["expiration_date"] = (date_str, 0.9)
    
#     return dates


# def extract_name_with_context(lines: List[str]) -> Optional[Dict]:
#     """Extract insured name using context"""
#     for i, line in enumerate(lines):
#         line_lower = line.lower()
        
#         if any(kw in line_lower for kw in ["insured", "policyholder", "named insured"]):
#             context = get_context_window(lines, i, window_size=4)
            
#             # Check same line (after colon)
#             if ":" in line:
#                 parts = line.split(":", 1)
#                 if len(parts) == 2:
#                     candidate = parts[1].strip()
#                     candidate = re.split(r'\s{2,}', candidate)[0].strip()
                    
#                     if is_valid_name(candidate):
#                         return {"value": candidate, "confidence": 0.9}
            
#             # Check next lines
#             for next_line in context["after"][:3]:
#                 if any(x in next_line.lower() for x in 
#                        ["address", "policy", "number", "date"]):
#                     break
                
#                 if is_valid_name(next_line):
#                     return {"value": next_line.strip(), "confidence": 0.85}
    
#     return None


# def extract_property_address_with_context(lines: List[str]) -> Optional[Dict]:
#     """Extract property address using context"""
#     for i, line in enumerate(lines):
#         line_lower = line.lower()
        
#         # Skip mailing addresses
#         if any(kw in line_lower for kw in ["mailing", "po box", "p.o. box"]):
#             continue
        
#         if any(kw in line_lower for kw in ["property address", "coverage detail for"]):
#             context = get_context_window(lines, i, window_size=3)
            
#             if "coverage detail for" in line_lower:
#                 match = re.search(r'coverage\s*detail\s*for\s+(.+)', line, re.I)
#                 if match:
#                     return {"value": match.group(1).strip(), "confidence": 0.9}
            
#             # Check next lines
#             for next_line in context["after"][:3]:
#                 if has_address_pattern(next_line):
#                     return {"value": next_line.strip(), "confidence": 0.85}
    
#     return None


# # === HELPER FUNCTIONS ===

# def is_date_like(text: str) -> bool:
#     """Check if text looks like a date"""
#     return bool(re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$', text))


# def is_phone_like(text: str) -> bool:
#     """Check if text looks like a phone number"""
#     digits = re.sub(r'\D', '', text)
#     return len(digits) == 10 or len(digits) == 11


# def is_valid_name(text: str) -> bool:
#     """Validate if text looks like a name"""
#     if not text or len(text) < 3 or len(text) > 60:
#         return False
    
#     words = text.split()
#     if len(words) < 2:
#         return False
    
#     if not (text.istitle() or text.isupper()):
#         return False
    
#     return True


# def has_address_pattern(text: str) -> bool:
#     """Check if text looks like a street address"""
#     if not re.match(r'^\d', text):
#         return False
    
#     if not re.search(r'\b[A-Z]{2}\b|\b\d{5}\b', text):
#         return False
    
#     return any(suffix in text.upper() for suffix in [
#         "ST", "STREET", "AVE", "AVENUE", "RD", "ROAD", "BLVD", "LANE", "DR", "DRIVE"
#     ])