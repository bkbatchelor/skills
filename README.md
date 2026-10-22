# Skills

A collection of reusable skills for AI-powered development workflows.

## Tech Stack

| Category | Technology |
|----------|------------|
| Format | Markdown |
| Version Control | Git |

## Quick Start

```bash
# Clone the repository
git clone git@github.com:bkbatchelor/skills.git
cd skills
```

## Installation

### Prerequisites
- Git

### Steps

1. Clone the repository:
   ```bash
   git clone git@github.com:bkbatchelor/skills.git
   ```

2. Navigate to project directory:
   ```bash
   cd skills
   ```

3. Copy skills to your opencode configuration:
   ```bash
   # Copy individual skills to your project
   cp -r generate-readme /path/to/your/project/.opencode/skills/
   cp -r commit-staged-changes /path/to/your/project/.opencode/skills/
   ```

4. Or add the skills directory to your global opencode config:
   ```bash
   # Add to ~/.config/opencode/opencode.json
   {
     "skills": {
       "paths": ["/path/to/skills"]
     }
   }
   ```

---

## Project Structure

```text
skills/
├── .gitignore                # Ignores Python bytecode caches
├── .githooks/                # Shared git hooks (enable per clone)
│   ├── commit-msg            # Validates the message, records a pending bump
│   └── post-commit           # Sets skill versions and amends them in
├── scripts/
│   └── bump-version.sh       # Version bump logic and manual bumps
├── commit-staged-changes/    # Git commit skill
│   ├── SKILL.md              # Skill definition
│   └── references/           # Reference materials
│       └── git-commit-template.md
├── generate-readme/          # README generation skill
│   ├── SKILL.md              # Skill definition
│   └── references/           # Reference materials
│       ├── basic-level-template.md
│       ├── standard-level-template.md
│       └── advance-level-template.md
├── goal-prompt-generator/    # Goal prompt generation skill
│   ├── SKILL.md              # Skill definition
│   └── references/           # Reference materials
│       └── goal-prompt-template.md
├── media-transcription/      # Audio/video transcription skill
│   ├── SKILL.md              # Skill definition
│   ├── config.env            # Saved defaults (models, key location, prices)
│   ├── references/           # Reference materials
│   │   ├── api.md
│   │   └── format.md
│   └── scripts/              # Helper scripts
│       └── transcribe.py
├── docs-curator/             # Document source curation skill
│   ├── SKILL.md              # Skill definition
│   ├── config.env            # Saved defaults (thresholds, format rank, scope tokens)
│   ├── sources.example.toml  # Annotated example of a sources file
│   ├── references/           # Reference materials
│   │   ├── format.md
│   │   ├── heuristics.md
│   │   └── review.md
│   ├── scripts/              # Helper scripts
│   │   ├── curate.py
│   │   └── curator/          # Modules (sources, inventory, extract, fingerprint, duplicates, ...)
│   └── tests/                # Fixture generator and smoke test
│       ├── make_fixtures.py
│       └── smoke_test.py
├── image-gateway/            # Image generation and editing skill
│   ├── SKILL.md              # Skill definition
│   ├── config.env            # Saved defaults (model, output dir, key file)
│   ├── references/           # Reference materials
│   │   └── api.md
│   └── scripts/              # Helper scripts
│       └── generate.sh
├── mermaid-to-svg/           # Mermaid diagram rendering skill
│   ├── SKILL.md              # Skill definition
│   ├── references/           # Reference materials
│   │   └── troubleshooting.md
│   └── scripts/              # Helper scripts
│       └── render.sh
└── visible-delegation/       # Visible agent delegation skill
    ├── SKILL.md              # Skill definition
    ├── references/           # Reference materials
    │   └── delegate-addendum.md
    └── scripts/              # Helper scripts
        ├── lib.sh
        ├── launch.sh
        ├── watch.sh
        ├── say.sh
        └── cleanup.sh
```

---

## Available Skills

