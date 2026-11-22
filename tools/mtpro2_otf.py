#!/usr/bin/env python3
"""
mtpro2_otf.py - convert MathTime Professional 2 (Type 1) into OpenType MATH fonts
for LuaLaTeX + unicode-math, plus the companion package mtpro2-otf.sty.

Independent converter: it reads only your MTPro2 files (.pfb outlines, .tfm metrics,
mtpro2.sty and its .fd files) and LaTeX's own fontmath.ltx, amsmath and unicode-math
tables. Upright Latin letters (which MTPro2 takes from Times) come from TeX Gyre Termes.

Layout follows classic TeX exactly: the package restores TeX's glyph boxes, kerns and
per-style parameters, rebuilds MTPro2's TFM fonts as virtual fonts on the OpenType glyphs
for LaTeX's own symbol families, and uses mtpro2.sty's own macros (\\widehat, \\overcbrace,
\\PARENS, \\xl, ...) taken from your mtpro2.sty. --selftest checks the result.

Usage:
    python3 mtpro2_otf.py MTPRO2_DIR OUTPUT_DIR [--weights regular,bold,heavy]
                          [--donor FONT.otf] [--zip]
    python3 mtpro2_otf.py --selftest MTPRO2_DIR [--work DIR] [--options complete,zswash,...]
                          [--scale 0.95]

Output: MTPro2Math.otf (+ -Bold, -Heavy with the Complete set), mtpro2-otf.sty and its
support files mtpro2-otf.lua, -variants.lua, -dims.lua, -tfm.lua, -legacy.tex, -macros.tex,
and mtpro2-otf-manifest.txt listing them (a later run removes only listed files it no longer
writes). Put them in your project, at the top level or in a folder on TEXINPUTS (e.g. Fonts/
via latexmkrc); compile with LuaLaTeX.

In your preamble:   \\usepackage{amsmath}  \\usepackage[options]{mtpro2-otf}
Options: mtpro2.sty's (same names and defaults), scale=<factor> (e.g. 0.95), ntxcal (newtx
calligraphic), textsf (\\mathsf from the text's sans-serif). \\MTPOTFedition and
\\MTPOTFversion tell which set (Complete/Lite) and version are loaded.

Requirements: Python 3.9+, fontTools (pip install fonttools), a TeX Live installation
(kpsewhich, fontmath.ltx, amsmath, unicode-math, tex-gyre). --selftest also needs pdftoppm
and, for its pixel comparison, Pillow; it runs OTS if opentype-sanitizer is installed.

The fonts and the generated support files contain MTPro2 data: for your own use under the
MTPro2 EULA (embedding the fonts in PDFs is fine). Do not redistribute them.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import math
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib import builder as otl
from fontTools.otlLib.builder import buildMathTable
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.cffLib.specializer import commandsToProgram, specializeCommands
from fontTools.misc.psCharStrings import T1OutlineExtractor, T2CharString
from fontTools.pens.transformPen import TransformPen
from fontTools.t1Lib import T1Font
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

UPM = 1000
PACKAGE_DATE = "2026/11/22"
PACKAGE_VERSION = "1.2"
# Fixed font timestamp (mtpro2.sty v2.3, 2009-04-27): identical input -> byte-identical fonts.
BUILD_TIME = int(datetime.datetime(2009, 4, 27, tzinfo=datetime.timezone.utc).timestamp()) + 2082844800


# ======================================================================
# 1. TeX inputs: TFM files and NFSS declarations
# ======================================================================

@dataclass
class TFMChar:
    width: float
    height: float
    depth: float
    italic: float
    tag: int
    remainder: int


@dataclass
class TFM:
    design_size: float
    chars: dict[int, TFMChar]
    params: list[float]                          # params[5] x-height, [22] axis, ...
    kerns: dict[tuple[int, int], float]
    nextlarger: dict[int, int]
    exten: dict[int, tuple[int, int, int, int]]   # top, mid, bot, rep


def read_tfm(path: Path) -> TFM:
    """Parse a TFM file; all dimensions are in units of the design size."""
    d = path.read_bytes()
    lf, lh, bc, ec, nw, nh, nd, ni, nl, nk, ne, np_ = struct.unpack(">12H", d[:24])
    fix = lambda b: struct.unpack(">i", b)[0] / 2**20
    words = lambda off, n: [d[off + 4 * i: off + 4 * i + 4] for i in range(n)]
    off = 24
    header = words(off, lh); off += 4 * lh
    ci = words(off, ec - bc + 1); off += 4 * (ec - bc + 1)
    W = [fix(w) for w in words(off, nw)]; off += 4 * nw
    H = [fix(w) for w in words(off, nh)]; off += 4 * nh
    D = [fix(w) for w in words(off, nd)]; off += 4 * nd
    I = [fix(w) for w in words(off, ni)]; off += 4 * ni
    LK = words(off, nl); off += 4 * nl
    K = [fix(w) for w in words(off, nk)]; off += 4 * nk
    E = words(off, ne); off += 4 * ne
    P = [0.0] + [fix(w) for w in words(off, np_)]
    chars, nextl, exten, kerns = {}, {}, {}, {}
    for i, (wi, hd, it, rem) in enumerate(ci):
        if wi == 0:
            continue
        c, tag = bc + i, it & 3
        chars[c] = TFMChar(W[wi], H[hd >> 4], D[hd & 15], I[it >> 2], tag, rem)
        if tag == 2:
            nextl[c] = rem
        elif tag == 3:
            exten[c] = tuple(E[rem])
    for c, ch in chars.items():                 # lig/kern programs: we only need kerns
        if ch.tag != 1:
            continue
        pc = ch.remainder
        if LK[pc][0] > 128:
            pc = 256 * LK[pc][2] + LK[pc][3]
        while pc < len(LK):
            skip, nxt, op, rem = LK[pc]
            if op >= 128:
                kerns[(c, nxt)] = K[256 * (op - 128) + rem]
            if skip >= 128:
                break
            pc += skip + 1
    return TFM(fix(header[1]), chars, P, kerns, nextl, exten)


def tex_number(tok: str) -> int:
    tok = tok.strip()
    if tok.startswith('"'):
        return int(tok[1:], 16)
    if tok.startswith("'"):
        return int(tok[1:], 8)
    if tok.startswith("`"):
        return ord(tok[-1])
    return int(tok)


KNOWN_FLAGS = {"mtp@full", "mtp@ams", "mtp@greekalpha", "mtp@slops"}


def active_text(src: str, flags: dict[str, bool]) -> str:
    """Drop the inactive branches of top-level conditionals.

    \\ifmtp@... use `flags`; every \\ifx is taken as false (option switches
    like \\ifx\\Gamma s or \\ifx\\mathbb i are off by default); other \\if..
    tokens (inside macro bodies) are kept as-is."""
    out, stack = [], []          # stack entries: (kind, active_before, branch_true)
    active = True
    pos = 0
    tok = re.compile(r"\\newif\\if[A-Za-z@]+|\\if([A-Za-z@]*)|\\else\b|\\fi\b|\\or\b")
    depth = 0                    # brace depth: \ifx in a macro body is not an option switch
    for m in tok.finditer(src):
        seg = src[pos:m.start()]
        depth += brace_balance(seg)
        if active:
            out.append(seg)
        t = m.group(0)
        pos = m.end()
        if t.startswith("\\newif"):
            if active:
                out.append(t)
            continue
        if t == "\\else":
            if stack and stack[-1][0] == "eval":
                kind, before, val = stack[-1]
                active = before and not val
                continue
            if active:
                out.append(t)
            continue
        if t == "\\or":
            if active:
                out.append(t)
            continue
        if t == "\\fi":
            if stack:
                kind, before, val = stack.pop()
                if kind == "eval":
                    active = before
                    continue
            if active:
                out.append(t)
            continue
        name = m.group(1) or ""
        if name in KNOWN_FLAGS or name == "x" and depth == 0 and _toplevel(src, m.start()):
            val = flags.get(name, False) if name != "x" else False
            stack.append(("eval", active, val))
            active = active and val
        else:
            stack.append(("keep", active, True))
            if active:
                out.append(t)
    if active:
        out.append(src[pos:])
    return "".join(out)


def brace_balance(text: str) -> int:
    """Net { minus } in TeX source, ignoring escaped braces and comments."""
    n, i = 0, 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        n += (c == "{") - (c == "}")
        i += 1
    return n


def _toplevel(src: str, pos: int) -> bool:
    line_start = src.rfind("\n", 0, pos) + 1
    return src[line_start:pos].strip() == ""


@dataclass
class Decl:
    kind: str          # symbol | delimiter | accent | radical
    cmd: str           # "\\sum" or a character like "+"
    cls: str
    fam: str
    slot: int
    fam2: str | None = None
    slot2: int | None = None


ARG = r"\s*\{\s*([^{}]*?)\s*\}"


def parse_decls(text: str) -> list[Decl]:
    out = []
    for m in re.finditer(r"\\DeclareMathSymbol\s*" + ARG * 4, text):
        cmd, cls, fam, slot = m.groups()
        out.append(Decl("symbol", cmd, cls, fam, tex_number(slot)))
    for m in re.finditer(r"\\DeclareMathDelimiter\s*" + ARG * 6, text):
        cmd, cls, f1, s1, f2, s2 = m.groups()
        out.append(Decl("delimiter", cmd, cls, f1, tex_number(s1), f2, tex_number(s2)))
    for m in re.finditer(r"\\DeclareMathAccent\s*" + ARG * 4, text):
        cmd, cls, fam, slot = m.groups()
        out.append(Decl("accent", cmd, cls, fam, tex_number(slot)))
    for m in re.finditer(r"\\DeclareMathRadical\s*" + ARG * 5, text):
        cmd, f1, s1, f2, s2 = m.groups()
        out.append(Decl("radical", cmd, "\\mathord", f1, tex_number(s1), f2, tex_number(s2)))
    return out


def parse_fonts(texts: list[str]):
    """Return (symbol font -> {version: (t,s,f)}, alphabet name -> {version: (t,s,f)})."""
    shapes = {}
    for text in texts:
        for m in re.finditer(r"\\DeclareFontShape\s*" + ARG * 5, text):
            enc, fam, ser, shp, spec = m.groups()
            sizes = re.findall(r"<\s*([\d.]*)\s*-\s*([\d.]*)\s*>\s*([A-Za-z0-9]+)", spec)
            if sizes:
                by = {}
                for lo, hi, name in sizes:
                    lo = float(lo) if lo else 0.0
                    by[lo] = name
                ordered = [by[k] for k in sorted(by)]  # small -> large
                trip = (ordered[-1], ordered[-2] if len(ordered) > 1 else ordered[-1], ordered[0])
                shapes[(enc, fam, ser, shp)] = trip
    symfonts = {}
    for text in texts:
        for m in re.finditer(r"\\DeclareSymbolFont\s*" + ARG * 5, text):
            name, enc, fam, ser, shp = m.groups()
            if (enc, fam, ser, shp) in shapes:
                symfonts.setdefault(name, {})["normal"] = shapes[(enc, fam, ser, shp)]
        for m in re.finditer(r"\\SetSymbolFont\s*" + ARG * 6, text):
            name, ver, enc, fam, ser, shp = m.groups()
            if (enc, fam, ser, shp) in shapes:
                symfonts.setdefault(name, {})[ver] = shapes[(enc, fam, ser, shp)]
    return symfonts, shapes


def read_delimiter_defs(text: str) -> dict[str, dict[str, tuple]]:
    """\\curlybraces/\\straightbraces/\\morphedbraces -> {lbrace: (cls, f1, s1, f2, s2)}."""
    out = {}
    for m in re.finditer(r"\\def\\(\w+braces)\{(.*?)\}\s*\n(?=\\def|\\let|\\[A-Za-z])", text, re.S):
        name, body = m.groups()
        d = {}
        for cs, code in re.findall(r"\\def\\(\w+)\{\\delimiter\"([0-9A-F]{7})", body):
            v = int(code, 16)
            d[cs] = ((v >> 24) & 0xF, (v >> 20) & 0xF, (v >> 12) & 0xFF, (v >> 8) & 0xF, v & 0xFF)
        if d:
            out[name] = d
    return out


def read_alt_letters(text: str) -> dict[str, dict[str, int]]:
    """\\MTPsetupScript etc.: {setup: {letter: slot}} from \\let\\altX=\\MTP@X + slot decls."""
    slots = {m.group(1): tex_number(m.group(2)) for m in re.finditer(
        r"\\DeclareMathSymbol\{\\MTP@(\w)\}\{\\mathalpha\}\{letters\}\{([^}]+)\}", text)}
    out = {}
    for m in re.finditer(r"\\newcommand\{\\MTPsetup(\w+)\}\{%?(.*?)\}\n", text, re.S):
        name, body = m.groups()
        out[name] = {x: slots[x] for x in re.findall(r"\\let\\alt(\w)=\\MTP@\w", body) if x in slots}
    return out


def read_wide_accents(text: str) -> dict[str, int]:
    """\\widehat etc. -> slot (family 3 char of \\mathaccent"03xx)."""
    out = {}
    for name in ("widehat", "widetilde", "widecheck", "widearc"):
        m = re.search(r"\\def\\@" + name + r"#1#2\{.*?\\mathaccent\"03([0-9A-F]{2})", text, re.S)
        if m:
            out[name] = int(m.group(1), 16)
    return out


def read_cbrace_slots(text: str) -> dict[str, list[tuple[str, int, float]]]:
    """\\overcbrace/\\undercbrace: (font letter, slot, upper width in em) for every brace
    the macro can pick. The macro chooses by width; the upper bound reproduces that choice."""
    out = {}
    for name in ("overcbrace", "undercbrace"):
        m = re.search(r"\\def\\" + name + r"#1\{(.*?)\\mathop\{", text, re.S)
        if not m:
            continue
        body = m.group(1)
        refs = []
        first = re.search(r"\\ifnum\\pointcount@<(\d+)(.*?)\\else\s*\\ifnum", body, re.S)
        if first:
            limit = int(first.group(1))
            pairs = re.findall(r"\\ifdim\\wd\\z@<(\d+)pt\s*\\def\\thebrace@\{\\hbox\{\\MTEXE@\\char(\d+)\}", first.group(2))
            refs += [("E", int(c), int(pt) / 10) for pt, c in pairs]
            last = re.findall(r"\\MTEXE@\\char(\d+)\}", first.group(2))[-1]
            refs.append(("E", int(last), float(limit)))
        prev = None
        for blk in re.finditer(r"(?:\\ifnum\\pointcount@<(\d+)\s*)?\\advance\\pointcount@(\d+)"
                               r"(?:\s*\\ifnum\\pointcount@>(\d+)\s*\\pointcount@\d+\s*\\fi)?"
                               r"\s*\\def\\thebrace@\{\\hbox\{\\MTEX([AEFG])@", body):
            hi, add, cap, font = blk.groups()
            lo = prev if prev is not None else 4
            add = int(add)
            if hi:
                refs += [(font, pc + add, pc + 1.0) for pc in range(lo, int(hi))]
                prev = int(hi)
            else:
                top = int(cap) if cap else lo + add
                refs += [(font, pc + add, pc + 1.0 if pc + add < top else 1000.0)
                         for pc in range(lo, top - add + 1)]
        out[name] = refs
    return out

def read_unicode_table(path: Path) -> dict[str, tuple[int, str]]:
    out = {}
    for m in re.finditer(r'\\UnicodeMathSymbol\{"([0-9A-F]+)\}\{\\(\w+)\s*\}\{\\(\w+)\}', path.read_text(encoding="utf-8")):
        cp, cmd, cls = m.groups()
        out.setdefault(cmd, (int(cp, 16), cls))
    return out


def font_skewchars(texts: list[str]) -> dict[str, int]:
    """Font file -> \\skewchar (family default, overridden per shape)."""
    famskew, out = {}, {}
    for text in texts:
        for m in re.finditer(r"\\DeclareFontFamily\s*" + ARG * 2 + r"\s*\{([^{}]*)\}", text):
            enc, fam, extra = m.groups()
            s = re.search(r"\\skewchar\\font\s*('?\d+)", extra)
            if s:
                famskew[(enc, fam)] = tex_number(s.group(1))
    for text in texts:
        for m in re.finditer(r"\\DeclareFontShape\s*" + ARG * 5 + r"\s*\{([^{}]*)\}", text):
            enc, fam, ser, shp, spec, extra = m.groups()
            s = re.search(r"\\skewchar\\font\s*('?\d+)", extra)
            skew = tex_number(s.group(1)) if s else famskew.get((enc, fam))
            if skew is None:
                continue
            for name in re.findall(r">\s*([A-Za-z0-9]+)", spec):
                out[name] = skew
    return out


def read_widearc(text: str) -> list[tuple[str, int]]:
    """\\widearc: [(font macro letter, slot)] e.g. [('G',0xB1),('F',0xB1),('E',0xD0),('A',0xBF)]."""
    m = re.search(r"\\def\\widearc#1\{(.*?)\n\\newbox", text, re.S)
    if not m:
        return []
    return [(f, int(s, 16)) for f, s in re.findall(r"\\textfont3=\\MTEX([AEFG])@\s*\$\\mathaccent\"03([0-9A-F]{2})", m.group(1))]


def read_um_aliases(path: Path) -> tuple[dict[str, str], dict[str, int]]:
    """unicode-math legacy aliases (\\le -> leq) and character remaps ('-' -> U+2212)."""
    text = path.read_text(encoding="utf-8")
    al = {}
    for a, b in re.findall(r"\\protected\\def\\(\w+)\s*\{\\(\w+)\}", text):
        al.setdefault(a, b)
    for a, b in re.findall(r"\\cs_set_protected:Npn\s*\\(\w+)\s*\{\s*\\(\w+)\s*\}", text):
        al.setdefault(a, b)
    rm = {c: int(h, 16) for c, h in re.findall(r"\\__um_remap_symbol:nnn\s*\{`\\(.)\}\s*\{\\\w+\}\s*\{\"([0-9A-F]+)\}", text)}
    return al, rm


def read_op_aliases(text: str) -> dict[str, str]:
    """\\let\\slsum\\slsumop, \\gdef\\slsum{\\DOTSB\\slsumop..} -> {slsum: slsumop}."""
    out = {}
    for a, b in re.findall(r"\\let\\(\w+)\\(\w+op)\b", text):
        out.setdefault(a, b)
    for a, b in re.findall(r"\\gdef\\(\w+)\{\\DOTS\w\\(\w+op)", text):
        out.setdefault(a, b)
    return out


def braced(text: str, i: int) -> tuple[str, int]:
    """Contents of the brace group starting at text[i] == '{' and the index after it."""
    depth, j = 0, i
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces")


def read_amsmath_variants(sty: str, amsmath: Path | None) -> dict[str, str]:
    """mtpro2.sty declares some symbols (\\mapsto, \\longrightarrow, ...) only when amsmath
    is not loaded; with amsmath they keep amsmath's composite definitions. Returns
    {command: amsmath's definition} for those commands."""
    m = re.search(r"\\@ifpackageloaded\{amsmath\}\{\}", sty)
    if not m or amsmath is None:
        return {}
    block, _ = braced(sty, m.end())
    cmds = set(re.findall(r"\\DeclareMathSymbol\{\\(\w+)\}", block))
    text, out = amsmath.read_text(encoding="latin-1"), {}
    for d in re.finditer(r"\\renewcommand\{\\(\w+)\}", text):
        if d.group(1) in cmds:
            out[d.group(1)], _ = braced(text, d.end())
    return out


CLASSIC_KERNEL = ("rightarrowfill", "leftarrowfill", "downbracefill", "upbracefill",
                  "overrightarrow", "overleftarrow", "overbrace", "underbrace")
CLASSIC_AMSMATH = ("overrightarrow", "overleftarrow", "overleftrightarrow",
                   "underrightarrow", "underleftarrow", "underleftrightarrow")


def read_classic_defs(text: str, names, ams: bool = False) -> dict[str, str]:
    """LaTeX's / amsmath's definitions of the constructions unicode-math replaces by
    stretchy OpenType glyphs (arrows over formulas, braces): {name: TeX definition}."""
    out = {}
    pat = (r"\\ams@(?:re)?newcommand\{\\(\w+)\}(\[\d\])?" if ams else
           r"\\DeclareRobustCommand\\(\w+)(\[\d\])?")
    for m in re.finditer(pat, text):
        if m.group(1) in names and m.group(1) not in out:
            j = m.end()
            while text[j] in " \n":
                j += 1
            body, _ = braced(text, j)
            out[m.group(1)] = f"\\DeclareRobustCommand\\{m.group(1)}{m.group(2) or ''}{{{body}}}"
    return out


def kpse(name: str) -> Path | None:
    try:
        p = subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip()
        return Path(p) if p else None
    except FileNotFoundError:
        return None


# ======================================================================
# 2. Unicode: which character each LaTeX command stands for
# ======================================================================

GREEK = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa varkappa "
         "lambda mu nu xi omicron pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega "
         "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta varTheta Iota Kappa Lambda Mu Nu Xi Omicron Pi "
         "Rho Sigma Tau Upsilon Phi Chi Psi Omega varbeta vardelta digamma Digamma").split()
ALPHABETS = {  # tag: (uppercase base, lowercase base, digits base, holes in the Unicode block)
    "italic": (0x1D434, 0x1D44E, None, {"h": 0x210E}),
    "bolditalic": (0x1D468, 0x1D482, None, {}),
    "bold": (0x1D400, 0x1D41A, 0x1D7CE, {}),
    "script": (0x1D49C, 0x1D4B6, None, {"B": 0x212C, "E": 0x2130, "F": 0x2131, "H": 0x210B, "I": 0x2110,
                                        "L": 0x2112, "M": 0x2133, "R": 0x211B, "e": 0x212F, "g": 0x210A,
                                        "o": 0x2134}),
    "boldscript": (0x1D4D0, 0x1D4EA, None, {}),
    "frak": (0x1D504, 0x1D51E, None, {"C": 0x212D, "H": 0x210C, "I": 0x2111, "R": 0x211C, "Z": 0x2128}),
    "boldfrak": (0x1D56C, 0x1D586, None, {}),
    "bb": (0x1D538, 0x1D552, 0x1D7D8, {"C": 0x2102, "H": 0x210D, "N": 0x2115, "P": 0x2119, "Q": 0x211A,
                                       "R": 0x211D, "Z": 0x2124}),
}
LATIN_GREEK = {"A": 0x391, "B": 0x392, "E": 0x395, "Z": 0x396, "H": 0x397, "I": 0x399, "K": 0x39A,
               "M": 0x39C, "N": 0x39D, "O": 0x39F, "P": 0x3A1, "T": 0x3A4, "X": 0x3A7, "o": 0x3BF}


def alpha_cp(tag: str, ch: str) -> int | None:
    up, lo, dg, holes = ALPHABETS[tag]
    if ch in holes:
        return holes[ch]
    if "A" <= ch <= "Z":
        return up + ord(ch) - 65
    if "a" <= ch <= "z":
        return lo + ord(ch) - 97
    if dg is not None and "0" <= ch <= "9":
        return dg + ord(ch) - 48
    return None


def gname(cp: int) -> str:
    """Glyph name from which PDF viewers recover the character (uniXXXX / uXXXXX)."""
    return f"uni{cp:04X}" if cp < 0x10000 else f"u{cp:X}"


class Unicode:
    """unicode-math's view: symbol table, legacy aliases (\\le -> \\leq), remaps ('-' -> U+2212)."""

    def __init__(self, table: dict, aliases: dict, remaps: dict):
        self.table, self.aliases, self.remaps = table, aliases, remaps

    def get(self, name: str) -> int | None:
        return self.table[name][0] if name in self.table else None

    def for_command(self, cmd: str, slot: int = 0, fam: str = "symbols") -> int | None:
        if len(cmd) == 1:
            return self.remaps.get(cmd, ord(cmd))
        name = cmd.lstrip("\\")
        if name.startswith("MTP@"):
            return None
        if name not in self.table and self.aliases.get(name) in self.table:
            name = self.aliases[name]
        if name not in self.table and name.endswith("op") and name[:-2] in self.table:
            name = name[:-2]                                   # \intop -> \int
        up_prefixed = name.startswith("up") and name[2:] in GREEK
        base = name[2:] if up_prefixed else name
        if base in GREEK:
            upright = up_prefixed or (base[0].isupper() and slot >= 0x7F) or fam != "letters"
            for key in (("mup" if upright else "mit") + base, "mup" + base, base):
                if key in self.table:
                    return self.table[key][0]
            return None
        return self.get(name)

    def base_for(self, name: str) -> int | None:
        """Base character of an MTPro2-only variant (\\varsubsetneq -> U+228A); copy-paste only."""
        stem = re.sub(r"op$", "", name)
        cands = [name, stem]
        for pre in ("var", "sl", "up", "thick", "short", "small", "big"):
            cands += [n[len(pre):] for n in (name, stem) if n.startswith(pre)]
        cands += [name.replace("vert", "", 1), re.sub(r"slant$", "", name), re.sub(r"char$", "", name)]
        for c in cands:
            if c in self.table:
                return self.table[c][0]
            if self.aliases.get(c) in self.table:
                return self.table[self.aliases[c]][0]
        return None


# ======================================================================
# 3. Inputs, read once and shared by all weights
# ======================================================================

