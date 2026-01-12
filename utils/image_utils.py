# utils/image_utils.py
# OPTIMAL: Balanced preprocessing (not too light, not too heavy)
import cv2
import numpy as np


def enhance_for_ocr(img, denoise_strength=10, sharpen=True, contrast_boost=False, morphology=False):
    """
    BALANCED preprocessing for insurance documents.
    Works for both clean and degraded docs.
    """
    if img is None:
        raise ValueError("Input image is None")

    # Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # === STEP 1: RESIZE (Optimal: 1800px) ===
    height, width = gray.shape
    target_height = 1800
    
    if height < target_height:
        scale = target_height / height
        new_width = int(width * scale)
        new_height = int(height * scale)
        gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

    # === STEP 2: DESKEW ===
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) > 0.5:
            (h, w) = gray.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            cos, sin = np.abs(M[0, 0]), np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            gray = cv2.warpAffine(gray, M, (new_w, new_h), 
                                  flags=cv2.INTER_CUBIC, 
                                  borderMode=cv2.BORDER_REPLICATE)

    # === STEP 3: DENOISE (Balanced) ===
    denoised = cv2.fastNlMeansDenoising(gray, None, h=denoise_strength, 
                                        templateWindowSize=7, searchWindowSize=21)

    # === STEP 4: CONTRAST (CLAHE) ===
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    if contrast_boost:
        enhanced = cv2.convertScaleAbs(enhanced, alpha=1.2, beta=10)

    # === STEP 5: SHARPEN ===
    if sharpen:
        gaussian = cv2.GaussianBlur(enhanced, (0, 0), 1.5)
        enhanced = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

    # === STEP 6: BINARIZATION ===
    _, binary_otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
    processed = cv2.max(binary_otsu, adaptive)

    # === STEP 7: MORPHOLOGY (Light) ===
    if morphology:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)

    # === STEP 8: BORDER REMOVAL ===
    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        padding = 15
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(processed.shape[1] - x, w + 2*padding)
        h = min(processed.shape[0] - y, h + 2*padding)
        processed = processed[y:y+h, x:x+w]

    return processed, None