# # app.py - INTELLIGENT CASCADING HYBRID VISUALIZATION
# # Clean Extraction Summary (NO stage/source/conf in output)

# import streamlit as st
# import cv2
# import sys
# import os
# import time
# import matplotlib.pyplot as plt
# import re

# # ============================================================
# # PATH FIX
# # ============================================================
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# # ============================================================
# # IMPORTS
# # ============================================================
# from utils.file_loader import expand_uploaded_files, load_input
# from orchestrator import run_pipeline_batch, run_pipeline

# # Import classifiers (UNCHANGED)
# try:
#     from agents.insurance_segmentation import segregate_insurance_document
#     from agents.document_classifier import classify_document, get_document_explanation
#     from agents.policy_classifier import classify_policy, get_policy_explanation
# except ImportError:
#     def segregate_insurance_document(lines):
#         return {"document_type": "OTH", "policy_type": "UNK", "fields": {}, "field_errors": []}
#     def classify_document(lines): return "OTH"
#     def classify_policy(lines): return "UNK"
#     def get_document_explanation(doc_type): return ""
#     def get_policy_explanation(policy_type): return ""

# # ============================================================
# # PAGE CONFIG
# # ============================================================
# st.set_page_config(layout="wide", page_title="Dynamic OCR")

# # ============================================================
# # SESSION STATE
# # ============================================================
# st.session_state.setdefault("uploaded", False)
# st.session_state.setdefault("files", [])

# # ============================================================
# # CONSTANTS
# # ============================================================
# ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".zip")

# # ============================================================
# # HELPERS
# # ============================================================
# def prettify(name: str) -> str:
#     return name.replace("_", " ").title()


# def merge_page_results(results: list) -> dict:
#     if not results:
#         return {}

#     all_raw_lines = []
#     combined_fields = {}
#     best = max(results, key=lambda x: x.get("confidence", 0.0))

#     for r in results:
#         all_raw_lines.extend(r.get("raw_lines", []))
#         combined_fields.update(r.get("fields", {}))

#     return {
#         "fields": combined_fields,
#         "raw_lines": all_raw_lines,
#         "confidence": best.get("confidence", 0.0),
#         "ocr_confidence": best.get("ocr_confidence", 0.0),
#         "page_count": len(results),
#     }


# def render_extracted_text(seg_result: dict) -> str:
#     fields = seg_result.get("fields", {})
#     if not fields:
#         return "No fields extracted"

#     out = []
#     for k, v in fields.items():
#         value = v.get("value") if isinstance(v, dict) else v
#         if value:
#             out.append(f"{prettify(k)}: {value}")
#     return "\n".join(out)

# # ============================================================
# # FIELD VALIDATION + SUMMARY
# # ============================================================
# def is_field_value_valid(field: str, value: str) -> bool:
#     if not value:
#         return False
#     v = value.lower().strip()
#     if field == "insured_name":
#         return not any(x in v for x in ["policy", "insurance"]) and not any(c.isdigit() for c in value)
#     if field in ("effective_date", "expiration_date"):
#         return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", v))
#     if field in ("policy_number", "loan_number"):
#         return sum(c.isdigit() for c in value) >= 6
#     return True


# def classify_extracted_fields(seg_result: dict):
#     from agents.insurance_segmentation import FIELD_RULES
#     fields = seg_result.get("fields", {})
#     doc_type = seg_result.get("document_type", "OTH")
#     required = FIELD_RULES.get(doc_type, [])

#     perfect, partial, failed = [], [], []
#     for f in required:
#         data = fields.get(f)
#         value = data.get("value") if isinstance(data, dict) else data
#         if not value:
#             failed.append(f)
#         elif not is_field_value_valid(f, value):
#             partial.append(f)
#         else:
#             perfect.append(f)
#     return perfect, partial, failed


# def draw_extraction_summary_tab(seg_result: dict):
#     perfect, partial, failed = classify_extracted_fields(seg_result)

#     st.markdown("### 📊 Extraction Summary")

