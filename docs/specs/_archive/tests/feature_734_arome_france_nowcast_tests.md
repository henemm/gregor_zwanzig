---
entity_id: feature_734_arome_france_nowcast_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
spec: docs/specs/modules/radar_nowcast_france.md
issue: 734
---

# Test-Manifest — Feature #734: AROME-HD-Routing für Frankreich

Mock-freie Tests. Reale Open-Meteo-API-Calls für die AROME-Pfade; deterministische
Tests mit echten `RadarFrame`/`NowcastResult`-Objekten für Bbox-/Label-/Konvektions-Logik.

Testdatei: `tests/tdd/test_feature_734_arome_france_nowcast.py`

## AC-1 — AROME wird wirklich genutzt (echter Fetch)

- `test_ac1_arome_france_real_fetch_returns_arome_source`
  Echter HTTP-Call: Korsika-Koordinate → `RadarNowcastService.get_nowcast` liefert
  `source == "AROME-FR"` und ≥1 reale Frame mit mm/h ≥ 0 (nicht der globale Fallback).

## AC-2 — Korrektes Routing pro Region (deterministisch)

- `test_ac2_within_arome_france_bbox`
  `_within_arome_france`: Korsika/Paris/Pyrenäen = True, Nord-Atlantik = False.
- `test_ac2_chain_routing_berlin_radar_atlantic_global`
  Ketten-Reihenfolge: Berlin → `source == "radar"` (RADOLAN-Vorrang), Atlantik → `source == "minutely_15"`.

## AC-3 — Transparente Quellen-Angabe (Pure-Function)

- `test_ac3_format_now_text_transparent_source_labels`
  `format_now_text` nennt bei `AROME-FR` „Météo-France"/„AROME"; beim Fallback „Open-Meteo (global)".

## AC-4 — Gewitter-Signal aus AROME

- `test_ac4_arome_convective_weathercode_drives_intensity`
  Reale `RadarFrame`-Objekte mit konvektivem WMO-Code → `is_convective == True`,
  `intensity_to_text` = „Starker Hagel/Gewitter". Kein Mock.
- `test_ac4_arome_real_fetch_has_weather_code`
  Echter Fetch gegen AROME-Koordinate belegt die Parse-Struktur (`weather_code` vorhanden, Frames numerisch).
