#!/usr/bin/env python3
"""
mtpro2_unicode.py: prepare MathTime Professional 2 (Complete or Lite) for this template.

Looks in the template's main folder (the parent of this tools folder) for an
MTPro2 installation: the zip from PCTeX (mtp2fonts.zip), mtp2lite.zip from
CTAN, or either one unpacked. It writes a flat copy into the Fonts folder in
which every Type 1 font has Unicode glyph names (e.g. "ogonek" -> "uni03B1" for
alpha), so maths copied from the PDF comes out as the right characters and the
PDF/A-2u check finds a Unicode value for every glyph. Only glyph *names*
change: outlines, hints, metrics and the .tfm files are untouched, so the
typeset result is identical. Variants (sizes, \\xl..\\XXXL, bold, heavy,
holey roman, \\altC, swash z, delimiter pieces) copy as the same character as
their regular form.

Usage (from the template's main folder):
    python3 tools/mtpro2_unicode.py              # main folder -> Fonts/
    python3 tools/mtpro2_unicode.py SOURCE       # a specific folder or zip

The class then finds Fonts/mtpro2.sty and loads MathTime with all its macros.
Needs only Python 3.8+ (standard library) and mtpro2_unicode_map.json next to
this script; the table holds font/slot -> Unicode pairs and no font data.

LICENCE: the MathTime fonts are licensed to you alone. The originals and the
files this script writes must never be committed to a public repository or
shared (the template's .gitignore blocks them); embedding them in your PDF is
allowed.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "Fonts"
MAP_FILE = HERE / "mtpro2_unicode_map.json"
SKIP_DIRS = {"Fonts", "tools", ".git", ".github"}
SUPPORT = {".tfm", ".fd", ".sty"}
GENERATED = {".pfb", ".tfm", ".fd", ".sty", ".map", ".tex", ".txt"}
EEXEC_KEY = 55665


# --- reading an installation: a folder tree or a zip ------------------------

class Source:
    """The files of one MTPro2 installation, by lower-case base name."""

    def __init__(self, label: str):
        self.label, self.files = label, {}

    def add(self, name: str, read):
        base = name.replace("\\", "/").rsplit("/", 1)[-1]
        if base and base.lower() not in self.files:
            self.files[base.lower()] = (base, read)

    @property
    def pfbs(self):
        return sorted(k for k in self.files if k.endswith(".pfb"))

    @property
    def edition(self):
        return "Complete" if len(self.pfbs) > 20 else "Lite"


def from_zip(path: Path) -> Source:
    src = Source(path.name)
    data = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if not info.is_dir():
                src.add(info.filename, lambda n=info.filename: zipfile.ZipFile(io.BytesIO(data)).read(n))
    return src


def from_dir(path: Path) -> Source:
    try:
        label = str(path.relative_to(ROOT))
    except ValueError:
        label = str(path)
    src = Source(label)
    for p in sorted(path.rglob("*")):
        if p.is_file():
            src.add(p.name, p.read_bytes)
    return src


def find_sources(where: Path) -> list[Source]:
    """Every folder holding mtpro2.sty, and every zip containing it, below `where`."""
    if where.is_file():
        return [from_zip(where)]
    found = []
    for p in sorted(where.iterdir()):
        if p.name in SKIP_DIRS or p.name.startswith("."):
            continue
        if p.is_dir() and any(p.rglob("mtpro2.sty")):
            found.append(from_dir(p))
        elif p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    if any(n.endswith("mtpro2.sty") for n in z.namelist()):
                        found.append(from_zip(p))
            except zipfile.BadZipFile:
                pass
    return [s for s in found if s.pfbs]


# --- Type 1 / PFB plumbing -------------------------------------------------

def read_pfb(data: bytes, name: str) -> tuple[bytes, bytes, bytes]:
    """Return the (cleartext, encrypted, trailer) segments of a PFB file."""
    parts, order, pos = {1: [], 2: []}, [], 0
    while pos < len(data):
        if data[pos] != 0x80:
            raise ValueError(f"{name}: not a PFB file")
        kind = data[pos + 1]
        if kind == 3:
            break
        (length,) = struct.unpack("<I", data[pos + 2:pos + 6])
        order.append(kind)
        parts[kind].append(data[pos + 6:pos + 6 + length])
        pos += 6 + length
    first_bin = order.index(2)
    return (b"".join(parts[1][:first_bin]), b"".join(parts[2]),
            b"".join(parts[1][first_bin:]))


def pfb_bytes(clear: bytes, enc: bytes, trailer: bytes) -> bytes:
    def seg(kind: int, chunk: bytes) -> bytes:
        return bytes([0x80, kind]) + struct.pack("<I", len(chunk)) + chunk
    return seg(1, clear) + seg(2, enc) + seg(1, trailer) + b"\x80\x03"


def eexec(data: bytes, decrypt: bool, r: int = EEXEC_KEY) -> bytes:
    out = bytearray()
    for c in data:
        p = c ^ (r >> 8)
        out.append(p)
        r = (((c if decrypt else p) + r) * 52845 + 22719) & 0xFFFF
    return bytes(out)


NAME = rb"[^\s/\[\]{}()<>%]+"
ENC_ENTRY = re.compile(rb"dup\s+(\d+)\s*/(" + NAME + rb")\s+put")
CS_ENTRY = re.compile(rb"\s*/(" + NAME + rb")\s+(\d+)\s+(\S+)\s")
CS_END = re.compile(rb"\s*(?:ND|\|-|noaccess\s+def)")
CS_NAMES = re.compile(rb"/(" + NAME + rb")\s+\d+\s+(?:RD|-\|)\s")


def rename_charstrings(plain: bytes, ren: dict[bytes, bytes]) -> bytes:
    """Rename glyphs in the /CharStrings dictionary, stepping over the binary data."""
    pos = plain.find(b"begin", plain.find(b"/CharStrings")) + len(b"begin")
    out = [plain[:pos]]
    while True:
        m = CS_ENTRY.match(plain, pos)
        if not m:
            break
        end = CS_END.match(plain, m.end() + int(m.group(2)))
        if not end:
            raise ValueError(f"malformed CharStrings entry for /{m.group(1).decode()}")
        out.append(plain[pos:m.start(1)] + ren.get(m.group(1), m.group(1))
                   + plain[m.end(1):end.end()])
        pos = end.end()
    out.append(plain[pos:])
    return b"".join(out)


def convert_font(data: bytes, font: str, slots: dict[str, str],
                 suffixed: dict[str, str]) -> tuple[bytes, int]:
    clear, enc, trailer = read_pfb(data, font)
    plain = eexec(enc, decrypt=True)
    encoding = {int(n): g for n, g in ENC_ENTRY.findall(clear)}
    cs_names = set(CS_NAMES.findall(plain[plain.find(b"/CharStrings"):]))

    used, ren, count, mapped = set(cs_names), {}, Counter(), 0
    for slot in sorted(encoding):
        old = encoding[slot]
        if old in ren or old == b".notdef" or old not in cs_names:
            continue
        hexcode = slots.get(str(slot))
        if hexcode:
            base = ("uni" if len(hexcode) == 4 else "u") + hexcode
            new = base
            while new.encode() in used:
                count[base] += 1
                new = f"{base}.v{count[base]}"
            if new != base:
                suffixed[new] = hexcode
            mapped += 1
        else:
            new = f"{font}.s{slot}"   # no Unicode meaning (e.g. a spacer): neutral name
        used.discard(old)
        used.add(new.encode())
        ren[old] = new.encode()

    clear = ENC_ENTRY.sub(lambda m: b"dup " + m.group(1) + b"/"
                          + ren.get(m.group(2), m.group(2)) + b" put", clear)
    plain = rename_charstrings(plain, ren)
    # Self-check: the renamed CharStrings must be complete before anything is written.
    new_cs = set(CS_NAMES.findall(plain[plain.find(b"/CharStrings"):]))
    missing = [g for g in ren.values() if g not in new_cs]
    if missing or len(new_cs) != len(cs_names):
        raise RuntimeError(f"{font}: renaming check failed ({len(missing)} glyphs missing)")
    return pfb_bytes(clear, eexec(plain, decrypt=False), trailer), mapped


def tounicode_tex(suffixed: dict[str, str]) -> str:
    lines = [
        "% mtpro2-glyphtounicode.tex: generated by tools/mtpro2_unicode.py. Do not commit.",
        "% Plain uniXXXX names are understood automatically; this file turns on ToUnicode",
        "% generation and maps the suffixed variant names (.v1, .v2, ...).",
        r"\ifdefined\pdfextension",
        r"  \protected\def\MTPgtu#1#2{\pdfextension glyphtounicode{#1}{#2}}",
        r"  \pdfvariable gentounicode=1",
        r"\else",
        r"  \def\MTPgtu#1#2{\pdfglyphtounicode{#1}{#2}}",
        r"  \pdfgentounicode=1",
        r"\fi",
    ]
    lines += [rf"\MTPgtu{{{n}}}{{{u}}}" for n, u in sorted(suffixed.items())]
    return "\n".join(lines) + "\n"


# --- the pre-commit hook -----------------------------------------------------

def install_hook() -> None:
    """Copy tools/hooks/pre-commit into the clone's .git/hooks (executable), so git refuses commits with
    the converted fonts. A copy, because Overleaf's GitHub synchronisation drops the executable flag of
    the file in tools/hooks. Leaves a different pre-commit hook of your own alone."""
    src, git = ROOT / "tools" / "hooks" / "pre-commit", ROOT / ".git"
    if not src.is_file() or not git.is_dir():           # not a git clone (e.g. an Overleaf download)
        return
    dst = git / "hooks" / "pre-commit"
    new = src.read_bytes()
    if dst.exists():
        old = dst.read_bytes()
        if old == new and dst.stat().st_mode & 0o111:
            return
        if b"MathTime" not in old:
            print(f"note: {dst} is a hook of your own; add the MathTime check from {src} to it")
            return
    dst.parent.mkdir(exist_ok=True)
    dst.write_bytes(new)
    dst.chmod(0o755)
    print(f"Installed the pre-commit hook that keeps the fonts out of git: {dst}")


# --- main ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", type=Path, default=ROOT,
                    help="folder or zip with the MTPro2 files (default: the template's main folder)")
    ap.add_argument("-o", "--output", type=Path, default=OUT,
                    help="folder to write to (default: the template's Fonts folder)")
    args = ap.parse_args(argv)
    out = args.output.resolve()

    table = json.loads(MAP_FILE.read_text())
    sources = find_sources(args.source.resolve())
    if not sources:
        sys.exit(f"No MathTime Professional 2 installation found in {args.source}.\n"
                 "Put mtp2fonts.zip (Complete) or mtp2lite.zip (Lite), or the unpacked folder, "
                 "in the template's main folder and run again.")
    src = max(sources, key=lambda s: len(s.pfbs))     # Complete wins over Lite
    print(f"MathTime Professional 2 {src.edition}: {src.label} ({len(src.pfbs)} fonts)")
    for other in sources:
        if other is not src:
            print(f"  (ignoring {other.label})")

    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():                          # drop a previous run (other edition)
        if old.is_file() and old.suffix.lower() in GENERATED and old.name != "README.md":
            old.unlink()

    suffixed, total = {}, 0
    for key in src.pfbs:
        name, read = src.files[key]
        font = Path(name).stem.lower()
        data, mapped = convert_font(read(), font, table.get(font, {}), suffixed)
        (out / name).write_bytes(data)
        total += mapped

    copied = 0
    for key, (name, read) in sorted(src.files.items()):
        suffix = Path(key).suffix
        if suffix in SUPPORT or key == "mtpro2.map" or key.startswith("eula"):
            (out / name).write_bytes(read())
            copied += 1
    (out / "mtpro2-glyphtounicode.tex").write_text(tounicode_tex(suffixed), encoding="ascii")

    for need in ("mtpro2.sty", "mtpro2.map"):
        if need not in src.files:
            print(f"warning: {need} not found in {src.label}")
    print(f"{len(src.pfbs)} fonts converted ({total} glyphs mapped), {copied} files copied -> {out}")
    print("Licence: keep these files private. Never commit or share them; the .gitignore blocks them.")
    install_hook()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
