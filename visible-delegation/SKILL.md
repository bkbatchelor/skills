---
name: visible-delegation
description: Delegate work to another coding-agent session (Claude Code or opencode) running in a named tmux session the user can attach to and watch, never as a hidden background run. Covers building a goal prompt, launching, monitoring with clear intervention rules, independently verifying the delegate's claimed results, and closing the session afterward. Use whenever the user asks to delegate a task, hand work off to another agent or session, run something in parallel with another Claude/agent, "spin up a second agent", "have another session do X while we do Y", or farm out a subtask, even if they don't mention tmux or visibility.
---

# Visible Delegation

Hand a bounded task to a second agent session that runs **in the open**: a named tmux session the user can attach to, watch live, and take over at any moment. You are the supervisor. You write the goal, launch the delegate, watch it, step in when it goes wrong, check its work yourself, and close the session when you're done.

Why visibility matters: a hidden background run (a `claude -p &`, `nohup`, or a background subagent) can't be watched, interrupted, or redirected. If it goes wrong, nobody finds out until the damage is done. A shared terminal keeps the user in control and lets you intervene before a bad command runs. So when this skill applies, don't fall back to hidden execution, even if it seems faster.

Scripts live in `scripts/` next to this file. Call them by absolute path. Each run keeps its files in `~/.local/state/visible-delegation/<session>/` (override with `VISIBLE_DELEGATION_DIR`): `goal.md`, `prompt.md` (goal plus supervision addendum), `pane.log` (raw output), and at the end `transcript.txt`.

## 1. Prepare

**Check the tools.** Run `command -v tmux` plus the agent CLI. If tmux is missing, install it with the system package manager (e.g. `sudo pacman -S tmux`, `sudo apt install tmux`, `brew install tmux`), after confirming with the user since it needs sudo.

**Pick the delegate CLI.** The default is `claude` (Claude Code). Use `opencode` when the user asks for it. If neither is on PATH, stop and tell the user.

**Bound the task.** Delegation only works for a task with a clear finish line. If the request is vague, settle the open decisions with the user first. Anything left undecided turns into the delegate's improvisation.

**Write the goal prompt.** If the `goal-prompt-generator` skill is available, use it. It produces the structure this skill depends on: Objective, Definition of Done, Repo Constraints, Verification Gates (exact commands with expected results), Stop Conditions, and Completion Report. Without that skill, write those same sections yourself, grounded in the real repo: check that paths exist, take commands from the repo's actual scripts, and run the gates once for a baseline. Save the prompt to a file, not into the repo, e.g. `<your scratch dir>/<slug>-goal.md`.

The **Verification Gates** are what make your results protocol possible. A gate like "looks good" can't be re-run. Make every gate a command with an expected outcome, or a specific file inspection.

**Isolate parallel work.** If the delegate edits the same repo you or another delegate are working in, give it its own git worktree (`git worktree add ../<repo>-<slug> -b <branch>`) and launch it there. Two agents editing one working tree corrupt each other's view of the code.

**Show the user before launching.** Give a short summary: objective, the gates, what's off-limits, and the session name. Also include the goal file path. If the task is risky or the user asked to review, wait for their go-ahead. Otherwise proceed, since they asked for the delegation.

## 2. Launch

Name the session `deleg-<short-slug>` (e.g. `deleg-readme-update`). The prefix makes delegate sessions easy to tell apart from the user's own sessions.

```bash
<skill>/scripts/launch.sh deleg-<slug> <workdir> <goal-file> [claude|opencode] [-- extra agent args]
```

The script:
- Creates the detached session in `<workdir>`.
- Strips the supervisor's `CLAUDE*` environment variables, which would otherwise make the delegate believe it's a nested child session.
- Logs the pane to `pane.log`.
- Starts the agent with the goal prompt plus `references/delegate-addendum.md`. The addendum tells the delegate it's being watched, to obey typed-in supervisor messages, and to end with a `DELEGATE-STATUS` line.

