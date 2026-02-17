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
    Expand ZIP files into independent in-memory file objects.
    Fixes closed ZipFile lambda bug.
    """
    expanded = []

    for f in files:
        name = f.name.lower()

        if name.endswith(".zip"):
            zip_bytes = f.getvalue()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                for fname in z.namelist():
                    if not fname.lower().endswith(ALLOWED_EXT):
                        continue

                    file_bytes = z.read(fname)  # ✅ READ WHILE OPEN

                    expanded.append(
                        type(
                            "UploadedFile",
                            (),
                            {
                                "name": fname,
                                "type": _guess_mime(fname),
                                "getvalue": lambda b=file_bytes: b,  # safe closure
                            },
                        )
                    )
        else:
            expanded.append(f)

    return expanded


# ============================================================
# INPUT LOADER — OLD PROJECT CONTRACT (STRONG)
# ============================================================
def load_input(data: bytes, mime_type: str):
    """
    STRONG / OLD-PROJECT BEHAVIOR

    - ALWAYS rasterize PDF pages
    - NEVER return text-only pages
    - OCR decides what is useful
    - Page 1 can NEVER be skipped

    Returns:
        List[np.ndarray]  # BGR images
    """
    pages = []

    if mime_type == "application/pdf":
        doc = fitz.open(stream=data, filetype="pdf")

        # 🔒 ALWAYS rasterize
        zoom = 450 / 72  # High-quality OCR
        mat = fitz.Matrix(zoom, zoom)

        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img = np.frombuffer(
                pix.samples, dtype=np.uint8
            ).reshape(pix.height, pix.width, pix.n)

            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            pages.append(img)

    else:
        img = cv2.imdecode(
            np.frombuffer(data, np.uint8),
            cv2.IMREAD_COLOR
        )
        if img is not None:
            pages.append(img)

    return pages


def _guess_mime(name: str) -> str:
    return "application/pdf" if name.lower().endswith(".pdf") else "image/png"
