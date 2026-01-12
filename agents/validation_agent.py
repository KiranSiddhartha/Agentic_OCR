# agents/validation_agent.py
# Enhanced validation with Stage 4 arbitration logic

import re
from datetime import datetime
from typing import Dict, Tuple, Optional


# ============================================================
# FIELD-SPECIFIC VALIDATORS
# ============================================================

def validate_policy_number(policy_num: str) -> Tuple[bool, float]:
    """
    Validate policy number format.
    Returns: (is_valid, score)
    """
    if not policy_num:
        return False, 0.0
    
    # Policy numbers are typically 8-25 alphanumeric characters
    if len(policy_num) < 6 or len(policy_num) > 30:
        return False, 0.3
    
    # Should contain at least some digits
    has_digit = any(c.isdigit() for c in policy_num)
    has_letter = any(c.isalpha() for c in policy_num)
    
    # Best: mix of letters and numbers
    if has_digit and has_letter:
        return True, 0.95
    # Acceptable: all digits (some policies are numeric only)
    elif has_digit:
        return True, 0.85
    # Weak: all letters
    elif has_letter:
        return True, 0.70
    else:
        return False, 0.2


def validate_date(date_str: str) -> Tuple[bool, float]:
    """
    Validate date format (MM/DD/YYYY or similar).
    Returns: (is_valid, score)
    """
    if not date_str:
        return False, 0.0
    
    # Try to parse as actual date
    date_patterns = [
        (r'^(\d{1,2})/(\d{1,2})/(\d{4})$', '%m/%d/%Y'),
        (r'^(\d{4})/(\d{1,2})/(\d{1,2})$', '%Y/%m/%d'),
        (r'^(\d{1,2})-(\d{1,2})-(\d{4})$', '%m-%d-%Y'),
    ]
    
    for pattern, fmt in date_patterns:
        if re.match(pattern, date_str):
            try:
                parsed = datetime.strptime(date_str, fmt)
                year = parsed.year
                
                # Reasonable year range for insurance docs
                if 1990 < year < 2100:
                    return True, 0.95
                else:
                    return True, 0.70
            except ValueError:
                pass
    
    # Fallback: Accept if it matches date pattern
    if re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{4}$', date_str):
        return True, 0.75
    
    return False, 0.2


def validate_name(name_str: str) -> Tuple[bool, float]:
    """
    Validate insured name.
    Returns: (is_valid, score)
    """
    if not name_str or len(name_str) < 3:
        return False, 0.0
    
    # Should start with capital letter
    if not name_str[0].isupper():
        return False, 0.3
    
    # Should not contain digits
    if any(c.isdigit() for c in name_str):
        return False, 0.4
    
    # Should not contain common document keywords
    invalid_keywords = ['policy', 'insurance', 'number', 'date', 'coverage', 'premium']
    if any(keyword in name_str.lower() for keyword in invalid_keywords):
        return False, 0.3
    
    # Should have at least first + last name
    if ' ' not in name_str:
        return True, 0.60
    
    # Check for reasonable length
    if len(name_str) < 5:
        return True, 0.70
    elif len(name_str) > 60:
        return True, 0.60  # Possibly extracted too much
    else:
        return True, 0.90


def validate_premium(premium_str: str) -> Tuple[bool, float]:
    """
    Validate premium amount.
    Returns: (is_valid, score)
    """
    if not premium_str:
        return False, 0.0
    
    # Remove $ and commas
    clean = premium_str.replace('$', '').replace(',', '').strip()
    
    # Should be a number
    try:
        amount = float(clean)
        
        # Reasonable range for premiums
        if 0 < amount < 1000000:
            return True, 0.95
        elif amount >= 1000000:
            return True, 0.75  # Very high, but possible
        else:
            return False, 0.2
    except ValueError:
        return False, 0.1


def validate_address(address_str: str) -> Tuple[bool, float]:
    """
    Validate address format.
    Returns: (is_valid, score)
    """
    if not address_str or len(address_str) < 10:
        return False, 0.0
    
    # Should contain at least one number (street number)
    if not any(c.isdigit() for c in address_str):
        return False, 0.3
    
    # Should contain some letters
    if not any(c.isalpha() for c in address_str):
        return False, 0.2
    
    # Good addresses typically have certain keywords
    address_keywords = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 
                        'lane', 'ln', 'way', 'court', 'ct', 'boulevard', 'blvd']
    
    has_keyword = any(keyword in address_str.lower() for keyword in address_keywords)
    
    if has_keyword:
        return True, 0.90
    else:
        return True, 0.75


# ============================================================
# CROSS-FIELD VALIDATION
# ============================================================

def validate_date_logic(fields: Dict) -> Dict[str, str]:
    """
    Validate date relationships (e.g., effective < expiration)
    Returns dict of errors
    """
    errors = {}
    
    effective = fields.get("effective_date", {}).get("value")
    expiration = fields.get("expiration_date", {}).get("value")
    
    if effective and expiration:
        try:
            eff_date = datetime.strptime(effective, '%m/%d/%Y')
            exp_date = datetime.strptime(expiration, '%m/%d/%Y')
            
            if eff_date >= exp_date:
                errors["date_logic"] = "Effective date must be before expiration date"
        except ValueError:
            pass  # Can't parse, skip validation
    
    return errors


