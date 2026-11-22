#!/usr/bin/env python3
"""
check_bib.py: tidy the bibliography (references.bib).

    python3 tools/check_bib.py               # report only
    python3 tools/check_bib.py --doi         # also look up missing DOIs on Crossref (internet)
    python3 tools/check_bib.py --doi --write # and write the safe fixes into references.bib

It reports:
  errors     entries that cannot be read, keys used twice, keys cited in the thesis
             that the .bib file does not have
  duplicates the same work twice (same DOI, or the same title and year)
  unused     entries the thesis does not cite (read from main.bcf, written when you compile)
  fields     required fields missing for the entry type (an article without journal, ...)
  DOIs       articles, papers and books without a DOI; with --doi a DOI is suggested when
             Crossref finds the same title (and year)
  format     page ranges with a single hyphen (12-18 instead of 12--18), DOIs given as a
             doi.org URL instead of in the doi field

--write changes only what is certain: page ranges, a doi.org URL moved to the doi field,
and DOIs that Crossref matched on title and year. The old file is kept as references.bib.bak.
Needs only Python 3.8+.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from common import ROOT, parser

REQUIRED = {
    "article": [("author",), ("title",), ("journal", "journaltitle"), ("year", "date")],
    "book": [("author", "editor"), ("title",), ("publisher",), ("year", "date")],
    "inproceedings": [("author",), ("title",), ("booktitle",), ("year", "date")],
    "incollection": [("author",), ("title",), ("booktitle",), ("year", "date")],
    "techreport": [("author",), ("title",), ("institution",), ("year", "date")],
    "report": [("author",), ("title",), ("institution",), ("year", "date")],
    "phdthesis": [("author",), ("title",), ("school", "institution"), ("year", "date")],
    "mastersthesis": [("author",), ("title",), ("school", "institution"), ("year", "date")],
    "thesis": [("author",), ("title",), ("institution", "school"), ("year", "date")],
    "online": [("title",), ("url", "doi")],
    "misc": [("title",)],
}
WANTS_DOI = {"article", "inproceedings", "incollection", "book"}


# --- reading the .bib file -------------------------------------------------------

class Entry:
    def __init__(self, kind, key, start, end, fields):
        self.kind, self.key, self.start, self.end, self.fields = kind, key, start, end, fields

    def get(self, name):
        f = self.fields.get(name)
        return f[0] if f else ""


def read_value(text, i):
    """Read a field value at text[i:]: {...}, "..." or a bare word. Returns (value, end)."""
    if text[i] == "{":
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{" and text[j - 1] != "\\":
                depth += 1
            elif text[j] == "}" and text[j - 1] != "\\":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j], j + 1
            j += 1
        raise ValueError("unbalanced braces")
    if text[i] == '"':
        j, depth = i + 1, 0
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            elif text[j] == '"' and depth == 0:
                return text[i + 1:j], j + 1
            j += 1
        raise ValueError("unterminated quote")
    m = re.match(r"[^,}\s]+", text[i:])
    return (m.group(0) if m else ""), i + (m.end() if m else 0)


def parse(text):
    entries, errors = [], []
    for m in re.finditer(r"@(\w+)\s*\{", text):
        kind = m.group(1).lower()
        if kind in ("comment", "preamble", "string"):
            continue
        line = text.count("\n", 0, m.start()) + 1
        km = re.match(r"\s*([^,\s]+)\s*,", text[m.end():])
        if not km:
            errors.append(f"line {line}: @{kind} without a key")
            continue
        key, i, fields = km.group(1), m.end() + km.end(), {}
        try:
            while True:
                ws = re.match(r"[\s,]*", text[i:])
                i += ws.end()
                if text[i] == "}":
                    break
                i_name = i
                fm = re.match(r"([\w:+.-]+)\s*=\s*", text[i:])
                if not fm:
                    raise ValueError(f"cannot read the field at '{text[i:i + 20].strip()}'")
                name, vstart = fm.group(1).lower(), i + fm.end()
                value, i = read_value(text, vstart)
                fields[name] = (value.strip(), vstart, i, i_name)
        except (ValueError, IndexError) as e:
            errors.append(f"line {line}: {key}: {e}")
            continue
        entries.append(Entry(kind, key, m.start(), i + 1, fields))
    return entries, errors


def plain(s):
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def year_of(e):
    return (e.get("year") or e.get("date"))[:4]


# --- Crossref ---------------------------------------------------------------------

def crossref_doi(e):
    """Look the title up on Crossref; return (doi, title found, similarity) or None."""
    query = {"query.bibliographic": plain(e.get("title")), "rows": "3", "select": "DOI,title,issued"}
    author = re.split(r"\s+and\s+", e.get("author"))[0] if e.get("author") else ""
    if author:
        query["query.author"] = plain(author.split(",")[0] if "," in author else author.split()[-1])
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "thesis-template check_bib.py (mailto:)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.load(r)["message"]["items"]
    best = None
    for it in items:
        title = (it.get("title") or [""])[0]
        sim = difflib.SequenceMatcher(None, plain(title), plain(e.get("title"))).ratio()
        year = str((it.get("issued", {}).get("date-parts") or [[None]])[0][0] or "")
        if best is None or sim > best[2]:
            best = (it["DOI"], title, sim, year)
    return best


# --- report -----------------------------------------------------------------------

def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("bib", nargs="?", type=Path, default=ROOT / "references.bib")
    ap.add_argument("--bcf", type=Path, default=ROOT / "main.bcf", help="biblatex control file (default main.bcf)")
    ap.add_argument("--doi", action="store_true", help="look up missing DOIs on Crossref")
    ap.add_argument("--write", action="store_true", help="write the safe fixes into the .bib file")
    args = ap.parse_args(argv)

    text = args.bib.read_text(encoding="utf-8")
    entries, errors = parse(text)
    problems = len(errors)
    print(f"{args.bib.name}: {len(entries)} entries")
    for e in errors:
        print(f"  FAIL  {e}")

    keys = {}
    for e in entries:
        keys.setdefault(e.key.lower(), []).append(e)
    for k, es in keys.items():
        if len(es) > 1:
            problems += 1
            print(f"  FAIL  key used {len(es)} times: {es[0].key}")

    # cited keys from the .bcf (biber's input, written by every compile)
    cited, cite_all = set(), False
    if args.bcf.exists():
        bcf = args.bcf.read_text(errors="replace")
        cited = set(re.findall(r"<bcf:citekey[^>]*>([^<]+)</bcf:citekey>", bcf))
        cite_all = "*" in cited
        missing = sorted(k for k in cited - {"*"} if k.lower() not in keys)
        if missing:
            problems += 1
            print(f"  FAIL  cited but not in {args.bib.name}: {', '.join(missing)}")
        unused = [] if cite_all else sorted(e.key for e in entries if e.key not in cited)
        if unused:
            print(f"  WARN  not cited in the thesis ({len(unused)}): {', '.join(unused)}")
    else:
        print(f"  note  {args.bcf.name} not found: compile once to check cited and unused entries")

    seen_doi, seen_title = {}, {}
    fixes = []                                   # (start, end, replacement) in the .bib text
    lookups = []
    for e in entries:
        doi = e.get("doi").strip()
        if doi:
            d = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.lower())
            if d in seen_doi:
                print(f"  WARN  same DOI in {seen_doi[d]} and {e.key}: the same work twice?")
            seen_doi[d] = e.key
        t = (plain(e.get("title")), year_of(e))
        if t[0] and t in seen_title:
            print(f"  WARN  same title and year in {seen_title[t]} and {e.key}: the same work twice?")
        seen_title[t] = e.key

        for alternatives in REQUIRED.get(e.kind, []):
            if not any(e.get(a) for a in alternatives):
                print(f"  WARN  {e.key} (@{e.kind}): no {' or '.join(alternatives)}")

        pages = e.fields.get("pages")
        if pages and re.fullmatch(r"\s*\w+\s*-\s*\w+\s*", pages[0]) and "--" not in pages[0]:
            new = re.sub(r"\s*-\s*", "--", pages[0].strip())
            print(f"  WARN  {e.key}: pages {pages[0]} -> {new} (an en dash, as in 12--18)")
            fixes.append((pages[1] + 1, pages[2] - 1, new) if text[pages[1]] in "{\"" else (pages[1], pages[2], new))

        url = e.fields.get("url")
        if url and re.match(r"https?://(dx\.)?doi\.org/", url[0]):
            d = re.sub(r"https?://(dx\.)?doi\.org/", "", url[0])
            if doi:
                print(f"  WARN  {e.key}: url repeats the DOI; remove the url field")
            else:
                print(f"  WARN  {e.key}: DOI given as url; it belongs in doi = {{{d}}}")
                fixes.append((url[1], url[2], "{" + d + "}"))
                fixes.append((url[3], url[3] + 3, "doi"))
                doi = d

        if not doi and e.kind in WANTS_DOI:
            lookups.append(e)

    if lookups:
        print(f"  WARN  no DOI ({len(lookups)}): {', '.join(e.key for e in lookups)}"
              + ("" if args.doi else "  (--doi looks them up)"))
    if args.doi:
        for e in lookups:
            try:
                found = crossref_doi(e)
            except Exception as ex:                  # offline, rate limit, ...
                print(f"        {e.key}: Crossref lookup failed ({ex.__class__.__name__})")
                continue
            if not found:
                print(f"        {e.key}: nothing found")
                continue
            doi, title, sim, year = found
            sure = sim >= 0.95 and (not year_of(e) or year == year_of(e))
            print(f"        {e.key}: {'match' if sure else 'possible match'} doi = {{{doi}}}"
                  + ("" if sure else f"  (\"{title}\", {year}; check it)"))
            if sure:
                pos = e.end - 1
                while text[pos - 1] in " \t\n":
                    pos -= 1
                comma = "" if text[pos - 1] == "," else ","
                line = text[text.rfind("\n", 0, pos) + 1:pos]
                indent = re.match(r"[ \t]*", line).group(0) or "    "
                fixes.append((pos, pos, f"{comma}\n{indent}doi = {{{doi}}}"))

    if args.write and fixes:
        shutil.copy2(args.bib, args.bib.with_suffix(".bib.bak"))
        for start, end, new in sorted(fixes, reverse=True):
            text = text[:start] + new + text[end:]
        args.bib.write_text(text, encoding="utf-8")
        print(f"\n{len(fixes)} fix(es) written to {args.bib.name} (old version: {args.bib.name}.bak)")
    elif fixes:
        print(f"\n{len(fixes)} fix(es) can be written with --write")
    print(f"{problems} problem(s) to fix.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
