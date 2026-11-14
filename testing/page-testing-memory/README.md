# page-testing-memory

Sets out the general process for QA (quality assurance, which means checking that a page works before users see it) on any web page or UI. A UI is the part of an app that people see and use.

Facts about one page never go in this skill. They go in the repo's testing runbook, a document that records how to test that repo.

## Install

Symlink this folder into your agent's skills folder. A symlink is a shortcut that makes the skill appear there without copying it. Run this in a terminal from the root of this repo:

```bash
ln -s "$PWD/testing/page-testing-memory" ~/.claude/skills/page-testing-memory
```

You can also copy the folder there instead of making a symlink.

## Usage

Ask Claude to QA, verify, or screenshot a page. The skill starts on its own. It works with `testing-runbook-creator`, which decides where the runbook lives and how its entries are formatted.

## What lives where

- **This skill:** the QA process, the states and inputs to try, the default screen widths (breakpoints, where the layout changes), and the pass or fail decisions.
- **Repo runbook:** routes (page addresses), selectors (the labels a test uses to find an element), test accounts (placeholder logins, not real ones), seed data (test data loaded before a test starts), cleanup steps, and quirks (odd behavior to know about).
