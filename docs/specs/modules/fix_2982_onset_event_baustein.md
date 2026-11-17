---
entity_id: fix_2982_onset_event_baustein
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: fix-2982-onset-event-baustein
tags: [alarm, onset, paritaet, refactor, ADR-0021]
---

# Ein Baustein fuer den Alarm-Beginn (OnsetEvent), Issue #2982

## Approval

- [ ] Approved

## Purpose

Der Alarm-Beginn (`OnsetEvent`) wird heute an mehreren Stellen getrennt gebaut (Trip-Versand, Ortsvergleich-Buendel, Vorschau/Replay, eine veraltete Altform). Neue Felder fehlten dadurch immer wieder still auf einem Pfad (#2009, #2046, #2050, #2051, #2054). Diese Spec fuehrt den Bau auf EINEN Baustein in `project.py` zusammen, reiner Umbau ohne sichtbare Aenderung der Alarmtexte (Quelle: `paritaets_bestandsaufnahme.md`, Eintrag NEU-1, Folge aus #1986).

## Scope

**In Scope**

- Neuer Baustein in `src/output/renderers/alert/project.py`: `onset_event_from_nowcast` (NowcastResult → OnsetEvent) und `onset_event_from_fields` (generisch über `dataclasses.fields(OnsetEvent)`).
- Umstellung aller Bau-Stellen auf den Baustein: Trip-Ableitung (`trip_alert.py`), Trip-Versand (`notification_service.send_radar_alert`), Ortsvergleich-Bündel (`to_multi_location_onset_alert_message`), Replay und Vorschau (`validator_render_service.py`), Test-Mail-Fixture (`scripts/send_gate_test_mails.py`).
- Entfernen der ungenutzten Altform `radar_alert_service.build_onset_alert_message`, Umstellung der drei betroffenen Testdateien.
- Golden-Master der Alarmtexte (4 Kanäle × Trip/Vergleich/Replay × laufend/künftig), Feld-Paritäts-Ratsche und AST-Ratsche.

**Out of Scope**

- Vorschau-Lücken `gap_km` und `stage_number` (Payload trägt sie nicht; Angleichung wäre sichtbare Änderung).
- Feld `already_running` im `OnsetPayload` (Nebenbefund, Triage).
- Umbau von `RadarAlertRequest` auf ein eingebettetes `OnsetEvent` (Variante ii-a).
- Jede sichtbare Änderung an Alarmtexten, Go-API oder Frontend.

## Definition of Done

- AC-1 bis AC-9 sind durch automatisierte Tests (ohne Mock-Theater) abgedeckt und grün; die Mutations-Gegenproben (Feld weglassen, zweite `OnsetEvent(`-Baustelle) werden jeweils von mindestens einem Test gefangen.
- Golden-Master vor und nach dem Umbau byte-identisch; alle bestehenden Onset-Paritätstests grün; alle 6 CI-Checks grün.
- Renderer-Commit-Gate erfüllt (Modus-Matrix-Test und Mail-Validator frisch grün).
- Staging-Lauf ohne Fehler, Prod-Deploy mit Selftest-Exit 0.

## Source

- **File:** `src/output/renderers/alert/project.py`
- **Identifier:** `onset_event_from_nowcast` (neu), `onset_event_from_fields` (neu)

> Schicht: Python-Core (`src/output/renderers/alert/`, `src/services/`, `api/`). Kein Frontend, keine Go-API.
>
> Trip/Ortsvergleich-Teilung: Der Baustein ist EIN geteilter Code fuer Trip und Ortsvergleich (ADR-0021). Bewusste Pfad-Unterschiede bleiben Eingaben des Bausteins und werden nicht vereinheitlicht.
>
> Mandantentrennung: Keine Nutzerdaten werden bewegt; keine neue Persistenz, kein neuer Endpoint. Der Baustein ist reine Funktion ohne `user_id`.
>
> Kanaele: Alarmtexte in allen vier Kanaelen (E-Mail, Telegram, SMS, Premium-SMS) bleiben byte-identisch.

## Estimated Scope

- **LoC:** +~180 / -~330 (netto ca. -150)
- **Files:** ~6 Produktiv + 4 Test
- **Effort:** medium (Risiko MEDIUM: kritischer Alarmpfad aller vier Kanaele)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OnsetEvent` (`src/output/renderers/alert/model.py`) | dataclass | Zielstruktur des Alarm-Beginns |
| `alert_log.nowcast_onset_at` | function | Beginn-Zeitpunkt (laufend = JETZT) |
| `project.onset_display`, `event_end_display`, `source_reach_display`, `location_sharpness_display` | functions | Anzeigefelder aus `NowcastResult` |
| `utils.timezone.day_offset`, `local_fmt`, `local_dt` | functions | Zeitzonen- und Tagesbezug |
| `official_alerts._de_weekday_short` | function | Wochentagskuerzel |
| `RainZone` | dataclass | Regenzonen im Trip-Pfad |
| `RadarAlertRequest` (`notification_service.py`) | dataclass | Trip-Versandbuendel, bleibt bestehen |
| `OnsetPayload` (`api/routers/validator.py`) | pydantic | Eingabe der API-Vorschau |
| ADR-0021 | Entscheidung | Trip und Ortsvergleich teilen die Alarm-Ausgabe |
| `tests/tdd/test_onset_*`, `test_regen_ausdehnung_kanalparitaet.py`, `test_multi_location_onset_alert.py`, `test_fix_2219_onset_replay_tagesbezug.py`, `test_onset_callsite_timezone_guard.py` | Tests | Regressionswaechter, bleiben gruen |

## Implementation Details

Reihenfolge (Golden-Master zuerst):

1. **Golden-Master (RED/Netz):** Heutige Alarmtexte in allen vier Kanaelen fuer Trip, Ortsvergleich und Replay/Vorschau, je laufend und kuenftig, einfrieren.
2. **Baustein in `project.py`:**
   - `onset_event_from_nowcast(nc, *, now_utc, tz, intensity_label, source_label, km_from=0.0, km_to=0.0, **ortskontext)` baut ein `OnsetEvent` aus einem `NowcastResult`. Beginn ueber `alert_log.nowcast_onset_at` plus `onset_display`; Ende, Reichweite, Ortsschaerfe, Menge, `already_running`, `convective_checked` ueber die bestehenden Helfer.
   - `onset_event_from_fields(obj)` baut ein `OnsetEvent` generisch ueber `dataclasses.fields(OnsetEvent)` aus einem Objekt mit gleichnamigen Attributen (Request, Payload, SimpleNamespace); fehlende Attribute fallen auf die Defaults der Dataclass. Zusatzfelder (z. B. `stage_number`) werden als Override uebergeben.
3. **Ortsvergleich** (`to_multi_location_onset_alert_message`) nutzt `onset_event_from_nowcast`.
4. **Replay** (`_render_nowcast_replay`) und **Vorschau** (`render_alert_preview`) bauen ueber den Baustein; `rain_zones`-Umwandlung der Payload bleibt erhalten.
5. **Trip** (`trip_alert.py`) ersetzt die eigene Ableitung durch den Baustein; Request-Spiegelfelder werden generisch aus dem Event gefuellt. `send_radar_alert` baut mit `onset_event_from_fields(request)` plus `stage_number` statt Feld-fuer-Feld-Kopie.
6. **Altform entfernen:** `radar_alert_service.build_onset_alert_message` (kein Produktionsaufrufer) faellt weg; drei Testdateien (`test_alarm_intensitaet_logik_unveraendert.py`, `tdd/test_profil_ampel_kette.py` inkl. Zaehltabelle, `tdd/test_s1c4b_einstiege_loesen_das_abo_auf.py`) und der Kommentar in `scripts/send_gate_test_mails.py` werden umgestellt; `test_issue_919_radar_alert_canonical.py` wird bei Bedarf angepasst.
7. **Variante ii-b:** `RadarAlertRequest` behaelt seine Felder (rund zehn Testdateien konstruieren ihn). Die Feld-Paritaets-Ratsche stellt sicher, dass kein neues `OnsetEvent`-Feld still im Trip-Pfad fehlt.
8. **Ratschen** in `tests/tdd/test_onset_event_baustein.py`: Feld-Paritaet `fields(OnsetEvent)` ist Teilmenge von `RadarAlertRequest` plus Ausnahmeliste; AST-Ratsche: `OnsetEvent(` wird in `src/` und `api/` nur in `project.py` konstruiert (`scripts/send_gate_test_mails.py` ueber den Baustein oder als dokumentierte Ausnahme der Ratsche).

**Bewusste Pfad-Unterschiede (bleiben Eingaben):** Labels (Trip: Intensitaet klein plus `radar_svc.source_label`; Vergleich: `nc.intensity_label` und `nc.source` roh; Replay: `_SOURCE_LABELS`), Zeitzone (Trip `tz`, Vergleich `loc_tz` je Ort, Replay `alert_tz`), `km=0` und `location_label` nur im Vergleich, `rain_zones`/`gap_km`/`km_measured`/`segment_id`/`briefing_context`/`stage_number` nur im Trip.

**Beginn-Divergenz:** Trip bildet den Zeitpunkt ueber `nowcast_onset_at` (laufend = JETZT), Vergleich/Replay bisher ueber `now + onset_minutes`. Ausgabe-neutral, weil alle Textformen bei `already_running` vor `onset_time` verzweigen; `onset_minutes` bleibt `nc.onset_minutes or 0`, der Sortierschluessel behandelt laufend bereits als 0.

**Renderer-Commit-Gate:** Aenderung unter `src/output/renderers/` loest das Gate aus; Modus-Matrix-Test und Validator muessen frisch gruen sein.

## Expected Behavior

- **Input:** `NowcastResult` (Trip, Vergleich, Replay) bzw. Request/Payload mit `OnsetEvent`-Feldern (Versand, Vorschau).
- **Output:** `OnsetEvent`, aus dem die vier Kanal-Renderer unveraendert denselben Alarmtext erzeugen wie vor dem Umbau.
- **Side effects:** keine; reine Funktionen.

## Test Plan

### Automated Tests (TDD RED)

Alle Tests laufen ohne Mocks, die nur die eigene Annahme spiegeln; Golden-Master gegen echte Renderer-Ausgabe.

- [ ] Golden-Master: GIVEN dieselbe Radar-Lage (laufend und kuenftig) WHEN Trip, Ortsvergleich und Replay in E-Mail, Telegram, SMS und Premium-SMS rendern THEN ist jeder Text byte-identisch zum eingefrorenen Stand vor dem Umbau.
- [ ] Baustein: GIVEN ein `NowcastResult` mit laufendem Regen WHEN `onset_event_from_nowcast` baut THEN `already_running` gesetzt, Beginn = JETZT, `onset_minutes` = 0.
- [ ] Baustein: GIVEN ein `NowcastResult` mit Beginn in 40 Minuten ueber Mitternacht WHEN der Baustein baut THEN stimmen Beginn-Zeit, Tagesversatz und Wochentagskuerzel mit der Zeitzone ueberein.
- [ ] Generisch: GIVEN ein Objekt mit allen `OnsetEvent`-Feldern WHEN `onset_event_from_fields` baut THEN ist jedes Feld 1:1 uebernommen; fehlende Felder haben die Dataclass-Defaults.
- [ ] Ortsvergleich: GIVEN zwei Orte in verschiedenen Zeitzonen WHEN das Buendel gebaut wird THEN hat jedes Event `km=0`, sein `location_label` und die Ortszeit.
- [ ] Ratsche Feldsatz: `fields(OnsetEvent)` ist Teilmenge von `RadarAlertRequest` plus Ausnahmeliste; ein neu hinzugefuegtes Feld ohne Eintrag macht den Test rot.
- [ ] Ratsche Bau: AST-Scan von `src/` und `api/` findet `OnsetEvent(` nur in `project.py`.
- [ ] Altform: `build_onset_alert_message` ist nicht mehr importierbar; die drei umgestellten Testdateien laufen gruen.
- [ ] Regressionswaechter: die genannten Paritaetstests laufen unveraendert gruen.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Nutzer mit Regenalarm (laufend oder kuenftig) / When der Alarm nach dem Umbau ueber E-Mail, Telegram, SMS und Premium-SMS versendet wird / Then sind alle vier Alarmtexte byte-identisch zu den Texten vor dem Umbau.
  - Test: Golden-Master rendert Trip-Alarm in vier Kanaelen und vergleicht mit dem eingefrorenen Vorher-Stand.

- **AC-2:** Given ein Nutzer mit Ortsvergleich-Alarm fuer mehrere Orte in verschiedenen Zeitzonen / When der gebuendelte Alarm in allen vier Kanaelen erzeugt wird / Then bleiben Ortsnamen, Ortszeiten, Entfernung 0 und alle Texte byte-identisch zum Stand vor dem Umbau.
  - Test: Golden-Master Ortsvergleich-Buendel, vier Kanaele, laufend und kuenftig, zwei Zeitzonen.

- **AC-3:** Given eine Alarm-Vorschau bzw. ein Replay im Validator / When die Vorschau nach dem Umbau gerendert wird / Then entspricht jeder Kanaltext dem Stand vor dem Umbau, auch die bekannten Luecken (keine Etappennummer, kein Abstand in der Vorschau) bleiben unveraendert.
  - Test: Golden-Master Vorschau (API-Payload) und Replay, vier Kanaele, laufend und kuenftig.

- **AC-4:** Given Regen laeuft bereits, wenn der Alarm ausgeloest wird / When Trip, Ortsvergleich und Replay den Alarm bauen / Then zeigen alle drei Pfade "laeuft bereits" ohne Beginnzeit und mit gleicher Reihenfolge im Buendel.
  - Test: Baustein-Test `already_running` plus Golden-Master laufend in allen drei Pfaden.

- **AC-5:** Given der Beginn liegt nach Mitternacht oder in einer anderen Zeitzone als UTC / When der Baustein den Beginn berechnet / Then stimmen Uhrzeit, Tagesbezug und Wochentagskuerzel mit der jeweils uebergebenen Zeitzone ueberein.
  - Test: Baustein-Test mit Beginn ueber Mitternacht in Europe/Berlin und Europe/Lisbon-Zeitzone.

- **AC-6:** Given `OnsetEvent` bekommt kuenftig ein neues Feld / When es nicht im Trip-Versandbuendel (`RadarAlertRequest`) oder in der Ausnahmeliste steht / Then schlaegt die Feld-Paritaets-Ratsche rot an, statt dass das Feld still auf einem Pfad fehlt.
  - Test: Ratsche `fields(OnsetEvent)` Teilmenge von `RadarAlertRequest` plus Ausnahmeliste; Mutationsprobe mit einem zusaetzlichen Testfeld.

- **AC-7:** Given der Produktivcode in `src/` und `api/` / When der Quelltext per AST geprueft wird / Then wird `OnsetEvent(` ausschliesslich in `src/output/renderers/alert/project.py` gebaut.
  - Test: AST-Ratsche ueber `src/` und `api/`; `scripts/send_gate_test_mails.py` geht ueber den Baustein oder steht dokumentiert in der Ausnahmeliste.

- **AC-8:** Given die veraltete Altform `build_onset_alert_message` ohne Produktionsaufrufer / When der Umbau abgeschlossen ist / Then existiert sie nicht mehr und alle bisherigen Tests laufen ueber den Baustein gruen.
  - Test: Import der Altform schlaegt fehl; die drei umgestellten Testdateien laufen gruen.

- **AC-9:** Given die bestehenden Paritaetstests fuer Onset (Zeitzone, Ende, Regen-Ausdehnung, Wochentagskuerzel, Menge, Reichweite/Guete, Replay-Tagesbezug, Multi-Location) / When sie nach dem Umbau laufen / Then sind alle unveraendert gruen.
  - Test: Lauf der benannten Testdateien als Regressionswaechter.

## Known Limitations

- Vorschau-Luecken `gap_km` und `stage_number` bleiben unveraendert (der Vorschau-Payload traegt sie nicht); Angleichung waere eine sichtbare Aenderung und gehoert in ein eigenes Issue.
- Nebenbefund: `OnsetPayload` hat kein Feld `already_running`, die API-Vorschau kann den Laufend-Fall nicht zeigen (nur Replay). Out of Scope, fuer die Nebenbefund-Triage notieren.
- `RadarAlertRequest` bleibt mit eigenen Feldern (Variante ii-b); die Doppelung der Feldnamen wird durch die Ratsche bewacht, nicht beseitigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (stuetzt sich auf ADR-0021)
- **Rationale:** Der Umbau setzt ADR-0021 (Trip und Ortsvergleich teilen die Alarm-Ausgabe) konsequent um und aendert keine Entscheidung. Variante ii-b (Request behaelt Felder) ist eine Umsetzungsabwaegung: ii-a haette rund zehn Testdateien gekostet bei geringem Zusatzgewinn.

## Changelog

- 2026-11-17: Initial spec created (Issue #2982, Folge aus #1986 / NEU-1)
