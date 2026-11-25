---
name: knowledge-graph
description: >-
  Runs the repeatable knowledge-graph pipeline for a repository: curates its docs with docs-curator, builds or updates the docs graph with graphify, and syncs the code graph with codegraph, through one `kg` script that holds every workaround and safety check (branch and clean-tree gate, PHI hard stop, snapshots and restore, verdict and community-label carry-forward, node-loss check, token-cost estimate). Use when the user wants to rebuild, refresh, update or check the status of a repo's knowledge graphs, set one up for a new repo, or restore a previous graph, e.g. refresh the graphs, update the docs graph after a merge, kg status. Also curates another repo selectively, only as far as the primary repo's unanswered goal questions need (`kg needs`, `kg external`). Skip for a one-off question answered from an existing graph (use graphify query or code-graph), for curating a folder that is not a git repo (use docs-curator directly), and for querying another repo's read-only graph.
metadata:
  version: 1.7.2
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

`kg all` runs the scripted steps in order and stops before the first one that needs a person.

With `graph.refresh: on_request` in `kg.yaml`, a routine run stops after `kg apply`: `kg status` reports "up to date" and `kg all` syncs the code graph instead of moving on to the docs graph. Run `kg graph prepare` (steps 4 to 7) only when the user asks for a docs-graph rebuild in that turn. The default, `always`, leads on to the docs graph as below. See "When the docs graph pays" for when to choose which.

The full sequence:

1. **`kg curate`**: takes a snapshot, regenerates the overrides, runs docs-curator `update` (or `analyze` the first time) with each PHI glob as `--no-extract` so PHI text is never extracted, purges any PHI text left in the cache, carries verdicts forward, and archives stale ones. Exit 3 means a person is needed: classifier batches waiting for labels (below), or clusters waiting for review.
   - A cluster that only **lost** members keeps the old verdict, marked done, when the old cluster had at most `carry_forward.subset_max_members` (default 25) members and its verdict was not a partial read. Larger or partly read clusters come back for a full review, because a shallow review must not be inherited by every piece a large cluster splits into.
   - It also **auto-closes** a pending cluster when fewer than two of its members can reach staging, because no verdict on such a cluster could change staging. The verdict it writes carries a `kg_auto` field that gives the reason.
   - Each `curate` and `apply` re-checks these against the current overrides and reopens any cluster that now has two or more members that can reach staging. Never add `kg_auto` to a verdict you wrote yourself.
   - **Classifier labels (optional).** When `config.yaml` has `classify_untyped: true`, docs-curator queues documents with no `type` front matter and no glob match (override-excluded and PHI files are never queued). If any batch has no labels yet, `kg curate` stops right after the PHI purge, before any cluster bookkeeping, and exits 3: typing merges requirements and ADRs into clusters, so these clusters are about to be re-numbered. Do the labelling in step 2, then run `kg curate` again.
2. **Label and review** (you): run `kg review`. If it reports clusters `deferred` past docs-curator's `max_llm_clusters_per_run`, those need a review too: after this round, `kg curate` queues them, and `kg apply` refuses until none are left (or raise the cap in `config.yaml`).
   - For each batch under `label:`, follow the docs-curator skill's classification step: label it with a subagent on the model named in the batch (Haiku by default) and write `.docs-curator/work/classify/labels/<batch_id>.json` (`references/verdict-schema.md` in that skill has the format). Then run `kg curate` again to apply the labels. Repeat while batches remain, because large corpora are queued in parts. Until then `kg review` lists no cluster verdicts, `kg apply` refuses, and `kg status` shows the next step as labelling. Labels are snapshotted with the verdicts.
   - Route each cluster review by the `review` field of its queue item, as the docs-curator skill's step 2 describes (Sonnet for `standard`, Opus for `deep`), and write `review_tier` and `model` in the verdict. After the verdicts are in, run `kg curate` once more: a standard verdict with a conflict or a low-confidence revision is queued again for a deep review, and `kg review` lists it under `escalate:` (`kg apply` refuses until it is redone with the deep model and the verdict says `review_tier: deep`).
   - For each cluster under `verdict:`, follow the docs-curator skill's step 2 and `references/verdict-schema.md` (in that skill), and write `.docs-curator/work/verdicts/<id>.json`.
   - For each cluster under `recheck:`, the verdict was copied from a re-numbered cluster that overlaps it by at least `carry_forward.verdict_overlap`. Read only the `new_members` listed in its `carried_forward` block. Check them against the carried revisions and conflicts, and against older documents on the same topic for status claims they contradict. Then set `carried_forward.review_done: true`.
   - When a changed document reverses a rule, grep the tracked docs for the old wording; `git diff` of the changed files is the quickest way to see what to look for.
