# page-testing-memory

Global process for QA of any web page or UI. Page-specific knowledge never lives here; it goes into the repo's testing runbook.

## Install

Symlink or copy this folder into your agent's skills directory:

```bash
ln -s "$PWD/testing/page-testing-memory" ~/.claude/skills/page-testing-memory
```

## Usage

Ask the agent to QA, verify, or screenshot a page. The skill triggers on its own. It works with `testing-runbook-creator`, which decides where the runbook lives and how entries are formatted.

## What lives where

- **This skill:** the QA process, states and inputs to try, breakpoint defaults, pass/fail judgement.
- **Repo runbook:** routes, selectors, test accounts (placeholders), seed data, cleanup, quirks.
