# Context: OpenMeteo Additional Metrics

## Status
- **Workflow:** `openmeteo-additional-metrics`
- **Phase:** `phase3_spec` (Spec geschrieben, wartet auf Approval)
- **Spec:** `docs/specs/modules/openmeteo_additional_metrics.md`

## Zusammenfassung

4 OpenMeteo-Parameter werden nicht genutzt, obwohl sie verfuegbar sind:

| Metrik | OpenMeteo Param | DP-Feld (existiert!) | Kategorie |
|--------|----------------|---------------------|-----------|
| Sichtweite | `visibility` | `visibility_m` | atmosphere |
| Regenwahrscheinlichkeit | `precipitation_probability` | `pop_pct` | precipitation |
| Gewitterenergie (CAPE) | `cape` | `cape_jkg` | precipitation |
| Nullgradgrenze | `freezing_level_height` | `freezing_level_m` | winter |

## Was zu tun ist

### 2 Dateien aendern (~55 LoC):

1. **`src/providers/openmeteo.py`** (~15 LoC):
   - HOURLY_PARAMS um 4 Parameter erweitern (Zeile 353-368)
   - `_parse_response()`: 4x `None` durch `get_val()` ersetzen (Zeilen 295, 296, 311, 313)

2. **`src/app/metric_catalog.py`** (~40 LoC):
   - 4 neue MetricDefinition-Eintraege nach `pressure` einfuegen
   - Alle `default_enabled=False`

### KEINE Aenderungen noetig:
- `models.py` - Felder existieren bereits
- `trip_report.py` - Formatter ist kataloggesteuert
- `weather_config.py` - Dialog liest aus MetricCatalog

## Vorheriger Workflow: weather-config-api-ui

Phase 2 (API-Aware UI) ist implementiert aber noch NICHT committed:
- weather_config.py komplett umgeschrieben (MetricCatalog, Kategorien, Provider-Detection, Aggregation-Dropdowns)
- Bugfix: Trip wird beim Dialog-Oeffnen frisch von Disk geladen
- 11/11 TDD-Tests GREEN

## Aktualisierte Specs

- `docs/specs/modules/weather_config.md` v2.2 - Metrik-Tabelle auf 19 Metriken erweitert
- `docs/specs/modules/openmeteo_additional_metrics.md` v1.0 - Neue Spec fuer dieses Feature

## Naechste Schritte nach /clean

1. User sagt "approved" -> Workflow geht zu phase4_approved
2. `/4-tdd-red` -> Tests anpassen (15 -> 19 Checkboxes) + Provider-Tests
3. `/5-implement` -> Die ~55 LoC implementieren
4. `/6-validate` -> Validieren
5. Beide Features (weather-config-api-ui + additional-metrics) committen
