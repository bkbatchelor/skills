---
name: testing-runbook-creator
description: Keeps a repo-local testing runbook so future sessions never rediscover how to test something. Read it before, and update it during, ANY testing, verification, smoke-testing, QA, or debugging activity in a repo - running a test suite, checking a UI page or API endpoint, reproducing a bug, validating a change, trying a CLI or script - whether or not the user mentions a runbook. Records per-workflow steps, safe vs destructive actions, seed/setup, cleanup, and exact verification commands with expected output, and fixes the runbook the moment reality differs. Skip only for pure code reading or editing where nothing is run or observed.
metadata:
  version: 1.1.0
---

# Testing Runbook Creator

Every time you test, verify, QA, or debug something in a repo, you learn things: the right command, the needed seed data, the step that breaks, what "passing" looks like. This skill makes that knowledge persist in the repo so the next session starts where this one ended.

## When this applies

Any activity that runs or observes the software: running tests, lint, typecheck or build checks, smoke-testing a page, endpoint, CLI or script, reproducing or debugging a bug, verifying a change works. The user does not need to say "runbook".

## Runbook location

Pick once per repo, in this order:

1. An existing testing doc (`TESTING.md`, `docs/testing.md`, `docs/qa.md`, `docs/testing-runbook.md`...). Use it; never create a second one. Follow its conventions where they differ from the format below.
2. Otherwise `docs/testing-runbook.md`.
3. If the repo has no `docs/` folder, `TESTING-RUNBOOK.md` at the repo root.

Create the file lazily, at your first discovery, not before.

## The four rules

### 1. Read first
Before running or testing anything, open the runbook and look for the feature or workflow (use the index at the top, or search). If an entry exists, follow its recipe instead of improvising. If the file does not exist or has no entry, carry on and apply rule 3.

### 2. Update when reality differs
If a step fails, a command's output differs from the expected output, a prerequisite is missing, or the entry is stale, fix the entry in the same session, at the moment you find out. Correct the text, then bump `Last verified`. Never leave a known-wrong recipe in place, and never work around it silently.

### 3. Record as you go
Write each discovery into the runbook as soon as you make it: right after a command works, a gotcha bites, or you learn what is safe. Do not batch it for the end of the session, because sessions get cut off and memory of exact output is lossy. Use small edits. Paste real command output, trimmed to the lines that prove success.

### 4. Record only what is reusable
Routine runs (`npm test`, lint, typecheck) go in a single "Test suite & checks" entry, written once and amended only on surprises. Do not log every run. Do not record one-off debugging narratives; record the durable lesson.

## Entry format

Add the entry title to the index at the top of the file, then add a `##` section:

```markdown
## <Feature / page / workflow>

- **Scope:** what this covers and what it does not
- **Last verified:** YYYY-MM-DD at commit <short sha>
- **Prerequisites / seed:** services to start, env var names, seed data, accounts (placeholders only)
- **Steps:**
  1. ...
- **Safe actions:** read-only or reversible things you can do freely
- **Destructive actions:** what deletes, mutates shared state, costs money, or hits production; never run without user approval
- **Verification:**
  ```bash
  <exact command>
  ```
  Expected:
  ```
  <trimmed real output>
  ```
- **Cleanup:** how to restore state (stop services, delete test data, reset DB)
- **Known defects:** open bugs the testing exposed, each with the symptom, the cause if known, and evidence (screenshot path or command output). Remove an item when it is fixed, or mark it fixed with the date
- **Gotchas:** non-obvious failures and their fixes
```

Omit a field only when it truly has no content; write "none" for Prerequisites, Cleanup and Known defects rather than dropping them, so readers know it was considered.

## Hard rules

- **No secrets.** The runbook is committed. Never write tokens, passwords, keys, or real user data. Name the env var or secret-store path and use placeholder or seed accounts.
- **Destructive means ask.** Document destructive steps and flag them, but do not run one unless the user has approved it in this session.
- **Do not commit.** Edit the runbook in the working tree only. In your final message, say the runbook changed and what you added or fixed. Branch and commit rules belong to the user's workflow.
- **Verify before you write.** Record commands you actually ran and output you actually saw, never what you expect.
- **Stay specific.** Exact commands, exact paths, exact expected output. "Run the tests" is not a recipe.
