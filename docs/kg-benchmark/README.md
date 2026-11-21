# kg-benchmark

Measures whether a knowledge graph, curated documents, or a change to your agent instructions actually helps an AI coding agent answer questions about your repository (repo). A knowledge graph is a searchable map of a repo's documents or code. The skill gives you numbers instead of impressions: answer quality, tokens and cost, with the likely range of each difference.

It is the test that the [knowledge-graph](../knowledge-graph/README.md) skill's best practice refers to. Run it before you decide whether a docs graph is worth rebuilding, or before you change the instructions your agents follow.

## What it does

- **Runs each question as a fresh agent session** in several setups, called arms. An arm is one combination of sources and instructions, such as "repo files only" or "curated text plus the code graph". Each session answers one question and ends, so no session sees another's work.
- **Keeps the arms apart.** Each arm gets only the tools and folders its setup allows. The folder that holds the answer keys is blocked in every arm. Your live instructions file is left out of every run, and an arm that tests an instructions change loads its own fixed copy.
- **Grades blind.** A separate session grades each answer against a key you write. It sees the question, the key and the answer, but not the arm.
- **Checks the grader.** Graders flag false claims, and about half of those flags turn out to be wrong. The skill gives the flagged claims, with the arm hidden, to an independent agent that checks each one against the repo. Only claims it confirms count.
- **Compares fairly.** For each pair of arms it works out the difference per question and the range the true difference most likely falls in (a 95% interval). If that range includes zero, the difference could be chance.
- **Shows what each arm actually did.** It counts graph calls, curated-text reads and searches per arm, so an arm that never used its graph is not mistaken for a test of that graph.

## Before you start

You need:

- Claude Code, logged in, and `uv`, a Python tool runner.
- The repo on your disk.
- For graph arms: the graphs, built with the knowledge-graph skill. For curated-text arms: a docs-curator staging folder.
- 15 to 25 questions about the repo, each with a key. The key lists the points a full answer needs, with the file and line that proves each one. `references/questions.md` explains how to write them.

A benchmark spends tokens: one run costs roughly as much as one real question, and grading adds about a fifth. `bench check` prints an estimate before anything runs.

## How to run one

Ask Claude to "benchmark the knowledge graph on this repo". The skill helps you design the arms and questions, asks before it spends, and runs these steps. To run them yourself:

1. Create the benchmark folder, outside the repo:
   ```bash
   alias bench='uv run --quiet --python 3.12 --script ~/.claude/skills/kg-benchmark/scripts/bench.py'
   bench init ~/benchmarks/my-bench
   cd ~/benchmarks/my-bench
   ```
2. Edit `bench.yaml` (the repo, the arms) and `questions.json` (your questions and keys).
3. Check the setup and see the cost estimate:
   ```bash
   bench check
   ```
   If it reports an unknown tool or a bad arm name, fix `bench.yaml` and run it again. Arm names use lowercase letters and digits only.
4. Run a short setup check in each arm:
   ```bash
   bench probe
   ```
   Read each arm's report. It should list the right instructions file (or none), say that allowed tools worked, and say that blocked files were denied. If an arm can read something it should not, fix `bench.yaml` and probe again before going on.
5. Run the benchmark. It runs every question in every arm, three times, in a rotating order:
   ```bash
   bench run
   ```
   If it stops partway, run it again. It skips the runs that already finished.
6. Collect the answers, check for leaks, and grade:
   ```bash
   bench extract
   bench leakcheck
   bench judge
   ```
   A leak flag is a lead, not a verdict: a search that skips a graph folder gets flagged too. Open each flagged run and check.
7. Check the grader's false-claim flags:
   ```bash
   bench audit-prep
   ```
   Give an agent the prompt in `references/audit-prompt.md`. When it has written `audit/audit.json`, run `bench audit-merge`.
8. Compare and write the report:
   ```bash
   bench compare
   bench metrics
   bench report
   ```

## Reading the results

- Look at the range, not only the average. On a 5-point scale with three runs per question, differences of 0.1 to 0.2 are usually within the noise.
- Count false claims only after the audit.
- Check `bench metrics` before you credit or blame a tool. If an arm never called its graph, it did not test the graph.
- An arm run later than the others, rather than interleaved with them, can differ because of when it ran. Say so in the report.

## Files

- `SKILL.md`: the steps Claude follows and the rules it keeps.
- `scripts/bench.py`: the benchmark script. It is one Python file that lists its own packages at the top.
- `references/arms.md`: setups to compare, and what each one isolates.
- `references/questions.md`: how to write questions and keys.
- `references/audit-prompt.md`: the prompt for the independent check of false claims.
- `references/lessons.md`: mistakes found in real benchmarks, and how the script avoids them.
- `tests/test_bench.py`: automated tests.

## Tests

Run this from the root of this repo:

```bash
uv run --no-project --python 3.12 --with pytest --with pyyaml pytest docs/kg-benchmark/tests
```
