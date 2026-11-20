\ProvidesClass{personal}[2020/05/24, v1.0]

\RequirePackage{ifthen}

\newif\if@american
\newif\if@british
\newif\if@print
\newif\if@thumb
\newif\if@showframe
%% Language: british (default) or american. Choosing one switches the other off.
\DeclareOption{american}{\@americantrue\@britishfalse}
\DeclareOption{british}{\@britishtrue\@americanfalse}
\DeclareOption{print}{\@printtrue}
\DeclareOption{thumb}{\if@print \@thumbtrue \fi}
\DeclareOption{showtrims}{\PassOptionsToClass{\CurrentOption}{memoir}} %% in report mode this marks the book page on the A4 sheet 
\DeclareOption{showframe}{\@showframetrue}
%% draft: fast compiles while writing. Images become labelled boxes, overfull lines are marked
%% with a black bar in the margin, and every page says DRAFT so it is never mistaken for the final version.
\newif\if@draft
\DeclareOption{draft}{\@drafttrue \PassOptionsToPackage{draft}{graphicx} \PassOptionsToClass{draft}{memoir}}

%% Book page size. Choose one; a5 is the default.
%%   dover   : 137 x 213 mm  (5 3/8 x 8 3/8 in, the classic Dover paperback)
%%   a5      : 148 x 210 mm  (handbook / paperback size)
%%   royal   : 156 x 234 mm  (typical academic book)
%%   tudelft : 170 x 240 mm  (TU Delft dissertation template, most common thesis size in NL)
\newcommand*{\thesis@pagesize}{a5}
\DeclareOption{dover}{\renewcommand*{\thesis@pagesize}{dover}}
\DeclareOption{a5}{\renewcommand*{\thesis@pagesize}{a5}}
\DeclareOption{royal}{\renewcommand*{\thesis@pagesize}{royal}}
\DeclareOption{tudelft}{\renewcommand*{\thesis@pagesize}{tudelft}}

