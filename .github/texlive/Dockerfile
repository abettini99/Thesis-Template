# TeX Live as Overleaf runs it: TeX Live 2026 installed from the TeX Live repository as it was on
# one day, the day Overleaf took its copy (its LaTeX format is dated 2026-06-26, its newest package
# 2026-06-18). Overleaf does not update its TeX Live afterwards, so neither does this image: its
# repository stays pinned to that day.
#
# Built by .github/workflows/texlive-image.yml and published as
# ghcr.io/<owner>/<repository>/texlive:overleaf-2026, which the build workflow compiles with.
# For a later Overleaf TeX Live: a new image with that year's date (see the workflow).
FROM debian:bookworm-slim

ARG TL_YEAR=2026
ARG TL_DATE=2026/06/26
ENV TL_REPO=https://texlive.info/tlnet-archive/${TL_DATE}/tlnet

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget perl xz-utils fontconfig git \
 && rm -rf /var/lib/apt/lists/*

# scheme-full like Overleaf, without documentation and sources (half the size)
RUN cd /tmp \
 && wget -q "${TL_REPO}/install-tl-unx.tar.gz" \
 && mkdir install-tl && tar -xzf install-tl-unx.tar.gz -C install-tl --strip-components=1 \
 && printf '%s\n' \
      "selected_scheme scheme-full" \
      "TEXDIR /usr/local/texlive/${TL_YEAR}" \
      "TEXMFLOCAL /usr/local/texlive/texmf-local" \
      "TEXMFSYSVAR /usr/local/texlive/${TL_YEAR}/texmf-var" \
      "TEXMFSYSCONFIG /usr/local/texlive/${TL_YEAR}/texmf-config" \
      "binary_x86_64-linux 1" \
      "instopt_adjustpath 0" \
      "tlpdbopt_install_docfiles 0" \
      "tlpdbopt_install_srcfiles 0" \
      "tlpdbopt_autobackup 0" \
      > profile \
 && ./install-tl/install-tl --profile=profile --repository="${TL_REPO}" \
 && rm -rf /tmp/install-tl /tmp/install-tl-unx.tar.gz /tmp/profile

ENV PATH=/usr/local/texlive/${TL_YEAR}/bin/x86_64-linux:${PATH}

# keep it pinned: tlmgr would otherwise update from the current repository
RUN tlmgr option repository "${TL_REPO}" \
 && luaotfload-tool --update \
 && lualatex --version | head -1 \
 && echo "TeX Live ${TL_YEAR}, repository of ${TL_DATE}" > /usr/local/texlive/SNAPSHOT
