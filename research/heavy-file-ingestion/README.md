# heavy-file-ingestion

Converts heavy or binary documents into chunked Markdown/CSV artifacts plus a standard `INDEX.md` before any analysis. Analysis always reads the artifacts, never the original file.

## When it runs

- Any binary document: PDF, PPTX, XLSX, DOCX, legacy Office formats, EPUB.
- Any text, CSV or TSV file over about 200 KB or 2,000 lines.
- Any analysis request that touches one of these.

Small plain-text files are read directly.

## Triggers

Shares or asks about a PDF, Office document, or large CSV/text file. Converts it before any analysis. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use heavy-file-ingestion
# or link it manually
ln -s ~/Projects/skills/research/heavy-file-ingestion ~/.claude/skills/heavy-file-ingestion
```

## Requirements

- `uv` and `python3`
- `markitdown` (required for Office, EPUB and HTML files; hard-fails without it): `uv tool install 'markitdown[pdf,pptx,docx,xlsx,xls]'`
- Recommended: poppler (`pdftotext`, `pdfinfo`, plus `pdfimages` and `pdftoppm`) for PDFs. Without `pdftotext` or `pdfinfo`, PDFs fall back to markitdown, which loses page markers, header/footer removal and scan detection. The script prints a warning to stderr and records it in `INDEX.md`
- Optional: `libreoffice` for legacy formats. `tesseract` for scanned pages: the script only flags them, and the agent runs `pdftoppm` then `tesseract` by hand
- Run `scripts/ingest.py --check` to see which tools are installed and what each missing one costs

## Usage

```bash
uv run --no-project python scripts/ingest.py <source> [--force] [--out DIR] [--max-chars N]
uv run --no-project python scripts/ingest.py --check
```

Output goes to `_ingested/<source-stem>/` next to the source, or `~/.cache/heavy-file-ingestion/<hash>/` if that folder is not writable. An unchanged source (same SHA-256) is not re-ingested.

```
_ingested/report/
  INDEX.md           source, hash, extent, tool, artifact table, warnings
  pages-001-004.md   chunks of about 25k characters or less
  assets/            embedded images (extracted, not described)
```

## Chunking

| Source | Split |
|--------|-------|
| PDF | Up to 20 pages and 25k characters per file |
| Deck | About 15 slides per file |
| Spreadsheet | One file per sheet, split further when large |
| CSV | 2,000 rows per file with the header repeated, plus `profile.md` |
| Text | By heading, then paragraph |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: triggers, the hard rule, recipes, chunking and index format |
| `scripts/ingest.py` | The conversion and indexing command |
