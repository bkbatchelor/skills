---
name: mermaid-to-svg
description: Renders Mermaid diagrams (flowchart, sequence, class, state, ER, gantt, pie, mindmap, and more) to validated SVG files with mermaid-cli, from .mmd files, mermaid blocks in Markdown, or pasted source. Use whenever the user asks to convert, render, export, or save a Mermaid diagram as SVG (also with PNG copies, or PDF), to turn a README's mermaid blocks into images, or to get a diagram that opens in Figma, Inkscape, Word, PowerPoint, or LaTeX. Also use when another skill needs Mermaid turned into an image file. Not for designing a diagram from a description with no Mermaid involved (use archify), charts of numeric data, or raster art (use image-gateway).
metadata:
  version: 1.2.0
---

# Mermaid to SVG

Render Mermaid source to SVG files with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`), which draws each diagram in headless Chrome. The bundled script, `scripts/render.sh`, wraps `mmdc` and provides sanity checks and portability options so the resulting SVGs work well in non-browser tools.

## Triggers

Use when the user:
- asks to convert, render, export, or save a Mermaid diagram as SVG, or as SVG plus PNG (or PDF)
- wants a README's or doc's mermaid blocks as image files
- needs a diagram that opens in Figma, Inkscape, Word, PowerPoint, LaTeX, or other non-browser tools
- or another skill needs Mermaid turned into an image file

Skip when:
- There is no Mermaid and the user wants a diagram designed from a description. Use `archify`.
- The request is a chart of numeric data, or raster art (use `image-gateway`).

## Requirements

- `node` / `npx`. If `mmdc` is on `PATH` the script uses it. Otherwise it runs `npx -y @mermaid-js/mermaid-cli@12.0.0`, which needs network access the first time.
- A Chrome or Chromium browser. The script finds `chromium`, `chromium-browser`, `google-chrome-stable`, or `google-chrome` on `PATH` and points puppeteer at it. Without one, puppeteer downloads its own copy which can be large.
- Optional: `xmllint`, used to check that the XML is well formed, and `rsvg-convert`, used for the portability preview in step 4.

If `node` is missing, stop and tell the user. Don't install a Node runtime yourself.

## Workflow

### 1. Find the source

Work out where the diagrams come from:

| Source | What to do |
|--------|------------|
| `.mmd` or `.mermaid` file | Render it directly. |
| Markdown file with ```mermaid ``` blocks | Pass the `.md` file. Every block is rendered, numbered in document order. |
| Source pasted into the conversation | Pipe it to the script on stdin, or write it to a `.mmd` file if the user wants to keep the source. |
| Mermaid embedded somewhere else (code comments, HTML `<pre class="mermaid">`, docs-site config) | Copy the diagram text into a `.mmd` file and render that file. Strip any surrounding comment markers. |

If the user hasn't said which diagrams they mean and a Markdown file has several blocks, render them all and list what was produced.

### 2. Choose where the output goes

- If the user names an output path, use it.
- Otherwise put the SVG next to its source with the same stem: `docs/flow.mmd` becomes `docs/flow.svg`, and the blocks in `README.md` become `README-1.svg`, `README-2.svg`, and so on. For a repo, ask the user if they want the outputs collected under a single directory.
- Before writing, check whether the target files already exist. Overwrite a file only if it was clearly rendered from this same source (same stem, the user is re-rendering). Otherwise ask first.

### 3. Render

```bash
SKILL=<path to this skill directory>

# Single file -> docs/flow.svg
"$SKILL/scripts/render.sh" docs/flow.mmd

# Explicit output, portable labels, theme and background
"$SKILL/scripts/render.sh" --portable -t neutral -b transparent docs/flow.mmd docs/images/flow.svg

# Every mermaid block in a Markdown file -> docs/images/README-1.svg, README-2.svg, ...
"$SKILL/scripts/render.sh" README.md docs/images/README.svg

# Diagram text from the conversation
"$SKILL/scripts/render.sh" - out/diagram.svg <<'EOF'
sequenceDiagram
  Client->>API: GET /items
  API-->>Client: 200 OK
EOF

# SVG plus a PNG beside it -> docs/flow.svg and docs/flow.png (2x scale, transparent)
"$SKILL/scripts/render.sh" --png docs/flow.mmd

# Sharper, white-background PNG capped at 1600 px on its longest side
"$SKILL/scripts/render.sh" --style modern --style-mode light --png docs/flow.mmd
"$SKILL/scripts/render.sh" --scale 3 --size 1600 -b white docs/flow.mmd docs/images/flow.svg

