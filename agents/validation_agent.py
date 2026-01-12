import re
from datetime import datetime

def validate_policy_number(policy_num):
    """
    Validate policy number format.
    Returns: (is_valid, score)
    """
    if not policy_num:
        return False, 0.0
    
    # Policy numbers are typically 8-25 alphanumeric characters
    if len(policy_num) < 8 or len(policy_num) > 30:
        return False, 0.3
    
    # Should contain at least some mix of letters and numbers
    has_digit = any(c.isdigit() for c in policy_num)
    has_letter = any(c.isalpha() for c in policy_num)
    
    if has_digit and has_letter:
        return True, 0.95
    elif has_digit or has_letter:
        return True, 0.80
    else:
        return False, 0.2

def validate_date(date_str):
    """
    Validate date format (MM/DD/YYYY or similar).
    Returns: (is_valid, score)
    """
    if not date_str:
        return False, 0.0
    
    date_patterns = [
        r'^(\d{1,2})/(\d{1,2})/(\d{4})$',
        r'^(\d{4})/(\d{1,2})/(\d{1,2})$',
    ]
    
    for pattern in date_patterns:
        m = re.match(pattern, date_str)
        if m:
            try:
                # Try to parse as valid date
                if len(m.group(3)) == 4:  # YYYY format
                    year = int(m.group(3))
                else:
                    year = int(m.group(1))
                
                if 1900 < year < 2100:  # Reasonable year range
                    return True, 0.95
            except:
                pass
    
    # Fallback: Accept if it matches date pattern even if not fully valid
    if re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{4}$', date_str):
        return True, 0.75
    
    return False, 0.2

def validate_name(name_str):
    """
    Validate insured name.
    Returns: (is_valid, score)
    """
    if not name_str or len(name_str) < 3:
        return False, 0.0
    
    # Should start with capital letter
    if not name_str[0].isupper():
        return False, 0.3
    
    # Should contain mostly letters and spaces
    clean = re.sub(r'[a-zA-Z\s\-\.\']', '', name_str)
    if len(clean) > 0:
        return True, 0.70  # Some non-letter characters, lower confidence
    
    # Check for reasonable length
    if len(name_str) < 5:
        return True, 0.70
    elif len(name_str) > 60:
        return True, 0.60  # Possibly extracted too much
    else:
        return True, 0.90

def validate_output(structured, confidence):
    """
    Enhanced validation agent for 90%+ accuracy.
    Validates field-specific formats and calculates validation scores.
    DO NOT delete fields - only score validity.
    """
    if not structured:
        return structured, confidence

    # Validate each field
    validation_scores = {}
    
    if "policy_number" in structured:
        policy = structured["policy_number"].get("value", "")
        is_valid, score = validate_policy_number(policy)
        validation_scores["policy_number"] = score
        structured["policy_number"]["validation_score"] = score
    
    if "effective_date" in structured:
        date = structured["effective_date"].get("value", "")
        is_valid, score = validate_date(date)
        validation_scores["effective_date"] = score
        structured["effective_date"]["validation_score"] = score
    
    if "expiration_date" in structured:
        date = structured["expiration_date"].get("value", "")
        is_valid, score = validate_date(date)
        validation_scores["expiration_date"] = score
        structured["expiration_date"]["validation_score"] = score
    
    if "insured_name" in structured:
        name = structured["insured_name"].get("value", "")
        is_valid, score = validate_name(name)
        validation_scores["insured_name"] = score
        structured["insured_name"]["validation_score"] = score
    
    # Calculate overall validation score
    if validation_scores:
        avg_validation_score = sum(validation_scores.values()) / len(validation_scores)
    else:
        avg_validation_score = 0.5
    
    # Adjust final confidence based on validation
    final_confidence = max(
        confidence,
        avg_validation_score * 0.8 + confidence * 0.2
    )
    
    return structured, round(final_confidence, 3)