@dataclass
class Inputs:
    files: dict[str, Path]
    sty: str                 # mtpro2.sty as is
    act: str                 # mtpro2.sty with the default option branches only
    fds: list[str]
    decls: list              # effective math declarations (fontmath.ltx + mtpro2.sty)
    symfonts: dict           # symbol font -> {version: (text, script, scriptscript) fonts}
    skew: dict[str, int]     # font -> \skewchar
    uni: Unicode
    complete: bool
    amsmath_defs: dict[str, str]
    classic: dict[str, dict[str, str]]       # "kernel"/"amsmath" -> {name: definition}

    @classmethod
    def load(cls, folder: Path) -> "Inputs":
        files = {p.name.lower(): p for p in folder.rglob("*") if p.is_file()}
        if "mtpro2.sty" not in files or "mt2mit.pfb" not in files:
            sys.exit(f"error: no MTPro2 files (mtpro2.sty, mt2mit.pfb, ...) under {folder}")
        fm, um, uml = kpse("fontmath.ltx"), kpse("unicode-math-table.tex"), kpse("unicode-math-luatex.sty")
        if not (fm and um and uml):
            sys.exit("error: fontmath.ltx / unicode-math not found - a TeX Live installation is needed")
        sty = files["mtpro2.sty"].read_text(encoding="latin-1")
        fds = [files[n].read_text(encoding="latin-1") for n in sorted(files) if n.endswith(".fd")]
        complete = "mt2bmit.pfb" in files and "mt2bmit.tfm" in files
        flags = {"mtp@full": complete, "mtp@ams": complete, "mtp@greekalpha": True, "mtp@slops": False}
        act = active_text(sty, flags)
        decls = parse_decls(active_text(fm.read_text(encoding="latin-1"), {})) + parse_decls(act)
        last = {(d.kind, d.cmd): i for i, d in enumerate(decls)}   # a later declaration wins
        decls = [d for i, d in enumerate(decls) if i in set(last.values())]
        symfonts, _ = parse_fonts([act] + fds)
        aliases, remaps = read_um_aliases(uml)
        return cls(files, sty, act, fds, decls, symfonts, font_skewchars([act] + fds),
                   Unicode(read_unicode_table(um), aliases, remaps), complete,
                   read_amsmath_variants(sty, kpse("amsmath.sty")),
                   {"kernel": read_classic_defs(fm.read_text(encoding="latin-1"), CLASSIC_KERNEL),
                    "amsmath": read_classic_defs(kpse("amsmath.sty").read_text(encoding="latin-1"),
                                                 CLASSIC_AMSMATH, ams=True) if kpse("amsmath.sty") else {}})


class Source:
    """Lazy access to the MTPro2 .tfm/.pfb files."""

    def __init__(self, files: dict[str, Path]):
        self.files, self._tfm, self._t1, self._rec = files, {}, {}, {}

    def has(self, name: str) -> bool:
        return f"{name}.pfb" in self.files and f"{name}.tfm" in self.files

    def tfm(self, name: str) -> TFM:
        if name not in self._tfm:
            self._tfm[name] = read_tfm(self.files[f"{name}.tfm"])
        return self._tfm[name]

    def _load(self, name: str):
        if name not in self._t1:
            f = T1Font(str(self.files[f"{name}.pfb"]))
            f.parse()
            self._t1[name] = (f.getGlyphSet(), f.font["Encoding"], f.font)
        return self._t1[name][:2]

    def private(self, name: str) -> dict:
        self._load(name)
        return self._t1[name][2]["Private"]

    def outline(self, name: str, slot: int) -> RecordingPen:
        """The glyph's outline, decoded once (glyphs are redrawn several times)."""
        key = (name, slot)
        if key not in self._rec:
            gs, enc = self._load(name)
            self._rec[key] = rec = RecordingPen()
            cs = gs[enc[slot]]
            ex = HintedT1Extractor(rec, self._t1[name][2]["Private"].get("Subrs", []))
            ex.execute(cs)
        return self._rec[key]

    def glyph_ok(self, name: str, slot: int) -> bool:
        if not self.has(name) or slot not in self.tfm(name).chars:
            return False
        gs, enc = self._load(name)
        return enc[slot] != ".notdef" and enc[slot] in gs


# ======================================================================
# 4. Glyphs
# ======================================================================

class HintedT1Extractor(T1OutlineExtractor):
    """Type 1 outline extractor that also records the stem hints: ("hintset", (stems,))
    entries in the RecordingPen, before the first path element they apply to. Hint
    replacement (othersubr 3, then a subroutine with the new stems) starts a new set."""

    def reset(self):
        super().reset()
        self.hset, self.newset, self.dirty = [], False, False

    def _stem(self, kind, pos, w):
        if self.newset:
            self.hset, self.newset = [], False
        self.hset.append((kind, pos, w))
        self.dirty = True

    def op_hstem(self, index):
        a = self.popall()
        if len(a) >= 2:
            self._stem("h", a[-2], a[-1])

    def op_vstem(self, index):
        a = self.popall()
        if len(a) >= 2:
            self._stem("v", a[-2] + self.sbx, a[-1])

    def op_hstem3(self, index):
        a = self.popall()
        for i in range(0, len(a) - 1, 2):
            self._stem("h", a[i], a[i + 1])

    def op_vstem3(self, index):
        a = self.popall()
        for i in range(0, len(a) - 1, 2):
            self._stem("v", a[i] + self.sbx, a[i + 1])

    def op_callothersubr(self, index):
        if len(self.operandStack) >= 2 and self.operandStack[-1] == 3:
            self.newset = True                      # hint replacement
        super().op_callothersubr(index)

    def _flush(self):
        if self.dirty:
            self.pen.value.append(("hintset", (list(self.hset),)))
            self.dirty = False

    def rMoveTo(self, point):
        self._flush()
        super().rMoveTo(point)

    def rLineTo(self, point):
        self._flush()
        super().rLineTo(point)

    def rCurveTo(self, pt1, pt2, pt3):
        self._flush()
        super().rCurveTo(pt1, pt2, pt3)


