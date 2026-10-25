# mermaid-to-svg

Renders Mermaid diagrams to SVG files with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`), then checks that the output is valid and actually shows the diagram.

## Triggers

Asks to render, convert, or export Mermaid diagrams as SVG (or PNG/PDF), including mermaid blocks in Markdown. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use mermaid-to-svg
# or link it manually
ln -s ~/Projects/skills/docs/mermaid-to-svg ~/.claude/skills/mermaid-to-svg
```

## Requirements

- `node` / `npx`. Without `mmdc` on `PATH`, the script runs `npx -y @mermaid-js/mermaid-cli@12.0.0`, which needs network access the first time.
- Chrome or Chromium. If none is found, puppeteer downloads its own copy.
- Optional: `xmllint` (XML well-formedness check) and `rsvg-convert` (portability preview).

## Usage

```bash
# Single file -> docs/flow.svg
scripts/render.sh docs/flow.mmd

# Explicit output, portable labels, theme and background
scripts/render.sh --portable -t neutral -b transparent docs/flow.mmd docs/images/flow.svg

# Every mermaid block in a Markdown file -> README-1.svg, README-2.svg, ...
scripts/render.sh README.md docs/images/README.svg

# Diagram text from stdin
scripts/render.sh - out/diagram.svg <<'EOF'
sequenceDiagram
  Client->>API: GET /items
EOF
```

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: finding the source, choosing output paths, rendering and checking |
| `scripts/render.sh` | Wrapper around `mmdc` with sanity checks and portability options |
| `references/troubleshooting.md` | Common failures and fixes |
