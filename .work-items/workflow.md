# Engineering workflow

This file defines the project's work-item conventions for all coding agents. Read it before tracked engineering work, including when using workshop, flesh-out, rubric, documentation, planning, or implementation skills. Explicit user instructions take precedence. Keep workflow rules here; agent instruction files point here.

## Locations and records

- `WORK-ITEMS.md` at the repository root lists every item, open and complete.
- `.work-items/<slug>/` contains one item's documents. Choose a short, descriptive lowercase hyphenated slug automatically. Reuse an identified item's folder; do not rename it when the display name changes. Resolve collisions with a meaningful suffix.
- Registration creates only the folder and a `registered` row in `WORK-ITEMS.md`. Do not create `item.md`, `intent.md`, or placeholder files during registration. The row is authoritative until an item record exists. Git does not preserve empty directories; recreate a registered folder when needed after checkout without treating its absence alone as corruption.
- Create `item.md` on the first substantive save or explicit active-stage start. It then becomes authoritative for the item's name and status. Other files carry the detail. Create stage documents only when needed; do not generate empty prerequisite documents.

An `item.md` starts with YAML frontmatter using exactly these required fields:

```yaml
---
name: "CSV export"
status: captured
---
```

Quote and escape the name as needed for valid YAML. Below the frontmatter, include a heading and a brief description of the intended outcome. Add relevant document links, unresolved blockers, and a concise resume note when useful. The resume note says where to continue and what information is still missing. Do not introduce a second state or readiness field.

## Canonical statuses

| Status | Meaning | Usual saved artifact |
|---|---|---|
| `registered` | Folder and index entry reserved; no item documents yet | Index row only |
| `captured` | Recorded for later; no stage has begun | `item.md` description |
| `ideating` | Exploring the idea and promising approaches | `idea.md` |
| `fleshing-out` | Defining intent, scope, and behavior | `intent.md` |
| `planning` | Designing phased implementation steps | `plan.md` |
| `implementing` | Making and verifying the changes | `plan.md` checkboxes and `progress.md` when needed |
| `complete` | Work finished; outcome and verification recorded | Completion note in `item.md` or `progress.md` |

Status describes the current activity, never the last completed artifact. Stages may be skipped or revisited as requested. Rubric definition is optional and is not a stage; see the quality rubric section. These are the only status values; record blockers or uncertainty in prose. `registered` belongs only to index entries without an item record.

When the user clearly begins a stage for an identified, tracked item (for example, "let's plan CSV export"), update `item.md` and the master table as part of that request, even if the user uses another skill. Do not require a second tracking command. Mention the change briefly. If the discussion has not yet been captured as an item, keep it conversational until asked to capture or save.

Saving alone preserves an existing item's active status. "Save this intent" does not advance to `planning`, and saving an old idea during implementation does not move the item backwards. For a newly saved item or a registration receiving its first substantive save, use the stage actually underway: idea → `ideating`, intent → `fleshing-out`, plan → `planning`, implementation progress → `implementing`. A request merely to register or capture an item for later creates only a `registered` row and folder. Saving a substantive description for later creates `item.md` with `captured`. If a known stage start was not recorded, reconcile status from that instruction rather than from the filename.

Advance or reopen only when the user's instruction calls for it, including natural language. Complete an item when the requested implementation is finished and appropriate verification has been performed, or when the user explicitly directs completion. Saving a plan is never evidence that implementation is complete. Record any verification limitations honestly. Do not infer that completion authorizes commits, merges, deployment, or publication.

## Conversation and saving

Use `setup-workitem` for folder-only registration. Registration must not start rubric definition or any other activity. Use existing skills for the thinking: `define-rubric` for an optional qualitative quality rubric, `workshop` for ideation, `flesh-out` for intent, and the agent's planning and implementation capabilities for subsequent work. No specific `/plan` or `/ideate` command is required. `update-workitem` handles saving, tracking, listing, and resuming, and routes registration-only requests to the same folder-only procedure. Natural language requests work too.

