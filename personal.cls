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

%% Book page size. Choose one; a5 is the default.
%%   a5      : 148 x 210 mm  (handbook / paperback size)
%%   royal   : 156 x 234 mm  (typical academic book)
%%   tudelft : 170 x 240 mm  (TU Delft dissertation template, most common thesis size in NL)
\newcommand*{\thesis@pagesize}{a5}
\DeclareOption{a5}{\renewcommand*{\thesis@pagesize}{a5}}
\DeclareOption{royal}{\renewcommand*{\thesis@pagesize}{royal}}
\DeclareOption{tudelft}{\renewcommand*{\thesis@pagesize}{tudelft}}

\ExecuteOptions{british} %% default language: British English
\ProcessOptions\relax

%% Public switch so files outside the class can check for print mode (\ifprintversion ... \else ... \fi)
\newif\ifprintversion
\if@print \printversiontrue \fi

\RequirePackage[l2tabu, orthodox]{nag} % https://ctan.org/pkg/nag %% In case I commit a cardinal sin of loading depreciated modules, or some dumb stuff that can be picked up (i.e use \centering instead of \begin{center}[...]\end{center})

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
}{% a5 (default)
    \setlength{\thesis@pagewidth}{148mm}   \setlength{\thesis@pageheight}{210mm}
    \setlength{\thesis@textwidth}{100mm}   \setlength{\thesis@textheight}{165mm}
    \setlength{\thesis@foremargin}{27.3mm} \setlength{\thesis@topmargin}{20mm}
}}
%% Chapter title size scales with the page, so long titles such as "Acknowledgements" still fit on one line.
\newcommand*{\chaptertitlesize}{30pt}
\ifthenelse{\equal{\thesis@pagesize}{tudelft}}{\renewcommand*{\chaptertitlesize}{36pt}}{}
\ifthenelse{\equal{\thesis@pagesize}{royal}}{\renewcommand*{\chaptertitlesize}{33pt}}{}

%% Fore-edge margins follow foreedge = (2/3)*(page width - binding - text width);
%% text widths give roughly 57-60 characters per line at 10pt in every size.

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

\if@showframe
    \RequirePackage{showframe}
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
    \RequirePackage[american]{babel}               % https://ctan.org/pkg/babel %% manages culturally-determined typographical (and other) rules for a wide range of languages 
    \RequirePackage[style=american]{csquotes}       % https://ctan.org/pkg/csquotes %% provides advanced facilities for inline and display quotations, check their documentation to find out how to quote properly        
    \RequirePackage[USenglish,style=iso]{datetime2} % https://www.ctan.org/pkg/datetime2 %% This package provides commands for formatting dates, times and time zones and redefines \today to use the same formatting style. By default uses ISO formatting described in ISO 8601 and DIN 5008.
\fi
\if@british
    \RequirePackage[british]{babel}
    \RequirePackage[style=british]{csquotes} 
    \RequirePackage[UKenglish,style=iso]{datetime2}
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

%%% NOMENCLATURE
\RequirePackage[intoc,english]{nomencl} % https://www.ctan.org/pkg/nomencl %% use this to make nomenclature!
% incorporate https://tex.stackexchange.com/questions/112884/how-to-achieve-nomenclature-entries-like-symbol-description-dimension-and-uni
\input{_options/formatNomenclature}

\RequirePackage[tableposition=top, figurename=Figure]{caption}
\renewcommand{\thefigure}{\thechapter.\arabic{figure}}
\renewcommand{\thetable}{\thechapter.\arabic{table}}
\renewcommand{\theequation}{\thechapter.\arabic{equation}}
\captionsetup*{font={small}, labelfont={sc, bf}, labelsep=quad}
\renewcommand{\arraystretch}{1.2}

\RequirePackage[backend=biber,natbib=true,style=numeric,sorting=none]{biblatex} % natbib has some cool commands like \citet, \citep which i really like.
\addbibresource{references.bib}

