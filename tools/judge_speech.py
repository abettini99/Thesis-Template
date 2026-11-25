#!/usr/bin/env python3
"""
judge_speech.py: an AI listener's verdict on the read-aloud thesis: PASS or FAIL, and why.

    python3 tools/judge_speech.py                 # reads speech/spoken.txt and speech/findings.md
    python3 tools/judge_speech.py --out speech    # (the folder tools/check_speech.py wrote)
    python3 tools/judge_speech.py --backend openai   # any OpenAI-compatible API (see below)
    python3 tools/judge_speech.py --demo          # a sample speech-judge.pdf, without a model

tools/check_speech.py checks the structure by rule; this asks a language model the question the
rules cannot answer: could a blind reader follow this? The model reads speech/spoken.txt, chapter by chapter, as a listener would hear it, and answers PASS
or FAIL. On FAIL it lists what a listener hears, why that is a problem and how to fix it, and
this writes them, with the automatic findings, into speech/speech-judge.pdf (a tagged PDF/UA-2,
compiled with LuaLaTeX).

It judges only whether the speech can be followed: not the writing, not the science, not the
template's placeholder text, and not the speech engine's own wording.

Two backends (--backend, or the environment variable SPEECH_JUDGE_BACKEND):

  claude  Claude through the Anthropic API. Needs ANTHROPIC_API_KEY (on GitHub: a repository secret
          of that name); the model is SPEECH_JUDGE_MODEL (default claude-sonnet-5-5). The default
          when the key is set.
  openai  any API that speaks OpenAI's chat completions: OpenAI, Mistral, Google Gemini, OpenRouter,
          Groq, GitHub Models, or a model of your own behind Ollama or llama.cpp. Set
          SPEECH_JUDGE_URL to its base address, SPEECH_JUDGE_MODEL to the model and
          SPEECH_JUDGE_API_KEY to the key (none for a server of your own). Base addresses:
              OpenAI      https://api.openai.com/v1
              Mistral     https://api.mistral.ai/v1
              Gemini      https://generativelanguage.googleapis.com/v1beta/openai
              OpenRouter  https://openrouter.ai/api/v1
              Ollama      http://localhost:11434/v1   (a model on your own machine)
          and the model name as the provider lists it.
          The default when SPEECH_JUDGE_API_KEY and SPEECH_JUDGE_URL are set and no Anthropic key.

Either way the thesis text goes to that provider: leave the keys out if that is not allowed for
your thesis. --focus sends only the lines that can go wrong (headings, formulas, figures, tables,
captions, lists; formulas with some words around them): about 40 % less text, so cheaper and faster.
SPEECH_JUDGE_ADVISORY=true makes a FAIL from the model advice only (the build does not fail on it).

Without a backend (no key, no --backend) it says so and stops with exit code 0. The exit code is 1
on FAIL, 0 on PASS or when the judge could not run. Needs Python 3.10+ (and LuaLaTeX for the PDF).
judge.json in the output folder has the verdict and, per part, the time and the token counts.
"""

from __future__ import annotations

import argparse
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
MODEL = os.environ.get("SPEECH_JUDGE_MODEL") or "claude-sonnet-5-5"  # (for openai: SPEECH_JUDGE_MODEL)
CHUNK = 80_000  # characters of spoken.txt per request

# The answer's shape; sent to OpenAI-compatible APIs that accept a JSON schema
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "summary": {"type": "string"},
        "problems": {
            "type": "array",
            "maxItems": 25,
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["major", "minor"]},
                    "page": {"type": "string"},
                    "heard": {"type": "string"},
                    "why": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["severity", "page", "heard", "why", "fix"],
            },
        },
    },
    "required": ["verdict", "summary", "problems"],
}

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


RISKY = re.compile(r"⟨|\[heading level|\[figure|\[table|\[row\]|\[caption\]|\[list|\(silent")


def focus(text: str, around: int = 160) -> str:
    """Only the lines that can go wrong; in long paragraphs, only the formulas and words around them."""
    out, page = [], None
    for line in text.splitlines():
        if line.startswith("--- page "):
            page = line
            continue
        if not RISKY.search(line):
            continue
        if page:
            out.append(page)
            page = None
        if len(line) > 4 * around and "⟨" in line:
            spans = [(max(0, m.start() - around), min(len(line), m.end() + around))
                     for m in re.finditer(r"⟨[^⟩]*⟩", line)]  # fmt: skip
            merged: list[list[int]] = []
            for a, b in spans:
                if merged and a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            line = " … ".join(trim(line, a, b) for a, b in merged)
        out.append(line)
    return "\n".join(out) + "\n"


