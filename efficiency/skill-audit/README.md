# skill-audit

A read-only audit of agent skills and harness configuration. It checks how each harness loads the skills you pick, validates them, finds duplicates and repeated content, estimates context cost, audits your Claude config files, and writes everything into one HTML report. It never edits a skill or a config file.

The harness is the program that runs Claude and loads its skills.

## Quick Start

Run these in a terminal. They download (clone) the repo with git, then create a symlink. A symlink is a shortcut that makes the skill appear where your harness loads skills.

```bash
git clone https://github.com/bkbatchelor/skills.git
cd skills
ln -s "$PWD/efficiency/skill-audit" ~/.claude/skills/skill-audit
```

Then ask Claude:

```text
/skill-audit generate-readme                          # one skill
/skill-audit generate-readme commit-staged-changes    # several skills
/skill-audit --all                                    # every skill in the repo
```

Names and paths both work. If you give no target, Claude asks which mode you want. It never starts a full run by itself.

## What it checks

| Check | Needs a key | Source |
|-------|-------------|--------|
| Loading per harness (Claude Code, Copilot CLI) | No | `scripts/tier-1-harness-check.sh` |
| Structure, quality score, security | No | `scripts/tier-1-validation-check.sh` |
| Broken references and missing MCP servers | No | `scripts/local-checks.py` |
| Duplicate skills | Yes | `scripts/tier-2-similarity-check.sh` |
| Estimated token cost of each skill | No | `scripts/local-checks.py` |
| Repeated content inside a skill | Yes | `scripts/tier-2-context-optimization-check.sh` |
| `settings.json` drift, permissions, hooks, MCP servers, `CLAUDE.md` | No | Local code, run once per run |

The checks marked "Yes" need an OpenRouter key in `ORCA_OPENROUTER_API_KEY` or `OPENROUTER_API_KEY`. Without a key, those sections show "not run" and the rest continue.

## Output

One self-contained HTML file at `../skills-reports/audit-<date>.html`, next to the repo. It holds a scorecard, a per-skill table, config findings, recommendations sorted by severity, and the run log. Script reports and logs go to `../skills-reports/`.

## Scripts

The four `scripts/tier-*` scripts and `scripts/local-checks.py` also work on their own. Run them from the repo root:

```bash
efficiency/skill-audit/scripts/tier-1-harness-check.sh --all --strict
efficiency/skill-audit/scripts/tier-1-validation-check.sh generate-readme
efficiency/skill-audit/scripts/tier-2-context-optimization-check.sh --all
efficiency/skill-audit/scripts/tier-2-similarity-check.sh
python3 -I efficiency/skill-audit/scripts/local-checks.py --all
```

## Requirements

- `skillevaluator` on your `PATH`
- `python3` (standard library only) for `scripts/local-checks.py`
- The `html-artifacts` skill, to build the report
- An OpenRouter key for the two Tier 2 checks (optional)
