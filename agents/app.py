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
# from orchestrator import run_pipeline

# # Optional legacy segmentation
# try:
#     from legacy.insurance_segmentation import segregate_insurance_document
# except ImportError:
#     def segregate_insurance_document(lines):
#         return {"document_type": "UNKNOWN", "policy_type": "UNKNOWN"}

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
# ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".pdf", ".zip")

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
#         "retries": best.get("retries", 0),
#         "retry_history": best.get("retry_history", []),
#         "recommendations": best.get("recommendations", []),
#         "page_count": len(results),
#     }


# def render_extracted_text(result: dict) -> str:
#     out = []
#     for k, v in result.get("fields", {}).items():
#         val = v.get("value") if isinstance(v, dict) else v
#         out.append(f"{prettify(k)}: {val}")
#     return "\n".join(out)


# # ============================================================
# # FIELD VALIDATION + SUMMARY
# # ============================================================
# def is_field_value_valid(field: str, value: str) -> bool:
#     if not value:
#         return False

#     v = value.lower().strip()

#     if field == "insured_name":
#         if any(x in v for x in ["policy", "insurance", "loan", "mortgage"]):
#             return False
#         if any(ch.isdigit() for ch in value):
#             return False
#         return 2 <= len(value.split()) <= 5

#     if field in ("effective_date", "expiration_date"):
#         return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", v))

#     if field == "policy_number":
#         return sum(c.isdigit() for c in value) >= 6

#     return True


# def classify_extracted_fields(result: dict):
#     fields = result.get("fields", {})
#     required = ["policy_number", "insured_name", "effective_date", "expiration_date"]

#     perfect, partial, failed = [], [], []

#     for f in required:
#         data = fields.get(f)
#         if not data:
#             failed.append(f)
#             continue

#         value = data.get("value") if isinstance(data, dict) else data
#         value = str(value).strip()

#         if not is_field_value_valid(f, value):
#             failed.append(f)
#         elif value.lower() in ("", "-", "none", "null"):
#             partial.append(f)
#         else:
#             perfect.append(f)

#     return perfect, partial, failed


# def draw_extraction_summary_tab(result: dict):
#     perfect, partial, failed = classify_extracted_fields(result)

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
#             st.markdown(f"🟠 {prettify(f)}")
#         for f in failed:
#             st.markdown(f"🔴 {prettify(f)}")

#     with right:
#         fig, ax = plt.subplots(figsize=(4, 4))
#         ax.pie(
#             [len(perfect), len(partial), len(failed)],
#             labels=["Perfect", "Partial", "Failed"],
#             autopct="%1.0f%%",
#             startangle=90,
#         )
#         ax.axis("equal")
#         st.pyplot(fig)


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
#     uploaded = st.file_uploader(
#         "Upload documents",
#         list(ALLOWED_EXT),
#         accept_multiple_files=True,
#     )
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

#     with col_img:
#         image_pages = 0
#         for i, page in enumerate(pages, 1):
#             if page.get("type") == "image":
#                 image_pages += 1
#                 st.image(
#                     cv2.cvtColor(page["content"], cv2.COLOR_BGR2RGB),
#                     caption=f"Page {i}"
#                 )
#         if image_pages == 0:
#             st.info("📄 PDF contains embedded text only (OCR not required).")

#     with col_out:
#         with st.spinner("Processing document..."):
#             start = time.time()
#             results = []
#             all_lines = []

#             for page in pages:
#                 if page.get("type") == "image":
#                     page_result = run_pipeline(page["content"], max_retries=1)
#                 else:
#                     page_result = {
#                         "fields": {},
#                         "raw_lines": page["content"].splitlines(),
#                         "confidence": 1.0,
#                         "ocr_confidence": 1.0,
#                         "retries": 0,
#                         "retry_history": [],
#                         "recommendations": [],
#                     }

#                 results.append(page_result)
#                 all_lines.extend(page_result.get("raw_lines", []))

#             result = merge_page_results(results)
#             elapsed = time.time() - start
#             seg = segregate_insurance_document(all_lines)

#         st.info(
#             f"📄 **Document Type:** {seg.get('document_type')} | "
#             f"🔒 **Policy Type:** {seg.get('policy_type')}"
#         )

#         st.metric("📊 Confidence", f"{result.get('confidence', 0.0)*100:.2f}%")
#         st.metric("📄 Pages", result.get("page_count", 0))
#         st.metric("⏱ Time (s)", f"{elapsed:.2f}")

