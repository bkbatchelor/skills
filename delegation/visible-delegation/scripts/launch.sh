#!/usr/bin/env bash
# Start a delegate agent in a herdr pane that the user can watch.
#
# Usage: launch.sh <name> <workdir> <goal-file> [claude|opencode] [-- extra agent args...]
#
#   <name>  herdr agent name, e.g. deleg-readme  ([a-z][a-z0-9_-]{0,31})
#
# Inside herdr (HERDR_ENV=1) the delegate gets a sibling pane next to the supervisor.
# Outside herdr it gets its own workspace in a dedicated named session ("delegates" by
# default, VISIBLE_DELEGATION_SESSION to override), never the user's focused session.
#
# Exit codes: 0 started and prompted · 4 agent blocked at startup (prompt NOT sent yet)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[[ $# -ge 3 ]] || usage
name=$1 workdir=$2 goal=$3; shift 3
kind=claude
if [[ $# -gt 0 && $1 != -- ]]; then kind=$1; shift; fi
[[ ${1:-} == -- ]] && shift
extra=("$@")

require_tools
[[ $name =~ ^[a-z][a-z0-9_-]{0,31}$ ]] || die "name must match [a-z][a-z0-9_-]{0,31}"
[[ $kind == claude || $kind == opencode ]] || die "unsupported agent '$kind' (claude or opencode)"
command -v "$kind" >/dev/null || die "agent CLI '$kind' not found on PATH"
[[ -d $workdir ]] || die "workdir not found: $workdir"
[[ -f $goal ]] || die "goal file not found: $goal"
workdir=$(cd "$workdir" && pwd)

if [[ ${HERDR_ENV:-} == 1 ]]; then mode=pane; session=""; else mode=session; session=$VD_HERDR_SESSION; fi

# --- herdr session (outside-herdr mode only) -----------------------------------------
if [[ $mode == session ]]; then
  if ! herdr session list 2>/dev/null | awk -v s="$session" '$1==s && $2=="running"{f=1} END{exit !f}'; then
    # Panes inherit the server's environment. The supervisor's own harness exports
    # CLAUDE* variables (session ids, messaging sockets) that would make the delegate
    # think it is a nested child session, so start the server without them.
    # CLAUDE_CONFIG_DIR is user configuration and stays.
    unset_args=()
    while IFS= read -r v; do
      [[ $v == CLAUDE_CONFIG_DIR ]] || unset_args+=(-u "$v")
    done < <(env | grep -oE '^CLAUDE[A-Za-z0-9_]*' || true)
    (setsid env "${unset_args[@]}" herdr --session "$session" server >/dev/null 2>&1 &)
    for _ in $(seq 1 40); do
      herdr session list 2>/dev/null | awk -v s="$session" '$1==s && $2=="running"{f=1} END{exit !f}' && break
      sleep 0.25
    done
    herdr session list 2>/dev/null | awk -v s="$session" '$1==s && $2=="running"{f=1} END{exit !f}' \
      || die "could not start herdr session '$session'"
    mkdir -p "$VD_ROOT"; touch "$VD_ROOT/.owns-session-$session"
  fi
  export HERDR_SESSION=$session
fi

[[ $(agent_status "$name") == gone ]] || die "a live agent named '$name' already exists; pick another name or clean it up"

rundir=$VD_ROOT/$name
if [[ -e $rundir ]]; then mv "$rundir" "$rundir.$(date +%Y%m%d-%H%M%S)"; fi
mkdir -p "$rundir"
cp "$goal" "$rundir/goal.md"
{ cat "$goal"; sed "s/{{NAME}}/$name/g" "$here/../references/delegate-addendum.md"; } > "$rundir/prompt.md"

# --- pane ----------------------------------------------------------------------------
if [[ $mode == session ]]; then
  out=$(herdr workspace create --cwd "$workdir" --label "$name" --no-focus)
  pane=$(jq -r '.result.root_pane.pane_id' <<<"$out")
  workspace=$(jq -r '.result.workspace.workspace_id' <<<"$out")
else
  out=$(herdr pane split --current --direction "${VD_SPLIT:-right}" --cwd "$workdir" --no-focus)
  pane=$(jq -r '.result.pane.pane_id' <<<"$out")
  workspace=""
fi
[[ -n $pane && $pane != null ]] || die "herdr did not return a pane: $out"

sid=""; [[ $kind == claude ]] && sid=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen)
{
  printf 'VD_NAME=%q\nVD_MODE=%q\nVD_SESSION=%q\nVD_WORKSPACE=%q\nVD_PANE=%q\n' "$name" "$mode" "$session" "$workspace" "$pane"
  printf 'VD_KIND=%q\nVD_WORKDIR=%q\nVD_CLAUDE_SESSION_ID=%q\n' "$kind" "$workdir" "$sid"
} > "$rundir/meta.env"

# `agent start` needs the pane's shell at its interactive prompt.
for _ in $(seq 1 40); do
  [[ -n $(herdr pane read "$pane" --source visible 2>/dev/null | tr -d '[:space:]') ]] && break
  sleep 0.25
done

# --- agent ---------------------------------------------------------------------------
agent_args=()
if [[ $kind == claude ]]; then
  # acceptEdits: file edits flow; most shell commands stop at an approval prompt that
  # herdr reports as "blocked". acceptEdits still auto-allows some file commands (rm,
  # mkdir...) inside the workdir, so the riskiest ones are denied outright.
  has_mode=0
  for a in "${extra[@]}"; do [[ $a == --permission-mode* || $a == --dangerously-skip-permissions ]] && has_mode=1; done
  [[ $has_mode == 0 ]] && agent_args+=(--permission-mode acceptEdits)
  agent_args+=(-n "$name" --session-id "$sid" --add-dir "$rundir")
  agent_args+=(--disallowedTools
    "Bash(git push:*)" "Bash(git reset --hard:*)" "Bash(git clean:*)" "Bash(git branch -D:*)"
    "Bash(rm -r:*)" "Bash(rm -rf:*)" "Bash(rm -fr:*)" "Bash(rm -Rf:*)" "Bash(sudo:*)"
    "Bash(npm publish:*)" "Bash(cargo publish:*)")
fi
agent_args+=("${extra[@]}")

start=$(herdr agent start "$name" --kind "$kind" --pane "$pane" --timeout 60000 -- "${agent_args[@]}" 2>&1 || true)
err=$(jq -r '.error.code // empty' <<<"$start" 2>/dev/null || true)

watch_hint() {
  if [[ $mode == session ]]; then
    echo "Watch    : herdr session attach $session    (in another terminal; open the '$name' workspace)"
  else
    echo "Watch    : the new pane beside this one, in the current herdr tab"
  fi
}

if [[ $err == agent_not_ready ]]; then
  cat <<EOF
BLOCKED_AT_STARTUP: '$name' is waiting on a dialog before it can take the goal prompt.
  run dir : $rundir
$(watch_hint)
Inspect the screen, answer the dialog (say.sh $name --key ...), then send the goal:
  say.sh $name --file $rundir/prompt.md
--- screen ---
$(screen "$name" 40)
EOF
  exit 4
elif [[ -n $err ]]; then
  die "herdr agent start failed: $start"
fi

sent=$(herdr agent prompt "$name" "$(cat "$rundir/prompt.md")" 2>&1 || true)
perr=$(jq -r '.error.code // empty' <<<"$sent" 2>/dev/null || true)
[[ -z $perr ]] || die "agent started but the goal prompt was not accepted: $sent"

cat <<EOF
Delegate started.
  name    : $name ($kind)
  workdir : $workdir
  herdr   : ${session:+session $session, }${workspace:+workspace $workspace, }pane $pane
  run dir : $rundir
$(watch_hint)
EOF
