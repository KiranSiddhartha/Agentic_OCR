 
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
# OCR-safe text utilities (NO aggressive cleaning)

import re
import unicodedata


def light_normalize_ocr(lines):
    """
    VERY LIGHT OCR normalization.
    Preserves OCR noise intentionally.
    """
    normalized = []

    for line in lines:
        if not line:
            continue

        # Unicode normalize
        l = unicodedata.normalize("NFKD", line)

        # Normalize dashes
        l = l.replace("–", "-").replace("—", "-")

        # Keep printable characters only
        l = "".join(c for c in l if c.isprintable()).strip()

        if l:
            normalized.append(l)

    return normalized


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


def merge_broken_lines(lines):
    """
    Layout-aware line merge.
    """
    if not lines or len(lines) < 2:
        return lines

    merged = []
    i = 0

    while i < len(lines):
        current = lines[i]

        if i + 1 < len(lines):
            next_line = lines[i + 1]

            # Preserve tables
            if "  " in current or "  " in next_line:
                merged.append(current)
                i += 1
                continue

            # Label continuation
            if current.endswith(":"):
                merged.append(current + " " + next_line)
                i += 2
                continue

            # Broken sentence
            if (
                len(current) < 40
                and current[-1].isalnum()
                and next_line[0].islower()
            ):
                merged.append(current + " " + next_line)
                i += 2
                continue

        merged.append(current)
        i += 1

    return merged
