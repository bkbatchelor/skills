# Gemini 3.5 Transcribe API reference

Checked on 2026-10-20 against https://ai.google.dev/gemini-api/docs/transcribe, https://ai.google.dev/gemini-api/docs/models/gemini-3.5-transcribe, https://ai.google.dev/gemini-api/docs/files and https://ai.google.dev/gemini-api/docs/pricing, and against live API responses. `scripts/transcribe.py` already does all of this. Read this file only to debug the script or to extend it.

## Contents
1. Upload (Files API)
2. Transcribe request
3. Response, as actually returned
4. Chapter request
5. Limits and incompatibilities
6. Prices
7. Raw curl example

## 1. Upload (Files API)

Audio goes through the Files API, which is free. Files are kept for 48 hours, at most 2 GB each. The script deletes them as soon as the transcription returns.

1. **Start.** `POST https://generativelanguage.googleapis.com/upload/v1beta/files` with these headers: `x-goog-api-key`, `X-Goog-Upload-Protocol: resumable`, `X-Goog-Upload-Command: start`, `X-Goog-Upload-Header-Content-Length: <bytes>`, `X-Goog-Upload-Header-Content-Type: audio/flac`, `Content-Type: application/json`. Body: `{"file": {"display_name": "…"}}`. The upload URL comes back in the `X-Goog-Upload-URL` response header.
2. **Upload.** `POST <upload url>` with `X-Goog-Upload-Offset: 0`, `X-Goog-Upload-Command: upload, finalize`, and the raw bytes as the body. The response is `{"file": {"name": "files/abc", "uri": "https://…/v1beta/files/abc", "mimeType", "sizeBytes", "state": "ACTIVE", "expirationTime", …}}`. Audio was already `ACTIVE` in testing. The script polls `GET /v1beta/files/abc` while it isn't.
3. **Delete.** `DELETE https://generativelanguage.googleapis.com/v1beta/files/abc`.

## 2. Transcribe request

`POST https://generativelanguage.googleapis.com/v1beta/interactions` (the Interactions API), headers `x-goog-api-key` and `Content-Type: application/json`:

```json
{
  "model": "gemini-3.5-transcribe",
  "input": [{"type": "audio", "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc", "mime_type": "audio/flac"}],
  "generation_config": {
    "transcription_config": {
      "language_codes": ["en-US"],
      "mode": {"type": "verbatim", "diarization_mode": "speaker", "timestamp_granularities": ["word"]}
    }
  },
  "store": false
}
```

| Field | Notes |
|---|---|
| `model` | The speech model field. `gemini-3.5-transcribe` handles files. `gemini-3.5-transcribe-live` is the WebSocket streaming variant: no diarization or word timestamps, 10-minute sessions, not used here |
| `input[].type` | `"audio"`, with `uri` (Files API) or inline base64 `data` (requests under 100 MB) and a `mime_type` |
| `transcription_config.language_codes` | BCP-47 codes. Omit it or pass `[]` for auto-detect, which handles code-switching |
| `transcription_config.mode` | `"smart"` (string) for a cleaned, formatted transcript, or `{"type": "verbatim", …}` (the default). `diarization_mode` and `timestamp_granularities` work **only in verbatim** |
| `mode.diarization_mode` | `"speaker"` |
| `mode.timestamp_granularities` | `["word"]`. Google notes this may slightly lower accuracy |
| `transcription_config.custom_vocabulary` | Up to 1,000 terms (100 or fewer works best). **Rejected together with diarization or timestamps** |
| `store` | `false` means Google doesn't keep the interaction |

Supported MIME types: `audio/wav`, `mp3`, `aiff`, `aac`, `ogg`, `flac`, `mpeg`, `m4a`, `l16`, `opus`, `alaw`, `mulaw`, `webm`. The script always sends FLAC that ffmpeg made, so container quirks don't matter.

## 3. Response, as actually returned

```json
{
  "status": "completed", "model": "gemini-3.5-transcribe", "object": "interaction",
  "steps": [{"type": "model_output", "content": [{
    "type": "text",
    "text": "Welcome back to Build Notes. … GitHub Actions.Yeah, we finally did it …",
    "annotations": [
      {"type": "word_info", "text": "Welcome", "start_offset": "0.100s", "end_offset": "0.400s",
       "speaker": "spk:0", "start_index": 0, "end_index": 7},
      {"type": "word_info", "text": "Notes.", "start_offset": "1.100s", "end_offset": "1.700s", "speaker": "spk:0", …},
      {"type": "word_info", "text": "Today", "start_offset": "2s", …}
    ]
  }]}],
  "usage": {"total_input_tokens": 1105, "input_tokens_by_modality": [{"modality": "audio", "tokens": 1104}, …],
            "total_output_tokens": 151, "total_thought_tokens": 0}
}
```

