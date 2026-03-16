#npm install concurrently
from fastapi import FastAPI, UploadFile, File
from fastapi.concurrency import run_in_threadpool
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
import uuid
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# from pdf2image import convert_from_path
import fitz
from orchestrator import run_pipeline_batch
from agents.document_router import classify_doc_type
from agents.document_classifier import get_document_explanation
from agents.policy_classifier import classify_policy, get_policy_explanation
from agents.insurance_segmentation import get_allowed_fields
from agents.validation_agent import enrich_api_fields

ENABLE_STRUCTURED_OCR_DISPLAY = os.getenv("ENABLE_STRUCTURED_OCR_DISPLAY", "0") == "1"
ZIP_ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf")
PDF_RENDER_DPI = int(os.getenv("PDF_RENDER_DPI", "200"))
LARGE_PDF_RENDER_DPI = int(os.getenv("LARGE_PDF_RENDER_DPI", "144"))
LARGE_PDF_PAGE_THRESHOLD = int(os.getenv("LARGE_PDF_PAGE_THRESHOLD", "40"))
MAX_ANALYZE_PDF_PAGES = int(os.getenv("MAX_ANALYZE_PDF_PAGES", "20"))
PDF_ALWAYS_INCLUDE_FIRST_PAGES = int(os.getenv("PDF_ALWAYS_INCLUDE_FIRST_PAGES", "3"))
LARGE_PDF_TEXT_FAST_PATH_MIN_FIELDS = int(os.getenv("LARGE_PDF_TEXT_FAST_PATH_MIN_FIELDS", "4"))
LARGE_PDF_TEXT_FAST_PATH_MIN_REQUIRED = int(os.getenv("LARGE_PDF_TEXT_FAST_PATH_MIN_REQUIRED", "4"))
PDF_RELEVANCE_KEYWORDS = (
    "declaration",
    "declarations",
    "certificate",
    "insured",
    "named insured",
    "policy",
    "coverage",
    "mortgage",
    "loan",
    "property",
    "premises",
    "effective",
    "expiration",
    "producer",
    "unit owner",
    "residence",
)
TEXT_FAST_PATH_REQUIRED_FIELDS = (
    "carrier_name",
    "policy_number",
    "insured_name",
    "effective_date",
    "expiration_date",
    "property_address",
)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
logger = logging.getLogger("agentic_ocr.api")

# app = FastAPI(title="Agentic OCR API", version="2.0")
app = FastAPI(
    title="Agentic OCR API",
    version="2.0",
    root_path="/api"
)
# Allow frontend (Next.js) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origin_regex=r"https://10\.0\.0\.\d+:9444",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

def _render_pdf_page(page, dpi: int):
    pix = page.get_pixmap(dpi=dpi)

    img = np.frombuffer(
        pix.samples,
        dtype=np.uint8
    ).reshape(pix.height, pix.width, pix.n)

    if pix.n == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _score_pdf_page_text(text: str, page_index: int) -> float:
    if not isinstance(text, str):
        text = ""

    lowered = text.lower()
    score = 0.0

    for keyword in PDF_RELEVANCE_KEYWORDS:
        if keyword in lowered:
            score += 3.0 if " " in keyword else 1.5

    if lowered.strip():
        score += 0.5

    # Earlier pages are more likely to contain the declaration/certificate pages.
    score += max(0.0, 2.0 - (page_index * 0.05))
    return score


def _extract_pdf_text_lines(page) -> list:
    try:
        text = page.get_text("text")
    except Exception:
        return []

    if not isinstance(text, str) or not text.strip():
        return []
    return [line.strip() for line in text.splitlines() if line and line.strip()]


def _normalize_text_match(value: str) -> str:
    if not isinstance(value, str):
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _select_pdf_page_indices(doc, max_pages: int):
    total_pages = int(doc.page_count or 0)
    if max_pages <= 0 or total_pages <= max_pages:
        return list(range(total_pages))

    chosen = set(range(min(total_pages, max(0, PDF_ALWAYS_INCLUDE_FIRST_PAGES))))
    scored = []

    for page_index in range(total_pages):
        try:
            text = doc.load_page(page_index).get_text("text")
        except Exception:
            text = ""
        scored.append((_score_pdf_page_text(text, page_index), page_index))

    scored.sort(key=lambda item: (-item[0], item[1]))
    for _, page_index in scored:
        chosen.add(page_index)
        if len(chosen) >= max_pages:
            break

    selected = sorted(chosen)
    if len(selected) > max_pages:
        selected = selected[:max_pages]
    return selected