| Skill | Description | Key Files |
|-------|-------------|-----------|
| commit-staged-changes | Commits staged changes using conventional commit format | `SKILL.md`, `references/git-commit-template.md` |
| generate-readme | Generates README files with three fidelity levels | `SKILL.md`, `references/basic-level-template.md`, `references/standard-level-template.md`, `references/advance-level-template.md` |
| goal-prompt-generator | Turns a plan or task into a self-contained, verifiable goal prompt | `SKILL.md`, `references/goal-prompt-template.md` |
| media-transcription | Transcribes audio/video into a Markdown transcript, word timestamps, speakers, chapters, and captions with Gemini 3.5 Transcribe | `SKILL.md`, `config.env`, `references/api.md`, `references/format.md`, `scripts/transcribe.py` |
| docs-curator | Curates document sources before knowledge-graph ingestion: finds duplicates, superseded revisions and contradictions, then builds a clean `curated/` tree of Markdown and linked native files | `SKILL.md`, `config.env`, `sources.example.toml`, `references/format.md`, `references/heuristics.md`, `references/review.md`, `scripts/curate.py`, `tests/smoke_test.py` |
| image-gateway | Generates or edits images with Google's Gemini API (Nano Banana Pro) using saved defaults | `SKILL.md`, `config.env`, `references/api.md`, `scripts/generate.sh` |
| mermaid-to-svg | Renders Mermaid diagrams to validated SVG files with mermaid-cli | `SKILL.md`, `references/troubleshooting.md`, `scripts/render.sh` |
| visible-delegation | Delegates work to another agent session in a watchable herdr pane | `SKILL.md`, `references/delegate-addendum.md`, `scripts/lib.sh`, `scripts/launch.sh`, `scripts/watch.sh`, `scripts/say.sh`, `scripts/cleanup.sh` |

---

### Skill Details

#### commit-staged-changes

---

Commits only staged changes using a specific commit message template. Never stages new files or modifies the working directory.

**Key Components:**
- `SKILL.md`: Skill definition with commit message rules and workflow
- `references/git-commit-template.md`: Complete commit message template

**Features:**
- Enforces Conventional Commits format
- Supports type/scope/summary format
- Validates subject line rules (uppercase, imperative mood, no period)
- Never runs `git add` or `git commit -a`

#### generate-readme

---

Generates professional README documentation with three fidelity levels. All diagrams use Mermaid chart format.

**Key Components:**
- `SKILL.md`: Skill definition with templates and workflow
- `references/basic-level-template.md`: BASIC level template
- `references/standard-level-template.md`: STANDARD level template
- `references/advance-level-template.md`: ADVANCE level template

**Fidelity Levels:**
- **BASIC**: Project name, tech stack, quick start, installation, usage
- **STANDARD**: BASIC + modules, contributing, license
- **ADVANCE**: STANDARD + architecture diagrams, configuration, API reference, testing, deployment

**Features:**
- Interactive fidelity level selection
- Automatic `.gitignore` parsing and exclusion
- README backup with incrementing numbers
- Mermaid diagram generation (ADVANCE level)

#### goal-prompt-generator

---

Turns an implementation plan or task description into a bounded, self-contained goal prompt that a fresh agent session can execute autonomously. The user can then check the result pass/fail without re-deriving the plan.

**Key Components:**
- `SKILL.md`: Skill definition with drafting workflow and quality checks
- `references/goal-prompt-template.md`: Required goal prompt structure

**Features:**
- Required sections: objective, background, definition of done, repo constraints, verification gates, stop conditions, completion report
- Grounds paths, commands, and baseline test state in the actual repository
- Requires every definition-of-done item to be objectively checkable and mapped to a gate
- Self-containment pass removes references to the originating conversation
- Delivers the prompt as a single copyable markdown block without executing the task

#### media-transcription

---

