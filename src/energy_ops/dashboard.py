"""Operations-focused Streamlit UI backed by the read-only FastAPI service."""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

from energy_ops.ui_components import PHASES, card, html_table, service_card, shell

load_dotenv()
API_URL = os.environ.get("ENERGY_OPS_API_URL", "http://127.0.0.1:18000")
ZONE = ZoneInfo("Europe/Berlin")
LABELS = {
    "wind_onshore": "Wind onshore",
    "wind_offshore": "Wind offshore",
    "photovoltaics": "Solar",
    "biomass": "Biomass",
    "hydropower": "Hydropower",
    "other_renewable": "Other renewables",
}
COLORS = {
    "Wind onshore": "#07588a",
    "Wind offshore": "#639ed7",
    "Solar": "#edaa23",
    "Biomass": "#5b9c63",
    "Hydropower": "#3e91b4",
    "Other renewables": "#a18bc3",
}
STATUS_COLORS = {
    "Succeeded": "#22c55e",
    "Failed": "#ef4444",
    "No change": "#f0a300",
    "Running": "#5d99d4",
}
st.set_page_config(page_title="Energy Operations Dashboard", page_icon="⚡", layout="wide")
shell()


@st.cache_data(ttl=60, show_spinner=False)
def fetch(path: str, parameters: tuple = ()) -> dict:
    response = requests.get(f"{API_URL}{path}", params=list(parameters), timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=10, show_spinner=False)
def health() -> dict:
    statuses = {}
    for name, path in (("api", "/health/live"), ("database", "/health/ready")):
        try:
            statuses[name] = requests.get(f"{API_URL}{path}", timeout=5).status_code == 200
        except requests.RequestException:
            statuses[name] = False
    statuses["checked_at"] = datetime.now(ZONE).strftime("%d %b %H:%M:%S %Z")
    return statuses


def chart_style(figure, height=290):
    figure.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial", "color": "#56677c", "size": 11},
        margin={"l": 10, "r": 10, "t": 12, "b": 12},
        legend={"orientation": "h", "y": 1.15, "x": 1, "xanchor": "right", "title": ""},
    )
    figure.update_yaxes(gridcolor="#edf0f4", zeroline=False)
    figure.update_xaxes(showgrid=False)
    return figure


def run_frame(runs):
    columns = [
        "filename",
        "status",
        "started_at",
        "finished_at",
        "inserted_count",
        "updated_count",
        "preserved_count",
        "missing_count",
        "id",
    ]
    frame = pd.DataFrame(runs) if runs else pd.DataFrame(columns=columns)
    for timestamp in ("started_at", "finished_at"):
        frame[timestamp] = pd.to_datetime(frame[timestamp], utc=True).dt.tz_convert(ZONE)
    return frame


def runs_table(frame, *, key):
    search_column, phase_column, _ = st.columns([2.5, 1.5, 5])
    with search_column:
        search = st.text_input(
            "Search runs",
            placeholder="Search...",
            key=f"{key}_search",
            label_visibility="collapsed",
        )
    with phase_column:
        phase = st.selectbox(
            "Phase",
            ["All", *[v[0] for v in PHASES.values()]],
            key=f"{key}_phase",
            label_visibility="collapsed",
        )
    selected = frame
    if search:
        selected = selected[selected["filename"].str.contains(search, case=False, regex=False)]
    if phase != "All":
        code = next(code for code, value in PHASES.items() if value[0] == phase)
        selected = selected[selected["status"] == code]
    table = pd.DataFrame(
        {
            "Name": selected["filename"],
            "Started": selected["started_at"].dt.strftime("%d %b %H:%M:%S %Z"),
            "Finished": selected["finished_at"].dt.strftime("%d %b %H:%M:%S %Z").fillna("—"),
            "Phase": selected["status"],
        }
    )
    html_table(table, phase_column="Phase")
    st.caption(f"{len(table)} of {len(frame)} runs shown · Europe/Berlin")
    return selected


