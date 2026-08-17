# STANDARD Level Template

---

Includes all BASIC sections plus:

## Project Structure
```text
{project_root}/
├── {key_directory_1}/    # {purpose_1}
├── {key_directory_2}/    # {purpose_2}
├── {config_file}         # {purpose}
└── {other_notable_files}
```
*Note: Files and directories matching .gitignore patterns are excluded from this view.*

## Modules

| Module | Description | Key Files |
|-------|-------------|-----------|
| {module_1} | {description_1} | `{file_1}`, `{file_2}` |
| {module_2} | {description_2} | `{file_3}`, `{file_4}` |
| {module_3} | {description_3} | `{file_5}` |

### Module Details

#### {module_1_name}

{detailed_description}

**Key Components:**
- `{component_1}`: {purpose}
- `{component_2}`: {purpose}

#### {module_2_name}

{detailed_description}

**Key Components:**
- `{component_1}`: {purpose}
- `{component_2}`: {purpose}

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch:
  ```bash
      git checkout -b feature/{branch_name}
  ```
3. Make your changes
4. Run tests:
   ```bash
   {test_command}
   ```
5. Submit a pull request

### Code Style

- Follow {coding_standard}
- Run linter before committing:
  ```bash
  {lint_command}
  ```

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`



## License

This project is licensed under the {license_name} License - see the [LICENSE](LICENSE) file for details.

*Generated with STANDARD fidelity level*
