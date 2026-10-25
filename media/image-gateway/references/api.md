# Gemini image API reference

Checked against https://ai.google.dev/gemini-api/docs/image-generation, https://ai.google.dev/api/interactions-api and https://ai.google.dev/gemini-api/docs/pricing on 2026-10-19. `scripts/generate.sh` already does all of this. Read this file only to debug the script, use a field it has no flag for (pass it with `--extra`), or check prices.

## Contents
1. Endpoint and request body
2. Response
3. Models and prices
4. Errors
5. Raw curl example

## 1. Endpoint and request body

`POST https://generativelanguage.googleapis.com/v1beta/interactions` with headers `x-goog-api-key: $GEMINI_API_KEY` and `Content-Type: application/json`.

This is Google's **Interactions API**, which the current docs use for every image example. The older `models/<id>:generateContent` route with `responseModalities: ["IMAGE"]` and `imageConfig` still appears in older guides. Don't mix the two shapes.

```json
{
  "model": "gemini-3-pro-image",
  "input": [
    {"type": "text", "text": "Make it snow outside the window. Keep everything else unchanged."},
    {"type": "image", "mime_type": "image/png", "data": "<BASE64>"}
  ],
  "response_format": {"type": "image", "aspect_ratio": "16:9", "image_size": "2K", "mime_type": "image/png"},
  "store": false
}
```

| Field | Notes |
|---|---|
| `model` | Model ID (see §3) |
| `input` | A string, or an array of content blocks: `{"type":"text","text":...}` and `{"type":"image","data":<base64>,"mime_type":...}` (or `"uri"` for Files API uploads). Up to 14 reference images |
| `response_format.type` | `"image"` |
| `response_format.aspect_ratio` | `1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9 1:4 4:1 1:8 8:1` |
| `response_format.image_size` | `512` (3.1 Flash Image only), `1K` (default), `2K`, `4K`. **Uppercase K**, because `2k` is rejected |
| `response_format.mime_type` | `image/png` or `image/jpeg`. **When omitted, the API returns JPEG** (verified with Pro) |
| `response_format.delivery` | `inline` (base64 in the response) or `uri` |
| `store` | `false` means Google doesn't keep the interaction. The script sends this, which rules out `previous_interaction_id` multi-turn edits. For iterating, pass the last image back with `-i` instead |
| `previous_interaction_id` | Continue a stored conversation (needs `store` true) |
| `tools` | e.g. Google Search grounding for real-world facts. Billed per search after 5,000 free per month |
| `generation_config` | `thinking_level`, `thinking_summaries`, sampling settings |

Gemini returns **one image per request**, so `-c N` makes N requests.

## 2. Response

```json
{
  "id": "v1_...", "object": "interaction", "status": "completed", "model": "gemini-3-pro-image",
  "steps": [
    {"type": "model_output", "content": [
      {"type": "text", "text": "Here is ..."},
      {"type": "image", "mime_type": "image/png", "data": "<BASE64>"}
    ]}
  ],
  "usage": {"total_input_tokens": 32, "total_output_tokens": 1223, "total_thought_tokens": 180,
            "total_tokens": 1435, "input_tokens_by_modality": [{"modality": "text", "tokens": 32}],
            "output_tokens_by_modality": [{"modality": "image", "tokens": 1120}]}
}
```

That `usage` is real, from a 1K Pro image on 2026-10-20. `total_output_tokens` includes about 100 caption-text tokens on top of the 1,120 image tokens. Only `output_tokens_by_modality` separates them.

Take the **last** `image` block from the `model_output` steps. The SDKs expose this as `interaction.output_image`. The response has no dollar cost, so the script estimates it from `usage` (see §3).

## 3. Models and prices

Standard paid tier per 1M tokens. **None of these image models has a free tier.** The key's Google Cloud project needs billing enabled.

| Model ID | Name | Input | Text + thinking out | Image out | Per image |
|---|---|---|---|---|---|
| `gemini-3-pro-image` | Nano Banana Pro | $2.00 | $12.00 | $120 | **$0.134** (1K/2K, 1,120 tok), **$0.24** (4K, 2,000 tok) |
| `gemini-nano-banana-2.1` | Nano Banana 2.1 | $1.50 | $7.50 | $30 | $0.034 (1K), $0.050 (2K), $0.113 (4K) |
| `gemini-3.1-flash-image` | Nano Banana 2 | $0.50 | $3.00 | $60 | ≈ $0.067 (1K) |
| `gemini-3.1-flash-lite-image` | Nano Banana 2 Lite | | | | cheapest, 1K only, weak at references |

Each input image costs about 560 tokens (≈ $0.001 on Pro). Thinking tokens are billed at the text rate, which adds a few tenths of a cent on Pro. The Batch and Flex tiers are half price but asynchronous, and the script doesn't use them.

Estimate: `(input × in + (thought + output − image) × text + image × image_rate) / 1e6`, with image tokens taken from `output_tokens_by_modality`. For the test image: (32×2 + 283×12 + 1120×120) / 1e6 = **$0.1379**.

## 4. Errors

Error body: `{"error": {"code": 429, "message": "...", "status": "RESOURCE_EXHAUSTED"}}`.

- `429 RESOURCE_EXHAUSTED`: the key's project hit its rate or quota limit. A message mentioning "limit: 0" or the free tier means the project has no billing, and these models need it. Check at https://aistudio.google.com/usage.
- `400 INVALID_ARGUMENT`: a bad field value (lowercase `2k`, `512` on Pro, an unsupported ratio) or an oversized input image.
- `403 PERMISSION_DENIED`: the key is invalid or restricted, or the API isn't enabled for the project.
- `500/503`: transient. The script retries.
- `status` other than `completed`, or no image block: usually a safety block. The model's text explains why.

## 5. Raw curl example

This reads the key from the env file without `source`, and keeps it out of `ps` and shell history:

```bash
KEY=$(sed -n 's/^GEMINI_API_KEY=//p' ~/.config/gemini/.env | tail -n1)
printf 'header = "x-goog-api-key: %s"\n' "$KEY" \
  | curl -sS -K - -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
      -H 'Content-Type: application/json' \
      -d '{"model":"gemini-3-pro-image","input":"a red apple on a wooden table","response_format":{"type":"image","aspect_ratio":"1:1"},"store":false}' \
  > /tmp/resp.json
jq -r '[.steps[] | select(.type=="model_output") | .content[] | select(.type=="image")] | last | .data' /tmp/resp.json \
  | base64 -d > apple.png
jq '.usage, .error' /tmp/resp.json
```
