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