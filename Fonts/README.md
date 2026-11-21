# Fonts: MathTime Professional 2 (optional)

The template sets maths in **newtx**, a Times-style maths font that comes with TeX Live and Overleaf. If you put an OpenType version of **MathTime Professional 2** (MTPro2) in this folder, the template uses it instead, automatically:

| File in this folder | Maths font |
|---|---|
| `MTPro2Math.otf` (or `MTPro2MathFull.otf`) | MathTime Professional 2 Complete: every alphabet from MathTime itself |
| `MTPro2MathLite.otf` | MathTime Professional 2 Lite. Lite has no bold italic, calligraphic, blackboard bold or Fraktur: calligraphic letters and bold Latin letters (vectors, tensors) come from newtx, as without MathTime; bold Greek, blackboard bold and Fraktur from TeX Gyre Termes Math |
| neither | newtx |

If both are present, the Complete version is used. (With XeLaTeX instead of LuaLaTeX, everything Lite lacks comes from TeX Gyre Termes Math, as XeLaTeX cannot mix in the newtx letters.) The log says which one: search it for "Maths font".

## Getting the font

1. **Download MathTime Professional 2.** Lite is free: from [PCTeX](https://www.pctex.com/mtpro2.html) or [CTAN](https://mirrors.ctan.org/fonts/mtp2lite.zip). Complete is sold by [PCTeX](https://www.pctex.com/mtpro2.html) (there is an academic price).
2. **Convert it to OpenType** with [mtp2otf](https://ctan.org/tex-archive/fonts/utilities/mtp2otf), following its README (for example `./build.sh --edition=lite` for Lite). The fonts come as Type 1 files; the template needs the single OpenType maths font the converter makes.
3. **Keep the converter's file name**, `MTPro2MathLite.otf` (Lite) or `MTPro2Math.otf` (Complete; `MTPro2MathFull.otf` also works), and put it in this `Fonts` folder of **your own thesis** project (upload it in Overleaf, or add it to your private thesis repository).
4. **Compile** with LuaLaTeX as usual. Nothing else needs changing: `\vec`, `\tensor`, `\mathsf`, `\mathcal` and the rest work the same with both maths fonts.

## Licence: do not share the font

MathTime Professional 2 is licensed to you personally; the licence does not allow redistributing it, and that includes the converted OpenType file. So:

- **Never** add the font to a public repository, including this template or a public copy of your thesis sources. Keep it only in a **private** repository or project.
- Embedding it in your thesis PDF is allowed: the licence lets you embed the fonts in documents for transfer, display and printing, so the PDF can be shared and published as usual.
- Check the licence ([Lite](https://ctan.org/tex-archive/fonts/mtp2lite), [Complete](https://www.pctex.com/mtpro2.html)) yourself, also before uploading the font to an online service such as Overleaf.