def operations(overview, runs):
    history = run_frame(runs)
    counts = history["status"].value_counts()
    row1 = st.columns(3)
    metrics1 = [
        ("RECENT IMPORT RUNS", f"{len(runs):,}", "Latest 200 recorded attempts", "▦", "info"),
        (
            "SUCCEEDED IMPORTS",
            str(counts.get("succeeded", 0)),
            "Published successfully",
            "✓",
            "success",
        ),
        ("FAILED IMPORTS", str(counts.get("failed", 0)), "Publication failures", "!", "danger"),
    ]
    for column, args in zip(row1, metrics1, strict=True):
        with column:
            card(*args)
    row2 = st.columns(3)
    metrics2 = [
        (
            "RENEWABLE SOURCES",
            str(overview["source_count"]),
            "Germany · actual generation",
            "▤",
            "info",
        ),
        (
            "OBSERVED MEASUREMENTS",
            f"{overview['observed_measurements']:,}",
            "Non-missing values in PostgreSQL",
            "✓",
            "success",
        ),
        (
            "UNAVAILABLE EXPORT SLOTS",
            f"{overview['unavailable_measurements']:,}",
            "Includes future empty export slots",
            "!",
            "warning",
        ),
    ]
    for column, args in zip(row2, metrics2, strict=True):
        with column:
            card(*args)
    row3 = st.columns(3)
    notes = sum(len(run["warnings"]) for run in runs if run["status"] == "succeeded")
    metrics3 = [
        (
            "VALIDATED INTERVALS",
            f"{overview['measurement_records'] // 6:,}",
            "15-minute calendar slots",
            "◷",
            "info",
        ),
        ("RECENT TIMESTAMP NOTES", str(notes), "Recognized clock-change labels", "✓", "success"),
        (
            "NO-CHANGE RUNS",
            str(counts.get("no_change", 0)),
            "Safe reruns · no duplicate records",
            "↻",
            "warning",
        ),
    ]
    for column, args in zip(row3, metrics3, strict=True):
        with column:
            card(*args)
    services = health()
    left, right = st.columns(2)
    with left:
        service_card("API SERVICE", services["api"], services["checked_at"])
    with right:
        service_card("POSTGRESQL DATABASE", services["database"], services["checked_at"])

    today = datetime.now(ZONE).date()
    grouped = history.assign(day=history["started_at"].dt.date).groupby(["day", "status"]).size()
    trend = pd.DataFrame(
        [
            {
                "Date": today - timedelta(days=offset),
                "Jobs": int(grouped.get((today - timedelta(days=offset), code), 0)),
                "Status": display[0],
            }
            for offset in reversed(range(5))
            for code, display in PHASES.items()
        ]
    )
    trend_column, distribution_column = st.columns([1.9, 1])
    with trend_column, st.container(border=True):
        st.subheader("Job Execution Trends")
        st.caption("Last 5 days · recorded import attempts")
        area = px.area(trend, x="Date", y="Jobs", color="Status", color_discrete_map=STATUS_COLORS)
        area.update_traces(line={"width": 1.5})
        st.plotly_chart(chart_style(area), width="stretch")
    with distribution_column, st.container(border=True):
        st.subheader("Job Distribution")
        st.caption("Recent import outcomes")
        distribution = pd.DataFrame(
            [
                {"Status": PHASES[code][0], "Jobs": int(count)}
                for code, count in counts.items()
                if code in PHASES
            ]
        )
        if not distribution.empty:
            donut = px.pie(
                distribution,
                names="Status",
                values="Jobs",
                hole=0.55,
                color="Status",
                color_discrete_map=STATUS_COLORS,
            )
            donut.update_traces(textinfo="percent", textposition="inside")
            donut = chart_style(donut)
            donut.update_layout(
                legend={"orientation": "h", "y": -0.08, "x": 0.5, "xanchor": "center"}
            )
            st.plotly_chart(donut, width="stretch")
        else:
            st.info("No imports have been recorded yet.")

    with st.expander("Scheduled Workflows", expanded=True):
        st.caption(
            "Argo scheduling is not configured yet. Current imports run through the local CLI."
        )
        html_table(pd.DataFrame(columns=["Name", "Schedule", "Last Scheduled", "Phase"]))
    with st.expander("Today's Runs", expanded=True):
        todays_runs = history[history["started_at"].dt.date == today]
        runs_table(todays_runs, key="today")


