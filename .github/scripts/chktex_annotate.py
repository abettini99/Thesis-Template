#!/usr/bin/env python3
"""
chktex_annotate.py: run chktex on .tex files and show its warnings as annotations on GitHub.

    python3 .github/scripts/chktex_annotate.py chapters/01Introduction.tex ...

Each warning appears next to its line in the commit or pull request (and in the run's summary).
Settings, and the warnings left out, are in .chktexrc. Never fails: these are suggestions.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main(files: list[str]) -> int:
    files = [f for f in files if f.endswith(".tex") and os.path.exists(f)]
    if not files:
        print("No .tex files to check.")
        return 0
    total = 0
    lines = []
    for f in files:
        # -v0: file:line:column:number:message; -q: no banner; -l: our settings
        r = subprocess.run(
            ["chktex", "-q", "-v0", "-l", ".chktexrc", f], capture_output=True, text=True, errors="replace"
        )
        for row in r.stdout.splitlines():
            parts = row.split(":", 4)
            if len(parts) < 5 or not parts[1].isdigit():
                continue
            path, line, col, num, msg = parts
            total += 1
            msg = msg.strip().replace("%", "%25").replace("\n", " ")
            print(f"::warning file={path},line={line},col={col},title=chktex {num}::{msg}")
            lines.append(f"| `{path}:{line}` | {num} | {msg} |")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write(f"### chktex: {total} suggestion(s) in {len(files)} file(s)\n\n")
            if lines:
                s.write("| where | # | suggestion |\n|---|---|---|\n" + "\n".join(lines[:200]) + "\n")
    print(f"chktex: {total} suggestion(s) in {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
