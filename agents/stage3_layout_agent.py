# agents/stage3_layout_agent.py
# Stage 3: Layout Extraction using LayoutXLM + Spatial Reasoning
# Handles tables, spatially separated key-value pairs, and complex layouts

from typing import List, Dict, Tuple, Optional
import re


def extract_with_layoutxlm(
    ambiguous_regions: List[Dict],
    relations: List[Tuple],
    missing_fields: List[str]
) -> Dict[str, Dict]:
    """
    Stage 3: Extract fields using LayoutXLM spatial reasoning
    
    This stage handles:
    - Tables with headers and values in different cells
    - Key-value pairs separated spatially (not adjacent)
    - Multi-column layouts
    - Complex form structures
    
    Args:
        ambiguous_regions: Layout elements identified as ambiguous by vision_agent
        relations: Spatial relations from relation_extraction_agent
        missing_fields: Fields still missing after Stage 1 and 2
    
    Returns:
        Dict of extracted fields with spatial confidence
    """
    
    if not ambiguous_regions or not missing_fields:
        return {}
    
    extracted = {}
    
    # Strategy 1: Use relations to find key-value pairs
    relation_fields = _extract_from_relations(relations, missing_fields)
    extracted.update(relation_fields)
    
    # Strategy 2: Extract from table structures
    table_fields = _extract_from_tables(ambiguous_regions, missing_fields)
    extracted.update(table_fields)
    
    # Strategy 3: Extract from spatial proximity
    proximity_fields = _extract_from_proximity(ambiguous_regions, missing_fields)
    extracted.update(proximity_fields)
    
    return extracted


# ============================================================
# STRATEGY 1: RELATION-BASED EXTRACTION
# ============================================================

def _extract_from_relations(
    relations: List[Tuple],
    missing_fields: List[str]
) -> Dict[str, Dict]:
    """
    Extract fields using HAS_VALUE relations from relation extraction
    
    Example relation: ("Policy Number", "HAS_VALUE", "ABC123456", 0.92)
    """
    
    extracted = {}
    
    # Map relation labels to field names
    label_to_field = {
        "policy number": "policy_number",
        "policy no": "policy_number",
        "insured name": "insured_name",
        "named insured": "insured_name",
        "effective date": "effective_date",
        "expiration date": "expiration_date",
        "total premium": "total_premium",
        "premium": "total_premium",
        "mailing address": "mailing_address",
        "property address": "property_address",
        "dwelling coverage": "dwelling_coverage",
        "coverage": "dwelling_coverage",
    }
    
    for relation in relations:
        if len(relation) != 4:
            continue
        
        entity1, rel_type, entity2, confidence = relation
        
        # Only process HAS_VALUE relations
        if rel_type != "HAS_VALUE":
            continue
        
        # Normalize label
        label_normalized = entity1.lower().strip().rstrip(':')
        
        # Find matching field
        field_name = label_to_field.get(label_normalized)
        
        if field_name and field_name in missing_fields:
            # Validate value
            if _validate_field_value(field_name, entity2):
                extracted[field_name] = {
                    "value": entity2,
                    "confidence": confidence * 0.88,  # Slight penalty for spatial extraction
                    "source": "layout_spatial",
                    "extraction_method": "relation_has_value"
                }
    
    return extracted


# ============================================================
# STRATEGY 2: TABLE EXTRACTION
# ============================================================

def _extract_from_tables(
    ambiguous_regions: List[Dict],
    missing_fields: List[str]
) -> Dict[str, Dict]:
    """
    Extract fields from table structures
    
    Tables are identified by:
    - Regular spacing between elements
    - Multiple rows and columns
    - Header row with data rows below
    """
    
    extracted = {}
    
    # Group elements into potential tables
    tables = _identify_table_structures(ambiguous_regions)
    
    for table in tables:
        # Extract from each table
        table_fields = _parse_table(table, missing_fields)
        extracted.update(table_fields)
    
    return extracted


def _identify_table_structures(elements: List[Dict]) -> List[List[Dict]]:
    """Group elements into table structures"""
    
    if len(elements) < 6:  # Tables need at least 6 elements
        return []
    
    # Sort by vertical position
    sorted_elements = sorted(elements, key=lambda e: e["box"][1])
    
    # Group into rows (elements with similar y-coordinates)
    rows = []
    current_row = [sorted_elements[0]]
    current_y = sorted_elements[0]["box"][1]
    
    for elem in sorted_elements[1:]:
        elem_y = elem["box"][1]
        
        # Same row if within 30 pixels vertically
        if abs(elem_y - current_y) < 30:
            current_row.append(elem)
        else:
            if len(current_row) >= 2:  # Valid row has at least 2 columns
                rows.append(current_row)
            current_row = [elem]
            current_y = elem_y
    
    if len(current_row) >= 2:
        rows.append(current_row)
    
    # A table has at least 2 rows
    if len(rows) >= 2:
        return [rows]
    
    return []


