"""Show the cover in a few colour schemes in one image: .github/readme/cover-variants.png.

cover.tex is compiled once per colour scheme, with the texts of settings/cover.tex and without the guides;
each cover is checked with tools/check_print.py, and the covers (back, spine and front) are set out
two by two, each with its name above it.

Run from the repository root:  python3 .github/scripts/cover_variants.py
Needs LuaLaTeX with latexmk, pdftoppm (poppler), and Python with Pillow and pikepdf.
The GitHub workflow .github/workflows/readme-images.yml runs it after a day with pushes.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".github" / "readme" / "cover-variants.png"

# name, then background, text, small lines and motif (HTML colours); the first is the template's
# default, as set in settings/cover.tex
VARIANTS = [
    ("Light blue-green + teal (default)", None, None, None, None),
    ("Oxblood + blush", "5A1F2B", "F5EEE8", "D2B4B0", "E6B8A8"),
    ("Sand + terracotta", "EFE6D2", None, "5E5248", "A0522D"),  # text: the default near-black grey
    ("Black + muted sand", "1A1C22", "F2F0E8", "A8A296", "CDB98F"),
]


SAMPLE = r"\coverguidesfalse"  # the final look: without the guides

PX_PER_MM = 2.5  # scale of the image
# the look of .github/scripts/page_sizes.py: grey sheet, shadowed covers, captions underneath
GAP_MM, MARGIN_MM, CAPTION_MM = 14, 10, 22
BACKGROUND, INK, GREY = (238, 238, 236), (30, 30, 30), (110, 110, 110)


def build(i, background, text, secondary, motif, outdir):
    """Compile cover.tex in this colour scheme; return the PDF."""
    colours = "".join(
        rf"\definecolor{{{name}}}{{HTML}}{{{value}}}"
        for name, value in (
            ("coverback", background),
            ("covertext", text),
            ("coversecondary", secondary),
            ("covermotifcolour", motif),
        )
        if value
    )
    src = (ROOT / "cover.tex").read_text()
    # after settings/cover.tex, through the hook template/cover.tex offers for it
    src = "\\AddToHook{thesis/cover/settings}{" + colours + SAMPLE + "}\n" + src
    job = f"_covervariant_{i}"
    tex = ROOT / f"{job}.tex"
    tex.write_text(src)
    try:
        subprocess.run(
            [
                "latexmk",
                "-lualatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-outdir={outdir}",
                tex.name,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        log = Path(outdir, f"{job}.log")
        print(log.read_text(errors="replace")[-3000:] if log.exists() else e.stdout[-3000:])
        raise
    finally:
        tex.unlink()
    return Path(outdir, f"{job}.pdf")


def default_colours():
    """The four colours as settings/cover.tex sets them, as hex (a grey given as {gray}{x})."""
    src = (ROOT / "settings" / "cover.tex").read_text()
    out = []
    for name in ("coverback", "covertext", "coversecondary", "covermotifcolour"):
        m = re.search(rf"^\\definecolor\{{{name}\}}\{{(HTML|gray)\}}\{{([^}}]+)\}}", src, re.M)
        if not m:
            sys.exit(f"settings/cover.tex: no \\definecolor{{{name}}} with an HTML or gray value")
        model, value = m.groups()
        out.append(value.upper() if model == "HTML" else f"{round(float(value) * 255):02X}" * 3)
    return out


def font(bold, size):
    for name in (
        ["SourceSans3-Semibold.otf", "SourceSansPro-Semibold.otf"]
        if bold
        else ["SourceSans3-Regular.otf", "SourceSansPro-Regular.otf"]
    ):
        path = subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip()
        if path:
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def save_if_changed(img):
    """Save the image, unless the file already shows the same pixels: PNG files written by another
    Pillow version differ in their bytes, and the workflow would otherwise commit an unchanged image."""
    if OUT.exists():
        old = Image.open(OUT).convert("RGB")
        if old.size == img.size and ImageChops.difference(old, img.convert("RGB")).getbbox() is None:
            print(f"{OUT.relative_to(ROOT)}: unchanged")
            return
    img.save(OUT, optimize=True)
    print(f"saved {OUT.relative_to(ROOT)} ({img.width} × {img.height} px)")


def main():
    covers, failed = [], []
    defaults = default_colours()
    with tempfile.TemporaryDirectory() as tmp:
        for i, (label, *colours) in enumerate(VARIANTS):
            pdf = build(i, *colours, tmp)
            check = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "check_print.py"), str(pdf)],
                capture_output=True,
                text=True,
            )
            print(f"{label}:\n{check.stdout.strip()}")
            if check.returncode:
                failed.append(label)
            dpi = PX_PER_MM * 25.4
            subprocess.run(
                ["pdftoppm", "-r", f"{dpi}", "-png", "-singlefile", str(pdf), f"{tmp}/c{i}"],
                check=True,
                capture_output=True,
            )
            img = Image.open(f"{tmp}/c{i}.png").convert("RGB")
            # trim the bleed, so the covers show as they will look once trimmed
            bleed = round(3 * PX_PER_MM)
            values = [v or d for v, d in zip(colours, defaults)]
            covers.append((label, values, img.crop((bleed, bleed, img.width - bleed, img.height - bleed))))

    px = PX_PER_MM
    f_title, f_text = font(True, round(6.5 * px)), font(False, round(5.5 * px))
    w = max(c.width for *_, c in covers)
    h = max(c.height for *_, c in covers)
    cols = 2
    rows = (len(covers) + cols - 1) // cols
    cell_h = h + CAPTION_MM * px
    width = round(2 * MARGIN_MM * px + cols * w + (cols - 1) * GAP_MM * px)
    height = round(2 * MARGIN_MM * px + rows * cell_h + (rows - 1) * GAP_MM * px)
    sheet = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for n, (label, values, img) in enumerate(covers):
        r, c = divmod(n, cols)
        x = round(MARGIN_MM * px + c * (w + GAP_MM * px))
        y = round(MARGIN_MM * px + r * (cell_h + GAP_MM * px))
        base = y + img.height
        draw.rectangle([x + 4, y + 4, x + img.width + 4, base + 4], fill=(205, 205, 202))  # shadow
        sheet.paste(img, (x, y))
        draw.rectangle([x, y, x + img.width - 1, base - 1], outline=(180, 180, 176))
        ty = base + round(5 * px)
        draw.text((x, ty), label, font=f_title, fill=INK)
        # the four colours as swatches with their values: background, text, small lines, motif
        sx, sy = x, ty + round(9 * px)
        for role, value in zip(("background", "text", "small lines", "motif"), values):
            sw = round(4 * px)
            draw.rectangle([sx, sy, sx + sw, sy + sw], fill="#" + value, outline=(180, 180, 176))
            text = f"{role} {value}"
            draw.text((sx + sw + round(1.5 * px), sy - round(0.6 * px)), text, font=f_text, fill=GREY)
            sx += sw + round(1.5 * px) + draw.textlength(text, font=f_text) + round(5 * px)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    save_if_changed(sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    if failed:
        print("check_print found errors in: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
