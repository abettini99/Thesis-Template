# Fonts: MathTime Professional 2 (optional)

The template sets maths in **newtx**, a Times-style maths font that comes with TeX Live and Overleaf. If you own **MathTime Professional 2** (MTPro2), Lite (free) or Complete (paid), the template can use it instead. There are two ways; the class picks the first one it finds in this folder:

| In this folder | Maths font | What you get |
|---|---|---|
| the files made by `tools/mtpro2_unicode.py` (`mtpro2.sty`, `mt2*.pfb`, ...) | MathTime, classic fonts **(recommended)** | every macro of the `mtpro2` package (`\xl` to `\XXXL` operators, `\SQRT`, `\widearc`, `\bm`, `\hm` heavy, ...), maths that copies as proper Unicode, PDF/A. LuaLaTeX only |
| `MTPro2Math.otf` / `MTPro2MathLite.otf` | MathTime, OpenType (from mtp2otf) | most of the designs through `unicode-math`, but not mtpro2's macros (no extra-large operators, no heavy weight, no bold symbols). Also works with XeLaTeX |
| nothing | newtx | |

Complete is used if both editions are present. The log says which font is in use: search it for "Maths font". In both cases `\vec`, `\tensor`, `\mathsf`, `\mathcal` and the rest work as before; calligraphic letters stay newtx's simpler ones.

**Lite** has no bold, calligraphic, blackboard bold, script or Fraktur. The template fills these in: bold letters (vectors, tensors) and calligraphic from newtx, blackboard bold and AMS symbols from the AMS fonts, script and Fraktur from Euler (classic route), or bold Greek, blackboard bold and Fraktur from TeX Gyre Termes Math (OpenType route).

## Classic fonts (recommended)

1. **Download MathTime Professional 2.** Lite is free: [mtp2lite.zip](https://mirrors.ctan.org/fonts/mtp2lite.zip) from CTAN (or from [PCTeX](https://www.pctex.com/mtpro2.html)). Complete is sold by [PCTeX](https://www.pctex.com/mtpro2.html) (`mtp2fonts.zip`; there is an academic price).
2. **Put the zip in the template's main folder** (next to `main.tex`), as it is or unpacked.
3. **Run** `python3 tools/mtpro2_unicode.py` from the main folder (Python 3.8 or newer, nothing to install). It finds the installation, gives every glyph a Unicode name, so maths copies correctly and passes the PDF/A check, and writes the result into this folder. Only the glyph names change: shapes and spacing are identical.
4. **Compile with LuaLaTeX through latexmk.** The template's `latexmkrc` adds this folder to TeX's search paths; Overleaf uses latexmk, so there you only upload the contents of this folder. (Running `lualatex` directly, the class cannot see the fonts: it warns and falls back to the next maths font.)

With Complete, the package loads MathTime's own blackboard bold, script and Fraktur. Package options and macros are described in `mtpro2.pdf` in the MathTime download.

## OpenType font

Convert MathTime with [mtp2otf](https://ctan.org/tex-archive/fonts/utilities/mtp2otf) (needs FontForge; see its README, e.g. `./build.sh --edition=lite`) and put the result here under the converter's name: `MTPro2MathLite.otf` (Lite) or `MTPro2Math.otf` (Complete; `MTPro2MathFull.otf` also works).

## Licence: do not share the fonts

MathTime Professional 2 is licensed to you personally. The licence does not allow redistributing it, and that includes the converted files. So:

- **Never** add the fonts to a public repository, including this template or a public copy of your thesis sources. The template's `.gitignore` keeps the MathTime zips and folders and everything in this folder except this README out of git.
- **Overleaf's GitHub synchronisation may not follow `.gitignore`**: if your Overleaf project is linked to a repository, upload the fonts to Overleaf only if that repository is private.
- Embedding the fonts in your thesis PDF is allowed: the licence lets you embed them in documents for transfer, display and printing, so the PDF can be shared and published as usual.
- Check the licence ([Lite](https://ctan.org/tex-archive/fonts/mtp2lite), [Complete](https://www.pctex.com/mtpro2.html)) yourself, also before uploading the fonts to an online service such as Overleaf.

## Accessibility

Both MathTime routes give PDF/A-2u, like newtx: every character, maths included, maps to Unicode, so the PDF can be searched and copied. A fully accessible PDF (PDF/UA: tagged structure, maths as MathML) is a different matter: LaTeX's tagging project does not support the memoir class yet, whichever maths font is used.
