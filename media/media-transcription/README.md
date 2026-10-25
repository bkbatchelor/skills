# media-transcription

Transcribes a local audio or video file into a standard transcription package with one command, using Google's Gemini 3.5 Transcribe API and ffmpeg.

## What you get

For `talk.mp4`, a `talk.transcript/` folder containing:

| File | Contents |
|------|----------|
| `talk.transcript.md` | Readable transcript with chapters, speaker turns and timestamps |
| `talk.words.json` | Every word with start/end seconds, speaker and turn |
| `talk.speakers.json` | Speakers and turns |
| `talk.chapters.json` | Semantic chapters with titles, summaries and keywords |
| `talk.srt`, `talk.vtt` | Captions |
| `manifest.json` | Source hash, models, settings, warnings and cost |
| `_raw/` | Untouched API responses, so the package can be rebuilt for free |

A package for an unchanged file is reused; pass `--force` to redo it.

## How it works

1. ffmpeg converts the input to mono 16 kHz FLAC.
2. Media over about 26 minutes is split near silences, and timestamps are shifted back onto the original timeline.
3. Each part is uploaded to the Gemini Files API and transcribed with speaker labels and word timestamps.
4. A second model writes the chapters.

## Triggers

Gives an audio or video file and asks for a transcript, captions, chapters, speaker labels, or meeting notes. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use media-transcription
# or link it manually
ln -s ~/Projects/skills/media/media-transcription ~/.claude/skills/media-transcription
```

## Requirements

- `ffmpeg` and `python3`
- A `GEMINI_API_KEY` in `~/.config/gemini/.env`. Get one at https://aistudio.google.com/apikey

## Usage

```bash
scripts/transcribe.py MEDIA [options]
```

Run `scripts/transcribe.py --help` for the options.

## Configuration

Defaults live in `config.env`: the transcription and chapter models, the env file, the chunk length (`MEDIA_TRANSCRIPTION_CHUNK_SECONDS`) and per-token prices used for cost estimates.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions |
| `scripts/transcribe.py` | The transcription command |
| `references/format.md` | Exact schema of every package file |
| `references/api.md` | API details |
| `config.env` | Saved preferences |
