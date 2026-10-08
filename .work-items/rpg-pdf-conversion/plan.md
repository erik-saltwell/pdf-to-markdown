# RPG PDF conversion implementation plan

Planning snapshot: 2026-10-07. [intent.md](intent.md) is the agreed requirements.
This document proposes implementation choices for its unresolved details; it
does not change the intent, select a winning converter, or authorize a commit.
All implementation checkboxes remain open.

## Scope and implementation baseline

Preserve the agreed interface:

```text
pdf-to-markdown [--settings FILE] convert PDF --output FOLDER
```

Keep `-o`, `show-settings`, `--version`, and help. Settings select the converter;
there is no command override. Process the entire PDF, prefer usable embedded
text, support English OCR locally, retain meaningful and uncertain images,
insert physical page comments, save available warnings and converter details,
and publish only after every page completes. Exit codes are 0 for completion
with optional recoverable warnings, 1 for processing/publication failure, and 2
for invalid arguments/settings. No batch, page-range, language, overwrite,
comparison, cleanup, or model-management commands are added.

Extraction remains separate from any future AI cleanup. Keep native structured
extraction where available and perform only required serialization, page
comments, asset linking/filtering, and reporting. Do not summarize or rewrite
rules. Do not introduce extraction-quality heuristics or full-page fallback
images. Internal page iteration is allowed; it does not expose page selection.

### Verified repository and machine facts

- Inspected `AGENTS.md`, `.work-items/workflow.md`, `.agent_context.md`, the
  work-item records, every file in `src/pdf_to_markdown/`, `settings.yaml`,
  `pyproject.toml`, `uv.lock`, `README.md`, `.pre-commit-config.yaml`,
  `.python-version`, and `.gitignore`. The project context has no extra policy.
- `cli.py` contains the Typer callback, global settings option, version output,
  and `show-settings`; there is no `convert`. `settings.py` already validates
  the four enum values, rejects unknown keys, and implements implicit missing
  or empty-file defaults and explicit missing-file errors. Preserve this loader.
- Direct execution in the existing `.venv` confirmed help and `show-settings`.
  An explicitly missing settings file exits 1, confirming the required change
  to 2 in `cli.py`.
- Runtime dependencies are only PyYAML, Rich, and Typer. No converter is
  installed in the project environment. The executable entry point and
  `python -m pdf_to_markdown` already work. Ruff and ty are configured; no test
  suite or test tooling is present.
- The observed machine is Linux x86_64, glibc 2.39, Python 3.12.13, uv 0.11.2,
  approximately 62 GiB RAM, an RTX 4090 with 24 GiB VRAM, and approximately
  981 GiB available disk space. The NVIDIA driver advertises CUDA 13.2; an
  installed CUDA toolkit or working PyTorch inference was not verified.
  Tesseract and its `eng` data are installed. Neither `docker` nor
  `llama-server` was found on PATH. These observations do not establish
  support for another machine.
- No PDF samples were found in the repository. No conversion, model download,
  backend installation, or runtime import of a converter was performed during
  planning. Repository files were already untracked; preserve that state.

### Verified upstream facts and compatibility conflicts