def hinted_charstring(t2: T2CharStringPen, sets: list) -> T2CharString:
    """The charstring of a pen whose commands contain ("_hints", n) markers (n: index into
    sets, each a list of (kind, position, width) stems): all stems declared once, and a
    hintmask wherever the active set changes (CFF's form of Type 1 hint replacement)."""
    def edge(st):                                   # (ghost hints: width -20 or -21)
        k, pos, w = st
        return (pos, pos) if w in (-20, -21) else (min(pos, pos + w), max(pos, pos + w))
    clean = []
    for hs in sets:                                 # each set: no overlaps, sane values
        keep = {"h": [], "v": []}
        # (MTPro2 writes many stems top edge first, with a negative width; CFF wants the
        # lower edge first, a negative width meaning a ghost hint, -20 or -21)
        hs = [(k, pos + w, -w) if w < 0 and w not in (-20, -21) else (k, pos, w) for k, pos, w in hs]
        for st in hs:
            lo, hi = edge(st)
            if max(abs(lo), abs(hi)) < 16000 and all(hi < a or lo > b for a, b in
                                                     (edge(t) for t in keep[st[0]])):
                keep[st[0]].append(st)
        clean.append(keep["h"] + keep["v"])
    stems = {k: sorted({st for hs in clean for st in hs if st[0] == k}, key=lambda t: (edge(t), t))
             for k in "hv"}
    cmds = []
    for k in "hv":
        args, last = [], 0
        for _, pos, w in stems[k]:
            args += [pos - last, w]
            last = pos + w
        if args:
            cmds.append((k + "stemhm" if len(clean) > 1 else k + "stem", args))
    order = stems["h"] + stems["v"]
    for op, args in t2._commands:
        if op == "_hints":
            if len(clean) > 1 and order:
                on, mask = set(clean[args]), bytearray((len(order) + 7) // 8)
                for i, st in enumerate(order):
                    if st in on:
                        mask[i // 8] |= 0x80 >> (i % 8)
                cmds += [("hintmask", []), ("", [bytes(mask)])]
            continue
        cmds.append((op, args))
    cmds = specializeCommands(cmds, generalizeFirst=False, maxstack=48)
    program = commandsToProgram(cmds)
    program.insert(0, round(t2._width))
    program.append("endchar")
    return T2CharString(program=program)


class ShortPen:
    """Splits segments so that no coordinate difference exceeds what a CFF charstring can
    hold as an integer (32767 units; the 8x extension glyphs are larger than that)."""
    LIMIT = 30000

    def __init__(self, pen):
        self.pen, self.cur = pen, (0, 0)

    def moveTo(self, p):
        self.pen.moveTo(p); self.cur = p

    def lineTo(self, p):
        (x0, y0), n = self.cur, 1
        while max(abs(p[0] - x0), abs(p[1] - y0)) / n > self.LIMIT:
            n += 1
        for i in range(1, n + 1):
            self.pen.lineTo((x0 + (p[0] - x0) * i / n, y0 + (p[1] - y0) * i / n))
        self.cur = p

    def curveTo(self, *pts):
        p0, p1, p2, p3 = self.cur, *pts
        if max(abs(b - a) for q, r in ((p0, p1), (p1, p2), (p2, p3)) for a, b in zip(q, r)) > self.LIMIT:
            mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            a, b, c = mid(p0, p1), mid(p1, p2), mid(p2, p3)
            d, e = mid(a, b), mid(b, c)
            f = mid(d, e)
            self.curveTo(a, d, f)
            self.curveTo(e, c, p3)
            return
        self.pen.curveTo(p1, p2, p3); self.cur = p3

    def qCurveTo(self, *pts):
        self.pen.qCurveTo(*pts); self.cur = pts[-1]

    def closePath(self):
        self.pen.closePath()

    def endPath(self):
        self.pen.endPath()

    def addComponent(self, *a):
        self.pen.addComponent(*a)


@dataclass(frozen=True)
class Ref:
    font: str
    slot: int
    scale: int = 1           # the extension fonts are used at 2x, 4x and 8x size


@dataclass
class Glyph:
    name: str
    ref: Ref | None          # None: composed or donor glyph
    width: float = 0         # advance (TFM width, adjusted by the stages below)
    height: float = 0        # TeX box (TFM), moved with dy
    depth: float = 0
    italic: float = 0        # italic correction left for the MATH table
    accent: float | None = None
    mkern: float = 0         # bottom-right math kern (TeX's subscript tuck)
    dy: float = 0            # vertical shift baked into the outline
    tex_box: bool = False    # bounding box extended to the TFM box
    shifted: bool = False
    widened: bool = False
    charstring: object = None
    bounds: tuple | None = None
    parts: list = field(default_factory=list)   # composed glyphs: (glyph, dx, dy)


# ======================================================================
# 5. Building one weight
# ======================================================================

# Unicode's bracket pieces, for the glyphs of assembled delimiters
_P = lambda top, rep, bot, mid=None: {k: v for k, v in (("top", top), ("rep", rep), ("bot", bot),
                                                        ("mid", mid)) if v}
PIECES = {0x28: _P(0x239B, 0x239C, 0x239D), 0x29: _P(0x239E, 0x239F, 0x23A0),
          0x5B: _P(0x23A1, 0x23A2, 0x23A3), 0x5D: _P(0x23A4, 0x23A5, 0x23A6),
          0x7B: _P(0x23A7, 0x23AA, 0x23A9, 0x23A8), 0x7D: _P(0x23AB, 0x23AA, 0x23AD, 0x23AC),
          0x2308: _P(0x23A1, 0x23A2, None), 0x2309: _P(0x23A4, 0x23A5, None),
          0x230A: _P(None, 0x23A2, 0x23A3), 0x230B: _P(None, 0x23A5, 0x23A6),
          0x7C: _P(None, 0x23D0, None), 0x2016: _P(None, 0x2016, None),
          0x222B: _P(0x2320, 0x23AE, 0x2321), 0x221A: _P(None, 0x23D0, 0x23B7),
          0x2191: _P(0x2191, 0x23D0, None), 0x2193: _P(None, 0x23D0, 0x2193),
          0x2195: _P(0x2191, 0x23D0, 0x2193), 0x21D1: _P(0x21D1, 0x2016, None),
          0x21D3: _P(None, 0x2016, 0x21D3), 0x21D5: _P(0x21D1, 0x2016, 0x21D3)}
LEGACY_EXTRA = {"mt2exa": 1, "mt2exe": 2, "mt2exf": 4, "mt2exg": 8, "mt2xl": 1, "mt2xxxl": 2}
EXT_FONTS = {"A": ("exa", 1), "E": ("exe", 2), "F": ("exf", 4), "G": ("exg", 8)}
CLASSES = {"\\mathord": 0, "\\mathalpha": 0, "\\mathop": 1, "\\mathbin": 2, "\\mathrel": 3,
           "\\mathopen": 4, "\\mathclose": 5, "\\mathpunct": 6}


class MathFontBuild:
    """Collects glyphs, code points, variants and TeX data for one weight; see build()."""

    def __init__(self, inp: Inputs, src: Source, weight: str):
        self.inp, self.src, self.weight = inp, src, weight
        self.glyphs: dict[str, Glyph] = {}
        self.by_ref: dict[Ref, str] = {}
        self.cmap: dict[int, str] = {}
        self.ssty: dict[str, list[str]] = {}             # glyph -> [script, scriptscript]
        self.vvar: dict[str, list[str]] = {}             # vertical size variants
        self.hvar: dict[str, list[str]] = {}             # horizontal size variants
        self.vasm: dict[str, list] = {}                  # vertical assemblies
        self.commands: dict[str, tuple[str, str]] = {}   # mtpro2.sty command -> (class, glyph)
        self.cmd_src: dict[str, tuple[str, int]] = {}
        self.glyph_cls: dict[str, str] = {}
        self.forced: set[str] = set()                    # commands mtpro2.sty deliberately replaces
        self.variants: dict[str, dict[str, str]] = {}    # per-use sets for the package
        self.kerns: dict[tuple[str, str], int] = {}
        self.limits: dict[str, str] = {}                 # operator -> its twin for \\limits
        self.tex_params: dict[str, int] = {}
        self.fallback: dict[str, str] = {}               # weight font -> regular font
        self.from_fallback: set[str] = set()
        for vers in inp.symfonts.values():
            base = vers.get("normal")
            for v, trip in vers.items():
                if base and v != "normal":
                    self.fallback.update({a: b for a, b in zip(trip, base) if a != b})

    # ---------------------------------------------------------------- helpers
    def fam(self, fam: str):
        """(text, script, scriptscript) fonts of a symbol font in this weight."""
        v = self.inp.symfonts.get(fam, {})
        return v.get(self.weight, v.get("normal"))      # (heavy letters: the normal ones, as in TeX)

    def trip(self, a, b, c):
        return (a, b, c) if self.src.has(a) else None

    def draw(self, g: Glyph):
        """(Re)draw a glyph's outline with its current width, shift and TeX box."""
        t2, bp = T2CharStringPen(min(round(g.width), 32767), None), BoundsPen(None)
        pen = ShortPen(t2)
        if g.ref is not None:
            sources = [(g.ref, 0, g.dy)]
        else:
            sources = [(self.glyphs[n].ref, dx, dy + self.glyphs[n].dy) for n, dx, dy in g.parts]
        sets = []                                   # hint sets (single-source glyphs only)
        for ref, dx, dy in sources:
            o, sc = self.src.outline(ref.font, ref.slot), ref.scale
            tp, tb = TransformPen(pen, (sc, 0, 0, sc, dx, dy)), TransformPen(bp, (sc, 0, 0, sc, dx, dy))
            for op, args in o.value:
                if op == "hintset":
                    if g.ref is not None:           # scaled and shifted with the outline
                        hs = [(k, pos + w, -w) if w < 0 and w not in (-20, -21) else (k, pos, w)
                              for k, pos, w in args[0]]     # (lower edge first, see below)
                        sets.append([(k, round(pos * sc + (dy if k == "h" else dx)),
                                      w if w in (-20, -21) else round(w * sc)) for k, pos, w in hs])
                        t2._commands.append(("_hints", len(sets) - 1))
                    continue
                getattr(tp, op)(*args)
                getattr(tb, op)(*args)
        g.bounds = bp.bounds
        if g.tex_box and g.bounds:              # zero-area contours at TeX's box (invisible)
            x = round(g.bounds[0])
            lo, hi = g.bounds[1], g.bounds[3]
            for y in (g.height, -g.depth):
                if y > hi + 0.5 or y < lo - 0.5:
                    pen.moveTo((x, round(y))); pen.lineTo((x + 1, round(y))); pen.closePath()
                    lo, hi = min(lo, round(y)), max(hi, round(y))
            g.bounds = (g.bounds[0], lo, g.bounds[2], hi)
        g.charstring = hinted_charstring(t2, sets) if sets else t2.getCharString()

    def add(self, ref: Ref, name: str, dup: bool = False) -> str | None:
        """Glyph for a source slot (shared unless dup); falls back to the regular weight."""
        if ref in self.by_ref and not dup:
            return self.by_ref[ref]
        if not self.src.glyph_ok(ref.font, ref.slot):
            fb = self.fallback.get(ref.font)
            if fb and self.src.glyph_ok(fb, ref.slot):
                self.by_ref[ref] = self.add(Ref(fb, ref.slot, ref.scale), name)
                self.from_fallback.add(self.by_ref[ref])    # (no glyph of this weight)
                return self.by_ref[ref]
            return None
        name = base = re.sub(r"[^A-Za-z0-9._]", "_", name)[:60]
        k = 1
        while name in self.glyphs:
            name, k = f"{base}_{k}", k + 1
        t, s = self.src.tfm(ref.font).chars[ref.slot], ref.scale * UPM
        g = Glyph(name, ref, t.width * s, t.height * s, t.depth * s, t.italic * s)
        skew = self.inp.skew.get(ref.font)
        kern = self.src.tfm(ref.font).kerns.get((ref.slot, skew)) if skew is not None else None
        if kern is not None:            # TeX centres accents over width + italic correction
            g.accent = (g.width + g.italic) / 2 + kern * s
        self.draw(g)
        self.glyphs[name] = g
        if not dup or ref not in self.by_ref:
            self.by_ref[ref] = name
        return name

    def add_sized(self, fonts, slot: int, name: str, scale: int = 1, dup: bool = False) -> str | None:
        """Text-size glyph plus its .ssty1/.ssty2 optical sizes from the script fonts."""
        if not fonts:
            return None
        g = self.add(Ref(fonts[0], slot, scale), name, dup)
        if g and g not in self.ssty and fonts[1] != fonts[0]:
            alts = []
            for i, f in enumerate(fonts[1:], 1):
                a = self.add(Ref(f, slot, scale), f"{g}.ssty{i}")
                alts.append(a or (alts[-1] if alts else g))
            self.ssty[g] = alts
        return g

    def compose(self, name: str, parts: list[tuple[str, float, float]], width: float) -> str | None:
        """New glyph drawn from existing glyphs at offsets (dx, dy)."""
        if any(p[0] not in self.glyphs for p in parts):
            return None
        g = Glyph(name, None, width, parts=parts)
        self.draw(g)
        if g.bounds:
            g.height, g.depth = g.bounds[3], -g.bounds[1]
        self.glyphs[name] = g
        return name

    def shift(self, name: str, dy: float):
        """Move a glyph vertically (TeX's run-time centring and placement, baked in)."""
        g = self.glyphs[name]
        if g.ref is None or g.shifted or abs(dy) < 0.5:
            return
        g.dy, g.height, g.depth, g.shifted = g.dy + dy, g.height + dy, g.depth - dy, True
        self.draw(g)

    def widen(self, name: str, extra: float):
        g = self.glyphs[name]
        g.width, g.widened = g.width + extra, True
        self.draw(g)

    def set_cmap(self, cp: int, g: str | None, force: bool = False):
        if g and (force or cp not in self.cmap):
            self.cmap[cp] = g

    def chain(self, font: str, slot: int, scale: int = 1):
        """NEXTLARGER chain from slot -> (Refs, extensible recipe or None)."""
        out, seen, tfm = [], set(), self.src.tfm(font)
        while slot in tfm.chars and slot not in seen:
            seen.add(slot)
            out.append(Ref(font, slot, scale))
            if slot in tfm.nextlarger:
                slot = tfm.nextlarger[slot]
            elif slot in tfm.exten:
                return out, (font, tfm.exten[slot], scale)
            else:
                break
        return out, None

    def ops(self) -> set[str]:
        return {g for cls, g in self.commands.values() if cls == "\\mathop"}

    # ---------------------------------------------------------------- stages
    def build(self) -> "MathFontBuild":
        self.latin_letters()
        self.symbols()
        self.greek_and_composites()
        self.large_operators()
        self.delimiters()
        self.accents()
        self.braces()
        self.centre_and_widen()
        self.alphabets()
        self.alternates()
        self.legacy_glyphs()
        self.tex_letter_boxes()
        self.tex_kerns()
        self.tex_parameters()
        self.tex_boxes()
        return self

    def latin_letters(self):
        letters = self.fam("letters")
        for c in list(range(65, 91)) + list(range(97, 123)):
            cp = alpha_cp("italic", chr(c))
            self.set_cmap(cp, self.add_sized(letters, c, gname(cp)))

    def symbols(self):
        """Every \\DeclareMathSymbol; MTPro2-only symbols are named after their base character."""
        uni = self.inp.uni
        # \\let\\nleq=\\notleq: the alias may be the name unicode-math knows
        lets: dict[str, list[str]] = {}
        for a, b in re.findall(r"\\let\\(\w+)\s*=?\s*\\(\w+)", self.inp.act):
            lets.setdefault(b, []).append(a)
        for d in self.inp.decls:
            if d.kind != "symbol" or d.fam == "operators" or not self.fam(d.fam):
                continue
            if d.cmd.startswith("\\MTP@") or d.cmd == "\\mtp@z" or (len(d.cmd) == 1 and d.cmd.isalpha()):
                continue
            cmd = d.cmd.lstrip("\\")
            cp = uni.for_command(d.cmd, d.slot, d.fam) or next(
                (c for c in (uni.for_command("\\" + a) for a in lets.get(cmd, [])) if c), None)
            if d.cmd == "\\mtp@@z":                       # zswash: swash z, copies as z
                name = gname(alpha_cp("italic", "z")) + ".swash"
            elif cp:
                name = gname(cp)
            else:
                bcp = uni.base_for(cmd)
                name = (gname(bcp) + "." if bcp else "mtp.") + cmd
            g = self.add_sized(self.fam(d.fam), d.slot, name)
            if not g:
                continue
            if cp:
                self.set_cmap(cp, g, force=True)
            self.glyph_cls[g] = d.cls
            if len(d.cmd) > 1:
                self.commands[cmd], self.cmd_src[cmd] = (d.cls, g), (d.fam, d.slot)
                for a in lets.get(cmd, []):
                    if a not in self.commands and a.isalpha():
                        self.commands[a], self.cmd_src[a] = (d.cls, g), (d.fam, d.slot)
        for a, b in read_op_aliases(self.inp.sty).items():   # \slsum -> \slsumop
            if b in self.commands and a not in self.commands:
                self.commands[a], self.cmd_src[a] = self.commands[b], self.cmd_src[b]
        self.forced = set(re.findall(r"\\let\\(\w+)\\@undefined[^\n]*\n\\DeclareMathSymbol\{\\\1\}",
                                     self.inp.act))

    def greek_and_composites(self):
        uni, letters = self.inp.uni, self.fam("letters")
        m = re.search(r"\\ifx\\Gamma s(.*?)\\else", self.inp.sty, re.S)   # italic capital Greek
        if m:
            for d in parse_decls(m.group(1)):
                cp = uni.get("mit" + d.cmd.lstrip("\\"))
                if cp:
                    self.set_cmap(cp, self.add_sized(letters, d.slot, gname(cp)))
        # dot sequences, composed like LaTeX's \cdots, \ldots, \vdots, \ddots
        thin = UPM / 6
        cd, ld = self.cmap.get(0x22C5), self.commands.get("ldotp", (None, None))[1]
        if cd:
            g = self.glyphs[cd]
            w, ax = g.width, g.height - (g.height + g.depth) / 2
            self.set_cmap(0x22EF, self.compose(gname(0x22EF), [(cd, i * (w + thin), 0) for i in range(3)],
                                               3 * w + 2 * thin))
            self.set_cmap(0x22EE, self.compose(gname(0x22EE), [(cd, 0, 400 * i + 60 - ax) for i in range(3)], w))
            self.set_cmap(0x22F1, self.compose(gname(0x22F1), [(cd, thin / 6 + i * (w + thin / 3),
                                                                700 - 300 * i - ax) for i in range(3)], 3 * w + thin))
        if ld:
            w = self.glyphs[ld].width
            self.set_cmap(0x2026, self.compose(gname(0x2026), [(ld, i * (w + thin), 0) for i in range(3)],
                                               3 * w + 2 * thin))
        # Greek letters that look like Latin ones (unicode-math needs the whole range)
        for lat, gr in LATIN_GREEK.items():
            it_gr = uni.get("mit" + (unicodedata.name(chr(gr)).split()[-1].capitalize() if lat.isupper()
                                     else "omicron"))
            if it_gr:
                self.set_cmap(it_gr, self.cmap.get(alpha_cp("italic", lat)))
        for up, it in ((0x2202, 0x1D715), (0x2207, 0x1D6FB)):   # italic partial/nabla code points
            self.set_cmap(it, self.cmap.get(up))
        pr = self.cmap.get(0x2032)                  # '' and ''' as TeX sets them: primes side by side
        if pr:
            for cp, k in ((0x2033, 2), (0x2034, 3), (0x2057, 4)):
                parts = lambda n: [(n, i * self.glyphs[n].width, 0) for i in range(k)]
                g = self.compose(gname(cp), parts(pr), k * self.glyphs[pr].width)
                if g:
                    self.set_cmap(cp, g, force=True)
                    alts = [self.compose(f"{g}.ssty{j}", parts(a), k * self.glyphs[a].width)
                            for j, a in enumerate(self.ssty.get(pr, []), 1)]
                    if alts and all(alts):
                        self.ssty[g] = alts

    def large_operators(self):
        """Text -> display NEXTLARGER chains (\\xl..\\XXXL come with mtpro2.sty's macros)."""
        for d in self.inp.decls:
            if d.kind == "symbol" and d.cls == "\\mathop" and d.fam == "largesymbols":
                root = self.commands.get(d.cmd.lstrip("\\"), (None, None))[1]
                if root:
                    refs, _ = self.chain(self.fam(d.fam)[0], d.slot)
                    self.vvar[root] = [v for v in (self.add(r, f"{root}.v{i}") for i, r in enumerate(refs)) if v]

    def delimiter(self, root_name: str, small, large, override=None, dup=False) -> str | None:
        """Small size, NEXTLARGER chain and extensible recipe of one delimiter."""
        g = self.add_sized(self.fam(small[0]), small[1], root_name, dup=dup) \
            if small and self.fam(small[0]) else None
        fonts = self.fam(large[0])
        if not fonts:
            return g
        refs, ext = self.chain(fonts[0], large[1]) if override is None else override(fonts[0])
        if ext and len(refs) > 1:       # TeX never sets the extensible character itself
            refs = refs[:-1]
        names = [n for n in (self.add(r, f"{g or root_name}.v{i}", dup) for i, r in enumerate(refs)) if n]
        g = g or (names[0] if names else None)
        if not g:
            return None
        self.vvar[g] = [g] + [n for n in names if n != g]
        if ext:
            font, (top, mid, bot, rep), scale = ext
            tf = self.src.tfm(font)

            m = re.match(r"uni([0-9A-F]{4})", root_name)
            roles = PIECES.get(int(m.group(1), 16), {}) if m else {}

            def piece(slot, role):
                # pieces are named after Unicode's bracket pieces (copy-paste: a tall '('
                # copies as its pieces, not as several '(')
                ch = tf.chars[slot]
                name = f"{gname(roles[role])}.{root_name}" if role in roles else f"{g}.p{slot}"
                return (self.add(Ref(font, slot, scale), name), int(role == "rep"),
                        (ch.height + ch.depth) * UPM * scale)
            rp = piece(rep, "rep")
            if not (top or mid or bot):
                parts = [(rp[0], 0, rp[2]), rp]          # OpenType needs one fixed part
            else:
                parts = ([piece(bot, "bot")] if bot else []) + [rp] + \
                        ([piece(mid, "mid"), rp] if mid else []) + ([piece(top, "top")] if top else [])
            self.vasm[g] = parts
        return g

    def delimiters(self):
        uni = self.inp.uni
        symchars = {d.cmd: (d.fam, d.slot) for d in self.inp.decls if d.kind == "symbol" and len(d.cmd) == 1}
        for d in self.inp.decls:
            # (< > as relations are other glyphs than the delimiters; / is the same glyph)
            if d.kind == "delimiter" and symchars.get(d.cmd, (d.fam, d.slot)) == (d.fam, d.slot):
                cp = uni.for_command(d.cmd, d.slot, d.fam)
                small = (d.fam, d.slot) if d.slot or d.fam != "largesymbols" else None
                g = self.delimiter(gname(cp) if cp else "mtp." + d.cmd.lstrip("\\"), small, (d.fam2, d.slot2))
                if g and cp:
                    self.set_cmap(cp, g, force=True)
            elif d.kind == "radical":
                self.set_cmap(0x221A, self.delimiter(gname(0x221A), (d.fam, d.slot), (d.fam2, d.slot2)), True)
        fam_names = {1: "letters", 2: "symbols", 3: "largesymbols"}

        def morphed_fix(cs, curly_large):
            """MTPro2's TFM chains the morphed braces wrongly (182 has no successor, 183 runs
            through the even slots). Intended: even slots for {, odd for }."""
            def f(font):
                tfm = self.src.tfm(font)
                slots = [k for k in range(182 if cs == "lbrace" else 183, 190, 2) if k in tfm.chars]
                return [Ref(font, k) for k in slots], self.chain(font, curly_large)[1]
            return f
        styles = read_delimiter_defs(self.inp.act)
        curly = styles.get("curlybraces", {})
        for style, defs in styles.items():
            tag = style.replace("braces", "")
            for cs, (cls, f1, s1, f2, s2) in defs.items():
                cp = 0x7B if cs == "lbrace" else 0x7D
                fix = morphed_fix(cs, curly[cs][4]) if tag == "morphed" and cs in curly else None
                g = self.delimiter(gname(cp) if tag == "curly" else f"{gname(cp)}.{tag}",
                                   (fam_names[f1], s1), (fam_names[f2], s2), fix, dup=tag != "curly")
                if g:
                    if tag == "curly":
                        self.set_cmap(cp, g, force=True)
                    self.variants.setdefault("delim:" + tag, {})[cs] = g

    def accents(self):
        """Fixed accents + wide sizes from the extension fonts (1x, 2x, 4x, 8x); \\widearc."""
        wide, uni = read_wide_accents(self.inp.sty), self.inp.uni
        pair = {"hat": "widehat", "tilde": "widetilde", "check": "widecheck"}
        names = ("hat", "tilde", "check", "bar", "breve", "acute", "grave", "dot", "ddot", "vec", "mathring")
        for d in self.inp.decls:
            if d.kind != "accent" or d.cmd.lstrip("\\") not in names:
                continue
            cp = uni.for_command(d.cmd, d.slot, d.fam)
            fonts = self.fam(d.fam)
            g = cp and self.add_sized(fonts, d.slot, gname(cp))
            if not g:
                continue
            self.set_cmap(cp, g, force=True)
            refs, _ = self.chain(fonts[0], d.slot)
            hv = [g] + [self.add(r, f"{g}.h{i}") for i, r in enumerate(refs[1:], 1)]
            w = pair.get(d.cmd.lstrip("\\"))
            for letter in ("AEFG" if w in wide else ""):
                fname, scale = EXT_FONTS[letter]
                font = self.fam("largesymbols")[0].replace("exa", fname) if letter == "A" else "mt2" + fname
                if self.src.has(font):
                    refs, _ = self.chain(font, wide[w], scale)
                    hv += [self.add(r, f"{g}.{fname}{r.slot}") for r in refs]
            hv = sorted(dict.fromkeys(h for h in hv if h), key=lambda n: self.glyphs[n].width)
            for h in hv:
                self.glyphs[h].accent = self.glyphs[h].width / 2
            self.hvar[g] = hv
        # mtpro2.sty's other accents (\\dotup .. \\ddddotup, \\what, \\wwtilde, ...): no
        # code point of their own; set by name, with the TFM's larger sizes as variants
        for d in self.inp.decls:
            name = d.cmd.lstrip("\\")
            if d.kind != "accent" or name in names or "@" in name or not name.isalpha():
                continue
            fonts = self.fam(d.fam)
            g = self.add_sized(fonts, d.slot, "mtp.acc." + name)
            if not g:
                continue
            refs, _ = self.chain(fonts[0], d.slot)
            hv = [g] + [self.add(r, f"{g}.h{i}") for i, r in enumerate(refs[1:], 1)]
            hv = sorted(dict.fromkeys(h for h in hv if h), key=lambda n: self.glyphs[n].width)
            for h in hv:
                self.glyphs[h].accent = self.glyphs[h].width / 2
            self.hvar[hv[0]] = hv
            self.variants.setdefault("accent", {})[name] = hv[0]
            self.variants.setdefault("accentfam", {})[name] = d.fam
        arc = []
        for letter, slot in read_widearc(self.inp.sty):
            fname, scale = EXT_FONTS[letter]
            if self.src.has("mt2" + fname):
                refs, _ = self.chain("mt2" + fname, slot, scale)
                arc += [self.add(r, f"{gname(0x23DC)}.{fname}{r.slot}") for r in refs]
        arc = sorted(dict.fromkeys(a for a in arc if a), key=lambda n: self.glyphs[n].width)
        if arc:
            self.set_cmap(0x23DC, arc[0], force=True)
            self.hvar[arc[0]] = arc

    def braces(self):
        """Curly over/under braces (U+23DE/U+23DF): the glyphs of mtpro2.sty's \\overcbrace
        and \\undercbrace (the macros themselves come with the package)."""
        for cs, cp in (("overcbrace", 0x23DE), ("undercbrace", 0x23DF)):
            hb = []
            for letter, slot, _ in read_cbrace_slots(self.inp.sty).get(cs, []):
                fname, scale = EXT_FONTS[letter]
                hb.append(self.add(Ref("mt2" + fname, slot, scale), f"{gname(cp)}.{fname}{slot}"))
            hb = sorted(dict.fromkeys(h for h in hb if h), key=lambda n: self.glyphs[n].width)
            if hb:
                self.set_cmap(cp, hb[0], force=True)
                self.hvar[hb[0]] = hb

    def centre_and_widen(self):
        """TeX centres large operators and big delimiters on the axis at run time; OpenType
        expects them centred in the font. Large operators' advance includes the italic
        overhang (OpenType convention); assembly pieces start at 0."""
        axis = self.src.tfm(self.fam("symbols")[0]).params[22] * UPM
        radical = self.cmap.get(0x221A)
        for root, vs in self.vvar.items():
            for n in vs:
                g = self.glyphs[n]
                if root != radical and g.ref is not None and ("ex" in g.ref.font or "xl" in g.ref.font):
                    self.shift(n, axis - (g.height - g.depth) / 2)
        for parts in self.vasm.values():
            for n, _, _ in parts:
                self.shift(n, self.glyphs[n].depth)
        # With limits, TeX boxes the operator without its italic correction (and shifts the
        # limits by half of it, as LuaTeX does): unwidened twins, which the package
        # substitutes for operators set with limits.
        for root in list(self.ops()):
            vs = self.vvar.get(root, [root])
            if not any(self.glyphs[n].ref is not None and self.glyphs[n].italic > 0 for n in vs):
                continue
            twins = []
            for n in vs:
                t = copy.copy(self.glyphs[n])
                t.name = n + ".limits"
                self.glyphs[t.name] = t
                twins.append(t.name)
            self.vvar[twins[0]] = twins
            self.limits[root] = twins[0]
            for n in vs:
                g = self.glyphs[n]
                if g.ref is not None and g.italic > 0 and not g.widened:
                    self.widen(n, g.italic)

    def alphabets(self):
        uni, src = self.inp.uni, self.src
        w = self.weight != "normal"

        def alphabet(tag, fonts, digits=False):
            if fonts:
                for c in list(range(65, 91)) + list(range(97, 123)) + (list(range(48, 58)) if digits else []):
                    cp = alpha_cp(tag, chr(c))
                    if cp:
                        self.set_cmap(cp, self.add_sized(fonts, c, gname(cp)), force=True)
        alphabet("script", self.trip(*(("mt2bmst", "mt2bmss", "mt2bmsf") if w else ("mt2mst", "mt2mss", "mt2msf"))))
        alphabet("boldscript", self.trip("mt2bmst", "mt2bmss", "mt2bmsf"))
        alphabet("frak", self.trip(*(("mt2bmft", "mt2bmfs", "mt2bmff") if w else ("mt2mft", "mt2mfs", "mt2mff"))))
        alphabet("boldfrak", self.trip("mt2bmft", "mt2bmfs", "mt2bmff"))
        alphabet("bb", self.trip("mt2bbt", "mt2bbs", "mt2bbf"), digits=True)
        alphabet("bold", self.trip("mt2mbt", "mt2mbs", "mt2mbf"), digits=True)
        alphabet("bolditalic", self.trip("mt2bmit", "mt2bmis", "mt2bmif"))
        if src.has("mt2bbit"):                       # the five double-struck italic letters
            for ch, cp in (("D", 0x2145), ("d", 0x2146), ("e", 0x2147), ("i", 0x2148), ("j", 0x2149)):
                self.set_cmap(cp, self.add_sized(("mt2bbit", "mt2bbis", "mt2bbif"), ord(ch), gname(cp)), True)
        if src.has("mt2bmit"):                       # bold Greek from the bold letters font
            m = re.search(r"\\ifx\\Gamma s(.*?)\\else", self.inp.sty, re.S)   # (slanted capitals)
            for d in parse_decls(m.group(1)) if m else []:
                cp = uni.get("mbfit" + d.cmd.lstrip("\\"))
                if cp:
                    self.set_cmap(cp, self.add_sized(("mt2bmit", "mt2bmis", "mt2bmif"), d.slot, gname(cp)), True)
            for d in self.inp.decls:
                nm = d.cmd.lstrip("\\")
                if d.kind == "symbol" and d.fam == "letters" and nm in GREEK:
                    cp = uni.get(("mbfit" if nm[0].islower() else "mbf") + nm)
                    if cp:
                        self.set_cmap(cp, self.add_sized(("mt2bmit", "mt2bmis", "mt2bmif"), d.slot, gname(cp)), True)

    def alternates(self):
        """Per-use sets for the package (no code points; names start with the base character)."""
        w = self.weight != "normal"

        def alt_set(setname, tag, fonts, digits=False, only=None):
            if not fonts:
                return
            for c in list(range(65, 91)) + list(range(97, 123)) + (list(range(48, 58)) if digits else []):
                ch = chr(c)
                cp = alpha_cp(tag, ch)
                if cp and (only is None or ch in only):
                    g = self.add_sized(fonts, only[ch] if only else c, f"{gname(cp)}.{setname}")
                    if g:
                        self.variants.setdefault(setname, {})[ch] = g
        alt = read_alt_letters(self.inp.sty)
        scr = ("mt2bmst", "mt2bmss", "mt2bmsf") if w else ("mt2mst", "mt2mss", "mt2msf")
        frk = ("mt2bmft", "mt2bmfs", "mt2bmff") if w else ("mt2mft", "mt2mfs", "mt2mff")
        alt_set("curly", "script", self.trip("mt2mct", "mt2mcs", "mt2mcf"))
        alt_set("bbitalic", "bb", self.trip("mt2bbit", "mt2bbis", "mt2bbif"), digits=True)
        alt_set("bbdark", "bb", self.trip("mt2bbdt", "mt2bbds", "mt2bbdf"), digits=True)
        alt_set("bbholey", "bb", self.trip("mt2hrbt", "mt2hrbs", "mt2hrbf"), digits=True)
        alt_set("bbholeydark", "bb", self.trip("mt2hrbdt", "mt2hrbds", "mt2hrbdf"), digits=True)
        alt_set("bbholeyitalic", "bb", self.trip("mt2hbit", "mt2hbis", "mt2hbif"), digits=True)
        alt_set("scriptalt", "script", self.trip(*scr), only=alt.get("Script", {}))
        alt_set("curlyalt", "script", self.trip("mt2mct", "mt2mcs", "mt2mcf"), only=alt.get("Curly", {}))
        alt_set("frakalt", "frak", self.trip(*frk), only=alt.get("Frak", {}))

    def legacy_fonts(self) -> dict[str, int]:
        """MTPro2 fonts the package rebuilds as TFM-exact virtual fonts (font -> scale):
        the legacy symbol fonts (LaTeX's own symbols, mtpro2.sty's macros) and the
        extension fonts mtpro2.sty loads directly at 1x, 2x, 4x and 8x size."""
        out = {}
        for fam in ("letters", "symbols", "largesymbols", "AMSa"):
            for f in self.fam(fam) or ():
                out.setdefault(f, 1)
        if self.weight == "normal":
            out.update({f: s for f, s in LEGACY_EXTRA.items() if f not in out})
        return {f: s for f, s in out.items() if self.src.has(f)}

    def legacy_glyphs(self):
        # the extra-large operators are named after their characters (copy-paste)
        xl, uni = {}, self.inp.uni
        for m in re.finditer(r"\\def\\(xl|XL|XXL|XXXL)@?\{(.*?)\\PackageError", self.inp.sty, re.S):
            font = "mt2xxxl" if m.group(1) == "XXXL" else "mt2xl"
            for cmd, slot in re.findall(r"\\ifx\\next\\(\w+)[^\n]*?\\xlposition@(\d+)", m.group(2)):
                cp = uni.for_command("\\" + cmd) or uni.base_for(cmd)
                if cp:
                    xl.setdefault((font, int(slot)), f"{gname(cp)}.{font[3:]}{slot}")
        for font, scale in self.legacy_fonts().items():
            for slot in self.src.tfm(font).chars:
                ref = Ref(font, slot, scale)
                if ref not in self.by_ref:
                    self.add(ref, xl.get((font, slot), f"mtp.{font}.{slot}"))

    def tex_letter_boxes(self):
        """In TeX's math fonts every character box is width + italic correction; superscripts
        follow it, subscripts tuck back by the correction. OpenType equivalent: advance =
        width + italic, bottom-right math kern = -italic."""
        skip = set(self.ops())
        for v in list(self.vvar.values()) + list(self.hvar.values()):
            skip.update(v)
        for parts in self.vasm.values():
            skip.update(p[0] for p in parts)
        for n, g in self.glyphs.items():
            if n not in skip and g.ref is not None and g.italic > 0 and not g.widened:
                ic = g.italic
                self.widen(n, ic)
                g.mkern, g.italic = -ic, 0

    def tex_kerns(self):
        """TFM kerns between consecutive characters of one font; TeX applies them in math,
        but only after ordinary characters (make_ord)."""
        # (every glyph drawn from a slot, also the copies of it: \\rhook, ...)
        by_font: dict[str, dict[int, list[str]]] = {}
        for name, g in self.glyphs.items():
            ref = g.ref
            if ref is not None and ref.scale == 1 and "ex" not in ref.font and "xl" not in ref.font:
                by_font.setdefault(ref.font, {}).setdefault(ref.slot, []).append(name)
        for font, slots in by_font.items():
            # (the skew character is a real one too: \\rhook in the letters font, and TeX kerns
            # before it like before any other character)
            for (a, b), k in self.src.tfm(font).kerns.items():
                if a in slots and b in slots and abs(k) > 1e-6:
                    for na in slots[a]:
                        if self.glyph_cls.get(na, "\\mathord") in ("\\mathord", "\\mathalpha"):
                            for nb in slots[b]:
                                self.kerns[(na, nb)] = round(k * UPM)
        # luaotfload (base mode) gives a script-size font the .ssty glyphs under the base
        # characters' codes, but keeps their kerns keyed by the partner's .ssty glyph:
        # repeat each such kern for the partner's base glyph.
        base = {alt: g for g, alts in self.ssty.items() for alt in alts}
        for (a, b), k in list(self.kerns.items()):
            if a in base and b in base:
                self.kerns.setdefault((a, base[b]), k)

    def tex_parameters(self):
        """TeX parameters OpenType has no slot for; the package applies them per style."""
        sp = self.src.tfm(self.fam("symbols")[0]).params
        skip = self.ops() | {self.cmap.get(0x221A)}

        def clear_ink(thr):
            """LuaTeX compares delimiter sizes with the ink, TeX with the TFM box: if a size
            is too small for TeX but its ink reaches the threshold, raise the threshold."""
            new = thr
            for root, vs in self.vvar.items():
                for g in (self.glyphs[n] for n in vs if root not in skip):
                    if g.bounds and g.ref is not None:
                        tfm, ink = g.height + g.depth, g.bounds[3] - g.bounds[1]
                        if tfm >= 0.8 * ink and tfm < thr <= ink + 0.5:   # (skip broken TFM boxes)
                            new = max(new, ink + 1)
            return new
        # in em; x-height and axis differ between MTPro2's text, script and scriptscript fonts
        sizes = [self.src.tfm(f).params for f in self.fam("symbols")]
        self.tex_params = {"sup1": sp[13], "sub2": sp[17], "supdrop": sp[18], "subdrop": sp[19],
                           "delim1": clear_ink(sp[20] * UPM) / UPM, "delim2": clear_ink(sp[21] * UPM) / UPM,
                           "xheight": [p[5] for p in sizes], "axis": [p[22] for p in sizes],
                           "opspacing5": self.src.tfm(self.fam("largesymbols")[0]).params[13],
                           # (accents from the extension font are lowered by its x-height)
                           "xheight3": self.src.tfm(self.fam("largesymbols")[0]).params[5]}
        rad = next((d for d in self.inp.decls if d.kind == "radical"), None)
        if rad and self.fam(rad.fam):        # TeX's radical rule: the small sign's height per size
            signs = [self.src.tfm(f).chars[rad.slot] for f in self.fam(rad.fam)]
            self.tex_params["radrule"] = [c.height for c in signs]
            self.tex_params["radsign"] = [c.height + c.depth for c in signs]
            self.tex_params["rule"] = self.src.tfm(self.fam("largesymbols")[0]).params[8]

    def tex_boxes(self):
        """Bounding boxes at least TeX's TFM boxes (LuaTeX measures boxes from the bbox)."""
        for g in self.glyphs.values():
            if g.ref is not None and g.bounds:
                g.tex_box = True
                self.draw(g)

    # ---------------------------------------------------------------- MATH constants
    def math_constants(self) -> dict:
        src = self.src
        sym, ext = self.fam("symbols")[0], self.fam("largesymbols")[0]
        s, x = src.tfm(sym).params, src.tfm(ext).params
        S, X = (lambda i: round(s[i] * UPM)), (lambda i: round(x[i] * UPM))
        th, xh = X(8), S(5)
        disp = 1300
        sumg = self.cmap.get(0x2211)
        if sumg and len(self.vvar.get(sumg, [])) > 1:      # display size of \sum must qualify
            g = self.glyphs[self.vvar[sumg][1]]
            disp = round(g.bounds[3] - g.bounds[1]) - 1
        return {
            "ScriptPercentScaleDown": 70, "ScriptScriptPercentScaleDown": 55,
            "DelimitedSubFormulaMinHeight": round(1.3 * S(6)),
            "DisplayOperatorMinHeight": disp, "MathLeading": 150,
            "AxisHeight": S(22), "AccentBaseHeight": xh, "FlattenedAccentBaseHeight": round(xh * 1.45),
            "SubscriptShiftDown": S(16), "SubscriptTopMax": round(0.8 * xh), "SubscriptBaselineDropMin": S(19),
            "SuperscriptShiftUp": S(14), "SuperscriptShiftUpCramped": S(15),   # display style: package
            "SuperscriptBottomMin": round(xh / 4), "SuperscriptBaselineDropMax": S(18),
            "SubSuperscriptGapMin": 4 * th, "SuperscriptBottomMaxWithSubscript": round(0.8 * xh),
            "SpaceAfterScript": 50,
            "UpperLimitGapMin": X(9), "UpperLimitBaselineRiseMin": X(11),
            "LowerLimitGapMin": X(10), "LowerLimitBaselineDropMin": X(12),
            "StackTopShiftUp": S(10), "StackTopDisplayStyleShiftUp": S(8),
            "StackBottomShiftDown": S(12), "StackBottomDisplayStyleShiftDown": S(11),
            "StackGapMin": 3 * th, "StackDisplayStyleGapMin": 7 * th,
            "StretchStackTopShiftUp": X(11), "StretchStackBottomShiftDown": X(12),
            "StretchStackGapAboveMin": X(9), "StretchStackGapBelowMin": X(10),
            "FractionNumeratorShiftUp": S(9), "FractionNumeratorDisplayStyleShiftUp": S(8),
            "FractionDenominatorShiftDown": S(12), "FractionDenominatorDisplayStyleShiftDown": S(11),
            "FractionNumeratorGapMin": th, "FractionNumDisplayStyleGapMin": 3 * th, "FractionRuleThickness": th,
            "FractionDenominatorGapMin": th, "FractionDenomDisplayStyleGapMin": 3 * th,
            "SkewedFractionHorizontalGap": 350, "SkewedFractionVerticalGap": 96,
            "OverbarVerticalGap": 3 * th, "OverbarRuleThickness": th, "OverbarExtraAscender": th,
            "UnderbarVerticalGap": 3 * th, "UnderbarRuleThickness": th, "UnderbarExtraDescender": th,
            "RadicalVerticalGap": th + round(th / 4), "RadicalDisplayStyleVerticalGap": th + round(xh / 4),
            "RadicalRuleThickness": th, "RadicalExtraAscender": th,
            "RadicalKernBeforeDegree": 278, "RadicalKernAfterDegree": -556, "RadicalDegreeBottomRaisePercent": 60,
        }


# ======================================================================
# 6. Writing the OpenType font
# ======================================================================

DONOR_CPS = list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)) + [
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x2C, 0x2E, 0x40, 0x5F, 0x7E, 0xA3, 0xA5, 0xA7, 0xB6]


def donor_glyphs(path: Path, wanted: list[int]) -> dict:
    """Upright Latin and a few ASCII symbols from a Times-like OpenType font."""
    f = TTFont(path)
    cmap, gs, hm, sc = f.getBestCmap(), f.getGlyphSet(), f["hmtx"], UPM / f["head"].unitsPerEm
    out = {}
    for cp in (c for c in wanted if c in cmap):
        n = cmap[cp]
        w = round(hm[n][0] * sc)
        pen, bp = T2CharStringPen(w, None), BoundsPen(None)
        for p in (pen, bp):
            gs[n].draw(TransformPen(p, (sc, 0, 0, sc, 0, 0)))
        out[gname(cp)] = (pen.getCharString(), w, round(bp.bounds[0]) if bp.bounds else 0, cp)
    return out


def layout_table(tag: str, feature: str, lookup) -> object:
    """GSUB/GPOS table with one feature and one lookup, for scripts DFLT and math."""
    t = getattr(ot, tag)()
    t.Version = 0x00010000
    t.LookupList = ot.LookupList()
    t.LookupList.Lookup = [lookup]
    t.LookupList.LookupCount = 1
    fr = ot.FeatureRecord()
    fr.FeatureTag = feature
    fr.Feature = ot.Feature()
    fr.Feature.FeatureParams = None
    fr.Feature.LookupListIndex = [0]
    fr.Feature.LookupCount = 1
    t.FeatureList = ot.FeatureList()
    t.FeatureList.FeatureRecord = [fr]
    t.FeatureList.FeatureCount = 1
    t.ScriptList = ot.ScriptList()
    t.ScriptList.ScriptRecord = []
    for script in ("DFLT", "math"):
        sr = ot.ScriptRecord()
        sr.ScriptTag = script
        sr.Script = ot.Script()
        sr.Script.DefaultLangSys = ot.LangSys()
        sr.Script.DefaultLangSys.LookupOrder = None
        sr.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
        sr.Script.DefaultLangSys.FeatureIndex = [0]
        sr.Script.DefaultLangSys.FeatureCount = 1
        sr.Script.LangSysRecord = []
        sr.Script.LangSysCount = 0
        t.ScriptList.ScriptRecord.append(sr)
    t.ScriptList.ScriptCount = 2
    table = newTable(tag)
    table.table = t
    return table


