"""Which PAC to install: the pinned version, or the newest one axes4 offers if the pinned one is gone.

    python pac_version.py <pinned MSI address>

Reads axes4's download page for the PAC installers it offers (PAC_Setup.<version>.msi), checks that
the pinned one can still be downloaded, and writes to $GITHUB_OUTPUT:

  url      the installer to use: the pinned one, or the newest if the pinned one is gone
  version  its version
  note     one line for the report: up to date, a newer PAC is available, or the pinned one is gone

Never fails on a newer version: that is news for the report, not an error.
"""

import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PAGE = "https://pac.pdf-accessibility.org/en/download"
pinned = sys.argv[1]


def version(url):
    m = re.search(r"PAC_Setup\.(\d+(?:\.\d+)+)\.msi", url)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def show(v):
    return ".".join(map(str, v)) or "?"


def reachable(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


offered = []
try:
    req = urllib.request.Request(PAGE, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    for href in re.findall(r'href="([^"]*PAC_Setup\.[\d.]+\.msi)"', html):
        offered.append(urllib.parse.urljoin(PAGE, href))
except Exception as e:  # the page itself may change: then only the pinned installer is known
    print("could not read the download page:", e)

newest = max(offered, key=version, default=None)
pinned_ok = reachable(pinned)
if pinned_ok and (not newest or version(newest) <= version(pinned)):
    use, note = pinned, f"PAC {show(version(pinned))}, the newest axes4 offers."
elif pinned_ok:
    use = pinned
    note = (
        f"PAC {show(version(pinned))} (pinned). axes4 now offers PAC {show(version(newest))}: "
        f"update PAC_MSI in .github/workflows/pac.yml to {newest}"
    )
elif newest:
    use = newest
    note = (
        f"The pinned PAC {show(version(pinned))} can no longer be downloaded; used PAC {show(version(newest))}. "
        f"Update PAC_MSI in .github/workflows/pac.yml to {newest}"
    )
else:
    sys.exit(f"Neither the pinned PAC installer nor axes4's download page could be read ({pinned})")

print(note)
with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
    f.write(f"url={use}\nversion={show(version(use))}\nnote={note}\n")
