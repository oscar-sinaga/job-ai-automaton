"""Text-based A4 resume following the owner's supplied single-column layout.

Presentation uses immutable, server-built version snapshots, never live profile
records or model-invented education and credentials.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, cast

from fpdf import FPDF
from fpdf.enums import MethodReturnValue

from oscar_api.modules.cv.models import CVVersion

_FONT_DIR = Path(__file__).with_name("fonts")
_BODY_SIZE = 9
_LINE = 4.5


def render_pdf(cv_version: CVVersion) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(9, 11, 9)
    pdf.set_auto_page_break(auto=True, margin=11)
    pdf.add_font("DejaVu", fname=str(_FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", style="B", fname=str(_FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_title("Resume")
    pdf.add_page()
    sections = cv_version.sections
    candidate = sections.get("candidate") or {}
    pdf.set_font("DejaVu", "B", 18)
    _text(pdf, str(candidate.get("name") or "Curriculum Vitae").upper(), height=8)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(110, 110, 110)
    contact = [candidate.get(key) for key in ("phone", "email", "linkedin", "github", "portfolio")]
    if any(contact):
        _text(pdf, " | ".join(str(value) for value in contact if value), height=4)
    if candidate.get("location"):
        _text(pdf, str(candidate["location"]), height=4)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", _BODY_SIZE)
    summary = sections.get("summary") or {}
    if summary.get("text"):
        _text(pdf, summary["text"])
    pdf.ln(2)

    experience = sections.get("experience") or []
    if experience:
        _heading(pdf, "Work Experiences")
        for block in sorted(
            experience, key=lambda item: item.get("start_date") or "", reverse=True
        ):
            _entry_header(
                pdf,
                str(block.get("company") or block.get("title") or "Experience"),
                _date_range(block),
            )
            if block.get("location"):
                pdf.set_text_color(110, 110, 110)
                _text(pdf, str(block["location"]))
                pdf.set_text_color(0, 0, 0)
            if block.get("title"):
                _text(pdf, str(block["title"]))
            for bullet in block.get("bullets", []):
                _bullet(pdf, bullet["text"])
            pdf.ln(2)

    education = sections.get("education") or []
    if education:
        _heading(pdf, "Education Level")
        for item in education:
            _entry_header(pdf, str(item["institution"]), _date_range(item))
            degree = " | ".join(str(item[key]) for key in ("degree", "field") if item.get(key))
            if degree:
                _text(pdf, degree)
            pdf.ln(2)

    projects = sections.get("projects") or []
    if projects:
        _heading(pdf, "Projects & Other Experience")
        for block in projects:
            _entry_header(pdf, str(block.get("name") or "Project"), _date_range(block))
            for bullet in block.get("bullets", []):
                _bullet(pdf, bullet["text"])
            pdf.ln(2)

    skills = sections.get("skills") or []
    certifications = sections.get("certifications") or []
    if skills or certifications:
        _heading(pdf, "Skills, Certifications & Other Experience")
        if skills:
            _bullet(pdf, "Hard Skills: " + ", ".join(skills))
        for item in certifications:
            details = " | ".join(str(item[key]) for key in ("name", "issuer") if item.get(key))
            issued = _date(item.get("issued_date"))
            _bullet(pdf, details + (f" ({issued})" if issued else ""))

    return bytes(pdf.output())


def _date(value: Any) -> str:
    if not value:
        return ""
    try:
        return dt.date.fromisoformat(str(value)).strftime("%b %Y")
    except ValueError:
        return str(value)


def _date_range(item: dict[str, Any]) -> str:
    start = _date(item.get("start_date"))
    end = "Present" if item.get("is_current") else _date(item.get("end_date"))
    return " - ".join(part for part in (start, end) if part)


def _heading(pdf: FPDF, text: str) -> None:
    if pdf.will_page_break(25):
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.l_margin, pdf.y, pdf.w - pdf.r_margin, pdf.y)
    pdf.ln(2)
    pdf.set_font("DejaVu", "", _BODY_SIZE)


def _entry_header(pdf: FPDF, title: str, dates: str) -> None:
    pdf.set_font("DejaVu", "B", _BODY_SIZE)
    date_width = min(48.0, max(33.0, pdf.get_string_width(dates) + 3)) if dates else 0.0
    title_width = pdf.epw - date_width
    height = cast(
        float,
        pdf.multi_cell(title_width, _LINE, title, dry_run=True, output=MethodReturnValue.HEIGHT),
    )
    if pdf.will_page_break(height + _LINE * 3):
        pdf.add_page()
    x, y = pdf.x, pdf.y
    pdf.multi_cell(title_width, _LINE, title, align="L", new_x="LMARGIN", new_y="NEXT")
    bottom = pdf.y
    if dates:
        pdf.set_xy(x + title_width, y)
        pdf.set_font("DejaVu", "", 8)
        pdf.multi_cell(date_width, _LINE, dates, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin, max(pdf.y, bottom))
    pdf.set_font("DejaVu", "", _BODY_SIZE)


def _bullet(pdf: FPDF, text: str) -> None:
    # Reserve a full first line before drawing its marker, including at page breaks.
    if pdf.will_page_break(_LINE):
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.cell(3, _LINE, "•")
    pdf.multi_cell(pdf.epw - 3, _LINE, text, align="L", new_x="LMARGIN", new_y="NEXT")


def _text(pdf: FPDF, text: str, *, height: float = _LINE) -> None:
    pdf.multi_cell(0, height, text, align="L", new_x="LMARGIN", new_y="NEXT")