def write_otf(B: MathFontBuild, family: str, donor: dict | None) -> TTFont:
    """Glyphs, metrics, names, 'ssty' (GSUB), 'kern' (GPOS) and MATH -> a CFF OpenType font."""
    order = [".notdef"] + list(B.glyphs)
    cs = {".notdef": T2CharStringPen(500, None).getCharString()}
    metrics = {".notdef": (500, 0)}
    for n, g in B.glyphs.items():
        cs[n] = g.charstring
        metrics[n] = (min(max(0, round(g.width)), 32767), round(g.bounds[0]) if g.bounds else 0)
    cmap = B.cmap                     # donor and Latin-Greek entries join the build's cmap
    for n, (c, w, lsb, cp) in (donor or {}).items():
        if cp not in cmap:
            order.append(n)
            cs[n], metrics[n], cmap[cp] = c, (w, lsb), n
    for lat, gr in LATIN_GREEK.items():                   # upright Alpha etc. = upright A etc.
        if gr not in cmap and ord(lat) in cmap:
            cmap[gr] = cmap[ord(lat)]
    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    ps = family.replace(" ", "")
    t1p = B.src.private(B.fam("letters")[0])        # alignment zones of the main (italic) font
    private = {k: t1p[k] for k in ("BlueValues", "OtherBlues", "StdHW", "StdVW", "StemSnapH",
                                   "StemSnapV", "BlueScale", "BlueShift", "BlueFuzz", "ForceBold")
               if k in t1p}
    private = {k: (list(v) if isinstance(v, (list, tuple)) else v) for k, v in private.items()}
    for k in ("StdHW", "StdVW"):
        if k in private:
            private[k] = private[k][0]
    fb.setupCFF(ps, {"FullName": family, "FamilyName": family, "Weight": "Regular"}, cs, private)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-300)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "psName": ps,
                       "uniqueFontIdentifier": ps, "fullName": family, "version": "Version 1.0",
                       "copyright": "Converted from MathTime Professional 2 (Publish or Perish, Inc.) "
                                    "for personal use"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-300, usWinAscent=1100, usWinDescent=400,
                usWeightClass={"normal": 400, "bold": 700, "heavy": 900}[B.weight])
    fb.setupPost()
    font = fb.font
    font["head"].created = font["head"].modified = BUILD_TIME
    gmap = font.getReverseGlyphMap()
    if B.ssty:
        font["GSUB"] = layout_table("GSUB", "ssty", otl.buildLookup([otl.buildAlternateSubstSubtable(B.ssty)]))
    if B.kerns:
        pairs = {k: (otl.buildValue({"XAdvance": v}), None) for k, v in B.kerns.items()}
        font["GPOS"] = layout_table("GPOS", "kern", otl.buildLookup(otl.buildPairPosGlyphs(pairs, gmap)))
    G = B.glyphs
    vv = {r: [(n, math.floor(G[n].height + G[n].depth)) for n in v] for r, v in B.vvar.items() if v}
    hv = {r: [(n, math.floor(G[n].width)) for n in v] for r, v in B.hvar.items() if v}
    va = {r: ([(n, ext, 0, 0, math.floor(adv)) for n, ext, adv in parts], 0)   # TeX: no overlap
          for r, parts in B.vasm.items()}
    extended = {n for v in B.vvar.values() for n in v[1:]} | {p[0] for ps_ in B.vasm.values() for p in ps_}
    buildMathTable(font, constants=B.math_constants(),
                   italicsCorrections={n: round(g.italic) for n, g in G.items() if round(g.italic)},
                   topAccentAttachments={n: round(g.accent) for n, g in G.items() if g.accent is not None},
                   extendedShapes=extended,
                   mathKerns={n: {"BottomRight": ([], [round(g.mkern)])} for n, g in G.items() if g.mkern},
                   minConnectorOverlap=0, vertGlyphVariants=vv, horizGlyphVariants=hv, vertGlyphAssembly=va)
    return font


# ======================================================================
# 7. Companion package (mtpro2-otf.sty / .lua / -variants.lua)
# ======================================================================

def lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def variants_lua(B: MathFontBuild) -> str:
    """Glyph-name tables used at run time (names are identical in all weights)."""
    out = ["-- mtpro2-otf-variants.lua: generated by mtpro2_otf.py (glyph names only, no font data)", "return {"]
    for setname, d in sorted(B.variants.items()):
        out.append(f"  [{lua_str(setname)}]={{" + ",".join(f"[{lua_str(k)}]={lua_str(v)}"
                                                           for k, v in sorted(d.items())) + "},")
    out.append("  limits={" + ",".join(f"[{lua_str(a)}]={lua_str(b)}" for a, b in sorted(B.limits.items())) + "},")
    for w, prm in getattr(B, "weight_params", {}).items():
        lua = lambda v: "{" + ",".join(f"{x:.7f}" for x in v) + "}" if isinstance(v, list) else f"{v:.7f}"
        out.append(f"  [{lua_str('texparams:' + w)}]={{" + ",".join(f"{k}={lua(v)}" for k, v in sorted(prm.items())) + "},")
    for w, cps in getattr(B, "nobold", {}).items():
        out.append(f"  [{lua_str('nobold:' + w)}]={{" + ",".join(f"[{cp}]=true" for cp in cps) + "},")
    if B.tex_params:
        lua = lambda v: "{" + ",".join(f"{x:.7f}" for x in v) + "}" if isinstance(v, list) else f"{v:.7f}"
        out.append("  texparams={" + ",".join(f"{k}={lua(v)}" for k, v in sorted(B.tex_params.items())) + "},")
    out.append("}")
    return "\n".join(out) + "\n"


def packed_lua(source: str, header: list[str]) -> str:
    """A Lua module stored compressed (zlib + base64, both built into LuaTeX)."""
    import base64
    import zlib
    data = base64.b64encode(zlib.compress(source.encode(), 9)).decode()
    lines = "\n".join(data[i:i + 100] for i in range(0, len(data), 100))
    return "\n".join(header) + "\nreturn load(zlib.decompress(mime.unb64((([[\n" + lines + \
        "\n]]):gsub('%s', '')))))()\n"


def tfm_lua(builds: dict[str, MathFontBuild]) -> str:
    """TFM data of the legacy fonts with the OpenType glyph of each character: the package
    builds virtual fonts from it that behave exactly like the Type 1 fonts' TFMs.
    Dimensions are TFM fix_words (2^-20 design size), scaled at load time as TeX does."""
    fw = lambda v: str(round(v * 2**20))
    out = ["-- mtpro2-otf-tfm.lua: generated by mtpro2_otf.py (TeX metrics and glyph names, no outlines)",
           "-- per font: K = kern values; c[slot] = {width, height, depth, italic, glyph index, raise,",
           "--   nextlarger, {top,mid,bot,rep}, {slot, kern index, ...}}  (fix_words)",
           "return {"]
    done = set()
    for w, B in builds.items():
        for font, scale in B.legacy_fonts().items():
            if font in done:
                continue
            done.add(font)
            t = B.src.tfm(font)
            gid = {n: i for i, n in enumerate(B.glyphs, 1)}         # glyph index in the font
            kvals = sorted({k for k in t.kerns.values()})
            kidx = {k: i + 1 for i, k in enumerate(kvals)}
            bychar: dict[int, list] = {}
            for (a, b), k in sorted(t.kerns.items()):
                bychar.setdefault(a, []).extend((b, kidx[k]))
            chars = []
            for slot, c in sorted(t.chars.items()):
                g = B.by_ref.get(Ref(font, slot, scale))
                if not g:
                    continue
                ext = t.exten.get(slot)
                kern = bychar.get(slot)
                chars.append(f"[{slot}]={{{fw(c.width)},{fw(c.height)},{fw(c.depth)},{fw(c.italic)},"
                             f"{gid[g]},{fw(B.glyphs[g].dy / (UPM * scale))},"
                             f"{t.nextlarger.get(slot, 'false')},"
                             f"{'{' + ','.join(map(str, ext)) + '}' if ext else 'false'},"
                             f"{'{' + ','.join(map(str, kern)) + '}' if kern else 'false'}}}")
            out.append(f"  [{lua_str(font)}]={{otf={lua_str(WEIGHTS[w][1])},scale={scale},"
                       f"ds={fw(t.design_size / 16)},p={{{','.join(fw(p) for p in t.params[1:])}}},"
                       f"K={{{','.join(fw(k) for k in kvals)}}},c={{")
            out.append("    " + ",\n    ".join(chars) + "}},")
    out.append("}")
    return "\n".join(out) + "\n"


def dims_lua(builds: dict[str, MathFontBuild]) -> str:
    """Exact TeX boxes (TFM width, height, depth) by glyph index. luaotfload measures glyphs
    from their outlines (rounded to font units, and ink that overshoots the TFM box counts);
    the package puts TeX's dimensions back when the font is loaded."""
    num = lambda v: f"{v:.3f}".rstrip("0").rstrip(".")
    out = ["-- mtpro2-otf-dims.lua: generated by mtpro2_otf.py (glyph metrics only, no outlines)",
           "-- per font: glyph index, width, height, depth (font units), repeated", "return {"]
    for w, B in builds.items():
        vals = []
        for gid, g in enumerate(B.glyphs.values(), 1):         # glyph 0 is .notdef
            if g.ref is not None:
                vals += [str(gid), num(max(g.width, 0)), num(g.height), num(g.depth)]
        out.append(f"  [{lua_str(WEIGHTS[w][0].replace(' ', ''))}]={{" + ",".join(vals) + "},")
    # per font: which glyph italic x is in the text/script/scriptscript instance (they differ by
    # 'ssty'), and the x-heights of those sizes' symbol fonts (TeX places accents with them)
    out.append("  info={")
    for w, B in builds.items():
        gid = {n: i for i, n in enumerate(B.glyphs, 1)}
        x = B.cmap.get(alpha_cp("italic", "x"))
        probe = [gid[x]] + [gid[a] for a in B.ssty.get(x, [])]
        xh = [B.src.tfm(f).params[5] for f in B.fam("symbols")]
        out.append(f"    [{lua_str(WEIGHTS[w][0].replace(' ', ''))}]={{probe={{{','.join(map(str, probe))}}},"
                   f"xheight={{{','.join(f'{v:.7f}' for v in xh)}}}}},")
    out.append("  },")
    out.append("}")
    return "\n".join(out) + "\n"


def command_defs(B: MathFontBuild) -> tuple[list[str], list[str]]:
    """(overrides, provides): lines defining mtpro2.sty's symbol commands by glyph name."""
    over, prov = [], []
    for cmd, (cls, g) in sorted(B.commands.items()):
        if "@" in cmd or not cmd.isalpha():
            continue
        fam, slot = B.cmd_src.get(cmd, ("symbols", 0))
        cp = B.inp.uni.for_command("\\" + cmd, slot, fam)
        line = f"\\MTP@sym\\{cmd}{{{g}}}{{{CLASSES.get(cls, 0)}}}"
        alias = B.inp.uni.aliases.get(cmd)       # unicode-math: \hbar -> \hslash, ...
        if cmd in B.forced or not cp or (cp in B.cmap and B.cmap[cp] != g) or \
                (alias and B.commands.get(alias, (None, None))[1] != g):
            over.append(line)    # mtpro2.sty replaces LaTeX's definition / unicode-math shows another glyph
        else:
            prov.append(line)    # define only if LaTeX/unicode-math lacks it
    return over, prov


