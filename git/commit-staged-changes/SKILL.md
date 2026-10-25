---
name: commit-staged-changes
description: >-
  Commits only the already-staged changes with a conventional message (Type(Scope): Summary), never staging files itself. Use only when the user explicitly asks to commit what is staged: "commit my staged changes", "commit what I've staged", "commit this with a good message" after they staged files. Never trigger proactively or after finishing work unprompted. Not for staging files, `git commit -a`, amending, pushing, or opening a PR (use commit-commands:commit or commit-commands:commit-push-pr when the user wants those).
metadata:
  version: 1.0.4
---

# Commit Staged Changes Skill

This skill provides instructions for committing only staged changes using a specific commit message format. It never stages new files or modifies the working directory.

## Triggers

Narrow on purpose: committing changes history, so run this skill only on an explicit request.

Use when the user says things like:
- "commit my staged changes", "commit what I've staged", "commit this"
- asks for a commit message for, or a commit of, the staged diff

Skip when:
- The user has not asked to commit. Never commit proactively after finishing work.
- They want files staged, `git commit -a`, an amend, a push, or a PR. Use `commit-commands:commit` or `commit-commands:commit-push-pr` for stage-and-commit or PR flows.

## Reference
See [git-commit-template.md](references/git-commit-template.md) for the complete template.

## Key Rules Summary

### Subject Line Format
`<Type>(<Scope>): <Summary>` (Scope is optional)

Rules:
- Start with uppercase letter
- Use imperative mood
- No period at end
- Maximum 50 characters

### Body Rules
- Explain *what* and *why* (not *how*)
- Wrap at 72 characters
- Separate from subject line with blank line

## Commit Types
| Type | Description |
|------|-------------|
| feat | Introduces a new feature |
| fix | Patches a bug in the codebase |
| docs | Changes related to documentation |
| style | Formatting changes |
| refactor | Code changes that neither fix bugs nor add features |
| perf | Performance improvements |
| test | Adding or correcting tests |

## Examples

### Good Commit Messages

**Feature:**
```
feat(auth): Add JWT authentication

Implement JWT-based authentication to enhance security.
This replaces the basic session-based approach.
```

**Fix:**
```
fix(api): Resolve timeout on large requests

Increase timeout limit to handle large dataset requests.
Previously, requests with >1000 records would timeout.
```

**Documentation:**
```
docs(readme): Update installation instructions

Clarify Python version requirements and add troubleshooting section.
```

**Style:**
```
style(format): Apply prettier formatting

Standardize code formatting across the project.
```

**Refactor:**
```
refactor(validation): Extract validation logic

Move validation rules to separate module for better maintainability.
```

**Performance:**
```
perf(query): Optimize database queries

Add indexes to improve query performance by 50%.
```

**Test:**
```
test(user): Add unit tests for user service

Cover edge cases for user creation and update operations.
```

### Bad Commit Messages (Rule Violations)

**Lowercase subject:**
```
feat(auth): add user authentication
```
*Incorrect: Subject must start with uppercase*

**Period at end:**
```
feat(auth): Add user authentication.
```
*Incorrect: No period at end of subject*

**Too long:**
```
feat(auth): Add user authentication and improve security and fix bugs
```
*Incorrect: Exceeds 50 character limit*

**Past tense:**
```
feat(auth): Added user authentication
```
*Incorrect: Must use imperative mood*

**Missing type:**
```
Add user authentication
```
*Incorrect: Missing commit type*

**Bad body (explains how, not what/why):**
```
feat(auth): Add user authentication

Changed the code to use JWT tokens instead of sessions.
Added new middleware and updated routes.
```
*Incorrect: Body explains how, not what/why*

## Agent Workflow

When instructed to commit changes:

1. **Check for staged changes:**
   ```bash
   git diff --cached --quiet
   ```
   - If exit code is 0, there are no staged changes. Inform user and stop.

2. **Inspect staged changes:**
   ```bash
   git diff --staged
   ```

3. **Determine commit type** based on the changes.

4. **Generate subject line** following the format `<Type>(<Scope>): <Summary>` (Scope is optional).

5. **Generate body** explaining *what* and *why* (not *how*).

6. **Commit with:**
   ```bash
   git commit -m "<Type>(<Scope>): <Summary>" -m "<Body>"
   ```

## Constraints

- **Never run `git add`** or `git commit -a`
- **Only commit already staged changes**
- **Ignore untracked files entirely**
- If no staged changes exist, inform the user and stop

## Repository Hooks

Some repositories enable git hooks that amend extra changes into the commit, such as this repository's `post-commit` hook, which sets a skill's `metadata.version`. Those changes are made by the hook, not by this skill, and are expected. Do not undo them or treat them as staging.
