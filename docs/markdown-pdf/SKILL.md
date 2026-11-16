---
name: markdown-pdf
description: Converts Markdown files to PDF, HTML, PNG or JPEG with the feature set of the VS Code extension "Markdown PDF" (yzane/vscode-markdown-pdf) - syntax highlighting, emoji, task checkboxes, ::: containers, :[x](file.md) includes, KaTeX math, locally drawn Mermaid diagrams, front matter, custom CSS, page size, margins, orientation, page ranges, header and footer templates, PNG/JPEG clip and quality, raw-HTML sanitizing. Use whenever the user asks to convert, export, render or print a Markdown file to PDF, HTML, PNG or JPEG, to make a PDF of a README or doc, or to batch-convert Markdown. Not for Mermaid-only diagram export (use mermaid-to-image), PDF or Office to Markdown (use heavy-file-ingestion), or Word files (use a docx skill).
metadata:
  version: 1.0.0
---

# Markdown to PDF, HTML, PNG, JPEG

`scripts/convert.sh` turns Markdown into PDF, HTML, PNG or JPEG. It reproduces the features of the VS Code extension Markdown PDF, with the same setting names and defaults, as a command line tool.

## Triggers

Use when the user asks to:
- convert, export, print or render a `.md` file to PDF, HTML, PNG or JPEG
- make a PDF (or an image) of a README, spec, report or notes
- batch-convert several Markdown files
- set page size, margins, headers, footers, or styles for a Markdown export

Skip when:
- The input is only Mermaid diagrams: use `mermaid-to-image`.
- The user wants PDF or Office files turned into Markdown: use `heavy-file-ingestion`.
- The user wants a Word file.

## Requirements

- Node.js 20 or newer. If `node` is missing, stop and tell the user. Do not install Node yourself.
- A Chromium-based browser (Chrome, Chromium or Edge) for PDF, PNG and JPEG. The script finds one on `PATH`, or use `--chrome PATH`. HTML needs no browser. This skill never downloads a browser. If none is found, say so and offer HTML output or ask the user to install one.
- First run installs the npm packages into the skill folder (`npm ci`, needs network once).

## Workflow

1. **Find the inputs.** One or more `.md` files. Ask only if the path is unclear.
2. **Pick formats.** Default is PDF. `-t pdf,html` or `-t all` for several. Output goes beside the source unless the user names a folder (`-o DIR`). Check the target files before writing: do not overwrite a file that was not made from this same source without asking.
3. **Diagrams are drawn locally; nothing is sent to a server.** Mermaid is drawn from the copy bundled in `node_modules` (inlined into HTML output, so it also works offline). PlantUML is **not supported on purpose**: drawing it needs a remote server, and diagram text can hold private details. A ` ```plantuml ` fence or `@startuml` block stays a plain code block and the script warns. Tell the user, and offer to rewrite the diagram as Mermaid. Never add a PlantUML server, a diagram API or any other remote renderer. Images or CSS URLs that the document itself links are still fetched by the browser; mention that if the document has remote ones and privacy matters.
4. **Run.**
   ```bash
   SKILL=<path to this skill directory>
   "$SKILL/scripts/convert.sh" README.md                         # README.pdf
   "$SKILL/scripts/convert.sh" -t pdf,html,png,jpeg doc.md        # all four
   "$SKILL/scripts/convert.sh" --landscape --format Letter --set margin.top=2cm doc.md
   "$SKILL/scripts/convert.sh" --no-header-footer --style brand.css -o out/ a.md b.md
   ```
   Paths printed on stdout are the files written. Warnings go to stderr.
5. **Verify.** Open or inspect the result before saying it is done: for a PDF run `pdfinfo` (pages, size) and `pdftotext | head` if installed, or convert page 1 to an image; for PNG or JPEG look at the image. Report any warning the script printed (missing image, failed include, PlantUML/Mermaid network use).

## Settings

Set with `--set KEY=VALUE` (repeatable), or a JSON file: `.markdown-pdf.json` beside the source or in the current folder, or `-c FILE`. Keys are the extension's `markdown-pdf.*` names without the prefix, flat (`"margin.top": "2cm"`) or nested. `convert.sh --help` prints every setting with its default. Command line values win over the file.

| Area | Settings |
|------|----------|
| Output | `type`, `outputDirectory` |
| Markdown | `breaks`, `emoji`, `highlight`, `highlightStyle` (any highlight.js style name, e.g. `monokai`), `sanitize` (`gfm`, `gfm-allow-style`, `none`), `markdown-it-include.enable`, `math.enabled`, `math.katex.macros` |
| Styling | `styles` (list of CSS paths or URLs), `includeDefaultStyles` |
| PDF page | `format`, `width`, `height`, `orientation`, `margin.top/bottom/left/right`, `scale`, `pageRanges`, `printBackground` |
| PDF header and footer | `displayHeaderFooter`, `headerTemplate`, `footerTemplate` |
| PNG and JPEG | `quality` (JPEG), `clip.x/y/width/height`, `omitBackground` |
| Browser | `executablePath` |

Header and footer templates take the placeholder classes `date`, `title`, `url`, `pageNumber`, `totalPages` on a `<span>`, plus `%%ISO-DATE%%`, `%%ISO-TIME%%` and `%%ISO-DATETIME%%`. `width` and `height` override `format`.

## Markdown syntax it understands

- Task lists `- [x]`, emoji `:smile:`, GitHub-style heading ids (so `[link](#my-heading)` works).
- `::: warning` ... `:::` makes `<div class="warning">`. The stylesheet styles `note`, `info`, `tip`, `warning`, `danger`, `important`.
- `:[label](other.md)` on its own line inlines another file. A missing file shows a red note and the export continues.
- Math with `$..$`, `$$..$$`, `\(..\)`, `\[..\]`.
- ` ```mermaid ` fences, drawn locally. PlantUML is not drawn (see step 3).
- `<div class="page"/>` forces a page break.
- YAML front matter is removed from the output. `title` becomes the document title (and the header title).

## Security

Raw HTML in the Markdown is sanitized by default (`sanitize=gfm`): `<script>`, `<style>`, `<iframe>` and similar are removed with their content, and event attributes and inline `style` attributes are dropped. Do not set `sanitize=none` or `gfm-allow-style` for Markdown the user did not write, because the page is loaded in a real browser with access to local files.

## Not carried over from the extension

- Convert on save and the VS Code commands. This is a command line tool: re-run it, or wire it to a file watcher or git hook if the user wants that.
- Automatic Chromium download. Install a browser instead.
- PlantUML and the `mermaidServer` setting, because both mean fetching from or sending to a remote server.
