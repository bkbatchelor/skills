# Template: bug-resolution comment

Use only for a comment that reports how a resolved bug was fixed (for example a drafted fix summary). Any other comment stays free text.

## Format

Four bold-labelled paragraphs, one blank line between them, in this order:

**Root cause:** <why the defect happened, 1-3 sentences>

**Change:** <what was changed, where in plain terms, when, and what is not affected>

**Validation:** <what was checked and by whom; state plainly what was not assessed or has no record, including which environment has the fix>

**Caveat:** <the weakest link in the evidence>

- Root cause, Change and Validation are always present.
- Caveat is optional: leave it out when the evidence has no gap or weak link.

## Rules

- Write it with the `plain-english-docs` skill (see `SKILL.md` step 2).
- Plain language, 1-3 sentences per section. No code, no file paths, no personal names.
- Dates in ISO form (2026-01-15). Name ticket and defect ids (for example `BUG-042 (PROJ-456)`).
- Never call something fixed or passed without a recorded result. Write "no record" or "we did not assess it" instead of guessing.
- Root cause, change, validation and caveat must match the team's resolution report.

## Example

**Root cause:** the date field on the signup form used the server's time zone instead of the user's, so a date picked late in the evening was saved as the next day.

**Change:** the form now saves the date in the user's own time zone. It is a one-line settings change, made on 2026-01-15. Other forms are not affected.

**Validation:** a developer before/after screenshot shows the right date. A QA retest note was added on 2026-01-17, but we did not assess it. No recorded test run was found, and we have no record of which environment has the fix.

**Caveat:** the commit messages do not name this ticket. The link rests on the change log entry for BUG-042 (PROJ-456).
