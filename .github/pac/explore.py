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


# the detail view: a window inside PAC with a tree of checks; open every failing row, read them all
def cell(item, column):
    for c in item.children(control_type="DataItem"):
        if c.window_text().startswith(column + " row"):
            try:
                return c.iface_value.CurrentValue, c
            except Exception:
                return "", c
    return "", None


def detail_rows(dw):
    rows = []
    for t in dw.descendants(control_type="TreeItem"):
        name, c = cell(t, "Checkpoint")
        if c is None:
            continue
        rows.append(
            dict(
                item=t,
                cell=c,
                name=name,
                left=c.rectangle().left,
                top=c.rectangle().top,
                passed=cell(t, "Passed")[0],
                warning=cell(t, "Warning")[0],
                error=cell(t, "Error")[0],
            )
        )
    return rows


try:
    win.child_window(title="PDF/UA", control_type="TabItem").click_input()
    win.child_window(auto_id="resultsInDetailPDFUAButton", control_type="Button").click_input()
    time.sleep(8)
    dw = win.child_window(title_re="Results in Detail.*", control_type="Window").wrapper_object()
    try:
        dw.maximize()
    except Exception:
        keyboard.send_keys("{VK_LWIN down}{UP}{VK_LWIN up}")
    time.sleep(2)
    opened = set()
    for _ in range(80):
        rows = detail_rows(dw)
        base = min(r["left"] for r in rows)
        todo = [
            r
            for r in rows
            if r["error"] not in ("", "-", "0")
            and (r["name"], r["top"] // 1) not in opened
            and r["name"] not in opened
            and (r["left"] - base) <= 4 * 24  # (not down to every single object)
        ]
        if not todo:
            break
        r = todo[0]
        opened.add(r["name"])
        r["cell"].click_input()
        keyboard.send_keys("{RIGHT}")
        time.sleep(1.5)
    rows = detail_rows(dw)
    base = min(r["left"] for r in rows)
    lines = [
        f"{'  ' * ((r['left'] - base) // 24)}{r['name']}\t{r['passed']}\t{r['warning']}\t{r['error']}"
        for r in rows
    ]
    (out / "06-detail-rows.txt").write_text("\n".join(lines), encoding="utf-8")
    say("detail rows:", len(rows), "opened:", len(opened))
    shot("06-detail")
    # the panels beside the tree describe the selected row: read them for the failing leaves
    notes = []
    for r in [r for r in rows if r["error"] not in ("", "-", "0")][-25:]:
        try:
            r["cell"].click_input()
            time.sleep(1)
            panel = [
                c.window_text() or getattr(c, "iface_value", None) and c.iface_value.CurrentValue
                for c in dw.descendants()
                if c.element_info.control_type in ("Text", "Edit", "Document")
            ]
            notes.append(f"== {r['name']} ({r['error']} errors)\n" + "\n".join(str(x) for x in panel if x))
        except Exception as e:
            notes.append(f"== {r['name']}: {e!r}")
    (out / "06-detail-notes.txt").write_text("\n\n".join(notes), encoding="utf-8")
    shot("06-detail-selected")
    dw.close()
    time.sleep(2)
except Exception as e:
    say("detail failed:", repr(e))

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


subprocess.run(["taskkill", "/IM", "msedge.exe", "/F"], capture_output=True)
say("done")
