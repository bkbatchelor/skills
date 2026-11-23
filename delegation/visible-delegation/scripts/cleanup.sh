#!/usr/bin/env bash
# Close a delegate properly: save its screen and transcript, then close the exact Orca
# terminal launch.sh created for it.
#
# Usage: cleanup.sh <name> [--force]
#
# Refuses (exit 3) while the delegate's task is still open (not succeeded or failed),
# unless --force. With --force it first asks Orca to stop the worker (worker-stop), and
# exits 1 without closing anything if Orca cannot confirm the stop.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: cleanup.sh <name> [--force]}
force=${2:-}
require_tools
load_meta "$name"

state=$(worker_state)
case $state in
  succeeded|failed|none) ;;
  *)
    if [[ $force != --force ]]; then
      echo "'$name' still has an open task (state: $state)."
      echo "Close it only if the user agreed; then rerun with --force."; exit 3
    fi
    stop=$("$ORCA" orchestration worker-stop --environment local --dispatch "$VD_DISPATCH" --json 2>&1)
    if [[ $(jq -r '.ok' <<<"$stop" 2>/dev/null) != true ]]; then
      echo "Orca could not confirm the worker stopped; nothing was closed. Check:"
      echo "  $ORCA orchestration worker-show --dispatch $VD_DISPATCH"
      echo "$stop"; exit 1
    fi ;;
esac

if [[ $(terminal_status) == running ]]; then
  screen > "$RUNDIR/screen.txt"
fi
t=$(transcript)
[[ -n $t ]] && cp "$t" "$RUNDIR/transcript.jsonl"

# A terminal launch.sh created is never closed by Orca's own worker release, so close
# exactly that one. Never close terminals this skill did not create.
if [[ $(terminal_status) == running ]]; then
  "$ORCA" terminal close --terminal "$VD_TERMINAL" --json >/dev/null 2>&1 \
    || echo "warning: Orca did not close terminal $VD_TERMINAL; check it in the app"
fi
echo "closed '$name' (task state: $state)"
saved="goal.md, prompt.md"
[[ -f $RUNDIR/screen.txt ]] && saved+=", screen.txt"
[[ -f $RUNDIR/transcript.jsonl ]] && saved+=", transcript.jsonl"
echo "run dir: $RUNDIR ($saved)"

others=""
for m in "$VD_ROOT"/deleg-*/meta.env; do
  [[ -f $m && $m != "$RUNDIR/meta.env" ]] || continue
  if (source "$m"; [[ $(terminal_status) == running ]]); then others+="$(basename "$(dirname "$m")")"$'\n'; fi
done
[[ -n $others ]] && { echo "other delegates still open:"; printf '%s' "$others"; }
exit 0