## Quality rubric

A qualitative quality rubric is optional. It is not a status, not a prerequisite for any stage, and never required before ideation, intent, planning, or implementation. Do not prompt the user to define one or record its absence as a gap.

When the user invokes `define-rubric`, it defines independent qualitative dimensions of quality, each with a concise description of what it values. Assessment uses subjective judgments explained in words. Do not define numerical scores, rating scales, anchor points (including verbal performance levels), weights, required targets, or pass/fail thresholds. Separate acceptance conditions may describe required behavior without replacing the quality rubric. Running `define-rubric` does not change the item's status.

Once the user approves the rubric, save it as a `Quality rubric` section of the item's `intent.md`, creating `intent.md` if it does not exist. Do not save a rubric the user has not approved; a paused draft stays in the conversation unless the user explicitly asks to save it, in which case mark it as an unapproved draft. Saving the rubric preserves an existing status; if it creates the first record for a registered item, use `captured`. Writing a rubric into `intent.md` does not start `fleshing-out`.

When `workshop` runs without an approved rubric, it derives its own working qualitative rubric from the idea's intended effect: a few named, distinct dimensions with concise descriptions, assessed in ordinary language without numerical scores, anchors, or fixed rating labels. State these dimensions at the start of workshop so the user can adjust them. This working rubric guides refinement only; it is not an approved rubric and is not written into `intent.md` unless the user explicitly asks to adopt it.

Use whichever rubric applies throughout later work: ideation considers how proposed changes improve dimensions and what they sacrifice; intent develops the chosen behavior; planning connects changes and verification to relevant dimensions when a rubric exists; evaluations record per-dimension judgments with supporting evidence or reasoning. Identify the version of the work and rubric evaluated. Dimensions lacking sufficient evidence remain unassessed; missing evidence does not establish low quality. Do not infer quality from completion checkboxes or compare evaluations against changed definitions as if they were equivalent. For older numerical rubrics, use the dimension names and meanings for qualitative assessment without carrying forward scales or anchors; preserve saved definitions and historical evaluations unless the user asks to revise them.

Revise approved dimensions or their descriptions only with user direction or agreement. Preserve the reason and distinguish earlier evaluations made against the prior definition. When an approved rubric exists, completion reports available qualitative judgments, evidence, and unassessed areas. Judgments inform refinement rather than determining a mandatory completion threshold. Do not claim quality was assessed when no evaluation was performed.

Saving is deliberate: "save this", "document this intent", or `update-workitem save plan` authorizes writing the relevant artifact and updating tracking. Choose its destination and structure from these conventions; do not ask the user for a path, template, or redundant approval. A save request does not start the next stage or authorize implementation. A request to implement does authorize recording implementation progress as work proceeds.

Determine the item from the current discussion, a supplied name or folder, and existing records. Ask one focused question only if multiple plausible items or artifact types make the target ambiguous. Never silently combine separate items. Do not require a global "current item" file: each conversation identifies its own item.

Use `document-this` for synthesis if available, supplying the conventional destination. Otherwise synthesize directly: preserve settled decisions and consequential reasoning, distinguish proposals and assumptions, record unresolved questions, and omit conversational filler and secrets. Do not invent missing decisions to fill a template. Preserve unrelated existing content. Reference supplied documents in place unless the user asks to import them; write the requested work-item synthesis in its standard folder.

## Artifact guidance

Use only sections that help a future reader; no mandatory empty headings.

