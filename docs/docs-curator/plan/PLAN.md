# doc-curator — build plan

Status: built on branch `feat/docs-curator-skill` (see `DECISIONS.md` for what changed from this plan: location `docs/docs-curator/`, name `docs-curator`, no numpy pin). The earlier pause to revisit one decision was superseded by the instruction to build from this plan as written.

Inputs:
- Requirements: `/home/bkb/Documents/research/doc-curator-extraction.md`
- Prior build record (the original code is gone): `/home/bkb/Downloads/doc-curator-as-built.md`

## What it is

A skill that takes a large, read-only repository of documents (`.pptx .pdf .md .xlsx .txt .docx`) and produces a curated staging tree for Graphify. It removes exact, cross-format and near duplicates, excludes superseded revisions, and flags contradictions and naming conflicts. It never modifies the source and never runs Graphify (it prints `/graphify <out>/staging`).

Three phases: `curate.py analyze` (deterministic), an LLM phase (Claude, following `SKILL.md`, one verdict file per cluster), `curate.py apply` (deterministic).

## Environment facts (checked 2026-10-27)

- `research/doc-curator/` is empty and untracked. The original build at `/mnt/dev/.../doc-curator` is gone, so this is a clean rebuild.
- Host has Python 3.14, `uv`, `soffice`, `markitdown`, and the `docker` CLI. The docker daemon was not confirmed. No Python dependencies are installed globally.
- Graphify upgraded to **0.9.97** with extras `svg,pdf,office,google` (tool pinned `==0.9.97`). The installed Graphify skill was refreshed to 0.9.97 (backup in the session scratchpad).
- `.pptx` is still absent from `graphify.detect`, so the stop condition is not triggered and pptx → PDF conversion stays.
- Accepted extensions moved between constants: `.yaml/.yml` are now in `CODE_EXTENSIONS`; `.pdf` is in `PAPER_EXTENSIONS`; `.docx/.xlsx` are in `OFFICE_EXTENSIONS`. The staging-extension test must take the union of all `*_EXTENSIONS` constants.
- Repo conventions: version bump hooks set `metadata.version` in `SKILL.md`; `CLAUDE.md` requires README sync (table row, `####` details section, Project Structure tree). Never commit to `main`.

## Decisions

### Layout, runtime, process
- **Q1** Skill content sits directly in `research/doc-curator/`: `SKILL.md`, `scripts/curate.py`, `scripts/check_env.sh`, `references/verdict-schema.md`, `requirements.txt`. Dev-only siblings: `tests/`, `docker/`, `DECISIONS.md`. `SKILL.md` says the runtime needs only `SKILL.md`, `scripts/`, `references/`. Branch `feat/doc-curator-skill`.
- **Q2** Run via `uv run --no-project --with-requirements <skill>/requirements.txt python scripts/curate.py …`. Code stays 3.10-compatible; Dockerfile pins 3.11. If a pinned package lacks 3.14 wheels (`fastembed`/onnxruntime is the risk), fall back to `uv run --python 3.12`. `requirements.txt` pins `graphifyy[pdf,office,google]==0.9.97`.
- **Q4** Formats the sources never defined (verdict schema, queue item, config, overrides, `state.json`, revision weights, `CONFLICTS.md`, `historical/`) are designed fresh, recorded in `DECISIONS.md`, and `references/` where the LLM phase needs them.
- **Q5** Full scope: synthetic corpus with every planted case, `corpus_expected.yaml`, fixture verdicts, `score.py`, pytest suite (test every rule settled in the requirements, not a test-count target), Dockerfile. Docker build gate runs only if the daemon responds; otherwise report it as not run. Real-corpus dry runs are out of scope.
- **Q21** Build in this session, in order: `DECISIONS.md`, corpus and answer key, `curate.py` with tests, `SKILL.md` and verdict reference, `check_env.sh` and Dockerfile, gates. One checkpoint after the deterministic core passes. Commit only when the user says so; no push or PR until asked. The LLM-phase gate (gate 7) is done by hand in this session.
- **Q22** `SKILL.md` description in `heavy-file-ingestion` style with a `## Triggers` section: use for deduping or preparing a document folder for Graphify; skip for single files (heavy-file-ingestion), building the graph (graphify), and modifying the source.
- **Q23** Symlink `~/.claude/skills/doc-curator` → `research/doc-curator`. Remove the stray empty `docs/docs-curator/` line from the README tree during README sync.
- **Q24** Done: installed Graphify skill refreshed to 0.9.97; only `.graphify_version` changed.

