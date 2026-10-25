#!/usr/bin/env bash
# Send input to a delegate.
#
# Usage: say.sh <name> <message...>      submit a message (refused while a dialog is open)
#        say.sh <name> --file <path>      submit a file's contents (e.g. the goal prompt)
#        say.sh <name> --key <key>...     press keys, e.g. --key 1 · --key esc · --key down enter
#
# Messages go through `herdr agent prompt`, which handles bracketed paste and refuses to
# type into an open approval dialog. After keys, waits briefly for herdr to see the
# dialog close, since its state lags a second or two behind the screen.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: say.sh <name> <message...> | --file <path> | --key <key>...}; shift
require_tools
load_meta "$name"
[[ $(agent_status "$name") != gone ]] || die "agent '$name' is not running"

case ${1:-} in
  --key)
    shift; [[ $# -gt 0 ]] || die "no keys given"
    before=$(agent_status "$name")
    for k in "$@"; do herdr agent send-keys "$name" "$k" >/dev/null; sleep 0.3; done
    if [[ $before == blocked ]]; then
      for _ in $(seq 1 20); do [[ $(agent_status "$name") != blocked ]] && break; sleep 0.25; done
    fi
    echo "status: $(agent_status "$name")"
    ;;
  --file)
    [[ -f ${2:-} ]] || die "file not found: ${2:-}"
    herdr agent prompt "$name" "$(cat "$2")" 2>&1 | jq -c '{status: (.result.agent.agent_status // .error.code)}'
    ;;
  *)
    msg="$*"; [[ -n $msg ]] || die "empty message"
    herdr agent prompt "$name" "$msg" 2>&1 | jq -c '{status: (.result.agent.agent_status // .error.code)}'
    ;;
esac
