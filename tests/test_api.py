"""API checks against actual PostgreSQL data, including absent and incomplete periods."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from energy_ops.api import create_app
from energy_ops.ingestion import import_file

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_engine, day_export):
    import_file(db_engine, day_export, start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))
    with TestClient(create_app(db_engine)) as api:
        yield api


def test_overview_and_health(client):
    assert client.get("/health/ready").status_code == 200
    stats = client.get("/v1/overview").json()
    assert stats["measurement_records"] == 576
    assert stats["observed_measurements"] == 480
    assert stats["source_count"] == 6
    assert client.get("/v1/runs").json()["data"][0]["status"] == "succeeded"


def test_daily_aggregation_and_missing_values(client):
    response = client.get(
        "/v1/generation/summary", params={"start_date": "2024-01-01", "end_date": "2024-01-02"}
    )
    assert response.status_code == 200, response.text
    rows = {row["source"]: row for row in response.json()["data"]}
    assert rows["biomass"]["observed_energy_mwh"] == "96"
    assert rows["biomass"]["is_complete"] is True
    assert rows["other_renewable"]["observed_energy_mwh"] is None
    assert rows["other_renewable"]["missing_intervals"] == 96
    assert rows["photovoltaics"]["observed_energy_mwh"] == "0"


def test_absent_period_is_not_reported_as_zero_or_complete(client):
    response = client.get(
        "/v1/generation/summary",
        params={"start_date": "2024-01-02", "end_date": "2024-01-03", "sources": "biomass"},
    )
    row = response.json()["data"][0]
    assert row["expected_intervals"] == 96
    assert row["observed_intervals"] == 0
    assert row["observed_energy_mwh"] is None
    assert row["is_complete"] is False


@pytest.mark.parametrize(
    ("day", "next_day", "expected"),
    [("2024-03-31", "2024-04-01", 92), ("2024-10-27", "2024-10-28", 100)],
)
def test_sql_expected_counts_handle_clock_changes(client, day, next_day, expected):
    response = client.get(
        "/v1/generation/summary",
        params={"start_date": day, "end_date": next_day, "sources": "biomass"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["expected_intervals"] == expected


@pytest.mark.parametrize(
    "parameters",
    [
        {"start_date": "2024-01-02", "end_date": "2024-01-01"},
        {"start_date": "2020-01-01", "end_date": "2030-01-01"},
        {"start_date": "2024-01-01", "end_date": "2024-01-02", "sources": "unknown"},
    ],
)
def test_query_limits(client, parameters):
    assert client.get("/v1/generation/summary", params=parameters).status_code == 422


def test_interval_queries_include_provenance(client):
    response = client.get(
        "/v1/generation/intervals",
        params={
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "source": "biomass",
            "limit": 2,
        },
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 2
    assert rows[0]["source_row"] == 2
    assert rows[0]["energy_mwh"] == "1"
    assert rows[0]["filename"] == "generation.csv"
    assert rows[0]["interval_start_utc"].startswith("2023-12-31T23:00:00")