- **`idea.md`:** intended effect, promising core, approaches considered, working direction and its rationale, assumptions, and open possibilities. Distinguish user agreement from agent recommendations.
- **`evaluations.md`:** qualitative judgments for individual dimensions, evidence or reasoning, evaluated work version, rubric definition/version used (normally the `Quality rubric` section of `intent.md`), and unassessed dimensions. Preserve earlier evaluations when recording a new assessment so improvements and regressions can be understood.
- **`intent.md`:** intended outcome, scope and exclusions, expected behavior and important flows, constraints, observable acceptance conditions, settled decisions and reasons, unresolved questions, and an optional `Quality rubric` section holding the approved rubric (dimension names and concise descriptions of the qualities they value, without scores, rating scales, or anchors). Describe what success means without inventing implementation choices. When `define-rubric` creates `intent.md`, it contains only a brief outcome statement and the rubric; do not invent scope or behavior to fill it out. Later intent saves preserve the rubric section, and other artifacts reference it instead of duplicating it.
- **`plan.md`:** enough intent to stand alone when earlier documents do not exist; relevant code or components actually inspected; phased steps with checkboxes, concrete changes, dependencies, expected outcomes, and verification for each phase. Identify material unknowns. Do not pretend paths or commands were verified if they were not.
- **`progress.md`:** create during implementation when the plan checkboxes alone cannot explain the handoff. Record completed work, current phase, remaining steps, deviations and reasons, blockers, and verification commands or direct checks with their actual outcomes. Keep it a current handoff rather than a transcript.

Before refining, planning, or implementing, read the intent (including any approved rubric), relevant evaluations, and other relevant artifacts that exist. Missing earlier documents do not require backfilling; clarify only gaps that materially affect the work. If a change invalidates downstream plans or progress, identify the affected sections and record that they need revision. Do not silently treat outdated documents as current or rewrite all stages on a narrow save request.

## Fresh conversations and implementation

To resume, read this workflow, the selected `item.md` if present, and the stage documents needed for the request. For a registration-only item, use its index row and report that it is registered and ready for whichever stage the user chooses, without creating documents or starting work automatically. Treat saved records as the handoff, then verify current code when implementing; recorded checkboxes do not prove that code is still present or correct. Do not rely on prior chat memory. "Resume" alone preserves status and continues that activity; listing items does not start work.

Each save must leave enough context to continue in a new conversation: outcome, decisions, constraints, unresolved questions, relevant references, and next action. During implementation, update checkboxes and meaningful progress at phase boundaries and before handing control back. Follow the requested implementation scope through completion unless blocked; a phase boundary is not an automatic approval gate.

## Verification policy

Do not create or expand unit tests, add unit-test tooling, or introduce test-driven development steps. Apply this to planning as well as implementation, including when another skill ordinarily recommends unit tests. Use appropriate builds, type checks, linting, direct execution, manual or browser checks, and other behavior-level verification suited to the change. Do not add an automated test suite by default. Report what was actually checked and any limitations. Do not delete or disable existing tests as a side effect.

## Master list

Use exactly these columns in the root `WORK-ITEMS.md`:

```markdown
# Work items

| Name | Status | Folder |
|---|---|---|
```

For every `.work-items/*/item.md`, maintain one row using its name and canonical status. Folder link text and destination both use the repo-relative path, including the trailing slash: `[.work-items/csv-export/](.work-items/csv-export/)`. Escape pipes in names for Markdown tables. Keep completed items in the same table. Use stable alphabetical order by folder slug and preserve unrelated text outside the table.

Also retain one row for every registration-only item, using the name and `registered` status stored in the index. A registered row without `item.md` is valid. When a record is created, update that same row from the record rather than adding a duplicate.

Update the table after every registration, save, status change, or completion. Read existing records and rows before editing; do not replace the table with only the current conversation's items. Reconcile it from all item records plus registration-only rows if it drifts. The index cannot be fully reconstructed from records alone because registrations have no records. If a non-registered row has no readable record, or a record has invalid status or metadata, report the inconsistency and preserve its information rather than silently dropping it or inventing a status. Re-read before writing when concurrent edits are possible.

"Show open work" filters out `complete`; "show all work" includes it. Listing normally reads without mutation; report discrepancies if noticed. After a mutation, check that the affected record, document links, and index row agree. Confirm the saved path and current status concisely.
