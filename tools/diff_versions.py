#!/usr/bin/env python3
"""
diff_versions.py: a PDF that marks every change since an earlier version, for your supervisors
or the committee: deleted text struck through in red, new text underlined in blue.

    git tag draft-2026-10                          # when you send a version out
    python3 tools/diff_versions.py draft-2026-10   # later: changes since then -> main-diff.pdf

The earlier version is any git revision: a tag, a commit, a branch (HEAD~3 works too). It is
compared with the files as they are now (saved, not necessarily committed). The chapters are
followed through \\include and \\input, so the whole thesis is compared.

Runs locally (Overleaf cannot run it): needs git, latexdiff and latexmk, which come with TeX Live.
The result, main-diff.tex and main-diff.pdf, is ignored by git.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from common import ROOT, parser


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("old", help="earlier version: a git tag, commit or branch")
    ap.add_argument("--main", default="main.tex", help="main file (default main.tex)")
    ap.add_argument("--no-compile", action="store_true", help="only write main-diff.tex")
    args = ap.parse_args(argv)
    for tool in ("git", "latexdiff") + (() if args.no_compile else ("latexmk",)):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found (latexdiff and latexmk come with TeX Live)")

    stem = Path(args.main).stem
    out = ROOT / f"{stem}-diff.tex"
    with tempfile.TemporaryDirectory() as tmp:
        old = Path(tmp)
        r = subprocess.run(["git", "archive", "--format=tar", args.old], cwd=ROOT, capture_output=True)
        if r.returncode:
            sys.exit(f"git cannot find version '{args.old}': {r.stderr.decode().strip()}")
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
            if hasattr(tarfile, "data_filter"):
                t.extractall(old, filter="data")
            else:
                t.extractall(old)
        if not (old / args.main).exists():
            sys.exit(f"{args.main} does not exist in version {args.old}")
        print(f"Comparing {args.main} at {args.old} with the current files ...")
        r = subprocess.run(
            ["latexdiff", "--flatten", "--type=UNDERLINE", "--subtype=SAFE", "--math-markup=coarse",
             "--encoding=utf8", str(old / args.main), str(ROOT / args.main)],
            cwd=ROOT, capture_output=True, text=True)
        if r.returncode or not r.stdout.strip():
            sys.exit("latexdiff failed:\n" + r.stderr[-2000:])
        out.write_text(r.stdout, encoding="utf-8")
    print(f"written: {out.name}")
    if args.no_compile:
        return 0
    r = subprocess.run(["latexmk", "-interaction=nonstopmode", "-halt-on-error", out.name],
                       cwd=ROOT, capture_output=True, text=True)
    pdf = out.with_suffix(".pdf")
    if r.returncode or not pdf.exists():
        print(f"Compiling {out.name} failed: see {out.with_suffix('.log').name}. latexdiff sometimes marks up "
              "a construct LaTeX cannot take; compile it by hand, or compare a smaller range of versions.")
        return 1
    print(f"written: {pdf.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
