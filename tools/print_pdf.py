#!/usr/bin/env python3
"""Convert the print PDF to CMYK, for a printer who wants every colour in the file already in their inks.

    python3 tools/print_pdf.py main.pdf --profile printer.icc      ->  main-cmyk.pdf

Most printers take the print-preparation edition as it is (PDF/X with RGB declared as sRGB) and convert
it themselves, for their own press and paper. Use this only when a printer asks for CMYK. Ask them for
their colour profile (an .icc file): CMYK numbers are ink amounts for one press and one paper, and a
file converted for another one has to be converted again, which costs quality and can put more ink on
the paper than it takes. Without --profile the standard FOGRA39 profile (offset print on coated paper,
from TeX Live) is used, with a warning.

What it does: every RGB colour (text, lines, fills, shadings) and every RGB image is converted from sRGB
to the printer's CMYK with their profile (relative colorimetric, with black point compensation); black
and greys stay black ink only; the PDF's output intent becomes the printer's profile. The PDF/X version
stays that of the input (set \\thesisprintstandard in settings/thesisinfo.tex before compiling: X-6, or X-4 for
printers who cannot take PDF 2.0). Transparency stays (both PDF/X-4 and PDF/X-6 allow it); for PDF/X-1a,
which does not, use Acrobat Pro or Ghostscript 10.05 or later. Anything it does not know how to convert,
it names and stops, rather than write a wrong file. Check the result with tools/check_print.py and look at
it before sending: CMYK cannot show the brightest screen colours, so saturated blues and greens come out
a little duller (as they would at the printer). Needs pikepdf and Pillow (pip install -r requirements.txt).
"""
import argparse
import io
import subprocess
import sys
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageCms


class Unsupported(Exception):
    pass


def find_fogra39():
    try:
        out = subprocess.run(["kpsewhich", "FOGRA39L_coated.icc"], capture_output=True, text=True).stdout.strip()
        if out:
            return Path(out)
    except OSError:
        pass
    return None


def icc_description(data):
    try:
        prof = ImageCms.ImageCmsProfile(io.BytesIO(data))
        return ImageCms.getProfileDescription(prof).strip() or "printer profile"
    except Exception:
        return "printer profile"


