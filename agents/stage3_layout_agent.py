# # agents/stage3_layout_agent.py
# # Stage 3: Layout Extraction using LayoutXLM + Spatial Reasoning
# # Handles tables, spatially separated key-value pairs, and complex layouts

# from typing import List, Dict, Tuple, Optional
# import re


# def extract_with_layoutxlm(
#     ambiguous_regions: List[Dict],
#     relations: List[Tuple],
#     missing_fields: List[str]
# ) -> Dict[str, Dict]:
#     """
#     Stage 3: Extract fields using LayoutXLM spatial reasoning
    
#     This stage handles:
#     - Tables with headers and values in different cells
#     - Key-value pairs separated spatially (not adjacent)
#     - Multi-column layouts
#     - Complex form structures
    
#     Args:
#         ambiguous_regions: Layout elements identified as ambiguous by vision_agent
#         relations: Spatial relations from relation_extraction_agent
#         missing_fields: Fields still missing after Stage 1 and 2
    
#     Returns:
#         Dict of extracted fields with spatial confidence
#     """
    
#     if not ambiguous_regions or not missing_fields:
#         return {}
    
#     extracted = {}
    
#     # Strategy 1: Use relations to find key-value pairs
#     relation_fields = _extract_from_relations(relations, missing_fields)
#     extracted.update(relation_fields)
    
#     # Strategy 2: Extract from table structures
#     table_fields = _extract_from_tables(ambiguous_regions, missing_fields)
#     extracted.update(table_fields)
    
#     # Strategy 3: Extract from spatial proximity
#     proximity_fields = _extract_from_proximity(ambiguous_regions, missing_fields)
#     extracted.update(proximity_fields)
    
#     return extracted


# # ============================================================
# # STRATEGY 1: RELATION-BASED EXTRACTION
# # ============================================================

# def _extract_from_relations(
#     relations: List[Tuple],
#     missing_fields: List[str]
# ) -> Dict[str, Dict]:
#     """
#     Extract fields using HAS_VALUE relations from relation extraction
    
#     Example relation: ("Policy Number", "HAS_VALUE", "ABC123456", 0.92)
#     """
    
#     extracted = {}
    
#     # Map relation labels to field names
#     label_to_field = {
#         "policy number": "policy_number",
#         "policy no": "policy_number",
#         "insured name": "insured_name",
#         "named insured": "insured_name",
#         "effective date": "effective_date",
#         "expiration date": "expiration_date",
#         "total premium": "total_premium",
#         "premium": "total_premium",
#         "mailing address": "mailing_address",
#         "property address": "property_address",
#         "dwelling coverage": "dwelling_coverage",
#         "coverage": "dwelling_coverage",
#     }
    
#     for relation in relations:
#         if len(relation) != 4:
#             continue
        
#         entity1, rel_type, entity2, confidence = relation
        
#         # Only process HAS_VALUE relations
#         if rel_type != "HAS_VALUE":
#             continue
        
#         # Normalize label
#         label_normalized = entity1.lower().strip().rstrip(':')
        
#         # Find matching field
#         field_name = label_to_field.get(label_normalized)
        
#         if field_name and field_name in missing_fields:
#             # Validate value
#             if _validate_field_value(field_name, entity2):
#                 extracted[field_name] = {
#                     "value": entity2,
#                     "confidence": confidence * 0.88,  # Slight penalty for spatial extraction
#                     "source": "layout_spatial",
#                     "extraction_method": "relation_has_value"
#                 }
    
#     return extracted


# # ============================================================
# # STRATEGY 2: TABLE EXTRACTION
# # ============================================================

# def _extract_from_tables(
#     ambiguous_regions: List[Dict],
#     missing_fields: List[str]
# ) -> Dict[str, Dict]:
#     """
#     Extract fields from table structures
    
#     Tables are identified by:
#     - Regular spacing between elements
#     - Multiple rows and columns
#     - Header row with data rows below
#     """
    
#     extracted = {}
    
#     # Group elements into potential tables
#     tables = _identify_table_structures(ambiguous_regions)
    
#     for table in tables:
#         # Extract from each table
#         table_fields = _parse_table(table, missing_fields)
#         extracted.update(table_fields)
    
#     return extracted


# def _identify_table_structures(elements: List[Dict]) -> List[List[Dict]]:
#     """Group elements into table structures"""
    
#     if len(elements) < 6:  # Tables need at least 6 elements
#         return []
    
#     # Sort by vertical position
#     sorted_elements = sorted(elements, key=lambda e: e["box"][1])
    