LUA = r'''-- mtpro2-otf.lua: run-time helper for mtpro2-otf.sty (picks MTPro2 glyphs by name)
mtpro2otf = mtpro2otf or {}
mtpro2otf.litebm = mtpro2otf.litebm or {}
mtpro2otf.vfchars = {}                             -- virtual fonts: font id -> characters
-- every file through TeX's own search paths (TEXINPUTS too, e.g. a Fonts/ folder added
-- by latexmkrc), never a fixed location
local function find(name, fmt)
  return kpse.find_file(name, fmt or "lua") or kpse.find_file(name, "tex")
end
mtpro2otf.find = find
local function load(name)
  local p = find(name .. ".lua")
  if not p then error("mtpro2-otf: cannot find " .. name .. ".lua") end
  return dofile(p)
end
function mtpro2otf.fontdir(name)                  -- folder of an OpenType font ("" if not found)
  local p = find(name, "opentype fonts")
  tex.sprint(-2, p and (p:match("^(.*/)") or "./") or "")
end
local V = load("mtpro2-otf-variants")
-- TeX's exact glyph boxes (luaotfload measures outlines: rounded, and with overshoots)
local D = load("mtpro2-otf-dims")
mtpro2otf.italic = {}                               -- font id -> {char -> subscript kern}
luatexbase.add_to_callback("luaotfload.patch_font", function(tfm, spec, id)
  local d = D[tfm.psname or (tfm.properties or {}).psname or ""]
  if not d or not tfm.characters then return end
  -- a glyph with several code points (A and Alpha, \\partial's U+2202 and U+1D715, | and
  -- \\mid): luaotfload gives its kerns and math kerns to one code point only; TeX looks
  -- characters up by the code it was given, so every code point needs them
  local codes = {}
  for u, c in pairs(tfm.characters) do
    if c.index then codes[c.index] = codes[c.index] or {}; table.insert(codes[c.index], u) end
  end
  for _, us in pairs(codes) do
    if #us > 1 then
      local kerns, mk
      for _, u in ipairs(us) do
        local c = tfm.characters[u]
        if c.kerns then kerns = kerns or {}; for v, k in pairs(c.kerns) do kerns[v] = kerns[v] or k end end
        mk = mk or c.mathkern
      end
      for _, u in ipairs(us) do
        local c = tfm.characters[u]
        if kerns then c.kerns = c.kerns or {}; for v, k in pairs(kerns) do c.kerns[v] = c.kerns[v] or k end end
        c.mathkern = c.mathkern or mk
      end
    end
  end
  for _, c in pairs(tfm.characters) do            -- ... and as the second of a pair too
    if c.kerns then
      local add = {}
      for v, k in pairs(c.kerns) do
        local cv = tfm.characters[v]
        for _, w in ipairs(cv and cv.index and codes[cv.index] or {}) do
          if w ~= v and not c.kerns[w] then add[w] = k end
        end
      end
      for w, k in pairs(add) do c.kerns[w] = k end
    end
  end
  -- the subscript tuck (TeX's italic correction) is applied by the package, always: take the
  -- math kerns out of LuaTeX's hands (it applies them only to some subscripts)
  local ik = {}
  for u, c in pairs(tfm.characters) do
    local mk = c.mathkern and c.mathkern.bottom_right
    if mk and mk[1] and mk[1].kern then ik[u] = mk[1].kern; c.mathkern = nil end
  end
  if id then mtpro2otf.italic[id] = ik end
  local f = tfm.parameters.factor or (tfm.parameters.size / (tfm.units_per_em or 1000))
  local at = {}
  for i = 1, #d, 4 do at[d[i]] = i end
  for _, c in pairs(tfm.characters) do             -- c.index: the glyph actually used
    local i = c.index and at[c.index]               -- (after 'ssty' in script fonts)
    if i then
      c.width, c.height, c.depth = math.floor(d[i+1] * f + 0.5), math.floor(d[i+2] * f + 0.5),
        math.floor(d[i+3] * f + 0.5)
    end
  end
  -- TeX lowers an accent by at most the x-height of the accent's font, which is the script
  -- (scriptscript) size's own font in sub- and superscripts; OpenType has one value
  local info, mp = D.info and D.info[tfm.psname], tfm.mathparameters
  local x = tfm.characters[0x1D465]
  if info and mp and x and mp.AccentBaseHeight then
    local level = 1
    for k, g in ipairs(info.probe) do if x.index == g then level = k end end
    local abh = math.floor(info.xheight[level] * tfm.parameters.size + 0.5)
    if mp.FlattenedAccentBaseHeight then
      mp.FlattenedAccentBaseHeight = math.floor(mp.FlattenedAccentBaseHeight * abh / mp.AccentBaseHeight + 0.5)
    end
    mp.AccentBaseHeight = abh
  end
end, "mtpro2-otf.dims")
local function fam() return tex.getmathcode(0x2211)[2] end
local function slot(name)
  local f = fam()
  return luaotfload.aux.slot_of_name(node.family_font(f, 0), name), f
end
-- Legacy layer: MTPro2's TFM fonts rebuilt as virtual fonts on the OpenType glyphs, so that
-- LaTeX's own symbol families and mtpro2.sty's macros (which load mt2exe etc. directly)
-- behave exactly as with the Type 1 fonts. A font named "mtp2vf:<tfm name>" is built here.
local TF
local function scaler(z)                           -- TeX's store_scaled (tex.web 571-572)
  local alpha = 16
  while z >= 0x800000 do z = z // 2; alpha = alpha + alpha end
  local beta = 256 // alpha
  alpha = alpha * z
  return function(v)
    if v < 0 then v = v + 0x100000000 end
    local a, b, c, d = v >> 24, (v >> 16) & 255, (v >> 8) & 255, v & 255
    local sw = (((((d * z) // 256) + (c * z)) // 256) + (b * z)) // beta
    return a == 255 and sw - alpha or sw
  end
end
local basefonts = {}
local function basefont(otf, size)
  local key = otf .. "@" .. size
  if not basefonts[key] then
    local data = fonts.definers.read("[" .. (find(otf, "opentype fonts") or otf) .. "]:mode=base;", size)
    local codes = {}                                -- glyph index -> character code
    for u, c in pairs(data.characters) do
      if c.index and not codes[c.index] then codes[c.index] = u end
    end
    basefonts[key] = { font.define(data), codes }
  end
  return basefonts[key][1], basefonts[key][2]
end
function mtpro2otf.virtual(name, size)
  TF = TF or load("mtpro2-otf-tfm")
  local T = TF[name]
  if not T then return nil end
  if size < 0 then size = (-size * T.ds) // 1000 end
  local sc = scaler(size)
  local bid, codes = basefont(T.otf, (size + T.scale // 2) // T.scale)
  local K = {}
  for i, k in ipairs(T.K) do K[i] = sc(k) end
  local chars = {}
  for slot, c in pairs(T.c) do
    local u = codes[c[5]]
    if u then
      local ch = { width = sc(c[1]), height = sc(c[2]), depth = sc(c[3]), italic = sc(c[4]),
        commands = c[6] ~= 0 and { { "down", sc(c[6]) }, { "slot", 1, u } } or { { "slot", 1, u } } }
      if c[7] then ch.next = c[7] end
      local e = c[8]
      if e then
        ch.extensible = { top = e[1] ~= 0 and e[1] or nil, mid = e[2] ~= 0 and e[2] or nil,
          bot = e[3] ~= 0 and e[3] or nil, rep = e[4] }
      end
      if c[9] then
        ch.kerns = {}
        for i = 1, #c[9], 2 do ch.kerns[c[9][i]] = K[c[9][i + 1]] end
      end
      chars[slot] = ch
    end
  end
  local p, params = T.p, {}
  local names = { "slant", "space", "space_stretch", "space_shrink", "x_height", "quad", "extra_space" }
  for i, v in ipairs(p) do
    local val = i == 1 and v // 16 or sc(v)
    params[names[i] or i] = val
  end
  return { name = "mtp2vf:" .. name, type = "virtual", size = size, designsize = T.ds,
    characters = chars, fonts = { { id = bid } }, parameters = params }
end
-- Font loading: build the virtual fonts, and apply the package's scale option to every
-- MTPro2 font (the OpenType ones and the virtual ones), as a size factor at load time.
-- Wraps whatever font loader is installed (luaotfload's, or another package's wrapper).
mtpro2otf.scale = mtpro2otf.scale or 1
do
  local desc = luatexbase.callback_descriptions("define_font")[1]
  local define = desc and luatexbase.remove_from_callback("define_font", desc) or font.read_tfm
  luatexbase.add_to_callback("define_font", function(name, size, id)
    local s = mtpro2otf.scale
    local n = name:match("^mtp2vf:(.+)$")
    if s ~= 1 and size > 0 and (n or name:find("MTPro2Math", 1, true)) then
      size = math.floor(size * s + 0.5)
    end
    if n then
      local f = mtpro2otf.virtual(n, size)
      if f then mtpro2otf.vfchars[id] = f.characters; return f end
    end
    return define(name, size, id)
  end, "mtpro2-otf.define_font")
end
-- Before LuaTeX converts a formula, adjust two things it does differently from TeX:
-- * a large operator without \\limits or \\nolimits is set like \\nolimits outside display
--   style (italic correction between operator and scripts); LuaTeX does that only for an
--   explicit \\nolimits;
-- * a subscript tucks under a character's italic correction whatever it contains: add the
--   kern at the start of the subscript (LuaTeX's math kerns would cover only some cases).
do
  local NOAD, STYLE, FRAC, CHOICE, RAD, ACC, SUBML, MCHAR = node.id("noad"), node.id("style"),
    node.id("fraction"), node.id("choice"), node.id("radical"), node.id("accent"),
    node.id("sub_mlist"), node.id("math_char")
  local names = { display = 0, crampeddisplay = 1, text = 2, crampedtext = 3, script = 4,
    crampedscript = 5, scriptscript = 6, crampedscriptscript = 7 }
  local function num(s) return type(s) == "number" and s or names[s] or 2 end
  local function sup(s) return (s < 4 and 4 or 6) + s % 2 end
  local function sub(s) return sup(s) | 1 end
  local function numer(s) return s < 2 and 2 + s % 2 or (s < 6 and s + 2 or s) end
  local function size(s) return s < 4 and 0 or (s < 6 and 1 or 2) end
  -- (LuaTeX versions differ here: newer ones box an operator with limits including its
  -- italic correction, older ones do not; try one operator to see which twin matches TeX)
  local limits_map = {}
  local function limits_char(nu, s)
    local id = node.family_font(nu.fam, size(s))
    local m = limits_map[id]
    if not m then
      m = {}
      local probe
      for a, b in pairs(V.limits or {}) do
        local ca, cb = luaotfload.aux.slot_of_name(id, a), luaotfload.aux.slot_of_name(id, b)
        if ca and cb then m[ca] = cb; probe = probe or { ca, cb } end
      end
      if probe then
        local f = font.getfont(id)
        local cw, ci = f.characters[probe[2]].width, f.characters[probe[2]].italic or 0
        local op = node.new("noad", 2)
        op.nucleus = node.new("math_char"); op.nucleus.fam, op.nucleus.char = nu.fam, probe[2]
        local box = node.hpack(node.mlist_to_hlist(op, "text", false))
        -- the twins are for engines that add the italic correction to the box
        if ci == 0 or math.abs(box.width - (cw + ci)) > math.abs(box.width - cw) then m = {} end
        node.flush_list(box)
      end
      limits_map[id] = m
    end
    return m[nu.char]
  end
  local function italic_kern(nu, s)
    local t = mtpro2otf.italic[node.family_font(nu.fam, size(s))]
    return t and t[nu.char]
  end
  local walk
  local function list(f, s) if f and f.id == SUBML then f.head = walk(f.head, s) end end
  local snames = { [0] = "display", "crampeddisplay", "text", "crampedtext", "script",
    "crampedscript", "scriptscript", "crampedscriptscript" }
  -- TeX's radical rule is as thick as the sign it uses; in script sizes the small sign is
  -- thicker than the default rule: set such a radical here, with the right thickness
  local function radical(n, s)
    local p = V.texparams
    if not (p and p.radsign) or s < 4 or not n.nucleus then return n end
    local u, z = mtpro2otf.fontsize[node.family_font(fam(), size(s))], size(s) + 1
    local tmp
    if n.nucleus.id == SUBML then tmp = node.copy_list(n.nucleus.head)
    else tmp = node.new("noad", 0); tmp.nucleus = node.copy(n.nucleus) end
    local x = node.hpack(node.mlist_to_hlist(tmp, snames[s | 1], false))
    local theta = p.rule * u
    local need = x.height + x.depth + theta + theta // 4 + theta
    node.flush_list(x)
    if need > p.radsign[z] * u then return n end      -- a larger sign: the default rule
    list(n.nucleus, s | 1); list(n.degree, 6)
    local sub, sup = n.sub, n.sup
    n.sub, n.sup = nil, nil
    local old = tex.getmath("radicalrule", snames[s])
    tex.setmath("radicalrule", snames[s], math.floor(p.radrule[z] * u + 0.5))
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local box = node.hpack(node.mlist_to_hlist(n, snames[s], false))
    tex.setmath("radicalrule", snames[s], old)
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  -- Lite \\bm / \\hm (no bold MTPro2 fonts): what has the \\bm attribute becomes newtx bold
  -- (letters, Greek, digits: real bold, like the Type 1 set-up), the bold font of an alphabet
  -- that has one, or else bm.sty's poor man's bold (three copies, .4mu apart, raised 1.5x)
  local LB = mtpro2otf.litebm
  local function pmb(nc, s, subtype)
    local tmp = node.new("noad", subtype or 0)
    tmp.nucleus = nc
    local b = node.hpack(node.mlist_to_hlist(tmp, snames[s], false))
    local r = s < 4 and 1 or tonumber(token.get_macro(s < 6 and "defaultscriptratio"
      or "defaultscriptscriptratio") or "") or (s < 6 and 0.7 or 0.5)
    local d = math.floor(0.4 / 18 * tex.getmath("quad", "text") * r + 0.5)
    local c1, c2 = node.copy(b), node.copy(b)
    c2.shift = -math.floor(1.5 * d + 0.5)
    local r1, r2 = node.hpack(c1, 0, "exactly"), node.hpack(c2, 0, "exactly")
    local k1, k2 = node.new("kern"), node.new("kern")
    k1.kern, k2.kern = d, d
    r1.next, k1.prev = k1, r1; k1.next, r2.prev = r2, k1; r2.next, k2.prev = k2, r2
    k2.next, b.prev = b, k2
    local sb = node.new("sub_box")
    sb.head = node.hpack(r1)
    return sb
  end
  local BOLDCP = { { 0x1D400, 0x1D433 }, { 0x1D468, 0x1D49B }, { 0x1D4D0, 0x1D503 },
    { 0x1D56C, 0x1D59F }, { 0x1D5D4, 0x1D607 }, { 0x1D63C, 0x1D66F }, { 0x1D6A8, 0x1D6E1 },
    { 0x1D71C, 0x1D755 }, { 0x1D756, 0x1D7C9 }, { 0x1D7CA, 0x1D7CB }, { 0x1D7CE, 0x1D7D7 },
    { 0x1D7EC, 0x1D7F5 } }
  local function boldcp(c)
    for _, r in ipairs(BOLDCP) do if c >= r[1] and c <= r[2] then return true end end
  end
  local FENCE, FRAC2 = node.id("fence"), node.id("fraction")
  local function bold(nc, s, subtype)           -- a math_char under \\bm: the field's new value
    if not (nc and nc.id == MCHAR) then return nc end
    local a = node.has_attribute(nc, LB.attr)
    if not a then return nc end
    node.unset_attribute(nc, LB.attr)             -- (once: the walk can meet it again)
    local m = LB.map and nc.fam == fam() and LB.map[nc.char]
    if m and LB[m[1]] then nc.fam, nc.char = LB[m[1]], m[2]; return nc end
    local main = nc.fam == fam()
    if main and boldcp(nc.char) then return nc end  -- already a bold letter (\\mathbf, \\symbf)
    local nb = main and V[a == 1 and "nobold:bold" or "nobold:heavy"]
    if nb and nb[nc.char] and (nc.char >= 0x1D434 and nc.char <= 0x1D467 or nc.char == 0x210E) then
      return nc                 -- (bm.sty: a letter typed as such keeps its font when its family
    end                         -- has no such weight; a command like \\alpha gets poor man's bold)
    local f = not (nb and nb[nc.char]) and LB.fams[a] and LB.fams[a][nc.fam]
    if f and main and nc.char >= 0xF0000 then       -- a glyph set by name (private code):
      local z = size(s)                             -- the same name in the bold font
      local name = mtpro2otf.byslot[nc.char]
      local ok, slot = pcall(luaotfload.aux.slot_of_name, node.family_font(f, 0), name or "")
      if name and ok and slot then nc.fam, nc.char = f, slot; return nc end
      f = nil
    end
    if f then nc.fam = f; return nc end
    f = LB.fontmap and LB.fontmap[a][node.family_font(nc.fam, size(s))]
    if f then nc.fam = f; return nc end            -- (a math alphabet's bold)
    if not main and not LB.symfam[nc.fam] then return nc end  -- (an alphabet: no poor man's bold)
    return pmb(nc, s, subtype)
  end
  local boldrad, boldfrac, todirect = {}, {}, node.direct.todirect
  local function fams(n)                        -- the bold families for n's attribute, if any
    local a = node.has_attribute(n, LB.attr)
    return a and LB.fams[a]
  end
  local function lite(n, s)
    local id = n.id
    if id == NOAD then
      n.nucleus = bold(n.nucleus, s, (n.subtype >= 1 and n.subtype <= 3) and n.subtype or 0)
    elseif id == ACC or id == RAD then
      n.nucleus = bold(n.nucleus, s | 1)
      local t = fams(n)
      if t and id == ACC then                     -- the accent itself, if its font has a bold
        for _, k in ipairs({ "accent", "bot_accent" }) do
          local ok, c = pcall(function() return n[k] end)
          if ok and c and c.fam and t[c.fam] then c.fam = t[c.fam] end
        end
      elseif t and n.left then                    -- the radical sign
        local d = n.left
        if t[d.small_fam] or t[d.large_fam] then boldrad[todirect(n)] = node.has_attribute(n, LB.attr) end
        if t[d.small_fam] then d.small_fam = t[d.small_fam] end
        if t[d.large_fam] then d.large_fam = t[d.large_fam] end
      end
      if id == RAD then n.degree = bold(n.degree, 6) end
    elseif id == FENCE then                       -- \\left( .. \\right): bold delimiters
      local t, d = fams(n), n.delim
      if t and d then
        if t[d.small_fam] then d.small_fam = t[d.small_fam] end
        if t[d.large_fam] then d.large_fam = t[d.large_fam] end
      end
      return
    elseif id == FRAC2 then                       -- the bold version's rule (bm.sty sets
      local t = fams(n)                           -- such a group in the bold version)
      local bf = t and t[fam()]
      local id2 = bf and node.family_font(bf, size(s))
      local mc = id2 and id2 > 0 and font.getfont(id2) and font.getfont(id2).MathConstants
      local w = n.width or 0
      if mc and mc.FractionRuleThickness and (w < 0 or w >= 0x40000000) then
        boldfrac[todirect(n)] = { mc.FractionRuleThickness, node.has_attribute(n, LB.attr) }
      end
      return
    else return end
    n.sup, n.sub = bold(n.sup, sup(s)), bold(n.sub, sub(s))
  end
  -- TeX's radical rule is as thick as the sign it chose is high (a large sign, a bold one
  -- under \\bm), OpenType has one value: where they differ, set the radical here
  local GLYPH, HLIST, VLIST = node.id("glyph"), node.id("hlist"), node.id("vlist")
  local function firstglyph(h)
    for x in node.traverse(h) do
      if x.id == GLYPH then return x end
      if (x.id == HLIST or x.id == VLIST) and x.head then
        local g = firstglyph(x.head)
        if g then return g end
      end
    end
  end
  local function exactradical(n, s, force)
    list(n.nucleus, s | 1); list(n.degree, 6)
    local trial = node.hpack(node.mlist_to_hlist(node.copy(n), snames[s], false))
    local g = firstglyph(trial.head)
    local f = g and font.getfont(g.font)
    local chars = f and f.characters or (g and mtpro2otf.vfchars[g.font])
    local c = chars and chars[g.char]
    node.flush_list(trial)
    local old = tex.getmath("radicalrule", snames[s])
    local h = c and c.height
    if not h or h <= 0 or (h == old and not force) then return n end
    local sub, sup = n.sub, n.sup
    n.sub, n.sup = nil, nil
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local st, saved = snames[s], {}
    local set = { radicalrule = h }
    -- (LaTeX's \\sqrt[n] is \\root, set in a box: under bm.sty that box is in the bold
    -- version, with the bold fonts' clearance; a plain \\sqrt keeps the formula's)
    local isroot = node.has_attribute(n, luatexbase.attributes["MTP@rootattr"] or -1)
    local bp = force and isroot and V[force == 2 and "texparams:heavy" or "texparams:bold"]
    if bp then
      local u, z = mtpro2otf.fontsize[node.family_font(fam(), size(s))], size(s) + 1
      local th = math.floor(bp.rule * u + 0.5)
      local phi = s < 2 and math.floor(bp.xheight[z] * u + 0.5) or th
      set.radicalvgap, set.radicalkern = th + math.abs(phi) // 4, th
    end
    for k, v in pairs(set) do saved[k] = tex.getmath(k, st); tex.setmath(k, st, v) end
    local box = node.hpack(node.mlist_to_hlist(n, st, false))
    for k, v in pairs(saved) do tex.setmath(k, st, v) end
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  -- an accent from the extension font (\\wwhat, \\wwtilde, \\wwcheck): TeX lowers it by at
  -- most that font's x-height (in a script: the extension font scaled), OpenType by the
  -- symbol fonts' (AccentBaseHeight): set the accent's kern as TeX does
  local KERN = node.id("kern")
  local extacc
  local function isext(n)
    if not extacc then
      extacc = {}
      for name, f in pairs(V.accentfam or {}) do
        if f == "largesymbols" and V.accent[name] then
          local sl = slot(V.accent[name])
          if sl then extacc[sl] = true end
        end
      end
    end
    local ok, a = pcall(function() return n.accent end)
    return ok and a and a.char and extacc[a.char] and a.fam == fam()
  end
  local function accentfix(h, A)
    local changed = false
    for x in node.traverse(h) do
      if x.id == VLIST and x.head then
        local a = x.head
        local k = a.next
        local b = k and k.next
        if k and k.id == KERN and b and not b.next and (b.id == HLIST or b.id == VLIST) then
          k.kern = -math.min(b.height, A)
          x.height = a.height + a.depth + k.kern + b.height
          changed = true
        end
      elseif x.id == HLIST and x.head and accentfix(x.head, A) then
        local w, hh, d = node.dimensions(x.head)
        x.height, x.depth = math.max(hh - (0), 0), d
        changed = true
      end
    end
    return changed
  end
  local function extaccent(n, s)
    local p = V.texparams
    list(n.nucleus, s | 1)
    local sub, sup = n.sub, n.sup
    n.sub, n.sup = nil, nil
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local u = mtpro2otf.fontsize[node.family_font(fam(), size(s))]
    local box = node.hpack(node.mlist_to_hlist(n, snames[s], false))
    if accentfix(box.head, math.floor(p.xheight3 * u + 0.5)) then
      local inner = box.head
      box.head = nil
      node.free(box)
      box = node.hpack(inner)
    end
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  walk = function(head, s)
    local n = head
    while n do
      local id = n.id
      if LB and LB.attr then lite(n, s) end
      if id == STYLE then
        s = num(n.style)
      elseif id == ACC and s >= 4 and V.texparams and V.texparams.xheight3 and isext(n)
          and not (n.nucleus and n.nucleus.id == MCHAR and (n.sub or n.sup)) then
        -- (in a script, where the sizes' x-heights differ; scripts on an accented character
        -- are TeX's own case, left to the engine)
        local r = extaccent(n, s)
        if n == head then head = r end
        list(r.sup, sup(s)); list(r.sub, sub(s))
        n = r
      elseif id == RAD and n.subtype <= 2 then
        local bold, r = boldrad[todirect(n)], n
        boldrad[todirect(n)] = nil
        if s >= 4 and not bold then r = radical(n, s) end
        if r == n then r = exactradical(n, s, bold) end
        if r ~= n then
          if n == head then head = r end
          list(r.sup, sup(s)); list(r.sub, sub(s))
          n = r
        else
          list(n.sup, sup(s)); list(n.sub, sub(s))
        end
      elseif id == NOAD or id == RAD or id == ACC then
        if id == NOAD and n.subtype == 1 and s > 1 then n.subtype = 3 end
        if id == NOAD and (n.subtype == 2 or n.subtype == 1) and s < 4 and n.nucleus
            and n.nucleus.id == MCHAR then
          local t = limits_char(n.nucleus, s)        -- operator set with limits
          if t then n.nucleus.char = t end
        end
        local nu, sb = n.nucleus, n.sub
        -- (TeX moves the scripts of an accented character onto the character)
        local k = (id == NOAD or id == ACC) and nu and nu.id == MCHAR and sb and italic_kern(nu, s)
        if k and k ~= 0 then
          if sb.id ~= SUBML then                    -- x_i: make the subscript a list
            local ml, ord = node.new("sub_mlist"), node.new("noad", 0)
            ord.nucleus, ml.head, n.sub = sb, ord, nil
            n.sub, sb = ml, ml
          end
          local kn = node.new("kern")
          kn.kern = k
          sb.head = node.insert_before(sb.head, sb.head, kn)
        end
        list(nu, (id == RAD or id == ACC) and (s | 1) or s)
        list(n.sup, sup(s)); list(sb, sub(s))
        if id == RAD then list(n.degree, 6) end
      elseif id == FRAC and boldfrac[todirect(n)] then
        -- under \\bm: bm.sty sets the group in the bold version, so TeX builds this fraction
        -- with the bold fonts' rule, num/denom shifts and axis; OpenType keeps its own gaps:
        -- set it here as TeX does (make_fraction)
        local _, wa = table.unpack(boldfrac[todirect(n)])
        boldfrac[todirect(n)] = nil
        local bp = V[wa == 2 and "texparams:heavy" or "texparams:bold"]
        if bp and n.num and n.denom and not n.left and not n.right then
          list(n.num, numer(s)); list(n.denom, numer(s) | 1)
          local u, z = mtpro2otf.fontsize[node.family_font(fam(), size(s))], size(s) + 1
          local function sp(v) return math.floor(v * u + 0.5) end
          local function clean(f, st)
            local h
            if f.id == SUBML then h = f.head; f.head = nil
            else h = node.new("noad", 0); h.nucleus = node.copy(f) end
            return node.hpack(node.mlist_to_hlist(h, snames[st], false))
          end
          local x, zb = clean(n.num, numer(s)), clean(n.denom, numer(s) | 1)
          if x.width < zb.width then x = node.hpack(x, zb.width, "exactly")
          elseif zb.width < x.width then zb = node.hpack(zb, x.width, "exactly") end
          local function centre(b, w)             -- TeX's rebox: the narrower one centred
            local g1, g2 = node.new("glue"), node.new("glue")
            g1.stretch, g1.stretch_order, g2.stretch, g2.stretch_order = 65536, 2, 65536, 2
            local inner = b.head; b.head = nil
            local l = g1; g1.next = inner; if inner then inner.prev = g1 end
            local last = node.tail(g1); last.next = g2; g2.prev = last
            node.free(b)
            return node.hpack(l, w, "exactly")
          end
          local w = math.max(x.width, zb.width)
          x, zb = centre(x, w), centre(zb, w)
          local th, axis = sp(bp.rule), sp(bp.axis[z])
          local up = sp(s < 2 and bp.num1[z] or bp.num2[z])
          local down = sp(s < 2 and bp.denom1[z] or bp.denom2[z])
          local clr, delta = s < 2 and 3 * th or th, th // 2
          local d1 = clr - ((up - x.depth) - (axis + delta))
          if d1 > 0 then up = up + d1 end
          local d2 = clr - ((axis - delta) - (zb.height - down))
          if d2 > 0 then down = down + d2 end
          local k1, r, k2 = node.new("kern"), node.new("rule"), node.new("kern")
          k1.kern = (up - x.depth) - (axis + delta)
          r.height, r.depth = th, 0
          k2.kern = (axis - delta) - (zb.height - down)
          x.next, k1.prev = k1, x; k1.next, r.prev = r, k1; r.next, k2.prev = k2, r
          k2.next, zb.prev = zb, k2
          local v = node.vpack(x)
          v.height, v.depth = up + x.height, zb.depth + down
          local nd = tex.nulldelimiterspace
          local b1, b2 = node.new("hlist"), node.new("hlist")
          b1.width, b2.width = nd, nd
          b1.next, v.prev = v, b1; v.next, b2.prev = b2, v
          local box = node.hpack(b1)
          local prev, nxt = n.prev, n.next
          local inner, nu = node.new("noad", 9), node.new("sub_box")
          nu.head, inner.nucleus = box, nu
          if prev then prev.next = inner; inner.prev = prev end
          if nxt then nxt.prev = inner; inner.next = nxt end
          if n == head then head = inner end
          n.prev, n.next = nil, nil
          node.flush_node(n)
          n = inner
        else
          list(n.num, numer(s)); list(n.denom, numer(s) | 1)
        end
      elseif id == FRAC then
        list(n.num, numer(s)); list(n.denom, numer(s) | 1)
      elseif id == CHOICE then
        n.display = walk(n.display, 0); n.text = walk(n.text, 2)
        n.script = walk(n.script, 4); n.scriptscript = walk(n.scriptscript, 6)
      end
      n = n.next
    end
    return head
  end
  luatexbase.add_to_callback("mlist_to_hlist", function(head, style, penalties)
    head = walk(head, num(style))
    return node.mlist_to_hlist(head, style, penalties)
  end, "mtpro2-otf.mlist")
end
-- (Lite: see setlitebm)
-- \\bm, \\hm: the fonts of each math version, as LaTeX records them (read at begin document);
-- a family whose font differs in the bold (heavy) version gets that font as a new family
local BM = { font = {}, alph = {} }
function mtpro2otf.bmfont(v, fam, name)
  BM.font[v] = BM.font[v] or {}
  BM.font[v][fam] = name
end
function mtpro2otf.bmalph(v, cs, enc, name)
  BM.alph[v] = BM.alph[v] or {}
  local function trim(x) return (x:gsub("^%s+", ""):gsub("%s+$", "")) end
  BM.alph[v][cs] = { trim(enc), trim(name) }      -- (robust commands' inner names end in a space)
end
function mtpro2otf.bmdeclare()
  -- (LaTeX allows 16 symbol fonts, so the new families are not symbol fonts: they count down
  -- from 255, clear of LaTeX's own, and \\bm loads their fonts for the current size)
  local L = mtpro2otf.litebm
  L.attr, L.fams = luatexbase.attributes["MTP@bmattr"], { {}, {} }
  local normal, byspec, top, defs = BM.font.normal or {}, {}, 255, {}
  L.symfam = {}
  for fam, name in pairs(normal) do byspec[name] = byspec[name] or fam; L.symfam[fam] = true end
  for i, v in ipairs({ "bold", "heavy" }) do
    for fam, name in pairs(normal) do
      local b = (BM.font[v] or {})[fam]
      if b and b ~= name and b:match("^[^/]*/.*/[^/]*/[^/]*$") then
        if not byspec[b] then
          byspec[b] = top
          defs[#defs + 1] = string.format("\\MTP@bmfam{%d}{%s}", top, b)
          top = top - 1
        end
        L.fams[i][fam] = byspec[b]
      end
    end
  end
  BM.top = top
  defs[#defs + 1] = "\\directlua{mtpro2otf.bmcheck()}"
  local ct = luatexbase.registernumber("catcodetable@atletter")
  tex.print(ct, "\\gdef\\MTP@bmfams{" .. table.concat(defs) .. "}")
end
-- (LuaTeX takes all math parameters from an OpenType font assigned to a family, so loading
-- the bold fonts would replace the ones in force: keep them)
local MP = { "quad", "axis", "operatorsize", "overbarkern", "overbarrule", "overbarvgap",
  "underbarkern", "underbarrule", "underbarvgap", "radicalkern", "radicalrule", "radicalvgap",
  "radicaldegreebefore", "radicaldegreeafter", "radicaldegreeraise", "stackvgap", "stacknumup",
  "stackdenomdown", "fractionrule", "fractionnumvgap", "fractionnumup", "fractiondenomvgap",
  "fractiondenomdown", "fractiondelsize", "skewedfractionhgap", "skewedfractionvgap",
  "limitabovevgap", "limitabovebgap", "limitabovekern", "limitbelowvgap", "limitbelowbgap",
  "limitbelowkern", "nolimitsubfactor", "nolimitsupfactor", "underdelimitervgap",
  "underdelimiterbgap", "overdelimitervgap", "overdelimiterbgap", "subshiftdrop",
  "supshiftdrop", "subshiftdown", "subsupshiftdown", "subtopmax", "supshiftup", "supbottommin",
  "supsubbottommax", "subsupvgap", "spaceafterscript", "connectoroverlapmin", "primeshiftup",
  "primeshiftdrop", "primespaceafter", "primewidth", "accentbaseheight", "accentbasedepth",
  "flattenedaccentbaseheight", "flattenedaccentbasedepth" }
local MS = { "display", "crampeddisplay", "text", "crampedtext", "script", "crampedscript",
  "scriptscript", "crampedscriptscript" }
local saved
function mtpro2otf.mathparams(save)
  if save then
    saved = {}
    for _, n in ipairs(MP) do
      for _, st in ipairs(MS) do
        local ok, v = pcall(tex.getmath, n, st)
        if ok and v then saved[#saved + 1] = { n, st, v } end
      end
    end
  elseif saved then
    for _, e in ipairs(saved) do tex.setmath("global", e[1], e[2], e[3]) end
    saved = nil
  end
end
-- math alphabets (\\mathrm etc. as NFSS sets them up): a family with the normal font, one
-- with the bold font, and a map from the one to the other by font, for each size
-- a bold version whose font NFSS substitutes with the normal one (no such shape) has no bold:
-- as with bm.sty, that family gets poor man's bold
function mtpro2otf.bmcheck()
  local L = mtpro2otf.litebm
  local function file(id)
    local f = id and id > 0 and font.getfont(id)
    return f and (f.filename or f.name) .. "|" .. tostring(f.size)
  end
  for i = 1, 2 do
    for fam, b in pairs(L.fams[i]) do
      local same = true
      for k = 0, 2 do
        local x, y = node.family_font(fam, k), node.family_font(b, k)
        if x ~= y and file(x) ~= file(y) then same = false end
      end
      if same then L.fams[i][fam] = nil end
    end
  end
end
function mtpro2otf.bmalphabets()
  local L = mtpro2otf.litebm
  local nalph, defs, byspec = BM.alph.normal or {}, {}, {}
  for i, v in ipairs({ "bold", "heavy" }) do
    for cs, e in pairs(BM.alph[v] or {}) do
      local n = nalph[cs]
      -- (unicode-math gives its text alphabets a new font for the normal version only, so
      -- the bold version's entry can be a stale one: then the same font family in bold)
      local nenc, nfam, _, nshape = (n and n[2] or ""):match("^([^/]*)/(.*)/([^/]*)/([^/]*)$")
      local _, bfam = e[2]:match("^([^/]*)/(.*)/([^/]*)/([^/]*)$")
      if nfam and bfam ~= nfam then e = { n[1], string.format("%s/%s/b/%s", nenc, nfam, nshape) } end
      if n and n[2] ~= e[2] then
        for _, spec in ipairs({ n[2], e[2] }) do
          if not byspec[spec] then
            byspec[spec] = BM.top
            defs[#defs + 1] = string.format("\\MTP@bmfam{%d}{%s}", BM.top, spec)
            BM.top = BM.top - 1
          end
        end
        defs[#defs + 1] = string.format("\\directlua{mtpro2otf.bmfontmap(%d,%d,%d)}", i,
          byspec[n[2]], byspec[e[2]])
      end
    end
  end
  local ct = luatexbase.registernumber("catcodetable@atletter")
  tex.print(ct, "\\g@addto@macro\\MTP@bmfams{" .. table.concat(defs) .. "}")
end
function mtpro2otf.bmfontmap(i, nf, bf)
  local L = mtpro2otf.litebm
  L.fontmap = L.fontmap or { {}, {} }
  for k = 0, 2 do
    local id = node.family_font(nf, k)
    if id and id > 0 then L.fontmap[i][id] = bf end
  end
end
-- Lite: letters, Greek and digits under \\bm from newtx (there are no bold MTPro2 fonts)
function mtpro2otf.setlitebm(t)
  local L = mtpro2otf.litebm
  L.it, L.up, L.rm = t.it, t.up, t.rm
  local m = {}
  for i = 0, 25 do
    m[0x1D434 + i] = { "it", 0x41 + i }; m[0x1D44E + i] = { "it", 0x61 + i }
    m[0x30 + (i % 10)] = { "rm", 0x30 + (i % 10) }
  end
  m[0x1D455], m[0x210E] = nil, { "it", 0x68 }    -- (italic h is U+210E)
  -- Greek in TeX's OML order (classic \\epsilon, \\phi are the lunate/straight forms)
  local lc = { 0x0B, 0x0C, 0x0D, 0x0E, 0x22, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x6F, 0x19, 0x1A, 0x26, 0x1B, 0x1C, 0x1D, 0x27, 0x1F, 0x20, 0x21 }
  for i, v in ipairs(lc) do m[0x1D6FC + i - 1] = { "it", v } end
  for cp, v in pairs({ [0x1D715] = 0x40, [0x1D716] = 0x0F, [0x1D717] = 0x23, [0x1D719] = 0x1E,
      [0x1D71A] = 0x25, [0x1D71B] = 0x24, [0x2113] = 0x60, [0x1D6A4] = 0x7B, [0x1D6A5] = 0x7C }) do
    m[cp] = { "it", v }
  end
  -- capital Greek: Greek shapes at TeX's slots 0-10, the others are Latin capitals
  local uc = { "A", "B", 0, 1, "E", "Z", "H", 2, "I", "K", 3, "M", "N", 4, "O", 5, "P", false,
    6, "T", 7, 8, "X", 9, 10 }
  for i, v in ipairs(uc) do
    if v then
      local slot = type(v) == "string" and v:byte() or v
      m[0x0391 + i - 1] = { "up", slot }; m[0x1D6E2 + i - 1] = { "it", slot }
    end
  end
  L.map = m
end
function mtpro2otf.provide(cs, cls)
  local t = token.create(cs)
  local c = t.cmdname
  tex.setcount("MTP@def", (c == "undefined_cs" or c == "math_given" or c == "relax") and 1 or 0)
  -- unicode-math lets many commands be their character (\\therefore = U+2234): keep it, with
  -- the class mtpro2.sty gives the command (TeX's spacing depends on it)
  if cls and (c == "other_char" or c == "letter" or c == "char_given") and t.mode then
    local m = tex.getmathcode(t.mode)
    local cur = m and (m[1] == 7 and 0 or m[1])
    if m and m[1] <= 7 and cur ~= (cls == 7 and 0 or cls) and m[2] then
      tex.setmathcode("global", t.mode, { cls, m[2], m[3] })
    end
  end
end
mtpro2otf.byslot = {}                               -- private code -> glyph name (for \\bm)
function mtpro2otf.glyph(name, cls)
  local s, f = slot(name)
  if s then mtpro2otf.byslot[s] = name end
  if s then tex.sprint(string.format('\\Umathchar"%X"%X"%X ', cls, f, s)) end
end
function mtpro2otf.alpha(set, text)
  if set == "none" then                          -- \\altX outside its alphabet
    texio.write_nl("term and log", "Package mtpro2-otf Warning: invalid use of \\alt" .. text)
    tex.sprint(text)
    return
  end
  local t = V[set] or {}
  local alt = V[set:gsub("alt$", "") .. "alt"] or {}
  local i = 1
  while i <= #text do
    local ch = text:sub(i, i)
    if ch == "\\" then                            -- a command: \\altX is this set's alternate X
      local name = text:match("^%a+", i + 1) or text:sub(i + 1, i + 1)
      i = i + 1 + #name
      while text:sub(i, i) == " " do i = i + 1 end
      local x = name:match("^alt(%a)$")
      if x and alt[x] then mtpro2otf.glyph(alt[x], 0) else tex.sprint("\\" .. name .. " ") end
    else
      if t[ch] then mtpro2otf.glyph(t[ch], 0) elseif ch ~= " " then tex.sprint(ch) end
      i = i + 1
    end
  end
end
-- TeX's per-style parameters (OpenType has one value, scaled by the style's font size)
local styles = { {"display", 0}, {"crampeddisplay", 0}, {"text", 0}, {"crampedtext", 0},
  {"script", 1}, {"crampedscript", 1}, {"scriptscript", 2}, {"crampedscriptscript", 2} }
local fontsize = setmetatable({}, { __index = function(t, id)   -- (font.getfont is slow)
  local f = font.getfont(id); t[id] = f and f.size or 0; return t[id] end })
mtpro2otf.fontsize = fontsize
function mtpro2otf.texparams()
  local p = V.texparams
  if not p then return end
  local f, sz = fam(), {}
  for i = 0, 2 do sz[i] = fontsize[node.family_font(f, i)] end
  local function set(name, style, v) tex.setmath(name, style, math.floor(v + 0.5)) end
  set("supshiftup", "display", p.sup1 * sz[0])
  for _, st in ipairs(styles) do
    local s, i = st[1], st[2]
    local u, n = sz[i], sz[math.min(i + 1, 2)]       -- this style's size, its scripts' size
    local xh = p.xheight[i + 1] * u
    set("supshiftdrop", s, p.supdrop * n)
    set("subshiftdrop", s, p.subdrop * n)
    set("subsupshiftdown", s, p.sub2 * u)
    set("fractiondelsize", s, (s:find("display") and p.delim1 or p.delim2) * u)
    set("axis", s, p.axis[i + 1] * u)
    set("subtopmax", s, xh * 4 / 5)
    set("supbottommin", s, xh / 4)
    set("supsubbottommax", s, xh * 4 / 5)
    if p.rule then set("radicalrule", s, p.rule * u) end
    set("limitabovekern", s, p.opspacing5 * u)       -- TeX pads limits by big_op_spacing5
    set("limitbelowkern", s, p.opspacing5 * u)
    tex.setmath("spaceafterscript", s, tex.scriptspace)   -- TeX: \\scriptspace, unscaled
  end
end
-- mtpro2.sty's accents without a code point of their own (\\dotup, \\what, ...)
function mtpro2otf.accent(name)
  local g, s, f = (V.accent or {})[name]
  if g then s, f = slot(g) end
  if s and f then tex.sprint(string.format('\\Umathaccent"0"%X"%X ', f, s)) end
end
function mtpro2otf.accents()
  local ct = luatexbase.registernumber("catcodetable@atletter")
  for name in pairs(V.accent or {}) do
    tex.print(ct, string.format("\\DeclareRobustCommand\\%s{\\directlua{mtpro2otf.accent('%s')}}",
      name, name))
  end
end
function mtpro2otf.delim(set, key, cls)
  local g = (V[set] or {})[key]
  if not g then return end
  local s, f = slot(g)
  if s then tex.sprint(string.format('\\Udelimiter"%X"%X"%X ', cls, f, s)) end
end
'''


