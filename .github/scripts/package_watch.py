#!/usr/bin/env python3
"""package_watch.py: compare tonight's TeX Live with the last known-good state (.github/watch/).

    python3 .github/scripts/package_watch.py printer.log digital.log probe.log
    python3 .github/scripts/package_watch.py --update printer.log digital.log probe.log

Two things are compared:
  fingerprints  probe-fingerprints.txt, written by .github/watch/probe.tex: an MD5 of the definition of
                every internal command of LaTeX or a package that the template overrides, and whether every
                internal variable and socket it uses still exists. A change means a package update rewrote
                code the template patches: look at that patch (the audit's patch inventory), even if the
                thesis still compiles.
  versions      every package, class and file version the logs name, so a report says what changed.

Writes watch-report.md. Exit code 1 if a fingerprint changed (or the baseline is missing), 0 otherwise;
version changes alone are reported but are no reason to fail. --update writes the new baseline.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / ".github" / "watch"
VERSION = re.compile(r"^(?:Package|Document Class|File|Language|Lua module): (\S+) (.+)$")
ENGINE = re.compile(r"^This is (LuaHBTeX|LuaTeX), Version (\S+)")
FORMAT = re.compile(r"^(LaTeX2e <[^>]+>)")


def versions(logs: list[Path]) -> dict[str, str]:
    found = {}
    for log in logs:
        if not log.exists():
            continue
        for line in log.read_text(errors="replace").splitlines():
            if m := VERSION.match(line):
                if "/" not in m.group(1) and not m.group(2).startswith("Graphic file"):   # not the thesis's files
                    found[m.group(1)] = m.group(2).strip()
            elif m := ENGINE.match(line):
                found[m.group(1)] = m.group(2)
            elif m := FORMAT.match(line):
                found["LaTeX format"] = m.group(1)
    return found


def read_pairs(path: Path) -> dict[str, str]:
    pairs = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                name, _, value = line.rpartition(" ")
                pairs[name] = value
    return pairs


def write_pairs(path: Path, pairs: dict[str, str], sep=" "):
    path.write_text("".join(f"{k}{sep}{v}\n" for k, v in sorted(pairs.items())))


def diff(old: dict[str, str], new: dict[str, str]) -> list[str]:
    rows = []
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            rows.append(f"| `{k}` | {old.get(k, '(new)')} | {new.get(k, '(gone)')} |")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="*", type=Path, help="the build logs (for the versions)")
    ap.add_argument("--fingerprints", type=Path, default=Path("probe-fingerprints.txt"))
    ap.add_argument("--update", action="store_true", help="write the new baseline")
    args = ap.parse_args(argv)

    if not args.fingerprints.exists():
        Path("watch-report.md").write_text("The probe wrote no fingerprints: it did not compile.\n")
        print("no fingerprints: the probe did not compile")
        return 1
    new_fp = read_pairs(args.fingerprints)
    new_ver = versions(args.logs)
    if args.update:
        BASE.mkdir(parents=True, exist_ok=True)
        write_pairs(BASE / "fingerprints.txt", new_fp)
        (BASE / "versions.txt").write_text("".join(f"{k}: {v}\n" for k, v in sorted(new_ver.items())))
        print(f"baseline written: {len(new_fp)} fingerprints, {len(new_ver)} versions")
        return 0

    old_fp = read_pairs(BASE / "fingerprints.txt")
    old_ver = {}
    if (BASE / "versions.txt").exists():
        for line in (BASE / "versions.txt").read_text().splitlines():
            k, _, v = line.partition(": ")
            old_ver[k] = v
    fp_rows = diff(old_fp, new_fp) if old_fp else []
    ver_rows = diff(old_ver, new_ver) if old_ver else []
    out = ["# Nightly package watch", ""]
    if not old_fp:
        out += ["No baseline yet: run the workflow by hand with *update baseline* ticked.", ""]
    if fp_rows:
        out += ["## Patched internals that changed", "",
                "A package update rewrote code the template overrides. Check the patch for each (the audit's "
                "patch inventory names the file), even if the thesis still compiles; once it is right, run "
                "the workflow by hand with *update baseline* ticked.", "",
                "| Command | Before | Now |", "|---|---|---|", *fp_rows, ""]
    else:
        out += ["No patched internal changed.", ""]
    if ver_rows:
        out += ["## Versions that changed since the baseline", "", "| Package or file | Before | Now |",
                "|---|---|---|", *ver_rows, ""]
    Path("watch-report.md").write_text("\n".join(out))
    print("\n".join(out))
    return 1 if (fp_rows or not old_fp) else 0


if __name__ == "__main__":
    sys.exit(main())
