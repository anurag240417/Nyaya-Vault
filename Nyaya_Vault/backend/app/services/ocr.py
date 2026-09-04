"""
OCR / text extraction (SKILL.md Section 9).

Rules followed here:
  1. Attempt native text extraction first (pdfminer.six) before OCR.
  2. Only fall back to OCR when native extraction yields too little text
     to be a real digital PDF (i.e. it's a scan).
  3. Never mutate the original file — this module only ever reads bytes
     passed to it, never writes back to storage.
  4. OCR output is not automatically trusted as legally correct — the
     caller (app/workers/document_processing.py) stores it for officer
     review, it is never auto-applied as final metadata.

Documented simplification (hackathon scope, not hidden from anyone
reading this): the native-vs-OCR decision is made at whole-document
granularity, not per-page. A mixed document (some native pages, some
scanned pages) will OCR the entire thing if the average native yield
is low. Per-page granularity is a straightforward extension — see the
TODO in extract_text() — but wasn't worth the complexity for P1.
"""
import io
from dataclasses import dataclass

import pytesseract
from pdf2image import convert_from_bytes
from pdfminer.high_level import extract_text as _pdfminer_extract_text
from PIL import Image

# Below this many characters, a PDF's "native" text is almost certainly
# just embedded metadata/OCR-layer noise, not real content — treat it as
# a scan and OCR it properly.
_MIN_NATIVE_TEXT_CHARS = 50

# Bound how many pages we'll OCR — a hackathon demo document is a few
# pages; without this, a huge accidental upload could hang the worker.
_MAX_OCR_PAGES = 25


@dataclass
class ExtractionResult:
    text: str
    method: str  # "native" | "ocr" | "unsupported"
    pages_processed: int
    ocr_used: bool


def _extract_pdf_native(file_bytes: bytes) -> str:
    try:
        return _pdfminer_extract_text(io.BytesIO(file_bytes)) or ""
    except Exception:
        # A malformed/encrypted PDF can make pdfminer raise rather than
        # return empty text — treat that as "no native text" and let the
        # OCR fallback handle it, rather than failing the whole upload.
        return ""


def _extract_pdf_via_ocr(file_bytes: bytes) -> tuple[str, int]:
    images = convert_from_bytes(file_bytes, dpi=300)[:_MAX_OCR_PAGES]
    page_texts = [pytesseract.image_to_string(img) for img in images]
    return "\n\n".join(page_texts), len(images)


def _extract_image_via_ocr(file_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image)


def extract_text(file_bytes: bytes, mime_type: str) -> ExtractionResult:
    """
    TODO (future extension, not required for P1 demo scope): switch to
    per-page native-vs-OCR decisions using pdfminer's page_numbers param
    for mixed scanned/native documents.
    """
    if mime_type == "application/pdf":
        native_text = _extract_pdf_native(file_bytes)
        if len(native_text.strip()) >= _MIN_NATIVE_TEXT_CHARS:
            return ExtractionResult(
                text=native_text, method="native", pages_processed=0, ocr_used=False
            )

        ocr_text, page_count = _extract_pdf_via_ocr(file_bytes)
        return ExtractionResult(
            text=ocr_text, method="ocr", pages_processed=page_count, ocr_used=True
        )

    if mime_type in ("image/jpeg", "image/png", "image/tiff"):
        ocr_text = _extract_image_via_ocr(file_bytes)
        return ExtractionResult(text=ocr_text, method="ocr", pages_processed=1, ocr_used=True)

    return ExtractionResult(text="", method="unsupported", pages_processed=0, ocr_used=False)