#     # Group into rows (elements with similar y-coordinates)
#     rows = []
#     current_row = [sorted_elements[0]]
#     current_y = sorted_elements[0]["box"][1]
    
#     for elem in sorted_elements[1:]:
#         elem_y = elem["box"][1]
        
#         # Same row if within 30 pixels vertically
#         if abs(elem_y - current_y) < 30:
#             current_row.append(elem)
#         else:
#             if len(current_row) >= 2:  # Valid row has at least 2 columns
#                 rows.append(current_row)
#             current_row = [elem]
#             current_y = elem_y
    
#     if len(current_row) >= 2:
#         rows.append(current_row)
    
#     # A table has at least 2 rows
#     if len(rows) >= 2:
#         return [rows]
    
#     return []


# def _parse_table(table_rows: List[List[Dict]], missing_fields: List[str]) -> Dict[str, Dict]:
#     """Parse table structure to extract fields"""
    
#     extracted = {}
    
#     if not table_rows:
#         return extracted
    
#     # Assume first row is headers
#     headers = table_rows[0]
#     data_rows = table_rows[1:]
    
#     # Map headers to field names
#     field_mappings = {}
#     for i, header in enumerate(headers):
#         header_text = header["text"].lower().strip().rstrip(':')
        
#         # Map common header names
#         if "coverage" in header_text or "limit" in header_text:
#             field_mappings[i] = "dwelling_coverage"
#         elif "premium" in header_text:
#             field_mappings[i] = "total_premium"
#         elif "deductible" in header_text:
#             field_mappings[i] = "deductible"
    
#     # Extract values from data rows
#     for row in data_rows:
#         for i, cell in enumerate(row):
#             if i in field_mappings:
#                 field_name = field_mappings[i]
                
#                 if field_name in missing_fields:
#                     extracted[field_name] = {
#                         "value": cell["text"],
#                         "confidence": cell.get("confidence", 0.8) * 0.85,
#                         "source": "layout_spatial",
#                         "extraction_method": "table_parsing"
#                     }
    
#     return extracted


# # ============================================================
# # STRATEGY 3: PROXIMITY-BASED EXTRACTION
# # ============================================================

# def _extract_from_proximity(
#     ambiguous_regions: List[Dict],
#     missing_fields: List[str]
# ) -> Dict[str, Dict]:
#     """
#     Extract fields based on spatial proximity
    
#     Finds values near field labels that aren't directly adjacent
#     """
    
#     extracted = {}
    
#     # Separate labels and values
#     labels = [e for e in ambiguous_regions if e.get("element_type") == "label"]
#     values = [e for e in ambiguous_regions if e.get("element_type") == "value"]
    
#     # Label patterns to look for
#     label_patterns = {
#         "policy_number": ["policy", "policy number", "policy no"],
#         "insured_name": ["insured", "name", "policyholder"],
#         "effective_date": ["effective", "inception", "start date"],
#         "expiration_date": ["expiration", "end date", "expires"],
#         "total_premium": ["premium", "total", "amount"],
#         "dwelling_coverage": ["dwelling", "coverage a", "limit"],
#     }
    
#     for field_name, patterns in label_patterns.items():
#         if field_name not in missing_fields:
#             continue
        
#         # Find matching label
#         matching_label = None
#         for label in labels:
#             label_text = label["text"].lower()
#             if any(pattern in label_text for pattern in patterns):
#                 matching_label = label
#                 break
        
#         if not matching_label:
#             continue
        
#         # Find nearest value
#         nearest_value = _find_nearest_value(matching_label, values)
        
#         if nearest_value:
#             # Validate value
#             if _validate_field_value(field_name, nearest_value["text"]):
#                 extracted[field_name] = {
#                     "value": nearest_value["text"],
#                     "confidence": nearest_value.get("confidence", 0.8) * 0.82,
#                     "source": "layout_spatial",
#                     "extraction_method": "proximity_matching"
#                 }
    
#     return extracted


# def _find_nearest_value(label: Dict, values: List[Dict]) -> Optional[Dict]:
#     """Find the value element nearest to a label"""
    
#     if not values:
#         return None
    
#     label_box = label["box"]
#     label_center_x = (label_box[0] + label_box[2]) / 2
#     label_center_y = (label_box[1] + label_box[3]) / 2
    
#     best_value = None
#     best_distance = float('inf')
    
#     for value in values:
#         value_box = value["box"]
#         value_center_x = (value_box[0] + value_box[2]) / 2
#         value_center_y = (value_box[1] + value_box[3]) / 2
        
