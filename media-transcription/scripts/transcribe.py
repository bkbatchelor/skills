#!/usr/bin/env python3
"""Turn a local audio or video file into a transcription package.

Uses Gemini 3.5 Transcribe (Interactions API) for words, timestamps and
speakers, and a Gemini Flash text model for semantic chapters. Standard
library only; needs ffmpeg and ffprobe on PATH.

    transcribe.py MEDIA [options]          see --help

Prints one JSON summary line on stdout. Progress and errors go to stderr.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

SCHEMA_VERSION = "1.0"
API = "https://generativelanguage.googleapis.com"
SKILL_DIR = Path(__file__).resolve().parent.parent
TURN_PAUSE_S = 2.0          # a silence this long starts a new turn
CUE_MAX_S, CUE_MAX_CHARS = 6.0, 84


def log(msg):
    print(f"media-transcription: {msg}", file=sys.stderr, flush=True)


def die(msg, code=1) -> NoReturn:
    log(msg)
    sys.exit(code)


# --- config and key ----------------------------------------------------------

def read_env_file(path):
    out = {}
    try:
        for line in Path(path).expanduser().read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip().removeprefix("export ").strip()] = v.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return out


def load_config():
    cfg = read_env_file(SKILL_DIR / "config.env")
    cfg.update({k: v for k, v in os.environ.items() if k.startswith("MEDIA_TRANSCRIPTION_")})
    return cfg


def load_key(cfg):
    env_file = cfg.get("MEDIA_TRANSCRIPTION_ENV_FILE", "~/.config/gemini/.env")
    key = read_env_file(env_file).get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        die(f"no GEMINI_API_KEY found in {env_file}. Get a key at https://aistudio.google.com/apikey "
            f"and add the line GEMINI_API_KEY=... to that file in an editor (chmod 600).")
    return key


# --- HTTP --------------------------------------------------------------------

class Gemini:
    def __init__(self, key):
        self.key = key

    def _req(self, url, body=None, headers=None, method=None):
        h = {"x-goog-api-key": self.key, **(headers or {})}
        delays = [5, 15, 40]
        while True:
            req = urllib.request.Request(url, body, h, method=method)
            try:
                return urllib.request.urlopen(req, timeout=900)
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                if e.code in (429, 500, 502, 503, 504) and delays:
                    d = delays.pop(0)
                    log(f"HTTP {e.code}, retrying in {d}s")
                    time.sleep(d)
                    continue
                try:
                    text = json.loads(text)["error"]["message"]
                except Exception:
                    text = text[:1500]
                die(f"HTTP {e.code} from {url.split('?')[0]}: {text}")
            except urllib.error.URLError as e:
                if delays:
                    d = delays.pop(0)
                    log(f"network error ({e.reason}), retrying in {d}s")
                    time.sleep(d)
                    continue
                die(f"network error: {e.reason}")

    def json(self, url, payload=None, method=None):
        body = json.dumps(payload).encode() if payload is not None else None
        hdr = {"Content-Type": "application/json"} if body else {}
        return json.load(self._req(url, body, hdr, method))

    def upload(self, path, mime):
        size = path.stat().st_size
        start = self._req(f"{API}/upload/v1beta/files",
                          json.dumps({"file": {"display_name": path.name}}).encode(),
                          {"X-Goog-Upload-Protocol": "resumable",
                           "X-Goog-Upload-Command": "start",
                           "X-Goog-Upload-Header-Content-Length": str(size),
                           "X-Goog-Upload-Header-Content-Type": mime,
                           "Content-Type": "application/json"})
        url = start.headers["X-Goog-Upload-URL"]
        with open(path, "rb") as fh:
            f = json.load(self._req(url, fh.read(), {"X-Goog-Upload-Offset": "0",
                                                     "X-Goog-Upload-Command": "upload, finalize"}))["file"]
        for _ in range(120):
            if f.get("state", "ACTIVE") == "ACTIVE":
                return f
            if f.get("state") == "FAILED":
                die(f"Files API could not process {path.name}: {f.get('error')}")
            time.sleep(2)
            f = self.json(f"{API}/v1beta/{f['name']}")
        die("uploaded file never became ACTIVE")

    def delete(self, name):
        try:
            self._req(f"{API}/v1beta/{name}", method="DELETE")
        except SystemExit:
            log(f"could not delete {name}; it expires on its own after 48 hours")

    def interact(self, body):
        return self.json(f"{API}/v1beta/interactions", body)


# --- media -------------------------------------------------------------------

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(path)], capture_output=True, text=True)
    if out.returncode:
        die(f"ffprobe cannot read {path}: {out.stderr.strip()[:300]}")
    info = json.loads(out.stdout)
    kinds = {s.get("codec_type") for s in info.get("streams", [])
             if not s.get("disposition", {}).get("attached_pic")}
    if "audio" not in kinds:
        die(f"{path} has no audio stream, so there is nothing to transcribe")
    return float(info["format"].get("duration") or 0), "video" in kinds


def extract_audio(src, dst, start=None, length=None):
    """Mono 16 kHz FLAC: lossless, small, accepted by the API, same for every input."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += ["-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        die(f"ffmpeg failed: {r.stderr.strip()[:500]}")


