#!/usr/bin/env bash
# Start a delegate agent in an Orca terminal tab the user can watch, and hand it the goal
# as a supervised Orca worker task.
#
# Usage: launch.sh <name> <workdir> <goal-file> [claude|opencode] [-- extra agent args...]
#        launch.sh --assign <name>     hand over the goal after a startup dialog (exit 4)
#
#   <name>  delegate name, e.g. deleg-readme  ([a-z][a-z0-9_-]{0,31})
#
# <workdir> must be inside a workspace Orca knows. The tab opens in that workspace
# without taking focus. Orca then wakes the supervisor when the delegate reports, asks a
# question, or stops at a prompt only a person can answer.
#
# Exit codes: 0 started and assigned · 4 agent waiting on a startup dialog (goal NOT sent)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

watch_hint() {
  echo "Watch    : the '$VD_NAME' terminal tab in the '$VD_WORKSPACE_NAME' workspace in Orca"
  [[ -n ${VD_HIDDEN:-} ]] && echo "           Orca may not show the tab yet; the user can open it with: $ORCA terminal focus --terminal $VD_TERMINAL"
  return 0
}

# Hand the goal to the delegate's terminal as an Orca worker task.
assign() {
  [[ -z ${VD_DISPATCH:-} ]] || die "'$VD_NAME' already has a task (dispatch $VD_DISPATCH)"
  [[ $(terminal_status) == running ]] || die "the terminal for '$VD_NAME' is gone"
  local out err
  out=$("$ORCA" orchestration worker-start --environment local --spec-file "$RUNDIR/prompt.md" \
    --task-title "$VD_NAME" --terminal "$VD_TERMINAL" --json 2>&1 || true)
  err=$(jq -r '.error.code // empty' <<<"$out" 2>/dev/null || echo unparsed)
  # Never rerun worker-start on failure (Orca's rule): report and stop.
  [[ -z $err ]] || die "worker-start failed, do not rerun it; read failedStage and see SKILL.md §2: $out"
  meta_set VD_DISPATCH "$(jq -r '.result.dispatchId' <<<"$out")"
  meta_set VD_TASK "$(jq -r '.result.taskId' <<<"$out")"
  meta_set VD_RUN "$(jq -r '.result.runId' <<<"$out")"
  load_meta "$VD_NAME"
  cat <<EOF
Delegate started.
  name     : $VD_NAME ($VD_KIND)
  workdir  : $VD_WORKDIR
  orca     : terminal $VD_TERMINAL, dispatch $VD_DISPATCH, task $VD_TASK, run $VD_RUN
  run dir  : $RUNDIR
$(watch_hint)
Orca wakes you when it reports, asks, or waits on a prompt. End your turn now.
EOF
}

if [[ ${1:-} == --assign ]]; then
  name=${2:?usage: launch.sh --assign <name>}
  require_tools; load_meta "$name"; assign; exit 0
fi