def analytics(overview, runs, *, quality_page):
    if not overview["first_observed_utc"]:
        st.info("Import a SMARD export to start exploring generation.")
        return
    first_day = datetime.fromisoformat(overview["first_observed_utc"]).astimezone(ZONE).date()
    latest = datetime.fromisoformat(overview["latest_observed_utc"]).astimezone(ZONE)
    last_day = (latest - timedelta(microseconds=1)).date()
    with st.expander("Filters", expanded=True):
        year_column, range_column, bucket_column = st.columns([1, 2, 1])
        with year_column:
            selected_year = st.selectbox("Year", list(range(last_day.year, first_day.year - 1, -1)))
        with range_column:
            selection = st.date_input(
                "Date range",
                value=(
                    max(first_day, date(selected_year, 1, 1)),
                    min(last_day, date(selected_year, 12, 31)),
                ),
                min_value=first_day,
                max_value=last_day,
                format="DD/MM/YYYY",
            )
        with bucket_column:
            aggregation = st.selectbox("Chart resolution", ["Daily", "Monthly", "Yearly"])
        selected = st.multiselect(
            "Energy sources", list(LABELS), default=list(LABELS), format_func=LABELS.get
        )
    if len(selection) != 2 or not selected:
        st.info("Choose a date range and at least one source.")
        return
    start, inclusive_end = selection
    end = inclusive_end + timedelta(days=1)
    parameters = (
        ("start_date", start.isoformat()),
        ("end_date", end.isoformat()),
        ("bucket", {"Daily": "day", "Monthly": "month", "Yearly": "year"}[aggregation]),
        *(("sources", source) for source in selected),
    )
    try:
        frame = pd.DataFrame(fetch("/v1/generation/summary", parameters)["data"])
    except (requests.RequestException, ValueError):
        st.error("Could not retrieve this date range. Refresh or choose a shorter range.")
        return
    if frame.empty:
        st.info("No data is available for this selection.")
        return
    frame["observed_energy_mwh"] = pd.to_numeric(frame["observed_energy_mwh"], errors="raise")
    frame["Energy (GWh)"] = frame["observed_energy_mwh"] / 1000
    frame["Source"] = frame["source"].map(LABELS)
    frame["Date"] = pd.to_datetime(frame["bucket_start"])
    expected, observed = (
        int(frame["expected_intervals"].sum()),
        int(frame["observed_intervals"].sum()),
    )
    missing = expected - observed
    energy = frame["observed_energy_mwh"].sum(min_count=1)
    st.caption(
        f"{start:%d %b %Y} — {inclusive_end:%d %b %Y} · {len(selected)} sources · Europe/Berlin"
    )
    if missing:
        st.warning(
            f"{missing:,} source/interval measurements are unavailable. "
            "Energy figures are observed subtotals; incomplete periods are marked below."
        )
    cards = st.columns(4)
    cards[0].metric(
        "Observed energy (TWh)" if missing else "Total energy (TWh)",
        f"{energy / 1_000_000:,.2f}" if pd.notna(energy) else "Unavailable",
    )
    cards[1].metric("Data coverage", f"{100 * observed / expected:.2f}%")
    cards[2].metric("Unavailable values", f"{missing:,}")
    cards[3].metric("Observed values", f"{observed:,}")

    if not quality_page:
        with st.container(border=True):
            st.subheader(f"{aggregation} Generation by Source")
            figure = px.line(
                frame, x="Date", y="Energy (GWh)", color="Source", color_discrete_map=COLORS
            )
            figure.update_traces(connectgaps=False, line={"width": 2})
            st.plotly_chart(chart_style(figure, 370), width="stretch")
        left, right = st.columns([1.2, 1])
        with left, st.container(border=True):
            st.subheader("Generation Mix")
            totals = frame.groupby("Source", as_index=False)["Energy (GWh)"].sum(min_count=1)
            bars = px.bar(
                totals.sort_values("Energy (GWh)"),
                x="Energy (GWh)",
                y="Source",
                color="Source",
                orientation="h",
                color_discrete_map=COLORS,
            )
            bars.update_layout(showlegend=False)
            st.plotly_chart(chart_style(bars), width="stretch")
        with right, st.container(border=True):
            st.subheader("Coverage by Source")
            quality = frame.groupby("Source", as_index=False)[
                ["observed_intervals", "expected_intervals", "missing_intervals"]
            ].sum()
            quality["Coverage (%)"] = (
                100 * quality["observed_intervals"] / quality["expected_intervals"]
            ).round(2)
            html_table(
                quality[["Source", "Coverage (%)", "missing_intervals"]].rename(
                    columns={"missing_intervals": "Unavailable"}
                )
            )
    else:
        with st.container(border=True):
            st.subheader("Coverage Across the Selected Period")
            heat = frame.pivot(index="Source", columns="Date", values="coverage_percent")
            figure = px.imshow(
                heat,
                aspect="auto",
                zmin=0,
                zmax=100,
                color_continuous_scale=["#efb45e", "#e5f2ed", "#279e62"],
                labels={"color": "Coverage (%)"},
            )
            st.plotly_chart(chart_style(figure, 330), width="stretch")
        with st.expander("Timestamp Normalization Notes", expanded=True):
            warnings = [
                {
                    "File": run["filename"],
                    "CSV Row": warning["source_row"],
                    "Source End Label": warning["original_end_label"],
                    "Canonical Local End": warning["canonical_local_end"],
                }
                for run in runs
                if run["status"] == "succeeded"
                for warning in run["warnings"]
            ]
            html_table(pd.DataFrame(warnings))
            st.caption(
                "Recorded notes cover loaded exports, including empty future calendar slots."
            )

    with st.expander("Explore and Export", expanded=True):
        export = frame[
            [
                "bucket_start",
                "Source",
                "observed_energy_mwh",
                "expected_intervals",
                "observed_intervals",
                "missing_intervals",
                "coverage_percent",
                "is_complete",
            ]
        ]
        st.dataframe(export, hide_index=True, width="stretch")
        st.download_button(
            "Download Selected Data · CSV",
            export.to_csv(index=False).encode(),
            file_name=f"renewable-generation-{start}-{inclusive_end}.csv",
            mime="text/csv",
        )
        st.caption(
            "Derived from Bundesnetzagentur | SMARD.de, CC BY 4.0; "
            "aggregated by German local period, energy in MWh."
        )


