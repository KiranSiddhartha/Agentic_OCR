# api/ocr_engine.py
# Enhanced PP-OCRv3 with bounding box support for VI-LayoutXLM
# MAXIMUM RECALL MODE - Cache permanently disabled

from paddleocr import PaddleOCR
import numpy as np
import cv2

class OCREngine:
    def __init__(self):
        """
        PP-OCRv3 optimized settings with layout-aware features
        MAXIMUM RECALL MODE - Captures ALL text including low-confidence items
        Cache permanently disabled for maximum freshness
        """
        self.ocr = PaddleOCR(
            lang="en",
            use_angle_cls=False,
            rec_algorithm="CRNN",

            # SPEED OPTIMIZATIONS
            use_mp=True,
            total_process_num=4,
            rec_batch_num=8,
            enable_mkldnn=True,

            # ACCURACY OPTIMIZATIONS - MAXIMUM RECALL
            drop_score=0.15,           # CHANGED: Was 0.25, now 0.15
            det_db_thresh=0.2,         # CHANGED: Was 0.3, now 0.2
            det_db_box_thresh=0.4,     # CHANGED: Was 0.5, now 0.4
            det_limit_side_len=2880,   # CHANGED: Was 1920, now 2880

            use_tensorrt=False,
            show_log=False,
        )

        # Cache permanently disabled - not needed for maximum recall
        # No cache variables at all

    # =========================================================
    # MAIN OCR METHODS
    # =========================================================

    def run(self, image):
        """
        Standard OCR run - returns lines and confidence
        No caching - always fresh results
        """
        try:
            if not self._is_processable(image):
                return [], 0.0

            result = self.ocr.ocr(image, cls=False)

            if not result or not result[0]:
                return [], 0.0

            detections = self._extract_detections(result[0])
            lines, confidences = self._layout_aware_sort(detections)
            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            return lines, round(avg_conf, 3)

        except Exception as e:
            print(f"OCR Error: {e}")
            return [], 0.0

    def run_with_boxes(self, image):
        """
        Enhanced OCR for VI-LayoutXLM integration
        MAXIMUM RECALL MODE - Keeps almost all text
        No caching - always fresh results
        """
        try:
            if not self._is_processable(image):
                return {
                    "text": [],
                    "boxes": [],
                    "confidences": [],
                    "lines": [],
                    "avg_confidence": 0.0,
                }

            result = self.ocr.ocr(image, cls=False)
            if not result or not result[0]:
                return {
                    "text": [],
                    "boxes": [],
                    "confidences": [],
                    "lines": [],
                    "avg_confidence": 0.0,
                }

            img_h, img_w = image.shape[:2]

            words, boxes, confidences = [], [], []

            for box, (text, conf) in result[0]:
                text = text.strip()
                
                # CRITICAL FIX: MAXIMUM PRESERVATION
                if not text:
                    continue
                
                # ULTRA-RELAXED: Keep text with 10%+ confidence
                if conf < 0.10:
                    continue
                
                # REMOVED: Alphanumeric check - keep ALL text including special chars

                xs = [p[0] for p in box]
                ys = [p[1] for p in box]

                norm_box = [
                    int((min(xs) / img_w) * 1000),
                    int((min(ys) / img_h) * 1000),
                    int((max(xs) / img_w) * 1000),
                    int((max(ys) / img_h) * 1000),
                ]

                words.append(text)
                boxes.append(norm_box)
                confidences.append(conf)

            detections = self._extract_detections(result[0])
            lines, _ = self._layout_aware_sort(detections)
            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            return {
                "text": words,
                "boxes": boxes,
                "confidences": confidences,
                "lines": lines,
                "avg_confidence": round(avg_conf, 3),
            }

        except Exception as e:
            print(f"OCR Error (run_with_boxes): {e}")
            return {
                "text": [],
                "boxes": [],
                "confidences": [],
                "lines": [],
                "avg_confidence": 0.0,
            }

    # =========================================================
    # RELATION EXTRACTION METHOD
    # =========================================================

    def run_for_re(self, image):
        """
        Relation-Extraction ready OCR output.
        Converts OCR into structured layout elements.
        """
        ocr = self.run_with_boxes(image)

        elements = []
        for idx, (txt, box, conf) in enumerate(
            zip(ocr["text"], ocr["boxes"], ocr["confidences"])
        ):
            elements.append({
                "id": f"w{idx}",
                "text": txt,
                "bbox": box,               # normalized 0–1000
                "confidence": conf,
                "element_type": "word"
            })

        return {
            "elements": elements,
            "lines": ocr["lines"],
            "avg_confidence": ocr["avg_confidence"]
        }

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================

    def _is_processable(self, image):
        if image is None or image.size == 0:
            return False
        h, w = image.shape[:2]
        return h >= 50 and w >= 50

    def _extract_detections(self, ocr_result):
        detections = []
        for box, (text, conf) in ocr_result:
            text = text.strip()
            
            # CRITICAL FIX: MAXIMUM PRESERVATION
            if not text:
                continue
            
            # ULTRA-RELAXED: Keep text with 10%+ confidence
            if conf < 0.10:
                continue
            
            # REMOVED: Alphanumeric check - keep ALL text

            xs = [p[0] for p in box]
            ys = [p[1] for p in box]

            detections.append({
                "text": text,
                "conf": conf,
                "x_min": min(xs),
                "x_max": max(xs),
                "x_center": (min(xs) + max(xs)) / 2,
                "y_min": min(ys),
                "y_max": max(ys),
                "y_center": (min(ys) + max(ys)) / 2,
            })
        return detections

    def _layout_aware_sort(self, detections):
        if not detections:
            return [], []

        is_multi = self._detect_multicolumn(detections)
        return (
            self._process_multicolumn(detections)
            if is_multi
            else self._process_single_column(detections)
        )

    def _detect_multicolumn(self, detections):
        if len(detections) < 15:
            return False

        page_width = max(d["x_max"] for d in detections)
        mid = page_width / 2
        left = sum(1 for d in detections if d["x_center"] < mid - 50)
        right = sum(1 for d in detections if d["x_center"] > mid + 50)

        return left > 8 and right > 8

    def _process_multicolumn(self, detections):
        page_width = max(d["x_max"] for d in detections)
        mid = page_width / 2

        left = [d for d in detections if d["x_center"] < mid]
        right = [d for d in detections if d["x_center"] >= mid]

        left_lines, left_conf = self._build_lines(left)
        right_lines, right_conf = self._build_lines(right)

        return left_lines + [""] + right_lines, left_conf + [1.0] + right_conf

    def _process_single_column(self, detections):
        return self._build_lines(detections)

    def _build_lines(self, detections):
        if not detections:
            return [], []
            
        detections.sort(key=lambda d: (d["y_center"], d["x_center"]))
        lines, confs = [], []

        curr, y = [], detections[0]["y_center"]
        for d in detections:
            if abs(d["y_center"] - y) < 15:
                curr.append(d)
            else:
                text = self._combine_with_spacing(curr)
                lines.append(text)
                confs.append(np.mean([x["conf"] for x in curr]))
                curr, y = [d], d["y_center"]

        if curr:
            lines.append(self._combine_with_spacing(curr))
            confs.append(np.mean([x["conf"] for x in curr]))

        return lines, confs

    def _combine_with_spacing(self, line):
        if not line:
            return ""
            
        line.sort(key=lambda d: d["x_center"])
        out = line[0]["text"]
        for i in range(1, len(line)):
            gap = line[i]["x_min"] - line[i - 1]["x_max"]
            out += (" " if gap < 25 else "  " if gap < 60 else "    ") + line[i]["text"]
        return out


