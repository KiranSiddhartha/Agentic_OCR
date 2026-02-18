
# # app.py – INTELLIGENT CASCADING HYBRID VISUALIZATION
# # Bounding boxes ONLY in preview (NOT in extracted fields)

# import streamlit as st
# import cv2
# import sys
# import os
# import time
# import matplotlib.pyplot as plt
# import re
# import numpy as np


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
# from orchestrator import run_pipeline_batch
# from agents.insurance_segmentation import segregate_insurance_document, FIELD_RULES, POLICY_FIELD_RULES
# from agents.document_classifier import classify_document, get_document_explanation
# from agents.policy_classifier import classify_policy, get_policy_explanation
# import html

# # ============================================================
# # PAGE CONFIG
# # ============================================================
# st.set_page_config(layout="wide", page_title="Dynamic OCR")

# # ============================================================
# # SESSION STATE
# # ============================================================
# st.session_state.setdefault("uploaded", False)
# st.session_state.setdefault("files", [])

# ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".zip")

# # ============================================================
# # HELPERS
# # ============================================================

# def prettify(name: str) -> str:
#     return name.replace("_", " ").title()


# def merge_page_results(results: list) -> dict:
#     if not results:
#         return {"fields": {}, "raw_lines": [], "confidence": 0.0, "page_count": 0}

#     all_lines, fields = [], {}
#     best = max(results, key=lambda r: r.get("confidence", 0.0))

#     for r in results:
#         all_lines.extend(r.get("raw_lines", []))
#         fields.update(r.get("fields", {}))

#     return {
#         "fields": fields,
#         "raw_lines": all_lines,
#         "confidence": best.get("confidence", 0.0),
#         "page_count": len(results),
#     }


# def render_extracted_text(seg: dict) -> str:
#     fields = seg.get("fields", {})
#     if not fields:
#         return "No fields extracted"

#     out = []
#     for k, v in fields.items():
#         val = v.get("value") if isinstance(v, dict) else v
#         if val:
#             out.append(f"{prettify(k)}: {val}")
#     return "\n".join(out)


# def strip_bbox(fields: dict) -> dict:
#     """Remove bbox/page before showing extracted fields"""
#     clean = {}
#     for k, v in fields.items():
#         if isinstance(v, dict):
#             v = v.copy()
#             v.pop("bbox", None)
#             v.pop("page", None)
#         clean[k] = v
#     return clean


# def draw_preview_boxes(image, fields, page_index):
#     """
#     Draw bounding boxes on preview image.
#     Handles:
#     - 0-based vs 1-based page index
#     - normalized or pixel bbox
#     """
#     img = image.copy()
#     h, w = img.shape[:2]

#     for v in fields.values():
#         if not isinstance(v, dict):
#             continue

#         bbox = v.get("bbox")
#         page = v.get("page")

#         if not bbox or page is None:
#             continue

#         # 🔑 FIX #1: normalize page index
#         if page + 1 != page_index:
#             continue

#         x1, y1, x2, y2 = bbox

#         # 🔑 FIX #2: normalized → pixel
#         if 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
#             x1, x2 = int(x1 * w), int(x2 * w)
#             y1, y2 = int(y1 * h), int(y2 * h)
#         else:
#             x1, y1, x2, y2 = map(int, bbox)

#         cv2.rectangle(
#             img,
#             (x1, y1),
#             (x2, y2),
#             (0, 255, 0),
#             2
#         )

#     return img


# def build_field_limitation_reason(document_type: str, policy_type: str):
#     """Build explanation for why only certain fields are shown"""
#     doc_fields = FIELD_RULES.get(document_type, set())
#     policy_fields = POLICY_FIELD_RULES.get(policy_type, set())

#     if policy_fields:
#         allowed = sorted(set(doc_fields) & set(policy_fields))
#         scope = "Document + Policy rules"
#     else:
#         allowed = sorted(doc_fields)
#         scope = "Document rules"

#     text = (
#         f"Based on {scope}\n\n"
#         f"Document Type: {document_type}\n"
#         f"{'Policy Type: ' + policy_type + chr(10) if policy_fields else ''}"
#         f"Allowed fields ({len(allowed)}):\n"
#         + " • ".join(prettify(f) for f in allowed)
#     )

#     # Escape HTML and replace newlines for title attribute
#     return html.escape(text).replace("\n", "&#10;")

# def classify_extracted_fields(seg_result: dict):
#     fields = seg_result.get("fields", {})
#     doc_type = seg_result.get("document_type", "OTH")

#     required = FIELD_RULES.get(doc_type)
#     if not required:
#         required = list(fields.keys())

#     perfect, partial, failed = [], [], []

#     for f in required:
#         data = fields.get(f)
#         value = data.get("value") if isinstance(data, dict) else None

#         if not value:
#             failed.append(f)
#         elif isinstance(value, str) and not value.strip():
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
#     st.markdown("## Dynamic OCR – Intelligent Cascading Hybrid")
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
#         "Upload documents", list(ALLOWED_EXT), accept_multiple_files=True
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

#     # -------- PREVIEW --------
#     with col_img:
#         st.markdown("### 📄 Document Preview")
#         for i, img in enumerate(pages, 1):
#             rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#             preview_img = draw_preview_boxes(
#                 rgb,
#                 st.session_state.get("latest_fields", {}),
#                 i,
#             )
#             st.image(preview_img, caption=f"Page {i}", use_container_width=True)
#             st.markdown("---")

#     # -------- PROCESSING --------
#     with col_out:
#         with st.spinner("Processing document..."):
#             start = time.time()

#             results = run_pipeline_batch(pages)
#             result = merge_page_results(results)

#             # 🔑 FIX: Use orchestrator fields directly, don't call segregate_insurance_document
#             # (orchestrator already does all extraction)
#             seg = {
#                 "fields": strip_bbox(result["fields"]),
#                 "document_type": classify_document(result["raw_lines"]),
#                 "policy_type": classify_policy(result["raw_lines"])
#             }

#             # store original fields for preview boxes
#             st.session_state["latest_fields"] = result["fields"]

#             elapsed = time.time() - start

#         m1, m2, m3 = st.columns(3)
#         m1.metric("📄 Pages", result["page_count"])
#         m2.metric("🎯 Accuracy (%)", f"{result['confidence']*100:.2f}")
#         m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

#         # ---------- DOC / POLICY (ℹ️ hover restored) ----------
#         c1, c2 = st.columns([1, 1])
#         with c1:
#             st.markdown(
#                 f"""
#                 **📄 Document Type:** `{seg['document_type']}`
#                 <span title="{get_document_explanation(seg['document_type'])}">ℹ️</span>
#                 """,
#                 unsafe_allow_html=True,
#             )
#         with c2:
#             st.markdown(
#                 f"""
#                 **🔐 Policy Type:** `{seg['policy_type']}`
#                 <span title="{get_policy_explanation(seg['policy_type'])}">ℹ️</span>
#                 """,
#                 unsafe_allow_html=True,
#             )
        
