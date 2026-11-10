# code-graph

Answers code questions with [codegraph](https://github.com/colbymchenry/codegraph), and checks a code change against the ADRs and design docs that constrain it.

## What it does

- Checks codegraph is installed and the repo is indexed. It never installs codegraph, and runs `codegraph init` only when you say yes.
- Answers "what calls X", "how does Y work", and "what breaks if I change Z" from the index, before grep or Read.
- **Change check:** lists the documents that may constrain your diff, reads the docs graph (built by [docs-curator](../docs-curator/README.md) and Graphify) read-only, and reports each candidate with a verdict: consistent, possibly conflicting, or can't tell. It is advisory and never blocks a commit.

The code graph and the docs graph stay separate. This skill never builds or edits the docs graph.

## Linking an ADR to code

Put `applies_to` in the document's front matter, using source-relative paths or symbol names:

```yaml
---
applies_to:
  - src/orders/service.py
  - OrderService.retry
---
```

Without it, the check still finds documents that name the changed file in their text. If no docs graph exists, or it is older than the newest document, the skill says so and falls back to searching the repo's own Markdown.

## Files

- `SKILL.md`: instructions for Claude
- `scripts/check_env.sh`: exit 0 ready, 1 codegraph missing, 2 repo not indexed
- `scripts/diff_links.sh`: changed files, the documents that list or name them, and whether the docs graph is missing, ok, or stale

## Requirements

`codegraph` on the PATH. For the change check, optionally the `graphify` CLI and a docs graph from docs-curator.
