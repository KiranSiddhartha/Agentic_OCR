# preprocessing.py
# OCR-SAFE preprocessing for PaddleOCR

import cv2


def preprocess(image, strategy=None):
    """
    SAFE preprocessing for PaddleOCR.
    - No sharpening
    - No morphology
    - No aggressive denoising
    - Keeps 3-channel image
    - OPTIMIZATION: Skip denoising for clean scans
    - INS batch Section 14: Enhanced preprocessing for image-only scans
    """

    if image is None:
        return image

    # Ensure BGR 3-channel image
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # OPTIMIZATION: Skip denoising for clean/high-quality scans
    # Clean scans have high mean pixel value and low noise
    mean_val = image.mean()
    if mean_val > 200:
        # Clean scan — denoising would only slow us down
        return image

    # --- INS batch Section 14: Enhanced preprocessing for scanned docs ---
    # For very dark/noisy scans, apply contrast enhancement first
    if mean_val < 100:
        # Dark scan — apply CLAHE for contrast enhancement
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # VERY mild denoise for noisy/fax/low-quality scans only
    image = cv2.fastNlMeansDenoisingColored(
        image,
        None,
        h=3,   # extremely mild
        hColor=3,
        templateWindowSize=7,
        searchWindowSize=21
    )

    return image