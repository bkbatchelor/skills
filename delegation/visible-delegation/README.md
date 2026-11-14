# visible-delegation

Hands a bounded task to another coding agent session. The other session can be Claude Code or opencode, which is another coding agent. It runs in a [herdr](https://herdr.dev) pane, a section of your terminal that you can watch. herdr is an agent multiplexer, a tool that runs several agent sessions side by side. You can see every step, so the task never runs hidden in the background.

The other session is called the **delegate** in this document.

## How it works

1. **Prepare:** build a goal prompt with `goal-prompt-generator`.
2. **Launch:** start the delegate in a visible herdr pane.
3. **Monitor:** watch its progress. Step in only when a rule in `SKILL.md` says to.
4. **Verify:** run the checks in the goal prompt (its verification gates) yourself. Do this before you report the delegate's results.
5. **Clean up:** close the session.

## When it starts

It starts only when you ask. Ask for it when you want to delegate a task, hand work to another agent, or run work in parallel with another session. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat. It also installs `goal-prompt-generator`.

```text
/agentic-library use visible-delegation
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/delegation/visible-delegation ~/.claude/skills/visible-delegation
```

## Requirements

- **herdr.** If it is missing, `SKILL.md` lists the install steps. Install it before you launch a delegate.
- **The `goal-prompt-generator` skill.**

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions for the five steps, and notes for opencode |
| `scripts/launch.sh` | Starts the delegate session |
| `scripts/watch.sh` | Shows the session's progress |
| `scripts/say.sh` | Sends the delegate a message |
| `scripts/cleanup.sh` | Closes the session |
| `scripts/lib.sh` | Helper code shared by the scripts |
| `references/delegate-addendum.md` | Text added to the goal prompt for the delegate |
