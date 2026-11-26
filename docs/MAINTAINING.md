# Maintaining the template

This is for whoever maintains the template itself. If you are writing a thesis with it, you need none of this: the [README](../README.md) is your guide.

## How the template is put together

| Part | Files | Read by |
|---|---|---|
| PDF kind and standards | `template/documentmetadata.tex` (before `\documentclass`: reads `settings/thesisinfo.tex`, picks PDF/A, PDF/UA or PDF/X), `template/pdfa.tex`, `template/printpdf.tex`, `template/thesisprint.lua` | `main.tex`, `propositions.tex`, `cover.tex` |
| Class | `thesis.cls`: options, page layout, fonts (`template/fontText.tex`, `fontMath.tex`), headings (`formatText.tex`), page styles (`formatPagestyles.tex`), thumb tabs, the committee commands | `main.tex`, `propositions.tex` |
| Packages and commands | `template/packages.tex` (in load order) and `template/commands.tex` | `main.tex`, first line after the class |
| Parts of the book | `template/matter.tex`: `\frontmatter`, `\mainmatter`, `\printreferences`, `\appendix`, `\backmatter` | `template/packages.tex` |
| Tagging | `template/accessibility.tex` (what screen readers get), `template/tagging.tex` and `template/tagging.lua` (workarounds for LaTeX and luamml), `template/nicematrix.tex`/`.lua`, `template/cancel.tex` | `template/packages.tex` |

The user's files (`settings/`, `chapters/`, `figures/`, `main.tex`) hold choices, not machinery. Keep it that way: a change a user would have to copy into their own files needs a migration note in `CHANGELOG.md`.

## Continuous integration

| Workflow | When | What |
|---|---|---|
| `build.yml` | pushes to main, tags, by hand | the thesis on two TeX Live versions (below), all checks, the speech check (AI judge on tags and by hand); on tags, the release files |
| `texlive-image.yml` | when its Dockerfile changes, by hand | the image `ghcr.io/abettini99/tudelft-dissertation-template/texlive:overleaf-2026` |
| `readme-images.yml` | nightly after a day with pushes | the page-size and cover images in the README |
| `nightly.yml` | nightly | the package watch (below) |
| `pac.yml` | releases, Mondays, by hand with a PDF address | PAC 2026 on a Windows runner |
| `lint.yml` | pushes and pull requests that change Python | Ruff |
| `diff.yml`, `quality.yml` | pushes and pull requests that change `.tex` files; links on Mondays | marked-up changes, spelling, chktex, links |

**Two TeX Live versions.** Overleaf's images are private, so `texlive-image.yml` builds our own from the TeX Live archive of the day Overleaf took its copy (`.github/texlive/Dockerfile`, 24 June 2026; it matched all 203 packages of an Overleaf log). The release files come from that build. The second build uses `texlive/texlive:latest` as an early warning. When Overleaf moves to TeX Live 2027, change the archive date and the image tag.

**Package watch.** `.github/watch/probe.tex` fingerprints every command, hook and Lua function of LaTeX and its packages that the template overrides or relies on. `nightly.yml` compares them with `.github/watch/fingerprints.txt` on the latest TeX Live and reports a change. A change means: check the code that depends on it, then refresh the baseline (run the workflow by hand with `update` set to true).

**PAC.** `.github/pac/run_pac.py` drives PAC's window (pywinauto), reads its verdict and the detailed results, and always writes a summary, even when a step fails. `pac_version.py` says when axes4 offers a newer PAC than `PAC_MSI` in `pac.yml`. The runner cannot download artifacts here, so the summary is also printed in the job log.

## Workarounds and when to remove them

Each lives in one place, with a comment saying when it can go. Upstream reports are listed so you know where to look.

| Workaround | Where | Remove when | Reported |
|---|---|---|---|
| Table header scope and column spans written on the cell, beside LaTeX's attribute classes | `template/tagging.tex`, section 6 | PAC reads attribute classes | axes4; LaTeX tagging project (labelled *spurious validation error [PAC]*) |
| Numbers and upright words as one MathML element; packages' MathML given its characters; letterlike letters without `mathvariant="normal"`; no structure for formulas with nothing to read | `template/tagging.lua` | luamml does it itself | not yet |
| Space characters in code listings (`\pdffakespace`) | `template/tagging.tex` | LaTeX's listings support adds them | not yet |
| Tagging suspended while a caption is measured | `thesis.cls` | never: the measuring is the template's own | — |
| Layout tables (`\layouttable`, also inside `\makecell`) | `template/accessibility.tex` | — (a choice, not a workaround) | — |

Known limitations without a workaround are listed in the README (PDF standards, *Known limitations*).

## Fonts

- **ntxmath-otf** (`template/fonts/ntxmath-otf/`) is newtx's maths as OpenType maths fonts, built by `tools/ntxmath_otf.py` (with `tools/mtpro2_otf.py` beside it). Rebuild it when newtx changes.
- **MathTime Professional 2** is converted on the user's machine by `tools/mtpro2_otf.py`. Its licence forbids sharing the fonts, converted or not: they must never reach any repository. `.gitignore` and `tools/hooks/pre-commit` keep them out.
- The README's maths-font images come from `.github/scripts/math_fonts.py`, which needs both MathTime editions, so it runs only locally.

## Releasing

1. Move the *Unreleased* section of `CHANGELOG.md` under the new version, with migration notes for anything users must copy into their own files.
2. Tag it (`v1.2.0`) and publish a release: `build.yml` attaches the PDFs, veraPDF's report and the PDF/UA-1 report; `pac.yml` adds PAC's.
3. Check the AI judge's verdict in the tag's build.
