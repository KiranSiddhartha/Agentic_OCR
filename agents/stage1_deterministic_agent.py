# agents/stage1_deterministic_agent.py
# Stage 1: Deterministic Extraction using Regex + Hard Anchors
# 100% accuracy for clearly labeled fields

import re
from typing import List, Dict


def extract_with_regex(lines: List[str], layout_elements: List[Dict] = None) -> Dict[str, Dict]:
    """
    Stage 1: Extract fields using deterministic regex patterns.
    
    This stage targets "hard anchors" - fields with clear labels like:
    - "Policy Number: ABC123"
    - "Insured Name: John Smith"
    
    Returns:
        {
            "policy_number": {
                "value": "ABC123",
                "confidence": 0.98,
                "source": "deterministic_regex",
                "pattern_matched": "policy_number_colon"
            }
        }
    """
    
    text = "\n".join(lines)
    fields = {}
    
    # ============================================================
    # POLICY NUMBER (Multiple Hard Anchor Patterns)
    # ============================================================
    policy_patterns = [
        # Pattern 1: "Policy Number: XXX"
        (r'Policy\s+Number[:\s]+([A-Z0-9\-]{6,30})', 'policy_number_colon', 0.98),
        
        # Pattern 2: "Policy No: XXX"
        (r'Policy\s+No\.?[:\s]+([A-Z0-9\-]{6,30})', 'policy_no_colon', 0.97),
        
        # Pattern 3: "Policy #: XXX"
        (r'Policy\s*#[:\s]+([A-Z0-9\-]{6,30})', 'policy_hash', 0.96),
        
        # Pattern 4: "Pol. No.: XXX"
        (r'Pol\.?\s+No\.?[:\s]+([A-Z0-9\-]{6,30})', 'pol_no_colon', 0.95),
    ]
    
    for pattern, pattern_name, confidence in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if _validate_policy_number(value):
                fields["policy_number"] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "deterministic_regex",
                    "pattern_matched": pattern_name
                }
                break
    
    # ============================================================
    # INSURED NAME (Hard Anchor)
    # ============================================================
    name_patterns = [
        # Pattern 1: "Named Insured: John Smith"
        (r'Named\s+Insured[:\s]+([A-Z][A-Za-z\s\.]{3,60}?)(?:\n|$)', 'named_insured_colon', 0.97),
        
        # Pattern 2: "Insured Name: John Smith"
        (r'Insured\s+Name[:\s]+([A-Z][A-Za-z\s\.]{3,60}?)(?:\n|$)', 'insured_name_colon', 0.96),
        
        # Pattern 3: "Policyholder: John Smith"
        (r'Policyholder[:\s]+([A-Z][A-Za-z\s\.]{3,60}?)(?:\n|$)', 'policyholder_colon', 0.95),
    ]
    
    for pattern, pattern_name, confidence in name_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            value = re.sub(r'\s+', ' ', match.group(1).strip())
            if _validate_name(value):
                fields["insured_name"] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "deterministic_regex",
                    "pattern_matched": pattern_name
                }
                break
    
    # ============================================================
    # DATES (Hard Anchor)
    # ============================================================
    
    # Effective Date
    effective_patterns = [
        (r'Effective\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'effective_date_colon', 0.97),
        (r'Policy\s+Effective[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'policy_effective_colon', 0.96),
        (r'Inception\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'inception_date_colon', 0.95),
    ]
    
    for pattern, pattern_name, confidence in effective_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields["effective_date"] = {
                "value": match.group(1),
                "confidence": confidence,
                "source": "deterministic_regex",
                "pattern_matched": pattern_name
            }
            break
    
    # Expiration Date
    expiration_patterns = [
        (r'Expiration\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'expiration_date_colon', 0.97),
        (r'Policy\s+Expires?[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'policy_expires_colon', 0.96),
        (r'Through[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 'through_date', 0.94),
    ]
    
    for pattern, pattern_name, confidence in expiration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields["expiration_date"] = {
                "value": match.group(1),
                "confidence": confidence,
                "source": "deterministic_regex",
                "pattern_matched": pattern_name
            }
            break
    
    # ============================================================
    # PREMIUM (Hard Anchor)
    # ============================================================
    premium_patterns = [
        (r'Total\s+Premium[:\s]+\$\s*([\d,]+\.?\d*)', 'total_premium_colon', 0.96),
        (r'Premium[:\s]+\$\s*([\d,]+\.?\d*)', 'premium_colon', 0.94),
        (r'Annual\s+Premium[:\s]+\$\s*([\d,]+\.?\d*)', 'annual_premium_colon', 0.95),
    ]
    
    for pattern, pattern_name, confidence in premium_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields["total_premium"] = {
                "value": f"${match.group(1)}",
                "confidence": confidence,
                "source": "deterministic_regex",
                "pattern_matched": pattern_name
            }
            break
    
    # ============================================================
    # ADDRESS (Hard Anchor)
    # ============================================================
    address_patterns = [
        (r'Mailing\s+Address[:\s]+([^\n]+(?:\n[^\n]{5,})?)', 'mailing_address_colon', 0.95),
        (r'Property\s+Address[:\s]+([^\n]+(?:\n[^\n]{5,})?)', 'property_address_colon', 0.94),
        (r'Address[:\s]+([^\n]+(?:\n[^\n]{5,})?)', 'address_colon', 0.92),
    ]
    
    for pattern, pattern_name, confidence in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = re.sub(r'\s+', ' ', match.group(1).strip())
            if _validate_address(value):
                # Use specific field name based on pattern
                field_name = "property_address" if "Property" in pattern_name else "mailing_address"
                
                fields[field_name] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "deterministic_regex",
                    "pattern_matched": pattern_name
                }
                break
    
    # ============================================================
    # COVERAGE LIMITS (Hard Anchor)
    # ============================================================
    dwelling_patterns = [
        (r'Dwelling\s+(?:Coverage|Limit)[:\s]+\$\s*([\d,]+)', 'dwelling_coverage_colon', 0.95),
        (r'Coverage\s+A[:\s]+\$\s*([\d,]+)', 'coverage_a', 0.94),
    ]
    
    for pattern, pattern_name, confidence in dwelling_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields["dwelling_coverage"] = {
                "value": f"${match.group(1)}",
                "confidence": confidence,
                "source": "deterministic_regex",
                "pattern_matched": pattern_name
            }
            break
    
    # ============================================================
    # LOAN NUMBER (Hard Anchor)
    # ============================================================
    loan_patterns = [
        (r'Loan\s+Number[:\s]+([A-Z0-9\-]{6,30})', 'loan_number_colon', 0.96),
        (r'Loan\s+No\.?[:\s]+([A-Z0-9\-]{6,30})', 'loan_no_colon', 0.95),
    ]
    
    for pattern, pattern_name, confidence in loan_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) >= 6 and any(c.isdigit() for c in value):
                fields["loan_number"] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "deterministic_regex",
                    "pattern_matched": pattern_name
                }
                break
    
    # ============================================================
    # AGENT NAME (Hard Anchor)
    # ============================================================
    agent_patterns = [
        (r'Agent[:\s]+([A-Z][A-Za-z\s\.]{3,40}?)(?:\n|$)', 'agent_colon', 0.93),
        (r'Producer[:\s]+([A-Z][A-Za-z\s\.]{3,40}?)(?:\n|$)', 'producer_colon', 0.92),
    ]
    
    for pattern, pattern_name, confidence in agent_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            value = re.sub(r'\s+', ' ', match.group(1).strip())
            if _validate_name(value):
                fields["agent"] = {
                    "value": value,
                    "confidence": confidence,
                    "source": "deterministic_regex",
                    "pattern_matched": pattern_name
                }
                break
    
    # ============================================================
    # ENHANCE WITH LAYOUT (IF AVAILABLE)
    # ============================================================
    if layout_elements:
        fields = _enhance_with_layout_boxes(fields, layout_elements)
    
    return fields


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _validate_policy_number(value: str) -> bool:
    """Validate policy number format"""
    if not value or len(value) < 6:
        return False
    
    # Must contain at least some digits
    if sum(c.isdigit() for c in value) < 3:
        return False
    
    # Shouldn't be all letters
    if value.isalpha():
        return False
    
    return True


def _validate_name(value: str) -> bool:
    """Validate insured name"""
    if not value or len(value) < 3:
        return False
    
    # Shouldn't contain numbers
    if any(c.isdigit() for c in value):
        return False
    
    # Shouldn't contain common non-name words
    invalid_words = ['policy', 'insurance', 'number', 'date', 'coverage']
    if any(word in value.lower() for word in invalid_words):
        return False
    
    # Should have at least one space (first + last name)
    if ' ' not in value:
        return False
    
    return True


def _validate_address(value: str) -> bool:
    """Validate address format"""
    if not value or len(value) < 10:
        return False
    
    # Should contain at least one number
    if not any(c.isdigit() for c in value):
        return False
    
    return True


# ============================================================
# LAYOUT ENHANCEMENT
# ============================================================

def _enhance_with_layout_boxes(fields: Dict, layout_elements: List[Dict]) -> Dict:
    """
    Add bounding boxes to extracted fields using layout information.
    This helps with visual highlighting in the UI.
    """
    
    for field_name, field_data in fields.items():
        value = field_data.get("value", "")
        
        # Find matching layout element
        for elem in layout_elements:
            if value.lower() in elem["text"].lower():
                field_data["bounding_box"] = {
                    "x_min": elem["box"][0],
                    "y_min": elem["box"][1],
                    "x_max": elem["box"][2],
                    "y_max": elem["box"][3]
                }
                break
    
    return fields