%% Bibliography options
%%   backreferences: each reference lists the pages it is cited on ("Cited on pages 12, 45.")
%%   chapterbib : every chapter ends with its own reference list (for a thesis built from papers),
%%                instead of one list at the end of the book
\newif\if@backref
\DeclareOption{backreferences}{\@backreftrue} % (not "backref": that name would also switch on hyperref's own back-references)
\newif\ifchapterbib
\DeclareOption{chapterbib}{\chapterbibtrue}

%% final: the version for the printer and the repository; hides all \todo notes.
\newif\if@final
\DeclareOption{final}{\@finaltrue \PassOptionsToPackage{disable}{todonotes}}

\ExecuteOptions{british} %% default language: British English
\ProcessOptions\relax

%% This template is set up for LuaLaTeX (better justification, PDF/A-2u maths). XeLaTeX still works.
\ifdefined\directlua\else
    \ClassWarningNoLine{personal}{This template is meant to be compiled with LuaLaTeX.\MessageBreak
        In Overleaf: Menu > Settings > Compiler > LuaLaTeX}
\fi

%% Public switch so files outside the class can check for print mode (\ifprintversion ... \else ... \fi)
\newif\ifprintversion
\if@print \printversiontrue \fi

% \RequirePackage[l2tabu, orthodox]{nag} % https://ctan.org/pkg/nag %% warns about outdated LaTeX commands; uncomment to check your writing

%% Page layout. The book page size is set by the a5 / royal / tudelft option (default a5);
%% only the paper it sits on differs between modes:
%%   print  : the book page plus 2mm bleed on every side, for the printer.
%%   report : the book page centred on an A4 sheet, for reading on screen or printing at home.
\LoadClass[10pt]{memoir}

\newlength{\thesis@pagewidth}   \newlength{\thesis@pageheight}  %% trimmed (final) book page
\newlength{\thesis@textwidth}   \newlength{\thesis@textheight}  %% type block (where you write)
\newlength{\thesis@foremargin}  \newlength{\thesis@topmargin}   %% outer and top margins
\newlength{\thesis@bleed}       \setlength{\thesis@bleed}{2mm}  %% TU Delft uses 2mm bleed

\ifthenelse{\equal{\thesis@pagesize}{tudelft}}{%
    \setlength{\thesis@pagewidth}{170mm}   \setlength{\thesis@pageheight}{240mm}
    \setlength{\thesis@textwidth}{113mm}   \setlength{\thesis@textheight}{192mm}
    \setlength{\thesis@foremargin}{33.4mm} \setlength{\thesis@topmargin}{23.9mm}
}{\ifthenelse{\equal{\thesis@pagesize}{royal}}{%
    \setlength{\thesis@pagewidth}{156mm}   \setlength{\thesis@pageheight}{234mm}
    \setlength{\thesis@textwidth}{105mm}   \setlength{\thesis@textheight}{180mm}
    \setlength{\thesis@foremargin}{29.3mm} \setlength{\thesis@topmargin}{25mm}
}{\ifthenelse{\equal{\thesis@pagesize}{dover}}{%
    \setlength{\thesis@pagewidth}{137mm}   \setlength{\thesis@pageheight}{213mm}
    \setlength{\thesis@textwidth}{92mm}    \setlength{\thesis@textheight}{168mm}
    \setlength{\thesis@foremargin}{25.3mm} \setlength{\thesis@topmargin}{20mm}
}{% a5 (default)
    \setlength{\thesis@pagewidth}{148mm}   \setlength{\thesis@pageheight}{210mm}
    \setlength{\thesis@textwidth}{100mm}   \setlength{\thesis@textheight}{165mm}
    \setlength{\thesis@foremargin}{27.3mm} \setlength{\thesis@topmargin}{20mm}
}}}
%% Chapter title size scales with the page, so long titles such as "Acknowledgements" still fit on one line.
\newcommand*{\chaptertitlesize}{30pt}
\ifthenelse{\equal{\thesis@pagesize}{tudelft}}{\renewcommand*{\chaptertitlesize}{36pt}}{}
\ifthenelse{\equal{\thesis@pagesize}{royal}}{\renewcommand*{\chaptertitlesize}{33pt}}{}
\ifthenelse{\equal{\thesis@pagesize}{dover}}{\renewcommand*{\chaptertitlesize}{28pt}}{}

%% Fore-edge margins follow foreedge = (2/3)*(page width - binding - text width);
%% text widths give roughly 53-60 characters per line at 10pt in every size.

\if@print
    \setstocksize{\dimexpr\thesis@pageheight+2\thesis@bleed\relax}{\dimexpr\thesis@pagewidth+2\thesis@bleed\relax}
    \settrimmedsize{\thesis@pageheight}{\thesis@pagewidth}{*}
    \settrims{\thesis@bleed}{\thesis@bleed}             %% Bleed: how far from {top}{right} the page sits on the stock
\else
    \setstocksize{297mm}{210mm}                         %% A4
    \settrimmedsize{\thesis@pageheight}{\thesis@pagewidth}{*}
    \settrims{\dimexpr(297mm-\thesis@pageheight)/2\relax}{\dimexpr(210mm-\thesis@pagewidth)/2\relax} %% centre the book page on A4
\fi
\settypeblocksize{\thesis@textheight}{\thesis@textwidth}{*}
\setbinding{7.0mm}           %% Binding margin is handled here
                             %% 3.00mm binding from TUD PhD template
                             %% 7.00mm binding might be better? based on what I have seen.
\setlrmargins{*}{\thesis@foremargin}{*} %% fore-edge margin; spine margin automatically handled.
                             %% Normally, your spine margin should be smaller, but the binding process is hot garbage based on what I have seen of previous theses.
\setulmargins{\thesis@topmargin}{*}{*}  %% top margin; bottom margin automatically handled.
\setheadfoot{\onelineskip}{2\onelineskip}
\setheaderspaces{*}{2\onelineskip}{*}
\setmarginnotes{17pt}{51pt}{\onelineskip}
\checkandfixthelayout
\sloppybottom % see memoir manual
%% No widows or orphans: never leave a single line of a paragraph alone at the top or bottom of a
%% page. \sloppybottom lets a page run one line long instead, so pages stay full.
\clubpenalty=10000          % first line of a paragraph alone at the bottom of a page
\widowpenalty=10000         % last line of a paragraph alone at the top of a page
\displaywidowpenalty=10000  % last line before a displayed equation alone at the top of a page
\brokenpenalty=5000         % avoid a page break right after a hyphenated line
%% On narrow pages, allow a little extra word spacing in a line rather than letting it stick out
%% into the margin (e.g. a long file name or URL that cannot be hyphenated).
\setlength{\emergencystretch}{1.5em}

\if@showframe
    \RequirePackage{showframe}
\fi

\if@draft
    \RequirePackage[firstpageonly=false]{draftwatermark}
    \DraftwatermarkOptions{text={DRAFT \textendash\ \today}, fontsize=8pt, angle=0, pos={0.5\paperwidth, 4mm}, color=black!60}
\fi

%%% COLOR-RELATED
\RequirePackage{xcolor}     % https://ctan.org/pkg/xcolor %% Provides easy driver-independent access to several kinds of color tints, shades, tones, and mixes of arbitrary colors.
\input{_options/formatColor}

%%% TIKZ-RELATED
\RequirePackage{tikz}
\input{_fixes/recto_verso_tikz_fix}
\input{_options/thumb}

\input{_options/formatText}

\if@american
    \RequirePackage[dutch,american]{babel}               % https://ctan.org/pkg/babel %% manages culturally-determined typographical (and other) rules for a wide range of languages 
    \RequirePackage[style=american]{csquotes}       % https://ctan.org/pkg/csquotes %% provides advanced facilities for inline and display quotations, check their documentation to find out how to quote properly        
\fi
\if@british
    \RequirePackage[dutch,british]{babel} % dutch for the Samenvatting; the last language is the main one
    \RequirePackage[style=british]{csquotes} 
\fi

\RequirePackage{microtype}

%%% MATH PACKAGES INTERLUDE
\RequirePackage{amsmath}   %% https://ctan.org/pkg/amsmath %% essential math package (integrals such as \oiint come from newtxmath)
\RequirePackage{mathtools}

%%% TEXT FONTS
%% Compile with XeLaTeX (or LuaLaTeX); fonts are loaded through fontspec.
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

%%% NOMENCLATURE: glossaries-extra, loaded after hyperref in _options/packages.tex

\RequirePackage[tableposition=top, figurename=Figure]{caption}
\renewcommand{\thefigure}{\thechapter.\arabic{figure}}
\renewcommand{\thetable}{\thechapter.\arabic{table}}
\renewcommand{\theequation}{\thechapter.\arabic{equation}}
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
%% A URL adds nothing when there is a DOI: hide it (and its access date).
\setlength\bibitemsep{0.5\baselineskip} % space between references
\AtEveryBibitem{\iffieldundef{doi}{}{\clearfield{url}\clearfield{urlyear}\clearfield{urlmonth}\clearfield{urlday}}}
\if@backref
    \ExecuteBibliographyOptions{backref=true, backrefstyle=three}
    \DefineBibliographyStrings{english}{backrefpage={cited on page}, backrefpages={cited on pages}}
    \DefineBibliographyStrings{british}{backrefpage={cited on page}, backrefpages={cited on pages}}
    \DefineBibliographyStrings{american}{backrefpage={cited on page}, backrefpages={cited on pages}}
\fi
\ifchapterbib
    %% Every \chapter starts a new reference section; its list is printed at the end of the chapter
    %% file (\include). Chapters without citations print nothing.
    \ExecuteBibliographyOptions{refsection=chapter}
    \AddToHook{include/end}{\printbibliography[heading=subbibintoc, title={References}]}
\fi

