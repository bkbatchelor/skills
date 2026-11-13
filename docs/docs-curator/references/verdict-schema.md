# Verdict schema

One JSON file per reviewed cluster, written to `<out>/.docs-curator/work/verdicts/<cluster_id>.json`. `curate.py apply` reads every `*.json` in that folder. A missing verdict means "keep everything"; a malformed file is skipped with a warning in `REPORT.md`.

## Shape

```json
{
  "cluster_id": "adf3d9fe0529eefa",
  "reviewed": true,
  "review_tier": "standard",
  "model": "sonnet",
  "partial_read": false,
  "revisions": [
    {
      "superseded": "policy/travel_policy.md",
      "superseded_by": "policy/travel_policy_updated.md",
      "confidence": 0.95,
      "rationale": "Same policy restated with a shorter claim window.",
      "unique_content": ["Field station travel: staff travelling to Antarctic research stations receive a per diem of 85 USD"]
    }
  ],
  "conflicts": [
    {
      "topic": "Guaranteed monthly uptime",
      "statements": [
        {"path": "ops/sla_standard.md", "quote": "The platform is guaranteed 99.9% monthly uptime.", "location": "first paragraph"},
        {"path": "support/support_terms.md", "quote": "Monthly uptime is guaranteed at 99.5% for standard plans.", "location": "first paragraph"}
      ],
      "rationale": "The two documents promise different uptime figures."
    }
  ]
}
```

An empty verdict, `{"cluster_id": "<id>", "reviewed": true}`, means "reviewed, nothing found".

## Fields

| Field | Required | Meaning |
|-------|----------|---------|
| `cluster_id` | yes | The queue item's id. Ties the verdict to the cluster; a stale id only produces a warning. |
| `reviewed` | yes | Always `true`. |
| `review_tier` | no | `standard` or `deep`: copy it from the queue item's `review.tier`. A `standard` verdict that holds a conflict or a revision below `low_confidence_threshold` is queued again at the deep tier on the next `analyze`. Without it a verdict is never re-queued. |
| `model` | no | The model alias that wrote the verdict (for the record only). |
| `partial_read` | no | `true` if you did not read every member in full. Listed in the report's warnings. |
| `revisions[]` | no | Claims that one document replaces another. |
| `conflicts[]` | no | Places where documents state incompatible facts. |
| `decision_checks[]` | no | Requirement-versus-ADR findings. Only for queue items with `"decision_check": true`. |
| `doc_type_guesses[]` | no | `{path, type}` (`requirement` or `adr`) for a member you classified yourself because no front matter `type` or path glob matched. Reported as a guess. |

### `revisions[]`

- `superseded`: source-relative path of the older document. `superseded_by`: path of the document that replaces it. Both must exist in the corpus and differ.
- `confidence`: number from 0 to 1. At or above `low_confidence_threshold` (default 0.75) the older file is excluded as `superseded`. Below it, the file is kept as `low_confidence_keep`.
- `rationale`: one or two sentences citing what in the text supports the claim.
- `unique_content`: short excerpts or descriptions of material the superseded file has and the newer one lacks. When non-empty, the full superseded file is also written to `_curated/historical/`. Use `[]` when there is none.
- When filename, in-text, and document-property signals already give a deterministic order (at least two agree and none contradict), the script's order wins. A verdict that disagrees only produces a warning.

### `conflicts[]`

- `topic`: a short label. `rationale`: why the statements cannot both hold.
- `statements[]`: at least two entries of `{path, quote, location}`. `quote` should be copied verbatim (whitespace and case are ignored when checked). `location` is free text such as a heading or sheet name.
- Conflicts never exclude anything. They are written to `_curated/CONFLICTS.md` and `.docs-curator/conflicts.json`.

### `decision_checks[]`

For a cluster that holds both business requirements and ADRs (`"decision_check": true` in the queue item). Each entry:

