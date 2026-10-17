---
name: mermaid-to-svg
description: Converts Mermaid diagrams (flowchart, sequence, class, state, ER, gantt, pie, mindmap, and the rest) into SVG files using mermaid-cli, then checks that the output is valid and actually shows its labels. Handles standalone .mmd/.mermaid files, every ```mermaid block in a Markdown file, and diagram source pasted into the conversation. Use whenever the user wants to render, export, convert, or save a Mermaid diagram as SVG (or PNG/PDF), turn the Mermaid blocks in a README or doc into image files, make diagrams display where Mermaid is not supported, or fix a Mermaid diagram that fails to render, even if they just say "make this chart an image".
---

# Mermaid to SVG

Render Mermaid source to SVG files with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`), which draws each diagram in headless Chrome. The bundled script, `scripts/render.sh`, wraps `mmdc` and handles the setup: it pins the CLI version, reuses a system Chrome, applies sandbox flags, and validates the result. Use the script rather than calling `mmdc` directly.

## Requirements

- `node` / `npx`. If `mmdc` is on `PATH` the script uses it. Otherwise it runs `npx -y @mermaid-js/mermaid-cli@12.0.0`, which needs network access the first time.
- A Chrome or Chromium browser. The script finds `chromium`, `chromium-browser`, `google-chrome-stable`, or `google-chrome` on `PATH` and points puppeteer at it. Without one, puppeteer downloads its own Chrome.
- Optional: `xmllint`, used to check that the XML is well formed, and `rsvg-convert`, used for the portability preview in step 4.

If `node` is missing, stop and tell the user. Don't install a Node runtime yourself.

## Workflow

### 1. Find the source

Work out where the diagrams come from:

| Source | What to do |
|--------|------------|
| `.mmd` or `.mermaid` file | Render it directly. |
| Markdown file with ```` ```mermaid ```` blocks | Pass the `.md` file. Every block is rendered, numbered in document order. |
| Source pasted into the conversation | Pipe it to the script on stdin, or write it to a `.mmd` file if the user wants to keep the source. |
| Mermaid embedded somewhere else (code comments, HTML `<pre class="mermaid">`, docs-site config) | Copy the diagram text into a `.mmd` file and render that file. Strip any surrounding comment markers or indentation. |

If the user hasn't said which diagrams they mean and a Markdown file has several blocks, render them all and list what was produced.

### 2. Choose where the output goes

- If the user names an output path, use it.
- Otherwise put the SVG next to its source with the same stem: `docs/flow.mmd` becomes `docs/flow.svg`, and the blocks in `README.md` become `README-1.svg`, `README-2.svg`, and so on. For a repo, ask whether they want an `assets/` or `docs/images/` folder instead if one already exists.
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

# Any other mmdc flag goes after --
"$SKILL/scripts/render.sh" flow.mmd flow.svg -- --no-font-embed -q
```

The script prints each SVG it wrote, one per line, on stdout. Its exit codes are: `0` success, `1` mmdc failed (usually a syntax error), `2` usage error, `3` nothing rendered or the output is invalid.

**Choosing options:**

- **`--portable`**: use this whenever the SVG will be opened outside a web browser, such as Inkscape, Figma import, LibreOffice, Word, PowerPoint, LaTeX, PDF tools, ImageMagick, or `rsvg-convert`. By default Mermaid draws flowchart, class, and state labels as HTML inside `<foreignObject>`, and those renderers drop it, which leaves empty boxes. `--portable` switches to plain SVG `<text>` and sets `xml:space="preserve"` on it so those renderers keep the spaces between words. Browsers and GitHub render either form, so if you can't tell where the file is going, use `--portable`.
- **`-t`**: the theme. The usual ones are `default`, `neutral` (good for documents and print), `dark`, `forest`, and `base` (use it with `themeVariables` in a config file). Run `npx -y @mermaid-js/mermaid-cli@12.0.0 --help` to see the full list for the pinned version.
- **`-b transparent`**: for diagrams placed on coloured or dark pages. The default background is white.
- **`-c config.json`**: Mermaid config, for things like `themeVariables`, `fontFamily`, and `flowchart.curve`. It is merged with `--portable` when you pass both.
- **`-- --no-font-embed`**: by default mmdc embeds web fonts, which makes even a small flowchart about 200 KB. Turning that off brings it to about 30 KB, but the viewer then falls back to its own fonts and label widths can shift. Keep fonts embedded unless the user cares about file size.
- **Other formats**: an output path ending in `.png` or `.pdf` produces that format instead. For sharper PNGs, add `-- -s 2`.

**Markdown rewriting.** If the output path ends in `.md` (e.g. `render.sh README.md out/README.md`), mmdc also writes a copy of the Markdown in which each block is replaced by `![diagram](./README-1.svg)`. That copy no longer contains the Mermaid source. Never overwrite the user's original Markdown this way. Write the copy somewhere else and ask before replacing anything. Often the better edit is to keep the source block and add the image link beside it, or to put the source in a `<details>` block.

### 4. Verify

The script has already checked that each file is non-empty, contains `<svg`, is well-formed XML (when `xmllint` is available), and isn't Mermaid's "Syntax error" diagram. Then check that it looks right:

1. **Look at it.** Render a PNG preview into a scratch location and read the image. Confirm that the nodes, labels, and arrows match the source and that no text is clipped or overlapping.
   ```bash
   "$SKILL/scripts/render.sh" docs/flow.mmd /tmp/flow-preview.png
   ```
2. **Portability check** (when you used `--portable`, or when the user will open the file outside a browser): rasterize the actual SVG with `rsvg-convert docs/flow.svg -o /tmp/flow-rsvg.png` and read it. If boxes appear without labels, the file still uses `<foreignObject>`. Re-render with `--portable`.
3. For Markdown input, confirm that the number of SVGs matches the number of ```` ```mermaid ```` blocks (`grep -c '^```mermaid' README.md`).

### 5. Fix render failures

When the script exits `1`, mmdc's parse error is shown above the `render.sh:` line, with a line number and the tokens it expected. Read `references/troubleshooting.md` for the common syntax pitfalls and environment problems (Chrome sandbox, missing browser, fonts, offline use). Fix the diagram source and re-render. If the fix changes what the diagram means, rather than only quoting or escaping, describe the change to the user.

Don't silently drop parts of a diagram to get it to render.

### 6. Report

Tell the user:

- each SVG written (path and approximate size)
- the options used (`--portable`, theme, background) and why
- any fixes made to the diagram source
- for Markdown input, which block produced which file

## Notes

- **Accessibility.** Mermaid writes `accTitle` and `accDescr` lines into the SVG's `<title>` and `<desc>`. If the SVG is going into docs and the source has neither, offer to add them.
- **Version pinning.** The script pins mermaid-cli `12.0.0` so output is reproducible. To use a different version, set `MERMAID_CLI_VERSION=<version>`. The mmdc version on `PATH` takes precedence over the pin.
- **Determinism.** Re-rendering unchanged source gives the same picture, but the generated SVG ids can still differ between runs. Don't treat an SVG diff as a sign that the diagram changed.
