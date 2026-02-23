# # agents/vision_agent.py - MAXIMUM RECALL MODE
# # Proper OCR integration with PP-OCRv3 and LayoutXLM

# from PIL import Image
# import torch
# import numpy as np

# # ============================================================
# # VISION AGENT – INTELLIGENT CASCADING HYBRID
# # ============================================================
# class VisionAgent:
#     def __init__(self, use_layoutxlm=True):
#         """
#         Stage-aware Vision Agent
#         Stage 0 : PP-OCRv3
#         Stage 1 : Rule-based layout
#         Stage 2 : LayoutLMv3 (LAZY — loaded only when needed)
#         """
#         from api.ocr_engine import OCREngine
#         self.ocr_engine = OCREngine()
#         print("[VisionAgent] PP-OCRv3 loaded")

#         self.use_layoutxlm = use_layoutxlm
#         self.processor = None
#         self.model = None
#         self._layoutlm_load_attempted = False

#     def _ensure_layoutlm(self):
#         """Lazy-load LayoutLMv3 only when first needed."""
#         if self._layoutlm_load_attempted:
#             return self.model is not None
#         self._layoutlm_load_attempted = True
#         try:
#             from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
#             self.processor = LayoutLMv3Processor.from_pretrained(
#                 "microsoft/layoutlmv3-base",
#                 apply_ocr=False
#             )
#             self.model = LayoutLMv3ForTokenClassification.from_pretrained(
#                 "microsoft/layoutlmv3-base"
#             )
#             self.model.eval()
#             print("[VisionAgent] LayoutLMv3 loaded (lazy)")
#             return True
#         except Exception as e:
#             print(f"[VisionAgent] LayoutLMv3 unavailable: {e}")
#             self.use_layoutxlm = False
#             return False

#     # --------------------------------------------------------
#     # STAGE 0 – OCR (STANDARD)
#     # --------------------------------------------------------
#     def run_vision(self, image):
#         return self.ocr_engine.run(image)

#     # --------------------------------------------------------
#     # NEW: RAW OCR OUTPUT (100% UNFILTERED)
#     # --------------------------------------------------------
#     def run_vision_raw(self, image):
#         """
#         Return 100% raw OCR text with NO filtering.
#         Use this for debugging missing text.
#         """
#         try:
#             ocr_results = self.ocr_engine.run_with_boxes(image)
            
#             # Return EVERYTHING - no filtering
#             all_text = []
#             for word, box, conf in zip(
#                 ocr_results.get("text", []),
#                 ocr_results.get("boxes", []),
#                 ocr_results.get("confidences", [])
#             ):
#                 all_text.append({
#                     "text": word,
#                     "box": box,
#                     "confidence": conf,
#                     "raw": True  # Flag to indicate unfiltered
#                 })
            
#             print(f"[VisionAgent] Raw OCR extracted {len(all_text)} items")
#             return all_text
            
#         except Exception as e:
#             print(f"[VisionAgent] Raw OCR failed: {e}")
#             return []

#     # --------------------------------------------------------
#     # NEW: EXPORT RAW OCR TO TEXT FILE
#     # --------------------------------------------------------
#     def export_raw_ocr(self, image, output_path="full_ocr_output.txt"):
#         """
#         Export 100% raw OCR to text file for debugging.
#         """
#         raw_ocr = self.run_vision_raw(image)
        
#         try:
#             with open(output_path, "w", encoding="utf-8") as f:
#                 f.write("=" * 80 + "\n")
#                 f.write("COMPLETE RAW OCR OUTPUT (100% UNFILTERED)\n")
#                 f.write("=" * 80 + "\n\n")
                
#                 for idx, item in enumerate(raw_ocr):
#                     f.write(f"{idx:4d} | {item['confidence']:.3f} | {item['text']}\n")
                
#                 f.write("\n" + "=" * 80 + "\n")
#                 f.write(f"TOTAL LINES: {len(raw_ocr)}\n")
#                 f.write("=" * 80 + "\n")
            
#             print(f"[VisionAgent] Raw OCR exported to {output_path}")
#             return output_path
            
#         except Exception as e:
#             print(f"[VisionAgent] Export failed: {e}")
#             return None

#     # --------------------------------------------------------
#     # INTELLIGENT CASCADING LAYOUT ANALYSIS
#     # --------------------------------------------------------
#     def analyze_layout(self, image, ocr_results=None):
#         """
#         INTELLIGENT CASCADE:
#         1. OCR
#         2. Rule-based layout
#         3. LayoutLMv3 ONLY if ambiguity detected
#         """

#         if ocr_results is None:
#             try:
#                 ocr_results = self.ocr_engine.run_with_boxes(image)
#             except Exception as e:
#                 print(f"[VisionAgent] OCR failed: {e}")
#                 return []

#         if not ocr_results.get("text"):
#             return []

#         # ---------- STAGE 1: RULE-BASED (FAST, FREE) ----------
#         basic_layout = self._basic_layout_analysis(image, ocr_results)

#         if not self.use_layoutxlm:
#             return basic_layout

#         # ---------- DECISION: SHOULD WE RUN LAYOUTLM? ----------
#         if not self._needs_semantic_layout(basic_layout):
#             return basic_layout

#         # ---------- STAGE 2: LAYOUTLMv3 (EXPENSIVE, LAZY-LOADED) ----------
#         if not self._ensure_layoutlm():
#             return basic_layout
#         try:
#             return self._layoutlm_analysis(image, ocr_results)
#         except Exception as e:
#             print(f"[VisionAgent] LayoutLM failed: {e}")
#             return basic_layout

#     # --------------------------------------------------------
#     # DECISION LOGIC (CRITICAL)
#     # --------------------------------------------------------
#     def _needs_semantic_layout(self, layout_elements):
#         """
#         Run LayoutLM ONLY if:
#         - Labels exist without nearby values
#         - Dense table-like structure


#         """

#         labels = [e for e in layout_elements if e["element_type"] == "label"]
#         values = [e for e in layout_elements if e["element_type"] == "value"]


#         if not labels or not values:
#             return False

#         # Too many labels with no values → ambiguity
#         orphan_labels = 0

#         for lbl in labels:
#             lx0, ly0, lx1, ly1 = lbl["box"]
#             matched = False

#             for val in values:
#                 vx0, vy0, vx1, vy1 = val["box"]
#                 if vx0 > lx1 and abs(vy0 - ly0) < 40:


#                     matched = True
#                     break

#             if not matched:
#                 orphan_labels += 1

#         return orphan_labels >= 2




