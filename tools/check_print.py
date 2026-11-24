#!/usr/bin/env python3
"""Check a PDF for the printer: the PDF/X essentials and what printers reject or charge for.

    python3 tools/check_print.py main.pdf          (the print-preparation edition; also cover.pdf)

Reports
  errors    what a printer's preflight rejects: no PDF/X identification or output intent, pages without
            trim or bleed box, RGB not given in sRGB explicitly (device RGB, named by figure file and page,
            even where sRGB is the page's default: a preflight may read it literally), fonts not embedded,
            links or attachments, images below 225 ppi;
  warnings  images below 300 ppi, lines thinner than 0.1 mm (they may not print), small text in "rich
            black" (black made of all four inks: coloured fringes);
  facts     the PDF/X version, the colour profile, the page count, and the pages in colour (printers
            charge per colour page; one stray coloured element makes a page a colour page).
This is not an official PDF/X validator (those are commercial, e.g. Acrobat Pro's preflight): it checks
the rules that matter for a thesis made with this template. Send the file through your printer's own
file check as well; most printers offer one free. Exit status 1 when there are errors. Needs pikepdf and
Pillow (pip install -r requirements.txt).
"""

import re
import sys
from collections import defaultdict

import pikepdf
from pikepdf import Name

MM = 72 / 25.4
HAIRLINE = 0.1 * MM  # pt
PPI_WARN, PPI_ERROR = 300, 225


def mat_mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def scale(m):
    """The mean scale factor of a matrix (for line widths)."""
    return abs(m[0] * m[3] - m[1] * m[2]) ** 0.5


class Report:
    def __init__(self):
        self.errors, self.warnings, self.facts = [], [], []
        self._seen = set()

    def add(self, kind, text):
        if (kind, text) not in self._seen:
            self._seen.add((kind, text))
            getattr(self, kind).append(text)


def is_rgb(cs):
    return cs == Name.DeviceRGB or (
        isinstance(cs, pikepdf.Array)
        and len(cs)
        and cs[0] == Name.Indexed
        and len(cs) > 1
        and cs[1] == Name.DeviceRGB
    )


def is_iccrgb(cs):
    if isinstance(cs, pikepdf.Array) and len(cs) and cs[0] == Name.Indexed:
        cs = cs[1]
    return isinstance(cs, pikepdf.Array) and len(cs) == 2 and cs[0] == Name.ICCBased and cs[1].get("/N") == 3


def image_in_colour(xo):
    """True if an RGB image has visible colour (not just greys)."""
    try:
        im = pikepdf.PdfImage(xo).as_pil_image().convert("RGB")
        im.thumbnail((200, 200))
        hsv = im.convert("HSV")
        sat = hsv.getchannel("S").getextrema()[1]
        return sat > 25
    except Exception:
        return True


def figure_index(folder, skip):
    """The figure PDFs in the project folder, by the digest of their page content: LaTeX copies a placed
    figure's content unchanged, so a figure in the thesis can be traced to its file."""
    import hashlib
    from pathlib import Path

    index = {}
    for f in Path(folder).rglob("*.pdf"):
        if f.resolve() == Path(skip).resolve() or f.stat().st_size > 20_000_000 or ".git" in f.parts:
            continue
        try:
            with pikepdf.open(f) as doc:
                for n, page in enumerate(doc.pages):
                    data = (
                        b"".join(c.read_bytes() for c in page.obj.Contents)
                        if isinstance(page.obj.get("/Contents"), pikepdf.Array)
                        else page.obj.Contents.read_bytes()
                    )
                    rel = str(f.relative_to(folder))
                    index[hashlib.sha1(data).hexdigest()] = rel + (
                        f" (page {n + 1})" if len(doc.pages) > 1 else ""
                    )
        except Exception:
            pass
    return index


