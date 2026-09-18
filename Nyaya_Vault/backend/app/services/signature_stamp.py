"""
An electronic-signature stamp for generated documents: issuing officer's
name, role, department, timestamp, and - when a signature block is passed
in - a real ECDSA P-256 digital signature over the exact record being
certified (see app/services/signing.py). Shared by certificate_builder.py
and notice_builder.py so both use one implementation, not two copies that
could drift apart.
"""
from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape
from typing import Any

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
_sig_heading_style = ParagraphStyle(
    "SigHeading", fontName="Times-Bold", fontSize=8.5, leading=12, textColor=_INK, spaceBefore=6,
)
_sig_mono_style = ParagraphStyle(
    "SigMono", fontName="Courier", fontSize=7, leading=9.5, textColor=_INK, wordWrap="CJK",
)


def build_issuer_signature_stamp(
    *, name: str, designation: str, department: str | None, signature: dict[str, Any] | None = None,
) -> list:
    """Returns a list of flowables to append to a document's story. Escapes
    its own inputs - callers should NOT pre-escape these specific fields,
    to avoid the double-escaping bug class (turning a literal '&' the user
    typed into a visible '&amp;'). This is the one place these three
    fields get rendered, so escaping happens here, once.

    `signature`, when provided, is the dict returned by
    SigningService.sign_for_user: algorithm, public_key_pem,
    canonical_payload, signature_b64, fingerprint. Printing all of it means
    the document is independently verifiable without any dependency on this
    system - a verifier only needs a standard ECDSA implementation.
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

    flowables: list = [
        Spacer(1, 10),
        HRFlowable(width="100%", color=_HAIRLINE, thickness=0.4, spaceAfter=6),
        stamp_table,
    ]

    if signature:
        flowables += [
            Spacer(1, 5),
            Paragraph(f"Cryptographic signature ({_xml_escape(signature['algorithm'])})", _sig_heading_style),
            Paragraph(f"Key fingerprint: {_xml_escape(signature['fingerprint'])}", _sig_mono_style),
            Paragraph(f"Signature: {_xml_escape(signature['signature_b64'])}", _sig_mono_style),
            Paragraph(f"Public key: {_xml_escape(signature['public_key_pem'])}".replace("\n", "<br/>"), _sig_mono_style),
            Paragraph(
                f"Signed record (canonical): {_xml_escape(signature['canonical_payload'])}", _sig_mono_style,
            ),
        ]

    flowables += [
        Spacer(1, 3),
        Paragraph(
            (
                "The signature above is a real ECDSA P-256 digital signature computed over the exact "
                "canonical record printed here, using a private key issued to this user account and held, "
                "encrypted, by this system (private keys never leave the backend). Anyone can independently "
                "verify it - recompute nothing more than a standard ECDSA check against the public key and "
                "record shown above - without needing to trust this system at verification time. It is not "
                "issued by a licensed Certifying Authority and is not a Digital Signature Certificate under "
                "the Information Technology Act, 2000, but it is a genuine cryptographic signature, not a "
                "typed name."
            ) if signature else (
                "This is an electronic issuance stamp recording who generated this document and "
                "when, based on the account they were logged into. It is NOT a cryptographic digital "
                "signature and carries no certificate chain - it has the same legal weight as a typed "
                "name, not a Digital Signature Certificate under the Information Technology Act, 2000. "
                "It does not itself certify the accuracy of the content above."
            ),
            _stamp_disclaimer_style,
        ),
    ]
    return flowables
