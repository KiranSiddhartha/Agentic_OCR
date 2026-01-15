# # api/ocr_engine.py
# # Enhanced PP-OCRv3 with bounding box support for VI-LayoutXLM

# from paddleocr import PaddleOCR
# import numpy as np
# import cv2
# import hashlib

# class OCREngine:
#     def __init__(self):
#         """
#         PP-OCRv3 optimized settings with layout-aware features
#         """
#         self.ocr = PaddleOCR(
#             lang="en",
#             use_angle_cls=False,
#             rec_algorithm="CRNN",

#             # SPEED OPTIMIZATIONS
#             use_mp=True,
#             total_process_num=4,
#             rec_batch_num=8,
#             enable_mkldnn=True,

#             # ACCURACY OPTIMIZATIONS
#             drop_score=0.25,
#             det_db_thresh=0.3,
#             det_db_box_thresh=0.5,
#             det_limit_side_len=1920,

#             use_tensorrt=False,
#             show_log=False,
#         )

#         self._cache = {}
#         self._cache_enabled = True

#     # =========================================================
#     # EXISTING METHODS (UNCHANGED)
#     # =========================================================

#     def run(self, image):
#         """
#         Standard OCR run - returns lines and confidence
#         """
#         try:
#             if not self._is_processable(image):
#                 return [], 0.0

#             cache_key = None
#             if self._cache_enabled:
#                 cache_key = self._get_cache_key(image)
#                 if cache_key in self._cache:
#                     return self._cache[cache_key]

#             result = self.ocr.ocr(image, cls=False)

#             if not result or not result[0]:
#                 return [], 0.0

#             detections = self._extract_detections(result[0])
#             lines, confidences = self._layout_aware_sort(detections)
#             avg_conf = float(np.mean(confidences)) if confidences else 0.0

#             if cache_key and self._cache_enabled:
#                 self._cache[cache_key] = (lines, round(avg_conf, 3))

#             return lines, round(avg_conf, 3)

#         except Exception as e:
#             print(f"OCR Error: {e}")
#             return [], 0.0

#     def run_with_boxes(self, image):
#         """
#         Enhanced OCR for VI-LayoutXLM integration
#         """
#         try:
#             if not self._is_processable(image):
#                 return {
#                     "text": [],
#                     "boxes": [],
#                     "confidences": [],
#                     "lines": [],
#                     "avg_confidence": 0.0,
#                 }

#             result = self.ocr.ocr(image, cls=False)
#             if not result or not result[0]:
#                 return {
#                     "text": [],
#                     "boxes": [],
#                     "confidences": [],
#                     "lines": [],
#                     "avg_confidence": 0.0,
#                 }

#             img_h, img_w = image.shape[:2]

#             words, boxes, confidences = [], [], []

#             for box, (text, conf) in result[0]:
#                 text = text.strip()
#                 if not text or conf < 0.20 or not any(c.isalnum() for c in text):
#                     continue

#                 xs = [p[0] for p in box]
#                 ys = [p[1] for p in box]

#                 norm_box = [
#                     int((min(xs) / img_w) * 1000),
#                     int((min(ys) / img_h) * 1000),
#                     int((max(xs) / img_w) * 1000),
#                     int((max(ys) / img_h) * 1000),
#                 ]

#                 words.append(text)
#                 boxes.append(norm_box)
#                 confidences.append(conf)

#             detections = self._extract_detections(result[0])
#             lines, _ = self._layout_aware_sort(detections)
#             avg_conf = float(np.mean(confidences)) if confidences else 0.0

#             return {
#                 "text": words,
#                 "boxes": boxes,
#                 "confidences": confidences,
#                 "lines": lines,
#                 "avg_confidence": round(avg_conf, 3),
#             }

#         except Exception as e:
#             print(f"OCR Error (run_with_boxes): {e}")
#             return {
#                 "text": [],
#                 "boxes": [],
#                 "confidences": [],
#                 "lines": [],
#                 "avg_confidence": 0.0,
#             }

#     # =========================================================
#     # 🔥 NEW METHOD (ADDED — DOES NOT BREAK ANYTHING)
#     # =========================================================

