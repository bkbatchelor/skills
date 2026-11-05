# BASIC Level Template

Section guide. Include a section only if the project has real content for it.

## Sections

1. **Title and description**: `# <project name>` and one sentence on what it does, taken from the manifest or existing docs.
2. **Tech Stack**: a short table (language, framework, package manager, notable tools) from the manifest and lockfiles.
3. **Getting Started**: one section, no repeats.
   - *Prerequisites*: runtimes and tools with versions when the manifest states them.
   - *Install*: clone command (use the real remote from `git remote get-url origin`, else omit the clone step), then the install command.
   - *Configure*: only if an `.env.example` or similar exists. Name the file.
   - *Run*: the real start command.
4. **Usage**: the basic command or call, then a table of the common commands that exist (npm scripts, Make targets, CLI subcommands). Add an example only if you can show real output or behavior.

## Example

````markdown
# acme-cli

Command-line tool for syncing Acme projects.

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | TypeScript |
| Package manager | pnpm |

## Getting Started

Requires Node 20+.

```bash
git clone https://github.com/acme/acme-cli
cd acme-cli
pnpm install
pnpm start
```

## Usage

| Command | Description |
|---------|-------------|
| `pnpm start` | Run the CLI |
| `pnpm test` | Run the tests |
````

## Rules

- Every command must appear in a manifest, script, or existing doc.
- No footer or generator note.
