#!/usr/bin/env bash
# Close a delegate session properly: save the transcript, exit the agent, kill the session.
#
# Usage: cleanup.sh <session> [--force]
#
# Refuses (exit 3) while someone is attached unless --force, so the user is never
# yanked out of a session they are watching.
set -uo pipefail
session=${1:?usage: cleanup.sh <session> [--force]}
force=${2:-}
root=${VISIBLE_DELEGATION_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/visible-delegation}
rundir=$root/$session
target="=$session:"

if ! tmux has-session -t "=$session" 2>/dev/null; then
  echo "session '$session' is not running (already closed)"
  [[ -d $rundir ]] && echo "run dir: $rundir"
  exit 0
fi

clients=$(tmux list-clients -t "=$session" -F '#{client_tty}' 2>/dev/null)
if [[ -n $clients && $force != --force ]]; then
  echo "clients still attached to '$session':"; echo "$clients"
  echo "ask the user to detach (Ctrl-b d), or rerun with --force"; exit 3
fi

mkdir -p "$rundir"
tmux capture-pane -p -J -S - -t "$target" > "$rundir/transcript.txt"

# Ask the agent to exit before killing the session, so it can flush its own session state.
shell_name=$(basename "${SHELL:-bash}")
running=$(tmux display-message -p -t "$target" '#{pane_current_command}')
if [[ $running != "$shell_name" && $running != bash && $running != zsh && $running != fish ]]; then
  tmux send-keys -t "$target" Escape; sleep 0.5
  tmux send-keys -t "$target" -l "/exit"; sleep 0.5; tmux send-keys -t "$target" Enter
  for _ in $(seq 1 20); do
    running=$(tmux display-message -p -t "$target" '#{pane_current_command}' 2>/dev/null) || break
    [[ $running == "$shell_name" || $running == bash || $running == zsh || $running == fish ]] && break
    sleep 0.5
  done
  if [[ $running != "$shell_name" && $running != bash && $running != zsh && $running != fish ]]; then
    tmux send-keys -t "$target" C-c; sleep 0.5; tmux send-keys -t "$target" C-c; sleep 1
  fi
fi

tmux kill-session -t "=$session"
echo "closed '$session'"
echo "transcript: $rundir/transcript.txt"
echo "raw log   : $rundir/pane.log"
left=$(tmux ls -F '#{session_name}' 2>/dev/null | grep -E '^deleg-' || true)
[[ -n $left ]] && { echo "other delegate sessions still open:"; echo "$left"; }
exit 0
