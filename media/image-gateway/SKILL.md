---
name: image-gateway
description: Generates or edits raster images through Google's Gemini API (Nano Banana Pro) with one command and saved defaults. Use whenever the user asks to generate, create, draw, render, illustrate, or make an image, picture, photo, icon, logo, banner, hero image, thumbnail, mockup, sticker, wallpaper, or artwork, or to edit, restyle, recolor, extend, or remove things from an existing image. Also use when another skill (slides, READMEs, docs, websites, social posts) needs a raster image, instead of writing its own image API code. Not for charts, diagrams, or SVG drawn from code (render those directly; use mermaid-to-svg for Mermaid).
metadata:
  version: 1.0.3
---

# Image Gateway

One command turns a prompt (and optionally reference images) into image files through Google's Gemini API (the Interactions API, `POST generativelanguage.googleapis.com/v1beta/interactions`):

```bash
~/Projects/skills/media/image-gateway/scripts/generate.sh "a lighthouse at dawn, oil painting"
```

The script is in this skill's `scripts/` folder. Use the absolute path of the directory this SKILL.md was loaded from, since the skill may be linked into several places. It needs `curl`, `jq` and `base64`.

## Triggers

Use when the user asks to generate, create, draw, render, illustrate, or make an image, picture, photo, icon, logo, banner, hero image, thumbnail, mockup, sticker, wallpaper, or artwork, or to edit, restyle, recolor, extend, or remove things from an existing image. Also use when another skill needs a raster image, such as slides, READMEs, docs, websites, or social posts, instead of writing its own image API code.

Skip when:
- The request is a chart, diagram, or SVG drawn from code. Render it directly, or use `mermaid-to-svg` for Mermaid.

## Saved preferences

These live in `config.env` next to this file, and the script reads them on every call. Flags override them for a single call. To change a default permanently, edit `config.env`.

| Setting | Value |
|---|---|
| Default model | `gemini-3-pro-image` (Nano Banana Pro) |
| Fallback model | `gemini-nano-banana-2.1` (Nano Banana 2.1), used only when Pro keeps failing with 429/5xx |
| Output directory | `~/Pictures/ai-generated` |
| API key | `GEMINI_API_KEY=` line in `~/.config/gemini/.env` |

The key is read from the env file on every call and is never copied anywhere else. Don't print it, `cat` the env file, pass it on a command line, or write it into this skill or any output. If the key is missing, the script says so. Tell the user to get a key at https://aistudio.google.com/apikey and add `GEMINI_API_KEY=...` to that file in their editor (`chmod 600`), not by pasting it into the chat. These image models have **no free tier**, so the key's project needs billing enabled.

## Usage

```
generate.sh [options] "prompt"
  -m MODEL      other model for this call (no fallback when set)
  -o PATH       output dir, or a full file path like ./assets/hero.png
  -n NAME       base filename (default: timestamp + prompt slug)
  -i FILE|URL   reference/input image, repeatable, up to 14 (URLs are downloaded first)
  -a RATIO      1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9 1:4 4:1 1:8 8:1
  -r SIZE       1K (default) | 2K | 4K
  -c N          N images = N separate requests (N × the price)
  -f FMT        png | jpeg (default jpeg; an -o path ending .png gets png)
  -x JSON       extra request-body fields, e.g. '{"tools":[{"type":"google_search"}]}'
  --no-fallback   --dry-run (prints the request body, makes no call, costs nothing)
```

On success the script prints one JSON line to stdout. Progress and errors go to stderr.

```json
{"files":["/home/.../20261020-001322-a-cozy-reading-nook.jpg"],"model":"gemini-3-pro-image","fell_back":false,"cost_usd":0.1379,"cost_is_estimate":true,"seconds":15,...}
```

It also appends that line to `.image-gateway-log.jsonl` in the output folder, which gives the user a running cost record.

### Examples

```bash
G=~/Projects/skills/media/image-gateway/scripts/generate.sh

# New image, square, straight into a project
$G -a 1:1 -o ./public/og-image.png "flat vector icon of a paper plane, teal on white"

# Edit an existing image: pass it with -i and say what changes and what stays
$G -i ./photo.jpg "remove the person on the left, keep everything else unchanged"

# Combine references (style + subject)
$G -i style.png -i product.png "the product rendered in the style of the first image"

# Wide hero at 2K (same price as 1K on Pro)
$G -a 21:9 -r 2K "misty pine forest at sunrise, cinematic"

# Cheaper draft on purpose
$G -m gemini-nano-banana-2.1 "rough storyboard frame: a kid finding a map in an attic"
```