#     def run_for_re(self, image):
#         """
#         Relation-Extraction ready OCR output.
#         Converts OCR into structured layout elements.
#         """
#         ocr = self.run_with_boxes(image)

#         elements = []
#         for idx, (txt, box, conf) in enumerate(
#             zip(ocr["text"], ocr["boxes"], ocr["confidences"])
#         ):
#             elements.append({
#                 "id": f"w{idx}",
#                 "text": txt,
#                 "bbox": box,               # normalized 0–1000
#                 "confidence": conf,
#                 "element_type": "word"
#             })

#         return {
#             "elements": elements,
#             "lines": ocr["lines"],
#             "avg_confidence": ocr["avg_confidence"]
#         }

#     # =========================================================
#     # INTERNAL HELPERS (UNCHANGED)
#     # =========================================================

#     def _is_processable(self, image):
#         if image is None or image.size == 0:
#             return False
#         h, w = image.shape[:2]
#         return h >= 50 and w >= 50

#     def _get_cache_key(self, image):
#         try:
#             sample = image[:: max(image.shape[0] // 10, 1)].tobytes()
#             return hashlib.md5(sample).hexdigest()
#         except Exception:
#             return None

#     def _extract_detections(self, ocr_result):
#         detections = []
#         for box, (text, conf) in ocr_result:
#             text = text.strip()
#             if not text or conf < 0.20 or not any(c.isalnum() for c in text):
#                 continue

#             xs = [p[0] for p in box]
#             ys = [p[1] for p in box]

#             detections.append({
#                 "text": text,
#                 "conf": conf,
#                 "x_min": min(xs),
#                 "x_max": max(xs),
#                 "x_center": (min(xs) + max(xs)) / 2,
#                 "y_min": min(ys),
#                 "y_max": max(ys),
#                 "y_center": (min(ys) + max(ys)) / 2,
#             })
#         return detections

#     def _layout_aware_sort(self, detections):
#         if not detections:
#             return [], []

#         is_multi = self._detect_multicolumn(detections)
#         return (
#             self._process_multicolumn(detections)
#             if is_multi
#             else self._process_single_column(detections)
#         )

#     def _detect_multicolumn(self, detections):
#         if len(detections) < 15:
#             return False

#         page_width = max(d["x_max"] for d in detections)
#         mid = page_width / 2
#         left = sum(1 for d in detections if d["x_center"] < mid - 50)
#         right = sum(1 for d in detections if d["x_center"] > mid + 50)

#         return left > 8 and right > 8

#     def _process_multicolumn(self, detections):
#         page_width = max(d["x_max"] for d in detections)
#         mid = page_width / 2

#         left = [d for d in detections if d["x_center"] < mid]
#         right = [d for d in detections if d["x_center"] >= mid]

#         left_lines, left_conf = self._build_lines(left)
#         right_lines, right_conf = self._build_lines(right)

#         return left_lines + [""] + right_lines, left_conf + [1.0] + right_conf

#     def _process_single_column(self, detections):
#         return self._build_lines(detections)

#     def _build_lines(self, detections):
#         detections.sort(key=lambda d: (d["y_center"], d["x_center"]))
#         lines, confs = [], []

#         curr, y = [], detections[0]["y_center"]
#         for d in detections:
#             if abs(d["y_center"] - y) < 15:
#                 curr.append(d)
#             else:
#                 text = self._combine_with_spacing(curr)
#                 lines.append(text)
#                 confs.append(np.mean([x["conf"] for x in curr]))
#                 curr, y = [d], d["y_center"]

#         if curr:
#             lines.append(self._combine_with_spacing(curr))
#             confs.append(np.mean([x["conf"] for x in curr]))

#         return lines, confs

#     def _combine_with_spacing(self, line):
#         line.sort(key=lambda d: d["x_center"])
#         out = line[0]["text"]
#         for i in range(1, len(line)):
#             gap = line[i]["x_min"] - line[i - 1]["x_max"]
#             out += (" " if gap < 25 else "  " if gap < 60 else "    ") + line[i]["text"]
#         return out

#     def clear_cache(self):
#         self._cache.clear()

#     def disable_cache(self):
#         self._cache_enabled = False


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