---
name: media-transcription
description: Transcribes a local audio or video file into a transcription package (Markdown transcript, word-level timestamp JSON, speaker labels, chapters, SRT/VTT captions) with Gemini 3.5 Transcribe and ffmpeg. Use whenever the user gives a media file (mp3, wav, m4a, flac, ogg, mp4, mov, mkv, webm, a voice memo, podcast, meeting or Zoom recording, interview, lecture) and asks for a transcript, captions, subtitles, chapters, timestamps, "who said what", meeting notes or a summary that needs the words first, or to make it searchable. Also use when another skill needs the words or timings of a recording; read the package instead of calling a speech API. Not for live dictation, text-to-speech, or files that already have a transcript package next to them.
metadata:
  version: 1.0.3
---

# Media Transcription

One command turns a recording into a transcription package next to it:

```bash
~/Projects/skills/media/media-transcription/scripts/transcribe.py ~/Videos/standup-2026-10-19.mp4
```

The script is in this skill's `scripts/` folder. Use the absolute path of the directory this SKILL.md was loaded from, since the skill may be linked into several places. It needs `python3` (standard library only), `ffmpeg` and `ffprobe`.

## Triggers

Use when the user gives a media file (mp3, wav, m4a, flac, ogg, opus, mp4, mov, mkv, webm, a voice memo, podcast, meeting or Zoom recording, interview, lecture, screen recording) and asks for a transcript, captions, subtitles, chapters, timestamps, speaker labels, "who said what", meeting notes or a summary that needs the words first, or to make it searchable. Also use when another skill needs the words or timings of a recording.

Skip when:
- The request is live microphone dictation, streaming, or text-to-speech.
- A transcript package already sits next to the file. Read it instead.

## Saved preferences

These live in `config.env` next to this file and are read on every run. To change a default permanently, edit `config.env`.

| Setting | Value |
|---|---|
| Speech model | `gemini-3.5-transcribe` (Gemini 3.5 Transcribe, file variant) |
| Chapter model | `gemini-3.8-flash` |
| Output folder | `<media folder>/<stem>.transcript/`, or `-o DIR` |
| API key | `GEMINI_API_KEY=` line in `~/.config/gemini/.env` (shared with image-gateway) |

The script reads the key from the env file on every run and never copies it anywhere else. Don't print it, `cat` the env file, put it on a command line, or write it into this skill or any output. If the key is missing, the script says so. Tell the user to get a key at https://aistudio.google.com/apikey and add `GEMINI_API_KEY=...` to that file in their editor (`chmod 600`), not by pasting it into the chat.

## What the script does

1. **Extracts the audio with ffmpeg.** Every input, video or audio, becomes mono 16 kHz FLAC in a temp folder: first audio track only, video and cover art dropped. This gives the API the same input every time and keeps uploads small. Files with no audio stream are rejected.
2. **Splits long media.** With speaker labels and word timestamps on, the API accepts at most 30 minutes per request. Anything over about 26 minutes is cut near silences into ~25-minute parts, and timestamps are shifted back onto the original timeline.
3. **Uploads each part to the Gemini Files API, then transcribes it.** The request uses `gemini-3.5-transcribe` in `verbatim` mode with speaker diarization and word timestamps. The uploaded file is deleted right after.
4. **Writes chapters.** The finished transcript goes to `gemini-3.8-flash`, which returns semantic chapters as structured JSON. The script then snaps each chapter to a turn boundary.
5. **Writes the package** and prints one JSON summary line to stdout. Progress goes to stderr.

It skips work when a package for the same file already exists (matched by file hash). `--force` redoes it.

## The output package

For `talk.mp4`, everything goes in `talk.transcript/`, and every file name starts with the media file's name:

