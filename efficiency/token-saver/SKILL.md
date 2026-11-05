---
name: token-saver
description: Token discipline for the rest of a job. Does exact work (counting, sorting, text search, field extraction, date normalization, format conversion, file comparison, validation) with local code instead of a model, sends only matching passages from large sources instead of whole files, rebuilds revisions from the last accepted result instead of the chat history, loads only the tools the job needs, and keeps answers the size of the request. Use when the user says token-saver, asks to save tokens or context, cut token waste, keep a long job cheap, or revise a result across many turns, and whenever a job touches a large transcript, repo, log, or export. Skip for short one-shot questions where nothing large is read.
metadata:
  version: 1.0.1
---

# Token Saver

Governs how context is spent for the rest of the job. You do the extra work; the user never summarizes an old chat, picks source files, creates a state file, or learns a script path.

## Honest limit

This skill cannot erase the call it was loaded into. That call's input is already spent. It only makes the work after it smaller.

## Rules

1. **Local code first.** For anything with one right answer (counting, sorting, exact text search, field extraction, date normalization, format conversion, file comparison, output validation), run code and read its output. Use a model for that work only after local code failed or cannot express it. Helpers: `scripts/tokensaver.py` (`count`, `fields`, `dates`, `diff`, `search`); `sort`, `jq`, `grep`, `pandoc` and similar are fine for the rest. Run helpers with `python3 -I <skill-dir>/scripts/tokensaver.py ...`, where `<skill-dir>` is this skill's folder.
2. **Search, then send only matches.** Never read a whole transcript, repository, log, or export because the answer might be in it. Run `tokensaver.py search <path> <pattern>` (output is capped, default 6000 characters). If the passages are not enough, pull exactly one more bounded passage (`--skip N`, or a narrower pattern). Never fall back to loading everything. For PDF/Office inputs, convert with the heavy-file-ingestion skill first and search the chunks.
3. **One accepted result.** When the user accepts a result, save it: `tokensaver.py accept <job-slug> <file|->`. This writes `~/.claude/state/token-saver/<job-slug>/accepted.md`, replacing the previous one, so there is never more than one. Choose the slug yourself from the job's name. For the next revision, run `tokensaver.py current <job-slug>` and build from that file plus the user's new change, not from the conversation that produced it. A rejected result is never saved; the previous accepted result stays current. If the user gives a change but nothing was ever accepted, use the latest result they have not rejected as the base and save it as accepted once they confirm it.
4. **Load only the tools the job can use.** A job that needs no tools gets none: no `ToolSearch`, no MCP schemas. When tools are needed, make at most one `ToolSearch select:` call naming exactly those tools. Do not start subagents unless rule 5 passes.
5. **Smaller model only when the whole job wins.** Count every call, retry, and human repair. Delegate to a smaller model (for example a subagent with `model: haiku`) only if all hold: the work is bulk (many similar items), mechanical (fixed rubric, no judgment on the user's intent), and checkable by code afterward. Otherwise stay on the current model. Decide from this checklist alone; never call a model to choose a model.
6. **Match the answer to the request.** A sentence request gets a sentence. No process diary, no unrequested options, no restating the question.
7. **One bounded repair.** If a check fails, repair once against that check's output and re-check. If it still fails, report the failure. Never retry a token-limit or usage-limit failure; shrink the input (narrower search, smaller passage, fewer files) and continue from there.

## Reporting usage

When asked, report fresh input, reused (cached) input, output, number of model calls, and retries. Use only numbers the harness shows or a session transcript records. Write `unavailable` for anything else; never estimate.
