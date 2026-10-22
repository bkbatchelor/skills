---
name: docs-curator
description: Curates one or more document sources (local folders and git repos, local or remote, roughly 1k to 10k files of pptx, docx, xlsx, pdf, md, txt, html, csv, json, yaml, toml, ini, properties and images) before they are ingested into a knowledge graph, so the graph is not built on copies, stale revisions and contradictions. Finds duplicate documents (including the same content in different formats), outdated or superseded revisions, and contradictory information. It never modifies a source. It writes proposals for the user to review, then builds docs-curator-out/curated/, a clean tree of Markdown conversions and hard-linked native files with provenance, ready for /graphify. Use whenever the user wants to dedupe, clean up, curate, audit, consolidate or "get ready for Graphify" a document repo, shared drive export or pile of notes and decks, find outdated or conflicting docs, check which version of a doc is current, or convert pptx/docx/xlsx/pdf to Markdown for a knowledge graph, RAG or search index. Also use when another skill (graphify, research, knowledge-base or RAG building, documentation review) needs a deduplicated, current set of documents. Those should read the curated package instead of walking the raw sources. Not for editing or summarizing a single file, for code repositories, for live document sync, or for sources that must be changed in place.
metadata:
  version: 1.0.0
---

# Docs Curator

Two commands curate a set of document sources. The first writes proposals for the user to review, and the second builds the clean tree from the accepted ones:

```bash
~/Projects/skills/docs-curator/scripts/curate.py analyze --sources sources.toml
~/Projects/skills/docs-curator/scripts/curate.py apply
```

The scripts are in this skill's `scripts/` folder. Use the absolute path of the directory this SKILL.md was loaded from, since the skill may be linked into several places. It needs `python3` 3.11 or newer (standard library only). Conversions use `pdftotext` and `pdfinfo` (poppler) for PDFs and `soffice` (LibreOffice) for legacy `.doc`, `.xls` and `.ppt`. `tesseract` is optional (OCR). Every external tool is called as a subprocess, and a missing one only affects the formats that need it.

## Saved preferences

These live in `config.env` next to this file and are read on every run. `DOCS_CURATOR_*` environment variables override them. To change a default permanently, edit `config.env`.

| Setting | Value |
|---|---|
| Near-duplicate threshold | `0.90` (5-word shingle Jaccard); cross-format `0.80` |
| Revision family threshold | `0.50` text similarity, plus a version, date or draft token in a name (or a git rename) |
| Keeper among duplicates | source priority, then `md > pptx = docx = xlsx > pdf > image`, then newest |
| Environment scope tokens | `dev, development, test, qa, staging, stage, uat, prod, production, local`, plus regions and tenants |
| Review packet cap | `200`; overflow is listed as unreviewed |
| OCR | off (`DOCS_CURATOR_OCR=1` to turn on) |
| Output folder | `./docs-curator-out/`, or `--out DIR` |
| Sources | `sources.toml` (see `sources.example.toml`), or paths and URLs on the command line |

## What the scripts do

1. **`analyze` reads the sources, read-only.** Local folders and repos are read in place. A remote URL is shallow-cloned (`git clone --depth 50 [--branch ref]`) into `docs-curator-out/sources/<name>/` with the user's own git credentials, and fetched again on re-runs. Tracked files, commit dates and rename history come from git. Git-LFS pointer stubs are detected and reported instead of read.
2. **Extracts text.** pptx, docx and xlsx are read from their zip XML, PDFs go through `pdftotext -layout`, legacy office files through `soffice` into the modern format, html, csv and config files directly. Results are cached by sha256, so re-runs only extract new or changed files. Unknown file types are listed as "unhandled", never dropped silently.
3. **Finds duplicates.** Exact bytes, then normalized text (same words in any format), then near-duplicates (MinHash plus exact Jaccard). The keeper is chosen by source priority, then format, then recency.
4. **Finds superseded files.** Explicit `DEPRECATED` / `SUPERSEDED` / `replaced by <file>` markers, and revision families (`spec_v1`, `spec_v2`, `spec_final`, drafts, dated copies, git renames) ranked by markers, then version tokens, then the newest reliable date, with mtime only as a tie-break.
5. **Flags contradictions.** Config files (json, yaml, toml, ini, properties) are compared key by key, but only within the same logical file and environment scope, so `application-dev` vs `application-prod` is never a conflict. Prose claims are grouped by topic and written to review packets.
6. **Writes the proposals.** `decisions.json` has one entry per finding with a `status` of `proposed`, `accept` or `reject`. Only exact and normalized duplicates and markers that name an existing file start as `accept`. Everything else, and every conflict, starts as `proposed`. Re-running `analyze` keeps the statuses already set. It also writes `packets/`, `REPORT.md` and `report.html`.
7. **`record` stores Claude's verdicts** on the packets in `decisions.json`. It never changes a status.
8. **`apply` builds `curated/`** from accepted proposals only. It never runs Graphify; it prints the command to run.

