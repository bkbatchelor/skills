# visible-delegation

Hands a bounded task to another coding agent session, then checks its work. The other session can be Claude Code or opencode, which is another coding agent. It runs in a terminal tab in Orca, an app for running coding agents side by side. You can watch every step, so the task never runs hidden in the background.

The other session is called the **delegate** in this document. Your own agent is the **supervisor**.

## How it works

1. **Prepare:** build a goal prompt with `goal-prompt-generator`.
2. **Launch:** open the delegate in a new Orca terminal tab and give it the goal as an Orca worker task. A worker task is Orca's way of tracking a job one agent gives another.
3. **Monitor:** Orca tells the supervisor when the delegate finishes, asks a question, or waits for an approval. The supervisor steps in only when a rule in `SKILL.md` says to.
4. **Verify:** the supervisor runs the checks in the goal prompt (its verification gates) itself before it reports the delegate's results.
5. **Clean up:** close the delegate's tab.

**Approvals are yours.** Orca doesn't let one agent answer another agent's approval dialogs. When the delegate asks to run a command, answer it in the delegate's tab. The supervisor tells you whether it is safe.

## When it starts

It starts only when you ask. Ask for it when you want to delegate a task, hand work to another agent and get it back checked, or run work in parallel with another session. `SKILL.md` lists every trigger phrase and when to skip the skill.

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

- **Orca and its `orca` command.** Check with `orca status`. If the command isn't found, install Orca first.
- **jq**, a command-line tool for reading JSON.
- **The `goal-prompt-generator` skill.**

The earlier version of this skill used herdr instead of Orca. It is in this repo's git history at commit `5feb7e1`.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions for the five steps, and notes for opencode |
| `scripts/launch.sh` | Opens the delegate's tab and gives it the goal |
| `scripts/status.sh` | Shows the delegate's state, screen, changed files and risky commands, once |
| `scripts/say.sh` | Sends the delegate a message through Orca |
| `scripts/cleanup.sh` | Saves the delegate's record and closes its tab |
| `scripts/lib.sh` | Helper code shared by the scripts |
| `references/delegate-addendum.md` | Text added to the goal prompt for the delegate |