#         tab1, tab2, tab3 = st.tabs(
#             ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
#         )

#         with tab1:
#             st.text_area(
#                 "Extracted Output",
#                 render_extracted_text(result),
#                 height=500,
#                 key=f"extracted_{f.name}"
#             )

#         with tab2:
#             draw_extraction_summary_tab(result)

#         with tab3:
#             st.text_area(
#                 "OCR Output (Layout Preserved)",
#                 "\n".join(result.get("raw_lines", [])),
#                 height=500,
#                 key=f"ocr_{f.name}"
#             )

# st.caption("")



import streamlit as st
import cv2
import sys
import os
import time
import matplotlib.pyplot as plt
import re

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
from orchestrator import run_pipeline_batch, run_pipeline

# Import the proper classifiers
try:
    from agents.insurance_segmentation import segregate_insurance_document
    from classification.document_classifier import classify_document, get_document_explanation
    from classification.policy_classifier import classify_policy, get_policy_explanation
except ImportError:
    def segregate_insurance_document(lines):
        return {"document_type": "OTH", "policy_type": "UNK", "fields": {}, "field_errors": []}
    def classify_document(lines):
        return "OTH"
    def classify_policy(lines):
        return "UNK"
    def get_document_explanation(doc_type):
        return ""
    def get_policy_explanation(policy_type):
        return ""

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(layout="wide", page_title="Dynamic OCR")

# ============================================================
# SESSION STATE
# ============================================================
st.session_state.setdefault("uploaded", False)
st.session_state.setdefault("files", [])

# ============================================================
# CONSTANTS
# ============================================================
ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".pdf", ".zip")

# ============================================================
# HELPERS
# ============================================================
def prettify(name: str) -> str:
    return name.replace("_", " ").title()


def merge_page_results(results: list) -> dict:
    if not results:
        return {}

    all_raw_lines = []
    combined_fields = {}
    best = max(results, key=lambda x: x.get("confidence", 0.0))

    for r in results:
        all_raw_lines.extend(r.get("raw_lines", []))
        combined_fields.update(r.get("fields", {}))

    return {
        "fields": combined_fields,
        "raw_lines": all_raw_lines,
        "confidence": best.get("confidence", 0.0),
        "ocr_confidence": best.get("ocr_confidence", 0.0),
        "retries": best.get("retries", 0),
        "retry_history": best.get("retry_history", []),
        "recommendations": best.get("recommendations", []),
        "page_count": len(results),
    }


def render_extracted_text(seg_result: dict) -> str:
    """
    Render extracted fields from segmentation result
    Shows all extracted fields with their values
    """
    out = []
    
    # Get fields from segmentation
    fields = seg_result.get("fields", {})
    
    if not fields:
        return "No fields extracted"
    
    # Display all extracted fields
    for field_name, field_value in fields.items():
        # Handle both dict and string values
        if isinstance(field_value, dict):
            value = field_value.get("value", "")
        else:
            value = field_value
        
        # Format the output
        display_name = prettify(field_name)
        display_value = value if value else "(not found)"
        out.append(f"{display_name}: {display_value}")
    
    # Show field errors if any
    field_errors = seg_result.get("field_errors", [])
    if field_errors:
        out.append("\n--- Missing Fields ---")
        for error in field_errors:
            out.append(f"⚠️ {error}")
    
    return "\n".join(out)


# ============================================================
# FIELD VALIDATION + SUMMARY
# ============================================================
def is_field_value_valid(field: str, value: str) -> bool:
    if not value or value == "(not found)":
        return False

    v = value.lower().strip()

    if field == "insured_name":
        if any(x in v for x in ["policy", "insurance", "loan", "mortgage"]):
            return False
        if any(ch.isdigit() for ch in value):
            return False
        return 2 <= len(value.split()) <= 5

    if field in ("effective_date", "expiration_date", "cancellation_date", "due_date"):
        return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", v))

    if field == "policy_number":
        return sum(c.isdigit() for c in value) >= 6
    
    if field == "loan_number":
        return sum(c.isdigit() for c in value) >= 6

    return True