def chunk_bounds(audio, duration, target):
    """Cut points near silences so chunks stay under the API's 30-minute limit."""
    if duration <= target + 60:
        return [(0.0, duration)]
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(audio), "-af",
                        "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    mids = [(a + b) / 2 for a, b in zip(starts, ends)]
    cuts, pos = [], 0.0
    while duration - pos > target + 60:
        aim = pos + target
        near = [m for m in mids if aim - 120 <= m <= min(aim + 60, pos + 1740)]
        cut = min(near, key=lambda m: abs(m - aim)) if near else aim
        cuts.append(cut)
        pos = cut
    edges = [0.0, *cuts, duration]
    return list(zip(edges[:-1], [b - a for a, b in zip(edges[:-1], edges[1:])]))


# --- transcription -----------------------------------------------------------

def transcribe_body(model, uri, langs):
    tc = {"mode": {"type": "verbatim", "diarization_mode": "speaker",
                   "timestamp_granularities": ["word"]}}
    if langs:
        tc["language_codes"] = langs
    return {"model": model,
            "input": [{"type": "audio", "uri": uri, "mime_type": "audio/flac"}],
            "generation_config": {"transcription_config": tc},
            "store": False}


def secs(v):
    if v is None:
        return None
    return float(str(v).rstrip("s") or 0)


def words_from_response(resp, offset, chunk_index):
    words, texts = [], []
    for step in resp.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for c in step.get("content", []):
            if c.get("type") != "text":
                continue
            texts.append(c.get("text", ""))
            for a in c.get("annotations", []) or []:
                if a.get("type") != "word_info":
                    continue
                s, e = secs(a.get("start_offset")), secs(a.get("end_offset"))
                words.append({"text": a.get("text", "").strip(),
                              "start": round((s or 0) + offset, 3),
                              "end": round((e if e is not None else s or 0) + offset, 3),
                              "api_speaker": a.get("speaker") or "unknown",
                              "chunk": chunk_index})
    return [w for w in words if w["text"]], " ".join(texts)


# --- package building --------------------------------------------------------

def hms(t):
    t = int(round(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def ts(t, sep):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}{sep}{ms % 1000:03d}"


def assign_speakers(words, names):
    """Package speaker IDs are S1, S2, ... in order of first appearance."""
    ids = {}
    for w in words:
        if w["api_speaker"] not in ids:
            ids[w["api_speaker"]] = f"S{len(ids) + 1}"
        w["speaker"] = ids[w["api_speaker"]]
    speakers = []
    for api, sid in ids.items():
        sw = [w for w in words if w["speaker"] == sid]
        speakers.append({"id": sid,
                         "label": names.get(sid) or f"Speaker {sid[1:]}",
                         "name": names.get(sid),
                         "api_labels": [api],
                         "word_count": len(sw),
                         "talk_time_s": round(sum(w["end"] - w["start"] for w in sw), 1),
                         "first_start": sw[0]["start"]})
    return speakers


def build_turns(words):
    turns = []
    for i, w in enumerate(words):
        prev = words[i - 1] if i else None
        if (not prev or w["speaker"] != prev["speaker"] or w["start"] - prev["end"] > TURN_PAUSE_S
                or w["chunk"] != prev["chunk"] and w["start"] - prev["end"] > 0.5):
            turns.append({"i": len(turns), "speaker": w["speaker"], "start": w["start"],
                          "end": w["end"], "word_range": [i, i], "text": ""})
        t = turns[-1]
        w["turn"] = t["i"]
        t["end"], t["word_range"][1] = w["end"], i
    for t in turns:
        a, b = t["word_range"]
        t["text"] = " ".join(w["text"] for w in words[a:b + 1])
    return turns


CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {"chapters": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "start_turn": {"type": "integer", "description": "Index of the turn where this chapter begins."},
            "title": {"type": "string", "description": "3-8 word topic title, no timestamp."},
            "summary": {"type": "string", "description": "1-2 sentences on what is covered."},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["start_turn", "title", "summary", "keywords"]}}},
    "required": ["chapters"],
}


