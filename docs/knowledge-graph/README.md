# knowledge-graph

Runs a repeatable process that keeps two knowledge graphs for a repository (repo). A knowledge graph is a searchable map. It has nodes, which are things such as a document or a function, and links between the nodes. The repo has two graphs:

- **The docs graph:** built from your documents. [docs-curator](../docs-curator/README.md) cleans up the documents first. Then Graphify builds the graph from them.
- **The code graph:** built from your code by [codegraph](https://github.com/colbymchenry/codegraph). You use it through the [code-graph](../code-graph/README.md) skill.

`kg` is a script that runs every routine step. It includes the workarounds that people used to do by hand. The skill handles the steps that need judgment. It always asks you before it spends tokens, the units of text that AI models read and write. You pay for them.

## What kg does for you

kg turns a repository's documents and code into two searchable knowledge graphs. It keeps them up to date as the repo changes. Each point below says what you get, then how kg delivers it.

### Trust and safety

- **Only reviewed content goes in.** The docs steps run only on the branches `main`, `develop` and `develop-*`, which means any branch whose name starts with `develop-`. They run only when the working tree is clean. A clean working tree has no unsaved changes. So the graph never shows unfinished or unmerged work. The `--allow-any-branch` option overrides this. kg logs every override.
- **Sensitive data stays out.** Paths listed in `phi_globs` are always excluded. PHI means protected health information, such as patient records. kg deletes their extracted text after every analyze step. If any trace of those paths appears in the text cache, the staging folder or the graph, the run stops with exit code 4. An exit code is the number a script returns when it ends. This is a hard stop, not a warning. The text cache is a stored copy of extracted text.
- **A bad run can be undone.** Before each curate step and each graph run, kg saves a snapshot. A snapshot is a saved copy of the graph, graphify's cache, the docs-curator state, the per-file decisions and the verdicts. kg keeps the last 3 snapshots. Run `kg restore` to put one back. A retry cannot remove the last good graph.
- **Spend is visible before it happens.** Before each graph run, kg shows a token-cost estimate, read from `cost.json`. If the estimate passes the cap, kg stops and asks for a separate, explicit yes. Lost nodes, which are graph nodes that disappeared, are sorted into "from changed files" and "unexplained". This happens before anything is forced through.

### Cost and effort

- **Cheap work stays cheap.** If `classify_untyped` is on, kg waits before it clusters. It waits until a small model has labelled the untyped documents. A cluster is a group of related documents. kg clusters again after labelling, so it does not write a verdict for a cluster that is about to change. A verdict is the review result for a cluster. Cluster reviews go to a standard model or a deep model. A standard review that finds a conflict is redone once by the deep model. `kg apply` does not run until that is done.
- **Review effort is spent once.** When a cluster is renumbered because one of its members changed, its old verdict carries over. That happens if the old and new member sets overlap by at least 80%. Moved files are followed. Reviewers see only the new members, not the whole cluster again. A cluster with fewer than two members that can reach staging closes automatically (`kg_auto`). It reopens if an override gives it a second member.
- **Incremental runs cost less.** Manifests written by older versions are updated to the current format. A manifest is the record of which files were processed. So `--update` reads again only the files that changed.
- **Naming stays stable.** A community is a group of linked nodes in the graph. Its label carries forward wherever at least 50% of its labelled members agree. So the graph's vocabulary does not change from run to run.
- **Nothing is lost silently.** The keeper check catches documents that left staging. They left because the duplicate they were grouped with had its keeper excluded too. A keeper is the copy kept from a set of duplicates.

### Control and repeatability

- **Overrides are generated, not hand-maintained.** `overrides.yaml` is built from three sources: git, the exclude groups in `kg.yaml`, and your own decisions in `overrides.manual.yaml`. Only git-tracked files are staged. The file rules come from docs-curator's `curate.py`, so the two always match.
- **Graph excludes are declarative.** You list the rules, and kg applies them. `graph.excludes` in `kg.yaml` holds patterns in gitignore style, the same pattern format as `.gitignore`. Examples are `*.xlsx.md` and `!/specs/api/decp.openapi.yaml.md`. A leading `!` keeps a file that an earlier rule excluded. Before each run, kg writes these patterns into graphify's exclude file. So new files follow the rules too. kg also removes the nodes of files that the rules newly exclude.
- **Hand corrections survive re-extraction.** Re-extraction means rebuilding the graph's nodes from the source files. `graph-fixups.yaml`, which sits next to `kg.yaml`, lists fixes you reviewed. They include links to add and duplicate nodes to merge. kg applies them after every run. kg always drops self-loop edges, which are links from a node back to itself.
- **Oversized files are planned for.** A graph run lists the files that need their own extraction chunk. A chunk is one piece of a larger job. This way the run does not fail halfway.
- **Code graph in one command.** `kg code` runs `codegraph sync` on any branch. It also turns off codegraph's telemetry, which is its usage reporting.
- **Portable setup.** The repo's `graphify-out` and `.docs-curator` links are written with `$HOME` paths. A path that starts with `$HOME` points to your home folder. So the links work on other computers.

## Layout

This folder is its own git repository. Git tracks only the files you write by hand.

```text
~/curated/<repo>/             # its own git repo; only the hand-made files are tracked
├── kg.yaml                   # pipeline settings (source, gate, phi_globs, exclude groups, thresholds, related repos)
├── config.yaml               # docs-curator settings
├── overrides.manual.yaml     # hand decisions, take precedence over generated rules
├── overrides.yaml            # generated by kg
├── staging/  .docs-curator/  graphify-out/
├── backups/<timestamp>/      # snapshots
└── .kg/                      # run log, cluster registry, review list, graph plan, label proposals
```

## Example kg.yaml

`kg init` writes a starting `kg.yaml`, the settings file for the pipeline. The example below shows one. Every key except `source` is optional. If you leave a key out, kg uses the default shown. Globs are file patterns, such as `data/*`. They follow `fnmatch` rules, a standard matching method. In these rules, `*` also matches `/`. Globs are relative to the repo root. The exception is `graph.excludes`. Its patterns use gitignore style and are relative to `staging/`. kg rejects keys it does not know.

```yaml
source: ~/Projects/my-repo           # the repo this folder curates; must match where kg runs

gating:                              # docs steps only (curate, apply, graph); codegraph sync runs anywhere
  branches: [main, develop, "develop-*"]
  require_clean: true

phi_globs:                           # never extracted or staged; any trace stops the run (exit 4)
  - "data/customer-exports/*"
  - "build/uploads/*/applications/*"

overrides:
  tracked_only: true                 # stage only git-tracked documents
  exclude_groups:                    # tracked, but not documentation
    - note: "test fixture"
      globs: ["*/src/test/*", "tests/*"]
    - note: "build/tool config"
      globs: ["pom.xml", "*/pom.xml", "package.json", "*/package.json"]
    - note: "agent tooling (not product docs)"
      enabled: false                 # listed but off; `kg overrides --dry-run` shows what it would drop
      globs: [".claude/*", ".github/prompts/*"]

known_excluded_keepers: []           # excluded files whose keeper is also excluded, already checked

carry_forward:
  verdict_overlap: 0.8               # copy a verdict to a re-numbered cluster at this member overlap
  label_agreement: 0.5               # reuse a community label when this share of members agrees
  label_min_known: 0.5               # ...and at least this share of all members had a label before
  subset_max_members: 25             # a cluster that only lost members keeps the verdict of an old one this small

graph:
  cost_cap_tokens: 1500000           # an estimate above this needs a separate, explicit yes
  agent_overhead_tokens: 60000       # fixed cost per extraction agent, added to the estimate
  big_file_bytes: 400000             # changed files over either limit get their own chunk
  big_file_line_chars: 20000
  excludes:                          # which staged files reach the graph; last match wins
    - "*.xlsx.md"                    # spreadsheets: mostly rows, costly
    - "*.json.md"
    - "*.pptx.pdf"                   # decks; their .pptx.notes.md speaker notes stay in
    - "/docs/form-library/**/*.pdf.md"
    - "!/specs/api/openapi.yaml.md"  # but the API contract does go in

backups:
  keep: 3                            # newest snapshots kept, plus the pre-run one of an unfinished graph run

related_repos:                       # other repos whose graphs are read-only from here
  - name: config-repo
    path: ~/Projects/config-repo
    graph: ~/Projects/config-repo/graphify-out/graph.json
    mapper: map_config_refs.py       # optional script in this folder; run by `kg apply`
```

## Usage

Run these commands in a terminal:

```bash
kg init ~/Projects/my-repo        # run once, then fill in phi_globs in kg.yaml
kg preflight --fix                # checks the setup; --fix applies the fixes it can make
kg status                         # shows where things stand and the next step
kg all                            # runs the scripted steps up to the next one that needs a person
kg review                         # lists batches waiting for labels, clusters waiting for a verdict, a deeper re-review or a re-check
kg graph prepare                  # before the graphify run: shows the cost estimate and the plan
kg graph check | labels | finish  # around graphify's merge (combining results) and labelling steps
kg code                           # runs codegraph sync, which updates the code index
kg restore [<timestamp>] --yes    # restores a saved snapshot; the timestamp in brackets is optional
```

Ask Claude to "refresh the knowledge graphs". The skill runs these commands. It stops to ask you when it needs your input.

## Files

- `SKILL.md`: the workflow Claude follows, the gates, exit codes and hard rules
- `scripts/kg.py`: the pipeline script. It is one Python file that lists its own packages at the top (the PEP 723 format). Run it with `uv run --python 3.12 --script`.
- `tests/test_kg.py`: a pytest suite (automated tests run with pytest). It covers gating, overrides, PHI, carry-forward, classifier batches and escalation, the node-loss check, labels, snapshots, links and manifest re-keying.

## Requirements

- `uv`, a Python tool runner, and Python 3.12. uv downloads Python 3.12 for you.
- The docs-curator, heavy-file-ingestion, code-graph and graphify skills.
- The `graphify` command-line tool, version 0.9.103 or newer.
- `codegraph`.

kg never installs any of these.

## Tests

Run this in a terminal from the root of this repo:

```bash
uv run --no-project --python 3.12 --with pytest --with pyyaml pytest docs/knowledge-graph/tests
```
