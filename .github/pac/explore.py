"""Step 2 of automating PAC: open the thesis through PAC's own dialog, wait for the check, and record
the window (screenshots and the UI Automation tree), the results table and the report dialog.
"""

import subprocess
import sys
import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Application, Desktop, keyboard

pac_exe, pdf = Path(sys.argv[1]) / "PAC.exe", Path(sys.argv[2]).resolve()
out = Path("pac-out")
out.mkdir(exist_ok=True)
log = open(out / "steps.txt", "w", encoding="utf-8")


def say(*a):
    print(*a)
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def shot(tag):
    ImageGrab.grab(all_screens=True).save(out / f"{tag}.png")


def tree(spec, tag):
    import contextlib
    import io

    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            spec.print_control_identifiers(depth=None)
        (out / f"{tag}-tree.txt").write_text(buf.getvalue(), encoding="utf-8")
    except Exception as e:
        say("tree failed:", tag, repr(e))


def texts(win):
    """Every control's type, name and value, in order: the results table is in here."""
    rows = []
    for c in win.wrapper_object().descendants():
        try:
            name = c.window_text()
            ctype = c.element_info.control_type
            value = ""
            try:
                value = c.iface_value.CurrentValue
            except Exception:
                pass
            rows.append(f"{ctype}\t{name}\t{value}")
        except Exception as e:
            rows.append(f"?\t{e!r}")
    return rows


app = Application(backend="uia").start(str(pac_exe))
win = app.window(title_re="PAC 20.*")
win.wait("visible ready", timeout=60)
say("PAC window:", win.window_text())
shot("01-start")
tree(win, "01-start")

# Open document -> the Windows file dialog -> the path -> Enter
win.child_window(auto_id="openButton", control_type="Button").click_input()
time.sleep(3)
shot("02-dialog")
dialogs = [w for w in Desktop(backend="uia").windows() if w.process_id() == app.process]
say("windows of PAC after the click:", [w.window_text() for w in dialogs])
dlg = app.window(control_type="Window", found_index=0).child_window(control_type="Window", found_index=0)
try:
    dlg.wait("visible", timeout=20)
    tree(dlg, "02-dialog")
    name_box = dlg.child_window(auto_id="1148", control_type="Edit")  # "File name:" in the common dialog
    name_box.set_edit_text(str(pdf))
    time.sleep(1)
    keyboard.send_keys("{ENTER}")
except Exception as e:
    say("dialog by tree failed:", repr(e), "- typing blind")
    keyboard.send_keys(str(pdf).replace(" ", "{SPACE}") + "{ENTER}", with_spaces=True)
say("path entered")

# PAC warns that PDF 2.0 is not fully supported (it is built for PDF 1.7): note the text, press OK
for _ in range(30):
    time.sleep(2)
    box = win.child_window(title="Unsupported PDF version", control_type="Window")  # (inside the main window)
    if box.exists(timeout=0):
        say("PAC says:", " | ".join(t for t in box.wrapper_object().texts() if t))
        for c in box.wrapper_object().descendants():
            if c.window_text():
                say("   ", c.element_info.control_type, c.window_text())
        box.child_window(title="OK", control_type="Button").click_input()
        say("pressed OK")
        break

# wait until the check is done: the results table gets numbers, and the window stops changing
start, last = time.time(), None
while time.time() - start < 600:
    time.sleep(15)
    now = texts(win)
    numbers = sum(1 for r in now if r.split("\t")[1].strip().isdigit())
    say(f"{time.time() - start:.0f} s: {len(now)} controls, {numbers} numbers")
    if any("This PDF file is" in r for r in now) and now == last:
        break
    last = now
shot("03-checked")
tree(win, "03-checked")
(out / "03-texts.txt").write_text("\n".join(texts(win)), encoding="utf-8")

for tab in ("WCAG", "Quality", "AI"):
    try:
        win.child_window(title=tab, control_type="TabItem").click_input()
        time.sleep(3)
        shot(f"04-{tab}")
        (out / f"04-{tab}-texts.txt").write_text("\n".join(texts(win)), encoding="utf-8")
    except Exception as e:
        say("tab", tab, "failed:", repr(e))

# PAC's own report: the "PDF report" button opens a save dialog with the file name selected
report = (out / "pac-report.pdf").resolve()
try:
    win.child_window(title="PDF/UA", control_type="TabItem").click_input()
    win.child_window(auto_id="pdfUaPdfReportButton", control_type="Button").click_input()
    time.sleep(4)
    shot("05-report-dialog")
    keyboard.send_keys(str(report).replace(" ", "{SPACE}") + "{ENTER}", with_spaces=True)
    for _ in range(60):
        time.sleep(5)
        if report.exists() and report.stat().st_size > 0:
            break
    say("PDF report:", report.exists() and report.stat().st_size, "bytes")
    shot("05-report-saved")
except Exception as e:
    say("report failed:", repr(e))


def expand_all(w):
    """Open every node of the tree views, so their texts can be read."""
    for _ in range(6):
        opened = 0
        for c in w.descendants(control_type="TreeItem"):
            try:
                if c.iface_expand_collapse.CurrentExpandCollapseState == 0:  # collapsed
                    c.iface_expand_collapse.Expand()
                    opened += 1
            except Exception:
                pass
        if not opened:
            break


# the detail view: PAC writes it as an HTML file and opens it in the browser; keep the file
try:
    import os
    import shutil

    t0 = time.time()
    win.child_window(auto_id="resultsInDetailPDFUAButton", control_type="Button").click_input()
    time.sleep(15)
    found = []
    for base in {
        os.environ.get("TEMP"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("APPDATA"),
        str(Path.home() / "Documents"),
        str(Path.home()),
        str(Path.cwd()),
    }:
        if not base or not Path(base).exists():
            continue
        for f in Path(base).rglob("*"):
            try:
                if (
                    f.is_file()
                    and "\\Edge\\" not in str(f)
                    and "\\Microsoft\\" not in str(f)
                    and f.stat().st_mtime > t0 - 5
                ):
                    found.append(f)
            except Exception:
                pass
    say("files written by the detail view:", [str(f) for f in found][:60])
    for w in Desktop(backend="uia").windows():
        if "Edge" in w.window_text() or w.class_name().startswith("Chrome"):
            say("browser window:", w.window_text())
            for e in w.descendants(control_type="Edit"):
                try:
                    say("   address:", e.window_text(), e.iface_value.CurrentValue)
                except Exception:
                    pass
    keep = sorted({f for f in found if f.suffix.lower() in (".html", ".htm", ".json", ".xml", ".tmp")})
    for n, f in enumerate(keep[:20]):
        shutil.copy(f, out / f"detail-{n}{f.suffix}")
        say("kept", f, f.stat().st_size, "bytes")
    subprocess.run(["taskkill", "/IM", "msedge.exe", "/F"], capture_output=True)
except Exception as e:
    say("detail failed:", repr(e))
say("done")
