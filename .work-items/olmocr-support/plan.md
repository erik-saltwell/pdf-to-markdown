# olmOCR support implementation

- [x] Inspect settings, worker dispatch, runtime setup, common image retention,
  native olmOCR 0.4.27 pipeline and Dolma schema.
- [x] Add converter selection, distribution reporting, runtime import check,
  pinned requirements and generated hashes.
- [x] Implement local pipeline invocation, page span validation, fallback
  rejection, native JSON retention, image filtering and process cleanup.
- [x] Provision the runtime and run a small digital/scanned PDF conversion.
- [x] Exercise invalid native results and verify existing converter selection.
- [x] Run Ruff, ty and build; document verified behavior and remaining limits.

Upstream references: https://github.com/allenai/olmocr and the PyPI 0.4.27 wheel.
The machine has an RTX 4090, CUDA driver support and Poppler installed.
Model download and vLLM startup remain to be verified. No unit tests added,
following project policy.

See [progress.md](progress.md) for final verification and limits.
