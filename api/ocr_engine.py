# api/ocr_engine.py
# Enhanced PP-OCRv3 with bounding box support for VI-LayoutXLM
# MAXIMUM RECALL MODE - Cache permanently disabled

from paddleocr import PaddleOCR
import numpy as np
import cv2
import logging
import threading

logger = logging.getLogger("agentic_ocr.ocr")

class OCREngine:
    def __init__(self):
        """
        PP-OCRv3 optimized settings with layout-aware features
        MAXIMUM RECALL MODE - Captures ALL text including low-confidence items
        Cache permanently disabled for maximum freshness
        """
        self._lock = threading.RLock()
        self._safe_mode = False
        self.ocr = self._build_ocr(safe_mode=False)

        # Cache permanently disabled - not needed for maximum recall
        # No cache variables at all

    def _build_ocr(self, safe_mode: bool):
        kwargs = {
            "lang": "en",
            "use_angle_cls": False,
            "rec_algorithm": "CRNN",
            "rec_batch_num": 8,
            "drop_score": 0.15,
            "det_db_thresh": 0.2,
            "det_db_box_thresh": 0.4,
            "det_limit_side_len": 2880,
            "use_tensorrt": False,
            "show_log": False,
        }

        if safe_mode:
            # Stability profile for long-running API workers.
            kwargs.update(
                {
                    "use_mp": False,
                    "enable_mkldnn": False,
                    "cpu_threads": 1,
                    "rec_batch_num": 4,
                }
            )
        else:
            kwargs.update(
                {
                    "use_mp": True,
                    "total_process_num": 4,
                    "enable_mkldnn": True,
                }
            )

        logger.info("ocr_engine.init safe_mode=%s", safe_mode)
        try:
            return PaddleOCR(**kwargs)
        except TypeError:
            # Handle PaddleOCR version drift (unsupported constructor args).
            fallback = dict(kwargs)
            for maybe_unsupported in ("cpu_threads", "total_process_num"):
                fallback.pop(maybe_unsupported, None)
            logger.warning(
                "ocr_engine.init_retry_without_optional_args removed=%s",
                [k for k in ("cpu_threads", "total_process_num") if k in kwargs],
            )
            return PaddleOCR(**fallback)

    def _empty_result(self):
        return {
            "text": [],
            "boxes": [],
            "confidences": [],
            "lines": [],
            "avg_confidence": 0.0,
        }

    @staticmethod
    def _has_ocr_items(result) -> bool:
        return bool(
            isinstance(result, list)
            and len(result) > 0
            and isinstance(result[0], list)
            and len(result[0]) > 0
        )

    @staticmethod
    def _is_recoverable_ocr_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        recoverable_patterns = (
            "tensor holds no memory",
            "holder_ should not be null",
            "layout should be onednn",
            "fused_conv2d",
            "preconditionnotmet",
        )
        return any(p in msg for p in recoverable_patterns)

    def _reinitialize(self, safe_mode: bool):
        with self._lock:
            self._safe_mode = safe_mode
            self.ocr = self._build_ocr(safe_mode=safe_mode)

    def _ocr_call_with_recovery(self, image):
        try:
            with self._lock:
                result = self.ocr.ocr(image, cls=False)

            # Some PaddleOCR failures return empty results without throwing.
            # Retry once in safe mode so raw text output does not silently disappear.
            if self._has_ocr_items(result):
                return result
            if not self._safe_mode:
                logger.warning("ocr_engine.empty_result_retry switching_to_safe_mode")
                self._reinitialize(safe_mode=True)
                with self._lock:
                    safe_result = self.ocr.ocr(image, cls=False)
                return safe_result
            return result
        except Exception as e:
            if not self._is_recoverable_ocr_error(e):
                raise

            logger.exception(
                "ocr_engine.recoverable_error safe_mode=%s; rebuilding engine",
                self._safe_mode,
            )
            try:
                if not self._safe_mode:
                    self._reinitialize(safe_mode=True)
                else:
                    # Recreate even in safe mode if instance is corrupted.
                    self._reinitialize(safe_mode=True)
                with self._lock:
                    return self.ocr.ocr(image, cls=False)
            except Exception:
                logger.exception("ocr_engine.recovery_retry_failed")
                raise

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

            result = self._ocr_call_with_recovery(image)

            if not self._has_ocr_items(result):
                return [], 0.0

            detections = self._extract_detections(result[0])
            lines, confidences = self._layout_aware_sort(detections)
            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            return lines, round(avg_conf, 3)

        except Exception as e:
            logger.exception("ocr_engine.run_failed error=%s", e)
            return [], 0.0

    def run_with_boxes(self, image):
        """
        Enhanced OCR for VI-LayoutXLM integration
        MAXIMUM RECALL MODE - Keeps almost all text
        No caching - always fresh results
        """
        try:
            if not self._is_processable(image):
                return self._empty_result()

            result = self._ocr_call_with_recovery(image)
            if not self._has_ocr_items(result):
                return self._empty_result()

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
            logger.exception("ocr_engine.run_with_boxes_failed error=%s", e)
            return self._empty_result()

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
