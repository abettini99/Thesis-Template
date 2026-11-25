#!/usr/bin/env python3
"""
judge_speech.py: an AI listener's verdict on the read-aloud thesis: PASS or FAIL, and why.

    python3 tools/judge_speech.py                 # reads speech/spoken.txt and speech/findings.md
    python3 tools/judge_speech.py --out speech    # (the folder tools/check_speech.py wrote)
    python3 tools/judge_speech.py --demo          # a sample speech-judge.pdf, without the API

tools/check_speech.py checks the structure by rule; this asks a language model (Claude, through
the Anthropic API) the question the rules cannot answer: could a blind reader follow this? The
model reads speech/spoken.txt, chapter by chapter, as a listener would hear it, and answers PASS
or FAIL. On FAIL it lists what a listener hears, why that is a problem and how to fix it, and
this writes them, with the automatic findings, into speech/speech-judge.pdf (a tagged PDF/UA-2,
compiled with LuaLaTeX).

It judges only whether the speech can be followed: not the writing, not the science, not the
template's placeholder text, and not the speech engine's own wording.

Needs the environment variable ANTHROPIC_API_KEY (on GitHub: a repository secret of that name);
without it, it says so and stops with exit code 0. The model is SPEECH_JUDGE_MODEL (default
claude-sonnet-5-5). This sends the thesis text to Anthropic: leave the secret out if that is not
allowed for your thesis. The exit code is 1 on FAIL, 0 on PASS or when the judge could not run.
Needs Python 3.10+ (and LuaLaTeX for the PDF).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import parser

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("SPEECH_JUDGE_MODEL", "claude-sonnet-5-5")
CHUNK = 80_000  # characters of spoken.txt per request

SYSTEM = """\
You review the accessibility of a doctoral thesis for blind readers. You are given the thesis as a \
screen reader would read it aloud, produced from the PDF's tag structure:

- "[heading level N] text" is a heading; "[heading level N] (silent)" means the heading has no text \
  and the listener hears only "heading level N".
- Text between ⟨ and ⟩ is a formula, as Speech Rule Engine (ClearSpeak style) speaks its MathML. \
  "(silent; its MathML file says: ...)" means the screen reader hears nothing there.
- "[figure: ...]" is a figure read by its alternative text.
- "[table, R rows, C columns]" starts a table, "[row] a | b | c" is one row (cells separated by |).
- "[list, N items]" starts a list; "[caption]" marks a caption.
- "--- page N ---" lines are not spoken; they tell you where you are.

Decide whether a blind listener could follow and understand this part of the thesis.

Answer FAIL only for problems that stop a listener from getting the content, for example:
- headings, formulas, figures or table cells that are silent or lose part of their content;
- formulas whose speech is wrong because of the markup: loose letters or numbers outside the maths, \
  numbers split into pieces, operator names spelled out as letters, missing or wrong grouping that \
  changes the meaning;
- alternative text that is missing, a file name, a placeholder, or does not say what the figure shows;
- reading order that puts content where it no longer makes sense;
- text that comes out as garbage, spelled letter by letter, or repeated.

Do not count: the writing style or the science; placeholder text of the template such as [year], \
[city] or Lorem ipsum; the speech engine's general wording (ClearSpeak is verbose, "normal d" for an \
upright d is fine); hyphenation; the page markers.

List minor issues too, marked "minor"; they do not make the verdict FAIL.

Answer with JSON only, no other text:
{"verdict": "PASS" or "FAIL",
 "summary": "one or two sentences",
 "problems": [{"severity": "major" or "minor", "page": "page number(s) as text",
               "heard": "what the listener hears, copied from the input (at most 200 characters)",
               "why": "why this is a problem for a listener", "fix": "how to fix it in the LaTeX source"}]}
