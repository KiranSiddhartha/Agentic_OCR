# agents/relation_extraction_agent.py
# Relation Extraction for Insurance Documents
from typing import List, Dict, Tuple, Optional
import re


class RelationExtractionAgent:
    """
    Extracts semantic relations between entities using
    layout information from VI-LayoutXLM
    """
    
    def __init__(self):
        self.relation_patterns = self._load_relation_patterns()
        
        # Spatial thresholds (in normalized coordinates 0-1000)
        self.horizontal_threshold = 100  # Max horizontal distance for same-line
        self.vertical_threshold = 50     # Max vertical distance for below
    
    def extract_relations(
        self, 
        layout_elements: List[Dict],
        fields: Dict = None
    ) -> List[Tuple[str, str, str, float]]:
        """
        Extract relations: (entity1, relation_type, entity2, confidence)
        
        Examples:
        - ("Policy Number", "HAS_VALUE", "HO-12345678", 0.95)
        - ("Insured Name", "LOCATED_AT", "Property Address", 0.88)
        - ("Effective Date", "PRECEDES", "Expiration Date", 0.92)
        
        Args:
            layout_elements: List of layout elements from VI-LayoutXLM
            fields: Optional dict of extracted fields for semantic relations
        
        Returns:
            List of relation tuples with confidence scores
        """
        relations = []
        
        if not layout_elements:
            return relations
        
        # 1. Spatial relations (based on layout proximity)
        spatial_rels = self._extract_spatial_relations(layout_elements)
        relations.extend(spatial_rels)
        
        # 2. Key-value relations (form fields)
        kv_rels = self._extract_keyvalue_relations(layout_elements)
        relations.extend(kv_rels)
        
        # 3. Semantic relations (based on field types)
        if fields:
            semantic_rels = self._extract_semantic_relations(fields)
            relations.extend(semantic_rels)
        
        # 4. Hierarchical relations (document structure)
        hier_rels = self._extract_hierarchical_relations(layout_elements)
        relations.extend(hier_rels)
        
        # Remove duplicates
        relations = self._deduplicate_relations(relations)
        
        return relations
    
    def _extract_spatial_relations(self, elements: List[Dict]) -> List[Tuple]:
        """Extract relations based on spatial proximity"""
        relations = []
        
        for i, elem1 in enumerate(elements):
            for j, elem2 in enumerate(elements[i+1:], start=i+1):
                # Skip if too far apart
                if self._calculate_distance(elem1, elem2) > 500:
                    continue
                
                # Check if elem2 is directly below elem1
                if self._is_below(elem1, elem2, threshold=self.vertical_threshold):
                    confidence = self._calculate_confidence(elem1, elem2, 'below')
                    if confidence > 0.6:
                        relations.append((
                            elem1['text'],
                            'PRECEDES',
                            elem2['text'],
                            confidence
                        ))
                
                # Check if elem2 is to the right (key-value pair)
                if self._is_right_of(elem1, elem2, threshold=self.horizontal_threshold):
                    if self._looks_like_label(elem1['text']):
                        confidence = self._calculate_confidence(elem1, elem2, 'right')
                        if confidence > 0.7:
                            relations.append((
                                elem1['text'],
                                'HAS_VALUE',
                                elem2['text'],
                                confidence
                            ))
        
        return relations
    
    def _extract_keyvalue_relations(self, elements: List[Dict]) -> List[Tuple]:
        """Extract key-value relations from form-like structures"""
        relations = []
        
        # Separate labels and values based on element type
        labels = [e for e in elements if e.get('element_type') in ['label', 'header']]
        values = [e for e in elements if e.get('element_type') in ['value', 'text']]
        
        for label in labels:
            label_text = label['text'].rstrip(':').strip()
            
            if not self._looks_like_label(label['text']):
                continue
            
            # Find best matching value
            best_value = None
            best_score = 0.0
            
            for value in values:
                # Skip if value is also a label
                if self._looks_like_label(value['text']):
                    continue
                
                # Calculate matching score
                score = self._calculate_kv_score(label, value)
                
                if score > best_score and score > 0.6:
                    best_score = score
                    best_value = value
            
            if best_value:
                relations.append((
                    label_text,
                    'HAS_VALUE',
                    best_value['text'],
                    best_score
                ))
        
        return relations
    
    def _extract_semantic_relations(self, fields: Dict) -> List[Tuple]:
        """Extract relations based on field semantics"""
        relations = []
        
        # Date relations
        if 'effective_date' in fields and 'expiration_date' in fields:
            relations.append((
                'effective_date',
                'BEFORE',
                'expiration_date',
                0.95
            ))
        
        # Policy ownership relations
        if 'policy_number' in fields and 'insured_name' in fields:
            relations.append((
                'policy_number',
                'BELONGS_TO',
                'insured_name',
                0.90
            ))
        
        # Address relations
        if 'insured_name' in fields and 'mailing_address' in fields:
            relations.append((
                'insured_name',
                'LIVES_AT',
                'mailing_address',
                0.88
            ))
        
        if 'property_address' in fields and 'policy_number' in fields:
            relations.append((
                'policy_number',
                'COVERS',
                'property_address',
                0.87
            ))
        
        # Coverage relations
        if 'dwelling_coverage' in fields and 'property_address' in fields:
            relations.append((
                'dwelling_coverage',
                'APPLIES_TO',
                'property_address',
                0.85
            ))
        
        # Premium relations
        if 'total_premium' in fields and 'policy_number' in fields:
            relations.append((
                'total_premium',
                'COST_OF',
                'policy_number',
                0.86
            ))
        
        return relations
    
    def _extract_hierarchical_relations(self, elements: List[Dict]) -> List[Tuple]:
        """Extract hierarchical document structure relations"""
        relations = []
        
        # Identify headers
        headers = [e for e in elements if e.get('element_type') == 'header']
        
        for header in headers:
            # Find elements under this header
            header_bottom = header['box'][3]
            
            # Find next header or end of document
            next_header_top = 1000
            for h in headers:
                if h['box'][1] > header_bottom and h['box'][1] < next_header_top:
                    next_header_top = h['box'][1]
            
            # All elements between current and next header belong to this section
            section_elements = [
                e for e in elements
                if header_bottom < e['box'][1] < next_header_top
                and e != header
            ]
            
            for elem in section_elements[:5]:  # Limit to first 5 for performance
                relations.append((
                    header['text'],
                    'CONTAINS',
                    elem['text'],
                    0.80
                ))
        
        return relations
    
    def _calculate_kv_score(self, label: Dict, value: Dict) -> float:
        """Calculate score for key-value pairing"""
        label_box = label['box']
        value_box = value['box']
        
        score = 0.0
        
        # Same line (horizontal alignment)
        y_diff = abs(label_box[1] - value_box[1])
        if y_diff < 30:
            score += 0.4
            
            # Value is to the right of label
            if value_box[0] > label_box[2]:
                score += 0.3
                
                # Close horizontal distance
                x_diff = value_box[0] - label_box[2]
                if x_diff < 100:
                    score += 0.2
                elif x_diff < 200:
                    score += 0.1
        
        # Vertical alignment (form style)
        elif value_box[1] > label_box[3]:
            y_gap = value_box[1] - label_box[3]
            if y_gap < 50:
                score += 0.3
                
                # Similar horizontal position
                x_diff = abs(label_box[0] - value_box[0])
                if x_diff < 50:
                    score += 0.3
        
        # Confidence boost
        score *= (label.get('confidence', 0.8) + value.get('confidence', 0.8)) / 2
        
        return min(score, 1.0)
    
    def _is_below(self, elem1: Dict, elem2: Dict, threshold: int = 50) -> bool:
        """Check if elem2 is directly below elem1"""
        box1 = elem1['box']
        box2 = elem2['box']
        
        # elem2 should be below elem1
        if box2[1] <= box1[3]:
            return False
        
        # Vertical distance check
        vertical_distance = box2[1] - box1[3]
        if vertical_distance > threshold:
            return False
        
        # Horizontal overlap check
        overlap = min(box1[2], box2[2]) - max(box1[0], box2[0])
        if overlap < 0:
            return False
        
        return True
    
    def _is_right_of(self, elem1: Dict, elem2: Dict, threshold: int = 100) -> bool:
        """Check if elem2 is to the right of elem1 (same line)"""
        box1 = elem1['box']
        box2 = elem2['box']
        
        # elem2 should be to the right
        if box2[0] <= box1[2]:
            return False
        
        # Horizontal distance check
        horizontal_distance = box2[0] - box1[2]
        if horizontal_distance > threshold:
            return False
        
        # Same line check (vertical alignment)
        y_diff = abs(box1[1] - box2[1])
        if y_diff > 30:
            return False
        
        return True
    
    def _calculate_distance(self, elem1: Dict, elem2: Dict) -> float:
        """Calculate Euclidean distance between two elements"""
        box1 = elem1['box']
        box2 = elem2['box']
        
        # Use center points
        center1_x = (box1[0] + box1[2]) / 2
        center1_y = (box1[1] + box1[3]) / 2
        center2_x = (box2[0] + box2[2]) / 2
        center2_y = (box2[1] + box2[3]) / 2
        
        return ((center2_x - center1_x)**2 + (center2_y - center1_y)**2)**0.5
    
    def _calculate_confidence(self, elem1: Dict, elem2: Dict, relation_type: str) -> float:
        """Calculate confidence for a relation"""
        base_conf = 0.8
        
        # Factor in OCR confidence
        conf1 = elem1.get('confidence', 0.8)
        conf2 = elem2.get('confidence', 0.8)
        ocr_conf = (conf1 + conf2) / 2
        
        # Distance factor
        distance = self._calculate_distance(elem1, elem2)
        distance_factor = max(0.5, 1.0 - (distance / 500))
        
        # Relation type factor
        type_factor = 1.0
        if relation_type == 'right' and self._looks_like_label(elem1['text']):
            type_factor = 1.1
        
        confidence = base_conf * ocr_conf * distance_factor * type_factor
        return min(confidence, 1.0)
    
    def _looks_like_label(self, text: str) -> bool:
        """Check if text looks like a field label"""
        if not text:
            return False
        
        label_patterns = [
            r'.*:$',  # Ends with colon
            r'^\s*[A-Z][A-Za-z\s]+:?$',  # Starts with capital
            r'.*(number|name|date|address|amount|total|coverage|premium|policy|insured).*'
        ]
        
        return any(re.match(p, text, re.I) for p in label_patterns)
    
    def _load_relation_patterns(self) -> Dict:
        """Load domain-specific relation patterns"""
        return {
            'temporal': ['BEFORE', 'AFTER', 'DURING', 'PRECEDES'],
            'ownership': ['BELONGS_TO', 'OWNS', 'HAS'],
            'location': ['LOCATED_AT', 'LIVES_AT', 'SITUATED_AT'],
            'containment': ['CONTAINS', 'INCLUDES', 'COMPRISES'],
            'association': ['HAS_VALUE', 'APPLIES_TO', 'COVERS', 'COST_OF']
        }
    
    def _deduplicate_relations(self, relations: List[Tuple]) -> List[Tuple]:
        """Remove duplicate relations, keeping highest confidence"""
        seen = {}
        
        for entity1, rel_type, entity2, conf in relations:
            key = (entity1.lower(), rel_type, entity2.lower())
            
            if key not in seen or seen[key][3] < conf:
                seen[key] = (entity1, rel_type, entity2, conf)
        
        return list(seen.values())