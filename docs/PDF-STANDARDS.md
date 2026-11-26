# PDF standards in detail

The background to the README's *PDF standards* section: what each standard is, what the template does for it, and what you can do. If you only want to hand in a valid thesis, the README is enough.

The same pages come out as two kinds of PDF, each to its own standard: the digital edition (and the proof edition) as an archival PDF, **PDF/A-4f**, and in the final version (`version=final`) an accessible one as well, **PDF/UA-2**; the printer edition (`edition=printer`) as **PDF/X-6**, or **PDF/X-4**. The preview edition, only for looking at, is a plain PDF. `\input{template/documentmetadata}` at the top of `main.tex` (and of `propositions.tex` and `cover.tex`) switches on LaTeX's PDF management, and tagging for PDF/UA, with the standard that fits the edition named in `\documentclass`. It is required: the class stops with an error without it. Tagging makes each compile slower, so only the final version is tagged; the drafts are the same pages without it (see *Faster compiling* in the README).

Archival and accessible PDF, roughly from least to most demanding:

| Standard | Year, base | What it guarantees on top of the row above |
|---|---|---|
| PDF/A-1b | 2005, PDF 1.4 | Looks the same for decades: fonts embedded, colours defined, nothing external |
| PDF/A-2b | 2011, PDF 1.7 | Newer features allowed (transparency, layers, JPEG 2000) |
| PDF/A-2u | 2011, PDF 1.7 | All text maps to Unicode, so it can be searched and copied |
| PDF/A-3u | 2012, PDF 1.7 | Files of any kind may be attached (data, code) |
| **PDF/A-4f** | 2020, PDF 2.0 | The same guarantees on PDF 2.0; Unicode always required; attachments allowed. **← this template** |
| PDF/A-2a, -4 with tags | | Tagged: headings, lists, tables and figures marked up for screen readers |
| **PDF/UA-2 (with PDF/A-4f)** | 2024, PDF 2.0 | Fully accessible: tagged, alt text, maths as MathML. **← this template** |

PDF for the printer, roughly from oldest to newest:

| Standard | Year, base | Colour | What it adds |
|---|---|---|---|
| PDF/X-1a | 2001/2003, PDF 1.3/1.4 | CMYK and spot colours only | Fonts embedded, no transparency, no RGB: the file is ready for one press as it is |
| PDF/X-3 | 2002/2003, PDF 1.3/1.4 | Also RGB and Lab, with a colour profile | Colour managed: the printer converts the colours for their own press |
| **PDF/X-4** | 2008/2010, PDF 1.6 | As PDF/X-3 | Transparency and layers kept as they are, not flattened. **← `X-4`** |
| PDF/X-5 | 2008/2010, PDF 1.6 | As PDF/X-3 | PDF/X-4 with parts kept outside the file (images, the colour profile) |
| **PDF/X-6** | 2020, PDF 2.0 | As PDF/X-3 | PDF/X-4 on PDF 2.0, which also allows a colour profile per page. **← `X-6` (default)** |

`tools/print_pdf.py` converts either to CMYK, keeping the version (see *If the printer wants CMYK* below); PDF/X-1a is not made by the template.

## Archival and accessible: PDF/A, PDF/UA

The digital edition is produced as **PDF/A-4f**, the current archival standard (on PDF 2.0), and as **PDF/UA-2**, the accessibility standard: fonts are embedded, colours are defined against the sRGB colour profile, every character (maths included) maps to Unicode so text can be searched and copied reliably, and the file carries standard metadata. It will display the same in decades. It is also tagged: headings, lists, tables, figures with their captions and alt text, footnotes and code are marked up for screen readers, and every formula carries MathML. This is set up in `template/pdfa.tex` with LaTeX's own PDF management, which the class loads right after reading `settings/thesisinfo.tex`; the metadata (title, author, keywords, language) comes from `settings/thesisinfo.tex`, so there is nothing to edit there.

