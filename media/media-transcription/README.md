# media-transcription

Turns a local audio or video file into a transcription package with one command. A package is a folder of related files. The skill uses Google's Gemini 3.5 Transcribe model, through the Gemini API, and ffmpeg. ffmpeg is a tool that converts audio and video files.

## What you get

For `talk.mp4`, the skill makes a `talk.transcript/` folder with these files:

| File | Contents |
|------|----------|
| `talk.transcript.md` | A readable transcript, with chapters, speaker turns and timestamps. A timestamp is the point in the recording where the words are spoken. |
| `talk.words.json` | Every word, with its start and end time in seconds, its speaker and its turn. JSON is a structured text format. |
| `talk.speakers.json` | The speakers and their turns |
| `talk.chapters.json` | The chapters, with titles, summaries and keywords |
| `talk.srt`, `talk.vtt` | Caption files, in two common formats |
| `manifest.json` | A record of the source file's fingerprint (hash), the models used, the settings, the warnings and the cost |
| `_raw/` | The untouched API responses. The package can be rebuilt from them without paying the API again. |

If the file has not changed, the skill reuses the existing package. Add `--force` to build it again.

## How it works

1. ffmpeg converts the input to mono 16 kHz FLAC. Mono means one audio channel. 16 kHz is a sample rate of 16,000 samples per second. FLAC is a lossless audio format.
2. A recording longer than about 26 minutes is cut into parts at quiet gaps. The timestamps are shifted so they match the original recording.
3. Each part is uploaded to Google's Gemini Files API, a service that stores files for the model to read. The model transcribes each part with speaker labels (who is talking) and word timestamps.
4. A second model writes the chapters.

## Triggers

It starts when you give it an audio or video file and ask for a transcript, captions, chapters, speaker labels or meeting notes. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use media-transcription
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/media/media-transcription ~/.claude/skills/media-transcription
```

## Requirements

- `ffmpeg` and `python3`.
- A `GEMINI_API_KEY` in `~/.config/gemini/.env`. The key is a secret string that gives this tool access to the Gemini API. Get one at https://aistudio.google.com/apikey

## Usage

Run this in a terminal. Replace `MEDIA` with the path to your audio or video file.

```bash
scripts/transcribe.py MEDIA [options]
```

Run `scripts/transcribe.py --help` to see every option.

## Configuration

Defaults live in `config.env`, a settings file in the skill folder. It sets:

- the transcription model and the chapter model
- the env file, which holds your key
- the length of each part, in seconds (`MEDIA_TRANSCRIPTION_CHUNK_SECONDS`)
- the price per token, which the skill uses for cost estimates

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions |
| `scripts/transcribe.py` | The transcription command |
| `references/format.md` | The exact format of every file in the package |
| `references/api.md` | API details |
| `config.env` | Saved settings |