Reference for the rules and thresholds: `references/heuristics.md`.

## The output package

Everything goes in `docs-curator-out/`:

| Path | Contents |
|---|---|
| `decisions.json` | Every proposal with evidence, `status`, `keeper` or `suggested_winner`, and Claude's `verdict` once recorded |
| `REPORT.md`, `report.html` | The report: counts, each proposal with evidence, unhandled files. `report.html` is self-contained |
| `packets/<id>.json` | Review packets for Claude: low-confidence revision families and prose conflicts |
| `verdicts/` | Copies of the verdict files that `record` merged |
| `curated/<source>/<relpath>` | Native Graphify-readable files (md, txt, yaml, json, png, jpg, gif, webp, svg), hard-linked (copied if linking fails) |
| `curated/<source>/<relpath>.md` | Converted files (pptx, docx, xlsx, pdf, html, csv, toml, ini, properties, legacy office), with provenance frontmatter |
| `curated/_manifest.json` | Every curated file, with the same provenance, plus every unhandled file |
| `quarantine.json` | Every file left out of `curated/`, with the reason and the proposal id |
| `sources/`, `cache/`, `inventory.json` | Clones of remote sources, the extraction cache, and the internal file list |

Converted files start with frontmatter: `source`, `source_location`, `commit`, `path`, `sha256`, `format`, `revision_rank`, `supersedes`, `duplicates_of_this` and `conflicts_with` (a list of `{path, proposal_id, summary}`). The exact schema of every file is in `references/format.md`. Read it before writing code that consumes the package.

## Usage

```
curate.py analyze [PATH|URL ...] [--sources sources.toml] [--out DIR] [--force] [--dry-run]
curate.py record VERDICTS [--out DIR]      VERDICTS is a JSON file or a folder of them
curate.py apply [--out DIR]
curate.py status [--out DIR]
```

- One-off runs work without a `sources.toml`: `curate.py analyze ./docs ~/Exports/drive https://host/repo.git`. The source name is the basename and the priority is 0. Use `sources.toml` when priorities matter: copy `sources.example.toml` and edit it. Entries have `name`, `path` or `url`, optional `ref`, `priority` (an integer, higher wins), and optional `include` / `exclude` glob lists.
- `--force` ignores the extraction cache. `--dry-run` lists the sources and file counts, without cloning or writing anything.

Each subcommand prints one JSON line on stdout and progress on stderr. The `analyze` line looks like:

```json
{"out_dir": ".../docs-curator-out", "files": 36, "unhandled": 1, "proposals": {"duplicate:exact": 2, "revision:version_family": 2, "conflict:prose": 1, "...": 0}, "preaccepted": 5, "needs_decision": 4, "packets": 3, "unreviewed": 0, "kept_statuses": 0, "cache_hits": 2, "cache_misses": 33, "warnings": []}
```

`apply` ends with `"next": "/graphify docs-curator-out/curated"`.

## How to handle a request

