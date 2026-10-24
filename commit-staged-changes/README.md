# commit-staged-changes

Commits only what is already staged, using a fixed commit message template. It never stages new or untracked files.

## When it runs

Use it when you want to commit staged changes without sweeping in anything else, for example after a partial `git add -p`.

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
