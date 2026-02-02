# agents/vision_agent.py - MAXIMUM RECALL MODE
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

                # IMPORTANT: apply_ocr MUST be False
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
    # STAGE 0 – OCR (STANDARD)
    # --------------------------------------------------------
    def run_vision(self, image):
        return self.ocr_engine.run(image)

    # --------------------------------------------------------
    # NEW: RAW OCR OUTPUT (100% UNFILTERED)
    # --------------------------------------------------------
    def run_vision_raw(self, image):
        """
        Return 100% raw OCR text with NO filtering.
        Use this for debugging missing text.
        """
        try:
            ocr_results = self.ocr_engine.run_with_boxes(image)
            
            # Return EVERYTHING - no filtering
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
                    "raw": True  # Flag to indicate unfiltered
                })
            
            print(f"[VisionAgent] Raw OCR extracted {len(all_text)} items")
            return all_text
            
        except Exception as e:
            print(f"[VisionAgent] Raw OCR failed: {e}")
            return []

    # --------------------------------------------------------
    # NEW: EXPORT RAW OCR TO TEXT FILE
    # --------------------------------------------------------
    def export_raw_ocr(self, image, output_path="full_ocr_output.txt"):
        """
        Export 100% raw OCR to text file for debugging.
        """
        raw_ocr = self.run_vision_raw(image)
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("COMPLETE RAW OCR OUTPUT (100% UNFILTERED)\n")
                f.write("=" * 80 + "\n\n")
                
                for idx, item in enumerate(raw_ocr):
                    f.write(f"{idx:4d} | {item['confidence']:.3f} | {item['text']}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"TOTAL LINES: {len(raw_ocr)}\n")
                f.write("=" * 80 + "\n")
            
            print(f"[VisionAgent] Raw OCR exported to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"[VisionAgent] Export failed: {e}")
            return None

    # --------------------------------------------------------
    # INTELLIGENT CASCADING LAYOUT ANALYSIS
    # --------------------------------------------------------
    def analyze_layout(self, image, ocr_results=None):
        """
        INTELLIGENT CASCADE:
        1. OCR
        2. Rule-based layout
        3. LayoutLMv3 ONLY if ambiguity detected
        """

        if ocr_results is None:
            try:
                ocr_results = self.ocr_engine.run_with_boxes(image)
            except Exception as e:
                print(f"[VisionAgent] OCR failed: {e}")
                return []

        if not ocr_results.get("text"):
            return []

        # ---------- STAGE 1: RULE-BASED (FAST, FREE) ----------
        basic_layout = self._basic_layout_analysis(image, ocr_results)

        if not self.use_layoutxlm:
            return basic_layout

        # ---------- DECISION: SHOULD WE RUN LAYOUTLM? ----------
        if not self._needs_semantic_layout(basic_layout):
            return basic_layout

        # ---------- STAGE 2: LAYOUTLMv3 (EXPENSIVE) ----------
        try:
            return self._layoutlm_analysis(image, ocr_results)
        except Exception as e:
            print(f"[VisionAgent] LayoutLM failed: {e}")
            return basic_layout

    # --------------------------------------------------------
    # DECISION LOGIC (CRITICAL)
    # --------------------------------------------------------
    def _needs_semantic_layout(self, layout_elements):
        """
        Run LayoutLM ONLY if:
        - Labels exist without nearby values
        - Dense table-like structure


        """

        labels = [e for e in layout_elements if e["element_type"] == "label"]
        values = [e for e in layout_elements if e["element_type"] == "value"]


        if not labels or not values:
            return False

        # Too many labels with no values → ambiguity
        orphan_labels = 0

        for lbl in labels:
            lx0, ly0, lx1, ly1 = lbl["box"]
            matched = False

            for val in values:
                vx0, vy0, vx1, vy1 = val["box"]
                if vx0 > lx1 and abs(vy0 - ly0) < 40:


                    matched = True
                    break

            if not matched:
                orphan_labels += 1

        return orphan_labels >= 2




    # --------------------------------------------------------
    # STAGE 2 – LAYOUTLMv3 (SAFE)
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
    # STAGE 1 – RULE-BASED LAYOUT (FALLBACK)
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

    # --------------------------------------------------------
    # KEY–VALUE PAIR EXTRACTION
    # --------------------------------------------------------
    def extract_key_value_pairs(self, layout_elements):
        pairs = []
        labels = [e for e in layout_elements if e["element_type"] in ("label", "header")]
        values = [e for e in layout_elements if e["element_type"] == "value"]

        for lbl in labels:
            lx0, ly0, lx1, ly1 = lbl["box"]
            best, dist = None, 1e9

            for val in values:
                vx0, vy0, vx1, vy1 = val["box"]
                if vx0 > lx1 and abs(vy0 - ly0) < 50:
                    d = vx0 - lx1
                elif vy0 > ly1 and vy0 - ly1 < 120:
                    d = vy0 - ly1
                else:
                    continue

                if d < dist:
                    dist = d
                    best = val

            if best:
                pairs.append((lbl["text"], best["text"]))

        return pairs


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
    """
    Global function for 100% raw OCR output.
    """
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.run_vision_raw(image)


def export_raw_ocr(image, output_path="full_ocr_output.txt"):
    """
    Global function to export raw OCR to file.
    """
    global _agent
    if _agent is None:
        _agent = VisionAgent(use_layoutxlm=False)
    return _agent.export_raw_ocr(image, output_path)