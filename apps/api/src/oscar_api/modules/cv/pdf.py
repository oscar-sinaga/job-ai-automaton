"""PDF rendering (docs/07 §3 step 7, docs/14 stable-template requirement).

One fixed template, decoupled from generation so export failures never touch
the underlying `CVVersion` (docs/03 §7).
"""

from __future__ import annotations

from fpdf import FPDF

from oscar_api.modules.cv.models import CVVersion

_CANDIDATE_NAME = "Oscar Michael Sinaga"


def render_pdf(cv_version: CVVersion) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _CANDIDATE_NAME, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, cv_version.label, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    sections = cv_version.sections
    summary = sections.get("summary") or {}
    if summary.get("text"):
        _heading(pdf, "Summary")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, summary["text"])
        pdf.ln(2)

    experience = sections.get("experience") or []
    if experience:
        _heading(pdf, "Experience")
        pdf.set_font("Helvetica", "", 11)
        for block in experience:
            for bullet in block.get("bullets", []):
                pdf.multi_cell(0, 6, f"- {bullet['text']}")
        pdf.ln(2)

    projects = sections.get("projects") or []
    if projects:
        _heading(pdf, "Projects")
        pdf.set_font("Helvetica", "", 11)
        for block in projects:
            for bullet in block.get("bullets", []):
                pdf.multi_cell(0, 6, f"- {bullet['text']}")
        pdf.ln(2)

    skills = sections.get("skills") or []
    if skills:
        _heading(pdf, "Skills")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, ", ".join(skills))

    return bytes(pdf.output())


def _heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
