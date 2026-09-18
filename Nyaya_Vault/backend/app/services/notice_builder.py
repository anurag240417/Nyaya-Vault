"""
Builds a legal notice PDF for any of the 16 registered notice types
(app/services/notice_types.py). Styled to match certificate_builder.py for
visual consistency across every document this system generates, without
reproducing the State Emblem of India or any government letterhead.

The system assembles verified structure: case reference, recipient details,
the notice type's structured fields, and (where one genuinely and commonly
applies) the real name of the governing Act. It never authors the
substantive legal content itself - the grounds, allegations, and demand are
always the free-text "body" the drafting officer writes. This mirrors
exactly how the Section 63 certificate separates system-verified facts from
human-attested judgment.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.notice_types import NOTICE_TYPES
from app.services.signature_stamp import build_issuer_signature_stamp

_INK = colors.HexColor("#1a1a2e")
_RULE = colors.HexColor("#8b1a1a")
_HAIRLINE = colors.HexColor("#333333")
_PAGE_MARGIN = 20 * mm


def build_legal_notice_pdf(
    *,
    notice_type: str,
    case_number: str,
    case_title: str,
    sender_name: str,
    sender_designation: str,
    sender_department: str | None,
    recipient_name: str,
    recipient_address: str,
    fields: dict[str, str],
    body: str,
    place: str,
    signature: dict[str, Any] | None = None,
) -> bytes:
    spec = NOTICE_TYPES[notice_type]  # KeyError deliberately propagates - caller must validate first
    notice_no = f"NV/NOTICE/{notice_type[:4]}/{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Same reasoning as certificate_builder.py: ReportLab's Paragraph text
    # is markup-aware, so every free-text field a user can influence must be
    # escaped before it reaches a Paragraph, or a well-formed tag renders as
    # live formatting instead of literal, visible text. Escaped once here,
    # not re-escaped anywhere else in this function.
    case_number = _xml_escape(str(case_number))
    case_title = _xml_escape(str(case_title))
    recipient_name = _xml_escape(str(recipient_name))
    recipient_address = _xml_escape(str(recipient_address))
    body = _xml_escape(str(body))
    place = _xml_escape(str(place))
    escaped_fields = {k: _xml_escape(str(v)) for k, v in fields.items()}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=_PAGE_MARGIN, bottomMargin=_PAGE_MARGIN + 8 * mm,
        leftMargin=_PAGE_MARGIN, rightMargin=_PAGE_MARGIN,
    )
    styles = getSampleStyleSheet()

    letterhead_style = ParagraphStyle(
        "Letterhead", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=13, textColor=_INK, alignment=TA_CENTER, spaceAfter=6,
    )
    notice_no_style = ParagraphStyle(
        "NoticeNo", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=9, textColor=_INK, alignment=TA_RIGHT,
    )
    title_style = ParagraphStyle(
        "NoticeTitle", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=15, textColor=_INK, alignment=TA_CENTER, spaceBefore=6, spaceAfter=4, leading=19,
    )
    statute_style = ParagraphStyle(
        "Statute", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=9.5, textColor=_RULE, alignment=TA_CENTER, spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "NoticeHeading", parent=styles["Normal"], fontName="Times-Bold",
        fontSize=11, textColor=_RULE, spaceBefore=14, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "NoticeBody", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=10, leading=15, textColor=_INK,
    )
    small_style = ParagraphStyle(
        "NoticeSmall", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=8, textColor=colors.grey,
    )

    story = []
    story.append(Paragraph("NYAYA VAULT", letterhead_style))
    story.append(HRFlowable(width="100%", color=_RULE, thickness=1.4, spaceAfter=2))
    story.append(HRFlowable(width="100%", color=_RULE, thickness=0.4, spaceAfter=8))

    story.append(Paragraph(f"Notice No.: {notice_no}", notice_no_style))
    story.append(Paragraph(_xml_escape(spec.title).upper(), title_style))
    if spec.statute_reference:
        story.append(Paragraph(f"Issued under: {_xml_escape(spec.statute_reference)}", statute_style))
    else:
        story.append(Spacer(1, 6))

    story.append(Paragraph(f"IN THE MATTER OF: <b>{case_title}</b> &nbsp;(Case No. {case_number})", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("To,", body_style))
    story.append(Paragraph(f"<b>{recipient_name}</b><br/>{recipient_address}", body_style))
    story.append(Spacer(1, 10))

    if spec.fields:
        story.append(Paragraph("Particulars", heading_style))
        rows = [
            [f.label, escaped_fields.get(f.key, "") or "-"]
            for f in spec.fields
        ]
        story.append(_two_col_table(rows))
        story.append(Spacer(1, 6))

    story.append(Paragraph("Notice", heading_style))
    for paragraph_text in body.split("\n"):
        if paragraph_text.strip():
            story.append(Paragraph(paragraph_text, body_style))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Place: {place} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: {datetime.now().strftime('%d %B %Y')}",
        body_style,
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", color=_HAIRLINE, thickness=0.4, spaceAfter=6))
    story.append(Paragraph(
        f"Notice No. {notice_no} was generated by the Nyaya Vault system from its own stored case "
        "records. The particulars and notice text above were provided by the issuing officer and "
        "have not been independently verified by the system - review before service or filing.",
        small_style,
    ))
    story.extend(build_issuer_signature_stamp(
        name=sender_name, designation=sender_designation, department=sender_department, signature=signature,
    ))

    def _page_frame(canvas, _doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(_RULE)
        canvas.setLineWidth(1.2)
        canvas.rect(14 * mm, 14 * mm, w - 28 * mm, h - 28 * mm)
        canvas.setFont("Times-Italic", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(w / 2, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return buffer.getvalue()


_cell_label_style = ParagraphStyle("NoticeCellLabel", fontName="Times-Bold", fontSize=9.5, leading=12, textColor=_INK)
_cell_value_style = ParagraphStyle("NoticeCellValue", fontName="Times-Roman", fontSize=9.5, leading=12, textColor=_INK)


def _two_col_table(rows: list[list[str]]) -> Table:
    wrapped_rows = [
        [Paragraph(str(label), _cell_label_style), Paragraph(str(value), _cell_value_style)]
        for label, value in rows
    ]
    table = Table(wrapped_rows, colWidths=[60 * mm, 100 * mm])
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