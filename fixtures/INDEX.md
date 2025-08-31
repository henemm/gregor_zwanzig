

# Fixtures Index – Gregor Zwanzig

This folder contains all static input/output fixtures used for testing.

---

## Analyzer
- `analyzer/input_series.json` → Sample input timeseries for analysis.
- `analyzer/expected_analysis.json` → Expected normalized analysis result.

## Providers
- `providers/met_sample.json` → Example response from MET Norway API.
- `providers/mosmix_sample.json` → Example response from DWD MOSMIX.
- `providers/nowcastmix_sample.json` → Example response from DWD NowcastMix.

## Renderer
- `renderer/expected_sms.txt` → Expected compact SMS output (token-based, ≤160 chars).
- `renderer/expected_email.html` → Expected email output, including token line, human-readable summary, tables, and debug block.

---

## Notes
- Fixtures are the **single source of truth** for renderer and analyzer tests.
- Any change in formats must update the corresponding fixture and tests together.