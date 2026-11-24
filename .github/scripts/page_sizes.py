"""Compare the four page sizes of the template in one image: .github/readme/page-sizes.png.

The template is compiled in each page size (preview edition: the trimmed page as printed),
the same page is taken from each, and the pages are set side by side at the same scale, with the
measured type size, leading, lines per page and line length underneath.

Run from the repository root:  python3 .github/scripts/page_sizes.py
Needs LuaLaTeX with latexmk and biber, pdftoppm and pdftotext (poppler), and Python with Pillow.
The GitHub workflow .github/workflows/readme-images.yml runs it after a day with pushes.
"""

import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".github" / "readme" / "page-sizes.png"
SIZES = [("demy", "Demy (default)"), ("a5", "A5"), ("royal", "Royal"), ("dutch", "Dutch")]
PAGE_TEXT = "Of the two unknowns"  # the page shown: the first text page of the sample chapter
PX_PER_MM = 4  # scale of the image
GAP_MM, MARGIN_MM = 14, 10
BACKGROUND, INK, GREY = (238, 238, 236), (30, 30, 30), (110, 110, 110)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def build(size, outdir):
    """Compile main.tex in this page size; return the PDF and the measured metrics."""
    src = (ROOT / "main.tex").read_text()
    src = re.sub(
        r"^\\documentclass\[[^\]]*\]\{thesis\}",
        rf"\\documentclass[edition=preview, version=final, size={size}]{{thesis}}",
        src,
        count=1,
        flags=re.M,
    )
    probe = (
        r"\typeout{THESIS-METRICS:\the\textwidth;\the\textheight;\csname f@size\endcsname;"
        r"\the\baselineskip;\csname thesis@fontscale\endcsname}"
    )
    src = src.replace(r"\begin{Spacing}{\thesisspacing}", r"\begin{Spacing}{\thesisspacing}" + probe, 1)
    job = f"_pagesizes_{size}"
    tex = ROOT / f"{job}.tex"
    tex.write_text(src)
    try:
        subprocess.run(
            [
                "latexmk",
                "-lualatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-outdir={outdir}",
                tex.name,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        log = Path(outdir, f"{job}.log")
        print(log.read_text(errors="replace")[-3000:] if log.exists() else e.stdout[-3000:])
        raise
    finally:
        tex.unlink()
    log = Path(outdir, f"{job}.log").read_text(errors="replace")
    m = re.search(r"THESIS-METRICS:([\d.]+)pt;([\d.]+)pt;([\d.]+);([\d.]+)pt;([\d.]+)", log)
    tw, th, fsize, lead, scale = (float(x) for x in m.groups())
    # the class sets fonts at their nominal size and scales them by \thesis@fontscale (1 for all sizes)
    return Path(outdir, f"{job}.pdf"), dict(textwidth=tw, textheight=th, size=fsize * scale, leading=lead)


def find_page(pdf):
    pages = run(["pdftotext", "-layout", str(pdf), "-"]).stdout.split("\f")
    hits = [i + 1 for i, p in enumerate(pages) if PAGE_TEXT in p]
    return hits[0] if hits else len(pages) // 2, pages


def chars_per_line(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    longest = max(len(l) for l in lines)
    body = [len(l) for l in lines if len(l) > 0.8 * longest]
    return round(statistics.median(body))


def font(bold, size):
    for name in (
        ["SourceSans3-Semibold.otf", "SourceSansPro-Semibold.otf"]
        if bold
        else ["SourceSans3-Regular.otf", "SourceSansPro-Regular.otf"]
    ):
        path = subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip()
        if path:
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def nice(x):
    """Point size as a typographer writes it: to the nearest half point."""
    return f"{round(2 * x) / 2:.1f}".rstrip("0").rstrip(".")


def save_if_changed(img):
    """Save the image, unless the file already shows the same pixels: PNG files written by another
    Pillow version differ in their bytes, and the workflow would otherwise commit an unchanged image."""
    if OUT.exists():
        old = Image.open(OUT).convert("RGB")
        if old.size == img.size and ImageChops.difference(old, img.convert("RGB")).getbbox() is None:
            print(f"{OUT.relative_to(ROOT)}: unchanged")
            return
    img.save(OUT, optimize=True)
    print(f"saved {OUT.relative_to(ROOT)} ({img.width} × {img.height} px)")


def main():
    MM = 72.27 / 25.4  # TeX points per mm
    panels = []
    with tempfile.TemporaryDirectory() as tmp:
        for size, label in SIZES:
            pdf, m = build(size, tmp)
            page, pages = find_page(pdf)
            dpi = PX_PER_MM * 25.4
            run(
                [
                    "pdftoppm",
                    "-r",
                    f"{dpi}",
                    "-png",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    str(pdf),
                    f"{tmp}/{size}",
                ]
            )
            img = Image.open(next(Path(tmp).glob(f"{size}-*.png"))).convert("RGB")
            w_mm, h_mm = img.width / PX_PER_MM, img.height / PX_PER_MM
            panels.append(
                dict(
                    img=img,
                    label=label,
                    option=size,
                    lines=[
                        f"{round(w_mm)} × {round(h_mm)} mm",
                        f"{nice(m['size'])} pt on "
                        + f"{round(m['leading'] * 4) / 4:.2f}".rstrip("0").rstrip(".")
                        + f" pt, {round(m['textheight'] / m['leading'])} lines",
                        f"text {round(m['textwidth'] / MM)} × {round(m['textheight'] / MM)} mm, "
                        f"≈ {chars_per_line(pages[page - 1])} characters per line",
                    ],
                )
            )
            print(f"{size}: page {page}, {panels[-1]['lines']}")

    px = PX_PER_MM
    f_title, f_text = font(True, 13 * px // 2), font(False, 11 * px // 2)
    caption_h = int(28 * px)
    width = int(2 * MARGIN_MM * px + sum(p["img"].width for p in panels) + GAP_MM * px * (len(panels) - 1))
    height = int(2 * MARGIN_MM * px + max(p["img"].height for p in panels) + caption_h)
    sheet = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    x, base = MARGIN_MM * px, MARGIN_MM * px + max(p["img"].height for p in panels)
    for p in panels:
        img = p["img"]
        y = base - img.height  # pages stand on one baseline
        draw.rectangle([x + 4, y + 4, x + img.width + 4, base + 4], fill=(205, 205, 202))  # shadow
        sheet.paste(img, (x, y))
        draw.rectangle([x, y, x + img.width - 1, base - 1], outline=(180, 180, 176))
        ty = base + 5 * px
        draw.text((x, ty), f"{p['label']}   ", font=f_title, fill=INK)
        tw = draw.textlength(f"{p['label']}   ", font=f_title)
        draw.text((x + tw, ty), p["option"], font=f_text, fill=GREY)
        for i, line in enumerate(p["lines"]):
            draw.text((x, ty + 9 * px + i * 6 * px), line, font=f_text, fill=GREY)
        x += img.width + GAP_MM * px
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 256 colours are plenty for grey pages, and keep the file (and the repository history) small
    save_if_changed(sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))


if __name__ == "__main__":
    sys.exit(main())
