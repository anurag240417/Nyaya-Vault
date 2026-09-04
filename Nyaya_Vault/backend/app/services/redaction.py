"""
AI-assisted redaction (SKILL.md Section 13).

CORE SECURITY PROPERTY — read this before touching apply_redactions():
a redaction that only draws a black box OVER text is not a redaction,
it's a visual trick. The original text is still selectable, copy-
pasteable, and extractable by anyone who opens the "redacted" PDF in a
text-aware tool. This is a real, repeatedly-documented failure mode in
actual government/legal document releases. This module uses PyMuPDF's
redaction annotations (page.add_redact_annot + page.apply_redactions),
which genuinely delete the underlying text/image content within the
redacted rectangle — not just paint over it. test_redaction_service.py
proves this by extracting text from a "redacted" PDF and asserting the
redacted value is actually gone, not just visually hidden.

WORKFLOW (on-demand, not automatic):
  1. Officer confirms extracted entities (existing /metadata/confirm
     flow) — Section 10: only confirmed entities are treated as
     authoritative enough to redact. An unconfirmed AI guess should
     not silently decide what gets blacked out of a legal document.
  2. Officer triggers suggestion generation for a specific document
     (POST /redactions/suggest) — this is NOT part of the automatic
     upload pipeline, because most documents are never prepared for
     disclosure; redaction is deliberate, not default.
  3. Officer reviews suggested regions, approves/rejects
     (POST /redactions/confirm — mirrors the existing entity-confirm
     pattern for consistency).
  4. Officer exports a redacted derivative (POST /redactions/export).
     The ORIGINAL document/version is never modified — a redacted
     copy is a new artifact, not an edit to evidence.

TWO LOCATION STRATEGIES, differing reliability:
  - Native-text PDFs: PyMuPDF's page.search_for(value) — exact,
    reliable, this is real text position data from the PDF itself.
  - Scanned PDFs / images: pytesseract.image_to_data() word-level
    bounding boxes, matched against the entity value. This is
    genuinely less reliable than the native path — OCR word
    segmentation doesn't always align cleanly with an entity's exact
    character span (see the word-joining logic below and its
    docstring for the specific failure modes). Flag this to the
    officer reviewing suggestions rather than pretending both paths
    are equally trustworthy.
"""
import io
import json
from dataclasses import dataclass

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

# Entity types considered personally-identifying by default. Case
# numbers, FIR numbers, legal sections, and dates are deliberately
# NOT in this set — they're case-identifying information a court/RTI
# disclosure typically still needs, not personal privacy data. This is
# a starting default, not a legal determination — the officer reviews
# every suggestion before it's applied, and can be given a way to pick
# additional entity types if this default set is wrong for a given
# document (that's a UI-layer decision, not this module's).
DEFAULT_REDACT_ENTITY_TYPES = {"PERSON", "PHONE", "EMAIL", "VEHICLE"}

_MIN_NATIVE_TEXT_CHARS = 50  # mirrors ocr_service.py's threshold


@dataclass
class RedactionRegion:
    page_number: int  # 0-indexed, matches PyMuPDF's convention
    x0: float
    y0: float
    x1: float
    y1: float
    entity_type: str
    value: str
    location_method: str  # "native" | "ocr" — surfaced so the UI can flag OCR-derived regions as less certain


def _is_native_pdf(file_bytes: bytes) -> bool:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return len(text.strip()) >= _MIN_NATIVE_TEXT_CHARS
    except Exception:
        return False


def _locate_regions_native_pdf(file_bytes: bytes, entities: list[tuple[str, str]]) -> list[RedactionRegion]:
    regions: list[RedactionRegion] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page_number, page in enumerate(doc):
            for entity_type, value in entities:
                for rect in page.search_for(value):
                    regions.append(
                        RedactionRegion(
                            page_number=page_number,
                            x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1,
                            entity_type=entity_type,
                            value=value,
                            location_method="native",
                        )
                    )
    finally:
        doc.close()
    return regions


def _words_bbox_union(words: list[dict]) -> tuple[float, float, float, float]:
    x0 = min(w["left"] for w in words)
    y0 = min(w["top"] for w in words)
    x1 = max(w["left"] + w["width"] for w in words)
    y1 = max(w["top"] + w["height"] for w in words)
    return x0, y0, x1, y1


