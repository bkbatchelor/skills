#!/usr/bin/env bash
# Start a delegate agent in a named, detached tmux session that anyone can attach to.
#
# Usage: launch.sh <session> <workdir> <goal-file> [claude|opencode] [-- extra agent args...]
#
# Creates a run dir (goal, full prompt, raw pane log), opens the tmux session in
# <workdir> with a clean environment, starts the agent with the goal prompt plus the
# supervision addendum, and prints how to attach.
set -euo pipefail

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[[ $# -ge 3 ]] || usage
session=$1 workdir=$2 goal=$3; shift 3
cli=claude
if [[ $# -gt 0 && $1 != -- ]]; then cli=$1; shift; fi
[[ ${1:-} == -- ]] && shift
extra=("$@")

here=$(cd "$(dirname "$0")/.." && pwd)
root=${VISIBLE_DELEGATION_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/visible-delegation}
rundir=$root/$session

command -v tmux >/dev/null || { echo "tmux is not installed" >&2; exit 1; }
command -v "$cli" >/dev/null || { echo "agent CLI '$cli' not found on PATH" >&2; exit 1; }
[[ -d $workdir ]] || { echo "workdir not found: $workdir" >&2; exit 1; }
[[ -f $goal ]] || { echo "goal file not found: $goal" >&2; exit 1; }
[[ $session =~ ^[A-Za-z0-9_-]+$ ]] || { echo "session name must be [A-Za-z0-9_-]" >&2; exit 1; }
if tmux has-session -t "=$session" 2>/dev/null; then
  echo "tmux session '$session' already exists; pick another name or clean it up" >&2; exit 1
fi
workdir=$(cd "$workdir" && pwd)

mkdir -p "$rundir"
cp "$goal" "$rundir/goal.md"
{ cat "$goal"; sed "s/{{SESSION}}/$session/g" "$here/references/delegate-addendum.md"; } > "$rundir/prompt.md"
printf '%s\n' "$session" > "$rundir/session"
printf '%s\n' "$workdir" > "$rundir/workdir"
printf '%s\n' "$cli" > "$rundir/cli"

# The supervisor's own agent harness exports CLAUDE* variables (session ids, messaging
# sockets). Inherited by the delegate they make it think it is a nested child session,
# so strip them. Keep CLAUDE_CONFIG_DIR, which is user configuration.
unset_args=()
while IFS= read -r v; do
  [[ $v == CLAUDE_CONFIG_DIR ]] || unset_args+=(-u "$v")
done < <(env | grep -oE '^CLAUDE[A-Za-z0-9_]*' || true)
shell=${SHELL:-/bin/bash}

tmux new-session -d -s "$session" -x 220 -y 50 -c "$workdir" \
  "$(printf '%q ' env "${unset_args[@]}" "$shell" -l)"
# Raw byte log of everything the pane prints: an audit trail that survives scrollback limits.
tmux pipe-pane -t "=$session:" -o "cat >> $(printf '%q' "$rundir/pane.log")"

prompt_q=$(printf '%q' "$rundir/prompt.md")
extra_q=""
[[ ${#extra[@]} -gt 0 ]] && extra_q=$(printf ' %q' "${extra[@]}")
case $cli in
  claude)
    # acceptEdits: file edits flow, shell commands stop at a visible approval prompt.
    has_mode=0
    for a in "${extra[@]}"; do [[ $a == --permission-mode* || $a == --dangerously-skip-permissions ]] && has_mode=1; done
    mode=""; [[ $has_mode == 0 ]] && mode=" --permission-mode acceptEdits"
    # The prompt goes first: --add-dir and --allowedTools are variadic and would
    # swallow a trailing positional prompt as one of their values.
    cmd="claude \"\$(cat $prompt_q)\"$mode -n $(printf '%q' "$session") --add-dir $(printf '%q' "$rundir")$extra_q"
    ;;
  opencode)
    cmd="opencode$extra_q --prompt \"\$(cat $prompt_q)\" $(printf '%q' "$workdir")"
    ;;
  *)
    echo "unsupported CLI '$cli' (expected claude or opencode)" >&2
    tmux kill-session -t "=$session"; exit 1
    ;;
esac
printf '%s\n' "$cmd" > "$rundir/command"

# Give the login shell a moment to draw its prompt so the keystrokes aren't eaten.
for _ in $(seq 1 20); do
  [[ -n $(tmux capture-pane -p -t "=$session:" | tr -d '[:space:]') ]] && break
  sleep 0.25
done
tmux send-keys -t "=$session:" -l "$cmd"
tmux send-keys -t "=$session:" Enter

cat <<EOF
Delegate started.
  session : $session
  agent   : $cli
  workdir : $workdir
  run dir : $rundir
Watch    : tmux attach -r -t $session     (read-only, safe for watching)
Take over: tmux attach -t $session        (you can type; detach with Ctrl-b d)
EOF
