# generate-readme

Writes and updates README files. A README is the front page of a project. It explains what the project is and how to use it. You choose how much detail the README has. The skill also adds Mermaid diagrams where they help. Mermaid is a text format for drawing diagrams.

## Fidelity levels

Fidelity means how much detail the README includes. Pick one of three levels:

| Level | Section template |
|-------|----------|
| BASIC | `references/basic-level-template.md` |
| STANDARD | `references/standard-level-template.md` |
| ADVANCE | `references/advance-level-template.md` |

## How it behaves

- It works out the fidelity level from your request. It asks only when the request is unclear.
- When it updates a README, it keeps accurate content that a person wrote. It does not rewrite everything.
- It makes a backup of the old README only when git cannot recover the old version. Git is the tool that tracks file history.
- It skips files that `.gitignore` lists. That file tells git which files to leave out.
- It checks commands, file paths and Mermaid blocks before it writes them down.
- It draws only the diagrams that the code supports.

## When it starts

Ask it to write, generate, refresh or update a README, or tell it that a repo needs one. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use generate-readme
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/docs/generate-readme ~/.claude/skills/generate-readme
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: the workflow, diagram rules, `.gitignore` handling and limits |
| `references/` | One section template for each fidelity level |
