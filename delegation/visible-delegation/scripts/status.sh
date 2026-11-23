#!/usr/bin/env bash
# One-shot check on a delegate: worker state, whether it waits on a person, the screen,
# git status of the workdir, and any risky shell commands it ran since the last check.
# Run it when Orca wakes you about the delegate, or when the user asks how it is doing.
# It is not a watcher: never loop it. Orca wakes you.
#
# Usage: status.sh <name> [--all-commands]
#
# The first line is a summary, e.g.
#   STATE running · WAITING-ON-PERSON hook · TERMINAL running
# followed by lines starting with DANGER for each new risky command (Claude only).
# --all-commands also lists every shell command the delegate has run so far.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: status.sh <name> [--all-commands]}
all=${2:-}
require_tools
load_meta "$name"

danger_re='rm -[a-zA-Z]*[rRf]|git push|--force|reset --hard|git clean|git checkout -- |git branch -D|drop (table|database)|truncate table|mkfs|dd if=|chmod -R|chown -R|curl [^|]*\| *(ba|z)?sh|wget [^|]*\| *(ba|z)?sh|sudo |npm publish|cargo publish|twine upload|kubectl (delete|apply)|terraform (apply|destroy)|orca orchestration reset'

show=""
[[ -n ${VD_DISPATCH:-} ]] && show=$("$ORCA" orchestration worker-show --environment local --dispatch "$VD_DISPATCH" --json 2>/dev/null || true)
state=$(jq -r '.result.state // empty' <<<"$show" 2>/dev/null); state=${state:-none}
# agentWait: null means Orca looked and found no wait; absent means it could not tell.
wait=$(jq -r 'if (.result.observation | type) != "object" then "unknown"
              elif .result.observation.agentWait == null then "no"
              else (.result.observation.agentWait.evidence // "yes") end' <<<"$show" 2>/dev/null)
term=$(terminal_status)
echo "STATE $state · WAITING-ON-PERSON ${wait:-unknown} · TERMINAL $term"

# Claude collapses shell calls on screen ("Ran 1 shell command"), so read the exact
# commands from its session transcript instead of scraping the terminal.
t=$(transcript)
if [[ -n $t ]]; then
  seen=$RUNDIR/commands-seen; [[ -f $seen ]] || echo 0 > "$seen"
  cmds=$(jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Bash") | .input.command | gsub("\n"; " ")' "$t" 2>/dev/null)
  n=$(grep -c . <<<"$cmds" || true)
  tail -n +"$(( $(cat "$seen") + 1 ))" <<<"$cmds" | grep -E "$danger_re" | sed 's/^/DANGER /'
  echo "$n" > "$seen"
  if [[ $all == --all-commands ]]; then echo "--- shell commands run ($n) ---"; echo "$cmds"; fi
elif [[ $VD_KIND == claude ]]; then
  echo "(no Claude transcript yet)"
fi

if [[ $term == running ]]; then
  echo "--- screen (last 40 lines) ---"
  screen | tail -40
fi
if git -C "$VD_WORKDIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "--- git status --short ($VD_WORKDIR) ---"
  git -C "$VD_WORKDIR" status --short | head -30
fi
exit 0
