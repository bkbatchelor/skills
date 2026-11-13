# testing-runbook-creator

Keeps a repo-local testing runbook so future sessions never rediscover how to test something. Whenever Claude tests, verifies, smoke-tests, QA's, or debugs anything in a repo, it reads the runbook first, records discoveries as it goes, and fixes the runbook when reality differs.

## Tech Stack

| Category | Technology |
|----------|------------|
| Format | Markdown skill (`SKILL.md`) |

## Quick Start

```bash
git clone git@github.com:bkbatchelor/skills.git
cd skills
ln -s "$PWD/testing/testing-runbook-creator" ~/.claude/skills/testing-runbook-creator
```

It triggers on any testing activity; you do not need to mention a runbook.

## Runbook location

An existing testing doc wins; otherwise `docs/testing-runbook.md`; otherwise `TESTING-RUNBOOK.md` at the repo root. Created at the first discovery.

## Entry fields

Scope, Last verified (date and commit), Prerequisites / seed, Steps, Safe actions, Destructive actions, Verification (exact command plus expected output), Cleanup, Known defects, Gotchas.

## Rules

Read first, update on mismatch, record as you go, never store secrets, never run destructive steps without approval, never commit on its own.
