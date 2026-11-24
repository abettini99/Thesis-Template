"""Figure text in the thesis's own fonts: TeX Gyre Termes for text, and for maths MathTime Professional 2
when tools/mtpro2_otf.py has written it into Fonts/ (as the class does), otherwise newtx.

Matplotlib typesets each label with LuaLaTeX (its pgf backend), so a figure's $\\alpha$, $C_L$ and
$\\Vert\\nabla\\boldsymbol{e}\\Vert$ are the same glyphs as in the text. Without LuaLaTeX it falls back to
matplotlib's own maths in Times New Roman (or STIX, if Times New Roman is not installed).

    import thesis_fonts
    maths = thesis_fonts.setup()   # "MathTime Complete", "MathTime Lite", "newtx", "Times New Roman" or "STIX"
    ...
    thesis_fonts.save(fig, "Images/my_figure.pdf")

setup("newtx") forces newtx, e.g. for figures that go into a public repository.
"""
import sys
import os
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.text

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "Fonts"
NTXOTF = ROOT / "_options" / "ntxmath-otf"   # newtx as OpenType maths fonts, part of the template
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
_NTXOTF = r"""
\usepackage{ntxmath-otf}
\let\boldsymbol\bm
\AddToHook{begindocument/end}{\ifdefined\normalUnderscoreDef\normalUnderscoreDef\fi}
"""
_MATHTIME = r"""
\usepackage[ntxcal]{mtpro2-otf}
\let\boldsymbol\bm
%% (matplotlib loads underscore.sty, which makes _ active; mtpro2's macros give the active _ a meaning of
%% their own: give it back to underscore.sty)
\AddToHook{begindocument/end}{\ifdefined\normalUnderscoreDef\normalUnderscoreDef\fi}
"""


def mathtime_edition():
    """'Complete', 'Lite' or None, as the class decides (from what tools/mtpro2_otf.py wrote)."""
    sty = FONTS / "mtpro2-otf.sty"
    if sty.exists() and (FONTS / "MTPro2Math.otf").exists():
        return "Lite" if "\\def\\MTPOTFedition{Lite}" in sty.read_text(encoding="latin-1") else "Complete"
    return None


def setup(maths="auto"):
    """Use the thesis fonts for all figures from here on. maths: "auto", "mathtime" or "newtx"."""
    if shutil.which("lualatex") is None:
        _state["pgf"] = False
        return _fallback()
    edition = mathtime_edition() if maths in ("auto", "mathtime") else None
    if maths == "mathtime" and edition is None:
        raise FileNotFoundError("No MathTime fonts in Fonts/: run tools/mtpro2_otf.py first (Fonts/README.md)")
    if edition:
        # LuaLaTeX finds the fonts and the package in Fonts/ (latexmkrc does the same for the thesis)
        for var in ("TEXINPUTS", "OPENTYPEFONTS", "LUAINPUTS"):
            os.environ[var] = str(FONTS) + os.pathsep + os.environ.get(var, "")
        preamble = _TEXT + _MATHTIME
        name = f"MathTime {edition}"
    elif (NTXOTF / "ntxmath-otf.sty").exists():
        # the same glyphs as classic newtxmath, as in the thesis (latexmkrc adds the folder there)
        for var in ("TEXINPUTS", "OPENTYPEFONTS", "LUAINPUTS"):
            os.environ[var] = str(NTXOTF) + os.pathsep + os.environ.get(var, "")
        preamble = _TEXT + _NTXOTF
        name = "newtx"
    else:
        preamble = _TEXT + _NEWTX
        name = "newtx"
    mpl.rcParams.update({
        "pgf.texsystem": "lualatex",
        "pgf.rcfonts": False,            # the fonts come from the preamble
        # images (imshow, rasterised plots) without smoothing: matplotlib asks for it, but PDF/A forbids it
        "pgf.preamble": preamble + r"\makeatletter\define@key{Gin}{interpolate}[true]{}\makeatother",
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
    _print_ready(path)


def _print_ready(path):
    """Declare the figure's RGB as sRGB and make black and greys true grey (tools/print_ready.py), so the
    printer converts its colours exactly and small text prints with black ink only. Skipped, with a note,
    without pikepdf or Pillow: the figure is then fine on screen, and tools/check_print.py names it."""
    if path.suffix.lower() != ".pdf":
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        from print_ready import make_print_ready
        make_print_ready(path)
    except ImportError as err:
        print(f"note: {path.name} not made print-ready ({err}); pip install -r requirements.txt")
