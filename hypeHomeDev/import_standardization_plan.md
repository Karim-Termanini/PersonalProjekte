# Long-term Import Standardization Plan

This plan outlines the transition from explicit `src.` prefixed imports to a standard `src` layout. This will resolve "missing-import" issues in IDEs like VS Code/Pyrefly and align the project with Python packaging best practices.

## Current Issue

The project uses a `src/` layout but imports modules with an absolute `src.` prefix (e.g., `from src.core.state import ...`). 

- **The Problem**: Tools that follow the standard `src` layout convention (PEP 517) expect `src/` to be the *container* and internal modules to be the *root*. When these tools infer `src/` as the root, they cannot resolve `src.` imports, leading to false-positive error flags.

## Proposed Strategy: "The Transparent src Layout"

We will migrate to a structure where `src` is added to the `PYTHONPATH` but omitted from the import strings. Internal imports will become `from core.state import ...`.

### Phase 1: Build System Reconfiguration
- **[MODIFY] [pyproject.toml](file:///home/karimodora/Documents/GitHub/hypeHomeDev/pyproject.toml)**:
    - Update `setuptools` to find packages starting inside the `src` directory.
    - Update `mypy` and `ruff` configurations to use `src` as the primary source root.

### Phase 2: Automated Refactoring
- **Global Search & Replace**: Performance a repository-wide refactor to remove the `src.` prefix from all internal imports.
    - *Example*: `from src.ui.widgets.card import Card` → `from ui.widgets.card import Card`.
- **Scripted Migration**: Use `sed` or a custom Python script to ensure `__init__.py` exports are also updated.

### Phase 3: Developer Environment Alignment
- **[NEW] `.vscode/settings.json`**: Explicitly set `"python.analysis.extraPaths": ["./src"]` to ensure IDEs resolve imports correctly without manual environment setup.
- **[MODIFY] [com.github.hypedevhome.yml](file:///home/karimodora/Documents/GitHub/hypeHomeDev/com.github.hypedevhome.yml)**: Ensure the Flatpak build environment correctly handles the new import structure.

### Phase 4: Verification & CI Cleanup
- Update all tests (which currently might rely on `src.` prefixing) to the new structure.
- Run a full Mypy/Ruff sweep to confirm 100% resolution.

## Risk Management

- **Circular Imports**: Removing the `src.` prefix can sometimes reveal existing circular dependencies that were "hidden" by absolute paths.
- **Test Discovery**: Pytest needs to be correctly configured using `pythonpath = ["src"]` in `pyproject.toml`.

## Timeline

This is a stabilization task designed for execution after Phase 6 (Maintenance) and before Phase 7 (Extensions).
