# docs-curator

A Claude Code skill that cleans up a large folder of documents (`.pptx .pdf .md .xlsx .txt .docx`) before you build a knowledge graph from it with [Graphify](https://pypi.org/project/graphifyy/).

It finds duplicates and outdated revisions, flags documents that contradict each other, and writes the documents worth keeping into a separate, tidy folder. Your original folder is never changed, and the skill never runs Graphify for you.

## Using the skill

Ask Claude in plain language:

- "Curate the docs in `~/docs` before I run Graphify."
- "Dedupe this repo and tell me which files are outdated."
- "Prepare `~/handbook` for a knowledge graph. Put the result in `~/curated/handbook`."

Everything generated goes to `~/curated/<project-name>/` by default, where `<project-name>` is the name of the source folder (`~/docs/handbook` becomes `~/curated/handbook/`). Name a different folder if you prefer; it must be outside the source folder. Staging, working files and the graph all live there, so the project folder stays clean.

Don't use it for a single file, for building or querying the graph (that's `graphify`), or for editing or deleting your originals.

## Execution options

| Option | How | Good for |
|--------|-----|----------|
| Plain language | "Curate `~/docs` into `~/curated/docs`." | Most runs. Claude loads the skill from the description. |
| Slash command | `/docs-curator` followed by the source and output folders, or just `/docs-curator` and answer Claude's questions | Forcing the skill when plain language doesn't trigger it. |
| Settings up front | Name them in the prompt: "curate `~/docs`, flag near duplicates but don't exclude them, use tfidf" | Runs where you already know the thresholds. Claude writes `config.yaml` before analyzing. |
| Continue a capped run | "Continue curating `~/curated/docs`" | Large folders. Claude re-runs analyze, reviews the remaining groups and applies. Existing reviews are kept. |
| Update after changes | "Update the curation of `~/docs`; I added and edited some files" | A folder that changed after a finished run. Claude reports what was added, modified and removed, reviews only the affected groups and rebuilds `staging/`. |
| Re-apply after overrides | "I want `policies/travel_2022.docx` kept. Re-apply." | Fixing one file's fate without redoing the review. |
| Watched delegate | "Delegate the curation of `~/docs` to another session" | Long runs. Uses the `visible-delegation` skill, so you can watch the session in a herdr pane. |
| Headless | `claude -p "Curate ~/docs into ~/curated/docs"` | Scripts and scheduled jobs. Nobody is there to answer questions, so name both folders and any settings. |
| Docker | Build the [reference image](docker/Dockerfile) and run Claude inside it | A machine without LibreOffice or `uv`, or an offline run (the embedding model is cached in the image). |

### Slash command examples

The skill is named `docs-curator` (with an `s`).

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
| `--source <dir>` | Folder of documents to curate. Read only. |
| `--out <dir>` | Output folder, outside `--source`. Default `~/curated/<project-name>/`. |
| `--near-duplicate-action flag\|exclude` | Written to `config.yaml`. Default `flag`. |
| `--embedding-backend fastembed\|tfidf` | Written to `config.yaml`. `tfidf` skips the model download. |
| `--continue` | Pick up groups left over from a capped run. |
| `--update` | The source gained, changed or lost files since the last run. Claude runs `update`, reviews only the affected groups, then applies. |
| `--apply-only` | Skip analyze and review. Re-build `staging/` from existing reviews and `overrides.yaml`. |

These are not parsed by code. Claude reads the text after `/docs-curator` and acts on it, so natural language works too (`/docs-curator ~/docs into ~/curated/docs`). Only `--source` is required. Any other `config.yaml` key can be passed the same way, with dashes for underscores.

Whichever option you choose, Claude needs the source folder. If it is missing, it asks.

## What happens

1. **Analyze.** Claude scans the folder, reads every file, and groups exact duplicates, copies in different formats (a deck and its PDF export), near-identical text, revision chains (`v1`, `v2`, `final`, dated copies) and related topics.
2. **Review.** Claude reads each group and decides whether one document supersedes another and whether any contradict each other. Contradictions are quoted word for word, and the quotes are checked against the documents afterwards. Claude only marks a file as superseded when it can defend that from the text.
3. **Apply.** Claude builds the curated folder and a report, then gives you a summary and the Graphify command to run.

After the folder changes, ask for an update. Claude lists the files added, modified and removed (saved in `.docs-curator/changes.json`), reviews only the groups that contain a new or modified file, and rebuilds `staging/`. Reviews of untouched groups are kept. Reviews of groups that changed are listed as stale and left in place.