def load_document_for_analysis(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    logger.info("load_document_for_analysis.start path=%s ext=%s", file_path, ext or "none")

    if ext != ".pdf":
        pages = load_input(file_path)
        return {
            "pages": pages,
            "page_numbers": list(range(len(pages))),
            "total_pages": len(pages),
            "page_limit_applied": False,
        }

    try:
        doc = fitz.open(file_path)
        try:
            total_pages = int(doc.page_count or 0)
            selected_pages = list(range(total_pages))
            page_limit_applied = False

            if total_pages > LARGE_PDF_PAGE_THRESHOLD and total_pages > MAX_ANALYZE_PDF_PAGES:
                selected_pages = _select_pdf_page_indices(doc, MAX_ANALYZE_PDF_PAGES)
                page_limit_applied = len(selected_pages) < total_pages

            dpi = LARGE_PDF_RENDER_DPI if total_pages > LARGE_PDF_PAGE_THRESHOLD else PDF_RENDER_DPI
            pages = []
            text_lines_by_page = []
            for page_index in selected_pages:
                page = doc.load_page(page_index)
                text_lines_by_page.append(_extract_pdf_text_lines(page))
                pages.append(_render_pdf_page(page, dpi=dpi))
        finally:
            doc.close()
    except Exception as e:
        logger.exception("load_document_for_analysis.failed path=%s error=%s", file_path, e)
        return {
            "pages": [],
            "page_numbers": [],
            "total_pages": 0,
            "page_limit_applied": False,
            "text_lines_by_page": [],
        }

    logger.info(
        "load_document_for_analysis.complete path=%s total_pages=%d selected_pages=%d dpi=%d",
        file_path,
        total_pages,
        len(selected_pages),
        LARGE_PDF_RENDER_DPI if total_pages > LARGE_PDF_PAGE_THRESHOLD else PDF_RENDER_DPI,
    )
    return {
        "pages": pages,
        "page_numbers": selected_pages,
        "total_pages": total_pages,
        "page_limit_applied": page_limit_applied,
        "text_lines_by_page": text_lines_by_page,
    }


def _remap_result_pages(results: list, page_numbers: list):
    if not results or not page_numbers or len(results) != len(page_numbers):
        return results

    remapped = []
    for idx, result in enumerate(results):
        actual_page = page_numbers[idx]
        cloned = dict(result)
        cloned_fields = {}
        for field_name, field_data in (result.get("fields", {}) or {}).items():
            if isinstance(field_data, dict):
                updated = field_data.copy()
                if isinstance(updated.get("page"), int):
                    updated["page"] = actual_page
                cloned_fields[field_name] = updated
            else:
                cloned_fields[field_name] = field_data
        cloned["fields"] = cloned_fields
        remapped.append(cloned)
    return remapped


def _remap_field_pages(fields: dict, page_numbers: list):
    if not isinstance(fields, dict) or not page_numbers:
        return fields

    remapped = {}
    for field_name, field_data in fields.items():
        if isinstance(field_data, dict):
            updated = field_data.copy()
            page_idx = updated.get("page")
            if isinstance(page_idx, int) and 0 <= page_idx < len(page_numbers):
                updated["page"] = page_numbers[page_idx]
            remapped[field_name] = updated
        else:
            remapped[field_name] = field_data
    return remapped


def _assign_field_pages_from_text(fields: dict, text_lines_by_page: list, page_numbers: list):
    if not isinstance(fields, dict) or not text_lines_by_page or not page_numbers:
        return fields

    out = {}
    normalized_pages = ["\n".join(lines or []) for lines in text_lines_by_page]
    normalized_pages = [_normalize_text_match(page_text) for page_text in normalized_pages]

    for field_name, field_data in fields.items():
        if not isinstance(field_data, dict):
            out[field_name] = field_data
            continue

        updated = field_data.copy()
        value = _normalize_text_match(str(updated.get("value", "") or ""))
        if value and not isinstance(updated.get("page"), int):
            for idx, page_text in enumerate(normalized_pages):
                if value in page_text or page_text in value:
                    updated["page"] = idx
                    break
        out[field_name] = updated

    return out


def _can_use_large_pdf_text_fast_path(text_lines_by_page: list, total_pages: int) -> bool:
    if total_pages < LARGE_PDF_PAGE_THRESHOLD:
        return False
    non_empty_pages = sum(1 for lines in text_lines_by_page if isinstance(lines, list) and len(lines) >= 3)
    return non_empty_pages >= 2


def _run_large_pdf_text_fast_path(text_lines_by_page: list, page_numbers: list, total_pages: int):
    if not _can_use_large_pdf_text_fast_path(text_lines_by_page, total_pages):
        return None

    all_lines = [line for page_lines in text_lines_by_page for line in (page_lines or []) if isinstance(line, str) and line.strip()]
    if len(all_lines) < 20:
        return None

    doc_type = classify_doc_type(all_lines)
    policy_type = classify_policy(all_lines)
    expected_fields = order_expected_fields(get_allowed_fields(doc_type, policy_type))

    clean_fields = enrich_api_fields(
        clean_fields={},
        expected_fields=expected_fields,
        lines=all_lines,
        doc_type=doc_type,
        policy_type=policy_type,
        ocr_confidence=0.97,
    )
    clean_fields = _assign_field_pages_from_text(clean_fields, text_lines_by_page, page_numbers)

    found_fields = sum(
        1 for data in clean_fields.values()
        if isinstance(data, dict) and str(data.get("value", "") or "").strip()
    )
    found_required = sum(
        1
        for field_name in TEXT_FAST_PATH_REQUIRED_FIELDS
        if isinstance(clean_fields.get(field_name), dict)
        and str(clean_fields[field_name].get("value", "") or "").strip()
    )

    if found_fields < LARGE_PDF_TEXT_FAST_PATH_MIN_FIELDS:
        return None
    if found_required < LARGE_PDF_TEXT_FAST_PATH_MIN_REQUIRED:
        return None

    return {
        "document_type": doc_type,
        "policy_type": policy_type,
        "expected_fields": expected_fields,
        "clean_fields": clean_fields,
        "all_lines": all_lines,
        "raw_lines_by_page": text_lines_by_page,
        "confidence": 0.97,
    }


def load_input(file_path: str):

    ext = os.path.splitext(file_path)[1].lower()
    logger.info("load_input.start path=%s ext=%s", file_path, ext or "none")

    if ext == ".pdf":
        pages = []

        try:
            doc = fitz.open(file_path)

            for page in doc:
                pages.append(_render_pdf_page(page, dpi=PDF_RENDER_DPI))

            doc.close()

        except Exception as e:
            logger.exception("load_input.pdf_conversion_failed path=%s error=%s", file_path, e)
            return []

        logger.info("load_input.complete path=%s pages=%d", file_path, len(pages))
        return pages

    img = cv2.imread(file_path)

    if img is None:
        logger.warning("load_input.image_read_failed path=%s", file_path)
        return []

    logger.info("load_input.complete path=%s pages=1", file_path)
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
    def _encode(page):
        if page is None:
            return None
        # Faster encode settings; preserves PNG output format.
        success, buffer = cv2.imencode(
            ".png",
            page,
            [cv2.IMWRITE_PNG_COMPRESSION, 1],
        )
        if not success:
            return None
        encoded = base64.b64encode(buffer).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    if not pages:
        return []

    max_workers = min(len(pages), max(1, (os.cpu_count() or 2)))
    if max_workers <= 1:
        return [img for img in (_encode(page) for page in pages) if img]

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        encoded_pages = list(ex.map(_encode, pages))
    return [img for img in encoded_pages if img]


@lru_cache(maxsize=1)
def load_vision_agent():
    # OCR-only helper for API post-processing; keep it lightweight.
    from agents.vision_agent import VisionAgent
    return VisionAgent(use_layoutxlm=False)


def find_value_bbox(value: str, words: list, boxes: list, prepared=None):
    if not value or not words or not boxes:
        return None
    value_clean = value.strip()
    if not value_clean:
        return None

    if prepared is None:
        ocr_words = [w.strip() if isinstance(w, str) else "" for w in words]
        ocr_lower = [w.lower() for w in ocr_words]
        ocr_norm = [re.sub(r"\s+", " ", w) for w in ocr_lower]
    else:
        ocr_lower, ocr_norm = prepared

    value_lower = value_clean.lower()

    for idx, wl in enumerate(ocr_lower):
        if wl == value_lower and idx < len(boxes) and boxes[idx]:
            return list(boxes[idx])

    value_lower_norm = re.sub(r"\s+", " ", value_lower)
    for idx, wl in enumerate(ocr_lower):
        if idx < len(boxes) and boxes[idx]:
            wl_norm = ocr_norm[idx]
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
        logger.exception("bbox_synthesis.vision_agent_load_failed error=%s", e)
        return fields

    patched = {}
    for k, v in fields.items():
        patched[k] = v.copy() if isinstance(v, dict) else v

    pending_fields = {}
    for field_name, field_data in patched.items():
        if (
            isinstance(field_data, dict)
            and field_data.get("bbox") is None
            and isinstance(field_data.get("value"), str)
            and field_data.get("value", "").strip()
        ):
            pending_fields[field_name] = field_data

    if not pending_fields:
        return patched

    preferred_pages = {}
    for field_name, field_data in pending_fields.items():
        page_idx = field_data.get("page")
        if isinstance(page_idx, int) and 0 <= page_idx < len(pages):
            preferred_pages.setdefault(page_idx, []).append(field_name)

    for page_idx in sorted(preferred_pages):
        page = pages[page_idx]
        try:
            ocr = vision.ocr_engine.run_with_boxes(page)
            words = ocr.get("text", []) if isinstance(ocr, dict) else []
            boxes = ocr.get("boxes", []) if isinstance(ocr, dict) else []
        except Exception as e:
            logger.warning("bbox_synthesis.preferred_page_failed page=%d error=%s", page_idx, e)
            continue

        if not words or not boxes:
            continue

        ocr_words = [w.strip() if isinstance(w, str) else "" for w in words]
        ocr_lower = [w.lower() for w in ocr_words]
        ocr_norm = [re.sub(r"\s+", " ", w) for w in ocr_lower]

        solved = []
        for field_name in preferred_pages[page_idx]:
            field_data = pending_fields.get(field_name)
            if not isinstance(field_data, dict):
                continue
            value = field_data.get("value", "")
            if not isinstance(value, str) or not value.strip():
                continue
            bbox = find_value_bbox(value, words, boxes, prepared=(ocr_lower, ocr_norm))
            if bbox:
                field_data["bbox"] = bbox
                field_data["page"] = page_idx
                solved.append(field_name)

        for field_name in solved:
            pending_fields.pop(field_name, None)

    def _ocr_page(payload):
        page_idx, page = payload
        try:
            ocr = vision.ocr_engine.run_with_boxes(page)
            words = ocr.get("text", []) if isinstance(ocr, dict) else []
            boxes = ocr.get("boxes", []) if isinstance(ocr, dict) else []
            return page_idx, words, boxes, None
        except Exception as e:
            return page_idx, [], [], e

    max_workers = min(len(pages), max(1, (os.cpu_count() or 2)))
    chunk_size = max(1, max_workers)
    skipped_pages = set(preferred_pages)

    # Chunked parallel OCR preserves first-page precedence and avoids scanning
    # remaining pages once all missing bbox fields are resolved.
    for start in range(0, len(pages), chunk_size):
        if not pending_fields:
            break

        chunk = [
            (page_idx, page)
            for page_idx, page in enumerate(pages[start:start + chunk_size], start)
            if page_idx not in skipped_pages
        ]
        if not chunk:
            continue
        if max_workers <= 1 or len(chunk) == 1:
            chunk_results = [_ocr_page(item) for item in chunk]
        else:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(chunk))) as ex:
                chunk_results = list(ex.map(_ocr_page, chunk))

        chunk_results.sort(key=lambda x: x[0])
        for page_idx, words, boxes, err in chunk_results:
            if err:
                logger.warning("bbox_synthesis.ocr_prescan_failed page=%d error=%s", page_idx, err)
                continue
            if not words or not boxes:
                continue

            ocr_words = [w.strip() if isinstance(w, str) else "" for w in words]
            ocr_lower = [w.lower() for w in ocr_words]
            ocr_norm = [re.sub(r"\s+", " ", w) for w in ocr_lower]

            solved = []
            for field_name, field_data in pending_fields.items():
                value = field_data.get("value", "")
                if not isinstance(value, str) or not value.strip():
                    continue

                bbox = find_value_bbox(value, words, boxes, prepared=(ocr_lower, ocr_norm))
                if bbox:
                    field_data["bbox"] = bbox
                    field_data["page"] = page_idx
                    solved.append(field_name)

            for field_name in solved:
                pending_fields.pop(field_name, None)

            if not pending_fields:
                break

    return patched


