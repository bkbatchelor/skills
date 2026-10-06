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
