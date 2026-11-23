---
name: visible-delegation
description: >-
  Delegate work to another coding-agent session (Claude Code or opencode) running as a supervised Orca worker in a terminal tab the user can watch, never as a hidden background run. Covers building a goal prompt, launching, handling Orca's wake-ups with clear intervention rules, independently verifying the delegate's claimed results, and closing the session afterward. Use whenever the user asks to delegate a task, hand work off to another agent or session and get it back checked, run something in parallel with another Claude or agent, "spin up a second agent", "have another session do X while we do Y", or farm out a subtask, even without mentioning Orca or visibility. Never launch a delegate on your own initiative. Only write the prompt without launching: use goal-prompt-generator.
metadata:
  version: 2.0.0
---

# Visible Delegation

Hand a bounded task to a second agent that runs **in the open**: a terminal tab in Orca, the agent workspace app, started as a supervised Orca worker. The user can watch it live and take over at any moment. You are the supervisor. You write the goal, launch the delegate, act when Orca wakes you, check its work yourself, and close it when you're done.

Why visibility matters: a hidden background run (a `claude -p &`, `nohup`, or a background subagent) can't be watched, interrupted, or redirected. If it goes wrong, nobody finds out until the damage is done. An Orca tab keeps the user in control. So when this skill applies, don't fall back to hidden execution, even if it seems faster.

Scripts live in `scripts/` next to this file. Call them by absolute path. They need the Orca CLI (`$ORCA_CLI_COMMAND`, or `orca` on `PATH`) and `jq`. Each delegate gets a run dir at `~/.local/state/visible-delegation/<name>/` (override with `VISIBLE_DELEGATION_DIR`) containing:
- `goal.md`
- `prompt.md` (goal plus supervision addendum)
- `meta.env` (Orca terminal, dispatch, task and run ids)
- `message-*.md` (what you sent it)
- after cleanup, `screen.txt` and `transcript.jsonl`

## Triggers

Use when the user asks to delegate a task, hand work off to another agent or session and get it back checked, run something in parallel with another Claude or agent, "spin up a second agent", "have another session do X while we do Y", or farm out a subtask.

Skip when:
- The user has not asked for delegation. Never launch a delegate on your own initiative.
- They only want a prompt written for a later run. Use `goal-prompt-generator`.
- They want a full handoff with nothing coming back ("hand this off", "give this to another worktree"). That is Orca's `orca-cli` handoff, not supervision.

## How Orca shapes this skill

Orca supervises workers itself, and its rules for supervisors apply here:
- **Orca wakes you.** When the delegate reports, asks a question, stops at a prompt only a person can answer, or exits, Orca sends you a message. Don't poll, sleep, or run watch loops: a polling script can take your mail and hide it from you.
- **You never type into the delegate's terminal.** Steer it with Orca mail (`say.sh`). You can't answer its approval dialogs or interrupt its turn. The user does that in its tab. The approval policy below tells you what to recommend.
- **Never rerun a failed Orca command on your own.** If `worker-start`, `send` or `reply` fails, do only what the CLI printed, or tell the user.

## 1. Prepare

**Check the tools.** Run `command -v "${ORCA_CLI_COMMAND:-orca}" jq` plus the agent CLI. If Orca is missing, don't install it yourself. Tell the user this skill needs the Orca app and its CLI, and wait. If the user would rather not use Orca, the herdr-based version of this skill is in this repo's git history at commit `5feb7e1`, and the tmux-based version at `9e60481`.

**Pick the delegate CLI.** The default is `claude` (Claude Code). Use `opencode` when the user asks for it.

**Bound the task.** Delegation only works for a task with a clear finish line. If the request is vague, settle the open decisions with the user first. Anything left undecided turns into the delegate's improvisation.

