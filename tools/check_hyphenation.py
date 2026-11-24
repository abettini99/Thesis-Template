#!/usr/bin/env python3
"""
check_hyphenation.py: list the words TeX hyphenated at the end of a line, to review them.

    python3 tools/check_hyphenation.py              # reads main.log (compile first, with LuaLaTeX)
    python3 tools/check_hyphenation.py other.log
    python3 tools/check_hyphenation.py --all        # list every hyphenated word, not just the doubtful

TeX hyphenates by patterns and gets technical terms, names and compounds wrong now and then
("ana-lysis", "Navier-Sto-kes"). The class writes every hyphenated word and its page to the log;
this lists them, alphabetically with their pages, and points out:

  across pages   a word split over two pages (the reader turns the page mid-word): reword,
                 or keep the word together with \\mbox{...}
  ladders        three or more hyphenated lines in a row: they look ragged
  names, terms   capitalised words (not at the start of a sentence), acronyms and words with
                 digits: check the break, or forbid it
  short halves   breaks that leave two letters on one side

Fix a wrong break by adding the word to settings/hyphenation.tex, with the right breaks marked
(\\hyphenation{equi-lib-rium}) or none at all (\\hyphenation{Navier}). Needs Python 3.8+.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from common import ROOT, parser


def read(log: Path):
    text = log.read_text(errors="replace")
    # TeX wraps the log at 79 characters: rejoin every record (they end with ";")
    records, buf = [], None
    for line in text.splitlines():
        if buf is not None:
            buf += line
        else:
            i = line.find("Thesis hyphen ")
            if i < 0:
                continue
            buf = line[i:]
        if ";" in buf:
            records.append(buf[: buf.index(";")])
            buf = None
    words = defaultdict(dict)
    for r in records:
        m = re.match(r"Thesis hyphen (\d+) para (\d+) line (\d+) (start|mid) before: (.*)$", r)
        if m:
            words[int(m[1])].update(para=int(m[2]), line=int(m[3]), start=m[4] == "start", before=m[5])
            continue
        m = re.match(r"Thesis hyphen (\d+) after: (.*)$", r)
        if m:
            words[int(m[1])]["after"] = m[2]
            continue
        m = re.match(r"Thesis hyphen (\d+) page([12]) (\d+)$", r)
        if m:
            words[int(m[1])][f"page{m[2]}"] = int(m[3])
    # lines measured in a box and thrown away (captions, tables tried twice) never reach a page: skip them
    return [w for _, w in sorted(words.items()) if "before" in w and "after" in w and "page1" in w]


def clean(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip(".,;:!?()[]\"'“”‘’")


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("log", nargs="?", type=Path, default=ROOT / "main.log", help="default: main.log")
    ap.add_argument("--all", action="store_true", help="list every hyphenated word")
    args = ap.parse_args(argv)
    if not args.log.exists():
        sys.exit(f"{args.log} not found: compile first (with LuaLaTeX)")
    words = read(args.log)
    if not words and "Thesis hyphen" not in args.log.read_text(errors="replace"):
        sys.exit(f"{args.log.name} has no hyphenation log: compile with LuaLaTeX and the template's class")
    for w in words:
        w["before"], w["after"] = clean(w["before"]), clean(w["after"])
        w["word"] = w["before"] + w["after"]
    print(f"{len(words)} hyphenated line ends\n")

    across = [w for w in words if w.get("page1") and w.get("page2") and w["page1"] != w["page2"]]
    ladders, run = [], []
    for w in words:
        if run and w["para"] == run[-1]["para"] and w["line"] == run[-1]["line"] + 1:
            run.append(w)
        else:
            if len(run) >= 3:
                ladders.append(run)
            run = [w]
    if len(run) >= 3:
        ladders.append(run)
    # names and terms: a capital that is not just the start of a sentence, two capitals, or a digit
    names = [
        w
        for w in words
        if (w["word"][:1].isupper() and not w.get("start"))
        or sum(c.isupper() for c in w["word"]) >= 2
        or any(c.isdigit() for c in w["word"])
    ]
    short = [w for w in words if min(len(w["before"]), len(w["after"])) <= 2]

    def show(w):
        return f"{w['before']}-{w['after']} (page {w.get('page1', '?')})"

    issues = 0
    if across:
        issues += len(across)
        print("Split across two pages (reword, or keep together with \\mbox{...}):")
        for w in across:
            print(f"  {w['before']}- | -{w['after']}   pages {w['page1']}/{w['page2']}")
        print()
    if ladders:
        issues += len(ladders)
        print("Three or more hyphenated lines in a row:")
        for run in ladders:
            print(
                "  "
                + ", ".join(f"{w['before']}-{w['after']}" for w in run)
                + f"   (page {run[0].get('page1', '?')})"
            )
        print()
    if names:
        print(
            "Names, acronyms and terms with digits: check the break, or forbid it in settings/hyphenation.tex:"
        )
        for w in names:
            print("  " + show(w))
        print()
    if short:
        print("Two letters on one side of the break:")
        for w in short:
            print("  " + show(w))
        print()
    if args.all:
        byword = defaultdict(list)
        for w in words:
            byword[(w["word"].lower(), w["before"] + "-" + w["after"])].append(w.get("page1", "?"))
        print("All hyphenated words:")
        for (_word, broken), pages in sorted(byword.items()):
            print(f"  {broken:<32} page {', '.join(str(p) for p in pages)}")
        print()
    elif words:
        print("(--all lists every hyphenated word)")
    print(f"{issues} place(s) to look at.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
