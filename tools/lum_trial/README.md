# lua-unicode-math trial for ntxmath-otf (branch `lum-trial`, not for merging)

On this branch `_options/ntxmath-otf/ntxmath-otf.sty` and `ntxmath-otf.lua` load
[lua-unicode-math](https://ctan.org/pkg/lua-unicode-math) (0.11, TeX Live 2026) in place of
unicode-math. Everything else in `_options/ntxmath-otf` (fonts, metrics, macros) is unchanged.
mtpro2-otf is not ported.

The variant is made from the unicode-math package that `tools/ntxmath_otf.py build` writes:

    python3 tools/ntxmath_otf.py build /tmp/ntx            # unicode-math version (ntxmath-otf 1.5)
    python3 tools/lum_trial/make_lum.py /tmp/ntx _options/ntxmath-otf

`unicode-math-codes.txt` and `unicode-math-delimiters.txt` hold what the script copies from a
unicode-math run (see below).

## What had to change, and why

| unicode-math feature ntxmath-otf relied on | lua-unicode-math | done here |
|---|---|---|
| `\setmathfont[..., script-features={}, ...]` | `\setmathfont` always adds `ssty` script fonts | NFSS families `NewTXMath`, `NewTXMath-Bold` declared directly, same luaotfload specification; family names keep the microtype wrapper working |
| `math-style=ISO/french` | `\UseInstance{lua-unicode-math-style}{ISO80000-2 / french / TeX}` | options map to the instance |
| `mathrm=sym` | `\mathrm`, `\operator@font` use the text font | `\mathrm` = `\symup`; `\operator@font` sets its "up" attribute (internal constant `\c__l_uni_math_attribute_symup_int`) |
| patch of `\__um_switch_to:n` (nested formulas start with normal letters) | alphabets are an attribute | the attribute is reset at the start of every formula |
| patch of `\__um_delimiter:Nnn` | not needed | removed |
| `\symoperators` / maths family found from `∑`'s mathcode | one family `\symlummain`; `∑` is maths-active | family number passed to Lua |
| commands are fixed code points (`\uppi` stays upright) | every Latin/Greek character of its family is restyled in Lua | glyphs placed by name use alias codes U+100000+ while lua-unicode-math runs, restored before luamml and the package's own layout |
| commands lacking a glyph get the previous definition (`\mapsto`) | its commands are macros that expand to the character | the detection also reads such macros |
| unicode-math's class for symbols the package "provides" | MathClass-15 classes | the class fix for the 299 commands unicode-math had as characters |
| unicode-math's mathcodes/delcodes | different classes for about 300 characters (µ, ∂, ∇, ∴, √, ‖, dashes, ...) | unicode-math's codes copied where they differ (`unicode-math-codes.txt`) |
| `\lbrace`, `\langle`, `\lfloor`, ... as `\Udelimiter` | the character | unicode-math's 59 delimiter commands defined as before |
| `'` (primes), `\root`, amsmath's dots (`\DOTSB`, `\mdots@`, `\dotsb@`) | its own Lua processing | LaTeX's prime, amsmath's macros, `\dotsb@` = `\cdots` as unicode-math sets it |
| maths parameters: maths font in family 0, TeX parameters of families 2/3 take precedence | maths font in family 4, set up last: OpenType values win | families 2 and 3 set again after each size's fonts |

## Results (2026-11-24, TeX Live 2026, this machine)

- **Thesis (newtx, tagged, PDF/A-4f + PDF/UA-2):** identical to ntxmath-otf 1.5 with unicode-math:
  every word's text and box, every page's pixels (100 dpi), the luamml MathML; veraPDF passes both
  profiles; no warnings, no overfull or underfull boxes.
- **Converter tests** (`ntxmath_otf.py selftest --fonts`): basic 227/228 (unicode-math 226/228:
  the classic prime now matches classic newtxmath, where unicode-math's did not); the thesis-like
  document tests identical to classic in all three variants.
- **Stress test: 4135/4272 (unicode-math 4241/4272).** Not ready beyond this thesis:
  `\bm` 3/103 (the package's `\bm` reads unicode-math's letter mathcodes), `\sumintop`,
  `\lgroup`/`\lmoustache` sizes, `\mathcal{xy}_i` and `\mathbb{xy}_i` (multi-letter boxing hooks
  unicode-math's alphabet switch). The thesis chapters use none of these forms.
- **Time per pass:** preamble 4.6 s CPU instead of 5.6 s, whole pass 36.9 s instead of 38.2 s
  (means of three alternating runs; wall-clock times vary by about ±2 s).

## For mtpro2-otf

The same steps, plus: its three versions (normal, bold, heavy) as NFSS families; the Lite
`\boldmath` fallback's attribute next to lua-unicode-math's; its own `\bm` (the same work as
above); and the unicode-math codes and delimiter list taken from an mtpro2-otf run.
