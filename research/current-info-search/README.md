# current-info-search

Answers questions about fast-changing facts (model releases, pricing, limits, library versions, changelogs, security advisories, news) from live Google Search instead of training data.

## How it works

1. **Gemini with Google Search grounding** runs first, every time. It returns an answer, the searches it ran and numbered sources, with Google redirect links resolved to real URLs.
2. **NotebookLM web research** runs only when the Gemini answer is not enough.

The skill also tells the agent to check a version, price or date it is about to write from memory.

## Triggers

Questions about recent or fast-moving facts (releases, pricing, versions, news, "latest", "still true?"), or when a remembered fact might be stale. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use current-info-search
# or link it manually
ln -s ~/Projects/skills/research/current-info-search ~/.claude/skills/current-info-search
```

## Requirements

- `python3` (standard library only)
- A `GEMINI_API_KEY`, exported or set in `~/.config/gemini/.env` (shared with `image-gateway` and `media-transcription`). Get one at https://aistudio.google.com/apikey
- For step 2: the `notebooklm` CLI, signed in with `notebooklm login`

## Usage

```bash
scripts/search.py gemini "latest stable Python release and its date"
scripts/search.py gemini "QUESTION" --json
scripts/search.py gemini "QUESTION" --model MODEL_ID
```

## Configuration

Defaults live in `config.env` and are read on every run:

| Variable | Meaning |
|----------|---------|
| `CURRENT_INFO_MODEL` | Gemini model for step 1 |
| `CURRENT_INFO_ENV_FILE` | File holding `GEMINI_API_KEY` |
| `CURRENT_INFO_NOTEBOOKLM` | NotebookLM CLI command |
| `CURRENT_INFO_NOTEBOOK_PREFIX` | Prefix for notebooks the skill creates |
| `CURRENT_INFO_NOTEBOOK_TIMEOUT` | Seconds to wait for NotebookLM research |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: when to search and how to answer |
| `scripts/search.py` | The search command |
| `config.env` | Saved preferences |
