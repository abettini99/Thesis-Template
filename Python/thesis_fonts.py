"""Figure text in the thesis's own fonts: TeX Gyre Termes for text, and for maths MathTime Professional 2
when tools/mtpro2_unicode.py has prepared it in Fonts/ (as the class does), otherwise newtx.

Matplotlib typesets each label with LuaLaTeX (its pgf backend), so a figure's $\\alpha$, $C_L$ and
$\\Vert\\nabla\\boldsymbol{e}\\Vert$ are the same glyphs as in the text. Without LuaLaTeX it falls back to
matplotlib's own maths in Times New Roman (or STIX, if Times New Roman is not installed).

    import thesis_fonts
    maths = thesis_fonts.setup()   # "MathTime Complete", "MathTime Lite", "newtx", "Times New Roman" or "STIX"
    ...
    thesis_fonts.save(fig, "Images/my_figure.pdf")

setup("newtx") forces newtx, e.g. for figures that go into a public repository.
"""
import os
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.text

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "Fonts"
_state = {"pgf": False}

# The same choices as _options/fontText.tex and _options/fontMath.tex (fonts at their nominal size:
# the figure's own point sizes are what get printed).
_TEXT = r"""
\usepackage[no-math]{fontspec}
\setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, BoldFont=*-bold,
    ItalicFont=*-italic, BoldItalicFont=*-bolditalic, Ligatures=TeX]
\usepackage{amsmath}
\usepackage{luatex85}% \pdfgentounicode and friends, which newtx and glyphtounicode.tex use
\pdfgentounicode=1
\input{glyphtounicode}
"""
_NEWTX = r"""
\let\thesisrm\rmdefault \renewcommand{\rmdefault}{ntxtlf}
\usepackage{newtxmath}
\let\rmdefault\thesisrm
\usepackage{bm}
"""
_MATHTIME = r"""
\input{mtpro2-glyphtounicode}
\pdfextension mapfile{+mtpro2.map}
%% MathTime has three designs: small (below 7 pt), script (7-9 pt) and text (9 pt and up). Labels in a
%% figure (7-8.5 pt) are its main text, set in Times, which has one design: give their maths the text
%% design too, which matches Times in width and weight. Exponents and indices keep the small design.
\directlua{
    local define = luatexbase.remove_from_callback("define_font", "luaotfload.define_font")
    luatexbase.add_to_callback("define_font", function(name, size, id)
        if size >= 7 * 65536 and name:match("^mt2.+s$") then
            local t = name:sub(1, -2) .. "t"
            if kpse.find_file(t, "tfm") then name = t end
        end
        return define(name, size, id)
    end, "thesis.mtpro2-design")
}
%s
\DeclareFontEncoding{LMS}{}{}\DeclareFontSubstitution{LMS}{ntxsy}{m}{n}
\DeclareMathAlphabet{\mathcal}{LMS}{ntxsy}{m}{n}
"""
_COMPLETE = r"""\usepackage[complete, mtpbb, mtpscr, mtpfrak, nofontinfo]{mtpro2}
\usepackage{bm}
\let\boldsymbol\bm
"""
_LITE = r"""\usepackage{amssymb}
\usepackage[lite, nofontinfo]{mtpro2}
\DeclareMathAlphabet{\mathscr}{U}{eus}{m}{n}
\DeclareMathAlphabet{\thesisbfit}{OML}{ntxmi}{b}{it}
\usepackage{bm}
\renewcommand{\boldsymbol}[1]{\thesisbfit{#1}}
"""


def mathtime_edition():
    """'Complete', 'Lite' or None, as the class decides."""
    if (FONTS / "mtpro2-glyphtounicode.tex").exists() and (FONTS / "mtpro2.sty").exists():
        return "Complete" if (FONTS / "mt2bmit.pfb").exists() else "Lite"
    return None


def setup(maths="auto"):
    """Use the thesis fonts for all figures from here on. maths: "auto", "mathtime" or "newtx"."""
    if shutil.which("lualatex") is None:
        _state["pgf"] = False
        return _fallback()
    edition = mathtime_edition() if maths in ("auto", "mathtime") else None
    if maths == "mathtime" and edition is None:
        raise FileNotFoundError("No MathTime fonts in Fonts/: run tools/mtpro2_unicode.py first")
    if edition:
        # LuaLaTeX finds the prepared fonts in Fonts/ (latexmkrc does the same for the thesis)
        for var in ("TEXINPUTS", "TFMFONTS", "T1FONTS", "TEXFONTMAPS", "ENCFONTS"):
            os.environ[var] = str(FONTS) + "//" + os.pathsep + os.environ.get(var, "")
        preamble = _TEXT + _MATHTIME % (_COMPLETE if edition == "Complete" else _LITE)
        name = f"MathTime {edition}"
    else:
        preamble = _TEXT + _NEWTX
        name = "newtx"
    mpl.rcParams.update({
        "pgf.texsystem": "lualatex",
        "pgf.rcfonts": False,            # the fonts come from the preamble
        "pgf.preamble": preamble,
        "text.usetex": False,
        "font.family": "serif",
    })
    _state["pgf"] = True
    return name


def _fallback():
    """Without LuaLaTeX: matplotlib's own text and maths in Times New Roman, if installed (Windows,
    macOS), otherwise in STIX, the Times-like font that ships with matplotlib."""
    from matplotlib import font_manager
    try:
        font_manager.findfont("Times New Roman", fallback_to_default=False)
    except ValueError:
        mpl.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral"], "mathtext.fontset": "stix"})
        print("thesis_fonts: no LuaLaTeX and no Times New Roman, figure text in STIX")
        return "STIX"
    settings = {
        "font.family": "serif", "font.serif": ["Times New Roman"],
        "mathtext.fontset": "custom",
        "mathtext.rm": "Times New Roman", "mathtext.it": "Times New Roman:italic",
        "mathtext.bf": "Times New Roman:bold", "mathtext.bfit": "Times New Roman:bold:italic",
        "mathtext.cal": "Times New Roman:italic",  # (matplotlib looks for a "cursive" font otherwise)
        "mathtext.fallback": "stix",     # symbols Times New Roman lacks (e.g. some arrows)
    }
    mpl.rcParams.update({k: v for k, v in settings.items() if k in mpl.rcParams})  # bfit: 3.8+
    print("thesis_fonts: no LuaLaTeX, figure text in Times New Roman (matplotlib's own maths)")
    return "Times New Roman"


def save(fig, path, **kwargs):
    """Save a figure as PDF in the thesis fonts (or with matplotlib's own, after a fallback)."""
    path = Path(path)
    if _state["pgf"]:
        fig.savefig(path, backend="pgf", **kwargs)
    else:
        # Matplotlib 3.11 and later join "ff", "fi", "fl" into ligatures, which its PDF output stores
        # as a missing glyph (the PDF/A check fails, the text cannot be copied): switch them off.
        for text in fig.findobj(matplotlib.text.Text):
            if hasattr(text, "set_fontfeatures"):
                text.set_fontfeatures(["-liga", "-clig"])
        fig.savefig(path, **kwargs)
