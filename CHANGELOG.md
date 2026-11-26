# Changelog

Versions follow [semantic versioning](https://semver.org): a change in the last number (1.0.1) only fixes things, in the middle number (1.1.0) adds something without changing what you have, and in the first number (2.0.0) asks you to change something in your thesis when you update; the entry says what.

## 2.0.0 (26 November 2026)

### Simpler to use (version 2: your files change)

The pages are the same as before, to the pixel, in every edition. What changes is what you edit: your files now hold only your choices.

- **`main.tex`** lists the parts of the book: `\frontmatter`, `\mainmatter`, `\printreferences`, `\appendix`, `\backmatter`. The page styles, page numbering, contents styles, bookmarks, thumb tabs and line spacing that `main.tex` used to set itself are done by these commands (`template/matter.tex`). `\tableofcontents`, `\listoffigures` and `\listoftables` start their own page; the contents get their bookmark.
- **Chapters:** the page style follows by itself (the chapter and the section in the running heads, or only the chapter when it has no sections, and *Appendix A* in the appendices), and `\chapter*` in the front and back matter adds itself to the contents. The `\pagestyle` after `\chapter` and the `\addcontentsline` after `\chapter*` can go.
- **`settings/packages.tex`** holds only your own packages, and **`settings/commands.tex`** your notation. The template's packages and settings (siunitx, tables, listings, hyperref, cleveref, statements, algorithms, ...) are in `template/packages.tex`, its commands (`\repeatcaption`, `\doi`, `\orcid`, `\file`, `\chapterbasedon`, `\panelref`, the list layout) in `template/commands.tex`, read by `main.tex` before your files.
- **The committee** in `settings/thesisinfo.tex` is a list of `\member[role]{name}{affiliation}` and `\membergroup{heading}`, no longer table rows. The promotors in the propositions (`\thesispromotors`, `\thesispromotorsdutch`) and the PDF title (`\thesispdftitle`) are derived; you can still set them yourself.
- **`propositions.tex` and `cover.tex`** hold only the propositions and the cover's settings: their layout is in `template/propositions.tex` and `template/cover.tex`, read by one line each. The cover takes late changes through a hook: `\AddToHook{thesis/cover/settings}{\coverguidesfalse}` at the top of `cover.tex`.
- **The README** is about a third shorter and is for writing a thesis. The details moved to `docs/`: [PDF-STANDARDS.md](docs/PDF-STANDARDS.md) (the standards in detail), [AI-JUDGE.md](docs/AI-JUDGE.md) (setting up the AI judge) and [MAINTAINING.md](docs/MAINTAINING.md) (CI, workarounds, releasing).

**Updating from 1.x.** Your old files keep working with the new `template/` and `thesis.cls` (tested: the same pages). To take up the simpler files, in this order:

1. Replace the body of `main.tex` from `\begin{document}` on with the new one, put your chapters back in, and add `\input{template/packages}` before `\input{settings/packages}`.
2. At the same time, replace `settings/packages.tex` and `settings/commands.tex` with the new ones and copy in what you added yourself. (Steps 1 and 2 go together: the old `settings/packages.tex` loaded the template's packages itself, which the new `main.tex` now does.)
3. Remove `\pagestyle{...}` after `\chapter` and `\addcontentsline{toc}{chapter}{...}` after `\chapter*` in your chapters (optional: they still work).
4. Replace the preamble of `propositions.tex` (the commands up to `\begin{document}`, and the two lines after it) with `\input{template/propositions}`, and `cover.tex` from its `\def\thesisforprinter` on with the new one (optional: the old files still work).
5. Rewrite the committee in `settings/thesisinfo.tex` with `\member` and `\membergroup` and remove `\thesispromotors`, `\thesispromotorsdutch` and `\thesispdftitle` (optional: the old table rows still work, as long as `\thesispromotors` stays set).

### Accessibility and checks

- **Contents and lists:** no longer use tocloft; LaTeX's own entry commands with tocloft's measurements give the same pages (identical to the pixel), and every entry is tagged properly (TOCI, Reference, Link) on every TeX Live. With the tocloft of Overleaf's TeX Live 2026 (2.3i), entries lost that structure, and an entry with maths failed PDF/UA-2.
- **Table cells:** a header cell's scope (column, row or both) and a `\multicolumn` cell's column span are now also written on the cell itself, next to LaTeX's attribute classes. PAC does not read attribute classes and reported every header cell (59 in the example thesis) as having no data cells; now none. veraPDF accepted both; the pages are unchanged.
- **Layout tables:** tables that only place text are no longer tagged as tables but as text blocks, so screen readers read them as text and checkers no longer ask for their header cells: the committee and colophon on page iv, the curriculum vitae, the QR code with its label, and the small tabular inside each `\makecell` or `\thead` (a header broken over two lines is now one header cell, not a table inside it). For your own: `\layouttable` before the tabular, in a group. If your `chapters/Z_CurriculumVitae.tex` is older, put `\begingroup\layouttable` after its `\addcontentsline` and `\endgroup` at the end. PAC's incomplete tables went from 7 to 0; the pages are unchanged.
- **Code listings:** the spaces between words are now space characters in the tagged text. listings sets each word in its own box, so the text read "importnumpyasnp"; screen readers now hear "import numpy as np". Indentation still has no characters.
- **Formulas (MathML):** a number is now one number: `\num{6.02214076e23}` was six pieces (6, ".", 022, 140, 76) that could be read as a product, and any decimal number written with a point was split at it. A word in upright letters (`\mathrm{disc}`, `u_\mathrm{eff}`, units) is now one word, not spelled letter by letter; `\mathsf{B}\mathsf{v}` stays two symbols. Boxes with nothing to read (the link target hyperref raises above an equation) no longer appear, so no equation holds an empty formula inside its MathML any more.
- **Formulas in the structure tree:** what screen readers read from the tagged structure now matches the MathML file. Operator names (`\inf`, `\sup`, `\max`, `\operatorname`), `\cdots` and the other composite symbols, and the merged numbers and words had empty elements there, with their characters loose in the formula; they now hold their text. The italic h (ℎ) and the other letters of the Letterlike Symbols block lose a wrong `mathvariant="normal"` ("normal italic h"). The empty formula inside hyperref's link target no longer becomes a second `<math>` in the equation's structure. Captions are no longer tagged while they are measured, so a formula in a caption is no longer there twice, once empty.
- **Panels** (`panels`): the shared axis titles (`xlabel`, `ylabel`) are artifacts; each panel's alternative text names its axes, and on their own they were read as loose formulas after the figure.
- **Chapter headings:** the label above the title ("CHAPTER 1") is now part of the heading in the tagged PDF; it was an artifact, so the heading read only "Introduction" where plain LaTeX reads "Chapter 1 Introduction".
- **Contents:** the entries for the contents, the list of figures and the list of tables now refer to their own heading. They were written before it and referred to what came before: the list of figures' entry to the contents, the contents' entry to the whole document.
- **QR codes** (`\qrlink`): the code itself is now an artifact inside the link, no longer a figure without alternative text; the link keeps its description. PAC reported the figure.
- **Doctoral committee** (`settings/thesisinfo.tex`): the *Independent members* and *Other members* lines span the table as paragraph cells (`p{\textwidth}`), so the spaces after them are no longer tagged as artifacts in the text. If your `settings/thesisinfo.tex` is older, replace `\multicolumn{2}{@{}l}` with `\multicolumn{2}{@{}p{\textwidth}@{}}` there; the page looks the same.
- **README:** a list of known limitations (formula alternate text, nicematrix, siunitx `S` columns, PAC's contents check), with what to do about each.
- **Speech check** (`tools/speech`): ClearSpeak with its preference to read the dot operator as "dot", so the divergence is "nabla dot u", not "nabla times u" (which a listener takes for the curl). `SPEECH_PREFERENCES` sets others.
- **Continuous integration:** every push builds on TeX Live as Overleaf has it (an image of the TeX Live repository of 24 June 2026; all 203 packages the thesis loads match an Overleaf log) and on the latest TeX Live. A PDF/UA-1 report (`tools/check_ua1.py`) shows how PAC sees the digital edition, and WTPDF 1.0 failures now fail the build. PAC itself runs after every release and on Mondays (`.github/workflows/pac.yml`): its PDF report and a summary are attached to the release, and the run says when axes4 offers a newer PAC.
- **Speech check:** `tools/check_speech.py` reads the digital edition the way a screen reader does (with `show-pdf-tags` and Speech Rule Engine for the maths) and fails on what a listener would miss: headings without text, figures without alternative text, captioned tables without header cells, silent links, formulas whose MathML says nothing. It writes the whole thesis as read aloud (`speech/spoken.txt`) and what reads differently since the latest release. The build runs it on every push and attaches `spoken.txt` to releases.
- **AI judge (optional):** `tools/judge_speech.py` asks a language model whether a blind reader could follow the thesis, beyond what the rules check: PASS or FAIL, and on FAIL `speech-judge.pdf` (itself a tagged PDF/UA-2) says why and how to fix it. Claude with a repository secret `ANTHROPIC_API_KEY`, or any provider with an OpenAI-compatible API (OpenAI, Mistral, Gemini, OpenRouter, a model of your own behind Ollama) with `SPEECH_JUDGE_API_KEY`, `SPEECH_JUDGE_URL` and `SPEECH_JUDGE_MODEL`. It runs for tags and runs by hand (every push with the variable `SPEECH_JUDGE_BACKEND`). This sends the thesis text to that provider; without a key the judge is skipped. (Small open models run on GitHub's own runners were tried and dropped: 15–50 minutes per run and verdicts too unreliable to act on.)
- `tools/check_speech.py` also warns about numbers split into two formulas (siunitx table columns read as "1", then "period 342").
- **Continuous integration:** the build also runs `tools/check_bib.py` and lists the hyphenated words in the run's summary. New workflows: *Changes since a version* (`tools/diff_versions.py` against the newest tag, on pushes and pull requests) and *Text quality* (codespell and chktex on changed `.tex` files; every Monday, `tools/check_links.py` checks the DOIs and web addresses). Dependabot keeps the actions and Speech Rule Engine up to date.

## 1.1.0 (24 November 2026)

- **Cover:** a fourth colour, `coversecondary`, for the small lines (*Doctoral thesis · TU Delft*, *About the author*, the spine mark); before, they followed the text colour. Fixed: with a light text colour on a dark cover, the front title stayed black. If your `settings/cover.tex` is older, add `\colorlet{coversecondary}{covertext!75}` to it.
- **Preview edition:** now a plain PDF (no PDF/A, tagging or attachments): it is only for looking at the trimmed book, and as a plain PDF it cannot be mistaken for the printer's file.
- **README:** the cover in four colour schemes, with their values, under *Propositions and cover*, and links to sample PDFs.
- **Releases:** a tag or a release published on GitHub gets the final PDFs attached: `thesis-digital.pdf`, `thesis-print.pdf`, `thesis-preview.pdf`, `cover.pdf` (without the guides), `propositions.pdf` and veraPDF's report. Before, only the digital edition, named after the tag.
- **Continuous integration:** the README images workflow (formerly *Page sizes*) also renders the cover variants and checks each for print, and commits an image only when it looks different. A new *Lint* workflow checks the Python scripts with Ruff on every push.
- **Python scripts:** `tools/mtpro2_otf.py` and `tools/ntxmath_otf.py` run on Python 3.10 and 3.11 again (they used syntax new in 3.12). All scripts reformatted with Ruff; what they produce is unchanged.

## 1.0.0 (24 November 2026)

First release of the TU Delft PhD thesis template, for **LuaLaTeX on TeX Live 2026** (Overleaf included).

### What it does

- **One source, four editions** with the same pages and page numbers: `digital` (screen and repository), `printer` (PDF/X-6 or PDF/X-4, with bleed), `preview` (the trimmed book on screen) and `proof` (centred on A4 or Letter for a home print).
- **Archival and accessible:** the digital final version is PDF/A-4f and PDF/UA-2 (tagged, with MathML for every formula). It passes veraPDF.
- **Print-ready:** PDF/X output, sRGB images, sideways pages rotated, crop marks on request. `tools/check_print.py` checks the file before it goes to the printer.
- **Four page sizes:** demy (default), A5, royal and the Dutch 170 × 240 mm. Text block, margins and type size follow automatically.
- **Three versions while writing:** `fast-draft` (fastest, untagged), `draft` (for supervisors, with line numbers) and `final` (tagged, with todo notes and change marks removed).
- **Layout:** chapter abstracts set apart beside the epigraphs, ISO-style section numbers, thumb tabs (switchable for the digital edition in `settings/thumbs.tex`) and brick-red links that meet WCAG contrast.
- **Your files apart from the template's:** `settings/`, `chapters/` and `figures/` are yours. An update replaces only `template/`, `tools/` and `thesis.cls`.
- **Checks and tools** for the PDF, figures, bibliography (including DOI lookup) and hyphenation, a Python plot style matched to the thesis, plus the propositions and the cover with spine.
- **Maths:** bundled ntxmath-otf, or MathTime Professional 2 if you own it. A pre-commit hook keeps the MathTime fonts out of git.
- **Continuous integration:** every push builds the printer and digital editions, the propositions and the cover, and runs the checks. The page-size image in the README is regenerated overnight after any day with changes. A nightly job watches the LaTeX packages the template patches and reports any that changed, now including the parts of luamml's Lua code the MathML fixes rely on.

### Licence

The template is released under the MIT License (see `LICENSE`). Excluded (see `EXCEPTIONS.md`): the TU Delft logo (TU Delft's trademark, to be used only as its brand guidelines allow), Josefin Sans (SIL Open Font License 1.1) and ntxmath-otf (LaTeX Project Public License 1.3). A thesis written with the template is not covered.

### Getting started

Open the README (its *Getting started* section), or use *Use this template* on GitHub and link the copy to Overleaf with the compiler set to LuaLaTeX and TeX Live 2026.
