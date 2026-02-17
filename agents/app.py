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
from agents.insurance_segmentation import segregate_insurance_document, FIELD_RULES, POLICY_FIELD_RULES
from agents.document_classifier import classify_document, get_document_explanation
from agents.policy_classifier import classify_policy, get_policy_explanation
import html

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(layout="wide", page_title="Dynamic OCR")
st.session_state.setdefault("processed", False)

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
            "document_type": "UNK",
            "policy_type": "UNK",
        }

    all_lines = []
    fields = {}

    # Merge all pages FIRST
    for r in results:
        all_lines.extend(r.get("raw_lines", []))
        fields.update(r.get("fields", {}))

    merged_lines = all_lines

    # Now classify on FULL document
    from document_router import classify_doc_type
    from policy_classifier import classify_policy

    doc_type = classify_doc_type(merged_lines)
    policy_type = classify_policy(merged_lines)

    best = max(results, key=lambda r: r.get("confidence", 0.0))

    return {
        "fields": fields,
        "raw_lines": merged_lines,
        "confidence": best.get("confidence", 0.0),
        "page_count": len(results),
        "document_type": doc_type,
        "policy_type": policy_type,
        "approach": best.get("approach"),
        "routing_reason": best.get("routing_reason"),
        "fallback_used": best.get("fallback_used"),
    }

def render_extracted_text(seg: dict) -> str:
    """Render extracted fields, filtered to only show fields allowed
    by get_allowed_fields() so the count matches the summary tab
    and the field limitation reason.
    """
    from agents.insurance_segmentation import get_allowed_fields

    fields = seg.get("fields", {})
    if not fields:
        return "No fields extracted"

    doc_type = seg.get("document_type", "UNK")
    policy_type = seg.get("policy_type", "UNK")
    allowed = get_allowed_fields(doc_type, policy_type)

    out = []
    for k, v in fields.items():
        # Only show fields that are in the allowed set for this doc+policy type
        if allowed and k not in allowed:
            continue
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


