# Changelog

Versions follow [semantic versioning](https://semver.org): a change in the last number (1.0.1) only fixes things, in the middle number (1.1.0) adds something without changing what you have, and in the first number (2.0.0) asks you to change something in your thesis when you update; the entry says what.

## Unreleased

- **Contents and lists:** no longer use tocloft; LaTeX's own entry commands with tocloft's measurements give the same pages (identical to the pixel), and every entry is tagged properly (TOCI, Reference, Link) on every TeX Live. With the tocloft of Overleaf's TeX Live 2026 (2.3i), entries lost that structure, and an entry with maths failed PDF/UA-2.
- **Table cells:** a header cell's scope (column, row or both) and a `\multicolumn` cell's column span are now also written on the cell itself, next to LaTeX's attribute classes. PAC does not read attribute classes and reported every header cell (59 in the example thesis) as having no data cells; now none. veraPDF accepted both; the pages are unchanged.
- **Layout tables:** tables that only place text are no longer tagged as tables but as text blocks, so screen readers read them as text and checkers no longer ask for their header cells: the committee and colophon on page iv, the curriculum vitae, the QR code with its label, and the small tabular inside each `\makecell` or `\thead` (a header broken over two lines is now one header cell, not a table inside it). For your own: `\layouttable` before the tabular, in a group. If your `chapters/Z_CurriculumVitae.tex` is older, put `\begingroup\layouttable` after its `\addcontentsline` and `\endgroup` at the end. PAC's incomplete tables went from 7 to 0; the pages are unchanged.
- **Code listings:** the spaces between words are now space characters in the tagged text. listings sets each word in its own box, so the text read "importnumpyasnp"; screen readers now hear "import numpy as np". Indentation still has no characters.
- **Formulas (MathML):** a number is now one number: `\num{6.02214076e23}` was six pieces (6, ".", 022, 140, 76) that could be read as a product, and any decimal number written with a point was split at it. A word in upright letters (`\mathrm{disc}`, `u_\mathrm{eff}`, units) is now one word, not spelled letter by letter; `\mathsf{B}\mathsf{v}` stays two symbols. Boxes with nothing to read (the link target hyperref raises above an equation) no longer appear, so no equation holds an empty formula inside its MathML any more.
- **Panels** (`panels`): the shared axis titles (`xlabel`, `ylabel`) are artifacts; each panel's alternative text names its axes, and on their own they were read as loose formulas after the figure.
- **QR codes** (`\qrlink`): the code itself is now an artifact inside the link, no longer a figure without alternative text; the link keeps its description. PAC reported the figure.
- **Doctoral committee** (`settings/thesisinfo.tex`): the *Independent members* and *Other members* lines span the table as paragraph cells (`p{\textwidth}`), so the spaces after them are no longer tagged as artifacts in the text. If your `settings/thesisinfo.tex` is older, replace `\multicolumn{2}{@{}l}` with `\multicolumn{2}{@{}p{\textwidth}@{}}` there; the page looks the same.
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
- **Continuous integration:** every push builds the printer and digital editions, the propositions and the cover, and runs the checks. The page-size image in the README is regenerated overnight after any day with changes. A nightly job watches the LaTeX packages the template patches and reports any that changed.

### Licence

The template is released under the MIT License (see `LICENSE`). Excluded (see `EXCEPTIONS.md`): the TU Delft logo (TU Delft's trademark, to be used only as its brand guidelines allow), Josefin Sans (SIL Open Font License 1.1) and ntxmath-otf (LaTeX Project Public License 1.3). A thesis written with the template is not covered.

### Getting started

Open the README (its *Getting started* section), or use *Use this template* on GitHub and link the copy to Overleaf with the compiler set to LuaLaTeX and TeX Live 2026.