class Converter:
    def __init__(self, pdf, profile_bytes):
        self.pdf = pdf
        srgb = ImageCms.createProfile("sRGB")
        cmyk = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
        flags = ImageCms.Flags.BLACKPOINTCOMPENSATION if hasattr(ImageCms, "Flags") else 0x2000
        self.tf = ImageCms.buildTransform(srgb, cmyk, "RGB", "CMYK",
                                          renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC, flags=flags)
        self.cache, self.seen, self.rgbnames = {}, set(), {}
        self.count = {"colours": 0, "images": 0}

    # --- colour values -------------------------------------------------------------------------
    def cmyk(self, rgb):
        """sRGB (0-1) to CMYK (0-1); greys stay black ink only."""
        r, g, b = (min(1.0, max(0.0, float(v))) for v in rgb)
        if abs(r - g) < 1e-6 and abs(g - b) < 1e-6:
            return (0.0, 0.0, 0.0, round(1.0 - r, 5))
        key = (round(r, 4), round(g, 4), round(b, 4))
        if key not in self.cache:
            im = Image.new("RGB", (1, 1), tuple(int(round(v * 255)) for v in key))
            c = ImageCms.applyTransform(im, self.tf).getpixel((0, 0))
            self.cache[key] = tuple(round(v / 255, 5) for v in c)
        return self.cache[key]

    @staticmethod
    def rgb_space(cs):
        """True for a three-component RGB space (DeviceRGB, ICCBased with N 3, CalRGB)."""
        if cs == Name.DeviceRGB:
            return True
        if isinstance(cs, Array) and len(cs) == 2:
            if cs[0] == Name.ICCBased and int(cs[1].get("/N", 0)) == 3:
                return True
            if cs[0] == Name.CalRGB:
                return True
        return False

    def space(self, cs, where):
        """A colour space with RGB replaced by DeviceCMYK (Indexed palettes converted)."""
        if self.rgb_space(cs):
            return Name.DeviceCMYK
        if isinstance(cs, Array) and len(cs) >= 1:
            kind = cs[0]
            if kind == Name.Indexed:
                if self.rgb_space(cs[1]):
                    hival = int(cs[2])
                    lookup = cs[3].read_bytes() if isinstance(cs[3], pikepdf.Stream) else bytes(cs[3])
                    out = bytearray()
                    for i in range(hival + 1):
                        c = self.cmyk([lookup[3 * i + j] / 255 for j in range(3)])
                        out += bytes(int(round(v * 255)) for v in c)
                    return Array([Name.Indexed, Name.DeviceCMYK, hival, pikepdf.String(bytes(out))])
                return cs
            if kind == Name.Pattern and len(cs) >= 2:
                return Array([Name.Pattern, self.space(cs[1], where)])
            if kind in (Name.ICCBased,) and int(cs[1].get("/N", 0)) == 4:
                return cs
            if kind in (Name.Separation, Name.DeviceN):
                alt = cs[2]
                if self.rgb_space(alt):
                    raise Unsupported(f"a spot colour with an RGB alternative ({where})")
                return cs
        return cs

    # --- shadings and functions ------------------------------------------------------------------
    def function(self, fn, where):
        """A function returning RGB, rewritten to return CMYK."""
        t = int(fn.get("/FunctionType", -1))
        if t == 2:
            for key in ("/C0", "/C1"):
                if key in fn and len(fn[key]) == 3:
                    fn[key] = Array(self.cmyk(fn[key]))
            if "/C0" not in fn:
                fn.C0 = Array(self.cmyk([0, 0, 0]))
            if "/C1" not in fn:
                fn.C1 = Array(self.cmyk([1, 1, 1]))
            if "/Range" in fn:
                fn.Range = Array([0, 1] * 4)
        elif t == 3:
            for sub in fn.Functions:
                self.function(sub, where)
            if "/Range" in fn:
                fn.Range = Array([0, 1] * 4)
        elif t == 0 and int(fn.get("/BitsPerSample", 0)) == 8 and isinstance(fn, pikepdf.Stream):
            data = fn.read_bytes()
            out = bytearray()
            for i in range(0, len(data) - 2, 3):
                out += bytes(int(round(v * 255)) for v in self.cmyk([data[i] / 255, data[i + 1] / 255, data[i + 2] / 255]))
            fn.write(bytes(out))
            fn.Range = Array([0, 1] * 4)
            if "/Decode" in fn:
                fn.Decode = Array([0, 1] * 4)
        else:
            raise Unsupported(f"a colour gradient of a kind not converted (function type {t}; {where})")

    def shading(self, sh, where):
        if not self.rgb_space(sh.get("/ColorSpace")):
            return
        if "/Function" not in sh:
            raise Unsupported(f"a colour gradient without a function ({where})")
        fns = sh.Function if isinstance(sh.Function, Array) else [sh.Function]
        for fn in fns:
            self.function(fn, where)
        sh.ColorSpace = Name.DeviceCMYK
        if "/Background" in sh and len(sh.Background) == 3:
            sh.Background = Array(self.cmyk(sh.Background))

    # --- images ---------------------------------------------------------------------------------
    def image(self, xo, where):
        cs = xo.get("/ColorSpace")
        if isinstance(cs, Array) and len(cs) and cs[0] == Name.Indexed:
            xo.ColorSpace = self.space(cs, where)
            self.count["images"] += 1
            return
        if not self.rgb_space(cs):
            return
        if int(xo.get("/BitsPerComponent", 8)) != 8:
            raise Unsupported(f"an RGB image with {xo.get('/BitsPerComponent')} bits per component ({where})")
        im = pikepdf.PdfImage(xo).as_pil_image().convert("RGB")
        out = ImageCms.applyTransform(im, self.tf)
        # greys in the image stay black ink only
        px_rgb, px_cmyk = im.load(), out.load()
        w, h = im.size
        if w * h <= 4_000_000:
            for y in range(h):
                for x in range(w):
                    r, g, b = px_rgb[x, y]
                    if r == g == b:
                        px_cmyk[x, y] = (0, 0, 0, 255 - r)
        was_jpeg = xo.get("/Filter") in (Name.DCTDecode, Array([Name.DCTDecode]))
        if was_jpeg:
            buf = io.BytesIO()
            out.save(buf, "JPEG", quality=95)
            xo.write(buf.getvalue(), filter=Name.DCTDecode)
            xo.Decode = Array([1, 0, 1, 0, 1, 0, 1, 0])   # Adobe's inverted CMYK JPEG
        else:
            xo.write(out.tobytes(), filter=None)
            if "/Decode" in xo:
                del xo["/Decode"]
        xo.ColorSpace = Name.DeviceCMYK
        xo.BitsPerComponent = 8
        if "/DecodeParms" in xo:
            del xo["/DecodeParms"]
        self.count["images"] += 1

    @staticmethod
    def key(res):
        return res.objgen if res.is_indirect else id(res)

    # --- content streams ------------------------------------------------------------------------
    def content(self, obj, res, where):
        cs_res = res.get("/ColorSpace", {}) if res is not None else {}
        csd = res.get("/ColorSpace") if res is not None else None
        rgbnames = self.rgbnames.get(self.key(csd), set()) if csd is not None else set()
        ops = pikepdf.parse_content_stream(obj)
        out, fill_rgb, stroke_rgb = [], False, False
        for operands, op in ops:
            o = str(op)
            if o in ("rg", "RG"):
                out.append((list(self.cmyk(operands)), pikepdf.Operator("k" if o == "rg" else "K")))
                self.count["colours"] += 1
            elif o in ("cs", "CS"):
                name = operands[0]
                space = cs_res.get(name) if name not in (Name.DeviceRGB, Name.DeviceGray, Name.DeviceCMYK, Name.Pattern) else name
                is_rgb = self.rgb_space(space) or str(name) in rgbnames
                if o == "cs":
                    fill_rgb = is_rgb
                else:
                    stroke_rgb = is_rgb
                out.append(([Name.DeviceCMYK] if is_rgb else operands, op))
            elif o in ("sc", "scn", "SC", "SCN") and ((o in ("sc", "scn") and fill_rgb) or (o in ("SC", "SCN") and stroke_rgb)):
                nums = [x for x in operands if not isinstance(x, Name)]
                if len(nums) != 3:
                    raise Unsupported(f"an RGB colour given as {o} with {len(nums)} values ({where})")
                out.append((list(self.cmyk(nums)), op))
                self.count["colours"] += 1
            elif o == "BI":
                raise Unsupported(f"an inline image ({where})")
            else:
                out.append((operands, op))
        data = pikepdf.unparse_content_stream(out)
        if isinstance(obj, pikepdf.Page):
            obj.obj.Contents = self.pdf.make_stream(data)
        else:
            obj.write(data)

    def resources(self, res, where):
        if res is None:
            return
        csd = res.get("/ColorSpace")
        if csd is not None:
            if self.key(csd) in self.rgbnames:               # shared by several pages: done already
                return self.resources_rest(res, where)
            rgbnames = {key for key in csd.keys() if self.rgb_space(csd[key])}
            self.rgbnames[self.key(csd)] = rgbnames          # (the content still names them)
            for key in list(csd.keys()):
                if key == "/DefaultRGB":
                    del csd[key]
                else:
                    csd[key] = self.space(csd[key], where)
        self.resources_rest(res, where)

    def resources_rest(self, res, where):
        for key in list(res.get("/XObject", {}).keys()):
            xo = res.XObject[key]
            if xo.objgen in self.seen and xo.objgen != (0, 0):
                continue
            self.seen.add(xo.objgen)
            if xo.get("/Subtype") == Name.Image:
                self.image(xo, where)
                if "/SMask" in xo:
                    pass                                       # soft masks are grey: unchanged
            elif xo.get("/Subtype") == Name.Form:
                self.form(xo, where)
        for key in list(res.get("/Pattern", {}).keys()):
            pat = res.Pattern[key]
            if int(pat.get("/PatternType", 0)) == 1:
                self.form(pat, where)
            elif "/Shading" in pat:
                self.shading(pat.Shading, where)
        for key in list(res.get("/Shading", {}).keys()):
            self.shading(res.Shading[key], where)
        for key in list(res.get("/ExtGState", {}).keys()):
            smask = res.ExtGState[key].get("/SMask")
            if isinstance(smask, Dictionary) and "/G" in smask:
                g = smask.G
                if g.objgen not in self.seen:
                    self.seen.add(g.objgen)
                    self.form(g, where)
                if "/BC" in smask and len(smask.BC) == 3:
                    smask.BC = Array(self.cmyk(smask.BC))
        for key in list(res.get("/Font", {}).keys()):
            font = res.Font[key]
            if font.get("/Subtype") == Name.Type3:
                for name in list(font.CharProcs.keys()):
                    self.content(font.CharProcs[name], font.get("/Resources", res), where)
                self.resources(font.get("/Resources"), where)

    def group(self, obj):
        if "/Group" in obj and "/CS" in obj.Group and self.rgb_space(obj.Group.CS):
            obj.Group.CS = Name.DeviceCMYK

    def form(self, xo, where):
        self.group(xo)
        if "/Resources" in xo:
            self.resources(xo.Resources, where)
        self.content(xo, xo.get("/Resources", Dictionary()), where)

    def page(self, page, n):
        where = f"page {n}"
        self.group(page.obj)
        res = page.obj.get("/Resources")
        self.resources(res, where)
        self.content(page, res if res is not None else Dictionary(), where)


