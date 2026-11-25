#!/usr/bin/env python3
"""
check_speech.py: what a screen reader gets from the digital edition, and whether it makes sense.

    python3 tools/check_speech.py digital.pdf                      # checks, writes speech/
    python3 tools/check_speech.py digital.pdf --baseline old.txt   # also: what changed since then

veraPDF says whether the tagging is valid; this says whether it reads well. It takes the PDF's
structure tree (with show-pdf-tags, part of TeX Live), reads it in order the way a screen reader
would, turns every formula's MathML into words with Speech Rule Engine, and checks:

  headings   every heading has text (a screen reader reads a heading's content, not its title),
             no level is skipped on the way down (H1 to H3), the first heading is a level 1
  figures    every figure has alternative text, and not a file name or a placeholder
  tables     every table has header cells
  links      every link has text; links that read out a bare web address are listed
  maths      every formula has MathML that gives words, both the copy in the structure tree and
             the associated file; formulas whose two copies read differently are listed
  text       characters a screen reader cannot say (private-use codes, U+FFFD)
  language   the document declares its language (needs pikepdf; skipped without it)

It writes, into speech/ (or --out):
  spoken.txt     the whole document as it would be read aloud: headings, paragraphs with the
                 formulas in words between ⟨ ⟩, figures by their alternative text, tables row by
                 row; "--- page N ---" lines say where you are
  findings.md    the problems, for the job summary on GitHub
  diff.txt       with --baseline: the changes in spoken.txt since that version (page lines ignored)

The exit code is 1 if anything must be fixed, 0 otherwise. Needs Python 3.10+, TeX Live's
show-pdf-tags (or --tags, its XML output) and Node.js with Speech Rule Engine:
    npm ci --prefix tools/speech
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from common import ROOT, Report, parser

MATHML = "http://www.w3.org/1998/Math/MathML"
PDF_NS = ("http://iso.org/pdf2/ssn", "http://iso.org/pdf/ssn")
SPEECH_JS = ROOT / "tools" / "speech" / "math-to-speech.mjs"

# Structure types that start a new line in spoken.txt
BLOCKS = {
    "Document", "Part", "Sect", "Div", "Art", "Aside", "P", "H", "Title", "Caption", "L", "LI", "LBody",
    "TOC", "TOCI", "BlockQuote", "Table", "THead", "TBody", "TFoot", "TR", "Figure",
    "Note", "FENote", "Index", "Bibliography", "BibEntry", "DocumentFragment",
}  # fmt: skip
HEADING = re.compile(r"H([1-9])$")
BAD_CHARS = re.compile(r"[-�]")
URL = re.compile(r"^(https?://|www\.|doi:|10\.\d{4,}/)\S+$", re.I)
PLACEHOLDER_ALT = re.compile(
    r"^(figure|image|picture|graphic|img|alt|todo|tbd|\S+\.(pdf|png|jpe?g|svg|eps))$", re.I
)


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def ns(tag) -> str:
    return tag[1:].split("}")[0] if isinstance(tag, str) and tag.startswith("{") else ""


def role(e) -> str:
    """The standard structure type: the element's own name in the PDF namespaces, else its role map."""
    if ns(e.tag) in PDF_NS:
        return local(e.tag)
    return e.get("rolemaps-to") or local(e.tag)


def is_pi(e) -> bool:
    return e.tag is ET.ProcessingInstruction


def page_of(pi) -> int | None:
    m = re.search(r'page="(\d+)"', pi.text or "")
    return int(m.group(1)) if m and (pi.text or "").startswith("MarkedContent") else None


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def mathml_string(e) -> str:
    """A clean MathML string from a <math> element of show-pdf-tags' XML (no ids, no PIs)."""

    def walk(n) -> str:
        if is_pi(n):
            return ""
        attrs = "".join(
            f' {k}="{v}"'
            for k, v in n.attrib.items()
            if k not in ("id",) and not k.startswith("{") and k != "rolemaps-to"
        )
        text = (n.text or "").strip()
        inner = escape(text) + "".join(walk(c) + escape((c.tail or "").strip()) for c in n)
        return f"<{local(n.tag)}{attrs}>{inner}</{local(n.tag)}>"

    return walk(e).replace("<math", f'<math xmlns="{MATHML}"', 1)


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Formula:
    page: int | None
    title: str
    se: str | None  # MathML from the structure tree
    af: str | None  # MathML from the associated file
    speech_se: str = ""
    speech_af: str = ""
    alt: str = ""
    direct: str = ""  # text in the Formula but outside its MathML
    linked: bool = True  # any content on the page belongs to it
    context: str = ""  # where it sits: TD, Caption, P, ...


