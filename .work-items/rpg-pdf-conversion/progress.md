# Implementation and verification

Implementation completed 2026-10-07 from [plan.md](plan.md), following
[intent.md](intent.md). The subsequent implementation request authorized the
plan's single setup operation with four isolated runtimes. No commits were
created. No unit tests, unit-test tooling, or committed fault harness were added.

## Delivered

- `scripts/install-tool.sh` installs the editable CLI and all four hashed,
  fully pinned Linux/Python 3.12 worker environments. Runtime registry activation
  follows dependency/import checks for every worker. Main CLI dependencies stay
  separate from conflicting converter dependencies.
- The agreed `convert PDF --output FOLDER` / `-o` interface, global settings,
  exit codes, Rich summaries, local OCR, model downloads, and saved reports.
- Docling, Marker, PyMuPDF4LLM layout, and MinerU 4 Basic integrations using their
  inspected release APIs. No remote document service or LLM cleanup is enabled.
- Exact physical page identities and comments, including blank pages; failed
  native outcomes, exceptions, missing/reordered pages, missing links, or export
  failures prevent publication. MinerU's preparation hook rejects known broken
  pages before placeholders can hide them. Docling rejects PARTIAL_SUCCESS.
- Conservative pixel/source evidence filtering; ambiguous visuals and small
  symbols survive. White symbols on transparency are retained. Files referenced
  by native JSON survive filtering of their Markdown link.
- Owned-file manifests, staging/candidates, collision/edit protection, stale
  generated-file removal, unrelated-file preservation, per-output locking,
  Linux atomic directory exchange, durable journal, rollback/restart recovery,
  and separate failure/publication-warning reports.
- README installation, commands, output formats, cache behavior, recovery
  semantics, verification policy, and extraction limitations.

## Verification actually performed

All checks ran on the existing Ubuntu Linux x86_64 / Python 3.12 machine with
an RTX 4090. Both Docling and Marker Torch 2.7.1/CUDA 12.6 environments performed
GPU tensor operations successfully. CPU ONNX and local Tesseract also ran.
CPU-only machines and other platforms/filesystems were not exercised.

**Installation and code checks:** installed all four runtimes from the bundled
locks; `uv pip check` and native imports passed in each. The full documented
setup script passed on an idempotent rerun and installed
`/home/eriksalt/.local/bin/pdf-to-markdown`. The installed tool performed a
conversion with `/tmp` as its working directory. `uv build` passed; inspection
confirmed all four runtime locks are bundled in the wheel. Ruff lint, Ruff
format checking, and ty passed. `pre-commit run --all-files` skipped Ruff because
the checkout has no tracked files, so pre-commit was also run with the explicit
source-file list: all three hooks passed. Files remain unstaged/uncommitted.

**CLI behavior:** help, version, and settings commands complete without importing
heavyweight converters or downloading models. Missing arguments, forbidden or
misplaced flags, explicit missing settings, invalid YAML/mapping/value/key,
missing input, and unsafe output shapes return 2. Missing/empty implicit
settings use Docling. Corrupt and encrypted PDFs return 1 and save failure
reports with available converter/version details. A corrupt rerun left the
successful output inventory unchanged.

**Synthetic conversions:** every candidate completed a four-page digital
sample containing stat-block numbers, rules, a grid map, a table and a blank
page; a two-page English scan; a twelve-page mixed document with leading,
intermediate and trailing blanks; and a three-page two-column/merged-cell
sample. The mixed document had exact comments 1–12 in every output, verifying
MinerU was not limited to ten pages. Selected rules/statistics were compared
with fixture text, merged cells remained HTML, and local image links were
validated. Synthetic scan map omissions are recorded in the review.

**Models:** actual first-use native weight-download progress was observed;
warm mixed-document runs succeeded with Hugging Face offline mode and network
proxies pointed at an unavailable local endpoint. A deliberately missing
Tesseract-data case downloaded the official English model with real byte
progress, verified its pinned SHA-256, reused it on a warm call, and performed
local OCR using the downloaded data. Model failures propagate as processing
failures; the old result is outside worker staging.

**Native failure gates:** a disposable wrapper supplied Docling's actual
PARTIAL_SUCCESS status with full placeholder coverage; the adapter rejected it
before export. A disposable wrapper supplied MinerU's native
`broken_page_indices=[1]`; the adapter rejected physical page 2 before parser
placeholder insertion and rendering. These wrappers live only in `/tmp`.
Exceptions are captured at the worker boundary with traceback/version details,
and the publisher accepts only a successful validated result.

**Image filtering:** direct disposable asset exercises removed opaque blank
and fully transparent assets, and removed a repeated solid outline only with
three-page stable source geometry and explicit no-caption evidence. Small
symbols, a map, missing caption evidence, and a white symbol on transparency
were retained. Native JSON references protected their files; multiple URI
aliases to one filtered file were handled without double deletion. Real-book
filtering identities/reasons were inspected in the reports.

