# Runtime consumers pin the published image digest, not this mutable build tag.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

LABEL org.opencontainers.image.source="https://github.com/metronforge/affine-bundle-solver"
LABEL org.opencontainers.image.description="Offline TeX toolchain for the affine-bundle-solver manuscript"

# Keep the existing pdfLaTeX/BibTeX toolchain. The current preamble does not
# require texlive-science (which also pulled in the large Greek language set).
# Package versions are recorded inside every published image; consumers use
# its immutable digest. A rebuild is an explicit toolchain update, not a
# promise of bit-identical apt resolution.
RUN apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 \
       -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       texlive-latex-base texlive-latex-recommended texlive-latex-extra \
       texlive-fonts-recommended lmodern \
    && mkdir -p /usr/local/share/abs-texlive \
    && dpkg-query -W > /usr/local/share/abs-texlive/packages.tsv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY build-manuscript /usr/local/bin/abs-build-manuscript
RUN chmod 0755 /usr/local/bin/abs-build-manuscript
ENV BIBTEX=bibtex
WORKDIR /work
CMD ["abs-build-manuscript"]
