---
entity_id: fix_3186_trip_pause_alarme
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-3186-trip-pause-alarme
tags: [trip, pause, alarm, radar, amtliche-warnung, "#3186", "#995"]
---

# Pausierter Trip schweigt in allen Alarmpfaden (Issue #3186)

## Approval

- [ ] Approved

## Purpose

Ein pausierter Trip bekommt heute keine Briefings mehr, aber Abweichungs-, amtliche Warn- und Radar-Alarme gehen weiter auf alle Kanäle. Der Fix lässt die Pause in allen drei Trip-Alarmarten schweigen, mit derselben Pause-Fassung wie bei den Briefings.

Produktaussage (PO-relevant): **Pause stoppt jetzt auch alle Alarme, einschließlich amtlicher Unwetterwarnungen.** Das hebt die bewusste Festlegung aus #995 AC-9 („Alert-Dispatch bleibt vom Pause-Filter unberührt") auf.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService.check_all_trips` (Abweichung und amtliche Warnungen), `TripAlertService._check_radar_trips` (Radar); Prädikat `trip_pausiert` in `src/services/trip_report_scheduler.py:322`

> **Schicht-Hinweis:** Nur Python-Core (`src/services/`). Go-API und Frontend bleiben unberührt (kein neues Feld, kein neuer Endpoint).

> **Trip/Ortsvergleich-Teilung:** Pendant ist `compare_alert_guard.is_silenced` (#1467 S2 AG6, Pause schweigt in allen Alarmpfaden des Ortsvergleichs). Der Trip nutzt das bestehende Trip-Prädikat `trip_pausiert`, keine zweite Definition. **Abweichung zum Ortsvergleich:** Dort gibt es keine befristete Pause (Inbound „pause" ist immer unbefristet, `_apply_compare_pause`); beim Trip kennt „pause 2d" zusätzlich `report_config.paused_until`. Das ist kein Widerspruch, sondern die unterschiedliche Bestandslage.

> **Mandantentrennung:** Es werden keine Nutzerdaten bewegt oder neu geschrieben. Das Prädikat liest nur das Trip-Objekt des jeweiligen Nutzers aus `load_all_trips`; `user_id` bleibt unverändert aus dem Trip.

> **Kanäle:** Der Riegel sitzt vor Kanal-Auflösung und Versand und gilt damit für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) gleichzeitig und gleichwertig (ADR-0095).

## Estimated Scope

