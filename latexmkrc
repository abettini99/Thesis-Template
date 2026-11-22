# latexmk settings for local builds: LuaLaTeX, PDF output.
# (On Overleaf, the compiler is chosen in Menu > Settings > Compiler.)
$pdf_mode = 4;

# MathTime Professional 2 (optional): the classic fonts made by tools/mtpro2_unicode.py live in the
# Fonts folder. Add it to TeX's search paths for style files, metrics, Type 1 fonts and font maps.
# Overleaf reads this file too. Harmless when the folder holds no fonts.
foreach my $var ('TEXINPUTS', 'TFMFONTS', 'T1FONTS', 'TEXFONTMAPS') {
    $ENV{$var} = './Fonts' . $search_path_separator . ($ENV{$var} // '');
}

# Local git clones: keep the pre-commit hook that refuses MathTime font files installed and up to date in
# .git/hooks (a copy, executable: Overleaf's GitHub synchronisation drops the executable flag of the file
# in tools/hooks, and git skips a hook that is not executable). Leaves a different hook of your own alone.
# Nothing happens on Overleaf, which has no .git folder.
{
    my ($src, $dst) = ('tools/hooks/pre-commit', '.git/hooks/pre-commit');
    if (-d '.git/hooks' && -f $src && open(my $in, '<:raw', $src)) {
        local $/; my $new = <$in>; close $in;
        my $old = '';
        if (-e $dst && open(my $cur, '<:raw', $dst)) { $old = <$cur>; close $cur; }
        if (($old ne $new || !-x $dst) && ($old eq '' || $old =~ /MathTime/)) {
            if (open(my $out, '>:raw', $dst)) {
                print $out $new; close $out; chmod 0755, $dst;
                print "latexmkrc: installed the MathTime pre-commit hook in $dst\n";
            }
        }
    }
}
