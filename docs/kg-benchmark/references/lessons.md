# Lessons from real runs

Each of these broke a real benchmark once. `bench` handles the ones marked (handled); the rest need you.

## Isolation

- **Headless runs load the live instructions file.** `claude -p` reads `~/.claude/CLAUDE.md`, so runs at different times see different versions as you edit it. (handled: every run excludes it with `claudeMdExcludes`; arms load fixed copies from an added folder with `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`.)
- **A deny rule on an arm's own instructions copy stops it loading, silently.** Deny only the other arms' copies. (handled.) Keep copies outside the benchmark folder, which is denied. (handled: `instructions_dir`.)
- **Instruction "why" lines can leak answers.** A rule explained with "two runs cited the wrong record for question 6" tells the agent the answer. Strip such lines from benchmark copies.
- **A permission path with one leading slash is not absolute.** `Read(/home/x/**)` is relative to the settings file; use `Read(//home/x/**)` or `~/`. (handled.) A symlinked or mounted path needs rules for both forms. (handled: the resolved path is added.)
- **A gitignored folder hides from search.** If a curated folder's `.gitignore` ignores `staging/`, a Grep from the curated root finds nothing. Tell the arm to search with the staging folder itself as the path.
- **Symlinks can bypass denies.** A repo can link its graph folder into the curated folder; `grep -R`, `find -L` and `cd <link>` follow it. (handled: dereferencing flags are denied for `deny_graphs` arms.)
- **Bash deny patterns with wildcards in the middle over-match.** Test allowed commands in the probe, not only blocked ones.
- **A tilde inside a shell loop is not expanded the way you expect.** Quote it, or build rules in Python. (handled.)
- **Login matters.** `--bare` skips the instructions file but needs an API key; OAuth logins do not work with it.

## Measurement

- **Count graph use from commands, not from text.** A search with `!graphify-out/**` or `grep -v graphify-out` mentions the folder but does not use it. A first version of the metric counted these and reported graph use where there was none. (handled: exclusions are stripped.)
- **Leak checks have the same false positives.** Read every flagged run before discarding it.
- **Judges are wrong often.** In three audits, about half of the judge's flags held up. Some failures were key gaps (a correct alternative name the key did not list). Always audit before counting false claims, and fix keys the audit shows are wrong.
- **Hand checks are not blind checks.** A count checked by hand is not comparable with counts from the blind audit; audit every arm the same way.
- **An unused tool is untested.** If an arm never calls the graph, the arm measured the instructions, not the graph. Check `bench metrics` before drawing conclusions about a tool.
- **Arms run later than others carry a timing caveat.** Interleave, or re-run an earlier arm alongside.
- **Three reps give wide intervals.** Differences of 0.1 to 0.2 on a 5-point scale are usually inside the noise. Report the interval, not only the mean.
- **Most tokens are cache reads.** Around 90% of each run's input is re-read context that costs a tenth of new input, so file reads are already cheap and a graph has little to save.
- **Price the cache writes correctly.** Reported costs used the 1-hour cache-write rate; recomputing with the 5-minute rate understates them.