def _levenshtein(a: str, b: str) -> int:
    """Standard DP edit distance. Values here are short (names/emails), so no need for anything fancier."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _fuzzy_acceptable(target: str, candidate: str) -> bool:
    """
    Whether a non-exact OCR-derived string is close enough to count as a
    match. Deliberately asymmetric and conservative:
      - Pure-digit values (phone numbers, etc.) require an EXACT match.
        A fuzzy digit match risks either missing a real match or, worse,
        matching the wrong number — and unlike a name, there's no
        semantic redundancy in a digit string to fall back on.
      - Short values (<6 chars) require exact match — not enough
        characters for "one typo" to be a meaningful signal vs. noise.
      - Longer alphabetic values (names, emails) tolerate edit distance
        1 — covers the single-character OCR misreads actually observed
        in testing (e.g. "Desai" -> "Desal", i/l confusion) without
        opening the door to matching a genuinely different word.
    A missed match here fails safe: the officer reviewing suggestions
    sees one fewer redaction than expected and can investigate, rather
    than the system silently redacting the wrong text.
    """
    if target.isdigit():
        return False
    if len(target) < 6:
        return False
    return _levenshtein(target, candidate) <= 1


def _find_value_in_ocr_words(value: str, words: list[dict]) -> tuple[float, float, float, float] | None:
    """
    Matches an entity value against a run of consecutive OCR words by
    comparing normalized (whitespace-stripped) concatenation. This is a
    best-effort heuristic, not exact matching — Tesseract sometimes
    splits a value like "9876543210" or "214/2026" into more than one
    "word" token, and rarely merges two real words into one. Handles
    the common case (value is 1-4 consecutive words) correctly; a value
    OCR'd with an internal stray space in a single visual word (see the
    NER regression test for exactly this kind of OCR artifact) may
    still be found since normalization strips all whitespace before
    comparing.

    Tries an exact match first (preferred, unambiguous); falls back to
    a conservative fuzzy match (see _fuzzy_acceptable) only if no exact
    match exists anywhere in the window — found necessary via live
    testing on a real Windows Tesseract build that misread "Desai" as
    "Desal" (single-character OCR error), which a different Tesseract
    build/platform did not reproduce.
    """
    normalized_target = value.replace(" ", "").replace("\t", "").lower()
    n = len(words)

    best_fuzzy: tuple[float, float, float, float] | None = None
    for start in range(n):
        concatenated = ""
        for end in range(start, min(start + 6, n)):  # cap window — a value won't span >6 OCR words
            concatenated += words[end]["text"]
            normalized_candidate = concatenated.replace(" ", "").lower()
            if normalized_candidate == normalized_target:
                return _words_bbox_union(words[start : end + 1])
            if best_fuzzy is None and _fuzzy_acceptable(normalized_target, normalized_candidate):
                best_fuzzy = _words_bbox_union(words[start : end + 1])
    return best_fuzzy


def _locate_regions_ocr(
    file_bytes: bytes, mime_type: str, entities: list[tuple[str, str]]
) -> list[RedactionRegion]:
    """
    IMPORTANT coordinate-space handling: OCR word boxes come from
    convert_from_bytes' 300dpi pixel-space render. For a PDF, the page
    itself is in POINT space (72 points/inch) — point dimensions do NOT
    equal pixel dimensions except by coincidence, so pixel coordinates
    must be scaled to the page's actual point size before being handed
    to fitz (which operates in points). Skipping this scaling would
    silently redact the wrong region on any real scanned PDF whose page
    size in points differs from its rendered pixel size — exactly the
    kind of bug that defeats the entire point of this feature without
    being visually obvious in a quick check.

    Standalone images (not embedded in a PDF) have no separate "point
    space" — regions stay in the image's own pixel coordinates, which
    is what apply_redactions' image branch expects.
    """
    if mime_type == "application/pdf":
        images = convert_from_bytes(file_bytes, dpi=300)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_rects = [doc[i].rect for i in range(len(doc))]
        doc.close()
    else:
        images = [Image.open(io.BytesIO(file_bytes))]
        page_rects = [None]

    regions: list[RedactionRegion] = []
    for page_number, image in enumerate(images):
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words = [
            {"text": data["text"][i], "left": data["left"][i], "top": data["top"][i],
             "width": data["width"][i], "height": data["height"][i]}
            for i in range(len(data["text"]))
            if data["text"][i].strip()
        ]

        page_rect = page_rects[page_number] if page_number < len(page_rects) else None
        if page_rect is not None:
            scale_x = page_rect.width / image.width
            scale_y = page_rect.height / image.height
        else:
            scale_x = scale_y = 1.0

        for entity_type, value in entities:
            bbox = _find_value_in_ocr_words(value, words)
            if bbox:
                px0, py0, px1, py1 = bbox
                regions.append(
                    RedactionRegion(
                        page_number=page_number,
                        x0=px0 * scale_x, y0=py0 * scale_y,
                        x1=px1 * scale_x, y1=py1 * scale_y,
                        entity_type=entity_type,
                        value=value,
                        location_method="ocr",
                    )
                )
    return regions


def suggest_redactions(
    file_bytes: bytes,
    mime_type: str,
    confirmed_entities: list[tuple[str, str]],
    redact_entity_types: set[str] = DEFAULT_REDACT_ENTITY_TYPES,
) -> list[RedactionRegion]:
    """
    confirmed_entities: list of (entity_type, value) — caller is
    responsible for passing only DocumentEntity rows where
    confirmed=True (see module docstring, Section 10).
    """
    targeted = [(t, v) for t, v in confirmed_entities if t in redact_entity_types]
    if not targeted:
        return []

    if mime_type == "application/pdf":
        if _is_native_pdf(file_bytes):
            return _locate_regions_native_pdf(file_bytes, targeted)
        return _locate_regions_ocr(file_bytes, mime_type, targeted)

    if mime_type in ("image/jpeg", "image/png", "image/tiff"):
        return _locate_regions_ocr(file_bytes, mime_type, targeted)

    return []


def region_to_json(region: RedactionRegion) -> str:
    return json.dumps(
        {
            "page_number": region.page_number,
            "x0": region.x0, "y0": region.y0, "x1": region.x1, "y1": region.y1,
            "location_method": region.location_method,
            "value": region.value,
        }
    )


def region_from_json(region_json: str, entity_type: str) -> RedactionRegion:
    """entity_type comes from the caller's RedactionSuggestion.entity_type column; value is embedded in the JSON itself."""
    data = json.loads(region_json)
    return RedactionRegion(
        page_number=data["page_number"],
        x0=data["x0"], y0=data["y0"], x1=data["x1"], y1=data["y1"],
        entity_type=entity_type,
        value=data.get("value", ""),
        location_method=data.get("location_method", "unknown"),
    )


