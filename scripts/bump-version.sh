#!/usr/bin/env bash
# Semantic versioning for skills (metadata.version in each SKILL.md).
#
# Usage:
#   scripts/bump-version.sh <skill> <major|minor|patch>   bump a skill by hand
#   scripts/bump-version.sh --commit-msg <file>           commit-msg hook entry
#   scripts/bump-version.sh --post-commit                 post-commit hook entry
#
# The hooks never increment the current version. They set each skill the
# commit touches to a target version:
#
#   target = (version at the merge-base with the base branch)
#            bumped once by the highest level among the branch's commits
#            touching that skill
#
# so a skill is bumped once per PR and amends or rebases converge on the
# same result. The base branch is origin/main unless overridden with
# `git config skills.versionBase <ref>`.

set -euo pipefail

say() { printf 'bump-version: %s\n' "$*" >&2; }
die() { say "$*"; exit 1; }

repo_root() { git rev-parse --show-toplevel; }
git_path() { git rev-parse --git-path "$1"; }
pending_file() { git_path skill-version-pending; }

# --- Levels ------------------------------------------------------------------

# none=0 patch=1 minor=2 major=3
level_num() {
  case "$1" in
    major) echo 3 ;; minor) echo 2 ;; patch) echo 1 ;; *) echo 0 ;;
  esac
}

level_name() {
  case "$1" in
    3) echo major ;; 2) echo minor ;; 1) echo patch ;; *) echo none ;;
  esac
}

# Strip comments and anything below the scissors line from a message on stdin.
clean_message() {
  sed -e '/^# -\{24\} >8 -\{24\}$/,$d' -e '/^#/d'
}

# Print the bump level number for a commit message on stdin.
message_level() {
  local msg subject type
  msg=$(clean_message)
  subject=$(printf '%s\n' "$msg" | sed -n '/[^[:space:]]/{p;q;}')
  if [[ $subject =~ ^[a-z]+(\([^\)]*\))?!: ]] ||
     printf '%s\n' "$msg" | grep -Eq '^BREAKING[ -]CHANGE: '; then
    echo 3; return
  fi
  type=${subject%%[(:]*}
  case "$type" in
    feat) echo 2 ;;
    fix|docs|style|refactor|perf|revert) echo 1 ;;
    *) echo 0 ;;
  esac
}

# --- Versions ----------------------------------------------------------------

# Print metadata.version from SKILL.md content on stdin (empty if absent).
read_version() {
  awk '
    NR == 1 && $0 == "---" { fm = 1; next }
    fm && $0 == "---" { exit }
    fm && /^metadata:[[:space:]]*$/ { md = 1; next }
    fm && md && /^[^[:space:]]/ { md = 0 }
    fm && md && /^[[:space:]]+version:/ {
      sub(/^[[:space:]]+version:[[:space:]]*/, "")
      gsub(/["'\''[:space:]]/, "")
      print; exit
    }
  '
}

# Rewrite SKILL.md content on stdin with metadata.version set to $1.
write_version() {
  awk -v ver="$1" '
    function emit_version() { print "  version: " ver; done = 1 }
    NR == 1 && $0 == "---" { fm = 1; print; next }
    fm && $0 == "---" {
      if (md && !done) emit_version()
      if (!done) { print "metadata:"; emit_version() }
      fm = 0; md = 0; print; next
    }
    fm && /^metadata:[[:space:]]*$/ { md = 1; print; next }
    fm && md && /^[^[:space:]]/ { if (!done) emit_version(); md = 0 }
    fm && md && /^[[:space:]]+version:/ { if (!done) emit_version(); next }
    { print }
  '
}

valid_semver() { [[ $1 =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; }

# bump_semver <version> <level-number>
bump_semver() {
  local major minor patch
  IFS=. read -r major minor patch <<<"$1"
  case "$2" in
    3) echo "$((major + 1)).0.0" ;;
    2) echo "$major.$((minor + 1)).0" ;;
    1) echo "$major.$minor.$((patch + 1))" ;;
    *) echo "$1" ;;
  esac
}

# semver_gt <a> <b>: true if a > b
semver_gt() {
  local a1 a2 a3 b1 b2 b3
  IFS=. read -r a1 a2 a3 <<<"$1"
  IFS=. read -r b1 b2 b3 <<<"$2"
  ((a1 != b1)) && { ((a1 > b1)); return; }
  ((a2 != b2)) && { ((a2 > b2)); return; }
  ((a3 > b3))
}

# --- Base branch -------------------------------------------------------------

base_ref() {
  local ref
  ref=$(git config --get skills.versionBase || echo origin/main)
  if git rev-parse -q --verify "$ref^{commit}" >/dev/null; then
    echo "$ref"
  elif git rev-parse -q --verify "${ref#origin/}^{commit}" >/dev/null; then
    echo "${ref#origin/}"
  fi
}

on_base_branch() {
  local branch base
  branch=$(git symbolic-ref -q --short HEAD || true)
  base=$(base_ref)
  [[ -n $branch && $branch == "${base#origin/}" ]]
}

in_sequence_operation() {
  local p
  for p in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
    [[ -e $(git_path "$p") ]] && return 0
  done
  return 1
}

# --- Target version ----------------------------------------------------------

# Top-level skill directories (containing SKILL.md at HEAD) touched by HEAD.
skills_in_head() {
  git diff-tree --root --no-commit-id --name-only -r HEAD |
    awk -F/ 'NF > 1 { print $1 }' | sort -u |
    while read -r dir; do
      git cat-file -e "HEAD:$dir/SKILL.md" 2>/dev/null && echo "$dir"
    done
}

