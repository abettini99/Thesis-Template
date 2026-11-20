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
\DeclareOption{showtrims}{\if@print \PassOptionsToClass{\CurrentOption}{memoir} \fi} 
\DeclareOption{showframe}{\@showframetrue}

\ExecuteOptions{}
\ProcessOptions\relax

\RequirePackage[l2tabu, orthodox]{nag} % https://ctan.org/pkg/nag %% In case I commit a cardinal sin of loading depreciated modules, or some dumb stuff that can be picked up (i.e use \centering instead of \begin{center}[...]\end{center})

%% Load this in for book
\if@print
    \LoadClass[10pt]{memoir}[openright]
    \setstocksize{244mm}{174mm}             %% Paper stock size = trimmed size + 2mm bleed on every side (matches TU Delft dissertation template).
    \settrimmedsize{240mm}{170mm}{*}        %% This is the layout/trimmed/paper size for which you work on,
                                            %% 170 x 240 mm: final book size of the TU Delft dissertation template
    \settrims{2mm}{2mm}                     %% Bleed: how far from {top}{right} that layout is placed on the stock (TU Delft uses 2mm)
    \settypeblocksize{192mm}{113mm}{*}      %% This is your workspace - where you write on.
    \setbinding{7.0mm}           %% Binding margin is handled here
                                 %% 3.00mm binding from TUD PhD template
                                 %% 7.00mm binding might be better? based on what I have seen.
                                 
    %% foreedge_margin = (2/3)*(trimmedsize_width - binding_offset - typeblock_width)
    %% topdown_margin  = (1/2)*(trimmedsize_height - typeblock_height)
    \setlrmargins{*}{33.40mm}{*} %% fore-edge margin is handled here (scaled from 35.33mm for the 170mm page)
                                 %% Normally, your spine margin should be smaller, but the binding process is hot garbage based on what I have seen of previous theses.
                                 %% spine margin automatically handled.
                                 %% 35.33mm ~= 1.00in * 1.39
    \setulmargins{23.90mm}{*}{*} %% top margin handled here, bottom margin automatically handled (scaled from 27.00mm for the 240mm page).
                                 %% 27.00mm ~= 1.00in * 1.06
    \setheadfoot{\onelineskip}{2\onelineskip}
    \setheaderspaces{*}{2\onelineskip}{*}
    \setmarginnotes{17pt}{51pt}{\onelineskip}
    \checkandfixthelayout
    \sloppybottom % see memoir manual
%% Load this in for report
\else
    \LoadClass[12pt]{memoir}
    \setstocksize{297mm}{210mm}             %% This is the paper stocksize, which is a4
    \settrimmedsize{291mm}{204mm}{*}        %% This is the layout/trimmed/paper size for which you work on.
    \settrims{2mm}{2mm}                     %% Bleed: how far from {top}{right} that layout is placed on the stock (TU Delft uses 2mm)
    \settypeblocksize{240.2mm}{153.2mm}{*}  %% This is your workspace - where you write on.
    \setbinding{0.0mm}                      %% Binding margin is handled here
    
    %% foreedge_margin = (2/3)*(trimmedsize_width - binding_offset - typeblock_width)
    %% topdown_margin  = (1/2)*(trimmedsize_height - typeblock_height)
    \setlrmargins{*}{25.4mm}{*}  %% fore-edge margin is handled here
                                 %% Normally, your spine margin should be smaller, but the binding process is hot garbage based on what I have seen of previous theses.
                                 %% spine margin automatically handled.
                                 %% 25.40mm = 1.00in * 1.00
    \setulmargins{25.4mm}{*}{*}  %% top margin handled here, bottom margin automatically handled.
                                 %% 25.40mm = 1.00in * 1.00
    \setheadfoot{\onelineskip}{2\onelineskip}
    \setheaderspaces{*}{2\onelineskip}{*}
    \setmarginnotes{17pt}{51pt}{\onelineskip}
    \checkandfixthelayout
\fi

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