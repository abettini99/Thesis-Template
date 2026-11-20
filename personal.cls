\ProvidesClass{personal}[2020/05/24, v1.0]

\RequirePackage{ifthen}

\newif\if@american
\newif\if@british
\newif\if@print
\newif\if@thumb
\newif\if@showframe
\DeclareOption{american}{\@americantrue}
\DeclareOption{british}{\@britishtrue}
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

\ExecuteOptions{}
\ProcessOptions\relax

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

% \setlength\footparindent{\parindent}
% \setlength{\footmarkwidth}{0em}
% \setlength{\footmarksep}{0em}
% \footmarkstyle{\makebox[\footparindent][l]{\textsuperscript{#1}}}

% % Online fix for all fontenc-inputenc interactions and use of inputenc, to be honest i have no clue what these do.
% \RequirePackage{iftex}
% \ifPDFTeX
% %   \RequirePackage[light]{kpfonts} %% Reenable newtx/newpx if kpfonts is disabled, amsmath included? but going to keep it in anyways
%    \RequirePackage[T1]{fontenc}
%    \RequirePackage[utf8]{inputenc} 
% %   \RequirePackage{lmodern}
% \else
%    \ifXeTeX
%      \RequirePackage{fontspec}
%      %% Testing out stuff here
%     %  \setmainfont{TeX Gyre Pagella}
%     %  \RequirePackage[euler-digits,euler-hat-accent]{eulervm}
%    \else 
%      \RequirePackage{luatextra}
%    \fi
%    \defaultfontfeatures{Ligatures=TeX}
% \fi

% \RequirePackage{enumitem}
% \setlist{labelindent=\parindent,leftmargin=*,nosep}
% \setlist[enumerate]{label={\arabic*)}}

% \RequirePackage{titletoc}

% Control over footnotes
% \RequirePackage[flushmargin,hang,bottom]{footmisc} % bottom makes footnotes always go at the very bottom of the page. %% Removed as memoir has its own options
% \RequirePackage{fancyhdr} % Provides extensive control over footers and headers % https://tex.stackexchange.com/questions/129829/warning-command-makecol-has-changed read the following link to see why the load order is this way instead of the other way.
% \RequirePackage[hyphens]{url}
% \ifxetex
%     \RequirePackage[hyperfootnotes=false,xetex]{hyperref} % double reffing solution comes from: http://ctan.cs.uu.nl/macros/latex/contrib/footmisc/footmisc.pdf
% \else
%     \ifpdf
%         \RequirePackage[hyperfootnotes=false,pdftex]{hyperref}
%     \else
%         \RequirePackage[hyperfootnotes=false,hypertex]{hyperref}
%     \fi
% \fi

% \RequirePackage[blocks]{authblk}
% \renewcommand{\Authfont}{\normalsize\upshape}
% \renewcommand{\Affilfont}{\normalsize\itshape}
% \setlength{\affilsep}{0pt}

% \renewcommand{\maketitle}{%
%   \begingroup
%   \renewcommand\and{\\[\baselineskip]}
%   \centering
%   {\LARGE\bfseries\@title\par}
%   \vskip2\baselineskip
%   \@author\par
%   \endgroup
%   \vskip\baselineskip
%   \setcounter{footnote}{0}
% }

\input{_options/formatText}


% \RequirePackage{lettrine}
% \setlength{\DefaultNindent}{0pt}

% \setlength{\abovedisplayskip}{\baselineskip}
% \setlength{\belowdisplayskip}{\baselineskip}
% \setlength{\abovedisplayshortskip}{\baselineskip}
% \setlength{\belowdisplayshortskip}{\baselineskip}

% \RequirePackage[sort&compress,numbers]{natbib}
% \bibliographystyle{apalike}
% \bibliographystyle{personal}
% \renewcommand{\bibfont}{\small}

% \RequirePackage{minted}     % https://ctan.org/pkg/minted %% Use this for code.
\if@american
    \RequirePackage[american]{babel}               % https://ctan.org/pkg/babel %% manages culturally-determined typographical (and other) rules for a wide range of languages 
    \RequirePackage[style=american]{csquotes}       % https://ctan.org/pkg/csquotes %% provides advanced facilities for inline and display quotations, check their documentation to find out how to quote properly        
    \RequirePackage[USenglish,style=iso]{datetime2} % https://www.ctan.org/pkg/datetime2 %% This package provides commands for formatting dates, times and time zones and redefines \today to use the same formatting style. By default uses ISO formatting described in ISO 8601 and DIN 5008.
\fi
\if@british
    \RequirePackage[UKenglish]{babel}
    \RequirePackage[style=british]{csquotes} 
    \RequirePackage[UKenglish,style=iso]{datetime2}
\fi

%% https://tex.stackexchange.com/questions/59702/suggest-a-nice-font-family-for-my-basic-latex-template-text-and-math        %%%%%% font suggestions!
\RequirePackage{blindtext}
\RequirePackage{microtype}

%%% MATH PACKAGES INTERLUDE
\RequirePackage{amsmath} % esint removed: newtxmath provides its own Times-style integrals (\oiint etc.)    
%% https://ctan.org/pkg/amsmath?lang=en %% essential math package, check their userguide for content 
%% https://www.ctan.org/pkg/esint %% The esint package permits access to alternate integral symbols when you are using the Computer Modern fonts.
\RequirePackage{mathtools}
% \RequirePackage{amsfonts}   %% not needed: newtxmath provides these symbols. https://ctan.org/pkg/amsfonts %% An extended set of fonts for use in mathematics

%%% TEXT FONTS
%% We use purely XeLaTeX now
\input{_options/fontText}

%%% MATH FONT
\input{_options/fontMath}

%%% NOMENCLATURE
\RequirePackage[intoc,english]{nomencl} % https://www.ctan.org/pkg/nomencl %% use this to make nomenclature!
% incorporate https://tex.stackexchange.com/questions/112884/how-to-achieve-nomenclature-entries-like-symbol-description-dimension-and-uni
\input{_options/formatNomenclature}

\RequirePackage[tableposition=top, figurename=Figure]{caption}
% \renewcommand{\thefigure}{\getCurrentSectionNumber--\arabic{figure}}
% \renewcommand{\thetable}{\getCurrentSectionNumber--\arabic{table}}
% \renewcommand{\theequation}{\getCurrentSectionNumber--\arabic{equation}}
\renewcommand{\thefigure}{\thechapter.\arabic{figure}}
\renewcommand{\thetable}{\thechapter.\arabic{table}}
\renewcommand{\theequation}{\thechapter.\arabic{equation}}
\captionsetup*{font={small}, labelfont={sc, bf}, labelsep=quad}
\renewcommand{\arraystretch}{1.2}

\RequirePackage[backend=biber,natbib=true,style=numeric,sorting=none]{biblatex} % natbib has some cool commands like \citet, \citep which i really like.
\addbibresource{references.bib}

% TO DO:
% - Make the american, british thing a mandatory option
% - Reorganize this mess