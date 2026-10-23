# Dashboard UI guide

[Back to project README](../README.md) · [Start the local services](local-runbook.md)

The Streamlit dashboard reads imported German SMARD generation data through FastAPI. PostgreSQL stores the measurements and execution history. The current workspace uses local historical CSV exports; it does not fetch live measurements or schedule imports.

## Navigation

Use the left sidebar to open Dashboard, Timeseries, Data quality, Import history, or Settings. The navy header identifies the local workspace. **Refresh** clears cached responses and reruns the current page; it does not import files. The last-import timestamp describes the latest recorded finished attempt, not the latest measurement.

## Dashboard

[![Operations overview with status cards and execution charts](screenshots/dashboard-overview.jpg)](screenshots/dashboard-overview.jpg)

The home page answers: did the imports work, what data is stored, and are the services reachable?

- **Recent import runs**, **Succeeded imports**, **Failed imports**, and **No-change runs** summarize the latest 200 recorded attempts. No change means an identical export was safely skipped.
- **Renewable sources** counts the six source categories. **Observed measurements** counts stored non-missing source values. **Unavailable export slots** counts stored missing values, including future empty slots in annual exports; it is not an outage count.
- **Validated intervals** counts the loaded 15-minute calendar slots. Each slot has six source records. **Recent timestamp notes** counts recognized clock-change label discrepancies in successful imports within the recent run history.
- **API service** and **PostgreSQL database** show health-check results and their check time. They describe reachability, not data freshness.
- **Job Execution Trends** shows recorded attempts over the last five days. **Job Distribution** summarizes outcomes within the recent run history.
- **Scheduled Workflows** states that Argo is not configured. **Today's Runs** lists attempts started on the current German local date, with filename search and a phase filter.

Cards describing stored measurements cover the whole loaded database; execution counts cover the latest 200 attempts.

## Timeseries

[![Generation analysis with date and source filters](screenshots/dashboard-timeseries.jpg)](screenshots/dashboard-timeseries.jpg)

1. Choose a **Year** to set the initial date range, then adjust the start and end dates. The UI includes the selected end date.
2. Choose **Daily**, **Monthly**, or **Yearly** chart resolution. Aggregates cover only the selected dates, so a partial month or year remains partial.
3. Select one or more **Energy sources**. The metrics and charts update together.
4. Inspect generation by source, the generation mix, and source-level coverage. Hover over Plotly charts for values and use their toolbar to zoom or save a chart image.
5. Open **Explore and Export** to inspect the aggregate rows and select **Download Selected Data · CSV**.

The headline energy metric uses TWh, charts use GWh, and the exported energy column uses MWh. Coverage is observed source/interval measurements divided by expected source/interval measurements. A measured zero is valid data; a missing value is unavailable. When anything is missing, energy is labelled as an observed subtotal rather than a complete total. Date selections and aggregation periods follow Europe/Berlin, including daylight-saving changes.

## Data quality

Use the same date, resolution, and source filters to inspect the coverage heatmap. **Timestamp Normalization Notes** shows recognized source-label discrepancies recorded during successful imports; these notes cover loaded exports, not only the selected chart period. The export table includes expected, observed, and missing counts, coverage percentage, and a completeness flag.

## Import history

Search for part of a CSV filename and choose a **Phase** to narrow the recent run list. Each row shows its start, finish, and outcome in Europe/Berlin time. Failed runs expose their recorded error, and **Publication Counts** shows inserted, updated, preserved, and missing counts. Importing and approving corrections remain CLI operations; this page displays their results.

## Settings

Settings displays the local region, source, timezone, measurement resolution, energy unit, API address, import mode, and scheduling status. It is read-only; configuration is managed in project files, and credentials are not displayed.

## Screenshot maintenance

Screenshots are stored in `docs/screenshots/` and were captured from the running local application on 23 October 2026. They contain real imported data and execution results, so their counts are examples rather than fixed expectations. After a substantial UI change, replace the screenshots and review this guide and the README together. The README uses repository-relative image links so GitHub can render them after the files are committed and pushed.
