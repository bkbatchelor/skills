# commit-staged-changes

Commits only the changes you have already staged, using a fixed commit message template. It never stages new or untracked files.

Staging marks changes with `git add`, so the next commit includes them. A commit is a saved change in git, the tool that tracks file history. An untracked file is a new file that git does not track yet.

## When to use it

Use it when you want to commit staged changes and nothing else. For example, use it after a partial `git add -p`. That command lets you stage part of a file, one piece at a time.

## Triggers

It runs only when you ask it to commit staged changes, for example with "commit my staged changes". It never runs on its own. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use commit-staged-changes
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/git/commit-staged-changes ~/.claude/skills/commit-staged-changes
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: the workflow, commit types, examples, limits, and how it handles repository hooks (scripts that git runs at set points, such as before a commit) |
| `references/git-commit-template.md` | The commit message template the skill follows |
