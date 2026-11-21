# Writing questions and keys

`questions.json` is a list. Each question:

```json
{
  "id": "Q01",
  "category": "design-intent",
  "question": "Who decides X, and which decision record settles it?",
  "must_have": [
    {"point": "Record N decides X; its status is Proposed, not Accepted.", "evidence": ["docs/adr/ADR-N.md:3"]}
  ],
  "nice_to_have": ["The older record M still says Y."],
  "penalise": ["Citing record M as the current decision."],
  "key_revision": []
}
```

- `id`: `Q01`, `Q02`, ... (used in file names).
- `category`: free text; `bench compare` averages by it. Useful categories: design intent, code structure, configuration, spanning docs and code, absence trap, outdated documents.
- `must_have`: the points a full answer needs, each with file:line evidence from the repo. Correctness and completeness are graded against these.
- `nice_to_have`: extra credit, never required.
- `penalise`: wrong answers you expect, such as citing a replaced document. The judge counts them as false claims.
- `key_revision`: dated notes when an audit corrects the key.

## Good questions

- **Answerable from the repo.** Every must-have point has evidence in a file an arm can read.
- **Realistic.** Phrase them the way a developer would ask, with the vocabulary they would use.
- **Mixed.** Include lookups, questions that need two or more files, and questions about how documents or code connect (the case a graph should win).
- **Traps.** At least one each of:
  - an absence question (a record or feature that does not exist),
  - an outdated document beside its replacement,
  - a fact that lives only in a Word, PDF, Excel or PowerPoint file,
  - a question whose answer changed recently (after the graphs were built).

## Good keys

- Write the key from the source, not from an agent's answer.
- Name what makes an answer wrong in `penalise`, so the judge does not have to guess.
- Accept every correct form of a name (an identifier, a title, a header). A key that accepts only one form turns correct answers into "false claims"; the audit will report these as `KEY_ISSUE`.
- Freeze the repo commit the keys were written against, and run every arm against it.
