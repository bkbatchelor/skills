---
name: goal-prompt-generator
description: >-
  Use when handing a plan or task to another agent session: writes a bounded goal prompt with done criteria, constraints, gates, stop conditions. Prompt only; to launch, use visible-delegation.
metadata:
  author: Brian Batchelor
  version: 1.0.8
  tags: [delegation, handoff, prompt-writing, autonomous-agents]
---

# Goal Prompt Generator

Convert a plan or task into a **goal prompt**: a document another agent session can pick up cold, work on without supervision, and that the user can later grade pass/fail without re-deriving the plan.

The receiving session has **none of this conversation's context**. It cannot see the plan you discussed, the files you read, the decisions you made, or what "the bug" refers to. Everything it needs must be in the prompt. Everything the user needs to check the result must be in the prompt too.

## Purpose

A goal prompt lets one agent session hand work to another and lets the user grade the result without re-reading the plan. This skill writes that prompt and nothing else.

## Prerequisites

- Read access to the target repository, so paths and commands can be checked before they go into the prompt.
- A plan or task to package: an earlier plan in the conversation, a plan file, an issue, or a description the user gives.
- `references/goal-prompt-template.md`, which holds the required structure.

## Triggers

Use when the user asks to package work for another session or agent, write a goal prompt, hand off a task, prepare a task for autonomous or background execution, or write a prompt for a subagent, cloud agent, or worktree session. Also use for "turn this plan into something another Claude can run", "make this a task I can kick off later", "prepare this for background execution", or "write a subagent prompt for this".

Skip when:
- The user wants the task done in this session.
- They want a delegate launched and watched. Use `visible-delegation`, which calls for a goal prompt first.

## Instructions

### 1. Pin down the source

Identify the plan or task being packaged: an earlier plan in the conversation, a plan file, an issue, or a description the user just gave. If it is too vague to produce verifiable done-criteria (e.g. "make auth better"), ask the user the minimum questions needed — an open design decision pushed onto the receiving agent becomes improvisation, which is exactly what the goal prompt exists to prevent.

### 2. Ground it in the repo

Don't write from memory. Before drafting, look at the actual repository so the prompt contains facts rather than guesses:

- **Paths**: confirm every file and directory you will name exists (or is explicitly new). Use paths relative to a stated repo root, and state the root as an absolute path.
- **Commands**: find the real build/test/lint/typecheck commands (package.json scripts, Makefile, justfile, pyproject, CI config). Don't invent `npm test` if the repo uses `pnpm vitest run`.
- **Baseline**: when cheap, run the verification commands now and record the current state. If tests already fail before any change, say so and list them — otherwise the receiving agent will chase pre-existing failures or you won't be able to tell regressions from old breakage.
- **Git state**: the branch to work on, and whether the agent should commit, and if so how (repo commit conventions, no pushing unless told).
- **Interfaces**: signatures, schemas, config keys, or snippets the agent will need to match. Quote them briefly rather than saying "follow the existing pattern" — then also name the file where the pattern lives.

### 3. Draft using the required structure

Every goal prompt uses the structure in `references/goal-prompt-template.md`. Read it before drafting. The required sections are:

1. **Objective** — one paragraph: what to build/change and why, and what "finished" means at a high level.
2. **Background** — the context a newcomer needs: relevant architecture, decisions already made (and alternatives already rejected, so they aren't relitigated), and known pitfalls.
3. **Definition of Done** — a checklist of verifiable statements.
4. **Repo Constraints** — what may be modified, what must not be touched, and git rules.
5. **Verification Gates** — exact commands, where to run them, and the expected result.
6. **Stop Conditions** — situations where the agent must halt and ask rather than improvise.
7. **Completion Report** — what the agent must hand back.

Guidance on the sections that are easiest to get wrong:

**Definition of Done.** Every item must be a statement someone can check true/false by running a command or looking at a specific place — no judgment calls. "Error handling is robust" is not checkable; "`parseConfig()` in the config module throws `ConfigError` when `port` is missing, covered by a test in the config test file" is. Include the negative space when it matters ("no changes to the public API of the library entry point"). If an item can't be made checkable, it probably hides an undecided design question — resolve it with the user.

**Repo Constraints.** List allowed areas as concrete paths or globs. List forbidden areas explicitly — lockfiles, generated code, migrations, CI config, vendored code, unrelated modules the agent might be tempted to "clean up". Say whether new dependencies are allowed (default: no).

**Verification Gates.** Give the exact command, the working directory, and the expected outcome (exit code, test counts, "no output", a specific string). Order them cheapest first. Map each Definition of Done item to the gate or inspection that proves it — if a DoD item has no gate, add one or explain how it's inspected.

**Stop Conditions.** These are what keep the agent bounded. Be specific to the task, then include the general ones that apply:
- The plan's assumptions turn out to be false (a named file/function/API doesn't exist or behaves differently).
- Completing the task appears to require modifying a forbidden area or adding a dependency.
- A gate fails for a reason outside the task's scope, or the same failure persists after a small, stated number of fix attempts (e.g. 3).
- Any destructive or outward-facing action: data migrations, deleting files outside the allowed area, force-pushing, publishing, calling external services.
- The requirement is ambiguous in a way that changes the result.

