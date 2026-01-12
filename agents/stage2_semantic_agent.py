# agents/stage2_semantic_agent.py
# Stage 2: Semantic Extraction using SpaCy NER
# Handles unlabeled entities that regex can't catch

import re
from typing import List, Dict, Optional

# Try to import spacy, fall back to rule-based if unavailable
try:
    import spacy
    SPACY_AVAILABLE = True
    _nlp = None
except ImportError:
    SPACY_AVAILABLE = False
    _nlp = None


def _load_spacy_model():
    """Lazy load spacy model"""
    global _nlp
    
    if not SPACY_AVAILABLE:
        return None
    
    if _nlp is None:
        try:
            # Try to load small English model
            _nlp = spacy.load("en_core_web_sm")
            print("[Stage2] SpaCy model loaded")
        except OSError:
            print("[Stage2] SpaCy model not found, using rule-based fallback")
            return None
    
    return _nlp


def extract_with_ner(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
    """
    Stage 2: Extract fields using Named Entity Recognition
    
    This stage handles:
    - Unlabeled names (PERSON entities)
    - Unlabeled addresses (GPE, LOC entities)
    - Unlabeled dates (DATE entities)
    - Unlabeled monetary amounts (MONEY entities)
    
    Args:
        lines: OCR text lines
        missing_fields: Fields that Stage 1 failed to extract
    
    Returns:
        Dict of extracted fields with NER confidence
    """
    
    if not missing_fields:
        return {}
    
    nlp = _load_spacy_model()
    
    if nlp is not None:
        return _extract_with_spacy(lines, missing_fields, nlp)
    else:
        return _extract_with_rules(lines, missing_fields)


# ============================================================
# SPACY-BASED EXTRACTION
# ============================================================

def _extract_with_spacy(lines: List[str], missing_fields: List[str], nlp) -> Dict[str, Dict]:
    """Extract entities using SpaCy NER"""
    
    text = "\n".join(lines)
    doc = nlp(text)
    
    extracted = {}
    
    # Map SpaCy entity types to field names
    entity_map = {
        "PERSON": "insured_name",
        "ORG": "insured_name",  # Organizations can also be policyholders
        "GPE": "mailing_address",  # Geo-political entities (cities, states)
        "LOC": "mailing_address",  # Locations
        "DATE": ["effective_date", "expiration_date"],
        "MONEY": "total_premium",
    }
    
    # Group entities by type
    entities_by_type = {}
    for ent in doc.ents:
        if ent.label_ not in entities_by_type:
            entities_by_type[ent.label_] = []
        entities_by_type[ent.label_].append(ent)
    
    # Extract PERSON/ORG → insured_name
    if "insured_name" in missing_fields:
        person_entities = entities_by_type.get("PERSON", []) + entities_by_type.get("ORG", [])
        
        if person_entities:
            # Use first person/org entity (usually the insured)
            best_entity = person_entities[0]
            
            # Validate: should not contain document keywords
            if _is_valid_name_entity(best_entity.text):
                extracted["insured_name"] = {
                    "value": best_entity.text,
                    "confidence": 0.82,
                    "source": "semantic_ner",
                    "ner_label": best_entity.label_
                }
    
    # Extract GPE/LOC → address
    if "mailing_address" in missing_fields or "property_address" in missing_fields:
        loc_entities = entities_by_type.get("GPE", []) + entities_by_type.get("LOC", [])
        
        if loc_entities:
            # Combine nearby location entities into full address
            address = _build_address_from_entities(loc_entities, doc)
            
            if address:
                field_name = "mailing_address" if "mailing_address" in missing_fields else "property_address"
                extracted[field_name] = {
                    "value": address,
                    "confidence": 0.78,
                    "source": "semantic_ner",
                    "ner_label": "LOC/GPE"
                }
    
    # Extract DATE → effective_date, expiration_date
    date_entities = entities_by_type.get("DATE", [])
    if date_entities and ("effective_date" in missing_fields or "expiration_date" in missing_fields):
        # Convert date entities to standard format
        dates = []
        for date_ent in date_entities:
            normalized = _normalize_date(date_ent.text)
            if normalized:
                dates.append(normalized)
        
        if dates and "effective_date" in missing_fields:
            extracted["effective_date"] = {
                "value": dates[0],
                "confidence": 0.75,
                "source": "semantic_ner",
                "ner_label": "DATE"
            }
        
        if len(dates) > 1 and "expiration_date" in missing_fields:
            extracted["expiration_date"] = {
                "value": dates[1],
                "confidence": 0.75,
                "source": "semantic_ner",
                "ner_label": "DATE"
            }
    
    # Extract MONEY → total_premium
    if "total_premium" in missing_fields:
        money_entities = entities_by_type.get("MONEY", [])
        
        if money_entities:
            # Use first money entity
            extracted["total_premium"] = {
                "value": money_entities[0].text,
                "confidence": 0.80,
                "source": "semantic_ner",
                "ner_label": "MONEY"
            }
    
    return extracted


# ============================================================
# RULE-BASED FALLBACK (NO SPACY)
# ============================================================

def _extract_with_rules(lines: List[str], missing_fields: List[str]) -> Dict[str, Dict]:
    """
    Fallback extraction using simple rules (when SpaCy unavailable)
    """
    
    text = "\n".join(lines)
    extracted = {}
    
    # Extract unlabeled name (capitalized words without numbers)
    if "insured_name" in missing_fields:
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        matches = re.findall(name_pattern, text)
        
        for match in matches:
            if _is_valid_name_entity(match):
                extracted["insured_name"] = {
                    "value": match,
                    "confidence": 0.70,
                    "source": "semantic_rules",
                    "ner_label": "PERSON"
                }
                break
    
    # Extract unlabeled address (number + street pattern)
    if "mailing_address" in missing_fields or "property_address" in missing_fields:
        address_pattern = r'(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln))?)'
        matches = re.findall(address_pattern, text, re.IGNORECASE)
        
        if matches:
            field_name = "mailing_address" if "mailing_address" in missing_fields else "property_address"
            extracted[field_name] = {
                "value": matches[0],
                "confidence": 0.68,
                "source": "semantic_rules",
                "ner_label": "ADDRESS"
            }
    
    # Extract unlabeled dates
    if "effective_date" in missing_fields or "expiration_date" in missing_fields:
        date_pattern = r'\b(\d{1,2}/\d{1,2}/\d{4})\b'
        dates = re.findall(date_pattern, text)
        
        if dates and "effective_date" in missing_fields:
            extracted["effective_date"] = {
                "value": dates[0],
                "confidence": 0.65,
                "source": "semantic_rules",
                "ner_label": "DATE"
            }
        
        if len(dates) > 1 and "expiration_date" in missing_fields:
            extracted["expiration_date"] = {
                "value": dates[1],
                "confidence": 0.65,
                "source": "semantic_rules",
                "ner_label": "DATE"
            }
    
    # Extract unlabeled money amounts
    if "total_premium" in missing_fields:
        money_pattern = r'\$\s*([\d,]+\.?\d*)'
        matches = re.findall(money_pattern, text)
        
        if matches:
            extracted["total_premium"] = {
                "value": f"${matches[0]}",
                "confidence": 0.72,
                "source": "semantic_rules",
                "ner_label": "MONEY"
            }
    
    return extracted


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _is_valid_name_entity(name: str) -> bool:
    """Validate that entity is actually a name"""
    
    if not name or len(name) < 3:
        return False
    
    # Reject if contains numbers
    if any(c.isdigit() for c in name):
        return False
    
    # Reject common document keywords
    invalid_keywords = [
        'policy', 'insurance', 'coverage', 'premium', 'effective',
        'expiration', 'date', 'number', 'company', 'agent', 'broker'
    ]
    
    name_lower = name.lower()
    if any(keyword in name_lower for keyword in invalid_keywords):
        return False
    
    # Should have at least first + last name
    words = name.split()
    if len(words) < 2:
        return False
    
    return True


def _build_address_from_entities(loc_entities, doc) -> Optional[str]:
    """Build complete address from location entities"""
    
    if not loc_entities:
        return None
    
    # Get text around location entities
    address_parts = []
    
    for ent in loc_entities[:3]:  # Use up to 3 location entities
        # Get surrounding context
        start = max(0, ent.start - 10)
        end = min(len(doc), ent.end + 5)
        
        context = doc[start:end].text
        
        # Look for street address pattern
        street_pattern = r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr)'
        match = re.search(street_pattern, context, re.IGNORECASE)
        
        if match:
            address_parts.append(match.group(0))
        
        address_parts.append(ent.text)
    
    if address_parts:
        return ", ".join(set(address_parts))  # Remove duplicates
    
    return None


def _normalize_date(date_text: str) -> Optional[str]:
    """Normalize date entity to MM/DD/YYYY format"""
    
    # Already in correct format
    if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_text):
        return date_text
    
    # Convert common date formats
    patterns = [
        (r'(\d{1,2})-(\d{1,2})-(\d{4})', r'\1/\2/\3'),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\2/\3/\1'),
    ]
    
    for pattern, replacement in patterns:
        match = re.search(pattern, date_text)
        if match:
            return re.sub(pattern, replacement, date_text)
    
    # Month name format (e.g., "January 15, 2024")
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    for month_name, month_num in month_map.items():
        if month_name in date_text.lower():
            # Extract day and year
            day_match = re.search(r'\b(\d{1,2})\b', date_text)
            year_match = re.search(r'\b(\d{4})\b', date_text)
            
            if day_match and year_match:
                return f"{month_num}/{day_match.group(1)}/{year_match.group(1)}"
    
    return None