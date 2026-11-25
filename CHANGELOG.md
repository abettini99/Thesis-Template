# Changelog

Versions follow [semantic versioning](https://semver.org): a change in the last number (1.0.1) only fixes things, in the middle number (1.1.0) adds something without changing what you have, and in the first number (2.0.0) asks you to change something in your thesis when you update; the entry says what.

## Unreleased

- **Speech check:** `tools/check_speech.py` reads the digital edition the way a screen reader does (with `show-pdf-tags` and Speech Rule Engine for the maths) and fails on what a listener would miss: headings without text, figures without alternative text, tables without header cells, links without text, formulas whose MathML says nothing. It writes the whole thesis as read aloud (`speech/spoken.txt`) and what reads differently since the latest release. The build runs it on every push and attaches `spoken.txt` to releases.
- **AI judge (optional):** with a repository secret `ANTHROPIC_API_KEY`, `tools/judge_speech.py` asks Claude whether a blind reader could follow the thesis: PASS or FAIL, and on FAIL `speech-judge.pdf` (itself a tagged PDF/UA-2) says why and how to fix it. This sends the thesis text to Anthropic; without the secret the judge is skipped.
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
