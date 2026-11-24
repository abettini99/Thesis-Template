#!/usr/bin/env python3
"""ntxmath_otf.py -- newtxmath (Times-like maths, free) as an OpenType MATH font for LuaLaTeX.

The free counterpart of mtpro2_otf.py, for documents without MathTime Pro 2: the same aim
(layout exactly as classic TeX with newtxmath, copy-paste, tagged PDF), the same engine
(mtpro2_otf.py, imported from the same folder), different input. Plain Times only: the
set-up of \\usepackage{newtxtext}\\usepackage{newtxmath} without options.

What it builds (all under the LaTeX Project Public License 1.3, like newtx; the outlines are
newtx's and txfonts'): NewTXMath.otf, NewTXMath-Bold.otf and the package ntxmath-otf.sty
with ntxmath-otf.lua, -variants.lua, -dims.lua, -tfm.lua, -legacy.tex, -macros.tex.

How it reads newtxmath: LuaLaTeX loads it and reports what it set up (families and their
fonts, every math command, mathcode and delcode, which glyph each alphabet letter uses, every
macro it defines or changes); each character is resolved through newtx's virtual fonts to
its Type 1 glyph, whose name also tells which alphabet slots hold real letters.

Usage:
  ntxmath_otf.py build OUT                     fonts and package in OUT (needs TeX Live 2026
                                               with newtx, and fontTools)
  ntxmath_otf.py selftest [--stress] [--size PT] [--fonts OUT] [--work DIR]
                                               compare with classic newtxmath, glyph by glyph
  ntxmath_otf.py survey [--options OPTS]       what newtxmath sets up
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from mtpro2_otf import UPM, kpse, read_tfm, read_unicode_table  # the shared engine
except ImportError:  # (stage 1 needs only these)

    def kpse(name):
        p = subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip()
        return Path(p) if p else None

    read_tfm = read_unicode_table = None


# ======================================================================
# 1. Virtual fonts: each character as glyphs of real fonts (and rules)
# ======================================================================


@dataclass
class VFChar:
    width: float  # in units of the design size
    glyphs: list = field(default_factory=list)  # (font name, code, dx, dy)
    rules: list = field(default_factory=list)  # (dx, dy, height, width)
    specials: int = 0


@dataclass
class VF:
    design_size: float
    fonts: dict  # font number -> (name, scale)
    chars: dict  # code -> VFChar


def read_vf(path: Path) -> VF:
    """Parse a .vf file and run each character's DVI packet (set, move, push/pop, rule)."""
    d = path.read_bytes()
    if d[0] != 247 or d[1] != 202:
        raise ValueError(f"{path}: not a VF file")
    k = d[2]
    i = 3 + k
    _cs, ds = struct.unpack(">Ii", d[i : i + 8])
    ds_pt = ds / 2**20
    i += 8
    fonts, chars = {}, {}

    def num(n, signed=True):
        nonlocal i
        b = d[i : i + n]
        i += n
        v = int.from_bytes(b, "big", signed=signed)
        return v

    while True:
        op = d[i]
        if 243 <= op <= 246:  # fnt_def1..4
            i += 1
            fnum = num(op - 242, signed=False)
            _c, s, _dsz = struct.unpack(">IiI", d[i : i + 12])
            i += 12
            a, l = d[i], d[i + 1]
            i += 2
            name = d[i + a : i + a + l].decode("latin-1")
            i += a + l
            fonts[fnum] = (name, s / 2**20)
        elif op == 242:  # long char
            i += 1
            pl, cc, tfmw = struct.unpack(">IIi", d[i : i + 12])
            i += 12
            chars[cc] = _packet(d[i : i + pl], tfmw / 2**20, fonts)
            i += pl
        elif op < 242:  # short char
            pl, cc = op, d[i + 1]
            tfmw = int.from_bytes(d[i + 2 : i + 5], "big", signed=True) / 2**20
            i += 5
            chars[cc] = _packet(d[i : i + pl], tfmw, fonts)
            i += pl
        elif op == 248:  # post
            break
        else:
            raise ValueError(f"{path}: unexpected byte {op}")
    return VF(ds_pt, fonts, chars)


_TFMS: dict = {}


def char_width(name: str, code: int) -> float:
    """A character's width in its font's design size (0 if unknown)."""
    if name not in _TFMS:
        p = kpse(name + ".tfm")
        _TFMS[name] = read_tfm(p) if p and read_tfm else None
    t = _TFMS[name]
    return t.chars[code].width if t and code in t.chars else 0.0


def _packet(p: bytes, width: float, fonts: dict) -> VFChar:
    """Interpret a DVI packet; dimensions are fix_words of the design size."""
    ch = VFChar(width)
    h = v = w = x = y = z = 0
    stack = []
    f = min(fonts) if fonts else 0
    i = 0
    fix = lambda b: int.from_bytes(b, "big", signed=True) / 2**20

    while i < len(p):
        op = p[i]
        i += 1
        if op < 128 or 128 <= op <= 131:  # set_char, set1..4: then move right
            if op < 128:
                c = op
            else:
                n = op - 127
                c = int.from_bytes(p[i : i + n], "big")
                i += n
            name, scale = fonts.get(f, ("?", 1.0))
            ch.glyphs.append((name, c, h, v))
            h += char_width(name, c) * scale
            continue
        if 133 <= op <= 136:  # put1..4
            n = op - 132
            c = int.from_bytes(p[i : i + n], "big")
            i += n
            ch.glyphs.append((fonts.get(f, ("?",))[0], c, h, v))
            continue
        if op in (132, 137):  # set_rule / put_rule
            a, b = fix(p[i : i + 4]), fix(p[i + 4 : i + 8])
            i += 8
            ch.rules.append((h, v, a, b))
            if op == 132:
                h += b
            continue
        if op == 138:  # nop
            continue
        if op == 141:
            stack.append((h, v, w, x, y, z))
            continue
        if op == 142:
            h, v, w, x, y, z = stack.pop()
            continue
        if 143 <= op <= 146:  # right
            n = op - 142
            h += fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            continue
        if op == 147:
            h += w
            continue
        if 148 <= op <= 151:
            n = op - 147
            w = fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            h += w
            continue
        if op == 152:
            h += x
            continue
        if 153 <= op <= 156:
            n = op - 152
            x = fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            h += x
            continue
        if 157 <= op <= 160:  # down
            n = op - 156
            v += fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            continue
        if op == 161:
            v += y
            continue
        if 162 <= op <= 165:
            n = op - 161
            y = fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            v += y
            continue
        if op == 166:
            v += z
            continue
        if 167 <= op <= 170:
            n = op - 166
            z = fix(p[i : i + n].rjust(4, b"\xff" if p[i] & 0x80 else b"\0"))
            i += n
            v += z
            continue
        if 171 <= op <= 234:  # fnt_num
            f = op - 171
            continue
        if 235 <= op <= 238:
            n = op - 234
            f = int.from_bytes(p[i : i + n], "big")
            i += n
            continue
        if 239 <= op <= 242:  # xxx (specials)
            n = op - 238
            k = int.from_bytes(p[i : i + n], "big")
            i += n + k
            ch.specials += 1
            continue
        raise ValueError(f"DVI op {op} in a VF packet")
    return ch


def resolve(name: str, code: int, depth: int = 0, cache: dict = {}) -> list:  # noqa: B006 (a deliberate cache)
    """A character of a (possibly virtual) font as real glyphs: [(real font, code, dx, dy)],
    plus rules marked ("<rule>", 0, dx, dy, h, w). Offsets in units of the top font's size."""
    if depth > 8:
        raise RecursionError(name)
    if name not in cache:
        p = kpse(name + ".vf")
        cache[name] = read_vf(p) if p else None
    vf = cache[name]
    if vf is None:
        return [(name, code, 0.0, 0.0)]
    ch = vf.chars.get(code)
    if ch is None:
        return []
    out = []
    scale = {n: s for n, s in vf.fonts.values()}
    for fname, c, dx, dy in ch.glyphs:
        s = scale.get(fname, 1.0)
        for g in resolve(fname, c, depth + 1):
            if g[0] == "<rule>":
                out.append(("<rule>", 0, dx + g[2] * s, dy + g[3] * s, g[4] * s, g[5] * s))
            else:
                out.append((g[0], g[1], dx + g[2] * s, dy + g[3] * s))
    for dx, dy, hgt, wd in ch.rules:
        out.append(("<rule>", 0, dx, dy, hgt, wd))
    return out


# ======================================================================
# 2. The font map: real font -> Type 1 file and encoding
# ======================================================================


def read_map(names=("newtx.map", "txfonts.map", "pdftex.map")) -> dict:
    out = {}
    for n in names:
        p = kpse(n)
        if not p:
            continue
        for line in p.read_text(errors="replace").splitlines():
            if not line.strip() or line[0] in "%#*;":
                continue
            toks = line.split()
            tfm = toks[0]
            pfb = next((t.lstrip("<[") for t in toks if t.lstrip("<[").endswith((".pfb", ".pfa"))), None)
            enc = next((t.lstrip("<[") for t in toks if t.lstrip("<[").endswith(".enc")), None)
            if pfb:
                out.setdefault(tfm, (pfb, enc))
    return out


# ======================================================================
# 3. What newtxmath sets up (asked from LuaLaTeX itself)
# ======================================================================