@dataclass
class Reading:
    lines: list[tuple[int | None, str]] = field(default_factory=list)
    headings: list[tuple[int | None, int, str, str]] = field(default_factory=list)  # page, level, text, title
    figures: list[tuple[int | None, str, str]] = field(default_factory=list)  # page, alt, text
    tables: list[tuple[int | None, int, int, str]] = field(default_factory=list)  # page, rows, th, caption
    links: list[tuple[int | None, str]] = field(default_factory=list)
    formulas: list[Formula] = field(default_factory=list)
    bad_chars: list[tuple[int | None, str]] = field(default_factory=list)
    jumps: list[tuple[int, int, str]] = field(default_factory=list)  # page read, after page, text
    late_lines: int = 0  # lines read after a later page


class Reader:
    """Reads the structure tree in order, as a screen reader would."""

    def __init__(self):
        self.r = Reading()
        self.page: int | None = None
        self.buf: list[str] = []
        self.stack: list[str] = []  # the structure types around the current element
        self.in_row = 0  # inside a table row: cells are read on one line

    # --- text collection -------------------------------------------------------------------------
    def flush(self, prefix: str = ""):
        if self.in_row and prefix != "[row] ":
            self.buf.append(" ")
            return
        text = squash("".join(self.buf))
        self.buf = []
        if text:
            self.r.lines.append((self.page, prefix + text))

    def emit(self, s: str):
        if s:
            self.buf.append(s)

    def text_of(self, e) -> str:
        """Plain text content (no formulas in words): for checks."""
        parts = []
        for n in e.iter():
            if is_pi(n):
                parts.append(n.tail or "")
            elif n is not e and local(n.tag) == "AssociatedFile":
                continue
            else:
                parts.append(n.text or "")
                if n is not e:
                    parts.append(n.tail or "")
        return squash("".join(parts))

    # --- the walk --------------------------------------------------------------------------------
    def run(self, root) -> Reading:
        tree = root.find("StructTreeRoot")
        self.visit(tree if tree is not None else root)
        self.flush()
        return self.r

    def visit(self, e):
        if is_pi(e):
            p = page_of(e)
            if p is not None:
                self.page = p
            self.emit(e.tail or "")
            return
        name, kind = local(e.tag), role(e)
        if name == "AssociatedFile" or kind == "Artifact":
            return
        if ns(e.tag) == MATHML:  # MathML outside a Formula: read its text
            self.emit(self.text_of(e) + " ")
            return
        expansion = e.get("expansion")
        if kind == "Formula":
            self.formula(e)
            return
        if kind == "Figure":
            self.figure(e)
            return
        if expansion:  # an abbreviation or unit with its spoken form (/E)
            self.emit(f" {expansion} ")
            return

        block = kind in BLOCKS or HEADING.match(kind) or kind in ("TH", "TD")
        if kind == "Code":  # a code block holds lines (P); inline code (\verb) does not
            block = any(not is_pi(c) and role(c) in BLOCKS for c in e)
        if block and kind not in ("TH", "TD"):
            self.flush()
        if kind == "Table":
            self.table_start(e)
        elif kind == "L" and not self.in_row:
            items = sum(1 for c in e if not is_pi(c) and role(c) == "LI")
            self.r.lines.append((self.page, f"[list, {items} items]"))
        elif kind == "Link":
            alts = " ".join(n.get("alt") or "" for n in e.iter() if not is_pi(n) and n.get("alt"))
            self.r.links.append((self.page, squash(self.text_of(e) + " " + alts)))

        self.emit(e.text or "")
        self.stack.append(kind)
        self.in_row += kind == "TR"
        for c in e:
            self.visit(c)
            if not is_pi(c):
                self.emit(c.tail or "")
        self.in_row -= kind == "TR"
        self.stack.pop()

        m = HEADING.match(kind)
        if m:
            text = squash("".join(self.buf))
            self.r.headings.append((self.page, int(m.group(1)), text, e.get("title") or ""))
            self.flush(f"[heading level {m.group(1)}] ")
            if not text:
                self.r.lines.append((self.page, f"[heading level {m.group(1)}] (silent)"))
        elif kind in ("TH", "TD"):
            self.emit(" | ")
        elif kind == "Caption":
            self.flush("[caption] ")
        elif kind == "TR":
            self.buf = [re.sub(r"(\s*\|\s*)+", " | ", "".join(self.buf)).strip(" |")]
            self.flush("[row] ")
        elif block:
            self.flush()
        if kind == "Table":
            self.r.lines.append((self.page, "[end of table]"))

    def table_start(self, e):
        rows = [n for n in e.iter() if not is_pi(n) and role(n) == "TR"]
        th = sum(1 for n in e.iter() if not is_pi(n) and role(n) == "TH")
        cols = max((sum(1 for c in r if not is_pi(c) and role(c) in ("TH", "TD")) for r in rows), default=0)
        caption = next((self.text_of(n) for n in e.iter() if not is_pi(n) and role(n) == "Caption"), "")
        self.r.tables.append((self.page, len(rows), th, caption))
        self.r.lines.append((self.page, f"[table, {len(rows)} rows, {cols} columns]"))

    def figure(self, e):
        alt = squash(e.get("alt") or "")
        text = self.text_of(e)
        for n in e.iter():  # keep the page up to date
            if is_pi(n) and page_of(n) is not None:
                self.page = page_of(n)
                break
        self.r.figures.append((self.page, alt, text))
        self.emit(f" [figure: {alt}] " if alt else f" [figure without alternative text] {text} ")

    def formula(self, e):
        se = af = None
        page = None
        for n in e.iter():
            if is_pi(n) and page is None and page_of(n) is not None:
                page = page_of(n)
            elif local(n.tag) == "AssociatedFile" and af is None:
                m = next((c for c in n if local(c.tag) == "math"), None)
                af = mathml_string(m) if m is not None else None
        # the structure tree's MathML: the <math> children (some formulas have several pieces)
        pieces = [c for c in e if not is_pi(c) and local(c.tag) == "math" and ns(c.tag) == MATHML]
        if pieces:
            inner = "".join(re.sub(r"^<math[^>]*>|</math>$", "", mathml_string(p)) for p in pieces)
            se = f'<math xmlns="{MATHML}"><mrow>{inner}</mrow></math>'
        if page is not None:
            self.page = page
        direct = squash((e.text or "") + "".join(c.tail or "" for c in e if is_pi(c)))
        linked = any(is_pi(n) and (n.text or "").startswith("MarkedContent") for n in e.iter())
        context = next(
            (
                k
                for k in reversed(self.stack)
                if k
                in ("TD", "TH", "Caption", "P", "LBody", "H1", "H2", "H3", "H4", "TOCI", "Note", "FENote")
            ),
            self.stack[-1] if self.stack else "",
        )
        f = Formula(
            self.page,
            e.get("title") or "",
            se,
            af,
            alt=squash(e.get("alt") or ""),
            direct=direct,
            linked=linked,
            context=context,
        )
        self.r.formulas.append(f)
        self.emit(f" \0F{len(self.r.formulas) - 1}\0 ")


