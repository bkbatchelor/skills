# token-saver

Keeps a job cheap in tokens. A token is a small unit of text that an AI model reads or writes. Tokens set what a job costs, and they limit how much text fits in one request. The skill does exact work with local code where it can. It searches for matching passages instead of sending whole files. It revises from one saved result instead of the whole chat. It loads only the tools the job needs. It keeps answers the size of the request.

You do not have to summarize an old chat, choose source files, create a state file, or learn a script path. Claude does that work itself.

**Honest limit:** the skill cannot undo the call it was loaded into. The input for that call is already spent. It only makes the work after that call smaller.

## Tech Stack

| Category | Technology |
|----------|------------|
| Format | Markdown skill (`SKILL.md`) |
| Language | Python 3, standard library only |
| Package Manager | None |

## Quick Start

Run these in a terminal. They download (clone) the repo with git, then create a symlink. A symlink is a shortcut that makes the skill appear where your harness loads skills. The harness is the program that runs Claude and loads its skills.

```bash
# Clone the repository
git clone git@github.com:bkbatchelor/skills.git
cd skills

# Link the skill where your harness loads skills
ln -s "$PWD/efficiency/token-saver" ~/.claude/skills/token-saver
```

Then ask Claude to use token-saver, or say you want to save tokens.

## Installation

### Prerequisites

- Git
- `python3`

### Steps

1. Clone the repository:
   ```bash
   git clone git@github.com:bkbatchelor/skills.git
   ```

2. Change into the repo folder:
   ```bash
   cd skills
   ```

3. Link the skill:
   ```bash
   ln -s "$PWD/efficiency/token-saver" ~/.claude/skills/token-saver
   ```

There are no dependencies to install and no environment to set up.

## Usage

### Basic Usage

Ask for the skill by name ("use token-saver"). You can also say you want to save tokens or cut token waste. It helps when you work with a large transcript, a code repo, a log, or an export. Short one-off questions do not need it.

### Common Commands

Claude runs these commands itself. To run them by hand, change into the `efficiency/token-saver/` folder first.

| Command | Description |
|---------|-------------|
| `python3 -I scripts/tokensaver.py search <path> <pattern> [-C 2] [--max-chars 6000] [--skip N] [-F] [-i]` | Searches a file and prints a capped set of matching passages. A passage is a few lines around a match. It also prints how many matches remain and the `--skip` value for the next set. |
| `python3 -I scripts/tokensaver.py count <file\|-> [--by lines\|unique\|field] [--field N] [--top N]` | Counts lines, words and characters. It can also count how often each line or field appears. |
| `python3 -I scripts/tokensaver.py fields <file\|-> col1,col2.sub [--format csv\|tsv\|json\|jsonl]` | Pulls out named columns, or JSON keys written with dots such as `user.name`, as TSV (tab-separated values). |
| `python3 -I scripts/tokensaver.py dates <file\|-> [--dayfirst]` | Rewrites the dates in text in the ISO 8601 format, such as `2026-11-05`. `--dayfirst` reads the day before the month. |
| `python3 -I scripts/tokensaver.py diff <a> <b>` | Shows the differences between two files, up to a set size. |
| `python3 -I scripts/tokensaver.py accept <job-slug> <file\|->` | Saves the accepted result for a job. A job slug is a short name for the job. |
| `python3 -I scripts/tokensaver.py current <job-slug>` | Prints the accepted result for a job. |

### Examples

- `python3 -I scripts/tokensaver.py search ../../README.md '^\| docs-curator \|' -C 0` prints only the matching table row, followed by `[1 passage(s) matched; showed 1-1; 0 more.]`.
- `python3 -I scripts/tokensaver.py dates notes.txt` turns `5 Nov 2026` into `2026-11-05`.

## Project Structure

```text
token-saver/
├── SKILL.md              # Skill definition: the rules Claude follows
├── README.md             # This file
└── scripts/
    └── tokensaver.py     # Helper commands Claude runs itself
```

## Modules

| Module | Description | Key Files |
|--------|-------------|-----------|
| Rules | Seven rules, plus a rule for reporting usage, that control how context is spent | `SKILL.md` |
| Helpers | Local, repeatable commands that do exact work without a model | `scripts/tokensaver.py` |

### Module Details

#### Rules

The skill has seven rules:

1. Use local code first.
2. Search first, then send only the matches.
3. Keep one accepted result to revise from.
4. Load only the tools the job needs.
5. Use a smaller model only when it is cheaper for the whole job.
6. Size answers to the request.
7. Make one bounded repair, which means one repair attempt with a set limit.

If a request hits a token limit or a usage limit, the skill does not retry it. It sends less input instead.

Usage numbers show how many tokens a job used. They include fresh input (new text the model read), reused input (input served from a cache), output (what the model wrote), model calls and retries. They appear only when the harness provides them. Otherwise they show `unavailable`.

**Key Components:**
- `SKILL.md`: the rules and the honest limit

#### Helpers

The helpers are Python commands that use only the standard library. That is the part of Python that comes built in, so there is nothing extra to install.

The accepted result for each job is stored at `~/.claude/state/token-saver/<job-slug>/accepted.md`, outside any repo. Saving a new result overwrites the old one, so no history builds up. A rejected result is never saved. To store results in a different folder, set `TOKEN_SAVER_STATE` to that folder.

**Key Components:**
- `scripts/tokensaver.py`: `search`, `count`, `fields`, `dates`, `diff`, `accept`, `current`

## Contributing

### Development Setup

1. Fork the repository. A fork is your own copy of it on GitHub.
2. Create a branch for your change. Replace `<branch-name>` with a short name:
   ```bash
   git checkout -b feat/<branch-name>
   ```
3. Make your changes.
4. Check that the helper still runs. This skill has no test suite, which means no automated tests:
   ```bash
   python3 -I efficiency/token-saver/scripts/tokensaver.py --help
   ```
5. Update the repo `README.md` if the skill's files or behavior changed. Then open a pull request.

### Code Style

- Use only the standard library in the script.
- Keep the rules in `SKILL.md` short enough to test.

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/), a standard format for commit messages:

```text
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## License

The repository does not have a LICENSE file yet. That file would state the terms for reusing the code.

---
*Generated with STANDARD fidelity level*
