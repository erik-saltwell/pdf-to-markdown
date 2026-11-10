# Implementation and verification

Completed 2026-11-10. `converter: olmocr` dispatches to an isolated, hashed
olmOCR 0.4.27 / vLLM 0.11.2 runtime. Setup provisions all five converters. The
adapter starts a loopback-only native server on an available port, processes the
whole document locally, validates native Dolma page spans and zero fallback
pages, preserves native JSON, and uses existing image retention/filtering and
transactional publication. Termination cleans up the private process group.
Reports include olmOCR and vLLM versions and effective extraction options.

## Verification

- `scripts/install-tool.sh`: all five locked runtimes installed, dependency checks
  and imports passed, registry activated and editable CLI installed.
- Ruff check/format, ty, `uv build`, and `git diff --check` passed. The wheel
  includes the adapter and hashed runtime lock.
- Settings accepts olmocr; project selection remains marker. Existing
  PyMuPDF4LLM converted the two-page fixture, including scanned text.
- Direct native-result checks accepted full spans and an empty physical page;
  rejected fallback pages, missing pages, gaps and uncovered trailing text.
- A CLI conversion with CUDA hidden failed with the GPU prerequisite message,
  saved a failure report and preserved every prior output hash.
- A real local GPU conversion processed two digital/scanned pages with zero
  native fallback pages. Both physical page comments appear in order. Sampled
  armor class 15, hit points 27, treasure 120 gold pieces and price 35 silver
  pieces match the source. Two source image links resolve; report and native
  JSON were checked. `accuracy_verified` remains false.
- Successful conversion left no native pipeline or vLLM server running. A
  separate worker SIGTERM check stopped the pipeline and saved a failed result.

Disposable verification artifacts: `/tmp/pdf-md-olmocr-verification/`. Logs:
`/tmp/pdf-md-olmocr-full-setup.log` and
`/tmp/pdf-md-olmocr-convert-final.log`. First-use model download completed with
visible progress; the repeat conversion reused cached weights.

## Native figure limitation

The first inference returned a figure link such as
`page_349_384_263_181.png` without creating an image file. The existing asset
gate correctly rejected publication. Upstream does not specify a reliable
coordinate system for these predictions. The final adapter preserves the figure
description as text, reports the placeholder names in options and emits a
warning. Native Dolma JSON remains unchanged; actual embedded PDF images are
retained separately on their physical pages. It does not invent image crops.

Large books, complex/rotated scans, figures inside scans, vector-only figures,
exhaustive wording/table fidelity, and other GPUs/platforms remain unverified.
No quality rubric was defined or assessed. No unit tests or tooling were added.
