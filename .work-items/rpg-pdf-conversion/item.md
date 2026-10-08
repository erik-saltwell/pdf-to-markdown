---
name: "RPG PDF conversion"
status: complete
---

# RPG PDF conversion

Convert tabletop RPG adventure and rulebook PDFs into Markdown with linked
local images for an AI assistant answering rules questions and running adventures.

The application implements the agreed [intent.md](intent.md) and the phased
[plan.md](plan.md): all four local converters, English OCR, physical page
comments, conservative image filtering, reports, and owned-file transactional
replacement. A single setup operation provisions isolated runtimes to resolve
the verified Typer/Pillow conflicts.

Completed and verified on 2026-10-07. Installation, Ruff/ty, package build, direct
conversions, native failure gates, model-download behavior, and publication
fault/recovery checks are recorded in [progress.md](progress.md). No unit tests
or test tooling were added, and no changes were committed.

All four candidates converted the supplied 25-page Temple of 1000 Swords.
The selected-page [source-fidelity review](review.md) records actual native
reading-order, duplication, OCR and table differences. Generated results are
under `converted/temple-of-1000-swords/` and ignored by Git. The user has selected
Marker provisionally in the project's `settings.yaml`, based on that review.
A permanent converter winner remains open, and reports do not certify accuracy.

Further evaluation can begin with additional books and real English scans.
Exhaustive source review, difficult cross-page layouts, broader decoration
calibration and other platforms/filesystems remain unverified. These are
evaluation limits rather than blockers to running the delivered application
on the verified machine.