Claude runs with `--permission-mode acceptEdits` by default. File edits flow freely, but every shell command stops at a visible approval prompt. That's the point where you catch destructive commands before they run. Pass `-- --allowedTools "Bash(<gate cmd>:*)" ...` to pre-approve the gate commands and read-only git if prompts get too chatty. Only switch modes if the user asks.

**Then tell the user how to watch**, using the commands the script prints:

> Delegate running in tmux session `deleg-<slug>`.
> Watch: `tmux attach -r -t deleg-<slug>` (read-only) · Take over: `tmux attach -t deleg-<slug>` · Detach: `Ctrl-b d`

Read-only attach is the safe default for watching, because keystrokes from the user's terminal would mix with yours. If the user attaches read-write and starts typing, they've taken the wheel. Stop sending keys until they hand it back.

## 3. Monitor

Run the watcher **in the background**, so the harness wakes you when something happens. Don't poll in the foreground or sleep:

```bash
<skill>/scripts/watch.sh deleg-<slug> [heartbeat_secs=300] [idle_secs=60]
```

It exits with a single event line, followed by the last 40 screen lines and `git status --short` of the delegate's workdir. Handle the event, then re-arm the watcher. For the first check, use a short heartbeat (~30s) to confirm the agent actually started (catches auth errors, trust dialogs, and a bad command line). After that, 5 minutes suits most tasks. Use shorter heartbeats for short tasks and longer ones for long builds.

| Event | What it means | What to do |
|---|---|---|
| `COMPLETE DONE/BLOCKED` | The delegate printed its status line. | Go to §4. |
| `PROMPT` | A permission or choice prompt is waiting. | Decide using the approval policy below. |
| `DANGER <cmd>` | A risky-looking command is on screen. | Look right away. If it's still a pending prompt, deny it. If it already ran, assess the damage and tell the user. |
| `IDLE` | The screen hasn't changed for a while. | Read the screen. The delegate is waiting (a question, a prompt, or done without the status line) or hung. |
| `HEARTBEAT` | Routine check-in. | Skim the screen and git status for drift, then re-arm. |
| `GONE` | The session vanished. | Find out why (the user closed it? a crash?) and tell the user. Check what was left in the working tree. |

### Approval policy for the delegate's prompts

You may approve on the user's behalf:
- Commands that are verification gates in the goal prompt.
- Read-only inspection (`ls`, `cat`, `git status/diff/log`, `grep`).
- Builds and tests inside the workdir.
- Edits to paths the goal prompt allows.

**Don't** approve anything that deletes outside the allowed area, rewrites git history, pushes, publishes, installs dependencies the goal didn't allow, uses sudo, or reaches external services. Deny it (pick "No"/Escape, then tell the delegate why with `say.sh`), and ask the user if the action might really be needed. Destructive actions are the user's call, not yours or the delegate's.

### Intervene vs. be patient

**Step in when:**
- **Destructive or outward-facing commands** are proposed or run (see above). Act immediately; this is the one case where waiting costs the most.
- **Scope drift**: `git status` shows files outside the allowed paths, or the screen shows work the goal didn't ask for ("while I'm here, let me refactor…"). Redirect it to the goal and name the files to restore or leave alone.
- **A stuck loop**: the same error, command, or edit three or more times with no new idea, or edits that flip back and forth. Interrupt and point at the Stop Condition about repeated failures, or give it the missing fact if you have it.
- **Questions to the supervisor**: answer from the goal prompt if it covers the question. If the answer would change the scope or a design decision, relay it to the user instead of inventing one.
- **No real progress**: idle with no prompt and no running command, or many heartbeats where the git status and the screen's substance haven't moved.
- **The delegate breaks the goal's rules** (commits when told not to, adds a dependency, skips the gates).

**Be patient when:**
- It's exploring and reading files early on. That's how it grounds itself.
- A long build or test suite is running and output is still moving.
- It's iterating on a failing gate with *different* fixes, under the attempt limit the goal set.
- It writes verbose reasoning or takes a different route than you would, while staying in scope.

