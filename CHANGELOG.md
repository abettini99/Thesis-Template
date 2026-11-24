# Changelog

## 1.0 (24 November 2026)

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

The template is released under the MIT License (see `LICENSE`). Excluded: the TU Delft logo (TU Delft's trademark, to be used only as its brand guidelines allow), Josefin Sans (SIL Open Font License 1.1) and ntxmath-otf (LaTeX Project Public License 1.3). A thesis written with the template is not covered.

### Getting started

Open the README (its *Getting started* section), or use *Use this template* on GitHub and link the copy to Overleaf with the compiler set to LuaLaTeX and TeX Live 2026.
