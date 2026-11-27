---
entity_id: fix_2063_onset_minute_exakt
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-2063-onset-minute
tags: [alarm, nowcast, radar, onset, zeit, paritaet]
---

# Radar-Uhrzeiten exakt am Frame-Zeitpunkt, Issue #2063

## Approval

- [ ] Approved

## Purpose

Die Uhrzeit im Radar-Alarm (Beginn, seit #2051 auch Ende und Radar-Reichweite) liegt in rund jedem zweiten Lauf eine Minute vor dem Zeitstempel der Radar-Quelle (z. B. 17:59 statt 18:00). Ursache: Der Dienst rundet auf ganze Minuten, verwirft den exakten Zeitpunkt, und jeder Verbraucher rechnet mit seiner eigenen Uhr (inklusive Sekunden) zurück und schneidet ab. Diese Spec führt exakte Zeitpunkte im Ergebnis mit und zeigt in allen Kanälen genau den Frame-Zeitpunkt, unabhängig von der Sekunde, in der der Lauf startet.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `NowcastResult`, `RadarNowcastService._derive_result`

Begleitend: `src/services/alert_log.py` (`nowcast_onset_at`, `nowcast_event_end_at`), `src/output/renderers/alert/project.py` (`onset_display`, `onset_event_from_nowcast`), `src/output/renderers/email/starkregen_hint.py`, `src/services/trip_report_scheduler.py`, `src/services/notification_service.py`, `src/services/rain_extent.py`, `src/services/trip_command_processor.py`.

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/`, `src/output/`). Kein Frontend, keine Go-API.
>
> **Trip/Ortsvergleich-Teilung:** Trip-Alarm und Ortsvergleich-Alarm nutzen weiterhin EINE zentrale Ableitung (`alert_log.nowcast_onset_at`, #2050 S6, ADR-0021). Es entsteht kein Pendant, der Fix gehört in die geteilte Stelle.
>
> **Mandantentrennung:** Keine Nutzerdaten werden bewegt, keine neue Persistenz, kein neuer Endpoint; `user_id`-Fluss unverändert.
>
> **Kanäle:** SMS, Premium-SMS, Telegram, E-Mail zeigen für denselben Lauf dieselbe Uhrzeit (ADR-0095, Kanalparität). Deshalb EIN gemeinsamer Release aller drei Scheiben.

## Estimated Scope

- **LoC:** ca. 220 (additiv, Optional-Felder mit Default None)
- **Files:** 8 Produktivdateien in 3 Scheiben (je Scheibe höchstens 4) + neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NowcastResult` | dataclass (`radar_service.py`) | Bekommt additiv `onset_at`, `event_end_at`, `source_reach_at` (UTC-Zeitpunkte, Default None) |
| `_derive_result` | method (`radar_service.py`) | Kennt `onset_ts` und `_end_ts` bereits exakt (seit #2046/#2051); setzt künftig die neuen Felder |
| `alert_log.nowcast_onset_at` / `nowcast_event_end_at` | functions | Zentrale Ableitung für Trip + Ortsvergleich; bevorzugt das Feld, Fallback `now + Minuten` |
| `project.onset_display` / `onset_event_from_nowcast` | functions | Baustein #2982 für Trip-Versand, Ortsvergleich, Replay; bekommt exakte Zeitpunkte, kein doppeltes Abschneiden des Vorlaufs |
| `utils/timezone.local_fmt` | function | Formatiert Uhrzeit (`%H:%M`); unverändert |
| `radar_alert_due` / `RADAR_ONSET_THRESHOLD_MIN` | Fälligkeitslogik | Nutzt `onset_minutes`, bleibt unverändert |
| `fix_2046_onset_menge`, `fix_2009_nowcast_vorlauf`, `fix_2982_onset_event_baustein`, `feat_2054_onset_wochentagskuerzel` | Specs | Vorarbeiten; Mengenrechnung, Vorlauf, Baustein und Wochentagskürzel bleiben erhalten |

## Implementation Details

Ansatz A2 (exakte Zeitstempel im Ergebnis statt Rückrechnung). Verworfen: B (`computed_at` plus Rundung, Tie-Risiko bei exakt :30) und C (nur Rundung in Verbrauchern, Drift durch frisches `now` bleibt).

**S1 Kern** (`radar_service.py`, `alert_log.py`, `alert/project.py`, ca. 90 LoC)

- `NowcastResult` erhält `onset_at`, `event_end_at`, `source_reach_at` (Optional, Default None). `_derive_result` setzt sie aus `onset_ts`, `max(_end_ts, _laufend[3])` (Ende bei laufendem Regen = Deckungsgrenze) und der Quell-Reichweite. `onset_minutes`/`event_end_minutes` bleiben unverändert (Vorlauf „in ~22 Min“, Logik).
- `format_now_text` (DE und EN, Wetter-Abfrage-Antwort) nutzt die Felder statt eines frischen `datetime.now()` (bisher `radar_service.py:871`, `:957`).
- `alert_log.nowcast_onset_at` und `nowcast_event_end_at` liefern das Feld, wenn gesetzt; sonst Fallback `now + minutes`. Bei `already_running` bleibt der Beginn `now_utc` (Regel #2050 S6).
- `project.py`: `onset_display`, `event_end_display`, `source_reach_display` formatieren den exakten Zeitpunkt; das doppelte Abschneiden des `vorlauf` entfällt.

**S2 Briefing und Versand** (`starkregen_hint.py`, `trip_report_scheduler.py`, `notification_service.py`, ca. 60 LoC)

- Starkregen-Kurzfristhinweis (`starkregen_hint.py`) verwendet die exakten Zeitpunkte und kein frisches `now`; Scheduler und Versand reichen sie durch (statt nur Minuten).

**S3 Strecken-Antwort** (`rain_extent.py`, `trip_command_processor.py`, ca. 70 LoC)

- Zonen tragen exakte Zeitpunkte; Inbound-Antwort (Zonen, Mail und Telegram) nennt dieselbe Uhrzeit wie der Alarm. Ohne exakten Zeitpunkt gilt der Fallback.

**Fallback:** Ist das Feld None (Replay, Vorschau, Stand-ins, alte Daten), gilt wie heute `now + Minuten`, ohne Absturz.

## Expected Behavior

- **Input:** `NowcastResult` aus `_derive_result` mit Frames; Laufzeitpunkt `now` in beliebiger Sekundenlage.
- **Output:** Jede angezeigte Radar-Uhrzeit (Beginn, Ende, Reichweite) ist exakt der Frame-Zeitpunkt, in allen Kanälen und Flächen identisch.
- **Side effects:** keine; additive Felder, Fälligkeit/Schwellen/Alarmtexte/`onset_minutes`-Rundung unverändert.

## Acceptance Criteria

Alle Tests laufen ohne Netz und ohne echte Uhr; die Sekundenlage wird über ein injiziertes `now` gesteuert (z. B. 17:37:42 und 17:37:12).

- **AC-1:** Given ein Radar-Frame mit Regenbeginn um 18:00 und ein Lauf um 17:37:42 bzw. 17:37:12 / When der Trip-Alarm und der Ortsvergleich-Alarm über die zentrale Ableitung gebildet werden / Then nennen beide Alarme als Beginn 18:00 und nicht 17:59.
  - Test: Zwei Läufe mit unterschiedlicher Sekundenlage über `_derive_result` und `nowcast_onset_at`; Trip- und Ortsvergleich-Text werden auf "18:00" geprüft.

- **AC-2:** Given ein Regenende bei Frame 19:45 und ein Lauf um 17:37:42 bzw. 17:37:12 / When der Alarm mit Ende-Angabe gebildet wird / Then nennt der Alarm als Ende 19:45.
  - Test: `nowcast_event_end_at` und gerenderter Alarm für beide Sekundenlagen, Prüfung auf "19:45".

- **AC-3:** Given eine Radar-Reichweite, die bei Frame 19:00 endet, und beide Sekundenlagen / When der Alarm die Reichweite nennt / Then steht dort 19:00.
  - Test: `source_reach_display` für beide Sekundenlagen auf "19:00" geprüft.

- **AC-4:** Given es regnet bereits beim Lauf (laufender Regen) / When der Alarm gebildet wird / Then bleibt der Beginn „jetzt“ und das Ende entspricht exakt der Deckungsgrenze der Radar-Daten, unabhängig von der Sekundenlage.
  - Test: `_derive_result` mit laufendem Regen, `already_running` und Ende gleich `max(_end_ts, Deckungsgrenze)`; beide Sekundenlagen.

- **AC-5:** Given ein Nowcast-Ergebnis mit Beginn 18:00 / When die Wetter-Abfrage (Kommando-Antwort) auf Deutsch und auf Englisch den Text bildet / Then nennt der Text in beiden Sprachen 18:00, dieselbe Uhrzeit wie der Alarm.
  - Test: `format_now_text` DE und EN für beide Sekundenlagen auf "18:00".

- **AC-6:** Given ein Starkregen-Hinweis im Briefing mit Beginn 18:00 / When das Briefing gerendert wird / Then nennt der Hinweis 18:00, auch wenn zwischen Abfrage und Rendern Sekunden vergangen sind.
  - Test: `starkregen_hint` mit injiziertem `now` in zwei Sekundenlagen, Prüfung auf "18:00".

- **AC-7:** Given eine Strecken-Antwort mit Regenzonen (Beginn 18:00) / When die Antwort per E-Mail und per Telegram gebildet wird / Then nennen beide Kanäle 18:00 als Zonenbeginn.
  - Test: `trip_command_processor`-Antwort mit Zonen aus `rain_extent`, E-Mail- und Telegram-Text auf "18:00".

- **AC-8:** Given derselbe Radar-Lauf / When SMS, Premium-SMS, Telegram und E-Mail den Alarm darstellen / Then zeigen alle vier Kanäle dieselbe Uhrzeit für Beginn, Ende und Reichweite.
  - Test: Vergleichstest über alle vier Kanäle für denselben Lauf (Sekundenlage :42), extrahierte Uhrzeiten sind identisch.

- **AC-9:** Given Beginn in 22,3 Minuten / When der Alarm erzeugt wird / Then lautet der Vorlauf unverändert „in ~22 Min“ und Fälligkeit, Schwellen und Entprellung (`radar_alert_due`) entscheiden wie vor der Änderung.
  - Test: `onset_minutes == 22`, Vorlauftext "~22 Min", `radar_alert_due`-Ergebnis identisch zum Vorzustand für Grenzwerte (z. B. 55 Min).

- **AC-10:** Given ein Ergebnis ohne exakten Zeitstempel (Replay, Vorschau, alte Daten) / When der Alarm gerendert wird / Then zeigt er wie bisher `jetzt + Minuten`, und es tritt kein Fehler auf.
  - Test: `NowcastResult` mit `onset_at=None`, `event_end_at=None` durch Trip-, Ortsvergleich- und Replay-Pfad; Ergebnis entspricht der bisherigen Rechnung, kein Absturz.

- **AC-11:** Given ein Regenbeginn nach Mitternacht (Frame 00:15 des Folgetags) / When der Alarm gebildet wird / Then zeigt er 00:15 mit dem korrekten Tagesbezug bzw. Wochentagskürzel (#2054, #2219).
  - Test: Lauf um 23:50:42 mit Frame 00:15; Tagesversatz und Kürzel stimmen, Bestandstest `test_alert_onset_day_rollover.py` bleibt grün.

## Known Limitations

- Frische Läufe zeigen die Frame-Zeit der Quelle, nicht die Ankunftszeit auf die Sekunde; das ist gewollt (Frame-Raster 5/15 Minuten).
- Gespeicherte ältere Ergebnisse ohne die neuen Felder zeigen weiterhin die bisherige Rechnung (Fallback); eine Nachmigration gibt es nicht.
- Der Alarm-Anker (#1468, #2009) vergleicht Onset-Zeitpunkte über `nowcast_onset_at`; exakte Frame-Zeit macht ihn stabiler, Anker-Tests (`test_onset_anchor_*`) sind als Regressionsnachweis mitzulaufen.

## Scope

### Affected Files

| File | Change Type | Scheibe |
|------|-------------|---------|
| `src/services/radar_service.py` | MODIFY | S1 |
| `src/services/alert_log.py` | MODIFY | S1 |
| `src/output/renderers/alert/project.py` | MODIFY | S1 |
| `src/output/renderers/email/starkregen_hint.py` | MODIFY | S2 |
| `src/services/trip_report_scheduler.py` | MODIFY | S2 |
| `src/services/notification_service.py` | MODIFY | S2 |
| `src/services/rain_extent.py` | MODIFY | S3 |
| `src/services/trip_command_processor.py` | MODIFY | S3 |

### Nicht im Scope

- Keine Änderung an der Rundung von `onset_minutes`/`event_end_minutes`.
- Keine Änderung an Schwellen, Fälligkeit, Entprellung.
- Keine Änderung an Alarmtexten außerhalb der Uhrzeit.

## Definition of Done

- AC-1 bis AC-11 durch benannte Tests grün; Bestandstests der Onset-Familie unverändert grün.
- Adversary mit Mutations-Gegenprobe ohne offenen Befund; alle sechs CI-Checks grün.
- Alle drei Scheiben in einem gemeinsamen Release (Kanalparität, ADR-0095).
- Staging-Verifikation bestanden, Prod-Deploy mit Selftest-Exit 0.

## Test Plan

### Automated Tests (TDD RED)

Neue Dateien unter `tests/tdd/` (benannt nach Verhalten, kein Mock-Theater, injiziertes `now` bzw. `RadarNowcastService(now_fn=...)`):

- [ ] `tests/tdd/test_onset_zeit_exakt_frame.py`: AC-1 bis AC-4, AC-9 bis AC-11 (Kern, S1). GIVEN Frame 18:00 und Lauf um 17:37:42/17:37:12 WHEN Alarm gebildet THEN "18:00".
- [ ] `tests/tdd/test_onset_zeit_exakt_abfrage_briefing.py`: AC-5, AC-6 (S1/S2).
- [ ] `tests/tdd/test_onset_zeit_exakt_strecke.py`: AC-7 (S3).
- [ ] `tests/tdd/test_onset_zeit_exakt_kanalparitaet.py`: AC-8 (alle vier Kanäle).

Bestandstests müssen grün bleiben, ohne Anpassung der Erwartung: `tests/tdd/test_alert_sms_onset_zeitpunkt.py`, `tests/tdd/test_alert_onset_day_rollover.py`, `tests/tdd/test_onset_*.py` (inkl. `test_onset_anchor_*`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Optional-Felder im bestehenden Ergebnisobjekt mit Fallback; keine neue Entscheidungsfläche (kein Kanal, Provider, Datenmodell-Bruch, keine Persistenz). Kanalparität folgt ADR-0095.

## Changelog

- 2026-11-27: Pflicht-Sektionen Scope, Definition of Done, Test Plan ergänzt (CI-Spec-Gate)
- 2026-11-27: Initial spec created (#2063, Radar-Uhrzeiten exakt am Frame-Zeitpunkt)
