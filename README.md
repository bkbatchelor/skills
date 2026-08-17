# Skills

A collection of reusable skills for AI-powered development workflows with [opencode](https://opencode.ai).

## Tech Stack

| Category | Technology |
|----------|------------|
| Platform | [opencode](https://opencode.ai) |
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

- [opencode](https://opencode.ai) installed and configured
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

## Project Structure

```text
skills/
├── commit-staged-changes/    # Git commit skill
│   ├── SKILL.md              # Skill definition
│   └── references/           # Reference materials
└── generate-readme/          # README generation skill
    ├── SKILL.md              # Skill definition
    └── references/           # Reference materials
```

## Available Skills

| Skill | Description | Key Files |
|--------|-------------|-----------|
| commit-staged-changes | Commits staged changes using conventional commit format | `SKILL.md`, `references/git-commit-template.md` |
| generate-readme | Generates README files with three fidelity levels | `SKILL.md`, `references/basic-level-template.md`, `references/standard-level-template.md` |

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

**Fidelity Levels:**
- **BASIC**: Project name, tech stack, quick start, installation, usage
- **STANDARD**: BASIC + modules, contributing, license
- **ADVANCE**: STANDARD + architecture diagrams, configuration, API reference, testing, deployment

**Features:**
- Interactive fidelity level selection
- Automatic `.gitignore` parsing and exclusion
- README backup with incrementing numbers
- Mermaid diagram generation (ADVANCE level)

---

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feature/add-new-skill
   ```
3. Make your changes
4. Test your skill in an opencode session
5. Submit a pull request

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

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(skill): Add new skill for code review
docs(skill): Update generate-readme documentation
fix(skill): Resolve commit-staged-changes validation
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Generated with STANDARD fidelity level*
