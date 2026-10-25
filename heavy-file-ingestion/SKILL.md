---
name: heavy-file-ingestion
description: Converts heavy or binary documents (PDF, PPTX, XLSX, DOCX, legacy Office, big CSV/TSV, large text dumps) into chunked Markdown/CSV artifacts plus an INDEX.md BEFORE any analysis. Use whenever the user shares, mentions, or asks anything about such a file (summarize, analyze, extract, compare, review, answer questions from it), or when a text/CSV file exceeds ~200 KB or ~2,000 lines. Never read or analyze the original file directly; all analysis reads the converted artifacts. Skip for small plain-text files, and for creating or editing PDF, Word, or PowerPoint files (use the pdf, docx, or pptx skills).
metadata:
  version: 1.0.2
---

# Heavy File Ingestion

Convert first, analyze second. The original is never the thing you read.

## Triggers

Run this skill when any of these is true, before any analysis:
- The user shares or references a binary document: `.pdf .pptx .ppt .xlsx .xls .docx .doc .odt .odp .ods .rtf .epub`, regardless of size.
- A text/CSV/TSV/JSON/log file is over ~200 KB or ~2,000 lines.
- An analysis request touches such a file (summarize, compare, extract, "what does slide 12 say").

Small plain-text files (e.g. a 5 KB Markdown file) are read directly. Creating or editing PDF, Word, or PowerPoint files is not ingestion; use the `pdf`, `docx`, or `pptx` skills.

## Workflow

1. **Check for an existing ingest.** Look for `<source dir>/_ingested/<stem>/INDEX.md`. If its `sha256` matches the source, reuse it.
2. **Ingest:** `uv run --no-project python ~/.claude/skills/heavy-file-ingestion/scripts/ingest.py <source>` (add `--force` to redo). The last output line is the artifact directory.
3. **Read `INDEX.md` first**, check Warnings, then open only the artifacts relevant to the question.
4. **Answer from artifacts**, citing artifact file and page/slide/sheet.

Output location: `_ingested/<source-stem>/` next to the source. If that directory is not writable, the script falls back to `~/.cache/heavy-file-ingestion/<hash>/`.

## Hard rule

Analysis reads converted artifacts, never the original. Before analysis, check: "Am I about to Read/open the PDF/deck/workbook/huge CSV itself?" If yes, stop and ingest. The only exception is rendering a single page to PNG (see Visual review) for flagged pages, and that PNG is itself a derived artifact.

## Conversion recipes

The script implements these; use the manual commands when it fails or you need a different cut.

| Type | Primary | Fallback |
|---|---|---|
| PDF (text) | `pdftotext -layout -f N -l M file.pdf -` per page range | `markitdown file.pdf` |
| PDF (scanned) | `pdftoppm -r 200 -png -f N -l M file.pdf out`, then `tesseract out-N.png out-N` | `ocrmypdf` (`uv tool install ocrmypdf`) |
| PPTX | `markitdown deck.pptx` (slide markers, notes, tables) | `soffice --headless --convert-to pdf`, then PDF recipe |
| XLSX | `markitdown book.xlsx` (one `##` section per sheet); for large sheets export CSV via `soffice --headless --convert-to csv` | `uv run --with openpyxl python` |
| CSV/TSV | script: row-range chunks with repeated header + `profile.md` | `uv run --with duckdb duckdb -c "SUMMARIZE SELECT * FROM 'f.csv'"` |
| DOCX | `markitdown doc.docx` | `soffice --headless --convert-to pdf` |
| Legacy .doc/.ppt/.xls/.odt/.rtf | `soffice --headless --convert-to docx/pptx/xlsx`, then the matching recipe | |
| EPUB/HTML/other | `markitdown file` | `soffice --headless --convert-to pdf` |

### Missing tools

Install without asking, user-level only:
- `markitdown`: `uv tool install 'markitdown[pdf,pptx,docx,xlsx,xls]'`
- Python libs: use `uv run --with <pkg> python ...` (no global install)

Ask the user before anything needing `sudo` (e.g. `sudo pacman -S poppler tesseract libreoffice-fresh`). Do not install `docling` (heavy ML dependencies).

## Chunking

Each artifact stays under ~25k characters (~6k tokens). Split on natural boundaries:
- **PDF:** by heading within each 20-page block; oversized sections by paragraph.
- **Decks:** ~15 slides per file, or fewer if the size cap is hit.
- **Spreadsheets:** one file per sheet; split big sheets by heading/rows.
- **CSV:** 2,000 rows per file, header repeated in each, plus `profile.md` (column types, non-null counts, samples). Query big CSVs with DuckDB over the chunks rather than reading rows.
- **Text dumps:** by heading, then paragraph.

If a source yields more than ~50 artifacts, add a coarse top-level section map to `INDEX.md` by hand.

## INDEX.md standard

Frontmatter: `source`, `sha256`, `bytes`, `extent` (pages/slides/sheets/rows), `converted`, `tool`. Then a table with columns `artifact | type | chars | ~tokens | summary` (one-line summary each), then `## Warnings`. The script writes heuristic summaries (first meaningful line); improve vague ones by hand after skimming the artifact.

## Visual review

Images and charts are extracted to `assets/` (PDFs) but never auto-captioned. Pages with little or no text are flagged in Warnings as needing visual review. When the question depends on one, render it (`pdftoppm -r 120 -png -f N -l N`) and view that single PNG.

## Verify

After ingest: INDEX.md exists, every listed artifact exists, no artifact exceeds the size cap, and Warnings were reviewed. Tell the user the artifact directory.
