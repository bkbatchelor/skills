# Mermaid Rendering Troubleshooting

## Reading the error

When parsing fails, mmdc prints something like:

```text
Error: Parse error on line 4:
...owchart LR A -->
--------------------^
Expecting 'AMP', 'COLON', 'PIPE', 'TESTSTR', ... got 'EOF'
```

The line number refers to the diagram source, counting from the diagram-type line. For Markdown input it counts within the failing block. The `^` marks where the parser gave up, and the real mistake is usually just before that point.

## Common syntax pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Parse error on a node such as `end`, `End`, or `END` in a flowchart | `end` is a keyword (it closes `subgraph`) | Rename the node or quote it: `E["end"]` |
| Error near `(`, `)`, `[`, `]`, `{`, `}`, `:` or `;` inside a label | These characters are node-shape or statement syntax | Put the label in double quotes: `A["calls foo(x)"]` |
| Error on a label containing `"` | Raw quote inside a quoted label | Use `#quot;` for the quote |
| Labels show `<br>` literally or break oddly | HTML in labels | Use `<br/>` inside a quoted label: `A["line one<br/>line two"]`. This works with and without `--portable` |
| `o` or `x` at the start of a node id changes the arrow (`A---oB`) | `--o` and `--x` are circle and cross edges | Put a space before the id or rename it: `A --- oB` |
| Unknown diagram type | Typo, or a diagram type newer than the pinned mermaid-cli | Check the first line (`flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, `erDiagram`, `gantt`, `pie`, `mindmap`, `timeline`, `gitGraph`, `quadrantChart`, `sankey-beta`, `xychart-beta`, `block-beta`, `architecture-beta`, ...) or raise `MERMAID_CLI_VERSION` |
| `graph` works but `flowchart` features don't | `graph` is the legacy alias | Use `flowchart TD` / `flowchart LR` |
| Sequence diagram error on a participant name with spaces | Unquoted alias | `participant A as "Auth Service"` |
| ER diagram error on an attribute | Attributes need `type name` | `string email PK` |
| Gantt error on dates | `dateFormat` doesn't match the task dates | Make `dateFormat YYYY-MM-DD` match every date |
| Frontmatter or `%%{init: ...}%%` ignored or erroring | Bad YAML or JSON in the directive | Validate it. In a `.md` file, the `---` frontmatter has to be inside the code block |

When you can't see the error, cut the diagram in half and re-render each half until the failing line shows up.

## Rendering looks wrong

- **Boxes without text in Inkscape, Office, ImageMagick, rsvg, or PDFs.** The labels are HTML inside `<foreignObject>`. Re-render with `--portable`. In Mermaid 11+, only the top-level `htmlLabels: false` setting works. `flowchart.htmlLabels` is ignored, and the script sets the correct key.
- **Words run together in a `--portable` SVG ("twowords").** The file was rendered without the script, or edited afterwards, and has lost `xml:space="preserve"` on its `<text>` elements. Re-render it with the script.
- **Text clipped or overflowing boxes.** The fonts available at render time differ from the ones at view time. Keep embedded fonts (don't pass `--no-font-embed`), or set the same `fontFamily` in a config file that the viewer will have.
- **Diagram too small or too large.** The SVG scales freely. `-- --size 1200` sets `max-width`, and `-- -s 2` doubles the PNG resolution.
- **Dark-mode pages.** Use `-t dark -b transparent`, or `-t base` with `themeVariables` in a config file.

## Environment problems

| Message | Fix |
|---------|-----|
| `Failed to launch the browser process` / `No usable sandbox!` | Run with `MERMAID_NO_SANDBOX=1` (the script does this automatically as root). This is common in containers and on Ubuntu 23.10+ with AppArmor's user-namespace restriction. |
| `Could not find Chrome (ver. ...)` | No system browser was found and puppeteer's download was skipped or failed. Install Chromium with the system package manager (ask the user first), or set `PUPPETEER_EXECUTABLE_PATH=/path/to/chrome`. |
| `npx` hangs or fails offline | The first run needs the npm registry. Install once with `npm i -g @mermaid-js/mermaid-cli@12.0.0` (ask first) so that `mmdc` is on `PATH`, or use the Docker image below. |
| Shared-library errors such as `libnss3.so`, `libatk-1.0.so` | Puppeteer's Chrome is missing system libraries. Using the distro's `chromium` package avoids this. |

## Docker fallback

If Node and Chrome can't be used locally but Docker can (ask before pulling images):

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/data" \
  ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:12.0.0 -i flow.mmd -o flow.svg
```

Paths are relative to the mounted directory. Add `-c` for a config file. For portable labels, mount a config containing `{"htmlLabels": false}`.

The script's validation doesn't run in this mode, so check the SVG yourself as described in step 4 of SKILL.md.
