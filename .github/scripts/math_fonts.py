#!/usr/bin/env python3
"""
Make the README images that compare the template's maths fonts: newtx (the default),
MathTime Professional 2 Lite and MathTime Professional 2 Complete.

  .github/readme/math-symbols.png   every symbol group, the three fonts row by row
  .github/readme/math-equation.png  one equation in the three fonts

Unlike page_sizes.py this cannot run on GitHub: it needs both MathTime editions,
which are licensed and never committed. Run it locally from the template folder:

  python3 .github/scripts/math_fonts.py path/to/mtp2lite.zip path/to/mtp2fonts.zip
  (zips or unpacked folders)

It converts both editions with tools/mtpro2_otf.py in a temporary folder and
loads the maths exactly as the class does (template/fontText.tex and fontMath.tex; newtx
as the OpenType maths fonts in template/fonts/ntxmath-otf).
Needs LuaLaTeX, pdftoppm (poppler), Pillow and fonttools. The images are pictures of the
typeset result, like a page of a PDF, and contain no font data.
"""
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".github" / "readme"
DPI = 220
MM = DPI / 25.4                      # pixels per millimetre

FONTS = [("newtx", None), ("MathTime Lite", "Lite"), ("MathTime Complete", "Complete")]

# (title, columns, cell width mm, glyph height mm, [(label, LaTeX maths)])
L = lambda names: [(n, "\\" + n) for n in names.split()]
GROUPS = [
    ("Latin letters", 13, 11, 9, [(c, c) for c in "abcdefghijklmnopqrstuvwxyz"]),
    ("", 13, 11, 9, [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]),
    ("Greek letters", 13, 11, 9, L("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota "
                                   "kappa lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi "
                                   "varphi chi psi omega")),
    ("", 13, 11, 9, L("Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega")),
    ("Bold (\\vec, \\tensor)", 13, 11, 9, [(c, "\\vec{%s}" % c) for c in "uvwxnfABFT"]
        + [(n, "\\vec{\\%s}" % n) for n in "alpha sigma tau omega nabla".split()]
        + [("0", "\\vec{0}"), ("1", "\\vec{1}")]),
    ("Symbols", 10, 14.3, 9, L("partial nabla infty hbar hslash ell wp aleph emptyset varnothing forall exists "
                             "neg prime angle triangle top bot")),
    ("Binary operators", 10, 14.3, 9, [("+", "+"), ("-", "-")] + L("pm mp times cdot circ bullet ast star "
                             "oplus ominus otimes oslash odot cup cap uplus sqcup vee wedge setminus wr "
                             "dagger ddagger diamond")),
    ("Relations", 10, 14.3, 9, [("=", "="), ("<", "<"), (">", ">")] + L("le ge leqslant geqslant ll gg neq "
                             "equiv approx sim simeq cong propto asymp doteq prec succ preceq subset supset "
                             "subseteq supseteq subsetneq sqsubseteq in ni notin perp parallel mid vdash "
                             "models coloneqq")),
    ("Negated relations", 10, 14.3, 9, L("nleq ngeq nless ngtr nsubseteq nsupseteq nmid nparallel nsim "
                             "ncong nprec nsucc nvdash")),
    ("Arrows", 10, 14.3, 9, L("to gets leftrightarrow Rightarrow Leftarrow Leftrightarrow uparrow downarrow "
                            "Uparrow Downarrow nearrow searrow mapsto hookrightarrow hookleftarrow "
                            "rightharpoonup rightleftharpoons leadsto")),
    ("", 5, 28.6, 9, L("longrightarrow longleftarrow Longrightarrow Longleftrightarrow longmapsto")),
    ("Large operators (display)", 8, 17.9, 17, [(n, "\\displaystyle\\%s" % n) for n in
                             "sum prod coprod int iint iiint oint bigcup bigcap bigoplus bigotimes bigodot "
                             "bigvee bigwedge biguplus bigsqcup".split()]),
    ("Delimiters (normal to \\Bigg)", 4, 35.75, 22, [
        (n, "\\Biggl%s\\biggl%s\\Bigl%s\\bigl%s%s" % ((d,) * 5)) for n, d in
        [("( )", "("), ("[ ]", "["), ("\\{ \\}", "\\{"), ("\\langle", "\\langle"), ("|", "|"),
         ("\\|", "\\|"), ("\\lfloor", "\\lfloor"), ("\\lceil", "\\lceil")]]),
    ("Accents and roots", 8, 17.9, 12, [("\\hat", "\\hat{a}"), ("\\tilde", "\\tilde{a}"), ("\\bar", "\\bar{a}"),
        ("\\dot", "\\dot{a}"), ("\\ddot", "\\ddot{a}"), ("\\check", "\\check{a}"), ("\\breve", "\\breve{a}"),
        ("\\acute", "\\acute{a}"), ("\\widehat", "\\widehat{xyz}"), ("\\widetilde", "\\widetilde{xyz}"),
        ("\\overline", "\\overline{xy}"), ("\\overrightarrow", "\\overrightarrow{AB}"),
        ("\\sqrt", "\\sqrt{x}"), ("\\sqrt[3]", "\\sqrt[3]{y}"), ("\\sqrt frac", "\\sqrt{\\frac{a}{b}}"),
        ("\\binom", "\\binom{n}{k}")]),
    ("Alphabets", 13, 11, 9, [("bb " + c, "\\mathbb{%s}" % c) for c in "NZQRC"]
        + [("cal " + c, "\\mathcal{%s}" % c) for c in "LVW"]
        + [("scr " + c, "\\mathscr{%s}" % c) for c in "FHL"]
        + [("frak " + c, "\\mathfrak{%s}" % c) for c in "gh"]),
    ("MathTime macros", 6, 23.8, 32, [("\\xl\\sum", "\\displaystyle\\xl\\sum"), ("\\XL\\sum", "\\displaystyle\\XL\\sum"),
        ("\\XXL\\int", "\\displaystyle\\XXL\\int"), ("\\SQRT", "\\displaystyle\\SQRT{\\frac{a^2}{b^2}}"),
        ("\\widearc", "\\widearc{AB}"), ("\\hm heavy", "\\hm{\\nabla\\Phi}")]),
]
NAME_H = 3.6                          # mm, the row with the command names

