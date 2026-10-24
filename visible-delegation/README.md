# visible-delegation

Delegates a bounded task to another coding-agent session (Claude Code or opencode) running in a [herdr](https://herdr.dev) pane you can watch. It is never a hidden background run.

## Workflow

1. **Prepare:** build a goal prompt (uses `goal-prompt-generator`).
2. **Launch:** start the delegate in a visible herdr pane.
3. **Monitor:** watch progress and intervene under clear rules.
4. **Verify:** independently re-run the delegate's verification gates before reporting its results.
5. **Clean up:** close the session.

## Install

```bash
/agentic-library use visible-delegation   # also pulls goal-prompt-generator
# or link it manually
ln -s ~/Projects/skills/visible-delegation ~/.claude/skills/visible-delegation
```

## Requirements

- `herdr`. `SKILL.md` has install steps if it is missing.
- The `goal-prompt-generator` skill.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions for the five steps and opencode notes |
| `scripts/launch.sh` | Start the delegate session |
| `scripts/watch.sh` | Monitor it |
| `scripts/say.sh` | Send it a message |
| `scripts/cleanup.sh` | Close it |
| `scripts/lib.sh` | Shared helpers |
| `references/delegate-addendum.md` | Text added to the goal prompt for the delegate |
