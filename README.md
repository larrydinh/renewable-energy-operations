# Renewable Energy Operations

A Python project for exploring Germany’s renewable electricity generation and monitoring the quality of the data behind it.

The goal is to turn public SMARD data into reliable time series that analysts can explore and operators can maintain—from importing a CSV to investigating a failed update.

> **Current stage: working local dashboard.** Validated SMARD exports load into PostgreSQL and are served through FastAPI to an interactive Streamlit dashboard. Workflow scheduling and cloud deployment are later milestones.

## Open the dashboard

With the local services running:

- **Dashboard:** [localhost:18501](http://127.0.0.1:18501)
- **API documentation:** [localhost:18000/docs](http://127.0.0.1:18000/docs)

The workspace has five views: **Dashboard**, **Timeseries**, **Data quality**, **Import history**, and **Settings**. The home page shows import outcomes, execution charts, and service health. In Timeseries and Data quality, filter by year, dates, and source; switch chart resolution; and export selected aggregates as CSV. Settings displays the current local configuration. Incomplete periods are labelled as observed subtotals.

## What will this project do?

The platform is being built to answer four questions:

- How much electricity comes from wind, solar, and other renewable sources?
- How does generation change by day, month, and year?
- Where is data missing, duplicated, or inconsistent?
- Which imports failed, and how can they be rerun safely?

The main engineering challenges are handling clock changes correctly, keeping missing values distinct from zero, and updating data without creating duplicate records.

## Data

The project uses **German actual-generation exports from [SMARD](https://www.smard.de/en/downloadcenter/download-market-data)** at **15-minute intervals**, measured in **MWh**.

It covers biomass, hydropower, offshore wind, onshore wind, solar photovoltaics, and other renewables. The initial downloaded files cover **2023–2025 and part of 2026**. Full datasets are kept outside Git.

Source: **Bundesnetzagentur | SMARD.de**, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See the [data contract](docs/data-contract.md) for timestamp, unit, and missing-value rules.

## Data flow

```text
SMARD CSV files
      ↓
Python — read, validate, and normalize
      ↓
PostgreSQL — store generation data and import history
      ↓
FastAPI — provide access to the data
      ↓
Streamlit — display trends, data quality, and import status
```

Later milestones will add **Argo Workflows** for scheduled imports and **Azure Kubernetes Service (AKS)** for deployment. The [architecture notes](docs/architecture.md) explain the design decisions.

## Progress

| Stage | Deliverable | Status |
|---|---|---|
| 1. Foundation | Python package, CLI, tests, and GitHub Actions configuration | Complete |
| 2. Data ingestion | CSV parsing, timeline validation, and clock-change handling | Complete for local exports |
| 3. Storage | PostgreSQL, atomic imports, safe reruns, and correction history | Working locally |
| 4. API and dashboard | Generation queries, charts, quality, and import monitoring | Working locally |
| 5. Operations and deployment | Scheduled jobs, preprod/prod, and recovery checks | Planned |

The current application uses historical local exports. Scheduled retrieval, login, preprod/prod deployment, and operational recovery drills remain planned.

## Quick start

You need **Git, Python 3.11+, and Docker Desktop**. The commands below are for macOS/Linux.

```bash
git clone https://github.com/larrydinh/renewable-energy-operations.git
cd renewable-energy-operations

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation --no-deps -e .

energy-ops --help
python -m pytest
```

If you already have the repository, start from its directory and skip the first two commands.

Copy `.env.example` to `.env`, choose a local database password, and use the same password in `DATABASE_URL`. Real credentials stay in this ignored file. A configured `.env` already exists on the development laptop.

```bash
# On a new machine, fetch the database image once.
docker pull postgres:17

# First launch: create the database, import the four exports, and start both services.
./scripts/start-local.sh --data-dir ../data/raw/smard

# Later launches: use the already imported database.
./scripts/start-local.sh
```

Keep the terminal running. Ctrl+C stops the API and dashboard; PostgreSQL data persists in a Docker volume. Ports 55432 (database), 18000 (API), and 18501 (dashboard) are bound to localhost. To stop the database too, use `docker compose stop db`.

See the [local runbook](docs/local-runbook.md) for individual commands, tests, backups, and troubleshooting.

## Parse your SMARD files

With the virtual environment active, pass one or more CSV paths:

```bash
energy-ops parse-smard ../data/raw/smard/*.csv
```

This example uses the shared `data/` directory beside the repository. You can pass any explicit local path instead. For each file, the report lists CSV row counts, six renewable measurements per row, and observed, missing, and zero counts by source. A malformed file produces an error with its row and column where applicable; no summary is printed unless all requested files parse successfully.

Try the small included sample with `energy-ops parse-smard tests/fixtures/smard_actual_generation_sample.csv`.

## Validate and normalize timestamps

For a complete export, specify the exact local-date period it contains:

```bash
energy-ops normalize-smard \
  ../data/raw/smard/Actual_generation_202401010000_202501010000_Quarterhour.csv \
  --start-date 2024-01-01 --end-date 2025-01-01
```

The end date is exclusive. This validates the entire file against that period; the dates do not filter a larger file. The JSON report includes UTC coverage, clock-change day counts, and warnings for recognized source end-label discrepancies. Invalid or incomplete timelines fail with an error. Original CSVs are read without modification.

## Development

Application code lives in `src/energy_ops/`, tests in `tests/`, and design notes in `docs/`.

GitHub Actions is configured to run tests, linting, formatting checks, and package builds on Python 3.11–3.13. For the local checks, dependency management, and contribution workflow, see the [development guide](docs/development.md).
