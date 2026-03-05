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
        grid_words = [[[] for _ in range(nc)] for _ in range(nr)]
        tx, ty = tbl_bbox[0], tbl_bbox[1]
        for t, b, _ in sorted(words_px, key=lambda w: ((w[1][1] + w[1][3]) / 2, (w[1][0] + w[1][2]) / 2)):
            cx, cy = (b[0]+b[2])/2 - tx, (b[1]+b[3])/2 - ty
            ri = self._nearest(cy, rows, "y")
            ci = self._nearest(cx, cols, "x")
            if ri >= 0 and ci >= 0:
                grid_words[ri][ci].append((cy, cx, t))
        grid = []
        for r in grid_words:
            row = []
            for c in r:
                c.sort(key=lambda it: (it[0], it[1]))
                row.append(" ".join(tok for _, _, tok in c).strip())
            grid.append(row)
        hdr = set()
        for h in st.get("headers", []):
            hy = (h["bbox"][1]+h["bbox"][3])/2
            for ri, rw in enumerate(rows):
                if rw["bbox"][1] <= hy <= rw["bbox"][3]:
                    hdr.add(ri)
                    break
        return self._normalize_grid(grid, sorted(hdr) or [0])

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

    @staticmethod
    def _normalize_grid(grid, hdr):
        if not grid:
            return [], [0]

        # Drop entirely empty columns.
        keep_cols = [ci for ci in range(len(grid[0])) if any((row[ci] or "").strip() for row in grid)]
        if not keep_cols:
            return [], [0]
        grid = [[(row[ci] or "").strip() for ci in keep_cols] for row in grid]

        # Drop entirely empty rows and remap header indices.
        old_to_new = {}
        compact = []
        for oi, row in enumerate(grid):
            if any(c.strip() for c in row):
                old_to_new[oi] = len(compact)
                compact.append(row)
        grid = compact
        if not grid:
            return [], [0]
        hdr = sorted(old_to_new[i] for i in hdr if i in old_to_new)

        # Infer header rows from top rows if model missed header labels.
        key = re.compile(r"\b(coverage|coverages|limits?|deductible|deductibles|premium|premiums|applicable)\b", re.I)
        inferred = [ri for ri in range(min(3, len(grid))) if key.search(" ".join(grid[ri]))]
        hdr = sorted(set(hdr + inferred))

        # Merge split headers into a single canonical header row.
        if len(hdr) > 1:
            merged = []
            for ci in range(len(grid[0])):
                parts = []
                for hi in hdr:
                    cell = grid[hi][ci].strip()
                    if cell and cell.lower() not in {p.lower() for p in parts}:
                        parts.append(cell)
                merged.append(" ".join(parts).strip())
            body = [row for ri, row in enumerate(grid) if ri not in set(hdr)]
            grid = [merged] + body
            hdr = [0]
        elif not hdr:
            hdr = [0]
        return grid, hdr

    @staticmethod
    def _has_table_signature(grid, hdr):
        if not grid or len(grid) < 2 or len(grid[0]) < 2:
            return False
        hr = sorted(set(hdr or [0]))
        header_text = " ".join(" ".join(grid[i]) for i in hr if 0 <= i < len(grid)).lower()
        has_cov = bool(re.search(r"\bcoverage(s)?\b", header_text))
        has_lim = bool(re.search(r"\blimit(s)?\b", header_text))
        has_right = bool(re.search(r"\bpremium(s)?\b", header_text)) or bool(
            re.search(r"\bdeductible(s)?\b", header_text)
        )
        return has_cov and has_lim and has_right

    # ================================================================
    #  GENERIC RULE-BASED TABLE DETECTOR
    # ================================================================

    def _detect_table_region(self, lines):
        for idx, line in enumerate(lines):
            if len(line) < 2:
                continue
            sorted_w = sorted(line, key=lambda w: w[1][0])
            line_text = " ".join(w[0] for w in sorted_w).lower()
            texts = [w[0] for w in sorted_w]

            # Avoid treating key/value summary rows as tables.
            colon_tokens = sum(1 for t in texts if t.strip().endswith(":"))
            if colon_tokens >= 2:
                continue

            # Require the left-side header anchors first.
            has_coverages = bool(re.search(r"\bcoverage(s)?\b", line_text))
            has_limits = bool(re.search(r"\blimit(s)?\b", line_text))
            if not (has_coverages and has_limits):
                continue

            # Support OCR where right-side header appears on the same line
            # or a nearby line (e.g., "Applicable Deductible(s) Premiums").
            header_words = list(sorted_w)
            right_hdr_idx = idx
            has_right = bool(re.search(r"\bpremium(s)?\b", line_text)) and (
                bool(re.search(r"\bdeductible(s)?\b", line_text))
                or bool(re.search(r"\bapplicable\b", line_text))
            )
            if not has_right:
                for j in range(idx, min(len(lines), idx + 8)):
                    cand = sorted(lines[j], key=lambda w: w[1][0])
                    cand_text = " ".join(w[0] for w in cand).lower()
                    if (
                        bool(re.search(r"\bpremium(s)?\b", cand_text))
                        and (
                            bool(re.search(r"\bdeductible(s)?\b", cand_text))
                            or bool(re.search(r"\bapplicable\b", cand_text))
                        )
                    ):
                        right_hdr_idx = j
                        has_right = True
                        header_words.extend(cand)
                        break
            if not has_right:
                continue

            gaps = [sorted_w[i][1][0] - sorted_w[i-1][1][2]
                    for i in range(1, len(sorted_w))]
            if not any(g > 50 for g in gaps):
                continue
            if not all(len(t) < 35 for t in texts):
                continue
            if any('$' in t for t in texts):
                continue
            if any(t.strip().endswith(':') for t in texts):
                continue
            if any(t[0].isupper() for t in texts if t.strip() and not t.startswith('$')):
                anchors = {}
                for w in sorted(header_words, key=lambda x: x[1][0]):
                    txt = w[0].lower()
                    if "coverag" in txt and "coverages" not in anchors:
                        anchors["coverages"] = w
                    elif "limit" in txt and "limits" not in anchors:
                        anchors["limits"] = w
                    elif ("deductible" in txt or "applicable" in txt) and "deductibles" not in anchors:
                        anchors["deductibles"] = w
                    elif "premium" in txt and "premiums" not in anchors:
                        anchors["premiums"] = w

                if not {"coverages", "limits", "deductibles", "premiums"}.issubset(set(anchors.keys())):
                    continue

                ordered = [
                    ("Coverages", anchors["coverages"]),
                    ("Limits", anchors["limits"]),
                    ("Applicable Deductible(s)", anchors["deductibles"]),
                    ("Premiums", anchors["premiums"]),
                ]
                col_bounds = [{
                    "label": lbl,
                    "x_start": ww[1][0],
                    "x_end": ww[1][2],
                    "x_center": (ww[1][0] + ww[1][2]) / 2,
                } for lbl, ww in ordered]
                col_bounds.sort(key=lambda c: c["x_center"])
                return min(idx, right_hdr_idx), col_bounds
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
            print("[VisionAgent] ▶ Using HYBRID pipeline (TD + TSR + fallback)")
            return self._hybrid_layout_reconstruction(pil, wn, wp, iw, ih, tsr_ok=True)
        else:
            print(f"[VisionAgent] ▶ Using HYBRID pipeline (rule-based only, reason: {self._tsr_error})")
            return self._hybrid_layout_reconstruction(pil, wn, wp, iw, ih, tsr_ok=False)

    # ================================================================
    #  HYBRID LAYOUT RECONSTRUCTION
    #  (TSR tables + rule-based fallback for uncovered regions)
    # ================================================================

    def _hybrid_layout_reconstruction(self, pil, wn, wp, iw, ih, tsr_ok=True):
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
            st = self._recognise_tsr(crop) if tsr_ok else None
            grid, hdr = None, [0]
            if st and st["rows"] and st["columns"]:
                tw = self._in_rgn(wp, bb, m=10)
                grid, hdr = self._tsr_grid(tw, st, bb)
                if grid and self._has_table_signature(grid, hdr):
                    print(f"[VisionAgent] ✓ TSR grid: {len(grid)}×{len(grid[0])} "
                          f"(headers at rows {hdr})")
                else:
                    grid = None
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

        # Run rule-based fallback on non-table words so missed table regions
        # can still be reconstructed while preserving form lines.
        fwp = self._outside(wp, tbl_bbs)
        fwn = [(t, self._p2n(b, iw, ih), c) for t, b, c in fwp]
        if fwn:
            tail = self._fb(fwn).strip()
            if tail:
                y0 = min(w[1][1] for w in fwn)
                sections.append((y0, tail))

        sections.sort(key=lambda s: s[0])
        return "\n\n".join(s[1] for s in sections)

    # Backward-compatible alias.
    def _full(self, pil, wn, wp, iw, ih):
        return self._hybrid_layout_reconstruction(pil, wn, wp, iw, ih, tsr_ok=True)

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
                    if g and self._has_table_signature(g, hr):
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
