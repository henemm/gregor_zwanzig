---
entity_id: radar_nowcast
type: module
created: 2026-06-07
updated: 2026-06-08
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, radar]
---

# Radar-Nowcasting (Issue #656)

## Approval

- [x] Approved

## Purpose

Liefert hochpräzise Kurzfrist-Niederschlagsinformationen ("Fängt es in den nächsten ~20 Minuten an zu regnen/gewittern?") als kompakten Text — sowohl auf Abruf (`### now` via Inbound-Kanal) als auch proaktiv (Radar-Alert bei herannahender Zelle). Übersetzt echte Kurzfrist-Daten (Open-Meteo `minutely_15` global, BrightSky/RADOLAN regional, GeoSphere INCA regional) in 2–3 Zeilen Text.

## Source

- **File:** `src/providers/brightsky.py` (neu), `src/services/radar_service.py` (neu), `src/services/trip_command_processor.py` (erweitert), `src/services/trip_alert.py` (erweitert)
- **Identifier:** `BrightSkyProvider`, `RadarNowcastService`, `TripCommandProcessor._show_now`, `TripAlertService.check_radar_alerts`
- **Schicht:** Python-Backend (`src/providers/`, `src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~400–550 (Provider + Service + Befehl + Alert-Anbindung + mock-freie Tests)
- **Files:** 4 produktiv + 2–3 Testdateien
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.openmeteo.OpenMeteoProvider` | provider | Globaler `minutely_15`-Nowcast (Basis, deckt GR20/Korsika) |
| `providers.geosphere.GeoSphereProvider.fetch_nowcast` | provider | INCA 15-min/1-km Nowcast (Österreich) — bereits vorhanden |
| `providers.brightsky.BrightSkyProvider` | provider | DWD-RADOLAN Radar (Deutschland + Grenzregionen) — neu |
| `app.trip.Trip.get_stage_for_date` | model | Aktuelle Etappe → repräsentative Position |
| `services.trip_command_processor` | service | `### now`-Befehlsregistrierung |
| `services.trip_alert.TripAlertService` | service | Proaktive Alert-Anbindung (Throttle/Ruhezeiten/Log) |

## Implementation Details

### Datenquellen-Wahl (Koordinaten-basiert, automatisch)
```
def select_nowcast_source(lat, lon):
    if within_radolan_coverage(lat, lon):   # DE-Bbox ~47.0–55.1 N, 5.8–15.1 E
        return "brightsky"                    # echtes Radar, höchste Präzision
    if within_inca_coverage(lat, lon):        # AT-Bbox ~46.3–49.1 N, 9.5–17.2 E
        return "geosphere_nowcast"
    return "openmeteo_minutely15"             # global, Fallback (deckt GR20/Korsika)
# Bei Fehler/leerer Antwort: nächste Quelle in der Kette versuchen.
```

### BrightSky Provider (`src/providers/brightsky.py`)
- Endpunkt `https://api.brightsky.dev/radar?lat=..&lon=..&format=plain` → Zeitreihe `precipitation_5` (0.01 mm pro 5 min) für aktuelle + ~2 h.
- Methode `fetch_radar(lat, lon) -> list[RadarFrame]` mit Zeitstempel + Niederschlagsrate (mm/h). Kein API-Key.
- Registriert sich via `register_provider("brightsky", BrightSkyProvider)`.

### RadarNowcastService (`src/services/radar_service.py`)
- `get_nowcast(lat, lon) -> NowcastResult{onset_minutes, intensity_label, source, frames, is_convective}`: holt Quelle, bestimmt Niederschlagsbeginn/-ende, übersetzt Intensität in Text.
- `intensity_to_text(mm_per_h, is_convective=False)`: Schwellen → "Kein Niederschlag" / "Leichter Regen" / "Mäßiger Regen" / "Starker Regen" / "Starker Hagel/Gewitter" (neu, bei konvektiven Frames). Die 5. Stufe basiert auf WMO-weather_code aus Open-Meteo `minutely_15` — siehe Issue #660 für Details.
- `format_now_text(result)`: 2–3 Zeilen, z. B. "Aktuell trocken. Regen ab ca. 14:40 (mäßig). Quelle: Radar."

### `### now` Befehl (`trip_command_processor.py`)
- `"now"` in `_VALID_COMMANDS`; Dispatch → `_show_now(trip, command_now)`.
- Position: `trip.get_stage_for_date(today)` → repräsentativer Waypoint (erster der Etappe); ohne heutige Etappe → klare Meldung.
- Ruft `RadarNowcastService.get_nowcast` + `format_now_text`; gibt `CommandResult` zurück (gleicher Kanal antwortet).

### Radar-Alert (`trip_alert.py`)
- `check_radar_alerts()` analog `check_all_trips`: nur Trips mit heutiger Etappe + aktivem Alerting.
- "Wachsam", wenn NWP-Regenrisiko der heutigen Etappe > 30 %; dann Nowcast-Quelle prüfen.
- Auslösung, wenn Niederschlag-Onset ≤ Schwelle (Default 20 min) am Positions-Punkt; respektiert bestehende Throttle/Ruhezeiten; schreibt `alert_log` (severity HIGH).

## Expected Behavior

- **Input:** Koordinaten (aus heutiger Etappe) bzw. `### now` Inbound-Nachricht; bei Alerts der Scheduler-Tick.
- **Output:** Textantwort (Ad-hoc) bzw. Alert-Mail/Telegram (proaktiv).
- **Side effects:** Throttle-/Alert-Log-Schreibvorgänge (nur Alert-Pfad); keine Trip-Mutation.

## Acceptance Criteria

- **AC-1:** Given eine reale Koordinate innerhalb der RADOLAN-Abdeckung (Deutschland) / When der BrightSky-Provider `fetch_radar(lat, lon)` aufruft / Then liefert er eine nicht-leere Zeitreihe echter Radar-Frames mit Zeitstempel und Niederschlagsrate (mm/h ≥ 0) für die nächsten Minuten.
  - Test: Echter HTTP-Call gegen `api.brightsky.dev/radar` mit fester DE-Koordinate; assert ≥ 1 Frame, Zeitstempel monoton, Raten numerisch ≥ 0. Kein Mock.

- **AC-2:** Given Niederschlagsraten und optional Konvektions-Indikatoren aus einer Nowcast-Quelle / When `RadarNowcastService.intensity_to_text` und `format_now_text` sie übersetzen / Then entsteht ein deterministischer deutscher Text, der die korrekte Intensitätsstufe ("Kein Niederschlag"…"Starker Hagel/Gewitter") und — falls Niederschlag bevorsteht — den ungefähren Beginn nennt.
  - Test: Pure-Function-Test mit realen Beispielraten (0.0, 0.3, 2.5, 8.0 mm/h) → erwartete Stufen-Strings; bei Onset-Reihe erwartete Beginn-Zeit im Text. Deterministisch, kein Netz, kein Dateiinhalt-Check.

- **AC-3:** Given ein Trip mit heutiger Etappe und eine Inbound-Nachricht mit Body `### now` / When `TripCommandProcessor.process` sie verarbeitet / Then liefert sie in unter 10 Sekunden ein erfolgreiches `CommandResult`, dessen Body die Nowcast-Aussage für die Etappen-Position enthält (inkl. Quellen-Angabe).
  - Test: Echter End-to-End-Aufruf von `process(InboundMessage(body="### now", ...))` mit realem Trip + echter Nowcast-API; assert `success`, Laufzeit < 10 s gemessen, Body enthält die Intensitäts-/Quellen-Aussage. Kein Mock der API.

- **AC-4:** Given ein Trip mit heutiger Etappe, aktivem Alerting und einer Nowcast-Quelle, die einen Niederschlag-Onset innerhalb der Alert-Schwelle (≤ 20 min) am Positions-Punkt meldet / When `TripAlertService.check_radar_alerts` läuft / Then wird genau ein Radar-Alert versendet, ein `alert_log`-Eintrag (severity HIGH) geschrieben und ein erneuter Lauf innerhalb des Throttle-Fensters sendet keinen weiteren Alert.
  - Test: Echter Lauf gegen einen Trip, dessen Positions-Nowcast einen Onset liefert (reale API an einer aktuell regnerischen Test-Koordinate ODER injizierte reale Frames über den Service, kein `Mock`); assert genau 1 Versand + alert_log-Eintrag, zweiter Lauf 0 Versand (Throttle). Versand-Empfänger = `gregor-test@henemm.com`.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_brightsky_fetch_radar_returns_real_frames` |
| AC-2 | `test_ac2_intensity_to_text_levels`, `test_ac2_format_now_text_mentions_onset_and_source`, `test_ac2_format_now_text_dry` |
| AC-3 | `test_ac3_now_command_returns_nowcast_under_10s`, `test_ac3_now_command_without_today_stage_gives_clear_message` |
| AC-4 | `test_ac4_radar_alert_due_pure_logic`, `test_ac4_check_radar_alerts_sends_once_then_throttles` |

Testdatei: `tests/tdd/test_feature_656_radar_nowcast.py` (mock-frei).

## Known Limitations

- "Aktuelle Position" = repräsentativer Punkt der heutigen Etappe, kein Live-GPS.
- "Kollisionskurs" im MVP = Onset-/Annäherungs-Trend im Punkt-Nowcast, kein voll-physikalisches Zell-Tracking mit Bewegungsvektor.
- RADOLAN deckt nur DE + Grenzregionen, INCA nur AT. Für Italien (inkl. Korsika, PO-Entscheidung 2026-07-09) liefert seit Issue #1162 Radar-DPC (Protezione Civile) reale Radarbeobachtung statt Modell-Downscaling. Fällt Radar-DPC aus, greift seit Issue #1186 als Modell-Rückfall ARPAE ICON-2I (2 km, Open-Meteo) — noch innerhalb derselben Italien-Domäne, bevor die Kette weiter auf AROME-FR/ICON-D2 (siehe `radar_nowcast_france.md`/`radar_nowcast_icon_d2.md`) bzw. zuletzt `minutely_15` zurückfällt. Konvektions-Indikator (WMO-weather_code) ist in Open-Meteo verfügbar; BrightSky/GeoSphere/DPC-Pfade haben kein natives Konvektions-Feld und nutzen einen Open-Meteo-Sidecar (ADR-0018) — ARPAE führt weather_code bereits mit, kein Sidecar nötig.
- Latenz-AC (< 10 s) abhängig von Fremd-API-Verfügbarkeit; Fallback-Kette bei Timeout/Leerantwort.
- WMO-Codes sind eine Modell-Klassifikation, kein Live-Blitz-Detektor; Genauigkeit hängt vom Open-Meteo-Modell ab.

## Changelog

- 2026-06-07: Initial spec created (Issue #656)
- 2026-06-08: Known Limitation "Gewitter/Hagel-Stufe" aufgelöst durch Issue #660 (WMO-weather_code Konvektions-Indikator integriert); AC-2 angepasst
- 2026-07-09: Known Limitation zur regionalen Abdeckung korrigiert — Italien (inkl. Korsika) fällt seit Issue #1162 (Radar-DPC/Protezione Civile) nicht mehr auf den globalen `minutely_15`-Fallback zurück, siehe `docs/specs/_archive/modules/issue_1162_radar_dpc.md`
- 2026-07-09: ARPAE-ICON-2I-Modell-Rückfall unter Radar-DPC ergänzt (Issue #1186) — vervollständigt die Zwei-Ebenen-Absicherung für Italien (echtes Radar primär, regionales Modell als Netz), siehe `docs/specs/modules/radar_nowcast_italy_arpae_fallback.md`
