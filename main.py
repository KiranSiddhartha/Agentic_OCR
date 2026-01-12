from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import cv2
import numpy as np

from orchestrator import run_pipeline

app = FastAPI(title="Agentic OCR API", version="1.0")


@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    max_retries: int = 0,
    debug: bool = False,
):
    """
    Fast OCR endpoint - single pass, no async overhead.
    """
    content = await file.read()
    npimg = np.frombuffer(content, np.uint8)
    image = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    if image is None:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid image or PDF page"},
        )

    result = run_pipeline(
        image=image,
        max_retries=max_retries,
        debug=debug,
    )

    return JSONResponse(content=result)