"""


def chunks(text: str) -> list[str]:
    """spoken.txt in pieces: whole chapters (split at level 1 headings) up to CHUNK characters."""
    parts, cur = [], []
    for line in text.splitlines(keepends=True):
        if line.startswith("[heading level 1]") and sum(map(len, cur)) > CHUNK // 4:
            parts.append("".join(cur))
            cur = []
        cur.append(line)
        if sum(map(len, cur)) > CHUNK and line.startswith("--- page "):
            parts.append("".join(cur))
            cur = []
    if cur:
        parts.append("".join(cur))
    # join small neighbours
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + len(p) <= CHUNK:
            out[-1] += p
        else:
            out.append(p)
    return out


def ask(key: str, findings: str, part: str, n: int, total: int) -> dict:
    user = (
        f"Part {n} of {total} of the thesis. For context, the automatic structure checks reported:\n\n"
        f"{findings}\n\n--- The thesis as read aloud (part {n} of {total}) ---\n\n{part}"
    )
    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 8000,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode()
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    for attempt in range(4):
        try:
            req = urllib.request.Request(API, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=600) as r:
                reply = json.load(r)
            text = "".join(b.get("text", "") for b in reply.get("content", []) if b.get("type") == "text")
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                raise ValueError(f"no JSON in the answer: {text[:300]}")
            return json.loads(m.group(0))
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(f"Anthropic API: HTTP {e.code}: {msg}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(f"Anthropic API not reachable: {e}") from e
    raise RuntimeError("Anthropic API: no answer")


DEMO = {
    "verdict": "FAIL",
    "summary": "A sample verdict, to show what the report looks like.",
    "problems": [
        {
            "severity": "major",
            "page": "22",
            "heard": "[heading level 1] (silent)",
            "why": "The listener hears only 'heading level 1' and cannot tell which chapter starts.",
            "fix": "Put the chapter title inside the heading's structure (the heading template).",
        },
        {
            "severity": "minor",
            "page": "32",
            "heard": "⟨𝜌 the fraction with numerator crossed out times U squared⟩ & 50% $x_1$",
            "why": "The cancelled rho is read as a loose letter before the fraction.",
            "fix": "Check how \\cancel is tagged.",
        },
    ],
}


# --- the PDF -------------------------------------------------------------------------------------
def tex(s: str) -> str:
    """Text for LaTeX: special characters escaped."""
    rep = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
        "%": r"\%", "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    }  # fmt: skip
    s = "".join(rep.get(c, c) for c in str(s))
    return s.replace("\0", "")


def md_to_tex(md: str) -> str:
    """findings.md (a list with sub-items) as LaTeX lists."""
    out, depth = [], 0
    for line in md.splitlines():
        m = re.match(r"^(\s*)- (.*)$", line)
        if not m:
            while depth:
                out.append(r"\end{itemize}")
                depth -= 1
            if line.strip():
                out.append(tex(line.replace("**", "")) + r"\par")
            continue
        level = len(m.group(1)) // 2 + 1
        while depth < level:
            out.append(r"\begin{itemize}")
            depth += 1
        while depth > level:
            out.append(r"\end{itemize}")
            depth -= 1
        item = tex(m.group(2))
        item = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", item)
        out.append(r"\item " + item)
    while depth:
        out.append(r"\end{itemize}")
        depth -= 1
    return "\n".join(out)


def kpse(name: str) -> bool:
    try:
        return subprocess.run(["kpsewhich", name], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def write_pdf(out: Path, verdict: dict, findings: str) -> Path | None:
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    major = [p for p in verdict.get("problems", []) if p.get("severity") != "minor"]
    minor = [p for p in verdict.get("problems", []) if p.get("severity") == "minor"]

    def problems(ps):
        if not ps:
            return r"None.\par"
        rows = []
        for p in ps:
            rows.append(
                r"\item[\textbf{p.~" + tex(p.get("page", "?")) + r"}] "
                r"\textit{A listener hears:} \enquote{" + tex(p.get("heard", "")) + r"}\par"
                r"\textit{Why:} " + tex(p.get("why", "")) + r"\par"
                r"\textit{Fix:} " + tex(p.get("fix", ""))
            )
        return "\\begin{description}\n" + "\n".join(rows) + "\n\\end{description}"

    # fonts for characters Latin Modern lacks (⟨ ⟩, maths letters): those that are installed
    found = [f for f in ("DejaVuSans.ttf", "STIXTwoMath-Regular.otf", "latinmodern-math.otf") if kpse(f)]
    fallback = ", ".join(f'"file:{f}:mode=harf;"' for f in found)
    doc = rf"""\DocumentMetadata{{lang=en-GB, pdfversion=2.0, pdfstandard=ua-2, tagging=on}}
