# Git Commit Template

## Subject Line
Format: `<Commit-Type>(<Scope>): <Summary>` (Scope is optional)

Rules:
- Start with uppercase letter
- Use imperative mood (e.g., "Add" not "Added")
- No period at the end
- Maximum 50 characters

## Body
- Explain *what* and *why* (not *how*)
- Wrap at 72 characters
- Separate from subject line with a blank line

## Checklist
- [ ] Separate subject from body with a blank line
- [ ] Limit the subject line to 50 characters
- [ ] Capitalize the subject line
- [ ] Do not end the subject line with a period
- [ ] Use the imperative mood in the subject line
- [ ] Wrap the body at 72 characters
- [ ] Use the body to explain what and why vs. how

## Commit Types
| Commit Type | Description |
|-------------|-------------|
| feat | Introduces a new feature |
| fix | Patches a bug in the codebase |
| docs | Changes related to documentation |
| style | Formatting changes (whitespace, formatting, etc.) |
| refactor | Code changes that neither fix bugs nor add features |
| perf | Performance improvements |
| test | Adding or correcting tests |