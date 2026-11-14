# code-graph

Answers questions about code with [codegraph](https://github.com/colbymchenry/codegraph). Codegraph builds an index, which is a stored map of the code's functions, files and calls. The skill also checks a code change against the design records that limit it. Design records are architecture decision records (ADRs), which are short documents that record a design choice and why it was made, and other design docs.

## What it does

- **Setup check:** confirms that codegraph is installed and that the repo has an index. It never installs codegraph. It runs `codegraph init`, which builds the index, only when you say yes.
- **Code questions:** answers questions such as "what calls X", "how does Y work", and "what breaks if I change Z". It reads the index first, before it searches text with grep (a text search tool) or opens files.
- **Change check:** lists the documents that may limit your changes, which is your diff. It reads the docs graph without changing it. Then it gives each document a verdict: consistent, possibly conflicting, or can't tell. This check gives advice only. It never blocks a commit.

The docs graph is a map of your documents. [docs-curator](../docs-curator/README.md) and Graphify, a tool that builds knowledge graphs from documents, build it. The code graph and the docs graph stay separate. This skill never builds or edits the docs graph.

## Linking an ADR to code

Add `applies_to` to a document's front matter. Front matter is the block of settings at the top of a file, between two lines of `---`. List the files or symbols (named functions or classes) that the document applies to. Use paths from the root of the repo.

```yaml
---
applies_to:
  - src/orders/service.py
  - OrderService.retry
---
```

Without `applies_to`, the check still finds documents that name the changed file in their text. If no docs graph exists, or if it is older than the newest document, the skill says so. It then searches the repo's own Markdown files instead. Markdown is a plain-text format, and its files end in `.md`.

## Files

- `SKILL.md`: instructions for Claude
- `scripts/check_env.sh`: checks the setup. An exit code is the number a script returns when it ends. Exit code 0 means ready. Exit code 1 means codegraph is missing. Exit code 2 means the repo is not indexed.
- `scripts/diff_links.sh`: lists the changed files and the documents that name them. It also reports whether the docs graph is missing, ok, or stale.

## Requirements

- `codegraph`, installed and on your PATH. PATH is the list of folders your terminal searches for commands.
- For the change check, optionally the `graphify` command-line tool and a docs graph from docs-curator.