\documentclass[11pt,a4paper]{{article}}
\usepackage{{fontspec}}
\directlua{{luaotfload.add_fallback("judgefallback", {{{fallback}}})}}
\setmainfont{{Latin Modern Roman}}[RawFeature={{fallback=judgefallback}}]
\usepackage[margin=25mm]{{geometry}}
\usepackage{{csquotes}}
\usepackage{{hyperref}}
\hypersetup{{pdftitle={{Speech check: FAIL}}, pdfdisplaydoctitle}}
\setlength{{\parindent}}{{0pt}}\setlength{{\parskip}}{{0.5\baselineskip}}
\begin{{document}}
\section*{{Speech check: FAIL}}
{tex(repo)} {tex(sha)} \quad {tex(when)} \quad judged by {tex(MODEL)}

\textbf{{Summary.}} {tex(verdict.get("summary", ""))}

The digital edition was read the way a screen reader reads it (tools/check\_speech.py, the file
spoken.txt in the same artifact), and a language model judged whether a blind listener could follow it.

\subsection*{{Why it fails}}
{problems(major)}

\subsection*{{Minor issues}}
{problems(minor)}

\subsection*{{Automatic checks (tools/check\_speech.py)}}
{md_to_tex(findings)}
\end{{document}}
"""
    src = out / "speech-judge.tex"
    src.write_text(doc, encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(
            ["lualatex", "-interaction=nonstopmode", "-halt-on-error", src.name],
            cwd=out,
            capture_output=True,
            text=True,
            errors="replace",
        )
    pdf = out / "speech-judge.pdf"
    if r.returncode != 0 or not pdf.exists():
        print("  (note: speech-judge.pdf could not be compiled; see speech-judge.log)", file=sys.stderr)
        return None
    return pdf


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument(
        "--out", type=Path, default=Path("speech"), help="check_speech.py's folder (default speech/)"
    )
    ap.add_argument("--demo", action="store_true", help="write a sample speech-judge.pdf (no API call)")
    args = ap.parse_args(argv)
    if args.demo:
        args.out.mkdir(parents=True, exist_ok=True)
        pdf = write_pdf(
            args.out, DEMO, "- **FAIL** 1 heading(s) without text (a sample finding)\n  - p. 22: level 1"
        )
        print(f"Sample: {pdf}" if pdf else "The sample could not be compiled")
        return 0 if pdf else 1
    spoken = args.out / "spoken.txt"
    if not spoken.exists():
        sys.exit(f"{spoken} not found: run tools/check_speech.py first")
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("AI judge skipped: no ANTHROPIC_API_KEY (add it as a repository secret to turn the judge on)")
        return 0
    findings = (
        (args.out / "findings.md").read_text(encoding="utf-8") if (args.out / "findings.md").exists() else ""
    )

    parts = chunks(spoken.read_text(encoding="utf-8"))
    results = []
    try:
        for i, part in enumerate(parts, 1):
            print(f"Asking {MODEL} about part {i} of {len(parts)} ({len(part)} characters) ...", flush=True)
            results.append(ask(key, findings, part, i, len(parts)))
    except (RuntimeError, ValueError) as e:
        print(f"AI judge could not run: {e}")
        (args.out / "judge.md").write_text(f"**AI judge: could not run** ({e})\n", encoding="utf-8")
        return 0

    problems = [p for r in results for p in r.get("problems", [])]
    failed = any(str(r.get("verdict", "")).upper() == "FAIL" for r in results) or any(
        p.get("severity") != "minor" for p in problems
    )
    verdict = {
        "verdict": "FAIL" if failed else "PASS",
        "summary": " ".join(r.get("summary", "") for r in results).strip(),
        "problems": problems,
        "model": MODEL,
    }
    (args.out / "judge.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    major = sum(p.get("severity") != "minor" for p in problems)
    line = f"**AI judge ({MODEL}): {verdict['verdict']}**: {verdict['summary']}"
    if failed:
        line += f"\n\n{major} major and {len(problems) - major} minor issue(s); see speech-judge.pdf."
    (args.out / "judge.md").write_text(line + "\n", encoding="utf-8")
    print(verdict["verdict"])
    if not failed:
        return 0
    pdf = write_pdf(args.out, verdict, findings)
    if pdf:
        print(f"Why: {pdf}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
