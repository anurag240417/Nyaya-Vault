"""
A visual electronic-signature stamp: issuing officer's name, role,
department, and timestamp, rendered onto a PDF. This is option A from the
digital-signature design discussion - NOT a cryptographic signature, no
PKI, no certificate chain. It is exactly as legally weak as a typed name
on a document, and the stamp says so explicitly so nobody mistakes it for
more than it is. Shared by certificate_builder.py and notice_builder.py so
both use one implementation, not two copies that could drift apart.
"""
from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

_INK = colors.HexColor("#1a1a2e")
_HAIRLINE = colors.HexColor("#333333")

_stamp_label_style = ParagraphStyle(
    "StampLabel", fontName="Times-Bold", fontSize=9, leading=13, textColor=_INK,
)
_stamp_disclaimer_style = ParagraphStyle(
    "StampDisclaimer", fontName="Times-Italic", fontSize=7.5, leading=10, textColor=colors.grey,
)


def build_issuer_signature_stamp(*, name: str, designation: str, department: str | None) -> list:
    """Returns a list of flowables to append to a document's story. Escapes
    its own inputs - callers should NOT pre-escape these specific fields,
    to avoid the double-escaping bug class (turning a literal '&' the user
    typed into a visible '&amp;'). This is the one place these three
    fields get rendered, so escaping happens here, once.
    """
    name = _xml_escape(str(name))
    designation = _xml_escape(str(designation))
    department_label = _xml_escape(str(department)) if department else "General"
    timestamp = datetime.now().strftime("%d %B %Y, %H:%M IST")

    stamp_table = Table(
        [[Paragraph(
            f"<b>Digitally Signed by:</b> {name}<br/>"
            f"<b>Designation:</b> {designation}<br/>"
            f"<b>Department:</b> {department_label}<br/>"
            f"<b>Date/Time:</b> {timestamp}",
            _stamp_label_style,
        )]],
        colWidths=[85 * mm],
    )
    stamp_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, _INK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    return [
        Spacer(1, 10),
        HRFlowable(width="100%", color=_HAIRLINE, thickness=0.4, spaceAfter=6),
        stamp_table,
        Spacer(1, 3),
        Paragraph(
            "This is an electronic issuance stamp recording who generated this document and "
            "when, based on the account they were logged into. It is NOT a cryptographic digital "
            "signature and carries no certificate chain - it has the same legal weight as a typed "
            "name, not a Digital Signature Certificate under the Information Technology Act, 2000. "
            "It does not itself certify the accuracy of the content above.",
            _stamp_disclaimer_style,
        ),
    ]