# # api/ocr_engine.py
# # Enhanced PP-OCRv3 with Grid-Based Table Reconstruction
# # Matches Kriyam.ai style output

# from paddleocr import PaddleOCR
# import numpy as np

# class OCREngine:
#     def __init__(self):
#         """
#         PP-OCRv3 initialized with high-sensitivity settings.
#         Designed to detect complex tables and faint text.
#         """
#         self.ocr = PaddleOCR(
#             lang="en",
#             use_angle_cls=False,
#             rec_algorithm="CRNN",
#             # High resolution for dense documents
#             rec_image_shape="3, 48, 320", 

#             # SPEED SETTINGS
#             use_mp=True,
#             total_process_num=4,
#             rec_batch_num=8,
#             enable_mkldnn=True,

#             # ACCURACY SETTINGS (MAXIMUM RECALL)
#             # These low thresholds ensure we don't miss "included" or small numbers
#             drop_score=0.01,           
#             det_db_thresh=0.1,         
#             det_db_box_thresh=0.3,     
#             det_limit_side_len=2880,   

#             use_tensorrt=False,
#             show_log=False,
#         )

#     # =========================================================
#     # MAIN EXECUTION
#     # =========================================================

#     def run(self, image):
#         try:
#             if not self._is_processable(image):
#                 return [], 0.0