Tell the agent what "halting" means: stop editing, leave the working tree in its current state (don't revert), and produce the completion report describing what blocked it and the options it sees.

### 4. Self-containment pass

Reread the draft as if you had never seen this conversation. Fix anything that leans on shared context:

- References like "the bug", "our approach", "as discussed", "the new endpoint", "option B" — replace with the actual content.
- Paths that are relative to nothing, or bare filenames that could match several files.
- Background the agent needs to make a correct call (why this approach, what the user cares about) that exists only in your head.
- Environment setup: how to install deps, required env vars (names only — never paste secrets), services that must be running.

### 5. Quality check — before delivering

Ask both questions honestly:

> **Could a competent agent with zero context execute this?**
> **Could the user verify the result without re-deriving the plan?**

Concretely, confirm:
- [ ] Every path named was checked against the repo (or is marked as new).
- [ ] Every DoD item is objectively checkable and maps to a gate or a stated inspection.
- [ ] Every gate command is real for this repo, with an expected result.
- [ ] Forbidden areas are listed, not just allowed ones.
- [ ] Stop conditions include task-specific triggers, not only the generic list.
- [ ] No references to this conversation remain.
- [ ] The scope is bounded — one coherent goal. If it reads like three projects, split it into multiple goal prompts and say what order they run in.

If either question gets a "no", fix the prompt before delivering — don't deliver with caveats.

### 6. Deliver

Output the goal prompt in a single fenced markdown block so it can be copied whole. Before the block, add at most two or three lines for the user: anything you assumed, the baseline state you observed, or an open question you'd like them to confirm. If the user asks for a file, write it where they say (otherwise suggest a path like `<repo>/.goals/<slug>.md` and confirm before writing into the repo).

Don't start executing the task yourself — packaging it is the job.

## Examples

**Vague request, ask first.** The user says "hand off the auth cleanup". The plan has no checkable outcome, so ask the one or two questions that pin it down (which module, what counts as finished) before drafting.

**Clear request, deliver the prompt.** The user says "package the plan to add a `--dry-run` flag to the export command so a background session can do it". After checking the repo, reply with a short note and one fenced block:

> Assumed the flag is CLI-only. Baseline: the test suite passes (42 tests).

```markdown
## Objective
Add a `--dry-run` flag to the `export` command that prints what would be written and writes nothing.

## Definition of Done
- [ ] `export --dry-run` exits 0 and creates no files.
- [ ] A test covers the flag and passes.
- [ ] No changes outside the export command and its tests.

## Verification Gates
1. `npm test` from the repo root: exit 0, 43 tests pass.

## Stop Conditions
- The export command does not exist where the plan says it does.
- Three fix attempts fail on the same gate.
```

The real prompt also fills in Background, Repo Constraints and Completion Report from `references/goal-prompt-template.md`.

**Background or subagent handoff.** The user says "prepare the migration plan for background execution". The plan names a destructive step (dropping a table). Put that step under Stop Conditions as a halt-and-ask trigger, not in the Definition of Done, and tell the user you did so in the note before the block.

## Limitations

- It writes the prompt only. It does not launch, watch or verify the receiving session; use `visible-delegation` for that.
- The prompt is only as accurate as the repo check. Without repo access, mark every path and command as unverified in the note.
- One goal per prompt. A plan that reads like several projects is split, and the run order is stated.
- It cannot make an undecided design question checkable. Those go back to the user.

## Troubleshooting

| Problem | Cause | Fix |
| --- | --- | --- |
| A Definition of Done item reads "robust" or "clean" | The outcome is a judgment call | Rewrite it as a command or a specific place to check; if it will not reduce, ask the user which behavior counts |
| A gate command fails when you run it now | Wrong command for this repo, or the baseline is already red | Find the real command in CI config or the build file; record pre-existing failures in the prompt |
| The prompt says "the bug" or "as discussed" | It leans on this conversation | Replace each reference with its actual content in the self-containment pass |
| The plan is too vague to verify | Open design decisions remain | Ask the user the one or two questions that settle them before drafting |
| The draft reads like three projects | Scope is too wide | Split into separate prompts and state their order |
