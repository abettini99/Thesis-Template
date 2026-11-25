#!/usr/bin/env python3
"""
check_ua1.py: how the digital edition fares in a PDF/UA-1 checker such as PAC.

    python3 tools/check_ua1.py              # checks main.pdf
    python3 tools/check_ua1.py other.pdf    # another PDF

The thesis is PDF/UA-2 (PDF 2.0), and veraPDF checks that in check_pdf.py. Many people judge
accessibility with PAC or Acrobat, which check PDF/UA-1 (PDF 1.7). This runs veraPDF's PDF/UA-1
profile, built on the same test conditions as PAC (the Matterhorn Protocol), and sorts what fails:

  expected   what a PDF/UA-2 file cannot meet in PDF/UA-1: its identification and PDF version,
             the MathML in the formulas and other structure types new in PDF 2.0, and the
             repeated header rows of long tables, tagged with PDF 2.0's Artifact element
  to fix     what PDF/UA-1 checkers report and the template could avoid (formulas without
             alternate text)
  unexplained  anything else: look into it

A report only: the exit code is 0, unless --strict is given and something is unexplained.
Needs veraPDF (https://verapdf.org) and Python with pikepdf.
"""

from __future__ import annotations

import collections
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import ROOT, parser

# structure types of PDF 1.7 (ISO 32000-1, 14.8.4): anything else is new in PDF 2.0 or MathML
PDF17 = set(
    "Document Part Art Sect Div BlockQuote Caption TOC TOCI Index NonStruct Private P H H1 H2 H3 H4 "
    "H5 H6 L LI Lbl LBody Table TR TH TD THead TBody TFoot Span Quote Note Reference BibEntry Code "
    "Link Annot Ruby RB RT RP Warichu WT WP Figure Formula Form".split()
)
SSN = "http://iso.org/pdf/ssn"
MATHML = "http://www.w3.org/1998/Math/MathML"


def structure(pdf: Path) -> dict:
    """What in the tag structure explains PDF/UA-1 findings: PDF 2.0 and MathML types, Artifact rows."""
    import pikepdf

    p = pikepdf.open(pdf)
    st = p.Root.get("/StructTreeRoot")
    out = {"new": collections.Counter(), "artifact_children": 0, "artifact_cells": 0}
    if st is None:
        return out
    rolemap = {}
    for ns in st.get("/Namespaces", []):
        for k, v in (ns.get("/RoleMapNS") or {}).items():
            if isinstance(v, pikepdf.Array):
                target = str(v[1].get("/NS")) if len(v) > 1 else SSN
                rolemap[(str(ns.get("/NS")), str(k))] = (str(v[0]), target)
            else:
                rolemap[(str(ns.get("/NS")), str(k))] = (str(v), str(ns.get("/NS")))

    def standard(e):
        s, ns = str(e.S), (str(e.NS.get("/NS")) if "/NS" in e else SSN)
        for _ in range(8):
            if (ns, s) not in rolemap:
                break
            s, ns = rolemap[(ns, s)]
        return s[1:], ns

    def kids(e):
        k = e.get("/K")
        if k is None:
            return []
        return [c for c in (k if isinstance(k, pikepdf.Array) else [k]) if isinstance(c, pikepdf.Dictionary)]

    def walk(e, parent):
        if "/S" not in e:
            return
        s, ns = standard(e)
        if s not in PDF17:
            out["new"]["MathML" if ns == MATHML else s] += 1
        if s == "Artifact" and parent == "Table":
            out["artifact_children"] += 1
        if s in ("TD", "TH") and parent == "Artifact":
            out["artifact_cells"] += 1
        for c in kids(e):
            walk(c, s)

    for c in kids(st):
        walk(c, None)
    return out


def failures(pdf: Path) -> list[tuple[str, int, str]]:
    """The PDF/UA-1 rules veraPDF finds broken: (clause-test, failed checks, description)."""
    verapdf = shutil.which("verapdf")
    if not verapdf:
        sys.exit("veraPDF not found: install it from https://verapdf.org (see the README)")
    xml = subprocess.run(
        [verapdf, "--flavour", "ua1", "--format", "xml", str(pdf)], capture_output=True, text=True
    ).stdout
    if "<validationReport" not in xml:
        sys.exit("veraPDF gave no report:\n" + xml[-2000:])
    rules = []
    for m in re.finditer(
        r'<rule [^>]*clause="([^"]+)" testNumber="(\d+)" status="failed" failedChecks="(\d+)"[^>]*>'
        r"\s*<description>(.*?)</description>",
        xml,
        re.S,
    ):
        rules.append((f"{m.group(1)}-{m.group(2)}", int(m.group(3)), " ".join(m.group(4).split())))
    return rules


def main(argv: list[str]) -> int:
    ap = parser(__doc__)
    ap.add_argument("pdf", nargs="?", default=str(ROOT / "main.pdf"))
    ap.add_argument("--strict", action="store_true", help="exit code 1 if anything is unexplained")
    args = ap.parse_args(argv)
    pdf = Path(args.pdf)
    s = structure(pdf)
    new = ", ".join(f"{n} {k}" for k, n in s["new"].most_common(8))
    expected = {
        "5-2": "identifies itself as PDF/UA-2, not PDF/UA-1",
        "6.1-1": "PDF 2.0, where PDF/UA-1 asks for PDF 1.7",
    }
    groups = {"expected": [], "to fix": [], "unexplained": []}
    for rule, n, desc in failures(pdf):
        if rule in expected:
            groups["expected"].append((rule, n, expected[rule]))
        elif rule == "7.1-5" and n <= sum(s["new"].values()):
            groups["expected"].append((rule, n, f"structure types new in PDF 2.0 and MathML ({new})"))
        elif rule == "7.2-3" and n <= s["artifact_children"]:
            groups["expected"].append(
                (rule, n, "long tables: repeated header rows tagged as PDF 2.0 Artifact elements")
            )
        elif rule == "7.2-9" and n <= s["artifact_cells"]:
            groups["expected"].append((rule, n, "long tables: cells of those repeated header rows"))
        elif rule == "7.7-1":
            groups["to fix"].append((rule, n, "formulas with MathML but without alternate text (Alt)"))
        else:
            groups["unexplained"].append((rule, n, desc))

    lines = [f"PDF/UA-1, with veraPDF's profile (the test conditions PAC uses): {pdf.name}"]
    for name, rows in groups.items():
        lines.append(f"\n{name}: {len(rows)} rule(s), {sum(n for _, n, _ in rows)} check(s)")
        lines += [f"  {rule:7} {n:6}  {text}" for rule, n, text in rows]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:  # (shown on the run's page)
        with open(summary, "a") as f:
            f.write("### PDF/UA-1, with veraPDF's profile (the test conditions PAC uses)\n\n")
            f.write("| | Rule | Checks | |\n|---|---|---|---|\n")
            for name, rows in groups.items():
                for rule, n, text in rows:
                    f.write(f"| {name} | {rule} | {n} | {text} |\n")
            f.write("\n")
    return 1 if args.strict and groups["unexplained"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