**Write the goal prompt.** If the `goal-prompt-generator` skill is available, use it. It produces the structure this skill depends on: Objective, Definition of Done, Repo Constraints, Verification Gates (exact commands with expected results), Stop Conditions, and Completion Report. Without it, write those sections yourself, grounded in the real repo: check that paths exist, take commands from the repo's actual scripts, and run the gates once for a baseline. Save the prompt to a file outside the repo, e.g. `<your scratch dir>/<slug>-goal.md`.

Write each gate as an executable command in a fenced code block, not inside a markdown table. Table cells force `|` to be escaped as `\|`, and in `grep -E` that escape matches a literal pipe, which silently breaks the gate.

**Pick the workdir.** It must be inside a workspace Orca knows (`orca worktree show --worktree current` from that directory says which). If the delegate edits the same repo that you or another delegate are working in, give it its own worktree: `orca worktree create --name <slug> --no-parent --json` (no `--agent`, so launch.sh starts the agent), and launch it there. Two agents editing one working tree corrupt each other's view of the code.

**Show the user before launching.** Give a short summary: objective, the gates, what's off-limits, and the delegate's name. Also include the goal file path. If the task is risky or the user asked to review, wait for their go-ahead. Otherwise proceed, since they asked for the delegation.

## 2. Launch

Name the delegate `deleg-<short-slug>` (lowercase, `[a-z][a-z0-9_-]`, at most 32 characters, e.g. `deleg-readme`). The prefix makes delegates easy to tell apart from the user's own agents.

```bash
<skill>/scripts/launch.sh deleg-<slug> <workdir> <goal-file> [claude|opencode] [-- extra agent args]
```

The script:
1. Opens a terminal tab titled with the delegate's name in the workdir's Orca workspace, without taking focus, and starts the agent in it.
2. Waits for the agent's input box.
3. Hands it `prompt.md` (the goal plus `references/delegate-addendum.md`) as a supervised Orca worker task (`orca orchestration worker-start --terminal`). Orca adds its own worker instructions, including how to ask you a question and how to report with `worker_done`.

For Claude it also passes:
- `--permission-mode acceptEdits`: file edits flow, and most shell commands stop at an approval dialog. Orca tells you when that happens.
- `--allowedTools` for `orca orchestration send/ask/check/reply`, so the delegate's own report and questions don't stop at a dialog.
- `--disallowedTools` deny rules for the worst commands (`git push`, `git reset --hard`, `git clean`, `rm -r*`, `sudo`, publishing, `orca orchestration reset`). `acceptEdits` still auto-allows some file commands, such as `rm` inside the workdir, so the approval dialog alone isn't a complete safety net.
- `--session-id`: puts Claude's transcript at a known path, so `status.sh` can read every shell command it actually ran.

Pass `-- --allowedTools "Bash(<gate cmd>:*)"` to pre-approve gate commands if the user gets too many dialogs. Only change the permission mode if the user asks.

**Exit code 4 (`BLOCKED_AT_STARTUP`)**: the agent shows a dialog before it can take the goal. This is usually Claude's "trust this folder?" for a directory it hasn't opened before. Show the user the screen the script printed and ask them to answer it in the tab. Then hand over the goal with `launch.sh --assign deleg-<slug>`.

**If `worker-start` fails**, don't rerun it. Read the `failedStage` it printed and follow `orca skills get orchestration --reference references/recovery-and-cleanup.md`, or tell the user. The terminal stays open; `cleanup.sh` closes it.

**Then tell the user how to watch, and end your turn:**

> Delegate `deleg-<slug>` is running in the `deleg-<slug>` terminal tab of the `<workspace>` workspace in Orca. Approval dialogs in that tab are yours to answer; I'll tell you which ones are safe.

If launch.sh said Orca did not show the tab, give the user the `orca terminal focus` command it printed. Don't run it yourself: it switches what they are looking at. If the user types into the delegate's tab, they've taken the wheel. Stop sending mail until they hand it back.

## 3. When Orca wakes you

Each wake is a message from the delegate's terminal. Run `scripts/status.sh deleg-<slug>` first: it prints the worker state, whether it waits on a person, any new `DANGER` commands from Claude's transcript, the screen, and `git status` of the workdir. Then act on the wake, and end your turn again.

