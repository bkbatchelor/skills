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
   cp -r docs/generate-readme /path/to/your/project/.opencode/skills/
   cp -r git/commit-staged-changes /path/to/your/project/.opencode/skills/
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
├── git/                      # Git workflow skills
│   └── commit-staged-changes/    # Git commit skill
│       ├── SKILL.md              # Skill definition
│       ├── README.md             # Install and usage
│       ├── README.md             # Install and usage
│       └── references/           # Reference materials
│           └── git-commit-template.md
├── docs/                     # Documentation skills
│   ├── generate-readme/          # README generation skill
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Install and usage
│   │   ├── README.md             # Install and usage
│   │   └── references/           # Reference materials
│   │       ├── basic-level-template.md
│   │       ├── standard-level-template.md
│   │       └── advance-level-template.md
│   ├── code-graph/               # Code knowledge graph skill (codegraph) and code-to-docs change check
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Overview, applies_to links, files
│   │   └── scripts/              # Helper scripts
│   │       ├── check_env.sh      # codegraph installed? repo indexed?
│   │       └── diff_links.sh     # Changed files -> documents that constrain them, docs graph freshness
│   ├── docs-curator/             # Document curation skill for Graphify
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Skill overview, usage, and output layout
│   │   ├── plan/                 # Build plan and decisions
│   │   │   ├── PLAN.md           # Build plan
│   │   │   └── DECISIONS.md      # Settled decisions and departures from the plan
│   │   ├── docs/                 # Supporting documentation
│   │   │   └── How docs-curator works.md  # Technical walkthrough of curate.py, with Mermaid architecture diagram
│   │   ├── requirements.txt      # Pinned Python dependencies
│   │   ├── references/           # Reference materials
│   │   │   └── verdict-schema.md
│   │   ├── scripts/              # Helper scripts
│   │   │   ├── curate.py         # analyze, update, apply and link commands
│   │   │   └── check_env.sh      # Dependency check
│   │   ├── docker/               # Reference image
│   │   │   └── Dockerfile
│   │   └── tests/                # Dev only: corpus, answer key, scorer, pytest suite
│   │       ├── make_corpus.py
│   │       ├── corpus_expected.yaml
│   │       ├── score.py
│   │       ├── conftest.py
│   │       ├── test_units.py
│   │       ├── test_pipeline.py
│   │       ├── test_requirement_adr.py
│   │       ├── test_routing.py
│   │       └── fixtures/verdicts/    # Hand-written verdicts, one per cluster
│   ├── knowledge-graph/          # Repeatable docs + code graph pipeline (kg script)
│   │   ├── SKILL.md              # Skill definition: workflow, gates, exit codes, hard rules
│   │   ├── README.md             # What kg automates, layout, usage
│   │   ├── scripts/
│   │   │   └── kg.py             # Pipeline script (PEP 723, uv run --python 3.12 --script)
│   │   └── tests/
│   │       └── test_kg.py        # pytest suite
│   ├── mermaid-to-image/           # Mermaid diagram rendering skill
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Install, requirements, usage
│   │   ├── references/           # Reference materials
│   │   │   └── troubleshooting.md
│   │   ├── styles/               # Modern look (Archify-inspired) config files
│   │   │   ├── modern-dark.json
│   │   │   ├── modern-light.json
│   │   │   └── canvases.json
│   │   └── scripts/              # Helper scripts
│   │       └── render.sh
│   └── html-artifacts/           # HTML artifact skill
│       ├── SKILL.md              # Skill definition
│       ├── README.md             # Install, usage, house style summary
│       ├── README.md             # Install, usage, house style summary
│       ├── references/           # Reference materials
│       │   └── template.html     # Starter page: tokens, components, every layout pattern
│       └── scripts/              # Helper scripts
│           └── verify.sh         # Screenshots in light and dark, console and offline checks
├── media/                    # Image and audio/video skills
│   ├── image-gateway/            # Image generation and editing skill
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Install, options, configuration
│   │   ├── README.md             # Install, options, configuration
│   │   ├── config.env            # Saved defaults (model, output dir, key file)
│   │   ├── references/           # Reference materials
│   │   │   └── api.md
│   │   └── scripts/              # Helper scripts
│   │       └── generate.sh
│   └── media-transcription/      # Audio/video transcription skill
│       ├── SKILL.md              # Skill definition
│       ├── README.md             # Install, usage, output package
│       ├── README.md             # Install, usage, output package
│       ├── config.env            # Saved defaults (models, key location, prices)
│       ├── references/           # Reference materials
│       │   ├── api.md
│       │   └── format.md
│       └── scripts/              # Helper scripts
│           └── transcribe.py
├── research/                 # Research and ingestion skills
│   ├── current-info-search/      # Live search for fast-changing facts
│   │   ├── SKILL.md              # Skill definition
│   │   ├── README.md             # Install, requirements, usage
│   │   ├── README.md             # Install, requirements, usage
│   │   ├── config.env            # Saved defaults (model, key file, NotebookLM CLI)
│   │   └── scripts/              # Helper scripts
│   │       └── search.py
│   └── heavy-file-ingestion/     # PDF/Office/large text to chunked Markdown
│       ├── SKILL.md              # Skill definition
│       ├── README.md             # Install, requirements, output layout
│       ├── README.md             # Install, requirements, output layout
│       └── scripts/              # Helper scripts
│           └── ingest.py
├── efficiency/               # Token and context discipline skills
│   └── token-saver/              # Token discipline skill
│       ├── SKILL.md              # Skill definition
│       ├── README.md             # Install, usage, helper commands, state location
│       └── scripts/              # Helper scripts
│           └── tokensaver.py     # search, count, fields, dates, diff, accept, current
├── testing/                  # Testing and verification skills
│   ├── testing-runbook-creator/  # Repo-local testing runbook skill
│   │   ├── SKILL.md              # Skill definition
│   │   └── README.md             # Install, runbook location, entry fields, rules
│   └── page-testing-memory/      # General web page QA process; page facts stay in repo runbooks
│       ├── SKILL.md              # Skill definition
│       └── README.md             # Install, usage, knowledge split
└── delegation/               # Agent delegation skills
    ├── goal-prompt-generator/    # Goal prompt generation skill
    │   ├── SKILL.md              # Skill definition
    │   ├── README.md             # Install and usage
    │   ├── README.md             # Install and usage
    │   └── references/           # Reference materials
    │       └── goal-prompt-template.md
    └── visible-delegation/       # Visible agent delegation skill
        ├── SKILL.md              # Skill definition
        ├── README.md             # Install, requirements, usage
        ├── README.md             # Install, requirements, usage
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

