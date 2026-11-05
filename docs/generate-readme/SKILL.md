---
name: generate-readme
description: Generates or updates a project's README.md at BASIC, STANDARD, or ADVANCE fidelity, with Mermaid diagrams at ADVANCE, backing up any existing README and respecting .gitignore. Use whenever the user asks to write, create, generate, draft, refresh, rewrite, or update a README, or says a repo "needs a README" or "project docs", even without naming a fidelity level. Not for API reference sites, changelogs, or tweaking one section of an existing README (edit it directly). Hand SVG output of diagrams to mermaid-to-image and banner or hero images to image-gateway.
metadata:
  version: 1.1.0
---

# Generate README Skill

Writes `README.md` at one of three fidelity levels. Every statement in the output must come from a file you read in this project. All diagrams use Mermaid.

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
