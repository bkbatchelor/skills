# docs-curator decisions

The design was settled in a grilling session (Q1 to Q24, recorded in `PLAN.md`) from the requirements in `/home/bkb/Documents/research/doc-curator-extraction.md` and the as-built record of the earlier build. This file records what was decided, what was designed fresh during the build (Q4), and where the build departed from the plan.

## Settled before the build

- **Staging is Markdown.** Every kept non-`.pptx` file is staged as Markdown with front matter (`source_path`, `source_format`, `sha256`, `status`, `description`). The body is the Phase 1 cached extraction. Fidelity loss for pdf, docx and xlsx (text only) is accepted. Kept `.pptx` files become `<name>.pptx.pdf` plus `<name>.pptx.notes.md`, because Graphify does not accept `.pptx`.
- **Names.** Staged name is the source-relative path with `.md` appended for every source that is not already `.md`.
- **`status` is the `decisions.jsonl` `reason`;** the kept copy of an exact-duplicate group reads `unique`.
- **`description` is deterministic:** first H1/H2, else first non-empty line, truncated to 160 characters, else the filename stem.
- **Existing front matter** in a source `.md` is nested under `source_front_matter`; if it does not parse it stays in the body and `REPORT.md` warns.
- **Near duplicates are flagged and kept** (`near_duplicate_action: flag`). `exclude` is opt-in.
- **Keeper rank:** `md > docx > pptx > xlsx > pdf > txt`, then text richness, then `keeper_prefers_descriptive_name`, then path.
- **Precedence:** overrides, exact, cross-format, near-duplicate (if exclude), superseded, low confidence, near-duplicate flag, subsumed. A missing verdict means keep.
- **Revision chains:** five signals (filename marker, in-text version or date, document-property date, mtime). A non-mtime signal contradicting the chosen order blocks determinism. Excluded as `superseded` with two agreeing non-mtime signals or a verdict at or above 0.75.
- **Subsumed:** 95% of token shingles contained in one other kept document that is at least 20% longer. Flag and keep.
- **Identifier collisions:** report only, three definition sites (filename start, heading start, index-table key cell).
- **Embeddings:** fastembed `BAAI/bge-small-en-v1.5`; if it cannot load, `analyze` stops unless config sets `embedding_backend: tfidf`.
- **Verdicts:** one file per cluster; `max_llm_clusters_per_run` 25, largest clusters first, the rest deferred to the next run.

## Designed during the build (Q4)

- **`reason` for unusable files.** `unreadable` and `not_ingestible` files get a `reason` equal to their `action`. The requirements list only `conversion_failed` for the unreadable family, so this keeps every row's `reason` non-empty. A failed `.pptx` conversion is `unreadable` with reason `conversion_failed`.
- **Config and overrides.** `<out>/config.yaml` (unknown keys are rejected) and `<out>/overrides.yaml` (`[{path, action: include|exclude, note}]`). An override wins over everything except `unreadable` and `not_ingestible` files.
- **State.** `<out>/.docs-curator/` holds `analysis.json` (everything `apply` needs), `state.json` (effective config, counts, last run), `decisions.jsonl`, `REPORT.md`, `conflicts.json`, `text/v<EXTRACT_VERSION>/`, `pdf/` (converted decks cached by sha256) and `work/{queue,verdicts}/`.
- **Valid containers.** `.docx/.pptx/.xlsx` must be zip files and `.pdf` must start with `%PDF`; markitdown otherwise falls back to plain text on a broken container and a corrupt file would be staged as garbage.
- **Cross-format duplicates** use the same threshold as near duplicates (0.90). The same-format case is flagged; the cross-format case is excluded (`format_duplicate`).
- **Chains need a topic cluster.** Files in a chain share a normalized filename stem in one directory (`revision_chain_scope`) and must fall in the same topic cluster.
- **Quote checking.** `apply` checks each conflict quote against the cached text (case and whitespace ignored) and marks misses `[quote not verified]`. `score.py --with-llm` fails on any unverified quote.
- **Verdict versus signals.** When two or more non-mtime signals agree, a contradicting verdict is ignored with a warning. A verdict can only add supersessions the signals do not settle.
- **Flags never point at excluded files.** A near-duplicate flag whose keeper was excluded (for example the keeper itself was superseded) is dropped, so the newer file reads `unique`. Found by a unit test.
- **Keeper tie-break.** After the descriptive-name score, a name with fewer revision markers wins (`expense_policy.txt` over `copy_of_expense_policy.txt`) before path order.
- **LibreOffice.** Conversions are serial, use a private profile, and convert a temporary copy so no lock files appear next to the source.
- **Skipped directories.** `.git`, `node_modules`, `__pycache__`. Symlinks are ignored.
- **Source guard.** `apply` stops if any source file's size or mtime differs from `analyze`.
- **Cluster fixtures are named after cluster ids,** which move when the corpus changes. `test_fixture_cluster_ids_match_the_current_corpus` fails loudly when that happens.

## Departures from the plan

- **Location and name.** The plan said `research/doc-curator/`. The repo already holds the committed skeleton at `docs/docs-curator/` with `name: docs-curator`, so the skill was built there. The work folder is `.docs-curator`. The install symlink is `~/.claude/skills/docs-curator`.
- **`numpy` is not pinned.** `numpy==2.5.4` needs Python 3.12 and the image pins 3.11. The Docker build caught this; numpy now resolves transitively (2.4.6 on 3.11).
- **Python versions seen.** Developed on 3.14. `uv run --with-requirements` picked 3.12.14 for the gate runs. The image (3.11) was built and `check_env.sh` passed in it; the test suite was not run on 3.11.

## Numbers that are untested on real data

Clustering cut `max(floor, mean + 1.0·stdev)` with floors 0.78 (fastembed) and 0.25 (TF-IDF). On the synthetic corpus the floor, not the statistic, set the cut, so z has not been exercised. Near-duplicate threshold 0.90, subsumed 95% and 20%, low-confidence 0.75, and the 0.35 LSH candidate threshold were chosen from the requirements and checked only on the synthetic corpus. A dry run on a real corpus is the follow-up.

## Not done

- Real-corpus dry runs (out of scope per Q5).
- OCR for text-free documents (Q17).

- **Default output and graphify-out link.** `--out` defaults to `~/curated/<basename of --source>`. A third command, `link`, creates `<out>/graphify-out/` and the symlink `<source>/graphify-out` pointing at it, so Graphify (which writes to the directory it runs from) never fills the project. This is the single, deliberate exception to "nothing under `--source` is written"; `apply` and `analyze` still write nothing there, and `graphify-out` is in `SKIP_DIRS` so the link is never inventoried. `link` refuses to replace a real directory or a symlink to somewhere else.
