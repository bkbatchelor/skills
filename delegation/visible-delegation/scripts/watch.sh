#!/usr/bin/env bash
# Block until a delegate needs the supervisor's attention, then print one event line
# plus context and exit. Run it in the background; re-arm after handling each event.
#
# Usage: watch.sh <name> [heartbeat_secs=300]
#
# Events (first line of output):
#   COMPLETE <DONE|BLOCKED>  the delegate printed a new DELEGATE-STATUS line
#   PROMPT                   herdr reports the agent blocked on an approval/question dialog
#   IDLE                     the agent finished a turn without a status line (question? stalled?)
#   DANGER <command>         the delegate ran or proposed a risky shell command (claude transcript)
#   HEARTBEAT <secs>         still working; routine check-in
#   GONE                     the agent is no longer running in its pane
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: watch.sh <name> [heartbeat_secs]}
heartbeat=${2:-300}
require_tools
load_meta "$name"

danger_re='rm -[a-zA-Z]*[rRf]|git push|--force|reset --hard|git clean|git checkout -- |git branch -D|drop (table|database)|truncate table|mkfs|dd if=|chmod -R|chown -R|curl [^|]*\| *(ba|z)?sh|wget [^|]*\| *(ba|z)?sh|sudo |npm publish|cargo publish|twine upload|kubectl (delete|apply)|terraform (apply|destroy)'
seen_status=$RUNDIR/status-seen     # how many DELEGATE-STATUS lines were already reported
seen_cmds=$RUNDIR/commands-seen     # how many transcript commands were already scanned
[[ -f $seen_status ]] || echo 0 > "$seen_status"
[[ -f $seen_cmds ]] || echo 0 > "$seen_cmds"

transcript() {
  [[ -n ${VD_CLAUDE_SESSION_ID:-} ]] || return 0
  ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$VD_CLAUDE_SESSION_ID".jsonl 2>/dev/null | head -1
}

check_danger() {
  # Claude collapses shell calls on screen ("Ran 1 shell command"), so read the exact
  # commands from its session transcript instead of scraping the terminal.
  local t; t=$(transcript); [[ -n $t ]] || return 1
  local cmds n hit
  cmds=$(jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Bash") | .input.command | gsub("\n"; " ")' "$t" 2>/dev/null)
  n=$(grep -c . <<<"$cmds" || true)
  hit=$(tail -n +"$(( $(cat "$seen_cmds") + 1 ))" <<<"$cmds" | grep -E "$danger_re" | head -1)
  echo "$n" > "$seen_cmds"
  [[ -n $hit ]] || return 1
  echo "DANGER $hit"
}

start=$(date +%s)
while :; do
  # Waits for the first settled state (idle, done or blocked); a timeout means "still working".
  herdr agent wait "$name" --timeout 20000 >/dev/null 2>&1
  status=$(agent_status "$name")

  if [[ $status == gone ]]; then echo "GONE"; exit 0; fi
  if check_danger; then context "$name"; exit 0; fi

  case $status in
    blocked) echo "PROMPT"; context "$name"; exit 0 ;;
    idle|done)
      # The addendum describes the status line without spelling a literal match, so only
      # the delegate's own report counts. Count occurrences so a status already reported
      # (still in scrollback after a follow-up message) isn't reported twice.
      statuses=$(screen "$name" | grep -oE 'DELEGATE-STATUS: (DONE|BLOCKED)\b')
      count=$(grep -c . <<<"$statuses" || true)
      if (( count > $(cat "$seen_status") )); then
        echo "$count" > "$seen_status"
        echo "COMPLETE $(tail -1 <<<"$statuses" | sed 's/DELEGATE-STATUS: //')"
      else
        echo "IDLE"
      fi
      context "$name"; exit 0 ;;
  esac

  if (( $(date +%s) - start >= heartbeat )); then
    echo "HEARTBEAT $(( $(date +%s) - start ))"; context "$name"; exit 0
  fi
done
