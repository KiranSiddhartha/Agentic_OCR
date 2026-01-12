"""
Retry logic for OCR pipeline.
Decides when to retry with different preprocessing strategies.
"""


def should_retry_text(lines, min_lines=5):
    """
    Check if we should retry based on text quality.
    
    Args:
        lines: List of extracted text lines
        min_lines: Minimum acceptable number of lines
        
    Returns:
        tuple: (should_retry, reason)
    """
    
    # Not enough text extracted
    if len(lines) < min_lines:
        return True, f"Too few lines: {len(lines)} < {min_lines}"
    
    # Check text quality
    total_length = sum(len(l) for l in lines)
    avg_length = total_length / len(lines) if lines else 0
    
    # Lines too short on average (likely noise or incomplete)
    if avg_length < 3:
        return True, f"Text too short: avg {avg_length:.1f} chars"
    
    # All good
    return False, "Text quality acceptable"


def should_retry(confidence, threshold=0.65, structured=None):
    """
    Smart retry logic based on confidence and fields.
    
    Args:
        confidence: Overall confidence score (0-1)
        threshold: Confidence threshold for retry decision
        structured: Extracted structured data (optional)
    
    Returns:
        tuple: (should_retry, reason)
    """
    retry_reason = ""
    
    # Check confidence threshold
    if confidence < threshold:
        retry_reason = f"Low confidence: {confidence:.2%} < {threshold:.2%}"
        return True, retry_reason
    
    # Check for missing critical fields
    if structured:
        required_fields = ["policy_number", "effective_date", "insured_name"]
        missing_fields = [f for f in required_fields if f not in structured or not structured[f].get("value")]
        
        if len(missing_fields) >= 2:
            retry_reason = f"Missing critical fields: {', '.join(missing_fields)}"
            return True, retry_reason
        
        # Check validation scores for extracted fields
        low_validation_fields = []
        for field, data in structured.items():
            if isinstance(data, dict):
                val_score = data.get("validation_score", 0.0)
                if 0 < val_score < 0.50:
                    low_validation_fields.append(f"{field} ({val_score:.1%})")
        
        if len(low_validation_fields) >= 1:
            retry_reason = f"Low validation scores: {', '.join(low_validation_fields)}"
            return True, retry_reason
    
    return False, "No retry needed"


def get_retry_strategy(retry_count):
    """
    Provide adaptive preprocessing strategy based on retry count.
    Each retry uses progressively more aggressive preprocessing.
    
    Args:
        retry_count: Current retry attempt (0, 1, 2, ...)
        
    Returns:
        dict: Strategy configuration for preprocessing
    """
    strategies = [
        {
            "name": "default",
            "denoise_strength": 10,
            "sharpen": True,
            "contrast_boost": False,
            "morphology": False,
            "description": "Standard preprocessing"
        },
        {
            "name": "aggressive_denoise",
            "denoise_strength": 15,
            "sharpen": True,
            "contrast_boost": True,
            "morphology": True,
            "description": "Heavy denoising + sharpening"
        },
        {
            "name": "high_contrast",
            "denoise_strength": 12,
            "sharpen": True,
            "contrast_boost": True,
            "morphology": True,
            "description": "Maximum contrast boost"
        },
    ]
    
    if retry_count >= len(strategies):
        return strategies[-1]
    
    return strategies[retry_count]


def get_retry_recommendations(confidence, structured=None):
    """
    Provide specific recommendations for improvement.
    
    Returns:
        List of specific retry strategies
    """
    recommendations = []
    
    if confidence < 0.50:
        recommendations.append("Try high_contrast mode for low-confidence images")
    
    if structured is None:
        recommendations.append("No field data - check if OCR extracted text")
    
    if not recommendations:
        recommendations.append("Results look good - manual review recommended")
    
    return recommendations


def should_terminate_retries(retry_count, max_retries):
    """Check if we should stop retrying."""
    return retry_count >= max_retries

