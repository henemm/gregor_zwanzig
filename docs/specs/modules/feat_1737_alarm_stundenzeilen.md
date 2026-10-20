---
entity_id: feat_1737_alarm_stundenzeilen
type: feature
issue: 1737
created: 2026-10-20
updated: 2026-10-20
status: draft
version: "1.0"
workflow: feat-1737-alarm-stundenzeilen
tags: [alarm, renderer, stundenzeilen, trip, ortsvergleich]
---

# Abweichungsalarm zeigt Stundenzeilen (alt → neu je Stunde)

## Approval

- [ ] Approved

## Purpose

Der Abweichungsalarm nennt heute nur den Tageswert und die „stärkste Stunde". Er beantwortet damit nicht, zu welcher Uhrzeit sich etwas geändert hat (PO: „Gewitter ist besser geworden, aber zu welcher Uhrzeit kommt es jetzt mit weniger Heftigkeit?"). Diese Spec ergänzt je betroffener Stunde eine Zeile mit Uhrzeit und alt → neu, in derselben Darstellungsform wie das Briefing des jeweiligen Kanals (ROH = Stufe/Wert, EINFACH = farbiger Punkt).

## Source

- **File:** `src/output/renderers/alert/render.py` (Kern), `src/output/renderers/alert/project.py`, `src/output/renderers/alert/model.py`
- **Identifier:** `render_email`, `render_telegram`, `render_sms`, `to_alert_message`, `to_multi_point_alert_message`, `AlertEvent`

> Schicht: Python-Core (`src/output/`, `src/services/`). Kein Go- und kein Frontend-Code betroffen.

## Estimated Scope

