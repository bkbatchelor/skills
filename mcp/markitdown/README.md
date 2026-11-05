# markitdown (MCP server)

Microsoft's [MarkItDown](https://github.com/microsoft/markitdown) as an MCP server. Converts PDF,
Office files (DOCX, XLSX, PPTX), HTML, images, audio and more into Markdown for an agent to read.

Exposes one tool:

| Tool | Purpose |
|------|---------|
| `convert_to_markdown` | Convert a URI (`http:`, `https:`, `file:`, `data:`) to Markdown |

## Requirements

[`uv`](https://docs.astral.sh/uv/) on `PATH`. Nothing else — `uvx` fetches and caches
`markitdown-mcp` on first launch, so there is no package to install or keep updated by hand.

The upstream package publishes pre-release versions only; `uvx` resolves these without extra flags.

## Install

```bash
/agentic-library use markitdown          # global  → ~/.claude/mcp/, registered in ~/.claude.json
/agentic-library use markitdown -p       # project → .claude/mcp/,  registered in ./.mcp.json
```

Restart the harness afterwards so the server loads.

## Manual registration

Merge the contents of `mcp.json` into `mcpServers.markitdown` in `~/.claude.json` (global) or
`./.mcp.json` (project).

## Notes

- `convert_to_markdown` returns Markdown as text; it does not write files. For large documents that
  need chunking to disk plus an `INDEX.md`, use the `heavy-file-ingestion` skill instead.
- To pin a version, change `args` to `["markitdown-mcp@0.0.1a8"]`.