Each skill's `SKILL.md` description and `## Triggers` section define when it activates and when it should be skipped.

| Skill | Description | Key Files |
|-------|-------------|-----------|
| commit-staged-changes | Commits staged changes using conventional commit format | `SKILL.md`, `README.md`, `references/git-commit-template.md` |
| generate-readme | Generates or updates README files at three fidelity levels, verifying commands and diagrams against the repo | `SKILL.md`, `README.md`, `references/basic-level-template.md`, `references/standard-level-template.md`, `references/advance-level-template.md` |
| goal-prompt-generator | Turns a plan or task into a self-contained, verifiable goal prompt | `SKILL.md`, `README.md`, `references/goal-prompt-template.md` |
| current-info-search | Answers questions about fast-changing facts from live Google Search (Gemini grounding) and NotebookLM web research, with dated, primary-source citations | `SKILL.md`, `README.md`, `config.env`, `scripts/search.py` |
| media-transcription | Transcribes audio/video into a Markdown transcript, word timestamps, speakers, chapters, and captions with Gemini 3.5 Transcribe | `SKILL.md`, `README.md`, `config.env`, `references/api.md`, `references/format.md`, `scripts/transcribe.py` |
| image-gateway | Generates or edits images with Google's Gemini API (Nano Banana Pro) using saved defaults | `SKILL.md`, `README.md`, `config.env`, `references/api.md`, `scripts/generate.sh` |
| heavy-file-ingestion | Converts PDFs, Office files, and large CSV/text into chunked Markdown plus an INDEX.md before analysis | `SKILL.md`, `README.md`, `scripts/ingest.py` |
| html-artifacts | Renders dense or visual output as one offline HTML file in a house style, verified by headless screenshots | `SKILL.md`, `README.md`, `references/template.html`, `scripts/verify.sh` |
| code-graph | Answers code questions with codegraph (never installs it; `codegraph init` only after approval) and checks a code change against the ADRs and design docs that constrain it, reading the docs graph read-only | `SKILL.md`, `README.md`, `scripts/check_env.sh`, `scripts/diff_links.sh` |
| docs-curator | Curates a read-only document folder into a deduplicated Markdown staging tree for Graphify, with an `update` command for added or modified files: removes duplicates and superseded revisions, flags contradictions and conflicting names, checks business requirements against ADRs, and routes classification and cluster review to different models by difficulty | `SKILL.md`, `README.md`, `docs/How docs-curator works.md`, `plan/PLAN.md`, `plan/DECISIONS.md`, `requirements.txt`, `references/verdict-schema.md`, `scripts/curate.py`, `scripts/check_env.sh`, `docker/Dockerfile` |
| knowledge-graph | Repeatable docs-graph and code-graph pipeline around docs-curator, Graphify and codegraph: one `kg` script with a branch and clean-tree gate, PHI hard stop, snapshots and restore, verdict and community-label carry-forward, a stop for docs-curator's classifier labels and deep re-reviews before `apply`, node-loss check and token-cost estimate | `SKILL.md`, `README.md`, `scripts/kg.py`, `tests/test_kg.py` |
| mermaid-to-image | Renders Mermaid diagrams to validated SVG, PNG, or PDF files, with an optional modern Archify-style look (rounded frame, background canvases), using mermaid-cli | `SKILL.md`, `README.md`, `references/troubleshooting.md`, `scripts/render.sh`, `styles/modern-{dark,light}.json`, `styles/canvases.json` |
| token-saver | Keeps the rest of a job cheap: local code before a model, bounded passage search, one accepted result to revise from, minimal tools, answers sized to the request | `SKILL.md`, `README.md`, `scripts/tokensaver.py` |
| testing-runbook-creator | Keeps a repo-local testing runbook (`docs/testing-runbook.md` by default): read before any testing, record discoveries as you go, fix the entry when reality differs; entries hold steps, safe vs destructive actions, seed, cleanup and exact verification commands | `SKILL.md`, `README.md` |
| page-testing-memory | Teaches the general web page QA process (states, forms, auth boundaries, breakpoints, screenshot evidence) and keeps every page-specific fact in the repo's testing runbook, partnering with testing-runbook-creator | `SKILL.md`, `README.md` |
| visible-delegation | Delegates work to another agent session in a watchable herdr pane | `SKILL.md`, `README.md`, `references/delegate-addendum.md`, `scripts/lib.sh`, `scripts/launch.sh`, `scripts/watch.sh`, `scripts/say.sh`, `scripts/cleanup.sh` |
| visible-delegation | Delegates work to another agent session in a watchable herdr pane | `SKILL.md`, `README.md`, `references/delegate-addendum.md`, `scripts/lib.sh`, `scripts/launch.sh`, `scripts/watch.sh`, `scripts/say.sh`, `scripts/cleanup.sh` |

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
- `SKILL.md`: Skill definition: workflow, verification and diagram rules
- `references/basic-level-template.md`: BASIC level template
- `references/standard-level-template.md`: STANDARD level template
- `references/advance-level-template.md`: ADVANCE level template