def draw_preview_boxes(image, fields, page_index, ocr_data=None, bbox_mode="fields"):
    """
    Draw bounding boxes on preview image.
    
    Args:
        image: Input image
        fields: Extracted fields with bounding boxes
        page_index: Current page number (1-based)
        ocr_data: Raw OCR data with word-level bounding boxes (optional)
        bbox_mode: "fields" (field-level), "words" (word-level), or "both"
    
    Handles:
    - 0-based vs 1-based page index
    - normalized or pixel bbox
    - Word-level and field-level bounding boxes
    """
    img = image.copy()
    h, w = img.shape[:2]
    
    print(f"\n{'='*80}")
    print(f"=== Drawing boxes for page {page_index} ===")
    print(f"Image size: {w}x{h}")
    print(f"Bbox mode: {bbox_mode}")
    print(f"Fields received: {len(fields) if fields else 0}")
    
    if fields:
        # Count fields with bboxes for this page
        fields_with_bbox = 0
        for fname, fdata in fields.items():
            if isinstance(fdata, dict) and 'bbox' in fdata and 'page' in fdata:
                fields_with_bbox += 1
        print(f"Fields with bbox data: {fields_with_bbox}")
    print('='*80)

    # Draw word-level bounding boxes (if available and requested)
    if bbox_mode in ["words", "both"] and ocr_data:
        words = ocr_data.get("text", [])
        boxes = ocr_data.get("boxes", [])
        
        print(f"Drawing {len(words)} word boxes...")
        
        for word, box in zip(words, boxes):
            if not box:
                continue
            
            # OCR boxes are normalized 0-1000
            x1, y1, x2, y2 = box
            x1 = int((x1 / 1000) * w)
            y1 = int((y1 / 1000) * h)
            x2 = int((x2 / 1000) * w)
            y2 = int((y2 / 1000) * h)
            
            # Draw word-level boxes in orange
            cv2.rectangle(
                img,
                (x1, y1),
                (x2, y2),
                (255, 165, 0),  # Orange for word-level
                1
            )

    # Draw field-level bounding boxes (if requested)
    if bbox_mode in ["fields", "both"]:
        drawn_count = 0
        
        if not fields:
            print("WARNING: No fields data available!")
            return img
            
        for field_name, v in fields.items():
            print(f"\nProcessing field: {field_name}")
            print(f"  Field type: {type(v)}")
            
            if not isinstance(v, dict):
                print(f"  Skipping - not a dict")
                continue

            bbox = v.get("bbox")
            page = v.get("page")
            
            print(f"  Has bbox: {bbox is not None}")
            print(f"  Bbox value: {bbox}")
            print(f"  Page: {page} (target: {page_index})")

            if not bbox or page is None:
                print(f"  Skipping - no bbox or page")
                continue

            # 🔑 FIX #1: Improved page matching logic
            # Handle multiple page numbering conventions
            page_matches = False
            
            # Case 1: page is 0-based, page_index is 1-based
            if page + 1 == page_index:
                page_matches = True
                print(f"  ✓ Page match (0-based): {page} + 1 == {page_index}")
            # Case 2: both are 1-based
            elif page == page_index:
                page_matches = True
                print(f"  ✓ Page match (1-based): {page} == {page_index}")
            # Case 3: page is 1-based, page_index needs adjustment
            elif page == page_index - 1:
                page_matches = True
                print(f"  ✓ Page match (adjusted): {page} == {page_index - 1}")
            # Case 4: Try page 0 = page 1 (some extractors use 0 for first page)
            elif page == 0 and page_index == 1:
                page_matches = True
                print(f"  ✓ Page match (zero-indexed): page 0 == page 1")
                
            if not page_matches:
                print(f"  ✗ Skipping - page mismatch (field page={page}, display page={page_index})")
                continue

            try:
                x1, y1, x2, y2 = bbox
                print(f"  Original bbox: ({x1}, {y1}, {x2}, {y2})")

                # 🔑 FIX #2: Robust coordinate conversion
                # Check if coordinates are normalized (0-1) or (0-1000) or pixels
                if all(isinstance(coord, (int, float)) for coord in [x1, y1, x2, y2]):
                    if 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
                        # Normalized 0-1
                        x1, x2 = int(x1 * w), int(x2 * w)
                        y1, y2 = int(y1 * h), int(y2 * h)
                        print(f"  Converted from 0-1 normalized to pixels")
                    elif 0 <= x1 <= 1000 and 0 <= y1 <= 1000 and 0 <= x2 <= 1000 and 0 <= y2 <= 1000:
                        # Normalized 0-1000
                        x1 = int((x1 / 1000) * w)
                        y1 = int((y1 / 1000) * h)
                        x2 = int((x2 / 1000) * w)
                        y2 = int((y2 / 1000) * h)
                        print(f"  Converted from 0-1000 normalized to pixels")
                    else:
                        # Already in pixels
                        x1, y1, x2, y2 = map(int, bbox)
                        print(f"  Using pixel coordinates as-is")
                    
                    # Ensure coordinates are within image bounds
                    x1 = max(0, min(x1, w))
                    y1 = max(0, min(y1, h))
                    x2 = max(0, min(x2, w))
                    y2 = max(0, min(y2, h))
                    
                    # Ensure x2 > x1 and y2 > y1 (swap if needed)
                    if x2 < x1:
                        x1, x2 = x2, x1
                    if y2 < y1:
                        y1, y2 = y2, y1
                    
                    # Validate box has area
                    if x2 - x1 < 1 or y2 - y1 < 1:
                        print(f"  ✗ Box too small: width={x2-x1}, height={y2-y1}")
                        continue
                else:
                    print(f"  ✗ Invalid bbox format: {bbox}")
                    continue
                
                print(f"  Final pixel bbox: ({x1}, {y1}, {x2}, {y2})")

                # Draw field-level boxes in dark green
                dark_green = (0, 100, 0)  # Dark green color (BGR format)
                cv2.rectangle(
                    img,
                    (x1, y1),
                    (x2, y2),
                    dark_green,  # Dark green for field-level
                    2
                )
                
                # Add field label
                label = prettify(field_name)
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                font_thickness = 1
                
                # Get text size for background
                (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, font_thickness)
                
                # Draw background rectangle for text
                label_y = max(text_h + 4, y1 - 4)
                cv2.rectangle(
                    img,
                    (x1, label_y - text_h - 4),
                    (x1 + text_w + 4, label_y),
                    dark_green,
                    -1
                )
                
                # Draw text
                cv2.putText(
                    img,
                    label,
                    (x1 + 2, label_y - 2),
                    font,
                    font_scale,
                    (0, 0, 0),
                    font_thickness
                )
                drawn_count += 1
                print(f"  ✓ Drew box successfully!")
                
            except Exception as e:
                print(f"  ERROR drawing box: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print(f"\n=== Summary: Drew {drawn_count} field boxes on page {page_index} ===\n")

    return img


def build_field_limitation_reason(document_type: str, policy_type: str):
    """Build explanation for why only certain fields are shown.
    
    Uses get_allowed_fields() as the single source of truth so that
    the field count here matches extraction and the summary tab.
    """
    from agents.insurance_segmentation import get_allowed_fields

    allowed_set = get_allowed_fields(document_type, policy_type)
    allowed = sorted(allowed_set)

    policy_fields = POLICY_FIELD_RULES.get(policy_type, set())
    scope = "Document + Policy rules" if policy_fields else "Document rules"

    text = (
        f"Based on {scope}\n\n"
        f"Document Type: {document_type}\n"
        f"{'Policy Type: ' + policy_type + chr(10) if policy_fields else ''}"
        f"Allowed fields ({len(allowed)}):\n"
        + " • ".join(prettify(f) for f in allowed)
    )

    # Escape HTML and replace newlines for title attribute
    return html.escape(text).replace("\n", "&#10;")

def classify_extracted_fields(seg_result: dict):
    """Classify extracted fields as perfect/partial/failed.
    
    Uses get_allowed_fields() as the single source of truth so that
    the field list here matches the extraction tab and the limitation reason.
    """
    from agents.insurance_segmentation import get_allowed_fields

    fields = seg_result.get("fields", {})
    doc_type = seg_result.get("document_type", "OTH")
    policy_type = seg_result.get("policy_type", "UNK")

    required = get_allowed_fields(doc_type, policy_type)
    if not required:
        required = set(fields.keys())

    perfect, partial, failed = [], [], []

    for f in sorted(required):
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

    # -------- LAYOUT: Preview (left) + Results (right) --------
    col_img, col_out = st.columns([1, 1], gap="large")
 
    with col_img:
        st.markdown("### 📄 Document Preview")

        for i, img in enumerate(pages, 1):
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            if st.session_state.get("processed"):
                page_key = f"{f.name}_page_{i}"
                ocr_data = st.session_state.get("ocr_data_by_page", {}).get(page_key)

                rgb = draw_preview_boxes(
                    rgb,
                    st.session_state.get("latest_fields", {}),
                    i,
                    ocr_data=ocr_data,
                    bbox_mode="both",  # or "fields"
                )

            st.image(rgb, caption=f"Page {i}", use_container_width=True)

            if i < len(pages):
                st.markdown("---")

    # -------- PROCESSING (spinner shows in right column) --------
    with col_out:
        with st.spinner("⏳ Processing document..."):
            start = time.time()

            # Extract OCR data for word-level bounding boxes
            from agents.vision_agent import VisionAgent
            from preprocessing import preprocess

            vision = VisionAgent(use_layoutxlm=True)
            ocr_data_by_page = {}

            # for page_idx, img in enumerate(pages, 1):
            #     processed = preprocess(img)
            #     ocr = vision.ocr_engine.run_with_boxes(processed)
            #     page_key = f"{f.name}_page_{page_idx}"
            #     ocr_data_by_page[page_key] = ocr

            for page_idx, img in enumerate(pages, 1):
                ocr = vision.ocr_engine.run_with_boxes(img)

            # Store OCR data in session state
            if "ocr_data_by_page" not in st.session_state:
                st.session_state["ocr_data_by_page"] = {}
            st.session_state["ocr_data_by_page"].update(ocr_data_by_page)

            # Run the main pipeline
            results = run_pipeline_batch(pages)
            result = merge_page_results(results)

            # seg = {
            #     "fields": strip_bbox(result["fields"]),
            #     "document_type": result.get("document_type") if result.get("document_type") not in (None, "", "UNK", "OTH") else classify_document(result.get("raw_lines", [])),
            #     "policy_type": result.get("policy_type") if result.get("policy_type") not in (None, "", "UNK") else classify_policy(result.get("raw_lines", [])),
            # }

            seg = {
                "fields": strip_bbox(result["fields"]),
                "document_type": result.get("document_type", "UNK"),
                "policy_type": result.get("policy_type", "UNK"),
            } 
            
            # store original fields for preview boxes
            st.session_state["latest_fields"] = result["fields"]
            st.session_state["processed"] = True
            
            # Debug: Check what fields have bounding boxes
            print(f"\n=== Stored fields for bounding boxes ===")
            for fname, fdata in result["fields"].items():
                if isinstance(fdata, dict):
                    has_bbox = "bbox" in fdata
                    has_page = "page" in fdata
                    print(f"  {fname}: bbox={has_bbox}, page={has_page}")
                    if has_bbox and has_page:
                        print(f"    → bbox={fdata['bbox']}, page={fdata['page']}")
            print("=" * 50)
            
            elapsed = time.time() - start

    # # -------- UPDATE PREVIEW WITH BOUNDING BOXES --------
    # with col_img:
    #     st.markdown("### 📄 Document Preview")

    #     for i, img in enumerate(pages, 1):
    #         rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    #         if st.session_state["processed"]:
    #             page_key = f"{f.name}_page_{i}"
    #             ocr_data = st.session_state.get("ocr_data_by_page", {}).get(page_key)

    #             rgb = draw_preview_boxes(
    #                 rgb,
    #                 st.session_state.get("latest_fields", {}),
    #                 i,
    #                 ocr_data=ocr_data,
    #                 bbox_mode="both",  # or "fields"
    #             )

    #         st.image(rgb, caption=f"Page {i}", use_container_width=True)

    #         if i < len(pages):
    #             st.markdown("---")

    # -------- RESULTS (right column) --------
    with col_out:
        m1, m2, m3 = st.columns(3)
        m1.metric("📄 Pages", result["page_count"])
        m2.metric("🎯 Accuracy (%)", f"{result['confidence']*100:.2f}")
        m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

        # ---------- DOC / POLICY (ℹ️ hover restored) ----------
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(
                f"""
                **📄 Document Type:** `{seg['document_type']}`
                <span title="{get_document_explanation(seg['document_type'])}">ℹ️</span>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                **🔐 Policy Type:** `{seg['policy_type']}`
                <span title="{get_policy_explanation(seg['policy_type'])}">ℹ️</span>
                """,
                unsafe_allow_html=True,
            )

        # ---------- FIELD LIMITATION (ℹ️ hover) ----------
        from agents.insurance_segmentation import get_allowed_fields as _get_allowed
        _allowed = _get_allowed(seg["document_type"], seg["policy_type"])
        _allowed_count = len(_allowed) if _allowed else len(seg["fields"])

        with st.expander(f"Why only {_allowed_count} fields? ℹ️"):
            st.markdown(
                build_field_limitation_reason(
                    seg["document_type"],
                    seg["policy_type"],
                ),
                unsafe_allow_html=True,
            )

        tab1, tab2, tab3 = st.tabs(
            ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
        )

        with tab1:
            st.text_area(
                "Extracted Output",
                render_extracted_text(seg),
                height=500,
                key=f"extracted_output_{f.name}_{i}_{int(time.time()*1000)}"
            )

        with tab2:
            draw_extraction_summary_tab(seg)

        with tab3:
            st.text_area(
                "OCR Output",
                "\n".join(result["raw_lines"]),
                height=500,
                key=f"ocr_output_{f.name}_{i}_{int(time.time()*1000)}"
            )

st.caption("")