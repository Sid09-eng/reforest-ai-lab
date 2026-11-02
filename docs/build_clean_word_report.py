"""Create the final report in a clean Word-native DOCX container.

The legacy .doc template is used as a visual guide only.  This avoids carrying
old Word metadata into the submitted report, while retaining an editable
NTU-style cover page and the same reviewed body, figures and references.
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

import generate_final_report as report


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Forest_Restoration_Using_AI_Final_Report_Draft.docx"


def center(doc, text="", size=12, bold=False, before=0, after=0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.bold = bold
    return p


def add_editable_cover(doc):
    center(doc, "", before=22)
    center(doc, "Forest Restoration Using AI", size=18, bold=True, after=34)
    center(doc, "Submitted by: [Student name]", size=12, after=16)
    center(doc, "Supervisor: [Supervisor name]", size=12, after=12)
    center(doc, "Co-supervisor: [Co-supervisor name]", size=12, after=38)
    center(doc, "School of Electrical & Electronic Engineering", size=12, bold=True, after=25)
    center(doc, "A final year project report presented to Nanyang Technological University", size=12, after=8)
    center(doc, "in partial fulfilment of the requirements for the", size=12, after=8)
    center(doc, "Degree of Bachelor of Engineering", size=12, after=30)
    center(doc, "2026", size=12)


def main():
    doc = Document()
    report.set_doc_defaults(doc)
    add_editable_cover(doc)
    report.table_count = 0
    report.add_cover_and_frontmatter(doc)
    report.chapter_one(doc)
    report.chapter_two(doc)
    report.chapter_three(doc)
    report.chapter_four(doc)
    report.chapter_five(doc)
    report.chapter_six(doc)
    report.chapter_seven(doc)
    report.references(doc)
    report.appendices(doc)
    doc.save(OUT)
    # A second open/save confirms the generated package is readable through
    # python-docx before it is handed to Word.
    Document(OUT).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
