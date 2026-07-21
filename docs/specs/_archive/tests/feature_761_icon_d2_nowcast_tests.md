---
entity_id: feature_761_icon_d2_nowcast_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
spec: docs/specs/modules/radar_nowcast_icon_d2.md
issue: 761
---

# Test-Manifest — Feature #761: ICON-D2-Routing für Zentraleuropa/Alpen

Mock-freie Tests. Reale Open-Meteo-API-Calls (`models=icon_d2`) für ICON-D2-Pfade;
deterministische Tests mit echten `RadarFrame`/`NowcastResult`-Objekten für Bbox-/Label-/
Konvektions-Logik.

Testdatei: `tests/tdd/test_feature_761_icon_d2_nowcast.py`

## AC-1 — ICON-D2 wird wirklich genutzt (echter Fetch)

- `test_ac1_icon_d2_real_fetch_returns_icon_d2_source`
  Echter HTTP-Call: Dolomiten-Koordinate (außerhalb DE/AT/FR) → `get_nowcast` liefert
  `source == "ICON-D2"` und ≥1 reale Frame mit mm/h ≥ 0.

## AC-2 — Korrekte Routing-Priorität

- `test_ac2_within_icon_d2_bbox`
  `_within_icon_d2`: Dolomiten/Slowenien = True, Nord-Atlantik = False.
- `test_ac2_chain_routing_precedence`
  Berlin → `radar` (RADOLAN-Vorrang), Schweiz-West → `AROME-FR` (vor ICON-D2),
  Atlantik → `minutely_15`.

## AC-3 — All-None-Guard (rotiertes Gitter)

- `test_ac3_icon_d2_all_none_falls_through_to_global`
  Koordinate in der Bbox aber außerhalb des Gitters (Polen-Tatra, real all-None) →
  `_fetch_icon_d2(...) == []` UND `get_nowcast(...).source == "minutely_15"`.

## AC-4 — Transparenz + Gewitter

- `test_ac4_format_now_text_icon_d2_label`
  `format_now_text` mit `NowcastResult(source="ICON-D2")` nennt „DWD ICON-D2".
- `test_ac4_icon_d2_convective_drives_intensity`
  Reale `RadarFrame`-Objekte mit konvektivem WMO-Code → `is_convective == True`,
  `intensity_to_text` = „Starker Hagel/Gewitter". Kein Mock.