DUMP_LUA = r"""
local out = {fams = {}, cmds = {}, macros = {}, mathcodes = {}, delcodes = {}}
for fam = 0, 255 do
  for s = 0, 2 do
    local id = node.family_font(fam, s)
    local f = id and id > 0 and font.getfont(id)
    if f then
      out.fams[#out.fams + 1] = {fam = fam, size = s, name = f.name, pt = f.size / 65536}
    end
  end
end
for _, cs in ipairs(tex.hashtokens()) do
  local ok, t = pcall(token.create, cs)
  if ok and t then
    local n = t.cmdname
    if n == "math_given" or n == "xmath_given" then
      local m = t.mode
      if type(m) == "table" then m = table.concat(m, ",") end
      out.cmds[cs] = tostring(m)
    elseif n == "call" or n == "long_call" or n == "protected_call" then
      local m = token.get_macro(cs)
      if m and #m < 300 and (m:find("\\delimiter") or m:find("\\mathaccent") or m:find("\\radical")
          or m:find("\\mathchar")) then
        out.macros[cs] = m
      end
    end
  end
end
out.vars = {}
for _, cs in ipairs({ "tx@enc", "rmdefaultB", "bold@wt", "sfdefault", "ttdefault", "encodingdefault",
                      "rmdefault" }) do
  out.vars[cs] = token.get_macro(cs) or ""
end
out.syms = {}
for _, cs in ipairs(tex.hashtokens()) do
  if cs:match("^sym") then
    local ok, t = pcall(token.create, cs)
    if ok and t and t.cmdname == "char_given" then out.syms[cs:sub(4)] = t.mode end
  end
end
out.skew = {}
for fam = 0, 15 do
  for s = 0, 2 do
    local id = node.family_font(fam, s)
    local f = id and id > 0 and font.getfont(id)
    if f then
      tex.runtoks(function()
        tex.sprint(string.format("\\global\\count255=\\skewchar\\%sfont%d ",
          ({ "text", "script", "scriptscript" })[s + 1], fam))
      end)
      out.skew[f.name] = tex.count[255]
    end
  end
end
for c = 0, 255 do
  local m = tex.getmathcode(c)
  if type(m) == "table" then m = table.concat(m, ",") end
  out.mathcodes[tostring(c)] = tostring(m)
  local d = tex.getdelcode(c)
  if type(d) == "table" then d = table.concat(d, ",") end
  out.delcodes[tostring(c)] = tostring(d)
end
local function enc(v, ind)
  if type(v) == "table" then
    local parts, isarr = {}, #v > 0
    for k, x in pairs(v) do
      parts[#parts + 1] = (isarr and "" or string.format("%q:", tostring(k))) .. enc(x)
    end
    return isarr and "[" .. table.concat(parts, ",") .. "]" or "{" .. table.concat(parts, ",") .. "}"
  elseif type(v) == "number" then return tostring(v)
  else return string.format("%q", tostring(v)) end
end
local fh = io.open(bold and "survey-dump-bold.json" or "survey-dump.json", "w"); fh:write(enc(out)); fh:close()
"""


PROBE_LUA = r"""
probe = probe or {}
function probe_box(key, n)
  local out = {}
  local function walk(h)
    for x in node.traverse(h) do
      if x.id == node.id("glyph") then
        local f = font.getfont(x.font)
        out[#out + 1] = (f and f.name or "?") .. "/" .. x.char
      elseif x.head then walk(x.head) end
    end
  end
  walk(tex.box[n].head)
  probe[key] = table.concat(out, " ")
end
function probe_save(fn)
  local t = {}
  for k, v in pairs(probe) do t[#t + 1] = string.format("%q:%q", k, v) end
  local fh = io.open(fn, "w"); fh:write("{" .. table.concat(t, ",") .. "}"); fh:close()
  probe = {}
end
"""

ALPHABET_CMDS = (
    "mathbb",
    "vvmathbb",
    "vmathbb",
    "mathcal",
    "mathscr",
    "mathfrak",
    "mathbf",
    "mathit",
    "mathsf",
    "mathtt",
    "mathrm",
)
ALPHABET_CHARS = [chr(c) for c in list(range(65, 91)) + list(range(97, 123)) + list(range(48, 58))]


def probe_tex(items: list[tuple[str, str]]) -> str:
    """TeX lines setting each (key, formula) in all three styles and reporting the glyphs."""
    out = []
    for key, f in items:
        for st in ("textstyle", "scriptstyle", "scriptscriptstyle"):
            k = f"{key}@{ {'textstyle': 't', 'scriptstyle': 's'}.get(st, 'ss') }"
            out.append(f"\\setbox0\\hbox{{$\\{st} {f}$}}\\directlua{{probe_box([==[{k}]==], 0)}}")
    return "\n".join(out)


def alphabet_items() -> list[tuple[str, str]]:
    return [(f"{a}:{c}", f"\\ifdefined\\{a}\\{a}{{{c}}}\\fi") for a in ALPHABET_CMDS for c in ALPHABET_CHARS]


MACRO_LUA = r"""
local fh = io.open(tex.jobname .. ".mac", "w")
for _, cs in ipairs(tex.hashtokens()) do
  local ok, t = pcall(token.create, cs)
  if ok and t then
    local n, m = t.cmdname, nil
    if n == "call" or n == "long_call" or n == "protected_call" or n == "protected_long_call" then
      m = n .. "\1" .. (token.get_meaning(cs) or "")
    else
      m = n .. "\1" .. tostring(t.mode)
    end
    fh:write(cs:gsub("[\n\t]", " "), "\t", (m:gsub("[\n\t]", " ")), "\n")
  end
end
fh:close()
"""


def macro_table(work: Path, preamble: str) -> dict:
    """Every control sequence after the preamble: name -> (command kind, meaning or code)."""
    (work / "mac.lua").write_text(MACRO_LUA)
    name = "mac" + str(abs(hash(preamble)) % 10**8)
    (work / f"{name}.tex").write_text(
        "\\documentclass{article}"
        + preamble
        + "\n\\begin{document}\\directlua{dofile('mac.lua')}\\end{document}\n"
    )
    subprocess.run(
        ["lualatex", "-interaction=nonstopmode", f"{name}.tex"], cwd=work, capture_output=True, timeout=600
    )
    out = {}
    p = work / f"{name}.mac"
    for line in p.read_text(errors="replace").splitlines() if p.exists() else []:
        if "\t" in line:
            k, v = line.split("\t", 1)
            kind, _, val = v.partition("\1")
            out[k] = (kind, val)
    return out


def ask_latex(options: str, work: Path) -> dict:
    (work / "survey-dump.lua").write_text(DUMP_LUA)
    (work / "probe.lua").write_text(PROBE_LUA)
    probe = probe_tex(alphabet_items())
    (work / "s.tex").write_text(
        "\\documentclass{article}\\usepackage{newtxtext}\n"
        f"\\usepackage[{options}]{{newtxmath}}\n"
        "\\begin{document}\\directlua{dofile('probe.lua')}$\\directlua{dofile('survey-dump.lua')}$\n"
        + probe
        + "\n\\directlua{probe_save('probe.json')}\n"
        "\\boldmath$\\directlua{bold = true; dofile('survey-dump.lua')}$\n"
        + probe
        + "\n\\directlua{probe_save('probe-bold.json')}\n"
        "\\end{document}\n"
    )
    subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "s.tex"], cwd=work, capture_output=True, timeout=600
    )
    p = work / "survey-dump.json"
    if not p.exists():
        raise SystemExit("LuaLaTeX did not report (is newtx installed?), see " + str(work / "s.log"))

    def load(p):
        return json.loads(re.sub(r"\\\n", r"\\n", p.read_text()))  # (Lua's %q line continuations)

    info = load(p)
    b = work / "survey-dump-bold.json"
    info["bold"] = load(b) if b.exists() else None
    for k, f in (("probe", "probe.json"), ("probe_bold", "probe-bold.json")):
        info[k] = load(work / f) if (work / f).exists() else {}
    # newtxmath's macros: what it defines or changes, against the same preamble without it
    base = macro_table(work, "\\usepackage{newtxtext}\\usepackage{amsmath}")
    ntx = macro_table(
        work, f"\\usepackage{{newtxtext}}\\usepackage{{amsmath}}\\usepackage[{options}]{{newtxmath}}"
    )
    info["macros_new"] = {k: v for k, v in ntx.items() if base.get(k) != v}
    return info


# ======================================================================
# 3b. The inputs for the shared engine (mtpro2_otf.MathFontBuild)
# ======================================================================


def read_enc(path: Path) -> list[str]:
    """PostScript encoding vector (.enc): 256 glyph names."""
    t = re.sub(r"%[^\n]*", "", path.read_text(errors="replace"))
    names = re.findall(r"/([^\s/\[\]{}]+)", t[t.index("[") + 1 : t.index("]")])
    return (names + [".notdef"] * 256)[:256]


class VFSource:
    """mtpro2_otf.Source for newtx: fonts by TFM name; a virtual font's character is drawn
    from the real Type 1 glyph its VF packet sets (with the packet's offset)."""

    def __init__(self):
        self.map = read_map()
        self._tfm, self._t1, self._rec, self._res = {}, {}, {}, {}

    def has(self, name: str) -> bool:
        return kpse(name + ".tfm") is not None

    def tfm(self, name: str):
        if name not in self._tfm:
            self._tfm[name] = read_tfm(kpse(name + ".tfm"))
        return self._tfm[name]

    def real(self, name: str):
        """Type 1 data of a real font: (glyph set, encoding vector, font dict)."""
        if name not in self._t1:
            from fontTools.t1Lib import T1Font

            pfb, enc = self.map.get(name, (None, None))
            path = kpse(pfb) if pfb else None
            if not path:
                self._t1[name] = None
            else:
                f = T1Font(str(path))
                f.parse()
                e = read_enc(kpse(enc)) if enc else list(f.font["Encoding"])
                self._t1[name] = (f.getGlyphSet(), e, f.font)
        return self._t1[name]

    def resolved(self, name: str, slot: int):
        key = (name, slot)
        if key not in self._res:
            self._res[key] = resolve(name, slot) if slot in self.tfm(name).chars else []
        return self._res[key]

    def glyph_ok(self, name: str, slot: int) -> bool:
        if not self.has(name) or slot not in self.tfm(name).chars:
            return False
        gl = [g for g in self.resolved(name, slot) if g[0] != "<rule>"]
        if not gl:
            return False
        for real, code, _, _ in gl:
            r = self.real(real)
            if r is None or code >= len(r[1]) or r[1][code] not in r[0]:
                return False
        return True

    def outline(self, name: str, slot: int):
        from fontTools.pens.recordingPen import RecordingPen
        from mtpro2_otf import HintedT1Extractor

        key = (name, slot)
        if key not in self._rec:
            self._rec[key] = rec = RecordingPen()
            gl = self.resolved(name, slot)
            single = len(gl) == 1
            for g in gl:
                if g[0] == "<rule>":
                    _, _, dx, dy, h, w = g
                    x0, y0 = dx * UPM, -dy * UPM
                    rec.moveTo((x0, y0))
                    rec.lineTo((x0 + w * UPM, y0))
                    rec.lineTo((x0 + w * UPM, y0 + h * UPM))
                    rec.lineTo((x0, y0 + h * UPM))
                    rec.closePath()
                    continue
                real, code, dx, dy = g
                gs, enc, fd = self.real(real)
                sub = RecordingPen()
                HintedT1Extractor(sub, fd["Private"].get("Subrs", [])).execute(gs[enc[code]])
                ox, oy = dx * UPM, -dy * UPM
                for op, args in sub.value:
                    if op == "hintset":
                        if single:  # (hints shift with the outline)
                            rec.value.append(
                                (op, ([(k, pos + (oy if k == "h" else ox), w) for k, pos, w in args[0]],))
                            )
                        continue
                    rec.value.append((op, tuple((x + ox, y + oy) for x, y in args)))
        return self._rec[key]

    def private(self, name: str) -> dict:
        """Private dict (alignment zones) of the real font behind a font's letter a."""
        gl = [g for g in self.resolved(name, 97) if g[0] != "<rule>"]
        r = self.real(gl[0][0]) if gl else None
        return dict(r[2]["Private"]) if r else {}


# TeX's math classes (\\mathchardef's class digit)
MATHCLASS = {
    0: "\\mathord",
    1: "\\mathop",
    2: "\\mathbin",
    3: "\\mathrel",
    4: "\\mathopen",
    5: "\\mathclose",
    6: "\\mathpunct",
    7: "\\mathalpha",
}


def ntx_inputs(info: dict):
    """mtpro2_otf.Inputs from what LuaLaTeX reported about newtxmath (survey dump)."""
    import mtpro2_otf as M

    famname = {v: k for k, v in info["syms"].items()}

    def symfonts(d):
        out = {}
        for e in d["fams"]:
            out.setdefault(famname.get(e["fam"], f"fam{e['fam']}"), {})[e["size"]] = e["name"]
        return out

    sf = {}
    for ver, d in (("normal", info), ("bold", info.get("bold"))):
        for fam, by in (symfonts(d) if d else {}).items():
            sf.setdefault(fam, {})[ver] = (by.get(0), by.get(1, by.get(0)), by.get(2, by.get(0)))
    decls = []
    for cs, v in sorted(info["cmds"].items()):  # (sorted: LuaTeX reports in hash order)
        if "," in v:  # \Umathchardef: class,fam,char
            c, f, ch = (int(x) for x in v.split(","))
        else:
            n = int(v)
            c, f, ch = n >> 12, (n >> 8) & 15, n & 255
        if f in famname:
            decls.append(M.Decl("symbol", "\\" + cs, MATHCLASS.get(c, "\\mathord"), famname[f], ch))
    for c, v in sorted(info["mathcodes"].items(), key=lambda kv: int(kv[0])):
        cl, f, ch = (int(x) for x in v.split(","))
        c = int(c)
        if cl < 8 and f in famname and 32 < c < 127 and not chr(c).isalnum():
            decls.append(M.Decl("symbol", chr(c), MATHCLASS.get(cl, "\\mathord"), famname[f], ch))
    for c, v in sorted(info["delcodes"].items(), key=lambda kv: int(kv[0])):
        a = [int(x) for x in v.split(",")]
        c = int(c)
        if a[0] >= 0 and 32 < c < 127 and a[0] in famname and a[2] in famname:
            cl = int(info["mathcodes"][str(c)].split(",")[0])
            decls.append(
                M.Decl(
                    "delimiter",
                    chr(c),
                    MATHCLASS.get(cl, "\\mathord"),
                    famname[a[0]],
                    a[1],
                    famname[a[2]],
                    a[3],
                )
            )
    for cs, body in sorted(info["macros"].items()):
        cs = cs.rstrip()
        m = re.match(r'\\delimiter\s*"([0-9A-F]{7})', body)
        if m:
            h = m.group(1)
            cl, f1, s1, f2, s2 = int(h[0], 16), int(h[1], 16), int(h[2:4], 16), int(h[4], 16), int(h[5:7], 16)
            if f1 in famname and f2 in famname:
                decls.append(
                    M.Decl(
                        "delimiter",
                        "\\" + cs,
                        MATHCLASS.get(cl, "\\mathord"),
                        famname[f1],
                        s1,
                        famname[f2],
                        s2,
                    )
                )
            continue
        m = re.match(r'\\radical\s*"([0-9A-F]{6})', body)
        if m:
            h = m.group(1)
            f1, s1, f2, s2 = int(h[0], 16), int(h[1:3], 16), int(h[3], 16), int(h[4:6], 16)
            if f1 in famname and f2 in famname:
                decls.append(M.Decl("radical", "\\" + cs, "\\mathord", famname[f1], s1, famname[f2], s2))
            continue
        m = re.match(r"\\mathaccentV\s*\{\w+\}([0-9A-F])([0-9A-F]{2})", body) or re.match(
            r'\\mathaccent\s*"[0-7]([0-9A-F])([0-9A-F]{2})', body
        )
        if m:
            f, sl = int(m.group(1), 16), int(m.group(2), 16)
            if f in famname:
                decls.append(M.Decl("accent", "\\" + cs, "\\mathord", famname[f], sl))
    last = {(d.kind, d.cmd): i for i, d in enumerate(decls)}
    decls = [d for i, d in enumerate(decls) if i in set(last.values())]
    um, uml = kpse("unicode-math-table.tex"), kpse("unicode-math-luatex.sty")
    aliases, remaps = M.read_um_aliases(uml)
    sty = kpse("newtxmath.sty").read_text(encoding="latin-1")
    fm = kpse("fontmath.ltx").read_text(encoding="latin-1")
    ams = kpse("amsmath.sty")
    skew = dict(info["skew"])
    skew.update((info.get("bold") or {}).get("skew", {}))  # (the bold version's fonts too)
    inp = M.Inputs(
        {},
        sty,
        "",
        [],
        decls,
        sf,
        {k: v for k, v in skew.items() if v >= 0},
        M.Unicode(M.read_unicode_table(um), aliases, remaps),
        True,
        M.read_amsmath_variants(sty, ams),
        {
            "kernel": M.read_classic_defs(fm, M.CLASSIC_KERNEL),
            "amsmath": M.read_classic_defs(ams.read_text(encoding="latin-1"), M.CLASSIC_AMSMATH, ams=True),
        },
    )
    return inp


# ======================================================================
# 3c. Building one weight: mtpro2_otf.MathFontBuild with newtx's own stages
# ======================================================================

DIGIT_NAMES = ("zero one two three four five six seven eight nine").split()


def _build_base():
    import mtpro2_otf as M

    return M.MathFontBuild


class NtxBuild(_build_base()):
    """One weight of NewTX Math. The shared stages read newtx's declarations; these differ:
    the operators font (OT1 Times, with the upright Greek) is part of the maths fonts, the
    alphabets come from what LuaLaTeX sets for \\mathbb etc., and the wide accents are
    newtx's \\widehat/\\widetilde chains."""

    def __init__(self, inp, src, weight, info):
        super().__init__(inp, src, weight)
        self.tex_ext = True  # (extensible delimiters exactly as TeX builds them)
        self.keep_class = True  # (newtxmath's classes where unicode-math's differ: \\Join)
        self.info = info
        self.probe = info["probe"] if weight == "normal" else info.get("probe_bold", {})
        self.probe_bold = info.get("probe_bold", {})
        # operators: as any other symbol font (MTPro2's is the text font, skipped there)
        # delimiters sharing a small glyph (| and \\arrowvert): the character's own chain wins
        uni = inp.uni
        rank = lambda d: (
            0
            if d.kind != "delimiter"
            else 3
            if len(d.cmd) == 1
            else 2
            if uni.for_command(d.cmd, d.slot, d.fam)
            else 1
        )
        inp.decls.sort(key=rank)
        inp.symfonts.setdefault("operatorsX", inp.symfonts["operators"])
        for d in inp.decls:
            if d.fam == "operators" and d.kind == "symbol":
                d.fam = "operatorsX"

    def build(self):
        self.latin_letters()
        self.upright()
        self.symbols()
        self.separate_ops()
        self.greek_and_composites()
        self.large_operators()
        self.delimiters()
        self.accents()
        self.centre_and_widen()
        self.alphabets()
        self.legacy_glyphs()
        self.separate_shared()
        self.tex_letter_boxes()
        self.tex_kerns()
        self.tex_parameters()
        self.tex_boxes()
        self.accent_xheights()
        return self

    def accent_xheights(self):
        """Each accent glyph's own font's x-height: TeX lowers an accent by at most that
        (\\hat from the operators font, \\dot from the symbols font, \\widehat from the
        extension font differ)."""
        self.accent_xheight = {}
        roots = [
            self.cmap.get(self.inp.uni.for_command(d.cmd, d.slot, d.fam))
            for d in self.inp.decls
            if d.kind == "accent"
        ] + list(self.variants.get("accent", {}).values())
        for r in dict.fromkeys(g for g in roots if g):
            hv = self.hvar.get(r, [r])
            for n in dict.fromkeys(hv + [a for h in hv for a in self.ssty.get(h, [])]):
                G = self.glyphs.get(n)
                if G is not None and G.ref is not None:
                    self.accent_xheight[n] = self.src.tfm(G.ref.font).params[5] * G.ref.scale

    def math_constants(self) -> dict:
        c = super().math_constants()
        acc = next((d for d in self.inp.decls if d.kind == "accent" and d.cmd == "\\hat"), None)
        if acc and self.fam(acc.fam):  # TeX lowers an accent by its own font's x-height
            c["AccentBaseHeight"] = round(self.src.tfm(self.fam(acc.fam)[0]).params[5] * 1000)
        return c

    def legacy_fonts(self) -> dict[str, int]:
        """newtx fonts the package rebuilds as TFM-exact virtual fonts: LaTeX's own symbol
        families (letters, symbols, largesymbols), for the kernel's constructions."""
        out = {}
        for fam in ("letters", "symbols", "largesymbols"):
            for f in self.fam(fam) or ():
                out.setdefault(f, 1)
        return out

    def separate_ops(self):
        """An operator sharing its glyph with another class (\\smallcoprod and \\amalg): its own
        copy, since operators keep their italic correction apart (OpenType) and others not."""
        others = {g for cls, g in self.commands.values() if cls != "\\mathop"}
        for cmd, (cls, g) in list(self.commands.items()):
            if cls == "\\mathop" and g in others and cmd in self.cmd_src:
                fam, slot = self.cmd_src[cmd]
                g2 = self.add_sized(self.fam(fam), slot, f"{g}.op", dup=True)
                if g2:
                    self.commands[cmd] = (cls, g2)

    def upright(self):
        """Digits, upright Latin letters and punctuation with a mathcode in the operators font."""
        ops = self.fam("operators")
        for c, v in sorted(self.info["mathcodes"].items(), key=lambda kv: int(kv[0])):
            c = int(c)
            cl, f, slot = (int(x) for x in v.split(","))
            if f == 0 and 32 < c < 127:
                cp = self.inp.uni.remaps.get(chr(c), c)
                self.set_cmap(cp, self.add_sized(ops, slot, M_gname(cp)))
        for c in list(range(65, 91)) + list(range(97, 123)):  # (\\mathrm, unicode-math's upright)
            self.set_cmap(c, self.add_sized(ops, c, M_gname(c)))

    def greek_and_composites(self):
        super().greek_and_composites()
        # italic capital Greek: newtx's \Gammait .. \Omegait (the letters font)
        for d in self.inp.decls:
            nm = d.cmd.lstrip("\\")
            if d.kind == "symbol" and nm.endswith("it") and nm[:-2] in M_GREEK() and nm[0].isupper():
                cp = self.inp.uni.get("mit" + nm[:-2])
                if cp:
                    self.set_cmap(cp, self.add_sized(self.fam(d.fam), d.slot, M_gname(cp)), force=True)

    def large_operators(self):
        """Text -> display chains of every operator in an extension font (newtx has two)."""
        for d in self.inp.decls:
            if d.kind == "symbol" and d.cls == "\\mathop" and d.fam.startswith("largesymbols"):
                root = self.commands.get(d.cmd.lstrip("\\"), (None, None))[1]
                if root and root not in self.vvar:
                    refs, _ = self.chain(self.fam(d.fam)[0], d.slot)
                    self.vvar[root] = [
                        v for v in (self.add(r, f"{root}.v{i}") for i, r in enumerate(refs)) if v
                    ]

    def delimiters(self):
        """The shared stage, then newtxmath's delimiters that unicode-math has no character or
        command for (\\llbracket, \\lbag, \\smlbrace, \\arrowvert, ...): their own glyphs and sizes,
        set by name (\\MTP@delim)."""
        super().delimiters()
        uni = self.inp.uni
        for d in self.inp.decls:
            if d.kind != "delimiter" or len(d.cmd) == 1:
                continue
            name = d.cmd.lstrip("\\")
            if (
                uni.for_command(d.cmd, d.slot, d.fam)
                or name in uni.table
                or uni.aliases.get(name) in uni.table
            ):
                continue
            g = self.delimiter(
                "mtp." + name, (d.fam, d.slot) if self.fam(d.fam) else None, (d.fam2, d.slot2), dup=True
            )
            if g:
                self.variants.setdefault("delim:ntx", {})[name] = g
                self.variants.setdefault("delimclass", {})[name] = d.cls

    def accents(self):
        super().accents()
        acc = {d.cmd.lstrip("\\"): d for d in self.inp.decls if d.kind == "accent"}
        for base, wide in (("hat", "widehat"), ("tilde", "widetilde")):
            cp = self.inp.uni.for_command("\\" + base)
            g = self.cmap.get(cp)
            d = acc.get(wide)
            if not (g and d and self.fam(d.fam)):
                continue
            refs, _ = self.chain(self.fam(d.fam)[0], d.slot)
            hv = self.hvar.get(g, [g]) + [self.add(r, f"{g}.w{i}") for i, r in enumerate(refs)]
            hv = sorted(dict.fromkeys(h for h in hv if h), key=lambda n: self.glyphs[n].width)
            for h in hv:
                self.glyphs[h].accent = self.glyphs[h].width / 2
            self.hvar[g] = hv

    # ------------------------------------------------------------ alphabets
    def _probe_entry(self, probe, key):
        """(fonts per style, slot) of a single-glyph probe, or None."""
        parts = [probe.get(f"{key}@{st}", "") for st in ("t", "s", "ss")]
        if not all(parts) or any(" " in p for p in parts):
            return None
        fonts = [p.rsplit("/", 1)[0] for p in parts]
        slots = {int(p.rsplit("/", 1)[1]) for p in parts}
        if len(slots) != 1 or any(not self.src.has(f) for f in fonts):
            return None
        return tuple(fonts), slots.pop()

    def _glyph_is(self, font, slot, cp, ch, tag=None):
        """Does the real glyph's name say it is this character? (classic alphabets give
        whatever sits in a slot: \\mathcal{z} is a double dagger)"""
        gl = [g for g in self.src.resolved(font, slot) if g[0] != "<rule>"]
        if len(gl) != 1:
            return False
        r = self.src.real(gl[0][0])
        if not r:
            return False
        name = r[1][gl[0][1]]
        ok = {M_gname(cp), f"u{cp:X}", f"u{cp:04X}", ch}
        if tag and self.weight != "normal":  # (a bold font's glyphs are the bold letters)
            import mtpro2_otf as M

            bt = {"frak": "boldfrak", "script": "boldscript", "italic": "bolditalic"}.get(tag)
            bcp = bt and M.alpha_cp(bt, ch)
            if bcp:
                ok |= {M_gname(bcp), f"u{bcp:X}"}
        if ch.isdigit():
            ok.add(DIGIT_NAMES[int(ch)])
        return name in ok or name.split(".")[0] in ok

    def alphabet(self, tag, probe, cmd, chars=ALPHABET_CHARS, setname=None, force=True):
        import mtpro2_otf as M

        for ch in chars:
            cp = M.alpha_cp(tag, ch)
            e = cp and self._probe_entry(probe, f"{cmd}:{ch}")
            if not e or not self._glyph_is(e[0][0], e[1], cp, ch, tag):
                continue
            if setname:
                g = self.add_sized(e[0], e[1], f"{M_gname(cp)}.{setname}")
                if g:
                    self.variants.setdefault(setname, {})[ch] = g
            else:
                if force or cp not in self.cmap:
                    self.set_cmap(cp, self.add_sized(e[0], e[1], M_gname(cp)), force=True)

    def alphabets(self):
        import mtpro2_otf as M

        P, PB = self.probe, self.probe_bold
        self.alphabet("bb", P, "mathbb")
        self.alphabet("bb", P, "vvmathbb", force=False)  # (lower case and digits: newtx's other bb)
        self.alphabet("bb", P, "vvmathbb", setname="vvbb")  # (\\vvmathbb, \\vmathbb as alphabets of
        self.alphabet("bb", P, "vmathbb", setname="vbb")  # their own: the options vvarbb, varbb)
        self.alphabet("script", P, "mathscr")
        self.alphabet("frak", P, "mathfrak")
        self.alphabet("script", P, "mathcal", setname="cal")
        self.alphabet("bold", PB if self.weight == "normal" else P, "mathbf")
        self.alphabet("boldscript", PB, "mathscr")
        self.alphabet("boldfrak", PB, "mathfrak")
        self.alphabet("script", PB, "mathcal", setname="boldcal")
        # bold italic letters and bold Greek: the letters font of the bold version
        bl = self.inp.symfonts["letters"].get("bold")
        if bl:
            for c in list(range(65, 91)) + list(range(97, 123)):
                cp = M.alpha_cp("bolditalic", chr(c))
                self.set_cmap(cp, self.add_sized(bl, c, M_gname(cp)), force=True)
            uni = self.inp.uni
            for d in self.inp.decls:
                nm = d.cmd.lstrip("\\")
                if d.kind == "symbol" and nm in M.GREEK and d.fam in ("letters", "lettersA"):
                    up = d.fam == "lettersA"
                    cp = uni.get(("mbf" if up else "mbfit") + nm)
                    fonts = self.inp.symfonts[d.fam].get("bold")
                    if cp and fonts:
                        self.set_cmap(cp, self.add_sized(fonts, d.slot, M_gname(cp)), force=True)


def M_GREEK():
    import mtpro2_otf as M

    return M.GREEK


def M_gname(cp):
    import mtpro2_otf as M

    return M.gname(cp)


# ======================================================================
# 3d. The package: ntxmath-otf.sty and its support files
# ======================================================================

PREFIX = "ntxmath-otf"
NTX_WEIGHTS = {"normal": ("NewTX Math", "NewTXMath.otf"), "bold": ("NewTX Math Bold", "NewTXMath-Bold.otf")}
NTX_DONORS = {"normal": "texgyretermes-regular.otf", "bold": "texgyretermes-bold.otf"}
NTX_COPYRIGHT = (
    "Converted from the newtx fonts (Michael Sharpe) and txfonts (Young Ryu); "
    "LaTeX Project Public License 1.3"
)
NTX_VERSION = "1.5"
NTX_DATE = "2026/11/23"
LEGACY_FAMS = ("letters", "symbols", "largesymbols")


def rebrand(text: str) -> str:
    """mtpro2-otf's run-time code and package text, for NewTX Math."""
    return (
        text.replace("mtpro2-otf", PREFIX)
        .replace("mtpro2otf", "ntxmathotf")
        .replace("MTPro2Math", "NewTXMath")
        .replace("mtp2vf:", "ntxvf:")
        .replace("mtpro2_otf.py", "ntxmath_otf.py")
    )


def ntx_lua() -> str:
    import mtpro2_otf as M

    lua = M.LUA
    old = "  return pt < 6.9999 and 3 or pt < 8.9999 and 2 or 1"
    assert old in lua, "LUA template changed (design sizes)"
    # newtx's .fd files: <-6.3> scriptscript design, <6.3-8.6> script, <8.6-> text
    lua = lua.replace(old, "  return pt < 6.2999 and 3 or pt < 8.5999 and 2 or 1")
    lua = lua.replace(
        "-- MTPro2's design for a size, as its .fd files choose it: 1 text (9 pt up), 2 script\n"
        "-- (7 to 9 pt), 3 scriptscript (below 7 pt)",
        "-- newtx's design for a size, as its .fd files choose it: 1 text (8.6 pt up), 2 script\n"
        "-- (6.3 to 8.6 pt), 3 scriptscript (below 6.3 pt)",
    )
    return rebrand(lua)


def ntx_legacy_tex(builds) -> str:
    """LaTeX's symbol families on the TFM-exact virtual fonts (as with newtxmath's)."""
    B = builds["normal"]
    out = [
        f"% {PREFIX}-legacy.tex: generated by ntxmath_otf.py",
        "% LaTeX's symbol fonts (letters, symbols, largesymbols) on the virtual newtx fonts",
    ]
    for fam in LEGACY_FAMS:
        v = B.inp.symfonts[fam]
        skew = B.inp.skew.get(v["normal"][0])
        skewchar = f"\\skewchar\\font={skew} " if skew is not None else ""
        out.append(f"\\DeclareFontFamily{{U}}{{ntxvf@{fam}}}{{{skewchar}}}")
        for ver, ser in (("normal", "m"), ("bold", "b")):
            t, sc, ss = v.get(ver, v["normal"])
            spec = (
                f"<-6.3>ntxvf:{ss}<6.3-8.6>ntxvf:{sc}<8.6->ntxvf:{t}"
                if len({t, sc, ss}) > 1
                else f"<->ntxvf:{t}"
            )
            out.append(f"\\DeclareFontShape{{U}}{{ntxvf@{fam}}}{{{ser}}}{{n}}{{{spec}}}{{}}")
        out.append(
            f"\\DeclareSymbolFont{{{fam}}}{{U}}{{ntxvf@{fam}}}{{m}}{{n}}"
            f"\\SetSymbolFont{{{fam}}}{{bold}}{{U}}{{ntxvf@{fam}}}{{b}}{{n}}"
        )
    import mtpro2_otf as M

    codes = {"letters": 1, "symbols": 2, "largesymbols": 3}
    defs = []
    for d in B.inp.decls:
        if d.kind == "delimiter" and d.fam in codes and d.fam2 in codes:
            code = f'"{M.CLASSES.get(d.cls, 0):X}{codes[d.fam]:X}{d.slot:02X}{codes[d.fam2]:X}{d.slot2:02X}'
            if len(d.cmd) == 1:
                defs.append(f'\\delcode`\\{d.cmd}="{code[2:]}')
            else:
                defs.append(f"\\def{d.cmd}{{\\delimiter{code} }}")
    out.append("\\def\\MTP@legacydelims{%\n" + "%\n".join(defs) + "%\n}")
    out.append("\\endinput")
    return "\n".join(out) + "\n"


# newtxmath's macros the package does not carry: alphabets (unicode-math's, by glyph), symbols
# set by \\mathaccent/\\delimiter (declarations), font loading and administration
MACRO_SKIP = re.compile(
    r"\\(use@mathgroup|mathhexbox|ntx@@|M@U|M@OML|M@LMS|M@LMX|"
    r"sym(?:AMSm|lettersA|symbolsC|largesymbolsTXA)\b|txf@ntname|readsufile|"
    r"DeclareMathSymbol|DeclareSymbolFont|SetSymbolFont|DeclareFontShape|"
    r"mathaccentV|mathaccent\b|delimiter\b|radical\b)"
)
MACRO_SKIP_NAMES = {
    "ShowMathFonts",
    "DeclareMathSymbolCtr",
    "loadsubfile",
    "readsufile",
    "ntxmathscale",
    "rmdefaultB",
    "fileversion",
    "filedate",
    "defaultscriptratio",
    "defaultscriptscriptratio",
    "Bbbk",
    "mathrm",
    "mathbb",
    "mathfrak",
    "mathscr",
    "mathslscr",
    "mathuscr",
    "varmathbb",
    "vmathbb",
    "vvmathbb",
    "ifiscseq",
    "checkmark",
    "circledR",
    "maltese",
    "LastDeclaredEncoding",
}
CS = re.compile(r"\\([A-Za-z@]+|.)")


def _uses(name: str, meaning: str) -> list[str]:
    """Control sequences a macro's body uses (a robust command: its inner 'name ' macro)."""
    body = meaning.split("->", 1)[-1]
    m = re.fullmatch(r"\\protect \\(\S+)  ", body)
    if m:
        return [m.group(1) + " "]
    return [c.group(1) for c in CS.finditer(body)]


def ntx_macros_tex(info: dict, B) -> str:
    """newtxmath's own macros (the kernel ones it changes, \\joinrel, \\vdots, \\not, ..., and
    its composite symbols and constructions: \\Mapsto, \\overgroup, \\widebar, \\vv, ...),
    verbatim, with the internal symbols they use (by glyph)."""
    new = info.get("macros_new", {})
    macro_kinds = ("call", "long_call", "protected_call", "protected_long_call")
    public = [
        k
        for k, (kind, v) in new.items()
        if kind in macro_kinds
        and k not in MACRO_SKIP_NAMES
        and (re.fullmatch(r"[A-Za-z]+", k) or re.fullmatch(r"not.|n.", k))
    ]  # (\\not= -> \\not=)
    ok: dict[str, bool] = {}

    def check(name, depth=0):
        """May this macro be carried (with what it uses)?"""
        if name in ok:
            return ok[name]
        ok[name] = True  # (recursion guard)
        kind, meaning = new[name]
        good = not MACRO_SKIP.search(meaning) and name not in MACRO_SKIP_NAMES and depth < 30
        if good:
            for c in _uses(name, meaning):
                if c in new and c != name:
                    k2, _ = new[c]
                    if k2 in macro_kinds and not check(c, depth + 1):
                        good = False
                        break
        ok[name] = good
        return good

    keep = [k for k in sorted(public) if check(k)]
    # the closure: internal macros and symbols they use
    order, seen, syms, chars = [], set(), [], []

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        kind, meaning = new[name]
        for c in _uses(name, meaning):
            if c in new and c not in seen:
                k2, _ = new[c]
                if k2 in macro_kinds:
                    visit(c)
                elif k2 in ("math_given", "xmath_given") and "@" in c and c in B.commands:
                    seen.add(c)
                    syms.append(c)
                elif k2 == "char_given" and "@" in c:  # (\\newtxmath@openbox: a \\chardef)
                    seen.add(c)
                    chars.append((c, new[c][1]))
        order.append(name)

    for k in keep:
        visit(k)
    import mtpro2_otf as M

    out = [
        f"% {PREFIX}-macros.tex: generated by ntxmath_otf.py from newtxmath.sty (LPPL 1.3):",
        "% its macros, as LuaLaTeX reports them, after the symbol commands are set up",
        "% (its text-mode symbols, \\openbox and \\AmS, use newtx's fonts as text fonts)",
    ]
    for c, code in chars:
        out.append(f"\\expandafter\\chardef\\csname {c}\\endcsname={code}\\relax")
    for c in syms:
        cls, g = B.commands[c]
        out.append(f"\\expandafter\\MTP@dosym\\csname {c}\\endcsname{{{g}}}{{{M.CLASSES.get(cls, 0)}}}%")
    for name in order:
        kind, meaning = new[name]
        params, sep, body = meaning.partition("->")
        if not sep:
            continue
        # a robust command's inner macro is named with a trailing space, printed as "\\not  ":
        # read back, that is \\not again (an endless loop); name it explicitly
        body = re.sub(
            r"\\([A-Za-z@]+)  ",
            lambda m: f"\\csname {m.group(1)} \\endcsname " if m.group(1) + " " in new else m.group(0),
            body,
        )
        pre = ("\\protected" if "protected" in kind else "") + ("\\long" if "long" in kind else "")
        out.append(f"{pre}\\expandafter\\def\\csname {name}\\endcsname{params}{{{body}}}%")
    out.append("\\endinput")
    return "\n".join(out) + "\n"


def option_lets() -> str:
    """newtxmath's options that switch between commands it defines anyway, read from it:
    upint (upright integrals), frenchmath (upright Greek, and upright capitals through
    unicode-math's math-style=french), vvarbb/varbb (\\mathbb as \\vvmathbb/\\vmathbb); cmintegrals
    has no effect in newtxmath either (its code is commented out)."""
    sty = kpse("newtxmath.sty").read_text(encoding="latin-1")
    sty = "\n".join(l.split("%")[0] for l in sty.splitlines())

    def lets(flag):  # (every \\iftx@<flag> block's first branch)
        return [
            p
            for m in re.finditer(r"(?<!newif)\\iftx@" + flag + r"(?![A-Za-z@])", sty)
            for p in block(m.end())
        ]

    def block(k):
        depth, end = 0, len(sty)
        for m in re.finditer(r"\\(if[A-Za-z@]*|else|fi)(?![A-Za-z@])", sty[k:]):
            w = m.group(1)
            if w.startswith("if"):
                depth += 1
            elif depth == 0:  # (\\else or \\fi of this \\iftx@...)
                end = k + m.start()
                break
            elif w == "fi":
                depth -= 1
        return re.findall(r"\\let\\(\w+)\s*=?\s*\\(\w+)", sty[k:end])

    out = []
    for opt, flag, extra in (
        ("upint", "upint", ""),
        ("frenchmath", "frenchm", "\\PassOptionsToPackage{math-style=french}{unicode-math}"),
    ):
        body = "".join(f"\\ifdefined\\{b}\\let\\{a}\\{b}\\fi" for a, b in lets(flag))
        out.append(f"\\DeclareOption{{{opt}}}{{{extra}\\AddToHook{{begindocument/end}}{{{body}}}}}\n")
    out.append(
        "\\DeclareOption{vvarbb}{\\AddToHook{begindocument/end}{\\let\\mathbb\\vvmathbb}}\n"
        "\\DeclareOption{varbb}{\\AddToHook{begindocument/end}{\\let\\mathbb\\vmathbb}}\n"
        "\\DeclareOption{cmintegrals}{}\n"
    )
    return "".join(out)


def _cut(text, start, end, new, inclusive=True):
    i = text.index(start)
    j = text.index(end, i) + (len(end) if inclusive else 0)
    return text[:i] + new + text[j:]


def ntx_sty(reg) -> str:
    """mtpro2-otf.sty for NewTX Math: the same engine, newtxmath's options and alphabets."""
    import mtpro2_otf as M

    t = M.make_sty(reg, NTX_DATE)
    t = _cut(
        t,
        "%% mtpro2-otf.sty -- ",
        "\\NeedsTeXFormat{LaTeX2e}",
        f"%% {PREFIX}.sty -- newtxmath (Times-like maths) as OpenType, for LuaLaTeX\n"
        "%% (built by ntxmath_otf.py; fonts and package under the LaTeX Project Public License 1.3)\n"
        "%% Loads NewTXMath(-Bold).otf with unicode-math, with the layout of classic newtxmath:\n"
        "%% every newtxmath symbol command, its alphabets, TeX's metrics and optical sizes.\n"
        "\\NeedsTeXFormat{LaTeX2e}",
    )
    t = t.replace(f"v{M.PACKAGE_VERSION} MTPro2 OpenType companion", f"v{NTX_VERSION} newtxmath as OpenType")
    t = _cut(
        t,
        "% which set these files were made from",
        "\\MTP@litetrue \\fi\n",
        "% the version (for classes that choose fallbacks)\n"
        f"\\def\\NTXOTFversion{{{NTX_VERSION}}}\n\\newif\\ifMTP@lite\n",
    )
    t = t.replace(
        "\\@for\\MTP@o:=mtpro2,bm,amssymb,amsfonts\\do", "\\@for\\MTP@o:=newtxmath,bm,amssymb,amsfonts\\do"
    )
    t = _cut(
        t,
        "% mtpro2.sty's options (same names, same defaults)",
        "\\ProcessOptions\\relax\n",
        "% newtxmath's options: scale (or scaled), slantedGreek and uprightGreek (the default); the\n"
        "% plain Times set-up is its default and the only one converted, so other newtxmath options\n"
        "% are ignored, with a warning. ISO: the same as slantedGreek (unicode-math's math-style=ISO:\n"
        "% italic capital Greek; \\upGamma, \\uppi, \\mathrm{e} stay upright)\n"
        + option_lets()
        + "\\DeclareOption{uprightGreek}{}\n"
        "\\DeclareOption{slantedGreek}{\\PassOptionsToPackage{math-style=ISO}{unicode-math}}\n"
        "\\DeclareOption{ISO}{\\PassOptionsToPackage{math-style=ISO}{unicode-math}}\n"
        "\\def\\MTP@cal{v}\\def\\MTP@scr{x}\\def\\MTP@frak{x}\\def\\MTP@bb{x}\\def\\MTP@br{c}\n"
        "\\newif\\ifMTP@slops \\newif\\ifMTP@zswash \\newif\\ifMTP@sbcorr \\newif\\ifMTP@textsf\n"
        "\\DeclareOption{textsf}{\\MTP@textsftrue}\n"
        "\\def\\MTP@scale{1}\n"
        "\\def\\MTP@opt#1=#2\\@nil{\\def\\MTP@key{#1}\\def\\MTP@val{#2}}\n"
        "\\DeclareOption*{\\expandafter\\MTP@opt\\CurrentOption=\\@nil\n"
        "  \\def\\MTP@tmp{scale}\\ifx\\MTP@key\\MTP@tmp\\else\\def\\MTP@tmp{scaled}\\fi\n"
        "  \\ifx\\MTP@key\\MTP@tmp\n"
        "    \\expandafter\\MTP@opt\\CurrentOption\\@nil\\let\\MTP@scale\\MTP@val\n"
        "  \\else\n"
        f"    \\PackageWarning{{{PREFIX}}}{{newtxmath option `\\CurrentOption' is not supported\n"
        "      (only plain Times is converted); ignored}%\n"
        "  \\fi}\n"
        "\\ProcessOptions\\relax\n",
    )
    t = _cut(
        t, "\\newcommand\\mathcurly[1]", "\\noexpand\\MTP@alpha{\\noexpand\\MTP@altset}{\\MTP@l}}}\n", ""
    )
    t = _cut(t, "% brace styles for \\left/\\right", "\\MTP@delim{morphed}{rbrace}{5}}\n", "")
    t = _cut(t, "\\providecommand\\zswash{", "}\n", "")
    t = t.replace(
        "(U+#2) is not in the MathTime Pro 2 fonts}{MathTime Pro 2 has no glyph for this character;\n"
        "  with its Type 1 fonts the command is not defined either.}",
        "(U+#2) is not in the NewTX Math font}{newtxmath has no glyph for this character;\n"
        "  with its Type 1 fonts the command is not defined either.}",
    )
    t = t.replace(
        "mathbb,mathcurly,%\n    mathbbdark,mathbbholey,mathbbitalic,symup,", "mathbb,%\n    symup,"
    )
    # the text alphabets as newtxmath declares them (\\mathbf, \\mathit in the roman font's
    # OT1 encoding, \\mathsf in OT1, \\mathtt in the default encoding)
    v = reg.info.get("vars", {})
    enc = v.get("tx@enc") or "OT1"
    rmB = v.get("rmdefaultB") or "\\rmdefault"  # (newtxmath's roman: minntx)
    t = _cut(
        t,
        "% the text alphabets as mtpro2.sty declares them",
        "\\let\\mathtt\\MTP@mathtt}\n",
        "% the text alphabets as newtxmath declares them: \\mathbf and \\mathit in the roman\n"
        f"% font ({enc}), \\mathsf in OT1, \\mathtt in the default encoding\n"
        f"\\DeclareMathAlphabet{{\\MTP@mathbf}}{{{enc}}}{{{rmB}}}{{b}}{{n}}\n"
        f"\\DeclareMathAlphabet{{\\MTP@mathit}}{{{enc}}}{{{rmB}}}{{m}}{{it}}\n"
        "\\DeclareMathAlphabet{\\MTP@mathsf}{OT1}{\\sfdefault}{m}{n}\n"
        "\\DeclareMathAlphabet{\\MTP@mathtt}{\\encodingdefault}{\\ttdefault}{m}{n}\n"
        f"\\SetMathAlphabet{{\\MTP@mathit}}{{bold}}{{{enc}}}{{{rmB}}}{{b}}{{it}}\n"
        "\\SetMathAlphabet{\\MTP@mathsf}{bold}{OT1}{\\sfdefault}{b}{n}\n"
        "\\SetMathAlphabet{\\MTP@mathtt}{bold}{\\encodingdefault}{\\ttdefault}{b}{n}\n"
        "\\AddToHook{begindocument/end}{\\let\\mathbf\\MTP@mathbf\\let\\mathit\\MTP@mathit\n"
        "  \\ifMTP@textsf\\else\\let\\mathsf\\MTP@mathsf\\fi\\let\\mathtt\\MTP@mathtt}\n"
        + (
            "\\directlua{ntxmathotf.ot1greek = true}% (\\mathbf{\\Delta}: the OT1 font's own Greek)\n"
            if enc == "OT1"
            else ""
        )
        + "% (newtxmath's text-mode symbols, \\openbox and \\AmS, use its fonts as text fonts)\n"
        "\\DeclareFontEncoding{LMS}{}{}\\DeclareFontSubstitution{LMS}{ntxsy}{m}{n}\n",
    )
    # (\mathrm is the maths font's own operators glyphs here, bold ones in the bold version, as
    # with newtxmath: no text-font \mathrm for the bold version)
    t = _cut(t, "% (mtpro2.sty) \\mathrm and operator names", "% (end mtpro2.sty)\n", "")
    # microtype: newtxmath's operators font, \DeclareSymbolFont{operators}{\tx@enc}{\rmdefaultB}{m}{n}
    # and {\bold@wt}{n} in the bold version
    a = "\\edef\\MTP@mt@enc{\\encodingdefault}\\edef\\MTP@mt@fam{\\rmdefault}\\def\\MTP@mt@bold{b}"
    assert a in t
    t = t.replace(
        "% the Type 1 set-up's operators font (mtpro2.sty: {\\encodingdefault}{\\rmdefault}, b/n in the bold\n"
        "% version, m/n in the heavy one), as when the package loads\n",
        "% the Type 1 set-up's operators font (newtxmath: {\\tx@enc}{\\rmdefaultB}, m/n and bold b/n)\n",
        1,
    )
    # (\\rmdefaultB as newtxmath sets it when it loads: \\rmdefault, or minntx with a Times text
    # package (newtxtext, tgtermes) or \\rmdefault ptm/minntx; the same glyphs either way, but
    # microtype's settings differ: ntxtlf is its Times, ptmx. Not a newtx family: minntx.)
    fam = (
        "\\edef\\MTP@mt@fam{\\rmdefault}"
        "\\@ifpackageloaded{newtxtext}{\\def\\MTP@mt@fam{minntx}}{}"
        "\\@ifpackageloaded{tgtermes}{\\def\\MTP@mt@fam{minntx}}{}"
        "\\directlua{local f = token.get_macro('MTP@mt@fam') "
        "if f == 'ptm' or not (f == 'minntx' or f:match('^ntx')) then token.set_macro('MTP@mt@fam', 'minntx') end}"
    )
    t = t.replace(a, f"\\def\\MTP@mt@enc{{{enc}}}{fam}\\def\\MTP@mt@bold{{{v.get('bold@wt') or 'b'}}}", 1)
    # newtxmath's classes for the ASCII symbols (unicode-math has its own: / is an opening
    # symbol with newtxmath, an ordinary one with unicode-math)
    cls = {
        int(c): int(v.split(",")[0])
        for c, v in reg.info["mathcodes"].items()
        if 32 < int(c) < 127 and not chr(int(c)).isalnum() and int(v.split(",")[0]) < 8
    }
    t = t.replace(
        "% hyperref: headings with maths",
        "% newtxmath's classes of the ASCII symbols\n"
        "\\AddToHook{begindocument/end}{\\directlua{for c, k in pairs({"
        + ",".join(f"[{c}]={k}" for c, k in sorted(cls.items()))
        + "}) do\n"
        "  local m = tex.getmathcode(c)\n"
        "  if type(m) == 'table' and m[1] < 8 and not (m[1] == k) then tex.setmathcode(c, {k, m[2], m[3]}) end\n"
        "end}}\n% hyperref: headings with maths",
        1,
    )
    # newtxmath's text alphabets (\mathbf, \mathit, \mathsf: its .fd files) and legacy symbol
    # fonts scale with \ntxmath@scaled, which newtxmath always sets from its scale option
    a = "\\edef\\MTP@s{s*[\\MTP@scale]}% (scaled like the MTPro2 fonts)\n"
    assert a in t
    t = t.replace(
        a,
        "\\edef\\MTP@s{s*[\\MTP@scale]}% (scaled like the maths font)\n"
        "\\let\\ntxmath@scaled\\MTP@s % newtxmath's text alphabets (its .fd files) scale with it\n",
        1,
    )
    import mtpro2_otf as M2

    delims = "%\n".join(
        f"  \\DeclareRobustCommand\\{c}{{\\MTP@delim{{ntx}}{{{c}}}{{{M2.CLASSES.get(reg.variants['delimclass'][c], 0)}}}}}"
        for c in sorted(reg.variants.get("delim:ntx", {}))
    )
    t = t.replace(
        "% hyperref: headings with maths",
        "% newtxmath's delimiters that unicode-math lacks (\\llbracket, \\lbag, \\arrowvert, ...)\n"
        '\\def\\MTP@delim#1#2#3{\\directlua{mtpro2otf.delim("delim:#1","#2",#3)}}\n'
        "\\AddToHook{begindocument/end}{%\n" + delims + "}\n% hyperref: headings with maths",
        1,
    )
    t = _cut(
        t,
        "% the options' choices of alphabets, braces, operators and z",
        "\\endinput\n",
        "% newtxmath's \\mathcal: its calligraphic capitals (unicode-math's script letters are\n"
        "% \\mathscr's)\n"
        "\\AtBeginDocument{%\n"
        "  \\protected\\def\\mathcal#1{\\MTP@galpha{cal}{#1}}%\n"
        "  \\protected\\def\\vvmathbb#1{\\MTP@galpha{vvbb}{#1}}\\protected\\def\\vmathbb#1{\\MTP@galpha{vbb}{#1}}%\n"
        "  \\ifMTP@textsf \\let\\mathsf\\MTP@textsf \\fi}\n"
        "% the alphabets that are math alphabets with newtxmath (\\mathrm, \\mathbb, \\mathfrak; its\n"
        "% \\mathscr sets each letter on its own): a group, so that \\mathrm{xy}_i is a box with a\n"
        "% script (one letter stays a character, as TeX makes it)\n"
        "\\AddToHook{begindocument/end}{%\n"
        "  \\@for\\MTP@o:=mathrm,mathbb,mathfrak\\do{%\n"
        "    \\expandafter\\let\\csname MTP@u@\\MTP@o\\expandafter\\endcsname\\csname\\MTP@o\\endcsname\n"
        "    \\expandafter\\protected\\expandafter\\edef\\csname\\MTP@o\\endcsname#1{{\\expandafter\\noexpand\n"
        "      \\csname MTP@u@\\MTP@o\\endcsname{#1}}}}}\n"
        "% \\mathrm of a capital Greek letter: newtxmath's operators font, an OT1 font with the eleven\n"
        "% capitals in slots 0-10 (the maths font's upright Greek is newtx's other design)\n"
        f"\\DeclareSymbolFont{{MTPops}}{{{enc}}}{{{rmB}}}{{m}}{{n}}\\SetSymbolFont{{MTPops}}{{bold}}{{{enc}}}{{{rmB}}}{{{v.get('bold@wt') or 'b'}}}{{n}}\n"
        "\\newattribute\\MTP@rmattr\n"
        "\\AddToHook{begindocument/end}{\\directlua{ntxmathotf.rmgreekfam = \\number\\symMTPops}%\n"
        "  \\let\\MTP@rm@outer\\mathrm \\protected\\def\\mathrm#1{\\MTP@rm@outer{\\MTP@rmattr=1 #1}}}\n"
        "\\endinput\n",
    )
    # newtxmath's macros replace unicode-math's definitions: after its set-up (which ends the
    # begin-document hook)
    old = "\\AtBeginDocument{\\makeatletter\\input{mtpro2-otf-macros.tex}\\makeatother}"
    assert old in t
    # (newtxmath's \\vdots, \\ddots come with its macros: their copy-paste spans after them)
    t = t.replace(
        old,
        "\\AddToHook{begindocument/end}{\\makeatletter\\input{mtpro2-otf-macros.tex}\\makeatother"
        "\\MTP@composite{vdots}{22EE}\\MTP@composite{ddots}{22F1}\\MTP@composite{adots}{22F0}}",
    )
    # operator names (\\sin, \\operatorname) and \\mathrm: the maths font's upright letters,
    # newtxmath's operators font (unicode-math's default: the text font)
    t = t.replace(
        "\\RequirePackage{unicode-math}\n",
        "\\RequirePackage{unicode-math}\n\\unimathsetup{mathrm=sym}% (\\mathrm, operator names: "
        "newtxmath's operators font, as glyphs of the maths font)\n",
        1,
    )
    t = rebrand(t)
    t = t.replace("\\MTPOTFversion", "\\NTXOTFversion")
    return t


def build_package(out: Path, options: str = "", quiet: bool = False):
    """Fonts (regular, bold) and the package files in out."""
    import mtpro2_otf as M

    work = Path(tempfile.mkdtemp(prefix="ntxbuild-"))
    info = ask_latex(options, work)
    out.mkdir(parents=True, exist_ok=True)
    builds = {}
    for w in ("normal", "bold"):
        inp = ntx_inputs(info)
        B = NtxBuild(inp, VFSource(), w, info).build()
        family, fn = NTX_WEIGHTS[w]
        dn = kpse(NTX_DONORS[w])
        M.write_otf(B, family, M.donor_glyphs(dn, M.DONOR_CPS) if dn else None, NTX_COPYRIGHT).save(out / fn)
        builds[w] = B
        if not quiet:
            print(f"{fn}: {len(B.glyphs)} glyphs, {len(B.cmap)} code points", flush=True)
    reg = M.weight_data(builds)
    (out / f"{PREFIX}-variants.lua").write_text(rebrand(M.variants_lua(reg)))
    (out / f"{PREFIX}-dims.lua").write_text(
        M.packed_lua(
            M.dims_lua(builds, NTX_WEIGHTS),
            [f"-- {PREFIX}-dims.lua: generated by ntxmath_otf.py: TeX's glyph boxes by glyph index"],
        )
    )
    tfm = M.tfm_lua(builds, NTX_WEIGHTS)
    (out / f"{PREFIX}-tfm.lua").write_text(
        M.packed_lua(
            tfm,
            [
                f"-- {PREFIX}-tfm.lua: generated by ntxmath_otf.py: newtx's TFM metrics with the glyph",
                "-- index of each character (compressed)",
            ],
        )
    )
    (out / f"{PREFIX}-legacy.tex").write_text(ntx_legacy_tex(builds), encoding="latin-1")
    (out / f"{PREFIX}-macros.tex").write_text(ntx_macros_tex(info, reg), encoding="utf-8")
    (out / f"{PREFIX}.lua").write_text(ntx_lua())
    (out / f"{PREFIX}.sty").write_text(ntx_sty(reg))
    return builds


# ======================================================================
# 3e. Selftest: classic newtxmath (Type 1) against ntxmath-otf, glyph by glyph
# ======================================================================

MTPRO2_ONLY = re.compile(
    r"\\(xl|XL|XXL|XXXL|PARENS|LEFTRIGHT|SQRT|ROOT|ccases|overcbrace|undercbrace|"
    r"alt[A-Za-z]|mathcurly|mathbb[a-z]+|zswash|hm|w+[a-z]+up|dotup|what|wwhat|"
    r"wwtilde|wtilde|wbar|wcheck|wwcheck|wwbar|lbracestraight|rbracestraight|"
    r"lbracemorphed|rbracemorphed|slsum|slprod|slcoprod|upsum|upprod|upcoprod)\b"
)


def selftest(
    work: Path | None = None,
    stress: bool = False,
    size: float | None = None,
    fonts: Path | None = None,
    options: str = "",
    document: bool = False,
) -> int:
    import os

    import mtpro2_otf as M

    work = Path(work or tempfile.mkdtemp(prefix="ntx-selftest-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if fonts is None:
        print(f"building the fonts in {work}", flush=True)
        build_package(work / "Fonts", quiet=True)
        fonts = work / "Fonts"
    formulas = [f for f in M.SELFTEST_FORMULAS if not MTPRO2_ONLY.search(f)]
    formulas += [f for f in M.GREEK_FORMULAS if f not in formulas]
    family = {f: "greek" if f in M.GREEK_FORMULAS else "basic" for f in formulas}
    # the same options for classic newtxmath (ISO is ours: newtxmath's slantedGreek)
    otf_opts = ",".join(o for o in options.split(",") if o)
    t1_opts = ",".join(
        "slantedGreek" if o == "ISO" else o.replace("scale=", "scaled=") for o in options.split(",") if o
    )
    t1_pkg = r"\usepackage%s{newtxmath}\usepackage{bm}" % (f"[{t1_opts}]" if t1_opts else "")
    otf_pkg = r"\usepackage%s{ntxmath-otf}" % (f"[{otf_opts}]" if otf_opts else "")
    if stress:
        info = json.loads((work / "info.json").read_text()) if (work / "info.json").exists() else None
        if info is None:
            info = ask_latex("", Path(tempfile.mkdtemp()))
            (work / "info.json").write_text(json.dumps(info))
        for fam, f in M.stress_formulas(ntx_inputs(info)):
            if f not in family and not MTPRO2_ONLY.search(f):
                family[f] = fam
                formulas.append(f)
    fs = (r"\fontsize{%g}{%g}\selectfont" % (size, size * 1.2)) if size else ""
    # (each formula's positions under its number: a formula whose TeX error loses the dump
    # must not shift the others)
    body = "\n".join(
        r"\directlua{selftestmark(%d)}\setbox0\hbox{" % i + fs + r"$%s$}\directlua{selftestdump(0)}"
        r"\shipout\vbox to 3cm{\kern2cm\hbox{\kern0.5cm\smash{\box0}}\vss}"
        r"\setbox2\vbox{\noindent\hbox{}\par}" % f
        for i, f in enumerate(formulas)
    )
    lua = M.SELFTEST_LUA.replace(
        "function selftestdump(k)",
        'function selftestmark(i) out:write("N " .. i .. "\\n") end\nfunction selftestdump(k)',
    )
    assert "selftestmark" in lua
    (work / "selftest-dump.lua").write_text(lua)
    doc = M.SELFTEST_DOC.replace(
        "\\usepackage{fontspec}\\setmainfont{TeX Gyre Termes}", "\\usepackage{newtxtext}"
    )
    (work / "st_t1.tex").write_text(doc % (t1_pkg, body))
    (work / "st_otf.tex").write_text(doc % (otf_pkg, body))
    env = dict(os.environ, TEXINPUTS=f"{fonts}:.:")
    skipped = set()
    for job in ("st_t1", "st_otf"):
        subprocess.run(
            ["lualatex", "-interaction=nonstopmode", job + ".tex"],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
        )
        log = (work / f"{job}.log").read_text(errors="replace") if (work / f"{job}.log").exists() else ""
        if not (work / f"{job}.pos").exists():
            print(f"error: {job}.tex failed, see {work / job}.log")
            return 1
        tex = (work / f"{job}.tex").read_text().splitlines()
        start = next(i for i, l in enumerate(tex) if "selftestmark" in l) + 1
        for m in re.finditer(r"^l\.(\d+) ", log, re.M):
            if 0 <= int(m.group(1)) - start < len(formulas):
                skipped.add(int(m.group(1)) - start)

    def positions(path):
        out, cur = {}, None
        for line in path.read_text().splitlines():
            f = line.split()
            if f[0] == "N":
                cur = int(f[1])
            elif f[0] == "F":
                out[cur] = {"box": tuple(int(v) / 65536 for v in f[1:]), "items": []}
            elif cur in out:
                out[cur]["items"].append((f[0],) + tuple(float(v) / 65536 for v in f[1:]))
        return out

    pa, pb = positions(work / "st_t1.pos"), positions(work / "st_otf.pos")
    keep = [i for i in range(len(formulas)) if i not in skipped and i in pa and i in pb]
    layout = {i: M.same_layout(pa[i], pb[i]) for i in keep}
    print(
        f"layout: {sum(m is None for m in layout.values())}/{len(keep)} formulas with every glyph and "
        f"rule where classic newtxmath puts it (within 0.01pt)"
    )
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
        print(
            f"  ({len(skipped)} formulas skipped: TeX errors: "
            + ", ".join(formulas[i] for i in sorted(skipped)[:8])
            + (", ..." if len(skipped) > 8 else "")
            + ")"
        )
    if document:
        # (newtxtext, which loads its fonts with fontspec: with another fontspec font, classic
        # newtxmath's operators font would be OT1 in that family, i.e. cmr10)
        rc = M.doctest(
            work,
            t1_pkg,
            otf_pkg,
            env,
            f"options {otf_opts or '(none)'}, newtxtext",
            text=r"\usepackage{newtxtext}",
        )
        # (and as a template that sets \rmdefault to newtx's Times without newtxtext: then
        # newtxmath's operators font is ntxtlf, which microtype gives its Times settings)
        sub = work / "doc-ntxtlf"
        sub.mkdir(exist_ok=True)
        sc = re.search(r"scaled?=([\d.]+)", options)
        after = r"\usepackage[scaled=%s]{newtxtext}" % sc.group(1) if sc else r"\usepackage{newtxtext}"
        rc |= M.doctest(
            sub,
            t1_pkg + after,
            otf_pkg + after,
            env,
            f"options {otf_opts or '(none)'}, \\rmdefault ntxtlf, newtxtext after the maths",
            text=r"\usepackage[T1]{fontenc}\renewcommand\rmdefault{ntxtlf}",
        )
        # (and with fontspec loaded first, T1 after it: the maths fonts are still set up in TU)
        sub = work / "doc-fontspec-t1"
        sub.mkdir(exist_ok=True)
        fs = r"\usepackage{fontspec}\setmainfont{TeX Gyre Termes}" + (f"[Scale={sc.group(1)}]" if sc else "")
        rc |= M.doctest(
            sub,
            t1_pkg + after,
            otf_pkg + after,
            env,
            f"options {otf_opts or '(none)'}, fontspec, then T1 \\rmdefault ntxtlf, newtxtext after",
            text=fs + r"\usepackage[T1]{fontenc}\renewcommand\rmdefault{ntxtlf}",
        )
        return rc
    return 0


# ======================================================================
# 4. The survey
# ======================================================================


def survey(options: str = "", out: Path | None = None) -> dict:
    work = Path(tempfile.mkdtemp(prefix="ntxsurvey-"))
    info = ask_latex(options, work)
    fmap = read_map()
    fams = {}
    for e in info["fams"]:
        fams.setdefault(e["fam"], {})[e["size"]] = e["name"]
    report = {
        "options": options,
        "families": {},
        "real_fonts": {},
        "commands": len(info["cmds"]),
        "macros": len(info["macros"]),
    }
    real = {}
    for fam, by in sorted(fams.items()):
        name = by.get(0)
        tfm = read_tfm(kpse(name + ".tfm")) if read_tfm and kpse(name + ".tfm") else None
        nchar = len(tfm.chars) if tfm else 0
        composite = rules = 0
        for c in tfm.chars if tfm else {}:
            gl = resolve(name, c)
            if sum(1 for g in gl if g[0] != "<rule>") > 1:
                composite += 1
            if any(g[0] == "<rule>" for g in gl):
                rules += 1
            for g in gl:
                if g[0] != "<rule>":
                    real.setdefault(g[0], set()).add(g[1])
        report["families"][fam] = {
            "fonts": by,
            "chars": nchar,
            "virtual": bool(kpse(name + ".vf")),
            "composite": composite,
            "with_rules": rules,
            "extensible": len(tfm.exten) if tfm else 0,
            "chains": len(tfm.nextlarger) if tfm else 0,
        }
    for r, codes in sorted(real.items()):
        report["real_fonts"][r] = {
            "glyphs": len(codes),
            "type1": fmap.get(r, (None, None))[0],
            "encoding": fmap.get(r, (None, None))[1],
        }
    # Unicode coverage: newtxmath's \mathchardef commands that unicode-math knows
    table = read_unicode_table(kpse("unicode-math-table.tex")) if read_unicode_table else {}
    known = [c for c in info["cmds"] if c in table]
    report["unicode"] = {
        "commands_in_unicode_math": len(known),
        "commands_not_in_unicode_math": sorted(c for c in info["cmds"] if c not in table),
    }
    if out:
        out.write_text(json.dumps(report, indent=1, default=list))
        (out.with_suffix(".dump.json")).write_text(json.dumps(info, indent=1))
    return report


def main(argv=None) -> int:
    import os

    if argv is None and os.environ.get("PYTHONHASHSEED") != "0":  # (the same fonts on every run)
        os.execve(sys.executable, [sys.executable] + sys.argv, dict(os.environ, PYTHONHASHSEED="0"))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey", help="what newtxmath sets up, and where its glyphs come from")
    s.add_argument("--options", default="", help="newtxmath options, e.g. libertine,vvarbb")
    s.add_argument("--out", type=Path, default=Path("survey.json"))
    b = sub.add_parser("build", help="build NewTX Math and the ntxmath-otf package")
    b.add_argument("out", type=Path)
    t = sub.add_parser("selftest", help="compare with classic newtxmath")
    t.add_argument("--work", type=Path)
    t.add_argument("--fonts", type=Path, help="use these built files instead of building")
    t.add_argument("--stress", action="store_true")
    t.add_argument("--size", type=float)
    t.add_argument(
        "--options",
        default="",
        help="package options for both, e.g. slantedGreek,scale=0.95 "
        "(ISO is newtxmath's slantedGreek; scale= is passed to newtxmath as scaled=)",
    )
    t.add_argument(
        "--document",
        action="store_true",
        help="also a thesis-like document (tagged PDF/UA-2, babel, fontspec, microtype, siunitx, hyperref)",
    )
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest(a.work, a.stress, a.size, a.fonts, a.options, a.document)
    if a.cmd == "build":
        build_package(a.out)
        return 0
    if a.cmd == "survey":
        r = survey(a.options, a.out)
        print(f"newtxmath [{a.options}]: {r['commands']} math commands, {r['macros']} macros")
        for fam, f in r["families"].items():
            print(
                f"  family {fam:>3}: {f['fonts'].get(0):<28} {f['chars']:>4} chars"
                f"{' (virtual)' if f['virtual'] else ''}, {f['composite']} composite,"
                f" {f['with_rules']} with rules, {f['extensible']} extensible, {f['chains']} size chains"
            )
        print(f"  real Type 1 fonts: {len(r['real_fonts'])}")
        for n, x in r["real_fonts"].items():
            print(f"    {n:<16} {x['glyphs']:>4} glyphs  {x['type1']}  {x['encoding'] or ''}")
        u = r["unicode"]
        print(
            f"  unicode-math names {u['commands_in_unicode_math']} of the commands; "
            f"{len(u['commands_not_in_unicode_math'])} others"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
