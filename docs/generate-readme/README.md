# generate-readme

Generates and updates README files at a chosen fidelity level, with Mermaid diagrams where they help.

## Fidelity levels

| Level | Section guide |
|-------|----------|
| BASIC | `references/basic-level-template.md` |
| STANDARD | `references/standard-level-template.md` |
| ADVANCE | `references/advance-level-template.md` |

## Behavior

- Infers the fidelity level from the request and asks only when unclear.
- On update, keeps accurate human-written content instead of rewriting everything.
- Backs up the old README only when git cannot recover it.
- Respects `.gitignore` through git's file listing.
- Verifies commands, paths and Mermaid blocks before writing.
- Draws only diagrams the codebase supports.

## Triggers

Asks to write, generate, refresh, or update a README, or says a repo needs one. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use generate-readme
# or link it manually
ln -s ~/Projects/skills/docs/generate-readme ~/.claude/skills/generate-readme
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: workflow, diagram guidelines, `.gitignore` handling and constraints |
| `references/` | One section guide per fidelity level |
