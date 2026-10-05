# Goal Prompt Template

Use this skeleton for every goal prompt. Keep the headings exactly; fill every section. Replace all `<…>` placeholders. Delete the HTML comments.

```markdown
# Goal: <short imperative title>

**Repository:** `<absolute path to repo root>`
**Branch:** `<branch to work on — create from <base> if it doesn't exist>`
All paths below are relative to the repository root.

## Objective

<One paragraph. What to change, why it matters, and what the finished state looks like.
A reader should know after this paragraph what success means.>

## Background

<Everything a newcomer needs and cannot infer quickly:>
- <Relevant architecture: which modules are involved and how they relate, with paths.>
- <Decisions already made, and alternatives already rejected (with the one-line reason), so they aren't reopened.>
- <Interfaces to match: signatures, schemas, config keys — quote briefly and name the file.>
- <Known pitfalls or quirks in this area.>
- <Environment setup: install command, required env vars (names only), services that must be running.>
- <Baseline: current results of the verification gates before any change, including pre-existing failures.>

## Definition of Done

All of the following must be true. Each item is checkable without judgment.

- [ ] <Verifiable statement — e.g. "`src/foo.ts` exports `bar(x: string): number`">
- [ ] <Verifiable statement — e.g. "`tests/foo.test.ts` has a test for the empty-input case, and it passes">
- [ ] <Negative constraint if relevant — e.g. "No files outside the allowed list are modified (`git diff --name-only <base>...HEAD`)">
- [ ] All verification gates below pass with the expected results.

## Repo Constraints

**May modify / create:**
- `<path or glob>` — <why>

**Must NOT touch:**
- `<path or glob>` — <why, if not obvious>
<!-- Typical: lockfiles, generated code, migrations, CI config, vendored deps, unrelated modules. -->

**Rules:**
- Dependencies: <"No new dependencies" | the specific ones allowed>.
- Git: <commit or not; commit message convention; never push/force-push unless stated>.
- <Any other rule: code style, no public API changes, etc.>

## Verification Gates

Run from the repository root, in this order, before claiming completion. All must meet the expected result.

| # | Command | Expected result | Proves DoD item(s) |
|---|---------|-----------------|--------------------|
| 1 | `<command>` | <exit 0 / "N passed, 0 failed" / no output / specific string> | <which items> |
| 2 | `<command>` | <expected> | <which items> |

<For any DoD item not covered by a command, state the exact inspection: "Open `<file>` and confirm <specific thing>".>

## Stop Conditions

Halt and ask — do not improvise — if any of these occur:

- <Task-specific trigger — e.g. "`legacyAuth()` is still called from anywhere outside `src/auth/`">
- <Task-specific trigger>
- A file, function, or API named in this prompt doesn't exist or behaves differently than described.
- The work appears to require modifying a "Must NOT touch" area or adding a dependency.
- A gate fails for a reason unrelated to this task, or the same failure persists after <N> fix attempts.
- Any destructive or outward-facing action would be needed (migrations, deleting data, pushing, publishing, external calls).
- A requirement is ambiguous in a way that would change the result.

**When halting:** stop making changes, leave the working tree as-is (do not revert), and write the Completion Report with the blocker, what you tried, and the options you see.

## Completion Report

Finish with a report containing:
1. **Status:** DONE or BLOCKED.
2. **Definition of Done:** each item, checked or unchecked, with evidence (command output summary, file:line).
3. **Gate results:** each command and its actual result.
4. **Files changed:** output of `git status --short` (and `git diff --stat` if committed).
5. **Deviations / notes:** anything done differently from this prompt and why; anything the reviewer should look at closely.
6. **If BLOCKED:** the stop condition hit, what was tried, and the options.
```