#         # ---------- FIELD LIMITATION (ℹ️ hover) ----------
#         st.markdown(
#             f"""
#             **Why only {len(seg['fields'])} fields?**
#             <span title="{build_field_limitation_reason(
#                 seg['document_type'],
#                 seg['policy_type']
#             )}">ℹ️</span>
#             """,
#             unsafe_allow_html=True,
#         )

#         tab1, tab2, tab3 = st.tabs(
#             ["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"]
#         )

#         with tab1:
#             st.text_area(
#                 "Extracted Output",
#                 render_extracted_text(seg),
#                 height=500,
#                 key=f"extracted_output_{f.name}_{i}_{int(time.time()*1000)}"
#             )

#         with tab2:
#             draw_extraction_summary_tab(seg)

#         with tab3:
#             st.text_area(
#                 "OCR Output", 
#                 "\n".join(result["raw_lines"]), 
#                 height=500,
#                 key=f"ocr_output_{f.name}_{i}_{int(time.time()*1000)}"
#             )

# st.caption("")

 
#2nd iteration updates:
# # app.py – INTELLIGENT CASCADING HYBRID VISUALIZATION
# # Click field → INSTANT RED bounding box highlight on preview
# # Fixed: Back button now correctly resets Home and stops pending processing

# import streamlit as st
# import cv2
# import sys
# import os
# import time
# import matplotlib.pyplot as plt
# import numpy as np
# import html
# import re
# import hashlib
# import json

# # ============================================================
# # PATH FIX
# # ============================================================
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# # ============================================================
# # IMPORTS (top-level, loaded ONCE)
# # ============================================================
# from utils.file_loader import expand_uploaded_files, load_input
# from orchestrator import run_pipeline_batch
# from agents.insurance_segmentation import (
#     segregate_insurance_document,
#     FIELD_RULES,
#     POLICY_FIELD_RULES,
# )
# from agents.document_classifier import classify_document, get_document_explanation
# from agents.policy_classifier import classify_policy, get_policy_explanation
# from agents.insurance_segmentation import get_allowed_fields

# # ============================================================
# # PAGE CONFIG
# # ============================================================
# st.set_page_config(layout="wide", page_title="Dynamic OCR")

# # ============================================================
# # CSS FIX: LEFT ALIGN BUTTONS + NO TRANSITION LAG
# # ============================================================
# st.markdown("""
#     <style>
#     /* Force text in buttons to align left */
#     div.stButton > button {
#         text-align: left !important;
#         justify-content: flex-start !important;
#         padding-left: 1rem !important;
#     }
#     /* Remove image transition lag */
#     img {
#         transition: none !important;
#         -webkit-transition: none !important;
#     }
#     </style>
# """, unsafe_allow_html=True)

# # ============================================================
# # SESSION STATE DEFAULTS
# # ============================================================
# _DEFAULTS = {
#     "uploaded": False,
#     "processed": False,
#     "files": [],
#     "ocr_data_by_page": {},
#     "latest_fields": {},
#     "pipeline_results": {},
#     "selected_field": None,
#     "decoded_pages": {},
#     "base_preview_cache": {},       # Small resized base images
#     "highlight_preview_cache": {},  # Cached Red-Box images
#     "fields_hash_cache": {},        
#     "uploader_key": 0,              # NEW: Logic to force uploader reset
# }
# for _k, _v in _DEFAULTS.items():
#     st.session_state.setdefault(_k, _v)

# ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".zip")

# # CONSTANT: Max width for preview images to ensure speed
# PREVIEW_MAX_WIDTH = 1000 


# # ============================================================
# # RESET TO HOME
# # ============================================================
# def reset_to_home():
#     """
#     Clears session state and increments uploader_key.
#     This forces the st.file_uploader widget to reset/clear.
#     """
#     # Save the current key to increment it
#     current_key = st.session_state.get("uploader_key", 0)
    
#     # Clear all state
#     for key in list(st.session_state.keys()):
#         del st.session_state[key]
    
#     # Restore defaults
#     for _k, _v in _DEFAULTS.items():
#         st.session_state[_k] = (
#             _v if not isinstance(_v, (dict, list)) else type(_v)()
#         )
    
#     # Increment key -> New Widget ID -> Clears files
#     st.session_state["uploader_key"] = current_key + 1


# # ============================================================
# # HELPERS
# # ============================================================
# def prettify(name: str) -> str:
#     return name.replace("_", " ").title()


# def merge_page_results(results: list) -> dict:
#     if not results:
#         return {
#             "fields": {},
#             "raw_lines": [],
#             "confidence": 0.0,
#             "page_count": 0,
#             "document_type": "OTH",
#             "policy_type": "OTH",
#         }

#     all_lines, fields = [], {}
#     for r in results:
#         all_lines.extend(r.get("raw_lines", []))
#         fields.update(r.get("fields", {}))

#     from document_router import classify_doc_type
#     from policy_classifier import classify_policy as _cp

#     doc_type = classify_doc_type(all_lines)
#     policy_type = _cp(all_lines)
#     best = max(results, key=lambda r: r.get("confidence", 0.0))

#     return {
#         "fields": fields,
#         "raw_lines": all_lines,
#         "confidence": best.get("confidence", 0.0),
#         "page_count": len(results),
#         "document_type": doc_type,
#         "policy_type": policy_type,
#         "approach": best.get("approach"),
#         "routing_reason": best.get("routing_reason"),
#         "fallback_used": best.get("fallback_used"),
#     }


# def strip_bbox(fields: dict) -> dict:
#     clean = {}
#     for k, v in fields.items():
#         if isinstance(v, dict):
#             v = v.copy()
#             v.pop("bbox", None)
#             v.pop("page", None)
#         clean[k] = v
#     return clean


# def ensure_fields_have_page(fields: dict, default_page: int = 0) -> dict:
#     patched = {}
#     for k, v in fields.items():
#         if isinstance(v, dict):
#             v = v.copy()
#             if v.get("page") is None:
#                 v["page"] = default_page
#         patched[k] = v
#     return patched


# # ============================================================
# # HASH HELPER
# # ============================================================
# def _hash_fields(fields: dict) -> str:
#     serializable = {}
#     for k, v in fields.items():
#         if isinstance(v, dict):
#             serializable[k] = {
#                 "bbox": v.get("bbox"),
#                 "page": v.get("page"),
#             }
#     return hashlib.md5(
#         json.dumps(serializable, sort_keys=True, default=str).encode()
#     ).hexdigest()


# # ============================================================
# # IMPROVED BBOX SYNTHESIS
# # ============================================================
# def _normalize_text(text: str) -> str:
#     return re.sub(r'[^\w\s]', '', text.strip().lower())

# def _tokenize_value(value: str) -> list:
#     raw = re.split(r'[\s,]+', value.strip())
#     return [t.lower() for t in raw if t]

