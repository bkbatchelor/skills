# Transcription package format, schema 1.0

This is the contract between `media-transcription` and every skill that reads its output. All times are **seconds as floats** on the original media's timeline (millisecond precision), even when the audio was transcribed in parts. All JSON is UTF-8 with 2-space indentation.

## Contents
1. Folder layout and naming
2. manifest.json
3. `<stem>.words.json`
4. `<stem>.speakers.json`
5. `<stem>.chapters.json`
6. `<stem>.transcript.md`
7. Captions
8. Invariants consumers can rely on
9. Versioning

## 1. Folder layout and naming

`<stem>` is the media file name without its extension. By default the folder sits next to the media.

```
<media dir>/
├── <stem>.<ext>
└── <stem>.transcript/
    ├── manifest.json
    ├── <stem>.transcript.md
    ├── <stem>.words.json
    ├── <stem>.speakers.json
    ├── <stem>.chapters.json
    ├── <stem>.srt
    ├── <stem>.vtt
    └── _raw/
        ├── transcribe-00.json   (one per part, untouched API response)
        └── chapters.json        (untouched chapter-model response)
```

Find a package by its manifest, not by guessing names: `manifest.json` → `files` maps a role to a file name inside the folder.

## 2. manifest.json

```json
{
  "schema_version": "1.0",
  "package": "media-transcription",
  "created": "2026-10-20T01:37:15-04:00",
  "source": {"path": "/abs/path/talk.mp4", "sha256": "…", "size_bytes": 2125798, "duration_s": 44.16, "had_video": true},
  "models": {"transcribe": "gemini-3.5-transcribe", "chapters": "gemini-3.8-flash"},
  "settings": {"mode": "verbatim", "diarization": true, "word_timestamps": true, "language_codes": []},
  "chunks": [{"i": 0, "start": 0.0, "duration_s": 44.16, "raw": "_raw/transcribe-00.json"}],
  "warnings": [],
  "cost": {"usd": 0.0068, "is_estimate": true, "transcribe_tokens": {"input": 1105, "output": 151}},
  "seconds": 10.3,
  "files": {"transcript_md": "talk.transcript.md", "words": "talk.words.json", "speakers": "talk.speakers.json",
            "chapters": "talk.chapters.json", "captions_srt": "talk.srt", "captions_vtt": "talk.vtt"},
  "counts": {"words": 111, "turns": 7, "speakers": 2, "chapters": 2}
}
```

`models.chapters` is `null` when chapters were skipped or failed. In that case there is one chapter covering the whole recording.

## 3. `<stem>.words.json`

```json
{
  "schema_version": "1.0", "source": "/abs/path/talk.mp4", "duration_s": 44.16, "time_unit": "seconds",
  "words": [
    {"i": 0, "text": "Welcome", "start": 0.1, "end": 0.4, "speaker": "S1", "turn": 0},
    {"i": 4, "text": "Notes.", "start": 1.1, "end": 1.7, "speaker": "S1", "turn": 0}
  ]
}
```

- `text` is the word as displayed, **with attached punctuation** (`"Notes."`, `"Yeah,"`). Numbers come out normalized, for example `"14"` and `"1.32"`. Joining `text` values with single spaces reproduces the turn text exactly.
- `i` is the index into `words`. `speaker` is a speaker `id`, and `turn` is a turn `i`.

## 4. `<stem>.speakers.json`

```json
{
  "schema_version": "1.0", "source": "…", "duration_s": 44.16,
  "speakers": [
    {"id": "S1", "label": "Maya", "name": "Maya", "api_labels": ["spk:0"], "word_count": 56, "talk_time_s": 18.1, "first_start": 0.1}
  ],
  "turns": [
    {"i": 0, "speaker": "S1", "start": 0.1, "end": 6.6, "word_range": [0, 19], "text": "Welcome back to Build Notes. …"}
  ]
}
```

- `id` is stable for a package: `S1`, `S2`, … in order of first speech. Use `id` in data. Use `label` for display: it is `name` if one was set with `--speakers`, otherwise `"Speaker N"`.
- A **turn** is one speaker's continuous speech. A new turn starts when the speaker changes or after a pause longer than 2.0 s. `word_range` is inclusive `[first, last]` word indices.

## 5. `<stem>.chapters.json`

```json
{
  "schema_version": "1.0", "source": "…", "duration_s": 44.16, "model": "gemini-3.8-flash",
  "chapters": [
    {"i": 0, "title": "Migrating Deploys to GitHub Actions", "start": 0.0, "end": 27.0,
     "start_turn": 0, "end_turn": 3, "summary": "…", "keywords": ["Jenkins", "GitHub Actions", "OIDC"]}
  ]
}
```

Chapters are contiguous, in order, and cover the whole recording. The first starts at `0.0`, each chapter's `end` equals the next chapter's `start`, and the last ends at `duration_s`. A chapter always begins on a turn boundary (`start` = that turn's start, except chapter 0).

## 6. `<stem>.transcript.md`

Meant for people and for grep. Its layout is stable, so a consumer can rely on it:

```markdown
# <stem>

- **Source:** `<abs path>`
- **Duration:** HH:MM:SS
- **Transcribed:** YYYY-MM-DD with `<model>` (verbatim, speaker diarization, word timestamps)
- **Speakers:** <label> (S1), <label> (S2)

> **Note:** <warnings, only if any>

## Chapters

1. **HH:MM:SS** <title>: <summary>

## Transcript

### HH:MM:SS · <chapter title>

**<speaker label>** `[HH:MM:SS]`
<turn text>
```

Each turn is two lines and a blank line. Timestamps are always zero-padded `HH:MM:SS`, rounded to the nearest second. Use the JSON files for sub-second precision.

## 7. Captions

- `<stem>.srt`: standard SRT. When the speaker changes, the cue text starts with `<label>: `.
- `<stem>.vtt`: WebVTT. Every cue carries a voice tag, `<v <label>>text`.

Cues never span two turns, last at most about 6 s, and hold at most 84 characters.

## 8. Invariants consumers can rely on

- Every word belongs to exactly one turn, and every turn to exactly one chapter.
- `words[i].i == i`, `turns[i].i == i` and `chapters[i].i == i`.
- Times never decrease along `words`, and `start <= end` for every item.
- The same media file (same sha256) re-run without `--force` returns the existing package unchanged.
- `--rerender` rebuilds every derived file from `_raw/` and keeps the speaker names and chapters, so derived files are disposable but `_raw/` is not.

## 9. Versioning

`schema_version` is `MAJOR.MINOR`.

- A **minor** bump only adds fields. Consumers must ignore fields they don't know.
- A **major** bump renames, removes or changes the meaning of a field or file. Consumers should refuse a major version they weren't written for.

Any change goes here first, then into `SCHEMA_VERSION` in `scripts/transcribe.py`.
