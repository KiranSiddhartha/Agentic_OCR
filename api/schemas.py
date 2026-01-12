from pydantic import BaseModel
from typing import List

class OCRResponse(BaseModel):
    lines: List[str]
    confidence: float