Re-running on an unchanged folder is cheap, and earlier reviews are kept. Very large folders are processed in batches of 25 groups. If some are left over, Claude tells you and you ask it to continue.

## What you get

```text
<out>/                       # default ~/curated/<project-name>/
├── graphify-out/            # Graphify's output; see "Running Graphify"
├── staging/                 # give this to Graphify
│   ├── <original path>.md   # each kept document, as Markdown with front matter
│   ├── <name>.pptx.pdf      # kept decks, as a PDF
│   ├── <name>.pptx.notes.md #   plus their speaker notes
│   └── _curated/
│       ├── CONFLICTS.md     # contradictions between documents
│       └── historical/      # superseded files that had unique content
└── .docs-curator/           # working files; REPORT.md is the one to read
```

Start with `<out>/.docs-curator/REPORT.md`. Pay most attention to:

- **Flagged but kept:** possible duplicates or outdated files Claude wasn't sure enough about to exclude.
- **Filed under conflicting names:** documents whose filename disagrees with their content.
- **Identifier collisions:** near-identical files that differ only in an ID, such as form templates.
- **Conflicts:** the contradictions found, with quotes.

Staged Markdown is text only. Layout, images and formatting in PDF, Word and Excel files are not carried over. Scanned documents with no text are kept with an empty body and listed in the report, because there is no OCR.

## Running Graphify

Graphify writes `graphify-out/` into the directory you run it from. To keep that out of your project, the skill's last step creates `<out>/graphify-out/` and two symlinks in the project root, `<source>/graphify-out` and `<source>/.docs-curator` (the working directory), pointing into `<out>`. Those links are the only things the skill writes to the source folder, plus a `.gitignore` entry if you opt in.

To keep the `.docs-curator` link out of git, ask for `--gitignore project` (adds `.docs-curator` to `<source>/.gitignore`) or `--gitignore global` (adds it to your global git excludes file). Neither is done unless you ask.

It then prints:

```text
cd <source> && /graphify <out>/staging
```

Run it yourself. Because of the symlink, the graph lands in `<out>/graphify-out/` and the project folder holds only the link. If the project already has a real `graphify-out` folder, the skill won't replace it. Move it aside and ask Claude to link again.

## Adjusting the result

Both files are optional and go in the output folder. Ask Claude to create them, or write them yourself, then ask it to re-run apply.

- **`overrides.yaml`:** force one file in or out when you disagree with its fate.
  ```yaml
  - path: policies/travel_2022.docx   # relative to the source folder
    action: include                   # or exclude
    note: still in force for contractors
  ```
- **`config.yaml`:** change behaviour, for example:
  ```yaml
  near_duplicate_action: exclude   # default is flag (keep and report)
  low_confidence_threshold: 0.75   # below this, older files are kept and flagged
  embedding_backend: tfidf         # skip the model download
  ```
  Unknown keys are rejected. Leave `near_duplicate_action` on `flag` unless the folder is prose where near-identical text really is redundant. Near-identical forms can be different documents.

Thresholds were tuned on a synthetic corpus only, so spot-check "Flagged but kept" and the superseded list after your first real run.

## Requirements

- `uv`, Python 3.10+, and LibreOffice (`soffice`, used to convert `.pptx` decks to PDF)
- The embedding model (`BAAI/bge-small-en-v1.5`) downloads on first use. If it can't, Claude will ask whether to switch to `tfidf`.
- The skill linked into Claude Code:
  ```bash
  ln -s "$(pwd)/docs/docs-curator" ~/.claude/skills/docs-curator
  ```

Claude checks the environment before starting and names anything missing. A reference [Docker image](docker/Dockerfile) bundles all of it.

## Files

| File | Purpose |
|------|---------|
| [SKILL.md](SKILL.md) | What Claude follows: triggers, workflow, hard rules |
| [references/verdict-schema.md](references/verdict-schema.md) | Format of Claude's per-group review results |
| [docs/How docs-curator works.md](<docs/How docs-curator works.md>) | Technical walkthrough of how `curate.py` works, with an architecture diagram |
| [plan/DECISIONS.md](plan/DECISIONS.md) | Settled design decisions and departures from the plan |
| [plan/PLAN.md](plan/PLAN.md) | Original build plan |
| `scripts/`, `requirements.txt`, `docker/`, `tests/` | Implementation, dependencies, reference image and dev-only tests |

Contributors: branch off `main`, use Conventional Commits, record design decisions in `plan/DECISIONS.md`, and update the repository's top-level `README.md` when this skill changes.
