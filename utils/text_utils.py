 
# # utils/text_utils.py
# # OPTIMAL: Simple but effective text processing
# import re
# import unicodedata


# def normalize_text(text):
#     """Basic normalization - no over-processing."""
#     if not text:
#         return ""

#     text = unicodedata.normalize("NFKD", text)
    
#     # Fix common unicode issues
#     text = text.replace("°", "o")
#     text = text.replace("–", "-")
#     text = text.replace("—", "-")
    
#     # Keep only printable
#     text = "".join(c for c in text if c.isprintable())
    
#     # Normalize spaces
#     text = re.sub(r"\s+", " ", text)
    
#     return text.strip()


# def merge_broken_lines(lines):
#     """
#     Smart line merging - CRITICAL for forms.
#     Merges lines that are clearly continuations.
#     """
#     if not lines or len(lines) < 2:
#         return lines

#     merged = []
#     i = 0

#     while i < len(lines):
#         current = lines[i]

#         if i + 1 < len(lines):
#             next_line = lines[i + 1]

#             # Rule 1: Label ends with colon
#             if current.endswith(":") and next_line:
#                 merged.append(current + " " + next_line)
#                 i += 2
#                 continue

#             # Rule 2: Broken word (current ends with letter, next starts lowercase)
#             if (current and 
#                 len(current) < 40 and
#                 current[-1].isalnum() and
#                 next_line and 
#                 next_line[0].islower()):
#                 merged.append(current + next_line)
#                 i += 2
#                 continue

#             # Rule 3: Very short line likely incomplete
#             if len(current.strip()) < 3 and next_line:
#                 merged.append(current + " " + next_line)
#                 i += 2
#                 continue

#         merged.append(current)
#         i += 1

#     return merged
 
# utils/text_utils.py
# OCR-safe text utilities (STRUCTURE-PRESERVING, DROP-IN)

import re
import unicodedata


# ------------------------------------------------------------
# VERY LIGHT OCR NORMALIZATION
# ------------------------------------------------------------
def light_normalize_ocr(lines):
    """
    VERY LIGHT OCR normalization.
    Preserves OCR noise intentionally.
    """
    normalized = []

    for line in lines:
        if not line:
            continue

        l = unicodedata.normalize("NFKD", line)
        l = l.replace("–", "-").replace("—", "-")
        l = "".join(c for c in l if c.isprintable()).strip()

        if l:
            normalized.append(l)

    return normalized


# ------------------------------------------------------------
# LEGACY SINGLE-LINE NORMALIZATION (SAFE)
# ------------------------------------------------------------
def normalize_text(text):
    """
    Legacy single-line normalization (SAFE).
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = text.replace("°", "o")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = "".join(c for c in text if c.isprintable())
    text = text.replace("\t", "    ")

    return text.strip()


# ------------------------------------------------------------
# STRUCTURE-AWARE FIELD SPLITTER
# ------------------------------------------------------------
_FIELD_LABELS = [
    "policy number",
    "policyholder/named insured",
    "policyholder since",
    "mailing address",
    "policy period",
    "24-hour claim reporting",
    "agent",
    "insurance provided by",
    "customer assistance number",
    "policy effective date",
]


def _split_structured_fields(lines):
    """
    Split known 'Label: value' lines into:
        Label:
        value
    """
    output = []

    for line in lines:
        l = line.strip()
        if not l:
            output.append("")
            continue

        lower = l.lower()
        matched = False

        for label in _FIELD_LABELS:
            if lower.startswith(label) and ":" in l:
                parts = re.split(r":\s*", l, maxsplit=1)
                output.append(parts[0].strip() + ":")
                if len(parts) > 1 and parts[1].strip():
                    output.append(parts[1].strip())
                matched = True
                break

        if not matched:
            output.append(l)

    return output


# ------------------------------------------------------------
# OCR-SAFE LINE MERGING (FINAL)
# ------------------------------------------------------------
def merge_broken_lines(lines):
    """
    OCR-safe line merge.
    Preserves label/value separation.
    DROP-IN SAFE.
    """
    if not lines:
        return []

    # Step 1: split structured fields first
    lines = _split_structured_fields(lines)

    merged = []
    buffer = ""

    for line in lines:
        line = line.strip()

        # Preserve blank lines
        if not line:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append("")
            continue

        # NEVER merge after a label
        if buffer.endswith(":"):
            merged.append(buffer)
            buffer = line
            continue

        # Merge only true sentence continuations
        if (
            buffer
            and buffer[-1].isalnum()
            and line[0].islower()
            and len(buffer) < 60
        ):
            buffer += " " + line
        else:
            if buffer:
                merged.append(buffer)
            buffer = line

    if buffer:
        merged.append(buffer)

    return merged