Package metadata and released wheel source were read without installing them.
Current releases observed were Docling 2.135.0, docling-core 2.100.0, Marker
2.0.0, PyMuPDF4LLM/PyMuPDF/PyMuPDF Layout 1.28.2, and MinerU 4.0.10. Recheck
at implementation time and pin the chosen versions rather than following
unbounded releases. Sources: [Docling metadata](https://pypi.org/pypi/docling/2.135.0/json),
[core metadata](https://pypi.org/pypi/docling-core/2.100.0/json),
[Marker metadata](https://pypi.org/pypi/marker-pdf/2.0.0/json),
[PyMuPDF4LLM metadata](https://pypi.org/pypi/pymupdf4llm/1.28.2/json),
and [MinerU metadata](https://pypi.org/pypi/mineru/4.0.10/json).

Two conflicts are confirmed by `uv pip compile` against temporary requirement
files, without changing the project's manifest or lock:

- Docling's standard dependencies require `typer<0.27.0`; the application
  currently requires `typer>=0.27.3`. That combined resolution failed.
- Marker requires `Pillow<11`; MinerU requires `Pillow>=11`. A combined
  resolution of all four current releases failed on this contradiction.
  Marker 1.10.2 retains the same Pillow limit, so pinning it does not make a
  shared environment possible.

Separate resolutions succeeded for Docling with its RapidOCR extra, Marker
2.0.0, Marker 1.10.2, PyMuPDF4LLM with RapidOCR/ONNX Runtime, and MinerU 4.0.10.
The MinerU resolution needed the actual machine's platform: generic Linux
cross-resolution initially failed because `mineru-llama-cpp` requires a
manylinux 2.34 wheel, whereas uv's generic target used 2.28. Resolution against
the local interpreter succeeded. **Resolution is not installation, ABI
compatibility, GPU compatibility, or successful inference.**

Marker 2 introduces Surya inference-server prerequisites (Docker with NVIDIA
support or `llama-server`). The recommended initial Marker baseline is
**1.10.2**, whose released `create_model_dict()` constructs local Surya
predictors directly. Its metadata resolved Surya 0.17.1 and Transformers
4.57.6. This is an evaluation version choice, not a converter winner.
[Marker current prerequisites](https://github.com/datalab-to/marker#inference-backend-prerequisites)
and [Marker 1.10.2 distribution](https://pypi.org/project/marker-pdf/1.10.2/).

### Proposed installation response to the conflicts

Keep the requirement that **one setup operation installs all four converters**.
Use a main CLI environment and four application-managed, locked worker
environments. This lets the main CLI retain its Typer version and separates the
incompatible Pillow and Transformers versions. Install every worker during
setup, not individually or only when selected; only model weights are deferred
until needed. Do not use `--no-deps` or dependency overrides to conceal conflicts.

Plan a single setup script, `scripts/install-tool.sh`, which installs the
editable main tool and provisions all four runtimes from
`runtime-requirements/<converter>.in` and platform-specific resolved locks.
Use a project/application-specific runtime directory outside result folders;
record its location so the editable tool finds its matching workers. Stage
runtime upgrades and replace their installation registry only after all four
are ready. Keep model caches independent of runtime environments and outputs.
The script must support an idempotent rerun and report a failed installation.

This is a proposed packaging mechanism, not an agreed permanent multi-backend
architecture. It preserves installation together but changes README's current
single `uv tool install --editable .` setup recipe. If "together" was intended
to require one Python environment specifically, that interpretation is blocked
by the verified metadata conflict; resolve it explicitly before implementing
this packaging choice. Do not silently drop a converter or install optional
backends. A future compatible shared lock may remove the isolated runtimes.

## Implementation choices and remaining feasibility gates

Use a small fixed dispatcher, four backend modules, and a file-based worker
result sufficient to return counts, artifacts, warnings, and failures. This
internal contract does not normalize Markdown, native extraction JSON, or
native reports. Proposed modules are `conversion.py`, `worker.py`,
`converters/{docling,marker,pymupdf4llm,mineru}.py`, `images.py`, `reports.py`,
and `output.py`. Add modules only when the phase needs them; no plugin registry,
server framework, benchmark command, or generic backend extension system.

Execute the main installation's worker bundle by trusted absolute path with the
selected runtime's Python interpreter. Keep its bootstrap and shared result
types stdlib-only; workers must not import `cli.py` or install the main package's
conflicting dependency set into their environments. Pass a request file with
the input, staging path, converter, and run ID; write results to a separate
file and stream progress/diagnostics visibly. A subprocess's exit 0 alone is
insufficient without a complete validated result. Use a small Markdown parser
and stdlib HTML parsing if needed for asset-reference validation, declare those
dependencies explicitly, and never rewrite unrelated Markdown content.

### Page references and completion evidence

Determine physical page count independently before conversion, using PyMuPDF
in its worker environment. Keep the input read-only. Validate the exact set of
page identities, not just a count, and use converter processing outcomes to
distinguish genuine blank pages from failed pages. This checks processing
coverage, not extraction accuracy. Never flag a page because it has little text.

- **Docling:** `DocumentConverter`/`PdfFormatOption` and
  `PdfPipelineOptions` expose local OCR and image generation. Results carry
  `status`, `errors`, and processed `pages`; current error records can carry
  one-based `page_no`. The standard pipeline reports page failures as FAILURE
  or PARTIAL_SUCCESS and can add failed-page placeholders to the exported
  document. Inspect the result, not only `document.pages`.
  [Converter API](https://docling-project.github.io/docling/reference/document_converter/)
  and [pipeline source](https://github.com/docling-project/docling/blob/main/docling/pipeline/standard_pdf_pipeline.py).
  Plan numbered comments using item provenance and native serializer hooks.
  A constant `page_break_placeholder` alone supplies no page number. Prefer
  one serialization with provenance-based insertion; page-specific export is
  a fallback only after checking that multipage items are neither duplicated
  nor omitted. Keep comments beside the relevant table/list content without
  breaking its Markdown or HTML. Verify blank pages and multipage tables.
  [Document serialization source](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py).
- **Marker baseline:** use `PdfConverter`, `create_model_dict()`, and
  `MarkdownRenderer`. Enable `paginate_output`; the renderer emits a distinct
  separator with a zero-based `page_id`. Replace only generated separators
  with `<!-- PDF page N -->`, using `page_id + 1`, and validate those identities
  against native `page_stats` and the input. Use a run-specific separator to
  avoid replacing matching text from the book. Retain native metadata.
  The released baseline exposes these APIs; rerun inspection after any version
  change. [Marker renderer source](https://github.com/datalab-to/marker/blob/master/marker/renderers/markdown.py).
- **PyMuPDF4LLM:** use layout mode and `to_markdown(..., page_chunks=True,
  write_images=True, embed_images=False, use_ocr=True, force_ocr=False,
  ocr_language="eng", show_progress=True)`. Current layout chunks use
  `metadata.page_number`, already one-based; older legacy examples use other
  keys. Prepend each validated chunk with its physical page comment. Catch
  exceptions and available warnings rather than assuming every returned
  string represents success. `table_output="html"` is supported in the
  inspected release's layout path; its legacy fallback lacks OCR, so require
  layout availability before enabling it.
  [API](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html)
  and [package source](https://github.com/pymupdf/pymupdf4llm).
- **MinerU 4:** use local `mineru.parser.parse`, with `tier="basic"`,
  `ocr_mode="auto"`, `image_analysis=True`, and `page_range="all"`.
  Basic uses small models without the VLM requirement; its fidelity remains
  to be evaluated. Do not copy MinerU 2/3 `do_parse`/`pipeline` snippets or use
  the document-library CLI, which defaults to only ten pages.
  [Local SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)
  and [tiers](https://opendatalab.github.io/MinerU/usage/tiers/).
  Current `ParseResult.pages`/MiddleJson use zero-based `page_idx`; native save
  produces `markdown.md`, `middle_json.json`, `structured_content.json`, and
  assets. Add comments through per-page native rendering or a renderer hook
  after materializing assets, preserving native order and references.
  [Result contract](https://opendatalab.github.io/MinerU/reference/output_files/).
  **Important blocker to resolve:** the released parser's PDF rewrite can
  insert empty `PageInfo` placeholders for known broken pages. Coverage alone
  therefore misses failures. Capture the native rewrite's
  `broken_page_indices`, processing diagnostics, and native page outcomes
  before they are lost. Prefer a narrow wrapper around the pinned parser's
  preparation step; do not infer failure from an empty block list. If native
  outcomes cannot be observed reliably without maintaining a substantial fork,
  this adapter cannot satisfy the failed-page requirement yet.
  [Parser source](https://github.com/opendatalab/MinerU/blob/master/mineru/parser/mineru_parser.py).

For all converters, warnings remain verbatim where available, with page numbers
converted to physical numbering only when upstream identifies the page.
Do not guess attribution from message text unless the pinned API documents it.
Use Python warning capture and the converter's logging channel, restoring
handlers afterwards; capture PyMuPDF's native message/warning channel and
MinerU's Loguru diagnostics as applicable. Unknown failure-like diagnostics
must be investigated before that adapter is declared complete. Recoverable
table/stat-block warnings retain extracted content and permit exit 0;
exceptions, known failed pages, incomplete coverage, or unresolved partial
processing prevent publication. Absence of warnings is not proof of accuracy.

### Conservative image filtering

Apply this policy during the first adapter, then every candidate integration:

1. Preserve maps, diagrams, illustrations, handouts, captions, text-bearing
   visuals, map legends/symbols, and anything ambiguous. No rejection based
   only on size, aspect ratio, repetition, position, or low visual variance.
2. Initially filter only demonstrably blank/transparent assets, explicit
   non-content background objects supported by native/source evidence, and
   repeated border-only assets with **combined** evidence: matching pixels or
   source object, stable peripheral placement across multiple pages, wholly
   outside text/meaningful figure areas, no attached caption, and no detected
   or embedded text. Numeric geometry tolerances are implementation constants
   to calibrate by visual inspection; they are not a confidence score.
3. Missing geometry, mixed-content crops, ambiguous classification, a legend
   association, or unreadable text-detection evidence means keep. In a scan,
   a border fused with useful content stays with that content; do not segment
   or discard a full-page map just because of its dimensions.
4. Disable documented aggressive native filters where possible. In particular,
   a legacy PyMuPDF4LLM `image_size_limit` is not a decoration classifier.
   Do not assume that option affects its current layout path. Keep native
   header/footer text until omission is shown to preserve book content.
5. Filter through the native object/serializer when possible, preserving text
   children and captions. Otherwise remove only the corresponding generated
   image reference, then delete the asset only if no retained reference uses
   it. Track decisions per occurrence; a reused asset with one meaningful
   occurrence remains. Do not remove prose or image-like strings in code.

Use existing native bounding boxes, source objects, and Pillow pixels; no
paid API, new semantic-classification service, or OCR of every illustration.
Where "no text" evidence is unavailable, keep the image. Log filtered asset
identities and reasons in the report so human review can inspect decisions.
The policy is a proposal requiring sample-based calibration, not a verified
RPG decoration detector. Repetition alone can describe useful recurring maps.

There is a concrete output-layout tension: Marker's native `save_output`
writes images beside the Markdown, while intent also requires an asset
subfolder. Propose the minimum adaptation: retain native filenames and report
names, place images in a Marker-specific subfolder, and rewrite just their
local references. Preserve all other native structure; document this deviation
instead of introducing a common output layout for all converters.
[Native writer source](https://github.com/datalab-to/marker/blob/master/marker/output.py).

### Models, OCR, and local execution

Pin inference configuration in each adapter, independently of user/global
converter configuration. Never instantiate remote conversion clients. Disable
picture descriptions and LLM cleanup/post-processing; ignore or reject remote
endpoint configuration inherited from the environment. Locally downloading
weights is allowed; sending PDF data or crops elsewhere is not.

- Docling: install `docling[rapidocr]`, use ONNX Runtime, explicitly select
  English (`RapidOcrOptions(lang=["en"])` in the inspected release), and keep
  the default selective OCR mode. Current RapidOCR options default to Chinese,
  so defaults alone do not meet intent. Disable remote services, descriptions,
  code/formula enrichment, and extra classifiers initially. Generate picture
  crops with `generate_picture_images=True`; do not export page screenshots
  or table fallback images. Models may internally render pages for analysis.
  [Pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
  and [figure export](https://docling-project.github.io/docling/_generated/examples/export_figures/).
  Before first inference, call the native `download_models(progress=True)`
  with only the selected layout/table/OCR bundles and disable its otherwise
  enabled code/formula and classifier downloads. Pass the resulting artifacts
  directory to the pipeline. Verify that the English OCR download matches the
  pipeline's selected model.
  [Downloader source](https://github.com/docling-project/docling/blob/main/docling/utils/model_downloader.py).
- Marker 1.10.2: explicitly set `use_llm=False`, preserve embedded text, and
  leave forced OCR off. Allow native Surya model downloads with their progress
  output visible. No LLM service is constructed. Verify English scans through
  this baseline's OCR, rather than inventing a language argument absent from
  its API. A switch to Marker 2 requires revisiting server provisioning,
  remote-endpoint rejection, models, and the runtime lock.
- PyMuPDF4LLM: explicitly choose the installed local OCR plugin rather than
  relying on availability-based selection. The initial proposal is Tesseract
  with `eng` on this machine; verify its plugin dependencies and provision
  English data automatically if absent on another supported installation.
  Install RapidOCR/ONNX Runtime in its runtime for a verified local alternative,
  but do not silently switch engines between comparisons. Missing OCR must
  fail readiness rather than continue with a warning and omit scan text.
  Current plugins can otherwise continue without OCR when none is available.
  [OCR plugin behavior](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/ocr-plugins.html).
- MinerU 4: explicitly configure Basic's local small-model backend (initially
  ONNX CPU), enable auto OCR, and turn off LLM-aided title/table processing.
  English capability and model configuration must be verified: the inspected
  `parse()` signature has no `lang` parameter. Use the native Basic model
  preparation/verification path, with provider progress forwarded to the
  terminal. Keep application-owned configuration separate from `~/.mineru`
  so a user's remote settings cannot change conversion behavior.
  [Models and configuration](https://opendatalab.github.io/MinerU/usage/model_source/).

Use native model caches and readiness checks. Show a clear preparation/download
stage and real native byte/file progress; a spinner alone is insufficient for
a download with no visible progress. If native initialization hides it, invoke
the pinned native downloader automatically with progress enabled. No separate
user download command is required. Download interruption, missing weights,
cache permissions, or network failure fail the run before publication. Do not
force redownloads on reruns. Verify warm-cache conversion without network.

### Reports

Proposed fallback format is UTF-8 JSON using the standard library. Reuse
Marker's native `<stem>_meta.json`, preserving its fields and adding a
`pdf_to_markdown` section when it lacks required run information. Other
backends retain their native extraction JSON and save `conversion-report.json`
when no suitable native report exists. Extraction JSON is not itself evidence
of successful processing. This selects a minimal report supplement, not a
normalized extraction schema.

Include run ID/timestamps, converter distribution and actual runtime version,
relevant OCR/model/runtime versions when available, selected local options,
input identity, requested output, outcome, input/processed page counts, images
saved, filtering reasons, available native warnings/errors and their source,
and native-report/artifact paths. Use SHA-256 if recording input identity;
hashing is not quality assessment. Unknown failed-page numbers remain unknown.
Record warning-availability limitations explicitly. Say processing completed
and content accuracy was not verified; never say the book is error-free.

On failure, leave the previous output and its success report untouched. Save
the diagnostic report to a unique sibling of the requested folder, for example
`.dragon-keep.failed-<run-id>.report.json`, using exclusive creation, and print
that path. This is a report, not a published partial book. If even diagnostic
writing fails, print the original error and the report-write failure and exit
1. Successful reports are staged and become visible with the generated files.

### Ownership and publication

Use a private `.pdf-to-markdown-manifest.json` in each successful result.
Store schema/application identity, generation ID, converter, relative owned
file paths, byte lengths, and hashes. Include Markdown, saved images, native
extraction/report files, and the fallback report. The manifest is the final
ownership record; it is not another page-reference format. Never infer ownership
from filename extensions, PDF stem, or converter directory names.

For a folder without a valid manifest, treat existing files as unrelated.
Preserve them when names do not collide; fail on collisions with new generated
files. Do not adopt or delete legacy-looking files automatically. Reject an
invalid/unsupported manifest, escaping/absolute paths, owned symlinks or symlink
ancestors, conflicting file/directory paths, and edited owned files whose
recorded hashes no longer match. These failures need no overwrite flag; the
user can choose a clean folder or move the conflicting file. Only verified
previously owned files become stale and removable. Unrelated children of a
generated-assets directory survive.

Publication proposal for the observed Linux target:

1. Validate paths before inference; reject a file as output, filesystem root,
   replacing the checkout/current-directory root, or an output tree containing
   the source PDF. Resolve symlinked destination roots conservatively.
   Acquire an advisory lock stored beside the destination, keyed by its
   resolved path, so simultaneous application runs cannot publish together.
2. Convert entirely in a unique sibling temporary directory on the same
   filesystem. Workers receive only this staging destination. Validate page
   outcomes, page comments, and all generated local image links. Absolute,
   cloud, escaping, and staging-directory links are rejected; ordinary textual
   links to external references need not be rejected.
3. Build a separate candidate result by copying unrelated files/directories
   from the old output without following symlinks, then overlaying the new
   generated files and manifest. Do not hardlink files that may be edited.
   Compare the old snapshot again before publication; abort on detected
   concurrent changes. Advisory locking cannot prevent another application
   from editing unrelated files, so document that external concurrent writers
   are outside the initial guarantee.
4. Flush candidate files and relevant directories. Write and flush a small
   transaction journal beside the output recording generation IDs and paths.
   If there is no old output, atomically rename the candidate into place.
   For an existing nonempty output, use Linux
   `renameat2(RENAME_EXCHANGE)` to atomically exchange old and new directories;
   `os.replace` cannot replace an arbitrary nonempty directory. Keep the
   exchanged old tree as rollback backup until commit is durable.
   [Linux rename semantics](https://man7.org/linux/man-pages/man2/rename.2.html).
5. On a precommit error, exchange back if necessary and preserve the old
   generation. On interruption, recover under the lock using journal state
   and manifest generation IDs: uncommitted swaps restore the old generation,
   committed swaps retain the new one. Flush parent-directory updates. If
   rollback itself fails, keep both trees and the journal, report exact paths,
   and stop; never delete the only intact previous generation.
6. Define the durable commit point before reporting success. Cleanup of the
   backup/journal after commit may produce a recoverable warning, not a
   misleading failed conversion. Next invocation finishes safe cleanup.

Verify exchange support on the actual filesystem before enabling replacement.
Use a small stdlib `ctypes` wrapper if necessary; do not add a transaction
framework. If exchange is unavailable, existing output remains untouched and
replacement is a feasibility blocker until a reviewed rollback-capable fallback
is defined. Cross-platform replacement and network filesystems are unverified.

## Phased implementation

### Phase 1 — Establish installable, local converter runtimes

**Dependencies:** the packaging response above; metadata conflicts are real.

- [x] Confirm the isolated-runtime installation choice or obtain a genuinely
  compatible shared dependency set. Recheck released metadata and inspect
  APIs against the exact versions selected.
- [x] Add the setup script, runtime requirements/locks, and a minimal runtime
  registry. Keep main application dependencies separate; explicitly declare
  every dependency used by worker code in its runtime. Provision all four
  automatically. Do not add converter optional extras to the application.
- [x] Start with Docling 2.135.0 plus RapidOCR, Marker 1.10.2, PyMuPDF4LLM
  1.28.2 plus required local OCR/plugin dependencies, and MinerU 4.0.10 Basic.
  Pin direct and resolved transitive versions. Match Torch/torchvision wheels
  and driver support for Docling/Marker; use ONNX CPU where selected. Check
  NumPy/OpenCV/Pillow imports rather than trusting their metadata constraints.
- [x] Verify runtime discovery from an editable install and from another
  working directory. Document the single setup operation and resource/cache
  locations in README. Keep Python 3.12 as the verified target; do not claim
  the project's open-ended `>=3.12` range proves worker support on every Python.

**Expected outcome:** one repeatable setup provides four usable local runtimes
without dependency overrides or user-managed backend installation.

**Verification:** on the target machine, perform a fresh setup and an idempotent
rerun, inspect all four locks/installed versions, import each converter in its
own interpreter, run `uv pip check` in each environment, and execute a tiny
local digital PDF and English scan through each native API. Observe actual
download progress and a warm-cache offline rerun. Record timings, peak resource
use where available, and unresolved binary/model failures. These are direct
smoke runs, not a new automated test suite. Do not pass this gate on resolver
success alone.

### Phase 2 — CLI, orchestration, and failure boundaries

**Dependencies:** runtime discovery from phase 1; backend implementations follow.

- [x] Add the agreed `convert` command in `cli.py`, required positional PDF,
  and required `--output`/`-o`. Keep global settings placement and the enum.
  Change settings errors to exit 2 and update scaffold help text.
- [x] Add `conversion.py` and `worker.py` for preflight, selected runtime
  invocation, input page count, staging, structured results, and cleanup.
  Use argument arrays rather than shell commands; do not import heavyweight
  converters for help/settings/version. Stream native progress and collect
  diagnostics without corrupting the worker result channel.
- [x] Separate argument/path-shape errors (2) from unreadable/corrupt/encrypted
  PDF, inference, model, export, or publication errors (1). Catch errors at
  the command boundary with useful Rich output and no false success message.
  Ensure cancellation leaves the previous result untouched.
- [x] Establish the phase 6 publisher boundary now: no backend may write
  directly to the user's output. An unfinished adapter fails explicitly.

**Expected outcome:** the CLI contract and staging lifecycle exist, with correct
exit behavior and a small dispatcher ready for real adapters.

**Verification:** directly execute help, version, settings, and both accepted
command examples. Exercise missing arguments, misplaced/unknown flags, each
invalid settings category, implicit missing/empty files, explicit missing
files, non-PDF/corrupt input, and an unwritable destination. Check exit codes
and verify heavyweight imports/downloads do not occur for informational
commands. Hash an existing result before and after a failed invocation.

### Phase 3 — Docling extraction with page comments, images, and OCR

**Dependencies:** phases 1–2 and the filtering/report choices above.

- [x] Implement the Docling adapter with English selective OCR, table structure
  recognition, local-only configuration, and referenced picture exports.
  Use native stem/artifact naming and relative image links.
- [x] Implement numbered page comments through verified provenance-aware
  serialization. Preserve native wording, reading order, tables, lists, and
  text within pictures. Inspect HTML table serialization for merged cells;
  use native table HTML when it preserves structure better, without replacing
  table content with images.
- [x] Add the conservative filtering in `images.py` immediately. Keep all
  uncertain images and record per-occurrence reasons and retained-file counts.
- [x] Capture status/errors/native warnings, reject every failed/partial page,
  and preserve native structured extraction for later review or cleanup.
  Add the initial JSON report through `reports.py`.

**Expected outcome:** the default converter produces a complete staged result
with linked useful images, invisible physical page comments, English scan
support, and an honest report. Publication still waits for phase 6.

**Verification:** directly run a digital multicolumn sample, scan, and mixed
document with a blank page, map, small symbol, illustration, repeating border,
number-heavy stat block, and merged-cell table. Compare wording/numbers/order
against the source manually and render Markdown to check comments are hidden
and images/tables work. Verify a deliberate native page-processing failure
rejects the whole result even if Docling exports placeholder pages. Check
recoverable native warnings preserve content and would permit exit 0.

### Phase 4 — Add Marker and PyMuPDF4LLM evaluation adapters

**Dependencies:** shared staging, filtering, and reporting from phases 2–3.

- [x] Implement Marker against the pinned baseline, with LLM processing off,
  local OCR, paginated native output, HTML tables where appropriate, native
  image basenames, and the minimal asset-subfolder adaptation. Reuse native
  metadata and add the namespaced application report information.
- [x] Implement PyMuPDF4LLM in layout mode with a fixed local English OCR
  plugin, page chunks, native image names, and a configured asset folder.
  Retain native headers/footers and uncertain small images. Use HTML tables
  only through the verified layout path; do not fall back to an OCR-free path
  for scans.
- [x] Verify native warning channels and every page's processing evidence.
  A backend without page-error state must propagate exceptions and native
  failures; matching `page_stats`/chunk identities is necessary but insufficient
  if it can silently skip processing. Investigate swallowed error paths.

**Expected outcome:** settings select either adapter and preserve its native
outputs while satisfying the common behavioral requirements.

**Verification:** run the same whole sample documents into separate staging
folders by changing settings files, without adding a comparison command.
Check zero/one-based page mapping, first/last/blank pages, linked images,
stat blocks, HTML tables, and warnings. Directly simulate a page exception
using a temporary development-only wrapper around a native processing call;
remove the wrapper after inspection. Confirm no partial result is publishable.
Record upstream omissions honestly rather than adding quality heuristics.

### Phase 5 — MinerU integration and strict broken-page handling

**Dependencies:** phase 1's verified Basic runtime and phases 2–4's shared work.

- [x] Implement the current stateless local parser, full page range, automatic
  OCR, Basic tier, and application-owned configuration. Disable remote and
  LLM-aided processing explicitly. Verify English capability without adding
  an unsupported language argument.
- [x] Retain native `markdown.md`, intermediate/structured JSON, and asset
  names. Materialize assets with the native writer, then insert page comments
  through native page rendering or a narrow hook. Preserve captions and
  multipage content; do not construct a replacement generic renderer.
- [x] Capture native broken-page indices before placeholder insertion, native
  diagnostics, and any dropped/failed-page outcomes. Validate original page
  mapping and apply conservative image filtering. Report limitations and
  fail the adapter's readiness gate if processing failures remain invisible.

**Expected outcome:** the fourth installed candidate meets the same local,
whole-document and failure requirements without importing obsolete APIs.

**Verification:** run digital, scanned, mixed, blank, and physically damaged
page samples. Confirm a native broken-page placeholder cannot yield success.
Check page indices against the original PDF, image materialization, warning
attribution, first-use progress, and warm-cache offline behavior. If a minimal
wrapper cannot expose actual failed pages, record the precise upstream gap
as a blocker; do not mark this phase complete or publish partial extraction.

### Phase 6 — Transactional publication and final terminal reports

**Dependencies:** staged outputs from completed adapters; filesystem exchange
support and ownership policy verification.

- [x] Implement `output.py`: sibling staging/candidate folders, manifest
  validation, owned-file inventory, unrelated-file preservation, collision
  handling, stale-file removal, destination lock, journal, atomic exchange,
  rollback, and restart recovery. Never recursively delete an asset directory
  merely because an earlier converter created it.
- [x] Gate publication on all page outcomes, required comments, resolved local
  assets, successful report serialization, and sufficient writable storage.
  Ensure links remain valid after moving the candidate out of staging.
- [x] Integrate the saved-report policy and Rich terminal summary: actual
  output, pages processed, retained image files, and available warnings.
  Report success only after durable publication; save failure diagnostics
  separately without altering the last success report.

**Expected outcome:** a successful rerun automatically replaces owned output
and removes stale assets while preserving unrelated files; a failed conversion
or precommit publication failure preserves the previous generation.

**Verification:** use disposable output trees and a real small conversion.
Check fresh output; rerun with fewer images; change converter and input stem;
add notes and unrelated files inside an asset folder; try a no-manifest folder,
unowned name collisions, invalid manifest, escaping path, edited generated
file, and symlink collision. Compare file inventories/hashes before and after.
Directly exercise failures during export/report writes, candidate construction,
exchange, flush, and rollback, plus interruption on either side of exchange
and durable commit. Use temporary development-only fault injection, not a
committed test harness. Restart and inspect journal recovery. Verify concurrent
application runs serialize and detected external edits abort publication.
Record the filesystem and the limits of crash/durability verification.

### Phase 7 — Whole-book review, documentation, and handoff

**Dependencies:** all four adapters and publication completed; representative
RPG PDFs available for local human review.

- [x] Run each configured candidate on representative full RPG books into
  separate output folders. Review source fidelity, reading order, maps/text
  association, small meaningful images, tables/stat blocks/numbers, scan OCR,
  and filtering decisions. Do not equate completed processing with correctness
  or select a winner without evidence and a separate agreed decision.
- [x] Update README with the final one-operation installation, exact agreed
  CLI examples, settings semantics, English OCR, first-use downloads and
  cache behavior, native output/report locations, ownership/collision policy,
  recovery procedure, and supported environment. Keep `settings.yaml` simple
  and defaulted to Docling. Describe how a future separate cleanup pass can
  read retained extraction without adding that feature.
- [x] Record actual verification results and remaining limitations in the
  work item or `progress.md` if needed. Keep intent unchanged unless a concrete
  conflict requires an explicitly recorded resolution. Update plan checkboxes
  and tracking at implementation phase boundaries.

**Expected outcome:** the agreed application is usable and its evaluation
limits are documented, with a fresh-conversation handoff supported by evidence.

**Verification:** run the documented setup and commands from the checkout and
another directory; rerun a full book successfully and fail a rerun deliberately
to check preservation. Run the existing checks after Python/dependency changes:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pre-commit run --all-files
uv build
```

Check worker code in the correct runtime contexts as needed; do not silence
missing third-party imports globally to make ty pass. Do not add or expand
unit tests, pytest, coverage, snapshot tools, or an automated test suite. Builds,
lint/type checks, direct executions, disposable fault exercises, and manual
source/output review implement the project's verification policy. No commit
or publication of the repository is implied by these checks.

## Assumptions and unresolved blockers at handoff

- **Proposed, not yet runtime-verified:** isolated runtimes delivered by one
  setup operation; Marker 1.10.2 baseline; MinerU Basic; filtering evidence
  rules; report supplements; Linux atomic exchange with journaled recovery.
  All need their stated phase verification before implementation is complete.
- **Confirmed shared-environment blocker:** Typer and Pillow requirements
  conflict. Separate metadata resolutions remove that particular conflict,
  but one-operation packaging and actual imports/inference remain unverified.
  Resolve a strict single-environment interpretation before changing setup.
- **Adapter gates:** Docling's numbered serialization around multipage items,
  each backend's warning/failure observability, MinerU's broken-page capture,
  native filters which may omit useful visuals, English model/plugin readiness,
  and genuinely visible model progress. None may be replaced by guessed quality
  scores, sparse-page flags, or full-page fallback images.
- **Output conflict:** Marker's native flat assets do not meet the requested
  subfolder layout without a minimal reference/path adaptation. The proposed
  exception is explicit and should be recorded with the implemented adapter.
- **Machine/filesystem gates:** all inference binaries/models, GPU execution,
  atomic exchange and crash recovery must be checked on the observed target.
  Other OSes, Python versions, and filesystems have not been verified.
- **Review material needed:** representative RPG PDFs, including a genuine
  English scan and meaningful small visuals, are required for fidelity and
  filter calibration. Small synthetic smoke inputs can establish plumbing but
  cannot establish RPG extraction quality. Do independent work before asking
  for any missing review material.

The next implementation task is phase 1. During this planning task, only the
plan and tracking documents are changed; dependencies, application source,
settings, README, and the repository lock remain unchanged.

## Implementation completion — 2026-10-07

The implementation request authorized the isolated-runtime approach. All seven
implementation phases are complete on the verified target machine. Checkboxes
record delivered changes; they do not certify exhaustive source accuracy or
every proposed verification case. Actual checks, implementation resolutions,
and limits are recorded in [progress.md](progress.md).

All four locked runtimes installed, passed dependency/import checks, and
converted digital, scanned, mixed and layout samples. Each also converted the
user-supplied 25-page Temple of 1000 Swords. Its selected-page source review is
in [review.md](review.md); no converter winner was chosen. Typer/Pillow isolation,
local model execution/download progress, MinerU broken-page observability,
Docling partial-status rejection, and Linux atomic exchange/recovery gates were
resolved and directly exercised.

Earlier unresolved installation/API gates describe the planning baseline. They
are superseded by the implementation evidence above. No known operational
blocker remains on this machine. Additional books, real scanned books,
exhaustive fidelity review, difficult cross-page layouts, decoration calibration,
and physical power-loss durability remain unverified. The agreed intent is
unchanged; the implementation does not add quality heuristics or cleanup.

Subsequently, the user approved Marker as the provisional converter selection.
The project's `settings.yaml`, README and intent now record that choice. The
implementation-time Docling selection above is historical; the existing
missing/empty-settings fallback still uses Docling. This configuration change
does not remove the other evaluation adapters or establish a permanent winner.
