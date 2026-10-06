#!/usr/bin/env bash
# Type a message into a delegate session and submit it.
#
# Usage: say.sh <session> <message...>
#        say.sh <session> --key <tmux-key>...   (raw keys, e.g. --key Escape, --key 1)
#
# Agent TUIs treat fast multi-char input as a paste, and an Enter arriving in the same
# burst can be swallowed into the paste. So the text is sent literally, then Enter
# after a short pause.
set -euo pipefail
session=${1:?usage: say.sh <session> <message...> | --key <key>...}; shift
target="=$session:"
tmux has-session -t "=$session" 2>/dev/null || { echo "no such session: $session" >&2; exit 1; }

if [[ ${1:-} == --key ]]; then
  shift
  for k in "$@"; do tmux send-keys -t "$target" "$k"; sleep 0.3; done
  exit 0
fi

msg="$*"
[[ -n $msg ]] || { echo "empty message" >&2; exit 1; }
tmux send-keys -t "$target" -l "$msg"
sleep 0.6
tmux send-keys -t "$target" Enter