Turns a local audio or video file into a transcription package with one command, using Google's [Gemini 3.5 Transcribe](https://ai.google.dev/gemini-api/docs/transcribe) model (`gemini-3.5-transcribe`). For `talk.mp4`, the package goes in `talk.transcript/` next to the media. The package format is versioned (schema 1.0), so editing and research skills can read it without guessing.

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, workflow, limits, and rules for skills that consume the package
- `config.env`: Saved defaults: speech and chapter models, API key env file, chunk length, and prices
- `references/format.md`: Package contract, covering every file's schema, the invariants consumers can rely on, and versioning rules
- `references/api.md`: Files API upload, transcribe request and response shapes (including where the live API differs from Google's docs), limits, prices, and a raw curl example
- `scripts/transcribe.py`: Extracts audio with ffmpeg, uploads it, transcribes it, writes chapters, and builds the package (Python standard library only)

**Output Package:**
- `<stem>.transcript.md`: Readable transcript with a chapter list and timestamped speaker turns
- `<stem>.words.json`: Every word with start/end seconds, speaker, and turn
- `<stem>.speakers.json`: Speakers (`S1`, `S2`, …) and their turns
- `<stem>.chapters.json`: Semantic chapters with title, summary, keywords, and time range
- `<stem>.srt` / `<stem>.vtt`: Captions with speaker names
- `manifest.json` and `_raw/`: Source hash, models, cost estimate, and the untouched API responses

**Requirements:**
- `python3`, `ffmpeg`, `ffprobe`
- A Gemini API key as `GEMINI_API_KEY=` in `~/.config/gemini/.env` (shared with image-gateway)

**Features:**
- Converts any video or audio input to mono 16 kHz FLAC before uploading
- Splits media longer than about 26 minutes near silences, staying under the API's 30-minute limit when diarization is on
- Speaker diarization and word-level timestamps in verbatim mode, with chapters from `gemini-3.8-flash`
- `--rerender --speakers 'S1=Name,…'` renames speakers in every file without another API call
- Skips files it has already transcribed (matched by file hash), and estimates cost at about $0.005 per minute of audio

#### docs-curator

---

Curates one or more document sources (local folders and git repos, local or remote, 1k to 10k files) before they are ingested into Graphify or another knowledge-graph or RAG tool. It finds duplicates (including the same content in different formats), outdated or superseded revisions and contradictions, and never modifies a source. `analyze` writes proposals to a `decisions.json` the user reviews, and `apply` builds `docs-curator-out/curated/` from the accepted ones, ready for `/graphify docs-curator-out/curated`. The file formats are versioned (schema 1.0).

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, the analyze, review, record, apply workflow, limits, and rules for skills that consume `curated/`
- `config.env`: Saved defaults: similarity thresholds, format rank, environment scope tokens, packet cap, OCR, row cap
- `sources.example.toml`: Annotated example declaring sources with priorities, refs and include/exclude globs
- `references/format.md`: Schemas for `decisions.json`, review packets, verdict files, `_manifest.json`, `quarantine.json` and the frontmatter
- `references/heuristics.md`: What is pre-accepted vs proposed, revision ranking, scope-aware config conflicts, thresholds
- `references/review.md`: How Claude reviews packets, writes verdicts, and fans out to subagents above about 20 packets
- `scripts/curate.py` and `scripts/curator/`: The CLI (`analyze`, `record`, `apply`, `status`) and its modules (Python standard library only)
- `tests/make_fixtures.py` and `tests/smoke_test.py`: Generates a three-source corpus (a folder, a git repo, a `file://` remote) and checks the whole flow

**Output Package:**
- `decisions.json`, `REPORT.md`, `report.html`: Proposals with evidence and `status` (`proposed`, `accept`, `reject`), and the report
- `packets/` and `verdicts/`: Review packets for ambiguous revisions and prose contradictions, and the verdicts recorded for them
- `curated/<source>/<relpath>`: Native Graphify-readable files, hard-linked; pptx, docx, xlsx, pdf and other formats as `<relpath>.md` with provenance frontmatter
- `curated/_manifest.json` and `quarantine.json`: Every curated and unhandled file, and every excluded file with its reason and proposal id

**Requirements:**
- `python3` 3.11 or newer
- `pdftotext` and `pdfinfo` (poppler) for PDFs, `soffice` (LibreOffice) for legacy `.doc`, `.xls` and `.ppt`, `git` for repos
- Optional: `tesseract` for OCR (`DOCS_CURATOR_OCR=1`)

**Features:**
- Sources are read-only; remote URLs are shallow-cloned with the user's git credentials and fetched on re-runs
- Exact, normalized-text and near-duplicate detection across formats, with the keeper chosen by source priority, then format, then recency
- Revision families ranked by explicit markers, version tokens, commit or content dates, and mtime only as a tie-break; low-confidence rankings go to review
- Config conflicts compared per logical file and environment scope, so `application-dev` vs `application-prod` is never flagged
- Re-running `analyze` keeps the user's earlier statuses, and results are cached by sha256 so re-runs are incremental

#### image-gateway

---

Generates or edits images with one command through Google's Gemini API (Interactions API), using saved defaults so routine requests need no setup. Other skills that need an image call this skill instead of writing their own image API code.

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, workflow, cost notes, and troubleshooting
- `config.env`: Saved preferences: default model (`gemini-3-pro-image`, Nano Banana Pro), fallback model (`gemini-nano-banana-2.1`), output directory (`~/Pictures/ai-generated`), and the env file that holds the API key
- `references/api.md`: Current Gemini image request and response shape, model IDs and prices, error meanings, and a raw curl example
- `scripts/generate.sh`: Builds the request, calls the API, saves the image(s), and prints a JSON summary with file paths and estimated cost

**Requirements:**
- `curl`, `jq`, `base64`
- A Gemini API key from a billing-enabled Google project, stored as `GEMINI_API_KEY=...` in `~/.config/gemini/.env` (chmod 600). The image models have no free tier.

**Features:**
- Text-to-image and image editing with up to 14 reference images (local files or URLs)
- Aspect ratio, 1K/2K/4K resolution, PNG/JPEG output, and multiple images per run
- Reads the key from the env file without sourcing it and keeps it out of the process list
- Retries 429/5xx errors with backoff, then falls back once to the cheaper model
- Estimates cost from token usage (about $0.14 per 1K/2K Pro image) and logs every run to `.image-gateway-log.jsonl`
- `--dry-run` prints the request body without calling the API

**Usage:**
```bash
image-gateway/scripts/generate.sh -a 16:9 -o ./assets/hero.png "misty pine forest at sunrise, cinematic"
image-gateway/scripts/generate.sh -i ./photo.jpg "remove the person on the left, keep everything else unchanged"
```

#### mermaid-to-svg

---

Converts Mermaid diagrams to SVG with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli). Takes standalone `.mmd` files, every ```` ```mermaid ```` block in a Markdown file, or diagram text on stdin, and checks that each output is valid before reporting it.

**Key Components:**
- `SKILL.md`: Skill definition with the source, output, render, verify, and fix workflow
- `references/troubleshooting.md`: Common Mermaid syntax pitfalls, rendering problems, Chrome/environment fixes, and a Docker fallback
- `scripts/render.sh`: Wraps `mmdc` (pinned version via `npx`), reuses a system Chromium, applies sandbox flags when needed, and validates the SVG output

**Requirements:**
- `node` / `npx`: Runs mermaid-cli
- Chrome or Chromium: Used by mermaid-cli to draw diagrams (downloaded by puppeteer if none is installed)

**Features:**
- `--portable` mode draws labels as SVG `<text>` instead of HTML `<foreignObject>`, so they show up in Inkscape, Office, ImageMagick, rsvg, and PDF tools
- Theme, background, and Mermaid config options, with any other `mmdc` flag passed through
- Optional PNG/PDF output, plus a preview step for checking the result visually
- Never rewrites the source Markdown in place

#### visible-delegation

---

Delegates a bounded task to another coding-agent session (Claude Code or opencode) running in a [herdr](https://herdr.dev) pane the user can watch. Inside herdr, the delegate gets a sibling pane in the supervisor's tab; outside herdr, it gets a workspace in a dedicated `delegates` session the user attaches to with `herdr session attach delegates`. The supervising agent launches, monitors, verifies, and cleans up the delegate.

**Key Components:**
- `SKILL.md`: Skill definition with supervision workflow, approval policy, and reporting format
- `references/delegate-addendum.md`: Supervision instructions appended to the delegate's goal prompt
- `scripts/lib.sh`: Shared helpers sourced by the other scripts (run metadata, agent status, screen reading, event context)
- `scripts/launch.sh`: Creates the pane, starts the agent with `herdr agent start`, and submits the goal prompt with `herdr agent prompt` (adds destructive-command deny rules and a fixed session id for Claude)
- `scripts/watch.sh`: Background watcher that blocks on `herdr agent wait` and reports completion, prompts, risky commands, idling, heartbeats, and a vanished agent
- `scripts/say.sh`: Sends messages, files, or keys to the delegate through herdr
- `scripts/cleanup.sh`: Saves the screen and Claude transcript, exits the agent, closes its pane or workspace, and stops the delegates session when empty

**Requirements:**
- `herdr`: Terminal workspace manager that hosts the delegate
- `jq`: Parses herdr's JSON output

**Features:**
- Visible execution in a `deleg-<slug>` herdr pane, never a hidden background run
- Supports Claude Code (default) and opencode delegates
- Monitoring with clear intervene-vs-wait rules and an approval policy for delegate prompts
- Independently re-runs every verification gate before reporting results
- Refuses to close a session while the user is attached unless forced

---

## Contributing

### Development Setup

1. Fork the repository
2. Enable the shared git hooks (once per clone, since git does not copy hooks):
   ```bash
   git config core.hooksPath .githooks
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feature/add-new-skill
   ```
4. Make your changes
5. Test your skill in an opencode session
6. Submit a pull request

### Code Style

- Follow existing SKILL.md structure and formatting
- Use clear, concise language
- Include examples for complex behaviors
- Test your skill before submitting

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `revert`

Examples:
```
feat(skill): Add new skill for code review
docs(skill): Update generate-readme documentation
fix(skill): Resolve commit-staged-changes validation
```

The `commit-msg` hook rejects messages that don't match this format: a known type, optional lowercase scope, capitalized summary, no trailing period, and a subject of at most 50 characters.

### Versioning

Every skill has a [Semantic Versioning](https://semver.org) number in its `SKILL.md` frontmatter:

```yaml
---
name: visible-delegation
description: ...
metadata:
  version: 1.0.0