## How to handle a request

1. **Write a good prompt.** Expand a short request into a concrete description covering the subject, setting, style or medium, lighting, composition, and any exact text to render (in quotes). For edits, say what changes *and* what must stay the same. Don't ask the user to approve the prompt for routine requests. Just generate.
2. **Pick the flags only when they matter.** Without `-a`, the model chooses the shape: Pro returned a landscape 1408×768 for a scene prompt in testing. Output is **JPEG by default**. Pass `-f png` (or an `-o` path ending in `.png`) when the user needs lossless output or will edit the image further. Pass `-a 1:1` for icons and avatars, `-a 9:16` for phone screens, and `-a 16:9` for slides and heroes. On Pro, 2K costs the same as 1K, so use `-r 2K` for anything that will be displayed large. If the user names a file or the image belongs to a project, use `-o` with that path. Otherwise leave the default folder.
3. **Run it once.** Each Pro image costs about $0.14, so don't make extra variations unless asked, and mention the total before running a batch (`-c 4` ≈ $0.55). Never loop on retries yourself: the script already retries 429/5xx errors with backoff and falls back once.
4. **Look at the result.** Open the file with your image-reading tool and check it matches the request (subject, text spelling, aspect ratio). If something is clearly wrong, say what's off and offer one re-run with a tightened prompt rather than silently spending more.
5. **Report back** with the file path, the model used, and `cost_usd` (an estimate from token counts). If `fell_back` is true, say Nano Banana 2.1 was used instead of Pro.

## Cost notes

These are Google's Standard paid-tier prices, checked 2026-10-19. The API returns token counts, not dollars, so the script estimates cost.

| Model | Per image |
|---|---|
| **Nano Banana Pro** (default) | **≈ $0.138** at 1K or 2K: $0.134 for the image (1,120 tokens at $120/M) plus ≈ $0.004 for thinking (~180 tokens) and a short caption (~100 tokens) at the text rate. Measured in testing on 2026-10-20. **≈ $0.24** at 4K (2,000 tokens). Each input image adds ≈ $0.001 |
| Nano Banana 2.1 (fallback) | $0.034 at 1K, $0.050 at 2K, $0.113 at 4K |

Mention the cost when it's above about $0.25, or when the user asks for several images. For many images at half price, Google's Batch API exists, but this script doesn't use it.

## Known behavior and troubleshooting

- **429 `RESOURCE_EXHAUSTED`** is the key's Google project quota or rate limit. A message about the free tier or "limit: 0" means billing isn't enabled. The script retries (10s, then 20s), then switches once to Nano Banana 2.1. If both fail, tell the user to check https://aistudio.google.com/usage and billing. Don't keep retrying.
- **400 `INVALID_ARGUMENT`** usually means a bad value: `512` on Pro, an unsupported ratio, or a huge input image. The script uppercases sizes for you, since the API rejects `2k`.
- **No image in the response** usually means a safety block. The script prints the model's text explanation. Rephrase rather than retry the same prompt.
- **Transparent backgrounds** aren't supported by Gemini. Ask for a plain white or solid-color background and tell the user it'll need background removal.
- **Iterating on an image:** pass the previous output back with `-i` and describe the change. The script sends `store: false` so Google doesn't keep requests, which means server-side multi-turn (`previous_interaction_id`) isn't used.
- Pro took 15 seconds for a 1K image in testing, so it isn't slow despite the thinking step.
- Every image carries Google's invisible SynthID watermark.
- Use `--dry-run` to see the exact request body without spending anything.

For the full request and response shape, model IDs and prices, error meanings, and a raw curl example, read `references/api.md`.

## For other skills that need images

If you're another skill (or an agent running one) and need an image, call this script. Don't write your own Gemini, OpenAI, OpenRouter or other image API code. That way there's one key location, one set of defaults, one cost log, and retry/fallback handling in one place. Pass the destination with `-o` and read the `files` array from the JSON on stdout:

```bash
out=$(~/Projects/skills/media/image-gateway/scripts/generate.sh -a 16:9 -o ./slides/img/title.png "...") \
  && path=$(jq -r '.files[0]' <<<"$out")
```

If the script exits non-zero, show its stderr message to the user and continue without the image, rather than falling back to some other image API.
