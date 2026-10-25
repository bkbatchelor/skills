#!/usr/bin/env bash
# Close a delegate properly: save its screen and transcript, exit the agent, close its
# pane or workspace, and stop the delegates session once nothing is left in it.
#
# Usage: cleanup.sh <name> [--force]
#
# In session mode it refuses (exit 3) while a client is attached to the delegates
# session, unless --force, so the user isn't yanked out of something they're watching.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: cleanup.sh <name> [--force]}
force=${2:-}
require_tools
load_meta "$name"

if [[ $VD_MODE == session && $force != --force ]]; then
  attached=$(pgrep -af "herdr( .*)? (--session $VD_SESSION|session attach $VD_SESSION)( |$)" | grep -v ' server' || true)
  if [[ -n $attached ]]; then
    echo "a client is attached to herdr session '$VD_SESSION':"; echo "$attached"
    echo "ask the user to detach, or rerun with --force"; exit 3
  fi
fi

if [[ $(agent_status "$name") != gone ]]; then
  screen "$name" > "$RUNDIR/screen.txt"
  # Close any open dialog, then ask the agent to exit so it can save its own state.
  [[ $(agent_status "$name") == blocked ]] && { herdr agent send-keys "$name" esc >/dev/null; sleep 1; }
  herdr agent prompt "$name" "/exit" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do [[ $(agent_status "$name") == gone ]] && break; sleep 0.5; done
  if [[ $(agent_status "$name") != gone ]]; then
    herdr agent send-keys "$name" ctrl+c >/dev/null 2>&1; sleep 0.5
    herdr agent send-keys "$name" ctrl+c >/dev/null 2>&1; sleep 1
  fi
fi

if [[ -n ${VD_CLAUDE_SESSION_ID:-} ]]; then
  t=$(ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$VD_CLAUDE_SESSION_ID".jsonl 2>/dev/null | head -1)
  [[ -n $t ]] && cp "$t" "$RUNDIR/transcript.jsonl"
fi

if [[ $VD_MODE == session ]]; then
  herdr workspace close "$VD_WORKSPACE" >/dev/null 2>&1 || true
else
  herdr pane close "$VD_PANE" >/dev/null 2>&1 || true
fi
echo "closed '$name'"
echo "run dir: $RUNDIR (goal.md, prompt.md, screen.txt${VD_CLAUDE_SESSION_ID:+, transcript.jsonl})"

# Stop the delegates session only if this skill started it and it's now empty.
if [[ $VD_MODE == session && -f $VD_ROOT/.owns-session-$VD_SESSION ]]; then
  left=$(herdr workspace list 2>/dev/null | jq '.result.workspaces | length' 2>/dev/null || echo 1)
  if [[ $left == 0 ]]; then
    unset HERDR_SESSION
    herdr session stop "$VD_SESSION" >/dev/null 2>&1 && herdr session delete "$VD_SESSION" >/dev/null 2>&1
    rm -f "$VD_ROOT/.owns-session-$VD_SESSION"
    echo "stopped empty herdr session '$VD_SESSION'"
  fi
fi

others=$(herdr agent list 2>/dev/null | jq -r '.result.agents[]?.name // empty' 2>/dev/null | grep '^deleg-' || true)
[[ -n $others ]] && { echo "other delegates still running:"; echo "$others"; }
exit 0
