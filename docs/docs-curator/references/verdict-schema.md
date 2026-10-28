# Verdict schema

One JSON file per reviewed cluster, written to `<out>/.docs-curator/work/verdicts/<cluster_id>.json`. `curate.py apply` reads every `*.json` in that folder. A missing verdict means "keep everything"; a malformed file is skipped with a warning in `REPORT.md`.

## Shape

```json
{
  "cluster_id": "adf3d9fe0529eefa",
  "reviewed": true,
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
| `partial_read` | no | `true` if you did not read every member in full. Listed in the report's warnings. |
| `revisions[]` | no | Claims that one document replaces another. |
| `conflicts[]` | no | Places where documents state incompatible facts. |

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

## Queue item (input)

`<out>/.docs-curator/work/queue/<cluster_id>.json` gives you:

- `cluster_id`, `read_words` (how much of each member to read).
- `members[]`: `path`, `also_at` (byte-identical copies elsewhere), `format`, `text_path` (the extracted text to read), `size_bytes`, `tokens`, and `revision_signals` (filename markers, in-text version and date, document-property date, file mtime).
- `chains[]`: revision chains the script found, with `order` (oldest to newest), which signals `agreeing` and `contradicting`, and whether it is `deterministic`.
- `near_duplicate_pairs[]`: pairs of members with high text similarity.