def main(argv):
    ap = argparse.ArgumentParser(description="Convert the print PDF to CMYK with the printer's colour profile.")
    ap.add_argument("pdf", help="the print-preparation PDF (PDF/X-6 or PDF/X-4)")
    ap.add_argument("--profile", help="the printer's colour profile (.icc); default FOGRA39 (coated paper)")
    ap.add_argument("-o", "--output", help="output file (default: <name>-cmyk.pdf)")
    args = ap.parse_args(argv)

    if args.profile:
        profile = Path(args.profile)
    else:
        profile = find_fogra39()
        if profile is None:
            print("error: no --profile given and FOGRA39 not found (kpsewhich FOGRA39L_coated.icc)")
            return 2
        print("warning: converting for FOGRA39 (offset print on coated paper). Ask your printer for their colour\n"
              "         profile: converted for another press or paper, the file has to be converted again.")
    data = profile.read_bytes()
    if data[12:16] != b"prtr" or data[16:20] != b"CMYK":
        print(f"error: {profile} is not a CMYK printer profile")
        return 2

    src = Path(args.pdf)
    dst = Path(args.output) if args.output else src.with_name(src.stem + "-cmyk.pdf")
    with pikepdf.open(src) as pdf:
        intents = [oi for oi in pdf.Root.get("/OutputIntents", []) if oi.get("/S") == Name.GTS_PDFX]
        if not intents:
            print(f"error: {src} is not a PDF/X file (compile the print-preparation edition)")
            return 2
        conv = Converter(pdf, data)
        try:
            for n, page in enumerate(pdf.pages, 1):
                conv.page(page, n)
        except Unsupported as err:
            print(f"error: cannot convert {err}; nothing written")
            return 1
        icc = pikepdf.Stream(pdf, data)
        icc.N = 4
        desc = icc_description(data)
        for oi in intents:
            oi.DestOutputProfile = icc
            oi.OutputConditionIdentifier = pikepdf.String(desc)
            oi.Info = pikepdf.String(desc)
            if "/RegistryName" in oi and profile.name != "FOGRA39L_coated.icc":
                del oi["/RegistryName"]
        pdf.save(dst)
    print(f"{dst}: {conv.count['colours']} colours and {conv.count['images']} images converted to CMYK for {desc}")
    print(f"check it: python3 tools/check_print.py {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
