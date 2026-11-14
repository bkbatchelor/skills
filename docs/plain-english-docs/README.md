# plain-english-docs

Writes documentation that a non-technical reader can follow. It also removes agent English, the stiff, padded style that AI models tend to fall into.

The skill sets these rules:

- Pick one documentation mode for each section: tutorial (teaches a beginner by doing), how-to (gives the steps to finish a task), reference (lists facts to look up) or explanation (gives background and reasons). A skippable Background block holds any explanation that a how-to needs.
- Define each term where it first appears.
- Write steps as commands, and name the place before the action.
- Keep reasons out of steps.
- Write no em dashes. Use full stops instead.
- Use plain words. `banned-words.md` lists the words to avoid and their replacements. That list is the ban list.
- Describe the failure for every step that can fail, and say what to do next.
- Check the draft with a self-check before you hand it over.

## Install

Run this in a terminal from the root of this repository. It creates a symlink, a shortcut that makes the skill appear in `~/.claude/skills/` without copying it.

```bash
ln -s "$PWD/docs/plain-english-docs" ~/.claude/skills/plain-english-docs
```

## What it covers

- **Modes and sentences:** the four modes and the sentence rules above.
- **Failure coverage:** every step that can fail says what the failure looks like and what to do next.
- **`banned-words.md`:** the ban list. Add a line when you catch a new word or phrase.
- **Self-check:** a check before delivery. `scripts/check.py` runs the exact checks for em dashes and ban-list words.

It does not apply to code comments, commit messages, or agent-facing files such as `SKILL.md` and `CLAUDE.md`. Use it alongside `generate-readme` and `html-artifacts`. Those skills decide what a document contains and how it looks. This skill decides how each sentence reads.