Each intervention costs the delegate context and momentum, so nudge only when the goal is actually at risk, not over style.

### How to intervene

Escalate only as far as needed:
1. **Nudge**: `scripts/say.sh deleg-<slug> "<message>"` while it's waiting for input. Be specific: quote the rule or section and name the files.
2. **Interrupt and redirect**: `scripts/say.sh deleg-<slug> --key Escape` (Claude Code stops its current turn; opencode uses Escape too), then `say.sh` the correction.
3. **Pause for the user**: tell them what you saw (with a short screen excerpt) and what you recommend. Leave the session as it is.
4. **Stop**: only if the user agrees, or a destructive action is underway and interrupting can't contain it. Then run `cleanup.sh` and report what state the working tree is in.

To answer a selection prompt, send the option's key: `say.sh deleg-<slug> --key 1` for "Yes", or `--key Escape` to deny. Always read the screen right before sending. Prompts change, and a stale keypress can approve the wrong thing.

## 4. Results: verify, then report

The delegate's report is a claim, not evidence. When it reports `COMPLETE`:

1. **Read the report.** Capture it with `tmux capture-pane -p -J -S -300 -t deleg-<slug>`.
2. **Re-run every Verification Gate yourself** from the goal prompt: same command, same directory. Compare against the *expected result in the goal prompt*, not the delegate's stated result.
3. **Check every Definition of Done item.** Each should map to a gate you just ran, or to an inspection you actually performed.
4. **Check the scope.** Run `git status --short` and `git diff --stat` (against the base, if it committed). Every change must be inside the allowed paths, with nothing from the "Must NOT touch" list. Confirm it left no stray processes (`tmux` pane idle; no new servers listening).
5. **Report to the user** in this shape:

```
Delegation <slug>: VERIFIED | FAILED VERIFICATION | BLOCKED
Gates (re-run by me):
  1. <command> — expected <x>, got <y> — PASS/FAIL
  ...
Definition of Done: <n>/<m> met (<list any unmet, with evidence>)
Scope: <files changed>; out-of-scope changes: none | <list>
Delegate's own claims that didn't hold: none | <list>
Session: <closed | still open: tmux attach -r -t deleg-<slug>>
```

Say "VERIFIED" only if every gate passed when *you* ran it. If something failed, tell the user plainly. Then, if the session is still open and the fix is within scope, offer to send the failure output back to the delegate for one more round. Don't quietly fix the delegate's work yourself and present it as passing. The user should know who did what.

If the delegate is `BLOCKED`, relay the Stop Condition it hit, what it tried, and its options, and add your own recommendation.

## 5. Clean up

Close sessions; don't abandon them.

```bash
<skill>/scripts/cleanup.sh deleg-<slug>      # add --force only if the user said to close it while attached
```

The script saves the full transcript to the run dir, asks the agent to `/exit`, and kills the session. It refuses while a client is attached, because yanking the user out of a session they're watching is rude. Ask them to detach (`Ctrl-b d`), or confirm the force.

When to clean up:
- After you've reported verified results, unless the user wants to keep poking at the session. In that case, tell them it's still open and that it's theirs to close.
- After a stop the user agreed to.
- Before you end your own work, check `tmux ls | grep '^deleg-'`. Close any session you launched and still own, or explicitly hand it to the user. Never kill a session you didn't launch.

Also remove any worktree you created once its branch is merged or the user is done with it (`git worktree remove <path>`), after confirming it has no unsaved work they want.

## opencode notes

- Launch with `launch.sh ... opencode`. The prompt is passed with `--prompt`, and the TUI opens in the workdir.
- opencode's permissions come from its config, not a CLI mode flag. Check `~/.config/opencode/opencode.json` for `permission` settings before launching. If shell commands run without approval, watch more closely (shorter heartbeats) because the `PROMPT` safety net isn't there. Don't pass `--auto` unless the user asks.
- `cleanup.sh` sends `/exit` and falls back to Ctrl-C, which works for both TUIs.