Differences from Google's docs, seen in live responses on 2026-10-20:

- Speaker labels are `spk:0`, `spk:1`, …, not `spk_1`.
- Offsets are duration strings that drop trailing zeros: `"2s"`, `"0.100s"`.
- Word `text` includes the punctuation attached to it. `start_index`/`end_index` are character offsets into `text`.
- The full `text` joins turns with no space between them (`"Actions.Yeah,"`). Build display text from the words, not from `text`.
- Audio costs 25 tokens per second (44 s → 1,104 tokens).

## 4. Chapter request

Same endpoint, a text model, and structured output:

```json
{
  "model": "gemini-3.8-flash",
  "input": "Split this transcript into semantic chapters … [0] 00:00:00 S1: Welcome back …",
  "response_format": {"type": "text", "mime_type": "application/json", "schema": {"type": "object", "properties": {"chapters": {…}}}},
  "store": false
}
```

The JSON is the `text` of the `model_output` step's text content. See `CHAPTER_SCHEMA` in the script.

## 5. Limits and incompatibilities

| Limit | Value |
|---|---|
| Audio per request | 1 hour. **30 minutes with diarization or word timestamps on**, so the script splits at about 25 minutes |
| Speakers | Up to 8. Google calls 3 or more experimental |
| Languages | 85+, auto-detected. Codes are listed in the transcribe doc |
| `smart` mode | Can't be combined with diarization or timestamps |
| `custom_vocabulary` | Can't be combined with diarization or timestamps |
| Batch / Flex / caching | Not supported for this model |

## 6. Prices

Standard paid tier, checked 2026-10-20. The free tier is free of charge but rate-limited.

| Model | Input per 1M tokens | Output per 1M tokens | Effective |
|---|---|---|---|
| `gemini-3.5-transcribe` | $2.00 (audio) | $12.00 | about $0.003/min in + $0.002/min out = **about $0.005 per minute** |
| `gemini-3.8-flash` (chapters) | $0.75 until 2026-12-31, then $1.50 | $3.75, then $7.50 | well under $0.01 for an hour-long transcript |
| `gemini-3.5-transcribe-live` | $3.50 | $21.00 | not used |

The test clip (44 s) cost $0.0068 in total, chapters included. Prices live in `config.env` so they can be updated without code changes.

## 7. Raw curl example

```bash
KEY=$(grep '^GEMINI_API_KEY=' ~/.config/gemini/.env | cut -d= -f2-)   # in a script only; never echo it
ffmpeg -i talk.mp4 -vn -ac 1 -ar 16000 -c:a flac /tmp/a.flac
N=$(stat -c%s /tmp/a.flac)
URL=$(curl -s -D - -o /dev/null "https://generativelanguage.googleapis.com/upload/v1beta/files" \
  -H "x-goog-api-key: $KEY" -H "X-Goog-Upload-Protocol: resumable" -H "X-Goog-Upload-Command: start" \
  -H "X-Goog-Upload-Header-Content-Length: $N" -H "X-Goog-Upload-Header-Content-Type: audio/flac" \
  -H "Content-Type: application/json" -d '{"file":{"display_name":"a"}}' | grep -i '^x-goog-upload-url:' | cut -d' ' -f2 | tr -d '\r')
URI=$(curl -s "$URL" -H "X-Goog-Upload-Offset: 0" -H "X-Goog-Upload-Command: upload, finalize" --data-binary @/tmp/a.flac | jq -r .file.uri)
curl -s https://generativelanguage.googleapis.com/v1beta/interactions -H "x-goog-api-key: $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"gemini-3.5-transcribe\",\"input\":[{\"type\":\"audio\",\"uri\":\"$URI\",\"mime_type\":\"audio/flac\"}],
       \"generation_config\":{\"transcription_config\":{\"mode\":{\"type\":\"verbatim\",\"diarization_mode\":\"speaker\",\"timestamp_granularities\":[\"word\"]}}},\"store\":false}"
```
