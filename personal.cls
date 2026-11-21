\ProvidesClass{personal}[2026/11/21 v2.0 TU Delft dissertation class, based on memoir]
%% PDF version 1.4 without object streams, as pdfx and hyperref expect for PDF/A (see _options/pdfa.tex);
%% it has to be set before anything writes to the PDF.
\ifdefined\pdfvariable \pdfvariable majorversion=1 \pdfvariable minorversion=4 \pdfvariable objcompresslevel=0 \fi

%% Options. Language: british (default) or american. Page size: dover (default), a5, royal or tudelft.
\newcommand*{\thesis@language}{british}
\DeclareOption{british}{\renewcommand*{\thesis@language}{british}}
\DeclareOption{american}{\renewcommand*{\thesis@language}{american}}
\newcommand*{\thesis@pagesize}{dover}
\DeclareOption{dover}{\renewcommand*{\thesis@pagesize}{dover}}
\DeclareOption{a5}{\renewcommand*{\thesis@pagesize}{a5}}
\DeclareOption{royal}{\renewcommand*{\thesis@pagesize}{royal}}
\DeclareOption{tudelft}{\renewcommand*{\thesis@pagesize}{tudelft}}
%% Edition: the same book pages, prepared for where they go.
%%   digital           : final size, for the screen (maroon links, coloured code, sideways pages
%%                       upright); for the repository, sharing and writing (default)
%%   print-preparation : with 2 mm bleed, for the professional printer
%%   print-showcase    : final size, as on paper: the printed book as it looks after trimming
%%   print-report      : on an A4 sheet (letter: US Letter), for printing a proof at home; with showtrims,
%%                       crop marks show where to cut
%% The print editions are set for paper: links invisible, code in black and white, no rotated pages.
\newcommand*{\thesis@edition}{digital}
\DeclareOption{digital}{\renewcommand*{\thesis@edition}{digital}}
\DeclareOption{print-preparation}{\renewcommand*{\thesis@edition}{print-preparation}}
\DeclareOption{print-showcase}{\renewcommand*{\thesis@edition}{print-showcase}}
\DeclareOption{print-report}{\renewcommand*{\thesis@edition}{print-report}}
\newif\if@letter
\DeclareOption{letter}{\@lettertrue}
\newif\if@thumb
\DeclareOption{thumb}{\@thumbtrue}
\DeclareOption{showtrims}{\PassOptionsToClass{\CurrentOption}{memoir}} % crop marks (print-preparation, print-report)
\newif\if@showframe
\DeclareOption{showframe}{\@showframetrue}
%% draft: fast compiles while writing. Images become labelled boxes, overfull lines are marked
%% with a black bar in the margin, and every page says DRAFT so it is never mistaken for the final version.
\newif\if@draft
\DeclareOption{draft}{\@drafttrue \PassOptionsToPackage{draft}{graphicx} \PassOptionsToClass{draft}{memoir}}
%% final: the version for the printer and the repository; hides all \todo notes.
\DeclareOption{final}{\PassOptionsToPackage{disable}{todonotes}}
%% backreferences: each reference lists the pages it is cited on. (Not called "backref": that name
%% would also switch on hyperref's own back-references.)
\newif\if@backref
\DeclareOption{backreferences}{\@backreftrue}
%% chapterbib: every chapter ends with its own reference list (a thesis built from papers).
\newif\ifchapterbib
\DeclareOption{chapterbib}{\chapterbibtrue}
\ProcessOptions\relax
\def\thesis@paper{trimmed}
\def\thesis@tmp{print-preparation}\ifx\thesis@edition\thesis@tmp \def\thesis@paper{bleed}\fi
\def\thesis@tmp{print-report}\ifx\thesis@edition\thesis@tmp \def\thesis@paper{sheet}\fi
\def\thesis@tmp{american}
\ifx\thesis@language\thesis@tmp \def\thesis@bcp{en-US}\else \def\thesis@bcp{en-GB}\fi % language in the PDF metadata

%% This template is set up for LuaLaTeX (better justification, PDF/A-2u maths). XeLaTeX still works.
\ifdefined\directlua\else
    \ClassWarningNoLine{personal}{This template is meant to be compiled with LuaLaTeX.\MessageBreak
        In Overleaf: Menu > Settings > Compiler > LuaLaTeX}
\fi

%% Public switch, for files outside the class (\ifprintversion ... \else ... \fi): true for the print
%% editions (links invisible, code in black and white, no rotated pages), false for digital.
\newif\ifprintversion
\def\thesis@tmp{digital}\ifx\thesis@edition\thesis@tmp\else \printversiontrue \fi

%% Page sizes. Per size: trimmed page, type block, fore-edge and top margins, chapter-title size.
%% The fore-edge margin is (2/3) x (page width - binding - text width); text widths give 70-77
%% characters per line. Type: 10 pt on 13.2 pt leading; Dover 9.5 pt (all fonts, maths included,
%% scaled to 95 %) on 12 pt; TU Delft 11 pt on 15 pt, as its wider lines would otherwise have over 80
%% characters. The chapter-title size follows the page, so "Acknowledgements" still fits on a line.
\newlength{\thesis@pagewidth}   \newlength{\thesis@pageheight}  % trimmed (final) book page
\newlength{\thesis@textwidth}   \newlength{\thesis@textheight}  % type block (where you write)
\newlength{\thesis@foremargin}  \newlength{\thesis@topmargin}   % outer and top margins
\newcommand*{\thesis@size}[7]{%
    \setlength{\thesis@pagewidth}{#1}\setlength{\thesis@pageheight}{#2}%
    \setlength{\thesis@textwidth}{#3}\setlength{\thesis@textheight}{#4}%
    \setlength{\thesis@foremargin}{#5}\setlength{\thesis@topmargin}{#6}%
    \def\chaptertitlesize{#7}}
\def\thesis@ptsize{10pt}
\def\thesis@fontscale{1}
\def\thesisspacing{1.1} % line spacing of the main text (\begin{Spacing} in main.tex)
\@namedef{thesis@size@dover}  {\thesis@size{137mm}{213mm}{92mm} {168mm}{25.3mm}{20mm}  {28pt}\def\thesis@fontscale{0.95}\def\thesisspacing{1}}
\@namedef{thesis@size@a5}     {\thesis@size{148mm}{210mm}{100mm}{165mm}{27.3mm}{20mm}  {30pt}}
\@namedef{thesis@size@royal}  {\thesis@size{156mm}{234mm}{105mm}{180mm}{29.3mm}{25mm}  {33pt}}
\@namedef{thesis@size@tudelft}{\thesis@size{170mm}{240mm}{113mm}{192mm}{33.4mm}{23.9mm}{36pt}\def\thesis@ptsize{11pt}}
\@nameuse{thesis@size@\thesis@pagesize}
\edef\thesis@tmp{\noexpand\LoadClass[\thesis@ptsize]{memoir}}\thesis@tmp

%% Paper: bleed   = the book page plus 2 mm bleed on every side (print-preparation);
%%        trimmed = the book page alone, at its final size (digital, print-showcase);
%%        sheet   = the book page centred on an A4 or US Letter sheet (print-report).
\newlength{\thesis@bleed}       \setlength{\thesis@bleed}{2mm}  % TU Delft uses 2mm bleed
\def\thesis@tmp{bleed}\ifx\thesis@paper\thesis@tmp
    \setstocksize{\dimexpr\thesis@pageheight+2\thesis@bleed\relax}{\dimexpr\thesis@pagewidth+2\thesis@bleed\relax}
    \settrimmedsize{\thesis@pageheight}{\thesis@pagewidth}{*}
    \settrims{\thesis@bleed}{\thesis@bleed}             %% Bleed: how far from {top}{right} the page sits on the stock
\else\def\thesis@tmp{trimmed}\ifx\thesis@paper\thesis@tmp
    \setstocksize{\thesis@pageheight}{\thesis@pagewidth} %% the trimmed page itself, nothing around it
    \settrimmedsize{\thesis@pageheight}{\thesis@pagewidth}{*}
    \settrims{0pt}{0pt}
\else
    \if@letter \setstocksize{11in}{8.5in}\else \setstocksize{297mm}{210mm}\fi %% A4 or US Letter
    \settrimmedsize{\thesis@pageheight}{\thesis@pagewidth}{*}
    \settrims{\dimexpr(\stockheight-\thesis@pageheight)/2\relax}{\dimexpr(\stockwidth-\thesis@pagewidth)/2\relax} %% centred on the sheet
\fi\fi
\settypeblocksize{\thesis@textheight}{\thesis@textwidth}{*}
\setbinding{7.0mm}                      %% allowance for the binding (glue and the curve into the spine); the TU Delft
                                        %% template uses 3 mm. Increase for very thick books (500+ pages).
\setlrmargins{*}{\thesis@foremargin}{*} %% fore-edge margin; the spine margin follows (text width and binding).
\setulmargins{\thesis@topmargin}{*}{*}  %% top margin; bottom margin automatically handled.
\setheadfoot{\onelineskip}{2\onelineskip}
\setheaderspaces{*}{2\onelineskip}{*}
\setmarginnotes{2.5mm}{\dimexpr\thesis@foremargin-4.5mm\relax}{\onelineskip} %% margin (todo) notes fill the outer margin
\checkandfixthelayout
%% No widows or orphans: never leave a single line of a paragraph alone at the top or bottom of a
%% page. Facing pages still end on the same line: when a page has to break early, the space around
%% headings, displays and floats stretches a little instead (pages are never allowed to run long).
\clubpenalty=10000          % first line of a paragraph alone at the bottom of a page
\widowpenalty=10000         % last line of a paragraph alone at the top of a page
\displaywidowpenalty=10000  % last line before a displayed equation alone at the top of a page
\brokenpenalty=5000         % avoid a page break right after a hyphenated line
\vbadness=10000             % that stretching is intended: don't report it as an underfull page
%% On narrow pages, allow a little extra word spacing in a line rather than letting it stick out
%% into the margin (e.g. a long file name or URL that cannot be hyphenated).
\setlength{\emergencystretch}{1.5em}
%% Overfull lines under 1 pt (0.35 mm, invisible) are not reported, e.g. a figure made at exactly the
%% text width that comes out a fraction of a point wider after rounding.
\hfuzz=1pt

%% Optional fields in _thesisinfo.tex: \IfThesisEmpty{\thesisfunding}{if empty}{if filled in}.
%% (\ifx against \empty fails for fields made with \newcommand, which are \long.)
\newcommand{\IfThesisEmpty}[1]{\if\relax\detokenize\expandafter{#1}\relax
    \expandafter\@firstoftwo\else\expandafter\@secondoftwo\fi}

\if@showframe
    \RequirePackage{showframe}
\fi

%%% THESIS INFORMATION AND ARCHIVAL PDF
%% _thesisinfo.tex (title, author, committee, ...) is read here, so that the PDF/A setup (pdfx) can
%% take its metadata from it; pdfx has to come before any colour package, as it sets up xcolor itself.
\IfFileExists{_thesisinfo.tex}{\input{_thesisinfo}}{\ClassWarningNoLine{personal}{_thesisinfo.tex not found}}
\input{_options/pdfa}

\if@draft
    \RequirePackage[firstpageonly=false]{draftwatermark}
    \DraftwatermarkOptions{text={DRAFT \textendash\ \today}, fontsize=8pt, angle=0, pos={0.5\paperwidth, 4mm}, color=black!60}
\fi

%%% COLOR-RELATED
\RequirePackage{xcolor}     % https://ctan.org/pkg/xcolor
\input{_options/formatColor}

%%% THUMB TABS (TikZ)
\RequirePackage{tikz}
\input{_options/thumb}

\input{_options/formatText}
\input{_options/formatPagestyles}

%% Language: British or American English, with Dutch for the Samenvatting.
\RequirePackage[dutch, main=\thesis@language]{babel}
\RequirePackage[style=\thesis@language]{csquotes}

\RequirePackage{microtype}

%%% MATHS: mathtools (loads amsmath); the maths font is set in fontMath.tex
\RequirePackage{mathtools}

%%% MATHS FONT CHOICE: MathTime Professional 2 if its OpenType file is in the Fonts folder
%% (Fonts/MTPro2MathFull.otf, else Fonts/MTPro2MathLite.otf; see Fonts/README.md), otherwise newtx.
%% \ifthesismathtime ... \else ... \fi lets other files follow the choice.
\newif\ifthesismathtime
\def\thesismathtimeedition{}
\IfFileExists{Fonts/MTPro2MathFull.otf}{\thesismathtimetrue\def\thesismathtimeedition{Full}}{%
    \IfFileExists{Fonts/MTPro2MathLite.otf}{\thesismathtimetrue\def\thesismathtimeedition{Lite}}{}}

%%% TEXT FONTS
%% Compile with LuaLaTeX (XeLaTeX also works); fonts are loaded through fontspec.
\input{_options/fontText}

%%% MATH FONT
\input{_options/fontMath}
%% LuaLaTeX: give the Type 1 maths fonts a Unicode map, so maths can be copied and searched
%% (and PDF/A "u" levels are possible). XeLaTeX does this by itself.
\ifdefined\directlua
    \pdfvariable gentounicode = 1
    \protected\def\pdfglyphtounicode{\pdfextension glyphtounicode}
    \input{glyphtounicode}
\fi

%%% CAPTIONS (figures, tables and equations are numbered per chapter by memoir: 2.1, 2.2, ...)
\RequirePackage[tableposition=top]{caption}
\captionsetup*{font={small}, labelfont={sc, bf}, labelsep=quad}
\renewcommand{\arraystretch}{1.2}

%% Bibliography: numbered in order of citation, compressed ([2-4]), \citet/\citep available (natbib=true).
\RequirePackage[
    backend     = biber,
    natbib      = true,
    style       = numeric-comp,  % [2-4] instead of [2, 3, 4]
    sorting     = none,          % numbered in order of first citation
    maxbibnames = 3,             % more than three authors: first three, then "et al."
    minbibnames = 3,
    doi         = true,          % DOIs shown and clickable
    isbn        = false,
    eprint      = false,
]{biblatex}
\addbibresource{references.bib}
\setlength\bibitemsep{0.25\baselineskip} % space between references
%% Set ragged right: references are full of long names, journal titles and DOIs, which in justified
%% text leave wide gaps.
\RequirePackage{ragged2e}
\renewcommand*{\bibfont}{\RaggedRight}

%% Line breaks in URLs and DOIs (typewriter), in the text and the references alike. Never a hyphen;
%% preferably where the Chicago Manual of Style puts them, so a character at the end of a line is
%% never mistaken for punctuation and the next line visibly continues the address:
%%   after a colon or a double slash;  before a single slash, full stop, comma, hyphen, underscore,
%%   tilde, number sign or percent sign;  before or after = and &.
%% Only if none of those fits does a URL break between other characters (letters, digits), so it never
%% sticks out into the margin.
%% (Penalties as registers, so a digit that follows in the URL is not read as part of the number.)
\chardef\thesis@urlgood=50   % penalty at a Chicago break point
\chardef\thesis@urlother=200 % penalty between other characters
\newif\ifthesis@urlslash
\newcommand*{\thesis@urlsetup}{%
    \Urlmuskip=0mu\relax
    \def\UrlBreaks{}\def\UrlBigBreaks{}%
    \def\UrlSpecials{%
        \do\ {\Url@space}\do\^^M{\Url@space}%
        \do\%{\thesis@urlslashfalse\penalty\thesis@urlgood\Url@percent}%
        \do\:{\thesis@urlslashfalse\mathchar`\:\penalty\thesis@urlgood}%
        \do\/{\ifthesis@urlslash \mathchar`\/\penalty\thesis@urlgood\thesis@urlslashfalse
              \else \penalty\thesis@urlgood\mathchar`\/\thesis@urlslashtrue \fi}%
        \do\.{\thesis@urlbefore\.}\do\,{\thesis@urlbefore\,}\do\-{\thesis@urlbefore\-}%
        \do\_{\thesis@urlbefore\_}\do\~{\thesis@urlbefore\~}\do\#{\thesis@urlbefore\#}%
        \do\={\thesis@urlbefore\=\penalty\thesis@urlgood}\do\&{\thesis@urlbefore\&\penalty\thesis@urlgood}%
        \thesis@urlotherchars}}
\newcommand*{\thesis@urlbefore}[1]{\thesis@urlslashfalse\penalty\thesis@urlgood\mathchar`#1}
\newcommand*{\thesis@urlotherchars}{%
    \def\thesis@do##1{\do##1{\thesis@urlslashfalse\mathchar`##1\penalty\thesis@urlother}}%
    \thesis@do a\thesis@do b\thesis@do c\thesis@do d\thesis@do e\thesis@do f\thesis@do g\thesis@do h%
    \thesis@do i\thesis@do j\thesis@do k\thesis@do l\thesis@do m\thesis@do n\thesis@do o\thesis@do p%
    \thesis@do q\thesis@do r\thesis@do s\thesis@do t\thesis@do u\thesis@do v\thesis@do w\thesis@do x%
    \thesis@do y\thesis@do z\thesis@do A\thesis@do B\thesis@do C\thesis@do D\thesis@do E\thesis@do F%
    \thesis@do G\thesis@do H\thesis@do I\thesis@do J\thesis@do K\thesis@do L\thesis@do M\thesis@do N%
    \thesis@do O\thesis@do P\thesis@do Q\thesis@do R\thesis@do S\thesis@do T\thesis@do U\thesis@do V%
    \thesis@do W\thesis@do X\thesis@do Y\thesis@do Z\thesis@do 0\thesis@do 1\thesis@do 2\thesis@do 3%
    \thesis@do 4\thesis@do 5\thesis@do 6\thesis@do 7\thesis@do 8\thesis@do 9\thesis@do )\thesis@do ]%
    \thesis@do ?\thesis@do ;\thesis@do !\thesis@do @\thesis@do +} % not ( or [: amsmath measures ( for its struts
\thesis@urlsetup
\renewcommand*{\biburlsetup}{\thesis@urlsetup} % biblatex would otherwise apply its own rules in the references
%% A URL adds nothing when there is a DOI: hide it (and its access date).
\AtEveryBibitem{\iffieldundef{doi}{}{\clearfield{url}\clearfield{urlyear}\clearfield{urlmonth}\clearfield{urlday}}}
\if@backref
    \ExecuteBibliographyOptions{backref=true, backrefstyle=three}
    \DefineBibliographyStrings{british}{backrefpage={cited on page}, backrefpages={cited on pages}}
    \DefineBibliographyStrings{american}{backrefpage={cited on page}, backrefpages={cited on pages}}
\fi
\ifchapterbib
    %% Every \chapter starts a new reference section; its list is printed at the end of the chapter
    %% file (\include). Chapters without citations print nothing (and don't warn about it).
    \ExecuteBibliographyOptions{refsection=chapter}
    \AddToHook{include/end}{\begingroup\let\blx@warn@bibempty\relax
        \printbibliography[heading=subbibintoc, title={References}]\endgroup}
\fi

