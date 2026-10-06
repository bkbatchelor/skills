#!/usr/bin/env bash
# Block until a delegate session needs the supervisor's attention, then print one
# event line plus context and exit. Run it in the background and re-arm after
# handling each event.
#
# Usage: watch.sh <session> [heartbeat_secs=300] [idle_secs=60]
#
# Events (first line of output):
#   COMPLETE <DONE|BLOCKED>  the delegate printed its DELEGATE-STATUS line
#   PROMPT                   a permission or choice prompt is waiting for an answer
#   DANGER <text>            a risky-looking command appeared on screen
#   IDLE <secs>              the screen has not changed for idle_secs (stuck, asking, or waiting)
#   HEARTBEAT <secs>         nothing notable happened; routine check-in
#   GONE                     the tmux session no longer exists
set -uo pipefail

session=${1:?usage: watch.sh <session> [heartbeat_secs] [idle_secs]}
heartbeat=${2:-300}
idle_limit=${3:-60}
root=${VISIBLE_DELEGATION_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/visible-delegation}
seen=$root/$session/danger-seen
mkdir -p "$root/$session"; touch "$seen"

target="=$session:"
danger_re='rm -[a-zA-Z]*[rf][a-zA-Z]* |git push|push --force|--force-with-lease|reset --hard|git clean -[a-z]*f|git checkout -- \.|git branch -D|drop (table|database)|truncate table|mkfs|dd if=|chmod -R 777|curl [^|]*\| *(ba|z)?sh|wget [^|]*\| *(ba|z)?sh|sudo |npm publish|cargo publish|twine upload|kubectl (delete|apply)|terraform (apply|destroy)'
prompt_re='Do you want to (proceed|make this edit|create|allow)|Do you trust the files|❯ *1\. Yes|Permission required|Allow once|\[y/n\]|\(y/N\)|\(Y/n\)'

context() {
  echo "--- screen (last 40 lines) ---"
  tmux capture-pane -p -J -t "$target" 2>/dev/null | sed '/^[[:space:]]*$/d' | tail -40
  local dir
  dir=$(tmux display-message -p -t "$target" '#{pane_current_path}' 2>/dev/null)
  if [[ -n $dir ]] && git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    echo "--- git status --short ($dir) ---"
    git -C "$dir" status --short | head -30
  fi
}

start=$(date +%s); last_change=$start; last_hash=""
while :; do
  if ! tmux has-session -t "=$session" 2>/dev/null; then echo "GONE"; exit 0; fi

  screen=$(tmux capture-pane -p -J -t "$target")
  history=$(tmux capture-pane -p -J -S -300 -t "$target")
  now=$(date +%s)

  # The addendum describes the status line without ever spelling a literal match,
  # so only the delegate's own report can trigger this.
  if status=$(grep -oE 'DELEGATE-STATUS: (DONE|BLOCKED)\b' <<<"$history" | tail -1) && [[ -n $status ]]; then
    echo "COMPLETE ${status#DELEGATE-STATUS: }"; context; exit 0
  fi

  if grep -qE "$prompt_re" <<<"$screen"; then
    echo "PROMPT"; context; exit 0
  fi

  # Only lines that look like commands being run or proposed, not prose about them.
  hit=$(grep -E '(Bash\(|^\s*[$#] |^\s*│? *\$ |Run(ning)? command|Shell)' <<<"$screen" | grep -iE "$danger_re" | head -1)
  if [[ -n $hit ]] && ! grep -qxF "$hit" "$seen"; then
    printf '%s\n' "$hit" >> "$seen"
    echo "DANGER $hit"; context; exit 0
  fi

  hash=$(md5sum <<<"$screen" | cut -d' ' -f1)
  if [[ $hash != "$last_hash" ]]; then last_hash=$hash; last_change=$now; fi
  if (( now - last_change >= idle_limit )); then
    echo "IDLE $((now - last_change))"; context; exit 0
  fi
  if (( now - start >= heartbeat )); then
    echo "HEARTBEAT $((now - start))"; context; exit 0
  fi
  sleep 5
done
