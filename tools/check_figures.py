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
  contrast   lines and text in a PDF figure in colours too light to stand out against
             the white page (accessibility, WCAG 2.2: 3:1 for lines, 4.5:1 for text)

It also lists files in figures/ that the thesis does not use. Needs Python 3.8+;
the text sizes and fonts of PDF figures need pikepdf (pip install -r requirements.txt).
"""

from __future__ import annotations

import math
import re
import struct
import subprocess
import sys
from pathlib import Path

from common import (
    IDENTITY,
    ROOT,
    Report,
    font_name,
    glyph_count,
    mul,
    notdef_count,
    operators,
    parser,
    shown_bytes,
)

PT_PER_MM = 72.27 / 25.4
TIMES = re.compile(
    r"Times|Termes|NimbusRom|Nimbus Roman|STIX|NewTX|ntx|tx(mia|sys|exa|sy|ex)|Tinos|Liberation ?Serif|"
    r"MT2|MTPro|TeXGyreTermes|Symbol",
    re.I,
)
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
    while i < len(lines):  # TeX wraps log lines at 79 characters
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
        sys.exit(f"{log.name} has no figure log: compile with the template's class (thesis.cls) first")
    textwidth, caption, scale = (float(x) for x in m.groups())
    figs = []
    for l in joined:
        f = re.match(
            r"Thesis figure: (.+?) \| ([\d.]+)pt x ([\d.]+)pt \| ([\d.]+)pt x ([\d.]+)pt \| page (\S+)", l
        )
        if f:
            name, nw, nh, pw, ph, page = f.groups()
            figs.append((name.strip(), float(nw), float(nh), float(pw), float(ph), page))
    return textwidth, caption * scale, figs


# --- inside a PDF figure ---------------------------------------------------------


def text_sizes(path: Path):
    """Font size of every glyph on page 1 (in the figure's own points), the font names, and the
    number of missing glyphs (.notdef)."""
    pdf = pikepdf.open(path)  # (kept: a page cannot outlive its document)
    page = pdf.pages[0]
    sizes, fonts, missing = [], set(), 0
    tm = tlm = IDENTITY
    size, font = 0, None
    for op, operands, res, ctm in operators(page, page.get("/Resources")):
        if op == "BT":
            tm = tlm = IDENTITY
        elif op == "Tf":
            size = float(operands[1])
            font = (res.get("/Font", {}) if res is not None else {}).get(str(operands[0]))
            if font is not None:
                fonts.add(font_name(font))
        elif op == "Tm":
            tm = tlm = [float(x) for x in operands]
        elif op in ("Td", "TD"):
            tm = tlm = mul([1, 0, 0, 1, float(operands[0]), float(operands[1])], tlm)
        elif (data := shown_bytes(op, operands)) is not None and size:
            m = mul(tm, ctm)
            # one entry per glyph, so "most of the text" counts characters, not text pieces
            # (TeX sets an exponent as a piece of its own)
            sizes += [abs(size) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))] * max(1, glyph_count(font, data))
            missing += notdef_count(font, data)
    if sizes and not visible_text(path):
        sizes, fonts = [], set()  # only invisible glyphs (matplotlib's PGF output has one)
    return sizes, fonts, missing


def _luminance(rgb) -> float:
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(rgb) -> float:
    """Contrast against a white page (WCAG 2.2): 1 to 21."""
    return 1.05 / (_luminance(rgb) + 0.05)


def low_contrast(path: Path):
    """Colours of lines and text in the figure that do not stand out enough against white (WCAG 2.2: 3:1
    for lines and other graphics a reader needs, 4.5:1 for text). Not reported: white (drawn on something
    dark, such as a colour map), thin light grey lines (grid lines: decoration) and filled areas."""
    pdf = pikepdf.open(path)
    page = pdf.pages[0]
    fill = stroke = (0.0, 0.0, 0.0)
    width = 1.0
    stack, found = [], {}

    def colour(nums):
        if len(nums) == 1:
            return (nums[0],) * 3
        if len(nums) == 3:
            return tuple(nums)
        if len(nums) == 4:  # CMYK, roughly
            c, m, y, k = nums
            return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        return None

    for op, operands, _res, ctm in operators(page, page.get("/Resources")):
        nums = []
        for x in operands:
            try:
                nums.append(float(x))
            except (TypeError, ValueError):
                pass
        if op == "q":
            stack.append((fill, stroke, width))
        elif op == "Q" and stack:
            fill, stroke, width = stack.pop()
        elif op == "w" and nums:
            width = nums[0] * math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
        elif op in ("rg", "g", "k", "sc", "scn") and colour(nums):
            fill = colour(nums)
        elif op in ("RG", "G", "K", "SC", "SCN") and colour(nums):
            stroke = colour(nums)
        elif op in ("S", "s", "B", "B*", "b", "b*"):
            grey = max(stroke) - min(stroke) < 0.02
            if not (grey and min(stroke) > 0.7 and width < 0.6):  # grid lines
                found.setdefault(("lines", stroke), contrast(stroke))
        elif op in ("Tj", "TJ", "'", '"'):
            found.setdefault(("text", fill), contrast(fill))
    out = []
    for (kind, rgb), cr in sorted(found.items(), key=lambda kv: kv[1]):
        need = 4.5 if kind == "text" else 3.0
        if 1.15 < cr < need:
            hexa = "#" + "".join(f"{round(c * 255):02X}" for c in rgb)
            out.append(
                f"{kind} in {hexa}: contrast {cr:.1f}:1 against white ({need:g}:1 needed to stand out); "
                "use a darker colour (the plot style's colours all pass)"
            )
    return out


def visible_text(path: Path) -> bool:
    """Whether the figure has any text a reader sees (pdftotext, from poppler; True without it)."""
    try:
        out = subprocess.run(["pdftotext", "-l", "1", str(path), "-"], capture_output=True, text=True).stdout
    except OSError:
        return True
    return bool(out.strip())


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
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return w, h
            i += 2 + length
    return None


# --- report ----------------------------------------------------------------------


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("log", nargs="?", type=Path, default=ROOT / "main.log", help="default: main.log")
    args = ap.parse_args(argv)
    if not args.log.exists():
        sys.exit(f"{args.log} not found: compile first (on Overleaf, download the log)")
    textwidth, caption, figs = read_log(args.log)
    print(f"Text width {mm(textwidth)}, caption text {caption:.1f} pt; {len(figs)} figure inclusions\n")
    r, seen_files = Report(), set()
    for name, nw, _nh, pw, _ph, page in figs:
        path = (ROOT / name) if (ROOT / name).exists() else Path(name)
        seen_files.add(path.resolve())
        if name.startswith("template/"):
            continue  # logos are sized on purpose
        notes, scale = [], pw / nw if nw else 1
        suffix = path.suffix.lower()
        scaled = abs(scale - 1) > SCALE_TOL and suffix not in (".png", ".jpg", ".jpeg")
        if pw > textwidth + 1:
            notes.append(f"{mm(pw)} wide, wider than the text ({mm(textwidth)}): it sticks into the margin")
        if suffix == ".pdf" and path.exists():
            if pikepdf is None:
                notes_text = "text sizes not checked (pip install -r requirements.txt)"
            else:
                try:
                    sizes, fonts, nmissing = text_sizes(path)
                except Exception as e:  # an unusual PDF: report, keep going
                    sizes, fonts, nmissing = [], set(), 0
                    notes.append(f"could not read the PDF ({e.__class__.__name__})")
                printed = [s * scale for s in sizes]
                if scaled and sizes:  # (a picture without text may be scaled)
                    notes.append(
                        f"printed at {scale:.0%} of its size: the text in it is scaled too. Make it "
                        f"{mm(min(pw, textwidth))} wide and include it without width=/scale="
                    )
                if printed:
                    lo, hi = min(printed), max(printed)
                    notes_text = f"text {lo:.1f}" + (f"-{hi:.1f}" if hi - lo > 0.05 else "") + " pt"
                    rounded = [round(p, 1) for p in printed]
                    main_size = max(set(rounded), key=rounded.count)  # most of the text
                    if main_size < MIN_MAIN:
                        notes.append(
                            f"most text is {main_size:.1f} pt in print: small (aim for about {caption:.1f} pt)"
                        )
                    if lo < MIN_ANY:
                        notes.append(f"some text is only {lo:.1f} pt in print: hard to read")
                    if hi > caption + 1:
                        notes.append(f"text up to {hi:.1f} pt, larger than the captions ({caption:.1f} pt)")
                else:
                    notes_text = "no text (or text as outlines)"
                if nmissing:
                    notes.append(
                        f"{nmissing} missing glyph(s) (.notdef): they print as nothing and fail the PDF/A "
                        "check. From matplotlib 3.11+ this is usually a ligature (ff, fi, fl): switch "
                        "them off as figures/plots/example_figures.py does, and export again"
                    )
                try:
                    notes += low_contrast(path)
                except Exception:
                    pass
                other = sorted(f for f in fonts if f and not TIMES.search(f))
                if other:
                    notes.append(f"fonts other than Times: {', '.join(other)} (the thesis uses Times)")
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
        r.warn(head, notes) if notes else r.ok(head)
    images = ROOT / "figures"
    if images.is_dir():
        unused = sorted(
            p.relative_to(ROOT)
            for p in images.rglob("*")
            if p.is_file()
            and p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg")
            and p.resolve() not in seen_files
            and "_cover" not in str(p)
        )
        if unused:
            print(f"\nNot used in this build ({len(unused)}): " + ", ".join(str(u) for u in unused))
    print(f"\n{r.warnings} figure(s) to look at.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
