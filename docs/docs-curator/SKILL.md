---
name: docs-curator
description: Curates a large, read-only folder of documents (.pptx .pdf .md .xlsx .txt .docx) into a deduplicated staging tree for Graphify. Removes byte-identical, cross-format and near duplicates, excludes superseded revisions, and flags contradictions and conflicting names, then writes every kept document as Markdown with front matter. Use whenever the user wants to dedupe, clean up, curate, or prepare a document repository or folder for Graphify or a knowledge graph. Never modifies the source and never runs Graphify; it prints the command. Skip for a single file (use heavy-file-ingestion), for building the graph itself (use graphify), and for any request to modify or delete the source documents.
metadata:
  version: 1.4.0
---

# Docs Curator

Three phases: a script analyzes, you judge the clusters, a script applies. The source folder is only ever read.

## Triggers

Run this skill when the user wants a folder of documents deduplicated, cleaned up, or prepared for Graphify: "curate these docs", "dedupe this repo before graphify", "which of these files are duplicates or outdated".

Skip it for:
- One file or a handful of files: use `heavy-file-ingestion`.
- Building or querying the graph: use `graphify`. This skill prints the Graphify command and never runs it.
- Editing, moving, or deleting the user's documents. Nothing under `--source` is created, changed, or removed.

## Prerequisites

The runtime needs only this folder's `SKILL.md`, `scripts/`, `references/` and `requirements.txt`. Set `SKILL=~/.claude/skills/docs-curator` (or wherever it is installed) and run everything through:

```bash
RUN="uv run --no-project --with-requirements $SKILL/requirements.txt"
$RUN bash $SKILL/scripts/check_env.sh        # exit 0 means ready; otherwise it names what is missing
```

System: `uv`, `python3` (3.10+), and `soffice` (LibreOffice, for `.pptx` to PDF). The embedding model (`BAAI/bge-small-en-v1.5`) downloads once on first use. If it cannot load, `analyze` stops; the user can set `embedding_backend: tfidf` in `config.yaml`. If you have to fall back to Python 3.12 (`--python 3.12`) because a wheel is missing, say so.

## Workflow

The output folder defaults to `~/curated/<project-name>/`, where `<project-name>` is the basename of `--source`. Omit `--out` to use it; a different `--out` must still be outside `--source`. Everything generated lives there: `staging/`, `.docs-curator/` and `graphify-out/`. Nothing generated goes in the project folder.

1. **Analyze.** `$RUN python $SKILL/scripts/curate.py analyze --source <src> --out <out>`. It inventories and hashes the files, extracts text, groups duplicates, finds revision chains and topic clusters, and writes one queue item per cluster to `<out>/.docs-curator/work/queue/<cluster_id>.json`. Re-running costs nothing for unchanged files.
2. **Review each queued cluster** (the LLM phase, done by you):
   - Read the queue item, then each member's `text_path`. Read the first ~6,000 words by default (`read_words` in the item). For longer members, diff them against the others instead of reading end to end. If you did not read everything, set `partial_read: true`.
   - Decide whether any member **supersedes** another (a later revision, an updated copy) and whether members **contradict** each other on a fact (numbers, dates, limits, owners).
   - Write `<out>/.docs-curator/work/verdicts/<cluster_id>.json` following `references/verdict-schema.md`. Write a file even when you find nothing (`{"cluster_id": "...", "reviewed": true}`) so the cluster counts as reviewed.
   - Quote contradicting statements verbatim; `apply` checks each quote against the document and marks misses `[quote not verified]`.
   - Only claim a supersession you can defend from the text. Give honest `confidence` (0 to 1). Below 0.75 the older file is kept and flagged.
   - Unique content in a superseded file goes in `unique_content`; that file also gets a copy under `_curated/historical/`.
