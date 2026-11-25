#!/usr/bin/env python3
"""
check_links.py: check that the DOIs and web addresses in the thesis still lead somewhere.

    python3 tools/check_links.py                    # references.bib and the chapters
    python3 tools/check_links.py other.bib chapters/01Introduction.tex

It reads the doi and url fields of the .bib files and every \\url{...} and \\href{...} in the .tex
files, and checks:

  DOIs   registered at doi.org (asked through doi.org's own handle service, so publishers that
         turn away scripts do not matter); the template's placeholders (10.xxxx/0000000) are skipped
  URLs   answer with a page (status below 400); "403 Forbidden" and "429 Too many requests" are
         only warnings, because many publishers refuse scripts but serve readers

The exit code is 1 if a DOI is not registered or an address is gone (404, 410, no such host),
0 otherwise. Needs only Python 3.9+ and an internet connection.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import ROOT, Report, parser

UA = "Mozilla/5.0 (thesis link check; +https://github.com/abettini99/tudelft-dissertation-template)"
PLACEHOLDER = re.compile(r"/(zenodo\.)?0+$")
FIELD = re.compile(r"\b(doi|url)\s*=\s*[{\"]\s*([^}\"]+?)\s*[}\"]", re.I)
TEX_URL = re.compile(r"\\(?:url|href)\{([^}]+)\}")


def collect(files: list[Path]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """DOIs and URLs, each with the places they come from."""
    dois: dict[str, list[str]] = {}
    urls: dict[str, list[str]] = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
        if f.suffix == ".bib":
            for m in FIELD.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                kind, value = m.group(1).lower(), m.group(2).strip()
                if kind == "doi":
                    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value, flags=re.I)
                    dois.setdefault(doi, []).append(f"{rel}:{line}")
                else:
                    urls.setdefault(value, []).append(f"{rel}:{line}")
        else:
            for m in TEX_URL.finditer(re.sub(r"(?<!\\)%.*", "", text)):  # (not in comments)
                line = text.count("\n", 0, m.start()) + 1
                if m.group(1).startswith(("http://", "https://")):
                    urls.setdefault(m.group(1), []).append(f"{rel}:{line}")
    return dois, urls


def check_doi(doi: str) -> tuple[str, str]:
    """('ok' | 'fail' | 'warn', message)"""
    api = "https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/")
    try:
        req = urllib.request.Request(api, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            code = json.load(r).get("responseCode")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "fail", "not registered at doi.org"
        return "warn", f"doi.org answered HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        return "warn", f"doi.org not reachable ({e})"
    return ("ok", "") if code == 1 else ("fail", f"not registered at doi.org (code {code})")


def check_url(url: str) -> tuple[str, str]:
    for method in ("HEAD", "GET"):  # some servers refuse HEAD
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=30):
                return "ok", ""
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (400, 403, 405, 406, 429, 501):
                continue
            if e.code in (404, 410):
                return "fail", f"HTTP {e.code} (gone)"
            if e.code in (401, 403, 429):
                return "warn", f"HTTP {e.code} (the site refuses scripts; check it in a browser)"
            return ("fail" if e.code < 500 else "warn"), f"HTTP {e.code}"
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.gaierror):
                return "fail", "no such host"
            return "warn", f"not reachable ({e.reason})"
        except (TimeoutError, socket.timeout):
            return "warn", "timed out"
    return "warn", "no answer"


def main(argv=None) -> int:
    ap = parser(__doc__)
    ap.add_argument("files", nargs="*", type=Path, help="default: references.bib and chapters/*.tex")
    args = ap.parse_args(argv)
    files = [f.resolve() for f in args.files] or [
        ROOT / "references.bib",
        *sorted((ROOT / "chapters").glob("*.tex")),
    ]
    dois, urls = collect([f for f in files if f.exists()])
    skipped = [d for d in dois if PLACEHOLDER.search(d)]
    for d in skipped:
        del dois[d]
    # a URL that is just the DOI again: the DOI check covers it
    for u in [u for u in urls if re.sub(r"^https?://(dx\.)?doi\.org/", "", u, flags=re.I) in dois]:
        del urls[u]

    r = Report()
    with ThreadPoolExecutor(8) as pool:
        doi_res = dict(zip(dois, pool.map(check_doi, dois)))
        url_res = dict(zip(urls, pool.map(check_url, urls)))
    for title, res, where in (("DOIs", doi_res, dois), ("Web addresses", url_res, urls)):
        r.section(f"{title} ({len(res)})")
        for link, (kind, msg) in sorted(res.items()):
            places = ", ".join(where[link])
            if kind == "fail":
                r.fail(f"{link}: {msg}", [places])
            elif kind == "warn":
                r.warn(f"{link}: {msg}", [places])
        bad = sum(k != "ok" for k, _ in res.values())
        if not bad:
            r.ok(f"all {len(res)} lead somewhere")
    if skipped:
        print(f"\n  note  placeholders skipped: {', '.join(skipped)}")
    print(f"\n{r.errors} broken link(s), {r.warnings} to check by hand.")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
