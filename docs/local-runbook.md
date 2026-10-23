# Local dashboard runbook

## What runs

| Component | Address | Responsibility |
|---|---|---|
| PostgreSQL 17 | localhost:55432 | Measurements, revisions, and import attempts |
| FastAPI | http://127.0.0.1:18000/docs | Read-only queries with OpenAPI documentation |
| Streamlit | http://127.0.0.1:18501 | Five dashboard views; queries the API |

The ports are specific to this project to avoid interfering with other applications. All services bind to localhost. The application currently assumes a trusted local user and has no remote login/authorization layer. Historical snapshots are not a live market feed.

## Start and stop

From the repository root, with dependencies installed and `.env` configured:

```bash
./scripts/start-local.sh
```

On first use, fetch `postgres:17` and provide the source directory:

```bash
docker pull postgres:17
./scripts/start-local.sh --data-dir ../data/raw/smard
```

The launcher applies Alembic migrations before starting services. With `--data-dir`, the launcher invokes `import-smard-batch`; export filenames provide period boundaries and the entire timeline is validated against those periods. If any file fails, the launcher exits before starting the API/UI; imports already committed remain available. Identical reimports are safe. Logs are in ignored `.local/logs/`. Ctrl+C stops only the API and dashboard children launched by this process. The database stays running; `docker compose stop db` stops it while retaining data.

If you see "port already in use", the workspace may already be running. Open its URLs or stop the existing launcher before starting another one. The launcher does not kill other applications or take over occupied ports.

## Individual commands

```bash
source .venv/bin/activate
docker compose up -d --wait --pull never db
energy-ops init-db
energy-ops import-smard \
  ../data/raw/smard/Actual_generation_202401010000_202501010000_Quarterhour.csv \
  --start-date 2024-01-01 --end-date 2025-01-01
```

In separate terminals, run:

```bash
python -m uvicorn energy_ops.api:app --host 127.0.0.1 --port 18000
```

```bash
python -m streamlit run src/energy_ops/dashboard.py
```

## Batch imports

Run a batch without restarting the API or dashboard:

```bash
source .venv/bin/activate
energy-ops import-smard-batch ../data/raw/smard
```

The command scans the directory non-recursively for `Actual_generation_*_Quarterhour.csv`, in filename order. Other files are ignored. Missing directories and directories with no matches fail instead of silently succeeding. Matching files with invalid names, dates, non-midnight boundaries, or non-increasing periods are reported as failures. The filename end is exclusive, and file content must pass the existing full-period validation; filenames alone do not prove validity.

Each file is a separate atomic import. A failed file rolls back its publication, and later files are still attempted. Earlier successful files remain committed: the batch is not one all-or-nothing transaction. The existing publication lock, checksum checks, revision history, and missing-value preservation also apply to batches. Conflicting known values fail; there is deliberately no batch-wide correction approval flag. Review the relevant export and use `import-smard FILE --start-date START --end-date END --accept-corrections` explicitly if appropriate.

Standard output contains a JSON report with UTC start/finish times, per-file outcomes, successful run IDs, counts of succeeded/no-change/failed files, and inserted/updated measurement totals. A top-level `succeeded` status includes clean batches of only no-change files. Exit code **0** means all files succeeded or were unchanged; **1** means a file or input directory failed. Invalid CLI arguments use argparse's exit code **2**. Directory-level errors go to standard error without a JSON report. Database error details are replaced with a generic message in the report.

To keep a report and preserve its exit status in a shell:

```bash
mkdir -p .local/reports
energy-ops import-smard-batch ../data/raw/smard > .local/reports/latest-batch.json
batch_exit=$?
echo "Batch exit code: $batch_exit"
```

Publication attempts are recorded in `import_runs` when the database is reachable. Filename/directory failures happen before a database import attempt and appear only in the batch output. Database outages can prevent audit persistence. The batch report itself is not stored as a separate database entity.

