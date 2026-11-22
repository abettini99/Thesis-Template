# Fonts: MathTime Professional 2 (optional)

The template sets maths in **newtx**, a Times-style maths font that comes with TeX Live and Overleaf. If you own **MathTime Professional 2** (MTPro2), Lite (free) or Complete (paid), the template uses it instead once `tools/mtpro2_otf.py` has converted it into this folder: OpenType maths fonts plus a small package, `mtpro2-otf`, that places every symbol exactly where the classic Type 1 fonts put it. Every macro of the `mtpro2` package works (`\xl` to `\XXXL` operators, `\SQRT`, `\widearc`, `\bm`, `\hm` heavy, ...), maths copies from the PDF as proper Unicode, and the PDF stays PDF/A-4f.

The class uses whichever edition the files were made from; the log says which maths font is in use (search it for "Maths font"). `\vec`, `\tensor`, `\mathsf`, `\mathcal` and the rest work as with newtx; calligraphic letters stay newtx's simpler ones. With Complete you get MathTime's own bold, heavy, blackboard bold, script and Fraktur. **Lite** has none of these: the package takes bold letters (vectors, tensors) from newtx, blackboard bold and the AMS symbols from the AMS fonts, and script and Fraktur from Euler, as the Type 1 set-up does.

## Setting it up

1. **Download MathTime Professional 2.** Lite is free: [mtp2lite.zip](https://mirrors.ctan.org/fonts/mtp2lite.zip) from CTAN (or from [PCTeX](https://www.pctex.com/mtpro2.html)). Complete is sold by [PCTeX](https://www.pctex.com/mtpro2.html) (`mtp2fonts.zip`; there is an academic price).
2. **Unpack the zip** anywhere, for instance next to `main.tex` (`.gitignore` keeps it out of git).
3. **Convert it:** `pip install fonttools`, then from the main folder
   `python3 tools/mtpro2_otf.py path/to/the/unpacked/folder Fonts`
   It needs a TeX Live installation (it reads a few LaTeX files) and takes about 20 seconds. It writes the fonts, the package and `mtpro2-otf-manifest.txt` into this folder; run again (for instance after switching between Lite and Complete), it removes only files of its own that it no longer writes. `python3 tools/mtpro2_otf.py --selftest path/to/the/unpacked/folder` checks the result against the Type 1 fonts.
4. **Compile with LuaLaTeX through latexmk.** The template's `latexmkrc` adds this folder to TeX's search paths; Overleaf uses latexmk, so there you upload the contents of this folder and set **TeX Live 2026**. (Running `lualatex` directly, the class cannot see the fonts: it warns and uses newtx.)

The package's options are `mtpro2`'s, set in `_options/fontMath.tex`; the full list is in the comments of `tools/mtpro2_otf.py` and in `mtpro2.pdf` from the MathTime download. Files from the older Type 1 route of this template (`mtpro2.sty`, `*.pfb`, `mtpro2-glyphtounicode.tex`, ...) can be deleted from this folder.

Commands that LaTeX or the maths font already have (`\div`, `\Re`, `\vec`, ...) are redefined at the start of the document, see `_options/commands.tex`: with MathTime, unicode-math sets them up only then. Do the same for redefinitions of your own.

## Licence: do not share the fonts

MathTime Professional 2 is licensed to you personally. The licence does not allow redistributing it, and that includes the converted files and the package the converter writes (it holds metrics and macros taken from MathTime). So:

- **Never** add the fonts to a public repository, including this template or a public copy of your thesis sources. The template's `.gitignore` keeps the MathTime zips and folders and everything in this folder except this README out of git. For a second lock, run `git config core.hooksPath tools/hooks` once in your clone: git then refuses any commit containing MathTime files, even ones forced past `.gitignore` or renamed (a thesis PDF with the fonts embedded is still allowed).
- **Overleaf's GitHub synchronisation may not follow `.gitignore`**: if your Overleaf project is linked to a repository, upload the fonts to Overleaf only if that repository is private.
- Embedding the fonts in your thesis PDF is allowed: the licence lets you embed them in documents for transfer, display and printing, so the PDF can be shared and published as usual.
- Check the licence ([Lite](https://ctan.org/tex-archive/fonts/mtp2lite), [Complete](https://www.pctex.com/mtpro2.html)) yourself, also before uploading the fonts to an online service such as Overleaf.

## Accessibility

With MathTime the PDF is PDF/A-4f, as with newtx: every character, maths included, maps to Unicode, so the PDF can be searched and copied. A fully accessible PDF (PDF/UA: tagged structure, maths as MathML) is a different matter: LaTeX's tagging project does not support the memoir class yet, whichever maths font is used.