# def _find_value_bbox(value: str, words: list, boxes: list) -> list:
#     if not value or not words:
#         return None
#     value_clean = value.strip()
#     if not value_clean:
#         return None
#     ocr_words = [w.strip() if w else "" for w in words]
#     ocr_lower = [w.lower() for w in ocr_words]
#     value_lower = value_clean.lower()
#     for idx, wl in enumerate(ocr_lower):
#         if wl == value_lower and idx < len(boxes) and boxes[idx]:
#             return list(boxes[idx])
#     value_tokens = _tokenize_value(value_clean)
#     if not value_tokens:
#         return None
#     ocr_tokens = []
#     ocr_token_box_idx = []
#     for idx, w in enumerate(ocr_words):
#         sub_tokens = re.split(r'[\s,]+', w.strip())
#         for st_ in sub_tokens:
#             if st_:
#                 ocr_tokens.append(st_.lower())
#                 ocr_token_box_idx.append(idx)
#     best_match = None
#     best_match_len = 0
#     for start in range(len(ocr_tokens)):
#         matched = 0
#         for vi, vt in enumerate(value_tokens):
#             ti = start + vi
#             if ti >= len(ocr_tokens): break
#             ot = _normalize_text(ocr_tokens[ti])
#             vt_clean = _normalize_text(vt)
#             if ot == vt_clean: matched += 1
#             elif vt_clean and ot and (vt_clean in ot or ot in vt_clean): matched += 1
#             elif (re.sub(r'[^0-9]', '', ot) == re.sub(r'[^0-9]', '', vt_clean) and len(re.sub(r'[^0-9]', '', vt_clean)) >= 3): matched += 1
#             else: break
#         if matched == len(value_tokens) and matched > best_match_len:
#             box_indices = set()
#             for vi in range(matched):
#                 box_indices.add(ocr_token_box_idx[start + vi])
#             x1m, y1m = float("inf"), float("inf")
#             x2m, y2m = float("-inf"), float("-inf")
#             for bi in box_indices:
#                 if bi < len(boxes) and boxes[bi]:
#                     a, b, c, d = boxes[bi]
#                     x1m, y1m = min(x1m, a), min(y1m, b)
#                     x2m, y2m = max(x2m, c), max(y2m, d)
#             if x1m < float("inf"):
#                 best_match = [x1m, y1m, x2m, y2m]
#                 best_match_len = matched
#     if best_match: return best_match
#     min_match = max(1, int(len(value_tokens) * 0.6))
#     for start in range(len(ocr_tokens)):
#         matched = 0
#         last_matched = start
#         for vi, vt in enumerate(value_tokens):
#             ti = start + vi
#             if ti >= len(ocr_tokens): break
#             ot = _normalize_text(ocr_tokens[ti])
#             vt_clean = _normalize_text(vt)
#             if ot == vt_clean or (vt_clean and ot and (vt_clean in ot or ot in vt_clean)):
#                 matched += 1
#                 last_matched = ti
#         if matched >= min_match:
#             box_indices = set()
#             for ti in range(start, last_matched + 1):
#                 if ti < len(ocr_token_box_idx):
#                     box_indices.add(ocr_token_box_idx[ti])
#             x1m, y1m = float("inf"), float("inf")
#             x2m, y2m = float("-inf"), float("-inf")
#             for bi in box_indices:
#                 if bi < len(boxes) and boxes[bi]:
#                     a, b, c, d = boxes[bi]
#                     x1m, y1m = min(x1m, a), min(y1m, b)
#                     x2m, y2m = max(x2m, c), max(y2m, d)
#             if x1m < float("inf"): return [x1m, y1m, x2m, y2m]
#     for vt in value_tokens:
#         vt_clean = _normalize_text(vt)
#         if len(vt_clean) < 3: continue
#         for idx, wl in enumerate(ocr_lower):
#             wl_clean = _normalize_text(wl)
#             if vt_clean == wl_clean and idx < len(boxes) and boxes[idx]:
#                 x1m, y1m, x2m, y2m = list(boxes[idx])
#                 for next_vt in value_tokens:
#                     nvt = _normalize_text(next_vt)
#                     if len(nvt) < 2: continue
#                     s_start = max(0, idx - 2)
#                     s_end = min(len(ocr_lower), idx + len(value_tokens) + 2)
#                     for nidx in range(s_start, s_end):
#                         nwl = _normalize_text(ocr_lower[nidx])
#                         if nwl and nvt and (nvt in nwl or nwl in nvt):
#                             if nidx < len(boxes) and boxes[nidx]:
#                                 a, b, c, d = boxes[nidx]
#                                 x1m, y1m = min(x1m, a), min(y1m, b)
#                                 x2m, y2m = max(x2m, c), max(y2m, d)
#                 return [x1m, y1m, x2m, y2m]
#     if len(value_lower) >= 4:
#         for idx, wl in enumerate(ocr_lower):
#             if idx < len(boxes) and boxes[idx]:
#                 if value_lower in wl: return list(boxes[idx])
#                 if wl in value_lower and len(wl) >= 4: return list(boxes[idx])
#     return None


# def synthesize_bboxes_for_page(fields, ocr_data, img_w, img_h, page_idx):
#     if not ocr_data:
#         return fields
#     words = ocr_data.get("text", [])
#     boxes = ocr_data.get("boxes", [])
#     if not words or not boxes:
#         return fields

#     patched = {}
#     for fn, fd in fields.items():
#         if isinstance(fd, dict):
#             fd = fd.copy()
#             existing_bbox = fd.get("bbox")
#             existing_page = fd.get("page")
#             if existing_bbox is not None and existing_page is not None:
#                 patched[fn] = fd
#                 continue
#             val = fd.get("value", "")
#             if isinstance(val, str) and val.strip():
#                 bbox = _find_value_bbox(val, words, boxes)
#                 if bbox:
#                     fd["bbox"] = bbox
#                     fd["page"] = page_idx
#                 else:
#                     pass
#             patched[fn] = fd
#         else:
#             patched[fn] = fd
#     return patched


# # ============================================================
# # BBOX PIXEL CONVERSION
# # ============================================================
# def bbox_to_pixels(bbox, img_w, img_h):
#     x1, y1, x2, y2 = bbox
#     if all(0 <= c <= 1 for c in [x1, y1, x2, y2]):
#         x1, x2 = int(x1 * img_w), int(x2 * img_w)
#         y1, y2 = int(y1 * img_h), int(y2 * img_h)
#     elif all(0 <= c <= 1000 for c in [x1, y1, x2, y2]):
#         x1 = int((x1 / 1000) * img_w)
#         y1 = int((y1 / 1000) * img_h)
#         x2 = int((x2 / 1000) * img_w)
#         y2 = int((y2 / 1000) * img_h)
#     else:
#         x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
#     x1, x2 = max(0, min(x1, img_w)), max(0, min(x2, img_w))
#     y1, y2 = max(0, min(y1, img_h)), max(0, min(y2, img_h))
#     if x2 < x1:
#         x1, x2 = x2, x1
#     if y2 < y1:
#         y1, y2 = y2, y1
#     return x1, y1, x2, y2


# def page_matches(field_page, display_page_0based):
#     if field_page is None:
#         return True
#     return field_page == display_page_0based


