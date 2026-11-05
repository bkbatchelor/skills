# token-saver

Token discipline for the rest of a job: local code before a model, bounded passage search, one accepted result to revise from, minimal tools, and answers sized to the request. Claude does the extra work itself, so you never summarize an old chat, pick source files, create a state file, or learn a script path.

**Honest limit:** it cannot erase the call it was loaded into. That call's input is already spent. It only makes the work after it smaller.

## Tech Stack

| Category | Technology |
|----------|------------|
| Format | Markdown skill (`SKILL.md`) |
| Language | Python 3, standard library only |
| Package Manager | None |

## Quick Start

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

2. Navigate to the project directory:
   ```bash
   cd skills
   ```

3. Link the skill:
   ```bash
   ln -s "$PWD/efficiency/token-saver" ~/.claude/skills/token-saver
   ```

No dependencies to install and no environment to set up.

## Usage

### Basic Usage

Ask for it by name ("use token-saver"), say you want to save tokens or cut token waste, or work with a large transcript, repo, log, or export. Short one-shot questions don't need it.

### Common Commands

Claude runs these itself. Run them by hand from `efficiency/token-saver/`:

| Command | Description |
|---------|-------------|
| `python3 -I scripts/tokensaver.py search <path> <pattern> [-C 2] [--max-chars 6000] [--skip N] [-F] [-i]` | Capped passage search; prints how many passages remain and the `--skip` value for the next bounded pull |
| `python3 -I scripts/tokensaver.py count <file\|-> [--by lines\|unique\|field] [--field N] [--top N]` | Line, word and character counts, or frequency of lines or fields |
| `python3 -I scripts/tokensaver.py fields <file\|-> col1,col2.sub [--format csv\|tsv\|json\|jsonl]` | Extract columns or dotted JSON keys as TSV |
| `python3 -I scripts/tokensaver.py dates <file\|-> [--dayfirst]` | Normalize dates in text to ISO 8601 |
| `python3 -I scripts/tokensaver.py diff <a> <b>` | Capped unified diff of two files |
| `python3 -I scripts/tokensaver.py accept <job-slug> <file\|->` | Save the one accepted result for a job |
| `python3 -I scripts/tokensaver.py current <job-slug>` | Print the accepted result |

### Examples

- `python3 -I scripts/tokensaver.py search ../../README.md '^\| docs-curator \|' -C 0` prints only the matching table row and `[1 passage(s) matched; showed 1-1; 0 more.]`.
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
| Rules | Seven rules plus the usage-reporting rule that govern how context is spent | `SKILL.md` |
| Helpers | Local, deterministic commands that replace model calls for exact work | `scripts/tokensaver.py` |

### Module Details

#### Rules

The skill's seven rules: local code first, search then send only matches, one accepted result, load only needed tools, a smaller model only when the whole job wins, answers sized to the request, and one bounded repair. Token-limit and usage-limit failures are never retried; the input is reduced instead. Usage numbers (fresh input, reused input, output, model calls, retries) are reported only when the harness provides them, otherwise `unavailable`.

**Key Components:**
- `SKILL.md`: the rules and the honest limit

#### Helpers

Standard-library Python subcommands. The one accepted result per job is stored at `~/.claude/state/token-saver/<job-slug>/accepted.md`, outside any repo. `accept` overwrites it, so no history builds up, and a rejected result is never saved. Set `TOKEN_SAVER_STATE` to use a different root.

**Key Components:**
- `scripts/tokensaver.py`: `search`, `count`, `fields`, `dates`, `diff`, `accept`, `current`

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feat/<branch-name>
   ```
3. Make your changes
4. Check the helper still runs (this skill has no test suite):
   ```bash
   python3 -I efficiency/token-saver/scripts/tokensaver.py --help
   ```
5. Update the repo `README.md` if the skill's files or behavior changed, then submit a pull request

### Code Style

- Keep the script standard-library only
- Keep `SKILL.md` rules short and testable

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## License

The repository has no LICENSE file yet.

---
*Generated with STANDARD fidelity level*
