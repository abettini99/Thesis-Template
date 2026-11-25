"""Check a PDF with PAC (PDF Accessibility Checker, axes4) and write what it finds.

    python run_pac.py <PAC folder> <file.pdf> <output folder>

PAC is a Windows program without a command line, so this drives its window through UI Automation
(what screen readers use), finding every control by its ID rather than by screen position. It opens
the PDF through PAC's own file dialog, accepts PAC's warning that PDF 2.0 is not fully supported
(PAC checks PDF/UA-1, which is PDF 1.7), waits for the verdict and writes to the output folder:

  pac-report.pdf   PAC's own report (one page: the verdict per checkpoint)
  pac-summary.md   every tab (PDF/UA, WCAG, Quality, AI) and, for each failing check, PAC's messages
  pac-*.png        screenshots, for when something goes wrong

Run by .github/workflows/pac.yml on a Windows runner.
"""

import sys
import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Application, keyboard

pac_dir, pdf, out = Path(sys.argv[1]), Path(sys.argv[2]).resolve(), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)


def shot(tag):
    ImageGrab.grab(all_screens=True).save(out / f"pac-{tag}.png")


def value(ctrl):
    try:
        return ctrl.iface_value.CurrentValue
    except Exception:
        return ""


# --- the results tables ---------------------------------------------------------------------------


def cell(item, column):
    """A row's cell in this column ("Checkpoint", "Passed", ...): its value and the cell itself."""
    for c in item.children(control_type="DataItem"):
        if c.window_text().startswith(column + " row"):
            return value(c), c
    return "", None


def table(win):
    """The checkpoint table of the tab shown: (checkpoint, passed, warned, failed) per row."""
    rows = []
    for t in win.wrapper_object().descendants(control_type="TreeItem"):
        name, c = cell(t, "Checkpoint")
        if c is not None:
            rows.append((name, cell(t, "Passed")[0], cell(t, "Warned")[0], cell(t, "Failed")[0]))
    return rows


def verdict(win):
    for c in win.wrapper_object().descendants(control_type="Text"):
        if c.window_text().startswith("This PDF file is"):
            return c.window_text()
    return ""


# --- the detail view: a tree of checks, longer than the window ------------------------------------


def detail_rows(dw):
    rows = []
    for t in dw.descendants(control_type="TreeItem"):
        name, c = cell(t, "Checkpoint")
        if c is not None:
            rows.append(
                dict(
                    name=name,
                    cell=c,
                    left=c.rectangle().left,
                    passed=cell(t, "Passed")[0],
                    warning=cell(t, "Warning")[0],
                    error=cell(t, "Error")[0],
                )
            )
    base = min((r["left"] for r in rows), default=0)
    for r in rows:
        r["depth"] = (r["left"] - base) // 24
    return rows


def find(dw, name, depth):
    """The row with this name and depth, scrolling (Home, then Page Down) until it is in view."""
    rows = []
    for attempt in range(14):
        rows = detail_rows(dw)
        for k, r in enumerate(rows):
            if r["name"] == name and r["depth"] == depth:
                return k, rows
        if not rows:
            break
        rows[0]["cell"].click_input()
        keyboard.send_keys("{HOME}" if attempt == 0 else "{PGDN}")
        time.sleep(0.8)
    return None, rows


def has_findings(r):
    return r["error"] not in ("", "-", "0") or r["warning"] not in ("", "-", "0")


def visit(dw, name, depth, leaf_depth, lines):
    """Open a row, list its children (paging down), recurse into those with findings, close it."""
    k, rows = find(dw, name, depth)
    if k is None:
        lines.append(f"{'  ' * depth}- {name}: (not found in the tree)")
        return
    r = rows[k]
    counts = f"passed {r['passed']}, warnings {r['warning']}, errors {r['error']}"
    lines.append(f"{'  ' * depth}- **{name}** ({counts})")
    r["cell"].click_input()
    keyboard.send_keys("{RIGHT}")
    time.sleep(1.5)
    children = {}
    for _ in range(8):
        k, rows = find(dw, name, depth) if not children else (-1, detail_rows(dw))
        if k is None:
            break
        more = False
        for x in rows[k + 1 :]:
            if x["depth"] <= depth and children:
                break
            if x["depth"] == depth + 1 and x["name"] not in children:
                children[x["name"]] = x
                more = True
        if not more or len(children) > 40:
            break
        rows[-1]["cell"].click_input()
        keyboard.send_keys("{PGDN}")
        time.sleep(0.8)
    counted = [c for c in children.values() if c["passed"] or c["warning"] or c["error"]]
    if depth >= leaf_depth or not counted:  # PAC's messages, one row per object: the distinct ones
        for msg in list(children)[:12]:
            lines.append(f"{'  ' * (depth + 1)}- {' '.join(msg.split())}")
    else:
        for c in counted:
            if has_findings(c):
                visit(dw, c["name"], depth + 1, leaf_depth, lines)
    k, rows = find(dw, name, depth)
    if k is not None:
        rows[k]["cell"].click_input()
        keyboard.send_keys("{LEFT}")
        time.sleep(1)


# --- the run: each step on its own, so a report is written whatever fails ------------------------

problems = []  # (step, what went wrong); listed in the summary
state = {"app": None, "win": None}


def step(name, func):
    """Run one step; on failure note it, take a screenshot, and go on with the next."""
    try:
        return func()
    except Exception as e:
        problems.append((name, f"{type(e).__name__}: {' '.join(str(e).split())[:300]}"))
        try:
            shot(f"failed-{name.split()[0].lower()}")
        except Exception:
            pass
        problems.append((f"{name}, what PAC showed", on_screen()))
        return None