| File | Contents |
|---|---|
| `talk.transcript.md` | Readable transcript: header, chapter list, then speaker turns grouped under chapter headings, each with `[HH:MM:SS]` |
| `talk.words.json` | Every word with `start`/`end` in seconds, `speaker` and `turn` |
| `talk.speakers.json` | Speakers (`S1`, `S2`, … with label, name, talk time) and turns (one speaker's continuous speech) |
| `talk.chapters.json` | Chapters with title, summary, keywords, start/end seconds, turn range |
| `talk.srt`, `talk.vtt` | Captions, max ~6 s and 84 characters per cue, with speaker names |
| `manifest.json` | Source path and hash, models, settings, parts, warnings, cost, file list |
| `_raw/` | Untouched API responses, so the package can be rebuilt without paying again |

The exact schema of each file is in `references/format.md`. Read it before writing code that consumes the package.

## Usage

```
transcribe.py MEDIA [options]
  -o DIR            package folder (default <media dir>/<stem>.transcript/)
  -l CODE           BCP-47 language hint, repeatable, e.g. -l en-US -l es-US (default: auto-detect)
  --speakers MAP    'S1=Maya Chen,S2=Sam Ortiz' sets display names
  --rerender        rebuild every file from _raw/ (no API cost). Use with --speakers
  --rechapter       with --rerender, also regenerate chapters (one cheap Flash call)
  --no-chapters     skip the chapter call (one chapter covers the whole recording)
  --force           transcribe again even if the package exists
  --dry-run         print the transcribe request body, make no calls
```

Summary line on success:

```json
{"package_dir": ".../talk.transcript", "skipped_existing": false, "files": {"transcript_md": ".../talk.transcript.md", "words": "...", ...}, "duration_s": 44.16, "words": 111, "turns": 7, "speakers": 2, "chapters": 2, "cost_usd": 0.0068, "warnings": []}
```

## How to handle a request

1. **Run it once** on the path the user gave. Don't ask them to confirm routine runs. A minute of audio costs about half a cent, so an hour costs about $0.30. Mention the estimate before running anything over 2 hours or a batch of files. Add `-l` only when the user names the language or the audio clearly isn't in the language auto-detection would guess.
2. **Name the speakers if you can.** The API labels speakers by voice, not by name. Read the start of `<stem>.transcript.md`. If the conversation makes names obvious ("Thanks, Sam"), or the user tells you them, run `--rerender --speakers 'S1=…,S2=…'`. That's free, and it updates every file. If you're guessing, tell the user who you think S1 and S2 are rather than applying names silently.
3. **Answer what they asked.** For a transcript, give the path to the `.md` and a short excerpt or summary. For captions, give the `.srt`/`.vtt` paths. For chapters, give the chapter list with timestamps. For "searchable", point to `words.json` for exact timestamps and the `.md` for grep and reading. Always give the package folder path.
4. **Surface warnings.** If `warnings` is non-empty, say so: speakers may swap where long media was split, or chapter generation failed and can be retried with `--rerender --rechapter`.

If the user wants something the package doesn't hold (a summary, action items, quotes, a clip list), produce it from the package files. Don't call the speech API again.

## Known behavior and limits

- **Speaker IDs.** The API returns labels like `spk:0` (not `spk_1` as Google's docs show). The package always uses `S1`, `S2`, … in order of first appearance, and keeps the original label in `speakers.json` → `api_labels`. Diarization handles up to 8 speakers, and Google calls 3 or more experimental, so spot-check group recordings.
- **Split parts.** Each part is diarized separately, and speakers are matched across parts by the API's label. That held in testing, but it isn't guaranteed, so the warning gives the split times to check.
- **Custom vocabulary is not used.** The API rejects `custom_vocabulary` combined with diarization or word timestamps, and the package needs both. If jargon keeps coming out wrong, fix it in the Markdown for the user, or tell them a vocabulary-biased plain-text run is possible but has no timestamps or speakers.
- **Verbatim, not smart mode.** Filler words stay in. `smart` mode can't do timestamps or speakers. For a cleaned-up read, edit from the `.md`.
- **No speech.** Silent or music-only files exit with an error, and the raw response is kept in `_raw/`.
- **Speed.** About 10 seconds end-to-end for a 45-second clip in testing, most of it the chapter call.
- **Errors.** 429 and 5xx responses are retried automatically (5 s, 15 s, 40 s). Don't add your own retry loop. A 400 usually means a bad `-l` code. A 429 that persists is quota or billing, so send the user to https://aistudio.google.com/usage.

For the request and response shapes, prices, and a raw curl example, read `references/api.md`.

## For editing, research and other skills

The package is an input format other skills rely on: video editors cutting on word timestamps, research skills quoting with timecodes, note-takers summarizing by chapter. That only works if the shape never drifts, so:

- Consume the package through the files and fields in `references/format.md`. Check `schema_version` (currently `1.0`) and treat an unknown major version as unsupported.
- Don't edit `words.json`, `speakers.json` or `chapters.json` by hand. Hand edits are lost on `--rerender`, and they can break the links between words, turns and chapters. Change names with `--speakers`. Put derived artifacts (summaries, clip lists, notes) in your own files inside the package folder, with names like `<stem>.summary.md`.
- If you're another skill and need a recording transcribed, run this script rather than writing your own speech-to-text code. Check for an existing `<stem>.transcript/manifest.json` first, since the script reuses it for free anyway.
- If the format really must change, change it here: bump `SCHEMA_VERSION` in the script, update `references/format.md`, and say what changed. Don't fork the format in another skill.
