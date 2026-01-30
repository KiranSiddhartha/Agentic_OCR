# agents/vision_agent.py - MAXIMUM RECALL MODE (FIXED PERFORMANCE)
# Proper OCR integration with PP-OCRv3 and LayoutXLM

from PIL import Image
import torch
import numpy as np

# ============================================================
# VISION AGENT – INTELLIGENT CASCADING HYBRID
# ============================================================
class VisionAgent:
    def __init__(self, use_layoutxlm=True):
        """
        Stage-aware Vision Agent
        Stage 0 : PP-OCRv3
        Stage 1 : Rule-based layout
        Stage 2 : LayoutLMv3 (ONLY if needed)
        """
        from api.ocr_engine import OCREngine
        self.ocr_engine = OCREngine()
        print("[VisionAgent] PP-OCRv3 loaded")

        self.use_layoutxlm = use_layoutxlm
        self.processor = None
        self.model = None

        if use_layoutxlm:
            try:
                from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification

                self.processor = LayoutLMv3Processor.from_pretrained(
                    "microsoft/layoutlmv3-base",
                    apply_ocr=False
                )

                self.model = LayoutLMv3ForTokenClassification.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )
                self.model.eval()

                print("[VisionAgent] LayoutLMv3 loaded")

            except Exception as e:
                print(f"[VisionAgent] LayoutLMv3 unavailable: {e}")
                self.use_layoutxlm = False

    # --------------------------------------------------------
    # STAGE 0 – OCR
    # --------------------------------------------------------
    def run_vision(self, image):
        return self.ocr_engine.run(image)

    def run_vision_raw(self, image):
        try:
            ocr_results = self.ocr_engine.run_with_boxes(image)
            all_text = []
            for word, box, conf in zip(
                ocr_results.get("text", []),
                ocr_results.get("boxes", []),
                ocr_results.get("confidences", [])
            ):
                all_text.append({
                    "text": word,
                    "box": box,
                    "confidence": conf,
                    "raw": True
                })
            return all_text
        except Exception as e:
            print(f"[VisionAgent] Raw OCR failed: {e}")
            return []

    def export_raw_ocr(self, image, output_path="full_ocr_output.txt"):
        raw_ocr = self.run_vision_raw(image)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for idx, item in enumerate(raw_ocr):
                    f.write(f"{idx:4d} | {item['confidence']:.3f} | {item['text']}\n")
            return output_path
        except Exception:
            return None

    # --------------------------------------------------------
    # INTELLIGENT CASCADING LAYOUT ANALYSIS
    # --------------------------------------------------------
    def analyze_layout(self, image, ocr_results=None):
        if ocr_results is None:
            try:
                ocr_results = self.ocr_engine.run_with_boxes(image)
            except Exception:
                return []

        if not ocr_results.get("text"):
            return []

        basic_layout = self._basic_layout_analysis(image, ocr_results)

        if not self.use_layoutxlm:
            return basic_layout

        # 🔒 FIX: LayoutLM now runs RARELY
        if not self._needs_semantic_layout(basic_layout):
            return basic_layout

        try:
            return self._layoutlm_analysis(image, ocr_results)
        except Exception as e:
            print(f"[VisionAgent] LayoutLM failed: {e}")
            return basic_layout

    # --------------------------------------------------------
    # DECISION LOGIC (FIXED – PERFORMANCE CRITICAL)
    # --------------------------------------------------------
    def _needs_semantic_layout(self, layout_elements):
        """
        STRICT gate for LayoutLM.

        Run ONLY if:
        - Many orphan labels exist
        - Clear label/value ambiguity
        """

        labels = [e for e in layout_elements if e["element_type"] == "label"]
        values = [e for e in layout_elements if e["element_type"] == "value"]

        # No labels or values → LayoutLM useless
        if not labels or not values:
            return False

        orphan_labels = 0

        for lbl in labels:
            lx0, ly0, lx1, ly1 = lbl["box"]
            matched = False

            for val in values:
                vx0, vy0, vx1, vy1 = val["box"]

                # Tight horizontal alignment only
                if vx0 > lx1 and abs(vy0 - ly0) < 20:
                    matched = True
                    break

            if not matched:
                orphan_labels += 1

        # 🔥 KEY FIX:
        # Previously: >= 2  (TOO AGGRESSIVE)
        # Now: >= 6        (RARE, HIGH-CONFIDENCE AMBIGUITY)
        return orphan_labels >= 6

    # --------------------------------------------------------
    # STAGE 2 – LAYOUTLMv3
    # --------------------------------------------------------
    def _layoutlm_analysis(self, image, ocr_results):
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image[:, :, ::-1])

        encoding = self.processor(
            image,
            ocr_results["text"],
            boxes=ocr_results["boxes"],
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=512
        )

        with torch.no_grad():
            logits = self.model(**encoding).logits

        predictions = logits.argmax(-1)[0]
        word_ids = encoding.word_ids(batch_index=0)

        return self._parse_layout(predictions, word_ids, ocr_results)

    # --------------------------------------------------------
    # PARSE LAYOUTLM OUTPUT
    # --------------------------------------------------------
    def _parse_layout(self, predictions, word_ids, ocr_results):
        label_map = {
            0: "O",
            1: "B-HEADER",
            2: "I-HEADER",
            3: "B-QUESTION",
            4: "I-QUESTION",
            5: "B-ANSWER",
            6: "I-ANSWER",
        }

        seen = set()
        layout_elements = []

        for t_idx, w_idx in enumerate(word_ids):
            if w_idx is None or w_idx in seen:
                continue
            if w_idx >= len(ocr_results["text"]):
                continue

            seen.add(w_idx)

            label = label_map.get(predictions[t_idx].item(), "O")
            word = ocr_results["text"][w_idx]
            box = ocr_results["boxes"][w_idx]
            conf = ocr_results["confidences"][w_idx]

            if "HEADER" in label:
                etype = "header"
            elif "QUESTION" in label:
                etype = "label"
            elif "ANSWER" in label:
                etype = "value"
            else:
                etype = "text"

            layout_elements.append({
                "text": word,
                "box": box,
                "element_type": etype,
                "confidence": conf,
                "layoutlm_label": label
            })

        return layout_elements

    # --------------------------------------------------------
    # STAGE 1 – RULE-BASED LAYOUT
    # --------------------------------------------------------
    def _basic_layout_analysis(self, image, ocr_results):
        elements = []

        for word, box, conf in zip(
            ocr_results["text"],
            ocr_results["boxes"],
            ocr_results["confidences"]
        ):
            word_clean = word.strip()
            etype = "text"

            if word_clean.endswith(":"):
                etype = "label"
            elif word_clean.isupper() and box[1] < 200:
                etype = "header"
            elif any(c.isdigit() for c in word_clean):
                etype = "value"

            elements.append({
                "text": word,
                "box": box,
                "element_type": etype,
                "confidence": conf
            })

        return elements


# ============================================================
# BACKWARD-COMPATIBLE SINGLETON
# ============================================================
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


def export_raw_ocr(image, output_path="full_ocr_output.txt"):
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.export_raw_ocr(image, output_path)
