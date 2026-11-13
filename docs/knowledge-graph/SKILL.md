---
name: knowledge-graph
description: Runs the repeatable knowledge-graph pipeline for a repository: curates its docs with docs-curator, builds or updates the docs graph with graphify, and syncs the code graph with codegraph, through one `kg` script that holds every workaround and safety check (branch and clean-tree gate, PHI hard stop, snapshots and restore, verdict and community-label carry-forward, node-loss check, token-cost estimate). Use when the user wants to rebuild, refresh, update or check the status of a repo's knowledge graphs, set one up for a new repo, or restore a previous graph, e.g. "refresh the graphs", "update the docs graph after the merge", "kg status", "set up the knowledge graph for this repo". Skip for a one-off question answered from an existing graph (use graphify query or code-graph), for curating a folder that is not a git repo (use docs-curator directly), and for querying another repo's read-only graph.
metadata:
  version: 1.0.0
---

# Knowledge Graph

One pipeline, three tools, two graphs:

- **Docs graph**: `docs-curator` curates the repo's documents into `~/curated/<repo>/staging/`, and the `graphify` skill builds `~/curated/<repo>/graphify-out/graph.json` from it.
- **Code graph**: `codegraph` indexes the repo into `<repo>/.codegraph/`.

The `kg` script does every deterministic step. You do the steps that need judgment: cluster verdicts, graphify's extraction, naming new communities, and asking the user. The script stops and says so whenever a person is needed. Never work around a stop.

## Prerequisites

Requires the `docs-curator`, `heavy-file-ingestion` and `code-graph` skills, the `graphify` CLI (0.9.103 or later) with its own skill, `codegraph`, and `uv`. Never install any of them yourself; `kg preflight` names what is missing.

Run the script as `kg` if `~/.local/bin/kg` exists. Otherwise use:

```bash
KG="uv run --quiet --python 3.12 --script ~/.claude/skills/knowledge-graph/scripts/kg.py"
```

If the shim is missing, offer it once ("Install a `kg` launcher in ~/.local/bin?") and run `$KG install-shim` only after a yes.

Run every command from inside the repo, or pass `--repo <path>`.

## Setup for a repo (once)

1. `kg init <repo>` creates `~/curated/<repo>/` with `kg.yaml`, `config.yaml`, `overrides.manual.yaml` and a `.gitignore`, and runs `git init` there. It never overwrites existing files.
2. Ask the user for the repo's PHI folders and write them to `phi_globs` in `kg.yaml`. If there are none, record that as `phi_globs: []` once the user confirms it. Review the `exclude_groups` with them as well.
3. Ask before indexing code: "Index this repo with `codegraph init`? It writes `.codegraph/` at the repo root." Only after a yes, run `kg init <repo> --codegraph`.
4. Run `kg preflight --fix`. `--fix` only turns codegraph telemetry off, which was agreed for this pipeline. Fix every `FAIL` before going on.

Commits to the curated folder's own git repo are the user's to make. Mention uncommitted changes there, but do not commit them yourself.

## The run

Start with `kg status`. It shows the gate, drift since the last curate and graph, pending reviews, PHI findings, backups, and the **next** step.

`kg all` runs the scripted steps in order and stops before the first one that needs a person. The full sequence:

1. **`kg curate`**: takes a snapshot, regenerates the overrides, runs docs-curator `update` (or `analyze` the first time), purges PHI text cache, carries verdicts forward, and archives stale ones. Exit 3 means clusters are waiting for review.
   - It also **auto-closes** a pending cluster when fewer than two of its members can reach staging, because no verdict on such a cluster could change staging. The verdict it writes carries a `kg_auto` field that gives the reason.
   - Each `curate` and `apply` re-checks these against the current overrides and reopens any cluster that now has two or more members that can reach staging. Never add `kg_auto` to a verdict you wrote yourself.
2. **Review** (you): run `kg review`.
   - For each cluster under `verdict:`, follow the docs-curator skill's step 2 and `references/verdict-schema.md` (in that skill), and write `.docs-curator/work/verdicts/<id>.json`.
   - For each cluster under `recheck:`, the verdict was copied from a re-numbered cluster that overlaps it by at least `carry_forward.verdict_overlap`. Read only the `new_members` listed in its `carried_forward` block. Check them against the carried revisions and conflicts, and against older documents on the same topic for status claims they contradict. Then set `carried_forward.review_done: true`.
   - When a changed document reverses a rule, grep the tracked docs for the old wording; `git diff` of the changed files is the quickest way to see what to look for.
