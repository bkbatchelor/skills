---
name: kg-benchmark
description: Benchmarks whether knowledge graphs (a graphify docs graph, a codegraph code graph), docs-curator curated text, or a change to the agent instructions file actually help an AI coding agent answer questions about a repository. Runs each question as a fresh headless Claude Code session in several isolated setups, grades every answer blind against a written key, rechecks flagged false claims with an independent audit, and reports correctness, tokens, cost and paired confidence intervals. Use when the user asks to benchmark, evaluate, measure or justify a knowledge graph, curated docs or graph rules, compare "graph vs no graph", decide whether a docs graph is worth rebuilding, or test a CLAUDE.md change. Skip for building or refreshing the graphs (use knowledge-graph), for one-off questions (use code-graph or graphify), and for benchmarking models or prompts unrelated to repository knowledge.
metadata:
  version: 1.0.0
---

# KG Benchmark

Answers one question with evidence: does this source (or this instruction) make the agent's answers better, cheaper, or neither? A run is one fresh `claude -p` session answering one question in one setup, called an **arm**. The `bench` script does every deterministic step; you design the test, check the setup, run the audit and write the conclusion.

## Prerequisites

- `claude` (Claude Code) logged in, `uv`, and the repo on disk.
- For graph arms: `graphify` and `codegraph` with built graphs. For curated-text arms: a docs-curator staging folder. Build them with the `knowledge-graph` skill first. Never install anything.

Run the script as:

```bash
BENCH="uv run --quiet --python 3.12 --script ~/.claude/skills/kg-benchmark/scripts/bench.py"
```

## Workflow

### 1. Design (with the user)

Agree on these before any run; use the `grilling` skill if it is installed.

- **The decision** the benchmark must inform (for example "keep rebuilding the docs graph?") and the success thresholds, set before the first run (for example "+0.5 correctness", "25% fewer tokens", "no more false claims").
- **Arms.** Change one thing per arm. Recipes are in `references/arms.md`: plain search, graphs available, graphs directed, curated text, curated text plus code graph, instruction-file variants.
- **Questions**, 15 to 25, each with a written key. Follow `references/questions.md`: answers must come from the repo, the key cites file:line evidence, and include traps (absence questions, outdated documents, binary-only sources).
- **Model, reps (3 minimum), and budget.** Run `$BENCH check` for the run count and a rough cost, and get the user's yes for the spend before step 3. Approval does not carry over to later rounds.

### 2. Set up and probe

1. `$BENCH init <dir>` writes `bench.yaml` and a `questions.json` template. Keep `<dir>` outside the repo and outside any folder an arm can read.
2. Fill in `bench.yaml` and `questions.json`. Arm names are lowercase letters and digits only.
3. `$BENCH check` validates both and prints each arm's allowed tools and deny count.
4. `$BENCH probe` runs a short setup check in every arm (pass `--model` for a cheaper model). For each arm confirm: the right instructions file or none is loaded, allowed tools work, denied tools and files are denied. Fix and re-probe until every arm is right. Do not skip this: isolation mistakes are silent (see `references/lessons.md`).

### 3. Run

`$BENCH run` runs every question in every arm, interleaved with a rotating start so time effects hit all arms equally. It skips traces that already have a result, so it is safe to re-run after an interruption. Run it in the background and wait for it to finish; never predict results.

Later arms added to an existing benchmark should be run interleaved with at least one earlier arm (re-run it), or the comparison carries a timing caveat; say so in the report.

### 4. Grade and check

1. `$BENCH extract`, then `$BENCH leakcheck`. Read every flagged run: a search that excludes a graph folder is not a leak, a successful read of a denied file is. Discard and re-run genuinely leaked runs.
2. `$BENCH judge` grades each answer in a tool-less session that sees only the question, the key and the redacted answer. Add setup-revealing words to `redact:` in `bench.yaml` before judging.
3. `$BENCH audit-prep`, then give a fresh general-purpose agent `references/audit-prompt.md` with the paths filled in. It verifies each judge-flagged claim against the sources and writes `audit/audit.json`. Then `$BENCH audit-merge`. Judges are often wrong (expect about half of flags to fail); only audited claims count as false claims.
4. Fix any answer key the audit shows is wrong (`KEY_ISSUE`), record the fix in the question's `key_revision` list, and re-judge that question's answers with `$BENCH judge --only <QID>` after removing their lines from `grades.jsonl`.

### 5. Compare and report

1. `$BENCH compare` gives per-arm averages and, for each pair, the per-question difference with a 95% bootstrap interval. `--pairs a:b,c:d` limits it. A range that includes zero could be chance; say so.
2. `$BENCH metrics` shows what each arm actually did: graph calls by graph, runs that read the curated text, identifier searches. An arm whose graph went unused did not test the graph.
3. `$BENCH report` writes `report.md`. Add the conclusion yourself: the decision, the evidence for it, what was not tested, and the limits (reps, one repo, run order, judge from the same model family).
4. Offer the user a 20% human spot-check of grades. It is the only check on the judge that is not a model.

## Hard rules

- Get the user's yes, with the cost estimate, before every `run` and `judge`. Never spend past it.
- Keep the benchmark folder (answer keys) out of every arm's reach; `bench` denies it. Never put it inside the repo.
- Exclude the live instructions file from every run (`bench` does) and give arms fixed copies with `instructions:`. Remove any lines from a copy that quote benchmark questions or answers.
- Never edit, commit, fetch or build in the repo or in any folder an arm reads. The benchmark is read-only towards them.
- Never report a judge flag as a false claim before the audit. Never report a difference without its interval.
- Never fabricate or estimate a result the script has not produced.
- When sharing results outside the team, remove project names, paths, people and client identifiers first, and scan the copy for them.

## Files

- `scripts/bench.py`: the script (one file, PEP 723 dependencies).
- `references/arms.md`: arm recipes and what each isolates.
- `references/questions.md`: how to write questions and keys.
- `references/audit-prompt.md`: the prompt for the independent false-claim audit.
- `references/lessons.md`: isolation and measurement mistakes found in real runs, and their fixes.
