# browser-qa

Tool layer for web page QA: drives a real browser through Chrome DevTools MCP and requires evidence for every finding.

## Install

```bash
ln -s "$PWD/testing/browser-qa" ~/.claude/skills/browser-qa
claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest   # if not already configured
```

## What it covers

- Layout: full-page screenshots at 1440x900, 768x1024, 390x844 plus an overflow check
- Performance: throttled mobile trace; LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 (lab data)
- New features: scripted walkthrough with console-error and failed-request checks
- Evidence rule, short report format, read-only and credential rules
- Findings about how to test a page go to the repo runbook via `testing-runbook-creator`

Works with `page-testing-memory` (process) and `testing-runbook-creator` (runbook).