# # ============================================================
# # BUILD BASE PREVIEW (WITH RESIZING FOR SPEED)
# # ============================================================
# def build_base_preview_for_page(png_bytes, fields, page_idx_0based):
#     img = cv2.imdecode(
#         np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR
#     )
#     if img is None:
#         return None
    
#     h, w = img.shape[:2]
#     scale = 1.0
#     if w > PREVIEW_MAX_WIDTH:
#         scale = PREVIEW_MAX_WIDTH / w
#         new_w = PREVIEW_MAX_WIDTH
#         new_h = int(h * scale)
#         img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
#         h, w = new_h, new_w

#     rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

#     if fields:
#         for fn, v in fields.items():
#             if not isinstance(v, dict):
#                 continue
#             bbox = v.get("bbox")
#             fp = v.get("page")
#             if not bbox or not page_matches(fp, page_idx_0based):
#                 continue
            
#             x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)
#             if x2 - x1 < 2 or y2 - y1 < 2:
#                 continue

#             dark_green = (0, 100, 0)
#             cv2.rectangle(rgb, (x1, y1), (x2, y2), dark_green, 1)

#             label = prettify(fn)
#             font = cv2.FONT_HERSHEY_SIMPLEX
#             f_scale = 0.4 
#             (tw, th_), _ = cv2.getTextSize(label, font, f_scale, 1)
#             ly = max(th_ + 4, y1 - 4)
#             cv2.rectangle(
#                 rgb, (x1, ly - th_ - 4), (x1 + tw + 4, ly), dark_green, -1
#             )
#             cv2.putText(
#                 rgb, label, (x1 + 2, ly - 2), font, f_scale, (255, 255, 255), 1
#             )
#     return rgb


# def get_or_build_base_preview(file_key, page_idx_0based, png_bytes, fields, fields_hash):
#     cache = st.session_state.get("base_preview_cache", {})
#     hash_cache = st.session_state.get("fields_hash_cache", {})
#     cache_key = f"{file_key}_p{page_idx_0based}"
#     old_hash = hash_cache.get(cache_key)

#     if cache_key in cache and old_hash == fields_hash:
#         return cache[cache_key]

#     base = build_base_preview_for_page(png_bytes, fields, page_idx_0based)
#     cache[cache_key] = base
#     hash_cache[cache_key] = fields_hash
#     st.session_state["base_preview_cache"] = cache
#     st.session_state["fields_hash_cache"] = hash_cache
#     st.session_state["highlight_preview_cache"] = {} 
#     return base


# def get_cached_highlight_image(file_key, base_rgb, fields, selected_field, page_idx_0based):
#     if not selected_field:
#         return base_rgb
#     cache_key = f"{file_key}_{page_idx_0based}_{selected_field}"
#     h_cache = st.session_state.get("highlight_preview_cache", {})
#     if cache_key in h_cache:
#         return h_cache[cache_key]
    
#     v = fields.get(selected_field)
#     if not isinstance(v, dict):
#         return base_rgb
#     bbox = v.get("bbox")
#     fp = v.get("page")
#     if not bbox or not page_matches(fp, page_idx_0based):
#         return base_rgb

#     img = base_rgb.copy()
#     h, w = img.shape[:2]
#     x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)

#     if x2 - x1 < 2 or y2 - y1 < 2:
#         return base_rgb

#     cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 3)
#     label = f">> {prettify(selected_field)} <<"
#     font = cv2.FONT_HERSHEY_SIMPLEX
#     f_scale = 0.6
#     (tw, th_), _ = cv2.getTextSize(label, font, f_scale, 2)
#     ly = max(th_ + 6, y1 - 6)
#     cv2.rectangle(img, (x1, ly - th_ - 6), (x1 + tw + 8, ly + 2), (255, 0, 0), -1)
#     cv2.putText(img, label, (x1 + 4, ly - 2), font, f_scale, (255, 255, 255), 2)

#     h_cache[cache_key] = img
#     st.session_state["highlight_preview_cache"] = h_cache
#     return img


# # ============================================================
# # CACHED PAGE DECODING
# # ============================================================
# @st.cache_data(show_spinner=False)
# def decode_pages(file_bytes, file_type):
#     pages = load_input(file_bytes, file_type)
#     if not pages:
#         return []
#     page_data = []
#     for p in pages:
#         success, buf = cv2.imencode(".png", p)
#         if success:
#             page_data.append(buf.tobytes())
#     return page_data


# # ============================================================
# # FIELD SELECTION CALLBACKS
# # ============================================================
# def on_field_click(field_name):
#     current = st.session_state.get("selected_field")
#     if current == field_name:
#         st.session_state["selected_field"] = None
#     else:
#         st.session_state["selected_field"] = field_name


# def clear_selection():
#     st.session_state["selected_field"] = None


# # ============================================================
# # CHECK BBOX HELPER
# # ============================================================
# def field_has_bbox(field_name: str, fields_with_bbox: dict) -> bool:
#     orig = fields_with_bbox.get(field_name, {})
#     return (
#         isinstance(orig, dict)
#         and orig.get("bbox") is not None
#         and isinstance(orig.get("bbox"), (list, tuple))
#         and len(orig.get("bbox", [])) == 4
#     )


# def field_page_number(field_name: str, fields_with_bbox: dict) -> int:
#     orig = fields_with_bbox.get(field_name, {})
#     if isinstance(orig, dict):
#         p = orig.get("page")
#         if p is not None:
#             return p
#     return -1


# # ============================================================
# # CLICKABLE FIELDS
# # ============================================================
# def render_clickable_fields(seg, fields_with_bbox, file_name, num_pages):
#     fields = seg.get("fields", {})
#     if not fields:
#         st.info("No fields extracted")
#         return

#     doc_type = seg.get("document_type", "OTH")
#     policy_type = seg.get("policy_type", "OTH")
#     allowed = get_allowed_fields(doc_type, policy_type)
#     selected = st.session_state.get("selected_field")

#     total_visible = 0
#     total_with_bbox = 0
#     for k, v in fields.items():
#         if allowed and k not in allowed:
#             continue
#         val = v.get("value") if isinstance(v, dict) else v
#         if not val:
#             continue
#         total_visible += 1
#         if field_has_bbox(k, fields_with_bbox):
#             total_with_bbox += 1

#     st.markdown(
#         f'<div style="font-size:0.82em; color:#888; margin-bottom:4px; '
#         f'padding:8px; background:rgba(255,255,255,0.02); border-radius:6px;">'
#         f'👆 <b>Click any field</b> to highlight on preview<br>'
#         f'<span style="color:#4caf50;">●</span> Located '
#         f'({total_with_bbox}/{total_visible}) &nbsp;&nbsp; '
#         f'<span style="color:#ff9800;">●</span> Not located '
#         f'({total_visible - total_with_bbox}/{total_visible})'
#         f'</div>',
#         unsafe_allow_html=True,
#     )

#     if selected:
#         st.button("✖ Clear selection", key=f"clr_{file_name}", on_click=clear_selection)