[[ $# -ge 3 ]] || usage
name=$1 workdir=$2 goal=$3; shift 3
kind=claude
if [[ $# -gt 0 && $1 != -- ]]; then kind=$1; shift; fi
[[ ${1:-} == -- ]] && shift
extra=("$@")

require_tools
[[ $name =~ ^[a-z][a-z0-9_-]{0,31}$ ]] || die "name must match [a-z][a-z0-9_-]{0,31}"
[[ $kind == claude || $kind == opencode ]] || die "unsupported agent '$kind' (claude or opencode)"
command -v "$kind" >/dev/null || die "agent CLI '$kind' not found on PATH"
[[ -d $workdir ]] || die "workdir not found: $workdir"
[[ -f $goal ]] || die "goal file not found: $goal"
workdir=$(cd "$workdir" && pwd)

# `current` resolves the innermost Orca workspace enclosing the directory, so a subfolder
# or a symlinked path still finds it.
ws=$(cd "$workdir" && "$ORCA" worktree show --worktree current --json 2>&1 || true)
ws_name=$(jq -r '.result.worktree.displayName // empty' <<<"$ws" 2>/dev/null || true)
[[ -n $ws_name ]] || die "no Orca workspace contains $workdir. Add it first (orca repo add / orca worktree create). Orca said: $ws"

if [[ -f $VD_ROOT/$name/meta.env ]]; then
  (load_meta "$name"; [[ $(terminal_status) == gone ]]) \
    || die "a live delegate named '$name' already exists; pick another name or clean it up"
fi

RUNDIR=$VD_ROOT/$name
if [[ -e $RUNDIR ]]; then mv "$RUNDIR" "$RUNDIR.$(date +%Y%m%d-%H%M%S)"; fi
mkdir -p "$RUNDIR"
cp "$goal" "$RUNDIR/goal.md"
{ cat "$goal"; sed "s/{{NAME}}/$name/g" "$here/../references/delegate-addendum.md"; } > "$RUNDIR/prompt.md"

# --- agent command -------------------------------------------------------------------
cmd=("$kind")
sid=""
if [[ $kind == claude ]]; then
  sid=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen)
  # acceptEdits: file edits flow; most shell commands stop at an approval prompt, which
  # Orca reports to the supervisor as a worker waiting on a person. acceptEdits still
  # auto-allows some file commands (rm, mkdir...) inside the workdir, so the riskiest
  # ones are denied outright.
  has_mode=0
  for a in "${extra[@]}"; do [[ $a == --permission-mode* || $a == --dangerously-skip-permissions ]] && has_mode=1; done
  [[ $has_mode == 0 ]] && cmd+=(--permission-mode acceptEdits)
  # No --add-dir for the run dir: Orca delivers the goal, and an extra directory makes
  # Claude ask "do you trust this directory?" before it takes input.
  cmd+=(-n "$name" --session-id "$sid")
  # The delegate reports and asks through Orca mail. Without these, its own report stops
  # at an approval dialog.
  cmd+=(--allowedTools
    "Bash(orca orchestration send:*)" "Bash(orca orchestration ask:*)"
    "Bash(orca orchestration check:*)" "Bash(orca orchestration reply:*)")
  cmd+=(--disallowedTools
    "Bash(git push:*)" "Bash(git reset --hard:*)" "Bash(git clean:*)" "Bash(git branch -D:*)"
    "Bash(rm -r:*)" "Bash(rm -rf:*)" "Bash(rm -fr:*)" "Bash(rm -Rf:*)" "Bash(sudo:*)"
    "Bash(npm publish:*)" "Bash(cargo publish:*)" "Bash(orca orchestration reset:*)")
fi
cmd+=("${extra[@]}")
# exec: when the agent exits, the terminal ends too, so Orca sees the exit.
command_line="cd $(printf '%q' "$workdir") && exec$(printf ' %q' "${cmd[@]}")"

# --- terminal ------------------------------------------------------------------------
out=$(cd "$workdir" && "$ORCA" terminal create --worktree current --title "$name" --command "$command_line" --json 2>&1 || true)
term=$(jq -r '.result.terminal.handle // empty' <<<"$out" 2>/dev/null || true)
[[ -n $term ]] || die "Orca did not return a terminal: $out"
hidden=$(jq -r '.result.terminal.warning // empty' <<<"$out")

{
  printf 'VD_NAME=%q\nVD_KIND=%q\nVD_WORKDIR=%q\nVD_WORKSPACE_NAME=%q\n' "$name" "$kind" "$workdir" "$ws_name"
  printf 'VD_TERMINAL=%q\nVD_CLAUDE_SESSION_ID=%q\nVD_HIDDEN=%q\n' "$term" "$sid" "${hidden:+1}"
} > "$RUNDIR/meta.env"
load_meta "$name"

# Wait for the agent's input box. A startup dialog (Claude's "trust this folder?") also
# settles, so read the screen before assigning.
"$ORCA" terminal wait --terminal "$term" --for tui-idle --timeout-ms 60000 --json >/dev/null 2>&1 || true
shot=$(screen)
if [[ $(terminal_status) != running ]]; then
  die "the agent exited during startup. Last screen: $shot"
fi
if grep -qiE 'trust|press enter to continue|select an option|do you want to' <<<"$shot"; then
  cat <<EOF
BLOCKED_AT_STARTUP: '$name' shows a dialog before it can take the goal.
  run dir : $RUNDIR
$(watch_hint)
Ask the user to answer it in the tab (Orca does not let a supervisor answer another
agent's menus). Then hand over the goal:
  $here/launch.sh --assign $name
--- screen ---
$(tail -40 <<<"$shot")
EOF
  exit 4
fi

assign
exit 0
