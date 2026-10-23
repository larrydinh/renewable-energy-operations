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
node --test tests/web/*.test.mjs  # Node.js 22+
python -m build --no-isolation
```

Use `ruff format .` to apply formatting, then review the changes. The tests cover both installed CLI entry points, decimal parsing, missing values, malformed files, record provenance, clock changes, and timeline validation. CI also installs the built wheel in a clean environment and runs it outside the checkout.

## Inspect local SMARD files

```bash
energy-ops parse-smard ../data/raw/smard/*.csv
```

The shell expands the wildcard into input paths. JSON is printed only after all inputs pass structural and numeric parsing. Redirect it to a local report if needed:

```bash
energy-ops parse-smard ../data/raw/smard/*.csv > /tmp/smard-report.json
```

The reusable Python interface is `energy_ops.smard.iter_generation(Path(...))`. It streams immutable records with `Decimal` or `None` values, source labels, the source filename, and the physical row number. Exhaust the iterator to check the whole file; early records do not establish that later rows are valid. Records retain local timestamp text. This stage does not check continuity, resolve repeated hours, or detect duplicate time intervals.

## Normalize a complete export

```bash
energy-ops normalize-smard \
  ../data/raw/smard/Actual_generation_202401010000_202501010000_Quarterhour.csv \
  --start-date 2024-01-01 --end-date 2025-01-01
```

These required dates describe the entire file, with an exclusive end; they are not query filters. The normalizer verifies every start and end label against the UTC timeline, rejects detectable missing/duplicated/reordered slots, and reports the known end-label conventions at clock transitions. Missing measurements remain `None`; future empty slots in the 2026 export are still valid calendar slots, not observed generation.

For application code:

```python
from datetime import date
from pathlib import Path

from energy_ops.time_normalization import normalize_file

result = normalize_file(
    Path("../data/raw/smard/Actual_generation_202401010000_202501010000_Quarterhour.csv"),
    start_date=date(2024, 1, 1),
    end_date=date(2025, 1, 1),
)
first = result.records[0]
print(first.interval_start_utc, first.interval_end_utc, first.energy_mwh)
print(result.summary())
```

The function holds one file's records in memory and returns an immutable result only after complete validation. The CLI prints a compact report; it does not save a normalized dataset or change the original CSV. Ingestion stages/publishes these records transactionally. Preserve source row order, especially across the repeated autumn hour; see the data contract for the limits of offset-free labels.

## Dependencies

`pyproject.toml` declares package metadata and supported dependency ranges. `requirements-dev.txt` pins the application, development and build dependencies used locally and in CI.

Update pins deliberately and check the complete Python CI matrix after dependency changes. These version pins are not a hash-verified dependency lock.

## Repository layout

```text
src/energy_ops/        Python package, CLI, API
src/energy_ops/web/    Build-free HTML, CSS, JavaScript frontend
tests/web/            Browser data transformation tests (Node.js)
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

Never commit passwords, tokens, or real `.env` files. `.env.example` documents the database settings. See the [local runbook](local-runbook.md) for database setup, imports, starting services, and isolated PostgreSQL tests.

The SMARD data licence is distinct from software licensing. No software licence has been selected for this repository yet.

## Frontend development

`web/index.html` defines the semantic application shell, `styles.css` implements the responsive Forest Studio design, `app.js` handles navigation and API requests, and `data.js` holds tested date/coverage/chart/CSV transformations. No npm dependencies or build are required. `package.json` declares ES modules and a convenience `npm test` command. Use Node.js 22+ for tests; the browser loads modules directly. FastAPI serves assets from the installed package, so verify that the wheel contains these files when changing packaging.
