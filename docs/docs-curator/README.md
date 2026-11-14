# docs-curator

docs-curator is a Claude Code skill, a set of instructions that Claude follows for one kind of task. This one cleans up a large folder of documents before you build a knowledge graph from them. A knowledge graph is a map of your documents that shows how they connect, and you can ask it questions. The skill works with the file types `.pptx .pdf .md .xlsx .txt .docx .xml .json .csv .yaml .yml`. You build the graph with [Graphify](https://pypi.org/project/graphifyy/), a tool that builds knowledge graphs.

The skill finds duplicates and outdated revisions. It flags documents that contradict each other. It writes the documents worth keeping into a separate, tidy folder. Your original folder is never changed. At the end, the skill offers to build the knowledge graphs. It runs Graphify only if you say yes.

## Using the skill

Ask Claude in plain language:

- "Curate the docs in `~/docs` before I run Graphify."
- "Dedupe this repo and tell me which files are outdated."
- "Prepare `~/handbook` for a knowledge graph. Put the result in `~/curated/handbook`."

The skill puts everything it makes in `~/curated/<project-name>/` by default. `<project-name>` is the name of the source folder. So `~/docs/handbook` becomes `~/curated/handbook/`. To use another folder, name it in your request. It must be outside the source folder. The working files, the staging folder and the graph all go there, so your project folder stays clean. Staging is the folder of cleaned copies of the documents that Graphify reads.

Do not use the skill for a single file. Do not use it to build or query the graph. Use `graphify` for that. Do not use it to edit or delete your originals.

## Ways to run it

| Option | How | Good for |
|--------|-----|----------|
| Plain language | "Curate `~/docs` into `~/curated/docs`." | Most runs. Claude loads the skill from the description. |
| Slash command | `/docs-curator` followed by the source and output folders. Or type `/docs-curator` alone and answer Claude's questions. | Forcing the skill when plain language does not start it. |
| Settings up front | Name them in the prompt: "curate `~/docs`, flag near duplicates but don't exclude them, use tfidf" | Runs where you already know the settings. Claude writes `config.yaml`, the settings file, before it analyzes. |
| Continue a capped run | "Continue curating `~/curated/docs`" | Large folders. A run stops at its batch limit, which is called capped. Claude runs the analysis again, reviews the groups left over, and applies the results. Existing reviews are kept. |
| Update after changes | "Update the curation of `~/docs`; I added and edited some files" | A folder that changed after a finished run. Claude reports what was added, changed and removed. It reviews only the affected groups and rebuilds `staging/`. |
| Re-apply after overrides | "I want `policies/travel_2022.docx` kept. Re-apply." | Changing one file's result without repeating the review. |
| Watched delegate | "Delegate the curation of `~/docs` to another session" | Long runs. It uses the `visible-delegation` skill, so you can watch the session in a herdr pane. |
| Headless | `claude -p "Curate ~/docs into ~/curated/docs"` | Scripts and scheduled jobs. `claude -p` runs Claude once from the command line, with no chat. Nobody is there to answer questions, so name both folders and any settings. |
| Docker | Build the [reference image](docker/Dockerfile) and run Claude inside it | A machine without LibreOffice or uv (see Requirements), or an offline run. The embedding model is cached in the image. |

### Slash command examples

Type the skill name exactly: `docs-curator`, with an `s`.

```text
/docs-curator --source ~/docs
/docs-curator --source ~/docs --out ~/curated/docs
/docs-curator --source ~/docs --out ~/curated/docs --near-duplicate-action exclude
/docs-curator --source ~/docs --out ~/curated/docs --embedding-backend tfidf
/docs-curator --source ~/docs --out ~/curated/docs --continue
/docs-curator --source ~/docs --out ~/curated/docs --apply-only
/docs-curator --source ~/docs --out ~/curated/docs --update
```

| Argument | Meaning |
|----------|---------|
| `--source <dir>` | The folder of documents to curate. Claude only reads it. |
| `--out <dir>` | The output folder, outside `--source`. The default is `~/curated/<project-name>/`. |
| `--near-duplicate-action flag\|exclude` | Saved in `config.yaml`. The default is `flag`. |
| `--embedding-backend fastembed\|tfidf` | Saved in `config.yaml`. `tfidf`, a simple word-based method, skips the model download. |
| `--continue` | Continues with groups left over from an earlier run that stopped at its batch limit. |
| `--update` | The source gained, changed or lost files since the last run. Claude runs the update step, reviews only the affected groups, then applies the results. |
| `--apply-only` | Skips analyze and review. Rebuilds `staging/` from the existing reviews and `overrides.yaml` (see [Adjusting the result](#adjusting-the-result)). |

No code reads these options. Claude reads the text after `/docs-curator` and follows it, so plain sentences work too, for example `/docs-curator ~/docs into ~/curated/docs`. Only `--source` is required. You can pass any other `config.yaml` setting the same way. Use dashes where the setting name has underscores.

Whichever way you run it, Claude needs the source folder. If you leave it out, Claude asks for it.

## What happens

The run has five steps:

1. **Analyze.** Claude scans the folder and reads every file. It groups files that look alike. A group can hold exact duplicates, copies in different formats (a deck and its PDF export), near-identical text, revision chains (such as `v1`, `v2`, `final`, or dated copies), and files on related topics.
2. **Classify (optional).** Turn this on with `classify_untyped`. A small, low-cost model labels each document that has no type. The label is requirement, ADR or other. Claude then runs the analysis again, so those documents join the requirement-versus-ADR check. Labels with less than 0.8 confidence are ignored.
3. **Review.** Claude reads each group. It decides whether one document replaces another, which is called superseding it. It also decides whether any documents contradict each other. Each contradiction is quoted word for word, and the quotes are checked against the documents afterwards. Claude marks a file as superseded only when the text supports it.
4. **Apply.** Claude builds the curated folder and a report, then gives you a summary.
5. **Docs graph (with your approval).** Claude asks whether to build the docs graph from `staging/`. Nothing runs until you say yes. Code is mapped by the separate `code-graph` skill.

> **Background (skip if you only need to run it).** The review step sends each group to a model that fits its difficulty. Sonnet and Opus are Claude models. Sonnet reviews ordinary groups. Opus reviews the harder ones: requirement-versus-ADR checks, revision chains whose order the file signals could not work out, and large groups. If a Sonnet review finds a contradiction or an unsure supersession, Opus reviews that group again. Haiku, a smaller model, is the default for the optional classify step. You can change these model names in `config.yaml`.
>
> The skill compares documents with embeddings. An embedding is a numeric fingerprint of a document's meaning. Documents with similar meanings get similar fingerprints. The default embedding model is `BAAI/bge-small-en-v1.5`.

When the folder changes, ask Claude for an update. Claude lists the files it added, changed and removed. The list is saved in `.docs-curator/changes.json`. Claude reviews only the groups that contain a new or changed file, and it rebuilds `staging/`. Reviews of untouched groups are kept. Reviews of changed groups are listed as stale and left in place. Stale means the review was written before the files changed.

Running the skill again on an unchanged folder is cheap, and earlier reviews are kept. Very large folders are processed in batches of 25 groups. If groups are left over, Claude tells you. Ask it to continue.

## What you get

```text
<out>/                       # default ~/curated/<project-name>/
├── graphify-out/            # the docs graph; see "Running Graphify"
├── staging/                 # give this to Graphify
│   ├── <original path>.md   # each kept document, as Markdown with front matter
│   ├── <name>.pptx.pdf      # kept decks, as a PDF
│   ├── <name>.pptx.notes.md #   plus their speaker notes
│   └── _curated/
│       ├── CONFLICTS.md     # contradictions between documents
│       └── historical/      # superseded files that had unique content
└── .docs-curator/           # working files; REPORT.md is the one to read
```

Front matter is the block of settings at the top of a Markdown file. `<out>` is the output folder you chose.

Read `<out>/.docs-curator/REPORT.md` first. Pay the most attention to these sections:

- **Flagged but kept:** possible duplicates or outdated files that the skill was not sure enough about to exclude.
- **Filed under conflicting names:** documents whose filename does not match their content.
- **Identifier collisions:** near-identical files that differ only in an ID, such as form templates.
- **Conflicts:** the contradictions found, with quotes.
- **Requirements and ADRs:** business requirements that conflict with an ADR, gaps, and unlinked items (see below).

The Markdown files hold text only. Layout, images and formatting in PDF, Word and Excel files are not kept. Scanned documents with no text are kept with an empty body, and the report lists them. The skill has no OCR (optical character recognition, which reads text from a picture), so it cannot read them.

## Requirements versus ADRs

An ADR is an architecture decision record. It is a short document that records a design choice and the reason for it. If your folder holds business requirements and ADRs, the skill can check one against the other. The skill needs to know which document is which. Do one of these:

- Add `type: requirement` or `type: adr` to the document's front matter.
- Or list path patterns, called globs, in `config.yaml`. A glob such as `adr/*` matches every file in the `adr` folder.

```yaml
adr_globs: ["adr/*", "docs/adr/*"]
requirement_globs: ["requirements/*"]
```

If your documents have neither, set `classify_untyped: true`. A small model then guesses the type of each document (see [Adjusting the result](#adjusting-the-result)). The report lists these guesses as "typed by the classifier".

To pair documents exactly, give each one an `id` and link them. Add `satisfies: REQ-12` to an ADR, or `decided_by: ADR-7` to a requirement. The skill also pairs each requirement with its most similar ADR on its own. The cut-off that decides how similar is similar enough is `cross_type_threshold`. It has not been tuned yet, so expect some pairs to be missed or wrong.

The skill gives you these results:

- A requirement and an ADR that cannot both hold go in `_curated/CONFLICTS.md`, marked `[requirement vs ADR]`. The entry has a verbatim quote from each side and the ADR's status. A superseded ADR, one that a newer decision replaced, does not count.
- Gaps and "can't tell" findings go in the report's "Requirements and ADRs" section. That section has an "Unlinked" list. It names requirements with no ADR, and ADRs with no requirement. Those are gaps, not conflicts.
- The skill never picks a winner and never edits a document. The people who own the documents decide.

## Running Graphify

Graphify writes `graphify-out/` into the folder you run it from. To keep that folder out of your project, the skill's last step does two things:

- It creates `<out>/graphify-out/`.
- It creates two symlinks in the project root. A symlink is a shortcut. They are `<source>/graphify-out` and `<source>/.docs-curator` (the working folder). Both point into `<out>`.

Those links are the only things the skill writes to the source folder. The one exception is a `.gitignore` entry, which is added only if you ask for it. `.gitignore` is a file that tells git which files to leave out.

To keep the `.docs-curator` link out of git, the version control system, ask for one of these:

- `--gitignore project` adds `.docs-curator` to `<source>/.gitignore`.
- `--gitignore global` adds it to your global git excludes file.

The skill does neither unless you ask.

When it finishes, the skill prints this command. It runs Graphify on the staged documents:

```text
cd <source> && /graphify <out>/staging
```

Because of the symlink, the graph lands in `<out>/graphify-out/`. The project folder holds only the link. If the project already has a real `graphify-out` folder, the skill will not replace it. Move that folder aside, then ask Claude to link again.

Claude then asks whether to build the docs graph. The build uses AI tokens, the units of text that a model reads and writes. You pay for them. When a graph already exists, only the changed files are read again. Your yes covers one run only. Claude asks again next time.

### Code is a separate graph

Code files are never staged. The report counts how many were skipped. Use the `code-graph` skill for code questions, such as what calls what, what depends on what, and how the code is laid out. That skill builds its own index with `codegraph`. It never touches the docs graph, and it does not need this skill.

To tie a document to code, add `applies_to` to its front matter:

```yaml
---
applies_to:
  - src/orders/service.py
  - OrderService.retry
---
```

The report lists each link under "Linked code (applies_to)". It flags any path that does not exist in the source. The `code-graph` skill uses these links to check a code change against the ADRs that limit it.

## Adjusting the result

Both files below are optional. They go in the output folder. Ask Claude to create them, or write them yourself. Then ask Claude to run apply again. Apply is the step that builds the curated folder from the reviews.

- **`overrides.yaml`:** forces one file in or out when you disagree with the skill's decision.

  ```yaml
  - path: policies/travel_2022.docx   # relative to the source folder
    action: include                   # or exclude
    note: still in force for contractors
  ```

- **`config.yaml`:** changes how the skill behaves. For example:

  ```yaml
  near_duplicate_action: exclude   # default is flag (keep and report)
  low_confidence_threshold: 0.75   # below this, older files are kept and flagged
  embedding_backend: tfidf         # skip the model download
  classify_untyped: true           # have a small model label untyped documents (default false)
  classify_min_confidence: 0.8     # ignore labels below this
  review_model_standard: sonnet    # model for ordinary groups
  review_model_deep: opus          # model for hard groups
  deep_review_min_members: 6       # groups this large count as hard
  ```

  The model names are aliases. Claude passes them to the subagents (helper sessions) it starts. You can change the cheap and strong models here without editing the skill.

  If you use a setting name that the skill does not know, the skill rejects it. Leave `near_duplicate_action` on `flag` unless your folder holds prose, where near-identical text is really redundant. Near-identical forms can still be different documents.

The thresholds were tuned only on a synthetic test set, which means made-up documents. They were not tuned on real files. After your first real run, check the "Flagged but kept" list and the superseded list by hand.

## Requirements

- The [heavy-file-ingestion](../../research/heavy-file-ingestion) skill, installed in `~/.claude/skills/`. Or set `HEAVY_FILE_INGESTION_SCRIPT` to the path of its `ingest.py`. That skill converts PDF, Word, Excel and PowerPoint files to Markdown. For PDFs it needs `pdftotext`, which comes from poppler (a set of PDF tools).
- `uv`, a Python tool runner, and Python 3.11 or newer. Run the skill with `--python 3.12`, and uv downloads that version for you.
- LibreOffice (`soffice`), a free office suite. The skill uses it to convert `.pptx` decks to PDF.
- The embedding model, `BAAI/bge-small-en-v1.5`. It downloads the first time it is used. If the download fails, Claude asks whether to switch to `tfidf`.
- The skill linked into Claude Code. Run this from the root of this repo:

  ```bash
  ln -s "$(pwd)/docs/docs-curator" ~/.claude/skills/docs-curator
  ```

Claude checks the environment before it starts, and it names anything missing. A reference Docker image (a sealed, ready-made copy of the full setup) bundles everything. Docker is a tool for running software in such packages.

## Files

| File | Purpose |
|------|---------|
| [SKILL.md](SKILL.md) | The instructions Claude follows: triggers, workflow, hard rules |
| [references/verdict-schema.md](references/verdict-schema.md) | The format of Claude's review result for each group |
| [docs/How docs-curator works.md](<docs/How docs-curator works.md>) | A technical walkthrough of how `curate.py` works, with an architecture diagram |
| [plan/DECISIONS.md](plan/DECISIONS.md) | Settled design decisions and where the build departed from the plan |
| [plan/PLAN.md](plan/PLAN.md) | The original build plan |
| `scripts/`, `requirements.txt`, `docker/`, `tests/` | The code, its dependencies, the reference image, and tests for developers |

For contributors: branch off `main`, use Conventional Commits (a standard format for commit messages), record design decisions in `plan/DECISIONS.md`, and update the repository's top-level `README.md` when this skill changes.
