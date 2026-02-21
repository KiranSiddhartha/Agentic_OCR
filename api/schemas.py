# from pydantic import BaseModel
# from typing import List, Dict, Optional, Tuple

# class BoundingBox(BaseModel):
#     x_min: float
#     y_min: float
#     x_max: float
#     y_max: float

# class OCRResult(BaseModel):
#     text: str
#     box: BoundingBox
#     confidence: float

# class LayoutElement(BaseModel):
#     text: str
#     box: BoundingBox
#     element_type: str  # 'text', 'table', 'form', 'header', etc.
#     confidence: float

# class Relation(BaseModel):
#     entity1: str
#     relation_type: str
#     entity2: str
#     confidence: float

# class ExtractedField(BaseModel):
#     value: str
#     confidence: float
#     source: str  # 'regex', 'relation', 'layoutxlm'
#     bounding_box: Optional[BoundingBox] = None

# class DocumentAnalysisResult(BaseModel):
#     document_type: str
#     ocr_results: List[OCRResult]
#     layout_elements: List[LayoutElement]
#     relations: List[Relation]
#     fields: Dict[str, ExtractedField]
#     overall_confidence: float

from pydantic import BaseModel
from typing import List, Dict, Optional, Any


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
    element_type: str   # title, section_header, paragraph, table, key_value,
                        # table_header, table_cell, footnote, page_footer, text
    confidence: float


class Relation(BaseModel):
    entity1: str
    relation_type: str
    entity2: str
    confidence: float


class ExtractedField(BaseModel):
    value: str
    confidence: float
    source: str   # regex, relation, layoutxlm, structure_model
    bounding_box: Optional[BoundingBox] = None


class TableCell(BaseModel):
    row: int
    col: int
    text: str
    is_header: bool = False
    row_span: int = 1
    col_span: int = 1
    box: Optional[BoundingBox] = None


class TableStructure(BaseModel):
    num_rows: int
    num_cols: int
    cells: List[TableCell]
    html: str
    markdown: str
    confidence: float


class StructureBlock(BaseModel):
    block_type: str   # title, section_header, key_value, paragraph,
                      # table, figure, list, footnote, page_footer
    text: str
    box: BoundingBox
    confidence: float
    children: Optional[List["StructureBlock"]] = None
    metadata: Optional[Dict[str, Any]] = None


StructureBlock.model_rebuild()


class DocumentAnalysisResult(BaseModel):
    document_type: str
    ocr_results: List[OCRResult]
    layout_elements: List[LayoutElement]
    structure_blocks: List[StructureBlock]
    tables: List[TableStructure]
    relations: List[Relation]
    fields: Dict[str, ExtractedField]
    overall_confidence: float