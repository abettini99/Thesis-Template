"""Step 2 of automating PAC: open the thesis through PAC's own dialog, wait for the check, and record
the window (screenshots and the UI Automation tree), the results table and the report dialog.
"""

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
    try:
        spec.print_control_identifiers(depth=None, filename=str(out / f"{tag}-tree.txt"))
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
win.child_window(title="Open document", control_type="Button").click_input()
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

# wait until the check is done: the results table gets numbers, and the window stops changing
start, last = time.time(), None
while time.time() - start < 600:
    time.sleep(15)
    now = texts(win)
    numbers = sum(1 for r in now if r.split("\t")[1].strip().isdigit())
    say(f"{time.time() - start:.0f} s: {len(now)} controls, {numbers} numbers")
    if numbers >= 6 and now == last:
        break
    last = now
shot("03-checked")
tree(win, "03-checked")
(out / "03-texts.txt").write_text("\n".join(texts(win)), encoding="utf-8")

for tab in ("WCAG", "Quality"):
    try:
        win.child_window(title=tab, control_type="TabItem").click_input()
        time.sleep(3)
        shot(f"04-{tab}")
        (out / f"04-{tab}-texts.txt").write_text("\n".join(texts(win)), encoding="utf-8")
    except Exception as e:
        say("tab", tab, "failed:", repr(e))

# PAC's own report: the "PDF report" button and whatever it asks
try:
    win.child_window(title="PDF/UA", control_type="TabItem").click_input()
    win.child_window(title="PDF report", control_type="Button").click_input()
    time.sleep(5)
    shot("05-report")
    say("windows after PDF report:", [w.window_text() for w in Desktop(backend="uia").windows()])
    tree(app.top_window(), "05-report")
except Exception as e:
    say("report failed:", repr(e))
say("done")
