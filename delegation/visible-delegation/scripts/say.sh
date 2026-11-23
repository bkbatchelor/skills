#!/usr/bin/env bash
# Send the delegate a message through Orca mail.
#
# Usage: say.sh <name> <message...>          send a message
#        say.sh <name> --file <path>          send a file's contents
#        say.sh <name> --subject <s> ...      set the subject (default "From your supervisor")
#
# A working delegate gets the message when its current turn ends; a finished one gets
# it as a follow-up task and reports again. Mail never answers an approval dialog and
# never interrupts a turn: only a person can do that, in the delegate's tab.
# To answer a question the delegate asked, use the reply command in Orca's wake message
# instead (orca orchestration reply --id <message_id> --body "...").
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

name=${1:?usage: say.sh <name> [--subject <s>] <message...> | --file <path>}; shift
require_tools
load_meta "$name"
[[ -n ${VD_DISPATCH:-} ]] || die "'$name' has no task yet; finish launch.sh first"

subject="From your supervisor"
if [[ ${1:-} == --subject ]]; then subject=${2:?no subject}; shift 2; fi

body=$RUNDIR/message-$(date +%Y%m%d-%H%M%S).md
case ${1:-} in
  --file) [[ -f ${2:-} ]] || die "file not found: ${2:-}"; cp "$2" "$body" ;;
  *) [[ -n "$*" ]] || die "empty message"; printf '%s\n' "$*" > "$body" ;;
esac

# Orca's rule: if send fails, do only what the CLI prints; never retry on your own.
"$ORCA" orchestration send --to "dispatch:$VD_DISPATCH" --subject "$subject" --body-file "$body" --json 2>&1 \
  | jq -c '{ok, result: (.result | if type == "object" then {messageId: (.messageId // .id), delivery: (.delivery // .outcome)} else . end), warnings: (.warnings // .result.warnings), error}'
