---
name: code-graph
description: Answers questions about source code (symbols, callers, dependencies, architecture, blast radius) with codegraph, a code knowledge graph, and checks a code change against the documents that constrain it, such as ADRs, by reading the docs graph that docs-curator and graphify built. Use for "how does X work in the code", "what calls Y", "what breaks if I change Z", "does this change conflict with an ADR or design doc", and to set up or refresh a repository's code index. Checks that codegraph is installed, runs `codegraph init` only after the user approves, and never installs anything. Skip for questions about PDFs, slides, or Markdown content (use graphify, after docs-curator), for curating documents (use docs-curator), and for editing code with no need to understand it first.
metadata:
  version: 1.0.1
---

# Code Graph

Code goes in one graph (codegraph), documents in another (graphify, built by `docs-curator`). The two are never merged. This skill queries the code graph, and for change checks it also reads the docs graph, read-only.

## Prerequisites

`SKILL=~/.claude/skills/code-graph` (or wherever it is installed). Run `bash $SKILL/scripts/check_env.sh [repo]`:

- Exit 1, `codegraph: missing`: stop. Do not install it. Tell the user to install it, then re-run the check.
- Exit 2, `index: absent`: ask the user before indexing (below).
- Exit 0: ready.

## Setting up the index

Indexing is the user's decision. When the index is absent, ask once: "Index this repo with `codegraph init`? It writes `.codegraph/` at the repo root." Run `codegraph init <repo>` only after a yes in this turn; an earlier yes does not carry over. If the user declines, fall back to grep and Read, and say so.

When the index exists but the code has changed since, run `codegraph sync <repo>` before answering. Use `codegraph status <repo>` to see what is indexed. `codegraph index` rebuilds from scratch; use it only if `sync` looks wrong.

## Answering code questions

Use `codegraph explore "<symbol names or the question>"` before grep or Read. It returns the relevant symbols' source and the call paths between them. Use `codegraph node <name>` for one symbol with its callers and callees, `codegraph context "<task>"` to gather context for a task, and `codegraph query <text>` to search symbols. Treat the output as already read; do not re-open those files. If an MCP `codegraph_explore` tool is listed, it gives the same answer.

## Checking a change against the docs

Run this when the user asks "does this conflict with an ADR", before committing a change to code that docs may constrain, or when reviewing a diff. It is advisory: it never blocks anything.

1. **Find the changed code.** `bash $SKILL/scripts/diff_links.sh [--base REF] [repo]` lists the changed files and, for each, the Markdown documents that list it under `applies_to:` (exact) or name it in their text (fuzzy). Use `codegraph explore` or `codegraph node` to name the changed symbols and their callers.
2. **Ask the docs graph, read-only.** If the script printed `docs-graph: ok <path>` or `stale <path>`, run `graphify query "<constraints on SYMBOL or FILE>" --graph <path>` for the changed symbols and modules. Also look for `applies_to` entries that name a symbol: `grep` the docs for it. Never build or update the docs graph here; that costs tokens and belongs to `docs-curator` with the user's approval.
3. **Fall back when the graph is missing or stale.** For `docs-graph: missing`, say so, then search the repository's own ADR and design folders (`grep -rn` for the file and symbol names). For `stale`, say that the graph is older than the newest document, suggest re-running `docs-curator`, and still run the text search so a recent ADR is not missed.
4. **Judge each hit.** Read the document passage and the changed code. A hit is a candidate, not proof. Report, per candidate: the document path and status (superseded ADRs are not binding), the passage, the changed code, and a verdict: `consistent`, `possibly conflicting`, or `can't tell`. When nothing was found, say which sources you searched.

If a question mixes code and documents, answer each half from its own graph and label which graph each answer came from.

## Hard rules

- Never install codegraph. Never run `codegraph init`, `index` or `uninit` without the user's yes in this turn.
- Never write to the docs graph, `graphify-out/`, or the user's documents. The cross-graph step only reads.
- Never claim a conflict from a text match alone; read both sides first.
- Answer only code questions from the code graph. For what a document says, use `graphify` on the docs graph.
