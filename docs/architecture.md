# Architecture decisions

Status: the Python foundation, SMARD numeric/structural parsing, and complete-grid UTC normalization are implemented. Persistence, the API, dashboard, and deployment remain planned.

## Objective

Let analysts inspect German renewable-generation data and let operators recover failed imports without duplicate or partially published facts.

## Planned data flow

```text
SMARD export -> immutable raw file -> Python validation and normalization
             -> PostgreSQL -> FastAPI -> Streamlit
```

Argo will later run the same ingestion command for scheduled and manual jobs. AKS is a later deployment milestone. PostgreSQL is the initial database; Oracle, contracts, settlement and simulated customer readings are outside the first release.

## Boundaries

- Keep parsing and time-series rules independent of HTTP, SQL and orchestration.
- Add adapters and persistence modules when their behavior is implemented.
- Preserve original inputs and record file checksum, row, parser version and import provenance.
- Publish accepted data in a transaction; keep failure diagnostics when publication rolls back.
- Distinguish workflow success from source completeness.
- Handle corrections as versioned observations; prevent old replays from overwriting newer data.
- API/UI users see committed data, coverage and units; missing values remain visible.

## First implementation gate

A parser must correctly handle normal days, both daylight-saving transitions, leap days, numeric zeros and missing markers. Detectable ordering defects and structurally invalid files must fail clearly. This contract now has automated tests; all four local annual exports have passed normalization with unchanged measurements. The next implementation gate is PostgreSQL schema/migrations, atomic publication, and duplicate-safe reruns.

## Production gate

Later releases require authorization, durable requests, concurrency control, recovery tests, observability, separate environment credentials, deployment rollback and a demonstrated backup restore. Naming an environment `prod` does not establish these properties.
