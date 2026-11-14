# image-gateway

Makes and edits images with Google's Gemini API, using the Nano Banana Pro image model. An API (application programming interface) is how one program calls another program's service. Gemini is Google's family of AI models.

You run one command. Saved defaults mean you do not set up each call again. Other skills can call this skill, so they do not need their own image code.

## Triggers

It starts when you ask to generate, draw, make or edit an image, icon, logo, banner or artwork. It also starts when another skill needs a raster image. A raster image is a picture made of pixels, such as a PNG or JPEG file. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use image-gateway
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/media/image-gateway ~/.claude/skills/image-gateway
```

## Requirements

- A `GEMINI_API_KEY` line in `~/.config/gemini/.env`. An API key is a secret string that lets this tool use your Google account. Make the file readable only by you by running `chmod 600` on it. That command limits the file to your user account. Get a key at https://aistudio.google.com/apikey
- Billing turned on in the Google Cloud project that owns the key. Google Cloud is Google's cloud platform. These image models have no free tier, so every image costs money.

## Usage

Run this in a terminal:

```bash
scripts/generate.sh [options] "prompt"
```

| Option | Meaning |
|--------|---------|
| `-m MODEL` | Use another model for this call only. The tool does not try a fallback model. |
| `-o PATH` | The output folder, or a full file path |
| `-n NAME` | The base file name |
| `-i FILE\|URL` | A reference or input image. Repeat the option for up to 14 images. |
| `-a RATIO` | The aspect ratio, for example `16:9` |
| `-r SIZE` | The image size: `1K` (default), `2K` or `4K` |
| `-c N` | Make N images. Each image is charged as one request. |
| `-f FMT` | `png` or `jpeg` (the default) |
| `--dry-run` | Print the request that would be sent, without sending it |

On success, the command prints one line of JSON, a structured text format. The line lists the files, the model and the estimated cost. The tool also adds that line to `.image-gateway-log.jsonl`, a log file in the output folder.

## Configuration

Defaults live in `config.env`, a settings file in the skill folder:

| Variable | Meaning |
|----------|---------|
| `IMAGE_GATEWAY_MODEL` | The default model |
| `IMAGE_GATEWAY_FALLBACK_MODEL` | A second model, used only when the default keeps failing with 429 (too many requests) or 5xx (server errors) |
| `IMAGE_GATEWAY_OUT_DIR` | The default output folder |
| `IMAGE_GATEWAY_ENV_FILE` | The file that holds the API key |

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions, cost notes and troubleshooting |
| `scripts/generate.sh` | The generation command |
| `references/api.md` | API details |
| `config.env` | Saved settings |
