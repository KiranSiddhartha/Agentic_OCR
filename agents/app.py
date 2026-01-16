 
# app.py – INTELLIGENT CASCADING HYBRID VISUALIZATION
# Bounding boxes ONLY in preview (NOT in extracted fields)

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
        return {"fields": {}, "raw_lines": [], "confidence": 0.0, "page_count": 0}

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
    }


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


def strip_bbox(fields: dict) -> dict:
    """Remove bbox/page before showing extracted fields"""
    clean = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            v = v.copy()
            v.pop("bbox", None)
            v.pop("page", None)
        clean[k] = v
    return clean


def draw_preview_boxes(image, fields, page_index):
    """
    Draw bounding boxes on preview image.
    Handles:
    - 0-based vs 1-based page index
    - normalized or pixel bbox
    """
    img = image.copy()
    h, w = img.shape[:2]

    for v in fields.values():
        if not isinstance(v, dict):
            continue

        bbox = v.get("bbox")
        page = v.get("page")

        if not bbox or page is None:
            continue

        # 🔑 FIX #1: normalize page index
        if page + 1 != page_index:
            continue

        x1, y1, x2, y2 = bbox

        # 🔑 FIX #2: normalized → pixel
        if 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
            x1, x2 = int(x1 * w), int(x2 * w)
            y1, y2 = int(y1 * h), int(y2 * h)
        else:
            x1, y1, x2, y2 = map(int, bbox)

        cv2.rectangle(
            img,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

    return img
 
def classify_extracted_fields(seg_result: dict):
    fields = seg_result.get("fields", {})
    doc_type = seg_result.get("document_type", "OTH")

    required = FIELD_RULES.get(doc_type)
    if not required:
        required = list(fields.keys())

    perfect, partial, failed = [], [], []

    for f in required:
        data = fields.get(f)
        value = data.get("value") if isinstance(data, dict) else None

        if not value:
            failed.append(f)
        elif isinstance(value, str) and not value.strip():
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
        "Upload documents", list(ALLOWED_EXT), accept_multiple_files=True
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
        continue

    col_img, col_out = st.columns([1, 1], gap="large")

    # -------- PREVIEW --------
    with col_img:
        st.markdown("### 📄 Document Preview")
        for i, img in enumerate(pages, 1):
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            preview_img = draw_preview_boxes(
                rgb,
                st.session_state.get("latest_fields", {}),
                i,
            )
            st.image(preview_img, caption=f"Page {i}", use_container_width=True)
            st.markdown("---")

    # -------- PROCESSING --------
    with col_out:
        with st.spinner("Processing document..."):
            start = time.time()

            results = run_pipeline_batch(pages)
            result = merge_page_results(results)

            seg = segregate_insurance_document(result["raw_lines"])
            seg["fields"] = result["fields"]
            seg["document_type"] = classify_document(result["raw_lines"])
            seg["policy_type"] = classify_policy(result["raw_lines"])

            # store original fields for preview boxes
            st.session_state["latest_fields"] = result["fields"]

            # strip bbox/page before display
            seg["fields"] = strip_bbox(seg["fields"])

            elapsed = time.time() - start

        m1, m2, m3 = st.columns(3)
        m1.metric("📄 Pages", result["page_count"])
        m2.metric("🎯 Accuracy (%)", f"{result['confidence']*100:.2f}")
        m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

        st.info(f"📄 **Document Type:** {seg['document_type']}")
        st.info(f"🔐 **Policy Type:** {seg['policy_type']}")

        tab1, tab2, tab3 = st.tabs(
            ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
        )

        with tab1:
            #st.text_area("Extracted Output", render_extracted_text(seg), height=500)
            st.text_area(
                "Extracted Output",
                render_extracted_text(seg),
                height=500,
                key=f"extracted_output_{ f.name }"
            )

        with tab2:
            draw_extraction_summary_tab(seg)

        with tab3:
            st.text_area(
                "OCR Output", "\n".join(result["raw_lines"]), height=500
            )

st.caption("")
 