# Any other mmdc flag goes after --
"$SKILL/scripts/render.sh" flow.mmd flow.svg -- --no-font-embed -q
```

The script prints each SVG it wrote, then each PNG, one per line, on stdout. Its exit codes are: `0` success, `1` mmdc failed (usually a syntax error), `2` usage error, `3` nothing rendered or the output is invalid.

**Choosing options:**

- **`--portable`**: use this whenever the SVG will be opened outside a web browser, such as Inkscape, Figma import, LibreOffice, Word, PowerPoint, LaTeX, PDF tools, ImageMagick, or `rsvg-convert`. By default `mmdc` draws labels using HTML `<foreignObject>` which many non-browser tools ignore; `--portable` renders labels as SVG `<text>` so they appear correctly.
- **`-t`**: the theme. The usual ones are `default`, `neutral` (good for documents and print), `dark`, `forest`, and `base` (use it with `themeVariables` in a config file). Run `npx -y @mermaid-js/mermaid-cli@12.0.0 -- --help` to list all available themes and options.
- **`-b transparent`**: for diagrams placed on coloured or dark pages. The default background is white.
- **`--style modern`**: applies a modern, Archify-inspired look (rounded tinted nodes, dashed rounded groups, slate edges, JetBrains Mono with system fallbacks, and the whole diagram enclosed in a rounded frame) to both the SVG and the PNG. Use it when the user asks for a modern, polished, or Archify-like diagram. **`--style-mode dark|light`** picks the variant (default `dark`). **`--canvas blank|dots|grid|blueprint`** (implies `--style modern`, default `blank`) picks the background: flat, a 20px dot grid, a 40px grid, or a 32px blueprint grid. The canvas sets the page colour unless `-b` is given. It forces the `base` theme; a `-c` file overrides individual values. Combine with `--portable` for non-browser tools, which ignore the canvas pattern (the colored background may also be dropped). Styled PNGs are screenshots of the SVG in the system Chrome, and a `--canvas` PDF is printed from it, so `--size` and extra mmdc args don't apply to them; without a system Chrome the PNG falls back to mmdc and has no canvas pattern.
- **`-c config.json`**: Mermaid config, for things like `themeVariables`, `fontFamily`, and `flowchart.curve`. It is merged with `--portable` when you pass both.
- **`-- --no-font-embed`**: by default mmdc embeds web fonts, which makes even a small flowchart about 200 KB. Turning that off brings it to about 30 KB, but the viewer then falls back to its own fonts and sizes.
- **`--png`**: also writes a PNG beside each SVG, with the same stem (`flow.svg` and `flow.png`; Markdown gives `README-1.png`, and so on). Use it when the destination can't take SVG (chat, slides, email, many CMSs). The PNG background is transparent unless you pass `-b`. The script checks that each PNG is non-empty and has a PNG header.
- **`--scale N`** (default 2) sets the PNG pixel density; **`--size N`** caps the PNG's longest side. Either one implies `--png`.
- **PDF**: an output path ending in `.pdf` produces a PDF instead (no validation).

**Markdown rewriting.** If the output path ends in `.md` (e.g. `render.sh README.md out/README.md`), mmdc also writes a copy of the Markdown in which each block is replaced by `![diagram](./README-1.svg)` references and a small caption describing the diagram's source.

### 4. Verify

The script has already checked that each file is non-empty, contains `<svg`, is well-formed XML (when `xmllint` is available), and isn't Mermaid's "Syntax error" diagram. Then check that it looks right in a viewer or by rasterizing it.

1. **Look at it.** Read a PNG of the diagram (the one from `--png`, or a preview rendered into a scratch location with `render.sh --png docs/flow.mmd /tmp/flow-preview.svg`). Confirm that the nodes, labels, and arrows match the source and that no text is clipped or overlapping.
2. **Portability check** (when you used `--portable`, or when the user will open the file outside a browser): rasterize the actual SVG with `rsvg-convert docs/flow.svg -o /tmp/flow-rsvg.png` and review it.
3. For Markdown input, confirm that the number of SVGs matches the number of ```mermaid ``` blocks (`grep -c '^```mermaid' README.md`).

### 5. Fix render failures

When the script exits `1`, mmdc's parse error is shown above the `render.sh:` line, with a line number and the tokens it expected. Read `references/troubleshooting.md` for the common syntax pitfalls and fixes.

Don't silently drop parts of a diagram to get it to render.

### 6. Report

Tell the user:

- each SVG and PNG written (path and approximate size)
- the options used (`--portable`, `--png`, theme, background) and why
- any fixes made to the diagram source
- for Markdown input, which block produced which file

## Notes

- **Accessibility.** Mermaid writes `accTitle` and `accDescr` lines into the SVG's `<title>` and `<desc>`. If the SVG is going into docs and the source has neither, offer to add them.
- **Version pinning.** The script pins mermaid-cli `12.0.0` so output is reproducible. To use a different version, set `MERMAID_CLI_VERSION=<version>`. The mmdc version on `PATH` takes precedence over the pinned one.
- **Determinism.** Re-rendering unchanged source gives the same picture, but the generated SVG ids can still differ between runs. Don't treat an SVG diff as a sign that the diagram changed.
