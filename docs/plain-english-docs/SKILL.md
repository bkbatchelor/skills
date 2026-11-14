---
name: plain-english-docs
description: Writes documentation in plain English that a non-technical reader can follow, and removes agent English. Use whenever you write or rewrite anything a person will read to get something done - READMEs, setup guides, how-to steps, instructions, user-facing messages, or explanations in chat - even if the user does not say "plain English". Picks one documentation mode per section, defines terms where they first appear, writes steps as commands, covers failures, bans a growing list of filler words, and ends with a self-check. Skip for code comments, commit messages, and files written for agents such as SKILL.md, CLAUDE.md, and prompts.
metadata:
  version: 1.0.0
---

# Plain English Docs

Write for a reader who wants to get something done and does not know your field. Agent English is the stiff, padded style that models drift into. This skill replaces it with short, concrete sentences.

Use it together with `generate-readme` and `html-artifacts`. They decide what goes in a document and how it looks. This skill decides how each sentence reads.

## When this applies

Apply it to anything a person reads to get something done:

- READMEs, setup guides, tutorials, and how-to pages
- Instructions and error messages shown to users
- Explanations written in chat

Do not apply it to:

- Code comments and commit messages
- Files written for agents: `SKILL.md`, `CLAUDE.md`, prompts, and agent configuration

The reader is non-technical by default. A developer audience does not change this. Keep the technical term and define it where it first appears.

## Step 1: Pick one mode per section

Before you write a section, choose exactly one mode and write it down in your notes.

| Mode | The reader wants to | The section does |
|---|---|---|
| Tutorial | Learn by doing, as a beginner | Leads them through one small, working result |
| How-to | Finish a task | Gives the steps and nothing else |
| Reference | Look something up | Lists facts in a fixed, scannable order |
| Explanation | Understand why | Gives background and reasons |

Rules:

- Never mix modes inside a section. If the section alternates between doing and explaining, split it.
- If a how-to needs a concept explained, put the explanation in its own marked block that the reader can skip. Use a heading or a labeled block such as "Background (skip if you only need the steps)". Put it before or after the steps, never between two steps.
- A tutorial teaches. A how-to assumes the reader already knows the basics. Do not write a tutorial and call it a how-to.

## Step 2: Write the sentences

### Define terms where they first appear

Define every term the first time it appears, in the same sentence. Do not send the reader to a glossary.

- Wrong: "Create a repository." (with "repository" defined in a glossary)
- Right: "Create a repository, which is a folder that Git tracks."

### Write steps as commands

- One action per step.
- Start with the imperative verb: "Open Settings. Choose GitHub. Click Install and Authorize."
- Say where before what. Write "In Settings, click Publish." Never write "Click Publish, which is in Settings."
- Number steps only when order matters.

### Name the place, do not point at it

Use the label or menu name. Do not use a screen direction.

- Wrong: "Click the gear icon in the top right."
- Right: "In the toolbar, click Settings."

Screen directions go stale when the interface moves.

### Keep reasons out of steps

A reason gets its own sentence or paragraph, after the step or in a Background block. A step never contains "because", "so that", or "which lets you".

### Use full stops, not em dashes

Write no em dashes. Use a full stop. If the aside does not survive as its own sentence, cut it.

### Use the plain word

| Write | Not |
|---|---|
| wrong | suboptimal |
| use | leverage, utilize |
| before | prior to |
| to | in order to |

The full list is in `banned-words.md`.

### Do not talk down

Never write "simply", "just", "easy", or "please" in an instruction. If it were easy, the reader would not be reading this.

## Step 3: Cover failure

Every step that can fail says what failure looks like and what to do about it. Put this in the line after the step.

- Name the visible sign: the message, the missing item, the blank screen.
- Say the cause if it is known, in plain words.
- Give the next action.

Example:

> In Settings, choose GitHub. Click Install and Authorize.
>
> If your repository is not in the list, that is a permissions thing, not a bug. Ask the repository owner to grant you access, then reload the page.

If you do not know how a step fails, say so to the user instead of inventing a failure.

## Step 4: Check the ban list

`banned-words.md` is the list of agent English. It holds filler words and the plain word to use instead. Read it before you write, and scan your draft against it.

When the user catches a new word or phrase, add it to `banned-words.md` in the same turn. Write the banned form, an arrow, and the replacement or "cut".

## Step 5: Self-check before delivering

Run all of these on the final text. Do not skip any because the text is short.

1. **Em dashes.** Run `python3 scripts/check.py <file>` for a file. For text in chat, save it to the scratchpad first. The em dash count must be zero. The script also lists ban-list hits. Fix each one or confirm it is not an instruction (for example, "just" inside a quote).
2. **Terms.** List every term a non-expert would not know. For each, confirm it is defined at its first use, in that sentence. Fix any that are not.
3. **Doing or why.** Read each section and ask whether it tells the reader to do something or tells them why. If it alternates, split it into a how-to part and a marked Background block.
4. **Weakest sentence.** Pick the weakest sentence. Read it aloud. If it needs a second read, rewrite it.
5. **Failure coverage.** For each step, ask what happens if it fails. Confirm failure is described where it can happen.

Report the result in one line, for example: "Self-check: 0 em dashes, 3 terms defined, 1 section split, 1 sentence rewritten."

## Files

- `banned-words.md`: the ban list. Grow it when the user catches a new word.
- `scripts/check.py`: counts em dashes and lists ban-list hits in a file.
