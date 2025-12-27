---
entity_id: provider_met
type: module
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [provider, weather, met-norway]
---

# Provider: MET Norway

## Approval

- [ ] Approved

## Purpose

Adapter fuer MET Norway Locationforecast API. Holt Wetterdaten und normalisiert sie in das interne DTO-Format.

## Source

- **File:** `src/providers/met.py` (geplant)
- **Identifier:** `class METProvider`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| NormalizedTimeseries | dto | Ausgabeformat |
| requests/httpx | lib | HTTP-Client |

## Implementation Details

```
API: Locationforecast 2.0 /compact

Mapping:
- air_temperature -> t2m_c
- wind_speed (m/s) x3.6 -> wind10m_kmh
- wind_speed_of_gust (m/s) x3.6 -> gust_kmh
- cloud_area_fraction -> cloud_total_pct
- precipitation_amount -> precip_1h_mm
- summary.symbol_code -> symbol

Thunder-Logik:
- symbol_code enthaelt "thunder" -> HIGH
- sonst NONE
```

## Expected Behavior

- **Input:** coords (lat, lon), start, end
- **Output:** NormalizedTimeseries
- **Side effects:** HTTP-Request an MET API

## Known Limitations

- Standard-Provider (verwendet wenn MOSMIX nicht qualifiziert)
- Benoetigt gueltige User-Agent Header

## Changelog

- 2025-12-27: Initial spec created (planned module)