- **Colours:** all template colours are RGB or grey. Use RGB (or greyscale) images and colours in your own figures as well; CMYK images break PDF/A.
- **Checking:** the digital and proof editions pass veraPDF's PDF/A-4f, PDF/UA-2 and WTPDF 1.0 (Accessibility and Reuse) checks. `python3 tools/check_pdf.py` checks your compiled PDF (see *Before you hand it in* in the README); it runs [veraPDF](https://verapdf.org) (free) for a full validation when that is installed, otherwise have the final PDF validated once with veraPDF or Adobe Acrobat's preflight. Valid tagging is not yet good speech: `python3 tools/check_speech.py main.pdf` reads the PDF the way a screen reader does and writes it all down in `speech/spoken.txt` (formulas in words), with the problems a listener would run into (needs TeX Live's `show-pdf-tags` and, for the maths, Node.js: `npm ci --prefix tools/speech`). The build on GitHub runs it on every push.
- **PAC and Acrobat** check accessibility against the older PDF/UA-1 (PDF 1.7), so on a PDF/UA-2 file they report things that are correct in PDF 2.0. `python3 tools/check_ua1.py` runs veraPDF's PDF/UA-1 profile, built on the same test conditions as [PAC](https://pac.pdf-accessibility.org), and sorts the findings: those a PDF/UA-2 file cannot avoid (its PDF version, the MathML in formulas and other PDF 2.0 structure types, the repeated header rows of long tables), those worth fixing (formulas without alternate text, for now), and anything unexplained. Useful when someone runs PAC on your thesis and asks about its findings. PAC itself runs on the template's releases (see [docs/MAINTAINING.md](docs/MAINTAINING.md)).
- **Metadata:** the PDF carries title, author, keywords, licence and, once filled in in `settings/thesisinfo.tex`, the ISBN, the DOI the TU Delft repository gives your dissertation (`\thesisdoi`) and your ORCID iD. Repositories and reference managers read them. Fields still holding their placeholder (`[978-94-...]`, the example ORCID iD) are left out. The licence is a short code, `\thesislicence{CC BY 4.0}` (or CC BY-SA, CC BY-ND, CC BY-NC, CC BY-NC-SA, CC BY-NC-ND 4.0, CC0 1.0, or empty for all rights reserved); it sets the sentence on the colophon, its link and the metadata. The colophon's link to the repository goes to your DOI once `\thesisdoi` is filled in.
- **Attachments** (`template/attachments.tex`): PDF/A-4f allows files inside the PDF; viewers list them in their attachments panel.
  - *Citation file:* `citation.bib` and `citation.ris` (EndNote, Zotero, Mendeley) for citing the thesis, made from `settings/thesisinfo.tex` on every compile.
  - *Data of a figure:* `\figuredata[description]{figures/plot.csv}` right after the `\includegraphics` attaches the file as the data of that figure (in the tagged PDF it belongs to the image); in a `panels` grid, `\panel[data={file}]{...}{...}`.
  - *Other files:* `\supplementfile[description]{file}` attaches any file to the thesis as a whole, e.g. the script that draws the figures.
  - Keep them small; large data sets belong in a repository such as 4TU.ResearchData, cited with their DOI.
- **Accessibility is partly yours:** the tagging is automatic, but screen readers can only read what you write. Give every figure alt text (see *Alt text* in the README), and write tables with a header row (`\toprule` ... `\midrule`, as in the Examples chapter).
- **What else screen readers get** (`template/accessibility.tex`, no change to the pages):
  - *Words in maths:* operator names (`\sin`, `\max`, `\DeclareMathOperator`) and `\mathword{Re}` are read as one word, not letter by letter; use `\mathword` for multi-letter names such as dimensionless numbers (the template's `\Re`, `\Ma`, ... do).
  - *Tables:* the first row of every table float (and of `xltabular`) is its header, so each cell is read with its column heading. A header of two rows: `\tagpdfsetup{table/header-rows={1,2}}` in the table before the tabular; a first column that heads its rows: `\tagpdfsetup{table/header-columns=1}`.
  - *Formulas:* every formula carries MathML; for one that reads badly (a large block matrix), `\formulaalt{a short description}` right before it gives screen readers that text instead.
  - *Acronyms:* after its first use, `\gls{bem}` gives "BEM" marked with its expansion, read as "blade element momentum theory".
  - *Units:* `\qty{10}{\metre\per\second}` is read as "10 metres per second" and `\unit{\kilo\gram}` as "kilograms", for units written with siunitx's macros (not for `\unit{m/s}`).
  - *Contrast:* the template's colours stand out against the page (text 4.5:1 or more, lines 3:1, WCAG 2.2), and links (brick red) also against the black text (3.9:1), as colour is the only thing that marks them; `tools/check_pdf.py` and `tools/check_figures.py` report colours of your own that do not (see *Colours* under *Plots and figures* in the README).
  - *Languages:* text in `\begin{otherlanguage}{dutch}` (the Dutch summary and propositions) is marked as Dutch, and a word in `\foreignlanguage{dutch}{...}` too, so screen readers switch pronunciation.
  - *Links:* each link also carries a short description (where it goes), which PDF/UA-1 checkers such as PAC and Acrobat ask for.
- **Known limitations:** listed in the README (*PDF standards*), with what to do about each.

## For the printer: PDF/X

The printer edition (`edition=printer`) is made as a **PDF/X** file, the standard for handing print files over: PDF/X-6 (on PDF 2.0) by default, or PDF/X-4 for printers whose systems do not take PDF 2.0 yet. Three settings in `settings/thesisinfo.tex`, next to the printer's name; ask your printer about each:

```latex
\newcommand{\thesisprintstandard}{X-6}  % or X-4
\newcommand{\thesisprintprofile}{}      % the printer's colour profile (.icc); {} for FOGRA39
\newcommand{\thesisbleed}{2mm}          % often 2 or 3 mm
```

What the file carries:
- **Trim and bleed:** every page says where it will be cut (the trim box) and how far the background runs past the cut (the bleed box). Crop marks are off: the printer places their own. If they ask for marks, add `cropmarks`; they go in a margin outside the bleed.
- **Colour, managed:** a screen mixes red, green and blue light, a press puts cyan, magenta, yellow and black ink on paper, and somebody has to convert one to the other. The file stays RGB, with every RGB colour (text, drawings, photos, figures) given in sRGB explicitly, so it means one exact colour, and the printer converts it for their own press and paper, which is where it is best done. Black text and greys stay grey and print with black ink only (as "rich black", a mix of all four inks, small text would get coloured fringes wherever the four printing plates do not line up exactly). The file names the press it was made for (the *output intent*): the printer's colour profile, or FOGRA39 (offset print on coated paper, the one that comes with TeX Live). For this RGB route the standard profile is fine; the printer's own is nice to have. Newer standard profiles (PSO Coated v3, PSO Uncoated v3) are free downloads from the ECI; set the file name if your printer uses one.
- **Nothing else:** no links (nothing clickable is allowed on the printed page), no attachments, no tagging; fonts embedded. The digital edition stays the archival, accessible one.
- **The cover and the propositions** are made the same way, with the same settings (the cover's bleed is set in `settings/cover.tex`).

**Figures.** LaTeX gives the RGB on its pages in sRGB, photos (RGB PNG and JPEG) included, but it cannot reach inside an included figure PDF. Figures saved with `thesis_fonts.save` are made ready for print as they are saved. For a figure PDF made elsewhere (a co-author's plot, another program), run `python3 tools/print_ready.py figures/figure.pdf`: the same treatment, nothing changes on screen.

**Check it:** `python3 tools/check_print.py main.pdf` (also run by `tools/check_pdf.py` for a PDF/X file). It reports what a printer's preflight rejects (no trim box, RGB not given in sRGB, named by figure file and page, fonts not embedded, links, images below 225 ppi) and what is worth a look (images below 300 ppi, lines thinner than 0.1 mm, small text in rich black), with the page count and the pages in colour. It is not an official PDF/X validator (those are commercial, such as Adobe Acrobat Pro's preflight): send the file through your printer's own file check as well; most printers offer one free.

**If the printer wants CMYK.** Some printers ask for every colour converted to their inks in the file itself. `python3 tools/print_pdf.py main.pdf --profile printer.icc` writes `main-cmyk.pdf`: every colour and image converted with the printer's profile, black and greys still black ink only, the same PDF/X version. Ask for their profile first: CMYK is ink amounts for one press and one paper, and a file converted for another has to be converted again (without `--profile` it uses FOGRA39, with a warning). CMYK cannot show the brightest screen colours, so saturated blues and greens come out a little duller; look at the result before sending it. **PDF/X-1a** (CMYK without transparency, still asked for by some printers) is not made by these tools: it needs Adobe Acrobat Pro or Ghostscript 10.05 or later.

**What to ask your printer:** which PDF/X version (PDF/X-6, PDF/X-4, PDF 2.0 or not), their colour profile (needed for CMYK, optional otherwise), RGB or CMYK, the bleed for the pages and for the cover, crop marks or none, the paper thickness (for the spine), and whether the page count must be a multiple of 4, 8 or 16 (they add blank pages at the end).

## Print costs

Printers usually charge every page that contains any colour as a colour page. So the print editions keep everything that appears on many pages black and white: the thumb tabs are light grey (black ink only), links are not coloured and code listings use bold and grey instead of colours. Colour in your own figures is fine; it only affects the pages they are on. `tools/check_print.py` lists the pages in colour (the number to quote); `tools/greyscale_preview.py` shows the thesis in greyscale.
