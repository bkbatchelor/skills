# generate-readme

Generates and updates README files at a chosen fidelity level, with Mermaid diagrams where they help.

## Fidelity levels

| Level | Template |
|-------|----------|
| BASIC | `references/basic-level-template.md` |
| STANDARD | `references/standard-level-template.md` |
| ADVANCE | `references/advance-level-template.md` |

## Behavior

- Backs up an existing README before replacing it.
- Respects `.gitignore` when scanning the project.
- Follows its own Mermaid diagram guidelines.

## Install

```bash
/agentic-library use generate-readme
# or link it manually
ln -s ~/Projects/skills/generate-readme ~/.claude/skills/generate-readme
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: workflow, diagram guidelines, `.gitignore` handling and constraints |
| `references/` | One README template per fidelity level |