#             result = self.ocr.ocr(image, cls=False)
#             if not result or not result[0]:
#                 return [], 0.0

#             # 1. Standardize the data
#             detections = self._extract_detections(result[0])
            
#             # 2. Run the Layout Engine (The "Brain" of the logic)
#             lines, confidences = self._layout_engine(detections)
            
#             avg_conf = float(np.mean(confidences)) if confidences else 0.0
#             return lines, round(avg_conf, 3)

#         except Exception as e:
#             print(f"OCR Error: {e}")
#             return [], 0.0

#     def run_with_boxes(self, image):
#         # Support method for visualization/debugging
#         try:
#             if not self._is_processable(image): return self._empty_result()
#             result = self.ocr.ocr(image, cls=False)
#             if not result or not result[0]: return self._empty_result()

#             img_h, img_w = image.shape[:2]
#             words, boxes, confidences = [], [], []

#             for box, (text, conf) in result[0]:
#                 text = text.strip()
#                 if not text or conf < 0.01: continue
                
#                 xs = [p[0] for p in box]
#                 ys = [p[1] for p in box]
#                 norm_box = [
#                     int((min(xs) / img_w) * 1000), int((min(ys) / img_h) * 1000),
#                     int((max(xs) / img_w) * 1000), int((max(ys) / img_h) * 1000),
#                 ]
#                 words.append(text)
#                 boxes.append(norm_box)
#                 confidences.append(conf)

#             detections = self._extract_detections(result[0])
#             lines, _ = self._layout_engine(detections)
#             avg_conf = float(np.mean(confidences)) if confidences else 0.0

#             return {
#                 "text": words, "boxes": boxes, "confidences": confidences,
#                 "lines": lines, "avg_confidence": round(avg_conf, 3),
#             }
#         except Exception as e:
#             print(f"OCR Error: {e}")
#             return self._empty_result()

#     def _empty_result(self):
#         return {"text": [], "boxes": [], "confidences": [], "lines": [], "avg_confidence": 0.0}

#     def run_for_re(self, image):
#         return self.run_with_boxes(image) # wrapper for existing calls

#     # =========================================================
#     # CORE LAYOUT LOGIC
#     # =========================================================

#     def _extract_detections(self, ocr_result):
#         # Convert Paddle format to easier Dict format
#         detections = []
#         for box, (text, conf) in ocr_result:
#             text = text.strip()
#             if not text: continue
            
#             xs = [p[0] for p in box]
#             ys = [p[1] for p in box]
#             detections.append({
#                 "text": text,
#                 "conf": conf,
#                 "x_min": min(xs), "x_max": max(xs),
#                 "x_center": (min(xs) + max(xs)) / 2,
#                 "y_min": min(ys), "y_max": max(ys),
#                 "y_center": (min(ys) + max(ys)) / 2,
#                 "height": max(ys) - min(ys)
#             })
#         return detections

#     def _layout_engine(self, detections):
#         if not detections: return [], []

#         # Sort top-to-bottom to find the layout structure
#         detections.sort(key=lambda d: d["y_center"])

#         # 1. SEARCH FOR TABLE HEADER
#         # We look for the "Coverages" ... "Premiums" line.
#         header_y = None
#         header_boxes = []
        
#         # Helper: group raw boxes into lines temporarily
#         temp_lines = self._group_into_lines(detections)
        
#         for line in temp_lines:
#             # Join text to check keywords
#             line_text = " ".join([d["text"].lower() for d in line])
#             # This combination identifies the table
#             if "coverages" in line_text and "limits" in line_text and "premiums" in line_text:
#                 header_y = line[0]["y_min"] - 10
#                 header_boxes = line
#                 break

#         final_lines = []
#         final_confs = []

#         # 2. SPLIT CONTENT: TOP vs TABLE
#         if header_y is not None:
#             # Split items above and below the header
#             top_items = [d for d in detections if d["y_center"] < header_y]
#             table_items = [d for d in detections if d["y_center"] >= header_y]

#             # A. Process Top (Standard Linear Layout)
#             top_lines, top_confs = self._process_standard_layout(top_items)
#             final_lines.extend(top_lines)
#             final_confs.extend(top_confs)
            
#             # Add spacer
#             if final_lines: final_lines.append("")

