#!/usr/bin/env python3
"""
check_pdf.py: check the compiled thesis before you hand it in or send it to the printer.

    python3 tools/check_pdf.py              # checks main.pdf and main.log
    python3 tools/check_pdf.py other.pdf    # another PDF (and its .log, if there is one)

It reports what a print shop or the TU Delft repository may reject:

  archival PDF  PDF/A-2u, with veraPDF (https://verapdf.org) when it is installed and
                the template's own basic checks otherwise
  fonts         every font embedded, no bitmap (Type 3) fonts, every font mapped to
                Unicode (so text can be searched and copied); figure files with
                fonts that are not embedded are named
  images        resolution of raster images at their printed size (300 ppi or more
                for print), and CMYK images (they break PDF/A)
  LaTeX log     errors, undefined references and citations, missing characters,
                overfull boxes, and whether a rerun is needed

The exit code is 1 if anything must be fixed, 0 otherwise. Needs Python 3.8+ and
the poppler tools pdfinfo, pdffonts and pdfimages (part of TeX Live on Windows;
"brew install poppler" on macOS; "poppler-utils" on Linux).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRINT_PPI, MIN_PPI = 300, 150


class Report:
    def __init__(self):
        self.errors = self.warnings = 0

    def section(self, title):
        print(f"\n{title}")

    def ok(self, msg):
        print(f"  OK    {msg}")

    def warn(self, msg, details=()):
        self.warnings += 1
        print(f"  WARN  {msg}")
        for d in list(details)[:12]:
            print(f"          {d}")
        if len(details) > 12:
            print(f"          ... and {len(details) - 12} more")

    def fail(self, msg, details=()):
        self.errors += 1
        print(f"  FAIL  {msg}")
        for d in list(details)[:12]:
            print(f"          {d}")
        if len(details) > 12:
            print(f"          ... and {len(details) - 12} more")


def run(*cmd) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout


def table(text: str, skip: int = 2) -> list[list[str]]:
    return [line.split() for line in text.splitlines()[skip:] if line.strip()]


# --- archival PDF -------------------------------------------------------------

def check_pdfa(pdf: Path, r: Report) -> None:
    r.section("Archival PDF (PDF/A-2u)")
    verapdf = shutil.which("verapdf")
    if verapdf:
        out = run(verapdf, "--flavour", "2u", "--format", "text", str(pdf))
        if re.search(r"^PASS\b", out, re.M):
            r.ok("veraPDF: PDF/A-2u compliant")
        else:
            rules = sorted(set(re.findall(r"^\s*FAIL\s+(\S.*)$", out, re.M))) or out.strip().splitlines()[-5:]
            r.fail("veraPDF: not PDF/A-2u compliant", rules)
        return
    data = pdf.read_bytes()
    xmp = run("pdfinfo", "-meta", str(pdf))
    part = re.search(r"pdfaid:part(?:>|=\")(\d)", xmp)
    conf = re.search(r"pdfaid:conformance(?:>|=\")([A-Za-z])", xmp)
    if part and conf and (part.group(1), conf.group(1).upper()) == ("2", "U"):
        r.ok("declares PDF/A-2u")
    else:
        r.fail("does not declare PDF/A-2u (the class sets this up: check that the build finished)")
    if b"/GTS_PDFA1" in data:
        r.ok("colour profile (output intent) present")
    else:
        r.fail("no PDF/A output intent (colour profile)")
    if b"/Encrypt" in data:
        r.fail("the PDF is encrypted; PDF/A does not allow that")
    if b"/JavaScript" in data:
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
        r.warn("Type 3 fonts, usually from a figure: some are bitmaps (blurry in print) and some printers "
               "refuse them. In matplotlib use the template's style file (pdf.fonttype 42)", sorted(set(type3)))
    if nouni:
        r.fail("fonts without a Unicode map: text in them cannot be searched or copied (PDF/A-2u)",
               sorted(set(nouni)))
    else:
        r.ok("all fonts map to Unicode")
    figures = sorted((ROOT / "Images").rglob("*.pdf")) if (ROOT / "Images").is_dir() else []
    bad = []
    for fig in figures:
        frows = [row for row in table(run("pdffonts", str(fig))) if len(row) >= 7]
        missing = sorted({row[0] for row in frows if row[-5] != "yes"})
        t3 = sorted({row[0] for row in frows if "Type 3" in " ".join(row)})
        if missing or t3:
            what = ", ".join(([f"not embedded: {', '.join(missing)}"] if missing else [])
                             + ([f"Type 3: {', '.join(t3)}"] if t3 else []))
            bad.append(f"{fig.relative_to(ROOT)}  ({what})")
    if bad:
        r.warn("figure files with problem fonts (fix them at the source and export again)", bad)
    elif figures:
        r.ok(f"fonts in the {len(figures)} figure PDFs in Images/ are embedded")


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
        r.fail("CMYK images: they break PDF/A, which defines colour in RGB; export them as RGB "
               "(the printer converts)", sorted(set(cmyk), key=lambda s: int(s.split()[1])))
    else:
        r.ok("no CMYK images (RGB and grey only, as PDF/A needs)")


# --- LaTeX log ---------------------------------------------------------------

def check_log(log: Path, r: Report) -> None:
    r.section(f"LaTeX log ({log.name})")
    if not log.exists():
        r.warn(f"{log.name} not found: compile first (on Overleaf, download the log from Logs and output files)")
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
        r.warn("overfull boxes (text sticking into the margin)",
               [f"{pt} pt {where}" for pt, where in overfull])
    else:
        r.ok("no overfull boxes")
    # PDF backend warnings ("warning  (pdf inclusion): found PDF version ..."): TeX wraps them, so rejoin
    backend = []
    for i, l in enumerate(lines):
        if l.startswith("warning  ("):
            msg = l + (lines[i + 1] if i + 1 < len(lines) and not lines[i + 1].startswith(("(", "<", "[")) else "")
            backend.append(msg.replace("warning  ", "", 1))
    inclusion = [b for b in backend if "PDF version" in b]
    if inclusion:
        r.warn("figures saved as a newer PDF version than this PDF (1.4): harmless, but to clear the warning "
               "save them as PDF 1.4 (e.g. Inkscape: Save as PDF, version 1.4)", inclusion)
    rest = [b for b in backend if b not in inclusion]
    if rest:
        r.warn("PDF backend warnings", rest)
    other = [w for w in warnings if "undefined" not in w and "Rerun" not in w]
    if other:
        r.warn("other warnings", other)
    if rerun:
        r.warn("the log asks for another run: compile again (latexmk does this by itself)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
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
    print(f"{args.pdf.name}: {pages.group(1) if pages else '?'} pages, {size.group(1).strip() if size else '?'}")
    r = Report()
    check_pdfa(args.pdf, r)
    check_fonts(args.pdf, r)
    check_images(args.pdf, r)
    check_log(args.pdf.with_suffix(".log"), r)
    print(f"\n{r.errors} problem(s) to fix, {r.warnings} warning(s) to look at.")
    return 1 if r.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