# target_version <skill> <merge-base>
target_version() {
  local skill=$1 mb=$2 base_ver level=0 sha l
  base_ver=$(git show "$mb:$skill/SKILL.md" 2>/dev/null | read_version || true)
  if ! valid_semver "$base_ver"; then
    # New or not-yet-versioned skill: its first version is 1.0.0.
    echo 1.0.0; return
  fi
  for sha in $(git rev-list --no-merges "$mb..HEAD" -- "$skill/"); do
    l=$(git log -1 --format=%B "$sha" | message_level)
    ((l > level)) && level=$l
  done
  bump_semver "$base_ver" "$level"
}

# --- Commands ----------------------------------------------------------------

cmd_manual() {
  local skill=${1%/} level file cur new
  level=$(level_num "${2:-}")
  ((level > 0)) || die "usage: $0 <skill> <major|minor|patch>"
  file="$(repo_root)/$skill/SKILL.md"
  [[ -f $file ]] || die "no such skill: $skill"
  cur=$(read_version <"$file")
  if valid_semver "$cur"; then
    new=$(bump_semver "$cur" "$level")
  else
    new=1.0.0
  fi
  write_version "$new" <"$file" >"$file.tmp" && mv "$file.tmp" "$file"
  say "$skill: ${cur:-unversioned} -> $new"
}

cmd_commit_msg() {
  local msgfile=$1 subject pending
  pending=$(pending_file)
  rm -f "$pending"
  in_sequence_operation && exit 0

  subject=$(clean_message <"$msgfile" | sed -n '/[^[:space:]]/{p;q;}')
  case "$subject" in
    "Merge "*|"Revert \""*|"fixup! "*|"squash! "*|"amend! "*) exit 0 ;;
  esac
  local types='feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert'
  if ! [[ $subject =~ ^($types)(\([a-z0-9._/-]+\))?!?:\ [A-Z] ]] ||
     [[ $subject == *. ]] || ((${#subject} > 50)); then
    say "commit message does not follow the commit template:"
    say "  $subject"
    say "expected '<type>(<scope>): <Summary>', type one of: ${types//|/, }"
    say "summary capitalized, no trailing period, subject at most 50 characters"
    exit 1
  fi

  if on_base_branch; then
    say "warning: committing directly on $(git symbolic-ref --short HEAD); skipping version bump"
    exit 0
  fi

  # Record the commit's parent so post-commit acts only on this commit.
  git rev-parse -q --verify HEAD >"$pending" || : >"$pending"
}

cmd_post_commit() {
  local pending expected parent root mb skill file cur target
  local -a changed=()
  pending=$(pending_file)
  [[ -f $pending ]] || exit 0
  expected=$(cat "$pending")
  rm -f "$pending"

  in_sequence_operation && exit 0
  # Merge commits are never bumped.
  git rev-parse -q --verify HEAD^2 >/dev/null && exit 0
  # Act only on the commit (or amend) that commit-msg saw.
  parent=$(git rev-parse -q --verify HEAD^ || true)
  if [[ $parent != "$expected" &&
        $parent != "$(git rev-parse -q --verify "$expected^" 2>/dev/null || true)" ]]; then
    exit 0
  fi

  local base
  base=$(base_ref)
  if [[ -z $base ]]; then
    say "warning: base branch not found; set it with 'git config skills.versionBase <ref>'"
    exit 0
  fi
  mb=$(git merge-base HEAD "$base" || true)
  [[ -n $mb ]] || { say "warning: no merge-base with $base; skipping"; exit 0; }

  root=$(repo_root)
  tmp_index=$(mktemp)
  trap 'rm -f "$tmp_index"' EXIT
  GIT_INDEX_FILE=$tmp_index git read-tree HEAD

  while read -r skill; do
    [[ -n $skill ]] || continue
    file="$skill/SKILL.md"
    cur=$(git show "HEAD:$file" | read_version)
    target=$(target_version "$skill" "$mb")
    if [[ $cur == "$target" ]]; then
      continue
    elif valid_semver "$cur" && semver_gt "$cur" "$target"; then
      say "$skill: keeping $cur (above computed target $target)"
      continue
    fi

    local old_blob new_blob
    old_blob=$(git rev-parse "HEAD:$file")
    new_blob=$(git show "HEAD:$file" | write_version "$target" | git hash-object -w --stdin)
    GIT_INDEX_FILE=$tmp_index git update-index --cacheinfo "100644,$new_blob,$file"

    # Keep the real index and working tree in step without disturbing
    # unrelated staged or unstaged edits.
    if [[ $(git ls-files -s -- "$file" | awk '{print $2}') == "$old_blob" ]]; then
      git update-index --cacheinfo "100644,$new_blob,$file"
    fi
    if [[ -f $root/$file ]]; then
      write_version "$target" <"$root/$file" >"$root/$file.tmp" &&
        mv "$root/$file.tmp" "$root/$file"
    fi
    changed+=("$skill ${cur:-unversioned} -> $target")
  done < <(skills_in_head)

  ((${#changed[@]})) || exit 0
  GIT_INDEX_FILE=$tmp_index git commit --amend --no-edit --no-verify --quiet --allow-empty
  local c
  for c in "${changed[@]}"; do say "$c"; done
}

case "${1:-}" in
  --commit-msg) unset GIT_INDEX_FILE; cmd_commit_msg "${2:?message file required}" ;;
  --post-commit) unset GIT_INDEX_FILE; cmd_post_commit ;;
  -h|--help|"") sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) cmd_manual "$@" ;;
esac
