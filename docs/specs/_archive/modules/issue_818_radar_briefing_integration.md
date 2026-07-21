---
entity_id: issue_818_radar_briefing_integration
type: feature
created: 2026-06-24
updated: 2026-06-24
status: draft
version: "1.0"
tags: [alert, radar, nowcast, briefing-snapshot, alert-state, throttle-migration, doppel-alert, epic-813, slice-3]
---

# Issue #818 — Radar-Nowcast-Briefing-Integration (Epic #813 Slice 3/3)

## Approval

- [ ] Approved

## Purpose

Integriert den Radar-Nowcast-Alert vollständig in den gemeinsamen Alert-Wächter aus Slice 1 und 2: Der Radar-Alert wird nur dann gesendet, wenn der Nowcast Regen ankündigt, den das letzte Briefing *nicht* vorhergesagt hat ("überraschender Regen"). Der separate Throttle-Speicher (`radar_alert_throttle.json`) wird in `alert_state` überführt, und ein Doppel-Alert-Schutz verhindert, dass Forecast-Abweichungs-Alert und Radar-Alert für denselben Regen gleichzeitig feuern.

## Source

- **File:** `src/services/trip_alert.py` — Hauptdatei: `check_radar_alerts()`, Throttle-Methoden, Doppel-Alert-Schutz
- **File:** `src/services/alert_state.py` — Erweiterte Nutzung für Radar-Throttle-Key
- **File:** `tests/tdd/test_issue_818_radar_briefing_integration.py` — Neue Tests (CREATE)
- **File:** `tests/tdd/test_issue_827_radar_throttle_recording.py` — Anpassung Throttle-Assertions (MODIFY)

> **Schicht: Python-Backend.** Alle produktiven Dateien liegen in `src/`.
> Go-API (`api/`, `internal/`) und Frontend (`frontend/`) bleiben vollständig unberührt.
> Briefing-Format, Mail-Renderer und UI bleiben unverändert.

## Estimated Scope