#     c1, c2, c3 = st.columns(3)
#     c1.metric("Perfect", len(perfect))
#     c2.metric("Partial", len(partial))
#     c3.metric("Failed", len(failed))

#     total = len(perfect) + len(partial) + len(failed)
#     st.progress((len(perfect) + 0.5 * len(partial)) / total if total else 0)

#     left, right = st.columns([1.2, 1])

#     with left:
#         for f in perfect:
#             st.markdown(f"🟢 {prettify(f)}")
#         for f in partial:
#             st.markdown(f"🟡 {prettify(f)}")
#         for f in failed:
#             st.markdown(f"🔴 {prettify(f)}")

#     with right:
#         if total:
#             fig, ax = plt.subplots(figsize=(4, 4))
#             ax.pie(
#                 [len(perfect), len(partial), len(failed)],
#                 labels=["Perfect", "Partial", "Failed"],
#                 autopct="%1.0f%%",
#                 startangle=90,
#                 colors=['#00ff00', '#ffff00', '#ff0000']
#             )
#             ax.axis("equal")
#             st.pyplot(fig)
#         else:
#             st.info("No fields to display")

# # ============================================================
# # HEADER
# # ============================================================
# h1, h2 = st.columns([8, 1])
# with h1:
#     st.markdown("## Dynamic OCR")
# with h2:
#     if st.session_state.uploaded and st.button("⬅ Back"):
#         st.session_state.uploaded = False
#         st.session_state.files = []
#         st.rerun()

# st.markdown("---")

# # ============================================================
# # UPLOAD
# # ============================================================
# if not st.session_state.uploaded:
#     uploaded = st.file_uploader("Upload documents", list(ALLOWED_EXT), accept_multiple_files=True)
#     if uploaded:
#         st.session_state.files = expand_uploaded_files(uploaded)
#         st.session_state.uploaded = True
#         st.rerun()
#     st.stop()

# # ============================================================
# # PROCESS FILES
# # ============================================================
# for f in st.session_state.files:
#     pages = load_input(f.getvalue(), f.type)
#     if not pages:
#         continue

#     col_img, col_out = st.columns([1, 1], gap="large")

#     # -------- PREVIEW --------
#     with col_img:
#         st.markdown("### 📄 Document Preview")

#         image_pages = 0

#         for i, page in enumerate(pages):
#             if page.get("type") == "image":
#                 image_pages += 1

#                 rgb = cv2.cvtColor(page["content"], cv2.COLOR_BGR2RGB)

#                 # KEY IS CRITICAL – prevents Streamlit overwrite
#                 st.image(
#                     rgb,
#                     caption=f"Page {i + 1}",
#                     use_container_width=True
#                 )

#                 st.markdown("---")  # visual separation

#         if image_pages == 0:
#             st.info("📄 PDF contains embedded text only (no raster pages)")

#     # -------- PROCESSING --------
#     with col_out:
#         with st.spinner("Processing document..."):
#             start = time.time()

#             image_pages_data = [p["content"] for p in pages if p.get("type") == "image"]
#             results = run_pipeline_batch(image_pages_data) if image_pages_data else []

#             result = merge_page_results(results)

#             seg = segregate_insurance_document(result.get("raw_lines", []))
#             seg["fields"] = result.get("fields", {})

#             elapsed = time.time() - start

#         # -------- SPEED & ACCURACY (RESTORED) --------
#         pages_cnt = result.get("page_count", 0)
#         speed_per_page = (elapsed / pages_cnt) if pages_cnt else 0
#         accuracy = result.get("confidence", 0.0) * 100

#         m1, m2, m3 = st.columns(3)
#         m1.metric("📄 Pages", pages_cnt)
#         m2.metric("⚡ Speed / Page (s)", f"{speed_per_page:.2f}")
#         m3.metric("🎯 Accuracy (%)", f"{accuracy:.2f}")

#         # -------- DOC / POLICY TYPE --------
#         doc_type = seg.get("document_type", "OTH")
#         policy_type = seg.get("policy_type", "UNK")

#         st.info(f"📄 **Document Type:** {doc_type}")
#         st.info(f"🔒 **Policy Type:** {policy_type}")

