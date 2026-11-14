---
name: browser-qa
description: Drives a real browser through Chrome DevTools MCP to verify web changes with evidence - screenshots at desktop/tablet/mobile breakpoints, Core Web Vitals traces (LCP, INP, CLS) against thresholds, and console-error and failed-request checks during a scripted walkthrough - then reports in a fixed short format. Use whenever the user asks to verify a web change, check page performance, audit a page, test responsive behavior, or confirm a UI change works in a real browser, even if they do not name the tool. Builds on page-testing-memory (QA process) and testing-runbook-creator (runbook). Skip for API-only, CLI, or unit-test work with no rendered page.
metadata:
  version: 1.0.0
---

# Browser QA

This skill is the **tool layer** for page QA: how to drive a real browser with Chrome DevTools MCP and what counts as evidence. The QA process (page states, forms, auth boundaries) is `page-testing-memory`; the runbook location, entry format and no-secrets rule are `testing-runbook-creator`. Load both. This skill does not restate them.

## When this applies

The user asks to verify a web change, check performance, audit a page, or test responsive behavior, or you need to confirm a UI change in a real browser.

## Setup

Backend: **Chrome DevTools MCP** (`npx chrome-devtools-mcp@latest`). Check `claude mcp list` for `chrome-devtools ... Connected`. If missing: `claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest`, then restart the session. Its tools are deferred, so load the ones you need with ToolSearch (`select:mcp__chrome-devtools__navigate_page,...`). Playwright MCP is an acceptable alternative if installed, but it has no trace/Core Web Vitals tooling.

Verify the connection before relying on it: `list_pages`, `navigate_page`, `take_screenshot`, `list_console_messages`. Navigate to the page **before** `performance_start_trace` (it reloads the page).

## Rules

1. **Read the runbook first** (`testing-runbook-creator` rule 1). It may override breakpoints, thresholds, URLs and start commands.
2. **Evidence rule.** Every finding ships with a screenshot path, a metric value, or a log excerpt. "Looks fine" without evidence is not a result; report it as *not verified*.
3. **Read-only by default.** Navigate, scroll, hover, open menus, run traces. Never submit forms, click data-changing controls, or complete purchases/deletions without the user's explicit go-ahead each time. Do not test production unless the user asked.
4. **Credentials.** Never type or store credentials. If a page needs login, open the login page in the MCP's browser and wait while the user signs in. Never save session profiles, cookies or tokens to evidence files. Redact tokens, emails and session IDs in log excerpts.
5. **Evidence location.** Save to `.browser-qa/<YYYY-MM-DD>-<page-slug>/` under the **session's working directory** (ignored via the user's global gitignore; do not edit a repo's `.gitignore`). The MCP refuses `filePath`s outside its workspace roots, so a different target repo's folder will not work. Name files `<page>-<check>-<width>.png`. Take a fresh `take_snapshot` (to a file, the output is long) after every reload: element uids go stale.
6. **The browser can restart between turns.** Page ids change and emulation is lost: call `list_pages`, navigate again, and re-run `emulate` before every check. Confirm the viewport with `innerWidth` before trusting a screenshot.
7. **Unreachable means unmeasured.** If something cannot be exercised (no interactive element for INP, page needs a state you cannot reach), say *not measured*, never *passed*.

## Recipes

Pick by change type; combine when a change spans several.

### Layout change: breakpoints
Defaults (runbook may override): desktop `1440x900x1`, tablet `768x1024x2,mobile,touch`, mobile `390x844x3,mobile,touch`.

For each size: `emulate` with `viewport`, reload, `take_screenshot` with `fullPage: true`, then run an overflow check with `evaluate_script`:
```js
() => ({ scrollW: document.documentElement.scrollWidth, innerW: innerWidth,
  overflow: document.documentElement.scrollWidth > innerWidth })
```
Look for horizontal scroll, clipped or overlapping content, unreachable controls, tap targets under 44x44 px on touch sizes, and broken navigation. Reset with `emulate` (omit viewport) at the end.

### Performance-relevant change: Core Web Vitals
Thresholds (Google "good", runbook may override): **LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1**.

1. `emulate`: mobile viewport, `cpuThrottlingRate: 4`, `networkConditions: "Fast 4G"`.
2. `navigate_page` to the URL, then `performance_start_trace` (`reload: true`, `autoStop: true`, `ignoreCache: true`, `filePath` into the evidence folder).
3. Record LCP, CLS and the LCP breakdown from the summary. Use `performance_analyze_insight` for the worst insights (e.g. `RenderBlocking`, `LCPBreakdown`).
4. **INP** needs a real interaction: start a trace with `reload: false, autoStop: false`, perform a scripted click or key press (`take_snapshot` for uids, then `click`/`press_key`), then `performance_stop_trace`. If no interaction is possible, INP is *not measured*.
5. Label results **lab data** (throttled emulation, single run) and note CrUX field data if the trace reports it. Re-run once if a value is within 10% of a threshold.

### New feature: console and network during a walkthrough
1. Navigate fresh so console and network logs start clean.
2. Script the walkthrough with `take_snapshot` + `click`/`fill`/`press_key`, taking a screenshot at each step (read-only steps unless the user approved otherwise).
3. `list_console_messages` (types `error`, `warn`, `issue`) and `list_network_requests`; flag every status >= 400, failed request, and error-level message. For a suspicious request use `get_network_request`.
4. Triage: tie each message to a step. Note noise you recognise (e.g. a missing `favicon.ico` 404) as an observation, not silently drop it.

## Report format

Keep it short. Use exactly these sections:

```
## Browser QA: <page> (<date>)
**Checked:** <url>, <recipes run>, <emulation/throttling>, <evidence folder>

### Passed
- <check>: <metric or observation> - <evidence path or log excerpt>

### Failed
- <finding> - <evidence>
  Repro: 1. <step> 2. <step> -> expected X, got Y

### Not verified
- <what and why>

### Runbook
<entry added/updated, or proposed entry if no local repo>
```

## Runbook integration

Findings about **how to test the page** go to the repo's testing runbook per `testing-runbook-creator`, as you learn them: URL and start command, how to reach states, the emulation presets and thresholds used, a working INP interaction, selectors, tool quirks, and confirmed defects (symptom plus evidence path under Known defects). Page-specific facts never go into this skill (the leak test from `page-testing-memory` applies). Edit the runbook in the working tree, do not commit it. If the audited page has no local repo, put the proposed entry in the report instead of writing anywhere.
