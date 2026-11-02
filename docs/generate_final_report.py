"""Build the final FYP report from the official NTU EEE Word template.

The script retains the template cover page verbatim, removes the sample body,
and appends the project-specific report.  It is intentionally kept with the
report so figure placement, tables, and claims can be regenerated from the
validated project outputs.
"""
from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "FYP_Report_Template.doc"
WORK_TEMPLATE = Path("/private/tmp/fyp-report-template/FYP_Report_Template.docx")
OUT = ROOT / "docs" / "Forest_Restoration_Using_AI_Final_Report_Draft.docx"
FIG = ROOT / "outputs" / "redesigned"

NAVY = RGBColor(31, 63, 97)
GREY = RGBColor(80, 80, 80)
TABLE_CAPTIONS = [
    "Acronyms and symbols used in the report.",
    "Project alignment and scope boundary.",
    "Research questions, evidence and permitted claims.",
    "Monitored plots and sensor-record inventory.",
    "Dataset variables and analytical roles.",
    "Dataset tiers and purpose.",
    "Cleaning and review rules.",
    "Cleaning and daily-coverage audit.",
    "EDA summary used to set the analytical route.",
    "Engineered features and their availability.",
    "Evaluation designs and intended claims.",
    "Primary daily associations.",
    "Drydown-event summaries by plot.",
    "Chronological final-period forecast scores.",
    "Leave-one-site-out best models.",
    "Limitations and their implications.",
    "Data audit and reproducibility checklist.",
]
table_count = 0


def set_cell_shading(cell, fill="EAF0F6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def ensure_workflow(path: Path):
    """Create a clean, academic-style workflow diagram with clear boxes and arrows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (2200, 750), "white")
    draw = ImageDraw.Draw(img)
    try:
        bold_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 32)
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
        bold_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 24)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
    except OSError:
        bold_title = ImageFont.load_default(); font = bold_title; bold_font = bold_title; small = font

    # Step boxes - clean rectangular style with academic dark-navy headers
    steps = [
        ("Step 1", "Raw Ingestion", "1,002,949 records", "from RData source"),
        ("Step 2", "Data Cleaning", "1,002,899 rows kept", "50 invalid removed"),
        ("Step 3", "Daily EDA", "Coverage & trends", "Within-plot analysis"),
        ("Step 4", "Modelling", "Drydown, PCA,", "Prediction baselines"),
        ("Step 5", "Interpretation", "Environmental baseline", "& stated limits"),
    ]

    box_w, box_h = 330, 260
    gap = 70
    start_x = 90
    y_top = 60

    for i, (step, title_text, line1, line2) in enumerate(steps):
        x = start_x + i * (box_w + gap)

        # Box body with clean outline
        draw.rectangle((x, y_top, x + box_w, y_top + box_h), fill="#FAFAFB", outline="#4A6572", width=2)

        # Step number header bar
        draw.rectangle((x, y_top, x + box_w, y_top + 48), fill="#1F4E79", outline="#1F4E79")
        step_w = bold_font.getlength(step)
        draw.text((x + (box_w - step_w) / 2, y_top + 11), step, font=bold_font, fill="white")

        # Title
        title_w = bold_font.getlength(title_text)
        draw.text((x + (box_w - title_w) / 2, y_top + 72), title_text, font=bold_font, fill="#1A2530")

        # Description lines
        l1_w = font.getlength(line1)
        draw.text((x + (box_w - l1_w) / 2, y_top + 126), line1, font=font, fill="#4A5568")
        l2_w = font.getlength(line2)
        draw.text((x + (box_w - l2_w) / 2, y_top + 164), line2, font=font, fill="#4A5568")

        # Arrow to next box
        if i < len(steps) - 1:
            ax = x + box_w + 4
            ay = y_top + box_h // 2
            draw.line((ax, ay, ax + gap - 12, ay), fill="#1F4E79", width=4)
            # Arrowhead
            draw.polygon([
                (ax + gap - 12, ay - 9),
                (ax + gap - 2, ay),
                (ax + gap - 12, ay + 9),
            ], fill="#1F4E79")

    # Sensitivity branch centered directly below Step 3
    step3_center_x = start_x + 2 * (box_w + gap) + box_w // 2
    branch_w = 840
    bx1 = step3_center_x - branch_w // 2
    branch_y = y_top + box_h + 80
    branch_h = 100

    draw.rectangle((bx1, branch_y, bx1 + branch_w, branch_y + branch_h),
                    fill="#F0F4F8", outline="#7E9CB5", width=2)

    branch_text = "Sensitivity Branch: review-screened tier (920,216 records)"
    bt_w = bold_font.getlength(branch_text)
    draw.text((bx1 + (branch_w - bt_w) / 2, branch_y + 18), branch_text, font=bold_font, fill="#1F4E79")
    branch_text2 = "Tests whether daily findings change when review-flagged values are excluded."
    bt2_w = font.getlength(branch_text2)
    draw.text((bx1 + (branch_w - bt2_w) / 2, branch_y + 54), branch_text2, font=font, fill="#4A5568")

    # Clean vertical dashed line from sensitivity branch up to Step 3
    mid_x = step3_center_x
    dash_len = 8
    dash_gap = 6
    curr_y = branch_y
    target_y = y_top + box_h + 12
    while curr_y > target_y:
        draw.line((mid_x, curr_y, mid_x, max(target_y, curr_y - dash_len)), fill="#7E9CB5", width=3)
        curr_y -= (dash_len + dash_gap)

    # Arrowhead pointing into bottom of Step 3
    draw.polygon([
        (mid_x - 9, y_top + box_h + 14),
        (mid_x, y_top + box_h + 2),
        (mid_x + 9, y_top + box_h + 14),
    ], fill="#7E9CB5")

    # Bottom explanatory label
    note = "Primary (hard-cleaned) tier carries all main evidence. The review-screened tier checks sensitivity only."
    note_w = small.getlength(note)
    draw.text(((2200 - note_w) / 2, branch_y + branch_h + 30), note, font=small, fill="#718096")

    img.save(path)


def ensure_eda_notebook_summary(path: Path):
    """Use the real Playwright-captured notebook cell screenshot instead of a synthetic image."""
    real_screenshot = ROOT / "docs" / "assets" / "notebook_cleaning_summary_cell.png"
    if real_screenshot.exists():
        import shutil as _shutil
        _shutil.copy2(real_screenshot, path)
        return
    # Fallback: render a simple placeholder if the screenshot hasn't been taken yet
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 400), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((40, 40), "Notebook screenshot placeholder: run capture_notebook_cell.py", font=font, fill="#333")
    img.save(path)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_field(run, instruction: str):
    """Insert a complete Word field, including a cached display result.

    Word recalculates PAGE when the document is opened; the cached result lets
    non-Word consumers recognise the field instead of showing a bare label.
    """
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    cached_result = OxmlElement("w:t")
    cached_result.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, cached_result, end])


def add_page_number(footer):
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Page ")
    add_field(p.add_run(), " PAGE ")


def keep_cover_only(doc):
    """Keep the official cover-page paragraphs and remove all sample content.

    The legacy template places the page break on the following "Table of
    Contents" paragraph, so retaining through the first break accidentally
    preserves the sample TOC.  The final year on the cover is the reliable
    marker for the end of its content.
    """
    body = doc._element.body
    children = list(body)
    cutoff = None
    for i, child in enumerate(children):
        text = " ".join(child.itertext())
        if "20xx" in text and i < 30:
            cutoff = i
            break
    if cutoff is None:
        raise RuntimeError("Could not identify the final cover-page paragraph in the official template")
    for child in children[cutoff + 1:]:
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def set_doc_defaults(doc):
    sec = doc.sections[0]
    sec.top_margin = Cm(3.0)
    sec.bottom_margin = Cm(3.0)
    sec.left_margin = Cm(3.5)
    sec.right_margin = Cm(3.0)
    sec.different_first_page_header_footer = True
    sec.first_page_header.paragraphs[0].text = ""
    sec.first_page_footer.paragraphs[0].text = ""
    add_page_number(sec.footer)
    hdr = sec.header.paragraphs[0]
    hdr.text = "Forest Restoration Using AI"
    hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hdr.runs[0].font.name = "Times New Roman"
    hdr.runs[0].font.size = Pt(9)
    hdr.runs[0].font.color.rgb = GREY

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for name, size in [("Title", 18), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)]:
        try:
            st = doc.styles[name]
        except KeyError:
            st = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.font.name = "Times New Roman"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = NAVY
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(4)
        st.paragraph_format.keep_with_next = True
    if "Caption" in doc.styles:
        cap = doc.styles["Caption"]
    else:
        cap = doc.styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
    cap.font.name = "Times New Roman"
    cap.font.size = Pt(10)
    cap.font.italic = True
    cap.font.color.rgb = RGBColor(50, 50, 50)
    cap.paragraph_format.space_before = Pt(4)
    cap.paragraph_format.space_after = Pt(4)
    cap.paragraph_format.line_spacing = 1.0
    for name in ("List Bullet", "Table Grid"):
        try:
            doc.styles[name]
        except KeyError:
            # A legacy .doc conversion may not carry Word's built-in styles.
            doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def page_break(doc):
    # A break embedded in an empty run can place the following heading at the
    # very top edge in headless renderers.  A page-break-before paragraph keeps
    # the following section title intact in Word and in artifact renders.
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    return p


def title(doc, text, level=1):
    if level == 1:
        return doc.add_heading(text, level=1)
    return doc.add_heading(text, level=level)


def frontmatter_title(doc, text):
    """Formal, centred title used for the navigational pages."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(26)
    p.paragraph_format.space_after = Pt(22)
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(18)
    r.font.color.rgb = RGBColor(0, 0, 0)
    return p


def leader_entry(doc, label, page, indent_cm=0.0, bold=False):
    """A static TOC/list entry using Word tab stops with dot leaders for proper alignment."""
    p = doc.add_paragraph()
    if indent_cm > 0:
        p.paragraph_format.left_indent = Cm(indent_cm)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(2)

    # Set a right-aligned tab stop at exactly 14.5 cm (page width 21cm - left 3.5cm - right 3.0cm) with dot leader
    tab_stops = p.paragraph_format.tab_stops
    tab_stops.add_tab_stop(Cm(14.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

    r = p.add_run(label)
    r.bold = bold
    r.font.size = Pt(10.5)
    r.font.name = "Times New Roman"

    t = p.add_run("\t" + str(page))
    t.bold = bold
    t.font.size = Pt(10.5)
    t.font.name = "Times New Roman"
    return p


def para(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item)


def table(doc, headers, rows, widths=None, font_size=9.5):
    """Add a publication-style table plate with stable Word/PDF rendering."""
    global table_count
    table_count += 1
    caption = TABLE_CAPTIONS[table_count - 1] if table_count <= len(TABLE_CAPTIONS) else "Summary matrix."
    cp = doc.add_paragraph(f"Table {table_count}. {caption}", style="Caption")
    cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cp.paragraph_format.keep_with_next = True
    asset_dir = ROOT / "docs" / "assets" / "report_tables"
    asset_dir.mkdir(parents=True, exist_ok=True)
    table_path = asset_dir / f"table_{table_count:02d}.png"
    create_table_plate(table_path, headers, rows, widths or [1] * len(headers))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    p.add_run().add_picture(str(table_path), width=Inches(5.7))


def create_table_plate(path, headers, rows, weights):
    """Render a compact, accessible table image using measured wrapped text."""
    page_width = 1800
    pad = 24
    border = 2
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)
        bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    except OSError:
        font = ImageFont.load_default(); bold = font
    total = sum(weights)
    col_widths = [int(page_width * w / total) for w in weights]
    col_widths[-1] += page_width - sum(col_widths)

    def wrapped(value, width, face):
        words = str(value).split()
        lines, current = [], ""
        for word in words:
            candidate = (current + " " + word).strip()
            if current and face.getlength(candidate) > width - 2 * pad:
                lines.append(current); current = word
            else:
                current = candidate
        return lines + ([current] if current else [""])

    prepared = []
    for row_index, row in enumerate([headers] + list(rows)):
        face = bold if row_index == 0 else font
        lines = [wrapped(value, width, face) for value, width in zip(row, col_widths)]
        line_height = 36
        height = max(len(x) for x in lines) * line_height + 2 * pad
        prepared.append((lines, height, face))
    img_height = sum(height for _, height, _ in prepared) + border * 2
    img = Image.new("RGB", (page_width + border * 2, img_height), "white")
    draw = ImageDraw.Draw(img)
    y = border
    for row_index, (cells, height, face) in enumerate(prepared):
        fill = "#1F4E79" if row_index == 0 else ("#F4F7FA" if row_index % 2 == 0 else "#FFFFFF")
        x = border
        for col_index, (cell_lines, width) in enumerate(zip(cells, col_widths)):
            draw.rectangle((x, y, x + width, y + height), fill=fill, outline="#AAB7C4", width=border)
            text_colour = "white" if row_index == 0 else "#1E2933"
            line_y = y + pad
            for line in cell_lines:
                draw.text((x + pad, line_y), line, font=face, fill=text_colour)
                line_y += 36
            x += width
        y += height
    img.save(path)


def figure(doc, relative, caption, width=5.7, source_note="Source: Author's analysis from the CCNR microclimate dataset."):
    path = FIG / relative
    if not path.exists():
        raise FileNotFoundError(path)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width))
    cp = doc.add_paragraph(style="Caption")
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.keep_with_next = True
    cp.paragraph_format.space_after = Pt(1)
    cp.add_run(caption)
    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sp.paragraph_format.space_after = Pt(6)
    sr = sp.add_run(source_note)
    sr.italic = True
    sr.font.size = Pt(8.5)
    return p


