---
entity_id: fix_2009_laufender_regen_vorlauf
type: bugfix
created: 2026-11-08
updated: 2026-11-08
status: implemented
version: "1.0"
workflow: fix-2009-nowcast-8min-nachmessung
tags: [alarm, radar, nowcast, alarmlog, entdopplung, issue-2009]
---

# Laufender Regen im Alarmlog und Ereignis-Anker: Vorlauf 0, Beginn = jetzt (#2009, Nachmessung)

## Approval

- [x] Approved

## Purpose

Bei bereits laufendem Regen meldet der Alarmlog heute weiterhin einen Vorlauf wie "8 Min", und der Ereignis-Anker (`event_at`) wandert mit jedem Lauf zum nächsten Viertelstundenpunkt. Die Spec zieht eine geteilte Ableitung in `src/services/alert_log.py` vor: Läuft der Regen schon, ist der Beginn der Zeitpunkt des Laufs und der Vorlauf 0. Trip- und Ortsvergleichspfad nutzen dieselbe Ableitung.

**Ehrliche Einordnung:** Die Anzeige an den Nutzer war schon korrekt. Der Renderer zeigt bei `already_running` "läuft bereits" (#2050 S2b). Der Fehler sitzt in der Messung (Alarmlog) und im Entdopplungsanker. Die "8" im Log ist deshalb überwiegend ein Mess-Artefakt, kein Wetterphänomen. Der Fix verbessert Messung und Entdopplung, nicht den Text an den Nutzer.

## Source

- **File:** `src/services/alert_log.py`
- **Identifier:** `nowcast_onset_at` (korrigiert) plus neue geteilte Vorlauf-Ableitung neben `nowcast_onset_at`

> **Schicht:** ausschließlich Python-Core (`src/services/`, `src/output/`). Kein Frontend, keine Go-API. Der Takt `3-58/5 * * * *` in `internal/scheduler/scheduler.go` bleibt unverändert.

> **Querschnitt:**
> - **Trip/Ortsvergleich:** Beide Pfade nutzen EINE Ableitung in `alert_log.py` (ADR-0021). Der Backoff-Schlüssel im Ortsvergleich wird wie im Trip gebildet. Es gibt keine Compare-eigene Variante.
> - **Mandantentrennung:** Es werden keine neuen datenbewegenden Endpoints angelegt. Die Wächter laufen trotzdem mit zwei verschiedenen Nutzern, damit der Alarmlog und die Entdopplung nicht nutzerübergreifend wirken.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS zeigen alle "läuft bereits" (ADR-0095). Der Inhalt bleibt unverändert, nur die Messung ändert sich.

## Estimated Scope

- **LoC:** Produktivcode ca. +25 bis +45, Tests ca. +140 bis +180
- **Files:** 4 Produktiv- (eine davon nur "prüfen") und 3 Testdateien
- **Effort:** low bis medium (Risiko LOW bis MEDIUM, weil die Entdopplung am `event_at` hängt)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py` (`RadarNowcastService`, `already_running`, `onset_minutes`) | module | Quelle, bleibt unverändert (Variante A verworfen) |
| `src/services/alert_log.py` (E-1-Felder `lead_time_minutes`, `event_at`, `event_end_at`) | module | Messinstrument, hier sitzt die geteilte Ableitung |
| `src/services/alert_gate.py` (Ereignis-Entdopplung) | module | Identität des Ereignisses hängt am `event_at` |
| `src/services/trip_alert.py` (`check_radar_alerts`) | module | Trip-Auslösepfad |
| `src/services/compare_radar_alert.py` (`check_all_compare_presets`) | module | Ortsvergleichs-Auslösepfad |
| `src/output/renderers/alert/render.py` / `project.py` | module | Anzeige "läuft bereits" in allen vier Kanälen, wird nur geprüft |
| `AlarmPruefstrecke`, `frame_source`-DI | test | Echter Prüfpfad ohne Mock |
| ADR-0021, ADR-0095 | adr | Trip/Vergleich geteilt, Kanalparität |
| Vorgänger-Specs `fix_2009_nowcast_vorlauf`, `feat_2261_a1_radar_vorlauf`, `feat_2261_a2s2_radar_takt`, `alarm_szenario_laufendes_ereignis` | spec | Bleiben gültig, diese Spec ergänzt sie |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_log.py` | MODIFY | `nowcast_onset_at` zieht `already_running` vor (Beginn = Lauf-Zeitpunkt). Neue Vorlauf-Ableitung (0 bei laufend). Falscher Docstring ("laufend, onset_minutes None") wird korrigiert. |
| `src/services/trip_alert.py` | MODIFY | `lead_time_minutes` (ca. `:443`) und `_onset_dt` (ca. `:2560`) nutzen die geteilte Ableitung |
| `src/services/compare_radar_alert.py` | MODIFY | `_onset_at` (ca. `:86`), Log-Stellen (ca. `:345`, `:471`) und Backoff-Schlüssel (ca. `:416`) wie im Trip (Trip `:2862` macht es schon richtig) |
| `src/output/renderers/alert/project.py` | VERIFY (MODIFY nur bei Befund) | Stellen ca. `:609`/`:625` prüfen, ob sie `onset_minutes` bei laufendem Regen ungeprüft durchreichen |
| `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` | MODIFY | Taktminute `:07` auf 5-Min-Takt `3-58/5` |
| `tests/tdd/test_radar_onset_threshold_variance.py` | MODIFY | Erwartete Vorlaufwerte: Raster 8 mod 15 wird zu 2/7/12 mod 15 |
| `tests/tdd/test_2009_laufender_regen_vorlauf_*.py` | CREATE | Die sieben RED-Wächter |

Zeilennummern sind Orientierung aus der Analyse. Der Developer verifiziert sie am Code.

### Nicht im Scope

- Dreifachmeldung vom 24.08. (ein Ereignis wird mehrfach gemeldet): eigener Mechanismus, Ticket #2848.
- Änderung der Quelle (`radar_service` `onset_minutes`): Variante A, verworfen. Sie würde die Semantik für Regenmenge, Aufenthaltsfenster, Mengenvergleich und Schärfe ändern.
- Stabiler Anker `running_since` (Slot-Start des laufenden Frames, Variante C): nur Folgeticket, falls die Entdopplung mit "jetzt" nicht hält.

## Implementation Details

Gewählt ist Variante B.

1. `nowcast_onset_at(nowcast, now_utc)` in `alert_log.py` prüft zuerst `already_running`. Dann ist der Beginn `now_utc`, sonst gilt die bisherige Ableitung aus `onset_minutes`.
2. Eine geteilte Funktion in `alert_log.py` liefert den Vorlauf: 0 bei `already_running`, sonst `onset_minutes`.
3. `trip_alert.py` und `compare_radar_alert.py` schreiben `lead_time_minutes`, `event_at` und `event_end_at` über diese Funktionen, ohne eigene Rechnung.
4. Der Backoff-Schlüssel im Ortsvergleich nutzt bei laufendem Regen keinen wandernden Zeitpunkt, so wie der Trip (`:2862`).
5. Die Quelle `radar_service` bleibt unverändert.

**Entdopplung:** Die Identität eines laufenden Ereignisses darf nicht von einem je Lauf wandernden Anker abhängen. Hält das "jetzt" als Anker nicht, belegt das der Wächter 3 oder 4 als rot, und es folgt Variante C als eigenes Ticket. Vor diesem Befund wird sie nicht vorweggenommen.

**Erwartete Vorlaufwerte im 5-Min-Takt:** Der Takt `3-58/5` gegen 15-Min-INCA-Frames ergibt Vorläufe von 2, 7 oder 12 Minuten (mod 15). Das ist ehrliche Arithmetik, keine Klemmung. Sie steht im Wächter als erwartete Werte, damit der Verdacht "alles ist 8" nicht wiederkehrt.

## Expected Behavior

- **Input:** Ein Lauf von `check_radar_alerts()` bzw. des Ortsvergleichs-Pfads mit einem Nowcast, bei dem das laufende Frame nass ist (`already_running`).
- **Output:** Alarmlog-Eintrag mit `lead_time_minutes = 0`, `event_at` = Zeitpunkt des Laufs. Nutzertext unverändert "läuft bereits".
- **Side effects:** Die Entdopplung verwendet den neuen Anker. Es wird für ein andauerndes Ereignis weiterhin höchstens ein Alarm gesendet.

## Definition of Done

AC-1 bis AC-8 sind durch die benannten Wächter (Trip- und Ortsvergleichs-Pfad, kein Mock) erst rot, dann grün nachgewiesen; die angepassten Bestandstests `test_alarm_szenario_laufendes_ereignis` und `test_radar_onset_threshold_variance` sind grün; die Mutations-Gegenprobe (Ableitung zurück auf `onset_minutes`) wird in beiden Pfaden einzeln rot; die Staging-Verifikation ist bestanden, Prod-Deploy und Selftest (Exit 0) sind durchgelaufen; im Ticket #2009 ist die Grenze „Produktivnachweis erst beim nächsten Regen auf einem aktiven Trip" kommentiert.

## Test Plan

### Automated Tests (TDD RED)

Alle Wächter fahren über den echten `check_radar_alerts()` bzw. den Ortsvergleichs-Pfad (`check_all_compare_presets`) mit `AlarmPruefstrecke` und `frame_source`-DI am echten `RadarNowcastService`. Kein `Mock()`/`patch()`. Zeitfest über `tests/helpers/wanduhr_matrix.py`.

- [x] Wächter 1: GIVEN Trip, laufendes und nächstes Frame nass, Lauf im 5-Min-Takt, WHEN der Alarm gesendet wird, THEN Log-Vorlauf 0 und Beginn = Lauf-Zeitpunkt (nicht nächster Viertelstundenpunkt).
- [x] Wächter 2: Dasselbe im Ortsvergleich.
- [x] Wächter 3: GIVEN laufender Regen über vier Stunden, Läufe alle 5 Minuten, THEN höchstens ein Alarm je 3 Stunden, nicht mehr Alarme als heute (genau ein Alarm: #2851).
- [x] Wächter 4: GIVEN Alarm "kommt in 8", WHEN der Regen beginnt und der nächste Lauf "läuft" sieht, THEN kein zweiter Alarm.
- [x] Wächter 5 (Gegenprobe): GIVEN Frame davor trocken, Regen in 8, THEN Vorlauf bleibt 8.
- [x] Wächter 6: GIVEN INCA und Takt `3-58/5`, THEN Vorlauf nur 2/7/12 mod 15, nicht überall 8.
- [x] Wächter 7: GIVEN laufender Regen, THEN alle vier Kanäle zeigen "läuft bereits", nie "in 0 Min".
- [x] Angepasste Bestandstests (`test_alarm_szenario_laufendes_ereignis`, `test_radar_onset_threshold_variance`) laufen grün.

Mutations-Gegenprobe (Pflicht, `implementation-validator`): Ersetzt man die Ableitung wieder durch `onset_minutes`, muss mindestens ein Wächter rot werden, und zwar in beiden Pfaden einzeln.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivem Radar-Alarm und einem Regen, der zum Zeitpunkt des Laufs bereits läuft (laufendes und nächstes Frame nass) / When der Alarm im 5-Minuten-Takt ausgelöst und protokolliert wird / Then steht im Alarmlog ein Vorlauf von 0 Minuten und als Beginn der Zeitpunkt des Laufs, nicht der nächste Viertelstundenpunkt.
  - Test: Wächter 1, echter `check_radar_alerts()` über `AlarmPruefstrecke`, Alarmlog-Eintrag ausgelesen, kein Mock.

- **AC-2:** Given ein Ortsvergleich mit aktivem Radar-Alarm und bereits laufendem Regen an einem Ort / When der Ortsvergleichs-Pfad ausgelöst und protokolliert wird / Then steht im Alarmlog derselbe Vorlauf 0 und derselbe Beginn (Zeitpunkt des Laufs) wie beim Trip, über dieselbe geteilte Ableitung.
  - Test: Wächter 2, Ortsvergleichs-Pfad über `AlarmPruefstrecke`, `frame_source`-DI, Ergebnis gegen Trip-Wert verglichen.

- **AC-3:** Given ein Regen, der vier Stunden lang andauert, und Läufe alle 5 Minuten / When alle Läufe nacheinander durchlaufen / Then wird innerhalb von 3 Stunden höchstens ein Alarm gesendet und nicht einer je Lauf, im Trip und im Ortsvergleich; insgesamt kommen nicht mehr Alarme als vor der Korrektur.
  - Test: Wächter 3, Langlauf über viele Takte, Zeitpunkte gesendeter Alarme gezählt, beide Pfade.
  - Eingegrenzt per PO-Entscheidung 2026-11-08: „genau ein Alarm über die ganze Dauer“ ist mit dem Anker „jetzt“ nicht erreichbar (Entdopplungsgrenze 180 Min), Folgeticket #2851.

- **AC-4:** Given ein bereits gesendeter Alarm "Regen kommt in 8 Minuten" / When der Regen beginnt und der nächste Lauf den Regen als laufend erkennt / Then kommt kein zweiter Alarm für dasselbe Ereignis.
  - Test: Wächter 4, Übergang "kommt" zu "läuft" über zwei Läufe, genau ein Versand insgesamt.

- **AC-5:** Given das Frame vor dem Regen ist trocken und der Regen beginnt in 8 Minuten / When der Alarm protokolliert wird / Then bleibt der Vorlauf 8 Minuten und der Beginn der berechnete Regenbeginn (die Gegenprobe: echter Vorlauf wird nicht auf 0 gesetzt).
  - Test: Wächter 5, trockenes Vorframe, Alarmlog-Vorlauf 8, Beginn = Frame-Zeitpunkt.

- **AC-6:** Given INCA-Frames im 15-Minuten-Raster und der Takt `3-58/5` / When über einen Zeitraum von mehreren Läufen vor einem Regenbeginn gemessen wird / Then liegen die Vorlaufwerte bei 2, 7 oder 12 Minuten (mod 15) und nicht durchgehend bei 8, damit die Streuung als erwarteter Wert festgeschrieben ist.
  - Test: Wächter 6 sowie angepasster `test_radar_onset_threshold_variance`, erwartete Werte 2/7/12 mod 15.

- **AC-7:** Given ein bereits laufender Regen / When der Alarm über E-Mail, Telegram, SMS und Premium-SMS ausgeliefert wird / Then zeigt jeder der vier Kanäle "läuft bereits" und keiner den Text "in 0 Min".
  - Test: Wächter 7, gerenderter Inhalt aller vier Kanäle auf "läuft bereits" geprüft, "in 0 Min" ausgeschlossen.

- **AC-8:** Given zwei verschiedene Nutzer mit je einem Trip und laufendem Regen / When beide Läufe ausgelöst werden / Then schreibt jeder Nutzer nur in seinen eigenen Alarmlog und die Entdopplung des einen unterdrückt den Alarm des anderen nicht.
  - Test: Zwei-Nutzer-Lauf im Wächter 1, Alarmlog je Nutzer geprüft.

## Known Limitations

- **Produktivnachweis:** Das Ticket #2009 lässt sich deterministisch nachweisen (Wächter 1 bis 7, Staging-Verifikation). Ein Nachweis im Produktivbetrieb ist erst möglich, sobald es auf einem aktiven Trip regnet. Bis dahin gibt es in Produktion keine neuen Radar-Alarme (Saisonende, kein aktiver Trip). Schließ-Kriterium des Tickets ist der deterministische Nachweis. Diese Grenze wird im Ticket-Kommentar benannt.
- Die Mess-Deutung der Alarmlog-Einträge vom 25.08. ("8", Ende gleich Horizontende) ist ein Indiz für das Artefakt, kein Beweis. Den Mechanismus belegt der Wächter 1.
- Mitschnitte der Eingangsdaten (`alert_input`) werden nur 24 Stunden aufbewahrt, eine rückwirkende Reproduktion am echten Regenereignis ist deshalb nicht möglich.
- Das "jetzt" als Entdopplungsanker trägt nicht über 3 Stunden hinaus (in RED gemessen: 4 h Regen ergeben Alarme um 10:03 und 13:08, heute 10:03 und 13:18). Ein Alarm über die ganze Dauer kommt in Folgeticket #2851 (stabiler, fortgeschriebener Anker), nicht in diese Spec.
- Wächter 7 prüft „läuft bereits" im Ortsvergleich nur für die E-Mail; Telegram, SMS und Premium-SMS sind nur im Trip-Pfad gerendert geprüft. Die Kanal-Darstellung wurde durch diesen Fix nicht geändert.
- Zusätzlich angepasster Bestandstest `tests/tdd/test_alert_log_ereignisgroessen.py` (erwartete `lead_time_minutes` bei `already_running` None → 0); in Affected Files nicht gelistet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine bestehende Entscheidung geändert. Die Anzeige "läuft bereits" (#2050) bleibt, die Quelle bleibt, und ADR-0021 (Trip/Vergleich geteilt) und ADR-0095 (Kanalparität) werden eingehalten. Es ist eine Fehlerbehebung innerhalb dieser Vorgaben.

## Changelog

- 2026-11-08: Implementiert und validiert (Phase 7), Status implemented (65 passed)
- 2026-11-08: AC-3 per PO-Entscheidung eingegrenzt auf „höchstens ein Alarm innerhalb von 3 Stunden“, Rest in #2851 (Befund aus TDD RED)
- 2026-11-08: Initial spec created (Nachmessung #2009, Variante B gewählt, A verworfen, C als mögliches Folgeticket)
