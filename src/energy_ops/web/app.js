import {
  SOURCES,
  esc,
  nextDay,
  berlinDate,
  coverage,
  summarySeries,
  intervalSeries,
  stackable,
  csv,
} from "./data.js";

const $ = (selector) => document.querySelector(selector);
const num = (value, digits = 0) =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: digits }).format(
    value,
  );
const timestamp = (value) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/Berlin",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(new Date(value))
    : "Running";
const dayLabel = (value) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Berlin",
    day: "numeric",
    month: "short",
  }).format(new Date(value.length === 10 ? value + "T12:00:00Z" : value));
const icons = {
  home: '<path d="m3 10 9-7 9 7v10H6V10M9 20v-7h6v7"/>',
  chart: '<path d="M4 20V10h3v10M10 20V5h3v15M16 20V2h3v18"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 6-7"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  settings:
    '<path d="m9 3-1 3-3 1-2 4 2 3v3l4 3 3-1 3 1 4-3v-3l2-3-2-4-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
  database:
    '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v13c0 4 16 4 16 0V5M4 10c0 4 16 4 16 0M4 15c0 4 16 4 16 0"/>',
  refresh:
    '<path d="M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/>',
  monitor:
    '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4M6 13h12"/>',
  code: '<path d="m8 5-6 7 6 7m8-14 6 7-6 7m-3-17-2 20"/>',
  flow: '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5H5v5m7-5h7v5"/>',
  arrow: '<path d="M3 12h17m-6-6 6 6-6 6"/>',
};
const icon = (name) =>
  `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${icons[name] || icons.chart}</svg>`;
document
  .querySelectorAll("[data-icon]")
  .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
const pages = {
  overview: [
    "Overview",
    "Renewable generation, data imports and system health at a glance.",
    "home",
  ],
  timeseries: [
    "Timeseries",
    "Explore renewable generation and source-level coverage.",
    "chart",
  ],
  quality: [
    "Data quality",
    "Measurement completeness and timestamp normalization.",
    "check",
  ],
  imports: [
    "Imports",
    "Recorded executions, publication outcomes and correction history.",
    "download",
  ],
  settings: ["Settings", "Your local workspace configuration.", "settings"],
};
$("nav").innerHTML = Object.entries(pages)
  .map(
    ([id, [name, , symbol]]) =>
      `<a href="#${id}" data-page="${id}">${icon(symbol)}<span>${name}</span></a>`,
  )
  .join("");
let metadata = null,
  runs = [],
  health = {},
  selected = SOURCES.map((s) => s.id),
  bucket = "day",
  revision = 0;
