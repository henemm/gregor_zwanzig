# Context: fix-3186-trip-pause-alarme (Issue #3186)

## Request Summary

Ein pausierter Trip (`paused_at` gesetzt, #995) bekommt keine Briefings mehr, die
Trip-Alarmpfade prüfen die Pause aber nicht: Radar-, Abweichungs- und amtliche
Warn-Alarme gehen weiter auf alle Kanäle. Ziel: geteilter Pause-Riegel für Trips
(analog `is_silenced` im Ortsvergleich, #1467 S2 AG6), vor jedem Nowcast-/Warnungs-Abruf,
in allen Trip-Alarmpfaden; Test je Pfad.

## Related Files

| Datei | Rolle |
|---|---|
| `src/services/trip_alert.py:1138` `check_all_trips` | Lauf für Abweichungs-Alarm UND amtliche Warnungen (`check_official_alert_triggers` bei :1261). Vorab-Filter bei :1200-1247 (aktive Quelle, abgelaufen) — Riegel gehört davor, vor `_get_cached_weather` und Warnungs-Abruf. |
| `src/services/trip_alert.py:2102` `_check_radar_trips` | Radar-Lauf; Vorbild-Riegel `radar_alert_enabled is False` bei :2122 (vor Segmentwahl und Nowcast, Stempel „erreicht" bleibt). |
| `src/services/trip_report_scheduler.py:322` `trip_pausiert(trip, moment)` | Bestehende EINE Fassung der Trip-Pause (`paused_at` ODER `report_config.paused_until` > moment), genutzt von Briefing-Sammellauf, Fälligkeit, „Nächstes Briefing". Kandidat für den geteilten Riegel. |
| `src/services/compare_alert_guard.py:48` `is_silenced` | Vorbild Ortsvergleich (paused_at, schedule=manual, archiviert, abgelaufen). |
| `src/app/loader.py:1804` `load_all_trips(include_archived=False)` | Archivierte Trips sind schon ausgenommen. |
| `api/routers/scheduler.py:112, :204` | Einstiege `/alert-checks` und Radar-Lauf. |

## Existing Patterns

- Radar-Schalter #2800: Prüfung als `continue` ganz vorn in der Trip-Schleife, nach dem „erreicht"-Stempel.
- Ortsvergleich: Regel nur im geteilten Baustein, nie inline (AC-28 aus #1467).
- Tests: `tests/tdd/test_trip_radar_schalter.py` — echter Lauf über `load_all_trips` mit Feld auf der Platte, `AlarmPruefstrecke`, zählende `RadarNowcastService`-Unterklasse, lokale Stubs für Telegram/seven.io, `mail_sink`. Vorlage für die neuen Tests (kein Mock-Theater).
- Amtliche Warnungen: `tests/tdd/test_issue_1088_official_alert_triggers.py`, `test_alarm_amtliche_warnungen_kette.py`.

## Dependencies / Dependents

- `trip_pausiert` liegt im Briefing-Scheduler; Import aus `trip_alert.py` ist schon üblich (`next_briefing.py` importiert ihn lokal). Zirkularität prüfen.
- Alarmprotokoll (#1459): ob ein pausierter Trip einen Unterdrückungs-Eintrag schreibt — Vorbild Radar-Schalter: kein Eintrag.

## Existing Specs

- `docs/specs/modules/feat_2800_trip_radar_alarm.md` (Radar-Schalter, gleiche Stelle)
- #1467 S2 AG6 / `compare_alert_guard` (Ortsvergleich-Vorbild)
- #995 (Trip-Pause-Knopf), #1969 AC-11 (`trip_pausiert`)

## Risks / offene Punkte für die Analyse

1. **`paused_until`**: `trip_pausiert` zählt auch die befristete Briefing-Pause (`report_config.paused_until`). Issue nennt nur `paused_at`. Entscheidung: gleiche Fassung wie Briefings (eine Wahrheit für „pausiert") vs. nur Knopf-Pause. Ortsvergleich-Vorbild `is_silenced` hat kein `paused_until`.
2. Rückkehr nach Fortsetzen: Throttle-/Anker-Zustand darf nicht dazu führen, dass beim Entpausieren alte Alarme nachgeschossen werden (Δ-Anker ist tagesgleich, amtliche Warnungen per State-Vergleich — prüfen, ob eine während der Pause aktive Warnung nach dem Fortsetzen einmal kommt; vermutlich gewollt).
3. Debug-/Test-Alarm-Trigger (`test_debug_trigger_*`) ist ausdrücklicher Testversand — nicht vom Riegel betroffen.
4. Amtliche Entwarnungen (#1441 allclear) während der Pause: State nicht verändern, damit nach dem Fortsetzen konsistent.

## Analysis

**Type:** Bugfix (Verhaltensumkehr von #995 AC-9, das „Alarme laufen trotz Pause weiter" bewusst festhielt).

### Root Cause
Die Trip-Pause ist nur im Briefing-Filter verdrahtet (`trip_pausiert`, `src/services/trip_report_scheduler.py:322`). Die beiden Trip-Alarmläufe in `src/services/trip_alert.py` kennen sie nicht: `check_all_trips` (:1138, Abweichung + amtliche Warnungen/Entwarnungen) und `_check_radar_trips` (:2102). `tests/tdd/test_issue_995_scheduler_pause.py:196` (`TestAC9AlertDispatchUnaffected`) schreibt das heutige Verhalten fest. Weitere Trip-Alarmwege gibt es nicht (Einstiege nur `api/routers/scheduler.py:101/198`); Testversand (`api/routers/debug.py`, `alert_test_service.py`) bleibt bewusst unberührt.

### Affected Files
| Datei | Change |
|---|---|
| `src/services/trip_alert.py` | MODIFY — zwei stille `continue`-Riegel mit `trip_pausiert(trip, now_utc)` (lokaler Import, Muster :1709) |
| `tests/tdd/test_issue_995_scheduler_pause.py` | MODIFY — AC-9-Test umdrehen (pausiert → kein Radar-Alarm; Gegenprobe ohne Pause → Alarm) |
| `tests/tdd/test_fix_3186_trip_pause_alarme.py` | CREATE — je Pfad ein Test (Abweichung, amtlich, Radar), `paused_until`-Fall, Pause-abgelaufen-Gegenprobe |

### Scope / Risk
~8 LoC Produktcode, 1 Produktdatei, Tests ~120 LoC. Risiko niedrig: reines Prädikat, seit #1969 AC-11 die eine Pause-Fassung.

### Technical Approach (Variante A, Plan-Bewertung)
| Variante | Verhalten | Dateien | LoC | Risiko |
|---|---|---|---|---|
| **A** `trip_pausiert` direkt | stumm bei `paused_at` ODER `paused_until` > jetzt | 1 | ~8 | niedrig |
| B neues Prädikat nur `paused_at` | „pause 2d" stoppt Briefings, nicht Alarme | 2 | ~15 | mittel (zwei Pause-Definitionen) |
| C neues Prädikat inkl. `paused_until` | wie A | 2 | ~15 | Duplikat |

Gewählt **A**: eine Pause-Definition für Briefing, Anzeige und Alarm; Parität zum Ortsvergleich (#1467 S2 AG6: Pause schweigt in allen Alarmpfaden).
- `check_all_trips`: Riegel nach dem „erreicht"-Stempel, VOR Vorab-Filter, `_get_cached_weather` und `check_official_alert_triggers` (sperrt Abweichung + amtlich zugleich, kein Wetter-/Warnungsabruf).
- `_check_radar_trips`: Riegel NACH dem Stempel (:2117, sonst Fristabbruch-Logik #3085 falsch), neben `radar_alert_enabled is False` (:2122), VOR Segmentwahl und Nowcast (ADR-0082-Budget).
- Stilles `continue`, kein Alarmprotokoll-Eintrag (Vorbild Radar-Schalter #2800).
- Filter NICHT in `load_all_trips()` (Trennung zum Briefing-Filter bleibt).

### Zustände (geprüft)
Throttle, Δ-Anker und amtlicher Warn-State werden nur beim Versand geschrieben → nach dem Fortsetzen kommt eine noch aktive amtliche Warnung einmal (gewollt). Eine während der Pause beendete Warnung erzeugt beim Fortsetzen ggf. keine Entwarnung mehr — Randfall, gewollt.

### Dependencies
Kein Zirkelimport (`trip_report_scheduler` importiert `trip_alert` nicht). Ortsvergleich-Inbound „pause" ist immer unbefristet (`_apply_compare_pause` :1661), Trip-„pause 2d" befristet über `paused_until` — kein Widerspruch.

### Open Questions / PO-relevant
- Produktaussage „Pause stoppt jetzt auch alle Alarme, inkl. amtlicher Unwetterwarnungen" hebt #995 AC-9 auf → steht in der Spec, Freigabe dort.
- Nebenbefund: Hilfetext des Befehls „pause" nennt nur „keine Briefings" — wird nach der Freigabe als Nebenbefund (#1199) erfasst, nicht in diesem Fix (Katalog/i18n, Zeichenbudget).
