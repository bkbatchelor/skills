# Arm recipes

An arm is one setup. Change one thing per arm, so each comparison isolates one cause. Every recipe below is a `bench.yaml` entry under `arms:`.

| Arm | Isolates | Entry |
|---|---|---|
| Plain search | The baseline: repo files only | `tools: [read]`, `deny_graphs: true`, a prompt saying graph tools are unavailable |
| Graphs available | What the graphs add when the agent may choose | `tools: [read, graphify, codegraph]`, no prompt |
| Graphs directed | The effect of telling the agent to use them | as above, plus `prompt: "Query the knowledge graphs before searching files."` |
| Curated text | What docs-curator's text adds without any graph | `tools: [read]`, `deny_graphs: true`, `add_dirs: [<staging>]`, a prompt naming the staging folder |
| Curated text + code graph | Whether the code graph adds to curated text | `tools: [read, codegraph]`, `deny_graphs: true`, `add_dirs: [<staging>]` |
| Instruction variant | A change to the agent instructions file | every source on, `instructions: <file>`, no prompt; one arm per version |

## Notes

- `deny_graphs: true` blocks reading the folders in `graph_paths` under the repo, `extra_dirs` and `curated_root`, and Bash commands that name them. With `codegraph` in `tools`, `.codegraph` stays readable.
- A tool missing from `tools` is denied, including its skill (`graphify` also denies the `knowledge-graph` skill).
- Prompts become `--append-system-prompt`. An arm that gets a pointer the others do not is testing the pointer too; say so, or give every arm the same pointer.
- For instruction variants, put each version in its own file and keep everything else identical. Diff the files before running: the only difference should be the change under test.
- Use the same model, reps and budget for every arm.

## What the arms found in one real benchmark

Eighteen questions about one repo, three runs each:

- Curated text scored highest; most of the gain came from Office and PDF files that became searchable.
- Graphs available scored between curated text and plain search, and tied with curated text plus code graph for the fewest false claims.
- Graphs directed cost about a quarter more tokens than plain search and had the most false claims.
- Curated text plus code graph scored the same as curated text alone; the code graph was used on caller questions only.
- With every source available and the instructions pointing to the curated text, agents did not use the docs graph at all.

Your repo may differ. That is why you run the benchmark.
