# RPG PDF conversion application

This document records the agreed behavior for a command-line application that
converts tabletop roleplaying game adventures and rulebooks from PDF into
Markdown with linked image assets. It preserves the decisions from the design
discussion so future work can continue without the conversation.

## Purpose and priorities

The primary consumer is an AI assistant answering rules questions and helping
run adventures. Favor complete, faithful source material over visual similarity
to the PDF. Accurate rules, numbers, stat blocks, tables, reading order, and
relationships between text and maps matter especially.

The initial conversion preserves wording and organizes extracted content into
Markdown. It does not summarize, interpret rules, enrich content, or apply an
AI cleanup pass. Successful processing does not establish extraction accuracy.

Design extraction so an optional AI cleanup pass can be added later. Keep that
pass separate from extraction and retain the original extraction. Details of
the future cleanup pass, including its configuration and processing provider,
remain unspecified.

## Command and settings

- Process one PDF per command, converting the whole document. Batch conversion
  and selecting page ranges are outside the initial scope.
- The user specifies an output folder for each run. Separate folders allow
  comparison without overwriting another converter's result.
- Select the converter through `settings.yaml`. The evaluation candidates are
  `docling`, `marker`, `pymupdf4llm`, and `mineru`. The user selected `marker`
  provisionally after the Temple of 1000 Swords review. The missing/empty
  settings fallback remains `docling`.
- Converter choice is a development-time evaluation capability. Eventually
  settle on one converter; do not optimize for a permanent multi-backend
  architecture or build a comparison command initially.
- Install all four converters together rather than requiring users to install
  individual optional backends.

### Agreed command-line interface

```text
pdf-to-markdown [--settings FILE] convert PDF --output FOLDER
```

- `PDF`: required positional path to one input PDF.
- `--output FOLDER` / `-o FOLDER`: required destination folder.
- `--settings FILE`: optional global settings-file option, placed before
  `convert`. By default, read `settings.yaml` from the current working directory.

Examples:

```sh
pdf-to-markdown convert "Dragon Keep.pdf" --output "./converted/dragon-keep"
pdf-to-markdown --settings marker.yaml convert adventure.pdf -o output/marker
```

To compare converters, edit `converter` in `settings.yaml` and choose different
output folders, or maintain separate settings files such as `marker.yaml`.
There is no per-command converter override.

Supporting commands:

```sh
pdf-to-markdown show-settings
pdf-to-markdown --version
pdf-to-markdown --help
pdf-to-markdown convert --help
```

Whole-document processing, English OCR when needed, conservative decorative-image
filtering, and a saved report are automatic behavior. A successful run replaces
previous generated output; a failed run preserves it. Do not add overwrite,
page-range, language, or converter flags in the initial interface.

Exit codes:

- `0`: completed conversion, including runs with recoverable warnings.
- `1`: processing failure.
- `2`: invalid command-line arguments or settings.

The interface is agreed but `convert` is not implemented yet. The existing
settings loader supports global `--settings`, validates converter names, and
exposes `show-settings`. Missing or empty implicit settings files use the
`docling` default; a missing explicitly requested file is an error. Settings
errors currently exit with code `1`; implementation must align this with the
agreed code `2`.

## Markdown and assets

Each result is a folder containing a Markdown document and a subfolder for
linked image assets. Preserve each converter's native filenames and output
structure during evaluation rather than normalizing all converters to an
identical schema. The result must still provide linked local assets and the
page references described below.

Allow HTML tables inside the Markdown when they better preserve complex table
structure, including merged cells. Plain Markdown tables are not mandatory.

Retain original PDF page references using invisible HTML comments, for example:

```markdown
<!-- PDF page 12 -->
```

Use physical PDF page numbers starting at 1, not printed page labels. Place
references with their corresponding page content without displaying them in
rendered Markdown. Do not add a separate page-reference metadata format merely
to support this requirement.

## Image selection

