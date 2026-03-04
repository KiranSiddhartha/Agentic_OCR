#npm install concurrently
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import cv2
import numpy as np
import tempfile
import os
import time
import base64
import re
import io
import zipfile
from functools import lru_cache

from pdf2image import convert_from_path
from orchestrator import run_pipeline_batch
from agents.document_router import classify_doc_type
from agents.document_classifier import get_document_explanation
from agents.policy_classifier import classify_policy, get_policy_explanation
from agents.insurance_segmentation import get_allowed_fields

ENABLE_STRUCTURED_OCR_DISPLAY = os.getenv("ENABLE_STRUCTURED_OCR_DISPLAY", "0") == "1"
ZIP_ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf")

app = FastAPI(title="Agentic OCR API", version="2.0")

# Allow frontend (Next.js) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_input(file_path: str):
    """
    Convert uploaded file into list of OpenCV images.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        pil_pages = convert_from_path(file_path, dpi=300)
        pages = []
        for p in pil_pages:
            img = cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR)
            pages.append(img)
        return pages

    img = cv2.imread(file_path)
    return [img]


def _guess_mime_from_name(name: str) -> str:
    lower = (name or "").lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".tif") or lower.endswith(".tiff"):
        return "image/tiff"
    return "application/octet-stream"


def pages_to_base64_png(pages):
    page_images = []
    for page in pages:
        if page is None:
            continue
        success, buffer = cv2.imencode(".png", page)
        if success:
            encoded = base64.b64encode(buffer).decode("utf-8")
            page_images.append(f"data:image/png;base64,{encoded}")
    return page_images


@lru_cache(maxsize=1)
def load_vision_agent():
    # OCR-only helper for API post-processing; keep it lightweight.
    from agents.vision_agent import VisionAgent
    return VisionAgent(use_layoutxlm=False)


def find_value_bbox(value: str, words: list, boxes: list):
    if not value or not words or not boxes:
        return None
    value_clean = value.strip()
    if not value_clean:
        return None

    ocr_words = [w.strip() if isinstance(w, str) else "" for w in words]
    ocr_lower = [w.lower() for w in ocr_words]
    value_lower = value_clean.lower()

    for idx, wl in enumerate(ocr_lower):
        if wl == value_lower and idx < len(boxes) and boxes[idx]:
            return list(boxes[idx])

    value_lower_norm = re.sub(r"\s+", " ", value_lower)
    for idx, wl in enumerate(ocr_lower):
        if idx < len(boxes) and boxes[idx]:
            wl_norm = re.sub(r"\s+", " ", wl)
            if value_lower_norm in wl_norm or wl_norm in value_lower_norm:
                if len(wl_norm) >= 4:
                    return list(boxes[idx])
    return None


def synthesize_missing_bboxes(fields: dict, pages: list):
    if not fields or not pages:
        return fields

    try:
        vision = load_vision_agent()
    except Exception as e:
        print(f"[API] Vision agent load failed, bbox synthesis skipped: {e}")
        return fields

    patched = {}
    for k, v in fields.items():
        patched[k] = v.copy() if isinstance(v, dict) else v

    for page_idx, page in enumerate(pages):
        pending = [
            fd for fd in patched.values()
            if isinstance(fd, dict)
            and fd.get("bbox") is None
            and isinstance(fd.get("value"), str)
            and fd.get("value", "").strip()
        ]
        if not pending:
            break

        try:
            ocr = vision.ocr_engine.run_with_boxes(page)
        except Exception as e:
            print(f"[API] OCR pre-scan failed page {page_idx}: {e}")
            continue

        words = ocr.get("text", []) if isinstance(ocr, dict) else []
        boxes = ocr.get("boxes", []) if isinstance(ocr, dict) else []
        if not words or not boxes:
            continue

        for field_name, field_data in patched.items():
            if not isinstance(field_data, dict):
                continue
            if field_data.get("bbox") is not None:
                if field_data.get("page") is None:
                    field_data["page"] = page_idx
                continue

            value = field_data.get("value", "")
            if not isinstance(value, str) or not value.strip():
                continue

            bbox = find_value_bbox(value, words, boxes)
            if bbox:
                field_data["bbox"] = bbox
                field_data["page"] = page_idx

    return patched


def build_display_ocr_by_page(pages: list):
    ocr_lines_by_page = []
    try:
        vision = load_vision_agent()
    except Exception as e:
        print(f"[API] Vision agent load failed for display OCR: {e}")
        return ocr_lines_by_page

    for page_idx, page in enumerate(pages):
        try:
            structured = vision.run_vision_structured(page)
            md = structured.get("markdown", "") if isinstance(structured, dict) else ""
            if isinstance(md, str) and md.strip():
                ocr_lines_by_page.append(md.splitlines())
            else:
                ocr_lines_by_page.append([])
        except Exception as e:
            print(f"[API] Structured OCR failed page {page_idx}: {e}")
            ocr_lines_by_page.append([])
    return ocr_lines_by_page


FIELD_DISPLAY_ORDER = [
    "carrier_name",
    "policy_number",
    "insured_name",
    "effective_date",
    "expiration_date",
    "property_address",
    "mailing_address",
    "mortgage_company",
    "loan_number",
    "total_premium",
    "cancellation_date",
    "cancellation_reason",
    "balance_due",
    "issue_date",
    "remit_info",
]


def order_expected_fields(field_names):
    ordered = []
    field_set = set(field_names or [])
    for name in FIELD_DISPLAY_ORDER:
        if name in field_set:
            ordered.append(name)
    for name in sorted(field_set):
        if name not in ordered:
            ordered.append(name)
    return ordered


def _extract_carrier_name_from_lines(lines):
    # Prefer compact carrier brand name for UI consistency.
    carrier_patterns = [
        (r"\bencompass\b", "Encompass"),
        (r"\berie\b", "Erie"),
        (r"\ballstate\b", "Allstate"),
        (r"\bstate\s+farm\b", "State Farm"),
        (r"\bfarmers\b", "Farmers"),
        (r"\btravelers\b", "Travelers"),
        (r"\bprogressive\b", "Progressive"),
        (r"\bnationwide\b", "Nationwide"),
        (r"\bliberty\s+mutual\b", "Liberty Mutual"),
        (r"\bchubb\b", "Chubb"),
    ]
    text = " ".join(lines).lower()
    for pattern, normalized in carrier_patterns:
        if re.search(pattern, text, re.I):
            return normalized
    return None


def _extract_loan_number_from_lines(lines):
    text = "\n".join(lines)
    m = re.search(r"loan\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9\-]{4,})", text, re.I)
    if m:
        return m.group(1).strip()
    return None


def _extract_total_premium_from_lines(lines):
    # First try same-line patterns.
    for line in lines:
        ll = line.lower()
        if "total premium" in ll or "total residence premium" in ll:
            m = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", line)
            if m:
                return f"${m.group(1)}"

    # Then try next-line amount after a premium label.
    for idx, line in enumerate(lines):
        ll = line.lower()
        if "total premium" in ll or "total residence premium" in ll:
            if idx + 1 < len(lines):
                nxt = lines[idx + 1]
                m = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", nxt)
                if m:
                    return f"${m.group(1)}"
    return None


def _extract_effective_date_from_lines(lines):
    text = "\n".join(lines)
    patterns = [
        r"policy effective date\s*(?:is|:)?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"effective date\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"beginning\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _extract_expiration_date_from_lines(lines):
    text = "\n".join(lines)
    patterns = [
        r"expiration date\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"through\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"to\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _extract_property_address_from_lines(lines):
    text = "\n".join(lines)
    m = re.search(
        r"coverage detail for\s+(.+?,\s*[A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
        text,
        re.I,
    )
    if m:
        return m.group(1).strip()

    for line in lines:
        if re.search(r"\d+\s+.+,\s*[A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?", line):
            return line.strip()
    return None


def fill_missing_expected_fields(clean_fields: dict, expected_fields: list, all_lines: list):
    patched = dict(clean_fields)

    def put_if_missing(field_name, value):
        if field_name not in expected_fields:
            return
        if not value:
            return
        existing = patched.get(field_name, {})
        if isinstance(existing, dict) and existing.get("value"):
            return
        patched[field_name] = {
            "value": value,
            "bbox": existing.get("bbox") if isinstance(existing, dict) else None,
            "page": existing.get("page") if isinstance(existing, dict) else None,
        }

    put_if_missing("carrier_name", _extract_carrier_name_from_lines(all_lines))
    put_if_missing("loan_number", _extract_loan_number_from_lines(all_lines))
    put_if_missing("total_premium", _extract_total_premium_from_lines(all_lines))
    put_if_missing("effective_date", _extract_effective_date_from_lines(all_lines))
    put_if_missing("expiration_date", _extract_expiration_date_from_lines(all_lines))
    put_if_missing("property_address", _extract_property_address_from_lines(all_lines))
    return patched


@app.post("/preview")
async def preview(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pages = load_input(tmp_path)
        os.remove(tmp_path)

        if not pages:
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to generate preview"},
            )

        return {
            "page_count": len(pages),
            "pages": pages_to_base64_png(pages),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/expand-zip")
async def expand_zip(file: UploadFile = File(...)):
    try:
        if not (file.filename or "").lower().endswith(".zip"):
            return JSONResponse(
                status_code=400,
                content={"error": "Only .zip files are supported for this endpoint."},
            )

        raw = await file.read()
        if not raw:
            return JSONResponse(status_code=400, content={"error": "Uploaded ZIP is empty."})

        expanded_files = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if not name.lower().endswith(ZIP_ALLOWED_EXT):
                    continue
                data = zf.read(info)
                if not data:
                    continue
                expanded_files.append(
                    {
                        "name": name.split("/")[-1] or name,
                        "type": _guess_mime_from_name(name),
                        "data_base64": base64.b64encode(data).decode("utf-8"),
                    }
                )

        if not expanded_files:
            return JSONResponse(
                status_code=400,
                content={"error": "No supported files found inside ZIP."},
            )

        return {
            "file_count": len(expanded_files),
            "files": expanded_files,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pages = load_input(tmp_path)

        if not pages:
            os.remove(tmp_path)
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to read document"},
            )

        start = time.time()

        # Run pipeline
        results = run_pipeline_batch(pages)

        if not results:
            os.remove(tmp_path)
            return {
                "document_type": "OTH",
                "policy_type": "OTH",
                "document_type_explanation": get_document_explanation("OTH"),
                "policy_type_explanation": get_policy_explanation("OTH"),
                "confidence": 0,
                "page_count": len(pages),
                "fields": {},
                "pages": [],
                "raw_lines": [],
                "raw_lines_by_page": [],
                "expected_fields": [],
                "summary_counts": {
                    "perfect": 0,
                    "partial": 0,
                    "failed": 0,
                },
            }

        # Merge extraction outputs across pages
        all_lines = []
        merged_fields = {}

        for r in results:
            page_lines = r.get("raw_lines", []) or []
            all_lines.extend(page_lines)
            merged_fields.update(r.get("fields", {}))

        # Classify full document
        doc_type = classify_doc_type(all_lines)
        policy_type = classify_policy(all_lines)
        best = max(results, key=lambda r: r.get("confidence", 0))
        expected_fields = order_expected_fields(
            get_allowed_fields(doc_type, policy_type)
        )

        merged_fields = synthesize_missing_bboxes(merged_fields, pages)

        # Preserve bbox + page and restrict to expected field universe when available.
        clean_fields = {}
        for k, v in merged_fields.items():
            if isinstance(v, dict) and v.get("value"):
                if expected_fields and k not in expected_fields:
                    continue
                clean_fields[k] = {
                    "value": v.get("value"),
                    "bbox": v.get("bbox"),
                    "page": v.get("page", 0) if v.get("bbox") is not None else v.get("page"),
                }

        page_images = pages_to_base64_png(pages)
        raw_lines_by_page = [r.get("raw_lines", []) or [] for r in results]
        if ENABLE_STRUCTURED_OCR_DISPLAY:
            structured_lines = build_display_ocr_by_page(pages)
            if structured_lines:
                raw_lines_by_page = structured_lines
                all_lines = [ln for page_lines in raw_lines_by_page for ln in page_lines]
        clean_fields = fill_missing_expected_fields(clean_fields, expected_fields, all_lines)
        perfect = 0
        partial = 0
        failed = 0
        if expected_fields:
            for field_name in expected_fields:
                value = clean_fields.get(field_name, {}).get("value")
                if value is None:
                    failed += 1
                elif isinstance(value, str) and not value.strip():
                    partial += 1
                else:
                    perfect += 1
        else:
            perfect = len(clean_fields)

        os.remove(tmp_path)

        return {
            "document_type": doc_type,
            "policy_type": policy_type,
            "document_type_explanation": get_document_explanation(doc_type),
            "policy_type_explanation": get_policy_explanation(policy_type),
            "confidence": best.get("confidence", 0),
            "page_count": len(pages),
            "fields": clean_fields,
            "pages": page_images,
            "raw_lines": all_lines,  # 🔥 THIS WAS MISSING
            "raw_lines_by_page": raw_lines_by_page,
            "expected_fields": expected_fields,
            "summary_counts": {
                "perfect": perfect,
                "partial": partial,
                "failed": failed,
            },
            "processing_time": round(time.time() - start, 2),
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/analyze")
def analyze_get():
    return {"message": "Use POST to upload a file."}
