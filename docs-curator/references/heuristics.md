# docs-curator heuristics

What the script decides by itself, how, and where the thresholds live. Defaults are in `config.env`; `DOCS_CURATOR_*` environment variables override them.

## Pre-accepted vs proposed

| Case | Starts as |
|---|---|
| Exact-byte duplicate (same sha256) | `accept` |
| Normalized-text duplicate (same words after dropping case, markup, punctuation, frontmatter, comments), including the same content in different formats | `accept` |
| Image with the same SVG-normalized hash | `accept` |
| File with an explicit `DEPRECATED`, `SUPERSEDED` or `replaced by <x>` marker where `<x>` is an existing file | `accept` |
| Near-duplicate, cross-format match below normalized equality, OCR-text duplicate | `proposed` |
| Revision family (even a high-confidence one) | `proposed` |
| Marker that names no existing file | `proposed` |
| Every conflict | `proposed` |

Re-running `analyze` keeps the status you set. Proposal ids hash the kind, method and member sha256s, so a proposal keeps its id until a member's content changes.

## Choosing the keeper among duplicates

1. Highest source `priority`.
2. Format rank (`DOCS_CURATOR_FORMAT_RANK`): `md=txt=html=csv > pptx=docx=xlsx=ppt=doc=xls > pdf > image`. The richest editable source wins.
3. Newest (best date, below), then the shorter path, then alphabetical.

Exact and normalized groups collapse first. Near-duplicate matching then looks only at each group's keeper, so one file is never in two duplicate proposals.

## Near-duplicates

- Text of `DOCS_CURATOR_MIN_WORDS` (12) words or more is sketched with a 128-bin one-permutation MinHash, banded (16 bands of 8) to find candidates, and every candidate is confirmed with exact Jaccard similarity of 5-word shingles.
- Same format: `DOCS_CURATOR_NEAR_SIM` (0.90). Different formats: `DOCS_CURATOR_CROSS_FORMAT_SIM` (0.80), since extraction differs a little between formats.
- Config files (json, yaml, toml, ini, properties) are never matched as near-duplicates, only as exact or normalized ones. A config that differs by a value is a potential conflict, not a copy.
- Two files with the same name stem but different version tokens (`spec_v1`, `spec_v2`), or a file and an earlier name of a renamed file, are revisions, not copies, so they are skipped here.
- Images: exact hash, SVG normalized hash (whitespace and attribute order ignored), and with `DOCS_CURATOR_OCR=1` identical OCR text of 5 words or more (proposed only). Images never take part in conflict checks.

## Revision families

A **family** is files sharing a normalized name stem. The stem is the file name without extension, lowercased, with these tokens removed: version (`v2`, `v1.2`, `version 3`), revision (`rev C`, `revision 2`), `final`, `draft`/`wip`, `copy`, `(1)`, ISO dates (`2026-03-01`, `20260301`) and US dates (`3-1-26`). Separators collapse to `_`.

Files join a family when:
- their text similarity (3-word shingles) is at or above `DOCS_CURATOR_FAMILY_SIM` (0.50), **and** at least one file's own name carries a token above; or
- a `git log --follow` rename chain links them: a file's earlier names count as stems too, and the similarity needed drops to half (0.25).

A plain name match with no token and no rename (two services' `README.md`, or `application.properties` in two folders) is never a family. The same relative path in two sources is also not a family; that is what config conflicts compare.

Files already excluded as duplicates or marked superseded do not take part.

### Ranking

Highest first, comparing in this order:

1. **Explicit markers.** Marked files are removed before families form.
2. **Version tokens.** Class `final` > `v`/`rev` (compared by number or letter) > no token. `draft` counts as no token; a draft is flagged instead (see below).
3. **Newest reliable date.** Git commit date; else the document's metadata date (pptx/docx `docProps/core.xml`, `pdfinfo`) or a labelled date in the content ("Last updated: 2026-03-01"); else a date in the file name.
4. **mtime**, only when no file in the comparison has a reliable date. For git-tracked files the commit date replaces mtime.

### Confidence

The ranking is **low confidence**, and the family gets a review packet, when any of these hold:
- the newest is decided only by mtime, or by nothing;
- a file has a date a day or more newer than the highest-versioned one (the layers disagree);
- the newest member is a draft;
- the newest member comes from a lower-priority source than another member.

Otherwise it is `high` (decided by version) or `medium` (decided by date).

## Markers

The first `DOCS_CURATOR_MARKER_CHARS` (3000) characters are searched for the upper-case words `DEPRECATED`, `SUPERSEDED`, `OBSOLETE`, the phrase "this document is deprecated", or `replaced by <x>` / `superseded by <x>`. `<x>` is resolved relative to the marked file's folder, then the source root, then by unique file name in the same source, then in any source. It must be an existing file other than the marked one.

## Config conflicts

- Files are flattened to fully-qualified keys (`server.port`, `hosts[0].name`).
- **Logical file**: the path with environment tokens removed, so `config/application-dev.properties` and `config/application-prod.properties` both become `config/application.properties`.
- **Scope**: the environment tokens found in the path. `DOCS_CURATOR_SCOPE_TOKENS` (`dev, development, test, qa, staging, stage, uat, prod, production, local`; `development`, `production` and `stage` are folded into `dev`, `prod` and `staging`), regions like `us-east-1`, and `tenant-<id>`.
- Only files with the same logical file **and** the same scope are compared. A different value for the same key is a deterministic conflict (listed up to 50 keys per pair).
- Never compared: dev vs prod, or two different services (different folders) with the same file name.
- Members of a revision family are not compared with each other: their differences are the revision, and the revision proposal covers them.
- Suggested winner: the higher source priority, else a clearly newer date, else none.

### YAML subset

The YAML reader handles block mappings, block lists (including lists of mappings), scalars, quoted strings, comments and `|` / `>` block scalars. Anchors, aliases, merge keys (`<<`), tags, flow collections (`{a: 1}`, `[a, b]`) and extra documents set `partial_parse`: the file is still compared on the keys that were read, and the report lists it. Flow collections are stored as one raw string value.

## Prose conflicts

1. **Topic clusters.** Documents of 30 words or more (not config, not images) get their top 15 terms by tf-idf, ignoring words only one document uses. A document joins the first cluster whose seed shares at least 4 terms or 30% of terms; otherwise it starts one. Clusters hold at most 40 documents.
2. **Claim sentences.** Sentences of 20-400 characters containing a number, money, percentage or limit, or `must`/`shall`/`should`/`never`/`required`/maximum/minimum.
3. **Candidate pairs.** One sentence from each document sharing at least 3 content words but different numbers, or at least 5 content words and opposite negation. A document pair with at least one candidate gets a packet; the 8 best candidates are in it.

This finds contradictions that are stated with numbers or opposite polarity about the same subject. It will not find a contradiction between two paraphrased claims without such a difference, and it does produce false candidates (two different limits in one document). Claude's verdict is the filter.

## Costs

Extraction is the slow part (a `soffice` conversion of a legacy file takes seconds), and it is cached by sha256, so re-runs only extract new or changed files. Near-duplicate matching is roughly linear in the number of files. Prose conflict checking is quadratic only inside a topic cluster (40 documents at most).