**Publication:** disposable filesystem exercises and real CLI reruns verified
fresh output, replacement into a nonempty unowned folder, stale-image removal,
changed input stem, nested unrelated notes, unrelated symlinks, collision
refusal, edited owned-file refusal, concurrent output-change refusal, generated
symlink refusal, and unsafe output rejection. Injected exchange, journal
preparation/commit, parent-directory flush, and report serialization failures
preserved or restored the old generation. Hard child-process termination after
exchange rolled back on the next invocation; termination after durable commit
retained the new generation. Concurrent application writers serialized. An
injected backup cleanup failure retained exit-success behavior and saved a
separate publication-warning report, then recovered on the next invocation.
These were direct disposable exercises, not an added automated test suite.

**Representative book:** the user supplied *Temple of 1000 Swords*, 25 pages.
All four converters completed it into `converted/temple-of-1000-swords/`.
Physical comments 1–25, invisible rendered comments, local image links, selected
page 12/24 stat-block numbers, source tables/rules, and the main map were checked.
The saved [review.md](review.md) records actual counts and qualitative findings.
It describes native reading-order/duplication/OCR/table differences; no converter
winner was selected and every report keeps `accuracy_verified: false`.

## Implementation resolutions and deviations

The confirmed Typer/Pillow conflicts are resolved operationally by installing
all four managed runtimes in one setup operation. There are no optional backend
extras or converter flags. Workers import the trusted application code from the
installed package while keeping backend dependencies isolated.

MinerU 4's actual constructor uses `parse_mode="auto"`; the earlier plan's
`ocr_mode` wording was not copied as an unsupported argument. The application
owns its local configuration, selects Basic ONNX, disables LLM-aided features,
and renders the saved native per-page document in FULL mode to retain furniture.
It scales normalized native boxes to physical PDF coordinates for filtering.

Real conversion showed maps can be classified as tables without warnings.
Docling/Marker conservatively preserve unlinked embedded source images, and
MinerU links native table images alongside table text. This preserves uncertain
existing assets; it does not rasterize pages, replace table text, or introduce
an extraction-quality scoring heuristic. Page-sized scan inputs stay with OCR.
Docling picture export uses scale 2.0 after inspecting the map's default low
resolution. Marker image basenames remain native inside the required subfolder.

RapidOCR disables logging propagation, so its native logger receives an
additional recorder while keeping its console handler. MinerU Loguru warnings
are forwarded to the worker recorder, including on failed runs. PyMuPDF's native
warning buffer and message channel are captured. Unknown page attribution is
left unset, rather than guessed from free-form message text.

The publisher's journal records the intended inventory. Restart recovery
refuses to discard changes made to an interrupted published folder; it preserves
both folders for manual recovery. Deferred post-commit cleanup gets a supplemental
sibling report because mutating the committed owned report would invalidate its
manifest hash. Application locks do not control external programs; the final
inventory check cannot eliminate every external writer race.

## Remaining limits

No known blocker remains for running the implemented application on the verified
machine. More source-fidelity evaluation is warranted: one real digital RPG book
and synthetic scans do not establish accurate extraction across all books.
Real scanned RPG books, exhaustive wording/number checks, complex cross-page
items, unusual source object transforms, and broader decoration calibration are
unverified. The application initially shipped with Docling selected.

Fault exercises used process termination and injected I/O errors on the current
Linux filesystem. They are not a physical power-loss/storage-controller crash
validation. Filesystems without atomic directory exchange/durable directory
flush are unsupported for replacement and fail safely. An interrupted extraction
process can leave an unreferenced sibling staging folder; it is never treated
as publishable output. Do not delete journals/backups needed for recovery.

Future cleanup remains separate and unspecified. Retained Markdown/native
structured artifacts are its possible inputs; no cleanup provider or behavior
was added.

## Subsequent configuration decision

The user approved Marker as the selected converter for now, following the
recommendation from the Temple of 1000 Swords review. Project `settings.yaml`
now selects `marker` (the pinned 1.10.2 runtime); README and intent record the
provisional choice. Missing/empty implicit settings still use the existing
Docling fallback. Both the installed CLI and the development CLI were checked
with `show-settings` and reported `converter: marker`. The work item remains
complete; no permanent winner or broader accuracy certification is implied.

## CLI help improvement

The user requested improved command-line help. Top-level `--help`,
`convert --help`, and `show-settings --help` now include copyable examples,
clear PDF/FILE/FOLDER placeholders, settings placement and fallback semantics,
local English OCR/download guidance, result/report details, safe rerun behavior,
and relevant exit-code or accuracy information. Examples use shell continuation
lines so they remain copyable at narrow terminal widths.

Review found that subcommand help previously failed when an explicit settings
file was missing or invalid. Settings loading now occurs only when a command
executes; help remains available without requiring valid configuration. Actual
commands still reject invalid settings with exit 2.

Direct installed-CLI help checks passed at 60/80/120 columns, and development
module help passed. All three help paths succeeded with missing/invalid settings;
`show-settings` still validates settings and reports the selected Marker.
Inspection confirmed help does not import heavyweight converters. A real
four-page Marker conversion completed after the callback change. Ruff lint and
format checking, ty, explicit-file pre-commit hooks, and `uv build` passed.
README documents the help behavior. No tests/tooling or commits were added;
the work item is complete again.
