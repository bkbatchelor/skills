# docs-curator file formats

Every file docs-curator writes that other tools or skills may read carries a `schema_version` (currently `1.0`). Check it, and treat an unknown major version as unsupported. All JSON is UTF-8. `file` ids everywhere are `<source-name>:<path relative to the source root>`, for example `official:docs/spec_final.md`.

Two files in the output folder are internal and not a contract: `inventory.json` (the file list `apply` reads) and `cache/` (extracted text and metadata keyed by sha256).

## Output layout

```
docs-curator-out/
├── sources/<name>/          clones of remote sources (ours; local sources are read in place)
├── cache/                   text/<sha>.md and meta/<sha>.json, so re-runs are incremental
├── inventory.json           internal
├── decisions.json           the proposals you review
├── packets/<proposal-id>.json   review packets for Claude
├── verdicts/                copies of the verdict files that `record` merged
├── REPORT.md, report.html   the report (self-contained)
├── quarantine.json          files left out of curated/, written by apply
└── curated/<source-name>/…  the Graphify input, with _manifest.json
```

## decisions.json

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-21T22:00:00+00:00",
  "sources": [{"name": "official", "location": "/path or url", "ref": null, "priority": 100, "commit": "a9dd0324…", "is_git": true, "include": [], "exclude": []}],
  "settings": {"near_sim": 0.9, "...": "the thresholds this run used"},
  "proposals": [ ...proposal... ],
  "unreviewed": ["conflict-62b79b02041b"],
  "dropped": ["duplicate-…"]
}
```

`unreviewed` lists proposals that need review but are over `DOCS_CURATOR_PACKET_CAP` and have no packet. `dropped` lists ids from the previous run that no longer exist.

### Proposal

| Field | Meaning |
|---|---|
| `id` | `<kind>-<12 hex>`: a hash of the kind, the method and the sorted sha256s of the members. Stable across runs, so decisions survive re-analysis. |
| `kind` | `duplicate`, `revision`, `superseded` or `conflict` |
| `method` | duplicate: `exact`, `normalized`, `near`, `cross_format`, `ocr`. revision: `version_family`, `rename_chain`. superseded: `marker`, `marker_no_target`. conflict: `config_key`, `prose`. |
| `status` | `proposed`, `accept` or `reject`. **The only field you normally edit.** `apply` acts on `accept` only. |
| `preaccepted` | true if the script set `status` to `accept` itself: exact and normalized duplicates, and markers that name an existing file. |
| `keeper` | file id kept (duplicate, revision, superseded); null for conflicts |
| `suggested_winner` | conflicts only: the script's suggestion (higher priority, then a clearly newer date), or null |
| `members` | `[{"file", "source", "path", "sha256", "format", "role"}]` with `role` `keeper`, `exclude` or `side` (a conflict side; both stay in) |
| `evidence` | method-specific details, below |
| `needs_review` / `review_reason` | whether Claude should look at it, and why |
| `packet` | `packets/<id>.json`, or null |
| `verdict` | null until `record` fills it (see Verdicts) |
| `final_keeper` | optional, set by you: overrides the keeper at `apply` |
| `note` | optional, free text |

`apply` picks the keeper in this order: `final_keeper`, then `verdict.suggested_winner`, then `keeper`. Members that are not the keeper are left out of `curated/` (for a conflict, nothing is left out).

Evidence shapes:

- duplicate: `{"similarity": 0.94 or null, "cross_format": true, "formats": ["md", "pdf", "pptx"]}`
- revision: `{"confidence": "high|medium|low", "decided_by": "version|date|mtime|none", "reasons": [...], "ranking": [{"rank": 1, "file", "version_key": [3], "draft": false, "date": 1.78e9, "date_source": "git|metadata|content|name|mtime"}]}`
- superseded: `{"marker_target": "new-process.md", "resolved": "official:docs/new-process.md"}`
- conflict `config_key`: `{"logical_file", "scope": ["prod"], "diff_count", "diffs": [{"key": "limits.max_users", "<file id>": "100", "<file id>": "250"}], "partial_parse": false}` (diffs capped at 50)
- conflict `prose`: `{"topic_terms": [...], "claim_pairs": [{"a", "b", "shared_terms", "numbers_a", "numbers_b"}]}`

## Review packet (`packets/<proposal-id>.json`)

```json
{
  "schema_version": "1.0",
  "proposal_id": "revision-2c3d79dc8b9d",
  "kind": "revision",
  "question": "Which of these files is the current revision? …",
  "script_keeper": "notes:roadmap_draft.md",
  "confidence": "low",
  "reasons": ["the newest member is a draft"],
  "files": [{"file", "source", "priority", "path", "signals", "commit_date", "excerpt"}],
  "diff_newest_vs_next": ["--- …", "+++ …"]
}
```

A `conflict` packet has `suggested_winner_by_script`, `topic_terms`, `candidate_claim_pairs` (same shape as the evidence's `claim_pairs`) and `files` (with longer excerpts) instead of `script_keeper`, `confidence`, `reasons` and the diff.

## Verdicts file

A JSON object with a `verdicts` list, a bare list, or a single verdict. `record` also accepts a folder of such files.

```json
{
  "schema_version": "1.0",
  "verdicts": [{
    "proposal_id": "conflict-62b79b02041b",
    "conflict": true,
    "suggested_winner": "shared:docs/data-retention.md",
    "rationale": "Retention after closure is 30 days in one document and 365 in the other.",
    "confidence": "high",
    "claims": [{"a": {"file": "notes:retention-policy.md", "quote": "retained for 30 days"},
                "b": {"file": "shared:docs/data-retention.md", "quote": "retained for 365 days"},
                "summary": "30 vs 365 days"}]
  }]
}
```

- `proposal_id` must exist in `decisions.json`.
- `conflict` (true/false) is required for conflict proposals. With `conflict: false`, `apply` does not flag the pair even if accepted.
- `suggested_winner` is optional and must be one of the proposal's member file ids. For a revision it is the file Claude judges current.
- `record` stores `{suggested_winner, conflict, rationale, confidence, claims, recorded_at}` as the proposal's `verdict`. It never changes `status`.

## curated/_manifest.json

```json
{
  "schema_version": "1.0",
  "generated_at": "…",
  "entries": [{
    "kind": "native | converted | unhandled",
    "source": "official", "path": "docs/spec_final.md", "sha256": "…", "format": "md", "commit": "a9dd0324…",
    "source_location": "/path or url",
    "curated_path": "official/docs/spec_final.md",
    "revision_rank": 1,
    "supersedes": ["official:docs/spec_v1.md"],
    "duplicates_of_this": [],
    "conflicts_with": [{"path": "shared/config/settings.yaml", "proposal_id": "conflict-db05c4f9c6d3", "summary": "…"}]
  }]
}
```

- Every file in `curated/` (except the manifest) has exactly one entry. `curated_path` is relative to `curated/`.
- `unhandled` entries have `curated_path: null`, `reason`, and none of the provenance fields. They are files with no extractor, git-lfs pointer stubs, and files whose extraction failed. They are never silently dropped.
- Excluded files are not here; they are in `quarantine.json`.

## quarantine.json

```json
{
  "schema_version": "1.0",
  "generated_at": "…",
  "entries": [{
    "file": "notes:terms.md", "source": "notes", "path": "terms.md", "sha256": "…", "format": "md",
    "proposal_id": "duplicate-1b5ecc0ce2d6",
    "reason": "duplicate (exact) of official:docs/glossary.md",
    "proposals": ["duplicate-1b5ecc0ce2d6"]
  }]
}
```

`proposal_id` is the first accepted proposal that excluded the file; `proposals` lists all of them.

## Converted file frontmatter

Converted files are `<relpath>.md` (for example `decks/q3.pptx.md`) starting with YAML frontmatter. Native files get the same fields in `_manifest.json` instead, because they are linked unchanged.

```yaml
---
schema_version: "1.0"
source: "notes"
source_location: "/home/me/notes"
commit: null
path: "decks/q3.pptx"
sha256: "…"
format: "pptx"
revision_rank: null
supersedes: []
duplicates_of_this: []
conflicts_with:
  - path: "shared/docs/other.md"
    proposal_id: "conflict-62b79b02041b"
    summary: "…"
---
```

`revision_rank` is 1 for the newest member of an accepted revision family, 2 for the next, and null for files outside a family. `conflicts_with[].path` is a path under `curated/`; `supersedes` and `duplicates_of_this` hold original file ids, since those files are not in `curated/`. Values are JSON-quoted strings, which is valid YAML.
