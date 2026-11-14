---
name: page-testing-memory
description: Teaches the general process for QA of any web page or UI, and keeps every page-specific fact in the repo's testing runbook instead of in the skill. Use whenever you QA, verify, smoke-test, or screenshot a web page, route, form, or UI component, even if the user does not say "QA". Covers page states (empty, loaded, error, loading), form testing with valid, invalid and edge input, auth boundaries, responsive breakpoints, and screenshot evidence. Pairs with testing-runbook-creator, which owns the runbook file. Skip for API-only, CLI, or unit-test work with no rendered page.
metadata:
  version: 1.1.1
---

# Page Testing Memory

This skill holds the **process** for QA of a web page. The **facts** about a particular page live in that repo's testing runbook. The skill is global and reused across projects; the runbook is local and compounds per project.

Load it together with `testing-runbook-creator`. That skill decides where the runbook lives, its entry format, and the no-secrets rule. This skill does not restate them.

## When this applies

Any QA or verification of a rendered page or UI: checking a route, exercising a form, confirming a UI change, reproducing a visual bug, taking screenshots. The user does not need to say "QA" or "runbook".

## The knowledge split

| Lives in this skill (global) | Lives in the repo's testing runbook (local) |
|---|---|
| The order of the QA process | Routes and URLs, and how to start the app |
| Which states and inputs to try | Selectors and how to reach each state |
| Breakpoint defaults and evidence habits | Test accounts (placeholders only), roles, seed data |
| How to judge pass or fail | Repo-specific breakpoints, known bugs, flaky areas |
| The rule for where new knowledge goes | Cleanup steps, destructive actions, quirks |

If a fact would be wrong or meaningless in another project, it belongs in the runbook.

## Process

### 0. Read the runbook first
Open the repo runbook and find the page's entry. Follow its start command, accounts, and selectors instead of rediscovering them. If there is no entry, you will create one as you go (see "Write it down now").

### 1. Identify the page's states
List the states the page can be in, then reach and inspect each one:

- **Empty:** no data yet; look for an empty-state message or call to action rather than a blank area.
- **Loaded:** normal data, including long text, many items, and a single item.
- **Error:** failed request, server error, offline, or invalid ID in the URL. Look for a useful message, no crash, and a way to recover.
- **Loading:** throttle the network or delay the response; look for a loading indicator and no layout jump or double submit.

Also note partial states (some data loaded, some failed) and permission-limited views. Record how to force each state (mock, seed, throttle, flag) in the runbook once you find out.

### 2. Test forms
For every form or input, try:

- **Valid:** the happy path; confirm the result appears where it should and persists after reload.
- **Invalid:** required fields empty, wrong formats, mismatched fields. Confirm clear inline errors and that nothing was submitted.
- **Edge:** very long input, leading and trailing whitespace, unicode and emoji, markup or script characters (should render as text), boundary numbers, duplicate submission by double click, and back or refresh after submit.

Also check keyboard use (tab order, Enter to submit, visible focus) and that errors are tied to their fields.

### 3. Verify auth boundaries
- Logged out: protected pages redirect or deny, and show no data flash.
- Wrong role: a lower-privilege account cannot see or perform higher-privilege actions, including by URL.
- Session end: expired or signed-out sessions fail cleanly mid-task.
- Direct object access: change an ID in the URL and confirm it does not expose another user's data.

Use only the accounts the runbook lists. Never use real credentials.

### 4. Check responsive behavior
Default breakpoints: **375** (mobile), **768** (tablet), **1024** (laptop), **1440** (desktop). If the repo defines its own breakpoints (check the runbook, then the CSS or config), use those and record them. At each width look for horizontal scroll, clipped or overlapping content, unreachable controls, tap targets that are too small, and navigation that breaks.

### 5. Capture evidence
Take a screenshot of each state and each breakpoint that you report on, plus every defect. Name files so they sort and explain themselves (`<page>-<state>-<width>.png`). Save them to the scratchpad or a temp directory; do not commit them unless the runbook says the repo keeps evidence. Drive the page with whatever browser automation is available: Playwright if installed, otherwise headless Chromium with a small driver page or script. Which tool works in a given repo, and how to set it up, is a runbook fact (record it under Prerequisites / seed).

### 6. Report
Report findings as pass, fail, or not tested per state, form case, auth check, and breakpoint, with evidence paths. Separate confirmed defects from observations. Say what you could not reach and why.

## Write it down now

When you learn a page-specific fact during QA, write it into the repo runbook **immediately**, not at the end. That means: a selector, a route, how to reach a state, a test account or seed record, a cleanup step, a quirk, a flaky behavior, a working start command. Use `testing-runbook-creator`'s location and entry format, and put each page-specific fact in the field that owns it:

| Fact | Entry field |
|---|---|
| Route, start command, accounts (placeholders), seed data | Prerequisites / seed |
| URL or action that forces each state (empty, error, loading), form cases, breakpoints | Steps |
| Exact command and expected output per check | Verification |
| Bugs you confirmed, with symptom and evidence path | Known defects |
| Selectors, flaky behavior, tool quirks | Gotchas |
| Test data to remove, servers to stop | Cleanup |

If a runbook step is wrong, fix it at once and update `Last verified`.

## The leak test

If you find yourself wanting to add a project detail to **this skill** (a route, a selector, a product name, a test account, a port, a quirk of one app), stop. That is the signal it belongs in the repo's runbook. Put it there. This skill changes only when the general process improves.

## Safety

- Run against a local or non-production environment. Do not test against production.
- Create data only with clearly labeled test values, and clean it up afterward.
- Document destructive actions in the runbook, but do not run one without the user's approval in this session.
- Never write secrets or real user data into the runbook or a screenshot.
- Edit the runbook in the working tree only; do not commit it unless asked.
