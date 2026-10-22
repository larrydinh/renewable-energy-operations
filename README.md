# Renewable Energy Operations

A Python project for exploring Germany’s renewable electricity generation and monitoring the quality of the data behind it.

The goal is to turn public SMARD data into reliable time series that analysts can explore and operators can maintain—from importing a CSV to investigating a failed update.

> **Current stage: project foundation.** The Python package, command-line interface, tests, and CI workflow are in place. Data ingestion and the dashboard are the next development stages.

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

## Planned data flow

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
| 2. Data ingestion | CSV parsing, validation, and clock-change handling | Next |
| 3. Storage | PostgreSQL, safe reruns, and correction history | Planned |
| 4. API and dashboard | Generation queries, charts, and import monitoring | Planned |
| 5. Operations and deployment | Scheduled jobs, preprod/prod, and recovery checks | Planned |

The current `energy-ops` command displays help and version information. It does not import data yet.

## Quick start

You need **Git and Python 3.11+**. The commands below are for macOS/Linux; no database or cloud account is required for the foundation.

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

## Development

Application code lives in `src/energy_ops/`, tests in `tests/`, and design notes in `docs/`.

GitHub Actions is configured to run tests, linting, formatting checks, and package builds on Python 3.11–3.13. For the local checks, dependency management, and contribution workflow, see the [development guide](docs/development.md).
