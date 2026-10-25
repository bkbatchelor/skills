# commit-staged-changes

Commits only what is already staged, using a fixed commit message template. It never stages new or untracked files.

## When it runs

Use it when you want to commit staged changes without sweeping in anything else, for example after a partial `git add -p`.

## Triggers

Only on an explicit request to commit staged changes ("commit my staged changes"). Never proactive. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use commit-staged-changes
# or link it manually
ln -s ~/Projects/skills/commit-staged-changes ~/.claude/skills/commit-staged-changes
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: workflow, commit types, examples, constraints and repository-hook handling |
| `references/git-commit-template.md` | The commit message template the skill follows |
