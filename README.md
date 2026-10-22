# Renewable Energy Operations

A Python project for importing, validating, and monitoring German renewable-generation data from SMARD.

The intended user is an analyst who needs trustworthy time series or an operator who needs to investigate and safely rerun a failed import. This is an independent learning and portfolio project.

## Current status

The foundation provides an installable Python package, the `energy-ops` command, automated tests, linting, formatting, and a GitHub Actions workflow. The command currently displays help and version information only.

CSV ingestion, PostgreSQL, the API, dashboard, Argo, and cloud deployment are planned. This repository is not a production-ready service yet.

## Local setup

Prerequisites: Git and Python 3.11 or newer. CI checks Python 3.11, 3.12, and 3.13. No database, Docker, cloud account, or credentials are needed at this stage.

From the repository directory on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation --no-deps -e .
energy-ops --help
energy-ops --version
```

`-e .` installs the package in editable mode: changes under `src/` are available without reinstalling. Activate the environment in each new terminal. Alternatively, run `python -m energy_ops`.

## Check your changes

```bash
ruff check .
ruff format --check .
python -m pytest
python -m build --no-isolation
```

To apply formatting, run `ruff format .`, inspect the changes, and repeat the checks. Tests exercise both installed CLI entry points, including invalid input. CI also installs the built wheel into a clean environment and runs it outside the checkout so missing package files are detected.

`requirements-dev.txt` pins the development/build tool versions used locally and in CI. `pyproject.toml` declares the supported dependency ranges. Update the pins deliberately and run the full CI matrix when changing them; the pins do not constitute a security audit or hash-verified supply-chain lock.

## Layout

```text
src/energy_ops/       Installable package and CLI
tests/               Automated tests
docs/                Architecture and source contract
.github/workflows/   Continuous integration
pyproject.toml       Package metadata and tool settings
requirements-dev.txt Pinned development/build dependencies
```

Keep full downloads in ignored `data/raw/` or outside the repository. Small, attributed fixtures will be added under `tests/fixtures/` with the parser milestone. Never commit passwords, tokens, or real `.env` files. `.env.example` documents configuration when it becomes necessary.

## Development workflow

1. Create a feature branch, for example `git switch -c feature/smard-parser`.
2. Implement one coherent change and its relevant tests.
3. Run checks and review `git diff` and `git status`.
4. Stage the intended files, commit with a descriptive message, and push the branch.
5. Open a pull request explaining behavior and validation; merge after CI passes.

The CI workflow runs on pushes and pull requests after it is uploaded to GitHub. Repository branch protection is a separate GitHub setting; it is not enabled by this file.

## Roadmap

1. **Foundation:** package, documentation, tests, and automatic checks.
2. **SMARD parser:** explicit numeric format, missing values, units, and tested UTC intervals.
3. **Persistence:** PostgreSQL migrations, atomic ingestion, safe reruns, and revision history.
4. **API:** bounded queries, completeness metadata, and import history.
5. **Dashboard:** generation trends, quality issues, and execution details.
6. **Operations:** durable job requests, Argo workflows, live acquisition, and recovery.
7. **Deployment:** preprod/prod, access controls, release promotion, and restore tests.

See [architecture](docs/architecture.md) and [data contract](docs/data-contract.md). The next milestone is a tested parser, not cloud deployment.

## Data attribution

Planned source: [Bundesnetzagentur | SMARD.de](https://www.smard.de/en/downloadcenter/download-market-data), available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Derived datasets and fixtures must retain attribution and describe transformations. The source-data licence is distinct from the repository's software licensing; no software licence has been selected yet.
