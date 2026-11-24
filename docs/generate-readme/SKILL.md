---
name: generate-readme
description: Writes or updates a project README.md at BASIC, STANDARD or ADVANCE level. Use when asked to write, refresh or rewrite a README or project docs. Not for changelogs, API sites or one-section edits.
metadata:
  version: 1.1.2
  author: Brian Batchelor
  tags: [readme, documentation, mermaid, markdown]
---

# Generate README Skill

Writes `README.md` at one of three fidelity levels. Every statement in the output must come from a file you read in this project. All diagrams use Mermaid.

## Purpose

Produce an accurate README for any repository by reading its real files, at the depth the user asks for. Hand diagram images to `mermaid-to-image` and banner images to `image-gateway`.

## Prerequisites

- Read access to the project files. Git is optional but gives the best `.gitignore` handling and backup decisions.
- Optional: `mmdc` (mermaid-cli) to render and validate Mermaid blocks. Without it, check syntax by eye.

## Triggers

Use when the user:
- asks to write, create, generate, draft, refresh, rewrite, or update a README
- says a repo or project "needs a README" or "needs docs", even without naming a fidelity level

Skip when:
- They want one section of an existing README changed. Edit it directly.
- They want API reference sites, changelogs, or other docs. This skill only writes `README.md`.
- They want diagrams as SVG files (use `mermaid-to-image`) or banner or hero images (use `image-gateway`).

## Fidelity levels

| Level | Adds | Template |
|-------|------|----------|
| BASIC | Name, tech stack, getting started, usage | [basic-level-template.md](references/basic-level-template.md) |
| STANDARD | BASIC + structure, modules, contributing, license | [standard-level-template.md](references/standard-level-template.md) |
| ADVANCE | STANDARD + architecture diagrams, configuration, API, testing, deployment | [advance-level-template.md](references/advance-level-template.md) |

Choose the level from the request ("quick README" is BASIC, "full docs with diagrams" is ADVANCE). If the request does not make it clear, ask with AskUserQuestion and recommend STANDARD. State the level you used in the final report.

## Workflow

1. **Pick the level** as above.
2. **Analyze the project.** Read the manifest (package.json, pyproject.toml, Cargo.toml, go.mod, pom.xml), the license file, CI config, and the top-level layout. Take the project name from the manifest, else the directory name.
3. **Respect `.gitignore`.** In a git repo, list files with `git ls-files --cached --others --exclude-standard` and never document anything outside that list. Outside a git repo, read `.gitignore` and apply it. Always skip `node_modules`, `.git`, `dist` and `build`.
4. **Read any existing README.** On an update, keep human-written content that is still accurate (badges, history, custom sections, tone) and rewrite only what is stale or missing. Do a full rewrite only when the user asks for one.
5. **Back up only if git cannot recover the old file.** If `README.md` is untracked, has uncommitted changes, or the directory is not a git repo, rename it to `README.{n+1}.md` (n is the highest existing backup number, starting at `README.1.md`) and tell the user. Otherwise skip the backup.
6. **Draft** the README following the level's template. Delete any section the project has no real content for. Never leave placeholders.
7. **Verify before writing:**
   - Each install, run, test and lint command exists (npm script in package.json, Makefile target, console entry point, and so on).
   - Each path and module named exists.
   - Each Mermaid block is valid: render with `mmdc` if installed, else check the syntax by eye.
   - Drop anything you cannot confirm, or mark it `<!-- TODO: verify -->`.
8. **Write `README.md`** in the project root and report: level used, backup location (if any), and any TODO markers left.

## Mermaid guidelines

Draw only diagrams the codebase supports, and every node must match a real file, module or service. If the project has no real architecture, draw none.

| Diagram | Use only when | Syntax |
|---------|---------------|--------|
| Architecture | There are several components or services | `graph TD` / `graph LR`, `subgraph` for groups |
| Sequence | A real multi-step or multi-service flow exists | `sequenceDiagram` |
| Flowchart | There is a real decision, error or deploy pipeline | `flowchart TD` with labeled branches |
| ER | The repo has a schema or models | `erDiagram` |

Keep each diagram to 15 nodes or fewer, with descriptive labels.

## Constraints

- Never overwrite a README that git cannot recover without a backup.
- Never document `.gitignore`d files.
- Mermaid is the only diagram format.
- No secrets (keys, passwords, tokens) in the output.
- No invented content: if you did not read it, do not write it.

## Example

User: "Write a full README with diagrams for this repo."

```text
level: ADVANCE
backup: none (README.md tracked and clean)
verify: npm scripts and paths confirmed
write: README.md
```

1. Level is ADVANCE ("full ... with diagrams").
2. Read `package.json`, `LICENSE`, `.github/workflows/`, and the `git ls-files` listing.
3. `README.md` is tracked and clean, so skip the backup. Draft from `references/advance-level-template.md`, and draw one `graph TD` of the real modules.
4. Confirm each `npm run` script and path exists, then write `README.md`.
5. Report: "ADVANCE, no backup needed, 1 TODO marker left."

## Limitations

- Writes only `README.md`. It does not produce API reference sites, changelogs or image files.
- Output is only as complete as the files it can read. Sections with no source content are dropped, not guessed.
- Mermaid is checked by `mmdc` only when installed; otherwise by eye.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| A command in the draft is missing from the README | It could not be confirmed in a manifest or Makefile | Add the script to the project, or keep the `<!-- TODO: verify -->` marker and tell the user |
| Mermaid block does not render | Syntax error or more than 15 nodes | Run `mmdc -i diagram.mmd -o /dev/null`, fix the error, split the diagram |
| Old README was lost | It was untracked or uncommitted and no backup was made | Look for `README.{n}.md` in the project root; git cannot recover untracked files |
| README lists ignored files | `.gitignore` was not applied | Rebuild the file list with `git ls-files --cached --others --exclude-standard` |
