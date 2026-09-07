# Package for External Review

This archive is the current pre-submission candidate prepared for external review of the affine-bundle linear solver. It does not claim that external peer review has already taken place.

Suggested entry points:

1. `paper.pdf` — compiled manuscript.
2. `paper.tex` and `references.bib` — LaTeX sources.
3. `src/` — C implementation.
4. `tests/` — regression, adversarial, and property-based tests.
5. `experiments/` — reproducible numerical experiment harnesses.
6. `data/` — packaged real-matrix control data, including `well1033` assets.
7. `FINAL_VALIDATION_REPORT.md` — final validation summary.
8. `REVIEW_NOTES.md` and `review_followup_changes.patch` — changes arising from the pre-submission audit.
9. `procedural_wording_neutralization.patch` — wording-only change that makes the review status explicit and neutral.
10. `SHA256SUMS.txt` — per-file integrity checks inside the package.

The latest pre-submission audit follow-up includes two clarifications:
- explicit distinct formulas for the affine-translation keep/drop thresholds;
- semantically inapplicable solution-quality fields are exported as NaN/null for INCONSISTENT/UNDECIDABLE outcomes.
