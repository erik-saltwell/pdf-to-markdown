---
name: "olmOCR support"
status: complete
---

# olmOCR support

Add `converter: olmocr` to the existing local PDF conversion workflow with a
hashed isolated runtime, native page references, embedded images, reports, and
existing transactional publication. Keep the current default and project selection.

olmOCR uses a local vision language model on every page, unlike the existing
engines that can prefer embedded text. Requires CUDA and Poppler. The adapter
runs olmOCR 0.4.27 with its default olmOCR-2-7B-1025-FP8 model, one concurrent
request, 80% GPU memory allocation, and strict rejection of fallback pages.

See [plan.md](plan.md) for implementation and verification.

Completed on 2026-11-10. All five runtimes provisioned successfully. The final
adapter converted a two-page digital/scanned fixture on the RTX 4090, preserved
physical page references and sampled numbers, and published two local source
image assets plus native Dolma JSON. The report records model figure placeholders
as warnings; their descriptions stay as text rather than broken image links.
No-GPU failure preserved prior output; worker termination stopped the pipeline.
Ruff, ty, build and diff checks passed. No unit tests or tooling were added.

Verification details and limits are in [progress.md](progress.md). Large books,
rotated/complex scans, vector figures and exhaustive content fidelity remain
unverified. Marker remains the provisional project selection. No commit made.