EQUATION = r"""
\boxed{\psi_{n\ell m} = \sqrt{\left(\frac{2}{na}\right)^{3} \frac{(n-\ell-1)!}{2n\,(n+\ell)!}}\;
  e^{-r/na} \left(\frac{2r}{na}\right)^{\ell} \left[L^{2\ell+1}_{n-\ell-1}(2r/na)\right] Y^{m}_{\ell}(\theta,\phi)}
\\[6pt]
\int \psi^{*}_{n\ell m}\,\psi_{n'\ell'm'}\, r^{2}\sin\theta \,\mathrm{d}r\,\mathrm{d}\theta\,\mathrm{d}\phi
  = \delta_{nn'}\,\delta_{\ell\ell'}\,\delta_{mm'}
"""

PREAMBLE = r"""\documentclass[border=0pt,multi=minipage]{standalone}
\usepackage{mathtools}
\makeatletter
\def\thesis@fontscale{1}
\newif\ifthesismathtime %(mt)s
\newif\ifthesisntxotf \ifthesismathtime\else\IfFileExists{ntxmath-otf.sty}{\thesisntxotftrue}{}\fi
\newif\ifthesisotfmath \ifthesismathtime\thesisotfmathtrue\fi \ifthesisntxotf\thesisotfmathtrue\fi
\input{template/fontText}
\input{template/fontMath}
\makeatother
\ifthesisotfmath\else\usepackage{bm}\fi
\AtBeginDocument{\renewcommand{\vec}[1]{\thesisboldmath{#1}}}
\providecommand{\xl}{}\providecommand{\XL}{}\providecommand{\XXL}{}
\newcommand{\na}{\text{\normalfont\footnotesize n/a}}
\newcommand{\cell}[3]{\parbox[c][#2][c]{#1}{\centering\large$#3$}}
\newcommand{\name}[2]{\parbox[c][%(nameh)smm][c]{#1}{\centering\fontsize{6}{7}\selectfont\ttfamily\detokenize{#2}}}
\begin{document}
"""


def grid(group, newtx):
    title, cols, w, h, items = group
    rows = [items[i:i + cols] for i in range(0, len(items), cols)]
    out = ["\\begin{minipage}{%smm}\\offinterlineskip" % (cols * w)]
    for row in rows:
        cells = []
        for label, tex in row:
            if newtx and label.startswith(("\\xl", "\\XL", "\\XXL", "\\SQRT", "\\widearc", "\\hm")):
                tex = "\\na"
            cells.append("\\cell{%smm}{%smm}{%s}" % (w, h, tex))
        cells += ["\\hspace{%smm}" % w] * (cols - len(row))
        out.append("\\hbox{%s}" % "".join(cells))
        names = ["\\name{%smm}{%s}" % (w, label) for label, _ in row]
        out.append("\\hbox{%s\\hspace{%smm}}" % ("".join(names), w * (cols - len(row))))
    out.append("\\end{minipage}")
    return "\n".join(out)