#     # --------------------------------------------------------
#     # STAGE 2 – LAYOUTLMv3 (SAFE)
#     # --------------------------------------------------------
#     def _layoutlm_analysis(self, image, ocr_results):
#         if isinstance(image, np.ndarray):
#             image = Image.fromarray(image[:, :, ::-1])

#         encoding = self.processor(
#             image,
#             ocr_results["text"],
#             boxes=ocr_results["boxes"],
#             return_tensors="pt",
#             truncation=True,
#             padding="max_length",
#             max_length=512
#         )

#         with torch.no_grad():
#             logits = self.model(**encoding).logits

#         predictions = logits.argmax(-1)[0]
#         word_ids = encoding.word_ids(batch_index=0)

#         return self._parse_layout(predictions, word_ids, ocr_results)

#     # --------------------------------------------------------
#     # PARSE LAYOUTLM OUTPUT
#     # --------------------------------------------------------
#     def _parse_layout(self, predictions, word_ids, ocr_results):
#         label_map = {
#             0: "O",
#             1: "B-HEADER",
#             2: "I-HEADER",
#             3: "B-QUESTION",
#             4: "I-QUESTION",
#             5: "B-ANSWER",
#             6: "I-ANSWER",
#         }

#         seen = set()
#         layout_elements = []

#         for t_idx, w_idx in enumerate(word_ids):
#             if w_idx is None or w_idx in seen:
#                 continue
#             if w_idx >= len(ocr_results["text"]):
#                 continue

#             seen.add(w_idx)

#             label = label_map.get(predictions[t_idx].item(), "O")
#             word = ocr_results["text"][w_idx]
#             box = ocr_results["boxes"][w_idx]
#             conf = ocr_results["confidences"][w_idx]

#             if "HEADER" in label:
#                 etype = "header"
#             elif "QUESTION" in label:
#                 etype = "label"
#             elif "ANSWER" in label:
#                 etype = "value"
#             else:
#                 etype = "text"

#             layout_elements.append({
#                 "text": word,
#                 "box": box,
#                 "element_type": etype,
#                 "confidence": conf,
#                 "layoutlm_label": label
#             })

#         return layout_elements

#     # --------------------------------------------------------
#     # STAGE 1 – RULE-BASED LAYOUT (FALLBACK)
#     # --------------------------------------------------------
#     def _basic_layout_analysis(self, image, ocr_results):
#         elements = []

#         for word, box, conf in zip(
#             ocr_results["text"],
#             ocr_results["boxes"],
#             ocr_results["confidences"]
#         ):
#             word_clean = word.strip()
#             etype = "text"

#             if word_clean.endswith(":"):
#                 etype = "label"
#             elif word_clean.isupper() and box[1] < 200:
#                 etype = "header"
#             elif any(c.isdigit() for c in word_clean):
#                 etype = "value"

#             elements.append({
#                 "text": word,
#                 "box": box,
#                 "element_type": etype,
#                 "confidence": conf
#             })

#         return elements

#     # --------------------------------------------------------
#     # KEY–VALUE PAIR EXTRACTION
#     # --------------------------------------------------------
#     def extract_key_value_pairs(self, layout_elements):
#         pairs = []
#         labels = [e for e in layout_elements if e["element_type"] in ("label", "header")]
#         values = [e for e in layout_elements if e["element_type"] == "value"]

#         for lbl in labels:
#             lx0, ly0, lx1, ly1 = lbl["box"]
#             best, dist = None, 1e9

#             for val in values:
#                 vx0, vy0, vx1, vy1 = val["box"]
#                 if vx0 > lx1 and abs(vy0 - ly0) < 50:
#                     d = vx0 - lx1
#                 elif vy0 > ly1 and vy0 - ly1 < 120:
#                     d = vy0 - ly1
#                 else:
#                     continue

#                 if d < dist:
#                     dist = d
#                     best = val

#             if best:
#                 pairs.append((lbl["text"], best["text"]))

#         return pairs


# # ============================================================
# # BACKWARD-COMPATIBLE SINGLETON
# # ============================================================
# _agent = None

# def run_vision(image):
#     global _agent
#     if _agent is None:
#         _agent = VisionAgent(use_layoutxlm=False)
#     return _agent.run_vision(image)


# def run_vision_raw(image):
#     """
#     Global function for 100% raw OCR output.
#     """
#     global _agent
#     if _agent is None:
#         _agent = VisionAgent(use_layoutxlm=False)
#     return _agent.run_vision_raw(image)


# def export_raw_ocr(image, output_path="full_ocr_output.txt"):
#     """
#     Global function to export raw OCR to file.
#     """
#     global _agent
#     if _agent is None:
#         _agent = VisionAgent(use_layoutxlm=False)
#     return _agent.export_raw_ocr(image, output_path)


# # agents/vision_agent.py
# # DOCUMENT-AWARE LAYOUT RECONSTRUCTION ENGINE
# # Strategy: Line grouping → Section detection → Form pairing / Table grid alignment

# from PIL import Image
# import torch
# import numpy as np
# import re

# class VisionAgent:
#     def __init__(self, use_layoutxlm=True):
#         from api.ocr_engine import OCREngine
#         self.ocr_engine = OCREngine()
#         print("[VisionAgent] Document-Aware Layout Engine Loaded")

#         self.use_layoutxlm = use_layoutxlm
#         self.processor = None
#         self.model = None
#         self._layoutlm_load_attempted = False

#     # ============================================================
#     # STEP 1: GROUP RAW WORDS INTO LINES BY Y-COORDINATE
#     # ============================================================

#     def _group_into_lines(self, words, y_tolerance=12):
#         """
#         Groups word tuples into lines based on Y-coordinate proximity.
#         Returns list of lines, each line is a list of (text, box, conf) sorted left-to-right.
#         """
#         if not words:
#             return []

#         words.sort(key=lambda w: (w[1][1], w[1][0]))

#         lines = []
#         current_line = [words[0]]
#         current_y = words[0][1][1]

#         for w in words[1:]:
#             if abs(w[1][1] - current_y) <= y_tolerance:
#                 current_line.append(w)
#             else:
#                 current_line.sort(key=lambda x: x[1][0])
#                 lines.append(current_line)
#                 current_line = [w]
#                 current_y = w[1][1]

#         if current_line:
#             current_line.sort(key=lambda x: x[1][0])
#             lines.append(current_line)

#         return lines

#     # ============================================================
#     # STEP 2: FIND TABLE HEADER ROW
#     # ============================================================