---
```

Bump it by how much the change affects people and agents using the skill:

| Level | When | Examples |
|-------|------|----------|
| **Major** (`X.0.0`) | The change breaks how the skill is used or what it depends on. | Renaming the skill; removing or renaming a script, argument, or output format; adding or swapping a required external tool; changing a structure another skill depends on. |
| **Minor** (`x.Y.0`) | New, backwards-compatible capability. | A new optional script, flag, mode, or reference file; support for another agent CLI; broader trigger conditions. |
| **Patch** (`x.y.Z`) | Fixes and wording that don't change the interface. | Script bug fixes; clarified instructions; typo and formatting fixes; description tweaks. |

The level follows the commit type:

- `feat` means minor.
- `fix`, `docs`, `style`, `refactor`, `perf`, and `revert` mean patch.
- `chore`, `test`, `ci`, and `build` mean no bump.
- `feat!:` (any type with `!`) or a `BREAKING CHANGE:` footer means major.

Each skill is bumped **at most once per pull request**, at the highest level of any commit in the PR that touches it. For example, `fix` + `fix` + `feat` on a skill at `1.2.3` merges as `1.3.0`. A change touching several skills bumps each one separately; a change touching only repo files such as `README.md` bumps nothing. A new skill starts at `1.0.0`.

With the hooks enabled, this happens automatically. After each commit on a feature branch, the `post-commit` hook sets every skill the commit touched to its target version and amends it into the same commit:

```text
target = (version at the merge-base with origin/main)
         bumped once by the highest level among the branch's commits touching the skill
```

Because the target is recomputed from the base each time, amending or rebasing gives the same result instead of stacking bumps. The hook skips merges, rebases, cherry-picks, and commits made directly on `main`, and keeps a version set by hand above the target. To use a base branch other than `origin/main`, run `git config skills.versionBase <ref>`.

To bump by hand, for example to fix a wrong level or declare a breaking change the commit messages don't mark:

```bash
scripts/bump-version.sh <skill> <major|minor|patch>
```

Update the **Version** column in [Available Skills](#available-skills) when a skill's version changes.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Generated with STANDARD fidelity level*
