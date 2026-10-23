# Architecture decisions

Status: numeric parsing, UTC normalization, PostgreSQL storage, the read-only FastAPI service, and a five-view custom HTML/CSS/JavaScript dashboard are implemented locally. Workflow automation and cloud deployment remain planned.

## Objective

Let analysts inspect German renewable-generation data and let operators recover failed imports without duplicate or partially published facts.

## Planned data flow

```text
SMARD export -> immutable raw file -> Python validation and normalization
             -> PostgreSQL -> FastAPI -> HTML/CSS/JavaScript
```

Argo will later run the same ingestion command for scheduled and manual jobs. AKS is a later deployment milestone. PostgreSQL stores measurements, import attempts and previous corrected values. Oracle, contracts, settlement and simulated customer readings are outside the first release. See the [local runbook](local-runbook.md) for the implemented behavior and current limitations.

## Boundaries

- Keep parsing and time-series rules independent of HTTP, SQL and orchestration.
- Add adapters and persistence modules when their behavior is implemented.
- Preserve original inputs and record file checksum, row, parser version and import provenance.
- Publish accepted data in a transaction; keep failure diagnostics when publication rolls back.
- Distinguish workflow success from source completeness.
- Handle corrections as versioned observations; prevent old replays from overwriting newer data.
- API/UI users see committed data, coverage and units; missing values remain visible.

## First implementation gate

A parser must correctly handle normal days, both daylight-saving transitions, leap days, numeric zeros and missing markers. Detectable ordering defects and structurally invalid files must fail clearly. All four annual exports have passed normalization and loading. PostgreSQL integration tests cover duplicate-safe reruns, explicit corrections, preservation of known values, constraints and publication rollback. API tests cover aggregation, coverage, provenance and query bounds.

## Production gate

Later releases require authorization, durable requests, concurrency control, recovery tests, observability, separate environment credentials, deployment rollback and a demonstrated backup restore. Naming an environment `prod` does not establish these properties.

## Web frontend

FastAPI serves `web/index.html` at `/` and packaged static assets at `/assets/`. The same origin supplies the read-only `/v1/` API, so no browser CORS configuration, CDN, frontend build, or second frontend service dependency is required. The local launcher runs the application on ports 18000 (API documentation) and 18501 (dashboard); both expose the same routes and use the same PostgreSQL database. One instance can serve both UI and API in a later deployment.

The browser converts exact decimal API strings to numbers only for display; CSV exports retain the original decimal strings. The overview fetches per-source intervals for selections of at most 31 days, inserts absent 15-minute slots into the chart grid, and converts MWh per quarter-hour to average MW by multiplying by four. Stacked areas are drawn only across contiguous slots with all six sources available; gaps are preserved. Longer overview selections and analytical pages use API aggregates. The frontend displays reachability snapshots rather than continuously monitored service health.
