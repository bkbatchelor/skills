# goal-prompt-generator

Turns an implementation plan or task description into a bounded, self-contained goal prompt that a fresh agent session can run on its own and be checked against.

## What a goal prompt contains

- Objective
- Definition of done
- Repository constraints
- Verification gates
- Stop conditions

## When it runs

Use it when you want to hand work to another session, subagent, cloud agent or worktree session, or prepare a task to kick off later. The `visible-delegation` skill depends on it.

## Install

```bash
/agentic-library use goal-prompt-generator
# or link it manually
ln -s ~/Projects/skills/goal-prompt-generator ~/.claude/skills/goal-prompt-generator
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions and workflow |
| `references/goal-prompt-template.md` | The goal prompt template |
