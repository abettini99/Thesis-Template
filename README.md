# Thesis template

A LaTeX template for a TU Delft PhD dissertation, built on the `memoir` class. It produces either a printable book (with bleed, crop marks and thumb tabs) or a report version of the same pages centred on A4.

## Compiling

- Compile with **XeLaTeX** (LuaLaTeX should also work). In Overleaf: *Menu → Settings → Compiler → XeLaTeX*.
- The bibliography uses **biblatex + biber** and the nomenclature uses **makeindex**. Overleaf runs both automatically. Locally, `latexmk -xelatex main.tex` does the same.

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

## Where things are

| File | Contents |
|---|---|
| `main.tex` | Document structure: which chapters are included, in which order. |
| `_thesisinfo.tex` | **Fill this in:** title, author, defence date, Rector Magnificus, doctoral committee, keywords, printer, ISBN. Used on the title pages, CV and in the PDF metadata. |
| `_titlepage.tex` | Title page, official TU Delft dissertation page, committee and colophon page. |
| `Chapters/` | Front matter (`00…`), chapters (`01…`, `02…`), appendices (`A_…`) and back matter (`Z_…`). |
| `Chapters/02Examples.tex` | Demonstrations of everything the template supports. Delete it (and the `lipsum`/`blindtext` lines in `main.tex`) once you no longer need it. |
| `Chapters/00Nomenclature.tex` | The list of symbols. |
| `references.bib` | Bibliography database. |
| `personal.cls` | The class: page layout, options, core packages. |
| `_options/` | Fonts, heading styles, page styles, colours, extra packages, custom commands. |

## Writing

- **Cross-references:** use `\cref{...}` (gives "Figure 2.1", "Equation (2.3)", "Section 2.1") and `\Cref{...}` at the start of a sentence.
- **Citations:** `\cite{key}` for [1], `\citet{key}` for "Author [1]", `\citeauthor{key}`, `\citeyear{key}`.
- **Units:** `\qty{1.225}{\kilo\gram\per\cubic\metre}`, `\num{6.02e23}`, `\unit{\metre\per\second}` (siunitx).
- **Custom maths commands** (in `_options/commands.tex`): `\vec{u}` (bold, underlined vector), `\grad`, `\div`, `\curl`, `\deriv{y}{x}`, `\pderiv{y}{x}`, `\sderiv{y}{t}` (material derivative), `\transpose`, `\cddot`, and dimensionless numbers such as `\Re`, `\Ma`, `\Pr`.
- **Figures and tables:** prefer `[tbp]` placement over `[H]`, so floats don't leave half-empty pages. Set full-width blocks that are *not* inside a figure or table environment with `\noindent` in front, so they don't pick up the paragraph indent.
- **Nomenclature:** add symbols in `Chapters/00Nomenclature.tex`, one command per group:

  | Command | Group | Arguments |
  |---|---|---|
  | `\nomtypeA{symbol}{description}` | Acronyms | |
  | `\nomtypeD{symbol}{description}{definition}` | Dimensionless numbers | |
  | `\nomtypeR{symbol}{description}{dimensions}{unit}` | Latin symbols | |
  | `\nomtypeG{symbol}{description}{dimensions}{unit}` | Greek symbols | |
  | `\nomtypeS{symbol}{description}` | Superscripts | |
  | `\nomtypeU{symbol}{description}` | Subscripts | |

- **A chapter based on a published paper:** see `Chapters/01Introduction.tex` for the chapter opener with an epigraph, a short abstract and a "parts of this chapter have been published in…" note. To include the published PDF itself, use `\includepdf[pages=-]{paper.pdf}` (pdfpages).

## Overleaf ↔ GitHub

This repository is synced with Overleaf (*Menu → GitHub*).

- Before editing elsewhere (locally, or with Claude), **push** from Overleaf so the repository has your latest version.
- After changes were committed to the repository, **pull** in Overleaf to bring them in.
