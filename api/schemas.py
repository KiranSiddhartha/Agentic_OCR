from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple

class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

class OCRResult(BaseModel):
    text: str
    box: BoundingBox
    confidence: float

class LayoutElement(BaseModel):
    text: str
    box: BoundingBox
    element_type: str  # 'text', 'table', 'form', 'header', etc.
    confidence: float

class Relation(BaseModel):
    entity1: str
    relation_type: str
    entity2: str
    confidence: float

class ExtractedField(BaseModel):
    value: str
    confidence: float
    source: str  # 'regex', 'relation', 'layoutxlm'
    bounding_box: Optional[BoundingBox] = None

class DocumentAnalysisResult(BaseModel):
    document_type: str
    ocr_results: List[OCRResult]
    layout_elements: List[LayoutElement]
    relations: List[Relation]
    fields: Dict[str, ExtractedField]
    overall_confidence: float