#         # Calculate distance
#         distance = ((value_center_x - label_center_x)**2 + 
#                    (value_center_y - label_center_y)**2)**0.5
        
#         # Prefer values to the right or below
#         is_right = value_box[0] > label_box[2]
#         is_below = value_box[1] > label_box[3]
        
#         if (is_right or is_below) and distance < best_distance and distance < 200:
#             best_distance = distance
#             best_value = value
    
#     return best_value


# # ============================================================
# # VALIDATION HELPERS
# # ============================================================

# def _validate_field_value(field_name: str, value: str) -> bool:
#     """Validate that extracted value matches expected field type"""
    
#     if not value or len(value) < 2:
#         return False
    
#     value = value.strip()
    
#     # Policy number validation
#     if field_name == "policy_number":
#         # Should have at least 6 characters and some digits
#         if len(value) < 6:
#             return False
#         if sum(c.isdigit() for c in value) < 3:
#             return False
#         return True
    
#     # Date validation
#     if field_name in ["effective_date", "expiration_date"]:
#         # Should match date pattern
#         return bool(re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', value))
    
#     # Name validation
#     if field_name == "insured_name":
#         # Should not contain numbers
#         if any(c.isdigit() for c in value):
#             return False
#         # Should have at least 2 words
#         if len(value.split()) < 2:
#             return False
#         return True
    
#     # Premium/coverage validation
#     if field_name in ["total_premium", "dwelling_coverage"]:
#         # Should contain numbers and possibly $ sign
#         clean = value.replace('$', '').replace(',', '')
#         try:
#             float(clean)
#             return True
#         except ValueError:
#             return False
    
#     # Address validation
#     if field_name in ["mailing_address", "property_address"]:
#         # Should contain at least one number
#         return any(c.isdigit() for c in value)
    
#     return True


# # ============================================================
# # CHUNKING FOR LARGE DOCUMENTS (AVOID 512 TOKEN LIMIT)
# # ============================================================

# def chunk_document_for_layoutxlm(
#     layout_elements: List[Dict],
#     max_elements_per_chunk: int = 100
# ) -> List[List[Dict]]:
#     """
#     Split document into chunks for LayoutXLM processing
    
#     This avoids the 512 token limit by processing sections separately
#     """
    
#     if len(layout_elements) <= max_elements_per_chunk:
#         return [layout_elements]
    
#     chunks = []
#     current_chunk = []
    
#     for elem in layout_elements:
#         current_chunk.append(elem)
        
#         if len(current_chunk) >= max_elements_per_chunk:
#             chunks.append(current_chunk)
#             current_chunk = []
    
#     if current_chunk:
#         chunks.append(current_chunk)
    
#     return chunks


"""
Stage 3 – Layout Agent (SPATIAL REASONING ONLY)

Purpose:
- Recover missing fields using spatial relationships
- Operates ONLY on missing fields
- Uses relations, tables, and proximity
- Never overrides earlier stages
"""

from typing import List, Dict, Tuple, Optional
import math
import re

# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def extract_with_layoutxlm(
    ambiguous_regions: List[Dict],
    relations: List[Tuple],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Stage 3 spatial extraction.
    Only fills missing fields using layout-based reasoning.
    """

    if not ambiguous_regions or not missing_fields:
        return {}

    extracted: Dict[str, Dict] = {}

    # Strategy 1: relation-based (strongest spatial signal)
    extracted.update(
        _extract_from_relations(relations, missing_fields)
    )

    # Strategy 2: table parsing
    extracted.update(
        _extract_from_tables(ambiguous_regions, missing_fields)
    )

    # Strategy 3: proximity matching
    extracted.update(
        _extract_from_proximity(ambiguous_regions, missing_fields)
    )

    return extracted


# ============================================================
# STRATEGY 1 — RELATION-BASED EXTRACTION
# ============================================================

def _extract_from_relations(
    relations: List[Tuple],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Uses spatial relations like:
    ("Policy Number", "HAS_VALUE", "ABC123", 0.92)
    """

    extracted = {}

    LABEL_MAP = {
        "policy number": "policy_number",
        "policy no": "policy_number",
        "insured name": "insured_name",
        "named insured": "insured_name",
        "effective date": "effective_date",
        "expiration date": "expiration_date",
        "mailing address": "mailing_address",
        "property address": "property_address",
        "total premium": "total_premium",
        "deductible": "deductible",
    }

    for rel in relations:
        if len(rel) != 4:
            continue

        label, rel_type, value, confidence = rel

        if rel_type != "HAS_VALUE":
            continue

        field = LABEL_MAP.get(label.lower().strip(":"))
        if not field or field not in missing_fields:
            continue

        if not _basic_sanity(field, value):
            continue

        extracted[field] = {
            "value": value.strip(),
            "confidence": round(confidence * 0.80, 3),  # spatial penalty
            "source": "layout",
            "method": "relation",
        }

    return extracted