**Fidelity Levels:**
- **BASIC**: Project name, tech stack, getting started, usage
- **STANDARD**: BASIC + structure, modules, contributing, license
- **ADVANCE**: STANDARD + architecture diagrams, configuration, API reference, testing, deployment

**Features:**
- Infers the fidelity level from the request and asks only when unclear
- Keeps accurate human-written content when updating an existing README
- Respects `.gitignore` through git's own file listing
- Backs up the old README (`README.n.md`) only when git cannot recover it
- Verifies commands, paths and Mermaid blocks before writing; unverified items are dropped or marked `TODO: verify`
- Draws only diagrams the codebase supports (ADVANCE level)

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

#### current-info-search

---

Looks up fast-changing facts (model releases, pricing, software versions, news, APIs) live instead of answering from training data. Gemini with Google Search grounding runs first; NotebookLM web research runs second for questions that need synthesis across many sources.

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, the Gemini curl example, the `notebooklm` command sequence, and the answering rules
- `config.env`: Saved defaults: Gemini model, API key env file, NotebookLM CLI name and timeout
- `scripts/search.py`: `gemini` and `notebook` subcommands (Python standard library only)

**Requirements:**
- `python3`
- A Gemini API key as `GEMINI_API_KEY`, exported or in `~/.config/gemini/.env` (shared with image-gateway)
- For the `notebook` subcommand: the `notebooklm` CLI (notebooklm-py), signed in with `notebooklm login`