#     def _find_table_header(self, lines):
#         """
#         Finds the 'Coverages | Limits | ... | Premiums' header line.
#         Returns (header_line_index, column_boundaries_dict) or (None, None).
#         """
#         for idx, line in enumerate(lines):
#             line_text_lower = " ".join(w[0].lower() for w in line)

#             if 'coverages' in line_text_lower and 'limits' in line_text_lower:
#                 col_bounds = {}
#                 for w in line:
#                     txt_l = w[0].lower()
#                     if 'coverages' in txt_l:
#                         col_bounds['coverages'] = w[1][0]
#                     elif 'applicable' in txt_l or 'deductible' in txt_l:
#                         col_bounds['deductibles'] = w[1][0]
#                     elif 'premium' in txt_l:
#                         col_bounds['premiums'] = w[1][0]
#                     elif 'limits' in txt_l:
#                         col_bounds['limits'] = w[1][0]
#                 return idx, col_bounds

#         return None, None

#     # ============================================================
#     # STEP 3: RENDER FORM SECTION (label:value pairing)
#     # ============================================================

#     def _render_form_section(self, lines):
#         """
#         Renders form/header area.
#         - Labels ending ':' with value on same line → "Label: Value"
#         - Labels ending ':' with value directly below → merge vertically
#         - Otherwise plain text line
#         """
#         output = []
#         skip_next = set()

#         for i, line in enumerate(lines):
#             if i in skip_next:
#                 continue

#             line_text = self._join_line_words(line)
#             stripped = line_text.strip()

#             # Check: standalone label ending with ':'
#             if stripped.endswith(':') and i + 1 < len(lines) and (i + 1) not in skip_next:
#                 next_line = lines[i + 1]
#                 next_text = self._join_line_words(next_line).strip()

#                 # Don't merge if next line is also a label
#                 if not next_text.endswith(':'):
#                     curr_x = line[0][1][0]
#                     next_x = next_line[0][1][0]
#                     curr_y_bot = max(w[1][3] for w in line)
#                     next_y_top = min(w[1][1] for w in next_line)

#                     vertically_close = (next_y_top - curr_y_bot) < 30
#                     left_aligned = abs(curr_x - next_x) < 40

#                     if vertically_close and left_aligned:
#                         output.append(f"{stripped} {next_text}")
#                         skip_next.add(i + 1)
#                         continue

#             output.append(line_text)

#         return output

#     def _join_line_words(self, line_words):
#         """Joins words in a line with gap-aware spacing."""
#         if not line_words:
#             return ""

#         parts = [line_words[0][0]]
#         last_x_end = line_words[0][1][2]

#         for w in line_words[1:]:
#             gap = w[1][0] - last_x_end
#             if gap > 100:
#                 parts.append("   ")
#             elif gap > 30:
#                 parts.append("  ")
#             else:
#                 parts.append(" ")
#             parts.append(w[0])
#             last_x_end = w[1][2]

#         return "".join(parts)

#     # ============================================================
#     # STEP 4: RENDER TABLE SECTION (grid-based column slotting)
#     # ============================================================

#     def _render_table_section(self, lines, col_bounds):
#         """
#         Slots each word into the correct column based on X-position
#         relative to the header boundaries.
#         """
#         output = []

#         cov_x = col_bounds.get('coverages', 0)
#         lim_x = col_bounds.get('limits', 400)
#         ded_x = col_bounds.get('deductibles', 600)
#         prem_x = col_bounds.get('premiums', 800)

#         # Emit header
#         output.append("Coverages | Limits | Applicable Deductibles | Premiums")

#         for line in lines[1:]:  # skip the header row itself
#             cols = [[], [], [], []]

#             for w in line:
#                 cx = (w[1][0] + w[1][2]) / 2

#                 if prem_x and cx >= prem_x - 20:
#                     cols[3].append(w[0])
#                 elif ded_x and cx >= ded_x - 20:
#                     cols[2].append(w[0])
#                 elif cx >= lim_x - 20:
#                     cols[1].append(w[0])
#                 else:
#                     cols[0].append(w[0])

#             c0 = " ".join(cols[0])
#             c1 = " ".join(cols[1])
#             c2 = " ".join(cols[2])
#             c3 = " ".join(cols[3])

#             row_text = f"{c0} {c1} {c2} {c3}".strip()
#             if row_text:
#                 parts = [c0]
#                 if c1: parts.append(c1)
#                 if c2: parts.append(c2)
#                 if c3: parts.append(c3)
#                 output.append(" ".join(parts))

#         return output

#     # ============================================================
#     # STEP 5: DETECT TABLE END
#     # ============================================================

#     def _find_table_end(self, table_lines):
#         """
#         Scans table lines to find where the coverage table ends.
#         Returns index within table_lines where non-table content starts.
#         """
#         end_markers = [
#             'mortgagee', 'policy number', 'total residence',
#             'form number', 'ed. date', 'biological irritants',
#             'medical expenses', 'scheduled personal',
#             'encompassone', 'your encompass agency',
#             'home protection', 'coverage detail for'
#         ]

#         for t_idx in range(1, len(table_lines)):
#             tline_text = " ".join(w[0] for w in table_lines[t_idx]).lower()
#             if any(marker in tline_text for marker in end_markers):
#                 return t_idx

#         return len(table_lines)

#     # ============================================================
#     # STEP 6: NOISE FILTERING
#     # ============================================================

#     def _filter_noise(self, lines):
#         """Remove OCR artifacts, duplicates, and junk."""
#         cleaned = []
#         seen = set()

#         noise_patterns = [
#             r'^\.?\s*ECECEs\s*$',
#             r'^\.?\s*SCCEPPET5\s*$',
#             r'^\.?\s*L03335\s*$',
#             r'^\d{13,}',
#             r'^1000[02].*0{4,}',
#             r'^2000[03].*\d{3}$',
#             r'^190415\d+',
#             r'^198415\d+',
#             r'^\.\s*$',
#             r'^f:\s*$',
#             r'^Creating protection around you',
#             r'^Page \d+ of \d+',
#             r'^Producer Code:',
#             r'^Short Code#',
#             r'^Office Use Space',
#             r'^Coverage applies only if',
#             r'^All references to .You.',
#             r'^\*?The Property Location Limit is the sum',
#             r'^individual limits of your',
#             r'^\.?Excludes misplacing',
#             r'^watches,?\s*stones',
#             r'^\(Your Total Limit',
#             r'^\(Refer to your Schedule',
#             r'^The coverages and limits shown',
#             r'^endorsements\.\s*$',
#             r'^The policy is subject to',
#             r'^See PLL deductibles',
#             r'^\.\s*See PLL',
#             r'^Per Endorsement\s*$',
#             r'^\(continued\)\s*$',
#         ]