#         # -------- TABS --------
#         tab1, tab2, tab3 = st.tabs(
#             ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
#         )

#         with tab1:
#             st.text_area("Extracted Output", render_extracted_text(seg), height=500)

#         with tab2:
#             draw_extraction_summary_tab(seg)

#         with tab3:
#             st.text_area("OCR Output", "\n".join(result.get("raw_lines", [])), height=500)

# st.caption("")

# app.py - INTELLIGENT CASCADING HYBRID VISUALIZATION 

import streamlit as st
import cv2
import sys
import os
import time
import matplotlib.pyplot as plt
import re
import numpy as np

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
from agents.insurance_segmentation import segregate_insurance_document, FIELD_RULES
from agents.document_classifier import classify_document
from agents.policy_classifier import classify_policy

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(layout="wide", page_title="Dynamic OCR")

# ============================================================
# SESSION STATE
# ============================================================
st.session_state.setdefault("uploaded", False)
st.session_state.setdefault("files", [])

ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".zip")

# ============================================================
# HELPERS
# ============================================================
def prettify(name: str) -> str:
    return name.replace("_", " ").title()


def merge_page_results(results: list) -> dict:
    if not results:
        return {
            "fields": {},
            "raw_lines": [],
            "confidence": 0.0,
            "page_count": 0,
            "metadata": {},
        }

    all_lines, fields = [], {}
    best = max(results, key=lambda r: r.get("confidence", 0.0))

    for r in results:
        all_lines.extend(r.get("raw_lines", []))
        fields.update(r.get("fields", {}))

    return {
        "fields": fields,
        "raw_lines": all_lines,
        "confidence": best.get("confidence", 0.0),
        "page_count": len(results),
        "metadata": best.get("metadata", {}),
    }

def merge_fields(current: dict, staged: dict) -> dict:
    """
    Merge two field dictionaries safely.
    Prefers higher-confidence values.
    Handles None values correctly.
    """

    merged = dict(staged)  # start with staged (older)

    for k, c in current.items():
        if c is None:
            continue

        s = merged.get(k)

        # If staged value is missing or None → take current
        if s is None:
            merged[k] = c
            continue

        # If either side is malformed → prefer valid dict
        if not isinstance(c, dict):
            continue
        if not isinstance(s, dict):
            merged[k] = c
            continue

        # Compare confidence safely
        c_conf = c.get("confidence", 0)
        s_conf = s.get("confidence", 0)

        merged[k] = c if c_conf >= s_conf else s

    return merged


# def merge_fields(cascade: dict, seg: dict) -> dict:
#     merged = {}
#     for k in set(cascade) | set(seg):
#         c, s = cascade.get(k), seg.get(k)
#         if c and not s:
#             merged[k] = c
#         elif s and not c:
#             merged[k] = s if isinstance(s, dict) else {"value": s, "confidence": 0.75}
#         else:
#             merged[k] = c if c.get("confidence", 0) >= s.get("confidence", 0) else s
#     return merged


def render_extracted_text(seg: dict) -> str:
    fields = seg.get("fields", {})
    if not fields:
        return "No fields extracted"

    out = []
    for k, v in fields.items():
        val = v.get("value") if isinstance(v, dict) else v
        if val:
            out.append(f"{prettify(k)}: {val}")
    return "\n".join(out)

# ============================================================
# FIELD VALIDATION (RESTORED)
# ============================================================
def is_field_value_valid(field: str, value: str) -> bool:
    if not value:
        return False

    v = value.lower().strip()

    if field == "insured_name":
        if any(x in v for x in ["policy", "insurance"]):
            return False
        if any(c.isdigit() for c in value):
            return False
        return True

    if field in ("effective_date", "expiration_date"):
        return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", v))

    if field in ("policy_number", "loan_number"):
        return sum(c.isdigit() for c in value) >= 6

    return True


