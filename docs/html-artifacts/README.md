# html-artifacts

Renders dense or visual output (plans, reports, research explainers, review summaries, comparisons, timelines, diagrams, walkthroughs, dashboards) as one self-contained HTML file in a fixed house style, instead of a long chat reply. The chat gets a short summary and the file path.

## Triggers

Produces an artifact when you explicitly ask for one of the above, and offers one in a single line when an answer would run past about 40 lines or hold a table wider than 3 columns. Skips short answers, code edits, and requests for another file type. See `SKILL.md` for the full list.

## Install

```bash
/agentic-library use html-artifacts
# or link it manually
ln -s ~/Projects/skills/docs/html-artifacts ~/.claude/skills/html-artifacts
```

## Requirements

- Chromium or Chrome (`chromium`, `chromium-browser`, or `google-chrome`) for the verify step. Without it the skill reports that the render could not be verified.

## What you get

- One `.html` file with inline CSS and JS, no external dependencies, and full content with JS off.
- Dark-first teal on slate, Inter and JetBrains Mono system stacks, a 4px spacing scale, and an OS-following theme with a toggle.
- Layout patterns for report, comparison table, timeline, diagram, dashboard, and walkthrough.
- Saved to `~/artifacts/<YYYY-MM-DD>-<slug>.html` (or `./artifacts/` for project-specific work); the path is always printed.

## Usage

```bash
scripts/verify.sh ~/artifacts/2026-10-24-my-report.html [out-dir]
```

`verify.sh` takes full-height screenshots at 1280 and 390 px in the default and a forced-dark theme, and fails on console errors or any external URL. Screenshots go to a `.shots/` folder beside the file. The skill requires reading them before it declares the artifact done.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: triggers, hard rules, house style tokens, layout patterns, verify rule |
| `references/template.html` | Starter page with the tokens, components, theme toggle, print styles, and each layout pattern |
| `scripts/verify.sh` | Headless Chromium screenshots and console/offline checks |