def build(name, edition, fonts_dir, work):
    mt = "\\thesismathtimetrue" if edition else "\\thesismathtimefalse"
    pages = [grid(g, edition is None) for g in GROUPS]
    eq = "\\begin{minipage}{150mm}\\[\\begin{gathered}%s\\end{gathered}\\]\\end{minipage}" % EQUATION
    src = (PREAMBLE % {"mt": mt, "nameh": NAME_H}
           + "\n".join(pages + [eq]) + "\n\\end{document}\n")
    job = name.replace(" ", "_")
    (work / f"{job}.tex").write_text(src)
    env = dict(os.environ)
    ntx = ROOT / "template" / "fonts" / "ntxmath-otf"          # newtx as OpenType maths fonts, as the class uses
    for var in ("TEXINPUTS", "OPENTYPEFONTS", "LUAINPUTS"):
        env[var] = f"{ntx}{os.pathsep}{env.get(var, '')}"
    if fonts_dir:
        for var in ("TEXINPUTS", "OPENTYPEFONTS", "LUAINPUTS"):
            env[var] = f"{fonts_dir}{os.pathsep}{env.get(var, '')}"
    r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error",
                        f"-output-directory={work}", str(work / f"{job}.tex")],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode:
        log = (work / f"{job}.log").read_text(errors="replace").splitlines()
        err = next((i for i, line in enumerate(log) if line.startswith("!")), len(log) - 8)
        sys.exit(f"{name}: LuaLaTeX failed:\n" + "\n".join(log[err:err + 8]))
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", str(work / f"{job}.pdf"), str(work / job)], check=True)
    return sorted(work.glob(f"{job}-*.png"))


def font(size, bold=False):
    for f in ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]:
        for d in ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF", "/Library/Fonts"]:
            if Path(d, f).exists():
                return ImageFont.truetype(str(Path(d, f)), size)
    return ImageFont.load_default()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    lite, full = (Path(a).resolve() for a in sys.argv[1:])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tool = ROOT / "tools" / "mtpro2_otf.py"
        for src, ed in ((lite, "Lite"), (full, "Complete")):
            if src.suffix.lower() == ".zip":            # the converter reads an unpacked folder
                with zipfile.ZipFile(src) as z:
                    z.extractall(tmp / f"{ed}-src")
                src = tmp / f"{ed}-src"
            subprocess.run([sys.executable, str(tool), str(src), str(tmp / ed)], check=True,
                           stdout=subprocess.DEVNULL)
        shots = {name: [Image.open(p).convert("L") for p in
                        build(name, ed, tmp / ed if ed else None, tmp)] for name, ed in FONTS}

    label_w, pad, grey = int(30 * MM), int(2 * MM), 110
    small, title_f = font(int(2.4 * MM)), font(int(3.2 * MM), bold=True)

    # symbols: per group and grid row, the three fonts above each other, then the names
    blocks = []
    for gi, (title, cols, w, h, items) in enumerate(GROUPS):
        nrows = -(-len(items) // cols)
        hg, hn = round(h * MM), round(NAME_H * MM)
        imgs = [shots[name][gi] for name, _ in FONTS]
        width = imgs[0].width
        if title:
            t = Image.new("L", (label_w + width, int(7 * MM)), 255)
            ImageDraw.Draw(t).text((0, int(2.2 * MM)), title, font=title_f, fill=0)
            blocks.append(t)
        for r in range(nrows):
            y0 = r * (hg + hn)
            row = Image.new("L", (label_w + width, 3 * hg + hn), 255)
            d = ImageDraw.Draw(row)
            for k, ((name, _), im) in enumerate(zip(FONTS, imgs)):
                row.paste(im.crop((0, y0, width, y0 + hg)), (label_w, k * hg))
                d.text((0, k * hg + hg // 2), name, font=small, fill=grey, anchor="lm")
                if k:
                    d.line((label_w, k * hg, label_w + width, k * hg), fill=225)
            names = imgs[0].crop((0, y0 + hg, width, y0 + hg + hn))
            row.paste(names.point(lambda v: 255 - (255 - v) * (255 - grey) // 255), (label_w, 3 * hg))
            blocks.append(row)
            blocks.append(Image.new("L", (1, pad), 255))
    W = max(b.width for b in blocks) + 2 * pad
    sheet = Image.new("L", (W, sum(b.height for b in blocks) + 2 * pad), 255)
    y = pad
    for b in blocks:
        sheet.paste(b, (pad, y))
        y += b.height
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.convert("P", palette=Image.ADAPTIVE, colors=64).save(OUT / "math-symbols.png", optimize=True)

    # equation
    eqs = [shots[name][-1] for name, _ in FONTS]
    gap = int(5 * MM)
    width = max(e.width for e in eqs)
    sheet = Image.new("L", (label_w + width + 2 * pad, sum(e.height for e in eqs) + gap * 4), 255)
    d = ImageDraw.Draw(sheet)
    y = gap
    for (name, _), e in zip(FONTS, eqs):
        sheet.paste(e, (label_w + pad, y))
        d.text((pad, y + e.height // 2), name, font=small, fill=grey, anchor="lm")
        y += e.height + gap
        if name != FONTS[-1][0]:
            d.line((pad, y - gap // 2, sheet.width - pad, y - gap // 2), fill=215)
    sheet.convert("P", palette=Image.ADAPTIVE, colors=64).save(OUT / "math-equation.png", optimize=True)
    print("written:", OUT / "math-symbols.png", OUT / "math-equation.png")


if __name__ == "__main__":
    main()