#         for line in lines:
#             line = line.strip()
#             if not line:
#                 continue
#             if line in seen:
#                 continue

#             is_noise = False
#             for pattern in noise_patterns:
#                 if re.match(pattern, line, re.IGNORECASE):
#                     is_noise = True
#                     break

#             if not is_noise:
#                 cleaned.append(line)
#                 seen.add(line)

#         return cleaned

#     # ============================================================
#     # STEP 7: MAIN PIPELINE
#     # ============================================================

#     def run_vision(self, image):
#         try:
#             ocr_results = self.ocr_engine.run_with_boxes(image)
#         except Exception:
#             lines, _ = self.ocr_engine.run(image)
#             return "\n".join(lines)

#         if not ocr_results or not ocr_results.get("text"):
#             return ""

#         words = list(zip(
#             ocr_results["text"],
#             ocr_results["boxes"],
#             ocr_results["confidences"]
#         ))

#         # 1. Group words into lines by Y-coordinate
#         lines = self._group_into_lines(words)

#         # 2. Find all table headers (there may be multiple on multi-page docs)
#         output_lines = []
#         processed_up_to = 0

#         while processed_up_to < len(lines):
#             # Search for next table header from current position
#             remaining = lines[processed_up_to:]
#             header_idx, col_bounds = self._find_table_header(remaining)

#             if header_idx is not None:
#                 # Render form section before this table
#                 form_lines = remaining[:header_idx]
#                 if form_lines:
#                     output_lines.extend(self._render_form_section(form_lines))

#                 # Find where this table ends
#                 table_start = remaining[header_idx:]
#                 table_end = self._find_table_end(table_start)

#                 # Render the table
#                 table_output = self._render_table_section(table_start[:table_end], col_bounds)
#                 output_lines.extend(table_output)

#                 # Move cursor past the table
#                 processed_up_to += header_idx + table_end
#             else:
#                 # No more tables — render rest as form
#                 output_lines.extend(self._render_form_section(remaining))
#                 break

#         # 3. Filter noise
#         final_lines = self._filter_noise(output_lines)

#         return "\n".join(final_lines)

#     # ============================================================
#     # COMPATIBILITY
#     # ============================================================

#     def run_vision_raw(self, image):
#         try:
#             r = self.ocr_engine.run_with_boxes(image)
#             return [{"text": t, "box": b, "confidence": c}
#                     for t, b, c in zip(r["text"], r["boxes"], r["confidences"])]
#         except:
#             return []

#     def analyze_layout(self, image, ocr_results=None):
#         if ocr_results is None:
#             ocr_results = self.ocr_engine.run_with_boxes(image)
#         return [{"text": t, "box": b, "element_type": "text"}
#                 for t, b in zip(ocr_results["text"], ocr_results["boxes"])]


# # SINGLETON
# _agent = None

# def run_vision(image):
#     global _agent
#     if _agent is None:
#         _agent = VisionAgent(use_layoutxlm=False)
#     return _agent.run_vision(image)

# def run_vision_raw(image):
#     global _agent
#     if _agent is None:
#         _agent = VisionAgent(use_layoutxlm=False)
#     return _agent.run_vision_raw(image)

# agents/vision_agent.py
# ════════════════════════════════════════════════════════════════════
#  FULL PIPELINE
#  ┌──────────┐    ┌────────────────┐    ┌──────────────────────┐
#  │ PaddleOCR│───▶│ Table Detect + │───▶│ Document Structure   │
#  │ (words)  │    │ TSR  (cells)   │    │ Model (DiT/LayoutLM) │
#  └──────────┘    └────────────────┘    └──────────────────────┘
#        │                  │                       │
#        ▼                  ▼                       ▼
#  word+box list     HTML <table>          StructureBlock list
#                                    (title / header / kv / table / footnote)
#        └──────────────────┴───────────────────────┘
#                           │
#                    ┌──────┴──────┐
#                    │  Assembler  │
#                    └─────────────┘
#                     Markdown │ JSON │ HTML

# agents/vision_agent.py
# ════════════════════════════════════════════════════════════════════
#  PIPELINE:   OCR  →  Table Transformer (TD+TSR)  →  Structure Model (DiT)
#
#  1. PaddleOCR         → word + normalised-0-1000 boxes
#  2. Table Detection   → table bounding boxes on full page
#  3. TSR               → row / column / cell boxes inside each table
#  4. Cell-Word mapping → OCR words slotted into grid cells
#  5. DiT (DocLayNet)   → semantic block types for non-table areas
#  6. Assembly          → Markdown / HTML / JSON
#
#  CRITICAL: Run `python setup_models.py` ONCE before first use
#  to download and cache all models (~500MB).
#
#  Fallback: When models aren't available, a rule-based engine handles
#  column-alignment detection AND table reconstruction generically.
# ════════════════════════════════════════════════════════════════════

from PIL import Image
import torch
import numpy as np
import re
import json
import time
from typing import List, Dict, Tuple, Optional, Any