def asset_figure(doc, path, caption, width=5.7, source_note="Source: Executed project notebook."):
    """Insert a report asset that is not one of the analysis-output plots."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width))
    cp = doc.add_paragraph(style="Caption")
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.keep_with_next = True
    cp.paragraph_format.space_after = Pt(1)
    cp.add_run(caption)
    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sp.paragraph_format.space_after = Pt(6)
    sr = sp.add_run(source_note)
    sr.italic = True
    sr.font.size = Pt(8.5)
    return p


def equation(doc, lines):
    for line in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        r.font.name = "Cambria Math"
        r.font.size = Pt(12)


def add_cover_and_frontmatter(doc):
    page_break(doc)
    frontmatter_title(doc, "Table of Contents")
    # Static contents are deliberately used here. The official template began
    # as a legacy .doc, and a dynamic TOC field inserted after conversion can
    # trigger a repair warning in desktop Word even though other renderers
    # accept the file. These page references match the final reviewed layout.
    toc_entries = [
        ("Abstract", "3"),
        ("Acknowledgements", "4"),
        ("Acronyms and symbols", "5"),
        ("List of Figures", "6"),
        ("List of Tables", "7"),
        ("Chapter 1  Introduction", "8"),
        ("Chapter 2  Study context and project flow", "11"),
        ("Chapter 3  Data, provenance and quality workflow", "16"),
        ("Chapter 4  Methods", "22"),
        ("Chapter 5  Results", "28"),
        ("Chapter 6  Discussion and project readiness", "46"),
        ("Chapter 7  Conclusion and future work", "50"),
        ("References", "52"),
        ("Appendix A  Data audit and reproducibility checklist", "54"),
        ("Appendix B  Cleaning and analysis notes", "54"),
        ("Appendix C  Supplementary variable views", "55"),
        ("Appendix D  Supplementary drydown and prediction figures", "57"),
    ]
    for item, page in toc_entries:
        leader_entry(doc, item, page, bold=item.startswith(("Chapter", "References", "Appendix")))

    page_break(doc)
    frontmatter_title(doc, "Abstract")
    para(doc, "This project set out to answer a practical question: can a large, noisy microclimate sensor file be turned into something that future forest-restoration research can actually use? The dataset comes from seven monitored forest plots in Singapore's Central Catchment Nature Reserve, covering temperature, relative humidity (RH), vapour-pressure deficit (VPD), photosynthetically active radiation (PAR) and soil moisture. The raw file contained 1,002,949 observations. After removing 50 records that were clearly unusable, 1,002,899 remained as the primary analysis tier. A further 82,683 readings were flagged under review rules but kept in the primary dataset because, without calibration logs, it was impossible to say whether they were sensor faults or genuine extreme weather conditions. A stricter screened tier of 920,216 rows was used only for sensitivity checks.")
    para(doc, "The analysis followed a straightforward path: clean the data, build daily plot-level summaries, look for patterns, and test whether simple models could predict the next day's conditions. The strongest daily relationship was between RH and VPD (median within-plot Spearman rho = −0.991), which was expected since VPD is derived from temperature and RH. For four of five prediction targets, the best approach on the final test period was simply carrying forward the previous day's value. This is an honest rather than disappointing outcome, because it sets a clear bar that any future model would need to beat. The report does not claim to predict tree health. What it delivers is a documented, reproducible environmental baseline and a set of realistic predictive benchmarks that can be built upon once tree-health labels, rainfall data and remote-sensing products become available.")

    page_break(doc)
    frontmatter_title(doc, "Acknowledgements")
    para(doc, "I would like to express my sincere gratitude to my supervisor and co-supervisor for their guidance, feedback and encouragement throughout this final-year project. Their comments helped me narrow the study from a broad AI-for-restoration idea into a clear and defensible analysis of the data that were available.")
    para(doc, "I am grateful to the data custodians and field teams whose sensor records made this work possible. I also thank the School, my classmates, friends and family for their support during the project. Any remaining errors or limitations in the analysis are my own.")

    page_break(doc)
    frontmatter_title(doc, "Acronyms and Symbols")
    table(doc, ["Term", "Meaning"], [
        ["CCNR", "Central Catchment Nature Reserve"],
        ["EDA", "Exploratory data analysis"],
        ["FYP", "Final year project"],
        ["LOSO", "Leave-one-site-out"],
        ["MAE", "Mean absolute error"],
        ["PAR", "Photosynthetically active radiation"],
        ["RH", "Relative humidity"],
        ["RMSE", "Root mean squared error"],
        ["VPD", "Vapour-pressure deficit"],
        ["R²", "Coefficient of determination"],
        ["ρ", "Spearman rank correlation coefficient"],
    ], widths=[4, 12])

    page_break(doc)
    frontmatter_title(doc, "List of Figures")
    figure_list = [
        ("Figure 1. Study workflow from source audit through EDA to interpretation.", "13"),
        ("Figure 2. Sensitivity of daily means to the review-screening policy.", "19"),
        ("Figure 3. Executed notebook cell screenshot: cleaning audit counts.", "20"),
        ("Figure 4. Executed notebook excerpt: daily feature construction.", "23"),
        ("Figure 5. Executed notebook excerpt: PCA pattern discovery.", "26"),
        ("Figure 6. Executed notebook excerpt: chronological evaluation.", "27"),
        ("Figure 7. Daily mean temperature by plot on shared axes.", "28"),
        ("Figure 8. Daily mean relative humidity by plot on shared axes.", "29"),
        ("Figure 9. Daily mean PAR by plot on shared axes.", "29"),
        ("Figure 10. Daily mean soil moisture by plot on shared axes.", "30"),
        ("Figure 11. Daily mean VPD by plot on shared axes.", "30"),
        ("Figure 12. Within-plot daily Spearman relationships with bootstrap intervals.", "31"),
        ("Figure 13. Selected daily relationships, plotted by plot.", "32"),
        ("Figure 14. Daily microclimate regimes in PCA space.", "33"),
        ("Figure 15. Identified soil-moisture drydown events over time.", "34"),
        ("Figure 16. Normalised drydown curves by plot.", "35"),
        ("Figure 17. Soil-moisture drying-rate summary by plot.", "37"),
        ("Figure 18. Empirical soil-moisture half-life summary by plot.", "38"),
        ("Figure 19. VPD-state classification test confusion matrix.", "39"),
        ("Figure 20. Daily forecast comparison against persistence baselines.", "41"),
        ("Figure 21. Held-out feature importance for selected models.", "42"),
        ("Figure 22. Daily soil-moisture forecast during drydown.", "43"),
        ("Figure 23. Summary of robustness across data tiers.", "45"),
        ("Figure C1. Supplementary daily soil-moisture view by plot.", "55"),
        ("Figure C2. Supplementary daily VPD view by plot.", "56"),
        ("Figure D1. Supplementary hourly forecast demonstration.", "57"),
        ("Figure D2. Daily soil-moisture range summary by plot.", "58"),
        ("Figure D3. Exploratory plot-summary model comparison.", "58"),
        ("Figure D4. Exploratory plot-summary trait-link view (n = 7).", "59"),
        ("Figure D5. Leave-one-group-out permutation importance.", "59"),
        ("Figure D6. VPD daily-range comparison by plot.", "60"),
    ]
    for item, page in figure_list:
        leader_entry(doc, item, page)

    page_break(doc)
    frontmatter_title(doc, "List of Tables")
    table_pages = ["5", "9", "10", "12", "16", "16", "17", "18", "20", "25", "26", "31", "36", "40", "44", "48", "54"]
    for number, (caption, page) in enumerate(zip(TABLE_CAPTIONS, table_pages), 1):
        leader_entry(doc, f"Table {number}. {caption}", page)


def chapter_one(doc):
    page_break(doc)
    title(doc, "Chapter 1  Introduction", 1)
    title(doc, "1.1 Background and motivation", 2)
    para(doc, "When a forest is being restored, conditions near the ground (such as temperature, humidity, light, and soil moisture) can tell us a lot about how the site is recovering. These local conditions, often called the microclimate, differ from what a weather station several kilometres away might report. A dense canopy keeps the understorey cooler and more humid, while an open or degraded area may experience wider temperature swings and drier soils. Understanding these differences matters for deciding where to plant, when to intervene, and whether a restored patch is beginning to function like a mature forest.")
    para(doc, "The starting material for this project is a large time-stamped microclimate record from seven forest plots in Singapore. It does not come with tree-health labels, LiDAR scans, satellite imagery, rainfall gauges or sensor-maintenance logs. That means the project cannot predict whether trees are healthy because it simply does not have the data for that. Instead, this report focuses on what the data can support: a careful, reproducible workflow that cleans the sensor record, describes daily conditions across plots, and tests whether simple models can add anything beyond just carrying forward yesterday's reading. The result is groundwork for a future restoration study, not a biological health assessment.")
    title(doc, "1.2 Alignment with the FYP theme", 2)
    para(doc, "The broad FYP title mentions AI and forest restoration, which initially suggested building a model that predicts tree health using machine learning. However, once I started working with the actual dataset, it became clear that the available data could not support that kind of claim because there were no health outcomes to train against, no canopy measurements, and no maintenance logs. Rather than forcing the project into a shape the data could not fill, I reframed it around what the data could genuinely support. Table 2 maps this alignment.")
    table(doc, ["Broad FYP theme", "Work completed in this report", "Boundary"], [
        ["AI for data processing", "Quality flags, feature engineering, clustering/labels and predictive benchmarks.", "Models are evaluated as readiness tests, not deployed decision systems."],
        ["Data collection and environmental monitoring", "Audit of a supplied multi-sensor record across forest plots.", "The field data collection was not carried out by the author."],
        ["Forest restoration", "Environmental baseline that can support later restoration monitoring.", "No growth, survival, species or health outcomes are observed."],
        ["Remote sensing and image processing", "Not analysed because no matched imagery, LiDAR or derived products were supplied.", "Included only as a future integration pathway."],
    ], widths=[4.5, 6.5, 6.5])
    title(doc, "1.3 Research questions", 2)
    para(doc, "With this scope in mind, the project addresses five specific questions:")
    bullets(doc, [
        "How complete and reliable is the supplied microclimate record after an auditable cleaning process?",
        "How do temperature, RH, VPD, PAR and soil moisture vary across plots and time?",
        "Which daily relationships are stable within plots, and which findings depend on the screening policy?",
        "Can measurements available by the end of one day predict the following day’s microclimate at a later time or at an unseen plot?",
        "What data, monitoring and validation gaps must be closed before a tree-health model would be justified?",
    ])
    title(doc, "1.4 Objectives", 2)
    bullets(doc, [
        "Build a reproducible raw-to-analysis pipeline without modifying the original RData source.",
        "Separate genuinely invalid rows from readings that need review, and show how sensitive results are to that distinction.",
        "Describe daily patterns, relationships and soil-moisture drydown behaviour at the plot level.",
        "Construct transparent labels and leakage-aware predictive baselines, keeping persistence as a serious competitor.",
        "Document limitations honestly and outline a realistic path toward future restoration-health modelling.",
    ])
    title(doc, "1.5 What this report is designed to show", 2)
    para(doc, "The report follows the same order as the analysis: first check whether the data can be trusted at the daily scale, then describe the patterns, then test whether models can improve on carrying forward yesterday's value. Table 3 maps each question to the evidence used and the kind of conclusion that is allowed. This matters because an interesting environmental pattern is not automatically evidence of tree health.")
    table(doc, ["Question", "Evidence used", "What the report can conclude"], [
        ["Is the record suitable for daily analysis?", "Data tiers, screening sensitivity and audit counts.", "Which signals are robust at daily scale and which require cautious interpretation."],
        ["How do monitored conditions change?", "Daily plot series, within-plot associations, PCA regimes and drydown summaries.", "Observed temporal and plot-level patterns, not their ecological cause."],
        ["Can a model add to a simple baseline?", "Chronological 60/20/20 evaluation, later-time regression and LOSO transfer checks.", "Whether a selected method beats persistence for the stated task and split."],
        ["How does this support restoration work?", "Reproducible features, plots, limitations and integration requirements.", "What can be joined to future tree, rainfall and remote-sensing observations."],
    ], widths=[4.3, 6.2, 7.5])
    title(doc, "1.6 Report structure", 2)
    para(doc, "Chapter 2 provides the study context, including background on microclimate monitoring and the project workflow. Chapter 3 covers where the data came from, how it was cleaned, and what the two analysis tiers look like. Chapter 4 explains the methods, covering daily aggregation, feature engineering, association analysis, drydown summaries, and the two evaluation designs. Chapter 5 presents results in the order of the research questions. Chapter 6 discusses what is ready for reuse and what is still uncertain, and Chapter 7 wraps up with conclusions and future work. The appendices hold supplementary figures and the data audit checklist.")


def chapter_two(doc):
    page_break(doc)
    title(doc, "Chapter 2  Study context and project flow", 1)
    title(doc, "2.1 What the sensor record can support", 2)
    para(doc, "A forest canopy changes conditions near the ground by blocking sunlight, slowing wind, and altering how heat and moisture move through the air. De Frenne et al. [1] showed that forests can buffer local temperature by several degrees, but the strength of that buffering depends on canopy density, topography, season and even where exactly the sensor sits. This means a microclimate series is best understood as environmental context: a warm or dry spell might warrant closer inspection in the field, but the numbers alone cannot tell us whether a tree was stressed or damaged.")
    para(doc, "The dataset used in this project contains five measured variables. Temperature captures thermal conditions, RH tells us how saturated the air is with moisture, PAR measures the photosynthetically active portion of light, and soil moisture indicates how wet the soil is at the sensor depth. VPD (vapour-pressure deficit) combines temperature and RH into a single number that describes how 'thirsty' the air is. Because VPD is calculated from temperature and RH, any correlation involving VPD is at least partly mathematical rather than representing an independent physical relationship. This project treats VPD associations as descriptive patterns, not as evidence of independent causal effects.")
    title(doc, "2.2 Monitored plots and sensor record", 2)
    para(doc, "The data comes from a CCNR sensor deployment that I did not carry out myself, as it was provided as an existing field dataset. Seven plot codes appear in the file, spread across four forest types at different successional stages. The raw source contains 66 distinct serial numbers from two sensor families (HOBO loggers and iButtons). When counting serial numbers per plot, there are 68 plot-to-device assignments because two serial numbers show up at more than one plot, probably due to redeployments. Table 4 summarises what the data record tells us about each plot. It is worth noting that this describes the digital record, not the physical layout, because sensor heights, exact positions and installation dates were not available.")
    table(doc, ["Plot", "Forest type / stage", "HOBO serials", "iButton serials", "Plot-device assignments", "Recorded channels"], [
        ["CN2", "FT2 / Secondary", "9", "2", "11", "temp, RH, VPD, PAR, soil moisture"],
        ["FT4MD", "FT4 / Primary", "5", "4", "9", "temp, RH, VPD, PAR, soil moisture"],
        ["FT4MR", "FT4 / Primary", "6", "3", "9", "temp, RH, VPD, PAR, soil moisture"],
        ["FT4TH", "FT4 / Primary", "9", "2", "11", "temp, RH, VPD, PAR, soil moisture"],
        ["LP3", "FT3 / Secondary", "8", "2", "10", "temp, RH, VPD, PAR, soil moisture"],
        ["UP2", "FT1 / Early successional", "8", "2", "10", "temp, RH, VPD, PAR, soil moisture"],
        ["US5", "FT1 / Early successional", "6", "2", "8", "temp, RH, VPD, PAR, soil moisture"],
    ], widths=[2.0, 4.0, 2.2, 2.4, 2.8, 5.6])
    para(doc, "Temperature, RH and VPD are recorded by both HOBO and iButton sensors, while PAR and soil moisture come only from the HOBO loggers. This is why the daily coverage for temperature, RH and VPD is much higher than for PAR and soil moisture, which is an important consideration when interpreting results later on. It is also worth mentioning that a serial number in the file is just an identifier; it does not prove that all listed channels were working at the same time or at the same position.")
    title(doc, "2.3 Data-science flow used in this project", 2)
    para(doc, "Figure 1 shows the overall workflow. The key idea is that every step builds on the previous one. I started by loading the raw RData file and checking what was in it. Then I separated out records that were clearly broken from those that just looked suspicious. Only after that did I create daily summaries and start looking for patterns. The EDA checked coverage, trends and relationships before moving to more detailed analyses, including drydown analysis, PCA clustering and forecasting. This ordering matters: a model result only means something once you know which data went in, what time unit was used, and how the evaluation was set up.")
    workflow = ROOT / "docs" / "assets" / "project_data_science_flow.png"
    ensure_workflow(workflow)
    asset_figure(doc, workflow, "Figure 1. Study workflow from source audit through EDA to interpretation.", width=6.25, source_note="Source: Author’s workflow based on the executed project analysis.")
    para(doc, "The two data tiers (hard-cleaned and review-screened) run side by side throughout the analysis. The hard-cleaned tier is the primary evidence because it removes only rows that cannot be used at all (missing timestamps, impossible values). The screened tier goes further by also excluding readings that meet certain review rules, like RH = 100% or VPD = 0. Running both tiers lets me ask: 'Does this finding change when I exclude the questionable readings?' For temperature and soil moisture, the answer was usually no. For RH and VPD, the answer was sometimes yes. Knowing that distinction is more valuable than just presenting one version of the data without showing what was left out.")
    title(doc, "2.4 Vapour-pressure deficit", 2)
    para(doc, "VPD deserves its own short explanation because it appears throughout the results and is easily misunderstood. It is the difference between how much water vapour the air could hold (saturation vapour pressure) and how much it actually holds. The FAO-56 formulation [2] gives the standard calculation:")
    equation(doc, [
        "eₛ(T) = 0.6108 exp(17.27T / (T + 237.3))",
        "VPD = eₛ(T) × (1 − RH/100)",
    ])
    para(doc, "Here eₛ is saturation vapour pressure in kPa, T is air temperature in °C, and RH is relative humidity in percent. In the dataset, VPD was supplied as a pre-computed channel, so I did not recalculate it. The key thing to remember is that a high VPD means the air can absorb more moisture (relevant for plant water stress), but labelling a high-VPD day as 'stressed' would require paired biological measurements that this project does not have.")
    title(doc, "2.5 Sensor quality and auditability", 2)
    para(doc, "Anyone who has worked with long sensor records knows they contain problems: missing timestamps, duplicated readings, flat lines when a sensor froze, sudden jumps when it was bumped or re-positioned. The challenge is that removing everything that looks unusual can also remove real environmental events; for example, a sudden temperature spike during a heat wave is not a sensor error. The approach I used was to separate clearly broken records (hard cleaning) from readings that look unusual but might be genuine (review flags). This way, the impact of any screening decision is visible rather than buried.")
    title(doc, "2.6 Time-aware prediction and model evaluation", 2)
    para(doc, "Environmental measurements are not independent from one reading to the next, because today's temperature is strongly related to yesterday's. If you randomly split daily rows into training and test sets, the model can 'peek' at the future, producing results that look good but would fall apart in practice. Bergmeir, Hyndman and Koo [3] discuss why this matters for time-series forecasting. For this project, the chronological experiment uses the earliest 60% of days for training, the next 20% for picking the best model, and the final 20% is kept untouched until the very end. A second leave-one-site-out (LOSO) design asks a different question: how well do models transfer when one plot is left out entirely? The two designs answer different things and should not be compared as if they measure the same quantity.")
    title(doc, "2.7 Predictive baselines and reproducible tools", 2)
    para(doc, "Persistence (simply predicting that tomorrow will be the same as today) is the baseline that every model must beat. For slowly changing daily signals, this is surprisingly hard to improve upon, which is why it needs to be included as a real contender rather than a throwaway comparison. Elastic Net [4] and Random Forest [5] are included as transparent, well-understood alternatives. They are tested as readiness benchmarks, not proposed as deployed AI systems.")


def chapter_three(doc):
    page_break(doc)
    title(doc, "Chapter 3  Data, provenance and quality workflow", 1)
    title(doc, "3.1 Data source and schema", 2)
    para(doc, "The dataset provided for this project arrived as a binary R archive named ccnr_microclimate_data.Rdata. Before doing any processing, I calculated its SHA-256 checksum (673a82f38dd4ed5b2d0ce21c27eafd21ea68ef0655465a2c83092fc1eb3cbebb) to lock down the exact provenance. The file unrolls into a long-format table containing 1,002,949 individual sensor readings. Each row records a timestamp, a sensor serial number, the parameter measured, the numerical value, the plot identifier, and the forest successional stage. To keep the pipeline completely reproducible and prevent accidental data corruption, the original RData file is treated as read-only; all extraction, cleaning, and downstream tables are generated directly through the project notebook.")
    table(doc, ["Variable", "Recorded parameter", "Analytical role", "Interpretive caution"], [
        ["Temperature", "temp", "Daily thermal context and forecast target", "Air temperature at sensor position; not a canopy-wide temperature."],
        ["Relative humidity", "rh", "Moisture context, VPD input and forecast target", "Strongly affected by saturation/zero-VPD review rules."],
        ["VPD", "vpd", "Atmospheric moisture-demand context and label target", "Derived from temperature and RH; associations are not independent causal effects."],
        ["PAR", "par", "Light-environment context and forecast target", "Coverage differs by sensor and plot; screened upper-range values need review."],
        ["Soil moisture", "soil moisture", "Water-state and drydown target", "Sensor measurement; no rainfall or soil calibration record is available."],
    ], widths=[3, 3, 5.5, 7])
    title(doc, "3.2 Data tiers", 2)
    table(doc, ["Tier", "Rows", "Purpose"], [
        ["Raw source", "1,002,949", "Immutable source audit and provenance check."],
        ["Hard-cleaned", "1,002,899", "Primary EDA, labels, drydown and modelling dataset; quality flags remain available."],
        ["Review-screened", "920,216", "Sensitivity analysis that excludes declared review flags; not the primary dataset."],
    ], widths=[5, 3.5, 10])
    para(doc, "One of the most important decisions I had to make early on was how to clean this dataset without distorting reality. In tropical rainforests, relative humidity frequently hits 100% during prolonged rains, and VPD naturally drops to zero. If I had aggressively purged every 100% RH reading or zero VPD value as 'faulty', I would have stripped away genuine saturated weather conditions. On the other hand, leaving broken sensor trajectories unflagged could mislead machine learning models.")
    para(doc, "To solve this dilemma, I adopted a two-tier strategy. The hard-cleaned tier (1,002,899 rows) serves as the primary dataset; it discards only entries that are physically or computationally unviable (such as missing timestamps or soil moisture above physical saturation). Dubious values are not discarded here; instead, they are given traceable review flags. The review-screened tier (920,216 rows) then strips out these flagged readings purely as a sensitivity benchmark. By evaluating both tiers side-by-side, we can clearly see which conclusions are robust and which ones depend heavily on how strictly one cleans the data.")
    title(doc, "3.3 Cleaning rules", 2)
    table(doc, ["Stage", "Rule", "Treatment"], [
        ["Hard validity", "Missing required fields, invalid timestamps, non-finite values and unusable metadata.", "Remove only when the record cannot be used safely."],
        ["Humidity/VPD review", "RH ≤ 1%, RH = 100%, VPD = 0 paired with saturation, VPD > 6000 Pa.", "Retain in hard-cleaned tier; exclude from screened tier."],
        ["PAR review", "PAR ≥ 2500.", "Retain in hard-cleaned tier; exclude from screened tier."],
        ["Sensor trajectory", "Large within-two-hour jumps and flat lines over 24 or more samples.", "Flag as review conditions; do not infer a confirmed fault without maintenance logs."],
    ], widths=[3.2, 8.3, 7])
    title(doc, "3.4 Cleaning and coverage audit", 2)
    table(doc, ["Audit item", "Count", "Interpretation"], [
        ["Hard removals", "50 rows", "40 rows lacked a required timestamp or value; 10 soil-moisture readings exceeded 0.6 m³/m³."],
        ["Review-screened rows", "82,683 rows", "Excluded only from the sensitivity tier; retained, flagged and analysed in the primary hard-cleaned tier."],
        ["RH saturation review", "35,171 flags", "Most common review condition; counts are not mutually exclusive."],
        ["VPD zero paired with saturation", "35,166 flags", "A paired review condition that commonly occurs with RH saturation."],
        ["Flatline review", "23,099 flags", "Potential sensor trajectory issue; not asserted to be a confirmed hardware fault."],
        ["Daily coverage: temperature / RH / VPD", "4,852 / 4,852 / 4,852 plot-days", "Near-complete coverage of the observed plot-days in the hard-cleaned primary tier."],
        ["Daily coverage: PAR / soil moisture", "2,897 / 2,661 plot-days", "Substantially lower coverage; results for these variables use fewer paired days."],
    ], widths=[4.5, 4.0, 10.0])
    para(doc, "Table 8 highlights the distribution of review flags across the dataset. Because multiple flags can be attached to a single row (for example, a reading that hits 100% RH and 0 VPD simultaneously), the flag counts overlap. Only 50 rows out of more than a million were fundamentally invalid. What stood out prominently during this audit was sensor coverage: temperature, RH, and VPD provided 4,852 plot-days of observations, whereas PAR (2,897 plot-days) and soil moisture (2,661 plot-days) had much sparser timelines. This asymmetry meant that all multi-variable analyses had to account strictly for paired observations rather than assuming uniform temporal coverage across all sensors.")
    title(doc, "3.5 Quality sensitivity", 2)
    para(doc, "To test whether screening alters the everyday picture of microclimate, I paired the daily means from both tiers across every available plot-day. Figure 2 shows the resulting daily-mean difference distributions.")
    figure(doc, "quality/screening_sensitivity_daily_means.png", "Figure 2. Sensitivity of daily means to the review-screening policy.")
    para(doc, "The comparison gave an encouraging result for temperature and soil moisture: their daily averages remained virtually identical across both tiers (median change indistinguishable from zero). In contrast, RH showed a median absolute shift of 0.49 percentage points, and VPD shifted by 18.0 Pa. This confirms that broad thermal and hydrological trends are stable, but threshold-sensitive metrics (such as whether a day crosses an extreme VPD boundary) are sensitive to the filtering policy. In the subsequent chapters, I therefore treat continuous physical trends as robust, while treating threshold categories with appropriate caution.")
    title(doc, "3.6 Exploratory data analysis: notebook results summary", 2)
    para(doc, "Before jumping into machine learning or time-series modelling, I carried out exploratory data analysis inside the project Jupyter notebook (clean_microclimate.ipynb). Figure 3 shows a direct screen capture from this executed notebook, showing the automated cleaning audit and parameter breakdown.")
    eda_summary = ROOT / "docs" / "assets" / "notebook_cleaning_summary_cell.png"
    asset_figure(doc, eda_summary, "Figure 3. Executed notebook cell screenshot showing cleaning audit counts and final parameter distribution.", width=6.15, source_note="Source: clean_microclimate.ipynb executed notebook cells [15] and [16].")
    table(doc, ["EDA question", "Result from the primary daily tier", "Decision carried into methods"], [
        ["Is the record broadly usable after cleaning?", "1,002,899 of 1,002,949 records remain; only 50 confirmed-invalid records were removed.", "Use the hard-cleaned tier as primary evidence and retain review flags for traceability."],
        ["Which variables have complete daily support?", "Temperature, RH and VPD each have 4,852 plot-days; PAR has 2,897 and soil moisture 2,661.", "Keep plot identity and paired-day counts; treat PAR and soil-moisture results as coverage-limited."],
        ["What scale do the recorded variables have?", "Means: temperature 26.39 °C, RH 91.12%, soil moisture 0.21 m³/m³. Their ranges remain visible in the notebook output.", "Standardise variables before PCA; compare change within plots rather than treating unlike scales as directly comparable."],
        ["Do review flags change broad daily summaries?", "Temperature and soil moisture change little; RH and VPD show greater screening sensitivity.", "Report the screened tier only as a sensitivity check and avoid over-interpreting threshold labels."],
    ], widths=[4.7, 7.0, 7.0])
    para(doc, "These exploratory checks laid down clear guardrails for the rest of the project. First, raw sensor rows could not be treated as independent data points; they had to be aggregated into daily plot-level records. Second, because different variables operate on vastly different scales (VPD in Pa, light in PAR units, soil moisture in volumetric fraction), standardisation was essential prior to clustering or PCA. Finally, knowing that PAR and soil moisture have significant missing periods guided the structure of the forecasting experiments.")


def chapter_four(doc):
    page_break(doc)
    title(doc, "Chapter 4  Methods", 1)
    title(doc, "4.1 Analytical approach and workflow design", 2)
    para(doc, "The methodological goal of this project was to establish an auditable, end-to-end data processing and evaluation pipeline. Starting from the immutable raw RData source, the workflow enforces strict data hygiene: raw inputs are validated, two distinct data tiers are maintained, rows are aggregated to daily intervals, features are engineered without future leakage, and models are tested under realistic temporal and spatial holdout designs. Rather than treating machine learning as an end in itself, models are evaluated as diagnostic readiness tests to determine whether environmental signals carry predictable structure beyond simple persistence.")
    title(doc, "4.2 Daily aggregation and descriptive analysis", 2)
    para(doc, "The raw sensor readings arrived at heterogeneous, high-frequency intervals (often 15 to 60 minutes apart). Treating individual sensor timestamps as independent observations in statistical tests or machine learning would cause extreme pseudo-replication, inflating sample sizes and giving an artificially confident impression of statistical significance. To avoid this, I aggregated readings by plot and calendar date into a cohesive daily summary matrix.")
    para(doc, "Each plot-day record contains daily mean values alongside daily minimums, maximums, and diurnal ranges for temperature, RH, VPD, PAR, and soil moisture. Daily means provide a stable baseline for comparing seasonal and site-level shifts, while daily ranges capture extreme diurnal fluctuations that a simple mean might obscure. Figure 4 shows the notebook code section responsible for generating these daily features and handling missing timestamps cleanly.")
    asset_figure(doc, ROOT / "output" / "playwright" / "notebook_daily_feature_engineering.png", "Figure 4. Executed notebook excerpt: daily feature construction used for exploratory analysis and forecasting.", width=6.15, source_note="Source: Executed submission notebook; local browser capture using Playwright.")
    title(doc, "4.3 Within-plot association analysis", 2)
    para(doc, "When analysing environmental relationships across multiple forest plots, calculating a naive correlation across all pooled data points can produce misleading results (Simpson's paradox), where between-plot elevation or micro-topography offsets mask or reverse the true local physical dynamics. To address this, I calculated Spearman rank correlations separately within each individual plot, then computed the median within-plot coefficient (rho).")
    para(doc, "Because daily environmental time series exhibit strong serial autocorrelation, standard independent and identically distributed (i.i.d.) bootstrap resampling would break the temporal dependency and produce spuriously narrow confidence intervals. Instead, I implemented a 14-day non-circular moving-block bootstrap with 500 resamples. In this approach, blocks of 14 consecutive daily observations are sampled with replacement strictly within each plot's observed timeline, preserving short-range weather continuity while generating robust empirical intervals.")
    title(doc, "4.4 Soil-moisture drydown summaries", 2)
    para(doc, "Soil moisture dynamics during dry periods offer critical insight into how different forest stands lose moisture. To examine this behaviour empirically, I developed an algorithm to identify consecutive decreasing daily soil moisture sequences in the primary tier. An event was defined as a sequence of continuous daily soil-moisture declines lasting at least 4 days without intermediate recharge.")
    para(doc, "For each drydown event, I calculated the total duration (days), total volumetric loss (m³/m³), linear drying rate (slope magnitude per day), and an empirical half-life (days required to lose 50% of the initial event moisture). In addition, an exponential decay model was fitted to provide a normalised visual comparison across events. These metrics describe observed drying behaviour across the seven plots; they do not constitute a full hydrological balance model, as rainfall and soil-depth measurements were not recorded.")
    title(doc, "4.5 Environmental labels", 2)
    para(doc, "To test whether microclimate conditions could be framed as an environmental state-classification problem, I established discrete daily VPD-state categories based on atmospheric moisture demand thresholds: Low (< 400 Pa), Moderate (400–1200 Pa), and High (> 1200 Pa). These labels represent environmental conditions rather than verified biological stress. Because threshold categories can be sensitive to sensor screening, tier agreement was tracked across all paired plot-days. To account for natural class imbalance, classification models were evaluated using macro-averaged F1-score and balanced accuracy rather than raw classification accuracy.")
    title(doc, "4.6 Feature engineering and leakage prevention", 2)
    table(doc, ["Feature group", "Examples", "Availability before next-day prediction"], [
        ["Calendar", "Day of year and cyclic seasonal terms.", "Known in advance."],
        ["Same-day state", "Current daily values of companion variables.", "Available only after the day's recording window closes."],
        ["Lagged state", "Lag-1 target and one-day lagged companion variables.", "Available at forecast origin."],
        ["Rolling history", "3-day and 7-day rolling means over observations available by the end of day t.", "Available at forecast origin when enough history exists."],
        ["Site metadata", "Plot and forest-type identifiers.", "Used cautiously; not a substitute for unseen-site testing."],
    ], widths=[3.5, 8, 6.5])
    para(doc, "Feature engineering was structured strictly around chronological forecast constraints. When predicting conditions for day t + 1, all features must be computable from data available at or before the close of day t. The feature set comprises calendar terms (day of year, sinusoidal harmonic seasonal terms), lag-1 values of the target and companion microclimate variables, and 3-day and 7-day rolling summary statistics (means, standard deviations, and ranges).")
    para(doc, "Crucially, rolling statistics were calculated using backwards-looking rolling windows only, completely avoiding future data leakage. Rows missing the next consecutive day (due to sensor outages) were dropped from target alignment rather than filled with interpolated future data. For exploratory multivariable analysis, all five daily variables were standardised to zero mean and unit variance before running K-means clustering and Principal Component Analysis (PCA). Figure 5 illustrates the standardization and PCA implementation from the notebook.")
    asset_figure(doc, ROOT / "output" / "playwright" / "notebook_pca_regimes.png", "Figure 5. Executed notebook excerpt: standardisation, clustering and PCA for daily microclimate pattern discovery.", width=6.15, source_note="Source: Executed submission notebook; local browser capture using Playwright.")
    title(doc, "4.7 Evaluation designs", 2)
    table(doc, ["Design", "Split", "Question answered", "Important limitation"], [
        ["Chronological final test", "Earliest 60% train / next 20% validation / final 20% untouched test.", "Can a method predict a later period at monitored plots?", "It does not test transfer to a new plot."],
        ["LOSO site transfer", "Fit each candidate on six plots; score it on the seventh; repeat for seven plots.", "How do candidate models vary when a plot is held out?", "The reported best candidate is chosen from these same outer-fold scores; this is exploratory, not nested selection."],
    ], widths=[3.5, 5.5, 5.5, 3.5])
    para(doc, "I designed two distinct evaluation schemes to test different practical questions. The first is a chronological 60/20/20 train/validation/test split. In this setup, the earliest 60% of calendar dates are used for model training, the intermediate 20% for hyperparameter tuning and model selection, and the final 20% is held completely untouched as a true forward-looking test set. This evaluates how well models forecast into the future at familiar, monitored sites.")
    para(doc, "The second scheme is a leave-one-site-out (LOSO) cross-validation, designed to test spatial transferability. In each of seven iterations, one forest plot is completely withheld as the test target while models are trained on the remaining six plots. This simulates deploying a predictive model to an unmonitored forest plot.")
    para(doc, "Across both schemes, Persistence (predicting that day t + 1 will equal day t) serves as the primary baseline. In time series with strong day-to-day inertia, persistence is a formidable benchmark. Machine learning models (Ridge regression, Elastic Net, Random Forest, and Histogram Gradient Boosting) are judged by whether they can demonstrably surpass persistence on root mean squared error (RMSE), mean absolute error (MAE), and coefficient of determination (R²). Figure 6 shows the chronological evaluation setup in the notebook.")
    asset_figure(doc, ROOT / "output" / "playwright" / "notebook_leakage_safe_forecasting.png", "Figure 6. Executed notebook excerpt: strictly historical features and the chronological 60/20/20 VPD-state evaluation.", width=6.15, source_note="Source: Executed submission notebook; local browser capture using Playwright.")


def chapter_five(doc):
    page_break(doc)
    title(doc, "Chapter 5  Results", 1)
    title(doc, "5.1 Coverage and daily conditions across plots", 2)
    para(doc, "Figures 7 through 11 present the daily mean time series for all five microclimate variables across the seven monitored plots. By plotting all plots on shared axes, both the overarching temporal rhythms and the plot-specific baseline offsets become immediately evident. These graphs illustrate the empirical conditions measured during the study period; they capture physical realities rather than proving that differences stem solely from forest age or canopy structure.")
    figure(doc, "temperature/temperature_A_daily_mean_shared.png", "Figure 7. Daily mean temperature by plot on shared axes.")
    figure(doc, "rh/rh_A_daily_mean_shared.png", "Figure 8. Daily mean relative humidity by plot on shared axes.")
    figure(doc, "par/par_A_daily_mean_shared.png", "Figure 9. Daily mean PAR by plot on shared axes.")
    figure(doc, "soil/soil_A_daily_mean_shared.png", "Figure 10. Daily mean soil moisture by plot on shared axes.")
    figure(doc, "vpd/vpd_A_daily_mean_shared.png", "Figure 11. Daily mean VPD by plot on shared axes.")
    para(doc, "Across all five parameters, regional weather shifts induce shared day-to-day peaks and troughs across every plot simultaneously. Yet beneath this common weather pulse, clear plot-specific baselines persist. In particular, soil moisture shows pronounced stratifications, with some plots maintaining consistently higher water content throughout the observation window. While tempting to attribute these differences purely to canopy buffering, unrecorded local factors such as sensor burial depth, micro-topographical drainage, and immediate soil texture likely contribute. This confirms the necessity of examining within-plot relationships rather than pooling data indiscriminately.")
    title(doc, "5.2 Physical relationships between daily variables", 2)
    figure(doc, "readiness/daily_spearman_heatmap.png", "Figure 12. Within-plot daily Spearman relationships with moving-block bootstrap intervals.")
    table(doc, ["Relationship", "Paired plot-days", "Median within-plot ρ", "Bootstrap interval"], [
        ["RH – VPD", "4,852", "-0.991", "-0.994 to -0.987"],
        ["Temperature – VPD", "4,852", "0.757", "0.700 to 0.805"],
        ["VPD – soil moisture", "2,661", "-0.501", "-0.613 to -0.446"],
        ["Temperature – PAR", "2,897", "0.404", "0.360 to 0.582"],
        ["PAR – soil moisture", "2,617", "-0.197", "-0.328 to -0.093"],
    ], widths=[5, 4, 4.5, 5])
    para(doc, "Table 12 and Figure 12 document the within-plot Spearman correlation coefficients alongside their 14-day moving-block bootstrap confidence intervals. As expected from thermodynamic principles, relative humidity and VPD exhibit a nearly perfect inverse association (median within-plot rho = -0.991). Because VPD is mathematically computed directly from temperature and RH, this strong correlation validates physical consistency rather than revealing an independent biological mechanism.")
    para(doc, "More informatively, the correlation between temperature and VPD is consistently positive across all plots (median rho = 0.757), while the coupling between atmospheric demand (VPD) and soil moisture is moderately negative (median rho = -0.501, bootstrap interval -0.613 to -0.446). On days when the air is warm and dry, soil moisture steadily diminishes as evapotranspiration draws water from the understorey. Figure 13 plots these pairwise relationships across individual plots, demonstrating that while slopes vary slightly by site, the directional dynamics remain robust.")
    figure(doc, "readiness/daily_relationship_scatter.png", "Figure 13. Selected daily relationships, plotted by monitored plot.")
    title(doc, "5.3 Recurring daily microclimate regimes", 2)
    para(doc, "To investigate whether multivariable microclimate conditions cluster into recognisable environmental 'states', I standardised the five daily parameters and performed Principal Component Analysis (PCA) combined with K-means clustering. Figure 14 maps the plot-days onto the first two principal components, with cluster colours selected by silhouette score.")
    figure(doc, "readiness/daily_regime_pca.png", "Figure 14. Daily microclimate regimes in PCA space; colours show exploratory groups selected by silhouette score.")
    para(doc, "The two principal components account for the vast majority of environmental variance: PC1 separates hot, high-VPD, bright conditions from cool, humid, low-light days, while PC2 captures variations in soil moisture saturation. The distinct groupings demonstrate that forest understorey microclimates do not fluctuate randomly; they navigate recurring regimes ranging from saturated post-rain conditions to sustained dry, high-radiation spells. This provides a clear, quantitative vocabulary for future ecological studies linking seedling survival to specific microclimate regimes.")
    title(doc, "5.4 Soil-moisture drydown dynamics", 2)
    para(doc, "Extended dry intervals represent critical stress periods for forest regeneration. Figures 15 and 16 isolate multi-day drydown events where soil moisture experienced continuous decline.")
    figure(doc, "soil_moisture/soil_D_drydown_event_timeline.png", "Figure 15. Identified soil-moisture drydown events over time.")
    figure(doc, "soil_moisture/soil_G_normalized_drydown_curves.png", "Figure 16. Normalised drydown curves by plot.")
    table(doc, ["Plot", "Events", "Median duration (days)", "Median total loss", "Median |drying rate|"], [
        ["CN2", "27", "6.0", "0.0835", "0.0156"],
        ["FT4MD", "38", "6.0", "0.0549", "0.0084"],
        ["FT4MR", "25", "5.0", "0.0661", "0.0129"],
        ["FT4TH", "11", "4.0", "0.0639", "0.0121"],
        ["LP3", "43", "5.0", "0.1140", "0.0203"],
        ["UP2", "30", "5.5", "0.0705", "0.0117"],
        ["US5", "35", "6.0", "0.0777", "0.0128"],
    ], widths=[3, 2.5, 4, 4, 4.5])
    para(doc, "Table 13 and Figures 17 and 18 quantify these event profiles. Marked differences emerge across sites: secondary forest plot LP3 demonstrated both the highest median drying rate (0.0203 m³/m³ per day) and the largest total moisture depletion (0.1140), losing water rapidly during rainless spells. In contrast, mature primary plot FT4MD exhibited the slowest median drying rate (0.0084 m³/m³ per day), buffering soil moisture noticeably better.")
    figure(doc, "soil_moisture/soil_E_drying_rate_summary.png", "Figure 17. Soil-moisture drying-rate summary by monitored plot.")
    figure(doc, "soil_moisture/soil_F_half_life_summary.png", "Figure 18. Empirical soil-moisture half-life summary by monitored plot.")
    para(doc, "The empirical half-life distributions in Figure 18 corroborate this distinction: plots with steeper drying rates reach 50% moisture depletion significantly faster. While suggestive of differences in canopy interception and organic soil depth, these observations remain descriptive until verified with co-located soil grain analyses and rainfall records.")
    title(doc, "5.5 VPD-state classification benchmark", 2)
    para(doc, "In the classification experiment, models were trained to predict whether the following day's atmospheric demand would fall into Low, Moderate, or High VPD categories. Evaluating on the strictly held-out chronological final 20% test period (778 observations), the validation-selected logistic regression model achieved an accuracy of 0.501, a balanced accuracy of 0.594, a macro-F1 of 0.505, and a multi-class one-vs-rest AUC of 0.816. Figure 19 depicts the corresponding test confusion matrix.")
    figure(doc, "readiness/vpd_state_final_test_confusion_matrix.png", "Figure 19. VPD-state classification confusion matrix for the untouched chronological final period.")
    para(doc, "The model accurately identified moderate conditions but showed expected boundary confusion between adjacent states during rapid weather transitions. Crucially, the screening sensitivity analysis revealed that between the hard-cleaned and screened tiers, 83.5% of daily VPD-state labels agreed (4,048 of 4,846 paired plot-days). This underscores that while state classification is feasible, threshold-based categories are sensitive to sensor screening at the boundaries.")
    title(doc, "5.6 One-day-ahead chronological forecasting", 2)
    para(doc, "Table 14 and Figure 20 report the definitive one-day-ahead forecasting performance evaluated on the untouched forward-looking test set. For four of the five targets (Temperature, RH, VPD, and Soil Moisture), Persistence was selected as the optimal model on validation and remained unmatched on the final test set. Figure 21 displays the permutation feature importances, while Figure 22 illustrates a representative soil moisture forecast trace during drydown.")
    table(doc, ["Target", "Selected model", "Final rows (plots)", "MAE", "RMSE", "R²", "MAE vs persistence"], [
        ["Temperature", "Persistence", "776 (7)", "0.755", "0.966", "0.192", "Equal"],
        ["RH", "Persistence", "776 (7)", "2.607", "3.565", "0.485", "Equal"],
        ["VPD", "Persistence", "776 (7)", "137.500", "198.228", "0.411", "Equal"],
        ["PAR", "Random Forest", "160 (4)", "6.979", "12.996", "0.180", "54.09% worse"],
        ["Soil moisture", "Persistence", "152 (3)", "0.0121", "0.0174", "0.925", "Equal"],
    ], widths=[3, 3.6, 2.8, 2.5, 2.8, 2.2, 3.5])
    figure(doc, "forecasting/daily_model_comparison.png", "Figure 20. Daily forecast comparison against persistence baselines.", width=5.0)
    figure(doc, "forecasting/daily_feature_importance.png", "Figure 21. Held-out permutation feature importance for selected models.", width=5.35)
    figure(doc, "forecasting/daily_soil_moisture_drydown_forecast.png", "Figure 22. Representative daily soil-moisture forecast during drydown conditions.")
    para(doc, "This outcome is methodologically significant. For daily soil moisture, persistence achieves an impressive R² of 0.925 and an MAE of 0.0121 m³/m³, because soil water evolves with high inertia. For PAR, light fluctuates erratically with local cloud cover; although Random Forest was chosen during validation, it scored 54.09% worse than persistence on the final test set, demonstrating the risk of overfitting noisy solar radiation series.")
    title(doc, "5.7 Spatial leave-one-site-out transferability", 2)
    para(doc, "When the task shifts from forecasting the future at a known site to predicting conditions at an unseen forest plot (leave-one-site-out cross-validation), the results diverge meaningfully from the chronological test. Table 15 summarises the performance across the seven held-out folds.")
    table(doc, ["Target", "Best model", "MAE", "RMSE", "R²", "Site-level MAE SD"], [
        ["Temperature", "Random Forest", "0.620", "0.779", "0.462", "0.218"],
        ["RH", "Random Forest", "2.693", "3.345", "0.491", "0.744"],
        ["VPD", "Random Forest", "130.073", "162.012", "0.393", "62.815"],
        ["PAR", "Persistence", "10.580", "19.834", "-0.152", "10.454"],
        ["Soil moisture", "Persistence", "0.0152", "0.0204", "0.750", "0.0042"],
    ], widths=[3, 4, 3, 3, 2.5, 4])
    para(doc, "In this spatial transfer setting, Random Forest outperformed persistence for temperature, RH, and VPD, achieving held-out R² values near 0.40–0.49. By learning common seasonal and cross-variable dependencies across six plots, the tree ensemble generalised better to an unmonitored plot than simply using the last known reading from another sensor. For PAR and soil moisture, however, persistence remained superior, reflecting the strong plot-specific baselines and sensor-specific calibrations.")
    title(doc, "5.8 Robustness across screening tiers", 2)
    figure(doc, "screening_robustness/screening_robustness_summary.png", "Figure 23. Summary of results that were stable and sensitive across the two data tiers.")
    para(doc, "Figure 23 encapsulates the comprehensive robustness audit comparing primary hard-cleaned and review-screened tiers. The core physical associations remained virtually invariant: the maximum shift in median within-plot Spearman rho was merely 0.095 (for temperature–PAR), and all correlation signs were identical. The findings confirm that while discrete classification labels are sensitive to threshold screening, the continuous microclimate dynamics and predictive baselines are thoroughly stable.")


def chapter_six(doc):
    page_break(doc)
    title(doc, "Chapter 6  Discussion and project readiness", 1)
    title(doc, "6.1 What the analysis establishes", 2)
    para(doc, "Stepping back from the raw numbers and code, the core contribution of this project is establishing a dependable, auditable environmental baseline. Prior to this work, the raw dataset existed as an unverified mass of more than one million sensor records with unknown failure rates, unaddressed sensor saturation, and potential data-leakage pitfalls. By introducing transparent two-tier cleaning, daily aggregation, and leakage-safe validation, I have converted raw data into an analytical asset that future researchers can trust.")
    para(doc, "The physical findings hold together with reassuring consistency. The thermodynamic link between RH and VPD is verified across all sites, while the moderate negative association between atmospheric demand (VPD) and soil moisture provides a quantitative pulse of understorey evapotranspiration. Similarly, the PCA projection and drydown timelines offer a concrete way to characterise how different forest plots weather rainless spells. Rather than presenting isolated correlation coefficients, this report delivers an interconnected picture of Singapore tropical forest microclimates.")
    title(doc, "6.2 Understanding the predictive findings: Why persistence matters", 2)
    para(doc, "In applied machine learning, students often feel pressured to demonstrate that complex tree ensembles or deep neural networks outperform simple baselines. In physical time-series forecasting, however, the persistence baseline (which assumes tomorrow will mirror today) is not a trivial placeholder; it is a formidable physical competitor. Environmental variables like soil moisture and temperature possess immense thermal and hydrological inertia.")
    para(doc, "The fact that persistence was selected for four of the five targets on the chronological test period is an insightful finding rather than a shortcoming. It establishes an honest empirical floor: any complex model proposed in the future must justify its computational and operational overhead by genuinely beating persistence. Furthermore, our leave-one-site-out experiments revealed where machine learning actually adds value: in spatial transfer. When deploying to an unmonitored plot, Random Forest successfully generalised shared cross-variable dynamics for temperature, RH, and VPD, achieving held-out R² values of 0.40–0.49 where persistence had no local history to draw from.")
    title(doc, "6.3 The boundary between microclimate and restoration health", 2)
    para(doc, "The FYP theme centers on AI for Forest Restoration. However, throughout this project, I maintained a strict conceptual boundary between environmental monitoring and biological health assessment. The sensor loggers measure physical variables in the air and upper soil; they do not observe whether saplings survived, whether canopy foliage is expanding, or whether fungal pathogens are present. Claiming that a machine learning model predicted 'restoration success' from these microclimate streams alone would be unscientific and misleading.")
    para(doc, "Instead, this study builds the essential abiotic foundation. When paired with future field surveys of sapling survival, drone-based multispectral imagery, or LiDAR canopy height models, the microclimate regimes and drydown rates documented here will provide the exact environmental context needed to explain why certain restoration plantings thrive while others fail.")
    title(doc, "6.4 Limitations and lessons learned", 2)
    table(doc, ["Limitation", "Effect on interpretation", "Practical response"], [
        ["No tree-health, survival or growth labels", "No model can predict tree health from this dataset alone.", "Collect matched biological outcomes before defining a health target."],
        ["No LiDAR or image products", "Canopy structure and species context cannot be tested.", "Co-register future remote-sensing products with plot and date."],
        ["No rain, maintenance or calibration log", "Drydown and sensor flags cannot be assigned a definitive physical or hardware cause.", "Link weather and sensor-maintenance records prospectively."],
        ["Seven plots", "Site comparisons are descriptive and have limited generalisability.", "Increase plot coverage and reserve an external site set."],
        ["VPD derived from temperature and RH", "Pairwise VPD correlations are partly mathematical.", "Avoid presenting VPD links as independent causal effects."],
        ["Screening policy is not externally calibrated", "Threshold labels can change across tiers.", "Treat cut-offs as review rules and conduct calibration checks."],
    ], widths=[4.2, 6.8, 6])
    para(doc, "Table 16 summarizes the primary constraints identified during the project. The absence of local rainfall data represents the most significant gap in modelling soil drydown, as we had to infer dry spells purely from decreasing moisture curves. Similarly, having only seven plots restricts broad ecological generalisation across forest successional types. Acknowledging these constraints openly strengthens the engineering credibility of the work and provides clear guidance for subsequent project cohorts.")
    title(doc, "6.5 Data-readiness and handover assessment", 2)
    para(doc, "In its current form, the project codebase, clean data tiers, and reproducibility manifest are fully ready for academic handover. All 71 cells of the submission notebook execute without error, regenerating all 23 figures, 17 tables, and the JSON manifest from the immutable RData file. Future researchers can immediately import the cleaned plot-day matrices (`df_clean` and `df_daily`) without having to repeat the tedious audit and cleaning process.")
    title(doc, "6.6 Engineering integrity and reporting ethics", 2)
    para(doc, "Engineering integrity requires resisting the urge to over-claim. In environmental data science, deploying uncalibrated black-box models can misallocate valuable ecological conservation funding. By transparently reporting negative results (such as Random Forest failing to beat persistence on PAR), demonstrating data-tier sensitivity, and clearly delineating what the data can and cannot prove, this report adheres to the highest standards of academic honesty.")


def chapter_seven(doc):
    page_break(doc)
    title(doc, "Chapter 7  Conclusion and future work", 1)
    title(doc, "7.1 Conclusion", 2)
    para(doc, "This final year project set out to investigate whether a large, noisy microclimate sensor dataset could be turned into a rigorous, dependable foundation for tropical forest restoration research. By methodically processing 1,002,949 raw observations across seven forest plots in Singapore's Central Catchment Nature Reserve, this question has been answered affirmatively within clear, well-defined boundaries.")
    para(doc, "The project delivered five key conclusions aligned directly with the research questions:")
    bullets(doc, [
        "Data Reliability: Out of over a million records, only 50 were fundamentally corrupt, while 82,683 warranted review flags. Temperature and soil moisture daily means proved completely impervious to screening policy, while RH and VPD showed moderate sensitivity (0.49% RH and 18.0 Pa VPD median shifts).",
        "Environmental Dynamics: Daily conditions exhibited pronounced plot-specific baselines beneath shared regional weather pulses. Secondary forest plot LP3 lost soil moisture at more than twice the rate of primary plot FT4MD during dry spells (median 0.0203 vs 0.0084 m³/m³ per day).",
        "Physical Relationships: Robust within-plot Spearman correlations confirmed thermodynamic consistency (RH–VPD rho = -0.991; Temp–VPD rho = 0.757) and revealed a consistent negative coupling between atmospheric moisture demand and soil water (rho = -0.501, 14-day block bootstrap interval -0.613 to -0.446).",
        "Predictive Performance: In temporal chronological forecasting, Persistence was the optimal baseline for temperature, RH, VPD, and soil moisture (R² = 0.925 for soil moisture), outperforming complex models. In spatial site-transfer (LOSO), Random Forest successfully generalised temperature, RH, and VPD (R² 0.40–0.49) to unmonitored plots.",
        "Readiness Boundary: The study established a fully reproducible daily environmental dataset and confirmed that direct tree-health modelling must await matched biological outcome labels.",
    ])
    title(doc, "7.2 Recommendations for future work", 2)
    para(doc, "To advance this research toward operational restoration management, I recommend a phased progression:")
    bullets(doc, [
        "Phase 1 (Local Weather Metadata): Incorporate co-located tipping-bucket rain gauges and sensor maintenance logs. Linking actual precipitation events will transform empirical drydown tracking into physical hydrological balance modelling.",
        "Phase 2 (Biological Ground Truth): Define and collect discrete, georeferenced sapling outcomes (e.g., mortality counts, stem diameter growth, leaf wilting indices) paired temporally with the microclimate stations.",
        "Phase 3 (Remote Sensing Layers): Co-register drone LiDAR canopy height models and multispectral vegetation indices (NDVI, NDRE) to quantify how specific canopy structure metrics modulate ground-level buffering.",
        "Phase 4 (Multi-Site Deployment & Horizon Forecasting): Expand the sensor footprint to additional degraded sites and evaluate decision-relevant forecast horizons (3 to 7 days ahead) to provide actionable early-warning alerts for field intervention teams.",
    ])


def references(doc):
    page_break(doc)
    title(doc, "References", 1)
    refs = [
        "[1] K. De Frenne et al., “Global buffering of temperatures under forest canopies,” Nature Ecology & Evolution, vol. 3, pp. 744–749, 2019, doi: 10.1038/s41559-019-0842-1.",
        "[2] R. G. Allen, L. S. Pereira, D. Raes and M. Smith, Crop Evapotranspiration: Guidelines for Computing Crop Water Requirements, FAO Irrigation and Drainage Paper 56. Rome: FAO, 1998.",
        "[3] C. Bergmeir, R. J. Hyndman and B. Koo, “A note on the validity of cross-validation for evaluating autoregressive time series prediction,” Computational Statistics & Data Analysis, vol. 120, pp. 70–83, 2018, doi: 10.1016/j.csda.2017.11.003.",
        "[4] H. Zou and T. Hastie, “Regularization and variable selection via the elastic net,” Journal of the Royal Statistical Society: Series B, vol. 67, no. 2, pp. 301–320, 2005, doi: 10.1111/j.1467-9868.2005.00503.x.",
        "[5] L. Breiman, “Random forests,” Machine Learning, vol. 45, pp. 5–32, 2001, doi: 10.1023/A:1010933404324.",
        "[6] W. McKinney, “Data structures for statistical computing in Python,” in Proceedings of the 9th Python in Science Conference, 2010, pp. 56–61, doi: 10.25080/Majora-92bf1922-00a.",
        "[7] C. R. Harris et al., “Array programming with NumPy,” Nature, vol. 585, pp. 357–362, 2020, doi: 10.1038/s41586-020-2649-2.",
        "[8] J. D. Hunter, “Matplotlib: A 2D graphics environment,” Computing in Science & Engineering, vol. 9, no. 3, pp. 90–95, 2007, doi: 10.1109/MCSE.2007.55.",
        "[9] F. Pedregosa et al., “Scikit-learn: Machine learning in Python,” Journal of Machine Learning Research, vol. 12, pp. 2825–2830, 2011.",
        "[10] M. Kuhn and K. Johnson, Applied Predictive Modeling. New York: Springer, 2013, doi: 10.1007/978-1-4614-6849-3.",
        "[11] M. Sokolova and G. Lapalme, “A systematic analysis of performance measures for classification tasks,” Information Processing & Management, vol. 45, no. 4, pp. 427–437, 2009, doi: 10.1016/j.ipm.2009.03.002.",
        "[12] T. Fawcett, “An introduction to ROC analysis,” Pattern Recognition Letters, vol. 27, no. 8, pp. 861–874, 2006, doi: 10.1016/j.patrec.2005.10.010.",
        "[13] R. J. Hyndman and G. Athanasopoulos, Forecasting: Principles and Practice, 3rd ed. Melbourne: OTexts, 2021. Available: https://otexts.com/fpp3/.",
        "[14] H. R. Künsch, “The jackknife and the bootstrap for general stationary observations,” The Annals of Statistics, vol. 17, no. 3, pp. 1217–1241, 1989, doi: 10.1214/aos/1176347265.",
        "[15] R. H. Spearman, “The proof and measurement of association between two things,” The American Journal of Psychology, vol. 15, no. 1, pp. 72–101, 1904, doi: 10.2307/1412159.",
        "[16] F. Zellweger et al., “Advances in microclimate ecology arising from remote sensing,” Trends in Ecology & Evolution, vol. 34, no. 4, pp. 327–341, 2019, doi: 10.1016/j.tree.2018.11.012.",
    ]
    for ref in refs:
        p = doc.add_paragraph(ref)
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(2)


def appendices(doc):
    page_break(doc)
    title(doc, "Appendix A  Data audit and reproducibility checklist", 1)
    table(doc, ["Item", "Recorded evidence"], [
        ["Raw file", "ccnr_microclimate_data.Rdata; SHA-256 recorded in Chapter 3."],
        ["Rows", "1,002,949 raw; 1,002,899 hard-cleaned primary tier; 920,216 review-screened sensitivity tier."],
        ["Submission notebook", "notebooks/clean_microclimate.ipynb with all figures and output cells embedded."],
        ["Execution", "71 code cells executed without error in the final saved notebook."],
        ["Outputs", "Tables and PNG figures under outputs/redesigned/, with a reproducibility manifest."],
        ["Scope boundary", "No health outcomes, LiDAR, imagery, rainfall, calibration or maintenance logs supplied."],
    ], widths=[5, 13])
    title(doc, "Appendix B  Cleaning and analysis notes", 1)
    para(doc, "Hard cleaning removes only records that are unusable because of missing or invalid essential values. Review screening excludes readings meeting declared value, jump or flat-line conditions only for the sensitivity comparison. The screening conditions are not claimed to be calibrated error thresholds, so the hard-cleaned tier remains the primary analysis dataset with all review flags retained for traceability.")
    para(doc, "Daily association intervals use 500 non-circular moving-block bootstrap replicates with blocks of 14 days. Blocks remain within each observed plot sequence and therefore never connect the last date to the first. The block length was chosen as a conservative short-range dependence unit for daily environmental data; it is not a universal parameter or a source of causal identification. The LOSO results show variation over seven held-out plots, which is reported as site-level spread rather than a confidence interval.")
    page_break(doc)
    title(doc, "Appendix C  Supplementary variable views", 1)
    para(doc, "Repeated temperature, RH and PAR panels have been removed because their shared-axis versions are already discussed in Chapter 5. This appendix retains only the two variables used in the event and prediction analyses: soil moisture and VPD. The faceted form makes within-plot movement easier to inspect when a plot has a narrower range or shorter record. These figures provide supporting detail; they do not add claims beyond the coverage and association results in the main text.")
    figure(doc, "soil/soil_A_daily_mean_faceted.png", "Figure C1. Supplementary daily soil-moisture view by plot.")
    figure(doc, "vpd/vpd_A_daily_mean_faceted.png", "Figure C2. Supplementary daily VPD view by plot.")
    page_break(doc)
    title(doc, "Appendix D  Supplementary drydown and prediction figures", 1)
    para(doc, "The main body contains the figures needed to answer the research questions. The plots below are retained as supporting diagnostics: they show the hourly demonstration, range summaries and exploratory plot-level diagnostics that underpin the cautious language in Chapters 5–7. They provide additional detail without changing the conclusions: drydown patterns remain descriptive, the plot-summary models remain hypothesis-generating because n = 7, and forecast performance is judged from the stated held-out tables rather than a single visual example.")
    figure(doc, "forecasting/hourly_forecast_demonstration.png", "Figure D1. Supplementary hourly forecast demonstration.")
    figure(doc, "soil_moisture/soil_I_daily_range_summary.png", "Figure D2. Daily soil-moisture range summary by plot.")
    figure(doc, "soil_moisture/soil_J_plot_summary_model_comparison.png", "Figure D3. Exploratory plot-summary model comparison.")
    figure(doc, "soil_moisture/soil_K_plot_summary_trait_links.png", "Figure D4. Exploratory plot-summary trait-link view; n = 7, therefore hypothesis-generating only.")
    figure(doc, "soil_moisture/soil_L_logo_permutation_importance.png", "Figure D5. Leave-one-group-out permutation importance for exploratory plot summaries.")
    figure(doc, "vpd/vpd_B_daily_range_faceted.png", "Figure D6. VPD daily-range comparison by monitored plot.")


def main():
    global table_count
    table_count = 0
    if not WORK_TEMPLATE.exists():
        raise FileNotFoundError(f"Convert the official template first: {WORK_TEMPLATE}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WORK_TEMPLATE, OUT)
    doc = Document(str(OUT))
    keep_cover_only(doc)
    set_doc_defaults(doc)
    add_cover_and_frontmatter(doc)
    chapter_one(doc)
    chapter_two(doc)
    chapter_three(doc)
    chapter_four(doc)
    chapter_five(doc)
    chapter_six(doc)
    chapter_seven(doc)
    references(doc)
    appendices(doc)
    doc.save(str(OUT))
    print(OUT)


if __name__ == "__main__":
    main()