def apply_redactions(file_bytes: bytes, mime_type: str, regions: list[RedactionRegion]) -> bytes:
    """
    Produces a NEW derivative — never mutates the caller's bytes or
    touches storage. Caller (the API layer) is responsible for storing
    this as a distinct artifact, not overwriting the original version.
    """
    if not regions:
        raise ValueError("apply_redactions called with zero regions — refusing to produce a no-op 'redacted' file that would misleadingly claim to be safe to disclose")

    if mime_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            for region in regions:
                page = doc[region.page_number]
                rect = fitz.Rect(region.x0, region.y0, region.x1, region.y1)
                # fill=(0,0,0): black box drawn AFTER apply_redactions()
                # removes the underlying content — this is genuine
                # deletion, not an overlay. See module docstring.
                page.add_redact_annot(rect, fill=(0, 0, 0))
            for page in doc:
                page.apply_redactions()
            output = doc.tobytes()
        finally:
            doc.close()
        return output

    if mime_type in ("image/jpeg", "image/png", "image/tiff"):
        # Images have no separate "text layer" to leak — a burned-in
        # black rectangle on raster pixels is genuinely irreversible,
        # unlike a vector overlay on a PDF would be.
        from PIL import ImageDraw

        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image)
        for region in regions:
            draw.rectangle([region.x0, region.y0, region.x1, region.y1], fill="black")
        buffer = io.BytesIO()
        image_format = "JPEG" if mime_type == "image/jpeg" else ("PNG" if mime_type == "image/png" else "TIFF")
        image.save(buffer, format=image_format)
        return buffer.getvalue()

    raise ValueError(f"Redaction not supported for mime_type={mime_type}")