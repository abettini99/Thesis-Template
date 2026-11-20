# Thesis template

A LaTeX template for a TU Delft PhD dissertation, built on the `memoir` class. It produces either a printable book (with bleed, crop marks and thumb tabs) or a report version of the same pages centred on A4.

## Compiling

Compile with **LuaLaTeX**. In Overleaf: *Menu → Settings → Compiler → LuaLaTeX*. Locally, `latexmk main.tex` does everything (the included `latexmkrc` selects LuaLaTeX).

- LuaLaTeX lets `microtype` stretch letters very slightly, which halves the number of hyphenated lines and gives evener word spacing.
- The bibliography uses **biblatex + biber**, which Overleaf runs automatically. The nomenclature needs no extra tool.
- The first compile on a new machine (or a new Overleaf project) takes longer while LuaLaTeX builds its font cache.
- XeLaTeX also works (it is somewhat faster), but the class prints a warning as a reminder.

## Faster compiling

A long thesis gets slow because every chapter, figure and plot is processed on every compile. While writing:

1. **Compile only the chapter you are working on.** In `main.tex`, uncomment `\includeonly{...}` and list the chapter(s), for example `\includeonly{Chapters/03Method}`. Page numbers and references to the other chapters are kept from the last full compile. Comment it out again for a full compile. (Chapters must be added with `\include{...}`, not `\input{...}`, for this to work.)
2. **Use the `draft` option.** Images are replaced by labelled boxes, overfull lines get a black bar in the margin, and every page says *DRAFT* with the date. Remove it for the final version. Overleaf's *Recompile → Fast [draft]* does the image part as well.
3. **Keep heavy plots out of the document.** Make plots in Python (matplotlib) or similar and include them as PDF. A TikZ drawing is redrawn on every compile, so keep TikZ for small diagrams.
4. **Keep images light.** Use vector PDF for plots and diagrams. For photos and renders, use JPG (or PNG for screenshots) at no more than about 300 dpi at the size they are printed: a figure 100 mm wide needs about 1200 pixels, not 6000.
5. **Load only what you use.** Optional packages are listed, commented out, at the bottom of `_options/packages.tex`.

(Automatic caching of TikZ pictures with the `memoize` package was tested and left out: it clashes with biblatex and depends on Perl modules that are not available everywhere.)

## Archival PDF (PDF/A)

The PDF is produced as **PDF/A-2u**, the archival standard: fonts are embedded, colours are defined against the sRGB colour profile, every character (maths included) maps to Unicode so text can be searched and copied reliably, and the file carries standard metadata. It will display the same in decades. This is set by `\DocumentMetadata{...}` in the first lines of `main.tex`, which must stay the first command in the file. The same PDF works for the printer and for the TU Delft repository.