# --- tools ---------------------------------------------------------------------------------------
def structure_xml(pdf: Path, tags: Path | None) -> ET.Element:
    if tags:
        data = tags.read_bytes()
    else:
        exe = os.environ.get("SHOW_PDF_TAGS") or shutil.which("show-pdf-tags")
        if not exe:
            sys.exit("show-pdf-tags not found (part of TeX Live 2025 and later); or pass --tags")
        cmd = ["texlua", exe] if exe.endswith(".lua") else [exe]
        cwd = Path(exe).parent if exe.endswith(".lua") else None  # (an unpacked copy finds its modules)
        r = subprocess.run([*cmd, "--xml", str(pdf.resolve())], capture_output=True, cwd=cwd)
        if r.returncode != 0:
            sys.exit("show-pdf-tags failed:\n" + r.stderr.decode(errors="replace")[-2000:])
        data = r.stdout
    p = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
    p.feed(data)
    return p.close()


def speak(formulas: list[Formula]) -> str | None:
    """Fills in the formulas' speech with Speech Rule Engine. Returns an error message, or None."""
    node = shutil.which("node")
    if not node:
        return "Node.js not found: formulas are not turned into words"
    if not (SPEECH_JS.parent / "node_modules" / "speech-rule-engine").exists():
        return "Speech Rule Engine not installed: run  npm ci --prefix tools/speech"
    jobs = []
    for i, f in enumerate(formulas):
        if f.se:
            jobs.append(json.dumps({"id": f"{i}:se", "mathml": f.se}))
        if f.af:
            jobs.append(json.dumps({"id": f"{i}:af", "mathml": f.af}))
    r = subprocess.run(
        [node, str(SPEECH_JS)], input="\n".join(jobs), capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        return "Speech Rule Engine failed: " + r.stderr[-500:]
    for line in r.stdout.splitlines():
        o = json.loads(line)
        i, which = o["id"].split(":")
        setattr(formulas[int(i)], f"speech_{which}", squash(o.get("speech", "")))
    return None


def document_language(pdf: Path) -> str | None | bool:
    """The catalogue's /Lang; False if pikepdf is not installed."""
    try:
        import pikepdf
    except ImportError:
        return False
    with pikepdf.open(pdf) as doc:
        lang = doc.Root.get("/Lang")
        return str(lang) if lang is not None else None


def release_baseline(name: str = "spoken.txt") -> str | None:
    """spoken.txt of the repository's latest release on GitHub (in Actions: GITHUB_REPOSITORY, GITHUB_TOKEN)."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo:
        return None
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "check_speech"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=30) as r:
            rel = json.load(r)
        asset = next((a for a in rel.get("assets", []) if a["name"] == name), None)
        if not asset:
            return None
        headers["Accept"] = "application/octet-stream"
        with urllib.request.urlopen(urllib.request.Request(asset["url"], headers=headers), timeout=60) as r:
            return r.read().decode("utf-8")
    except Exception as e:  # no release yet, no network: then there is simply no comparison
        print(f"  (note: no spoken.txt from the latest release: {e})", file=sys.stderr)
        return None


# --- checks --------------------------------------------------------------------------------------
def where(page) -> str:
    return f"p. {page}" if page else "p. ?"


def check(rd: Reading, lang, r: Report, md: list[str]):
    def fail(msg, details=()):
        r.fail(msg, details)
        md.append(f"- **FAIL** {msg}" + "".join(f"\n  - {d}" for d in list(details)[:20]))

    def warn(msg, details=()):
        r.warn(msg, details)
        md.append(f"- WARN {msg}" + "".join(f"\n  - {d}" for d in list(details)[:20]))

    r.section("Language")
    if lang is False:
        print("  note  pikepdf not installed: language not checked")
    elif not lang:
        fail("the document declares no language (/Lang): a screen reader guesses the voice")
    else:
        r.ok(f"document language: {lang}")

    r.section("Headings")
    silent = [f"{where(p)}: level {lv} '{title}'" for p, lv, text, title in rd.headings if not text]
    if silent:
        fail(f"{len(silent)} heading(s) without text: a screen reader says only 'heading level N'", silent)
    jumps, prev = [], 0
    for p, lv, text, title in rd.headings:
        if prev and lv > prev + 1:
            jumps.append(f"{where(p)}: level {prev} to {lv}: '{text or title}'")
        prev = lv
    if jumps:
        fail(f"{len(jumps)} heading level(s) skipped on the way down", jumps)
    if rd.headings and rd.headings[0][1] != 1:
        warn(f"the first heading is level {rd.headings[0][1]}, not 1")
    if not silent and not jumps:
        r.ok(f"{len(rd.headings)} headings, all with text, no levels skipped")

    r.section("Figures")
    no_alt = [f"{where(p)}: {text[:60] or '(no text either)'}" for p, alt, text in rd.figures if not alt]
    weak = [f"{where(p)}: '{alt}'" for p, alt, text in rd.figures if alt and PLACEHOLDER_ALT.match(alt)]
    if no_alt:
        fail(f"{len(no_alt)} figure(s) without alternative text", no_alt)
    if weak:
        fail(f"{len(weak)} figure(s) whose alternative text is a file name or a placeholder", weak)
    if not no_alt and not weak:
        r.ok(f"{len(rd.figures)} figures, all with alternative text")

    r.section("Tables")
    no_th = [f"{where(p)}: {cap[:60] or '(no caption)'}" for p, rows, th, cap in rd.tables if rows and not th]
    if no_th:
        fail(f"{len(no_th)} table(s) without header cells (TH): cells are read without their column", no_th)
    else:
        r.ok(f"{len(rd.tables)} tables, all with header cells")

    r.section("Links")
    empty = [where(p) for p, t in rd.links if not t]
    bare = [f"{where(p)}: {t}" for p, t in rd.links if t and URL.match(t)]
    if empty:
        fail(f"{len(empty)} link(s) without text", empty)
    if bare:
        print(f"  note  {len(bare)} link(s) read out a bare address or DOI (fine in the references)")
    if not empty:
        r.ok(f"{len(rd.links)} links, all with text")

    r.section("Maths")
    places = {"TD": "table cells", "TH": "table headers", "Caption": "captions", "P": "paragraphs",
              "LBody": "lists", "TOCI": "the contents", "Note": "notes", "FENote": "notes"}  # fmt: skip
    no_mathml = [f"{where(f.page)}: {f.title}" for f in rd.formulas if not f.se and not f.af]
    unlinked = [f for f in rd.formulas if not f.linked and not f.speech_se]
    if unlinked:
        by: dict[str, int] = {}
        for f in unlinked:
            k = places.get(f.context, f.context or "elsewhere")
            by[k] = by.get(k, 0) + 1
        warn(
            f"{len(unlinked)} empty formula tag(s): nothing on the page belongs to them (phantoms, such as "
            "siunitx's alignment digits, or a caption typeset twice to measure it). Silent when the structure "
            "is read, but a tool that reads the MathML files says them: "
            + ", ".join(f"{n} in {k}" for k, n in sorted(by.items(), key=lambda kv: -kv[1])),
            [f"{where(f.page)} ({f.context}): its file says '{f.speech_af[:70]}'" for f in unlinked],
        )
    silent = [f for f in rd.formulas if f.linked and not f.speech_se and not f.direct]
    if silent:
        fail(f"{len(silent)} formula(s) whose MathML in the structure tree says nothing",
             [f"{where(f.page)}: should say '{f.speech_af[:70]}'" for f in silent])  # fmt: skip
    outside = [f for f in rd.formulas if f.direct]
    if outside:
        warn(
            f"{len(outside)} formula(s) with characters outside their MathML elements (in the formula, "
            "but not in an <mi>/<mn>/<mo>): read as loose text, not as maths",
            [f"{where(f.page)}: '{f.direct[:30]}' outside; tree says '{f.speech_se[:50]}'" for f in outside],
        )
    silent_af = [f"{where(f.page)}: {f.title}" for f in rd.formulas if f.af is not None and not f.speech_af]
    if silent_af:
        fail(f"{len(silent_af)} formula(s) whose associated MathML file says nothing", silent_af)
    if no_mathml:
        fail(f"{len(no_mathml)} formula(s) without MathML", no_mathml)
    differ = [
        f"{where(f.page)}: tree '{f.speech_se[:50]}' / file '{f.speech_af[:50]}'"
        for f in rd.formulas
        if f.speech_se and f.speech_af and not f.direct and norm(f.speech_se) != norm(f.speech_af)
    ]
    if differ:
        warn(f"{len(differ)} formula(s) read differently from the structure tree and the file", differ)
    if not (no_mathml or silent or silent_af):
        r.ok(f"{len(rd.formulas)} formulas, all with MathML that gives words")

    r.section("Reading order")
    if rd.jumps:
        warn(
            f"{rd.late_lines} line(s) are read after a later page ({len(rd.jumps)} jump(s) back): floats "
            "placed at the end of the structure, for example",
            [f"p. {p} read after p. {top}: '{t}'" for p, top, t in rd.jumps],
        )
    else:
        r.ok("pages are read in order")

    r.section("Text")
    if rd.bad_chars:
        fail(
            f"{len(rd.bad_chars)} line(s) with characters a screen reader cannot say",
            [f"{where(p)}: ...{t}..." for p, t in rd.bad_chars],
        )
    else:
        r.ok("no unspeakable characters")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def spoken_text(rd: Reading) -> str:
    out, page, top = [], object(), 0
    for p, line in rd.lines:
        if p != page and p is not None:
            out.append(f"--- page {p} ---")
            page = p
        line = re.sub(r"\0F(\d+)\0", lambda m: wrap(say(rd.formulas[int(m.group(1))])), line)
        line = squash(line)
        if not line:
            continue
        if p is not None and p < top - 1:
            rd.late_lines += 1
            if not rd.jumps or rd.jumps[-1][1] != top:
                rd.jumps.append((p, top, line[:60]))
        top = max(top, p or 0)
        out.append(line)
        bad = BAD_CHARS.search(line)
        if bad:
            rd.bad_chars.append((p, line[max(0, bad.start() - 25) : bad.end() + 25]))
    return "\n".join(out) + "\n"


def wrap(speech: str) -> str:
    return f"⟨{speech}⟩" if speech else ""


def say(f: Formula) -> str:
    """What a screen reader reading the structure tree says (the structure tree's MathML, else loose text)."""
    if f.speech_se:
        return f"{f.direct} {f.speech_se}".strip() if f.direct else f.speech_se
    if f.direct:
        return f.direct
    if not f.linked:
        return ""  # an empty tag: nothing to read
    return f"(silent; its MathML file says: {f.speech_af})" if f.speech_af else "(silent)"


def diff(old: str, new: str) -> str:
    keep = [ln for ln in old.splitlines() if not ln.startswith("--- page ")]
    now = [ln for ln in new.splitlines() if not ln.startswith("--- page ")]
    return "\n".join(difflib.unified_diff(keep, now, "baseline", "now", lineterm="", n=1))


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("pdf", type=Path, help="the tagged PDF (the digital edition)")
    ap.add_argument("--tags", type=Path, help="show-pdf-tags --xml output, instead of running it")
    ap.add_argument("--out", type=Path, default=Path("speech"), help="output folder (default speech/)")
    ap.add_argument("--baseline", type=Path, help="an earlier spoken.txt to compare with")
    ap.add_argument(
        "--baseline-release", action="store_true", help="compare with spoken.txt of the latest GitHub release"
    )
    args = ap.parse_args(argv)
    if not args.pdf.exists():
        sys.exit(f"{args.pdf} not found")

    root = structure_xml(args.pdf, args.tags)
    rd = Reader().run(root)
    r, md = Report(), []
    print(f"{args.pdf.name}: {len(rd.lines)} lines read aloud, {len(rd.formulas)} formulas")
    err = speak(rd.formulas)
    if err:
        r.fail(err)
        md.append(f"- **FAIL** {err}")
    text = spoken_text(rd)
    check(rd, document_language(args.pdf), r, md)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "spoken.txt").write_text(text, encoding="utf-8")
    old = args.baseline.read_text(encoding="utf-8") if args.baseline else None
    if old is None and args.baseline_release:
        old = release_baseline()
    r.section("Changes")
    if old is not None:
        d = diff(old, text)
        (args.out / "diff.txt").write_text(d + "\n", encoding="utf-8")
        changed = sum(1 for ln in d.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))
        print(f"  note  {changed} line(s) read differently from the baseline: {args.out / 'diff.txt'}")
        md.append(f"\n{changed} line(s) read differently from the last release (see diff.txt).")
    else:
        print("  note  no baseline to compare with")

    head = "**Speech check: FAIL**" if r.errors else "**Speech check: OK**"
    counts = f"{r.errors} problem(s) to fix, {r.warnings} warning(s); {len(rd.formulas)} formulas read."
    (args.out / "findings.md").write_text(f"{head}\n\n{counts}\n\n" + "\n".join(md) + "\n", encoding="utf-8")
    print(f"\n{counts}  Read-aloud text: {args.out / 'spoken.txt'}")
    return 1 if r.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