class Walker:
    def __init__(self, pdf, report, figures=None):
        self.pdf, self.r = pdf, report
        self.colour_pages = set()
        self.figures = figures or {}
        self.thin = defaultdict(set)  # (figure file, width in mm) -> pages

    def where(self, page, src):
        lab = self.labels[page]
        loc = f"page {page + 1}" + (f" (printed {lab})" if lab and lab != str(page + 1) else "")
        return loc + (f", in {src}" if src else "")

    def run(self):
        self.labels = []
        for p in self.pdf.pages:
            try:
                self.labels.append(str(p.label))
            except Exception:
                self.labels.append("")
        for i, page in enumerate(self.pdf.pages):
            res = page.obj.get("/Resources", pikepdf.Dictionary())
            self.stream(i, page, res, (1, 0, 0, 1, 0, 0), None, default_rgb=self.has_default(res))
        for (src, width), pages in sorted(self.thin.items(), key=lambda kv: min(kv[1])):
            pages = sorted(pages)
            where = ", ".join(str(p + 1) for p in pages[:8]) + (" ..." if len(pages) > 8 else "")
            self.r.add(
                "warnings",
                f"lines thinner than 0.1 mm ({width:.2f} mm) on page{'s' if len(pages) > 1 else ''} "
                f"{where}" + (f", in {src}" if src else ""),
            )

    @staticmethod
    def has_default(res):
        cs = res.get("/ColorSpace") if res is not None else None
        return cs is not None and "/DefaultRGB" in cs and is_iccrgb(cs.DefaultRGB)

    def rgb_unmanaged(self, page, src, what, default_rgb):
        """Device RGB: an error. With sRGB as the page's default it is still sRGB to a reader that applies
        the default, but a preflight may read it literally; without it, it is unmanaged colour."""
        how = "device RGB, sRGB only by default" if default_rgb else "RGB not declared as sRGB"
        self.r.add(
            "errors",
            f"{how} ({what}): {self.where(page, src)}"
            + ("; run tools/print_ready.py on that file" if src else ""),
        )

    def group(self, page, obj, src):
        """A transparency group that blends in device RGB: the colours it mixes are unmanaged."""
        grp = obj.get("/Group") if hasattr(obj, "get") else None
        if isinstance(grp, pikepdf.Dictionary) and is_rgb(grp.get("/CS")):
            self.r.add(
                "warnings",
                f"transparency blended in device RGB (/Group /CS): {self.where(page, src)}"
                + ("; run tools/print_ready.py on that file" if src else ""),
            )

    def stream(self, page, obj, res, ctm, src, default_rgb, depth=0):
        if depth > 12:
            return
        self.group(page, obj.obj if hasattr(obj, "obj") else obj, src)
        try:
            ops = pikepdf.parse_content_stream(obj)
        except Exception as err:
            self.r.add("warnings", f"could not read a content stream ({err}): {self.where(page, src)}")
            return
        stack, gs = [], {"ctm": ctm, "w": 1.0, "fill": ("g", (0,)), "intext": False, "tsize": 10.0}
        cs_res = res.get("/ColorSpace", {}) if res is not None else {}

        def fill_space(name):
            if name in (Name.DeviceRGB,):
                return "rgb"
            if name in (Name.DeviceGray,):
                return "g"
            if name in (Name.DeviceCMYK,):
                return "k"
            c = cs_res.get(name) if isinstance(name, Name) else None
            if c is None and name not in (Name.Pattern,):
                return "missing"
            if c is not None and is_iccrgb(c):
                return "iccrgb"
            if c is not None and c == Name.DeviceRGB:
                return "rgb"
            if c is not None and c == Name.DeviceCMYK:
                return "k"
            if c is not None and c == Name.DeviceGray:
                return "g"
            if isinstance(c, pikepdf.Array) and len(c) == 2 and c[0] == Name.ICCBased:
                return {1: "g", 4: "k"}.get(int(c[1].get("/N", 0)), "other")
            return "other"

        for operands, op in ops:
            o = str(op)
            if o == "q":
                stack.append(dict(gs))
            elif o == "Q":
                if stack:
                    gs = stack.pop()
            elif o == "cm" and len(operands) == 6:
                gs["ctm"] = mat_mul(tuple(float(x) for x in operands), gs["ctm"])
            elif o == "w" and operands:
                gs["w"] = float(operands[0])
            elif o in ("rg", "RG"):
                comps = tuple(float(x) for x in operands)
                self.rgb_unmanaged(page, src, "colour", default_rgb)
                if max(comps) - min(comps) > 0.02:
                    self.colour_pages.add(page)
                if o == "rg":
                    gs["fill"] = ("rgb", comps)
            elif o in ("k", "K"):
                comps = tuple(float(x) for x in operands)
                if max(comps[:3]) > 0.02:
                    self.colour_pages.add(page)
                if o == "k":
                    gs["fill"] = ("k", comps)
            elif o in ("g",) and operands:
                gs["fill"] = ("g", (float(operands[0]),))
            elif o in ("cs", "CS") and operands:
                kind = fill_space(operands[0])
                if kind == "rgb":
                    self.rgb_unmanaged(page, src, "colour space", default_rgb)
                elif kind == "missing":
                    self.r.add(
                        "errors", f"colour space {operands[0]} used but not defined: {self.where(page, src)}"
                    )
                if o == "cs":
                    gs["fill"] = (kind, ())
            elif o in ("sc", "scn", "SC", "SCN") and operands:
                nums = []
                for x in operands:
                    try:
                        nums.append(float(x))
                    except (TypeError, ValueError):
                        pass
                if len(nums) == 3 and max(nums) - min(nums) > 0.02:
                    self.colour_pages.add(page)
                kind_now = gs["fill"][0] if o in ("sc", "scn") else None
                need = {"rgb": 3, "iccrgb": 3, "k": 4, "g": 1}.get(kind_now)
                if need and len(nums) != need and not any(isinstance(x, Name) for x in operands):
                    self.r.add(
                        "errors",
                        f"a colour with {len(nums)} values in a {need}-value colour space: "
                        f"{self.where(page, src)}",
                    )
                if o in ("sc", "scn") and len(nums) == 3:
                    gs["fill"] = (gs["fill"][0], tuple(nums))
                if o in ("scn", "SCN") and isinstance(operands[-1], Name):  # a pattern
                    pat = res.get("/Pattern", {}).get(operands[-1]) if res is not None else None
                    if pat is not None and int(pat.get("/PatternType", 0)) == 2:
                        sh = pat.get("/Shading")
                        if sh is not None and is_rgb(sh.get("/ColorSpace")):
                            self.rgb_unmanaged(page, src, "shading pattern", default_rgb)
                    elif pat is not None and int(pat.get("/PatternType", 0)) == 1:
                        pres = pat.get("/Resources")
                        self.stream(
                            page,
                            pat,
                            pres if pres is not None else res,
                            gs["ctm"],
                            src,
                            self.has_default(pres) if pres is not None else default_rgb,
                            depth + 1,
                        )
            elif o in ("S", "s", "B", "B*", "b", "b*"):
                width = gs["w"] * scale(gs["ctm"])
                if width < HAIRLINE:
                    self.thin[(src, round(width / MM, 2))].add(page)
            elif o == "BT":
                gs["intext"] = True
            elif o == "ET":
                gs["intext"] = False
            elif o == "Tf" and len(operands) == 2:
                gs["tsize"] = float(operands[1])
            elif o in ("Tj", "TJ", "'", '"') and gs["intext"]:
                kind, comps = gs["fill"]
                size = gs["tsize"] * scale(gs["ctm"])
                rich = (kind in ("rgb", "iccrgb") and comps and max(comps) < 0.25) or (
                    kind == "k" and len(comps) == 4 and comps[3] > 0.7 and max(comps[:3]) > 0.1
                )
                if rich and size < 12:
                    self.r.add(
                        "warnings",
                        f"small text in rich black (all four inks): {self.where(page, src)}"
                        + ("; run tools/print_ready.py on that file" if src else ""),
                    )
            elif o == "INLINE IMAGE" and operands:
                cs = getattr(operands[0], "colorspace", None)
                if str(cs) in ("/DeviceRGB", "/RGB"):
                    self.rgb_unmanaged(page, src, "inline image", default_rgb)
            elif o == "sh" and operands:
                sh = res.get("/Shading", {}).get(operands[0]) if res is not None else None
                if sh is not None and is_rgb(sh.get("/ColorSpace")):
                    self.rgb_unmanaged(page, src, "shading", default_rgb)
                if sh is not None and sh.get("/ColorSpace") not in (Name.DeviceGray,):
                    self.colour_pages.add(page)
            elif o == "Do" and operands:
                xo = res.get("/XObject", {}).get(operands[0]) if res is not None else None
                if xo is None:
                    continue
                if xo.get("/Subtype") == Name.Image:
                    self.image(page, src, xo, gs["ctm"], default_rgb)
                elif xo.get("/Subtype") == Name.Form:
                    m = tuple(float(x) for x in xo.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                    xres = xo.get("/Resources")
                    name = src
                    if "/PTEX.PageNumber" in xo:  # a placed PDF figure: which file?
                        import hashlib

                        try:
                            name = self.figures.get(
                                hashlib.sha1(xo.read_bytes()).hexdigest(), "a placed figure"
                            )
                        except Exception:
                            name = "a placed figure"
                    own = xres is not None
                    self.stream(
                        page,
                        xo,
                        xres if own else res,
                        mat_mul(m, gs["ctm"]),
                        name,
                        self.has_default(xres) if own else default_rgb,
                        depth + 1,
                    )

    def image(self, page, src, xo, ctm, default_rgb):
        if xo.get("/ImageMask"):
            return
        cs = xo.get("/ColorSpace")
        if is_rgb(cs):
            if src:
                self.rgb_unmanaged(page, src, "image", default_rgb)
            else:  # a photo placed by LaTeX: a palette PNG, most likely
                self.r.add(
                    "errors",
                    f"photo in device RGB (a palette PNG? save it as an RGB PNG or JPEG): "
                    f"{self.where(page, src)}",
                )
        if is_rgb(cs) or is_iccrgb(cs):
            if image_in_colour(xo):
                self.colour_pages.add(page)
        elif cs == Name.DeviceCMYK:
            self.colour_pages.add(page)
        w, h = int(xo.get("/Width", 0)), int(xo.get("/Height", 0))
        wpt = (ctm[0] ** 2 + ctm[1] ** 2) ** 0.5
        hpt = (ctm[2] ** 2 + ctm[3] ** 2) ** 0.5
        if min(w, h) < 16 or wpt < 1 or hpt < 1:
            return
        ppi = min(w / (wpt / 72), h / (hpt / 72))
        if ppi < PPI_ERROR:
            self.r.add("errors", f"image at {ppi:.0f} ppi (printers ask for 300): {self.where(page, src)}")
        elif ppi < PPI_WARN - 5:
            self.r.add("warnings", f"image at {ppi:.0f} ppi (300 is best): {self.where(page, src)}")


def check(path, folder=None):
    from pathlib import Path

    r = Report()
    pdf = pikepdf.open(path)
    root = pdf.Root
    # identification and output intent
    meta = ""
    if "/Metadata" in root:
        meta = root.Metadata.read_bytes().decode("utf-8", "replace")
    m = re.search(r"GTS_PDFXVersion>\s*([^<\s][^<]*)<", meta) or re.search(r'GTS_PDFXVersion="([^"]+)"', meta)
    version = m.group(1).strip() if m else None
    if not version:
        r.add("errors", "no PDF/X identification (not the print-preparation edition?)")
    else:
        r.add("facts", f"{version}, PDF {pdf.pdf_version}")
        if version.startswith("PDF/X-4") and float(pdf.pdf_version) > 1.6:
            r.add("errors", "PDF/X-4 needs PDF 1.6 or lower")
        if version.startswith("PDF/X-6") and pdf.pdf_version != "2.0":
            r.add("errors", "PDF/X-6 needs PDF 2.0")
    intents = [oi for oi in root.get("/OutputIntents", []) if oi.get("/S") == Name.GTS_PDFX]
    if not intents:
        r.add("errors", "no PDF/X output intent (the colour profile of the press)")
    else:
        oi = intents[0]
        prof = oi.get("/DestOutputProfile")
        if prof is None:
            r.add("errors", "the output intent has no embedded colour profile")
        else:
            data = prof.read_bytes()
            cls, space = data[12:16].decode("latin-1"), data[16:20].decode("latin-1").strip()
            if cls != "prtr":
                r.add("errors", f"the output intent's profile is not a printer profile ({cls})")
            r.add("facts", f"colour profile: {oi.get('/OutputConditionIdentifier', '?')} ({space})")
    # forbidden things
    if pdf.is_encrypted:
        r.add("errors", "the PDF is encrypted")
    names = root.get("/Names", {})
    if "/EmbeddedFiles" in names:
        r.add("errors", "the PDF has attachments (not for the printer)")
    if "/JavaScript" in names or "/AA" in root:
        r.add("errors", "the PDF has JavaScript or automatic actions")
    # pages: boxes and annotations
    nobox = []
    for i, page in enumerate(pdf.pages):
        o = page.obj
        mb = [float(x) for x in o.get("/MediaBox", page.mediabox)]
        tb = o.get("/TrimBox") or o.get("/ArtBox")
        if tb is None:
            nobox.append(i + 1)
            continue
        tb = [float(x) for x in tb]
        bb = [float(x) for x in o.get("/BleedBox", o.get("/CropBox", mb))]
        eps = 0.01
        if not (
            bb[0] <= tb[0] + eps and bb[1] <= tb[1] + eps and bb[2] >= tb[2] - eps and bb[3] >= tb[3] - eps
        ):
            r.add("errors", f"page {i + 1}: the trim box is not inside the bleed box")
        if not (
            mb[0] <= bb[0] + eps and mb[1] <= bb[1] + eps and mb[2] >= bb[2] - eps and mb[3] >= bb[3] - eps
        ):
            r.add("errors", f"page {i + 1}: the bleed box is larger than the page")
        if "/Annots" in o and len(o.Annots):
            r.add("errors", f"page {i + 1}: links or other annotations (none allowed on the printed page)")
    if nobox:
        r.add("errors", f"no trim box on {len(nobox)} pages (first: page {nobox[0]})")
    else:
        tb = [float(x) for x in pdf.pages[0].obj.TrimBox]
        bb = [float(x) for x in pdf.pages[0].obj.get("/BleedBox", tb)]
        r.add(
            "facts",
            f"trimmed page {(tb[2] - tb[0]) / MM:.1f} x {(tb[3] - tb[1]) / MM:.1f} mm, "
            f"bleed {(tb[0] - bb[0]) / MM:.1f} mm",
        )
    # fonts
    for i, page in enumerate(pdf.pages):
        stack = [page.obj.get("/Resources")]
        seen = set()
        while stack:
            res = stack.pop()
            if res is None or res.objgen in seen and res.objgen != (0, 0):
                continue
            seen.add(res.objgen)
            for _, font in res.get("/Font", {}).items():
                sub = font.get("/Subtype")
                fd = font.get("/FontDescriptor")
                if sub == Name.Type0:
                    fd = font.DescendantFonts[0].get("/FontDescriptor")
                if sub == Name.Type3:
                    r.add("warnings", f"bitmap-style (Type 3) font {font.get('/BaseFont', '')}: page {i + 1}")
                    continue
                if fd is None or not any(k in fd for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                    r.add("errors", f"font not embedded: {font.get('/BaseFont', '?')} (page {i + 1})")
            for _, xo in res.get("/XObject", {}).items():
                if xo.get("/Subtype") == Name.Form:
                    stack.append(xo.get("/Resources"))
    # content: colour, images, lines
    w = Walker(pdf, r, figure_index(folder or Path(path).resolve().parent, path))
    w.run()
    n = len(pdf.pages)
    r.add(
        "facts",
        f"{n} pages"
        + ("" if n % 4 == 0 else " (printers print in sheets of 4, 8 or 16 pages and add blank ones: ask)"),
    )
    cp = sorted(w.colour_pages)
    if cp:
        labels = [
            str(i + 1) + (f" ({w.labels[i]})" if w.labels[i] and w.labels[i] != str(i + 1) else "")
            for i in cp
        ]
        r.add("facts", f"{len(cp)} pages in colour (PDF page, printed number): " + ", ".join(labels))
    else:
        r.add("facts", "no pages in colour (black and white throughout)")
    return r


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    status = 0
    for path in argv:
        r = check(path)
        print(f"{path}:")
        for kind, mark in (("facts", "  "), ("errors", "E "), ("warnings", "W ")):
            for line in getattr(r, kind):
                print(f"  {mark}{line}")
        print(f"  {len(r.errors)} errors, {len(r.warnings)} warnings")
        status |= bool(r.errors)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