def classify_extracted_fields(seg_result: dict):
    fields = seg_result.get("fields", {})
    doc_type = seg_result.get("document_type", "OTH")
    required = FIELD_RULES.get(doc_type, [])

    perfect, partial, failed = [], [], []

    for f in required:
        data = fields.get(f)
        value = data.get("value") if isinstance(data, dict) else data

        if not value:
            failed.append(f)
        elif not is_field_value_valid(f, value):
            partial.append(f)
        else:
            perfect.append(f)

    return perfect, partial, failed


def draw_extraction_summary_tab(seg_result: dict):
    perfect, partial, failed = classify_extracted_fields(seg_result)

    st.markdown("### 📊 Extraction Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Perfect", len(perfect))
    c2.metric("Partial", len(partial))
    c3.metric("Failed", len(failed))

    total = len(perfect) + len(partial) + len(failed)
    st.progress((len(perfect) + 0.5 * len(partial)) / total if total else 0)

    left, right = st.columns([1.2, 1])

    with left:
        for f in perfect:
            st.markdown(f"🟢 {prettify(f)}")
        for f in partial:
            st.markdown(f"🟡 {prettify(f)}")
        for f in failed:
            st.markdown(f"🔴 {prettify(f)}")

    with right:
        if total:
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie(
                [len(perfect), len(partial), len(failed)],
                labels=["Perfect", "Partial", "Failed"],
                autopct="%1.0f%%",
                startangle=90,
                colors=["#00ff00", "#ffff00", "#ff0000"],
            )
            ax.axis("equal")
            st.pyplot(fig)
        else:
            st.info("No fields to display")

# ============================================================
# HEADER
# ============================================================
h1, h2 = st.columns([8, 1])
with h1:
    st.markdown("## Dynamic OCR – Intelligent Cascading Hybrid")
with h2:
    if st.session_state.uploaded and st.button("⬅ Back"):
        st.session_state.uploaded = False
        st.session_state.files = []
        st.rerun()

st.markdown("---")

# ============================================================
# UPLOAD
# ============================================================
if not st.session_state.uploaded:
    uploaded = st.file_uploader(
        "Upload documents",
        list(ALLOWED_EXT),
        accept_multiple_files=True,
    )
    if uploaded:
        st.session_state.files = expand_uploaded_files(uploaded)
        st.session_state.uploaded = True
        st.rerun()
    st.stop()

# ============================================================
# PROCESS FILES
# ============================================================
for f in st.session_state.files:
    pages = load_input(f.getvalue(), f.type)
    if not pages:
        st.error("No raster pages produced. Check loader.")
        continue

    col_img, col_out = st.columns([1, 1], gap="large")

    # -------- PREVIEW (IMAGE-ONLY, OLD STYLE) --------
    with col_img:
        st.markdown("### 📄 Document Preview")
        for i, img in enumerate(pages, 1):
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            st.image(rgb, caption=f"Page {i}", use_container_width=True)
            st.markdown("---")

    # -------- PROCESSING --------
    with col_out:
        with st.spinner("Processing document..."):
            start = time.time()

            results = run_pipeline_batch(pages)
            result = merge_page_results(results)

            doc_type = classify_document(result["raw_lines"])
            policy_type = classify_policy(result["raw_lines"])

            seg = segregate_insurance_document(result["raw_lines"])
            seg["document_type"] = doc_type
            seg["policy_type"] = policy_type
            seg["fields"] = merge_fields(result["fields"], seg.get("fields", {}))

            elapsed = time.time() - start

        # -------- METRICS --------
        acc = result["confidence"] * 100
        pages_cnt = result["page_count"]

        m1, m2, m3 = st.columns(3)
        m1.metric("📄 Pages", pages_cnt)
        m2.metric("🎯 Accuracy (%)", f"{acc:.2f}")
        m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

        st.info(f"📄 **Document Type:** {doc_type}")
        st.info(f"🔐 **Policy Type:** {policy_type}")

        # -------- TABS --------
        tab1, tab2, tab3 = st.tabs(
            ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
        )

        with tab1:
            st.text_area("Extracted Output", render_extracted_text(seg), height=500)

        with tab2:
            draw_extraction_summary_tab(seg)

        with tab3:
            st.text_area("OCR Output", "\n".join(result["raw_lines"]), height=500)

st.caption("")