def _parse_table(table_rows: List[List[Dict]], missing_fields: List[str]) -> Dict[str, Dict]:
    """Parse table structure to extract fields"""
    
    extracted = {}
    
    if not table_rows:
        return extracted
    
    # Assume first row is headers
    headers = table_rows[0]
    data_rows = table_rows[1:]
    
    # Map headers to field names
    field_mappings = {}
    for i, header in enumerate(headers):
        header_text = header["text"].lower().strip().rstrip(':')
        
        # Map common header names
        if "coverage" in header_text or "limit" in header_text:
            field_mappings[i] = "dwelling_coverage"
        elif "premium" in header_text:
            field_mappings[i] = "total_premium"
        elif "deductible" in header_text:
            field_mappings[i] = "deductible"
    
    # Extract values from data rows
    for row in data_rows:
        for i, cell in enumerate(row):
            if i in field_mappings:
                field_name = field_mappings[i]
                
                if field_name in missing_fields:
                    extracted[field_name] = {
                        "value": cell["text"],
                        "confidence": cell.get("confidence", 0.8) * 0.85,
                        "source": "layout_spatial",
                        "extraction_method": "table_parsing"
                    }
    
    return extracted


# ============================================================
# STRATEGY 3: PROXIMITY-BASED EXTRACTION
# ============================================================

def _extract_from_proximity(
    ambiguous_regions: List[Dict],
    missing_fields: List[str]
) -> Dict[str, Dict]:
    """
    Extract fields based on spatial proximity
    
    Finds values near field labels that aren't directly adjacent
    """
    
    extracted = {}
    
    # Separate labels and values
    labels = [e for e in ambiguous_regions if e.get("element_type") == "label"]
    values = [e for e in ambiguous_regions if e.get("element_type") == "value"]
    
    # Label patterns to look for
    label_patterns = {
        "policy_number": ["policy", "policy number", "policy no"],
        "insured_name": ["insured", "name", "policyholder"],
        "effective_date": ["effective", "inception", "start date"],
        "expiration_date": ["expiration", "end date", "expires"],
        "total_premium": ["premium", "total", "amount"],
        "dwelling_coverage": ["dwelling", "coverage a", "limit"],
    }
    
    for field_name, patterns in label_patterns.items():
        if field_name not in missing_fields:
            continue
        
        # Find matching label
        matching_label = None
        for label in labels:
            label_text = label["text"].lower()
            if any(pattern in label_text for pattern in patterns):
                matching_label = label
                break
        
        if not matching_label:
            continue
        
        # Find nearest value
        nearest_value = _find_nearest_value(matching_label, values)
        
        if nearest_value:
            # Validate value
            if _validate_field_value(field_name, nearest_value["text"]):
                extracted[field_name] = {
                    "value": nearest_value["text"],
                    "confidence": nearest_value.get("confidence", 0.8) * 0.82,
                    "source": "layout_spatial",
                    "extraction_method": "proximity_matching"
                }
    
    return extracted


def _find_nearest_value(label: Dict, values: List[Dict]) -> Optional[Dict]:
    """Find the value element nearest to a label"""
    
    if not values:
        return None
    
    label_box = label["box"]
    label_center_x = (label_box[0] + label_box[2]) / 2
    label_center_y = (label_box[1] + label_box[3]) / 2
    
    best_value = None
    best_distance = float('inf')
    
    for value in values:
        value_box = value["box"]
        value_center_x = (value_box[0] + value_box[2]) / 2
        value_center_y = (value_box[1] + value_box[3]) / 2
        
        # Calculate distance
        distance = ((value_center_x - label_center_x)**2 + 
                   (value_center_y - label_center_y)**2)**0.5
        
        # Prefer values to the right or below
        is_right = value_box[0] > label_box[2]
        is_below = value_box[1] > label_box[3]
        
        if (is_right or is_below) and distance < best_distance and distance < 200:
            best_distance = distance
            best_value = value
    
    return best_value


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _validate_field_value(field_name: str, value: str) -> bool:
    """Validate that extracted value matches expected field type"""
    
    if not value or len(value) < 2:
        return False
    
    value = value.strip()
    
    # Policy number validation
    if field_name == "policy_number":
        # Should have at least 6 characters and some digits
        if len(value) < 6:
            return False
        if sum(c.isdigit() for c in value) < 3:
            return False
        return True
    
    # Date validation
    if field_name in ["effective_date", "expiration_date"]:
        # Should match date pattern
        return bool(re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', value))
    
    # Name validation
    if field_name == "insured_name":
        # Should not contain numbers
        if any(c.isdigit() for c in value):
            return False
        # Should have at least 2 words
        if len(value.split()) < 2:
            return False
        return True
    
    # Premium/coverage validation
    if field_name in ["total_premium", "dwelling_coverage"]:
        # Should contain numbers and possibly $ sign
        clean = value.replace('$', '').replace(',', '')
        try:
            float(clean)
            return True
        except ValueError:
            return False
    
    # Address validation
    if field_name in ["mailing_address", "property_address"]:
        # Should contain at least one number
        return any(c.isdigit() for c in value)
    
    return True


# ============================================================
# CHUNKING FOR LARGE DOCUMENTS (AVOID 512 TOKEN LIMIT)
# ============================================================

def chunk_document_for_layoutxlm(
    layout_elements: List[Dict],
    max_elements_per_chunk: int = 100
) -> List[List[Dict]]:
    """
    Split document into chunks for LayoutXLM processing
    
    This avoids the 512 token limit by processing sections separately
    """
    
    if len(layout_elements) <= max_elements_per_chunk:
        return [layout_elements]
    
    chunks = []
    current_chunk = []
    
    for elem in layout_elements:
        current_chunk.append(elem)
        
        if len(current_chunk) >= max_elements_per_chunk:
            chunks.append(current_chunk)
            current_chunk = []
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks