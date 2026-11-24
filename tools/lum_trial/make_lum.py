#!/usr/bin/env python3
"""Make a lua-unicode-math variant of the generated ntxmath-otf package (trial, branch lum-trial).
Usage: make_lum.py SRC_DIR OUT_DIR   (SRC_DIR: a built ntxmath-otf folder, unicode-math version)

The data files beside this script come from runs of both set-ups (see README.md): unicode-math's
mathcodes and delcodes, lua-unicode-math's, and unicode-math's delimiter commands."""
import shutil
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for p in src.iterdir():
    if p.is_file():
        shutil.copy(p, out / p.name)


def sub(name, a, b, count=1):
    p = out / name
    t = p.read_text()
    n = t.count(a)
    assert n == count, (name, a[:80], n)
    p.write_text(t.replace(a, b))


S = "ntxmath-otf.sty"
# options: the maths style as a lua-unicode-math instance, not unicode-math options
sub(S, r"\DeclareOption{frenchmath}{\PassOptionsToPackage{math-style=french}{unicode-math}",
       r"\DeclareOption{frenchmath}{\def\MTP@style{french}")
sub(S, r"\DeclareOption{slantedGreek}{\PassOptionsToPackage{math-style=ISO}{unicode-math}}",
       r"\DeclareOption{slantedGreek}{\def\MTP@style{ISO80000-2}}")
sub(S, r"\DeclareOption{ISO}{\PassOptionsToPackage{math-style=ISO}{unicode-math}}",
       r"\DeclareOption{ISO}{\def\MTP@style{ISO80000-2}}")
sub(S, r"\def\MTP@features{}", r"\def\MTP@features{}\def\MTP@style{TeX}")
# load lua-unicode-math; keep amsmath's \root and dots markers (lua-unicode-math replaces them
# with its own Lua processing); \mathrm and operator names from the maths font's upright letters
sub(S, "\\RequirePackage{unicode-math}\n\\unimathsetup{mathrm=sym}% (\\mathrm, operator names: newtxmath's operators font, as glyphs of the maths font)\n",
    r"""\@for\MTP@o:=root,DOTSB,DOTSI,DOTSX,DOTSC,mdots@\do{\ifcsname\MTP@o\endcsname
  \expandafter\let\csname MTP@k@\MTP@o\expandafter\endcsname\csname\MTP@o\endcsname\fi}
\RequirePackage{lua-unicode-math}
\directlua{ntxmathotf.lumrestore()}
\@for\MTP@o:=root,DOTSB,DOTSI,DOTSX,DOTSC,mdots@\do{\ifcsname MTP@k@\MTP@o\endcsname
  \expandafter\let\csname\MTP@o\expandafter\endcsname\csname MTP@k@\MTP@o\endcsname\fi}
\edef\MTP@tmp{\noexpand\UseInstance{lua-unicode-math-style}{\MTP@style}}\MTP@tmp
% (the classic prime: ' is LaTeX's ^{\prime...}; ` the character)
\begingroup\lccode`\~=`\' \lowercase{\endgroup\def~}{\active@math@prime}
\mathcode`\`="0060
\AtBeginDocument{\let\mathrm\symup}
\def\operator@font{\mathfamattr=\csname c__l_uni_math_attribute_symup_int\endcsname\relax}
""")
# (no unicode-math delimiter patch)
sub(S, "\\ExplSyntaxOn\n\\cs_set:Nn \\__um_delimiter:Nnn { \\Udelimiter \\mathchar@type#1 \\csname sym#2\\endcsname #3 ~ }\n\\ExplSyntaxOff\n", "")
# the fonts: NFSS families as unicode-math declared them (same luaotfload specification), no
# separate script fonts (the package chooses newtx's designs by size)
sub(S, r"\edef\MTP@load{\noexpand\setmathfont{NewTXMath.otf}[Path=\MTP@path,RawFeature={\MTP@features},script-features={},sscript-features={}]}\MTP@load",
    r"""\DeclareFontFamily{TU}{NewTXMath}{}
\edef\MTP@load{\noexpand\DeclareFontShape{TU}{NewTXMath}{m}{n}{<->\noexpand\UnicodeFontFile{\MTP@path NewTXMath.otf}{mode=base;script=math;language=dflt;mathfontdimen=xetex;\MTP@features}}{}}\MTP@load
\DeclareSymbolFont{lummain}{TU}{NewTXMath}{m}{n}
\directlua{ntxmathotf.mainfam = \number\symlummain}""")
sub(S, r"""  \edef\MTP@load{\noexpand\setmathfont{NewTXMath-Bold.otf}[Path=\MTP@path,version=bold,RawFeature={\MTP@features},script-features={},sscript-features={}]}\MTP@load""",
    r"""  \edef\MTP@load{\noexpand\DeclareFontFamily{TU}{NewTXMath-Bold}{}\noexpand\DeclareFontShape{TU}{NewTXMath-Bold}{m}{n}{<->\noexpand\UnicodeFontFile{\MTP@path NewTXMath-Bold.otf}{mode=base;script=math;language=dflt;mathfontdimen=xetex;\MTP@features}}{}}\MTP@load
  \SetSymbolFont{lummain}{bold}{TU}{NewTXMath-Bold}{m}{n}""")
sub(S, r"""  \edef\MTP@load{\noexpand\setmathfont{NewTXMath-Heavy.otf}[Path=\MTP@path,version=heavy,RawFeature={\MTP@features},script-features={},sscript-features={}]}\MTP@load""",
    r"""  \DeclareMathVersion{heavy}\edef\MTP@load{\noexpand\DeclareFontFamily{TU}{NewTXMath-Heavy}{}\noexpand\DeclareFontShape{TU}{NewTXMath-Heavy}{m}{n}{<->\noexpand\UnicodeFontFile{\MTP@path NewTXMath-Heavy.otf}{mode=base;script=math;language=dflt;mathfontdimen=xetex;\MTP@features}}{}}\MTP@load
  \SetSymbolFont{lummain}{heavy}{TU}{NewTXMath-Heavy}{m}{n}""")
# nested formulas: start with the document's letters (the alphabet attribute is reset)
sub(S, "\\ExplSyntaxOn\n\\cs_set_protected:Nn \\__um_switch_to:n { \\tl_use:c {g__um_switchto_#1_tl} \\ifmmode \\MTP@inalpha=\\@ne \\fi }\n\\ExplSyntaxOff\n\\def\\MTP@resetmc{\\ifnum\\MTP@inalpha>\\z@ \\MTP@inalpha=\\z@ \\directlua{ntxmathotf.resetmc()}\\fi}\n",
    "\\def\\MTP@resetmc{\\mathfamattr=\\csname c__l_uni_math_attribute_unset_int\\endcsname\\relax}\n")
for name in ("ntxmath-otf.sty", "ntxmath-otf-legacy.tex", "ntxmath-otf-macros.tex"):
    p = out / name
    p.write_text(p.read_text().replace(r"\symoperators", r"\symlummain"))

L = "ntxmath-otf.lua"
sub(L, "local function fam() return tex.getmathcode(0x2211)[2] end",
       "local function fam() return ntxmathotf.mainfam or tex.getmathcode(0x2211)[2] end")
print("ok")

# lua-unicode-math restyles every Latin and Greek character of its family in Lua; unicode-math
# only restyled typed characters (its commands are fixed code points). The glyphs placed by name
# use alias codes (U+100000 + the code) while lua-unicode-math runs, the real codes after it
sub(L, """  if s then tex.sprint(string.format('\\\\Umathchar"%X"%X"%X ', cls, f, s)) end
end""", """  if s and ntxmathotf.aliased and ntxmathotf.aliased(s) then s = s + 0x100000 end
  if s then tex.sprint(string.format('\\\\Umathchar"%X"%X"%X ', cls, f, s)) end
end""")
with open(out / L, "a") as fh:
    fh.write("""
-- lua-unicode-math: the glyphs placed by name under alias codes while it restyles letters
do
  local A = 0x100000
  local ranges = { {0x30, 0x39}, {0x41, 0x5A}, {0x61, 0x7A}, {0x131, 0x131}, {0x237, 0x237},
    {0x391, 0x3A9}, {0x3B1, 0x3C9}, {0x3D0, 0x3F6}, {0x2202, 0x2202}, {0x2207, 0x2207} }
  function ntxmathotf.aliased(s)
    for _, r in ipairs(ranges) do if s >= r[1] and s <= r[2] then return true end end
    return false
  end
  luatexbase.add_to_callback("luaotfload.patch_font", function(tfm)
    if not (tfm.characters and (tfm.name or ""):find("NewTXMath", 1, true)) then return end
    local ch = tfm.characters
    for _, r in ipairs(ranges) do
      for u = r[1], r[2] do if ch[u] then ch[A + u] = ch[u] end end
    end
  end, "ntxmath-otf.lumalias")
  local MCHAR, MTCHAR, SUBML = node.id("math_char"), node.id("math_text_char"), node.id("sub_mlist")
  local fields = { "nucleus", "sub", "sup", "prime", "num", "denom", "degree", "accent", "bot_accent",
    "top_accent", "overlay_accent", "display", "text", "script", "scriptscript" }
  local has = node.has_field
  local function fix(n)
    while n do
      local id = n.id
      if id == MCHAR or id == MTCHAR then
        if n.char >= A then n.char = n.char - A end
      elseif id == SUBML then
        fix(n.head)
      else
        for _, f in ipairs(fields) do
          if has(n, f) then local v = n[f]; if v then fix(v) end end
        end
      end
      n = n.next
    end
  end
  function ntxmathotf.lumrestore()
    luatexbase.add_to_callback("pre_mlist_to_hlist_filter", function(head)
      fix(head); return true
    end, "ntxmath-otf.lumrestore")
  end
end
""")
# unicode-math defined some symbol commands as their character (the package then fixes that
# character's class) and kept the others; lua-unicode-math defines them all as macros that
# expand to their character: the same class fix for the commands unicode-math had as characters
UMCHAR = ['Angstrom', 'Bumpeq', 'Cap', 'Coloneq', 'Cup', 'Doteq', 'Finv', 'Game', 'Im', 'Leftarrow', 'Leftrightarrow', 'Lleftarrow', 'Lsh', 'Nearrow', 'Nwarrow', 'Re', 'Rightarrow', 'Rrightarrow', 'Rsh', 'Searrow', 'Subset', 'Supset', 'Swarrow', 'VDash', 'Vdash', 'Vvdash', 'Zbar', 'aleph', 'amalg', 'angle', 'approx', 'approxeq', 'ast', 'asymp', 'backsim', 'backsimeq', 'barwedge', 'beth', 'between', 'bigstar', 'bigtriangleup', 'blacktriangle', 'blacktriangledown', 'bot', 'boxast', 'boxbar', 'boxbslash', 'boxdot', 'boxminus', 'boxplus', 'boxtimes', 'bumpeq', 'cap', 'cdot', 'circeq', 'circledast', 'circledcirc', 'circleddash', 'clubsuit', 'coloneq', 'complement', 'cong', 'cup', 'curlyeqprec', 'curlyeqsucc', 'curlyvee', 'curlywedge', 'curvearrowleft', 'curvearrowright', 'dagger', 'daleth', 'dashcolon', 'dashv', 'ddagger', 'diagdown', 'diagup', 'diamondsuit', 'div', 'divideontimes', 'doteq', 'dotplus', 'doublebarwedge', 'downdownarrows', 'downharpoonleft', 'downharpoonright', 'ell', 'eqcirc', 'eqcolon', 'eqsim', 'eqslantgtr', 'eqslantless', 'equiv', 'exists', 'fallingdotseq', 'flat', 'forall', 'frown', 'geq', 'geqq', 'geqslant', 'gg', 'ggg', 'gimel', 'gnapprox', 'gneq', 'gneqq', 'gnsim', 'gtrapprox', 'gtreqless', 'gtreqqless', 'gtrless', 'gtrsim', 'heartsuit', 'hslash', 'imath', 'in', 'infty', 'intercal', 'jmath', 'laplac', 'leftarrow', 'leftarrowtail', 'leftharpoondown', 'leftharpoonup', 'leftleftarrows', 'leftrightarrow', 'leftrightarrows', 'leftrightharpoons', 'leftrightsquigarrow', 'leftsquigarrow', 'leftthreetimes', 'leq', 'leqq', 'leqslant', 'lessapprox', 'lesseqgtr', 'lesseqqgtr', 'lessgtr', 'lesssim', 'll', 'lll', 'lnapprox', 'lneq', 'lneqq', 'lnsim', 'looparrowleft', 'looparrowright', 'ltimes', 'mathdollar', 'mathparagraph', 'mathsection', 'measuredangle', 'mho', 'mid', 'mp', 'multimap', 'multimapinv', 'nLeftarrow', 'nLeftrightarrow', 'nRightarrow', 'nVDash', 'nVdash', 'nabla', 'napprox', 'nasymp', 'natural', 'ncong', 'ne', 'nearrow', 'neg', 'nequiv', 'nexists', 'ngeq', 'ngtr', 'ngtrless', 'ngtrsim', 'ni', 'nleftarrow', 'nleftrightarrow', 'nleq', 'nless', 'nlessgtr', 'nlesssim', 'nmid', 'nni', 'notin', 'nparallel', 'nprec', 'npreccurlyeq', 'nrightarrow', 'nsim', 'nsimeq', 'nsqsubseteq', 'nsqsupseteq', 'nsubset', 'nsubseteq', 'nsucc', 'nsucccurlyeq', 'nsupset', 'nsupseteq', 'ntrianglelefteq', 'ntrianglerighteq', 'nvDash', 'nvdash', 'nwarrow', 'odot', 'ominus', 'oplus', 'oslash', 'otimes', 'parallel', 'partial', 'pitchfork', 'pm', 'prec', 'precapprox', 'preccurlyeq', 'preceq', 'preceqq', 'precnapprox', 'precneqq', 'precnsim', 'precsim', 'propto', 'rightarrow', 'rightarrowtail', 'rightharpoondown', 'rightharpoonup', 'rightleftarrows', 'rightleftharpoons', 'rightrightarrows', 'rightsquigarrow', 'rightthreetimes', 'risingdotseq', 'rtimes', 'searrow', 'setminus', 'sharp', 'sim', 'simeq', 'smile', 'spadesuit', 'sphericalangle', 'sqcap', 'sqcup', 'sqsubset', 'sqsubseteq', 'sqsupset', 'sqsupseteq', 'star', 'subset', 'subseteq', 'subseteqq', 'subsetneq', 'subsetneqq', 'succ', 'succapprox', 'succcurlyeq', 'succeq', 'succeqq', 'succnapprox', 'succneqq', 'succnsim', 'succsim', 'supset', 'supseteq', 'supseteqq', 'supsetneq', 'supsetneqq', 'swarrow', 'times', 'top', 'triangledown', 'triangleleft', 'trianglelefteq', 'triangleq', 'triangleright', 'trianglerighteq', 'twoheadleftarrow', 'twoheadrightarrow', 'upharpoonleft', 'upharpoonright', 'uplus', 'upuparrows', 'vDash', 'varclubsuit', 'vardiamondsuit', 'varheartsuit', 'varnothing', 'varspadesuit', 'vartriangle', 'vartriangleleft', 'vartriangleright', 'vdash', 'vee', 'veebar', 'wedge', 'wp', 'wr']
sub(L, """  local c = t.cmdname
  tex.setcount("MTP@def", (c == "undefined_cs" or c == "math_given" or c == "relax") and 1 or 0)""",
    """  local c = t.cmdname
  if c:find("call") and ntxmathotf.umchar[cs] then
    local b = token.get_macro(cs)
    if b and utf8.len(b) == 1 then c = "other_char"; t = { mode = utf8.codepoint(b) } end
  end
  tex.setcount("MTP@def", (c == "undefined_cs" or c == "math_given" or c == "relax") and 1 or 0)""")
sub(L, "function ntxmathotf.provide(cs, cls)", "ntxmathotf.umchar = {" + ",".join('["%s"]=true' % n for n in UMCHAR) + "}\nfunction ntxmathotf.provide(cs, cls)")
# (restored when the font lacks the character)
sub(L, """    if c == "math_given" or c == "xmath_given" then
      ch = type(m) == "table" and m[#m] or (type(m) == "number" and m % 0x200000) or nil""",
    """    if c:find("call") then
      local b = token.get_macro(cs)
      if b and utf8.len(b) == 1 then ch = utf8.codepoint(b) end
    elseif c == "math_given" or c == "xmath_given" then
      ch = type(m) == "table" and m[#m] or (type(m) == "number" and m % 0x200000) or nil""")
print("ok2")

# unicode-math's mathcodes and delcodes where lua-unicode-math's differ (classes from its own
# table, not Unicode's MathClass): from dumps of both set-ups (family labels: MAIN = the maths
# font, nullfont1 = LaTeX's letters family); characters unicode-math makes maths-active are left out
HERE = Path(__file__).resolve().parent
mc, dc, cur = [], [], None
for line in (HERE / "unicode-math-codes.txt").read_text().split("\n"):
    if line.startswith("# "):
        cur = mc if "mathcodes" in line else dc
    elif line:
        cur.append(line)
with open(out / L, "a") as fh:
    fh.write("""
-- unicode-math's mathcodes and delcodes (lua-unicode-math trial)
function ntxmathotf.umcodes()
  local M = ntxmathotf.mainfam
  local mc = {%s}
  local dc = {%s}
  for c, v in pairs(mc) do tex.setmathcode(c, { v[1], v[2] == "M" and M or v[2], v[3] }) end
  for c, v in pairs(dc) do tex.setdelcode(c, { v[1] == "M" and M or v[1], v[2], v[3] == "M" and M or v[3], v[4] }) end
end
""" % (",".join(x.replace(",M,", ',"M",') for x in mc), ",".join(x.replace("{M,", '{"M",').replace(",M,", ',"M",') for x in dc)))
print("umcodes", len(mc), len(dc))
# applied once the document starts (after the package's own class fixes would undo nothing:
# they come from the same unicode-math set-up), before lua-unicode-math's commands are used
sub(S, r"\AddToHook{begindocument/end}{\directlua{ntxmathotf.nochar()}}",
       r"\AddToHook{begindocument/end}{\directlua{ntxmathotf.umcodes()}\directlua{ntxmathotf.nochar()}}")

# unicode-math's delimiter commands (\lbrace = \Udelimiter 4 <maths font> "7B, ...):
# lua-unicode-math makes them their character, which the package gives newtxmath's class
dl = [l.split() for l in open(HERE / "unicode-math-delimiters.txt").read().split("\n") if l]
defs = "".join(r'\protected\def\%s{\Udelimiter %s\symlummain "%s }' % (n, c, ch) for n, c, f, ch in dl)
sub(S, r"\directlua{ntxmathotf.lumrestore()}", r"\directlua{ntxmathotf.lumrestore()}" + "\n" + defs)
print("delims", len(dl))

# the maths parameters as with unicode-math: its maths font was family 0, so the TeX parameters
# of families 2 and 3 (LaTeX's symbols and largesymbols, set up later) took precedence; here the
# maths font is set up after them, so they are set again once a size's fonts are in place
sub(S, r"\directlua{ntxmathotf.lumrestore()}", r"""\directlua{ntxmathotf.lumrestore()}
\def\dotsb@{\cdots}% (as unicode-math sets it)
\every@math@size\expandafter{\the\every@math@size\global\textfont2=\textfont2 \global\scriptfont2=\scriptfont2
  \global\scriptscriptfont2=\scriptscriptfont2 \global\textfont3=\textfont3
  \global\scriptfont3=\scriptfont3 \global\scriptscriptfont3=\scriptscriptfont3 }""")
