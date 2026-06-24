# Context: #873 — Schneehöhe/Schneefallgrenze als Display-Filter

## Betroffene Dateien
- `src/formatters/sms_trip.py`: SMS_SYMBOL_BY_METRIC ergänzen
- `src/output/tokens/builder.py`: _wintersport() Threshold-Filter
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`: UI-Zeilen

## Sonderfall SFL
Inverse Logik: SFL ≤ Schwellwert → anzeigen (niedrige Schneefallgrenze = relevanter).