STY = r'''%% mtpro2-otf.sty -- MathTime Pro 2 as OpenType (built by mtpro2_otf.py) for LuaLaTeX
%% Loads MTPro2Math(-Bold/-Heavy).otf with unicode-math and restores MTPro2's extras:
%%   \xl \XL \XXL \XXXL, \bm \hm, \altC..\altz, \mathcurly, \mathbbdark, \mathbbholey,
%%   \mathbbholeydark, \mathbbitalic, \mathbbholeyitalic, \mathfrakalt, \mathcurlyalt,
%%   \zswash, straight/morphed braces, and every mtpro2.sty symbol command.
\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{mtpro2-otf}[@@DATE@@ v@@VERSION@@ MTPro2 OpenType companion]
\RequirePackage{iftex}
\RequireLuaTeX
% which set these files were made from, and the version (for classes that choose fallbacks)
\def\MTPOTFedition{@@EDITION@@}
\def\MTPOTFversion{@@VERSION@@}
\newif\ifMTP@lite \def\MTP@tmp{Lite}\ifx\MTPOTFedition\MTP@tmp \MTP@litetrue \fi
% packages that clash: mtpro2-otf provides their commands
\newif\ifMTP@ownload
\def\MTP@clash#1#2{\PackageError{mtpro2-otf}{Do not load #1 together with mtpro2-otf}%
  {mtpro2-otf provides #2. Remove \protect\usepackage{#1}.}}
\def\MTP@addclash#1{\@ifpackageloaded{#1}{\MTP@clash{#1}{its commands}}{}%
  \AddToHook{package/#1/before}{\ifMTP@ownload\else\MTP@clash{#1}{its commands}\fi}}
\@for\MTP@o:=mtpro2,bm,amssymb,amsfonts\do{\expandafter\MTP@addclash\expandafter{\MTP@o}}
\def\MTP@features{}
% mtpro2.sty's options (same names, same defaults); anything else is an OpenType feature
% (Lite has no script, Fraktur or blackboard bold: Euler and AMS ones, as for the Type 1 fonts)
\def\MTP@cal{c}\def\MTP@scr{a}\def\MTP@frak{a}\def\MTP@bb{b}\def\MTP@br{c}
\ifMTP@lite \def\MTP@scr{e}\def\MTP@frak{e}\def\MTP@bb{y}\fi
\newif\ifMTP@slops \newif\ifMTP@zswash \newif\ifMTP@sbcorr \newif\ifMTP@textsf
\def\MTP@complete#1{\ifMTP@lite\PackageWarning{mtpro2-otf}{Option `\CurrentOption' needs
  MTPro2 Complete; ignored}\else#1\fi}
\def\MTP@na{\PackageWarning{mtpro2-otf}{Option `\CurrentOption' needs fonts the OpenType
  conversion does not have; ignored}}
\@for\MTP@o:=complete,lite,amssymbols,noamssymbols,compatiblegreek,errorshow,warningshow,%
  nofontinfo\do{\expandafter\DeclareOption\expandafter{\MTP@o}{}}
\DeclareOption{uprightGreek}{\def\MTP@greek{u}}
\DeclareOption{slantedGreek}{\def\MTP@greek{s}\PassOptionsToPackage{math-style=ISO}{unicode-math}%
  \directlua{mtpro2otf = mtpro2otf or {} mtpro2otf.slantedgreek = true}}
\DeclareOption{uprightoperators}{\MTP@slopsfalse}
\DeclareOption{slantedoperators}{\MTP@slopstrue}
\DeclareOption{subscriptcorrection}{\MTP@sbcorrtrue}
\DeclareOption{nosubscriptcorrection}{\MTP@sbcorrfalse}
\DeclareOption{zswash}{\MTP@zswashtrue}
\DeclareOption{nozswash}{\MTP@zswashfalse}
\DeclareOption{curlybraces}{\def\MTP@br{c}}
\DeclareOption{straightbraces}{\def\MTP@br{s}}
\DeclareOption{morphedbraces}{\def\MTP@br{m}}
\DeclareOption{cmcal}{\def\MTP@cal{c}}
\DeclareOption{eucal}{\def\MTP@cal{e}}
\DeclareOption{mtpcal}{\MTP@complete{\def\MTP@cal{a}}}
\DeclareOption{mtpccal}{\MTP@complete{\def\MTP@cal{u}}}
\DeclareOption{lucidacal}{\MTP@na}\DeclareOption{mtpluscal}{\MTP@na}
\DeclareOption{mtpscr}{\MTP@complete{\def\MTP@scr{a}}}
\DeclareOption{lucidascr}{\MTP@na}\DeclareOption{mtplusscr}{\MTP@na}
\DeclareOption{mtpfrak}{\MTP@complete{\def\MTP@frak{a}}}
\DeclareOption{eufrak}{\def\MTP@frak{e}}
\DeclareOption{amsbb}{\def\MTP@bb{y}}
% the template's choices: newtx's calligraphic letters; \mathsf from the text's sans-serif
\DeclareOption{ntxcal}{\def\MTP@cal{n}}
\DeclareOption{textsf}{\MTP@textsftrue}
\DeclareOption{mtpbb}{\MTP@complete{\def\MTP@bb{b}}}
\DeclareOption{mtpbbd}{\MTP@complete{\def\MTP@bb{d}}}
\DeclareOption{mtphrb}{\MTP@complete{\def\MTP@bb{h}}}
\DeclareOption{mtphrd}{\MTP@complete{\def\MTP@bb{k}}}
\DeclareOption{mtpbbi}{\MTP@complete{\def\MTP@bb{i}}}
\DeclareOption{mtphbi}{\MTP@complete{\def\MTP@bb{j}}}
% scale=<factor>: all MTPro2 fonts at that fraction of their nominal size (e.g. 0.95 next
% to text set at 95%); anything else is an OpenType feature
\def\MTP@scale{1}
\def\MTP@opt#1=#2\@nil{\def\MTP@key{#1}\def\MTP@val{#2}}
\DeclareOption*{\expandafter\MTP@opt\CurrentOption=\@nil
  \def\MTP@tmp{scale}\ifx\MTP@key\MTP@tmp
    \expandafter\MTP@opt\CurrentOption\@nil\let\MTP@scale\MTP@val
  \else
    \edef\MTP@features{\ifx\MTP@features\@empty\else\MTP@features,\fi\CurrentOption}%
  \fi}
\ProcessOptions\relax
\ifMTP@sbcorr\catcode`\_=12 \fi
\directlua{mtpro2otf = mtpro2otf or {} mtpro2otf.scale = \MTP@scale\space
  dofile(kpse.find_file("mtpro2-otf.lua", "lua") or kpse.find_file("mtpro2-otf.lua", "tex"))}% before the fonts load: registers the metrics fix
\ifMTP@lite % Lite lacks the AMS symbols and blackboard bold: the AMS fonts' (scaled), kept for
  % exactly the commands whose glyphs Lite does not have
  \edef\MTP@s{s*[\MTP@scale]}%
  \DeclareFontFamily{U}{msa}{}\DeclareFontShape{U}{msa}{m}{n}{<-6>\MTP@s msam5<6-8>\MTP@s msam7%
    <8->\MTP@s msam10}{}%
  \DeclareFontFamily{U}{msb}{}\DeclareFontShape{U}{msb}{m}{n}{<-6>\MTP@s msbm5<6-8>\MTP@s msbm7%
    <8->\MTP@s msbm10}{}%
  \MTP@ownloadtrue\RequirePackage{amssymb}\MTP@ownloadfalse
  \let\MTP@amsbb\mathbb
  \def\MTP@amslist{@@AMSLIST@@}%
  \@for\MTP@o:=\MTP@amslist\do{\expandafter\let\csname MTP@ams@\MTP@o\expandafter\endcsname
    \csname\MTP@o\endcsname}%
  \AddToHook{begindocument/end}{\@for\MTP@o:=\MTP@amslist\do{\expandafter\let
    \csname\MTP@o\expandafter\endcsname\csname MTP@ams@\MTP@o\endcsname}}%
\fi
\RequirePackage{unicode-math}
\edef\MTP@path{\directlua{mtpro2otf.fontdir("MTPro2Math.otf")}}% (found like any TeX file)
\edef\MTP@load{\noexpand\setmathfont{MTPro2Math.otf}[Path=\MTP@path,RawFeature={\MTP@features}]}\MTP@load
\IfFileExists{MTPro2Math-Bold.otf}{%
  \edef\MTP@load{\noexpand\setmathfont{MTPro2Math-Bold.otf}[Path=\MTP@path,version=bold,RawFeature={\MTP@features}]}\MTP@load
  \def\MTP@boldver{bold}}{\def\MTP@boldver{normal}}
\IfFileExists{MTPro2Math-Heavy.otf}{%
  \edef\MTP@load{\noexpand\setmathfont{MTPro2Math-Heavy.otf}[Path=\MTP@path,version=heavy,RawFeature={\MTP@features}]}\MTP@load
  \def\MTP@heavyver{heavy}}{\let\MTP@heavyver\MTP@boldver}
% LaTeX's symbol families (letters, symbols, largesymbols) on TFM-exact virtual MTPro2 fonts
\input{mtpro2-otf-legacy.tex}
% (an alphabet with a bold font: a symbol font, so that \bm finds its bold)
\def\MTP@alph#1#2#3#4{% alphabet, name, encoding, family (shapes m/n and b/n)
  \DeclareSymbolFont{MTP#2}{#3}{#4}{m}{n}\SetSymbolFont{MTP#2}{bold}{#3}{#4}{b}{n}%
  \DeclareSymbolFontAlphabet{#1}{MTP#2}}
% alphabets the options can choose from fonts that are not MTPro2 (as mtpro2.sty does)
\edef\MTP@s{s*[\MTP@scale]}% (scaled like the MTPro2 fonts)
\if c\MTP@cal \DeclareFontFamily{OMS}{MTPcmsy}{\skewchar\font48}%
  \DeclareFontShape{OMS}{MTPcmsy}{m}{n}{<-6>\MTP@s cmsy5<6-7>\MTP@s cmsy6<7-8>\MTP@s cmsy7%
    <8-9>\MTP@s cmsy8<9-10>\MTP@s cmsy9<10->\MTP@s cmsy10}{}%
  \DeclareFontShape{OMS}{MTPcmsy}{b}{n}{<-6>\MTP@s cmbsy5<6-7>\MTP@s cmbsy6<7-8>\MTP@s cmbsy7%
    <8-9>\MTP@s cmbsy8<9-10>\MTP@s cmbsy9<10->\MTP@s cmbsy10}{}%
  \MTP@alph\MTP@cmcal{cmcal}{OMS}{MTPcmsy}\fi
\if n\MTP@cal \let\ntxmath@scaled\MTP@s
  \DeclareFontEncoding{LMS}{}{}\DeclareFontSubstitution{LMS}{ntxsy}{m}{n}%
  \MTP@alph\MTP@ntxcal{ntxcal}{LMS}{ntxsy}\fi
\if e\MTP@cal \let\MTP@needeus\@empty\fi \if e\MTP@scr \let\MTP@needeus\@empty\fi
\ifdefined\MTP@needeus \DeclareFontFamily{U}{eus}{\skewchar\font'60}%
  \DeclareFontShape{U}{eus}{m}{n}{<-6>\MTP@s eusm5<6-8>\MTP@s eusm7<8->\MTP@s eusm10}{}%
  \DeclareFontShape{U}{eus}{b}{n}{<-6>\MTP@s eusb5<6-8>\MTP@s eusb7<8->\MTP@s eusb10}{}%
  \MTP@alph\MTP@eus{eus}{U}{eus}\fi
\if e\MTP@frak \DeclareFontFamily{U}{euf}{}%
  \DeclareFontShape{U}{euf}{m}{n}{<-6>\MTP@s eufm5<6-8>\MTP@s eufm7<8->\MTP@s eufm10}{}%
  \DeclareFontShape{U}{euf}{b}{n}{<-6>\MTP@s eufb5<6-8>\MTP@s eufb7<8->\MTP@s eufb10}{}%
  \MTP@alph\MTP@eufrak{eufrak}{U}{euf}\fi
\ifMTP@lite\else\if y\MTP@bb \DeclareFontFamily{U}{msb}{}%
  \DeclareFontShape{U}{msb}{m}{n}{<-6>\MTP@s msbm5<6-8>\MTP@s msbm7<8->\MTP@s msbm10}{}%
  \DeclareMathAlphabet{\MTP@amsbb}{U}{msb}{m}{n}\fi\fi
\ifMTP@textsf % \mathsf in the document's sans-serif font (MTPro2 has no sans letters)
  \AddToHook{begindocument/before}{\DeclareMathAlphabet{\MTP@textsf}{TU}{\sfdefault}{m}{n}%
    \SetMathAlphabet{\MTP@textsf}{bold}{TU}{\sfdefault}{\bfdefault}{n}}%
\fi
% TeX's per-style parameters, set at the start of every formula (follows size changes)
\def\MTP@params{\directlua{mtpro2otf.texparams()}}
\everymath\expandafter{\the\everymath\MTP@params}
\everydisplay\expandafter{\the\everydisplay\MTP@params}

% \bm and \hm as bm.sty does them, symbol by symbol: whatever is typeset under \bm gets an
% attribute, and mtpro2-otf.lua moves each symbol to the bold font its family has in the bold
% math version (the heavy one for \hm), or draws bm's poor man's bold where there is none;
% so do the math alphabets. Every symbol keeps its class and its scripts.
\providecommand\bm{}\providecommand\hm{}
\newattribute\MTP@bmattr
\newattribute\MTP@rootattr % (marks LaTeX's \root box, see mtpro2-otf.lua)
\protected\def\bm#1{\relax\ifmmode\MTP@bmsize\begingroup\MTP@bmattr=1 #1\endgroup
  \else\ensuremath{\bm{#1}}\fi}
\protected\def\hm#1{\relax\ifmmode\MTP@bmsize\begingroup\MTP@bmattr=2 #1\endgroup
  \else\ensuremath{\hm{#1}}\fi}
% (the bold fonts in the extra families, for the current size: as NFSS sets a math alphabet)
\let\MTP@bmfams\@empty \def\MTP@bmat{}
\def\MTP@bmsize{\ifx\MTP@bmat\tf@size\else\directlua{mtpro2otf.mathparams(true)}\MTP@bmfams
  \directlua{mtpro2otf.mathparams(false)}\global\let\MTP@bmat\tf@size\fi}
\def\MTP@bmfam#1#2{\begingroup\escapechar\m@ne\let\math@fonts\@empty
  \expandafter\MTP@bmfam@\csname#2\endcsname{#1}\globaldefs\@ne\math@fonts\endgroup}
\def\MTP@bmfam@#1#2{\getanddefine@fonts{#2}#1}
% (the fonts of each version, as LaTeX records them: \mv@normal, \mv@bold, \mv@heavy)
% (symbol fonts before the document starts, alphabets once unicode-math has set its own)
\def\MTP@bmread#1#2{\begingroup\escapechar\m@ne
  \ifnum#2=0
    \def\getanddefine@fonts##1##2{\directlua{mtpro2otf.bmfont("#1",\number##1,
      "\luaescapestring{\string##2}")}}\let\install@mathalphabet\@gobbletwo
  \else
    \let\getanddefine@fonts\@gobbletwo\def\install@mathalphabet##1##2{\MTP@bmreadalph{#1}##2}%
  \fi
  \csname mv@#1\endcsname\endgroup}
\def\MTP@bmreadalph#1\select@group#2#3#4{\directlua{mtpro2otf.bmalph("#1",
  "\luaescapestring{\string#2}","\luaescapestring{\string#3}","\luaescapestring{\string#4}")}}
\AddToHook{begindocument/before}{%
  \MTP@bmread{normal}0\MTP@bmread{bold}0\ifdefined\mv@heavy\MTP@bmread{heavy}0\fi
  \directlua{mtpro2otf.bmdeclare()}}
\AddToHook{begindocument/end}{%
  \MTP@bmread{normal}1\MTP@bmread{bold}1\ifdefined\mv@heavy\MTP@bmread{heavy}1\fi
  \directlua{mtpro2otf.bmalphabets()}}
\ifMTP@lite % no bold MTPro2 fonts: letters, Greek and digits in newtx bold (as the Type 1
  % set-up does), digits in the text font's bold; \hm is \bm (no heavy fonts)
  \ifnum\directlua{tex.sprint((kpse.find_file("ntxbmi.tfm", "tfm") and
      kpse.find_file("ntx-Bold-tlf-ot1.tfm", "tfm")) and 1 or 0)}=1
    \DeclareFontFamily{OML}{MTPntxbmi}{\skewchar\font=127 }%
    \DeclareFontShape{OML}{MTPntxbmi}{b}{it}{<-6.3>\MTP@s ntxbmi5<6.3-8.6>\MTP@s ntxbmi7%
      <8.6->\MTP@s ntxbmi}{}%
    \DeclareFontFamily{OT1}{MTPntxb}{}%
    \DeclareFontShape{OT1}{MTPntxb}{b}{n}{<->\MTP@s ntx-Bold-tlf-ot1}{}%
    \DeclareSymbolFont{MTPbmit}{OML}{MTPntxbmi}{b}{it}%
    \DeclareSymbolFont{MTPbmup}{OT1}{MTPntxb}{b}{n}%
    \def\MTP@bmletters{it=\number\symMTPbmit, up=\number\symMTPbmup,}%
  \else
    \PackageWarningNoLine{mtpro2-otf}{newtx is not installed: \string\bm\space draws
      letters\MessageBreak in poor man's bold too}%
    \def\MTP@bmletters{}%
  \fi
  \AddToHook{begindocument/before}{%
    \DeclareSymbolFont{MTPbmrm}{TU}{\rmdefault}{\bfdefault}{n}%
    \directlua{mtpro2otf.setlitebm{\MTP@bmletters rm=\number\symMTPbmrm}}}%
  \let\hm\bm
\fi

% alphabets and alternate letters (per use)
\def\MTP@alpha#1#2{\directlua{mtpro2otf.alpha("#1","\luaescapestring{\detokenize{#2}}")}}
\def\MTP@galpha#1#2{{\MTP@alpha{#1}{#2}}}% (a group, like a math alphabet)
\def\MTP@altset{none}% (outside its alphabets mtpro2.sty's \altX is X, with a warning)
\def\MTP@wrapalpha#1#2{\expandafter\let\csname MTP@orig\string#1\endcsname#1%
  \protected\edef#1##1{{\def\noexpand\MTP@altset{#2}\expandafter\noexpand
    \csname MTP@orig\string#1\endcsname{##1}}}}
\newcommand\mathcurly[1]{\MTP@alpha{curly}{#1}}
\newcommand\mathcurlyalt[1]{\MTP@galpha{curlyalt}{#1}}
\newcommand\mathfrakalt[1]{\MTP@galpha{frakalt}{#1}}
\newcommand\mathbbdark[1]{\MTP@galpha{bbdark}{#1}}
\newcommand\mathbbholey[1]{\MTP@galpha{bbholey}{#1}}
\newcommand\mathbbholeydark[1]{\MTP@galpha{bbholeydark}{#1}}
\newcommand\mathbbitalic[1]{\MTP@galpha{bbitalic}{#1}}
\newcommand\mathbbholeyitalic[1]{\MTP@galpha{bbholeyitalic}{#1}}
\@for\MTP@l:=C,G,I,L,M,N,Q,S,Y,Z,r,x,y,z\do{% (the alternate of the alphabet it is used in)
  \expandafter\protected\expandafter\edef\csname alt\MTP@l\endcsname{%
    \noexpand\MTP@alpha{\noexpand\MTP@altset}{\MTP@l}}}

% brace styles for \left/\right
\def\MTP@delim#1#2#3{\directlua{mtpro2otf.delim("delim:#1","#2",#3)}}
\DeclareRobustCommand\lbracestraight{\MTP@delim{straight}{lbrace}{4}}
\DeclareRobustCommand\rbracestraight{\MTP@delim{straight}{rbrace}{5}}
\DeclareRobustCommand\lbracemorphed{\MTP@delim{morphed}{lbrace}{4}}
\DeclareRobustCommand\rbracemorphed{\MTP@delim{morphed}{rbrace}{5}}

% every mtpro2.sty symbol command, by glyph name
\def\MTP@dosym#1#2#3{\DeclareRobustCommand#1{\directlua{mtpro2otf.glyph("#2",#3)}}}
\let\MTP@sym\MTP@dosym
% (provide: unless unicode-math defines it; LaTeX's own \mathchardef'd symbols point to
% the legacy Computer Modern families, so those are replaced too)
\def\MTP@psym#1#2#3{\directlua{mtpro2otf.provide("\luaescapestring{\expandafter\@gobble\string#1}",#3)}%
  \ifnum\MTP@def=1 \MTP@dosym#1{#2}{#3}\fi}
\newcount\MTP@def
\AtBeginDocument{%
@@OVERRIDES@@
\let\MTP@sym\MTP@psym
@@PROVIDES@@
}
% with amsmath, mtpro2.sty keeps amsmath's composite arrows (\mapsto = \mapstochar\rightarrow, ...)
\AtBeginDocument{\@ifpackageloaded{amsmath}{%
@@AMSMATH@@
}{}}
\providecommand\zswash{\directlua{mtpro2otf.glyph("@@ZSWASH@@",0)}}

% arrows over formulas and \overbrace/\underbrace as LaTeX/amsmath build them (from
% pieces and rules) instead of unicode-math's stretchy glyphs
\AtBeginDocument{%
@@CLASSIC@@
}

% \sqrt[n]{...}: TeX's placement of the degree (raised by 0.6 of the radical's height
% minus depth; OpenType's percentage counts height plus depth)
\AtBeginDocument{\@ifpackageloaded{amsmath}{%
  \def\plainroot@#1\of#2{\setbox\rootbox\hbox{$\m@th\scriptscriptstyle{#1}$}%
    \mathchoice{\r@@t\displaystyle{#2}}{\r@@t\textstyle{#2}}%
      {\r@@t\scriptstyle{#2}}{\r@@t\scriptscriptstyle{#2}}\egroup}%
  \def\r@@t#1#2{\setbox\z@\hbox{$\MTP@rootattr=1 \m@th#1\sqrtsign{#2}$}%
    \dimen@\ht\z@\advance\dimen@-\dp\z@
    \setbox\@ne\hbox{$\m@th#1\mskip\uproot@ mu$}\advance\dimen@ by1.667\wd\@ne
    \mkern-\leftroot@ mu\mkern5mu\raise.6\dimen@\copy\rootbox
    \mkern-10mu\mkern\leftroot@ mu\box\z@}}{}}

% mtpro2.sty's accents that have no Unicode character (\dotup, \what, \wwtilde, ...)
\AtBeginDocument{\directlua{mtpro2otf.accents()}}
% mtpro2.sty's own macros (\widehat, \overcbrace, \PARENS, \SQRT, \xl, ...), verbatim
\AtBeginDocument{\makeatletter\input{mtpro2-otf-macros.tex}\makeatother}

% the options' choices of alphabets, braces, operators and z (after unicode-math's set-up)
\AtBeginDocument{%
  % mtpro2.sty's own alphabets are {\MTPsetup..\MTP..{#1}}: a group, and \altX for that alphabet
  \if a\MTP@scr \MTP@wrapalpha\mathscr{scriptalt}\fi
  \if a\MTP@frak \MTP@wrapalpha\mathfrak{frakalt}\fi
  \MTP@wrapalpha\mathcurly{curlyalt}%
  \if b\MTP@bb \MTP@wrapalpha\mathbb{none}\fi
  \if c\MTP@cal \let\mathcal\MTP@cmcal \fi
  \if n\MTP@cal \let\mathcal\MTP@ntxcal \fi
  \if e\MTP@cal \let\mathcal\MTP@eus \fi
  \if e\MTP@scr \let\mathscr\MTP@eus \fi
  \ifMTP@textsf \let\mathsf\MTP@textsf \fi
  \if a\MTP@cal \let\mathcal\mathscr \fi
  \if u\MTP@cal \let\mathcal\mathcurly \fi
  \if e\MTP@frak \let\mathfrak\MTP@eufrak \fi
  \if y\MTP@bb \let\mathbb\MTP@amsbb \fi
  \if d\MTP@bb \let\mathbb\mathbbdark \fi
  \if h\MTP@bb \let\mathbb\mathbbholey \fi
  \if k\MTP@bb \let\mathbb\mathbbholeydark \fi
  \if i\MTP@bb \let\mathbb\mathbbitalic \fi
  \if j\MTP@bb \let\mathbb\mathbbholeyitalic \fi
  \@ifpackageloaded{amsmath}{% \sum, \prod, \coprod as mtpro2.sty defines them
    \gdef\slsum{\DOTSB\slsumop\slimits@}\gdef\slprod{\DOTSB\slprodop\slimits@}%
    \gdef\slcoprod{\DOTSB\slcoprodop\slimits@}\gdef\upsum{\DOTSB\upsumop\slimits@}%
    \gdef\upprod{\DOTSB\upprodop\slimits@}\gdef\upcoprod{\DOTSB\upcoprodop\slimits@}}{%
    \let\slsum\slsumop\let\slprod\slprodop\let\slcoprod\slcoprodop
    \let\upsum\upsumop\let\upprod\upprodop\let\upcoprod\upcoprodop}%

  \ifMTP@zswash \begingroup\lccode`\~=`\z\lowercase{\endgroup\def~{\zswash}}\fi}
% (last: unicode-math sets mathcodes and \sum at the start of the document)
\AddToHook{begindocument/end}{\ifMTP@zswash\mathcode`z="8000 \fi
  \if s\MTP@br \straightbraces \fi  % mtpro2.sty's own (the braces of its fonts' metrics)
  \if m\MTP@br \morphedbraces \fi
  \ifMTP@sbcorr\mathcode`\_="8000 \fi
  \ifMTP@slops \let\sum\slsum\let\prod\slprod\let\coprod\slcoprod
  \else \let\sum\upsum\let\prod\upprod\let\coprod\upcoprod \fi}

\endinput
'''


