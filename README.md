# Thesis template

A LaTeX template for a TU Delft PhD dissertation, built on the `memoir` class. It produces either a printable book (with bleed, crop marks and thumb tabs) or a report version of the same pages centred on A4.

## Compiling

The template compiles with **LuaLaTeX** or **XeLaTeX**. In Overleaf: *Menu → Settings → Compiler*.

| | LuaLaTeX *(recommended for the final version)* | XeLaTeX |
|---|---|---|
| Justification | Better: `microtype` can also stretch letters very slightly, which halves the number of hyphenated lines and gives evener word spacing | Good |
| Speed | About 1.4× slower | Faster, handy while writing |

The bibliography uses **biblatex + biber**, which Overleaf runs automatically. Locally, `latexmk -lualatex main.tex` (or `-xelatex`) does everything. The nomenclature needs no extra tool.

## Faster compiling

A long thesis gets slow because every chapter, figure and plot is processed on every compile. While writing:

1. **Compile only the chapter you are working on.** In `main.tex`, uncomment `\includeonly{...}` and list the chapter(s), for example `\includeonly{Chapters/03Method}`. Page numbers and references to the other chapters are kept from the last full compile. Comment it out again for a full compile. (Chapters must be added with `\include{...}`, not `\input{...}`, for this to work.)
2. **Use the `draft` option.** Images are replaced by labelled boxes, overfull lines get a black bar in the margin, and every page says *DRAFT* with the date. Remove it for the final version. Overleaf's *Recompile → Fast [draft]* does the image part as well.
3. **Keep heavy plots out of the document.** A TikZ/pgfplots plot with a lot of data is redrawn on every compile. Either make it in a separate small `standalone` document, compile that once and include the resulting PDF with `\includegraphics`, or make the plot in Python (matplotlib) and save it as PDF. Small diagrams and simple plots are fine inline.
4. **Keep images light.** Use vector PDF for plots and diagrams. For photos and renders, use JPG (or PNG for screenshots) at no more than about 300 dpi at the size they are printed: a figure 100 mm wide needs about 1200 pixels, not 6000.
5. **Load only what you use.** Optional packages are listed, commented out, at the bottom of `_options/packages.tex`.

(Automatic caching of TikZ pictures with the `memoize` package was tested and left out: it clashes with biblatex and depends on Perl modules that are not available everywhere.)

## Archival PDF (PDF/A)

The PDF is produced as **PDF/A-2b**, the archival standard: fonts are embedded, colours are defined against the sRGB colour profile, and the file carries standard metadata, so it will display the same in decades. This is set by `\DocumentMetadata{...}` in the first lines of `main.tex`, which must stay the very first thing in the file. The same PDF works for the printer and for the TU Delft repository.

- **Colours:** all template colours are RGB or grey. Use RGB (or greyscale) images and colours in your own figures as well; CMYK images break PDF/A-2b.
- **Checking:** the template passes the standard PDF/A-2b checks, but have the final PDF validated once with [veraPDF](https://verapdf.org) (free) or Adobe Acrobat's preflight.
- **Accessible (tagged) PDF**, the higher PDF/UA and PDF/A "a" levels, is not possible yet: the `memoir` class, `caption`/`subcaption` and `pgfplots` are not yet compatible with LaTeX's tagging code.

## Class options

Set in the first line of `main.tex`, for example:

```latex
\documentclass[print,thumb,showtrims]{personal}
```

| Option | Effect |
|---|---|
| `a5` *(default)*, `royal`, `tudelft` | Book page size: 148 × 210 mm, 156 × 234 mm or 170 × 240 mm. Text block, margins and chapter-title size follow automatically. |
| `print` | Book version: the page plus 2 mm bleed on every side, chapters start on right-hand pages. Without it you get the report version: the same page centred on A4, no blank pages. |
| `thumb` | Chapter thumb tabs on the page edge (print version only). |
| `showtrims` | Crop marks showing where the page is trimmed (print) or where the book page sits on A4 (report). |
| `british` *(default)*, `american` | Language: hyphenation, quotation marks and dates. |
| `showframe` | Shows the page layout frames, for checking the layout. |
| `draft` | Fast compiles while writing: images as boxes, overfull lines marked, *DRAFT* and the date on every page. |

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
- **Custom maths commands** (in `_options/commands.tex`): `\vec{u}` (bold, underlined vector), `\grad`, `\div`, `\curl`, `\deriv{y}{x}`, `\pderiv{y}{x}`, `\sderiv{y}{t}` (material derivative), `\transpose`, `\cddot`, and dimensionless numbers such as `\Re`, `\Ma`, `\Pr`.
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

## Overleaf ↔ GitHub

This repository is synced with Overleaf (*Menu → GitHub*).

- Before editing elsewhere (locally, or with Claude), **push** from Overleaf so the repository has your latest version.
- After changes were committed to the repository, **pull** in Overleaf to bring them in.