- **LoC:** Produkt ca. +8, Tests ca. +120
- **Files:** 3 (1 Produktdatei, 2 Testdateien)
- **Effort:** low (Risiko niedrig: reines Prädikat, seit #1969 AC-11 die eine Pause-Fassung)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_alert.py | MODIFY | Zwei stille `continue`-Riegel mit `trip_pausiert(trip, now_utc)` (lokaler Import) in `check_all_trips` und `_check_radar_trips` |
| tests/tdd/test_issue_995_scheduler_pause.py | MODIFY | `TestAC9AlertDispatchUnaffected` umdrehen: pausiert = kein Radar-Alarm; Gegenprobe ohne Pause = Alarm |
| tests/tdd/test_fix_3186_trip_pause_alarme.py | CREATE | Je Alarmart ein Test, `paused_until` Zukunft/Vergangenheit, Fortsetzen, Gegenprobe auf vier Kanälen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| trip_pausiert (`src/services/trip_report_scheduler.py`) | function | Die eine Pause-Fassung: `paused_at` gesetzt ODER `report_config.paused_until` > Moment |
| TripAlertService.check_all_trips | service | Lauf für Abweichungs-Alarm und amtliche Warnungen/Entwarnungen (`check_official_alert_triggers`) |
| TripAlertService._check_radar_trips | service | Radar-Lauf; Vorbild-Riegel `radar_alert_enabled is False` (#2800) |
| RadarNowcastService | service | Nowcast-Abruf, darf bei Pause nicht aufgerufen werden (ADR-0082-Budget) |
| load_all_trips (`src/app/loader.py`) | function | liefert Trips (archivierte schon ausgenommen); bekommt bewusst KEINEN Pause-Filter |
| compare_alert_guard.is_silenced | function | Vorbild Ortsvergleich (#1467 S2 AG6), bleibt unverändert |
| api/routers/scheduler.py | router | Einstiege `/alert-checks` und Radar-Lauf, unverändert |
| feat_2800_trip_radar_alarm | spec | Radar-Schalter an gleicher Stelle, Stempel „erreicht" bleibt davor |
| #995 / #1969 AC-11 | issues | Trip-Pause-Knopf bzw. Einführung von `trip_pausiert` |
| ADR-0082, ADR-0095 | adr | Abrufbudget, Kanalparität |

Kein Zirkelimport: `trip_report_scheduler` importiert `trip_alert` nicht; der Import in `trip_alert.py` erfolgt lokal in der Funktion (bestehendes Muster).

## Implementation Details

Root Cause: Die Trip-Pause ist nur im Briefing-Filter verdrahtet. `check_all_trips` und `_check_radar_trips` kennen sie nicht; `TestAC9AlertDispatchUnaffected` schreibt dieses Verhalten fest. Weitere Trip-Alarmwege gibt es nicht (Einstiege nur über `api/routers/scheduler.py`).

Gewählt ist Variante A: `trip_pausiert` direkt verwenden. Verworfen: B (neues Prädikat nur `paused_at`, hätte „pause 2d" für Briefings, nicht aber für Alarme wirksam gemacht, zwei Pause-Definitionen) und C (neues Prädikat inkl. `paused_until`, Duplikat von A).

1. **`check_all_trips`:** stiller `continue` direkt nach dem „erreicht"-Stempel, VOR Vorab-Filter (aktive Quelle, abgelaufen), `_get_cached_weather` und `check_official_alert_triggers`. Das sperrt Abweichungs-Alarm und amtliche Warnung/Entwarnung zugleich; es gibt weder Wetter- noch Warnungs-Abruf.
2. **`_check_radar_trips`:** stiller `continue` NACH dem „erreicht"-Stempel (sonst wäre die Fristabbruch-/Fairness-Logik #3085 falsch), neben `radar_alert_enabled is False`, VOR Segmentwahl und Nowcast-Abruf.
3. **Still:** kein Alarmprotokoll-Eintrag (#1459), Vorbild Radar-Schalter #2800.
4. **Nicht in `load_all_trips`:** der Briefing-Filter und der Alarm-Riegel bleiben getrennt gesetzt, Anzeige und Listen sehen pausierte Trips weiter.
5. **Testversand unberührt:** Debug-/Test-Alarm (`api/routers/debug.py`, `alert_test_service.py`, `test_debug_trigger_*`) ist ausdrücklicher Testversand und umgeht den Riegel bewusst.

### Zustände

Throttle, Δ-Anker und amtlicher Warn-State werden nur beim Versand geschrieben. Während der Pause bleiben sie daher unverändert. Folge nach dem Fortsetzen: Eine noch aktive amtliche Warnung kommt einmal (gewollt). Eine während der Pause beendete Warnung erzeugt nach dem Fortsetzen ggf. keine Entwarnung mehr (Randfall, gewollt).

## Expected Behavior

- **Input:** Trip mit `paused_at` oder `report_config.paused_until` in der Zukunft; Wetterabweichung, aktive amtliche Warnung oder Regen im Anflug.
- **Output:** Kein Versand auf irgendeinem der vier Kanäle, kein Wetter-, Warnungs- oder Nowcast-Abruf, kein Alarmprotokoll-Eintrag.
- **Side effects:** Keine. Der „zuletzt erreicht"-Stempel des Radar-Laufs bleibt gesetzt; Throttle, Anker und Warn-State bleiben unverändert.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `tests/tdd/test_fix_3186_trip_pause_alarme.py`, kein Mock-Theater. Vorlage `tests/tdd/test_trip_radar_schalter.py`: Feld auf der Platte, echter Lauf über `load_all_trips`, `AlarmPruefstrecke`, zählende `RadarNowcastService`-Unterklasse, lokale Stubs für Telegram und seven.io, `mail_sink`.

- [ ] Test 1: GIVEN Trip mit `paused_at` und signifikanter Abweichung WHEN `check_all_trips` läuft THEN kein Versand auf vier Kanälen und kein Wetter-Abruf
- [ ] Test 2: GIVEN pausierter Trip mit aktiver amtlicher Warnung WHEN `check_all_trips` läuft THEN kein Versand, kein Warnungs-Abruf, Warn-State unverändert
- [ ] Test 3: GIVEN pausierter Trip und Regen im Anflug WHEN der Radar-Lauf läuft THEN zählender Nowcast-Dienst ohne Aufruf, kein Versand, Stempel „erreicht" gesetzt
- [ ] Test 4: GIVEN `paused_until` in Zukunft bzw. Vergangenheit WHEN alle drei Alarmläufe laufen THEN Zukunft = still, Vergangenheit = Alarme laufen
- [ ] Test 5: GIVEN Pause aufgehoben und noch aktive amtliche Warnung WHEN nächster Lauf THEN genau ein Alarm
- [ ] Test 6: GIVEN nicht pausierter Trip WHEN die Läufe laufen THEN Alarm auf allen vier Kanälen
- [ ] Test 7: GIVEN pausierter Trip WHEN Läufe laufen THEN kein Alarmprotokoll-Eintrag; Testversand (Debug-Trigger) liefert weiterhin
- [ ] Test 8: `test_issue_995_scheduler_pause.py::TestAC9AlertDispatchUnaffected` umgedreht (pausiert = kein Radar-Alarm, Gegenprobe ohne Pause = Alarm)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gesetztem `paused_at` und einer signifikanten Wetterabweichung / When der Lauf `check_all_trips` läuft / Then wird auf keinem der vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) ein Alarm versendet und kein Wetter abgerufen
  - Test: Trip mit `paused_at` auf der Platte, Wetter-Stub mit Abweichung; Versandprotokolle aller vier Kanäle leer, Wetter-Abruf-Zähler 0.

- **AC-2:** Given ein pausierter Trip mit aktiver amtlicher Wetterwarnung / When der Alarmlauf läuft / Then wird nichts versendet, keine Warnung abgerufen und der Warn-State bleibt unverändert
  - Test: Warnungs-Quelle zählt Aufrufe (0), Versandprotokolle leer, Warn-State-Datei vor und nach dem Lauf identisch.

- **AC-3:** Given ein pausierter Trip mit Regen im Anflug / When der Radar-Lauf läuft / Then wird kein Nowcast abgerufen und nichts versendet, der Trip gilt aber als „erreicht" (Stempel bleibt, Fairness und Fristabbruch aus #3085 unverändert)
  - Test: Zählende `RadarNowcastService`-Unterklasse ohne Aufruf, Versand leer, „zuletzt erreicht"-Stempel des Trips gesetzt.

- **AC-4:** Given `report_config.paused_until` liegt in der Zukunft (Inbound „pause 2d") / When Abweichungs-, Warn- und Radar-Lauf laufen / Then schweigen alle drei Alarmarten wie bei `paused_at`; liegt `paused_until` in der Vergangenheit, laufen die Alarme wieder normal
  - Test: Zwei Läufe je Alarmart mit `paused_until` in Zukunft (kein Versand) bzw. Vergangenheit (Versand erfolgt).

- **AC-5:** Given eine Pause wird aufgehoben (`paused_at` entfernt) / When der nächste Lauf läuft / Then alarmiert der Trip wieder normal, und eine noch aktive amtliche Warnung kommt genau einmal
  - Test: Lauf pausiert (kein Versand), `paused_at` von der Platte entfernen, zweiter Lauf: genau ein Warn-Alarm, dritter Lauf: keiner mehr.

- **AC-6:** Given ein nicht pausierter Trip / When die Alarmläufe laufen / Then alarmiert er unverändert auf allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS)
  - Test: Gegenprobe mit denselben Stubs ohne Pause; je Kanal genau ein Alarm zugestellt.

- **AC-7:** Given die bestehende Pause-Fassung `trip_pausiert` / When der Riegel in den Alarmläufen greift / Then nutzt er genau diese Fassung (keine zweite Pause-Definition), bleibt still ohne Alarmprotokoll-Eintrag, `load_all_trips` filtert nicht, und der Testversand (Debug-/Test-Alarm) bleibt unberührt
  - Test: Pausierter Trip bleibt über `load_all_trips` ladbar, Alarmprotokoll nach dem Lauf leer; Debug-Trigger für den pausierten Trip stellt weiter zu; ein Trip, den `trip_pausiert` als pausiert meldet, schweigt in allen drei Läufen.

- **AC-8:** Given die Festlegung #995 AC-9 „Alert-Dispatch bleibt vom Pause-Filter unberührt" / When #3186 umgesetzt ist / Then ist sie ausdrücklich aufgehoben, und der Test `test_issue_995_scheduler_pause.py::TestAC9AlertDispatchUnaffected` prüft das umgekehrte Verhalten (pausiert = kein Alarm, ohne Pause = Alarm)
  - Test: Umgedrehter Test läuft grün; er schlägt rot fehl, wenn der Riegel entfernt wird.

## Scope

- **Im Umfang:** Stille Riegel in `check_all_trips` und `_check_radar_trips` mit `trip_pausiert`, umgedrehter #995-Test, neue Testdatei.
- **Nicht im Umfang:** Pause-Filter in `load_all_trips`, neue Felder, Go/Frontend, Alarmprotokoll-Eintrag für Unterdrückung, Testversand, Ortsvergleich (hat `is_silenced`).
- **Nebenbefund (out of scope, Sammel-Issue #1199):** Der Hilfetext des Befehls „pause" nennt nur „keine Briefings". Anpassung (Katalog/i18n, Zeichenbudget) wird nach der Freigabe als Nebenbefund erfasst, nicht in diesem Fix.

## Known Limitations

- Eine während der Pause beendete amtliche Warnung erzeugt nach dem Fortsetzen ggf. keine Entwarnung mehr (gewollt).
- Während der Pause erscheint für Unterdrückung kein Alarmprotokoll-Eintrag (Vorbild #2800).
- Der Hilfetext „pause" beschreibt die erweiterte Wirkung noch nicht (Nebenbefund #1199).

## Definition of Done

- AC-1 bis AC-7 durch Kern-Tests in `tests/tdd/test_fix_3186_trip_pause_alarme.py` belegt (echte Läufe über `load_all_trips`, Pause-Feld auf der Platte, alle vier Kanäle), Kern-Schicht grün
- AC-8: `TestAC9AlertDispatchUnaffected` umgedreht und grün, übrige #995-/#1969-Pause-Tests unverändert grün
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe (Riegel entfernt/verschoben → ein Test wird rot)
- Alle 6 CI-Checks grün, Staging-E2E bestanden, Produktion ausgeliefert, Selftest grün
- Nebenbefund Hilfetext „pause" in #1199 erfasst

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein ADR geändert. Die Entscheidung ist die Umkehr der Festlegung #995 AC-9 (Spec-Ebene, hier ausdrücklich dokumentiert) und folgt ADR-0095 (alle Kanäle gleich) sowie ADR-0082 (Prüfung vor dem Abruf).

## Changelog

- 2026-11-27: Initial spec created (Issue #3186)
