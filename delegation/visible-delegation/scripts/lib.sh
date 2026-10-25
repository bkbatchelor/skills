# Shared helpers for the visible-delegation scripts. Source it; don't run it.

VD_ROOT=${VISIBLE_DELEGATION_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/visible-delegation}
# Named herdr session used when the supervisor itself is not running inside herdr.
VD_HERDR_SESSION=${VISIBLE_DELEGATION_SESSION:-delegates}

die() { echo "$*" >&2; exit 1; }

require_tools() {
  command -v herdr >/dev/null || die "herdr is not installed. See the 'Install herdr' section of SKILL.md."
  command -v jq >/dev/null || die "jq is not installed (needed to parse herdr's JSON output)."
}

# Load a delegate's run metadata and point herdr at the right session.
load_meta() {
  local name=$1
  RUNDIR=$VD_ROOT/$name
  [[ -f $RUNDIR/meta.env ]] || die "no run metadata for '$name' (expected $RUNDIR/meta.env)"
  # shellcheck disable=SC1091
  source "$RUNDIR/meta.env"
  if [[ $VD_MODE == session ]]; then export HERDR_SESSION=$VD_SESSION; fi
}

agent_status() {  # prints idle|working|blocked|done|unknown, or "gone"
  herdr agent get "$1" 2>/dev/null | jq -r '.result.agent.agent_status // "gone"' 2>/dev/null || echo gone
}

screen() {  # the agent's current screen, blank lines dropped
  # Agent TUIs like Claude Code draw on the alternate screen, which never reaches herdr's
  # scrollback, so the "recent" sources come back empty. The visible screen is what is
  # reliably there; the full record is the agent's own transcript.
  herdr agent read "$1" --source visible 2>/dev/null | sed '/^[[:space:]]*$/d'
}

context() {  # what the supervisor needs to see alongside any event
  local name=$1
  echo "--- screen (last 40 lines) ---"
  screen "$name" | tail -40
  if git -C "$VD_WORKDIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "--- git status --short ($VD_WORKDIR) ---"
    git -C "$VD_WORKDIR" status --short | head -30
  fi
}
