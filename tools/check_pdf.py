#!/usr/bin/env python3
"""
check_pdf.py: check the compiled thesis before you hand it in or send it to the printer.

    python3 tools/check_pdf.py              # checks main.pdf and main.log
    python3 tools/check_pdf.py other.pdf    # another PDF (and its .log, if there is one)

It reports what a print shop or the TU Delft repository may reject. For the print-preparation
edition (PDF/X, for the printer) it runs tools/check_print.py instead of the archival checks.

  archival PDF  PDF/A-4f, with veraPDF (https://verapdf.org) when it is installed and
                the template's own basic checks otherwise; with veraPDF also PDF/UA-2 and
                WTPDF 1.0 Accessibility and Reuse (accessibility) when the PDF declares them
                (the final version, which is tagged)
  fonts         every font embedded, no bitmap (Type 3) fonts, every font mapped to
                Unicode (so text can be searched and copied); figure files with
                fonts that are not embedded are named
  images        resolution of raster images at their printed size (300 ppi or more
                for print), and CMYK images (they break PDF/A)
  contrast      coloured text too light to stand out against the white page
                (accessibility, WCAG 2.2: 4.5:1); lines and text inside figures are
                checked by tools/check_figures.py
  LaTeX log     errors, undefined references and citations, missing characters,
                overfull boxes, and whether a rerun is needed

The exit code is 1 if anything must be fixed, 0 otherwise. Needs Python 3.8+ and
the poppler tools pdfinfo, pdffonts and pdfimages (part of TeX Live on Windows;
"brew install poppler" on macOS; "poppler-utils" on Linux).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from common import ROOT, Report, font_name, notdef_count, operators, parser, run, shown_bytes

PRINT_PPI, MIN_PPI = 300, 150


def table(text: str, skip: int = 2) -> list[list[str]]:
    return [line.split() for line in text.splitlines()[skip:] if line.strip()]


# --- archival PDF -------------------------------------------------------------

PDFA = ("4", "F")  # the standard the class produces: PDF/A-4f
PDFA_NAME = f"PDF/A-{PDFA[0]}{PDFA[1].lower()}"


def check_pdfa(pdf: Path, r: Report) -> None:
    r.section(f"Archival and accessible PDF ({PDFA_NAME}, PDF/UA-2, WTPDF 1.0)")
    verapdf = shutil.which("verapdf")
    if verapdf:  # veraPDF checks every standard the PDF declares, one line each
        out = run(verapdf, "--format", "text", "--verbose", str(pdf))
        verdicts = dict(
            (m.group(2).lower(), m.group(1)) for m in re.finditer(r"^(PASS|FAIL) .* (\w+)\s*$", out, re.M)
        )
        rules = [l.strip() for l in out.splitlines() if l.strip() and not re.match(r"(PASS|FAIL) ", l)][
            :40
        ] or out.strip().splitlines()[-5:]
        named = {
            "4f": PDFA_NAME,
            "ua2": "PDF/UA-2 (accessible: tagged, for screen readers)",
            "wt1a": "WTPDF 1.0 Accessibility (well-tagged, for assistive technology)",
            "wt1r": "WTPDF 1.0 Reuse (well-tagged, for reusing the content)",
        }
        for flavour, name in named.items():
            if flavour not in verdicts and flavour != "4f":
                continue  # (PDF/UA and WTPDF only when the final version is tagged)
            if verdicts.get(flavour) == "PASS":
                r.ok(f"veraPDF: {name} compliant")
            else:
                r.fail(f"veraPDF: not {name} compliant", rules)
        return
    xmp = run("pdfinfo", "-meta", str(pdf))
    part = re.search(r"pdfaid:part(?:>|=\")(\d)", xmp)
    conf = re.search(r"pdfaid:conformance(?:>|=\")([A-Za-z])", xmp)
    if part and conf and (part.group(1), conf.group(1).upper()) == PDFA:
        r.ok(f"declares {PDFA_NAME}")
    else:
        r.fail(f"does not declare {PDFA_NAME} (the class sets this up: check that the build finished)")
    try:  # (objects may sit in compressed streams: read them with pikepdf)
        import pikepdf

        doc = pikepdf.open(pdf)
        intents = [str(oi.get("/S")) for oi in doc.Root.get("/OutputIntents", [])]
        encrypted, javascript = doc.is_encrypted, "/JavaScript" in doc.Root.get("/Names", {})
    except ImportError:
        data = pdf.read_bytes()
        intents = ["/GTS_PDFA1"] if b"/GTS_PDFA1" in data else []
        encrypted, javascript = b"/Encrypt" in data, b"/JavaScript" in data
    if "/GTS_PDFA1" in intents:
        r.ok("colour profile (output intent) present")
    else:
        r.fail("no PDF/A output intent (colour profile)")
    if encrypted:
        r.fail("the PDF is encrypted; PDF/A does not allow that")
    if javascript:
        r.fail("the PDF contains JavaScript; PDF/A does not allow that")
    print("        (basic checks only: install veraPDF for a full validation)")


# --- fonts -------------------------------------------------------------------


def check_fonts(pdf: Path, r: Report) -> None:
    r.section("Fonts")
    rows = [row for row in table(run("pdffonts", str(pdf))) if len(row) >= 7]
    # columns from the right: emb sub uni object-number generation
    notemb = [row[0] for row in rows if row[-5] != "yes"]
    nouni = [row[0] for row in rows if row[-3] != "yes"]
    type3 = [row[0] for row in rows if "Type 3" in " ".join(row)]
    r.ok(f"{len(rows)} fonts") if rows else r.fail("no fonts found (is this the right PDF?)")
    if notemb:
        r.fail("fonts not embedded (printers and PDF/A need every font embedded)", sorted(set(notemb)))
    else:
        r.ok("all fonts embedded")
    if type3:
        r.warn(
            "Type 3 fonts, usually from a figure: some are bitmaps (blurry in print) and some printers "
            "refuse them. In matplotlib use the template's style file (pdf.fonttype 42)",
            sorted(set(type3)),
        )
    if nouni:
        r.fail(
            "fonts without a Unicode map: text in them cannot be searched or copied (PDF/A)",
            sorted(set(nouni)),
        )
    else:
        r.ok("all fonts map to Unicode")
    try:
        hits = missing_glyphs(pdf)
    except ImportError:
        print("        (missing glyphs not checked: pip install -r requirements.txt)")
    else:
        if hits:
            r.fail(
                "missing glyphs (.notdef): they print as nothing and PDF/A forbids them. In a figure from "
                "matplotlib 3.11+ this is usually a ligature (ff, fi, fl); tools/check_figures.py names the file",
                [f"page {p}: {', '.join(sorted(f))}" for p, f in sorted(hits.items())],
            )
        else:
            r.ok("no missing glyphs")
    figures = sorted((ROOT / "figures").rglob("*.pdf")) if (ROOT / "figures").is_dir() else []
    bad = []
    for fig in figures:
        frows = [row for row in table(run("pdffonts", str(fig))) if len(row) >= 7]
        missing = sorted({row[0] for row in frows if row[-5] != "yes"})
        t3 = sorted({row[0] for row in frows if "Type 3" in " ".join(row)})
        if missing or t3:
            what = ", ".join(
                ([f"not embedded: {', '.join(missing)}"] if missing else [])
                + ([f"Type 3: {', '.join(t3)}"] if t3 else [])
            )
            bad.append(f"{fig.relative_to(ROOT)}  ({what})")
    if bad:
        r.warn("figure files with problem fonts (fix them at the source and export again)", bad)
    elif figures:
        r.ok(f"fonts in the {len(figures)} figure PDFs in figures/ are embedded")


def missing_glyphs(pdf: Path):
    """{page: font names} of the pages that show the .notdef (missing) glyph; needs pikepdf."""
    import pikepdf

    hits, doc = {}, pikepdf.open(pdf)
    for n, page in enumerate(doc.pages, 1):
        font = None
        for op, operands, res, _ in operators(page, page.get("/Resources")):
            if op == "Tf":
                font = (res.get("/Font", {}) if res is not None else {}).get(str(operands[0]))
            elif (data := shown_bytes(op, operands)) is not None and notdef_count(font, data):
                hits.setdefault(n, set()).add(font_name(font))
    return hits


# --- colour contrast ---------------------------------------------------------


def text_colours(pdf: Path):
    """{(r, g, b): set of pages} of the colours text is set in (outside the figures); needs pikepdf."""
    import pikepdf

    found, doc = {}, pikepdf.open(pdf)
    for n, page in enumerate(doc.pages, 1):
        fill, stack = (0.0, 0.0, 0.0), []
        for op, operands, _res, _ in operators(page, page.get("/Resources")):
            nums = []
            for x in operands:
                try:
                    nums.append(float(x))
                except (TypeError, ValueError):
                    pass
            if op == "q":
                stack.append(fill)
            elif op == "Q" and stack:
                fill = stack.pop()
            elif op in ("rg", "sc", "scn") and len(nums) == 3:
                fill = tuple(nums)
            elif op in ("g", "sc", "scn") and len(nums) == 1:
                fill = (nums[0],) * 3
            elif op in ("k", "sc", "scn") and len(nums) == 4:
                c, m, y, k = nums
                fill = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
            elif op in ("Tj", "TJ", "'", '"'):
                found.setdefault(tuple(round(v, 3) for v in fill), set()).add(n)
    return found


def check_contrast(pdf: Path, r: Report) -> None:
    """Coloured text that does not stand out enough against the white page (WCAG 2.2: 4.5:1)."""
    r.section("Colour contrast (accessibility)")
    try:
        found = text_colours(pdf)
    except ImportError:
        print("        (not checked: pip install -r requirements.txt)")
        return

    def contrast(rgb):
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 1.05 / (0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] + 0.05)

    low = []
    for rgb, pages in sorted(found.items(), key=lambda kv: contrast(kv[0])):
        cr = contrast(rgb)
        if 1.15 < cr < 4.5:  # (white text sits on something dark: not judged here)
            hexa = "#" + "".join(f"{round(c * 255):02X}" for c in rgb)
            where = ", ".join(str(p) for p in sorted(pages)[:10]) + (" ..." if len(pages) > 10 else "")
            low.append(f"{hexa}: {cr:.1f}:1, on page{'s' if len(pages) > 1 else ''} {where}")
    if low:
        r.warn(
            "text in colours too light against white (4.5:1 needed; lines and text in figures: "
            "tools/check_figures.py)",
            low,
        )
    else:
        r.ok(f"all text colours stand out against white ({len(found)} colours)")


# --- images ------------------------------------------------------------------


def check_images(pdf: Path, r: Report) -> None:
    r.section("Raster images")
    out = run("pdfimages", "-list", str(pdf))
    rows = [row for row in table(out) if len(row) >= 14 and row[2] == "image"]
    if not rows:
        r.ok("no raster images (vector figures only)")
        return
    low, very_low, cmyk, seen = [], [], [], set()
    for row in rows:
        page, obj, color = row[0], row[10], row[5]
        if obj in seen:
            continue
        seen.add(obj)
        try:
            ppi = min(float(row[12]), float(row[13]))
        except ValueError:
            continue
        where = f"page {page}: {row[3]}x{row[4]} px at {ppi:.0f} ppi"
        if ppi < MIN_PPI:
            very_low.append(where)
        elif ppi < PRINT_PPI:
            low.append(where)
        if color == "cmyk":
            cmyk.append(f"page {page}")
    r.ok(f"{len(seen)} raster image{'' if len(seen) == 1 else 's'}")
    if very_low:
        r.fail(f"images below {MIN_PPI} ppi at their printed size: visibly blurry in print", very_low)
    if low:
        r.warn(f"images below {PRINT_PPI} ppi at their printed size: fine on screen, soft in print", low)
    if not (low or very_low):
        r.ok(f"all images {PRINT_PPI} ppi or more at their printed size")
    if cmyk:
        r.fail(
            "CMYK images: they break PDF/A, which defines colour in RGB; export them as RGB "
            "(the printer converts)",
            sorted(set(cmyk), key=lambda s: int(s.split()[1])),
        )
    else:
        r.ok("no CMYK images (RGB and grey only, as PDF/A needs)")


# --- LaTeX log ---------------------------------------------------------------


def check_log(log: Path, r: Report) -> None:
    r.section(f"LaTeX log ({log.name})")
    if not log.exists():
        r.warn(
            f"{log.name} not found: compile first (on Overleaf, download the log from Logs and output files)"
        )
        return
    text = log.read_text(errors="replace")
    lines = text.splitlines()
    errors = [f"line {i + 1}: {l}" for i, l in enumerate(lines) if l.startswith("! ")]
    undef = sorted(set(re.findall(r"(?:Reference|Citation) [`']([^']+)' on page \d+ undefined", text)))
    missing = sorted(set(re.findall(r"Missing character: There is no (.+?) in font ([^!]+)!", text)))
    overfull = re.findall(r"^Overfull \\[hv]box \(([\d.]+)pt too \w+\) (.*)$", text, re.M)
    warnings = [l for l in lines if re.match(r"(LaTeX|Package \S+|Class \S+) Warning", l)]
    rerun = re.search(r"Rerun to get|rerun LaTeX|Please \(re\)run Biber", text)
    if errors:
        r.fail("errors (the PDF may be incomplete)", errors)
    else:
        r.ok("no errors")
    if undef:
        r.fail("undefined references or citations (they print as ?? or as the key)", undef)
    else:
        r.ok("all references and citations resolved")
    if missing:
        r.fail("missing characters (left out of the PDF)", [f"{c} in {f.strip()}" for c, f in missing])
    if overfull:
        r.warn(
            "overfull boxes (text sticking into the margin)", [f"{pt} pt {where}" for pt, where in overfull]
        )
    else:
        r.ok("no overfull boxes")
    # PDF backend warnings ("warning  (pdf inclusion): found PDF version ..."): TeX wraps them, so rejoin
    backend = []
    for i, l in enumerate(lines):
        if l.startswith("warning  ("):
            msg = l + (
                lines[i + 1] if i + 1 < len(lines) and not lines[i + 1].startswith(("(", "<", "[")) else ""
            )
            backend.append(msg.replace("warning  ", "", 1))
    inclusion = [b for b in backend if "PDF version" in b]
    if inclusion:
        r.warn(
            "figures saved as a newer PDF version than this PDF (1.4): harmless, but to clear the warning "
            "save them as PDF 1.4 (e.g. Inkscape: Save as PDF, version 1.4)",
            inclusion,
        )
    rest = [b for b in backend if b not in inclusion]
    if rest:
        r.warn("PDF backend warnings", rest)
    other = [w for w in warnings if "undefined" not in w and "Rerun" not in w]
    if other:
        r.warn("other warnings", other)
    if rerun:
        r.warn("the log asks for another run: compile again (latexmk does this by itself)")


def is_pdfx(path) -> bool:
    """A PDF/X file: an output intent of the kind GTS_PDFX (read with pikepdf when it is installed)."""
    try:
        import pikepdf

        with pikepdf.open(path) as pdf:
            return any(str(oi.get("/S")) == "/GTS_PDFX" for oi in pdf.Root.get("/OutputIntents", []))
    except ImportError:
        return b"GTS_PDFX" in Path(path).read_bytes()


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("pdf", nargs="?", type=Path, default=ROOT / "main.pdf", help="default: main.pdf")
    args = ap.parse_args(argv)
    for tool in ("pdfinfo", "pdffonts", "pdfimages"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found: install poppler (see the top of this script)")
    if not args.pdf.exists():
        sys.exit(f"{args.pdf} not found: compile first, or give the path of the PDF")
    info = run("pdfinfo", str(args.pdf))
    pages = re.search(r"Pages:\s+(\d+)", info)
    size = re.search(r"Page size:\s+(.+)", info)
    print(
        f"{args.pdf.name}: {pages.group(1) if pages else '?'} pages, {size.group(1).strip() if size else '?'}"
    )
    r = Report()
    if is_pdfx(args.pdf):
        # the print-preparation edition (PDF/X, for the printer): its own checks, then the log
        print("PDF/X (for the printer): tools/check_print.py")
        import check_print

        pr = check_print.check(args.pdf)
        for line in pr.facts:
            print(f"  {line}")
        for line in pr.errors:
            r.fail(line)
        for line in pr.warnings:
            r.warn(line)
    else:
        check_pdfa(args.pdf, r)
        check_fonts(args.pdf, r)
        check_images(args.pdf, r)
        check_contrast(args.pdf, r)
    check_log(args.pdf.with_suffix(".log"), r)
    print(f"\n{r.errors} problem(s) to fix, {r.warnings} warning(s) to look at.")
    return 1 if r.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
