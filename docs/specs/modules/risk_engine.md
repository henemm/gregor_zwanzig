---
entity_id: risk_engine
type: module
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [risk, weather, logic]
---

# Risk Engine

## Approval

- [ ] Approved

## Purpose

Bewertet normalisierte Wetterdaten anhand konfigurierbarer Schwellenwerte und identifiziert Risiken.

## Source

- **File:** `src/engine/risk.py` (geplant)
- **Identifier:** `class RiskEngine`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| NormalizedTimeseries | dto | Input-Daten |

## Implementation Details

```
Risiko-Typen:
- thunderstorm (NONE/MED/HIGH)
- wind (moderate/high)
- rain (moderate/heavy)
- heat (warning/extreme)

Output-Format:
{
  "risks": [
    {"type": "thunderstorm", "level": "high", "from": "14:00Z"},
    {"type": "wind", "level": "moderate", "gust_kmh": 48, "from": "16:00Z"}
  ]
}

Schwellen (konfigurierbar):
- max_wind_kmh
- thunder_level
- rain_threshold_mm
- heat_threshold_c
```

## Expected Behavior

- **Input:** List[NormalizedTimeseries], Konfiguration
- **Output:** RiskAssessment mit Liste von Risiken
- **Side effects:** Keine

## Known Limitations

- Keine eigene meteorologische Modellierung
- Regelbasiert, kein ML

## Changelog

- 2025-12-27: Initial spec created (planned module)
