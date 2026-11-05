# token-saver

Token discipline for the rest of a job. Once loaded, Claude spends context carefully on its own: it does the extra work itself, and you never summarize an old chat, pick source files, create a state file, or learn a script path.

**Honest limit:** it cannot erase the call it was loaded into. That call's input is already spent. It only makes the work after it smaller.

## Install

The skill is the `efficiency/token-saver/` folder. Link it where your harness loads skills:

```bash
ln -s "$PWD/efficiency/token-saver" ~/.claude/skills/token-saver
```

Requires `python3` (standard library only). Nothing else to install.

## Use

Ask for it by name ("use token-saver"), say you want to save tokens or cut token waste, or work with a large transcript, repo, log, or export. Short one-shot questions don't need it.

## What it does

| Rule | Behavior |
|------|----------|
| Local code first | Counting, sorting, exact search, field extraction, date normalization, format conversion, file comparison, and validation run as code, not through a model |
| Search, then send matches | Large sources are searched; only matching passages are read. If they aren't enough, it pulls one more bounded passage, never everything |
| One accepted result | The result you accept is saved; the next revision is built from it plus your change, not from the chat. Rejected results are never saved |
| Minimal tools | Only tools the job can use are loaded. A job with no tool needs gets none |
| Smaller model only if the whole job wins | Counts every call, retry, and repair. Decided by a fixed checklist, never by a model call |
| Answer sized to the request | A sentence request gets a sentence. No process diary or unrequested options |
| One bounded repair | One repair against a failed check. Token-limit and usage-limit failures are never retried; the input is reduced instead |

## Files

- `SKILL.md`: the rules Claude follows
- `scripts/tokensaver.py`: helper commands Claude runs itself

### Helper commands

```bash
python3 -I scripts/tokensaver.py search <path> <pattern> [-C 2] [--max-chars 6000] [--skip N] [-F] [-i]
python3 -I scripts/tokensaver.py count <file|-> [--by lines|unique|field] [--field N] [--top N]
python3 -I scripts/tokensaver.py fields <file|-> col1,col2.sub [--format csv|tsv|json|jsonl]
python3 -I scripts/tokensaver.py dates <file|-> [--dayfirst]
python3 -I scripts/tokensaver.py diff <a> <b>
python3 -I scripts/tokensaver.py accept <job-slug> <file|->
python3 -I scripts/tokensaver.py current <job-slug>
```

`search` caps its output and prints how many passages remain and the `--skip` value for the next bounded pull.

## Where state lives

The one accepted result per job is `~/.claude/state/token-saver/<job-slug>/accepted.md`, outside any repo. `accept` overwrites it, so there is never a history to grow. Set `TOKEN_SAVER_STATE` to use a different root.

## Reporting usage

When asked, it reports fresh input, reused input, output, model calls, and retries. Any number the harness doesn't provide is reported as `unavailable`, never estimated.