def trim(line: str, a: int, b: int) -> str:
    """line[a:b], widened to whole words (so that no word looks cut off to the model)."""
    while a > 0 and not line[a - 1].isspace():
        a -= 1
    while b < len(line) and not line[b].isspace():
        b += 1
    return line[a:b].strip()


def chunks(text: str, size: int) -> list[str]:
    """spoken.txt in pieces: whole chapters (split at level 1 headings) up to size characters."""
    parts, cur = [], []
    for line in text.splitlines(keepends=True):
        if line.startswith("[heading level 1]") and sum(map(len, cur)) > size // 4:
            parts.append("".join(cur))
            cur = []
        cur.append(line)
        if sum(map(len, cur)) > size and line.startswith("--- page "):
            parts.append("".join(cur))
            cur = []
    if cur:
        parts.append("".join(cur))
    # join small neighbours
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + len(p) <= size:
            out[-1] += p
        else:
            out.append(p)
    return out


def prompt(findings: str, part: str, n: int, total: int, focused: bool) -> str:
    note = (
        "Only the lines that can go wrong are shown (headings, formulas, figures, tables, captions, lists); "
        '"…" marks text left out of a paragraph. Judge what is shown.\n\n'
        if focused
        else ""
    )
    return (
        f"Part {n} of {total} of the thesis.\n\nThe automatic structure checks have already reported the "
        "problems below. They are fixed separately: do NOT report them again (no silent headings, tables "
        "without header cells, links without text, or anything else listed here). Report only problems "
        "these checks miss. If you find none, answer PASS with an empty list.\n\n"
        f"{findings}\n\n{note}--- The thesis as read aloud (part {n} of {total}) ---\n\n{part}"
    )


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON in the answer: {text[:300]}")
    return json.loads(m.group(0))


def ask_claude(key: str, user: str) -> tuple[dict, dict]:
    t0 = time.monotonic()
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
            usage = reply.get("usage", {})
            stats = {
                "seconds": round(time.monotonic() - t0, 1),
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            }
            return parse(text), stats
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


