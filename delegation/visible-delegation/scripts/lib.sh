# Shared helpers for the visible-delegation scripts. Source it; don't run it.

VD_ROOT=${VISIBLE_DELEGATION_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/visible-delegation}
# The Orca CLI. Inside Orca, ORCA_CLI_COMMAND names the exact executable for this host.
ORCA=${ORCA_CLI_COMMAND:-orca}

die() { echo "$*" >&2; exit 1; }

require_tools() {
  command -v "$ORCA" >/dev/null || die "the Orca CLI ('$ORCA') is not on PATH. See 'Requirements' in SKILL.md."
  command -v jq >/dev/null || die "jq is not installed (needed to parse Orca's JSON output)."
}

# Load a delegate's run metadata.
load_meta() {
  local name=$1
  RUNDIR=$VD_ROOT/$name
  [[ -f $RUNDIR/meta.env ]] || die "no run metadata for '$name' (expected $RUNDIR/meta.env)"
  # shellcheck disable=SC1091
  source "$RUNDIR/meta.env"
  refresh_dispatch
}

# A follow-up message to a finished delegate starts a new Dispatch in the same terminal,
# so the one launch.sh recorded can go stale. Point VD_DISPATCH at the delegate's open
# Dispatch if it has one, else at the newest one Orca lists for its terminal.
refresh_dispatch() {
  [[ -n ${VD_RUN:-} && -n ${VD_TERMINAL:-} ]] || return 0
  local d
  d=$("$ORCA" orchestration worker-list --environment local --run "$VD_RUN" --json 2>/dev/null \
    | jq -r --arg t "$VD_TERMINAL" '[.result.workers[]? | select(.terminal == $t)]
        | ((map(select(.state != "succeeded" and .state != "failed")) + .)[0].dispatchId) // empty' 2>/dev/null)
  [[ -n $d ]] && VD_DISPATCH=$d
  return 0
}

# The delegate's Orca worker state (ready, running, succeeded, failed...), or "none"
# when no task has been assigned to it yet.
worker_state() {
  [[ -n ${VD_DISPATCH:-} ]] || { echo none; return; }
  "$ORCA" orchestration worker-show --environment local --dispatch "$VD_DISPATCH" --json 2>/dev/null \
    | jq -r '.result.state // "unknown"' 2>/dev/null || echo unknown
}

# Read the delegate's rendered screen as JSON (empty when the terminal is gone).
screen_json() {
  "$ORCA" terminal read --terminal "$VD_TERMINAL" --screen --json 2>/dev/null || true
}

terminal_status() {  # "running" while the delegate's terminal is open, otherwise "gone"
  # Orca reports "exited" for a terminal whose process ended; treat anything else as gone.
  local s; s=$(screen_json | jq -r '.result.terminal.status // empty' 2>/dev/null)
  [[ $s == running ]] && echo running || echo gone
}

screen() {  # the delegate's current screen, blank lines dropped
  # Agent TUIs repaint, so a plain read comes back as stacked fragments; --screen is the
  # rendered frame. The full record is the agent's own transcript.
  screen_json | jq -r '.result.terminal.tail[]?' 2>/dev/null | sed '/^[[:space:]]*$/d'
}

transcript() {  # path of a Claude delegate's session transcript, if it exists yet
  [[ -n ${VD_CLAUDE_SESSION_ID:-} ]] || return 0
  ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$VD_CLAUDE_SESSION_ID".jsonl 2>/dev/null | head -1
}

# Write a meta.env line, quoted for `source`.
meta_set() { printf '%s=%q\n' "$1" "$2" >> "$RUNDIR/meta.env"; }
