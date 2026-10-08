# pdf-to-markdown

Convert one whole RPG PDF into Markdown with physical page references, local
image assets, and a saved conversion report. Extraction preserves the
converter's wording and table structure; it does not summarize or rewrite rules.
English OCR runs locally when needed. Completed processing does not establish
content accuracy.

## Install

The current installation targets **Linux x86_64 and Python 3.12**. Install
[uv](https://docs.astral.sh/uv/), then run this single setup operation from the
checkout:

```sh
scripts/install-tool.sh
pdf-to-markdown --help
```

Setup installs the CLI as an editable tool and installs **all four** converters
in managed, isolated Python environments. Their Typer and Pillow requirements
conflict in one environment. Each runtime uses a fully pinned, hashed lock;
setup checks dependencies and imports before activating the runtime registry.
Rerun the same script after changing runtime dependencies or to repair setup.
Installing only the CLI with `uv tool install` does not provision converters.

| Setting | Pinned converter | Local extraction / OCR |
|---|---|---|
| `docling` (fallback default) | Docling 2.135.0 | Standard PDF pipeline, English RapidOCR |
| `marker` (project selection) | Marker 1.10.2 | Local Surya; LLM processing disabled |
| `pymupdf4llm` | PyMuPDF4LLM 1.28.2 | Layout engine, English Tesseract |
| `mineru` | MinerU 4.0.10 | Basic tier, local ONNX, automatic OCR |

Marker uses the local baseline supported by this adapter. It is intentionally
pinned rather than following releases with different server requirements.
Marker is selected provisionally in the project's `settings.yaml`, based on
the Temple of 1000 Swords review. A permanent converter winner remains open.

Dependencies and model caches require several GB. PyTorch layout models use an
available compatible GPU; CPU extraction is supported but can be slower. The
installation and conversions were exercised on Ubuntu x86_64 with Python 3.12
and an RTX 4090. Other platforms and filesystem implementations are unverified.

## Convert

```sh
pdf-to-markdown convert "Dragon Keep.pdf" --output "./converted/dragon-keep"
pdf-to-markdown --settings marker.yaml convert adventure.pdf -o output/marker
```

The PDF and output folder are required. `--settings` is a global option and
belongs **before** `convert`. Choose a converter in YAML:

```yaml
converter: marker  # docling, marker, pymupdf4llm, or mineru
```

By default, settings come from `settings.yaml` in the current working directory.
A missing or empty implicit file uses `docling`; a missing explicitly requested
file is an error. Unknown settings, unsupported converter names, and invalid
YAML are rejected.

```sh
pdf-to-markdown show-settings
pdf-to-markdown --version
pdf-to-markdown --help
pdf-to-markdown convert --help
```

Help includes copyable examples, settings placement, output/replacement behavior,
and first-use download guidance. It works even if the requested settings file is
missing or invalid; settings are validated when an actual command runs.

There are no converter, page-range, language, or overwrite flags. Each invocation
processes one entire PDF. For comparisons, use separate settings files and
output folders.

## Results and review

Native output names and structure remain visible:

| Converter | Markdown | Assets | Additional output |
|---|---|---|---|
| Docling | `<book>.md` | `<book>_artifacts/` | `<book>.docling.json`, `conversion-report.json` |
| Marker | `<book>.md` | `images/` | `<book>_meta.json` with an application report section |
| PyMuPDF4LLM | `<book>.md` | `images/` | `<book>.chunks.json`, `conversion-report.json` |
| MinerU | `markdown.md` | `images/` | `middle_json.json`, `structured_content.json`, `model_output.json`, `conversion-report.json` |

Marker image basenames remain native; their links are adjusted to the required
asset subfolder. Empty asset folders are possible when extraction finds no
linked images. Complex tables may use HTML to retain merged cells.

Invisible comments such as `<!-- PDF page 12 -->` identify **physical pages,
starting at 1**, including blank pages. Printed page labels are not used.
Comments stay beside their page content, outside HTML tables.

Filtering removes demonstrably blank/transparent assets. A repeated solid
border is removed only with matching pixels, stable peripheral placement on
at least three pages, evidence that it is outside content, and explicit absence
of a caption. Missing evidence, symbols, maps, and ambiguous images are kept.
Filtering decisions appear in the report. Assets still referenced by native
JSON are retained even when their Markdown reference is filtered.

Some converters label maps as tables. Docling and Marker therefore retain
unlinked embedded source images conservatively, with links on their physical
page; MinerU also links native table images alongside the extracted tables.
Extracted text is retained. Page-sized scan inputs stay with OCR; there is no
general full-page image fallback. Native misclassification can still omit
visuals, particularly in scans.

The terminal displays output location, processed pages, linked images, available
warnings, and report location. Reports include converter/runtime versions,
effective extraction options, input hash, and available native diagnostics.
Reports set `accuracy_verified: false`: a successful run, or absence of warnings,
does not prove that numbers, reading order, tables, or visuals are correct.
Review source pages before relying on extracted rules.

The Markdown and native structured output are retained extraction artifacts for
a future separate cleanup pass. That pass is not implemented.

## Downloads and local processing

On first use, converters download their required model weights with visible
progress. Later runs reuse cached weights. PyMuPDF4LLM reuses installed English
Tesseract data or downloads a checksum-verified
[official English model](https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0).
The downloaded models execute locally. The PDF is not uploaded for conversion,
and no paid API, document server, or LLM cleanup is configured.

Managed runtimes live under
`${XDG_DATA_HOME:-~/.local/share}/pdf-to-markdown/runtimes/`; model caches live
under `${XDG_CACHE_HOME:-~/.cache}/pdf-to-markdown/models/`. First use requires
internet access and may take substantially longer than a warm run. Download
failure fails the run and preserves any previous output.

## Reruns and failures

Reruns automatically replace files owned by the previous successful conversion
and remove stale generated assets. A hidden manifest records their paths and
hashes. Unrelated files, including files inside an asset folder, survive.
Collisions with unrelated names, edited/deleted generated files, unsafe paths,
and concurrent output changes abort replacement.

Conversion writes to a sibling staging folder. Only a complete, validated book
can be published. The publisher builds a replacement folder and uses Linux
atomic directory exchange with a durable journal and a per-output lock. If
publication fails, it restores the previous generation. The next invocation
recovers an interrupted transaction. Filesystems without directory exchange or
required durability operations fail safely. Avoid editing the output during a
run; the lock coordinates application writers, not other programs.

A failed run writes a uniquely named sibling
`.<folder>.failed-<run-id>.report.json`, leaving the previous successful report
and result intact. Deferred post-commit cleanup is a recoverable warning and
gets a separate sibling publication report. If interrupted output was modified
before recovery, the application preserves both folders and requests manual
recovery instead of discarding those changes.

Exit codes are `0` for completed processing (including recoverable warnings),
`1` for processing/publication failure, and `2` for arguments/settings errors.
Any known failed page or incomplete physical-page coverage prevents publication.

## Development and verification

```sh
uv sync --locked
uv run --locked pdf-to-markdown --help
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ty check
uv build
uv run --locked pre-commit install
```

Pre-commit runs Ruff and ty using the versions in `uv.lock`. The project does
not add unit tests or test tooling. Verification uses direct CLI conversions,
manual source/output review, and disposable publication fault exercises.
Runtime requirements and locks are bundled in
`src/pdf_to_markdown/runtime_requirements/`; regenerate locks deliberately and
re-run the full setup and direct conversions after changing them.

Implementation and verification details are recorded in
[the work item](.work-items/rpg-pdf-conversion/progress.md). All four converters
processed synthetic digital/scanned samples, a 12-page mixed document, and the
user-supplied 25-page *Temple of 1000 Swords*. Outputs for that book are under
`converted/temple-of-1000-swords/<converter>/` (ignored by Git). Selected source
pages, tables, stat-block numbers, and map assets were reviewed; observed
differences are recorded in [the review](.work-items/rpg-pdf-conversion/review.md).
More books, real scanned books, exhaustive wording review, and difficult
cross-page layouts remain unverified. Marker is the provisional project selection.