let currentSummary = [];
async function api(path) {
  const response = await fetch(path, {
    cache: "no-store",
    signal: AbortSignal.timeout(25000),
  });
  if (!response.ok)
    throw new Error(
      response.status === 503
        ? "The database is unavailable. Start the local services and retry."
        : `Could not load data (HTTP ${response.status}).`,
    );
  return response.json();
}
async function loadMetadata() {
  const [overview, history, live, ready] = await Promise.all([
    api("/v1/overview"),
    api("/v1/runs?limit=200"),
    api("/health/live").catch(() => null),
    api("/health/ready").catch(() => null),
  ]);
  metadata = overview;
  runs = history.data;
  health = {
    api: !!live,
    database: !!ready,
    checked: new Date().toISOString(),
  };
  if (overview.first_observed_utc) {
    const first = berlinDate(overview.first_observed_utc),
      last = berlinDate(Date.parse(overview.latest_observed_utc) - 1);
    for (const field of [$("#start"), $("#end")]) {
      field.min = first;
      field.max = last;
    }
    if (!$("#end").value) {
      $("#end").value = last;
      $("#start").value = [first, nextDay(last, -6)].sort().at(-1);
    }
  }
}
function page() {
  return pages[location.hash.slice(1)] ? location.hash.slice(1) : "overview";
}
function dateQuery(resolution = bucket, sources = selected) {
  const start = $("#start").value,
    end = $("#end").value;
  if (
    !start ||
    !end ||
    start > end ||
    start < $("#start").min ||
    end > $("#end").max
  )
    throw new Error(
      "Choose valid start and end dates within the loaded observations.",
    );
  const query = new URLSearchParams({
    start_date: start,
    end_date: nextDay(end),
    bucket: resolution,
  });
  sources.forEach((source) => query.append("sources", source));
  return query;
}
function status(value) {
  const label =
    {
      succeeded: "Succeeded",
      no_change: "No change",
      failed: "Failed",
      running: "Running",
    }[value] || value;
  const tone =
    {
      succeeded: "online",
      no_change: "neutral",
      failed: "offline",
      running: "neutral",
    }[value] || "neutral";
  return `<span class="status ${tone}"><i class="dot" style="background:currentColor"></i>${esc(label)}</span>`;
}
function table(headers, rows, extra = "") {
  return `<div class="table-scroll"><table class="${extra}"><thead><tr>${headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}" class="empty">No matching records</td></tr>`}</tbody></table></div>`;
}
function stat(label, value, note, symbol) {
  return `<div class="stat"><span class="stat-icon">${icon(symbol)}</span><div><div class="stat-label">${esc(label)}</div><strong class="stat-value">${esc(value)}</strong><small class="stat-note">${esc(note)}</small></div></div>`;
}
function healthPanel() {
  return `<section class="panel health"><h2>Service health</h2><p class="panel-subtitle">Current local service reachability.</p>${[
    ["API", "code", health.api],
    ["PostgreSQL", "database", health.database],
    ["Argo", "flow", null],
  ]
    .map(
      ([label, symbol, online]) =>
        `<div class="service">${icon(symbol)}<span>${label}</span><span class="state ${online === null ? "neutral" : online ? "online" : "offline"}"><i class="dot" style="background:currentColor"></i>${online === null ? "Not configured" : online ? "Online" : "Unavailable"}</span></div>`,
    )
    .join(
      "",
    )}<p class="health-time">Checked ${esc(timestamp(health.checked))}</p></section>`;
}
function coveragePanel(c) {
  return `<section class="panel"><h2>Data coverage</h2><p class="panel-subtitle">Share of expected measurements available<br>for the selected period.</p><div class="coverage-body"><div class="ring" role="img" aria-label="Coverage ${c.percent.toFixed(2)} percent" style="background:conic-gradient(#258346 ${c.percent}%,#e5ebe0 0)"><div class="ring-inner">${c.percent.toFixed(2)}%</div></div><div class="coverage-list"><div><span><i class="dot" style="background:#258346"></i>Available</span><b>${num(c.observed)}</b></div><div><span><i class="dot" style="background:#b8c4ba"></i>Missing</span><b>${num(c.missing)}</b></div><div><span>Total expected</span><b>${num(c.expected)}</b></div></div></div></section>`;
}
function runRows(rows) {
  return rows.map((r) => [
    esc(timestamp(r.started_at)),
    status(r.status),
    `<span class="filename" title="${esc(r.filename)}">${esc(r.filename)}</span>`,
    num(r.inserted_count),
    num(r.updated_count),
    num(r.preserved_count),
    r.finished_at
      ? num((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 1000, 2) +
        "s"
      : "Running",
  ]);
}
function recentPanel() {
  return `<section class="panel recent"><div class="panel-heading"><div><h2>Recent import runs</h2><p class="panel-subtitle">Latest recorded attempts · independent of generation dates.</p></div><a class="button" href="#imports">View all imports ${icon("arrow")}</a></div>${table(["Start time ↓", "Status", "Source file", "New", "Updated", "Preserved", "Duration"], runRows(runs.slice(0, 6)))}</section>`;
}
function renderChart(data, container, allowStack = true) {
  if (!data.keys.length) {
    container.innerHTML = '<p class="empty">No data for this selection.</p>';
    return;
  }
  const valid = data.keys.map((_, i) =>
    data.series.every(
      (s) =>
        s.values[i] !== null &&
        Number.isFinite(s.values[i]) &&
        s.values[i] >= 0,
    ),
  );
  const stacked =
    allowStack &&
    data.series.length > 0 &&
    valid.some(Boolean) &&
    !data.series.some((s) => s.values.some((v) => v !== null && v < 0));
  const width = 900,
    height = 300,
    left = 75,
    right = 14,
    top = 15,
    bottom = 43,
    pw = width - left - right,
    ph = height - top - bottom;
  const all = data.series.flatMap((s) => s.values.filter((v) => v !== null));
  const totals = data.keys.map((_, i) =>
    data.series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0),
  );
  const max = Math.max(1, ...(stacked ? totals : all)) * 1.08,
    min = Math.min(0, ...all);
  const x = (i) => left + (i * pw) / Math.max(1, data.keys.length - 1),
    y = (v) => top + ((max - v) * ph) / (max - min);
  const segments = (values) => {
    const result = [];
    let segment = [];
    values.forEach((v, i) => {
      if (v === null) {
        if (segment.length) result.push(segment);
        segment = [];
      } else segment.push([i, v]);
    });
    if (segment.length) result.push(segment);
    return result;
  };
  let paths = "",
    baseline = data.keys.map(() => 0);
  for (const series of data.series) {
    if (stacked) {
      const upper = series.values.map((v, i) =>
        valid[i] ? v + baseline[i] : null,
      );
      paths += segments(upper)
        .map(
          (segment) =>
            `<path d="${segment.map(([i, v], j) => `${j ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(" ")} ${[
              ...segment,
            ]
              .reverse()
              .map(([i]) => `L${x(i).toFixed(2)},${y(baseline[i]).toFixed(2)}`)
              .join(" ")}Z" fill="${series.color}" fill-opacity=".86"/>`,
        )
        .join("");
      baseline = upper.map((v) => v ?? 0);
    } else {
      paths += segments(series.values)
        .map((segment) =>
          segment.length === 1
            ? `<circle cx="${x(segment[0][0])}" cy="${y(segment[0][1])}" r="2" fill="${series.color}"/>`
            : `<path d="${segment.map(([i, v], j) => `${j ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(" ")}" fill="none" stroke="${series.color}" stroke-width="1.7"/>`,
        )
        .join("");
    }
  }
  let grid = "";
  for (let i = 0; i <= 5; i++) {
    const value = min + ((max - min) * i) / 5;
    grid += `<line class="grid" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left - 9}" y="${y(value) + 3}" text-anchor="end">${num(value, max < 10 ? 1 : 0)}</text>`;
  }
  const steps = Math.min(6, data.keys.length - 1);
  for (let i = 0; i <= steps; i++) {
    const j = steps ? Math.round((i * (data.keys.length - 1)) / steps) : 0;
    grid += `<text x="${x(j)}" y="${height - 19}" text-anchor="middle">${esc(dayLabel(data.labels[j]))}</text>`;
  }
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${stacked ? "Stacked renewable generation" : "Renewable generation by source"} in ${data.unit}"><text transform="translate(12 145) rotate(-90)" text-anchor="middle">${data.unit === "MW" ? "Generation (MW)" : "Energy (GWh)"}</text>${grid}${paths}<rect class="chart-hit" x="${left}" y="${top}" width="${pw}" height="${ph}" fill="transparent"/></svg><div class="chart-tooltip" hidden></div><div class="legend">${data.series.map((s) => `<span><i class="dot" style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}</div>`;
  const svg = container.querySelector("svg"),
    tooltip = container.querySelector(".chart-tooltip");
  svg.addEventListener("pointermove", (event) => {
    const box = svg.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const index = Math.max(
      0,
      Math.min(
        data.keys.length - 1,
        Math.round(((ratio * width - left) / pw) * (data.keys.length - 1)),
      ),
    );
    tooltip.textContent =
      (data.unit === "MW"
        ? timestamp(data.labels[index])
        : dayLabel(data.labels[index])) +
      "\n" +
      data.series
        .map(
          (s) =>
            `${s.name}: ${s.values[index] === null ? "Unavailable" : num(s.values[index], 2) + " " + data.unit}`,
        )
        .join("\n");
    tooltip.hidden = false;
    tooltip.style.left =
      Math.min(event.clientX - box.left + 12, box.width - 205) + "px";
    tooltip.style.top = "15px";
  });
  svg.addEventListener("pointerleave", () => (tooltip.hidden = true));
}
async function summary(resolution = bucket, sources = selected) {
  return (await api("/v1/generation/summary?" + dateQuery(resolution, sources)))
    .data;
}
async function overview(token) {
  const rows = await summary(
    "day",
    SOURCES.map((s) => s.id),
  );
  const c = coverage(rows);
  const start = $("#start").value,
    end = $("#end").value,
    days = (Date.parse(end) - Date.parse(start)) / 86400000 + 1;
  let chartData = summarySeries(rows, SOURCES);
  if (days <= 31) {
    const q = new URLSearchParams({
      start_date: start,
      end_date: nextDay(end),
      limit: "5000",
    });
    const response = await Promise.all(
      SOURCES.map((s) =>
        api("/v1/generation/intervals?" + q + "&source=" + s.id),
      ),
    );
    chartData = intervalSeries(response, start, end);
  }
  if (token !== revision) return;
  const count = (status) => runs.filter((r) => r.status === status).length;
  const complete = stackable(chartData);
  $("#content").innerHTML =
    `<div class="overview-grid"><div class="left-stack"><div class="stats">${stat("Observed measurements", num(c.observed), "Selected dates · six sources", "database")}${stat("Import runs", num(runs.length), `${count("succeeded")} succeeded · ${count("no_change")} no change · ${count("failed")} failed`, "refresh")}${stat("Coverage", c.percent.toFixed(2) + "%", "Of expected measurements", "check")}</div><section class="panel generation"><div class="panel-heading"><div><h2>Renewable generation in Germany</h2><p class="panel-subtitle">${days <= 31 ? "15-minute measurements" : "Daily observed energy"} · ${esc(dayLabel(start))} – ${esc(dayLabel(end))} · Europe/Berlin</p></div><span class="chart-unit">${chartData.unit === "MW" ? "Generation (MW)" : "Energy (GWh)"}</span></div>${c.missing ? `<p class="panel-subtitle">${num(c.missing)} unavailable measurements · ${days <= 31 ? "gaps remain where any source is unavailable" : "observed subtotals"}</p>` : ""}<div class="chart" id="generation-chart"></div><p class="health-time">${complete ? "Stacked source contributions." : days <= 31 ? "Areas appear only where all six sources are observed." : "Observed subtotals; incomplete periods use separate lines."} Hover over the chart for values.</p></section></div><div class="right-stack">${coveragePanel(c)}${healthPanel()}</div></div>${recentPanel()}`;
  renderChart(chartData, $("#generation-chart"), days <= 31 || complete);
}
function sourceFilters() {
  return `<div class="filters"><label for="bucket" class="sr-only">Chart resolution</label><select id="bucket"><option value="day">Daily</option><option value="month">Monthly</option><option value="year">Yearly</option></select>${SOURCES.map((s) => `<label class="source-toggle"><input type="checkbox" value="${s.id}" ${selected.includes(s.id) ? "checked" : ""}><i class="dot" style="background:${s.color}"></i>${s.name}</label>`).join("")}<button class="button" id="export">${icon("download")}Export CSV</button></div>`;
}
function wireFilters() {
  $("#bucket").value = bucket;
  $("#bucket").addEventListener("change", (event) => {
    bucket = event.target.value;
    render();
  });
  document.querySelectorAll(".source-toggle input").forEach((el) =>
    el.addEventListener("change", () => {
      selected = [
        ...document.querySelectorAll(".source-toggle input:checked"),
      ].map((v) => v.value);
      render();
    }),
  );
  $("#export").addEventListener("click", () => {
    const columns = [
      "bucket_start",
      "source",
      "observed_energy_mwh",
      "expected_intervals",
      "observed_intervals",
      "missing_intervals",
      "coverage_percent",
      "is_complete",
    ];
    const blob = new Blob([csv(currentSummary, columns)], {
      type: "text/csv;charset=utf-8",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `renewable-generation-${$("#start").value}-${$("#end").value}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
}
async function analytics(token, quality) {
  const rows = selected.length ? await summary() : [];
  if (token !== revision) return;
  currentSummary = rows;
  const c = coverage(rows),
    total = rows
      .filter((r) => r.observed_energy_mwh !== null)
      .reduce((sum, r) => sum + Number(r.observed_energy_mwh), 0);
  const totals = SOURCES.filter((s) => selected.includes(s.id)).map((s) => {
    const data = rows.filter((r) => r.source === s.id);
    return {
      ...s,
      ...coverage(data),
      energy: data.every((r) => r.observed_energy_mwh === null)
        ? null
        : data.reduce((sum, r) => sum + Number(r.observed_energy_mwh ?? 0), 0),
    };
  });
  const metrics = `<div class="analysis-stats">${stat(c.missing ? "Observed energy (TWh)" : "Total energy (TWh)", rows.some((r) => r.observed_energy_mwh !== null) ? num(total / 1e6, 2) : "Unavailable", "Selected period", "chart")}${stat("Data coverage", c.percent.toFixed(2) + "%", "Expected measurement grid", "check")}${stat("Unavailable values", num(c.missing), "Missing stays distinct from zero", "database")}${stat("Observed values", num(c.observed), "Includes measured zeroes", "database")}</div>`;
  const coverageRows = totals.map((s) => [
    esc(s.name),
    s.percent.toFixed(2) + "%",
    num(s.observed),
    num(s.missing),
    s.energy === null ? "Unavailable" : num(s.energy / 1000, 2),
  ]);
  const days = [...new Set(rows.map((r) => r.bucket_start))].sort();
  const heat = totals
    .map(
      (s) =>
        `<div class="heatmap"><strong>${s.name}</strong>${rows
          .filter((r) => r.source === s.id)
          .map(
            (r) =>
              `<span class="heat-cell" style="background:${r.coverage_percent === 100 ? "#429363" : r.coverage_percent >= 95 ? "#b5d5ae" : "#eacb72"}" title="${esc(r.bucket_start)}: ${r.coverage_percent}%" role="img" aria-label="${esc(r.bucket_start)} coverage ${r.coverage_percent}%"></span>`,
          )
          .join("")}</div>`,
    )
    .join("");
  const notes = runs
    .filter((r) => r.status === "succeeded")
    .flatMap((r) =>
      r.warnings.map((w) => [
        esc(r.filename),
        esc(w.source_row),
        esc(w.original_end_label),
        esc(w.canonical_local_end),
      ]),
    );
  $("#content").innerHTML =
    `${sourceFilters()}${!selected.length ? '<p class="notice">Choose at least one energy source.</p>' : ""}${c.missing ? `<p class="notice">${num(c.missing)} source/interval measurements are unavailable. Energy figures are observed subtotals; incomplete periods remain labelled.</p>` : ""}${metrics}${quality ? `<section class="panel"><h2>Coverage across the selected period</h2><p class="panel-subtitle">${esc(days[0] || "")} — ${esc(days.at(-1) || "")} · Green: complete · Pale green: ≥95% · Amber: &lt;95%</p><div class="table-scroll">${heat || '<p class="empty">No sources selected.</p>'}</div></section>` : `<section class="panel"><h2>Generation by source</h2><p class="panel-subtitle">${{ day: "Daily", month: "Monthly", year: "Yearly" }[bucket]} energy · Europe/Berlin</p><div class="chart analysis-chart" id="analysis-chart"></div></section>`}<section class="panel recent"><h2>Source mix and coverage</h2><p class="panel-subtitle">Observed energy for the selected dates.</p><br>${table(["Source", "Coverage", "Observed", "Missing", "Energy (GWh)"], coverageRows)}</section>${quality ? `<section class="panel recent"><h2>Timestamp normalization notes</h2><p class="panel-subtitle">Recognized clock-change labels from recent successful imports, across all loaded periods.</p><br>${table(["File", "CSV row", "Source end label", "Canonical local end"], notes)}</section>` : ""}<details class="detail"><summary>Explore aggregate rows (${rows.length})</summary><br>${table(
      [
        "Period",
        "Source",
        "Observed MWh",
        "Expected",
        "Observed",
        "Missing",
        "Complete",
      ],
      rows.map((r) => [
        esc(r.bucket_start),
        esc(SOURCES.find((s) => s.id === r.source)?.name),
        r.observed_energy_mwh === null
          ? "Unavailable"
          : esc(r.observed_energy_mwh),
        num(r.expected_intervals),
        num(r.observed_intervals),
        num(r.missing_intervals),
        r.is_complete ? "Yes" : "No",
      ]),
    )}</details>`;
  wireFilters();
  if (!quality)
    renderChart(
      summarySeries(
        rows,
        SOURCES.filter((s) => selected.includes(s.id)),
      ),
      $("#analysis-chart"),
      false,
    );
}
function imports() {
  $("#content").innerHTML =
    `<section class="panel"><h2>Import executions</h2><p class="panel-subtitle">Latest 200 attempts. Imports and correction approval remain CLI operations.</p><div class="toolbar"><label class="sr-only" for="search">Search filenames</label><input id="search" type="search" placeholder="Search filenames…"><label class="sr-only" for="phase">Import phase</label><select id="phase"><option value="">All phases</option><option value="succeeded">Succeeded</option><option value="no_change">No change</option><option value="failed">Failed</option><option value="running">Running</option></select></div><div id="run-table"></div><div id="run-details"></div></section>`;
  const update = () => {
    const search = $("#search").value.toLowerCase(),
      phase = $("#phase").value;
    const filtered = runs.filter(
      (r) =>
        r.filename.toLowerCase().includes(search) &&
        (!phase || r.status === phase),
    );
    $("#run-table").innerHTML =
      table(
        [
          "Start time",
          "Status",
          "Source file",
          "New",
          "Updated",
          "Preserved",
          "Duration",
        ],
        runRows(filtered),
      ) +
      `<p class="health-time">${filtered.length} of ${runs.length} runs shown · Europe/Berlin</p>`;
    $("#run-details").innerHTML = filtered
      .map(
        (r) =>
          `<details class="detail"><summary>${status(r.status)} &nbsp; ${esc(r.filename)}</summary><pre>${esc(JSON.stringify({ run_id: r.id, period_start: r.start_date, period_end_exclusive: r.end_date, source_rows: r.source_rows, measurement_records: r.measurement_records, missing_count: r.missing_count, warnings: r.warnings, error: r.error }, null, 2))}</pre></details>`,
      )
      .join("");
  };
  $("#search").addEventListener("input", update);
  $("#phase").addEventListener("change", update);
  update();
}
function settings() {
  const rows = [
    ["Environment", "Local workspace"],
    ["Region", "Germany"],
    ["Data source", "Bundesnetzagentur | SMARD.de"],
    ["Timezone", "Europe/Berlin"],
    ["Source interval", "15 minutes"],
    ["Stored energy unit", "MWh"],
    ["API", location.origin],
    ["Import mode", "Local CLI · single or batch"],
    ["Argo scheduling", "Not configured"],
    ["Loaded source categories", num(metadata.source_count)],
    ["Stored measurements", num(metadata.measurement_records)],
    [
      "Last observed interval end",
      metadata.latest_observed_utc
        ? timestamp(metadata.latest_observed_utc)
        : "Unavailable",
    ],
  ];
  $("#content").innerHTML =
    `<section class="panel"><h2>Workspace configuration</h2><p class="panel-subtitle">Read-only settings. Configuration is managed in project files; secrets are never displayed here.</p><br>${table(
      ["Setting", "Value"],
      rows.map((r) => r.map(esc)),
      "settings-table",
    )}</section>`;
}
async function render() {
  const token = ++revision,
    id = page();
  $("#title").textContent = pages[id][0];
  $("#subtitle").textContent = pages[id][1];
  $("#breadcrumb").innerHTML =
    `Energy Operations <span>/</span> Germany <span>/</span> ${pages[id][0]}`;
  document.querySelectorAll("nav a").forEach((link) => {
    if (link.dataset.page === id) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $(".date-range").hidden = ["imports", "settings"].includes(id);
  $(".date-range").style.display = ["imports", "settings"].includes(id)
    ? "none"
    : "flex";
  $("#message").innerHTML = "";
  $("#content").setAttribute("aria-busy", "true");
  try {
    if (!metadata) await loadMetadata();
    if (token !== revision) return;
    if (!metadata.first_observed_utc && !["imports", "settings"].includes(id)) {
      $("#content").innerHTML =
        '<section class="panel empty"><h2>Your workspace is ready for data</h2><p>Import a SMARD export using energy-ops import-smard-batch, then refresh.</p></section>';
      return;
    }
    if (id === "overview") await overview(token);
    else if (id === "timeseries" || id === "quality")
      await analytics(token, id === "quality");
    else if (id === "imports") imports();
    else settings();
  } catch (error) {
    if (token === revision) {
      $("#message").innerHTML =
        `<p class="notice error">${esc(error.message)} Your existing data has not been changed.</p>`;
      $("#content").innerHTML =
        '<p class="empty">Adjust the selection or use Refresh to retry.</p>';
    }
  } finally {
    if (token === revision) $("#content").setAttribute("aria-busy", "false");
  }
}
$("#refresh").addEventListener("click", async () => {
  const button = $("#refresh");
  button.disabled = true;
  try {
    await loadMetadata();
    await render();
  } catch (error) {
    $("#message").innerHTML =
      `<p class="notice error">${esc(error.message)}</p>`;
  } finally {
    button.disabled = false;
  }
});
$(".skip").addEventListener("click", (event) => {
  event.preventDefault();
  $("#main").focus();
});
window.addEventListener("hashchange", () => render());
for (const selector of ["#start", "#end"])
  $(selector).addEventListener("change", () => render());
render();