#     if selected and not field_has_bbox(selected, fields_with_bbox):
#         st.warning(f"⚠️ **{prettify(selected)}** was extracted but its position could not be located on the document.")

#     for k, v in fields.items():
#         if allowed and k not in allowed: continue
#         val = v.get("value") if isinstance(v, dict) else v
#         if not val: continue

#         has_bbox = field_has_bbox(k, fields_with_bbox)
#         is_active = k == selected
        
#         display_val = str(val)
#         if len(display_val) > 45: display_val = display_val[:45] + "…"

#         if is_active and has_bbox: icon = "🔴"
#         elif is_active and not has_bbox: icon = "🟠"
#         elif has_bbox: icon = "🟢"
#         else: icon = "🟡"

#         label = f"{icon} {prettify(k)}: {display_val}"
#         st.button(label, key=f"fb_{file_name}_{k}", use_container_width=True, on_click=on_field_click, args=(k,))


# # ============================================================
# # CLICKABLE SUMMARY
# # ============================================================
# def render_clickable_summary(seg, fields_with_bbox, file_name, num_pages):
#     fields = seg.get("fields", {})
#     doc_type = seg.get("document_type", "OTH")
#     policy_type = seg.get("policy_type", "OTH")
#     required = get_allowed_fields(doc_type, policy_type)
#     if not required: required = set(fields.keys())
#     selected = st.session_state.get("selected_field")
#     perfect, partial, failed = [], [], []
#     for fn in sorted(required):
#         data = fields.get(fn)
#         value = data.get("value") if isinstance(data, dict) else None
#         if not value: failed.append(fn)
#         elif isinstance(value, str) and not value.strip(): partial.append(fn)
#         else: perfect.append(fn)

#     st.markdown("### 📊 Extraction Summary")
#     c1, c2, c3 = st.columns(3)
#     c1.metric("✅ Perfect", len(perfect))
#     c2.metric("🟡 Partial", len(partial))
#     c3.metric("🔴 Failed", len(failed))
#     total = len(perfect) + len(partial) + len(failed)
#     st.progress((len(perfect) + 0.5 * len(partial)) / total if total else 0)

#     if selected:
#         st.button("✖ Clear highlight", key=f"clrs_{file_name}", on_click=clear_selection)
#     if selected and not field_has_bbox(selected, fields_with_bbox):
#         st.warning(f"⚠️ **{prettify(selected)}** – position not found")

#     st.markdown('<div style="font-size:0.82em; color:#888; margin-bottom:6px;">👆 Click any field to highlight on preview</div>', unsafe_allow_html=True)
#     left, right = st.columns([1.2, 1])

#     with left:
#         for category, items, base_icon in [("p", perfect, "🟢"), ("y", partial, "🟡")]:
#             for fn in items:
#                 has_bbox = field_has_bbox(fn, fields_with_bbox)
#                 is_active = fn == selected
#                 if is_active: icon = "🔴" if has_bbox else "🟠"
#                 elif has_bbox: icon = base_icon
#                 else: icon = "🟡"
#                 badge = " 📍" if has_bbox else " ⚠️"
#                 label = f"{icon} {prettify(fn)}{badge}"
#                 st.button(label, key=f"s{category}_{file_name}_{fn}", use_container_width=True, on_click=on_field_click, args=(fn,))

#         for fn in failed:
#             has_bbox = field_has_bbox(fn, fields_with_bbox)
#             is_active = fn == selected
#             if has_bbox:
#                 icon = "🔴" if is_active else "🔴"
#                 st.button(f"{icon} {prettify(fn)} 📍", key=f"sf_{file_name}_{fn}", use_container_width=True, on_click=on_field_click, args=(fn,))
#             else:
#                 st.markdown(f"🔴 {prettify(fn)} — not extracted")

#     with right:
#         if total:
#             fig, ax = plt.subplots(figsize=(4, 4))
#             ax.pie([len(perfect), len(partial), len(failed)], labels=["Perfect", "Partial", "Failed"], colors=["#4caf50", "#ff9800", "#f44336"], autopct="%1.0f%%", startangle=90)
#             ax.axis("equal")
#             st.pyplot(fig)
#         else:
#             st.info("No fields to display")


# # ============================================================
# # FIELD LIMITATION REASON
# # ============================================================
# def build_field_limitation_reason(document_type, policy_type):
#     allowed_set = get_allowed_fields(document_type, policy_type)
#     allowed = sorted(allowed_set)
#     policy_fields = POLICY_FIELD_RULES.get(policy_type, set())
#     scope = ("Document + Policy rules" if policy_fields else "Document rules")
#     text = (f"Based on {scope}\n\n" f"Document Type: {document_type}\n" f"{'Policy Type: ' + policy_type + chr(10) if policy_fields else ''}" f"Allowed fields ({len(allowed)}):\n" + " • ".join(prettify(f) for f in allowed))
#     return html.escape(text).replace("\n", "&#10;")


# # ============================================================
# # HEADER
# # ============================================================
# h1, h2 = st.columns([8, 1])
# with h1:
#     st.markdown("## Dynamic OCR – Intelligent Cascading Hybrid")
# with h2:
#     if st.session_state.get("uploaded") and st.button("⬅ Back"):
#         reset_to_home()
#         st.rerun()

# st.markdown("---")


# # ============================================================
# # UPLOAD
# # ============================================================
# if not st.session_state.get("uploaded", False):
#     # Dynamic key ensures uploader clears when key increments
#     ukey = st.session_state.get("uploader_key", 0)
#     uploaded = st.file_uploader(
#         "Upload documents", 
#         list(ALLOWED_EXT), 
#         accept_multiple_files=True,
#         key=f"uploader_{ukey}" 
#     )
#     if uploaded:
#         st.session_state.files = expand_uploaded_files(uploaded)
#         st.session_state.uploaded = True
#         st.rerun()
#     st.stop()


# # ============================================================
# # PROCESS FILES
# # ============================================================
# # If "Back" was clicked, reset_to_home cleared st.session_state.files
# # So this loop will not run, effectively stopping processing.
# for f in st.session_state.files:

#     file_key = f"result_{f.name}"
#     file_bytes = f.getvalue()

#     page_png_list = decode_pages(file_bytes, f.type)
#     if not page_png_list:
#         continue

#     num_pages = len(page_png_list)

#     # Decode to numpy only when needed for pipeline
#     if file_key not in st.session_state.get("pipeline_results", {}):
#         pages = []
#         for pb in page_png_list:
#             arr = cv2.imdecode(
#                 np.frombuffer(pb, np.uint8), cv2.IMREAD_COLOR
#             )
#             if arr is not None:
#                 pages.append(arr)
#         if not pages:
#             continue

#         with st.spinner("⏳ Processing document..."):
#             start = time.time()

#             from agents.vision_agent import VisionAgent
#             vision = VisionAgent(use_layoutxlm=True)
#             ocr_data_by_page = {}

