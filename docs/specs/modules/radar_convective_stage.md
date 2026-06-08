---
entity_id: radar_convective_stage
type: module
created: 2026-06-07
updated: 2026-06-08
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, radar, convective]
---

# Radar-Nowcast: Gewitter/Hagel-Stufe (Issue #660)

## Approval

- [x] Approved

## Purpose

Erweitert den Radar-Nowcast (#656) um eine 5. Intensitätsstufe „Starker Hagel/Gewitter", die nicht aus der Regenrate (mm/h) ableitbar ist, sondern aus einem Konvektions-Indikator der Datenquelle stammt. Quelle ist Open-Meteos `weather_code` (WMO 95/96/99) im bereits genutzten `minutely_15`-Pfad — global, deckt die Sicherheits-Zielgruppe (GR20/Korsika). Löst die in `radar_nowcast.md` dokumentierte Known Limitation auf.

## Source

- **File:** `src/providers/brightsky.py` (RadarFrame erweitert), `src/services/radar_service.py` (erweitert), `src/services/trip_alert.py` (Alert-Kennzeichnung)
- **Identifier:** `RadarFrame.is_convective`, `RadarNowcastService.intensity_to_text`, `RadarNowcastService._derive_result`, `RadarNowcastService._fetch_openmeteo_minutely15`, `NowcastResult.is_convective`, `TripAlertService.check_radar_alerts`
- **Schicht:** Python-Backend (`src/providers/`, `src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~80–120 (Flag in RadarFrame + Open-Meteo-Parsing + intensity_to_text-Eskalation + NowcastResult-Flag + Alert-Label + mock-freie Tests)
- **Files:** 3 produktiv + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.openmeteo` / Open-Meteo `minutely_15` | provider | Liefert `weather_code` (WMO) als globalen Konvektions-Indikator |
| `providers.brightsky.RadarFrame` | model | Trägt neu das `is_convective`-Flag |
| `services.radar_service.RadarNowcastService` | service | Übersetzt Frames → Stufe/Text/Alert |
| `services.trip_alert.TripAlertService.check_radar_alerts` | service | Proaktiver Alert, kennzeichnet Gewitter als höchste Priorität |

## Implementation Details

### Konvektions-Indikator (Quelle)
- **Primär: Open-Meteo `minutely_15=precipitation,weather_code`** (global, gleicher Endpunkt wie heute). Frame gilt als konvektiv, wenn `weather_code ∈ {95, 96, 99}` (WMO: 95 Gewitter, 96 Gewitter mit leichtem Hagel, 99 Gewitter mit starkem Hagel).
- **BrightSky `plain`:** kein Konvektions-Feld → `is_convective` bleibt `False` (4-Stufen-Fallback, keine Falsch-Eskalation).
- **GeoSphere INCA:** `pt`-Codes 0–4 enthalten keinen Gewitter-Typ → `is_convective` bleibt `False`.

### `RadarFrame` (`src/providers/brightsky.py`)
- Neues additives Feld `is_convective: bool = False` (Default → bestehende Pfade bit-identisch).

### `RadarNowcastService` (`src/services/radar_service.py`)
- `_fetch_openmeteo_minutely15`: zusätzlich `weather_code` abfragen; pro Frame `is_convective = (code in {95, 96, 99})`.
- `intensity_to_text(mm_per_h, is_convective=False)`: bei `is_convective=True` → `"Starker Hagel/Gewitter"` (schlägt jede rate-basierte Stufe, auch bei niedriger mm/h). Sonst unverändertes 4-Stufen-Verhalten.
- `_derive_result`: `is_convective = any(f.is_convective for f in window-frames mit precip ≥ threshold)`; `intensity_label = self.intensity_to_text(max_rate, is_convective)`. `NowcastResult` erhält additives Feld `is_convective: bool = False`.
- `format_now_text`: nutzt bereits `intensity_label` → zeigt automatisch „Starker Hagel/Gewitter".

### Radar-Alert (`src/services/trip_alert.py`)
- `check_radar_alerts`: bei `result.is_convective` Subject/Body kennzeichnen (z. B. Subject-Präfix „⚠️ Gewitter"), severity bleibt HIGH (bereits höchste Stufe).

## Expected Behavior

- **Input:** Koordinaten (heutige Etappe) für `### now` bzw. Alert-Tick; Open-Meteo liefert `weather_code`.
- **Output:** Bei Konvektion Stufe „Starker Hagel/Gewitter" in Ad-hoc-Antwort und proaktivem Alert (als höchste Priorität gekennzeichnet).
- **Side effects:** Keine zusätzlichen über #656 hinaus (Throttle/alert_log unverändert).

## Acceptance Criteria

- **AC-1:** Given Frames mit gesetztem Konvektions-Flag / When `RadarNowcastService.intensity_to_text(mm_per_h, is_convective=True)` aufgerufen wird / Then liefert sie deterministisch `"Starker Hagel/Gewitter"` — unabhängig von `mm_per_h` (auch bei niedriger Rate), und bei `is_convective=False` bleibt das bisherige 4-Stufen-Verhalten exakt erhalten.
  - Test: Pure-Function-Test mit (0.2, True), (8.0, True) → „Starker Hagel/Gewitter"; (0.0/0.3/2.5/8.0, False) → bisherige Stufen-Strings. Deterministisch, kein Netz, kein Dateiinhalt-Check.

- **AC-2:** Given eine reale Open-Meteo-`minutely_15`-Antwort / When `_fetch_openmeteo_minutely15(lat, lon)` läuft / Then enthält jeder zurückgegebene `RadarFrame` das `is_convective`-Flag, das genau dann `True` ist, wenn der zugehörige `weather_code` in {95, 96, 99} liegt — verifiziert gegen echte API.
  - Test: Echter HTTP-Call gegen Open-Meteo `minutely_15=precipitation,weather_code` mit fester Koordinate; assert jeder Frame hat ein bool-`is_convective`; und ein deterministischer Mapping-Test (DI: reale WMO-Code-Reihe inkl. 95/96/99 durch den Service) beweist die korrekte Flag-Setzung. Kein Mock der Logik.

- **AC-3:** Given ein injizierter Frame-Satz (DI-Seam `frame_source`, reale Werte, kein Mock) mit mindestens einem konvektiven, nassen Frame im Nowcast-Fenster / When `get_nowcast` → `_derive_result` läuft / Then ist `NowcastResult.is_convective == True`, `intensity_label == "Starker Hagel/Gewitter"`, und `format_now_text` nennt diese Stufe im Text.
  - Test: `RadarNowcastService(frame_source=...)` mit echten RadarFrame-Objekten (eins konvektiv); assert Flag, Label und Text. Kein Netz, kein Mock.

- **AC-4:** Given ein Trip mit heutiger Etappe, aktivem Alerting und einem Nowcast-Ergebnis mit `is_convective=True` und Onset ≤ 20 min / When `TripAlertService.check_radar_alerts` läuft / Then wird genau ein Radar-Alert mit Gewitter-Kennzeichnung versendet (Subject/Body weisen die Gewitter-Lage aus), ein `alert_log`-Eintrag (severity HIGH) geschrieben, und ein zweiter Lauf innerhalb des Throttle-Fensters sendet keinen weiteren Alert.
  - Test: Echter Lauf gegen einen Trip, dessen Positions-Nowcast über injizierte reale konvektive Frames (DI, kein `Mock`) einen Onset liefert; assert genau 1 Versand + alert_log HIGH + Gewitter-Kennzeichnung im Subject/Body, zweiter Lauf 0 Versand (Throttle). Empfänger = `gregor-test@henemm.com`.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_intensity_convective_overrides_rate`, `test_ac1_intensity_non_convective_unchanged` |
| AC-2 | `test_ac2_openmeteo_frames_have_convective_flag`, `test_ac2_weathercode_maps_to_convective` |
| AC-3 | `test_ac3_derive_result_convective_label_and_text` |
| AC-4 | `test_ac4_radar_alert_convective_marked_once_then_throttles` |

Testdatei: `tests/tdd/test_feature_660_convective_stage.py` (mock-frei).

## Known Limitations

- Konvektions-Indikator nur über Open-Meteo-`weather_code` (global). BrightSky/GeoSphere-Pfade kennzeichnen keine Konvektion (kein passendes Quellfeld) → in DE/AT-Abdeckung kann eine Gewitter-Lage unbemerkt bleiben, solange der Radar/INCA-Pfad greift. Bewusster Scope: globale Abdeckung der Zielgruppe zuerst.
- WMO-Codes sind eine Modell-Klassifikation, kein Live-Blitz-Detektor; Genauigkeit hängt vom Open-Meteo-Modell ab.
- Keine Unterscheidung Hagel vs. reines Gewitter im Label (95/96/99 → eine gemeinsame Stufe).

## Changelog

- 2026-06-07: Initial spec created (Issue #660)
- 2026-06-08: Implementation complete; WMO-weather_code (95/96/99) integration in Open-Meteo `minutely_15`, `RadarFrame.is_convective` flag added, `intensity_to_text` escalation implemented, alert kennzeichnung (⚠️ Gewitter) aktiv
