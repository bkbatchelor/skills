# Reviewing packets

The script decides what it can prove. Everything else goes to a **review packet** in `docs-curator-out/packets/`, and Claude (the agent running the skill) judges it. Two kinds:

- `revision`: a revision family whose ranking is low confidence. Which file is current?
- `conflict` (prose): two documents with candidate contradicting claims. Do they really contradict?

Run `curate.py status` first. `packets_without_verdict` lists what is left to review, and `unreviewed` lists proposals that were over the packet cap and have no packet.

## What a verdict is

One JSON object per packet. The shape is in `format.md`. In short:

```json
{"proposal_id": "<packet's proposal_id>",
 "conflict": true,
 "suggested_winner": "<one of the packet's file ids, or null>",
 "rationale": "one or two sentences a reviewer can check",
 "confidence": "high | medium | low",
 "claims": [{"a": {"file": "…", "quote": "…"}, "b": {"file": "…", "quote": "…"}, "summary": "…"}]}
```

- Revision packet: set `suggested_winner` to the file you judge current, whether or not it is the script's `script_keeper`. Leave `conflict` out. Give the evidence in `rationale` (a "not approved" line in a draft, a changelog entry, a later date inside the text, a diff that only adds).
- Prose packet: set `conflict` to `true` only for a real contradiction, with one `claims` entry per contradicting pair and a short exact quote from each side. Set `false` if the candidate pairs are not about the same thing (two different limits, a figure and its unit conversion). Set `suggested_winner` when one document is clearly the authority (higher priority source, newer, more specific); otherwise leave it null and say why.
- Quote the packet's `excerpt` or `candidate_claim_pairs`. If the excerpt is too short to judge, read the file at the path given in the packet before answering; do not guess.
- When it really is ambiguous, say so with `confidence: "low"` and leave the winner null. Do not invent a verdict to clear the list.

## Never change status

Verdicts are advice. Do not edit `status` in `decisions.json` and do not run `apply` because of a verdict. `record` never touches it. Statuses are the user's, or yours only when the user explicitly asks you to accept or reject on their behalf.

## Fan-out

Up to about 20 packets: review them yourself, in one pass, writing one verdicts file.

More than about 20: split them. Start parallel subagents, each given a slice of roughly 10 to 20 packet paths, this file and the verdict shape. Tell each to:

1. read only its packets (and the files the packets point to),
2. write exactly one file, `docs-curator-out/verdicts-in/<slice-name>.json`, as `{"verdicts": [...]}`,
3. return only the number of verdicts written and any packet it could not judge,
4. not run `curate.py`, and not edit any other file.

Then run `curate.py record docs-curator-out/verdicts-in` once. `record` reads every `*.json` in the folder. Check its summary: `errors` lists unknown proposal ids, winners that are not members, and conflict packets missing `conflict`. Fix those verdicts and record again; recording the same proposal twice just replaces the earlier verdict.

Spot-check a few verdicts from each subagent against their packets before showing the user, particularly any `conflict: true`.

## After recording

Show the user `REPORT.md` (or `report.html`) and a short list of what needs a decision, with your verdicts next to the script's suggestions. They accept or reject by editing `status` in `decisions.json` (or tell you what to set). At `apply`, a verdict's `suggested_winner` becomes the keeper of an accepted revision unless `final_keeper` is set, and a `conflict: false` verdict stops an accepted conflict proposal from being flagged.
