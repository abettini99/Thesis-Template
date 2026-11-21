#!/usr/bin/env python3
"""
check_figures.py: check that the figures fit the thesis typography.

    python3 tools/check_figures.py              # reads main.log (compile first)
    python3 tools/check_figures.py other.log

The class writes every included graphic to the log with its own size and the size it
is printed at. For each figure this reports:

  scale      whether it is printed at its own size. A figure made at the printed
             width (the template's style file does that) keeps its text at the size
             it was made with; scaling it with width=... shrinks or grows the text.
  width      whether it fits the text width, or sticks into the margin
  text size  the printed size of the text inside a PDF figure: most of it should be
             about the caption size (README, Plots); below 6.5 pt is small, anything
             below 5 pt (exponents included) hard to read, above the captions heavy
  fonts      fonts that differ from the text's Times (e.g. a plotting tool's default
             DejaVu Sans or Arial)
  resolution printed resolution of PNG and JPEG figures (300 ppi or more for print)

It also lists files in Images/ that the thesis does not use. Needs Python 3.8+;
the text sizes and fonts of PDF figures need pikepdf (pip install -r requirements.txt).
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PT_PER_MM = 72.27 / 25.4
TIMES = re.compile(r"Times|Termes|NimbusRom|Nimbus Roman|STIX|NewTX|ntx|Tinos|Liberation ?Serif|"
                   r"MT2|MTPro|TeXGyreTermes|Symbol", re.I)
MIN_MAIN, MIN_ANY, SCALE_TOL, PRINT_PPI = 6.5, 5.0, 0.03, 300

try:
    import pikepdf
except ImportError:
    pikepdf = None


def mm(pt: float) -> str:
    return f"{pt / PT_PER_MM:.1f} mm"


# --- the log -------------------------------------------------------------------

def read_log(log: Path):
    lines = log.read_text(errors="replace").splitlines()
    joined, i = [], 0
    while i < len(lines):                                  # TeX wraps log lines at 79 characters
        line = lines[i]
        if line.startswith(("Thesis figure:", "Thesis layout:")):
            while not re.search(r"\| page \S+$|fontscale [\d.]+$", line) and i + 1 < len(lines):
                i += 1
                line += lines[i]
        joined.append(line)
        i += 1
    layout = next((l for l in joined if l.startswith("Thesis layout:")), "")
    m = re.search(r"textwidth ([\d.]+)pt \| captionsize ([\d.]+) ?pt \| fontscale ([\d.]+)", layout)
    if not m:
        sys.exit(f"{log.name} has no figure log: compile with the template's class (personal.cls) first")
    textwidth, caption, scale = (float(x) for x in m.groups())
    figs = []
    for l in joined:
        f = re.match(r"Thesis figure: (.+?) \| ([\d.]+)pt x ([\d.]+)pt \| ([\d.]+)pt x ([\d.]+)pt \| page (\S+)", l)
        if f:
            name, nw, nh, pw, ph, page = f.groups()
            figs.append((name.strip(), float(nw), float(nh), float(pw), float(ph), page))
    return textwidth, caption * scale, figs


# --- inside a PDF figure ---------------------------------------------------------

def mul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def text_sizes(path: Path):
    """Font sizes (in the figure's own points) of all text, the font names, and the number of
    missing glyphs (.notdef) of page 1."""
    pdf = pikepdf.open(path)
    page = pdf.pages[0]
    sizes, fonts, missing = [], set(), [0]

    def walk(stream, resources, ctm, depth=0):
        if depth > 8:
            return
        stack, tm, tlm, size, font = [], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0], 0, None
        for operands, op in pikepdf.parse_content_stream(stream):
            op = str(op)
            if op == "q":
                stack.append(ctm)
            elif op == "Q" and stack:
                ctm = stack.pop()
            elif op == "cm":
                ctm = mul([float(x) for x in operands], ctm)
            elif op == "BT":
                tm = tlm = [1, 0, 0, 1, 0, 0]
            elif op == "Tf":
                size = float(operands[1])
                font = resources.get("/Font", {}).get(str(operands[0])) if resources else None
                if font is not None:
                    fonts.add(str(font.get("/BaseFont", "")).lstrip("/").split("+")[-1])
            elif op == "Tm":
                tm = tlm = [float(x) for x in operands]
            elif op in ("Td", "TD"):
                tlm = mul([1, 0, 0, 1, float(operands[0]), float(operands[1])], tlm)
                tm = tlm
            elif op in ("Tj", "TJ", "'", '"') and size:
                m = mul(tm, ctm)
                sizes.append(abs(size) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2])))
                if font is not None and font.get("/Subtype") == "/Type0":
                    items = operands[0] if op == "TJ" else [operands[-1]]
                    data = b"".join(bytes(x) for x in items if isinstance(x, pikepdf.String))
                    missing[0] += sum(1 for i in range(0, len(data) - 1, 2) if data[i:i + 2] == b"\0\0")
            elif op == "Do" and resources is not None:
                xo = resources.get("/XObject", {}).get(str(operands[0]))
                if xo is not None and xo.get("/Subtype") == "/Form":
                    m = [float(x) for x in xo.get("/Matrix", [1, 0, 0, 1, 0, 0])]
                    walk(xo, xo.get("/Resources", resources), mul(m, ctm), depth + 1)

    walk(page, page.get("/Resources"), [1, 0, 0, 1, 0, 0])
    return sizes, fonts, missing[0]


def raster_pixels(path: Path):
    data = path.read_bytes()[:65536]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


# --- report ----------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="?", type=Path, default=ROOT / "main.log", help="default: main.log")
    args = ap.parse_args(argv)
    if not args.log.exists():
        sys.exit(f"{args.log} not found: compile first (on Overleaf, download the log)")
    textwidth, caption, figs = read_log(args.log)
    print(f"Text width {mm(textwidth)}, caption text {caption:.1f} pt; {len(figs)} figure inclusions\n")
    problems, seen_files = 0, set()
    for name, nw, nh, pw, ph, page in figs:
        path = (ROOT / name) if (ROOT / name).exists() else Path(name)
        seen_files.add(path.resolve())
        if "_title_images" in name:
            continue                                     # logos are sized on purpose
        notes, scale = [], pw / nw if nw else 1
        suffix = path.suffix.lower()
        if abs(scale - 1) > SCALE_TOL and suffix not in (".png", ".jpg", ".jpeg"):
            notes.append(f"printed at {scale:.0%} of its size: the text in it is scaled too. Make it "
                         f"{mm(min(pw, textwidth))} wide and include it without width=/scale=")
        if pw > textwidth + 1:
            notes.append(f"{mm(pw)} wide, wider than the text ({mm(textwidth)}): it sticks into the margin")
        if suffix == ".pdf" and path.exists():
            if pikepdf is None:
                notes_text = "text sizes not checked (pip install -r requirements.txt)"
            else:
                try:
                    sizes, fonts, nmissing = text_sizes(path)
                except Exception as e:                  # an unusual PDF: report, keep going
                    sizes, fonts, nmissing = [], set(), 0
                    notes.append(f"could not read the PDF ({e.__class__.__name__})")
                printed = [s * scale for s in sizes]
                if printed:
                    lo, hi = min(printed), max(printed)
                    notes_text = f"text {lo:.1f}" + (f"-{hi:.1f}" if hi - lo > 0.05 else "") + " pt"
                    rounded = [round(p, 1) for p in printed]
                    main_size = max(set(rounded), key=rounded.count)      # most of the text
                    if main_size < MIN_MAIN:
                        notes.append(f"most text is {main_size:.1f} pt in print: small (aim for about {caption:.1f} pt)")
                    if lo < MIN_ANY:
                        notes.append(f"some text is only {lo:.1f} pt in print: hard to read")
                    if hi > caption + 1:
                        notes.append(f"text up to {hi:.1f} pt, larger than the captions ({caption:.1f} pt)")
                else:
                    notes_text = "no text (or text as outlines)"
                if nmissing:
                    notes.append(f"{nmissing} missing glyph(s) (.notdef): they print as nothing and fail the PDF/A "
                                 "check. From matplotlib 3.11+ this is usually a ligature (ff, fi, fl): switch "
                                 "them off as Python/example_figures.py does, and export again")
                other = sorted(f for f in fonts if f and not TIMES.search(f))
                if other:
                    notes.append(f"fonts other than Times: {', '.join(other)} (the template's style file uses Times)")
        elif suffix in (".png", ".jpg", ".jpeg") and path.exists():
            px = raster_pixels(path)
            if px:
                ppi = px[0] / (pw / 72.27)
                notes_text = f"{px[0]}x{px[1]} px, {ppi:.0f} ppi printed"
                if ppi < PRINT_PPI:
                    notes.append(f"{ppi:.0f} ppi at its printed size: soft in print (300 ppi or more)")
            else:
                notes_text = ""
        else:
            notes_text = ""
        head = f"{name} (page {page}): {mm(pw)} wide" + (f", {notes_text}" if notes_text else "")
        if notes:
            problems += 1
            print(f"  WARN  {head}")
            for n in notes:
                print(f"          {n}")
        else:
            print(f"  OK    {head}")
    images = ROOT / "Images"
    if images.is_dir():
        unused = sorted(p.relative_to(ROOT) for p in images.rglob("*")
                        if p.is_file() and p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg")
                        and p.resolve() not in seen_files and "_title_images" not in p.parts
                        and "_cover" not in str(p))
        if unused:
            print(f"\nNot used in this build ({len(unused)}): " + ", ".join(str(u) for u in unused))
    print(f"\n{problems} figure(s) to look at.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
