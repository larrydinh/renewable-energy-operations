/** Pure transformations shared by the browser and Node tests. */
export const SOURCES = [
  { id: "wind_onshore", name: "Onshore wind", color: "#237647" },
  { id: "wind_offshore", name: "Offshore wind", color: "#86b797" },
  { id: "photovoltaics", name: "Solar", color: "#f1ca50" },
  { id: "biomass", name: "Biomass", color: "#285a7e" },
  { id: "hydropower", name: "Hydropower", color: "#82b5d2" },
  { id: "other_renewable", name: "Other", color: "#b7c1bc" },
];
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export const nextDay = (iso, days = 1) =>
  new Date(Date.parse(iso + "T00:00:00Z") + days * 86400000)
    .toISOString()
    .slice(0, 10);
export function berlinDate(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const values = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${values.year}-${values.month}-${values.day}`;
}
export function berlinMidnight(iso) {
  const target = Date.parse(iso + "T00:00:00Z");
  let instant = target;
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let i = 0; i < 3; i++) {
    const p = Object.fromEntries(
      formatter.formatToParts(new Date(instant)).map((v) => [v.type, v.value]),
    );
    instant +=
      target -
      Date.UTC(
        Number(p.year),
        Number(p.month) - 1,
        Number(p.day),
        Number(p.hour),
        Number(p.minute),
        Number(p.second),
      );
  }
  return instant;
}
export function coverage(rows) {
  const expected = rows.reduce((sum, r) => sum + r.expected_intervals, 0);
  const observed = rows.reduce((sum, r) => sum + r.observed_intervals, 0);
  return {
    expected,
    observed,
    missing: expected - observed,
    percent: expected ? (100 * observed) / expected : 0,
  };
}
export function summarySeries(rows, sources) {
  const keys = [...new Set(rows.map((r) => r.bucket_start))].sort();
  const lookup = new Map(rows.map((r) => [r.source + "|" + r.bucket_start, r]));
  return {
    keys,
    labels: keys,
    unit: "GWh",
    series: sources.map((source) => ({
      ...source,
      values: keys.map((key) => {
        const row = lookup.get(source.id + "|" + key);
        return row?.observed_energy_mwh == null
          ? null
          : Number(row.observed_energy_mwh) / 1000;
      }),
    })),
    complete: rows.every((row) => row.is_complete),
  };
}
export function intervalSeries(responses, start, end) {
  const from = berlinMidnight(start),
    to = berlinMidnight(nextDay(end));
  const keys = [];
  for (let t = from; t < to; t += 900000) keys.push(t);
  return {
    keys,
    labels: keys.map((t) => new Date(t).toISOString()),
    unit: "MW",
    series: SOURCES.map((source, i) => {
      const lookup = new Map(
        responses[i].data.map((row) => [
          Date.parse(row.interval_start_utc),
          row.energy_mwh,
        ]),
      );
      return {
        ...source,
        values: keys.map((t) =>
          lookup.get(t) == null ? null : Number(lookup.get(t)) * 4,
        ),
      };
    }),
  };
}
export function stackable(data) {
  return (
    data.complete !== false &&
    data.series.every((s) =>
      s.values.every((v) => v !== null && Number.isFinite(v) && v >= 0),
    )
  );
}
export function csv(rows, columns) {
  const quote = (value) =>
    '"' + String(value ?? "").replaceAll('"', '""') + '"';
  return (
    "\uFEFF" +
    [
      columns.map(quote).join(","),
      ...rows.map((row) => columns.map((key) => quote(row[key])).join(",")),
    ].join("\r\n")
  );
}
