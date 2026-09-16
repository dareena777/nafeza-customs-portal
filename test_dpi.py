import os
import sys
import cv2
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from dpi import DPINormalizer


def load_document_pages(file_path: str, target_dpi: int = 300) -> list[np.ndarray]:
    """Reads a file (PDF or Image) and returns a list of RGB NumPy image arrays at 300 DPI."""
    ext = os.path.splitext(file_path)[1].lower()
    pages = []

    if ext == ".pdf":
        print(f"[*] Rendering PDF pages at {target_dpi} DPI...")
        doc = fitz.open(file_path)
        zoom = target_dpi / 72  # Base PDF resolution is 72 DPI
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(np.array(img))
    else:
        print("[*] Reading image file...")
        img_bgr = cv2.imread(file_path)
        if img_bgr is not None:
            pages.append(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

    return pages


def inspect_preprocessing(sample_path: str):
    if not os.path.exists(sample_path):
        print(f"[-] Error: File not found at '{sample_path}'")
        return

    print(f"[*] Processing document: {sample_path}")
    raw_pages = load_document_pages(sample_path, target_dpi=300)

    if not raw_pages:
        print(f"[-] Error: Could not read or render any pages from {sample_path}")
        return

    normalizer = DPINormalizer()

    for idx, img_rgb in enumerate(raw_pages, start=1):
        suffix = f"_page_{idx}" if len(raw_pages) > 1 else ""

        # Preprocess using both pipeline paths
        vision_ready = normalizer.enhance_for_vision(img_rgb)
        binary_ready = normalizer.enhance_for_ocr(img_rgb)

        # Output filenames
        vision_filename = f"test_vision_output{suffix}.jpg"
        binary_filename = f"test_binary_output{suffix}.jpg"

        # Save outputs locally
        cv2.imwrite(
            vision_filename, cv2.cvtColor(vision_ready, cv2.COLOR_RGB2BGR)
        )
        cv2.imwrite(binary_filename, binary_ready)

        print(f"[+] Page {idx} saved:")
        print(f"    - {vision_filename} (For Gemini Vision)")
        print(f"    - {binary_filename} (For Tesseract/EasyOCR)")

    print("\nVisual Evaluation Guidelines:")
    print(
        "  1. Open 'test_vision_output*.jpg' - Ensure 19-digit ACID & HS codes are sharp without color distortion."
    )
    print(
        "  2. Open 'test_binary_output*.jpg' - Verify background shadows/stamps didn't turn into black noise blocks."
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_preprocessing(sys.argv[1])
    else:
        print("Usage: python test_dpi.py <path_to_invoice.pdf_or_image>")