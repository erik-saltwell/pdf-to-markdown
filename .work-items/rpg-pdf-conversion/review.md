# Source-fidelity review

Reviewed on 2026-10-07 during implementation. This is a selected-page review of
one user-supplied book, not an exhaustive accuracy certification. After the
review, the user approved Marker as the provisional project selection.

## Source and outputs

Source: `/home/eriksalt/Downloads/Old School Essentials/Temple of 1000 swords/temple-of-1000-swords-v1.pdf`.

The PDF has 25 physical pages and usable embedded text. Input SHA-256:
`22af071e27ccaa56230ba723862c2abae9a72949a727dfa80052589655da8373`.

All converters completed the entire book and published their results. Output
folders are under `converted/temple-of-1000-swords/`, ignored by Git. Counts
below come from the final saved reports; warnings include native library and
processing diagnostics, not content-accuracy scores.

| Converter | Version | Pages | Linked image files | Warnings | Filtered references |
|---|---|---|---|---|---|
| Docling | 2.135.0 | 25 | 17 | 9 | 67 |
| Marker | 1.10.2 | 25 | 11 | 6 | 66 |
| PyMuPDF4LLM | 1.28.2 | 25 | 9 | 0 | 0 |
| MinerU | 4.0.10 | 25 | 17 | 2 | 0 |

Markdown artifacts:

- [Docling](../../converted/temple-of-1000-swords/docling/temple-of-1000-swords-v1.md)
- [Marker](../../converted/temple-of-1000-swords/marker/temple-of-1000-swords-v1.md)
- [PyMuPDF4LLM](../../converted/temple-of-1000-swords/pymupdf4llm/temple-of-1000-swords-v1.md)
- [MinerU](../../converted/temple-of-1000-swords/mineru/markdown.md)

These links resolve from this work-item folder through the repository root.
The generated files are local review artifacts, not repository source files.

## What was checked

Each Markdown document has the exact physical page-comment sequence 1–25.
CommonMark/HTML rendering retains the comments invisibly. Every linked image
resolves to a local file after publication. Reports identify converter/runtime
versions and retain `accuracy_verified: false`.

The source's physical page 9 map and all four linked map assets were inspected
visually. They retain the dungeon rooms, north arrow, colored water, and
`1 sq. = 10 feet` scale. The thin outer rectangle remains with the useful map;
it is not removed merely because it looks like a border. Docling's final
picture export uses `images_scale=2.0` to retain more detail than its default
low-resolution export.

Physical page 12 was compared with the source's merfolk stat block and island
room. All candidates retain the sampled AC/HD/THAC0 values, saving throws,
leader rules, treasure count/value, and Lydia's 4HD leader treatment. Physical
page 24 retains the sampled gelatinous-cube and iron-mongrel statistics,
including hit points, attack dice, THAC0 bonuses, XP values, paralysis duration,
and the Door Sword's text. Formatting and apostrophes vary by converter.

Physical pages 5 and 7–8 were reviewed for encounter/search rules and table
structure, including the encounter chance/dice, search duration and injury
rule, and selected sword-table values. HTML tables remain available rather
than requiring conversion into plain Markdown tables. This was a selected
row/value review, not a cell-by-cell audit of every table.

## Observed differences and limits

**Docling:** sampled numeric rules remain readable and the map is retained.
On page 5, the native reading order places the random-encounter section between
the first adventure hook and the remaining hooks. On page 12, it duplicates a
fragment of the island description. Page 9 includes imperfect OCR of map
labels, including a spurious character. The application preserves these native
results and does not introduce a cleanup or rewriting pass. Recoverable empty
OCR-result warnings are saved, including RapidOCR's non-propagating log channel.

**Marker:** the sampled room and stat-block text is readable, and the map is
retained. Warnings include native PDF repair messages, Pydantic deprecations,
and the upstream warning about forking a multithreaded process. In a separate
synthetic layout sample, Marker produced an empty table on a blank page without
an extraction warning; it demonstrates why processing success is not a content
accuracy claim.

**PyMuPDF4LLM:** sampled stat blocks and prose retain the reviewed numbers, and
the map image is useful. The map page also contains substantial noisy OCR text.
The heading `SEARCHINGFORSWORDS` retains the source text-extraction spacing
rather than adding editorial corrections. Zero warnings did not identify the
map OCR noise. In the synthetic scan, it retained OCR text but did not link the
map embedded in that scan.

**MinerU:** sampled numerical rules and the map are retained. The sword table
on page 8 is emitted as a large combined HTML table with substantial spans and
some joined words; its associations deserve further review. Native table crops
are linked alongside table text. Recoverable warnings include unauthenticated
model-hub access and a native PDF dependency warning; document conversion still
runs locally.

Blank/transparent supplemental source-image references were filtered in
Docling and Marker. Filtering identities and reasons are in their reports.
The useful page 9 map survived in every candidate. Repeating decorative-border
classification was exercised separately with a deliberately simple outline;
this book does not establish a general RPG decoration classifier.

The review supports application usability and exposes real converter
limitations. It does not establish a winner, verify every word/number, validate
large scanned books, or cover every difficult cross-page layout. Further
converter evaluation should use additional books and real English scans.
