# heavy-file-ingestion

Converts large or binary documents into smaller Markdown or CSV files, then writes an index file called `INDEX.md`. A binary file is a file in a format that only programs can read, such as PDF or Word. Markdown is a plain-text format. CSV (comma-separated values) is a table in plain text.

Analysis then reads the converted files, never the original file.

## When it runs

- Any binary document: PDF, PPTX (PowerPoint), XLSX (Excel), DOCX (Word), older Office formats, and EPUB (an e-book format).
- Any text, CSV or TSV (tab-separated values) file larger than about 200 KB or 2,000 lines.
- Any analysis request that touches one of these.

Small plain-text files are read directly.

## Triggers

It starts when you share or ask about a PDF, an Office document, or a large CSV or text file. It converts the file before any analysis. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use heavy-file-ingestion
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/research/heavy-file-ingestion ~/.claude/skills/heavy-file-ingestion
```

## Requirements

- `uv`, a Python tool runner, and `python3`.
- **markitdown**, a converter for Office, EPUB and HTML files. The script stops with an error without it. Install it by running this in a terminal:

  ```bash
  uv tool install 'markitdown[pdf,pptx,docx,xlsx,xls]'
  ```

- **poppler (recommended for PDFs).** Poppler is a set of PDF tools. It includes `pdftotext`, which reads the text, `pdfinfo`, which reads file details, `pdfimages`, which pulls out images, and `pdftoppm`, which turns pages into pictures.
  - Without `pdftotext` or `pdfinfo`, the script converts PDFs with markitdown instead. That path loses page markers, header and footer removal, and scan detection. Scan detection finds pages that are scanned pictures with no text.
  - The script prints a warning to stderr, the error output stream, and it records the warning in `INDEX.md`.
- **Optional:**
  - `libreoffice`, a free office suite. It converts legacy formats.
  - `tesseract`, an OCR program. OCR (optical character recognition) reads text from pictures. The script only flags scanned pages. Claude runs `pdftoppm` and then `tesseract` on the flagged pages by hand.
- To see which tools are installed and what each missing tool costs you, run `scripts/ingest.py --check`.

## Usage

Run these commands in a terminal. Replace `<source>` with the file to convert.

```bash
uv run --no-project python scripts/ingest.py <source> [--force] [--out DIR] [--max-chars N]
uv run --no-project python scripts/ingest.py --check
```

Output goes to `_ingested/<source-stem>/` next to the source. The source stem is the file name without its extension. If that folder is not writable, the output goes to `~/.cache/heavy-file-ingestion/<hash>/` instead. A cache folder holds files the tool can make again. An unchanged source is not converted again. The skill checks this with a SHA-256 fingerprint, a code made from the file's contents.

```text
_ingested/report/
  INDEX.md           source, hash, extent, tool, artifact table, warnings
  pages-001-004.md   chunks of about 25k characters or less
  assets/            embedded images (extracted, not described)
```

A chunk is one of the smaller files that a source is split into. `INDEX.md` lists the source, its hash (fingerprint), its size, the tool used, a table of the chunks, and any warnings.

## Chunking

| Source | Split |
|--------|-------|
| PDF | Up to 20 pages and 25k characters per file |
| Deck (PowerPoint) | About 15 slides per file |
| Spreadsheet | One file per sheet, split further when a sheet is large |
| CSV | 2,000 rows per file, with the header repeated, plus `profile.md` |
| Text | By heading, then by paragraph |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: triggers, the hard rule, recipes, chunking and the index format |
| `scripts/ingest.py` | The conversion and indexing command |