- **LoC:** produktiv ca. +400 bis +480 / −30 (Tests zusätzlich)
- **Files:** ca. 9 produktiv + neue Testdatei(en) + angepasste Bestandstests
- **Effort:** high (ein Workflow, keine Scheiben: alle vier Kanäle und der Ortsvergleich gehören zu einer Frage, Epic #2133). `loc_limit_override 500` wird gesetzt, sobald `workflow.py status` den realen Stand zeigt.

## Nicht-Ziele

- **Radar-/Onset-Alarm** (`radar_alert_service.py`, `OnsetShiftEvent`): trägt einen Einsatzzeitpunkt, keine Stufen-Abweichung je Stunde. Unverändert.
- **Amtlicher Alarm**: eigener Renderer, unverändert.
- **`delta_pct`** (`alert/model.py`) bleibt ohne Aufrufer. Prozentuale Änderungsangaben kommen nicht zurück (seit #1948 S6 entfernt). Prozent als Einheit (z. B. Regenwahrscheinlichkeit) bleibt unberührt.
- **`src/output/renderers/email/helpers.py`** wird möglichst nicht geändert (sonst zusätzlich Briefing- und Compare-Nachweis nötig). Bestehende Funktionen (`ampel_level`, `_ampel_dot_css`, Gewitter-Wortpfad) werden nur aufgerufen; ein schmaler Helfer `alert/hours.py` kapselt die Alarm-Logik.
- **SMS-Stufen-Tokens** (`LEVELS`, #1948 S6 Nicht-Ziele) bleiben unverändert.
- **Zeitformat** `local_fmt` (`HH:MM`, mit #2009 abgestimmt) wird übernommen, nicht neu erfunden.
- Keine Handlungsempfehlungen, keine Prozentangaben, keine Confidence-Anzeige.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `weather_snapshot.save_alarm_anchor` / `load_alarm_anchor` (ADR-0056) | module | liefert die ALTE Stundenreihe (`hourly`) |
| `compare_weather_snapshot.py` | module | alte Stundenreihe je Ort im Ortsvergleich |
| `SegmentWeatherData.timeseries` | model | frische (neue) Stundenreihe |
| `email/helpers.py`: `ampel_level`, `_ampel_dot_css`, `fmt_val`, `build_format_modes` | module | Briefing-Zellformat und Punkt-Darstellung (nur lesend genutzt) |
| `loader._resolve_format_mode`, `get_metrics_for_channel` (`models.py`) | module | Auflösung ROH/EINFACH je Kanal (Kanal-Kaskade) |
| `metric_catalog.py` (`dp_field`, `is_level`, Ampel-Fähigkeit) | module | Stundengröße und Stufenfähigkeit je Metrik |
| `trip_alert.py`, `notification_service.py`, `compare_alert.py` | module | Durchreichen der alten Reihe und der Anzeige-Konfiguration |
| ADR-0009, ADR-0011, ADR-0013, ADR-0021, ADR-0056 | adr | Einheitlicher Renderer, Trip/Ortsvergleich-Teilung, Anker |

## Implementation Details

1. **Durchreichen:** `check_and_send_alerts` (`trip_alert.py`) gibt `cached_weather` (alte Reihe) über `_send_alert` an `send_deviation_alert` weiter. Im Ortsvergleich reicht `_evaluate_one_location` (`compare_alert.py`) `cached[0]` je Ort als `anchor_points` an `send_multi_location_deviation_alert` weiter. Die Alarm-Vorschau (`compare_alert_preview_service.py`) und `validator_render_service.py` nutzen denselben Weg.
2. **Anzeigemodus:** `_dispatch_alert_message` löst je Kanal den Modus (ROH/EINFACH) aus der Anzeige-Konfiguration des Trips bzw. Vergleichs des jeweiligen Nutzers auf (gleiche Kanal-Kaskade wie das Briefing) und gibt ihn an `AlertMessage` mit.
3. **Modell:** `AlertEvent` erhält additiv ein Feld `hours` (Tupel von Stundenzeilen: Ortszeit, alter Wert, neuer Wert, Stufe alt/neu). Fehlt es, bleibt die heutige Ausgabe.
4. **Projektion** (`to_alert_message`, `to_multi_point_alert_message`): Stunden im Segmentfenster werden per UTC-Zeitstempel zwischen alter und neuer Reihe gepaart; Ortszeit über den bestehenden `_tz_for_location`.
5. **Auswahl betroffener Stunden** (in `alert/hours.py`): Metrik mit Stufe (ampelfähig: Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, CAPE; dazu Gewitter) = Stunde mit Stufenwechsel. Metrik ohne Stufe (z. B. Temperatur) = Stunde, deren Stundendifferenz die Alarmschwelle der Metrik erreicht. Ergebnis ist der zusammenhängende Bereich von erster bis letzter betroffener Stunde. Mehr als 6 Zeilen: die 6 stärksten Stunden in Zeitreihenfolge plus Hinweiszeile „betroffen HH:MM–HH:MM".
6. **Darstellung:** E-Mail = Tabellenzeilen „HH:MM | alt → neu" (ROH: Stufenwort/Wert wie im Briefing; EINFACH: CSS-Punkte, keine Emojis, #2220). Telegram = Zeilenliste im Zellformat des Telegram-Briefings. SMS und Premium-SMS = Zeitspanne „HH–HH" am bestehenden Token.
7. **Ereignisstruktur:** Je Ereignis ein eigener Stundenblock unter seiner Kopfzeile (keine Kreuztabelle). Summen-Metriken: Summe bleibt in der Kopfzeile, Stundenzeilen zeigen Stundenwerte.

## Expected Behavior

- **Input:** Abweichungsalarm (Trip oder Ortsvergleich) mit alter Stundenreihe (Anker) und neuer Stundenreihe.
- **Output:** Je Ereignis und betroffener Stunde eine Zeile in allen vier Kanälen (SMS/Premium-SMS als Zeitspanne).
- **Side effects:** keine; ohne Stundenreihe bleibt die heutige Ausgabe unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Alarm, bei dem sich das Gewitter in den Stunden 14, 15 und 16 Uhr (Ortszeit) gegenüber dem Briefing geändert hat, When die Alarm-E-Mail erstellt wird, Then steht unter der Kopfzeile des Ereignisses je betroffener Stunde eine eigene Zeile mit der Uhrzeit im Format HH:MM (Ortszeit) und dem alten und neuen Wert (alt → neu), also drei Zeilen für 14:00, 15:00 und 16:00.

- **AC-2:** Given ein Trip, dessen Briefing in der E-Mail die Darstellung EINFACH (farbiger Punkt) und in einem anderen Kanal ROH (Stufe/Wert) nutzt, When der Alarm für diesen Trip in beiden Kanälen erstellt wird, Then zeigen die Stundenzeilen in der E-Mail farbige Punkte aus HTML/CSS (keine Emoji-Zeichen) und im anderen Kanal die Stufe bzw. den Wert, jeweils genau so wie das Briefing desselben Kanals.

- **AC-3:** Given ein Alarm mit betroffenen Stunden, When der ausführliche Telegram-Text erstellt wird, Then enthält er dieselben Stunden wie die E-Mail, je Stunde eine Zeile, und jede Zelle ist im gleichen Format geschrieben wie im Telegram-Briefing desselben Trips.

- **AC-4:** Given ein Alarm mit betroffenen Stunden von 14 bis 16 Uhr, When SMS und Premium-SMS erstellt werden, Then trägt das bestehende Token die Zeitspanne „14–16", die Stufen-Tokens (z. B. TH:M->H) bleiben unverändert und der Text ist höchstens 160 Zeichen lang.

- **AC-5:** Given ein Ortsvergleich-Alarm, bei dem zwei von drei Orten betroffen sind, When der Alarm in einem beliebigen Kanal erstellt wird, Then erscheinen die Stundenzeilen je betroffenem Ort unter dem Ort nach denselben Regeln wie beim Trip (Uhrzeit, alt → neu, ROH/EINFACH, Kappung), und der nicht betroffene Ort bekommt keine Stundenzeilen.

- **AC-6:** Given ein Alarm für eine Metrik mit Stufe (z. B. Gewitter, Wind) und einer für eine Metrik ohne Stufe (z. B. Temperatur), When die Stundenzeilen gebildet werden, Then ist bei der Metrik mit Stufe jede Stunde mit einem Stufenwechsel betroffen, bei der Metrik ohne Stufe jede Stunde, deren Unterschied zwischen alt und neu mindestens die Abweichungsschwelle erreicht, die für diese Metrik den Alarm ausgelöst hat (Einstellung des Trips bzw. Ortsvergleichs, sonst Standardwert), angewendet auf den Stundenwert; erreicht keine einzelne Stunde dieses Kriterium (z. B. weil sich eine Summe auf viele Stunden verteilt), gilt jede Stunde mit einer Abweichung zwischen alt und neu als betroffen; angezeigt wird der zusammenhängende Bereich von der ersten bis zur letzten betroffenen Stunde.

- **AC-7:** Given ein Ereignis mit 9 betroffenen Stunden, When der Alarm erstellt wird, Then zeigt er höchstens 6 Stundenzeilen, nämlich die 6 stärksten Stunden in der Reihenfolge der Uhrzeit, und darunter eine Hinweiszeile „betroffen HH:MM–HH:MM" mit der ersten und letzten betroffenen Stunde.

- **AC-8:** Given ein Alarm mit zwei Ereignissen (z. B. Gewitter und Wind), When die E-Mail erstellt wird, Then hat jedes Ereignis unter seiner eigenen Kopfzeile seinen eigenen Block von Stundenzeilen, und es entsteht keine gemeinsame Tabelle über beide Ereignisse.

- **AC-9:** Given ein Alarm für eine Summen-Metrik wie Niederschlag, When er erstellt wird, Then steht die Summe weiterhin in der Kopfzeile des Ereignisses und die Stundenzeilen zeigen die Werte der einzelnen Stunden, nicht die Summe.

- **AC-10:** Given ein Alarm, für den es keinen Anker mit alter Stundenreihe gibt (erster Alarm), When er erstellt wird, Then zeigt jede Stundenzeile nur den neuen Wert ohne „alt →" und ohne Zusatzhinweis; Given gar keine Stundenreihe vorhanden ist, Then ist die Ausgabe identisch mit der heutigen Ausgabe.

- **AC-11:** Given ein Ortsvergleich mit Alarm-Einstellungen, When die Alarm-Vorschau angezeigt wird, Then enthält sie dieselben Stundenzeilen wie der tatsächliche Versand für denselben Datenstand.

- **AC-12:** Given ein beliebiger Alarm mit Stundenzeilen, When er in irgendeinem Kanal erstellt wird, Then enthalten die Stundenzeilen und die Hinweiszeile nur Uhrzeiten und Werte bzw. Stufen, keine Empfehlung an den Nutzer und keine berechnete Prozentangabe (Prozent bleibt nur als Einheit eines Messwerts erlaubt).

- **AC-13:** Given zwei verschiedene Nutzer, deren Trips (oder Ortsvergleiche) unterschiedliche Darstellungen für denselben Kanal eingestellt haben (EINFACH bzw. ROH), When für beide ein Alarm erstellt wird, Then folgt jeder Alarm ausschließlich der Konfiguration seines eigenen Nutzers, und die Konfiguration des anderen Nutzers verändert die Ausgabe nicht.

## Test Plan

### Automated Tests (TDD RED)

Neue Kern-Testdatei(en), nach Verhalten benannt, z. B. `tests/tdd/test_alert_hour_rows.py`. Kein Mock-Theater: Eingabe sind aufgezeichnete Anker-/Frisch-Reihen als versionierte Fixtures, geprüft wird die gerenderte Ausgabe.

- [ ] Test 1: GIVEN aufgezeichnete Anker- und Frisch-Reihe mit Gewitter-Änderung 14–16 Uhr WHEN `render_email` THEN drei Zeilen 14:00/15:00/16:00 mit alt → neu (AC-1)
- [ ] Test 2: GIVEN Trip mit EINFACH in Mail und ROH in Telegram WHEN beide Kanäle rendern THEN Mail: CSS-Punkte ohne Emoji, Telegram: Stufenwort/Wert wie Briefing (AC-2, AC-3)
- [ ] Test 3: GIVEN Gewitter-Alarm WHEN SMS und Premium-SMS rendern THEN Token mit „14–16", Stufen-Tokens unverändert, Länge ≤ 160 (AC-4)
- [ ] Test 4: GIVEN Ortsvergleich mit zwei von drei betroffenen Orten WHEN Mail/Telegram rendern THEN Stundenzeilen nur bei den betroffenen Orten, gleiche Regeln wie Trip (AC-5)
- [ ] Test 5: GIVEN Stufenmetrik und Temperatur WHEN Auswahl betroffener Stunden THEN Stufenwechsel bzw. Differenz ≥ Schwelle, zusammenhängender Bereich (AC-6)
- [ ] Test 6: GIVEN 9 betroffene Stunden WHEN Mail rendert THEN genau 6 Zeilen in Zeitreihenfolge plus Hinweiszeile „betroffen HH:MM–HH:MM" (AC-7)
- [ ] Test 7: GIVEN Mehr-Ereignis-Alarm und Summen-Metrik WHEN Mail rendert THEN je Ereignis eigener Block, Summe in der Kopfzeile, Stundenwerte in den Zeilen (AC-8, AC-9)
- [ ] Test 8: GIVEN Alarm ohne Anker bzw. ohne jede Stundenreihe WHEN rendern THEN nur neuer Wert bzw. Ausgabe byte-gleich zur heutigen (AC-10)
- [ ] Test 9: GIVEN Alarm-Vorschau und Versand für denselben Datenstand WHEN beide rendern THEN gleiche Stundenzeilen (AC-11)
- [ ] Test 10: GIVEN Alarm mit Stundenzeilen WHEN alle Kanäle rendern THEN keine Handlungsempfehlung, keine berechnete Prozentangabe (AC-12)
- [ ] Test 11: GIVEN zwei Nutzer mit verschiedener Anzeige-Konfiguration WHEN je Nutzer ein Alarm rendert THEN jeder folgt seiner eigenen Konfiguration (AC-13)

### Bestandstests, die angepasst werden müssen

`tests/tdd/test_957_alert_mail_literal_structure.py` (feste Zeilenzahl/Struktur), `test_issue_918_alert_preview_4ch.py`, `test_issue_1169_compare_alert_consumer.py` (byte-genau), `test_alert_multi_event_where_when.py` (`splitlines()[-1]`) und weitere der ca. 88 Testdateien, die den Alert-Renderer referenzieren und die Zeilenzahl festschreiben. Erwartung: Fixtures ohne Stundenreihe bleiben unverändert grün (AC-10); nur Tests mit Stundenreihen werden nachgezogen.

## Gates

- `renderer_mail_gate`: für `alert/*` Matrix-Nachweis (Modus-Matrix-Test) und `radar_alert_mail_validator.py` frisch grün vor dem Commit. Wird `email/helpers.py` doch angefasst, zusätzlich Briefing- und Compare-Nachweis.
- Staging-Verifikation mit echter zugestellter Alarm-Mail (Wegwerf-Nutzer `gregor-test+…`) gegen den passenden Validator.
- Mutations-Gegenprobe im Adversary: z. B. Paarung per Index statt UTC-Zeitstempel, Kappung auf 7 statt 6, Modus hart auf ROH, Summe statt Stundenwert in den Zeilen.

## Risiken

- Zentraler, von allen vier Kanälen und beiden Flächen geteilter Renderer (Risiko mittel); additive Änderung, ohne Stundenreihe bleibt die Ausgabe gleich.
- Alte Stundenreihe muss durch mehrere Schichten durchgereicht werden; falsche Paarung (Zeitzone/UTC) würde falsche Uhrzeiten zeigen.
- SMS-Länge ≤ 160 Zeichen mit zusätzlicher Zeitspanne.
- Der Anker kann fehlen oder aus dem Briefing statt aus dem Alarm-Anker stammen (Quellenreihenfolge in `_get_cached_weather`).
- `render_deviation_alert` ist ein reiner Kompat-Shim für Tests und wird nicht angefasst.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/model.py` | MODIFY | `AlertEvent.hours`, Anzeigemodus je Kanal an `AlertMessage` |
| `src/output/renderers/alert/project.py` | MODIFY | Stundenzeilen aus alter und neuer Reihe bauen (Trip und Ortsvergleich) |
| `src/output/renderers/alert/render.py` | MODIFY | E-Mail (Einzel- und Mehr-Ereignis), Telegram, SMS/Premium-SMS |
| `src/output/renderers/alert/hours.py` | CREATE | Auswahl betroffener Stunden, Kappung, Zellformat ROH/EINFACH |
| `src/services/trip_alert.py` | MODIFY | alte Reihe an `send_deviation_alert` durchreichen |
| `src/services/notification_service.py` | MODIFY | alte Reihe und Anzeige-Konfiguration an Projektion/Renderer |
| `src/services/compare_alert.py` | MODIFY | `cached[0]` je Ort als `anchor_points` mitgeben |
| `src/services/compare_alert_preview_service.py` | MODIFY | Vorschau zeigt dieselben Stundenzeilen |
| `src/services/validator_render_service.py` | MODIFY | Aufrufer des Renderers mitziehen (prüfen) |
| `tests/tdd/test_alert_hour_rows.py` | CREATE | Kern-Tests (siehe Test Plan) |
| Bestandstests (siehe oben) | MODIFY | an neue Struktur anpassen |

### Estimated Changes
- Files: ca. 9 produktiv + Tests
- LoC: +400 bis +480 / −30 (produktiv)

## Known Limitations

- SMS und Premium-SMS können keine Stundentabelle tragen; dort nur die Zeitspanne „HH–HH".
- `delta_pct` bleibt ungenutzt; Prozentänderungen kommen nicht zurück.
- Radar-/Onset-Alarm und amtlicher Alarm zeigen keine Stundenzeilen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung innerhalb ADR-0011 (ein Renderer für alle Alarm-Kanäle), ADR-0021 (Trip/Ortsvergleich teilen Engine) und ADR-0056 (Alarm-Anker liefert die alte Reihe). Keine dokumentierte Entscheidung wird geändert.

## Changelog

- 2026-10-20: Initial spec created (Issue #1737, PO bestätigt volle Stundenansicht)
