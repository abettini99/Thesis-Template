#!/usr/bin/env python3
"""
greyscale_preview.py: see the thesis as a black-and-white printer prints it.

    python3 tools/greyscale_preview.py              # main.pdf -> main-grey.pdf, plus a report
    python3 tools/greyscale_preview.py other.pdf

It reports:
  colour pages   which pages contain colour at all: printers charge per colour page, so this
                 is the number to quote (the digital edition has brick-red links on many pages;
                 compile a print edition to count)
  figures        colours in each figure PDF that become the same grey: lines or areas that
                 differ only in such colours cannot be told apart in print. Fine if they also
                 differ in line style or marker, as with the template's matplotlib style

and writes main-grey.pdf, every page in greyscale, to look through. Needs Python 3.8+, the
poppler tools (pdftoppm, pdfinfo) and Pillow; the figure check needs pikepdf
(pip install -r requirements.txt).
"""

from __future__ import annotations

import itertools
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import ROOT, operators, parser
from PIL import Image, ImageChops

CHROMA = 40  # max-min of R, G, B above which a pixel counts as coloured (0-255)
MIN_PIXELS = 12  # coloured pixels a page needs (ignores stray anti-aliasing)
SAME_GREY = 8.0  # CIE L* difference below which two colours look the same in grey


def lightness(rgb) -> float:
    """CIE L* (0 black .. 100 white) of an sRGB colour with components 0..1."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return 116 * y ** (1 / 3) - 16 if y > 216 / 24389 else y * 24389 / 27


def hexcol(rgb) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def figure_colours(path: Path):
    """The distinct colours (as RGB 0..1) a figure strokes or fills with, black/grey/white left out."""
    import pikepdf

    pdf = pikepdf.open(path)  # (kept: a page cannot outlive its document)
    page, cols = pdf.pages[0], set()
    for op, operands, _, _ in operators(page, page.get("/Resources")):
        vals = []
        for v in operands:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
        if op in ("rg", "RG") or (op in ("sc", "scn", "SC", "SCN") and len(vals) == 3):
            rgb = tuple(vals[:3])
        elif op in ("k", "K") and len(vals) == 4:
            c, m, y, k = vals
            rgb = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        else:
            continue
        if max(rgb) - min(rgb) > 0.06:  # a colour, not a grey
            cols.add(tuple(round(c, 3) for c in rgb))
    return sorted(cols)


def pages_in_order(folder: Path, prefix: str):
    return sorted(folder.glob(f"{prefix}-*.png"), key=lambda q: int(re.findall(r"\d+", q.stem)[-1]))


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("pdf", nargs="?", type=Path, default=ROOT / "main.pdf", help="default: main.pdf")
    ap.add_argument("--dpi", type=int, default=150, help="resolution of the greyscale preview (default 150)")
    args = ap.parse_args(argv)
    for tool in ("pdftoppm", "pdfinfo"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found: install poppler (see tools/check_pdf.py)")
    if not args.pdf.exists():
        sys.exit(f"{args.pdf} not found: compile first")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        subprocess.run(["pdftoppm", "-r", "40", "-png", str(args.pdf), str(tmp / "c")], check=True)
        colour, pages = [], pages_in_order(tmp, "c")
        for i, p in enumerate(pages, 1):
            r, g, b = Image.open(p).convert("RGB").split()
            chroma = ImageChops.subtract(
                ImageChops.lighter(ImageChops.lighter(r, g), b), ImageChops.darker(ImageChops.darker(r, g), b)
            )
            if chroma.point(lambda v: 255 if v > CHROMA else 0).histogram()[255] >= MIN_PIXELS:
                colour.append(i)
        pages = len(pages)
        print(f"{args.pdf.name}: {pages} pages, {len(colour)} with colour")
        if colour:
            print("  colour pages: " + ", ".join(map(str, colour)))
        print()

        out = args.pdf.with_name(args.pdf.stem + "-grey.pdf")
        subprocess.run(
            ["pdftoppm", "-r", str(args.dpi), "-gray", "-png", str(args.pdf), str(tmp / "g")], check=True
        )
        imgs = [Image.open(p).convert("L") for p in pages_in_order(tmp, "g")]
        imgs[0].save(out, save_all=True, append_images=imgs[1:], resolution=args.dpi)
        print(f"greyscale preview: {out.name}\n")

    figures = sorted((ROOT / "figures").glob("**/*.pdf")) if (ROOT / "figures").is_dir() else []
    import importlib.util

    if importlib.util.find_spec("pikepdf") is None:
        print("figure colours not checked: pip install -r requirements.txt")
        return 0
    alike_total = 0
    for fig in figures:
        try:
            cols = figure_colours(fig)
        except Exception as e:  # an unusual PDF: report, keep going
            print(f"  ?     {fig.relative_to(ROOT)}: could not read ({e.__class__.__name__})")
            continue
        pairs = [
            (a, b) for a, b in itertools.combinations(cols, 2) if abs(lightness(a) - lightness(b)) < SAME_GREY
        ]
        if pairs:
            alike_total += 1
            print(f"  NOTE  {fig.relative_to(ROOT)}: colours that print as the same grey:")
            for a, b in pairs:
                print(
                    f"          {hexcol(a)} and {hexcol(b)} (lightness {lightness(a):.0f} and {lightness(b):.0f})"
                )
        else:
            what = (
                f"{len(cols)} colour{'' if len(cols) == 1 else 's'}, distinct in grey"
                if cols
                else "no colour"
            )
            print(f"  OK    {fig.relative_to(ROOT)}: {what}")
    if alike_total:
        print(
            "\nFine if those lines or areas also differ in line style, marker or hatching "
            "(the template's matplotlib style gives every colour its own line style)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
