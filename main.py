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
from functools import lru_cache

# from pdf2image import convert_from_path
import fitz
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

# app.add_middleware(
#     CORSMiddleware,
#     allow_origin_regex=r"https://10\.0\.0\.\d+:9444",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

def load_input(file_path: str):
    """
    Convert uploaded file into list of OpenCV images.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        pages = []

        try:
            doc = fitz.open(file_path)

            for page in doc:
                pix = page.get_pixmap(dpi=300)

                img = np.frombuffer(
                    pix.samples,
                    dtype=np.uint8
                ).reshape(pix.height, pix.width, pix.n)

                # Convert RGBA → BGR if needed
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                pages.append(img)

            doc.close()

        except Exception as e:
            print(f"[API] PDF conversion failed: {e}")
            return []

        return pages

    img = cv2.imread(file_path)

    if img is None:
        print(f"[API] Failed to read image: {file_path}")
        return []

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
    text = "\n".join(lines)

    # First preference: explicit label in renewal docs.
    for m in re.finditer(
        r"(?im)\b(?:carrier|company|insurer)\s*name\s*[:\-]?\s*([^\n]+)",
        text,
    ):
        cand = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;-")
        if cand and len(cand) >= 4:
            return cand

    # Fallback: common carrier keywords.
    # Try "policy provided by" or "insurance provided by" pattern first
    for m_prov in re.finditer(
        r"(?im)(?:your\s+)?(?:policy|insurance)\s+provided\s+by\s*:?\s*\n?\s*([^\n]+)",
        text,
    ):
        cand = re.sub(r"\s+", " ", m_prov.group(1)).strip(" .,:;-")
        # Strip trailing noise
        cand = re.sub(r'\s*(customer|phone|tel|fax|www\.|http|\(\d{3}\)).*$', '', cand, flags=re.I).strip()
        if cand and len(cand) >= 6:
            return cand

    carrier_patterns = [
        # Full names first (most specific)
        (r"\ballstate\s+vehicle\s+and\s+property\s+insurance\s+company\b", "Allstate Vehicle and Property Insurance Company"),
        (r"\ballstate\s+fire\s+and\s+casualty\s+insurance\s+company\b", "Allstate Fire and Casualty Insurance Company"),
        (r"\ballstate\s+indemnity\s+company\b", "Allstate Indemnity Company"),
        (r"\ballstate\s+insurance\s+company\b", "Allstate Insurance Company"),
        (r"\badirondack\s+insurance\s+exchange\b", "Adirondack Insurance Exchange"),
        (r"\bencompass\s+indemnity\s+company\b", "Encompass Indemnity Company"),
        (r"\berie\s+insurance\b", "Erie Insurance"),
        # Brand names (less specific, last resort)
        (r"\ballstate\b", "Allstate"),
        (r"\bencompass\b", "Encompass"),
        (r"\berie\b", "Erie"),
        (r"\bstate\s+farm\b", "State Farm"),
        (r"\bfarmers\b", "Farmers"),
        (r"\btravelers\b", "Travelers"),
        (r"\bprogressive\b", "Progressive"),
        (r"\bnationwide\b", "Nationwide"),
        (r"\bliberty\s+mutual\b", "Liberty Mutual"),
        (r"\bchubb\b", "Chubb"),
        (r"\ballied\s+trust\b", "Allied Trust"),
    ]
    joined_lower = " ".join(lines).lower()
    for pattern, normalized in carrier_patterns:
        if re.search(pattern, joined_lower, re.I):
            return normalized
    return None


def _extract_policy_number_from_lines(lines):
    text = "\n".join(lines)
    noise_suffix = re.compile(
        r"(?i)(24\s*hour|claim\s*report|reporting|agent|insured|effective|expiration|policy\s*period).*"
    )

    # Inline labeled pattern: "Policy number: 123456789" / "Policy No: ABC12345"
    for m in re.finditer(
        r"policy\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\s]{4,30})",
        text,
        re.I,
    ):
        cand = re.sub(r"\s+", " ", m.group(1)).strip()
        cand = noise_suffix.sub("", cand).strip()
        cand = re.split(
            r"\s+(?:policy\s*(?:description|type|period|number|info|information)|"
            r"effective|expiration|insured|loan|agent|premium|deductible)\b",
            cand,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .,:;-")
        compact = re.sub(r"[^A-Z0-9\-]", "", cand.upper())
        if len(compact) >= 6 and re.search(r"\d{4,}", compact):
            # OCR bleed fix: strip trailing noise ONLY when it's clearly OCR merge
            # Do NOT strip legitimate policy suffixes like "BP", "T", "F"
            bleed = re.match(r"^(\d{6,16})([-]?[A-Z]{3,}.*)$", compact)
            if bleed:
                suffix = bleed.group(2).lstrip("-")
                noise_words = ("HOUR", "CLAIM", "REPORT", "AGENT", "INSURED",
                               "EFFECTIVE", "POLICY", "PREMIUM", "STANDARD")
                if any(suffix.startswith(nw) for nw in noise_words):
                    result = bleed.group(1)
                    # Also strip trailing digits that came from column merge
                    # E.g., "12345678924" where "24" is from "24-HOUR"
                    for trail in ("24", "800", "12"):
                        if result.endswith(trail) and len(result) - len(trail) >= 6:
                            result = result[:-len(trail)]
                            break
                    return result
            return compact

    # OCR variant: "Policy Number ; 2004939477" etc.
    for m in re.finditer(
        r"policy\s*(?:number|no\.?|#)\s*[\:\-\.;]?\s*([A-Z0-9][A-Z0-9\-\s]{4,40})",
        text,
        re.I,
    ):
        cand = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;-")
        cand = re.split(
            r"\s+(?:effective|expiration|insured|loan|agent|premium|deductible)\b",
            cand,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .,:;-")
        compact = re.sub(r"[^A-Z0-9\-]", "", cand.upper())
        if len(compact) >= 6 and re.search(r"\d{4,}", compact):
            return compact

    # Header/value split pattern:
    #   "Policy number"  (line N)
    #   "123456789"      (line N+1..N+5)
    for idx, line in enumerate(lines):
        if re.search(r"(?i)^policy\s*(?:number|no\.?|#)\s*:?\s*$", str(line).strip()):
            for off in range(1, 6):
                if idx + off >= len(lines):
                    break
                cand = str(lines[idx + off]).strip()
                if not cand:
                    continue
                if re.search(r"(?i)^(policy|loan|insured|agent|premium|deductible|page)\b", cand):
                    continue
                token = cand.split()[0]
                compact = re.sub(r"[^A-Z0-9]", "", token.upper())
                if len(compact) >= 6 and re.search(r"\d{4,}", compact):
                    bleed = re.match(r"^(\d{6,16})([-]?[A-Z]{3,}.*)$", compact)
                    if bleed:
                        suffix = bleed.group(2).lstrip("-")
                        noise_words = ("HOUR", "CLAIM", "REPORT", "AGENT", "INSURED",
                                       "EFFECTIVE", "POLICY", "PREMIUM", "STANDARD")
                        if any(suffix.startswith(nw) for nw in noise_words):
                            result = bleed.group(1)
                            for trail in ("24", "800", "12"):
                                if result.endswith(trail) and len(result) - len(trail) >= 6:
                                    result = result[:-len(trail)]
                                    break
                            return result
                    return compact
    return None


def _extract_loan_number_from_lines(lines):
    text = "\n".join(lines)

    # Prefer inline labeled values, but reject column headers like "Type".
    for m in re.finditer(
        r"loan\s*(?:number|no\.?|#)\s*[\:\-\.;]?\s*([A-Z0-9\-]{3,})",
        text,
        re.I,
    ):
        cand = m.group(1).strip()
        if cand.lower() in {"type", "number", "loan", "acct", "account", "id"}:
            continue
        digits = re.sub(r"\D", "", cand)
        if 7 <= len(digits) <= 16:
            return digits

    # Fallback: value on following line within a short lookahead window.
    for idx, line in enumerate(lines):
        if re.search(r"loan\s*(?:number|no\.?|#)\s*[:\-]?\s*$", line, re.I):
            for off in range(1, 5):
                if idx + off >= len(lines):
                    break
                cand = str(lines[idx + off]).strip()
                if not cand:
                    continue
                if re.search(r"(?i)^(type|number|loan|account|acct)\b", cand):
                    continue
                digits = re.sub(r"\D", "", cand)
                if 7 <= len(digits) <= 16:
                    return digits
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

    # Label form with punctuation/OCR noise: "Total Premium ; $500"
    text = "\n".join(lines)
    m = re.search(
        r"(?im)\btotal(?:\s+residence)?\s+premium\b\s*[\:\-\.;]?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)",
        text,
    )
    if m:
        return f"${m.group(1)}"
    return None


def _extract_date_after_label(text: str, label_pattern: str):
    m = re.search(
        rf"(?im)\b{label_pattern}\b\s*[\:\-\.;]?\s*([0-1]?\d[\/\-][0-3]?\d[\/\-](?:19|20)\d{{2}}|[A-Za-z]+\s+\d{{1,2}},\s+\d{{4}})",
        text,
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_effective_date_from_lines(lines):
    text = "\n".join(lines)
    direct = _extract_date_after_label(text, r"(?:policy\s+)?effective\s+date")
    if direct:
        return direct
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
    direct = _extract_date_after_label(text, r"(?:policy\s+)?expiration\s+date")
    if direct:
        return direct
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


def _extract_mailing_address_from_lines(lines):
    text = "\n".join(lines)

    # Same-line labeled address.
    m = re.search(r"(?im)\bmailing\s+address\b\s*[\:\-\.;]?\s*([^\n]+)", text)
    if m:
        cand = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;-")
        if re.search(r"\d{5}(?:-\d{4})?$", cand):
            return cand
        if len(cand) >= 10:
            return cand

    # Next-line fallback after a standalone label.
    for idx, line in enumerate(lines):
        if re.search(r"(?i)^\s*mailing\s+address\s*[\:\-\.;]?\s*$", str(line).strip()):
            parts = []
            for off in range(1, 4):
                if idx + off >= len(lines):
                    break
                cand = str(lines[idx + off]).strip()
                if not cand:
                    if parts:
                        break
                    continue
                if re.search(r"(?i)^(policy|loan|effective|expiration|carrier|premium|named|insured)\b", cand):
                    break
                parts.append(cand)
                if re.search(r"\d{5}(?:-\d{4})?$", cand):
                    break
            if parts:
                return re.sub(r"\s+", " ", ", ".join(parts)).strip(" ,")
    return None


def _extract_insured_name_from_lines(lines):
    text = "\n".join(lines)

    def _looks_like_person_name(v: str):
        s = re.sub(r"\s+", " ", (v or "")).strip(" .,:;-")
        if not s:
            return False
        if re.search(r"\d", s):
            return False
        bad_kw = (
            "insurance", "company", "exchange", "bank", "mortgage",
            "policy", "address", "mailing", "premium", "effective", "expiration",
        )
        if any(k in s.lower() for k in bad_kw):
            return False
        parts = [p for p in re.split(r"\s+", s) if p]
        return 2 <= len(parts) <= 6

    def _clean_candidate(raw: str):
        cand = re.sub(r"\s+", " ", (raw or "")).strip(" .,:;-")
        cand = re.split(
            r"(?i)\b(mailing\s+address|property\s+address|loan\s+number|policy\s+number|effective\s+date|expiration\s+date|total\s+premium)\b",
            cand,
            maxsplit=1,
        )[0].strip(" .,:;-")
        if not cand:
            return None
        # Names should not look like addresses or date/amount lines.
        if re.search(r"\d{1,6}\s+\w+", cand):
            return None
        if re.search(r"\$|\d{1,2}[\/\-]\d{1,2}[\/\-](?:19|20)\d{2}", cand):
            return None
        if len(cand) < 3:
            return None
        return cand

    # Same-line labels.
    for m in re.finditer(
        r"(?im)\b(?:named\s+insured|insured\s+name|name\s+of\s+insured)\b\s*[\:\-\.;]?\s*([^\n]+)",
        text,
    ):
        cand = _clean_candidate(m.group(1))
        if cand:
            return cand

    # "Named insured and mailing address" block: name often starts on next line.
    for idx, line in enumerate(lines):
        if re.search(r"(?i)named\s+insured(?:\s+and\s+mailing\s+address)?", str(line)):
            for off in range(1, 4):
                if idx + off >= len(lines):
                    break
                cand = _clean_candidate(str(lines[idx + off]).strip())
                if cand:
                    names = [cand]
                    for off2 in range(off + 1, min(off + 4, 6)):
                        if idx + off2 >= len(lines):
                            break
                        nxt_raw = str(lines[idx + off2]).strip()
                        if not nxt_raw:
                            continue
                        if re.search(r"\d{1,6}\s+\w+", nxt_raw) or re.search(r"\d{5}(?:-\d{4})?$", nxt_raw):
                            break
                        nxt = _clean_candidate(nxt_raw)
                        if nxt and _looks_like_person_name(nxt):
                            if nxt.lower() not in {n.lower() for n in names}:
                                names.append(nxt)
                            continue
                        break
                    if len(names) >= 2:
                        return " & ".join(names[:2])
                    return names[0]

    # Generic "Insured:" label fallback.
    for idx, line in enumerate(lines):
        if re.search(r"(?i)^\s*insured\s*[\:\-\.;]?\s*$", str(line).strip()):
            for off in range(1, 3):
                if idx + off >= len(lines):
                    break
                cand = _clean_candidate(str(lines[idx + off]).strip())
                if cand:
                    return cand

    return None


def _extract_cancellation_date_from_lines(lines):
    """Extract cancellation date from OCR lines."""
    text = "\n".join(lines)

    # Pattern 1: "POLICY CANCELLATION DATE IS : 09/04/2020"
    patterns = [
        r"(?i)policy\s+cancellation\s+date\s+is\s*:\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)cancellation\s+(?:effective\s+)?date\s*(?:is)?\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)(?:cancel(?:led|lation)|termination)\s+(?:effective\s+)?(?:on|date)?\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)(?:cancel(?:led)?|terminated)\s+(?:.*?(?:standard|local)\s+time\s+)?on\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)non-?renewal\s+(?:effective\s+)?date\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)

    # Fallback: line containing "cancellation" near a date
    for line in lines:
        ll = line.lower()
        if any(w in ll for w in ("cancellation", "cancelled", "canceled", "cancel date", "termination")):
            dates = re.findall(r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b', line)
            if dates:
                return dates[0]

    return None


def _extract_cancellation_reason_from_lines(lines):
    """Extract cancellation reason from OCR lines."""
    text = "\n".join(lines)

    # Pattern 1: "reason for cancellation: ..."
    m = re.search(
        r"(?i)reason\s+(?:for\s+)?(?:cancellation|termination|non-?renewal)\s*[:\-]?\s*(.{4,80})",
        text,
    )
    if m:
        return m.group(1).strip().rstrip(".,;:")

    # Pattern 2: "cancellation reason: ..."
    m = re.search(r"(?i)cancel(?:lation)?\s+reason\s*[:\-]?\s*(.{4,80})", text)
    if m:
        return m.group(1).strip().rstrip(".,;:")

    # Pattern 3: Infer from "premium payment has not been received"
    for line in lines:
        ll = line.lower()
        if "premium" in ll and ("not been received" in ll or "non-payment" in ll or "nonpayment" in ll):
            return "Non-payment of premium"
        if "underwriting" in ll and ("reason" in ll or "cancel" in ll):
            return "Underwriting reasons"

    return None


def _augment_insured_with_secondary(existing_value, lines):
    base = str(existing_value or "").strip()
    if not base:
        return None
    text = "\n".join(lines)

    def _is_name_line(raw: str):
        s = re.sub(r"\s+", " ", (raw or "")).strip(" .,:;-")
        if not s:
            return False
        if re.search(r"\d", s):
            return False
        if any(k in s.lower() for k in (
            "policy", "effective", "expiration", "loan", "mailing",
            "address", "premium", "carrier", "insurance", "mortgage",
        )):
            return False
        return 2 <= len(s.split()) <= 6

    # If already contains 2 names, leave as-is.
    if re.search(r"\s(?:and|&|/)\s", base, re.I):
        return base

    for idx, line in enumerate(lines):
        if not re.search(r"(?i)named\s+insured(?:\s+and\s+mailing\s+address)?|insured\s+name", str(line)):
            continue
        found_primary = False
        for off in range(1, 6):
            if idx + off >= len(lines):
                break
            cand = str(lines[idx + off]).strip()
            if not cand:
                continue
            if re.search(r"\d{1,6}\s+\w+|\d{5}(?:-\d{4})?$", cand):
                break
            if not _is_name_line(cand):
                continue
            if base.lower() in cand.lower() or cand.lower() in base.lower():
                found_primary = True
                continue
            if found_primary:
                return f"{base} & {cand}"

    # Inline format: "Named insured: A and B"
    m = re.search(
        r"(?im)\b(?:named\s+insured|insured\s+name)\b\s*[:\-]?\s*([^\n]+)",
        text,
    )
    if m:
        rhs = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;-")
        # Reject label fragments like "AND ADDRESS", "AND MAILING ADDRESS"
        rhs_lower = rhs.lower()
        is_label = any(frag in rhs_lower for frag in (
            "address", "mailing", "location", "policy", "premium",
            "coverage", "effective", "expiration", "information",
        ))
        if not is_label and re.search(r"\b(and|&|/)\b", rhs, re.I):
            alpha_words = [w for w in rhs.split() if w.isalpha() and len(w) > 1]
            if len(alpha_words) >= 3:
                return rhs
    return base


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
    put_if_missing("policy_number", _extract_policy_number_from_lines(all_lines))
    put_if_missing("insured_name", _extract_insured_name_from_lines(all_lines))
    put_if_missing("loan_number", _extract_loan_number_from_lines(all_lines))
    put_if_missing("total_premium", _extract_total_premium_from_lines(all_lines))
    put_if_missing("effective_date", _extract_effective_date_from_lines(all_lines))
    put_if_missing("expiration_date", _extract_expiration_date_from_lines(all_lines))
    put_if_missing("property_address", _extract_property_address_from_lines(all_lines))
    put_if_missing("mailing_address", _extract_mailing_address_from_lines(all_lines))
    put_if_missing("cancellation_date", _extract_cancellation_date_from_lines(all_lines))
    put_if_missing("cancellation_reason", _extract_cancellation_reason_from_lines(all_lines))

    # Insured name may already exist with only primary person; enrich with
    # co-insured when present in nearby insured block lines.
    if "insured_name" in expected_fields and isinstance(patched.get("insured_name"), dict):
        existing = patched["insured_name"].get("value")
        enriched = _augment_insured_with_secondary(existing, all_lines)
        if enriched and enriched.strip():
            patched["insured_name"]["value"] = enriched.strip()
    return patched


@app.post("/preview")
async def preview(file: UploadFile = File(...)):
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "")[-1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pages = load_input(tmp_path)

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

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


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
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "")[-1]

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pages = load_input(tmp_path)

        if not pages:
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to read document"},
            )

        start = time.time()

        # Run CPU-heavy pipeline in a threadpool to avoid blocking the event loop
        results = await run_in_threadpool(run_pipeline_batch, pages)

        if not results:
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

        return {
            "document_type": doc_type,
            "policy_type": policy_type,
            "document_type_explanation": get_document_explanation(doc_type),
            "policy_type_explanation": get_policy_explanation(policy_type),
            "confidence": best.get("confidence", 0),
            "page_count": len(pages),
            "fields": clean_fields,
            "pages": page_images,
            "raw_lines": all_lines,
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

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/analyze")
def analyze_get():
    return {"message": "Use POST to upload a file."}