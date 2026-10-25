# image-gateway

Generates or edits images through Google's Gemini API (Nano Banana Pro) with one command, using saved defaults so no per-call setup is needed. Other skills can call it instead of writing their own image API code.

## Triggers

Asks to generate, draw, make, or edit an image, icon, logo, banner, or artwork, or another skill needs a raster image. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use image-gateway
# or link it manually
ln -s ~/Projects/skills/image-gateway ~/.claude/skills/image-gateway
```

## Requirements

- A `GEMINI_API_KEY` line in `~/.config/gemini/.env` (`chmod 600`). Get a key at https://aistudio.google.com/apikey
- Billing enabled on the key's project. These image models have no free tier.

## Usage

```bash
scripts/generate.sh [options] "prompt"
```

| Option | Meaning |
|--------|---------|
| `-m MODEL` | Use another model for this call (no fallback) |
| `-o PATH` | Output directory or full file path |
| `-n NAME` | Base filename |
| `-i FILE\|URL` | Reference or input image, repeatable up to 14 |
| `-a RATIO` | Aspect ratio, for example `16:9` |
| `-r SIZE` | `1K` (default), `2K` or `4K` |
| `-c N` | N images, charged as N requests |
| `-f FMT` | `png` or `jpeg` (default) |
| `--dry-run` | Print the request body without calling the API |

On success it prints one JSON line (files, model, estimated cost) and appends it to `.image-gateway-log.jsonl` in the output folder.

## Configuration

Defaults live in `config.env`:

| Variable | Meaning |
|----------|---------|
| `IMAGE_GATEWAY_MODEL` | Default model |
| `IMAGE_GATEWAY_FALLBACK_MODEL` | Used only when the default keeps failing with 429/5xx |
| `IMAGE_GATEWAY_OUT_DIR` | Default output folder |
| `IMAGE_GATEWAY_ENV_FILE` | File holding the API key |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions, cost notes and troubleshooting |
| `scripts/generate.sh` | The generation command |
| `references/api.md` | API details |
| `config.env` | Saved preferences |
