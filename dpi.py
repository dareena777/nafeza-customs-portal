import cv2
import fitz  # PyMuPDF
import numpy as np
from PIL import Image


class DPINormalizer:
    @staticmethod
    def enhance_for_vision(image_np: np.ndarray) -> np.ndarray:
        """
        Enhances luminance contrast via CLAHE while preserving RGB colors 
        for Multi-modal Vision LLMs (Gemini 3.6-Flash).
        """
        if len(image_np.shape) == 2:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)

        # Convert RGB -> LAB space to sharpen text without distorting background colors
        lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)

        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)

    @staticmethod
    def enhance_for_ocr(image_np: np.ndarray) -> np.ndarray:
        """
        Applies bilateral filtering and adaptive binarization 
        for traditional OCR text engines (Tesseract / EasyOCR).
        """
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_np

        denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        return cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8,
        )