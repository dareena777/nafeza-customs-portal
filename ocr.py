import io
import time
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError

# Local imports
from dpi import DPINormalizer
from schema import InvoiceDataResponse


def resolve_schema_refs(schema_dict: dict) -> dict:
    """Recursively resolves $ref pointers in Pydantic schemas for Gemini API compliance."""
    if "$defs" not in schema_dict:
        return schema_dict

    defs = schema_dict.pop("$defs")

    def _replace_refs(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_key = obj["$ref"].split("/")[-1]
                return _replace_refs(defs[ref_key])
            return {k: _replace_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_replace_refs(item) for item in obj]
        return obj

    return _replace_refs(schema_dict)


def preprocess_file_bytes(file_bytes: bytes, file_type: str, normalizer: DPINormalizer) -> list[Image.Image]:
    """Processes raw document bytes into enhanced PIL images using DPINormalizer."""
    processed_images = []
    
    if "pdf" in file_type.lower():
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        zoom = 300 / 72  # Target 300 DPI scale
        mat = fitz.Matrix(zoom, zoom)
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            enhanced_np = normalizer.enhance_for_vision(img_np)
            processed_images.append(Image.fromarray(enhanced_np))
    else:
        pil_img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        img_np = np.array(pil_img)
        enhanced_np = normalizer.enhance_for_vision(img_np)
        processed_images.append(Image.fromarray(enhanced_np))

    return processed_images


def extract_with_gemini(images: list[Image.Image], api_key: str) -> InvoiceDataResponse:
    """Sends enhanced images to Gemini for structured extraction with retry logic and active model fallbacks."""
    client = genai.Client(api_key=api_key)

    contents = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        contents.append(
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
        )

    prompt = (
        "You are an expert Nafeza Egyptian Customs Document Intelligence Engine.\n"
        "Analyze all provided invoice images and extract data strictly matching the requested schema:\n"
        "1. Capture the 19-digit Egyptian ACID number accurately.\n"
        "2. Capture the 9-digit Egyptian Importer Tax ID accurately.\n"
        "3. Extract all line items into the table with exact descriptions, HS codes, quantities, unit prices, and line totals.\n"
        "4. Extract header metadata: invoice number, invoice date, currency, origin port, destination port, exporter address, and printed bill total."
    )
    contents.append(prompt)

    raw_schema = InvoiceDataResponse.model_json_schema()
    clean_schema = resolve_schema_refs(raw_schema)

    config = types.GenerateContentConfig(
        system_instruction="Extract all invoice details strictly according to the provided JSON schema.",
        response_mime_type="application/json",
        response_schema=clean_schema,
        temperature=0.0,
    )

    # Valid production Gemini models in fallback order
    candidate_models = ["gemini-3.6-flash", "gemini-1.5-flash"]
    last_exception = None

    for model in candidate_models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return InvoiceDataResponse.model_validate_json(response.text)
            
            except APIError as e:
                last_exception = e
                # Retry on 503 high load spikes or 429 rate limits
                if getattr(e, "code", None) in [429, 503] or "503" in str(e) or "429" in str(e):
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    break
            except Exception as e:
                last_exception = e
                break

    raise last_exception