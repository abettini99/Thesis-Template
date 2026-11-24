"""Shared helpers for the scripts in tools/ (not run on its own)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the template's main folder
IDENTITY = (1, 0, 0, 1, 0, 0)


def parser(doc: str) -> argparse.ArgumentParser:
    """Command-line parser described by the second paragraph of a script's docstring."""
    return argparse.ArgumentParser(
        description=doc.split("\n\n")[1].strip(), formatter_class=argparse.RawDescriptionHelpFormatter
    )


def run(*cmd) -> str:
    """A command's output. If it fails, says so on stderr (an empty result would read as "nothing found")."""
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        import sys

        msg = (r.stderr.strip().splitlines() or [f"exit code {r.returncode}"])[-1]
        print(f"  (note: {cmd[0]} failed: {msg})", file=sys.stderr)
    return r.stdout


class Report:
    """OK / WARN / FAIL lines with indented details, and the counts for the summary."""

    def __init__(self):
        self.errors = self.warnings = 0

    @staticmethod
    def section(title):
        print(f"\n{title}")

    @staticmethod
    def ok(msg):
        print(f"  OK    {msg}")

    def warn(self, msg, details=()):
        self.warnings += 1
        self._line("WARN", msg, details)

    def fail(self, msg, details=()):
        self.errors += 1
        self._line("FAIL", msg, details)

    @staticmethod
    def _line(kind, msg, details, limit=12):
        details = list(details)
        print(f"  {kind:<4}  {msg}")
        for d in details[:limit]:
            print(f"          {d}")
        if len(details) > limit:
            print(f"          ... and {len(details) - limit} more")


# --- inside a PDF (needs pikepdf) -------------------------------------------------


def mul(a, b):
    """Product of two PDF matrices (a then b)."""
    return [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def operators(stream, resources, ctm=IDENTITY, depth=0):
    """Every operator of a content stream as (op, operands, resources, ctm), forms included (drawn with
    their matrix and resources); ctm follows q, Q and cm."""
    import pikepdf

    if depth > 8:
        return
    stack = []
    for operands, op in pikepdf.parse_content_stream(stream):
        op = str(op)
        if op == "q":
            stack.append(ctm)
        elif op == "Q" and stack:
            ctm = stack.pop()
        elif op == "cm":
            ctm = mul([float(x) for x in operands], ctm)
        elif op == "Do" and resources is not None:
            xo = resources.get("/XObject", {}).get(str(operands[0]))
            if xo is not None and xo.get("/Subtype") == "/Form":
                m = [float(x) for x in xo.get("/Matrix", IDENTITY)]
                yield from operators(xo, xo.get("/Resources", resources), mul(m, ctm), depth + 1)
                continue
        yield op, operands, resources, ctm


def shown_bytes(op, operands) -> bytes | None:
    """The character codes a text-showing operator (Tj, TJ, ', ") shows, else None."""
    import pikepdf

    if op not in ("Tj", "TJ", "'", '"'):
        return None
    items = operands[0] if op == "TJ" else [operands[-1]]
    return b"".join(bytes(x) for x in items if isinstance(x, pikepdf.String))


def glyph_count(font, data: bytes) -> int:
    return len(data) // 2 if font is not None and font.get("/Subtype") == "/Type0" else len(data)


def notdef_count(font, data: bytes) -> int:
    """How many of the codes show the missing glyph (.notdef), which prints as nothing and PDF/A
    forbids: code 0 of a CID font, or a code a simple font's encoding maps to .notdef."""
    import pikepdf

    if font is None:
        return 0
    if font.get("/Subtype") == "/Type0":
        return sum(1 for i in range(0, len(data) - 1, 2) if data[i : i + 2] == b"\0\0")
    enc = font.get("/Encoding")
    if not (isinstance(enc, pikepdf.Dictionary) and "/Differences" in enc):
        return 0
    code, notdef = 0, set()
    for x in enc.Differences:
        if isinstance(x, int):
            code = int(x)
        else:
            if str(x) == "/.notdef":
                notdef.add(code)
            code += 1
    return sum(1 for b in data if b in notdef)


def font_name(font) -> str:
    """A font's name without the subset prefix (ABCDEF+Times-Roman -> Times-Roman)."""
    return str(font.get("/BaseFont", "")).lstrip("/").split("+")[-1]