| Wake | What it means | What to do |
|---|---|---|
| `worker_done`, outcome `succeeded` | The delegate says it's finished. | Go to §4. |
| `worker_done`, outcome `failed` | It hit a Stop Condition or is blocked. | Go to §4 and relay the blocker. |
| `question` | It asked you something. | Answer from the goal prompt with the `orca orchestration reply` command in the wake message. If the answer would change the scope or a design decision, ask the user first. |
| `escalation`, `needs-input` | It stopped at an approval or question dialog only a person can answer. | Read the dialog in the message and the screen, then tell the user what it wants and what you recommend under the approval policy below. |
| `escalation`, `exited` | The agent process exited without reporting. | Find out why (the user exited it? a crash?), check what was left in the working tree, and tell the user. |
| `escalation`, `lost` or other | Orca can't tell what happened. | Check `orca orchestration worker-show --dispatch <id>`. Don't send mail or retry while liveness is `unverifiable`; report the uncertainty to the user. |
| A `DANGER` line from `status.sh` | Claude's transcript shows a risky shell command. | Look right away. If it's still a pending dialog, tell the user to deny it. If it already ran, assess the damage and tell the user. |

If the user asks how the delegate is doing between wakes, run `status.sh` once and report. Don't start a loop.

### Approval policy for the delegate's dialogs

You answer none of them; the user does. When Orca says the delegate is waiting, recommend **approve** for:
- Commands that are verification gates in the goal prompt.
- Read-only inspection (`ls`, `cat`, `git status/diff/log`, `grep`).
- Builds and tests inside the workdir.
- Edits to paths the goal prompt allows.

Recommend **deny** for anything that deletes outside the allowed area, rewrites git history, pushes, publishes, installs dependencies the goal didn't allow, uses sudo, or reaches external services. Then tell the delegate why with `say.sh`, and ask the user whether the action is really needed. Destructive actions are the user's call, not yours or the delegate's.

If the dialogs keep coming for the same safe gate command, suggest relaunching with `-- --allowedTools "Bash(<cmd>:*)"` next time, or that the user picks "don't ask again" for it.

### Intervene vs. be patient

**Step in when:**
- **Destructive or outward-facing commands** are proposed or run (see above). Act immediately; this is the one case where waiting costs the most.
- **Scope drift**: `git status` shows files outside the allowed paths, or the screen shows work the goal didn't ask for ("while I'm here, let me refactor…"). Redirect it to the goal and name the files to restore or leave alone.
- **A stuck loop**: the same error, command, or edit three or more times with no new idea, or edits that flip back and forth. Point at the Stop Condition about repeated failures, or give it the missing fact if you have it.
- **Questions to the supervisor**: answer from the goal prompt if it covers the question. If the answer would change the scope or a design decision, relay it to the user instead of inventing one.
- **The delegate breaks the goal's rules** (commits when told not to, adds a dependency, skips the gates).

**Be patient when:**
- It's exploring and reading files early on. That's how it grounds itself.
- A long build or test suite is running.
- It's iterating on a failing gate with *different* fixes, under the attempt limit the goal set.
- It takes a different route than you would, while staying in scope.

Each intervention costs the delegate context and momentum, so step in only when the goal is actually at risk, not over style.

### How to intervene

Escalate only as far as needed:
1. **Mail**: `scripts/say.sh deleg-<slug> "<message>"`. Be specific: quote the rule or section and name the files. A working delegate reads it when its current turn ends, so mail can't stop a command that is about to run.
2. **Ask the user to stop the turn**: when it must stop now, tell the user to press Esc in the delegate's tab, then send the correction with `say.sh`.
3. **Pause for the user**: tell them what you saw (with a short screen excerpt) and what you recommend. Leave the delegate as it is.
4. **Stop**: only if the user agrees, or a destructive action is underway that the user can't stop in time. Run `cleanup.sh deleg-<slug> --force` and report what state the working tree is in.

