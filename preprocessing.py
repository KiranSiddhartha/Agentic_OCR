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
    """

    if image is None:
        return image

    # Ensure BGR 3-channel image
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # VERY mild denoise (optional, safe)
    image = cv2.fastNlMeansDenoisingColored(
        image,
        None,
        h=3,   # extremely mild
        hColor=3,
        templateWindowSize=7,
        searchWindowSize=21
    )

    return image
