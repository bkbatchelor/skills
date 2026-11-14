# testing-runbook-creator

Keeps a runbook in each repo, so future sessions do not have to work out how to test something again. A runbook is a document with the steps for testing that repo.

Whenever Claude tests, verifies, smoke-tests (runs a quick check that the basics work), runs QA, or debugs something in a repo, it does three things. It reads the runbook first. It records what it learns as it goes. It fixes the runbook when the steps no longer match what happens.

## Tech Stack

| Category | Technology |
|----------|------------|
| Format | Markdown skill (`SKILL.md`) |

## Quick Start

Run these in a terminal. The last line creates a symlink, a shortcut that makes the skill appear in `~/.claude/skills/` without copying it.

```bash
git clone git@github.com:bkbatchelor/skills.git
cd skills
ln -s "$PWD/testing/testing-runbook-creator" ~/.claude/skills/testing-runbook-creator
```

It triggers on any testing activity. You do not need to mention a runbook.

## Runbook location

Claude uses the first of these that applies:

1. An existing testing document.
2. `docs/testing-runbook.md`.
3. `TESTING-RUNBOOK.md` in the repo's root folder, the top folder of the repo.

If none exists, Claude creates the runbook when it makes its first discovery.

## Entry fields

Each entry in the runbook has these fields:

- **Scope:** what the entry covers.
- **Last verified:** the date and the commit when the steps last worked. A commit is a saved change in git.
- **Prerequisites / seed:** what must be set up first, including any seed data.
- **Steps:** what to do.
- **Safe actions:** steps that do not change or delete data.
- **Destructive actions:** steps that delete or change data.
- **Verification:** the exact command to run, and the output it should show.
- **Cleanup:** how to undo the changes that the test made.
- **Known defects:** bugs that are already known.
- **Gotchas:** surprises that catch people out.

## Rules

- Read the runbook first.
- Update the runbook when reality differs from it.
- Record discoveries as you go.
- Never store secrets, such as passwords, keys or tokens.
- Never run a destructive step without approval.
- Never make a commit on its own.