After a partial failure, inspect the report, fix the rejected input or database problem, and rerun the same directory. Unchanged successful exports will be skipped. Open **Import history** and press **Refresh** to inspect database-recorded outcomes. This command is suitable for a future scheduler, but automated retrieval, scheduling, and interrupted-run reconciliation remain unimplemented.

## Import behavior

- Every attempt is stored in `import_runs`. Numeric and timestamp errors reject publication.
- A PostgreSQL advisory lock serializes publication. COPY loads a temporary staging table, and publication commits as one transaction.
- Current observations have a unique `(source, interval_start_utc)` key and a 15-minute duration constraint. SQL NUMERIC retains exact decimal values; NULL retains missing measurements.
- Same checksum, normalization policy and period: record a `no_change` attempt. A differently packaged file with the same values also leaves facts unchanged.
- Incoming NULL never overwrites a known value. `preserved_count` records how many such conflicts were ignored.
- Changed known measurements fail by default. After reviewing a newer export, pass `--accept-corrections` to replace them. Previous values and lineage are saved in `observation_revisions`.
- A failure during publication rolls back facts and revisions, then records the failed attempt separately. An interrupted process or database outage may leave a `running` attempt; automatic reconciliation is a later milestone.
- Raw files remain in their original directory. The database stores the filename and checksum; it is not a second immutable copy of the file. Preserve source files and backups independently.

The correction flag represents a deliberate operator choice. Source revision-age ordering, retractions, a workflow dispatcher, and automated acquisition are not yet implemented.

## Query and coverage rules

API date ranges use German local calendar dates and an **exclusive end**. The dashboard's end-date selector is inclusive and converts it to the next local date before querying.

The aggregation query creates the expected 15-minute UTC grid for the requested date range and sources. It counts observed values against that grid, including absent database slots. Spring/autumn days correctly have 92/100 intervals. Missing data never becomes a zero energy total. JSON represents exact decimal MWh values as strings; the chart client converts them for plotting.

Daily/monthly/yearly aggregates describe the selected date span. A partial month/year remains partial. The UI labels incomplete selections as observed energy subtotals and includes completeness columns in CSV exports. Future empty slots in the 2026 annual file are preserved but the dashboard date picker defaults to the observed coverage.

The overview reports latest observed coverage, not a proof of continuously complete data. Timestamp warnings cover successful loaded exports. These are expected source-label normalization notes, not unexplained data repair.

## Tests

```bash
ruff check .
ruff format --check .
python -m pytest
python -m build --no-isolation
```

The PostgreSQL tests require a **separate disposable database** whose name ends in `_test`. They truncate tables in that test database. They never use `DATABASE_URL` as an implicit fallback.

```bash
docker compose exec -T db createdb -U energy_ops energy_ops_test
# Set TEST_DATABASE_URL to the separate energy_ops_test database using your local credentials.
python -m pytest -m integration
```

`energy_ops_test` already exists on the development laptop. GitHub Actions starts its own ephemeral PostgreSQL service and runs these tests on each supported Python version.

## Local backups

Before significant data changes, create a logical backup in the ignored local directory:

```bash
mkdir -p .local/backups
docker compose exec -T db pg_dump -U energy_ops -d energy_ops -Fc > .local/backups/energy_ops.dump
```

Keep a copy outside the laptop if you need machine-loss protection. Do not run `docker compose down -v` unless you intentionally want to remove the project's database volume. A tested restore drill is still part of the later operational milestone.

## Follow-up work

Add authenticated operator actions, durable workflow submission, live source acquisition, stricter role separation, immutable raw-object storage, monitoring/alerts, preprod/prod isolation and a demonstrated backup restore before treating this as an internet-facing production service.

## Dashboard navigation

Dashboard is the operations home: actual import counts, recent execution charts, API/database health checks, and today’s runs. Timeseries contains generation charts and CSV exports. Data quality shows coverage and clock-change notes. Import history supports filename and phase filters. Settings displays local configuration. Argo scheduling is explicitly marked as not configured until orchestration is implemented.
