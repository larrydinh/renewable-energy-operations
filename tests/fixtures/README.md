# SMARD parser fixture

Source: **Bundesnetzagentur | SMARD.de**, German actual generation, 1 January 2024,
00:00–00:45 local time. Original export:
`Actual_generation_202401010000_202501010000_Quarterhour.csv`.

Data: [SMARD download centre](https://www.smard.de/en/downloadcenter/download-market-data),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

This is a **modified test sample, not an authoritative data extract**. It keeps
the two timestamp columns, six renewable columns and pumped storage. In the second
row, hydropower was changed to `-` and photovoltaics to `0.00`. In the third row,
all six renewable measurements were changed to `-`. Other included values retain
the source values. These changes exercise missing, zero and partial-coverage cases.

The sample has no BOM; generated test inputs also exercise UTF-8 with BOM.
