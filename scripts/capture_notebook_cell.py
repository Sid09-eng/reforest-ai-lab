"""Capture a real Jupyter notebook cell screenshot using Playwright.

Opens the .ipynb file in a local browser rendering and screenshots
the specified cell range to create authentic-looking notebook captures.
"""
import json
import html
from pathlib import Path
from playwright.sync_api import sync_playwright


NOTEBOOK = Path("/Users/siddharthchoudhary09/Desktop/fyp_project/notebooks/clean_microclimate.ipynb")
OUT_DIR = Path("/Users/siddharthchoudhary09/Desktop/fyp_project/docs/assets")


def render_cell_html(nb_path: Path, cell_indices: list[int], title: str = "") -> str:
    """Build a minimal HTML page that looks like a Jupyter notebook cell."""
    with open(nb_path) as f:
        nb = json.load(f)

    cells_html = []
    for idx in cell_indices:
        cell = nb["cells"][idx]
        cell_type = cell["cell_type"]
        source = "".join(cell.get("source", []))

        if cell_type == "code":
            # Get execution count
            exec_count = cell.get("execution_count", "")
            exec_label = f"In&nbsp;[{exec_count}]:" if exec_count else "In&nbsp;[&nbsp;]:"

            # Code input
            code_html = html.escape(source)

            # Outputs
            output_html = ""
            for out in cell.get("outputs", []):
                if "text" in out:
                    output_html += html.escape("".join(out["text"]))
                elif "data" in out:
                    if "text/plain" in out["data"]:
                        output_html += html.escape("".join(out["data"]["text/plain"]))

            out_label = f"Out[{exec_count}]:" if exec_count and output_html.strip() else ""

            cells_html.append(f"""
            <div class="cell code-cell">
                <div class="cell-row">
                    <div class="prompt input-prompt">{exec_label}</div>
                    <div class="input-area"><pre><code>{code_html}</code></pre></div>
                </div>
                {"" if not output_html.strip() else f'''
                <div class="cell-row output-row">
                    <div class="prompt output-prompt">{out_label}</div>
                    <div class="output-area"><pre>{output_html}</pre></div>
                </div>
                '''}
            </div>
            """)
        elif cell_type == "markdown":
            cells_html.append(f"""
            <div class="cell markdown-cell">
                <div class="cell-row">
                    <div class="prompt"></div>
                    <div class="markdown-area">{source}</div>
                </div>
            </div>
            """)

    page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        background: #ffffff;
        padding: 20px 24px;
        max-width: 960px;
    }}
    .cell {{
        margin-bottom: 12px;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        overflow: hidden;
    }}
    .cell-row {{
        display: flex;
        align-items: flex-start;
    }}
    .prompt {{
        min-width: 90px;
        max-width: 90px;
        padding: 10px 8px 10px 10px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 12px;
        text-align: right;
        color: #6a737d;
        flex-shrink: 0;
        user-select: none;
    }}
    .input-prompt {{
        color: #0366d6;
        font-weight: 600;
    }}
    .output-prompt {{
        color: #d73a49;
        font-weight: 600;
    }}
    .input-area {{
        flex: 1;
        background: #f6f8fa;
        padding: 10px 14px;
        border-left: 1px solid #e1e4e8;
    }}
    .input-area pre {{
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    .input-area code {{
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 13px;
        line-height: 1.55;
        color: #24292e;
    }}
    .output-area {{
        flex: 1;
        padding: 10px 14px;
        border-left: 1px solid #e1e4e8;
        border-top: 1px solid #e1e4e8;
        background: #ffffff;
    }}
    .output-area pre {{
        margin: 0;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 13px;
        line-height: 1.55;
        color: #24292e;
        white-space: pre-wrap;
    }}
    .markdown-area {{
        flex: 1;
        padding: 12px 16px;
        font-size: 14px;
        line-height: 1.6;
        color: #24292e;
    }}
    .markdown-area h3 {{
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 6px;
    }}
</style>
</head>
<body>
{"".join(cells_html)}
</body>
</html>"""
    return page_html


def capture(cell_indices: list[int], output_name: str, title: str = "", width: int = 960):
    """Render cells and screenshot them."""
    html_content = render_cell_html(NOTEBOOK, cell_indices, title)

    tmp_html = Path("/tmp") / f"nb_capture_{output_name}.html"
    tmp_html.write_text(html_content)

    out_path = OUT_DIR / output_name
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.goto(f"file://{tmp_html}")
        page.wait_for_timeout(500)

        # Get the actual content height
        body = page.query_selector("body")
        bbox = body.bounding_box()

        page.screenshot(
            path=str(out_path),
            clip={"x": 0, "y": 0, "width": width, "height": bbox["height"] + 40},
        )
        browser.close()

    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    # Figure 3: EDA cleaning summary cell (cell 24 has the cleaning audit output)
    capture([24, 25], "notebook_cleaning_summary_cell.png", width=900)
    print("Done!")
