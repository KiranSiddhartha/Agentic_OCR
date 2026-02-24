"""
# Toggle this to True to show filenames, False to hide them
SHOW_FILENAMES = True 
"""
import streamlit as st
import cv2
import sys
import os
import time
import matplotlib.pyplot as plt
import numpy as np
import html
import re
import hashlib
import json
import streamlit.components.v1 as components

# ============================================================
# PATH FIX
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# IMPORTS
# ============================================================
from utils.file_loader import expand_uploaded_files, load_input
from orchestrator import run_pipeline_batch
from agents.insurance_segmentation import (
    segregate_insurance_document,
    get_allowed_fields,
)
from agents.document_classifier import classify_document, get_document_explanation
from agents.policy_classifier import classify_policy, get_policy_explanation

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(layout="wide", page_title="Dynamic OCR")

# ============================================================
# CSS INJECTION (Styles Only)
# ============================================================
st.markdown("""
    <style>
    /* Button Alignment Fix */
    div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding-left: 1rem !important;
    }
    /* Prevent Image Transitions */
    img {
        transition: none !important;
        -webkit-transition: none !important;
    }
    /* Expander Styling */
    .streamlit-expanderHeader {
        background-color: #f0f2f6;
        border-radius: 5px;
        font-weight: 600;
        font-size: 1.1rem;
    }
    [data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# KEEP-ALIVE HEARTBEAT (prevents session timeout on idle)
# ============================================================
components.html(
    """
    <script>
    (function() {
        if (window._stKeepAlive) clearInterval(window._stKeepAlive);
        window._stKeepAlive = setInterval(function() {
            window.parent.document.dispatchEvent(new Event('mousemove'));
        }, 25000);
    })();
    </script>
    """,
    height=0,
    width=0,
)

# ============================================================
# SESSION STATE DEFAULTS
# ============================================================
_DEFAULTS = {
    "uploaded": False,
    "processed": False,
    "files": [],
    "pipeline_results": {},
    "ocr_cache": {},
    "selected_field": None,
    "base_preview_cache": {},
    "highlight_preview_cache": {},
    "fields_hash_cache": {},
    "uploader_key": 0,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".zip")
PREVIEW_MAX_WIDTH = 1000

# ============================================================
# CONFIGURATION
# ============================================================
# Toggle this to True to show filenames, False to hide them
SHOW_FILENAMES = True 

# ============================================================
# PERFORMANCE CACHING (CRITICAL FOR SPEED)
# ============================================================
@st.cache_resource(show_spinner="Loading AI Models...")
def load_vision_agent():
    from agents.vision_agent import VisionAgent
    return VisionAgent(use_layoutxlm=True)

@st.cache_data(show_spinner=False)
def decode_pages(file_bytes, file_type):
    pages = load_input(file_bytes, file_type)
    if not pages:
        return []
    page_data = []
    for p in pages:
        success, buf = cv2.imencode(".png", p)
        if success:
            page_data.append(buf.tobytes())
    return page_data

# ============================================================
# HELPERS
# ============================================================
def reset_to_home():
    current_key = st.session_state.get("uploader_key", 0)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v if not isinstance(_v, (dict, list)) else type(_v)()
    st.session_state["uploader_key"] = current_key + 1

def prettify(name: str) -> str:
    return name.replace("_", " ").title()

def merge_page_results(results: list) -> dict:
    if not results:
        return {
            "fields": {}, "raw_lines": [], "confidence": 0.0,
            "page_count": 0, "document_type": "OTH", "policy_type": "OTH",
        }
    all_lines, fields = [], {}
    for r in results:
        all_lines.extend(r.get("raw_lines", []))
        fields.update(r.get("fields", {}))

    from document_router import classify_doc_type
    from policy_classifier import classify_policy as _cp

    doc_type = classify_doc_type(all_lines)
    policy_type = _cp(all_lines)
    best = max(results, key=lambda r: r.get("confidence", 0.0))

    return {
        "fields": fields, "raw_lines": all_lines,
        "confidence": best.get("confidence", 0.0),
        "page_count": len(results),
        "document_type": doc_type,
        "policy_type": policy_type,
        "approach": best.get("approach"),
    }

def strip_bbox(fields: dict) -> dict:
    clean = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            v = v.copy()
            v.pop("bbox", None)
            v.pop("page", None)
        clean[k] = v
    return clean

def ensure_fields_have_page(fields: dict, default_page: int = 0) -> dict:
    patched = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            v = v.copy()
            if v.get("page") is None:
                v["page"] = default_page
        patched[k] = v
    return patched

def _hash_fields(fields: dict) -> str:
    serializable = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            serializable[k] = {"bbox": v.get("bbox"), "page": v.get("page")}
    return hashlib.md5(json.dumps(serializable, sort_keys=True, default=str).encode()).hexdigest()

# ============================================================
# BBOX SYNTHESIS (REQUIRED FOR HIGHLIGHTING)
# ============================================================
def _normalize_text(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text.strip().lower())

def _tokenize_value(value: str) -> list:
    return [t.lower() for t in re.split(r'[\s,]+', value.strip()) if t]

def _find_value_bbox(value: str, words: list, boxes: list) -> list:
    if not value or not words:
        return None
    value_clean = value.strip()
    if not value_clean:
        return None
    ocr_words = [w.strip() if w else "" for w in words]
    ocr_lower = [w.lower() for w in ocr_words]
    value_lower = value_clean.lower()

    for idx, wl in enumerate(ocr_lower):
        if wl == value_lower and idx < len(boxes) and boxes[idx]:
            return list(boxes[idx])

    if len(value_lower) >= 4:
        for idx, wl in enumerate(ocr_lower):
            if idx < len(boxes) and boxes[idx] and (value_lower in wl or (wl in value_lower and len(wl) >= 4)):
                return list(boxes[idx])
    return None

def synthesize_bboxes_for_page(fields, ocr_data, img_w, img_h, page_idx):
    if not ocr_data:
        return fields
    words, boxes = ocr_data.get("text", []), ocr_data.get("boxes", [])
    if not words or not boxes:
        return fields

    patched = {}
    for fn, fd in fields.items():
        if isinstance(fd, dict):
            fd = fd.copy()
            if fd.get("bbox") is None or fd.get("page") is None:
                val = fd.get("value", "")
                if isinstance(val, str) and val.strip():
                    bbox = _find_value_bbox(val, words, boxes)
                    if bbox:
                        fd["bbox"] = bbox
                        fd["page"] = page_idx
            patched[fn] = fd
        else:
            patched[fn] = fd
    return patched

def bbox_to_pixels(bbox, img_w, img_h):
    x1, y1, x2, y2 = bbox
    if all(0 <= c <= 1 for c in [x1, y1, x2, y2]):
        x1, x2 = int(x1 * img_w), int(x2 * img_w)
        y1, y2 = int(y1 * img_h), int(y2 * img_h)
    elif all(0 <= c <= 1000 for c in [x1, y1, x2, y2]):
        x1, y1 = int((x1 / 1000) * img_w), int((y1 / 1000) * img_h)
        x2, y2 = int((x2 / 1000) * img_w), int((y2 / 1000) * img_h)
    else:
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    return max(0, x1), max(0, y1), min(x2, img_w), min(y2, img_h)

def page_matches(field_page, display_page_0based):
    return True if field_page is None else field_page == display_page_0based

# ============================================================
# IMAGE FORMAT CONVERTERS (PNG bytes <-> RGB array)
# ============================================================
def _rgb_to_png_bytes(rgb_array):
    """Convert an RGB numpy array to PNG bytes for stable caching."""
    if rgb_array is None:
        return None
    bgr = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    success, buf = cv2.imencode(".png", bgr)
    return buf.tobytes() if success else None

def _png_bytes_to_rgb(png_bytes):
    """Decode PNG bytes back to an RGB numpy array for drawing."""
    if png_bytes is None:
        return None
    arr = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)

# ============================================================
# IMAGE PREVIEW BUILDERS (now return PNG bytes, not arrays)
# ============================================================
def build_base_preview_for_page(png_bytes, fields, page_idx_0based):
    img = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if w > PREVIEW_MAX_WIDTH:
        scale = PREVIEW_MAX_WIDTH / w
        img = cv2.resize(img, (PREVIEW_MAX_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    if fields:
        for fn, v in fields.items():
            if not isinstance(v, dict):
                continue
            bbox, fp = v.get("bbox"), v.get("page")
            if not bbox or not page_matches(fp, page_idx_0based):
                continue
            x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)
            if x2 - x1 < 2 or y2 - y1 < 2:
                continue
            dark_green = (0, 100, 0)
            cv2.rectangle(rgb, (x1, y1), (x2, y2), dark_green, 1)
    return _rgb_to_png_bytes(rgb)

def get_or_build_base_preview(file_key, page_idx_0based, png_bytes, fields, fields_hash):
    cache = st.session_state.get("base_preview_cache", {})
    hash_cache = st.session_state.get("fields_hash_cache", {})
    cache_key = f"{file_key}_p{page_idx_0based}"

    if cache_key in cache and hash_cache.get(cache_key) == fields_hash:
        return cache[cache_key]

    base = build_base_preview_for_page(png_bytes, fields, page_idx_0based)
    cache[cache_key] = base
    hash_cache[cache_key] = fields_hash
    st.session_state["base_preview_cache"] = cache
    st.session_state["fields_hash_cache"] = hash_cache
    st.session_state["highlight_preview_cache"] = {}
    return base

def get_cached_highlight_image(file_key, base_png_bytes, fields, selected_field, page_idx_0based):
    if not selected_field:
        return base_png_bytes
    cache_key = f"{file_key}_{page_idx_0based}_{selected_field}"
    h_cache = st.session_state.get("highlight_preview_cache", {})
    if cache_key in h_cache:
        return h_cache[cache_key]

    v = fields.get(selected_field)
    if not isinstance(v, dict):
        return base_png_bytes
    bbox, fp = v.get("bbox"), v.get("page")
    if not bbox or not page_matches(fp, page_idx_0based):
        return base_png_bytes

    rgb = _png_bytes_to_rgb(base_png_bytes)
    if rgb is None:
        return base_png_bytes

    img = rgb.copy()
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return base_png_bytes

    cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 3)
    label = f">> {prettify(selected_field)} <<"
    font, f_scale = cv2.FONT_HERSHEY_SIMPLEX, 0.6
    (tw, th_), _ = cv2.getTextSize(label, font, f_scale, 2)
    ly = max(th_ + 6, y1 - 6)
    cv2.rectangle(img, (x1, ly - th_ - 6), (x1 + tw + 8, ly + 2), (255, 0, 0), -1)
    cv2.putText(img, label, (x1 + 4, ly - 2), font, f_scale, (255, 255, 255), 2)

    result_bytes = _rgb_to_png_bytes(img)
    h_cache[cache_key] = result_bytes
    st.session_state["highlight_preview_cache"] = h_cache
    return result_bytes

# ============================================================
# COPY HELPERS (FIXED)
# ============================================================
def format_all_fields_as_text(fields, allowed=None):
    lines = []
    for k, v in fields.items():
        if allowed and k not in allowed:
            continue
        val = v.get("value") if isinstance(v, dict) else v
        if val:
            lines.append(f"{prettify(k)}: {val}")
    return "\n".join(lines)

def format_all_fields_as_json(fields, allowed=None):
    clean = {}
    for k, v in fields.items():
        if allowed and k not in allowed:
            continue
        val = v.get("value") if isinstance(v, dict) else v
        if val:
            clean[prettify(k)] = str(val)
    return json.dumps(clean, indent=2, ensure_ascii=False)

def copy_button_js(text_to_copy, button_label="📋 Copy to Clipboard", key="copy_btn"):
    escaped = (
        html.escape(text_to_copy)
        .replace("`", "\\`")
        .replace("\n", "\\n")
        .replace("'", "\\'")
    )
    component_html = f"""
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
    </style>
    <button onclick="
        navigator.clipboard.writeText(`{escaped}`).then(
            () => this.innerText = '✅ Copied!',
            () => this.innerText = '❌ Failed'
        );
        setTimeout(() => this.innerText = '{button_label}', 2000);
    " style="
        background: #262730;
        color: #fafafa;
        border: 1px solid #4a4a5a;
        padding: 0px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        width: 100%;
        height: 38px;
        line-height: 38px;
        white-space: nowrap;
        text-align: center;
        display: flex;
        justify-content: center;
        align-items: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        transition: background 0.2s;
    " onmouseover="this.style.background='#3a3a4a'"
      onmouseout="this.style.background='#262730'"
    >{button_label}</button>
    """
    components.html(component_html, height=40)

# ============================================================
# UI COMPONENTS
# ============================================================
def on_field_click(field_name):
    curr = st.session_state.get("selected_field")
    st.session_state["selected_field"] = None if curr == field_name else field_name

def clear_selection():
    st.session_state["selected_field"] = None

def field_has_bbox(field_name, fields_with_bbox):
    orig = fields_with_bbox.get(field_name, {})
    return isinstance(orig, dict) and orig.get("bbox") and len(orig.get("bbox", [])) == 4

def field_page_number(field_name, fields_with_bbox):
    orig = fields_with_bbox.get(field_name, {})
    return orig.get("page", -1) if isinstance(orig, dict) else -1

def render_clickable_fields(seg, fields_with_bbox, file_name, num_pages):
    fields = seg.get("fields", {})
    doc_type = seg.get("document_type", "OTH")
    policy_type = seg.get("policy_type", "OTH")
    allowed = get_allowed_fields(doc_type, policy_type)
    selected = st.session_state.get("selected_field")

    # 1. Determine visible fields first
    visible_fields = {
        k: v for k, v in fields.items()
        if (not allowed or k in allowed) and (v.get("value") if isinstance(v, dict) else v)
    }

    # 2. Check if anything is extracted
    if not visible_fields:
        st.warning("No fields are extracted")
        return

    total_visible = len(visible_fields)
    total_bbox = sum(1 for k in visible_fields if field_has_bbox(k, fields_with_bbox))

    col_info, col_copy = st.columns([4, 1])

    with col_info:
        st.markdown(
            f'<div style="font-size:0.82em; color:#888; margin-bottom:4px; '
            f'padding:8px; background:rgba(255,255,255,0.02); border-radius:6px;">'
            f'👆 <b>Click any field</b> to highlight on document<br>'
            f'<span style="color:#4caf50;">●</span> Located ({total_bbox}/{total_visible}) '
            f'<span style="color:#ff9800;">●</span> Not located '
            f'({total_visible - total_bbox}/{total_visible})</div>',
            unsafe_allow_html=True,
        )

    with col_copy:
        copy_text = format_all_fields_as_text(fields, allowed)
        copy_button_js(copy_text, "📋 Copy List", key=f"cptext_{file_name}")

    st.markdown("---")

    if selected:
        st.button(
            "✖ Clear selection",
            key=f"clr_{file_name}",
            on_click=clear_selection,
        )

    for k, v in fields.items():
        if allowed and k not in allowed:
            continue
        val = v.get("value") if isinstance(v, dict) else v
        if not val:
            continue

        has_bbox = field_has_bbox(k, fields_with_bbox)
        is_active = k == selected
        icon = (
            "🔴" if is_active and has_bbox
            else ("🟠" if is_active
                  else ("🟢" if has_bbox else "🟡"))
        )

        display_val = str(val)
        truncated = display_val[:45] + "…" if len(display_val) > 45 else display_val

        st.button(
            f"{icon} {prettify(k)}: {truncated}",
            key=f"fb_{file_name}_{k}",
            use_container_width=True,
            on_click=on_field_click,
            args=(k,),
        )

def render_clickable_summary(seg, fields_with_bbox, file_name, num_pages):
    fields = seg.get("fields", {})
    doc_type = seg.get("document_type", "OTH")
    policy_type = seg.get("policy_type", "OTH")
    required = get_allowed_fields(doc_type, policy_type)
    if not required:
        required = set(fields.keys())
    selected = st.session_state.get("selected_field")

    perfect, partial, failed = [], [], []
    for fn in sorted(required):
        val = fields.get(fn, {}).get("value")
        if not val:
            failed.append(fn)
        elif not str(val).strip():
            partial.append(fn)
        else:
            perfect.append(fn)

    st.markdown("### 📊 Extraction Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Perfect", len(perfect))
    c2.metric("🟡 Partial", len(partial))
    c3.metric("🔴 Failed", len(failed))

    if selected:
        st.button(
            "✖ Clear highlight",
            key=f"clrs_{file_name}",
            on_click=clear_selection,
        )

    l, r = st.columns([1.2, 1])
    with l:
        for cat, items, icon_base in [
            ("p", perfect, "🟢"),
            ("y", partial, "🟡"),
        ]:
            for fn in items:
                has_bbox = field_has_bbox(fn, fields_with_bbox)
                icon = (
                    "🔴" if fn == selected and has_bbox
                    else ("🟠" if fn == selected
                          else (icon_base if has_bbox else "🟡"))
                )
                badge = " " if has_bbox else " ⚠️"
                st.button(
                    f"{icon} {prettify(fn)}{badge}",
                    key=f"s{cat}_{file_name}_{fn}",
                    use_container_width=True,
                    on_click=on_field_click,
                    args=(fn,),
                )
        for fn in failed:
            if field_has_bbox(fn, fields_with_bbox):
                st.button(
                    f"🔴 {prettify(fn)} ",
                    key=f"sf_{file_name}_{fn}",
                    use_container_width=True,
                    on_click=on_field_click,
                    args=(fn,),
                )
            else:
                st.markdown(f"🔴 {prettify(fn)} — not extracted")
    with r:
        if (len(perfect) + len(partial) + len(failed)) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            fig.patch.set_alpha(0)
            ax.pie(
                [len(perfect), len(partial), len(failed)],
                labels=["Perfect", "Partial", "Failed"],
                colors=["#4caf50", "#ff9800", "#f44336"],
                autopct="%1.0f%%",
                startangle=90,
            )
            ax.axis("equal")
            st.pyplot(fig)

def build_field_limitation_reason(document_type, policy_type):
    allowed = sorted(get_allowed_fields(document_type, policy_type))
    list_str = " • ".join(prettify(f) for f in allowed)
    return html.escape(
        f"Document Type: {document_type}\nPolicy Type: {policy_type}\nAllowed ({len(allowed)}):\n{list_str}"
    ).replace("\n", "&#10;")

# ============================================================
# MAIN LAYOUT
# ============================================================
h1, h2 = st.columns([8, 1])
with h1:
    st.markdown("## Dynamic OCR – Intelligent Cascading Hybrid")
with h2:
    if st.session_state.get("uploaded") and st.button("⬅ Back"):
        reset_to_home()
        st.rerun()
st.markdown("---")

# UPLOAD
if not st.session_state.get("uploaded", False):
    ukey = st.session_state.get("uploader_key", 0)
    uploaded = st.file_uploader(
        "Upload documents",
        list(ALLOWED_EXT),
        accept_multiple_files=True,
        key=f"uploader_{ukey}",
    )
    if uploaded:
        st.session_state.files = expand_uploaded_files(uploaded)
        st.session_state.uploaded = True
        st.rerun()
    st.stop()

# ============================================================
# EXECUTION
# ============================================================
for i, f in enumerate(st.session_state.files):
    file_key = f"result_{f.name}"

    if i > 0:
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

    label_text = f"📁 **Document {i + 1}**"
    if SHOW_FILENAMES:
        label_text += f" — {f.name}"
    
    with st.expander(label_text, expanded=True):

        # 1. IMMEDIATE DECODE
        page_png_list = decode_pages(f.getvalue(), f.type)
        if not page_png_list:
            st.error("Could not decode file.")
            continue
        num_pages = len(page_png_list)

        # 2. CREATE LAYOUT COLUMNS
        col_img, col_out = st.columns([1, 1], gap="large")

        # 3. RENDER LEFT COLUMN (PREVIEW)
        with col_img:
            st.markdown("### 📄 Document Preview")

            processed_data = st.session_state.get("pipeline_results", {}).get(file_key)
            fields_with_bbox = processed_data["result"]["fields"] if processed_data else {}
            f_hash = _hash_fields(fields_with_bbox)

            selected_field = st.session_state.get("selected_field")

            if selected_field:
                if field_has_bbox(selected_field, fields_with_bbox):
                    pg = field_page_number(selected_field, fields_with_bbox)
                    pg_label = f" (Page {pg + 1})" if num_pages > 1 else ""
                    st.success(f"🔴 Highlighting: **{prettify(selected_field)}**{pg_label}")
                else:
                    st.warning(f"⚠️ **{prettify(selected_field)}** – position not found")

            for page_idx, png_bytes in enumerate(page_png_list):
                base_png = get_or_build_base_preview(file_key, page_idx, png_bytes, fields_with_bbox, f_hash)

                if (
                    selected_field
                    and field_has_bbox(selected_field, fields_with_bbox)
                    and page_matches(field_page_number(selected_field, fields_with_bbox), page_idx)
                ):
                    display_png = get_cached_highlight_image(
                        file_key, base_png, fields_with_bbox, selected_field, page_idx
                    )
                else:
                    display_png = base_png

                if display_png:
                    st.image(display_png, caption=f"Page {page_idx + 1}", use_container_width=True)
                else:
                    st.error(f"Could not render page {page_idx + 1}")

                if page_idx < num_pages - 1:
                    st.markdown("---")

        # 4. RENDER RIGHT COLUMN (RESULTS)
        with col_out:
            result_container = st.empty()

            if processed_data:
                result = processed_data["result"]
                seg = processed_data["seg"]
                elapsed = processed_data["elapsed"]

                m1, m2, m3 = st.columns(3)
                m1.metric("📄 Pages", result["page_count"])
                m2.metric("🎯 Accuracy (%)", f"{result['confidence'] * 100:.2f}")
                m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

                c1, c2 = st.columns([1, 1])
                doc_expl = html.escape(get_document_explanation(seg["document_type"]))
                pol_expl = html.escape(get_policy_explanation(seg["policy_type"]))

                with c1:
                    st.markdown(
                        f'**📄 Document Type:** `{seg["document_type"]}` '
                        f'<span title="{doc_expl}">ℹ️</span>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        f'**🔐 Policy Type:** `{seg["policy_type"]}` '
                        f'<span title="{pol_expl}">ℹ️</span>',
                        unsafe_allow_html=True,
                    )

                _allowed = get_allowed_fields(seg["document_type"], seg["policy_type"])
                with st.expander(
                    f"Why only {len(_allowed) if _allowed else len(seg['fields'])} fields? ℹ️"
                ):
                    st.markdown(
                        build_field_limitation_reason(seg["document_type"], seg["policy_type"]),
                        unsafe_allow_html=True,
                    )

                # --- Check if we have valid extracted fields to determine tabs ---
                raw_fields = seg.get("fields", {})
                has_extracted_data = False
                for k, v in raw_fields.items():
                    val = v.get("value") if isinstance(v, dict) else v
                    if val and (not _allowed or k in _allowed):
                        has_extracted_data = True
                        break

                # Create tabs based on data availability
                if has_extracted_data:
                    tab1, tab2, tab3, tab4 = st.tabs(
                        ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text", "🔧 JSON Output"]
                    )
                else:
                    tab1, tab2, tab3 = st.tabs(
                        ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
                    )
                    tab4 = None

                with tab1:
                    render_clickable_fields(seg, fields_with_bbox, f.name, num_pages)

                with tab2:
                    render_clickable_summary(seg, fields_with_bbox, f.name, num_pages)

                with tab3:
                    st.text_area(
                        "OCR Output",
                        "\n".join(result["raw_lines"]),
                        height=500,
                        key=f"ocr_{f.name}",
                    )

                if tab4:
                    with tab4:
                        fields_for_json = seg.get("fields", {})
                        allowed_for_json = get_allowed_fields(
                            seg.get("document_type", "OTH"),
                            seg.get("policy_type", "OTH"),
                        )
                        json_output = format_all_fields_as_json(fields_for_json, allowed_for_json)
                        
                        c_fill, c_btn = st.columns([4, 1])
                        with c_btn:
                            copy_button_js(json_output, "📋 Copy JSON", key=f"cpjson_tab_{f.name}")
                            
                        st.code(json_output, language="json")

            else:
                with result_container.container():
                    with st.spinner("⏳ Analyzing document (OCR + Extraction)..."):
                        start = time.time()

                        pages = []
                        for pb in page_png_list:
                            arr = cv2.imdecode(np.frombuffer(pb, np.uint8), cv2.IMREAD_COLOR)
                            if arr is not None:
                                pages.append(arr)

                        vision = load_vision_agent()
                        ocr_data_by_page = {}

                        for page_idx, img in enumerate(pages):
                            try:
                                ocr = vision.ocr_engine.run_with_boxes(img)
                                ocr_data_by_page[f"{f.name}_page_{page_idx}"] = ocr
                            except Exception as ocr_err:
                                print(f"[APP] OCR pre-scan failed page {page_idx}: {ocr_err}")

                        results = run_pipeline_batch(pages)

                        result = merge_page_results(results)
                        enriched = result["fields"]

                        for pi, img in enumerate(pages):
                            pk = f"{f.name}_page_{pi}"
                            ocr = ocr_data_by_page.get(pk)
                            if ocr:
                                hh, ww = img.shape[:2]
                                enriched = synthesize_bboxes_for_page(enriched, ocr, ww, hh, pi)

                        enriched = ensure_fields_have_page(enriched, default_page=0)
                        result["fields"] = enriched

                        seg = {
                            "fields": strip_bbox(enriched),
                            "document_type": result.get("document_type", "OTH"),
                            "policy_type": result.get("policy_type", "OTH"),
                        }

                        if "pipeline_results" not in st.session_state:
                            st.session_state["pipeline_results"] = {}
                        st.session_state["pipeline_results"][file_key] = {
                            "result": result,
                            "seg": seg,
                            "elapsed": time.time() - start,
                        }

                        st.rerun()

st.caption("")