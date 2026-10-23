import test from "node:test";
import assert from "node:assert/strict";
import {
  SOURCES,
  berlinMidnight,
  berlinDate,
  nextDay,
  coverage,
  summarySeries,
  intervalSeries,
  stackable,
  csv,
  esc,
} from "../../src/energy_ops/web/data.js";

test("German calendar boundaries contain 92/100 intervals across DST", () => {
  assert.equal(
    (berlinMidnight("2024-04-01") - berlinMidnight("2024-03-31")) / 900000,
    92,
  );
  assert.equal(
    (berlinMidnight("2024-10-28") - berlinMidnight("2024-10-27")) / 900000,
    100,
  );
  assert.equal(berlinDate("2024-01-01T23:30:00Z"), "2024-01-02");
  assert.equal(nextDay("2024-02-28"), "2024-02-29");
});
test("coverage counts missing measurements instead of treating them as zero", () => {
  assert.deepEqual(
    coverage([{ expected_intervals: 96, observed_intervals: 90 }]),
    { expected: 96, observed: 90, missing: 6, percent: 93.75 },
  );
  assert.equal(coverage([]).percent, 0);
});
test("summary values preserve missing versus zero and exclude incomplete stacks", () => {
  const data = summarySeries(
    [
      {
        source: "biomass",
        bucket_start: "2024-01-01",
        observed_energy_mwh: "0",
        is_complete: true,
      },
      {
        source: "biomass",
        bucket_start: "2024-01-02",
        observed_energy_mwh: null,
        is_complete: false,
      },
    ],
    [SOURCES[3]],
  );
  assert.deepEqual(data.series[0].values, [0, null]);
  assert.equal(stackable(data), false);
});
test("interval chart inserts absent slots, retains zeroes and converts MWh to MW", () => {
  const sources = SOURCES.map(() => ({
    data: [
      { interval_start_utc: "2023-12-31T23:00:00Z", energy_mwh: "0" },
      { interval_start_utc: "2023-12-31T23:15:00Z", energy_mwh: "12.5" },
      { interval_start_utc: "2023-12-31T23:30:00Z", energy_mwh: null },
    ],
  }));
  const data = intervalSeries(sources, "2024-01-01", "2024-01-01");
  assert.equal(data.keys.length, 96);
  assert.deepEqual(data.series[0].values.slice(0, 4), [0, 50, null, null]);
  assert.equal(stackable(data), false);
  const complete = { series: [{ values: [0, 1, 2] }] };
  assert.equal(stackable(complete), true);
  assert.equal(stackable({ series: [{ values: [-1, 0] }] }), false);
});
test("CSV preserves exact decimal strings and escapes delimiters", () => {
  const text = csv(
    [{ energy: "123456789.123456789", label: 'wind,"north"' }],
    ["energy", "label"],
  );
  assert.equal(
    text,
    '\uFEFF"energy","label"\r\n"123456789.123456789","wind,""north"""',
  );
  assert.equal(
    esc('<script>"x"</script>'),
    "&lt;script&gt;&quot;x&quot;&lt;/script&gt;",
  );
});
