\ProvidesClass{personal}[2026/11/22 v3.0 TU Delft dissertation class, based on book]
%% Parts of this class are adapted from the memoir class (Peter Wilson, Lars Madsen and Will Robertson;
%% https://ctan.org/pkg/memoir), distributed under the LaTeX Project Public License 1.3c: the page
%% styles, the epigraphs, the Spacing environment, the crop marks and the type sizes (read from memoir's
%% size files). memoir's code is unchanged in memoir; the adapted copies here carry other names or
%% replace memoir's only inside this class.

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
\newif\ifthesis@showtrims
\DeclareOption{showtrims}{\thesis@showtrimstrue} % crop marks (print-preparation, print-report)
\newif\if@showframe
\DeclareOption{showframe}{\@showframetrue}
%% draft: fast compiles while writing. Images become labelled boxes, overfull lines are marked
%% with a black bar in the margin, and every page says DRAFT so it is never mistaken for the final version.
\newif\if@draft
\DeclareOption{draft}{\@drafttrue \PassOptionsToPackage{draft}{graphicx} \PassOptionsToClass{draft}{book}}
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

%% LuaLaTeX only: the class uses Lua for page balance, line breaks of URLs, maths fonts and the logs.
\IfFormatAtLeastF{2026-06-01}{%
    \ClassError{personal}{This template needs TeX Live 2026 or later}{In Overleaf: Menu > Settings >
        TeX Live version > 2026.}\@@end}
\ifdefined\directlua\else
    \ClassError{personal}{This template needs LuaLaTeX}{In Overleaf: Menu > Settings > Compiler > LuaLaTeX.
        Locally: latexmk main.tex (latexmkrc selects LuaLaTeX).}
    \expandafter\@@end
\fi
%% LaTeX's PDF management and tagging code: \DocumentMetadata{...} on the first line of main.tex.
\IfDocumentMetadataTF{}{%
    \ClassError{personal}{\string\DocumentMetadata\space missing}{Put
        \string\DocumentMetadata{pdfversion=2.0, pdfstandard=a-4f} on the first line, before \string\documentclass.}}

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
\edef\thesis@tmp{\noexpand\LoadClass[\thesis@ptsize,twoside,openright]{book}}\thesis@tmp
\RequirePackage{etoolbox}
%% The type sizes and default spacings of memoir, which the earlier versions of this class were based on
%% (\small and \large are a little smaller than in the book class): its size option file, read as is.
\newlength{\onelineskip} \newlength{\lxvchars} \newlength{\xlvchars} \newif\ifextrafontsizes
\def\thesis@tmp#1pt{#1}\edef\thesis@tmp{\expandafter\thesis@tmp\thesis@ptsize}\input{mem\thesis@tmp.clo}
%% One em of the class's type size, as memoir measured lengths given in em when the class was loaded
\newdimen\thesis@em \thesis@em=\@xpt\p@ \def\thesis@tmpb{11}\ifx\thesis@tmp\thesis@tmpb \thesis@em=\@xipt\p@\fi
\def\thesis@tmpb{12}\ifx\thesis@tmp\thesis@tmpb \thesis@em=\@xiipt\p@\fi

%%% PAGE LAYOUT
%% The sheet (the PDF page), the book page on it and the type block on the book page:
%%   bleed   = the book page plus 2 mm bleed on every side (print-preparation);
%%   trimmed = the book page alone, at its final size (digital, print-showcase);
%%   sheet   = the book page centred on an A4 or US Letter sheet (print-report).
%% \stockwidth x \stockheight is the sheet, \paperwidth x \paperheight the book page, \trimtop and
%% \trimedge its distance from the sheet's top and outer edge.
\providecommand\stockwidth{}\providecommand\stockheight{}% (the kernel's)
\newlength{\trimtop}     \newlength{\trimedge}
\newlength{\spinemargin} \newlength{\foremargin}  \newlength{\uppermargin} \newlength{\lowermargin}
\setlength{\onelineskip}{\baselineskip} % one line of normal text
\newlength{\thesis@bleed}       \setlength{\thesis@bleed}{2mm}  % TU Delft uses 2mm bleed
\setlength{\paperwidth}{\thesis@pagewidth}
\setlength{\paperheight}{\thesis@pageheight}
\def\thesis@tmp{bleed}\ifx\thesis@paper\thesis@tmp
    \setlength{\stockwidth}{\dimexpr\paperwidth+2\thesis@bleed}%
    \setlength{\stockheight}{\dimexpr\paperheight+2\thesis@bleed}%
    \setlength{\trimtop}{\thesis@bleed}\setlength{\trimedge}{\thesis@bleed}%
\else\def\thesis@tmp{sheet}\ifx\thesis@paper\thesis@tmp
    \if@letter \setlength{\stockwidth}{8.5in}\setlength{\stockheight}{11in}%
    \else      \setlength{\stockwidth}{210mm}\setlength{\stockheight}{297mm}\fi
    \setlength{\trimtop}{\dimexpr(\stockheight-\paperheight)/2}%
    \setlength{\trimedge}{\dimexpr(\stockwidth-\paperwidth)/2}%
\else
    \setlength{\stockwidth}{\paperwidth}\setlength{\stockheight}{\paperheight}%
    \setlength{\trimtop}{0pt}\setlength{\trimedge}{0pt}%
\fi\fi
%% The type block: the given width, and the height rounded down to whole lines. The spine margin is
%% what the fore-edge margin and the text leave (it includes 7 mm for the binding: the glue and the
%% curve into the spine; increase the fore-edge margin's share for very thick books, 500+ pages).
\setlength{\textwidth}{\thesis@textwidth}
\setlength{\foremargin}{\thesis@foremargin}
\setlength{\spinemargin}{\dimexpr\paperwidth-\textwidth-\foremargin}
\@tempdima=\thesis@textheight \divide\@tempdima\baselineskip \@tempcnta=\@tempdima
\setlength{\textheight}{\dimexpr\@tempcnta\baselineskip+\topskip}
\setlength{\uppermargin}{\thesis@topmargin}
\setlength{\lowermargin}{\dimexpr\paperheight-\textheight-\uppermargin}
\setlength{\headheight}{\onelineskip}   \setlength{\headsep}{2\onelineskip}
\setlength{\footskip}{2\onelineskip}
\setlength{\marginparsep}{2.5mm}        %% margin (todo) notes fill the outer margin
\setlength{\marginparwidth}{\dimexpr\foremargin-4.5mm}
\setlength{\marginparpush}{\onelineskip}
%% TeX's own margins (from 1 inch), in whole points, as memoir computed them for the earlier versions
\def\thesis@topoint#1{\divide#1\p@\multiply#1\p@}
\setlength{\topmargin}{\dimexpr\trimtop+\uppermargin-\headsep-\headheight-1in}
\setlength{\oddsidemargin}{\dimexpr\stockwidth-\trimedge-\paperwidth+\spinemargin-1in}
\setlength{\evensidemargin}{\dimexpr\trimedge+\foremargin-1in}
\thesis@topoint\textwidth \thesis@topoint\oddsidemargin \thesis@topoint\evensidemargin
\setlength{\pagewidth}{\stockwidth} \setlength{\pageheight}{\stockheight}
%% Crop marks (showtrims, print-preparation and print-report): a cross at each corner of the book page
%% and a short mark at the middle of each edge, drawn on every sheet.
\ifthesis@showtrims
    \newcommand*{\thesis@trimcross}{\begin{picture}(0,0)\unitlength 1cm\thinlines
        \put(-2,0){\line(1,0){4}}\put(0,-2){\line(0,1){4}}\end{picture}}
    \newcommand*{\thesis@trimmid}[4]{\begin{picture}(0,0)\unitlength 1mm\thinlines\put(#1,#2){\line(#3,#4){10}}\end{picture}}
    \AddToHook{shipout/background}{\put(0,0){\vbox to \z@{%
        \vskip\trimtop
        \hb@xt@\z@{%
            \ifodd\c@page \hskip\dimexpr\stockwidth-\trimedge-\paperwidth\relax \else \hskip\trimedge \fi
            \vbox to \paperheight{\let\protect\relax
                \hb@xt@\paperwidth{\thesis@trimcross\hfil\thesis@trimmid{0}{2}{0}{1}\hfil\thesis@trimcross}%
                \vfil
                \hb@xt@\paperwidth{\thesis@trimmid{-2}{0}{-1}{0}\hfil\thesis@trimmid{2}{0}{1}{0}}%
                \vfil
                \hb@xt@\paperwidth{\thesis@trimcross\hfil\thesis@trimmid{0}{-12}{0}{1}\hfil\thesis@trimcross}}%
            \hss}%
        \vss}}}
\fi

%% A chapter starts on a right-hand page; the empty left-hand page before it has no running head.
\def\cleardoublepage{\clearpage\if@twoside \ifodd\c@page\else
    \hbox{}\thispagestyle{cleared}\newpage\if@twocolumn\hbox{}\newpage\fi\fi\fi}

%% Line spacing of a passage: \begin{Spacing}{1.1} ... \end{Spacing} (used for the main text in main.tex)
\newenvironment{Spacing}[1]{\par\begingroup\def\baselinestretch{#1}\@currsize}
    {\par\vskip\parskip\vskip\baselineskip\endgroup\vskip-\parskip\vskip-\baselineskip}

%% Floats are set at single spacing, whatever the text around them; \setfloatadjustment{table}{\small}
%% adds settings of its own to every float of a type.
\newcommand{\setfloatadjustment}[2]{\@namedef{#1adjustment}{#2}}
\AddToHook{cmd/@floatboxreset/after}{\def\baselinestretch{1}\normalsize\@nameuse{\@captype adjustment}}

%% Description lists as memoir set them: the label at the left margin in bold, a label separation
%% before and after it. (LaTeX's tagging code sets lists with its own templates, not \descriptionlabel.)
\@for\thesis@tmp:=1,2,3,4,5,6\do{\EditInstance{list}{description-\thesis@tmp}
    {label-width = \z@, item-indent = -\leftmargin}}
\EditInstance{item}{description}{label-format = \hspace\labelsep\normalfont\bfseries #1}

%% After a displayed equation that ends a paragraph or an environment (a proof ending with \qedhere,
%% say), LaTeX's new code takes the paragraph skip off below it and adds it back at the next blank line.
%% Added back as a separate skip it keeps the space before a following heading, statement or list from
%% merging with the space below the equation; both are left out instead, as with the old code.
\def\thesis@addparskip{%
    \ifdim\lastskip>\z@
        \@tempskipa\lastskip \unskip \@tempskipb\glueexpr\lastskip+\parskip\relax
        \ifdim\@tempskipb=\z@ \ifdim\gluestretch\@tempskipb=\z@ \ifdim\glueshrink\@tempskipb=\z@
            \unskip \vskip\@tempskipa % the display's "minus the paragraph skip" and this one cancel out
        \else \vskip\glueexpr\@tempskipa+\parskip\relax \fi
        \else \vskip\glueexpr\@tempskipa+\parskip\relax \fi
        \else \vskip\glueexpr\@tempskipa+\parskip\relax \fi
    \else \vskip\parskip \fi}
\ExplSyntaxOn
\def\@doendpe{\@endpetrue
  \def\par{\@restorepar \clubpenalty\@clubpenalty
    \if@domathendpe \thesis@addparskip \@domathendpefalse \fi
    \tag_socket_use:n {@doendpe} \@endpefalse \everypar{} \par}
  \everypar{{\setbox\z@\lastbox}\everypar{}\@endpefalse\@domathendpefalse}}
\ExplSyntaxOff

%% A page that ends with a displayed equation: LaTeX's new display code leaves skips after it that add up
%% to nothing, and they kept the type block from ending at the equation's depth, as it did with the old
%% code (the page then came out a few points fuller). Skips at the end of a page that add up to nothing
%% are removed before the page is made up.
%% (The page is made up as before: a stretchable skip at its end, from \clearpage, stays where it is.)
\def\@outputbox@removebskip{\global\let\@outputbox@reinsertbskip\relax}
\newif\ifthesis@stripped \newif\ifthesis@stripany
\def\thesis@striptail{%
    \ifnum\lastnodetype=13 \unpenalty\expandafter\thesis@striptail
    \else\ifnum\lastnodetype=11
        \ifnum\numexpr\gluestretchorder\lastskip+\glueshrinkorder\lastskip=\z@
            \ifdim\lastskip=\z@\else\thesis@strippedtrue\fi
            \thesis@stripanytrue \advance\skip@\lastskip \unskip\expandafter\expandafter\expandafter\thesis@striptail
        \fi
    \fi\fi}
\def\@make@normalcolbox{%
    \setbox\@outputbox\vbox{\boxmaxdepth\@maxdepth \unvbox\@outputbox
        \skip@\z@skip \thesis@strippedfalse \thesis@stripanyfalse \thesis@striptail
        \ifthesis@stripped
            \ifdim\skip@=\z@ \ifdim\gluestretch\skip@=\z@ \ifdim\glueshrink\skip@=\z@
            \else\vskip\skip@\fi \else\vskip\skip@\fi \else\vskip\skip@\fi
        \else \ifthesis@stripany \vskip\skip@ \fi\fi}% (only skips of nothing: one is put back, as the page
        % then ended with a skip with the old code too)
    \setbox\@outputbox \vbox to\@colht {%
        \@texttop
        \@outputbox@depth \dp\@outputbox
        \unvbox \@outputbox
        \vskip -\@outputbox@depth
        \@textbottom}}

%% microtype lets the first letter after the label of a list item or statement ("Proof.") protrude into
%% the space after the label; it does that through LaTeX's old list code, so with the new code here.
\newif\ifthesis@afterlabel
\def\thesis@lpstep{\ifthesis@afterlabel\global\thesis@afterlabelfalse\expandafter\thesis@lp\fi}
\def\thesis@lp{\ifdefined\leftprotrusion\expandafter\leftprotrusion\fi}
\ExplSyntaxOn
\cs_gset_protected:Npn \__kernel_list_label_after:n #1
  {
    \tag_socket_use:nn {block/startpara/direct} { #1 }
    \global\thesis@afterlabeltrue
    \exp_args:No \tl_if_in:nnF { \the\everypar } { \thesis@lpstep }
      { \everypar \expandafter { \the\everypar \thesis@lpstep } }
  }
\ExplSyntaxOff

%% Float placement as memoir set it: more floats per page, and fuller pages of text and floats.
\renewcommand{\topfraction}{.85}    \renewcommand{\bottomfraction}{.5}
\renewcommand{\textfraction}{.1}    \renewcommand{\floatpagefraction}{.7}
\renewcommand{\dbltopfraction}{.85} \renewcommand{\dblfloatpagefraction}{.7}
\setcounter{topnumber}{3} \setcounter{bottomnumber}{2} \setcounter{totalnumber}{4} \setcounter{dbltopnumber}{3}
\setcounter{tocdepth}{1}
\renewcommand{\labelenumii}{\theenumii)}
\renewcommand{\thefigure}{\thechapter.\@arabic\c@figure}
\renewcommand{\thetable}{\thechapter.\@arabic\c@table}

%% After a displayed equation the page may break at once, as with LaTeX's old display code: LaTeX's
%% new code allows the break only after some skips, which counts the equation's depth into the page
%% and could push the next lines to the next page.
\ExplSyntaxOn
\cs_if_exist:NT \__math_prepare_display_end:
  {
    \cs_gset_protected:Npn \__math_prepare_display_end:
      {
        \bool_lazy_or:nnTF
          { \dim_compare_p:nNn \belowdisplayskip < {0pt} }
          { \dim_compare_p:nNn \belowdisplayshortskip < {0pt} }
          { \tl_gclear:N \g__math_skip_sign_tl }
          {
            \tl_gset:Nn \g__math_skip_sign_tl {-}
            \skip_set:Nn \belowdisplayskip      {-\belowdisplayskip}
            \skip_set:Nn \belowdisplayshortskip {-\belowdisplayshortskip}
          }
        \int_gset:Nn \g__math_postdisplaypenalty_int { \@M }
      }
  }
\ExplSyntaxOff

%% Footnotes as memoir set them: a big skip above the rule, measured from the baseline of the last line
%% of text (not from below its descenders).
\setlength{\skip\footins}{\bigskipamount}
%% the mark in a box 1.8 em of the class's type size wide, the text then indented 1 em per paragraph
\AddToHook{begindocument/before}{\ifdefined\footnotemargin \setlength{\footnotemargin}{1.8\thesis@em}\fi}
\newdimen\thesis@footparindent \thesis@footparindent=\thesis@em
\AddToHook{fntext/para}{\parindent\thesis@footparindent}
\AddToHook{fntext}{\def\baselinestretch{1}}% footnotes single-spaced (as memoir)
\AssignSocketPlug{build/column/baselineattach}{on}

%% Lists (memoir's scheme, as in the earlier versions of this class): \tightlists (commands.tex) sets
%% them without extra space between items, the first line of a further paragraph in an item indented.
\newskip\parsepi \newskip\topsepi \newskip\itemsepi \newskip\parsepii \newskip\topsepii \newskip\itemsepii
\newskip\topsepiii \newskip\itemsepiii \newskip\partopsepiii
\setlength{\partopsep}{0.2\onelineskip \@plus 0.1\onelineskip \@minus 0.1\onelineskip}
\parsepi=0.3333\onelineskip \@plus 0.1667\onelineskip \@minus\p@ \itemsepi=\parsepi
\topsepi=0.6667\onelineskip \@plus 0.3333\onelineskip \@minus 0.2\onelineskip
\parsepii=0.1667\onelineskip \@plus\p@ \@minus\p@ \topsepii=\parsepi \itemsepii=\parsepii
\topsepiii=\parsepii \itemsepiii=\topsepiii \partopsepiii=\p@ \@plus\z@ \@minus\p@
\newdimen\thesis@listparindent % the paragraph indent in lists: none, or the text's (\tightlists)
\def\@listi{\leftmargin\leftmargini \parsep\parsepi \topsep\topsepi \itemsep\itemsepi \listparindent\thesis@listparindent}
\let\@listI\@listi \@listi
\def\@listii{\leftmargin\leftmarginii \labelwidth\leftmarginii \advance\labelwidth-\labelsep
    \topsep\topsepii \parsep\parsepii \itemsep\itemsepii \listparindent\thesis@listparindent}
\def\@listiii{\leftmargin\leftmarginiii \labelwidth\leftmarginiii \advance\labelwidth-\labelsep
    \topsep\topsepiii \parsep\z@ \itemsep\itemsepiii \partopsep\partopsepiii \listparindent\thesis@listparindent}
\newcommand*{\tightlists}{%
    \setlength{\partopsep}{0.5\onelineskip \@plus \p@ \@minus \p@}%
    \parsepi=\z@ \@plus\p@ \@minus\p@ \itemsepi=\parsepi \topsepi=\z@ \@plus\p@ \@minus\p@
    \parsepii=\z@ \@plus\p@ \@minus\p@ \topsepii=\parsepi \topsepiii=\parsepii
    \thesis@listparindent\parindent}

%% \needspace{3\onelineskip}: start a new page unless that much space is left on this one
\newcommand{\needspace}[1]{\begingroup\setlength{\dimen@}{#1}%
    \vskip\z@\@plus\dimen@\penalty -100\vskip\z@\@plus-\dimen@
    \vskip\dimen@\penalty 9999\vskip-\dimen@\vskip\z@skip\endgroup}

%% No widows or orphans: never leave a single line of a paragraph alone at the top or bottom of a
%% page. Facing pages still end on the same line: when a page has to break early, the space around
%% headings, displays and floats stretches a little instead (pages are never allowed to run long).
\clubpenalty=10000          % first line of a paragraph alone at the bottom of a page
\widowpenalty=10000         % last line of a paragraph alone at the top of a page
\displaywidowpenalty=10000  % last line before a displayed equation alone at the top of a page
\brokenpenalty=5000         % avoid a page break right after a hyphenated line
\vbadness=10000             % that stretching is intended: don't report it as an underfull page
%% But only up to a limit: each space stretches at most as far as it allows. A page that needs more (few
%% headings or displays to share the gap) ends short by the rest instead, so the spacing stays even.
\directlua{
    function thesis_stretch(n)
        local s = 0
        for g in node.traverse_id(node.id("glue"), tex.box[n].list) do
            if g.stretch_order > 0 and g.stretch > 0 then tex.sprint("-1") return end
            s = s + g.stretch
        end
        tex.sprint(s)
    end
}
\AtBeginDocument{%
    \let\thesis@makecol\@makecol
    \def\@makecol{\thesis@makecol
        \setbox\@tempboxa\vbox{\unvcopy\@outputbox}%
        \dimen@=\dimexpr\@colht-\ht\@tempboxa-\dp\@tempboxa\relax % the gap to fill
        \dimen@ii=\directlua{thesis_stretch(\number\@outputbox)}sp % what the spaces allow
        \ifdim\dimen@ii>\z@ \ifdim\dimen@>\z@
            \dimen@=\dimexpr\dimen@-\dimen@ii\relax % the part beyond what they allow: at the foot
            \ifdim\dimen@>\onelineskip % less than a line: stretch a little further, stay flush
                \setbox\@outputbox\vbox to\@colht{\unvbox\@outputbox\vskip\z@\@plus\dimen@}%
            \fi
        \fi\fi}}
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

%%% THESIS INFORMATION AND ARCHIVAL PDF
%% _thesisinfo.tex (title, author, committee, ...) is read here, so that the PDF/A setup can
%% take its metadata from it.
\IfFileExists{_thesisinfo.tex}{\input{_thesisinfo}}{\ClassWarningNoLine{personal}{_thesisinfo.tex not found}}
\input{_options/pdfa} % before anything that loads xcolor (showframe, lualineno, ...)

\if@showframe
    \RequirePackage{showframe}
\fi

\if@draft
    %% line numbers in the margin, so readers can point at a line ("p. 12, l. 31"); lualineno numbers
    %% the lines of each finished page just before it is shipped out, equations included
    \RequirePackage{lualineno}
    \newcounter{thesislineno}
    \lualineno{
        define = {
            name = thesis
            toks = {\stepcounter{thesislineno}}
            left = {\normalfont\fontsize{6}{7}\selectfont\sffamily\color{black!45}\thethesislineno\kern4mm}
        }
        set = thesis
    }
    \RequirePackage[firstpageonly=false]{draftwatermark}
    \DraftwatermarkOptions{text={\normalfont DRAFT \textendash\ \today}, fontsize=8pt, angle=0, pos={0.5\paperwidth, 4mm}, color=black!60}
\fi

%%% COLOR-RELATED
\RequirePackage{xcolor}     % https://ctan.org/pkg/xcolor
\input{_options/formatColor}

%%% THUMB TABS (TikZ)
\RequirePackage{tikz}
\input{_options/thumb}

%%% HYPHENATION LOG for tools/check_hyphenation.py: every word TeX hyphenates at a line end goes to the
%% log with its page (the output does not change).
\IfFileExists{_options/hyphenationlog.lua}{\directlua{dofile("_options/hyphenationlog.lua")}}{}

%%% FIGURE LOG for tools/check_figures.py: every included graphic writes its natural and printed size
%% (and page) to the log, and the log records the text width, caption size and font scale.
\AddToHookWithArguments{cmd/Gin@setfile/after}{\thesis@logfigure{#3}}
%% (draft: the space before the file name in the box that graphicx sets, which LaTeX's tagging version of
%% that code drops: the name is the only thing set in \ttfamily there)
\AddToHook{cmd/Gin@setfile/before}{\ifGin@draft \let\thesis@ttfamily\ttfamily
    \def\ttfamily{\space\thesis@ttfamily\let\ttfamily\thesis@ttfamily}\fi}
\AtBeginDocument{%
    \begingroup\small\edef\thesis@tmp{\f@size}\expandafter\endgroup
    \expandafter\def\expandafter\thesis@captionsize\expandafter{\thesis@tmp}%
    \wlog{Thesis layout: textwidth \the\textwidth\space| captionsize \thesis@captionsize pt | fontscale \thesis@fontscale}}
\def\thesis@logfigure#1{\edef\thesis@tmp{#1 | \the\Gin@nat@width\space x \the\Gin@nat@height\space
    | \the\Gin@req@width\space x \the\Gin@req@height}\expandafter\thesis@logfigure@\expandafter{\thesis@tmp}}
\def\thesis@logfigure@#1{\write\m@ne{Thesis figure: #1 | page \thepage}}

\input{_options/formatText}
\input{_options/formatPagestyles}

%% Language: British or American English, with Dutch for the Samenvatting.
\RequirePackage[dutch, main=\thesis@language]{babel}
\RequirePackage[style=\thesis@language]{csquotes}

\RequirePackage{microtype}

%%% MATHS: mathtools (loads amsmath); the maths font is set in fontMath.tex
\RequirePackage{mathtools}

%%% MATHS FONT CHOICE (see Fonts/README.md): MathTime Professional 2 as OpenType maths fonts, as
%% tools/mtpro2_otf.py writes them into Fonts/ (MTPro2Math.otf and the mtpro2-otf package), Complete or
%% Lite, whichever the files were made from. Otherwise newtx. \ifthesismathtime follows this choice.
\newif\ifthesismathtime
\IfFileExists{Fonts/mtpro2-otf.sty}{%
    %% the files are found through the search path that latexmkrc adds (Overleaf runs latexmk)
    \IfFileExists{mtpro2-otf.sty}{\thesismathtimetrue}%
      {\ClassWarningNoLine{personal}{MathTime fonts found in Fonts/, but TeX cannot see that folder.\MessageBreak
        Compile with latexmk, which reads the template's latexmkrc (Overleaf does this).\MessageBreak
        Using newtx for now}}}{}

%%% TEXT FONTS
%% Loaded through fontspec.
\input{_options/fontText}

%%% MATH FONT
\input{_options/fontMath}
%% Space around relations (=, <, \to) may stretch only a little in justified lines (TeX allows it to
%% double); the word spaces take up the slack instead.
\AtBeginDocument{\thickmuskip=5mu plus 2mu\relax}
%% Break an inline formula across lines only when nothing else works (TeX's defaults allow it readily after
%% =, < and after +, -); rewording is the better fix when it still happens.
\relpenalty=9999 \binoppenalty=9999
%% Give the Type 1 maths fonts a Unicode map, so maths can be copied and searched (PDF/A).
\pdfvariable gentounicode = 1
\protected\def\pdfglyphtounicode{\pdfextension glyphtounicode}
\input{glyphtounicode}

%%% CAPTIONS (figures, tables and equations are numbered per chapter by memoir: 2.1, 2.2, ...)
%% "TABLE 2.1" in bold small capitals, a quad, the caption in the small size. Tables have their caption
%% on top, figures below; 6pt (half a line) between caption and content. A caption that fits on one
%% line is centred; a longer one is justified, or ragged right without hyphens if narrower than 60 mm
%% (figures side by side: justified, such a narrow measure gives uneven word spaces and hyphens).
%% (The class sets its captions itself, as the caption package did for the earlier versions: that
%% package does not work with LaTeX's tagging code yet.)
\setlength{\abovecaptionskip}{0.5\onelineskip} \setlength{\belowcaptionskip}{\z@}
\newcommand*{\captionlabelfont}{\scshape\bfseries}
\newcommand*{\thesis@captiontop}{table,lstlisting}
\newif\ifthesis@captop
\newcommand*{\thesis@capstrut}{\vrule\@height\ht\strutbox\@width\z@}% (the first line as high as a strut)
\newif\ifthesis@capcentre \thesis@capcentretrue % (the captions of algorithms are not centred)
\newcommand{\thesis@captionbox}[2]{% label, text: the caption, as a box the width of the line
    \sbox\@tempboxa{\small{\captionlabelfont #1}\quad #2}%
    \vbox{\small\parindent\z@
        \ifdim\wd\@tempboxa>\hsize
            \parfillskip\z@\@plus1fil \ifdim\hsize<60mm \thesis@raggednohyphen\fi
        \else\ifthesis@capcentre
            \leftskip\@flushglue \rightskip\@flushglue \parfillskip\z@skip
        \fi\fi
        {\captionlabelfont #1}\thesis@capstrut\quad #2\@finalstrut\strutbox\par}}
%% Long tables: the caption the width of the line, centred on the table, 6pt above the table.
\ExplSyntaxOn
\def\thesis@LTmakecaption#1#2#3{% \@gobble for \caption*, label, text
  \LT@mcol\LT@cols{@{}c@{}}{%
    \AssignTaggingSocketPlug{parbox/before}{noop}%
    \AssignTaggingSocketPlug{parbox/after}{noop}%
    \hbox to\z@{\hss\parbox[t]\linewidth{\reset@font\normalsize
      \vskip-\ht\strutbox
      {\parindent\z@ \leavevmode
       \cs_if_eq:NNTF #1 \@gobble {\thesis@captionnolabel{#3}} {\thesis@captionbox{#2}{#3}}\par}%
      \vskip\dimexpr\abovecaptionskip\relax \hrule\@height\z@}%
    \hss}}}
\ExplSyntaxOff
\newcommand{\thesis@captionnolabel}[1]{\vbox{\small\parindent\z@
    \leftskip\@flushglue \rightskip\@flushglue \parfillskip\z@skip \thesis@capstrut#1\@finalstrut\strutbox\par}}
\AddToHook{begindocument}{\@ifpackageloaded{longtable}{\let\LT@makecaption\thesis@LTmakecaption}{}}
%% (and spaces after \caption in a long table are ignored, as with the caption package)
\AddToHook{begindocument/end}{\@ifpackageloaded{longtable}{\let\thesis@LTc@ption\LT@c@ption
    \def\LT@c@ption#1[#2]#3{\thesis@LTc@ption{#1}[{#2}]{#3}\ignorespaces}}{}}

%% Table rules and the space around them as memoir set them: in em and ex of the class's type size
%% (booktabs measures them in the text font when it is loaded, which is set 5 % smaller).
\AddToHook{package/booktabs/after}{%
    \dimen@=\thesis@em
    \setlength{\heavyrulewidth}{0.08\dimen@} \setlength{\lightrulewidth}{0.05\dimen@}
    \setlength{\cmidrulewidth}{0.03\dimen@}  \setlength{\cmidrulekern}{0.5\dimen@}
    \setlength{\defaultaddspace}{0.5\dimen@}
    \setlength{\belowrulesep}{0.28015\dimen@} \setlength{\aboverulesep}{0.1724\dimen@}}

%% A caption starts a paragraph of its own: its link target then does not add an empty line below a
%% figure that is set in the same paragraph as the \caption command.
\AddToHook{cmd/caption/before}{\ifhmode\par\fi}
\AddToHook{begindocument}{%
    \long\def\@makecaption#1#2{%
        \thesis@captopfalse
        \@for\@tempa:=\thesis@captiontop\do{\ifx\@tempa\@captype\thesis@captoptrue\fi}%
        \par
        \ifthesis@captop \vskip\belowcaptionskip \else \hrule\@height\z@ \vskip\abovecaptionskip \fi
        \UseHookWithArguments{cmd/@makecaption/before}{2}{#1}{#2}%
        \UseTaggingSocket{caption/begin}{\@current@float@struct}%
        \UseTaggingSocket{para/begin}%
        {\parindent\z@ \leavevmode \thesis@captionbox{#1}{#2}\par}%
        \@minipagefalse % (as a paragraph did: the material below the caption is spaced as in the text)
        \UseTaggingSocket{caption/end}%
        \ifthesis@captop \vskip\dimexpr\abovecaptionskip\relax
            \def\@tempa{lstlisting}\ifx\@tempa\@captype\else\hrule\@height\z@\fi
        \else \vskip\belowcaptionskip \fi}}
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
%% The reference list is listed in the contents (as memoir did)
\defbibheading{bibliography}[\bibname]{\chapter*{#1}\addcontentsline{toc}{chapter}{#1}%
    \@mkboth{\abx@MakeMarkcase{#1}}{\abx@MakeMarkcase{#1}}}
\setlength\bibitemsep{0.25\baselineskip} % space between references
%% Set ragged right: references are full of long names, journal titles and DOIs, which in justified
%% text leave wide gaps.
\RequirePackage{ragged2e}
%% Ragged-right lines need no hyphens: forbid them, and let the right edge vary a little more instead.
\newcommand*{\thesis@raggednohyphen}{\setlength{\RaggedRightRightskip}{0pt plus 4em}\RaggedRight
    \hyphenpenalty=10000 \tolerance=9999 \hbadness=10000 }
\renewcommand*{\bibfont}{\thesis@raggednohyphen}

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
\newcommand*{\thesis@urlotherchars}{% letters, digits and ) ] ? ; ! @ + (not ( or [: amsmath measures ( for its struts)
    \@tfor\thesis@c:=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789)]?;!@+\do{%
        \expandafter\thesis@do\thesis@c}}
\newcommand*{\thesis@do}[1]{\do#1{\thesis@urlslashfalse\mathchar`#1\penalty\thesis@urlother}}
%% Never leave the last few characters of a URL or DOI alone on a new line (the break points among the
%% last four characters are removed from the list url.sty has just built; no ~ in the Lua: it is an
%% active character here).
\directlua{
    function thesis_urltail(k)
        local nest = tex.nest[tex.nest.ptr]
        local n, chars = nest.tail, 0
        while n and not (n == nest.head) and chars < k do
            if n.id == node.id("penalty") then n.penalty = 10000
            elseif n.id == node.id("noad") then chars = chars + 1 end
            n = n.prev
        end
    end
}
\def\UrlRight{\directlua{thesis_urltail(4)}}
\thesis@urlsetup
\renewcommand*{\biburlsetup}{\thesis@urlsetup} % biblatex would otherwise apply its own rules in the references
%% "doi:" stays on the same line as the DOI itself (biblatex's default allows a break after the colon).
\DeclareFieldFormat{doi}{\mkbibacro{DOI}\addcolon\addnbspace
    \ifhyperref{\href{https://doi.org/#1}{\nolinkurl{#1}}}{\nolinkurl{#1}}}
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
    \AddToHook{cmd/chapter/before}{\newrefsection}% (biblatex finds no \@makechapterhead to hook into)
    \AddToHook{include/end}{\begingroup\let\blx@warn@bibempty\relax
        \printbibliography[heading=subbibintoc, title={References}]\endgroup}
\fi

