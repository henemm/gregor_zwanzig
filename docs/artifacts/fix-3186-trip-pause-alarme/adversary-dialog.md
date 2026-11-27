# Adversary Dialog — fix-3186-trip-pause-alarme
Spec: docs/specs/modules/fix_3186_trip_pause_alarme.md
Datum: 2026-11-27 18:01

## Checkliste
- [x] **Input:** Trip mit `paused_at` oder `report_config.paused_until` in der Zukunft; Wetterabweichung, aktive amtliche Warnung oder Regen im Anflug.
- [x] **Output:** Kein Versand auf irgendeinem der vier Kanäle, kein Wetter-, Warnungs- oder Nowcast-Abruf, kein Alarmprotokoll-Eintrag.
- [x] **Side effects:** Keine. Der „zuletzt erreicht"-Stempel des Radar-Laufs bleibt gesetzt; Throttle, Anker und Warn-State bleiben unverändert.
- [x] **AC-1:** Given ein Trip mit gesetztem `paused_at` und einer signifikanten Wetterabweichung / When der Lauf `check_all_trips` läuft / Then wird auf keinem der vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) ein Alarm versendet und kein Wetter abgerufen
- [x] **AC-2:** Given ein pausierter Trip mit aktiver amtlicher Wetterwarnung / When der Alarmlauf läuft / Then wird nichts versendet, keine Warnung abgerufen und der Warn-State bleibt unverändert
- [x] **AC-3:** Given ein pausierter Trip mit Regen im Anflug / When der Radar-Lauf läuft / Then wird kein Nowcast abgerufen und nichts versendet, der Trip gilt aber als „erreicht" (Stempel bleibt, Fairness und Fristabbruch aus #3085 unverändert)
- [x] **AC-4:** Given `report_config.paused_until` liegt in der Zukunft (Inbound „pause 2d") / When Abweichungs-, Warn- und Radar-Lauf laufen / Then schweigen alle drei Alarmarten wie bei `paused_at`; liegt `paused_until` in der Vergangenheit, laufen die Alarme wieder normal
- [x] **AC-5:** Given eine Pause wird aufgehoben (`paused_at` entfernt) / When der nächste Lauf läuft / Then alarmiert der Trip wieder normal, und eine noch aktive amtliche Warnung kommt genau einmal
- [x] **AC-6:** Given ein nicht pausierter Trip / When die Alarmläufe laufen / Then alarmiert er unverändert auf allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS)
- [x] **AC-7:** Given die bestehende Pause-Fassung `trip_pausiert` / When der Riegel in den Alarmläufen greift / Then nutzt er genau diese Fassung (keine zweite Pause-Definition), bleibt still ohne Alarmprotokoll-Eintrag, `load_all_trips` filtert nicht, und der Testversand (Debug-/Test-Alarm) bleibt unberührt
- [x] **AC-8:** Given die Festlegung #995 AC-9 „Alert-Dispatch bleibt vom Pause-Filter unberührt" / When #3186 umgesetzt ist / Then ist sie ausdrücklich aufgehoben, und der Test `test_issue_995_scheduler_pause.py::TestAC9AlertDispatchUnaffected` prüft das umgekehrte Verhalten (pausiert = kein Alarm, ohne Pause = Alarm)

## Dialog

### Runde 1
**Adversary:**
Tests (benannte Dateien, Ausgabe pytest-green.txt): 33 passed, 0 failed (test_fix_3186, test_issue_995, test_trip_radar_schalter, test_alarm_radar_kette, test_alarm_amtliche_warnungen_kette).

Confirmation: AC-1/AC-2/AC-4 (Abweichung, amtliche Warnung)
Code reference: src/services/trip_alert.py:1203 (trip_pausiert-Riegel in check_all_trips, nach reached-Stempel Z.1194, vor Wetter-/Warnungsabruf). Status: CONFIRMED
Confirmation: AC-3 (Radar, Stempel bleibt)
Code reference: src/services/trip_alert.py:2133 (Riegel in _check_radar_trips hinter reached-Stempel und radar_alert_enabled, vor Segmentwahl/Nowcast). Status: CONFIRMED
Confirmation: AC-7 (eine Pause-Fassung, kein Loader-Filter)
Code reference: src/services/trip_alert.py:1203 und :2133 nutzen trip_pausiert aus trip_report_scheduler.py:322; load_all_trips unveraendert. Status: CONFIRMED
Confirmation: AC-5, AC-6, AC-8: durch Tests belegt (Fortsetzen genau ein Alarm, vier Kanaele, umgedrehter #995-Test). Status: CONFIRMED

Mutations-Gegenprobe (jeweils per String-Ersetzung, Original aus Sicherung wiederhergestellt):
- M1 Riegel check_all_trips entfernt: rot (AC1, AC2, AC4 x2, AC5, AC7)
- M2 Riegel Radar entfernt: rot (AC3 x2, AC4, AC7, 995 test_paused_trip_no_radar_alert)
- M3 Radar-Riegel VOR Stempel: rot (test_ac3_..._gilt_im_radarlauf_trotzdem_als_erreicht)
- M4a Riegel hinter _get_cached_weather: rot (AC1, AC4)
- M4b Riegel hinter check_official_alert_triggers: rot (AC1, AC2, AC4)
- M5 nur paused_at statt trip_pausiert: rot (AC4 zukunft und vergangen)
- M6 Pause-Filter in load_all_trips: rot (AC3-Stempel, AC7 x2)
Alle 7 Mutationen gefangen. Grenzfaelle trip_pausiert: paused_until == now -> nicht pausiert (konsistent mit Briefings), naiv -> UTC, aware +1s -> pausiert, report_config None -> nicht pausiert.

**Implementierer:** (keine Rueckfrage, kein Eingriff noetig)

### Runde 2
**Adversary:**
Fehlerpfad: trip_pausiert steht in beiden Schleifen innerhalb des je-Trip-try (Code reference: src/services/trip_alert.py:1203 und :2133), eine Ausnahme trifft nur diesen Trip (failed-Zaehler), andere Trips laufen weiter. Weitere Alarmeinstiege: api/routers/scheduler.py ruft nur check_all_trips / check_radar_alerts_run; check_and_send_alerts wird nur vom Testversand ausserhalb der Schleife genutzt (bewusst unberuehrt, AC-7 Test grün). Zweinutzer: Riegel liest nur das Trip-Objekt, keine user_id-Aenderung. Beobachtung (kein Finding): die Pause-Wirkung und Ausnahme-Isolation in der Schleife sind nicht durch einen eigenen Mutationstest fuer einen Mehr-Trip-Lauf belegt, der Code-Pfad ist aber strukturell ein continue.
Keine Findings.

**Implementierer:** (keine Rueckfrage)

## Herkunft der Vorbedingungen

Vorbedingungen (Trip-Dateien, Pause-Felder, Stubs) stammen aus den Tests selbst: Pause-Feld auf der Platte, echter Lauf ueber load_all_trips; keine Fremdaufzeichnung.

## Verdict

VERDICT: VERIFIED
Tests: 33 passed, 0 failed. Mutationen: 7/7 gefangen. Findings: keine.

## Geprüfte Dateien

- sha256:9dd26721fb42d257aa36eb6c8646a36bf5796c38d4b81e3dfff78d0fe0827907  src/services/trip_alert.py

## Prüfbasis

- base: 413cb7647d7f71155621912b217de95ed80ab70a
- blob:a8f547f3798bbb1aec14ac74108d5206a3185dd1  src/services/trip_alert.py
