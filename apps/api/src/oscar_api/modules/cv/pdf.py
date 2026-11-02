"""PDF rendering (docs/07 §3 step 7, docs/14 stable-template requirement).

One fixed template, decoupled from generation so export failures never touch
the underlying `CVVersion` (docs/03 §7).
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from oscar_api.modules.cv.models import CVVersion

_FONT_DIR = Path(__file__).with_name("fonts")


def render_pdf(cv_version: CVVersion) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", fname=str(_FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", style="B", fname=str(_FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()

    sections = cv_version.sections
    candidate = sections.get("candidate") or {}
    pdf.set_font("DejaVu", "B", 16)
    _text(pdf, candidate.get("name") or "Curriculum Vitae", height=9)
    pdf.set_font("DejaVu", "", 9)
    contact = [candidate.get(key) for key in ("email", "phone", "linkedin", "github", "portfolio")]
    for value in contact:
        if value:
            _text(pdf, str(value), height=5)
    pdf.ln(2)

    summary = sections.get("summary") or {}
    if summary.get("text"):
        _heading(pdf, "Summary")
        pdf.set_font("DejaVu", "", 10)
        _text(pdf, summary["text"])
        pdf.ln(2)

    experience = sections.get("experience") or []
    if experience:
        _heading(pdf, "Experience")
        for block in experience:
            pdf.set_font("DejaVu", "B", 10)
            title = " | ".join(filter(None, [block.get("title"), block.get("company")]))
            if title:
                _text(pdf, title)
            pdf.set_font("DejaVu", "", 9)
            if block.get("start_date"):
                end = "Present" if block.get("is_current") else (block.get("end_date") or "")
                _text(pdf, f"{block['start_date']} - {end}", height=5)
            pdf.set_font("DejaVu", "", 10)
            for bullet in block.get("bullets", []):
                _text(pdf, f"- {bullet['text']}")
            pdf.ln(2)
        pdf.ln(2)

    projects = sections.get("projects") or []
    if projects:
        _heading(pdf, "Projects")
        for block in projects:
            if block.get("name"):
                pdf.set_font("DejaVu", "B", 10)
                _text(pdf, block["name"])
            pdf.set_font("DejaVu", "", 10)
            for bullet in block.get("bullets", []):
                _text(pdf, f"- {bullet['text']}")
            pdf.ln(2)
        pdf.ln(2)

    skills = sections.get("skills") or []
    if skills:
        _heading(pdf, "Skills")
        pdf.set_font("DejaVu", "", 10)
        _text(pdf, ", ".join(skills))

    return bytes(pdf.output())


def _heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


def _text(pdf: FPDF, text: str, *, height: int = 6) -> None:
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")
