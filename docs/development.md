# Development guide

Follow the [README quick start](../README.md#quick-start) to create and activate the virtual environment and install the package.

## Working locally

Activate the environment in each new terminal:

```bash
source .venv/bin/activate
```

The editable installation (`-e .`) makes changes under `src/` available without reinstalling. Run `energy-ops --help` or `python -m energy_ops --help` to inspect the current interface.

## Checks

Run these from the repository root before committing:

```bash
ruff check .
ruff format --check .
python -m pytest
python -m build --no-isolation
```

Use `ruff format .` to apply formatting, then review the changes. The current tests exercise both installed CLI entry points, including invalid input. CI also installs the built wheel in a clean environment and runs it outside the checkout.

## Dependencies

`pyproject.toml` declares package metadata and supported dependency ranges. `requirements-dev.txt` pins the development and build tools used locally and in CI.

Update pins deliberately and check the complete Python CI matrix after dependency changes. These version pins are not a hash-verified dependency lock.

## Repository layout

```text
src/energy_ops/        Python package and CLI
tests/                Automated tests
docs/                 Architecture, data contract, and development guide
.github/workflows/    Continuous integration
pyproject.toml        Package metadata and tool settings
requirements-dev.txt  Pinned development and build dependencies
```

## Git workflow

1. Create a feature branch, such as `git switch -c feature/smard-parser`.
2. Implement a coherent change and its relevant tests.
3. Run the checks above and review `git diff` and `git status`.
4. Stage the intended files, commit with a descriptive message, and push the branch.
5. Open a pull request explaining behavior and validation; merge after CI passes.

The CI workflow runs on pushes and pull requests when uploaded to GitHub. Branch protection must be configured separately in the repository settings.

## Data and configuration

Keep full downloads in ignored `data/raw/` or outside the repository. Add small, attributed fixtures under `tests/fixtures/` when implementing the parser. Preserve original source files and describe any fixture transformations.

Never commit passwords, tokens, or real `.env` files. `.env.example` documents configuration when it becomes necessary; no environment variables are required for the current foundation.

The SMARD data licence is distinct from software licensing. No software licence has been selected for this repository yet.