To read more than `status.sh` showed, use `orca orchestration worker-read --dispatch <id> --limit 200`, or `status.sh deleg-<slug> --all-commands` for every shell command the Claude delegate ran.

## 4. Results: verify, then report

The delegate's report is a claim, not evidence. When its `worker_done` arrives:

1. **Read the report** in the wake message, or with `orca orchestration worker-read --dispatch <id>`.
2. **Re-run every Verification Gate yourself** from the goal prompt: same command, same directory. Compare against the *expected result in the goal prompt*, not the delegate's stated result.
3. **Check every Definition of Done item.** Each should map to a gate you just ran, or to an inspection you actually performed.
4. **Check the scope.** Run `git status --short` and `git diff --stat` (against the base, if it committed). Every change must be inside the allowed paths, with nothing from the "Must NOT touch" list. Skim the shell commands it ran (`status.sh deleg-<slug> --all-commands`) for anything the goal didn't call for.
5. **Report to the user** in this shape:

```
Delegation <name>: VERIFIED | FAILED VERIFICATION | BLOCKED
Gates (re-run by me):
  1. <command> — expected <x>, got <y> — PASS/FAIL
  ...
Definition of Done: <n>/<m> met (<list any unmet, with evidence>)
Scope: <files changed>; out-of-scope changes: none | <list>
Delegate's own claims that didn't hold: none | <list>
Delegate: <closed | still open: the tab to watch>
```

Say "VERIFIED" only if every gate passed when *you* ran it. If something failed, tell the user plainly. Then, if the delegate is still open and the fix is within scope, offer to send the failure output back for one more round (`say.sh`; Orca gives a finished worker the message as a follow-up task and wakes you on its next `worker_done`; the follow-up gets a new Dispatch id, which the wake message names and the scripts pick up on their own). Don't quietly fix the delegate's work yourself and present it as passing. The user should know who did what.

If the delegate reports `failed`, relay the Stop Condition it hit, what it tried, and its options, and add your own recommendation. A reported failure is a conclusion: never mark it completed.

## 5. Clean up

Close delegates; don't abandon them.

```bash
<skill>/scripts/cleanup.sh deleg-<slug>      # add --force only if the user agreed to stop an unfinished task
```

The script:
1. Refuses while the task is still open, unless `--force`. With `--force` it asks Orca to stop the worker first, and closes nothing if Orca can't confirm the stop.
2. Saves the screen and Claude's transcript to the run dir.
3. Closes the exact terminal launch.sh created. Orca's automatic worker release never closes a terminal it didn't start, so this step is always needed.
4. Lists other delegates that are still open.

When to clean up:
- After you've reported verified results, unless the user wants to keep using the delegate. In that case, tell them it's still open and that it's theirs to close.
- After a stop the user agreed to.
- Before you end your own work, check `ls ~/.local/state/visible-delegation/` for `deleg-*` delegates you launched and still own. Close them, or explicitly hand them to the user. Never close terminals, tabs, or workspaces you didn't create.

Also remove any worktree you created once its branch is merged or the user is done with it, after confirming it has no unsaved work they want (`orca worktree rm --worktree <selector>`).

## opencode notes

- Launch with `launch.sh ... opencode`. The script starts `opencode` in the tab and hands it the task the same way.
- opencode's permissions come from its config, not a CLI flag. Check `~/.config/opencode/opencode.json` for `permission` settings before launching, and make sure `orca orchestration send` and `ask` are allowed, or every report stops at a dialog.
- There's no Claude transcript, so `status.sh` prints no `DANGER` lines. If shell commands run without approval, read the screen and `git status` at every wake, and ask the user to keep the tab in view.

## Requirements

- **Orca**, the app and its CLI. Inside Orca, `ORCA_CLI_COMMAND` names the CLI. Run `orca status` to check the runtime is reachable.
- **jq**, to parse Orca's JSON output.
- The delegate's CLI (`claude` or `opencode`) on the host Orca runs agents on (`orca agent installed --json`).
