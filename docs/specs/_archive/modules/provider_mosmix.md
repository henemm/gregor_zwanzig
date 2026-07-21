---
entity_id: provider_mosmix
type: module
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [provider, weather, dwd, mosmix]
---

# Provider: MOSMIX (DWD)

## Approval

- [ ] Approved

## Purpose

Adapter fuer DWD MOSMIX Open Data. Nur verwendet wenn Qualitaetskriterien erfuellt (siehe decision_matrix).

## Source

- **File:** `src/providers/mosmix.py` (geplant)
- **Identifier:** `class MOSMIXProvider`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| NormalizedTimeseries | dto | Ausgabeformat |
| decision_matrix | spec | Qualitaetskriterien |

## Implementation Details

```
Qualifizierungskriterien (Gate):
- Distanz <= 25 km
- |Delta H| <= 150 m
- Land/See-Flag: gleich

Mapping:
- TTT -> t2m_c
- FF (m/s) x3.6 -> wind10m_kmh
- FX/FX1 (m/s) x3.6 -> gust_kmh
- RR1c -> precip_1h_mm
- N -> cloud_total_pct
- ww -> symbol (via symbol_mapping)
- CAPE_* -> cape_jkg

Thunder-Logik:
- ww in {95,96,99} -> HIGH
- elif CAPE >= 800 -> MED
- else NONE
```

## Expected Behavior

- **Input:** coords (lat, lon), start, end
- **Output:** NormalizedTimeseries oder None (wenn nicht qualifiziert)
- **Side effects:** HTTP-Request an DWD Open Data

## Known Limitations

- Nur in DE/nahe DE sinnvoll
- Stationsbasiert, nicht flaechendeckend

## Changelog

- 2025-12-27: Initial spec created (planned module)
