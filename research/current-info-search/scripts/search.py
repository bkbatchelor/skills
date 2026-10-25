#!/usr/bin/env python3
"""Answer questions about fast-moving facts from live search, not training data.

    search.py gemini   QUESTION [--model M] [--json]
    search.py notebook QUESTION [--deep] [--keep] [--json]

`gemini` calls the Gemini API with Google Search grounding. `notebook` runs a
NotebookLM web-research pass in a throwaway notebook through the `notebooklm`
CLI, asks it for a cited answer, then deletes the notebook (only one this run
created). Standard library only.

Answers and sources go to stdout. Progress and errors go to stderr.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

API = "https://generativelanguage.googleapis.com/v1beta"
SKILL_DIR = Path(__file__).resolve().parent.parent


def log(msg):
    print(f"current-info-search: {msg}", file=sys.stderr, flush=True)


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
    for k, v in os.environ.items():
        if k.startswith("CURRENT_INFO_"):
            cfg[k] = v
    return cfg


def load_key(cfg):
    key = os.environ.get("GEMINI_API_KEY") or read_env_file(
        cfg.get("CURRENT_INFO_ENV_FILE", "~/.config/gemini/.env")
    ).get("GEMINI_API_KEY")
    if not key:
        die(
            "GEMINI_API_KEY not found. Get a key at https://aistudio.google.com/apikey "
            f"and add GEMINI_API_KEY=... to {cfg.get('CURRENT_INFO_ENV_FILE')} (chmod 600)."
        )
    return key


# --- gemini ------------------------------------------------------------------

def resolve_redirect(uri):
    """Grounding sources come back as Google redirect links; find the real URL."""
    if "grounding-api-redirect" not in uri:
        return uri

    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoFollow)
    try:
        opener.open(urllib.request.Request(uri, method="HEAD"), timeout=10)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        if loc:
            return loc
    except Exception:
        pass
    return uri


def cmd_gemini(args, cfg):
    key = load_key(cfg)
    model = args.model or cfg.get("CURRENT_INFO_MODEL", "gemini-3.8-flash")
    today = dt.date.today().isoformat()
    body = {
        "contents": [{"parts": [{"text": f"Today is {today}. {args.question}"}]}],
        "tools": [{"google_search": {}}],
    }
    req = urllib.request.Request(
        f"{API}/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        die(f"Gemini API error {e.code}: {e.read().decode()[:500]}")
    except urllib.error.URLError as e:
        die(f"network error: {e.reason}")

    cand = (resp.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    if not text:
        die(f"no answer returned (finishReason={cand.get('finishReason')}): {json.dumps(resp)[:500]}")
    meta = cand.get("groundingMetadata") or {}
    sources = []
    for i, c in enumerate(meta.get("groundingChunks", []), 1):
        web = c.get("web") or {}
        if web.get("uri"):
            sources.append({"n": i, "title": web.get("title", ""), "url": resolve_redirect(web["uri"])})
    out = {
        "tool": "gemini",
        "model": model,
        "retrieved": today,
        "answer": text.strip(),
        "queries": meta.get("webSearchQueries", []),
        "sources": sources,
    }
    if not sources:
        out["warning"] = "no grounding sources returned; treat the answer as unverified"
    emit(out, args.json)


# --- notebooklm --------------------------------------------------------------

def nlm(cfg, *argv, check=True, timeout=900):
    cmd = [cfg.get("CURRENT_INFO_NOTEBOOKLM", "notebooklm"), *argv]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        die(f"{cmd[0]} not found. Install notebooklm-py and run `{cmd[0]} login`.")
    except subprocess.TimeoutExpired:
        die(f"`{' '.join(cmd)}` timed out after {timeout}s")
    if check and p.returncode != 0:
        text = (p.stdout + "\n" + p.stderr).strip()
        m = re.search(r"^Error:.*?(?=\n\s*\n|\Z)", text, re.S | re.M)
        msg = re.sub(r"\s+", " ", m.group(0) if m else text[-400:])[:400]
        hint = f" Run `{cmd[0]} login` and retry." if re.search(r"auth|login|cookie|expired|sign", text, re.I) else ""
        die(f"`{' '.join(cmd[:3])}` failed: {msg}{hint}")
    return p


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    die(f"could not parse notebooklm JSON output: {text[:300]}")


def find_key(obj, *names):
    """First value found under any of `names`, searching nested JSON."""
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n]:
                return obj[n]
        for v in obj.values():
            r = find_key(v, *names)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, *names)
            if r:
                return r
    return None


def cmd_notebook(args, cfg):
    today = dt.date.today().isoformat()
    prefix = cfg.get("CURRENT_INFO_NOTEBOOK_PREFIX", "current-info:")
    topic = re.sub(r"\s+", " ", args.question).strip()[:50]
    title = f"{prefix} {topic} {today}"
    timeout = int(cfg.get("CURRENT_INFO_NOTEBOOK_TIMEOUT", 300))

    nlm(cfg, "auth", "check", "--test")  # fail early with a login hint if signed out or expired
    created = parse_json(nlm(cfg, "create", title, "--json").stdout)
    nb_id = find_key(created, "id", "notebook_id")
    if not nb_id:
        die(f"could not read the new notebook's id from: {json.dumps(created)[:300]}")
    log(f"created notebook {nb_id[:8]}… ({title})")
    try:
        research = ["source", "add-research", args.question, "-n", nb_id,
                    "--import-all", "--timeout", str(timeout), "--json"]
        if args.deep:
            research += ["--mode", "deep"]
        log("researching the web (this takes a minute or more)…")
        nlm(cfg, *research, timeout=timeout * 2 + 60)
        srcs_raw = parse_json(nlm(cfg, "source", "list", "-n", nb_id, "--json").stdout)
        ask_q = (f"Today is {today}. {args.question}\nAnswer from the sources only. "
                 "Start with the answer itself, key facts and numbers first, with the date "
                 "next to each fact. Mark any claim that rests only on third-party sources. "
                 "Do not write a separate section classifying the sources.")
        ans = parse_json(nlm(cfg, "ask", ask_q, "-n", nb_id, "--new", "--json").stdout)
    finally:
        if args.keep:
            log(f"kept notebook {nb_id} (--keep)")
        else:
            nlm(cfg, "delete", "-n", nb_id, "-y", check=False)
            log(f"deleted notebook {nb_id[:8]}…")

    answer = find_key(ans, "answer", "text", "response") or ""
    if not answer:
        die(f"no answer from NotebookLM: {json.dumps(ans)[:400]}")
    listing = srcs_raw.get("sources", srcs_raw) if isinstance(srcs_raw, dict) else srcs_raw
    sources = []
    for i, s in enumerate(listing if isinstance(listing, list) else [], 1):
        sources.append({"n": i, "title": s.get("title", ""),
                        "url": s.get("url") or s.get("source_url") or ""})
    out = {
        "tool": "notebooklm",
        "retrieved": today,
        "answer": str(answer).strip(),
        "references": find_key(ans, "references", "citations") or [],
        "sources": sources,
        "notebook_id": nb_id if args.keep else None,
    }
    emit(out, args.json)


# --- output ------------------------------------------------------------------

def emit(out, as_json):
    if as_json:
        print(json.dumps(out, indent=2))
        return
    print(out["answer"])
    print(f"\n--- retrieved {out['retrieved']} via {out['tool']}"
          + (f" ({out['model']})" if out.get("model") else "") + " ---")
    if out.get("queries"):
        print("searches: " + "; ".join(out["queries"]))
    if out.get("warning"):
        print(f"WARNING: {out['warning']}")
    for s in out["sources"]:
        print(f"[{s['n']}] {s['title']} - {s['url']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gemini", help="Gemini API with Google Search grounding")
    g.add_argument("question")
    g.add_argument("--model", help="override CURRENT_INFO_MODEL for this call")
    g.add_argument("--json", action="store_true")
    n = sub.add_parser("notebook", help="NotebookLM web research in a throwaway notebook")
    n.add_argument("question")
    n.add_argument("--deep", action="store_true", help="deep research mode (slower)")
    n.add_argument("--keep", action="store_true", help="do not delete the notebook afterward")
    n.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    {"gemini": cmd_gemini, "notebook": cmd_notebook}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
