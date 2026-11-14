# goal-prompt-generator

Turns an implementation plan or task description into a goal prompt. A goal prompt is a written brief that a new AI agent session can follow on its own. An agent is an AI assistant that can run commands and change files. The brief says what to build, how to tell it is finished, which rules apply, which checks must pass, and when to stop.

## What a goal prompt contains

- **Objective:** what to build or change.
- **Definition of done:** how to tell the work is finished.
- **Repository constraints:** the rules for the code repository (repo) the work happens in.
- **Verification gates:** the checks that must pass before the work counts as done.
- **Stop conditions:** the points where the agent must stop and report back.

## When to use it

Use it when you want to hand work to:

- another session
- a subagent, which is a helper agent started by another agent
- a cloud agent, which runs on a remote server
- a worktree session, which runs in a separate copy of the repo that git calls a worktree

Use it also when you want to prepare a task now and start it later. The `visible-delegation` skill needs this skill to build its goal prompts.

## Triggers

It starts when you ask it to hand off a task, write a goal prompt, or package a plan for another session or agent. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use goal-prompt-generator
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/delegation/goal-prompt-generator ~/.claude/skills/goal-prompt-generator
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions the agent follows, and the steps it takes |
| `references/goal-prompt-template.md` | The goal prompt template |
