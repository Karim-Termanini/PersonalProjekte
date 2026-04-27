# Contributing to HypeDevHome

Thank you for your interest in contributing to HypeDevHome! We welcome all contributions — from bug fixes and features to documentation and translations.

> **⚠️ Important:** All contributions must respect the project's Flatpak + Docker-first approach. The application must work across all Linux distributions without modifications.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating. By contributing, you agree to its terms.

---

## How to Contribute

### Reporting Bugs

If you find a bug, please [open an issue](https://github.com/hypedevhome/hypedevhome/issues/new?template=bug_report.yml) with:

1. **Environment:** Distribution, desktop environment, Flatpak version
2. **Steps to reproduce** the issue
3. **Expected behavior** vs **actual behavior**
4. **Screenshots** or **logs** if applicable

### Suggesting Features

We love new ideas! [Open a feature request](https://github.com/hypedevhome/hypedevhome/issues/new?template=feature_request.yml) describing:

1. The **problem** you're trying to solve
2. Your **proposed solution**
3. **Alternatives** you've considered

### Submitting Pull Requests

1. **Fork** the repository
2. **Create a branch** from `main` (see [Branch Naming](#branch-naming))
3. **Make your changes**
4. **Run tests and linters** locally
5. **Submit a pull request** to `main`

---

## Development Workflow

### Branch Naming

Use the following convention for branch names:
```
phase-X-short-description
```
Examples:
- `phase-0-project-setup`
- `phase-1-core-ui-shell`
- `fix-github-widget-refresh`

### Commit Messages

We use **Conventional Commits** format:
```
type(scope): description

type: feat, fix, docs, chore, refactor, test, ci
scope: component or area being changed
```
Examples:
```
feat(ui): add dashboard grid layout
fix(config): handle missing config file gracefully
docs(readme): update installation instructions
ci(workflows): add flatpak build validation
```

### Pull Request Process

1. **Ensure all CI checks pass** (linting, type checking, tests, Docker/Flatpak builds)
2. **Reference related issues** in the PR description (`Closes #123`)
3. **Describe your changes** clearly with screenshots if UI-related
4. **Request review** from at least one maintainer
5. **Address feedback** and push updates
6. **Merge after approval** by a maintainer

---

## Code Style

### Python

- Follow **PEP 8** with 4-space indentation
- Use **type hints** on all functions and methods
- Run **ruff** for linting and formatting before committing
- Run **mypy** for type checking (allow `--allow-untyped-defs` initially)
- Keep functions small and focused
- Use descriptive variable and function names

### GTK / Libadwaita

- Follow the [Libadwaita Human Interface Guidelines (HIG)](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.4/)
- Use UI files (`.ui`) for layouts when possible
- Keep UI logic separate from business logic
- Ensure accessibility labels are set on interactive elements

### General

- **No hardcoded paths** — use config constants
- **Handle errors gracefully** — never crash the app
- **Log important events** — use the project logger, not `print()`
- **Thread safety** — use thread-safe data structures for shared state

---

## Testing

### Running Tests Locally
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Writing Tests

- Write tests for **all new functionality**
- Place tests in the appropriate `tests/` subdirectory
- Use descriptive test names: `test_<function>_<scenario>()`
- Test both **success** and **failure** cases
- Aim for **>80% code coverage**

### CI Checks

All pull requests trigger the following CI workflows:
- **Lint** — ruff
- **Type Check** — mypy
- **Tests** — pytest (Python 3.11, 3.12)
- **Docker Build** — validates Dockerfile
- **Flatpak Build** — validates manifest

**All checks must pass** before a PR can be merged.

---

## Questions?

If you have questions about contributing, feel free to:
- Open a [discussion](https://github.com/hypedevhome/hypedevhome/discussions)
- Ask in an existing issue
- Contact the maintainers directly

Thank you for contributing to HypeDevHome! 🎉
