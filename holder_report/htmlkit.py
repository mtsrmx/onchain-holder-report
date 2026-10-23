"""Helpers to build the report HTML and print it to PDF."""
import csv
import glob
import html
import re
from pathlib import Path

from .config import DATA, REPORT


def esc(s):
    return html.escape(str(s), quote=True)


def n(x, digits=0):
    """Format a number with thousands separators; negatives use a plain hyphen."""
    if x in ("", None):
        return ""
    v = float(x)
    s = f"{abs(v):,.{digits}f}"
    return ("-" if v < 0 else "") + s


def signed(x, digits=0):
    v = float(x)
    if round(v, digits) == 0:
        return "0"
    return ("+" if v > 0 else "-") + f"{abs(v):,.{digits}f}"


def svg_inline(name):
    """Inline a chart SVG so it uses the page fonts and stays sharp in the PDF."""
    t = (REPORT / "charts" / f"{name}.svg").read_text()
    t = re.sub(r"<\?xml[^>]*>", "", t)
    t = re.sub(r"<!DOCTYPE[^>]*>", "", t)
    t = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"\sheight="[^"]*"', r"\1", t, count=1)
    return t


def figure(no, name, alt):
    return (f'<div class="card" role="img" aria-label="{esc(alt)}"><div class="figno">FIGURE {no}</div>'
            f'{svg_inline(name)}<a class="screen-only fullsize" href="charts/{name}.png">Open full size</a></div>')


def table(header, rows, numeric_cols=(), total_last=False, cls=""):
    th = "".join(f'<th class="{"n" if i in numeric_cols else ""}">{esc(h)}</th>' for i, h in enumerate(header))
    body = []
    for j, r in enumerate(rows):
        tr_cls = ' class="total"' if total_last and j == len(rows) - 1 else ""
        tds = "".join(f'<td class="{"n" if i in numeric_cols else ""}">{c}</td>' for i, c in enumerate(r))
        body.append(f"<tr{tr_cls}>{tds}</tr>")
    return (f'<div class="tablewrap"><table class="{cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def read_csv(name):
    with open(DATA / name) as f:
        return list(csv.reader(f))


def chromium():
    hits = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    return hits[0] if hits else None


def print_pdf(html_path: Path, pdf_path: Path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        exe = chromium()
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page()
        pg.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(pdf_path), print_background=True, prefer_css_page_size=True)
        b.close()
