# latexmk settings for local builds: LuaLaTeX, PDF output.
# (On Overleaf, the compiler is chosen in Menu > Settings > Compiler.)
$pdf_mode = 4;

# MathTime Professional 2 (optional): the classic fonts made by tools/mtpro2_unicode.py live in the
# Fonts folder. Add it to TeX's search paths for style files, metrics, Type 1 fonts and font maps.
# Overleaf reads this file too. Harmless when the folder holds no fonts.
foreach my $var ('TEXINPUTS', 'TFMFONTS', 'T1FONTS', 'TEXFONTMAPS') {
    $ENV{$var} = './Fonts' . $search_path_separator . ($ENV{$var} // '');
}