3. **Apply.** `$RUN python $SKILL/scripts/curate.py apply --source <src> --out <out>`. It builds `<out>/staging/`, writes `REPORT.md`, `decisions.jsonl` and `state.json` under `<out>/.docs-curator/`, and prints the next steps.
4. **Link.** `$RUN python $SKILL/scripts/curate.py link --source <src> --out <out>`. It creates `<out>/graphify-out/` and two symlinks in the project root: `<src>/graphify-out` and `<src>/.docs-curator`, pointing at `<out>/graphify-out` and `<out>/.docs-curator` (the working directory). Graphify writes `graphify-out/` into the directory it runs from, so running it from `<src>` sends its output to `<out>` instead of filling the project. It refuses to replace an existing `graphify-out` that is not that symlink; tell the user. Offer `--gitignore project` (appends `.docs-curator` to `<src>/.gitignore`) or `--gitignore global` (appends it to the global git excludes file: `core.excludesFile`, else `~/.config/git/ignore`); only pass it if the user says yes. The entry has no trailing slash because git treats a symlink as a file.
5. **Report to the user:** the totals, the report path, anything under "Flagged but kept", "Filed under conflicting names", "Identifier collisions", the conflicts found, and the printed `cd <src> && /graphify <out>/staging` line. Do not run Graphify.

If the queue was capped (`max_llm_clusters_per_run`, default 25, largest clusters first), the rest are listed in the report. Tell the user, and run analyze, review, and apply again to pick them up; existing verdicts are kept.

## Updating after the source changed

When files were added, modified or removed after a finished run, use `update` instead of a full re-run: `$RUN python $SKILL/scripts/curate.py update --source <src> --out <out>`. It requires an earlier `analyze`, re-runs it, and writes `<out>/.docs-curator/changes.json` with `added`, `modified`, `removed`, `affected_clusters`, `queued_clusters` and `stale_verdicts`. Only clusters containing a new or modified file get a new id, so only they are queued; every other verdict is kept.

1. Run `update` and tell the user the added, modified and removed counts.
2. Review the queued clusters exactly as in step 2 above, then run `apply` and `link` (if needed).
3. `stale_verdicts` are verdicts for clusters that no longer exist (a member changed or was removed). Leave the files in place; `apply` warns about them. Mention them to the user.
4. A removed source file disappears from `staging/` when `apply` rebuilds it.

If nothing changed, `update` says so and `staging/` is already current.

## Settings and overrides

Both files are optional and live in `<out>/`. Missing means defaults. The settings in effect are written to `state.json`.

- `config.yaml`: for example `near_duplicate_action: exclude`, `near_duplicate_threshold: 0.90`, `low_confidence_threshold: 0.75`, `max_llm_clusters_per_run: 25`, `revision_chain_scope: directory|corpus`, `embedding_backend: fastembed|tfidf`. Unknown keys are rejected. Defaults and names are in `scripts/curate.py` (`DEFAULTS`).
- `overrides.yaml`: a list of `{path, action: include|exclude, note}` keyed by source-relative path. An override wins over every rule except unreadable and not-ingestible files. Offer this when the user disagrees with one file's fate, then re-run `apply`.

`near_duplicate_action` defaults to `flag` (kept and reported). Near-identical text is not proof of duplication when identity lives in an identifier, as in form libraries. Suggest `exclude` only for prose corpora where near-identical text really is redundant, and ask first.

## What staging looks like

- Every kept document except `.pptx` becomes Markdown named `<source path>.md` (a source `.md` keeps its name), with front matter: `source_path`, `source_format`, `sha256`, `status`, `description`. Text only: layout, images and formatting of PDF, Word and Excel files are not carried over.
- A kept `.pptx` becomes `<name>.pptx.pdf` plus `<name>.pptx.notes.md` (speaker notes).
- `_curated/CONFLICTS.md` lists contradictions; `_curated/historical/` holds superseded files that had unique content.
- Text-free documents (scans) are staged with an empty body and listed under "Flagged but kept"; there is no OCR. Corrupt or password-protected files are `unreadable`; other extensions are `not_ingestible`.

## Hard rules

- Never write under `--source`, except the single `graphify-out` symlink that `link` creates. Never pass an `--out` inside it. Graphify and the source documents are not yours to run or change.
- If `apply` says the source changed since analyze, run analyze again; do not edit the analysis files.
- Stop and ask if: Graphify starts accepting `.pptx` (this design assumes it does not), the embedding model will not load and the user has not chosen tfidf, or a requirement is ambiguous in a way that would change which documents reach staging.
- Thresholds were tuned on a synthetic corpus only. After the first real run, suggest the user spot-check "Flagged but kept" and the superseded list.
