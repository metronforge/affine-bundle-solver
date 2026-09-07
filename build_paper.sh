#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PDFLATEX=${PDFLATEX:-pdflatex}
BIBTEX=${BIBTEX:-bibtex8}
$PDFLATEX -interaction=nonstopmode -halt-on-error paper.tex
$BIBTEX paper
$PDFLATEX -interaction=nonstopmode -halt-on-error paper.tex
$PDFLATEX -interaction=nonstopmode -halt-on-error paper.tex
$PDFLATEX -interaction=nonstopmode -halt-on-error paper.tex
echo "Built paper.pdf"