def chat_url(base: str) -> str:
    base = base.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def ask_openai(url: str, key: str, model: str, user: str) -> tuple[dict, dict]:
    """An OpenAI-compatible chat completions API. Providers differ in what they accept, so a request
    they refuse is sent again without the schema, or with max_completion_tokens for max_tokens."""
    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "max_tokens": 8000,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "verdict", "schema": SCHEMA},
        },
    }
    headers = {"content-type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    t0 = time.monotonic()
    for attempt in range(6):
        try:
            req = urllib.request.Request(chat_url(url), data=json.dumps(params).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=900) as r:
                reply = json.load(r)
            text = reply["choices"][0]["message"].get("content") or ""
            usage = reply.get("usage", {})
            stats = {
                "seconds": round(time.monotonic() - t0, 1),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
            return parse(text), stats
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            low = msg.lower()
            if e.code == 400 and "max_tokens" in low and "max_tokens" in params:
                params["max_completion_tokens"] = params.pop("max_tokens")  # (OpenAI's newer models)
                continue
            if e.code in (400, 422) and "response_format" in params:
                params.pop("response_format")  # no JSON schema here: the instructions ask for JSON anyway
                continue
            if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(f"{chat_url(url)}: HTTP {e.code}: {msg}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 5:
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(f"{chat_url(url)} not reachable: {e}") from e
    raise RuntimeError(f"{chat_url(url)}: no answer")


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


def write_pdf(out: Path, verdict: dict, findings: str, label: str = MODEL) -> Path | None:
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
\usepackage{{unicode-math}}
\directlua{{luaotfload.add_fallback("judgefallback", {{{fallback}}})}}
\setmainfont{{Latin Modern Roman}}[RawFeature={{fallback=judgefallback}}]
\usepackage[margin=25mm]{{geometry}}
\usepackage{{csquotes}}
\usepackage{{hyperref}}
\hypersetup{{pdftitle={{Speech check: FAIL}}, pdfdisplaydoctitle}}
\setlength{{\parindent}}{{0pt}}\setlength{{\parskip}}{{0.5\baselineskip}}
\begin{{document}}
\section*{{Speech check: FAIL}}
{tex(repo)} {tex(sha)} \quad {tex(when)} \quad judged by {tex(label)}

\textbf{{Summary.}} {tex(verdict.get("summary", ""))}

The digital edition was read the way a screen reader reads it (tools/check\_speech.py, the file
spoken.txt in the same artifact), and a language model judged whether a blind listener could follow it.

\subsection*{{What the model found beyond the automatic checks}}
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
    ap.add_argument("--demo", action="store_true", help="write a sample speech-judge.pdf (no model)")
    ap.add_argument("--backend", choices=["claude", "openai", "none"], help="default: SPEECH_JUDGE_BACKEND")
    ap.add_argument("--focus", action=argparse.BooleanOptionalAction, default=False,
                    help="only the lines that can go wrong (cheaper)")  # fmt: skip
    ap.add_argument("--chunk", type=int, default=CHUNK, help=f"characters per request (default {CHUNK})")
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
    okey = os.environ.get("SPEECH_JUDGE_API_KEY", "").strip()
    ourl = os.environ.get("SPEECH_JUDGE_URL", "").strip()
    default = "claude" if key else ("openai" if okey and ourl else "none")
    backend = (args.backend or os.environ.get("SPEECH_JUDGE_BACKEND") or default).lower()
    if backend in ("none", ""):
        print(
            "AI judge skipped: no backend (set the ANTHROPIC_API_KEY secret, or see --help for other models)"
        )
        return 0
    if backend not in ("claude", "openai"):
        sys.exit(f"unknown backend {backend!r}: claude, openai or none")
    if backend == "claude" and not key:
        print("AI judge skipped: backend claude, but no ANTHROPIC_API_KEY")
        return 0
    omodel = os.environ.get("SPEECH_JUDGE_MODEL", "").strip()
    if backend == "openai" and not (ourl and omodel):
        print("AI judge skipped: backend openai needs SPEECH_JUDGE_URL and SPEECH_JUDGE_MODEL")
        return 0
    label = MODEL if backend == "claude" else omodel
    focused = args.focus
    findings = (
        (args.out / "findings.md").read_text(encoding="utf-8") if (args.out / "findings.md").exists() else ""
    )

    text = spoken.read_text(encoding="utf-8")
    if focused:
        text = focus(text)
    parts = chunks(text, args.chunk)
    results, stats = [], []
    t0 = time.monotonic()
    try:
        for i, part in enumerate(parts, 1):
            print(f"Asking {label} about part {i} of {len(parts)} ({len(part)} characters) ...", flush=True)
            user = prompt(findings, part, i, len(parts), focused)

            def ask(u: str) -> tuple[dict, dict]:
                return ask_claude(key, u) if backend == "claude" else ask_openai(ourl, okey, omodel, u)

            try:
                res, st = ask(user)
            except ValueError:  # an answer that is not JSON (cut off?): once more, asking for fewer problems
                print("    (no usable answer; asking again for at most 10 problems)", flush=True)
                res, st = ask(user + "\n\nList at most 10 problems, the most important first.")
            st.update(
                part=i,
                characters=len(part),
                verdict=res.get("verdict"),
                problems=len(res.get("problems", [])),
            )
            print("   ", json.dumps(st), flush=True)
            results.append(res)
            stats.append(st)
    except (RuntimeError, ValueError, KeyError) as e:
        print(f"AI judge could not run: {e}")
        (args.out / "judge.md").write_text(f"**AI judge: could not run** ({e})\n", encoding="utf-8")
        return 0

    problems = [p for r in results for p in r.get("problems", [])]
    # FAIL if the automatic checks failed, or the model found a major problem they missed
    auto_failed = findings.lstrip().startswith("**Speech check: FAIL**")
    model_failed = any(p.get("severity") != "minor" for p in problems)
    failed = auto_failed or model_failed
    verdict = {
        "verdict": "FAIL" if failed else "PASS",
        "summary": " ".join(r.get("summary", "") for r in results).strip(),
        "problems": problems,
        "model": label,
        "backend": backend,
        "focused": focused,
        "characters": len(text),
        "seconds": round(time.monotonic() - t0, 1),
        "automatic_checks_failed": auto_failed,
        "model_found_major": model_failed,
        "parts": stats,
    }
    (args.out / "judge.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    major = sum(p.get("severity") != "minor" for p in problems)
    line = f"**AI judge ({label}): {verdict['verdict']}**: {verdict['summary']}"
    if failed:
        line += (
            f"\n\nThe model found {major} major and {len(problems) - major} minor issue(s) beyond the automatic "
            f"checks{' (which also failed)' if auto_failed else ''}; see speech-judge.pdf."
        )
    line += f"\n\n({len(parts)} part(s), {len(text)} characters, {verdict['seconds']:.0f} s)"
    (args.out / "judge.md").write_text(line + "\n", encoding="utf-8")
    print(f"{verdict['verdict']}  ({verdict['seconds']:.0f} s)")
    if not failed:
        return 0
    pdf = write_pdf(args.out, verdict, findings, label)
    if pdf:
        print(f"Why: {pdf}")
    # SPEECH_JUDGE_ADVISORY=true: the model's FAIL is advice (the automatic checks still count)
    if os.environ.get("SPEECH_JUDGE_ADVISORY", "").lower() in ("1", "true", "yes") and not auto_failed:
        print("(advisory: the model's FAIL does not fail the build)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
