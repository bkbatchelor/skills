---
name: current-info-search
description: Answers questions about fast-changing facts from live Google Search (Gemini API with grounding) and NotebookLM web research instead of training data or default web search. Use whenever the user asks about anything recent or fast-moving, such as AI model releases, model pricing, context windows or limits, software or library versions, changelogs, API changes or deprecations, security advisories, news, or "latest", "current", "new", "today", "this week", "still true?". Also use whenever the user's claim or your own knowledge of such a fact might be stale (a version number, price, model name or date from memory), and when another skill or task depends on a fact like that being current. Not for timeless facts, questions about the user's own code, or searching local files.
metadata:
  version: 1.0.0
---

# Current Info Search

Training data goes stale. For anything that changes quickly, look it up live with `scripts/search.py` before answering:

```bash
~/Projects/skills/current-info-search/scripts/search.py gemini "latest stable Python release and its date"
```

The script is in this skill's `scripts/` folder. Use the absolute path of the directory this SKILL.md was loaded from, since the skill may be linked into several places. It needs `python3` (standard library only).

## Saved preferences

These live in `config.env` next to this file and are read on every run. To change a default permanently, edit `config.env`.

| Setting | Value |
|---|---|
| Gemini model | `gemini-3.8-flash` (`--model` overrides it for one call) |
| API key | `GEMINI_API_KEY`: an exported variable wins, otherwise the line in `~/.config/gemini/.env` (shared with image-gateway and media-transcription) |
| NotebookLM CLI | `notebooklm` (notebooklm-py). It signs in with `notebooklm login`, not with the API key |

Never print the key, `cat` the env file, pass the key on a command line you display, or write it into this skill or any output. If the key is missing the script says so. Tell the user to get one at https://aistudio.google.com/apikey and add `GEMINI_API_KEY=...` to that file in their editor (`chmod 600`), not by pasting it into the chat.

## When to use it

Search **before answering** when any of these hold:

- The question is about something recent or fast-moving: model releases, pricing, context limits, software and package versions, API behavior or deprecations, changelogs, security advisories, news, who currently holds a role.
- The question contains "latest", "current", "newest", "now", "today", "this week/month", or a year at or after your training cutoff.
- The user states a version, price, model name, date or "X was released" that you cannot confirm. Check it instead of agreeing or correcting from memory.
- You are about to write a version number, price, model ID or date from memory into code, config or docs.

Skip it for timeless facts, the user's own code, and anything answerable from local files.

## Step 1: Gemini with Google Search grounding (always first)

```bash
search.py gemini "QUESTION"            # answer, searches run, numbered sources
search.py gemini "QUESTION" --json     # same, as JSON
search.py gemini "QUESTION" --model MODEL_ID   # use a different model for one call
```

Put the time frame and the exact thing you need in the question ("since 2026-09-24", "API price per 1M tokens", "official announcement link"). The script prepends today's date. Source links come back as Google redirects, and the script resolves them to the real URLs.

The same call as raw curl (the key comes from the environment):

```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"What is the latest Python release?"}]}],
       "tools":[{"google_search":{}}]}'
```

The answer is in `candidates[0].content.parts[].text`. The sources are in `candidates[0].groundingMetadata.groundingChunks[].web` (`uri` is a redirect, `title` is only the domain) and the searches run are in `webSearchQueries`. If `groundingChunks` is empty, nothing was searched, so treat the answer as unverified.

## Step 2: NotebookLM research (only when needed)

Run it when the question needs synthesis across many sources, when the user asks for it, or when Gemini's sources are thin, conflicting or all secondary.

```bash
search.py notebook "QUESTION"           # fast web research, ~1 minute
search.py notebook "QUESTION" --deep    # deep research, about 5 minutes
search.py notebook "QUESTION" --keep    # keep the notebook instead of deleting it
```

The script runs these `notebooklm` commands, and you can run them by hand:

```bash
notebooklm auth check                                   # signed in?  if not: notebooklm login
notebooklm create "current-info: <topic> <date>" --json # note the notebook id
notebooklm source add-research "QUESTION" -n ID --import-all --json
notebooklm source list -n ID --json
notebooklm ask "QUESTION" -n ID --new --json            # cited answer
notebooklm delete -n ID -y                              # only the notebook you just created
```

Fast mode takes about 1 minute. Deep mode takes about 5 minutes and finds far more official sources (vendor docs, cloud model cards, release notes), but it also imports some irrelevant ones, so use it only when the question needs primary sources. Run it with a generous Bash timeout.

Each run uses a throwaway notebook named `current-info: <topic> <date>` and deletes it afterward, but only the one it created. **Never write into, ask, or delete the user's existing notebooks.**

Reading the output: the `[N]` markers inside a NotebookLM answer point at passages inside its sources and do not match the numbered list under the answer, so don't copy them. Cite by source title and URL instead. Its web research tends to pull in blogs and aggregators, so look for official sources in the list, and run a Gemini query for the primary link if there is none.

## Rules for answering

1. **Cite dates and primary sources.** Every answer built from search results states (a) the date of each fact, meaning when it was published or released, plus the date you retrieved it, and (b) a link to the primary source: the vendor's announcement, docs, pricing page, changelog, repo release or standard. Prefer first-party sources over blogs, aggregators and videos. If only secondary sources exist, say so, and say which claims rest on them.
2. **Search results win over training data.** When results contradict what you remember, go with the results. Don't hedge back toward memory, and don't "correct" a result because it doesn't match what you expect. Say what changed ("my training data says X, current sources say Y as of DATE"). If two search results disagree with each other, report both, prefer the primary source and the newer date, and say that they conflict.
3. **Don't invent.** If no source confirms a detail, say you couldn't verify it. Don't fill a gap from memory and present it as current. A model name or version you don't recognize is not a reason to doubt it. Check it.
4. **Say which tool answered.** Name Gemini or NotebookLM, and mention when a tool failed or was skipped.