Include meaningful visuals: maps, illustrations, handouts, and diagrams. Filter
decorative borders, backgrounds, and other confidently identified decorations.
Filtering is required during the initial converter evaluation, not deferred
until a converter is selected.

Keep images whose purpose is uncertain. Completeness takes priority over
eliminating every decoration: accidentally discarding a useful map symbol or
handout is worse than retaining an extra decorative image.

Do not add full-page image fallbacks as a general response to uncertain
extraction. Image filtering must not undermine the relationship between useful
visuals and their accompanying text.

## Local execution and scans

Extraction runs locally and requires no paid API. Do not send the PDF to cloud
services for conversion.

Support scanned PDFs using local OCR where pages lack usable embedded text;
prefer usable embedded text rather than forcing OCR on every page. OCR supports
English only initially.

Download required model weights automatically when a converter first needs
them, with visible download progress. Downloading models is distinct from
uploading document content. First use may take longer and require internet
access; PDF processing remains local.

## Warnings, failures, and replacement

If a table or stat block cannot be extracted reliably but processing can
continue, keep the extracted content and report any available converter warning.
Do not replace the region with an image fallback or stop solely for that
recoverable warning.

Initially rely on converter warnings and human review. Do not add custom
extraction-quality heuristics such as flagging sparse pages. Converters may fail
to detect incorrect numbers, missing text, or other errors; reports must not
imply all such problems have been detected.

If any page fails processing, treat the run as failed. Do not publish a partial
book or replace the previous successful result with it.

Reruns automatically replace the previous conversion without requiring an
`--overwrite` flag. Convert into a temporary folder and replace the previous
output only after the new run finishes successfully. A failed rerun preserves
the previous successful output.

The working replacement approach is to preserve unrelated files while removing
stale generated assets. How the application identifies owned files and safely
publishes a replacement remains unresolved.

## Reporting

Display a brief Rich terminal summary with the output location, pages processed,
images saved, and available warnings. Also save a conversion report containing
available warnings and the converter name and version. Reuse a converter's
native report where available; a common report format has not been agreed.

Reports support comparison and review. Distinguish completed processing from
verified content accuracy and report failed runs honestly.

## Observable acceptance conditions

- A single whole-book conversion produces Markdown with linked local images in
  the requested output folder.
- The selected evaluation converter comes from the validated settings file.
- Wording is preserved through extraction without an AI rewrite or summary.
- Physical page references are present as comments and invisible when rendered.
- Complex tables may retain HTML structure.
- Meaningful visuals are retained; confidently identified decorations are
  filtered, and uncertain images are kept.
- English scans can be processed with local OCR and no paid conversion API.
- Required models download automatically with visible progress on first use.
- The terminal summary and saved report identify the result and available
  warnings, including converter details in the saved report.
- A successful rerun replaces its previous generated result automatically;
  any failed page prevents replacement and preserves the prior output.

## Current implementation and unresolved details

The project has a Typer CLI, Rich output, a validated converter setting, an
editable tool installation, and Ruff and ty pre-commit checks. The converter
integrations and the behavior described above are not implemented yet.

Before implementation, resolve these details without reopening settled scope:

- Verify that all four converters and their OCR/model dependencies can coexist
  and run on the target machine.
- Determine how each native output exposes page boundaries, linked assets,
  failed pages, recoverable warnings, and model download progress.
- Define a conservative local method for identifying decorative images while
  retaining uncertain and meaningful visuals.
- Define file ownership and safe replacement behavior, including stale assets,
  unrelated files, and failures during publication.
- Select the saved-report format where native reports are insufficient.

Marker is the user-approved provisional project selection following the
[Temple of 1000 Swords review](review.md). Its sampled stat blocks, map and prose
supported the recommendation, while the alternatives showed reading-order,
duplication, noisy OCR or table-association concerns. This selected-page review
of one book does not establish a permanent winner or exhaustive accuracy.
Docling was the initial research recommendation; all four candidates remain
available for further evaluation.