**Features:**
- Defaults to `gemini-3.8-flash`, overridable per call with `--model`
- Resolves Google's grounding redirect links to the real source URLs
- NotebookLM runs use a throwaway notebook that is deleted afterward, so existing notebooks are never touched
- Answers must cite dates and primary sources, and search results win over training data

#### heavy-file-ingestion

Converts PDFs, Office documents, and large CSV/text files into chunked Markdown plus an `INDEX.md` before any analysis, so the original file is never read directly.

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, the ingest command, and the rules for reading the artifacts
- `scripts/ingest.py`: Converts the source and writes the chunked artifacts and `INDEX.md`

**Requirements:**
- `uv` and `python3`
- `markitdown` (required) for Office files and as the PDF fallback when poppler is missing
- Recommended: poppler (`pdftotext`, `pdfinfo`, `pdfimages`, `pdftoppm`) for PDFs
- Optional: `libreoffice` for legacy formats; `tesseract` for scanned pages (run by hand, not by the script)

**Features:**
- Splits PDFs, decks, spreadsheets, CSVs, and text into chunks of about 25k characters or less
- Writes output to `_ingested/<source-stem>/` next to the source, or `~/.cache/heavy-file-ingestion/<hash>/` if that folder is not writable
- Skips re-ingesting a source whose SHA-256 is unchanged
- `--check` reports which external tools are installed and what each missing one costs; a missing poppler also prints a stderr warning during PDF ingest

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
media/image-gateway/scripts/generate.sh -a 16:9 -o ./assets/hero.png "misty pine forest at sunrise, cinematic"
media/image-gateway/scripts/generate.sh -i ./photo.jpg "remove the person on the left, keep everything else unchanged"
```

#### mermaid-to-image

---

Converts Mermaid diagrams to SVG, PNG, or PDF, optionally in a modern Archify-inspired style, with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli). Takes standalone `.mmd` files, every ```` ```mermaid ```` block in a Markdown file, or diagram text on stdin, and checks that each output is valid before reporting it.

**Key Components:**
- `SKILL.md`: Skill definition with the source, output, render, verify, and fix workflow
- `README.md`: Install, requirements, and usage examples
- `references/troubleshooting.md`: Common Mermaid syntax pitfalls, rendering problems, Chrome/environment fixes, and a Docker fallback
- `scripts/render.sh`: Wraps `mmdc` (pinned version via `npx`), reuses a system Chromium, applies sandbox flags when needed, and validates the SVG and PNG output
- `styles/modern-dark.json`, `styles/modern-light.json`: Mermaid config (`themeVariables` plus `themeCSS`) behind `--style modern`
- `styles/canvases.json`: Background canvases (page colour plus root-element CSS) behind `--canvas`, which `render.sh` injects into the SVG

**Requirements:**
- `node` / `npx`: Runs mermaid-cli
- Chrome or Chromium: Used by mermaid-cli to draw diagrams (downloaded by puppeteer if none is installed). A system Chrome is also needed for PNG and PDF output with `--canvas` patterns

**Features:**
- `--portable` mode draws labels as SVG `<text>` instead of HTML `<foreignObject>`, so they show up in Inkscape, Office, ImageMagick, rsvg, and PDF tools
- `--style modern` applies an Archify-inspired look before rendering: rounded, tinted nodes, dashed rounded groups, slate edges, a JetBrains Mono font stack with system fallbacks (not embedded), and a rounded frame enclosing the whole diagram, with the background clipped to it. `--style-mode dark|light` (default dark) picks the variant and sets the page colour unless `-b` is given; a `-c` config overrides the style
- `--canvas blank|dots|grid|blueprint` (implies `--style modern`, default `blank`) picks the background, each in dark and light: flat, a 20px dot grid, a 40px grid, or a 32px blueprint grid. With a style, PNGs and PDFs are made from the finished SVG with the system Chrome, so `--size` and extra `mmdc` args don't apply to them; non-browser viewers ignore the patterns
- Theme, background, and Mermaid config options, with any other `mmdc` flag passed through
- `--png` writes a PNG beside each SVG (`<stem>-N.png` for Markdown blocks), with `--scale N` (default 2) and `--size N`; PNGs are transparent unless `-b` is given
- PDF output by naming a `.pdf` path, plus a preview step for checking the result visually
- Never rewrites the source Markdown in place

