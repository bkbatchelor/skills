# plain-english-docs

Writes documentation a non-technical reader can follow. It picks one documentation mode per section, defines terms where they first appear, writes steps as commands, covers failures, and bans agent English.

## Install

```bash
ln -s "$PWD/docs/plain-english-docs" ~/.claude/skills/plain-english-docs
```

Run the command from the root of this repository.

## What it covers

- Four modes, one per section: tutorial, how-to, reference, explanation. A skippable Background block holds any explanation a how-to needs.
- Sentence rules: define terms in place, steps as commands, name the place, reasons apart from steps, no em dashes, plain words.
- Recovery coverage: every step that can fail says what failure looks like and what to do.
- `banned-words.md`: the agent-English ban list. Add a line when you catch a new word.
- A self-check before delivery, with `scripts/check.py` for the exact checks (em dash count and ban-list hits).

Does not apply to code comments, commit messages, or agent-facing files such as `SKILL.md` and `CLAUDE.md`. Use it with `generate-readme` and `html-artifacts`.
