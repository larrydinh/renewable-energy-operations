# SMARD actual-generation contract: initial specification

Status: based on inspection of four annual exports covering 2023–2026 on 22 October 2026. Parser implementation and fixtures are the next milestone. These rules describe those exports, not every possible SMARD download.

## Source format

- UTF-8 with BOM, semicolon delimiter.
- `Start date` and `End date`, for example `Jan 1, 2024 12:00 AM`.
- English decimal formatting: `1,459.75` means 1459.75.
- Missing marker `-`; never substitute zero.
- Six renewable headers: Biomass, Hydropower, Wind offshore, Wind onshore, Photovoltaics, Other renewable; each followed by ` [MWh] Original resolutions`.
- Source local timezone: Europe/Berlin; resolution: 15 elapsed minutes.
- MWh is interval energy. Do not multiply it by 0.25 again. Pumped storage is excluded from this renewable basket.

## Canonical representation

Store source identity, timezone-aware UTC start/end, decimal MWh or an explicit missing status, and original file/row provenance. Intervals are `[start, end)`. Original source strings remain recoverable.

## Clock changes

The inspected files contain repeated autumn start labels and two end-label discrepancies per year. For example, the 2024 spring row beginning 01:45 says it ends at 02:00, which is nonexistent locally that day; its actual elapsed end is 03:00 local time.

For a complete ordered export, require an explicit period, generate its UTC grid, and check every source start label and the full row count before assigning UTC identities. Derive the canonical end by adding 15 elapsed minutes. Preserve and report recognized end-label discrepancies.

Do not apply row-position assignment to shuffled, truncated or incomplete grids. Ambiguous partial inputs require offsets or independent evidence; otherwise reject them. Do not deduplicate on local labels. Expected local-day counts are 92, 96 or 100, calculated from timezone-aware midnight boundaries.

## Coverage

The 2026 export ends at the exclusive boundary 1 January 2027 but contains future missing slots. A filename does not establish observed coverage. Report latest observed and latest continuously complete periods separately; mark incomplete sums as observed subtotals.

## Required parser tests

1. English numbers, zeros, missing markers and malformed numeric text.
2. Header/unit mismatches and malformed rows.
3. Spring and autumn transitions, leap day and year boundaries.
4. Removed, duplicated and reordered rows.
5. UTC uniqueness and interval duration.
6. Source-row provenance and preserved raw labels.

Source: [Bundesnetzagentur | SMARD.de](https://www.smard.de/en/downloadcenter/download-market-data). Future fixtures must include attribution, the original source period and transformations performed.