```json
{
  "kind": "conflict",
  "topic": "Payment retry limit",
  "requirement": {"path": "docs/retries.md", "quote": "retry failed payment submissions up to 10 times", "location": "first paragraph"},
  "adr": {"path": "adr/0007-retries.md", "quote": "capped at 3 attempts", "location": "decision"},
  "adr_status": "accepted",
  "requirement_version": "2",
  "rationale": "A cap of 3 cannot satisfy 10 retries."
}
```

- `kind`: `conflict` (the two cannot both hold), `gap` (a requirement no ADR addresses, an ADR no requirement justifies, or an ADR that ignores a requirement), or `cant_tell`. Anything else is read as `cant_tell`.
- `requirement` / `adr`: `{path, quote, location}`. A `conflict` needs both sides with a verbatim quote; a `gap` may have one side. Quotes are checked like conflict quotes and marked `[quote not verified]` when missing.
- `adr_status` and `requirement_version`: copy them from the documents (the queue item gives `doc_status`). Check whether the ADR is superseded before calling something a conflict; a superseded ADR is not binding.
- A `conflict` is written to `_curated/CONFLICTS.md` under `[requirement vs ADR]`. `gap` and `cant_tell` appear in the report's "Requirements and ADRs" section. Nothing is excluded, and no document is changed.

## Queue item (input)

`<out>/.docs-curator/work/queue/<cluster_id>.json` gives you:

- `cluster_id`, `read_words` (how much of each member to read).
- `members[]`: `path`, `also_at` (byte-identical copies elsewhere), `format`, `text_path` (the extracted text to read), `size_bytes`, `tokens`, and `revision_signals` (filename markers, in-text version and date, document-property date, file mtime).
- `chains[]`: revision chains the script found, with `order` (oldest to newest), which signals `agreeing` and `contradicting`, and whether it is `deterministic`.
- `near_duplicate_pairs[]`: pairs of members with high text similarity.
- `members[].doc_type`, `type_source` (`front_matter`, `path` or `classifier`), `doc_id`, `doc_status`: present when a member is a requirement or ADR. `type_confidence` is added when the classifier typed it. `decision_check` is `true` when the cluster holds both.
- `review`: `{tier, model, reasons[]}`, the routing for this cluster. `tier` is `deep` when `reasons` is non-empty: `requirement_vs_adr`, `ambiguous_revision_chain` (a chain the signals could not order), `large_cluster` (at least `deep_review_min_members` members), or `escalated_conflict_found` / `escalated_low_confidence_revision` (a standard review that found something). `model` is the alias from `review_model_deep` or `review_model_standard`. `<out>/.docs-curator/work/routing.json` groups the queued cluster ids by model.

## Classification pre-step (optional)

Only when `classify_untyped: true`. `analyze` queues documents that have no front matter `type` and match no glob, in batches of `classify_batch_size`: `<out>/.docs-curator/work/classify/queue/<batch_id>.json`.

```json
{"batch_id": "5b1c0e7d2a9f4c31", "model": "haiku", "labels": ["requirement", "adr", "other"],
 "docs": [{"path": "docs/retries.md", "sha256": "…", "format": "md", "title": "Payment retries", "snippet": "first 300 words…"}]}
```

Write one file per batch to `<out>/.docs-curator/work/classify/labels/<batch_id>.json`:

```json
{"batch_id": "5b1c0e7d2a9f4c31",
 "labels": [{"sha256": "…", "path": "docs/retries.md", "type": "requirement", "confidence": 0.95}]}
```

- `type`: `requirement` (a business requirement: what the system must do), `adr` (an architecture decision record: a decision, its context and status) or `other`. Use `other` for anything that is not clearly one of the first two.
- `confidence`: 0 to 1. Below `classify_min_confidence` (default 0.8) the label is ignored. The document stays untyped and is not queued again.
- Labels are keyed by `sha256`, so they survive a rename and stop applying when the file changes. A malformed file or entry is skipped with a warning.
- A document whose front matter declares any `type` (even `policy`) is never queued or overridden. Front matter and globs always win over a label.