### Staging output
- **Q3** Every non-`.pptx` file is staged as Markdown; the body is the Phase 1 cached extraction. The fidelity loss for pdf/docx/xlsx (text only) is accepted and recorded in `DECISIONS.md`.
- **Q6** Staged name = source-relative path with `.md` appended for every non-`.md` source (`report.pdf.md`, `todo.txt.md`). Source `.md` keeps its name. A kept `.pptx` becomes `deck.pptx.pdf` + `deck.pptx.notes.md`.
- **Q7** Front-matter `status` = the `decisions.jsonl` `reason` (kept copy of an exact-duplicate group reads `unique`). Front matter goes on every generated `.md`, including `.notes.md` and `_curated/CONFLICTS.md` (`source_format: generated`). The `.notes.md` carries `source_path`, `sha256`, `status` for the PDF/notes pair. Fields: `source_path`, `source_format`, `sha256`, `status`, `description`; no tags and no revision info. `description` is deterministic: first H1/H2, else first non-empty line, truncated to ~160 chars; filename stem for text-free documents.
- **Q8** Existing front matter in a source `.md` is parsed and nested under `source_front_matter`. If it does not parse, it stays in the body and a warning goes in `REPORT.md`.
- **Q9** Superseded documents are excluded and listed in `REPORT.md`. If the verdict's `unique_content` is non-empty, a full Markdown copy (`status: superseded`) goes in `_curated/historical/<source-relative path>.md`.
- **Q13** The hard-link/copy fallback rule is dropped (every staged file is generated). `REPORT.md` "Staging method" says: generated (Markdown from cached extraction; PDF via LibreOffice). LibreOffice conversions stay serialized.
- **Q17** Text-free document: staged as `.md` with an empty body, filename-stem description, listed under "Flagged but kept", no OCR. Extraction error (corrupt, password-protected): `action: unreadable`, not staged. Extension outside the six: `not_ingestible`, not staged. Failed `.pptx` conversion: `unreadable` with reason `conversion_failed`.

### Analysis rules
- **Q12** Default `embedding_backend: fastembed` with `BAAI/bge-small-en-v1.5`. If the model cannot load, `analyze` exits non-zero with a clear message unless config sets `embedding_backend: tfidf`. The backend is recorded in `state.json` and `REPORT.md`.
- **Q14** Keeper format rank: `md > docx > pptx > xlsx > pdf > txt`. Tie-break order: format rank, text richness, `keeper_prefers_descriptive_name`, path order.
- **Q15** Revision chains: members share a normalized filename stem (markers and version tokens stripped) within a directory (`revision_chain_scope: directory|corpus`, default `directory`) and are topically clustered. Signals, each voting an order: (1) strict filename marker or version number in the name, (2) ambiguous marker (`final latest current draft`) counting only if the text agrees, (3) in-text version/revision/date line, (4) docx/pptx core-property dates, (5) `filesystem_mtime`. A non-mtime signal contradicting the chosen order blocks determinism; mtime never blocks and does not count toward the two agreeing signals. Excluded as `superseded` with at least two agreeing non-mtime signals or an LLM verdict at or above `low_confidence_threshold`; otherwise `low_confidence_keep`.
- **Q16** Subsumed: at least 95% of a document's normalized token shingles are contained in one other kept document and it is at least 20% shorter. Flag and keep (`action: include`, reason `subsumed_flag`, container in `kept_instead`). Config: `subsumed_containment`, `subsumed_min_length_ratio`.
- **Q18** Identifier collisions: default pattern `\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b`, checked only at filename start, heading start, and index-table key cell (index tables recognized by header vocabulary `id ticket key ref number`). Config: `identifier_patterns`, `identifier_title_headers`. Report only, never exclude. Docs state the narrow scope.
- **Q19** Topic clustering cut `max(floor, mean + z·stdev)`, starting z = 1.0, fastembed floor 0.78, TF-IDF floor 0.25. Tuned on the synthetic corpus only; final numbers recorded in `DECISIONS.md` and marked untested on real data. Suggest a real-corpus dry run afterward as a follow-up.
- Carried over from the requirements, unchanged: `near_duplicate_action` default `flag`, threshold 0.90; `similarity_max_tokens` 50,000 with Dice fallback; `IDENTIFIER_TEXT_SIMILARITY` 0.999; resolution precedence `overrides → exact → cross-format → near-duplicate (if exclude) → superseded → low_confidence → near_duplicate_flag → subsumed`; missing verdict means keep; `.md`/`.txt` read as UTF-8 directly; text normalized before cross-format comparison; `EXTRACT_VERSION` in the cache path.

