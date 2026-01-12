import cv2
import numpy as np
import zipfile
import io
import fitz  # PyMuPDF

ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf")


# ============================================================
# ZIP EXPANSION
# ============================================================
def expand_uploaded_files(files):
    """
    Expand ZIP files into individual file-like objects.
    """
    expanded = []

    for f in files:
        name = f.name.lower()

        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(f.read())) as z:
                for fname in z.namelist():
                    if fname.lower().endswith(ALLOWED_EXT):
                        expanded.append(
                            type(
                                "UploadedFile",
                                (),
                                {
                                    "name": fname,
                                    "type": _guess_mime(fname),
                                    "getvalue": lambda z=z, fname=fname: z.read(fname),
                                },
                            )
                        )
        else:
            expanded.append(f)

    return expanded


# ============================================================
# INPUT LOADER (OPTIMAL + FAST)
# ============================================================
def load_input(data: bytes, mime_type: str):
    """
    Load image or PDF input.

    Strategy:
    1) Extract vector text first (fastest)
    2) OCR only if page is image-only
    3) Rasterize at 220 DPI (CRNN sweet spot)

    Returns:
      [
        { "type": "text",  "content": str },
        { "type": "image", "content": np.ndarray }
      ]
    """
    pages = []

    if mime_type == "application/pdf":
        doc = fitz.open(stream=data, filetype="pdf")

        for page in doc:
            text = page.get_text("text")

            if text and len(text.strip()) > 100:
                pages.append({
                    "type": "text",
                    "content": text
                })
                continue

            # Image-only page → render at 220 DPI
            zoom = 220 / 72
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

            img = np.frombuffer(
                pix.samples, dtype=np.uint8
            ).reshape(pix.height, pix.width, pix.n)

            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            pages.append({
                "type": "image",
                "content": img
            })

    else:
        img = cv2.imdecode(
            np.frombuffer(data, np.uint8),
            cv2.IMREAD_COLOR
        )
        if img is not None:
            pages.append({
                "type": "image",
                "content": img
            })

    return pages


def _guess_mime(name: str) -> str:
    return "application/pdf" if name.lower().endswith(".pdf") else "image/png"