def build_display_ocr_by_page(pages: list):
    ocr_lines_by_page = []
    try:
        vision = load_vision_agent()
    except Exception as e:
        logger.exception("display_ocr.vision_agent_load_failed error=%s", e)
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
            logger.warning("display_ocr.page_failed page=%d error=%s", page_idx, e)
            ocr_lines_by_page.append([])
    return ocr_lines_by_page

def _page_has_text(lines) -> bool:
    if not isinstance(lines, list):
        return False
    return any(isinstance(ln, str) and ln.strip() for ln in lines)


def merge_structured_with_fallback(structured_lines, fallback_lines):
    if not isinstance(fallback_lines, list):
        return fallback_lines
    if not isinstance(structured_lines, list):
        return fallback_lines

    merged = []
    total = max(len(structured_lines), len(fallback_lines))
    for idx in range(total):
        structured_page = structured_lines[idx] if idx < len(structured_lines) else []
        fallback_page = fallback_lines[idx] if idx < len(fallback_lines) else []
        merged.append(structured_page if _page_has_text(structured_page) else fallback_page)
    return merged


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

@app.post("/preview")
async def preview(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex[:8]
    request_start = time.time()
    tmp_path = None
    try:
        file_name = file.filename or "unnamed"
        logger.info("preview.start request_id=%s file=%s", request_id, file_name)
        suffix = os.path.splitext(file.filename or "")[-1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pages = load_input(tmp_path)

        if not pages:
            logger.warning("preview.no_pages request_id=%s file=%s", request_id, file_name)
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to generate preview"},
            )

        logger.info(
            "preview.complete request_id=%s file=%s pages=%d elapsed=%.2fs",
            request_id,
            file_name,
            len(pages),
            time.time() - request_start,
        )
        return {
            "page_count": len(pages),
            "pages": pages_to_base64_png(pages),
        }

    except Exception as e:
        logger.exception("preview.failed request_id=%s error=%s", request_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.warning("preview.cleanup_failed request_id=%s path=%s error=%s", request_id, tmp_path, e)


@app.post("/expand-zip")
async def expand_zip(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex[:8]
    request_start = time.time()
    try:
        file_name = file.filename or "unnamed"
        logger.info("expand_zip.start request_id=%s file=%s", request_id, file_name)
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
            logger.warning("expand_zip.no_supported_files request_id=%s file=%s", request_id, file_name)
            return JSONResponse(
                status_code=400,
                content={"error": "No supported files found inside ZIP."},
            )

        logger.info(
            "expand_zip.complete request_id=%s file=%s extracted=%d elapsed=%.2fs",
            request_id,
            file_name,
            len(expanded_files),
            time.time() - request_start,
        )
        return {
            "file_count": len(expanded_files),
            "files": expanded_files,
        }
    except Exception as e:
        logger.exception("expand_zip.failed request_id=%s error=%s", request_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex[:8]
    request_start = time.time()
    tmp_path = None
    try:
        file_name = file.filename or "unnamed"
        logger.info("analyze.start request_id=%s file=%s", request_id, file_name)
        suffix = os.path.splitext(file.filename or "")[-1]

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        document = load_document_for_analysis(tmp_path)
        pages = document.get("pages", [])
        analyzed_page_numbers = document.get("page_numbers", [])
        total_pages = int(document.get("total_pages", len(pages)) or len(pages))
        page_limit_applied = bool(document.get("page_limit_applied", False))
        text_lines_by_page = document.get("text_lines_by_page", [])
        logger.info(
            "analyze.loaded request_id=%s file=%s pages=%d total_pages=%d page_limit_applied=%s",
            request_id,
            file_name,
            len(pages),
            total_pages,
            page_limit_applied,
        )

        if not pages:
            logger.warning("analyze.no_pages request_id=%s file=%s", request_id, file_name)
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to read document"},
            )

        start = time.time()

        fast_path = _run_large_pdf_text_fast_path(
            text_lines_by_page=text_lines_by_page,
            page_numbers=analyzed_page_numbers,
            total_pages=total_pages,
        )

        if fast_path is None:
            # Run CPU-heavy pipeline in a threadpool to avoid blocking the event loop
            results = await run_in_threadpool(run_pipeline_batch, pages)
            results = _remap_result_pages(results, analyzed_page_numbers)
            logger.info("analyze.pipeline_completed request_id=%s file=%s page_results=%d", request_id, file_name, len(results or []))
        else:
            results = []
            logger.info(
                "analyze.text_fast_path_used request_id=%s file=%s selected_pages=%d total_pages=%d",
                request_id,
                file_name,
                len(analyzed_page_numbers),
                total_pages,
            )

        if not results and fast_path is None:
            return {
                "document_type": "OTH",
                "policy_type": "OTH",
                "document_type_explanation": get_document_explanation("OTH"),
                "policy_type_explanation": get_policy_explanation("OTH"),
                "confidence": 0,
                "page_count": total_pages,
                "analyzed_page_count": len(pages),
                "analyzed_page_numbers": [page + 1 for page in analyzed_page_numbers],
                "page_limit_applied": page_limit_applied,
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

        if fast_path is not None:
            all_lines = fast_path.get("all_lines", []) or []
            merged_fields = fast_path.get("clean_fields", {}) or {}
            doc_type = fast_path.get("document_type", "OTH")
            policy_type = fast_path.get("policy_type", "OTH")
            expected_fields = fast_path.get("expected_fields", []) or []
            best = {"confidence": fast_path.get("confidence", 0.97)}
            raw_lines_by_page = fast_path.get("raw_lines_by_page", []) or []
        else:
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
            raw_lines_by_page = [r.get("raw_lines", []) or [] for r in results]

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

        if ENABLE_STRUCTURED_OCR_DISPLAY and fast_path is None:
            structured_lines = build_display_ocr_by_page(pages)
            if structured_lines:
                raw_lines_by_page = merge_structured_with_fallback(
                    structured_lines,
                    raw_lines_by_page,
                )
                all_lines = [ln for page_lines in raw_lines_by_page for ln in page_lines]

        clean_fields = enrich_api_fields(
            clean_fields=clean_fields,
            expected_fields=expected_fields,
            lines=all_lines,
            doc_type=doc_type,
            policy_type=policy_type,
            ocr_confidence=float(best.get("confidence", 0.85) or 0.85),
        )

        # Keep bbox synthesis, but skip page image encoding here because
        # analyze no longer returns "pages" and encoding can be expensive.
        clean_fields = synthesize_missing_bboxes(clean_fields, pages)
        clean_fields = _remap_field_pages(clean_fields, analyzed_page_numbers)
        # page_images = pages_to_base64_png(pages)

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

        response = {
            "document_type": doc_type,
            "policy_type": policy_type,
            "document_type_explanation": get_document_explanation(doc_type),
            "policy_type_explanation": get_policy_explanation(policy_type),
            "confidence": best.get("confidence", 0),
            "page_count": total_pages,
            "analyzed_page_count": len(pages),
            "analyzed_page_numbers": [page + 1 for page in analyzed_page_numbers],
            "page_limit_applied": page_limit_applied,
            "fields": clean_fields,
            "raw_lines": all_lines,
            # "pages": page_images,
            "pages": [],
            "raw_lines_by_page": raw_lines_by_page,
            "expected_fields": expected_fields,
            "summary_counts": {
                "perfect": perfect,
                "partial": partial,
                "failed": failed,
            },
            "processing_time": round(time.time() - start, 2),
        }
        logger.info(
            "analyze.complete request_id=%s file=%s pages=%d fields=%d elapsed=%.2fs",
            request_id,
            file_name,
            total_pages,
            len(clean_fields),
            time.time() - request_start,
        )
        return response

    except Exception as e:
        logger.exception("analyze.failed request_id=%s error=%s", request_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.warning("analyze.cleanup_failed request_id=%s path=%s error=%s", request_id, tmp_path, e)


@app.get("/analyze")
def analyze_get():
    return {"message": "Use POST to upload a file."}