#### docs-curator

---

Curates a large, read-only folder of documents (`.pptx .pdf .md .xlsx .txt .docx .xml .json .csv .yaml .yml`) into a staging tree ready for [Graphify](https://pypi.org/project/graphifyy/). It removes byte-identical, cross-format, and near duplicates, excludes superseded revisions, and flags contradictions, conflicting filenames, and identifier collisions. Output defaults to `~/curated/<project-name>/`, and `graphify-out` and `.docs-curator` symlinks in the project point there so Graphify's output and the working files stay out of it. Apart from those symlinks (and an optional `--gitignore project|global` entry) it never modifies the source. At the end it asks before building the docs graph with Graphify, per run; it never starts Graphify without that approval. Code is not staged or mapped here: the [code-graph](#code-graph) skill covers it, and a doc can link to code with `applies_to:` front matter, listed in the report.

**Key Components:**
- `SKILL.md`: Skill definition with triggers, the analyze, review, apply workflow, and hard rules
- `README.md`: User-facing guide to invoking the skill, what Claude does at each phase, the output layout (where `.docs-curator/` and `staging/` are written), and how to adjust results
- `docs/How docs-curator works.md`: Technical walkthrough of `curate.py` (analyze, update, decide, apply, link), with a Mermaid architecture diagram
- `scripts/curate.py`: `analyze` (deterministic inventory, extraction, grouping, clustering, queue), `update` (re-analyze after files were added, modified or removed, report the changes, queue only affected clusters), `apply` (verdicts and overrides to `staging/`, `REPORT.md`, `decisions.jsonl`), and `link` (symlinks `<source>/graphify-out` and `<source>/.docs-curator` into `<out>`; `--gitignore project|global` adds `.docs-curator` to a gitignore)
- `references/verdict-schema.md`: JSON schema for the per-cluster verdict files the assistant writes between the two phases
- `scripts/check_env.sh`: Exits 0 when provisioned, otherwise names what is missing
- `requirements.txt`: Pinned Python dependencies (`graphifyy==0.9.103` is installed only to check its accepted extensions in tests)
- `docker/Dockerfile`: Reference image (Python 3.11, LibreOffice, cached embedding model)
- `plan/DECISIONS.md`: Every settled decision and where the build departed from `plan/PLAN.md`
- `tests/`: Dev-only synthetic corpus generator with an answer key, `score.py`, fixture verdicts, and a pytest suite, including `test_requirement_adr.py` for the requirement-versus-ADR check and `test_routing.py` for classification and review routing (not needed at runtime)

**Requirements:**
- `uv` and Python 3.11+ (pass `--python 3.12` so uv fetches it); run through `uv run --no-project --python 3.12 --with-requirements requirements.txt python scripts/curate.py ...`
- The `heavy-file-ingestion` skill (required: converts PDF, Word, Excel and PowerPoint files to Markdown during `analyze`) and `pdftotext` (poppler)
- `soffice` (LibreOffice) to convert kept `.pptx` decks to PDF
- First run downloads the `BAAI/bge-small-en-v1.5` embedding model; `embedding_backend: tfidf` in `config.yaml` avoids it

**Features:**
- Three phases: `analyze`, a per-cluster LLM review that writes verdict files, then `apply`; an approval-gated docs-graph step follows
- Exact, cross-format (for example a deck and its PDF export), and near-duplicate detection with MinHash and rapidfuzz; near duplicates are flagged and kept unless `near_duplicate_action: exclude`
- Revision chains from filename markers, in-text versions and dates, document properties, and mtime; a file is excluded as superseded only with two agreeing signals or a confident verdict
- Every kept document except `.pptx` is staged as Markdown with front matter (`source_path`, `source_format`, `sha256`, `status`, `description`); decks become a PDF plus a speaker-notes sidecar
- `_curated/CONFLICTS.md` for contradictions (quotes are checked against the text) and `_curated/historical/` for superseded files with unique content
- Requirement-versus-ADR check: documents typed by front matter or path globs are paired by id and by similarity; conflicts go to `CONFLICTS.md`, gaps and unlinked items to the report; report only, no winner picked
- Optional classification pre-step (`classify_untyped: true`): untyped documents are queued in batches for a small model (Haiku by default) to label as requirement, ADR or other; labels are keyed by content hash, applied above `classify_min_confidence`, and never override front matter or globs
- Per-cluster review routing: each queue item names a tier and model alias (Sonnet for ordinary clusters; Opus for requirement-vs-ADR checks, unorderable revision chains and large clusters), `work/routing.json` groups them, and a standard-tier verdict that finds a conflict or an unsure supersession is re-queued once at the deep tier. The script only records the aliases; it never calls a model
- `applies_to:` front matter ties a document to code paths or symbols; the report lists the links and flags paths missing from the source
- Optional `config.yaml` and `overrides.yaml` in the output folder; a second run on an unchanged corpus processes nothing new
- `--no-extract <glob>` on `analyze`/`update`: matching files (e.g. PHI folders) are hashed but never opened, and excluded in a way no override can undo
- Every staged text file ends with a newline, so graphify's coverage check never flags it as partly read
- `update` handles a corpus that changed after a finished run: it reports added, modified and removed files in `changes.json` and queues only the clusters containing a new or modified file
- Thresholds are tuned on a synthetic corpus only; spot-check the first real run

**Usage:**
```bash
RUN="uv run --no-project --python 3.12 --with-requirements docs/docs-curator/requirements.txt"
$RUN python docs/docs-curator/scripts/curate.py analyze --source ~/docs --out ~/curated/docs
# review each cluster in ~/curated/docs/.docs-curator/work/queue/, write verdicts, then:
$RUN python docs/docs-curator/scripts/curate.py apply --source ~/docs --out ~/curated/docs
$RUN python docs/docs-curator/scripts/curate.py link --source ~/docs --out ~/curated/docs   # ~/docs/graphify-out and ~/docs/.docs-curator -> ~/curated/docs/
```

#### code-graph

---

Maps source code with [codegraph](https://github.com/colbymchenry/codegraph), a code knowledge graph, and keeps it separate from the document graph that [docs-curator](#docs-curator) and Graphify build. It also checks a code change against the documents that constrain it, such as ADRs, by reading the docs graph read-only. The check is advisory and reports each candidate as consistent, possibly conflicting, or can't tell.

**Key Components:**
- `SKILL.md`: Skill definition with the setup gate, how to answer code questions, the change-check procedure, and hard rules
- `README.md`: Overview, how to link an ADR to code with `applies_to`, and the file list
- `scripts/check_env.sh`: Exits 0 when codegraph is installed and the repo is indexed, 1 when codegraph is missing, 2 when the repo is not indexed
- `scripts/diff_links.sh`: Lists changed files and the Markdown documents that list them under `applies_to` or name them, and reports whether the docs graph is missing, ok, or stale

**Requirements:**
- `codegraph` on the PATH (the skill never installs it)
- For the change check, optionally the `graphify` CLI and a docs graph built by docs-curator

**Features:**
- Runs `codegraph init` only after the user approves in that turn; falls back to grep and Read if declined
- Answers from `codegraph explore`, `node`, `context` and `query` before grep or Read, and runs `sync` first when the index is behind
- Change check: exact links from `applies_to` front matter, fuzzy matches from document text, a read-only `graphify query` on the docs graph, and a plain text search of the repo's Markdown when the graph is missing or stale
- Never builds or edits the docs graph; the two graphs are never merged

**Usage:**
```bash
bash docs/code-graph/scripts/check_env.sh .          # exit 0 ready, 1 codegraph missing, 2 not indexed
bash docs/code-graph/scripts/diff_links.sh --base main .
```

#### knowledge-graph

---

Packages the docs-graph and code-graph process for a repository into one repeatable pipeline. [docs-curator](#docs-curator) curates the documents, Graphify builds the docs graph, and [codegraph](#code-graph) indexes the code. The `kg` script runs every deterministic step and holds the workarounds those tools need. The skill does the steps that need judgment (cluster verdicts, Graphify extraction, naming new communities) and asks before spending tokens.

**Key Components:**
- `SKILL.md`: The run sequence (curate, review, apply, graph prepare, ask, Graphify with check and labels, finish, code), gating, restore, exit codes, and hard rules
- `README.md`: What kg automates, the `~/curated/<repo>/` layout, and usage
- `scripts/kg.py`: Subcommands `init`, `preflight`, `overrides`, `curate`, `review`, `apply`, `graph prepare|check|fixups|labels|finish`, `code`, `status`, `restore`, `all` and `install-shim`
- `tests/test_kg.py`: pytest suite (gating, overrides, PHI, carry-forward, classifier batches and escalation, node-loss check, labels, snapshots, links, manifest re-keying)

**Requirements:**
- `uv` (Python 3.12 is fetched), the `graphify` CLI 0.9.103 or later with its skill, `codegraph`, and the docs-curator, heavy-file-ingestion and code-graph skills. kg installs none of them

**Features:**
- Per-repo settings in `~/curated/<repo>/kg.yaml`, kept with `config.yaml` and `overrides.manual.yaml` in that folder's own git repo
- Docs steps only run on `main`, `develop` or `develop-*` with a clean tree; `--allow-any-branch` overrides this and is logged. `codegraph sync` runs on any branch
- PHI globs: always excluded, their extracted text purged after every analyze, and any trace in the cache, staging or graph stops the run (exit 4)
- `overrides.yaml` generated from git plus the exclude groups, using file rules imported from docs-curator's `curate.py`
- With docs-curator's `classify_untyped` on, `kg curate` stops (exit 3) before cluster bookkeeping until untyped documents are labelled, then re-clusters; `kg review` lists batches to label and standard-tier verdicts queued for a deeper re-review, and `kg apply` refuses until both are done; labels are snapshotted
- Verdicts carried to re-numbered clusters when membership overlaps by at least 80%, with moved files followed; only the new members go to review
- Clusters where fewer than two members can reach staging are auto-closed (`kg_auto`) and reopened if an override change gives them a second
- Keeper-chain check for documents that silently left staging
- Snapshots before each curate and each graph run (keeps 3) and `kg restore`
- Token-cost estimate with a cap, a list of oversized files, lost nodes sorted into explained and unexplained before `force=True`, and community labels carried forward at 50% agreement
- Re-keys graphify manifests written by older versions, so `--update` re-extracts only the files that changed
- Graph exclude rules in `kg.yaml` (`graph.excludes`, gitignore-style) written into graphify's exclude file on every run, with nodes of newly excluded files pruned
- `graph-fixups.yaml` per repo: hand-reviewed links and duplicate-node merges re-applied after every graph run (`kg graph fixups`); self-loops always dropped
- Repo symlinks written in `$HOME` form; codegraph telemetry kept off

**Usage:**
```bash
KG="uv run --quiet --python 3.12 --script docs/knowledge-graph/scripts/kg.py"
$KG init ~/Projects/my-repo && $KG preflight --fix
$KG status
$KG all          # stops before the first step that needs a person
```

#### html-artifacts

---

Renders dense or visual output (plans, reports, research explainers, review summaries, comparisons, timelines, diagrams, walkthroughs, dashboards) as one self-contained HTML file in a fixed house style, instead of a long chat reply. The chat gets a short summary and the file path.

**Key Components:**
- `SKILL.md`: Skill definition with trigger conditions, hard rules, the house style tokens, layout patterns, and the verify-before-done rule
- `README.md`: Install, usage, requirements, and a summary of the house style
- `README.md`: Install, usage, requirements, and a summary of the house style
- `references/template.html`: Starter page with the tokens, components, theme toggle, print styles, and an example of each layout pattern
- `scripts/verify.sh`: Renders the file with headless Chromium and checks the result

**Requirements:**
- Chromium or Chrome (`chromium`, `chromium-browser`, or `google-chrome`) for the verify step; without it the skill reports that the render could not be verified

**Features:**
- Produces an artifact on an explicit request, and offers one in a single line when an answer would run past about 40 lines or hold a table wider than 3 columns
- One `.html` file with inline CSS and JS, no external dependencies, and full content with JS off
- Dark-first teal on slate, with Inter and JetBrains Mono system stacks, a 4px spacing scale, and an OS-following theme with a toggle
- Layout patterns for report, comparison table, timeline, diagram, dashboard, and walkthrough
- `verify.sh` takes full-height screenshots at 1280 and 390 px in the default and a forced-dark theme, fails on console errors or any external URL, and the skill requires reading the screenshots before declaring the artifact done
- Saves to `~/artifacts/<YYYY-MM-DD>-<slug>.html` (or `./artifacts/` for project-specific work) and always prints the path

**Usage:**
```bash
docs/html-artifacts/scripts/verify.sh ~/artifacts/2026-10-24-my-report.html
```

#### token-saver

---

Token discipline for the rest of a job. It cannot erase the call it was loaded into; it only makes the work after it smaller.

**Key Components:**
- `SKILL.md`: Seven rules (local code first, search then send only matches, one accepted result, minimal tools, smaller model only when the whole job wins, answer sized to the request, one bounded repair) and the usage-reporting rule
- `README.md`: Install, usage, helper commands, and where the accepted result is stored
- `scripts/tokensaver.py`: `search` (capped passages, `--skip N` for one more bounded pull), `count`, `fields` (CSV/TSV/JSON/JSONL), `dates` (ISO 8601), `diff`, `accept`, `current`

**Requirements:**
- `python3` (standard library only)

**Features:**
- Keeps one accepted result per job at `~/.claude/state/token-saver/<job-slug>/accepted.md`; rejected results are never saved
- Never retries a token-limit or usage-limit failure; reduces the input instead
- Reports usage numbers only when the harness provides them, otherwise `unavailable`
- The skill picks the job slug and runs the script itself, so the user manages no state file or paths

#### testing-runbook-creator

---

Makes testing knowledge persist in the repo. Triggers on any testing, verification, smoke-testing, QA, or debugging activity, not only when a runbook is mentioned.

**Key Components:**
- `SKILL.md`: Four rules (read first, update on mismatch, record as you go, record only what is reusable), the entry format, and the hard rules
- `README.md`: Install, runbook location, entry fields

**Requirements:**
- None

**Features:**
- Runbook location: an existing testing doc wins, else `docs/testing-runbook.md`, else `TESTING-RUNBOOK.md` at the repo root; created at the first discovery
- Entry fields: Scope, Last verified (date and commit), Prerequisites / seed, Steps, Safe actions, Destructive actions, Verification (exact command plus expected output), Cleanup, Gotchas
- Never records secrets, never runs destructive steps without approval, never commits the runbook on its own

**Usage:**
```bash
ln -s "$PWD/testing/testing-runbook-creator" ~/.claude/skills/testing-runbook-creator
```

#### page-testing-memory

---

Global process for QA of any web page or UI, with a hard split: the process lives in the skill, and every page-specific fact lives in the repo's testing runbook.

**Key Components:**
- `SKILL.md`: Trigger conditions, the knowledge-split table, the QA process (page states, form testing, auth boundaries, breakpoints 375/768/1024/1440, screenshot evidence, reporting), the write-it-down-now rule, the leak test, and safety rules
- `README.md`: Install and usage

**Requirements:**
- `testing-runbook-creator` (owns the runbook location, entry format, and no-secrets rule)
- Some browser automation in the target repo; the skill is tool-agnostic

**Features:**
- Selectors, routes, test accounts, seed data, and cleanup quirks go into the repo runbook the moment they are learned
- Wanting to add a project detail to the skill is the signal it belongs in the repo runbook
- Screenshots go to a temp or scratchpad directory and are not committed unless the runbook says so
- Runs only against local or non-production environments; destructive actions need approval

**Usage:**
```bash
ln -s "$PWD/testing/page-testing-memory" ~/.claude/skills/page-testing-memory
```

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
scripts/bump-version.sh <skill> <major|minor|patch>   # <skill> is a name or a path such as docs/generate-readme
```

Update the **Version** column in [Available Skills](#available-skills) when a skill's version changes.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Generated with STANDARD fidelity level*
