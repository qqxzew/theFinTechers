"""OPO draft export: Markdown (copilot.opo_draft.to_markdown) and PDF (reportlab). The PDF carries the DRAFT / SYNTHETIC banner on every page."""
from __future__ import annotations

import os
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
BANNER = "NÁVRH – SYNTETICKÁ DATA – není skutečné oznámení"


def _register_fonts() -> tuple[str, str]:
    for reg, bold in FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("StajSans", reg))
            pdfmetrics.registerFont(TTFont("StajSans-Bold", bold))
            return "StajSans", "StajSans-Bold"
    raise RuntimeError("no Unicode TTF font found (needed for Czech diacritics)")


def opo_to_pdf(opo: dict, path: str) -> str:
    regular, bold = _register_fonts()
    body = ParagraphStyle("body", fontName=regular, fontSize=10, leading=14)
    h = ParagraphStyle("h", fontName=bold, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=3)
    title = ParagraphStyle("t", fontName=bold, fontSize=14, leading=18, spaceAfter=6)

    def banner(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(bold, 8.5)
        canvas.setFillColorRGB(0.65, 0.2, 0.1)
        canvas.drawString(18 * mm, A4[1] - 10 * mm, BANNER)
        canvas.setFillColorRGB(0.4, 0.4, 0.4)
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"strana {doc.page}")
        canvas.restoreState()

    story = [Paragraph(escape(opo["title"]), title), Spacer(1, 4)]
    for s in opo["sections"]:
        story.append(Paragraph(escape(f"{s['no']}. {s['title']}"), h))
        story.append(Paragraph(escape(s["text"]).replace("\n", "<br/>"), body))
    if opo.get("section_v_violations"):
        story.append(Paragraph(escape("Upozornění kontroly (QA) – k vyřešení člověkem před použitím"), h))
        for v in opo["section_v_violations"]:
            story.append(Paragraph(escape(f"- {v.get('kind')}: {v.get('detail', '')} (věta {v.get('sentence')})"), body))
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm,
                            title=opo["title"], author="Stáj (draft generator)")
    doc.build(story, onFirstPage=banner, onLaterPages=banner)
    return path
