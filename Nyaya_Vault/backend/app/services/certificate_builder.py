"""
Builds a Section 63 (Bharatiya Sakshya Adhiniyam, 2023) electronic evidence
certificate PDF, styled to look like a formal legal/government certificate
(double-ruled border, serif typography, certificate number, seal-placeholder
box) - WITHOUT reproducing the State Emblem of India or any government
department's name or letterhead.Everything here is generic formal-document styling
built from the case's own data.

"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_INK = colors.HexColor("#1a1a2e")       # near-black navy, formal document ink
_RULE = colors.HexColor("#8b1a1a")      # deep maroon rule, common on Indian legal stationery
_HAIRLINE = colors.HexColor("#333333")
_PAGE_MARGIN = 20 * mm
_BORDER_INSET = 10 * mm  # how far the drawn border sits from the page edge


def build_section63_certificate_pdf(
    *,
    case_number: str,
    case_title: str,
    document_title: str,
    document_type: str | None,
    document_id: str,
    version_number: int,
    sha256_hash: str,
    file_size_bytes: int,
    mime_type: str,
    created_at: str,
    device_operator_name: str,
    device_operator_designation: str,
    expert_name: str,
    expert_designation: str,
    expert_qualification: str,
    place: str,
    audit_events: list[dict[str, Any]],
) -> bytes:
    certificate_no = f"NV/S63/{document_id[:8].upper()}/{datetime.now().year}"

    # ReportLab's Paragraph text is markup-aware (a small HTML-like subset) -
    # any of these fields that reach a Paragraph unescaped lets whoever fills
    # them in (the certificate-generation form's free-text fields, or a
    # username) inject live formatting into what's meant to be a neutral,
    # court-facing certificate. A well-formed tag like
    # <font color="red" size="30">CASE DISMISSED</font> renders exactly as
    # written, silently - it doesn't even raise like a malformed one would.
    # Escaping here, once, before anything is used, closes that off for
    # every field this function touches.
    case_number = _xml_escape(str(case_number))
    case_title = _xml_escape(str(case_title))
    document_title = _xml_escape(str(document_title))
    document_type = _xml_escape(str(document_type)) if document_type else document_type
    device_operator_name = _xml_escape(str(device_operator_name))
    device_operator_designation = _xml_escape(str(device_operator_designation))
    expert_name = _xml_escape(str(expert_name))
    expert_designation = _xml_escape(str(expert_designation))
    expert_qualification = _xml_escape(str(expert_qualification))
    place = _xml_escape(str(place))
    audit_events = [
        {**e, "actor_username": _xml_escape(str(e.get("actor_username", "system")))}
        for e in audit_events
    ]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=_PAGE_MARGIN, bottomMargin=_PAGE_MARGIN + 8 * mm,
        leftMargin=_PAGE_MARGIN, rightMargin=_PAGE_MARGIN,
    )
    styles = getSampleStyleSheet()

    letterhead_style = ParagraphStyle(
        "Letterhead", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=13, textColor=_INK, alignment=TA_CENTER, spaceAfter=1,
    )
    tagline_style = ParagraphStyle(
        "Tagline", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=8.5, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=6,
    )
    cert_no_style = ParagraphStyle(
        "CertNo", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=9, textColor=_INK, alignment=TA_RIGHT,
    )
    title_style = ParagraphStyle(
        "CertTitle", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=15, textColor=_INK, alignment=TA_CENTER,
        spaceBefore=6, spaceAfter=4, leading=19,
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=9, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "CertHeading", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=11, textColor=_RULE, spaceBefore=14, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "CertBody", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=10, leading=15, textColor=_INK,
    )
    small_style = ParagraphStyle(
        "CertSmall", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=8, textColor=colors.grey,
    )

    story = []

    # ---- Letterhead ----
    story.append(Paragraph("NYAYA VAULT", letterhead_style))
    story.append(Paragraph(
        "Secure Digital Evidence &amp; Case Management System",
        tagline_style,
    ))
    story.append(HRFlowable(width="100%", color=_RULE, thickness=1.4, spaceAfter=2))
    story.append(HRFlowable(width="100%", color=_RULE, thickness=0.4, spaceAfter=8))

    story.append(Paragraph(f"Certificate No.: {certificate_no}", cert_no_style))
    story.append(Paragraph(
        "CERTIFICATE UNDER SECTION 63<br/>BHARATIYA SAKSHYA ADHINIYAM, 2023",
        title_style,
    ))
    story.append(Paragraph(
        "(Certificate for admissibility of an electronic record, in the form "
        "prescribed by the Schedule to the Act)",
        subtitle_style,
    ))

    story.append(Paragraph(
        f"IN THE MATTER OF: <b>{case_title}</b> &nbsp;(Case No. {case_number})",
        body_style,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("1.&nbsp;&nbsp;Identification of the electronic record", heading_style))
    identity_rows = [
        ["Case number", case_number],
        ["Case title", case_title],
        ["Document title", document_title],
        ["Document type", document_type or "Unclassified"],
        ["Document ID", document_id],
        ["Version certified", f"v{version_number}"],
        ["File size", f"{file_size_bytes:,} bytes"],
        ["MIME type", mime_type],
        ["Recorded creation time", created_at],
    ]
    story.append(_two_col_table(identity_rows))

    story.append(Paragraph("2.&nbsp;&nbsp;Manner of production of the electronic record", heading_style))
    story.append(Paragraph(
        "This electronic record was produced and is maintained by the Nyaya "
        "Vault secure case management system. Upon upload, the system computed "
        "a SHA-256 cryptographic hash of the exact uploaded bytes, stored the "
        "record in immutable, versioned object storage, and appended a "
        "hash-chained audit log entry for the upload event. No modification "
        "to a stored version is possible through the system; any subsequent "
        "change to the underlying document is captured only as a new, "
        "separately hashed version, leaving the original intact and available.",
        body_style,
    ))

    story.append(Paragraph("3.&nbsp;&nbsp;Hash value and algorithm (per Section 63(4)(c))", heading_style))
    story.append(_two_col_table([
        ["Hash algorithm", "SHA-256"],
        ["Hash value", sha256_hash],
    ], mono_second_col=True))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The above hash value was computed at the time of upload and can be "
        "independently recomputed from the stored file to verify that the "
        "record has not been altered since. The system's Audit Integrity "
        "function additionally verifies the unbroken hash-chain of every "
        "recorded event for this document.",
        body_style,
    ))

    story.append(Paragraph("4.&nbsp;&nbsp;Custody events recorded for this document", heading_style))
    if audit_events:
        rows = [["#", "Event", "Actor", "Time"]]
        for e in audit_events[:15]:
            rows.append([
                str(e.get("sequence", "")),
                str(e.get("action", "")).replace("_", " ").title(),
                str(e.get("actor_username", "system")),
                str(e.get("timestamp", "")),
            ])
        story.append(_custody_table(rows))
        if len(audit_events) > 15:
            story.append(Paragraph(
                f"...and {len(audit_events) - 15} further recorded event(s), "
                "available in full in the system's Audit Trail.",
                small_style,
            ))
    else:
        story.append(Paragraph("No custody events recorded.", body_style))

    story.append(Paragraph("PART A — Certificate of the person in charge of the device", heading_style))
    story.append(Paragraph(
        f"I, <b>{device_operator_name}</b> ({device_operator_designation}), being a person "
        "occupying a responsible position in relation to the operation of the "
        "system referred to above, certify that the electronic record described "
        "in Clause 1 was produced by that system in the course of its regular "
        "use, that the system was operating properly at the material time, and "
        "that the information contained in the record accurately reproduces "
        "the information originally supplied to the system.",
        body_style,
    ))
    story.append(Spacer(1, 10))
    story.append(_signature_and_seal_block("Signature of device operator"))

    story.append(Paragraph("PART B — Certificate of the expert", heading_style))
    story.append(Paragraph(
        f"I, <b>{expert_name}</b> ({expert_designation}, {expert_qualification}), have "
        "examined the electronic record and the hash value referred to in "
        "Clause 3 above, obtained using the SHA-256 algorithm, and certify that "
        "the said hash value correctly and uniquely represents the contents of "
        "the electronic record as stored at the time of this certificate.",
        body_style,
    ))
    story.append(Spacer(1, 10))
    story.append(_signature_and_seal_block("Signature of expert"))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"Place: {place} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "
        f"Date: {datetime.now().strftime('%d %B %Y')}",
        body_style,
    ))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=_HAIRLINE, thickness=0.4, spaceAfter=6))
    story.append(Paragraph(
        f"Certificate No. {certificate_no} was generated by the Nyaya Vault "
        "system from its own stored records and audit trail. It is a draft "
        "aid for legal proceedings and does not substitute for independent "
        "verification by the signing expert before submission to a court.",
        small_style,
    ))

    def _page_frame(canvas, _doc):
        canvas.saveState()
        w, h = A4
        # Double-ruled border, common on formal certificates/stamp paper.
        canvas.setStrokeColor(_RULE)
        canvas.setLineWidth(1.4)
        canvas.rect(_BORDER_INSET, _BORDER_INSET, w - 2 * _BORDER_INSET, h - 2 * _BORDER_INSET)
        canvas.setStrokeColor(_HAIRLINE)
        canvas.setLineWidth(0.5)
        inner = _BORDER_INSET + 2.2 * mm
        canvas.rect(inner, inner, w - 2 * inner, h - 2 * inner)
        # Page number footer, inside the border.
        canvas.setFont("Times-Italic", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(w / 2, _BORDER_INSET + 6 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return buffer.getvalue()


_cell_label_style = ParagraphStyle(
    "CellLabel", fontName="Times-Bold", fontSize=9.5, leading=12, textColor=_INK,
)
_cell_value_style = ParagraphStyle(
    "CellValue", fontName="Times-Roman", fontSize=9.5, leading=12, textColor=_INK,
)
_cell_mono_style = ParagraphStyle(
    "CellMono", fontName="Courier", fontSize=8, leading=11, textColor=_INK,
    wordWrap="CJK",  # allows breaking a long unbroken hash string mid-line
)


def _two_col_table(rows: list[list[str]], mono_second_col: bool = False) -> Table:
    value_style = _cell_mono_style if mono_second_col else _cell_value_style
    wrapped_rows = [
        [Paragraph(str(label), _cell_label_style), Paragraph(str(value), value_style)]
        for label, value in rows
    ]
    table = Table(wrapped_rows, colWidths=[55 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.6, _HAIRLINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9c9c9")),
    ]))
    return table


_custody_header_style = ParagraphStyle(
    "CustodyHeader", fontName="Times-Bold", fontSize=8.5, leading=11, textColor=_INK,
)
_custody_cell_style = ParagraphStyle(
    "CustodyCell", fontName="Times-Roman", fontSize=8.5, leading=11, textColor=_INK,
)


def _custody_table(rows: list[list[str]]) -> Table:
    header, *body = rows
    wrapped = [[Paragraph(str(c), _custody_header_style) for c in header]]
    wrapped += [[Paragraph(str(c), _custody_cell_style) for c in row] for row in body]
    table = Table(wrapped, colWidths=[12 * mm, 55 * mm, 45 * mm, 48 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2ede6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOX", (0, 0), (-1, -1), 0.6, _HAIRLINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9c9c9")),
    ]))
    return table


def _signature_and_seal_block(label: str) -> Table:
    signature = Table(
        [["_________________________"], [label], ["Name & Date"]],
        colWidths=[75 * mm],
    )
    signature.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, 1), "Times-Bold"),
        ("TOPPADDING", (0, 1), (0, -1), 2),
    ]))

    seal_box = Table([["AFFIX SEAL /\nSTAMP HERE"]], colWidths=[30 * mm], rowHeights=[20 * mm])
    seal_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Times-Italic"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
    ]))

    outer = Table([[signature, seal_box]], colWidths=[110 * mm, 40 * mm])
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return outer