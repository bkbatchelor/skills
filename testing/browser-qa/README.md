# browser-qa

Checks web pages in a real browser. It uses Chrome DevTools MCP, a connector that lets Claude control Chrome. MCP (Model Context Protocol) is a standard way for tools to plug into Claude. Every finding needs evidence, such as a screenshot or a trace. A trace is a recording of how the page loads and responds.

## Install

Run these in a terminal from the root of this repo. The first line creates a symlink, a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. Skip the second line if Chrome DevTools is already set up.

```bash
ln -s "$PWD/testing/browser-qa" ~/.claude/skills/browser-qa
claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest
```

## What it covers

- **Layout:** full-page screenshots at 1440x900, 768x1024 and 390x844 pixels. It also checks for overflow, which is content that runs past the edge of the screen and forces sideways scrolling.
- **Performance:** a throttled mobile trace. Throttled means the test slows the connection and processor to imitate a phone. The pass limits are:
  - LCP (largest contentful paint, when the main content appears): 2.5 seconds or less.
  - INP (interaction to next paint, how long the page takes to respond to a tap or click): 200 milliseconds or less.
  - CLS (cumulative layout shift, how much the page jumps while it loads): 0.1 or less.

  These numbers are lab data. They come from a test browser, not from real visitors.
- **New features:** a scripted walkthrough, which is a set of steps the browser follows. It checks for console errors (errors the page logs) and failed requests (requests that did not load).
- **Rules:** the evidence rule, a short report format, read-only access, and how credentials (login details) are handled.

Notes about how to test a page go into the repo's testing runbook, a document of test steps. The `testing-runbook-creator` skill writes them.

It works with `page-testing-memory` (the QA process) and `testing-runbook-creator` (the runbook).