def make_chapters(gem, model, turns, duration):
    lines = "\n".join(f"[{t['i']}] {hms(t['start'])} {t['speaker']}: {t['text']}" for t in turns)
    minutes = max(duration / 60, 0.1)
    guide = ("Use 1-3 chapters." if minutes < 3 else
             f"Aim for roughly one chapter per 3-8 minutes (about {max(2, round(minutes / 5))}), "
             "following real topic shifts rather than equal lengths.")
    prompt = ("Split this transcript into semantic chapters: contiguous sections that each cover one "
              "topic, in order, with no gaps. Each line is '[turn index] HH:MM:SS speaker: text'. "
              f"The first chapter must start at turn 0. {guide} Titles are specific to the content "
              "(not 'Introduction' unless it is one). Keywords are 2-6 searchable terms, names or "
              "products actually said.\n\nTRANSCRIPT\n" + lines)
    body = {"model": model, "input": prompt, "store": False,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": CHAPTER_SCHEMA}}
    resp = gem.interact(body)
    text = "".join(c.get("text", "") for s in resp.get("steps", []) if s.get("type") == "model_output"
                   for c in s.get("content", []) if c.get("type") == "text")
    try:
        raw = json.loads(text)["chapters"]
    except (ValueError, KeyError) as e:
        raise RuntimeError(f"chapter model returned unparseable JSON ({e})") from None
    return normalize_chapters(raw, turns, duration), resp


def normalize_chapters(raw, turns, duration):
    seen, chs = set(), []
    for c in sorted(raw, key=lambda c: c.get("start_turn", 0)):
        st = min(max(int(c.get("start_turn", 0)), 0), len(turns) - 1)
        if st in seen:
            continue
        seen.add(st)
        chs.append({"title": c.get("title", "").strip() or "Untitled", "summary": c.get("summary", "").strip(),
                    "keywords": c.get("keywords", []), "start_turn": st})
    if not chs or chs[0]["start_turn"] != 0:
        chs.insert(0, {"title": "Opening", "summary": "", "keywords": [], "start_turn": 0})
        if len(chs) > 1 and chs[1]["start_turn"] == 0:
            chs.pop(0)
    for i, c in enumerate(chs):
        nxt = chs[i + 1]["start_turn"] if i + 1 < len(chs) else len(turns)
        c.update(i=i, start=0.0 if i == 0 else turns[c["start_turn"]]["start"],
                 end=turns[nxt]["start"] if nxt < len(turns) else round(duration, 3),
                 end_turn=nxt - 1)
    return [{k: c[k] for k in ("i", "title", "start", "end", "start_turn", "end_turn", "summary", "keywords")}
            for c in chs]


def single_chapter(turns, duration):
    return [{"i": 0, "title": "Full recording", "start": 0.0, "end": round(duration, 3), "start_turn": 0,
             "end_turn": len(turns) - 1, "summary": "", "keywords": []}]


def cues(words, turns, labels):
    out = []
    for t in turns:
        a, b = t["word_range"]
        cur = []
        for w in words[a:b + 1]:
            if cur and (w["end"] - cur[0]["start"] > CUE_MAX_S
                        or len(" ".join(x["text"] for x in cur)) + len(w["text"]) > CUE_MAX_CHARS):
                out.append(cur)
                cur = []
            cur.append(w)
            if w["text"][-1] in ".?!" and w["end"] - cur[0]["start"] > 2.5:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
    res, last = [], None
    for c in out:
        spk = c[0]["speaker"]
        res.append({"start": c[0]["start"], "end": max(c[-1]["end"], c[0]["start"] + 0.5),
                    "speaker": labels[spk], "new_speaker": spk != last,
                    "text": " ".join(w["text"] for w in c)})
        last = spk
    for x, y in zip(res, res[1:]):
        x["end"] = min(x["end"], y["start"])
    return res


def write_captions(pkg, stem, cue_list):
    srt, vtt = [], ["WEBVTT", ""]
    for n, c in enumerate(cue_list, 1):
        prefix = f"{c['speaker']}: " if c["new_speaker"] else ""
        srt += [str(n), f"{ts(c['start'], ',')} --> {ts(c['end'], ',')}", prefix + c["text"], ""]
        vtt += [f"{ts(c['start'], '.')} --> {ts(c['end'], '.')}", f"<v {c['speaker']}>{c['text']}", ""]
    (pkg / f"{stem}.srt").write_text("\n".join(srt))
    (pkg / f"{stem}.vtt").write_text("\n".join(vtt))


def write_markdown(pkg, stem, meta, speakers, turns, chapters):
    labels = {s["id"]: s["label"] for s in speakers}
    L = [f"# {stem}", "",
         f"- **Source:** `{meta['source']['path']}`",
         f"- **Duration:** {hms(meta['source']['duration_s'])}",
         f"- **Transcribed:** {meta['created'][:10]} with `{meta['models']['transcribe']}` "
         "(verbatim, speaker diarization, word timestamps)",
         "- **Speakers:** " + ", ".join(f"{s['label']} ({s['id']})" for s in speakers), ""]
    if meta.get("warnings"):
        L += ["> **Note:** " + " ".join(meta["warnings"]), ""]
    L += ["## Chapters", ""]
    for c in chapters:
        L.append(f"{c['i'] + 1}. **{hms(c['start'])}** {c['title']}" + (f": {c['summary']}" if c["summary"] else ""))
    L += ["", "## Transcript", ""]
    by_start = {c["start_turn"]: c for c in chapters}
    for t in turns:
        if t["i"] in by_start:
            c = by_start[t["i"]]
            L += [f"### {hms(c['start'])} · {c['title']}", ""]
        L += [f"**{labels[t['speaker']]}** `[{hms(t['start'])}]`", t["text"], ""]
    (pkg / f"{stem}.transcript.md").write_text("\n".join(L).rstrip() + "\n")


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def render(pkg, stem, meta, words, chapters, names):
    """Write every derived file from words + chapters. Safe to re-run (--rerender)."""
    for w in words:
        w.pop("speaker", None)
        w.pop("turn", None)
    speakers = assign_speakers(words, names)
    turns = build_turns(words)
    if chapters is None:
        chapters = single_chapter(turns, meta["source"]["duration_s"])
    labels = {s["id"]: s["label"] for s in speakers}
    files = {"transcript_md": f"{stem}.transcript.md", "words": f"{stem}.words.json",
             "speakers": f"{stem}.speakers.json", "chapters": f"{stem}.chapters.json",
             "captions_srt": f"{stem}.srt", "captions_vtt": f"{stem}.vtt"}
    head = {"schema_version": SCHEMA_VERSION, "source": meta["source"]["path"],
            "duration_s": meta["source"]["duration_s"]}
    dump(pkg / files["words"], {**head, "time_unit": "seconds", "words": [
        {"i": i, "text": w["text"], "start": w["start"], "end": w["end"], "speaker": w["speaker"], "turn": w["turn"]}
        for i, w in enumerate(words)]})
    dump(pkg / files["speakers"], {**head, "speakers": speakers, "turns": turns})
    dump(pkg / files["chapters"], {**head, "model": meta["models"].get("chapters"), "chapters": chapters})
    write_captions(pkg, stem, cues(words, turns, labels))
    meta.update(files=files, counts={"words": len(words), "turns": len(turns), "speakers": len(speakers),
                                     "chapters": len(chapters)})
    write_markdown(pkg, stem, meta, speakers, turns, chapters)
    dump(pkg / "manifest.json", meta)
    return meta


# --- main --------------------------------------------------------------------

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_names(s):
    out = {}
    for part in filter(None, (s or "").split(",")):
        if "=" not in part:
            die(f"--speakers expects S1=Name,S2=Name; got {part!r}")
        k, v = part.split("=", 1)
        out[k.strip().upper()] = v.strip()
    return out


def summary(pkg, meta, skipped=False):
    print(json.dumps({"package_dir": str(pkg), "skipped_existing": skipped,
                      "files": {k: str(pkg / v) for k, v in meta["files"].items()},
                      "duration_s": meta["source"]["duration_s"], **meta["counts"],
                      "cost_usd": meta["cost"]["usd"], "warnings": meta.get("warnings", [])}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", help="local audio or video file")
    ap.add_argument("-o", "--out", help="package directory (default: <media dir>/<stem>.transcript/)")
    ap.add_argument("-l", "--lang", action="append", default=[],
                    help="BCP-47 language hint, repeatable (default: auto-detect)")
    ap.add_argument("--speakers", help="name speakers, e.g. 'S1=Maya Chen,S2=Sam Ortiz'")
    ap.add_argument("--no-chapters", action="store_true", help="skip the chapter model call")
    ap.add_argument("--rerender", action="store_true",
                    help="rebuild files from the saved raw response (no transcription cost); use with --speakers")
    ap.add_argument("--rechapter", action="store_true", help="with --rerender, also regenerate chapters")
    ap.add_argument("--force", action="store_true", help="re-transcribe even if a package already exists")
    ap.add_argument("--dry-run", action="store_true", help="print the transcribe request body; no API calls")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} is not installed (Arch: sudo pacman -S ffmpeg; macOS: brew install ffmpeg)")
    src = Path(args.media).expanduser().resolve()
    if not src.is_file():
        die(f"no such file: {src}")
    stem = src.stem
    pkg = Path(args.out).expanduser().resolve() if args.out else src.parent / f"{stem}.transcript"
    cfg = load_config()
    model = cfg.get("MEDIA_TRANSCRIPTION_MODEL", "gemini-3.5-transcribe")
    ch_model = cfg.get("MEDIA_TRANSCRIPTION_CHAPTER_MODEL", "gemini-3.8-flash")
    names = parse_names(args.speakers)
    manifest_path = pkg / "manifest.json"

    if args.dry_run:
        print(json.dumps(transcribe_body(model, "<uploaded-file-uri>", args.lang), indent=2))
        return

    if args.rerender:
        if not manifest_path.exists():
            die(f"nothing to rerender: {manifest_path} does not exist")
        meta = json.loads(manifest_path.read_text())
        words = []
        for ch in meta["chunks"]:
            resp = json.loads((pkg / ch["raw"]).read_text())
            words += words_from_response(resp, ch["start"], ch["i"])[0]
        old = {s["id"]: s for s in json.loads((pkg / meta["files"]["speakers"]).read_text())["speakers"]}
        names = {**{k: v["name"] for k, v in old.items() if v.get("name")}, **names}
        chapters = json.loads((pkg / meta["files"]["chapters"]).read_text())["chapters"]
        if args.rechapter:
            gem = Gemini(load_key(cfg))
            tmp = [{**w} for w in words]
            assign_speakers(tmp, names)
            chapters, resp = make_chapters(gem, ch_model, build_turns(tmp), meta["source"]["duration_s"])
            dump(pkg / "_raw" / "chapters.json", resp)
            meta["models"]["chapters"] = ch_model
        summary(pkg, render(pkg, stem, meta, words, chapters, names))
        return

    digest = sha256(src)
    if manifest_path.exists() and not args.force:
        meta = json.loads(manifest_path.read_text())
        if meta.get("source", {}).get("sha256") == digest and meta.get("schema_version") == SCHEMA_VERSION:
            log(f"already transcribed (same file hash): {pkg}. Use --force to redo, --rerender to rebuild.")
            summary(pkg, meta, skipped=True)
            return

    duration, has_video = probe(src)
    gem = Gemini(load_key(cfg))
    target = float(cfg.get("MEDIA_TRANSCRIPTION_CHUNK_SECONDS", 1500))
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "_raw").mkdir(exist_ok=True)
    t0 = time.time()
    warnings, words, chunks, usage_in, usage_out = [], [], [], 0, 0

    with tempfile.TemporaryDirectory(prefix="media-transcription-") as tmpd:
        tmp = Path(tmpd)
        full = tmp / "audio.flac"
        log(("extracting audio track from video" if has_video else "normalizing audio") + f" ({hms(duration)})")
        extract_audio(src, full)
        bounds = chunk_bounds(full, duration, target)
        if len(bounds) > 1:
            warnings.append(f"Audio was transcribed in {len(bounds)} parts (API limit is 30 min per request); "
                            "speaker labels are matched across parts by the API's label and may swap at "
                            + ", ".join(hms(s) for s, _ in bounds[1:]) + ". Spot-check speakers there.")
        for i, (start, length) in enumerate(bounds):
            part = full
            if len(bounds) > 1:
                part = tmp / f"part{i}.flac"
                extract_audio(full, part, start, length)
            log(f"uploading and transcribing part {i + 1}/{len(bounds)}" if len(bounds) > 1
                else "uploading and transcribing")
            f = gem.upload(part, "audio/flac")
            try:
                resp = gem.interact(transcribe_body(model, f["uri"], args.lang))
            finally:
                gem.delete(f["name"])
            raw_name = f"_raw/transcribe-{i:02d}.json"
            dump(pkg / raw_name, resp)
            w, text = words_from_response(resp, start, i)
            if not w and text.strip():
                warnings.append(f"Part {i + 1} returned text but no word timestamps.")
            words += w
            u = resp.get("usage", {})
            usage_in += u.get("total_input_tokens", 0)
            usage_out += u.get("total_output_tokens", 0) + u.get("total_thought_tokens", 0)
            chunks.append({"i": i, "start": round(start, 3), "duration_s": round(length, 3), "raw": raw_name})

    if not words:
        die(f"the API returned no words (silent or non-speech audio?). Raw response: {pkg / '_raw'}")

    p = lambda k, d: float(cfg.get(k, d))
    cost = usage_in * p("MEDIA_TRANSCRIPTION_PRICE_IN", 2) / 1e6 + usage_out * p("MEDIA_TRANSCRIPTION_PRICE_OUT", 12) / 1e6
    meta = {"schema_version": SCHEMA_VERSION, "package": "media-transcription",
            "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": {"path": str(src), "sha256": digest, "size_bytes": src.stat().st_size,
                       "duration_s": round(duration, 3), "had_video": has_video},
            "models": {"transcribe": model, "chapters": None},
            "settings": {"mode": "verbatim", "diarization": True, "word_timestamps": True,
                         "language_codes": args.lang},
            "chunks": chunks, "warnings": warnings}

    chapters = None
    if not args.no_chapters:
        log(f"writing chapters with {ch_model}")
        tmpw = [{**w} for w in words]
        assign_speakers(tmpw, names)
        try:
            chapters, resp = make_chapters(gem, ch_model, build_turns(tmpw), duration)
            dump(pkg / "_raw" / "chapters.json", resp)
            meta["models"]["chapters"] = ch_model
            u = resp.get("usage", {})
            cost += (u.get("total_input_tokens", 0) * p("MEDIA_TRANSCRIPTION_CHAPTER_PRICE_IN", 0.75)
                     + (u.get("total_output_tokens", 0) + u.get("total_thought_tokens", 0))
                     * p("MEDIA_TRANSCRIPTION_CHAPTER_PRICE_OUT", 3.75)) / 1e6
        except (RuntimeError, SystemExit) as e:
            warnings.append(f"Chapter generation failed ({e}); wrote one chapter covering the whole recording. "
                            "Retry with --rerender --rechapter.")
    meta["cost"] = {"usd": round(cost, 4), "is_estimate": True,
                    "transcribe_tokens": {"input": usage_in, "output": usage_out}}
    meta["seconds"] = round(time.time() - t0, 1)
    summary(pkg, render(pkg, stem, meta, words, chapters, names))


if __name__ == "__main__":
    main()