#             for page_idx, img in enumerate(pages):
#                 try:
#                     ocr = vision.ocr_engine.run_with_boxes(img)
#                     pk = f"{f.name}_page_{page_idx}"
#                     ocr_data_by_page[pk] = ocr
#                     print(f"OCR page {page_idx}: {len(ocr.get('text',[]))} words")
#                 except Exception as e:
#                     print(f"OCR failed page {page_idx}: {e}")

#             st.session_state["ocr_data_by_page"].update(ocr_data_by_page)

#             results = run_pipeline_batch(pages)
#             result = merge_page_results(results)
#             enriched = result["fields"]

#             for pi, img in enumerate(pages):
#                 pk = f"{f.name}_page_{pi}"
#                 ocr = ocr_data_by_page.get(pk)
#                 if ocr:
#                     hh, ww = img.shape[:2]
#                     enriched = synthesize_bboxes_for_page(enriched, ocr, ww, hh, pi)

#             enriched = ensure_fields_have_page(enriched, default_page=0)
#             result["fields"] = enriched

#             seg = {
#                 "fields": strip_bbox(enriched),
#                 "document_type": result.get("document_type", "OTH"),
#                 "policy_type": result.get("policy_type", "OTH"),
#             }

#             st.session_state["latest_fields"] = enriched
#             st.session_state["processed"] = True
#             elapsed = time.time() - start

#             if "pipeline_results" not in st.session_state:
#                 st.session_state["pipeline_results"] = {}
#             st.session_state["pipeline_results"][file_key] = {
#                 "result": result,
#                 "seg": seg,
#                 "elapsed": elapsed,
#             }

#             st.rerun()

#     # ========================================================
#     # RENDER
#     # ========================================================
#     cached = st.session_state.get("pipeline_results", {}).get(file_key)
#     if not cached:
#         continue

#     result = cached["result"]
#     seg = cached["seg"]
#     elapsed = cached["elapsed"]
#     fields_with_bbox = result["fields"]
#     selected_field = st.session_state.get("selected_field")
#     f_hash = _hash_fields(fields_with_bbox)

#     col_img, col_out = st.columns([1, 1], gap="large")

#     # ---- PREVIEW ----
#     with col_img:
#         st.markdown("### 📄 Document Preview")

#         if selected_field:
#             has_bb = field_has_bbox(selected_field, fields_with_bbox)
#             sel_page = field_page_number(selected_field, fields_with_bbox)
#             if has_bb:
#                 pg_label = f" (Page {sel_page + 1})" if num_pages > 1 else ""
#                 st.success(f"🔴 Highlighting: **{prettify(selected_field)}**{pg_label}")
#             else:
#                 st.warning(f"⚠️ **{prettify(selected_field)}** – position not found on document")

#         for i, png_bytes in enumerate(page_png_list):
#             base_rgb = get_or_build_base_preview(file_key, i, png_bytes, fields_with_bbox, f_hash)
#             if base_rgb is None: continue

#             if selected_field and \
#                field_has_bbox(selected_field, fields_with_bbox) and \
#                page_matches(field_page_number(selected_field, fields_with_bbox), i):
#                 display_rgb = get_cached_highlight_image(file_key, base_rgb, fields_with_bbox, selected_field, i)
#             else:
#                 display_rgb = base_rgb

#             st.image(display_rgb, caption=f"Page {i + 1}", use_container_width=True)
#             if i < len(page_png_list) - 1: st.markdown("---")

#     # ---- RESULTS ----
#     with col_out:
#         m1, m2, m3 = st.columns(3)
#         m1.metric("📄 Pages", result["page_count"])
#         m2.metric("🎯 Accuracy (%)", f"{result['confidence'] * 100:.2f}")
#         m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

#         c1, c2 = st.columns([1, 1])
#         with c1:
#             st.markdown(f"**📄 Document Type:** `{seg['document_type']}` <span title='{get_document_explanation(seg['document_type'])}'>ℹ️</span>", unsafe_allow_html=True)
#         with c2:
#             st.markdown(f"**🔐 Policy Type:** `{seg['policy_type']}` <span title='{get_policy_explanation(seg['policy_type'])}'>ℹ️</span>", unsafe_allow_html=True)

#         _allowed = get_allowed_fields(seg["document_type"], seg["policy_type"])
#         _allowed_count = (len(_allowed) if _allowed else len(seg["fields"]))

#         with st.expander(f"Why only {_allowed_count} fields? ℹ️"):
#             st.markdown(build_field_limitation_reason(seg["document_type"], seg["policy_type"]), unsafe_allow_html=True)

#         tab1, tab2, tab3 = st.tabs(["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"])
#         with tab1: render_clickable_fields(seg, fields_with_bbox, f.name, num_pages)
#         with tab2: render_clickable_summary(seg, fields_with_bbox, f.name, num_pages)
#         with tab3: st.text_area("OCR Output", "\n".join(result["raw_lines"]), height=500, key=f"ocr_{f.name}")

