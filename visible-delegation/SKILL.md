---
name: visible-delegation
description: Delegate work to another coding-agent session (Claude Code or opencode) running in a herdr pane the user can watch, never as a hidden background run. Covers building a goal prompt, launching, monitoring with clear intervention rules, independently verifying the delegate's claimed results, and closing the session afterward. Use whenever the user asks to delegate a task, hand work off to another agent or session, run something in parallel with another Claude/agent, "spin up a second agent", "have another session do X while we do Y", or farm out a subtask, even if they don't mention herdr or visibility.
metadata:
  version: 1.0.0
---

# Visible Delegation

Hand a bounded task to a second agent that runs **in the open**: a pane in [herdr](https://herdr.dev), the terminal workspace manager for coding agents. The user can watch it live and take over at any moment. You are the supervisor. You write the goal, launch the delegate, watch it, step in when it goes wrong, check its work yourself, and close it when you're done.

Why visibility matters: a hidden background run (a `claude -p &`, `nohup`, or a background subagent) can't be watched, interrupted, or redirected. If it goes wrong, nobody finds out until the damage is done. A shared terminal keeps the user in control and lets you intervene before a bad command runs. So when this skill applies, don't fall back to hidden execution, even if it seems faster.

Scripts live in `scripts/` next to this file. Call them by absolute path. They need `herdr` and `jq`. Each delegate gets a run dir at `~/.local/state/visible-delegation/<name>/` (override with `VISIBLE_DELEGATION_DIR`) containing:
- `goal.md`
- `prompt.md` (goal plus supervision addendum)
- `meta.env` (herdr ids)
- after cleanup, `screen.txt` and `transcript.jsonl`

## Where the delegate runs

herdr's own rule is never to drive the user's focused session from outside herdr. The scripts respect that and pick a mode automatically:

- **You are inside herdr** (`HERDR_ENV=1`): the delegate gets a **sibling pane** in your current tab, opened without stealing focus. The user sees it next to you. `VD_SPLIT=down` splits downward instead of to the right.
- **You are outside herdr**: the delegate gets its own **workspace in a dedicated named session**, `delegates` (override with `VISIBLE_DELEGATION_SESSION`). The scripts start it headless if needed. The user watches with `herdr session attach delegates` in another terminal. The session is stopped again once its last delegate is cleaned up, if the scripts started it.

## 1. Prepare

**Check the tools.** Run `command -v herdr jq` plus the agent CLI. If herdr is missing, don't install it yourself. Give the user the steps in [Install herdr](#install-herdr) and wait for them to confirm. If the user would rather not install it, the tmux-based version of this skill is in this repo's git history at commit `9e60481`.

**Pick the delegate CLI.** The default is `claude` (Claude Code). Use `opencode` when the user asks for it.

**Bound the task.** Delegation only works for a task with a clear finish line. If the request is vague, settle the open decisions with the user first. Anything left undecided turns into the delegate's improvisation.

**Write the goal prompt.** If the `goal-prompt-generator` skill is available, use it. It produces the structure this skill depends on: Objective, Definition of Done, Repo Constraints, Verification Gates (exact commands with expected results), Stop Conditions, and Completion Report. Without it, write those sections yourself, grounded in the real repo: check that paths exist, take commands from the repo's actual scripts, and run the gates once for a baseline. Save the prompt to a file outside the repo, e.g. `<your scratch dir>/<slug>-goal.md`.

Write each gate as an executable command in a fenced code block, not inside a markdown table. Table cells force `|` to be escaped as `\|`, and in `grep -E` that escape matches a literal pipe, which silently breaks the gate.

**Isolate parallel work.** If the delegate edits the same repo that you or another delegate are working in, give it its own git worktree and launch it there. Use `herdr worktree create`, or `git worktree add ../<repo>-<slug> -b <branch>`. Two agents editing one working tree corrupt each other's view of the code.

**Show the user before launching.** Give a short summary: objective, the gates, what's off-limits, and the delegate's name. Also include the goal file path. If the task is risky or the user asked to review, wait for their go-ahead. Otherwise proceed, since they asked for the delegation.

## 2. Launch

Name the delegate `deleg-<short-slug>` (lowercase, `[a-z][a-z0-9_-]`, at most 32 characters, e.g. `deleg-readme`). The prefix makes delegates easy to tell apart from the user's own agents.

```bash
<skill>/scripts/launch.sh deleg-<slug> <workdir> <goal-file> [claude|opencode] [-- extra agent args]
```

The script:
1. Creates the pane.
2. Starts the agent with `herdr agent start`.
3. Submits the goal prompt plus `references/delegate-addendum.md` with `herdr agent prompt`. The addendum tells the delegate it's being watched, to obey supervisor messages, and to end with a `DELEGATE-STATUS` line.

For Claude it also passes:
- `--permission-mode acceptEdits`: file edits flow, and most shell commands stop at an approval dialog that herdr reports as `blocked`.
- `--disallowedTools` deny rules for the worst commands (`git push`, `git reset --hard`, `git clean`, `rm -r*`, `sudo`, publishing). `acceptEdits` still auto-allows some file commands, such as `rm` inside the workdir, so the approval dialog alone isn't a complete safety net.
- `--session-id`: puts Claude's transcript at a known path, so the watcher can read every shell command it actually ran.

Pass `-- --allowedTools "Bash(<gate cmd>:*)"` to pre-approve gate commands if prompts get too chatty. Only change the permission mode if the user asks.

**Exit code 4 (`BLOCKED_AT_STARTUP`)**: the agent hit a dialog before it could take the prompt. This is usually Claude's "trust this folder?" for a directory it hasn't opened before. Read the screen the script prints. If it's the trust dialog for the workdir the user asked you to delegate in, accept it (`say.sh <name> --key down enter` selects "Yes, I trust this folder"). Anything else, ask the user. Then send the goal: `say.sh <name> --file <run dir>/prompt.md`.

**Then tell the user how to watch:**

> Delegate `deleg-<slug>` is running.
> Watch: *(inside herdr)* the new pane beside this one · *(outside herdr)* `herdr session attach delegates` in another terminal, then open the `deleg-<slug>` workspace.

herdr has no read-only attach. If the user types into the delegate's pane, they've taken the wheel. Stop sending input until they hand it back.

## 3. Monitor

Run the watcher **in the background**, so the harness wakes you when something happens. Don't poll in the foreground or sleep:

```bash
<skill>/scripts/watch.sh deleg-<slug> [heartbeat_secs=300]
```

It blocks on herdr's own agent state (`herdr agent wait`), so it costs nothing while the delegate works. It exits with one event line, followed by the recent screen and `git status --short` of the workdir. Handle the event, then re-arm the watcher. Re-arm only after you've sent input or decided to keep waiting. Re-arming while the agent is still sitting idle just reports `IDLE` again. 5 minutes suits most tasks as a heartbeat; use less for short tasks and more for long builds.

| Event | What it means | What to do |
|---|---|---|
| `COMPLETE DONE/BLOCKED` | The delegate printed a new status line. | Go to §4. |
| `PROMPT` | herdr reports `blocked`: an approval or question dialog is open. | Decide using the approval policy below. |
| `DANGER <cmd>` | Claude's transcript shows a risky shell command. | Look right away. If it's still a pending dialog, deny it. If it already ran, assess the damage and tell the user. |
| `IDLE` | The turn ended without a status line. | Read the screen. It's usually a question for you, or it stopped early. |
| `HEARTBEAT` | Still working; routine check-in. | Skim the screen and git status for drift, then re-arm. |
| `GONE` | The agent no longer runs in its pane. | Find out why (the user exited it? a crash?) and tell the user. Check what was left in the working tree. |

### Approval policy for the delegate's prompts

You may approve on the user's behalf:
- Commands that are verification gates in the goal prompt.
- Read-only inspection (`ls`, `cat`, `git status/diff/log`, `grep`).
- Builds and tests inside the workdir.
- Edits to paths the goal prompt allows.

**Don't** approve anything that deletes outside the allowed area, rewrites git history, pushes, publishes, installs dependencies the goal didn't allow, uses sudo, or reaches external services. Deny it (`--key esc`, then tell the delegate why), and ask the user if the action might really be needed. Destructive actions are the user's call, not yours or the delegate's.

### Intervene vs. be patient

**Step in when:**
- **Destructive or outward-facing commands** are proposed or run (see above). Act immediately; this is the one case where waiting costs the most.
- **Scope drift**: `git status` shows files outside the allowed paths, or the screen shows work the goal didn't ask for ("while I'm here, let me refactor…"). Redirect it to the goal and name the files to restore or leave alone.
- **A stuck loop**: the same error, command, or edit three or more times with no new idea, or edits that flip back and forth. Interrupt and point at the Stop Condition about repeated failures, or give it the missing fact if you have it.
- **Questions to the supervisor**: answer from the goal prompt if it covers the question. If the answer would change the scope or a design decision, relay it to the user instead of inventing one.
- **No real progress**: many heartbeats where the git status and the screen's substance haven't moved.
- **The delegate breaks the goal's rules** (commits when told not to, adds a dependency, skips the gates).

**Be patient when:**
- It's exploring and reading files early on. That's how it grounds itself.
- A long build or test suite is running.
- It's iterating on a failing gate with *different* fixes, under the attempt limit the goal set.
- It takes a different route than you would, while staying in scope.

Each intervention costs the delegate context and momentum, so nudge only when the goal is actually at risk, not over style.

### How to intervene

Escalate only as far as needed:
1. **Nudge**: `scripts/say.sh deleg-<slug> "<message>"`. Be specific: quote the rule or section and name the files. herdr refuses to type a message into an open dialog, so answer the dialog first.
2. **Interrupt and redirect**: `scripts/say.sh deleg-<slug> --key esc` stops the agent's current turn. Then `say.sh` the correction.
3. **Pause for the user**: tell them what you saw (with a short screen excerpt) and what you recommend. Leave the delegate as it is.
4. **Stop**: only if the user agrees, or a destructive action is underway and interrupting can't contain it. Then run `cleanup.sh` and report what state the working tree is in.

To answer a dialog, send the option's key: `--key 1` for "Yes", or `--key esc` to deny. Always read the screen right before sending. Dialogs change, and a stale keypress can approve the wrong thing. To read more than the watcher showed, use `herdr agent read deleg-<slug> --source recent-unwrapped --lines 200`. Outside herdr, set `HERDR_SESSION=delegates` first.

## 4. Results: verify, then report

The delegate's report is a claim, not evidence. When it reports `COMPLETE`:

1. **Read the report** in the watcher output, or with `herdr agent read`.
2. **Re-run every Verification Gate yourself** from the goal prompt: same command, same directory. Compare against the *expected result in the goal prompt*, not the delegate's stated result.
3. **Check every Definition of Done item.** Each should map to a gate you just ran, or to an inspection you actually performed.
4. **Check the scope.** Run `git status --short` and `git diff --stat` (against the base, if it committed). Every change must be inside the allowed paths, with nothing from the "Must NOT touch" list. Skim the shell commands it ran (`jq` over the transcript, or `transcript.jsonl` after cleanup) for anything the goal didn't call for.
5. **Report to the user** in this shape:

```
Delegation <name>: VERIFIED | FAILED VERIFICATION | BLOCKED
Gates (re-run by me):
  1. <command> — expected <x>, got <y> — PASS/FAIL
  ...
Definition of Done: <n>/<m> met (<list any unmet, with evidence>)
Scope: <files changed>; out-of-scope changes: none | <list>
Delegate's own claims that didn't hold: none | <list>
Delegate: <closed | still open: how to watch it>
```

Say "VERIFIED" only if every gate passed when *you* ran it. If something failed, tell the user plainly. Then, if the delegate is still open and the fix is within scope, offer to send the failure output back for one more round. Don't quietly fix the delegate's work yourself and present it as passing. The user should know who did what.

If the delegate is `BLOCKED`, relay the Stop Condition it hit, what it tried, and its options, and add your own recommendation.

## 5. Clean up

Close delegates; don't abandon them.

```bash
<skill>/scripts/cleanup.sh deleg-<slug>      # add --force only if the user said to close it while attached
```

The script:
1. Saves the screen and Claude's transcript to the run dir.
2. Asks the agent to `/exit`, falling back to Ctrl-C.
3. Closes the pane (inside herdr) or the workspace (delegates session).
4. Stops the delegates session if it started that session and nothing is left in it.

In session mode it refuses while a client is attached, because yanking the user out of something they're watching is rude. Ask them to detach, or confirm the force.

When to clean up:
- After you've reported verified results, unless the user wants to keep poking at the delegate. In that case, tell them it's still open and that it's theirs to close.
- After a stop the user agreed to.
- Before you end your own work, check `herdr agent list` (with `HERDR_SESSION=delegates` when outside herdr) for `deleg-*` agents. Close any you launched and still own, or explicitly hand them to the user. Never close panes, workspaces, or sessions you didn't create.

Also remove any worktree you created once its branch is merged or the user is done with it, after confirming it has no unsaved work they want.

## opencode notes

- Launch with `launch.sh ... opencode`. herdr starts it with `--kind opencode`.
- opencode's permissions come from its config, not a CLI flag. Check `~/.config/opencode/opencode.json` for `permission` settings before launching.
- There's no Claude transcript, so `DANGER` events aren't available. If shell commands run without approval, use shorter heartbeats and read the screen at each one.

## Install herdr

If `command -v herdr` fails, give the user these steps and wait for them to confirm. Don't run them yourself.

1. Install with one of:
   - Arch / Omarchy: `sudo pacman -S herdr`
   - Homebrew (macOS/Linux): `brew install herdr`
   - mise: `mise use -g herdr` (older mise: `mise use -g github:herdrdev/herdr`)
   - Nix: `nix profile install github:herdrdev/herdr/<latest release tag>`
   - Official script (Linux/macOS): `curl -fsSL https://herdr.dev/install.sh | sh`
   - Windows PowerShell: `powershell -ExecutionPolicy Bypass -c "irm https://herdr.dev/install.ps1 | iex"`
2. Verify with `herdr --version`. If the command isn't found, restart the terminal or add the install directory to `PATH`.
3. Run `herdr` once to complete the first-run onboarding.
4. Full docs: https://herdr.dev/docs/install/