3. **`kg apply`**: runs docs-curator `apply`. It writes the `graphify-out` and `.docs-curator` symlinks in `$HOME` form, stops on PHI in the cache or staging, checks keeper chains, and runs the mappers for `related_repos`. Exit 3 with `keeper:` lines means content left staging because its keeper is excluded too. Show the user each line and offer either an include in `overrides.manual.yaml` or adding the path to `known_excluded_keepers`. Then run `kg curate` and `kg apply` again.
4. **`kg graph prepare`**: takes a snapshot, re-keys graphify's manifest if needed (otherwise every update re-extracts the whole corpus), lists changed and deleted files, estimates the token cost, and lists oversized files.
5. **Ask the user** (one yes/no question): "Update the docs graph? N changed files, about T input tokens." If `over_cap` is true, say that it exceeds the cap and get a separate, explicit yes for the cost. Approval for an earlier run does not carry over.
6. **Run graphify** (you): run the `graphify_command` printed in `.kg/graph-plan.json`, from the repo root, following the graphify skill and its `references/update.md`. While doing so:
   - Give each `big_files` entry its own extraction chunk, and tell that agent to parse the file with `python3 -I` rather than Read.
   - Tell every extraction agent to read `graphify-out/graph.json` read-only and reuse the existing node IDs for its files, so cross-file edges survive.
   - **After the merge step and before Step 4**, run `kg graph check`.
     - Exit 0: every lost node comes from a changed or deleted file, so if `to_json`'s shrink guard refuses, pass `force=True`.
     - Exit 3: show the user the unexplained losses. Use `force=True` only after they accept them; otherwise stop and offer `kg restore`.
   - **At Step 5 (labels)**, run `kg graph labels` and start `LABELS_DICT` from `carried` in `.kg/labels-proposed.json`. Name only the communities under `needs_name`, keeping labels unique.
7. **`kg graph finish`**: checks the new graph for PHI, records the run, and prunes old snapshots. Report the node, edge and community counts and the query line.
8. **`kg code`**: runs `codegraph sync`. It works on any branch, because the code index follows the current checkout.

## Gating

`curate`, `apply`, `graph prepare` and `all` run only on the branches in `kg.yaml` (default `main`, `develop`, `develop-*`) with a clean working tree. When one refuses (exit 2), tell the user why and stop. Pass `--allow-any-branch` only when the user explicitly asks for it in this turn; the override is logged in `.kg/runs.jsonl`. `kg code`, `status`, `review`, `preflight` and `restore` are not gated.

## Restore

`kg restore` shows what the latest snapshot would put back. `kg restore <timestamp> [--only graph|curator]` picks a specific snapshot or part. Nothing is restored without `--yes`, so get the user's yes first. Snapshots live in `~/curated/<repo>/backups/`, and the newest `backups.keep` (default 3) are kept.

## Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0 | done | go on |
| 1 | failure or preflight blocked | read the message and fix it |
| 2 | gate refused | tell the user; do not override on your own |
| 3 | needs a person | reviews, unexplained node loss, or keeper problems |
| 4 | PHI found | stop everything and show the user the findings |

## Related repos

A `related_repos` entry names another repo whose graph is read-only from here. Query it with `graphify query "<q>" --graph <graph>` and cite which graph each fact came from. Never rebuild it, run `--update` on it, or write to it from this repo. Its optional `mapper` script lives in the curated folder and gets `KG_SOURCE`, `KG_RELATED_PATH`, `KG_RELATED_NAME` and `KG_OUT` in its environment.

## Hard rules

- Never run graphify without the user's yes for this run, with the cost estimate in the question.
- Never pass `force=True` while `kg graph check` reports unexplained losses the user has not accepted.
- Exit 4 (PHI) stops the run. Never stage, extract or graph a path that matches `phi_globs`, and never add an include override for one.
- Never commit to the user's repos, including the curated folder's git repo.
- Never edit `overrides.yaml` by hand; it is regenerated. Hand decisions go in `overrides.manual.yaml`.
- Never install tools or skills; `kg preflight` names what is missing.
