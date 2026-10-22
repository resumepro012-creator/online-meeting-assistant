"""Builds REPORT.docx from REPORT.md (single source of truth), embedding the charts.

Uses python-docx. Charts are embedded as PNG because python-docx cannot embed SVG
and no SVG->PNG renderer is available in this environment, so they are produced by
``scripts/make_report_charts.py`` (pure-Python PNG).

Run (after ``make_report_charts.py``):
    .venv\\Scripts\\python.exe scripts\\make_report_docx.py
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
SOURCE = ROOT / "REPORT.md"
TARGET = ROOT / "REPORT.docx"

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")
IMAGE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")
CODE_FENCE = re.compile(r"^```")
HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
NUMBERED = re.compile(r"^\d+\.\s+")
SEPARATOR_CELLS = re.compile(r"^[\s|:\-]+$")


def add_inline(paragraph, text: str) -> None:
    """Render **bold**, `code` and [label](url) inline markup into a paragraph."""
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
        elif part.startswith("[") and "](" in part:
            label = part[1 : part.index("](")]
            paragraph.add_run(label)
        else:
            paragraph.add_run(part)


def add_horizontal_rule(document: Document) -> None:
    paragraph = document.add_paragraph()
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.makeelement(qn("w:pBdr"), {})
    bottom = borders.makeelement(qn("w:bottom"), {
        qn("w:val"): "single",
        qn("w:sz"): "6",
        qn("w:space"): "1",
        qn("w:color"): "D1D5DB",
    })
    borders.append(bottom)
    p_pr.append(borders)


def add_table(document: Document, rows: list[list[str]]) -> None:
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.autofit = True
    for r, row in enumerate(rows):
        for c, cell_text in enumerate(row):
            cell = table.cell(r, c)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            add_inline(paragraph, cell_text)
            for run in paragraph.runs:
                run.font.size = Pt(9)
                if r == 0:
                    run.bold = True
    document.add_paragraph()


def build() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"FAIL: {SOURCE} not found")

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    document = Document()
    document.core_properties.title = "AI Online Class & Meeting Assistant - Technical Report"

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    image_count = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        # --- code fence ------------------------------------------------ #
        if CODE_FENCE.match(stripped):
            index += 1
            block: list[str] = []
            while index < len(lines) and not CODE_FENCE.match(lines[index].strip()):
                block.append(lines[index])
                index += 1
            index += 1
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(2)
            for i, code_line in enumerate(block):
                if i:
                    paragraph.add_run().add_break()
                run = paragraph.add_run(code_line)
                run.font.name = "Consolas"
                run.font.size = Pt(8.5)
            continue

        # --- image ------------------------------------------------------ #
        image_match = IMAGE.match(stripped)
        if image_match:
            image_path = (SOURCE.parent / image_match.group("path")).resolve()
            if image_path.exists():
                document.add_picture(str(image_path), width=Inches(6.2))
                document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                image_count += 1
            else:
                document.add_paragraph(f"[missing image: {image_match.group('path')}]")
            index += 1
            continue

        # --- table ------------------------------------------------------ #
        if stripped.startswith("|") and index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not SEPARATOR_CELLS.match(lines[index].strip()):
                    rows.append(cells)
                index += 1
            if rows:
                add_table(document, rows)
            continue

        # --- heading ---------------------------------------------------- #
        heading_match = HEADING.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            if level == 1:
                heading = document.add_heading(level=1)
                add_inline(heading, text)
                for run in heading.runs:
                    run.font.size = Pt(22)
                    run.font.color.rgb = RGBColor(0x31, 0x2E, 0x81)
            else:
                heading = document.add_heading(level=level)
                add_inline(heading, text)
                if level == 2:
                    for run in heading.runs:
                        run.font.size = Pt(15)
                        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
                elif level == 3:
                    for run in heading.runs:
                        run.font.size = Pt(12.5)
                        run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
            index += 1
            continue

        # --- horizontal rule -------------------------------------------- #
        if stripped in {"---", "***", "___"}:
            add_horizontal_rule(document)
            index += 1
            continue

        # --- blockquote -------------------------------------------------- #
        if stripped.startswith(">"):
            block = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                block.append(lines[index].strip().lstrip(">").strip())
                index += 1
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Inches(0.3)
            for i, chunk in enumerate(block):
                if i:
                    paragraph.add_run().add_break()
                add_inline(paragraph, chunk)
            for run in paragraph.runs:
                run.italic = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)
            continue

        # --- bullets / numbered lists ------------------------------------ #
        if stripped.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            add_inline(paragraph, stripped[2:])
            index += 1
            continue
        if NUMBERED.match(stripped):
            paragraph = document.add_paragraph(style="List Number")
            add_inline(paragraph, NUMBERED.sub("", stripped))
            index += 1
            continue

        # --- blank ------------------------------------------------------- #
        if not stripped:
            index += 1
            continue

        # --- plain paragraph --------------------------------------------- #
        paragraph = document.add_paragraph()
        add_inline(paragraph, stripped)
        index += 1

    document.save(str(TARGET))
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes, {image_count} charts embedded)")


if __name__ == "__main__":
    build()