class VisionAgent:

    def __init__(self, use_layoutxlm=True):
        from api.ocr_engine import OCREngine
        self.ocr_engine = OCREngine()

        self.use_layoutxlm = use_layoutxlm
        self.processor = None
        self.model = None
        self._layoutlm_load_attempted = False

        # Table Transformer (lazy)
        self._td_model = self._tsr_model = None
        self._td_proc = self._tsr_proc = None
        self._tsr_loaded = False
        self._tsr_error = None

        # Document Structure Model (lazy)
        self._dsm_model = self._dsm_proc = None
        self._dsm_loaded = False
        self._dsm_error = None
        self._dsm_name = None

        print("[VisionAgent] Pipeline initialized (models load on first use)")

    # ================================================================
    #  DIAGNOSTIC: Call this to check what's working
    # ================================================================

    def diagnose(self):
        """
        Call this to get a full status report.
        Returns dict AND prints to console.

        Usage:
            agent = VisionAgent()
            status = agent.diagnose()
        """
        print("=" * 60)
        print("VISION AGENT DIAGNOSTIC REPORT")
        print("=" * 60)

        status = {}

        # 1. OCR
        try:
            self.ocr_engine
            status["ocr"] = {"status": "OK", "engine": "PaddleOCR"}
            print(f"  [OCR]       ✓ PaddleOCR loaded")
        except Exception as e:
            status["ocr"] = {"status": "FAILED", "error": str(e)}
            print(f"  [OCR]       ✗ FAILED: {e}")

        # 2. Table Transformer
        print(f"  [TSR]       Loading Table Transformer...")
        tsr_ok = self._ensure_tsr()
        if tsr_ok:
            status["table_detection"] = {"status": "OK", "model": "table-transformer-detection"}
            status["table_structure"] = {"status": "OK", "model": "table-transformer-structure-recognition"}
            print(f"  [TD]        ✓ Table Detection model loaded")
            print(f"  [TD]          Labels: {self._td_model.config.id2label}")
            print(f"  [TSR]       ✓ Table Structure model loaded")
            print(f"  [TSR]         Labels: {self._tsr_model.config.id2label}")
        else:
            status["table_detection"] = {"status": "FAILED", "error": self._tsr_error}
            status["table_structure"] = {"status": "FAILED", "error": self._tsr_error}
            print(f"  [TD]        ✗ FAILED: {self._tsr_error}")
            print(f"  [TSR]       ✗ FAILED: {self._tsr_error}")

        # 3. Document Structure Model
        print(f"  [DSM]       Loading Document Structure Model...")
        dsm_ok = self._ensure_dsm()
        if dsm_ok:
            status["structure_model"] = {"status": "OK", "model": self._dsm_name}
            print(f"  [DSM]       ✓ {self._dsm_name}")
            print(f"  [DSM]         Labels: {self._dsm_model.config.id2label}")
        else:
            status["structure_model"] = {"status": "FAILED", "error": self._dsm_error}
            print(f"  [DSM]       ✗ FAILED: {self._dsm_error}")

        # 4. Pipeline path
        if tsr_ok:
            path = "FULL (OCR → TD → TSR → Grid → Markdown/HTML)"
        else:
            path = "FALLBACK (OCR → Rule-based table detection)"
        status["active_pipeline"] = path
        print(f"\n  [PIPELINE]  {path}")

        # 5. Dependency check
        print(f"\n  [DEPS]      Checking packages...")
        for pkg, imp in [("torch", "torch"), ("transformers", "transformers"),
                         ("timm", "timm"), ("PIL", "PIL")]:
            try:
                mod = __import__(imp)
                ver = getattr(mod, "__version__", "?")
                status[f"dep_{pkg}"] = ver
                print(f"  [DEPS]      ✓ {pkg} = {ver}")
            except ImportError:
                status[f"dep_{pkg}"] = "MISSING"
                print(f"  [DEPS]      ✗ {pkg} NOT INSTALLED")

        print("=" * 60)
        return status

    # ================================================================
    #  LAZY LOADERS  (with detailed error capture)
    # ================================================================

    def _ensure_tsr(self):
        if self._tsr_loaded:
            return self._tsr_model is not None
        self._tsr_loaded = True
        self._tsr_error = None

        # Step 1: Check imports
        try:
            from transformers import DetrImageProcessor, TableTransformerForObjectDetection
        except ImportError as e:
            self._tsr_error = f"ImportError: {e}. Install: pip install transformers torch timm"
            print(f"[VisionAgent] ✗ TSR import failed: {self._tsr_error}")
            return False

        # Step 2: Load Table Detection
        try:
            t0 = time.time()
            self._td_proc = DetrImageProcessor.from_pretrained(
                "microsoft/table-transformer-detection", revision="no_timm")
            self._td_model = TableTransformerForObjectDetection.from_pretrained(
                "microsoft/table-transformer-detection", revision="no_timm")
            self._td_model.eval()
            print(f"[VisionAgent] ✓ Table Detection loaded ({time.time()-t0:.1f}s)")
        except Exception as e:
            self._tsr_error = f"TD load failed: {e}"
            print(f"[VisionAgent] ✗ Table Detection: {e}")
            return False

        # Step 3: Load Table Structure Recognition
        try:
            t0 = time.time()
            self._tsr_proc = DetrImageProcessor.from_pretrained(
                "microsoft/table-transformer-structure-recognition", revision="no_timm")
            self._tsr_model = TableTransformerForObjectDetection.from_pretrained(
                "microsoft/table-transformer-structure-recognition", revision="no_timm")
            self._tsr_model.eval()
            print(f"[VisionAgent] ✓ Table Structure Recognition loaded ({time.time()-t0:.1f}s)")
        except Exception as e:
            self._tsr_error = f"TSR load failed: {e}"
            print(f"[VisionAgent] ✗ Table Structure: {e}")
            # TD loaded but TSR failed — clear TD too for consistency
            self._td_model = None
            return False

        return True

    def _ensure_dsm(self):
        if self._dsm_loaded:
            return self._dsm_model is not None
        self._dsm_loaded = True
        self._dsm_error = None

        candidates = [
            "microsoft/dit-base-finetuned-doclaynet",
            "microsoft/dit-large-finetuned-doclaynet",
            "microsoft/dit-base-finetuned-publaynet",
        ]

        try:
            from transformers import AutoImageProcessor, AutoModelForObjectDetection
        except ImportError as e:
            self._dsm_error = f"ImportError: {e}"
            print(f"[VisionAgent] ✗ DSM import failed: {e}")
            return False

        for mid in candidates:
            try:
                t0 = time.time()
                self._dsm_proc = AutoImageProcessor.from_pretrained(mid)
                self._dsm_model = AutoModelForObjectDetection.from_pretrained(mid)
                self._dsm_model.eval()
                self._dsm_name = mid
                print(f"[VisionAgent] ✓ Structure Model: {mid} ({time.time()-t0:.1f}s)")
                return True
            except Exception as e:
                print(f"[VisionAgent]   ✗ {mid}: {e}")
                continue

        self._dsm_error = "No structure model could be loaded"
        print(f"[VisionAgent] ✗ Structure Model unavailable → rule-based fallback")
        return False

    # ================================================================
    #  MODEL INFERENCE WRAPPERS
    # ================================================================

    def _detect_tables(self, pil, thr=0.7):
        if not self._td_model:
            return []
        inp = self._td_proc(images=pil, return_tensors="pt")
        with torch.no_grad():
            out = self._td_model(**inp)
        tgt = torch.tensor([pil.size[::-1]])
        r = self._td_proc.post_process_object_detection(
            out, threshold=thr, target_sizes=tgt)[0]
        t = [{"bbox": b.tolist(), "score": s.item()}
             for s, b in zip(r["scores"], r["boxes"]) if s.item() >= thr]
        t.sort(key=lambda x: x["bbox"][1])
        print(f"[VisionAgent] TD found {len(t)} table(s)")
        return t

    def _recognise_tsr(self, crop, thr=0.5):
        if not self._tsr_model:
            return None
        inp = self._tsr_proc(images=crop, return_tensors="pt")
        with torch.no_grad():
            out = self._tsr_model(**inp)
        tgt = torch.tensor([crop.size[::-1]])
        r = self._tsr_proc.post_process_object_detection(
            out, threshold=thr, target_sizes=tgt)[0]
        st = {"rows": [], "columns": [], "headers": []}
        lm = self._tsr_model.config.id2label
        for s, l, b in zip(r["scores"], r["labels"], r["boxes"]):
            n = lm[l.item()]
            e = {"bbox": b.tolist(), "score": s.item()}
            if "row" in n and "header" not in n:
                st["rows"].append(e)
            elif "column" in n and "header" not in n:
                st["columns"].append(e)
            elif "header" in n:
                st["headers"].append(e)
        st["rows"].sort(key=lambda x: x["bbox"][1])
        st["columns"].sort(key=lambda x: x["bbox"][0])
        print(f"[VisionAgent] TSR → {len(st['rows'])} rows, {len(st['columns'])} cols")
        return st

    def _detect_dsm(self, pil, thr=0.5):
        if not self._dsm_model:
            return []
        inp = self._dsm_proc(images=pil, return_tensors="pt")
        with torch.no_grad():
            out = self._dsm_model(**inp)
        tgt = torch.tensor([pil.size[::-1]])
        r = self._dsm_proc.post_process_object_detection(
            out, threshold=thr, target_sizes=tgt)[0]
        lm = self._dsm_model.config.id2label
        b = [{"label": lm[l.item()], "bbox": box.tolist(), "score": s.item()}
             for s, l, box in zip(r["scores"], r["labels"], r["boxes"])
             if s.item() >= thr]
        b.sort(key=lambda x: x["bbox"][1])
        return b

    # ================================================================
    #  TSR CELL-WORD MAPPING
    # ================================================================

    def _tsr_grid(self, words_px, st, tbl_bbox):
        rows, cols = st["rows"], st["columns"]
        if not rows or not cols:
            return [], [0]
        nr, nc = len(rows), len(cols)
        grid = [[""] * nc for _ in range(nr)]
        tx, ty = tbl_bbox[0], tbl_bbox[1]
        for t, b, _ in words_px:
            cx, cy = (b[0]+b[2])/2 - tx, (b[1]+b[3])/2 - ty
            ri = self._nearest(cy, rows, "y")
            ci = self._nearest(cx, cols, "x")
            if ri >= 0 and ci >= 0:
                grid[ri][ci] = (grid[ri][ci] + " " + t).strip()
        hdr = set()
        for h in st.get("headers", []):
            hy = (h["bbox"][1]+h["bbox"][3])/2
            for ri, rw in enumerate(rows):
                if rw["bbox"][1] <= hy <= rw["bbox"][3]:
                    hdr.add(ri)
                    break
        return grid, sorted(hdr) or [0]

    @staticmethod
    def _nearest(c, items, axis):
        lo, hi = (1, 3) if axis == "y" else (0, 2)
        best, bd = -1, 1e9
        for i, it in enumerate(items):
            if it["bbox"][lo] <= c <= it["bbox"][hi]:
                return i
            d = min(abs(c - it["bbox"][lo]), abs(c - it["bbox"][hi]))
            if d < bd:
                bd, best = d, i
        return best

    # ================================================================
    #  GENERIC RULE-BASED TABLE DETECTOR
    # ================================================================

    def _detect_table_region(self, lines):
        for idx, line in enumerate(lines):
            if len(line) < 2:
                continue
            sorted_w = sorted(line, key=lambda w: w[1][0])
            gaps = [sorted_w[i][1][0] - sorted_w[i-1][1][2]
                    for i in range(1, len(sorted_w))]
            if not any(g > 50 for g in gaps):
                continue
            texts = [w[0] for w in sorted_w]
            if not all(len(t) < 35 for t in texts):
                continue
            if any('$' in t for t in texts):
                continue
            if any(t.strip().endswith(':') for t in texts):
                continue
            if any(t[0].isupper() for t in texts if t.strip() and not t.startswith('$')):
                col_bounds = [{
                    "label": w[0],
                    "x_start": w[1][0],
                    "x_end": w[1][2],
                    "x_center": (w[1][0] + w[1][2]) / 2,
                } for w in sorted_w]
                return idx, col_bounds
        return None, None

    def _find_table_end(self, lines, header_idx, col_bounds):
        end_patterns = [
            r"deductible[\s\-]section", r"special discount", r"multi[\s\-]line",
            r"special state", r"section\s+i[il]\s", r"mortgag", r"loss payee",
            r"this amendment", r"authorized representative",
            r"form and endorsement", r"endorsement\(s\)", r"total residence",
            r"your encompass", r"revised annual",
        ]
        x_min = min(c["x_start"] for c in col_bounds) - 30
        x_max = max(c["x_end"] for c in col_bounds) + 30

        for ti in range(header_idx + 1, len(lines)):
            line_text = " ".join(w[0] for w in lines[ti]).lower()
            if any(re.search(p, line_text) for p in end_patterns):
                return ti
            word_xs = [(w[1][0] + w[1][2]) / 2 for w in lines[ti]]
            if word_xs and all(x < x_min or x > x_max for x in word_xs):
                return ti
        return len(lines)

    def _build_fallback_grid(self, lines, header_idx, table_end, col_bounds):
        n_cols = len(col_bounds)
        header = [cb["label"] for cb in col_bounds]
        grid = [header]
        for line in lines[header_idx + 1: table_end]:
            row = [""] * n_cols
            for w in line:
                wx = (w[1][0] + w[1][2]) / 2
                best_col, best_dist = 0, float('inf')
                for ci, cb in enumerate(col_bounds):
                    d = abs(wx - cb["x_center"])
                    if d < best_dist:
                        best_dist = d
                        best_col = ci
                row[best_col] = (row[best_col] + " " + w[0]).strip()
            if any(c.strip() for c in row):
                grid.append(row)
        return grid

    # ================================================================
    #  FORM RENDERING
    # ================================================================

    def _render_form(self, lines):
        out, skip = [], set()
        for i, line in enumerate(lines):
            if i in skip:
                continue
            text = self._join(line).strip()
            if text.endswith(":") and i + 1 < len(lines) and (i+1) not in skip:
                nxt = lines[i + 1]
                nt = self._join(nxt).strip()
                if not nt.endswith(":"):
                    cb = max(w[1][3] for w in line)
                    nt_top = min(w[1][1] for w in nxt)
                    if (nt_top - cb) < 30 and abs(line[0][1][0] - nxt[0][1][0]) < 40:
                        out.append(f"{text} {nt}")
                        skip.add(i + 1)
                        continue
            out.append(text)
        return out

    @staticmethod
    def _join(ws):
        if not ws:
            return ""
        p = [ws[0][0]]
        lx = ws[0][1][2]
        for w in ws[1:]:
            g = w[1][0] - lx
            p.append("   " if g > 100 else "  " if g > 30 else " ")
            p.append(w[0])
            lx = w[1][2]
        return "".join(p)

    # ================================================================
    #  LINE GROUPING + NOISE FILTER
    # ================================================================

    def _group(self, words, tol=12):
        if not words:
            return []
        ws = sorted(words, key=lambda w: (w[1][1], w[1][0]))
        lines, cur, cy = [], [ws[0]], ws[0][1][1]
        for w in ws[1:]:
            if abs(w[1][1] - cy) <= tol:
                cur.append(w)
            else:
                cur.sort(key=lambda x: x[1][0])
                lines.append(cur)
                cur, cy = [w], w[1][1]
        if cur:
            cur.sort(key=lambda x: x[1][0])
            lines.append(cur)
        return lines

    _NOISE = [re.compile(p, re.I) for p in [
        r"^\.?\s*ECECEs\s*$", r"^\.?\s*SCCEPPET5\s*$", r"^\.?\s*L03335\s*$",
        r"^\d{13,}", r"^1000[02].*0{4,}", r"^2000[03].*\d{3}$",
        r"^19\d{3,}_\d+", r"^190415\d+", r"^198415\d+",
        r"^\.\s*$", r"^f:\s*$",
        r"^Creating protection around you",
        r"^001\s+E", r"^011\s+8",
    ]]

    def _clean(self, lines):
        seen, out = set(), []
        for raw in lines:
            ln = raw.strip()
            if not ln or ln in seen:
                continue
            if any(p.match(ln) for p in self._NOISE):
                continue
            out.append(ln)
            seen.add(ln)
        return out

    # ================================================================
    #  SERIALISATION
    # ================================================================

    @staticmethod
    def _grid_to_html(grid, hdr=None):
        if not grid:
            return ""
        hr = set(hdr or [0])
        h = '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">\n'
        tb = False
        for ri, row in enumerate(grid):
            if ri in hr:
                h += "  <thead><tr>\n"
                for c in row:
                    h += f"    <th>{c.strip()}</th>\n"
                h += "  </tr></thead>\n"
                if not tb:
                    h += "  <tbody>\n"
                    tb = True
            else:
                if not tb:
                    h += "  <tbody>\n"
                    tb = True
                h += "  <tr>\n"
                for c in row:
                    h += f"    <td>{c.strip()}</td>\n"
                h += "  </tr>\n"
        if tb:
            h += "  </tbody>\n"
        h += "</table>"
        return h

    @staticmethod
    def _grid_to_md(grid, hdr=None):
        if not grid:
            return ""
        hr = set(hdr or [0])
        out = []
        for ri, row in enumerate(grid):
            out.append("| " + " | ".join(c.strip() for c in row) + " |")
            if ri in hr:
                out.append("| " + " | ".join("---" for _ in row) + " |")
        return "\n".join(out)

    # ================================================================
    #  HELPERS
    # ================================================================

    @staticmethod
    def _n2p(b, w, h):
        return [b[0]*w/1000, b[1]*h/1000, b[2]*w/1000, b[3]*h/1000]

    @staticmethod
    def _p2n(b, w, h):
        return [int(b[0]/w*1000), int(b[1]/h*1000),
                int(b[2]/w*1000), int(b[3]/h*1000)]

    @staticmethod
    def _in_rgn(words, bb, m=5):
        return [(t, b, c) for t, b, c in words
                if bb[0]-m <= (b[0]+b[2])/2 <= bb[2]+m
                and bb[1]-m <= (b[1]+b[3])/2 <= bb[3]+m]

    @staticmethod
    def _outside(words, rgns):
        o = []
        for t, b, c in words:
            cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
            if not any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rgns):
                o.append((t, b, c))
        return o

    @staticmethod
    def _imginfo(img):
        if isinstance(img, np.ndarray):
            h, w = img.shape[:2]
            pil = (Image.fromarray(img[:, :, ::-1])
                   if len(img.shape) == 3 and img.shape[2] == 3
                   else Image.fromarray(img))
            return h, w, pil
        if isinstance(img, Image.Image):
            return img.size[1], img.size[0], img
        return 0, 0, None

    @staticmethod
    def _extract_fields(lines):
        f = {}
        for i, line in enumerate(lines):
            t = " ".join(w[0] for w in line)
            m = re.match(r'^(.+?):\s+(.+)$', t)
            if m and len(m.group(1)) < 60:
                f[m.group(1).strip()] = m.group(2).strip()
            elif t.strip().endswith(':') and i+1 < len(lines):
                nt = " ".join(w[0] for w in lines[i+1])
                if not nt.strip().endswith(':'):
                    k = t.strip().rstrip(':').strip()
                    if k and len(k) < 60:
                        f[k] = nt.strip()
        return f

    # ================================================================
    #  MAIN: run_vision  (backward-compatible → string)
    # ================================================================

    def run_vision(self, image):
        try:
            ocr = self.ocr_engine.run_with_boxes(image)
        except Exception:
            return "\n".join(self.ocr_engine.run(image)[0])
        if not ocr or not ocr.get("text"):
            return ""

        wn = list(zip(ocr["text"], ocr["boxes"], ocr["confidences"]))
        ih, iw, pil = self._imginfo(image)
        if pil is None:
            print("[VisionAgent] ⚠ Could not convert image to PIL → FALLBACK")
            return self._fb(wn)

        wp = [(t, self._n2p(b, iw, ih), c) for t, b, c in wn]

        tsr_ok = self._ensure_tsr()
        self._ensure_dsm()

        if tsr_ok:
            print("[VisionAgent] ▶ Using FULL pipeline (TD + TSR)")
            return self._full(pil, wn, wp, iw, ih)
        else:
            print(f"[VisionAgent] ▶ Using FALLBACK pipeline (reason: {self._tsr_error})")
            return self._fb(wn)

    # ================================================================
    #  FULL PIPELINE  (TSR + optional DiT)
    # ================================================================

    def _full(self, pil, wn, wp, iw, ih):
        tables = self._detect_tables(pil)
        if not tables:
            print("[VisionAgent] TD found 0 tables → falling back to rule-based")
            return self._fb(wn)

        tbl_bbs = [t["bbox"] for t in tables]
        sections = []

        for tbl in tables:
            bb = tbl["bbox"]
            pad = 10
            crop = pil.crop((max(0, bb[0]-pad), max(0, bb[1]-pad),
                             min(iw, bb[2]+pad), min(ih, bb[3]+pad)))
            st = self._recognise_tsr(crop)
            grid, hdr = None, [0]
            if st and st["rows"] and st["columns"]:
                tw = self._in_rgn(wp, bb, m=10)
                grid, hdr = self._tsr_grid(tw, st, bb)
                if grid:
                    print(f"[VisionAgent] ✓ TSR grid: {len(grid)}×{len(grid[0])} "
                          f"(headers at rows {hdr})")
            if grid:
                sections.append((bb[1], self._grid_to_md(grid, hdr)))
            else:
                print("[VisionAgent] TSR grid empty → fallback for this table")
                twn = [(t, self._p2n(b, iw, ih), c)
                       for t, b, c in self._in_rgn(wp, bb, m=10)]
                tl = self._group(twn)
                hi, cb = self._detect_table_region(tl)
                if hi is not None:
                    te = self._find_table_end(tl, hi, cb)
                    g = self._build_fallback_grid(tl, hi, te, cb)
                    if g:
                        sections.append((bb[1], self._grid_to_md(g, [0])))

        fwp = self._outside(wp, tbl_bbs)
        fwn = [(t, self._p2n(b, iw, ih), c) for t, b, c in fwp]
        fl = self._group(fwn)
        if fl:
            rendered = self._render_form(fl)
            cleaned = self._clean(rendered)
            if cleaned:
                y0 = fwn[0][1][1] if fwn else 0
                sections.append((y0, "\n".join(cleaned)))

        sections.sort(key=lambda s: s[0])
        return "\n\n".join(s[1] for s in sections)

    # ================================================================
    #  FALLBACK PIPELINE
    # ================================================================

    def _fb(self, wn):
        lines = self._group(wn)
        out, pos = [], 0
        while pos < len(lines):
            rem = lines[pos:]
            hi, cb = self._detect_table_region(rem)
            if hi is not None and cb:
                if hi > 0:
                    out.extend(self._render_form(rem[:hi]))
                    out.append("")
                te = self._find_table_end(rem, hi, cb)
                grid = self._build_fallback_grid(rem, hi, te, cb)
                if grid:
                    out.append(self._grid_to_md(grid, [0]))
                out.append("")
                pos += te
            else:
                out.extend(self._render_form(rem))
                break
        return "\n".join(self._clean(out))

    # ================================================================
    #  STRUCTURED OUTPUT
    # ================================================================

    def run_vision_structured(self, image):
        try:
            ocr = self.ocr_engine.run_with_boxes(image)
        except Exception:
            t = "\n".join(self.ocr_engine.run(image)[0])
            return {"markdown": t, "json": {"raw_text": t}, "html": t}
        if not ocr or not ocr.get("text"):
            return {"markdown": "", "json": {}, "html": ""}

        wn = list(zip(ocr["text"], ocr["boxes"], ocr["confidences"]))
        ih, iw, pil = self._imginfo(image)
        wp = [(t, self._n2p(b, iw, ih), c) for t, b, c in wn] if pil else []
        lines = self._group(wn)
        fields = self._extract_fields(lines)
        md = self.run_vision(image)

        th, tj = [], []
        if self._ensure_tsr() and pil:
            for tbl in self._detect_tables(pil):
                bb = tbl["bbox"]
                crop = pil.crop((max(0, bb[0]-10), max(0, bb[1]-10),
                                 min(iw, bb[2]+10), min(ih, bb[3]+10)))
                st = self._recognise_tsr(crop)
                if st and st["rows"] and st["columns"]:
                    tw = self._in_rgn(wp, bb)
                    g, hr = self._tsr_grid(tw, st, bb)
                    if g:
                        th.append(self._grid_to_html(g, hr))
                        tj.append(g)
                        continue
                twn = [(t, self._p2n(b, iw, ih), c)
                       for t, b, c in self._in_rgn(wp, bb)]
                tl = self._group(twn)
                hi, cb = self._detect_table_region(tl)
                if hi is not None:
                    te = self._find_table_end(tl, hi, cb)
                    g = self._build_fallback_grid(tl, hi, te, cb)
                    if g:
                        th.append(self._grid_to_html(g, [0]))
                        tj.append(g)
        if not tj:
            hi, cb = self._detect_table_region(lines)
            if hi is not None:
                te = self._find_table_end(lines, hi, cb)
                g = self._build_fallback_grid(lines, hi, te, cb)
                if g:
                    th.append(self._grid_to_html(g, [0]))
                    tj.append(g)

        sb = []
        if self._ensure_dsm() and pil:
            for blk in self._detect_dsm(pil):
                bw = self._in_rgn(wp, blk["bbox"], m=10) if wp else []
                sb.append({"type": blk["label"],
                           "text": " ".join(t for t, _, _ in bw),
                           "bbox": blk["bbox"],
                           "confidence": blk["score"]})

        return {
            "markdown": md,
            "html": "\n\n".join(th),
            "json": {
                "document_type": "insurance_declaration",
                "form_fields": fields,
                "tables": tj,
                "structure_blocks": sb,
                "raw_text": md,
            },
        }

    # ================================================================
    #  COMPATIBILITY
    # ================================================================

    def run_vision_raw(self, image):
        try:
            r = self.ocr_engine.run_with_boxes(image)
            return [{"text": t, "box": b, "confidence": c}
                    for t, b, c in zip(r["text"], r["boxes"], r["confidences"])]
        except Exception:
            return []

    def analyze_layout(self, image, ocr_results=None):
        if ocr_results is None:
            ocr_results = self.ocr_engine.run_with_boxes(image)
        return [{"text": t, "box": b, "element_type": "text"}
                for t, b in zip(ocr_results["text"], ocr_results["boxes"])]


# ================================================================
#  SINGLETONS
# ================================================================
_agent = None


def run_vision(image):
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.run_vision(image)


def run_vision_raw(image):
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.run_vision_raw(image)


def run_vision_structured(image):
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.run_vision_structured(image)