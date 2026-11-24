#!/usr/bin/env python3
"""Make figure PDFs ready for print: RGB colours in sRGB, black and greys as true grey.

    python3 tools/print_ready.py figures/plot.pdf [more.pdf ...]     (changes the files in place)

A printer converts RGB to the inks of their press. They can only do that exactly when they know which
RGB is meant: this script sets every RGB colour in a figure in sRGB (the colour space of screens and of
matplotlib), explicitly, in the figure file itself, where LaTeX cannot reach (with sRGB also as the
default for anything else written as plain RGB). It also turns pure greys and black
written as RGB (axes, tick labels, text) into true grey, which prints with black ink only: as RGB they
would become "rich black", a mix of all four inks, and small text would get coloured fringes wherever the
four printing plates do not line up exactly. Nothing changes on screen.

figures/plots/thesis_fonts.py runs this on every figure it saves; use the script for figure PDFs made elsewhere
(a co-author's plot, another program). tools/check_print.py finds figures in the print PDF that still
need it. Photos (PNG, JPEG) need nothing: LaTeX declares their RGB as sRGB itself. Running it twice on a
file changes nothing the second time. Needs pikepdf and Pillow (pip install -r requirements.txt).
"""
import sys
from pathlib import Path

import pikepdf
from pikepdf import Name, Array, Dictionary

RGB_OPS = {"rg": "g", "RG": "G"}


def srgb_profile():
    """An sRGB ICC profile (Pillow's built-in, from LittleCMS)."""
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


class Fixer:
    def __init__(self, pdf):
        self.pdf = pdf
        icc = pikepdf.Stream(pdf, srgb_profile())
        icc.N = 3
        self.cs = pdf.make_indirect(Array([Name.ICCBased, icc]))
        self.seen = set()
        self.greys = 0

    def colourspace(self, cs):
        """A colour space with every /DeviceRGB in it replaced by the sRGB space."""
        if isinstance(cs, Name):
            return self.cs if cs == Name.DeviceRGB else cs
        if isinstance(cs, Array) and len(cs) > 0:
            kind = cs[0]
            if kind == Name.Indexed and len(cs) >= 2:
                cs[1] = self.colourspace(cs[1])
            elif kind == Name.Pattern and len(cs) >= 2:
                cs[1] = self.colourspace(cs[1])
            elif kind in (Name.Separation, Name.DeviceN) and len(cs) >= 3:
                cs[2] = self.colourspace(cs[2])
        return cs

    def content(self, obj):
        """Rewrite a content stream: equal RGB components become grey."""
        ops = pikepdf.parse_content_stream(obj)
        out, changed = [], False
        for operands, op in ops:
            o = str(op)
            if o in RGB_OPS and len(operands) == 3 and operands[0] == operands[1] == operands[2]:
                out.append(([operands[0]], pikepdf.Operator(RGB_OPS[o])))
                changed = True
                self.greys += 1
            elif o in RGB_OPS and len(operands) == 3:               # a colour: in sRGB, explicitly
                fill = o == "rg"
                out.append(([Name("/thesisSRGB")], pikepdf.Operator("cs" if fill else "CS")))
                out.append((list(operands), pikepdf.Operator("sc" if fill else "SC")))
                changed = True
            elif o in ("cs", "CS") and len(operands) == 1 and operands[0] == Name.DeviceRGB:
                out.append(([Name("/thesisSRGB")], op))
                changed = True
            else:
                out.append((operands, op))
        if changed:
            data = pikepdf.unparse_content_stream(out)
            if isinstance(obj, pikepdf.Page):
                obj.obj.Contents = self.pdf.make_stream(data)
            else:
                obj.write(data)
        return changed

    def resources(self, res):
        """Declare RGB as sRGB in a resource dictionary, and fix everything it uses."""
        if res is None:
            return
        csd = res.get("/ColorSpace")
        if csd is None:
            csd = res.ColorSpace = Dictionary()
        csd.DefaultRGB = self.cs
        csd.thesisSRGB = self.cs
        for key in list(csd.keys()):
            if key not in ("/DefaultRGB", "/thesisSRGB"):
                csd[key] = self.colourspace(csd[key])
        for key in list(res.get("/XObject", {}).keys()):
            self.xobject(res.XObject[key])
        for key in list(res.get("/Pattern", {}).keys()):
            pat = res.Pattern[key]
            if pat.get("/PatternType") == 1:                    # tiling pattern: a content stream
                self.form(pat)
            elif "/Shading" in pat:
                self.shading(pat.Shading)
        for key in list(res.get("/Shading", {}).keys()):
            self.shading(res.Shading[key])
        for key in list(res.get("/ExtGState", {}).keys()):
            smask = res.ExtGState[key].get("/SMask")
            if isinstance(smask, Dictionary) and "/G" in smask:
                self.form(smask.G)

    def shading(self, sh):
        if "/ColorSpace" in sh:
            sh.ColorSpace = self.colourspace(sh.ColorSpace)

    def form(self, xo):
        if xo.objgen in self.seen and xo.objgen != (0, 0):
            return
        self.seen.add(xo.objgen)
        if "/Group" in xo and "/CS" in xo.Group:
            xo.Group.CS = self.colourspace(xo.Group.CS)
        if "/Resources" not in xo:
            xo.Resources = Dictionary()
        self.resources(xo.Resources)
        self.content(xo)

    def xobject(self, xo):
        if xo.get("/Subtype") == Name.Form:
            self.form(xo)
        elif xo.get("/Subtype") == Name.Image and "/ColorSpace" in xo:
            xo.ColorSpace = self.colourspace(xo.ColorSpace)

    def page(self, page):
        if "/Group" in page.obj and "/CS" in page.obj.Group:
            page.obj.Group.CS = self.colourspace(page.obj.Group.CS)
        if "/Resources" not in page.obj:
            page.obj.Resources = Dictionary()
        self.resources(page.obj.Resources)
        self.content(page)


def make_print_ready(path):
    """Changes the PDF at path in place; returns the number of greys made true grey."""
    path = Path(path)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        fixer = Fixer(pdf)
        for page in pdf.pages:
            fixer.page(page)
        pdf.save(path)
    return fixer.greys


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for name in argv:
        n = make_print_ready(name)
        print(f"{name}: RGB in sRGB; {n} grey colours made true grey")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