- **LoC:** ~170–210 netto (A: ~40 produktiv + 100–130 Tests; B: ~30 Throttle-Migration; D: ~15 Doppel-Alert-Guard)
- **Files:** 2 produktiv (MODIFY) + 2 Testdateien (1 CREATE, 1 MODIFY)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_snapshot.py` — `WeatherSnapshotService.load_dated(trip_id, date)` | upstream | Liefert heutigen Briefing-Snapshot als `List[SegmentWeatherData]` (read-only) |
| `src/services/alert_state.py` — `AlertStateService` | upstream | Speichert Radar-Throttle-Zeitstempel; prüft Doppel-Alert-Guard |
| `src/services/trip_segments.py` — `TripSegment.end_time` | upstream | UTC-Endzeit des Segments für den "nur kommende Segmente"-Filter (Slice 2, bereits implementiert) |
| `src/services/radar_service.py` — `NowcastResult` | upstream | Felder `onset_minutes`, `is_convective` für Briefing-Vergleich |
| `src/services/trip_report_scheduler.py` — `_reset_alert_state_after_briefing` | downstream | Löscht `alert_state`-Datei nach Briefing-Versand → Radar-Throttle wird automatisch mitgeresettet |
| Issue #816 (Slice 1) — `alert_state.py`, AlertStateService | prerequisite | Muss deployed sein (✅) |
| Issue #822 (Slice 2) — Segment-Helfer, Segment-Filter | prerequisite | Muss deployed sein (✅) |

## Implementation Details

### A — Nowcast-vs-Briefing-Vergleich (Hauptwert)

Neue Hilfsfunktion in `trip_alert.py`:

```
_briefing_precip_for_onset(snapshot, segment_id, onset_dt, tz) -> Optional[float]
```

Logik:
1. Snapshot laden: `WeatherSnapshotService(user_id).load_dated(trip.id, today)` → `List[SegmentWeatherData]` oder `None`
2. Passenden Segment-Eintrag via `segment_id` suchen
3. `onset_dt` (UTC-aware) auf die UTC-Stunde normieren: `onset_hour = onset_dt.replace(minute=0, second=0, microsecond=0)` als naive datetime (ohne tzinfo), da Snapshot-Timestamps naiv sind
4. `hourly[onset_hour].precip_1h_mm` aus dem passenden SegmentWeatherData-Eintrag lesen
5. Rückgabe: `float` (mm) oder `None` wenn Stunde nicht im Snapshot vorhanden

Entscheidungslogik in `check_radar_alerts()`:
- Briefing-Wert `>= 0.5 mm` → kein Alert (Regen war angekündigt, nicht überraschend)
- Briefing-Wert `< 0.5 mm` → Alert senden mit Text: `"Regen ab HH:MM, im Briefing für HH:00 Uhr nicht angekündigt"`
- Snapshot nicht vorhanden (`load_dated` → `None`) → Alert trotzdem senden (Fallback, bisheriges Verhalten)

Bagatellschwelle 0.5 mm ist fest kodiert (nicht konfigurierbar in Slice 3).

### B — Radar-Throttle-Migration → alert_state

Bestehende Methoden/Felder die entfernt werden:
- `_radar_throttle_times` (In-Memory-Dict in `TripAlertService`)
- `_load_radar_throttle()`
- `_save_radar_throttle()`

Neues Key-Schema in `alert_state/<trip_id>.json`:
```
"radar_throttle": {"reported_at": "<ISO-8601>"}
```
Kein `last_reported_value` (Radar-Throttle braucht kein Wert-Delta, nur einen Zeitstempel).

Cooldown-Prüfung: `reported_at` aus `alert_state.get("radar_throttle")` gegen `now - cooldown_min`.

Lazy Migration: Beim ersten Zugriff nach Deploy prüfen ob `radar_alert_throttle.json` vorhanden ist. Falls ja: `reported_at` daraus lesen als Fallback, in `alert_state` schreiben, alte Datei stehen lassen (wird im nächsten Lauf ignoriert). Nach einem Release-Zyklus kann die alte Datei entfernt werden.

`_reset_alert_state_after_briefing()` löscht bereits die komplette `alert_state`-Datei → Radar-Throttle wird automatisch nach jedem Briefing mitgeresettet, ohne zusätzlichen Code.

### C — "Nur kommende Segmente"-Filter (Nachweis)

Bereits implementiert in `check_radar_alerts()` Z. 616–631 (Slice 2, Issue #822). Kein neuer Code nötig. Nur ein Nachweis-Test schreiben der das Verhalten als guard-Charakter sichert.

### D — Doppel-Alert-Schutz

Problem: Forecast-Abweichungs-Alert (aus `check_all_trips`, läuft alle 30 Min) und Radar-Alert (läuft alle 15 Min) können für denselben Regen gleichzeitig feuern.

Guard-Logik in `check_radar_alerts()` vor dem Alert-Versand:
1. `alert_state` des aktiven Segments laden
2. Keys `"thunder_level_max:<segment_id>"` und `"precip:<segment_id>"` prüfen
3. Wenn `reported_at` innerhalb `cooldown_min` von `now` → Radar-Alert unterdrücken (Forecast-Alert war aktuell/umfassender)
4. Wenn kein aktueller Forecast-Alert-Eintrag → Radar-Alert normal senden

## Expected Behavior

- **Input:** `check_radar_alerts()` auf `TripAlertService(user_id=X)` — iteriert alle aktiven Trips.
- **Output:**
  - Kein Alert wenn: Segment bereits abgelaufen, kein Nowcast-Onset, Briefing hatte Regen angekündigt (`>= 0.5 mm`), Radar-Throttle aktiv, oder Forecast-Alert wurde kürzlich für dasselbe Segment gesendet.
  - Alert mit Onset-Text "Regen ab HH:MM, im Briefing für HH:00 Uhr nicht angekündigt" wenn: Nowcast sagt Onset UND Briefing-Snapshot hat `< 0.5 mm` für diese Stunde (oder Snapshot fehlt) UND kein aktueller Doppel-Alert-Guard.
- **Side effects:**
  - `data/users/<user_id>/alert_state/<trip_id>.json` — `"radar_throttle"` wird nach Alert geschrieben.
  - `data/users/<user_id>/radar_alert_throttle.json` — Read-Fallback für einen Release-Zyklus; wird nicht mehr geschrieben.
  - `data/users/<user_id>/alert_log.json` — Eintrag bei Versand (unverändert).

## Acceptance Criteria

- **AC-1:** Given ein Nowcast sagt Regen-Onset in 10 Minuten für das aktive Segment und der Briefing-Snapshot für diese UTC-Stunde enthält `precip_1h_mm >= 0.5` / When `check_radar_alerts()` läuft / Then wird kein Radar-Alert gesendet (Regen war im Briefing angekündigt, nicht überraschend). Test: Briefing-Snapshot mit `precip_1h_mm = 1.2` für die aktuelle Stunde in `data/users/tdd-818-ac1/` ablegen; NowcastResult mit `onset_minutes = 10` via DI-Seam injizieren; nach Lauf kein Alert-Log-Eintrag und kein `alert_state["radar_throttle"]`-Eintrag. Kein Mock.

- **AC-2:** Given ein Nowcast sagt Regen-Onset in 10 Minuten für das aktive Segment und der Briefing-Snapshot für diese UTC-Stunde enthält `precip_1h_mm = 0.0` (Regen nicht angekündigt) / When `check_radar_alerts()` läuft / Then wird ein Radar-Alert gesendet mit Text der "im Briefing nicht angekündigt" enthält, und `alert_state["radar_throttle"]["reported_at"]` wird gesetzt. Test: Snapshot mit `precip_1h_mm = 0.0` ablegen, NowcastResult via DI-Seam; nach Lauf `alert_state`-Datei laden und `radar_throttle.reported_at` prüfen (echte Persistenz). Kein Mock.

- **AC-3:** Given kein Briefing-Snapshot für heute vorhanden (`WeatherSnapshotService.load_dated` gibt `None` zurück) und Nowcast sagt Regen-Onset / When `check_radar_alerts()` läuft / Then wird ein Radar-Alert gesendet (Fallback: kein Snapshot = kein Unterdrücken). Test: `data/users/tdd-818-ac3/` ohne Snapshot-Datei, NowcastResult mit Onset via DI-Seam; Alert-Log-Eintrag oder `radar_throttle`-Eintrag nachweisbar. Kein Mock.

- **AC-4:** Given ein Forecast-Abweichungs-Alert für `"precip:<segment_id>"` wurde vor 30 Minuten gesendet und steht im `alert_state` mit `reported_at` innerhalb des Cooldown-Fensters / When `check_radar_alerts()` für dasselbe Segment läuft / Then wird kein Radar-Alert gesendet (Doppel-Alert-Schutz aktiv). Test: `alert_state`-Datei mit Eintrag `"precip:<segment_id>": {"reported_at": "<jetzt - 30 min>"}` anlegen, Cooldown = 120 Min; NowcastResult mit Onset; nach Lauf kein neuer `radar_throttle`-Eintrag und kein Alert. Kein Mock.

- **AC-5:** Given alle Segmente des heutigen Trips haben `end_time < now_utc` (Etappe bereits abgelaufen) / When `check_radar_alerts()` läuft / Then wird kein Radar-Alert gesendet (Segment-Filter greift). Test: Trip mit einem Segment, dessen `end_time = jetzt - 1h`; NowcastResult mit Onset; nach Lauf kein Alert-Log-Eintrag, kein `radar_throttle`-Eintrag. Nachweis-Test für bereits implementierten Filter. Kein Mock.

- **AC-6:** Given ein Radar-Alert wurde gesendet und `alert_state["radar_throttle"]["reported_at"]` ist gesetzt / When `check_radar_alerts()` innerhalb des Cooldown-Fensters erneut läuft / Then wird kein zweiter Alert gesendet (Throttle via alert_state aktiv). Test: ersten Lauf mit Onset und Snapshot `< 0.5 mm` → Alert + Throttle-Eintrag; sofortiger zweiter Lauf mit identischen Bedingungen → kein zweiter Alert-Log-Eintrag. Echter Datei-Zustand, kein Mock.

- **AC-7:** Given zwei Nutzer (`tdd-818-ac7a`, `tdd-818-ac7b`) mit je eigenem Trip, Snapshot und alert_state / When `check_radar_alerts()` für `tdd-818-ac7a` einen Alert auslöst / Then bleibt `data/users/tdd-818-ac7b/` vollständig unberührt (kein Alert, kein radar_throttle-Eintrag). Test: zwei `TripAlertService`-Instanzen mit separaten user_ids; nach Lauf unter `ac7a` Timestamp-Vergleich aller Dateien unter `ac7b`. Kein Mock.

## Known Limitations

- Bagatellschwelle 0.5 mm für den Briefing-Vergleich ist in Slice 3 fest kodiert und nicht pro-Nutzer konfigurierbar. Konfigurierbarkeit ist kein Scope dieses Slices.
- Alte `radar_alert_throttle.json`-Dateien werden für einen Release-Zyklus als Read-Fallback gelesen, aber nicht mehr geschrieben. Automatische Bereinigung ist kein Scope dieses Slices.
- Doppel-Alert-Schutz prüft nur `"thunder_level_max:<seg_id>"` und `"precip:<seg_id>"`-Keys. Andere Forecast-Alert-Metriken (Temp, Wind) lösen keinen Guard aus.
- SMS-Kanal nicht im Scope (nur E-Mail und Telegram).
- Kein dedizierter `radar_alert_validator.py` (analog `briefing_mail_validator.py`). Mail-Verifikation erfolgt über DI-Seam + alert_state-Datei-Inspektion in den TDD-Tests.
- `is_convective`-Feld aus `NowcastResult` wird in dieser Spec nicht für eine separate Entscheidungslogik genutzt — die Briefing-Vergleichs-Logik gilt für Regen und Gewitter gleichermaßen.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` | MODIFY | `check_radar_alerts()`: Briefing-Lookup + Doppel-Alert-Guard; `_load_radar_throttle()`/`_save_radar_throttle()`/`_radar_throttle_times` entfernen; Throttle-Logik auf AlertStateService umstellen |
| `src/services/alert_state.py` | MODIFY | Additiv: Radar-Throttle-Key `"radar_throttle"` ohne `last_reported_value` lesen/schreiben (Schema-Erweiterung rückwärtskompatibel) |
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | CREATE | 7 mock-freie Tests für AC-1 bis AC-7 |
| `tests/tdd/test_issue_827_radar_throttle_recording.py` | MODIFY | Throttle-Assertions auf alert_state-Key umstellen statt `radar_alert_throttle.json` |

### Estimated Changes

- Files: 4
- LoC: +170/−30 (netto; alte Throttle-Methoden werden entfernt)

## AC-Test-Mapping

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_briefing_announced_rain_suppresses_radar_alert` |
| AC-2 | `test_ac2_unannounced_rain_triggers_radar_alert` |
| AC-3 | `test_ac3_missing_snapshot_fallback_sends_alert` |
| AC-4 | `test_ac4_double_alert_guard_suppresses_radar_when_forecast_recent` |
| AC-5 | `test_ac5_past_segment_no_alert_guard_test` |
| AC-6 | `test_ac6_radar_throttle_via_alert_state_cooldown` |
| AC-7 | `test_ac7_mandantentrennung_isolated` |

Testdatei: `tests/tdd/test_issue_818_radar_briefing_integration.py` (mock-frei, echter Dateisystem-State).

## Changelog

- 2026-06-24: v1.0 Initial spec created (Issue #818, Epic #813 Slice 3/3). Nowcast-vs-Briefing-Vergleich, Radar-Throttle-Migration → alert_state, Doppel-Alert-Schutz, Nachweis-Test Segment-Filter.
