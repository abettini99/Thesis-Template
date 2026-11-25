"""Step 1 of automating PAC: start it with the thesis, and record what its window shows.

Takes screenshots and writes the window's UI Automation tree (what a screen reader sees), so the
next step can find the controls and the results by name instead of by screen position.
"""

import subprocess
import sys
import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop

pac_dir, pdf = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
out = Path("pac-out")
out.mkdir(exist_ok=True)
exes = sorted(pac_dir.rglob("*.exe"))
(out / "files.txt").write_text("\n".join(str(p) for p in sorted(pac_dir.rglob("*"))))
exe = next((p for p in exes if p.stem.lower() in ("pac", "pac2026", "pac 2026")), None) or next(
    p for p in exes if "pac" in p.stem.lower() and "unins" not in p.stem.lower()
)
print("starting", exe, "with", pdf)
proc = subprocess.Popen([str(exe), str(pdf)])


def snapshot(tag):
    ImageGrab.grab(all_screens=True).save(out / f"{tag}.png")
    with open(out / f"{tag}-windows.txt", "w", encoding="utf-8") as f:
        for w in Desktop(backend="uia").windows():
            try:
                f.write(f"=== window: {w.window_text()!r} pid={w.process_id()} class={w.class_name()}\n")
                if w.process_id() == proc.pid or "PAC" in w.window_text():
                    w.print_control_identifiers(depth=None, filename=str(out / f"{tag}-tree.txt"))
            except Exception as e:  # (a window may close while we look)
                f.write(f"   ({e})\n")


for t in (10, 30, 60, 120, 240):
    time.sleep(t - (0 if t == 10 else {30: 10, 60: 30, 120: 60, 240: 120}[t]))
    snapshot(f"t{t:03d}")
    print("snapshot at", t, "s; running:", proc.poll() is None)