### LLM phase and config
- **Q10** One verdict file per cluster, `<out>/.doc-curator/work/verdicts/<cluster_id>.json`, with `cluster_id`, `reviewed: true`, optional `revisions[]` (`superseded`, `superseded_by`, `confidence` 0–1, `rationale`, `unique_content[]`) and optional `conflicts[]` (`topic`, `statements[]` of `{path, quote, location}`, `rationale`), and `partial_read` when not everything was read. An empty verdict means "reviewed, nothing found". Below `low_confidence_threshold` (default 0.75) the file is kept as `low_confidence_keep`.
- **Q11** `config.yaml` and `overrides.yaml` at the root of `<out>/` (optional `--config` / `--overrides` flags). Missing files mean defaults; effective settings are written to `state.json`. Overrides are a list of `{path, action: include|exclude, note}` keyed by source-relative path.
- **Q20** `max_llm_clusters_per_run` default 25, largest clusters first; the rest are listed in the `REPORT.md` "LLM queue" section and picked up on the next run (verdicts persist). Queue items give each member's cached-text path, size and revision signals. `SKILL.md` tells Claude to read each member's first ~6,000 words by default, diff long members, and set `partial_read: true` if it did not read everything. Cap and word limit are config settings.

## Hard constraints (from the requirements)

- Never touch the source; verify with checksums before and after. Refuse an `--out` inside `--source`.
- Never run Graphify; print the command only.
- Idempotent: a second `analyze` + `apply` on an unchanged corpus processes 0 new or changed files and reproduces identical `action`/`reason`; an `overrides.yaml` entry flips exactly the targeted file.
- Halt and ask if an instruction contradicts a settled decision, Graphify gains `.pptx` support, or a requirement is ambiguous in a way that would change what ends up in staging.

## Deliverables

`DECISIONS.md`; `SKILL.md`; `scripts/curate.py` (`analyze`, `apply`, `--help` exits 0); `scripts/check_env.sh`; `references/verdict-schema.md`; `requirements.txt`; `docker/Dockerfile`; `tests/make_corpus.py`, `tests/corpus_expected.yaml`, `tests/fixtures/verdicts/`, `tests/score.py`; pytest suite including the staging-extension test derived from the installed `graphify.detect`; README sync (table row, details section, tree).

## Verification gates

1. `check_env.sh` exits 0.
2. `curate.py --help` exits 0 and lists `analyze` and `apply`.
3. `pytest tests -q` passes.
4. Full pipeline on the synthetic corpus with fixture verdicts: `score.py` prints `ALL EXPECTATIONS MET`.
5. Source corpus checksums identical before and after.
6. Staging: every non-`.pptx` source is a `.md` with a parseable five-field front-matter block; every kept `.pptx` is a `.pdf` + `.notes.md` pair; no raw `.pptx`; all extensions are in the union of `graphify.detect` `*_EXTENSIONS`.
7. End-to-end run with the LLM phase done for real passes `score.py --with-llm`.
8. Docker build, only if the daemon responds; otherwise say it was not run.

## Known soft spots

- `near_duplicate_action` must stay a config switch, never a hard rule.
- Version-marker regexes must read both ends of the filename stem.
- Cluster IDs and boundaries are unstable across small input changes; fixtures named after cluster IDs break when corpus files change.
- Identifier-collision detection only suits documents that describe work, not document libraries.
- Thresholds are untuned on real data.