3. **`kg apply`**: runs docs-curator `apply`. It writes the `graphify-out` and `.docs-curator` symlinks in `$HOME` form, stops on PHI in the cache or staging, checks keeper chains, and runs the mappers for `related_repos`. Exit 3 with `keeper:` lines means content left staging because its keeper is excluded too. Show the user each line and offer either an include in `overrides.manual.yaml` or adding the path to `known_excluded_keepers`. Then run `kg curate` and `kg apply` again.
4. **`kg graph prepare`**: takes a snapshot, re-keys graphify's manifest if needed (otherwise every update re-extracts the whole corpus), and writes `graph.excludes` from `kg.yaml` into graphify's exclude file (`.graphify_build.json`). It then lists changed and deleted files, plus graph sources that the exclude rules now leave out, estimates the token cost, and lists oversized files. The estimate prices the changed files themselves (bytes / 4): files agents read at a content multiplier, big and long files they parse with a script at the lower `parsed_content_multiplier`, plus a fixed overhead per extraction agent. It works with no `cost.json`; a prune-only run is estimated at 0. `kg graph finish` measures the read-content multiplier from the tokens graphify recorded (only when the run read more content than it parsed) and prepare uses the mean of the last three measurements.
5. **Ask the user** (one yes/no question): "Update the docs graph? N changed files, about T input tokens." If `over_cap` is true, say that it exceeds the cap and get a separate, explicit yes for the cost. Approval for an earlier run does not carry over.
6. **Run graphify** (you): run the `graphify_command` printed in `.kg/graph-plan.json`, from the repo root, following the graphify skill and its `references/update.md`. While doing so:
   - Give each `big_files` and `long_files` entry its own extraction chunk (`long_files` are over 2,000 lines, graphify's own rule), and tell that agent to parse the file with `python3 -I` rather than Read. The cost estimate already counts one agent per entry.
   - Tell every extraction agent to read `graphify-out/graph.json` read-only and reuse the existing node IDs for its files, so cross-file edges survive.
   - Tell every extraction agent: when a file cites another document by an identifier in `graph.citation_ids` (default `ADR`), add a node for the citation whose label *starts* with the identifier (for example `ADR-005 PDF overlay`), even when that document is in another chunk. Agents only see their own chunk, so these citations would otherwise get no edge; `kg graph fixups` links each one to the cited file's node when the label's words occur in that file.
   - **Prune with the plan's list, not graphify's.** In the merge step, pass `prune_sources` from `.kg/graph-plan.json` to `build_merge`. That list is the deleted files plus the files under `excluded`. graphify's own update procedure prunes deleted files only, so without this the nodes of a newly excluded file would stay in the graph for good.
   - When the plan has `excluded` files but nothing changed or was deleted, graphify's detection reports "No files changed" and stops. Continue anyway: write the empty extraction from `references/update.md` and run the merge with the plan's `prune_sources`.
   - **After the merge step and before Step 4**, run `kg graph check`.
     - Exit 0: every lost node comes from a changed, deleted or newly excluded file, so if `to_json`'s shrink guard refuses, pass `force=True`.
     - Exit 3: show the user the unexplained losses. Use `force=True` only after they accept them; otherwise stop and offer `kg restore`.
   - **Right after `kg graph check`**, run `kg graph fixups`. It applies `~/curated/<repo>/graph-fixups.yaml` to the merged extraction before graphify builds and clusters: `links` to add, `merge` entries that fold a duplicate node into the one to keep, and self-loops always dropped. It also links cross-chunk citations (above). Nodes removed by a listed merge count as explained in `kg graph check`. Add a fixup only after checking that the two nodes are the same thing, not two instances (for example the same clause on two forms).
   - **At Step 5 (labels)**, run `kg graph labels` and start `LABELS_DICT` from `carried` in `.kg/labels-proposed.json`. Name only the communities under `needs_name`, keeping labels unique. A community is carried only if at least `label_min_known` of its members had a label before, so a community made mostly of new material always gets a fresh name.
7. **`kg graph finish`**: checks the new graph for PHI, records the run, and prunes old snapshots. Report the node, edge and community counts and the query line.
8. **`kg code`**: runs `codegraph sync`. It works on any branch, because the code index follows the current checkout.

## When the docs graph pays

A benchmark on a real repository (18 developer questions, several setups, three runs each, graded blind, with false claims rechecked against the sources) found:

- **The curated text did the work.** Sessions that could search `~/curated/<repo>/staging/` scored highest, mostly because Word, Excel, PDF and PowerPoint files become searchable text. The docs graph built from that same text added nothing on top, and its build cost several times the curation reviews.
- **With a pointer to the curated text in the agent instructions, agents left the docs graph alone**, and lost no quality.
- **A "query the graphs first" instruction made things worse:** about a quarter more tokens than plain search and the most false claims, because the agent queried the graph and then read the files anyway. A graph summary linked to the wrong document produced a wrong citation.
- **The code graph helped on its own kind of question** (callers and change impact) and costs no model tokens to refresh.

So:

- Point agents at the staging folder for document questions, and at the code graph for callers and change impact. Never add a rule to query the graphs first.
- Treat any graph result as a pointer: open the file it names and cite the line, not the graph. Never conclude something is absent because a graph lacks it; search for the exact identifier.
- Consider `graph.refresh: on_request` once agents are pointed at the curated text. Keep curation and `kg code` running after merges.
- A docs graph earns its cost when many questions are about links between documents (paths, citations, groups), or when the corpus is too large to search well. Before relying on it, test that on your own questions with the `kg-benchmark` skill, which runs the same comparison (isolated setups, blind grading, audited false claims) on any repo.

## Gating

`curate`, `apply`, `graph prepare` and `all` run only on the branches in `kg.yaml` (default `main`, `develop`, `develop-*`) with a clean working tree. When one refuses (exit 2), tell the user why and stop. Pass `--allow-any-branch` only when the user explicitly asks for it in this turn; the override is logged in `.kg/runs.jsonl`. `kg code`, `status`, `review`, `preflight` and `restore` are not gated.

## Restore

`kg restore` shows what the latest snapshot would put back. `kg restore <timestamp> [--only graph|curator]` picks a specific snapshot or part. Nothing is restored without `--yes`, so get the user's yes first. Snapshots live in `~/curated/<repo>/backups/`, and the newest `backups.keep` (default 3) are kept. Two guards protect them: an unchanged state reuses the latest snapshot instead of adding one, and the snapshot an unfinished graph run started from (named in `.kg/graph-plan.json`) is never pruned.

**If a graphify run fails partway, restore first, then retry.** `kg graph prepare` warns when the previous run never reached `kg graph finish` and keeps that run's pre-run snapshot as the restore point. Offer `kg restore <that snapshot> --only graph`, and run it with `--yes` once the user agrees, before preparing again.

## Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0 | done | go on |
| 1 | failure or preflight blocked | read the message and fix it |
| 2 | gate refused | tell the user; do not override on your own |
| 3 | needs a person | reviews, unexplained node loss, or keeper problems |
| 4 | PHI found | stop everything and show the user the findings |

When a folder is newly added to `phi_globs`, the existing graph may still hold its nodes. `kg curate` and `kg apply` remove it from the cache and staging, and `kg graph prepare` then lists those graph sources under `phi_pruned` and adds them to `prune_sources`. Run that graph update promptly; `kg graph finish` exits 4 if any PHI node remains.

## Goal-scoped curation of an external repo

Use this when the primary repo's goals need facts that only another repo holds. Curating that whole repo is the cost to avoid, so curate the primary first and the external repo only as far as its questions require. The steps go in order, and each one waits for the user where it says so.

1. **Know the goals.** With the primary curated and graphed, run `kg needs init`. Propose goals from the curated docs and the graph (README, ADRs, requirements, and the gap and "can't tell" findings in docs-curator's report) with `kg needs add-goal "<text>"`. Show them to the user, and run `kg needs approve-goals` only after their yes. Changing a goal clears the approval.
2. **Write questions.** `kg needs add-question "<text>" --goal gN --expects <kind of fact>` (a contract, an API, a policy). Questions must serve a goal and ask for something that would live in another repo.
3. **Gate each question against the primary graphs.** Query the docs graph (`graphify query`) and the code graph (`codegraph explore`). If the primary answers it, run `kg needs set qN --status answered-internally --answer ... --source ...`. If not, run `kg needs set qN --status external-only --evidence "<the queries that came back empty>"`. `kg` refuses `external-only` without evidence. No `external-only` questions means no external curation.
4. **Register the clone.** `kg external add <name> --path <local clone> --phi-glob <glob>...`, or `--no-phi` after the user confirms the external repo has no PHI paths. Ask them; do not reuse the primary's globs. The clone must already exist. `kg` never clones, fetches or writes into it, and warns if its tree is dirty.
5. **Inventory, then pick.** `kg external inventory <name>` lists candidate files with sizes and first headings only, never PHI paths. Choose the files each `external-only` question needs and write `~/curated/<repo>/external/<name>/scope.yaml` (`repo_sha`, `files: [{path|glob, questions: [qN]}]`). Every file must serve a question.
6. **Approve the scope.** `kg external scope <name>` validates it and prints the file count and token estimate. Ask the user one yes/no with those numbers. Over `external.max_files` (default 50) or `external.cost_cap_tokens`, say so and get a separate yes. Then run `kg external scope <name> --approve` (adding `--accept-over-cap` for an overage). Approval for an earlier scope does not carry over.
7. **Build and review.** `kg external build <name>` runs docs-curator with `--scope` and the external PHI globs as `--no-extract`, and pins the clone's commit. Review queued clusters as in the main run (the work dir is `external/<name>/.docs-curator/`), then `kg external apply <name>`. There is no `link` step: the clone is never touched.
8. **Graph it.** Ask the user to approve the graphify run with its cost, as in the main run. Run graphify from `external/<name>/` on its `staging/`, then `kg external finish <name>`, which checks for PHI and records the graph as **partial coverage**.
9. **Answer.** Query the scoped graph and cite it as "scoped graph, partial coverage": a missing fact is not proof it is absent from the repo. Record each answer with `kg needs set qN --status answered-externally --answer ... --source <path>`.
10. **Still unanswered?** You may propose added files for that question only, then repeat steps 6 to 8 for them. Each question gets at most two widening rounds; `kg external scope --approve` refuses a third. After that, run `kg needs set qN --status unanswered` and report it.

Later: `kg external status <name>` reports drift only in scoped files. A refresh is `kg external build <name>`, which re-curates only the changed ones. After retiring a question, `kg external prune <name>` lists files that served only retired questions; rewrite the scope with `--yes` only after the user agrees.

The primary's gates, snapshots and PHI hard stop still apply. External builds take their own snapshot in `external/<name>/backups/`.

## Related repos

A `related_repos` entry names another repo whose graph is read-only from here. Query it with `graphify query "<q>" --graph <graph>` and cite which graph each fact came from. Never rebuild it, run `--update` on it, or write to it from this repo. Its optional `mapper` script lives in the curated folder and gets `KG_SOURCE`, `KG_RELATED_PATH`, `KG_RELATED_NAME` and `KG_OUT` in its environment.

## Hard rules

- Never run graphify without the user's yes for this run, with the cost estimate in the question.
- Never pass `force=True` while `kg graph check` reports unexplained losses the user has not accepted.
- Exit 4 (PHI) stops the run. Never stage, extract or graph a path that matches `phi_globs`, and never add an include override for one.
- Never commit to the user's repos, including the curated folder's git repo.
- Never edit `overrides.yaml` by hand; it is regenerated. Hand decisions go in `overrides.manual.yaml`.
- Never write to, fetch into, clone, link into or run `codegraph init` on an external repo. Never curate an external file that no `external-only` question asked for.
- Never install tools or skills; `kg preflight` names what is missing.
