# STANDARD Level Template

Everything in [BASIC](basic-level-template.md), plus the sections below. Include a section only if the project has real content for it.

## Added sections

1. **Project Structure**: a `text` tree of the key directories and files, each with a short purpose comment. Only paths that exist, and nothing `.gitignore`d.
2. **Modules**: a table (module, description, key files), then a short subsection per module listing its main components and what each does. Group by what the code does, not by file count. Skip modules with nothing to say.
3. **Contributing**: only steps the project supports.
   - Branch and PR flow, using the repo's own conventions if documented.
   - The real test and lint commands.
   - Commit convention only if the history or config (commitlint, CONTRIBUTING.md) shows one.
4. **License**: the license name from the LICENSE file and a link to it. Omit if there is no license file.

## Example

````markdown
## Project Structure

```text
acme-cli/
├── src/       # CLI commands and sync logic
├── tests/     # Vitest suites
└── package.json
```

## Modules

| Module | Description | Key Files |
|--------|-------------|-----------|
| sync | Pulls and pushes projects | `src/sync/index.ts` |

## License

MIT, see [LICENSE](LICENSE).
````

## Rules

- Every path must exist.
- No footer or generator note.