def on_screen():
    """The windows of PAC and the texts in any dialog: what PAC was showing when a step failed."""
    try:
        from pywinauto import Desktop

        parts = []
        for w in Desktop(backend="uia").windows():
            title = w.window_text()
            if not title or title in ("Taskbar", "Program Manager"):
                continue
            texts = []
            for c in w.descendants(control_type="Window") + [w]:
                for t in c.descendants(control_type="Text")[:15]:
                    if t.window_text() and len(t.window_text()) < 300:
                        texts.append(t.window_text())
            parts.append(
                f"window '{title}'" + (": " + " | ".join(dict.fromkeys(texts))[:600] if texts else "")
            )
        return "; ".join(parts) or "no windows"
    except Exception as e:
        return f"(could not read the screen: {e!r})"


def start():
    app = Application(backend="uia").start(str(pac_dir / "PAC.exe"))
    win = app.window(title_re="PAC 20.*")
    win.wait("visible ready", timeout=90)
    state.update(app=app, win=win)
    return win.window_text()


def open_pdf():
    win = state["win"]
    win.child_window(auto_id="openButton", control_type="Button").click_input()
    time.sleep(3)
    keyboard.send_keys(str(pdf).replace(" ", "{SPACE}") + "{ENTER}", with_spaces=True)
    # PAC is built for PDF 1.7 and says so for a PDF 2.0 file: keep its words, press OK
    for _ in range(30):
        time.sleep(2)
        box = win.child_window(title="Unsupported PDF version", control_type="Window")
        if box.exists(timeout=0):
            text = " ".join(
                c.window_text()
                for c in box.wrapper_object().descendants(control_type="Text")
                if c.window_text()
            )
            box.child_window(title="OK", control_type="Button").click_input()
            return text
        if verdict(win):
            return ""
    return ""


def wait_verdict():
    win = state["win"]
    for _ in range(80):
        if verdict(win):
            time.sleep(5)
            shot("checked")
            return verdict(win)
        time.sleep(10)
    raise TimeoutError("PAC gave no verdict within 15 minutes (see pac-checked.png)")


def tabs():
    win = state["win"]
    lines = []
    for tab in ("PDF/UA", "WCAG", "Quality", "AI"):
        try:
            win.child_window(title=tab, control_type="TabItem").click_input()
            time.sleep(3)
            lines += [
                f"### {tab}: {verdict(win)}\n",
                "| Checkpoint | Passed | Warned | Failed |",
                "|---|---|---|---|",
            ]
            lines += [f"| {n} | {p} | {w} | {f} |" for n, p, w, f in table(win)]
            lines.append("")
        except Exception as e:
            problems.append((f"{tab} tab", f"{type(e).__name__}: {e}"))
    return lines


def details():
    win = state["win"]
    win.child_window(title="PDF/UA", control_type="TabItem").click_input()
    win.child_window(auto_id="resultsInDetailPDFUAButton", control_type="Button").click_input()
    time.sleep(8)
    dw = win.child_window(title_re="Results in Detail.*", control_type="Window").wrapper_object()
    try:
        dw.maximize()
    except Exception:
        pass
    time.sleep(2)
    lines = []
    try:
        for top, leaf in (("PDF/UA", 4), ("Quality", 3)):
            visit(dw, top, 0, leaf, lines)
    finally:
        try:
            dw.close()
            time.sleep(2)
        except Exception:
            pass
    return lines


def pdf_report():
    win = state["win"]
    report = (out / "pac-report.pdf").resolve()
    win.child_window(title="PDF/UA", control_type="TabItem").click_input()
    win.child_window(auto_id="pdfUaPdfReportButton", control_type="Button").click_input()
    time.sleep(4)
    keyboard.send_keys(str(report).replace(" ", "{SPACE}") + "{ENTER}", with_spaces=True)
    for _ in range(60):
        time.sleep(3)
        if report.exists() and report.stat().st_size > 0:
            return report
    raise TimeoutError("PAC's PDF report was not written within 3 minutes")


version = step("Start PAC", start)
warning = step("Open the PDF", open_pdf) if version else None
result = step("Wait for the verdict", wait_verdict) if version else None
tab_lines = step("Read the tabs", tabs) if result else None
detail_lines = step("Read the detail view", details) if result else None
report = step("Save PAC's PDF report", pdf_report) if result else None

md = [
    f"## PAC: `{pdf.name}`\n",
    f"{version or 'PAC did not start'}. Standard: PDF/UA-1 (PAC checks PDF 1.7 files).\n",
]
if warning:
    md.append(f"> PAC's warning: {' '.join(warning.split())}\n")
md.append(f"**Verdict:** {result or 'none (see the problems below)'}\n")
if problems:
    md += [
        "### Problems running PAC\n",
        "These steps failed; the screenshots (pac-failed-*.png) show where:\n",
    ]
    md += [f"- **{name}:** {what}" for name, what in problems]
    md.append("")
md += tab_lines or []
if detail_lines:
    md += ["### Details: PAC's messages for each check with errors or warnings\n", *detail_lines, ""]
md.append(f"PAC's own report: {'pac-report.pdf' if report else 'not written'}.\n")
(out / "pac-summary.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))
if state["app"]:
    try:
        state["app"].kill()
    except Exception:
        pass
# a report is always written; the exit code says whether PAC gave a verdict and its report
sys.exit(0 if result and report else 1)