1. **Pin down the sources.** If the user names folders or repos, use them. If they have a `sources.toml`, use it. Ask about priority only when the sources overlap (an official repo and a shared-drive export of the same material) and nothing says which one wins. Remote URLs are cloned with the user's own credentials. If a clone fails on authentication, tell the user rather than trying other ways in.
2. **Run `analyze`** with `--out` set if the user named a folder. Don't ask the user to confirm routine runs. It reads sources only. A first run over several thousand files can take minutes, mostly in conversions, and re-runs are fast.
3. **Review packets.** Read `references/review.md` first. Run `status` to see which packets lack a verdict. Up to about 20 packets, judge them yourself. Above that, fan out to parallel subagents, each taking a slice of the packets and writing one verdicts file, as `review.md` describes. Then run `record` once on the file or folder and read its `errors`. Verdicts never change a status.
4. **Show the report.** Give the user the path to `REPORT.md` (or `report.html`) and a short summary: how many duplicates are pre-accepted, which revision families and conflicts need a decision, with your verdicts next to the script's suggestions, plus unhandled files and anything over the packet cap. Say that nothing has been left out of `curated/` yet.
5. **The user accepts or rejects.** They edit `status` in `decisions.json`, or tell you what to set. Only change a status when they ask you to, for example "accept everything except the conflicts". A proposal can also carry a `final_keeper` they set. Re-running `analyze` after a source changes keeps these decisions.
6. **Run `apply`.** It builds `curated/` from accepted proposals only, so proposals still `proposed` have no effect. Report the counts (curated, converted, quarantined, unhandled) and where `quarantine.json` is.
7. **Print the Graphify command**, from the `next` field: `/graphify docs-curator-out/curated`. Don't run it unless the user asks.

If the user wants something the outputs don't hold (a list of the stale decks, which source has the most duplicates), produce it from `decisions.json` and `quarantine.json`. Don't rescan the sources.

## Known behavior and limits

- **Sources are never modified.** Excluding a file means leaving it out of `curated/`, recorded in `quarantine.json`. Cloned remote sources live under `docs-curator-out/sources/`. Hard links in `curated/` share data with the source files, so editing a source file in place changes the curated copy; re-run `analyze` and `apply` after changes.
- **`apply` checks the sources.** If a file changed since `analyze`, it stops and asks for a new `analyze`.
- **Conflicts keep both documents** by default. The conflict is recorded in each document's frontmatter or manifest entry, with a suggested winner. The skill never drops either side. To leave the losing document out of the graph, add it to the source's `exclude` list in `sources.toml` and re-run `analyze`.
- **Prose contradictions are candidates, not proof.** The script only pairs sentences about the same subject with different numbers or opposite negation. Paraphrased contradictions without such a difference are not found. Claude's verdict is the filter.
- **Revision ranking can be wrong** when files have no version tokens and no dates, such as copies on a shared drive with only mtimes. Those families are low confidence and go to review. A `draft` is never trusted to be the newest.
- **YAML is a block-subset parser.** Anchors, aliases, tags, flow collections and multi-document files set `partial_parse`: the file is kept and compared on the keys that were read, and the report lists it. Details in `references/heuristics.md`.
- **Topic clustering is keyword-based**, with at most 40 documents per cluster, so two documents about one subject in different vocabularies may never be compared.
- **Formats.** PDFs without a text layer produce no text unless OCR is on. Spreadsheets and CSVs are cut at 200 rows per sheet. Text-only formats other than those listed (for example `.rst`, `.docm`, `.odt`) are listed as unhandled.
- **Git history is shallow for clones** (`--depth 50`), so commit dates and renames older than that are not seen. Local repos use their full history.
- **Graphify.** `curated/` holds Markdown and plain files that Graphify reads without extras. docs-curator converts pptx, xlsx, docx and pdf itself because Graphify cannot read `.pptx`, and its PDF, XLSX and DOCX readers need libraries that may not be installed.
- **Speed.** Hashing and git history are fast. Each legacy office conversion is a `soffice` run of a few seconds. Everything is cached by content hash.

## For Graphify and other skills

`curated/` and its manifest are an input format other skills rely on. That only works if the shape never drifts, so:

- Consume the package through the files and fields in `references/format.md`. Check `schema_version` (currently `1.0`) and treat an unknown major version as unsupported.
- Don't edit files in `curated/` or `_manifest.json` by hand; `apply` rebuilds the whole folder. Change `decisions.json` and run `apply` again. Put derived artifacts in your own folder, not in `curated/`.
- A converted file's frontmatter says where it came from (`source`, `path`, `commit`) and what it replaced (`supersedes`, `duplicates_of_this`) or disagrees with (`conflicts_with`). Surface that provenance when you answer from these documents, particularly `conflicts_with`.
- If you are another skill and need a curated set, check for an existing `docs-curator-out/curated/_manifest.json` first, and run this skill's `analyze` and `apply` rather than writing your own deduplication.
- If the format really must change, change it here: bump `SCHEMA_VERSION` in `scripts/curator/__init__.py`, update `references/format.md`, and say what changed.