# st.caption("")


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
# CSS FIX
# ============================================================
st.markdown("""
    <style>
    div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding-left: 1rem !important;
    }
    img {
        transition: none !important;
        -webkit-transition: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE DEFAULTS
# ============================================================
_DEFAULTS = {
    "uploaded": False,
    "processed": False,
    "files": [],
    "pipeline_results": {},
    "ocr_cache": {}, # Store OCR coordinates separately
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
# PERFORMANCE CACHING (CRITICAL FOR SPEED)
# ============================================================
@st.cache_resource(show_spinner="Loading AI Models...")
def load_vision_agent():
    """
    Loads the heavy AI model ONCE. 
    Using cache_resource prevents the 300s reload time on every interaction.
    """
    from agents.vision_agent import VisionAgent
    # Initialize the model once and keep it in memory
    return VisionAgent(use_layoutxlm=True)

@st.cache_data(show_spinner=False)
def decode_pages(file_bytes, file_type):
    pages = load_input(file_bytes, file_type)
    if not pages: return []
    page_data = []
    for p in pages:
        success, buf = cv2.imencode(".png", p)
        if success: page_data.append(buf.tobytes())
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
            v.pop("bbox", None); v.pop("page", None)
        clean[k] = v
    return clean

def ensure_fields_have_page(fields: dict, default_page: int = 0) -> dict:
    patched = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            v = v.copy()
            if v.get("page") is None: v["page"] = default_page
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
def _normalize_text(text: str) -> str: return re.sub(r'[^\w\s]', '', text.strip().lower())
def _tokenize_value(value: str) -> list: return [t.lower() for t in re.split(r'[\s,]+', value.strip()) if t]

def _find_value_bbox(value: str, words: list, boxes: list) -> list:
    if not value or not words: return None
    value_clean = value.strip()
    if not value_clean: return None
    ocr_words = [w.strip() if w else "" for w in words]
    ocr_lower = [w.lower() for w in ocr_words]
    value_lower = value_clean.lower()
    
    # Strategy 1: Exact Match
    for idx, wl in enumerate(ocr_lower):
        if wl == value_lower and idx < len(boxes) and boxes[idx]: return list(boxes[idx])
    
    # Strategy 2: Anchor Substring
    if len(value_lower) >= 4:
        for idx, wl in enumerate(ocr_lower):
            if idx < len(boxes) and boxes[idx] and (value_lower in wl or (wl in value_lower and len(wl) >= 4)):
                return list(boxes[idx])
    return None

def synthesize_bboxes_for_page(fields, ocr_data, img_w, img_h, page_idx):
    """
    Maps extracted values back to coordinates using the explicit OCR data.
    """
    if not ocr_data: return fields
    words, boxes = ocr_data.get("text", []), ocr_data.get("boxes", [])
    if not words or not boxes: return fields
    
    patched = {}
    for fn, fd in fields.items():
        if isinstance(fd, dict):
            fd = fd.copy()
            # If missing coordinates, try to find them
            if fd.get("bbox") is None or fd.get("page") is None:
                val = fd.get("value", "")
                if isinstance(val, str) and val.strip():
                    bbox = _find_value_bbox(val, words, boxes)
                    if bbox: 
                        fd["bbox"] = bbox; fd["page"] = page_idx
            patched[fn] = fd
        else: patched[fn] = fd
    return patched

def bbox_to_pixels(bbox, img_w, img_h):
    x1, y1, x2, y2 = bbox
    # Handle normalized (0-1) vs absolute vs 1000-scale
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
# IMAGE PREVIEW BUILDERS
# ============================================================
def build_base_preview_for_page(png_bytes, fields, page_idx_0based):
    img = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None: return None
    h, w = img.shape[:2]
    if w > PREVIEW_MAX_WIDTH:
        scale = PREVIEW_MAX_WIDTH / w
        img = cv2.resize(img, (PREVIEW_MAX_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2] 
    
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Draw Green Boxes
    if fields:
        for fn, v in fields.items():
            if not isinstance(v, dict): continue
            bbox, fp = v.get("bbox"), v.get("page")
            if not bbox or not page_matches(fp, page_idx_0based): continue
            x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)
            if x2-x1<2 or y2-y1<2: continue
            
            dark_green = (0, 100, 0)
            cv2.rectangle(rgb, (x1, y1), (x2, y2), dark_green, 1)
            # Labels can be added here if needed
    return rgb

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

def get_cached_highlight_image(file_key, base_rgb, fields, selected_field, page_idx_0based):
    if not selected_field: return base_rgb
    cache_key = f"{file_key}_{page_idx_0based}_{selected_field}"
    h_cache = st.session_state.get("highlight_preview_cache", {})
    if cache_key in h_cache: return h_cache[cache_key]
    
    v = fields.get(selected_field)
    if not isinstance(v, dict): return base_rgb
    bbox, fp = v.get("bbox"), v.get("page")
    if not bbox or not page_matches(fp, page_idx_0based): return base_rgb
    
    img = base_rgb.copy()
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox_to_pixels(bbox, w, h)
    if x2-x1<2 or y2-y1<2: return base_rgb
    
    # Red Highlight
    cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 3)
    label = f">> {prettify(selected_field)} <<"
    font, f_scale = cv2.FONT_HERSHEY_SIMPLEX, 0.6
    (tw, th_), _ = cv2.getTextSize(label, font, f_scale, 2)
    ly = max(th_ + 6, y1 - 6)
    cv2.rectangle(img, (x1, ly - th_ - 6), (x1 + tw + 8, ly + 2), (255, 0, 0), -1)
    cv2.putText(img, label, (x1 + 4, ly - 2), font, f_scale, (255, 255, 255), 2)
    
    h_cache[cache_key] = img
    st.session_state["highlight_preview_cache"] = h_cache
    return img

# ============================================================
# UI COMPONENTS
# ============================================================
def on_field_click(field_name):
    curr = st.session_state.get("selected_field")
    st.session_state["selected_field"] = None if curr == field_name else field_name

def clear_selection(): st.session_state["selected_field"] = None

def field_has_bbox(field_name, fields_with_bbox):
    orig = fields_with_bbox.get(field_name, {})
    return isinstance(orig, dict) and orig.get("bbox") and len(orig.get("bbox", [])) == 4

def field_page_number(field_name, fields_with_bbox):
    orig = fields_with_bbox.get(field_name, {})
    return orig.get("page", -1) if isinstance(orig, dict) else -1

def render_clickable_fields(seg, fields_with_bbox, file_name, num_pages):
    fields = seg.get("fields", {})
    if not fields: st.info("No fields extracted"); return
    doc_type, policy_type = seg.get("document_type", "OTH"), seg.get("policy_type", "OTH")
    allowed = get_allowed_fields(doc_type, policy_type)
    selected = st.session_state.get("selected_field")
    
    total_visible = sum(1 for k in fields if (not allowed or k in allowed) and fields[k].get("value"))
    total_bbox = sum(1 for k in fields if (not allowed or k in allowed) and fields[k].get("value") and field_has_bbox(k, fields_with_bbox))
    
    st.markdown(f'<div style="font-size:0.82em; color:#888; margin-bottom:4px; padding:8px; background:rgba(255,255,255,0.02); border-radius:6px;">👆 <b>Click any field</b> to highlight<br><span style="color:#4caf50;">●</span> Located ({total_bbox}/{total_visible}) <span style="color:#ff9800;">●</span> Not located ({total_visible - total_bbox}/{total_visible})</div>', unsafe_allow_html=True)
    if selected: st.button("✖ Clear selection", key=f"clr_{file_name}", on_click=clear_selection)
    
    for k, v in fields.items():
        if allowed and k not in allowed: continue
        val = v.get("value") if isinstance(v, dict) else v
        if not val: continue
        has_bbox = field_has_bbox(k, fields_with_bbox)
        is_active = (k == selected)
        icon = "🔴" if is_active and has_bbox else ("🟠" if is_active else ("🟢" if has_bbox else "🟡"))
        display_val = str(val)[:45] + "…" if len(str(val)) > 45 else str(val)
        st.button(f"{icon} {prettify(k)}: {display_val}", key=f"fb_{file_name}_{k}", use_container_width=True, on_click=on_field_click, args=(k,))

def render_clickable_summary(seg, fields_with_bbox, file_name, num_pages):
    fields = seg.get("fields", {})
    doc_type, policy_type = seg.get("document_type", "OTH"), seg.get("policy_type", "OTH")
    required = get_allowed_fields(doc_type, policy_type)
    if not required: required = set(fields.keys())
    selected = st.session_state.get("selected_field")
    
    perfect, partial, failed = [], [], []
    for fn in sorted(required):
        val = fields.get(fn, {}).get("value")
        if not val: failed.append(fn)
        elif not str(val).strip(): partial.append(fn)
        else: perfect.append(fn)
    
    st.markdown("### 📊 Extraction Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Perfect", len(perfect)); c2.metric("🟡 Partial", len(partial)); c3.metric("🔴 Failed", len(failed))
    
    if selected: st.button("✖ Clear highlight", key=f"clrs_{file_name}", on_click=clear_selection)
    
    l, r = st.columns([1.2, 1])
    with l:
        for cat, items, icon_base in [("p", perfect, "🟢"), ("y", partial, "🟡")]:
            for fn in items:
                has_bbox = field_has_bbox(fn, fields_with_bbox)
                icon = "🔴" if fn == selected and has_bbox else ("🟠" if fn == selected else (icon_base if has_bbox else "🟡"))
                badge = " " if has_bbox else " ⚠️"
                st.button(f"{icon} {prettify(fn)}{badge}", key=f"s{cat}_{file_name}_{fn}", use_container_width=True, on_click=on_field_click, args=(fn,))
        for fn in failed:
            if field_has_bbox(fn, fields_with_bbox):
                st.button(f"🔴 {prettify(fn)} ", key=f"sf_{file_name}_{fn}", use_container_width=True, on_click=on_field_click, args=(fn,))
            else:
                st.markdown(f"🔴 {prettify(fn)} — not extracted")
    with r:
        if (len(perfect)+len(partial)+len(failed)) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            fig.patch.set_alpha(0)
            ax.pie([len(perfect), len(partial), len(failed)], labels=["Perfect", "Partial", "Failed"], colors=["#4caf50", "#ff9800", "#f44336"], autopct="%1.0f%%", startangle=90)
            ax.axis("equal")
            st.pyplot(fig)

def build_field_limitation_reason(document_type, policy_type):
    allowed = sorted(get_allowed_fields(document_type, policy_type))
    list_str = " • ".join(prettify(f) for f in allowed)
    return html.escape(f"Document Type: {document_type}\nPolicy Type: {policy_type}\nAllowed ({len(allowed)}):\n{list_str}").replace("\n", "&#10;")

# ============================================================
# MAIN LAYOUT
# ============================================================
h1, h2 = st.columns([8, 1])
with h1: st.markdown("## Dynamic OCR – Intelligent Cascading Hybrid")
with h2:
    if st.session_state.get("uploaded") and st.button("⬅ Back"):
        reset_to_home()
        st.rerun()
st.markdown("---")

# UPLOAD
if not st.session_state.get("uploaded", False):
    ukey = st.session_state.get("uploader_key", 0)
    uploaded = st.file_uploader("Upload documents", list(ALLOWED_EXT), accept_multiple_files=True, key=f"uploader_{ukey}")
    if uploaded:
        st.session_state.files = expand_uploaded_files(uploaded)
        st.session_state.uploaded = True
        st.rerun()
    st.stop()

# ============================================================
# EXECUTION
# ============================================================
for f in st.session_state.files:
    file_key = f"result_{f.name}"
    
    # 1. IMMEDIATE DECODE
    page_png_list = decode_pages(f.getvalue(), f.type)
    if not page_png_list: continue
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
                pg_label = f" (Page {pg+1})" if num_pages > 1 else ""
                st.success(f"🔴 Highlighting: **{prettify(selected_field)}**{pg_label}")
            else:
                st.warning(f"⚠️ **{prettify(selected_field)}** – position not found")

        for i, png_bytes in enumerate(page_png_list):
            base_rgb = get_or_build_base_preview(file_key, i, png_bytes, fields_with_bbox, f_hash)
            
            if selected_field and field_has_bbox(selected_field, fields_with_bbox) and \
               page_matches(field_page_number(selected_field, fields_with_bbox), i):
                display_rgb = get_cached_highlight_image(file_key, base_rgb, fields_with_bbox, selected_field, i)
            else:
                display_rgb = base_rgb
            
            st.image(display_rgb, caption=f"Page {i+1}", use_container_width=True)
            if i < num_pages - 1: st.markdown("---")

    # 4. RENDER RIGHT COLUMN (RESULTS)
    with col_out:
        result_container = st.empty()

        if processed_data:
            # CASE A: Render Results (Already processed)
            result = processed_data["result"]
            seg = processed_data["seg"]
            elapsed = processed_data["elapsed"]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("📄 Pages", result["page_count"])
            m2.metric("🎯 Accuracy (%)", f"{result['confidence']*100:.2f}")
            m3.metric("⚡ Time (s)", f"{elapsed:.2f}")

            c1, c2 = st.columns([1, 1])
            doc_expl = html.escape(get_document_explanation(seg['document_type']))
            pol_expl = html.escape(get_policy_explanation(seg['policy_type']))
            
            with c1: 
                st.markdown(f"**📄 Document Type:** `{seg['document_type']}` <span title=\"{doc_expl}\">ℹ️</span>", unsafe_allow_html=True)
            with c2: 
                st.markdown(f"**🔐 Policy Type:** `{seg['policy_type']}` <span title=\"{pol_expl}\">ℹ️</span>", unsafe_allow_html=True)

            _allowed = get_allowed_fields(seg["document_type"], seg["policy_type"])
            with st.expander(f"Why only {len(_allowed) if _allowed else len(seg['fields'])} fields? ℹ️"):
                st.markdown(build_field_limitation_reason(seg["document_type"], seg["policy_type"]), unsafe_allow_html=True)

            tab1, tab2, tab3 = st.tabs(["🧾 Extracted Fields", "📊 Extraction Summary", "📄 OCR Text"])
            
            with tab1:
                render_clickable_fields(seg, fields_with_bbox, f.name, num_pages)

            with tab2:
                render_clickable_summary(seg, fields_with_bbox, f.name, num_pages)

            with tab3:
                st.text_area("OCR Output", "\n".join(result["raw_lines"]), height=500, key=f"ocr_{f.name}")
        
        else:
            # CASE B: Process Now (Run Agent + Pipeline)
            with result_container.container():
                with st.spinner("⏳ Analyzing document (OCR + Extraction)..."):
                    start = time.time()
                    
                    # 1. Decode pages
                    pages = []
                    for pb in page_png_list:
                        arr = cv2.imdecode(np.frombuffer(pb, np.uint8), cv2.IMREAD_COLOR)
                        if arr is not None: pages.append(arr)
                    
                    # 2. RUN OCR AGENT (RESTORED - REQUIRED FOR COORDINATES)
                    # We use the cached agent to minimize load time
                    vision = load_vision_agent()
                    ocr_data_by_page = {}
                    
                    # We run this loop to get the BOXES that standard pipeline drops
                    for page_idx, img in enumerate(pages):
                        try:
                            ocr = vision.ocr_engine.run_with_boxes(img)
                            ocr_data_by_page[f"{f.name}_page_{page_idx}"] = ocr
                        except: pass
                    
                    # 3. RUN PIPELINE (For Extraction)
                    results = run_pipeline_batch(pages)
                    
                    # 4. MERGE DATA
                    result = merge_page_results(results)
                    enriched = result["fields"]

                    # 5. SYNTHESIZE BBOXES (Map values to coordinates found in Step 2)
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

                    # Store results
                    if "pipeline_results" not in st.session_state: st.session_state["pipeline_results"] = {}
                    st.session_state["pipeline_results"][file_key] = {
                        "result": result, "seg": seg, "elapsed": time.time() - start
                    }
                    
                    st.rerun()

st.caption("")