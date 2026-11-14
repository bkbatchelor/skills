# current-info-search

Answers questions about facts that change quickly. Examples are model releases, prices, limits, library versions, changelogs (lists of changes in each version), security advisories (warnings about security flaws) and news. It gets the answer from live Google Search. It does not use the facts the model learned during training.

## How it works

1. **Gemini with Google Search grounding** runs first, every time. Gemini is Google's AI model. Grounding means the model bases its answer on live search results and cites them. This step returns the answer, the searches the model ran, and numbered sources. Google redirect links, which pass through a Google address, are changed into the real page addresses.
2. **NotebookLM web research** runs only when the Gemini answer is not enough. NotebookLM is a Google research tool. The skill uses its command-line tool.

The skill also tells Claude to check any version, price or date that it is about to write from memory.

## Triggers

It starts with questions about recent or fast-moving facts, such as releases, prices, versions and news. It also starts with words such as "latest" or "still true?". It starts when a fact from memory might be out of date. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use current-info-search
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/research/current-info-search ~/.claude/skills/current-info-search
```

## Requirements

- `python3`. The skill uses only the standard library, the part of Python that comes built in.
- A `GEMINI_API_KEY`. An API key is a secret string that lets this tool use Google's Gemini service. Set it as an environment variable, which is a named setting in your shell. Or put it in `~/.config/gemini/.env`. This is the same file that `image-gateway` and `media-transcription` use. Get a key at https://aistudio.google.com/apikey
- For step 2, the `notebooklm` command-line tool, signed in with `notebooklm login`.

## Usage

Run one of these commands in a terminal. Replace `QUESTION` with your question.

```bash
scripts/search.py gemini "latest stable Python release and its date"
scripts/search.py gemini "QUESTION" --json
scripts/search.py gemini "QUESTION" --model MODEL_ID
```

## Configuration

Defaults live in `config.env`, a settings file in the skill folder. The skill reads them on every run.

| Variable | Meaning |
|----------|---------|
| `CURRENT_INFO_MODEL` | The Gemini model used in step 1 |
| `CURRENT_INFO_ENV_FILE` | The file that holds `GEMINI_API_KEY` |
| `CURRENT_INFO_NOTEBOOKLM` | The command that runs the NotebookLM tool |
| `CURRENT_INFO_NOTEBOOK_PREFIX` | The name prefix for notebooks the skill creates |
| `CURRENT_INFO_NOTEBOOK_TIMEOUT` | How many seconds to wait for NotebookLM research |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: when to search and how to answer |
| `scripts/search.py` | The search command |
| `config.env` | Saved settings |
