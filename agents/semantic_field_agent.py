# agents/semantic_field_agent.py
"""
Semantic Field Arbitration Agent
--------------------------------
Uses a local LLM (Ollama: Mistral / Llama 3)
ONLY to resolve ambiguous extracted fields.

Rules-first, LLM-last architecture.
"""

import requests
import json
from typing import Dict, List

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "mistral"   # or "llama3"

# -------------------------------
# 🔐 Safety limits
# -------------------------------
MAX_TEXT_CHARS = 3500
TIMEOUT = 30


# -------------------------------
# 🔍 Entry Point
# -------------------------------
def semantic_arbitrate(
    raw_lines: List[str],
    structured: Dict[str, Dict],
    low_confidence_fields: List[str],
    debug: bool = False,
) -> Dict[str, Dict]:
    """
    Resolve ambiguous fields using semantic understanding.

    Args:
        raw_lines: Cleaned OCR text lines
        structured: Output from rule-based extraction
        low_confidence_fields: Fields needing arbitration
        debug: Enable logging

    Returns:
        Updated structured fields
    """

    if not low_confidence_fields:
        return structured

    # Build semantic context
    document_text = "\n".join(raw_lines)
    document_text = document_text[:MAX_TEXT_CHARS]

    prompt = _build_prompt(
        document_text,
        structured,
        low_confidence_fields,
    )

    response = _call_ollama(prompt, debug)

    if not response:
        return structured

    return _merge_semantic_results(structured, response, debug)


# -------------------------------
# 🧠 Prompt Builder
# -------------------------------
def _build_prompt(text, structured, fields):
    return f"""
You are an insurance document analysis expert.

You are given OCR text from an insurance policy.
Some fields were extracted using rules but are ambiguous.

Your task:
- Identify the correct value ONLY for the requested fields
- Use document context
- Do NOT hallucinate
- Return JSON only

Fields to resolve:
{json.dumps(fields)}

Existing extracted values:
{json.dumps(structured, indent=2)}

OCR Text:
\"\"\"
{text}
\"\"\"

Return ONLY JSON in this format:
{{
  "field_name": "correct_value"
}}
"""


# -------------------------------
# 🔗 Ollama Call
# -------------------------------
def _call_ollama(prompt, debug=False):
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.1,
        }

        res = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT,
        )

        if res.status_code != 200:
            if debug:
                print("LLM error:", res.text)
            return None

        raw = res.json().get("response", "").strip()

        # Extract JSON safely
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return None

        return json.loads(raw[start:end + 1])

    except Exception as e:
        if debug:
            print("Semantic agent error:", e)
        return None


# -------------------------------
# 🔁 Merge Results
# -------------------------------
def _merge_semantic_results(structured, semantic_data, debug=False):
    for field, value in semantic_data.items():
        if field in structured:
            if debug:
                print(f"[Semantic Override] {field}: {structured[field]} → {value}")
            structured[field] = {
                "value": value,
                "source": "semantic_agent",
            }
    return structured


# -------------------------------
# 🧪 Helper: Identify low confidence fields
# -------------------------------
def find_low_confidence_fields(structured, threshold=0.7):
    """
    Identify fields that need semantic arbitration.
    """
    candidates = []

    for field, data in structured.items():
        if not isinstance(data, dict):
            continue

        conf = data.get("confidence", 1.0)
        if conf < threshold:
            candidates.append(field)

    return candidates