def classic_defs(B: MathFontBuild) -> str:
    k, a = B.inp.classic["kernel"], B.inp.classic["amsmath"]
    lines = [d for n, d in k.items()]
    if a:
        lines.append("\\@ifpackageloaded{amsmath}{%\n" + "%\n".join(a.values()) + "%\n}{}")
    return "%\n".join(lines) + "%"


LEGACY_FAMS = {"operators": 0, "letters": 1, "symbols": 2, "largesymbols": 3}


def legacy_tex(builds: dict[str, MathFontBuild]) -> tuple[str, str]:
    """(mtpro2-otf-legacy.tex, mtpro2-otf-macros.tex): LaTeX's symbol families on the
    virtual MTPro2 fonts (preamble), and mtpro2.sty's own macros (\\widehat, \\overcbrace,
    \\PARENS, \\SQRT, \\xl, ...) verbatim from your mtpro2.sty (begin document); its \\font
    loads point at the virtual fonts."""
    B = builds["normal"]
    act, legacy = B.inp.act, set()
    for b in builds.values():
        legacy.update(b.legacy_fonts())
    vf = lambda text: re.sub(r"\b(mt2\w+)\b", lambda m: "mtp2vf:" + m.group(1) if m.group(1) in legacy
                             else m.group(1), text)
    out = ["% mtpro2-otf-legacy.tex: generated by mtpro2_otf.py from your mtpro2.sty - keep private",
           "% 1. LaTeX's symbol fonts (letters, symbols, largesymbols, AMSa) on the virtual fonts"]
    shapes = set()
    for line in act.splitlines():
        m = re.match(r"\\DeclareFontShape\{(\w+)\}\{(\w+)\}\{(\w+)\}\{(\w+)\}\{([^}]*)\}", line)
        if m:
            fonts = re.findall(r"mt2\w+", m.group(5))
            if fonts and all(f in legacy for f in fonts):
                shapes.add(m.group(1, 2, 3, 4))
                out.append(vf(line))
    encfam = {(e, f) for e, f, _, _ in shapes}
    heads = {"enc": [], "fam": []}                  # encodings, then families, before the shapes
    for line in act.splitlines():
        m = re.match(r"\\Declare(?:FontEncoding|FontSubstitution)\{(\w+)\}", line)
        if m and any(e == m.group(1) for e, _ in encfam):
            heads["enc"].append(line)
        m = re.match(r"\\DeclareFontFamily\{(\w+)\}\{(\w+)\}", line)
        if m and m.group(1, 2) in encfam:
            heads["fam"].append(line)
    out[2:2] = heads["enc"] + heads["fam"]
    for line in act.splitlines():
        arg = r"\s*\{(\w+)\}"
        m = (re.match(r"\\DeclareSymbolFont" + arg + "()" + arg * 4, line) or
             re.match(r"\\SetSymbolFont" + arg * 6, line))
        if m and m.group(1) in ("letters", "symbols", "largesymbols", "AMSa") and m.group(3, 4, 5, 6) in shapes:
            out.append(line)
    out.append("% 2. the extension fonts mtpro2.sty loads directly")
    m = re.search(r"\\dimen@\\f@size pt\n(.*?\\def\\getpoints@[^\n]*\n)", act, re.S)
    if m:
        out.append("\\begingroup\\normalsize\\expandafter\\endgroup\\expandafter\\dimen@\\f@size pt")
        out.append(vf(m.group(1)).rstrip())
    out.append("% 3. TeX's delimiter codes (for mtpro2.sty's \\PARENS, \\LEFTRIGHT, \\ccases)")
    defs = []
    for d in B.inp.decls:
        if d.kind == "delimiter" and d.fam in LEGACY_FAMS and d.fam2 in LEGACY_FAMS:
            code = (f'"{CLASSES.get(d.cls, 0):X}{LEGACY_FAMS[d.fam]:X}{d.slot:02X}'
                    f'{LEGACY_FAMS[d.fam2]:X}{d.slot2:02X}')
            if len(d.cmd) == 1:
                defs.append(f"\\delcode`\\{d.cmd}={'"' + code[2:]}")
            else:
                defs.append(f"\\def{d.cmd}{{\\delimiter{code} }}")
    out.append("\\def\\MTP@legacydelims{%\n" + "%\n".join(defs) + "%\n}")
    out.append("\\endinput")
    fonts_part, out = "\n".join(out) + "\n", [
        "% mtpro2-otf-macros.tex: generated by mtpro2_otf.py from your mtpro2.sty - keep private",
        "% mtpro2.sty's own macros, verbatim (they use the virtual fonts of mtpro2-otf-legacy.tex)"]
    for name in ("curlybraces", "straightbraces", "morphedbraces"):
        m = re.search(r"\\def\\" + name + r"\{.*?\n.*?\n", act)
        if m:
            out.append(m.group(0).rstrip())
    sty = B.inp.sty             # as written (the region has no option conditionals)
    i = sty.find("\\newbox\\prePbox@")              # from \PARENS's helpers ...
    k = max(sty.find("\\def\\undercbrace#1", i), sty.find("\\def\\overcbrace#1", i))   # ... to the braces
    if i >= 0 and k > 0:
        region = sty[i:braced(sty, sty.index("{", k))[1]]
        m = re.search(r"\\begingroup\s*\\catcode`\\_=13.*?\\mathcode`\\_=\\string\"8000", B.inp.sty, re.S)
        if m:                   # the subscript correction (active only with catcode 12 '_')
            region += "\n" + m.group(0)
        region = region.replace("\\curlybraces\\EXtest@@", "\\curlybraces\\MTP@legacydelims\\EXtest@@")
        # (\\{ and \\} are \\lbrace and \\rbrace to mtpro2.sty; with unicode-math they are
        # macros of their own: \\LEFTRIGHT\\{\\} must still take its brace path)
        region = region.replace("\\else\\specdelim@false\\fi",
                                "\\else\\ifx#1\\{\\specdelim@true\\else\\ifx#1\\}\\specdelim@true"
                                "\\else\\specdelim@false\\fi\\fi\\fi", 1)
        # the trial displays in \vbox{$$..$$}: TeX ends that box with an implicit \par,
        # which loops forever where \par is a no-op macro (longtable cells, TeX Live 2025+)
        out.append(region.replace("\\vbox{$$", "\\vbox{\\let\\par\\endgraf$$").rstrip())
    out.append("\\endinput")
    return fonts_part, "\n".join(out) + "\n"


def ams_fallbacks(B: MathFontBuild) -> list[str]:
    """amssymb's symbols that mtpro2.sty does not declare (Lite): the package keeps amssymb's
    definitions, as amssymb loaded before mtpro2.sty does with the Type 1 fonts."""
    out = []
    for name in ("amsfonts.sty", "amssymb.sty"):
        p = kpse(name)
        for cmd in re.findall(r"\\Declare(?:MathSymbol|MathDelimiter)\{?\\(\w+)\}?", p.read_text(
                encoding="latin-1")) if p else []:
            if cmd not in out and cmd.isalpha() and cmd not in B.commands:   # (not mtpro2.sty's)
                out.append(cmd)
    return out


def make_sty(B: MathFontBuild, date: str) -> str:
    over, prov = command_defs(B)
    z = B.commands.get("mtp@@z", (None, ""))[1]
    return (STY.replace("@@DATE@@", date).replace("@@OVERRIDES@@", "%\n".join(over) + "%")
            .replace("@@PROVIDES@@", "%\n".join(prov) + "%").replace("@@ZSWASH@@", z)
            .replace("@@EDITION@@", "Complete" if B.inp.complete else "Lite")
            .replace("@@VERSION@@", PACKAGE_VERSION)
            .replace("@@AMSLIST@@", ",".join(ams_fallbacks(B)) if not B.inp.complete else "")
            .replace("@@CLASSIC@@", classic_defs(B))
            .replace("@@AMSMATH@@", "%\n".join(f"\\renewcommand{{\\{c}}}{{{d.strip()}}}" for c, d in
                                              sorted(B.inp.amsmath_defs.items())) + "%"))


# ======================================================================
# 8. Driver
# ======================================================================

WEIGHTS = {"normal": ("MTPro2 Math", "MTPro2Math.otf"), "bold": ("MTPro2 Math Bold", "MTPro2Math-Bold.otf"),
           "heavy": ("MTPro2 Math Heavy", "MTPro2Math-Heavy.otf")}
DONORS = {"normal": "texgyretermes-regular.otf", "bold": "texgyretermes-bold.otf", "heavy": "texgyretermes-bold.otf"}


def convert(folder: Path, out: Path, weights=("normal", "bold", "heavy"), donor: Path | None = None,
            quiet: bool = False) -> dict[str, MathFontBuild]:
    inp = Inputs.load(folder)
    src = Source(inp.files)
    out.mkdir(parents=True, exist_ok=True)
    builds = {}
    for w in weights:
        if w != "normal" and not inp.complete:
            continue
        B = MathFontBuild(inp, src, w).build()
        family, fn = WEIGHTS[w]
        dn = donor or kpse(DONORS[w])
        write_otf(B, family, donor_glyphs(dn, DONOR_CPS) if dn else None).save(out / fn)
        builds[w] = B
        if not quiet:
            print(f"{fn}: {len(B.glyphs)} glyphs, {len(B.cmap)} code points")
    if "normal" in builds:
        reg = builds["normal"]
        # code points that the bold (heavy) font has only in a lighter weight: \\bm (\\hm)
        # gives them poor man's bold, as bm.sty does for a family without that weight
        reg.weight_params = {}
        for w, B in builds.items():
            if w != "normal":
                sz = [B.src.tfm(f).params for f in B.fam("symbols")]
                reg.weight_params[w] = {k: [p[i] for p in sz] for k, i in
                                        (("num1", 8), ("num2", 9), ("denom1", 11), ("denom2", 12),
                                         ("xheight", 5), ("axis", 22))}
                reg.weight_params[w]["rule"] = B.src.tfm(B.fam("largesymbols")[0]).params[8]
        reg.nobold = {}
        for w, B in builds.items():
            if w == "normal":
                continue
            # (a TeX family without fonts of this weight, like the letters for \\hm)
            lighter = {f for fam, v in reg.inp.symfonts.items() if w not in v for f in v.get("normal", ())}
            cps = {cp for cp, g in B.cmap.items() if g in B.from_fallback}
            cps |= {cp for cp, g in reg.cmap.items()
                    if g in reg.glyphs and reg.glyphs[g].ref and reg.glyphs[g].ref.font in lighter}
            reg.nobold[w] = sorted(cps)
        (out / "mtpro2-otf-variants.lua").write_text(variants_lua(reg))
        (out / "mtpro2-otf-dims.lua").write_text(packed_lua(dims_lua(builds), [
            "-- mtpro2-otf-dims.lua: generated by mtpro2_otf.py: TeX's glyph boxes by glyph index",
            "-- (metrics only, compressed; contains MTPro2 data: keep private)"]))
        (out / "mtpro2-otf-tfm.lua").write_text(packed_lua(tfm_lua(builds), [
            "-- mtpro2-otf-tfm.lua: generated by mtpro2_otf.py: MTPro2's TFM metrics with the glyph",
            "-- index of each character (no outlines, compressed; contains MTPro2 data: keep private)"]))
        fonts_part, macros_part = legacy_tex(builds)
        (out / "mtpro2-otf-legacy.tex").write_text(fonts_part, encoding="latin-1")
        (out / "mtpro2-otf-macros.tex").write_text(macros_part, encoding="latin-1")
        (out / "mtpro2-otf.lua").write_text(LUA)
        (out / "mtpro2-otf.sty").write_text(make_sty(reg, PACKAGE_DATE))
    for p in folder.rglob("*"):
        if p.is_file() and p.name.upper().startswith("EULA"):
            shutil.copy2(p, out / p.name)
    eulas = sorted({p.name for p in folder.rglob("*") if p.is_file() and p.name.upper().startswith("EULA")})
    write_manifest(out, [WEIGHTS[w][1] for w in builds] + (WRITTEN[3:] if "normal" in builds else []) + eulas)
    return builds


MANIFEST = "mtpro2-otf-manifest.txt"
WRITTEN = [WEIGHTS[w][1] for w in ("normal", "bold", "heavy")] + [
    "mtpro2-otf.sty", "mtpro2-otf.lua", "mtpro2-otf-variants.lua", "mtpro2-otf-dims.lua",
    "mtpro2-otf-tfm.lua", "mtpro2-otf-legacy.tex", "mtpro2-otf-macros.tex"]


def write_manifest(out: Path, names: list[str]):
    """List what the converter wrote; files listed by an earlier run that this run did not
    write (e.g. the Bold and Heavy fonts after switching from Complete to Lite) are removed.
    Nothing else in the folder is ever touched."""
    old = out / MANIFEST
    if old.exists():
        for line in old.read_text().splitlines():
            n = line.strip()
            if n and not n.startswith("#") and "/" not in n and n not in names and (out / n).is_file():
                (out / n).unlink()
    old.write_text("# files written by mtpro2_otf.py (contain MTPro2 data: keep private)\n"
                   + "\n".join(names) + "\n")


# ======================================================================
# 9. Self-test: typeset formulas with the Type 1 fonts (mtpro2.sty) and with the
#    OpenType fonts (mtpro2-otf.sty) and compare the pages pixel by pixel
# ======================================================================

SELFTEST_FORMULAS = [
    'x^2',
    'x_i^2',
    'x_{i,j}^{k+1}',
    'e^{-x^2}',
    "f'(x)",
    "f''(y)",
    'a_{n_k}',
    '2^{2^n}',
    '\\frac{a}{b}',
    '\\frac{1}{1+x^2}',
    '\\displaystyle\\frac{a}{b}',
    '\\displaystyle\\frac{\\partial^2 u}{\\partial x^2}',
    '\\tfrac12',
    '\\dfrac{n!}{k!(n-k)!}',
    '\\binom{n}{k}',
    '\\displaystyle\\binom{n}{k}',
    '\\sqrt{x}',
    '\\sqrt{x^2+y^2}',
    '\\sqrt[3]{x}',
    '\\displaystyle\\sqrt{\\frac{a}{b}}',
    '\\sqrt{\\sqrt{x}}',
    '\\sum_{i=1}^n a_i',
    '\\displaystyle\\sum_{i=1}^n a_i',
    '\\displaystyle\\prod_{k=1}^\\infty',
    '\\displaystyle\\int_0^1 f(x)\\,dx',
    '\\int_0^\\infty',
    '\\displaystyle\\oint_C',
    '\\displaystyle\\iint_D',
    '\\displaystyle\\lim_{n\\to\\infty}',
    '\\displaystyle\\max_{x\\in X}',
    '\\displaystyle\\bigcup_{i\\in I}A_i',
    '\\left(\\frac{a}{b}\\right)',
    '\\left[\\frac{a}{b}\\right]',
    '\\left\\{\\frac{a}{b}\\right\\}',
    '\\left|\\frac{a}{b}\\right|',
    '\\left\\langle\\frac{a}{b}\\right\\rangle',
    '\\displaystyle\\left(\\sum_{i=1}^n a_i\\right)',
    '\\bigl(x\\bigr)',
    '\\Bigl(x\\Bigr)',
    '\\biggl(x\\biggr)',
    '\\Biggl(x\\Biggr)',
    '\\Bigl[x\\Bigr]',
    '\\Bigl\\{x\\Bigr\\}',
    '\\Bigl\\langle x\\Bigr\\rangle',
    '\\Bigl| x\\Bigr|',
    '\\Bigl\\| x\\Bigr\\|',
    '\\hat{x}',
    '\\hat{A}',
    '\\bar{z}',
    '\\vec{v}',
    '\\tilde{n}',
    '\\dot{x}\\ddot{y}',
    '\\widehat{AB}',
    '\\widetilde{xyz}',
    '\\overline{x+y}',
    '\\underline{x+y}',
    'a+b-c',
    'a\\le b\\ge c',
    'a=b\\ne c',
    'x\\in A\\subseteq B',
    'f\\colon X\\to Y',
    'a\\cdot b\\times c',
    '(a,b]',
    '\\{x\\mid x>0\\}',
    '\\|x\\|',
    '\\mathbb{R}^n',
    '\\mathcal{O}(n)',
    '\\mathfrak{g}',
    '\\alpha\\beta\\gamma\\delta',
    '\\Gamma\\Delta\\Theta',
    '\\infty\\partial\\nabla',
    '\\cdots\\ldots',
    '\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}',
    '\\begin{cases}1&x>0\\\\0&x\\le0\\end{cases}',
    'x_1^2+x_2^2',
    '\\lim_{x\\to0}\\frac{\\sin x}{x}',
    '\\displaystyle\\sum_{\\substack{i<j\\\\i,j\\in S}} a_{ij}',
    'e^{i\\pi}+1=0',
    '\\int\\!\\!\\int f',
    '\\frac{\\frac{a}{b}}{\\frac{c}{d}}',
    '\\displaystyle\\frac{1}{\\sqrt{2\\pi}}',
    '\\left(\\frac{\\displaystyle\\sum_{i}x_i}{n}\\right)^{\\!2}',
    '\\Biggl\\{\\biggl[\\Bigl(\\bigl(x\\bigr)\\Bigr)\\biggr]\\Biggr\\}',
    '\\left\\lfloor\\frac{n}{2}\\right\\rfloor',
    '\\left\\lceil x\\right\\rceil',
    '\\left.\\frac{df}{dx}\\right|_{x=0}',
    '\\overbrace{a+b+c}^{n}',
    '\\underbrace{x+\\cdots+x}_{k}',
    '\\overrightarrow{AB}',
    '\\bar{\\bar{x}}',
    '\\hat{\\imath}\\,\\vec{\\jmath}',
    '\\tilde{\\mathcal{A}}',
    '\\widetilde{abcdef}',
    '\\check{c}\\breve{u}\\acute{e}\\grave{a}',
    'A\\otimes B\\oplus C',
    'f\\circ g',
    'a\\equiv b\\pmod{n}',
    'x\\mapsto x^2',
    'A\\Rightarrow B\\iff C',
    '\\forall\\epsilon>0\\;\\exists\\delta',
    '\\aleph_0<2^{\\aleph_0}',
    '\\hbar\\omega',
    '\\ell^p',
    '\\Re z+\\Im z',
    '\\varphi\\vartheta\\varepsilon\\varrho',
    '\\Sigma\\Pi\\Omega\\Xi',
    '\\mathbf{v}\\cdot\\mathbf{w}',
    '\\bm{\\alpha}+\\bm{x}',
    '\\mathrm{d}x\\,\\mathrm{d}y',
    '\\sin^2\\theta+\\cos^2\\theta',
    '\\log_2 n',
    '\\det A^{-1}',
    '\\begin{bmatrix}1&0\\\\0&1\\end{bmatrix}',
    '\\begin{vmatrix}a&b\\\\c&d\\end{vmatrix}',
    '\\displaystyle\\int_{-\\infty}^{\\infty}e^{-x^2}\\,dx=\\sqrt{\\pi}',
    '\\sum\\nolimits_{k} a_k',
    '\\prod_{p}\\frac{1}{1-p^{-s}}',
    '\\displaystyle\\bigcap_{n=1}^\\infty A_n',
    '\\displaystyle\\bigoplus_{i} V_i',
    '\\coprod_i X_i',
    '\\langle x,y\\rangle',
    '\\lvert x\\rvert',
    '\\lVert x\\rVert',
    'a\\mid b\\nmid c',
    'x\\leqslant y\\geqslant z',
    'A\\subsetneq B\\supseteq C',
    '\\emptyset\\varnothing',
    'x\\notin\\mathbb{Q}',
    'n!\\binom{n}{k}^{-1}',
    '\\sqrt[n]{x^n+y^n}',
    '\\sqrt{1+\\sqrt{1+\\sqrt{x}}}',
    '\\displaystyle\\lim_{n\\to\\infty}\\Bigl(1+\\frac1n\\Bigr)^n',
    'f^{(n)}(x)',
    'x^{y^{z}}',
    '{}_2F_1',
    '\\dot{x}=Ax+Bu',
    '\\nabla\\times\\mathbf{E}=-\\partial_t\\mathbf{B}',
    '\\xl\\sum_{i=1}^n',
    '\\XL\\int_0^1',
    '\\overcbrace{a+b+c+d}^{4}',
    'x\\longrightarrow y\\longleftarrow z',
    'A\\Longrightarrow B\\Longleftarrow C',
    'f\\colon A\\hookrightarrow B',
    'a\\doteq b',
    'x\\longmapsto y',
    'P\\Longleftrightarrow Q',
    '\\hbar\\neq\\hslash',
    '\\PARENS{\\frac{a}{b}}',
    '\\PARENS{\\displaystyle\\sum_{i=1}^n\\frac{x_i}{y_i}}',
    '\\widehat{xyz}',
    '\\widetilde{ABCDEFGH}',
    '\\widecheck{uv}',
    '\\widearc{AB}',
    '\\SQRT{x}',
    '\\SQRT[3]{x^2+1}',
    '\\LEFTRIGHT\\langle\\rangle{\\frac{a}{b}}',
    '\\ccases{1&x>0\\\\0&x\\le0}',
    '\\undercbrace{x_1+x_2+x_3}_{n}',
    '\\overcbrace{a+b+c+d+e+f+g+h+i}^{9}',
    '\\XXXL\\int_0^1',
    '\\XXL\\bigcup_{i}',
    '\\left(x\\right)',
    '\\left\\langle x\\right\\rangle',
    '\\hat{f}\\tilde{g}\\bar{h}\\vec{k}',
    '\\mathscr{C\\altC}\\mathcal{G}',
    '\\mathscr{\\altC\\altG\\altz}',
    '\\mathfrak{\\altY\\alty}',
    '\\bm{x+\\alpha}\\hm{y}',
    '\\mathbb{RN}',
    '\\Biggl\\{x\\Biggr\\}',
    'x_{\\hat{a}}',
    'e^{\\tilde{x}+\\bar{y}}',
    '2^{\\vec{v}}',
    'x_{\\widehat{ab}}',
    '\\frac{\\hat{a}}{\\dot{b}}',
    'f_{\\frac12}',
    'f_{(a)}',
    'P_{\\mathrm{ab}}',
    'V_{\\!a}',
    'T_{-1}',
    'x_{\\alpha}^{\\hat b}',
    '\\Gamma_{i}^{j}',
    '\\hat{x}_i',
    '\\tilde{V}_{i}^{2}',
    '{x}_i',
    'f_{\\mathbb{R}}',
    'y_{\\sqrt{a}}',
    'x^{\\sqrt{\\frac{a}{b}}}',
    'e^{\\sqrt[3]{x}}',
    '\\frac{\\sqrt{a}}{\\sqrt{b}}',
    'x_{\\sqrt{y_{\\sqrt{z}}}}',
    '\\boldmath x+\\alpha\\sum_{i}',
    '\\mathversion{heavy}\\sum_{i}\\int',
    '\\bm{\\hat{x}}_i',
    '\\bm{x}_i',
    '\\displaystyle\\int\\limits_0^1 f',
    '\\displaystyle\\sum\\nolimits_{i} a_i',
    '\\sum\\limits_{i=1}^n',
    '\\displaystyle\\slsum_{i=1}^n\\slprod_k',
    '\\textstyle\\slsum\\limits_{i}',
    '\\bm{\\alpha}_k',
    '\\bm{\\Gamma}^2',
    '\\hm{y}_j',
    '\\bm{\\tilde{n}}',
    '\\bm{\\sum}',
    '\\bm{2\\pi r}',
    '\\bm{\\mathcal{A}}+\\bm{\\partial f}',
    '\\bm{\\int_0^1 f}',
    'a\\bm{\\le}b',
    '\\bm{\\epsilon\\varepsilon\\phi\\varphi\\vartheta\\ell}',
    '\\bm{a^{2}_{k}}',
    '\\bm{\\sqrt{y}}',
    'x_{\\bm{v}+\\bm{w}}',
    '\\bm{A}\\bm{x}=\\bm{b}',
    '\\mathbf{A}^{T}\\mathbf{x}',
    '\\mathrm{d}x\\wedge\\mathrm{d}y',
    '\\mathit{diff}',
    '\\operatorname{tr}(A)',
    '\\lim\\sup_{n}x_n',
    '\\left(\\begin{array}{cc}a&b\\\\c&d\\end{array}\\right)',
    '\\sum_{\\substack{0\\le i\\le m\\\\0<j<n}}P(i,j)',
    '\\int_{\\partial\\Omega}u\\,\\nabla v\\cdot n\\,ds',
    '\\|u\\|_{H^1(\\Omega)}^2',
    "u''(x)+u'(x)",
    '\\mathcal{L}\\{f\\}(s)',
    '\\overline{\\overline{AB}}',
    '\\underline{\\underline{x}}',
    'x\\overset{!}{=}y',
    '\\xrightarrow{f}',
    '\\stackrel{\\mathrm{def}}{=}',
]

def stress_formulas(inp: "Inputs") -> list[tuple[str, str]]:
    """--stress: many more formulas, (family, formula), grouped by where TeX and OpenType math
    differ (glyph boxes and italic corrections, per-size parameters, kerns, growing symbols,
    the engine's own rules for scripts, limits, radicals and accents, \\bm, mtpro2.sty's
    macros). Generated from the declarations, so every symbol command is covered."""
    out: list[tuple[str, str]] = []
    add = lambda fam, *fs: out.extend((fam, f) for f in fs)
    syms = [d for d in inp.decls if d.kind == "symbol" and d.cmd.startswith("\\") and "@" not in d.cmd]
    cls = {d.cmd: d.cls for d in syms}
    ords = [d.cmd for d in syms if d.cls in ("\\mathord", "\\mathalpha")]
    bins = [d.cmd for d in syms if d.cls == "\\mathbin"]
    rels = [d.cmd for d in syms if d.cls == "\\mathrel"]
    ops = [d.cmd for d in syms if d.cls == "\\mathop"]
    latin = [chr(c) for c in range(65, 91)] + [chr(c) for c in range(97, 123)]
    greek = [c for c in ords if c.lstrip("\\") in GREEK]
    letters = latin + greek
    # 1. every symbol command, alone and between letters (boxes, classes, spacing)
    for d in syms:
        k = d.cmd
        if cls[k] == "\\mathop":
            add("symbol", f"{k}", f"\\displaystyle{k}")
        elif cls[k] == "\\mathbin":
            add("symbol", f"a{k} b")
        elif cls[k] == "\\mathrel":
            add("symbol", f"a{k} b")
        else:
            add("symbol", f"{k}", f"x{k} y")
    # 2. scripts on every letter and ordinary symbol: italic correction and the subscript
    #    tuck, also where the subscript starts with something that is not a character
    for k in letters + [c for c in ords if c not in greek][:80]:
        add("scripts", f"{k}_i", f"{k}^2", f"{k}_i^2", f"{k}_{{ij}}^{{2}}")
    for k in ["f", "T", "V", "W", "P", "Y", "\\Gamma", "\\Upsilon", "\\Psi", "\\beta", "\\rho"]:
        add("scripts-compound", f"{k}_{{\\frac12}}", f"{k}_{{\\sqrt{{x}}}}", f"{k}_{{\\mbox{{a}}}}",
            f"{k}_{{}}^2", f"{k}_{{\\scriptscriptstyle i}}", f"{k}_{{x_i}}", f"{k}_{{(n)}}",
            f"{k}_{{.}}", f"{k}'", f"{k}''_i", f"{k}^{{\\prime}}_{{\\!i}}", f"{{{k}}}_i",
            f"\\mathop{{{k}}}\\nolimits_i", f"{k}_{{\\left(x\\right)}}")
    # 3. accents on letters (italic corrections, skew kerns, scripts, sizes)
    accents = [d.cmd for d in inp.decls if d.kind == "accent" and "@" not in d.cmd]
    for a in accents:
        for k in ["a", "f", "x", "A", "T", "W", "\\alpha", "\\Gamma", "i", "j", "\\imath"]:
            add("accent", f"{a}{{{k}}}")
        add("accent", f"x_{{{a}{{a}}}}", f"{a}{{x}}_i^2", f"{a}{{{a}{{x}}}}", f"{a}{{xy}}")
    for a in ("\\widehat", "\\widetilde", "\\overline", "\\underline", "\\overrightarrow"):
        for k in ["x", "xy", "xyz", "xyzw", "ABCDEF", "x_1+\\cdots+x_n"]:
            add("wide", f"{a}{{{k}}}")
    # 4. kerns: the TFM's largest letter pairs (TeX applies them between ordinary characters)
    by_slot = {d.slot: d.cmd for d in syms if d.fam == "letters"}
    for c in latin:
        by_slot.setdefault(ord(c), c)
    kerns = sorted(((abs(k), a, b) for (a, b), k in inp_kerns(inp).items()
                    if a in by_slot and b in by_slot), reverse=True)
    for _, a, b in kerns[:150]:
        add("kern", f"{by_slot[a]} {by_slot[b]}", f"{by_slot[a]} {by_slot[b]}_i")
    add("kern", "\\partial f", "\\partial_x f", "A\\Alpha V", "x|y|", "x\\mid y", "\\nabla f")
    # 5. operators: limits, display/text, scripts
    for o in ops:
        add("operator", f"{o}_{{i=1}}^n", f"\\displaystyle{o}_{{i=1}}^n", f"\\displaystyle{o}\\limits_i",
            f"{o}\\limits_{{i}}^{{n}}", f"\\displaystyle{o}\\nolimits_i^n", f"x_{{{o}_i}}")
    # 6. growing symbols: every delimiter around content of increasing height
    delims = [d.cmd for d in inp.decls if d.kind == "delimiter" and "@" not in d.cmd] + ["(", "[", "|", "\\|", "/"]
    tall = ["x", "x^2", "\\frac{a}{b}", "\\dfrac{a}{b}", "\\frac{\\frac{a}{b}}{c}",
            "\\begin{matrix}a\\\\b\\\\c\\end{matrix}", "\\begin{matrix}a\\\\b\\\\c\\\\d\\\\e\\end{matrix}",
            "\\begin{matrix}a\\\\b\\\\c\\\\d\\\\e\\\\f\\\\g\\\\h\\end{matrix}"]
    for d in dict.fromkeys(delims):
        for t in tall:
            add("delimiter", f"\\left{d} {t}\\right.")
        for b in ("\\big", "\\Big", "\\bigg", "\\Bigg"):
            add("delimiter", f"{b}{d}")
    # 7. radicals: heights, degrees, scripts
    for t in tall[:6] + ["\\sqrt{x}", "\\sqrt{\\sqrt{x}}"]:
        add("radical", f"\\sqrt{{{t}}}", f"\\sqrt[3]{{{t}}}", f"x_{{\\sqrt{{{t}}}}}", f"x^{{\\sqrt{{{t}}}}}")
    # 8. fractions and stacks in every style
    for st in ("\\displaystyle", "\\textstyle", "\\scriptstyle", "\\scriptscriptstyle"):
        add("fraction", f"{st}\\frac{{a}}{{b}}", f"{st}\\binom{{n}}{{k}}", f"{st}{{a\\atop b}}",
            f"{st}\\frac{{x^2}}{{y_i}}", f"{st}\\overline{{x}}", f"{st}\\underline{{y}}",
            f"{st}\\overbrace{{a+b}}^{{n}}", f"{st}\\underbrace{{a+b}}_{{n}}", f"{st}\\stackrel{{a}}{{=}}",
            f"{st}\\sqrt{{x}}", f"{st} x_i^2", f"{st}\\hat{{x}}")
    # 8b. alphabets: grouping (scripts attach to the whole), kerns, the alternates
    for al in ("\\mathscr", "\\mathcal", "\\mathfrak", "\\mathbb", "\\mathbf", "\\mathrm",
               "\\mathit", "\\mathsf", "\\mathtt", "\\mathcurly", "\\mathbbdark"):
        add("alphabet", f"{al}{{A}}", f"{al}{{AB}}^2", f"{al}{{xy}}_i", f"x{al}{{T}}y",
            f"{al}{{A}}{al}{{V}}", f"\\hat{{{al}{{A}}}}", f"{al}{{A}}'")
    add("alphabet", "\\mathscr{\\altC\\altG\\altz}", "\\mathfrak{\\altY\\alty\\altx}",
        "\\mathcurly{\\altG\\altM\\altN\\altQ\\altY}", "\\mathcal{\\altC}x",
        "\\mathscr{A\\altL}^2", "\\mathfrak{g}_{\\altY}")
    # 9. \bm on all of the above kinds
    for f in ["x", "\\alpha", "\\Gamma", "2", "+", "=", "\\le", "\\sum", "\\int", "\\partial",
              "\\nabla", "\\infty", "\\hat{x}", "\\vec{v}", "\\widehat{xy}", "x_i^2", "\\frac{a}{b}",
              "\\sqrt{x}", "\\sqrt[3]{x}", "\\left(x\\right)", "(x)", "\\sum_{i=1}^n x_i",
              "\\mathcal{A}", "\\mathbb{R}", "\\mathfrak{g}", "\\mathrm{d}", "\\mathbf{x}",
              "f'", "\\cdot", "\\times", "\\{x\\}", "|x|", "\\langle x\\rangle", "\\ell", "\\imath"]:
        add("bm", f"\\bm{{{f}}}", f"a\\bm{{{f}}}b", f"x_{{\\bm{{{f}}}}}")
    add("bm", "\\hm{x+\\alpha}", "\\hm{\\sum}", "\\hm{\\partial f}", "\\bm{x}\\hm{x}x")
    # 10. mtpro2.sty's macros
    for o in ("\\sum", "\\prod", "\\int", "\\oint", "\\bigcup", "\\bigoplus"):
        for x in ("\\xl", "\\XL", "\\XXL", "\\XXXL"):
            add("macro", f"{x}{o}_{{i=1}}^n")
    for t in ("x", "\\frac{a}{b}", "\\dfrac{a}{b}", "\\begin{matrix}a\\\\b\\\\c\\end{matrix}"):
        add("macro", f"\\PARENS{{{t}}}", f"\\LEFTRIGHT[]{{{t}}}", f"\\LEFTRIGHT\\{{\\}}{{{t}}}",
            f"\\LEFTRIGHT\\langle\\rangle{{{t}}}", f"\\LEFTRIGHT||{{{t}}}", f"\\SQRT{{{t}}}", f"\\SQRT[n]{{{t}}}")
    add("macro", "\\ccases{1&x>0\\\\0&x\\le0}", "\\ccases{a&b\\\\c&d\\\\e&f}",
        "\\overcbrace{a+b}^{2}", "\\undercbrace{a+b+c}_{3}", "\\widearc{AB}", "\\widearc{ABCD}",
        "\\ROOT 3\\OF{x}", "\\UPROOT{2}\\LEFTROOT{-1}\\SQRT[3]{x}")
    return out


def inp_kerns(inp: "Inputs") -> dict:
    """The TFM kerns of the math italic font (text size)."""
    path = inp.files.get("mt2mit.tfm")
    return read_tfm(path).kerns if path else {}


SELFTEST_DOC = r"""\documentclass{article}
\usepackage{fontspec}\setmainfont{TeX Gyre Termes}
\usepackage{amsmath}
%s
\directlua{dofile("selftest-dump.lua")}
\pdfvariable horigin=0pt \pdfvariable vorigin=0pt
\pagewidth=8cm \pageheight=3cm
\begin{document}
%s
\end{document}
"""

# writes the position of every glyph and rule of box 0 to <job>.pos (pt, origin = box origin)
SELFTEST_LUA = r"""
local out = io.open(tex.jobname .. ".pos", "w")
local GLYPH, HLIST, VLIST, RULE, KERN, GLUE = node.id("glyph"), node.id("hlist"), node.id("vlist"),
  node.id("rule"), node.id("kern"), node.id("glue")
local RUNNING = -1073741824
local function walk(box, x, y, items)
  local vertical = box.id == VLIST
  if vertical then y = y - box.height end
  local n = box.list
  while n do
    local id = n.id
    if id == GLYPH then
      if vertical then y = y + n.height end
      items[#items + 1] = {"G", x + n.xoffset, y - n.yoffset, n.width, n.height, n.depth}
      if vertical then y = y + n.depth else x = x + n.width end
    elseif id == HLIST or id == VLIST then
      if vertical then
        y = y + n.height; walk(n, x + n.shift, y, items); y = y + n.depth
      else
        walk(n, x, y + n.shift, items); x = x + n.width
      end
    elseif id == RULE then
      local w, h, d = n.width, n.height, n.depth
      if w == RUNNING then w = box.width end
      if h == RUNNING then h = box.height end
      if d == RUNNING then d = box.depth end
      if vertical then y = y + h end
      if w > 0 and h + d > 0 then items[#items + 1] = {"R", x, y, w, h, d} end
      if vertical then y = y + d else x = x + w end
    elseif id == KERN then
      if vertical then y = y + n.kern else x = x + n.kern end
    elseif id == GLUE then
      local g = node.effective_glue(n, box)
      if vertical then y = y + g else x = x + g end
    end
    n = n.next
  end
end
function selftestdump(k)
  local items = {}
  walk(tex.box[k], 0, 0, items)
  local b = tex.box[k]
  out:write(string.format("F %d %d %d\n", b.width, b.height, b.depth))
  for _, t in ipairs(items) do out:write(table.concat(t, " "), "\n") end
  out:flush()
end
"""


def selftest_positions(path: Path) -> list[dict]:
    """<job>.pos -> per formula {box: (w, h, d), items: [(kind, x, y, w, h, d)]} in pt."""
    out = []
    for line in path.read_text().splitlines():
        f = line.split()
        if f[0] == "F":
            out.append({"box": tuple(int(v) / 65536 for v in f[1:]), "items": []})
        else:
            out[-1]["items"].append((f[0],) + tuple(float(v) / 65536 for v in f[1:]))
    return out


def same_layout(a: dict, b: dict, tol: float = 0.01) -> str | None:
    """None if every glyph and rule sits where TeX puts it, else a short description.
    Glyph boxes may differ in height/depth by a uniform vertical shift (glyphs that are
    centred in the font rather than at run time) and in width (italic corrections)."""
    if abs(a["box"][0] - b["box"][0]) > tol:
        return f"width {a['box'][0]:.3f}pt vs {b['box'][0]:.3f}pt"
    ia = sorted(a["items"], key=lambda t: (round(t[1], 1), round(t[2], 1)))
    ib = sorted(b["items"], key=lambda t: (round(t[1], 1), round(t[2], 1)))
    if len(ia) != len(ib):      # composed glyphs (\cdots, '') - compare the extents
        ext = lambda its: (min(t[1] for t in its), max(t[1] + t[3] for t in its))
        ea, eb = ext(ia), ext(ib)
        ok = all(abs(x - y) <= tol for x, y in zip(ea, eb))
        return None if ok else f"extent {ea[0]:.2f}-{ea[1]:.2f}pt vs {eb[0]:.2f}-{eb[1]:.2f}pt"
    def offset(p, q):
        dy, dh, dd = q[2] - p[2], q[4] - p[4], q[5] - p[5]
        if p[0] == "G" and abs(dh + dd) < 0.03 and abs(dh) > 0.03:
            dy -= dh
        d = max(abs(q[1] - p[1]), abs(dy))
        if p[0] == "R":
            d = max(d, abs(q[3] - p[3]), abs(dh), abs(dd))
        return d if p[0] == q[0] else 1e9
    worst, left = 0.0, list(ib)
    for p in ia:                # pair every item with the nearest one of the same kind
        q = min(left, key=lambda q: offset(p, q))
        left.remove(q)
        worst = max(worst, offset(p, q))
    return None if worst <= tol else f"an item {worst:.3f}pt off"


T1_SCALE = r"""\directlua{
  local scale = %s
  local desc = luatexbase.callback_descriptions("define_font")[1]
  local define = luatexbase.remove_from_callback("define_font", desc)
  luatexbase.add_to_callback("define_font", function(name, size, id)
    if size > 0 and (name:match("^mt2") or name:match("^cmb?sy") or name:match("^msbm") or
        name:match("^msam") or name:match("^eu[sf]") or name:match("^ntx")) then size = math.floor(size * scale + 0.5) end
    return define(name, size, id)
  end, "selftest.mtpro2-scale")}"""


def selftest(folder: Path, work: Path | None = None, dpi: int = 600, options: str | None = None,
             scale: float = 1.0, stress: bool = False) -> int:
    """Build the fonts, typeset SELFTEST_FORMULAS with the Type 1 fonts (mtpro2.sty) and the
    OpenType fonts (mtpro2-otf.sty); compare where TeX placed every glyph and rule, and the
    rendered pages (which also differ where the rasteriser hints the Type 1 fonts)."""
    for tool in ("lualatex", "pdftoppm"):
        if not shutil.which(tool):
            sys.exit(f"error: --selftest needs {tool}")
    try:
        from PIL import Image, ImageChops
    except ImportError:
        Image = None
        print("(Pillow not installed: skipping the pixel comparison)")
    import os
    import tempfile
    work = Path(work or tempfile.mkdtemp(prefix="mtpro2-selftest-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    print(f"building the fonts in {work}")
    convert(folder, work / "Fonts", quiet=True)     # in a subfolder, found through TEXINPUTS
    try:                                            # optional: pip install opentype-sanitizer
        import ots
        for p in sorted((work / "Fonts").glob("MTPro2Math*.otf")):
            r = ots.sanitize(str(p), os.devnull, capture_output=True, text=True)
            print(f"OTS (font validator): {p.name}: {'OK' if r.returncode == 0 else r.stderr.strip()}")
    except ImportError:
        pass
    complete = Inputs.load(folder).complete
    opts = f"[{options}]" if options else "[complete,mtpscr,mtpcal,mtpfrak,mtpbb]" if complete else "[lite]"
    formulas = list(SELFTEST_FORMULAS)
    family = {f: "basic" for f in formulas}
    if stress:                                  # (layout only: no pixel comparison)
        for fam, f in stress_formulas(Inputs.load(folder)):
            # (Lite: the Type 1 reference takes \\bm from newtx's math italic, whose slots
            # match MTPro2's letters font only for letters, Greek and digits)
            if not complete and fam == "bm" and re.search(r"[^\\a-zA-Z0-9{}_ ^]|\\(?!bm|hm|alpha|Gamma|ell|imath|partial)", f):
                continue
            if f not in family:
                family[f] = fam
                formulas.append(f)
        Image = None
    if not complete:
        # (no reference: with mtpro2.sty, bm takes an upright capital Greek from the bold
        # letters font, which newtx's has not, and \hm finds mtpro2.sty's heavy version, whose
        # missing fonts NFSS replaces with the normal ones; the package uses newtx's bold text
        # Greek, and \hm is \bm as with bm.sty when there is no heavy version)
        pat = r"\\hm\b" if "slantedGreek" in (options or "") else r"\\bm\{\\[A-Z]|\\hm\b"
        if not subprocess.run(["kpsewhich", "ntxbmi.tfm"], capture_output=True, text=True).stdout.strip():
            pat = r"\\[bh]m\b"   # (no newtx: no bold letters for the Type 1 reference)
            print("(newtx not installed: skipping the \\bm formulas)")
        formulas = [f for f in formulas if not re.search(pat, f)]
    body = "\n".join(r"\setbox0\hbox{$%s$}\directlua{selftestdump(0)}"
                     r"\shipout\vbox to 3cm{\kern2cm\hbox{\kern0.5cm\smash{\box0}}\vss}"
                     r"\setbox2\vbox{\noindent\hbox{}\par}" % f
                     for f in formulas)
    (work / "selftest-dump.lua").write_text(SELFTEST_LUA)
    t1_scale = T1_SCALE % scale if scale != 1 else ""      # Type 1: scaled as the fonts load
    otf_opts = opts if scale == 1 else f"[{opts.strip('[]')},scale={scale}]"
    # Lite: the AMS symbols, blackboard bold and Fraktur from amssymb, script from Euler, as the
    # package (and the thesis template's Type 1 set-up) does
    lite_t1 = "" if complete else r"\usepackage{amssymb}"
    # (and bm without bold MTPro2 fonts: newtx bold letters, the text font's bold digits,
    # bold alphabets, poor man's bold for the rest)
    lite_t1b = "" if complete else (r"\DeclareMathAlphabet{\mathscr}{U}{eus}{m}{n}"
        r"\SetMathAlphabet{\mathscr}{bold}{U}{eus}{b}{n}"
        r"\SetSymbolFont{letters}{bold}{OML}{ntxmi}{b}{it}"
        r"\SetSymbolFont{symbols}{bold}{LMP2}{mtt}{m}{n}"
        r"\SetSymbolFont{largesymbols}{bold}{LMP3}{mtt}{m}{n}")
    (work / "st_t1.tex").write_text(SELFTEST_DOC % (t1_scale + r"\pdfextension mapfile{+mtpro2.map}" + lite_t1 +
                                                    r"\usepackage%s{mtpro2}" % opts + lite_t1b + r"\usepackage{bm}", body))
    (work / "st_otf.tex").write_text(SELFTEST_DOC % (r"\usepackage%s{mtpro2-otf}" % otf_opts, body))
    mt = str(folder.resolve()) + "//"
    env = dict(os.environ, TEXINPUTS=f"./Fonts:.:{mt}:", TFMFONTS=f".:{mt}:", T1FONTS=f".:{mt}:",
               TEXFONTMAPS=f".:{mt}:")         # (the package needs nothing but TEXINPUTS)
    env.pop("OPENTYPEFONTS", None)
    env.pop("LUAINPUTS", None)
    skipped = set()
    for job in ("st_t1", "st_otf"):
        subprocess.run(["lualatex", "-interaction=nonstopmode", job + ".tex"],
                       cwd=work, env=env, capture_output=True, text=True)
        log = (work / f"{job}.log").read_text(errors="replace") if (work / f"{job}.log").exists() else ""
        if not (work / f"{job}.pdf").exists():
            print(f"error: {job}.tex failed, see {work / job}.log")
            return 1
        tex = (work / f"{job}.tex").read_text().splitlines()
        start = next(i for i, l in enumerate(tex) if l.startswith("\\setbox0")) + 1
        for m in re.finditer(r"^l\.(\d+) ", log, re.M):    # formulas with TeX errors
            if 0 <= int(m.group(1)) - start < len(formulas):
                skipped.add(int(m.group(1)) - start)
    pa, pb = selftest_positions(work / "st_t1.pos"), selftest_positions(work / "st_otf.pos")
    keep = [i for i in range(len(formulas)) if i not in skipped]
    n = len(keep)
    layout = {i: same_layout(pa[i], pb[i]) for i in keep}
    print(f"layout: {sum(m is None for m in layout.values())}/{n} formulas with every glyph and rule "
          f"where TeX puts it (within 0.01pt)")
    if stress:
        fams = {}
        for i in keep:
            t = fams.setdefault(family[formulas[i]], [0, 0])
            t[0] += layout[i] is None
            t[1] += 1
        print("  by family: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in fams.items()))
    for i, msg in layout.items():
        if msg:
            print(f"  {formulas[i]:55s} {msg}")
    if skipped:
        print(f"  ({len(skipped)} formulas skipped: TeX errors, e.g. commands your fonts lack: "
              + ", ".join(formulas[i] for i in sorted(skipped)[:3]) + (", ..." if len(skipped) > 3 else "") + ")")
    if Image is None:
        return 0 if all(m is None for m in layout.values()) else 1
    for job in ("st_t1", "st_otf"):
        for p in work.glob(f"{job}-*.png"):
            p.unlink()
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", job + ".pdf", job], cwd=work, check=True)
    pages = lambda job: sorted(work.glob(f"{job}-*.png"))
    ink = lambda img: img.histogram()[255]
    same, report = 0, []
    for i, (fa, fb) in enumerate(zip(pages("st_t1"), pages("st_otf"))):
        if i in skipped:
            continue
        a = Image.open(fa).convert("L").point(lambda v: 255 if v < 128 else 0, "1")
        b = Image.open(fb).convert("L").point(lambda v: 255 if v < 128 else 0, "1")
        diff = ink(ImageChops.logical_xor(a, b)) / max(ink(a), 1)
        if diff < 0.02:
            same += 1
        else:
            report.append((formulas[i], diff))
            ov = Image.merge("RGB", [ImageChops.invert(b.convert("L")), ImageChops.invert(
                ImageChops.logical_or(a, b).convert("L")), ImageChops.invert(a.convert("L"))])
            ov.save(work / f"diff-{i + 1:02d}.png")
    print(f"pixels: {same}/{n} formulas render the same at {dpi} dpi (ink difference < 2%)")
    for f, d in report:
        print(f"  {f:55s} ink difference {d * 100:4.1f}%")
    if report:
        print(f"  overlays (red: Type 1 only, blue: OpenType only): {work}/diff-NN.png")
    return 0 if all(m is None for m in layout.values()) else 1


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Convert MathTime Pro 2 to OpenType MATH (+ mtpro2-otf package).")
    ap.add_argument("mtpro2", type=Path, help="folder with your MTPro2 files (searched recursively)")
    ap.add_argument("output", type=Path, nargs="?", help="output folder")
    ap.add_argument("--weights", default="regular,bold,heavy", help="comma list of regular,bold,heavy")
    ap.add_argument("--donor", type=Path, help="upright Times-like OTF for Latin letters (default: TeX Gyre Termes)")
    ap.add_argument("--zip", action="store_true", help="also write OUTPUT.zip")
    ap.add_argument("--selftest", action="store_true", help="compare against the Type 1 fonts (pixel test)")
    ap.add_argument("--work", type=Path, help="work folder for --selftest (default: a temporary folder)")
    ap.add_argument("--options", help="package options for --selftest, e.g. complete,zswash,slantedGreek")
    ap.add_argument("--scale", type=float, default=1.0, help="--selftest with all maths fonts at this size factor")
    ap.add_argument("--stress", action="store_true", help="--selftest with about 3000 more generated formulas")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest(a.mtpro2, a.work, options=a.options, scale=a.scale, stress=a.stress)
    if not a.output:
        ap.error("OUTPUT folder required")
    weights = tuple({"regular": "normal"}.get(w.strip(), w.strip()) for w in a.weights.split(","))
    convert(a.mtpro2, a.output, weights, a.donor)
    if a.zip:
        z = a.output.with_suffix(".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for n in [MANIFEST] + [l for l in (a.output / MANIFEST).read_text().splitlines()
                                   if l and not l.startswith("#")]:
                zf.write(a.output / n, n)                 # only what the converter wrote
        print(f"zip written: {z}")
    print("Keep the output private: modified MTPro2 fonts are for your own use only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
