# html-artifacts

Turns dense or visual output into one web page file. You open the file in a browser. The output can be a plan, report, research explainer, review summary, comparison, timeline, diagram, walkthrough or dashboard. The page uses one fixed look, called the house style. The chat then gets a short summary and the file path, instead of a long reply.

## Triggers

It makes the page when you ask for one of the outputs above. It offers one in a single line when an answer would run past about 40 lines or hold a table wider than 3 columns. It skips short answers, code edits, and requests for another file type. `SKILL.md` has the full list.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use html-artifacts
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/docs/html-artifacts ~/.claude/skills/html-artifacts
```

## Requirements

- Chromium or Chrome, a web browser. The verify step uses it to take screenshots. The skill looks for a command named `chromium`, `chromium-browser` or `google-chrome`. Without one, the skill reports that it could not verify how the page looks.

## What you get

- One `.html` file. It holds its own styles (CSS) and scripts (JavaScript) inside the file, so it loads nothing from elsewhere. All of its content shows even when JavaScript is turned off.
- A dark-first look: teal on slate. The fonts are Inter and JetBrains Mono. If a computer lacks them, the page uses fonts that it does have. Spacing uses steps of 4 pixels. The theme follows your computer's light or dark setting, and a toggle lets you switch it.
- Layout patterns for a report, a comparison table, a timeline, a diagram, a dashboard and a walkthrough.
- A file saved to `~/artifacts/<YYYY-MM-DD>-<slug>.html`. The slug is a short name made of words joined by dashes. For project-specific work, the file goes to `./artifacts/` instead. The skill always prints the path.

## Usage

Run this in a terminal to check a page:

```bash
scripts/verify.sh ~/artifacts/2026-10-24-my-report.html [out-dir]
```

The script takes a full-height screenshot, a picture of the whole page, at 1280 and 390 pixels wide. It takes them in the normal theme and in a forced dark theme. It fails if the page logs console errors, which are messages the browser prints when something breaks. It also fails if the page loads any external URL.

The screenshots go in a `.shots/` folder beside the file. Claude reads them before it says the page is done.

If `verify.sh` fails, fix the file and run the script again.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: when to use the skill, hard rules, house style values, layout patterns, and the verify rule |
| `references/template.html` | A starter page with the style values, components, theme toggle, print styles and each layout pattern |
| `scripts/verify.sh` | Takes the headless Chromium screenshots and checks for console errors and offline problems. Headless means the browser runs with no window. |