navigation = {
    "Dashboard": "▦  Dashboard",
    "Timeseries": "⌁  Timeseries",
    "Data quality": "◴  Data quality",
    "Import history": "▤  Import history",
    "Settings": "⚙  Settings",
}
with st.sidebar:
    page = st.radio(
        "Navigation", list(navigation), format_func=navigation.get, label_visibility="collapsed"
    )
    with st.expander("Germany"):
        st.caption("Actual renewable generation\n\nEurope/Berlin · 15-minute intervals")
    st.divider()
    st.markdown('<div class="ops-kicker">LOCAL WORKSPACE</div>', unsafe_allow_html=True)
    st.caption("Historical SMARD exports")

header, refresh = st.columns([4, 1])
with header:
    st.title("Energy Operations Dashboard" if page == "Dashboard" else page.title())
    st.caption(
        {
            "Dashboard": "Import performance, data quality, and system health.",
            "Timeseries": "Renewable generation trends and source-level coverage.",
            "Data quality": "Measurement completeness and timestamp normalization.",
            "Import history": "Recorded executions, publication outcomes, and recovery details.",
            "Settings": "Current local workspace configuration.",
        }[page]
    )
with refresh:
    if st.button("↻ Refresh", width="stretch"):
        st.cache_data.clear()
        st.rerun()

try:
    overview = fetch("/v1/overview")
    runs = fetch("/v1/runs", (("limit", 200),))["data"]
except (requests.RequestException, ValueError):
    st.error("The data service is unavailable. Start ./scripts/start-local.sh and refresh.")
    st.stop()

if runs:
    latest_import = max((run["finished_at"] for run in runs if run["finished_at"]), default=None)
    if latest_import:
        last = datetime.fromisoformat(latest_import).astimezone(ZONE)
        st.caption(
            f"Last import attempt: {last:%d %b %H:%M %Z} · Manual imports · No active schedule"
        )
st.divider()

if page == "Dashboard":
    operations(overview, runs)
elif page in ("Timeseries", "Data quality"):
    analytics(overview, runs, quality_page=page == "Data quality")
elif page == "Import history":
    with st.container(border=True):
        st.subheader("Import Runs")
        filtered = runs_table(run_frame(runs), key="history")
    for _, run in filtered.iterrows():
        if run.get("error"):
            with st.expander(f"Failed: {run['filename']}"):
                st.code(run["error"])
    with st.expander("Publication Counts", expanded=False):
        st.dataframe(
            filtered[
                ["filename", "inserted_count", "updated_count", "preserved_count", "missing_count"]
            ],
            hide_index=True,
            width="stretch",
        )
else:
    with st.container(border=True):
        st.subheader("Workspace Configuration")
        html_table(
            pd.DataFrame(
                [
                    ("Environment", "Local"),
                    ("Region", "Germany"),
                    ("Source", "Bundesnetzagentur | SMARD.de"),
                    ("Timezone", "Europe/Berlin"),
                    ("Resolution", "15 minutes"),
                    ("Stored energy unit", "MWh"),
                    ("API", API_URL),
                    ("Import mode", "Local CLI"),
                    ("Argo scheduling", "Not configured"),
                ],
                columns=["Setting", "Value"],
            )
        )
        st.caption("Configuration is managed in the project files; secrets are not shown here.")

st.divider()
st.caption("Bundesnetzagentur | SMARD.de · CC BY 4.0 · Historical exports · Europe/Berlin")