# ============================================================
# STRATEGY 2 — TABLE EXTRACTION
# ============================================================

def _extract_from_tables(
    regions: List[Dict],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Handles tables where headers and values are separated.
    """

    extracted = {}

    tables = _detect_tables(regions)
    for table in tables:
        headers = table[0]
        rows = table[1:]

        header_map = {}
        for idx, h in enumerate(headers):
            text = h["text"].lower()
            if "premium" in text:
                header_map[idx] = "total_premium"
            elif "deductible" in text:
                header_map[idx] = "deductible"

        for row in rows:
            for idx, cell in enumerate(row):
                field = header_map.get(idx)
                if field and field in missing_fields:
                    if _basic_sanity(field, cell["text"]):
                        extracted[field] = {
                            "value": cell["text"].strip(),
                            "confidence": round(cell.get("confidence", 0.8) * 0.78, 3),
                            "source": "layout",
                            "method": "table",
                        }

    return extracted


def _detect_tables(elements: List[Dict]) -> List[List[List[Dict]]]:
    """
    Groups elements into simple row-based tables using Y proximity.
    """

    if len(elements) < 6:
        return []

    sorted_elems = sorted(elements, key=lambda e: e["box"][1])
    rows = []
    current = [sorted_elems[0]]
    current_y = sorted_elems[0]["box"][1]

    for el in sorted_elems[1:]:
        y = el["box"][1]
        if abs(y - current_y) < 30:
            current.append(el)
        else:
            if len(current) >= 2:
                rows.append(current)
            current = [el]
            current_y = y

    if len(current) >= 2:
        rows.append(current)

    if len(rows) >= 2:
        return [rows]

    return []


# ============================================================
# STRATEGY 3 — PROXIMITY MATCHING
# ============================================================

def _extract_from_proximity(
    regions: List[Dict],
    missing_fields: List[str],
) -> Dict[str, Dict]:
    """
    Finds values spatially near labels.
    """

    extracted = {}

    labels = [r for r in regions if r.get("role") == "label"]
    values = [r for r in regions if r.get("role") == "value"]

    FIELD_LABELS = {
        "policy_number": ["policy"],
        "insured_name": ["insured", "policyholder"],
        "effective_date": ["effective"],
        "expiration_date": ["expiration"],
        "total_premium": ["premium"],
        "deductible": ["deductible"],
    }

    for field, keywords in FIELD_LABELS.items():
        if field not in missing_fields:
            continue

        label = _find_label(labels, keywords)
        if not label:
            continue

        value = _nearest_value(label, values)
        if not value:
            continue

        if not _basic_sanity(field, value["text"]):
            continue

        extracted[field] = {
            "value": value["text"].strip(),
            "confidence": round(value.get("confidence", 0.8) * 0.75, 3),
            "source": "layout",
            "method": "proximity",
        }

    return extracted


def _find_label(labels: List[Dict], keywords: List[str]) -> Optional[Dict]:
    for l in labels:
        t = l["text"].lower()
        if any(k in t for k in keywords):
            return l
    return None


def _nearest_value(label: Dict, values: List[Dict]) -> Optional[Dict]:
    lx1, ly1, lx2, ly2 = label["box"]
    lc_x = (lx1 + lx2) / 2
    lc_y = (ly1 + ly2) / 2

    best = None
    best_dist = float("inf")

    for v in values:
        vx1, vy1, vx2, vy2 = v["box"]
        vc_x = (vx1 + vx2) / 2
        vc_y = (vy1 + vy2) / 2

        dist = math.hypot(vc_x - lc_x, vc_y - lc_y)

        if dist < best_dist and dist < 200:
            best = v
            best_dist = dist

    return best


# ============================================================
# BASIC SANITY (NOT NORMALIZATION)
# ============================================================

def _basic_sanity(field: str, value: str) -> bool:
    if not value or len(value.strip()) < 2:
        return False

    if field in {"policy_number", "loan_number"}:
        return sum(c.isdigit() for c in value) >= 3

    if field in {"insured_name"}:
        return not any(c.isdigit() for c in value)

    if field in {"total_premium", "deductible"}:
        return any(c.isdigit() for c in value)

    return True