- **Colours:** all template colours are RGB or grey. Use RGB (or greyscale) images and colours in your own figures as well; CMYK images break PDF/A.
- **Checking:** the template passes the standard PDF/A-2u checks with both engines, but have the final PDF validated once with [veraPDF](https://verapdf.org) (free) or Adobe Acrobat's preflight.
- **PDF/A-4** (the newest version, based on PDF 2.0) also compiles: use `pdfstandard = A-4, pdfversion = 2.0`. It is not more archival than 2u for this document, and older tools support it less well, so 2u is the safer choice.
- **Accessible (tagged) PDF**, the higher PDF/UA and PDF/A "a" levels, is not possible yet: the `memoir` class, the `caption` package and the `newtxmath` maths font are not yet compatible with LaTeX's tagging code, and several other packages have not been tested with it.

## Class options

Set in the first line of `main.tex`, for example:

```latex
\documentclass[print,thumb,showtrims]{personal}
```

| Option | Effect |
|---|---|
| `dover` *(default)*, `a5`, `royal`, `tudelft` | Book page size: 137 × 213 mm (the classic Dover paperback, 5⅜ × 8⅜ in), 148 × 210 mm, 156 × 234 mm or 170 × 240 mm. Text block, margins and chapter-title size follow automatically. Dover is set in 9.5 pt type on 12.4 pt leading, like the Dover paperbacks; the other sizes in 10 pt on 13.2 pt. Check that your printer offers the size. |
| `print` | Book version: the page plus 2 mm bleed on every side, chapters start on right-hand pages. Without it you get the report version: the same page centred on A4, no blank pages. |
| `thumb` | Chapter thumb tabs on the page edge (print version only). Appendices continue below the last chapter; the spacing adapts so all tabs fit on the page (it uses the chapter count from the previous compile, so compile twice after adding chapters). |
| `showtrims` | Crop marks showing where the page is trimmed (print) or where the book page sits on A4 (report). |
| `british` *(default)*, `american` | Language: hyphenation, quotation marks and dates. |
| `showframe` | Shows the page layout frames, for checking the layout. |
| `draft` | Fast compiles while writing: images as boxes, overfull lines marked, *DRAFT* and the date on every page. |
| `final` | The version for the printer and the repository: hides all todo notes. |
| `backreferences` | Each reference in the bibliography ends with the pages it is cited on: "(cited on pages 12, 45)". |
| `chapterbib` | Every chapter ends with its own reference list instead of one list at the end of the book, as is common for a thesis built from papers. |

## Where things are

| File | Contents |
|---|---|
| `main.tex` | Document structure: which chapters are included, in which order, and `\includeonly` for compiling single chapters. |
| `_thesisinfo.tex` | **Fill this in:** title, author, defence date, Rector Magnificus, doctoral committee, keywords, printer, ISBN. Used on the title pages, CV and in the PDF metadata. |
| `_titlepage.tex` | Title page, official TU Delft dissertation page, committee and colophon page. |
| `Chapters/` | Front matter (`00…`), chapters (`01…`, `02…`), appendices (`A_…`) and back matter (`Z_…`). |
| `Chapters/02Examples.tex` | Demonstrations of everything the template supports. Delete it (and the `lipsum`/`blindtext` lines in `main.tex`) once you no longer need it. |
| `_nomenclature.tex` | **Fill this in:** acronyms and symbols for the nomenclature. |
| `Chapters/00Nomenclature.tex` | Prints the nomenclature lists. |
| `references.bib` | Bibliography database. |
| `personal.cls` | The class: page layout, options, core packages. |
| `_options/` | Fonts, heading styles, page styles, colours, extra packages, custom commands. |

## Writing

- **Cross-references:** use `\cref{...}` (gives "Figure 2.1", "Equation (2.3)", "Section 2.1") and `\Cref{...}` at the start of a sentence.
- **Citations:** `\cite{key}` for [1], `\citet{key}` for "Author [1]", `\citeauthor{key}`, `\citeyear{key}`.
- **Units:** `\qty{1.225}{\kilo\gram\per\cubic\metre}`, `\num{6.02e23}`, `\unit{\metre\per\second}` (siunitx).
- **Custom maths commands** (in `_options/commands.tex`): `\vec{u}` and `\tensor{\tau}` (plain italics by default; switch both to bold, arrows or underlines in one place), `\grad`, `\div`, `\curl`, `\deriv{y}{x}`, `\pderiv{y}{x}`, `\sderiv{y}{t}` (material derivative), `\transpose`, `\cddot`, and dimensionless numbers such as `\Re`, `\Ma`, `\Pr`.
- **Todo notes:** `\todo{...}` puts a note in the margin, `\todo[inline]{...}` in the text, `\missingfigure{...}` a placeholder figure. The class option `final` removes them all.
- **Figures and tables:** prefer `[tbp]` placement over `[H]`, so floats don't leave half-empty pages. Set full-width blocks that are *not* inside a figure or table environment with `\noindent` in front, so they don't pick up the paragraph indent.
- **Acronyms and symbols:** define them once in `_nomenclature.tex` and use them with `\gls{label}`. An acronym is written out in full the first time ("blade element momentum theory (BEM)") and abbreviated afterwards; a symbol is printed as defined, in text or maths. In headings and captions, use `\glsfmtshort{label}` for acronyms. Everything defined appears in the nomenclature; delete `\glsaddall` in `Chapters/00Nomenclature.tex` to list only what the text actually uses.

  | Command | List |
  |---|---|
  | `\nomacronym{label}{SHORT}{long form}` | Acronyms |
  | `\nomdimless{label}{symbol}{description}{definition}` | Dimensionless numbers |
  | `\nomlatin[sort]{label}{symbol}{description}{dimensions}{units}` | Latin symbols |
  | `\nomgreek{label}{symbol}{description}{dimensions}{units}` | Greek symbols |
  | `\nomsuper{label}{symbol}{description}` | Superscripts |
  | `\nomsub{label}{symbol}{description}` | Subscripts |

  Symbols, dimensions and definitions are written as maths without `$...$` (dimensions with `\Lunit`, `\Munit`, `\Tunit`, `\Qunit`); write `--` for a dimensionless quantity. Latin symbols are sorted by the optional sort key (the label if none is given); Greek symbols and sub- and superscripts appear in the order they are defined.

- **A chapter based on a published paper:** see `Chapters/01Introduction.tex` for the chapter opener with an epigraph, a short abstract and a "parts of this chapter have been published in…" note. To include the published PDF itself, uncomment `pdfpages` in `_options/packages.tex` and use `\includepdf[pages=-]{paper.pdf}`.

## Plots

Make plots in Python with the style file `Python/thesis.mplstyle` (see `Python/example_plot.py`):

```python
import matplotlib.pyplot as plt
plt.style.use("Python/thesis.mplstyle")
```

It sets Times (or STIX, a Times-like font included with matplotlib), text at about the caption size (7.5–8.5 pt for the Dover default; add 0.5 pt for the other page sizes), a default size of 92 mm wide, colour-blind-safe colours each with its own line style (so lines stay apart in greyscale), and PDF output with embedded TrueType fonts, as needed for PDF/A. Make each figure at the size it will be printed, and include it with `\includegraphics{...}` without scaling, so the text in the figure keeps its size:

| Page size | Full text width | Half width (two side by side) |
|---|---|---|
| `dover` | 92 mm (3.62 in) | 44 mm (1.73 in) |
| `a5` | 100 mm (3.94 in) | 48 mm (1.89 in) |
| `royal` | 105 mm (4.13 in) | 50 mm (1.98 in) |
| `tudelft` | 113 mm (4.45 in) | 54 mm (2.13 in) |

## Print costs

Printers usually charge every page that contains any colour as a colour page. So the print version keeps everything that appears on many pages black and white: the thumb tabs are black, links are invisible and code listings use bold and grey instead of colours. Colour in your own figures is fine; it only affects the pages they are on.

## Overleaf ↔ GitHub

This repository is synced with Overleaf (*Menu → GitHub*).

- Before editing elsewhere (locally, or with Claude), **push** from Overleaf so the repository has your latest version.
- After changes were committed to the repository, **pull** in Overleaf to bring them in.