def classify_extracted_fields(seg_result: dict):
    """
    Classify fields based on segmentation result
    Uses the actual required fields for the document type
    """
    fields = seg_result.get("fields", {})
    document_type = seg_result.get("document_type", "OTH")
    
    # Get required fields for this document type
    from agents.insurance_segmentation import FIELD_RULES
    required = FIELD_RULES.get(document_type, [])

    perfect, partial, failed = [], [], []

    for f in required:
        data = fields.get(f)
        
        if not data:
            failed.append(f)
            continue

        # Handle both dict and string values
        value = data.get("value") if isinstance(data, dict) else data
        value = str(value).strip() if value else ""

        if not value or value == "(not found)":
            failed.append(f)
        elif not is_field_value_valid(f, value):
            partial.append(f)
        elif value.lower() in ("", "-", "none", "null"):
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
    if total > 0:
        st.progress((len(perfect) + 0.5 * len(partial)) / total)
    else:
        st.progress(0.0)

    left, right = st.columns([1.2, 1])

    with left:
        for f in perfect:
            st.markdown(f"🟢 {prettify(f)}")
        for f in partial:
            st.markdown(f"🟡 {prettify(f)}")
        for f in failed:
            st.markdown(f"🔴 {prettify(f)}")

    with right:
        if total > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie(
                [len(perfect), len(partial), len(failed)],
                labels=["Perfect", "Partial", "Failed"],
                autopct="%1.0f%%",
                startangle=90,
                colors=['#00ff00', '#ffff00', '#ff0000']
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
    st.markdown("## Dynamic OCR")
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
# PROCESS FILES (OPTIMIZED WITH BATCH PROCESSING)
# ============================================================
for f in st.session_state.files:
    pages = load_input(f.getvalue(), f.type)
    if not pages:
        continue

    col_img, col_out = st.columns([1, 1], gap="large")

    with col_img:
        image_pages = 0
        for i, page in enumerate(pages, 1):
            if page.get("type") == "image":
                image_pages += 1
                st.image(
                    cv2.cvtColor(page["content"], cv2.COLOR_BGR2RGB),
                    caption=f"Page {i}"
                )
        if image_pages == 0:
            st.info("📄 PDF contains embedded text only (OCR not required).")

    with col_out:
        with st.spinner("Processing document..."):
            start = time.time()
            
            # Separate image and text pages
            image_pages_data = [p for p in pages if p.get("type") == "image"]
            text_pages_data = [p for p in pages if p.get("type") != "image"]
            
            results = []
            all_lines = []
            
            # Process all image pages in parallel (3-5x faster)
            if image_pages_data:
                images = [p["content"] for p in image_pages_data]
                
                # Batch processing with parallel execution
                batch_results = run_pipeline_batch(
                    images, 
                    max_retries=1, 
                    debug=False,
                    max_workers=min(4, len(images))
                )
                
                results.extend(batch_results)
                
                for r in batch_results:
                    all_lines.extend(r.get("raw_lines", []))
            
            # Process text pages (fast, no OCR needed)
            for page in text_pages_data:
                page_result = {
                    "fields": {},
                    "raw_lines": page["content"].splitlines(),
                    "confidence": 1.0,
                    "ocr_confidence": 1.0,
                    "retries": 0,
                    "retry_history": [],
                    "recommendations": [],
                }
                results.append(page_result)
                all_lines.extend(page_result.get("raw_lines", []))

            result = merge_page_results(results)
            elapsed = time.time() - start
            
            # Use proper segmentation with classifiers
            seg = segregate_insurance_document(all_lines)

        # Display Document Type and Policy Type with explanations
        doc_type = seg.get('document_type', 'OTH')
        policy_type = seg.get('policy_type', 'UNK')
        
        doc_explanation = get_document_explanation(doc_type)
        policy_explanation = get_policy_explanation(policy_type)
        
        st.info(
            f"📄 **Document Type:** {doc_type}"
            + (f" - {doc_explanation}" if doc_explanation else "")
        )
        st.info(
            f"🔒 **Policy Type:** {policy_type}"
            + (f" - {policy_explanation}" if policy_explanation else "")
        )

        # Key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Confidence", f"{result.get('confidence', 0.0)*100:.2f}%")
        with col2:
            st.metric("📄 Pages", result.get("page_count", 0))
        with col3:
            st.metric("⏱ Time (s)", f"{elapsed:.2f}")

        # Tabs
        tab1, tab2, tab3 = st.tabs(
            ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
        )

        with tab1:
            st.text_area(
                "Extracted Output",
                render_extracted_text(seg),
                height=500,
                key=f"extracted_{f.name}"
            )

        with tab2:
            draw_extraction_summary_tab(seg)

        with tab3:
            st.text_area(
                "OCR Output (Layout Preserved)",
                "\n".join(result.get("raw_lines", [])),
                height=500,
                key=f"ocr_{f.name}"
            )

st.caption("")