def validate_field_type_mismatch(field_name: str, value: str) -> Optional[str]:
    """
    Sanity check: ensure field values match expected types
    Returns error message if invalid, None if valid
    """
    
    # Premium should not be a date
    if field_name == "total_premium":
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}', value):
            return "Premium cannot be a date"
    
    # Date should not be a name
    if field_name in ["effective_date", "expiration_date"]:
        if len(value.split()) > 2 and not re.match(r'\d{1,2}/\d{1,2}/\d{4}', value):
            return "Date field contains non-date text"
    
    # Policy number should not be a full sentence
    if field_name == "policy_number":
        if len(value.split()) > 3:
            return "Policy number should not be multi-word text"
    
    return None


# ============================================================
# MAIN VALIDATION FUNCTION (BACKWARD COMPATIBLE)
# ============================================================

def validate_output(structured: Dict, confidence: float) -> Tuple[Dict, float]:
    """
    Basic validation (backward compatible)
    Enhanced version is validate_and_arbitrate()
    """
    if not structured:
        return structured, confidence
    
    # Validate each field
    validation_scores = {}
    
    validators = {
        "policy_number": validate_policy_number,
        "effective_date": validate_date,
        "expiration_date": validate_date,
        "insured_name": validate_name,
        "total_premium": validate_premium,
        "mailing_address": validate_address,
        "property_address": validate_address,
    }
    
    for field_name, validator in validators.items():
        if field_name in structured:
            value = structured[field_name].get("value", "")
            is_valid, score = validator(value)
            
            validation_scores[field_name] = score
            structured[field_name]["validation_score"] = score
            structured[field_name]["is_valid"] = is_valid
    
    # Calculate overall validation score
    if validation_scores:
        avg_validation_score = sum(validation_scores.values()) / len(validation_scores)
    else:
        avg_validation_score = 0.5
    
    # Adjust final confidence based on validation
    final_confidence = (avg_validation_score * 0.6) + (confidence * 0.4)
    
    return structured, round(final_confidence, 3)


# ============================================================
# STAGE 4: VALIDATION & ARBITRATION
# ============================================================

def validate_and_arbitrate(
    merged_fields: Dict,
    ocr_confidence: float,
    stage_breakdown: Dict
) -> Tuple[Dict, float]:
    """
    Stage 4: Validate and arbitrate between multiple extraction stages
    
    Args:
        merged_fields: Combined fields from all stages
        ocr_confidence: Base OCR confidence
        stage_breakdown: Individual stage results for arbitration
    
    Returns:
        (validated_fields, final_confidence)
    """
    
    if not merged_fields:
        return {}, ocr_confidence
    
    validated = {}
    validation_scores = {}
    field_errors = {}
    
    # ============================================================
    # STEP 1: VALIDATE EACH FIELD
    # ============================================================
    
    validators = {
        "policy_number": validate_policy_number,
        "effective_date": validate_date,
        "expiration_date": validate_date,
        "insured_name": validate_name,
        "total_premium": validate_premium,
        "mailing_address": validate_address,
        "property_address": validate_address,
        "dwelling_coverage": validate_premium,
    }
    
    for field_name, field_data in merged_fields.items():
        value = field_data.get("value", "")
        
        # Type mismatch check
        type_error = validate_field_type_mismatch(field_name, value)
        if type_error:
            field_errors[field_name] = type_error
            continue  # Skip this field
        
        # Run validator if available
        if field_name in validators:
            is_valid, val_score = validators[field_name](value)
            
            if not is_valid:
                field_errors[field_name] = f"Failed validation (score: {val_score:.2f})"
                continue
            
            validation_scores[field_name] = val_score
            
            # Add validation info to field
            field_data["validation_score"] = val_score
            field_data["is_valid"] = is_valid
        
        validated[field_name] = field_data
    
    # ============================================================
    # STEP 2: CROSS-FIELD VALIDATION
    # ============================================================
    
    cross_errors = validate_date_logic(validated)
    field_errors.update(cross_errors)
    
    # ============================================================
    # STEP 3: ARBITRATION BETWEEN STAGES
    # ============================================================
    
    # If a field failed validation, try alternate sources
    for field_name, error in field_errors.items():
        alternates = []
        
        # Check if other stages have this field
        for stage_name, stage_fields in stage_breakdown.items():
            if field_name in stage_fields:
                alt_value = stage_fields[field_name].get("value")
                alt_conf = stage_fields[field_name].get("confidence", 0.5)
                
                # Validate alternate
                if field_name in validators:
                    is_valid, val_score = validators[field_name](alt_value)
                    if is_valid:
                        alternates.append({
                            "value": alt_value,
                            "confidence": alt_conf * val_score,
                            "source": f"{stage_name}_alternate",
                            "validation_score": val_score
                        })
        
        # Use best alternate if available
        if alternates:
            best = max(alternates, key=lambda x: x["confidence"])
            validated[field_name] = best
            validation_scores[field_name] = best["validation_score"]
    
    # ============================================================
    # STEP 4: CALCULATE FINAL CONFIDENCE
    # ============================================================
    
    if validation_scores:
        avg_validation = sum(validation_scores.values()) / len(validation_scores)
    else:
        avg_validation = 0.5
    
    # Weight: 60% validation, 40% OCR
    final_confidence = (avg_validation * 0.6) + (ocr_confidence * 0.4)
    
    # Penalty for field errors
    if field_errors:
        penalty = min(0.15, len(field_errors) * 0.03)
        final_confidence = max(0.1, final_confidence - penalty)
    
    return validated, round(final_confidence, 3)