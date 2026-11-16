# markdown-pdf

Turns Markdown files into PDF, HTML, PNG or JPEG pictures. It copies the features of the VS Code extension [Markdown PDF](https://github.com/yzane/vscode-markdown-pdf) (by yzane) and uses the same setting names and defaults. You run it from a terminal or ask an agent to run it.

## Triggers

It starts when you ask to convert, export or print a Markdown file as PDF, HTML, PNG or JPEG. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use markdown-pdf
```

To install it by hand, run this in a terminal. It makes a symlink (a shortcut) so the skill appears in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/docs/markdown-pdf ~/.claude/skills/markdown-pdf
```

## Requirements

- **Node.js 20 or newer.** Check with `node -v`. If the command is not found, install Node first.
- **Chrome, Chromium or Edge** for PDF, PNG and JPEG. The script looks for one on your PATH (the list of folders your terminal searches for programs). If yours is somewhere else, pass `--chrome /path/to/browser`. HTML output needs no browser. The skill never downloads a browser for you.
- **Internet access on the first run.** The script runs `npm ci` once to install its packages into the skill folder. Each later run works offline.

## Usage

Run these in a terminal from this skill's folder, or use the full path to `scripts/convert.sh`:

```bash
# README.md -> README.pdf, next to the source
scripts/convert.sh README.md

# All four formats, written to out/
scripts/convert.sh -t all -o out/ README.md

# Page setup: landscape Letter, 2 cm top margin, no header or footer
scripts/convert.sh --landscape --format Letter --set margin.top=2cm --no-header-footer doc.md

# Your own CSS, and only pages 1 to 3
scripts/convert.sh --style brand.css --set pageRanges=1-3 doc.md

# Cropped JPEG at 80 percent quality
scripts/convert.sh -t jpeg --set quality=80 --set clip.x=0 --set clip.y=0 --set clip.width=800 --set clip.height=600 doc.md
```

The script prints each file it wrote. Problems such as a missing image go to the error output as `warning:` lines.

`scripts/convert.sh --help` lists every setting and its default. You can also keep settings in a JSON file called `.markdown-pdf.json` beside the Markdown file:

```json
{ "format": "Letter", "margin": { "top": "2cm" }, "highlightStyle": "monokai" }
```

If a setting name is not known, the script stops with `Unknown setting` and exit code 2.

## What it supports

| Feature | Notes |
|---------|-------|
| Output | PDF, HTML (images embedded), PNG, JPEG |
| Code | Syntax highlighting with highlight.js, any style by name |
| Text | Emoji codes, task checkboxes, GitHub-style heading ids, `::: warning` boxes, YAML front matter, page breaks with `<div class="page"/>` |
| Includes | `:[label](other.md)` on its own line pastes another file in |
| Math | KaTeX, drawn without a network |
| Diagrams | Mermaid, drawn on your computer from a bundled copy |
| PDF page | Paper size, custom width and height, orientation, margins, scale, page ranges, background printing |
| PDF header and footer | HTML templates with `title`, `date`, `pageNumber`, `totalPages` and `%%ISO-DATE%%` style placeholders |
| PNG and JPEG | Clip area, JPEG quality, transparent background |
| Safety | Raw HTML is cleaned by default (`sanitize`: `gfm`, `gfm-allow-style`, `none`) |

## Things to know

- **Nothing is sent to a remote server.** Mermaid diagrams are drawn on your computer. HTML output contains the Mermaid script inside the file, so it works offline too (the file is about 3 MB larger).
- **PlantUML is not supported, on purpose.** The extension draws it by sending the diagram text to a public server (plantuml.com). This tool never does that, because diagram text can hold private details. A `plantuml` block shows as plain code, and the script prints a warning. Rewrite the diagram as Mermaid.
- **Images and CSS links in your Markdown are still fetched.** If your document points at a web address for an image, the browser loads it, as it would for any web page.
- **Not included from the extension:** convert on save, the VS Code menu commands, PlantUML, the `mermaidServer` setting, and the automatic Chromium download.
- **Install audit note:** `npm audit` reports a low-severity finding in the KaTeX copy that `@vscode/markdown-it-katex` brings in. It affects KaTeX's `trust` option, which this tool does not use.

## Tests

```bash
node --test tests
```

The PDF, PNG and JPEG test is skipped when no browser is installed.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition |
| `scripts/convert.sh` | Entry point: checks Node, installs packages once, runs `convert.mjs` |
| `scripts/convert.mjs` | The converter and command line |
| `styles/default.css` | Default page styles |
| `package.json`, `package-lock.json` | Pinned packages |
| `tests/` | Sample Markdown and `node --test` tests |