#             # B. Process Table (Grid Layout)
#             tbl_lines, tbl_confs = self._process_grid_table(header_boxes, table_items)
#             final_lines.extend(tbl_lines)
#             final_confs.extend(tbl_confs)

#         else:
#             # Fallback: No table found, process everything as standard layout
#             return self._process_standard_layout(detections)

#         return final_lines, final_confs

#     # =========================================================
#     # LAYOUT HELPERS
#     # =========================================================

#     def _group_into_lines(self, detections):
#         # Groups loose boxes into lines based on Y-coordinates
#         if not detections: return []
#         # Sort by Y
#         detections.sort(key=lambda d: d["y_center"])
        
#         lines = []
#         current_line = []
#         current_y = detections[0]["y_center"]
#         current_h = detections[0]["height"]

#         for d in detections:
#             # If vertical distance is small (< 60% of text height), it's the same line
#             if abs(d["y_center"] - current_y) < (current_h * 0.6):
#                 current_line.append(d)
#                 # Adjust moving average Y
#                 current_y = (current_y + d["y_center"]) / 2
#             else:
#                 # New line started
#                 current_line.sort(key=lambda x: x["x_min"]) # Sort Left-to-Right
#                 lines.append(current_line)
#                 current_line = [d]
#                 current_y = d["y_center"]
#                 current_h = d["height"]
        
#         if current_line:
#             current_line.sort(key=lambda x: x["x_min"])
#             lines.append(current_line)
            
#         return lines

#     def _process_standard_layout(self, items):
#         # Processes non-table text (like headers, addresses)
#         lines = self._group_into_lines(items)
#         output = []
#         confs = []
        
#         for line in lines:
#             # Combine words with intelligent spacing
#             line_str = line[0]["text"]
#             line_confs = [line[0]["conf"]]
            
#             for i in range(1, len(line)):
#                 # Calculate gap
#                 gap = line[i]["x_min"] - line[i-1]["x_max"]
#                 # If gap is huge (columnar), add 4 spaces, otherwise 1
#                 sep = "    " if gap > 40 else " "
#                 line_str += sep + line[i]["text"]
#                 line_confs.append(line[i]["conf"])
            
#             output.append(line_str)
#             confs.append(np.mean(line_confs))
            
#         return output, confs

#     def _process_grid_table(self, header_row, all_table_items):
#         # 1. CALCULATE COLUMN BOUNDARIES
#         # We need to know where "Limits" starts and "Premiums" starts to draw invisible lines.
#         # Default boundaries (0-1000 scale approx) just in case
#         bound_limit = 500
#         bound_deduct = 700
#         bound_prem = 850
        
#         # Refine boundaries based on actual header positions
#         for d in header_row:
#             txt = d["text"].lower()
#             if "limits" in txt:
#                 bound_limit = d["x_min"] - 20
#             elif "deductible" in txt or "applicable" in txt:
#                 bound_deduct = d["x_min"] - 20
#             elif "premium" in txt:
#                 bound_prem = d["x_min"] - 20

#         # 2. GROUP CONTENT INTO ROWS
#         rows = self._group_into_lines(all_table_items)
        
#         output = []
#         confs = []
#         is_first = True

#         for row in rows:
#             # Initialize 4 Buckets: [Coverages, Limits, Deductibles, Premiums]
#             cols = [[], [], [], []]
#             row_conf = []

#             for d in row:
#                 row_conf.append(d["conf"])
#                 cx = d["x_center"]
                
#                 # GRID LOGIC: Assign text to bucket based on center X
#                 if cx < bound_limit:
#                     cols[0].append(d["text"])
#                 elif cx < bound_deduct:
#                     cols[1].append(d["text"])
#                 elif cx < bound_prem:
#                     cols[2].append(d["text"])
#                 else:
#                     cols[3].append(d["text"])

#             # Join the content of each bucket
#             c1 = " ".join(cols[0])
#             c2 = " ".join(cols[1])
#             c3 = " ".join(cols[2])
#             c4 = " ".join(cols[3])

#             # Markdown Format
#             md_row = f"| {c1} | {c2} | {c3} | {c4} |"
            
#             output.append(md_row)
#             if is_first:
#                 # Add Markdown Header Separator after the first row (the header)
#                 output.append("|---|---|---|---|")
#                 is_first = False
            
#             confs.append(np.mean(row_conf) if row_conf else 0.0)

#         return output, confs
    
#     def _is_processable(self, image):
#         if image is None or image.size == 0: return False
#         h, w = image.shape[:2]
#         return h >= 50 and w >= 50